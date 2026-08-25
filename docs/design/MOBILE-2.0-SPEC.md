# SelahCue Controller — Mobile "Design 2.0" UI Spec (implementation-ready)

Status: **design complete — ready for engineering** · Author: UI/UX (Uma), 2026-08-17
Figma file: `SYQn5hFY8YVQKm3c6rw0eJ` · Frames: `342:124` (base surfaces) · `355:124` (role homes) ·
`357:124` (enforcement states) · `363:124` (navigation & config)
Companions: [DESIGN-2.0-HANDOFF.md](DESIGN-2.0-HANDOFF.md) · [DESIGN-TOKENS.md](DESIGN-TOKENS.md) ·
[UX-CANONICAL.md](UX-CANONICAL.md) · [DETECTIONS-VIEW-spec.md](DETECTIONS-VIEW-spec.md) ·
[MOBILE-DESIGN-CLEANUP-handoff.md](MOBILE-DESIGN-CLEANUP-handoff.md)
Code seam: `implementation/mobile/selahcue_controller/lib/`

> **What this is.** The complete, measured translation of the four mobile Design 2.0 frames into
> Flutter-buildable specification. Every colour, size and gap below was either **read off the Figma
> render at 1:1** (marked *measured*) or is a **stated reasoned default** where the frames do not
> settle it (marked *default*). Nothing here is guessed.
>
> **What this is not.** It does not change the palette. `DesignTokens.d2*` is a **pinned
> cross-surface contract** (`selahcue-present/tests/test_tokens.rs::design2_palette_is_pinned_across_surfaces`
> greps `design_tokens.dart` for `d2<Camel> = Color(0xFF<HEX>)` for every entry in
> `tokens::design2::MANIFEST`). **Do not rename, remove, or add a `d2*` constant while building this
> spec.** §2.6 lists the two places the frames reach for a colour the palette does not have, and
> gives a token-only way to build each without touching the palette. If the owner instead wants the
> palette extended, that is a four-surface story (Rust `MANIFEST` + `app.css` `--sc-*` + Dart +
> WCAG re-audit), not a mobile change.

### Reading conventions

| Marker | Meaning |
|---|---|
| *measured* | Sampled from the Figma render at 1:1 (pixel value / node geometry from `get_metadata`). |
| *default* | The frames don't settle it. A reasoned value is given with its rationale. Change freely with cause. |
| **A11Y-FIX** | The frame's own value fails WCAG. Build the fix, not the frame. Contrast maths in §6. |
| ⚠ | A conflict between two frames, or between a frame and the shipped app. Resolution given. |

---

## 1. Surfaces in scope

| # | Surface | Frame node | Code seam |
|---|---|---|---|
| 1 | Pairing / discovery (+ QR scan, waiting, error) | `342:133` | `views/pairing_view.dart` |
| 2 | App shell: app bar · connection banner · emergency strip · bottom tab bar | `363:133` | `views/controller_view.dart`, `views/widgets/mobile_widgets.dart` |
| 3 | Live tab | `342:189`, `363:149`, `356:187` | `views/tabs/live_tab.dart` |
| 4 | Plan tab | (no dedicated frame — derived, §4.4) | `views/tabs/plan_tab.dart` |
| 5 | Scripture tab | `343:128`, `355:217` | `views/tabs/scripture_tab.dart` |
| 6 | Timer tab | `343:169`, `356:139` | `views/tabs/timer_tab.dart` |
| 7 | Detections — "Needs your approval" | `355:219` (card) | `views/detections_view.dart` |
| 8 | Config / About sheet | `366:128` | `ConfigSheet` in `controller_view.dart` |
| 9 | Permission blocked (sheet) | `357:218` | **new** |
| 10 | Role changed — live (banner) | `358:128` | **new** |
| 11 | Action rejected (toast) | `358:149` | partially `ConnectionBanner` |
| 12 | Access removed | `358:166` | `AccessRemovedScreen` |
| 13 | Role-scoped bottom tabs | `364:128` | `models/tab_scope.dart` |

---

## 2. Token mapping — legacy `DesignTokens.*` → Design 2.0 `d2*`

### 2.1 The complete swap list

Every legacy member currently referenced in `lib/` (usage counts from the tree at time of writing).

| Legacy token | Hex | Uses | → Design 2.0 | Hex | Semantic reason |
|---|---|---:|---|---|---|
| `bgBase` | `#0E1116` | 12 | `d2Base` | `#0B0D12` | App background. 1:1. *measured — every frame's screen field is `#0B0D12`.* |
| `bgPanel` | `#171B22` | 15 | **split** — see §2.2 | — | **NOT 1:1.** `bgPanel` is currently doing three jobs. |
| `border` | `#2B323D` | 16 | `d2Border` | `#262A34` | Hairlines. 1:1. *measured on every card/row/field edge.* |
| `textPrimary` | `#EEF1F6` | 31 | `d2Text` | `#F4F6FB` | Primary text. 1:1. |
| `textMuted` | `#9AA4B2` | 48 | `d2TextSecondary` | `#A7AEBE` | **NOT `d2TextMuted`.** See §2.3 — this is the single most dangerous mapping in the migration. |
| `accentBrand` | `#5B6BD6` | 7 | `d2Primary` | `#6E5CF0` | Brand/seed colour, primary fills, selection. 1:1 as a *fill*; **never as text on dark** (§6.4). |
| `previewInk` | `#2BB673` | 10 | `d2Preview` | `#35C08A` | Staged/safe ink — text, icons, borders on dark. 1:1. |
| `liveInk` | `#EF4444` | 14 | `d2Live` | `#FF4D4D` | On-air ink. 1:1. |
| `warnInk` | `#F2B53C` | 8 | `d2Warn` **or** `d2Gold` — see §2.4 | `#F5A524` / `#F2B84B` | **NOT 1:1.** Legacy `warnInk` carries both "warning" and "scripture" today; Design 2.0 splits them. |
| `previewFill` | `#0F7B6C` | 8 | **`d2PreviewSoft` + `d2PreviewBorder` + `d2Preview` ink** | — | **NOT 1:1.** White-on-fill → ink-on-tint. §2.5. |
| `liveFill` | `#A3283A` | 7 | **`d2LiveSoft` + `d2LiveBorder` + `d2Live` ink** | — | **NOT 1:1.** §2.5. |
| `warnFill` | `#9A5B00` | 4 | **`d2WarnSoft` + `d2WarnBorder` + `d2Warn` ink** | — | **NOT 1:1.** §2.5. |
| `outputBlack` | `#000000` | 1 | `DesignTokens.outputBlack` (unchanged) | `#000000` | The audience matte is real black, not a UI neutral. Keep as-is. |

Two `d2*` members are **new roles with no legacy equivalent** and must be adopted:

| New token | Hex | Where it is used |
|---|---|---|
| `d2Elevated` | `#1C1F28` | Every secondary control: Prev/Next, Pause/Reset, Clear, Reject, Got it, quiet-cue buttons, view-only banner, toast card, inactive toggle track. *measured.* |
| `d2Inset` | `#0F1116` | Wells and inputs: the HH:MM:SS custom-time well, segmented-control track, roles-that-can-approve card, lock-note rows. *measured.* |
| `d2AccentSoft` | `#201F3A` | The brand/admin role chip tint. *measured.* |
| `d2InfoSoft` / `d2Info` | `#10222B` / `#38BDF8` | The "reconnecting…" row and the Administrator footer note. *measured.* |
| `d2GoldSoft` / `d2Gold` | `#2A2415` / `#F2B84B` | Scripture identity: verse numbers, references, the Scripture-role chip, the approval card. *measured.* |
| `d2BorderStrong` | `#363B47` | *default* — reserved for the focus/emphasis hairline on a selected but unfocused row. No frame uses it; do not invent a use. |

### 2.2 `bgPanel` is not 1:1 — it splits three ways

`DesignTokens.bgPanel #171B22` is currently the app-bar fill, the card fill **and** the secondary
button fill. Design 2.0 gives those three jobs three different neutrals (*all measured*):

| Current use of `bgPanel` | → Design 2.0 | Evidence |
|---|---|---|
| **App bar background** (`controller_view`, `detections_view`) | `d2Base` `#0B0D12` — the bar is **flush with the screen**, no fill, no elevation | `363:137` app-bar band sampled `#0B0D12`, identical to the body field |
| **Bottom nav bar background** | `d2Surface` `#14161D` + **1 px `d2Border` top edge** | `363:176` sampled `#14161D`; the hairline at its top row sampled `#262A34` |
| **Card / panel fill** (transcript card, detection card, host row, About group) | `d2Surface` `#14161D` | every card in all four frames |
| **Secondary button fill** (`_TransportBtn`, `_NavBtn`, `_EmgButton` idle) | `d2Elevated` `#1C1F28` | `342:211` Prev, `343:193` Pause, `363:169` BLACKOUT all sampled `#1C1F28` |
| **Popup menu / sheet surface** (`_TranslationPicker`, `ConfigSheet`) | sheet body `d2Base`; grouped cards inside it `d2Surface` | `366:134` sheet field `#0B0D12`, PREFERENCES/ABOUT groups `#14161D` |

### 2.3 `textMuted` maps to `d2TextSecondary`, **never** to `d2TextMuted`

This is the trap. The names line up; the values do not.

- Legacy `textMuted #9AA4B2` measures **6.84–7.50 : 1** on the legacy surfaces — it is a
  *secondary body* colour, and 48 call sites use it for hints, captions, sub-labels and footnotes.
- `d2TextMuted #6B7383` measures **3.45–4.08 : 1** on the Design 2.0 surfaces (§6.1). It clears
  AA-large only. DESIGN-TOKENS' own a11y note gates it at 3.0 and calls it "tertiary/label-only".

**Rule: `DesignTokens.textMuted` → `d2TextSecondary #A7AEBE` at all 48 sites.** No exceptions.

**`d2TextMuted` is not used for any text in the mobile app.** The frames do reach for it — lock-note
rows, the Config overlines and label column, inactive tab labels, sub-labels under buttons — and in
every one of those places it fails AA-normal at the size drawn. Those are marked **A11Y-FIX**
throughout §4 and resolved to `d2TextSecondary`. Reserve `d2TextMuted` for non-text decoration only
(e.g. the view-only badge dot), where no reading is required.

### 2.4 `warnInk` splits into `d2Warn` and `d2Gold`

Legacy `warnInk #F2B53C` is used for two unrelated meanings today. Design 2.0 separates them and the
separation is load-bearing (DESIGN-2.0-HANDOFF §2: gold is the "Selah" signal and **never means
status**).

| Current call site | Meaning | → |
|---|---|---|
| `scripture_tab.dart` `_VerseRow` verse number | scripture identity | **`d2Gold #F2B84B`** *(measured: `343:149` verse number sampled `#F2B84B` on `#10231C`)* |
| `timer_tab.dart` warn readout colour | timer approaching zero | **`d2Warn #F5A524`** |
| `scripture_tab.dart` `_DetectionBanner` icon/label/border | needs-attention | **`d2Warn`** |
| `controller_view.dart` `RoleBadge` colour for `assistant` | role identity | **`d2Gold`** *(measured: the Scripture-role chip in `343:132` and `364:188` is the gold family, not amber)* |
| `ConfigSheet` Status = "Reconnecting…" | warning | **`d2Warn`** |

Because `d2GoldSoft` and `d2WarnSoft` are the same hex (`#2A2415`) the *tints* are indistinguishable;
only the ink and the border differ (`d2WarnBorder #4A3A15` serves both — the palette has no separate
gold border, and the frames use `#4A3A15` behind gold, *measured* on the Scripture role chip).

### 2.5 The fill→tint inversion — and what `StatusBadge` becomes

**Today:** `previewFill / liveFill / warnFill` are deep, saturated hexes that carry **white** text.
They were audited as white-on-fill ≥ 4.5:1. Every chip, badge and banner in the app is built that way.

**Design 2.0 inverts this**: a bright ink sits on a soft same-hue tint with a same-hue border. The
saturated fill only survives in two places — the pressed/armed state of a destructive control, and
the "Send TIME UP" button — and **both need a dark label, not white** (§6.2).

The migration is therefore *one fill token → three tokens plus a text-colour flip*:

| Legacy | → fill | → border | → label |
|---|---|---|---|
| `previewFill` + white | `d2PreviewSoft #10231C` | `d2PreviewBorder #1C3A2E` | `d2Preview #35C08A` |
| `liveFill` + white | `d2LiveSoft #2A1416` | `d2LiveBorder #5A2327` | `d2Live #FF4D4D` |
| `warnFill` + white | `d2WarnSoft #2A2415` | `d2WarnBorder #4A3A15` | `d2Warn #F5A524` |

#### `StatusBadge` → `StatusChip`

`views/widgets/mobile_widgets.dart` currently ships:

```
StatusBadge({required String text, required Color color})
  // solid `color` fill, radius 4, 10/w800/+0.6, Colors.white
```

That signature cannot express the new chip — the caller passes one colour and gets white text.
**Replace it with a tone-driven chip.** Suggested API (naming is the engineer's call; the *shape* is not):

```
enum StatusTone { live, preview, warn, gold, info, brand, neutral }

StatusChip({
  required String text,
  required StatusTone tone,
  bool dot = false,        // leading 7 px filled circle in the ink colour
})
```

Per-tone triple (*all measured*):

| Tone | fill | border | ink | Used by |
|---|---|---|---|---|
| `live` | `d2LiveSoft` | `d2LiveBorder` | `d2Live` | app-bar `● LIVE`, plan-row LIVE, monitor LIVE header |
| `preview` | `d2PreviewSoft` | `d2PreviewBorder` | `d2Preview` | PAIRED, RUNNING, PREVIEW, `94%` confidence, Producer role chip |
| `warn` | `d2WarnSoft` | `d2WarnBorder` | `d2Warn` | detections count badge, PAUSED |
| `gold` | `d2GoldSoft` | `d2WarnBorder` | `d2Gold` | Scripture-role chip |
| `info` | `d2InfoSoft` | `Color.lerp(d2InfoSoft, d2Info, .16)` — §2.6 | `d2Info` | Stage-manager role chip, "reconnecting" row |
| `brand` | `d2AccentSoft` | `d2PrimaryHover` @ 50 % over fill | **`d2Text`** — **A11Y-FIX**, §6.5 | Administrator/Operator role chip |
| `neutral` | `d2Elevated` | `d2Border` | `d2TextSecondary` | Viewer/Unknown role chip, view-only marker |

Geometry (*measured*): height **23**, horizontal padding **10**, radius **pill (999)**, label
**11 / w800 / +0.6**, dot **7 px** with **6 px** gap. `RoleBadge` chips run one step up: height **27**,
label **12 / w700 / +0.2**, dot **8 px** (*measured* `364:130`).

> **Never colour alone (WCAG 1.4.1).** Every chip keeps its text label. The dot is an *additional*
> cue, never a replacement.

### 2.6 The two colours the frames use that the palette does not have

Both are called out loudly because the palette is pinned.

1. **The "on-air wash"** — the Live/Preview monitor card and the on-air verse card are filled with a
   vertical gradient whose top stop *measures* `#231B48` and whose bottom stop resolves to
   `d2Base #0B0D12` (`342:202`, `363:155`, `363:162`, `355:149`, `355:178` — all identical).
   `#231B48` is **not** a `d2*` token; the nearest is `d2AccentSoft #201F3A`.
   **Recommendation: build it as `LinearGradient(begin: topCenter, end: bottomCenter, colors: [d2AccentSoft, d2Base])`.**
   The delta is 14 in the blue channel and invisible behind the 18/w700 verse text that sits on it
   (measured contrast on the wash: body `15.47 : 1`, gold reference `8.88 : 1` — both unaffected).
   If exact Figma fidelity is required instead, declare a **private** `const _onAirWash = Color(0xFF231B48)`
   in the widget file — **not** in `DesignTokens`, because a Dart-only member creates surface drift
   the project forbids ("change all surfaces together", DESIGN-TOKENS).

2. **`info-border`** — `d2Info` has an ink and a soft tint but **no border member**, while
   live/preview/warn all have one. The frames draw `#1C3A4A` (*measured*, the Stage-manager role chip
   and the reconnecting row). Note `#1C3A4A` is exactly the preview-border pattern with a blue
   B-channel.
   **Recommendation (no palette change): `Color.lerp(d2InfoSoft, d2Info, 0.16)` ≈ `#16394A`** —
   the same construction reproduces `d2PreviewBorder` from its pair to within 6/255, so it is the
   palette's own rule, not an invention.
   **Escalation (owner decision, §7-Q1): add `d2InfoBorder #1C3A4A`.** That is a four-surface story:
   `tokens::design2::MANIFEST` + `--sc-info-border` in `app.css` + `d2InfoBorder` in
   `design_tokens.dart` + re-run `design2_palette_is_pinned_across_surfaces` and
   `design2_palette_meets_wcag_aa`.

### 2.7 Material theme seed

`main.dart` seeds `ColorScheme.fromSeed(seedColor: DesignTokens.accentBrand)`. Change the seed to
`d2Primary`, and set `scaffoldBackgroundColor: d2Base`, `dividerColor: d2Border`. Everything else in
this spec is explicit and does not rely on the generated scheme.

---

## 3. Component specs

Global: **radius 14** for cards, **12** for rows and full-width buttons, **8** for compact controls,
**999** for chips (*measured*, §3.10). Borders are **1 px** and always a token colour — the app is
flat; **no shadows anywhere**. Minimum touch target **48 × 48 dp** (satisfies both NFR-026's ≥44 pt
and MOBILE-DESIGN-CLEANUP §1's 48; §6.6 lists every frame element that is under it today).

### 3.1 Button

| Variant | Fill | Border | Label | Height | Radius |
|---|---|---|---|---|---|
| **primary** | `d2Primary #6E5CF0` **flat** — **A11Y-FIX**, see box | none | `Colors.white`, 15/w700 (compact) · 17/w800/+0.4 (full-width) | 48 (compact) · 54 (full-width CTA) | 12 |
| **secondary** | `d2Elevated #1C1F28` | `d2Border` 1 px | `d2Text`, 15/w600 | 48–54 | 12 |
| **ghost** | transparent | none | `d2TextSecondary`, 14/w600 | 48 | 12 |
| **danger** | `d2LiveSoft #2A1416` | `d2LiveBorder #5A2327` 1 px | `d2Live`, 15/w700 | 48–54 | 12 |
| **danger-armed / engaged** | `d2Live #FF4D4D` solid | none | **`d2LiveSoft #2A1416`**, 15/w800 — **A11Y-FIX** (white is 3.27:1) | 48–54 | 12 |
| **success (GO LIVE)** | green gradient, left→right `#3DD299 → #27A478` (*measured* `342:215`, `363:165`, `356:211`) | none | **`d2PreviewSoft #10231C`**, 17/w800/+0.4 — **A11Y-FIX** (white is 1.93:1 at the light end) | 54 | 12 |
| **disabled (any variant)** | unchanged | unchanged | unchanged | — | wrap in `Opacity(0.4)` (*measured*: the rejected-state GO LIVE renders the gradient at exactly 40 %) |

> **A11Y-FIX — the primary violet gradient cannot carry white text.**
> DESIGN-2.0-HANDOFF §4 specifies "primary (violet gradient)" and the frames draw
> `d2PrimaryHover → d2Primary` left→right (*measured*: Request access `#7D6DFE→#6D5BEF`, Scan QR
> `#7C6CFC→#6D5BEF`, Start `#7C6CFC→#6F5CF0`, Next line `#7C6CFC→#6E5CF0`).
> White on `d2PrimaryHover` is **3.78 : 1** — it fails AA-normal, and the label sits over the light
> half. White on flat `d2Primary` is **4.72 : 1** and passes; that is the pairing the handoff's own
> §6 audit blessed. **Ship flat `d2Primary`.** Owner option B in §7-Q2 keeps the gradient by adding
> a darker violet stop; do not do that unilaterally.
> Note the frames are already inconsistent here — the compact Connect button (`342:158`) is *measured*
> flat `#6E5CF0`, so flat primary is inside the design's own vocabulary.

The **success gradient is safe** at both ends with the dark ink: `8.50 : 1` light end,
`5.21 : 1` dark end. Keep the gradient there.

### 3.2 StatusChip / RoleBadge

See §2.5. Nothing further.

### 3.3 KindBadge (plan-item kind)

*default* — no mobile frame draws it; derived from DESIGN-2.0-HANDOFF §4 and the desktop console.
Fill `d2Inset`, border `d2Border` 1 px, radius **6**, padding 6 × 3, label **10 / w800 / +0.8** in:
SONG → `d2PrimaryHover`; SCRIPTURE → `d2Gold`; SECTION → `d2TextSecondary`; ANNOUNCEMENT → `d2Info`.
Today `plan_tab.dart` renders the kind as plain uppercase muted text; upgrading it to a badge is
optional in this pass — if it stays plain text it must move to `d2TextSecondary`.

### 3.4 Card

Fill `d2Surface #14161D`, border `d2Border` 1 px, radius **14** (*measured*: 13-px corner inset on the
QR card and the timer well), padding **13** (*measured* on the transcript and detection cards; round
the existing 12 up to 13 or keep 12 — the difference is invisible, **default: keep 12** to avoid
churn). Header pattern = overline + optional count chip, overline **11 / w800 / +0.8** in
`d2TextSecondary` (**A11Y-FIX**; the frames use `d2TextMuted`).

### 3.5 ListRow

Height ≥ **48**, radius **12**, padding 12 × 10, title **15 / w600** `d2Text`, sub-label
**12 / w400** `d2TextSecondary`.

| State | Fill | Border |
|---|---|---|
| default | `d2Surface` | `d2Border` 1 px |
| **live-tint** | `d2LiveSoft` | `d2Live` **1.5 px** |
| **staged-tint** | `d2PreviewSoft` | `d2PreviewBorder` 1 px, **or** `d2Preview` 1.5 px when the row is the single staged item (*measured*: the staged verse row `343:153` uses `#1C3A2E`; the monitor card uses full `#35C08A`) |
| **selected** | `d2Surface` | `d2PrimaryHover #7E6EFF` **2 px** (*measured*: the paired host row `342:143`) |
| disabled / removed | as default, wrapped in `Opacity(0.5)` (*measured*: the "🔒 removed" rows in `358:136` are exactly 50 %) |

Both tinted states also carry a text label (LIVE / PREVIEW chip or the ✓ stage affordance) — colour
is never the only signal.

### 3.6 Input

Fill `d2Surface` for a search/text field on a `d2Base` screen (*measured* `343:141`, `355:232`);
`d2Inset` when the field sits **inside** a card. Border `d2Border` 1 px, radius **12**, height **44**
(*measured* 41–44; **use 48** to meet the touch minimum — *default*). Text **15 / w400** `d2Text`;
placeholder `d2TextSecondary`; leading `⌕` glyph 17 px `d2TextSecondary` at 14 left inset.
Focus: border → `d2PrimaryHover` 2 px (§6.7).

**Select** (translation picker): same fill/border/radius, height **48**, width hugs, label
**15 / w600** in `d2Gold` when it names a Bible translation (*measured*: `343:145` "KJV" is
`#F2B84B`), otherwise `d2Text`; trailing `▾` 11 px `d2TextSecondary`.

### 3.7 Toggle

*measured* `366:167`: **42 × 24**, knob **18** white, track radius pill.
ON = `d2Primary` track. OFF = `d2Elevated` track + `d2Border` 1 px.
The switch alone is 42 × 24 — **the whole 50-dp row is the tap target** (*measured* row height 50).

### 3.8 SegmentedControl

*measured* `356:188`: track `d2Inset` + `d2Border` 1 px, 3 px inset, radius track **9** / segment **7**.
Active segment = **flat `d2Primary`** (*measured* — no gradient here), label `Colors.white` 13/w700.
Inactive label `d2TextSecondary` 13/w600.
Frame draws segments 86 × 31; **spec track height 48, segment height 42** (*default*, touch minimum).

### 3.9 Monitor / OutputCard

*measured* `363:150`, `356:197`, `342:202`:

- Chip **above** the card, not inside it: `StatusChip(PREVIEW, preview, dot)` / `StatusChip(LIVE, live, dot)`,
  17 px tall, with **6 px** gap to the card.
- Card: the on-air wash (§2.6), radius **12**, border **2 px** — `d2Preview` for preview,
  `d2Live` for live.
- Inside: reference/title overline **11 / w800 / +0.8** in `d2Gold` (scripture) or `d2TextSecondary`
  (song/section) at 12 left/12 top; body **15 / w700** `d2Text`, max 2 lines, ellipsised;
  optional footer `● LIVE` **11 / w800** in **`d2Live`** — **A11Y-FIX**: the frames render this
  footer in `d2LiveBorder #5A2327` on the wash, which measures **1.42 : 1**. Use `d2Live`
  (**5.35 : 1**).
- Idle: body reads "Nothing staged" / "Output idle" in **15 / w500** `d2TextSecondary`, no wash —
  plain `d2Surface` fill.
- **Blackout overlay** (live card only): the existing pattern survives — a bordered
  `BLACKOUT — OUTPUT DARK` pill (1 px `d2Live`, white 11/w800/+0.8) above content dimmed to
  `Opacity(0.3)`, over `outputBlack`.
- Layout: side by side above `kSideBySideBreakpoint` (520), stacked with the transport between on a
  phone — **keep the shipped `LayoutBuilder` behaviour**; the frames draw both.

### 3.10 Radii, spacing, type — the measured scale

| Radius | Value | Where (*measured* corner inset) |
|---|---|---|
| Card / sheet group | **14** | QR card 13, timer well 13 |
| Row / full-width button / input / monitor | **12** | Prev 12, Blackout 12, verse row 12, search 11, UP NEXT 11 |
| Compact button / chip-button / kind badge | **8** | Connect 5–6 |
| Pill / status chip / toggle / drag handle | **999** | PAIRED 8 on a 23-tall pill |

| Spacing | Value | Evidence |
|---|---|---|
| Screen horizontal gutter | **20** | *measured* — content is x=20 w=350 in a 390 frame, in all four frames. ⚠ the shipped app uses 14/16; change uniformly |
| Vertical gap between blocks | **14** | *measured* — the gap is 14 between every stacked block in `342/343/355/356` |
| Gap inside a 2-up row | **10** | *measured* (170 + 10 + 170 = 350) |
| Gap inside a 3-up row | **9** | *measured* (110.67 × 3 + 9 × 2 = 350) |
| Overline → its content | **14** | *measured* |
| Card inner padding | **12–13** | *measured* |
| App bar height | **56** | *default* (frame band is 54 + status bar) |
| Bottom tab bar | **64** + safe area, items **≥ 48** | *measured* items 53 tall |

| Type role | Size / weight / tracking | Colour |
|---|---|---|
| Screen title (app bar) | 20 / w700 / 0 | `d2Text` |
| Section heading | 17 / w700 | `d2Text` |
| Overline | 11 / w800 / +0.8 | `d2TextSecondary` |
| Row title | 15 / w600 | `d2Text` |
| Body / verse | 14 / w400 / line-height 1.35 | `d2Text` |
| On-air verse | 18 / w700 / line-height 1.35 | `d2Text` |
| Secondary / caption / hint | 12–13 / w400 | `d2TextSecondary` |
| Button label | 15 / w600 · 17 / w800 / +0.4 for the primary CTA | per §3.1 |
| Chip label | 11 / w800 / +0.6 | tone ink |
| Timer readout | 68 / w800 / tabular figures | semantic (§4.6) |
| Custom-time digit | 28 / w800 / tabular | `d2Text` |
| Unit label (HOURS/MIN/SEC) | 10 / w700 / +0.8 | `d2TextSecondary` |

---

## 4. Per-screen specs

Layout order is top→bottom. Every screen: `d2Base` field, 20 gutter, 14 block rhythm.

### 4.1 Pairing / discovery — `342:133` → `pairing_view.dart`

**Order:** brand header → "Connect to a host" heading + helper → `DISCOVERED ON YOUR NETWORK`
overline + refresh → host rows → **Scan the pairing QR** primary → device-name input → *Enter an
invite manually* disclosure → QR hint card.

| Element | Spec |
|---|---|
| Brand header | 32 × 32 logo mark (violet, no tile) + "SelahCue" 20/w700 `d2Text`, 10 gap |
| Heading | "Connect to a host" 17/w700 `d2Text` |
| Helper | "On the SelahCue host, press P to start pairing. Pick it below, scan its QR, or paste the invite." 13/w400 `d2TextSecondary` |
| Overline | `DISCOVERED ON YOUR NETWORK` 11/w800/+0.8 `d2TextSecondary`; trailing 48 × 48 refresh `IconButton`, `d2TextSecondary` |
| **Host row** | ListRow, **70 tall** (*measured*), `d2Surface`/`d2Border` r12. Leading 🖥 glyph 17 px `d2TextSecondary` at x=15. Title 15/w700 `d2Text`; sub "MacBook Pro · last used today" / "Windows · 192.168.1.24" 12/w400 `d2TextSecondary`. Trailing: `StatusChip('PAIRED', preview, dot: true)` when already paired, else a **primary compact button "Connect"** 85 × 48 (*frame draws 34 — raised for touch*) |
| **Paired row** | selected ListRow state: `d2PrimaryHover` **2 px** border (*measured*) |
| QR hint card | Card `d2Surface`/`d2Border` r14, 161 tall, centred 84 × 84 QR glyph, caption "Scan the QR on the desktop to pair a new booth" 13/w400 `d2TextSecondary`, centred, 2 lines |

**States**

| State | Rendering |
|---|---|
| Loading (scanning LAN) | 18 × 18 `CircularProgressIndicator` (`d2Primary`) replaces the refresh icon. No skeleton rows. |
| Empty | "None found — make sure this phone is on the same Wi-Fi as the host, then tap refresh." 12/w400 `d2TextSecondary` in place of the row list. |
| Fingerprint-confirm dialog | Unchanged flow (security-critical). Restyle: `d2Surface` surface, title 17/w700, fingerprint `SelectableText` 20/w700 monospace `d2Text` on a `d2Inset` r8 well, checkbox "This matches the fingerprint the host shows", code field disabled until checked, actions Cancel (ghost) / Pair (primary). |
| Waiting for approval | Full-screen centred: 30 px spinner → 24 → "Waiting for the host to allow this device" 17/w600 `d2Text` → 10 → `You appear as "<name>" — the operator approves you (with a role) from the Remote Control console.` 13 `d2TextSecondary` → 6 → "This request expires in about 2 minutes." 12 `d2TextSecondary`. |
| Error | Message in `d2Live` 13/w500 below the disclosure. Field values preserved. |
| Scan route | Full-bleed camera, app bar "Scan the pairing QR", `d2Base` scaffold. |

### 4.2 App shell — `363:133`

⚠ **Three frames draw three different app bars.** `363:137` is the one labelled "matches the built
app" and is canonical for *structure*; `342`/`355` are spec-board furniture (a violet logo tile plus
the screen name) and must **not** be built. But `363:137` omits the granted-role chip, which the
shipped app carries and which every other frame shows. **Merged canonical app bar** (*default* on the
merge, *measured* on each part):

```
[ plan name or tab title ]  [● LIVE chip]        [role chip] [10:42] [ⓘ]
```

- Height **56**, background **`d2Base`**, no elevation, `titleSpacing: 20`.
- Plan name **20 / w700** `d2Text`, ellipsised; falls back to the current tab title when empty.
- `● LIVE` = `StatusChip('LIVE', live, dot: true)`, shown only when anything is on air, 8 gap.
- Role chip = `RoleBadge` (§2.5 geometry), tone per §5.3.
- Wall clock **13 / w600** `d2TextSecondary`, tabular figures.
- **ⓘ** `Icons.info_outline` `d2TextSecondary`, in a **48 × 48** `IconButton` (*frame glyph is 16 × 34 —
  raised for touch*), tooltip/semantic label "Session, settings and about".

**Connection banner** (`ConnectionBanner`, directly under the app bar, full-bleed):

| Condition | Fill | Border | Copy | Ink |
|---|---|---|---|---|
| `reconnecting` | `d2WarnSoft` | 1 px `d2WarnBorder` bottom | "Reconnecting to the host… your taps won't be sent" | `d2Warn` 12/w600 |
| `syncing` (link up, state not re-read) | `d2WarnSoft` | as above | "Syncing live state…" | `d2Warn` 12/w600 |
| command error | `d2LiveSoft` | 1 px `d2LiveBorder` bottom | server message + trailing "Dismiss" | `d2Live` 12/w400; "Dismiss" 12/w700 |
| healthy | not rendered | | | |

**A11Y-FIX:** today these are white-on-solid `warnFill`/`liveFill`. White on solid `d2Warn` is
**2.04 : 1** and on solid `d2Live` **3.27 : 1** — both fail. The soft-tint form measures 7.56 and 5.31.

**Emergency strip** (persistent, above the tab bar, on every tab **and** on the pushed detections
route). Container `d2Surface`, 1 px `d2Border` top **and** bottom, padding 12 / 8. Two buttons,
10 apart, each **48** tall, radius 12:

| Control | Idle | Armed (first tap) | Engaged |
|---|---|---|---|
| **Blackout** | `d2LiveSoft` + `d2LiveBorder` + `d2Live` "■ BLACKOUT" | `d2Live` solid + `d2LiveSoft` ink "■ CONFIRM BLACKOUT" | `d2Live` solid + `d2LiveSoft` ink "■ UN-BLACKOUT" |
| **Clear all** | `d2Elevated` + `d2LiveBorder` + `d2Live` "✕ CLEAR ALL" | `d2Live` solid + `d2LiveSoft` ink "✕ CONFIRM CLEAR" | — |

⚠ `342:218` and `356:215` give Blackout the red family and Clear the neutral; `363:168` inverts it
(BLACKOUT neutral, CLEAR ALL red). **Resolution: Blackout owns the red family** — it is the control
with an *engaged* state, so it needs a soft→solid escalation ladder, and it is the more consequential
action. Clear-all keeps a red **ink and border on a neutral fill**, which distinguishes the two at a
glance without two competing red blocks. *(Open question §7-Q3 if the owner disagrees.)*

Behaviour is unchanged from the shipped `EmergencyStrip`: arm-then-confirm with a 3 s self-disarm,
the armed command bound at arm time, un-blackout is one tap, everything disabled at `Opacity(0.4)`
while `syncing` with the reason in the semantic label.

**Bottom tab bar** (*measured* `363:176`): `d2Surface`, 1 px `d2Border` top edge, height 64 + safe
area, items ≥ 48 tall. Active icon **and** label `d2PrimaryHover #7E6EFF` (4.79 : 1 on `d2Surface`);
inactive `d2TextSecondary` (**A11Y-FIX** — the frame uses `d2TextMuted` at 3.45 : 1). Label
11 / w600. No pill indicator is drawn in the frame; **default: drop the Material indicator** and let
the ink carry selection, or keep `d2Primary @ 22 %` if the team prefers the M3 affordance — either is
acceptable, but be consistent.

Badges on a destination:
- **view-only ◐** — `Badge(smallSize: 7, backgroundColor: d2TextSecondary)`, `AlignmentDirectional.topStart`
  when a count is also present. Tooltip/semantics append " — view only".
- **pending approvals** — `Badge(backgroundColor: d2Warn, textColor: d2Base)` (**A11Y-FIX**: white on
  `d2Warn` fails; `d2Base` on `d2Warn` is 9.52 : 1), capped at `99+`, top-end corner, semantics
  append " — N need approval".

### 4.3 Live tab — `342:189` · `363:149` · `356:187`

**Order (phone):** PREVIEW monitor → transport row → LIVE monitor → "Next: …" hint → LIVE TRANSCRIPT
card.
**Order (≥ 520 dp):** monitors side by side → transport → hint → transcript.
The role-home frames (`356:197`) draw the monitors side by side even on a phone; **the shipped
stacked-with-transport-between order wins** — it puts GO LIVE under the thumb and is already tested.

| Element | Spec |
|---|---|
| Monitor cards | §3.9 |
| Transport | `◀` 64 × 54 secondary · **GO LIVE** `Expanded` 54 tall success button · `▶` 64 × 54 secondary; 8 apart. Glyphs 18 px `d2Text`, `excludeSemantics` with labels "Previous item" / "Next item". |
| UP NEXT card | `d2Surface`/`d2Border` r12, 60 tall: 64 × 38 wash thumbnail (r8) + overline `UP NEXT` 11/w800 `d2TextSecondary` + title 15/w600 `d2Text` |
| Next hint | "Next: <title>" 12/w400 `d2TextSecondary` |
| LIVE TRANSCRIPT | Card r14 `d2Surface`/`d2Border`, overline `LIVE TRANSCRIPT`, last 6 finalised lines 13/w400/1.35 `d2Text`, in-progress line *italic* `d2TextSecondary` |

**States:** view=null → centred `CircularProgressIndicator`. Nothing staged → preview card idle copy
"Nothing staged". Nothing live → "Output idle". Blackout → live card overlay (§3.9). No transcript →
section omitted entirely. `syncing` → transport at `Opacity(0.4)`, disabled, monitors keep their last
snapshot (the banner says it is stale — blanking tells the operator less). Role without
`navigate`/`goLive` → **no transport row at all** (hidden, not disabled — role gating hides).

### 4.4 Plan tab — no dedicated frame; derived

⚠ **The four mobile frames do not draw the Plan tab.** Built from the ListRow spec (§3.5), the
console's plan column (`312:124` left), and the shipped `plan_tab.dart`. Everything here is *default*.

**Order:** `SERVICE PLAN` overline → scrolling item list (6 gap) → hint footer.

Row: ListRow r12, 48 min height, padding 12 × 10. Title 15/w600 `d2Text` (1 line, ellipsised); below
it the kind badge (§3.3) or `KIND · N slides` 10/w400/+0.5 `d2TextSecondary`. Trailing
`StatusChip('LIVE', live)` or `StatusChip('PREVIEW', preview)`. Row tint per §3.5 (live wins when an
item is both).

Hint footer 12/w400 `d2TextSecondary`, one of:
- `syncing` → "Syncing live state… controls are disabled until this device is back in step with the desktop."
- no `navigate` → "Read-only — your role can view the plan but not stage it."
- `navigate` + `goLive` → "Tap to stage in Preview · double-tap to send it live"
- `navigate` only → "Tap to stage in Preview"

**States:** view=null → spinner. **Empty plan** (*missing today — add*): centred, 56 px circle
`d2Elevated` with a `list_alt` glyph `d2TextSecondary`, "No items in this plan" 17/w700 `d2Text`,
"The operator adds items on the desktop." 13 `d2TextSecondary`. View-only → rows render but are not
tappable and show no ripple.

### 4.5 Scripture tab — `343:128` · `355:217`

**Order:** detection banner (conditional) → search row (translation select + reference field) → book
suggestion chips (conditional) → loading bar (conditional) → chapter nav → verse list → footer hint.

| Element | Spec |
|---|---|
| Detection banner | `d2WarnSoft` fill, 1 px `d2WarnBorder`, r12, **min 48** tall, padding 12 × 10. `warning_amber_rounded` 18 px `d2Warn` + "N verses need approval" 13/w700/+0.2 `d2Warn` + `chevron_right` 20 px `d2Warn`. **A11Y-FIX:** today `warnFill @ 14 %` with a `warnInk` border — move to the token tint. |
| Search field | §3.6, `Expanded`, 48 tall, placeholder "Reference — e.g. gen 1 1", trailing 48 × 48 search `IconButton` |
| Translation select | §3.6, 63 × 48, label in `d2Gold` |
| Suggestion chips | `d2Surface` fill, `d2Border`, r8, 13/w400 `d2Text`, 8 gap/run-gap, ≥ 48 tall |
| Loading | 2 px `LinearProgressIndicator` in `d2Primary` under the search row |
| Chapter nav | `‹` 40 × 48 secondary · heading `ISAIAH 61 · KJV` **11 / w800 / +0.8** `d2TextSecondary` centred · `›` 40 × 48 |
| **Verse row** | ListRow, r12, padding 12 × 13. **Verse-number column ≥ 26 wide** — *measured*: `355:239` draws it 16 wide and a 2-digit number wraps to two lines. Number 13/w700 **`d2Gold`**. Text 14/w400/1.35 `d2Text`, 6 gap. Trailing stage affordance, ≥ 32 × 44 hit slop inside the row: default `→` 15 px `d2TextSecondary` on `d2Elevated` r8; staged `✓` on a solid `d2Preview` pill with `d2PreviewSoft` glyph (*measured*). |
| Row tints | staged → `d2PreviewSoft` + `d2PreviewBorder`; live → `d2LiveSoft` + `d2Live` 1.5 px (live wins) |
| Footer hint | "Tap → to stage on the operator's preview · they confirm before it goes live" 12/w400 `d2TextSecondary`, centred, up to 2 lines |

**Approval card** (Scripture-role home, `355:219` — *this is the same data as the detections queue*):
Card `d2GoldSoft` fill + **`d2WarnBorder` 1 px** + r14, padding 13. Row 1: reference
`Romans 8:28 · KJV` 15/w700 `d2Gold` + `StatusChip('94%', preview)` right-aligned. Row 2: the heard
text in curly quotes, 13/w400/1.4, 2 lines, `d2Text`. Row 3: **Approve → Live** success button
(158 × 51) + **Reject** secondary (158 × 51), 8 apart.
⚠ On the *Scripture-role home* the primary action is labelled "Approve → Live"; in the shipped
detections queue it is "Approve" and it **stages to Preview, it does not go on air** (FR-115).
**Resolution: keep "Approve" and the existing footnote** "Approving stages the verse in Preview. It
does not go on air." The frame's "→ Live" label is wrong against FR-115 and must not be built.

**States:** no `searchScripture` → centred "Scripture control is not part of your role." 13
`d2TextSecondary` (tab is hidden for those roles anyway — this is the belt-and-braces path).
Idle → "Type a reference above to browse its chapter." Fetch failed → "Couldn't load that chapter
here. You can still stage the reference directly." + Stage (secondary) / Live (success) pair.
Transient miss with a chapter on screen → snackbar `Couldn't load "<ref>".`, chapter retained.
`syncing` → rows non-interactive at `Opacity(0.4)`; the detection banner **stays enabled** (reading
the queue is always safe).

### 4.6 Timer tab — `343:169` · `356:139`

**Order:** timer card → `SET A CUSTOM TIME` + HH:MM:SS well + Start → −1:00 / +1:00 → Pause / Reset /
Stop → **Send "TIME UP" to stage** → `STAGE MESSAGE` + 3 presets (deferred, §5.4) → lock note.

| Element | Spec |
|---|---|
| Timer card | Card r14 `d2Surface`/`d2Border`, 185 tall, centred column: `StatusChip` state pill (RUNNING → preview · PAUSED → warn · TIME UP → live) → 68/w800 tabular readout → 13/w400 `d2TextSecondary` context line |
| Readout colour | running `d2Preview` · warning `d2Warn` · TIME UP `d2Live` · none `d2TextSecondary` with `–:––` |
| Context line | "Sermon · counts down to 00:00" / "warning · shown on the stage output only" / "overrun · shown on the stage output only" / "no timer running" |
| **Custom-time well** | *measured* `367:126`: `d2Inset` fill, `d2Border`, r12, 257 × 67. Three 28/w800 tabular digit-pairs `d2Text` with `:` separators 28 `d2TextSecondary`; unit labels `HOURS` `MIN` `SEC` 10/w700/+0.8 `d2TextSecondary` beneath. **Replaces the shipped minutes-only field** so hours can be set (DESIGN-2.0-HANDOFF §5.1). Each digit-pair is a tap target ≥ 48 wide opening a number keypad; the whole well is one form. |
| Start | primary compact, 81 × 48 |
| ±1:00 | two secondary buttons, 170 × 50, "− 1:00" / "+ 1:00" 15/w600 |
| Pause / Reset / Stop | 3-up secondary, 110 × 50, 9 apart. **Stop is danger** (`d2LiveSoft`/`d2LiveBorder`/`d2Live`) — *measured*. Pause swaps to "Resume" when the timer is paused. |
| **Send "TIME UP" to stage** | Full-width **danger-armed** styling: solid `d2Live` fill, r12, 81 tall. Title "Send \"TIME UP\" to stage" 17/w800 in **`d2LiveSoft`** — **A11Y-FIX**, white measures 3.27 : 1. Sub-line "Shows on the stage display only — never the audience" 12/w500 in **`d2LiveSoft` at full opacity** (5.31 : 1) — **A11Y-FIX**, the frame renders it in `d2TextMuted` on the red at **1.46 : 1**, effectively invisible. Do **not** soften it to 80 % to separate it from the title (that lands at 3.69 : 1 and fails); separate by size and weight instead. |
| Lock note | `d2Inset` fill, `d2Border`, r12, ≥ 48 tall, 🔒 + "Slides, scripture & blackout aren't in your role." 12/w400 **`d2TextSecondary`** — **A11Y-FIX** (frame uses `d2TextMuted` at 3.96 : 1) |

**States:** no timer → readout `–:––`, adjust/Pause/Stop disabled at `Opacity(0.4)`, presets and the
custom well stay enabled. `syncing` → every control disabled, readout retained. No `timer` capability
→ card + readout only, all controls hidden (tab is marked ◐).

### 4.7 Detections — "Needs your approval" route

`DETECTIONS-VIEW-spec.md` remains the authoritative behavioural spec (route construction, pop rules,
text scaling, the S1–S11 state matrix, haptics). **This section supersedes only its §4.1–§4.3**,
which deliberately pinned that surface to the legacy layer while `d2*` was unadopted. After this
migration it uses `d2*` like everything else; §4.2's "Design 2.0 successor" column is the swap list,
**corrected** as follows:

| DETECTIONS §4.2 says | Correction |
|---|---|
| `textMuted → d2TextSecondary` | ✔ correct — this spec agrees |
| `warnFill → d2WarnSoft` | ✔ correct, **plus** a 1 px `d2WarnBorder` and the label flips to `d2Warn` |
| `previewFill → d2Preview` (Approve fill) | ✘ **the label must flip to `d2PreviewSoft`.** White on `d2Preview` is 3.15–1.93 : 1 across the gradient. Approve becomes a **success** button per §3.1 |
| `liveFill → d2LiveSoft` (error banner) | ✔ correct, **plus** the text flips from white to `d2Live` |
| `previewInk → d2Preview` ("All caught up" tick) | ✔ correct |
| `accentBrand → d2Primary` | ✔ correct |
| §4.3 contrast table | **must be recomputed** — every row was measured against the legacy hexes. §6.1 below is the replacement. |

Component-level: count badge `StatusChip(tone: warn)`; detection card = Card (§3.4); confidence pill
stays deliberately **neutral** (`d2Inset` fill, `d2Border`, `d2TextSecondary` label) — green would
claim "staged", which is exactly what the card is asking about; Approve = success button 48 tall,
Reject = secondary 48 tall, stacking above text-scale 1.30; footnote 11/w400 `d2TextSecondary`.
Emergency strip and connection banner are carried on this route (non-negotiable — it is a screen an
operator sits on for a whole sermon).

### 4.8 Config / About sheet — `366:128`

Modal bottom sheet, `isScrollControlled`, radius 16 top, **background `d2Base`** (*measured*), drag
handle 44 × 5 `d2Border` pill. Content gutter 20.

**Order:** identity header → divider → `CONNECTION` → 4 rows → role note → Disconnect → divider →
`PREFERENCES` → 3 toggle rows → divider → `ABOUT` → 3 rows.

| Element | Spec |
|---|---|
| Identity | 44 × 44 violet logo mark (r12) + "SelahCue" 20/w700 `d2Text` + "Controller · <Role>" 13/w400 `d2TextSecondary` (**A11Y-FIX** — frame uses `d2TextMuted`; also drop the +1.5 tracking, it is body text not an overline) |
| Divider | 1 px `d2Border`, full 350 width, 28 total height |
| Overline | `CONNECTION` / `PREFERENCES` / `ABOUT` 11/w800/+0.8 `d2TextSecondary` (**A11Y-FIX**) |
| Connection row | label column **112** wide, 13/w400 `d2TextSecondary`; value 13/w500 `d2Text`; 7 vertical padding |
| Status value | "Connected" `d2Preview` · "Reconnecting…" `d2Warn` |
| Host / Role / Fingerprint | `192.168.1.60:52255` · the role label (§5.5) · `2244-0CAD-C14C`. ⚠ Role is **read-only** here — assignment lives on the desktop |
| Role note | "Your role is assigned & managed on the desktop." 12/w400 `d2TextSecondary` |
| Disconnect | full-width **danger** button, 48 tall, transparent fill + 1 px `d2Live` + `d2Live` label + `link_off` icon, "Disconnect this device" |
| Preferences group | Card `d2Surface`/`d2Border` r14 containing three 50-tall rows separated by 1 px `d2Border`; label 15/w400 `d2Text`; Toggle (§3.7) right-aligned; **the whole row toggles** |
| Preference labels | "Keep screen awake" · "Haptic feedback" · "Reduce motion" |
| About group | Card, three 48-tall rows (*frame draws 43 — raised for touch*): "Version" + `1.0.0 (128)` 13/w400 `d2TextSecondary` · "Open-source licenses" › · "Help & support" › |
| Chevrons | `›` 18 px `d2TextSecondary` |

The shipped sheet also carries "Privacy policy" and "Terms of use" rows, which the frame omits.
**Keep them** — they are store-compliance surfaces. Place them above "Open-source licenses".

### 4.9 Access removed — `358:166` → `AccessRemovedScreen`

Full-screen, `d2Base`, 28 padding, vertically centred between two `Spacer`s.

Order: 56 × 56 circle `d2LiveSoft` fill + 1 px `d2LiveBorder`, r16 (*measured — the frame draws a
rounded rectangle, not a circle*), `link_off` glyph 28 px `d2Live` → 20 → "Access removed" 22/w700
`d2Text` centred → 10 → "An administrator unpaired this device. Your role and keys are no longer
valid." 14/w400 `d2TextSecondary` centred → 18 → reassurance card: `d2PreviewSoft` fill, 1 px
`d2PreviewBorder`, r12, padding 14 × 12, `check_circle_outline` 18 px `d2Preview` + "The live service
is unaffected — the desktop keeps running." 13/w400 `d2Preview` → `Spacer` → full-width **primary**
button 54 tall, `qr_code_scanner` + "Scan QR to pair again".

Semantics: the heading is a focusable `header` so assistive tech announces the screen change.

### 4.10 Permission blocked — `357:218` (new)

A **modal bottom sheet** over the current tab, with the underlying screen dimmed by a
`Colors.black @ 28 %` scrim (*measured*: `d2Base` reads `#08090E` behind the sheet). The control that
was tapped stays visible above the sheet, rendered disabled — the operator must be able to see what
they touched.

Sheet: `d2Surface`, radius 16 top, drag handle, 20 gutter.

Order → 31 → 44 × 44 circle `d2GoldSoft` fill + 1 px `d2WarnBorder`, 🔒 glyph 22 px `d2Gold` → 14 →
**"That's not in your role"** 19/w700 `d2Text` centred → 14 → body 14/w400/1.4 `d2TextSecondary`
centred, 2 lines: *"Approving scripture needs the Scripture Operator role. You're signed in as a
Presenter."* (template: `"<Action> needs the <role> role. You're signed in as a <current role>."`) →
14 → roles card: `d2Inset` fill, 1 px `d2Border`, r12, padding 14, overline
`ROLES THAT CAN <ACTION>` 10/w800/+0.8 `d2TextSecondary`, then wrapped `StatusChip`s at 23 tall in
each role's tone, 8 gap → 14 → actions row: **Got it** secondary (170 × 48) + **Request access**
primary (170 × 48), 10 apart.

**States:** if the app cannot name the qualifying roles (older host), drop the roles card and the
body becomes "This control isn't part of your role. Ask your operator on the desktop."
**Request access** is fire-and-forget: on tap it closes the sheet and shows a snackbar "Access
request sent to the desktop."; if the host does not support the request command, **hide the button
entirely** rather than showing a dead one.

> **Never a silent dead-end.** A control the role lacks is normally *hidden*. This sheet exists for
> the cases where it cannot be — a server-side denial arriving after an optimistic tap, or a
> capability the client mirror thought it had.

### 4.11 Role changed — live — `358:128` (new)

An **inline, non-blocking banner** injected at the top of the body, under the connection banner.
Never a modal: UX-CANONICAL §3 forbids blocking modals over live-control chrome.

Banner: `d2WarnSoft` fill, 1 px `d2WarnBorder`, r12, padding 13, min 68 tall. 🔑 glyph 14 px `d2Warn`
at x=13 + 24 gap; title "Your role changed → Observer" 15/w700 **`d2Text`** (*measured*); body "An
admin updated your access · live controls were removed just now." 12/w400/1.4 `d2Warn`.

Below it, while the banner is present:
- overline `PREVIOUS CONTROLS` 10/w800/+0.8 `d2TextSecondary`
- one row per removed capability: ListRow at **`Opacity(0.5)`** (*measured*), 42 tall, label 14/w400
  `d2Text`, trailing "🔒 removed" 12/w400 `d2TextSecondary`
- a reassurance row: `d2Elevated` + `d2Border`, r12, 👁 + "You can still watch previews & the
  transcript." 13/w400 `d2TextSecondary`

**Behaviour:** the removed controls disappear from the UI **immediately** (FR-090) — the rows are a
*receipt*, not a control. The banner is dismissible and auto-dismisses after 20 s (*default*); the
role chip in the app bar has already changed. Announce via `SemanticsService.announce` at
`Assertiveness.assertive`.

### 4.12 Action rejected — `358:149` (new)

A **toast card** pushed into the same slot as the connection banner (they never coexist: a rejection
is always followed by a reconnect state).

Card: `d2Elevated` fill, 1 px `d2LiveBorder`, r12, padding 13, 57 tall. `warning_amber_rounded` 15 px
`d2Live` + title "Action rejected" 14/w700 `d2Text` + sub "Your pairing changed — reconnecting…"
12/w400 `d2TextSecondary`.

Below: explanatory copy 12/w400/1.4 `d2TextSecondary`, centred — "The desktop validates every command
at execution time. A command it can't validate is dropped — never queued to fire later out of
context." Then a status row: `d2InfoSoft` fill, 1 px info-border (§2.6), r12, 35 tall, 13 px
indeterminate spinner `d2Info` + "Reconnecting to <host name>…" 13/w400 `d2Info`.

The rejected control itself renders **disabled at `Opacity(0.4)`** while this is up (*measured*: the
GO LIVE button in `358:150` is the success gradient at exactly 40 %).

**Behaviour (FR-097):** nothing is queued or retried. The toast auto-dismisses when the link is
healthy and live state has been re-read. Reduced motion → the spinner becomes a static ring.

### 4.13 Access-request / enforcement summary

| State | Surface | Blocking? | Dismissal |
|---|---|---|---|
| Permission blocked | bottom sheet | yes, but emergency chords still reachable behind it — **do not** cover the emergency strip | Got it / scrim tap |
| Role changed — live | inline banner | no | auto 20 s or tap |
| Action rejected | inline toast | no | auto on resync |
| Access revoked | full-screen route | terminal | re-pair only |

---

## 5. Role-scoped tab matrix

### 5.1 What the design draws — `364:128` (*measured*)

`👁` = view-only · `dim` = hidden for that role.

| Designed role | Live | Plan | Scripture | Timer | More |
|---|---|---|---|---|---|
| Observer | 👁 | 👁 | 👁 | hidden | hidden |
| Worship Leader | ● | ● | hidden | 👁 | hidden |
| Scripture Op. | ● | ● | ● | 👁 | hidden |
| Timer Op. | 👁 | 👁 | hidden | ● | hidden |
| Production Op. | ● | ● | ● | ● | ● |
| Administrator | ● | ● | ● | ● | ● |

"More" groups Production/Admin-only tools: **lower thirds · macros · output health · (Admin) editable
transcript** (*measured*, `364:291`).

### 5.2 What the backend actually enforces

`models/rbac.dart` mirrors `selahcue-lan/src/rbac.rs` and enforces **four** roles. Remote paired
devices are clamped below Operator, so **three** are reachable on a phone.

| Backend role | Capabilities | Reachable on a phone? |
|---|---|---|
| `operator` | all 11 | **No** — the desktop clamps remote roles below Operator |
| `producer` | goLive, navigate, clearLive, blackout, timer, searchScripture, transcribe, monitor | Yes |
| `assistant` | searchScripture, navigate, monitor | Yes |
| `viewer` | monitor | Yes |
| `unknown` | ∅ (fail-closed) | Yes, as a deny-all fallback |

### 5.3 The buildable matrix — build exactly this

| Backend role | Designed equivalent | Live | Plan | Scripture | Timer | More | Role-chip tone |
|---|---|---|---|---|---|---|---|
| `producer` | Production Operator | ● | ● | ● | ● | **deferred** | `preview` |
| `assistant` | Scripture Operator | ● | ● | ● | 👁 | hidden | `gold` |
| `viewer` | Observer | 👁 | 👁 | **hidden** | 👁 | hidden | `neutral` |
| `unknown` | — | 👁 | 👁 | hidden | 👁 | hidden | `neutral` |
| `operator` | Administrator | ● | ● | ● | ● | **deferred** | `brand` |

This is exactly what `visibleTabsFor()` in `models/tab_scope.dart` already computes. **No change to
that function is required by this spec.**

⚠ **Two divergences from the design board, both resolved in favour of the code:**

1. **Observer: the design shows `Scripture 👁` and hides `Timer`; the code hides `Scripture` and
   shows `Timer 👁`.** The code is right. The Scripture tab's content comes from `get_chapter`,
   which is gated on `searchScripture` — a viewer would get a permanently empty browser. The timer
   readout arrives in the ordinary state poll that every role receives, so `Timer 👁` is a real,
   populated view-only surface. **Build the code's rule.** Update the Figma Observer row.
2. **Scripture Op. / Timer Op. show `Timer 👁` and `Live 👁` respectively; the code derives the same
   ◐ flags from capabilities.** No conflict — just noting the rule is derived, not hard-coded.

### 5.4 Not buildable today — deferred, do not fake

| Designed role home | Why it cannot be built | Tracking |
|---|---|---|
| **Worship Leader** (`355:165`) | No backend role grants lyric-line navigation without scripture/blackout, and **no capability exists at all** for Repeat-section or the quiet cues (Repeat / Vamp / Move on) — those are new wire commands, not a permission slice | `86ajxuf81` / `86ajxufbg` |
| **Timer Operator** (`356:128`) | `timer` is held only by `producer`, which also holds everything else. A timer-only role does not exist | `86ajxuf81` |
| **Administrator** (`356:238`) | Maps to `operator`, which the desktop **clamps** for remote devices. Also needs an editable-transcript command that does not exist | `86ajxuf81` |
| **"More" tab** (lower thirds · macros · output health) | None of these have wire commands or RBAC capabilities | `86ajxufbg` |
| **Stage messages** (`356:162`, Wrap up / 2 min / Custom…) | Engine-side committed; no mobile wire command yet | see DECISION log "Stage theme+message" |

**Do not invent client-side roles.** The client mirror is a UX affordance only; the desktop
fail-closes. Adding a phantom "Worship Leader" to `MobileRole` would make the app offer controls the
server will deny — the exact failure mode `rbac.dart`'s header warns about.

### 5.5 ⚠ "Producer" vs "Production Operator" — recommendation

| Where | Current label |
|---|---|
| Wire protocol / `rbac.rs` / `MobileRole` enum | `producer` |
| `MobileRole.label`, `RoleBadge`, shipped Config sheet | **"Producer"** |
| PERSONAS §2 / PRD §16 / Figma `366:140`, `366:153`, `364:243`, `357:241` | **"Production Operator"** |

**Recommendation: canonicalise on "Producer".**

Rationale: (a) the wire string is `producer` and is pinned cross-language by the protocol fixtures —
the label should not fight it; (b) the shipped app, the Dart enum and its tests already say
"Producer", so this is the cheaper edit; (c) the long form does not fit the chrome — the Figma frames
themselves abbreviate it to **"Production Op."** in the role chip and the tab matrix, which is the
tell that a 27 pt pill and a 68 pt tab cannot hold it.

**What has to change:** PERSONAS §2 and PRD §16 rename the role to "Producer" (keep "production
operator" as a parenthetical persona description); Figma text layers `366:140`, `366:153`,
`364:243`, `357:241` and the `355:184` role-home title update to "Producer". **No code change.**

If the owner prefers "Production Operator" instead, the cost is: `rbac.dart` `label`, the `RoleBadge`
and Config-sheet renderings, `rbac_test.dart`, this spec's §5.3 tone table, and a truncation strategy
for the chip — and the wire value still stays `producer`, so docs and protocol permanently disagree.

---

## 6. Accessibility

Bar: **AA — 4.5 : 1 normal text, 3 : 1 large text (≥ 24 px, or ≥ 18.66 px bold) and UI components.**
NFR-026. All ratios below are computed to WCAG 2.1 relative luminance from the pinned hexes.

### 6.1 Contrast — every pairing this spec uses

| Foreground | Background | Ratio | Verdict |
|---|---|---:|---|
| `d2Text` | `d2Base` / `d2Surface` / `d2Elevated` / `d2Inset` | 17.97 / 16.71 / 15.22 / 17.46 | pass |
| `d2TextSecondary` | `d2Base` / `d2Surface` / `d2Elevated` / `d2Inset` | 8.74 / 8.12 / 7.40 / 8.49 | pass |
| `d2TextMuted` | `d2Base` / `d2Surface` / `d2Elevated` / `d2Inset` | 4.08 / 3.79 / 3.45 / 3.96 | **FAIL AA-normal — not used for text** |
| `d2Live` | `d2Base` / `d2Surface` / `d2Elevated` / `d2LiveSoft` | 5.94 / 5.52 / 5.03 / 5.31 | pass |
| `d2Preview` | `d2Base` / `d2Surface` / `d2Elevated` / `d2PreviewSoft` | 8.38 / 7.79 / 7.10 / 7.08 | pass |
| `d2Warn` | `d2Base` / `d2Surface` / `d2WarnSoft` | 9.52 / 8.85 / 7.56 | pass |
| `d2Gold` | `d2Base` / `d2Surface` / `d2GoldSoft` / on-air wash | 10.86 / 10.10 / 8.62 / 8.88 | pass |
| `d2Info` | `d2Base` / `d2Surface` / `d2InfoSoft` | 9.07 / 8.43 / 7.62 | pass |
| `d2PrimaryHover` | `d2Base` / `d2Surface` | 5.15 / 4.79 | pass |
| `d2PrimaryHover` | `d2Elevated` | 4.36 | **fail** — no violet text on elevated |
| `d2PrimaryHover` | `d2AccentSoft` | 4.22 | **fail** — see §6.5 |
| `d2Primary` | `d2Base` | 4.12 | **fail** — `d2Primary` is a **fill only**, never text on dark |
| white | `d2Primary` | 4.72 | pass — the primary button |
| white | `d2PrimaryHover` | 3.78 | **fail** — why the gradient is dropped (§3.1) |
| white | `d2Live` | 3.27 | **fail** — why TIME UP / armed-emergency use `d2LiveSoft` ink |
| white | `d2Warn` | 2.04 | **fail** — why the warn banner is a soft tint, not a solid fill |
| `d2Base` | `d2Warn` | 9.52 | pass — the nav-bar approval count badge |
| `d2LiveSoft` | `d2Live` | 5.31 | pass |
| `d2LiveSoft` @ 80 % | `d2Live` | 3.69 | **fail** — never soften the ink on a solid red fill |
| white | GO-LIVE gradient (light / dark end) | 1.93 / 3.15 | **fail** |
| `d2PreviewSoft` | GO-LIVE gradient (light / dark end) | 8.50 / 5.21 | pass — the specified ink |
| `d2Text` | `d2AccentSoft` | 14.73 | pass — the brand role chip (§6.5) |
| `d2Text` / `d2Live` | on-air wash | 15.47 / 5.35 | pass |
| `d2LiveBorder` | on-air wash | 1.42 | **frame bug** — the `● LIVE` footer (§3.9) |
| `d2TextMuted` | `d2Live` | 1.46 | **frame bug** — the TIME UP sub-line (§4.6) |

### 6.2 The four measured frame bugs — build the fix, not the frame

1. `● LIVE` footer on the on-air card drawn in `d2LiveBorder` → **`d2Live`**.
2. TIME UP sub-line drawn in `d2TextMuted` on solid red → **`d2LiveSoft` @ 80 %**.
3. Lock notes, Config overlines/labels, About values, inactive tab labels, sub-labels under buttons
   drawn in `d2TextMuted` → **`d2TextSecondary`**.
4. Scripture-role chip fill drawn `#2A1416` (`d2LiveSoft`) while its border is `#4A3A15`
   (`d2WarnBorder`) — a transposition of `2415`/`1416`. → **`d2GoldSoft #2A2415`**.

### 6.3 Never colour alone (WCAG 1.4.1)

- LIVE / PREVIEW / STAGED / PAIRED / RUNNING always carry a **text label**; the dot and the border
  are additional.
- The staged verse carries a `✓` glyph, not only a green tint. The live row carries a LIVE chip, not
  only a red border.
- View-only tabs carry the word "view only" in the tooltip **and** the semantic label, not only the
  ◐ dot.
- Blackout announces its engaged state in the label itself ("UN-BLACKOUT") and via `aria-pressed`
  equivalent (`Semantics(toggled:)`).
- Timer state is a chip word (RUNNING / PAUSED / TIME UP) as well as a readout colour.

### 6.4 Semantic labels (the full set)

| Element | `Semantics` |
|---|---|
| GO LIVE | `button`, label "Go live"; disabled → "Go live, unavailable while reconnecting"; `excludeSemantics: true` |
| ◀ / ▶ | "Previous item" / "Next item", glyph excluded |
| Blackout | `button`, `toggled: blackout`, label "Blackout" / "Un-blackout" / "Confirm blackout" |
| Clear all | "Clear all" / "Confirm clear all" |
| Verse row | "Verse N" + ", staged" / ", live" |
| Stage affordance | "Stage verse N on the operator's preview" |
| Detection Approve/Reject | "Approve <reference>" / "Reject <reference>" |
| Confidence pill | "<n> percent match" (never the literal "94% MATCH" — some VoiceOver voices spell MATCH) |
| Tab destination | "<Tab>" + " — view only" + " — N need approval" |
| ⓘ | "Session, settings and about" |
| Role chip | "Role: <label>" |
| Timer readout | "<m> minutes <s> seconds remaining" — the raw `12:45` is read as a time of day |
| Monitor card | "Preview: <title>" / "Live: <title>" / "Preview empty" / "Live output idle" |
| Access removed heading | `header: true`, focused on route entry |
| Role-changed banner | `SemanticsService.announce(..., Assertiveness.assertive)` |
| Permission sheet | `namesRoute`, focus moves to the heading |
| Logo images | `semanticLabel: ''` (decorative) |

### 6.5 The one place the ink rule breaks

`d2PrimaryHover` on `d2AccentSoft` is **4.22 : 1** — the Administrator/Operator role chip fails.
**Fix: `brand`-tone chips use a `d2Text` label** (14.73 : 1) with a `d2PrimaryHover` dot and border.
The chip stays visually violet; only the letters change. All other tones keep their ink label
(lowest is live at 5.31). §7-Q4 offers the alternative (a lighter violet token).

### 6.6 Touch targets — every frame element under 48 dp

*measured* from the frame geometry. Raise all of these; the rest already pass.

| Element | Node | Frame size | Spec |
|---|---|---|---|
| "Connect" row button | `342:158` | 85 × 34 | 85 × **48** |
| Translation select | `343:144` / `355:235` | 63 × 42 / 61 × 40 | 63 × **48** |
| ⓘ app-bar action | `363:144` | 16 × 34 | **48 × 48** hit area |
| Emergency buttons | `363:169` | 170 × 39 | 170 × **48** |
| Segmented-control segment | `356:189` | 86 × 31 | 86 × **42** in a **48** track |
| Stage-message presets | `356:163` | 110 × 40 | 110 × **48** |
| About rows | `366:182` | 350 × 43 | 350 × **48** |
| "Correct" transcript chip | `360:161` | 80 × 25 | 80 × **44** min |
| Verse stage affordance | `343:151` | 15 × 34 | not an independent target — **the whole 64–83 tall row is tappable**; give the glyph ≥ 32 × 44 hit slop for the explicit stage gesture |

### 6.7 Focus, motion, scaling

- **Focus ring** (external keyboard / switch control): `d2PrimaryHover` 2 px with a 2 px offset.
  Keep it distinct from *selection*, which uses the same violet as a **border on the element itself** —
  ring + offset is the differentiator (DESIGN-2.0-HANDOFF §6).
- **Reduced motion** (`SettingsController.reduceMotion` **and** `MediaQuery.disableAnimations`):
  route transitions become zero-duration (already installed in `main.dart`); the reconnecting spinner
  becomes a static ring; the banner appears/disappears without slide; progress bars become
  indeterminate-free where a determinate value exists. **TIME UP is solid, never flashing**
  (UX-CANONICAL §5, ADR-0015) — this spec adds no flashing anywhere.
- **Text scaling** to 3.0 must not clip: Approve/Reject stack above 1.30 (existing constant
  `kStackActionsAtTextScale`); the detection banner is a `minHeight: 48` around intrinsic content,
  never a fixed box; tab labels stay single words; the timer readout is allowed to shrink-to-fit
  rather than wrap.
- **Responsive**: `ResponsiveBody` caps the control column at 560 and centres it; monitors go side by
  side at ≥ 520. Unchanged.
- **Haptics**: `SettingsScope.haptic()` on every audience-affecting commit (GO LIVE, emergency
  confirm, Approve) and on opening the detections route. Never on navigation.

---

## 7. Open design questions

Each has a recommendation. Where the recommendation is already reflected in §3–§6, it is marked
**[applied]** — the question is whether to *keep* it, not whether to build it.

**Q1 — `info-border`.** The palette has `d2Info` and `d2InfoSoft` but no border member, while
live/preview/warn all have one. The frames draw `#1C3A4A`.
**Recommendation [applied]: derive it as `Color.lerp(d2InfoSoft, d2Info, 0.16)`** and leave the
palette alone. Escalate to a real `d2InfoBorder #1C3A4A` only if the owner wants full family parity —
that is a four-surface story with a WCAG re-audit, not a mobile change.

**Q2 — the primary violet gradient.** Measured white-on-`d2PrimaryHover` is 3.78 : 1, so the
handoff's "primary (violet gradient)" cannot carry a normal-size white label.
**Recommendation [applied]: flat `d2Primary` for every primary button** (4.72 : 1).
Option B: keep the gradient and add a darker stop (e.g. `#5F4EE0`, white at 5.75 : 1) — a palette
addition, so a four-surface story. Option C: keep the gradient and require every primary label to be
≥ 19 px w800 so AA-large applies — brittle, one small button reintroduces the failure.

**Q3 — which emergency control wears the red.** `342:218` and `356:215` say Blackout; `363:168` says
Clear-all. **Recommendation [applied]: Blackout** — it is the control with an engaged state and so
needs a soft→solid ladder, and it is the more consequential action. Clear-all keeps red ink and a red
border on a neutral fill. Confirm, then fix the odd frame.

**Q4 — the brand role chip.** Violet ink on `d2AccentSoft` is 4.22 : 1.
**Recommendation [applied]: `d2Text` label with a violet dot and border.**
Option B: add a lighter violet token — palette change, four surfaces.

**Q5 — Observer's tab set.** The design gives Observer `Scripture 👁` and hides `Timer`; the code
does the opposite, for good reason (§5.3).
**Recommendation [applied]: keep the code's rule and correct the Figma row.**

**Q6 — "Approve → Live" vs "Approve".** The Scripture-role home labels the primary action
"Approve → Live", which contradicts FR-115 (an approved detection **stages to Preview** and never
auto-displays).
**Recommendation [applied]: "Approve", with the existing footnote.** Fix the Figma label.

**Q7 — the screen gutter changes from 14/16 to 20.** *measured* — all four frames use 20.
**Recommendation: adopt 20 everywhere in one pass.** A half-migrated app with two gutters looks
broken in a way neither value does. If the team would rather not touch every padding, the fallback is
to keep 16 and accept a uniform 4 dp difference from Figma — but pick one and apply it globally.

**Q8 — Plan tab has no frame.** §4.4 is derived from the ListRow primitive, the desktop console's
plan column and the shipped tab. **Recommendation: build §4.4 as written and back-fill a Figma frame
after**, so the board stops being incomplete. The empty-plan state in particular is specified here
and drawn nowhere.

**Q9 — the M3 nav indicator.** The frame shows selection carried by ink colour alone, with no pill.
The shipped app uses the Material `NavigationBar` indicator.
**Recommendation: drop the indicator and let the violet ink carry selection** (matches the frame, and
the label is already redundant with the icon). Low stakes either way — just be consistent.

**Q10 — Producer vs Production Operator.** See §5.5. **Recommendation: "Producer"**, changing docs
and Figma, not code.

---

## 8. Build order (suggested)

1. **Tokens & primitives** — §2 swap list, `StatusChip` replacing `StatusBadge`, Button variants,
   Card/ListRow/Input/Toggle/Segmented. Nothing renders differently until step 2, so this lands safe.
2. **Shell** — app bar, connection banner, emergency strip, tab bar, badges (§4.2).
3. **Tabs** — Live, Plan, Scripture, Timer (§4.3–4.6) + detections re-skin (§4.7).
4. **Pairing & Config** (§4.1, §4.8).
5. **Enforcement states** — permission sheet, downgrade banner, rejection toast, access removed
   (§4.9–4.12). Only the last one exists today.
6. **A11y sweep** — §6.1 table as a test fixture; §6.6 target audit; text scale 1.0 / 1.3 / 2.0 / 3.0
   golden pass.

Deferred and explicitly **not** in this build: the "More" tab, Worship-Leader and Timer-Operator role
homes, the Administrator home, stage messages (§5.4).
