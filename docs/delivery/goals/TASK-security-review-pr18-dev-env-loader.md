# Goal Contract — TASK-security-review-pr18-dev-env-loader

## Identity

- Goal ID: TASK-security-review-pr18-dev-env-loader
- Parent goal ID: NONE
- Title: PR #18 (feat/86akby6yy-dev-env-loader) is security-reviewed at head 6cfbc4a with the dev-key blind-spot question adjudicated, findings posted on the PR, and a verdict reported to the requester
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby6yy
- Created: 2026-09-04
- Updated: 2026-09-04 (completed)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

At head 6cfbc4a2e5330dc841db3d49d6d4d1cd6e9504ff (base origin/main cb006fc): the dev-env loader
is assessed against the specific concern that it reintroduces the runtime-config-loader shape
scripts/dev_key_not_in_release.sh names as its open bypass; the allowlist enforcement, feature
reachability in release artefacts, key-leak channels, set_var soundness, and the entitlement-key
blind-spot question each receive explicit verdicts backed by evidence; findings are posted as PR
review comments and a verdict (safe as-is / safe with named conditions / blocking) is reported.

## Baseline

PR #18 is a Draft against main. One commit on top of origin/main (cb006fc); merge-base equals
origin/main so the branch is current. CI green on all non-skipped jobs at head. The implementing
engineer declined to self-certify and requested security review first. The loader reads the
repo-root .env behind an off-by-default `dev-keys` feature, exports at most DEEPGRAM_API_KEY and
OPENAI_API_KEY, and prints name-only startup lines.

## Inputs and evidence sources

- Repository at /Users/m.oluwole/Documents/code/scph, read via `git show 6cfbc4a:<path>` /
  `git show cb006fc:<path>` — never the shared working tree
- PR #18 description and diff (gh CLI); engineer's goal contract TASK-86akby6yy-dev-env-loader.md
- scripts/dev_key_not_in_release.sh, scripts/dev_key_scan.py, .github/workflows/*, Makefile,
  operator Cargo.toml/Cargo.lock, tauri.conf.json, PRD FR-082/FR-134/CON-5/NFR-018
- Mutation probes and builds only in an isolated scratchpad worktree at 6cfbc4a, restored clean

## Scope

### In scope

- Allowlist fail-closed analysis: is the two-name allowlist pinned at both the plan layer and the
  set_var boundary; would a test catch widening (LOADABLE edit and load_from edit separately)
- Feature reachability: every route by which dev-keys could be compiled into a distributed
  artefact (feature unification, default features, --all-features in CI/packaging, Tauri bundle
  config, installer workflows, Makefile release targets) — searched for unenumerated spellings
- Leak channels: startup lines, Debug impls, panic messages (set_var failure path), dbg!, any
  diagnostics/env-dump path in the operator
- set_var soundness pre-thread; test-binary env races
- Whether sanctioning this loader widens the entitlement-key blind spot QA demonstrated
- FR-082, FR-134, CON-5/NFR-018 conformance; build_note_request untouched
- The Makefile line and the deliberate ci.yml gap: block or defer to 86ak5rjh7

### Non-goals

- Modifying the code under review; merging or marking the PR ready
- Reviewing the two consumer lanes (86akby4yz, 86akby7d8) beyond their stated contract
- Re-running the engineer's full 8-mutation battery (spot-check only where load-bearing)

### Constraints

- No `make ci` (shared checkout; concurrent-session false reds); targeted cargo test only, in an
  isolated worktree with its own target dir
- Never pipe a gate whose exit code will be read
- Verify against SHAs, not the shared working tree; negative searches need a positive control

### Assumptions and unknowns

- ASSUMED: gh CLI authenticated (verified via pr view)
- UNKNOWN: ClickUp MCP connectivity — not present in this session's toolset; pending update will
  be returned to the requester
- UNKNOWN: artifact-publishing tooling availability for the report page; if absent, PR comments
  carry the findings and the gap is stated

## Dependencies and approvals

- gh CLI authenticated — available
- ClickUp MCP — not present; structured pending update in the final report

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The allowlist question is answered with evidence: pinned where, and does a test catch widening at each layer (LOADABLE, plan, load_from write loop) | code read at 6cfbc4a + mutation probes in isolated worktree with exit codes | explicit verdict per layer; any unpinned layer named as a finding | Verdict: fails closed and is pinned at the plan layer, NOT at the export boundary. Probe B (LOADABLE widened by SELAHCUE_DEV_SIGNING_SEED): 5 tests FAIL, exit 101 — widening the list itself is caught, incl. by CI (default features, 3 OSes). Probe A (load_from write loop widened past the allowlist): 78/78 GREEN, exit 0 — no test asserts the boundary where values reach the process env. Finding F1 (Medium) with a concrete boundary test specified. Worktree restored clean after each probe | PASS |
| C-002 | yes | Every artefact-producing build route is enumerated and checked for dev-keys reachability, including unenumerated spellings (--all-features, unification, defaults, bundler, installer) | grep + read of workflows/Makefile/scripts/tauri config at 6cfbc4a, with positive controls for negative searches | explicit verdict: unreachable in release artefacts, or a named route | Verdict: unreachable in any distributed artefact at head. default = []; dev-keys = [] referenced by nothing else; operator excluded from workspace, binary crate, zero reverse deps (grep positive control: selahcue-app found in 4 manifests); installer runs cargo tauri build --features stt only; tauri.conf.json has no features/beforeBuildCommand; CI operator job default-features; no --all-features anywhere (positive control: --features server found); OP_FEATURES ?= stt/empty; launch-smoke + nfr build selahcue-desktop only. Empirical: default debug bin has 0/4 signature strings, dev-keys bin 4/4 (paired positive control). Residual: guarded by enumerable spellings only -> condition F5 (effect-level artefact scan in windows-installer.yml) | PASS |
| C-003 | yes | Leak channels are assessed end-to-end: startup lines, Report/Plan Debug, set_var panic path, env-dump/diagnostics paths in the operator | code read + empirical probe of the set_var failure mode under the pinned toolchain | explicit verdict; findings filed where a value can escape | Verdict: structural redaction holds on every module-owned path (Report all-&'static; Plan Debug hand-written, pinned with positive control); no logging/diagnostic framework in operator src. ONE escape found: std::env::set_var's failure panic prints the full value — empirically verified under pinned 1.98.0 (the panic message embeds the variable name and the entire offending value verbatim) triggered by a NUL byte in a .env value. Finding F2 (Low). F3 (Info): exported keys inherit into every child process (autolaunch sidecar) | PASS |
| C-004 | yes | set_var soundness is assessed for the production path and the test binary | code read + dependency check for pre-main constructors | explicit verdict with residual assumptions named | Verdict: sound. load() is the first statement of main; the only pre-main constructor in the dependency tree is tauri-utils STARTING_BINARY (ctor 0.8.0) which caches current_exe() on the main thread, spawns no thread, reads no env. Rust-side env access is internally locked by std on Unix; disabled/enabled test groups are in mutually exclusive cfg blocks, enabled siblings serialised by ENV_LOCK. Edition 2021 + forbid(unsafe_code): a 2024 bump fails loudly as the PR states | PASS |
| C-005 | yes | The blind-spot question is adjudicated: does sanctioning this loader make the QA-demonstrated entitlement-key bypass easier or harder to notice | read of dev_key_not_in_release.sh header + comparison of shapes | explicit verdict with reasoning a reviewer can check | Verdict: does not materially widen the blind spot. Operator links no selahcue-licensing (absent from operator Cargo.lock; positive control selahcue-app present), so no runtime path from this loader to entitlement verification exists in the artefact; LOADABLE widening — including to an entitlement-style name — is killed by 5 CI-run tests (Probe B); the QA bypass requires an env READ inside the licensing path, this adds a bounded WRITE of two fixed AI names in a different binary; the review-enforced rule at TrustedKeys::insert is unchanged. Residual normalisation risk named and bounded by condition F5, matching the artefact-scan philosophy the installer workflow header already prescribes | PASS |
| C-006 | yes | FR-082/FR-134/CON-5/NFR-018 conformance stated; build_note_request untouched verified by diff scope | PRD read + diff file list | explicit per-requirement verdict | FR-082: pass with F2 edge noted. FR-134: deviation (plaintext repo-root .env, live keys) accepted by owner for this phase per coordinator; replacements ticketed (86akby3xu; notes proxied). CON-5/NFR-018: pass — loader performs no egress (fs read + env write only); selahcue-core/providers.rs byte-identical to origin/main at head (diff empty); ProvidersConfig::build_note_request confirmed at providers.rs:417; selahcue-cloud untouched | PASS |
| C-007 | yes | The Makefile/ci.yml gap receives a block-or-defer verdict with reasoning | analysis of which controls run in CI default-features vs dev-keys | explicit verdict | Verdict: correctly deferred to 86ak5rjh7. The security-load-bearing controls (disabled-build no-read test + all redaction/allowlist tests) compile under plain cfg(test) and run in CI's default-features operator job on 3 OSes — independently confirmed: default suite 76 passed incl. all 10 default dev_env tests; Probe C (un-gate the loader) turns exactly a_build_without_dev_keys_does_not_read_a_key_file RED in that default suite. CI misses only the 3 enabled:: convenience tests; note the F1 boundary test will also live there, one more reason to close 86ak5rjh7 | PASS |
| C-008 | yes | Findings posted as PR review comments on PR #18 with a security verdict | gh pr review / gh api | review visible on PR #18 | review 5111431802 posted on PR #18, state COMMENTED, verified via gh api | PASS |
| C-009 | yes | Verdict and finding count by severity reported to the requester | final response text | stated | final report: Pass with named conditions — 0 blocking/high, 1 medium (F1), 1 low (F2), 2 informational (F3/F4), 1 condition (F5) | PASS |

## Verification plan

- Focused verification: SHA-pinned code reads; isolated worktree at 6cfbc4a for builds and
  mutation probes; empirical std::env::set_var failure-mode probe under the pinned toolchain
- Broader regression verification: the engineer's mutation table spot-checked against the tests
  as committed
- Independent verifier: requester and the other three reviewers on the same PR
- Required environment: gh CLI, pinned Rust toolchain

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: the allowlist is pinned only at the pure plan layer; no artefact route enables dev-keys
- Change or investigation: SHA-pinned reads of Cargo.toml/workflows/Makefile/tauri.conf.json; greps with positive controls; isolated worktree at 6cfbc4a (own CARGO_TARGET_DIR); baseline cargo test both feature states (76 / 78 passed, exit 0 both); binary builds both states scanned for 4 signature strings; Probe A (widen write loop) GREEN 78/78; Probe B (widen LOADABLE) RED 5 tests
- Verifier executed: exit codes captured directly, never piped
- Result: C-002 PASS; C-001 PASS with finding F1 (Medium)
- New evidence: scratchpad baseline_default.log, baseline_devkeys.log, build_default.log, build_devkeys.log, mutA.log, mutB.log, bin_default/bin_devkeys scans
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-004, C-005, C-006, C-007
- Hypothesis: the one leak route is std's own set_var panic; soundness holds; blind spot not widened
- Change or investigation: empirical set_var NUL probe under pinned 1.98.0 (panic embeds full value, exit 101 captured directly); operator-wide greps for env dumps/diagnostics/dbg; ctor dependency traced to tauri-utils STARTING_BINARY (read source); operator Cargo.lock searched for selahcue-licensing (negative, with positive control); providers.rs diffed byte-identical; Probe C (un-gate loader) RED on exactly the named control test
- Verifier executed: as above
- Result: all PASS; findings F2 (Low), F3/F4 (Info), condition F5
- New evidence: scratchpad setvar_probe/p198.err, mutC.log
- Decision: iterate

### Iteration 3

- Target criterion: C-008, C-009
- Hypothesis: posting the consolidated review completes the deliverable
- Change or investigation: posted consolidated review on PR #18; verdict Pass with named conditions (0 blocking, 1 medium, 1 low, 2 informational, 1 condition); worktree removed
- Verifier executed: gh api reviews list
- Result: C-008 PASS, C-009 PASS via final report
- New evidence: review URL on PR #18
- Decision: complete

## Risks and rollback

- Risk: review comments name bypass shapes on a private repo PR — acceptable audience (team-only)
- Risk: mutation probes could disturb the shared checkout — mitigated by an isolated worktree
  with its own CARGO_TARGET_DIR, removed at the end
- Rollback: review is additive commentary; worktree removed at the end

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr18-dev-env-loader.md --completion
- Validator result: recorded on the run below
- Independent verification result: the requester and the other three reviewers gate the same PR
- Terminal state: VERIFIED_COMPLETE (review deliverable); the PR itself remains Draft pending the four-reviewer gate
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — ClickUp MCP not available in this session; structured update returned to the requester
