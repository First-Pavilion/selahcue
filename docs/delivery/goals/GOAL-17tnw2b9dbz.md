# Goal Contract — TASK-17tnw2b9dbz

## Identity

- Goal ID: TASK-17tnw2b9dbz
- Parent goal ID: NONE
- Title: Detect compiled STT developer-override capability in release artifacts
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9dbz
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective

A real optimized release binary that honors the development STT model override must carry a detectable marker and fail the unchanged installer scanner policy; a normal release must ignore the override and scan clean.

## Baseline

Verified main013a84bc70055d63c79c1ba12212e631842fb03d: scanner has8 signatures/45 self-test cases; STT override relies on cfg debug_assertions and no effect marker. Installer builds operator with stt; actual worker/readiness paths call stt_model_source::model_source_from_env. Rust/Cargo1.98.0 match pinned toolchain. Isolated Git worktree /private/tmp/selahcue-17tnw2b9dbz-stt-effect-guard, branch codex/17tnw2b9dbz-stt-effect-guard. Managed-worktree API failed repository identification; no user checkout changes.

## Inputs and evidence sources

- Root live-read task brief and snapshot /private/tmp/17tnw2b9dbz-selected-task.json.
- Actual stt_model_source.rs, operator Cargo features/main/listening call sites, windows-installer.yml and installer_secret_scan.py.
- Follow-up17tnw2b0prh and known inline profile/rustflag/legacy config/environment bypasses documented in the owning module.

## Scope

### In scope

- Debug-only unique marker on actual reachable DeveloperOverride branch; permanent scanner signature/pins/self-test growth; actual compiled production-module artifact tests and narrow documentation.

### Non-goals

- Installer release/dispatch, providers, model downloads, GUI automation, secrets, unrelated credentials/guards, workflow changes owned by PR350, runtime override-policy weakening.

### Constraints

- Preserve all scanner targets, encodings, byte floors, redaction and fail-closed behavior. Marker proof must come from real reachable source, not fixture injection/unreferenced static. Demonstrate optimized/LTO and stripped retention on native platform, label Windows/full-operator limits honestly. Python imports at top in new code. Integrate reviewed main normally before freeze; preserve other worktrees and primary mobile lock.

### Assumptions and unknowns

- UNKNOWN: Windows/MSVC full installer build is outside this native bounded artifact proof; existing packaging scanner remains the shipping effect gate.
- VERIFIED: ClickUp start/status write is pending quota/UI deadlines; root explicitly authorized necessary implementation exception, not a claim of saved In Progress.

## Dependencies and approvals

- Root owns ClickUp, independent Cody/Shadow/Quinn/Vera reviews, actual CI, merge and QA. Pending start-comment payload supplied to root; no connector retry.
- PR350 scanner normal-CI wiring is unmerged/independent; do not edit its worktree/workflow scope. Root reports main85f1fbe after cache355 with no scanner/STT/toolchain delta; integrate at final freshness check.
- User wave authorizes scoped draft source publication; actual auto-review rejection stops publication retries.

## Completion predicate

All mandatory rows must be PASS for VERIFIED_COMPLETE.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual reachable override in optimized assertions-on release is rejected, normal release is pinned/clean | Build real operator normal/unsafe profiles; python3 scripts/test_stt_override_artifact.py --normal-operator SAFE --unsafe-operator UNSAFE --output-dir TASK_TMP | Unsafe real binary honors override and scanner rejects marker; safe real binary pinned and full scanner passes | docs/delivery/evidence/17tnw2b9dbz-stt-effect-guard.md | PASS |
| C-002 | yes | Marker survives LTO/stripping when unsafe path exists, no fabricated binary payload/floor relaxation | Actual production-module source hashes and stripped native artifact matcher | Unsafe stripped binary still contains declared marker; safe does not; original full scan byte floor retained | docs/delivery/evidence/17tnw2b9dbz-stt-effect-guard.md | PASS |
| C-003 | yes | Existing guards and new signature encodings/pins remain fail closed without value disclosure | python3 scripts/installer_secret_scan.py --self-test and optimized-Python run | At least47 cases pass, retained guards/targets/encodings/floors and new UTF8/UTF16LE injections | docs/delivery/evidence/17tnw2b9dbz-stt-effect-guard.md | PASS |
| C-004 | yes | Owning runtime module tests and affected formatting/source guards pass | Actual stt_model_source Rust tests debug/release, formatting and targeted import/release guards | Tests/checks exit0 with scoped native evidence; no installer dispatch | docs/delivery/evidence/17tnw2b9dbz-stt-effect-guard.md | PASS |
| C-005 | yes | Current hosted CI and all four independent reviews pass frozen source | Parent Cody/Shadow/Quinn/Vera reports and actual CI | All PASS before merge/QA | Parent review handoff | PENDING |
| C-006 | yes | Pending ClickUp start/evidence/status updates are actually saved/read back | Root authenticated status/comment receipt | In Progress/start/evidence visible; no invented save | Root delivery tracking | PASS |

## Verification plan

- Focused verification: actual offline scratch Cargo release builds including production module, runtime profile effects, full scanner on real operator artifacts and supplemental small-probe stripped matcher, source/artifact hashes; paired safe/unsafe baseline RED then GREEN.
- Broader regression verification: full scanner self-tests normal/optimized Python, owning std-only Rust module debug/release tests, affected formatting/source guards. Preserve full operator/installer limits explicitly.
- Independent verifier: Cody, Shadow, Quinn and Vera dispatched by root.
- Required environment: pinned Rust/Cargo1.98.0, native host compiler/linker/strip; scratch isolated Cargo home/targets, no downloads, no GUI/model/provider operation.

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002.
- Hypothesis: source-exact release probe demonstrates current assertions-on override with no scanner finding, establishing meaningful RED before marker/signature changes.
- Change or investigation: traced actual operator feature reachability and scanner policy; prepared bounded artifact verifier only after contract validation.
- Verifier executed: structural contract; baseline45 scanner tests and real artifact RED.
- Result: baseline scanner45PASS; first real small probe406808bytes cannot pass unchanged1MBfloor. Root directed real operator builds for mandatory full-scanner proof; no padding/floor reduction. Source-exact small probe remains explicitly supplemental. Fullnormaloperator38,375,504bytes scannerGREEN; globalassertions-on35,545,088bytes alreadyREDfor existingDeepgram only, lacksSTTspecificmarker (do not claim whole-old-scanner bypass). Owning module baseline24debug/24releasePASS; specificSTTartifact assertionRED and newonce/no-input-echo testRED.
- New evidence: root status write explicitly pending exception; no false In Progress claim.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001 through C-003.
- Hypothesis: a debug-only fixed notice on the actual DeveloperOverride branch, consumed by the existing once-only Write path, survives optimization and independently identifies the STT capability without exposing caller inputs.
- Change or investigation: implement observable marker (not unreferenced static/black_box), retain release policy, add ninth permanent scanner signature/pins and47case floor. Root approved real fulloperator objective and native-only scope. New privacy/once test observed RED before production code. Normally integrated reviewed main1488 before final builds; historical baseline artifacts are old013 evidence only.
- Verifier executed: owning module privacy/fulltests, scanner47 normal/optimized, source-exact optimized supplemental cases; actual final operator pairs follow after source checkpoint.
- Result: scanner47 normal/optimized Python PASS; complete owning module25debug/24release PASS; eight effective-profile/LTO/strip supplemental cases PASS; import guards PASS. Final full-operator proof remains pending.
- New evidence: global oldunsafe binary already had unrelatedDeepgram hit; additiveSTTmarker test correctly fails without STTneedle.
- Decision: iterate.

### Iteration 3

- Target criterion: C-001 through C-004.
- Hypothesis: final actual operator artifacts preserve the independently tested marker effect with unchanged full-scanner byte floor.
- Change or investigation: integrate reviewed main2f4dcc25 (including hygiene1488), checkpoint source; compile real operator normal and assertions-on release from identical desktop/toolchain/resource inputs.
- Verifier executed: paired full native operator builds and canonical scanner; final compiled-profile/module verifier.
- Result: PASS. Both final full operator builds exited0; normal38379104bytes full scannerGREEN/nohits, unsafe35546096bytes RED with explicitSTT UTF8hit plus retainedDeepgram hit. All455 recorded inputs match across both builds and final tree. Completed47normal/-O,25debug/24release,eight supplementalLTO/strip and import guard receipts retained; no extra build variants.
- New evidence: final actual input manifests and compiler feature/profile receipts retained separately from historical013 baseline.
- Decision: verify; reserve iteration4 for review remediation.

### Iteration 4 — reserved integrated-source refresh

- Target criterion: C-001 through C-006 freshness after reviewed issue370 merge.
- Hypothesis: normally integrated main22de62fc retains the STT effect while changed compiled autolaunch inputs require BOTH fulloperator artifacts rebuilt.
- Change or investigation: root expressly authorizes reservediteration4, preserving1–3; normal merge8824b03b integrates reviewedmain22 (including canaryc4). NativeSTT InProgress actually saved/readback by root. No publicAPIlocaldocs carried in; scanner350 remains separate required dependency, not waived.
- Verifier executed: pending fresh paired native operator builds/fullcanonicalscans, current47normal/-O/permanentmarkerrefusal,fmt/changedpathchecks and byteidentity of retained module/profileprobe inputs.
- Result: PASS current paired realoperator builds exit0; new455manifest equal acrossboth/finaltree, onlyautolaunchchanged from historical. Normal39133520GREEN, unsafe36276128REDexplicitnewSTT plusDeepgram. Current47normal/-O/requiredmarkerremovalrefusal/fmtPASS; changedpath10realtestsPASS, initialdoc-toolmismatch captured then onlyunfinisheddoctestphasepinned1.98 exits0. Retain byteidenticalearlier25/24+8 only.
- New evidence: newcurrenthashes/argv/compilerbinary/profiles/fullscan receipts in evidence; oldpair retainedhistoricalfd57. NativeSTT InProgress readbackrootverified.
- Decision: freeze after allverifiersfinish; root fouraffectedrefresh/currentCI/merge gates pending; no fifth iteration silently.

## Risks and rollback

- Risks: unreferenced marker optimized away, marker placed in safe release, scanner false confidence from fake data/too-small artifact, unsupported platform overclaim.
- Rollback or recovery: revert scoped marker/signature/test/doc changes; never weaken existing release gate or ship unsafe binary. Preserve raw artifact/compiler/source identity receipts for review.

## Pause and escalation conditions

- Stop for actual publication rejection, missing pinned toolchain/native prerequisite, material policy decision or max4 exhausted. No installer release or source/runtime scope expansion. Root owns pending delivery tracking and review remediation disposition.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2b9dbz.md
- Validator result: structural PASS; completion intentionally pending independent gates.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: C-005 currentintegratedCI/fouraffectedreviews and formalregularscanner350dependency pendingroot. C-001 through C-004 refreshedlocalPASS; C-006 actualnativeInProgress readbackrootverified. Iteration4of4 used; no silentextension.
- ClickUp final evidence comment: root owns pending authenticated update.
