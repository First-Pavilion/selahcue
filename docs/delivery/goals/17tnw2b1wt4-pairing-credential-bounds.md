# Goal Contract — 17tnw2b1wt4

## Identity

- Goal ID: TASK-17tnw2b1wt4
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: Bound issued pairing credentials and displayed rejection reasons
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wt4
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Malformed issued pairing credentials never reach secure storage or a successful pairing outcome. Valid bounded opaque credentials still pair unchanged, and rejection display text is bounded without changing verdict classification.

## Baseline

Freshly fetched main be3bd43576757d2963b6ef1748fe29afa1f1e622 (tree d2b920ab) requires only non-empty string device_id/token in PairResult.fromJson. The real pairing flow persists those fields via PairingController and StoredSession.save. Shared rejection parsing returns arbitrary-length strings unchanged. Existing tests cover missing/wrong-typed fields, normal verdicts and malformed-reply persistence behavior.

Read full captured task in wave2-20261029/mobile-qualification/17tnw2b1wt4.json. Its connector comments response is a quota error. Root separately qualified comments in the signed-in UI with all activity categories and Comments enabled; the root receipt 17tnw2b1wt4-comments-ui-qualification.md records no owner-comment entries. No runtime baseline is claimed from source inspection.

After actual test-only RED, ordinary merge 4389e9c9 integrated freshly fetched main 6a1f414cc3213006b333a071893db394ffd03039. Its API/deployment-only delta has no mobile subtree changes. No source history was rewritten.

## Inputs and evidence sources

- Existing task description/acceptance criteria, no declared dependencies, and root's separate UI comments qualification.
- lib/models/protocol.dart PairResult, AuthResult and shared rejection helper; pairing_controller.dart persistence flow.
- Existing auth_pair_result and pairing_controller_malformed_reply tests, real pinned-TLS LoopbackHost, FakeKeystore.
- Real host server.rs mints dev- plus random hex device IDs and 64-character lowercase hex tokens.
- Root owns ClickUp UI, hosted CI, publication, independent reviews, merge and QA.

## Scope

### In scope

- Validate newly issued device_id/token as non-blank printable ASCII, each at most 1024 characters, without rewriting valid values or imposing a hex-only grammar.
- Bound displayed rejection reason to at most 1024 UTF-16 code units, preserve shorter text and avoid cutting a surrogate pair.
- Pure parser boundaries plus real TLS pairing/secure-storage consequences and controls.

### Non-goals

- Existing-profile migration, transport/frame byte caps, role grammar, revocation policy, pairing deadlines or host credential minting.
- Other tickets, UI redesign, signing, platform configuration or application publication.

### Constraints

- No local project runtime, Flutter/pub/Node/build, simulator, container or performance execution while host paging prevents admission.
- Hosted test-only behavioral RED before production changes; no test/analyzer pass claim from inspection.
- Preserve unknown-role string fail-closed parsing, explicit rejection semantics, missing/empty reason handling and wrong-type malformed handling.
- No credential logging, trimming/replacing accepted secrets, storage deletion on malformed grant, push, PR mutation, ClickUp write or extra agents.
- Work only in this isolated branch; other agents own separate tickets and must not be reverted.

### Assumptions and unknowns

- 1024 is the concrete technical bound for the task's approximately 1 KiB credentials. Printable ASCII matches its non-ASCII/control-character examples while accepting opaque punctuation and embedded spaces.
- Reason text uses a display cap, not a closed vocabulary; an oversized reason is still an explicit rejection.
- Real-host end-to-end tests exercise the existing pinned TLS client; physical-device/storage backend behavior is not claimed.
- Actual hosted test-only RED is established; corrected GREEN, independent reviews and delivery remain pending root execution.

## Dependencies and approvals

- Task has no declared blocking dependency or unresolved owner decision in captured task/UI activity.
- Prior typed malformed-verdict and loopback test infrastructure is present in current main.
- Root explicitly assigned this ticket and handles start status/comment and all external gates.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Invalid issued credentials cannot pair or write storage | Pure shape tests and real TLS PairingController negatives for huge/NUL/control/blank/non-ASCII/over-bound values | PairMalformed, malformed-host message, null outcome, zero writes/deletes and no stored profile | Hosted focused regression receipts | PENDING |
| C-002 | yes | Bounded opaque and real-host credentials retain behavior | Exact 1024/1025 parser boundary and real host dev-hex/64-hex pairing controls | At-bound and real-host fields unchanged; over-bound malformed; valid pairing saved once | Hosted parser and pairing controls | PENDING |
| C-003 | yes | Displayed rejection reasons are capped without verdict changes | Pair/Auth parser reason boundaries and real TLS 1 MiB rejection | Truncated bounded reason; short Unicode unchanged; explicit rejection retained; nothing saved | Hosted focused reason receipts | PENDING |
| C-004 | yes | Regressions detect the missing bounds | Frozen test-only source before production edit; repeat after removing validation/cap if needed | Each negative shape and huge reason fails behaviorally, controls pass, no setup/analyzer failure mistaken for RED | PR 271 CI 40948228392 at 6023d371, analysis passed, 401 tests passed and 42 behavior regressions failed; mobile-credential-red.log | PASS |
| C-005 | yes | Broader mobile behavior passes on corrected source | Hosted flutter analyze and full flutter test | Analysis exits 0, applicable full suite passes with existing role/auth/malformed controls | Root exact-source CI receipt | PENDING |
| C-006 | yes | Independent review and authorized delivery close | Cody, Quinn, Vera, Shadow and root delivery | Four current-source passes, actual merge verified, exact linked ticket QA persisted/reread | Root reviews/merge/QA receipts | PENDING |

## Verification plan

- Focused hosted selector: flutter test test/models/pairing_credential_bounds_test.dart test/controllers/pairing_controller_credential_bounds_test.dart.
- Run hosted flutter analyze and the focused tests on unchanged production first; require actual behavioral RED and passing positive controls.
- Corrected candidate needs hosted flutter analyze/full flutter test and independent Cody, Quinn, Vera and Shadow reviews.
- Existing short-reason/unknown-role/additive-field/auth-classification tests remain part of full regression coverage.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-004
- Hypothesis: missing field-length/printability validation admits malformed grants to persistence, and unbounded reason parsing admits oversized display text.
- Change or investigation: inspect full task/UI qualification/current main and write parser plus real TLS controller regressions/positive boundary controls before production changes.
- Verifier executed: structural Goal validator/full baseline diff check, then root-hosted Flutter analysis and full tests on frozen test-only commit 6023d3710a9cf5e6af74751c8ccb521b91551786.
- Result: actual behavioral RED, PR 271 CI 40948228392. Analysis passed; 401 tests passed and 42 failed. Invalid credential parser cases returned PairGranted, real TLS invalid grants returned PairedOutcome and could overwrite the prior profile, and oversized pair/auth reasons exceeded the cap. Real-host credentials, exact-limit opaque credentials/unknown role, short Unicode/1024-unit reasons and existing verdict/close controls passed.
- New evidence: saved wave2-20261029/mobile-credential-red.log was inspected before production edits; the failures exercise actual parser and persistence consequences rather than setup errors.
- Decision: iterate with scoped validation and display cap; retain the observed test source unchanged.

### Iteration 2

- Target criterion: C-001 through C-003, C-005 and C-006
- Hypothesis: validating issued values before PairGranted construction prevents storage/auth reuse of malformed credentials; capping shared reason parsing bounds display text while preserving rejection classification.
- Change or investigation: add a length-first, bounded printable-ASCII/non-blank credential validator; retain accepted strings unchanged and unknown-role behavior. Cap shared rejection text at 1024 UTF-16 units, stepping back when a cut ends on a leading surrogate. No transport/controller/storage policy change. Integrate API-only current main ordinarily before publishing the corrected candidate.
- Verifier executed: source inspection, full current-main baseline diff check, structural Goal validator, and unchanged-test source diff. No local project runtime was executed while resource admission remained unavailable.
- Result: corrected source prepared; fresh hosted analysis/full tests and all four independent current-source reviews remain pending root.
- New evidence: production diff is confined to protocol.dart validation and shared reason parsing. Test files remain identical to the observed RED commit.
- Decision: hand off frozen candidate for hosted GREEN/reviews and remediate valid findings within the remaining iteration budget.

## Risks and rollback

- Risks: restricting to the host's current hex grammar would reject future valid opaque credentials; truncating a reason must not turn a rejection into a malformed or granted verdict or corrupt a surrogate pair.
- Rollback or recovery: revert this ticket only; no migration, wire-version or platform change.

## Pause and escalation conditions

- Actual test-only behavioral RED was observed before production edits; await corrected-source hosted checks and independent review before completion.
- Keep valid findings and unexecuted gates explicit; remediate within eight iterations.
- Route genuine owner-policy questions to root; do not invent revocation/role policy or bypass local resource admission.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wt4-pairing-credential-bounds.md
- Validator result: structural validation passed (exit 0); corrected-source behavior awaits hosted execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-003, C-005 and C-006; C-004 passed on frozen test-only source
- ClickUp final evidence comment: root owns publication
