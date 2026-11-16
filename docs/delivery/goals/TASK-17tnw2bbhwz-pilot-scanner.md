# Goal Contract — TASK-17tnw2bbhwz-pilot-scanner

## Identity

- Goal ID: TASK-17tnw2bbhwz-pilot-scanner
- Parent goal ID: NONE
- Title: Confine the pilot exception to two consumed native credential fields
- Role: devops-engineer
- Status: BLOCKED
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhwz
- Created: 2026-10-31
- Updated: 2026-11-03
- Maximum iterations: 6
- Independent verification required: yes

## Objective

An ordinary installer cannot carry pilot/developer credentials; a provenance-bound pilot permits only its two exact consumed native fields, with secret-safe deny scanning of every shipped component.

## Baseline

Base a2ed7f96dd5eb8508406f7a901c1ad57d3a519b5 has P02 generated native source. Existing8markers/45selftests pass unchanged. P03 native files are reserved to Nova/Farah until freeze/merge. Actual provider approval and produced-installer proof are unavailable from fixtures.

## Inputs and evidence sources

- Browser-verified P04 original3criteria: root p04-clickup-source.txt
- Root-accepted Aria minimal contract aria-p04-contract.md; endpoint call-site attribution explicitly not required
- P02 source and unchanged scanner/licensing development key gate

## Scope

### In scope

- Python policy/all-occurrence matcher, canonical payload/frame and native-image/slice admission; package provenance/inventory controls; tests/docs
- Narrow consumed native envelope integration only after root coordinates P03 merge

### Non-goals

- Real credential access, .env discovery, provider calls, competing heavy builds, workflow enablement, dispatch, uploads or public artifacts
- P03 consent/transport/deadline logic or unrelated API/mobile/marketing work

### Constraints

- Own isolated worktree/branch only, never revert others; root owns browser/review/merge
- Preserve8ordinary markers/45controls/default scanner API/floors/positivecontrols/read-onlyhashes
- Only2exact credential spans; no package-wide endpoint/credential bypass

### Assumptions and unknowns

- UNKNOWN native envelope retention per platform; platform acceptance requires actual compiler/package proof
- UNKNOWN P01 real issuer restrictions/expiry; synthetic source admission never authorizes real embedding

## Dependencies and approvals

- User authorized atomic implementation plus4reviews/fixes/re-review/main merge; root accepted Aria contract
- P03 native ownership blocks hooks until coordinated merge; Python phase allowed now
- P01 remains real-input/publication gate, not permission to read existing keys

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Ordinary policy retains old controls and rejects pilot/known credential bytes | old45selftests and new policy negatives | oldcontrols and ordinary negatives pass | 28focused controls and45old selftests | PASS |
| C-002 | yes | Only2field spans in1consumed native envelope per expected slice pass | frame/schema/image/all-occurrence controls and narrow native probe | duplicates/outside/encoded/ambiguous keys and bad provenance fail | Python native fixtures pass; actual Rust hooks wait P03 | BLOCKED |
| C-003 | yes | Known unrelated secrets/development signing fixtures fail without diagnostics leaking | inventory/labeled matcher/captured-output canaries | no8byte fragment or input fingerprint in output/errors | focused output/error/repr controls and public fixture inventory | PASS |
| C-004 | yes | Accepted platform uses actual produced installer/fresh extraction/closed inventory/hash proof | real platform extraction + package/native validation | no synthetic fixture substituted for installer acceptance | platform run links | BLOCKED |
| C-005 | yes | Real input meets P01 restrictions/expiry and fixed cohort | actual issuer proof linked by root | no real embedding without approval/proof | P01 ticket | BLOCKED |
| C-006 | yes | Integrated source passes4independent reviews and normalCI after fixes | Cody/Shadow/Quinn/Vera + exactheadCI | no blockers, applicable checks green | root review reports | PENDING |

## Verification plan

- Focused verification: unittest scripts/test_pilot_installer_scan.py and unchanged scanner selftest
- Broader regression verification: affected packaging/workflow suites and exactheadCI; no competing whole operator build
- Independent verifier: root-coordinated4reviewers
- Required environment: Python3.9+ (3.9.6 verified), tiny local native fixture compiler; actual package adapters remain platform gates

## Iteration ledger

### Iteration 1

- Target criterion: C001–003 Python phase
- Hypothesis: exact canonical frame plus all-occurrence labeled matching confines2field spans while preserving deny scanning
- Change or investigation: tests first, then bounded core; native hook waits P03
- Verifier executed: old scanner selftest
- Result:28focused controls and45old selftests pass; tiny native consumed-frame fixture compiled, not executed
- New evidence: scripts/test_pilot_installer_scan.py and docs/release/PILOT-SCANNER.md; Python phase frozen at a2ed7f96 base
- Decision: blocked; hand Python phase to root pending coordinated P03 native ownership release

### Iteration 2

- Target criterion: C002 complete framed candidate accounting
- Hypothesis: classifying a complete frame by header/length/trailer independently of body syntax closes the confirmed ignored nonobject-frame gap without rejecting standalone runtime MAGIC
- Change or investigation: owner reproduced Aria audit with complete second nonobject/non-JSON/empty and overlength bodies; added standalone-adjacency compatibility controls
- Verifier executed: scripts/test_pilot_installer_scan.py and original scanner --self-test
- Result: RED4failures, then GREEN31focused and45old controls
- New evidence: focused regression tests and docs/release/PILOT-SCANNER.md audit-correction section
- Decision: blocked; return corrected Python phase, keep native/extraction/P01/review gates open

### Iteration 3

- Target criterion: C003/C004 declared frontend policy and build-chain helper source
- Hypothesis: separate known-actual-secret scanning of closed reviewed frontend inputs preserves public help while fresh generated-output and emitted/package hash bindings fail stale source/cache/member evidence
- Change or investigation: root-accepted aria-p04-embedded-assets.md clarification; own Python asset helper/tests/docs only, no native files
- Verifier executed: focused asset tests initially RED5missing-module failures; existing31core/45old controls retained
- Result:9asset controls pass after RED,31existing policy and45old controls pass; helpers cannot prove an actual Tauri/Cargo/package chain
- New evidence: scripts/test_pilot_asset_provenance.py and docs/release/PILOT-SCANNER.md Iteration3 section
- Decision: bounded final iteration; native/extraction/P01/review gates remain blocked/pending, later continuation needs explicit budget disposition

### Iteration 4 — root-authorized review remediation

- Authorization: p04-review-remediation-disposition.md explicitly extends the consumed3iteration budget to5 before work; original ledger/predicate unchanged. Iteration5 reserved only for verified re-review correction, no6/native work.
- Target criterion: C003 diagnostic boundary and V-P04-1 bounded known-secret scan passes
- Hypothesis: suppressing implicit exception context centrally closes full traceback/logger leakage; validated deduplicated deny probes in one matcher pass remove inventory-sized full-file rereads
- Change or investigation: reproduce P04-SHADOW-01 and V-P04-1 with focused RED controls, then fix owned Python only
- Verifier executed: test_pilot_asset_provenance.py, test_pilot_installer_scan.py, original scanner selftest
- Result: RED2findings reproduced; GREEN11asset/31core/45legacy, logical target read passes independent of inventory0vs16; whole native/package/P01/review gates remain blocked/pending
- New evidence: root disposition, four phase reports at ac8798b9, traceback/logger and read-count regressions
- Decision: bounded remediation; no silent further extension

### Iteration 5 — reserved verified re-review correction

- Authorization: root invokes reserved5only for P04-QUINN-02; no6 or native work allowed
- Target criterion: C003 finite filesystem metadata/source-resolution refusal boundary
- Hypothesis: a narrow OSError boundary at public/shared filesystem helpers plus a resolve-only RuntimeError conversion closes uncaught preflight failures without hiding programming errors
- Change or investigation: RED full traceback/logger metadata and source-resolution controls; portable own chmod000 case with finally cleanup
- Verifier executed:15asset diagnostics/read-count tests,31core tests,45legacy selftests
- Result: RED6preflight failures reproduced; GREEN15asset/31core/45legacy including actual chmod000 and resolve-loop cases, no skips; whole native/extraction/P01/currentCI gates unchanged
- New evidence: round2 Quinn/Shadow/root diagnostics; prior findings independently closed
- Decision: final bounded correction frozen for final snapshot refresh; max5consumed, no6 or native continuation

### Iteration 6 — authorized closed-inventory review correction

- Authorization: current user authorized MR remediation; root explicitly extends exhausted maximum5 to6 for confirmed Q-P04-03 only. Original criteria and iterations1–5 are preserved. No native/driver/extraction/P01 work or acceptance waiver.
- Target criterion: C003/C004 source-phase closed inventory, unreadable recursive subtrees.
- Hypothesis: pathlib rglob suppresses child traversal errors; explicit error-propagating scandir traversal refuses unreadable unlisted subtrees while preserving symlink/depth/count/byte/time bounds.
- Change or investigation: regression-first actual permission refusal and deterministic iterator refusal; smallest traversal correction only.
- Verifier executed: regression-first scanner suite RED2; corrected scanner/asset/legacy suites and structural validation.
- Result: GREEN33core/15asset/45legacy controls, no skips; actual mode000 subtree refuses, recursive iterator failure is sanitized, and readable extra/missing inventory remains rejected.
- New evidence: docs/delivery/evidence/p04-scanner-review-fix.md and two focused regressions.
- Decision: root owns four-review refresh and exact-head CI; whole C002/C004/C005 remain BLOCKED.

## Risks and rollback

- Risks: compiler pooling, unsafe extraction, stale provenance and diagnostics; fail closed
- Rollback or recovery: revert P04 unit; ordinary deny policy and real-input block remain

## Pause and escalation conditions

- Native edits await P03 merge and root coordination; no criteria waived
- Stop after3materially distinct failed approaches without new evidence
- Full completion requires actual package/P01 and independent checks

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhwz-pilot-scanner.md
- Validator result: structural validation passed before iteration; repeat at phase handoff
- Independent verification result: pending
- Terminal state: BLOCKED
- Remaining failed or blocked criteria: C002 actual native hooks/retention, C004 real extraction/package, C005 real provider proof; C006 integrated reviews/CI pending
- ClickUp final evidence comment: root owns browser, not yet claimed applied
