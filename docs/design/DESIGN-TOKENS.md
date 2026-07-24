# SelahCue — Design Tokens (implementation record)

Status: implemented in batch 7w (story `86ajp0b3d`) · Source of truth: [UX-CANONICAL.md](UX-CANONICAL.md) §4 (semantics + fills) + the Figma design system (file `SYQn5hFY8YVQKm3c6rw0eJ`, variables read 2026-07-24).

## Where the tokens live (change together — pinned by tests)

| Surface | File | Pinned by |
|---|---|---|
| Rust (canonical source) | `implementation/desktop/crates/selahcue-present/src/tokens.rs` | `selahcue-present/tests/test_tokens.rs` (WCAG audit + §4 exactness) |
| Operator webview | `implementation/desktop/crates/selahcue-operator/dist/index.html` (`:root` CSS variables) | `test_tokens.rs::operator_webview_is_pinned_to_the_canonical_tokens` |
| Flutter controller | `implementation/mobile/selahcue_controller/lib/models/design_tokens.dart` | `test_tokens.rs::mobile_tokens_are_pinned_to_the_canonical_tokens` + `test/models/design_tokens_test.dart` |
| Stage/confidence display | `StageTheme::dark()` (uses the token inks directly) | `test_tokens.rs::stage_display_uses_the_semantic_inks` |

## The reconciliation: canonical fills vs Figma inks

UX-CANONICAL §4 pins one deep hex per meaning; the Figma design system carries brighter
`accent/*` variables for the same meanings. Both are kept, with distinct roles:

- **fill** — the UX-CANONICAL hex, exact. Used as chip/badge/panel-header **backgrounds
  carrying white text** (audited ≥4.5:1 as white-on-fill).
- **ink** — the Figma `accent/*` value, same hue family. Used as **text/glyph colour on
  the dark surfaces** (audited ≥4.5:1 against `bg/base`, `bg/panel`, and the stage
  background).

One meaning per colour **family** everywhere: green = safe/positive (staged content, a
timer on track — never "on air"), red = on-air/alarm (live content, TIME UP), amber =
warning/threshold. Staged and warning are never the same colour; LIVE/PREVIEW always
carry a text label (WCAG 1.4.1), the blackout button announces its engaged state
(`aria-pressed` + an "ON" label), and key hints on token-filled buttons switch to
white to hold AA.

| Token | Meaning | fill (§4, exact) | ink (Figma) |
|---|---|---|---|
| `preview` | Preview / staged (not on air) | `#0f7b6c` | `#2bb673` (`accent/preview`) |
| `live` | Live / Program (on air) | `#a3283a` | `#ef4444` (`accent/live`) |
| `warn` | Warning / threshold | `#9a5b00` | `#f2b53c` (`accent/warn`) |
| `neutral` | Idle / inactive | `#2b323d` | `#9aa4b2` (`text/muted`) |

Surfaces (Figma): `bg/base #0e1116` · `bg/panel #171b22` · `bg/elevated #1e232c` ·
`border #2b323d` · `text/primary #eef1f6` · `text/muted #9aa4b2` · `accent/brand #5b6bd6`.

## Canonical keybindings (implemented)

`selahcue_app::keymap` is the contract-tested state machine (UX-CANONICAL §1); the
output window consumes it natively and the operator webview mirrors it in JS
(double-`Esc` window: 1000 ms in both; OS key auto-repeat filtered on both — a held
`Esc` never completes the double-tap). `Esc` **no longer quits** the output window —
double-`Esc` is Clear-all; quit via the window close button. Any intervening key —
including the host-local pairing keys `P`/`Y`/`N` and the emergency chords — disarms
a pending first `Esc`. `Backspace` (clear current layer) equals Clear-all while the
live output is single-layer; the actions stay distinct so bindings are stable when
per-layer clearing lands (`86ajp0awx`). Emergency chords (`Ctrl/Cmd+Shift+B`,
`Ctrl/Cmd+Shift+.` — matched by physical key code, so Shift's character translation
cannot kill them) pierce text fields/dialogs **in-app**; OS-level global registration
ships with the app-shell story (`86ajp5vp6` adjacency — see the story's scope note).

## Emergency chrome (implemented)

The operator shell's footer (`#emergency`) matches the Figma console design: BLACKOUT
(`B`) + CLEAR ALL (`Esc Esc`) with "Always reachable · pierces any dialog", present and
operable in every state including while a row is being edited (UX-CANONICAL §3).

## Reduced motion / seizure safety

The webview honours `prefers-reduced-motion` (all transitions/animations off). The
TIME UP state is solid inverted by default (§5) — no flashing anywhere yet, so the
ADR-0015 flash-rate analyzer remains scoped to the Timers epic (`86ajp07nr`).
