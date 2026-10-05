//! The registry of installed translations (feature `installed`).
//!
//! A [`Registry`] owns one directory in the app DATA directory (not the OS cache directory, which
//! the OS may purge): one `<name>.tsv.gz` per installed translation and one receipt,
//! [`RECEIPT_FILE`] (`installed.json`), which records what is installed (code, digest, size, the
//! time it was installed as the caller's clock gave it, the catalogue schema). The receipt is the
//! single source of truth: a file without a receipt entry is not installed, and an entry whose file
//! is missing or is a symlink is not listed.
//!
//! # Installing
//!
//! [`Registry::install_from_reader`] (and `install_from_file`) run one pipeline, and a file becomes
//! installed only at its end:
//!
//! 1. the bytes stream into a staging file that is **created exclusively** (a pre-planted file or
//!    symlink at that name is never followed or overwritten; the next free name is used), capped at
//!    the catalogue's pinned size, while a SHA-256 is computed;
//! 2. the digest must equal the catalogue's; then [`crate::validate`] checks the file's shape (a
//!    decompression cap, the row grammar, books 1 to 66, ascending rows, no markup residue, verse
//!    counts equal to the catalogue entry);
//! 3. the new receipt is written to its own temp file, the staging file is renamed onto the final
//!    name, and the receipt is renamed into place.
//!
//! Any failure or a cancel before step 3 removes the staging file (and only a file this call
//! created) and changes nothing that was installed. The one window that is not a single rename is
//! between the last two renames: a crash there leaves the new file beside the old receipt, which
//! the load path refuses (its digest no longer matches), so it fails closed rather than serving
//! the wrong text; installing again repairs it.
//!
//! # Bounded memory
//!
//! Each decoded index is about 7 MiB. The registry keeps at most `capacity` of them (default
//! [`DEFAULT_RESIDENT_INDEXES`], 3) and evicts the least recently used. A re-installed or removed
//! translation is dropped from memory the next time anything is read (the receipt is re-read on
//! every read, so another process's install is seen too). The bundled translations are NOT part of
//! this and keep their own load-once indexes.

use std::collections::HashMap;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::bible::Bible;
use crate::catalog::{
    is_sha256_hex, validate_file_name, CatalogEntry, Catalogue, TranslationCode, MAX_ASSET_BYTES,
    MAX_ENTRIES,
};
use crate::digest::{hex_lower, sha256_hex};
use crate::validate::{decode_verses, validate_asset, Counts, ValidationError};
use crate::Verse;

/// How many decoded indexes are kept in memory at once, unless the registry is built with another
/// number. About 7 MiB each, so 3 is roughly 21 MiB.
pub const DEFAULT_RESIDENT_INDEXES: usize = 3;
/// The receipt file name inside the registry directory.
pub const RECEIPT_FILE: &str = "installed.json";
/// Overrides [`default_data_dir`] (tests, and a portable install). Used as given.
pub const DATA_DIR_ENV: &str = "SELAHCUE_SCRIPTURE_DATA";

const RECEIPT_SCHEMA: u64 = 1;
/// The largest receipt that is read at all. Real ones are a few hundred bytes per translation.
const MAX_RECEIPT_BYTES: u64 = 256 * 1024;
/// Bytes moved per read while staging (bounds transient memory).
const CHUNK_BYTES: usize = 64 * 1024;
/// How many staging names are tried before giving up (one per leftover or planted file).
const MAX_STAGING_NAMES: u32 = 16;
const STAGING_SUFFIX: &str = ".part";
const RECEIPT_TEMP_BASE: &str = ".installed.json";
const RECEIPT_TEMP_SUFFIX: &str = ".tmp";

/// The directory installed translations live in: `$SELAHCUE_SCRIPTURE_DATA` if set, else
/// `selahcue/translations` under the platform's per-user DATA directory
/// (`%LOCALAPPDATA%` on Windows, `~/Library/Application Support` on macOS, `$XDG_DATA_HOME` or
/// `~/.local/share` elsewhere). Deliberately not the cache directory: the OS may purge a cache,
/// and a purged translation would silently disappear. `None` when no home directory can be found.
pub fn default_data_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os(DATA_DIR_ENV).filter(|d| !d.is_empty()) {
        return Some(PathBuf::from(dir));
    }
    data_root().map(|root| root.join("selahcue").join("translations"))
}

fn non_empty_env(name: &str) -> Option<PathBuf> {
    std::env::var_os(name)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}

#[cfg(target_os = "macos")]
fn data_root() -> Option<PathBuf> {
    non_empty_env("HOME").map(|h| h.join("Library").join("Application Support"))
}

#[cfg(target_os = "windows")]
fn data_root() -> Option<PathBuf> {
    non_empty_env("LOCALAPPDATA")
}

#[cfg(not(any(target_os = "macos", target_os = "windows")))]
fn data_root() -> Option<PathBuf> {
    // Per the XDG spec an empty or relative XDG_DATA_HOME is treated as unset.
    non_empty_env("XDG_DATA_HOME")
        .filter(|p| p.is_absolute())
        .or_else(|| non_empty_env("HOME").map(|h| h.join(".local").join("share")))
}

/// One installed translation, as the receipt records it.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct InstalledTranslation {
    pub code: TranslationCode,
    /// The plain file name inside the registry directory.
    pub file_name: String,
    /// Lowercase-hex SHA-256 of the file, as verified at install and re-checked at every load.
    pub sha256: String,
    pub size_bytes: u64,
    /// The `installed_at` the caller passed (its clock; this crate never reads one).
    pub installed_at: u64,
    /// The catalogue schema in force when it was installed.
    pub catalogue_schema: u32,
}

/// Where an install is.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Phase {
    /// Bytes are being received and written to the staging file.
    Downloading,
    /// The digest is being checked and the file's shape validated.
    Verifying,
    /// The file and the receipt are being put in place.
    Installing,
}

/// A progress report: bytes moved so far out of the pinned total, in a phase.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Progress {
    pub phase: Phase,
    pub done: u64,
    pub total: u64,
}

/// Optional callbacks for an install: a progress report and a cancel flag.
#[derive(Default)]
pub struct InstallHooks<'a> {
    cancel: Option<&'a AtomicBool>,
    progress: Option<&'a dyn Fn(Progress)>,
}

impl<'a> InstallHooks<'a> {
    /// Stop the install, cleanly, when `flag` becomes true. Checked before every chunk is read and
    /// before each later step; a read that is already blocked finishes (or times out) first.
    pub fn with_cancel(mut self, flag: &'a AtomicBool) -> Self {
        self.cancel = Some(flag);
        self
    }

    /// Call `report` as the install advances.
    pub fn with_progress(mut self, report: &'a dyn Fn(Progress)) -> Self {
        self.progress = Some(report);
        self
    }

    pub(crate) fn check_cancel(&self) -> Result<(), InstallError> {
        if self.cancel.is_some_and(|c| c.load(Ordering::Relaxed)) {
            Err(InstallError::Cancelled)
        } else {
            Ok(())
        }
    }

    fn report(&self, phase: Phase, done: u64, total: u64) {
        if let Some(f) = self.progress {
            f(Progress { phase, done, total });
        }
    }
}

/// Why the receipt could not be read or written.
#[derive(Debug)]
pub enum ReceiptError {
    /// `installed.json` is not a trustworthy receipt (not JSON, a symlink, too large, a bad field).
    Corrupt(String),
    Io(std::io::Error),
}

impl std::fmt::Display for ReceiptError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReceiptError::Corrupt(why) => write!(f, "the install record is damaged: {why}"),
            ReceiptError::Io(e) => write!(f, "the install record could not be read: {e}"),
        }
    }
}

impl std::error::Error for ReceiptError {}

/// Why an install failed. A failure never leaves a partial install: nothing that was installed
/// before changes, and no staging file is left behind.
#[derive(Debug)]
pub enum InstallError {
    /// The catalogue has no such code.
    UnknownCode {
        code: String,
    },
    /// The catalogue's file name is not a plain name (defence in depth: the catalogue refuses these
    /// when it is parsed).
    FileName {
        file_name: String,
        reason: &'static str,
    },
    /// The caller's cancel flag was set.
    Cancelled,
    /// The source gave more bytes than the catalogue pins.
    TooLarge {
        limit: u64,
    },
    /// The bytes' SHA-256 is not the catalogue's.
    Verify {
        expected: String,
        actual: String,
    },
    /// The digest matched but the file is not shaped like a Bible.
    Invalid(ValidationError),
    /// Reading the SOURCE failed (a dropped connection, an unreadable path).
    Source(std::io::Error),
    /// Writing under the registry directory failed.
    Io(std::io::Error),
    Receipt(ReceiptError),
}

impl std::fmt::Display for InstallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InstallError::UnknownCode { code } => write!(f, "'{code}' is not in the catalogue"),
            InstallError::FileName { file_name, reason } => {
                write!(
                    f,
                    "catalogue file name '{file_name}' is not usable: {reason}"
                )
            }
            InstallError::Cancelled => write!(f, "the install was cancelled"),
            InstallError::TooLarge { limit } => {
                write!(
                    f,
                    "the file is larger than the {limit} bytes the catalogue pins"
                )
            }
            InstallError::Verify { expected, actual } => write!(
                f,
                "integrity check failed: expected {expected}, got {actual}"
            ),
            InstallError::Invalid(e) => write!(f, "the file is not a valid translation: {e}"),
            InstallError::Source(e) => write!(f, "reading the translation failed: {e}"),
            InstallError::Io(e) => write!(f, "writing the translation failed: {e}"),
            InstallError::Receipt(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for InstallError {}

impl From<ReceiptError> for InstallError {
    fn from(e: ReceiptError) -> Self {
        InstallError::Receipt(e)
    }
}

/// Why a translation's text could not be read.
#[derive(Debug)]
pub enum LoadError {
    /// No receipt entry for the code.
    NotInstalled,
    /// The receipt names a file that is missing, or is not a regular file.
    Missing,
    /// The file is not the one the receipt records (damaged or replaced after install).
    Mismatch {
        expected: String,
        actual: String,
    },
    /// The file no longer validates.
    Invalid(ValidationError),
    Io(std::io::Error),
    Receipt(ReceiptError),
}

impl std::fmt::Display for LoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LoadError::NotInstalled => write!(f, "that translation is not installed"),
            LoadError::Missing => write!(f, "the translation's file is missing"),
            LoadError::Mismatch { expected, actual } => write!(
                f,
                "the translation's file is not the one that was installed (expected {expected}, got {actual})"
            ),
            LoadError::Invalid(e) => write!(f, "the translation's file is not valid: {e}"),
            LoadError::Io(e) => write!(f, "the translation could not be read: {e}"),
            LoadError::Receipt(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for LoadError {}

/// What [`Registry::recover`] did.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Recovered {
    /// Leftover staging files removed.
    pub removed: usize,
    /// Staging-looking entries left alone because they are not regular files (a symlink, a folder).
    pub skipped: usize,
}

/// A file this call created, removed on drop unless disarmed. It is only ever built from a path
/// returned by an exclusive create, so it can only remove what this call made.
pub(crate) struct Created {
    pub(crate) path: PathBuf,
    armed: bool,
}

impl Created {
    pub(crate) fn new(path: PathBuf) -> Created {
        Created { path, armed: true }
    }

    pub(crate) fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for Created {
    fn drop(&mut self) {
        if self.armed {
            let _ = fs::remove_file(&self.path);
        }
    }
}

/// Create a new file `dir/<base><suffix>` that must not already exist, trying `<base>.1<suffix>`,
/// `<base>.2<suffix>`, ... when a name is taken. `create_new` is `O_EXCL`: it fails if the path
/// exists AS ANYTHING, including a symlink (dangling or not), so a planted link is never followed.
pub(crate) fn create_exclusive(
    dir: &Path,
    base: &str,
    suffix: &str,
) -> std::io::Result<(PathBuf, File)> {
    for attempt in 0..MAX_STAGING_NAMES {
        let name = if attempt == 0 {
            format!("{base}{suffix}")
        } else {
            format!("{base}.{attempt}{suffix}")
        };
        let path = dir.join(name);
        match OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
        {
            Ok(file) => return Ok((path, file)),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e),
        }
    }
    Err(std::io::Error::new(
        std::io::ErrorKind::AlreadyExists,
        "no free staging file name",
    ))
}

/// Whether `name` is one of the files THIS module stages: `<file>.tsv.gz.part` or
/// `<file>.tsv.gz.<n>.part` (an install in flight), or `.installed.json.tmp` /
/// `.installed.json.<n>.tmp` (a receipt being written). Narrow on purpose: cleanup runs in a
/// directory a user can point elsewhere (`SELAHCUE_SCRIPTURE_DATA`), and `movie.mp4.part` is not
/// ours to delete.
fn is_staging_name(name: &str) -> bool {
    // Drop an optional `.<n>` attempt counter from the end of `stem`.
    fn without_counter(stem: &str) -> &str {
        match stem.rsplit_once('.') {
            Some((head, n)) if !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()) => head,
            _ => stem,
        }
    }
    if let Some(stem) = name.strip_suffix(STAGING_SUFFIX) {
        let file = without_counter(stem);
        return file.ends_with(".tsv.gz") && validate_file_name(file).is_ok();
    }
    if let Some(stem) = name.strip_suffix(RECEIPT_TEMP_SUFFIX) {
        return without_counter(stem) == RECEIPT_TEMP_BASE;
    }
    false
}

/// Flush a directory's entries to disk where the OS lets a program ask (best effort).
fn sync_dir(dir: &Path) {
    #[cfg(unix)]
    if let Ok(d) = File::open(dir) {
        let _ = d.sync_all();
    }
    #[cfg(not(unix))]
    let _ = dir;
}

fn receipt_path(dir: &Path) -> PathBuf {
    dir.join(RECEIPT_FILE)
}

/// Read and validate the receipt. A missing file is an empty list; anything else wrong with it is
/// [`ReceiptError`]. Never follows a symlink, never reads more than [`MAX_RECEIPT_BYTES`].
fn read_receipts(dir: &Path) -> Result<Vec<InstalledTranslation>, ReceiptError> {
    let path = receipt_path(dir);
    let meta = match fs::symlink_metadata(&path) {
        Ok(m) => m,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(ReceiptError::Io(e)),
    };
    if !meta.file_type().is_file() {
        return Err(ReceiptError::Corrupt(
            "installed.json is not a regular file".to_string(),
        ));
    }
    let mut bytes = Vec::new();
    File::open(&path)
        .and_then(|f| f.take(MAX_RECEIPT_BYTES + 1).read_to_end(&mut bytes))
        .map_err(ReceiptError::Io)?;
    if bytes.len() as u64 > MAX_RECEIPT_BYTES {
        return Err(ReceiptError::Corrupt(format!(
            "installed.json is larger than {MAX_RECEIPT_BYTES} bytes"
        )));
    }
    parse_receipts(&bytes)
}

/// The receipt to build the next one from: what is there, or nothing if it is damaged (an install
/// or a removal replaces the file anyway, so a bad receipt is healed rather than blocking).
fn receipts_for_update(dir: &Path) -> Result<Vec<InstalledTranslation>, InstallError> {
    match read_receipts(dir) {
        Ok(list) => Ok(list),
        Err(ReceiptError::Corrupt(_)) => Ok(Vec::new()),
        Err(e) => Err(InstallError::Receipt(e)),
    }
}

fn parse_receipts(bytes: &[u8]) -> Result<Vec<InstalledTranslation>, ReceiptError> {
    let bad = |why: &str| ReceiptError::Corrupt(why.to_string());
    let doc: Value = serde_json::from_slice(bytes)
        .map_err(|e| ReceiptError::Corrupt(format!("not valid JSON: {e}")))?;
    let root = doc.as_object().ok_or_else(|| bad("not a JSON object"))?;
    if root.get("schema").and_then(Value::as_u64) != Some(RECEIPT_SCHEMA) {
        return Err(bad("unsupported receipt schema"));
    }
    let list = root
        .get("translations")
        .and_then(Value::as_array)
        .ok_or_else(|| bad("'translations' is not an array"))?;
    if list.len() > MAX_ENTRIES {
        return Err(bad("too many entries"));
    }

    let mut out: Vec<InstalledTranslation> = Vec::with_capacity(list.len());
    for item in list {
        let o = item
            .as_object()
            .ok_or_else(|| bad("an entry is not an object"))?;
        let text = |key: &str| {
            o.get(key)
                .and_then(Value::as_str)
                .ok_or_else(|| ReceiptError::Corrupt(format!("'{key}' is missing or not text")))
        };
        let number = |key: &str| {
            o.get(key)
                .and_then(Value::as_u64)
                .ok_or_else(|| ReceiptError::Corrupt(format!("'{key}' is missing or not a number")))
        };
        let code = TranslationCode::parse(text("code")?)
            .map_err(|e| ReceiptError::Corrupt(format!("code is not usable: {e:?}")))?;
        let file_name = text("file_name")?;
        validate_file_name(file_name).map_err(|why| {
            ReceiptError::Corrupt(format!(
                "file_name '{file_name}' is not a plain name: {why}"
            ))
        })?;
        let sha256 = text("sha256")?;
        if !is_sha256_hex(sha256) {
            return Err(bad("sha256 is not 64 lowercase hex characters"));
        }
        let size_bytes = number("size_bytes")?;
        if size_bytes == 0 || size_bytes > MAX_ASSET_BYTES {
            return Err(bad("size_bytes is outside the allowed range"));
        }
        let catalogue_schema = u32::try_from(number("catalogue_schema")?)
            .map_err(|_| bad("catalogue_schema is too large"))?;
        if out.iter().any(|r| r.code == code) {
            return Err(bad("a code is listed twice"));
        }
        out.push(InstalledTranslation {
            code,
            file_name: file_name.to_string(),
            sha256: sha256.to_string(),
            size_bytes,
            installed_at: number("installed_at")?,
            catalogue_schema,
        });
    }
    Ok(out)
}

fn render_receipts(list: &[InstalledTranslation]) -> Vec<u8> {
    let translations: Vec<Value> = list
        .iter()
        .map(|r| {
            json!({
                "code": r.code.as_str(),
                "file_name": r.file_name,
                "sha256": r.sha256,
                "size_bytes": r.size_bytes,
                "installed_at": r.installed_at,
                "catalogue_schema": r.catalogue_schema,
            })
        })
        .collect();
    let doc = json!({ "schema": RECEIPT_SCHEMA, "translations": translations });
    let mut bytes = serde_json::to_vec_pretty(&doc).unwrap_or_default();
    bytes.push(b'\n');
    bytes
}

/// Whether the receipt's file is really there: a regular file (never a symlink) of the recorded
/// size. A cheap check; the digest is checked when the text is read.
fn file_in_place(dir: &Path, rec: &InstalledTranslation) -> bool {
    fs::symlink_metadata(dir.join(&rec.file_name))
        .is_ok_and(|m| m.file_type().is_file() && m.len() == rec.size_bytes)
}

struct Resident {
    code: String,
    sha256: String,
    index: Arc<Vec<Verse>>,
    hits: u64,
}

#[derive(Default)]
struct State {
    /// Most recently used first. Never longer than the registry's capacity.
    resident: Vec<Resident>,
    /// How many times each code's file has been decoded (a test seam). Keys are codes taken from
    /// receipts, so at most [`MAX_ENTRIES`] of them.
    loads: HashMap<String, u64>,
    /// The most decoded indexes that were in memory at once, counting the one being decoded (a test
    /// seam: it is what proves eviction happens BEFORE a decode, not after).
    peak: usize,
}

impl State {
    /// Drop every resident index that is no longer what the receipt says is installed: a removed
    /// translation, or one that has been replaced by a file with a different digest.
    fn prune(&mut self, receipts: &[InstalledTranslation]) {
        self.resident.retain(|r| {
            receipts
                .iter()
                .any(|x| x.code.as_str() == r.code && x.sha256 == r.sha256)
        });
    }
}

struct Inner {
    dir: PathBuf,
    catalogue: Catalogue,
    capacity: usize,
    /// Serialises install, remove and recover (one writer at a time in this process).
    write_lock: Mutex<()>,
    state: Mutex<State>,
}

/// A directory of installed translations plus a bounded cache of their decoded text.
///
/// Cheap to clone (a shared handle). Constructing one does no I/O; the directory is created by the
/// first install. One registry per process is the norm ([`Registry::global`]); tests build their
/// own over private directories.
#[derive(Clone)]
pub struct Registry {
    inner: Arc<Inner>,
}

impl std::fmt::Debug for Registry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Registry")
            .field("dir", &self.inner.dir)
            .field("capacity", &self.inner.capacity)
            .finish()
    }
}

impl Registry {
    /// A registry over `dir`, validating installs against `catalogue`, keeping at most
    /// [`DEFAULT_RESIDENT_INDEXES`] decoded indexes in memory.
    pub fn new(dir: impl Into<PathBuf>, catalogue: Catalogue) -> Registry {
        Registry::with_capacity(dir, catalogue, DEFAULT_RESIDENT_INDEXES)
    }

    /// Like [`Registry::new`] with an explicit cap on resident decoded indexes. A cap of 0 is one:
    /// a cache that holds nothing would decode the whole file on every lookup.
    pub fn with_capacity(
        dir: impl Into<PathBuf>,
        catalogue: Catalogue,
        capacity: usize,
    ) -> Registry {
        Registry {
            inner: Arc::new(Inner {
                dir: dir.into(),
                catalogue,
                capacity: capacity.max(1),
                write_lock: Mutex::new(()),
                state: Mutex::new(State::default()),
            }),
        }
    }

    /// The process-wide registry: the embedded catalogue over [`default_data_dir`]. `None` when no
    /// data directory can be worked out. The directory is resolved once, on first use.
    pub fn global() -> Option<&'static Registry> {
        static GLOBAL: OnceLock<Option<Registry>> = OnceLock::new();
        GLOBAL
            .get_or_init(|| {
                default_data_dir().map(|dir| Registry::new(dir, Catalogue::embedded().clone()))
            })
            .as_ref()
    }

    pub fn dir(&self) -> &Path {
        &self.inner.dir
    }

    /// Whether `other` is a handle to this same registry (not merely one over the same directory).
    pub(crate) fn same_registry(&self, other: &Registry) -> bool {
        Arc::ptr_eq(&self.inner, &other.inner)
    }

    pub fn catalogue(&self) -> &Catalogue {
        &self.inner.catalogue
    }

    /// The most decoded indexes this registry keeps in memory.
    pub fn capacity(&self) -> usize {
        self.inner.capacity
    }

    fn lock_state(&self) -> MutexGuard<'_, State> {
        // A panic in another thread while it held the lock cannot leave the state half-updated in
        // a way that matters (every update is a single push, remove or truncate), so recover it.
        self.inner.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn lock_write(&self) -> MutexGuard<'_, ()> {
        self.inner
            .write_lock
            .lock()
            .unwrap_or_else(|e| e.into_inner())
    }

    /// Every translation that is installed: has a receipt entry AND a regular file of the recorded
    /// size. In code order. An unreadable or damaged receipt is an `Err` (so a screen can say so),
    /// and a missing one is simply no installs.
    pub fn installed(&self) -> Result<Vec<InstalledTranslation>, ReceiptError> {
        let dir = &self.inner.dir;
        Ok(read_receipts(dir)?
            .into_iter()
            .filter(|r| file_in_place(dir, r))
            .collect())
    }

    /// The receipt entry for `code` if it is installed (see [`Registry::installed`]).
    pub fn installed_entry(&self, code: &TranslationCode) -> Option<InstalledTranslation> {
        self.installed().ok()?.into_iter().find(|r| &r.code == code)
    }

    /// A handle for installed translation `code` (case-insensitive), or `None` when it is not
    /// installed. See [`Bible`].
    pub fn bible(&self, code: &str) -> Option<Bible> {
        let upper = code.to_ascii_uppercase();
        let code = TranslationCode::parse(&upper).ok()?;
        self.installed_entry(&code)?;
        let name = self
            .inner
            .catalogue
            .find(code.as_str())
            .map(|e| e.name.clone())
            .unwrap_or_else(|| code.to_string());
        Some(Bible::installed(self.clone(), code, name))
    }

    /// The decoded text of installed translation `code`.
    ///
    /// Served from memory when resident; otherwise the file is read, checked against the receipt's
    /// digest, validated and decoded, and becomes the most recently used. The receipt is re-read on
    /// every call, so a translation re-installed (by this process or another) is served from its
    /// new file, never the stale decoded copy. The returned `Arc` is a snapshot: an eviction while
    /// a caller holds it frees the memory only when the caller lets go.
    pub fn index(&self, code: &TranslationCode) -> Result<Arc<Vec<Verse>>, LoadError> {
        let mut st = self.lock_state();
        let receipts = read_receipts(&self.inner.dir).map_err(LoadError::Receipt)?;
        st.prune(&receipts);
        let rec = receipts
            .iter()
            .find(|r| &r.code == code)
            .ok_or(LoadError::NotInstalled)?;

        if let Some(pos) = st.resident.iter().position(|r| r.code == code.as_str()) {
            let mut hit = st.resident.remove(pos);
            hit.hits += 1;
            let index = Arc::clone(&hit.index);
            st.resident.insert(0, hit);
            return Ok(index);
        }

        // 1. Read and verify the file first: that is the step that fails for a missing or damaged
        //    file, and it must not cost a good index its place in memory.
        let bytes = self.read_verified(rec)?;
        // 2. Make room BEFORE decoding. After this there are at most `capacity - 1` indexes
        //    resident, so the one decoded next brings the total to `capacity`, never to
        //    `capacity + 1`: the peak, not just the steady state, is bounded. (The lock is held
        //    throughout, so at most one decode is in flight.)
        st.resident.truncate(self.inner.capacity - 1);
        st.peak = st.peak.max(st.resident.len() + 1);
        let index = Arc::new(self.decode(rec, &bytes)?);
        *st.loads.entry(code.to_string()).or_insert(0) += 1;
        st.resident.insert(
            0,
            Resident {
                code: code.to_string(),
                sha256: rec.sha256.clone(),
                index: Arc::clone(&index),
                hits: 0,
            },
        );
        Ok(index)
    }

    /// Check that installed translation `code` is intact: it has a receipt entry, its file is a
    /// regular file, and the file's SHA-256 is the receipt's. Reads and hashes the file but decodes
    /// nothing and touches no cache, so it can never evict a resident index.
    pub fn verify(&self, code: &TranslationCode) -> Result<(), LoadError> {
        let receipts = read_receipts(&self.inner.dir).map_err(LoadError::Receipt)?;
        let rec = receipts
            .iter()
            .find(|r| &r.code == code)
            .ok_or(LoadError::NotInstalled)?;
        self.read_verified(rec).map(drop)
    }

    /// Decode `bytes` (already verified against the receipt) into a verse index.
    fn decode(&self, rec: &InstalledTranslation, bytes: &[u8]) -> Result<Vec<Verse>, LoadError> {
        let hint = self
            .inner
            .catalogue
            .find(rec.code.as_str())
            .map_or(32_000, |e| e.verse_count() as usize);
        decode_verses(bytes, hint).map_err(LoadError::Invalid)
    }

    /// The file's bytes, once, after checking they are the ones the receipt records. Read into
    /// memory (bounded by the receipt's size, itself capped) and hashed THERE, so what is checked
    /// is what is used: nothing can change between the check and the decode.
    fn read_verified(&self, rec: &InstalledTranslation) -> Result<Vec<u8>, LoadError> {
        let path = self.inner.dir.join(&rec.file_name);
        match fs::symlink_metadata(&path) {
            Ok(m) if m.file_type().is_file() => {}
            Ok(_) => return Err(LoadError::Missing),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Err(LoadError::Missing),
            Err(e) => return Err(LoadError::Io(e)),
        }
        let mut bytes = Vec::with_capacity(rec.size_bytes.min(MAX_ASSET_BYTES) as usize);
        File::open(&path)
            .and_then(|f| f.take(rec.size_bytes + 1).read_to_end(&mut bytes))
            .map_err(LoadError::Io)?;
        let actual = sha256_hex(&bytes);
        if bytes.len() as u64 != rec.size_bytes || actual != rec.sha256 {
            return Err(LoadError::Mismatch {
                expected: rec.sha256.clone(),
                actual,
            });
        }
        Ok(bytes)
    }

    /// Install `code` from the file at `source`. See [`Registry::install_from_reader`].
    pub fn install_from_file(
        &self,
        code: &str,
        source: &Path,
        installed_at: u64,
        hooks: &InstallHooks<'_>,
    ) -> Result<InstalledTranslation, InstallError> {
        let meta = fs::symlink_metadata(source).map_err(InstallError::Source)?;
        if !meta.file_type().is_file() {
            return Err(InstallError::Source(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "the source is not a regular file",
            )));
        }
        let mut file = File::open(source).map_err(InstallError::Source)?;
        self.install_from_reader(code, &mut file, installed_at, hooks)
    }

    /// Install `code` (case-insensitive) from `source`, which is read to its end.
    ///
    /// The code must be in this registry's catalogue; the source must be exactly the pinned size
    /// and SHA-256 and must pass [`crate::validate`] with the entry's verse counts. `installed_at`
    /// is recorded as given (the caller's clock). On success the translation is installed and any
    /// earlier install of the same code is replaced; on any failure nothing installed changes.
    pub fn install_from_reader(
        &self,
        code: &str,
        source: &mut dyn Read,
        installed_at: u64,
        hooks: &InstallHooks<'_>,
    ) -> Result<InstalledTranslation, InstallError> {
        let _writer = self.lock_write();
        let entry = self
            .inner
            .catalogue
            .find(code)
            .ok_or_else(|| InstallError::UnknownCode {
                code: code.to_string(),
            })?;
        self.install_locked(entry, source, installed_at, hooks)
    }

    fn install_locked(
        &self,
        entry: &CatalogEntry,
        source: &mut dyn Read,
        installed_at: u64,
        hooks: &InstallHooks<'_>,
    ) -> Result<InstalledTranslation, InstallError> {
        let dir = &self.inner.dir;
        validate_file_name(&entry.file_name).map_err(|reason| InstallError::FileName {
            file_name: entry.file_name.clone(),
            reason,
        })?;
        hooks.check_cancel()?;
        fs::create_dir_all(dir).map_err(InstallError::Io)?;
        // Leftovers of an install that was killed (never counted as installed) go first.
        let _ = self.recover_locked();

        let total = entry.size_bytes;
        let (staging_path, mut file) =
            create_exclusive(dir, &entry.file_name, STAGING_SUFFIX).map_err(InstallError::Io)?;
        let mut staging = Created::new(staging_path.clone());

        // 1. Stream into the staging file, hashing, capped at the pinned size.
        let mut hasher = Sha256::new();
        let mut buf = vec![0u8; CHUNK_BYTES];
        let mut done: u64 = 0;
        loop {
            hooks.check_cancel()?;
            let n = match source.read(&mut buf) {
                Ok(n) => n,
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(e) => return Err(InstallError::Source(e)),
            };
            if n == 0 {
                break;
            }
            if done.saturating_add(n as u64) > total {
                return Err(InstallError::TooLarge { limit: total });
            }
            file.write_all(&buf[..n]).map_err(InstallError::Io)?;
            hasher.update(&buf[..n]);
            done += n as u64;
            hooks.report(Phase::Downloading, done, total);
        }

        // 2. The digest, then the shape of the file.
        hooks.check_cancel()?;
        hooks.report(Phase::Verifying, done, total);
        let actual = hex_lower(&hasher.finalize());
        if actual != entry.sha256 {
            return Err(InstallError::Verify {
                expected: entry.sha256.clone(),
                actual,
            });
        }
        file.flush().map_err(InstallError::Io)?;
        file.seek(SeekFrom::Start(0)).map_err(InstallError::Io)?;
        validate_asset(
            &mut file,
            Counts {
                ot: entry.verses_ot,
                nt: entry.verses_nt,
            },
        )
        .map_err(InstallError::Invalid)?;
        hooks.check_cancel()?;
        file.sync_all().map_err(InstallError::Io)?;
        drop(file);

        // 3. Put it in place: the new receipt is fully written first, so what remains is two
        // renames.
        hooks.report(Phase::Installing, done, total);
        let previous = receipts_for_update(dir)?;
        let had_before = previous.iter().any(|r| r.code == entry.code);
        let record = InstalledTranslation {
            code: entry.code.clone(),
            file_name: entry.file_name.clone(),
            sha256: entry.sha256.clone(),
            size_bytes: total,
            installed_at,
            catalogue_schema: self.inner.catalogue.schema(),
        };
        let mut next: Vec<InstalledTranslation> = previous
            .into_iter()
            .filter(|r| r.code != record.code)
            .collect();
        next.push(record.clone());
        next.sort_by(|a, b| a.code.as_str().cmp(b.code.as_str()));

        let mut receipt_tmp = self.write_receipt_temp(&next)?;
        hooks.check_cancel()?;
        let final_path = dir.join(&entry.file_name);
        fs::rename(&staging_path, &final_path).map_err(InstallError::Io)?;
        staging.disarm();
        if let Err(e) = fs::rename(&receipt_tmp.path, receipt_path(dir)) {
            if !had_before {
                // Nothing was installed before, so the file just moved into place would be an
                // orphan with no receipt. Take it back out.
                let _ = fs::remove_file(&final_path);
            }
            return Err(InstallError::Io(e));
        }
        receipt_tmp.disarm();
        sync_dir(dir);

        self.lock_state().prune(&next);
        Ok(record)
    }

    /// Write `list` to a fresh temp receipt (exclusive create, synced) and return its guard.
    fn write_receipt_temp(&self, list: &[InstalledTranslation]) -> Result<Created, InstallError> {
        let (path, mut file) =
            create_exclusive(&self.inner.dir, RECEIPT_TEMP_BASE, RECEIPT_TEMP_SUFFIX)
                .map_err(InstallError::Io)?;
        let guard = Created::new(path);
        file.write_all(&render_receipts(list))
            .and_then(|()| file.sync_all())
            .map_err(InstallError::Io)?;
        Ok(guard)
    }

    /// Remove an installed translation: its receipt entry, then its file. Returns `false` when it
    /// was not installed (or is not a code this registry could have installed), `true` when it was.
    /// A removed translation is also dropped from memory.
    pub fn remove(&self, code: &str) -> Result<bool, InstallError> {
        let _writer = self.lock_write();
        let upper = code.to_ascii_uppercase();
        let Ok(code) = TranslationCode::parse(&upper) else {
            return Ok(false);
        };
        let dir = &self.inner.dir;
        let previous = receipts_for_update(dir)?;
        let Some(record) = previous.iter().find(|r| r.code == code).cloned() else {
            return Ok(false);
        };
        let next: Vec<InstalledTranslation> =
            previous.into_iter().filter(|r| r.code != code).collect();

        // The receipt first: from this rename on it is not installed, whatever happens to the file.
        let mut receipt_tmp = self.write_receipt_temp(&next)?;
        fs::rename(&receipt_tmp.path, receipt_path(dir)).map_err(InstallError::Io)?;
        receipt_tmp.disarm();
        sync_dir(dir);
        self.lock_state().prune(&next);

        match fs::remove_file(dir.join(&record.file_name)) {
            Ok(()) => Ok(true),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(true),
            Err(e) => Err(InstallError::Io(e)),
        }
    }

    /// Clean up after an install that was killed: remove leftover staging files (`*.part`) and
    /// leftover temp receipts. Only regular files with those reserved names are removed; a symlink
    /// or a folder with such a name is left alone and counted as skipped. Safe to call at any
    /// time; installing calls it first. Does nothing if the directory does not exist.
    pub fn recover(&self) -> Result<Recovered, InstallError> {
        let _writer = self.lock_write();
        self.recover_locked().map_err(InstallError::Io)
    }

    fn recover_locked(&self) -> std::io::Result<Recovered> {
        let entries = match fs::read_dir(&self.inner.dir) {
            Ok(rd) => rd,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Recovered::default()),
            Err(e) => return Err(e),
        };
        let mut report = Recovered::default();
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if !is_staging_name(&name) {
                continue;
            }
            // `DirEntry::file_type` does not follow symlinks.
            let regular = entry.file_type().is_ok_and(|t| t.is_file());
            if regular && fs::remove_file(entry.path()).is_ok() {
                report.removed += 1;
            } else {
                report.skipped += 1;
            }
        }
        Ok(report)
    }

    /// **Test seam, not a product API.** The codes whose decoded index is in memory, most recently
    /// used first. Per registry instance, so no other test's reads can show up in it.
    #[doc(hidden)]
    pub fn resident_codes(&self) -> Vec<String> {
        self.lock_state()
            .resident
            .iter()
            .map(|r| r.code.clone())
            .collect()
    }

    /// **Test seam.** `Some(hits)` if `code`'s index is resident (how many reads were served from
    /// memory since it was decoded), `None` if it is not. Per key, never a global count.
    #[doc(hidden)]
    pub fn resident_hits_for(&self, code: &str) -> Option<u64> {
        self.lock_state()
            .resident
            .iter()
            .find(|r| r.code == code)
            .map(|r| r.hits)
    }

    /// **Test seam.** The most decoded indexes this registry has held at once, counting the one
    /// being decoded. Never more than [`Registry::capacity`]; equal to it once the cache has filled.
    #[doc(hidden)]
    pub fn peak_decoded(&self) -> usize {
        self.lock_state().peak
    }

    /// **Test seam.** How many times `code`'s file has been decoded by this registry.
    #[doc(hidden)]
    pub fn loads_for(&self, code: &str) -> u64 {
        self.lock_state().loads.get(code).copied().unwrap_or(0)
    }
}
