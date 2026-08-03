# Release Recommendation

## Decision

PASS WITH APPROVED EXCEPTIONS

## One-line rationale

Every code-measurable performance NFR passes with an ~80× latency margin and zero memory leaks; the only
unverified items are two GUI-display-dependent NFRs (idle-RSS / cold-start), deferred to owner-run
`make nfr`, plus a set of non-blocking, owned efficiency follow-ups.

## What the decision rests on

| Owner concern | Verdict | Evidence |
| --- | --- | --- |
| "no memory leaks" | Confirmed none | ~65 bounded/flood tests green + independent hot-path scan found no uncapped hot/long-running collection (`04-results/BOTTLENECK-ANALYSIS.md`) |
| "no lags" | Confirmed within budget | Stage→Live median 2.8 ms / max 3.6 ms @1080p; slide-trigger, long-verse auto-fit, keyword search all inside budget; GPU↔CPU parity SSIM ≥ 0.99 (`04-results/BASELINE-REPORT.md`) |
| "no performance issues" | Six non-blocking findings, none Critical/High | All bounded, none on/blanking the render path (`04-results/BOTTLENECK-ANALYSIS.md`) |

## Approved exceptions (why this is not an unqualified pass)

1. **Idle-RSS (≤300 MB) and cold-start (≤3 s) NFRs were not measured this session.** They require an
   attached display; the session is headless. The harness exists (`make nfr`). Deferred to the owner. This
   is recorded as an exception, not silently passed.
2. **Two MEDIUM CPU/allocation efficiency follow-ups accepted** with owners (PERF-1 STT interim
   re-transcription, PERF-2 quote-matcher token memoisation). Both are bounded, off the render path, and
   cannot blank live output. Accepted as scheduled optimisations, not release blockers.
3. **Four LOW / LOW-MEDIUM lock/upload observations accepted** with owners (PERF-3..PERF-6). All bounded and
   sub-frame.

## Conditions to reach an unqualified pass

- Owner runs `make nfr` on a machine with a display; if idle-RSS ≤ 300 MB and cold-start ≤ 3 s both hold,
  exception (1) clears and the decision becomes an unqualified pass.
- Exceptions (2) and (3) are quality follow-ups, not release gates; they can be scheduled post-release.

## Not a FAIL because

No Critical or High defect exists, no leak was found, and no audience-visible latency budget is exceeded —
in fact each passes by a very large margin. The residual items are one deferred GUI measurement and owned
efficiency work, which is precisely the "PASS WITH APPROVED EXCEPTIONS" case rather than a blocking failure.
