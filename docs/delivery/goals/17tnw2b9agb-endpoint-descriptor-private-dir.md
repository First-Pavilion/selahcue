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
- Tests as listed in the predicate; mutation-verified.

### Non-goals

- A fallback that reads the old shared `/tmp/selahcue-operator-endpoint.json` on Linux. That is the
  attack. Old and new builds simply do not find each other (see Risks).
- Moving to `openat`/`renameat` against a held directory descriptor. The directory is private (our
  uid, no group or other bits), so nobody else can swap entries inside it between our check and our
  use; the only parent we do not control is the sticky shared temp directory, in which another
  account cannot rename or remove our entry. Stated honestly under Risks.
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
| C-001 | yes | The directory is resolved by one shared function: a valid `XDG_RUNTIME_DIR` (absolute, a real directory not a symlink, owned by the current uid, no group or other bits) is used as is; one that is relative, empty, missing, a file, a symlink, foreign-owned or too open is ignored; a private temp directory is used as is (the macOS and Windows shape); a shared temp directory leads to a `selahcue-UID` subdirectory | `cargo test -p selahcue-lan --test test_local_endpoint` | tests pass, each refusal paired with a positive control | `test_local_endpoint` 39 passed, 0 failed (exit 0). RED first: 31 of 39 failed against a scaffold with the old behaviour (8 passed because they are controls that hold either way). Mutants killed: L11 xdg ignored (4 RED), L12 relative accepted (2), L13 xdg unverified (2), L14 private temp ignored (3), L14b temp always used (8), L15 fallback name without uid (7), L8 no owner check (5), L9 no mode check (8), L10 lstat replaced by stat (3), S1 to S5 on the Python mirror (1 each) | PASS |
| C-002 | yes | The fallback directory is created `0700`, then verified (lstat style) before every use; if it exists with another owner, a wide mode, as a symlink or as a plain file it is not used and nothing is created inside it; creating it is idempotent | same command | tests pass | same file; L16 created 0755 (1 RED), L17 no final verify (4 RED), L8, L9, L10 as above; squat by foreign owner, too-open (6 modes), symlink to a good private dir, plain file, unreachable parent: each refused with nothing created inside, and each paired with a positive control | PASS |
| C-003 | yes | The reader refuses, promptly and without blocking: a planted FIFO (also one with a writer attached, also mode `0600` and ours), a symlink whose target is a valid owned `0600` file, a file owned by another user (injected uid), any mode other than `0600`, a directory, an oversized file, non-UTF-8 bytes, and a file inside a directory that is not private; a valid file is read (positive control for each) | same command, plus the operator tests `read_endpoint_at` family | tests pass; the FIFO tests carry a watchdog so a regression fails instead of hanging | lan: FIFO, FIFO with a valid descriptor parked in it, symlink, dangling symlink, foreign owner (file half via `read_file_as`, full read via the directory), 8 wrong modes, directory, oversize at limit and over, non-UTF-8, directory not private (4 modes), symlinked directory. Operator: FIFO (the base reader BLOCKED: `did not return within 5 s`), symlink, uid handed through, private directory. RED: operator 4 of 10 against the base reader. Mutants killed: L1 no O_NONBLOCK (1 RED, the watchdog fires), L2 no O_NOFOLLOW (2), L3 no type check (3), L4 no owner check (1), L5 loose mode (1), L6 no size check (1), L7 no directory check (3), L27 (2), O1 (4), O2 (1), O3 (1). SURVIVOR L28 (`take(max_len)` removed): defence in depth against growth between fstat and read, not deterministically testable, the size check above it is what the tests pin | PASS |
| C-004 | yes | The host publishes only into a private directory it owns: a scratch directory that is too open, or owned by another uid (injected), makes the publish fail with nothing created and the previous descriptor untouched; the production target is created and verified lazily; host write then reader read round-trips in one private directory | `cargo test -p selahcue-desktop endpoint` and the `ServerEnv` tests | tests pass | desktop `endpoint` filter 40 passed 3 ignored (the ignored three are child processes run by their parents); full workspace 1961 passed, 0 failed, 5 ignored (exit 0). RED first: 8 of 40 against the scaffold. Mutants killed: H1 unverified directory (3 RED), H3 sweep takes live files (4 RED, including both multi-publisher tests), H4 per-user directory not created (1). Round trip: the host publishes into a private directory and the operator-side `read_descriptor_as` accepts it and finds the token | PASS |
| C-005 | yes | A stale staging file left by a crash is removed on the next publish; a staging file of a live process, a foreign-owned one, a symlink, a directory, a name that does not parse and the descriptor itself are left alone; the sweep examines a bounded number of entries | `cargo test -p selahcue-lan --test test_local_endpoint` and `cargo test -p selahcue-desktop endpoint` | tests pass | lan: dead pid, live pid kept, old file under a live pid, foreign owner, symlink, directory, names not ours, cap, missing directory, real liveness (this process, pid 1 = EPERM = alive, i32::MAX and u32::MAX dead), production sweep; host: `publishing_sweeps_a_crash_leftover_and_nothing_else`. Mutants killed: L18 (1), L19 (1), L20 (3), L21 (1), L22 (1), L23 (1), L24 (2), L25 (1), L26 and L26b (the age constant moved: first version of the test aged the file BY the constant and survived, fixed with absolute ages and a pinned range), H2 no sweep (1) | PASS |
| C-006 | yes | The Windows rename retry is bounded (5 attempts, at most 500 ms of sleeping), retries only sharing-type errors, is platform-independent logic unit-tested with fake errors, and the production policy is pinned | `cargo test -p selahcue-desktop endpoint` | tests pass; the `cfg(windows)` half is NOT compiled or run here | The retry already existed (`RenamePolicy`, `retry`, `is_sharing_error`, unit tests on every platform); this goal pins the budget on every platform (`the_windows_rename_budget_is_five_attempts_and_a_few_hundred_milliseconds`: 5 attempts, 300 to 500 ms of sleeping) and widens the pause 20 ms to 100 ms. Mutants killed: H5a (20 ms, 1 RED), H5b (5 s, 2), H6 (1 attempt, 1). The `cfg(windows)` classifier branch and the real Windows rename are NOT compiled or run here | PASS |
| C-007 | yes | `scripts/endpoint_path.py` (used by `make launch`, `make remote`, `make nfr`) resolves to the same path as the Rust resolver for the same environment, including the shared-temp, private-temp and XDG cases | the Rust cross-check test, plus running the script by hand | test passes | `make_and_the_nfr_script_resolve_the_same_path_as_the_rust_code` runs `python3 -I scripts/endpoint_path.py` against `resolve_dir` on 7 environments; RED first (script absent); mutants S1 to S5 on the script killed (1 RED each). Survivor by nature: the script's own owner comparison cannot be exercised without a second user. `make -n remote` and `sh -n scripts/measure_nfr.sh` read well; the host was NOT started (it would write the real descriptor) | PASS |
| C-008 | yes | Host and operator both use the shared module; the operator's reader is exercised through its own entry point (FIFO, symlink, foreign owner, positive controls) | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml` default and `--features dev-keys,openai-notes` | tests pass | operator tests 430 passed (default, baseline 425) and 444 passed (`dev-keys,openai-notes`, baseline 439), 0 failed, exit 0 both. SURVIVOR O4 (the operator's path wrapper replaced by its own `temp_dir().join(..)`): equal on macOS, where `$TMPDIR` is already private; it bites on Linux, where the shared `/tmp` resolves to `selahcue-UID` (`the_operator_names_the_shared_descriptor_path`). Three existing operator tests (`a_world_readable_descriptor_is_refused`, `a_0600_descriptor_is_accepted`, `an_oversized_descriptor_is_refused`) now start from a `0700` scratch directory, because `tempfile::tempdir()` is `0755` and the reader refuses such a directory; without that they would have passed or failed for the wrong reason | PASS |
| C-009 | yes | No wire fixture, mobile file or operator frontend file changed; no new package in either lock file; `cargo deny check licenses sources bans` and `cargo audit` are clean for both roots | `git diff --stat origin/main`, `git diff origin/main -- Cargo.lock`, cargo deny, cargo audit | only the `selahcue-lan` dependency list entries change in the lock files | `git diff origin/main -- implementation/mobile implementation/desktop/crates/selahcue-lan/tests/test_protocol.rs implementation/desktop/crates/selahcue-operator/dist` is empty. Lock files: `implementation/desktop/Cargo.lock` gains `rustix 1.1.4` and `tempfile` as dependencies of `selahcue-lan`; the operator lock gains `rustix`; no package added. `cargo deny check licenses sources bans`: ok for both roots (exit 0); `cargo audit`: exit 0 for both, only the allowed warnings that were already there (ttf-parser, chacha20 and others) | PASS |
| C-010 | yes | Format, lint, tests and guards are green with exit codes captured to files | `cargo fmt --check` (workspace and operator), clippy `-D warnings` (workspace; operator default and `dev-keys,openai-notes`), `cargo test --no-fail-fast` (workspace; operator both feature sets), `sh scripts/import_guards.sh`, `python3 scripts/check_launch_reachability.py` | every exit code 0 (`make ci` itself is NOT run) | fmt 0/0 (workspace, operator); clippy `-D warnings` workspace `--all-targets` 0, `selahcue-lan --features server` 0, operator default 0, operator `dev-keys,openai-notes` 0; tests: workspace 1961 passed 0 failed 5 ignored, `selahcue-lan --features server` 179 passed, operator 430 and 444; `scripts/import_guards.sh` 0; `scripts/check_launch_reachability.py` 0. `make ci` was NOT run (does not fit the disk; concurrent runs collide) | PASS |
| C-011 | yes | Branch is up to date with `origin/main` and the Draft PR is open against `main` | `git rev-list --count HEAD..origin/main`; `gh pr view` | `0`; state DRAFT | `git rev-list --count HEAD..origin/main` printed 0 at origin/main 3ab74050; Draft PR recorded in the PR itself | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Design decisions (and why)

1. One shared module in `selahcue-lan`, not two copies. Both consumers already depend on that crate, it
   forbids `unsafe`, and a single definition makes "host and operator agree" structural. Two copies would need
   a drift test; one definition needs none. (The Python mirror for shell tooling does need one, see C-007.)
2. `rustix` rather than `libc`: `geteuid`, `kill(pid, 0)` and the open flags are safe calls there, so the
   crate keeps `forbid(unsafe_code)`. It is already in both lock files, so no new package enters the supply chain.
3. Directory rule on Unix, in order: a valid `XDG_RUNTIME_DIR`; else the temp directory when it is itself
   private (this is the macOS shape, where `$TMPDIR` is already `0700` and owned by the user, so macOS keeps its
   location byte for byte); else a `selahcue-UID` subdirectory of the temp directory (the Linux `/tmp` shape).
   One rule, no per-OS branches, and a `TMPDIR=/tmp` override on macOS is caught the same way as Linux.
4. Validity of a directory is judged with `lstat` (a symlink is refused, never followed), owner equal to the
   effective uid, and `mode & 0o077 == 0`. Mode `0500` is accepted by the check (no group or other bits) and then
   fails on write with a clean error; the explicit `0700` fix-up is not added (a umask of `0277` is not a case
   worth a second code path; the failure is closed, not open).
5. Create-then-verify race: `mkdir` is atomic and either creates a directory owned by us or fails with
   `EEXIST`; whoever won, the following `lstat` check decides. Inside the sticky shared temp directory another
   account cannot rename or remove an entry we own, and cannot add entries to a directory that is `0700` and ours.
   A hostile account that pre-creates `/tmp/selahcue-UID` first makes us fail closed (nothing published, nothing
   read): a denial of service for local auto-connect, not a disclosure or a redirect. `XDG_RUNTIME_DIR`, which the
   login system creates `0700` for the user, is the real fix wherever it exists; the fallback is for sessions
   without it, and a name in a shared directory can never be fully squat-proof. Follow-up candidate: a fallback under
   the user's home.
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
    still refuses non-regular files and bounds the size. The rename retry already existed.

## Verification plan

- Focused verification: the new tests (C-001 to C-008), each mutation-verified by applying one mutant at a time and running the
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

## Risks and rollback

- Risks:
  - VERSION SKEW. The protocol number is unchanged and the descriptor is not on the wire. On Linux an OLD host
    publishes to `/tmp` and a NEW operator looks in the private directory (and the reverse), so they do not find
    each other; the operator then runs its stand-alone demo and the user connects by hand, the existing manual path.
    Deliberately, no fallback reads the old shared name. On macOS and Windows the location is unchanged, so old and
    new interoperate (the new reader is stricter about type and owner; a descriptor written by the old host is a
    regular `0600` file of ours and passes).
  - Denial of service by squatting the fallback directory name in a shared `/tmp` is reduced to "fail closed", not removed (decision 5).
  - The directory check and the file open are two syscalls, not an `openat` against a held descriptor (non-goal above).
  - The Windows retry delay (5 attempts, 100 ms apart, 400 ms in all) is a judgement: the old 80 ms was
    also a judgement. Nothing measured how long a scanner holds a freshly written file. The Windows leg is not compiled or run here.
  - Legacy files in the shared `/tmp` from older builds are left in place (owner-only, dead token).
- Rollback or recovery: revert the single PR. No data format, migration or wire change is involved; the descriptor is regenerated on every host start.

## Pause and escalation conditions

- Disk below 12.5 GiB free: wait and re-check (bounded), report it.
- Any need to change a pinned wire fixture or the frontend: stop and ask (orchestrator).
- Any new package in a lock file: stop and ask.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9agb-endpoint-descriptor-private-dir.md` and `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py` on the same file
- Validator result: both validators exit 0 (structural and completion modes)
- Independent verification result: pending (orchestrator runs the four-reviewer gate)
- Terminal state: handoff at a Draft PR; not VERIFIED_COMPLETE until independent review passes
- Remaining failed or blocked criteria: none; independent review, QA, `make ci` and the Windows and Linux legs are the orchestrator's or unverified (see Risks)
- ClickUp final evidence comment: the orchestrator posts it
