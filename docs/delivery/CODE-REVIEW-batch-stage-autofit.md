# Code Review — Batch stage auto-fit (apply wrap-to-width + shrink-to-fit to the confidence monitor)

- **Scope:** story `86ajq14wa` (owner refine): the audience output auto-fits, but the **stage / confidence monitor** (`compose_stage`/`push_region`) used its own fixed top-anchored `layout_lines` that **truncated** (dropped lines past the region bottom) and **clipped** (no wrap) long verses. Apply the same auto-fit so the speaker sees the full verse. Executed via `/goal` (`TASK-86ajq14wa-stage-autofit.md`), backend-engineer.
- **Method:** adversarial Workflow review (`wf_f1436d1c-fe6`, 2 lenses → per-finding verify). Lenses: refactor-equivalence (the audience output must not change) · stage-correctness/regression. No self-approval.
- **Outcome:** **0 findings.** Both lenses read the code (43 tool-uses total) and confirmed the audience output is unchanged and the stage change is correct — a clean, well-scoped change.

## What shipped

**Refactor (DRY):** the audience auto-fit core was extracted from `layout_region` into a shared **`compose::autofit_layers(lines, rect, max_cell, lh, align_h, align_v, color, fit)`**; `layout_region` is now a thin wrapper that derives those params from the theme's `RegionStyle`. The audience output is byte-identical (the wrapper passes `max_cell = style.cell_px(height)` and the helper applies the same `.min(rect.h).max(1)`; all other params come straight from `style`).

**Stage:** `stage::push_region` now calls `autofit_layers` (`ShrinkToFit`, top-anchored, `max_cell ≈ 20% of the region`, `lh ≈ 1.3` matching the historical line+gap ratio) instead of `layout_lines`, so the confidence monitor **word-wraps + shrinks** the full slide (reference + verse). The now-unused `layout_lines` + `LineMetrics` were removed. Verified: Esther 8:9 renders in full on the stage (reference + whole verse, no truncation/clip), with the timer strip + next region + clock intact (`scratchpad/stage.png`).

## Findings

**None.** The two lenses verified:
- **refactor-equivalence** — `layout_region`'s wrapper passes exactly the old values (`design_cell = style.cell_px(height).min(rect.h).max(1)`, `lh = style.line_height()`, align/colour/fit/rect from the style); the combined early-return is equivalent; the wrap/binary-search/layout body is unchanged. The audience compose/present suites stay green.
- **stage-regression** — the timer strip, current + next regions, clock, and display-identify overlay all still compose; `layout_lines`/`LineMetrics` have no other callers (removed cleanly); the geometry doesn't overflow or overlap; a short line stays a sensible size and an empty slide renders nothing; the work is bounded by the shared `MAX_WRAP_WORDS`/`line_cap` guards; dual-output independence holds.

## Verification

- Full workspace `cargo test --all-features`, `fmt --check`, `clippy --all-targets` **clean**; operator crate `cargo build` clean.
- `stage_current_region_auto_fits_a_long_verse_without_truncation_or_clip` (Esther 8:9 wraps into ≥3 lines, every line ≤ region width, every word present incl. the reference, nothing overflows the current band); the existing stage suite (timer states, current/next, empty-state, dual-output independence, identify) stays green; the audience compose/present suites unchanged.
- Visual: `scratchpad/stage.png` — the full Esther 8:9 on the confidence monitor.
- Deferred (shared with the audience follow-ups): per-character CJK line-breaking, full `Fit::Paginate`.
- **3-OS CI:** pending this push.
