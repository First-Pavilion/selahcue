//! The recognition seam: turn one bracketed speech utterance (16 kHz mono `f32`) into
//! transcript text.
//!
//! [`Recognizer`] is the trait; [`FakeRecognizer`] is a deterministic canned-text
//! implementation for tests (and any no-model run). [`WhisperRecognizer`] (feature
//! `whisper`) is the real whisper.cpp backend. The engine calls `transcribe` once per
//! closed utterance, off the host thread, so a slow recognition never blocks the render
//! path. `transcribe` borrows the samples (it never takes ownership) so the engine can
//! reuse its utterance buffer across calls (no per-utterance re-allocation).

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

/// The recognition seam. Given one closed utterance's 16 kHz mono samples and its span
/// (ms from the session origin), return zero or more recognized segments. The samples are
/// borrowed, never consumed. Deterministic implementations (the fake) return exactly their
/// canned output.
pub trait Recognizer {
    /// A stable, human-readable engine name for honest disclosure (FR-120), e.g.
    /// `"whisper-large-v3-turbo"` or `"fake"`.
    fn label(&self) -> &str;

    /// Recognize one utterance (`samples` = 16 kHz mono `f32`). Empty text results are the
    /// recognizer's own concern to suppress; the engine additionally drops empties.
    fn transcribe(&mut self, samples: &[f32], start_ms: u64, end_ms: u64)
        -> Vec<RecognizedSegment>;
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

    fn transcribe(
        &mut self,
        _samples: &[f32],
        start_ms: u64,
        end_ms: u64,
    ) -> Vec<RecognizedSegment> {
        match self.scripts.pop_front() {
            Some(text) => vec![RecognizedSegment::final_text(text, start_ms, end_ms)],
            None => Vec::new(),
        }
    }
}

#[cfg(feature = "whisper")]
pub use whisper_backend::{WhisperContext, WhisperRecognizer};

#[cfg(feature = "whisper")]
mod whisper_backend {
    //! Real on-device recognition via `whisper-rs` (whisper.cpp). Compiled only under the
    //! `whisper` feature so the default build needs no native toolchain or model file.
    //! Accuracy/latency are spike-gated (S8/S11) and not asserted by this crate's tests.

    use super::{RecognizedSegment, Recognizer};
    use crate::model::{verify_model, ModelSelection};
    use std::path::Path;
    use std::sync::Arc;

    pub use whisper_rs::WhisperContext;
    use whisper_rs::{FullParams, SamplingStrategy, WhisperContextParameters};

    /// whisper.cpp-backed recognizer. Holds a **shared** loaded model context (`Arc`) so a
    /// stop→start can reuse the resident model instead of reloading it, and transcribes each
    /// utterance with greedy decoding.
    pub struct WhisperRecognizer {
        ctx: Arc<WhisperContext>,
        label: String,
        threads: i32,
    }

    impl WhisperRecognizer {
        /// Verify (FR-156) then load a model from `model_path`. The model is SHA-256-checked
        /// against `expected_sha256` **before** it is handed to whisper.cpp — a mismatch
        /// refuses to load (integrity is enforced here, not left to the caller). Use this for a
        /// path whose integrity is NOT already established (e.g. an operator-supplied file).
        pub fn load(
            model_path: &Path,
            expected_sha256: &str,
            selection: &ModelSelection,
        ) -> Result<Self, String> {
            // FR-156 / ADR-0012: integrity gate before load.
            verify_model(model_path, expected_sha256).map_err(|e| e.to_string())?;
            Self::load_unverified(model_path, selection)
        }

        /// Load a model **without** re-hashing it — for a path whose SHA-256 was ALREADY verified
        /// (the download/cache path verifies on fetch). Re-hashing a ~1.6 GB file on every start
        /// is pure latency before the mic even opens, so the caller vouches for integrity here.
        pub fn load_unverified(
            model_path: &Path,
            selection: &ModelSelection,
        ) -> Result<Self, String> {
            let path = model_path
                .to_str()
                .ok_or_else(|| "model path is not valid UTF-8".to_string())?;
            let ctx = WhisperContext::new_with_params(path, WhisperContextParameters::default())
                .map_err(|e| format!("whisper load: {e}"))?;
            Ok(Self::from_context(Arc::new(ctx), selection))
        }

        /// Build a recognizer around an already-loaded, shared model context — so a stop→start
        /// reuses the resident model (load once) instead of re-verifying + reloading it.
        pub fn from_context(ctx: Arc<WhisperContext>, selection: &ModelSelection) -> Self {
            WhisperRecognizer {
                ctx,
                label: format!("whisper-{}", selection.model.as_str()),
                threads: selection.threads.max(1) as i32,
            }
        }

        /// The shared model context, for caching across capture sessions (bounded: one model).
        pub fn context(&self) -> Arc<WhisperContext> {
            Arc::clone(&self.ctx)
        }
    }

    impl Recognizer for WhisperRecognizer {
        fn label(&self) -> &str {
            &self.label
        }

        fn transcribe(
            &mut self,
            samples: &[f32],
            start_ms: u64,
            end_ms: u64,
        ) -> Vec<RecognizedSegment> {
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
            if state.full(params, samples).is_err() {
                return Vec::new();
            }
            let n = state.full_n_segments().unwrap_or(0);
            let mut out = Vec::new();
            for i in 0..n {
                if let Ok(text) = state.full_get_segment_text(i) {
                    let trimmed = text.trim();
                    if !trimmed.is_empty() {
                        out.push(RecognizedSegment::final_text(trimmed, start_ms, end_ms));
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
        let frame = vec![0.0_f32; 320];
        assert_eq!(r.transcribe(&frame, 0, 20)[0].text, "hello");
        assert_eq!(r.transcribe(&frame, 20, 40)[0].text, "world");
        assert!(r.transcribe(&frame, 40, 60).is_empty());
    }

    #[test]
    fn recognized_segment_clamps_end() {
        let s = RecognizedSegment::final_text("x", 100, 50);
        assert_eq!(s.end_ms, 100);
    }
}
