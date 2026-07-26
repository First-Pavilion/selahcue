# Code Review — App menu + Screens page (86ajq321f)

- **Scope:** story `86ajq321f` — implement the gated nav/Screens design (`NAV-IA-spec.md`; Figma 212:124/217:124) in the operator console (`dist/index.html`): a top-bar app menu + surface routing, a "Screens" output-manager surface, and a de-cluttered console. Executed via `/goal` (`TASK-86ajq321f-nav-screens-impl.md`).
- **Method:** an adversarial Workflow review (`wf_24fcee74-a1e`, 3 lenses — a11y/keyboard · invariant-preservation · wiring — 15 agents, each finding verified). **11 raised → 11 CONFIRMED → 8 fixed, 3 accepted (pre-existing); 1 refuted.**

## What shipped

The console single-page app gained a **top-bar app menu** (`role="menu"`, accesskeys 1–5, F10) routing between in-page surfaces — Live Console (home) · Theme Designer (placeholder) · **Screens** · Plan · Settings — while `<header>` (menu) and `<footer id="emergency">` stay **outside** the router so the emergency footer + the window keymap persist on every surface. The **Screens** surface (from 217:124) renders per-screen rows with a **role** (Audience→Theme dropdown; Stage→Current/Next/Timer chips), Output assignment, and Format, wired to the existing `assign_output`/`set_theme`/`identify_outputs` commands. The console right zone is **de-cluttered** to a compact outputs status + a "Manage outputs" route. Verified by the token pin test, a new structure test, JS syntax, balanced tags, and headless renders of the real console.

## Findings and dispositions

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | **HIGH** | With the menu open, the global capture keydown handler still fired transport/emergency keys on a focused menuitem — arrow-navigating the menu could stage a verse / Backspace could clear live output | **Fixed:** an `isMenuOpen()` early-return in the handler (after the emergency chords + F10) — menu nav no longer drives the presentation |
| 2 | **HIGH** | Menu items had no visible focus ring (`:focus-visible` bg == panel bg + `outline:none`) — WCAG 2.4.7 | **Fixed:** distinct hover bg (#232a35) + a 2px accent `outline` on `:focus-visible` (confirmed in a headless render) |
| 3 | med | Route change was silent to AT + dropped focus to `<body>` | **Fixed:** `showSurface` moves focus into the new surface (`tabindex=-1` + `.focus()`) + announces via an `aria-live` `#route-status` region |
| 4 | med | Menu keyboard model incomplete (no Home/End, Tab didn't close, no roving tabindex) | **Fixed:** Home/End added; Tab closes; roving tabindex (`focusNav`) |
| 5 | med | `Cmd/Ctrl+M` collides with the macOS "Minimize window" accelerator | **Fixed:** dropped the `Cmd+M` binding — F10 (+ the clickable button) opens the menu |
| 6 | med | The menu keydown branch returned without `disarm()`, re-opening the double-Esc Clear-all hole | **Fixed:** `disarm()` in the F10 branch |
| 7 | low | Bare transport keys fired on every surface, not just the console | **Fixed:** transport keys gated to when `#surface-console` is active (emergency chords stay global) |
| 8 | low | Stale deferred view can render on blur when data reverts while a picker is focused | **Accepted** — the pre-existing focus-out deferral ("don't yank a focused picker"), carried over unchanged; converges on the next update |
| 9 | low | Chosen assignment visibly reverts in the dropdown until focus leaves | **Accepted** — the pre-existing "snap back to the host's truth" pattern (the picker re-reflects persisted state next update) |
| 10 | low | `#screens-identify`/rows stay stale if outputs drop to zero while a picker is focused | **Accepted** — same focus-out deferral; cosmetic, converges on next non-focused render |
| 11 | low | Empty themes list → an option-less Theme dropdown | **Fixed:** a disabled "No themes offered" placeholder |

**Refuted (1):** a claimed additional keymap regression that verification could not reproduce.

## Verification

`test_tokens` (pin + the new `operator_webview_has_the_app_menu_and_screens_surface` structure test) green; JS syntax valid; all tags balanced (div 31/31); headless renders confirm the menu, the Screens surface (with the emergency footer pinned on it), the de-cluttered status, and the focus ring. **Deferred (seams noted):** the per-screen theme ENGINE (`86ajq321k` — the Theme dropdown sets the global theme today), the Theme Designer editor (S8-3c), the Plan/Settings surfaces (menu entries only). **CI:** pending this push.
