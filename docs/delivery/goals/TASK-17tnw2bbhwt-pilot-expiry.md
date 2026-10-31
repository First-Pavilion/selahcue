# Goal Contract — TASK-17tnw2bbhwt-pilot-expiry

## Identity

- Goal ID: TASK-17tnw2bbhwt-pilot-expiry
- Parent goal ID: NONE
- Title: Pilot access expiry/rejection preserves offline operation
- Role: ai-engineer (native owner Nova; accountable frontend owner Farah)
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhwt
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Pilot cloud actions stop at the shared effective expiry, lane-specific rejection is explained safely, late notes never persist, and offline presentation/available local transcription remain intact.

## Baseline

Initially merged main a2ed7f96dd5eb8508406f7a901c1ad57d3a519b5; audited/rebased to4e2ce4374713956a498978fdf6383c74c2c548cb before review freeze (intervening API/docs/mobile only). P02 blocks new construction only. Refreshed merged provider_source/pilot admission and transport seams; provisional Farah plan is an input, not runtime evidence.

## Inputs and evidence sources

- Root browser-reread all three P03 criteria; /private/tmp/selahcue-continuation-20261031/farah-p03-plan.md; merged source.

## Scope

### In scope

- One P03 unit: Nova owns Rust/native status, actual HTTP/WebSocket deadlines, late-save refusal and native tests. Farah owns tracked dist JS/HTML/CSS and JS tests. No real provider keys/calls, scanner policy, packaging, publication or licensing changes.

### Non-goals

- Provider/model/prompt quality changes, actual credential issuance or embedding, scanner policy, packaging/publication/deployment and licence changes. P01/P04 gates remain external. No hardware or real-provider runtime claim.

### Constraints

- Fixed cutoff 2027-04-30T23:59:59Z and earliest provider expiry; preserve consent/completed transcripts/licences/offline output. Shared branch; no concurrent Git mutations or staging another engineer’s files.

### Assumptions and unknowns

- UNKNOWN actual provider scope/expiry/revocation proof (P01), unique scanner payload boundary/policy (P04), hardware/package proof. Root owns live browser/runtime evidence and ClickUp.

## Dependencies and approvals

- P02 merged. Root authorized P03 implementation and all four reviews; root alone merges. P01/P04 remain real-embedding gates.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Before/at/after and provider-rejected states are correct without raw body/credential disclosure; real active network work respects admitted deadline and late notes never save/stage | Native deadline/loopback/late-save tests and UI tests | zero failures; measured loopback client/worker close within 500ms after deadline | docs/delivery/evidence/p03-pilot-expiry.md | PASS |
| C-002 | yes | Offline live output and available local STT remain intact through expiry/rejection | Actual shared worker fallback tests plus root runtime journey | no output/frame/draft/transcript loss; local fallback truthful | docs/delivery/evidence/p03-pilot-expiry.md | PASS |
| C-003 | yes | Restart/retry cannot extend fixed validity and replacement-build guidance is visible | Fixed UTC/monotonic restart/retry tests and UI/runtime checks | same absolute end; fixed visible guidance, no pilot .env instructions | docs/delivery/evidence/p03-pilot-expiry.md | PASS |
| C-004 | yes | Required supported runtime journey has actual evidence, with source/fixture limits explicit | Root CUA/native smoke | recorded before/expiry/rejection/offline UI journey; fixture/native evidence distinguished; root accepts supported journey limits | docs/delivery/evidence/p03-pilot-expiry.md | PENDING |
| C-005 | yes | All four independent reviewers approve current head | Cody Shadow Quinn Vera | no blocking findings | docs/reviews/ | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Safe frontend contract

Ordinary builds: `providers_view.pilot_access` and command `pilot_access_status` return null. Pilot builds return only `{state, notes_state, transcription_state, notes_uses_pilot, effective_expiry_unix_seconds, replacement_required}`. All states are `available|expired|rejected|unavailable`. Shared config/UTC/monotonic expiry affects both applicable pilot lanes. `notes_uses_pilot=false` only when the same native actual-route selector chooses configured hosted notes; hosted errors never latch pilot rejection and captured request routes govern all awaits. Missing/malformed applicability fails closed for notes. Provider rejection latches only that lane; action gating uses its lane field. Global state is worst (expired, rejected, unavailable, available); replacement_required is true if either lane needs replacement. Expiry is absolute UTC integer seconds, nullable only for invalid/absent config. No credential, cohort secret, parser error, response body or local path is serialized. Fixed command errors: `pilot_expired`, `pilot_access_rejected`, `pilot_unavailable`. Rejected never asserts definite revocation. Non-pilot behavior remains compatible.

## Verification plan

- Focused verification: Focused deterministic Rust/UI tests plus real loopback socket/head/body deadline tests; no broad redundant builds/model downloads.
- Broader regression verification: Focused deterministic Rust/UI tests plus real loopback socket/head/body deadline tests; no broad redundant builds/model downloads.
- Independent verifier: Cody, Shadow, Quinn, Vera; root supported CUA/native runtime journey.
- Required environment: Local macOS native Rust/loopback and synthetic config; browser/native runtime when root can access supported CUA.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 native deadline/status baseline
- Hypothesis: one admitted UTC/monotonic deadline enforced at actual I/O and save boundaries prevents active work or retries renewing pilot validity.
- Change or investigation: read merged P02 and provisional handoff; sent stable nonsecret per-lane IPC contract to Farah.
- Verifier executed:
- Result: baseline source inspected; no runtime completion claimed.
- New evidence:
- Decision: iterate

### Iteration 2

- Target criterion: C-001/C-002/C-003
- Hypothesis: owning actual HTTP/WebSocket work and checking actual persistence admission prevents late egress/results while keeping offline state intact.
- Change or investigation: native shared UTC/monotonic admission, lane status/rejection, hard transport cancellation and same-source fallback; Aria clarified pre-cutoff admitted mutations may finish later; checks added after draft load/mutex/socket readiness.
- Verifier executed: affected native release suites, real loopback HTTP/WS/backpressure, sink readiness, operator storage/live-frame and mixed hosted-route controls; Farah actual-module Node/headless and root synthetic CUA.
- Result: HTTP3/STT6/core3/LAN1 pass; 1106 assertions across93 successful affected-target summaries. A source redaction target failed, corrected with explicit per-arm parsers and guarded-method hostile reply coverage; focused6+4 pass. Earlier integrated operator491 pass/2 ignored; final time-controlled CI phases now25 passing executions.
- New evidence: docs/delivery/evidence/p03-pilot-expiry.md; Farah UI20 Node and2906 headless pass at7533f9e; root labelled same-page automatic expiry CUA.
- Decision: iterate

### Iteration 3

- Target criterion: C-001/C-003 and automatic reachability
- Hypothesis: one focused release-pilot step in the existing native job can verify before/equality/after without real keys or future date failure.
- Change or investigation: root-approved narrow CI step, committed synthetic config, test-only epoch, nonzero/required-name assertions and production binary hook exclusion. Strict lint exposed test-module placement, a duplicated attribute, an incorrect test mutex name and new test assertion lint; corrected without weakening gate.
- Verifier executed: exact extracted workflow step; native strict lint; workflow inventory/minutes/actionlint; both rustfmt checks/diff check.
- Result: native strict lint and workflow/format checks PASS; exact focused step PASS:5/9/1/5/5 named nonzero controls before/equality/after; production executable hook exclusion PASS.
- New evidence: /private/tmp/p03-exact-ci.log, /private/tmp/p03-native-clippy.log, docs/delivery/evidence/p03-pilot-expiry.md.
- Decision: focused checks complete; freeze source for four independent reviews and separately authorized isolated native CUA smoke.

## Risks and rollback

- Risks: native/UI and loopback evidence does not establish real provider-account, installer or hardware behavior; system time is not tamper-proof across restart. Root acceptance/current CI/four independent reviews remain required.
- Rollback or recovery: revert the whole P03 unit; pilot feature remains off by default and real embedding stays P01/P04 gated.

## Pause and escalation conditions

- If real transport cannot meet the meaningful deadline/close bound, bring concrete evidence to Aria/root; do not replace transport cancellation with UI timeout or weaken criteria.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhwt-pilot-expiry.md
- Validator result: structural PASS; completion intentionally not claimed.
- Independent verification result: pending four independent reviews/current hosted CI.
- Terminal state: GATE_REVIEW (source increment; whole task remains active).
- Remaining failed or blocked criteria: C-004 native CUA journey/acceptance pending; C-005 four current independent reviews pending.
- ClickUp final evidence comment:
