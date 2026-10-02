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

    /// Fixed `FullParams::set_audio_ctx` value for EVERY decode this recognizer runs.
    ///
    /// Left at the whisper.cpp default (0 = full 1,500-position / 30 s context), `full()`
    /// zero-pads whatever audio it is given up to a 30 s mel frame and runs the whole
    /// encoder over it — cost is therefore FLAT (~1.05-1.15 s measured) no matter how short
    /// the window is. Interims fire every 0.8 s of speech, so that flat cost alone makes the
    /// pipeline fall behind on any hardware (measured: mean lag climbed 3.6 s -> 14.0 s over
    /// a 126 s paced run). Capping the context to cover only the audio actually given bounds
    /// per-decode cost to a ~2.9-3.2x cut across the whole range this pipeline actually
    /// produces (measured on real, non-repeating speech, Apple M5/Metal: ~270-430 ms from
    /// 1.6 s up to the 10 s force-close), with recognized text byte-identical to the uncapped
    /// baseline at every window measured. Independently re-verified by a performance review
    /// (Vera, 86akcfp3u), which found no reason to change this constant.
    ///
    /// This ONE value is used for every call — not a value picked per window length —
    /// because the FIRST decode at a new context shape rebuilds whisper.cpp's compute graph,
    /// costing an extra 1.3-2.0 s; varying the context per call would reintroduce exactly the
    /// latency spikes this fix removes (and did: a 512-for-interims / 1024-for-finals split
    /// dropped 0.96 s of audio in a real-time run, 86akcgmuh spike).
    ///
    /// **WHY 576, NOT 86akcfp3u's ORIGINAL 512 (17tnw2b0nkq, from the 86akcgmuh spike).** A
    /// final force-closed at the 10.000 s cap usually ends mid-word, and at 512 the encoder then
    /// sees only 0.24 s past the cut (512 / 50 = 10.24 s). With almost no silence after the
    /// abrupt end, greedy decoding frequently says the preceding phrase again ("…and then wait
    /// long and then wait long and then wait"). The loop rate falls steadily as that tail grows
    /// (spike, N = 370 ten-second windows ending mid-speech, 20 synthetic voices, 16 texts):
    /// 512 -> 7.8%, **576 -> 3.2%**, 640 -> 2.7%, 1024 -> 1.4%, uncapped -> 0.3% (the mechanism
    /// is Inferred from that dose-response, not proven). 576 is the cheapest step that captures
    /// most of the gain: its measured cost against 512 is within noise, while 768 (~1.35x) and
    /// 1024 (~1.3-1.5x) cost clearly more per 10 s final in the spike's A/B. The engine additionally trims any loop that remains on a
    /// force-closed final (`crate::repetition::trim_trailing_repeat`); the two are independent
    /// and `a_force_closed_final_ending_mid_word_does_not_repeat_itself` guards this constant
    /// on its own (its raw-decode layer). 576 also satisfies the alignment constraint below.
    ///
    /// ENVELOPE COUPLING WITH `engine.rs` — READ BEFORE CHANGING EITHER CONSTANT (Cody/Vera
    /// finding, 86akcfp3u review; tracked for phase 2, 86akcfp6z, not fixed here). `audio_ctx`
    /// does not just bound cost — it bounds how much audio the encoder can see AT ALL.
    /// whisper.cpp's context units are 20 ms each (30 s of context / 1,500 positions), so
    /// `audio_ctx` covers exactly `audio_ctx / 50` seconds of real audio: 576 -> **11.52 s**
    /// (512 -> 10.24 s before 17tnw2b0nkq). Feed it more than that and whisper.cpp does not
    /// slow down gradually — cost jumps ~5x (a second internal encode+decode pass) AND the extra
    /// audio is silently NOT transcribed. Measured on real speech at 512: 10.0 s -> 178 chars
    /// (~400 ms); 10.24 s -> 183 chars (~2.2-3.1 s); 10.5 s and 11.0 s -> the SAME 183 chars. A
    /// full extra second of real speech produced zero additional words past the envelope —
    /// silent content loss, not a crash or an error.
    ///
    /// `engine.rs`'s `EngineConfig::max_utterance_samples` defaults to `10 *
    /// TARGET_SAMPLE_RATE` = exactly 10.000 s, the longest any utterance (interim or final)
    /// ever gets before force-close — so production sits 1.52 s (13%) under this cliff at
    /// 576 (0.24 s at the original 512), but nothing in the code ties the two constants together. If
    /// `max_utterance_samples` is ever raised (phase 2 is scheduled to touch `engine.rs`)
    /// without revisiting `WHISPER_AUDIO_CTX` in lockstep, long utterances start silently
    /// losing trailing words while looking like a pure win. Whoever touches either constant
    /// next: `WHISPER_AUDIO_CTX / 50` (seconds) MUST stay comfortably above whatever
    /// `max_utterance_samples` allows, with real margin, not just a positive one. This crate
    /// cannot enforce that at compile time from here — it would need `max_utterance_samples`,
    /// which lives in `engine.rs` and is out of scope for this fix — so today it is enforced
    /// as this comment plus a phase-2 tracking item, not a cross-file static assertion.
    ///
    /// ALIGNMENT CONSTRAINT, derived (not sampled) from the vendored source this build
    /// compiles (`whisper-rs-sys` 0.13.1, via a security review, 86akcfp3u): on the
    /// non-flash-attention decode path, the cross-attention KV view is built with byte stride
    /// `n_audio_ctx * 2` (the KV cache is fp16, `whisper.cpp:2584-2587`), and Metal's F16
    /// matmul kernel asserts `nb01 % 8 == 0` (`ggml-metal.m:2263`) — so the constraint is
    /// exactly `audio_ctx % 4 == 0` on this vendored version (the same reduction holds for
    /// F32/BF16 too). This session's own sweep (512, 532, 600, 700, 800, 900, 1000) all pass
    /// it; 650 fails it (SIGABRT). A performance review independently confirmed the
    /// derivation at an untested adjacent pair: 654 fails, 656 passes. Values above the
    /// model's own maximum (1,500 for this model) are rejected cleanly with an error, not a
    /// crash (`whisper.cpp:5473`). This rule is version-pinned — re-derive it on any
    /// whisper-rs bump or before tuning CUDA/Vulkan/CPU values, which have their own kernels
    /// and alignment rules. The `const _` assertion below pins the arithmetic half (multiple
    /// of 4, within the model's own maximum) so a future out-of-range or misaligned retune
    /// fails to compile instead of aborting at runtime.
    ///
    /// Applied to BOTH a streaming interim decode and the end-of-utterance final: this
    /// method's signature (`samples`, `start_ms`, `end_ms`) carries no signal distinguishing
    /// the two — `SttEngine::emit_interim` and `SttEngine::close_utterance` both call the
    /// same `Recognizer::transcribe`, and giving one of them a different context belongs to
    /// `engine.rs`, which is out of scope for this fix (see ticket 86akcfp3u; the phase-2
    /// backpressure sub-issue that also touches `engine.rs` is 86akcfpbj). Applying the one
    /// value to both is the deliberate, measured choice, independently re-verified: a
    /// performance review found recognized text byte-identical between capped and uncapped
    /// decodes across the whole ramp a real utterance grows through before the 6 s interim
    /// window engages (1.6/2.4/3.2/4.8/5.6 s) and at the 10 s final — not an accident of a
    /// shared params builder.
    ///
    /// **86akcgmvb resolution, added after this doc comment's original "this crate cannot
    /// enforce that at compile time from here" line was written — that line is still true of
    /// THIS constant (it only ever pins the DEFAULT), but the coupling itself is now enforced,
    /// at `engine.rs`'s `SttEngine::build`/`build_with_clock`, as a RUNTIME check against a
    /// mirrored horizon constant, `engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES` — a compile-time-
    /// only assertion could never have covered a `listening.rs`-supplied runtime value anyway.**
    /// The const assertion immediately below this one pins that mirrored constant EQUAL to this
    /// one, so the two cannot silently drift apart on any build that actually compiles this
    /// `whisper` module.
    const WHISPER_AUDIO_CTX: std::os::raw::c_int = 576;

    // Pins the arithmetic half of the ALIGNMENT CONSTRAINT above at compile time: a future
    // retune to a misaligned or out-of-range value fails the build instead of SIGABRT-ing
    // whisper.cpp's Metal backend at runtime. Wording per security review, 86akcfp3u.
    const _: () = assert!(
        WHISPER_AUDIO_CTX > 0 && WHISPER_AUDIO_CTX <= 1500 && WHISPER_AUDIO_CTX % 4 == 0,
        "audio_ctx must be positive, <= n_audio_ctx (1500), and a multiple of 4: Metal's F16 \
         matmul asserts nb01 % 8 == 0 on a 2-byte-per-element stride (SIGABRT otherwise) -- \
         see WHISPER_AUDIO_CTX's doc comment"
    );

    // 86akcgmvb: keeps `engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES` (the always-compiled mirror
    // the runtime `max_utterance_samples` guard checks against, since this whole module is
    // gated behind the heavy `whisper` feature and the guard's default build cannot see
    // `WHISPER_AUDIO_CTX` directly) pinned EQUAL to the real value here, on any build that
    // actually compiles this module. A retune of either constant without the other fails the
    // BUILD, not a test that might not be run — see `engine.rs`'s `WHISPER_AUDIO_CTX_HORIZON_SAMPLES`
    // doc comment for the full reasoning.
    const _: () = assert!(
        crate::engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES
            == (WHISPER_AUDIO_CTX as usize) * (crate::TARGET_SAMPLE_RATE as usize) / 50,
        "engine::WHISPER_AUDIO_CTX_HORIZON_SAMPLES must track WHISPER_AUDIO_CTX exactly, or the \
         runtime max_utterance_samples guard (86akcgmvb) checks against the wrong horizon \
         whenever the whisper feature is actually compiled in"
    );

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
            // Bound the encoder pass to the audio actually given to it (see
            // WHISPER_AUDIO_CTX's doc comment) instead of paying a flat ~1.05-1.15 s
            // zero-padded-to-30s cost on every call — this is the fix for the measured
            // 3.6 s -> 14.0 s transcript lag (86akcfp3u).
            params.set_audio_ctx(WHISPER_AUDIO_CTX);
            // Force one output segment per call. This backend already receives exactly one
            // VAD-bracketed span per call (an interim window or the closed utterance), so
            // there is nothing useful for whisper.cpp's own internal segmentation to split —
            // and today, without this, a multi-segment result from one call is emitted as
            // MULTIPLE `RecognizedSegment`s that all carry the SAME (start_ms, end_ms) (this
            // function's parameters, not per-segment timestamps), a duplicate-timestamp
            // artifact this removes rather than introduces (mechanism independently
            // confirmed structurally real by code review, 86akcfp3u: whisper.cpp's own
            // seek/segment loop is what reuses the shared timestamp on a multi-segment call).
            //
            // EVIDENCED, not just plausible: code review raised a real, different risk here —
            // that forcing single-segment could truncate trailing audio if the model ever
            // emits an early end-of-text token before the window's true end (a known
            // whisper.cpp behavior around mid-utterance pauses). Tested twice and cleared: an
            // A/B on four independent 10 s continuous-speech slices (single_segment on vs.
            // off, same ctx) produced identical text in all four pairs, and a purpose-built
            // fixture with four clauses separated by 500/650/400 ms pauses (the shape most
            // likely to trigger an early EOT) was also byte-identical across both arms
            // (86akcfp3u review, Vera + Quinn). No accuracy cost found.
            // The engine's force-close trim (`engine.rs`, `close_utterance`, 17tnw2b0nkq) depends
            // on this: with one segment per call, trimming "per segment" is trimming "per
            // utterance". Dropping this setting makes that code trim every segment, not just
            // the one that ends at the cut — read its doc comment first.
            params.set_single_segment(true);
            if state.full(params, samples).is_err() {
                return Vec::new();
            }
            // whisper-rs 0.16: `full_n_segments` no longer returns a `Result`, and a segment's
            // text comes from `get_segment(i)` + `to_str()`. `to_str()` is the STRICT accessor —
            // like 0.14's `full_get_segment_text`, a segment whose bytes are not valid UTF-8 is
            // skipped rather than repaired (`to_str_lossy` would silently insert U+FFFD into the
            // transcript).
            let n = state.full_n_segments();
            let mut out = Vec::new();
            for i in 0..n {
                if let Some(Ok(text)) = state.get_segment(i).map(|seg| seg.to_str()) {
                    let trimmed = text.trim();
                    if !trimmed.is_empty() {
                        out.push(RecognizedSegment::final_text(trimmed, start_ms, end_ms));
                    }
                }
            }
            out
        }
    }

    /// Behavioural tests against the REAL whisper.cpp backend and the real
    /// `ggml-large-v3-turbo.bin` model. These are slow and gated on the model file being
    /// present in the OS cache (the crate's own accuracy/latency policy, see the module doc
    /// above) — each test skips cleanly (with an `eprintln!`) rather than failing when the
    /// model is absent, so the suite still passes on a machine without it. No CI job
    /// currently runs the `whisper`/`metal` features that compile this module at all
    /// (86ak5rjh7), so these are real assertions with real evidence, but ungated in CI today.
    #[cfg(test)]
    mod whisper_tests {
        use super::*;
        use crate::model::{Backend, HardwareProbe, WhisperModel};
        use std::io::Read as _;
        use std::path::PathBuf;
        use std::sync::Mutex;
        use std::time::{Duration, Instant};

        /// `cargo test`'s default runner executes tests concurrently across threads. Each
        /// test in this module loads its OWN ~1.6 GB model and creates its OWN Metal
        /// context/state — running several of those truly concurrently thrashes the GPU
        /// (measured: an 8s decode that takes ~430 ms run alone measured 17+ s when four of
        /// these tests happened to start together). This isn't a timing property of the fix;
        /// it's resource contention between tests. Every timing-sensitive test below takes
        /// this lock for its whole body so at most one real-model decode runs at a time,
        /// regardless of `cargo test`'s thread count — a correctness requirement of the test
        /// harness, not a workaround for `--test-threads=1` callers have to remember.
        static WHISPER_TEST_LOCK: Mutex<()> = Mutex::new(());

        /// Acquire the shared GPU-serialization lock, recovering from a poisoned lock (an
        /// earlier test panicking while it held the lock must not cascade-fail every test
        /// after it — the panic is already reported by that test).
        fn lock_whisper_gpu() -> std::sync::MutexGuard<'static, ()> {
            WHISPER_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner())
        }

        /// The path this crate's other code (model.rs, model_fetch.rs) writes/expects the
        /// downloaded large-v3-turbo model at. `None` if `HOME` is unset or the file is
        /// missing/wrong-sized (a partial download) — either way the caller should skip.
        fn cached_model_path() -> Option<PathBuf> {
            let home = std::env::var_os("HOME")?;
            let path = PathBuf::from(home)
                .join("Library/Caches/selahcue/models")
                .join(WhisperModel::LargeV3Turbo.asset().file_name);
            let expected_len = WhisperModel::LargeV3Turbo.asset().size_bytes;
            match std::fs::metadata(&path) {
                Ok(m) if m.len() == expected_len => Some(path),
                _ => None,
            }
        }

        /// A `ModelSelection` that forces the real production model + the Metal backend,
        /// independent of `HardwareProbe::select_model`'s step-down logic (which would pick a
        /// smaller model when the `metal` feature isn't compiled in) — these tests want to
        /// reproduce the investigation's own measurement conditions (large-v3-turbo, Metal).
        fn production_selection() -> ModelSelection {
            ModelSelection {
                model: WhisperModel::LargeV3Turbo,
                threads: HardwareProbe::detect().threads.saturating_sub(1).max(1),
                backend: Backend::Metal,
            }
        }

        /// Load the cached model with full SHA-256 verification (the same integrity gate
        /// production takes for a not-yet-verified path) — a test correctness choice over
        /// `load_unverified`'s speed, since this suite runs rarely and only locally.
        fn load_test_recognizer(model_path: &Path) -> WhisperRecognizer {
            let asset = WhisperModel::LargeV3Turbo.asset();
            WhisperRecognizer::load(model_path, asset.sha256, &production_selection())
                .expect("cached model at the pinned path/size must load and verify")
        }

        /// Minimal RIFF/WAVE chunk walk to pull out raw PCM16 samples, normalized to `f32`.
        /// Doesn't assume a fixed 44-byte header: `afconvert`'s own WAVE output inserts a
        /// `FLLR` filler chunk between `fmt ` and `data` (confirmed by inspecting the fixture
        /// byte-for-byte), so a fixed-offset reader would silently read garbage/zeros.
        fn read_wav_pcm16_mono(path: &Path) -> Vec<f32> {
            let mut bytes = Vec::new();
            std::fs::File::open(path)
                .and_then(|mut f| f.read_to_end(&mut bytes))
                .expect("fixture WAV must be readable");
            assert_eq!(&bytes[0..4], b"RIFF", "not a RIFF file");
            assert_eq!(&bytes[8..12], b"WAVE", "not a WAVE file");
            let mut i = 12usize;
            while i + 8 <= bytes.len() {
                let id = &bytes[i..i + 4];
                let size =
                    u32::from_le_bytes([bytes[i + 4], bytes[i + 5], bytes[i + 6], bytes[i + 7]])
                        as usize;
                let body_start = i + 8;
                if id == b"data" {
                    let body = &bytes[body_start..body_start + size];
                    // Manual index/step (not `chunks_exact`) to avoid depending on whichever
                    // `unwrap`/`as_chunks` idiom the pinned toolchain's clippy currently
                    // prefers for this pattern — CLAUDE.md documents that exact lint
                    // (`chunks_exact_to_as_chunks`) as having broken `main` on a stable bump.
                    let mut out = Vec::with_capacity(body.len() / 2);
                    let mut j = 0;
                    while j + 1 < body.len() {
                        let s = i16::from_le_bytes([body[j], body[j + 1]]);
                        out.push(s as f32 / i16::MAX as f32);
                        j += 2;
                    }
                    return out;
                }
                i = body_start + size + (size % 2); // RIFF chunks are word-aligned
            }
            panic!("no `data` chunk found in {path:?}");
        }

        /// The committed ~5.8 s recorded-speech fixture (macOS `say` + `afconvert`, 16 kHz
        /// mono PCM16, generated once — not synthesized at test time) used by the
        /// text-equivalence test below.
        fn speech_fixture_samples() -> Vec<f32> {
            let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("tests/fixtures/sample_speech_16k_mono.wav");
            read_wav_pcm16_mono(&path)
        }

        /// The committed ~22 s recorded-speech fixture (macOS `say` + `afconvert`, 16 kHz
        /// mono PCM16, generated once), long enough that every timing-test window below is a
        /// genuine PREFIX slice — never a repeat of itself.
        fn speech_long_fixture_samples() -> Vec<f32> {
            let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("tests/fixtures/sample_speech_long_16k_mono.wav");
            read_wav_pcm16_mono(&path)
        }

        /// `target_secs` of REAL, NON-REPEATING speech for the timing tests below: a prefix
        /// slice of the long fixture above.
        ///
        /// CORRECTED (86akcfp3u review): an earlier version of this function built windows by
        /// tiling (`.cycle()`) the SHORT ~5.8 s fixture, reasoning that the defect is purely
        /// in the encoder's pass over a fixed-size context regardless of content. That was
        /// WRONG and materially corrupted this file's own timing evidence: any window past
        /// 5.81 s was the same sentence AGAIN, and whisper.cpp loops on the literal repeat,
        /// burning temperature-fallback retries that have nothing to do with `audio_ctx`. A
        /// performance review (Vera) measured the tiled fixture running 1.4-3.1 s at
        /// 10/12/14 s windows while real non-repeating speech at the SAME windows ran
        /// 360-460 ms — and found the tiled fixture was ALSO fast at 9.8 s and unstable
        /// (1.3-3.0 s) at 9.5 s, proving the cost tracked the REPEAT FRACTION, not the window
        /// length or `audio_ctx`. This is what produced this PR's earlier (wrong) claim of a
        /// "10 s regression" — see `WHISPER_AUDIO_CTX`'s doc comment for the real boundary
        /// (an `audio_ctx / 50` s content-loss envelope — 10.24 s at the then-current 512, 11.52 s
        /// at 576 since 17tnw2b0nkq — not a 10.0 s slowdown).
        ///
        /// Fixed by slicing prefixes of a long (~22 s), never-repeated recording instead of
        /// cycling a short one. Panics rather than silently tiling if a future caller asks
        /// for more than the fixture provides — extend the fixture, do not reintroduce a
        /// repeat.
        fn speech_like_samples(target_secs: u64) -> Vec<f32> {
            let fixture = speech_long_fixture_samples();
            let target_len = (target_secs * 16_000) as usize;
            assert!(
                target_len <= fixture.len(),
                "requested {target_secs}s but the long fixture is only {:.2}s -- extend the \
                 fixture, do not fall back to tiling/cycling it",
                fixture.len() as f64 / 16_000.0
            );
            fixture[..target_len].to_vec()
        }

        /// PRIMARY mutation-verified test (see the PR / handoff for the mutation transcript):
        /// with `set_audio_ctx`/`set_single_segment` in place, an 8 s window decodes well
        /// under the pre-fix flat cost, AFTER a warm-up call establishes the compute-graph
        /// shape (the same one-time cost — 1.3-2.0 s per the ticket — a real session pays
        /// once at startup, not once per decode; measuring the cold first call would
        /// conflate that one-time cost with the per-decode cost this fix actually changes,
        /// and this session confirmed exactly that conflation empirically: a cold single
        /// call measured 791-899 ms here, noisier and closer to the threshold than the
        /// ~360-520 ms steady state this same window measures after a warm-up).
        ///
        /// 8 s (well under the 10 s `max_utterance_samples` ceiling AND the 11.52 s
        /// `audio_ctx` envelope — see `WHISPER_AUDIO_CTX`'s doc comment) is a representative
        /// mid-range window; `capped_audio_ctx_bounds_a_ten_second_decode_at_the_\
        /// max_utterance_ceiling` below covers the ceiling itself. Mutation-verify by
        /// deleting the two `params.set_*` calls in `transcribe` above, re-running this
        /// file's tests (with siblings, not `--exact`), confirming this goes RED, then
        /// restoring them.
        #[test]
        fn capped_audio_ctx_bounds_an_eight_second_decode_off_the_flat_thirty_second_cost() {
            let Some(model_path) = cached_model_path() else {
                eprintln!(
                    "skipping: no cached model at ~/Library/Caches/selahcue/models/{}",
                    WhisperModel::LargeV3Turbo.asset().file_name
                );
                return;
            };
            let _guard = lock_whisper_gpu();
            let mut recognizer = load_test_recognizer(&model_path);
            // 8 s of REAL, NON-REPEATING speech (see `speech_like_samples`) — not silence
            // (trips an unrelated whisper.cpp fallback-retry path) and not tiled/cycled audio
            // (see `speech_like_samples`'s doc comment for why that also corrupts timing).
            let samples = speech_like_samples(8);
            // Warm-up call: pays the one-time compute-graph-build cost so the TIMED call
            // below measures steady-state decode cost (see doc comment).
            let _ = recognizer.transcribe(&samples, 0, 8_000);
            let started = Instant::now();
            let _ = recognizer.transcribe(&samples, 0, 8_000);
            let elapsed = started.elapsed();
            eprintln!("8s window decode (steady state): {elapsed:?}");
            assert!(
                elapsed < Duration::from_millis(700),
                "an 8s window took {elapsed:?} (threshold 700ms); pre-fix (audio_ctx left at \
                 the whisper.cpp default) this measured ~1.05-1.15s flat regardless of window \
                 length (independently reproduced: 1.03-1.15s baseline on this machine) — if \
                 this goes red, audio_ctx has likely regressed to the default"
            );
        }

        /// Proves the "one fixed value, no shape-switching" constraint: once the FIRST call
        /// has paid the one-time compute-graph build cost for `WHISPER_AUDIO_CTX`, EVERY
        /// subsequent call — regardless of how long its window is — stays fast, because the
        /// context shape never changes between calls. If a future change picked `audio_ctx`
        /// per window length, later calls at a new shape would each re-pay the 1.3-2.0s
        /// rebuild and this test would go red.
        ///
        /// Window lengths are drawn from the confirmed-fast range (independently measured on
        /// real, non-repeating speech: 6-9s all land at ~360-460ms at the original
        /// `WHISPER_AUDIO_CTX`=512, 86akcfp3u; see the dedicated ten-second-ceiling test below for
        /// the `max_utterance_samples` boundary, and `WHISPER_AUDIO_CTX`'s doc comment for the real
        /// `audio_ctx / 50` s envelope).
        #[test]
        fn capped_audio_ctx_stays_fast_across_varying_window_lengths_in_one_session() {
            let Some(model_path) = cached_model_path() else {
                eprintln!("skipping: no cached model");
                return;
            };
            let _guard = lock_whisper_gpu();
            let mut recognizer = load_test_recognizer(&model_path);
            let windows_s = [2u64, 6, 9, 7]; // deliberately non-monotonic
                                             // First call pays the one-time graph-build cost — not asserted. Real,
                                             // NON-REPEATING speech throughout (see `speech_like_samples`) — silence trips an
                                             // unrelated whisper.cpp fallback-retry path, and tiled/cycled audio measures the
                                             // repeat, not the window (see that function's doc comment for both).
            let first = speech_like_samples(windows_s[0]);
            let _ = recognizer.transcribe(&first, 0, windows_s[0] * 1000);
            for &secs in &windows_s[1..] {
                let samples = speech_like_samples(secs);
                let started = Instant::now();
                let _ = recognizer.transcribe(&samples, 0, secs * 1000);
                let elapsed = started.elapsed();
                eprintln!("{secs}s window (after the first call): {elapsed:?}");
                assert!(
                    elapsed < Duration::from_millis(700),
                    "a {secs}s window took {elapsed:?} after the context shape was already \
                     established — a fixed audio_ctx should never re-pay the graph-rebuild \
                     cost on a later call of a different length"
                );
            }
        }

        /// A window of EXACTLY 10s — `engine.rs`'s `max_utterance_samples` default, the
        /// longest any utterance (interim or final) ever gets before force-close — meets the
        /// SAME ~700ms bar as every other window. No special allowance.
        ///
        /// CORRECTED (86akcfp3u review): an earlier version of this test claimed a "10s
        /// regression" (measured ~1.4-1.5s, a 2000ms ceiling calibrated to admit it) and
        /// flagged it for performance review. That claim was WRONG — it was an artifact of
        /// `speech_like_samples` tiling a too-short fixture (see that function's doc comment),
        /// not a property of `audio_ctx=512` or of this window length. Independently
        /// re-measured on real, non-repeating speech: 10.0s decodes in ~400ms, same as every
        /// other window, ~2.9x FASTER than the ~1.1-1.15s uncapped baseline. There is no
        /// regression on the final path at 10.0s.
        ///
        /// The real, DIFFERENT boundary this fix has is documented at `WHISPER_AUDIO_CTX`'s
        /// doc comment: `audio_ctx` gives the encoder a hard `audio_ctx / 50` s horizon (11.52 s
        /// at 576 since 17tnw2b0nkq; 10.24 s at the original 512), past which cost jumps ~5x AND
        /// transcription silently stops growing (content loss, not slowness). This test's 10.0s
        /// window sits 1.52 s (13%) under that envelope, which is exactly production's real
        /// margin (`engine.rs`'s force-close), and does not itself probe the envelope — it
        /// confirms production's actual ceiling is fast and safe, nothing more.
        #[test]
        fn capped_audio_ctx_bounds_a_ten_second_decode_at_the_max_utterance_ceiling() {
            let Some(model_path) = cached_model_path() else {
                eprintln!("skipping: no cached model");
                return;
            };
            let _guard = lock_whisper_gpu();
            let mut recognizer = load_test_recognizer(&model_path);
            // 10 s of REAL, NON-REPEATING speech — see `speech_like_samples`'s doc comment;
            // this is the exact window whose tiled-audio measurement produced this PR's
            // earlier, incorrect "10s regression" claim.
            let samples = speech_like_samples(10);
            // Warm-up call (see the primary test's doc comment for why): isolates
            // steady-state decode cost from the one-time graph-build cost.
            let _ = recognizer.transcribe(&samples, 0, 10_000);
            let started = Instant::now();
            let _ = recognizer.transcribe(&samples, 0, 10_000);
            let elapsed = started.elapsed();
            eprintln!("10s window decode (max_utterance ceiling, steady state): {elapsed:?}");
            assert!(
                elapsed < Duration::from_millis(700),
                "a 10s window (engine.rs's max_utterance_samples ceiling) took {elapsed:?} \
                 (threshold 700ms, the SAME bar as every other window); pre-fix this measured \
                 ~1.05-1.15s flat — if this goes red, audio_ctx has likely regressed to the \
                 default, NOT the already-corrected tiled-fixture artifact this test used to \
                 (wrongly) admit"
            );
        }

        /// Discharges the ticket's "if you cap the final too, prove the text is unchanged"
        /// requirement: on a real recorded-speech fixture (>= 4s, the window range the
        /// investigation validated), the capped decode's text must match a baseline decode
        /// built with the EXACT pre-fix `FullParams` (no `set_audio_ctx`/`set_single_segment`
        /// call at all) run against the same loaded model.
        #[test]
        fn capping_does_not_change_recognized_text_for_a_real_speech_fixture() {
            let Some(model_path) = cached_model_path() else {
                eprintln!("skipping: no cached model");
                return;
            };
            let _guard = lock_whisper_gpu();
            let samples = speech_fixture_samples();
            let duration_s = samples.len() as f64 / 16_000.0;
            assert!(
                duration_s >= 4.0,
                "fixture must be >= 4s (the validated window range), got {duration_s:.2}s"
            );

            let mut recognizer = load_test_recognizer(&model_path);
            let capped: String = recognizer
                .transcribe(&samples, 0, (duration_s * 1000.0) as u64)
                .into_iter()
                .map(|s| s.text)
                .collect::<Vec<_>>()
                .join(" ");

            // Pre-fix baseline: the exact FullParams this recognizer built before this change,
            // sharing the SAME loaded model (so a text difference can only come from the two
            // new `set_*` calls, not from a different model/context instance).
            let mut state = recognizer
                .context()
                .create_state()
                .expect("state creation must succeed");
            let mut baseline_params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
            baseline_params.set_n_threads(production_selection().threads.max(1) as i32);
            baseline_params.set_translate(false);
            baseline_params.set_print_special(false);
            baseline_params.set_print_progress(false);
            baseline_params.set_print_realtime(false);
            baseline_params.set_print_timestamps(false);
            state
                .full(baseline_params, &samples)
                .expect("baseline decode must succeed");
            let n = state.full_n_segments();
            let mut baseline = String::new();
            for i in 0..n {
                if let Some(Ok(text)) = state.get_segment(i).map(|seg| seg.to_str()) {
                    if !baseline.is_empty() {
                        baseline.push(' ');
                    }
                    baseline.push_str(text.trim());
                }
            }

            eprintln!("capped:   {:?}", capped.trim());
            eprintln!("baseline: {:?}", baseline.trim());
            assert_eq!(
                capped.trim(),
                baseline.trim(),
                "capping audio_ctx/single_segment changed the recognized text vs. the pre-fix \
                 baseline on a >= 4s fixture — the final's accuracy path must be unaffected"
            );
        }

        /// 86akcgmuh REPRODUCTION FIXTURES: continuous speech that the REAL `SttEngine`
        /// force-closes at exactly 10.000 s, mid-word. Each file is
        /// `[300 ms silence][the 10.000 s window][up to 2 s of the same speaker continuing][600
        /// ms silence]`, 16 kHz mono PCM16, and the 10 s window is one the production engine
        /// (EnergyVad, default `EngineConfig`) itself force-closed when it heard the source
        /// recording — the 300 ms lead-in is a whole number of 20 ms VAD frames, so the replayed
        /// fixture force-closes on exactly the same audio.
        ///
        /// Each pair is (fixture file, an anchor phrase the correct force-closed final contains).
        /// Observed on `main` (large-v3-turbo, Metal, `WHISPER_AUDIO_CTX` = 512, 86akcgmuh spike):
        /// - A: "...Ask them how they are really doing, and then wait long and then wait long and
        ///   then wait" (the uncapped reference ends "...and then wait long")
        /// - B: "...Do not just sing the words on the screen. Look at the one the words on the
        ///   screen. Look at the one the words on the" (reference: "...Look at the one the words")
        ///
        /// LICENSING — READ BEFORE MERGING: both files are macOS `say`-derived (voices "Karen" and
        /// "Daniel"; original text written for the spike, not copyrighted material). They inherit
        /// the replacement obligation tracked on 86akcmmc1 exactly like the two existing
        /// `say`-derived fixtures. Replacing them means re-finding a window that loops on real
        /// speech — the harness and method are on 86akcgmuh.
        const FORCE_CLOSE_LOOP_FIXTURES: [(&str, &str); 2] = [
            (
                "tests/fixtures/force_close_loop_a_16k_mono.wav",
                "ask them how they are really doing and then wait",
            ),
            (
                "tests/fixtures/force_close_loop_b_16k_mono.wav",
                "do not just sing the words on the screen look at the one",
            ),
        ];

        /// 86akcgmuh / 17tnw2b0nkq — the defect, end to end: a final the engine FORCE-CLOSED at
        /// 10 s, mid-word, must not repeat a span of itself back-to-back. Drives the real
        /// `SttEngine` (production VAD and default `EngineConfig`, so the 10 s force-close is the
        /// production path) over each fixture with the real `WhisperRecognizer`.
        ///
        /// Checks TWO layers, because the fix has two independent parts:
        /// 1. The raw decode — `WhisperRecognizer::transcribe` on exactly the samples the engine
        ///    force-closed, before any engine post-processing — must not loop. This is what
        ///    `WHISPER_AUDIO_CTX` = 576 fixes (both fixtures loop at 512, 86akcgmuh), and the
        ///    only assertion here that reddens if the constant is reverted: the engine's trim
        ///    (part 2 of the fix) would otherwise hide a reverted constant on these fixtures.
        /// 2. The engine's emitted finals must not loop — the end-to-end user-visible outcome,
        ///    whatever combination of levers delivers it.
        ///
        /// The trim itself is guarded separately, without a model, by
        /// `engine::tests::the_trailing_repeat_trim_applies_only_to_force_closed_finals`.
        ///
        /// Positive controls stop this passing vacuously: (1) the first final must span >= 9 s,
        /// i.e. the fixture still reaches the force-close path rather than closing early on a
        /// pause; (2) both the raw decode and the final must still contain the fixture's anchor
        /// phrase, so an empty or truncated transcript cannot read as "no loop". The loop detector
        /// is `repetition::back_to_back_repeat`, whose own positive and negative controls run in
        /// the default build.
        ///
        /// Mutation check (17tnw2b0nkq): with `WHISPER_AUDIO_CTX` (and its engine mirror) set back
        /// to 512 this goes RED on the raw-decode layer. Runs only when the model is cached, like
        /// every test in this module; no CI job compiles this module at all (86ak5rjh7).
        #[test]
        fn a_force_closed_final_ending_mid_word_does_not_repeat_itself() {
            use crate::audio::AudioChunk;
            use crate::engine::{EngineConfig, SttEngine};
            use crate::guard::FeedbackGuard;
            use crate::repetition::{back_to_back_repeat, normalized_words};
            use crate::vad::EnergyVad;
            use selahcue_core::transcript::TranscriptProvider;

            let Some(model_path) = cached_model_path() else {
                eprintln!("skipping: no cached model");
                return;
            };
            let _guard = lock_whisper_gpu();
            let shared = load_test_recognizer(&model_path).context();
            let mut loops = Vec::new();
            for (file, anchor) in FORCE_CLOSE_LOOP_FIXTURES {
                let audio =
                    read_wav_pcm16_mono(&PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(file));
                let (mut engine, mut provider) = SttEngine::build(
                    EngineConfig::default(),
                    Box::new(EnergyVad::new()),
                    Box::new(WhisperRecognizer::from_context(
                        Arc::clone(&shared),
                        &production_selection(),
                    )),
                    FeedbackGuard::new(),
                );
                engine.process(&AudioChunk::new(audio.clone(), 16_000, 1));
                engine.flush();
                let finals: Vec<_> = provider.poll().into_iter().filter(|s| s.is_final).collect();
                for s in &finals {
                    eprintln!("{file} [{}-{} ms]: {:?}", s.start_ms, s.end_ms, s.text);
                }
                let first = finals
                    .first()
                    .unwrap_or_else(|| panic!("{file}: the engine produced no final at all"));
                assert!(
                    first.end_ms - first.start_ms >= 9_000,
                    "{file}: the first final spans only {} ms — the fixture no longer reaches the \
                     10 s force-close path, so this test would no longer exercise 86akcgmuh",
                    first.end_ms - first.start_ms
                );
                assert!(
                    normalized_words(&first.text).join(" ").contains(anchor),
                    "{file}: the force-closed final lost its anchor phrase {anchor:?} — a \
                     truncated or empty final must not pass as 'no loop'. Got {:?}",
                    first.text
                );

                // Layer 1: the raw decode of exactly the samples the engine force-closed (the
                // transcript clock is 16 samples per ms), with no engine post-processing.
                let window = &audio[(first.start_ms * 16) as usize..(first.end_ms * 16) as usize];
                let raw =
                    WhisperRecognizer::from_context(Arc::clone(&shared), &production_selection())
                        .transcribe(window, first.start_ms, first.end_ms)
                        .into_iter()
                        .map(|s| s.text)
                        .collect::<Vec<_>>()
                        .join(" ");
                eprintln!("{file} raw decode: {raw:?}");
                assert!(
                    normalized_words(&raw).join(" ").contains(anchor),
                    "{file}: the raw decode lost its anchor phrase {anchor:?}. Got {raw:?}"
                );
                if let Some((span, times)) = back_to_back_repeat(&raw) {
                    loops.push(format!("{file} (raw decode): {span:?} x{times} in {raw:?}"));
                }

                // Layer 2: every final the engine emitted.
                for s in &finals {
                    if let Some((span, times)) = back_to_back_repeat(&s.text) {
                        loops.push(format!("{file}: {span:?} x{times} in {:?}", s.text));
                    }
                }
            }
            assert!(
                loops.is_empty(),
                "86akcgmuh: force-closed final(s) repeat themselves back-to-back:\n{}",
                loops.join("\n")
            );
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
