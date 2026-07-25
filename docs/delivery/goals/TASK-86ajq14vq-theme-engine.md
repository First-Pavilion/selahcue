# Goal Contract — TASK-86ajq14vq-theme-engine

## Identity

- Goal ID: TASK-86ajq14vq-theme-engine
- Parent goal ID: STAGE8-core-presentation
- Title: Implement the theme render model + engine (FR-010, MVP cut) — a slide-design template applied to the audience output with real alignment + per-region typography, switchable with zero content loss, persisted + recovered
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14vq
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Implement the S8-3a theme model (`docs/design/THEME-MODEL-spec.md`) as a real render engine: a **Theme** is a slide-design template (background + positioned **regions** with alignment + typography) the audience output uses. Switching a theme **restyles content with zero loss** (content ⟂ theme). MVP cut: solid background, the single bundled font family, real H+V alignment + per-region size/colour/line-height, shrink-to-fit later. Makes it unmistakably a *template* (alignment/positions/typography differ), not a colour mode.

## Baseline

Verified (post batch-8c revert; tree at `24f72f7`):
- `selahcue-engine::raster::draw_text` shapes one line via cosmic-text and renders it **left/top-anchored** from `rect` (`buffer.layout_runs()` loop; `run.line_w` is available → alignment is a localized x-offset). `Layer::Text{rect,text,px,color}` (scene.rs); the GPU compositor CPU-rasterizes text via this same path.
- `compose_slide(slide, theme, w, h)` (compose.rs) lays out `slide.lines()` top-anchored within one safe-area region; `Theme{background,text,safe_margin_permille}` (slide.rs), `Presenter` holds one `theme` + retained `staged`/`live_slide` slides (present.rs) — NO `set_theme` today.
- Controller/wire/persistence topology (from the S8-3a-adjacent trace): `LiveController::new(_,_,_,theme)`; `Command` enum + `OperatorStateView` (additive `#[serde(default,skip_serializing_if)]`); `required_permission` exhaustive match (`ConfigureOutputs` = Operator-only); `MIGRATIONS` len 7 (v7=live_free_body), `target_version()==len`; `SessionState`+snapshot/restore; cross-lang wire fixtures (test_protocol.rs ↔ protocol_test.dart).

## Inputs and evidence sources

- Story 86ajq14vq + S8-3a spec `docs/design/THEME-MODEL-spec.md` + Figma 204:124/208:124; FR-010; ADR-0014 (shaping); ADR-0002 (compositor); raster.rs/compose.rs/present.rs/controller.rs; tokens.rs.

## Scope

### In scope

- **Theme model** (`selahcue-present`): `RegionStyle{rect‰, align_h, align_v, size‰, line_height‰, color}` + `Theme{name, background: Rgba, title: RegionStyle, body: RegionStyle}`; 3 built-ins matching the mocks — **classic-center** (default; amber reference/title top-centered + white body centered), **high-contrast** (black bg, larger, tighter), **lower-third** (body in a bottom band); registry (`builtin`/`builtin_names`/`name_of`); serde.
- **Alignment engine** (`scene`+`raster`): `Layer::Text` gains `align: TextAlign`; `draw_text` offsets by `(rect.w − line_w)·factor` (measured via cosmic-text) → real L/C/R; work stays frame-bounded (cull preserved).
- **compose**: region-based layout — title + body each laid out in their region with V-alignment (offset the block) + per-region size/colour/line-height; existing safe-area / no-bottom-bleed invariants preserved.
- **Presenter::set_theme** — recompose Preview+Live from retained content (zero loss); `theme()`.
- **Wire**: `Command::SetTheme{name}` (additive) + `OperatorStateView.theme`/`.themes` (skip-if-empty → pinned fixtures byte-stable) + RBAC `ConfigureOutputs`; controller `theme_name` + apply (unknown → BadRequest) + operator_view; console picker + Dart `SetTheme`.
- **Persist**: migration v8 (`session_state.theme`) + `SessionState.theme` + snapshot/restore + main.rs mapping + recovery.

### Non-goals (deferred — note seams; create follow-ups if warranted)

- Gradient/image backgrounds, multi-weight/family fonts, custom-font import, full pagination, per-role auto-selection + per-item override (S8-3d), the Theme Designer UI (S8-3c).

### Constraints

- Zero content loss on switch (property-tested). Additive wire (VERSION stays 2; pinned fixtures byte-identical). Additive nullable migration (older DB opens). Deterministic + 3-OS byte parity (single bundled shaper). Bounded memory. fmt/clippy clean.

### Assumptions and unknowns

- ASSUMED (owner may override at the gate): solid bg + single bundled family + 3 built-ins for MVP. ASSUMED: one Theme renders both scripture (title=reference) and song (title=song title) consistently — per-role templates + per-item override are S8-3d.

## Dependencies and approvals

- S8-3a design (done, gated). S8-2 shaping (done). Blocks S8-3c/d.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Theme model + 3 built-ins (classic-center/high-contrast/lower-third) resolvable by name, distinct, serde round-trip | `cargo test -p selahcue-present` | model tests pass | test_slide::builtin_themes_are_distinct_designs (present 3 built-ins, name round-trip, distinct align/position) | PASS |
| C-002 | yes | Alignment: a centered line's ink is horizontally centred (not left-anchored); right-align too; work stays frame-bounded | raster test | centre/right offset correct; cull intact | test_raster::text_alignment_offsets_the_line (centre/right offset by line_w; cull intact) + rendered previews match S8-3a mocks | PASS |
| C-003 | yes | compose is region-based: title + body render in their regions with V-align + per-region typography; safe-area + no-bottom-bleed invariants preserved | compose/stage tests | themed layout; invariants hold | test_compose (region layout, title-only→body, no bottom-margin bleed, title+6-body cap) | PASS |
| C-004 | yes | `Presenter::set_theme` recomposes Preview+Live with ZERO content loss; a themed scripture + song render (switch = same content, new look) | present test | content preserved; look changes | test_present::set_theme_restyles..._without_losing_content (switch==started-there; content preserved) | PASS |
| C-005 | yes | Wire additive: `SetTheme` pinned fixture; `OperatorStateView` gains theme/themes WITHOUT changing v2 fixtures; RBAC Operator-only; Dart parity | `cargo test -p selahcue-lan` + flutter | fixtures stable; rbac correct | test_protocol (pinned v2 fixtures byte-stable + SetTheme fixture) + test_rbac (Operator-only) + dart parity (flutter 42 green) | PASS |
| C-006 | yes | Persist: migration v8 (`target_version()==8`), older DB upgrades; active theme round-trips snapshot→save→load→restore | data + app tests | theme survives recovery | test_db (target_version==8, v7→v8 upgrade) + test_session_repo (theme round-trip) + test_controller (snapshot/restore theme) | PASS |
| C-007 | yes | Full: workspace + GPU parity + fmt/clippy clean; adversarial Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | workspace+GPU parity+fmt/clippy GREEN; review wf_fe4db576-c11 (3 LOW→fixed, 0 hi/med); **CI run 30176359947 GREEN 12/12 (rust ×3 OSes)** | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-crate cargo test (present/engine/lan/data/app). Broader: full workspace + GPU parity + fmt/clippy; Flutter (Dart parity); 3-OS CI. Independent: adversarial Workflow review (content-loss · alignment-correctness · wire-compat · migration-safety lenses).
- Required environment: local + 3-OS CI.

## Iteration ledger

### Iteration 1

- Target: C-001..C-007.
- Change: added the region-based Theme model (theme.rs, 3 built-ins) + Layer::Text align + draw_text alignment + region-based compose + Presenter::set_theme + the controller/wire/rbac/persist/console/dart plumbing (theme-agnostic, reused from the reverted 8c). Updated the compose/raster tests for the region model; added theme-model, alignment, set_theme, controller-theme, wire-fixture, migration-v8, and session-theme tests.
- Verifier: full workspace + GPU parity + fmt/clippy GREEN; Flutter 42 green; rendered previews of classic/high-contrast/lower-third scripture+song match the S8-3a mocks (centred navy vs bottom-left band = a real template difference, not a colour swap).
- Result: C-001..C-006 PASS locally; C-007 pending the adversarial review (wf_fe4db576-c11) + 3-OS CI.
- Decision: continue (await review; then commit + CI).

## Risks and rollback

- Risks: alignment non-determinism across OSes (mitigated: single bundled shaper + byte-parity CI); a theme switch losing content (mitigated: recompose retained slides + property test); fixture drift (mitigated: additive skip-if-empty + pinned SetTheme fixture both sides); migration breaking old DBs (mitigated: additive nullable + upgrade test). Rollback: git; additive across crates.

## Pause and escalation conditions

- The 3 owner decisions (built-in count / extra fonts / gradient bg) are assumed for MVP and surfaced at the gate; not blockers.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14vq-theme-engine.md --require-complete`
- Validator result: PASS --require-complete (7/7)
- Independent verification result: adversarial Workflow wf_fe4db576-c11 — 3 LOW confirmed → fixed/dispositioned, 0 hi/med
- Terminal state: VERIFIED_COMPLETE (CI run 30176359947 green)
- ClickUp final evidence comment: posted on 86ajq14vq
