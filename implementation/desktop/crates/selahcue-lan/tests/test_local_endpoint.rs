//! `selahcue_lan::local_endpoint` (17tnw2b9agb): where the endpoint descriptor lives, how it is read,
//! and how a crashed publisher's leftovers are swept.
//!
//! The descriptor holds a bearer token. The threats are another local account that can write the
//! shared `/tmp`: it can squat the name, plant a FIFO (hanging the reader's `open(2)`), plant a
//! symlink, or leave a file of its own. Every refusal below is paired with a positive control (the
//! SAME call on a valid input succeeds), so "refused" cannot be a dead mechanism.
//!
//! Only the Unix halves are tested here (the Windows branch has no owner or mode to check and is not
//! compiled on this machine). The Linux-specific branches (`XDG_RUNTIME_DIR`, a world-writable
//! `/tmp`) are driven through the injected [`DirEnv`], so they run on macOS too; no test touches the
//! real `/run/user/UID`, the real shared temp directory or a real descriptor. "Another user" is
//! simulated by injecting a different uid: the real files are ours, the injected current uid is not.
#![cfg(unix)]

use selahcue_lan::local_endpoint::{
    parse_staging_name, pid_is_alive, prepare_dir, read_descriptor_as, read_file_as, resolve_dir,
    staging_file_name, sweep_stale_staging, sweep_stale_staging_with, verify_private_dir, DirEnv,
    DirError, ReadError, DESCRIPTOR_FILE_NAME, MAX_SWEEP_ENTRIES, STAGING_PREFIX, STAGING_SUFFIX,
    STALE_AFTER,
};
use std::io::Write;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::time::{Duration, Instant, SystemTime};
use tempfile::TempDir;

const MAX: u64 = 4096;
const BODY: &str = r#"{"addr":"127.0.0.1:1","pin":"00","device":"d","token":"t"}"#;

fn my_uid() -> u32 {
    rustix::process::geteuid().as_raw()
}

/// A scratch directory that is private to us (`tempfile` creates it `0700`; asserted, not assumed).
fn private_dir() -> TempDir {
    let dir = tempfile::tempdir().expect("tempdir");
    set_mode(dir.path(), 0o700);
    dir
}

/// A scratch directory that looks like a shared `/tmp`: anyone may write to it.
fn shared_dir() -> TempDir {
    let dir = tempfile::tempdir().expect("tempdir");
    set_mode(dir.path(), 0o777);
    dir
}

fn set_mode(path: &Path, mode: u32) {
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode)).expect("chmod");
}

fn mode_of(path: &Path) -> u32 {
    std::fs::symlink_metadata(path).expect("stat").mode() & 0o7777
}

fn env(xdg: Option<&Path>, temp: &Path) -> DirEnv {
    DirEnv {
        xdg_runtime_dir: xdg.map(|p| p.as_os_str().to_owned()),
        temp_dir: temp.to_path_buf(),
        uid: my_uid(),
    }
}

fn as_other_user(mut env: DirEnv) -> DirEnv {
    env.uid = env.uid.wrapping_add(1);
    env
}

fn subdir_of(temp: &Path) -> PathBuf {
    temp.join(format!("selahcue-{}", my_uid()))
}

fn descriptor_in(dir: &Path, mode: u32, body: &[u8]) -> PathBuf {
    let path = dir.join(DESCRIPTOR_FILE_NAME);
    std::fs::write(&path, body).expect("write descriptor");
    set_mode(&path, mode);
    path
}

fn read(path: &Path) -> Result<String, ReadError> {
    read_descriptor_as(path, MAX, my_uid())
}

fn entries(dir: &Path) -> usize {
    std::fs::read_dir(dir).expect("list").count()
}

// ---- where the descriptor lives --------------------------------------------------------------

#[test]
fn a_valid_xdg_runtime_dir_is_used_as_is() {
    let xdg = private_dir();
    let temp = shared_dir();

    assert_eq!(
        resolve_dir(&env(Some(xdg.path()), temp.path())),
        xdg.path(),
        "a private XDG_RUNTIME_DIR is the per-user home of the descriptor"
    );
    assert_eq!(entries(temp.path()), 0, "resolving creates nothing");
}

#[test]
fn an_xdg_runtime_dir_that_is_not_ours_alone_is_ignored() {
    let temp = shared_dir();
    let fallback = subdir_of(temp.path());
    let holder = private_dir();

    // Positive control first: the SAME arrangement with a valid XDG dir does use it.
    let good = private_dir();
    assert_eq!(
        resolve_dir(&env(Some(good.path()), temp.path())),
        good.path()
    );

    let not_a_dir = holder.path().join("a-file");
    std::fs::write(&not_a_dir, "x").expect("file");
    let real = holder.path().join("real");
    std::fs::create_dir(&real).expect("mkdir");
    set_mode(&real, 0o700);
    let link = holder.path().join("link");
    std::os::unix::fs::symlink(&real, &link).expect("symlink");
    let mut wide = Vec::new();
    for mode in [0o750, 0o705, 0o770, 0o707, 0o755, 0o777] {
        let d = holder.path().join(format!("wide-{mode:o}"));
        std::fs::create_dir(&d).expect("mkdir");
        set_mode(&d, mode);
        wide.push((format!("mode {mode:o}"), d));
    }

    let mut bad: Vec<(String, PathBuf)> = vec![
        ("not a directory".into(), not_a_dir),
        ("a symlink to a private directory".into(), link),
        ("missing".into(), holder.path().join("missing")),
    ];
    bad.extend(wide);
    for (label, xdg) in &bad {
        assert_eq!(
            resolve_dir(&env(Some(xdg), temp.path())),
            fallback,
            "an XDG_RUNTIME_DIR that is {label} must be ignored"
        );
    }

    // Owned by someone else (the check is on the owner, not just the mode).
    assert_eq!(
        resolve_dir(&as_other_user(env(Some(good.path()), temp.path()))),
        subdir_of_for(temp.path(), my_uid().wrapping_add(1)),
        "an XDG_RUNTIME_DIR owned by another user must be ignored"
    );

    // Relative and empty values are ignored even when they name something that WOULD verify: a
    // relative spelling of the private directory `good` (the premise is asserted, so this cannot
    // pass merely because the relative path points nowhere).
    let relative = relative_to_cwd(good.path());
    assert!(relative.is_relative());
    verify_private_dir(&relative, my_uid()).expect("premise: the relative spelling verifies");
    assert_eq!(
        resolve_dir(&env(Some(&relative), temp.path())),
        fallback,
        "a relative XDG_RUNTIME_DIR must be ignored"
    );
    let mut empty = env(None, temp.path());
    empty.xdg_runtime_dir = Some(std::ffi::OsString::new());
    assert_eq!(resolve_dir(&empty), fallback, "an empty XDG_RUNTIME_DIR");
}

/// `target` spelled relative to the current directory (`../../..` up to the root, then down).
fn relative_to_cwd(target: &Path) -> PathBuf {
    let cwd = std::env::current_dir().expect("cwd");
    let mut relative = PathBuf::new();
    for _ in cwd
        .components()
        .filter(|c| matches!(c, std::path::Component::Normal(_)))
    {
        relative.push("..");
    }
    for part in target.components() {
        if let std::path::Component::Normal(name) = part {
            relative.push(name);
        }
    }
    relative
}

fn subdir_of_for(temp: &Path, uid: u32) -> PathBuf {
    temp.join(format!("selahcue-{uid}"))
}

#[test]
fn a_temp_dir_that_is_already_private_is_used_as_is() {
    // The macOS shape: $TMPDIR is a per-user 0700 directory, so the descriptor keeps its location.
    let temp = private_dir();
    assert_eq!(resolve_dir(&env(None, temp.path())), temp.path());
    assert_eq!(entries(temp.path()), 0);
}

#[test]
fn a_shared_temp_dir_leads_to_a_per_user_subdirectory() {
    // The Linux /tmp shape.
    let temp = shared_dir();
    assert_eq!(resolve_dir(&env(None, temp.path())), subdir_of(temp.path()));

    // A private temp dir that belongs to someone else is not ours to use as is either.
    let theirs = private_dir();
    assert_eq!(
        resolve_dir(&as_other_user(env(None, theirs.path()))),
        subdir_of_for(theirs.path(), my_uid().wrapping_add(1)),
    );
}

// ---- creating and verifying the private directory ----------------------------------------------

#[test]
fn the_fallback_directory_is_created_0700_and_reused() {
    let temp = shared_dir();
    let want = subdir_of(temp.path());

    let first = prepare_dir(&env(None, temp.path())).expect("create");
    assert_eq!(first, want);
    assert_eq!(mode_of(&first), 0o700, "created owner-only");
    assert_eq!(std::fs::metadata(&first).expect("stat").uid(), my_uid());

    std::fs::write(first.join("keep"), "x").expect("file");
    let second = prepare_dir(&env(None, temp.path())).expect("reuse");
    assert_eq!(second, want);
    assert!(
        first.join("keep").exists(),
        "preparing an existing directory must not recreate it"
    );
}

#[test]
fn preparing_a_valid_xdg_or_private_temp_dir_creates_nothing() {
    let xdg = private_dir();
    let temp = shared_dir();
    assert_eq!(
        prepare_dir(&env(Some(xdg.path()), temp.path())).expect("xdg"),
        xdg.path()
    );
    assert_eq!(entries(temp.path()), 0, "no fallback directory was made");

    let private_temp = private_dir();
    assert_eq!(
        prepare_dir(&env(None, private_temp.path())).expect("private temp"),
        private_temp.path()
    );
    assert_eq!(entries(private_temp.path()), 0);
}

#[test]
fn a_fallback_directory_squatted_by_another_user_is_refused_and_left_alone() {
    // Simulated squat: the directory exists under the exact name this "user" would use, but it is
    // owned by someone else (here: we are the owner, the injected current uid is not).
    let temp = shared_dir();
    let other = as_other_user(env(None, temp.path()));
    let planted = subdir_of_for(temp.path(), other.uid);
    std::fs::create_dir(&planted).expect("plant");
    set_mode(&planted, 0o700);

    // Positive control: the same directory is accepted for its real owner.
    verify_private_dir(&planted, my_uid()).expect("our own 0700 directory verifies");

    assert_eq!(prepare_dir(&other), Err(DirError::WrongOwner));
    assert_eq!(entries(&planted), 0, "nothing may be created inside it");
}

#[test]
fn a_fallback_directory_that_is_too_open_is_refused() {
    for mode in [0o755, 0o750, 0o705, 0o701, 0o770, 0o777] {
        let temp = shared_dir();
        let planted = subdir_of(temp.path());
        std::fs::create_dir(&planted).expect("plant");
        set_mode(&planted, mode);

        assert_eq!(
            prepare_dir(&env(None, temp.path())),
            Err(DirError::TooOpen),
            "mode {mode:o}"
        );
        assert_eq!(
            entries(&planted),
            0,
            "mode {mode:o}: nothing created inside"
        );

        set_mode(&planted, 0o700);
        assert!(
            prepare_dir(&env(None, temp.path())).is_ok(),
            "mode {mode:o}: control, the same directory at 0700 is accepted"
        );
    }
}

#[test]
fn a_fallback_directory_that_is_a_symlink_is_refused_not_followed() {
    let temp = shared_dir();
    let target = private_dir();
    std::os::unix::fs::symlink(target.path(), subdir_of(temp.path())).expect("symlink");

    assert_eq!(
        prepare_dir(&env(None, temp.path())),
        Err(DirError::Symlink),
        "a symlink to a perfectly good private directory is still a symlink"
    );
    assert_eq!(
        entries(target.path()),
        0,
        "nothing created through the link"
    );
    verify_private_dir(target.path(), my_uid()).expect("control: the target itself verifies");
}

#[test]
fn a_fallback_name_taken_by_a_plain_file_is_refused() {
    let temp = shared_dir();
    std::fs::write(subdir_of(temp.path()), "x").expect("plant");
    assert_eq!(
        prepare_dir(&env(None, temp.path())),
        Err(DirError::NotDirectory)
    );
}

#[test]
fn a_fallback_directory_that_cannot_be_created_is_an_error() {
    let temp = shared_dir();
    let missing_parent = temp.path().join("no-such-dir");
    assert_eq!(
        prepare_dir(&env(None, &missing_parent)),
        Err(DirError::CreateFailed)
    );
}

#[test]
fn a_missing_directory_does_not_verify() {
    let temp = private_dir();
    assert_eq!(
        verify_private_dir(&temp.path().join("nope"), my_uid()),
        Err(DirError::Missing)
    );
}

// ---- reading the descriptor --------------------------------------------------------------------

#[test]
fn a_valid_descriptor_is_read() {
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, BODY.as_bytes());
    assert_eq!(read(&path).as_deref(), Ok(BODY));
}

/// Run `f` on a thread and give it `limit` to finish. A reader that blocks (the bug) cannot hang
/// the suite: after the limit `release` is called to unblock it, and the test fails.
fn promptly<T: Send + 'static>(
    limit: Duration,
    f: impl FnOnce() -> T + Send + 'static,
    release: impl FnOnce(),
) -> (T, Duration) {
    let (tx, rx) = mpsc::channel();
    let started = Instant::now();
    std::thread::spawn(move || {
        let _ = tx.send(f());
    });
    match rx.recv_timeout(limit) {
        Ok(v) => (v, started.elapsed()),
        Err(_) => {
            release();
            panic!("the call did not return within {limit:?}: it blocked");
        }
    }
}

fn make_fifo(path: &Path) {
    // `mkfifo` is a standard tool on macOS and Linux (rustix has no `mknodat` on macOS).
    let made = std::process::Command::new("mkfifo")
        .arg(path)
        .status()
        .expect("mkfifo is a standard tool on macOS and Linux");
    assert!(made.success(), "mkfifo failed");
    // mkfifo honours the umask (0644 under the usual 022); make it the mode a real descriptor has,
    // so only the file TYPE can be what refuses it.
    set_mode(path, 0o600);
}

/// Unblocks a reader stuck in `open(2)` on `fifo` by opening the other end.
fn release_fifo(fifo: PathBuf) -> impl FnOnce() {
    move || {
        let _ = std::fs::OpenOptions::new().write(true).open(fifo);
    }
}

#[test]
fn a_fifo_at_the_path_is_refused_without_blocking() {
    let dir = private_dir();
    let fifo = dir.path().join(DESCRIPTOR_FILE_NAME);
    make_fifo(&fifo);
    assert_eq!(mode_of(&fifo), 0o600, "premise: right owner, right mode");

    let p = fifo.clone();
    let (result, took) = promptly(
        Duration::from_secs(5),
        move || read(&p),
        release_fifo(fifo.clone()),
    );

    assert_eq!(result, Err(ReadError::NotRegularFile));
    assert!(took < Duration::from_secs(2), "took {took:?}");

    // Control: the same call on a regular file at the same path succeeds.
    std::fs::remove_file(&fifo).expect("remove fifo");
    descriptor_in(dir.path(), 0o600, BODY.as_bytes());
    assert_eq!(read(&fifo).as_deref(), Ok(BODY));
}

#[test]
fn a_fifo_with_data_waiting_in_it_is_refused_on_its_type_not_read() {
    let dir = private_dir();
    let fifo = dir.path().join(DESCRIPTOR_FILE_NAME);
    make_fifo(&fifo);
    // O_RDWR on a FIFO does not block; it lets us park a complete, valid descriptor in the pipe.
    let mut holder = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&fifo)
        .expect("hold the fifo open");
    holder.write_all(BODY.as_bytes()).expect("fill the pipe");

    let p = fifo.clone();
    let (result, _) = promptly(
        Duration::from_secs(5),
        move || read(&p),
        release_fifo(fifo.clone()),
    );
    drop(holder);

    assert_eq!(
        result,
        Err(ReadError::NotRegularFile),
        "a pipe full of a valid descriptor must not be accepted as one"
    );
}

#[test]
fn a_symlink_at_the_path_is_refused_even_when_its_target_is_valid() {
    let dir = private_dir();
    let real = dir.path().join("real.json");
    std::fs::write(&real, BODY).expect("target");
    set_mode(&real, 0o600);
    let link = dir.path().join(DESCRIPTOR_FILE_NAME);
    std::os::unix::fs::symlink(&real, &link).expect("symlink");

    assert_eq!(read(&link), Err(ReadError::Symlink));
    assert_eq!(
        read(&real).as_deref(),
        Ok(BODY),
        "control: the target reads"
    );
}

#[test]
fn a_dangling_symlink_is_refused_not_reported_as_absent() {
    let dir = private_dir();
    let link = dir.path().join(DESCRIPTOR_FILE_NAME);
    std::os::unix::fs::symlink(dir.path().join("gone"), &link).expect("symlink");
    assert_eq!(read(&link), Err(ReadError::Symlink));
}

#[test]
fn a_descriptor_owned_by_another_user_is_refused() {
    // `read_file_as` is the file half of `read_descriptor_as` (no directory check): with the
    // directory check in front, a foreign uid is stopped by the directory first, and the file
    // owner check could not be seen to bite at all.
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, BODY.as_bytes());

    assert_eq!(
        read_file_as(&path, MAX, my_uid().wrapping_add(1)),
        Err(ReadError::WrongOwner)
    );
    assert_eq!(
        read_file_as(&path, MAX, my_uid()).as_deref(),
        Ok(BODY),
        "control: the same file for its real owner"
    );
    assert_eq!(
        read_descriptor_as(&path, MAX, my_uid().wrapping_add(1)),
        Err(ReadError::Dir(DirError::WrongOwner)),
        "and the full read refuses it too (at the directory, which is judged first)"
    );
}

#[test]
fn any_mode_other_than_0600_is_refused() {
    for mode in [0o644, 0o640, 0o660, 0o602, 0o604, 0o400, 0o700, 0o755] {
        let dir = private_dir();
        let path = descriptor_in(dir.path(), mode, BODY.as_bytes());
        assert_eq!(
            read(&path),
            Err(ReadError::WrongMode(mode)),
            "mode {mode:o}"
        );
        set_mode(&path, 0o600);
        assert_eq!(read(&path).as_deref(), Ok(BODY), "mode {mode:o}: control");
    }
}

#[test]
fn a_directory_at_the_path_is_refused() {
    let dir = private_dir();
    let at = dir.path().join(DESCRIPTOR_FILE_NAME);
    std::fs::create_dir(&at).expect("mkdir");
    set_mode(&at, 0o600);
    assert_eq!(read(&at), Err(ReadError::NotRegularFile));
}

#[test]
fn an_oversized_descriptor_is_refused_and_one_at_the_limit_is_read() {
    let dir = private_dir();
    let at_limit = format!("{BODY}{}", " ".repeat(MAX as usize - BODY.len()));
    assert_eq!(at_limit.len() as u64, MAX, "premise");
    let path = descriptor_in(dir.path(), 0o600, at_limit.as_bytes());
    assert_eq!(read(&path).as_deref(), Ok(at_limit.as_str()));

    let over = format!("{at_limit} ");
    std::fs::write(&path, over).expect("grow");
    assert_eq!(read(&path), Err(ReadError::TooLarge));
}

#[test]
fn bytes_that_are_not_text_are_refused() {
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, &[0xff, 0xfe, 0x00]);
    assert_eq!(read(&path), Err(ReadError::Unreadable));
}

#[test]
fn a_missing_descriptor_or_directory_reads_as_absent() {
    let dir = private_dir();
    assert_eq!(
        read(&dir.path().join(DESCRIPTOR_FILE_NAME)),
        Err(ReadError::Absent)
    );
    assert_eq!(
        read(&dir.path().join("no-such-dir").join(DESCRIPTOR_FILE_NAME)),
        Err(ReadError::Absent),
        "no host has run yet: not worth a log line"
    );
}

#[test]
fn a_descriptor_in_a_directory_that_is_not_private_is_not_trusted() {
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, BODY.as_bytes());

    for mode in [0o755, 0o750, 0o705, 0o777] {
        set_mode(dir.path(), mode);
        assert_eq!(
            read(&path),
            Err(ReadError::Dir(DirError::TooOpen)),
            "directory mode {mode:o}"
        );
    }
    set_mode(dir.path(), 0o700);
    assert_eq!(
        read(&path).as_deref(),
        Ok(BODY),
        "control: directory at 0700"
    );

    assert_eq!(
        read_descriptor_as(&path, MAX, my_uid().wrapping_add(1)),
        Err(ReadError::Dir(DirError::WrongOwner)),
        "a directory owned by someone else is judged before the file in it"
    );
}

#[test]
fn a_descriptor_reached_through_a_symlinked_directory_is_not_trusted() {
    let real = private_dir();
    descriptor_in(real.path(), 0o600, BODY.as_bytes());
    let holder = private_dir();
    let link = holder.path().join("dir-link");
    std::os::unix::fs::symlink(real.path(), &link).expect("symlink");

    assert_eq!(
        read(&link.join(DESCRIPTOR_FILE_NAME)),
        Err(ReadError::Dir(DirError::Symlink))
    );
}

// ---- staging names -----------------------------------------------------------------------------

#[test]
fn staging_names_round_trip() {
    let name = staging_file_name(4242, 7);
    assert!(name.starts_with(STAGING_PREFIX) && name.ends_with(STAGING_SUFFIX));
    assert_eq!(parse_staging_name(&name), Some((4242, 7)));
    assert_eq!(
        parse_staging_name(&staging_file_name(u32::MAX, u64::MAX)),
        Some((u32::MAX, u64::MAX))
    );
}

#[test]
fn only_exact_staging_names_parse() {
    for bad in [
        "",
        DESCRIPTOR_FILE_NAME,
        ".selahcue-endpoint.abc.1.tmp",
        ".selahcue-endpoint.1.tmp",
        ".selahcue-endpoint.1.2.3.tmp",
        ".selahcue-endpoint.1.2.tmp.bak",
        ".selahcue-endpoint..2.tmp",
        ".selahcue-endpoint.1..tmp",
        ".selahcue-endpoint.-1.2.tmp",
        ".selahcue-endpoint.+1.2.tmp",
        ".selahcue-endpoint.99999999999.2.tmp",
        "selahcue-endpoint.1.2.tmp",
        "other.tmp",
    ] {
        assert_eq!(parse_staging_name(bad), None, "{bad:?}");
    }
}

// ---- the stale sweep ---------------------------------------------------------------------------

fn plant_staging(dir: &Path, pid: u32, n: u64) -> PathBuf {
    let path = dir.join(staging_file_name(pid, n));
    std::fs::write(&path, "dead-token").expect("plant");
    set_mode(&path, 0o600);
    path
}

fn age(path: &Path, by: Duration) {
    let f = std::fs::OpenOptions::new()
        .write(true)
        .open(path)
        .expect("open for mtime");
    f.set_modified(SystemTime::now() - by).expect("set mtime");
}

fn sweep(dir: &Path, uid: u32, alive: &dyn Fn(u32) -> bool) -> usize {
    sweep_stale_staging_with(dir, uid, SystemTime::now(), alive, MAX_SWEEP_ENTRIES)
}

#[test]
fn a_leftover_of_a_dead_process_is_removed() {
    let dir = private_dir();
    let stale = plant_staging(dir.path(), 4242, 0);
    let descriptor = descriptor_in(dir.path(), 0o600, BODY.as_bytes());

    assert_eq!(sweep(dir.path(), my_uid(), &|_| false), 1);

    assert!(!stale.exists(), "the crash leftover is gone");
    assert!(
        descriptor.exists(),
        "the descriptor is never a sweep target"
    );
}

#[test]
fn a_fresh_file_of_a_live_process_is_left_alone() {
    // An in-flight publisher (the host's own thread, or a second output window) must not have its
    // staging file taken from under it: the rename would then fail.
    let dir = private_dir();
    let live = plant_staging(dir.path(), 4242, 0);

    assert_eq!(sweep(dir.path(), my_uid(), &|_| true), 0);
    assert!(live.exists());

    // Control: once that process is dead, the same file goes.
    assert_eq!(sweep(dir.path(), my_uid(), &|_| false), 1);
    assert!(!live.exists());
}

#[test]
fn a_leftover_under_a_recycled_live_pid_goes_once_it_is_old_enough() {
    let dir = private_dir();
    let young = plant_staging(dir.path(), 1, 0);
    let old = plant_staging(dir.path(), 1, 1);
    age(&young, STALE_AFTER - Duration::from_secs(30));
    age(&old, STALE_AFTER + Duration::from_secs(30));

    assert_eq!(sweep(dir.path(), my_uid(), &|_| true), 1);

    assert!(young.exists(), "younger than the limit: kept");
    assert!(!old.exists(), "older than the limit: removed");
}

#[test]
fn a_file_owned_by_another_user_is_never_swept() {
    let dir = private_dir();
    let theirs = plant_staging(dir.path(), 4242, 0);

    assert_eq!(
        sweep(dir.path(), my_uid().wrapping_add(1), &|_| false),
        0,
        "the files are ours, the injected current user is not"
    );
    assert!(theirs.exists());
    assert_eq!(sweep(dir.path(), my_uid(), &|_| false), 1, "control");
}

#[test]
fn a_symlink_at_a_staging_name_is_left_alone_and_never_followed() {
    let dir = private_dir();
    let victim = dir.path().join("victim.txt");
    std::fs::write(&victim, "precious").expect("victim");
    let link = dir.path().join(staging_file_name(4242, 0));
    std::os::unix::fs::symlink(&victim, &link).expect("symlink");
    let plain = plant_staging(dir.path(), 4242, 1);

    assert_eq!(
        sweep(dir.path(), my_uid(), &|_| false),
        1,
        "only the plain file"
    );

    assert!(plain.parent().is_some() && !plain.exists(), "control");
    assert!(std::fs::symlink_metadata(&link)
        .expect("link")
        .file_type()
        .is_symlink());
    assert_eq!(
        std::fs::read_to_string(&victim).expect("victim"),
        "precious"
    );
}

#[test]
fn a_directory_at_a_staging_name_is_left_alone() {
    let dir = private_dir();
    let planted = dir.path().join(staging_file_name(4242, 0));
    std::fs::create_dir_all(planted.join("sub")).expect("plant");

    assert_eq!(sweep(dir.path(), my_uid(), &|_| false), 0);
    assert!(planted.join("sub").is_dir());
}

#[test]
fn names_that_are_not_ours_are_never_swept() {
    let dir = private_dir();
    let mut kept = Vec::new();
    for name in [
        "notes.tmp",
        ".selahcue-endpoint.abc.1.tmp",
        ".selahcue-endpoint.1.2.tmp.bak",
        "endpoint.json",
    ] {
        let p = dir.path().join(name);
        std::fs::write(&p, "x").expect("plant");
        kept.push(p);
    }
    assert_eq!(sweep(dir.path(), my_uid(), &|_| false), 0);
    assert!(kept.iter().all(|p| p.exists()));
}

#[test]
fn the_sweep_examines_a_bounded_number_of_entries() {
    let dir = private_dir();
    let planted: Vec<_> = (0..6).map(|n| plant_staging(dir.path(), 4242, n)).collect();

    let removed = sweep_stale_staging_with(dir.path(), my_uid(), SystemTime::now(), &|_| false, 3);

    assert_eq!(removed, 3, "a cap of 3 examines 3 entries");
    assert_eq!(planted.iter().filter(|p| p.exists()).count(), 3);
    assert_eq!(
        sweep(dir.path(), my_uid(), &|_| false),
        3,
        "control: the rest go"
    );
    assert!(MAX_SWEEP_ENTRIES >= 256 && MAX_SWEEP_ENTRIES <= 65_536);
}

#[test]
fn sweeping_a_missing_directory_removes_nothing_and_does_not_panic() {
    let dir = private_dir();
    assert_eq!(sweep(&dir.path().join("nope"), my_uid(), &|_| false), 0);
}

#[test]
fn the_real_liveness_check_tells_this_process_from_a_pid_that_cannot_exist() {
    assert!(pid_is_alive(std::process::id()));
    assert!(!pid_is_alive(i32::MAX as u32), "above any pid_max");
    assert!(!pid_is_alive(u32::MAX), "not a valid pid at all");
    assert!(!pid_is_alive(0), "pid 0 is not a process we may name");
    assert!(
        pid_is_alive(1),
        "pid 1 exists and is not ours: `kill(pid, 0)` answers permission denied, which means alive"
    );
}

#[test]
fn the_production_sweep_keeps_our_own_fresh_file_and_removes_a_dead_one() {
    let dir = private_dir();
    let mine = plant_staging(dir.path(), std::process::id(), 0);
    let dead = plant_staging(dir.path(), i32::MAX as u32, 0);

    assert_eq!(sweep_stale_staging(dir.path(), my_uid()), 1);

    assert!(mine.exists(), "this process's own in-flight file");
    assert!(!dead.exists());
}

// ---- the shell tooling must agree with the Rust resolver -----------------------------------------

fn script_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../../scripts/endpoint_path.py")
}

fn script_says(xdg: Option<&Path>, temp: &Path) -> PathBuf {
    let mut cmd = std::process::Command::new("python3");
    cmd.arg("-I").arg(script_path()).env("TMPDIR", temp);
    match xdg {
        Some(x) => cmd.env("XDG_RUNTIME_DIR", x),
        None => cmd.env_remove("XDG_RUNTIME_DIR"),
    };
    let out = cmd.output().expect("python3 is required by `make ci`");
    assert!(
        out.status.success(),
        "scripts/endpoint_path.py failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    PathBuf::from(String::from_utf8(out.stdout).expect("utf-8").trim_end())
}

#[test]
fn make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code() {
    let xdg_ok = private_dir();
    let xdg_open = shared_dir();
    let shared_temp = shared_dir();
    let private_temp = private_dir();

    let cases: Vec<(&str, Option<PathBuf>, PathBuf)> = vec![
        (
            "private xdg",
            Some(xdg_ok.path().into()),
            shared_temp.path().into(),
        ),
        (
            "xdg too open",
            Some(xdg_open.path().into()),
            shared_temp.path().into(),
        ),
        ("xdg relative", Some(".".into()), shared_temp.path().into()),
        (
            "xdg relative but private",
            Some(relative_to_cwd(xdg_ok.path())),
            shared_temp.path().into(),
        ),
        (
            "xdg missing path",
            Some(shared_temp.path().join("nope")),
            shared_temp.path().into(),
        ),
        ("no xdg, shared temp", None, shared_temp.path().into()),
        ("no xdg, private temp", None, private_temp.path().into()),
    ];
    for (label, xdg, temp) in &cases {
        let rust = descriptor_path_for(&env(xdg.as_deref(), temp));
        assert_eq!(script_says(xdg.as_deref(), temp), rust, "{label}");
    }
    // Premise: the cases really cover all three outcomes.
    assert_eq!(
        descriptor_path_for(&env(None, shared_temp.path())),
        subdir_of(shared_temp.path()).join(DESCRIPTOR_FILE_NAME)
    );
    assert_eq!(
        descriptor_path_for(&env(None, private_temp.path())),
        private_temp.path().join(DESCRIPTOR_FILE_NAME)
    );
}

fn descriptor_path_for(env: &DirEnv) -> PathBuf {
    resolve_dir(env).join(DESCRIPTOR_FILE_NAME)
}
