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

## 3. Output manager — its own **page**, redesigned for ease of use (`Output settings`)

The Output manager **moves out of the console** into its own **page** (reached from the menu, or the console shortcut §4). Per owner direction it drops the complex drag-grid + big inspector (the earlier `28:2`) in favour of a **simple, scannable per-output list** ("Output settings"): one **row per output**, each a self-contained card the operator enables and configures in place.

**Per-output row (design):**
- **Title + subtitle** — `Main Output` / `Configure Main Output` (and `Output 2…N`).
- **Enable this output** — a right-aligned toggle (accent when ON). A disabled output shows the row collapsed (title + toggle only).
- **On enable, reveal three dropdowns** (one line):
  1. **Select theme** — the **per-output theme/template** (e.g. *Full Screen*, *Lower Third*) — so each output renders its own look (Main = Full Screen, an NDI feed = Lower Third). *(This establishes **per-output theme** as the model — see §3a.)*
  2. **Output monitor** — a physical display **or** a virtual output (*NDI Output*, browser-source).
  3. **Output format** — resolution + refresh (e.g. *1920×1080 / 30 Hz*, */ 24 Hz*).
- **`Identify`** stays available (top-right of the page) to flash the number on each physical output.

*Page, not modal:* multiple outputs each with three controls is a scannable list that benefits from a full page. A quick-assign modal is a possible later shortcut (noted). The advanced per-output transforms (delay/rotate/crop/test-pattern, R2 FR-044) live under an optional **"Advanced ▾"** disclosure per row so the default view stays simple.

**States:**
| State | Trigger | Treatment |
|---|---|---|
| **empty** | no displays detected | rows show the monitor dropdown as "No displays found — connect a projector / add NDI"; enable is disabled with a hint |
| **disabled** | output toggle OFF | row collapsed to title + toggle (no dropdowns) — the default for unused outputs |
| **enabled/assigned** | toggle ON + monitor chosen | the three dropdowns filled; a green status dot by the title |
| **mismatch** | an assigned monitor disappeared | the monitor dropdown turns **amber** "— display disconnected · reselect"; title dot amber; a text label (colour never the only cue) |
| **identify-active** | *Identify* pressed | each physical output shows its big number; the button is `aria-pressed` |

### 3a. Per-output theme (model implication)

Each output carries its **own theme/template** (the row's *Select theme*). The audience/main output, a stage display, and a lower-third NDI feed can each render a different design **simultaneously** from the same live content. This extends the S8-3b engine (one global theme today) to a **per-output theme map** — a follow-up engine story (relates to S8-3d per-item override, but keyed by **output**, not plan item). Flagged for the engine backlog; the design here is the source of truth for it.

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
