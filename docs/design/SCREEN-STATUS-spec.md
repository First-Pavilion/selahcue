# Top-bar per-screen on-air status — Design Spec (UI-D1)

**Status:** design · **Owner:** /ui-ux-designer (Uma) · **ClickUp:** [`86ak7kgn9`](https://app.clickup.com/t/86ak7kgn9) (sequence #4)
**Requirement:** FR-214 — one dot + label per enabled screen, in **SelahCue** colour semantics. MVP.
**Evidence grade:** CITED (E01), and SelahCue deliberately **exceeds** the reference: its Audience/Stage toggles cover system screens only — NDI/SDI screens are always on and cannot be toggled — so its at-a-glance state is partial by design. SelahCue's status covers **every registered screen, including virtual feeds**.
**Sources:** PRD §14 EPIC-UI-D + "Designer detail — FR-214/215" · research §6 T2 (Screen Configuration is the #1 volunteer failure point, cited 2019→2025), §7.5 (FreeShow precedent) · `NAV-IA-spec.md` §3/§4 · `UX-CANONICAL.md` · shipped `dist/index.html` `<header>`.
**Figma:** built — [Section: SelahCue · Operator UI MVP — EPIC-UI-A/B/C/D (RISK-205 Figma catch-up)](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-124).
Frames: [UI-D1 · 01 — The six per-screen state treatments](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=985-127) · [UI-D1 · 02 — Special states and the detail popover](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=985-196).
In context, in the real 64px top bar with a before/after and the narrow variant: [IN CONTEXT · 04 — top bar, before / after UI-D1](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=981-124).
Also: [legend + open questions](https://www.figma.com/design/SYQn5hFY8YVQKm3c6rw0eJ/SelahCue?node-id=965-125). The frames are drawn from this spec and the shipped `--sc-*` token values, not copied from the existing Design 2.0 frames (RISK-205: those lag the console on contrast). Chips read **PREVIEW / LIVE** pending Priya's ruling (F3). Colours bind to `sc/*` variables added to the file's `SelahCue Color` collection at their shipped values; the six structure-palette trios are present and marked **PROPOSED**.
Drawn to scale, the narrow variant surfaced a fit problem the spec did not predict: at ~1100px the bar does not fit even with the status group already collapsed. It is annotated on the frame with three options and a recommendation, for Priya and the owner to settle.

---

## 1. 🚨 The colour collision — read this before anything else

**In the owner's screenshot the reference shows Audience as a red hollow ring meaning OFF, and Stage as green meaning ON.**

**SelahCue inverts both.** Red means *on air*. Green means *staged / safe*. Importing the reference's mapping would put a red ring on a screen that is dark and a green light on a screen that is showing the congregation — the exact opposite of the truth, on the one indicator an operator glances at mid-service.

This is why FR-214 is classified **ADAPT, not ADOPT**. The divergence is deliberate and is recorded in DEC-016 fact #2 and CON-U4.

| State | SelahCue |
|---|---|
| **red, filled** | this screen is showing live content |
| **neutral, hollow** | enabled and idle |
| **amber, triangle** | fault / mismatch |
| **struck-through + "OFF"** | disabled |

> If a reviewer says *"but the reference uses red for off"* — that is the collision, not a bug report. Point them here.

---

## 2. Where it goes

Into the existing `.topbar-status` cluster in the console `<header>`, **before** the timer chip, as a single labelled group:

```
┌ topbar-left ─────────┐   ┌ topbar-transport ──────────────┐   ┌ topbar-status ────────────────────────────┐
│ ≡ SelahCue ▾ │ Live  │   │ ◀ Prev  Next ▶  ● GO LIVE  Blk │   │ [▤ ● Main ○ Stage ○ Stream ○ L3] ⏱ 🕘 ⬤ │
└──────────────────────┘   └────────────────────────────────┘   └───────────────────────────────────────────┘
```

**It is one control, not four.** The whole group is a single `<button>` that routes to the Screens page (`NAV-IA-spec.md` §3). Four separate click targets in a 64px bar would be small, and there is nothing per-screen to click — the status is read-only (§6).

**It is on every surface**, not only the console. The top bar is shared, and knowing what is on air matters just as much while you are in the Theme Designer. This matches the emergency-footer invariant (`NAV-IA-spec.md` §2): the things that tell you about the audience follow you.

### 2.1 Chip anatomy

Each screen renders as `[glyph] Name [state word, only when not idle]`.

| Part | Detail |
|---|---|
| Glyph | 8px, per §3. Shape differs per state, not only colour. |
| Name | 11px 600, `--sc-text-secondary`. The short registry name: Main, Stage, Stream, L3. |
| State word | 10px 700 status chip, **only** for LIVE / OFF / FAULT / BLACKOUT / IDENTIFY. Idle is the quiet default and shows nothing. |

Idle chips are therefore ~62px, so four screens fit in ~250px. That is what keeps the group viable in a 64px bar.

### 2.2 Responsive collapse — collapse the quiet, never the loud

Below a top-bar content width where the group would push the transport out of centre (~1100px window):

- Screens in **idle** collapse into one summary chip: `▤ 4 screens`.
- Screens in **LIVE, FAULT, OFF or IDENTIFY** stay expanded, always, at every width.
- So the worst case narrow rendering is `▤ 3 screens  ● Main LIVE` — never `▤ 4 screens` alone while something is on air or broken.

Full per-screen detail is in a popover on hover **and on focus**, listing every screen with its state word. Nothing is only discoverable by hovering.

---

## 3. State treatment

| State | Glyph | Colour | Name | Chip | Accessible name |
|---|---|---|---|---|---|
| **Live** | `●` filled | `--sc-live` `#FF4D4D` | normal | `LIVE` — `--sc-live` ink on `--sc-live-soft`, `--sc-live-border` (5.31:1) | "Main: showing live content" |
| **Enabled-idle** | `○` hollow | `--sc-text-secondary` `#A7AEBE` | normal | none | "Stage: enabled, idle" |
| **Blackout** | `○` hollow | `--sc-text-secondary` | normal | `BLACKOUT` — `--sc-text` on `--sc-inset`, `--sc-border-strong` | "Main: enabled, blacked out" |
| **Fault / mismatch** | `▲` triangle | `--sc-warn` `#F5A524` | normal | `FAULT` — `--sc-warn` on `--sc-warn-soft`, `--sc-warn-border` (7.56:1) | "Stream: display disconnected — reselect" |
| **Disabled** | `⊘` | `--sc-text-muted`† | **struck-through**, dimmed | `OFF` — `--sc-text-secondary` on `--sc-inset` | "L3: disabled" |
| **Identify-active** | `❶` the output number | `--sc-primary` | normal | `IDENTIFY` | "Main: identifying, output 1" |

**Four channels carry state, not one:** glyph shape, colour, the name's decoration, and a text chip. A monochrome screenshot of this bar is still readable, which is the test.

† The one place `--sc-text-muted` is right: a disabled screen's glyph is *deliberately* recessive, it is a non-text indicator, and the name beside it is struck through and carries an `OFF` chip. No information depends on reading the glyph.

### 3.1 What "live" means, precisely

**A screen is LIVE when the compositor is putting non-blank content on it.**

- Blackout → **not** live. Idle-black plus a `BLACKOUT` chip, per the ticket.
- Cleared → not live. Idle.
- A stage/confidence screen showing NOW/NEXT/timer → **live**. It is showing content, to people. Stage screens are seen by the worship team, and "is my confidence monitor up?" is a real mid-service question.
- A disabled screen → never live, regardless of what the compositor thinks. Disabled wins.

This needs a **per-screen** signal. A global "something is live" flag cannot answer it — see §8-F2.

---

## 4. States and transitions

| State | Trigger | Treatment |
|---|---|---|
| **normal** | any mix of the six per-screen states | §3 |
| **no screens registered** | fresh install, nothing configured | `▤ No screens configured` in `--sc-warn`, routing to the Screens page. Not an empty space — an unconfigured output is the #1 volunteer failure (research §6 T2), and silence here is the failure mode. |
| **all disabled** | every screen toggled off | `▤ All screens off` with an `OFF` chip. Loud, because it means the congregation sees nothing. |
| **host link lost** | the console cannot reach the host | the group dims and shows `▤ Screens — status unknown`. **It must not keep showing the last-known dots as if current.** A stale green-looking bar during a disconnect is worse than an honest "unknown". |
| **updating** | a screen's state changed | the affected chip updates in place within **1s** (NFR-205). No spinner, no skeleton — a status indicator that flickers to a loading state is unreadable. |

---

## 5. Update path

Push, not poll. The status subscribes to the host's screen-state signal and re-renders the affected chip; it does not run a 1s timer against the registry. A poll would meet the ≤1s number on paper while showing state up to a second stale at the moment it matters.

**It must read real host signals.** `86ak4xxwm` ("stop the operator console fabricating system health") is in progress and is directly relevant: this indicator is worthless — worse than absent — if it reports a screen as live because the console assumed so. Where a signal is genuinely unavailable, the correct rendering is the **unknown** state in §4, never an optimistic guess.

**Bounded:** the subscription holds one state record per registered screen and nothing else. No history, no event log, no growth over a 12h service day.

---

## 6. It reports; it does not change anything

**This surface is read-only (CON-U2).** Clicking the group routes to the Screens page. It does **not** toggle a screen.

This matters more than it sounds. In the reference, the equivalent toolbar buttons *are* toggles. An operator arriving from that product will try to click a dot to mute the stream, and if the click toggled, they would black out a feed while trying to check it. So:

- The button's accessible name is **"Screen status — open Screens & Outputs"**. It says where it goes.
- The tooltip reads *"Read-only. Open Screens & Outputs to enable or disable a screen."*
- Nothing in the group is a toggle, has `aria-pressed`, or looks like a switch.

**FR-215 (console quick-mute) is R2 and is not this ticket.** When it lands it adds an explicit, separately-labelled control with an inline confirm and audit logging — it does not turn these dots into switches. Recorded here so the boundary is not blurred later.

**CON-U1** holds trivially: a status dot is a state indicator, not a rendering of audience output. Nothing here draws a frame.

---

## 7. Accessibility

- **Structure:** one `<button>` containing a `role="list"` of per-screen `role="listitem"` chips. One tab stop. The button's accessible name is §6's.
- **Every dot has a text label**, and separately, **every state has a non-colour channel** — glyph shape, text decoration, and a state chip (§3). The AC asks for the first; WCAG 1.4.1 needs the second, and the ticket's own "colour is never the only cue" is what makes the difference matter.
- **State changes announce politely** through an `aria-live="polite"` region: *"Main is now live"*, *"Stream: display disconnected"*, *"L3 disabled"*. Polite, never assertive — this fires during a service and must not interrupt.
- **Announcements are debounced and coalesced.** Four screens changing at once announces *"3 screens changed: Main live, Stream disconnected, L3 disabled"*, not four interruptions.
- **Contrast:** all chips use the Design 2.0 status-chip treatment (ink on same-hue soft tint with a border) — LIVE 5.31:1, FAULT 7.56:1. Screen names use `--sc-text-secondary` (8.13:1). **No new ink.** GO LIVE (8.70:1), BLACKOUT (7.19:1) and primary (4.72:1) are untouched — this group adds nothing near them (CON-U7).
- **Reduced motion:** the identify state's pulsing ring becomes a static ring. Nothing else animates.
- **The popover** (§2.2) opens on focus as well as hover, is `Esc`-dismissible, and returns focus to the button.

---

## 8. Findings

**F1 — FR-214 supersedes the shipped/NAV-IA status semantics; it does not merely add to them.**
`NAV-IA-spec.md` §4 specifies the console's compact outputs status as *"green = healthy; amber dot on mismatch"*. **Green-for-healthy conflicts with CON-U4**, where green means staged/safe, and it conflicts with FR-214's mapping, where enabled-and-idle is neutral. Under this spec there is **no green** in the screen status at all. `NAV-IA-spec.md` §4 needs updating to match, or the two documents will disagree and whoever builds this will follow the older one.

**F2 — per-screen "live" needs a per-screen signal, and it may not exist yet.**
§3.1 defines LIVE as "the compositor is putting non-blank content on this screen". If the host only exposes a global live/blackout state plus a per-screen enabled flag, then a Stream screen that is enabled but receiving nothing would render as LIVE, which is a lie on the one indicator that must not lie. **This should be verified against `86ak4xxwm` before implementation is sized.** If the per-screen signal is not available, the honest MVP is `enabled / disabled / fault` with LIVE deferred — and that is very close to OQ-5's simpler alternative, which would then be the *forced* answer rather than a preference.

**F3 — "every dot has a text label" is necessary but not sufficient.**
The screen *name* labels the screen; it does not label the *state*. Taken literally, the AC would be satisfied by four named dots whose state is carried by colour alone — a WCAG 1.4.1 failure. §3 adds glyph shape, text decoration and a state chip. Flagged because the AC as written could be signed off on the weaker reading.

**F4 — the top bar is already dense.** Timer chip, LIVE chip, clock and connection pill occupy `.topbar-status` today. Adding four screen chips is viable only because idle chips carry no state word (§2.1) and because the collapse rule keeps the quiet ones out of the way (§2.2). If a future story adds another top-bar element, this group is the one that will break first.

---

## 9. Open question carried — an assumption, not a decision

> **OQ-5 is unanswered. The mapping in §1 is what the PRD proposes, taken here as an assumption awaiting owner confirmation. It is not a decision, and this spec does not close OQ-5.**
>
> **Assumed:** red dot = the screen is rendering live content; struck-through = disabled.
> **The alternative the PRD names** — dot = enabled/disabled only — is simpler, cheaper, and needs no per-screen live signal. It also **loses on-air awareness**, which is the entire user problem (JTBD-U4): an operator who can see that Stream is *enabled* still cannot tell whether the stream is seeing anything.
> **My recommendation is the richer mapping**, on the condition in F2: if the per-screen live signal does not exist and is not cheap, the simpler mapping is the honest ship, and LIVE arrives when the signal does. Either way the layout, the chip anatomy, the collapse rule and the accessibility work are identical — only the state set narrows. **Cost of a late change: one state removed from §3.**

**CON-U6** — mobile shows this status **read-only for all four roles**. Nothing here assumes seven.
**DEC-016 remains PROPOSED.**

---

## 10. Handoff and QA

**Reads from:** the screen registry (`86ajujr0y`, complete) and the host signal seams (`86ak4xxwm`, in progress — F2). **Related:** `86ajtxnn1` (real OS display names) — the names in these chips must be the real registry names, not placeholders.

**QA steps** are posted in list form on the ticket.
