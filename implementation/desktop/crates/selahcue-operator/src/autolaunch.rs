//! Auto-launch of the native audience output window bundled beside the operator.
//!
//! In a packaged install the operator ships `selahcue-output(.exe)` as a sibling binary and
//! starts it on launch, then connects over the loopback endpoint file (the same file a
//! hand-started output window writes). This keeps the ADR-0002/0003 two-process model: the
//! console never renders audience output; it drives a separate native compositor process.
//!
//! In a dev run (`cargo run` / `make operator`) the sibling binary does not exist next to the
//! operator's `target/` executable, so [`spawn_output_window`] returns `None` and today's
//! behaviour (connect to a separately-launched window, else the demo backend) is unchanged.

use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;

/// The bundled output-window binary that should sit beside the operator executable.
pub fn output_sidecar_path(operator_exe: &Path) -> PathBuf {
    let name = format!("selahcue-output{}", std::env::consts::EXE_SUFFIX);
    match operator_exe.parent() {
        Some(dir) => dir.join(name),
        None => PathBuf::from(name),
    }
}

/// Poll `ready` up to `max_attempts` times, calling `on_wait` between attempts. Returns `true`
/// as soon as `ready()` is true, else `false`. Clock-free so it is deterministically testable;
/// the real caller passes a filesystem check + a `thread::sleep`.
pub fn wait_for_endpoint(
    mut ready: impl FnMut() -> bool,
    max_attempts: u32,
    mut on_wait: impl FnMut(),
) -> bool {
    for attempt in 0..max_attempts {
        if ready() {
            return true;
        }
        if attempt + 1 < max_attempts {
            on_wait();
        }
    }
    false
}

/// Handle to the spawned output window so the operator can terminate it on exit (no orphan
/// process). [`SpawnedOutput::kill`] is best-effort and safe to call more than once.
pub struct SpawnedOutput {
    child: Mutex<Option<Child>>,
}

impl SpawnedOutput {
    pub fn kill(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

/// Start the bundled output window (packaged install only) and wait briefly for its loopback
/// endpoint file to appear, so the operator's subsequent `build_backend()` connects instead of
/// falling back to the demo. Returns `None` when the sibling binary is absent (dev run) or the
/// spawn fails — the caller then keeps today's behaviour.
pub fn spawn_output_window(operator_exe: &Path, endpoint: &Path) -> Option<SpawnedOutput> {
    spawn_output_window_with(operator_exe, endpoint, 66, Duration::from_millis(150))
        .ok()
        .flatten()
}

/// [`spawn_output_window`] with the wait for the endpoint injected (66 attempts of 150 ms, about 10 s,
/// in production), so a test can run the real spawn path without waiting that long.
/// Keep the actual spawn error for focused diagnostics; the public API preserves its optional
/// fallback without logging paths or OS error text.
fn spawn_output_window_with(
    operator_exe: &Path,
    endpoint: &Path,
    max_attempts: u32,
    pause: Duration,
) -> std::io::Result<Option<SpawnedOutput>> {
    let sidecar = output_sidecar_path(operator_exe);
    if !sidecar.exists() {
        // Dev run: leave any endpoint written by a hand-started output window untouched.
        return Ok(None);
    }
    // Remove any stale endpoint from a previous run so we only ever connect to THIS instance. Only
    // from a directory that is private to this user: a symlink planted where the directory should
    // be is refused, not followed to delete a file of someone else's choosing (17tnw2b9agb).
    if let Err(why) = selahcue_lan::local_endpoint::remove_descriptor(
        endpoint,
        selahcue_lan::local_endpoint::current_uid(),
    ) {
        eprintln!(
            "SelahCue operator: left the endpoint file at {} alone ({why}).",
            endpoint.display()
        );
    }
    let child = Command::new(&sidecar).spawn()?;
    let appeared = wait_for_endpoint(
        || endpoint.exists(),
        max_attempts,
        || std::thread::sleep(pause),
    );
    if !appeared {
        eprintln!(
            "SelahCue operator: output window started but wrote no endpoint yet; \
             using the demo backend until it connects."
        );
    }
    Ok(Some(SpawnedOutput {
        child: Mutex::new(Some(child)),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;
    use std::path::Path;

    #[test]
    fn sidecar_sits_beside_the_operator_exe() {
        let got = output_sidecar_path(Path::new("/opt/selahcue/selahcue-operator"));
        let want = format!(
            "/opt/selahcue/selahcue-output{}",
            std::env::consts::EXE_SUFFIX
        );
        assert_eq!(got, Path::new(&want));
    }

    #[test]
    fn wait_returns_true_as_soon_as_ready_and_stops_polling() {
        let calls = Cell::new(0u32);
        let waits = Cell::new(0u32);
        // false, false, true -> ready on the 3rd check
        let ok = wait_for_endpoint(
            || {
                let n = calls.get() + 1;
                calls.set(n);
                n >= 3
            },
            10,
            || waits.set(waits.get() + 1),
        );
        assert!(ok);
        assert_eq!(calls.get(), 3, "stops checking once ready");
        assert_eq!(waits.get(), 2, "waits only between checks");
    }

    #[test]
    fn wait_gives_up_after_max_attempts() {
        let waits = Cell::new(0u32);
        let ok = wait_for_endpoint(|| false, 3, || waits.set(waits.get() + 1));
        assert!(!ok);
        assert_eq!(waits.get(), 2, "no wait after the final failed check");
    }

    #[test]
    fn wait_with_zero_attempts_is_false() {
        assert!(!wait_for_endpoint(|| true, 0, || {}));
    }

    #[test]
    fn spawn_returns_none_when_no_sidecar_present() {
        // A temp dir with no selahcue-output binary beside the fake operator exe.
        let dir = std::env::temp_dir().join(format!("selahcue-autolaunch-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let fake_operator = dir.join(format!("selahcue-operator{}", std::env::consts::EXE_SUFFIX));
        let endpoint = dir.join("selahcue-operator-endpoint.json");
        assert!(spawn_output_window(&fake_operator, &endpoint).is_none());
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// A stand-in output window that exits at once, beside a fake operator executable, so the real
    /// spawn path runs. `bin` must be a fresh directory.
    #[cfg(unix)]
    fn fake_sidecar(bin: &Path) -> PathBuf {
        let sidecar = bin.join(format!("selahcue-output{}", std::env::consts::EXE_SUFFIX));
        // A freshly written executable can fail exec with ETXTBSY on Linux while a
        // writable descriptor survives in a concurrently forked process. Reference an
        // existing immutable executable instead; Command still spawns a real child.
        std::os::unix::fs::symlink("/usr/bin/true", &sidecar).expect("sidecar symlink");
        assert!(
            sidecar.is_file(),
            "immutable stand-in executable must exist"
        );
        bin.join(format!("selahcue-operator{}", std::env::consts::EXE_SUFFIX))
    }

    #[cfg(unix)]
    #[test]
    fn stand_in_uses_an_existing_executable_without_a_fresh_write_exec_window() {
        let bin = private_dir();
        let operator = fake_sidecar(bin.path());
        let sidecar = output_sidecar_path(&operator);
        assert!(
            std::fs::symlink_metadata(&sidecar)
                .expect("fixture metadata")
                .file_type()
                .is_symlink(),
            "stand-in must reference an existing executable, not freshly write one"
        );
        assert_eq!(
            std::fs::read_link(&sidecar).expect("fixture target"),
            Path::new("/usr/bin/true")
        );
    }

    #[cfg(unix)]
    fn stand_in_spawn_failed(operator: &Path, error: std::io::Error) -> ! {
        use std::os::unix::fs::PermissionsExt;
        let sidecar = output_sidecar_path(operator);
        let mode = std::fs::metadata(&sidecar)
            .ok()
            .map(|m| m.permissions().mode() & 0o777);
        // Fixed phase + metadata only, never the private fixture path or raw error text.
        panic!(
            "stand-in phase=spawn exists={} mode={mode:?} kind={:?} errno={:?}",
            sidecar.exists(),
            error.kind(),
            error.raw_os_error()
        );
    }

    #[cfg(unix)]
    fn private_dir() -> tempfile::TempDir {
        use std::os::unix::fs::PermissionsExt;
        let dir = tempfile::tempdir().expect("tempdir");
        std::fs::set_permissions(dir.path(), std::fs::Permissions::from_mode(0o700))
            .expect("chmod");
        dir
    }

    /// Startup removes the previous run's descriptor so the operator only connects to THIS host,
    /// but only from a private directory. Here the descriptor path runs through a symlink to a
    /// directory holding a file of that name; following the link would delete it.
    #[cfg(unix)]
    #[test]
    fn spawn_never_follows_a_symlinked_directory_to_delete_a_stale_endpoint() {
        let bin = private_dir();
        let operator = fake_sidecar(bin.path());
        let victim_dir = private_dir();
        let victim = victim_dir.path().join("selahcue-operator-endpoint.json");
        std::fs::write(&victim, "precious").expect("victim");
        let holder = private_dir();
        let link = holder.path().join("dir-link");
        std::os::unix::fs::symlink(victim_dir.path(), &link).expect("symlink");

        let spawned = spawn_output_window_with(
            &operator,
            &link.join("selahcue-operator-endpoint.json"),
            1,
            Duration::ZERO,
        )
        .unwrap_or_else(|error| stand_in_spawn_failed(&operator, error))
        .expect("the stand-in sidecar is present");
        spawned.kill();

        assert_eq!(
            std::fs::read_to_string(&victim).expect("victim"),
            "precious"
        );
    }

    /// The internal diagnostic preserves the real OS error; the public optional
    /// fallback stays unchanged. Never fabricate a successful spawn on an error path.
    #[cfg(unix)]
    #[test]
    fn nonexecutable_sidecar_preserves_spawn_error_and_public_fallback() {
        use std::os::unix::fs::PermissionsExt;
        let bin = private_dir();
        let operator = bin.path().join("selahcue-operator");
        let sidecar = output_sidecar_path(&operator);
        std::fs::write(&sidecar, "not executable").expect("write negative fixture");
        std::fs::set_permissions(&sidecar, std::fs::Permissions::from_mode(0o600)).expect("chmod");
        let endpoint = bin.path().join("endpoint.json");
        let error = match spawn_output_window_with(&operator, &endpoint, 1, Duration::ZERO) {
            Err(error) => error,
            Ok(_) => panic!("nonexecutable sidecar unexpectedly spawned"),
        };
        assert_eq!(error.kind(), std::io::ErrorKind::PermissionDenied);
        assert!(error.raw_os_error().is_some(), "retain the actual OS errno");
        assert!(spawn_output_window(&operator, &endpoint).is_none());
    }

    /// Positive control for the test above: the same spawn on a real private directory does remove
    /// the stale descriptor, so "survived" above is the directory check, not a dead removal.
    #[cfg(unix)]
    #[test]
    fn spawn_removes_a_stale_endpoint_from_a_private_directory() {
        let bin = private_dir();
        let operator = fake_sidecar(bin.path());
        let dir = private_dir();
        let stale = dir.path().join("selahcue-operator-endpoint.json");
        std::fs::write(&stale, "stale").expect("stale");

        let spawned = spawn_output_window_with(&operator, &stale, 1, Duration::ZERO)
            .unwrap_or_else(|error| stand_in_spawn_failed(&operator, error))
            .expect("the stand-in sidecar is present");
        spawned.kill();

        assert!(
            !stale.exists(),
            "a stale descriptor in a private directory is removed"
        );
    }

    #[test]
    fn spawn_leaves_a_live_endpoint_alone_when_no_sidecar_present() {
        // Dev run (`make output` + `make operator`): no sibling binary, so an endpoint written by
        // a hand-started output window must survive — deleting it would strand the console on the
        // demo backend.
        let dir =
            std::env::temp_dir().join(format!("selahcue-autolaunch-ep-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let fake_operator = dir.join(format!("selahcue-operator{}", std::env::consts::EXE_SUFFIX));
        let endpoint = dir.join("selahcue-operator-endpoint.json");
        std::fs::write(&endpoint, "{}").expect("seed endpoint");
        assert!(spawn_output_window(&fake_operator, &endpoint).is_none());
        assert!(endpoint.exists(), "a live endpoint must not be removed");
        let _ = std::fs::remove_dir_all(&dir);
    }
}
