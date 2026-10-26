//! Where the loopback endpoint descriptor lives, how it is read, and how a crashed publisher's
//! leftovers are swept (17tnw2b9agb).
//!
//! The descriptor is a small JSON file the output window (the host) publishes so the operator shell on
//! the same machine can find it and authenticate: loopback address, certificate pin, device name and a
//! BEARER TOKEN. Host and operator both use this module, so they cannot disagree about the directory,
//! the file names or the checks.
//!
//! # The threat
//!
//! On Linux `std::env::temp_dir()` is the shared, world-writable `/tmp` and `XDG_RUNTIME_DIR` was never
//! consulted. Another local account could create the descriptor's name (or the host's staging names)
//! first, so the host's rename failed and nothing was published; or plant a FIFO there, which blocks a
//! plain `open(2)` for read forever, hanging the operator's startup (the reader runs on the Tauri main
//! thread); or plant a symlink or a file of its own.
//!
//! # Where the descriptor goes (Unix)
//!
//! The first of these that is *private to the current user* ([`verify_private_dir`]):
//!
//! 1. `$XDG_RUNTIME_DIR` (absolute, and a directory the login system made `0700` for the user);
//! 2. the temp directory itself, when it is already private (this is macOS, where `$TMPDIR` is a
//!    per-user `0700` directory, so macOS keeps its location unchanged);
//! 3. otherwise a `selahcue-UID` subdirectory of the temp directory, created `0700` ([`prepare_dir`])
//!    and VERIFIED again before every use (the Linux `/tmp` shape).
//!
//! "Private" means: `lstat` says a real directory (a symlink is refused, never followed), owned by the
//! effective uid, with no group or other permission bits. A directory that exists with the wrong owner
//! or mode is not used, not followed and not repaired; the caller fails closed (nothing published,
//! nothing read). `mkdir` is atomic, so whoever creates the fallback name, the check that follows
//! decides; in the sticky shared temp directory another account can neither rename nor remove an entry
//! we own, and cannot add entries to a `0700` directory that is ours. What it CAN do is create the
//! fallback name first (then we refuse it and local auto-connect is lost: a denial of service, not a
//! disclosure or a redirect). `XDG_RUNTIME_DIR` is the real fix wherever it exists.
//!
//! There is deliberately NO fallback to the old shared `/tmp/selahcue-operator-endpoint.json`: that is
//! the attack. An old host and a new operator (or the reverse) simply do not find each other on Linux
//! and the operator runs its stand-alone demo until connected by hand.
//!
//! # Windows
//!
//! The temp directory is already per-user (`%TEMP%`) and keeps the ACL it inherits; there is no owner or
//! mode to check, so [`verify_private_dir`] only checks that it is a directory. The reader still
//! refuses anything that is not a regular file and bounds the size.
//!
//! # Reading ([`read_descriptor_as`])
//!
//! The parent directory is verified, then the file is opened with `O_NOFOLLOW | O_NONBLOCK`, and every
//! remaining check is made on the OPEN descriptor (`fstat`), never on the path: a regular file, owned by
//! the current user, mode exactly `0600`, no larger than the cap. A FIFO opened `O_NONBLOCK` for read
//! returns at once and is refused on its type, so no input can make the call wait. The read itself is
//! capped.
//!
//! # Sweeping ([`sweep_stale_staging_with`])
//!
//! A host killed between creating its staging file and renaming it leaves
//! `.selahcue-endpoint.PID.N.tmp` (mode `0600`, a dead token). The next publish removes such a file
//! when it is a regular file of ours (`lstat`, never a symlink), its name parses exactly, and either its
//! process is gone or it is older than [`STALE_AFTER`]. A fresh file of a live process is an in-flight
//! publish and is left alone. At most [`MAX_SWEEP_ENTRIES`] directory entries are examined.
//!
//! Every error here is label-only: it names a condition, never the descriptor's contents.

use std::ffi::OsString;
use std::fmt;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};

/// The descriptor's file name, shared by the host (publisher) and the operator (reader).
pub const DESCRIPTOR_FILE_NAME: &str = "selahcue-operator-endpoint.json";

/// Every staging file is `STAGING_PREFIX.PID.N.STAGING_SUFFIX`.
pub const STAGING_PREFIX: &str = ".selahcue-endpoint";
/// See [`STAGING_PREFIX`].
pub const STAGING_SUFFIX: &str = ".tmp";

/// A staging file of a live process is left alone until it is this old. A real publish takes
/// microseconds, so a file this old is a leftover even if its pid has since been recycled.
pub const STALE_AFTER: Duration = Duration::from_secs(60);

/// Directory entries one sweep examines, however many the directory holds. `XDG_RUNTIME_DIR` is shared
/// with the rest of the login session, so the cap bounds the work, not just the memory.
pub const MAX_SWEEP_ENTRIES: usize = 4096;

/// Prefix of the per-user fallback subdirectory (`selahcue-UID`).
#[cfg(unix)]
const FALLBACK_DIR_PREFIX: &str = "selahcue-";

/// Everything the directory choice depends on, injected so every branch (Linux's `/tmp`, a macOS
/// `$TMPDIR`, a foreign owner) is testable on any machine.
#[derive(Clone, Debug)]
pub struct DirEnv {
    /// `$XDG_RUNTIME_DIR`, if set.
    pub xdg_runtime_dir: Option<OsString>,
    /// `std::env::temp_dir()`.
    pub temp_dir: PathBuf,
    /// The effective uid. Meaningless (0) on Windows.
    pub uid: u32,
}

impl DirEnv {
    /// This process's real environment.
    pub fn current() -> Self {
        #[cfg_attr(not(unix), allow(unused_mut))]
        let mut temp_dir = std::env::temp_dir();
        #[cfg(unix)]
        if temp_dir.as_os_str().is_empty() {
            // `TMPDIR=` (set but empty): treat it as unset, the way the shell tooling does.
            temp_dir = PathBuf::from("/tmp");
        }
        DirEnv {
            xdg_runtime_dir: std::env::var_os("XDG_RUNTIME_DIR"),
            temp_dir,
            uid: current_uid(),
        }
    }
}

/// The effective uid of this process (0 on Windows, where nothing uses it).
pub fn current_uid() -> u32 {
    #[cfg(unix)]
    {
        rustix::process::geteuid().as_raw()
    }
    #[cfg(not(unix))]
    {
        0
    }
}

/// Why a directory is not usable as the descriptor's home.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DirError {
    /// It does not exist.
    Missing,
    /// It is a symbolic link (never followed).
    Symlink,
    /// It exists and is not a directory.
    NotDirectory,
    /// It is owned by another user.
    WrongOwner,
    /// Its mode gives group or other users some access.
    TooOpen,
    /// It could not be inspected.
    Unreadable,
    /// It did not exist and could not be created.
    CreateFailed,
}

impl fmt::Display for DirError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            DirError::Missing => "it does not exist",
            DirError::Symlink => "it is a symbolic link",
            DirError::NotDirectory => "it is not a directory",
            DirError::WrongOwner => "it is owned by another user",
            DirError::TooOpen => "other users have access to it (it must be owner-only)",
            DirError::Unreadable => "it could not be inspected",
            DirError::CreateFailed => "it could not be created",
        })
    }
}

impl std::error::Error for DirError {}

/// Why a descriptor was not read. [`ReadError::Absent`] is the ordinary "no host is running" case and
/// not worth a log line; every other variant is a refusal.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ReadError {
    /// Nothing there (or its directory does not exist yet).
    Absent,
    /// The directory it sits in is not private to this user.
    Dir(DirError),
    /// The path is a symbolic link (never followed).
    Symlink,
    /// Not a regular file: a FIFO, a device, a socket, a directory.
    NotRegularFile,
    /// Owned by another user.
    WrongOwner,
    /// Mode other than `0600` (the mode found).
    WrongMode(u32),
    /// Larger than the cap.
    TooLarge,
    /// Could not be opened or read, or is not text.
    Unreadable,
}

impl fmt::Display for ReadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ReadError::Absent => f.write_str("there is no descriptor"),
            ReadError::Dir(why) => write!(f, "its directory is not private to this user: {why}"),
            ReadError::Symlink => f.write_str("it is a symbolic link"),
            ReadError::NotRegularFile => f.write_str("it is not a regular file"),
            ReadError::WrongOwner => f.write_str("it is owned by another user"),
            ReadError::WrongMode(mode) => write!(f, "it is not mode 0600 (found {mode:o})"),
            ReadError::TooLarge => f.write_str("it is larger than the limit"),
            ReadError::Unreadable => f.write_str("it could not be read"),
        }
    }
}

impl std::error::Error for ReadError {}

/// The directory the descriptor lives in for `env`. Pure resolution: it creates nothing, so the
/// operator and any shell tooling can ask without side effects. See the module docs for the rule.
pub fn resolve_dir(env: &DirEnv) -> PathBuf {
    #[cfg(unix)]
    {
        if let Some(xdg) = env.xdg_runtime_dir.as_deref() {
            let xdg = Path::new(xdg);
            if xdg.is_absolute() && verify_private_dir(xdg, env.uid).is_ok() {
                return xdg.to_path_buf();
            }
        }
        if verify_private_dir(&env.temp_dir, env.uid).is_ok() {
            return env.temp_dir.clone();
        }
        env.temp_dir
            .join(format!("{FALLBACK_DIR_PREFIX}{}", env.uid))
    }
    #[cfg(not(unix))]
    {
        env.temp_dir.clone()
    }
}

/// The descriptor's path in this process's real environment (host and operator both call this).
pub fn descriptor_path() -> PathBuf {
    resolve_dir(&DirEnv::current()).join(DESCRIPTOR_FILE_NAME)
}

/// [`resolve_dir`], then make sure the directory exists (creating the per-user fallback `0700` if it
/// does not) and is private to `env.uid`. The publisher calls this; on any error it publishes nothing.
pub fn prepare_dir(env: &DirEnv) -> Result<PathBuf, DirError> {
    let dir = resolve_dir(env);
    if verify_private_dir(&dir, env.uid) == Err(DirError::Missing) {
        create_private_dir(&dir)?;
    }
    verify_private_dir(&dir, env.uid)?;
    Ok(dir)
}

#[cfg(unix)]
fn create_private_dir(dir: &Path) -> Result<(), DirError> {
    use std::os::unix::fs::DirBuilderExt;
    match std::fs::DirBuilder::new().mode(0o700).create(dir) {
        Ok(()) => Ok(()),
        // Someone else won the race to create it. Whether it is acceptable is the verify's call.
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(()),
        Err(_) => Err(DirError::CreateFailed),
    }
}

#[cfg(not(unix))]
fn create_private_dir(dir: &Path) -> Result<(), DirError> {
    std::fs::create_dir(dir).map_err(|_| DirError::CreateFailed)
}

/// Is `dir` a real directory that only `uid` can use? Judged with `lstat`, so a symlink (even to a
/// perfectly good private directory) is refused rather than followed. On Windows there is no owner or
/// mode to judge, and this only checks that it is a directory.
pub fn verify_private_dir(dir: &Path, uid: u32) -> Result<(), DirError> {
    let meta = std::fs::symlink_metadata(dir).map_err(|e| match e.kind() {
        std::io::ErrorKind::NotFound => DirError::Missing,
        _ => DirError::Unreadable,
    })?;
    let kind = meta.file_type();
    if kind.is_symlink() {
        return Err(DirError::Symlink);
    }
    if !kind.is_dir() {
        return Err(DirError::NotDirectory);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if meta.uid() != uid {
            return Err(DirError::WrongOwner);
        }
        if meta.mode() & 0o077 != 0 {
            return Err(DirError::TooOpen);
        }
    }
    #[cfg(not(unix))]
    let _ = uid;
    Ok(())
}

/// Read the descriptor at `path` as user `uid` (the current user, in production; injected so a test can
/// stand in for "a file owned by another user"). At most `max_len` bytes. See the module docs.
pub fn read_descriptor_as(path: &Path, max_len: u64, uid: u32) -> Result<String, ReadError> {
    let parent = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    match verify_private_dir(parent, uid) {
        Ok(()) => {}
        Err(DirError::Missing) => return Err(ReadError::Absent),
        Err(why) => return Err(ReadError::Dir(why)),
    }
    read_file_as(path, max_len, uid)
}

/// The file half of [`read_descriptor_as`]: open without blocking or following, then judge the open
/// descriptor. It does NOT look at the directory (the caller has, or [`read_descriptor_as`] does); it
/// is public so the owner check can be exercised on its own, since a directory check in front would
/// otherwise always stop a foreign uid first.
pub fn read_file_as(path: &Path, max_len: u64, uid: u32) -> Result<String, ReadError> {
    use std::io::Read;

    let file = open_without_blocking_or_following(path)?;
    // From here on, only the OPEN descriptor is consulted (`fstat`), never the path again.
    let meta = file.metadata().map_err(|_| ReadError::Unreadable)?;
    if !meta.file_type().is_file() {
        return Err(ReadError::NotRegularFile);
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if meta.uid() != uid {
            return Err(ReadError::WrongOwner);
        }
        let mode = meta.mode() & 0o7777;
        if mode != 0o600 {
            return Err(ReadError::WrongMode(mode));
        }
    }
    #[cfg(not(unix))]
    let _ = uid;
    if meta.len() > max_len {
        return Err(ReadError::TooLarge);
    }
    let mut data = String::new();
    file.take(max_len)
        .read_to_string(&mut data)
        .map_err(|_| ReadError::Unreadable)?;
    Ok(data)
}

#[cfg(unix)]
fn open_without_blocking_or_following(path: &Path) -> Result<std::fs::File, ReadError> {
    use rustix::fs::OFlags;
    use rustix::io::Errno;
    use std::os::unix::fs::OpenOptionsExt;

    // `O_NONBLOCK`: opening a FIFO for read returns at once instead of waiting for a writer.
    // `O_NOFOLLOW`: a symlink in the last component fails with `ELOOP` instead of being followed.
    let flags = (OFlags::NOFOLLOW | OFlags::NONBLOCK).bits() as i32;
    std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(flags)
        .open(path)
        .map_err(|e| {
            if e.raw_os_error() == Some(Errno::LOOP.raw_os_error()) {
                ReadError::Symlink
            } else if e.kind() == std::io::ErrorKind::NotFound {
                ReadError::Absent
            } else {
                ReadError::Unreadable
            }
        })
}

#[cfg(not(unix))]
fn open_without_blocking_or_following(path: &Path) -> Result<std::fs::File, ReadError> {
    std::fs::File::open(path).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            ReadError::Absent
        } else {
            ReadError::Unreadable
        }
    })
}

/// The name of a staging file: `.selahcue-endpoint.PID.N.tmp`.
pub fn staging_file_name(pid: u32, n: u64) -> String {
    format!("{STAGING_PREFIX}.{pid}.{n}{STAGING_SUFFIX}")
}

/// The inverse of [`staging_file_name`]; `None` for anything that is not exactly that shape.
pub fn parse_staging_name(name: &str) -> Option<(u32, u64)> {
    let rest = name
        .strip_prefix(STAGING_PREFIX)?
        .strip_prefix('.')?
        .strip_suffix(STAGING_SUFFIX)?;
    let (pid, n) = rest.split_once('.')?;
    let digits = |s: &str| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit());
    if !digits(pid) || !digits(n) {
        return None;
    }
    Some((pid.parse().ok()?, n.parse().ok()?))
}

/// Is there a process with this pid? `kill(pid, 0)`: "no such process" is the only answer that means
/// no (permission denied means it exists and is someone else's). Always `true` on Windows, where the
/// age rule alone decides.
pub fn pid_is_alive(pid: u32) -> bool {
    #[cfg(unix)]
    {
        let Some(pid) = i32::try_from(pid)
            .ok()
            .and_then(rustix::process::Pid::from_raw)
        else {
            return false;
        };
        match rustix::process::test_kill_process(pid) {
            Ok(()) => true,
            Err(e) => e != rustix::io::Errno::SRCH,
        }
    }
    #[cfg(not(unix))]
    {
        let _ = pid;
        true
    }
}

/// Remove the staging files a crashed publisher left in `dir`: the real clock, the real liveness check
/// and [`MAX_SWEEP_ENTRIES`]. Returns how many were removed.
pub fn sweep_stale_staging(dir: &Path, uid: u32) -> usize {
    sweep_stale_staging_with(
        dir,
        uid,
        SystemTime::now(),
        &pid_is_alive,
        MAX_SWEEP_ENTRIES,
    )
}

/// [`sweep_stale_staging`] with the clock, the liveness check and the entry cap injected.
///
/// Only a regular file (`lstat`: a symlink or a directory is left alone, and nothing is followed),
/// owned by `uid`, whose name parses as a staging name, and whose process is gone (`alive` says no) or
/// that is at least [`STALE_AFTER`] old.
pub fn sweep_stale_staging_with(
    dir: &Path,
    uid: u32,
    now: SystemTime,
    alive: &dyn Fn(u32) -> bool,
    max_entries: usize,
) -> usize {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return 0;
    };
    let mut removed = 0;
    for entry in entries.take(max_entries) {
        let Ok(entry) = entry else { continue };
        let file_name = entry.file_name();
        let Some((pid, _)) = file_name.to_str().and_then(parse_staging_name) else {
            continue;
        };
        let path = entry.path();
        let Ok(meta) = std::fs::symlink_metadata(&path) else {
            continue;
        };
        if !meta.file_type().is_file() || !owned_by(&meta, uid) {
            continue;
        }
        let old = meta
            .modified()
            .ok()
            .and_then(|modified| now.duration_since(modified).ok())
            .is_some_and(|age| age >= STALE_AFTER);
        if alive(pid) && !old {
            continue; // an in-flight publish
        }
        if std::fs::remove_file(&path).is_ok() {
            removed += 1;
        }
    }
    removed
}

fn owned_by(meta: &std::fs::Metadata, uid: u32) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        meta.uid() == uid
    }
    #[cfg(not(unix))]
    {
        let _ = (meta, uid);
        true
    }
}
