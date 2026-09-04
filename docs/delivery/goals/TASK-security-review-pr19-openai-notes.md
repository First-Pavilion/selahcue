# Goal Contract — TASK-security-review-pr19-openai-notes

## Identity

- Goal ID: TASK-security-review-pr19-openai-notes
- Parent goal ID: NONE
- Title: PR #19 (feat/86akby7d8-openai-sermon-notes) is security-reviewed at head 756e754 with the no-echo, egress-choke-point, bounded-memory and release-containment questions answered by evidence, findings posted on the PR, and a verdict reported
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby7d8
- Created: 2026-09-04
- Updated: 2026-09-04 (completed; head moved 756e754 -> ea5ba05 mid-review, re-anchored)
- Maximum iterations: 8
- Independent verification required: yes

## Objective

At head 756e754 (base origin/main cb006fc): the direct-to-OpenAI notes path is assessed for
key-fragment echo on every response path (mapped, unmapped, timeout, malformed JSON, non-JSON,
5xx, indirect formatting including reqwest error Display and any Debug route); the consent choke
point ProvidersConfig::build_note_request is verified unweakened and unbypassable by the new
path; the clamping bounds are verified to bite by mutation; the openai-notes feature is verified
unreachable in distributed artefacts; the deferred-disclosure split (86akby942) receives an
explicit safe/unsafe verdict; findings posted on PR #19 with a verdict.

## Baseline

PR #19 is a Draft, two commits on origin/main (cb006fc). Same developer-key phase as PR #18
(loader cleared at 70b116b; F5/86akc041v open). Both keys live. The engineer captured a real
OpenAI 401 whose body embeds a masked key fragment; the new mapping reads error.code/error.type
only. The hosted client's own body-echo defect (client.rs truncate(body,200)) is out of scope,
tracked 86akbzxjg. Owner accepts developer-key auth posture; disclosure deferred to 86akby942
flagged as launch gate. Cody reviews in parallel; the branch engineer is parked.

## Inputs and evidence sources

- git show 756e754:<path> / origin/main by SHA — never a shared working tree; the engineer's
  worktree at /Users/m.oluwole/Documents/code/scph-86akby7d8 is read-only reference, not touched
- PR #19 description, diff, and the two commits; my own isolated scratchpad worktree at 756e754
  for builds and mutation probes
- selahcue-cloud (openai.rs, client.rs, contract.rs, lib.rs, local.rs, tests), selahcue-core
  providers.rs, operator Cargo.toml/main.rs/dist, ci.yml, Makefile, PRD FR-132/CON-5/NFR-018

## Scope

### In scope

- Every path a response byte can take into a String that reaches UI/log: the full error mapping,
  defaults, JSON parse failures, transport errors, status branches, Debug/Display impls,
  panics/expect on response data
- Choke point: build_note_request diff at this head; whether the OpenAI path can send without it
- Bounded memory: the clamp bounds and whether their tests fail when the clamp is removed
- Containment: feature graph for openai-notes (default features, unification via
  selahcue-cloud deps, --all-features spellings, installer, CI, Makefile), binary evidence where
  cheap; the PR-18-adjacent Cargo.toml feature-table conflict noted for the coordinator
- The disclosure-deferral split verdict; FR-132 naming in the panel
- Key handling at the call site: how the key is read, stored, sent; whether it can reach any
  error/Debug path

### Non-goals

- The hosted client's own truncate(body,200) defect (86akbzxjg) — verify untouched, do not ask
- Re-reviewing PR #18's loader; correctness/maintainability (Cody's dimension)
- Modifying code; merging; marking ready

### Constraints

- Exit codes captured directly, never piped; probes only in my own scratchpad worktree with its
  own target dir, restored clean and removed
- Negative searches carry positive controls; SHA-pinned reads throughout

### Assumptions and unknowns

- ASSUMED: gh CLI authenticated (verified)
- UNKNOWN: whether tests require network; resolve by reading test harness before running
- ClickUp MCP absent again this session; record routed via the coordinator

## Dependencies and approvals

- gh CLI — available; ClickUp MCP — absent, coordinator routes

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every response path is traced and the no-echo property receives a per-path verdict, with the captured-401 control mutation-verified | code read of openai.rs at 756e754 + mutation probe (echo the body in an unmapped branch) | explicit verdict per path; control goes RED under echo mutation | Every path traced: mapped arms (401/403/404/402/429/400) return fixed wording or compared-only codes; error_code is compared, never formatted; serde_json errors positional only (empirical probe with positive control, SERDE_EXIT=0); transport errors kind+URL; read_bounded cap error carries the cap only; UI hop is NoteError Display + stable code. Captured-401 control mutation-verified: E2 (echo in the 401 arm) RED, 3 tests. GAP FOUND: E1 (echo in the default arm) GREEN at 756e754 AND ea5ba05; E1b (echo in the 5xx arm) GREEN at 756e754 — the no-echo property is pinned per-fixture-arm, not across the mapping. Recommended sweep test validated in-worktree: kills E1 immediately. Finding F-1 (Low) | PASS |
| C-002 | yes | The consent choke point is unweakened and the OpenAI path cannot egress without it | diff of providers.rs vs origin/main + call-graph read of the send path | explicit verdict; any bypass named | build_note_request byte-identical to origin/main (function-level diff IDENTICAL); generate_sermon_notes calls it before any provider; both operator paths (cloud-live fallthrough + openai-notes) route through generate_sermon_notes; C1 mutation (ignore the Generate press) RED via ForbiddenTransport panic 'egress! a request left the device' — the control bites at the network boundary itself; no-audio asserted on the actual outgoing bytes at ea5ba05; base URL is a constant, not env-redirectable in production | PASS |
| C-003 | yes | The clamp bounds bite: removing a clamp turns a named test red | mutation probe on the clamp with siblings | RED on the named test; restored green | B1 (remove .take(MAX_POINTS)) RED at exactly the_point_count_is_bounded_and_the_point_bound_is_what_bit; ClampLog per-key accessor bounded by BOUND_COUNT; compile-time premise pins present; ea5ba05 adds the socket-level bound (read_bounded, take(cap+1), 4MB) fixing the parse-only-cap gap Cody found; MAX_OUTPUT_TOKENS asserted on the wire | PASS |
| C-004 | yes | openai-notes is unreachable in any distributed artefact; every enablement spelling checked with positive controls | manifest/workflow/Makefile reads + greps + feature-graph analysis at 756e754 | explicit verdict or a named route | openai and openai-notes off by default; no workspace member enables them (licensing depends on selahcue-cloud default-features only); operator remains standalone/bin/no reverse deps; installer workflow untouched (still --features stt); all new gate lines are clippy/test targets; --all-features absent; observed execution: run 33864618387 operator jobs on 3 OSes each show two 74-passed runs with the feature-gated a_build_with_the_direct_path... ok in the second. Merge collisions with PR 18 noted (operator Cargo.toml features table + ci.yml operator job region) | PASS |
| C-005 | yes | Key handling at the call site is assessed end to end (read, storage, transmission, error paths) | code read | explicit verdict; findings where a key can escape | from_env: env read, empty==absent, Token::new immediately; Token redacts Debug/Display, no Serialize, constant-time eq; key travels only via bearer_auth header (had_bearer asserted; bearer-drop mutation RED at ea5ba05); key-in-body and key-in-draft asserted absent; reqwest header-invalid errors carry no value; provider derives no Debug | PASS |
| C-006 | yes | The disclosure-deferral split receives an explicit verdict; FR-132 panel naming verified | PRD read + dist/settings.js read | verdict stated with reasoning | Verdict: the split is SAFE for the developer-key phase. Panel names OpenAI (FR-132) with a DEVELOPER KEY badge; disclosure is accuracy-only; operator_headless.py asserts absence of retention/retain/training data/processing agreement/DPA wording at the rendered surface. Condition of the verdict: 86akby942 gates any use with real congregation data, not merely launch — lane A + this PR together make real-sermon egress possible the moment a developer flips consent | PASS |
| C-007 | yes | Findings posted on PR #19 with a security verdict | gh pr review / gh api | review visible | consolidated review posted on PR #19 at ea5ba05 (verified via gh api) | PASS |
| C-008 | yes | Verdict and finding count reported to the coordinator | final response | stated | verdict: clear with conditions — 0 blocking/high, 1 low (F-1 sweep test, fix in PR), 2 informational (licensing feature rule; 86akc041v string-set extension), reported in final response | PASS |

## Verification plan

- Focused: SHA-pinned reads; isolated worktree at 756e754; targeted cargo test on selahcue-cloud
  (workspace member — no tauri staging needed); mutation probes with siblings
- Independent verifier: coordinator, Cody in parallel, remaining reviewers
- Environment: pinned toolchain, gh CLI

## Iteration ledger

### Iteration 1 (head 756e754)

- Target criterion: C-001, C-002, C-003, C-005, C-006 groundwork
- Change or investigation: SHA-pinned reads of the full diff; isolated worktree, own target dir; baseline 26+siblings green; probes E1 GREEN (gap), E1b GREEN (gap), E2 RED x3 (positive control), B1 RED (named clamp test), C1 RED (ForbiddenTransport egress panic), serde probe 0-exit with positive control; sweep-test recommendation validated in-worktree (kills E1)
- Result: F-1 identified and remediation validated
- Evidence: scratchpad p19_baseline.log, p19_E1.log, p19_E1b.log, p19_E2.log, p19_B1.log, p19_C1.log, p19_serde.log, p19_sweep.log
- Decision: iterate (head moved mid-review)

### Iteration 2 (head ea5ba05)

- Target criterion: re-anchor + C-004, C-007, C-008
- Change or investigation: read the remediation delta (read_bounded, request assertions, operator/CI gates); worktree moved to ea5ba05; baseline 30+siblings green; E1 re-applied GREEN (finding stands); bearer-drop mutation RED at the named test; CI run 33864618387 operator logs verified on 3 OSes (feature-gated test executed); worktree restored clean and removed
- Result: all criteria PASS
- Evidence: scratchpad p19r2_baseline.log, p19r2_E1.log, p19r2_bearer.log, p19_job_*.txt
- Decision: complete

## Risks and rollback

- Probes isolated; worktree removed at end; review is additive commentary
- Live keys exist in the shared checkout .env — probes must never read the real .env or run
  binaries that would; tests under review must be checked for real-key usage before running

## Final evaluation

- Validator command: python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-security-review-pr19-openai-notes.md --completion
- Validator result: recorded on the run below
- Independent verification result: coordinator, Cody in parallel, remaining reviewers on the same PR
- Terminal state: VERIFIED_COMPLETE (review deliverable); PR remains Draft pending the rest of the gate
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: PENDING — MCP absent; routed via the coordinator
