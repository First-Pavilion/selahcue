//! One signed manifest per install, re-verified whenever reopened.

use crate::verified::verify_with_envelope;
use crate::{
    decide_cache_replacement, verify_entitlement, CacheDecision, EntitlementVerificationError,
    TrustedKeys, VerifiedEntitlement, MAX_ENTITLEMENT_ENVELOPE_BYTES,
};
use std::fmt;
use std::fs::{self, File, Metadata, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

const CACHE_FILE: &str = "entitlement-cache.json";
const LOCK_FILE: &str = "entitlement-cache.lock";
const STAGING_FILE: &str = "entitlement-cache.stage";

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum EntitlementCacheError {
    Verification(EntitlementVerificationError),
    UnsafeFile,
    Io(io::ErrorKind),
}

impl fmt::Display for EntitlementCacheError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Verification(error) => error.fmt(f),
            Self::UnsafeFile => f.write_str("unsafe entitlement cache path or file type"),
            Self::Io(kind) => write!(f, "entitlement cache I/O failed ({kind:?})"),
        }
    }
}

impl std::error::Error for EntitlementCacheError {}

impl From<io::Error> for EntitlementCacheError {
    fn from(error: io::Error) -> Self {
        Self::Io(error.kind())
    }
}

impl From<EntitlementVerificationError> for EntitlementCacheError {
    fn from(error: EntitlementVerificationError) -> Self {
        Self::Verification(error)
    }
}

/// An install's cache in a caller-provided, existing app-owned data directory.
/// Neither the filename nor the lock is derived from the device, response, or credentials.
pub struct EntitlementCache {
    directory: PathBuf,
}

impl EntitlementCache {
    pub fn new(app_data_dir: impl Into<PathBuf>) -> Self {
        Self {
            directory: app_data_dir.into(),
        }
    }

    pub fn path(&self) -> PathBuf {
        self.directory.join(CACHE_FILE)
    }

    /// Revalidate the stored signature and device binding. A missing file is normal.
    pub fn load(
        &self,
        keys: &TrustedKeys,
        device_public_id: &str,
        device_fingerprint: &str,
    ) -> Result<Option<VerifiedEntitlement>, EntitlementCacheError> {
        self.check_directory()?;
        let Some(file) = open_regular(&self.path(), false)? else {
            return Ok(None);
        };
        let max = MAX_ENTITLEMENT_ENVELOPE_BYTES as u64;
        if file.metadata()?.len() > max {
            return Err(EntitlementVerificationError::Oversized.into());
        }
        let mut body = Vec::new();
        file.take(max + 1).read_to_end(&mut body)?;
        verify_entitlement(&body, keys, device_public_id, device_fingerprint)
            .map(Some)
            .map_err(Into::into)
    }

    /// Verify the candidate, serialize the compare-and-replace across handles, and publish
    /// only after the complete new envelope has been written and synced. An unreadable
    /// or unsafe destination is refused. A regular but unverifiable file can be recovered
    /// by a newly verified envelope for this device.
    pub fn replace(
        &self,
        body: &[u8],
        keys: &TrustedKeys,
        device_public_id: &str,
        device_fingerprint: &str,
    ) -> Result<CacheDecision, EntitlementCacheError> {
        let (envelope, incoming) =
            verify_with_envelope(body, keys, device_public_id, device_fingerprint)?;
        self.check_directory()?;

        // Keep the lock inode across replacements (and releases) so competing callers
        // compare and publish under the same lock, even when the envelope inode changes.
        let lock = open_regular(&self.directory.join(LOCK_FILE), true)?
            .ok_or(EntitlementCacheError::UnsafeFile)?;
        lock.lock()?;
        let cached = match self.load(keys, device_public_id, device_fingerprint) {
            Ok(cached) => cached,
            Err(EntitlementCacheError::Verification(_)) => None,
            Err(other) => return Err(other),
        };
        let decision = decide_cache_replacement(
            cached.as_ref().map(VerifiedEntitlement::facts),
            incoming.facts(),
        );
        if decision == CacheDecision::Replace {
            // Serialize only the five envelope fields, retaining the exact signed string.
            // In particular, unsigned HTTP metadata never makes it to disk.
            let stored = serde_json::to_vec(&envelope)
                .map_err(|_| EntitlementVerificationError::MalformedEnvelope)?;
            if stored.len() > MAX_ENTITLEMENT_ENVELOPE_BYTES {
                return Err(EntitlementVerificationError::Oversized.into());
            }
            publish(&self.directory, &self.path(), &stored)?;
        }
        Ok(decision)
    }

    fn check_directory(&self) -> Result<(), EntitlementCacheError> {
        let metadata = fs::symlink_metadata(&self.directory)?;
        if !metadata.is_dir() || is_link_or_device(&metadata) {
            return Err(EntitlementCacheError::UnsafeFile);
        }
        Ok(())
    }
}

// The caller holds the cache lock. A fixed staging name bounds interrupted writes
// to one file, and create_new never opens a planted link or truncates another inode.
fn publish(directory: &Path, destination: &Path, body: &[u8]) -> Result<(), EntitlementCacheError> {
    let staging = directory.join(STAGING_FILE);
    match fs::symlink_metadata(&staging) {
        Ok(metadata) if is_regular(&metadata) => fs::remove_file(&staging)?,
        Ok(_) => return Err(EntitlementCacheError::UnsafeFile),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }

    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options.open(&staging)?;
    let written = file.write_all(body).and_then(|()| file.sync_all());
    drop(file);
    let committed = written.and_then(|()| fs::rename(&staging, destination));
    if committed.is_err() {
        // Preserve the original error. A leftover can be reclaimed on the next write.
        let _ = fs::remove_file(&staging);
    }
    committed.map_err(Into::into)
}

fn is_link_or_device(metadata: &Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        use windows_sys::Win32::Storage::FileSystem::{
            FILE_ATTRIBUTE_DEVICE, FILE_ATTRIBUTE_REPARSE_POINT,
        };

        metadata.file_attributes() & (FILE_ATTRIBUTE_DEVICE | FILE_ATTRIBUTE_REPARSE_POINT) != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

fn is_regular(metadata: &Metadata) -> bool {
    metadata.is_file() && !is_link_or_device(metadata)
}

fn open_regular(path: &Path, lock_file: bool) -> Result<Option<File>, EntitlementCacheError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if !is_regular(&metadata) => return Err(EntitlementCacheError::UnsafeFile),
        Ok(_) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(error.into()),
    }

    let mut options = OpenOptions::new();
    options.read(true);
    if lock_file {
        options.write(true).create(true);
    }

    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        // Refuse a symlink swapped in after observation, or a FIFO without blocking.
        options
            .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
            .mode(0o600);
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        use windows_sys::Win32::Storage::FileSystem::FILE_FLAG_OPEN_REPARSE_POINT;

        options.custom_flags(FILE_FLAG_OPEN_REPARSE_POINT);
    }

    match options.open(path) {
        Ok(file) if is_regular(&file.metadata()?) => Ok(Some(file)),
        Ok(_) => Err(EntitlementCacheError::UnsafeFile),
        Err(error) if !lock_file && error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn failed_rename_removes_staging_and_preserves_destination() -> io::Result<()> {
        let directory = tempfile::tempdir()?;
        let destination = directory.path().join(CACHE_FILE);
        fs::create_dir(&destination)?;
        fs::write(destination.join("marker"), b"keep")?;

        assert!(matches!(
            publish(directory.path(), &destination, b"new cache"),
            Err(EntitlementCacheError::Io(_))
        ));
        assert_eq!(fs::read(destination.join("marker"))?, b"keep");
        assert!(!directory.path().join(STAGING_FILE).exists());
        Ok(())
    }
}
