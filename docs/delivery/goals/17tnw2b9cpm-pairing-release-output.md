# Goal Contract — TASK-17tnw2b9cpm

## Identity

- Goal ID: TASK-17tnw2b9cpm
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Keep release pairing credentials out of inherited output streams
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9cpm
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A release-profile host can turn pairing on without writing its real pairing code or invite link to stdout or stderr, while debug builds retain the developer printout and stage QR/authentication lifecycle remains intact.

## Baseline

Actual main93bf472f65a1846117eecf09b1972c4118dc0cd4. The GUI App toggle offers a 120-second single-use Producer pairing code, prints the URI/code/ASCII QR unconditionally, and shows the same invite on stage. The packaged operator inherits stdio. Full existing task has zero comments, no dependencies, no parent and linked17tnw2b9aga. This is Low defense in depth; redeeming still requires operator approval and role assignment, and stage observers already see the QR.

## Inputs and evidence sources

- Frozen complete mobile-qualification/17tnw2b9cpm.json and qualification report, AGENT-RUNBOOK.md, selected20.
- selahcue-desktop main pairing/host startup and existing real-host test seams; LAN pairing/session APIs; root/desktop CLAUDE guidance.
- Root-approved actual childprocess host/TLS-registry capture and mechanical exact-body extraction plan, not a formatter-only or physical-GUI claim.

## Scope

### In scope

- Actual release build omits pairing code/invite from both inherited streams; safe message points to stage QR. Debug retains current printout.
- Mechanical shared pairing-toggle body used by App and host-domain process tests; original behavior/body identity proved before actual RED.
- Real host thread/TLS listener/registry starts in child process with existing hermetic environment seams; pairing-on and actual code/link read via private test receipt separate from captured output.
- Real stage QR, single-use/approval/withdrawal invariants and actual debug/release profile coverage, meaningful mutants/restoration and normal configured gates.

### Non-goals

- No TTL, auth/role/approval, network policy, stage UI or operator-console policy change; no new production test mode or CLI flag.
- No controller/autolaunch/LAN protocol/operator main/headless edits, unrelated owner holds or deployment.
- No physical native GUI/macOS/Windows/device acceptance or universal performance claim.

### Constraints

- Own managed worktree/branch, one ticket/PR, no reverting others. Parent owns tracker/four reviews/consolidation/merge/QA.
- No local project runtime/import/test/build/install/container/simulator/benchmark; hosted-only execution. Tiny Git/stdlib/static checks allowed.
- Actual release RED and debug/host positives before behavior fix. Capture real streams; setup/compile/oracle failures remain failures, not RED proof.
- Real cfg(debug_assertions) from actual profiles, not a test-supplied boolean pretending to be release. Private synthetic-code receipt never logged.

### Assumptions and unknowns

- UNKNOWN actual release stream contents until hosted RED. Existing safe host seam uses loopback/no mDNS/private endpoint; no live shared host files.
- Native GUI route is preserved by exact delegation/source review; automated evidence exercises the real shared host domain process without GPU windows.

## Dependencies and approvals

- User-authorized frozen20 plus root dispatch and explicit root approval of real-host childprocess/TLS-registry domain test with mechanical shared toggle.
- Other Mika owns controller/autolaunch observation; JSON author owns protocol/tls/errors; Farah owns headless/operator main. Any overlap returns to root before edits.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual release pairing output defect reproduced before fix | Hosted actual debug/release child host capture, exact-body/source proof | Release genuinely prints actual code/link and fails; debug/real startup/QR controls pass | pairing-release-output/red-job.log and red-classification.json actual debug138/0, release pairing0/1, release banner8/0 | PASS |
| C-002 | yes | Release never discloses actual pairing code/link and debug retains developer printout | Actual-profile host capture and meaningful disclosure/debug mutants | Release both streams safe with stage instruction; debug actual code/link present; mutants caught; bytes restored | Candidate focused/mutation hosted receipts | PENDING |
| C-003 | yes | Real QR/auth/lifecycle remains correct | Actual host registry/stage QR/single-use/pending approval/withdrawal positives and source comparison | Stage invite is real; role approval and120s/single-use semantics unchanged; no live shared files | Host child assertions and immutable source proof | PENDING |
| C-004 | yes | Required final normal and profile-specific gates pass | Hosted normal configured Linux plus explicit debug/release host tests | All required executed gates pass; ignores/skips/platform limits explicit | Current-source normal and supplemental raw | PENDING |
| C-005 | yes | Four independent reviews, actual merge and exact QA handoff verified | Root Cody/Quinn/Vera/Shadow, merge parents/tree and ticket qa reread | All4 Pass/no unresolved findings, reviewed result merged and linked task QA | Root reports/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: child test process starts actual TLS host, toggles pairing, captures stdout/stderr, independently checks actualcode+invite receipt; real cfgdebug/release.
- Broader regression verification: existing host/banner/pairing tests and full normal affected Linux/Rust/operator/native/launch/audit gates; exact tests/source restoration.
- Independent verifier: root-coordinated Cody, Quinn, Vera and Shadow.
- Required environment: hosted pinned Rust/Linux with existing setup/cache/default encryption; source/Git/stdlib/static locally only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: unconditional print_pairing_block writes real code/link in actual release profile; exact shared toggle and child real-host stream capture can prove it without starting unsafe GUI App storage.
- Change or investigation: complete task/callers/readiness/role/runbook read, managed worktree from actual93bf; create+attach registration100cap retained and returned own path reused. Root confirmed real-host domain process gate and exact mechanical extraction.
- Verifier executed: source/metadata inspection and structural child validator before substantive tests.
- Result: scope established; runtime, review and delivery pending.
- New evidence: full task, approved plan and this contract.
- Decision: iterate

### Iteration 2

- Target criterion: C-001.
- Hypothesis: actual release prints the real code while real debug and lifecycle controls pass.
- Change or investigation: independently read official41186228673 raw/metadata at exact tests-first827/workflow-onlyf9d5. Debug fullhost138passed0failed6existing/childignored, actual debug code+URI capture positive; real release parent fails specifically on actual code in stdout after successful child lifecycle/private receipt; release existing-banner8passed0failed. No compile/setup/oracle substitution. URI assertion was after first code assertion, so original actual release URI presence is not separately claimed. Six component hashes restore exactly; original diagnostic marker substitution is recorded honestly.
- Verifier executed: official raw phase/test/failure/compiled-profile markers, immutable parent/source/workflow/body proofs and final component maps.
- Result: C-001 PASS; exact release code-exposure defect reproduced. All final candidate/profile/mutation/review/delivery gates remain pending.
- New evidence: pairing-release-output/red-job.log, red-metadata.json, red-classification.json and extraction-proof.json.
- Decision: iterate

### Iteration 3

- Target criterion: C-002 through C-004.
- Hypothesis: an actual release cfg guard with a safe stage-QR notice prevents inherited-stream disclosure while preserving the exact debug printout and pairing lifecycle.
- Change or investigation: minimal early release branch in print_pairing_block; original developer print body remains byte-identical after the guard. Added nonsecret boolean stream-premise traces to the existing parent test without weakening assertions; final independent code-only/link-only stderr and debug-suppression mutants must prove both stream/oracle obligations.
- Verifier executed: installed pinned formatting, source/diff/component/contract static checks; hosted candidate profiles/normal/mutants pending.
- Result: candidate prepared, no runtime-green or review/completion claim.
- New evidence: forthcoming immutable candidate/component/profile/mutation receipts.
- Decision: handoff

## Risks and rollback

- Risks: a formatter-only oracle, synthetic profile boolean, leaked fixture code in test logs, widened trust seams or omitted actual toggle/auth side effects.
- Rollback or recovery: actual childprocess/profile captures, private code receipt, exact extraction proof, minimal profile guard and meaningful source-mutant restoration; isolated PR can be reverted if evidenced.

## Pause and escalation conditions

- Stop for new product/policy or destructive/production access. Preserve every failed/setup/unknown outcome; bounded diagnostics only with new evidence. No next selected unit without root dispatch.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9cpm-pairing-release-output.md
- Validator result: PASS structural validation before extraction and tests
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-005
- ClickUp final evidence comment: root-owned
