//! Model integrity (FR-156 / ADR-0012) + hardware probe / model selection (FR-101).
//!
//! Before a whisper model is loaded it is verified against a pinned SHA-256 (ADR-0012
//! extends the app's signing/verification discipline to local AI model files): a mismatch
//! refuses to load. The file is hashed in bounded chunks — a multi-hundred-MB model never
//! sits in memory to be hashed. The model *delivery/update* path is deferred (ADR-0012 →
//! Stage-13); this crate only verifies a model already present at a path.
//!
//! [`HardwareProbe`] inspects the host and selects a whisper variant + thread count within
//! the ≤2 GB resident budget (ADR-0010).

use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;

use sha2::{Digest, Sha256};

/// Bytes read per hash chunk. Bounds the memory used while verifying a large model file.
const HASH_CHUNK_BYTES: usize = 64 * 1024;

/// Why a model failed to verify/load.
#[derive(Debug)]
pub enum ModelError {
    /// The file could not be opened/read.
    Io(std::io::Error),
    /// The pinned expected hash is not valid lowercase hex SHA-256 (64 hex chars).
    BadExpectedHash,
    /// The file's SHA-256 did not match the pinned expected hash.
    Mismatch { expected: String, actual: String },
}

impl std::fmt::Display for ModelError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ModelError::Io(e) => write!(f, "model I/O error: {e}"),
            ModelError::BadExpectedHash => {
                write!(f, "pinned model hash is not a 64-char hex SHA-256")
            }
            ModelError::Mismatch { expected, actual } => write!(
                f,
                "model integrity check failed: expected {expected}, got {actual}"
            ),
        }
    }
}

impl std::error::Error for ModelError {}

/// Compute the lowercase-hex SHA-256 of the file at `path`, reading in bounded chunks.
pub fn sha256_file(path: &Path) -> Result<String, ModelError> {
    let file = File::open(path).map_err(ModelError::Io)?;
    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buf = [0u8; HASH_CHUNK_BYTES];
    loop {
        let n = reader.read(&mut buf).map_err(ModelError::Io)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex_lower(&hasher.finalize()))
}

/// Verify that the model file at `path` matches `expected_sha256` (64-char lowercase hex).
/// Returns the verified digest on success; refuses (never loads) on any mismatch.
pub fn verify_model(path: &Path, expected_sha256: &str) -> Result<String, ModelError> {
    let expected = expected_sha256.trim().to_ascii_lowercase();
    if expected.len() != 64 || !expected.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(ModelError::BadExpectedHash);
    }
    let actual = sha256_file(path)?;
    if actual == expected {
        Ok(actual)
    } else {
        Err(ModelError::Mismatch { expected, actual })
    }
}

/// Lowercase-hex encode a byte slice (no external hex dependency).
fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}

/// The acceleration backend the host offers whisper.cpp.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    /// Apple Metal (macOS/iOS).
    Metal,
    /// NVIDIA CUDA.
    Cuda,
    /// Vulkan compute.
    Vulkan,
    /// CPU only.
    Cpu,
}

/// A whisper model variant, with its approximate resident footprint.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WhisperModel {
    LargeV3Turbo,
    Medium,
    Small,
    Base,
}

impl WhisperModel {
    /// A stable identifier used in the provider/recognizer label (honest disclosure).
    pub fn as_str(self) -> &'static str {
        match self {
            WhisperModel::LargeV3Turbo => "large-v3-turbo",
            WhisperModel::Medium => "medium",
            WhisperModel::Small => "small",
            WhisperModel::Base => "base",
        }
    }

    /// Approximate resident bytes (quantized) — used against the ≤2 GB budget.
    pub fn approx_resident_bytes(self) -> u64 {
        match self {
            WhisperModel::LargeV3Turbo => 1_600 * 1024 * 1024, // ~1.6 GB
            WhisperModel::Medium => 1_500 * 1024 * 1024,
            WhisperModel::Small => 500 * 1024 * 1024,
            WhisperModel::Base => 150 * 1024 * 1024,
        }
    }

    /// The pinned downloadable asset for this variant — the bundled public-domain-ish
    /// whisper.cpp `ggml` weights from the upstream `ggerganov/whisper.cpp` model repo. The
    /// SHA-256 is each file's published Git-LFS digest — the **same** digest
    /// [`verify_model`] recomputes after download, so a corrupted or substituted file is
    /// rejected (FR-156 / ADR-0012). Full signature/HSM custody is the Stage-13 hardening;
    /// this is the hash-pin baseline. Values captured 2026-08 from Hugging Face.
    pub fn asset(self) -> ModelAsset {
        // whisper.cpp ggml weights are MIT-licensed (OpenAI Whisper) and served from the
        // upstream model repo. The download URL and the pinned digest move together.
        const BASE_URL: &str = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/";
        let (file_name, sha256, size_bytes) = match self {
            WhisperModel::LargeV3Turbo => (
                "ggml-large-v3-turbo.bin",
                "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
                1_624_555_275,
            ),
            WhisperModel::Medium => (
                "ggml-medium.bin",
                "6c14d5adee5f86394037b4e4e8b59f1673b6cee10e3cf0b11bbdbee79c156208",
                1_533_763_059,
            ),
            WhisperModel::Small => (
                "ggml-small.bin",
                "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
                487_601_967,
            ),
            WhisperModel::Base => (
                "ggml-base.bin",
                "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
                147_951_465,
            ),
        };
        ModelAsset {
            model: self,
            file_name,
            url: BASE_URL,
            sha256,
            size_bytes,
        }
    }
}

/// A pinned, downloadable whisper model file: its name, the source URL prefix, the pinned
/// SHA-256 the downloaded bytes must match, and the expected size. This is the supply-chain
/// pin (ADR-0012): the URL and digest travel together and a mismatch refuses to load.
#[derive(Debug, Clone, Copy)]
pub struct ModelAsset {
    pub model: WhisperModel,
    pub file_name: &'static str,
    /// URL prefix; the full download URL is `url` + `file_name`.
    pub url: &'static str,
    /// Lowercase-hex SHA-256 the downloaded file must match ([`verify_model`]).
    pub sha256: &'static str,
    pub size_bytes: u64,
}

impl ModelAsset {
    /// The full download URL (`url` + `file_name`).
    pub fn download_url(&self) -> String {
        format!("{}{}", self.url, self.file_name)
    }
}

/// The upper bound on resident model memory (ADR-0010): a model must fit within ~2 GB.
pub const MAX_MODEL_RESIDENT_BYTES: u64 = 2 * 1024 * 1024 * 1024;

/// The chosen model + thread count for this host.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ModelSelection {
    pub model: WhisperModel,
    pub threads: usize,
    pub backend: Backend,
}

/// A best-effort read of the host's STT-relevant capabilities.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct HardwareProbe {
    pub backend: Backend,
    /// Usable parallelism (CPU threads), always at least 1.
    pub threads: usize,
}

impl HardwareProbe {
    /// Detect the host's backend + parallelism. Deterministic per machine; the acceleration
    /// backend is chosen from the target OS as a safe default (a precise runtime GPU probe
    /// is a later refinement). Never panics.
    pub fn detect() -> Self {
        let threads = std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
            .max(1);
        HardwareProbe {
            backend: default_backend(),
            threads,
        }
    }

    /// Select a whisper variant appropriate for the host, **enforcing** the ≤2 GB resident
    /// budget (FR-101). On an accelerated backend or a well-provisioned CPU (≥4 threads) we
    /// prefer large-v3 Turbo (real-time capable); leaner hosts step down. The preferred
    /// model is then filtered through [`MAX_MODEL_RESIDENT_BYTES`] as defence in depth, so
    /// the budget is enforced by the selector itself — not merely asserted by a test — and a
    /// future footprint bump can never silently ship an over-budget model. Thread count for
    /// decoding is capped so we never oversubscribe.
    pub fn select_model(&self) -> ModelSelection {
        // Prefer the large real-time model ONLY when a GPU backend is actually compiled into this
        // build (`metal`/`cuda`/`vulkan`). The OS-derived `backend` label does not accelerate
        // decoding on its own — a "Metal" label with no `metal` feature still runs on the CPU,
        // where the 1.6 GB model is far slower than real time. A CPU-only build therefore steps
        // down to a small model for live latency (base on a very lean host).
        let preferred = if gpu_acceleration_compiled() {
            WhisperModel::LargeV3Turbo
        } else if self.threads >= 2 {
            WhisperModel::Small
        } else {
            WhisperModel::Base
        };
        // Step down (Turbo → Medium → Small → Base) until the resident budget is satisfied.
        let model = [
            preferred,
            WhisperModel::Medium,
            WhisperModel::Small,
            WhisperModel::Base,
        ]
        .into_iter()
        .find(|m| m.approx_resident_bytes() <= MAX_MODEL_RESIDENT_BYTES)
        .unwrap_or(WhisperModel::Base);
        // Leave one core for capture/host; clamp to a sane decoding range.
        let threads = self.threads.saturating_sub(1).clamp(1, 8);
        ModelSelection {
            model,
            threads,
            backend: self.backend,
        }
    }
}

/// Whether a whisper.cpp GPU backend is compiled into THIS build (Cargo features `metal` /
/// `cuda` / `vulkan`). [`HardwareProbe::select_model`] prefers the large real-time model only
/// when this is true: the OS backend label alone does not accelerate decoding, so a CPU-only
/// build must step down to a small model to keep live transcription near real time.
pub const fn gpu_acceleration_compiled() -> bool {
    cfg!(any(feature = "metal", feature = "cuda", feature = "vulkan"))
}

/// The default acceleration backend for the build target (a conservative heuristic).
fn default_backend() -> Backend {
    #[cfg(target_os = "macos")]
    {
        Backend::Metal
    }
    #[cfg(not(target_os = "macos"))]
    {
        Backend::Cpu
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    /// A unique temp file path (no external tempfile dep; PID + a counter avoid collisions).
    fn temp_path(tag: &str) -> std::path::PathBuf {
        use std::sync::atomic::{AtomicU32, Ordering};
        static SEQ: AtomicU32 = AtomicU32::new(0);
        let n = SEQ.fetch_add(1, Ordering::Relaxed);
        std::env::temp_dir().join(format!(
            "selahcue-stt-{}-{}-{}.bin",
            tag,
            std::process::id(),
            n
        ))
    }

    fn write_file(path: &Path, bytes: &[u8]) {
        let mut f = File::create(path).expect("create temp");
        f.write_all(bytes).expect("write temp");
    }

    #[test]
    fn sha256_of_known_content_is_correct() {
        // SHA-256("abc") — the canonical NIST test vector.
        let p = temp_path("abc");
        write_file(&p, b"abc");
        let got = sha256_file(&p).expect("hash");
        assert_eq!(
            got,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        let _ = std::fs::remove_file(&p);
    }

    #[test]
    fn matching_hash_verifies() {
        let p = temp_path("match");
        write_file(&p, b"model-bytes");
        let digest = sha256_file(&p).expect("hash");
        assert!(verify_model(&p, &digest).is_ok());
        // Case-insensitive on the expected hash.
        assert!(verify_model(&p, &digest.to_uppercase()).is_ok());
        let _ = std::fs::remove_file(&p);
    }

    #[test]
    fn mismatched_hash_refuses() {
        let p = temp_path("mismatch");
        write_file(&p, b"model-bytes");
        let wrong = "0".repeat(64);
        assert!(matches!(
            verify_model(&p, &wrong),
            Err(ModelError::Mismatch { .. })
        ));
        let _ = std::fs::remove_file(&p);
    }

    #[test]
    fn bad_expected_hash_is_rejected() {
        let p = temp_path("badhash");
        write_file(&p, b"x");
        assert!(matches!(
            verify_model(&p, "not-hex"),
            Err(ModelError::BadExpectedHash)
        ));
        let _ = std::fs::remove_file(&p);
    }

    #[test]
    fn missing_file_is_io_error() {
        let p = temp_path("missing");
        assert!(matches!(
            verify_model(&p, &"a".repeat(64)),
            Err(ModelError::Io(_))
        ));
    }

    #[test]
    fn probe_selects_within_budget() {
        let probe = HardwareProbe::detect();
        assert!(probe.threads >= 1);
        let sel = probe.select_model();
        assert!(sel.threads >= 1);
        assert!(
            sel.model.approx_resident_bytes() <= MAX_MODEL_RESIDENT_BYTES,
            "selected {} exceeds the 2 GB budget",
            sel.model.as_str()
        );
    }

    #[test]
    fn low_end_cpu_steps_down_to_a_smaller_model() {
        let probe = HardwareProbe {
            backend: Backend::Cpu,
            threads: 1,
        };
        assert_eq!(probe.select_model().model, WhisperModel::Base);
    }

    #[test]
    fn cpu_only_build_uses_a_small_model_not_the_large_one() {
        // The core perf fix: without a compiled GPU backend, even a many-core host with a
        // "Metal" OS label must NOT pick the 1.6 GB large model — on the CPU it decodes far
        // slower than real time. Small is the live-latency choice; base only on a lean host.
        assert!(
            !gpu_acceleration_compiled(),
            "the default test build has no GPU backend feature"
        );
        let beefy = HardwareProbe {
            backend: Backend::Metal,
            threads: 8,
        };
        assert_eq!(
            beefy.select_model().model,
            WhisperModel::Small,
            "a CPU-only build must step down from large-v3-turbo to small"
        );
    }

    #[cfg(any(feature = "metal", feature = "cuda", feature = "vulkan"))]
    #[test]
    fn gpu_build_prefers_the_large_real_time_model() {
        // With a GPU backend compiled in, the large real-time-capable model is preferred (it
        // runs on the GPU, not the CPU). Only exercised in a `--features metal` (etc.) build.
        assert!(gpu_acceleration_compiled());
        let probe = HardwareProbe {
            backend: Backend::Metal,
            threads: 8,
        };
        assert_eq!(probe.select_model().model, WhisperModel::LargeV3Turbo);
    }

    #[test]
    fn every_model_variant_has_a_well_formed_pinned_asset() {
        // The download manifest must be a valid supply-chain pin for every variant: a
        // 64-char lowercase-hex SHA-256 (the digest verify_model checks), an https URL, a
        // `.bin` file name, and a plausible size. A malformed pin is a build defect.
        for m in [
            WhisperModel::LargeV3Turbo,
            WhisperModel::Medium,
            WhisperModel::Small,
            WhisperModel::Base,
        ] {
            let a = m.asset();
            assert_eq!(a.model, m);
            assert_eq!(a.sha256.len(), 64, "{} sha256 not 64 hex", a.file_name);
            assert!(
                a.sha256
                    .bytes()
                    .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()),
                "{} sha256 must be lowercase hex",
                a.file_name
            );
            assert!(a.file_name.ends_with(".bin"));
            let url = a.download_url();
            assert!(url.starts_with("https://"), "{url} is not https");
            assert!(url.ends_with(a.file_name));
            assert!(
                a.size_bytes > 1_000_000,
                "{} size implausibly small",
                a.file_name
            );
        }
    }
}
