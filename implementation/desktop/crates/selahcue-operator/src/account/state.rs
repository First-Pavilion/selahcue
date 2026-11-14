//! Local install metadata. Call persistence methods on the account worker.
use serde::{Deserialize, Serialize};
use std::{
    fmt,
    fs::{self, File, Metadata, OpenOptions},
    io::{self, Read, Write},
    path::{Component, Path, PathBuf},
};

use selahcue_licensing::{DeviceIdentity, IdempotencyKey};

const SCHEMA_VERSION: u32 = 1;
const METADATA_FILE: &str = "account-metadata.json";
const LOCK_FILE: &str = "account-metadata.lock";
const STAGING_FILE: &str = "account-metadata.stage";
const MAX_METADATA_BYTES: usize = 16 * 1024;

/// One fresh observation from native device custody. Only a successful
/// absence check permits identity creation. An error means custody is unknown.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CredentialPresence {
    Missing,
    Present,
    Unavailable,
}

impl CredentialPresence {
    pub(crate) fn from_check<E>(check: Result<bool, E>) -> Self {
        match check {
            Ok(false) => Self::Missing,
            Ok(true) => Self::Present,
            Err(_) => Self::Unavailable,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum AccountStorageError {
    IdentityRecoveryRequired,
    CredentialPresenceUnavailable,
    UnsafePath,
    Oversize,
    Malformed,
    Io(io::ErrorKind),
    Changed,
    InvalidIdentity,
    PendingActivationPath,
    EntropyUnavailable,
}

impl fmt::Display for AccountStorageError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::IdentityRecoveryRequired => "account device identity recovery required",
            Self::CredentialPresenceUnavailable => "account device credential presence unavailable",
            Self::UnsafePath => "unsafe account metadata path",
            Self::Oversize => "account metadata too large",
            Self::Malformed => "invalid account metadata",
            Self::Io(_) => "account metadata I/O failed",
            Self::Changed => "account metadata changed",
            Self::InvalidIdentity => "invalid account device identity",
            Self::PendingActivationPath => "another activation path is pending",
            Self::EntropyUnavailable => "account identity randomness unavailable",
        };
        f.write_str(message)
    }
}

impl std::error::Error for AccountStorageError {}

impl From<io::Error> for AccountStorageError {
    fn from(error: io::Error) -> Self {
        Self::Io(error.kind())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct AccountMetadata {
    schema_version: u32,
    revision: u64,
    install_fingerprint: String,
    platform: String,
    app_version: String,
    display_name: String,
    pub(crate) activated_public_id: Option<String>,
    pub(crate) skipped_setup: bool,
    pending_activation: Option<PendingActivation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PendingActivation {
    path: ActivationPath,
    idempotency_key: String,
    identity: InstallIdentity,
}

impl PendingActivation {
    pub(crate) fn path(&self) -> ActivationPath {
        self.path
    }

    pub(crate) fn device_identity(&self) -> Result<DeviceIdentity, AccountStorageError> {
        self.identity.device_identity()
    }

    pub(crate) fn retry_key(&self) -> Result<IdempotencyKey, AccountStorageError> {
        IdempotencyKey::new(&self.idempotency_key).map_err(|_| AccountStorageError::Malformed)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum ActivationPath {
    AccountSession,
    EnrollmentKey,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct InstallIdentity {
    install_fingerprint: String,
    platform: String,
    app_version: String,
    display_name: String,
}

impl InstallIdentity {
    fn device_identity(&self) -> Result<DeviceIdentity, AccountStorageError> {
        let normalized = DeviceIdentity::new(
            &self.install_fingerprint,
            &self.platform,
            &self.app_version,
            &self.display_name,
        )
        .map_err(|_| AccountStorageError::Malformed)?;
        if !is_random_id(&self.install_fingerprint)
            || normalized.platform != self.platform
            || normalized.app_version != self.app_version
            || normalized.display_name != self.display_name
        {
            return Err(AccountStorageError::Malformed);
        }
        Ok(normalized)
    }
}

impl AccountMetadata {
    pub(crate) fn fingerprint(&self) -> &str {
        &self.install_fingerprint
    }

    pub(crate) fn display_fields(&self) -> (&str, &str, &str) {
        (&self.display_name, &self.platform, &self.app_version)
    }

    pub(crate) fn pending_activation(&self) -> Option<&PendingActivation> {
        self.pending_activation.as_ref()
    }

    /// Freeze the next request. The worker saves the result before sending it
    /// and sends the pending values from that saved snapshot.
    pub(crate) fn begin_activation(
        &mut self,
        path: ActivationPath,
        platform: &str,
        version: &str,
        display_name: &str,
    ) -> Result<&PendingActivation, AccountStorageError> {
        if let Some(pending) = &self.pending_activation {
            if pending.path != path {
                return Err(AccountStorageError::PendingActivationPath);
            }
        } else {
            let identity =
                DeviceIdentity::new(&self.install_fingerprint, platform, version, display_name)
                    .map_err(|_| AccountStorageError::InvalidIdentity)?;
            self.pending_activation = Some(PendingActivation {
                path,
                idempotency_key: random_id(|bytes| getrandom::fill(bytes).is_ok())?,
                identity: InstallIdentity {
                    install_fingerprint: identity.fingerprint,
                    platform: identity.platform.clone(),
                    app_version: identity.app_version.clone(),
                    display_name: identity.display_name.clone(),
                },
            });
            self.platform = identity.platform;
            self.app_version = identity.app_version;
            self.display_name = identity.display_name;
        }
        self.pending_activation
            .as_ref()
            .ok_or(AccountStorageError::Malformed)
    }

    /// A definitive outcome lets the worker retire the pending request. An
    /// ambiguous outcome must leave it saved for retry.
    pub(crate) fn clear_pending_activation(&mut self) {
        self.pending_activation = None;
    }

    fn validate(&self) -> Result<(), AccountStorageError> {
        if self.schema_version != SCHEMA_VERSION || !is_random_id(&self.install_fingerprint) {
            return Err(AccountStorageError::Malformed);
        }

        let normalized = DeviceIdentity::new(
            &self.install_fingerprint,
            &self.platform,
            &self.app_version,
            &self.display_name,
        )
        .map_err(|_| AccountStorageError::Malformed)?;
        if normalized.platform != self.platform
            || normalized.app_version != self.app_version
            || normalized.display_name != self.display_name
        {
            return Err(AccountStorageError::Malformed);
        }

        if let Some(id) = &self.activated_public_id {
            // The current API issues dev_ followed by 16 random bytes in hex.
            if !id.strip_prefix("dev_").is_some_and(is_random_id) {
                return Err(AccountStorageError::Malformed);
            }
        }
        if let Some(pending) = &self.pending_activation {
            let identity = pending.device_identity()?;
            if identity.fingerprint != self.install_fingerprint
                || !is_random_id(&pending.idempotency_key)
            {
                return Err(AccountStorageError::Malformed);
            }
        }
        Ok(())
    }
}

fn is_random_id(value: &str) -> bool {
    value.len() == 32
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn random_id(fill: impl FnOnce(&mut [u8; 16]) -> bool) -> Result<String, AccountStorageError> {
    let mut bytes = [0; 16];
    if !fill(&mut bytes) {
        return Err(AccountStorageError::EntropyUnavailable);
    }
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut encoded = String::with_capacity(32);
    for byte in bytes {
        encoded.push(char::from(HEX[usize::from(byte >> 4)]));
        encoded.push(char::from(HEX[usize::from(byte & 0x0f)]));
    }
    Ok(encoded)
}

/// Fixed files inside the operator's OS-resolved app-data directory.
pub(crate) struct AccountMetadataStore {
    directory: PathBuf,
}

impl AccountMetadataStore {
    pub(crate) fn new(directory: PathBuf) -> Self {
        Self { directory }
    }

    pub(crate) fn load_or_create(
        &self,
        presence: CredentialPresence,
    ) -> Result<AccountMetadata, AccountStorageError> {
        self.load_or_create_with_entropy(presence, |bytes| getrandom::fill(bytes).is_ok())
    }

    pub(super) fn load_or_create_with_entropy(
        &self,
        presence: CredentialPresence,
        fill: impl FnOnce(&mut [u8; 16]) -> bool,
    ) -> Result<AccountMetadata, AccountStorageError> {
        let path = self.directory.join(METADATA_FILE);
        let directory_exists = self.directory_exists()?;
        if directory_exists {
            // Publication replaces the entire file. A reader can load the
            // observed generation without opening or creating a write lock.
            if let Some(metadata) = read_metadata(&path)? {
                return Ok(metadata);
            }
        }
        match presence {
            CredentialPresence::Present => {
                return Err(AccountStorageError::IdentityRecoveryRequired)
            }
            CredentialPresence::Unavailable => {
                return Err(AccountStorageError::CredentialPresenceUnavailable)
            }
            CredentialPresence::Missing => {}
        }

        if !directory_exists {
            // Tauri can resolve the app-data location before it exists.
            fs::create_dir_all(&self.directory)?;
        }
        let _lock = self.lock()?;
        // Another process may have published the identity while we waited.
        if let Some(metadata) = read_metadata(&path)? {
            return Ok(metadata);
        }
        let metadata = AccountMetadata {
            schema_version: SCHEMA_VERSION,
            revision: 0,
            install_fingerprint: random_id(fill)?,
            platform: std::env::consts::OS.to_owned(),
            app_version: env!("CARGO_PKG_VERSION").to_owned(),
            display_name: String::new(),
            activated_public_id: None,
            skipped_setup: false,
            pending_activation: None,
        };
        self.publish(&path, &metadata)?;
        Ok(metadata)
    }

    /// Compare the loaded revision under the lock before publishing. Continue
    /// using the returned snapshot after a successful save. On Changed, obtain
    /// fresh custody evidence and reload before deciding how to proceed.
    pub(crate) fn save(
        &self,
        metadata: &AccountMetadata,
    ) -> Result<AccountMetadata, AccountStorageError> {
        let _lock = self.lock()?;
        let path = self.directory.join(METADATA_FILE);
        let current = read_metadata(&path)?.ok_or(AccountStorageError::Changed)?;
        if current.revision != metadata.revision
            || current.install_fingerprint != metadata.install_fingerprint
        {
            return Err(AccountStorageError::Changed);
        }
        if let (Some(saved), Some(candidate)) =
            (&current.pending_activation, &metadata.pending_activation)
        {
            if saved != candidate {
                return Err(AccountStorageError::Changed);
            }
        }
        let mut committed = metadata.clone();
        committed.revision = committed
            .revision
            .checked_add(1)
            .ok_or(AccountStorageError::Changed)?;
        self.publish(&path, &committed)?;
        Ok(committed)
    }

    fn directory_exists(&self) -> Result<bool, AccountStorageError> {
        if !self.directory.is_absolute()
            || self
                .directory
                .components()
                .any(|component| component == Component::ParentDir)
        {
            return Err(AccountStorageError::UnsafePath);
        }
        match fs::symlink_metadata(&self.directory) {
            Ok(metadata) if metadata.is_dir() && !is_link_or_device(&metadata) => Ok(true),
            Ok(_) => Err(AccountStorageError::UnsafePath),
            Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(false),
            Err(error) => Err(error.into()),
        }
    }

    fn lock(&self) -> Result<File, AccountStorageError> {
        if !self.directory_exists()? {
            return Err(AccountStorageError::Changed);
        }

        // A fixed inode serializes cooperating writers across replacements.
        // A writer can restore a missing lock before rereading metadata.
        let file = open_regular(&self.directory.join(LOCK_FILE), true)?
            .ok_or(AccountStorageError::Changed)?;
        validate_open_regular(&file, true)?;
        file.lock()?;
        Ok(file)
    }

    fn publish(
        &self,
        destination: &Path,
        metadata: &AccountMetadata,
    ) -> Result<(), AccountStorageError> {
        metadata.validate()?;
        let body = serde_json::to_vec(metadata).map_err(|_| AccountStorageError::Malformed)?;
        if body.len() > MAX_METADATA_BYTES {
            return Err(AccountStorageError::Oversize);
        }

        let staging = self.directory.join(STAGING_FILE);
        if observe_regular(&staging)? {
            fs::remove_file(&staging)?;
        }
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut file = options.open(&staging)?;
        let written = file.write_all(&body).and_then(|()| file.sync_all());
        drop(file);
        let published = written.and_then(|()| fs::rename(&staging, destination));
        if published.is_err() {
            let _ = fs::remove_file(&staging);
        }
        published?;
        #[cfg(unix)]
        File::open(&self.directory)?.sync_all()?;
        Ok(())
    }
}

fn read_metadata(path: &Path) -> Result<Option<AccountMetadata>, AccountStorageError> {
    let Some(file) = open_regular(path, false)? else {
        return Ok(None);
    };
    read_metadata_file(file).map(Some)
}

pub(super) fn read_metadata_file(file: File) -> Result<AccountMetadata, AccountStorageError> {
    let attrs = validate_open_regular(&file, false)?;
    let max = MAX_METADATA_BYTES as u64;
    if attrs.len() > max {
        return Err(AccountStorageError::Oversize);
    }
    let mut bytes = Vec::new();
    file.take(max + 1).read_to_end(&mut bytes)?;
    if bytes.len() > MAX_METADATA_BYTES {
        return Err(AccountStorageError::Oversize);
    }
    let metadata: AccountMetadata =
        serde_json::from_slice(&bytes).map_err(|_| AccountStorageError::Malformed)?;
    metadata.validate()?;
    Ok(metadata)
}

fn observe_regular(path: &Path) -> Result<bool, AccountStorageError> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.is_file() && !is_link_or_device(&metadata) => Ok(true),
        Ok(_) => Err(AccountStorageError::UnsafePath),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(false),
        Err(error) => Err(error.into()),
    }
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

fn open_regular(path: &Path, lock_file: bool) -> Result<Option<File>, AccountStorageError> {
    if !observe_regular(path)? && !lock_file {
        return Ok(None);
    }

    #[cfg(unix)]
    let opened = {
        use rustix::fs::{open, Mode, OFlags};
        let mut flags = OFlags::NOFOLLOW | OFlags::NONBLOCK | OFlags::CLOEXEC;
        flags |= if lock_file {
            OFlags::RDWR
        } else {
            OFlags::RDONLY
        };
        if lock_file {
            flags |= OFlags::CREATE;
        }
        match open(path, flags, Mode::RUSR | Mode::WUSR) {
            Ok(fd) => Ok(File::from(fd)),
            Err(rustix::io::Errno::LOOP) => return Err(AccountStorageError::UnsafePath),
            Err(error) => Err(io::Error::from(error)),
        }
    };
    #[cfg(windows)]
    let opened = {
        use std::os::windows::fs::OpenOptionsExt;
        use windows_sys::Win32::Storage::FileSystem::FILE_FLAG_OPEN_REPARSE_POINT;
        OpenOptions::new()
            .read(true)
            .write(lock_file)
            .create(lock_file)
            .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
            .open(path)
    };
    #[cfg(not(any(unix, windows)))]
    let opened = OpenOptions::new()
        .read(true)
        .write(lock_file)
        .create(lock_file)
        .open(path);

    let file = match opened {
        Ok(file) => file,
        Err(error) if !lock_file && error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.into()),
    };
    Ok(Some(file))
}

fn validate_open_regular(file: &File, lock_file: bool) -> Result<Metadata, AccountStorageError> {
    let attrs = file.metadata()?;
    if !attrs.is_file() || is_link_or_device(&attrs) {
        return Err(AccountStorageError::UnsafePath);
    }
    #[cfg(unix)]
    let link_count = {
        use std::os::unix::fs::MetadataExt;
        attrs.nlink()
    };
    #[cfg(windows)]
    let link_count = winapi_util::file::information(file)?.number_of_links();

    // A concurrent replacement can unlink an already-open metadata
    // generation. The lock must still name one inode for all writers.
    #[cfg(any(unix, windows))]
    if link_count > 1 || (lock_file && link_count == 0) {
        return Err(AccountStorageError::UnsafePath);
    }
    Ok(attrs)
}
