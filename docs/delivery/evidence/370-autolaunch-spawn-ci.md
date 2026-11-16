# Autolaunch stand-in spawn failure — issue370

Issue: https://github.com/First-Pavilion/selahcue/issues/370

The original Ubuntu operator CI41856346193 failed at `spawn_removes_a_stale_endpoint_from_a_private_directory`, after461 passed/1 failed/1 ignored. Its actual spawn OS error was discarded by `.spawn().ok()?`; the historical errno is UNKNOWN. This correction does not assert that the later controlled failure was the original cause, or that diagnostic-only success fixes it.

## Demonstrated hazard and change

A network-isolated Linux aarch64 container ran a real exec of the same freshly written/chmod0755 shell fixture while a writable descriptor remained open. It failed with actual errno26/ETXTBSY, exists=true, mode0755. A sidecar symlink to the existing system `true` executable spawned a real process and exited0. This demonstrates a concrete write/exec fixture hazard, including the kind of writable descriptor a concurrent fork can inherit; it does not prove that a concurrent fork caused the old CI failure. No sleep/retry/timeout increase was used.

The Unix stand-in now references existing `/usr/bin/true` rather than writing/chmodding a new executable. The same production Command path still launches a real child, and tests kill/wait it. The fixture asserts the target exists and is a regular executable target. Both original private stale-endpoint removal and symlink-victim survival assertions remain intact. `/bin/true` initially produced a broken symlink on macOS; metadata immediately diagnosed this setup mistake and the actual common `/usr/bin/true` path replaced it.

The private injected-wait helper now retains `io::Result<Option<SpawnedOutput>>`. The public API immediately maps errors to its existing optional fallback. No new public logging or behavior is introduced. Focused test failures report fixed phase, existence/mode, ErrorKind and raw errno, without private fixture paths or raw OS text. A real nonexecutable fixture asserts PermissionDenied and a retained errno, plus unchanged public None fallback.

## Actual verification

- RED: old fresh-written fixture failed the new no-fresh-write-exec-window contract. `/private/tmp/370-autolaunch-diagnosis/fixture-red.log` records the expected failing test (Cargo101; an outer log-display shell returned0).
- Linux real-exec diagnostic: `/private/tmp/370-autolaunch-diagnosis/probe.py` and `linux.log`. The first container setup used an invalid tmpfs option; no process probe ran until the option was corrected to `rw,exec`. No installer/Tauri/provider/model/GUI operation occurred.
- Final macOS source-exact focused harness: all10 autolaunch tests PASS, no ignored/filtered tests, real production module and real local_endpoint source linked. Pinned Rust1.98.0, locked/offline scratch dependencies seeded from the workspace lock. Harness/target: `/private/tmp/370-autolaunch-harness` and `/private/tmp/370-autolaunch-target`; log `autolaunch-final.log` in the diagnostic directory. No full operator/Ubuntu suite claim.
- Real crate `cargo +1.98.0 test --locked --offline --manifest-path implementation/desktop/Cargo.toml -p selahcue-lan --test test_local_endpoint`:63 passed/1 failed/4 existing ignored, exit101. Unchanged `any_mode_other_than_0600_is_refused` at test505 accepted mode04600 instead of WrongMode on this macOS host. This is a remaining broader regression limitation, not silently fixed or skipped. All actual symlink/private-directory/stale/sweep/subprocess controls passed. Log `endpoint-final.log`.
- The initial attempt to include the integration file as a nested module in the mini harness had59 passed/5 failed/4 ignored because self-subprocess names and manifest path depended on the real test target. That approach was abandoned; the faithful real crate result above supersedes it without hiding its failures.

## Delivery gates

Separate branch/worktree from frozen STT PR368. No workflows, dependencies, locks or STT source change. Three-iteration Goal; implementation uses iteration2, iteration3 reserved for review findings. Actual current hosted CI and independent Cody/Shadow/Quinn/Vera reviews are pending root. Native ClickUp start/backfill is pending under root's explicit implementation exception; no saved In Progress claim. All owned subprocesses finished/reaped before handoff. No performance/Windows/full-installer claim.

Proposed visible start comment: “Kenji started issue370 CI-unblock investigation on codex/370-autolaunch-spawn-ci, separate from frozen STT PR368. Goal TASK-370 max3; preserve real spawn and endpoint safety. Actual prior errno unknown; capture bounded OS-error evidence before a scoped fix. Native start/status backfill remains pending authenticated receipt.”
