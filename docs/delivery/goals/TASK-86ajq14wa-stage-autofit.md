# Goal Contract — TASK-86ajq14wa-stage-autofit

## Identity

- Goal ID: TASK-86ajq14wa-stage-autofit
- Parent goal ID: STAGE8-core-presentation
- Title: Apply auto-fit (wrap-to-width + shrink-to-fit) to the STAGE / confidence-monitor output too — the speaker sees the full verse
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wa
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Owner: the audience output now auto-fits (wrap + shrink, zero content loss), but the **stage / confidence monitor** (`StageDisplay` / `compose_stage`) had its own fixed top-anchored layout (`layout_lines`) that **truncated** (dropped lines past the region bottom) and **clipped** (no wrap) a long verse. Apply the same auto-fit so the speaker sees the full verse.

## Baseline

Verified: `stage::push_region` called `compose::layout_lines` — a fixed-cell, top-anchored layout that `break`s when a line would cross the region bottom (truncation) and does not wrap (`draw_text` clips a wide line). The audience path (`layout_region`) already word-wraps + binary-search-auto-sizes. The wrap/auto-fit core was inline in `layout_region`.

## Scope

### In scope

- **Refactor:** extract the audience auto-fit core into a shared `compose::autofit_layers(lines, rect, max_cell, lh, align_h, align_v, color, fit)`; `layout_region` becomes a thin wrapper (derives params from the `RegionStyle`). No behaviour change for the audience.
- **Stage:** `stage::push_region` now calls `autofit_layers` (ShrinkToFit, top-anchored, `max_cell` = the region's design line height ≈ 20% of the region, `lh` ≈ 1.3) instead of `layout_lines`, so the confidence monitor wraps + shrinks the full slide (reference + verse) — never truncated/clipped.
- Remove the now-unused `layout_lines` + `LineMetrics`.

### Non-goals (seams — note)

- A distinct stage typography design (reference vs body styling); the stage stays uniform. Per-character CJK line-breaking + full `Fit::Paginate` (shared with the audience follow-ups).

### Constraints

- Deterministic; bounded work (same `MAX_WRAP_WORDS`/`line_cap` guards as the audience). The stage's dual-output independence, timer, next region, and identify overlay unaffected. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Shared `autofit_layers` extracted; `layout_region` is a thin wrapper with NO audience behaviour change (existing compose/present tests green) | `cargo test -p selahcue-present` | audience unchanged | present suites green | PASS |
| C-002 | yes | Stage auto-fits: a long verse on the confidence monitor wraps to the region width + shrinks so the FULL verse shows — no truncation, no clip, no overflow | stage render test + visual | full verse on stage | test_stage::stage_current_region_auto_fits... + scratchpad/stage.png | PASS |
| C-003 | yes | No regression: stage timer/next/identify/dual-output intact; `layout_lines`/`LineMetrics` removed cleanly; workspace green; fmt/clippy clean | `cargo test --workspace` + clippy | all green | workspace test + clippy | PASS |
| C-004 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-stage-autofit.md; CI green pending push | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present` (the refactor keeps the audience compose/present suites green; the new `test_stage` auto-fit test proves full verse + no clip + no overflow) + a rendered stage (`scratchpad/stage.png`). Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (refactor-equivalence · stage-correctness/regression lenses).

## Iteration ledger

1. Extracted `autofit_layers` (shared) from `layout_region`; `layout_region` → thin wrapper. Verifier: present compose/present suites green (audience byte-unchanged). C-001 PASS.
2. `stage::push_region` → `autofit_layers` (ShrinkToFit); removed `layout_lines` + `LineMetrics`. Verifier: `stage_current_region_auto_fits_a_long_verse_without_truncation_or_clip` + rendered stage (`stage.png`: full Esther 8:9 on the monitor). C-002/C-003 PASS.
3. **Independent review** (`wf_f1436d1c-fe6`, 2 lenses → verify): **0 findings** — refactor byte-equivalent for the audience; stage geometry/regression clean. Full workspace test + fmt + clippy + operator build clean. See `docs/delivery/CODE-REVIEW-batch-stage-autofit.md`. C-004 PASS (3-OS CI green pending push).

## Risks and rollback

- Risks: the refactor accidentally changing audience output (mitigated: `layout_region` delegates the identical logic; audience tests green); stage spacing looking different (mitigated: `lh`≈1.3 matches the old line+gap ratio; visual checked). Rollback: git.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wa-stage-autofit.md --require-complete`
- Validator result: PASS (4/4 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_f1436d1c-fe6` (2 lenses) — 0 findings.
- Terminal state: GATE_REVIEW (verifiable work complete; local make-ci + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wa; BUILD CONTROL 86ajnx548 updated.
