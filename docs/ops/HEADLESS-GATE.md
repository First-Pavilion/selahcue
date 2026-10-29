# Operator headless launcher policy

Decision for [17tnw2b1wvh](https://app.clickup.com/t/90131572460/17tnw2b1wvh), 29 October 2026.

The complete launcher contract continues to run on every `operator_headless.py` invocation,
including local `make operator-headless`, `make ci` and hosted CI. It makes the browser verdict
trustworthy; running only in CI would leave a broken local launcher unverified. The 16 environment
CLI scenarios introduced in PR #253 remain mandatory. There is no new skip flag or CI-only branch.
This keeps the existing behavior and makes its cost explicit.

The fake-hang readiness schedule is **1, 3, 20 seconds**. A promptly started fake reaches its real
timeout after one second rather than three. Missing browser/helper readiness markers mean an
inconclusive attempt and retry, never a passing hang check. The three-second middle attempt stays:
the historical ticket reports startup misses with a two-second middle wait under heavy load. The
20-second fallback and all process, temporary-file and exit-code assertions stay intact. A complete
passing result from a browser that never exits remains an infrastructure failure.

The nominal attempt budgets total 24 seconds if all three attempts are needed, versus 23 seconds
for the old 3/20 schedule, before cleanup and scheduling overhead. That bounded extra second on the
slow-start path is the tradeoff for saving about two seconds on the ready path.

The real Chrome wall cap stays **90 seconds**. Raising it to 150 seconds would add a minute before
reporting each genuine hang. Historical PR #153 recorded a 79.8-second passing browser phase at
load 117: 90 seconds leaves 10.2 seconds, or 12.8% of that runtime; 150 seconds would leave 70.2
seconds, or 88.0%. Those figures came from the ticket and were not reproduced in this study.
Observations below belong to the original study revision and do not establish a maximum latency or high-load guarantee. The browser
virtual-time budget and strict timeout-failure mapping remain unchanged.

## Original study and source scope

The original study at `8ae21ff634a7be7bf194b5c863f6180336c633fa` runs the exact tracked hang-check AST, actual fixture/launcher, PID/temp
cleanup and real gate verdict. It does not repeat the full 16-case CLI group 20 times. Baseline is
`8f7d610e`; baseline/candidate order alternates AB/BA. Launcher, fixture and PID primitives must be
AST-identical to that baseline for the runner to proceed. All raw samples are retained in
[schedule-samples.json](../delivery/goals/17tnw2b1wvh-evidence/schedule-samples.json).

| Observation | Baseline 3/20 | Candidate 1/3/20 |
|---|---:|---:|
| Critical hang-check samples | 20 | 20 |
| Median wall time | 3.013465 s | 1.010239 s |
| Minimum / maximum | 3.005706 / 3.044174 s | 1.005833 / 1.160599 s |
| Natural startup retries | 0 | 0 |
| Terminal failures observed | 0 | 0 |

Median paired saving: **2.003454 seconds**. Ambient one-minute load ranged from
6.48 to 15.35. This is an observed 0/20 count per version, not a universal flake-rate claim.
The samples completed between Mika's explicit quiet-CPU windows and before the subsequent full
native CI load. No quiet-host or historical load-117 reproduction is claimed.

Synthetic readiness controls separately exercised 1/3 and 1/3/20 attempts with 1.5-second and
four-second readiness delays. All recorded browser/helper processes were dead and temporary work
folders empty. Injecting an incorrect non-timeout result after a real hung fake produced the
expected failures: it was not reported timed out, and a passing partial block would otherwise
incorrectly map to exit 0 rather than required exit 2. These controls are retained in
[schedule-controls.json](../delivery/goals/17tnw2b1wvh-evidence/schedule-controls.json).

One complete gate on that original study source passed all 2,347 browser checks and the full launcher/environment
contract. Its self-test took 38.736 seconds, actual Chrome phase 13.763 seconds and total
55.021 seconds. The 90-second cap leaves 76.237 seconds, or 553.9% of that observed Chrome
phase. This is one observation, not a paired full-gate study. The two-second saving above applies
to the critical component; it is not a measured percentage reduction of this expanded full gate.
The older 4.1-second/62% overhead and monthly-runner estimates are historical, not current claims.
The phase record and exact script hashes are in
[gate-timing.json](../delivery/goals/17tnw2b1wvh-evidence/gate-timing.json).

Reproduce the frozen scoped study from `8ae21ff6` in an isolated checkout. Later launcher
primitive changes require a new comparison baseline; `--pairs` refuses them. Current-source
`--controls` is functional verification only and records its source hash separately:

```sh
python3 docs/delivery/goals/17tnw2b1wvh-evidence/measure_schedule.py --pairs 20 --output /tmp/selahcue-schedule.json
python3 docs/delivery/goals/17tnw2b1wvh-evidence/measure_schedule.py --controls --output /tmp/selahcue-controls.json
```

At the original study revision, the checked-in runner changed only workspace/output path binding
from the executed one-off runner; function-body equality was verified. After integrating the
shared lifecycle extraction, only current-source functional controls can bypass the original
baseline primitive-identity guard. Paired measurement still requires that guard. The original
40 samples and all their metadata remain unchanged; integrated controls are separate evidence,
not a fresh measurement of the original two-second saving. The initial unchanged-schedule comparison
failed the saving predicate, as recorded in
[red-samples.json](../delivery/goals/17tnw2b1wvh-evidence/red-samples.json).

## Shared-lifecycle integration refresh

After integrating main `6ef0e098`, the same1/3/20 controller runs through the shared
file-backed lifecycle extracted for auth and visual captures. The original study's
40 samples, headroom observation and source metadata are unchanged. New functional
controls are retained in
[integrated-controls.json](../delivery/goals/17tnw2b1wvh-evidence/integrated-controls.json):
forced delays take1/3 and1/3/20 attempts, and a deliberately incorrect timeout flag
still fails the strict verdict. These are current-source functional checks, with
no paired samples or new claim about the original2.003454-second saving. The full
integrated operator/caller gate outcomes are recorded in the Goal Contract and
refresh handoff separately from the original benchmark. The real operator refresh overlapped
a separate private-branch auth gate; it is functional evidence, not an isolated timing or
resource-attribution study.

The parent ticket's separate size correction is root-owned: replace only the obsolete `~1 MB`
claim with `~59 KB (Vera's measurement in PR #153)`, preserve the rest of its description and
status, and read back the saved phrase. It records a historical measurement, not today's source
file size.
