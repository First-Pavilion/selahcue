# Design 2.0 parity audit — Theme Designer

**Role:** UI/UX Designer (Uma) · **Date:** 2026-09-20 · **Type:** read-only audit + gap spec
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` (all nodes on page `0:1`)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

The Theme Designer main canvas and inspector — the one surface named in the Phase B brief as never
having gone through the existing `CON-`/`PME-`/`STG-` audits (confirmed: none of its frame ids appear
in `DESIGN-2.0-PARITY-AUDIT-{console,presentation,stage}.md` beyond one incidental read of `317:124`
as the audience-output element-model reference in the Presentation audit).

| Frame | Name | Size | Region |
|---|---|---|---|
| `317:124` | Theme Designer — Design 2.0 | 1760×1000 | topbar + overall layout spine |
| `319:124` | (unnamed "Frame", the add-content toolbar) | 1400×52 | canvas-zone toolbar |
| `319:152` | (unnamed "Frame", the templates strip) | 1400×111 | canvas-zone footer |
| `325:124` | (unnamed "Frame", the inspector selection header) | 360×67 | inspector-zone header |
| `325:131` | (unnamed "Frame", BACKGROUND section) | 360×247 | inspector-zone |
| `325:154` | (unnamed "Frame", TYPOGRAPHY section) | 360×203 | inspector-zone |
| `325:189` | (unnamed "Frame", LAYERS section) | 360×281 | inspector-zone |

Code: `implementation/desktop/crates/selahcue-operator/dist/index.html:536-867` (`#surface-theme-designer`)
plus the `td*` functions in `app.js` (~55 functions; the canvas element model, background/typography
wiring, and layers list are the ones this audit exercised) and the `.td-*` rules in `app.css`.

### `563:201` — confirmed NOT part of this surface

The Phase A brief flagged `563:201` as a candidate fourth frame for this audit ("currently an unnamed
generic 'Frame' node… referenced elsewhere as the Theme Designer templates strip / a content-hugging
dialog — confirm before citing, rename if so"). **It is not the templates strip.** `get_metadata` on
`563:201` returns a frame titled *"Live Console — Service Timer › Stage (theme + message)"*, with body
text *"Adds the stage/confidence theme picker + production-message composer to the Live Console, as a
Timer | Stage sub-tab of the Service Timer tab."* Its contents are a **stage/confidence theme picker**
(Worship / Scripture / Timer-only template cards) and a **stage message composer** — a spec for a
sub-tab of the **Live Console's Service Timer tab**, unrelated to the Theme Designer editor audited
here. It shares vocabulary ("stage theme") with Theme Designer, which is almost certainly why the
earlier incidental read mis-filed it.

**Action taken:** none. Renaming `563:201` to a Theme-Designer-flavoured name would make this exact
mis-filing more likely for the next reader, not less — the node needs a name that reflects what it
actually is (a Live Console Stage sub-tab spec), which is outside this audit's scope to assign. Left
generically named; recorded as **Open question TD-OQ-1** below rather than acted on. This surface's
templates strip is `319:152`, confirmed by its own content (`TEMPLATES` header + 5 template cards) and
audited as such above.

The other three target nodes (`317:124`, `319:124`, `325:124`) are also generically named **"Frame"**
at their own level in Figma (only their *parent* section, `317:124` itself, carries a real name) —
along with roughly 20 other generic "Frame" nodes already noted elsewhere on this page. Renaming all of
them is a page-wide Figma hygiene pass, not a one-surface fix; flagged in **Open questions** rather than
done piecemeal here, so the naming convention lands consistently in one pass instead of drifting further
apart between audits.

## Method

`get_metadata` on `317:124` (full subtree, one call) for structure/text/geometry, cross-checked against
`implementation/desktop/crates/selahcue-operator/dist/index.html:536-867` and the `td*` functions in
`app.js`. `get_variable_defs` was not run per-frame for this surface (the presentation audit already
established, and this audit's manual reading of every colour value below confirms, that **no node on
this page carries a bound Figma variable** — every colour is a raw literal). Where a literal equals a
shipped `--sc-*` token the token is named for readability; the frame carries no such binding.

## Verdict vocabulary

Same as the existing three audits: **MATCH** / **DRIFT** / **MISSING** / **EXTRA** / **UNSPECIFIED** /
**INTENTIONAL-DEVIATION** (code deliberately, permanently departs from the frame for a non-a11y reason —
not a gap) / **A11Y-DEFECT** (the implementation fails NFR-020 regardless of the frame) /
**A11Y-CONFLICT** (the Figma pairing fails NFR-020; the frame is the defect, never "fixed" toward).
Severity: **S1** blocks correct/accessible use · **S2** visible parity break an operator would notice ·
**S3** cosmetic · **S4** informational.

---

# Summary

**12 numbered findings: TD-001…TD-012.**

| Verdict | Count |
|---|---|
| MATCH | 14 |
| DRIFT | 8 |
| MISSING | 2 |
| EXTRA | 2 |
| A11Y-DEFECT | 1 |
| UNSPECIFIED | 1 |

Severity: **1 × S1**, 9 × S2, 13 × S3, 5 × S4.

**The one S1 — TD-012, the Save theme button.** `.td-save-cta` (`app.css:1217-1224`) paints white text
on `linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary))`. This is the fourth sighting of
the exact defect the Presentation audit already named and fixed elsewhere in this codebase
(`.tb-golive`, `app.css:4505-4507`; PME-002/003 on the Figma side; PME-005 on `.pm-btn-primary:hover`) —
white on `--sc-primary-hover #7E6EFF` at the gradient's near end measures **3.78:1**, below the 4.5:1
bar for the button's 12-13px bold label (not large text). This is the button that **persists a design
to disk**; it is not a decorative control.

## Headline

Theme Designer is, structurally, one of the **best-matched** surfaces audited in this round. The
add-content toolbar, canvas geometry, LAYERS panel (drag reorder, Alt+↑/↓, eye toggle, aria-current
selection), and BACKGROUND section (including showing hex text beside every swatch — something the
Presentation inspector's colour control was found *missing*, PME-028) all match their frames closely,
several with EXTRAs that are net improvements. The gaps cluster in two places:

1. **The templates strip's content model doesn't match its own backend.** Figma `319:152` draws five
   named template cards ("Worship", "Gradient", "Midnight", "Sunrise", "Minimal"); the shipped
   `builtin_themes` command returns exactly three, named `"classic"`, `"high-contrast"`,
   `"lower-third"` (`selahcue-present/src/theme.rs:590`) — the same three-vs-five, evocative-vs-
   functional naming mismatch the Presentation audit already flagged for the *audience-output* side of
   this same theme model (OUT-009, scoped-later per `theme.rs:380-381`). **TD-002.**
2. **The recurring gradient/white-text contrast defect has reached this surface's most important
   control.** TD-012 above.

## Where the specs stand

No dedicated Theme Designer handoff doc exists in `docs/design/` — `DESIGN-2.0-HANDOFF.md` does not
name `317:124`, `319:124`, or `325:124` individually. `THEME-MODEL-spec.md` documents the underlying
data model (regions/elements/background/typography) that both this surface and the audience-output
compositor implement against, and is accurate as far as it goes, but is not a UI spec for this screen —
it does not describe the topbar, the templates strip, or any pixel geometry. This is worth recording as
a gap in the documentation itself, not just in the UI (see **Open questions**).

---

# Frame `317:124` — Topbar (h 57)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Brand row: 31px icon + "SelahCue" 14px + `▾` | `317:127-130` | Lives in the global app header per the app's own convention (same relocation the Presentation audit found and accepted for `329:127-130`) — `index.html:64` region, not re-drawn inside `#surface-theme-designer` | MATCH (relocated by design, consistent with the rest of the shell) | S4 |
| — | Vertical divider + "Theme Designer" surface label | `317:131-132` | `.topbar-divider` / `#surface-label`, `index.html:63-64` | MATCH | S4 |
| — | Topbar bar: `justify-content: space-between`, implied padding | `317:125`, h 57 | `.td-header` (`app.css:1174-1179`): `padding: 11px 18px`, `background: var(--sc-surface)`, `border-bottom: 1px solid var(--sc-border)` | MATCH | — |
| **TD-001** | `⧉ Duplicate` | `317:134-135`: 82×31, "Duplicate" 12px | `#td-duplicate` `index.html:547` + `.td-header-actions button:not(.td-save-cta)` (`app.css:1203-1210`): `padding: 8px 13px`, r9, `--sc-elevated` fill, `--sc-text-secondary` label — includes a `⧉` glyph and a `title` tooltip the frame doesn't draw | DRIFT (padding/radius close but not identical; the glyph + tooltip are EXTRA) | S4 |
| — | `Preview on output` | `317:136-137`: 132×31, "Preview on output" 12px | `#td-apply` `index.html:548`, same `.td-header-actions button` rule | MATCH | — |
| **TD-002** | `Save theme` | `317:138-139`: 95×31, flat-looking pill, "Save theme" 12px | `#td-save` `.td-save-cta` (`app.css:1217-1224`): `linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary))` fill, white 700-weight label | DRIFT in the frame (the mock doesn't clearly draw a gradient here, unlike the Presentation flagship's `▶ Present`/`+ Import`) but the **implementation's** choice to use the forbidden gradient is the real defect — see **A11Y** below (TD-012) | S2 (parity) / **S1 (a11y, TD-012)** |

---

# Frame `319:124` — Add-content toolbar (h 52)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | `T Text` | `319:125-127`: 65×32, glyph + label | `[data-add="text"]`, `index.html:560-561`; `.td-canvas-zone .td-addbar button[data-add]` (`app.css:1248-1258`) | MATCH | — |
| — | `▢ Shape` | `319:128-130`: 79×32 | `[data-add="shape"]`, `index.html:561-562` | MATCH | — |
| — | `🖼 Image` | `319:131-133`: 79×31 | `[data-add="image"]`, `index.html:562-563` | MATCH | — |
| — | Divider | `319:134`: 10×1 | not a distinct element in code — the fourth "Scripture" button and its `.td-later` disabled treatment sit where Figma's divider would be | UNSPECIFIED (Figma draws a divider with nothing named after it before "Audience ·…"; the code instead inserts a fourth button there) | S4 |
| — | "Audience · 1920×1080" | `319:135`: 129×15 | `.td-audience` `index.html:567`, `app.css:1276-1280`: `--sc-text-muted`, 12px | A11Y-classified — see **A11Y** | S4 |
| **TD-003** | Zoom control `− 68% +` | `319:136-139`: 86×30, showing **68%** | `#td-zoom-out`/`#td-zoom-v`/`#td-zoom-in`, `index.html:568-572`, defaulting to **100%** | DRIFT (the *value* Figma drew is illustrative — the control itself is EXTRA-improved: it is a frontend-only preview scale that never touches the real 1920×1080 output, `app.css:1326-1335`, a distinction Figma's static mock has no way to express) | S4 |
| **TD-004** | `Scripture` add button, drawn **enabled** in Figma (no fourth button exists on `319:124` — this is an EXTRA the code adds) | not drawn | `[data-add="scripture"]`, `index.html:564-565`: `disabled`, `.td-later`, title *"Scripture is the intrinsic Body region"* — an honest "later" affordance (matches the project's stated never-fake-it rule, the same pattern the Presentation audit approved for `▶ Video`) | EXTRA (scope-INTENTIONAL) | S4 |

---

# Frame `319:152` — Templates strip (h 111)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "TEMPLATES" overline | `319:153`: 75×13 | `.td-templates-title` `index.html:651`, `app.css:1418+` | MATCH | — |
| **TD-005** | Scriptures / Slides tab pair | Not present on `319:152` at all — the frame draws five plain template cards with no tab strip above them | `#td-tab-scriptures` (active) / `#td-tab-slides` (`.td-later`, disabled, title implied by context), `index.html:645-650` — an honest "later" affordance for a Slides-kind template tab that doesn't exist yet | EXTRA (scope-INTENTIONAL, and arguably the more honest state — a Slides tab that goes nowhere would be worse) | S4 |
| **TD-006** | `＋ New (from current)` / `↓ Import` / `↑ Export` | Not drawn (no header actions on `319:152`) | `index.html:653-655`; Import/Export are `.td-later` (disabled, "later" affordances) — matches the CLAUDE.md-adjacent code comment at `index.html:637-639` calling these out explicitly as deliberate | EXTRA (New is live; Import/Export scope-INTENTIONAL) | S4 |
| **TD-002** | Five named template cards: **Worship, Gradient, Midnight, Sunrise, Minimal** (`319:154-178`, each 120×87: a 120×68 swatch + a name label) | `#td-themes` populated by `tdList()` (`app.js:1649-1761`) from `invoke("builtin_themes")`, which resolves to `Theme::BUILTIN_NAMES = ["classic", "high-contrast", "lower-third"]` (`selahcue-present/src/theme.rs:590`) — **three** built-ins, named for their *function*, not an evocative preset name | **DRIFT** — count (3 vs 5) and naming convention (functional vs. evocative) both differ. This is the Theme-Designer-surface instance of the same gap the Presentation audit found on the *audience-output* side (`OUT-009`): `theme.rs:380-381` already scopes a fuller per-content-role template set as **S8-3d, deliberately later** — so this is *scoped-later, not broken*, but it means an operator opening Theme Designer today sees three functionally-named templates where the design promised five evocative ones | S2 |
| — | Thumbnail rendering | Static per-card colour mocks | `tdThumb()` (`app.js:1627-1647`): renders the theme's **real** background (solid/gradient/image→neutral) plus title/body colour bars, so each card reflects the actual saved theme rather than a generic swatch | EXTRA (a real improvement — a saved theme's card always tells the truth about what it contains) | — |
| **TD-007** | Saved (user-created) themes and their delete affordance | Not drawn on `319:152` at all — the frame shows only the five built-in-style cards | `tdList()` renders a second row set from `tdSaved`, each with a two-click-confirm `✕` delete (`app.js:1694-1761`) | EXTRA (a materially needed capability the frame simply doesn't show — likely because the frame predates the save-a-named-theme feature, `86ajq4xmy`, referenced in `index.html:637-639`) | S4 |
| **TD-008** | Collapse/expand chevron on the strip header | Not drawn | `#td-templates-toggle`, `index.html:642-644`, `aria-expanded` | EXTRA | S4 |
| — | Inline "Save theme" name form | Not drawn as part of `319:152` | `#td-save-row` (`index.html:662-669`): a WKWebView-safe inline form (no `window.prompt`), per the code comment referencing the project's known WKWebView limitation | EXTRA (necessary — matches a documented platform constraint) | S4 |

---

# Frame `325:124` — Inspector selection header (h 67)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Type chip (`T` in a 25×19 pill) | `325:126-127` | `#td-insp-chip` `index.html:682` (a generic `◈` glyph by default, swapped per selection by JS — not read in this pass beyond the default) | MATCH (default state) | — |
| — | Selected name "Title" | `325:128` | `#td-insp-title` `index.html:684` | MATCH | — |
| — | Subtext "Text element · selected on canvas" | `325:129`: 195×15 | `#td-insp-sub` `index.html:685`, default text "Select a layer to edit" (Figma shows the *selected* state; the code's unselected default is a different, and reasonable, state not drawn on this frame) | UNSPECIFIED (no unselected-header variant exists on `325:124` to compare against) | S4 |

---

# Frame `325:131` — BACKGROUND section (h 247)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "BACKGROUND" overline | `325:133`: 88×13 | `.td-sect-title` `index.html:765`, `app.css:1759+` | MATCH | — |
| — | Solid / Gradient / Image segmented control | `325:136-141`: three equal segments in a track, `Solid` pre-selected | `#td-bg-type` `index.html:766-769`, `role="group"`, three `[data-bg]` buttons with `aria-pressed` | MATCH | — |
| **TD-009** | Solid swatch + hex text: a 22×22 swatch + "#241C4A" | `325:145-146` | `#td-bg` (`<input type="color">`) + `#td-bg-hex` text, reflected live by `tdBgReflect()` (`app.js:2369-2376`) | **MATCH** — and notably *better* than the equivalent Presentation-surface control, which the Presentation audit flagged as missing hex text entirely (PME-028/PME-030) | — |
| — | Preset swatches (5: Black/Near-black/Indigo/Gold/White) | Not drawn on `325:131` at all | `#td-bg-presets` `index.html:778-781`: five `[data-color]` buttons with real `aria-label`s | EXTRA | S4 |
| — | Gradient two-stop swatches + hex (`#325:145-149` pattern reused for gradient) | `325:143-149` | `#td-bg-from`/`#td-bg-to` + `#td-bg-from-hex`/`#td-bg-to-hex`, reflected by `tdBgReflect()` (`app.js:2377-2379`) | MATCH | — |
| — | "180° · Vertical" angle readout | `325:150-153` | `#td-bg-dir` select: `Vertical`/`Horizontal`/`Diagonal ↘`/`Diagonal ↗` (`index.html:791-796`) | DRIFT — Figma shows a single free-angle readout ("180°"); the code offers four fixed directions with no numeric angle. Functionally narrower, but each option is a real, working direction (not a "later" stub) | S3 |
| — | Image background (choose/drop + path field) | Not drawn on `325:131` at all (Figma's Background section only shows Solid, per the frame's default state) | `#td-bg-image` `index.html:799-810`: a dropzone, a "Choose image…" button, and an honest paste-a-path fallback with a code comment explaining why (*"the offline build has no dialog crate"*) | EXTRA (necessary; honestly scoped) | S4 |

---

# Frame `325:154` — TYPOGRAPHY section (h 203)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "TYPOGRAPHY" overline | `325:156` | `.td-sect-title`, `index.html:815` | MATCH | — |
| — | Font family "Inter" + Weight "Bold ▾" | `325:159-163` | `#td-font` (populated from `system_fonts`, `app.js:1583-1601`) + `#td-weight` (`Regular`/`Semibold`/`Bold`/`Black`), `index.html:817-828` | DRIFT (structural improvement, not a defect) — Figma shows a static "Inter"; the code offers every font installed on the host machine, with a documented cross-platform caveat (*"themed = per-machine; default Noto Sans = cross-OS-identical"*, `index.html:848-850`) | S4 |
| — | Size "64" / Line "1.1" / Spacing "0" | `325:165-176` | `#td-size`/`#td-lh`/`#td-letter`, `index.html:830-837` — all percent/multiplier/em fields with explicit `aria-label`s naming the unit | MATCH | — |
| **TD-010** | Colour swatch + colour **name** "White" | `325:178-180`: a 22×22 swatch + the resolved colour's name, not its hex | `.td-colorcell` `index.html:839-841`: `<input type="color" id="td-color">` + the static label "Text colour" — the *field* label, not the current value's name or hex | DRIFT — the frame shows what the colour currently *is* ("White"); the code shows what the *field* is for. An operator has to open the swatch to see the current value at all | S3 |
| — | Align `L / C / R` | `325:181-187` | `#td-el-text-align` on the **element** text panel (a `<select>`, `index.html:727-732`) exists for text *elements*; **for region text** (Title/Body), no equivalent align control was found in the Typography section (`index.html:813-851`) | MISSING (region-level text alignment; element-level exists) | **TD-011, S2** |
| — | Fit segmented (Shrink-to-fit / Paginate / Clip) | `325:...` not drawn on this frame at all — Fit is drawn on `325:131` region in some Theme Designer variants elsewhere in the file, absent here | `#td-fit` `index.html:844-847`: three real `[data-f]` buttons | MATCH-by-inference (control exists and is wired; no frame on `325:154` itself to compare pixel values against) | S4 |

---

# Frame `325:189` — LAYERS section (h 281)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | "LAYERS" overline + "+ Add layer" | `325:191`/`325:188` | `.td-layers-title` + `#td-layers-add`, `index.html:857-859` | MATCH | — |
| — | Layer row: drag handle `⋮⋮` + kind glyph (`T`/`●`) + name + "Kind · z#" meta + `👁` | `325:193-224`, four example rows (Title z3, Body z2, Kicker z2, Glow Orb z1) | `tdLayerRow()` (`app.js:2134-2230`): handle, glyph (`🖼`/`T`/`●` by kind), name, `"<kind> · z<n>"` meta, eye button toggling `👁`/`🚫` with `aria-pressed` + `aria-label` | **MATCH** — structurally exact, including the two always-present intrinsic Region rows (Figma's "Title"/"Body" rows) alongside N free elements (Figma's "Kicker"/"Glow Orb" are element examples, not a third region — the code's 2-region model reconciles cleanly with the 4-row mock) | — |
| — | Reorder | Implied by z-index labels, not separately drawn as an interaction | Pointer drag (`tdLayerDragStart`) + keyboard `Alt+↑/↓` (`app.js:2215-2219`), `aria-current` on the selected row (not colour alone) | MATCH (+ EXTRA a11y — keyboard parity for a pointer gesture) | — |

---

# Accessibility

## A11Y-1 — Real defect (fix regardless of the frame)

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **TD-012** | `.td-save-cta` — `app.css:1217-1224`: `background: linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary))`, `color: #fff`, `font-weight: 700`, inherited 12-13px from `.td-header-actions button` | white on `--sc-primary-hover #7E6EFF` (the gradient's near end) = **3.78:1** at ≤13px bold | 13px bold is not large text (needs ≥18.66px bold), so the 4.5:1 bar applies. This is the **Save theme** button — the only path to persisting a design. It is the fourth instance of a defect this codebase has already fixed once (`.tb-golive`/`.timer-start`, `app.css:4505-4507`) and flagged twice more this audit round (Preservice's `.ps-start`, see `DESIGN-2.0-PARITY-AUDIT-preservice.md`; and the Presentation audit's `PME-005`). | Darken instead of lighten, matching the fix already shipped for `.tb-golive`: `background: linear-gradient(90deg, var(--sc-primary), #5a48d0)` (white ≥6:1 across the whole gradient), or flatten to solid `--sc-primary` (4.72:1). No frame change needed — Figma's `317:138-139` doesn't clearly draw a gradient here in the first place. |

## A11Y-2 — Classified, not blanket-swapped (pre-existing project-wide condition)

Consistent with the Presentation audit's A11Y-3 treatment of `--sc-text-muted` (`#6B7383`, 3.79:1 on
`--sc-surface`, clears AA-large only): this surface's uses are informational/secondary, not essential
body copy, and fall on the compliant side of the project's own written policy (`app.css:4476-4478`).

| Selector | Line | Text | Class | Verdict |
|---|---|---|---|---|
| `.td-audience` | `app.css:1276-1280` | "Audience · 1920×1080" | informational readout (the output resolution is fixed, not decision-relevant) | compliant under policy |
| `.td-canvas-label`/`.td-note` | `app.css:982-989` (legacy block, superseded where redeclared) | live-preview hint copy, class `coming-soon` | supplementary instruction text | compliant under policy — same tier as PME-006-011's "essential" carve-out does **not** apply here since this hint duplicates what the toolbar itself already states |
| `#td-audience`/font sizes across `.td-hint` rows | multiple | "Weight + letter-spacing apply to ALL…", "Drag to move…", "Click a layer to select it…" | instructional micro-copy | same tier as the muted-token policy's explicit carve-out |

No new site is added to the known open item (the second-tier compliant-muted-token decision, **Q-02**
in the Presentation audit) by this surface.

## A11Y-3 — Clear

- Every colour-carrying state on this surface pairs with text or a glyph: the eye toggle swaps glyph
  (`👁`/`🚫`) and `aria-pressed`, not colour alone; the selected layer row uses `aria-current`, not
  border colour alone; the "later" affordances (`Scripture` add, `Slides` tab, `Import`/`Export`) all
  carry a `title` naming the reason, satisfying WCAG 1.4.1.
- No green-gradient/white-text pairing (the worst of the four known-alarming pairings, 1.93:1) appears
  anywhere on this surface.

## Reconciliation — 2026-09-21

**Author:** Farah (Frontend Engineer). **Scope:** `TD-012` only, fixed under ClickUp task
`17tnw2axpt9` ("shared gradient-hover contrast fix", TD-012 / PSC-005 / DLM-001 — the same
defect found once here and twice more on the Pre-service and Download-modal surfaces). This
section is additive; the table above is left as originally written.

### FIXED

| Finding | Evidence |
|---|---|
| `TD-012` | `.td-save-cta` (`app.css:1217-1236`): the rest-state gradient's stops were reversed from `linear-gradient(90deg, var(--sc-primary-hover), var(--sc-primary))` to `linear-gradient(90deg, var(--sc-primary), #5a48d0)` — measured white-on-stop at **4.72:1 / 6.42:1**, both clearing AA. `:hover` changed from `filter: brightness(1.06)` to a flat `background: #5a48d0` (**6.42:1**) — see the note below on why the filter form was not kept. Verified by 9 new assertions in `scripts/operator_headless.py` (the `TD-012` block), mutation-tested (reverting the CSS locally reproduces the original 3.78:1 FAIL). Commit `d8ecf4b`. |

**Note — a gap found while fixing this, not fixed here.** The established pattern this finding
was asked to copy (`.tb-golive`/`.timer-start`, `app.css:5002-5007`,
`CODE-REVIEW-batch-desktop-design2-web1.md` §1) darkens the rest-state gradient the same way but
keeps `:hover { filter: brightness(1.06); }` unchanged. Recomputing that filter against the
darkened gradient's near stop (`var(--sc-primary)`, 4.72:1 at rest) gives **4.27:1 on hover** —
under AA-normal — and no headless check currently measures GO LIVE's or the Service-Timer
Start's hover state to catch it. `TD-012`/`PSC-005` avoid this by replacing the filter with a
flat darkened fill instead of copying the filter form literally. The latent `.tb-golive`/
`.timer-start` hover gap is out of scope for this ticket (already-shipped, reviewed code, not
one of TD-012/PSC-005/DLM-001) and is flagged as a follow-up rather than touched silently.

---

# Open questions

- **TD-OQ-1 (naming/documentation, not a design decision).** `563:201` is not the Theme Designer
  templates strip — it documents an unrelated Live Console Stage sub-tab. It should be renamed to
  reflect its real content (something like *"Live Console · Service Timer — Stage theme + message
  (Timer|Stage sub-tab)"*) by whoever owns that Live Console spec next, not guessed here. Left
  unrenamed rather than mis-named a second way.
- **TD-OQ-2 (Figma hygiene, page-wide).** `317:124`, `319:124`, `325:124`, and their sub-frames are
  generically named "Frame" at the node level (only the top-level section carries a real name),
  alongside roughly 20 other generic "Frame" nodes already on this page (noted during Phase A/B
  planning). A one-pass renaming sweep across the whole page — not per-audit — would remove the
  ambiguity this task's brief had to work around for `563:201`. Not this audit's call to schedule.
- **TD-OQ-3 (product).** TD-002 — should the Templates strip's built-in set grow from 3
  (`classic`/`high-contrast`/`lower-third`) toward the 5 evocative names Figma draws, or should the
  Figma mock be corrected to the shipped 3? `theme.rs:380-381` already defers a fuller per-role set to
  S8-3d — this question is whether *that* work should also reconcile the Theme-Designer-surface strip,
  or whether the two surfaces (Theme Designer template picker vs. audience-output template *role* set,
  OUT-009 in the Presentation audit) are allowed to diverge in count/naming permanently. Product/owner
  call, not Uma's or Farah's.
- **TD-OQ-4 (product, minor).** TD-011 — is region-level text alignment (Title/Body) intentionally
  absent, or a real gap? Element-level text alignment exists (`#td-el-text-align`); region-level does
  not appear to. If regions are meant to always inherit a fixed alignment from the theme's layout model,
  this is UNSPECIFIED-by-design and should be recorded as such rather than built.

---

## Pending ClickUp update

No ClickUp task ID was assigned to this audit at authoring time. Recorded per Phase D of the parent
plan (`docs/delivery/goals/TASK-design2-parity-audit-uncovered-surfaces.md`) — ticket creation and
linking is out of scope for this docs-only pass.
