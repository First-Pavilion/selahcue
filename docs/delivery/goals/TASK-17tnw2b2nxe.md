# Goal Contract — TASK-17tnw2b2nxe

## Identity
- Goal ID: TASK-17tnw2b2nxe
- Parent goal ID: NONE
- Title: WAL contention regression asserts busy-handler mechanism instead of runner speed
- Role: devops-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2nxe
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Make the existing WAL contention regression independent of host scheduling speed while deterministically detecting removal of the scoped checkpoint busy-timeout fix.

## Baseline
Verified main6b096771 and PR359be13c756 have identical selahcue-data/test/Cargo.lock sources. Hosted Ubuntu run41767835782 failed whole-delete585ms against500ms; historical ticket Windows556ms. Exact hosted slow phase unknown. Local original37 tests pass; controlled ordinary writer lock causes659ms transaction versus3ms checkpoint, whereas historical zero-timeout-removal mutation causes5.142s checkpoint.

## Inputs and evidence sources
- Parent full live read of existing17tnw2b2nxe and explicit authorized fix loop.
- selahcue-data/src/db.rs; tests/test_transcript_repo.rs; implementation/desktop/CLAUDE.md.
- /private/tmp/pr359-wal-diagnosis-handoff.md and raw controls.

## Scope
### In scope
- Test-only mechanism regression, public-API functional regression and diagnostic timings, one central timing-policy note.
- Bounded temporary PR proof for20 consecutive Windows and macOS passes; Goal/evidence.
### Non-goals
- Production behavior/dependency changes, installer execution, deployment, credentials, clock-threshold relaxation, retries or best-of masking.
### Constraints
- Own branch/worktree only; frozen359/355 and primary user lock untouched.
- Root owns ClickUp/reviews/merge/QA. ClickUp start write currently failed, not In Progress verified; parent expressly permits implementation while repairing native UI.
- Preserve public deletion, pinned-reader and writer-success checks; mechanism replaces wall-clock correctness gate per existing approved ticket AC, superseding preliminary preserve500ms proposal.
### Assumptions and unknowns
- UNKNOWN exact hosted585ms slow phase; do not label proven environment variance.
- VERIFIED actual Windows20 in run41828208557 and local macOS20; these are distinct host receipts.

## Dependencies and approvals
- Root existing-ticket scope receipt authorizes this fix and bounded host proof; no new ticket.
- Root coordinates all four independent reviews and actual CI before merge; refresh359 afterward.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Mechanism regression catches actual scoped timeout removal without clock gating | real SQLite positive control and actual old-timeout-removal mutation | fixed code green; mutation fails because busy handler invoked | docs/delivery/evidence/17tnw2b2nxe.md | PASS |
| C-002 | yes | Public deletion and writer behavior remain checked independently of runner speed; one timing-policy note exists | focused/full data suite plus source review | functional checks pass; timings diagnostic only; no production behavior changes | focused suite and diff | PASS |
| C-003 | yes | Twenty consecutive Windows and macOS focused runs pass without retries | bounded host proof on final source and local macOS20 | all20 per host pass; any failure aborts proof | local logs and hosted run URL | PASS |
| C-004 | yes | Applicable gates, four independent reviews and actual CI pass | cargo fmt/clippy/data tests, workflow controls and Cody/Shadow/Quinn/Vera | checks pass on reviewed head; main verified before QA | root PR/CI/review receipts | PENDING |

## Verification plan
- Focused verification: existing failing control then deterministic busy-handler and timeout-restoration/WAL-positive controls; actual boundary mutation with siblings.
- Broader regression verification: full selahcue-data suite, formatting/clippy, workflow/minutes/actionlint checks if proof workflow added.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera.
- Required environment: macOS local, actual hosted Windows and macOS proof, ordinary Ubuntu PR CI. No simulated Windows claim.

## Iteration ledger
### Iteration1
- Target criterion: C-001 and C-002 baseline.
- Hypothesis: SQLite busy-handler invocation under pinned WAL is the causal invariant; elapsed whole-delete time cannot distinguish checkpoint waiting from scheduling/ordinary writer locks.
- Change or investigation: earlier baseline and two isolated actual-SQLite probes; inspect current private helper and public test.
- Verifier executed: original37-test suite,600ms writer-lock control and removed-zero-timeout mutation.
- Result: original37 pass; both controls red for distinct measured phases, supporting mechanism-based replacement.
- New evidence: /private/tmp/pr359-wal-diagnosis-handoff.md.
- Decision: iterate

### Iteration2
- Target criterion: C-001 and C-002.
- Hypothesis: a real pinned-reader positive control plus thread-local busy-handler observation detects removal of the scoped timeout boundary regardless of scheduler speed, while the public scenario retains functional concurrency checks.
- Change or investigation: added two private real-SQLite tests; replaced three elapsed assertions with diagnostic timings; kept concurrent writer layout and original 5 ms pacing, clarified that pacing cannot prove overlap; added one central timing-policy note. Production implementation unchanged.
- Verifier executed: new mechanism tests GREEN; actual zero-timeout-removal mutation with both lib siblings RED; restored source. Encrypted full data suite in progress; Windows proof prepared with existing registered ci workflow, manual branch-ref only, readonly/no credentials, 15-minute bound.
- Result: mechanism tests pass; mutation fails because busy-handler count is 1 instead of 0, not because time elapsed. Initial test-file append used the wrong relative path and wrote nothing; an empty-filter run is excluded from evidence, then the correct two-test target ran successfully.
- New evidence: /private/tmp/17tnw2b2nxe-mechanism-green.log; /private/tmp/17tnw2b2nxe-old-timeout-mutant.log.
- Decision: iterate

### Iteration3
- Target criterion: C-003 host proof and C-004 local controls.
- Hypothesis: the same final Rust tree passes20 consecutive real macOS/Windows runs; explicit binding to the verified Windows Perl avoids shell-specific PATH drift during SQLCipher setup.
- Change or investigation: local macOS20 completed; final formatting/clippy/full encrypted data suite and seven normal workflow controls passed. First Windows proof failed before tests because Git Bash selected incomplete MSYS Perl, while pwsh had verified Strawberry Perl. Inspecting openssl-src confirmed OPENSSL_SRC_PERL selects its actual executable; proof-only correction persists the verified path and checks required modules. No Rust changes.
- Verifier executed: local40 target invocations; final local controls; hosted41827583650 setup and failure logs; actual encrypted old-boundary mutation with all data siblings.
- Result: macOS20 pass; old mutation fails deterministic count1 versus0 and preserved public append_detection with DatabaseBusy. First hosted run failed setup, zero test iterations; Windows proof pending corrected setup, not represented as pass or a test retry.
- New evidence: /private/tmp/17tnw2b2nxe-macos20.json; final-rust.json; final-controls.json; encrypted-old-mutant.log; windows-proof-failed.log.
- Decision: iterate

### Iteration4
- Target criterion: C-003 host completion and final predicate evaluation.
- Hypothesis: corrected Windows Perl selection permits the unchanged Rust source to complete the required host proof without retries; exact blob identity permits restoring temporary CI without invalidating that source evidence.
- Change or investigation: completed Windows proof; restored ci.yml byte-for-byte from main6b096; documented failed setup, real named-test counts and unchanged Rust blobs. No production behavior or Rust-source changes after the original proof commit.
- Verifier executed: actual run41828208557 log parsed for each START/PASS1..20, exactly one actual completion marker and20 passes for each named test; local macOS20; final187-test encrypted suite, warning-clean clippy/fmt and eight normal policy/toolchain checks. Final structural Goal/diff validation at handoff.
- Result: C-001 through C-003 PASS. Initial log parser rejected the echoed script literal as a second completion marker; corrected parsing anchors actual timestamped output, no test rerun. Both final Rust blobs equal cb583e073711e7851c9a4e3b93f68364167c1e25. No permanent CI workflow diff remains.
- New evidence: docs/delivery/evidence/17tnw2b2nxe.md; /private/tmp/17tnw2b2nxe-windows20.json; proof-source-identity.json and final local verifier receipts.
- Decision: gate-review

## Risks and rollback
- Risks: callback cross-test pollution, vacuous pinned-reader control, accidental removal of end-to-end functionality; isolate callback state and require real contention plus uncontended WAL truncate.
- Rollback or recovery: revert isolated test/docs/proof changes; no persisted product state.

## Pause and escalation conditions
- Stop for production behavior changes, unavailable real Windows proof or four iterations exhausted; no gate waiver.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b2nxe.md
- Validator result: structural validation passed; final structural validation recorded at handoff. Completion intentionally pending C-004.
- Independent verification result: pending root.
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-001 through C-003 PASS; C-004 local checks pass, root-owned four independent reviews/final-head CI/main/QA pending.
- ClickUp final evidence comment: root owns authenticated UI; pending write is explicit, not claimed saved.
