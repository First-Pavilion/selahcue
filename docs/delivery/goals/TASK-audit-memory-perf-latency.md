# Goal Contract — TASK-audit-memory-perf-latency

## Identity

- Goal ID: TASK-audit-memory-perf-latency
- Parent goal ID: BUILD-selahcue (Stage 7/8 quality)
- Title: Code audit — memory leaks · slow-loading views · scripture→output latency
- Role: qa-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited ~21h — follow-up tickets queued in the report)
- Created: 2026-07-31
- Independent verification required: yes (adversarially verify each HIGH before reporting)
- Maximum iterations: 10

## Objective

Owner-requested audit (read-only + measurement; NOT a feature batch): (1) find **memory leaks / unbounded growth** across the desktop Rust workspace + the operator webview against the project no-leak rule (every collection/cache/ring/listener bounded, with a bounded-memory test); flag **missing** bounded-memory tests. (2) Identify **slow-loading views** in the operator webview (heavy on-load/activation work). (3) **Measure** the scripture→output response time — the host-side `parse_one`+`verses_in`+`compose_slide`+`raster::render` latency for a representative verse — and account for the added webview→wire→host hops. Deliver an honest severity-ranked findings report under `docs/quality/` with file:line evidence + measured numbers + recommended fixes; queue follow-up tickets (ClickUp rate-limited). Do NOT change product code except the one timing test; do NOT touch the uncommitted font batch.

## Baseline

Verified from code + session context: the workspace has bounded-memory tests for several structures (engine glyph cache `RESET_EVERY`, `TranscriptLog`/`DetectionQueue` rings, `MAX_ELEMENTS`, the media decode cache). The operator webview polls the host every 1 s + debounces the console render. `compose_slide`+`raster::render` is a pure integer function (deterministic → timeable). This audit inventories ALL such structures + surfaces, not only the tested ones.

## Scope

### In scope

- **Memory audit:** enumerate every growing structure (Rust `Vec`/`HashMap`/ring/cache; webview arrays/DOM/listeners/timers) and classify **bounded (with test) / bounded (no test) / UNBOUNDED**. Cover: engine glyph+shape cache + `RESET_EVERY`, media decode cache, transcript log + detection queue + dedup ring, controller per-frame state, saved-theme library, the webview console-render poll/timers, `#verse-list`/`#transcript`/`#detections` DOM, session clipboard, event-listener accumulation.
- **View-load audit:** per operator surface (Live Console, Theme Designer, Screens, Scriptures) identify heavy on-load/activation work (base64 payload size, synchronous compose, big DOM builds, N+1 round-trips, unthrottled polls).
- **Latency measurement:** ONE timing test (`selahcue-app` or `selahcue-present`) timing the verse compose+render path; report the median + where the budget goes; reason about the wire/webview hops (loopback).
- **Deliverable:** `docs/quality/AUDIT-memory-perf-latency.md` — severity-ranked findings (file:line, measured numbers, fix), HIGHs adversarially verified, follow-up tickets queued.

### Non-goals

- Fixing the found issues (follow-up tickets); GUI-runtime profiling of the Tauri webview (can't launch it here — reason from code + the loopback path); the uncommitted font batch (audited as-is, not modified).

### Constraints

- Read-only except the timing test + the report. The timing test must be deterministic + non-flaky (measure + a LOOSE sanity ceiling, print the actual). Every HIGH finding adversarially verified before it is reported. Honest labels (Verified/Inferred/Assumed). fmt/clippy clean for the timing test.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Memory audit: every growing structure (Rust + webview) inventoried + classified bounded/unbounded; each UNBOUNDED or bounded-but-untested one is a finding with file:line + a recommended cap/test | Workflow memory lens + verify | complete inventory; gaps flagged | AUDIT report §1 | PASS |
| C-002 | yes | View-load audit: each operator surface's on-load/activation cost characterised; heavy paths flagged with evidence | Workflow view lens + verify | per-surface costs; heavy paths flagged | AUDIT report §2 | PASS |
| C-003 | yes | Latency: a deterministic timing test measures the verse `parse+verses+compose+render` path; the report states the measured median + the hop budget (webview→wire→host) | `cargo test -p <crate> -- --nocapture` | measured number reported | timing test + report §3 | PASS |
| C-004 | yes | Report: `docs/quality/AUDIT-memory-perf-latency.md` severity-ranked with evidence; every HIGH adversarially verified (0 unverified HIGH); follow-up tickets queued; timing test fmt/clippy clean | review report + `cargo fmt/clippy` | honest report; HIGHs verified; queued | AUDIT report | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- A `Workflow` fan-out (ultracode): a memory-leak lens (Rust + webview), a view-load lens (webview surfaces), each reading the code; per HIGH finding an adversarial verify (default REFUTED). A direct timing test for C-003. The report synthesises verified findings only.
- Required environment: local (host-side measurable; the Tauri GUI is not launchable here — webview costs reasoned from code).

## Iteration ledger

- Iter 0 (C-003): wrote `scripture_stage_to_live_latency_is_measured` in `selahcue-app` — a 1920×1080 `LiveController` (the shared helper is 320×180, which would under-report), warm-up, then median over 25× `apply(StageScripture)+apply(GoLive)` with the live frame materialized, print `[AUDIT]`, assert a loose 150ms ceiling. **Measured: median 118.7ms / p90 125.3 / max 126.4.** A throwaway present-level probe attributed the split: one compose+render ≈59ms (compose ≈8.6ms, raster ≈50.5ms → raster ~85%); the ~118ms controller figure ≈ two compose+renders (preview then live) + the sub-ms parse/lookup. Result: PASS.
- Iter 1 (C-001/C-002): `Workflow` fan-out `wf_f7726032-3d7` (3 lenses — memory-rust, memory-webview, viewload-webview; 336k tokens). **0 HIGH raised** → no adversarial verify round needed (honest: no HIGH to verify). Inventory: 7 structures bounded+tested (no action); **5 MEDIUM + 4 LOW** gaps. The two headline findings hand-verified: M1 plan-rebuild-every-second (read `app.js:25/37/43` + the `view.timer`-excluded console sig at 262-269) and the two Rust MEDIUMs (grep-confirmed no `MAX_PLAN_ITEMS`/`MAX_ACTIVE_SESSIONS`). Result: PASS.
- Iter 2 (C-004): wrote `docs/quality/AUDIT-memory-perf-latency.md` — severity-ranked, file:line evidence, measured numbers, honest Verified/Inferred labels, 0 unverified HIGH (none raised), 6 follow-ups queued (ClickUp rate-limited). Timing test fmt/clippy clean (workspace-wide). Result: PASS.

## Risks and rollback

- Risks: a flaky timing test (mitigated: measure + a loose ceiling + print; median of N runs). A false-positive finding (mitigated: adversarial verify each HIGH). Missing a structure (mitigated: the fan-out enumerates by grep of `Vec::new`/`HashMap`/`push`/`addEventListener`/`setInterval`). Rollback: git; only the timing test + report are added.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-audit-memory-perf-latency.md --require-complete`
- Validator result: (run below)
- Independent verification result: The audit IS the independent verification pass. The Workflow lenses read the code independently; HIGH findings would have been adversarially verified (0 raised); the two headline findings were additionally hand-verified. No product code changed, so no separate review gate applies — only the timing test + report were added.
- Terminal state: **VERIFIED_COMPLETE** — read-only audit + one committed timing test; C-001..C-004 all PASS; 0 release-blocking defect; 5 MEDIUM + 4 LOW follow-ups queued.
- ClickUp final evidence comment: (queued — MCP rate-limited; §4 of the report holds the tickets + a BUILD CONTROL `86ajnx548` update to post on recovery)
