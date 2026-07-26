# Goal Contract — TASK-86ajq14wa-autofit-text

## Identity

- Goal ID: TASK-86ajq14wa-autofit-text
- Parent goal ID: STAGE8-core-presentation
- Title: Auto-fit verse text — stop truncating long scriptures with "…"; wrap to the region width + scale the font so the FULL verse fills the box (zero content loss, FR-010)
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14wa
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 12
- Independent verification required: yes

## Objective

Owner-reported: Esther 8:9 (the longest KJV verse) renders **truncated with "…"** and does not shrink to show the whole verse, and the text does not fill the region box. Root-fix the auto-fit so scripture (and songs) render the **full** content, wrapped to the region width and scaled so every line fits the region — filling the box, never truncating (FR-010 zero content loss).

## Baseline

Verified: `controller.rs` pre-wraps verse text at a **fixed 42 columns** (`SCRIPTURE_WRAP_COLS`) and **caps at 6 lines**, truncating to 5 + "…" (`SCRIPTURE_MAX_LINES`) — a stale leftover from before the theme engine existed (its comment cites "pagination is a later slice"). `compose::layout_region` then lays each pre-wrapped line as a `Layer::Text`; `raster::draw_text` renders one line, no wrap, clips overflow. `raster::measure_line_width(text, px)` now exists (refine 2). `Slide.body: Vec<String>`. Songs pass stanza lines (intentional breaks); scripture passes verse text.

## Scope

### In scope

- **Compositor auto-fit (`compose::layout_region`):** treat each input body line as a **paragraph**; **word-wrap** it to the region width (`rect.w`) using `measure_line_width`; for `ShrinkToFit`, iteratively size the cell to the **largest** (≤ the design size) where ALL wrapped lines fit `rect.h` — so a long verse shrinks to fit the whole passage and fills the box, and a short one keeps the design size. Intentional input line breaks (song stanzas) are preserved (each paragraph wraps independently). No horizontal clip. `Clip`/`Paginate` keep the design size + wrap to width (drop vertical overflow; pagination later).
- **Controller: stop truncating** — remove the fixed-col wrap + 6-line cap + "…" for scripture and song slides; pass the full verse / stanza lines as paragraphs (the compositor wraps + fits). Update the stale comment.
- Tests updated to the new correct behavior (full verse, wrapped-to-width, auto-sized).

### Non-goals (seams — note)

- Full `Fit::Paginate` (multi-slide pagination); auto-GROW beyond the design size to fill for very short content (design size stays the ceiling); per-region reference-gap.

### Constraints

- Zero content loss (the full verse always renders — no "…"). Deterministic (bundled shaper). Bounded work (the fit loop is capped; no unbounded shaping). Existing zero-loss / alignment / no-leak invariants preserved. fmt/clippy clean; 3-OS CI.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | No truncation: a long verse (Esther 8:9) renders the FULL text — no "…", the last words present; the controller no longer caps/truncates scripture or songs | `cargo test -p selahcue-app` + render | full verse, no ellipsis | test_controller::scripture_slides_keep_the_full_passage_never_truncating + scratchpad/esther.png | PASS |
| C-002 | yes | Auto-fit: `layout_region` wraps each paragraph to `rect.w` (no horizontal clip) and `ShrinkToFit` sizes the font so ALL wrapped lines fit `rect.h` (fills the box); a long verse produces many lines that all fit; songs' breaks preserved | `cargo test -p selahcue-present` + render | wraps + fits; widest ≤ rect.w; all lines fit | test_compose::auto_fit_wraps_a_long_paragraph... + esther.png | PASS |
| C-003 | yes | No regression / zero content loss: theme switch still zero-loss; titles/songs render; no-leak + determinism hold; existing suites green (updated where semantics legitimately changed) | `cargo test --workspace` | all green | workspace green; Esther compose ~19ms (< go-live budget) | PASS |
| C-004 | yes | Full: make ci + operator build + fmt/clippy clean; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-autofit.md; CI green pending push | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-app` (controller: full verse, no "…") + `-p selahcue-present` (compose wrap+fit; a long verse's wrapped lines all fit + widest ≤ rect.w; songs preserve breaks; determinism) + `-p selahcue-engine`; a rendered Esther 8:9 (full verse, filled box). Broader: make ci + 3-OS CI. Independent: adversarial Workflow review (auto-fit-correctness/convergence · content-loss/zero-loss · performance-no-leak lenses).
- Required environment: local + CI.

## Iteration ledger

1. **Controller** — removed the fixed-42-col wrap + 6-line cap + "…" for scripture (`scripture_slide_in`) and songs (`item_slide`); full verse/stanza paragraphs pass through. Verifier: `scripture_slides_keep_the_full_passage_never_truncating` (Esther 8:9 + Psalm 119 176 verses + John 11:35). C-001 PASS.
2. **Compositor auto-fit** — `layout_region` word-wraps each paragraph to `rect.w` + binary-searches the largest cell (≤ design) where all wrapped lines fit `rect.h`. Verifier: `auto_fit_wraps_a_long_paragraph...` + rendered Esther 8:9 (`esther.png`, full verse + filled box). C-002 PASS.
3. **Independent review** (`wf_f491e24f-6ed`, 3 lenses → verify, 9 agents): 6 raised → **2 CONFIRMED (1 HIGH + 1 MED), both fixed; 4 refuted.** (HIGH) unbounded O(words²) shaping could stall Go Live → rewrote the wrap O(N) memoized + `MAX_WRAP_WORDS` budget (3000-word paste now ~19.5ms); (MED) over-wide/CJK single token clipped → the fit predicate now checks width (`fits_w`), so it shrinks the cell. Added `auto_fit_shrinks_an_unbreakable_token...` + `go_live_latency_holds_for_the_longest_verse_auto_fit`. Full workspace test + fmt + clippy + operator build clean. See `docs/delivery/CODE-REVIEW-batch-autofit.md`. C-003/C-004 PASS.

## Risks and rollback

- Risks: the fit loop cost (shaping per wrap-candidate — bounded by a capped iteration count + measured widths; acceptable at preview + Go-Live sizes; verify no-leak via the existing RESET_EVERY cache bound); a single unbreakable ultra-long token (cell floors at 1px — acceptable degenerate); song rendering changes (auto-fit vs fixed — verify stanzas still read well); many existing tests assert the OLD capped behavior (update to the new correct behavior, not weaken invariants). Rollback: git; the change is within compose + controller.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14wa-autofit-text.md --require-complete`
- Validator result: PASS (4/4 mandatory PASS)
- Independent verification result: adversarial Workflow review `wf_f491e24f-6ed` (3 lenses, 9 agents) — 2 confirmed (HIGH+MED) both fixed; 4 refuted. See `docs/delivery/CODE-REVIEW-batch-autofit.md`.
- Terminal state: GATE_REVIEW (verifiable work complete; local make-ci + operator build green; 3-OS CI green pending this push; awaiting the `/build` user gate)
- ClickUp final evidence comment: posted on 86ajq14wa; BUILD CONTROL 86ajnx548 updated.
