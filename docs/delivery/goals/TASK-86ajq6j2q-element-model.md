# Goal Contract — TASK-86ajq6j2q-element-model

## Identity

- Goal ID: TASK-86ajq6j2q-element-model
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: Layered element model + z-order + opacity — the engine foundation of Canvas Editing (shape elements this batch)
- Role: backend-engineer (theme model + compositor)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6j2q
- Created: 2026-07-27
- Independent verification required: yes
- Maximum iterations: 16

## Objective

Lay the foundation for on-canvas editing: extend the design/render model from the fixed title/body regions + single `Band` to an ordered list of **layered elements**, each positioned (per-mille rect) + **opacity** + a **z-index** relative to the text, composited back-to-front. This batch delivers the model + compositing + the **shape** element kind (fill/border, like a generalized `Band`); the **image** kind (needs the S8-6 decode, `86ajpzhbc`) and **text** kind, plus all on-canvas authoring UI, are the dependent stories.

## Baseline

Verified from code:
- `scene::Frame { background, layers: Vec<Layer>, blackout }`; `Layer = Fill{rect,color} | Text{…}`. Layers already composite in **painter's (list) order**, so z-ordering exists at the scene level. `raster::blend` is src-over integer alpha; `fill_rect` blends each pixel — so a translucent `Fill` (alpha < 255) already reads as a translucent panel.
- `compose_slide(slide, theme, w, h)` builds a `Frame`: background → `band_layers(band)` (a `Band` composites to `Layer::Fill` rects — fill + up to 4 border edges) → title/body text regions.
- `Theme` is a fixed-size `Copy` POD (`background`, `title`/`body: RegionStyle`, `band: Option<Band>`, `font: Option<FontName>`). `Band` is all-scalar (`Copy`).
- The GPU backend consumes `scene::Layer`; the theme persists as JSON (saved_theme table v11, session custom_theme v9).

**Key architecture finding:** a shape element composites to the existing `Layer::Fill` (exactly as `Band` does) — so **no `scene`/engine/GPU change is needed**; the work is the `Theme` model + `compose_slide` + persistence. A growable element list (`Vec`, for clean `skip_serializing_if` serde + the future text/image kinds) forces **`Theme: Copy → Clone`** — there is no clean Copy-preserving path (a fixed array would serialize as `[null,…]`, breaking byte-stability). The Copy→Clone ripple is mechanical (one explicit copy-move at `present.rs` + compiler-guided fixes).

## Scope

### In scope

- **Model (`theme.rs`):** `Theme.elements: Vec<Element>` (`#[serde(default, skip_serializing_if = "Vec::is_empty")]` → a default theme's JSON is byte-identical). `Element` is an enum with a **`Shape`** variant this batch: `{ rect (per-mille x/y/w/h), fill: Rgba, border: Rgba, border_permille: u16, opacity: u8 (0–255), z: i16 }`. `Theme` derives `Clone` (not `Copy`); `RegionStyle`/`Band`/`FontName` stay `Copy`. Bounded: a `MAX_ELEMENTS` cap enforced where elements are added/loaded (no unbounded growth). The enum is `#[non_exhaustive]`-friendly / additive so `Text`/`Image` variants land later without a wire break.
- **Compose (`compose.rs`):** `compose_slide` renders the elements as `Layer::Fill` layers (a shape = a fill rect + border edges, like `band_layers`), each pre-multiplying the element `opacity` into its fill/border alpha (src-over blend already handles translucency). **z-order:** elements with `z < 0` render BEHIND the text regions, `z >= 0` render IN FRONT; within a group, list order. The existing `Band` + regions are unchanged when `elements` is empty.
- **Copy→Clone ripple:** fix every site the compiler flags in `present.rs` / `controller.rs` / tests (`self.live_theme = self.staged_theme` → `.clone()`, `theme()`/`main_screen_theme()` getters clone, etc.), preserving the per-screen/per-item/saved-theme behaviour exactly.
- **Persistence + recovery:** elements ride in the theme JSON (saved_theme / custom_theme) — **no migration**; `target_version` unchanged; pinned wire/theme fixtures byte-stable. A custom theme with elements round-trips + recovers.

### Non-goals (seams — note)

- The **image** element kind + its decode (S8-6 `86ajpzhbc`, story `86ajq6j49`). The **text** element kind (free text box with content). All **on-canvas authoring UI** — add/select/drag/resize/arrange (stories `86ajq6j4p` interactions, `86ajq6j64` text/shape). So this batch is the engine model + compositing + tests, NOT the Theme Designer UI (a theme's elements are exercised via tests this batch).

### Constraints

- Determinism preserved (NFR-014): a theme with no elements renders **byte-identical** to today — the parity (`test_parity`) + pinned-render tests are the guard. No `scene`/engine/GPU change. Additive serde (byte-stable default) + **no migration**. Bounded (element cap). `RegionStyle`/`Band`/`FontName` stay `Copy`; only `Theme` loses `Copy`. fmt/clippy clean; 3-OS CI (parity is the gate).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Model + ripple: `Theme.elements: Vec<Element>` with an `Element::Shape` variant; `Theme` is `Clone` (RegionStyle/Band/FontName stay `Copy`); bounded (`MAX_ELEMENTS`); the whole workspace + operator compile with the Copy→Clone ripple fixed (per-screen/per-item/saved-theme behaviour preserved) | `cargo build --workspace` + operator | compiles; Theme Clone; bounded | build + test_present | PASS |
| C-002 | yes | Compose z-order + opacity: shape elements render as Fill layers, `z < 0` behind / `z >= 0` in front of the text, each blended with its opacity; a theme with NO elements is byte-identical to today (determinism) | `cargo test -p selahcue-present -p selahcue-engine` | z-order + opacity render; default byte-identical | test_compose | PASS |
| C-003 | yes | Persistence + recovery: elements round-trip in the theme JSON; additive (NO migration, `target_version` unchanged, pinned v2 fixtures byte-stable); a custom theme with elements survives save/load + recovery | `cargo test -p selahcue-app -p selahcue-lan -p selahcue-data` | elements persist + recover; no wire/migration drift | test_controller/test_protocol/test_db | PASS |
| C-004 | yes | Full: make ci + operator build + fmt/clippy clean; determinism preserved (parity + pinned green); independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed; parity holds | CODE-REVIEW-batch-element-model.md; CI run | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present` (a shape element renders as a fill; a `z<0` element paints behind the text, a `z>=0` in front; opacity blends translucently; a theme with no elements is byte-identical to a captured baseline; bounded), `-p selahcue-engine` (no scene/GPU regression, parity), `-p selahcue-app`/`-p selahcue-data`/`-p selahcue-lan` (theme-with-elements round-trip + recovery; no wire/migration drift; `target_version` unchanged). Broader: make ci + 3-OS CI (parity is the determinism gate). Independent: adversarial Workflow review (model/Copy-ripple · compose z-order+opacity+determinism · persistence/no-drift lenses).
- Required environment: local + CI.

## Iteration ledger

- **Iter 1 — model + ripple (C-001).** `theme.rs`: `Element` enum (internally-tagged, `Shape { rect permille, fill, border, border_permille, opacity, z }` — all-scalar → `Element: Copy`) + `Theme.elements: Vec<Element>` (skip-if-empty) + `MAX_ELEMENTS=64` + `Element::z()`. `Theme` derives `Clone` (not `Copy`); RegionStyle/Band/FontName/Element stay `Copy`. **The Copy→Clone ripple was just 3 sites** in present.rs (`self.live_theme = self.staged_theme.clone()`, `main_screen_theme()`/`theme()` getters clone) — everything else compiled unchanged; workspace + operator build. **PASS.**
- **Iter 2 — compose z-order + opacity (C-002).** `compose.rs`: `element_layers` renders a Shape as Fill layers (fill + up to 4 border edges, per-mille like `band_layers`) with opacity multiplied into the fill+border alpha; `compose_slide` stable-sorts by z and renders `z<0` BEHIND the text (after the band), `z>=0` IN FRONT. Evidence: `test_compose` (5 new: empty→byte-identical, front occludes text, behind keeps text on top, opacity blends, additive+byte-stable serde) + the existing pinned/parity tests still green (determinism). **PASS.**
- **Iter 3 — persistence + recovery + bounded (C-003).** Elements ride in the theme JSON (canonical `custom_theme` / `saved_theme`); `set_custom_theme` + `save_theme` reject `elements.len() > MAX_ELEMENTS` (no-leak). **No migration** — `protocol.rs`/`migrations.rs`/`rbac.rs` untouched, `target_version` unchanged, pinned v2 fixtures byte-stable (lan+data green). Evidence: `test_controller` (a custom theme with a front element applies → renders red on the live output → recovers identically; an over-cap theme rejected). **PASS.**
- **Iter 4 — gate (C-004).** `cargo fmt --check` clean (main + operator); `clippy -D warnings` clean on every target this batch touches; 275 tests across present/engine/gpu/app/lan/data pass incl. **test_parity** (determinism preserved); operator builds. Independent adversarial Workflow review launched (run `wf_8475bc43-098`); findings + CI pending.
- **Iter 5 — review findings fixed (C-004).** Review `wf_8475bc43-098` (3 lenses, 7 agents, per-finding adversarial verify) returned **3 confirmed / 1 refuted**. The two MEDIUMs were the SAME defect from two lenses — `load_saved_themes` (controller.rs) was the one theme-with-elements ingress NOT bounded by `MAX_ELEMENTS` (the write paths `set_custom_theme`/`save_theme`/`restore` all reject over-cap, but the startup store load only checked name+JSON), so a tampered/version-skewed DB row could smuggle an unbounded element Vec into compose. **Fixed:** the load filter now also bounds `t.elements.len() <= MAX_ELEMENTS` (reusing its single deserialize), dropping over-cap rows defensively like the name/count/JSON guards; regression added to `saved_theme_library_is_bounded_and_load_drops_bad_entries`. The LOW was a real corner double-blend: element borders now carry the shape opacity, so overlapping full-length edges double-blended (brighter) at the four corners. **Fixed:** left/right edges span full height and own the corners; top/bottom cover only the interior width — every border pixel blends exactly once (opaque borders unchanged; a no-element / no-border theme is byte-identical). New regression `a_translucent_element_border_paints_its_corners_uniformly`. The refuted finding (an unknown future `kind` dropping the whole theme on an older build) is inherent to the additive-enum seam, not this batch, and is already the intended degradation. Re-verified: `make ci` **ALL GREEN** (workspace fmt/clippy/test incl. parity + operator + Flutter). **PASS.**

## Risks and rollback

- Risks: the `Copy → Clone` ripple breaking the determinism-critical present.rs / recently-shipped per-screen/per-item/saved-theme paths (mitigated: compiler-guided; the parity + pinned + per-screen/per-item test suites are the guard; behaviour preserved); a non-empty-elements default accidentally changing the byte-stable theme JSON (mitigated: `skip_serializing_if` + a byte-identical test); unbounded element growth (mitigated: `MAX_ELEMENTS` cap + a test); z-order/opacity compositing wrong (mitigated: behind/in-front + opacity render tests); wire/migration drift (mitigated: NONE — elements ride in the theme JSON; assert fixtures + `target_version`). Rollback: git; additive across the theme/compose layer.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j2q-element-model.md --require-complete`
- Validator result: PASS (4/4 mandatory criteria PASS)
- Independent verification result: adversarial Workflow review `wf_8475bc43-098` — 3 confirmed / 1 refuted; all 3 fixed + regression-tested; re-verified `make ci` ALL GREEN. See `docs/delivery/CODE-REVIEW-batch-element-model.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; paused at the /build user gate for continue/refine/pause/abort)
- ClickUp final evidence comment: posted on 86ajq6j2q (→ qa) + BUILD CONTROL 86ajnx548
