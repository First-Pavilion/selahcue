# App Navigation / Information Architecture — Design Spec (86ajq1n14)

**Status:** design (gates a frontend impl story) · **Owner:** /ui-ux-designer · **Requirements:** FR-014 (design system/IA), FR-040/FR-151 (outputs) · **Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` — menu + console de-clutter (node ids in the handoff); the Output manager reuses the existing **`28:2` Displays & Outputs** page.

> The app is gaining surfaces (Console, Theme Designer, Displays & Outputs, Plan/Library, Settings). This spec defines **how the operator navigates between them** and **moves the Output manager out of the console** into its own surface, leaving only a compact status behind.

---

## 1. Decision — a top-bar **app menu** (committed; not a left nav rail)

**Chosen:** the top-left **SelahCue** wordmark is an **app-menu button** (`≡ SelahCue ▾`); clicking it — or **`F10`** / **`Cmd/Ctrl+M`** — opens a menu of surfaces. Each surface is a **full-page route** (the WKWebView swaps content) sharing the top bar (`SelahCue / <surface>`), matching the existing `28:2` / `204:124` frames.

**Why (UX rationale, owner asked for the best call):** the operator's real job is **live cueing** in a dense OBS 3-zone console with a pinned emergency footer; the other surfaces (Theme Designer, Displays & Outputs, Settings) are **occasional setup/config**, not per-cue. A persistent left nav rail permanently taxes the console's horizontal space (Preview|Live + panels are already tight) to speed up navigation that happens a few times per service — a poor trade. The top-bar menu is **zero-footprint when closed**, keeps every pixel for the live zones, and reuses the design language already in `28:2`/`204:124`. *Rejected:* **left nav rail** (constant ~48px space cost for rare nav; wrong priority for a live tool), **bottom tabs** (collide with the pinned emergency footer). One-click speed is recovered via **accesskeys 1–5** for power users.

**Surfaces (menu order):**
| Item | Route | Home? | Accesskey |
|---|---|---|---|
| **Live Console** | the OBS operator console (`165:124` / `dist/index.html`) | ✅ `Esc` returns here from any surface | `1` |
| **Theme Designer** | `204:124` (S8-3a/c) | | `2` |
| **Displays & Outputs** | `28:2` (the Output manager, §3) | | `3` |
| **Plan / Library** | (later surface) | | `4` |
| **Settings** | (later surface) | | `5` |

**Why a top-bar menu, not a rail:** the console is a dense OBS 3-zone layout with a pinned emergency footer; a persistent left rail steals horizontal space from the live zones. A top-bar menu is **zero-footprint when closed**, and surfaces are occasional destinations (you live in the Console during service). *Rejected:* left nav rail (space cost), bottom tabs (collides with the emergency footer).

---

## 2. Invariants — emergency + keymap on **every** surface

- The **emergency footer** (`■ BLACKOUT` · `✕ CLEAR ALL`) stays **pinned on every surface**, not just the Console — an operator must be able to black/clear the audience output while in the Theme Designer or Output manager.
- The canonical keymap's **always-global chords** (`Cmd/Ctrl+.` clear-all, `Cmd/Ctrl+B` blackout) fire on every surface regardless of focus (the pinned-invariant the console tests already assert — extend it app-wide).
- The app menu is a proper `role="menu"`: arrow-key navigation, `Esc` closes + returns focus, and it **never overlays or traps focus over the emergency footer**. Opening the menu does not change the live output.
- Route change announces the active surface (`aria-current="page"` on the menu item; an `aria-live` "Now on: Theme Designer").

**Focus order (any surface):** app-menu → surface content → emergency footer.

---

## 3. Screen manager — its own **page** ("Screens"): the best of ProPresenter + Pewbeam

The output manager **moves out of the console** into its own **"Screens"** page. **Decision (owner asked for the best call, weighing two references):**

- **From ProPresenter** — the **Screen vs Output** distinction and, crucially, the **screen ROLE**: *Audience* vs *Stage* (SelahCue already has main/stage outputs + a stage/confidence display + FR-040). A role determines what a screen shows.
- **From Pewbeam** — the **flat, scannable per-screen list with an enable toggle**: volunteer-friendly, low cognitive load (the target user is often a church volunteer, not an AV engineer).
- **Rejected for MVP (ProPresenter power features, deferred R2 — seams noted):** per-layer **Looks**, **Mirror / Grouped / Edge-blend** screen types, multi-screen groups.
- **Rejected (pure Pewbeam):** a role-less flat list — SelahCue's stage/confidence output genuinely needs *different* config (current/next/timer, not a theme), so a role concept is required.

**Verdict:** a **simple per-screen list** (Pewbeam ergonomics) where each screen carries a **role** (ProPresenter's concept) that swaps its content control.

**Per-screen row (design):**
- **Name + role badge** — `Main Screen` · **Audience**; `Stage Display` · **Stage**; `Lower Third` · **Lower-third**; `Stream` · **Stream**.
- **Enable this screen** — a right-aligned toggle (accent ON). *Chose Pewbeam's toggle over ProPresenter's add/delete* — an operator flips a stream/lower-third on/off fast mid-service; deleting + recreating is wrong for the common fixed set. A disabled screen collapses to name + role + toggle.
- **On enable, reveal:**
  1. **Output** — one dropdown: a physical display / **NDI** / **SDI** / browser-source (ProPresenter's Hardware tab, simplified to a single control).
  2. **Format** — resolution + refresh (e.g. *1920×1080 · 60 Hz*).
  3. **Content — role-dependent:**
     - **Audience / Lower-third / Stream** → a **Theme** picker (the **per-screen theme/template**, §3a) — SelahCue's MVP simplification of ProPresenter's *Looks* (per-layer routing is R2).
     - **Stage** → **Stage layout** toggles (Current line · Next line · Timer · Clock) instead of a theme — driving the confidence monitor SelahCue already renders (`StageDisplay`).
- **`Identify`** (page top-right) flashes each physical output's number. **`+ Add screen`** creates a virtual/NDI/stream screen; **delete** is offered for virtual screens only (a physical-display screen can be disabled, not deleted).

*Page, not modal:* multiple screens each with several controls is a scannable list that suits a full page; advanced per-screen transforms (delay/rotate/crop, R2 FR-044) sit under a per-row **"Advanced ▾"**.

**States:**
| State | Trigger | Treatment |
|---|---|---|
| **empty** | no displays detected | the Output dropdown reads "No displays found — connect a projector / add NDI"; enable disabled with a hint |
| **disabled** | screen toggle OFF | row collapsed to name + role + toggle (default for unused screens) |
| **audience-configured** | Audience/Lower-third/Stream role, enabled | Output · Format · **Theme** filled; green role dot |
| **stage-configured** | Stage role, enabled | Output · Format · **Stage-layout toggles** (no theme) |
| **mismatch** | an assigned output disappeared | Output dropdown **amber** "— display disconnected · reselect"; role dot amber + text label (colour never the only cue) |
| **identify-active** | *Identify* pressed | each physical output shows its big number; button `aria-pressed` |

### 3a. Per-screen theme (model implication)

Each **Audience-class** screen carries its **own theme/template** (its *Theme* control): the main projector, a lower-third NDI feed, and a stream can render **different designs simultaneously** from the same live content. This extends the S8-3b engine (one global theme today) to a **per-screen theme map** — a follow-up **engine story** (related to S8-3d per-item override, but keyed by **screen**, not plan item). The design here is the source of truth for it; flagged for the engine backlog.

---

## 4. Console de-clutter — a compact outputs status

The console's right-zone **Outputs `aside`** (role rows + pickers + Identify) is **replaced by a compact, read-only status**:

- One line of role dots + labels: `Outputs  ● Main  ● Stage  ● Stream  · 3 assigned` (green = healthy; **amber dot on mismatch**).
- A **`Manage outputs ⤢`** button → routes to the Displays & Outputs surface (§3).
- **Identify displays** stays reachable from the console (a small button next to the status) — it is a live diagnostic used mid-setup.

This frees the console right zone (timer + detections + the theme picker stay) and keeps outputs *observable* at a glance without the full manager inline.

---

## 5. Accessibility & tokens

- Menu: `role="menu"`/`menuitem`, arrow-key + `Home`/`End` nav, `Esc` close + focus-return, `aria-current="page"` on the active surface; each item has an accesskey (§1) and an SR name. AA contrast (design-system tokens).
- Compact status: the amber mismatch dot carries a text label too (colour is never the only cue — WCAG 1.4.1).
- All chrome bound to the existing tokens (`DESIGN-TOKENS.md` / `tokens.rs`: bg/base, bg/panel, border, text/primary, accent, preview/live/warn) — extend, don't fork.

---

## 6. Handoff → implementation (later frontend story)

- Add the app-menu to the console `<header>` (replace the bare `<h1>`), routing between surfaces in the WKWebView; persist the emergency footer + global chords on every route (extend the pinned keymap invariant app-wide).
- Replace the Outputs `aside` with the compact status + `Manage outputs` route; keep `Identify`.
- Build the Output-manager surface from `28:2` (+ the empty/mismatch/identify states); wire to the existing `assign_output` / `identify_outputs` commands (already in the wire protocol).
- Tests (later): nav routing + `aria-current`; **emergency-chord reachability on every surface**; output-manager state coverage; the canonical-keymap pin extended app-wide.

**Open at the gate:** confirm (a) top-bar menu vs left rail; (b) Output manager as a page (reuse 28:2) vs a modal overlay; (c) menu trigger key (`F10` vs `Cmd/Ctrl+M`).
