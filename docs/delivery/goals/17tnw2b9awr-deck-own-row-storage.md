# Goal Contract — TASK-17tnw2b9awr

## Identity

- Goal ID: TASK-17tnw2b9awr
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Preserve a deck's own database row through ordinary leave/store and relaunch
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9awr
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A loaded deck writes only its own persisted row even when the stored JSON name differs from its key; the actual ordinary leave/open route and edit/store/relaunch preserve both presentations and never rewrite an untouched sibling.

## Baseline

Actual main3bbdd4b5970958e11b56db2206630afb6cf69776 includes reviewed DNV. Library loads separate row_keys then heals JSON names; UID backfill skips mismatched rows but ordinary store persists by in-memory name. Actual deck_open closure stores the outgoing workspace before loading target; startup chooses first library.list entry. Given Alpha(old1slide namedZed)/realZed3, this can overwrite realZed during leave. Full frozen task0comments/no declared dependencies; ADR0031 remains Proposed with explicit knownlimit7 and re-mint exceptions. Root verified prerequisite222; tracker live refresh/start and prior QA exports remain pending access.

## Inputs and evidence sources

- Full api-qualification/17tnw2b9awr.json with whole AC/comments/deps/links, qualifications.md rank6, selected20 and AGENT-RUNBOOK.md.
- Current deck_library load/heal/store/rename/delete/restore/writers; main deck_open/startup and shared DeckWorkspace; SQLite deck_repo numbered writers and triggers.
- ADR0031 decisions5/6/knownlimit7 and all remaining limits; current root/desktop guidance, existing identity/number/readonly/corrupt-store tests.

## Scope

### In scope

- Make row keys authoritative for loaded names and preserve own-row destination when other existing heal rules require a display name change; ordinary save/delete/explicit atomic rename cannot target a sibling.
- Real SQLite Alpha1/Zed3 load→actual shared leave/open→relaunch and distinct same-JSON-name edit/store/relaunch, untouched-row bytes and trigger-observed writes.
- Mechanical exact-body extraction to deck_open_in, reserved by root before Farah13Y0, so tests drive production route without GUI. Preserve wrapper lock/error/control order and all DNU cloud blocks.
- Targeted blank/case/space/corrupt/readonly/healthy/already-open positives; meaningful own-row/store-route mutants/exact restoration; precise ADR5/6/limit7 update without changing Proposed status.

### Non-goals

- No controller/LAN/mobile/driver/UI/plan-wire/uid trust policy, historical number/link redesign, single-instance guard, broad cleanup, held185/233 decisions or other selected unit.
- No deployment or GUI automation; tests exercise shared production domain path, not a claim of Tauri/browser end-to-end interaction.

### Constraints

- Owned isolated codex branch; not alone, preserve others. main.rs reservation only mechanical deck_open_in extraction/delegation/test path. Controller.rs remains Mika13XZ-only and must not be edited.
- Actual hosted tests-first behavioral RED before heal/storage fix; extraction must preserve exact old closure body and prove identity. No skipped/compile/setup failures called RED.
- Preserve stored slide/content/history, UIDs/numbers/held-back/read-only/live/permission/other heal invariants. Any old backfill test whose deliberate no-repair expectation changes must retain whole-content/no-other-row/count assertions with exact task traceability.
- No local project runtime/import/build/install/tests/container/benchmark. Hosted existing pinned operator setup and compact exact-parent diagnostic refs; static source/Git/stdlib/formatter/goal checks only locally.
- Root owns tracker/fourreviews/publication/merge/QA; author ordinary push/draftPR/body-file/immediate attachment permitted, existing100attachment cap explicit.

### Assumptions and unknowns

- UNKNOWN actual shared leave route RED until hosted real database tests; direct store-only inference is insufficient.
- SQLite permits blank/exact case/space keys. Existing display-name/held-back heal may still change a key-derived name; safe own-row binding must handle these without inventing new naming policy or disabling saves.

## Dependencies and approvals

- User selected20 and root dispatch authorize this unchanged task. DNV actual merge3bb verified; QA/export pending root receipt, not complete yet.
- Root reserved main.rs for exact deck_open helper until this merge, Farah13Y0 waits. Controller.rs remains reserved and no edit is expected.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Actual shared ordinary leave reproduces own-row overwrite before fix | Hosted SQLite load/startup/shared deck_open_in/store/relaunch with independent snapshots/triggers | Alpha1/Zed3 defect genuinely RED with actual leave witness and healthy controls, no setup/oracle substitution | deck-own-row-storage/red metadata/raw/classification and extraction identity proof | PENDING |
| C-002 | yes | Every later write stays on its own row after name/key mismatch | Real ordinary leave/edit/store/relaunch and blank/case/space rename/delete/restore cases with byte/SQL-write evidence | Both presentations/content survive, distinct rows/names/ids/UIDs retained, no untouched-row update | Hosted focused GREEN and meaningful mutants/exact restoration | PENDING |
| C-003 | yes | Existing storage/heal/number/live/permission invariants and ADR remain accurate | Existing identity/number/readonly/corrupt/healthy tests, source/component comparison and ADR5/6/limit7 review | Existing legitimate assertions pass or precisely task-superseded own-row repair expectations preserve stronger content/no-collateral checks; Proposed status/unrelated limits unchanged | Full operator/identity/number raw and static review evidence | PENDING |
| C-004 | yes | Final normal affected gates pass at exact source | Normal pinned Linux Rust/operator/default/devkeys/openainotes/RELEASE/native/audit gates plus scoped sensitivity/restoration | All required current-source gates pass; skips/ignores/other platforms explicit, no waiver | Current normal/supplemental metadata/raw receipts | PENDING |
| C-005 | yes | Four final independent reviews and actual merged tree/QA verified | Root Cody/Quinn/Vera/Shadow receipts, expected/actual merge tree and exact linked-ticket qa readback | No unresolved finding, approved tree merged, ticket qa persisted | Root review/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: real temporary SQLite rows, distinct rich slides/UIDs/numbers, SQL triggers recording touched row keys and exact JSON snapshots; shared production leave/open helper with startup choice and legitimate controls.
- Broader regression verification: full normal operator/Rust/default/features/RELEASE/native gates and bounded own-row/store-route sensitivity/exact restoration.
- Independent verifier: Cody, Quinn, Vera and Shadow coordinated by root.
- Required environment: hosted pinned Linux/operator setup only for runtime; local source/Git/stdlib/static/goal tools.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: JSON-name authority and name-keyed ordinary store let a startup-loaded stale deck overwrite a sibling, while backfill's skip guard protects load only.
- Change or investigation: full task/ADR/current load/store/writer/startup path read; managed checkout actual3bb exists despite100registration cap, path reused. Root reserved main.rs exact helper extraction before Farah13Y0; no controller changes. Inventory found blank/held-back healed-name cases needing own-row binding as well as valid-key canonical names.
- Verifier executed: source/Git/guidance and structural child validation before tests/code.
- Result: scope ready; actual RED and final criteria pending, no product fix.
- New evidence: authoritative frozen task/qualification/ADR/runbook and this contract.
- Decision: iterate

## Risks and rollback

- Risks: load repair writes sibling rows, corrupted/unreadable rows shift bindings, healed ids mismatch keys, names/UIDs/numbers/history rewritten, failed rename drops destination binding, vacuous no-op save and inferred helper-only route.
- Rollback or recovery: one scoped reviewed PR; real snapshots/SQL triggers, unchanged helper-body proof, controlled mutants and exact restoration; no production database mutation/deployment.

## Pause and escalation conditions

- Stop for owner/new product policy, required controller/shared-file changes without coordination, destructive/production actions or bounded no-progress limit. Preserve all actual failed/unexecuted gates; yield hosted checkpoints. No other unit without root dispatch.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9awr-deck-own-row-storage.md
- Validator result: PASS structural verification before substantive tests
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-005 pending
- ClickUp final evidence comment: root-owned pending access
