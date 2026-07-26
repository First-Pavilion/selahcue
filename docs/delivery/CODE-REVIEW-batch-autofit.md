# Code Review — Batch auto-fit text (stop truncating long verses; wrap-to-width + auto-size)

- **Scope:** story `86ajq14wa` (owner refine): Esther 8:9 (longest KJV verse) rendered **truncated with "…"** and didn't fill the box. Root-fix the auto-fit so scripture/songs render the **full** content, wrapped to the region width and scaled so every line fits (FR-010 zero content loss). Executed via `/goal` (`TASK-86ajq14wa-autofit-text.md`), backend-engineer.
- **Method:** adversarial Workflow review (`wf_f491e24f-6ed`, 3 lenses → per-finding adversarial verify, 9 agents). Lenses: auto-fit-correctness/convergence · content-loss/zero-loss · performance/no-leak. No self-approval.
- **Outcome:** **6 raised → 2 CONFIRMED → both fixed; 4 refuted.** 1 HIGH + 1 MEDIUM (both in the new wrap/auto-fit code, caught + fixed before ship).

## What shipped

**Root cause:** the controller pre-wrapped verses at a **fixed 42 columns** and **capped at 6 lines with "…"** (`SCRIPTURE_MAX_LINES`) — a stale leftover from before the theme engine's shrink-to-fit existed. **Fix:**
- **Controller:** removed the fixed-col wrap + cap + "…" for scripture and songs — each verse/stanza-line is passed as a full **paragraph**.
- **Compositor (`compose::layout_region`):** now **word-wraps** each paragraph to the region width and **auto-sizes** the font via a binary search for the largest cell (≤ the design size) where every wrapped line fits **both** `rect.h` and `rect.w`. A long verse shrinks so the whole passage shows and fills the box; a short one keeps the design size; songs' line breaks are preserved. Verified: Esther 8:9 renders all 8 wrapped lines ending "language." (full verse, filled box).

## Findings and dispositions

| # | Lens | Sev | Finding | Disposition |
|---|------|-----|---------|-------------|
| 1 | perf-noleak | **HIGH** | **Unbounded shaping could stall Go Live.** The wrap measured the *accumulated line* per word → O(words²) shaping, and the `line_cap` was checked only *between* paragraphs, so a single large paragraph (a long free-text paste, a whole chapter) issued millions of `rustybuzz` shapes → the **synchronous** `go_live()` could block for seconds mid-service. | **Fixed:** the wrap now measures each word **once** (memoized per cell) and fills lines by summed advances → **O(words)**; a **`MAX_WRAP_WORDS = 1000`** budget (far above any real verse) + the intra-loop `line_cap` bound the work. Re-benched: a 3000-word paste composes in **~19.5ms** (was multi-second). Overflow beyond the budget → pagination (a later slice), the slide *data* is untouched. |
| 2 | autofit-correctness | **MED** | **Over-wide single token clipped.** The fit predicate checked only *height*; `wrap_paragraph` put the first word of a line unconditionally, so an unbreakable token wider than the region (a very long word, or a **space-less CJK verse** — `split_whitespace` makes it one token) stayed one line at the design size and **clipped on the right** — reintroducing the very bug the prior refine fixed. | **Fixed:** the wrap now flags `fits_w = false` when any token exceeds `rect.w`, and the binary-search predicate requires `fits_w && block_h ≤ rect.h` — so an over-wide token **shrinks the cell** until it fits (never clips). Test: `auto_fit_shrinks_an_unbreakable_token_to_fit_the_width`. (Proper per-character CJK line-breaking — so a long CJK verse wraps instead of shrinking to one tiny line — is noted as a follow-up.) |

### Refuted (verified NOT real — 4)

- **"silently drops overflow lines (no …)"** — refuted: at the chosen cell `block_h(display.len()) ≤ rect.h` guarantees `display.len() ≤ max_lines`, so `n == display.len()` — no line dropped; the `line_cap` only triggers for a block that can't fit anyway (and `block_h(rect.h+1) > rect.h`, so a capped trial always reports "doesn't fit").
- **"test asserts the data model, not the frame"** — refuted: the controller-level no-"…" assertion is correct for its layer; the frame-level wrap/fit is covered by `test_compose`.
- **"latency test uses a 6-word verse"** — addressed anyway: added `go_live_latency_holds_for_the_longest_verse_auto_fit` (Esther 8:9).
- **"RESET_EVERY shares the render counter"** — refuted low-impact: the cache stays memory-bounded and deterministic (a mid-compose reset rebuilds identically).

## Verification

- Full workspace `cargo test --all-features`, `fmt --check`, `clippy --all-targets` **clean**; operator crate `cargo build` clean.
- Backend: `auto_fit_wraps_a_long_paragraph...` (full verse wrapped + every line ≤ rect.w + no word dropped + fits height), `auto_fit_shrinks_an_unbreakable_token_to_fit_the_width`, `scripture_slides_keep_the_full_passage_never_truncating` (Esther 8:9 + Psalm 119's 176 verses + John 11:35), `go_live_latency_holds_for_the_longest_verse_auto_fit`; a rendered Esther 8:9 (`scratchpad/esther.png`) — full verse, filled box, no "…".
- Perf: Esther 8:9 compose ~19ms; a 3000-word paste ~19.5ms (bounded). All < the 150ms go-live budget.
- Deferred with seams (noted): full `Fit::Paginate` (multi-slide for content beyond one slide), per-character CJK line-breaking, auto-GROW beyond the design size for very short content.
- **3-OS CI:** pending this push.
