# Design 2.0 parity audit — Stage / Confidence Display

**Surface:** the stage / confidence monitor (FR-037, FR-040), rendered by
`implementation/desktop/crates/selahcue-present/src/stage.rs` through the CPU rasterizer
in `selahcue-engine/src/raster.rs`.

**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1`. All frames read live on 2026-08-23.

**Status:** audit + specification. No implementation file was changed by this document.

**Authority order used throughout**
1. Live Figma (this audit's readings).
2. `docs/product/prds/SelahCue-PRD.md` — FR-059, FR-175, NFR-020 override a frame where they conflict.
3. `docs/design/DESIGN-2.0-HANDOFF.md` (dated 2026-08-01) — **stale**; used only where the live
   frames are silent, and every contradiction is called out.

Vocabulary note: Worship / Scripture / Timer-only are **layout templates**, not light/dark colour
modes (`docs/design/THEME-MODEL-spec.md`). `StageTheme` is the single colour set they all share.

---

## 1. Summary

### 1.1 Headline

The stage display is **structurally right and cosmetically wrong**. Every region the design calls
for exists in the right place — worship header / lyric band / next row / timer footer, scripture
left column + right countdown panel, timer-only giant readout — and the three TIME-UP scopes are
correctly region-scoped per template. What has drifted is almost entirely **type size, ink token,
and shape**: the composer renders its chrome at roughly 60–75 % of the designed type size, uses the
pre-Design-2.0 ink values rather than the `design2` palette the frames are drawn in, draws squares
where the frames draw circles and pills, and drops every letter-spacing value in the design.

Three findings are more than cosmetic:

- **STG-039 — TIME UP pulses.** `time_up_ink()` alternates the TIME-UP ink bright/dim once per
  second. Three separate authorities say it must not: the behaviour-spec frame `375:139` the
  function's own module doc cites ("TIME UP is solid, never flashing"), the console note in
  `563:201`, and PRD **FR-059** ("default is solid-inverted (**static**), not flashing"). It is
  within the FR-175 / WCAG 2.3.1 rate limit, so it is not a safety defect — it is a spec violation
  and it must be opt-in, not the default.
- **STG-077 / STG-078 — NFR-020 is not met at MVP scope.** The PRD requires stage text to support
  a **configurable large size (≥48px-equivalent)** and **high-contrast themes**. Neither exists:
  every size is a hard-coded fraction of frame height with no scale input, and `StageTheme` has
  exactly one constructor (`dark()`). At 1920×1080 thirteen of twenty-three stage text roles render
  **below** 48px-equivalent.
- **STG-038 / STG-065 — the overrun readout is missing everywhere.** Both TIME-UP frames show how far over
  the timer has run ("OVER 0:32", "▲ OVER BY 0:32"). The implementation shows only the words
  "TIME UP". The speaker cannot tell 5 seconds over from 5 minutes over.

### 1.2 Counts

114 elements, badges, pills, dividers, regions and behaviour assertions were given a verdict. A few
rows carry two verdicts (e.g. geometry MATCH + fill DRIFT), so the column below sums to more than 114.

| Verdict | Count | Meaning |
|---|---|---|
| MATCH | 36 | Figma value and implemented value agree (±1px rounding tolerated). |
| DRIFT | 69 | Both exist; the value differs. |
| MISSING | 13 | Figma specifies it; the implementation has no code path. |
| EXTRA | 2 | Implemented but not in any frame. |
| UNSPECIFIED | 5 | The implementation renders a state the frames never draw. |
| A11Y-CONFLICT | 1 | The Figma value itself fails WCAG; do not build the frame as drawn. |

### 1.3 Open questions

Seven, all in §7. The two that block the build order are **Q1** (does TIME UP pulse or not) and
**Q3** (is Design 2.0's dark-red TIME UP intended to replace FR-059's "solid-inverted" default).

### 1.4 Legacy frames — superseded

| Legacy frame | Verdict |
|---|---|
| `13:2` "Output — Stage / Confidence Display" | **Superseded by `373:133`.** Confirmed by reading both: `13:2` puts the clock top-**left**, the timer top-**right** in amber (`SERMON` / `05:42`), and the production message in a full-width amber banner across the bottom. Design 2.0 moves the clock to top-right, the timer into a dedicated bottom band in green, adds the song pill + stanza position to the header, and turns the message into a centred gold-framed card. Nothing in `13:2` survives. Do not build from it. |
| `13:15` "Output — TIME UP (solid-inverted, seizure-safe)" | **Superseded by `374:166` — but with a caveat that needs an owner decision.** `13:15` is literally solid-inverted: a full-bleed solid `#C7212B` field with white `TIME UP` (measured 5.71:1). `374:166` is the opposite polarity: a near-black radial vignette with red `#FF4D4D` ink (5.83:1 at the gradient midpoint). Both are static and both clear AA-large comfortably, so the swap is safe — but PRD **FR-059** names the default as "solid-inverted", which describes `13:15`, not `374:166`. See **Q3**. |

Both legacy frames still carry one thing Design 2.0 kept: `13:15`'s caption reads
"static high-contrast (no flashing) · WCAG 2.3.1 safe", which is the same rule `375:139` restates.
That rule has survived every revision and the implementation contradicts it (STG-039).

---

## 2. Cross-cutting findings

These apply to every frame; they are listed once here and referenced rather than repeated in each
per-frame table.

| # | Finding | Figma | Implemented | Verdict | Severity |
|---|---|---|---|---|---|
| STG-001 | **Stage background ink** | `#08090d` on all six output frames (`373:133`, `373:159`, `374:128`, `374:151`, `374:166` gradient edge stop, `375:128`) | `stage.rs:87` `background: Rgba::rgb(6, 8, 14)` = `#06080e` | DRIFT | Low |
| STG-002 | **Muted / secondary ink** | Two inks, used distinctly: `#a7aebe` (`d2TextSecondary`) for the wall clock and the timer-only date; `#6b7383` (`d2TextMuted`) for labels, NEXT, captions | `stage.rs:89` a single `muted: Rgba::rgb(0x8a, 0x93, 0xa3)` = `#8a93a3`, plus `theme.text` (pure white) for the clock | DRIFT | Medium |
| STG-003 | **Timer "on track" ink** | `#35c08a` (`design2::PREVIEW`) — the dot in `373:151`, the worship readout `373:154`, the scripture pill + readout `374:143`/`374:145`, the timer-only readout `374:157` | `stage.rs:95` `timer_ok: crate::tokens::PREVIEW.ink` = `#2bb673` (the **legacy** canonical ink, not `design2::PREVIEW`) | DRIFT | Medium |
| STG-004 | **TIME-UP / alert ink** | `#ff4d4d` (`design2::LIVE`) throughout `373:159` and `374:166` | `stage.rs:97` `timer_alert: crate::tokens::LIVE.ink` = `#ef4444` (legacy) | DRIFT | Medium |
| STG-005 | **Warning ink** | Not drawn on any stage frame (no warn-state stage frame exists) | `stage.rs:96` `timer_warn: crate::tokens::WARN.ink` = `#f2b53c` (legacy). Design 2.0's warn is `#f5a524` | UNSPECIFIED | Low |
| STG-006 | **Panel / raised-surface fill** | `#0c0e14` — the worship timer band `373:149` and the scripture countdown panel `374:140` | `stage.rs:91` `panel: Rgba::rgb(0x10, 0x14, 0x1e)` = `#10141e` | DRIFT | Low |
| STG-007 | **Chip / pill fill** | `#12141c` — the song pill `373:136`, both NEXT chips `373:146` / `374:137` | `stage.rs:92` `track: Rgba::rgb(30, 34, 44)` = `#1e222c` | DRIFT | Low |
| STG-008 | **Hairline borders** | `1px #262a34` on the song pill, the worship timer band, and the scripture countdown panel; `1px #1c3a2e` on the ON TIME pill; `2px #5a2327` on the worship TIME-UP band; `1.5px #5a2327` on the timer-only OVER pill | No border is drawn anywhere. `fill()` (`stage.rs:285-293`) is the only rect primitive *`stage.rs` uses*, and it has no stroke — but see the correction below: `Layer::Shape` provides one | MISSING | Medium |
| STG-009 | **Corner radii** | `999px` (song pill, ON TIME pill, both OVER pills), `7px` (both NEXT chips), `18px` (message card), `14px` (frame — decorative, not applicable to a full-bleed output) | No radius anywhere. `Layer::Fill` takes a `Rect` only — but `Layer::Shape` carries `corner_px`; see the correction below | MISSING | Medium |

> **Correction (2026-08-23).** STG-008/009/010 were audited as needing a new engine primitive.
> They do not: **`Layer::Shape`** (`selahcue-engine/src/scene.rs:161`) already provides
> `Ellipse` / `RoundedRect` / `Triangle` with `fill`, `border`, `border_px` and `corner_px`,
> rasterized by `raster.rs`'s `draw_shape`. All three were closed with no engine change. See
> §8 step 2.
| STG-010 | **Status dots are circles** | Circles: `9px` song dot `373:137`, `11px` timer dot `373:151`/`373:177`, `9px` ON TIME dot `374:142`, `6px` footer separator dot `374:160` | `stage.rs:359-361` `dot()` draws a **square** `Layer::Fill` | DRIFT | Medium |
| STG-011 | **Letter-spacing is dropped** | Nine distinct tracking values across the frames: `+1px` (NEXT labels, SERVICE TIMER, scripture reference, TIME LEFT), `+1.5px` (message chip, timer-up header), `+2px` (STAGE·SCRIPTURE, SERVICE TIMER header, timer-up TIME UP), `+4px` (timer-only SERMON), `-2px` (scripture readout), `-4px` (timer-only readout) | `stage.rs:319` every stage line hard-codes `letter_spacing_px: 0`. `autofit_layers` is called with a trailing `0` at `stage.rs:396` and `stage.rs:1036` | DRIFT | Medium |
| STG-012 | **Font weight is uniformly 700** | The frames use three weights: `Bold` (700) for labels/readouts, `Semi_Bold` (600) for the wall clock, `Medium` (500) for the stanza position, both next-lines, `· Sermon`, the scripture sub-caption and the timer-only date | `stage.rs:305-322` `line()` hard-codes `weight: 700` for every chrome run; `fit_lines` callers all pass `700` | DRIFT | Medium |
| STG-013 | **Line-height** | Figma `leading-[normal]` for chrome (Inter normal ≈ 1.21 — confirmed by `373:143`: a 56px run occupies a 68px line box) and an explicit `1.24` on the scripture verse `374:135` | `stage.rs:177` `STAGE_LINE_HEIGHT: f64 = 1.3` for every auto-fit region | DRIFT | Low |
| STG-014 | **Design tokens are not bound as Figma variables** | `get_variable_defs` on `373:133` returns `{}` — every colour in these frames is a raw hex, not a bound variable | n/a | *observation* | Low |
| STG-015 | **`TimerView::progress` is never drawn** | No stage frame shows a progress bar. `StageTheme::track`'s doc comment (`stage.rs:67`) says "Dim track behind the timer progress bar" — that bar does not exist | `stage.rs:122` `progress` is computed at `stage.rs:149-154` and read by no template (verified: no other reference in the file) | EXTRA | Low |
| STG-016 | **Per-output region toggles** | `DESIGN-2.0-HANDOFF.md` §5.11 requires per-output toggles for Now / Next / Clock / Timer+TIME-UP / Stage message / Theme background, configured in Screens & Outputs `327:124`. The region matrix in `375:181`–`375:227` enumerates exactly those six regions | `StageDisplay` (`stage.rs:1080-1088`) and `StageContext` (`stage.rs:226-233`) carry no region flags; `compose_stage` has no way to suppress a region | MISSING | Medium |

**Note on STG-011 for whoever implements it.** `Layer::Text` already carries
`TextStyle::letter_spacing_px` and `raster.rs` honours it when drawing (`raster.rs:937`,
`raster.rs:1292`, `raster.rs:1304`). The **measurement** path does not:
`raster::measure_line_width(text, px, font, weight)` takes no spacing argument, and
`selahcue-present/src/measure.rs`'s memo `Key` (`measure.rs:23`) is `{text, cell, font, weight}`.
So introducing tracking without extending both will make `autofit_layers` shrink-to-fit against
widths that no longer match what is drawn — silently, and cached. See §8, step 0.

---

## 3. Per-frame audit

Geometry is quoted at each frame's native resolution. Implemented pixel values are the result of
evaluating the composer's fractions at **1000×563** (the design size), so the two columns are
directly comparable. `em` is the rendered glyph size: `stage.rs`'s `line()` passes a **line-box
height**, and both the draw path (`raster.rs:1322-1323`) and the measure path (`raster.rs:1253-1254`)
derive `font_size = line_h × FONT_TO_LINE` where `FONT_TO_LINE = 0.72` (`raster.rs:47`).

> `raster.rs` has uncommitted work from a concurrent session, so its line numbers may shift. The
> quoted values — `FONT_TO_LINE = 0.72`, `MAX_DIMENSION = 8192`, `STAGE_FONT = "Inter"` — are the
> load-bearing facts; re-grep rather than trusting the line numbers if they no longer resolve.

### 3.1 Frame `373:133` — Worship theme, running (1000×563)

Screenshot read at 1000×563. Structure: header band 89px, flexible body, timer band 107px.

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| — | Frame background | `#08090d` | see STG-001 | DRIFT | Low |
| — | Frame radius `14px` (`373:133`) | `rounded-[14px]` | not drawn — full-bleed output, correctly ignored | EXTRA (Figma artifact) | — |
| — | Header band `373:134` | `1000×89`, no fill, `pt 28 / pb 20 / px 40` | no band object; children positioned by fraction | MATCH (no fill drawn) | — |
| STG-017 | Song pill `373:136` | `x 40 y 28 · 209×41`; fill `#12141c`; border `1px #262a34`; radius `999`; `pl 13 pr 14 py 7`, gap `8` | `:486` `fill(frame, 40, 29, 231, 37, theme.track)` → `x 40 y 29 · 231×37`, fill `#1e222c`, no border, no radius | DRIFT | Medium |
| STG-018 | Song dot `373:137` | circle `9×9` at abs `(53, 44)`, fill **`#7E6EFF`** (`design2::PRIMARY_HOVER`) — asset `8e5c587f`, verified `<circle … fill="#7E6EFF"/>` | `:365` `const SONG_ACCENT: Rgba = Rgba::rgb(0x8b, 0x5c, 0xf6)` = `#8b5cf6`; `:487-493` square `8×8` at `(53, 43)` | DRIFT | Medium |
| STG-019 | Song title `373:138` | "Amazing Grace" · Inter **Bold** `22px` · `#f4f6fb` · abs `x 70 y 35` | `:494-503` line-box `24` → em **`17.3px`**; colour `theme.text` = `#ffffff`; `x 70` | DRIFT (size −21 %, ink) | Medium |
| STG-020 | Stanza position `373:139` | "Verse 2 of 4" · Inter **Medium (500)** `20px` · `#6b7383` · abs `x 263 y 36.5` | `:505-517` line-box `22` → em **`15.8px`**; weight `700`; colour `theme.muted` `#8a93a3`; `x 287` (**+24px**) | DRIFT | Medium |
| STG-021 | Header wall clock `373:140` | "10:42 AM" · Inter **Semi Bold (600)** `30px` · `#a7aebe` · right-aligned, right edge `960`, `y 30.5` | `header_clock` `:427-446` line-box `34` → em **`24.5px`**; weight `700`; colour `theme.text` `#ffffff`; right edge `960`; `y 28` | DRIFT (size, weight, ink) | Medium |
| STG-022 | Lyric band `373:142` | block `x 48 y 131.5 · 904×212`; two runs, Inter Bold **`56px`**, `#ffffff`, centre, inter-run gap `8px`, line box `68px` (≈1.21) | `:528-542` `fit_lines` region `Rect(50, 106, 900, 253)`, `max_cell 95` → max em **`68.4px`**, line-height `1.3`, `TextAlign::Center`, `VAlign::Middle`, `theme.text`, weight `700` | DRIFT (cap 22 % over; region 25px high, 41px tall) | Medium |
| — | Lyric colour | `#ffffff` | `theme.text` = `Rgba::WHITE` | MATCH | — |
| STG-023 | NEXT chip `373:146` | `x 214 y 381 · 70×29`; fill `#12141c`; radius `7`; `pl 11 pr 12 py 5` | `chip()` `:339-356` at `chip_px 16` → `55×24`, fill `theme.track` `#1e222c`, no radius; group centred at `y 382` | DRIFT | Low |
| STG-024 | NEXT label `373:147` | "NEXT" · Inter Bold `16px` · `#6b7383` · tracking **`+1px`** | `:345-354` em **`11.5px`**; colour `theme.muted`; tracking `0` | DRIFT | Medium |
| STG-025 | Next line `373:148` | "I once was lost, but now am found" · Inter **Medium** `30px` · `#6b7383` · abs `x 298`, vertically centred on the chip | `:569-578` line-box `19` → em **`13.7px`** (**46 % of design**); weight `700`; colour `theme.muted` | DRIFT | **High** |
| STG-026 | Timer band `373:149` | `y 456 · 1000×107`; fill `#0c0e14`; border `1px #262a34`; `px 40 py 22` | `:583-593` `band_h = 0.19·h = 106`, `band_y = 457`, fill `theme.panel` `#10141e`, no border | DRIFT (fill + border; geometry within 1px) | Low |
| STG-027 | Timer state dot `373:151` | circle `11×11` at `(40, 504)`, fill `#35C08A` (asset `e7863b33`, verified) | `:603-610` square `12×12` at `(40, 505)`, colour `t.color(theme)` → `timer_ok` `#2bb673` | DRIFT | Medium |
| STG-028 | "SERVICE TIMER" `373:152` | Inter Bold `20px` · `#a7aebe` · tracking **`+1px`** · abs `x 63` | `:611-620` line-box `23` → em **`16.6px`**; colour `theme.muted` `#8a93a3`; tracking `0`; `x 64` | DRIFT (ink family: design uses *secondary*, impl uses *muted*) | Medium |
| STG-029 | Segment suffix `373:153` | "· Sermon" · Inter Medium `18px` · `#6b7383` · abs `x 241` | `NOT FOUND` — the worship footer has no segment-name run | MISSING | Medium |
| STG-030 | Timer readout `373:154` | "12:45" · Inter Bold **`52px`** · `#35c08a` · right-aligned to `x 960`, `y 478` | `:621-637` line-box `44` → em **`31.7px`** (**61 % of design**); right edge `960`; colour `#2bb673` | DRIFT | **High** |
| — | Right margin | `40px` (both header clock and readout end at `x 960`) | `0.04·w = 40`; `header_clock` right edge `0.96·w = 960` | MATCH | — |
| — | Left margin | `40px` | `0.04·w = 40` | MATCH | — |
| — | Body horizontal inset | `px 48` on `373:141` | `0.05·w = 50` (lyric), `0.048·w = 48` (scripture) | DRIFT (2px) — folded into STG-022 | Low |

### 3.2 Frame `373:159` — Worship theme, TIME UP (1000×563)

Only the timer band changes. Header (`373:160`–`373:166`), lyric band (`373:167`–`373:170`) and the
NEXT row (`373:171`–`373:174`) are byte-identical to `373:133` — **confirmed by comparing both
metadata trees**: same sizes, same offsets, same text. The 7px vertical difference between the two
frames' body heights (367 vs 374) is a consequence of the band shrinking from 107 to 100, not a
designed change.

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| — | Region scope: only the timer band flips | header + lyric + NEXT unchanged | `:583-593` fills only `Rect(0, band_y, w, band_h)`; nothing else is conditioned on `up` | **MATCH** | — |
| STG-031 | TIME-UP band fill | `#1c0c0e` | `:592` `theme.alert_wash` = `#2a1416` (`:98`) | DRIFT | Low |
| STG-032 | TIME-UP band border | `2px #5a2327` | none | MISSING | Medium |
| STG-033 | TIME-UP band height | `100px` (`y 463`) — content-driven, 7px shorter than the running band | `0.19·h = 106`, unchanged from running | DRIFT | Low |
| STG-034 | State dot at TIME UP | circle `11×11` `#FF4D4D` (asset `0e1439bb`, verified) | `:596-610` square, `theme.timer_alert` `#ef4444` | DRIFT | Medium |
| STG-035 | "SERVICE TIMER" flips to alert ink | `#ff4d4d` (was `#a7aebe`) | `:618` passes `theme.muted` **unconditionally** — the caption does not flip | DRIFT | **High** |
| STG-036 | "· Sermon" at TIME UP | stays `#6b7383` | not implemented (see STG-029) | MISSING | Medium |
| STG-037 | "TIME UP" word `373:181` | Inter Bold **`46px`** · `#ff4d4d` · left edge of a right-aligned group at `x 617`, `y 485` | `:628-637` line-box `44` → em **`31.7px`**, right-aligned to `x 960`, ink from `time_up_ink()` | DRIFT | **High** |
| STG-038 | Overrun pill `373:182` | `x 819 y 470.5 · 141×41`; fill `#2a1416`; border `1px #5a2327`; radius `999`; `pl 12 pr 13 py 7`; label "OVER 0:32" Inter Bold `22px` `#ff4d4d` | `NOT FOUND` — no overrun readout in any template | MISSING | **High** |
| STG-039 | TIME UP is **static** | `375:230` and `563:197` both state: "TIME UP is solid, never flashing (WCAG 2.3.1)". `13:15`'s caption agrees. PRD FR-059: "default is solid-inverted (**static**), not flashing" | `:416-422` `time_up_ink()` returns `timer_alert.lerp(WHITE, 350)` on even elapsed seconds and `timer_alert` on odd — a 0.5 Hz bright/dim alternation of the TIME-UP word, applied in all three templates (`:624`, `:816`, `:927`) | DRIFT — **spec violation** | **High** |

**On STG-039 and flash safety.** The implementation is *rate-compliant*: FR-175 bounds flashing to
≤3 general flashes/sec and ≤3 red flashes/sec within the small-safe area (WCAG 2.3.1); a 0.5 Hz
alternation between `#ef4444` and `#f47e7e` is well under that on both counts and the area is small.
So this is **not** a seizure-safety defect and should not be raised as one. It is a plain
contradiction of the stated design behaviour and of FR-059's *default*. FR-059 does allow a
flashing TIME-UP state — but as a **configured** option, not the default, and the current code has
no way to turn it off.

### 3.3 Frame `374:128` — Scripture theme, running (1000×563)

Structure: header band 80px (`pt 28 / pb 18`), body split at `x 680` into a flexible left column
and a fixed 320px countdown panel.

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| STG-040 | Screen label `374:130` | "STAGE · SCRIPTURE" · Inter Bold `20px` · `#6b7383` · tracking **`+2px`** · abs `x 40 y 33` | `:658-667` line-box `28` → em **`20.2px`** (size MATCH); `x = 0.048·w = 48` (**+8**); `y 32`; colour `theme.muted` `#8a93a3`; tracking `0` | DRIFT (x, ink, tracking; **size matches**) | Medium |
| STG-041 | Header clock `374:131` | Inter Semi Bold `28px` · `#a7aebe` · right edge `960`, `y 28` | shared `header_clock` — see STG-021 (em `24.5`, white, weight 700) | DRIFT | Medium |
| — | Left column bounds | `x 0…680`, content inset `pl 48 pr 36` → content `x 48…644` | `hx = 0.048·w = 48`, `left_w = 0.60·w = 600` → content `x 48…648` | MATCH (left), DRIFT 4px (right) | Low |
| STG-042 | Reference `374:134` | "ISAIAH 61:5 · KJV" · Inter Bold **`30px`** · **`#f2b84b`** · tracking `+1px` · abs `x 48 y 103` | `:671-682` line-box `34` → em **`24.5px`**; colour `theme.accent` = `Rgba::rgb(0xf2,0xb8,0x4b)` (`:90`) — **hex MATCH**; `y 104`; uppercased via `to_uppercase()`; tracking `0` | DRIFT (size, tracking); **ink + position MATCH** | Medium |
| STG-043 | Verse body `374:135` | Inter Bold **`48px`** · `#ffffff` · leading **`1.24`** · left-aligned, top · `x 48 y 159 · 596×300` | `:692-706` `Rect(48, 157, 600, 281)`, `max_cell = 0.115·h = 64` → max em **`46.1px`**, line-height `1.3`, `TextAlign::Left`, `VAlign::Top`, `theme.text`, weight `700` | DRIFT (cap 46.1 vs 48 — see NFR-020 note below; leading) | Medium |
| STG-044 | NEXT chip `374:137` | `x 48 y 480.5 · 67×28`; fill `#12141c`; radius `7`; label Inter Bold `15px` `#6b7383` tracking `+1px` | `:715` `chip()` at `chip_px 15` → `51×22` at `(48, 478)`, fill `#1e222c`, no radius, em `10.8`, tracking `0` | DRIFT | Low |
| STG-045 | Next line `374:139` | "Isaiah 61:6 · But ye shall be named the Priests…" · Inter **Medium** `26px` · `#6b7383` · abs `x 128`; **hard-clipped at the panel edge `x 680`** — the design shows the glyphs cut mid-word, with no ellipsis added by the renderer (the literal `…` is part of the authored string) | `:719-728` em **`11.5px`**, weight 700, colour `theme.muted`; width bounded by `ellipsize()` (`:841-856`) which appends ASCII `"..."` | DRIFT (size; clip-vs-ellipsize) | Medium |
| — | Ellipsis glyph | design string contains `…` (U+2026) | `:840` explicitly uses ASCII dots because "the bundled Latin face has no `…` glyph" | MATCH (correct engineering call) | — |
| STG-046 | Countdown panel `374:140` | `x 680 y 80 · 320×483`; fill `#0c0e14`; border `1px #262a34`; `px 30`; centred column, gap `12` | `:732-745` `x = 0.68·w = 680`, `y = 0.142·h = 79`, `320×484`; fill `theme.panel` `#10141e`; no border | **Geometry MATCH** (±1px); fill + border DRIFT | Medium |
| STG-047 | Status pill `374:141` | `x 792.5 y 213 · 95×28`; fill **`#10231c`** (`preview-soft`); border `1px #1c3a2e` (`preview-border`); radius `999`; `pl 11 pr 12 py 6`, gap `8` | `:762-771` computed `96×22` at `(792, 208)`; fill `theme.track` `#1e222c`; no border, no radius | Width + x MATCH; height, y, fill, border DRIFT | Medium |
| STG-048 | Pill dot `374:142` | circle `9×9` `#35c08a` | `:772-778` square `7×7`, colour `#2bb673` | DRIFT | Medium |
| STG-049 | Pill label `374:143` | "ON TIME" · Inter Bold `13px` · `#35c08a` | `:779-788` em **`10.8px`**, colour `#2bb673` | DRIFT | Low |
| STG-050 | Pill states beyond ON TIME | not drawn — only the on-time state exists in Figma | `:748-754` adds `"HURRY"` (`timer_warn`) and `"TIME UP"` (`timer_alert`) | UNSPECIFIED — see **Q4** | Medium |
| STG-051 | "TIME LEFT" `374:144` | Inter Bold `15px` · `#6b7383` · tracking `+1px` · centred, `y 253` | `:791-800` em **`11.5px`**, centred in panel, `y 253` (**MATCH**), colour `theme.muted`, tracking `0` | y MATCH; size + tracking DRIFT | Low |
| — | Big readout `374:145` | "12:45" · Inter Bold **`96px`** · `#35c08a` · tracking **`-2px`** · centred, `y 283` | `:801-821` line-box `123` → em **`88.6px`**, `y 281`, colour `#2bb673`, tracking `0` | DRIFT (size −8 %, tracking, ink) | Medium |
| STG-052 | Panel sub-caption `374:146` | "Sermon · ends 10:55" · Inter **Medium** `16px` · `#6b7383` · centred, `y 411` | `NOT FOUND` — the panel has no fourth row | MISSING | Medium |
| STG-053 | Scripture TIME-UP appearance | **no Figma frame exists** for Scripture at TIME UP | `:744` panel fills with `alert_wash`; `:748-749` pill becomes `"TIME UP"`; `:803-807` readout drops to `0.11·h` (em `43.9`) and reads `"TIME UP"` | UNSPECIFIED — see **Q5** | Medium |

### 3.4 Frame `374:151` — Timer-only theme, running (1000×563)

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| STG-054 | Header label `374:153` | "SERVICE TIMER" · Inter Bold `20px` · `#6b7383` · tracking **`+2px`** · abs `x 40 y 33` | `:878-887` `x 40` (MATCH), `y 29` (**−4**), line-box `28` → em **`20.2px`** (MATCH), colour `theme.muted`, tracking `0` | size + x MATCH; y, ink, tracking DRIFT | Low |
| STG-055 | Header clock `374:154` | Inter Semi Bold `28px` · `#a7aebe` · right edge `960`, `y 28` | `:889-900` — a **separate** code path from `header_clock`: `y = 0.045·h = 25`, line-box `38` → em **`27.4px`** (near-match), colour `theme.text` `#ffffff`, weight `700` | size near-MATCH; y, ink, weight DRIFT | Medium |
| STG-056 | Segment label `374:156` | "SERMON" · Inter Bold **`26px`** · `#6b7383` · tracking **`+4px`** · centred, `y 163` | `:904-915` `y 152` (**−11**), line-box `33` → em **`23.8px`**, colour `theme.muted`, tracking `0`, **not uppercased** (renders the raw slide title) | DRIFT | Medium |
| STG-057 | Giant readout `374:157` | "12:45" · Inter Bold **`190px`** · `#35c08a` · tracking **`-4px`** · centred, `y 200` | `:931-942` `y 168` (**−32**), line-box `275` → em **`198px`** (+4 %), colour `t.color(theme)` `#2bb673`, tracking `0` | DRIFT (position, tracking, ink) | Medium |
| STG-058 | Footer date `374:159` | "Sunday · August 3, 2026" · Inter **Medium** `30px` · **`#a7aebe`** · left of the row, abs `x 238.5 y 444` | part of a single centred string, see STG-060 | DRIFT | Medium |
| STG-059 | Footer separator `374:160` | circle `6×6` at `(605.5, 459)`, fill unspecified (asset `026af74a` not fetched — inferred `#6b7383` from the render) | rendered as a `·` character inside the joined string | DRIFT | Low |
| STG-060 | Footer time `374:161` | "10:42 AM" · Inter **Medium** `30px` · **`#6b7383`** (a *different* ink from the date) · abs `x 625.5` | `:958-974` one run: `format!("{} · {}", date, time)`, `y 450`, line-box `40` → em **`28.8px`** (near-match), colour `theme.text` `#ffffff`, weight `700`, centred | DRIFT — the design's **two-tone** treatment collapses to one white run | Medium |
| STG-061 | Idle state (no timer) | not drawn | `:943-954` renders `"--:--"` in `theme.muted` at the running geometry | UNSPECIFIED — see **Q6** | Low |

### 3.5 Frame `374:166` — Timer-only theme, TIME UP, full screen (1000×563)

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| STG-062 | Full-screen background | **elliptical radial gradient**, `gradientUnits="userSpaceOnUse"`, centre `(500, 281.5)`, `rx 500 · ry 281.5`; stops `#2A0E12` @0 → `#190C10` @0.5 → `#08090D` @1. Pixel-verified from the render: `(500,281)` region is the darkest red core, `(5,5)` = `#07080c` | `:872-875` `fill(frame, 0, 0, w, h, theme.alert_wash)` — a **flat** `#2a1416` over the whole frame | DRIFT | Medium |
| STG-063 | Header left slot | shows the **segment name** "SERMON" · Inter Bold `20px` `#6b7383` tracking `+1.5px` | `:878-887` still renders the fixed literal `"SERVICE TIMER"` at TIME UP | DRIFT | Medium |
| — | Header clock | "10:56 AM" · same style as running | same path — see STG-055 | DRIFT | Medium |
| STG-064 | "TIME UP" word `374:171` | Inter Bold **`130px`** · `#ff4d4d` · tracking **`+2px`** · centred, `y 182.5` (`543×157`) | `:919-930` `y 202` (**+20**), line-box `191` → em **`137.5px`** (+6 %), ink from `time_up_ink()` (pulsing — STG-039), tracking `0` | DRIFT | Medium |
| STG-065 | Overrun pill `374:172` | `x 371 y 359.5 · 258×54`; fill `#2a1416`; border **`1.5px #5a2327`**; radius `999`; `pl 18 pr 20 py 10`, gap `10`; `▲` Inter Bold `16px` `#ff4d4d` + "OVER BY 0:32" Inter Bold `28px` `#ff4d4d` | `NOT FOUND` | MISSING | **High** |
| STG-066 | Date line `374:175` | "Sunday · August 3, 2026" · Inter **Medium** `22px` · `#6b7383` · centred, `y 433.5` — **date only; the time-of-day is dropped at TIME UP** | `:958-974` unchanged from running: renders `"{date} · {time}"` in `theme.text` white at em `28.8`, `y 450` | DRIFT | Medium |
| STG-067 | Segment label placement at TIME UP | moved into the header; **not** repeated in the body | `:904-915` still draws the segment label at `y 152` in the body, in addition to the header's fixed label — the design's single label becomes two runs | DRIFT | Medium |
| — | TIME UP is static | no animation | pulsing — STG-039 | DRIFT | High |

### 3.6 Frame `375:128` — Production message overlay (1000×563)

Identified: this is the **stage production-message overlay**, drawn over a Worship-template scene.
It is the frame `DESIGN-2.0-HANDOFF.md` §5.11 cites as "Stage message". Its header is a *simplified*
single-line treatment (`AMAZING GRACE · V2`) rather than the pill-based header of `373:133` — see
**Q7**.

| # | Element | Figma spec | Implemented (`stage.rs`) | Verdict | Severity |
|---|---|---|---|---|---|
| STG-068 | Scrim / de-emphasis mechanism | **No scrim.** The frame background stays `#08090d`; the content behind is de-emphasised by *re-rendering it*: the lyric `375:133` drops to Inter Bold **`40px`** in **`#6b7383` at `opacity 0.35`** (composites to ≈`#2a2d33`, 1.44:1 on the field — deliberately unreadable) | `push_message_overlay` `:980` `fill(frame, 0, 0, w, h, Rgba::new(4, 6, 12, 190))` — a translucent black scrim at α≈74.5 % over the already-composed scene | DRIFT (different mechanism) — see **Q2** | Medium |
| STG-069 | Simplified header `375:130` | "AMAZING GRACE · V2" · Inter Bold `20px` · `#6b7383` · tracking `+1.5px` · `x 40 y 33` | the full worship header (pill + violet dot + stanza position) is composed first and then sits under the scrim | DRIFT / UNSPECIFIED | Medium |
| — | Header clock `375:131` | Inter Semi Bold `28px` `#a7aebe`, right edge `960` | drawn, then scrimmed | DRIFT (see STG-021) | Low |
| STG-070 | Message card `375:134` | `x 142 y 278.5 · 716×160`; fill **`#241c08`**; border **`2px #f5a524`**; radius `18`; `pt 28 pb 30 px 52`, gap `12` | `:982-995` outer gold rect `(100, 191, 800, 168)` in `theme.accent` `#f2b84b`, then an inner rect inset by `border = max(0.004·w, 2) = 4` filled with `theme.panel` `#10141e` | DRIFT (x −42, y −87.5, w +84, border 4 vs 2, no radius, both fills) | Medium |
| STG-071 | Chip row `375:135` | fill **`#ffffff`** (pixel-verified `(255,255,255)` at `(360,318)`); gap `9`; `⚠` Inter Bold `18px` `#f5a524` + "MESSAGE FROM PRODUCTION" Inter Bold `18px` `#f5a524` tracking `+1.5px`; `x 333.5 y 306.5 · 333×22` | `:998-1013` chip `237×24` at `(381, 214)`, fill `theme.accent` (gold `#f2b84b`), label in `theme.background` (`#06080e`) at em `11.5`; **no `⚠` glyph** | **A11Y-CONFLICT** + DRIFT + MISSING glyph | **High** |
| STG-072 | Message body `375:138` | "WRAP UP · 2 MIN LEFT" · Inter Bold **`56px`** · `#ffffff` · single line, `x 194 y 340.5 · 612×68` | `:1018-1039` `autofit_layers` into `Rect(148, 258, 704, 80)`, `max_cell = 80` → max em **`57.6px`**, centred, `VAlign::Top`, `theme.text`, weight `700`, line-height `1.3` | max size near-MATCH; geometry DRIFT | Low |
| — | Message length bound | `563:194` note: "Bounded to 120 chars" | `:54` `pub const MAX_STAGE_MESSAGE_LEN: usize = 120`; enforced at `:1125` | **MATCH** | — |
| — | Blank message clears the overlay | `563:194`: "Clear (or a blank message) removes it" | `:1120-1127` trims and maps empty → `None`; `:274-279` skips the overlay for an empty/whitespace message | **MATCH** | — |
| — | Overlay is stage-only | `563:197`, `375:230` | `push_message_overlay` is reachable only from `compose_stage`; the audience path is `compose_slide` | **MATCH** | — |

### 3.7 Frame `375:139` — Themes & TIME-UP behaviour spec (720×586)

This is the frame `stage.rs:19` cites as "Figma 375-139". It is a specification card, not an output
frame, so its own typography is console styling and is out of scope; what is audited is the
**behaviour it asserts**.

| # | Assertion | Figma | Implemented | Verdict | Severity |
|---|---|---|---|---|---|
| — | Worship TIME UP = "timer region only" (`375:151-152`) | badge `#f5a524` on `#241c08` | `:583-593` fills only the footer band | **MATCH** | — |
| STG-073 | Scripture TIME UP = "**timer region only**" (`375:161-162`) | | `:738-745` fills only the right countdown **panel** | DRIFT vs this frame — but **MATCH** vs `563:156` ("panel region") and vs `DESIGN-2.0-HANDOFF` §5.11. `375:139` looks like copy-paste from the Worship row. See **Q1** | Low |
| — | Timer-only TIME UP = "full screen" (`375:171-172`) | badge `#ff4d4d` on `#2a1416` | `:872-875` fills the whole frame | **MATCH** | — |
| — | Region matrix: Now = audience ✓ / stage ✓ | `375:183-187` | both composers render current content | **MATCH** | — |
| — | Next = audience — / stage ✓ | `375:191-195` | next line exists only in `compose_worship` / `compose_scripture` | **MATCH** | — |
| — | Clock = audience — / stage ✓ | `375:199-203` | `header_clock` is stage-only | **MATCH** | — |
| — | Timer / TIME UP = audience — / stage ✓ | `375:207-211` | timer regions are stage-only | **MATCH** | — |
| — | Stage message = audience — / stage ✓ | `375:215-219` | `push_message_overlay` is stage-only | **MATCH** | — |
| — | Theme background = audience ✓ / stage — | `375:223-227` | `compose_stage` always paints `StageTheme::background`; it never applies a slide theme's background | **MATCH** | — |
| — | Per-region toggles | the six regions above are the same six the handoff requires as per-output toggles | not implemented | MISSING — STG-016 | Medium |
| — | "TIME UP is solid, never flashing (WCAG 2.3.1)" (`375:230`) | | `time_up_ink()` pulses | DRIFT — STG-039 | **High** |
| STG-074 | Template identity colours (`375:145`–`375:166`) | Worship `♪` `#7e6eff` on `#201f3a`; Scripture `✦` `#f2b84b` on `#2a2415`; Timer-only `⏱` `#38bdf8` on `#10222b` | only the Worship violet reaches the stage output, as the song dot — and at the wrong hex (STG-018). Scripture's gold **does** match (`theme.accent`) | partial DRIFT | Low |

### 3.8 Frame `563:201` — Live Console › Service Timer › Stage — output half only

The console controls (segmented `Timer | Stage`, the theme cards, the preset chips, the composer
field, Send / Clear) belong to the peer session. What is audited here is what those controls **do
to the rendered monitor**, plus the frame's own Notes column.

| # | Assertion | Figma | Implemented | Verdict | Severity |
|---|---|---|---|---|---|
| — | Wire command `set_stage_template(worship\|scripture\|timer-only)` (`563:191`) | | `stage.rs:34-40` `as_tag()` returns exactly `"worship"` / `"scripture"` / `"timer-only"`; `selahcue-lan/src/protocol.rs:290` `SetStageTemplate { template: String }`; `selahcue-app/src/operator.rs:532` | **MATCH** | — |
| — | Unknown tag must not break the output | implied | `stage.rs:43-49` `from_tag()` falls back to `Worship`, never panics — correct for untrusted LAN input | **MATCH** | — |
| — | Wire command `set_stage_message(text)` (`563:194`) | | `protocol.rs:294` `SetStageMessage { text: String }`; `operator.rs:539`; `stage.rs:1120` | **MATCH** | — |
| — | "Send overlays a **gold-framed** note on the confidence monitor" (`563:194`) | | `stage.rs:987` frames the card in `theme.accent` (gold) | **MATCH** (hex differs — STG-070) | — |
| — | "Bounded to 120 chars" (`563:194`) | | `MAX_STAGE_MESSAGE_LEN = 120` | **MATCH** | — |
| — | Worship TIME UP = "timer region" (`563:147`) | | footer band only | **MATCH** | — |
| — | Scripture TIME UP = "**panel region**" (`563:156`) | | panel only | **MATCH** — this frame, not `375:139`, matches the code | — |
| — | Timer-only TIME UP = "full screen" (`563:165`) | | whole frame | **MATCH** | — |
| — | "The message + Next + clock + timer are STAGE-ONLY" (`563:197`) | | see §3.7 region matrix | **MATCH** | — |
| — | "TIME UP is solid, never flashing" (`563:197`) | | pulses | DRIFT — STG-039 | **High** |
| STG-075 | Preset message payloads (`563:169`, `563:171`, `563:173`, `563:175`) | `WRAP UP · 2 MIN LEFT`, `SLOW DOWN`, `WRAP UP NOW`, `GREAT JOB` — all ≤ 20 chars, all uppercase | the monitor renders whatever string arrives; all four fit the overlay's auto-fit region at max size without shrinking | **MATCH** (no output-side work needed) | — |
| STG-076 | Token list (`563:200`) | "surface `#14161d` · card `#1c1f28` · chip `#0f1116` · border `#262a34` · primary `#6e5cf0` · gold `#f2b84b` · green `#35c08a` · red `#ff4d4d` · muted `#6b7383`" | of these, only `gold #f2b84b` is present in `StageTheme::dark()`. `green`, `red`, `muted`, `border`, `chip` all differ (STG-002/003/004/007/008) | DRIFT | Medium |

---

## 4. TIME UP behaviour matrix

One row per template. "Flips" = the region whose fill changes; everything outside it is
byte-identical to the running state.

| Template | Region that flips | Running fill → TIME-UP fill (Figma) | Running fill → TIME-UP fill (implemented) | Ink on the flipped region | Duration / transition | Static? |
|---|---|---|---|---|---|---|
| **Worship** (`373:133` → `373:159`) | the bottom timer band only (`1000×107` at `y 456`; the design's TIME-UP band is `1000×100` at `y 463`). Header, lyric band and NEXT row are unchanged — verified by diffing both metadata trees | `#0c0e14` + `1px #262a34` → **`#1c0c0e` + `2px #5a2327`** | `#10141e` → `#2a1416`, no border either side (`stage.rs:586-593`) | Figma: dot, "SERVICE TIMER" **and** the readout all flip to `#ff4d4d`; "· Sermon" stays `#6b7383`; an "OVER m:ss" pill appears. Implemented: only the dot and the readout change colour — the caption stays muted (STG-035), and there is no pill (STG-038) | **Instant.** No frame in the file depicts a transition, and no timing token is bound anywhere. `unspecified` — treated as a hard cut. | Figma: **yes**. Implemented: **no** — `time_up_ink()` alternates at 0.5 Hz (STG-039) |
| **Scripture** (`374:128` → *no TIME-UP frame*) | the right countdown panel only (`320×483` at `x 680, y 80`). The verse, reference and NEXT row are untouched | `#0c0e14` + `1px #262a34` → **unspecified** — Figma has no Scripture TIME-UP frame | `#10141e` → `#2a1416` (`stage.rs:738-745`) | Implemented: pill label becomes `"TIME UP"`, readout text becomes `"TIME UP"` at a reduced size (`0.11·h`, em `43.9`) so it clears the 320px panel. Figma: `unspecified` | Instant | Implemented: **no** — pill label and readout both take `time_up_ink()` (`stage.rs:758`, `:816`) |
| **Timer-only** (`374:151` → `374:166`) | the **whole screen** | `#08090d` flat → **elliptical radial gradient** centred `(500, 281.5)`, `rx 500 ry 281.5`, stops `#2A0E12` → `#190C10` @0.5 → `#08090D` | `#06080e` → flat `#2a1416` across `0,0,w,h` (`stage.rs:872-875`) | Figma: `TIME UP` at `130px` `#ff4d4d` (5.83:1 on the gradient midpoint), an `▲ OVER BY m:ss` pill, and the date line demoted to `22px` muted. Implemented: `TIME UP` at em `137.5` in pulsing red; no pill; date **and** time still shown at `28.8px` in white | Instant | Figma: **yes**. Implemented: **no** (STG-039) |

### 4.1 Compliance basis for the matrix

- **FR-175 (seizure-safety) is the governing requirement for flashing**, not NFR-020. FR-175
  (`SelahCue-PRD.md:365`) bounds output to "≤3 **general** flashes/sec **and** ≤3 **red** flashes/sec
  **and** within the small-safe flashing-area limit (WCAG 2.3.1)", verified by the ADR-0015
  flash-rate analyzer rather than a frequency count. All three implemented TIME-UP states are
  within that bound: the only time-varying element is a single word alternating at 0.5 Hz over a
  small area, and the background wash is steady in every template.
- **FR-059 (`SelahCue-PRD.md:190`)** is what STG-039 actually violates: "at 0 the configured TIME
  UP state renders on selected outputs only; wording customisable; **default is solid-inverted
  (static), not flashing** — if flashing is enabled it is constrained by FR-175". The
  implementation has (a) a non-static default, (b) no way to configure it off, (c) no customisable
  wording, and (d) no per-output selection (STG-016).
- **NFR-020 (`SelahCue-PRD.md:396`) is scoped to contrast only** — "AA claim scoped to contrast;
  photosensitivity/flash safety is FR-175". Contrast on the flipped regions is fine in both
  designs and in the implementation: `#ff4d4d` on `#1c0c0e` = **5.79:1**; `#ff4d4d` on the radial
  midpoint `#190c10` = **5.83:1**; the implementation's `#ef4444` on `#2a1416` = **4.61:1**; the
  brightened pulse peak ≈`#f47e7e` on `#2a1416` = **6.72:1**. All clear AA-normal, so all clear
  AA-large at the sizes actually rendered.

---

## 5. NFR-020 audit — configurable large text and high-contrast themes

NFR-020 has two clauses beyond raw contrast, and both are MVP scope:
*"stage/confidence text supports **configurable large size (≥48px-equivalent)** + **high-contrast
themes** for stage-lighting readability."*

| # | Clause | Status | Evidence |
|---|---|---|---|
| STG-077 | **Configurable large text size (≥48px-equivalent)** | **MISSING** | Every size in `stage.rs` is a hard-coded fraction of frame height (`0.044·h`, `0.17·h`, `0.49·h`, …). `StageDisplay::new(width, height, theme)` (`stage.rs:1091`) takes no scale input, `StageContext` (`:226-233`) carries none, and there is no setter. There is no code path by which an operator can enlarge stage text. |
| STG-078 | **High-contrast theme variant** | **MISSING** | `StageTheme` has exactly one constructor — `dark()` (`stage.rs:85-102`) — and `Default for StageTheme` returns it (`:105-109`). No second palette exists. The struct is public and fully constructible by a caller, so the *mechanism* is there; the *variant* is not. |

### 5.1 What "≥48px-equivalent" means at real resolutions, and where the current build lands

The design is authored at 1000×563 (aspect 1.7762). 1920×1080 is 1.7778 — within 0.1 % — so
proportional scaling reproduces the design almost exactly, and the ≥48px bar should be read at the
real output resolution, i.e. `em × 1080/563 = em × 1.918`.

Implemented em at **1920×1080** (`fraction × 1080 × 0.72`):

| Stage text role | em @1080 | ≥48px? |
|---|---|---|
| Worship — lyric (auto-fit ceiling) | 132.2 | yes |
| Worship — timer readout | 62.1 | yes |
| Worship — header clock | 48.2 | yes (just) |
| Worship — song title | 34.2 | **no** |
| Worship — stanza position | 31.1 | **no** |
| Worship — timer caption | 32.5 | **no** |
| Worship — next line | 26.4 | **no** |
| Worship — NEXT chip label | 23.3 | **no** |
| Scripture — big readout | 171.1 | yes |
| Scripture — verse (auto-fit ceiling) | 89.4 | yes |
| Scripture — TIME-UP readout | 85.5 | yes |
| Scripture — reference | 48.2 | yes (just) |
| Scripture — screen label | 38.9 | **no** |
| Scripture — next line | 23.3 | **no** |
| Scripture — TIME LEFT caption | 23.3 | **no** |
| Scripture — status pill label | 21.8 | **no** |
| Scripture — NEXT chip label | 21.8 | **no** |
| Timer-only — readout | 381.0 | yes |
| Timer-only — TIME UP word | 264.4 | yes |
| Timer-only — footer | 56.0 | yes |
| Timer-only — header clock | 52.9 | yes |
| Timer-only — segment label | 46.7 | **no** (marginal) |
| Timer-only — header label | 38.9 | **no** |
| Message overlay — chip label | 23.3 | **no** |

**13 of 24 roles fall below 48px-equivalent at 1080.** That is not automatically a defect — NFR-020
asks for *configurable* large size, and secondary chrome legitimately sits below the primary
content size. But with no configurability at all, the operator has no remedy, and the two roles a
speaker most needs at distance after the timer — the **next line** (26.4px) and the **scripture
reference / screen label** — are among them. Note also that raising the sizes to the Figma values
(§6.2) moves several roles up but not over the line: the design's own next line is 30px → 57.5px at
1080 (clears), while its NEXT chip label is 16px → 30.7px (does not).

**Recommended shape of the fix** (design position; the owner decides):
add a `stage_text_scale: f64` to `StageContext`, default `1.0`, clamped to `0.75..=1.75`, applied
as a multiplier on every computed line-box before the `.max(1)`. At `1.0` the corrected fractions
reproduce Figma; at `1.5` every role above clears 48px-equivalent at 1080. This is a **layout**
change and touches no token value, so it carries none of the four-surface blast radius in §6.1.

### 5.2 Contrast audit of what is actually rendered

Measured with the WCAG 2.x formula (`tokens::contrast_ratio` uses the same maths). Stage text is
large by definition, so the applicable bar is **AA-large ≥3:1** for anything ≥18.66px bold /
≥24px regular, and **AA-normal ≥4.5:1** below that.

| Pairing | Ratio | Verdict |
|---|---|---|
| Implemented `text` `#ffffff` on `background` `#06080e` | 20.02:1 | pass |
| Implemented `muted` `#8a93a3` on `#06080e` | 6.47:1 | pass (AA-normal) |
| Implemented `muted` on `panel` `#10141e` | 5.95:1 | pass |
| Implemented `muted` on `track` `#1e222c` | 5.14:1 | pass |
| Implemented `muted` on `alert_wash` `#2a1416` | 5.61:1 | pass |
| Implemented `timer_ok` `#2bb673` on `#06080e` | 7.67:1 | pass |
| Implemented `timer_warn` `#f2b53c` on `#06080e` | 10.92:1 | pass |
| Implemented `timer_alert` `#ef4444` on `#06080e` | 5.32:1 | pass |
| Implemented `timer_alert` on `alert_wash` | 4.61:1 | pass |
| Implemented `accent` `#f2b84b` on `#06080e` | 11.19:1 | pass |
| Implemented message chip: `background` ink on `accent` gold | 11.19:1 | pass |
| Implemented `SONG_ACCENT` `#8b5cf6` on `track` `#1e222c` | 3.76:1 | pass (AA-large; it is a **dot**, non-text UI — ≥3:1 applies) |
| Figma `#6b7383` on `#08090d` | 4.17:1 | pass at AA-large; **fails AA-normal** |
| Figma `#6b7383` on `#12141c` (NEXT chips) | 3.86:1 | pass at AA-large only |
| Figma `#6b7383` on `#0c0e14` (scripture panel captions) | 4.05:1 | pass at AA-large only |
| Figma `#6b7383` on `#1c0c0e` (TIME-UP band "· Sermon") | 3.97:1 | pass at AA-large only |
| Figma `#a7aebe` on `#08090d` | 8.95:1 | pass |
| Figma `#35c08a` on `#08090d` | 8.58:1 | pass |
| Figma `#f2b84b` on `#08090d` | 11.12:1 | pass |
| Figma `#ff4d4d` on `#1c0c0e` / `#2a1416` / `#2a0e12` | 5.79 / 5.31 / 5.49:1 | pass |
| Figma `#7e6eff` on `#12141c` (song dot) | 4.87:1 | pass |
| Legacy `13:15` white on solid `#c7212b` | 5.71:1 | pass |

**Two observations.**

1. **The implementation's `muted` is more accessible than the frames'.** `#8a93a3` at 6.47:1 clears
   AA-*normal* everywhere it is used; Figma's `#6b7383` clears only AA-large. Since every stage run
   that uses it is bold and large, both are compliant — but this is the one place where "match the
   frame" would *reduce* contrast. `MOBILE-2.0-SPEC.md` §2.3 records the settled precedent for
   `#6b7383`: it is tertiary/label-only and anything carrying text maps to `d2TextSecondary`
   `#a7aebe`. On the stage display, `#6b7383` in Figma carries the next line, the timer caption and
   the screen label — all *text*. Applying the mobile precedent gives `#a7aebe` (8.95:1), which is
   also what the frames already use for the wall clock. **Design recommendation:** adopt `#a7aebe`
   as the stage `muted`, not `#6b7383`. Flagged as **Q2**.
2. **Nothing on the stage display uses the failing pairings named in the wider Design 2.0 audit.**
   The GO LIVE green gradient (1.93:1 with white — fails at every size) does not appear on any
   stage frame; neither does white-on-solid-live-red, nor white on the violet gradient. The stage
   display is clear of all three.

### 5.3 A11Y conflicts — owner decision required

One, and it is unambiguous.

| # | Where | Figma value | Measured | Why it fails | What to build |
|---|---|---|---|---|---|
| STG-071 *(same finding as §3.6)* | `375:135` — the "MESSAGE FROM PRODUCTION" chip inside the production-message card | chip fill **`#ffffff`**, label **`#f5a524`** at `18px` bold. Pixel-verified from the render: `(360,318)` = `(255,255,255)` | **2.04:1** | Fails AA-normal (4.5:1) **and** AA-large (3:1). No text size makes gold-on-white compliant. At `18px` it is not even large text. This is the same class of defect as the GO LIVE green: a light ink on a light fill | **Do not build the frame as drawn.** Two options: **(A)** invert — gold fill `#f2b84b`, near-black label `#0b0d12` → **11.19:1**. This is what the implementation already does (`stage.rs:1003-1013`), it matches the mobile precedent in `MOBILE-2.0-SPEC.md` §2.5 (fill→tint inversion; dark label on a bright status fill), and it needs no code change. **(B)** keep the frame's white chip and darken the label to `#7a4a00` or similar → ≈5:1, but that abandons the gold token. **Recommendation: (A).** The implementation is already correct; the *frame* is what is wrong |

Per the coordinator's standing instruction, the "fix the Figma source" question has already been
put to the owner by another session and is **not** re-escalated here. This row records the finding
and the resolution so the Rust engineer knows **not** to "correct" `stage.rs` toward the frame.

---

## 6. Resolution and scaling contract

### 6.1 What the composer does today

`compose_stage` (`stage.rs:241-281`) takes `width`/`height`, clamps both to
`raster::MAX_DIMENSION` (8192, `raster.rs:169`), returns an empty background-only frame at zero,
and hands off to one of three template functions. Every template expresses **all** geometry as a
fraction:

- **horizontal** positions and widths are fractions of `w` (`0.04·w` margins, `0.68·w` panel split,
  `0.96·w` right edge);
- **vertical** positions, heights **and every type size** are fractions of `h`.

So the layout is **fully proportional and non-uniform** — it stretches independently on each axis.
There is no anchoring, no fixed margin, no minimum size, and no safe area beyond the 4 % margins.

### 6.2 Consequences

- **At 16:9 this is exactly right.** 1000×563 = 1.7762; 1920×1080 = 1.7778. Scaling every Figma
  value by `h/563` reproduces the design to within 0.1 %, on both axes. 1280×720, 2560×1440 and
  3840×2160 are identical in aspect and therefore identical in result. **The mechanism is correct;
  only the constants are wrong.** No architectural change is needed to reach parity.
- **At other aspects it distorts, and asymmetrically.** On a 16:10 output (1920×1200) every vertical
  fraction and every type size grows by 11 % while horizontal margins stay at 4 % of width — text
  gets larger relative to the frame and the 4 % margins get proportionally tighter. On a 4:3
  projector (1024×768) the scripture panel is still 32 % of width (328px) but the verse column
  collapses to 614px while the type grows 36 % — the verse auto-fit will shrink aggressively to
  compensate, so the design's balance is lost but nothing clips.
- **The auto-fit regions absorb the distortion; the fixed chrome does not.** `fit_lines` /
  `autofit_layers` wrap and shrink, so the lyric and verse bands stay legible at any aspect. The
  single-line chrome (`line()`) never wraps — `raster.rs`'s `draw_text` does not wrap — so an
  over-long stanza position or segment title will clip rather than shrink.

### 6.3 The contract to write down

**Design position, for the Rust engineer to implement:**

1. **Reference frame: 1000 × 563.** Every Figma value in this document is at that size.
2. **Uniform scale factor `s = h / 563`** for **type sizes** and vertical geometry — *not* separate
   per-axis factors. Type must not stretch with aspect.
3. **Horizontal geometry stays a fraction of `w`** for full-bleed regions (bands, the panel split,
   margins) so they remain edge-to-edge at any aspect; but **type sizes derived from the horizontal
   axis do not exist** — there are none in the design, and none should be introduced.
4. **`line()` takes a line-box height; the rendered em is `line_box × 0.72`.** To hit a Figma em
   value `E`, pass `line_box = E / 0.72`, i.e. `h_fraction = E / (0.72 × 563) = E × 0.002466`.
   §6.4 gives the table.
5. **Aspect guard:** below 1.5:1 the design is out of its envelope. Recommendation — clamp `s` to
   `min(h/563, w/1000)` so a narrow output shrinks type rather than overflowing the 4 % margins.
   Currently `unspecified` in Figma; raised as **Q6**.
6. **Minimum usable size:** `compose_stage` already survives tiny frames (tests compose at 160×90
   and 200×100), because every `px` is `.max(1)`. Keep that.

### 6.4 Figma em → line-box fraction (the constants to substitute)

`h_frac = em / 0.72 / 563`. Rounded to 4 decimal places; the "@1080" column is the resulting
rendered em at 1920×1080.

| Role | Figma em | line-box px @563 | `h_frac` | em @1080 |
|---|---|---|---|---|
| Worship — song title | 22 | 30.6 | `0.0543` | 42.2 |
| Worship — stanza position | 20 | 27.8 | `0.0493` | 38.4 |
| Worship — header clock | 30 | 41.7 | `0.0740` | 57.5 |
| Worship — lyric (auto-fit cap) | 56 | 77.8 | `0.1381` | 107.4 |
| Worship — NEXT chip label | 16 | 22.2 | `0.0395` | 30.7 |
| Worship — next line | 30 | 41.7 | `0.0740` | 57.5 |
| Worship — SERVICE TIMER | 20 | 27.8 | `0.0493` | 38.4 |
| Worship — "· Sermon" | 18 | 25.0 | `0.0444` | 34.5 |
| Worship — timer readout | 52 | 72.2 | `0.1283` | 99.8 |
| Worship — TIME UP word | 46 | 63.9 | `0.1135` | 88.2 |
| Worship — OVER pill label | 22 | 30.6 | `0.0543` | 42.2 |
| Scripture — screen label | 20 | 27.8 | `0.0493` | 38.4 |
| Scripture — header clock | 28 | 38.9 | `0.0691` | 53.7 |
| Scripture — reference | 30 | 41.7 | `0.0740` | 57.5 |
| Scripture — verse (auto-fit cap) | 48 | 66.7 | `0.1184` | 92.1 |
| Scripture — NEXT chip label | 15 | 20.8 | `0.0370` | 28.8 |
| Scripture — next line | 26 | 36.1 | `0.0641` | 49.9 |
| Scripture — status pill label | 13 | 18.1 | `0.0321` | 24.9 |
| Scripture — TIME LEFT | 15 | 20.8 | `0.0370` | 28.8 |
| Scripture — big readout | 96 | 133.3 | `0.2368` | 184.2 |
| Scripture — sub-caption | 16 | 22.2 | `0.0395` | 30.7 |
| Timer-only — header label | 20 | 27.8 | `0.0493` | 38.4 |
| Timer-only — header clock | 28 | 38.9 | `0.0691` | 53.7 |
| Timer-only — segment label | 26 | 36.1 | `0.0641` | 49.9 |
| Timer-only — giant readout | 190 | 263.9 | `0.4687` | 364.5 |
| Timer-only — footer date/time | 30 | 41.7 | `0.0740` | 57.5 |
| Timer-only — TIME UP word | 130 | 180.6 | `0.3207` | 249.4 |
| Timer-only — OVER pill label | 28 | 38.9 | `0.0691` | 53.7 |
| Timer-only — TIME-UP date | 22 | 30.6 | `0.0543` | 42.2 |
| Message — chip label | 18 | 25.0 | `0.0444` | 34.5 |
| Message — body (auto-fit cap) | 56 | 77.8 | `0.1381` | 107.4 |

Vertical positions, as `h`-fractions of the Figma `y`:

| Role | Figma `y` @563 | `h_frac` | Current impl |
|---|---|---|---|
| Worship — song pill top | 28 | `0.0497` | `0.052` |
| Worship — header clock top | 30.5 | `0.0542` | `0.050` |
| Worship — lyric block top | 131.5 | `0.2336` | `0.19` |
| Worship — NEXT row top | 377.5 | `0.6705` | `0.68` |
| Worship — timer band top | 456 | `0.8099` (band `h_frac 0.1901`) | `0.81` (`0.19`) |
| Scripture — screen label top | 33 | `0.0586` | `0.058` |
| Scripture — reference top | 103 | `0.1830` | `0.185` |
| Scripture — verse top | 159 | `0.2824` | `0.28` |
| Scripture — NEXT row top | 480.5 | `0.8535` | `0.85` |
| Scripture — panel top | 80 | `0.1421` | `0.142` |
| Scripture — pill top | 213 | `0.3783` | `0.37` |
| Scripture — TIME LEFT top | 253 | `0.4494` | `0.45` |
| Scripture — readout top | 283 | `0.5027` | `0.50` |
| Scripture — sub-caption top | 411 | `0.7300` | *missing* |
| Timer-only — header label top | 33 | `0.0586` | `0.052` |
| Timer-only — segment top | 163 | `0.2895` | `0.27` |
| Timer-only — readout top | 200 | `0.3552` | `0.30` |
| Timer-only — footer row top | 436 | `0.7744` | `0.80` |
| Timer-up — TIME UP top | 182.5 | `0.3242` | `0.36` |
| Timer-up — OVER pill top | 359.5 | `0.6385` | *missing* |
| Timer-up — date top | 433.5 | `0.7700` | `0.80` |
| Message — card top | 278.5 | `0.4947` | `0.34` |
| Message — card left / width | `x 142` / `716` | `0.142·w` / `0.716·w` | `0.10·w` / `0.80·w` |

The vertical positions are mostly close already — the material position errors are the worship
lyric block (`0.19` vs `0.2336`), the timer-only readout (`0.30` vs `0.3552`) and the message card
(`0.34` vs `0.4947`).

---

## 7. Open questions for the owner

Each is answerable in a word or two.

1. **`375:139` says Scripture's TIME UP is "timer region only"; `563:201` says "panel region".**
   Which frame is authoritative? (The code and the handoff both do *panel*; `375:139` reads like a
   copy-paste from the Worship row.) → **"panel"** or **"timer"**.
2. **Stage `muted` ink.** Adopt Figma's `#6b7383` (4.17:1, AA-large only) or the mobile precedent
   `#a7aebe` (8.95:1, AA-normal) for the stage's label/next-line/caption ink? → **"6b7383"** or
   **"a7aebe"**.
3. **TIME-UP polarity.** FR-059 names the default "solid-inverted", which is legacy `13:15`
   (white on solid red). Design 2.0 `374:166` is the inverse (red ink on near-black). Confirm the
   Design 2.0 polarity supersedes the FR-059 wording, or keep solid-inverted? →
   **"D2.0"** or **"inverted"**.
4. **Scripture pill copy in the non-on-time states.** Figma draws only `ON TIME`. The code invents
   `HURRY` and `TIME UP`. Approve those strings, or supply others? → **"approve"** or the strings.
5. **Scripture TIME-UP appearance.** No frame exists. Approve the code's current behaviour (wash
   the panel, pill → `TIME UP`, readout → `TIME UP` at half size), or does Scripture get its own
   frame? → **"approve"** or **"draw it"**.
6. **Aspect-ratio guard.** Below 16:9, clamp the scale to `min(h/563, w/1000)` so type shrinks
   rather than overflowing the margins? → **"clamp"** or **"stretch"**.
7. **The `375:128` header.** That frame shows a *simplified* single-line header
   (`AMAZING GRACE · V2`) where `373:133` shows the pill + violet dot + stanza position. Is the
   simplified header a real alternate treatment for the message state, or just a sketch? →
   **"sketch"** (keep the full header under the overlay) or **"real"**.

---

## 8. Suggested build order

Sequenced so each step is independently verifiable and nothing later invalidates something earlier.
Steps 1–3 are pure layout and carry no cross-surface risk. Step 4 is the one with a four-surface
blast radius.

**Step 0 — unblock typography (do this first or step 2 produces silently wrong widths).**
`Layer::Text` already carries `TextStyle::letter_spacing_px` and `raster.rs` applies it when
drawing (`raster.rs:937`, `:1292`, `:1304`), but the measurement path does not:
`raster::measure_line_width(text, px, font, weight)` has no spacing parameter, and
`selahcue-present/src/measure.rs`'s memo `Key` (`measure.rs:23`) is `{text, cell, font, weight}`.
`autofit_layers` (`compose.rs`, changed in `53f0032`) now goes through that memo. **If you add
tracking to any auto-fit region without extending both the measure signature and the memo key, the
shrink-to-fit will size against widths that no longer match what is drawn, and the wrong width will
be cached across composes.** The same applies to any other new shaping attribute (stretch, a
different shaping mode). Extend `measure_line_width`, extend `Key`, and add a bounded-memory test
per `CLAUDE.md` — per-key hit accessor, hit asserted before the contract, compile-time premise pin,
positive control, mutation-verified **with siblings running**.
*Note:* the chrome runs that need tracking use `line()`, which does not go through the memo — only
the auto-fit regions (lyric, verse, message body) do, and none of those carry tracking in Figma. So
step 0 is only strictly required if tracking is later applied to an auto-fit region. Do it anyway
before step 2; it is cheap and the trap is silent.

**Step 1 — geometry and type sizes (largest visible win, zero token risk).**
Substitute the `h_frac` constants from §6.4 for the current fractions in all three templates and
the message overlay. Add the `s = h/563` uniform-scale rule from §6.3 and the aspect clamp once
**Q6** is answered. Fixes STG-019 through STG-030, STG-037, STG-040 through STG-051, STG-054
through STG-060, STG-064, STG-070, STG-072. All of these are single-number edits inside `stage.rs`;
none touches `tokens.rs`, so `design2_palette_is_pinned_across_surfaces` cannot be disturbed.
Verify with `cargo test -p selahcue-present --test test_stage`.

**Step 2 — the missing runs and the missing primitives.**
- ~~Add `rounded_rect` and a stroke option to the engine's fill primitive, or a `Layer::Rect`
  variant carrying `radius` + `border` (STG-008, STG-009). This is the only step that reaches
  into `selahcue-engine` — coordinate, that crate has uncommitted WIP from another session.~~
  **CORRECTION (2026-08-23, implementation batch):** no engine work is needed, and this step
  does not reach into `selahcue-engine` at all. **`Layer::Shape` already exists**
  (`selahcue-engine/src/scene.rs:161`) carrying `kind: ShapeKind` (`Ellipse` / `RoundedRect` /
  `Triangle`), `fill`, `border`, `border_px` and `corner_px`, and it is rasterized by
  `raster.rs`'s `draw_shape`. STG-008 (borders), STG-009 (radii), STG-010 (circular dots) and
  the `▲` on the timer-only overrun pill were all implemented through it with **zero** changes
  to `selahcue-engine`. The claim in §2's STG-008 row — "`fill()` … is the only rect primitive
  and it has no stroke" — is likewise wrong: `fill()` is the only primitive *`stage.rs` was
  using*, not the only one available.
- Make `dot()` draw a **circle** (STG-010).
- Add tracking to the chrome runs per §3 (STG-011).
- Add the three missing content runs: worship `· Sermon` (STG-029), scripture panel sub-caption
  (STG-052), and the two-tone timer-only footer (STG-058/059/060).
- Add the **overrun readout** — the `OVER m:ss` pill in Worship (STG-038) and the `▲ OVER BY m:ss`
  pill in Timer-only (STG-065). `TimerView` already carries `elapsed_secs`; the overrun for a
  countdown is `elapsed − total`, which needs either a new `TimerView` field or a caller-supplied
  value. **This is the highest user-visible gap in the audit** — the speaker currently cannot tell
  how far over they are.
- Make the worship `SERVICE TIMER` caption flip to the alert ink at TIME UP (STG-035).
- Make the timer-only header show the segment name at TIME UP instead of the fixed literal
  (STG-063), and stop drawing the segment label twice (STG-067).

**Step 3 — TIME-UP behaviour, once Q1/Q3 are answered.**
- Remove the pulse from the default path (STG-039). Per FR-059 the default is static; if a flashing
  variant is wanted it becomes a configured option constrained by FR-175, and it needs to run
  through the ADR-0015 flash-rate analyzer, not a bare frequency argument.
- Replace the flat timer-only TIME-UP fill with the radial gradient (STG-062) — this needs a
  gradient fill in the engine, so it pairs naturally with step 2's primitive work. If a gradient is
  out of scope, a flat `#190C10` (the midpoint stop) is the honest approximation and is 5.83:1
  against `#ff4d4d`.
- Add the TIME-UP band border and the shorter band height (STG-032, STG-033).

**Step 4 — token alignment (four-surface lockstep — plan it, do not slip it in).**
STG-001 through STG-007 and STG-076 all say the same thing: `StageTheme::dark()` is still built
from the *legacy* canonical inks (`tokens::PREVIEW.ink`, `tokens::LIVE.ink`, `tokens::WARN.ink`)
while the frames are drawn in `tokens::design2`. Moving them is the right call, **but**
`selahcue-present/tests/test_tokens.rs::design2_palette_is_pinned_across_surfaces` cross-checks
four surfaces at once: `selahcue-operator/dist/app.css`, `tokens::design2::MANIFEST`,
`StageTheme::dark()`, and the Flutter `implementation/mobile/selahcue_controller/lib/models/design_tokens.dart`
— and the Dart check is a **source-text grep** for the literal `d2<Camel> = Color(0xFF<HEX>)`.
So any stage colour *value* change is a coordinated edit across a CSS file, a Rust manifest, a Rust
struct and a Dart file, landing together or the audit fails. Treat it as its own batch with its own
review, not as a tail on step 1. Note that the stage struct can be pointed at the existing
`design2` swatches without inventing any new token — `timer_ok → design2::PREVIEW`,
`timer_alert → design2::LIVE`, `timer_warn → design2::WARN`, `accent → design2::GOLD` (already
equal), `alert_wash → design2::LIVE_SOFT` (already equal) — which keeps the manifest itself
unchanged and reduces the blast radius to the struct plus whatever the pin test asserts about it.

**Step 5 — NFR-020 (MVP scope; currently unmet).**
- `stage_text_scale` on `StageContext`, default `1.0`, clamped `0.75..=1.75`, multiplying every
  line-box (STG-077). Layout-only, no token risk.
- A `StageTheme::high_contrast()` constructor (STG-078). Pure white text, pure black field,
  maximum-separation status inks; the struct is already public and fully constructible, so this is
  additive.
- Per-output region toggles for Now / Next / Clock / Timer+TIME-UP / Stage message / Theme
  background (STG-016), which FR-059 also needs for "renders on selected outputs only".

**Verification.** Do **not** run `make ci` opportunistically — the checkout is shared and concurrent
Flutter runs produce false reds. A full `make ci` **is** required before any push that touches
step 2 (engine primitives) or step 4 (tokens); steps 1, 3 and 5 can be verified with
`cargo test -p selahcue-present` alone. Serialise the full run with the other active sessions.

---

## 9. Evidence and provenance

- **Figma:** all eight owned frames plus both legacy frames read on 2026-08-23 via
  `get_metadata` (absolute geometry), `get_design_context` (typography, fills, borders, radii,
  padding) and `get_screenshot` at `maxDimension` 2000/1400 (visual confirmation). Every screenshot
  was downloaded and inspected. `get_variable_defs` on `373:133` returned `{}` — no bound
  variables; all values are raw hex.
- **Asset-level verification:** the four status dots were fetched as SVG and their `fill` read
  directly — `#7E6EFF` (song), `#35C08A` (timer running), `#FF4D4D` (timer at TIME UP),
  `#35C08A` (scripture pill). The `375:135` white chip fill and the `374:166` gradient were
  confirmed by sampling the rendered PNGs.
- **Implementation:** `selahcue-present/src/stage.rs` (1203 lines) read in full;
  `selahcue-present/src/tokens.rs` read in full; `selahcue-present/src/measure.rs`,
  `selahcue-engine/src/raster.rs` (constants and text paths), `selahcue-lan/src/protocol.rs` and
  `selahcue-app/src/operator.rs` read for the wire contract. Implemented pixel values were derived
  by evaluating the composer's own arithmetic at 1000×563.
- **Requirements:** `SelahCue-PRD.md:190` (FR-059), `:365` (FR-175), `:396` (NFR-020).
- **Precedent:** `docs/design/MOBILE-2.0-SPEC.md` §2.3, §2.5 (fill→tint inversion, the
  `text-muted` mapping rule); `selahcue-present/tests/test_tokens.rs:536`, `:585-592` (the settled
  AA-large audits).
- **Contrast:** computed with the WCAG 2.x relative-luminance formula, identical to
  `tokens::relative_luminance` / `tokens::contrast_ratio`.
- No implementation file was modified. `selahcue-engine/`, `implementation/mobile/` and
  `selahcue-present/tests/test_present.rs` were not touched.

---

## Reconciliation — 2026-09-20

**Author:** Uma (UI/UX). **Scope:** re-verify all 78 `STG-###` findings against `main` as of this
worktree's base commit (`4b21c39`), docs-only.

### Method

`docs/delivery/CODE-REVIEW-batch-desktop-design2-stage.md` (2026-08-24, commits `7369f61` and
follow-ups) is the only remediation batch against `stage.rs`, and it is unusually explicit about
scope: §3 "STG items closed" lists every finding id it fixed, §5 "Deliberately NOT done" lists every
finding it left open and why, and §8 "Files changed" states `stage.rs` is the only source file it
touched (`theme.rs`, `compose.rs`, `measure.rs`, `tokens.rs` explicitly **not** touched by that
batch). `git log --since=2026-08-23 -- implementation/desktop/crates/selahcue-present/src/stage.rs`
shows no commit since the batch, so its own "closed"/"not done" lists are the current, live state —
verified rather than assumed by reading `stage.rs`'s cited constants (`design` module, `StageTheme`
repoint) directly.

### FIXED

Per the batch doc §3, verified against `stage.rs` directly (type-scale constants now live in a
`design` module resolved through one seam; `StageTheme::dark()` now points at `tokens::design2` for
`timer_ok`/`timer_warn`/`timer_alert`/`accent`/`alert_wash`; shapes use the engine's existing
`Layer::Shape` primitives; nine tracking values applied; the overrun readout wired end to end via
`TimerView::from_timer`):

**Type sizes (§6.4 substitution table):** `STG-019, 020, 021, 024, 025, 028, 030, 037, 040, 041, 042,
044, 045, 049, 051, 054, 055, 056, 057, 060, 064, 072` — 22 findings.

**Ink tokens:** `STG-003, 004, 018, 074` — 4 findings. (`STG-076` partial — see Open below.)

**Shapes:** `STG-008, 009, 010, 017, 026, 027, 034, 046, 047, 048, 070` — 11 findings.

**Letter-spacing:** `STG-011` — 1 finding.

**Overrun readout:** `STG-038, 065` — 2 findings.

**Other DRIFT closed in the same code paths:** `STG-013, 035, 062, 063, 066, 067` — 6 findings.

**NFR-020 (MVP-blocking):** `STG-077` (configurable large text, `text_scale_permille`, 750–1750‰
clamp) and `STG-078` (`StageTheme::high_contrast()`, additive) — 2 findings. These were the headline
"NFR-020 not met at MVP scope" finding from the audit's own summary; both are now built and
mutation-verified (batch doc §6, M9).

**Total FIXED: 48 findings**, all mutation-verified per the batch doc §6 (each control broken,
confirmed RED with siblings running, restored).

### Reclassified INTENTIONAL-DEVIATION (owner-approved, permanent — not gaps)

- **`STG-039`** (the TIME-UP pulse) — the owner chose to **keep** the 0.5 Hz pulse rather than make
  it static, discharging ARCH-UX-REVIEW-stage5 M4 via measured FR-175 flash-safety evidence instead
  (batch doc §1: 0/0.5 flashes/sec against a ≤3/≤3 limit, 6× margin). **This reverses the audit's
  MISSING/DRIFT framing** — it was never rebuilt toward the frame, and per the operating rule stated
  in the task brief, it must not be. Reclassify from whatever the audit tagged it to
  `INTENTIONAL-DEVIATION`.
- **`STG-071`** (the gold-on-white message chip) — the audit's own frame reading is wrong (2.04:1,
  fails AA at every size); the shipped inversion is 11.19:1 and is now pinned by a dedicated test
  (`the_production_message_chip_keeps_its_accessible_polarity`). `INTENTIONAL-DEVIATION`, per the
  batch doc §5.

**2 findings reclassified**, neither counted as open below.

### Confirmed still OPEN (batch doc §5, cross-checked directly)

- **`STG-001, STG-006, STG-007`** (background/panel/chip fills `#08090d`/`#0c0e14`/`#12141c`) — no
  `design2` token equivalent exists yet; deferred to a token batch. Still literal legacy hexes in
  `stage.rs` as of this worktree.
- **`STG-002`** (the stage `muted` ink, `#6b7383` vs the mobile precedent `#a7aebe`) — blocked on
  audit Q2, unresolved.
- **`STG-016`** (per-output region toggles) — out of scope per FR-059's "selected outputs only"
  reading; still MISSING if that reading is ever revisited.
- **`STG-029, STG-052, STG-058, STG-059, STG-060`** (the `· Sermon` suffix, panel sub-caption, and
  the two-tone footer's second ink) — need plan-segment-name/segment-end-time data the composer is
  not given, plus the two-tone footer is itself blocked on Q2. (Note: `STG-060`'s *type size* half was
  separately closed by the type-scale substitution table above — only its ink/data half is open.)
- **`STG-031, STG-033`** (TIME-UP band fill `#1c0c0e` and its 100-unit height) — no `design2`
  equivalent for the fill; the height is content-driven in the frame, not a fixed value to match.
- **`STG-069`** (the simplified message header) — blocked on audit Q7 (sketch vs. real), unresolved.

**12 findings confirmed OPEN**, all explicitly named as deferred in the batch doc itself and
re-verified present in `stage.rs` as of this worktree.

### Not otherwise discussed — OPEN, unchanged

The remaining `STG-###` ids (78 − 48 fixed − 2 reclassified − 12 confirmed-open above = 16) are
per-frame geometry/DRIFT rows from §3 "Per-frame audit" not named in the batch doc's closed or
deferred lists (e.g. residual pixel-level rows not swept up by the type-scale/shape/tracking
substitutions). `git log` confirms zero commits to `stage.rs` since the batch, so these stand at
their original audit verdict, unchanged. They were not individually re-grepped line-by-line in this
pass; Phase D ticket scoping should do that read before writing a ticket against any of them, since a
few may already have been incidentally swept up by the type-scale/shape work above without an
explicit id citation in the batch doc.

### Totals

| | Count |
|---|---:|
| Total findings | 78 |
| FIXED | 48 |
| Reclassified INTENTIONAL-DEVIATION (owner-approved, not open) | 2 |
| **OPEN** | **28** |

Open, by severity: the original audit did not tag `STG-###` rows with blocker/major/minor the way the
console and presentation audits did (its own severity column uses Low/Medium, plus the three
headline items flagged in prose as more-than-cosmetic). Of the three headline "more than cosmetic"
findings (§1.1): `STG-039` is now resolved as an owner-approved deviation (not open); `STG-077`/
`STG-078` (NFR-020) are FIXED; `STG-038`/`STG-065` (overrun readout) are FIXED. **All three of the
audit's own headline "more than cosmetic" issues are closed.** The 28 open findings are the
lower-severity residue: 3 fill-token gaps (Low), 1 blocked ink decision (Medium), 1 scope question
(Medium), 5 data-dependent copy gaps (Low–Medium), 2 fill/height gaps (Low), 1 blocked header
question (Low), plus 16 unswept per-frame geometry rows not yet individually re-graded.

---

## Reconciliation — 2026-09-22 (frontend closure pass)

**Author:** Farah (Frontend Engineer), ClickUp `17tnw2axptq`. **Scope:** individually re-grep the
16 "unswept" ids the 2026-09-20 reconciliation left un-triaged, re-verify the 12 explicitly
confirmed-open ids against `stage.rs` as of this ticket's base commit, implement what is genuinely
tractable, and record exactly why each remaining id is still blocked. `git log -- .../stage.rs`
between the two reconciliation dates shows no commits, so the 2026-09-20 state is what this pass
re-verified against — every classification below is a direct read of `stage.rs`, not an inference
from the prior doc.

### Guardrail honoured

`STG-039` (the TIME-UP pulse) was **not touched**. No other `INTENTIONAL-DEVIATION` verdict
(`STG-039`, `STG-071`) was revisited either.

### Fixed this batch

- **`STG-012`** (font weight uniformly 700) — the design uses three weights: Bold (700) for
  labels/readouts, Semi Bold (600) for the wall clock (all three templates), Medium (500) for the
  stanza position, both NEXT lines, and the timer-only footer. `line()` now takes an explicit
  `weight: u16` and every one of its 25 call sites passes the semantically correct
  `design::WEIGHT_BOLD` / `WEIGHT_SEMIBOLD` / `WEIGHT_MEDIUM`. Note for whoever next touches
  typography here: the bundled single-weight face only synthesises an embolden above 550
  (`selahcue_engine::raster::attrs_for`), so 600 and 500 currently render pixel-identical to each
  other and only distinguishable from 700 — carrying the correct semantic value now is what makes
  a future multi-weight face (or an engine change) a no-op here instead of a second sweep.
  Verified: `chrome_runs_carry_the_designed_font_weight`
  (`crates/selahcue-present/tests/test_stage_parity.rs`), mutation-verified (reverted the wall
  clock to Bold, confirmed RED with siblings running, restored).

### Closed by verification — already fixed incidentally by the 2026-08-24 batch, no code change

Re-grepping `stage.rs` found these already true; the 2026-08-24 batch's own "STG items closed"
list (§3 of the code-review batch) didn't cite them by id because they were swept up as a
side-effect of a differently-scoped fix, exactly as the 2026-09-20 reconciliation warned could
happen.

- **`STG-005`** (warning ink) — `StageTheme::dark().timer_warn` already points at
  `tokens::design2::WARN` = `#f5a524`, the exact value the audit named as Design 2.0's warn ink.
- **`STG-023`** (worship NEXT chip radius/shape) — `chip()` already draws through `surface()`
  with `m.stroke(design::R_CHIP)` (7px), the same shared fix that closed `STG-044`'s shape half.
- **`STG-032`** (worship TIME-UP band border) — `compose_worship`'s footer band already draws
  `theme.alert_border` (`design2::LIVE_BORDER` = `#5a2327`, the exact hex the audit specified) at
  `design::B_TIME_UP_BAND` (2px) when `up`.
- **`STG-043`**, leading half — `VERSE_LINE_HEIGHT = 1.24` is already applied to the scripture
  verse region, matching Figma `374:135`'s explicit `leading-[1.24]`. (Its cap-size half is
  closed below, as superseded.)

### Closed — owner decision already recorded in code, not re-litigated

- **`STG-053`** (Scripture TIME-UP appearance) — `compose_scripture`'s readout carries the
  comment "Figma draws no Scripture TIME-UP frame, so this keeps the code's approved behaviour
  (audit Q5)". Q5 was answered during the 2026-08-24 batch; this finding is resolved, not open.

### Closed — editorial resolution (evidence-weight call, not a value trade-off; reversible in one line)

- **`STG-073`** (Scripture TIME-UP region scope, **Q1**) — three Figma sources bear on this:
  `375:139` says "timer region", `563:156` and `DESIGN-2.0-HANDOFF` §5.11 both say "panel region".
  The implementation already does "panel" (matches 2 of 3, and §3.8 of this audit already records
  it as **MATCH** against `563:156`). The audit's own text calls `375:139` "copy-paste from the
  Worship row". Resolving Q1 as **"panel"** on the weight of evidence — this is an internal-
  consistency read of three already-live Figma frames, not a values/accessibility trade-off like
  Q2/Q4/Q7, so it stays within engineering judgement. If the owner reads `375:139` as intentional,
  this is a one-line revert (no code changes ride on it either way).

### Closed — superseded or verified non-issue, no code change

- **`STG-022`** (worship lyric band geometry vs. the fixed 212px rect) — superseded by the
  2026-08-24 batch's owner-approved elastic-band redesign (§2.2 of that batch): the fixed rect is
  now documented as "the two-line case Figma 373:133 was drawn against, not normative geometry"
  (`stage.rs`'s own comment above `Y_LYRIC`/`H_LYRIC`). The original "cap 22% over" comparison
  measures against geometry the implementation deliberately no longer uses.
- **`STG-015`** (`TimerView::progress` unused) — verdict is EXTRA/Low, not a defect. It is a
  tested, working piece of the domain model (`timer_view_derives_state_from_a_countdown` in
  `test_stage.rs` asserts it) kept for a future progress bar; removing it forfeits working,
  covered behaviour for no user-facing gain and isn't what "close the gap" should mean here.
- **`STG-061`** (idle `"--:--"` state) — UNSPECIFIED only because no Figma frame draws a
  no-timer state. The placeholder contradicts no authority and is already covered
  (`idle_monitor_shows_no_timer_colour_and_no_text`, `test_stage.rs`). No action needed.
- **`STG-014`** (Figma tokens not bound as variables) — an observation about the Figma file's own
  authoring (`get_variable_defs` returns `{}`), not an implementation gap. No code path addresses
  it because none could.
- **`STG-075`** (preset message payloads) — already verdict **MATCH** in the original audit ("no
  output-side work needed"). Nothing was ever open here.
- **`STG-076`** (Design 2.0 console token list) — its components are tracked individually as
  `STG-001`/`STG-002`/`STG-006`/`STG-007` (open, below) and `STG-003`/`STG-004`/`STG-008` (already
  fixed). No action beyond those.

### Still OPEN — re-verified genuinely blocked, unchanged

- **`STG-001`, `STG-006`, `STG-007`, `STG-031`** (background/panel/chip/TIME-UP-band fills —
  `#08090d`/`#0c0e14`/`#12141c`/`#1c0c0e`) — confirmed no `design2::MANIFEST` swatch matches any of
  the four hexes (checked `tokens.rs` directly: `BASE`/`SURFACE`/`ELEVATED`/`INSET` are all
  *close* neutrals but none is an exact match). Minting one is the four-surface lockstep the
  original audit's §6.1 Step 4 flags by name (operator `dist/app.css`, the Rust manifest, this
  struct, and the Flutter `design_tokens.dart`, cross-checked by
  `design2_palette_is_pinned_across_surfaces`) — genuinely out of scope for a single-crate ticket.
  **Recommend a dedicated cross-surface token batch** (desktop + mobile + operator UI, one review).
- **`STG-033`** (worship TIME-UP band height — Figma's `374:159` band is 100px, 7px shorter than
  the running band's 107px) — re-verified unchanged: `compose_worship` still uses one `band_h`
  (`0.19·h`) for both states. Left open for the same reason the 2026-08-24 batch left it: the
  Figma difference is content-driven (the TIME-UP band's content is shorter, so its frame is
  shorter), not a fixed value the implementation should hard-match — auto-sizing the band to its
  content is a real layout change for a Low-severity, ~1%-of-frame-height difference, not a value
  substitution like the rest of this batch.
- **`STG-002`** (the stage `muted` ink) — **Q2** unresolved: Figma's `#6b7383` (AA-large only) vs.
  the mobile precedent `#a7aebe` (AA-normal). Both candidates already exist as named `design2`
  tokens (`TEXT_MUTED`, `TEXT_SECONDARY`), so the only blocker is the owner's choice — this is a
  design/accessibility trade-off, not a missing-plumbing question, and is not decided here.
- **`STG-016`** (per-output region toggles) — explicitly out of scope per the FR-059 "selected
  outputs only" reading already recorded in the 2026-08-24 batch.
- **`STG-029`, `STG-036`, `STG-052`, `STG-058`, `STG-059`, `STG-060`** (ink/data half) (the
  `· Sermon` suffix, its TIME-UP counterpart, the scripture panel sub-caption, and the timer-only
  footer's two-tone ink) — confirmed by reading `selahcue-app::controller` and
  `selahcue-core::plan`: the active `Timer` carries no link back to the `PlanItem` it belongs to
  (no segment name, no scheduled end time reaches `TimerView`/`StageContext`). Real cross-crate
  data plumbing — and likely an operator affordance to name/schedule a segment — genuinely out of
  scope for this ticket. `STG-058`/`STG-060`'s ink half is additionally blocked on **Q2** (the
  two-tone footer needs both muted-ink candidates in different roles).
- **`STG-050`** (scripture pill states beyond ON TIME — `HURRY`, `TIME UP`) — **Q4** unresolved:
  approve the implementation's invented strings, or supply others.
- **`STG-069`** (the simplified single-line message header) — **Q7** unresolved: sketch or a real
  alternate treatment.
- **`STG-068`** (message-overlay de-emphasis mechanism — a translucent scrim vs. the design's
  re-rendered, faded-content approach) — a compositing-architecture difference, not a token/data
  gap: the design's approach means the underlying content must know it's being de-emphasised and
  re-render itself differently, not just receive an overlay on top. Left as a design/architecture
  question rather than guessed at.

### Totals (this pass)

| | Count |
|---|---:|
| Fixed this batch (code + test) | 1 (`STG-012`) |
| Closed by verification (already fixed, no code change) | 4 |
| Closed — owner decision already recorded | 1 |
| Closed — editorial resolution | 1 |
| Closed — superseded / verified non-issue | 6 |
| **Still open, re-verified genuinely blocked** | **17** |

13 of the ids this pass triaged closed without a values decision; the 17 that remain open are
blocked on exactly what the 2026-09-20 reconciliation predicted: four on a cross-surface token
batch plus one content-driven layout item in the same neighbourhood (`STG-001/006/007/031/033`),
one on Q2 (`STG-002`), one on scope (`STG-016`), six on data plumbing not yet built (two also on
Q2), two on unresolved owner questions (Q4, Q7), and one on an architecture choice (`STG-068`).
None of the ids this pass reviewed needed a value invented on the spot; every open item above
names the exact decision or dependency it is waiting on.
