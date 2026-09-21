# Design 2.0 parity audit — Presentation surfaces

**Role:** UI/UX Designer (Uma) · **Date:** 2026-08-23 · **Type:** read-only audit + gap spec
**Goal Contract:** `docs/delivery/goals/TASK-design2-parity-audit-presentation.md`
**Figma file:** `SYQn5hFY8YVQKm3c6rw0eJ` (all nodes on page `0:1`)
**Status:** point-in-time. Figma and `dist/` both move; re-run before acting on a row older than a week.

## What was audited

Both halves of "Presentation":

- **Part A — operator editor + media library + presentations library (web).**
  `implementation/desktop/crates/selahcue-operator/dist/{index.html,app.css,app.js}`,
  the `#surface-presentation` section (`index.html:752`) and its `pm-*` component set.
- **Part B — audience output rendering (Rust).**
  `implementation/desktop/crates/selahcue-present/src/{compose.rs,theme.rs,deck.rs,slide.rs,tokens.rs,measure.rs}`
  and `implementation/desktop/crates/selahcue-gpu`.

| Frame | Name | Size | Part |
|---|---|---|---|
| `329:124` | Presentation & Media — Design 2.0 (flagship) | 1760×1000 | A |
| `509:124` | Presentation & Media — States | 1712×1848 | A |
| `547:124` | Presentations (Library + New) | 1760×1000 | A |
| `552:124` | Presentations · Create & Manage | 1760×900 | A |
| `208:124` | Theme templates — audience output (S8-3a) | 1440×360 | B |
| `390:124` | Background — States | 1216×449 | B |

`317:124` / `204:124` (Theme Designer) were read **only** for the element model the compositor must
render. Their UI belongs to the Theme Designer surface and is not audited here.

## Method

For every frame: `get_screenshot` at high `maxDimension` (downloaded and visually inspected),
`get_design_context` on the frame and its sub-nodes for exact values, `get_variable_defs` for bound
tokens, then the matching implementation read and quoted.

**`get_variable_defs` on `329:124` returned `{}`** — nothing on these frames is bound to a Figma
variable. Every Figma value below is therefore a **raw literal in the file**, not a token reference.
Where a literal happens to equal a `--sc-*` token, this audit names the token for readability, but
the frame does not carry that binding. See open question **Q-01**.

## Verdict vocabulary

| Verdict | Meaning |
|---|---|
| **MATCH** | Implemented value equals the Figma value (or is within a stated tolerance). |
| **DRIFT** | Both exist; the values differ. |
| **MISSING** | Figma specifies it; the implementation has no equivalent. |
| **EXTRA** | The implementation has it; Figma does not draw it. |
| **UNSPECIFIED** | Figma does not specify the value — raised as an open question. |
| **A11Y-INTENTIONAL** | The implementation deliberately departs from the frame to satisfy NFR-020. The **frame** is the defect. Never treat as drift to "fix". |
| **A11Y-DEFECT** | The **implementation** fails NFR-020. Must be fixed regardless of the frame. |

Severity: **S1** blocks correct/accessible use · **S2** visible parity break an operator would notice ·
**S3** cosmetic (a few px, a weight, a label) · **S4** informational.

## The accessibility bar that governs every colour row

`docs/product/prds/SelahCue-PRD.md:396` — **NFR-020 (MVP)**: "Operator UI meets WCAG 2.1 AA contrast
(≥4.5:1 normal text, ≥3:1 large text/UI)". **Two** thresholds. Large = ≥24 px, or ≥18.66 px bold.

Three of the four palette pairings that look alarming are already settled in code, and this audit
does **not** re-open them:

1. **White on the violet gradient / `primary-hover` `#7E6EFF` = 3.78:1.**
   `selahcue-present/tests/test_tokens.rs:585-592` pins this as AA-large and states the constraint:
   *"the primary gradient/hover must not carry small white body text; small white labels sit on the
   flat `primary`"*. Not a fork — a usage rule. Verified against the frames below.
2. **White on solid live-red `#FF4D4D` = 3.27:1.** Clears AA-large; only *small* text violates.
3. **`--sc-text-muted #6B7383` = 3.79:1 on `--sc-surface`.** `test_tokens.rs:536` audits it
   deliberately at AA-large, label-only. Pre-existing across committed `dist/app.css`, not introduced
   by this parity pass. Logged separately in §A11Y-2.
4. **White on the GO-LIVE green gradient = 1.93:1** fails *both* thresholds. **It does not appear on
   any Presentation surface** — verified: `.pm-tp-live` (`app.css:5801`) is `--sc-live` ink on
   `--sc-elevated` (5.03:1) and `.pm-tp-btn` (`app.css:5803`) is neutral. No green gradient exists in
   `#surface-presentation`. Recorded as **clear**.

Deliberate a11y fixes already in `dist/` (another session, asserted by
`scripts/operator_headless.py`) are **INTENTIONAL**, never drift.

---

# Summary

**80 numbered gaps: PME-001…PME-063 (web) and OUT-001…OUT-017 (audience output).**
Every "Implemented" cell in this document cites `file:line` and quotes an actual value, or reads
`NOT FOUND`. No implementation file was modified.

## Headline

The Presentation editor is in **far better shape than a parity audit usually finds** — the
`pm-*` component set covers the flagship's structure almost completely, the accessibility work is
real and thoughtful, and several implementation choices are visibly *better* than the frames they
came from. The gaps cluster in three places, and they are specific:

1. **The primary action is missing.** `▶ Present` is drawn as the flagship's primary button
   (`329:140`) and listed in the card `⋯` menu (`553:140`), and exists in **neither**. The function
   is written (`pmPresent()`, `app.js:7004`) and reachable **only from the ⌘K command palette**
   (`app.js:5000`). An operator who does not know the palette cannot present a deck at all
   (**PME-014**, **PME-055**).
2. **The states board is half-built.** Of 21 enumerable states on `509:124`, **9 are complete, 8 are
   partial, and 2 are missing outright** — including **View-only / permission**, which does not exist
   on this surface in any form (**PME-043**).
3. **Part B designs objects the model cannot hold.** `208:130`'s `CCLI #7115744 · Sinach` cannot be
   rendered: `Theme` has no footer/attribution region and `Slide` is `{ title, body: Vec<String> }`
   (**OUT-006**, **OUT-015**). CCLI reporting is a licensing obligation, not a nicety.

## Part A — editor, media library, presentations library (web)

| Verdict | Count |
|---|---|
| MATCH | 55 |
| DRIFT | 39 |
| MISSING | 16 |
| PARTIAL (a designed state only half-built) | 6 |
| EXTRA (implemented, not drawn) | 9 |
| A11Y-INTENTIONAL (the frame is the defect) | 5 |
| UNSPECIFIED | 3 |

Severity: **6 × S1**, 27 × S2, 21 × S3, 31 × S4.

**The six S1s:** PME-001 (LIVE badge at 3.27:1), PME-014 + PME-055 (no Present control),
PME-043 (no view-only mode), PME-053 (no `Start from` group), PME-058 (delete copy promises undo the
backend does not provide), PME-059 (no warning when a service plan references the deck being deleted).

**Notable EXTRAs, all worth keeping and back-filling into Figma:** the `OPEN` deck flag, the
"changes aren't being saved on this machine" persistence banner, the remove-from-library `✕` with its
`alertdialog` confirm, the LIVE-slide warning on delete, the drag-reorderable LAYERS panel, and the
`Relink…` path for missing images.

## Part B — audience output (Rust)

| Verdict | Count |
|---|---|
| MATCH | 8 |
| DRIFT | 10 |
| MISSING | 2 (plus 4 section-level: OUT-006, OUT-009, OUT-012, OUT-015) |
| EXTRA | 1 |
| UNSPECIFIED | 1 |

Severity: **1 × S1** (OUT-006, the CCLI footer), 7 × S2, 5 × S3, 5 × S4.

Three findings deserve to be read even if nothing else is:

- **OUT-001 — `208:124` is pre-Design-2.0 and was never re-skinned.** Its board background is
  `#0E1116` (the *legacy* `tokens::BG_BASE`, `tokens.rs:77`), its captions are `#9AA4B2` (legacy
  `textMuted`), and its amber is `#F2B53C`. The compositor agrees with the frame exactly
  (`AMBER`, `theme.rs:420-425`) — so this is MATCH, not drift, but it means the audience output runs
  on the legacy amber while every chrome surface runs on Design 2.0's `#F2B84B` (**Q-09**).
- **OUT-009 — the template *set* does not match.** `BUILTIN_NAMES` is
  `["classic", "high-contrast", "lower-third"]` — two *style variants* plus one output role — where
  the frame designs *per-content-role* templates (Scripture / Song / Lower-Third). Only
  `lower-third` overlaps. `Theme`'s own doc already scopes this as S8-3d (`theme.rs:380-381`), so it
  is **scoped-later, not broken** — but it is why OUT-002, OUT-004 and OUT-006 all read as gaps: the
  objects the frame designs do not yet exist.
- **OUT-012 — the GPU compositor renders `Layer::Fill` only.** It silently skips `Text`, `Image` and
  `Shape` and has no `Gradient` arm (`compositor.rs:6-12`, `160`), so the SSIM ≥ 0.99 parity oracle
  proves parity **over fill-rect frames only** (`test_parity.rs:92-106`). Not a live regression — the
  shell CPU-composites today — but the parity claim is narrower than it sounds.

## Accessibility

`compose.rs` changed under this audit (`53f0032`, the `measure_word` memo). **Verified: it does not
move a pixel in this parity pass**, as designed. The live trap it creates for future work is
**OUT-013** and is called out in the Rust build order.

Four palette pairings that look alarming were checked against `PRD:396` (NFR-020) and the code:

- **White on the violet gradient (3.78:1)** — a **settled usage rule**, not a fork
  (`test_tokens.rs:585-592`). **Verified: no `pm-*` rule uses a gradient at all.** Every primary
  control on these surfaces is a flat fill at 4.72:1 or better. **One miss:**
  `.pm-btn-primary:hover` lightens to `--sc-primary-hover` and lands at 3.78:1 (**PME-005**) — the
  same defect the console already fixed for `.tb-golive` at `app.css:4505-4507`.
- **White on solid live-red (3.27:1)** — clears AA-large, so only small text violates. On these
  surfaces exactly one usage is small: `.pm-slide-live-badge` at **9 px bold** (**PME-001**).
- **White on the GO-LIVE green (1.93:1)** — **clear**; it does not occur on any Presentation surface.
- **`--sc-text-muted` (3.79:1)** — a **pre-existing** project-wide condition (105 call sites at HEAD)
  with a written policy at `app.css:4476-4478`. Classified rather than blanket-swapped: six usages
  (PME-006…PME-011) fall inside the project's own "essential text" rule and should be promoted now;
  the rest are a token decision (**Q-02**). Note the media-library metadata lines
  (`JPG · 2.4 MB`, `1.2 GB of media`) are **already compliant in the implementation** — the violation
  lives only in the frame.

## Where the specs stand

- `DESIGN-2.0-HANDOFF.md` — **stale, confirmed.** Its node map lists only `329:124`; it references
  none of `509:124`, `547:124`, `552:124`, `208:124`, `390:124`.
- `PRESENTATION-MEDIA-STATES-spec.md` — **agrees**, and is *behind* the implementation in one place:
  its "there is no inspector" delta note is out of date, the inspector shipped.
- `PRESENTATIONS-LIBRARY-spec.md` — **agrees with Figma throughout.** Eight rows where the
  implementation departs are places where it departs from the spec **and** the frame — unbuilt spec,
  not design ambiguity.

## Blocking decisions

Three of the fourteen open questions block work; the rest have workable defaults recorded:
**Q-08** (is deleting a presentation undoable — the design and the code contradict each other),
**Q-10** (are `208:124`'s mock geometries normative or illustrative — every Part B geometry row
depends on it), **Q-02** (the muted-token policy).

---

# A11Y findings

## A11Y-1 — Real defects found (fix regardless of the frame)

| # | Where | Measured | Why it fails | Fix |
|---|---|---|---|---|
| **PME-001** | `.pm-slide-live-badge` — `app.css:4665-4675`: `background: var(--sc-live)` (`#FF4D4D`), `color: #fff`, `font-size: 9px`, `font-weight: 700` | white on `#FF4D4D` = **3.27:1** at **9 px bold** | 9 px bold is not large text (needs ≥18.66 px bold), so the 4.5:1 bar applies. Fails by a wide margin. This is the LIVE badge on the presented slide's rail card — the single most safety-relevant label on the surface. | Flip the ink to `--sc-live-soft #2A1416` on the red fill (**5.31:1**) — the exact remedy the mobile app already shipped for its armed-danger controls (`MOBILE-2.0-SPEC.md:245`). Do **not** soften it to 80 % (3.69:1, `MOBILE-2.0-SPEC.md:846`). |
| **PME-002** | Figma `331:126`/`331:127` — `+ Import`: `bg-gradient-to-r from-[#7E6EFF] to-[#6E5CF0]`, label `#FFF` **12 px bold** | white over the light end = **3.78:1** at 12 px | Violates the constraint pinned at `test_tokens.rs:585-592`. **The frame is the defect** — the implementation already avoids it: `.pm-import` (`app.css:4935-4944`) is `--sc-accent-soft` fill + `--sc-primary` border + `--sc-text` label. | Correct the frame to the shipped treatment (or to flat `--sc-primary`, 4.72:1). No code change. |
| **PME-003** | Figma `329:140`/`329:141` — `▶ Present`: same gradient, label `#FFF` **12 px bold** | **3.78:1** at 12 px | Same constraint. The implementation has no such button at all (see **PME-014**), so nothing ships broken — but the frame must not be built as drawn. | When PME-010 is built, use flat `--sc-primary` with white (4.72:1), and correct the frame. |
| **PME-004** | Figma `331:191`/`331:192` — media footer stats: `bg-white` frame with `#FF4D4D` label **11 px semibold** | red on white = **3.27:1** at 11 px | A stray white fill on the frame (visible in the render as a white pill under "1 missing · 3 unused"). Almost certainly an accidental fill, not a design intent. The implementation renders it on `--sc-surface` (`.pm-media-stats.warn`, `app.css:5041`) = **5.52:1**. | Frame fix only — delete the white fill. |

## A11Y-2 — Primary fills on these surfaces: verified compliant, with one miss

The console carries a documented remediation block at `app.css:4472-4507` — *"Review fixes
(adversarial a11y + design-fidelity pass) … `--sc-text-muted` (#6b7383) is AA-large ONLY, so
essential small text is promoted to `--sc-text-secondary`"*. Finding **#10** in that block darkens
the gradient primaries (`.tb-golive`, `.timer-start` → `linear-gradient(90deg, var(--sc-primary),
#5a48d0)`, `app.css:4505-4507`); finding **#7** re-fills BLACKOUT with `#a3283a`.

**Verified: no `pm-*` rule uses the violet gradient at all.** The only gradients under a `pm-`
selector are decorative thumbnail placeholders (`.pm-asset-thumb` `app.css:4986`, `.pm-lib-thumb`
`5463`) and the busy shimmer (`5594-5599`). Every primary control on these surfaces is a flat fill:

| Control | Rule | Fill | Label | Measured | Verdict |
|---|---|---|---|---|---|
| `.pm-btn-primary` — backs `#pm-lib-new`, `#pm-lib-empty-new`, `#pm-grid-edit`, `#pm-grid-empty-edit`, the prompt confirm | `app.css:4592-4601` | flat `var(--sc-primary) #6E5CF0` | `#fff`, `font: inherit` = **14 px** / 600 | **4.72:1** | compliant |
| `.pm-import` — `+ Import` | `app.css:4935-4944` | `--sc-accent-soft #201F3A` | `--sc-text #F4F6FB` 12 px | **14.73:1** | compliant |
| `.pm-rtab[aria-selected="true"]`, `.pm-mtab[aria-pressed="true"]` | `app.css:4879`, `4957` | flat `--sc-primary` | `#fff` | **4.72:1** | compliant |

| # | The one miss | Detail |
|---|---|---|
| **PME-005** | `.pm-btn-primary:hover` — `app.css:4602`: `background: var(--sc-primary-hover)` | On hover the white 14 px/600 label sits on `#7E6EFF` = **3.78:1**, below AA-normal. The rest-state fill was chosen correctly (flat `--sc-primary`) but the hover reintroduces exactly the pairing that `test_tokens.rs:585-592` forbids and that `app.css:4505-4507` already remedies for `.tb-golive`. Hover is a real UI state; WCAG applies. **Fix:** darken instead of lighten — `background: #5a48d0` (white = 6.42:1), matching finding #10's direction. Severity **S2**. |

## A11Y-3 — `--sc-text-muted` on these surfaces: classified, not blanket-swapped

`--sc-text-muted #6B7383` measures **4.08 / 3.79 / 3.45 / 3.96 : 1** on base / surface / elevated /
inset — fails AA-normal everywhere, clears AA-large everywhere.
`--sc-text-secondary #A7AEBE` measures **7.40–8.74 : 1**. `test_tokens.rs:536` audits the muted token
at AA-large, label-only. There are **105 call sites** at HEAD across `dist/`, so this is a
pre-existing, project-wide condition, not something this parity pass introduces.

The project's own written policy (`app.css:4476-4478`) is: *"headings, form-section labels,
instructions, empty-states … are essential text → must clear AA-normal. Supplementary micro-text —
unit captions, kbd hints, resolution, placeholders, count pills — stays muted."*

**The residual exposure:** WCAG 1.4.3 exempts *incidental* text — decoration, inactive controls,
invisible text, text that is part of a picture. It does **not** exempt "supplementary". A file-size
or format readout is informational, so it is in scope even though it is small and secondary. So the
policy is right about its first half and optimistic about its second.

**Do not propose a blanket swap.** Promoting all 105 sites flattens the type hierarchy the muted
token exists to create. Classified for these surfaces:

| # | Selector / copy | Line | Size | Class | Verdict |
|---|---|---|---|---|---|
| **PME-006** | `.pm-insp-note` — "Select an element to edit it." | `app.css:4921` | 11 px | **empty state** — named as essential by the project's own policy | violation, and a **miss against the written rule** |
| **PME-007** | `.pm-media-empty` — "No matching media." | `app.css:5042` | 13 px | **empty state** | violation, same miss |
| **PME-008** | `.pm-lib-empty-sub` — "Create your first slide deck — a sermon, a song set, or announcements." | `app.css:5590` | 13 px | **empty-state body copy** | violation, same miss |
| **PME-009** | `.pm-grid-hint` — "Double-click a slide to present it live." | `app.css:5791` | 12 px | **instruction** — named as essential | violation, same miss |
| **PME-010** | `.pm-tile-failmsg` — a thumbnail render failure message | `app.css:5790` | 12 px | **error text** | violation |
| **PME-011** | `.pm-deck-seg-btn` — the Grid/List segment labels | `app.css:6013` | 12 px | **interactive control label** — UI components need ≥3:1 *and* their text ≥4.5:1 | violation |
| **PME-012** | `.pm-lib-meta` — "24 slides"; `.pm-lib-new-sub` — "Start a blank deck"; `.pm-link-meta`; `.pm-verse-vps` | `app.css:5499`, `5546`, `5936`, `6042` | 12 px | **informational, not incidental** — the slide count is decision-relevant when choosing a deck | violation (weaker than the above; the honest fix is a token decision, **Q-02**) |
| — | `.pm-deck-pill` (count pill, `6022`), `.pm-lib-q::placeholder` (`5422`) | — | 11–13 px | explicitly allowed to stay muted by the written policy | compliant under the policy; still non-exempt under 1.4.3 — folded into **Q-02** |
| — | `.pm-deckswitch-caret` `▾` (`5381`), `.pm-lib-search-ico` `⌕` (`5420`), `.pm-deck-thumb` `▦` glyph (`6019`) | — | — | **decorative glyphs** — genuinely incidental | compliant, leave alone |

**Recommendation.** Promote **PME-006…PME-011** to `--sc-text-secondary` now: each is squarely inside
the project's *existing* written rule, so it is applying a policy rather than setting one, and it
changes no token value. For **PME-012** and the count-pill/placeholder tier, the right answer is
probably **a second, compliant muted token for small type** — a value between `#6B7383` and
`#A7AEBE` that clears 4.5:1 on surface while still reading as a third tier. That is a palette
addition, hence a four-surface lockstep change
(`test_tokens.rs::design2_palette_is_pinned_across_surfaces` cross-checks `dist/app.css`,
`tokens::design2::MANIFEST`, `StageTheme::dark()` and the mobile `design_tokens.dart`). It is a
design call with real numbers behind it — see **Q-02**.

**Already correct, do not "restore":** `.pm-asset-meta` (`app.css:5009`) and `.pm-media-foot`
(`app.css:5038`) use `--sc-text-secondary` where Figma `331:144` / `331:190` draw `#6B7383`. So the
media-library metadata lines (`JPG · 2.4 MB`, `MP4 · 1080p`, `MOV · Loop`, `1.2 GB of media`) are
**already compliant in the implementation** — the violation lives only in the frame.
**A11Y-INTENTIONAL.**

## A11Y-4 — Clear

- **White on the GO-LIVE green gradient (1.93:1)** does not occur anywhere in `#surface-presentation`.
  Verified: `.pm-tp-live` (`app.css:5801`) is `--sc-live` ink on `--sc-elevated` (5.03:1);
  `.pm-tp-btn` (`app.css:5803`) is `--sc-surface` fill with `--sc-text`. No green gradient exists on
  this surface.
- Every state pairs colour with text or a glyph (`aria-label` additions `app.js:7470-7472`; the LIVE
  badge's literal "LIVE" text `app.js:7389-7393`) — WCAG 1.4.1 satisfied.

---

# Frame `329:124` — Presentation & Media (flagship, 1760×1000)

Layout spine: `220 / 1180 / 360`. Implemented as
`.pm-body { grid-template-columns: 220px 1fr 360px }` (`app.css:4607-4612`) — **MATCH**.

## Topbar (`329:125`, h 57)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Topbar bar | `bg #14161D`, `px 18 / py 13`, h 57 | `.pm-topbar` `app.css:4559-4568`: `background: var(--sc-surface)` (`#14161D`), `padding: 10px 16px`, `border-bottom: 1px solid var(--sc-border)` | DRIFT (padding 10/16 vs 13/18) | S3 |
| — | Brand mark + "SelahCue" + `▾` | `329:127-130`: 31 px rounded-6 icon, "SelahCue" Inter Bold 14 `#F4F6FB`, caret `#6B7383` 10 px | Lives in the global app header, not `pm-topbar` — `index.html:64` region | MATCH (relocated by design) | S4 |
| — | Vertical divider | `329:131`: 1×20 `#262A34` | `.topbar-divider`, `index.html:63` | MATCH | S4 |
| — | Surface label "Presentation" | `329:132`: Inter SemiBold 14 `#A7AEBE` | `#surface-label`, `index.html:64` | MATCH | S4 |
| **PME-013** | Deck chip "▦ Sermon: Grace That Feeds · 6 slides" | `329:133`: **static chip** — `bg #1C1F28`, `1px #262A34`, r7, `px10/py5`, gap 6; `▦` `#F2B84B` 11 px bold; name `#F4F6FB` 12 px semibold; count `#6B7383` 11 px medium | `#pm-deckswitch` `index.html:755-758` + `app.css:5364-5381`: an **interactive button** — r**9**, `px12/py6`, `font-size 14 / weight 600`, plus a `▾` caret; `▦` is `--sc-primary-hover` not gold; count `--sc-text-secondary` not muted | DRIFT (chip→button is intentional per `PRESENTATIONS-LIBRARY-spec.md` §2; the metrics and the `▦` colour are not) | S3 |
| **PME-014** | **`▶ Present`** primary action | `329:140/141`: gradient pill r9, `px13/py8`, white 12 px bold | **NOT FOUND as a control.** `pmPresent()` exists (`app.js:7004`) but is reachable **only** from the ⌘K command palette (`app.js:5000`). No button in `pm-topbar` (`index.html:753-762`). | MISSING | **S1** |
| **PME-015** | `Add to plan` secondary action | `329:138/139`: `bg #1C1F28`, `1px #262A34`, r9, `px13/py8`, `#A7AEBE` 12 px semibold | **NOT FOUND.** Deliberately dropped — `PRESENTATIONS-LIBRARY-spec.md` §2 records it as "a disabled *later* stub" replaced by the deck switcher. | MISSING (documented intent) | S4 |
| **PME-016** | `＋ New` | not drawn in `329:124` | `#pm-newpres` `index.html:760`, `.pm-btn-ghost` | EXTRA (reasonable) | S4 |

## SLIDES rail (`329:143`, w 220)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Rail | w 220, own surface | `.pm-slides` `app.css:4614-4620` — `border-right: 1px solid var(--sc-border)`, `background: var(--sc-surface)` | MATCH | — |
| — | "SLIDES" overline | `329:144`: 11×13 at x13/y15, tracked caps | `.pm-rail-head` `app.css:4621-4627`: 11 px / 700 / `letter-spacing .08em` / `--sc-text-secondary`, `padding 14px 14px 8px` | MATCH | — |
| — | Slide row = index + card | `329:145`: 194 wide, card 179×84, index gutter ~15 | `.pm-slide` `app.css:4634-4640`: `grid-template-columns: 14px 1fr; gap 8px`; `.pm-slide-card` `min-height: 72px` | DRIFT (card 72 min vs 84 fixed) | S3 |
| — | Row pitch | 95 px (84 card + 11 gap) | `.pm-slide-list` `app.css:4628-4633`: `gap: 10px`, `padding: 4px 12px` | DRIFT (10 vs 11) | S3 |
| — | Card chrome | r8 implied, elevated fill | `.pm-slide-card` `app.css:4642-4653`: `1px var(--sc-border)`, `r8`, `var(--sc-elevated)`, `padding 10px` | MATCH | — |
| — | Selected card (slide 2) | violet 1.5–2 px ring | `.pm-slide.sel .pm-slide-card` `app.css:4654`: `border-color: var(--sc-primary)` + `box-shadow: 0 0 0 1px` | MATCH | — |
| **PME-017** | Card overline + title (`329:148/149`: "SERMON TITLE" 7 px caps over "Grace That Feeds" 13 px) | a two-tier card: a **kind overline** then the title | `pmRenderSlides` `app.js:7382-7387` renders `l0` (12 px/600) then `ln` lines (11 px) from `s.lines` — there is **no kind overline**. `.pm-slide-kind` exists (`app.css:4659`) but is never written by `app.js`. | MISSING (dead class) | S2 |
| **PME-061** | Media slide thumbnails (`329:158`, `329:170`: a 150×84 image plate with "▶ Testimony clip" / "🖼 Harvest field") | slide cards for media slides render a **picture**, not text | `app.js:7382-7387` renders text lines only for every slide kind | MISSING | S2 |
| — | `+ Add slide` | `329:176`: 194×37, dashed, centred | `#pm-add-slide` `index.html:835` + `app.css:4685-4695`: `1px dashed var(--sc-border-strong)`, r8, `padding 9px`, `margin 8px 12px 14px` | MATCH | — |
| — | `‹ Done` back button | not drawn | `#pm-done` `index.html:832` | EXTRA (needed by the library/grid modes) | S4 |

## Canvas zone (`329:178`, w 1180)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Toolbar bar | `330:124` h 52, items at y10, h 32 | `.pm-toolbar` `app.css:4698-4706`: `padding: 8px 16px`, `gap: 6px`, `flex-wrap: wrap` | MATCH | — |
| — | `T Text` | `330:125-127`: 65×32, glyph + label 13 px | `index.html:840`, `.pm-tool` `app.css:4707+`: `padding 6px 12px`, `gap 6px` | MATCH | — |
| — | `▢ Shape` | `330:128-130`: 79×32 | `index.html:841` | MATCH | — |
| — | `🖼 Image` | `330:131-133`: 79×31 | `index.html:842` | MATCH | — |
| — | `▶ Video` | `330:134-136`: 77×32, drawn **enabled** | `index.html:843-844`: `.pm-tool.pm-later`, `aria-disabled="true"`, title "On-slide video is a later increment (ADR-0020)"; `.pm-later { opacity: .5 }` `app.css:4603` | A11Y/scope-INTENTIONAL — an honest "later" affordance, matches the repo's "never fake it" rule | S4 |
| — | `🎨 Background` | `330:137-139`: 113×31 | `index.html:845-846` | MATCH | — |
| — | Divider | `330:140`: 10×1 | `.pm-tool-div` `index.html:847` | MATCH | — |
| — | `↶` / `↷` | `330:142-145`: two 33×24 buttons in a 76×32 group | `#pm-undo` / `#pm-redo` `index.html:848-851`, with `aria-keyshortcuts` | MATCH (+ EXTRA a11y) | — |
| — | "Slide 2 / 6 · 1920×1080" | `330:146`: 15 px, at x571 | `#pm-slide-pos` `index.html:852`, `aria-live="polite"` | MATCH | — |
| **PME-018** | Keyboard-hint strip | **not drawn** | `#pm-canvas-hint` `index.html:854-857` — a full-width `<p>` of `<kbd>` hints between the toolbar and the canvas, `app.css:4672-4684` | EXTRA — it consumes vertical canvas height the frame gives to the slide, and is the largest single layout divergence in the zone | S2 |
| — | Slide stage | `330:147` 1180×836 holding an 880×495 slide (16:9), letterboxed and centred | `#pm-canvas-box` / `#pm-canvas` `index.html:858-859` (`width=16 height=9`), painted by `render_deck_slide` at `maxW 960 / maxH 540` (`app.js:7404`) | MATCH (native preview, ADR-0002/0003 respected) | — |
| — | Selection box + 8 handles | `330:153-159`: box + **six** handles drawn (nw/n/ne/sw/s/se); 9×9 r-rects | `#pm-sel` `index.html:860-866` renders **eight** (`nw n ne e se s sw w`) | DRIFT — the impl is the correct superset; `CANVAS-EDITING-spec.md` §1/§2 owns the model and specifies 8 | S4 |
| — | Bottom bar | `330:160` h 55 | `.pm-bottombar` `index.html:869` | MATCH | — |
| — | Speaker-notes field | `330:161-163`: 868×33, `📝` + "Speaker notes — read slowly, pause after 'vinedressers'" 15 px | `#pm-notes` `index.html:871-872`, placeholder **"Speaker notes — shown on the stage monitor, never the audience"** | DRIFT (copy) — the impl copy is *better*: it states where notes appear. Keep the impl, correct the frame. | S4 |
| — | `Transition [Fade ▾]` | `330:164-167`: 122×33 | `#pm-transition` `index.html:873-876`, options **Cut / Fade** | MATCH | — |
| — | `Auto-advance [Off ▾]` | `330:168-171`: 134×33 | `#pm-autoadv` `index.html:877-884`, options Off/3s/5s/8s/15s/30s | MATCH (Figma shows only "Off"; the option set is UNSPECIFIED) | S4 |

## Media library (`329:179`, w 360)

Figma panel: `bg #14161D`, `padding 15`, `gap 13` between blocks.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **PME-019** | Media / Inspector tab strip | **not drawn on `329:124`** — the panel starts at "MEDIA LIBRARY" | `.pm-right-tabs` `index.html:890-895` + `app.css:4861-4880` | EXTRA on this frame — but **specified** by `509:124` `512:125-129`. Not a defect; the flagship is simply the older drawing. | S4 |
| — | "MEDIA LIBRARY" overline | `331:125`: Inter **Bold 12 px**, `#6B7383`, `letter-spacing 1px` | `.pm-rail-head` reused (`index.html:899`) — **11 px**, `letter-spacing .08em` (≈0.88 px at 11 px), `--sc-text-secondary` | DRIFT on size/tracking; **A11Y-INTENTIONAL** on the colour | S3 |
| — | `+ Import` | `331:126/127`: gradient r8 `px11/py7`, white 12 px bold | `#pm-import` `index.html:899-900` + `app.css:4935-4944`: `--sc-accent-soft` fill, `1px --sc-primary`, `--sc-text` label 12 px, r8, `padding 6px 12px` | **A11Y-INTENTIONAL** — see **PME-002** | S4 |
| **PME-020** | Type filter — All / Images / Video / Audio | `331:128-136`: a **segmented control** — an inset track (`bg #0F1116`, `1px #262A34`, **r9**, `padding 3`) holding four equal segments (`r7`, `py7`); active = `#6E5CF0` fill + white 12 px bold; inactive = transparent + `#A7AEBE` 12 px medium | `.pm-media-tabs` `app.css:4945` + `.pm-mtab` `4946-4957`: **four free-standing buttons**, `gap 4`, each with its own `1px --sc-border` + r8 + `--sc-elevated` fill. **No track.** | DRIFT — reads as a button row, not a segmented control | S2 |
| — | Search field | `331:137-139`: `bg #0F1116`, `1px #262A34`, r8, `px12/py9`, `⌕` 14 px + "Search media…" 12 px `#6B7383` | `.pm-media-search` `app.css:4958-4969`: `--sc-inset`, r8, `padding 7px 10px`, `margin 6px 12px`; `.pm-media-q` 13 px | DRIFT (padding, input size) | S3 |
| — | Asset grid | `331:140`: 2-up, tile w 150, **gap 11**, tile stack `gap 7` | `.pm-media-grid` `app.css:4973-4980`: `1fr 1fr`, **gap 12**, `padding 8px 12px`; `.pm-asset` `gap 5` | DRIFT (1 px / 2 px) | S3 |
| — | Asset thumbnail | 150×90 (5:3), r8, `1px #262A34`, per-asset gradient fill | `.pm-asset-thumb` `app.css:4981-4993`: `aspect-ratio: 5 / 3`, r8, `1px var(--sc-border)`, `linear-gradient(135deg,#232634,#1A1D27)` | MATCH — geometry matches; the per-asset colouring is a Figma mock, real thumbnails come from the host | — |
| — | Asset name | `331:143`: 11 px semibold `#F4F6FB`, ellipsised | `.pm-asset-name` `app.css:5007`: **12 px**, `--sc-text`, ellipsised | DRIFT (1 px) | S3 |
| — | Asset meta ("JPG · 2.4 MB") | `331:144`: 10 px medium `#6B7383` | `.pm-asset-meta` `app.css:5009`: **11 px**, `--sc-text-secondary`; text built at `app.js:7507-7508` as `kind.toUpperCase() + " · " + size_label` | **A11Y-INTENTIONAL** on colour; DRIFT on size | S4 |
| — | Video tile — play glyph + duration badge | `331:151-154`: a 34 px circle with a dark `▶`, plus a `rgba(11,13,18,0.72)` r5 `px6/py2` badge at `left 7 / bottom 7`, white 9 px bold | `app.js:7475-7483`: `.pm-play` `▶` (`app.css:4995`: 22 px, white, `opacity .85` — **no circle**) + `.pm-badge` (`app.css:4994-5002`: `rgba(0,0,0,0.6)`, r5, `left 6 / bottom 6`, 10 px) | DRIFT — no play-button disc | S3 |
| **PME-021** | Missing tile | `331:168-172`: **1.5 px dashed `#5A2327`** on `bg #0F1116`; `⚠` 18 px `#FF4D4D`; the word **"Missing"** 10 px inside the tile; name `#FF4D4D`; meta "File moved" | `app.js:7473-7474` writes only `<span aria-hidden="true">⚠</span>`; `.pm-asset.missing .pm-asset-thumb` (`app.css:5006`) is a **solid** `--sc-live-border` on `--sc-live-soft`. Name red at `app.css:5008`; meta "File moved" at `app.js:7508`. | DRIFT (solid vs dashed, `--sc-live-soft` vs inset) + **MISSING** the visible "Missing" caption | S2 |
| — | Missing tile a11y | `509:124` `514:139`: label "‹file›, media missing — relink" | `app.js:7470` — `"Missing media " + a.name`; the thumb is `disabled` + `aria-disabled` (`7499-7501`) | DRIFT (label wording; no "relink" cue) | S3 |
| **PME-022** | Remove-from-library `✕` | **not drawn** | `.pm-asset-del` `app.js:7513-7529`, revealed on hover/focus (`app.css:5091`) | EXTRA — a genuinely needed affordance with a proper `alertdialog` confirm. Back-fill the frame. | S4 |
| — | "AUDIO" section head | `331:173`: Bold 11 px `#6B7383`, `letter-spacing 1px` | `.pm-media-sect` `app.css:5010-5017`: 11 px / 700 / `.08em` / `--sc-text-secondary` | **A11Y-INTENTIONAL** on colour, MATCH otherwise | — |
| **PME-023** | Audio row | `331:174-180`: `bg #0F1116` (**inset**), `1px #262A34`, **r9**, `pl11/pr12/py10`; a **26 px `#1C1F28` circle** with a **gold `#F2B84B` ▶**; a two-line stack — name 12 px semibold `#F4F6FB` over **format "WAV" 10 px `#6B7383`**; duration 11 px semibold `#A7AEBE` | `.pm-audio-row` `app.css:5019-5027`: `--sc-elevated` fill (**not** inset), **r8**, `padding 8px 10px`; `.pm-play` is a bare `<span>` in `--sc-primary` (`5028`) with **no disc**; `app.js:5543-5555` renders **name only** — **no format sub-line**; duration `--sc-text-secondary` 12 px | DRIFT (fill, radius, play disc, ink) + **MISSING** the format sub-line | S2 |
| **PME-024** | Audio play control | Drawn as a filled circular control — reads as **interactive** (audition the track) | `app.js:5545`: `row.innerHTML = '<span class="pm-play" aria-hidden="true">▶</span>'` — a decorative span. There is **no audio preview**, and nothing labels it as unavailable. | MISSING (or the frame over-promises) — **Q-05** | S2 |
| — | Footer "1.2 GB of media" | `331:190`: 11 px medium `#6B7383` | `#pm-media-total` `index.html:915`; text `total_label + " of media"` (`app.js:7557`); `.pm-media-foot` `app.css:5031-5040`: 12 px, `--sc-text-secondary`, `border-top` | **A11Y-INTENTIONAL** on colour | — |
| — | Footer "1 missing · 3 unused" | `331:192`: `#FF4D4D` 11 px semibold **on a white frame fill** | `#pm-media-stats` `index.html:915`; built at `app.js:7558-7562`; `.warn` → `--sc-live` on `--sc-surface` (`app.css:5041`) | **A11Y-INTENTIONAL** — see **PME-004** | — |
| **PME-025** | Panel scroll behaviour | `331:188` — a 10×168 spacer pushes the footer to the bottom; the whole panel is one column | The grid scrolls (`app.css:4978`) but the AUDIO block is `flex: 0 0 auto` (`app.css:5018`), so with many audio tracks the panel's own overflow is untested. | UNSPECIFIED — **Q-06** | S3 |

---

# Frame `509:124` — Presentation & Media, States board (1712×1848)

This board is **mostly annotation, not pixel design**: sections ① and ② draw real UI, section ③ is
twelve labelled prose vignettes. It is therefore a *state* spec, and the verdicts below are about
behaviour and copy as much as geometry. Its own header (`509:126`) names
`docs/design/PRESENTATION-MEDIA-STATES-spec.md` as the companion.

## ① Contextual right panel (`510:125`) — Media ⟷ Inspector

The tab strip is `Media | Inspector` pills — active = flat `#6E5CF0` + white, inactive = elevated +
`#A7AEBE`. Implemented at `.pm-rtab` (`app.css:4868-4880`) — **MATCH**, and this is where the
flagship's missing tab strip (PME-019) is actually specified.

### `512:124` — 01 Right panel · Media (default)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Media tab active on load | `512:126-127` Media selected | `index.html:891-892` `aria-selected="true"` | MATCH | — |
| — | Inspector tab disabled → "Select an element" | `512:135` | `index.html:893-894` `aria-disabled="true" tabindex="-1"`; the panel body writes **"Select an element to edit it."** (`app.js:7299`) | MATCH (copy expanded, better) | — |

### `510:126` — 04 Inspector · Text

Figma row order: **Content · Font · Size (90 ‰) · Weight · Align (`≡ ⬍ top`) · Colour (`▨ #F0F0F5`) ·
Fit (`Shrink-to-fit ▾`) · Arrange hint · Opacity (100%)**. Header: title `Text element` + `2 of 5` +
`👁` + `🗑`.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Header `Text element` · `2 of 5` · `👁` · `🗑` | `510:134-138` | `app.js:7305-7312`: `.pm-insp-title` = `"Text element"`, `.pm-insp-count` = `"2 of 5"`, eye `👁`/`🚫` with `aria-pressed`, `🗑` `.pm-iconbtn.danger` | MATCH (+ EXTRA: the eye swaps glyph, not just colour) | — |
| **PME-026** | Row **order** | Content → Font → Size → Weight → Align → Colour → Fit → Arrange → Opacity | `app.js:7314-7327`: Content → **Size ‰** → **Line ‰** → Font → Weight → Align → **V-align** → Colour → Fit → OPACITY → **LAYERS** | DRIFT — Size/Line hoisted above Font; Align split in two | S3 |
| **PME-027** | `Align` control | `510:158`: **one** combined control reading `≡ ⬍ top` (horizontal + vertical in a single affordance) | `app.js:7320-7325`: three `aria-pressed` buttons (`≡ ≣ ≡`) for horizontal, **plus a separate `V-align` select** (`7326`) | DRIFT — functionally a superset, but the two horizontal-align glyphs `left` and `right` are the **same character `≡`**, so left and right are visually indistinguishable | **S2** |
| **PME-028** | `Colour` control | `510:162`: a swatch **plus the literal hex `#F0F0F5`** as text | `app.js:7144`: `<input type="color">` only (`app.css:4914`: 46×26). The hex is never shown or typeable. | DRIFT / MISSING (no hex readout or entry) | S2 |
| — | `Size 90 ‰` | `510:150` | `app.js:7315` `pmInspRow("Size ‰", pmNum(...))` | MATCH | — |
| — | `Fit Shrink-to-fit ▾` | `510:166` | `app.js:7328`: options `Shrink to fit` / `Clip` | DRIFT (label hyphenation; Figma shows only one option — set UNSPECIFIED) | S4 |
| **PME-029** | `Arrange: ⤓ back · ↓ · ↑ · ⤒ front · behind the text` | `510:167`: a hint line naming four z-order actions **and** reporting the element's position relative to the text | `app.js:7348-7349`: a `LAYERS` section + `pmRenderLayers` — a drag-reorderable front-to-back list (`app.js:7196-7201`). Keyboard `[`/`]` z-order is offered in `#pm-canvas-hint` (`index.html:854-857`). No "behind the text" readout. | EXTRA/DRIFT — the layers panel is a richer replacement; the *relative-to-text* readout is MISSING | S3 |
| **PME-062** | `Opacity 100%` | `510:171` | `app.js:7345-7347` under an `OPACITY` section head; value is **0–255**, not a percentage (`Math.min(255, v)`) | DRIFT — the frame says `100%`, the control says `255` | S2 |

### `511:124` — 05 Inspector · Shape

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Header `Shape element` · `2 of 5` · `👁` · `🗑` | `511:132-136` | `app.js:7303` `kindTitle` map | MATCH | — |
| **PME-030** | `Fill ▨ #7C5CFF` | `511:140` — hex `#7C5CFF` | `app.js:7330` `pmColor(el.fill, …)` — swatch only | DRIFT (no hex readout, as PME-028). **Note the hex itself: `#7C5CFF` is neither `--sc-primary #6E5CF0` nor `--sc-primary-hover #7E6EFF`** — a third violet that exists nowhere in the palette. Sample content or a stray value — **Q-03** | S3 |
| **PME-031** | `Border ▨ · 2 px` | `511:144` — **one** control carrying colour *and* width, in **px** | `app.js:7331-7332`: **two** rows — `Border` (colour) and `Border ‰` (per-mille) | DRIFT — the impl split is arguably clearer, but the unit differs (px vs ‰) | S3 |
| — | `Corner 16 ‰` | `511:148` | `app.js:7333` `Corner ‰` | MATCH | — |
| — | `Shape Rounded ▾` | `511:152` | `app.js:7334`: `Rectangle / Rounded / Ellipse / Triangle` | MATCH (Figma shows one option; the set is UNSPECIFIED) | S4 |
| — | `Arrange` hint · `Opacity` | `511:153`, `511:157` | as PME-029 / opacity above | see above | — |

### `511:158` — 06 Inspector · Image

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **PME-032** | Asset preview + metadata | `511:172-175`: a **56×40 real thumbnail**, name `harvest field.jpg`, and a metadata line **`JPG · 2.4 MB · 1920×1080`** | `app.js:7333-7336`: `.pm-insp-thumb` is a **static gradient placeholder** (`app.css:4922`: 52×38, `linear-gradient(135deg,#232634,#1A1D27)`) with no image; the name is rendered; **there is no metadata line at all** | DRIFT (placeholder vs preview, 52×38 vs 56×40) + **MISSING** the `JPG · 2.4 MB · 1920×1080` line | S2 |
| **PME-033** | `Replace… (R → media, images)` | `511:177`: a **full-width** button whose label carries the **keyboard shortcut and its effect** | `app.js:7337`: full-width button labelled **`"Replace…"`** (or `"Relink…"` when missing). The shortcut hint is absent, and no `R` key binding was found in `app.js`. | DRIFT (label) + MISSING (the `R` shortcut) | S2 |
| — | `Fit Fill ▾` | `511:181` | `app.js:7341-7343`: `Stretch / Fit (letterbox) / Fill (cover)`, `aria-label="Image fit"` | MATCH (impl is the fuller set) | — |
| — | Missing-image variant | not drawn | `app.js:7335`, `7337`: name prefixed `"⚠ Missing — "` in `.pm-insp-missing` (`app.css:4920`), button becomes `Relink…` | EXTRA (correct, and it satisfies `514:138`'s "relink") | — |
| **PME-034** | Inspector variants **02** and **03** | The board numbers the panels `01`, `04`, `05`, `06` — **`02` and `03` are absent from the file** | n/a | UNSPECIFIED — two designed states are missing from the board. Candidates: a Background inspector (the toolbar has `🎨 Background`) and a multi/no-selection state. **Q-04** | S2 |

## ② Canvas — element selection (`512:137`)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Selection box + 8 handles | `512:140-148`: box + **8** 9×9 handles | `#pm-sel` `index.html:860-866`, 8 handles | MATCH (`CANVAS-EDITING-spec.md` §1/§2 owns the model) | — |
| **PME-035** | On-canvas **z-badge** `Text · in front · 2 of 5` | `512:149/150`: a small chip pinned just above the selection box, naming kind + z-position + index | **NOT FOUND.** `#pm-sel` (`index.html:860-866`) renders handles only. The same information exists, but only in the Inspector header (`app.js:7306-7308`) — i.e. only when the right panel is on the Inspector tab. | MISSING | S2 |
| — | Double-click Text = inline edit; Tab cycle; arrows move; `[` `]` z; `H` hide; `Del` remove | `512:151` | `#pm-canvas-hint` `index.html:854-857` documents exactly this grammar; `app.js:7866` binds `Delete`/`Backspace` | MATCH | — |

## ③ State gallery (`514:125`) — twelve vignettes

| # | Node | State | Figma requires | Implemented | Verdict | Sev |
|---|---|---|---|---|---|---|
| **PME-036** | `514:126` | **Empty deck** | Rail shows a single **"No slides yet — + Add slide" CTA button (focused)**; canvas shows an empty-slide placeholder; a11y: canvas name **"Empty deck — add a slide"** | Rail: `#pm-slide-list` simply renders nothing and `#pm-add-slide` remains (`index.html:834-835`) — **no "No slides yet" copy**. The equivalent copy exists only in **grid mode**: `#pm-grid-empty` "This presentation has no slides yet" (`index.html:819`). Canvas `aria-label` is the static "Slide preview — editable canvas" (`index.html:858-859`). | **PARTIAL** — grid mode has it, the editor rail does not; the canvas a11y name never changes | S2 |
| **PME-037** | `514:130` | **Empty slide** | Background only + a faint centred **"Empty slide — add content with the toolbar"**; the toolbar buttons are the CTAs; never blank (NFR-024) | The **rail card** falls back to the word `"Empty slide"` (`app.js:7381`). The **canvas** renders whatever the host composes — no placeholder string was found in the operator or in `compose.rs`. | **MISSING** on the canvas | S2 |
| **PME-038** | `514:133` | **Empty / filtered media** | **Two distinct messages**: "No media yet — **+ Import**" (empty library, with a CTA) and "No results for ‹q›" (filter/search). Footer reads **"0 of media"**. | `app.js:7450-7454`: a single `.pm-media-empty` div reading **"No matching media."** for both cases, with **no `+ Import` CTA** and no query echo. Footer is `total_label + " of media"` (`app.js:7557`) so it does degrade correctly. | **PARTIAL** — one message where two are specified; CTA missing | S2 |
| **PME-039** | `514:136` | **Media cell — Missing** | Red-tinted tile + `⚠` + the word **Missing** + "File moved"; name in live-red; a **Relink…** action re-points the file; cannot be placed until relinked. A11y: "‹file›, media missing — relink". | Tile: `⚠` only, no "Missing" caption (`app.js:7473-7474`); solid not dashed border (`app.css:5006`); name red (`5008`); meta "File moved" (`app.js:7508`); thumb `disabled` + `aria-disabled` (`7499-7501`). **Relink exists only from the Inspector** (`app.js:7337`), not from the media tile. A11y label is "Missing media ‹file›" (`7470`) — no "relink" cue. | **PARTIAL** — see PME-021; the relink path is not reachable from the cell | S2 |
| **PME-040** | `514:140` | **Media cell — Unused** | A small visible **"unused" tag** on the cell; counts into the footer "· M unused". Informational; bulk "remove unused" is a later affordance. | Footer count: yes (`app.js:7561`). Cell tag: **NOT FOUND** — `a.unused` appears only inside the `aria-label` (`app.js:7472`). No CSS class for it exists. | **PARTIAL** — screen-reader-only, invisible to sighted users | S2 |
| **PME-041** | `514:143` | **Media cell — Importing** | Skeleton cell + spinner while the host reads metadata; `role="status"` announcing **"Importing ‹file›"**. Import = image picker today; video/audio disk import is later. | **NOT FOUND.** No "Importing" string, skeleton cell, or `role=status` announcement exists in the media path — `grep -n 'Importing' app.js` returns only the Theme Designer's unrelated stub (`app.js:2643`). | **MISSING** | S2 |
| **PME-042** | `514:146` | **Media cell — Hover / Selected** | Hover/focus: **accent outline + a subtle lift + a "+ add" affordance**, with a focus-visible ring (WCAG 2.4.7). Selected (the asset used by the current image element): **accent corner check + name in accent**. | Hover/focus: `.pm-asset-thumb:hover, :focus-visible { border-color: var(--sc-primary) }` (`app.css:4926`) — outline only, **no lift, no "+ add" affordance**. Selected: `.pm-asset.in-use` gives an accent ring + `.pm-asset-name` in `--sc-primary-hover` (`app.css:4924-4925`) — **no corner check**. | **PARTIAL** | S3 |
| — | `514:149` | **Present / Live** | Rail card shows a **left live-rule + a "LIVE" text badge** (not colour-only); `aria-label` appends **"(live on the audience output)"**. Routing the composite to the physical output is the deferred seam and the Present button is honest about it. | `.pm-slide.live .pm-slide-card { border-left: 3px solid var(--sc-live) }` (`app.css:4660`); `.pm-slide-live-badge` text "LIVE" (`app.js:7389-7393`); `aria-label` "(live on the audience output)" (`app.js:7377-7379`). Routing **is now wired** — `deck_go_live` sends the composed slide over the LAN link (`app.js:7001-7007`), toast "Now presenting on the audience output". | **MATCH**, and better than the frame's caveat — **but see the A11Y-DEFECT PME-001** on the badge's contrast | S1 (via PME-001) |
| — | `514:152` | **Delete slide (confirm)** | `role="alertdialog"` popover: **"Delete slide n?"** + Cancel / Delete, focus on Cancel, Esc cancels. Two-step, never a single-click destroy; ⌘Z also restores. | `app.js:7413-7425`: title `"Delete slide " + s.n + "?"`, body "This removes the slide and its elements from the deck. You can undo it.", confirm label **"Delete slide"**, plus an EXTRA warning when the slide is LIVE. The only-slide case disables the affordance with a reason (`app.js:7411`). Undo is real and bounded — `MAX_UNDO = 60` (`selahcue-operator/src/deck_workspace.rs:27`), above FR-016's ≥20. | **MATCH** (+ EXTRA live warning) | — |
| — | `514:155` | **Delete element / Undo** | Select → `Del` / inspector `🗑` → removed + a brief **"Element deleted — Undo"** toast (`role="status"`). Reversible via ⌘Z (≥20 steps). | `app.js:5563-5571`: `pmToast("Element deleted", "Undo", () => pmUndo())`; `#pm-toast` is `role="status" aria-live="polite"` (`index.html:771`); `pmUndo` → `deck_undo` (`app.js:7009`); depth 60. `Delete`/`Backspace` bound at `app.js:7866`; `🗑` at `app.js:7310`. | **MATCH** | — |
| — | `514:158` | **Remove media (in use)** | `role="alertdialog"`: **"Remove ‹file›? It's used on 2 slides."** Two-step; warns when the asset is referenced before removing. | `app.js:7519-7528`: title `"Remove " + a.name + "?"`, body "This removes the file from the media library. You can undo it.", warning "Used on N slide(s) — removing it leaves those slides with missing media.", confirm "Remove". | **MATCH** | — |
| **PME-043** | `514:161` | **System — Loading · Error · View-only** | Three sub-states. **Loading:** skeleton rail + canvas `aria-busy`, Live untouched. **Error:** non-blocking "Couldn't ‹action› — retry" with `role="alert"`, last-good state kept. **View-only (permission):** edit tools **hidden and out of tab order**, plus a **"View only" text chip**. | **Loading:** canvas only — `aria-busy` + `.pm-canvas-box.busy` shimmer (`app.js:5417`, `app.css:5133-5142`), plus the library grid (`app.css:5593-5600`). **No skeleton on the slides rail.** **Error:** `#pm-error` with `role="alert"`, Retry and Dismiss (`index.html:764-770`) — MATCH. **View-only:** **NOT FOUND** — a grep for `View only` / `view-only` / `viewOnly` across `app.js`, `index.html` and `app.css` returns nothing in the `pm-*` path. There is no permission-gated mode on this surface at all. | **PARTIAL** — Error MATCH, Loading partial, View-only MISSING entirely | **S1** |

## State coverage matrix — `509:124`

One row per vignette on the board, in board order.

| Vignette | Node | Implementation has it? | Where | Gap |
|---|---|---|---|---|
| 01 Right panel · Media (default) | `512:124` | **Yes** | `index.html:889-916` | — |
| 02 (absent from the board) | — | n/a | — | **PME-034** |
| 03 (absent from the board) | — | n/a | — | **PME-034** |
| 04 Inspector · Text | `510:126` | **Yes**, with drift | `app.js:7313-7328` | PME-026/027/028 |
| 05 Inspector · Shape | `511:124` | **Yes**, with drift | `app.js:7329-7334` | PME-030/031 |
| 06 Inspector · Image | `511:158` | **Yes**, with drift | `app.js:7336-7343` | PME-032/033 |
| Canvas · element selected | `512:137` | **Partial** — no z-badge | `index.html:860-866` | PME-035 |
| Empty deck | `514:126` | **Partial** — grid mode only | `index.html:818-821` | PME-036 |
| Empty slide | `514:130` | **Partial** — rail only, not canvas | `app.js:7381` | PME-037 |
| Empty / filtered media | `514:133` | **Partial** — one message, no CTA | `app.js:7450-7454` | PME-038 |
| Media cell — Missing | `514:136` | **Partial** — no caption, no relink from the cell | `app.js:7473-7474` | PME-039, PME-021 |
| Media cell — Unused | `514:140` | **Partial** — screen-reader only | `app.js:7472` | PME-040 |
| Media cell — Importing | `514:143` | **No** | — | PME-041 |
| Media cell — Hover / Selected | `514:146` | **Partial** — no lift, no "+ add", no corner check | `app.css:4924-4926` | PME-042 |
| Present / Live | `514:149` | **Yes** | `app.js:7389-7393`, `7001-7007` | PME-001 (a11y) |
| Delete slide (confirm) | `514:152` | **Yes** | `app.js:7413-7425` | — |
| Delete element / Undo | `514:155` | **Yes** | `app.js:5563-5571` | — |
| Remove media (in use) | `514:158` | **Yes** | `app.js:7519-7528` | — |
| System — Loading | `514:161` | **Partial** — canvas + library grid, no rail skeleton | `app.js:5417` | PME-043 |
| System — Error | `514:161` | **Yes** | `index.html:764-770` | — |
| System — View-only (permission) | `514:161` | **No** | — | **PME-043** |

**Coverage: 9 of 21 fully implemented, 8 partial, 2 absent from the design, 2 missing entirely.**

---

# Frame `547:124` — Presentations (Library + New), 1760×1000

The implementation of this frame is `#pm-library` (`index.html:773-804`) — a **view mode of the
Presentation surface**, not a separate route. `docs/design/PRESENTATIONS-LIBRARY-spec.md` already
specifies this frame accurately; where the implementation drifts below, it drifts from **both** the
frame and that spec.

Note for the a11y record: `547:137` `btn-new` is **flat `#6E5CF0`**, not a gradient — white 13.5 px
semibold on it is 4.72:1. The violet-gradient problem is confined to the older flagship (`331:126`,
`329:140`).

## Topbar (`547:125`, h 64)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Bar | `bg #14161D`, `border-bottom #262A34`, `px 28`, gap 14, h 64 | `.pm-lib-head` `app.css:5388-5396`: `padding: 16px 28px`, `gap: 14px`, `border-bottom: 1px solid var(--sc-border)` | MATCH (h implied 64 ≈ 16+30+16) | — |
| **PME-044** | App icon `▦` | `547:127/128`: a **30 px `#6E5CF0` rounded-8 tile** with a white 15 px bold `▦` | `index.html:775`: a bare `<span class="pm-plan-ico">▦</span>` coloured `--sc-primary-hover` (`app.css:5408`) — **no tile** | DRIFT | S3 |
| — | Title "Presentations" | `547:129`: Inter Bold **17 px** `#F4F6FB` | `.pm-lib-title` `app.css:5407`: **16 px** / 700 / `--sc-text` | DRIFT (1 px) | S4 |
| **PME-045** | Subtitle "Your slide decks" | `547:130`: Inter Regular 12.5 px `#6B7383`, sitting beside the title | **NOT FOUND** in `index.html:774-785` | MISSING | S3 |
| — | Search field | `547:132`: 280×38, `bg #0F1116`, `1px #262A34`, r9, `px12`, gap 8; `⌕` 15 px; placeholder "Search presentations" 13 px `#6B7383` | `.pm-lib-search` `app.css:5411-5419`: h **38**, r **9**, `--sc-inset`, `padding 0 12px`, gap 8; `.pm-lib-q` width **210 px**, 13 px (`5421`); placeholder text matches (`index.html:778`) | MATCH except the field is 210 px wide inside a hug, vs a fixed 280 | S4 |
| **PME-046** | Sort control | `547:135/136`: a **`Recent ▾` chip** — `bg #1C1F28`, `1px #262A34`, r9, h 38, `#A7AEBE` 13 px medium. The cards' "edited 2h ago" metadata confirms recency is the intended default sort. | `index.html:780-783`: a `<label>Sort</label>` + `<select>` with **only `Name` and `Slides`**. **There is no "Recent" option**, and `pmRenderLibGrid` (`app.js:6716`) sorts by name or slide count only. | DRIFT (chip→labelled select) + **MISSING** the Recent option | S2 |
| — | `＋ New Presentation` | `547:137/138`: **flat `#6E5CF0`**, r9, h 38, `pl16/pr18`, white 13.5 px semibold | `#pm-lib-new` `index.html:784`, `.pm-btn-primary` `app.css:4592-4601`: flat `--sc-primary`, r8, `padding 7px 16px`, 14 px/600 | MATCH (r8 vs r9) — **but see PME-005 for the hover state** | S4 |

## Body (`547:139`)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Count "7 presentations" | `549:125`: at the head of the body, left | `#pm-lib-count` `index.html:789`, `aria-live="polite"`; text at `app.js:6719` — `"N presentation(s)"` plus `" · M matching"` while filtering | MATCH (+ EXTRA match count) | — |
| **PME-047** | **Grid / List view toggle** | `549:127-131`: a two-segment control `▦ Grid` / `☰ List`, 124×28, right-aligned on the count row | **NOT FOUND** for the presentations library. (`.pm-deck-seg` at `app.css:6012-6016` is a *different* control — the plan-item deck **picker** modal.) | **MISSING** | S2 |
| — | Grid | `549:132`: `flex-wrap`, **gap 24**, tiles 405 wide → 4-up at 1760 | `.pm-lib-grid` `app.css:5439-5443`: `repeat(auto-fill, minmax(300px, 1fr))`, **gap 22** | DRIFT (responsive vs fixed 405; gap 22 vs 24) — the responsive rule is the better choice | S4 |
| — | Body padding | `549:132` at x28 under a 22 px head offset | `.pm-lib-body` `app.css:5437`: `padding: 18px 28px 28px` | MATCH | — |

### New tile (`549:133`)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **PME-063** | Tile | `bg #14161D`, **1.5 px dashed `#363B47`**, r12, **h 292**, gap 10, centred | `.pm-lib-new-tile` `app.css:5522-5535`: `1.5px dashed var(--sc-border-strong)`, r12, `--sc-surface`, gap **8**, **`min-height: 232px`** | DRIFT — 60 px shorter than the cards it sits beside, so the row is ragged | S2 |
| — | `＋` disc | `549:134/135`: **46 px**, r23, `bg #201F3A`, `1px #7E6EFF`, glyph 22 px `#7E6EFF` | `.pm-lib-new-plus` `app.css:5538-5548`: **44 px**, r22, `--sc-accent-soft`, `1px --sc-primary-hover`, **20 px** | DRIFT (2 px) | S4 |
| — | Label "New presentation" | `549:136`: 15 px semibold `#F4F6FB` | `app.js:6731` text; `app.css:5545`: **14.5 px** / 600 | DRIFT (0.5 px) | S4 |
| **PME-048** | Sub-label | `549:137`: **"Start a blank deck or from a template"** 12.5 px `#6B7383` centred | `app.js:6732`: **"Start a blank deck"** — the "or from a template" half is dropped | DRIFT (copy). Defensible: templates are not built (see PME-052), so the shorter copy is *honest*. Correct the frame, or restore the copy when templates land. | S4 |

### Deck card (`549:138` and siblings)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Card | `bg #1C1F28`, `1px #262A34`, r12, 405×292 | `.pm-lib-card` `app.css:5446-5457`: `--sc-elevated`, `1px --sc-border`, r12 | MATCH | — |
| **PME-049** | Card thumbnail | `549:139`: **405×214** (1.89:1) on `bg #0F1116`, containing a **slide-shaped skeleton preview** — an accent title bar 150×16 r4, then three body bars (341/301/261 × 7, r3) in `#363B47` | `.pm-lib-thumb` `app.css:5459-5468`: **`aspect-ratio: 16 / 9`** (= 227.8 tall at 405 wide) with `linear-gradient(135deg,#2A2F52,#14161D)` and a single **46 px `▦` glyph** at 16 % white (`app.js:6746`) | DRIFT — wrong ratio (14 px taller) **and** a generic icon where the design shows a deck-like preview | S2 |
| **PME-050** | Thumbnail accent colour | The title bar's colour **varies per card**: `#35C08A` (preview green), `#F2B84B` (gold), `#38BDF8` (info blue), `#7E6EFF` (violet) across the seven cards | n/a — no per-deck accent exists | UNSPECIFIED — is the accent meaningful (deck kind / colour tag) or decorative variety? **Q-07** | S3 |
| — | Slide-count pill | `549:144/145`: `bg black @ 62 %`, r6, `px8/py3`, white **11.5 px semibold**, inset ~14 right / 12 bottom | `.pm-lib-pill` `app.css:5469-5479`: `rgba(0,0,0,0.62)`, r6, `padding 2px 8px`, `right 10 / bottom 10`, 11.5 px / **700** | MATCH (± 2–4 px inset, weight 700 vs 600) | S4 |
| — | Card name | `549:148`: 14.5 px semibold `#F4F6FB`, ellipsised | `.pm-lib-name` `app.css:5498`: 14.5 px / 600 / `--sc-text`, ellipsised | **MATCH** | — |
| **PME-051** | Card meta | `549:149`: **"24 slides · edited 2h ago"** 12 px `#6B7383` — a **relative edited time** | `app.js:6753`: `mt.textContent = meta` where `meta = "N slides"` (`app.js:6740`) — the **same string as the pill**, duplicated, with **no edited time** | DRIFT + MISSING. `PRESENTATIONS-LIBRARY-spec.md` §7 also requires the edited time in the card's accessible name. | S2 |
| — | `⋯` button | `549:150/151`: 30×30, r7, glyph 18 px `#A7AEBE` | `.pm-lib-dots` `app.css:5501-5514`: 30×30, r7, 18 px, `--sc-text-secondary`; `aria-label` "More actions for ‹name›" (`app.js:6757`) | MATCH | — |
| — | Open-deck marker | not drawn | `.pm-lib-openflag` "OPEN" chip + `.pm-lib-card.open` accent ring (`app.css:5458`, `5480-5490`; `app.js:6747`) | EXTRA (useful — back-fill the frame) | S4 |
| — | Persistence banner | not drawn | `#pm-lib-nopersist` `index.html:786-787`: "Changes aren't being saved on this machine — the presentation store couldn't open." `role="status"`, warn-soft tint (`app.css:5425-5434`) | EXTRA (honest and important — back-fill the frame) | S4 |

---

# Frame `552:124` — Presentations · Create & Manage, 1760×900

Three annotated panels: ① the New-Presentation dialog, ② the first-run empty state, ③ the card `⋯`
menu + delete confirm.

## ① Create — "New presentation" dialog (`552:130`, 430×396)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Dialog | 430×396, title "New presentation" at `552:131` | `pmPrompt` `app.js:5579-5607` — `role="dialog" aria-modal="true"`, focus-trapped, Esc cancels, `input.focus(); input.select()` | MATCH on chrome and behaviour | — |
| **PME-052** | `Name` field default | `552:135`: pre-filled **"Sunday Service — Aug 11"** — a *suggested* name derived from service + date, fully selected so typing replaces it | `app.js:6798`: `value: "Untitled presentation"` | DRIFT — the frame and `PRESENTATIONS-LIBRARY-spec.md` §4 both specify a suggested name | S2 |
| **PME-053** | **`Start from` radio group** | `552:136-153`: three options, each a 16 px radio + a two-line label — **Blank deck** / "One empty slide, ready to edit"; **Duplicate an existing presentation** / "Copy slides + theme from another deck"; **From a template · later** / "Themed starters (sermon, song, liturgy)" (an honest disabled "later") | **NOT FOUND.** `pmPrompt` (`app.js:5579-5607`) renders a title, one label, one text input and two buttons. There is no `Start from` group of any kind. Duplicate exists, but only from the card `⋯` menu (`app.js:6774`). | **MISSING** — the largest single omission on this frame | **S1** |
| — | `Cancel` / `Create presentation` | `552:157`, `552:159` | `app.js:5592-5593`: `.pm-btn-ghost` "Cancel" + `.pm-btn-primary` with `confirmLabel: "Create presentation"` (`app.js:6798`) | MATCH | — |

## ② Empty — first run, no presentations (`552:162`)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Icon plate | `552:163/164`: a 70×72 plate holding a 26×36 `▦` | `.pm-lib-empty-ico` `app.css:5586-5590`: 68×68, r17, `--sc-accent-soft`, **1 px dashed `--sc-primary`**, glyph 28 px | DRIFT (dashed border is EXTRA; 68 vs 70×72) | S4 |
| — | Title "No presentations yet" | `552:165` | `index.html:793` — **exact string match**; `.pm-lib-empty-title` 17 px / 700 (`app.css:5591`) | **MATCH** | — |
| — | Body "Create your first slide deck — a sermon, a song set, or announcements." | `552:166` | `index.html:794` — **exact string match**; `.pm-lib-empty-sub` (`app.css:5592`) | **MATCH** (colour: see PME-008) | — |
| — | `＋ New Presentation` | `552:167/168` | `#pm-lib-empty-new` `index.html:795`, `.pm-btn-primary` | MATCH | — |
| **PME-054** | "or ⌘N" hint | `552:169`: a hint line **below** the CTA | **NOT FOUND** in the empty state. `⌘N` is bound and titled on `#pm-newpres` (`index.html:760`), but never surfaced here. | MISSING | S3 |

## ③ Manage — card `⋯` menu + delete confirm (`553:126`)

### Card `⋯` menu (`553:128`, 248×229)

Figma order: `↗ Open` · `✎ Rename` · `⧉ Duplicate` · `◫ Present` · `⇩ Export deck (.json)…` · —— ·
`🗑 Delete`. Each row 236×34 with a leading glyph.

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Menu chrome | 248 wide, rows 34 tall, a divider before Delete | `.pm-lib-menu` `app.css:5551-5570`: `min-width: 190px`, rows `padding 8px 10px`, `.pm-lib-menu-div` before Delete; `role="menu"`, arrow-navigable, Esc + Tab close and restore focus (`app.js:6764-6785`) | DRIFT (190 vs 248 min-width) + EXTRA (keyboard model) | S4 |
| — | `Open` | `553:131` | `app.js:6770` `item("Open", …)` | MATCH (glyph missing) | S4 |
| — | `Rename` | `553:134` | `app.js:6771` — **`"Rename…"`** | DRIFT (ellipsis) | S4 |
| — | `Duplicate` | `553:137` | `app.js:6772` | MATCH (glyph missing) | S4 |
| **PME-055** | `Present` | `553:140` — present the deck straight to live from the library | **NOT FOUND** in `pmLibOpenMenu` (`app.js:6766-6775`) | **MISSING** — compounds PME-014: there is now *no* button anywhere that presents a deck | **S1** |
| **PME-056** | `Export deck (.json)…` | `553:143` | **NOT FOUND** anywhere in `app.js` | MISSING | S2 |
| — | `Delete` (danger) | `553:146` | `app.js:6774` `item("Delete", …, true)` → `.danger` `--sc-live` (`app.css:5567`) | MATCH (glyph missing) | — |
| **PME-057** | Menu item **glyphs** | Every row carries a leading glyph: `↗ ✎ ⧉ ◫ ⇩ 🗑` | `app.js:6768` sets `b.textContent = label` only — no glyph is ever rendered, though `.pm-lib-menu button` reserves `gap: 10px` for one (`app.css:5559`) | MISSING (all six) | S3 |

### Delete confirm (`553:148`, 430×205)

| # | Component | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Dialog | `role="alertdialog"`, Cancel-focused, Esc cancels (per `PRESENTATIONS-LIBRARY-spec.md` §7) | `pmConfirm` — invoked at `app.js:6989-7000` | MATCH | — |
| — | Title | `553:149`: `Delete "Youth Night — Identity"?` | `app.js:6991`: `"Delete “" + name + "”?"` | MATCH | — |
| **PME-058** | Body copy | `553:150`: "This removes the presentation and **its 12 slides** from your library. **You can undo it.**" | `app.js:6992`: "This removes the presentation and **its slides** from your library. **This can't be undone.**" | **DRIFT — and a direct contradiction.** Two separate problems: (a) the **slide count is missing**; (b) the design promises undo, the implementation denies it. The implementation is telling the truth — `pmLibDelete` fires `deck_delete` and toasts a bare "Presentation deleted" (`app.js:6994`) with **no Undo action**, unlike the slide/element deletes which do pass one (`app.js:5570`). So the **design promises reversibility the backend does not provide**. **Q-08** | **S1** |
| **PME-059** | In-plan warning | `553:152/153`: `⚠ Used in "Sunday Service — Aug 4" — that plan item will show missing.` — warns when the deck is **referenced by a service plan** | `app.js:6993`: the warning fires only when the deck is **the one currently open in the editor** ("It's the presentation you have open — deleting it switches the editor to another."). **The plan-reference check does not exist.** | **MISSING** — a plan can silently lose its deck | **S1** |
| — | `Cancel` / `Delete` | `553:157`, `553:159` | `app.js:6995` `confirmLabel: "Delete"` | MATCH | — |

---

# Part B — audience output rendering

## Frame `208:124` — Theme templates, audience output (S8-3a), 1440×360

Three 440×248 mocks (≈16:9) of what the **compositor** puts on the audience screen. The board draws
absolutely-positioned text; the implementation models regions in per-mille. Positions below are
converted to ‰ of the mock (÷440 horizontal, ÷248 vertical) so they are directly comparable.

### `OUT-001` — this frame is **pre-Design-2.0** and was never re-skinned

| Evidence | Value | Design 2.0 equivalent |
|---|---|---|
| Board background `208:124` | `#0E1116` | `tokens::design2::BASE` is `#0B0D12`. `#0E1116` is the **legacy** `tokens::BG_BASE` (`selahcue-present/src/tokens.rs:77`). |
| Every caption (`208:125`, `208:129`, `208:136`, `208:138`, `208:142`) | `#9AA4B2` | The legacy `textMuted`. Design 2.0's is `TEXT_SECONDARY #A7AEBE` (`tokens.rs:151`). |
| The amber reference ink | `#F2B53C` | Design 2.0's `GOLD` is `#F2B84B` (`tokens.rs:165`). |

The implementation agrees with the **frame**: `const AMBER: Rgba = { r: 242, g: 181, b: 60 }`
(`selahcue-present/src/theme.rs:420-425`) is exactly `#F2B53C`. So this is **MATCH**, not drift — but
it means the audience output runs on the *legacy* amber while every chrome surface runs on Design
2.0's gold. Whether the output palette should track the chrome palette is a real question with a
four-surface consequence — **Q-09**. Severity **S3**, informational until answered.

### `208:126` — Scripture — Full

| # | Component | Figma spec (converted) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| **OUT-002** | Background | a **two-stop linear gradient**: `#0D1730 → #1B2E5A` at **150.59°**, second stop at **71.4 %** | `Theme::classic()` `theme.rs:447`: `Background::Solid(Rgba::rgb(8, 10, 20))` = `#080A14` — **a flat colour** | DRIFT — the model *can* express a gradient (`Background::Gradient`, `theme.rs:360`) but no built-in uses one | S2 |
| **OUT-003** | Gradient angle | 150.59° with a mid-stop at 71.4 % | `GradientDirection` (`selahcue-engine/src/scene.rs:222-235`) is a **four-value enum** — `Vertical`, `Horizontal`, `DiagonalDown`, `DiagonalUp`. `GradientBackground` (`theme.rs:332-338`) has exactly two stops at 0 % and 100 %. | **MISSING** — neither an arbitrary angle nor a mid-stop position is expressible | S2 |
| **OUT-016** | Reference line | `208:127`: centred, `#F2B53C`, Inter SemiBold, y **282 ‰**, size **60 ‰** | `theme.rs:448-460` `title`: `x 60‰ y 150‰ w 880‰ h 110‰`, centre/middle → optical centre **205 ‰**; `size_permille: 48`; `color: AMBER`; `Fit::ShrinkToFit` | DRIFT — 77 ‰ higher and 12 ‰ smaller than the mock | S2 |
| **OUT-017** | Body | `208:128`: centred white Inter Bold, x **91 ‰**, w **818 ‰**, y **395 ‰**, size **105 ‰** | `theme.rs:461-479` `body`: `x 60‰ y 280‰ w 880‰ h 560‰`, centre/middle → optical centre **560 ‰**; `size_permille: 78`; `line_height_permille: 1150` | DRIFT — 165 ‰ lower and 27 ‰ smaller | S2 |
| — | Mapping caveat | The mock positions text **absolutely**; the implementation lays out **regions with vertical centring and shrink-to-fit**. A one-line verse therefore sits where the region centres it, not where the mock draws it. | — | An exact mapping needs an owner call on whether the mock is normative geometry or an illustration — **Q-10** | S3 |

### `208:130` — Song — Center

| # | Component | Figma spec (converted) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Background | `#080A0F` flat | `Theme::classic()` `theme.rs:447`: `#080A14` | DRIFT (5 units of blue) | S4 |
| **OUT-004** | Stanza lines | `208:131-134`: **four separate 24 px bold white lines**, tops 52/86/120/154 → pitch **137 ‰**, size **97 ‰**, implied line-height **1417 ‰** | `Slide` (`slide.rs:9-12`) is `{ title: String, body: Vec<String> }`; `classic().body.line_height_permille = 1150` (`theme.rs:472`) | DRIFT — 267 ‰ tighter leading than drawn | S3 |
| **OUT-005** | **No title region** | The Song mock has **no** reference/title line — the first stanza line starts at the top of the text block. `Theme`'s doc (`theme.rs:376-379`) assumes "title = the song title", which this frame contradicts. | `Theme` always has a `title` region; `RegionStyle.visible` (`theme.rs:65`) can hide it, but no built-in does | DRIFT (expressible, not configured) | S3 |
| **OUT-006** | **CCLI footer** | `208:135`: `CCLI #7115744 · Sinach` — 10 px regular `#9AA4B2` at y **911 ‰**, centred. A licensing/attribution line the mock's own caption calls out as **(S8-5)**. | **NOT FOUND.** `Theme` (`theme.rs:386-419`) has `background`, `title`, `body`, optional `band`, `font`, `weight`, `letter_spacing_permille`, `elements` — **no footer / attribution region**. a `grep` for `ccli` / `attribution` / `footer` under `selahcue-present/src/` matches only `stage.rs` (the *stage monitor*, a different surface). | **MISSING** — and CCLI reporting is a legal obligation for song use, not a nicety | **S1** |
| — | Workaround | — | An `Element::Text` (`theme.rs:139`) could carry it, but that is per-theme static text, not per-song data | — | S4 |

### `208:137` — Lower Third — Stream

`Theme::lower_third()`'s own doc-comment cites this node (`theme.rs:524-532`) and records an owner
refinement ("the band spans nearly the full width (3 %–97 %) rather than a narrow left column"), so
this is the one template built directly against its frame.

| # | Component | Figma spec (converted) | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Band rect | `208:139`: x **27 ‰**, y **661 ‰**, w **945 ‰**, h **258 ‰**, r8 | `theme.rs:568-579` (`band`): `x 30‰ y 660‰ w 940‰ h 300‰` | MATCH on x/y/w; DRIFT on height (+42 ‰) | S3 |
| **OUT-007** | Band fill | `#05080D` at **90 % opacity** — a near-black tinted panel | `Rgba { r: 0, g: 0, b: 0, a: 150 }` (`theme.rs:571-576`) = pure black at **59 %** | DRIFT — noticeably more transparent, and untinted | S2 |
| — | Band border | 1 px `#F2B53C` on a 248-tall mock = **4 ‰** | `border: AMBER`, `border_permille: 5` (`theme.rs:577-578`) | MATCH | — |
| **OUT-008** | Reference line size | `208:140`: **16 px bold** = **65 ‰**, `#F2B53C`, at y **706 ‰** | `theme.rs:538-551` `title`: `size_permille: 40`, `y 688‰`, `align_h: Left`, `align_v: Middle` | DRIFT — the reference renders at **40 ‰ where the frame draws 65 ‰** (roughly 60 % of the drawn size), so the reference reads much smaller than the body instead of matching it | S2 |
| — | Body line size | `208:141`: 16 px semibold white = **65 ‰**, y **794 ‰** | `theme.rs:552-566` `body`: `size_permille: 62`, `y 762‰`, `align_h: Left`, `align_v: Top` | MATCH (±3 ‰) | — |
| — | Background behind the band | `#051A0F` — the mock's stand-in for keyed video, with the caption "(transparent / keyed over live video)" (`208:138`) | `Background::Solid(Rgba::rgb(4, 12, 9))` = `#040C09` (`theme.rs:537`); the doc-comment (`theme.rs:534-536`) states true NDI alpha-keying is a later slice | DRIFT on the exact hex; the **honest deferral is correctly documented** | S4 |

### `OUT-009` — the template *set* does not match

| Figma template | Role | Nearest built-in |
|---|---|---|
| Scripture — Full | content role: scripture | — |
| Song — Center | content role: song | — |
| Lower Third — Stream | output role: keyed stream | `lower_third` |

`Theme::BUILTIN_NAMES` (`theme.rs:590`) is `["classic", "high-contrast", "lower-third"]` — i.e. two
**style variants** (`classic`, `high-contrast`) plus one output role. The frame's set is
**per-content-role** templates. Only `lower-third` overlaps. `high_contrast()` (`theme.rs:487-531`)
is drawn nowhere on the board; `Scripture — Full` and `Song — Center` have no implementation.

The `Theme` doc already anticipates this: *"Per-role templates + per-item override are S8-3d"*
(`theme.rs:380-381`). So this is **scoped-later, not broken** — but it is the reason `OUT-002`,
`OUT-004` and `OUT-006` all read as gaps: the objects the frame designs do not yet exist.
Verdict **MISSING (scoped)**, severity **S2**.

## Frame `390:124` — Background — States (Design 2.0), 1216×449

This frame draws a **Theme Designer panel**. Its *UI* belongs to the Theme Designer surface and is
out of scope here. What is in scope is the **background model it implies the compositor must
render**: three modes, two gradient stops, an angle, and a per-device image.

| # | Model requirement | Figma spec | Implemented | Verdict | Sev |
|---|---|---|---|---|---|
| — | Three modes `Solid / Gradient / Image` | `390:132-138` — a three-segment control | `Background` enum (`theme.rs:356-364`): `Solid(Rgba)` / `Gradient(GradientBackground)` / `Image(ImageBackground)`, `#[serde(untagged)]` so an existing solid theme's JSON stays byte-identical | **MATCH** | — |
| — | Solid: a hex value | `393:127` — `#0E1016` beside a 22 px swatch | `Background::Solid(Rgba)` (`theme.rs:358`) | MATCH (the value `#0E1016` is the legacy `BG_BASE`, see OUT-001) | S4 |
| **OUT-010** | Solid: **5 preset chips** | `393:130-135` — five 59.2×34 chips under a `PRESETS` overline; **the five colours are not labelled anywhere in the frame** | No preset list exists in `theme.rs` or `tokens.rs` | UNSPECIFIED — which five? — **Q-11** | S3 |
| — | Gradient: two stops | `390:166-170` — `#241C4A` (from) and `#0E1016` (to) | `GradientBackground { from, to }` (`theme.rs:332-338`) | **MATCH** | — |
| **OUT-011** | Gradient: **angle** | `390:172-174` — an `ANGLE` field reading **`180° · Vertical`**: a degree value *and* a named preset | `GradientDirection` (`scene.rs:222-235`) — a four-value enum, no degrees | DRIFT — `180° · Vertical` maps onto `GradientDirection::Vertical`, so the *drawn* value is expressible, but the control implies free angles the model cannot carry. Compare `OUT-003`: `208:126` uses **150.59°**, which is **not** expressible. **Q-12** | S2 |
| — | Image: drop-zone | `394:129/130` — "Drop an image here" / "PNG or JPG · on this machine" | `ImageBackground { source: MediaRef }` (`theme.rs:344-346`); `ImageFormat` (`selahcue-engine/src/media.rs:76-95`) is exactly `Png` / `Jpeg`, **sniffed not trusted from the extension** (`media.rs:82-84`) | **MATCH**, and the implementation is stricter than the frame promises | — |
| — | Image: per-device | `394:133` — "Stays on this machine — themed backgrounds are per-device." | `theme.rs:340-343`: "the decoded pixels never ride the theme JSON; a missing/corrupt/unsupported source draws the missing-media placeholder (FR-070), never a blank frame or a crash" | **MATCH** | — |
| — | Image: fit | not drawn | `ImageFit` exists in the scene model and the operator exposes Stretch/Fit/Fill (`app.js:7341`) | EXTRA | S4 |

## `OUT-012` — the GPU compositor cannot render any of these templates

`selahcue-gpu/src/compositor.rs:6-12` states it plainly: *"This pipeline renders only `Layer::Fill`
and **silently skips `Layer::Text`, `Layer::Image`, and `Layer::Shape`**"*. There is no
`Layer::Gradient` arm either — the only match is `if let Layer::Fill { rect, color } = layer`
(`compositor.rs:160`).

The SSIM ≥ 0.99 parity oracle (`selahcue-gpu/tests/test_parity.rs:92-106`) therefore proves parity
**only over fill-rect frames**. It is not evidence that the GPU path can draw a scripture slide.

This is **not a live regression**: the same file records that the desktop shell CPU-composites via
`selahcue-present` and blits the framebuffer, so text renders on screen today. It is ADR-0002's
intended-future path. But it means **the audience-output parity claim in the architecture summary is
narrower than it sounds**, and any plan to move the screen onto the GPU compositor must first land
glyph, image, shape and gradient rendering. Verdict **MISSING (scoped, documented)**, severity **S2**.

## `OUT-013` — the `measure_word` memo key is a live trap for anything in this spec

`compose.rs` changed under this audit (commit `53f0032`): `autofit_layers` now calls
`crate::measure::measure_word(...)` (`compose.rs:87-88`, `105`), backed by a bounded LRU in the new
`selahcue-present/src/measure.rs` that **persists across composes**
(`MAX_MEASURE_CACHE_ENTRIES = 4096`, `measure.rs:43`). Layout output is bit-identical by design.
**Verified: it does not move a pixel in this parity pass.**

The memo key is:

```rust
struct Key { text: Box<str>, cell: u32, font: Option<FontName>, weight: u16 }   // measure.rs:22-27
```

with a hand-written `Hash` over the same four fields (`measure.rs:29-36`), because `FontName` is `Eq`
but not `Hash`. Its doc-comment is the contract: *"Everything that changes the shaped width of a run
of text — i.e. exactly the arguments of `selahcue_engine::raster::measure_line_width`"*.

**Today this is correct**, and deliberately so: `letter_spacing_permille` is **excluded** and added
*outside* the memo as a per-glyph multiply (`compose.rs:84`, `105-106`), with the reasoning stated at
`compose.rs:103-104` — *"folding it into the key would split the memo per tracking value for no
saving"*.

**The trap:** if any change in this audit introduces a **new attribute that affects text shaping
inside `measure_line_width`** — a different shaping mode, font stretch/width, a real tracking applied
during shaping rather than after, small-caps, a variable-font axis — it **must** be added to `Key`
*and* to the hand-written `Hash`. Miss either and the memo silently returns a width measured under
the old attribute, so lines wrap wrong and `Fit::ShrinkToFit` picks the wrong cell — with no error
and no failing test, because the cache hit *looks* like a success.

Two candidate changes in this audit touch that boundary: **OUT-008** (the lower-third reference size)
is safe — `cell` is already in the key. Any future per-region tracking, or a font-weight rendering
change, is not.

## `OUT-014` — a token *value* change is a four-surface lockstep change

`selahcue-present/tests/test_tokens.rs::design2_palette_is_pinned_across_surfaces` cross-checks the
Design 2.0 palette against **four** sources: `dist/app.css`, `tokens::design2::MANIFEST`,
`StageTheme::dark()`, and the mobile `design_tokens.dart` — the last by source-text grep for the
literal `d2<Camel> = Color(0xFF<HEX>)` (`test_tokens.rs:525-530`).

Consequences for this audit: **Q-02** (a second compliant muted token), **Q-09** (output amber
`#F2B53C` → Design 2.0 gold `#F2B84B`), and **OUT-010** (a preset palette) are all four-surface
stories, not local edits. None of them is proposed as a fix here; each is an open question.

## `OUT-015` — `Slide` cannot express what the frames draw

`Slide` (`slide.rs:9-12`) is `{ title: String, body: Vec<String> }` and its own doc says *"Richer
content (media, columns) extends this later"* (`slide.rs:6-7`). Against the frames:

- `208:130` needs **song metadata** (CCLI number, author) distinct from body lines → **OUT-006**.
- `329:124`'s deck slides include a **video slide** (`329:158`, "▶ Testimony clip") and an **image
  slide** (`329:170`, "🖼 Harvest field") — content kinds `Slide` has no field for. The authored path
  uses `Theme::elements` (`theme.rs:417`) instead, via `compose_authored_slide` (`compose.rs:659`),
  so the two content models are parallel rather than unified.

Verdict **MISSING (scoped)**, severity **S3**. Recorded so the CCLI and media-slide work is planned
against the model rather than bolted onto `body: Vec<String>`.

---

# Cross-check against the existing specs

## `docs/design/DESIGN-2.0-HANDOFF.md` (2026-08-01) — stale, confirmed

Its node map (§1, `DESIGN-2.0-HANDOFF.md:19-30`) lists **only** `329:124` for this area
(row 4, "Presentation & Media (mini-deck)"). It contains **no reference to `509:124`, `547:124`,
`552:124`, `208:124` or `390:124`** — verified by grep. §5.4 (`:175`) describes `329:124` as a "NEW
build". Live Figma wins throughout this audit; the handoff should be re-pointed at the five frames it
omits.

## `docs/design/PRESENTATION-MEDIA-STATES-spec.md` (2026-08-04) — agrees, and is more current than it claims

| Where | Status |
|---|---|
| §"What this is" — "Node `329:124` shows exactly **one** state … so the shipped implementation had to infer them" | **Still true.** This audit confirms the flagship draws one state; `509:124` is the states board it promises. |
| §1 anatomy diagram — `TOPBAR ▦ Presentation · <deck name> · N slides [Add to plan] [▶ Present]` | **Drifted.** `Add to plan` was deliberately dropped (PME-015); `▶ Present` was **never built as a control** (PME-014). The spec's own diagram still shows both. |
| §"Owner decisions (2026-08-04)" #2 — the right 360 px column becomes contextual, Media ⟷ Inspector | **Now shipped.** The spec's "Design ↔ implementation delta (honest)" paragraph says *"there is **no** inspector … this spec introduces one; that is an implementation-rework follow-up (§8)"*. That rework **has landed** — `#pm-inspector-body` (`index.html:904`), `app.js:7288-7352`. The spec's delta note is out of date and should be marked resolved. |
| §"Tokens" list | Matches `dist/app.css` `:root` (`app.css:4574-4622`) exactly. Note it repeats `--sc-text-muted` without the AA-large caveat — worth aligning with `app.css:4472-4478`. |

## `docs/design/PRESENTATIONS-LIBRARY-spec.md` (2026-08-04) — agrees with Figma; the implementation drifted from both

This spec is accurate against `547:124` / `552:124`. Every row below is a place where the
implementation departs from the spec **and** the frame — so these are not design ambiguities, they
are unbuilt spec:

| Spec | Says | Implementation | Gap |
|---|---|---|---|
| §3 anatomy (`:30-52`) | `[Recent ▾]` sort · `[▦ Grid] [☰ List]` toggle · "Your slide decks" | Name/Slides select; no toggle; no subtitle | PME-046, PME-047, PME-045 |
| §4 (`:57`) | Name pre-filled `"<Service> — <date>"` | `"Untitled presentation"` | PME-052 |
| §4 (`:58-61`) | `Start from` radio group — Blank / Duplicate / Template·later | absent | **PME-053** |
| §5 (`:70`) | `⋯` menu: Open · Rename · Duplicate · **Present** · **Export deck (.json)…** · — · Delete | Open · Rename… · Duplicate · — · Delete | PME-055, PME-056 |
| §5 (`:72`) | Delete copy: "…its **N slides**… **You can undo it.**" + toast "Presentation deleted — **Undo**" | "…its slides… **This can't be undone.**", toast without an Undo | **PME-058** |
| §5 (`:72`) | ⚠ warning when the deck is **referenced by a service plan** | warns only when the deck is the one open in the editor | **PME-059** |
| §6 state matrix (`:79-89`) | Search-no-results copy: "No presentations match "<q>" — **Clear search**" | `app.js:6724-6726` renders "No presentations match "<q>"" with **no Clear affordance** | PME-060 |
| §7 (`:96`) | Card accessible name = deck name + meta + **edited time** | `app.js:6745`: name + slide count only | PME-051 |

`PME-060` is assigned here: **the "Clear search" affordance in the library's no-results state is
missing** (`app.js:6724-6726`), severity **S3**.

---

# Open questions for the owner

Each is answerable in a word or two.

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| **Q-01** | Should the Design 2.0 palette become **Figma variables**? | `get_variable_defs` returns `{}` for every frame audited — nothing is bound, so each frame carries raw hexes and drifts independently (this is exactly how `208:124` kept the legacy palette). | Leave as-is; keep auditing by hand. |
| **Q-02** | Add **a second muted token** for small type (clears 4.5:1, still a third tier), or promote everything to `--sc-text-secondary`? | Decides PME-012 and the count-pill/placeholder tier. A new token is a four-surface lockstep change (OUT-014). | Promote only PME-006…PME-011; leave the rest. |
| **Q-03** | Figma `511:140` fills the sample shape with **`#7C5CFF`** — a violet that is in no palette. Sample content, or a stray value? | If it is meant to be a token, the shape default should use `--sc-primary`. | Sample content; ignore. |
| **Q-04** | The states board numbers its inspector panels `01, 04, 05, 06`. **What were 02 and 03?** | Two designed states are missing from the file. Likely a Background inspector and a no-selection/multi-selection state. | Treat as never-drawn; spec them fresh. |
| **Q-05** | Is the media-library **audio `▶` interactive** (audition the track), or decorative? | Figma draws a filled circular control that reads as a button; the implementation renders an `aria-hidden` span with no behaviour (PME-024). | Decorative — restyle it so it does not look pressable. |
| **Q-06** | With many audio tracks, should the **whole media panel scroll**, or only the asset grid? | Today the grid scrolls and the AUDIO block is `flex: 0 0 auto` (PME-025). | Whole panel scrolls. |
| **Q-07** | The library card thumbnails use a **per-card accent colour** (green / gold / blue / violet). Meaningful (deck kind, colour tag) or decorative variety? | Decides whether PME-050 needs a data field. | Decorative; drop it. |
| **Q-08** | **Is deleting a presentation undoable?** | Figma `553:150` and `PRESENTATIONS-LIBRARY-spec.md` §5 both say yes; the implementation says no and provides no Undo (PME-058). One of the three is wrong. | Make it undoable (slide + element delete already are, `MAX_UNDO = 60`). |
| **Q-09** | Should the **audience output** move from the legacy amber `#F2B53C` to Design 2.0 gold `#F2B84B`? | The chrome runs on `#F2B84B`; the compositor runs on `#F2B53C` (OUT-001). Either is defensible — output palettes need not track chrome — but it should be a decision, not an accident. Four-surface change if yes. | Keep `#F2B53C`; note it in the handoff as deliberate. |
| **Q-10** | Are `208:124`'s mock geometries **normative**, or illustrative? | The mock positions text absolutely; the compositor lays out centred, shrink-to-fit regions. OUT-002/003 and the size deltas hinge on this. | Illustrative — the region model wins; redraw the mocks from a real render. |
| **Q-11** | **Which five colours** are the background presets in `393:130-135`? | Unlabelled in the frame; nothing in `theme.rs` (OUT-010). | Derive from `tokens::design2` (base / inset / accent-soft / gold-soft / preview-soft). |
| **Q-12** | Do gradient backgrounds need **free angles**, or are the four enum directions enough? | `390:172` shows `180° · Vertical`; `208:126` uses **150.59°**, which the enum cannot express (OUT-003, OUT-011). | Four directions are enough; redraw `208:126` at a supported angle. |
| **Q-13** | Keep the always-visible **keyboard-hint strip** above the canvas (`#pm-canvas-hint`)? | It is EXTRA (PME-018) and eats canvas height the frame gives to the slide. It is also a genuine discoverability aid. | Keep, but collapse it behind a `?` toggle. |
| **Q-14** | Is **"Add to plan"** permanently dropped from the editor topbar? | `PRESENTATIONS-LIBRARY-spec.md` §2 records the replacement, but `PRESENTATION-MEDIA-STATES-spec.md` §1 still draws it and so does `329:124` (PME-015). | Permanently dropped; correct both frames and the spec diagram. |

---

# Suggested build order

Sequenced so each step is independently shippable and the highest-severity items land first.
**No implementation file was modified by this audit.**

## Web (Part A)

**Step 1 — safety and access (S1).** Nothing here needs a design decision.

1. **PME-001** — `.pm-slide-live-badge`: white on `--sc-live` at 9 px bold is 3.27:1. Change the ink
   to `--sc-live-soft #2A1416` (5.31:1). One CSS line, `app.css:4671`. This is the highest-value
   single change in the audit.
2. **PME-014 + PME-055** — a real **`▶ Present`** control. Today presenting is command-palette-only
   (`app.js:5000`), which means an operator who does not know ⌘K cannot present at all. Add the
   button to `pm-topbar` and the `Present` item to the card `⋯` menu. Use **flat `--sc-primary`**,
   never the gradient the frame draws (PME-003).
3. **PME-043 (view-only)** — there is no permission-gated mode on this surface. Decide whether the
   Presentation surface needs one before building it; if yes, it is edit tools hidden **and out of
   tab order**, plus a "View only" text chip.
4. **PME-059** — warn on delete when a **service plan references the deck**. A plan silently losing
   its deck is a Sunday-morning failure.
5. **PME-058 / Q-08** — resolve the undo contradiction, then make copy and behaviour agree.
6. **PME-053** — the `Start from` radio group in the New-Presentation dialog.

**Step 2 — accessibility policy (S2), after Q-02.**

7. **PME-005** — `.pm-btn-primary:hover` → `#5a48d0`, mirroring the existing fix at `app.css:4505-4507`.
8. **PME-006…PME-011** — promote to `--sc-text-secondary`. These sit squarely inside the project's
   own written rule (`app.css:4476-4478`), so this applies policy rather than setting it.
9. **PME-027** — the two horizontal-align buttons currently share the glyph `≡`; left and right are
   indistinguishable. Use `≡ ≣ ≡` → distinct glyphs, or icons.

**Step 3 — missing states (S2).** Work the state-coverage matrix top-down.

10. **PME-041** (Importing), **PME-040** (visible "unused" tag), **PME-039/PME-021** (Missing tile:
    dashed border, "Missing" caption, relink from the cell), **PME-042** (hover lift + "+ add" +
    selected corner check).
11. **PME-036 / PME-037 / PME-038** — the three empty states: empty deck (editor rail), empty slide
    (canvas placeholder), and splitting "no media yet" from "no results for ‹q›" with a `+ Import` CTA.
12. **PME-043 (loading)** — a rail skeleton to match the canvas and library-grid shimmers.

**Step 4 — library parity (S2).**

13. **PME-046** (a `Recent` sort — needs an edited-at field), **PME-051** (card meta shows the edited
    time; also feeds the accessible name), **PME-049** (thumbnail 1.89:1 + a deck-like skeleton
    preview), **PME-047** (Grid/List toggle), **PME-063** (the New tile height, 232 → 292).
14. **PME-056** (Export deck `.json`), **PME-057** (menu glyphs), **PME-060** (Clear search).

**Step 5 — inspector and editor detail (S2–S3).**

15. **PME-032** (real image thumbnail + the `JPG · 2.4 MB · 1920×1080` metadata line),
    **PME-033** (the `R` shortcut and its label), **PME-028/PME-030** (hex readout + entry on colour
    controls), **PME-035** (the on-canvas z-badge).
16. **PME-020** (media type filter as a real segmented control), **PME-023** (audio row: inset fill,
    r9, a play disc, the format sub-line), **PME-061** (media slides show a picture in the rail, not
    text), **PME-062** (opacity reads 0–255 where the design says a percentage).

**Step 6 — cosmetics (S3–S4).** PME-013, PME-017, PME-026, PME-031, PME-044, PME-045, PME-048,
PME-052, PME-054, and the sub-pixel padding/size rows.

## Rust (Part B)

**Read this before touching `compose.rs`.** `autofit_layers` is memoized through
`selahcue-present/src/measure.rs`. The **memo key** is `Key { text, cell, font, weight }`
(`measure.rs:22-27`) with a hand-written `Hash` (`measure.rs:29-36`). If any change below introduces
**a new attribute that affects shaping inside `measure_line_width`** — a shaping mode, font
stretch/width, tracking applied *during* shaping, small-caps, a variable-font axis — it **must** be
added to **both** the `Key` struct and that hand-written `Hash`. Miss either and the cache returns a
width measured under the old attribute: lines wrap wrong, `Fit::ShrinkToFit` picks the wrong cell,
and nothing fails — the hit looks like a success. `letter_spacing_permille` is deliberately *outside*
the key and added as a per-glyph multiply afterwards (`compose.rs:84`, `103-106`); keep it that way
unless tracking moves into shaping, in which case the key must change with it. See **OUT-013**.

**Step 1 — decisions first.** Q-09 (output amber), Q-10 (are the mocks normative), Q-12 (free
gradient angles). Each changes what "parity" even means for `208:124`. **Do not start Step 2 until
Q-10 is answered** — every geometry row in that frame depends on it.

**Step 2 — the model gap that has a legal edge.**

1. **OUT-006 / OUT-015** — a **CCLI / attribution region**. `Theme` has no footer region and `Slide`
   has no song metadata, so `208:130`'s `CCLI #7115744 · Sinach` cannot be rendered at all. Design
   this into the model (a `footer: Option<RegionStyle>` on `Theme` plus song metadata on the content
   side), not as a static `Element::Text`. Keep it additive with `skip_serializing_if` so pinned
   theme fixtures stay byte-stable — the pattern `band`, `font` and `letter_spacing_permille`
   already follow (`theme.rs:392-416`).

**Step 3 — per-role templates (S2), after Q-10.**

2. **OUT-009** — `BUILTIN_NAMES` is `["classic", "high-contrast", "lower-third"]`: two style variants
   plus one output role, where the frame designs **content-role** templates. `Theme`'s own doc
   already scopes this as S8-3d (`theme.rs:380-381`). Build `Scripture — Full` and `Song — Center` as
   real templates; keep `high-contrast` (an NFR-020 affordance the board simply does not draw).
3. **OUT-002 / OUT-003 / OUT-016 / OUT-017** — give `Scripture — Full` its gradient and reconcile its reference/body geometry. If Q-12 says the four-direction enum
   stands, redraw `208:126` at a supported direction rather than widening the enum.
4. **OUT-004** — song leading: the frame implies **1417 ‰**, `classic()` uses 1150 ‰ (`theme.rs:472`).

**Step 4 — lower-third refinement (S2).** The one template built against its frame, so these are
small, well-defined corrections.

5. **OUT-008** — the reference line renders at `size_permille: 40` (`theme.rs:538-551`) where the
   frame draws **65 ‰**; the reference currently reads much smaller than the body instead of matching it.
6. **OUT-007** — band fill: `rgba(0,0,0,150)` (59 % pure black) vs the frame's `#05080D` at 90 %.
7. Band height: 300 ‰ vs the frame's 258 ‰.

**Step 5 — background model (S3).** **OUT-010** (the five presets, after Q-11), **OUT-011** (the
angle control's contract, after Q-12).

**Step 6 — the GPU path (S2, scoped).** **OUT-012** — `selahcue-gpu` renders `Layer::Fill` only and
silently skips `Text`, `Image` and `Shape`, with no `Gradient` arm at all
(`compositor.rs:6-12`, `160`). The SSIM ≥ 0.99 oracle therefore proves parity over fill-rect frames
only (`test_parity.rs:92-106`). This is ADR-0002's future path, not a live regression — the shell
CPU-composites today. But nothing should move the on-screen surface onto this compositor until glyph,
image, shape and gradient rendering land, and the parity oracle is extended to cover them.

## Verification note

No `make ci` run is needed for this audit — it changed no code. **A full `make ci` will be needed
before landing any step above**, and it must be run **one at a time in this checkout** (concurrent
Flutter runs produce false reds, `CLAUDE.md` §Conventions). Steps that touch `dist/` must also keep
`scripts/operator_headless.py` green — it asserts computed opacity and real client rects specifically
to stop the deliberate a11y fixes from regressing.

---

# Pending ClickUp update

`clickup_search` for "Design 2.0 parity presentation media" returned **0 results** — no task exists
for this audit. Per the operating contract, no shadow backlog was created. The structured update to
apply when a task is opened:

- **Link** this document and `docs/delivery/goals/TASK-design2-parity-audit-presentation.md`.
- **Figma nodes** to attach: `329:124`, `509:124`, `547:124`, `552:124`, `208:124`, `390:124`.
- **Blocking decisions** for the `/build` gate: **Q-08** (deck-delete reversibility), **Q-10**
  (are the `208:124` mocks normative), **Q-02** (muted-token policy). Every other question has a
  workable default recorded above.
- **Suggested child stories:** one per build-order step — six web, six Rust.
- **Related epics:** Presentation & Slides (`86ajp07ce`), Service Planning & Library (`86ajp072p`).

---

## Owner decisions (2026-08-23)

| Question | Decision | Consequence |
|---|---|---|
| **Q-14** — is "Add to plan" permanently dropped? | **No — reinstated.** | `PRESENTATIONS-LIBRARY-spec.md` §2.1 added; `PME-015` closes as BUILT, not `MISSING (documented intent)`. The regression guard in `selahcue-present/tests/test_tokens.rs` must be widened (see below). |
| **Q-08** — is deleting a presentation undoable? | **Build the undo.** | Design and spec were right; the implementation's hard delete is the gap. Consistent with slide/element deletes (`MAX_UNDO = 60`). |
| **Q-09 / OUT-001** — audience output palette | **Pending a render comparison.** | The owner approved a Design 2.0 re-skin, then scoped a later instruction to leave the audience output alone. Two 1920×1080 renders (legacy amber `#F2B53C` vs `d2::GOLD #F2B84B`) were commissioned before the decision is confirmed. **Nothing changes on the congregation-facing output until then.** |
| Audience output **fit** behaviour | **Unchanged — owner-locked.** | `theme.rs`'s `Fit::ShrinkToFit` default stays. The elastic-band / grow-to-fit work is **confidence-monitor only**; any new fit mode must be opt-in and leave every audience caller byte-for-byte identical. |

### The Q-14 guard is too narrow — action required

`test_tokens.rs` asserts `!html.contains("id=\"pm-addplan\"")` to keep the **dead stub** out. The
reinstated control uses `pm-addtoplan`, so the guard passes — but only by a one-character
distinction between a banned dead stub and a required live control. That is not a difference a
future reader will reliably preserve.

Widen it to assert **both** halves:
1. the dead stub `id="pm-addplan"` is still absent, **and**
2. the functional control `id="pm-addtoplan"` is present **and wired** (`function pmAddToPlan`,
   and its `onclick` assignment) — so removing the feature fails the test rather than silently
   satisfying it.

Without (2) the guard cannot tell "correctly reinstated" from "deleted again".

---

## Reconciliation — 2026-09-20

**Author:** Uma (UI/UX). **Scope:** re-verify all 80 findings (`PME-001`…`PME-063`,
`OUT-001`…`OUT-017`) against `main` as of this worktree's base commit (`4b21c39`), docs-only.

### Method

`docs/delivery/CODE-REVIEW-batch-desktop-design2-web1.md` (commit `7c149ea`, 2026-08-23) is the
**only** remediation batch that names any `PME-###` finding. `git log --since=2026-08-23` for
`selahcue-present/src/{theme.rs,compose.rs,measure.rs,slide.rs}` — the four files every `OUT-###`
finding cites — returns **zero commits**; Part B (audience output) is byte-identical to the audit
date and every `OUT-###` verdict stands unchanged. For Part A (web), any `PME-###` not named in the
web1 batch's explicit "§7 Scope kept" list or its "§8 Findings raised, not fixed" table was
re-checked with a direct `grep`/`Read` against the current `dist/` tree rather than assumed unchanged,
because the web1 batch also touched adjacent CSS (`.seg` rename, the `--sc-*` review block) that could
plausibly have side-effected a Presentation-surface rule; none did.

### FIXED

| Finding | Evidence |
|---|---|
| `PME-001` | LIVE badge now uses the canonical white-text red fill (7.19:1), not `--sc-live` as a fill (3.27:1). `CODE-REVIEW-batch-desktop-design2-web1.md` §3, gate-verified (`operator_headless.py` PME-001 checks, all PASS). |
| `PME-005` | `.pm-btn-primary:hover` darkens to `#5a48d0` (6.42:1) instead of lightening to `--sc-primary-hover` (3.78:1). Same batch, §4. |
| `PME-014` | `#pm-present` — a real `▶ Present` control in the Presentation topbar, reachable without ⌘K, dispatching `pmGridGoLive`/`pmPresent` per surface mode. Same batch, §5. |
| `PME-015` | `#pm-addtoplan` — a real, wired `Add to plan` control with rollback-on-failure and Undo, resolving the audit's own Q-14 in favour of keeping the control (owner-confirmed per the batch doc's §5 citation of `PRESENTATIONS-LIBRARY-spec.md` §2.1). |

**4 findings FIXED**, all in Part A, all S1.

### Explicitly raised but NOT fixed (batch doc's own admission)

- **`PME-055`** — no `Present` item in the library card `⋯` menu. Web1 batch §8: *"The audit pairs it
  with PME-014; scope was the topbar only. Presenting is now reachable without ⌘K, so the S1 is
  closed, but the menu item is still missing."* Confirmed **OPEN** — `grep -n "Present" app.js` around
  the card menu (`app.js:6766-6775` per the batch doc's own citation) shows no such item as of this
  worktree.

### Re-verified still OPEN (the other named S1s)

- **`PME-043`** (no view-only/permission-gated mode on the Presentation surface) — the only "View
  only" markup in `dist/` is explicitly scoped to the Service Plan surface (`index.html:1063`,
  comment: *"frame 612:342"*, a Plan node, not Presentation's `509:124`). **OPEN**, unchanged.
- **`PME-053`** (no `Start from` radio group in the New-Presentation dialog) — the only "Start from a
  template" strings in `app.js` (`app.js:7873`, `app.js:8229`) sit in the Service Plan empty-state /
  plan-lifecycle code (matching `CON-173`'s Q11), not the Presentations-library New dialog. **OPEN**,
  unchanged.
- **`PME-058`** (delete-undo copy/behaviour contradiction, Q-08) and **`PME-059`** (no warning when a
  service plan references the deck being deleted) — `app.js` does carry a general presentation-delete
  Undo (`app.js:8831`, `app.js:9151`), but neither carries the specific plan-reference warning
  `PME-059` asks for, and Q-08's copy/behaviour reconciliation is not recorded as decided anywhere in
  `docs/delivery/` or `docs/design/`. **Both OPEN.**

All remaining `PME-###` (54 more) and every `OUT-###` (17) are **OPEN, unchanged since 2026-08-23** —
Part B by the zero-commit check above; the remaining Part A items because they sit outside web1's
five named fixes and its own scope-kept list, and none surfaced in the direct re-check pass either.

### Totals

| | Count |
|---|---:|
| Total findings | 80 (63 `PME-` + 17 `OUT-`) |
| FIXED | 4 |
| SUPERSEDED | 0 |
| **OPEN** | **76** |

Open, by severity (from the audit's own summary tables, reduced only by the 4 confirmed FIXED — all
4 were S1):

| Severity | Originally | Open |
|---|---:|---:|
| S1 | 6 (Part A) + 1 (Part B, `OUT-006`) = 7 | 3 (`PME-043, PME-053/PME-058/PME-059` — Part A) + 1 (`OUT-006`) |
| S2 | 27 (A) + 7 (B) = 34 | 34 (unchanged) |
| S3 | 21 (A) + 5 (B) = 26 | 26 (unchanged) |
| S4 | 31 (A) + 5 (B) = 36 | 36 (unchanged) |

(The S1 row: `PME-055` is a **duplicate id-pairing** with `PME-014` in the audit's own "six S1s"
grouping, not a distinct seventh severity slot — so of the six Part-A S1 slots, two (`PME-001`,
`PME-014`) are closed and four (`PME-043`, `PME-053`, `PME-058`, `PME-059`) plus the paired
`PME-055` remain open.)

Three blocking decisions (Q-02, Q-08, Q-10) named in the original audit remain unanswered and still
gate the bulk of Part A step 2+ and all of Part B step 3+ of the suggested build order.
