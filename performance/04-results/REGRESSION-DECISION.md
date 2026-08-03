# Regression Decision + Independent Verification

## Regression posture

There is no prior performance baseline artifact to diff against — this is the first formal performance
review. So "regression" here means: does current `main` (`dbd040e`) violate any product performance NFR or
the repo's bounded-memory policy? **No.** All budget/parity/bounded tests are green, with ≥80× latency
margin. The numbers in `BASELINE-REPORT.md` become the reference future candidates are diffed against
(thresholds in `CANDIDATE-REPORT.md`).

## CI regression gates already in place

The product budgets are encoded as release-build pass/fail tests inside `make ci`, so a future latency or
parity regression fails CI without extra tooling:

- `go_live_slide_trigger_latency_is_within_budget` (150 ms)
- `go_live_latency_holds_for_the_longest_verse_auto_fit` (150 ms)
- `keyword_search_meets_the_500ms_budget` (500 ms)
- `selahcue-gpu` `test_parity` (SSIM ≥ 0.99)
- every bounded-memory/flood test

The bounded-memory policy ("new buffering code gets a bounded-memory test") is the standing gate against
new leaks.

## Independent verification (fresh-context reviewer)

A separate fresh-context reviewer was tasked to **refute** this review (default to "not verified"), and
re-derived every claim from source while re-running the cheap tests. Verdict: **DECISION_SOUND** — the
review holds. Confirmed, independently of the author:

1. **Bounded-memory claims are real (`leak_refutation: null`).** The reviewer enumerated every
   `push/push_back/insert/entry/extend/push_str` growth site across all crates (incl. the excluded
   `selahcue-operator` and `selahcue-stt`) and traced each to a cap or self-prune. No uncapped
   hot/long-running collection was found. It additionally corroborated a subtle case: `ServicePlan::add_item`
   is itself uncapped, but **every production caller** enforces `MAX_PLAN_ITEMS = 500` (`Command::AddItem`,
   the local operator shell, and the restore path), and `insert_item` has no production caller.
2. **`ManualProvider.pending` characterisation correct.** Its only non-doc reference outside the type is
   under `#[cfg(test)]` in `pump.rs`; the production STT path is `SttEngine → SegmentSink →
   SttProvider::poll → controller.ingest_transcript(...)` and never wires `ManualProvider` to a live source.
3. **Latency reproduced.** The reviewer's own release run of `scripture_stage_to_live_latency_is_measured`
   printed `median=2.566ms p90=2.835ms max=3.134ms (n=25)` — single-digit ms, consistent with the author's
   2.8/3.6 (run-to-run variance). `test_present` `go_live` (4 passed), keyword-search 500 ms budget, and
   `selahcue-gpu` `test_parity` (which **executed** on this M5's GPU rather than skipping) all PASS.
4. **The six findings are accurate and non-blocking.** #1 (`emit_interim` transcribes the whole `utterance`
   over the ~0.8 s worker-thread cadence — out-of-band from render, "cannot stall audience output" confirmed;
   ~6–7× re-transcription arithmetic sound) and #2 (per-candidate `BTreeSet<String>` alloc, bounded by
   `MAX_CANDIDATES = 5000`) match the code.
5. **The gap is honestly recorded** — idle-RSS/cold-start deferred to owner-run `make nfr`, carried as an
   approved exception rather than a silent pass.

### Minor risks the reviewer surfaced (none a refutation; folded into follow-ups)

- **`SessionRegistry.pending` has no hard count cap** the way `active` does (256) — it relies on
  expiry-prune plus operator-only reachability (pruned before each offer, TTL-bounded). Safe today, but
  asymmetric; a one-line cap would make the invariant local rather than reachability-dependent. Filed as
  PERF-8.
- **GPU-parity PASS is hardware-dependent** — `test_parity` skips on a box with no usable GPU (per
  `CLAUDE.md`). It genuinely executed and passed on this M5; on a truly headless box the parity gate would
  degrade to "not exercised." Noted in `BASELINE-REPORT.md`.
- **Finding #1's audience impact on weak hardware is unmeasured** — the one claim backed only by a
  memory-bound test, not an executed RTF measurement. Already flagged MEDIUM/non-blocking; the RTF
  micro-benchmark is PERF-1's acceptance gate.

## Decision

No blocking performance regression. The release decision (with the single owner-run exception) is recorded
in `05-handoff/RELEASE-RECOMMENDATION.md`.
