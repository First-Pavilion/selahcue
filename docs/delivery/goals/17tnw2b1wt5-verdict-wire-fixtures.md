# Goal Contract — 17tnw2b1wt5

## Identity

- Goal ID: TASK-17tnw2b1wt5
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Pin all existing host authentication and pairing verdict bytes across Rust and Dart
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1wt5
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Existing host verdict serialization and Dart decoding have matching literal fixtures for authentication granted/rejected and pairing parked/granted/rejected, including each of the three existing rejection reasons. Targeted serializer/parser mutants must break the new fixtures without any production behavior change.

## Baseline

Verified actual main dd5cc038efe04681e42746edb8d243996badc947. Rust auth_frames_round_trip pins granted bytes but rejected only round-trips; Dart protocol_test.dart pins pair granted/parked but not the complete verdict matrix. Production DenyReason is Forbidden, Unauthenticated, BadRequest; existing VERSION and reason/revocation/credential policies remain unchanged. Linked predecessor17tnw2b1f1v is merged andQA; captured full five comments have no threaded replies. Current task has zero comments/dependencies, standalone on the requested list.

## Inputs and evidence sources

- Full fresh task/history/custom/dependency payloads under wave3-20261030/mobile-qualification/17tnw2b1wt5.json and17tnw2b1f1v-prerequisite.json.
- Current protocol declarations, real serde serializer/deserializer, Dart AuthResult/PairResult parsers and existing two cross-language fixture files.
- Canonical mobile/goal/runtime contracts, repository guidance and frozen selected20 scope.

## Scope

### In scope

- selahcue-lan/tests/test_protocol.rs exact existing verdict serialization fixtures and decoding controls.
- mobile/selahcue_controller/test/models/protocol_test.dart decoding the identical literals to exact variants/fields.
- This Goal Contract and bounded hosted mutation evidence. Temporary workflow-only diagnostics may mutate runner source, with exact candidate/first-parent object checks and restoration, but must not survive final source.

### Non-goals

- Production parser/serializer/API/VERSION/reason/revocation/credential or transport changes.
- New product rejection policy, unrelated coverage, UI/native/device/signing/platform or performance acceptance.

### Constraints

- Coverage-only work: legitimate baseline GREEN; do not manufacture a productRED. Real hosted mutants establish regression sensitivity.
- Own new isolated branch/worktree and only scoped fixture/goal files; not alone, preserve other authors' changes.
- No local Flutter/pub/Rust/build/test/install/simulator/container/benchmark. Tiny Git/stdlib/static validation only; normal full hosted Rust/Flutter gates mandatory.
- Ordinary own push/draft/body-file/immediateattachment and bounded hosted diagnostics allowed. No forcepush/protected edits/merge/ClickUpUI/status/review publishing/subagents or next ticket until root assigns.

### Assumptions and unknowns

- Existing three DenyReason values define this fixture matrix; unknown future reason/revocation policy is outside this task.
- Hosted normal baseline/candidate suites and actual mutation outcomes are unverified until run receipts. No native/device evidence is required by this coverage-only contract or claimed.

## Dependencies and approvals

- Auth/pair malformed-reply predecessor is current/merged/QA, including unchanged intentional explicit-rejection behavior.
- Root selected this ticket first, owns start/status, allfour independent reviews, merge and exactlinkedQA handoff.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Rust pins all nine existing verdict byte shapes | Real to_json plus literal from_json assertions in test_protocol.rs | Authgranted/3rejected and pairparked/granted/3rejected match exact literals | Focused37testsPASS in diagnostic41089108351 on exact8b49eeff; broad normal gate is C004 | PASS |
| C-002 | yes | Dart decodes the same nine literals correctly | AuthResult/PairResult parsing tests in protocol_test.dart | Exact variants, reason strings, credentials and role | Focused33casesPASS/all9namedfixtures success in41089108351; broad normal gate is C004 | PASS |
| C-003 | yes | New fixtures detect meaningful contract drift | Hosted isolated Rust tag/reason-casing and Dart tag-match mutants with controls/siblings retained | Each mutation actually fails new named fixtures; restored candidate passes; setup failures do not qualify | 41091337793: five actual named fixture failures, unaffected controls PASS, restored Rust37/Dart33 PASS; exact source hashes | PASS |
| C-004 | yes | Normal full affected Rust and Flutter gates pass | Exact final-source normalCI Rust suites and flutter analyze/fulltest | Applicable normal jobs/steps succeed; skipped areas explicitly unexecuted | Historical5c5529f2 normal41090942165 FAILURE (operator dev-keys448pass/1fail/1ignored); fresh integrated-source gate pending, no waiver | PENDING |
| C-005 | yes | Production contract/source remains unchanged | Full baseline diff and object/source identity checks after diagnostic restoration | Final diff only two fixture files/Goal; no workflow or product/dependency changes | Current-main diff only two fixtures/Goal; production/workflow/dependency objects equal main; immutable integration manifest and diffcheck | PASS |
| C-006 | yes | Independent review and authorized delivery close | Root Cody/Quinn/Vera/Shadow reports, merge/tree proof and exactQA readback | Four current-source Pass verdicts, verified merge andQA | Root delivery receipts | PENDING |

## Verification plan

- Focused Rust: cargo test -p selahcue-lan --test test_protocol (normal default and relevant server suite through hostedCI).
- Focused Dart: flutter test test/models/protocol_test.dart; normalCI also runs analysis/fullFlutter.
- Baseline/fixtures must pass real existing serialization/parsing. Mutant compile/setup failures are not sensitivity evidence; inspect actual new named fixture failures and surviving positive/sibling cases.
- Hosted diagnostic workflow must anchor exact candidate/first-parent, restore all runner edits, verify product/test source identity and retain raw logs. Remove workflow-only diagnostic from final tree; do not forcepush history.
- Root controls independent reviews/mergeQA; no completion claim while any mandatory criterion remains pending.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 and C-002
- Hypothesis: independent literal fixture matrices close the existing serializer/decoder coverage gap without any production change.
- Change or investigation: read full task/prerequisite/current source and instructions; created own managed worktree/branch from fresh main; prepare exact matrix tests.
- Verifier executed: structural Goal validation before fixture edits; hosted baseline/full gates pending.
- Result: preparation only; no runtime or sensitivity claim yet.
- New evidence: current serializer supports all required frames; no missing production behavior needs a fix.
- Decision: add fixtures, freeze clean source and obtain normal hosted GREEN plus meaningful hosted mutation results.

### Iteration 2

- Target criterion: C-003 through C-005
- Hypothesis: filtering machine output to JSON objects fixes the diagnostic parser while retaining all nine required fixture completions; a separate exact-first-parent workflow ref keeps product normal CI independent.
- Change or investigation: candidate8b49eeff has only two fixtures/Goal. Temporary child e29f2c76 added one workflow. Diagnostic41089108351 actually ran Rust37/37 and Dart33/33 cases including allnine newfixtures, then failed before any mutant because a valid JSON list reached event.get. Normaltemphead41089119925 also failed actionlint SC1083 for unquoted HEAD^{tree}; originalnormal41088751822 cancelled. These are diagnostic/setup failures, not killed mutants or normal GREEN. Corrected parser type-gate was checked against actual saved machine output, allnine fixture successes recovered; installed static actionlint and embedded Python syntax validation passed after quotingrefs. Corrected workflow-only child a71ff51a on separate diagnosticref has exact firstparent8b49eeff and identical product/tests/Goal; fresh hosted diagnostic41090718753 pending. Ordinarily remove the temporary workflow from product PR and preserve the unchanged fixtures; fresh actualmain remainsdd5cc038.
- Verifier executed: original raw17tnw2b1wt5-mutant-job.log and17tnw2b1wt5-diagnostic-lint-job.log, actual event parser/staticworkflow validation, source/object comparison, structuralGoal/fullbaseline diffcheck; final normalCI and corrected hosted mutants pending.
- Result: C001/C002 focusedPASS; C003 sensitivity stillPENDING with zero prior mutants executed. Cody/Quinn candidate source inspections found no fixture defect and block final acceptance only on actual sensitivity/restoration and finalsource/fullnormal gates.
- New evidence: valid Flutter machine output includes non-object JSON; event-type handling must not assume every decoded value is an event. Loader success is not counted as a test case.
- Decision: freeze clean three-file product candidate and obtain fresh full normalCI independently of bounded diagnosticref; inspect allfive actual mutation failures, surviving controls and restoredGREEN/hashes before finalhandoff. No production protocol correction.

### Iteration 3

- Target criterion: C-003
- Hypothesis: matching actual Dart machine assertion result `failure` permits the complete sensitivity/restoration matrix without changing fixture bytes.
- Change or investigation: second diagnostic41090718753 killed the three Rust mutants and Dart auth mutant before its oracle incorrectly required `error`; Dart pair and restored suites were not executed. Corrected isolated workflow-only child49686e2b of8b49eeff ran41091337793 SUCCESS. Rust auth/pair serde-tag and reason-casing mutants fail the new named fixtures, with unaffected controls passing. Dart auth/pair tag mutants fail all corresponding new fixtures, while the opposite verdict group and hello sibling pass. Restored focused Rust37 and Dart33 cases pass; all four original source hashes match. Both failed diagnostic attempts remain retained.
- Verifier executed: actual five mutation failure outputs, surviving controls, restored suites and four SHA256 values in17tnw2b1wt5-mutant-attempt3.log/receipt.json and object-mapping.json.
- Result: C-003 PASS; fixture/product bytes match8b49eeff and clean5c5529f2. This proves coverage sensitivity without a product fix.
- Decision: preserve clean product source; normal full affected CI remains an independent mandatory gate.

### Iteration 4

- Target criterion: C-004
- Hypothesis: one authorized boundary-instrumented diagnostic in the actual failing dev-keys context could attribute the stand-in spawn failure without changing flow or accepting a rerun as a gate.
- Change or investigation: normal41090942165 on exact5c5529f2 FAILED operator dev-keys (448 passed,1 failed,1 ignored) at autolaunch.rs233, `the stand-in sidecar spawns`. Existing `.spawn().ok()?` discarded the OS error; cause/errno unknown. Separate workflow-only child12494337 of5c5529f2 ran41118719835 SUCCESS: original four feature/browser steps passed,16 full parallel dev-keys repetitions passed449/0/1ignored,16 focused spawn repetitions passed4/0. Zero spawn-error markers;32 absent markers belong only to intentional missing-sidecar controls. Actual source/instrumentation hashes match the published context manifest. Prior main31c native diagnostic41058550197 also did not reproduce its historical failure; neither establishes cause of this failure.
- Verifier executed: actual raw17tnw2b1wt5-autolaunch-diagnostic.log, independently checked32 outcomes/markers/context hashes, classification.json and original failed normal log.
- Result: cause UNKNOWN, errno UNKNOWN; no attributed reproduction. Instrumented success is not a normal acceptance gate, does not waive41090942165 FAILURE and supports no production autolaunch fix or flakiness claim.
- Decision: STOP diagnostics. Preserve the historical failure and obtain current-source acceptance through the authorized necessary integration below.

### Iteration 5

- Target criterion: C-004 and C-005
- Hypothesis: ordinary current-main integration is required before current-source review and a normal full affected CI gate while preserving scoped fixture bytes.
- Change or investigation: fetched and ordinarily merged actual main e5a1611b728901811b6427f7cff2ded0ccfa4dcd (merged transcript privacy and API proxy hardening). Both fixtures remain byte-identical to8b49eeff/5c5529f2. Final current-main diff has only the two fixtures and this Goal; all production/workflow/dependency objects equal main, without diagnostic instrumentation or workflow. Integration is necessary source synchronization, not a claimed fix for the unexplained spawn event.
- Verifier executed: structural Goal validation, full current-main diffcheck, exact blob/subtree/patch manifest; normal full hosted CI pending for frozen integrated candidate.
- Result: C-005 PASS; C-004 PENDING for current source. Historical normal failure remains FAILURE regardless of this candidate's result. Four fresh independent reviews/merge/QA remain pending.
- Decision: publish one fresh current-source normal CI run and yield immutable evidence. If it fails, preserve failure, stop further diagnostics and route the concrete blocker. No local project runtime.

## Risks and rollback

- Risks: roundtrip-only assertions miss shared drift, expectations derived from serializer defeat literal pins, tests change production policy, or mutant setup failure is misreported as detection.
- Rollback or recovery: revert this ticket's fixture/goal edits only; no wire/API/schema/platform change.

## Pause and escalation conditions

- Diagnose unexpected baseline/setup failures rather than treating them as intendedRED. Keep all mutant and positive evidence distinct.
- Yield long hosted waits with immutable SHA/tree/run/checkpoint. No second ticket without root assignment.
- Return actual remaining predicate for root explicit replan if eight iterations are exhausted; no silent extension.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1wt5-verdict-wire-fixtures.md
- Validator result: structural validation passed before edits and after integration; current-source hosted gate pending
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-004 (current-source normal CI pending; historical failure retained), C-006 (root reviews/merge/QA pending)
- ClickUp final evidence comment: root owns publication
