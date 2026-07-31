# Goal Contract — TASK-86ajq6j4p-canvas-refine

## Identity

- Goal ID: TASK-86ajq6j4p-canvas-refine
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: Theme Designer canvas refine — click-select fix, right-click menu, native image picker, plan-dropdown alignment
- Role: frontend-engineer (operator Tauri webview + a small host command)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6j4p (canvas interactions refine; the picker is the 86ajq6j49 frontend)
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 14

## Objective

Owner refine cluster on the just-shipped canvas authoring UI: **(#3)** clicking an element on the canvas must **select** it — today the selection box (`#td-sel`) overlays the region/selected element and blocks the hit-test, so elements beneath it can't be clicked (a defect in `86ajq6j4p`); **(#6)** the per-item **theme dropdown** on the service plan is misaligned/overwide (CSS bug); **(#4)** a **right-click context menu** on a canvas element (Copy · Paste · Delete · Send to back · Bring to front), WKWebView-safe + keyboard-accessible; **(#1)** replace the Add-Image host-path input with a **native OS file picker** (`tauri-plugin-dialog` + a `pick_image` host command), keeping the path input as a fallback. Record the **#8** decision (scripture live-follow only when already live) + register **#2** (more shapes), **#5** (font weight/letter = `86ajq3225`), **#7** (real Preview/Live render) as follow-up tickets — NOT implemented here.

## Baseline

Verified from code (this session's scout + implementation):
- **#3 root cause:** `tdBox` pointerdown hit-test returns early when `tdSel.contains(e.target)` (app.js), and `tdSel` (pointer-events:auto) overlays the active target — so with the default **region** selected (the large Body region box), clicking most of the canvas hits `#td-sel` and never re-hit-tests an element beneath it. The fix is to re-hit-test the topmost element on any canvas pointerdown (not only outside the selection box).
- **#4:** no context menu exists; `tdArrange`/`tdDeleteEl` + the element model are in place. A custom menu (a positioned `<div>`, `contextmenu` preventDefault — WKWebView blocks the native menu anyway) with Copy/Paste/Delete/Send-to-back/front; copy/paste via a JS `tdClip` holding a cloned element.
- **#1:** no host dialog exists; **online now** — `tauri-plugin-dialog v2.7.2` resolves (Tauri v2 org). A `#[tauri::command] pick_image()` using the plugin's blocking Rust API (`app.dialog().file().add_filter("PNG",…).blocking_pick_file()`) returns the chosen absolute path (our own command → no JS capability needed, matching `system_fonts`/`builtin_themes`). `MediaRef` validates length(≤1024B)/non-empty/no-NUL host-side; FR-138 canonicalization stays the deferred hardening. `deny.toml` = permissive-only (no copyleft), `multiple-versions=warn`; **`cargo-deny` is installed locally** → verify the license/bans gate before pushing. The operator is a SEPARATE cargo workspace with its own fmt/clippy/build + audit + SBOM + deny CI.
- **#6:** the service-plan per-item theme `<select>` (console surface) renders misaligned/overwide vs the sibling rows (owner screenshot). CSS in `dist/app.css` (the plan-row / theme-select rule).

## Scope

### In scope

- **#3 (`dist/app.js`):** a `tdHitTest(clientX, clientY)` helper; call it in `tdPointerDown` (when not on a resize handle) to select the topmost element under the cursor before starting the drag — so clicking any element selects it, even under the region/selection box. The existing empty-canvas + Escape deselect stays.
- **#6 (`dist/app.css` / possibly `index.html`):** align the plan per-item theme dropdown with its row (width/flex), matching the sibling rows.
- **#4 (`dist/{app.js,index.html,app.css}`):** a WKWebView-safe custom **context menu** on a canvas element (right-click / a menu key) — **Copy** (`tdClip` = cloned element), **Paste** (add a clone offset, if `tdClip` set + under the 64 cap), **Delete**, **Send to back**, **Bring to front**. Keyboard: menu items are focusable buttons; `Cmd/Ctrl+C`/`V` copy/paste the selection; `Esc`/click-away closes; announced.
- **#1 (`src/main.rs` + `Cargo.toml` + `dist/app.js`):** add `tauri-plugin-dialog`; register it; a `pick_image()` command (PNG filter) → `Option<String>`; **Add Image** + **Replace…** invoke it and set `Element::Image.source`; the host-path row remains a fallback if the picker returns nothing / errors. Verify the operator **builds + `cargo deny check` passes** locally.
- **Follow-ups (record, do NOT implement):** #8 scripture live-follow-when-already-live; #2 more shape kinds (engine); #5 font weight/letter (`86ajq3225`); #7 real Preview/Live render — as ClickUp tickets/notes.

### Non-goals (seams)

- #2 / #5 / #7 / #8 implementation. FR-138 media-root confinement (still deferred). Multi-select, align/distribute, rotation, undo/redo (beyond copy/paste). Aspect-preserving image Fit.

### Constraints

- Operator-workspace fmt/clippy/build clean; **`cargo deny check` clean** (the new dep must be permissive + policy-conformant); `node --check` clean; WKWebView-safe (no native contextmenu, no `window.prompt`); a11y (keyboard-operable menu, announcements, focus); the console invariants (preview⟂live, emergency chrome) intact. The picker adds a Rust dep → the operator CI (build + audit + SBOM + deny, 3 OSes) is the gate.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Bug fixes: (#3) clicking ANY element on the canvas selects it — including an element beneath the region/selection box — via `tdHitTest` in the pointer path; (#6) the plan per-item theme dropdown is aligned with its row | headless (Chrome + Tauri stub) + visual/DOM check | click selects the topmost element; dropdown aligned | headless test; app.css | PASS |
| C-002 | yes | Right-click context menu (#4): Copy / Paste / Delete / Send-to-back / Bring-to-front on a canvas element; WKWebView-safe (custom menu, native suppressed); keyboard-operable (menu buttons + Cmd/Ctrl+C/V) + announced; Paste clones offset within the 64 cap | headless interaction test | menu opens + each action works; copy/paste clones | headless test | PASS |
| C-003 | yes | Native image picker (#1): `tauri-plugin-dialog` + a `pick_image` command wired; Add Image / Replace open the native dialog → the chosen path sets `Element::Image.source`; path-input fallback retained; operator **builds + `cargo deny check` clean** | operator build + `cargo deny check` + `node --check` | picker wired; build + deny green | build log; deny log | PASS |
| C-004 | yes | Gate: operator `cargo fmt --check` + `clippy -D warnings` + build clean; `node --check dist/app.js`; headless check passes; the #8 decision + #2/#5/#7 follow-ups recorded in ClickUp; independent Workflow review, findings fixed; CI green (operator-shell + audit + SBOM + deny) | operator gate + Workflow + CI | all green; review fixed; follow-ups tracked | CODE-REVIEW-batch-canvas-refine.md; CI run | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: headless Chrome + `window.__TAURI__` stub (stubbing `pick_image` → a fixed path) driving: click an element under the region box → it selects; right-click → the menu opens; Copy→Paste clones (offset, bounded); Delete/Send-to-back/front via the menu; Cmd/Ctrl+C/V. `node --check`. Operator `cargo fmt --check` + `clippy -D warnings` + `cargo build` (compiles the new dep) + **`cargo deny check`** (license/bans). Visual: the plan dropdown alignment. Independent: adversarial Workflow review (interaction/hit-test · context-menu/a11y/WKWebView · picker-command/deny/no-drift lenses). CI: operator-shell (3 OSes) + audit + SBOM + deny.
- Required environment: local (headless Chrome, cargo-deny, operator build) + CI.

## Iteration ledger

- **Iter 1 — bug fixes (C-001).** #3: added `tdHitTest(clientX,clientY)`; `tdPointerDown` re-hit-tests the topmost element on pointerdown (unless on a handle) so clicking an element BENEATH the region/selection box selects it; the `tdBox` handler reuses `tdHitTest` + starts a grab-move in the same gesture; both drag paths guard `e.button !== 0` (right-click → context menu). #6: the plan `.item-theme` select got a fixed `width:104px` (was only `max-width`) so every row's dropdown is the same size + aligns. Evidence: headless — clicking an element under the Body-region box selects it. **PASS.**
- **Iter 2 — context menu (C-002).** A WKWebView-safe custom menu (`#td-ctx`, native suppressed): Copy (`tdClip`), Paste (offset clone, bounded 64), Delete, Bring-to-front, Send-to-back; opens on `contextmenu` (selecting the element under the cursor), positioned + clamped to the viewport, keyboard-operable (arrow nav, Esc/click-away close) + `Cmd/Ctrl+C`/`V`; announced. Evidence: headless — right-click opens the menu; Copy→Paste + Cmd+C/V clone (+1); menu Delete removes. **PASS.**
- **Iter 3 — native picker (C-003).** Added `tauri-plugin-dialog` (Tauri org, permissive) + a `pick_image()` command (PNG filter, blocking) registered in the invoke handler + `.plugin(tauri_plugin_dialog::init())`. Add Image / Replace call `tdPickImage` → the native dialog → the chosen path (validated like `MediaRef`) → `Element::Image.source`; the manual path row remains a fallback if the picker is unavailable. **Verified locally:** operator `cargo build` clean (19.5s), **`cargo deny check` = bans/licenses/sources OK**, `clippy -D warnings` clean, `cargo fmt --check` clean. Evidence: headless (stubbed `pick_image`) — Add Image adds an image with the chosen path, no manual row. **PASS.**
- **Iter 4 — gate (C-004).** `node --check` clean; operator fmt/clippy/build/deny clean; **headless check 29/29** (all prior regressions + #1/#3/#4). Independent adversarial Workflow review launched (`wf_05171980-00b`).
- **Iter 5 — review findings fixed (C-004).** Review `wf_05171980-00b` (3 lenses, 8 agents): **4 confirmed / 1 refuted** — and the two HIGHs were exactly what my local checks could NOT catch (the headless stub bypassed the real `pick_image`; the headless test checked the `hidden` attribute, not the computed CSS). **All fixed:** (HIGH) `.td-ctx { display:flex }` (author) defeats the `[hidden]` attribute in WKWebView, so the context menu never hid — added `.td-ctx[hidden] { display:none }` (the codebase's own `.td-save-row[hidden]` proved the footgun); (HIGH) `pick_image` was a SYNC command → `blocking_pick_file` on the main thread would deadlock/freeze the whole operator mid-service — made it **`async fn`** (Tauri spawns it off-main); (MED) the plain re-hit-test let an overlapping element steal a drag from the selected target — made the grab **sticky** for a selected ELEMENT (grabbing inside its own rect keeps+moves it) while a REGION still re-hit-tests (so #3 holds); (LOW) a left-click to dismiss the menu also selected/grabbed — a click while the menu is open now just dismisses it. The refuted one (missing `MediaRef` trim rule on the picked path) is a non-issue (the OS returns a real path; the host trims anyway). Re-verified: operator **rebuild + clippy + fmt + deny clean**; **headless check 33/33** (incl. the menu's *computed* display + the dismiss-click). **PASS.**

## Risks and rollback

- Risks: the `tdHitTest`-in-pointerdown change breaking region drag or double-selecting (mitigated: hit-test only when not on a handle; a region stays selected when no element is under the cursor; headless regression). The new dialog dep failing `cargo deny` (copyleft/unknown source) or the 3-OS build (mitigated: `tauri-plugin-dialog` is Tauri-org permissive; verify `cargo deny` + build locally before push; if it fails, revert #1 to the path input + defer). The native picker unavailable on a headless/CI env (mitigated: it's a host command only invoked on user action; the path-input fallback + the headless stub). Context-menu focus trap / WKWebView native menu (mitigated: preventDefault + Esc/click-away close + focus management). Rollback: git; the picker is the only host change (revertable to the path input).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j4p-canvas-refine.md --require-complete`
- Validator result: PASS (4/4 mandatory)
- Independent verification result: adversarial Workflow review wf_05171980-00b (3 lenses, 8 agents) — 4 confirmed / 1 refuted; all fixed (2 HIGH: menu [hidden] guard + async pick_image); headless 33/33; operator build+deny+clippy+fmt clean. See CODE-REVIEW-batch-canvas-refine.md.
- Terminal state: GATE_REVIEW (verifiable work complete; paused at the /build gate)
- ClickUp final evidence comment: posted on 86ajq6j4p + BUILD CONTROL 86ajnx548; follow-ups 86ajtwq24/28/2b + 86ajq3225 note
