# Reset timing replay evidence

These are the complete timing receipts retained for QA-265-1. They contain every warmup, target pair and interleaved same-path null pair from the original studies, with runtime/configuration and real publish/commit/body counts. No sample was removed or rewritten. Source commits in the receipts identify GitHub's tested synthetic checkout or the nonshipping diagnostic branch, rather than pretending they are the PR branch SHA.

| Receipt | Original run | SHA256 of retained file |
| --- | --- | --- |
| `pr-ci40923541126.json` | [Failed full PR CI](https://github.com/First-Pavilion/selahcue/actions/runs/40923541126) | `7c98bc392b98bec3784e567784c5a5b79832233e9b7f01a5a7d453be14196974` |
| `pad-removal40923575228.json` | [Frozen-source candidate/mutation/restoration diagnostic](https://github.com/First-Pavilion/selahcue/actions/runs/40923575228) | `62f2f900af7da4126ac86820a78de7274e019e59a56624b305b202ae614be9fa` |

The failed full suite recorded one unknown-address HTTP request at 450.772ms. Its all-sample mean interval was [-33.098, 11.170]ms and included zero: precision was insufficient to establish mean equivalence or an outside-band signed gap. The old assertion incorrectly called that proof of account-existence distinguishability. The cause of the slow request is unproven; the receipt is preserved, not relabeled as a proven harmless product event. The actual pad-removal receipt independently retains a repeatable positive branch gap.

## Fixed protocol after QA-265-1

The existing resend probe judges median latency and reports instrument noise. Reset now keeps its fixed four warmup pairs, 32 alternating AB/BA target pairs, 32 interleaved same-path null pairs, original ±3ms band, actual HTTP/commit/Redis checks and minimum-floor positive control. There is one fixed study: no adaptive repeats, trimming, winsorization, sample deletion, replacement, band widening, or production-floor change.

For paired differences `D`, use the order-statistic median interval `[D_(10), D_(23)]`. Under independent continuous pair differences, the number below the population median is Binomial(32, 0.5). The interval misses only when at most nine lie on either side. Thus coverage is `1 - 2 * sum(C(32, i), i=0..9) / 2^32 = 97.9938393%`; ties make the coverage conservative. The target/null intervals jointly cover their medians with at least 95.9876786% by the union bound, without requiring independence between those two intervals. Serial correlation can invalidate the independence assumption within a sample, so raw order and null data remain explicit.

Both median intervals must fit the unchanged band. Every raw arithmetic-mean value and its original Student-t interval remain in the report. A signed target mean interval wholly above +3ms or below -3ms independently vetoes the gate, even if the median fits. The same signed asymmetry in the null control invalidates the instrument. An interval overlapping a band boundary is precision-inconclusive, rather than proof of a directional gap. An inconclusive target median fails the gate; an inconclusive mean does not become a mean-equivalence claim when the scoped median/null gate passes.

Deterministic tests in the existing `test_customer_auth_slice.py` replay both complete receipts and verify unchanged raw hashes. They accept the observed precision-failure receipt under the scoped protocol, reject the actual mutant, reject persistent ±3.5ms gaps, and reject six-of-32 same-branch 150ms delays in either direction through the retained mean veto. A separate opposing-outlier control ensures an inconclusive mean cannot excuse a signed median gap. Broad median intervals and invalid null controls fail with accurate diagnoses. Isolated positive/negative outliers at every position are retained in raw/mean evidence without masquerading as a demonstrated signed gap. Fixed sample-count, finite-duration and exact order-statistic controls guard the instrument itself.

## Evidence boundary

This establishes paired-location equivalence within the measured band with a retained evidenced signed-mean-gap veto. It does not prove equality of arbitrary latency distributions, rare tails, variance, or arbitrary network/scheduling conditions. The mean veto prevents a median-only gate from hiding the demonstrated minority-delay mean asymmetry, but finite 32-pair evidence cannot exclude every rare tail. All raw values remain available for further investigation, and production overruns retain the existing bounded report. Production `ACCOUNT_RESET_REQUEST_MIN_SECONDS` remains 0.1s and service behavior is unchanged by this test-instrument correction.
