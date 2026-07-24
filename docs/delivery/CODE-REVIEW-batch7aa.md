# Code Review — Batch 7aa (display enumeration/assignment + identify + outputs panel)

- **Scope reviewed:** physical-display enumeration with persisted per-output assignment (schema v5), the identify overlay (host key + wire command), the console OUTPUTS panel, RBAC `ConfigureOutputs` (Operator-only), and the outputs wire surface.
- **Method:** independent multi-lens adversarial review via the Workflow tool (run `wf_5b9ebabf-34e`, 15 agents; first attempt aborted on session limits and was rerun cleanly): 3 finder lenses (window/monitor lifecycle · wire/RBAC coherence · panel runtime) → per-finding adversarial verification, including winit platform-source checks (macOS/Windows monitor naming). No self-approval.
- **Raised → confirmed → unique:** **11 confirmed → 7 unique (A–G)** · 1 refuted.

## Findings and dispositions (all fixed)

| # | Sev | Defect | Fix |
|---|-----|--------|-----|
| A | high | `display_key` (`name\|WxH`) **collides for identical monitors** — the classic two-identical-projectors venue became unassignable (both roles resolve to the first match; the picker options were indistinguishable); the verifier confirmed macOS names same-model monitors identically in winit source | position-ordered ordinal keys (`…#1`/`…#2`, left-to-right — stable across re-enumeration) via a pure, unit-tested `display_keys()`; picker names get the same suffix |
| B | high | Assignment **persisted before checking the display exists**, and a stale key then called `set_fullscreen(None)` — a bad pick could yank the live audience output to windowed mid-service AND overwrite the working venue profile | validate against live monitors first; a missing display is ignored with a report — window and saved profile untouched; the controller additionally denies keys not in the advertised display list |
| C | med | Output status was a **one-shot snapshot** read synchronously after `set_fullscreen` (fullscreen moves land async) and never refreshed on move/resize — the panel showed the old monitor/size indefinitely | status republishes on `Resized`/`Moved` (where the truth actually arrives) from a cached assignment table |
| D | low | Identify frames cached at activation size, never invalidated on resize | cache cleared on `Resized` |
| E | med | A failed/denied assignment gave **no feedback** and left the select showing a false state that could not be retried | controller denies unknown keys (client-visible); the picker snaps back to the persisted truth and stays re-selectable |
| F | high | The outputs rebuild (`innerHTML = ""`) could **yank an open picker**; focus fell to `<body>`, so the operator's next `Enter` fired **GO LIVE** | rebuilds defer while focus is inside the panel and flush on focus-out |
| G | low | The picker never reflected the current assignment; the Identify button was a silent no-op with no outputs | `assigned_key` on the wire (skip-if-none; fixture updated) drives the selected option; Identify disabled when no outputs exist |

## Verification after remediation

- `cargo test --workspace --features selahcue-lan/server`: **252 passed** (10 new this batch: 2 key-derivation, 2 output-repo, identify lifecycle, assignment bounds + validation, wire E2E incl. Producer denial, serialize fixtures). Clippy `-D warnings` clean; operator crate clean; Flutter **19**.
- Wire E2E: Operator sees injected output status over TLS, identifies (armed → started on tick), assigns (pending drained); Producer's identify/assign are RBAC-denied.
- v2 fixtures byte-identical (skip-if-empty/none fields); the new outputs surface + both commands pinned serialize-side.

## Residual notes

- **On-device acceptance pending**: the story's 2+-display walk (windows opening on assigned displays, identify numbers on each) needs the user's multi-monitor Mac — headless CI cannot exercise winit monitor placement.
- Hotplug/monitor-change events, per-output resolution config, venue profiles beyond the single table, and per-picker-row identify remain tracked scope (Outputs epic).
- Physically swapping cables between two identical projectors is indistinguishable to software (documented in `display_keys`).
