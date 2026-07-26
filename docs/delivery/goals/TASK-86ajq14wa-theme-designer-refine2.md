# Goal Contract — TASK-86ajq14wa-theme-designer-refine2

## Identity

- Goal ID: TASK-86ajq14wa-theme-designer-refine2
- Parent goal ID: STAGE8-core-presentation
- Title: Theme Designer refine 2 — fix shrink-to-fit width clipping (render engine) + align the editor to Figma 204-124 (honest shell)
- Role: frontend-engineer (+ the render-engine fix it needs)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wa
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Two owner-reported issues: (1) **shrink-to-fit still clips** long scriptures — the render engine only fit line COUNT (height), never line WIDTH, so a line wider than the region clipped on the right; (2) the Theme Designer **doesn't match Figma 204-124** — missing the header (New/Import/Export/Save changes), Scriptures/Slides tabs, Add-content toolbar, CANVAS label, the 9-point alignment grid, Lock-aspect + Ref-gap, and Font/Weight/Letter. Fix (1) in the compositor; align (2) to the Figma with **honest "later" affordances** (owner: honest shell now) for the deferred features, **keeping the current 3 built-ins** (owner).

## Baseline

Verified: `compose::layout_region` shrink-to-fit sizes the cell so `want` lines fit `rect.h` (vertical only); `raster::draw_text` shapes each line with `set_size(fs, None, None)` (NO wrap) → an over-wide line clips at `clip_right`. No width measurement is exposed. The Theme Designer (`dist/index.html`/`app.css`/`app.js`, split) has the full-center canvas + drag/resize + inspector (X/Y/W/H + H/V align + colour/size/lh/Fit) but not the Figma's header/tabs/add-content/9-point-grid/lock/refgap/font shell. Deferred features have their own stories: saved-theme library `86ajq4xmy`, multi-font engine `86ajq3225`.

## Scope

### In scope

- **Shrink-to-fit width fix (engine + compose):** add `raster::measure_line_width(text, px)` (same font sizing as `draw_text`); in `layout_region`, after the vertical-fit cell, scale the cell down so the **widest** line also fits `rect.w` (iterate to absorb rounding). A long verse renders fully — no right-edge clip.
- **Design alignment (Figma 204-124), honest shell:** header (`New` wired · `Import`/`Export`/`Save changes` → honest status routing to `86ajq4xmy`); Scriptures/Slides tabs (Scriptures live; Slides → honest later); Add-content toolbar (Text/Scripture/Shape/Image → honest later); CANVAS label; **9-point alignment icon grid** (functional, maps to `align_h`/`align_v`); **Lock-aspect** (functional resize constraint); Ref-gap + Font/Weight/Letter present but **disabled + honestly labelled** ("arrives with 86ajq3225"); Fit reordered to Shrink/Paginate/Clip. Keep the 3 built-ins.

### Non-goals (seams — note)

- Actually building Import/Export, the saved-theme library / Save-changes persistence (`86ajq4xmy`), on-canvas Add-content, Slides (non-scripture) templates, multi-font family/weight/letter-spacing + reference-gap (`86ajq3225`) — presented as honest "later" affordances only.

### Constraints

- The width fix is deterministic (bundled shaper) + keeps existing render tests green. All functional Theme Designer wiring (drag/resize/preview/apply/host-builtins) intact. No fake controls (honest "later" states). Pinned console invariants (emergency footer/keymap, token needles, structure) intact. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Shrink-to-fit fits WIDTH: `measure_line_width` added; a long line scales so it fits `rect.w` (no right clip); existing shrink/render tests stay green | `cargo test -p selahcue-present -p selahcue-engine` + render | wide line fits; no regression | test_compose::shrink_to_fit_scales_a_wide_line_to_fit_the_region_width + scratchpad/long.png | PASS |
| C-002 | yes | Theme Designer aligns to Figma 204-124: header (New/Import/Export/Save) · Scriptures/Slides tabs · Add-content · CANVAS · 9-point align grid · Lock-aspect · Ref-gap · Font/Weight/Letter; functional controls work | structure test + headless render | matches the Figma shell | test_tokens needles + scratchpad/shot-td-aligned.png | PASS |
| C-003 | yes | Deferred affordances are HONEST (no fake success — route to their stories); functional wiring (drag/resize/preview/apply/lock) intact; pins green; JS parses; tags balanced | structure test + headless interaction + node --check | honest + no regression | test_tokens/test_keymap green; node --check; lock-aspect interaction (2.00→2.00 locked, 0.86 unlocked) | PASS |
| C-004 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batchS83c-refine2.md; CI green pending push | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present -p selahcue-engine` (the width-fit + existing shrink/compose/render tests); `test_tokens` (split-aware pins + the new shell needles); `test_keymap`; `node --check app.js`; tag balance; a headless render of the aligned surface + a headless interaction test (lock-aspect resize). Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (shrink-fit-correctness · design-honesty/no-fake-controls · a11y/regression lenses).
- Required environment: local + CI.

## Iteration ledger

1. **Shrink-to-fit width fix** — root-caused the clip to vertical-only fit + non-wrapping `draw_text`; added `raster::measure_line_width` and a bounded width-shrink loop in `layout_region`. Verifier: `shrink_to_fit_scales_a_wide_line_to_fit_the_region_width` (incl. the would-overflow-at-design-size sanity) + present/engine suites green; rendered long verse (`long.png`) no longer clips. C-001 PASS.
2. **Figma 204-124 honest-shell alignment** — added the header (New wired · Import/Export/Save → honest status), Scriptures/Slides tabs, Add-content toolbar, CANVAS label, the 9-point alignment icon grid (functional, `data-a`/`data-v`), Lock-aspect (functional), Ref-gap + Font/Weight/Letter (disabled + honestly labelled → 86ajq3225), Fit reordered. Kept the 3 built-ins. Verifier: headless render (`shot-td-aligned.png`) matches the Figma; interaction test proved Lock-aspect (2.00 locked / 0.86 unlocked); pins + `node --check` + tags green. C-002/C-003 PASS.
3. **Independent adversarial review** (`wf_01c8ca19-a5a`, 3 lenses → verify, 5 agents): 2 raised → **2 CONFIRMED (both LOW a11y), both fixed; shrink-fit + honesty lenses clean.** Fixed: (a11y) `Save changes` AA contrast — dropped `golive` so the dimmed label passes; (a11y) completed the tabs widget — `role=tabpanel` + `aria-controls` + `aria-disabled` on the not-yet Slides tab. Verifier: pins + tags green; full workspace test + fmt + clippy clean; operator clippy + build clean. See `docs/delivery/CODE-REVIEW-batchS83c-refine2.md`. C-004 PASS (3-OS CI green pending push).

## Risks and rollback

- Risks: the width shrink over-shrinks tiny (single ultra-long token → cell 1px, acceptable degenerate) or costs extra shaping per compose (bounded: ≤4 passes × lines, cheap at preview/Go-Live sizes); dishonest UI if a "later" control fakes success (mitigated: they set an honest status, never a success); pinned-needle drift from the restructure (mitigated: tests updated + green). Rollback: git; the engine fn is additive.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wa-theme-designer-refine2.md --require-complete`
- Validator result: PASS (4/4 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_01c8ca19-a5a` (3 lenses, 5 agents) — 2 confirmed LOW a11y findings both fixed; shrink-fit + honesty lenses clean. See `docs/delivery/CODE-REVIEW-batchS83c-refine2.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; local make-ci + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wa; BUILD CONTROL 86ajnx548 updated.
