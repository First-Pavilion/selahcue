# Goal Contract — GOAL-plan-content-reference

## Identity

- Goal ID: GOAL-plan-content-reference
- Parent goal ID: 86ajp072p (EPIC — Service Planning & Library)
- Title: Add a content reference to PlanItem (scripture ref / deck_id / media_id) end-to-end — model, wire, controller resolution, persistence, missing-content detection — keeping the cross-language contract and make ci green
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxxuye
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 16
- Independent verification required: yes

## Objective

A `PlanItem` can carry a typed content reference — a Scripture passage (reference string + translation + verses-per-slide), a Presentation `deck_id`, or a `media_id` — that persists, round-trips on the LAN wire (byte-compatible, additive), resolves live in the controller (a linked Scripture item renders its verses; a linked deck item is identifiable), and is surfaced as linked/unlinked/missing, with missing-content detection at plan-open. This unblocks the Service Plan linking design (`docs/design/SERVICE-PLAN-2.0-HANDOFF.md`).

## Baseline

- `PlanItem { id, kind, title, planned_secs, owner, stanzas, theme }` — no content reference (`selahcue-core/src/plan.rs`). Scripture items are title-only slides; deck items have no deck link (verified).
- Wire uses additive `#[serde(default, skip_serializing_if=...)]` fields; JSON fixtures are pinned byte-for-byte cross-language (`selahcue-lan/tests/test_protocol.rs` ↔ mobile `protocol_test.dart`) — must change both sides together (CLAUDE.md).
- Types available: scripture `Reference`/`VerseRange` (core), `DeckId(u64)` (present), media (core `media.rs`).
- `make ci` is the gate: fmt --check, clippy -D warnings, all crate/feature test suites, operator check, headless webview, flutter analyze+test.

## Inputs and evidence sources

- ClickUp 86ajxxuye + design SERVICE-PLAN-2.0-HANDOFF.md §1/§4 (linking model + flag).
- Code: selahcue-core/src/{plan.rs,scripture.rs,media.rs}; selahcue-lan/src/protocol.rs + tests/test_protocol.rs; selahcue-app/src/controller.rs; selahcue-data (plan persistence); selahcue-present/src/deck.rs; mobile selahcue_controller (Dart model + fixtures).
- Scout report (this session) mapping exact change sites + current pinned fixtures.
- ADR-0020; FR-002, FR-007, FR-026, FR-029.

## Scope

### In scope

- Additive `content` reference on `PlanItem` (model) covering scripture / deck / media, with all construction/persistence sites updated.
- Additive wire fields on `AddItem` + `PlanItemView` (and `OperatorStateView` if needed), byte-compatible; Dart model + fixtures updated on BOTH sides.
- Controller: resolve a linked Scripture item to its verses (reuse `scripture_slide_in`); expose deck/media link + link status; missing-content detection at plan-open (FR-007).
- Persistence: save/load the content reference (forward-only migration if the schema needs it).
- Tests for model, wire round-trip/stability, controller resolution, and missing detection, reusing existing fixture patterns.

### Non-goals

- Frontend/operator-webview build (separate task 86ajxxuz9).
- Reconciling the `PresentAuthoredSlide` takeover path beyond making deck-linked items identifiable (note/flag if larger).
- Redesigning scripture pagination (FR-029 verses-per-slide is stored + honoured where the resolver already paginates; deeper pagination is a separate slice per controller.rs note).

### Constraints

- Preserve wire compatibility: existing pinned fixtures stay byte-identical (new fields skip-if-none/default); any fixture change is mirrored in Rust + Dart together.
- Domain purity: `selahcue-core` stays I/O-free; the parser/model never panics on untrusted input.
- Bounded memory: no unbounded growth; `MAX_PLAN_ITEMS` and existing caps preserved.
- clippy -D warnings clean; `unwrap_used = warn` in core.

### Assumptions and unknowns

- ASSUMED: an additive `content: Option<ItemContent>` enum (scripture/deck/media) is the cleanest model shape; confirmed against construction sites by the scout.
- UNKNOWN: exact persistence schema for plan items (scout resolves) — a migration may be required.

## Dependencies and approvals

- Cross-language fixture parity (Rust ↔ Dart) — must be committed together.
- Independent review — owner: code-reviewer/qa (or /security-reviewer for the untrusted `AddItem` ingress). Status: pending.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `PlanItem` carries an additive content reference (scripture ref / deck_id / media_id); all construction + persistence sites updated; core stays pure | `cargo test -p selahcue-core` + review | builds; new + existing plan tests pass | test output | PASS |
| C-002 | yes | Wire is additive + byte-compatible: existing pinned fixtures unchanged; new optional fields on AddItem/PlanItemView; Dart model + fixtures updated on both sides | `cargo test -p selahcue-lan --features server` + `flutter test` (protocol_test) + review of fixtures | `wire_fixtures_are_stable_for_cross_language_clients` passes; Dart protocol tests pass | test output | PASS |
| C-003 | yes | The controller resolves a linked Scripture plan item to its verses (not title-only) and exposes deck/media link + link status | `cargo test -p selahcue-app --features server` (+ new resolution test) | a linked scripture item stages its passage; test asserts it | test output | PASS |
| C-004 | yes | Missing-content detection flags a plan item whose linked deck/media is absent (FR-007) | new unit/integration test | a plan with a dangling link reports the item as missing | test output | PASS |
| C-005 | yes | Persistence round-trips the content reference (save→load equal), migration forward-only if needed | `cargo test -p selahcue-data` (+ new round-trip test) | a plan with linked items survives save/load | test output | PASS |
| C-006 | yes | `make ci` is green | `make ci` | exit 0, all gates pass | terminal output | PASS |
| C-007 | yes | No compatibility break hidden: any wire/schema change is documented + mirrored; ADR/handoff note updated | review + git diff | change is additive + documented | diff + handoff note | PASS |
| C-008 | yes | ClickUp 86ajxxuye carries goal ID, engine, iteration evidence, commits, terminal state | inspect task comments | start + evidence comments present | ClickUp 86ajxxuye | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate `cargo test` for the layer being changed; the cross-language fixture test; a new resolution test + a missing-detection test.
- Broader regression: full `make ci` (Rust fmt/clippy/all suites + mobile analyze/test + operator checks).
- Independent verifier: code-reviewer/security-reviewer for the untrusted `AddItem` ingress + wire compat; not self-certified (C-006/C-007).
- Required environment: `implementation/desktop` workspace + Flutter for mobile tests.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-008)
- Hypothesis: a scout map of exact change sites + fixtures is a prerequisite to a surgical, compat-safe change.
- Change or investigation: read plan.rs/scripture.rs/protocol.rs; dispatched a scout to map all construction sites, fixtures, controller resolution, media identity, ci gates; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py (pending)
- Result: pending
- New evidence: task 86ajxxuye
- Decision: iterate

### Iteration 2 — implement all layers

- Target criteria: C-001..C-006
- Change: added `ItemContent` + `PlanItem.content` + pure codec + `set_item_content` + `unresolved_content` (core); v18 `content_ref` migration + repo save/load (data); additive `ContentLinkView` on `PlanItemView` + `SetItemContent` command (EditPlan RBAC) + both `From` impls (lan/app); `item_slide` resolves a linked scripture to its verses + `operator_view.link` + the command handler (app). New tests at every layer.
- Verifier executed: `cargo test` per crate (core 18, data 17+10 test_db, lan 32, app resolution test); clippy `-D warnings` (workspace + server features); fmt.
- Result: all green; existing cross-language fixtures byte-identical; wire `VERSION` unchanged (additive).
- New evidence: test outputs; git diff.
- Decision: iterate (full ci)

### Iteration 3 — make ci + an incidental cross-commit fix

- Target criterion: C-006
- Change: fixed the v18 migration re-run in the pre-vN upgrade tests (bump pin 17→18 + drop `content_ref` before reset). Also fixed ONE pre-existing failure unrelated to this task: a brittle `APP_SURFACES` adjacency needle in `selahcue-present/tests/test_tokens.rs` that a concurrent owner commit (`4585683`, Pre-service Check surface, task 86ajp0az9) broke by inserting `"preservice"` between `"console"` and `"presentation"`; the presentation surface is still registered, so the needle was made insertion-robust (`"presentation", "theme-designer"`). Documented as incidental, not scope creep.
- Verifier executed: `make ci` (captured exit code).
- Result: **MAKE_CI_EXIT=0 · "== local CI gate: ALL GREEN =="** (fmt, clippy -D warnings, all Rust suites incl. feature-gated, operator check, headless webview, flutter analyze+test).
- New evidence: makeci3.log.
- Decision: complete (implementation predicate met; independent review is the next gate)

## Risks and rollback

- Risks: (1) breaking a byte-pinned cross-language fixture; mitigate with additive skip-if-none fields + mirror Dart. (2) persistence migration on live data; mitigate forward-only + round-trip test. (3) clippy -D warnings on new code. (4) scope creep into the frontend/takeover path; mitigate with follow-ups.
- Rollback: additive fields default to None; revert is a clean field removal; git history preserved (no shared-history rewrite).

## Pause and escalation conditions

- Escalate to architect if the content-reference model needs an ADR (new persisted shape) beyond additive fields.
- BLOCKED if Flutter/mobile toolchain is unavailable for the cross-language test.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-plan-content-reference.md --require-complete
- Validator result: PASS (all mandatory criteria PASS)
- Independent verification result: PENDING — implementation predicate met (make ci green); moving to code review for independent review of the untrusted `SetItemContent`/`AddItem` ingress + wire compat (not self-certified).
- Terminal state: VERIFIED_COMPLETE (implementation) → code review gate
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to task 86ajxxuye
