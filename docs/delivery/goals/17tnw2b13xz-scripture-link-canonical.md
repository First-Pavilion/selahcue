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
