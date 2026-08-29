# Attention badges on plan rows and slide thumbnails — Design Spec (UI-A2)

**Status:** design · **Owner:** /ui-ux-designer (Uma) · **ClickUp:** [`86ak7kgnm`](https://app.clickup.com/t/86ak7kgnm) (sequence #5)
**Requirement:** FR-204 — attention badges on plan rows and slide thumbnails (missing media, unassigned output, over-long text). MVP.
**Evidence grade: SCREENSHOT-DERIVED in part.** The reference's countdown/warning thumbnail badges are **vendor-undocumented — seen only in the owner's screenshots**. The *idea* of surfacing item-level warnings is sound and matches SelahCue's own pre-service check; **the specific badge roster is not a spec.** This spec therefore derives the roster from SelahCue's own detection model (master FR-007, which already ships) and treats the screenshot as intent.
**Sources:** PRD §14 EPIC-UI-A + "Designer detail — FR-204" · master FR-007 (missing-media detection), FR-084 (cancellable background work) · shipped `dist/app.js:6193-6214` (`planLinkChip`, the existing `⚠ presentation missing` chip), `dist/preservice.js:114-117` (the existing remediation surface).
**Figma:** built — [Section: SelahCue · Operator UI MVP — EPIC-UI-A/B/C/D (RISK-205 Figma catch-up)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-124).
Frames: [UI-A2 · 01 — The roster, and where a badge sits](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=986-127) · [UI-A2 · 02 — Badge state matrix, including the scanning state](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=986-225).
In context: [IN CONTEXT · 03 — console with UI-A1 + UI-A2](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=979-124) (plan rows) and [IN CONTEXT · 02 — console with UI-B1](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=978-139) (slide cards).
Also: [legend + open questions](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-125). The frames are drawn from this spec and the shipped `--sc-*` token values, not copied from the existing Design 2.0 frames (RISK-205: those lag the console on contrast). Chips read **PREVIEW / LIVE** pending Priya's ruling (F3). Colours bind to `sc/*` variables added to the file's `SelahCue Color` collection at their shipped values; the six structure-palette trios are present and marked **PROPOSED**.

---

## 1. The rule that decides everything else

**A badge is a live read of a check, never a latched event.**

The badge renders the *current* result of running a detection. It is not a record that something once went wrong. Everything in this spec follows from that, and it is the direct answer to the risk the ticket raises:

> `86ak507hh` — output-fault reporting is incomplete: a held fault never self-clears and `DecoderFault` is unreachable. **If a fault never self-clears, a badge will never clear either.**

If the badge is a computed read, a condition that goes away removes the badge on the next computation, and the broken-latch problem never reaches the operator. If the badge subscribes to fault *events*, it inherits the bug. So:

1. **Badges are computed, not received.** Each is the output of a check that can be re-run and can return "clear".
2. **A badge type that cannot be recomputed is not shipped.** An indicator that can only ever turn on is worse than no indicator: operators learn within two services to ignore it, and then it is dead weight on the surface where they most need to trust what they see. §7-F1.
3. **Every badge has an operator-driven re-check path**, so even a slow or stuck check has a way out that does not require a restart.

---

## 2. The roster

Two classes, and they must not be confused: one asks for action, the other is context.

### 2.1 ⚠ Attention (amber) — something will be wrong if this goes live

| Issue | Detection | Status |
|---|---|---|
| **Missing media** | master FR-007 missing-media detection | **ships** — surfaced today only as a pre-service count (`preservice.js:114`) |
| **Missing presentation** | the linked deck id is not in the library | **ships** — surfaced today as the `⚠ presentation missing` chip on the plan row (`app.js:6203`). Folded into this system rather than left as a second mechanism. |
| **Unassigned output** | the item targets a screen role with no enabled screen | needs the screen registry read — available (`86ajujr0y` complete) |
| **Over-long text** | the theme's ShrinkToFit hit its floor: the text will render below the legibility minimum or clip | **detection not verified to exist** — §7-F2 |

### 2.2 ⏱ Note (info) — context, not a problem

| Note | Source |
|---|---|
| **Auto-advance** | the item's auto-advance setting (`#pm-autoadv`, ships) |
| **Timer attached** | a countdown/timer associated with the item |

A Note is never amber and never uses the warning glyph. Colouring "this song auto-advances" as a warning trains operators to ignore amber, which is the thing FR-204 exists to make them notice.

---

## 3. Appearance

### 3.1 On a plan row

A leading badge, immediately before the item title, inside the existing `.item .main`:

| | Attention | Note |
|---|---|---|
| Glyph | `⚠` | `⏱` |
| Ink | `--sc-warn` `#F5A524` | `--sc-info` `#38BDF8` |
| Background | `--sc-warn-soft` `#2A2415` | `--sc-info-soft` `#10222B` |
| Border | `--sc-warn-border` `#4A3A15` | `--sc-info-border` `#1C3A4A` |
| Contrast | **7.56:1** | AA (Design 2.0 §6) |
| Size | 18×18, radius 6 | same |

**Amber pairs with a shape, never colour alone** — the `⚠` glyph is part of the badge, not decoration, and it is the channel that survives a monochrome render or a red-green colour deficiency.

**Multiple issues on one item** collapse to **one** badge with a count: `⚠ 3`. The count is text. Opening it lists all three. Three stacked badges on a 34px row is unreadable and the row is not where triage happens.

### 3.2 On a slide thumbnail

Top-right of the card. This forces a small piece of card re-planning, because FR-210's group band now owns the bottom edge:

| Position | Occupant | Change |
|---|---|---|
| top-left | slide number | unchanged (`.slide-card-n`) |
| **top-right** | `[badge] [PREVIEW/LIVE chip]`, right-aligned | **the status chip moves here from bottom-right** |
| bottom edge | group colour band / footer strip | new, from FR-210 |

The status chip's move is a consequence of `SONG-GROUPS-HOTKEYS-spec.md` §2.1 taking the bottom edge, not a preference. Recorded here so the two tickets do not each assume they own that space.

### 3.3 In List view

The badge sits in its own fixed-width column, after the state chip and before the slide number, so rows never reflow as badges arrive (§5).

---

## 4. Opening remediation — reuse, do not build

**The ticket is explicit: do not build a new remediation surface.** Badge activation routes to what already exists:

| Issue | Opens |
|---|---|
| Missing media | the **pre-service check** (`preservice.js`), scrolled and focused to this item's row |
| Missing presentation | the existing **link modal** (`openLinkModal`, `app.js:6219`) for that plan item |
| Unassigned output | the **Screens & Outputs** page (`NAV-IA-spec.md` §3) |
| Over-long text | the **deck/song editor** for that slide |
| Multiple | the **pre-service check**, filtered to this item |

Opening remediation is authoring, not a live action: **it must not touch the live output** (CON-U2). Nothing in this path stages, commits, clears or blacks out.

### 4.1 A badge is only interactive where it is allowed to be

Slide cards are `role="option"` inside a `role="listbox"` (`app.js:4909`, `:7500`). **Interactive descendants of an option are not exposed to assistive technology**, so a `<button>` inside a slide card is a button that a screen-reader user cannot reach — an accessibility trap that looks fine in a mouse test.

Therefore:

- **On a plan row:** the badge is a real `<button>`, with `stopPropagation` so it does not also select the row, revealed the same way the shipped `.tools` are (opacity, never `display:none`, so it keeps its tab order — `app.css:3369`).
- **On a slide card:** the badge is a **non-interactive indicator**. The problem is instead stated in the option's accessible name (§6), and remediation is reached from the plan row, or from the pre-service check (`⌘⇧K`, already bound), which lists everything.

This satisfies both acceptance criteria — *"the badge opens the remediation prompt"* on the row, and *"badge state also appears on the item's slide thumbnails"* as an indicator — without building an unreachable control.

---

## 5. The scanning state — the thing the ticket does not name but needs

Badge computation is background and cancellable (master FR-084): **a slow media scan must never delay plan rendering.** That creates a problem the ticket does not address:

> While the scan is in flight, "no badge" is ambiguous. It means either *"this item is fine"* or *"nobody has looked yet"* — and those are very different things to know ten minutes before a service.

So:

- **The badge slot is reserved** at fixed width from first paint, in both rows and cards. Rows never reflow when badges land, and the grid never re-lays out mid-scan.
- **The plan header shows a quiet `Checking items…`** while any scan is in flight — small, in `--sc-text-secondary`, non-blocking, and never a spinner over the plan.
- **When the scan completes it disappears.** Absence of the indicator plus absence of a badge then unambiguously means "checked, and fine".
- **Cancellation:** switching plan, closing the plan or quitting cancels in-flight scans. A cancelled scan leaves `Checking items…` **off** and the plan header reading `Not checked` rather than implying a clean result it never obtained.

---

## 6. States

| State | Trigger | Treatment |
|---|---|---|
| **checking** | scan in flight | reserved empty slot + `Checking items…` in the plan header |
| **warning** | a check returned a problem | `⚠` badge; accessible name states the problem and the file |
| **note** | auto-advance / timer configured | `⏱` badge |
| **multiple** | ≥2 issues | one `⚠ n` badge; details on open |
| **resolved** | the next computation returns clear | the badge **disappears**. No success flash, no green tick — the absence is the message, and a green anything here would collide with staged/safe (CON-U4). |
| **not checked** | scan cancelled or never run | plan header reads `Not checked`; no badges. Never rendered as "clean". |
| **check failed** | the check itself errored | `⚠` badge whose accessible name is *"Could not check this item"*, opening the pre-service check. An unrunnable check is itself a warning — it is never silently treated as a pass. |

---

## 7. Findings

**F1 — a badge type that cannot recompute must not ship.** §1. Directly aimed at `86ak507hh`: if output-fault state is latched and cannot clear, an output-fault badge would be permanently on for some operators, and the whole badge system loses credibility with it. The design position is to gate the badge on the detection being re-runnable, not to add a manual dismiss — a dismissible warning is a warning nobody reads.

**F2 — "over-long text" has no verified detection.** Missing media (master FR-007) ships. Missing presentation ships. Unassigned output can be read from the screen registry. **Over-long text is in the FR's requirement text but I could not confirm a detection exists for it**, and the honest definition — the theme's ShrinkToFit reached its floor — is an engine-side signal, not something the console can compute. Options: (a) descope it from MVP and ship three attention types; (b) raise an engine ticket for a ShrinkToFit-floor signal. The badge is specified either way, so it costs nothing to land later. @Priya / @Diego — this affects the ticket's scope, not just its build.

**F3 — the PREVIEW/LIVE chip must move from bottom-right to top-right of a slide card.** FR-210's group band takes the bottom edge. Two tickets both need that space; neither says so. §3.2.

**F4 — the existing `⚠ presentation missing` chip must be folded in, not left alongside.** `app.js:6203` already renders one warning treatment on plan rows. If FR-204 adds a second badge system next to it, a plan row with a missing deck will show two different warning affordances for one problem. Fold it into the roster (§2.1) as part of this work.

---

## 8. Accessibility

- **Accessible names are specific, and name the thing.** *"Missing media: backdrop.jpg"*, not "warning". *"3 problems: missing media, unassigned output, and 1 more"* for the collapsed badge. *"Auto-advance after 5 seconds"* for a note.
- **Amber always pairs with the `⚠` shape**, never colour alone (WCAG 1.4.1). Info always pairs with `⏱`.
- **The plan row badge** is a `<button>` with an `aria-describedby` naming what activating it will open — *"Opens the pre-service check"* — so activating is not a leap of faith.
- **Slide-card badges are indicators**, and their content appears in the option's accessible name: *"Slide 4, Chorus, missing media: backdrop.jpg"* (§4.1).
- **Badges appearing mid-scan announce politely, once, coalesced:** *"3 items need attention"* when the scan settles — not one announcement per badge as it lands.
- **Resolution announces too:** *"Missing media resolved for Good Grace"*. A silent disappearance is invisible to a screen-reader user, who has no peripheral vision of the list.
- **Contrast:** `--sc-warn` on `--sc-warn-soft` is 7.56:1; `--sc-info` on `--sc-info-soft` is AA (Design 2.0 §6). **No new ink** — GO LIVE 8.70:1, BLACKOUT 7.19:1 and primary 4.72:1 are untouched (CON-U7). `--sc-text-muted` is not used.
- **Reduced motion:** badges appear and disappear without animation. There is no attention-seeking pulse — a service-long amber pulse is an accessibility problem and an irritation.

---

## 9. Constraints check

| Constraint | How it is met |
|---|---|
| **CON-U2** staging never changes Live | Badges are advisory. Every remediation route is authoring or navigation; none stages, commits, clears or blacks out. |
| **CON-U4** one meaning per colour | amber = warning, info-blue = context. No green (would read as staged/safe), no red (would read as live). Resolution is an absence, not a green tick. |
| **CON-U7** no ink regression | Existing warn and info token trios only. Nothing new. |
| **CON-U1** WebView is the console only | A badge is an indicator; nothing renders audience output. |
| **CON-U3** offline | All four checks are local. Missing-media detection is a filesystem read; the screen registry is local. |
| **CON-U6** four roles, not seven | Badges are visible to every role. Remediation follows the permission of the surface it opens — the badge grants nothing. Mobile shows badges **read-only**. |

---

## 10. Handoff and QA

**Related:** `86ajp0az9` (missing-media detection + pre-service check, complete) — the detection this surfaces and the UI it opens. `86ajy0hw0` (Service Plan wire + missing flag, in progress) — supplies the per-item flag; design does not wait on it, implementation should follow it. `86ak507hh` (faults never self-clear) — §1 and F1.

**Sequencing:** F3 means this ticket and UI-C1 both touch slide-card layout. Whichever lands second must not undo the other's placement; the card plan in §3.2 is the shared reference.

**QA steps** are posted in list form on the ticket.
