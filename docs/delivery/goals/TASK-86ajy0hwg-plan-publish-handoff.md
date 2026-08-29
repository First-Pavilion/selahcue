# Goal Contract — TASK-86ajy0hwg

## Identity

- Goal ID: TASK-86ajy0hwg
- Parent goal ID: NONE
- Title: A coordinator can publish the service plan to the live operator view, and a client can render the change badge, the view-only state, and the four empty-state actions from host-authoritative state
- Role: backend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: NONE — ClickUp MCP was not reachable this session (no ClickUp tools registered at all, not a transient failure). Ticket id `86ajy0hwg` is taken from repository evidence only; see "Inputs".
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The host reports enough publish / hand-off state for the Service Plan surface to render FR-006 without inventing anything, and accepts the five commands that surface needs — with no path through them that can change the live audience output.

## Baseline

Verified at `3b39fb5` (`origin/main`, PR #13 merged) by direct inspection, re-checking the four premises recorded on the ticket:

- No `role` or `can_edit` on `OperatorView` (`selahcue-app/src/operator.rs:63`) or `OperatorStateView` (`selahcue-lan/src/protocol.rs:706`); the last field was `summary`.
- No `Publish`, `TemplatePlan`, `DuplicatePlan`, `ImportPlan` or `RestoreAutosave` in `protocol.rs`. The only `Publish` hits in the tree were two unrelated "Publish health" comments in `selahcue-desktop/src/main.rs`.
- No `changed`, `version` or `published` flag on either view.
- `ServicePlan::duplicate()` (`selahcue-core/src/plan.rs:927`) had no wire caller; the `.duplicate(` hits were the deck library's and `plan_repo`'s.

All four premises held. Repository evidence places this at FR-006 (`docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md:75`, "Coordinator→operator handoff never built").

## Inputs and evidence sources

- `docs/product/prds/SelahCue-PRD.md:107` — FR-006 acceptance criterion.
- `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md:75` and `:96` — the gap rows for FR-006 and FR-005.
- `docs/design/SERVICE-PLAN-2.0-HANDOFF.md` §2/§5/§8 — the frame table (frames 5, 8, 13, 14, 15, 16, 17), the state table, and the builder→console publish description at `:105`.
- `docs/design/UX-STATE-MATRIX.md` §4 — the empty-state action list (`:108`) and the view-only rule (`:111`, "hidden, not just greyed").
- `docs/design/UX-FLOWS.md` Flow 1 — "Publish to team", change badge, duplicate/template branches.
- `docs/design/COMPONENT-SPECS.md:150`, `:169`, `:190` — the `v4 (published)` label and `draft → validated → published`.
- `selahcue-operator/dist/app.js:7452-7461` — the existing SEAM comment naming `86ajy0hwg` as the missing backend and `86ak8467m` as the consumer.

## Scope

### In scope

- Five LAN commands: `publish_plan`, `new_plan`, `template_plan`, `duplicate_plan`, `import_plan`.
- Three `OperatorStateView` fields: `viewer`, `publish`, `plan_templates`, plus their `OperatorView` counterparts.
- The RBAC mapping for the five commands, and a host-computed `can_edit` verdict.
- A starter-template mechanism the host reports rather than the client transcribing.

### Non-goals

- Autosave restore and per-item Undo (frames 13 and 16) — `86ajy0hxg`.
- The Service Plan frontend itself — `86ak8467m`.
- Persisting publish state across a restart (needs a `session_repo` migration).
- A saved-plan LIBRARY over the wire, which "Duplicate previous" needs.
- FR-139's portable plan bundle.

### Constraints

- The LAN wire is byte-pinned cross-language; new view fields must be skip-if-none/empty and appended last.
- RBAC must go through the single `authorize()` choke point.
- Staging never changes Live; only Go Live does.
- NFR-024: no component failure may blank live output.
- Bounded memory, with tests that bite.

### Assumptions and unknowns

- ASSUMED: publish is a host-local builder→console hand-off, per `SERVICE-PLAN-2.0-HANDOFF.md:105`. The shipped button reads "Publish to team", which reads as network-backed. UNKNOWN and owned by the Product Manager; no ticket exists.
- UNKNOWN: what `validated` means in `draft → validated → published`. No document defines its predicate, so only draft/published are modelled.
- ASSUMED: the starter-template CONTENT is provisional. The set is a product decision; no document specifies it.

## Dependencies and approvals

- ClickUp MCP — UNAVAILABLE. No shadow backlog created; the pending update is in the handoff report.
- GitHub Actions minutes — EXHAUSTED. CI cannot run on PR #14; local gates are the only evidence.
- Four-reviewer pipeline (Cody, Sana, Vera, Quinn) — dispatched at `02a8095`.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The five commands exist on the wire with pinned names and field names | `cargo test -p selahcue-lan --test test_protocol` | exit 0; `plan_publish_and_lifecycle_commands_have_a_pinned_wire_shape` passes | 29 passed / 0 failed | PASS |
| C-002 | yes | The new view fields are additive — the cross-language byte pin is unchanged | `cargo test -p selahcue-lan --test test_protocol` | `wire_fixtures_are_stable_for_cross_language_clients` passes with all three fields present in the struct | 29 passed / 0 failed | PASS |
| C-003 | yes | All five commands are gated by the existing `EditPlan` permission and denied below Operator | `cargo test -p selahcue-lan --test test_rbac` | `plan_publish_and_lifecycle_commands_are_operator_only_plan_editing` passes | 20 passed / 0 failed | PASS |
| C-004 | yes | `can_edit` agrees with the choke point for every plan-edit command, for every role | `cargo test -p selahcue-lan --test test_rbac` | `can_edit_plan_agrees_with_the_choke_point_for_every_plan_edit_command` passes; mutation M3 turns it RED | 20 passed / 0 failed; M3 RED | PASS |
| C-005 | yes | Publishing does not change one pixel of the live output, nor the live index | `cargo test -p selahcue-app --features server --test test_publish` | `publishing_never_changes_the_live_output` passes with its positive control | 17 passed / 0 failed | PASS |
| C-006 | yes | No plan-replacing command blanks Live; the on-air slide is carried over and no plan row is reported LIVE | same | `every_plan_replacement_keeps_the_live_slide_on_air` passes for all four commands; mutations M4 and M5 turn it RED | 17 passed / 0 failed; M4, M5 RED | PASS |
| C-007 | yes | The change badge reports difference from the published document, not merely that it was touched | same | `undoing_back_to_the_published_plan_clears_the_badge` passes; mutation M2 turns it RED | 17 passed / 0 failed; M2 RED | PASS |
| C-008 | yes | A never-published plan never shows a badge | same | `a_plan_that_was_never_published_reports_no_badge_and_no_version` passes with its positive control | 17 passed / 0 failed | PASS |
| C-009 | yes | Every lifecycle guard refuses an input only it rejects, leaving the plan untouched, and each has a working benign counterpart | same | both battery tests pass; mutations M7, M8, M11 turn the battery RED | 17 passed / 0 failed; M7, M8, M11 RED | PASS |
| C-010 | yes | Import is bounded by `MAX_PLAN_ITEMS`, asserted on the entity | same | `an_import_is_bounded_by_the_plan_item_cap` passes; mutation M6 turns it RED | 17 passed / 0 failed; M6 RED | PASS |
| C-011 | yes | The LAN handler stamps the authenticated role, and a view-only role is still refused the edit | same | both handler tests pass; mutation M9 turns the stamp test RED | 17 passed / 0 failed; M9 RED | PASS |
| C-012 | yes | No regression across the workspace | `cargo test --workspace --no-fail-fast` | exit 0 | 108 suites, 1174 passed, 0 failed | PASS |
| C-013 | yes | Feature-gated suites pass | `cargo test -p selahcue-lan/-app --features server`, `-p selahcue-data/-desktop --features encryption`, `-p selahcue-scripture --features download` | all exit 0 | exit codes captured directly, all 0 | PASS |
| C-014 | yes | The out-of-workspace operator crate still builds, lints and passes, and the headless webview gate is green | `cargo fmt --check` + `clippy -D warnings` + `cargo test` on its manifest; `python3 scripts/operator_headless.py` | all exit 0 | operator 66 passed; headless 963 checks, 0 FAIL | PASS |
| C-015 | yes | Formatting and lints are clean | `cargo fmt --check`; `cargo clippy --workspace --all-targets --features selahcue-app/server -- -D warnings` | exit 0 | both exit 0 | PASS |
| C-016 | yes | Import guards pass (no manifest edit was made, run as a precaution) | `sh scripts/import_guards.sh` | exit 0 | `== import guards: OK ==` | PASS |
| C-017 | yes | Every control claimed in a comment actually fails when the thing it names is removed | 11-mutation battery, siblings running, never `--exact` | every claimed control RED, or the claim corrected | 10/11 RED; M1 found subsumed and the claim corrected in `2908ffc` + `02a8095` | PASS |
| C-020 | yes | A replaced plan is a DRAFT and never inherits the discarded plan's publish state | `cargo test -p selahcue-app --features server --test test_publish` | `a_replaced_plan_is_a_draft_again_...` passes for all four commands | 22 passed / 0 failed; mutation M14 RED | PASS |
| C-021 | yes | Duplicating mid-service keeps the on-air row marked and navigable | same | `duplicating_mid_service_keeps_the_on_air_row_marked_and_navigable` passes | 22 passed / 0 failed; M15 RED | PASS |
| C-022 | yes | The badge clears when an edit is reversed by a second edit, not only by undo | same | `an_edit_that_is_reversed_by_a_second_edit_clears_the_badge` passes | 22 passed / 0 failed; M16 RED | PASS |
| C-023 | yes | Plan labels refuse Cc, Cf and Zl/Zp, and accept ordinary international text | `cargo test -p selahcue-core --test test_plan` | `a_plan_label_must_be_visible_bounded_and_single_line` passes | exit 0; M17 RED | PASS |
| C-024 | yes | `same_document` ignores the id counter and nothing else | same | `same_document_ignores_the_id_counter_and_nothing_else` passes | exit 0; M18 and M19 RED | PASS |
| C-025 | yes | The local Tauri console can invoke all five actions | `cargo test -p selahcue-app --features server --test test_publish` + `cargo check` on the operator manifest | `the_console_shell_can_reach_every_publish_and_lifecycle_action` passes; operator crate builds with the five Tauri bindings registered | 22 passed / 0 failed; operator check exit 0 | PASS |
| C-026 | yes | A new `ServicePlan` field cannot silently escape the change comparison | add a field, `cargo check -p selahcue-core` | compile error at `same_document` | `E0027: pattern does not mention field` at plan.rs:978, then reverted | PASS |
| C-027 | yes | The out-of-workspace operator crate compiles the five Tauri bindings from CLEAN, and they are registered | `rm -rf` its target dir, then `cargo check --all-targets`, `clippy -D warnings`, `cargo test` on its manifest | all exit 0; all five appear in `generate_handler!` | exit 0 (54s cold); 66 tests pass; five bindings confirmed registered | PASS |
| C-028 | yes | Plan labels accept scripts whose spelling needs ZWNJ/ZWJ, and still refuse direction controls and invisible-only names | `cargo test -p selahcue-core --test test_plan` | Persian, Urdu, Devanagari, Sinhala "ශ්‍රී", Malayalam and family emoji accepted; RLO/LRE/isolates/ZWSP/BOM/word-joiner and all-joiner names refused | exit 0; mutations M20-M22 RED | PASS |
| C-029 | yes | The codec preserves orthographic joiners in a stored label, and still strips direction controls | same | Persian and Sinhala labels round-trip byte-identically; an RLO is stripped | exit 0; M23 RED | PASS |
| C-030 | yes | A rejected import installs nothing, not even the rows before the bad one | `cargo test -p selahcue-app --features server --test test_publish` | the previous run sheet survives a valid/invalid/valid import | exit 0; M24 RED |PASS |
| C-031 | yes | Re-publishing moves the baseline to the new document | same | undo back to the FIRST published document reports `changed` | exit 0; M25 and M26 RED | PASS |
| C-032 | yes | Replacing the plan clears Preview and drops the navigation cursor | same | `staged_index` drops, Preview repaints, `Next` resumes at row 0 | exit 0; M27 and M28 RED | PASS |
| C-018 | yes | Independent review by Cody, Sana, Vera and Quinn with blocking findings remediated | four-reviewer pipeline on PR #14 | no outstanding blocking findings | dispatched at `02a8095` | PENDING |
| C-019 | no | CI green on the branch | GitHub Actions | all jobs pass | NOT RUNNABLE — Actions minutes exhausted; runs complete in 7-10s with zero steps | NOT_APPLICABLE |

## Accepted risk — CI could not run at all

**GitHub Actions minutes are exhausted**, so no job ran on PR #14; runs complete in seconds with zero steps. The following are therefore **unverified for this change and accepted as risk**, not merely "not run locally". Recorded here because ClickUp MCP is unreachable and this is the only durable place for it:

| Uncovered job | Why it matters here | Residual risk |
|---|---|---|
| ubuntu + Windows matrix (`rust`, `operator`) | Verified on macOS only. New code is pure Rust with no path, filesystem or line-ending handling, so exposure is low | Low |
| Playwright **WebKit** smoke | The Blink gate ran (963 checks, 0 FAIL); no WebView-only break can be seen | Low — no `dist/` change in this branch |
| `cargo audit` / `cargo deny` | No dependency was added or changed by this branch | Low |
| `launch-smoke` | The operator crate compiles cold and its bindings are registered, but the app was never launched | Medium for the console seam |
| `make nfr` | Performance review measured the changed paths directly and judged NFR observation unnecessary | Low, by reviewer agreement |
| Flutter `analyze` + `test` | Deliberately skipped: concurrent runs produce false reds and one `make ci` was live in the shared checkout. No Dart file changed, and the cross-language byte pin passes unchanged | Low |

## Verification plan

- Focused verification: `cargo test -p selahcue-app --features server --test test_publish`, `-p selahcue-lan --test test_rbac`, `-p selahcue-lan --test test_protocol`.
- Broader regression verification: workspace tests, the four feature-gated suites, the out-of-workspace operator crate, `operator_headless.py`, `import_guards.sh`, fmt and clippy.
- Independent verifier: Cody, Sana, Vera, Quinn on PR #14.
- Required environment: macOS (darwin/arm64), toolchain pinned by `rust-toolchain.toml`, private `CARGO_TARGET_DIR` outside the shared checkout.

**Not covered locally, and stated rather than implied:** the ubuntu and Windows CI matrix, the Playwright WebKit engine smoke, `cargo audit` and `cargo deny`, `launch-smoke`, `make nfr`, and the Flutter analyze/test gate. The Flutter gate was deliberately skipped — the repository records that concurrent runs produce false reds and one `make ci` was running in the shared checkout — and no Dart file was changed.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-011 (the whole surface).
- Hypothesis: the surface can be delivered additively, without a new `Permission` and without touching the live-output path.
- Change or investigation: five commands, three view fields, the starter-template registry in core, the publish state in `LiveController`, the handler stamp.
- Verifier executed: per-crate builds, then the focused suites.
- Result: all green; the pre-existing cross-language byte pin unchanged, which is C-002's evidence.
- New evidence: `selahcue-app` cannot reach `selahcue-data`, and the desktop host persists exactly ONE plan row — so a saved-plan library, which "Duplicate previous" needs, is not reachable without a layering change.
- Decision: iterate.

### Iteration 2

- Target criterion: C-007.
- Hypothesis: a revision counter is sufficient for the change badge.
- Change or investigation: rejected on inspection. A counter cannot distinguish "edited" from "edited and undone", so it would leave a "Review changes" badge over a plan identical to the published one. Replaced with an exact comparison against a published document clone, recomputed only when the document moves so no deep compare enters the per-frame view path.
- Verifier executed: `cargo test -p selahcue-app --features server`.
- Result: green.
- New evidence: the cost is one plan-sized clone against the 60 `plan_undo` already holds.
- Decision: iterate.

### Iteration 3

- Target criterion: C-017.
- Hypothesis: every control named in a comment fails when its target is removed.
- Change or investigation: 11-mutation battery with siblings running.
- Verifier executed: `scratchpad/mutate.py`, twice, reproducing identically.
- Result: 10 RED. **M1 SURVIVED** — adding `Command::PublishPlan` to `is_plan_edit` left the entire `selahcue-app` suite green.
- New evidence: the exclusion is SUBSUMED — the block consuming that predicate also requires `self.plan != before`, and publishing changes no item, so no input exists that only the exclusion rejects. It is worth keeping (it saves a plan-sized clone per publish) but it is not what holds the badge down; the document comparison is. The comment claiming otherwise was false and was corrected in both the source and the test rather than a test being manufactured to fit it.
- Decision: handoff.

### Iteration 4

- Target criterion: C-018 (independent review), which failed on its first pass.
- Hypothesis: the surface was complete. It was not.
- Change or investigation: performance review returned Pass and corrected a premise I had assumed rather than checked — `operator_view()` is NOT the per-frame path. Security review returned Pass with one low advisory. **Code review returned changes-requested with one blocking and two high findings.**
- Verifier executed: the focused suites plus a six-mutation battery on the remediation.
- Result: all green; six new mutations RED.
- New evidence, and the part worth carrying forward:
  - **B1**: every plan replacement left the discarded plan's publish baseline in place, so a brand-new plan reported itself as published with changes to review.
  - **H3**: `duplicate_plan` un-marked the on-air row mid-service and reset `live_slide`, so `Next` stopped advancing the song the audience was hearing. **My own test asserted this as correct** — the shared four-command loop pinned it in place. This is the "test that vouches for a bug" failure mode, not a vacuous test, and it is the second time on this branch that a test or comment asserted something untrue.
  - **L9**: the Tauri console could not reach any of the five actions. The wire and controller were complete while the seam was missing, so the backend would have reported itself finished while the frontend it exists to unblock stayed blocked.
  - Six doc comments across the branch asserted things the code does not do. All corrected.
- Decision: iterate, then handoff for re-review.

## Risks and rollback

- Risks: publish state is not persisted, so a restart silently returns the plan to "draft". It can only fail to show a badge, never show a false one. The starter-template contents are provisional and may not survive product review. `duplicate_plan` copies the loaded plan, which is not what the empty-state frame's "Duplicate previous" means.
- Rollback or recovery: the change is purely additive on the wire — every new field is skip-if-none/empty and every new command is a new variant, so reverting the branch restores the prior behaviour exactly and no persisted data carries the new shape.

## Pause and escalation conditions

- Whether Publish should cross the LAN or reach the Platform API rather than being a host-local hand-off — Product Manager. No ticket exists.
- What `validated` means and what gates a publish — Product Manager. No ticket exists.
- The starter-template set and its contents — Product Manager. No ticket exists.
- A saved-plan library over the wire (needed by "Duplicate previous") — Software Architect, then Delivery. Requires a layering decision; no ticket exists.
- Persisting publish state — needs a `session_repo` migration; no ticket exists.
- `AddItem`/`RenameItem` titles are not length-bounded (pre-existing, not introduced here); 500 rows of unbounded title is a real no-leak gap. No ticket exists.
- `ServicePlan::from_parts` — the persistence rehydration path — applies no bound to the plan name, so `MAX_PLAN_LABEL_LEN` holds at the wire ingress only. Documented at the constant; closing it is a persistence change. No ticket exists.
- `sanitize_field` neither drops nor replaces U+2028/U+2029, so a hard line break can still ride into a stored LINK LABEL. Same class as the ingress gap fixed here, different path. No ticket exists.
- **Frame 8's "Duplicate previous" acceptance criterion is NOT met** and cannot be met here: `duplicate_plan` copies the LOADED plan, while every document defining the action (`UX-STATE-MATRIX.md:108`, `COMPONENT-SPECS.md:192`, `UX-FLOWS.md:142`, `WORKFLOWS.md:171`) defines it as duplicating a PREVIOUS service. Three of four empty-state actions land. Needs a plan-library ticket. **No ticket exists.**
- **Publish state is lost on restart, and the "safe direction" argument covers only the badge.** The `v4 (published)` header (`COMPONENT-SPECS.md:150`) cannot be rendered by a counter that returns to zero, and FR-006 exists precisely so an operator does not run a stale plan — so failing to show the badge after a crash is the harmful direction, not the safe one. Needs a follow-up ticket; `86ajy0hxg` covers autosave restore, not this. **No ticket exists.**
- **`AddItem` and `RenameItem` bypass the label rule entirely** — `trim` plus non-empty only — so a direction override, an invisible title or a 50,000-character title still reaches the run sheet through the path an operator actually uses, and `RenameItem` applies no length bound. Routing them through `plan_label_valid` is the coherent single rule now that the set no longer locks out scripts, but it changes established command behaviour and needs its own test round. Routed to security for the scope call. **No ticket exists.**
- Whether `install_plan`'s run-sheet comparison should use the observable-document definition (`same_document`) rather than whole-item equality including ids. Today an import of visually identical rows keeps the live marker when ids match and drops it when a row was removed and re-added. Conservative and harmless, but not the same question. **No ticket exists.**
- Undo after a plan replacement restores the document but not its publish state, so a published plan returns reading as a draft. Accepted: restoring it needs a publish baseline beside all 60 undo snapshots, roughly doubling a stated bound, and the failure is safe (never a false badge, no content loss, no live-output effect). Documented at `install_plan`. No ticket exists.
- The `plan_edit_cmds()` list that pins `can_edit_plan`'s probe as representative is hand-maintained; Rust cannot enumerate `Command`'s variants without a derive this crate does not carry. A new plan-edit command not added to it is silently uncovered. Documented in the test.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajy0hwg-plan-publish-handoff.md`
- Validator result: see the handoff report.
- Independent verification result: PENDING — four reviewers dispatched at `02a8095`.
- Terminal state: PENDING — `VERIFIED_COMPLETE` requires C-018 (Cody re-review at `5729e08`, Quinn outstanding).
- Remaining failed or blocked criteria: C-018 pending; C-019 not applicable (Actions minutes exhausted).
- ClickUp final evidence comment: NOT POSTED — ClickUp MCP unreachable. The pending update is reproduced in the handoff report.
