# Goal Contract — 17tnw2b0wg3

## Identity

- Goal ID: TASK-17tnw2b0wg3
- Parent goal ID: WAVE2-SELAHCUE-20
- Title: A failed keystore read at launch reaches Connect instead of a stuck splash
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0wg3
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

When the platform keystore cannot supply a stored profile, Launcher follows the existing first-run Connect path without an unhandled asynchronous error, while normal missing-profile and valid-profile startup behavior stays intact.

## Baseline

Verified main `55d5ff3a1b8d18e4702613cd1861a8d226197d37` (tree `927b7e5d`) has Launcher._start awaiting StoredSession.load outside its guarded connect block. StoredSession.load catches malformed JSON but not platform read failures. PairingView._loadPaired already catches Object around the same read and treats failure as absent profile. Existing launcher widget tests cover connect failures but not a failing keystore read.

The full live task and no-comment response are saved in the orchestration evidence folder `wave2-20261029/mobile-qualification/17tnw2b0wg3.json`. No runtime baseline is claimed from source inspection.

## Inputs and evidence sources

- Existing ClickUp task17tnw2b0wg3, including full acceptance criteria and successful empty-comments read.
- lib/main.dart Launcher, models/stored_session.dart, and views/pairing_view.dart reference recovery path.
- test/views/launcher_connect_failure_test.dart and test/support/fake_keystore.dart existing channel/test patterns.
- Current hosted flutter controller workflow: flutter pub get, flutter analyze, flutter test.
- Root's explicit implementation/review/merge/QA authorization; root owns external writes.

## Scope

### In scope

- Guard the launch-time stored-profile read and reuse the existing first-run route on failure.
- Extend the existing launcher widget tests with the real secure-storage method-channel failure and missing/valid controls.
- Preserve raw stored data on failed read; no destructive cleanup or credential logging.

### Non-goals

- Session transport, reconnect policy, credential format, permissions, pairing protocol or secure-storage migration.
- New screens, design changes, signing, application publication or physical device acceptance claims.

### Constraints

- Work only in this isolated ticket branch; other agents own separate work.
- No local heavy Flutter/pub/build/simulator or timing run while host paging fails resource admission.
- Test-only hosted RED first; only then implement the minimal catch. Root publishes and runs CI.
- Do not call a skipped, unexecuted or inconclusive gate passed.
- No branch rewrites, source edits outside this ticket, external posts or task-status changes by Mika.

### Assumptions and unknowns

- The issue is at the shared Flutter storage interface. Platform-specific restore behavior is not reproduced locally; tests inject the actual plugin channel failure.
- Hosted baseline RED is established on the test-only commit; corrected-candidate GREEN remains unknown until root executes the frozen commit.

## Dependencies and approvals

- Existing malformed-connect recovery and test seams are present in current main.
- No declared blocking dependency or owner decision exists on this task.
- Root saved In Progress via ClickUp UI and owns the start comment, review orchestration, PR/CI, merge and QA readback.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Platform read failure reaches Connect without an unhandled error or connect attempt | Real Launcher widget regression with secure-storage read throwing PlatformException | Connect shown after brand delay; splash gone; no framework exception; no storage delete/write | Hosted test-first RED and corrected launcher widget receipts | PENDING |
| C-002 | yes | Null-profile and valid-profile startup paths retain behavior | Widget controls for null profile and a valid profile passed to injected connect | Null reaches Connect without network; valid attempts reconnect with exact stored fields | Hosted launcher widget control receipts | PENDING |
| C-003 | yes | The new regression fails when the guard is absent | Frozen test-only commit before production edit | Actual assertion or unhandled keystore error demonstrates the missing behavior, not setup failure | PR 266, CI 40940174437, commit a7c931b4; PlatformException and missing PairingView; orchestration evidence wave2-20261029/mobile-red.log | PASS |
| C-004 | yes | Corrected source passes the relevant broader mobile gates | Hosted flutter analyze and flutter test on current integrated source | Analysis exits0 and full applicable Flutter suite passes | Root exact-source CI receipt | PENDING |
| C-005 | yes | Independent reviews and authorized delivery gates close | Cody, Quinn, Vera, Shadow; root merge/QA receipt | All current-source reviews pass, actual merge verified, exact QA status reread | Root delivery evidence and ClickUp handoff | PENDING |

## Verification plan

- Focused verification: extend test/views/launcher_connect_failure_test.dart using the existing MethodChannel mock and connect seam; observe actual hosted RED before minimal implementation.
- Broader regression verification: hosted flutter analyze and full flutter test, including existing launch-connect failure tests.
- Independent verifier: Cody, Quinn, Vera and Shadow, coordinated by root.
- Required environment: hosted Linux Flutter workflow; keystore failure injection through the actual Flutter plugin channel. Local native/physical device reproduction is not claimed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: a platform read error escapes before Launcher reaches any navigation; guarding this read as PairingView does will recover through the existing first-run path.
- Change or investigation: inspect exact source, create isolated branch, and add regression/control tests before modifying production.
- Verifier executed: structural goal validator; root-hosted Flutter analysis and full test suite on test-only commit a7c931b42003141b7c45ac07d1dfa3b476b9e4ac.
- Result: actual behavioral RED. Flutter analysis passed. The full suite reported 382 passed and 1 failed: the new platform-keystore-read test raised PlatformException(keystore_unavailable) and found zero PairingView widgets. Both null-profile and valid-profile controls passed.
- New evidence: PR 266 / CI 40940174437, saved by root at wave2-20261029/mobile-red.log; inspected the exception, missing-route assertion and control results before changing production.
- Decision: iterate

### Iteration 2

- Target criterion: C-001, C-002, C-004, C-005
- Hypothesis: guarding only StoredSession.load with the existing PairingView-style Object catch routes an unavailable profile through the established null-profile path without changing reconnect or navigation ownership.
- Change or investigation: guard the read in Launcher._start; leave profile storage untouched and preserve the existing brand delay, mounted checks and separate narrow connect guard. Tests remain unchanged from the observed RED commit.
- Verifier executed: source inspection, git diff --check and structural Goal Contract validator. No local Flutter runtime was run because host resource admission remains unavailable.
- Result: source candidate prepared; hosted corrected-source analysis/full tests and four independent reviews remain pending root execution.
- New evidence: production diff is confined to the guarded stored-profile load and clarifying the separate connect-guard comment.
- Decision: hand off frozen candidate to root for hosted GREEN and independent review; remediate valid findings within the remaining iteration budget.

## Risks and rollback

- Risks: fallback must not wipe an unreadable profile, expose plugin error text, or change valid-profile reconnect/navigation.
- Rollback or recovery: revert this ticket only; no schema, storage format or wire change.

## Pause and escalation conditions

- Test-only RED was observed before production changes; wait for root's corrected-source hosted results and independent reviews before claiming completion.
- Return any genuine owner decision or missing runtime evidence to root; continue independent allowed work without a user permission request.
- Do not run local heavy verification to bypass failed resource admission.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0wg3-keystore-startup.md
- Validator result: structural validation passed (exit 0); behavior remains pending hosted execution
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001, C-002, C-004 and C-005; C-003 passed on the frozen test-only commit
- ClickUp final evidence comment: root owns publication
