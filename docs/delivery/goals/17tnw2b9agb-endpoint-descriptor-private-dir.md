# Goal Contract — 17tnw2b9agb-endpoint-descriptor-private-dir

## Identity

- Goal ID: 17tnw2b9agb-endpoint-descriptor-private-dir
- Parent goal ID: NONE
- Title: The endpoint descriptor (a bearer token) is published and read in a per-user private directory, and the operator's reader can no longer be hung, redirected or fooled by a FIFO, a symlink or another account's file
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9agb
- Created: 2026-10-26
- Updated: 2026-10-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The output window (host) publishes a small JSON file holding a loopback address, a certificate pin
and a bearer token; the operator shell reads it to auto-connect. Today both use
`std::env::temp_dir().join("selahcue-operator-endpoint.json")`, which on Linux is the shared,
world-writable `/tmp`. After this change:

- the host and the operator resolve ONE per-user private directory through ONE shared module and
  use only that directory for the descriptor and its staging files;
- the operator's reader cannot be blocked, redirected or fooled by what sits at that path: it opens
  with `O_NONBLOCK` and `O_NOFOLLOW`, then judges the OPEN descriptor (regular file, owned by the
  current user, mode exactly `0600`, bounded size) and never blocks on a FIFO;
- a staging file left by a crashed host is removed on the next start, and only if it is ours;
- the descriptor's own cleanup (the host's clean exit, the packaged operator's startup) refuses to
  follow a planted symlink where the directory should be, and the host removes exactly the path it
  published;
- on a Linux session without `XDG_RUNTIME_DIR` the descriptor lives in the user's own home
  (`selahcue` under the XDG state directory), where no other account can create the name, and only
  falls back to a name in the shared `/tmp` when there is no usable home;
- a Windows rename that fails with a sharing error is retried briefly (already true on `main`; this
  goal keeps it, pins it and widens the pause a little, see Baseline).

## Baseline

Verified by reading origin/main `3ab74050` (the ticket's line numbers are stale; the code moved):

- Host path: `selahcue-desktop/src/main.rs` `endpoint_path()` (about line 5084) is
  `std::env::temp_dir().join("selahcue-operator-endpoint.json")`. It is used by
  `ServerEnv::production_from` (about line 4146) and by the clean-exit `endpoint::remove`.
- Operator path: `selahcue-operator/src/main.rs` `endpoint_file_path()` (about line 5590), the same
  expression; also handed to `autolaunch::spawn_output_window` (about line 10693).
- Reader: `read_endpoint_at` (about line 5644) uses `std::fs::File::open(path)`. It follows a
  symlink, opens blocking (a FIFO planted at the path blocks `open(2)` forever), checks the mode and
  the size on the open descriptor but NOT the file type and NOT the owner. It runs on the Tauri
  main thread from `setup()` through `block_on(build_backend())`, and again from the async `view`
  command whenever a reconnect is due.
- Writer: `selahcue-desktop/src/endpoint.rs` (PR #219 and its two review rounds) already stages the
  bytes in an owner-only sibling file created with `O_EXCL`, then renames it over the descriptor.
  The staging name is `.selahcue-endpoint.PID.N.tmp` (not the `.selahcue-operator-endpoint.json.PID.tmp`
  the ticket names; that older shape is gone). In the shared `/tmp` another account can still make the
  publish fail by pre-creating the final name or all eight staging names (verified by the existing
  hostile-neighbour tests, which pin "fail cleanly after eight names").
- A crash between staging and rename leaves `.selahcue-endpoint.PID.N.tmp` (mode `0600`, dead token).
  Nothing sweeps it. (The doc comment in `publish_owner_only` says so.)
- Windows rename retry: ALREADY PRESENT. `endpoint.rs` has `RenamePolicy` (5 attempts, 20 ms apart,
  Windows only), `retry`, and `is_sharing_error` (kind `PermissionDenied` or raw codes 5, 32, 33),
  with unit tests that run on every platform. The ticket's fourth item was met by PR #219's review
  rounds. It sleeps 4 x 20 ms = 80 ms in total.
- The descriptor is not on the wire and the mobile app never reads it: a grep of `implementation/mobile`,
  `implementation/api`, `implementation/marketing` and `implementation/web` for `operator-endpoint` and
  `endpoint.json` finds nothing. The cross-language protocol fixtures are not involved.
- Other readers of the same path: `Makefile` (`ENDPOINT :=`, used by `make launch`, `make remote`),
  `scripts/measure_nfr.sh` (`make nfr`, which CI runs on ubuntu under xvfb), both computed with
  Python as `tempfile.gettempdir()/selahcue-operator-endpoint.json`. These would stop finding the
  descriptor on Linux after the move unless they follow it.
- Crate layout: `selahcue-desktop` and `selahcue-operator` both depend on `selahcue-lan` (the operator
  to host link crate), so one module there can serve both. `selahcue-lan` has `#![forbid(unsafe_code)]`,
  and no crate in the tree depends directly on `libc` or `rustix`; `rustix` 1.1.4 is already in both
  lock files (it arrives through `tempfile`).

## Inputs and evidence sources

- ClickUp 17tnw2b9agb (description and acceptance criteria); found by Shadow reviewing PR #219 (17tnw2b2q2z).
- `implementation/desktop/crates/selahcue-desktop/src/endpoint.rs`, `main.rs` (`ServerIo`, `run_server`, `endpoint_path`).
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (`read_endpoint_at`, `endpoint_file_path`, `build_backend`, `maybe_reconnect_from`), `autolaunch.rs`.
- `Makefile`, `scripts/measure_nfr.sh`, `scripts/check_nfr_token_leak.py`.
- `rustix` 1.1.4 API (safe wrappers for `geteuid`, `OFlags`, `mknodat`, `kill(pid, 0)`), already vendored in the cargo registry cache.

## Scope

### In scope

- New module `selahcue_lan::local_endpoint` (one shared implementation, used by host and operator):
  directory resolution, private-directory creation and verification, file and staging names, the
  hardened read, the stale-staging sweep. Platform-independent logic takes its inputs as parameters
  (environment, current uid, clock, pid-liveness) so every refusal is testable on macOS.
- Host: publish only into a verified private directory; sweep stale staging files first; the
  production target is resolved lazily (`EndpointFile::PerUser`) so constructing the production
  environment in a test creates nothing.
- Operator: `endpoint_file_path()` and `read_endpoint_at` delegate to the shared module; autolaunch
  uses the same path.
- Dev tooling follows the move: `scripts/endpoint_path.py` mirrors the resolution, `Makefile` and
  `scripts/measure_nfr.sh` call it, and a Rust test runs it against the Rust resolver on the same
  inputs so the two cannot drift.
- Windows rename retry: keep, pin, and widen the total pause to 400 ms (see Risks for why this is a
  judgement, not a measurement).
- Round 2 (three reviews of `c9f779f4`): `local_endpoint::remove_descriptor` and its use by the host's
  clean exit (the path the server recorded) and the operator's autolaunch; the home step
  (`$XDG_STATE_HOME` or `$HOME/.local/state`, then `selahcue`) with `DirEnv.home`/`xdg_state_home`
  and the Python mirror; trailing separators stripped before `lstat`; the symlink refusal under
  `cfg(unix)` only; a directory we create set to exactly `0700` after `mkdir`; `DirEnv::current` and
  the host/operator wrappers tested in child processes with a controlled environment; the Darwin
  unset-`TMPDIR` case in the Python mirror; setuid/setgid/sticky modes refused; a real-kernel foreign
  owner test; no wall-clock assertions.
- Tests as listed in the predicate; mutation-verified.

### Non-goals

- A fallback that reads the old shared `/tmp/selahcue-operator-endpoint.json` on Linux. That is the
  attack. Old and new builds simply do not find each other (see Risks).
- Moving to `openat`/`renameat` against a held directory descriptor. The directory is private (our
  uid, no group or other bits), so nobody else can swap entries inside it between our check and our
  use; the only parent we do not control is the sticky shared temp directory, in which another
  account cannot rename or remove our entry. Stated honestly under Risks.
- Dev tooling that uses the path does NOT verify the directory's owner: `make launch` and
  `scripts/measure_nfr.sh` run `rm -f "$ENDPOINT"`, `make remote` and `make nfr` read it. They run as
  the same user as the host, in a developer's shell, on the path the Python mirror prints; they were
  left as they are (round-2 review F1, owner-approved scope). A planted symlinked directory could make
  `rm -f` delete a file the invoking developer can delete. `make remote` also puts the token in argv
  (pre-existing; separate ticket).
- Windows ACL ownership checks. Windows keeps the per-user `%TEMP%` location and the ACL it inherits
  (the ticket's own statement); no owner or mode check exists there.
- Removing the legacy file a pre-change host may have left in the shared `/tmp`.
- Any change to the wire protocol, a pinned fixture, the mobile app or the operator's `dist/` frontend.

### Constraints

- No `unsafe` (the crate forbids it); the only new dependency edge is `rustix` (`std`, `fs`, `process`)
  on Unix, which adds NO new package to either lock file.
- Memory and work stay bounded: the read is capped, the sweep examines a fixed number of directory
  entries, the staging-name search keeps its existing limit of 8.
- Logs and errors are label-only: a path and a fixed reason, never the descriptor's contents or the token.
- Existing tests are not weakened or deleted. Where one pinned the old location or relied on a world-readable scratch directory
  it is updated and listed in the PR.

### Assumptions and unknowns

- VERIFIED: the mobile app does not read the descriptor (grep above).
- ASSUMED: no external tool outside this repo reads `temp_dir()/selahcue-operator-endpoint.json`.
- UNKNOWN: Linux and Windows behaviour is not run here (this machine is macOS). Every Linux-specific branch is
  exercised through injected inputs; the real `/run/user/UID` and the shared `/tmp` are not touched. The `cfg(windows)`
  code is not compiled locally (no Windows target is installed and none may be added).

## Dependencies and approvals

- None blocking. The orchestrator runs the four-reviewer gate, marks the PR ready and moves the ticket; this goal ends at a Draft PR.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The directory is resolved by one shared function. Order on Unix: (1) a valid `XDG_RUNTIME_DIR` (absolute, a real directory not a symlink, owned by the current uid, no group or other bits); (2) the temp dir when it is itself private (macOS); (3) `selahcue` under an absolute `XDG_STATE_HOME`, else `HOME/.local/state` (absolute `HOME`), when that directory is private and its parent (or, when missing, the nearest existing ancestor) is a real directory of ours that group and other cannot write to; (4) only otherwise the `selahcue-UID` last resort in a shared temp dir. Each invalid candidate is ignored, each paired with a positive control | `cargo test -p selahcue-lan --test test_local_endpoint` | tests pass, each refusal paired with a positive control | `test_local_endpoint` 62 passed, 0 failed, 3 ignored (the ignored three are child processes run by their parents), exit 0. Round-2 RED: 14 of 62 failed against the round-1 module plus stubs for the new API. Mutants killed (round 2): H1 home step never (12 RED), H2 missing ancestor unchecked (5), H3 existing parent unchecked (1), H4 group-writable parent accepted (2), H5 parent owner unchecked (1), H6 symlinked parent accepted (2), H7 `XDG_STATE_HOME` ignored (2), H8 wrong sub-path (13), H9 relative accepted (4), H10 creation order (3), H11 directory name (12); round 1 L8 to L15 as before | PASS |
| C-002 | yes | Directories we create (the home step's missing components and the last resort) are created `0700` and then set to exactly `0700` (a hostile umask `0277` must not leave `0400`), existing components are never changed, and every directory is verified (lstat style, trailing separators stripped) before every use; one that exists with another owner, a wide mode, as a symlink (also spelled with a trailing slash) or as a plain file is not used and nothing is created inside it; creating is idempotent | same command | tests pass | same file. Hostile umask run in a child process under `umask 0277` (RED without the chmod: U1 2 RED, U2 chmod to 0750 6 RED). Trailing slash: symlink refused with 0, 1 and 3 trailing slashes, a real private directory still accepted with them, `/` not mangled (T1 2 RED, T2 1 RED). Round-1 mutants L16, L17 as before. SURVIVORS, all race-only: H12 and H13 (the ancestor and final-parent re-checks inside `create_state_dir` only matter if something changes between `resolve` and `create`, and `resolve` already filters) and U3 (`chmod` of an EXISTING directory on `AlreadyExists`, reachable only if the directory appears between the check and the `mkdir`) | PASS |
| C-003 | yes | The reader refuses, promptly and without blocking: a planted FIFO (also one with a writer attached, also mode `0600` and ours), a symlink whose target is a valid owned `0600` file, a file owned by another user (injected uid), any mode other than `0600`, a directory, an oversized file, non-UTF-8 bytes, and a file inside a directory that is not private; a valid file is read (positive control for each) | same command, plus the operator tests `read_endpoint_at` family | tests pass; the FIFO tests carry a watchdog so a regression fails instead of hanging | lan: FIFO, FIFO with a valid descriptor parked in it, symlink, dangling symlink, foreign owner (file half via `read_file_as`; the full read via the directory; a real-kernel foreign owner `/etc/hosts` that passes the owner check only for its real owner and is then refused on mode), 11 wrong modes now including setuid, setgid and sticky `0o4600 0o2600 0o1600` (M1: mask `0o777` instead of `0o7777`, 1 RED), directory, oversize at limit and over, non-UTF-8, directory not private (4 modes), symlinked directory. Operator: FIFO (the base reader BLOCKED: `did not return within 5 s`), symlink, uid handed through, private directory. No wall-clock assertion remains (the 5 s watchdog is the only bound). Round-1 mutants L1 to L7, L27, O1 to O3 as before. SURVIVOR L28 (`take(max_len)` removed): defence in depth against growth between fstat and read, not deterministically testable | PASS |
| C-004 | yes | The host publishes only into a private directory it owns: a scratch directory that is too open, or owned by another uid (injected), makes the publish fail with nothing created and the previous descriptor untouched; the production target is created and verified lazily; host write then reader read round-trips in one private directory | `cargo test -p selahcue-desktop endpoint` and the `ServerEnv` tests | tests pass | desktop `endpoint` filter and the production wiring: 43 passed, 3 ignored, 0 failed; full workspace 1987 passed, 0 failed, 9 ignored (exit 0). Round-1 mutants H1 to H6 of that round as before. Round 2: the host publishes through the production target in a CHILD process whose environment has `XDG_RUNTIME_DIR` set (E8: the server ignoring XDG, 2 RED) and cleans up exactly what it published (R1f: cleanup removes the re-resolved path, 2 RED; R1g: the server does not record the path, 2 RED) | PASS |
| C-005 | yes | A stale staging file left by a crash is removed on the next publish; a staging file of a live process, a foreign-owned one, a symlink, a directory, a name that does not parse and the descriptor itself are left alone; the sweep examines a bounded number of entries | `cargo test -p selahcue-lan --test test_local_endpoint` and `cargo test -p selahcue-desktop endpoint` | tests pass | unchanged from round 1 (lan sweep tests, host `publishing_sweeps_a_crash_leftover_and_nothing_else`; mutants L18 to L26b, H2 and H3 of round 1); stale files in the home directory are swept the same way | PASS |
| C-006 | yes | The Windows rename retry is bounded (5 attempts, at most 500 ms of sleeping), retries only sharing-type errors, is platform-independent logic unit-tested with fake errors, and the production policy is pinned | `cargo test -p selahcue-desktop endpoint` | tests pass; the `cfg(windows)` half is NOT compiled or run here | The retry already existed (`RenamePolicy`, `retry`, `is_sharing_error`, unit tests on every platform); this goal pins the budget on every platform (`the_windows_rename_budget_is_five_attempts_and_a_few_hundred_milliseconds`: 5 attempts, 300 to 500 ms of sleeping) and widens the pause 20 ms to 100 ms. Mutants killed: H5a (20 ms, 1 RED), H5b (5 s, 2), H6 (1 attempt, 1). The `cfg(windows)` classifier branch and the real Windows rename are NOT compiled or run here | PASS |
| C-007 | yes | `scripts/endpoint_path.py` (used by `make launch`, `make remote`, `make nfr`) resolves to the same path as the REAL Rust pipeline (`DirEnv::current()` then `descriptor_path()`, run in a child process with the same four environment variables) on every case: private/too open (0777)/group bit only (0750)/file/symlink/symlink with a trailing slash/relative/relative but private/empty/missing XDG_RUNTIME_DIR, shared and private temp, a temp dir spelled with a trailing slash, TMPDIR unset (macOS: the Darwin user temp dir via confstr) and empty, the home step in six shapes, HOME unset/relative/empty, and the foreign owner comparison against a real root-owned directory and a searchable root-owned HOME | the Rust cross-check test, plus running the script by hand | test passes | `make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code` passes on 33 environments (31 where no root-owned 0700 directory exists to use as a foreign owner; exit 0). Mutants killed on the script: P1 no confstr, P2 group-writable parent accepted, P3 no XDG_STATE_HOME, P4 empty TMPDIR kept, P5 trailing slash followed, P6 private check without owner, P7 wrong home sub-path, P8 parent owner unchecked (1 RED each; P8 first SURVIVED and drove the searchable-foreign-HOME case). The script is mirrored by hand; the test is what keeps it honest. Dev tooling does not verify the directory owner (Non-goals) | PASS |
| C-008 | yes | Host and operator both use the shared module; the operator's reader is exercised through its own entry point (FIFO, symlink, foreign owner, positive controls) | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` default and `--features dev-keys,openai-notes` | tests pass | operator tests 432 passed (default) and 446 passed (`dev-keys,openai-notes`), 0 failed, 1 ignored (the child half), exit 0 both. The operator's wrapper is pinned against the REAL environment: a child process with `XDG_RUNTIME_DIR` set must find the operator reading the descriptor from inside it (E9: the wrapper replaced by its own `temp_dir().join(..)`, 2 RED; the round-1 survivor O4 is dead). Autolaunch: a stale descriptor is removed from a private directory (control) and NOT through a symlinked directory (R1h: plain `remove_file`, 1 RED). `tempfile::tempdir()` is 0755 so the operator's own descriptor tests start from a 0700 directory | PASS |
| C-009 | yes | No wire fixture, mobile file or operator frontend file changed; no new package in either lock file; `cargo deny check licenses sources bans` and `cargo audit` are clean for both roots | `git diff --stat origin/main`, `git diff origin/main -- Cargo.lock`, cargo deny, cargo audit | only the `selahcue-lan` dependency list entries change in the lock files | `git diff origin/main -- implementation/mobile implementation/desktop/crates/selahcue-lan/tests/test_protocol.rs implementation/desktop/crates/selahcue-operator/dist` is empty. Lock files: `implementation/desktop/Cargo.lock` gains `rustix 1.1.4` and `tempfile` as dependencies of `selahcue-lan`; the operator lock gains `rustix`; no package added. `cargo deny check licenses sources bans`: ok for both roots (exit 0); `cargo audit`: exit 0 for both, only the allowed warnings that were already there (ttf-parser, chacha20 and others) | PASS |
| C-010 | yes | Format, lint, tests and guards are green with exit codes captured to files | `cargo fmt --check` (workspace and operator), clippy `-D warnings` (workspace; operator default and `dev-keys,openai-notes`), `cargo test --no-fail-fast` (workspace; operator both feature sets), `sh scripts/import_guards.sh`, `python3 scripts/check_launch_reachability.py` | every exit code 0 (`make ci` itself is NOT run) | Round 2 head: fmt 0/0 (workspace, operator); clippy `-D warnings` workspace `--all-targets` 0, `selahcue-lan --features server` 0, operator default 0, operator `dev-keys,openai-notes` 0; tests: workspace 1987 passed 0 failed 9 ignored, `selahcue-lan --features server` 202 passed 3 ignored, operator 432 and 446 passed 1 ignored; `scripts/import_guards.sh` 0; `scripts/check_launch_reachability.py` 0. The dependency set did not change in round 2 (lock files identical to round 1), so cargo deny and cargo audit were not re-run. `make ci` was NOT run | PASS |
| C-011 | yes | Branch is up to date with `origin/main` and the Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; state DRAFT | `git rev-list --count HEAD..origin/main` printed 0 at origin/main 3ab74050; Draft PR recorded in the PR itself | PASS |
| C-012 | yes | `remove_descriptor` removes the descriptor only after its directory verifies private for the user; a planted symlink where the directory should be (also spelled with a trailing slash) is refused and the file behind it survives; a directory of another user, or one that is too open, is refused; nothing at the path or no directory is not an error; a symlink at the LAST component is removed itself, never followed; something that cannot be unlinked is an error. The host's clean exit removes exactly the path its server recorded (never a re-resolved one, so a host that published nothing removes nothing), and the operator's autolaunch uses it | `cargo test -p selahcue-lan --test test_local_endpoint`; `cargo test -p selahcue-desktop -- endpoint the_host_publishes`; operator `autolaunch` tests | tests pass, each refusal paired with a positive control | lan 5 removal tests; host `clean_exit_removal_never_follows_a_symlinked_directory` and `..._leaves_a_directory_owned_by_someone_else_alone`; operator `spawn_never_follows_a_symlinked_directory_to_delete_a_stale_endpoint` and its control. Mutants killed: R1 (2 RED), R1b (1), R1c (1), R1d (2), R1e (1), R1f (2), R1g (2), R1h (1) | PASS |
| C-013 | yes | `DirEnv::current()` reads the real environment: `XDG_RUNTIME_DIR`, `XDG_STATE_HOME`, `HOME` honoured, `TMPDIR` empty treated as `/tmp`, a private `TMPDIR` used as is, the uid is the effective uid, and the resulting `descriptor_path()` is right; the host and operator wrappers are exercised against that environment without `set_var` in the shared test process (child processes re-executing the test binary) | the same lan test file; host and operator child-process tests | tests pass | `dir_env_current_reads_the_real_environment` runs four children with different environments; host `the_host_publishes_into_xdg_runtime_dir_and_cleans_up_exactly_what_it_published`; operator `the_operator_reads_the_descriptor_from_xdg_runtime_dir`. Mutants killed: E1 to E7 (3 RED each), E8 (2), E9 (2) | PASS |
| C-014 | yes | The symlink refusal is Unix-only (Windows keeps its directory-only behaviour; a junctioned `%TEMP%` is not refused), expressed as a pure decision `judge_dir_kind(is_symlink, is_dir, refuse_symlinks)` plus `REFUSE_SYMLINKED_DIRS = cfg!(unix)` that is tested on every platform; no Windows-only test is added | same lan test file | tests pass | `only_unix_refuses_a_symlinked_directory_and_the_decision_is_pure`; mutants W1 (constant false, 5 RED) and W2 (decision ignores the flag, 1 RED). The Windows build is NOT compiled here | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Design decisions (and why)

1. One shared module in `selahcue-lan`, not two copies. Both consumers already depend on that crate, it
   forbids `unsafe`, and a single definition makes "host and operator agree" structural. Two copies would need
   a drift test; one definition needs none. (The Python mirror for shell tooling does need one, see C-007.)
2. `rustix` rather than `libc`: `geteuid`, `kill(pid, 0)` and the open flags are safe calls there, so the
   crate keeps `forbid(unsafe_code)`. It is already in both lock files, so no new package enters the supply chain.
3. Directory rule on Unix, in order: (1) a valid `XDG_RUNTIME_DIR`; (2) the temp directory when it is itself
   private (the macOS shape, where `$TMPDIR` is already `0700` and owned by the user, so macOS keeps its
   location byte for byte); (3) the home step: a `0700` `selahcue` directory under an absolute `XDG_STATE_HOME`,
   else `HOME/.local/state`; (4) only when there is no usable home, a `selahcue-UID` subdirectory of the temp
   directory (the Linux `/tmp` last resort). One rule, no per-OS branches, and a `TMPDIR=/tmp` override on
   macOS is caught the same way as Linux. The rule is a pure function of the environment and the file system
   (the Python mirror and the operator compute it without creating anything), so processes that see the same
   environment agree.
4. Validity of a directory is judged with `lstat` after stripping trailing separators (a symlink is refused,
   never followed; `lstat("link/")` would follow it, and macOS `$TMPDIR` ends in a slash), owner equal to the
   effective uid, and `mode & 0o077 == 0`. A directory WE create is then set to exactly `0700` through an
   `O_NOFOLLOW | O_DIRECTORY` file descriptor (`fchmod`), so a hostile umask (`0277`) cannot leave a `0400`
   directory we can never use; an existing directory is never changed. (Superseding round 1, which left this
   unfixed.) The symlink refusal itself is Unix-only: on Windows a symlinked or junctioned `%TEMP%` is a normal
   setup and the previous behaviour (directory check only, the link followed) is kept, via a pure, tested
   decision function and a constant, with no Windows-only test.
5. Create-then-verify race: `mkdir` is atomic and either creates a directory owned by us or fails with
   `EEXIST`; whoever won, the following `lstat` check decides. Inside the sticky shared temp directory another
   account cannot rename or remove an entry we own, and cannot add entries to a directory that is `0700` and ours.
   A hostile account that pre-creates `/tmp/selahcue-UID` first makes us fail closed (nothing published, nothing
   read): a denial of service for local auto-connect, not a disclosure or a redirect. Round 2 moves that last resort
   behind the home step, so it is reached only when there is no usable home: unset or relative `HOME`, a state
   parent owned by someone else or writable by group or other (a home created with `umask 002` is skipped and
   falls through), a symlinked parent, or a `selahcue` entry that is not a private directory.
6. Reader order of checks: verify the parent directory, `open(O_RDONLY, O_NOFOLLOW, O_NONBLOCK, O_CLOEXEC)`, then
   `fstat` the OPEN descriptor (type, owner, mode, size), then a capped read. A FIFO opens at once under
   `O_NONBLOCK` and is refused on its type, so no path can block.
7. Mode `0600` EXACTLY is kept for the reader (what it enforced already), not "no group or other bits".
8. Stale sweep rule: only inside the verified directory; only regular files (lstat) owned by us; only names
   that parse as `.selahcue-endpoint.PID.N.tmp`; removed when the pid is not a live process OR the file is older
   than 60 s. The pid test alone would never clean a leftover under a recycled pid (including our own); the age
   test alone would leave a fresh crash leftover until a minute passed. A live publisher's in-flight file (our
   pid, microseconds old) is never touched. At most 4096 directory entries are examined.
9. `EndpointFile::PerUser` resolves lazily inside the server thread, so building `ServerEnv::production()` in a
   test has no side effect.
10. Windows: unchanged location (`%TEMP%`, per-user), no owner or mode check, directory-exists check only; the reader
    still refuses non-regular files and bounds the size. The rename retry already existed. `pid_is_alive` is always
    `true` there, so a crash leftover is swept only once it is older than 60 s: weaker than Unix, where a dead pid is
    swept at once.
11. Cleanup (round 2, Shadow F1). `remove_descriptor` removes only after `verify_private_dir(parent)` passes and never
    follows a symlink at the last component. The host removes exactly the path its server recorded in
    `RemoteShared.endpoint` when it published (a host that published nothing removes nothing, and one host cannot
    delete another's descriptor), and the operator's autolaunch uses the same function for the previous run's
    descriptor. The dev tooling's `rm -f` is left as it is (Non-goals).
12. The home step (round 2, Cody Minor 1), what was thought through:
    - It is the only way the first acceptance criterion ("another account cannot create the name") can hold on a
      Linux session without `XDG_RUNTIME_DIR`: no other account can create an entry in a `0700` home, or in a
      parent that group and other cannot write to.
    - Creation: missing components (`.local`, `.local/state`, `selahcue`) are created `0700`, each set to exactly
      `0700`, top down, only the ones we create; the nearest existing ancestor must be a real directory (lstat) owned
      by us that group and other cannot write to, else the step is skipped. An existing component is never changed.
    - A stale descriptor can persist in the home after a crash (a tmpfs would not keep it). The host removes it on a
      clean exit, the next publish overwrites it, the sweep removes leftover staging files, and a dead token fails
      the connect, which falls back to the manual path. The descriptor carries the certificate pin, so a stranger who
      now owns that port is never sent the token: the pinned TLS handshake fails first.
    - `HOME` and `XDG_STATE_HOME` are environment-controlled; the process already runs as the user, so this adds no
      attacker capability. A borrowed `HOME` (for example `sudo` that keeps it) fails the owner check and skips the step.
    - Shared homes: on a home shared between machines (NFS) two machines running a host overwrite each other's
      descriptor and an operator may read the other machine's. The descriptor is then useless rather than dangerous
      (loopback address plus a pin that will not match). A graphical login normally has `XDG_RUNTIME_DIR` (step 1), so
      the home step is for headless and ssh sessions. Modes are only as good as the file system enforcing them.
    - Version skew: unchanged. On Linux an old host (publishes in `/tmp`) and a new operator do not find each other,
      and the reverse; no fallback reads the old name. Old and new both land in the same place on macOS and Windows.
    - The two processes must see the same `XDG_RUNTIME_DIR`, `XDG_STATE_HOME`, `HOME` and `TMPDIR`.
13. Tests that read the real process environment (`DirEnv::current`, the host's server wiring, the operator's path
    wrapper) run in a child process started with a controlled environment: the shared test process cannot call
    `set_var` without racing its siblings, and a test that compares a wrapper with the function it calls cannot fail
    on macOS, where `$TMPDIR` is already private. The mutants that died to this (round-1 survivor O4, Quinn M33 to M35)
    are in the matrix.

## Verification plan

- Focused verification: the new tests (C-001 to C-014), each mutation-verified by applying one mutant at a time and running the
  whole test file with its siblings (never `--exact`), then restoring byte-identical (`cmp`).
- Broader regression verification: the full workspace and operator suites, fmt, clippy in every feature set the CI uses, the
  import guards and the launch-reachability check.
- Independent verifier: the orchestrator's four-reviewer gate (code, performance, security, QA) after this goal ends at a Draft PR.
- Required environment: macOS worktree `w2-r2`, cargo with `CARGO_INCREMENTAL=0`, `/opt/homebrew/bin` on `PATH`.

## Iteration ledger

### Iteration 0

- Target criterion: all (baseline)
- Hypothesis: the reader blocks on a FIFO and follows a symlink on the unmodified code, and the host publishes into a directory of any mode.
- Change or investigation: read the code at `3ab74050`, listed every consumer of the path, found the Windows retry already present.
- Verifier executed: none yet (tests are written first, see the next iteration).
- Result: baseline recorded above.
- Decision: iterate

### Iteration 1

- Target criterion: C-001 to C-008 (write the failing tests first)
- Hypothesis: against the old behaviour the FIFO test blocks, the symlink and wrong-owner tests pass through, a too-open directory is published into, and nothing sweeps.
- Change or investigation: a scaffold `local_endpoint` (public surface, old behaviour) and the host scaffold (`EndpointFile`, `publish_to`, `publish_owner_only_as` ignoring their new inputs); the operator RED run used the BASE reader (`git show HEAD:` plus the new tests).
- Verifier executed: `cargo test -p selahcue-lan --test test_local_endpoint`; `cargo test -p selahcue-desktop -- endpoint production_publishes`; the operator `endpoint_guard_tests` filter.
- Result: RED as predicted. lan 31 of 39 failed (the FIFO test reported `the call did not return within 5s: it blocked`); host 8 of 40 failed; operator 4 of 10 failed (`did not return within 5 s: it blocked on the planted file`). The cross-check test failed for the right reason (no script).
- New evidence: `rustix` has no `mknodat` on macOS, so the tests make FIFOs with the standard `mkfifo` tool; `mkfifo` and `tempfile::tempdir()` both honour the umask (`0644`, `0755`), which the tests had to correct before their premises held.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-009
- Hypothesis: the shared module plus the host and operator wiring turn every test green without touching an existing assertion.
- Change or investigation: the real `local_endpoint`, host `publish_owner_only_as`/`publish_to`/`EndpointFile`, operator reader and path delegating to the module, `scripts/endpoint_path.py`, Makefile and `measure_nfr.sh`.
- Verifier executed: the same three commands, then the mutation matrix.
- Result: GREEN after three test corrections (the file-owner check was unreachable behind the directory check, so `read_file_as` was split out; a `Scratch` and a `tempdir` had to be made `0700`; the relative-XDG test now uses a relative spelling of a private directory that verifies). 46 mutants run, 44 killed, 2 survivors accounted for (L28 and O4; the Python mirror's own owner comparison could not be mutated into anything a test can see, see C-007).
- New evidence: mutant L26 (the age constant) SURVIVED the first version of the sweep test, which aged a file "by the constant plus 30 s"; absolute ages and a pinned range fixed it. This is the `implementation/desktop/CLAUDE.md` trap "a control that guards another control reads a copy".
- Decision: iterate (gates, then PR)

### Iteration 3

- Target criterion: C-009 to C-011
- Hypothesis: the change touches no wire fixture, no frontend and no new package; the gates stay green.
- Change or investigation: fmt, clippy in four configurations, tests in five, the guard scripts, cargo deny and cargo audit for both roots.
- Verifier executed: see C-009 and C-010.
- Result: all exit codes 0 (a first clippy run failed on a constant assertion in the new test and on two items only tests use; fixed).
- Decision: handoff (Draft PR; the orchestrator runs the reviews)

### Iteration 4 (review round 2 of c9f779f4: Shadow PASS WITH CONDITIONS, Cody PASS WITH CONDITIONS, Quinn PASS)

- Target criterion: C-001 to C-003, C-007, C-008, C-012 to C-014
- Hypothesis: the seven MUST items and the SHOULD items in the coordinator's list are closed by `remove_descriptor`, the home step, a Unix-only symlink refusal, trailing-separator stripping, an explicit `0700` after `mkdir`, and child-process tests of the environment wiring.
- Change or investigation: as listed in Scope. Order honestly: the production changes were written before the new tests this round, so the RED evidence was produced afterwards: the lan tests against the round-1 module plus stubs of the new API (14 of 62 failed), and the host and operator tests by mutants that restore the old behaviour (R1d, R1f, R1g, R1h, E8, E9 each RED). That is weaker than test-first and is stated here rather than hidden.
- Verifier executed: the lan, desktop and operator test commands, the 46-mutant round-2 matrix, then the full gate list.
- Result: GREEN. 43 of 46 mutants killed; 3 survivors, all race-only (H12, H13, U3). P8 (the Python mirror's parent-owner check) first SURVIVED and drove a new case (a searchable root-owned HOME).
- New evidence: (1) `std::env::temp_dir()` on macOS with `TMPDIR` unset is the Darwin user temp dir (verified with a one-line Rust program), so Shadow F6 is correct and the Python mirror now uses `confstr` through `ctypes`; (2) the mutation harness had a defect: restoring a file with `copy2` kept its OLD mtime, so cargo kept the previous mutant's build and a later mutant of another crate ran against it (the Python mutants ran against an M1-mutated lan test binary, and the host mutants R1d to R1g and E8 against a lan mutated by the preceding mutant). Found because `any_mode_other_than_0600_is_refused` failed on mutants that cannot touch it. Fixed (`os.utime` after the restore) and every affected mutant was re-run; the round-1 matrix had the same defect, but its cross-crate transitions only followed the harmless survivor L28, so its results stand; (3) `cargo fmt --all` in the workspace does NOT format the excluded operator crate: it needs its own `cargo fmt`.
- Decision: handoff (Draft PR; the orchestrator runs the reviews)

## Risks and rollback

- Risks:
  - VERSION SKEW. The protocol number is unchanged and the descriptor is not on the wire. On Linux an OLD host
    publishes to `/tmp` and a NEW operator looks in the private directory (and the reverse), so they do not find
    each other; the operator then runs its stand-alone demo and the user connects by hand, the existing manual path.
    Deliberately, no fallback reads the old shared name. On macOS and Windows the location is unchanged, so old and
    new interoperate (the new reader is stricter about type and owner; a descriptor written by the old host is a
    regular `0600` file of ours and passes).
  - Denial of service by squatting a name in a shared `/tmp` now needs the home step to be unusable first (decision 12); where it IS reached it is still "fail closed", not removed (decision 5).
  - The home step is skipped for a group-writable home (`umask 002`, user-private groups), which then falls to the `/tmp` last resort.
  - Dev tooling does not verify the directory's owner (Non-goals).
  - On Windows a crash leftover is swept only when older than 60 s (decision 10).
  - The directory check and the file open are two syscalls, not an `openat` against a held descriptor (non-goal above).
  - The Windows retry delay (5 attempts, 100 ms apart, 400 ms in all) is a judgement: the old 80 ms was
    also a judgement. Nothing measured how long a scanner holds a freshly written file. The Windows leg is not compiled or run here.
  - Legacy files in the shared `/tmp` from older builds are left in place (owner-only, dead token).
- Rollback or recovery: revert the single PR. No data format, migration or wire change is involved; the descriptor is regenerated on every host start.

## Pause and escalation conditions

- Disk below the floor (12.5 GiB in round 1, 11.5 GiB in round 2): wait and re-check (bounded), report it.
- Any need to change a pinned wire fixture or the frontend: stop and ask (orchestrator).
- Any new package in a lock file: stop and ask.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9agb-endpoint-descriptor-private-dir.md` and `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py` on the same file
- Validator result: both validators exit 0 (structural and completion modes)
- Independent verification result: pending (orchestrator runs the four-reviewer gate)
- Terminal state: handoff at a Draft PR; not VERIFIED_COMPLETE until independent review passes
- Remaining failed or blocked criteria: none; independent review, QA, `make ci` and the Windows and Linux legs are the orchestrator's or unverified (see Risks)
- ClickUp final evidence comment: the orchestrator posts it
