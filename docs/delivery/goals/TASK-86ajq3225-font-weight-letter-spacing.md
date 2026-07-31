# Goal Contract — TASK-86ajq3225-font-weight-letter-spacing

## Identity

- Goal ID: TASK-86ajq3225-font-weight-letter-spacing
- Parent goal ID: EPIC-86ajp07ce-presentation-slides
- Title: Enable font weight + letter-spacing in the Theme Designer (refine #5)
- Role: backend-engineer (engine text shaping + theme model) + frontend-engineer (designer fields)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq3225 (⚠ ClickUp MCP rate-limited — updates queued below)
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 12

## Objective

Owner refine #5 — the Theme Designer's **Weight** (`#td-weight`, a Regular-only disabled select) and **Letter** spacing (`#td-letter`, a disabled `0 em` input) fields are disabled ("arrive later, 86ajq3225"). Enable them: a theme can set a **font weight** (Regular…Bold) and **letter-spacing** (tracking) that the audience output renders, deterministically (NFR-014), additively (no wire/migration break), for both the bundled default font and a per-machine system font.

## Baseline

Verified from code:
- **Engine** (`selahcue-engine/src/raster.rs`): `draw_text(fb, rect, text, px, color, align, font)` shapes via cosmic-text 0.12 (swash rasterizer) over the single **bundled Noto Sans Regular** (`attrs_for(font)` sets only the family; `buffer.set_text(…, Shaping::Advanced)`); glyphs are blitted at `origin_x + pg.x`, aligned by the shaped `run.line_w`. `measure_line_width` mirrors the attrs. `scene::Layer::Text { rect, text, px, color, align, font }` (derives `Eq`).
- **cosmic-text/swash** synthesize weight: requesting `Attrs::weight(Weight::BOLD)` against a family that only has Regular yields a **synthetic-bold** `Synthesis` swash renders by a pure integer embolden — deterministic + cross-OS-identical (the glyph `cache_key` encodes the synthesis). A **system font** with a real bold face uses that face.
- **Present** (`theme.rs`): `Theme` carries a theme-level `font: Option<FontName>` (86ajq6fxt); `RegionStyle` has `size_permille`/`line_height_permille` per region. `compose::compose_slide` emits a `Layer::Text` per region (title/body) with the theme font. No weight/letter-spacing yet.
- **Designer** (`dist/`): `#td-weight` (disabled select, Regular only) + `#td-letter` (disabled `0 em`) sit with the theme-level font control.

**Key design:** add a **theme-level** `weight: u16` (400 default) + `letter_spacing_permille: i16` (0 default; signed per-mille of the font size, so it scales with size) to `Theme` (additive, `skip_serializing_if` default → byte-stable). `Layer::Text` gains `weight: u16` (skip-if-400) + `letter_spacing_px: i32` (skip-if-0), `Eq`-preserving. `draw_text` applies `Attrs::weight(Weight(weight))` (synthesis for the bundled font) and offsets glyph *i* by `i·letter_spacing_px`, adjusting the alignment width by `(glyph_count−1)·letter_spacing_px`; `letter_spacing_px` is clamped to a sane range so tighter tracking can't invert the left-to-right cull. `compose` passes the theme weight + `letter_spacing_px = cell_px·letter_spacing_permille/1000` to each `Layer::Text`. The designer enables Regular/Medium/Semibold/Bold (400/500/600/700) + an em input (→ per-mille). GPU-skip unaffected (Text already skipped). Deterministic (pure integer glyph raster + a deterministic synthesis).

## Scope

### In scope

- **Engine (`scene.rs`, `raster.rs`):** `Layer::Text` gains `weight: u16` (`skip_serializing_if` = 400) + `letter_spacing_px: i32` (skip-if-0), Eq-preserving; `draw_text` + `measure_line_width` apply weight (cosmic-text `Weight`) + per-glyph letter-spacing (bounded); default (400/0) renders **byte-identically to before**.
- **Present (`theme.rs`, `compose.rs`):** `Theme` gains `weight: u16` + `letter_spacing_permille: i16` (additive, `skip_serializing_if` default); `compose_slide` passes them to each `Layer::Text` (letter-spacing per-mille → px via the region cell). Default theme JSON byte-identical.
- **Designer (`selahcue-operator/dist/`):** enable `#td-weight` (Regular/Medium/Semibold/Bold) + `#td-letter` (em → per-mille); wire to the previewed/saved theme; keyboard + WKWebView-safe.
- **Tests:** engine (BOLD renders more ink than Regular; positive letter-spacing pushes the rightmost ink further right; deterministic; default 400/0 byte-identical; additive serde; bounded/no-panic on extreme spacing), compose (weight + letter-spacing flow into `Layer::Text`; per-mille→px), theme (additive serde: a default-weight/spacing theme's JSON is unchanged), operator headless (the fields set the theme + re-preview).

### Non-goals (seams)

- Per-REGION weight/letter-spacing (title vs body independently) — theme-level this slice; bundling additional weight FACES for the default font (synthetic bold is used); variable-font axes; kerning controls; multi-family bundling (FR-173).

### Constraints

- Determinism (NFR-014): the synthetic-bold synthesis + the integer letter-spacing offset are pure functions → byte-identical cross-OS; a Regular/0-spacing render + pinned text fixtures byte-identical. Additive serde (default byte-stable) + no wire/migration change. Bounded (letter-spacing clamped; the left-to-right cull preserved; no panic). `Eq` preserved. GPU-skip unaffected. fmt/clippy/deny clean; 3-OS CI.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Engine: `Layer::Text` gains `weight`/`letter_spacing_px` (additive, Eq, skip-if-default → a Regular/0 layer is byte-identical); `draw_text` renders BOLD with more ink than Regular, positive letter-spacing widens the glyph spread, deterministically + bounded (no panic on extreme spacing) | `cargo test -p selahcue-engine` | weight+spacing render; deterministic; additive | test_scene/test_raster | PASS |
| C-002 | yes | Present: `Theme` gains `weight`/`letter_spacing_permille` (additive, default JSON byte-identical); `compose_slide` flows them into every `Layer::Text` (per-mille→px) | `cargo test -p selahcue-present -p selahcue-app -p selahcue-lan -p selahcue-data -p selahcue-gpu` | flows; no drift; parity unchanged | test_compose/test_controller | PASS |
| C-003 | yes | Designer: `#td-weight` + `#td-letter` enabled + wired (theme preview + save); operator + workspace compile; clippy clean | operator `node --check` + headless | fields set the theme + re-preview | headless test | PASS |
| C-004 | yes | Gate: make ci + operator build/fmt/clippy/deny clean; determinism + pinned fixtures green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-font-weight.md; CI 30642394688 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-engine` (BOLD ink > Regular ink; letter-spacing rightmost-ink shift; determinism; Regular/0 byte-identical; additive serde; extreme-spacing no-panic), `-p selahcue-present` (weight + letter-spacing in `Layer::Text`; per-mille→px), `-p selahcue-gpu` (parity unchanged — Text still skipped), `-p selahcue-app`/`-lan`/`-data` (no wire/migration drift; a weighted/spaced theme applies+recovers). Broader: make ci + operator gate + 3-OS CI. Operator headless: the weight/letter fields set the theme + re-preview. Independent: adversarial Workflow review (shaping-determinism/weight-synthesis/bounded · model-serde-no-drift · designer-wiring lenses).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (verify the risk): confirmed empirically that cosmic-text 0.12 does NOT synthesize bold for the single-weight bundled font (`bold_renders_more_ink` failed with only `Attrs::weight`). Pivoted weight to a deterministic **faux-bold** (integer horizontal smear) for the bundled font; a system font uses its real weight face.
- Iter 1 (C-001): `TextStyle { weight, letter_spacing_px }` + `Layer::Text.style: Option<TextStyle>` (scene.rs, additive/Eq/skip-if-default); `draw_text` applies `Attrs::weight` + faux-bold embolden (font.is_none() && weight>550 → 1–2 px) + per-glyph letter-spacing (clamped ±2·px; `ls>=0` cull guard); `measure_line_width` takes weight. Evidence: `test_raster` — `bold_weight_renders_more_ink_than_regular` (+ determinism), `letter_spacing_widens_and_default_is_byte_identical` (None == default == pre-feature), `extreme_letter_spacing_is_bounded_no_panic` (i32::MIN/MAX); `test_scene::text_style_is_additive_and_default_skipped`. Result: PASS.
- Iter 2 (C-002): `Theme` gains `weight`/`letter_spacing_permille` (additive, skip-if-default); `autofit_layers`/`layout_region` thread them; `letter_spacing_px = cell·permille/1000`; the confidence monitor (`stage.rs`) stays 400/0. Evidence: `test_compose::theme_weight_and_letter_spacing_flow_into_text_layers` (default → no style; weighted → every text layer weight 700 + scaled px); full `-p selahcue-present/-app/-lan/-data/-gpu` green (no wire/migration drift; parity unchanged — Text skipped). Result: PASS.
- Iter 3 (C-003): operator `dist/` — `#td-weight` (Regular/Semibold/Bold/Black) + `#td-letter` (em) enabled + wired to `tdTheme.weight`/`letter_spacing_permille` (deleted at the 400/0 default → byte-stable). Evidence: `node --check`; headless **58/58** (5 new #5: weight 700 set, 0.1 em → 100 permille, fields enabled, Regular/0 dropped). Result: PASS.
- Iter 4 (C-004): Gates — `cargo fmt --check` + `clippy --workspace --all-targets` + `--features server` clean; `cargo test --workspace` (53 groups, 0 fail) + `--features server` green; operator fmt/clippy/build + `deny bans·licenses·sources` OK; headless 58/58. Independent adversarial Workflow review + 3-OS CI: in progress.
- Iter 5 (C-004, review landed): adversarial Workflow review `wf_66ba08ec-5b7` (3 lenses → refute-by-default verify) raised 6 → **4 confirmed (2 distinct defects) → 2 refuted**. **Both defects fixed + regression-tested:** (1) MEDIUM panic regression — `raster.rs:741` `2 * px as i32` overflowed i32 for `px ≥ 2³⁰` (DEBUG multiply-overflow / RELEASE min>max), firing even at the default style; fixed by computing the clamp bound in i64+saturate (`((px as i64)*2).min(i32::MAX as i64) as i32`), pinned by `extreme_px_text_does_not_overflow_panic`. (2) LOW wrong-render — `measure_line_width` omitted letter-spacing, so auto-fit fit the untracked width while `draw_text` added `(glyphs−1)·ls`, clipping tracked text on the right (FR-010 zero-loss violation); fixed by folding positive tracking into `wrap_at` (per-glyph + per-space, conservative, O(words)), pinned by `tracked_text_fits_its_region_no_right_clip`. Refutations correct (intentional ls≥0 cull guard; cosmetic app-unproducible weight-select gap). Re-verified: workspace **466 passed / 0 failed**, `--features server`/`encryption` green, fmt/clippy clean, operator headless 58/58. Full review in `docs/delivery/CODE-REVIEW-batch-font-weight.md`. Result: PASS pending only the 3-OS CI run (this push).

## Risks and rollback

- Risks: synthetic bold NOT rendering bolder for the bundled font (mitigated: verify empirically first — a `bold_renders_more_ink` test; if cosmic-text/swash does not synthesize, fall back to bundling a Bold face OR scope weight to system fonts + note the seam). Non-deterministic weight/spacing (mitigated: pure integer synthesis + integer offset; determinism + pinned tests). Letter-spacing breaking the left-to-right cull / a panic (mitigated: clamp spacing; saturating arithmetic; a bounded test). Byte-drift on a default theme (mitigated: `skip_serializing_if` defaults; byte-identical tests). Rollback: git; additive across scene/raster/theme/compose/designer.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq3225-font-weight-letter-spacing.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; queued)

## Pending ClickUp updates (MCP rate-limited — post on recovery)

- Move `86ajq3225` → in-progress with the goal start comment (this contract, engine=goal, max 12).
- At handoff: evidence comment + status per the QA outcome; update BUILD CONTROL `86ajnx548`.
