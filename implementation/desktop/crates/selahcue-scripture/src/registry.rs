//! The registry of installed translations (feature `installed`).
//!
//! A [`Registry`] owns one directory in the app DATA directory (not the OS cache directory, which
//! the OS may purge): one `<name>.tsv.gz` per installed translation and one receipt,
//! [`RECEIPT_FILE`] (`installed.json`, see [`crate::receipt`]), which records what is installed. The
//! receipt is the single source of truth: a file without a receipt entry is not installed, and an
//! entry whose file is missing or is a symlink is not listed.
//!
//! **One writer process.** The write lock, the in-flight list and every cache here are per
//! process. Nothing stops a second process installing into the same directory, and two would lose
//! updates and delete each other's staging files. Today only the operator installs; the host only
//! reads. If that ever changes, the answer is an advisory lock file, not this module.
//!
//! # Installing
//!
//! [`Registry::install_from_reader`] (and `install_from_file`) run one pipeline, and a file becomes
//! installed only at its end. The slow part runs WITHOUT the write lock, so a download in progress
//! never blocks `remove`, `recover` or another install:
//!
//! 1. the bytes stream into a staging file that is **created exclusively** (a pre-planted file or
//!    symlink at that name is never followed or overwritten; the next free name is used), capped at
//!    the catalogue's pinned size, while a SHA-256 is computed;
//! 2. the digest must equal the catalogue's; then [`crate::validate`] checks the file's shape (one
//!    gzip member, a decompression cap, the row grammar, books 1 to 66, ascending rows, no markup or
//!    invisible characters, verse counts equal to the catalogue entry);
//! 3. only now is the write lock taken (waiting for it honours the cancel flag): the new receipt is
//!    written to its own temp file, the staging file is renamed onto the final name, and the
//!    receipt is renamed into place.
//!
//! Any failure or a cancel before step 3 removes the staging file (and only a file this call
//! created) and changes nothing that was installed. The one window that is not a single rename is
//! between the last two renames: a crash there leaves the new file beside the old receipt, which
//! the load path refuses (its digest no longer matches), so it fails closed rather than serving
//! the wrong text; installing again repairs it.
//!
//! Installing or removing over an unreadable receipt is refused, never papered over: that would
//! forget every other install. [`Registry::repair_receipt`] rebuilds it from the files on disk.
//!
//! # Bounded memory
//!
//! Each decoded index is about 5 to 6 MB (measured: 4.6 to 6.0 MiB of text and rows per real
//! translation). The registry keeps at most `capacity` of them (default
//! [`DEFAULT_RESIDENT_INDEXES`], 3) and evicts the least recently used. Room is made BEFORE a
//! decode, by reserving a slot, so the peak, not just the steady state, stays at the cap even with
//! several threads loading at once; [`InstalledIndex`] counts itself from the first byte of memory,
//! which is how the tests observe the peak. The decode itself runs outside the state lock, so a
//! resident translation is never made to wait for another one's decode; a per-code latch stops two
//! threads decoding the same file. A translation this registry re-installs or removes is dropped
//! from memory by that call; one that another process replaced is dropped by the next read (the
//! receipt is re-read whenever its length, modification time or inode changes). The bundled
//! translations are NOT part of this and keep their own load-once indexes.

use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{Read, Seek, SeekFrom, Write};
use std::ops::Deref;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::{Arc, Condvar, Mutex, MutexGuard, OnceLock, TryLockError};
use std::time::Duration;

use sha2::{Digest, Sha256};

use crate::bible::Bible;
use crate::catalog::{validate_file_name, CatalogEntry, Catalogue, TranslationCode};
use crate::digest::{hex_lower, sha256_file, sha256_hex};
use crate::receipt::{file_in_place, read_receipts, receipt_path, render_receipts, Stamp};
pub use crate::receipt::{InstalledTranslation, ReceiptError, RECEIPT_FILE};
use crate::staging::{
    create_exclusive, is_staging_name, sync_dir, Created, Inflight, InflightGuard,
    RECEIPT_TEMP_BASE, RECEIPT_TEMP_SUFFIX,
};
use crate::validate::{decode_verses, validate_asset, Counts, ValidationError};
use crate::Verse;

/// How many decoded indexes are kept in memory at once, unless the registry is built with another
/// number. About 5 to 6 MB each, so 3 is roughly 15 to 18 MB.
pub const DEFAULT_RESIDENT_INDEXES: usize = 3;
/// Overrides [`default_data_dir`]: for development and portable installs. Must be an ABSOLUTE path;
/// a relative one is refused (see [`default_data_dir`]).
pub const DATA_DIR_ENV: &str = "SELAHCUE_SCRIPTURE_DATA";

/// Bytes moved per read while staging (bounds transient memory).
const CHUNK_BYTES: usize = 64 * 1024;
/// How long a queued install sleeps between looks at the write lock (and at its cancel flag).
const LOCK_POLL: Duration = Duration::from_millis(2);

/// The directory installed translations live in: `$SELAHCUE_SCRIPTURE_DATA` if set, else
/// `selahcue/translations` under the platform's per-user DATA directory
/// (`%LOCALAPPDATA%` on Windows, `~/Library/Application Support` on macOS, `$XDG_DATA_HOME` or
/// `~/.local/share` elsewhere). Deliberately not the cache directory: the OS may purge a cache,
/// and a purged translation would silently disappear. `None` when no home directory can be found.
///
/// The environment override is a development and portable-install switch. It is used as given
/// when it is an absolute path, and REFUSED (`None`, so nothing is read or written anywhere) when
/// it is relative: a relative path resolves against whatever directory the process happened to be
/// started in, which would silently move where translations are read from and where cleanup
/// deletes files. An empty value is the same as unset.
pub fn default_data_dir() -> Option<PathBuf> {
    if let Some(dir) = std::env::var_os(DATA_DIR_ENV).filter(|d| !d.is_empty()) {
        let dir = PathBuf::from(dir);
        return dir.is_absolute().then_some(dir);
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
    /// Stop the install, cleanly, when `flag` becomes true. Checked before every chunk is read,
    /// before each later step and while waiting for the write lock; a read that is already blocked
    /// finishes (or times out) first, and if it then fails the install reports `Cancelled`, not a
    /// network error.
    pub fn with_cancel(mut self, flag: &'a AtomicBool) -> Self {
        self.cancel = Some(flag);
        self
    }

    /// Call `report` as the install advances.
    pub fn with_progress(mut self, report: &'a dyn Fn(Progress)) -> Self {
        self.progress = Some(report);
        self
    }

    pub(crate) fn is_cancelled(&self) -> bool {
        self.cancel.is_some_and(|c| c.load(Ordering::Relaxed))
    }

    pub(crate) fn check_cancel(&self) -> Result<(), InstallError> {
        if self.is_cancelled() {
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

/// Why an install failed. A failure never leaves a partial install: nothing that was installed
/// before changes, and no staging file is left behind.
#[derive(Debug)]
pub enum InstallError {
    /// The catalogue has no such code.
    UnknownCode { code: String },
    /// The catalogue's file name is not a plain name (defence in depth: the catalogue refuses these
    /// when it is parsed).
    FileName {
        file_name: String,
        reason: &'static str,
    },
    /// The caller's cancel flag was set.
    Cancelled,
    /// The source gave more bytes than the catalogue pins.
    TooLarge { limit: u64 },
    /// The bytes' SHA-256 is not the catalogue's.
    Verify { expected: String, actual: String },
    /// The digest matched but the file is not shaped like a Bible.
    Invalid(ValidationError),
    /// Reading the SOURCE failed (a dropped connection, an unreadable path).
    Source(std::io::Error),
    /// Writing under the registry directory failed.
    Io(std::io::Error),
    /// The receipt is unreadable. Nothing was changed; see [`Registry::repair_receipt`].
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
    /// The file no longer validates, or holds more or other verses than the receipt records.
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

/// A load failure worth remembering for a given file: it will repeat until the file changes.
#[derive(Debug, Clone)]
enum Damage {
    Mismatch { expected: String, actual: String },
    Invalid(ValidationError),
}

impl Damage {
    fn of(e: &LoadError) -> Option<Damage> {
        match e {
            LoadError::Mismatch { expected, actual } => Some(Damage::Mismatch {
                expected: expected.clone(),
                actual: actual.clone(),
            }),
            LoadError::Invalid(v) => Some(Damage::Invalid(v.clone())),
            _ => None,
        }
    }

    fn to_error(&self) -> LoadError {
        match self {
            Damage::Mismatch { expected, actual } => LoadError::Mismatch {
                expected: expected.clone(),
                actual: actual.clone(),
            },
            Damage::Invalid(v) => LoadError::Invalid(v.clone()),
        }
    }
}

/// What [`Registry::recover`] did.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Recovered {
    /// Leftover staging files removed.
    pub removed: usize,
    /// Staging-looking entries left alone because they are not regular files (a symlink, a folder),
    /// or because an install in this process is using them.
    pub skipped: usize,
}

/// Counts decoded indexes alive in this registry, and the most there have been at once.
#[derive(Default)]
struct LiveCounter {
    live: AtomicUsize,
    peak: AtomicUsize,
}

/// One live decoded index. Created BEFORE the memory of the index is, dropped when the index is.
struct LiveGuard(Arc<LiveCounter>);

impl LiveGuard {
    fn new(counter: &Arc<LiveCounter>) -> LiveGuard {
        let now = counter.live.fetch_add(1, Ordering::SeqCst) + 1;
        counter.peak.fetch_max(now, Ordering::SeqCst);
        LiveGuard(Arc::clone(counter))
    }
}

impl Drop for LiveGuard {
    fn drop(&mut self) {
        self.0.live.fetch_sub(1, Ordering::SeqCst);
    }
}

/// The decoded text of one installed translation: its verses in canonical order. It dereferences
/// to `Vec<Verse>`. It counts itself in its registry from the moment decoding starts until it is
/// dropped, so a test can observe how many decoded indexes ever existed at once rather than trust
/// a counter the cache keeps about itself.
pub struct InstalledIndex {
    verses: Vec<Verse>,
    _live: LiveGuard,
}

impl InstalledIndex {
    /// Decode `bytes` (already verified against the receipt). The only way to make one, so the
    /// live count cannot be bypassed.
    fn decode(
        bytes: &[u8],
        counts: Counts,
        live: &Arc<LiveCounter>,
    ) -> Result<InstalledIndex, ValidationError> {
        let guard = LiveGuard::new(live);
        let verses = decode_verses(bytes, counts)?;
        Ok(InstalledIndex {
            verses,
            _live: guard,
        })
    }
}

impl Deref for InstalledIndex {
    type Target = Vec<Verse>;

    fn deref(&self) -> &Vec<Verse> {
        &self.verses
    }
}

impl std::fmt::Debug for InstalledIndex {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "InstalledIndex({} verses)", self.verses.len())
    }
}

struct Resident {
    code: String,
    sha256: String,
    index: Arc<InstalledIndex>,
    hits: u64,
}

/// What is known about one translation's file: its digest and stamp when it was last examined, and
/// whether it was found damaged.
struct Health {
    sha256: String,
    stamp: Option<Stamp>,
    damage: Option<Damage>,
}

struct CachedReceipts {
    stamp: Stamp,
    list: Vec<InstalledTranslation>,
}

#[derive(Default)]
struct State {
    /// Most recently used first. Never longer than the registry's capacity.
    resident: Vec<Resident>,
    /// Slots held by decodes that are running right now (outside this lock). `resident.len() +
    /// reserved` never exceeds the capacity.
    reserved: usize,
    /// Codes whose file one thread is loading right now; others wait for it instead of decoding the
    /// same file twice.
    pending: HashSet<String>,
    /// How many times each code's file has been decoded (a test seam). Keys are codes taken from
    /// receipts, so at most [`crate::catalog::MAX_ENTRIES`] of them.
    loads: HashMap<String, u64>,
    receipts: Option<CachedReceipts>,
    health: HashMap<String, Health>,
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

    /// The resident index for `code`, if any, moved to the front as the most recently used.
    fn take_hit(&mut self, code: &TranslationCode) -> Option<Arc<InstalledIndex>> {
        let pos = self.resident.iter().position(|r| r.code == code.as_str())?;
        let mut hit = self.resident.remove(pos);
        hit.hits += 1;
        let index = Arc::clone(&hit.index);
        self.resident.insert(0, hit);
        Some(index)
    }
}

/// Points in a load where a test can step in. **Test seam, not a product API.**
#[doc(hidden)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LoadStage {
    /// The receipt entry has been read and this thread owns the load; the file is not read yet.
    AfterReceipt,
    /// The file has been read, verified and validated and a slot is reserved; the decode has not
    /// started. No lock is held.
    BeforeDecode,
}

type LoadHook = Arc<dyn Fn(LoadStage) + Send + Sync>;

struct Inner {
    dir: PathBuf,
    catalogue: Catalogue,
    capacity: usize,
    /// Serialises the short critical sections that change what is installed: the final replace of
    /// an install, `remove`, `recover`, `repair_receipt`. Never held across a network or file read.
    write_lock: Mutex<()>,
    state: Mutex<State>,
    /// Signalled when a load finishes or gives up its slot.
    loaded: Condvar,
    inflight: Arc<Inflight>,
    live: Arc<LiveCounter>,
    hook: Mutex<Option<LoadHook>>,
    receipt_reads: AtomicU64,
    file_reads: AtomicU64,
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

/// Keeps the registry's write lock held. **Test seam.**
#[doc(hidden)]
pub struct WriteHold<'a>(#[allow(dead_code)] MutexGuard<'a, ()>);

/// The staged file of an install that has been downloaded, hashed and validated.
struct Staged {
    /// Removes the staging file unless the install renames it into place.
    guard: Created,
    /// Lists the staging file as in flight until the install is over.
    _inflight: InflightGuard,
    done: u64,
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
                loaded: Condvar::new(),
                inflight: Arc::new(Inflight::default()),
                live: Arc::new(LiveCounter::default()),
                hook: Mutex::new(None),
                receipt_reads: AtomicU64::new(0),
                file_reads: AtomicU64::new(0),
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

    /// The write lock, but a caller that is only queueing for it gives up as soon as its cancel
    /// flag is set instead of waiting its turn.
    fn lock_write_cancellable(
        &self,
        hooks: &InstallHooks<'_>,
    ) -> Result<MutexGuard<'_, ()>, InstallError> {
        loop {
            match self.inner.write_lock.try_lock() {
                Ok(guard) => return Ok(guard),
                Err(TryLockError::Poisoned(p)) => return Ok(p.into_inner()),
                Err(TryLockError::WouldBlock) => {
                    hooks.check_cancel()?;
                    std::thread::sleep(LOCK_POLL);
                }
            }
        }
    }

    fn fire(&self, stage: LoadStage) {
        let hook = self
            .inner
            .hook
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .clone();
        if let Some(hook) = hook {
            hook(stage);
        }
    }

    /// The receipt, from memory unless its length, modification time or inode changed since it was
    /// last read. A hit costs one `stat`; a change costs one read and parse.
    fn receipts_locked(&self, st: &mut State) -> Result<Vec<InstalledTranslation>, ReceiptError> {
        let path = receipt_path(&self.inner.dir);
        let meta = match fs::symlink_metadata(&path) {
            Ok(m) => m,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                st.receipts = None;
                return Ok(Vec::new());
            }
            Err(e) => return Err(ReceiptError::Io(e)),
        };
        if !meta.file_type().is_file() {
            st.receipts = None;
            return Err(ReceiptError::Corrupt(
                "installed.json is not a regular file".to_string(),
            ));
        }
        let stamp = Stamp::of(&meta);
        if let Some(cached) = &st.receipts {
            if cached.stamp == stamp {
                return Ok(cached.list.clone());
            }
        }
        self.inner.receipt_reads.fetch_add(1, Ordering::Relaxed);
        st.receipts = None;
        let list = read_receipts(&self.inner.dir)?;
        st.receipts = Some(CachedReceipts {
            stamp,
            list: list.clone(),
        });
        Ok(list)
    }

    /// Every translation that is installed: has a receipt entry AND a regular file of the recorded
    /// size. In code order. An unreadable or damaged receipt is an `Err` (so a screen can say so),
    /// and a missing one is simply no installs. Always reads the receipt from disk.
    pub fn installed(&self) -> Result<Vec<InstalledTranslation>, ReceiptError> {
        let dir = &self.inner.dir;
        Ok(read_receipts(dir)?
            .into_iter()
            .filter(|r| file_in_place(dir, r))
            .collect())
    }

    /// The receipt entry for `code` if it is installed: it has an entry and a regular file of the
    /// recorded size. This does not hash the file; see [`Registry::verify`].
    pub fn installed_entry(&self, code: &TranslationCode) -> Option<InstalledTranslation> {
        let rec = {
            let mut st = self.lock_state();
            self.receipts_locked(&mut st)
                .ok()?
                .into_iter()
                .find(|r| &r.code == code)?
        };
        file_in_place(&self.inner.dir, &rec).then_some(rec)
    }

    /// A handle for installed translation `code` (case-insensitive), or `None` when it is not
    /// installed. See [`Bible`]. Does file I/O (the receipt, and a `stat` of the file), never
    /// network I/O.
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
    /// digest and verse counts, validated and decoded, and becomes the most recently used. The
    /// receipt is re-read whenever it changes on disk, so a translation re-installed (by this
    /// process or another) is served from its new file, never the stale decoded copy. The returned
    /// `Arc` is a snapshot: an eviction while a caller holds it frees the memory only when the
    /// caller lets go.
    ///
    /// A file found damaged is remembered (by its length, modification time and inode) and the
    /// same answer is returned without reading it again until the file changes. If the file does
    /// not match the receipt because a re-install replaced both a moment ago, the read is retried
    /// once against the new receipt rather than reporting damage that is not there.
    ///
    /// "Changes" means its length, modification time or inode differs from when it was last looked
    /// at. A change that leaves all three alone (a same-length rewrite inside one tick of the file
    /// system's clock, or bit rot that touches no timestamp) is not noticed until the next change;
    /// but the bytes of a file are hashed at EVERY load, so what is decoded and served is always
    /// the verified file. Only a remembered verdict (the damaged-file answer, and the answer of
    /// [`Registry::verify`]) can be out of date by that much.
    pub fn index(&self, code: &TranslationCode) -> Result<Arc<InstalledIndex>, LoadError> {
        let first = self.index_once(code);
        if let Err(LoadError::Mismatch { expected, .. }) = &first {
            if self.receipt_moved_on(code, expected) {
                return self.index_once(code);
            }
        }
        first
    }

    /// Whether the receipt (read afresh) now records a different file for `code` than `sha256`.
    fn receipt_moved_on(&self, code: &TranslationCode, sha256: &str) -> bool {
        let mut st = self.lock_state();
        st.receipts = None;
        match self.receipts_locked(&mut st) {
            Ok(list) => list.iter().any(|r| &r.code == code && r.sha256 != sha256),
            Err(_) => false,
        }
    }

    fn index_once(&self, code: &TranslationCode) -> Result<Arc<InstalledIndex>, LoadError> {
        // 1. Under the state lock, briefly: the receipt, a hit, another thread's load, a remembered
        //    failure. Nothing slow happens here.
        let rec = {
            let mut st = self.lock_state();
            loop {
                let receipts = self.receipts_locked(&mut st).map_err(LoadError::Receipt)?;
                st.prune(&receipts);
                let rec = receipts
                    .iter()
                    .find(|r| &r.code == code)
                    .cloned()
                    .ok_or(LoadError::NotInstalled)?;
                if let Some(hit) = st.take_hit(code) {
                    return Ok(hit);
                }
                if st.pending.contains(code.as_str()) {
                    // Another thread is loading this very file: wait for it, then look again.
                    st = self
                        .inner
                        .loaded
                        .wait(st)
                        .unwrap_or_else(|e| e.into_inner());
                    continue;
                }
                if let Some(damage) = self.known_damage(&st, &rec) {
                    return Err(damage.to_error());
                }
                st.pending.insert(code.to_string());
                break rec;
            }
        };
        let mut ticket = LoadTicket {
            registry: self,
            code: code.to_string(),
            reserved: false,
        };
        self.fire(LoadStage::AfterReceipt);

        // 2. No lock: read the file, check its digest, and validate its shape with a streaming pass
        //    that allocates no index. A bad file fails HERE, before anything is evicted.
        let counts = Counts {
            ot: rec.verses_ot,
            nt: rec.verses_nt,
        };
        let stamp = self.data_stamp(&rec);
        let bytes = match self.load_checks(&rec) {
            Ok(bytes) => bytes,
            Err(e) => {
                self.record_health(&rec, stamp, Err(&e));
                return Err(e);
            }
        };

        // 3. Under the lock, briefly: reserve a slot, evicting the least recently used index(es) so
        //    that residents plus decodes in flight stay within the capacity.
        {
            let mut st = self.lock_state();
            loop {
                if st.resident.len() + st.reserved < self.inner.capacity {
                    break;
                }
                if st.resident.pop().is_some() {
                    continue;
                }
                // Every slot is another thread's decode in flight: wait for one to finish.
                st = self
                    .inner
                    .loaded
                    .wait(st)
                    .unwrap_or_else(|e| e.into_inner());
            }
            st.reserved += 1;
            ticket.reserved = true;
        }

        // 4. No lock: decode. The index counts itself live from its first byte of memory.
        self.fire(LoadStage::BeforeDecode);
        let decoded = InstalledIndex::decode(&bytes, counts, &self.inner.live);
        drop(bytes);
        let index = Arc::new(decoded.map_err(LoadError::Invalid)?);

        // 5. Under the lock, briefly: the slot becomes a resident entry.
        {
            let mut st = self.lock_state();
            st.reserved -= 1;
            ticket.reserved = false;
            *st.loads.entry(code.to_string()).or_insert(0) += 1;
            st.health.insert(
                code.to_string(),
                Health {
                    sha256: rec.sha256.clone(),
                    stamp,
                    damage: None,
                },
            );
            st.resident.insert(
                0,
                Resident {
                    code: code.to_string(),
                    sha256: rec.sha256.clone(),
                    index: Arc::clone(&index),
                    hits: 0,
                },
            );
        }
        // `ticket` drops here: the code is no longer pending and waiters are woken.
        Ok(index)
    }

    /// What the file for `rec` looks like right now (its length, modification time and inode).
    fn data_stamp(&self, rec: &InstalledTranslation) -> Option<Stamp> {
        fs::symlink_metadata(self.inner.dir.join(&rec.file_name))
            .ok()
            .map(|m| Stamp::of(&m))
    }

    /// A remembered damage for exactly this file (same digest, same stamp), if there is one.
    fn known_damage(&self, st: &State, rec: &InstalledTranslation) -> Option<Damage> {
        let health = st.health.get(rec.code.as_str())?;
        let damage = health.damage.as_ref()?;
        if health.sha256 != rec.sha256 {
            return None;
        }
        let now = self.data_stamp(rec)?;
        (health.stamp == Some(now)).then(|| damage.clone())
    }

    /// Remember how `rec`'s file checked out, as of `stamp`. Only a damaged file or a good one is
    /// remembered; a missing file or an I/O error is cheap to find out again.
    fn record_health(
        &self,
        rec: &InstalledTranslation,
        stamp: Option<Stamp>,
        result: Result<(), &LoadError>,
    ) {
        let damage = match result {
            Ok(()) => None,
            Err(e) => match Damage::of(e) {
                Some(d) => Some(d),
                None => return,
            },
        };
        if stamp.is_none() {
            return;
        }
        self.lock_state().health.insert(
            rec.code.to_string(),
            Health {
                sha256: rec.sha256.clone(),
                stamp,
                damage,
            },
        );
    }

    /// Check that installed translation `code` is intact and would load: it has a receipt entry,
    /// its file is a regular file, its SHA-256 and size are the receipt's, and it passes the same
    /// validation a load applies (including the verse counts the install recorded). Decodes
    /// nothing and touches no cache, so it can never evict a resident index. The answer for a given
    /// file is remembered until its length, modification time or inode changes, so asking again
    /// costs a `stat`, not a hash.
    pub fn verify(&self, code: &TranslationCode) -> Result<(), LoadError> {
        let rec = {
            let mut st = self.lock_state();
            self.receipts_locked(&mut st)
                .map_err(LoadError::Receipt)?
                .into_iter()
                .find(|r| &r.code == code)
                .ok_or(LoadError::NotInstalled)?
        };
        let stamp = self.data_stamp(&rec);
        if let Some(now) = stamp {
            let st = self.lock_state();
            if let Some(h) = st.health.get(rec.code.as_str()) {
                if h.sha256 == rec.sha256 && h.stamp == Some(now) {
                    return h.damage.as_ref().map_or(Ok(()), |d| Err(d.to_error()));
                }
            }
        }
        let result = self.load_checks(&rec).map(drop);
        self.record_health(&rec, stamp, result.as_ref().map(|_| ()));
        result
    }

    /// The file's bytes after every check a load applies: the digest and size, then a streaming
    /// validation against the verse counts the install recorded.
    fn load_checks(&self, rec: &InstalledTranslation) -> Result<Vec<u8>, LoadError> {
        let bytes = self.read_verified(rec)?;
        validate_asset(
            bytes.as_slice(),
            Counts {
                ot: rec.verses_ot,
                nt: rec.verses_nt,
            },
        )
        .map_err(LoadError::Invalid)?;
        Ok(bytes)
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
        self.inner.file_reads.fetch_add(1, Ordering::Relaxed);
        let mut bytes =
            Vec::with_capacity(rec.size_bytes.min(crate::catalog::MAX_ASSET_BYTES) as usize);
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
    ///
    /// Reading `source` (a download, perhaps) happens before the write lock is taken, so a stalled
    /// source blocks nothing else; only the final replace is serialised. If the receipt is
    /// unreadable this fails with [`InstallError::Receipt`] and changes nothing.
    pub fn install_from_reader(
        &self,
        code: &str,
        source: &mut dyn Read,
        installed_at: u64,
        hooks: &InstallHooks<'_>,
    ) -> Result<InstalledTranslation, InstallError> {
        let entry = self
            .inner
            .catalogue
            .find(code)
            .ok_or_else(|| InstallError::UnknownCode {
                code: code.to_string(),
            })?;
        validate_file_name(&entry.file_name).map_err(|reason| InstallError::FileName {
            file_name: entry.file_name.clone(),
            reason,
        })?;
        hooks.check_cancel()?;
        fs::create_dir_all(&self.inner.dir).map_err(InstallError::Io)?;
        // An unreadable receipt is refused BEFORE a byte is downloaded: the commit would refuse it
        // anyway, and a download that can only be thrown away is a waste of the user's data.
        receipts_for_update(&self.inner.dir)?;
        // Leftovers of an install that was killed (never counted as installed) go first. Best
        // effort, and only if nobody else is changing what is installed right now: waiting here
        // would make an install that is merely starting queue, uncancellably, behind another
        // writer. A cleanup that is skipped is done by the next install or by `recover`.
        self.recover_if_idle();

        let staged = self.stage(entry, source, hooks)?;
        let _writer = self.lock_write_cancellable(hooks)?;
        self.commit(entry, staged, installed_at, hooks)
    }

    /// Stream `source` into a staging file, hashing it, then check the digest and validate the
    /// file. No lock is held.
    fn stage(
        &self,
        entry: &CatalogEntry,
        source: &mut dyn Read,
        hooks: &InstallHooks<'_>,
    ) -> Result<Staged, InstallError> {
        let total = entry.size_bytes;
        let (path, mut file, inflight) =
            Inflight::create_staging(&self.inner.inflight, &self.inner.dir, &entry.file_name)
                .map_err(InstallError::Io)?;
        let guard = Created::new(path);

        // 1. Stream into the staging file, hashing, capped at the pinned size.
        let mut hasher = Sha256::new();
        let mut buf = vec![0u8; CHUNK_BYTES];
        let mut done: u64 = 0;
        loop {
            hooks.check_cancel()?;
            let n = match source.read(&mut buf) {
                Ok(n) => n,
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                // A read that failed (a timeout, say) after the caller asked to cancel is the
                // cancel, not a network failure.
                Err(_) if hooks.is_cancelled() => return Err(InstallError::Cancelled),
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
        Ok(Staged {
            guard,
            _inflight: inflight,
            done,
        })
    }

    /// Put a staged file in place. The caller holds the write lock. The new receipt is fully
    /// written first, so what remains is two renames.
    fn commit(
        &self,
        entry: &CatalogEntry,
        mut staged: Staged,
        installed_at: u64,
        hooks: &InstallHooks<'_>,
    ) -> Result<InstalledTranslation, InstallError> {
        let dir = &self.inner.dir;
        let total = entry.size_bytes;
        hooks.check_cancel()?;
        let previous = receipts_for_update(dir)?;
        let had_before = previous.iter().any(|r| r.code == entry.code);
        let record = InstalledTranslation {
            code: entry.code.clone(),
            file_name: entry.file_name.clone(),
            sha256: entry.sha256.clone(),
            size_bytes: total,
            verses_ot: entry.verses_ot,
            verses_nt: entry.verses_nt,
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
        hooks.report(Phase::Installing, staged.done, total);
        hooks.check_cancel()?;
        let final_path = dir.join(&entry.file_name);
        fs::rename(&staged.guard.path, &final_path).map_err(InstallError::Io)?;
        staged.guard.disarm();
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
        self.forget_after_write(&next, Some(entry.code.as_str()));
        Ok(record)
    }

    /// After the receipt changed: drop the cached receipt, the remembered health of `code`, and
    /// every resident index that is no longer what `next` says is installed.
    fn forget_after_write(&self, next: &[InstalledTranslation], code: Option<&str>) {
        let mut st = self.lock_state();
        st.receipts = None;
        match code {
            Some(c) => {
                st.health.remove(c);
            }
            None => st.health.clear(),
        }
        st.prune(next);
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
    /// A removed translation is also dropped from memory. If the receipt is unreadable this fails
    /// with [`InstallError::Receipt`] and changes nothing.
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
        self.forget_after_write(&next, Some(code.as_str()));

        match fs::remove_file(dir.join(&record.file_name)) {
            Ok(()) => Ok(true),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(true),
            Err(e) => Err(InstallError::Io(e)),
        }
    }

    /// Rebuild the receipt from the files on disk, for when it is unreadable (installing and
    /// removing refuse to run over it, so no other translation is forgotten). A catalogue entry
    /// whose file is in the directory as a regular file of the pinned size with the pinned SHA-256
    /// is recorded as installed (its verse counts from the entry, `installed_at` as given); every
    /// other file is left exactly where it is and is not recorded. The old receipt is replaced
    /// atomically. Returns what it recorded.
    pub fn repair_receipt(
        &self,
        installed_at: u64,
    ) -> Result<Vec<InstalledTranslation>, InstallError> {
        let _writer = self.lock_write();
        let dir = &self.inner.dir;
        let mut found: Vec<InstalledTranslation> = Vec::new();
        for entry in self.inner.catalogue.translations() {
            let path = dir.join(&entry.file_name);
            let Ok(meta) = fs::symlink_metadata(&path) else {
                continue;
            };
            if !meta.file_type().is_file() || meta.len() != entry.size_bytes {
                continue;
            }
            if sha256_file(&path).is_ok_and(|digest| digest == entry.sha256) {
                found.push(InstalledTranslation {
                    code: entry.code.clone(),
                    file_name: entry.file_name.clone(),
                    sha256: entry.sha256.clone(),
                    size_bytes: entry.size_bytes,
                    verses_ot: entry.verses_ot,
                    verses_nt: entry.verses_nt,
                    installed_at,
                    catalogue_schema: self.inner.catalogue.schema(),
                });
            }
        }
        found.sort_by(|a, b| a.code.as_str().cmp(b.code.as_str()));
        fs::create_dir_all(dir).map_err(InstallError::Io)?;
        let mut receipt_tmp = self.write_receipt_temp(&found)?;
        fs::rename(&receipt_tmp.path, receipt_path(dir)).map_err(InstallError::Io)?;
        receipt_tmp.disarm();
        sync_dir(dir);
        self.forget_after_write(&found, None);
        Ok(found)
    }

    /// Clean up after an install that was killed: remove leftover staging files (`*.tsv.gz.part`)
    /// and leftover temp receipts. Only regular files with those reserved names are removed; a
    /// symlink or a folder with such a name is left alone and counted as skipped, and so is the
    /// staging file of an install running in THIS process right now. Does nothing if the directory
    /// does not exist.
    ///
    /// **Safe only with one writer process.** It cannot see another process's in-flight staging
    /// file and would delete it (that install then fails, closed). Installing runs it first (when
    /// the write lock is free), so the same holds for every install.
    pub fn recover(&self) -> Result<Recovered, InstallError> {
        let _writer = self.lock_write();
        self.recover_locked()
    }

    /// [`Registry::recover`] if the write lock is free right now, and nothing at all if it is not.
    fn recover_if_idle(&self) {
        let _writer = match self.inner.write_lock.try_lock() {
            Ok(guard) => guard,
            Err(TryLockError::Poisoned(p)) => p.into_inner(),
            Err(TryLockError::WouldBlock) => return,
        };
        let _ = self.recover_locked();
    }

    /// The body of [`Registry::recover`]; the caller holds the write lock.
    fn recover_locked(&self) -> Result<Recovered, InstallError> {
        let entries = match fs::read_dir(&self.inner.dir) {
            Ok(rd) => rd,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Recovered::default()),
            Err(e) => return Err(InstallError::Io(e)),
        };
        // Held for the whole scan: no install can create a staging file (and so none can be
        // missed) while files are being deleted.
        let in_flight = self.inner.inflight.lock();
        let mut report = Recovered::default();
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if !is_staging_name(&name) {
                continue;
            }
            // `DirEntry::file_type` does not follow symlinks.
            let regular = entry.file_type().is_ok_and(|t| t.is_file());
            if regular
                && !in_flight.contains(&entry.path())
                && fs::remove_file(entry.path()).is_ok()
            {
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

    /// **Test seam.** The most decoded indexes this registry has had alive at once, counting an
    /// index from the moment its decode starts until it is dropped (so it includes one a caller is
    /// still holding after eviction). Observed by the index itself, not computed by the cache.
    #[doc(hidden)]
    pub fn peak_live_indexes(&self) -> usize {
        self.inner.live.peak.load(Ordering::SeqCst)
    }

    /// **Test seam.** How many decoded indexes of this registry are alive right now.
    #[doc(hidden)]
    pub fn live_indexes(&self) -> usize {
        self.inner.live.live.load(Ordering::SeqCst)
    }

    /// **Test seam.** How many times `code`'s file has been decoded by this registry.
    #[doc(hidden)]
    pub fn loads_for(&self, code: &str) -> u64 {
        self.lock_state().loads.get(code).copied().unwrap_or(0)
    }

    /// **Test seam.** How many times the receipt has actually been read and parsed.
    #[doc(hidden)]
    pub fn receipt_reads(&self) -> u64 {
        self.inner.receipt_reads.load(Ordering::Relaxed)
    }

    /// **Test seam.** How many times an installed file has actually been read from disk.
    #[doc(hidden)]
    pub fn file_reads(&self) -> u64 {
        self.inner.file_reads.load(Ordering::Relaxed)
    }

    /// **Test seam.** Holds the write lock until the returned value is dropped.
    #[doc(hidden)]
    pub fn hold_writes_for_tests(&self) -> WriteHold<'_> {
        WriteHold(self.lock_write())
    }

    /// **Test seam.** Calls `hook` at each [`LoadStage`] of every load, with no lock held.
    #[doc(hidden)]
    pub fn set_load_hook_for_tests(&self, hook: Option<LoadHook>) {
        *self.inner.hook.lock().unwrap_or_else(|e| e.into_inner()) = hook;
    }
}

/// The receipt to build the next one from. An unreadable receipt is an error here, never an empty
/// list: treating it as empty would forget every other install.
fn receipts_for_update(dir: &Path) -> Result<Vec<InstalledTranslation>, InstallError> {
    read_receipts(dir).map_err(InstallError::Receipt)
}

/// Marks a code as being loaded by this thread and, if it holds one, gives its slot back when it
/// goes out of scope (including by an early return or a panic), waking threads that wait.
struct LoadTicket<'a> {
    registry: &'a Registry,
    code: String,
    reserved: bool,
}

impl Drop for LoadTicket<'_> {
    fn drop(&mut self) {
        let mut st = self.registry.lock_state();
        st.pending.remove(&self.code);
        if self.reserved {
            st.reserved -= 1;
        }
        drop(st);
        self.registry.inner.loaded.notify_all();
    }
}
