//! The recognition seam: turn one bracketed speech utterance (16 kHz mono `f32`) into
//! transcript text.
//!
//! [`Recognizer`] is the trait; [`FakeRecognizer`] is a deterministic canned-text
//! implementation for tests (and any no-model run). [`WhisperRecognizer`] (feature
//! `whisper`) is the real whisper.cpp backend. The engine calls `transcribe` once per
//! closed utterance, off the host thread, so a slow recognition never blocks the render
//! path.

/// One bracketed span of speech to be recognized: 16 kHz mono `f32` plus its position in
/// the session (ms from the session origin, derived from the sample clock — no wall clock).
#[derive(Debug, Clone, PartialEq)]
pub struct Utterance {
    /// 16 kHz mono samples for this utterance.
    pub samples: Vec<f32>,
    /// Utterance start, ms from the session origin.
    pub start_ms: u64,
    /// Utterance end, ms from the session origin (`>= start_ms`).
    pub end_ms: u64,
}

impl Utterance {
    /// Build an utterance, clamping `end_ms` to be `>= start_ms`.
    pub fn new(samples: Vec<f32>, start_ms: u64, end_ms: u64) -> Self {
        Utterance {
            samples,
            start_ms,
            end_ms: end_ms.max(start_ms),
        }
    }
}

/// A recognized span of text with its timing and whether it is a committed final.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecognizedSegment {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    /// `false` for a streaming interim hypothesis; the offline chunked backends emit finals.
    pub is_final: bool,
}

impl RecognizedSegment {
    /// A final segment.
    pub fn final_text(text: impl Into<String>, start_ms: u64, end_ms: u64) -> Self {
        RecognizedSegment {
            text: text.into(),
            start_ms,
            end_ms: end_ms.max(start_ms),
            is_final: true,
        }
    }
}

/// The recognition seam. Given a closed utterance, return zero or more recognized segments.
/// Deterministic implementations (the fake) return exactly their canned output.
pub trait Recognizer {
    /// A stable, human-readable engine name for honest disclosure (FR-120), e.g.
    /// `"whisper-large-v3-turbo"` or `"fake"`.
    fn label(&self) -> &str;

    /// Recognize one utterance. Empty text results are the recognizer's own concern to
    /// suppress; the engine additionally drops empties defensively.
    fn transcribe(&mut self, utterance: &Utterance) -> Vec<RecognizedSegment>;
}

/// A deterministic recognizer that returns pre-supplied text, one canned line per utterance.
///
/// Feed it a script of strings; each `transcribe` pops the next one and returns it as a
/// single final segment spanning the utterance. When the script is exhausted it returns
/// nothing. This makes the whole pipeline reproducible with no model.
#[derive(Debug, Clone, Default)]
pub struct FakeRecognizer {
    scripts: std::collections::VecDeque<String>,
}

impl FakeRecognizer {
    /// A recognizer with no canned lines (returns nothing).
    pub fn new() -> Self {
        FakeRecognizer {
            scripts: std::collections::VecDeque::new(),
        }
    }

    /// A recognizer pre-loaded with a script of lines, one returned per utterance.
    pub fn with_script(lines: impl IntoIterator<Item = impl Into<String>>) -> Self {
        FakeRecognizer {
            scripts: lines.into_iter().map(Into::into).collect(),
        }
    }

    /// Queue one more canned line.
    pub fn push_line(&mut self, line: impl Into<String>) {
        self.scripts.push_back(line.into());
    }
}

impl Recognizer for FakeRecognizer {
    fn label(&self) -> &str {
        "fake"
    }

    fn transcribe(&mut self, utterance: &Utterance) -> Vec<RecognizedSegment> {
        match self.scripts.pop_front() {
            Some(text) => vec![RecognizedSegment::final_text(
                text,
                utterance.start_ms,
                utterance.end_ms,
            )],
            None => Vec::new(),
        }
    }
}

#[cfg(feature = "whisper")]
pub use whisper_backend::WhisperRecognizer;

#[cfg(feature = "whisper")]
mod whisper_backend {
    //! Real on-device recognition via `whisper-rs` (whisper.cpp). Compiled only under the
    //! `whisper` feature so the default build needs no native toolchain or model file.
    //! Accuracy/latency are spike-gated (S8/S11) and not asserted by this crate's tests.

    use super::{RecognizedSegment, Recognizer, Utterance};
    use crate::model::ModelSelection;
    use std::path::Path;

    use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

    /// whisper.cpp-backed recognizer. Holds a loaded model context and transcribes each
    /// utterance with greedy decoding. Construct it only after the model file has been
    /// integrity-verified ([`crate::model::verify_model`]).
    pub struct WhisperRecognizer {
        ctx: WhisperContext,
        label: String,
        threads: i32,
    }

    impl WhisperRecognizer {
        /// Load a verified model from `model_path` using the given hardware `selection`.
        ///
        /// The caller MUST have verified the model's integrity first (FR-156); this method
        /// only loads. Returns an error string on load failure rather than panicking.
        pub fn load(model_path: &Path, selection: &ModelSelection) -> Result<Self, String> {
            let path = model_path
                .to_str()
                .ok_or_else(|| "model path is not valid UTF-8".to_string())?;
            let ctx = WhisperContext::new_with_params(path, WhisperContextParameters::default())
                .map_err(|e| format!("whisper load: {e}"))?;
            Ok(WhisperRecognizer {
                ctx,
                label: format!("whisper-{}", selection.model.as_str()),
                threads: selection.threads.max(1) as i32,
            })
        }
    }

    impl Recognizer for WhisperRecognizer {
        fn label(&self) -> &str {
            &self.label
        }

        fn transcribe(&mut self, utterance: &Utterance) -> Vec<RecognizedSegment> {
            let mut state = match self.ctx.create_state() {
                Ok(s) => s,
                Err(_) => return Vec::new(),
            };
            let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
            params.set_n_threads(self.threads);
            params.set_translate(false);
            params.set_print_special(false);
            params.set_print_progress(false);
            params.set_print_realtime(false);
            params.set_print_timestamps(false);
            if state.full(params, &utterance.samples).is_err() {
                return Vec::new();
            }
            let n = state.full_n_segments().unwrap_or(0);
            let mut out = Vec::new();
            for i in 0..n {
                if let Ok(text) = state.full_get_segment_text(i) {
                    let trimmed = text.trim();
                    if !trimmed.is_empty() {
                        out.push(RecognizedSegment::final_text(
                            trimmed,
                            utterance.start_ms,
                            utterance.end_ms,
                        ));
                    }
                }
            }
            out
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fake_returns_scripted_lines_in_order() {
        let mut r = FakeRecognizer::with_script(["hello", "world"]);
        let u = Utterance::new(vec![0.0; 320], 0, 20);
        assert_eq!(r.transcribe(&u)[0].text, "hello");
        assert_eq!(r.transcribe(&u)[0].text, "world");
        assert!(r.transcribe(&u).is_empty());
    }

    #[test]
    fn recognized_segment_clamps_end() {
        let s = RecognizedSegment::final_text("x", 100, 50);
        assert_eq!(s.end_ms, 100);
    }
}
