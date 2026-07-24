# Code Review — Batch 7ac (timer manual entry + live add/subtract)

- **Scope reviewed:** `Timer::adjust` (core), the `AdjustTimer` wire command (RBAC = the existing Timer permission), the controller arm with crash-recovery persistence, and the console + mobile controls (minutes entry, ±1:00 live adjustment).
- **Method:** independent adversarial review via the Workflow tool (run `wf_e358648f-a84`, 8 agents; 2 lenses: timer semantics/persistence · client wiring) → per-finding adversarial verification. No self-approval.
- **Raised → confirmed → unique:** **6 confirmed → 4 unique (A–D)** · 0 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | med | A wire-legal absurd delta could push the live total past **u32::MAX seconds**, and the recovery snapshot's cast **wraps modulo 2³²** — pre-crash and post-restore timers diverge (the acceptance's "survives crash/restore" broken for edge inputs) | `Timer::adjust` clamps the target to `0..=u32::MAX` seconds — the same domain `StartTimer` and the snapshot use (test: `+i64::MAX` lands exactly at the cap); the legacy `add_time`/`subtract_time` helpers now delegate to `adjust` so every mutation path shares the clamp |
| B | low | The minutes input's `max="999"` was decorative (typed values passed through), oversized values either started absurd timers or **silently no-op'd** on u32 overflow; decimals/e-notation mangled | both surfaces sanitize (finite → floor → clamp 1..=999) before sending |
| C | low | The stand-alone **demo shell never ticks** the controller, so the new timer controls (and the readout) were dead in Local mode | `OperatorShell` ticks on every act/view (the remote path's host ticks per frame; an extra tick is harmless) |
| D | low | Tapping ±1:00 in the 1s poll gap after the timer was stopped elsewhere raised a misleading **"Not allowed"** banner on mobile (it's a state race, not permissions) | `bad_request` denials refresh silently — the fresh view already shows the truth; real permission denials still surface |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **256 passed** (+3 this batch: core adjust semantics incl. the clamp, controller adjust + crash-recovery persistence + idle denial, wire E2E extending a running countdown). Clippy `-D warnings` clean; operator crate clean; Flutter **20** (analyze clean).
- Acceptance math verified in tests: 5:00 started, +1:00 at 1:20 elapsed → remaining 4:40; snapshot carries total 360s and the restored timer matches; −9999s lands in TIME UP without underflow.
- Wire: `adjust_timer` fixture-pinned (i64, negative case); Dart command shape tested; RBAC inherits the Timer permission (Producer may adjust — consistent with StartTimer).

## Residual notes

- Pause/resume exists in the core but has no UI story yet; per-output timer visibility and more presets remain Timers-epic scope (`86ajp07nr`).
- Owner request ticketed this session: search-result snippets with match highlighting (`86ajpv0ub`).
