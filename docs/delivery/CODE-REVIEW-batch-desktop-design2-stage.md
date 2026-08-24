# Code review — batch: desktop Design 2.0 stage / confidence monitor

**Surface:** `implementation/desktop/crates/selahcue-present/src/stage.rs` (the stage /
confidence monitor, FR-037 / FR-040).
**Source of requirements:** `docs/design/DESIGN-2.0-PARITY-AUDIT-stage.md` (STG-001…STG-078),
plus four owner decisions and two owner-reported defects that arrived mid-batch.

**Status:** implementation + tests complete; `selahcue-present` and `selahcue-app` green.
`make ci` has **not** been run — the coordinator holds that slot.

---

## 1. Flash-safety measurement — evidence to discharge ARCH-UX-REVIEW-stage5 M4

The owner chose to keep the 0.5 Hz TIME-UP pulse. `ARCH-UX-REVIEW-stage5.md:183` offers two
routes to discharge M4; the project previously took *"or make solid-inverted the default"*.
Keeping the pulse means discharging under the first route — **constrain the default flashing
TIME UP to satisfy the red-flash and flash-area sub-criteria**, with analyzer evidence.

Measured with `selahcue_engine::analysis::analyze_flashes` (WCAG worst-case over an 8×8 tile
grid, so it covers **area**, not just rate). 10-second capture at 12 fps — five full pulse
cycles. Harness: `crates/selahcue-present/tests/test_stage_flash.rs`.

| Template | luminance flashes/s | red flashes/s | `passes` | worst tile (col,row) | tile luminance swing | pulsing area @1920×1080 |
|---|---|---|---|---|---|---|
| Worship | **0.000** | **0.000** | **true** | (5,7) | 0.0415 | **0.54 %** |
| Scripture | **0.000** | **0.000** | **true** | (6,4) | 0.0432 | **0.63 %** |
| Timer-only | **0.000** | **0.500** | **true** | (3,3) | 0.0944 | **4.18 %** |

FR-175 limit is ≤3 general **and** ≤3 red flashes/sec. **All three templates pass, with a 6×
margin on the worst figure (timer-only red, 0.500/s).**

Three things worth stating precisely:

- **The field is `passes`, not `within_limit`** (`analysis.rs:35`).
- **Worship and Scripture register zero flashes of either kind.** The pulsing word is too
  small a fraction of its tile to move that tile's luminance past the analyzer's amplitude
  gate (swings 0.042/0.043 against a 0.10 threshold). That is the **area** sub-criterion doing
  its job, not the analyzer missing the pulse — the pulse is independently proven present by
  `the_time_up_pulse_is_present_and_small_area_on_every_template`.
- **Timer-only is the case M4 was actually about** (whole-screen takeover). Its pulsing region
  is 4.18 % of the screen against WCAG's 25 % small-safe limit, and only the red channel
  registers at all, at 0.500/s.

**Controls, so these numbers cannot be vacuous:**

- *Positive control* — a synthetic 6 Hz full-screen strobe through the **same** harness,
  capture length and analyzer call reports `luminance=6.000/s red=6.000/s passes=false`. The
  instrument fires when there is something to fire at.
- *Vacuity guard* — each capture asserts its frames are not all identical, so a flattened
  `time_up_ink` would fail rather than report a comfortable 0.000/s.
- *Sensitivity check* — these figures are measured on a build that already replaces the
  timer-only TIME-UP background with this batch's vignette. Re-run against the **pre-change
  flat `#2a1416` wash**: `luminance=0.000/s red=0.500/s passes=true`. **Identical verdict** —
  the result is a property of the pulse, not of the new vignette.

`time_up_ink` was **not modified**.

---

## 2. Owner-approved deviations, recorded so they are not "fixed" back

### 2.1 The TIME-UP pulse vs FR-059

`SelahCue-PRD.md:190` (FR-059, MVP) states:

> At 0 the configured TIME UP state renders on selected outputs only; wording customisable;
> **default is solid-inverted (static), not flashing** — if flashing is enabled it is
> constrained by FR-175

`stage.rs`'s `time_up_ink` alternates the TIME-UP word bright/dim once per elapsed second.
This is a **deliberate, owner-approved deviation** from that sentence, retained on purpose,
with the §1 measurements as its FR-175 evidence. Do not "correct" it to static.

### 2.2 The design frame's lyric band is the two-line case, not normative geometry

Figma `373:133` draws the Worship template with a **two-line** lyric, which fills its 212-unit
band at the design size and looks right. The frame was never drawn against a real 8–9-line
stanza. Consequently `H_LYRIC = 212` (37.7 % of `REF_H`) is read in this batch as *the
two-line case*, and the live band is elastic instead (§4.2). This is a real change in how
`373:133` is read and it is deliberate.

### 2.3 The audience output is untouched

Owner-locked. All growth/elastic work is expressed at the **stage call sites**, which hand
`autofit_layers` the region height as its ceiling. **No `Fit` variant was added and
`compose.rs` was not edited**, so every audience caller is byte-identical.
`the_audience_output_still_shrinks_only` pins it: a short audience slide still renders at its
theme's design size rather than growing.

---

## 3. STG items closed

**Type sizes (§6.4 substitution).** STG-019, 020, 021, 024, 025, 028, 030, 037, 040, 041,
042, 044, 045, 049, 051, 054, 055, 056, 057, 060, 064, 072. Every Figma **em** is now a named
constant in `stage.rs`'s `design` module and converted through one seam
(`Metrics::cell`, `line_box = em / 0.72 / 563 × h`). The audit's table reproduced exactly at
1920×1080 for every role checked.

**Ink tokens.** STG-003, 004, 018, 074, 076 (partial). `StageTheme::dark()` now points at
`tokens::design2` — `timer_ok → PREVIEW`, `timer_warn → WARN`, `timer_alert → LIVE`,
`accent → GOLD`, `alert_wash → LIVE_SOFT`, the soft tints/borders → `*_SOFT`/`*_BORDER`, and
the song dot → `PRIMARY_HOVER` (`#7e6eff`, the asset-verified value). **No token value
changed**; only references moved.

**Shapes.** STG-008 (hairline borders), STG-009 (corner radii), STG-010 (circular dots),
STG-017, 026, 027, 034, 046, 047, 048, 070. Implemented with the engine's **existing**
`Layer::Shape` (`Ellipse` / `RoundedRect` / `Triangle`, with `border_px` + `corner_px`) — see
§7.1, the audit was wrong that no such primitive exists. `selahcue-engine` was not edited.

**Letter-spacing.** STG-011 — all nine tracking values, on the runs the design tracks, with a
negative control pinning the untracked runs at 0.

**Overrun readout.** STG-038 and STG-065 — `OVER m:ss` on Worship, `▲ OVER BY m:ss` on
Timer-only, plus an `OVER m:ss` on the Scripture panel (its TIME-UP frame does not exist;
audit Q5 approved the code's behaviour). The `▲` is a `ShapeKind::Triangle`, not a glyph — the
bundled Latin face has no `▲`, exactly as it has no `…`.

**Other DRIFT closed in the same code paths.** STG-035 (the SERVICE TIMER caption flips to the
alert ink at TIME UP), STG-062 (the vignette, §4.1), STG-063 + STG-067 (the segment name moves
into the header at TIME UP and is no longer drawn twice), STG-066 (date-only at TIME UP),
STG-013 (line height 1.21 for chrome / 1.24 for the verse).

**NFR-020.** STG-077 — `StageContext::text_scale_permille` + `StageDisplay::set_text_scale`,
default 1000‰, clamped 750–1750‰, multiplying every line box and its tracking. STG-078 —
`StageTheme::high_contrast()`, **additive**; `dark()`'s structure is unchanged apart from the
token repoint above.

## 4. Owner-reported defects fixed

### 4.1 TIME-UP polarity → the Design 2.0 vignette (STG-062)

`374:166`'s elliptical radial ramp (`#2A0E12` → `#190C10` @0.5 → `#08090D`) replaces the flat
wash. **The engine has no radial gradient** — `Layer::Gradient` is a two-stop *linear* ramp
(`GradientDirection` is vertical/horizontal/diagonal) and `raster.rs` is another session's
tree — so it is approximated by 12 concentric `ShapeKind::Ellipse` bands, painted the ramp
colour at each band's inner edge. 12 is derived from the ramp, not taste: the whole gradient
spans 34 steps of red and 5 of green/blue, so 12 bands step red by ~3/255. Bounded in layer
count, and every band precedes the first text run so the stack lands in the static-prefix
cache. **Recommend a `Layer::RadialGradient` follow-up in `selahcue-engine`.**

Contrast on the vignette: `#ff4d4d` on the `#190c10` midpoint = **5.83:1**, on the `#2a0e12`
core = **5.49:1**, on the `#08090d` rim = **5.94:1**. Clears AA-normal everywhere, so AA-large
at the rendered size a fortiori.

### 4.2 "Tiny lyric, huge empty margins" → elastic bands

Two coupled causes, both confirmed:

1. **Shrink-only fit.** The design size was a *ceiling*; a short stanza could never reach past
   it and a long one shrank inside a band that is only 37.7 % of the frame.
2. **A fixed NEXT size.** With `EM_NEXT_LINE = 30` against a shrinking lyric, **any stanza of
   ≥6 lines rendered the coming line larger than the line being sung.**

Fixed by making the live band **elastic** — it runs from the bottom of the header chrome to
the top of a reserved NEXT row, less a named `BAND_SAFE_GAP` at each end, with both edges
derived from the chrome's own constants. Re-derived rather than taken on trust:

| | fixed | elastic | gain |
|---|---|---|---|
| Worship band | 212.0 | **306.2** | +44 % at every line count |
| Worship 8-line em | 16.1 | **23.3** | +44 % |
| Worship 9-line em | 14.3 | **20.6** | +44 % |
| Scripture band | 300.0 | **318.2** | +6 % |

NEXT is now `subordinate_cell(resolved_lyric_cell, 30/56, …)` — the design's own ratio —
**with a design-size ceiling**. That ceiling is a deliberate addition to the brief: coupling
that could push NEXT *up* when the band grows trades one defect for another, because the
scripture NEXT line is ellipsized (it would ellipsize away to `...`) and the worship one is
not (it would overflow the frame). Coupling therefore only ever pulls NEXT down.

**Timer-only was deliberately not made elastic, and this needs an owner call.** It has no
auto-fit content band — its readout is a single fixed `line()` at the design's 190px em. The
gap between the segment label (ends ≈199) and the footer (starts 436) is 237 units, so an
elastic rule there would resolve the readout to ~171px em and **shrink it by ~10 %**. Applying
the rule would make that template worse; I left it and am reporting it rather than forcing it.

### 4.3 `OVER 0:00` frozen — the overrun never reached the screen

My first cut put `overrun_secs` on `StageContext` with a `StageDisplay::set_overrun_secs`
setter, on the reasoning that adding a field to `TimerView` would break test literals in files
this batch was told not to edit. **That placement caused the defect**: nothing on the live path
called the setter, so the value held its default forever. Test convenience drove a production
design choice.

Corrected structurally: `overrun_secs` now lives on **`TimerView`**, filled by
`TimerView::from_timer` from `Timer::overrun(now)`. The setter is gone. `LiveController::tick`
already builds a `TimerView` and passes it straight to `stage.update`, so **the wiring needed
no controller change and there is no setter left to forget**. Every literal construction site
states the value explicitly — no `..Default::default()`, deliberately.

Per the coordinator's correction, `timer_key` was **left untouched**: `overrun` is a pure
function of `elapsed`, so adding it to the key could never make the key flip when it otherwise
would not.

### 4.4 The Worship NEXT line ran off the frame (found by measurement, §7.3)

Fixed in the same batch: Worship now ellipsizes its next line as Scripture already did, and
the boundary is tested in **both** directions — a line long enough to overflow must gain the
ellipsis and stay inside the frame, and a line that fits must render verbatim. A 1..=40-word
sweep pins the invariant across the boundary (`right <= frame width` at every length, and the
ellipsis present exactly when the text was cut), with a premise assertion that the sweep
actually crosses the boundary rather than proving one direction forty times.

---

## 5. Deliberately NOT done

| Item | Why |
|---|---|
| **STG-039** (remove the pulse) | Owner keeps it. §2.1. |
| **STG-071** (the gold-on-white message chip) | The **frame** is wrong (2.04:1, fails AA at every size). The implementation's inversion is correct at 11.19:1. Not corrected toward the frame; `the_production_message_chip_keeps_its_accessible_polarity` now pins that polarity so this batch's size/shape work cannot regress it. |
| **STG-001, 006, 007** (background / panel / chip fills) | `#08090d`, `#0c0e14`, `#12141c` have **no `design2` equivalent**. Matching them means new token values, which is the four-surface lockstep. Deferred to a token batch. |
| **STG-002** (the `muted` ink) | Audit **Q2**, unresolved: `#6b7383` (4.17:1, AA-large only) vs the mobile precedent `#a7aebe` (8.95:1). An open owner question, not an unambiguous fix. |
| **STG-029, 052, 058/059/060** (the `· Sermon` suffix, the panel sub-caption, the two-tone footer) | Need data the composer is not given (the plan segment name, the segment end time), and the two-tone footer's second ink is blocked on Q2. |
| **STG-016** (per-output region toggles) | Out of scope; also FR-059's "selected outputs only". |
| **STG-031, 033** (the TIME-UP band fill `#1c0c0e` and its 100-unit height) | The fill has no `design2` equivalent; the height is content-driven in the frame. |
| **STG-069** (the simplified message header) | Audit **Q7** unresolved — sketch or real. |
| Timer-only elastic band | §4.2 — with the owner. It has no auto-fit band and the rule would *shrink* its readout ~10 %. **Not started.** |
| Audience palette re-skin | §7.5 — with the owner. The two renders are visually indistinguishable (no channel moving more than 15/255), so it is a consistency call, not a legibility one. **Nothing on the audience output changed.** |

---

## 6. Mutation verification

Every control below was broken, the suite re-run **with its siblings** (whole test file, never
`--exact`), the RED confirmed, and the source restored from a pristine copy.

| # | Mutation | Result |
|---|---|---|
| M1 | `from_timer` stops reading `Timer::overrun` | **RED** — `the_stage_overrun_readout_advances_across_ticks`: *"byte-identical at 1s over and 3s over — the overrun readout is not advancing"* |
| M2 | Worship readout back to its pre-fix size (52.0 → 32.3 em) | **RED** — `type_sizes_match_the_design_2_0_reference`, left 86 / right 138 |
| M3 | `overrun_label` drops the value | **RED** — `time_up_shows_how_far_over_the_timer_has_run` |
| M4 | The design's +1px tracking becomes none | **RED** — `tracked_runs_carry_the_designed_letter_spacing`: *"worship NEXT label +1"*, left 0 / right 2 |
| M5 | The status dot goes back to a square | **RED** — `status_dots_are_circles_and_pills_are_rounded`: *"worship draws exactly two dots … found 0"* |
| M6 | The lyric band reverts to a shrink-only ceiling | **RED** — `the_live_band_grows_to_fill_its_region` |
| M7 | NEXT goes back to a fixed constant | **RED** — `the_next_line_never_outgrows_the_live_line` + `the_next_row_keeps_the_designs_ratio_to_the_live_line`, left 79 / right 47 |
| M8 | The ON TIME pill borrows the warn tint | **RED** — `stage_display_uses_the_semantic_inks`: *"stage ok soft tint"* |
| M9 | The operator text scale is ignored | **RED** — 3 tests, incl. the 48px-equivalent roll-call (9 roles fell below the bar) |
| M10 | The vignette collapses to the flat wash | **RED** — `timer_only_time_up_paints_a_bounded_radial_vignette` |
| E1 | The lyric band reverts to the fixed 212-unit rect | **RED** — *"a two-line stanza fills 404 px of a 590 px band"* |
| E2 | `BAND_SAFE_GAP` set to 0 | **RED** — 2 tests, incl. the no-collision check |
| E3 | Width bound removed | **first attempt GREEN — see below** |
| W1 | Worship ellipsize removed (the overflow defect restored) | **RED** — `a_long_worship_next_line_is_ellipsized_and_a_short_one_is_left_alone`: *"a next line long enough to overflow was not ellipsized"* |
| W2 | Worship ellipsize forced on lines that already fit | **RED** — same test, other direction: *"a short next line was altered — it must render verbatim, never gain an ellipsis"* (+5 siblings) |
| C1 | The NEXT-coupling ceiling (`.min(design_cell)`) removed | **RED** — `the_next_coupling_ceiling_holds_where_it_is_load_bearing` + `the_scripture_next_line_stays_subordinate_to_the_verse` |

**E3 is worth flagging as a process note.** My first mutation inflated `fill_cell`'s return by
4×, expecting the width-bound assertion to fire. It came back **GREEN — but the mutation was
neutralised, not the test weak**: `autofit_layers` clamps `max_cell` to `rect.h` internally, so
the inflated ceiling was a no-op. The real width bound lives in `compose.rs` (`fits_w`), which
this batch may not edit. Re-run as **E3′** — widen the lyric *region* until width cannot bind —
it returned **RED**: *"a 40-character unbreakable token resolved to 590 px in a 590 px band —
the fit is not bounded by the region WIDTH, only its height."*

**C1 exposed a ceiling assertion that did not bite, and it has been replaced.** My first
ceiling check lived in `the_next_row_keeps_the_designs_ratio_to_the_live_line` and asserted the
*worship* NEXT cell against the design size. Removing the ceiling left it **green**: on Worship
the reserved row height happens to equal the design cell, so `row_h` clamps to the same value
and the ceiling is enforced twice. The ceiling is only load-bearing on **Scripture**, whose row
is taller. `the_next_coupling_ceiling_holds_where_it_is_load_bearing` now asserts it there, at
a one-line verse (maximum band growth), and pins the premise that the *uncapped* ratio would
actually exceed the design cell in that case — otherwise the test would be asserting a ceiling
in a scenario where it never applies.

**Two mutations were RED but with unusable messages, and the tests were fixed rather than
accepted.** Under W2 and C1 the over-inflated line is ellipsized away to `"..."`, so the
content-based lookup panicked with `.expect("the … NEXT line renders")` — technically RED, but
naming the lookup rather than the defect. Both now report what actually went wrong and list the
runs present, and the short-line direction asserts against the frame's text list so it survives
the run being truncated away.

**A vacuous assertion I wrote and had to fix.** `test_tokens.rs` briefly contained
`assert_eq!(ink.rgba, ink.rgba)` — a value compared to itself, which can never fail, inside the
per-state chip loop. Caught in review, not by me. It now binds each state's stage ink, soft
tint and border to that state's **own** `design2` swatches (M8 is its mutation). I re-audited
the rest of what I added and removed three more assertions that could not fail: a `px > 0`
check behind an `||` that let an absent run pass, a `>= 1` check on a value `line()` already
clamps, and an `assert_ne!(chip_ink, WHITE)` implied by the `assert_eq!` above it. Each was
replaced with the property it was standing in for.

---

## 7. Findings to report

### 7.1 The audit is wrong that the engine has no shape primitive

The audit's STG-008/009/010 say *"`fill()` is the only rect primitive and it has no stroke"*
and prescribe adding one to `selahcue-engine`. **`Layer::Shape` already exists**
(`scene.rs:161`) with `ShapeKind::{Ellipse, RoundedRect, Triangle}`, `fill`, `border`,
`border_px` and `corner_px`, rasterized by `raster.rs:718 draw_shape`. Borders, radii, circular
dots and the `▲` were all implementable with **zero** engine changes.

**Corrected in the audit itself** (`docs/design/DESIGN-2.0-PARITY-AUDIT-stage.md`), since a
reader following the build order would otherwise open a coordination thread with the
`selahcue-engine` session that is not needed: §8 step 2's engine bullet is struck through with
the correction, and §2's STG-008/009 rows now carry a pointer to it.

### 7.2 The `measure_word` memo trap is already handled for the auto-fit path

The audit's step 0 warns that adding tracking to an auto-fit region would shrink against
untracked cached widths. **`autofit_layers` already budgets for it** — `compose.rs:84`'s
`ls_add`, with a comment explaining that tracking is deliberately kept *out* of the memo key
and added on top, "because folding it into the key would split the memo per tracking value for
no saving." So the trap as described does not exist for tracking. It **does** exist for any
attribute that changes the *shaped* width (weight, family, stretch) — those have no such
escape hatch. All nine tracked runs go through `line()`, which bypasses the memo entirely, and
`no_auto_fit_region_carries_tracking` pins that none of the three auto-fit regions carries any.

Note the unit difference, which is a live trap: `autofit_layers` takes tracking in **permille
of the cell** (`i16`); `TextStyle::letter_spacing_px` is **px** (`i32`).

### 7.3 Frame-edge behaviour (the owner's screenshot question) — measured

Probed at 1920×1080 with a deliberately over-long next line:

- **The wall clock cannot overflow.** It is right-aligned into a rect spanning `x=0 …
  x=1843` (`0.96·w`), i.e. it stops 77 px inside the right edge and starts at 0. Top-right
  clipping in the screenshot is the crop, not the app. (Since confirmed by the owner.)
- **The Worship NEXT row could overflow, on the right — now FIXED.** The row is centred via
  `w.saturating_sub(group_w)/2`, which clamps to 0 when the group is wider than the frame, so
  the chip landed at `x=21` — flush left but not clipped — while the *line* ran to
  `right=4854` against a 1920-wide frame and was cut at the frame edge with no ellipsis,
  because Worship did not ellipsize its next line (Scripture did: chip at `x=111`, no
  overflow). A speaker read a sentence sliced off mid-word with no indication anything was
  missing.

  Worship now applies the same `ellipsize()` Scripture uses, against the width left between
  the frame margins after the chip and its gap. `ellipsize` returns the string unchanged when
  it already fits, so **a line that fits does not gain an ellipsis** — the half of the contract
  that a naive "does it ellipsize?" assertion would miss.

  One consequence worth recording: at the maximum stage text scale (175 %) the worship next
  line is now legitimately truncated where it previously ran off-screen. That is the intended
  trade — truncated *with* an indication beats silently cut — but it means a large text scale
  shows less of the coming line.

### 7.4 The "as it ships" palette quoted for the render task was not the audience theme

The brief quoted background `#0E1116` and caption ink `#9AA4B2`. Those are
`tokens::BG_BASE` and `tokens::NEUTRAL.ink` — **operator-surface** tokens. The audience
compositor uses `Theme::classic()`, whose background is `#080a14` and whose verse ink is pure
`#ffffff`. The renders below use what actually ships, read from the constructor.

### 7.5 The two palette renders are visually near-identical — say so before shipping the comparison

| Role | Ships today | Design 2.0 | Δ per channel |
|---|---|---|---|
| Background | `#080a14` | `#0b0d12` | (+3, +3, −2) |
| Accent (reference line) | `#f2b53c` | `#f2b84b` | (0, +3, +15) |
| Verse ink | `#ffffff` | `#f4f6fb` | (−11, −9, −4) |

Accent contrast: **10.76:1** shipped vs **10.86:1** Design 2.0. Verse: 19.74:1 vs 17.97:1.
Both clear AA comfortably either way. 100 % of pixels differ *numerically* (the background
changed everywhere) but **no channel moves by more than 15/255, and the accent difference is
3 units of green and 15 of blue** — not perceptible at congregation distance. The honest
summary for the owner is that this re-skin is a **consistency** decision, not a legibility one.

Renders (1920×1080, identical slide/geometry/fit, palette the only variable):

- `/Users/m.oluwole/Documents/code/scph/docs/design/visual-parity/palette-decision/audience-scripture-shipped.png`
- `/Users/m.oluwole/Documents/code/scph/docs/design/visual-parity/palette-decision/audience-scripture-design2.png`

Nothing shipped changed: the Design 2.0 variant is a local `Theme` value inside the render
test. `theme.rs` and every token are untouched.

### 7.6 The design's message card cannot hold its own body size

Figma `375:134` gives the card 160 units and the body a 68-unit text box for a 56px em. This
renderer takes a **line box** and derives `em = line_box × 0.72`, so the same 56px em needs 78
units — 10 more than the card's own arithmetic (`28 + 22 + 12 + 68 + 30 = 160`) leaves. The
body region therefore runs to the card's bottom edge rather than stopping at the design's
`pb 30`; the extra is line-box leading, not ink, so the glyphs still sit inside the padded
area. Clamping instead would render the note at ~38px where the design says 56px.

Separately: the longest preset payload (`WRAP UP · 2 MIN LEFT`, Figma `563:169`) measures a
hair wider than the design's own 612px body box in our shaper, so it lands **one pixel** under
the cap. That is the auto-fit working, not a size regression, and it is pinned as such.

---

## 8. Files changed

**Source**

- `implementation/desktop/crates/selahcue-present/src/stage.rs` — the batch.

**Tests**

- `crates/selahcue-present/tests/test_stage_parity.rs` *(new, 23 tests)* — type scale,
  tracking, shapes, overrun, vignette, text scale, high contrast, elastic bands, hierarchy,
  the audience-unchanged guard, the STG-071 polarity guard.
- `crates/selahcue-present/tests/test_stage_flash.rs` *(new, 5 tests)* — the §1 measurement.
- `crates/selahcue-present/tests/render_audience_palette.rs` *(new, 1 test)* — §7.5's renders.
- `crates/selahcue-app/tests/test_stage_overrun.rs` *(new, 3 tests)* — the §4.3 end-to-end wire.
- `crates/selahcue-present/tests/test_tokens.rs` — the stage ink pin moved from the legacy
  tokens to `design2`, plus the high-contrast audit. **No token value is asserted here**, so
  it cannot drift out of step with `design2_palette_is_pinned_across_surfaces` — which was
  re-run and **passes untouched** (see §9).
- `crates/selahcue-present/tests/test_stage.rs` — three stale pins updated to the Design 2.0
  values (giant readout 190px em; the timer-only TIME-UP corner is the vignette rim, with a
  new "the centre is redder than the rim" assertion; the song dot `#7e6eff`), the lyric-band
  overflow bound re-derived from the elastic geometry, and `TimerView`/`StageContext`
  literals updated.
- `crates/selahcue-present/tests/test_measure.rs`, `tests/test_present.rs`,
  `tests/visual_parity_render.rs` — one `TimerView` literal each, stated explicitly.

**Docs / artefacts**

- this file; `docs/design/visual-parity/palette-decision/*.png`.

**Not touched:** `implementation/mobile/**`, `selahcue-engine/**` (read-only),
`selahcue-present/src/compose.rs`, `src/measure.rs`, `src/theme.rs`, `src/tokens.rs`,
`scripts/measure_nfr.sh`, `selahcue-app/src/controller.rs`.

`test_present.rs` and `visual_parity_render.rs` were on this batch's do-not-touch list; the
one-line `TimerView` edit in each was made under the coordinator's explicit later instruction
to move the field onto `TimerView` and update the literals.

---

## 9. Verification

```bash
cargo test -p selahcue-present                      # 16 suites, all ok
cargo test -p selahcue-app --features server        # all ok (--features server is mandatory)
cargo clippy -p selahcue-present --all-targets      # clean
cargo clippy -p selahcue-app --features server --all-targets   # clean
rustfmt --edition 2021 --check <each changed file>  # clean
```

`make ci` **not** run — the coordinator holds the slot. It is required before push: this batch
touches `test_tokens.rs`, one of the four-surface lockstep's checks.

**The cross-surface token pin is intact**, and it is worth stating its real shape because the
concern raised against this batch named the wrong test.

`design2_palette_is_pinned_across_surfaces` covers **three** surfaces — `dist/app.css`,
`tokens::design2::MANIFEST`, and the Flutter `design_tokens.dart` — and **never references
`StageTheme`**. It passes unchanged. The fourth surface, the stage display, is pinned by a
**second** test, `stage_display_uses_the_semantic_inks`. So four surfaces are covered by two
tests, not four by one.

That split is the better arrangement and is deliberate: the stage needs only the **semantic
inks** (ok / warn / alert / gold, plus each state's soft tint and border), not the whole
manifest, so pinning it separately keeps the stage test small and keeps colour *values* out of
it entirely — it asserts struct-to-swatch identity, never a hex. That is why repointing the
stage could not disturb the manifest pin.

Before this batch `stage_display_uses_the_semantic_inks` pinned `StageTheme::dark()` to the
**legacy** tokens, so the stage was the one surface rendering `#ef4444` for "on air" while the
console and the controller rendered `#ff4d4d`. Repointing the struct is what makes that test's
own first sentence — "the same colour never means two things across surfaces" — true rather
than aspirational. `git diff` on `src/` moves no colour literal.

## 10. Recommended follow-ups

*Done in this batch (kept for the trail):*

- ~~Ellipsize the Worship next line as Scripture already does~~ — **done**, §4.4 / §7.3.
- ~~Correct the audit's build-order step 2~~ — **done**, the correction is written into
  `DESIGN-2.0-PARITY-AUDIT-stage.md` §8 step 2 and its §2 STG-008/009 rows.

*Open:*

1. `Layer::RadialGradient` in `selahcue-engine`, replacing the 12-band approximation (§4.1).
2. **With the owner** — the timer-only readout: leave it, or let the elastic rule shrink it
   ~10 % for consistency (§4.2). Not started.
3. **With the owner** — the audience palette re-skin (§7.5). Not started; nothing on the
   audience output changed.
4. Resolve audit **Q2** (the stage `muted` ink), which blocks STG-002 and STG-058/059/060.
5. A token batch for STG-001/006/007 — the three stage fills with no `design2` equivalent.
6. Export `raster`'s private `FONT_TO_LINE` so `stage.rs` and its tests stop restating `0.72`.
7. Consider whether the maximum stage text scale should shorten the worship next line as much
   as it now does (§7.3) — the ellipsis is correct, but at 175 % little of the line survives.
