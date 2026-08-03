# Performance Brief

## Request

Owner (verbatim): *"go through the entire codebase and review the application performance. Run
end-to-end tests to make sure there's no memory leaks, no lags and no performance issues."*

## Interpretation

A whole-codebase performance review of the SelahCue desktop Rust workspace with three explicit
acceptance concerns, mapped to measurable outcomes:

| Owner concern | Measurable question | Where answered |
| --- | --- | --- |
| "no memory leaks" | Does any collection on a hot or long-running path grow without bound? | `04-results/BOTTLENECK-ANALYSIS.md`, bounded-memory suites |
| "no lags" | Does the audience-visible slide/cue trigger stay within its latency budget? | `04-results/BASELINE-REPORT.md` |
| "no performance issues" | Are there CPU/allocation/lock hot spots that would degrade under real service load? | `04-results/BOTTLENECK-ANALYSIS.md` |

## Product context

SelahCue is a church presentation + ministry-assist app. The performance-critical invariants come
from `ARCHITECTURE.md`:

- **Desktop-authoritative, offline-first.** The native output window (winit + wgpu) owns the audience
  display; the operator console (Tauri WebView) is a control surface only and never renders audience output.
- **No component failure may blank live output** (NFR-024, "never-blank"). Latency and lock behaviour on
  the render path are therefore correctness concerns, not just comfort.
- **AI assists but never gates core controls.** STT/detection run out-of-band on worker threads; they may
  never stall the render loop.
- **Resource use is bounded.** The repo rule "no unbounded queues/caches/logs; new buffering code gets a
  bounded-memory test" is a first-class constraint (see `CLAUDE.md`).

## Affected roles / workflows

- **Operator** — stages and triggers slides/scripture; watches live transcript + detected scripture.
- **Audience output** — the native full-HD window that must never lag or blank.
- **Mobile controller** — LAN peer issuing RBAC-checked commands over a pinned-TLS WebSocket.

## Current symptoms

None reported. This is a proactive pre-release review, triggered after the STT engine, real-time
interim transcription, and scripture detection (R4) landed on `main`.

## Deadline / gate

Pre-release quality gate for the current `main` tip (HEAD `dbd040e`). No production-load test is
authorised or required — the app is desktop/LAN, not a hosted service.

## Prohibited actions

- No production/hosted load testing (there is no hosted surface; not applicable).
- No modification of production code as part of this review (review-only scope).
- No changes to the concurrent Design-2 workstream's files.
