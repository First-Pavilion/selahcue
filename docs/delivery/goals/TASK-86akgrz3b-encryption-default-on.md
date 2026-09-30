# Goal Contract — TASK-86akgrz3b-encryption-default-on

## Identity

- Goal ID: TASK-86akgrz3b-encryption-default-on
- Parent goal ID: NONE
- Title: `selahcue-desktop`'s (and, as discovered necessary, `selahcue-operator`'s) `encryption` (SQLCipher) feature ships default-on, Windows CI actually builds/tests it, the installer artifact is verified encrypted, and 86ajtxzrn's open question is closed
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgrz3b
- Created: 2026-09-30T13:22:17Z
- Updated: 2026-09-30T13:22:17Z
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Ship option (a) — encrypted by default (SQLCipher) — for `selahcue-desktop`, with Windows CI able to
actually build/test the feature (not skip it), the shipped Windows installer artifact verified to
carry the encrypted path, `scripts/check_launch_reachability.py`'s registry/tags and the Makefile's
`RELEASE_UNSAFE_FEATURES` registry kept accurate, and 86ajtxzrn's relevant open question resolved
with a link back to this ticket. `make ci` passes, including the previously Windows-skipped
encryption test now actually running there.

## Baseline

**Verified against the tree at origin/main (2f26541), 2026-09-30:**

- `selahcue-desktop/Cargo.toml`'s `encryption` feature exists (`selahcue-data/encryption` +
  keyring/argon2/getrandom/zeroize), tagged `LAUNCH_REACHABILITY: OPT-IN` / `RELEASE: SAFE`, no
  `default = [...]` array in that crate at all.
- `selahcue-data/Cargo.toml`'s `encryption` feature (`rusqlite/bundled-sqlcipher-vendored-openssl`
  + zeroize) is off by default too.
- `.github/workflows/ci.yml:495-501` (`rust` job): the "Test (at-rest encryption)" step is gated
  `if: ${{ !cancelled() && runner.os != 'Windows' }}` — Windows has never compiled this feature at
  all, not just skipped the test.
- `.github/workflows/windows-installer.yml` builds `selahcue-desktop --features ndi` and
  `selahcue-operator` (`cargo tauri build --features stt`) without `--features encryption`, and has
  no perl/nasm setup for a vendored-OpenSSL build.
- **New finding, not in the original brief**: `selahcue-operator/src/main.rs`'s
  `open_transcript_db_at` (the Transcripts viewer's read path, 86akcffvt) opens the shared store via
  plain `selahcue_data::Database::open_existing_readonly` — no key, and `selahcue-operator` has no
  `encryption` Cargo feature at all. Its own doc comment already names the gap: "an
  at-rest-encrypted store this default (non-`encryption`) build can't open" reports "transcript
  store unavailable". Once `selahcue-desktop` defaults to `encryption` on, every fresh install with
  a working OS keychain (the common case) creates an encrypted store, and the operator's
  already-shipped Transcripts page goes permanently, silently non-functional for every such
  install — a real, in-scope "user-visible regression" the ticket's own acceptance criteria (and
  the brief's explicit "confirm ... no user-visible regression") rule out shipping.
- `Makefile`'s `RELEASE_UNSAFE_FEATURES := dev-keys openai-notes cloud-stt` — no `encryption`.
- `scripts/check_launch_reachability.py`'s `CRATE_MANIFESTS` already registers both
  `selahcue-operator` and `selahcue-desktop` (contrary to the brief's uncertainty, this part needs
  no code change — only accurate tags on the Cargo.toml side, plus the Makefile actually carrying
  the `encryption` token so the dry-run text the script inspects contains it, since a Cargo
  `default` feature is otherwise invisible to that script's `--features <list>` text scan).
- 86ajtxzrn (transcript+detection persistence) and 86akcfftu (durable write path) are both already
  `complete`; 86ajtxzrn's description lists five open product/legal questions, one of which is this
  ticket's own subject.

## Inputs and evidence sources

- ClickUp 86akgrz3b (this ticket), 86akcfftu (risk acceptance), 86ajtxzrn (five open questions)
- Repository tree at branch `security/86akgrz3b-encryption-default-on`, cut from `origin/main` @ 2f26541
- `.github/workflows/ci.yml`, `.github/workflows/windows-installer.yml`
- `scripts/check_launch_reachability.py`, `Makefile`
- `implementation/desktop/crates/{selahcue-desktop,selahcue-data,selahcue-operator}`

## Scope

### In scope

- `selahcue-desktop`: `encryption` becomes a Cargo `default` feature.
- `selahcue-data`: add a read-only encrypted-open primitive (`open_existing_readonly_encrypted`)
  so a reader that must never write/create/migrate can still open an encrypted store — mirrors the
  existing `open_existing_readonly`/`open_encrypted` pair.
- `selahcue-operator`: gains its own `encryption` feature (default-on), a duplicated (per ADR-0007's
  "key acquisition is the shell's job, not selahcue-data's") key-acquisition module reading the SAME
  OS-keychain entry `selahcue-desktop` writes, and `open_transcript_db_at` updated to read an
  encrypted store when the on-disk file isn't plaintext SQLite — closing the regression above.
- Windows CI toolchain: perl+nasm verification/setup added to the `rust`, `operator`, and
  `operator-native` jobs' Windows legs, and to `windows-installer.yml`; the `rust` job's encryption
  test step's `runner.os != 'Windows'` skip removed.
- `windows-installer.yml`: verified (by dispatching it and inspecting the produced artifact) to ship
  the encrypted path once default-on.
- `scripts/check_launch_reachability.py`: tag comments updated on both crates' `encryption`
  features (`OPT-IN` → `REQUIRED`, `RELEASE: SAFE` confirmed); `Makefile`'s `DESKTOP_FEATURES`/
  `OP_FEATURES` updated to carry the `encryption` token explicitly (Cargo defaults don't appear in
  `--features` dry-run text, so the REQUIRED check needs the explicit token — no change to the
  script's own detection algorithm).
- `Makefile`'s `RELEASE_UNSAFE_FEATURES`: verified `encryption` does NOT belong there (no change
  expected; verification recorded either way).
- 86ajtxzrn: one comment resolving its encryption-default open question, linking back here.
- Four-reviewer gate (Cody/Vera/Shadow/Quinn), Draft PR against `main`, `make ci` green including
  Windows-lane encryption tests, real `gh pr checks` green.

### Non-goals

- The FDE-verification fallback path (option b) and the hybrid option (c) — product owner explicitly
  chose (a) only.
- Any change to `selahcue-operator`'s deck-DB path (`open_deck_db`) — out of this ticket's
  transcript/FR-154 scope; it has its own pre-existing, separately-tracked "align with desktop's
  data_dir()" follow-up.
- Closing 86ajtxzrn's other four open questions.
- Retention/deletion behaviour changes (86ajtxzrn's own territory, already shipped).

### Constraints

- Never work on `main`; own worktree + branch (`security/86akgrz3b-encryption-default-on`, cut from
  `origin/main`), Draft PR, no self-merge.
- Shared checkout: confirmed via session list that no other active session is in `scph` right now;
  still serialize `make ci` (one at a time) per repo CLAUDE.md.
- `binaries/` gitignored sidecar placeholders (`make stage-operator-binaries`) needed before
  `selahcue-operator` compiles in this fresh worktree.
- ADR-0007: key acquisition/derivation stays out of `selahcue-data` — the data layer only *applies*
  an already-derived key. The operator-side key module is a duplicate, not a shared crate, to avoid
  violating that boundary or pulling `selahcue-desktop`'s winit/wgpu dependency tree into the Tauri
  shell.

### Assumptions and unknowns

- ASSUMED: GitHub's `windows-latest` runner ships Strawberry Perl on PATH (documented in the
  runner-images software manifest). VALIDATION OWNER: this ticket — a `perl -v` verification step is
  added to each affected Windows job/workflow rather than silently assumed; if that assertion ever
  fails in a real run, the job fails loudly with a clear diagnostic rather than a confusing OpenSSL
  build error deep inside `cargo build`.
- ASSUMED: `ilammy/setup-nasm@v1` is an acceptable third-party action to add (matches this repo's
  existing use of pinned, narrowly-scoped third-party actions like `ilammy/msvc-dev-cmd@v1`,
  `Swatinem/rust-cache@v2`). VALIDATION OWNER: Shadow (security review) — flagged explicitly for
  supply-chain review as part of the four-reviewer gate.
- UNKNOWN until a real Windows CI run: exact wall-clock cost the vendored OpenSSL build adds to the
  `rust`/`operator`/`operator-native` Windows legs, and whether it pushes any job over its
  `timeout-minutes` budget. VALIDATION OWNER: this ticket, via the real CI run on the opened PR; if a
  budget is blown, the smallest fix is a targeted timeout bump on that job with the measured number
  cited, not a scope cut.

## Dependencies and approvals

- Product owner decision already given: ship option (a), encrypted by default (this session's
  instruction).
- No further product/architecture approval identified as blocking; the operator read-path fix is
  treated as in-scope implementation of "the chosen posture" per the ticket's own AC1/AC2, not a new
  decision requiring escalation — flagged clearly in the PR description and ClickUp comment so
  a reviewer can object if they disagree with scope.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `encryption` is a Cargo `default` feature of `selahcue-desktop` | `cargo metadata --manifest-path implementation/desktop/Cargo.toml --format-version1` (or `grep default` in Cargo.toml) + a build with no `--features` flag links SQLCipher | `default = ["encryption", ...]` present; `cargo build -p selahcue-desktop` (no flags) produces a binary requiring a key | Cargo.toml diff; `cargo test -p selahcue-desktop` (no flags) — 52/52 incl. `encryption_tests` | PASS |
| C-002 | yes | `selahcue-operator`'s Transcripts read path can open a store `selahcue-desktop` wrote with `encryption` on, using the same OS-keychain key | New `selahcue-operator` unit tests (`open_transcript_db_with_key` — right key opens, wrong key/no key report unavailable, plaintext store still opens plain) | All new tests pass; existing `transcript_db_open_tests` unaffected | `cargo test -p selahcue-operator` (no flags) — 176/176 incl. 4 new `transcript_db_open_encrypted_tests` | PASS |
| C-003 | yes | Windows CI actually compiles/tests the `encryption` feature (not just skips it) | Real `gh pr checks` on the opened PR: `rust (windows-latest)`, `operator (windows-latest)`, `operator-native (windows-latest)` all pass | All green, no skip | CI run URLs | PENDING |
| C-004 | yes | The `rust` job's at-rest-encryption test step runs on Windows too | ci.yml diff (the `runner.os != 'Windows'` clause removed) + the real run's step log for that job on windows-latest | Step present and green on Windows | CI run log link | PENDING |
| C-005 | yes | The shipped Windows installer artifact actually carries the encrypted path, not just the flag default | Dispatch `windows-installer.yml` on this branch; download the artifact; inspect the built binary/bundle for the SQLCipher/vendored-OpenSSL link evidence | Artifact built successfully with `encryption` compiled in (verified by binary inspection, not just reading the workflow YAML) | Workflow run URL + inspection notes | PENDING |
| C-006 | yes | `check_launch_reachability.py`'s real check (not just `--self-test`) passes with `encryption` tagged `REQUIRED`/`SAFE` on both crates | `python3 scripts/check_launch_reachability.py --self-test && python3 scripts/check_launch_reachability.py` | Exit 0, prints confirmation including `encryption` | Self-test 46/46; real check passes, output cites `encryption`/`read-encrypted-transcripts`; mutation-verified twice (Makefile token drop, `TARGET_BUILDS_CRATE` drift) | PASS |
| C-007 | yes | `Makefile`'s `RELEASE_UNSAFE_FEATURES` registry is verified accurate (encryption excluded, confirmed not merely assumed) | Read `Makefile`; re-run `check_launch_reachability.py`'s RELEASE cross-check | `encryption` absent, `dev-keys openai-notes cloud-stt` unchanged, cross-check passes | Real check output: `['cloud-stt', 'dev-keys', 'openai-notes'] confirmed release-unsafe` — unchanged, encryption absent | PASS |
| C-008 | yes | 86ajtxzrn's encryption-default open question is marked resolved with a link to 86akgrz3b | ClickUp comment on 86ajtxzrn | Comment posted, visible on read-back | Comment id 1400430000037024 | PASS |
| C-009 | yes | `make ci` passes on this branch | `make ci` (full target, local machine) | Exit 0, all steps green | `/tmp/make_ci_86akgrz3b.log` — `== local Rust/Flutter gate: ALL GREEN ==`, 242 `test result: ok`, 253 Flutter tests, 0 failures | PASS |
| C-010 | yes | Four-reviewer gate passed (Cody, Vera, Shadow, Quinn), blocking findings remediated | Each reviewer dispatched against the real diff/PR; re-check after remediation | All four report no outstanding blocking findings | Review report artifact URL(s), linked on the PR and ClickUp | PENDING |
| C-011 | yes | Draft PR opened against `main`, not merged by this agent, real `gh pr checks` green | `gh pr view`/`gh pr checks` | PR open, Draft or Ready per review state, checks green | PR URL | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: targeted `cargo test -p selahcue-data --features encryption`,
  `cargo test -p selahcue-desktop` (no flags — proving default-on), `cargo test -p selahcue-operator`
  (no flags) after each Rust change.
- Broader regression verification: full `make ci` before opening the PR; real GitHub Actions run
  (`gh pr checks`) after pushing, including the Windows lanes specifically.
- Independent verifier: Cody (code), Vera (performance — CI timing budget impact), Shadow (security —
  key handling, third-party action supply chain), Quinn (QA — installer artifact inspection,
  fresh-install behaviour).
- Required environment: this worktree (macOS, arm64) for local `make ci`; real GitHub-hosted
  ubuntu-latest/macos-latest/windows-latest runners for the matrix and the installer build.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002 (the two structural Rust changes)
- Hypothesis: making `encryption` default-on for `selahcue-desktop` alone would silently break
  `selahcue-operator`'s already-shipped Transcripts reader; both must land together.
- Change or investigation: read `selahcue-desktop/src/keys.rs`, `selahcue-data/src/{db,key}.rs`,
  `selahcue-operator/src/main.rs`'s `open_transcript_db_at`/`transcript_data_dir` and their existing
  tests to confirm the exact mechanism and the safest, most precedent-consistent fix.
- Verifier executed: `cargo test -p selahcue-data --features encryption`;
  `cargo test -p selahcue-desktop` (no flags); `cargo test -p selahcue-operator` (no flags);
  `cargo clippy`/`cargo fmt --check` on both workspaces.
- Result: PASS. `selahcue-data`: 3 new tests for `open_existing_readonly_encrypted` (right key,
  wrong key, never-creates). `selahcue-desktop`: 52/52 including `encryption_tests`, now reachable
  with no explicit flag. `selahcue-operator`: 176/176 including 4 new
  `transcript_db_open_encrypted_tests`. All clippy/fmt clean.
- New evidence: confirmed via `grep`/`Read` that `open_deck_db` and `open_transcript_db_at` both
  call plain, unkeyed `Database::open`/`open_existing_readonly`, and that `open_transcript_db_at`'s
  own doc comment already anticipates this exact gap. Also found and fixed a real regression
  during implementation: the naive `open_transcript_db_at` called `keys::acquire` (real OS
  keychain) unconditionally, so every plaintext-path test started touching the real keychain
  (90+s run, real writes) — fixed by peeking the on-disk header first; full suite now 2s.
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-004 (Windows CI toolchain)
- Hypothesis: `perl`+`nasm` missing on `windows-latest` for the `rust`/`operator`/`operator-native`
  jobs is the actual blocker; `windows-latest` is documented to ship Strawberry Perl but NASM is
  not preinstalled.
- Change or investigation: added `ilammy/setup-nasm@v1` + a `perl -v` verification step (fails
  loudly rather than assuming) to all three jobs' Windows legs and to `windows-installer.yml`;
  removed the `runner.os != 'Windows'` skip on the `rust` job's at-rest-encryption test step.
- Verifier executed: `actionlint` on both modified workflow files;
  `.github/scripts/check_workflows.py --self-test` and the real check (step-ordering/scope rules).
- Result: PASS locally (both green). Real Windows CI execution is C-003's actual verifier —
  PENDING until the PR is pushed and `gh pr checks` reports the Windows lane.
- New evidence: none yet from a real Windows runner (ASSUMED item in the contract, not yet
  validated).
- Decision: iterate

### Iteration 3

- Target criterion: C-006, C-007 (`check_launch_reachability.py`, `RELEASE_UNSAFE_FEATURES`)
- Hypothesis: tagging both crates' encryption features `REQUIRED`/`SAFE` and threading the tokens
  through the Makefile would satisfy the existing checker unchanged.
- Change or investigation: tagged both features; added `read-encrypted-transcripts`/`encryption`
  tokens to `OP_FEATURES`/`DESKTOP_FEATURES`. Ran the real check — it FAILED: `make operator`/
  `make build-operator` don't build `selahcue-desktop` at all, so `encryption`'s reachability was
  being checked against targets that structurally can't reach it. Root-caused: every prior
  `REQUIRED` feature lived on `selahcue-operator`, which all three `TARGETS` entries build, so a
  target-uniform check was correct only by coincidence until now.
- Verifier executed: `check_launch_reachability.py --self-test` and the real check, before and
  after the fix; two live mutation tests (dropped the Makefile token → caught; dropped
  `selahcue-desktop` from the new `TARGET_BUILDS_CRATE["launch"]` entry → caught by the new
  `target_builds_crate_omits_no_crate_mentions_can_see` drift check), each restored after
  confirming RED then GREEN.
- Result: PASS. Added `TARGET_BUILDS_CRATE` (hardcoded + one-directional drift check, matching the
  script's existing `CRATE_MANIFESTS`-is-hardcoded precedent and its documented reason —
  `crate_mentions` is blind to the macOS `operator` wrapper-script shape). Self-test: 46/46 (up
  from 39). Real check: passes, correctly scoped.
- New evidence: this was a genuine, previously-latent gap in the checker itself, not just a tag
  choice — recorded in the script's own module docstring and in the Makefile/Cargo.toml comments.
- Decision: iterate

### Iteration 4

- Target criterion: C-008 (86ajtxzrn open question), C-009 (`make ci`)
- Change or investigation: posted the resolution comment on 86ajtxzrn; launched full `make ci`
  locally (properly backgrounded this time — an earlier attempt combined manual `&`/`disown` with
  the harness's own `run_in_background`, which orphaned the process from tracking; corrected by
  polling the real PID directly).
- Verifier executed: `make ci` (full target).
- Result: PASS. `== local Rust/Flutter gate: ALL GREEN ==`. 242 `test result: ok` suites, 253
  Flutter tests passed, zero `test result: FAILED`, zero compiler errors, zero panics (swept the
  full 9,266-line log). One unrelated, environment-local generated-file diff
  (`GeneratedPluginRegistrant.swift`, a Flutter plugin-import rename from the local pub cache)
  discarded before committing — not part of this ticket's scope.
- Decision: handoff (ready for commit, push, Draft PR, and the four-reviewer gate)

### Iteration 5

- Target criterion: C-003, C-004 (real Windows CI execution)
- Change or investigation: committed, pushed, opened Draft PR #125, dispatched the
  windows-installer.yml verification build and the four-reviewer gate. The PR's own `ci.yml` run
  (36727646787) came back with all four still-running jobs (`rust (windows-latest)`,
  `operator shell (windows-latest)`, `operator shell — release & native-toolchain features
  (windows-latest)`, and — unexpectedly — `operator shell (ubuntu-latest)`) marked `cancelled`,
  all within the same ~15s wall-clock window (14:28:13–14:28:31) despite being at wildly different
  points in their own step sequences. That timing signature (simultaneous, not per-job-timeout
  staggered) means the whole RUN was cancelled externally, not that any of these four jobs failed
  or timed out on its own.
- Verifier executed: `gh api .../jobs/<id>` step-by-step inspection of all four cancelled jobs
  before re-running anything.
- Result: strong POSITIVE evidence despite the cancellation. Every step this PR actually touches
  succeeded before the external cancel hit: `NASM for the vendored-OpenSSL build (Windows only)` —
  success; `Verify Perl is on PATH for the vendored-OpenSSL build (Windows only)` — success (on
  all three Windows jobs); `Clippy (default features)`/`Clippy (server features)` — success on
  `rust (windows-latest)`; `Clippy`/`Check` — success on `operator shell (windows-latest)`; and on
  `operator shell — release & native-toolchain features (windows-latest)`, `Clippy (dev-keys,
  openai-notes, RELEASE)` AND `Test (dev-keys,openai-notes, RELEASE)` both SUCCEEDED — a full
  RELEASE-profile build and test pass with `read-encrypted-transcripts` (default-on, pulling in
  vendored SQLCipher+OpenSSL) compiled in, on Windows. The cancellation hit later, unrelated steps
  (`Clippy (stt,cloud-stt)`, mid-`Test (workspace...)`, `Install Playwright WebKit`) — none of
  which this PR touches.
- New evidence: re-ran the cancelled jobs only (`gh run rerun 36727646787 --failed`), reusing the
  already-successful jobs' results; a fresh wait is in progress.
- Decision: iterate

### Iteration 6

- Target criterion: C-010 (four-reviewer gate)
- Change or investigation: Cody and Shadow reported. Both independently converged on the same two
  security findings (existing plaintext stores never migrated; a keychain failure at first launch
  silently and permanently creates an invisible plaintext store) plus Cody's own finding
  (`open_transcript_db_with_key` read the whole transcript file just to check 16 bytes).
- Verifier executed: fixed Cody's finding (bounded 16-byte peek, matching the sibling function's
  existing pattern) and Shadow's Blocker 2 minimum requirement (a real `security_status` Tauri
  command + Settings → Security UI wiring, replacing the stale hardcoded "NOT YET ON" claim with a
  live Encrypted/Not Encrypted/Ready/Unavailable status). Re-ran `cargo test`/`clippy`/`fmt` on
  `selahcue-operator` (180/180, clean) and `scripts/operator_headless.py` (2069/2069, 0 FAIL, exact
  check-count bumped from 2065 with a real measured re-run, not hand-derived).
- Result: PASS on both fixes. Blocker 1 (no migration for pre-existing installs) NOT fixed in this
  PR — judged too large/risky to add under time pressure; instead corrected the overstated
  ClickUp language (86ajtxzrn comment), filed and linked a follow-up ticket (17tnw2b0gt9), and
  escalated the accept-vs-build-now decision to the product owner via a ClickUp comment on
  86akgrz3b, rather than deciding unilaterally.
- New evidence: full `make ci` re-run after these fixes — `== local Rust/Flutter gate: ALL GREEN
  ==`, 242 `test result: ok`, 253 Flutter tests, 0 failures (`/tmp/make_ci_86akgrz3b_round2.log`).
- Decision: iterate (awaiting Vera + Quinn; committing and pushing these fixes now)

### Iteration 7

- Target criterion: C-005 (installer artifact)
- Change or investigation: the dispatched `windows-installer.yml` run (36727677825) completed:
  `success`, 32m6s total. Quinn's QA agent downloaded the produced artifact
  (`.qa_installer_artifact/SelahCue Operator_0.1.0_x64-setup.exe`, 27MB — gitignored/untracked,
  never staged) for direct binary inspection.
- Verifier executed: `gh run view 36727677825 --json status,conclusion`.
- Result: PASS (build succeeded). Binary-level confirmation that the encrypted path is genuinely
  compiled in (not just the flag default) is Quinn's in-progress independent verification — not
  self-certified here.
- Decision: iterate

### Iteration 8

- Target criterion: C-010 (four-reviewer gate), performance regressions Vera's review surfaced
- Change or investigation: Vera reported. 1 blocking (V1: `operator` job's 15-min Windows cap
  ACTUALLY TIMED OUT on a real run — "The job has exceeded the maximum execution time of 15m0s"),
  3 non-blocking (V2: `operator-native`'s 45-min cap down to ~10% cold-run headroom, not the ~40%
  its own comment claimed; V3: `SessionStore::open_store`'s whole-file read, same class of bug
  already fixed in the operator, now hit on every desktop launch — measured 122MB peak / ~44ms
  warm on a 116.6MB store; V4: the NFR gate never measures the encrypted path since Linux CI has
  no Secret Service). Also an open, "inferred" question addressed to Shadow/Quinn: could macOS
  Keychain ACLs prompt when `selahcue-operator` reads a key `selahcue-desktop` created (two
  different processes/identities)?
- Verifier executed: fixed V1 (timeout-minutes 15 -> 30, `operator` job) and V2 (15 -> wait, 45
  -> 60, `operator-native` job) with Vera's real measured numbers cited in the comments; fixed V3
  (bounded 16-byte header peek in `SessionStore::open_store`, identical pattern to the operator
  fix). Did not fix V4 (Linux-CI-environmental, out of proportion to fix now). For the open
  keychain question: built a throwaway 3-binary Cargo project (writer/reader/cleanup, distinct
  compiled executables, same `keyring` 3.6.3 + feature set as the real code) and ran it for real
  against this machine's macOS Keychain rather than reasoning about it in the abstract.
- Result: PASS on V1/V2/V3 (`cargo test -p selahcue-desktop`: 52/52, clippy clean, fmt clean;
  `actionlint`/`check_workflows.py` clean on the ci.yml edits). Keychain experiment: **no access
  prompt, no hang** across create (different binary) -> read (different binary) -> delete
  (different binary again) — the two operations the real `keys::acquire()` code path actually
  uses (get/set) both succeeded silently. Caveat recorded and posted (PR comment
  #issuecomment-5914031685): tested via bare dev binaries, not the final packaged `.app` bundle,
  so this de-risks the underlying mechanism without being a full end-to-end replication.
- New evidence: full `make ci` re-run in progress after these fixes (round 3).
- Decision: iterate

## Risks and rollback

- Risks: Windows CI timing (vendored OpenSSL build can be slow); a subtly wrong key-sharing
  implementation could corrupt nothing (SQLCipher never partially decrypts) but could regress the
  Transcripts UI in a different way (e.g. always reporting unavailable) if the on-disk
  plaintext-vs-encrypted discriminator has an edge case; the duplicated key module in
  `selahcue-operator` drifting from `selahcue-desktop`'s copy over time.
- Rollback or recovery: single Draft PR, easily reverted; `encryption` default can be reverted to
  `default = []` in one line if Windows CI proves unworkable; no data migration involved (both
  plaintext and encrypted stores continue to be read correctly by the updated code either way).

## Pause and escalation conditions

- If the real Windows CI run shows the vendored-OpenSSL build cannot complete in a reasonable time
  budget even after a `timeout-minutes` bump, escalate to the user rather than silently shipping
  Windows-excluded coverage again.
- If Shadow's security review objects to the operator-side key-module duplication (e.g. wants a
  shared crate instead), treat that as a legitimate architecture question and escalate rather than
  overriding.

## Final evaluation

- Validator command: (recorded at completion)
- Validator result: (recorded at completion)
- Independent verification result: (recorded at completion)
- Terminal state: (recorded at completion)
- Remaining failed or blocked criteria: (recorded at completion)
- ClickUp final evidence comment: (recorded at completion)
