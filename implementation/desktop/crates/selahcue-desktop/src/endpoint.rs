//! The loopback endpoint descriptor (17tnw2b2q2z): the small JSON file a running output window
//! publishes so the operator shell on the same machine can find and authenticate to it.
//!
//! It carries a bearer token, and the operator shell re-reads it for the life of its session
//! (`selahcue-operator`'s `read_endpoint_at`, which also refuses anything but mode `0600`). So the
//! one property that matters is that **a reader never finds the path half-written or looser than
//! `0600`**. The first cut used `std::fs::write`, which creates and truncates the final path
//! BEFORE writing and only `chmod`s afterwards: a reader in that gap saw an empty descriptor (the
//! flake that failed `the_scripture_warm_up_runs_before_the_listener_is_bound` on ubuntu CI) or, on
//! Linux where `temp_dir()` is the shared `/tmp`, a world-readable file holding the token.
//!
//! [`write_endpoint`] therefore stages the bytes in an owner-only sibling file and `rename`s it
//! over the path.

use std::io::Write;
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

/// Every staging file is `<STAGING_PREFIX>.<pid>.<n>.tmp`. The prefix is fixed (not derived from
/// the descriptor's own file name), so the staging name's length never depends on the final
/// name's: a legal name near `NAME_MAX` cannot fail with `ENAMETOOLONG` only because of the
/// staging suffix.
const STAGING_PREFIX: &str = ".selahcue-endpoint";

/// Fresh staging names tried before a publish gives up. Collisions need a hostile or crashed
/// neighbour (see [`staging_path`]), so one retry is already generous.
const MAX_STAGING_ATTEMPTS: usize = 8;

/// Windows only: antivirus and the search indexer sometimes hold a freshly written file open for
/// a moment, and `rename` over a path then fails with a sharing violation. Try a few times
/// before giving up; the previous descriptor is untouched either way (never worse than before).
const RENAME_ATTEMPTS: usize = if cfg!(windows) { 5 } else { 1 };
const RENAME_RETRY_DELAY: Duration = Duration::from_millis(20);

/// Write a local endpoint descriptor so the operator shell on this machine can
/// auto-discover + connect (a loopback-only convenience; real pairing is QR + host
/// confirmation). Values are simple ASCII (addr/hex/ids), so a hand-built JSON string is
/// safe. Returns the path written, if any.
///
/// Published ATOMICALLY and owner-only from the first byte: see the module docs and
/// [`publish_owner_only`].
pub(crate) fn write_endpoint(
    path: &Path,
    addr: SocketAddr,
    pin_hex: &str,
    device: &str,
    token: &str,
) -> Option<PathBuf> {
    let json = format!(
        "{{\"addr\":\"{addr}\",\"pin\":\"{pin_hex}\",\"device\":\"{device}\",\"token\":\"{token}\"}}"
    );
    match publish_owner_only(path, json.as_bytes()) {
        Ok(()) => Some(path.to_path_buf()),
        Err(e) => {
            eprintln!("SelahCue: could not write operator endpoint file: {e}");
            None
        }
    }
}

/// Best-effort removal on a clean exit, so a later operator shell does not try to attach to a
/// defunct window with a dead token and port.
pub(crate) fn remove(path: &Path) {
    let _ = std::fs::remove_file(path);
}

/// A fresh staging file name beside `path`: same directory (so the final rename never crosses a
/// filesystem), dot-prefixed, and unique per CALL — the pid separates processes, a process-wide
/// counter separates calls within one. A predictable per-process name let two publishers in one
/// process share a file (torn reads, failed publishes) and let another account pre-create it in a
/// sticky `/tmp` to make every publish fail.
fn staging_path(path: &Path) -> PathBuf {
    static NEXT: AtomicU64 = AtomicU64::new(0);
    let n = NEXT.fetch_add(1, Ordering::Relaxed);
    path.with_file_name(format!("{STAGING_PREFIX}.{}.{n}.tmp", std::process::id()))
}

/// Replace `path` with `contents` so that no reader ever observes a partial or a looser-than-
/// `0600` file: stage in a [`staging_path`] created owner-only with `create_new` (`O_EXCL`: a
/// planted file, directory or symlink at that name is never opened, followed or deleted; the
/// publish just moves on to a fresh name), write it fully, then `rename` it into place. On any
/// failure the staging file WE created is removed, so nothing accumulates in the shared temp
/// dir, and the previous descriptor is left as it was.
///
/// There is no `fsync`: the descriptor is ephemeral and regenerated, with a fresh token and
/// port, on every start, so losing it in a crash loses nothing. A process killed between creating
/// the staging file and renaming it leaves one `0600` dot-file holding a token that died with
/// the process; nothing sweeps it (the window is microseconds).
fn publish_owner_only(path: &Path, contents: &[u8]) -> std::io::Result<()> {
    publish_with(path, contents, &mut || staging_path(path))
}

/// [`publish_owner_only`] with the staging names injected, so a test can plant something at the
/// name the publisher will try first.
fn publish_with(
    path: &Path,
    contents: &[u8],
    next_staging: &mut dyn FnMut() -> PathBuf,
) -> std::io::Result<()> {
    let (tmp, mut file) = create_staging(next_staging)?;
    let staged = fill_staging(&mut file, contents);
    // Closed before the rename: Windows will not replace a file that is still open.
    drop(file);
    let published = staged.and_then(|()| rename_into_place(&tmp, path));
    if published.is_err() {
        let _ = std::fs::remove_file(&tmp);
    }
    published
}

/// Create a staging file that did not exist, owner-only from the first instant.
fn create_staging(
    next_staging: &mut dyn FnMut() -> PathBuf,
) -> std::io::Result<(PathBuf, std::fs::File)> {
    let mut taken = None;
    for _ in 0..MAX_STAGING_ATTEMPTS {
        let tmp = next_staging();
        let mut options = std::fs::OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        match options.open(&tmp) {
            Ok(file) => return Ok((tmp, file)),
            // Taken by something else: leave it exactly as it is and try the next name.
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => taken = Some(e),
            Err(e) => return Err(e),
        }
    }
    Err(taken.unwrap_or_else(|| std::io::ErrorKind::AlreadyExists.into()))
}

fn fill_staging(file: &mut std::fs::File, contents: &[u8]) -> std::io::Result<()> {
    // Exactly `0600` whatever the umask did to the creation mode — `selahcue-operator` refuses
    // anything else — and before any byte of the token is written.
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.set_permissions(std::fs::Permissions::from_mode(0o600))?;
    }
    file.write_all(contents)
}

fn rename_into_place(tmp: &Path, path: &Path) -> std::io::Result<()> {
    retry(
        RENAME_ATTEMPTS,
        RENAME_RETRY_DELAY,
        || std::fs::rename(tmp, path),
        |e| cfg!(windows) && is_sharing_error(e),
    )
}

/// Run `op`, retrying after `delay` while it fails with an error `transient` accepts, at most
/// `attempts` tries in all. The last error is returned as it was.
fn retry<T>(
    attempts: usize,
    delay: Duration,
    mut op: impl FnMut() -> std::io::Result<T>,
    transient: impl Fn(&std::io::Error) -> bool,
) -> std::io::Result<T> {
    let mut attempt = 1;
    loop {
        match op() {
            Err(e) if attempt < attempts && transient(&e) => {
                attempt += 1;
                std::thread::sleep(delay);
            }
            other => return other,
        }
    }
}

/// What Windows reports when another process briefly holds a file: access denied, a sharing
/// violation or a lock violation (raw codes 5, 32, 33).
fn is_sharing_error(e: &std::io::Error) -> bool {
    e.kind() == std::io::ErrorKind::PermissionDenied
        || matches!(e.raw_os_error(), Some(5 | 32 | 33))
}

/// What the tests share with `main.rs`'s warm-up tests: how to read a descriptor back.
#[cfg(test)]
pub(crate) fn json_field<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    let needle = format!("\"{key}\":\"");
    let start = json.find(&needle)? + needle.len();
    let len = json[start..].find('"')?;
    Some(&json[start..start + len])
}

/// True only for a COMPLETE descriptor: a closed object carrying all four fields.
#[cfg(test)]
pub(crate) fn is_complete_descriptor(json: &str) -> bool {
    json.starts_with('{')
        && json.ends_with('}')
        && ["addr", "pin", "device", "token"]
            .iter()
            .all(|k| json_field(json, k).is_some_and(|v| !v.is_empty()))
}

#[cfg(test)]
mod tests {
    use super::{
        create_staging, is_complete_descriptor, is_sharing_error, json_field, publish_with, remove,
        retry, staging_path, write_endpoint, MAX_STAGING_ATTEMPTS, STAGING_PREFIX,
    };
    use std::io::Read;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::Arc;
    use std::time::{Duration, Instant};

    /// A private scratch directory, removed on drop — also when an assertion unwinds.
    struct Scratch(PathBuf);

    impl Scratch {
        fn new(tag: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "selahcue-endpoint-test-{tag}-{}-{:?}",
                std::process::id(),
                std::thread::current().id()
            ));
            std::fs::create_dir_all(&dir).expect("create scratch dir");
            Scratch(dir)
        }

        fn descriptor(&self) -> PathBuf {
            self.0.join("endpoint.json")
        }

        fn entries(&self) -> usize {
            std::fs::read_dir(&self.0).expect("list scratch").count()
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            #[cfg(unix)]
            {
                // A test that made the directory read-only must not strand it.
                use std::os::unix::fs::PermissionsExt;
                let _ = std::fs::set_permissions(&self.0, std::fs::Permissions::from_mode(0o700));
            }
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    fn addr() -> std::net::SocketAddr {
        ([127, 0, 0, 1], 4242).into()
    }

    fn publish(path: &Path, token: &str) -> Option<PathBuf> {
        write_endpoint(path, addr(), "ab12", "operator-shell", token)
    }

    #[cfg(unix)]
    fn mode_of(meta: &std::fs::Metadata) -> u32 {
        use std::os::unix::fs::PermissionsExt;
        meta.permissions().mode() & 0o777
    }

    /// One look at the descriptor, the way a reader would take it: `None` if there is nothing to
    /// read, `Some(Ok)` for a complete owner-only file, `Some(Err)` with the reason otherwise.
    fn observe(path: &Path) -> Option<Result<(), String>> {
        let mut file = std::fs::File::open(path).ok()?;
        #[cfg(unix)]
        let mode = file.metadata().map(|m| mode_of(&m)).ok();
        let mut body = String::new();
        file.read_to_string(&mut body).ok()?;
        if !is_complete_descriptor(&body) {
            return Some(Err(format!("incomplete descriptor: {body:?}")));
        }
        #[cfg(unix)]
        if mode != Some(0o600) {
            return Some(Err(format!("mode {mode:?} (want 0600) on {body:?}")));
        }
        Some(Ok(()))
    }

    /// Mode of every staging file currently beside `dir`'s descriptor, as a reader would see it.
    #[cfg(unix)]
    fn loose_staging_files(dir: &Path) -> Vec<String> {
        let Ok(entries) = std::fs::read_dir(dir) else {
            return Vec::new();
        };
        entries
            .flatten()
            .filter(|e| e.file_name().to_string_lossy().starts_with(STAGING_PREFIX))
            .filter_map(|e| {
                let meta = std::fs::File::open(e.path()).ok()?.metadata().ok()?;
                (mode_of(&meta) != 0o600)
                    .then(|| format!("staging file {:?} mode {:o}", e.file_name(), mode_of(&meta)))
            })
            .collect()
    }

    /// Stops a spinning thread when dropped — also when the owner unwinds, so a failing test can
    /// never leave its reader spinning forever.
    struct StopOnDrop(Arc<AtomicBool>);

    impl Drop for StopOnDrop {
        fn drop(&mut self) {
            self.0.store(true, Ordering::Release);
        }
    }

    // ---- happy paths --------------------------------------------------------------------

    #[test]
    fn write_endpoint_publishes_a_complete_owner_only_descriptor() {
        let scratch = Scratch::new("happy");
        let path = scratch.descriptor();

        let written = publish(&path, "tok-1");
        assert_eq!(written.as_deref(), Some(path.as_path()));

        let json = std::fs::read_to_string(&path).expect("read descriptor");
        assert!(is_complete_descriptor(&json), "{json:?}");
        assert_eq!(json_field(&json, "addr"), Some("127.0.0.1:4242"));
        assert_eq!(json_field(&json, "pin"), Some("ab12"));
        assert_eq!(json_field(&json, "device"), Some("operator-shell"));
        assert_eq!(json_field(&json, "token"), Some("tok-1"));
        #[cfg(unix)]
        assert_eq!(
            mode_of(&std::fs::metadata(&path).expect("stat")),
            0o600,
            "the descriptor carries a bearer token"
        );
        assert_eq!(
            scratch.entries(),
            1,
            "no temporary file may be left beside the descriptor"
        );
    }

    #[test]
    fn publishing_again_replaces_the_previous_descriptor_completely() {
        let scratch = Scratch::new("again");
        let path = scratch.descriptor();
        // The previous descriptor is LONGER than the new one, so an in-place rewrite that forgot
        // to truncate would leave a stale tail behind.
        assert!(publish(&path, &"t".repeat(200)).is_some());
        assert!(publish(&path, "short").is_some());

        // Exact bytes. This pins the WRITER side of the layout only; the operator's reader
        // (`Endpoint` in selahcue-operator) is a separate parse with its own tests.
        assert_eq!(
            std::fs::read_to_string(&path).expect("read descriptor"),
            "{\"addr\":\"127.0.0.1:4242\",\"pin\":\"ab12\",\"device\":\"operator-shell\",\"token\":\"short\"}"
        );
        assert_eq!(scratch.entries(), 1);
    }

    /// Deterministic twin of the hammer below: a reader that already has the previous descriptor
    /// open must keep seeing that COMPLETE descriptor — never an emptied or half-rewritten one —
    /// while a new one is published. An in-place truncate-and-rewrite changes what the open
    /// handle reads; replacing the file by rename cannot. (Windows: `std` opens with delete
    /// sharing, so the replace is expected to work there too; that is exactly what this checks
    /// when CI runs it.)
    #[test]
    fn publishing_over_a_descriptor_replaces_it_rather_than_rewriting_it_in_place() {
        let scratch = Scratch::new("replace");
        let path = scratch.descriptor();

        assert!(publish(&path, "old-token").is_some());
        let before = std::fs::read_to_string(&path).expect("read first descriptor");
        let mut held = std::fs::File::open(&path).expect("open first descriptor");

        assert!(publish(&path, "new-token").is_some());

        let mut seen_by_held_handle = String::new();
        held.read_to_string(&mut seen_by_held_handle)
            .expect("read through the held handle");
        assert_eq!(
            seen_by_held_handle, before,
            "a reader holding the previous descriptor must still see it complete; the file was \
             rewritten in place instead of being replaced"
        );
        let after = std::fs::read_to_string(&path).expect("read new descriptor");
        assert!(
            is_complete_descriptor(&after) && after.contains("new-token"),
            "the path must now hold the new, complete descriptor: {after:?}"
        );
        #[cfg(unix)]
        assert_eq!(
            mode_of(&std::fs::metadata(&path).expect("stat")),
            0o600,
            "the descriptor carries a bearer token"
        );
    }

    #[test]
    fn remove_deletes_the_descriptor_and_tolerates_its_absence() {
        let scratch = Scratch::new("remove");
        let path = scratch.descriptor();
        assert!(publish(&path, "tok").is_some());

        remove(&path);
        assert!(
            !path.exists(),
            "a clean exit must not leave a stale descriptor"
        );
        remove(&path); // already gone: best-effort, must not panic
    }

    // ---- concurrency ----------------------------------------------------------------------

    /// The ticket's failure, reproduced without any server: one thread publishes the descriptor
    /// over and over (alternating "fresh path" and "replace the previous one") while another
    /// spins reading it. Written in place, a reader landing between create and write saw an
    /// EMPTY file (the ticket's `descriptor should name ... port 44879: `), or a 0644 file
    /// holding a bearer token. Published by rename, a reader sees the path absent, the previous
    /// descriptor, or the new one — each complete and owner-only — and the staging file is
    /// owner-only from the moment it exists.
    ///
    /// Nothing here asserts how long anything took on the passing side. The writer keeps going
    /// until BOTH enough publishes and enough observations (clean or not) have happened, so a
    /// starved reader cannot make the test pass vacuously; it is capped by a time budget, and a
    /// failure still reports the reader's findings before the progress check.
    #[test]
    fn a_reader_polling_the_descriptor_never_sees_a_partial_or_loose_one() {
        const MIN_PUBLISHES: usize = 1000;
        const MIN_OBSERVATIONS: usize = 300;
        const BUDGET: Duration = Duration::from_secs(60);
        /// Memory bound: the reader keeps the first few offending observations, not all of them.
        const MAX_KEPT_PROBLEMS: usize = 5;

        let scratch = Scratch::new("hammer");
        let path = scratch.descriptor();
        let stop = Arc::new(AtomicBool::new(false));
        let observations = Arc::new(AtomicUsize::new(0));

        let reader = {
            let (path, stop, observations) = (path.clone(), stop.clone(), observations.clone());
            std::thread::spawn(move || {
                let mut problems: Vec<String> = Vec::new();
                while !stop.load(Ordering::Acquire) {
                    #[cfg(unix)]
                    for loose in loose_staging_files(path.parent().expect("parent")) {
                        if problems.len() < MAX_KEPT_PROBLEMS {
                            problems.push(loose);
                        }
                    }
                    match observe(&path) {
                        None => {}
                        Some(Ok(())) => {
                            observations.fetch_add(1, Ordering::Relaxed);
                        }
                        Some(Err(why)) => {
                            observations.fetch_add(1, Ordering::Relaxed);
                            if problems.len() < MAX_KEPT_PROBLEMS {
                                problems.push(why);
                            }
                        }
                    }
                }
                problems
            })
        };
        let stopper = StopOnDrop(stop);

        let started = Instant::now();
        let mut publishes = 0usize;
        while (publishes < MIN_PUBLISHES || observations.load(Ordering::Relaxed) < MIN_OBSERVATIONS)
            && started.elapsed() < BUDGET
        {
            if publishes.is_multiple_of(2) {
                let _ = std::fs::remove_file(&path); // alternate: fresh path / replace previous
            }
            assert!(
                publish(&path, &format!("token-{publishes}")).is_some(),
                "publish #{publishes} failed"
            );
            publishes += 1;
        }
        drop(stopper);
        let problems = reader.join().expect("reader thread");

        assert!(
            problems.is_empty(),
            "a reader observed a descriptor that was not complete and owner-only: {problems:#?}"
        );
        let seen = observations.load(Ordering::Relaxed);
        assert!(
            publishes >= MIN_PUBLISHES && seen >= MIN_OBSERVATIONS,
            "the hammer did not get going within {BUDGET:?}: {publishes} publishes, \
             {seen} observations"
        );
        assert_eq!(
            scratch.entries(),
            1,
            "publishing {publishes} times must leave exactly the descriptor behind"
        );
    }

    /// Two publishers in ONE process (not a shape production has today — the server thread
    /// starts once — but the doc promises "never a partial file" unconditionally). With a
    /// per-process staging name they shared a file: torn or empty reads and failed publishes.
    #[test]
    fn two_publishers_in_one_process_never_expose_a_partial_descriptor() {
        const PER_WRITER: usize = 500;
        let scratch = Scratch::new("two-writers");
        let path = scratch.descriptor();
        let stop = Arc::new(AtomicBool::new(false));
        let observations = Arc::new(AtomicUsize::new(0));

        let reader = {
            let (path, stop, observations) = (path.clone(), stop.clone(), observations.clone());
            std::thread::spawn(move || {
                let mut problems: Vec<String> = Vec::new();
                while !stop.load(Ordering::Acquire) {
                    if let Some(seen) = observe(&path) {
                        observations.fetch_add(1, Ordering::Relaxed);
                        if let Err(why) = seen {
                            if problems.len() < 5 {
                                problems.push(why);
                            }
                        }
                    }
                }
                problems
            })
        };
        let stopper = StopOnDrop(stop);

        let writers: Vec<_> = (0..2)
            .map(|w| {
                let path = path.clone();
                std::thread::spawn(move || {
                    (0..PER_WRITER)
                        .filter(|i| publish(&path, &format!("w{w}-{i}")).is_none())
                        .count()
                })
            })
            .collect();
        let failed: usize = writers.into_iter().map(|w| w.join().expect("writer")).sum();
        drop(stopper);
        let problems = reader.join().expect("reader thread");

        assert!(problems.is_empty(), "partial or loose reads: {problems:#?}");
        assert_eq!(failed, 0, "publishes failed when two shared a process");
        assert!(
            observations.load(Ordering::Relaxed) > 0,
            "reader never saw the file"
        );
        assert_eq!(scratch.entries(), 1, "leftover staging files");
    }

    /// The constant-name regression guard: successive calls must never hand out the same name.
    #[test]
    fn every_call_gets_a_fresh_staging_name_beside_the_descriptor() {
        let path = Path::new("/some/dir/endpoint.json");
        let a = staging_path(path);
        let b = staging_path(path);
        assert_ne!(a, b, "two publishers would share one staging file");
        for name in [&a, &b] {
            assert_eq!(
                name.parent(),
                path.parent(),
                "must stay in the same directory"
            );
            let file = name.file_name().expect("file name").to_string_lossy();
            assert!(
                file.starts_with(STAGING_PREFIX) && file.ends_with(".tmp"),
                "{file}"
            );
            assert!(
                file.contains(&std::process::id().to_string()),
                "separate processes must not share a name: {file}"
            );
        }
    }

    // ---- hostile or unlucky neighbours ----------------------------------------------------

    /// Publish with `planted` as the first staging names tried, then fresh ones. Returns the
    /// publish result and how many names were asked for.
    fn publish_after(path: &Path, planted: &[PathBuf]) -> (std::io::Result<()>, usize) {
        let mut asked = 0usize;
        let mut planted = planted.iter();
        let result = publish_with(path, b"{\"complete\":\"yes\"}", &mut || {
            asked += 1;
            planted
                .next()
                .cloned()
                .unwrap_or_else(|| staging_path(path))
        });
        (result, asked)
    }

    /// Something already sits at the staging name (a crashed run, or another account in a sticky
    /// `/tmp`): the publisher must move on to a fresh name and must NOT delete or write to what
    /// it found — it is not ours.
    #[test]
    fn a_staging_name_that_is_already_taken_is_skipped_not_deleted() {
        let scratch = Scratch::new("taken");
        let path = scratch.descriptor();
        let taken = scratch.0.join(format!("{STAGING_PREFIX}.1.0.tmp"));
        std::fs::write(&taken, "someone else's file").expect("plant");

        let (result, asked) = publish_after(&path, std::slice::from_ref(&taken));

        result.expect("publish must succeed on a fresh name");
        assert_eq!(asked, 2, "one collision, then a fresh name");
        assert_eq!(
            std::fs::read_to_string(&taken).expect("planted file"),
            "someone else's file",
            "the planted file must be left exactly as found"
        );
        assert_eq!(
            std::fs::read_to_string(&path).expect("descriptor"),
            "{\"complete\":\"yes\"}"
        );
        assert_eq!(
            scratch.entries(),
            2,
            "descriptor + the planted file, nothing else"
        );
    }

    /// The security control the publish depends on: `create_new` never follows a symlink planted
    /// at the staging name in a shared `/tmp`. A `create(true).truncate(true)` open would write
    /// the bearer token through it into the victim file.
    #[cfg(unix)]
    #[test]
    fn a_symlink_planted_at_the_staging_name_is_never_followed() {
        let scratch = Scratch::new("tmp-symlink");
        let path = scratch.descriptor();
        let victim = scratch.0.join("victim.txt");
        std::fs::write(&victim, "precious").expect("victim");
        let link = scratch.0.join(format!("{STAGING_PREFIX}.1.0.tmp"));
        std::os::unix::fs::symlink(&victim, &link).expect("plant symlink");

        let (result, _) = publish_after(&path, std::slice::from_ref(&link));

        result.expect("publish must succeed on a fresh name");
        assert_eq!(
            std::fs::read_to_string(&victim).expect("victim"),
            "precious",
            "the token was written through a planted symlink"
        );
        assert!(
            std::fs::symlink_metadata(&link)
                .expect("link")
                .file_type()
                .is_symlink(),
            "the planted link must be left alone"
        );
        let json = std::fs::read_to_string(&path).expect("descriptor");
        assert_eq!(json, "{\"complete\":\"yes\"}");
        assert_eq!(mode_of(&std::fs::metadata(&path).expect("stat")), 0o600);
    }

    /// A directory at the staging name is just another taken name.
    #[test]
    fn a_directory_at_the_staging_name_is_skipped_and_left_intact() {
        let scratch = Scratch::new("tmp-dir");
        let path = scratch.descriptor();
        let dir = scratch.0.join(format!("{STAGING_PREFIX}.1.0.tmp"));
        std::fs::create_dir_all(dir.join("sub")).expect("plant dir");

        let (result, _) = publish_after(&path, std::slice::from_ref(&dir));

        result.expect("publish must succeed on a fresh name");
        assert!(
            dir.join("sub").is_dir(),
            "the planted directory must be untouched"
        );
        assert_eq!(
            std::fs::read_to_string(&path).expect("descriptor"),
            "{\"complete\":\"yes\"}"
        );
    }

    /// Every name the publisher is willing to try is taken: it must give up with the
    /// `AlreadyExists` error after exactly `MAX_STAGING_ATTEMPTS` names, and leave both the
    /// previous descriptor and the planted files as they were.
    #[test]
    fn running_out_of_staging_names_fails_cleanly_after_a_bounded_number_of_tries() {
        let scratch = Scratch::new("exhausted");
        let path = scratch.descriptor();
        assert!(publish(&path, "old").is_some());
        let old = std::fs::read_to_string(&path).expect("old descriptor");
        let taken: Vec<PathBuf> = (0..MAX_STAGING_ATTEMPTS)
            .map(|i| scratch.0.join(format!("{STAGING_PREFIX}.1.{i}.tmp")))
            .collect();
        for t in &taken {
            std::fs::write(t, "taken").expect("plant");
        }

        let (result, asked) = publish_after(&path, &taken);

        let err = result.expect_err("no free staging name");
        assert_eq!(err.kind(), std::io::ErrorKind::AlreadyExists);
        assert_eq!(asked, MAX_STAGING_ATTEMPTS, "the retry must be bounded");
        assert_eq!(std::fs::read_to_string(&path).expect("descriptor"), old);
        assert!(
            taken.iter().all(|t| t.exists()),
            "planted files must survive"
        );
        assert_eq!(scratch.entries(), 1 + MAX_STAGING_ATTEMPTS);
    }

    /// The destination is itself a symlink: the link is replaced by the new regular file and the
    /// file it pointed at is not written.
    #[cfg(unix)]
    #[test]
    fn a_symlink_at_the_final_path_is_replaced_not_followed() {
        let scratch = Scratch::new("final-symlink");
        let victim = scratch.0.join("victim.txt");
        std::fs::write(&victim, "precious").expect("victim");
        let path = scratch.descriptor();
        std::os::unix::fs::symlink(&victim, &path).expect("plant symlink");

        assert!(publish(&path, "tok").is_some());

        assert_eq!(
            std::fs::read_to_string(&victim).expect("victim"),
            "precious"
        );
        assert!(!std::fs::symlink_metadata(&path)
            .expect("descriptor")
            .file_type()
            .is_symlink());
        assert!(is_complete_descriptor(
            &std::fs::read_to_string(&path).expect("descriptor")
        ));
    }

    // ---- failure paths --------------------------------------------------------------------

    #[test]
    fn a_publish_that_cannot_complete_returns_none_and_leaves_nothing_behind() {
        // The directory is missing: nothing can be created, nothing is returned.
        let scratch = Scratch::new("failure");
        let missing = scratch.0.join("no-such-dir").join("endpoint.json");
        assert!(publish(&missing, "tok").is_none());
        assert!(!missing.exists());

        // The staging file IS created but the final rename fails (the destination is a
        // non-empty directory): the staging file must be cleaned up and the directory left
        // untouched.
        let blocked = scratch.descriptor();
        std::fs::create_dir_all(&blocked).expect("make destination a directory");
        std::fs::write(blocked.join("keep"), "x").expect("make it non-empty");
        assert!(publish(&blocked, "tok").is_none());
        assert!(blocked.is_dir() && blocked.join("keep").exists());
        let names: Vec<_> = std::fs::read_dir(&scratch.0)
            .expect("list scratch")
            .map(|e| e.expect("entry").file_name())
            .collect();
        assert_eq!(
            names,
            [std::ffi::OsString::from("endpoint.json")],
            "a failed publish must not leave its staging file behind"
        );
    }

    /// A read-only directory: the publish fails, the previous descriptor survives, and no
    /// staging file is left. (Skipped when the process can write anyway, e.g. as root.)
    #[cfg(unix)]
    #[test]
    fn an_unwritable_directory_returns_none_and_keeps_the_previous_descriptor() {
        use std::os::unix::fs::PermissionsExt;
        let scratch = Scratch::new("read-only");
        let path = scratch.descriptor();
        assert!(publish(&path, "old").is_some());
        let old = std::fs::read_to_string(&path).expect("old descriptor");
        std::fs::set_permissions(&scratch.0, std::fs::Permissions::from_mode(0o500))
            .expect("make read-only");
        if std::fs::File::create(scratch.0.join("probe")).is_ok() {
            eprintln!("skipped: this process can write to a 0500 directory (root?)");
            return;
        }

        let result = publish(&path, "new");

        std::fs::set_permissions(&scratch.0, std::fs::Permissions::from_mode(0o700))
            .expect("restore");
        assert!(
            result.is_none(),
            "publishing into a read-only directory must fail"
        );
        assert_eq!(std::fs::read_to_string(&path).expect("descriptor"), old);
        assert_eq!(scratch.entries(), 1, "no staging file may be left");
    }

    // ---- sizes ------------------------------------------------------------------------------

    #[test]
    fn a_descriptor_larger_than_a_page_is_written_exactly() {
        let scratch = Scratch::new("big");
        let path = scratch.descriptor();
        let token = "t".repeat(1 << 20);
        assert!(publish(&path, &token).is_some());

        let json = std::fs::read_to_string(&path).expect("descriptor");
        assert!(is_complete_descriptor(&json));
        assert_eq!(json_field(&json, "token").map(str::len), Some(1 << 20));
    }

    /// The staging name must not grow with the final name: a legal 245-character name used to
    /// fail because the staging name added a dozen characters of its own.
    #[test]
    fn a_final_name_near_name_max_still_publishes() {
        let scratch = Scratch::new("long-name");
        let path = scratch.0.join(format!("{}.json", "e".repeat(240)));
        assert!(publish(&path, "tok").is_some());
        assert!(path.exists());
        assert_eq!(scratch.entries(), 1);
    }

    #[test]
    fn staging_file_creation_is_owner_only_and_new() {
        let scratch = Scratch::new("create");
        let mut names = vec![scratch.0.join("a.tmp")].into_iter();
        let (path, file) = create_staging(&mut || names.next().expect("one name")).expect("create");
        #[cfg(unix)]
        assert_eq!(mode_of(&file.metadata().expect("stat")), 0o600);
        drop(file);
        assert_eq!(path, scratch.0.join("a.tmp"));
    }

    // ---- the Windows rename retry (logic runs everywhere, with no sleeping) --------------------

    #[test]
    fn a_transient_failure_is_retried_until_it_succeeds() {
        let mut calls = 0;
        let result = retry(
            5,
            Duration::ZERO,
            || {
                calls += 1;
                if calls < 3 {
                    Err(std::io::ErrorKind::PermissionDenied.into())
                } else {
                    Ok(calls)
                }
            },
            is_sharing_error,
        );
        assert_eq!(result.expect("third try succeeds"), 3);
    }

    #[test]
    fn a_persistent_failure_gives_up_after_exactly_the_attempt_budget() {
        let mut calls = 0;
        let result: std::io::Result<()> = retry(
            5,
            Duration::ZERO,
            || {
                calls += 1;
                Err(std::io::ErrorKind::PermissionDenied.into())
            },
            is_sharing_error,
        );
        assert_eq!(
            result.expect_err("never succeeds").kind(),
            std::io::ErrorKind::PermissionDenied
        );
        assert_eq!(calls, 5);
    }

    #[test]
    fn a_failure_that_is_not_transient_is_not_retried() {
        let mut calls = 0;
        let result: std::io::Result<()> = retry(
            5,
            Duration::ZERO,
            || {
                calls += 1;
                Err(std::io::ErrorKind::NotFound.into())
            },
            is_sharing_error,
        );
        assert!(result.is_err());
        assert_eq!(calls, 1, "NotFound is not a sharing problem");
    }

    #[test]
    fn sharing_errors_are_recognised_by_kind_and_by_windows_code() {
        assert!(is_sharing_error(
            &std::io::ErrorKind::PermissionDenied.into()
        ));
        assert!(is_sharing_error(&std::io::Error::from_raw_os_error(32))); // sharing violation
        assert!(is_sharing_error(&std::io::Error::from_raw_os_error(33))); // lock violation
        assert!(!is_sharing_error(&std::io::ErrorKind::NotFound.into()));
        assert!(!is_sharing_error(&std::io::Error::other("boom")));
    }

    // ---- other processes and the OS (unix) ---------------------------------------------------------

    /// Run THIS test binary again as a child, running only `child_test`, optionally under a
    /// shell prefix such as `umask 0400;`. Fails unless the child really ran that one test and
    /// it passed: `--exact` with a wrong name would "pass" with zero tests.
    #[cfg(unix)]
    fn run_child(child_test: &str, shell_prefix: &str, env: &[(&str, &Path)]) {
        let exe = std::env::current_exe().expect("current exe");
        let script = format!(
            "{shell_prefix} exec \"$0\" --exact endpoint::tests::{child_test} --test-threads=1"
        );
        let mut command = std::process::Command::new("sh");
        command.arg("-c").arg(script).arg(exe);
        for (key, value) in env {
            command.env(key, value);
        }
        let out = command.output().expect("spawn child");
        let stdout = String::from_utf8_lossy(&out.stdout);
        assert!(
            out.status.success() && stdout.contains("1 passed; 0 failed"),
            "child {child_test} did not run and pass:\n{stdout}\n{}",
            String::from_utf8_lossy(&out.stderr)
        );
    }

    /// Child half: when asked, publish under whatever umask the parent set and check the mode.
    #[cfg(unix)]
    #[test]
    fn child_publishes_under_a_hostile_umask() {
        let Some(path) = std::env::var_os("ENDPOINT_TEST_UMASK_PATH") else {
            return; // not running as the child
        };
        let path = PathBuf::from(path);
        assert!(publish(&path, "tok").is_some());
        assert_eq!(mode_of(&std::fs::metadata(&path).expect("stat")), 0o600);
    }

    /// The explicit `chmod` after creation: with `umask 0400` the creation mode `0600` comes out
    /// as `0200` (no owner read), so only the explicit set makes the file the exact `0600` the
    /// operator shell insists on.
    #[cfg(unix)]
    #[test]
    fn the_descriptor_is_exactly_0600_even_under_a_hostile_umask() {
        let scratch = Scratch::new("umask");
        let path = scratch.descriptor();
        run_child(
            "child_publishes_under_a_hostile_umask",
            "umask 0400;",
            &[("ENDPOINT_TEST_UMASK_PATH", &path)],
        );
        assert_eq!(
            mode_of(&std::fs::metadata(&path).expect("the child must have published")),
            0o600
        );
    }

    /// Child half of the disk-full test: runs under a 512-byte file-size limit.
    #[cfg(unix)]
    #[test]
    fn child_publishes_when_the_disk_is_full() {
        let Some(path) = std::env::var_os("ENDPOINT_TEST_FULL_PATH") else {
            return;
        };
        let path = PathBuf::from(path);
        assert!(publish(&path, "old").is_some(), "a small descriptor fits");
        let before = std::fs::read_to_string(&path).expect("old descriptor");

        let result = publish(&path, &"x".repeat(4000));

        assert!(result.is_none(), "a write beyond the size limit must fail");
        assert_eq!(std::fs::read_to_string(&path).expect("descriptor"), before);
        assert_eq!(
            std::fs::read_dir(path.parent().expect("parent"))
                .expect("list")
                .count(),
            1,
            "a failed write must not leave its staging file behind"
        );
    }

    /// A write that fails midway (`EFBIG`, which is what a full disk looks like to `write_all`
    /// here): the previous descriptor survives and the half-written staging file is removed.
    #[cfg(unix)]
    #[test]
    fn a_write_that_fails_midway_keeps_the_previous_descriptor_and_leaves_no_staging_file() {
        let scratch = Scratch::new("full");
        let path = scratch.descriptor();
        run_child(
            "child_publishes_when_the_disk_is_full",
            "trap '' XFSZ; ulimit -f 1;",
            &[("ENDPOINT_TEST_FULL_PATH", &path)],
        );
    }

    /// Child half of the two-process test: publish until the parent creates the stop file.
    #[cfg(unix)]
    #[test]
    fn child_publishes_until_stopped() {
        let (Some(path), Some(stop), Some(id)) = (
            std::env::var_os("ENDPOINT_TEST_PATH"),
            std::env::var_os("ENDPOINT_TEST_STOP"),
            std::env::var("ENDPOINT_TEST_ID").ok(),
        ) else {
            return;
        };
        let (path, stop) = (PathBuf::from(path), PathBuf::from(stop));
        let started = Instant::now();
        let mut failed = 0usize;
        let mut n = 0usize;
        while !stop.exists() && started.elapsed() < Duration::from_secs(60) {
            if publish(&path, &format!("c{id}-{n}")).is_none() {
                failed += 1;
            }
            n += 1;
        }
        assert_eq!(failed, 0, "child {id}: {failed} of {n} publishes failed");
    }

    /// Two real output-window processes publishing into the same place at once: every
    /// observation complete and owner-only, no failed publish, no staging file left.
    #[cfg(unix)]
    #[test]
    fn two_processes_publishing_at_once_never_expose_a_partial_descriptor() {
        const MIN_OBSERVATIONS: usize = 300;
        let scratch = Scratch::new("two-procs");
        let stop_dir = Scratch::new("two-procs-stop");
        let path = scratch.descriptor();
        let stop = stop_dir.0.join("stop");

        let exe = std::env::current_exe().expect("current exe");
        let spawn = |id: &str| {
            std::process::Command::new(&exe)
                .args([
                    "--exact",
                    "endpoint::tests::child_publishes_until_stopped",
                    "--test-threads=1",
                ])
                .env("ENDPOINT_TEST_PATH", &path)
                .env("ENDPOINT_TEST_STOP", &stop)
                .env("ENDPOINT_TEST_ID", id)
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .spawn()
                .expect("spawn child")
        };
        let (a, b) = (spawn("1"), spawn("2"));

        let started = Instant::now();
        let mut observations = 0usize;
        let mut problems: Vec<String> = Vec::new();
        while observations < MIN_OBSERVATIONS && started.elapsed() < Duration::from_secs(60) {
            match observe(&path) {
                None => {}
                Some(Ok(())) => observations += 1,
                Some(Err(why)) => {
                    observations += 1;
                    if problems.len() < 5 {
                        problems.push(why);
                    }
                }
            }
        }
        std::fs::write(&stop, "stop").expect("stop file");
        for (name, child) in [("1", a), ("2", b)] {
            let out = child.wait_with_output().expect("child");
            let stdout = String::from_utf8_lossy(&out.stdout);
            assert!(
                out.status.success() && stdout.contains("1 passed; 0 failed"),
                "publisher {name} failed:\n{stdout}\n{}",
                String::from_utf8_lossy(&out.stderr)
            );
        }

        assert!(problems.is_empty(), "partial or loose reads: {problems:#?}");
        assert!(
            observations >= MIN_OBSERVATIONS,
            "only {observations} observations"
        );
        assert_eq!(scratch.entries(), 1, "leftover staging files");
    }
}
