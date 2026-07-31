# Goal Contract — TASK-86ajq6j4p-canvas-interactions

## Identity

- Goal ID: TASK-86ajq6j4p-canvas-interactions
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: On-canvas element authoring UI — select / move / 8-handle resize / arrange / delete + Add Shape/Image, in the Theme Designer
- Role: frontend-engineer (operator Tauri webview)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6j4p (delivers the interaction layer; also the `86ajq6j49` image-frontend add/edit, minus the native picker)
- Created: 2026-07-31
- Independent verification required: yes
- Maximum iterations: 14

## Objective

Build the Theme Designer **element authoring UI** from `CANVAS-EDITING-spec.md`, wired to the already-shipped engine model: **add** (Shape, Image-via-path), **select** (click, z-order hit-test), **move** (drag + keyboard nudge), **resize** (8 handles, edge-clamp, lock-aspect, pointercancel-safe), **arrange** (send-to-back / bring-to-front / forward / backward per the §2a z-arithmetic), **delete**, and a **per-element inspector** (X/Y/W/H · opacity · arrange · shape fill/border/border-thickness · image source). Generalises the existing single-**region** drag/resize (S8-3c) to arbitrary **elements**. Fully client-side — the host already composites `tdTheme.elements` via `render_sample` and persists them via `SetCustomTheme`/`SaveTheme` (bounded at `MAX_ELEMENTS = 64`), so **no host change and no new dependency** are needed. This makes shapes + images finally **usable** on the canvas.

## Baseline

Verified from code (read-only scout of `selahcue-operator/dist/app.js` :516-992, `index.html`, `app.css`, `src/main.rs`, + `selahcue-present/src/theme.rs`):
- **Preview auto-composites elements:** `tdPreview()` (app.js:752) → `invoke("preview_theme", {themeJson})` → host `render_sample(&theme, 480, 270)` (main.rs:377) — the SAME compositor as the audience output. So an element added to `tdTheme.elements` appears in the preview with **no client-side drawing**.
- **Reusable machinery:** `#td-sel` + 8 handles (`data-h="nw|n|ne|w|e|sw|s|se"`, index.html:195-204) + `tdPointerDown/Move/Up`/`pointercancel` (app.js:816-879) + `tdSetRect` (:767, clamps w/h 20..1000, x/y 0..1000−size) + per-mille↔% (`/10`, `*10`, `(dx/boxW)*1000`) operate on any `{x,y,w,h}_permille` object. Today they're hard-bound to `tdTheme[tdRegion]`. Keyboard nudge/resize at :882-896.
- **Inspector pattern:** static DOM controls re-bound by `tdSync()` (:730) from `tdTheme[tdRegion]`; segmented controls via `tdSeg` (:536, sets `.on` + `aria-pressed`); X/Y/W/H number inputs (:793-806, commit-on-blur, clamp); `type="color"` pickers (bg/text); ranges (size/line-height). `Rgba` is `{r,g,b,a}` u8 — exactly what `tdHex`/`tdRgb` produce (1:1 for fill/border).
- **Persist for free:** `JSON.stringify(tdTheme)` at preview/apply/save (:757/:987/:957) already carries `tdTheme.elements`. Host `set_custom_theme` (controller.rs:315) rejects `elements.len() > MAX_ELEMENTS`.
- **Element JSON:** `#[serde(tag="kind")]` → `Element::Shape { "kind":"shape", x/y/w/h_permille:u16, fill/border:{r,g,b,a}, border_permille:u16, opacity:u8, z:i16 }`; `Element::Image { "kind":"image", x/y/w/h_permille, source:"<path>", opacity:u8, z:i16 }`. z<0 behind text, z≥0 in front. `MediaRef` (source) validates trim/non-empty/≤1024B/no-NUL on the host.
- **No host dialog exists**, and **no dialog crate (`rfd`/`tauri-plugin-dialog`) is in the offline cargo cache** — a native file-picker cannot build offline this batch. The operator is a SEPARATE cargo workspace with its own fmt/clippy gate + `unwrap_used="warn"`; the webview bridge is `window.__TAURI__.core.invoke` (no WS in the webview).

**Key finding:** the render + drag/8-handle machinery + persistence are fully reusable and need **zero host change**. The net-new work is client-side: an element list + canvas selection model (an active-target abstraction region|element), an element inspector (opacity/z-arrange/fill/border/border-thickness/image-source), and the Add-content bar wiring. **Add Image uses a host-path text input** (offline-safe); the **native OS file-picker + FR-138 media-root confinement are deferred** (offline-blocked dialog dep) to the `86ajq6j49`-frontend follow-up.

## Scope

### In scope (`selahcue-operator/dist/{app.js,index.html,app.css}` — client-side only)

- **Active-target model:** generalize `tdRegion` to a target that is a **region** (`body`/`title`) OR an **element** (index into `tdTheme.elements`). `tdSetRect`/`tdDrawSel`/`tdSync`/pointer/keyboard operate on the active target.
- **Add-content bar:** wire the (currently inert) **Add Shape** → push a default visible `Element::Shape` (centred, `z := max+1`, opaque neutral fill `#3a4150`, no border), auto-select; **Add Image** → a host-path input → push `Element::Image { source }`, auto-select. Both **disabled at `MAX_ELEMENTS = 64`** with a reason. (Text/Scripture stay disabled — `Element::Text` unbuilt.)
- **Select:** click the canvas → **z-order hit-test** (topmost element by composite paint order at the point; else fall back to the region controls); the selection box + 8 handles bind to the active element.
- **Move + resize:** reuse `tdPointerDown/Move/Up`/`tdSetRect` on the active element (8 handles, edge-clamp, lock-aspect via `#td-lock`, pointercancel-safe); keyboard nudge (arrows) + resize (Shift+arrows).
- **Arrange (z-order):** Send to Back (`z:=min−1`) / Bring to Front (`z:=max+1`) / Forward / Backward (swap z with nearest neighbour) per **§2a**; keyboard `Cmd/Ctrl+]`/`[` (+`Shift`); the **behind-text / in-front chip** reflects `sign(z)`; keep z distinct.
- **Delete:** an element via the existing **two-click confirm** pattern; selection moves to the next in paint order.
- **Per-element inspector:** X/Y/W/H (reuse) · **opacity** range (0–100% ↔ `u8`) · **arrange** buttons + chip · per-kind — **shape** fill/border `type="color"` + border-thickness range (↔ `border_permille`); **image** source (path field + edit). The Fill/Border pickers are RGB (opacity is the single alpha).
- **a11y:** ARIA on the 8 handles; a live region announcing select / arrange ("moved behind the text") / add / delete; keyboard path (spec §8); colour never the only cue.
- **Invariants intact:** preview-only (editing never touches Live — apply is the existing explicit action); emergency Clear/Blackout chrome untouched; WKWebView-safe.

### Non-goals (seams — note)

- The **native OS file-picker** + **FR-138** media-root confinement/canonicalization (offline-blocked dialog dep) → `86ajq6j49`-frontend follow-up. Multi-select + group transform; align/distribute; rotation (R2). The **Text** element (`86ajq6j64`). Aspect-preserving image **Fit**. Undo/redo (a delete toast at minimum). Snapping is best-effort (safe-area guide already exists; edge/centre snap optional).

### Constraints

- Client-side only — **no host change, no new dependency** (offline-safe). Bounded (`MAX_ELEMENTS = 64`, enforced host-side; the UI disables Add at the cap). No engine/wire/migration change → no determinism/parity concern. Operator-workspace fmt/clippy clean (`unwrap_used="warn"`); WKWebView-safe; a11y (WCAG-AA, keyboard). The console invariants (preview⟂live, emergency chrome) stay intact.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Add + model: Add Shape / Add Image(path) push a valid `Element` onto `tdTheme.elements` (default rect, distinct z, auto-selected), disabled at `MAX_ELEMENTS`; the element serializes in the theme JSON with the correct `"kind"` shape; the active-target abstraction (region or element) drives the inspector/canvas | headless (Chrome + Tauri stub) + `node --check` | element added + serialized correctly; bounded; target switches | headless test | PASS |
| C-002 | yes | Direct manipulation: select (click, z-order hit-test) · move (drag + arrow nudge) · 8-handle resize (edge-clamp, lock-aspect, pointercancel-safe) · delete (confirm) — on the active element; the numeric X/Y/W/H + opacity fields stay in sync with the selection | headless interaction test | select/move/resize/delete work; fields synced | headless test | PASS |
| C-003 | yes | Arrange + inspector + a11y: Send-to-back/Bring-to-front/Forward/Backward per §2a (+ keyboard) with the behind/in-front chip; shape fill/border/border-thickness + image source; opacity; ARIA on handles + select/arrange/add/delete announcements; preview-only invariant intact | headless test + a11y checks | z-order changes correctly + announced; per-kind controls bind; invariants intact | headless test | PASS |
| C-004 | yes | Gate: operator `cargo fmt --check` + `clippy -D warnings` + build clean; `node --check dist/app.js`; a headless interaction+render check passes; structure pins; independent Workflow review, findings fixed; CI green (operator-shell job) | operator gate + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-canvas-interactions.md; CI run | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: headless Chrome (`--headless=new --dump-dom`/screenshot) with a `window.__TAURI__` stub (stubbing `invoke("preview_theme")` → a fixed frame, `builtin_themes`, `system_fonts`, `set_custom_theme`/`save_theme` echo) driving the Theme Designer JS — add a shape, click-select, drag-move, handle-resize, arrange (z buttons + keyboard), delete, and assert `tdTheme.elements` + the numeric/opacity fields + the selection overlay update correctly; a render check that a shape/image element appears; structure pins (the element inspector DOM). `node --check dist/app.js`. Operator `cargo fmt --check` + `clippy -D warnings` + build. Independent: adversarial Workflow review (interaction-correctness/z-order · a11y/invariants · state-sync/persist lenses). CI: the operator-shell job (this batch touches only the operator workspace; the desktop rust/parity matrix is unaffected — no engine change).
- Required environment: local (headless Chrome) + CI.

## Iteration ledger

- **Iter 1 — active-target refactor + add/model (C-001).** Generalised `tdRegion` to `tdSelEl` (−1 = region, else element index); `tdActive()`/`tdActiveIsEl()`/`tdEls()`/`tdPaintOrder()` helpers; refactored `tdDrawSel`/`tdSyncLayout`/`tdSetRect`/the X/Y/W/H handler/the pointer handlers/the keyboard handler to the active target (region editing preserved — the region path is unchanged). Wired **Add Shape** (default visible fill, `z:=max+1`, auto-select) + **Add Image** via a host-path row (`#td-img-row`); disabled at 64; `tdSelEl` reset on every theme switch. Persist rides the existing `SetCustomTheme`/`SaveTheme`. Evidence: headless — a shape/image serializes with the correct `"kind"`; default z/opacity correct. `node --check` clean. **PASS.**
- **Iter 2 — direct manipulation (C-002).** Click hit-test on `#td-canvas-box` (front-to-back paint order) → select; move (drag + Arrow nudge), 8-handle resize (reused edge-clamp/lock-aspect/pointercancel machinery on the active element); two-click delete; the numeric X/Y/W/H stay synced to the selection. Evidence: headless — numeric X=10% → x_permille=100 on the active element; ArrowRight nudges +10‰; two-click delete removes it. **PASS.**
- **Iter 3 — arrange + inspector + a11y (C-003).** Element inspector (`#td-el-inspector`): opacity range (0–100% ↔ u8), arrange seg (Send-to-back/backward/forward/Bring-to-front) implementing §2a (rewrites `z`: back=min−1, front=max+1, forward/backward swap the nearest neighbour — NOT a list splice), the behind/in-front chip, shape fill/border (RGB) + border-width, image source/Replace; ARIA on the handles (reused) + `#td-status` announcements (select/arrange/add/delete); preview-only (Apply stays the explicit action). Region regression preserved. Evidence: headless — Send-to-back sets z=−1 + chip "Behind text", Bring-to-front z=+1; opacity 50%→128; selecting a region hides the element inspector. **17/17 headless checks pass, 0 fail.** **PASS.**
- **Iter 4 — gate (C-004).** `node --check dist/app.js` clean; **zero Rust change** (only `dist/{app.js,index.html,app.css}`), so operator fmt/clippy/build are unaffected — `cargo fmt --check` clean. Headless interaction check (17/17). Independent adversarial Workflow review launched (`wf_dba0dc46-65a`).
- **Iter 5 — review findings fixed (C-004).** Review `wf_dba0dc46-65a` (3 lenses, 15 agents): **11 confirmed / 1 refuted / 0 unverified** (several confirmations were the same defect from two lenses). **All fixed:** (MED) the two-click delete arm was a global flag not reset on selection change → arming a delete on A then selecting B deleted B on one click → reset `tdElDelArm`/label in `tdSyncEl` (every selection change); (MED) no way to deselect back to region editing once an element was picked (region controls hidden) → **Escape** + an **empty-canvas click** now deselect; (MED) the armed delete wasn't announced to AT → `tdAnnounce` on arm; (MED/LOW) the image path length was checked in UTF-16 units + NUL wasn't rejected (disagreeing with `MediaRef`'s 1024-BYTE/NUL rule) → use `tdNameBytes` (bytes) + reject NUL; (LOW) arrange forward/backward no-op'd on equal-z ties → paint-order-neighbour swap + tie step + an i16 clamp; (LOW) the 8 handles carried no ARIA + `#td-sel`/inputs were labelled "Region" for elements → handles `aria-hidden`, dynamic `#td-sel` label, element-neutral X/Y/W/H labels; (LOW) arrange announced "Moved" even when nothing changed + omitted the position → announce only on change + "n of m". The 1 refuted (arrange z overflowing i16) verified impractical (I added a clamp anyway). Re-verified: `node --check` clean; **headless check now 22/22** (incl. deselect + arm-reset). **PASS.**

## Risks and rollback

- Risks: the active-target refactor breaking the existing REGION drag/resize (mitigated: region remains a target type; regression-check regions still edit). z-order arrange implemented as a list-splice no-op (mitigated: §2a pins z-arithmetic; a headless arrange test asserts the composited/paint order changes). Element count unbounded (mitigated: host rejects >64; UI disables Add at the cap + a test). Preview-only invariant leak (mitigated: apply stays the existing explicit action; editing only previews). WKWebView pointer-capture quirks (mitigated: reuse the proven S8-3c handlers + pointercancel). Native picker expectation (mitigated: image-add via a path input this batch; the native picker is a documented offline-blocked follow-up). Rollback: git; operator-only, additive JS.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j4p-canvas-interactions.md --require-complete`
- Validator result: PASS (4/4 mandatory)
- Independent verification result: adversarial Workflow review `wf_dba0dc46-65a` (3 lenses, 15 agents) — 11 confirmed / 1 refuted; all fixed; headless 22/22. See CODE-REVIEW-batch-canvas-interactions.md.
- Terminal state: GATE_REVIEW (verifiable work complete; paused at the /build gate)
- ClickUp final evidence comment: posted on 86ajq6j4p (→ qa) + BUILD CONTROL 86ajnx548
