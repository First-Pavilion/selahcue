# Goal Contract — 17tnw2b13xz

## Identity

- Goal ID: TASK-17tnw2b13xz
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Store canonical scripture link references from LAN clients
- Role: mobile-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b13xz
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The host stores the existing parser's canonical Reference Display for a successfully parsed SetItemContent scripture link, retaining chapter fitting, translation pinning, already canonical bytes and existing denial/legacy/Preview-only behavior.

## Baseline

Fresh actual main400bbb524de76e4cbc49b8c99db7df6299b6dfa4 after root-verified AY5JM merge. Full frozen task/comments packet has zero comments/dependencies/links and explicitly requests canonical storage after parse succeeds. Current set_item_content validates parse_one but discards Reference and stores sanitized input unless fitting changes it. fitted_scripture_reference returns None for an in-range passage. Existing parser tests already confirm to/en-dash/through forms canonicalize to Romans8:28-30; existing controller tests pin canonical input, missing passages, chapter fitting and translation pinning.

## Inputs and evidence sources

- W3 mobile-qualification/17tnw2b13xz.json, qualifications.md, selected20.json and AGENT-RUNBOOK.md.
- Root/desktop CLAUDE guidance and canonical runtime/mobile/Goal contracts; no AGENTS files found.
- selahcue-app controller.rs set_item_content, item_content_from_link and fitting helpers; existing controller/remote integration tests; core parser Reference Display/tests.
- Root explicitly assigns this host LAN unit to Mika and reserves controller.rs from concurrent Kenji AWR edits.

## Scope

### In scope

- Minimal set_item_content canonical storage after successful existing parse, preserving fit/pin order and policy.
- Focused public controller and actual pinned-TLS authenticated SetItemContent/RemoteOperator regressions and positive controls; this Goal.
- Separate exact-parent hosted mutation diagnostic and normal affected Rust CI; compact immutable review-dispatch evidence.

### Non-goals

- Parser syntax, mobile range selection, default translation policy, protocol/auth/transport/error semantics, load-time legacy rewrites, unrelated controller behavior or additional units.
- Native output/GPU/device acceptance; these are not required for this host command storage regression.

### Constraints

- Own isolated managed worktree/codex branch; creation returned actual checkout with100-registration cap, use actual path without duplicate/retry. Shared repo; never stage/revert others.
- No local project runtime/import/build/test/install/container/benchmark. Hosted genuine entry-point RED and positives before production edits; setup/compiler failure is not RED.
- Existing Reference Display only; preserve malformed denial, missing-but-parseable acceptance/status, chapter-fit translation pinning, fit-free default translation absence, metadata and Preview-only/no-Live semantics. Do not broaden load-time behavior.
- Ordinary push/one draftPR/body-file/immediate attachment attempt and bounded separate workflow-only diagnostics authorized. No forcepush/protected edits/subagents/ClickUp/status/review publishing/merge or next DQ0.
- Root owns four independent reviewers, remediation routing, current-target proof, merge and exactQA. Start/status and live UI refresh pending unlock; frozen unchanged scope remains authorized.

### Assumptions and unknowns

- Frozen full task/comments are verified; fresh live tracker read is unavailable while Mac locked and connector capped. Root owns catch-up, no tracker receipt is claimed.
- Runtime and full gate results pending. Source inspection does not establish behavior; loopback TLS is not a physical LAN/native output acceptance claim.

## Dependencies and approvals

- Existing parser support and prior PR144 are merged in actual main; no decision gate in captured task. Root reserves controller.rs ownership for this ticket.
- AY5JM merged; QA/completed export remains pending root receipt, closed source stays unchanged.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Loosely spelled scripture references are stored canonically through actual host command entry points | Public LiveController apply and real pinned-TLS authenticated SetItemContent/RemoteOperator tests | to/en-dash/through inputs store Romans 8:28-30 in plan and returned view, not raw input; canonical input byte-identical | Hosted RED/GREEN named assertions/raw | PENDING |
| C-002 | yes | Existing fitting, translation, malformed and unresolved contracts remain intact | Same real entry-point positive/negative controls and existing fit/legacy suites | Fit/pin preserved; fit-free translation absence/explicit code and metadata unchanged; malformed denies without mutation; parseable missing remains accepted/missing | Hosted focused/full Rust results | PENDING |
| C-003 | yes | Permissions and audience output are preserved | Actual authenticated forbidden-role denial and staged/current Live checks | Forbidden request cannot mutate plan; linking stages only Preview and cannot change current Live | Hosted real TLS/controller controls | PENDING |
| C-004 | yes | Regression tests detect removal of canonicalization and preservation regressions | Meaningful hosted scoped mutants with all sibling cases and exact restoration | Named actual behavioral failures for intended mutants; all baseline/restored controls pass; guarded source/tests/dependencies byte-identical | Diagnostic exact-parent/source mapping/raw/hashes | PENDING |
| C-005 | yes | Normal affected gates and scoped source pass | Hosted full affected normal Rust workflow, full diffcheck/target/prefix/component proof | Required jobs PASS; only controller/focused tests/Goal, no product workflow/dependency/parser changes; skips explicit | Exact SHA/tree/normal logs/review-dispatch | PENDING |
| C-006 | yes | Independent review and delivery close | Root Cody/Quinn/Vera/Shadow final reports, merge tree and exactQA receipt | All four Pass, actual merge and persistedQA verified | Root receipts and completed evidence export | PENDING |

## Verification plan

- Tests-first exercise actual production handler through existing public controller APIs and real loopback pinned TLS, using real paired roles/RemoteOperator and returned/host plan state rather than a copied normalizer.
- Preserve existing canonical byte test. New loose-range matrix plus canonical, whole-chapter/overflow fit/pin, explicit metadata/default absence, malformed unchanged, unresolved missing, permission and neverLive positives.
- After actual behavioral RED, minimal Reference Display assignment in set_item_content only; no new parser or fit semantics.
- Meaningful mutation removal of canonicalization, loss of fit/pin or policy preservation guards must be caught with positive siblings. Restore identical tracked source/tests/Cargo dependencies; no temporary workflow in product PR.
- Normal configured affected Linux Rust gates mandatory; exact jobs/skips/ignored/native limits recorded. Root all four current-source reviews and QA required.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-005
- Hypothesis: the existing handler validates a loose range but persists its raw spelling; real command entry-point tests can reproduce this without source changes.
- Change or investigation: read complete frozen task/comments and qualification, canonical/parser/fit helpers, existing test controls and current guidance. Fetch actualmain400bbb52 and create own managed checkout;100-registration error retained, no duplicate. Create bounded Goal before code edits.
- Verifier executed: source inspection and structural Goal validator; hosted behavior pending.
- Result: preparation only, all runtime/delivery criteria pending.
- New evidence: fitted_scripture_reference deliberately leaves fit-free passages alone, so fix belongs only in set_item_content after parse; shared load-time helper need not change.
- Decision: add meaningful tests-only host/realTLS cases and freeze draftPR for actual RED; no local runtime.

### Iteration 2

- Target criterion: C-001 through C-005
- Verifier executed: actual tests-first normal41175610073 at80345b41, full8 executed raw/hash archive mobile-qualification/17tnw2b13xz/red-attempt1. Format/compile/setup passed; focused13-case file repeatedly reports4 passed/9 failed. Six real direct/pinned-TLS loose-reference mismatches prove the storage defect. Three preservation checks fail only because live_generation increments by1, after earlier plan/metadata/denial assertions succeeded.
- New evidence: controller field/method docs explicitly define live_generation as a safe over-approximation; apply increments it before dispatch for potentially mutating commands, even when later denied. It does not imply actual audience pixels changed. My generation-equality oracle was invalid; no production fix is warranted for those counts.
- Change: tests only replace counter equality with full actual audience RGBA dimensions/bytes, Live Slide and index snapshots. Keep all prior canonical/plan/dirty/permission/metadata assertions. Add actual GoLive positive control to the existing canonical case to prove the snapshot detects real output change. All13 named cases retained; production still identical to400bbb52.
- Hypothesis: a bounded focused hosted run now yields exactly six genuine canonicalization failures and all seven preservation controls pass against unchanged production.
- Result: static correction prepared; actual corrected RED pending. No broad blind normal rerun or source edit.
- Decision: publish separate exact-parent workflow-only focused diagnostic, preserving failed9-case history, before minimal canonical storage fix. Parent/root owns tracker catch-up and review/mergeQA.

### Iteration 3

- Target criterion: C-001 through C-005
- Verifier executed: bounded corrected tests-only diagnostic41177482383 SUCCESS at workflow-only386a84a9, exact first parente6082726. The actual Cargo invocation exits101 with exactly six typed-versus-canonical mismatches and all seven preservation positives passing,13 named cases total; all nine guarded source/test/dependency hashes unchanged. Full raw/metadata/SHA256, actual six assertion blocks and file/component audits archived in mobile-qualification/17tnw2b13xz/corrected-red-ci. This is qualified behavioral RED, not a normal GREEN.
- Positive evidence: canonical bytes/metadata/default absence, fit/pin, malformed full-plan retention/dirty, parseable missing, sanitize-first, canonical TLS and forbidden/malformed wire/no-Live controls all pass against original production. Actual GoLive changes pixel bytes in the audience-oracle positive; generation counters are no longer used as output equality.
- Hypothesis: retain the successfully parsed Reference and use its existing Display only when the existing chapter-fit path does not rewrite the reference.
- Change: minimal set_item_content let-Ok parse and canonical else assignment, with precise related comments. Existing fitting/translation pinning, sanitized validation, malformed denial, missing acceptance/status, permissions, transport/errors and load-time legacy helpers untouched. All corrected test assertions remain intact.
- Result: candidate prepared; fresh target integration, full normal Rust and meaningful hosted mutants/restoration pending. No local project runtime.
- Decision: ordinarily integrate fresh actual main before publication, freeze the single PR310 candidate and separate exact-parent diagnostic; root owns all4 reviews/mergeQA. No next unit.

### Iteration 4

- Target criterion: C-004 and C-005
- Verifier executed: exact-source normal41178023431 at4e76a71f FAILED only the original operator DEFAULT Test: autolaunch.rs233 stand-in-sidecar spawn assertion,435 passed/1 failed/1 ignored. All other seven selected jobs and the other three operator feature phases passed. Full raw/metadata/hash/classification preserved in W3 mobile-qualification/17tnw2b13xz/normal-attempt1.
- Sensitivity result: separate exact-parent workflow-only run41178278280 SUCCESS. All four canonical-storage/fit/pin/neverLive mutants fail the intended named assertions with every unaffected sibling passing; all13 baseline/restored cases pass and all nine tracked source/test/Cargo identities restore exactly. Actual receipt/raw in mutation-attempt1.
- New evidence: autolaunch None precedes endpoint waiting and can reflect absent sidecar or the original suppressed spawn error. Actual original cause/errno UNKNOWN; no canonicalization failure or attributed source regression is claimed.
- Decision: keep failed normal intact and freeze product source. A separately authorized bounded observation-only diagnostic may investigate the original boundary; sensitivity success is no normal waiver.

### Iteration 5

- Target criterion: C-005
- Verifier executed: one separate workflow-only diagnostic41185328467 at4d089f18, exact firstparent4e76. It preserves the original full operator job/default parallelism/assertions/lifetimes/30-minute cap in current4e76 and baseline3bb contexts. Each context then executes16 full DEFAULT plus16 focused DEFAULT spawn suites within the finite five-minute trial phase.
- Actual result: all original Format/Check/four Clippy+Test phases/Chrome/WebKit passed in both contexts. All64 requested trials completed successfully. Original phase counts per context are436/449/440/453 passed with0failed/1ignored. Trial summaries are436passed/0failed/1ignored for full suites and4passed/0failed for focused suites.
- Classification: zero spawn-error/FD markers; the32 captured absent-sidecar markers per context belong only to the two intentional absent-sidecar controls. None is evidence for the originally failing stale-endpoint test. Original cause/errno remain UNKNOWN. Immutable source-start/component identities and observed instrumentation hashes verified in autolaunch-diagnostic-ci/author-classification.json; successful harness output capture and post-error/non-atomic observer limits remain explicit.
- Decision: STOP diagnostics. No autolaunch production fix, flake label, causality claim or normal waiver. Original normal41178023431 remains FAILURE. Hosted diagnostics do not establish normal acceptance.

### Iteration 6

- Target criterion: C-005 and current-source review readiness
- Change: ordinarily integrate verified actual main93bf472f65a1846117eecf09b1972c4118dc0cd4 (AYETE selector and AWR operator-row work). These target changes do not modify this controller fix, focused tests, parser, LAN, dependencies or autolaunch source. Update this Goal ledger with actual historical results; no application fix is inferred from target integration.
- Verifier: full source/target patch and expected-prefix object proof, component mapping back to the four verified mutants, structural Goal validator and full diffcheck. One fresh normal full affected CI is required on the resulting revision; no blind rerun of the old failed head or more spawn diagnostics.
- Result: current candidate preparation; new normal and all four current-source independent reviews remain pending. C-006/root merge and persistedQA remain pending; no completion claim.
- Decision: freeze the clean candidate, publish the updated ordinary branch and yield an immutable CI checkpoint. If required work remains at max8, report the remaining predicate for root replan rather than silently extend.

## Risks and rollback

- Risks: changing fit/pin order, silently rejecting unresolved passages, permission mutation, legacy load changes or accidentally updating Live while re-staging Preview.
- Rollback or recovery: revert only this scoped controller assignment/tests/Goal. No migration/protocol/persistence format change.

## Pause and escalation conditions

- Stop for product semantics beyond explicit canonicalization, unexpected parser/legacy policy ambiguity or conflicting controller ownership; root coordinates.
- Do not count setup failure as behaviorRED, waive failed normal gates, silently extend max8 or start DQ0. Yield immutable hosted waits.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b13xz-scripture-link-canonical.md
- Validator result: initial structural PASS before test edits
- Independent verification result: pending root
- Terminal state: pending
- Remaining failed or blocked criteria: C-001 through C-006
- ClickUp final evidence comment: root owns publication; start/status pending unlock
