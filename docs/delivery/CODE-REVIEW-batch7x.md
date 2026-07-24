# Code Review — Batch 7x (operator console build-out per Figma)

- **Scope reviewed:** the operator webview restructured into the Figma console layout (file `SYQn5hFY8YVQKm3c6rw0eJ`, node 4:2) on the batch-7w design system: top bar (plan name, LIVE chip, clock), plan panel, labeled PREVIEW·STAGED / LIVE·ON AIR panels with GO LIVE between, SERVICE TIMER panel; pin-test extension.
- **Method:** independent adversarial review via the Workflow tool (run `wf_f9323e54-033`, 11 agents): 3 finder lenses (7w-invariant regression + stale references · console runtime · Figma fidelity + a11y) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **8 confirmed → 4 unique** (0 refuted). All 14 batch-7w fixes verified as preserved by the regression lens.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | The new PREVIEW/LIVE panels sat below the editor guard, so an emergency clear or Go Live landed while an inline editor / delete-confirm was open left the **on-air panel showing stale truth** (indefinitely, for an open editor) — the exact defect class 7w fixed for the blackout state, reintroduced on the flagship indicator | `setPanel` calls moved into `syncChrome()` — the panels sync on every view (they touch only static DOM, never the guarded plan rows) |
| B | low→med (3 lenses) | Prev/Next reduced to bare glyphs (`◀`/`▶`) with no accessible name — a screen-reader regression from 7w's labeled buttons | explicit `aria-label`s |
| C | low | Fixed 300px/250px grid columns clipped on narrow windows (no responsive floor) | `minmax()` columns, `min-width: 0` on grid children, 720px body floor with scroll |
| D | low | On-air changes were silent to assistive tech | `aria-live="polite"` on the live-panel surface (text changes only on real transitions) |

## Verification after remediation

- `cargo test --workspace`: **232 passed** (pin test extended with the console needles: panel labels, ids, blackout overlay text). Clippy `-D warnings` clean; operator crate clean; Flutter **16 passed**.
- 7w invariants re-verified after the fixes: physical-key chords, `e.repeat` filter, button blur + BUTTON exemption, disarm ordering, armed-hint expiry, `aria-pressed`, key-hint AA overrides — all present.

## Residual notes

- Slide **body** text in the panels arrives when `OperatorView` carries it (editor stories); panels show title + kind today.
- Outputs panel (`86ajpew0c`), scripture tab (`86ajpew05`), transcript (R3), timer +1:00/Pause (`86ajp07nr`), and the mobile console remain tracked elsewhere.
- Visual QA on the user's machine pending (`make operator` against a running output window).
