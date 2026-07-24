# Code Review — Batch 7w (design system + canonical keybindings + emergency chrome)

- **Scope reviewed:** canonical token module (`selahcue-present::tokens` + WCAG audit + cross-surface pinning); canonical keymap (`selahcue_app::keymap` + contract tests); desktop key rewiring (double-Esc clear-all, Esc-quit removed); operator webview (tokens, JS key mirror, `#emergency` footer, reduced-motion); stage-display retokenization; Flutter tokens + retokenized views.
- **Method:** independent multi-lens adversarial review via the Workflow tool (run `wf_f4a4b8dc-747`, 40 agents): 5 finder lenses (spec-fidelity vs UX-CANONICAL §1/§3/§4/§5 · keymap/state-machine correctness · webview runtime · a11y/token-audit soundness · cross-surface residue) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **33 confirmed → 14 unique defects** (the dead clear-all chord was independently found by all 5 lenses) · **2 refuted** (OS-level global hotkeys and timer-warn colour-only labelling — out of the story's scope, and the code does not claim them).

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | `Ctrl/Cmd+Shift+.` clear-all fallback chord was **dead code** — with Shift held, `e.key` is `">"`, never `"."` (all 5 lenses found this) | chords matched by **physical key** (`e.code === "Period"` / `"KeyB"`) |
| B | high | Key **auto-repeat** unfiltered on both surfaces — a held `Esc` completes the double-tap (~300ms repeat ≪ 1000ms window), a held `B` strobes blackout | winit `repeat` field and JS `e.repeat` both return early |
| C | high | Focused-button hijack: after any click, `Enter`/`Space` fired **Go Live/Next** instead of activating the focused button (emergency buttons not keyboard-operable) | `BUTTON` targets exempt from Enter/Space; mouse-clicked buttons blur (`e.detail > 0` — keyboard activation keeps focus) |
| D | high | Stale blackout state while an editor was open: `render()` early-returned before syncing `dataset.on`, so the toggle could **re-assert blackout instead of lifting it** | chrome sync split into `syncChrome()` that runs on every view, before the editor guard |
| E | med | `Esc`, `P`/`Y`/`N` (or a chord), `Esc` completed an **accidental Clear-all** — host-handled keys bypassed the disarm contract | `Keymap::disarm()` called on P/Y/N; JS chord paths + in-field typing disarm; contract test added |
| F | med | `Backspace` was wired to **clear the staged Preview** — the §1 action is "clear current **live** layer" (opposite surface) | `clear_staged` removed; `ClearLayer` → `Command::Clear` (≡ clear-all while live is single-layer; distinct action kept for 86ajp0awx) |
| G | med | Key-hint text on token-filled buttons failed AA (2.05:1 on GO LIVE, 2.85:1 on engaged BLACKOUT/armed CLEAR ALL) — a pairing the token audit did not cover | white hint text on filled buttons (5.3:1 / 7.2:1); rule pinned by the webview needle test |
| H | med | Pin-test needle `"LIVE"` was satisfied by the "GO LIVE" button — the actual badge labels were unpinned | needles are the exact `badge("live", "LIVE")` / `badge("preview", "PREVIEW")` calls + `aria-pressed` + the hint-contrast rule |
| I | med | Webview omitted `Backspace` while claiming to mirror the canonical map | `Backspace` case added (→ clear; same single-layer note) |
| J | low | Blackout engaged state was **colour-only** on the footer button (label toggle regressed, no `aria-pressed`) | "ON" text label + `aria-pressed` synced every view |
| K | low | Armed CLEAR ALL hint never expired — stale red "armed" state | 1000ms expiry timer aligned with the double-tap window |
| L | low | Typing inside a text field never disarmed a pending double-Esc (guard ran before the disarm) | disarm moved above the tag guard |
| M | low | Flutter ignored the OS reduced-motion setting (story scope) | `MediaQuery.disableAnimations` → no-op page transitions app-wide |
| N | low | Mobile Material scheme still seeded from the superseded blue `#3B82F6` | `DesignTokens.accentBrand #5b6bd6` added and used |

Doc-level (from the one-meaning-per-colour finding): the sanctioned colour-family
semantics (green = safe/positive incl. timer-on-track; red = on-air/alarm incl.
TIME UP) are now stated precisely in `tokens.rs` and `DESIGN-TOKENS.md` instead of
an over-broad "never reused" claim.

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **232 passed, 0 failed** (12 new this batch: 7 keymap contract incl. disarm + bounded-state, 5 token audit/pinning).
- `cargo clippy -D warnings` clean; `cargo fmt --check` clean; operator crate clean.
- `flutter analyze`: no issues; `flutter test`: **16 passed** (4 new token-audit tests).
- Contrast audited in tests on both stacks (WCAG relative-luminance math, ≥4.5:1 on every rendered pairing: white-on-fills, inks on `bg/base`/`bg/panel`/stage background, primary text).

## Residual notes

- OS-level **global** hotkey registration (chords that fire when SelahCue is unfocused) is deliberately not in this batch — tracked with the app-shell story (`86ajp5vp6` adjacency), recorded in `DESIGN-TOKENS.md`.
- The command palette (`Ctrl/Cmd+K`, FR-015) and per-layer clearing (`Backspace`'s full semantics, `86ajp0awx`) are separate planned stories.
- The full Figma console layout (three-panel preview/live, outputs panel, transcript) is the console build-out batch; this story delivered the system underneath it.
