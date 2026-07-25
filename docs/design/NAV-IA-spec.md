# App Navigation / Information Architecture — Design Spec (86ajq1n14)

**Status:** design (gates a frontend impl story) · **Owner:** /ui-ux-designer · **Requirements:** FR-014 (design system/IA), FR-040/FR-151 (outputs) · **Figma:** file `SYQn5hFY8YVQKm3c6rw0eJ` — menu + console de-clutter (node ids in the handoff); the Output manager reuses the existing **`28:2` Displays & Outputs** page.

> The app is gaining surfaces (Console, Theme Designer, Displays & Outputs, Plan/Library, Settings). This spec defines **how the operator navigates between them** and **moves the Output manager out of the console** into its own surface, leaving only a compact status behind.

---

## 1. Decision — a top-bar **app menu** (not a left nav rail)

The top-left **SelahCue** wordmark becomes an **app-menu button** (`≡ SelahCue ▾`). Clicking it — or **`F10`** / **`Cmd/Ctrl+M`** — opens a menu listing the surfaces. Each surface is a **full-page route** (the WKWebView swaps content) sharing the top bar (`SelahCue / <surface>`), matching the existing `28:2` / `204:124` frames.

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

## 3. Output manager — its own surface (reuse `28:2`)

The Output manager **moves out of the console** into the existing **Displays & Outputs page** (`28:2`), reached from the menu (or the console shortcut, §4). That page already has: the **OUTPUTS list** (role rows with a status dot + resolution/connection + `Add output`), the **drag-arrange grid** (monitors numbered to match *Identify*), and the **per-output settings** inspector (resolution / fps / orientation / layout / theme / safe-area / delay / scaling / mirroring / test-pattern). *Page, not modal:* the arrange grid + settings are substantial and match `28:2`; a quick-assign modal is a possible later shortcut (noted).

**States to add on the manager surface:**
| State | Trigger | Treatment |
|---|---|---|
| **empty** | no displays detected | "No displays found — connect a projector or add a virtual output" + `Add output` |
| **assigned** | roles mapped to displays | the shipped look (`28:2`) — role rows with green dots |
| **mismatch** | an assigned display disappeared | the role row + its grid tile turn **amber**: "Main projector — display disconnected · Reassign"; the audience output falls back per FR-040 |
| **identify-active** | *Identify displays* pressed | each grid tile + each physical output shows its big number; the button is `aria-pressed` |

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
