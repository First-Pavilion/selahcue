# Plan section groups + duration roll-ups — Design Spec (UI-A1)

**Status:** design · **Owner:** /ui-ux-designer (Uma) · **ClickUp:** [`86ak7kgmk`](https://app.clickup.com/t/86ak7kgmk) (sequence #2)
**Requirements:** FR-201 (coloured, collapsible section headers), FR-202 (per-item duration, per-section subtotal, plan total) · master FR-002/FR-004/FR-074
**Evidence grade:** CITED (E09 — reference playlists carry Headers / Placeholders / Presentations). The key adaptation is that **a section is an inert label and never fires anything** (research §7.5) — SelahCue deliberately takes the inert side against Proclaim's time-driven model.
**Sources:** PRD §14 EPIC-UI-A + "Designer detail — FR-201/202" · `DESIGN-2.0-HANDOFF.md` §3.1/§4 · shipped console `dist/index.html:92-100`, `dist/app.css:3279-3430`, `dist/app.js:64-110`.
**Figma:** built — [Section: SelahCue · Operator UI MVP — EPIC-UI-A/B/C/D (RISK-205 Figma catch-up)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-124).
Frames: [UI-A1 · 01 — Section state matrix](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=983-127) · [UI-A1 · 02 — Structure palette, gear menu, colour submenu, delete confirm](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=983-318).
In context, at real scale in the shipped 380px plan column: [IN CONTEXT · 03 — console with UI-A1 + UI-A2](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=979-124) (with [IN CONTEXT · 01 — console today (baseline)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=977-124) as the baseline).
Also: [legend + open questions](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-125). The frames are drawn from this spec and the shipped `--sc-*` token values, not copied from the existing Design 2.0 frames (RISK-205: those lag the console on contrast). Chips read **PREVIEW / LIVE** pending Priya's ruling (F3). Colours bind to `sc/*` variables added to the file's `SelahCue Color` collection at their shipped values; the six structure-palette trios are present and marked **PROPOSED**.

---

## 1. The model this rests on, and why it makes the hard parts easy

`plan_item` already has a `kind` of `section`, and the console already renders it — **as an ordinary row with a `SECTION` kind badge** (`app.css:3354`). So the data exists and nothing new is stored. What changes is that a section stops being a row and becomes a **header that owns the items following it**.

**Grouping is derived from position, not from a parent pointer.** A section header owns every item after it until the next section header or the end of the plan. Items before the first header are *ungrouped* and render exactly as they do today.

Three of this ticket's hardest requirements fall out of that for free, and the spec relies on it:

- **"Deleting a section never deletes items"** — deleting the header removes one flat-list entry. The items after it are untouched; they simply become owned by the *preceding* header, or ungrouped if there was none. No cascade, no orphan handling, no confirmation dialog needed beyond naming the outcome (§7).
- **"Items reorder within and across sections by drag"** — every drag is a reorder in one flat list. "Across sections" is not a special case.
- **"A plan with no sections renders exactly as today"** — a plan with no `section` items produces no headers, so the render path is the current one.

---

## 2. Layout

The plan stays in the console left zone (`#plan-wrap`). **No new surface.**

```
┌─ Service plan ─────────────── 32 items · 1:12:40 ──┐   ← plan header: count + TOTAL
│                                                     │
│  Welcome slide                          2:00        │   ← ungrouped item (before any header)
│                                                     │
│ ▼ ▎PRE-SERVICE            3 items · 8:00      ⚙    │   ← section header
│     Countdown                          5:00        │
│     Announcements                      3:00        │
│     Welcome                               —        │
│                                                     │
│ ▶ ▎WORSHIP           6 items · 24:30 · partial ⚙   │   ← collapsed
│     ● LIVE  Good Grace                             │   ← live stub — never hidden
│     ◆ PREVIEW  Great Are You Lord                  │   ← staged stub
│                                                     │
│ ▼ ▎SERMON                 2 items · 35:00     ⚙    │
│     …                                               │
└─────────────────────────────────────────────────────┘
```

### 2.1 Section header

A full-width bar, 34px tall, radius 11, sitting flush in the `#plan` column with the existing 8px gap above and **4px below** (tighter than the inter-item gap, so the header reads as attached to its group rather than floating between two).

Left to right:

| Part | Detail |
|---|---|
| **Chevron** | `▼` expanded / `▶` collapsed. A real `<button>` with `aria-expanded`, 24×24, the only click target that collapses. |
| **Colour rule** | A 3px full-height bar at the left edge in the section's ink (§3). This is the colour cue. |
| **Name** | Uppercase, 11px, 700, letter-spacing `.06em`, in the section's ink. Ellipsized; full name in `title` **and** in the group's accessible name. |
| **Counts** | `3 items · 8:00` in `--sc-text-secondary`, right-aligned before the gear. `· partial` appended when any child duration is unset (§4). |
| **Gear `⚙`** | 24×24 ghost button, appears on hover and on `:focus-within` (the shipped `.tools` pattern, `app.css:3369` — opacity, never `display:none`, so it keeps its tab order). Opens the section menu (§7). |

The header background is the section's **soft tint**, with a 1px border in the section's **border** token. It is deliberately *quieter* than a plan item card: the items are what you act on, the header is scaffolding.

### 2.2 Item rows

Unchanged from today (`.item`, `--sc-elevated`, radius 11) except:

- **Indent 12px** when inside a section, so the grouping is legible without a containing box.
- **Duration**, right-aligned, `--sc-text-secondary`, tabular figures, before the existing `.tools`.

Everything else — kind badge, link chip, live/staged tint, hover tools — is untouched. **The `is-live` and `is-staged` card tints keep their shipped ink exactly** (CON-U7).

### 2.3 Plan header

`#plan-sub` gains the plan total next to the item count: `32 items · 1:12:40`, with `· partial` when any item anywhere in the plan has no duration.

---

## 3. The structure palette (shared with FR-210)

Six fixed slots. **Not a colour picker** — the gear offers these six and nothing else, so every plan in every church stays inside an audited set.

**Constraint that shapes the whole palette (CON-U4):** red, green and amber are spoken for by broadcast status, and gold is reserved for scripture (Design 2.0 §2). That leaves the blue → indigo → violet → magenta arc, plus a neutral. Six slots is at the edge of what is comfortably distinguishable in that arc on a dark surface — see §11-F1. This is survivable **only because colour is never load-bearing here**: the section name is always present, in text, at the same size, in every state.

| Slot | Name | Ink | Soft (header bg) | Border | Status |
|---|---|---|---|---|---|
| 1 | **Sky** | `#38BDF8` | `#10222B` | `#1C3A4A` | existing — `--sc-info` / `--sc-info-soft` / `--sc-info-border` |
| 2 | **Blue** | `#60A5FA` | `#111C2E` | `#1E3355` | new token trio |
| 3 | **Indigo** | `#818CF8` | `#191C33` | `#2C3160` | new token trio |
| 4 | **Violet** | `#A78BFA` | `#201F3A` | `#38306B` | soft = existing `--sc-accent-soft` |
| 5 | **Magenta** | `#E879F9` | `#2A1730` | `#4A2955` | new token trio — measured **6.75:1** |
| 6 | **Slate** | `#A7AEBE` | `#1B2029` | `#333A47` | ink = existing `--sc-text-secondary` — measured **7.35:1** |

**Default assignment** for a newly created section: the next unused slot in order, wrapping at 6. Deterministic, so two operators building the same plan get the same colours.

**Token work this implies.** Four new ink/soft/border trios must be added to `selahcue-present/src/tokens.rs` and mirrored on the four pinned surfaces (Rust, `dist/app.css`, `design_tokens.dart`, `StageTheme::dark()`), with `test_tokens.rs` extended to audit every new pairing. This is the coordinated token change DESIGN-2.0-HANDOFF §3.2 warns about — **do not hex-swap blind**, and do not let this ticket land on the webview alone.

**None of these hues is in the live / preview / warn families, and none is gold.** That is the property to assert in review, not "they look different enough".

---

## 4. Durations (FR-202)

### 4.1 Format

| Length | Format | Example |
|---|---|---|
| under 1 hour | `m:ss` | `5:00`, `12:30` |
| 1 hour or more | `h:mm:ss` | `1:12:40` |
| not set | `—` (em dash) | |

Tabular figures, so a column of durations aligns. Never `0:00` for an unset value — zero is a real duration and means "instant", which is not the same as "nobody has said".

### 4.2 Summation

- An unset duration is **excluded** from every sum. It never counts as zero.
- A sum that excluded at least one unset child is marked **`· partial`** — on the section header, and on the plan header if any item anywhere is unset.
- A section with **no** durations set at all shows `— · partial`, not `0:00`.
- A collapsed section still shows its subtotal. Collapsing hides items, never arithmetic.

`· partial` is deliberately a word and not an asterisk or a colour: a coordinator pacing a service needs to know at a glance that the number is a floor, not an estimate, and a glyph does not say that.

### 4.3 Where the number is computed

`86ajy0hw0` (in progress) supplies per-item duration and plan-summary counts. **The `partial` flag must be computed in exactly one place, and it should be the same place as the sum** — otherwise a UI that filters or collapses can disagree with the wire about whether a total is complete. Design's requirement: whatever computes a subtotal also returns whether it is partial. Implementation of FR-202 lands after `86ajy0hw0`; the two must agree on this before either ships.

---

## 5. State matrix

| State | Trigger | Treatment |
|---|---|---|
| **expanded** | default | `▼`, items visible and indented |
| **collapsed** | chevron, `←`, or restored preference | `▶`, items hidden, counts and subtotal still shown, stubs per §6 |
| **empty section** | header with no items before the next header | header + a single muted row *"No items in this section"*, `--sc-text-secondary`, not clickable. Never a bare header with nothing under it — that reads as a rendering bug. |
| **partial durations** | any child unset | `12:30 · partial` |
| **no durations at all** | every child unset | `— · partial` |
| **drag-over, between sections** | dragging an item over a gap | 2px `--sc-primary` insertion line spanning the plan column |
| **drag-over, into a collapsed section** | dragging over a collapsed header | the header highlights and **auto-expands after 600ms hover** so the operator can see where the item lands; dropping on a still-collapsed header appends to the end of that section |
| **drag-over, into an empty section** | dragging over the "no items" row | insertion line inside the section |
| **renaming** | gear → Rename | the header name becomes an inline `<input>` (WKWebView implements neither `prompt()` nor `confirm()` — `app.js:100`, so in-page editing is the only option); `⏎` commits, `Esc` cancels |
| **recolouring** | gear → Colour | a 6-swatch row in the menu, each swatch a `menuitemradio` with a **text name**, not colour alone |
| **recovery** | app restart after a crash | collapse state restored with the plan (master FR-074 autosave) |
| **no sections** | plan has no `section` items | renders exactly as today — no headers, no indent, no grouping |
| **mobile mirror** | any | sections render **read-only** for all roles. 4-role model unchanged (CON-U6); no mobile role edits plan structure. |

---

## 6. Edge cases

**Deleting a section never deletes items.** The menu item reads **"Delete section only"** and its confirm names the outcome: *"Delete the section 'Worship'? Its 6 items stay in the plan."* The items merge into the preceding section, or become ungrouped if this was the first header.

**Collapsing must never hide what is on air.** A collapsed section that contains the live item renders a **live stub** directly under its header: the existing `● LIVE` chip plus the item title, on the shipped `is-live` tint. It is not indented with the hidden items — it belongs to the header.

**Collapsing should not hide what `⏎` will put on air either.** *This is an addition beyond the ticket, offered with its reasoning so Priya can strike it:* the same treatment is applied to the **staged** item. `⏎` Go Live commits whatever is staged; an operator who has collapsed a section and cannot see the staged item is one keypress from a surprise. The ticket's stated principle — "never let plan structure hide what is on air" — applies with equal force to what is one keystroke from being on air. Cost: one more stub row, only when a collapsed section holds the staged item.

**Both stubs at once** — live stub first, then staged. Two rows maximum; a section cannot hold more than one live and one staged item.

**A section header cannot be staged or gone live.** It is an inert label (research §7.5). It is not in the item selection order, `⏎` on a focused header does nothing, and the Next/Previous transport skips it. This is the single most important behavioural property of a section and it should have its own test.

**Dragging a section header** reorders the header **and the run of items it owns**, as one block. Dragging a header into the middle of another section is therefore a split, and the insertion line renders at the section boundary it will produce, never mid-run.

**A section named identically to another** is allowed and needs no disambiguation — the plan is ordered, and coordinators legitimately have two "Worship" blocks.

---

## 7. The gear menu

`role="menu"`, opens below-left of the gear, `Esc` closes and returns focus to the gear.

| Item | Type | Behaviour |
|---|---|---|
| **Rename** | `menuitem` | inline edit (§5) |
| **Colour ▸** | submenu | six `menuitemradio` swatches, each labelled with its name (Sky, Blue, Indigo, Violet, Magenta, Slate) — never colour alone |
| **Collapse all sections** | `menuitem` | convenience; the inverse appears when everything is already collapsed |
| — | separator | |
| **Delete section only** | `menuitem`, danger | confirm dialog naming the outcome (§6) |

The confirm is an in-page `role="alertdialog"` with a focus trap and `Esc` to cancel — the shipped pattern. Not `window.confirm`, which is dead in WKWebView.

---

## 8. Keyboard and focus

The plan gains proper list semantics: each section renders as `<div role="group" aria-labelledby="sec-<id>-name">` containing a `role="heading" aria-level="3"` header and its items.

| Key | Where | Action |
|---|---|---|
| `↑` `↓` | plan | move between rows. **Headers are in the traversal order** (so they can be reached, renamed and collapsed) but are **not** in the *selection* order — moving onto a header does not stage anything |
| `←` | on a header | collapse |
| `→` | on a header | expand |
| `←` | on an item inside a section | move focus to that section's header |
| `→` | on a header, already expanded | move to its first item |
| `↑` `↓` | across a **collapsed** section | skip its hidden items entirely, but **stop on any visible stub** (§6) — the stub is real, focusable content |
| `⏎` | on an item | Go Live, unchanged |
| `⏎` | on a header | nothing (§6) |
| `F2` | on a header | Rename, without opening the gear menu |

Roving `tabindex`: one tab stop for the whole plan list. The gear and chevron are reachable within a row by `Tab` once the row has focus (`:focus-within` reveals them), matching the shipped tools behaviour.

---

## 9. Accessibility

- **Headers are real headings inside real groups.** `role="heading" aria-level="3"` for the name; the enclosing `role="group"` carries `aria-labelledby` pointing at it, so a screen reader announces *"Worship, group, 6 items"* on entry and the plan becomes navigable by heading.
- **Chevron** is a `<button aria-expanded="true|false" aria-controls="<group-id>">` with an accessible name of *"Collapse Worship" / "Expand Worship"* — the section name is in the name, so a list of buttons is not six identical "Collapse".
- **Colour is never the only cue.** The section name is always present as text. The colour swatches in the menu are labelled. The `partial` marker is a word.
- **Duration** rows use `<span aria-label="8 minutes">8:00</span>` — a screen reader reading "eight colon zero zero" is not useful. The plan total announces as *"Total 1 hour 12 minutes 40 seconds, partial"*.
- **Collapse announces** politely: *"Worship collapsed, 6 items hidden"* — and, when a stub is shown, *"Good Grace is live and still shown"*, because the operator needs to know the thing they can still see is deliberate.
- **Contrast.** Section ink on section soft tint is AA for the header name (§3, audit required for the four new trios). All secondary text uses `--sc-text-secondary` (8.13:1 on surface) and **never** `--sc-text-muted` (3.79:1 — the known open item; this spec adds no new site to it).
- **Reduced motion.** Collapse/expand is instant under `prefers-reduced-motion`; otherwise a 150ms height transition. The 600ms drag auto-expand hover delay stays either way — it is a timing affordance, not an animation.

---

## 10. Tokens

Reused as-is: `--sc-elevated`, `--sc-border`, `--sc-border-strong`, `--sc-text`, `--sc-text-secondary`, `--sc-primary` (insertion line, focus ring), `--sc-live-soft`/`--sc-live-border`/`--sc-live` and `--sc-preview-soft`/`--sc-preview-border`/`--sc-preview` (the stubs and row tints, **unchanged**), `--sc-info`/`--sc-info-soft`/`--sc-info-border` (palette slot 1), `--sc-accent-soft` (slot 4 soft).

New: twelve values — four ink/soft/border trios for palette slots 2, 3, 5, 6-border (§3). Coordinated four-surface change with a `test_tokens.rs` audit extension.

---

## 11. Findings

**F1 — six distinguishable section hues is at the edge of the available space.** With red, green, amber and gold all reserved, the palette lives in a blue → magenta arc. Slots 2 and 3 (Blue `#60A5FA`, Indigo `#818CF8`) are the closest pair and will read as similar at a 3px rule in a dark booth. I have kept six because FR-210 asks for six and because **colour is explicitly a scanning aid here, not a carrier of meaning** — the name is always there. If the owner wants six *crisply* distinct hues, something has to give: either the reserved families, or the count. Flagged, not resolved.

**F2 — the ticket's "gear → recolour" implies a colour picker; this spec gives a fixed six.** An arbitrary picker cannot be contrast-audited, cannot be kept out of the status families, and would let a plan ship a section that reads as "live". Fixed six is the safe reading of the requirement, but it is a narrowing and should be confirmed.

**F3 — the staged stub (§6) is an addition beyond the ticket.** Included with its reasoning, easy to remove, flagged so it is a decision rather than a drift.

**F4 — this ticket adds four new token trios.** That is a coordinated four-surface change (DESIGN-2.0-HANDOFF §3.2), not a CSS edit, and it is larger than the ticket's "restyled to Design 2.0 kind-badge language" wording implies. Diego should know before sizing the implementation ticket.

---

## 12. Handoff and QA

**Depends on:** `86ajy0hw0` (Service Plan wire — per-item duration + plan summary) for the FR-202 data. Design does not wait on it; implementation of FR-202 should land after it, and §4.3 is the thing the two must agree on.

**QA steps** are posted in list form on the ticket.
