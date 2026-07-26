# Goal Contract — TASK-86ajq321f-nav-screens-impl

## Identity

- Goal ID: TASK-86ajq321f-nav-screens-impl
- Parent goal ID: STAGE8-core-presentation
- Title: Implement the app menu + Screens page in the operator console per the gated design, preserving the pinned console invariants
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq321f
- Created: 2026-07-26
- Updated: 2026-07-26
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Turn the gated nav/Screens design (`docs/design/NAV-IA-spec.md`; Figma 212:124 menu / 217:124 Screens) into the operator console (`crates/selahcue-operator/dist/index.html`): a **top-bar app menu** that routes between in-page surfaces, a **Screens** surface (the redesigned output manager), and a **de-cluttered** console (compact outputs status). The emergency footer + canonical keymap must remain live on every surface. No console pin test may break.

## Baseline

Verified: `dist/index.html` is a single-page app — a `window` `keydown` listener drives the canonical keymap + the emergency chords (`Ctrl/Cmd+Shift+B` blackout, `Ctrl/Cmd+Shift+.` clear) which **already fire globally**; `<header><h1 id="plan-name">` (bare, no nav); the OBS 3-zone `<main>` (`zone-left/center/right`, `obs-row`, `id="preview-panel"/"live-panel"`); an `<aside aria-label="Outputs">` with `#outputs` + `#identify` (populated by `renderOutputs(view)`); the theme picker `#themes`; a pinned `<footer id="emergency">`. **Pin test** `selahcue-present/tests/test_tokens.rs::operator_webview_is_pinned_to_the_canonical_tokens` asserts the HTML *contains* a fixed set of needles (token hexes, `id="emergency"`, BLACKOUT/CLEAR ALL, zone-left/center/right, obs-row, preview/live panels, translation/verse-list, transcript/detections, badge() calls, prefers-reduced-motion) — ALL must remain. No test asserts absence, so additive markup is safe. Wire commands available: `assign_output`, `identify_outputs`, `set_theme`, `view` (+ the operator view carries `outputs`, `displays`, `themes`, `theme`).

## Inputs and evidence sources

- Story 86ajq321f + epic 86ajp08bx; NAV-IA-spec.md (§1 menu, §2 invariants, §3 Screens, §4 de-clutter); Figma 212:124/217:124; dist/index.html; test_tokens.rs; the operator Tauri commands (selahcue-operator/src/main.rs).

## Scope

### In scope

- **App menu**: replace the bare `<h1>` header with an app-menu button (`≡ SelahCue ▾`) + a `role="menu"` dropdown routing to **Live Console** (home) · **Theme Designer** (placeholder) · **Screens** · **Plan** (placeholder) · **Settings** (placeholder). Arrow-nav + `Esc` + `aria-current`; `F10`/`Ctrl/Cmd+M` to open; accesskeys 1–5. Keep `#plan-name` (render uses it).
- **Router**: show/hide in-page surface sections; `<header>` (menu) + `<footer id="emergency">` stay visible on every surface (so the emergency footer + the window keymap listener persist app-wide). The console 3-zone becomes the `console` surface (all inner ids/zones preserved).
- **Screens surface** (from 217:124): per-screen rows with a role badge (Audience/Stage/Lower-third/Stream) + Enable toggle + Output dropdown + Format + a Theme dropdown (uses the host `themes` list) + Identify; wired to `assign_output`/`identify_outputs`; honest states (empty/disabled/assigned/mismatch). Per-screen theme rendering is a separate engine story (86ajq321k) — the dropdown is UI + records intent (seam noted).
- **De-clutter**: replace the console Outputs `aside` body with a compact read-only status (role dots + "N assigned" + amber-on-mismatch) + a "Manage outputs" button routing to Screens; keep `#identify` reachable + the theme picker.

### Non-goals

- The per-screen theme ENGINE (86ajq321k); the Theme Designer editor (S8-3c); building the Plan/Settings surfaces (menu entries only); advanced per-output transforms (R2).

### Constraints

- ALL test_tokens needles remain (additive only). The canonical keymap + emergency chords work on every surface. No new external deps (self-contained webview). Accessible menu (roles/focus/keyboard). Preserve every pinned element id + the emergency footer + the badge()/keymap JS.

### Assumptions and unknowns

- ASSUMED: surfaces are in-page sections toggled by a router (the app is one WKWebView document) — matches the existing single-page keymap. The transport keys stay global (an operator can drive live from any surface — consistent with "live controls always reachable").

## Dependencies and approvals

- Design 86ajq1n14 (gated). Engine commands exist. Per-screen theme (86ajq321k) is a downstream story.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | App menu added + routes between surfaces (Console/Theme Designer/Screens/Plan/Settings); role=menu + arrow/Esc/accesskeys; `#plan-name` kept | screenshot/DOM review + a webview assert test | menu routes; a11y roles present | dist/index.html (app-menu role=menu, 5 surfaces, accesskeys) + test_tokens::operator_webview_has_the_app_menu_and_screens_surface | PASS |
| C-002 | yes | Emergency footer + canonical keymap + global chords remain live on EVERY surface (footer never hidden by the router; window listener intact) | code review + test_tokens (emergency needles) | footer persists; chords global | emergency footer sits AFTER </main> (asserted in the new test); window keymap + F10 added after the chords | PASS |
| C-003 | yes | Screens surface renders per-screen rows (role/enable/output/format/theme/identify) wired to assign_output/identify_outputs + honest states | screenshot + review | Screens matches 217:124 | #surface-screens + #screens-list wired to assign_output/set_theme/identify; role-driven (Audience→theme, Stage→chips); honest states | PASS |
| C-004 | yes | Console de-cluttered: compact outputs status + "Manage outputs" route replaces the aside body; identify + theme picker kept | screenshot + review | compact status + route | compact #outputs-status + #manage-outputs route; #identify + #themes kept | PASS |
| C-005 | yes | ALL pinned invariants intact: `test_tokens` green (every needle present); the webview still parses/loads; no console pin regression | `cargo test -p selahcue-present test_tokens` + operator build | test_tokens PASS; builds | token pin test 5/5 + structure test PASS; JS syntax valid; tags balanced (div 31/31) | PASS |
| C-006 | yes | Full verification: make ci (fmt/clippy/tests) + operator build green; independent Workflow review, findings fixed; 3-OS CI green | make-ci + Workflow + CI | all green; review fixed | review wf_24fcee74-a1e (11→8 fixed incl. 2 HIGH, 3 accepted); CODE-REVIEW-batch-nav-screens.md; **CI run 30190586979 green (11 success, flutter path-skipped)** | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-present test_tokens` (pin test); operator crate build (webview parses); a small assertion test that the new nav/screens ids + roles are present. Broader: make ci + 3-OS CI. Independent: Workflow review (a11y/keyboard-trap lens · invariant-preservation lens · wiring-correctness lens).
- Required environment: local + CI. (Live browser interaction not scriptable here; verify by DOM/structure + screenshots of the Figma reference + a headless contains-assert.)

## Iteration ledger

### Iteration 1

- Change: added the top-bar app menu + surface router + Screens surface + console de-clutter to dist/index.html (additive; all pin needles preserved). Wrapped the console 3-zone in #surface-console; emergency footer + keymap kept outside the router. Wired assign_output/set_theme/identify_outputs. New structure test.
- Verifier: token pin + structure tests green; JS syntax valid; tags balanced; headless renders of the real console (menu, Screens, focus).
- Result: C-001..C-005 PASS.
- Decision: continue to review.

### Iteration 2 — adversarial review fixes

- Review wf_24fcee74-a1e (a11y/keyboard · invariant · wiring): 11 confirmed → **8 fixed** (2 HIGH: menu-open transport-key leakage → isMenuOpen() guard; no focus ring → accent outline; + 4 med: route focus/announce, roving-tabindex+Home/End+Tab, drop Cmd+M collision, disarm; + 2 low: console-only transport gate, empty-themes placeholder), **3 accepted** (pre-existing focus-out deferral / revert-to-truth), 1 refuted.
- Re-verified: JS valid; tests 6/6; focus ring confirmed in a headless render.
- Decision: gate-review after CI.

## Risks and rollback

- Risk: breaking a pinned needle or the keymap. Mitigated: additive-only markup; the pin test + a keymap-preserved check run before push; the emergency footer stays outside the router. Rollback: git (one file).

## Pause and escalation conditions

- If routing needs multiple HTML documents (not in-page), that's an architecture change — escalate; MVP assumes in-page surfaces.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq321f-nav-screens-impl.md --require-complete`
- Validator result: PASS --require-complete (6/6)
- Independent verification result: adversarial Workflow wf_24fcee74-a1e — 11 confirmed → 8 fixed (2 HIGH), 3 accepted pre-existing, 1 refuted
- Terminal state: VERIFIED_COMPLETE (CI run 30190586979 green)
- ClickUp final evidence comment: posted on 86ajq321f
