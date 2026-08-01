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

    /// Select the largest whisper variant that fits the ≤2 GB budget and is appropriate for
    /// the host. On an accelerated backend or a well-provisioned CPU (≥4 threads) we choose
    /// large-v3 Turbo (real-time capable, FR-101); leaner hosts step down. Thread count for
    /// decoding is capped so we never oversubscribe.
    pub fn select_model(&self) -> ModelSelection {
        let model = if self.backend != Backend::Cpu || self.threads >= 4 {
            WhisperModel::LargeV3Turbo
        } else if self.threads >= 2 {
            WhisperModel::Small
        } else {
            WhisperModel::Base
        };
        // Leave one core for capture/host; clamp to a sane decoding range.
        let threads = self.threads.saturating_sub(1).clamp(1, 8);
        ModelSelection {
            model,
            threads,
            backend: self.backend,
        }
    }
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
}
