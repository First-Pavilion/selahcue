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
//! 3. a `0700` `selahcue` directory under `$XDG_STATE_HOME` (absolute) or `$HOME/.local/state`: the
//!    user's own home, where no other account can create the name at all. Missing components are
//!    created `0700` (only the ones we create; an existing one is never changed), and the step is
//!    skipped unless the nearest existing parent is a real directory owned by this user and not
//!    writable by group or other;
//! 4. only when there is no usable home (unset or relative `HOME`, an unusable parent, a `selahcue`
//!    entry that is not a private directory): a `selahcue-UID` subdirectory of the temp directory,
//!    created `0700` and VERIFIED again before every use (the shared-`/tmp` last resort).
//!
//! "Private" means: `lstat` says a real directory (a symlink is refused, never followed; trailing
//! slashes are stripped first, because `lstat("link/")` follows the link), owned by the effective uid,
//! with no group or other permission bits. A directory that exists with the wrong owner or mode is not
//! used, not followed and not repaired; a step whose directory fails the check is skipped, and when
//! the last resort fails too the caller fails closed (nothing published, nothing read).
//!
//! The resolution is a pure function of the environment and the file system, so the host, the
//! operator and the shell tooling (`scripts/endpoint_path.py`) agree as long as they see the same
//! `XDG_RUNTIME_DIR`, `XDG_STATE_HOME`, `HOME` and `TMPDIR`.
//!
//! Notes on the home step (3):
//!
//! - A descriptor can outlive its host there (a crash leaves it; a tmpfs would not). The host removes
//!   it on a clean exit ([`remove_descriptor`]), the next publish overwrites it, the sweep removes
//!   leftover staging files, and a dead token fails the connect, which falls back to the manual path.
//!   The pinned certificate in the descriptor means a stranger who now owns that port cannot be sent
//!   the token: the TLS handshake fails first.
//! - `HOME` and `XDG_STATE_HOME` come from the environment, which the process controls only because
//!   it already runs as the user. A process started with a borrowed `HOME` (e.g. `sudo` without
//!   resetting it) fails the owner check on the parent and skips the step.
//! - On a home shared between machines (NFS) two machines running a host would overwrite each
//!   other's descriptor; a graphical login normally has `XDG_RUNTIME_DIR` (step 1) so the home step is
//!   for headless and ssh sessions. Modes are only as good as the file system enforcing them.
//! - Home directories created with a group-writable mode (`umask 002`) skip the step and fall to the
//!   last resort.
//!
//! In the last resort the name lives in a directory other accounts can write to. `mkdir` is atomic, so
//! whoever creates it, the check that follows decides; in the sticky shared temp directory another
//! account can neither rename nor remove an entry we own, and cannot add entries to a `0700` directory
//! that is ours. What it CAN do is create the name first (then we refuse it and local auto-connect is
//! lost: a denial of service, not a disclosure or a redirect). Where the parent is NOT sticky the
//! backstop is the file rules, not the directory: a descriptor is only trusted when it is a regular
//! file of ours at mode `0600` in a directory of ours, so a swapped entry can cost the connection but
//! cannot disclose the token or redirect the operator.
//!
//! There is deliberately NO fallback to the old shared `/tmp/selahcue-operator-endpoint.json`: that is
//! the attack. An old host and a new operator (or the reverse) simply do not find each other on Linux
//! and the operator runs its stand-alone demo until connected by hand.
//!
//! # Windows
//!
//! The temp directory is already per-user (`%TEMP%`) and keeps the ACL it inherits; there is no owner or
//! mode to check, so [`verify_private_dir`] only checks that it is a directory (a symlink or junction
//! is followed, as before this module existed: only Unix refuses one). The reader still refuses
//! anything that is not a regular file and bounds the size. [`pid_is_alive`] is always `true` there,
//! so a crash leftover is swept only once it is older than [`STALE_AFTER`], later than on Unix.
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
    /// `$XDG_STATE_HOME`, if set.
    pub xdg_state_home: Option<OsString>,
    /// `$HOME`, if set.
    pub home: Option<OsString>,
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
            xdg_state_home: std::env::var_os("XDG_STATE_HOME"),
            home: std::env::var_os("HOME"),
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
    /// The directory above it is not owned by this user, or others can write to it.
    ParentNotPrivate,
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
            DirError::ParentNotPrivate => {
                "the directory above it is not owned by this user or others can write to it"
            }
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

/// Name of the directory under the user's state directory.
#[cfg(unix)]
const STATE_DIR_NAME: &str = "selahcue";

/// Which of the places in the module docs the descriptor goes to.
#[cfg(unix)]
enum Choice {
    /// `XDG_RUNTIME_DIR` or the temp dir itself: already exists and verified private.
    Existing(PathBuf),
    /// The home step. Exists and verified, or missing with a usable parent (then created).
    State(PathBuf),
    /// The `selahcue-UID` last resort in the shared temp directory.
    TempFallback(PathBuf),
}

#[cfg(unix)]
impl Choice {
    fn into_path(self) -> PathBuf {
        match self {
            Choice::Existing(p) | Choice::State(p) | Choice::TempFallback(p) => p,
        }
    }
}

/// `value` as an absolute path; an empty or relative value is ignored (the XDG rule).
#[cfg(unix)]
fn absolute(value: Option<&OsString>) -> Option<PathBuf> {
    let path = Path::new(value?);
    (path.is_absolute()).then(|| path.to_path_buf())
}

/// The directory the home step puts `selahcue` in: `$XDG_STATE_HOME`, else `$HOME/.local/state`.
#[cfg(unix)]
fn state_base(env: &DirEnv) -> Option<PathBuf> {
    absolute(env.xdg_state_home.as_ref())
        .or_else(|| absolute(env.home.as_ref()).map(|home| home.join(".local").join("state")))
}

/// `lstat` with trailing separators removed first: `lstat("link/")` FOLLOWS the link, so a path
/// spelled with a trailing slash (macOS `$TMPDIR` is) would otherwise defeat the symlink refusal.
#[cfg(unix)]
fn lstat(path: &Path) -> std::io::Result<std::fs::Metadata> {
    std::fs::symlink_metadata(strip_trailing_separators(path))
}

/// `path` without trailing `/` characters (the root itself stays `/`).
#[cfg(unix)]
fn strip_trailing_separators(path: &Path) -> &Path {
    use std::ffi::OsStr;
    use std::os::unix::ffi::OsStrExt;
    let bytes = path.as_os_str().as_bytes();
    let mut end = bytes.len();
    while end > 1 && bytes[end - 1] == b'/' {
        end -= 1;
    }
    Path::new(OsStr::from_bytes(&bytes[..end]))
}

/// Is `dir` a real directory (not a symlink), owned by `uid`, that group and other cannot write to?
/// The rule for the directory ABOVE one we create or use under the home step: we must not let
/// someone else swap what we put there.
#[cfg(unix)]
fn closed_and_ours(dir: &Path, uid: u32) -> bool {
    use std::os::unix::fs::MetadataExt;
    lstat(dir).is_ok_and(|meta| {
        meta.file_type().is_dir() && meta.uid() == uid && meta.mode() & 0o022 == 0
    })
}

/// The nearest ancestor of `dir` that exists (lstat), if every step up was a plain "not found".
#[cfg(unix)]
fn nearest_existing_ancestor(dir: &Path) -> Option<PathBuf> {
    let mut candidate = dir.parent();
    while let Some(path) = candidate {
        match lstat(path) {
            Ok(_) => return Some(path.to_path_buf()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => candidate = path.parent(),
            Err(_) => return None,
        }
    }
    None
}

/// Can the home step use `dir`? Either it exists and is a private directory whose parent is closed
/// and ours, or it is missing and the nearest existing ancestor (the first thing we would create
/// under) is closed and ours.
#[cfg(unix)]
fn state_dir_usable(dir: &Path, uid: u32) -> bool {
    match verify_private_dir(dir, uid) {
        Ok(()) => dir
            .parent()
            .is_some_and(|parent| closed_and_ours(parent, uid)),
        Err(DirError::Missing) => {
            nearest_existing_ancestor(dir).is_some_and(|ancestor| closed_and_ours(&ancestor, uid))
        }
        Err(_) => false,
    }
}

#[cfg(unix)]
fn choose(env: &DirEnv) -> Choice {
    if let Some(xdg) = absolute(env.xdg_runtime_dir.as_ref()) {
        if verify_private_dir(&xdg, env.uid).is_ok() {
            return Choice::Existing(xdg);
        }
    }
    if verify_private_dir(&env.temp_dir, env.uid).is_ok() {
        return Choice::Existing(env.temp_dir.clone());
    }
    if let Some(base) = state_base(env) {
        let dir = base.join(STATE_DIR_NAME);
        if state_dir_usable(&dir, env.uid) {
            return Choice::State(dir);
        }
    }
    Choice::TempFallback(
        env.temp_dir
            .join(format!("{FALLBACK_DIR_PREFIX}{}", env.uid)),
    )
}

/// The directory the descriptor lives in for `env`. Pure resolution: it creates nothing, so the
/// operator and any shell tooling can ask without side effects. See the module docs for the rule.
pub fn resolve_dir(env: &DirEnv) -> PathBuf {
    #[cfg(unix)]
    {
        choose(env).into_path()
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

/// [`resolve_dir`], then make sure the directory exists (creating the home step's `selahcue`
/// directory, or the last resort's, `0700` if it does not) and is private to `env.uid`. The publisher
/// calls this; on any error it publishes nothing.
pub fn prepare_dir(env: &DirEnv) -> Result<PathBuf, DirError> {
    #[cfg(unix)]
    {
        match choose(env) {
            Choice::Existing(dir) => {
                verify_private_dir(&dir, env.uid)?;
                Ok(dir)
            }
            Choice::State(dir) => {
                create_state_dir(&dir, env.uid)?;
                Ok(dir)
            }
            Choice::TempFallback(dir) => {
                if verify_private_dir(&dir, env.uid) == Err(DirError::Missing) {
                    create_private_dir(&dir)?;
                }
                verify_private_dir(&dir, env.uid)?;
                Ok(dir)
            }
        }
    }
    #[cfg(not(unix))]
    {
        let dir = env.temp_dir.clone();
        if verify_private_dir(&dir, env.uid) == Err(DirError::Missing) {
            create_private_dir(&dir)?;
        }
        verify_private_dir(&dir, env.uid)?;
        Ok(dir)
    }
}

/// Create the home step's directory (and only the missing components above it, each `0700`), then
/// verify it and its parent. An existing component is never touched.
#[cfg(unix)]
fn create_state_dir(dir: &Path, uid: u32) -> Result<(), DirError> {
    if verify_private_dir(dir, uid) == Err(DirError::Missing) {
        let ancestor = nearest_existing_ancestor(dir).ok_or(DirError::CreateFailed)?;
        if !closed_and_ours(&ancestor, uid) {
            return Err(DirError::ParentNotPrivate);
        }
        let mut missing = Vec::new();
        let mut walk = dir;
        while walk != ancestor {
            missing.push(walk.to_path_buf());
            walk = walk.parent().ok_or(DirError::CreateFailed)?;
        }
        for part in missing.iter().rev() {
            create_private_dir(part)?;
        }
    }
    verify_private_dir(dir, uid)?;
    if dir
        .parent()
        .is_some_and(|parent| closed_and_ours(parent, uid))
    {
        Ok(())
    } else {
        Err(DirError::ParentNotPrivate)
    }
}

/// `mkdir 0700`. If WE created it, set it to exactly `0700` afterwards: the creation mode went through
/// the umask (`0277` would leave `0400`, a directory we then cannot use for good). An "already
/// exists" is somebody else's directory, left exactly as found for the verify to judge.
#[cfg(unix)]
fn create_private_dir(dir: &Path) -> Result<(), DirError> {
    use std::os::unix::fs::DirBuilderExt;
    match std::fs::DirBuilder::new().mode(0o700).create(dir) {
        Ok(()) => set_exactly_0700(dir),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(()),
        Err(_) => Err(DirError::CreateFailed),
    }
}

/// `fchmod` on the directory opened `O_NOFOLLOW | O_DIRECTORY`, so the mode change cannot be steered
/// through a symlink swapped in after the `mkdir`.
#[cfg(unix)]
fn set_exactly_0700(dir: &Path) -> Result<(), DirError> {
    use rustix::fs::OFlags;
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    let flags = (OFlags::NOFOLLOW | OFlags::DIRECTORY).bits() as i32;
    std::fs::OpenOptions::new()
        .read(true)
        .custom_flags(flags)
        .open(dir)
        .and_then(|handle| handle.set_permissions(std::fs::Permissions::from_mode(0o700)))
        .map_err(|_| DirError::CreateFailed)
}

#[cfg(not(unix))]
fn create_private_dir(dir: &Path) -> Result<(), DirError> {
    std::fs::create_dir(dir).map_err(|_| DirError::CreateFailed)
}

/// Whether a directory that is a symlink is refused. Unix refuses (a symlink is where a squatter
/// points us); Windows follows it, as it did before this module existed (a junctioned `%TEMP%` is a
/// normal setup there, and refusing it would silently stop the descriptor being published).
pub const REFUSE_SYMLINKED_DIRS: bool = cfg!(unix);

/// The kind half of the directory check, as a pure decision so it can be tested on every platform.
#[doc(hidden)]
pub fn judge_dir_kind(
    is_symlink: bool,
    is_dir: bool,
    refuse_symlinks: bool,
) -> Result<(), DirError> {
    if is_symlink && refuse_symlinks {
        return Err(DirError::Symlink);
    }
    if !is_dir {
        return Err(DirError::NotDirectory);
    }
    Ok(())
}

#[cfg(unix)]
fn dir_metadata(dir: &Path) -> std::io::Result<std::fs::Metadata> {
    lstat(dir)
}

#[cfg(not(unix))]
fn dir_metadata(dir: &Path) -> std::io::Result<std::fs::Metadata> {
    std::fs::metadata(dir)
}

/// Is `dir` a real directory that only `uid` can use? On Unix judged with `lstat` (trailing
/// separators removed), so a symlink (even to a perfectly good private directory) is refused rather
/// than followed. On Windows there is no owner or mode to judge, a symlink is followed, and this only
/// checks that it is a directory.
pub fn verify_private_dir(dir: &Path, uid: u32) -> Result<(), DirError> {
    let meta = dir_metadata(dir).map_err(|e| match e.kind() {
        std::io::ErrorKind::NotFound => DirError::Missing,
        _ => DirError::Unreadable,
    })?;
    let kind = meta.file_type();
    judge_dir_kind(kind.is_symlink(), kind.is_dir(), REFUSE_SYMLINKED_DIRS)?;
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

/// Why a descriptor was not removed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RemoveError {
    /// Its directory is not private to this user, so nothing in it was touched.
    Dir(DirError),
    /// The unlink itself failed.
    Failed,
}

impl fmt::Display for RemoveError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RemoveError::Dir(why) => write!(f, "its directory is not private to this user: {why}"),
            RemoveError::Failed => f.write_str("it could not be removed"),
        }
    }
}

impl std::error::Error for RemoveError {}

/// Remove the descriptor at `path`, but only after its directory passes [`verify_private_dir`] for
/// `uid`: a planted symlink at the directory is refused instead of being followed to a file the
/// attacker chose. `Ok(true)` if it was removed, `Ok(false)` if there was nothing (or no directory)
/// to remove. The unlink itself never follows a symlink at the last component.
pub fn remove_descriptor(path: &Path, uid: u32) -> Result<bool, RemoveError> {
    let parent = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    match verify_private_dir(parent, uid) {
        Ok(()) => {}
        Err(DirError::Missing) => return Ok(false),
        Err(why) => return Err(RemoveError::Dir(why)),
    }
    match std::fs::remove_file(path) {
        Ok(()) => Ok(true),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err(RemoveError::Failed),
    }
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
/// descriptor. It does NOT look at the directory (the caller has, or [`read_descriptor_as`] does).
/// Internal: it is public only so the file-owner check can be exercised on its own (a directory
/// check in front would otherwise always stop a foreign uid first). Use [`read_descriptor_as`].
#[doc(hidden)]
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
