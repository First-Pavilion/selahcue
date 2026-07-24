# Code Review — Batch 7z (operator console QA polish: keyboard focus + plan rows)

- **Scope reviewed:** one file (`crates/selahcue-operator/dist/index.html`) fixing two owner-QA bugs: `86ajphu2h` (canonical keys dead when the operator window has focus — WKWebView delivers key events only once an element in the document has focus) and `86ajphtyh` (cramped plan rows).
- **Fixes under review:** body focus management (`tabIndex=-1` + `grabFocus()` on load / window-focus / focusout) + the keydown listener moved to the capture phase; two-line Figma row layout (ellipsis title over muted kind) with hover/focus-revealed edit tools.
- **Method:** independent adversarial review via the Workflow tool (run `wf_b28ed65b-931`, 4 agents, 2 lenses: focus machinery · row/interaction regression) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **2 confirmed → 1 unique** (both lenses independently found the same defect; 0 refuted).

## Finding and disposition (fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | The hover-reveal used `display:none`, which **removes the tool buttons from the tab order** — the `:focus-within` reveal was circular (focus can never enter a row whose only focusable elements are unfocusable), so keyboard-only operators lost rename/reorder/delete entirely (a regression vs the always-visible buttons), and an **armed delete-confirm could go invisible** when the pointer left the row mid-window | tools hidden with `opacity: 0` + `pointer-events: none` (buttons stay tabbable; Tab into a row triggers `:focus-within` → visible); the armed confirm pins the tools open via a `.confirming` class for its 3s window |

## Verification after remediation

- Operator crate `cargo check` clean; webview JS syntax-checked (`node --check`); pin tests green (needles unchanged).
- 7w/7x/7y invariants re-checked by the review: capture-phase listener still honours the INPUT/BUTTON guards (capture fires on `window` before target handlers, but the guard logic is inside the handler — the rename editor's Enter/Escape are unaffected because the tag guard returns first), chords, repeat filter, disarm rules, blur-on-mouse-click all preserved.

## Residual notes

- **The keyboard-focus fix needs on-device confirmation** (`86ajphu2h` stays the user's re-QA item): the root cause — no focused element before the first click in WKWebView — is addressed with standard mitigations (focusable body, focus re-grab, capture phase), but headless CI cannot exercise macOS first-responder behaviour.
- Row layout targets the Figma console item style; duration/slide-count metadata on the second line arrives when the plan model carries it.
