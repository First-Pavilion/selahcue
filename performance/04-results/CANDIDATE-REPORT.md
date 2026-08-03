# Candidate Report

## Relationship to baseline

This engagement is a **review**, not an optimisation. No production code was changed, so the candidate
build **is** the baseline (revision `dbd040e`). All numbers in `BASELINE-REPORT.md` are the candidate
numbers. This file exists to make that explicit and to state what a future candidate must beat.

## Candidate = `dbd040e` (current `main`)

| Dimension | Candidate result | Verdict |
| --- | --- | --- |
| Stage→Live @1080p | median 2.80 ms / p90 3.41 ms / max 3.65 ms | Well within ceiling |
| Slide-trigger budget | ≤ 150 ms | PASS |
| Long-verse auto-fit | ≤ 150 ms | PASS |
| Keyword search | < 500 ms | PASS |
| GPU↔CPU parity | SSIM ≥ 0.99 | PASS |
| Memory bounds | all caps hold under flood | PASS (no leak) |
| Concurrency / sessions | no leak, capped, reaped | PASS |
| At-rest encryption | open/migrate/backup | PASS |
| Idle RSS / cold start | not measured (headless) | OWNER-RUN |

## Regression baseline for future candidates

Any future change must keep, at the same host class and release profile:

- Stage→Live median ≤ ~30 ms (a 10× cushion over today's 2.8 ms; a jump toward the 300 ms ceiling is a
  regression to investigate long before it fails the budget test).
- All budget/parity tests green in `make ci`.
- Every bounded-memory test green — a new buffering site without a bounded test is a regression by policy.

## If follow-ups #1/#2 are implemented later

- **#1 STT sliding-window interim** — candidate must show reduced per-utterance transcription work (real-time
  factor) with **no change** to interim/final segment correctness (the two interim-streaming tests must stay
  green). Add a micro-benchmark capturing RTF before/after.
- **#2 quote-matcher token memoisation** — candidate must show reduced allocations per final segment with
  identical match results (`test_quote_match`, `test_quote_detection` unchanged).
