# Review — CI cost reduction (path-filter the matrix, 86ajq0569)

- **Scope:** cut GitHub Actions minutes/cost (`.github/workflows/ci.yml`) — prompted by the repo hitting its Actions quota this session. Executed via the `/goal` engine (`TASK-86ajq0569-ci-cost.md`, validator `--require-complete` PASS, 5/5). Config-only; **no coverage removed**.
- **Method:** pyyaml parse + a job-DAG audit + a scenario trace, then an independent review agent (the only safety net — CI can't run to self-verify while Actions is down).

## Change

A `changes` job (dorny/paths-filter@v3) detects which side changed and gates the rest:

| Job(s) | Runs when |
|---|---|
| rust ×3 · operator ×3 · launch-smoke ×2 · audit · supply-chain | the **desktop** side changed (`implementation/desktop/**`, `Makefile`, `scripts/**`, `implementation/web/**`, or `ci.yml`) |
| flutter | the **mobile** side changed (`implementation/mobile/**` or `ci.yml`) |
| flutter's `apk --debug` + JDK step | the **android** host changed (`android/**`, the multicast Dart, `pubspec.*`, or `ci.yml`) |

Every filter includes `ci.yml` so a workflow change re-runs everything. Caching (rust-cache + flutter) and the docs-only trigger skip are retained. **No matrix OS, gate, or step was removed** — the 3-OS parity gate runs in full on every desktop change.

## Scenario trace (verified)

| Commit touches | Jobs that run |
|---|---|
| desktop only | rust ×3, launch-smoke ×2, operator ×3, audit, supply-chain (Flutter skipped) |
| mobile only (pure Dart) | flutter (apk step skipped) |
| mobile + android | flutter (apk step runs) |
| both / ci.yml | everything |

## Savings

macOS bills **10×** minutes, Windows 2×. The three macOS jobs alone are ~30 weighted units per full run. A mobile-only commit now skips the entire ~50-weighted-unit desktop set; a desktop-only commit skips Flutter + the heavy Android SDK/Gradle apk build. Stage-8 commits are overwhelmingly single-side → this roughly **halves** average weighted-minute consumption.

## Review — 0 high/med; 3 LOW fixed

- **Coverage gap (LOW):** `implementation/web/**` matched neither filter (a latent hole if it ever gains code) → added to the desktop filter as a catch-all. Desktop build inputs (Makefile, scripts/, deny.toml) were already covered.
- **android narrowness (LOW):** a Flutter/plugin dep bump wouldn't re-run the apk check → added `pubspec.yaml`/`pubspec.lock` to the android filter.
- **Misleading comment (LOW, important):** the header claimed a paths-filter *job* avoids stuck-pending PRs, but this gates *downstream* jobs with `if:` — a skipped **required** check would deadlock a PR. Corrected the comment: safe only because this repo pushes to main with no branch protection; **before enabling required status checks, add a single aggregator job** (`needs:` all jobs; passes if each result is success or skipped) and require THAT.
- Verified clean: the DAG (all `needs`/`if`/outputs resolve), 3-OS parity preserved, and dorny/paths-filter's push default (diff vs the before-SHA; fails safe to over-run on a null/unreachable base).

## Status

The change is YAML-valid, DAG-audited, scenario-traced, and reviewed **locally**. Its own CI-green confirmation waits on the **owner restoring GitHub Actions** (the same outage that motivated it) — and once Actions is back, this change is exactly what keeps future runs cheap.
