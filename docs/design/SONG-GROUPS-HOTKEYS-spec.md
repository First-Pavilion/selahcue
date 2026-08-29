# Song group colour-coding + jump-to-section hotkeys — Design Spec (UI-C1)

**Status:** design · **Owner:** /ui-ux-designer (Uma) · **ClickUp:** [`86ak7kgn1`](https://app.clickup.com/t/86ak7kgn1) (sequence #3)
**Requirements:** FR-210 (group colour-coding on slides), FR-211 (single-key jump-to-section that **stages**, never goes live) · master FR-019/FR-024 · METRIC-202, NFR-205
**Evidence grade: MIXED, and it changes what this spec is allowed to lean on.**
 · **FR-210 — CITED** (E03: group tokens colour-matched to the group). Labelled sections are a 6/7 category convention.
 · **FR-211 — INFERRED.** The reference product's hotkey mechanism is documented only in a Pro6-era article (E42); its survival into v21.x is inferred from chips in the owner's screenshot, with **no current vendor documentation**. Section hotkeys are contested in the category (4/7). **This spec therefore builds on master FR-024's own merits and on SelahCue's keymap and song model — not on what the reference may or may not still do.** Proclaim is the analogue used where an analogue helps: keys derived from section labels, displayed on the slide (research §7.4).
**Sources:** PRD §14 EPIC-UI-C + "Designer detail — FR-210/211" · `selahcue-app/src/keymap.rs` (the collision authority, AS-U4) · `PLAN-SECTIONS-DURATIONS-spec.md` §3 (the shared structure palette) · `SLIDE-VIEW-DENSITY-spec.md` (the views these colours must survive).
**Figma:** built — [Section: SelahCue · Operator UI MVP — EPIC-UI-A/B/C/D (RISK-205 Figma catch-up)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-124).
Frames: [UI-C1 · 01 — Group colour on the slide, in every view](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=984-127) · [UI-C1 · 02 — Hotkeys: assignment, chip states, state matrix](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=984-237).
In context, on real slide cards in the shipped console: [IN CONTEXT · 02 — console with UI-B1](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=978-139).
Also: [legend + open questions](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-125). The frames are drawn from this spec and the shipped `--sc-*` token values, not copied from the existing Design 2.0 frames (RISK-205: those lag the console on contrast). Chips read **PREVIEW / LIVE** pending Priya's ruling (F3). Colours bind to `sc/*` variables added to the file's `SelahCue Color` collection at their shipped values; the six structure-palette trios are present and marked **PROPOSED**.

---

## 1. What this adds

A song's slides already know their group (`86ajpzha3`, complete). Today that knowledge is invisible on the grid, and reaching the chorus means scrolling. This spec makes the group **visible** on every slide in every view, and makes it **reachable in one keypress** — where the keypress **stages** and Go Live commits.

---

## 2. Colour on the slide

### 2.1 The band

Every slide card belonging to a song group carries a **3px colour band along its bottom edge**, in the group's ink. It is inside the card's radius, full width, and it sits *under* the PREVIEW/LIVE frame so a status frame is never obscured by a group colour.

- **First slide of a group:** the band grows to a 20px **footer strip** carrying the group **name** (uppercase, 10px, 700, letter-spacing `.04em`, in the group ink on the group soft tint) and, at its right, the **key chip** (§3.4).
- **Continuation slides:** the 3px band only. No name, no chip.

That asymmetry is the whole idea: the eye finds the start of a group, and the run of colour tells it how long the group is without reading anything.

### 2.2 In every view (the FR-210 acceptance criterion)

| View | Treatment |
|---|---|
| **Grid** | as §2.1 |
| **Text** | the same footer strip and band on the text card — the colour is what makes a wall of lyrics scannable, so this is the view where it matters most |
| **List** | a 3px colour rule at the row's leading edge, plus the group **name** in its own column on the first row of each group and blank on continuations |
| **Stacked plan view** (FR-208, R2) | as Grid |
| **Mobile read-only plan view** | the same band and name; mobile is read-only for this (CON-U6), so no chip is shown — a mobile user has no keyboard to press |

**The one-row-per-group option** in the density cluster's `⋯` menu (`SLIDE-VIEW-DENSITY-spec.md` §6) exists because of this feature: turning it on makes each group start a fresh row, which turns the colour bands into a structural outline of the song.

### 2.3 The palette

**Uses the shared structure palette defined once in `PLAN-SECTIONS-DURATIONS-spec.md` §3** — six slots, ink / soft / border, all outside the live-red, preview-green, warn-amber and scripture-gold families (CON-U4). Defining it in one place is deliberate: two palettes for two kinds of structure would double the audit and eventually drift.

Fixed role → slot mapping, **not user-assignable in v1**:

| Group role | Palette slot | Ink |
|---|---|---|
| Verse | 3 Indigo | `#818CF8` |
| Chorus | 1 Sky | `#38BDF8` |
| Bridge | 4 Violet | `#A78BFA` |
| Pre-chorus | 2 Blue | `#60A5FA` |
| Tag | 5 Magenta | `#E879F9` |
| Other / unrecognised | 6 Slate | `#A7AEBE` |

Chorus gets the brightest, most saturated slot because it is the group operators jump to most.

**Every numbered verse shares the Verse slot.** Verse 1, Verse 2 and Verse 3 are all Indigo. They are the same *kind* of thing; distinguishing them is the number's job, and the number is in the name and in the key. Giving each verse its own hue would burn the palette on a distinction nobody scans for.

**Contrast:** each ink is used on its own soft tint for the footer strip. Slot 6 measures 7.35:1 and slot 5 measures 6.75:1; the four new trios must be audited in `test_tokens.rs` as part of the token work UI-A1 §3 describes. The 3px band is a non-text UI indicator and needs ≥3:1 against the card background (`--sc-inset` `#0F1116`), which every slot clears comfortably.

---

## 3. Hotkeys (FR-211)

### 3.1 What the key does — and what it cannot do

**Pressing a group's key stages that group's first slide. It does not change the audience output. Go Live commits.** This is the load-bearing constraint on the whole ticket (CON-U2), and the requirement is stronger than "we didn't wire it to Live":

> **It must be impossible for a group hotkey to reach the Live output.** The handler dispatches exactly one command — the same `select_slide` / stage the arrow keys already use — and that command's permission is `Navigate`, not `GoLive` (`rbac.rs:110-113`). A hotkey that could go live would need a *different command*, and there is none. That is the property to assert in review.

Budget: keypress → staged ≤150ms (METRIC-202, inheriting NFR-004).

### 3.2 Assignment — deterministic, collision-checked, never surprising

Keys are **auto-assigned**. The algorithm runs once per song, in group order, and is pure — the same song always produces the same keys, so an operator's muscle memory survives a reload.

For each group, in order of first appearance, take the first candidate that is free:

1. **A trailing number in the group name** → that digit. `Verse 2` → `2`. This is how worship leaders actually talk, and it beats any letter derived from "Verse 2".
2. **The first letter of the group name** → `Chorus` → `C`.
3. **Each subsequent distinct letter of the name**, in order. `Bridge` → `B` is unavailable (§3.3), so → `R`.
4. **The first free letter A–Z**, then the first free digit.
5. **Nothing.** The group gets no chip and a muted **"no key"** badge in place of one.

"Free" means: not reserved by the canonical keymap (§3.3) and not already assigned to another group **in this song**.

Worked example — a typical song:

| Group | Key | Rule |
|---|---|---|
| Verse 1 | `1` | trailing number |
| Pre-Chorus | `P` | first letter |
| Chorus | `C` | first letter |
| Verse 2 | `2` | trailing number |
| Bridge | `R` | `B` reserved → next distinct letter |
| Tag | `T` | first letter |

### 3.3 The reserved set — read it from the keymap, do not hardcode it

`selahcue-app/src/keymap.rs` is the collision authority (AS-U4). It claims `Space`, `→`, `←`, `Enter`, `Esc`, `Backspace` and the character **`B`** (Blackout). Everything else single-key is free: bare digits are unused (the console's `1`–`7` bindings are `Cmd/Ctrl`-modified, `app.js:3873`), and every letter except `B` is unused unmodified.

**The assignment must query the keymap at runtime, not copy this list.** If a future story claims another letter, a hardcoded list silently starts handing out a key that no longer works — a failure that would only show up mid-service. Extend `keymap.rs` with a `is_reserved(KeyPress) -> bool` (or equivalent) and call it.

> **Consequence worth stating plainly, because every reviewer familiar with Proclaim will ask: `B` for Bridge is permanently impossible in SelahCue.** Blackout is `B` and the keymap module documents emergency actions as **non-unbindable** — there is no configuration surface that can remove them. Bridge therefore gets `R`. This is correct, it is not a bug, and it should not be "fixed" by weakening Blackout.

### 3.4 The key chip

On the first slide of each group only, at the right of the footer strip: the Design 2.0 **kbd chip** primitive — `--sc-inset` background, 1px `--sc-border`, radius 6, 11px 700, the key character in `--sc-text`.

- **Idle** — as above.
- **Pressed** — the chip inverts to the group ink for 180ms, then returns. Suppressed under `prefers-reduced-motion`, where the confirmation is carried by the staged frame moving and the announcement, both of which happen regardless.
- **No key** — a muted **"no key"** chip in `--sc-text-secondary` on `--sc-inset`. Never an empty space, which reads as a rendering fault.

### 3.5 When hotkeys are inactive

- While a **text input, textarea, search field or content-editable has focus** — the existing keymap rule. A worship leader typing "Chorus" into search must not stage six sections.
- While a **modal or confirm dialog is open**, except the always-global emergency chords, which pierce dialogs by design.
- When the open item is **not a song** — there are no groups, so there are no keys.

There is **no** global "hotkeys off" toggle in v1. The focus rule covers the real accident case, and a hidden mode that silently disables a documented key is worse than no mode.

---

## 4. States

| State | Trigger | Treatment |
|---|---|---|
| **idle** | default | band + name + chip per §2 |
| **pressed** | the group's key | chip flash, that group's first slide becomes staged, announcement (§6) |
| **already staged** | key pressed for the group already staged | re-stage its **first** slide. Not a no-op: an operator deep in verse 2 pressing `2` means "back to the top of verse 2". Announcement says so. |
| **no key** | assignment exhausted (§3.2 step 5) | "no key" chip; the group is still reachable by click and by arrow keys |
| **not a song** | a scripture / announcement / media item | no bands, no chips, no keys registered |
| **input focused** | §3.5 | keys inert; no visual change (a chip that dimmed on every keystroke would be noise) |
| **permission denied** | role lacks `Navigate` | keys inert, with an announced reason on first press — never a silent no-op |

---

## 5. Edge cases

- **Two groups with the same name** — "Chorus" twice. They get **distinct keys** (`C`, then `H` by rule 3) and the **same colour**, because they are the same kind of section. The chip disambiguates; the colour is not trying to.
- **More groups than available keys** — 35 keys exist (25 letters + 10 digits). Beyond that, groups get "no key". The ticket anticipated a limit of 26; digits raise it, and the fallback behaviour is unchanged.
- **A group whose name is only punctuation or empty** — falls to rule 4 (first free letter) and displays as "Other" in slot 6.
- **A group with no slides** — no band to draw and nothing to stage. It gets no key; it is skipped in assignment order so it does not consume one.
- **The song changes while the operator is in it** (edited elsewhere, host arbitration) — keys are reassigned by the same pure algorithm, so unchanged groups keep their keys. Only added or removed groups shift anything, and the chips update in place. Do **not** re-derive keys from a random ordering.
- **A key is pressed twice rapidly** — each press stages; there is no double-press meaning. Staging is idempotent and output-neutral, so a repeat is harmless.
- **A group hotkey and the density cluster's `-`/`+`** — no collision: the cluster's keys are scoped to the focused control and `stopPropagation()` (`SLIDE-VIEW-DENSITY-spec.md` §4.3).

---

## 6. Accessibility

- **`aria-keyshortcuts`** on each group's first slide option, carrying the assigned key (e.g. `aria-keyshortcuts="C"`). This is what lets a screen reader user discover the shortcut instead of learning it from a chip they cannot see.
- **The chip is not the only place the key is stated.** The option's accessible name includes it: *"Slide 7, Chorus, shortcut C"*.
- **The jump announces** through the existing `aria-live` scene payload: **"Staged: Chorus 1"**. On a re-stage of the already-staged group: *"Staged: Chorus 1, from the start"*. On a denied press: *"You do not have permission to change the staged slide."*
- **Colour is never the only cue (WCAG 1.4.1).** The group name is text on the first slide of every group, in every view. The key is text. On continuation slides the band alone carries no meaning that is not already available from the name above it and from the slide's accessible name, which always includes the group.
- **Reduced motion** — the chip flash is suppressed; the announcement and the moved staging still confirm the action.
- **Contrast** — group ink on group soft tint at AA for the name and chip; the 3px band at ≥3:1 as a non-text indicator. `--sc-text-muted` is not used.
- **Never colour-only for status** — the group band must never be mistaken for a status frame. It is 3px, at the bottom edge, inside the radius; a status frame is a 2px full border. Different geometry, different position, and no group hue is in a status family.

---

## 7. RBAC (CON-U6 — four roles today, not seven)

- **Desktop console** is the authoritative operator; group hotkeys are a desktop surface.
- **The jump is a staging request**, so it needs `Permission::Navigate`, not `GoLive` — the same permission the arrow keys already use. Nothing here escalates.
- **Mobile**: a mobile client capable of navigation under **today's four-role model (the Producer path)** may issue the same staged jump. **Do not design or implement against the seven-role matrix** — `86ajxuf81` / `86ajxufbg` are *not* dependencies of this ticket. The mobile plan view otherwise shows group colour and name **read-only** (§2.2).
- A role without `Navigate` gets an announced refusal, not silence (§4).

---

## 8. Open question carried — an assumption, not a decision

> **OQ-7 is unanswered. What follows is the PRD's stated consequence of silence, taken as an assumption awaiting owner confirmation. It is not a decision, and this spec does not close OQ-7.**
>
> **Assumed:** keys are **auto-assigned only** in v1. No per-song user assignment.
> **Why this is a comfortable place to sit:** the algorithm in §3.2 is pure and deterministic, so the keys a song gets are stable and predictable — which is most of what a user-assignable system would have bought. The two cases it does not serve are a church with a house convention that differs from the derived letters, and the `B`-for-Bridge expectation that SelahCue can never satisfy (§3.3).
> **If the owner chooses user-assignable:** it becomes a per-song field, the collision check in §3.3 stays exactly as specified (it is the part that must not be user-overridable), and it should be built on `86ak11qq4` (remappable keyboard shortcuts, currently deferred) rather than as a second one-off mechanism. The chip, the states, the announcements and the palette are all unaffected.

**OQ-8 is answered** — keep the staging invariant. The acceptance criteria here stand as written; a group hotkey stages and only Go Live commits. The double-click accelerator (`DOUBLE-CLICK-GO-LIVE-proposal.md`) is a **pointer** gesture on a slide and does not apply to hotkeys: there is no "double-press to go live", and there should not be, because a keyboard already has an unambiguous commit key in `⏎`.

**DEC-016 remains PROPOSED.**

---

## 9. Findings

**F1 — `B` for Bridge is permanently unavailable** (§3.3). Not a defect; a consequence of Blackout being non-unbindable. Stated because it is the first thing anyone comparing to Proclaim will raise.

**F2 — the reserved-key list must be read from `keymap.rs`, not copied into the webview.** A hardcoded list will silently rot the first time another story claims a letter, and it will fail mid-service rather than at build time. This is a small implementation requirement with a disproportionate failure mode.

**F3 — this ticket consumes the token work introduced by UI-A1.** The structure palette's four new trios are defined in `PLAN-SECTIONS-DURATIONS-spec.md` §3 and are a coordinated four-surface change. **UI-C1 cannot ship before that token work lands**, even though the two tickets are otherwise independent. @Diego — that is a sequencing dependency the tickets do not currently record.

**F4 — all numbered verses share one hue** (§2.3). A reviewer expecting "every section its own colour" will read this as a gap. It is a decision: the palette is six wide, the distinction between Verse 1 and Verse 2 is carried by the number, and spending hues on it would leave nothing for Tag and Pre-chorus.

---

## 10. Handoff and QA

**Depends on:** `86ajpzha3` (songs: multi-slide items with structure, complete) for the group model; **UI-A1's token work** for four of the six palette slots (F3).

**QA steps** are posted in list form on the ticket.
