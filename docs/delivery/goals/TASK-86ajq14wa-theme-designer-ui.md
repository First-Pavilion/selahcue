# Goal Contract — TASK-86ajq14wa-theme-designer-ui

## Identity

- Goal ID: TASK-86ajq14wa-theme-designer-ui
- Parent goal ID: STAGE8-core-presentation
- Title: The Theme Designer editor (S8-3c) — author a custom audience theme in the console with an accurate live preview, apply it to the output, and recover it
- Role: frontend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wa
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Make FR-010's "theme editable centrally" real: replace the console's Theme Designer placeholder surface with an editor — pick a built-in theme, edit its key properties, see an **accurate live preview**, and **Apply** it to the audience output (persisted + recovered). Per THEME-MODEL-spec §5; Figma 204:124.

## Baseline

Verified: the theme engine (S8-3b) renders ANY `selahcue-present::Theme` via `compose_slide → selahcue-engine::render → FrameBuffer` (RGBA8 bytes); `Theme` + `RegionStyle` + `Fit` are serde-serializable. The console (`dist/index.html`) has a placeholder `#surface-theme-designer` reached from the app menu. `selahcue-lan` (wire) does NOT depend on `selahcue-present` → a custom theme must cross the wire as a JSON **string**. `selahcue-operator` (Tauri) already imports `selahcue_present::Theme` + `selahcue_engine` → it can render a preview **locally** (a pure function of Theme, no host round-trip). Wire adds are additive (`Command`/`OperatorStateView` use skip-if-empty; pinned v2 fixtures). Migrations: 8 (v8=theme); `target_version()==len`. `base64` is already vetted in the tree.

## Inputs and evidence sources

- Story 86ajq14wa + epic 86ajp07ce; THEME-MODEL-spec.md §2/§5; Figma 204:124; theme.rs/compose.rs/raster.rs; protocol.rs/rbac.rs; migrations.rs/session_repo.rs; controller.rs; selahcue-operator/main.rs; dist/index.html; test_tokens.rs (pin + structure test).

## Scope

### In scope (MVP slice)

- **Preview command** (`selahcue-operator`, local pure fn): `preview_theme(theme_json) -> { w, h, rgba_base64 }` — deserialize the JSON to `Theme`, compose a sample scripture slide, render, base64-encode the RGBA. No wire/host round-trip.
- **Apply**: `Command::SetCustomTheme{ theme_json: String }` (additive, RBAC `ConfigureOutputs`) → controller deserializes → `Theme` → `presenter.set_theme` + `theme_name = "custom"`; invalid JSON → `BadRequest`. Operator `set_custom_theme` command (Local + Remote).
- **Persist**: migration v9 (`session_state.custom_theme` JSON) + `SessionState.custom_theme` + snapshot/restore (a custom theme takes precedence over the named theme on recovery).
- **Frontend** (`dist/index.html` `#surface-theme-designer`): theme list (built-ins + "＋ New" = duplicate current) + an inspector editing the audience theme's **background colour**, and the **body** + **title** regions' **colour · size · horizontal alignment · line-height · Fit**; a `<canvas>` **live preview** (ImageData from `preview_theme`, debounced on change) + **Apply**. Keep pinned console invariants.

### Non-goals (seams — note; later increments)

- On-canvas element drag/add, position/dimension + 9-point + reference-gap editing (MVP does colour/size/align/line-height/fit), import/export, a saved named-theme library, per-screen assignment (86ajq321k), gradient/image backgrounds (86ajq3225).

### Constraints

- Additive wire (VERSION 2; pinned fixtures byte-stable). Additive nullable migration (older DB opens). ALL `test_tokens` needles + the structure test remain; emergency footer/keymap intact. The preview is a pure function (deterministic, matches the real output). fmt/clippy clean; 3-OS CI.

### Assumptions and unknowns

- ASSUMED: rendering a small preview (e.g. 480×270) each debounced edit is fast enough (the engine renders < a few ms at that size). ASSUMED: one active custom theme at a time (a named library is a later slice).

## Dependencies and approvals

- S8-3b theme engine (done). Reached via the app menu (86ajq321f, done).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `preview_theme(theme_json)` composes + renders a sample slide with the given Theme and returns base64 RGBA + dims; matches the engine output; bad JSON errors cleanly | operator unit/int test | accurate preview payload | operator test | PASS |
| C-002 | yes | `Command::SetCustomTheme{theme_json}` is additive (pinned v2 fixtures byte-stable) + RBAC ConfigureOutputs; controller applies the custom theme (invalid JSON → BadRequest) | `cargo test -p selahcue-lan` + controller test | fixtures stable; apply works | test_protocol/test_rbac/test_controller | PASS |
| C-003 | yes | Persist: migration v9 (`target_version()==9`), older DB upgrades; the active custom theme round-trips snapshot→save→load→restore (takes precedence over the named theme) | data + app tests | custom theme survives recovery | test_db/test_session_repo/test_controller | PASS |
| C-004 | yes | Theme Designer surface: theme list + inspector (bg/body/title: colour·size·align·line-height·Fit) + a canvas live preview (updates on edit) + Apply; reached from the menu | screenshot/DOM + structure test | editor renders + previews + applies | dist/index.html + render | PASS |
| C-005 | yes | Pinned console invariants intact: `test_tokens` (pin + structure) green; JS valid; tags balanced; emergency footer/keymap untouched | `cargo test test_tokens` + JS check | all green | test run | PASS |
| C-006 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batchS83c.md; CI run | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate cargo test (lan/data/app) + an operator preview test; test_tokens (pin+structure); JS syntax; a headless render of the Theme Designer surface (canvas preview). Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (wire-compat · preview-correctness/security · persistence · a11y/invariant lenses).
- Required environment: local + CI.

## Iteration ledger

1. **Backend seams** — added `preview_theme` (pure host render, base64 RGBA), `Command::SetCustomTheme{theme_json}` (additive, RBAC ConfigureOutputs), `render_sample`, migration v9, `SessionState.custom_theme`, controller `set_custom_theme` + snapshot/restore precedence. Verifier: per-crate `cargo test` (lan/data/app/present) → all green. C-001/C-002/C-003 evidence in place.
2. **Frontend surface** — replaced the `#surface-theme-designer` placeholder with the editor (theme list + `<canvas>` preview via `ImageData` from `preview_theme`, debounced + Inspector: bg/colour/size/align/line-height/Fit + Apply). Verifier: headless render (`shot-td.png`) inspected — list + preview + inspector + Apply + emergency footer all present; `test_tokens` structure + pin green; JS parses; tags balanced. C-004/C-005 PASS.
3. **Robustness pre-empt** — before review, changed `set_custom_theme` to persist the **canonical re-serialized** `Theme` (bounds snapshot size, strips ignored JSON). Verifier: `set_custom_theme_applies_and_survives_recovery` still green.
4. **Independent adversarial review** (`wf_a55ca48d-b5d`, 4 lenses → per-finding verify, 15 agents): 11 raised → **4 CONFIRMED, 7 refuted** (incl. the verbatim-JSON finding, refuted because iter-3 pre-empted it). Fixed all 4: (a11y MED) segmented controls now `role="group"`+`aria-labelledby`+`aria-pressed`; (a11y MED) Apply failure surfaced on the aria-live status; (test LOW) inspector-control needles pinned; (test LOW) added `recovery_prefers_the_custom_theme_over_a_conflicting_built_in_name`. Verifier: full workspace `test`+`fmt`+`clippy` clean; operator `cargo check` clean; new/updated tests green. C-006 PASS pending 3-OS CI on push. See `docs/delivery/CODE-REVIEW-batchS83c.md`.

## Risks and rollback

- Risks: preview render cost per keystroke (mitigated: small preview + debounce); a theme-JSON injection/oversized payload (mitigated: serde-typed deserialize, size bound, BadRequest on invalid); wire/fixture drift (additive skip-if-empty + pinned fixture); migration breaking old DBs (additive nullable + upgrade test). Rollback: git; additive across crates.

## Pause and escalation conditions

- If the preview render proves too slow at the chosen size, reduce the preview resolution (documented), not the accuracy model.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wa-theme-designer-ui.md --require-complete`
- Validator result: PASS (6/6 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_a55ca48d-b5d` (4 lenses, 15 agents) — 4 confirmed findings all fixed; 7 refuted. See `docs/delivery/CODE-REVIEW-batchS83c.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; local `make ci` + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wa; BUILD CONTROL 86ajnx548 updated.
