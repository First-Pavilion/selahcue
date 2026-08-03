# Release Recommendation

## Decision

PASS

## One-line rationale

Every defined performance threshold passes — audience-path latency with an ~80× margin, zero memory leaks,
and the two previously-deferred GUI NFRs (idle-RSS, cold-start) now measured and comfortably inside budget.
The six efficiency findings are optional, owned follow-ups, not waived threshold failures.

## What the decision rests on

| Owner concern | Verdict | Evidence |
| --- | --- | --- |
| "no memory leaks" | Confirmed none | ~65 bounded/flood tests green + independent hot-path scan found no uncapped hot/long-running collection (`04-results/BOTTLENECK-ANALYSIS.md`) |
| "no lags" | Confirmed within budget | Stage→Live median 2.8 ms / max 3.6 ms @1080p; slide-trigger, long-verse auto-fit, keyword search all inside budget; GPU↔CPU parity SSIM ≥ 0.99 (`04-results/BASELINE-REPORT.md`) |
| "no performance issues" | Six non-blocking findings, none Critical/High | All bounded, none on/blanking the render path (`04-results/BOTTLENECK-ANALYSIS.md`) |

## Resource NFRs — now measured (owner-run `make nfr`, release, Darwin arm64 / Apple M5)

| NFR | Budget | Measured | Result |
| --- | --- | --- | --- |
| Cold start (launch → control-server-ready) | ≤ 3.0 s | **1.56 s** | PASS (~1.9× headroom) |
| Idle memory (max RSS over 5 s) | ≤ 300 MB | **124.1 MB** | PASS (~2.4× headroom) |
| Slide-trigger latency (re-confirmed by the harness) | ≤ 150 ms | within budget | PASS |

This closes the sole prior exception; there are no waived threshold failures remaining.

## Follow-ups (quality, not release gates)

Six efficiency findings are filed as owned follow-ups (PERF-1..PERF-8 under Build Control `86ajnx548`).
Two are MEDIUM CPU/allocation optimisations (STT interim re-transcription, quote-matcher token
memoisation); four are LOW/LOW-MEDIUM lock/upload observations. All are bounded, off the render path, and
cannot blank live output. They can be scheduled post-release and do not affect this decision.

## Not a FAIL, and no longer conditional

No Critical or High defect exists, no leak was found, and every audience-visible and resource NFR passes —
each by a wide margin. With the idle-RSS / cold-start measurement now in hand, this is an unqualified pass
rather than a conditional one.
