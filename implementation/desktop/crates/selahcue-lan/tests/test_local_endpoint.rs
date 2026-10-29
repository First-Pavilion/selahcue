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
    descriptor_path, parse_staging_name, pid_is_alive, prepare_dir, prepare_staging_dir,
    read_descriptor_as, read_file_as, remove_descriptor, resolve_dir, staging_file_name,
    sweep_stale_staging, sweep_stale_staging_with, verify_private_dir, DirEnv, DirError, ReadError,
    RemoveError, DESCRIPTOR_FILE_NAME, MAX_SWEEP_ENTRIES, STAGING_DIR_NAME, STAGING_PREFIX,
    STAGING_SUFFIX, STALE_AFTER,
};
use std::io::Write;
use std::os::unix::fs::{FileTypeExt, MetadataExt, PermissionsExt};
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
        xdg_state_home: None,
        home: None,
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
    let (result, _took) = promptly(
        Duration::from_secs(5),
        move || read(&p),
        release_fifo(fifo.clone()),
    );

    // No timing assertion on `took`: the 5 s watchdog above is the bound that fails a blocking
    // reader, and a tight wall-clock limit would flake on a loaded machine.
    assert_eq!(result, Err(ReadError::NotRegularFile));

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
    for mode in [
        0o644, 0o640, 0o660, 0o602, 0o604, 0o400, 0o700, 0o755, 0o4600, 0o2600, 0o1600,
    ] {
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

// The sweep's cap is a bound on work, not a tuning knob: pinned at compile time to a sane range.
const _: () = assert!(MAX_SWEEP_ENTRIES >= 256 && MAX_SWEEP_ENTRIES <= 65_536);

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
    // Absolute ages, NOT derived from `STALE_AFTER`: a test that ages the file "by the constant plus
    // a bit" follows the constant wherever a mutation moves it, and stays green (found by mutation).
    // The premise pins the constant to the range the ages below are chosen around.
    assert!(
        STALE_AFTER >= Duration::from_secs(30) && STALE_AFTER <= Duration::from_secs(300),
        "STALE_AFTER moved: re-choose the ages below on purpose"
    );
    let dir = private_dir();
    let young = plant_staging(dir.path(), 1, 0);
    let old = plant_staging(dir.path(), 1, 1);
    age(&young, Duration::from_secs(10));
    age(&old, Duration::from_secs(600));

    assert_eq!(sweep(dir.path(), my_uid(), &|_| true), 1);

    assert!(
        young.exists(),
        "10 s old and its process is alive: an in-flight publish, kept"
    );
    assert!(
        !old.exists(),
        "10 minutes old: a leftover even though the pid is alive, removed"
    );
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

    assert!(!plain.exists(), "control: the plain file is swept");
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

#[test]
fn crash_leftovers_beyond_the_cap_are_eventually_swept_on_restart() {
    let dir = private_dir();
    let dead: Vec<_> = (0..32)
        .map(|n| plant_staging(dir.path(), i32::MAX as u32, n))
        .collect();
    for n in 0..6000 {
        std::fs::write(
            dir.path().join(format!(".aaaa-unrelated-{n:05}")),
            "precious",
        )
        .expect("unrelated");
    }
    let positions: Vec<_> = std::fs::read_dir(dir.path())
        .expect("entries")
        .enumerate()
        .filter_map(|(i, entry)| {
            let entry = entry.expect("entry");
            entry
                .file_name()
                .to_str()
                .and_then(parse_staging_name)
                .map(|_| i)
        })
        .collect();
    assert!(
        positions.iter().any(|i| *i >= MAX_SWEEP_ENTRIES),
        "fixture must exercise a staging file beyond the production cap: {positions:?}"
    );
    let live = plant_staging(dir.path(), std::process::id(), 99);
    let victim = dir.path().join("victim.txt");
    std::fs::write(&victim, "precious").expect("victim");
    let link = dir.path().join(staging_file_name(i32::MAX as u32, 100));
    std::os::unix::fs::symlink(&victim, &link).expect("symlink");
    let directory = dir.path().join(staging_file_name(i32::MAX as u32, 101));
    std::fs::create_dir(&directory).expect("directory");
    let fifo = dir.path().join(staging_file_name(i32::MAX as u32, 102));
    assert!(std::process::Command::new("mkfifo")
        .arg(&fifo)
        .status()
        .expect("mkfifo")
        .success());
    let descriptor = descriptor_in(dir.path(), 0o600, BODY.as_bytes());
    for _ in 0..5 {
        let status = std::process::Command::new(std::env::current_exe().expect("test binary"))
            .args(["--ignored", "--exact", "sweep_restart_child"])
            .env("SELAHCUE_SWEEP_TEST_DIR", dir.path())
            .status()
            .expect("child");
        assert!(status.success());
    }
    assert_eq!(
        dead.iter().filter(|path| path.exists()).count(),
        0,
        "reopening the same prefix must not strand crash leftovers"
    );
    assert!(live.exists());
    assert!(std::fs::symlink_metadata(&link)
        .expect("link")
        .file_type()
        .is_symlink());
    assert!(directory.is_dir());
    assert!(std::fs::symlink_metadata(&fifo)
        .expect("FIFO")
        .file_type()
        .is_fifo());
    assert_eq!(
        std::fs::read_to_string(&victim).expect("victim"),
        "precious"
    );
    assert_eq!(
        std::fs::read_to_string(&descriptor).expect("descriptor"),
        BODY
    );
    for n in 0..6000 {
        assert_eq!(
            std::fs::read_to_string(dir.path().join(format!(".aaaa-unrelated-{n:05}")))
                .expect("unrelated survives"),
            "precious"
        );
    }
}

#[test]
#[ignore = "child process for crash_leftovers_beyond_the_cap_are_eventually_swept_on_restart"]
fn sweep_restart_child() {
    let dir = std::env::var_os("SELAHCUE_SWEEP_TEST_DIR").expect("private fixture");
    let dir = Path::new(&dir);
    sweep_stale_staging(dir, my_uid());
    // Observe real completion, with a watchdog rather than a fixed sleep. Production cleanup
    // becomes asynchronous beyond its foreground cap, and the test process must stay alive.
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let stale = (0..32).any(|n| dir.join(staging_file_name(i32::MAX as u32, n)).exists());
        if !stale {
            break;
        }
        assert!(
            Instant::now() < deadline,
            "background sweep never reached legacy leftovers"
        );
        std::thread::yield_now();
    }
}

#[test]
fn staging_namespace_is_private_idempotent_and_refuses_unsafe_existing_entries() {
    let dir = private_dir();
    let staging = prepare_staging_dir(dir.path(), my_uid()).expect("create staging");
    assert_eq!(staging, dir.path().join(STAGING_DIR_NAME));
    assert_eq!(mode_of(&staging), 0o700);
    assert_eq!(
        prepare_staging_dir(dir.path(), my_uid()).expect("idempotent"),
        staging
    );
    assert_eq!(
        prepare_staging_dir(dir.path(), my_uid().wrapping_add(1)),
        Err(DirError::WrongOwner)
    );
    set_mode(&staging, 0o755);
    assert_eq!(
        prepare_staging_dir(dir.path(), my_uid()),
        Err(DirError::TooOpen)
    );
    assert_eq!(
        mode_of(&staging),
        0o755,
        "never repair an existing directory"
    );
    std::fs::remove_dir(&staging).expect("remove");
    let target = private_dir();
    std::os::unix::fs::symlink(target.path(), &staging).expect("plant symlink");
    assert_eq!(
        prepare_staging_dir(dir.path(), my_uid()),
        Err(DirError::Symlink)
    );
    assert_eq!(std::fs::read_dir(target.path()).expect("target").count(), 0);
    std::fs::remove_file(&staging).expect("unlink");
    std::fs::write(&staging, "precious").expect("plant file");
    assert_eq!(
        prepare_staging_dir(dir.path(), my_uid()),
        Err(DirError::NotDirectory)
    );
    assert_eq!(std::fs::read_to_string(&staging).expect("file"), "precious");
    std::fs::remove_file(&staging).expect("remove file");
    assert!(
        prepare_staging_dir(dir.path(), my_uid()).is_ok(),
        "recovery after refusal"
    );
}

#[test]
fn a_failed_sweep_can_be_reentered_after_directory_permissions_are_restored() {
    let dir = private_dir();
    let stale = plant_staging(dir.path(), i32::MAX as u32, 0);
    set_mode(dir.path(), 0o755);
    assert_eq!(sweep_stale_staging(dir.path(), my_uid()), 0);
    assert!(stale.exists());
    set_mode(dir.path(), 0o700);
    assert_eq!(sweep_stale_staging(dir.path(), my_uid()), 1);
    assert!(!stale.exists());
}

// ---- the home step: a private `selahcue` directory under the user's state directory --------------

fn home_env(home: &Path, temp: &Path) -> DirEnv {
    DirEnv {
        home: Some(home.as_os_str().to_owned()),
        ..env(None, temp)
    }
}

fn state_dir_of(home: &Path) -> PathBuf {
    home.join(".local").join("state").join("selahcue")
}

fn mkdir_mode(path: &Path, mode: u32) {
    std::fs::create_dir_all(path).expect("mkdir");
    set_mode(path, mode);
}

#[test]
fn the_home_state_directory_is_used_when_nothing_better_exists() {
    let home = private_dir();
    let temp = shared_dir();

    assert_eq!(
        resolve_dir(&home_env(home.path(), temp.path())),
        state_dir_of(home.path())
    );
    assert_eq!(entries(home.path()), 0, "resolving creates nothing");
    assert_eq!(entries(temp.path()), 0);
}

#[test]
fn xdg_runtime_dir_and_a_private_temp_dir_both_beat_the_home_step() {
    let home = private_dir();
    let xdg = private_dir();
    let shared = shared_dir();
    let private_temp = private_dir();

    let mut with_xdg = home_env(home.path(), shared.path());
    with_xdg.xdg_runtime_dir = Some(xdg.path().as_os_str().to_owned());
    assert_eq!(resolve_dir(&with_xdg), xdg.path());

    assert_eq!(
        resolve_dir(&home_env(home.path(), private_temp.path())),
        private_temp.path()
    );
}

#[test]
fn preparing_creates_only_the_missing_components_0700_and_leaves_existing_ones_alone() {
    let home = private_dir();
    let temp = shared_dir();
    let local = home.path().join(".local");
    mkdir_mode(&local, 0o755);
    std::fs::write(local.join("marker"), "x").expect("marker");

    let first = prepare_dir(&home_env(home.path(), temp.path())).expect("create");

    assert_eq!(first, state_dir_of(home.path()));
    assert_eq!(mode_of(&first), 0o700);
    assert_eq!(mode_of(first.parent().expect("state")), 0o700, "created");
    assert_eq!(
        mode_of(&local),
        0o755,
        "an existing component is never changed"
    );
    assert!(local.join("marker").exists());
    assert_eq!(
        entries(temp.path()),
        0,
        "nothing was made in the shared temp dir"
    );

    std::fs::write(first.join("keep"), "x").expect("file");
    assert_eq!(
        prepare_dir(&home_env(home.path(), temp.path())).expect("reuse"),
        first
    );
    assert!(
        first.join("keep").exists(),
        "an existing directory is reused as is"
    );
}

#[test]
fn an_absolute_xdg_state_home_is_the_base_and_a_relative_or_empty_one_is_ignored() {
    let home = private_dir();
    let state = private_dir();
    let temp = shared_dir();

    let mut absolute = home_env(home.path(), temp.path());
    absolute.xdg_state_home = Some(state.path().as_os_str().to_owned());
    assert_eq!(resolve_dir(&absolute), state.path().join("selahcue"));
    let created = prepare_dir(&absolute).expect("create");
    assert_eq!(created, state.path().join("selahcue"));
    assert_eq!(mode_of(&created), 0o700);
    assert_eq!(entries(home.path()), 0, "HOME was not used");

    // Relative: a relative spelling of a directory that WOULD be a fine base (premise asserted).
    let relative = relative_to_cwd(state.path());
    assert!(relative.is_relative());
    let mut env_relative = home_env(home.path(), temp.path());
    env_relative.xdg_state_home = Some(relative.into_os_string());
    assert_eq!(resolve_dir(&env_relative), state_dir_of(home.path()));

    let mut env_empty = home_env(home.path(), temp.path());
    env_empty.xdg_state_home = Some(std::ffi::OsString::new());
    assert_eq!(resolve_dir(&env_empty), state_dir_of(home.path()));
}

#[test]
fn without_a_usable_home_the_shared_temp_last_resort_is_used() {
    let temp = shared_dir();
    let fallback = subdir_of(temp.path());
    let home = private_dir();

    for (label, value) in [
        ("unset", None),
        ("empty", Some(std::ffi::OsString::new())),
        (
            "relative",
            Some(relative_to_cwd(home.path()).into_os_string()),
        ),
    ] {
        let mut e = env(None, temp.path());
        e.home = value;
        assert_eq!(resolve_dir(&e), fallback, "HOME {label}");
    }
    assert_eq!(
        resolve_dir(&home_env(home.path(), temp.path())),
        state_dir_of(home.path()),
        "control: a usable HOME"
    );
}

#[test]
fn a_parent_that_group_or_other_can_write_to_is_not_used() {
    for mode in [0o775, 0o777, 0o757, 0o772, 0o722, 0o702] {
        let temp = shared_dir();
        let fallback = subdir_of(temp.path());

        // The nearest existing ancestor is HOME itself (nothing created yet).
        let home = private_dir();
        set_mode(home.path(), mode);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            fallback,
            "HOME mode {mode:o}"
        );

        // The parent of `selahcue` exists with that mode.
        let home = private_dir();
        let state = home.path().join(".local").join("state");
        mkdir_mode(&state, mode);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            fallback,
            "state directory mode {mode:o}"
        );
        // ... and so does an existing, otherwise perfect, `selahcue` below it.
        mkdir_mode(&state.join("selahcue"), 0o700);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            fallback,
            "existing selahcue under a parent of mode {mode:o}"
        );
    }
    // Controls: a parent that is merely readable by others is fine.
    for mode in [0o700, 0o755, 0o750] {
        let temp = shared_dir();
        let home = private_dir();
        mkdir_mode(&home.path().join(".local").join("state"), mode);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            state_dir_of(home.path()),
            "control: parent mode {mode:o}"
        );
    }
}

#[test]
fn a_parent_owned_by_someone_else_is_not_used() {
    let home = private_dir();
    let temp = shared_dir();
    let other = as_other_user(home_env(home.path(), temp.path()));
    assert_eq!(
        resolve_dir(&other),
        subdir_of_for(temp.path(), other.uid),
        "HOME belongs to another user (e.g. sudo kept HOME): skip the step"
    );
    assert_eq!(
        resolve_dir(&home_env(home.path(), temp.path())),
        state_dir_of(home.path()),
        "control: the real owner"
    );
}

#[test]
fn a_symlinked_parent_or_ancestor_is_not_used() {
    let temp = shared_dir();
    let fallback = subdir_of(temp.path());

    // `.local/state` is a symlink to a perfectly good directory of ours.
    let home = private_dir();
    let elsewhere = private_dir();
    mkdir_mode(&home.path().join(".local"), 0o700);
    std::os::unix::fs::symlink(elsewhere.path(), home.path().join(".local").join("state"))
        .expect("symlink");
    assert_eq!(resolve_dir(&home_env(home.path(), temp.path())), fallback);

    // `.local` is the symlink and `state` is missing below it (the ancestor we would create under).
    let home = private_dir();
    std::os::unix::fs::symlink(elsewhere.path(), home.path().join(".local")).expect("symlink");
    assert_eq!(resolve_dir(&home_env(home.path(), temp.path())), fallback);
    assert_eq!(
        entries(elsewhere.path()),
        0,
        "nothing created through the link"
    );
}

#[test]
fn an_existing_selahcue_that_is_not_a_private_directory_is_not_used() {
    let temp = shared_dir();
    let fallback = subdir_of(temp.path());
    for mode in [0o755, 0o750, 0o705, 0o701] {
        let home = private_dir();
        let dir = state_dir_of(home.path());
        mkdir_mode(&dir, mode);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            fallback,
            "existing selahcue at mode {mode:o}"
        );
        set_mode(&dir, 0o700);
        assert_eq!(
            resolve_dir(&home_env(home.path(), temp.path())),
            dir,
            "mode {mode:o}: control, the same directory at 0700"
        );
    }

    let home = private_dir();
    let state = home.path().join(".local").join("state");
    mkdir_mode(&state, 0o700);
    let good = private_dir();
    std::os::unix::fs::symlink(good.path(), state.join("selahcue")).expect("symlink");
    assert_eq!(resolve_dir(&home_env(home.path(), temp.path())), fallback);

    let home = private_dir();
    mkdir_mode(&home.path().join(".local").join("state"), 0o700);
    std::fs::write(state_dir_of(home.path()), "x").expect("file");
    assert_eq!(resolve_dir(&home_env(home.path(), temp.path())), fallback);
}

#[test]
fn a_state_base_under_a_plain_file_is_not_used() {
    let temp = shared_dir();
    let holder = private_dir();
    let file = holder.path().join("a-file");
    std::fs::write(&file, "x").expect("file");
    let mut e = env(None, temp.path());
    e.xdg_state_home = Some(file.join("below").into_os_string());
    assert_eq!(resolve_dir(&e), subdir_of(temp.path()));
}

#[test]
fn preparing_with_an_unusable_home_falls_back_and_touches_nothing_in_it() {
    let temp = shared_dir();
    let home = private_dir();
    set_mode(home.path(), 0o777);

    let got = prepare_dir(&home_env(home.path(), temp.path())).expect("last resort");

    assert_eq!(got, subdir_of(temp.path()));
    assert_eq!(
        entries(home.path()),
        0,
        "an unusable HOME is not written to"
    );
}

// ---- directories we create are exactly 0700, whatever the umask -----------------------------------

/// Run THIS test binary again as a child running only `child_test` (an `#[ignore]`d half), under a
/// shell prefix such as `umask 0277;` and with `env` added / `unset` removed. For code that reads
/// the real process environment or the umask: neither can be changed in the shared test process
/// without racing its siblings. Returns the child's stdout; fails unless the child really ran that
/// one test and it passed.
fn run_child(
    child_test: &str,
    shell_prefix: &str,
    env: &[(&str, &std::ffi::OsStr)],
    unset: &[&str],
) -> String {
    let exe = std::env::current_exe().expect("current exe");
    let script = format!(
        "{shell_prefix} exec \"$0\" --ignored --exact {child_test} --test-threads=1 --nocapture"
    );
    let mut command = std::process::Command::new("sh");
    command.arg("-c").arg(script).arg(exe);
    for key in unset {
        command.env_remove(key);
    }
    for (key, value) in env {
        command.env(key, value);
    }
    let out = command.output().expect("spawn child");
    let stdout = String::from_utf8_lossy(&out.stdout).into_owned();
    assert!(
        out.status.success() && stdout.contains("1 passed; 0 failed"),
        "child {child_test} did not run and pass:\n{stdout}\n{}",
        String::from_utf8_lossy(&out.stderr)
    );
    stdout
}

fn path_var(name: &str) -> PathBuf {
    PathBuf::from(std::env::var_os(name).expect("run by its parent only"))
}

/// Child half: create directories under a hostile umask and report their modes by asserting them.
#[test]
#[ignore = "child process of the hostile-umask test; run only by its parent"]
fn child_prepares_under_a_hostile_umask() {
    let temp = path_var("CHILD_TEMP");
    let home = path_var("CHILD_HOME");

    // The shared-temp last resort.
    let fallback = prepare_dir(&env(None, &temp)).expect("last resort");
    assert_eq!(mode_of(&fallback), 0o700, "last-resort directory");

    let staging = prepare_staging_dir(&fallback, my_uid()).expect("staging");
    assert_eq!(mode_of(&staging), 0o700, "staging directory");

    // The home step: every component we create.
    let created = prepare_dir(&home_env(&home, &temp)).expect("home step");
    assert_eq!(created, state_dir_of(&home));
    for dir in [
        home.join(".local"),
        home.join(".local").join("state"),
        created,
    ] {
        assert_eq!(mode_of(&dir), 0o700, "{}", dir.display());
    }
}

#[test]
fn directories_we_create_are_exactly_0700_even_under_a_hostile_umask() {
    // 0277 leaves read-only, 0400 removes owner read, and 0777 removes all access.
    // Each child starts from fresh directories, so it exercises creation rather than reuse.
    for mask in ["0277", "0400", "0777"] {
        let temp = shared_dir();
        let home = private_dir();
        run_child(
            "child_prepares_under_a_hostile_umask",
            &format!("umask {mask};"),
            &[
                ("CHILD_TEMP", temp.path().as_os_str()),
                ("CHILD_HOME", home.path().as_os_str()),
            ],
            &[],
        );
        assert_eq!(mode_of(&subdir_of(temp.path())), 0o700);
    }
}

// ---- DirEnv::current is the real environment ------------------------------------------------------

/// Child half: `DirEnv::current()` must report what the (independently supplied) EXPECT_* variables
/// say. A variable the parent did not set means "expect None".
#[test]
#[ignore = "child process of the DirEnv::current tests; run only by its parent"]
fn child_checks_dir_env_current() {
    let expected = |name: &str| std::env::var_os(name);
    let current = DirEnv::current();
    assert_eq!(current.xdg_runtime_dir, expected("EXPECT_XDG_RUNTIME"));
    assert_eq!(current.xdg_state_home, expected("EXPECT_XDG_STATE"));
    assert_eq!(current.home, expected("EXPECT_HOME"));
    if let Some(temp) = expected("EXPECT_TEMP") {
        assert_eq!(current.temp_dir, PathBuf::from(temp));
    }
    assert_eq!(
        current.uid.to_string(),
        std::env::var("EXPECT_UID").expect("run by its parent only")
    );
    if let Some(path) = expected("EXPECT_DESCRIPTOR") {
        assert_eq!(descriptor_path(), PathBuf::from(path));
    }
}

/// Child half: print what the real process environment resolves to (for the cross-check).
#[test]
#[ignore = "child process of the cross-check test; run only by its parent"]
fn child_prints_the_descriptor_path() {
    println!("DESCRIPTOR_PATH={}", descriptor_path().display());
}

#[test]
fn dir_env_current_reads_the_real_environment() {
    // The uid the kernel reports for something we just created, not the function under test.
    let probe = private_dir();
    let uid = std::fs::metadata(probe.path())
        .expect("stat")
        .uid()
        .to_string();
    let xdg = private_dir();
    let state = private_dir();
    let home = private_dir();
    let shared = shared_dir();
    let private_temp = private_dir();

    // Everything set: each variable lands in its own field, and the private XDG dir wins.
    let xdg_descriptor = xdg.path().join(DESCRIPTOR_FILE_NAME);
    run_child(
        "child_checks_dir_env_current",
        "",
        &[
            ("XDG_RUNTIME_DIR", xdg.path().as_os_str()),
            ("EXPECT_XDG_RUNTIME", xdg.path().as_os_str()),
            ("XDG_STATE_HOME", state.path().as_os_str()),
            ("EXPECT_XDG_STATE", state.path().as_os_str()),
            ("HOME", home.path().as_os_str()),
            ("EXPECT_HOME", home.path().as_os_str()),
            ("TMPDIR", shared.path().as_os_str()),
            ("EXPECT_TEMP", shared.path().as_os_str()),
            ("EXPECT_UID", uid.as_ref()),
            ("EXPECT_DESCRIPTOR", xdg_descriptor.as_os_str()),
        ],
        &[],
    );

    // A private TMPDIR is used as is; nothing else set.
    let private_descriptor = private_temp.path().join(DESCRIPTOR_FILE_NAME);
    run_child(
        "child_checks_dir_env_current",
        "",
        &[
            ("TMPDIR", private_temp.path().as_os_str()),
            ("EXPECT_TEMP", private_temp.path().as_os_str()),
            ("EXPECT_UID", uid.as_ref()),
            ("EXPECT_DESCRIPTOR", private_descriptor.as_os_str()),
        ],
        &["XDG_RUNTIME_DIR", "XDG_STATE_HOME", "HOME"],
    );

    // An EMPTY TMPDIR is /tmp, not the empty path (which would resolve against the cwd); with the
    // other variables unset they must read as None.
    run_child(
        "child_checks_dir_env_current",
        "",
        &[
            ("TMPDIR", std::ffi::OsStr::new("")),
            ("EXPECT_TEMP", std::ffi::OsStr::new("/tmp")),
            ("EXPECT_UID", uid.as_ref()),
        ],
        &["XDG_RUNTIME_DIR", "XDG_STATE_HOME", "HOME"],
    );

    // A shared TMPDIR with a usable HOME resolves to the home step, end to end.
    let want = state_dir_of(home.path()).join(DESCRIPTOR_FILE_NAME);
    run_child(
        "child_checks_dir_env_current",
        "",
        &[
            ("TMPDIR", shared.path().as_os_str()),
            ("EXPECT_TEMP", shared.path().as_os_str()),
            ("HOME", home.path().as_os_str()),
            ("EXPECT_HOME", home.path().as_os_str()),
            ("EXPECT_UID", uid.as_ref()),
            ("EXPECT_DESCRIPTOR", want.as_os_str()),
        ],
        &["XDG_RUNTIME_DIR", "XDG_STATE_HOME"],
    );
}

// ---- removing the descriptor ----------------------------------------------------------------------

#[test]
fn removing_the_descriptor_removes_it_and_tolerates_its_absence() {
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, BODY.as_bytes());

    assert_eq!(remove_descriptor(&path, my_uid()), Ok(true));
    assert!(!path.exists());
    assert_eq!(
        remove_descriptor(&path, my_uid()),
        Ok(false),
        "already gone"
    );
    assert_eq!(
        remove_descriptor(&dir.path().join("no-such-dir").join("x"), my_uid()),
        Ok(false),
        "no directory yet: nothing to remove"
    );
}

#[test]
fn removing_never_follows_a_symlinked_directory() {
    let victim_dir = private_dir();
    let victim = descriptor_in(victim_dir.path(), 0o600, b"precious");
    let holder = private_dir();
    let link = holder.path().join("dir-link");
    std::os::unix::fs::symlink(victim_dir.path(), &link).expect("symlink");

    assert_eq!(
        remove_descriptor(&link.join(DESCRIPTOR_FILE_NAME), my_uid()),
        Err(RemoveError::Dir(DirError::Symlink))
    );
    assert!(victim.exists(), "the file behind the link must survive");
    // The trailing-slash spelling of the same link is refused too.
    assert_eq!(
        remove_descriptor(
            &PathBuf::from(format!("{}/", link.display())).join(DESCRIPTOR_FILE_NAME),
            my_uid()
        ),
        Err(RemoveError::Dir(DirError::Symlink))
    );
    assert!(victim.exists());

    // Control: the same removal through the real directory works.
    assert_eq!(remove_descriptor(&victim, my_uid()), Ok(true));
}

#[test]
fn removing_from_a_directory_that_is_not_private_is_refused() {
    let dir = private_dir();
    let path = descriptor_in(dir.path(), 0o600, BODY.as_bytes());

    set_mode(dir.path(), 0o755);
    assert_eq!(
        remove_descriptor(&path, my_uid()),
        Err(RemoveError::Dir(DirError::TooOpen))
    );
    set_mode(dir.path(), 0o700);
    assert_eq!(
        remove_descriptor(&path, my_uid().wrapping_add(1)),
        Err(RemoveError::Dir(DirError::WrongOwner))
    );
    assert!(path.exists(), "refused both times");
    assert_eq!(remove_descriptor(&path, my_uid()), Ok(true), "control");
}

#[test]
fn removing_does_not_follow_a_symlink_at_the_last_component() {
    let dir = private_dir();
    let victim = dir.path().join("victim.txt");
    std::fs::write(&victim, "precious").expect("victim");
    let link = dir.path().join(DESCRIPTOR_FILE_NAME);
    std::os::unix::fs::symlink(&victim, &link).expect("symlink");

    assert_eq!(remove_descriptor(&link, my_uid()), Ok(true));
    assert!(
        std::fs::symlink_metadata(&link).is_err(),
        "the link itself is gone"
    );
    assert_eq!(
        std::fs::read_to_string(&victim).expect("victim"),
        "precious"
    );
}

#[test]
fn removing_something_that_cannot_be_unlinked_is_an_error() {
    let dir = private_dir();
    let at = dir.path().join(DESCRIPTOR_FILE_NAME);
    std::fs::create_dir(&at).expect("a directory where the file should be");
    assert_eq!(remove_descriptor(&at, my_uid()), Err(RemoveError::Failed));
}

// ---- symlinks, trailing slashes and the platform decision ------------------------------------------

#[test]
fn a_symlink_is_refused_whether_or_not_the_path_ends_in_a_slash() {
    let target = private_dir();
    let holder = private_dir();
    let link = holder.path().join("dir-link");
    std::os::unix::fs::symlink(target.path(), &link).expect("symlink");
    let slash = PathBuf::from(format!("{}/", link.display()));
    let slashes = PathBuf::from(format!("{}///", link.display()));

    for (label, path) in [
        ("plain", &link),
        ("one slash", &slash),
        ("three slashes", &slashes),
    ] {
        assert_eq!(
            verify_private_dir(path, my_uid()),
            Err(DirError::Symlink),
            "{label}: lstat(\"link/\") would follow the link"
        );
    }
    // The same through the temp-dir decision: a symlinked temp dir with a trailing slash is not
    // "already private".
    assert_eq!(
        resolve_dir(&env(None, &slash)),
        slash.join(format!("selahcue-{}", my_uid()))
    );

    // Controls: a real private directory is accepted with and without slashes.
    let real_slash = PathBuf::from(format!("{}/", target.path().display()));
    let real_slashes = PathBuf::from(format!("{}///", target.path().display()));
    for path in [target.path(), real_slash.as_path(), real_slashes.as_path()] {
        verify_private_dir(path, my_uid()).expect("a real private directory");
    }
}

#[test]
fn the_root_directory_is_judged_not_mangled() {
    // Stripping trailing separators must leave "/" alone (a real kernel-owned directory: refused
    // for its owner or its mode, never reported as missing or unreadable).
    let got = verify_private_dir(Path::new("/"), my_uid());
    assert!(
        matches!(got, Err(DirError::WrongOwner | DirError::TooOpen)) || my_uid() == 0,
        "{got:?}"
    );
}

// ---- the real kernel's idea of "another user" ------------------------------------------------------

/// A directory the kernel says belongs to someone else and that has no group or other bits, if one
/// exists here (`/root` on Linux, `/private/var/audit` and friends on macOS). The injected-uid tests prove the logic;
/// this proves the owner comparison against a uid the kernel really reports.
fn foreign_private_dir() -> Option<PathBuf> {
    [
        "/root",
        "/private/var/audit",
        "/private/var/agentx",
        "/private/var/install",
    ]
    .iter()
    .map(PathBuf::from)
    .find(|dir| {
        std::fs::symlink_metadata(dir)
            .is_ok_and(|m| m.is_dir() && m.uid() != my_uid() && m.mode() & 0o077 == 0)
    })
}

#[test]
fn a_file_the_kernel_says_belongs_to_someone_else_is_refused() {
    let hosts = Path::new("/etc/hosts");
    let Ok(meta) = std::fs::metadata(hosts) else {
        eprintln!("skipped: no /etc/hosts here");
        return;
    };
    if meta.uid() == my_uid() {
        eprintln!("skipped: /etc/hosts is ours (running as its owner)");
        return;
    }
    assert_eq!(
        read_file_as(hosts, MAX, my_uid()),
        Err(ReadError::WrongOwner)
    );
    // Control: as its real owner the owner check is passed and the NEXT check (it is world-readable)
    // is what refuses, so the line above is the owner check and not something earlier.
    assert_eq!(
        read_file_as(hosts, MAX, meta.uid()),
        Err(ReadError::WrongMode(meta.mode() & 0o7777))
    );
}

#[test]
fn a_directory_the_kernel_says_belongs_to_someone_else_is_refused() {
    let Some(dir) = foreign_private_dir() else {
        eprintln!("skipped: no root-owned 0700 directory visible here");
        return;
    };
    assert_eq!(
        verify_private_dir(&dir, my_uid()),
        Err(DirError::WrongOwner)
    );
    let owner = std::fs::symlink_metadata(&dir).expect("stat").uid();
    verify_private_dir(&dir, owner).expect("control: judged as its real owner it is private");
}

// ---- the shell tooling must agree with the Rust resolver -----------------------------------------

fn script_path() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../../scripts/endpoint_path.py")
}

/// The four environment variables the resolution reads; `None` means "unset".
#[derive(Clone, Default)]
struct Vars {
    xdg_runtime: Option<std::ffi::OsString>,
    xdg_state: Option<std::ffi::OsString>,
    home: Option<std::ffi::OsString>,
    tmpdir: Option<std::ffi::OsString>,
}

impl Vars {
    fn pairs(&self) -> [(&'static str, &Option<std::ffi::OsString>); 4] {
        [
            ("XDG_RUNTIME_DIR", &self.xdg_runtime),
            ("XDG_STATE_HOME", &self.xdg_state),
            ("HOME", &self.home),
            ("TMPDIR", &self.tmpdir),
        ]
    }
}

fn some(path: &Path) -> Option<std::ffi::OsString> {
    Some(path.as_os_str().to_owned())
}

fn script_says(vars: &Vars) -> PathBuf {
    let mut cmd = std::process::Command::new("python3");
    cmd.arg("-I").arg(script_path());
    for (name, value) in vars.pairs() {
        match value {
            Some(v) => cmd.env(name, v),
            None => cmd.env_remove(name),
        };
    }
    let out = cmd.output().expect("python3 is required by `make ci`");
    assert!(
        out.status.success(),
        "scripts/endpoint_path.py failed: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    PathBuf::from(String::from_utf8(out.stdout).expect("utf-8").trim_end())
}

/// What the real Rust pipeline (`DirEnv::current()` then `descriptor_path()`) says, in a child
/// process that has exactly `vars` as its environment variables.
fn rust_says(vars: &Vars) -> PathBuf {
    let set: Vec<(&str, &std::ffi::OsStr)> = vars
        .pairs()
        .into_iter()
        .filter_map(|(name, value)| value.as_deref().map(|v| (name, v)))
        .collect();
    let unset: Vec<&str> = vars
        .pairs()
        .into_iter()
        .filter(|(_, value)| value.is_none())
        .map(|(name, _)| name)
        .collect();
    let stdout = run_child("child_prints_the_descriptor_path", "", &set, &unset);
    // libtest prints "test NAME ... " first and the captured output follows on the same line.
    let start = stdout
        .find("DESCRIPTOR_PATH=")
        .expect("the child prints DESCRIPTOR_PATH=")
        + "DESCRIPTOR_PATH=".len();
    PathBuf::from(stdout[start..].lines().next().expect("a path"))
}

#[test]
fn make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code() {
    let xdg_ok = private_dir();
    let xdg_open = shared_dir();
    let xdg_group_only = private_dir();
    set_mode(xdg_group_only.path(), 0o750);
    let holder = private_dir();
    let xdg_file = holder.path().join("a-file");
    std::fs::write(&xdg_file, "x").expect("file");
    let link_target = private_dir();
    let link = holder.path().join("xdg-link");
    std::os::unix::fs::symlink(link_target.path(), &link).expect("symlink");
    let link_slash = PathBuf::from(format!("{}/", link.display()));
    let shared_temp = shared_dir();
    let private_temp = private_dir();
    let foreign = foreign_private_dir();

    // Home-based scenarios, each with its own HOME so none can see another's directories.
    let home_fresh = private_dir();
    let home_existing = private_dir();
    mkdir_mode(&state_dir_of(home_existing.path()), 0o700);
    let state_home = private_dir();
    let home_open_parent = private_dir();
    mkdir_mode(&home_open_parent.path().join(".local").join("state"), 0o775);
    let home_open_selahcue = private_dir();
    mkdir_mode(&state_dir_of(home_open_selahcue.path()), 0o755);
    let home_open = private_dir();
    set_mode(home_open.path(), 0o777);
    let home_symlinked = private_dir();
    mkdir_mode(&home_symlinked.path().join(".local"), 0o700);
    std::os::unix::fs::symlink(
        link_target.path(),
        home_symlinked.path().join(".local").join("state"),
    )
    .expect("symlink");

    let with_temp = |temp: &Path| Vars {
        tmpdir: some(temp),
        ..Vars::default()
    };
    let shared = shared_temp.path();
    let mut cases: Vec<(&str, Vars)> = vec![
        (
            "private xdg",
            Vars {
                xdg_runtime: some(xdg_ok.path()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg too open (0777)",
            Vars {
                xdg_runtime: some(xdg_open.path()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg with a group bit only (0750)",
            Vars {
                xdg_runtime: some(xdg_group_only.path()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg is a file",
            Vars {
                xdg_runtime: some(&xdg_file),
                ..with_temp(shared)
            },
        ),
        (
            "xdg is a symlink to a private directory",
            Vars {
                xdg_runtime: some(&link),
                ..with_temp(shared)
            },
        ),
        (
            "xdg is that symlink spelled with a trailing slash",
            Vars {
                xdg_runtime: some(&link_slash),
                ..with_temp(shared)
            },
        ),
        (
            "xdg relative",
            Vars {
                xdg_runtime: Some(".".into()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg relative but private",
            Vars {
                xdg_runtime: Some(relative_to_cwd(xdg_ok.path()).into_os_string()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg empty",
            Vars {
                xdg_runtime: Some("".into()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg missing path",
            Vars {
                xdg_runtime: some(&shared.join("nope")),
                ..with_temp(shared)
            },
        ),
        ("no xdg, shared temp", with_temp(shared)),
        ("no xdg, private temp", with_temp(private_temp.path())),
        (
            "private temp spelled with a trailing slash",
            with_temp(&PathBuf::from(format!(
                "{}/",
                private_temp.path().display()
            ))),
        ),
        (
            "temp is a symlink to a private directory, trailing slash",
            Vars {
                tmpdir: Some(link_slash.clone().into_os_string()),
                ..Vars::default()
            },
        ),
        ("TMPDIR unset", Vars::default()),
        (
            "TMPDIR empty",
            Vars {
                tmpdir: Some("".into()),
                ..Vars::default()
            },
        ),
        (
            "home, nothing created yet",
            Vars {
                home: some(home_fresh.path()),
                ..with_temp(shared)
            },
        ),
        (
            "home, selahcue exists",
            Vars {
                home: some(home_existing.path()),
                ..with_temp(shared)
            },
        ),
        (
            "xdg state home",
            Vars {
                xdg_state: some(state_home.path()),
                ..with_temp(shared)
            },
        ),
        (
            "relative xdg state home falls back to home",
            Vars {
                xdg_state: Some(relative_to_cwd(state_home.path()).into_os_string()),
                home: some(home_fresh.path()),
                ..with_temp(shared)
            },
        ),
        (
            "empty xdg state home falls back to home",
            Vars {
                xdg_state: Some("".into()),
                home: some(home_fresh.path()),
                ..with_temp(shared)
            },
        ),
        (
            "home relative",
            Vars {
                home: Some(relative_to_cwd(home_fresh.path()).into_os_string()),
                ..with_temp(shared)
            },
        ),
        (
            "home empty",
            Vars {
                home: Some("".into()),
                ..with_temp(shared)
            },
        ),
        (
            "home unset",
            Vars {
                xdg_state: None,
                ..with_temp(shared)
            },
        ),
        (
            "home state parent group-writable",
            Vars {
                home: some(home_open_parent.path()),
                ..with_temp(shared)
            },
        ),
        (
            "home selahcue too open",
            Vars {
                home: some(home_open_selahcue.path()),
                ..with_temp(shared)
            },
        ),
        (
            "home itself world-writable",
            Vars {
                home: some(home_open.path()),
                ..with_temp(shared)
            },
        ),
        (
            "home state parent is a symlink",
            Vars {
                home: some(home_symlinked.path()),
                ..with_temp(shared)
            },
        ),
        (
            "private xdg beats home",
            Vars {
                xdg_runtime: some(xdg_ok.path()),
                home: some(home_fresh.path()),
                ..with_temp(shared)
            },
        ),
        (
            "private temp beats home",
            Vars {
                home: some(home_fresh.path()),
                ..with_temp(private_temp.path())
            },
        ),
    ];
    if let Some(dir) = &foreign {
        cases.push((
            "xdg owned by root (0700)",
            Vars {
                xdg_runtime: some(dir),
                ..with_temp(shared)
            },
        ));
        cases.push((
            "home owned by root",
            Vars {
                home: some(dir),
                ..with_temp(shared)
            },
        ));
    } else {
        eprintln!("note: no root-owned 0700 directory here; the foreign-owner cases are skipped");
    }

    // A parent that is someone else's but otherwise perfectly closed (root-owned `/usr`, mode 0755,
    // searchable): only the OWNER comparison refuses it, which the mode-private foreign directory
    // above cannot show for the "parent of selahcue" rule (it is unsearchable, so lstat fails first).
    cases.push((
        "home is a searchable directory of another user",
        Vars {
            home: some(Path::new("/usr")),
            ..with_temp(shared)
        },
    ));

    let mut answers = std::collections::BTreeMap::new();
    for (label, vars) in &cases {
        let rust = rust_says(vars);
        assert_eq!(script_says(vars), rust, "{label}");
        answers.insert(*label, rust);
    }

    // Premises: the cases really cover the outcomes they claim to.
    let name = DESCRIPTOR_FILE_NAME;
    let fallback = subdir_of(shared).join(name);
    assert_eq!(answers["private xdg"], xdg_ok.path().join(name));
    for refused in [
        "xdg too open (0777)",
        "xdg with a group bit only (0750)",
        "xdg is a file",
        "xdg is a symlink to a private directory",
        "xdg is that symlink spelled with a trailing slash",
        "xdg relative",
        "xdg relative but private",
        "xdg empty",
        "xdg missing path",
        "no xdg, shared temp",
        "home relative",
        "home empty",
        "home unset",
        "home state parent group-writable",
        "home selahcue too open",
        "home itself world-writable",
        "home state parent is a symlink",
    ] {
        assert_eq!(answers[refused], fallback, "{refused}");
    }
    assert_eq!(
        answers["no xdg, private temp"],
        private_temp.path().join(name)
    );
    assert_eq!(
        answers["private temp spelled with a trailing slash"],
        PathBuf::from(format!("{}/", private_temp.path().display())).join(name)
    );
    assert_ne!(
        answers["temp is a symlink to a private directory, trailing slash"],
        link_target.path().join(name)
    );
    assert_eq!(
        answers["home, nothing created yet"],
        state_dir_of(home_fresh.path()).join(name)
    );
    assert_eq!(
        answers["home, selahcue exists"],
        state_dir_of(home_existing.path()).join(name)
    );
    assert_eq!(
        answers["xdg state home"],
        state_home.path().join("selahcue").join(name)
    );
    assert_eq!(
        answers["relative xdg state home falls back to home"],
        state_dir_of(home_fresh.path()).join(name)
    );
    assert_eq!(answers["private xdg beats home"], xdg_ok.path().join(name));
    assert_eq!(
        answers["private temp beats home"],
        private_temp.path().join(name)
    );
    if my_uid() != 0 {
        assert_eq!(
            answers["home is a searchable directory of another user"],
            fallback
        );
    }
    if let Some(dir) = &foreign {
        assert_ne!(answers["xdg owned by root (0700)"], dir.join(name));
        assert_eq!(answers["home owned by root"], fallback);
    }
}
