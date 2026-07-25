# Code Review — Batch 7am (emergency-controls closeout + per-layer deferral)

- **Scope:** story `86ajp0awx` (Emergency clear/blackout + per-layer clearing, **urgent**) — closeout. Blackout, clear-all, the canonical keybindings (`keymap.rs`: `B`, `Esc·Esc`, `Backspace`=`ClearLayer`, arrows/Space/Enter) and always-on emergency chrome were delivered in earlier batches (7o/7p/7w). This batch **verifies/hardens** them against the story's acceptance and **defers per-layer clearing**.
- **Owner-approved scoping decision:** per-layer clearing cannot be meaningfully implemented on the current architecture — the live output is a **single `Slide`** (`Presenter.live_slide: Option<Slide>`), with no independently-addressable persistent layers, so "clear the current layer" == "clear all". Real per-layer clearing needs the R2 multi-layer/overlay model (no overlay/lower-third producers exist yet). **Split into new story `86ajpy59e`** under the R2 · Media & Output Expansion epic; `ClearLayer` (Backspace) keeps aliasing to Clear-all until then.
- **Method:** independent adversarial review via the Workflow tool (run `wf_4dd40dc7-881`, 7 agents; 2 lenses — test-validity, closeout-soundness — each finding verified to refute). No self-approval.
- **Raised → confirmed → unique:** **3 confirmed → 2 unique (both low, in the new tests) fixed** · 2 refuted. The **closeout-soundness lens confirmed the deferral is sound** (single-slide model verified; deferral comments consistent; every other acceptance criterion covered by code+tests).

## What this batch delivered (verification of the already-shipped controls)

| Acceptance criterion | Evidence |
|---|---|
| Keybindings match UX-CANONICAL exactly | `test_keymap.rs` (Rust contract, 8 tests) **+ new** webview mirror test pinning the JS keymap in `index.html` to the canonical map |
| Emergency keys fire even over a dialog (modal-pierce) | **new** test asserts the `Ctrl/Cmd+Shift+B` / `+Period` chords are matched **before** the input-focus early-return (structural ordering), capture-phase |
| Blackout/clear act <200ms with network disabled | **new** `test_controller.rs` test: `Blackout`/`Clear` resolve to `Ack` on the in-process presenter (no LAN on the desktop emergency path) and take effect (live darkens / live item removed) well inside 200ms (~1000× margin — a locality+latency sanity check, not a timing race) |
| Always-on emergency chrome, un-blackout restores | already pinned by the token-audit test (`id="emergency"`, BLACKOUT/CLEAR ALL) + `Presenter::blackout` retains the slide |

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | low | The webview keymap test claimed "all canonical bindings present" but didn't pin **Space→Next** (`case " ":`), so deleting the Space fall-through would leave the test green | added `"case \" \":"` to the pinned needles |
| B | low | The capture-phase check `html.contains("true // capture")` was **coupled to the source comment** — a reworded comment would false-fail while a benign refactor could slip through | replaced with a **structural** assertion (`"},\n        true"` — the capture arg immediately after the handler body closes), tied to the listener shape not the comment |

## Refuted (correctly)

- "Both new tests are real / non-vacuous / non-flaky" — affirmed as a non-defect.
- "<200ms is verified only for the in-process controller, not the LAN path" — refuted: the story's controls are the **operator's** (desktop, in-process); the mobile LAN path is a different surface, out of this story's scope.

## Verification after remediation

- `cargo test --workspace`: **268 passed** (+2: the webview keybinding/modal-pierce contract test and the blackout/clear offline-latency test). `cargo clippy` clean.
- No production behaviour changed (comment-only source edits + tests).

## Residual / deferred

- **Per-layer clearing → `86ajpy59e`** (R2), blocked on the multi-layer output model. `ClearLayer` intentionally aliases to Clear-all until then (documented in `keymap.rs`, `main.rs`, `index.html`).
- On-device QA of the emergency controls (offline blackout/clear, chords over a dialog) posted on `86ajp0awx`.
