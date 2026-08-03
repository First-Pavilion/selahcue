# Defects and Follow-ups

No Critical or High performance defect was found. Nothing here blocks release. Items are owned follow-ups
and one owner-run measurement.

## Severity summary

| Severity | Count | Blocks release? |
| --- | --- | --- |
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 (PERF-1, PERF-2) | No (accepted, owned) |
| Low / Low-Medium | 4 (PERF-3..PERF-6) | No (accepted, owned) |
| Minor note | 2 (PERF-7, PERF-8) | No (accepted, owned) |
| Owner-run measurement | 1 (NFR-MEM) | No (approved exception) |

## Follow-ups (from `BOTTLENECK-ANALYSIS.md`)

| ID | Title | Severity | Owner | Acceptance for the fix |
| --- | --- | --- | --- | --- |
| PERF-1 | STT interim: transcribe a sliding window/tail, not the whole growing buffer | MEDIUM | ai | Reduced real-time factor per utterance; the two interim-streaming tests stay green; add an RTF micro-benchmark |
| PERF-2 | Quote matcher: memoise per-verse token sets in `QuoteIndex` at build time | MEDIUM | ai | Fewer allocations per final segment; `test_quote_match` + `test_quote_detection` unchanged |
| PERF-3 | Native render loop: dirty-flag the framebuffer upload + redraw; skip when unchanged | LOW-MEDIUM | backend/graphics | No per-frame 8 MB upload on a static slide; parity + never-blank preserved; helps idle power/RSS |
| PERF-4 | RemoteOperator: split read-only thumbnail/state polls off the control lock | LOW-MEDIUM | frontend/backend | A laggy poll no longer serialises against go-live/blackout |
| PERF-5 | `operator_view()`: memoise verse lookups / dirty-track if poll cadence rises | LOW | backend | No behavioural change at 1 Hz; guards against a future higher poll rate |
| PERF-6 | Desktop redraw: drop the controller lock before wgpu present | LOW | backend | Remote command no longer waits up to a vsync behind present |
| PERF-7 | `ManualProvider.pending`: add a one-line bound if it ever backs a live ingest source | LOW | backend | Test/host-injection only today; bound before any production wiring |
| PERF-8 | `SessionRegistry.pending`: add a hard count cap symmetric with `active` (256) | LOW | backend | Bound becomes a local invariant, not a reachability argument; existing session E2E stays green |

## Owner-run measurement

| ID | Title | Owner | How to close |
| --- | --- | --- | --- |
| NFR-MEM | Idle RSS ≤ 300 MB and cold start ≤ 3 s | owner | Run `make nfr` on a machine with a display; paste numbers into `04-results/BASELINE-REPORT.md`. If both hold, the release exception clears. |

## ClickUp

Per the repo convention (Build Control `86ajnx548` is the source of truth), these follow-ups should be
filed as linked tasks and the review evidence linked from the Build Control task. ClickUp update is pending
(see handoff note in `STATUS.md`); this file is the ready-to-file list.
