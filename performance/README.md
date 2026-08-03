# SelahCue — Performance Review (whole-codebase)

Scope: an evidence-backed performance review of the SelahCue desktop Rust workspace,
answering the owner request — *"go through the entire codebase and review the
application performance. Run end-to-end tests to make sure there's no memory leaks,
no lags and no performance issues."*

This is a **review / release-gate assessment of current `main`** (HEAD `dbd040e`), not an
optimisation engagement. No production code was modified. The candidate build under
assessment is the current tip; there is no separate "before" build because no optimisation
was applied — findings are handed off as owned follow-ups.

## How to read this

| Question | File |
| --- | --- |
| One-line decision | [05-handoff/RELEASE-RECOMMENDATION.md](05-handoff/RELEASE-RECOMMENDATION.md) |
| What was measured, with numbers | [04-results/BASELINE-REPORT.md](04-results/BASELINE-REPORT.md) |
| Where the CPU / allocation / lock risks are | [04-results/BOTTLENECK-ANALYSIS.md](04-results/BOTTLENECK-ANALYSIS.md) |
| Every threshold + its verifier + evidence | [01-goals/METRICS-AND-THRESHOLDS.md](01-goals/METRICS-AND-THRESHOLDS.md) |
| Findings + owners + follow-ups | [05-handoff/DEFECTS-AND-FOLLOWUPS.md](05-handoff/DEFECTS-AND-FOLLOWUPS.md) |
| Current stage / terminal state | [STATUS.md](STATUS.md) |

## Structure

This follows the performance-engineer standard layout. Executable tests are **not** duplicated
here — they live in each crate's `tests/` directory and in `scripts/`. `03-suite/TEST-INVENTORY.md`
maps scenarios to the real test files and commands.

- `00-intake/` — brief, toolchain, measured system baseline
- `01-goals/` — goal contract, metric register, risk matrix
- `02-plan/` — test plan, workload model, environment, scenario matrix
- `03-suite/` — test inventory + execution commands (pointers into the repo)
- `04-results/` — baseline report, candidate report, run index, bottleneck analysis, regression decision
- `05-handoff/` — defects/follow-ups, optimisation log, release recommendation

## Headline

- **No memory leak found.** Every buffering site on a hot or long-running path is hard-capped and
  has a matching bounded-memory test. Verified by an exhaustive independent hot-path scan plus
  ~65 bounded/flood tests, all green.
- **No lag on the audience-visible path.** Stage→Live compose+render at 1920×1080 measures
  median **2.8 ms** / max **3.6 ms** (release), against a 150 ms single-trigger product budget and a
  ~300 ms two-render ceiling — an ~80× margin.
- **Six efficiency findings**, none catastrophic: two MEDIUM CPU/allocation follow-ups and four
  LOW/LOW-MEDIUM lock/upload observations. All bounded; none can blank live output.
- **One measurement gap:** idle-RSS and cold-start NFRs need a GUI display and are owner-run via
  `make nfr`; they were not executed in this headless session. Recorded as an approved exception.
