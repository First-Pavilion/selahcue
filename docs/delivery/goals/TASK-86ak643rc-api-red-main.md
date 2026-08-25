# Goal Contract — TASK-86ak643rc-api-red-main

## Identity

- Goal ID: TASK-86ak643rc-api-red-main
- Parent goal ID: NONE
- Title: `api (django)` runs clean — the two erroring resend tests and the constant-time probe
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak643rc (defects 2 and 3) and https://app.clickup.com/t/86ak5rnrr
- Created: 2026-08-25
- Updated: 2026-08-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`implementation/api/tests/test_resend_verification.py` collects and runs with no
`AttributeError`, the two limiter-outage tests exercise real behaviour rather than a stub,
and the constant-time probe gives a trustworthy verdict on CI hardware and under local
contention — while still going red when a real timing difference is introduced.

## Baseline

Verified at `607a7b5` with a Python 3.14 venv rebuilt from `pyproject.toml` (the documented
`/private/tmp/selahcue-api-venv` no longer exists):

- `pytest tests/test_resend_verification.py -q` → `20 passed, 2 errors`, both errors
  `AttributeError: module 'selahcue_api.apps.accounts.services' has no attribute
  '_reset_degraded_send_window'`.
- CI runs `31904270364` (2026-08-15) and `31968483487` (2026-08-16) both report
  `2 failed, 188 passed, 2 errors`. The **second** failure,
  `test_the_eligible_branch_costs_well_under_the_constant_time_floor`, appears in neither
  ticket and is **not** in this goal's scope — see Non-goals.
- `enforce_budget_reporting_outage` exists in `throttling/guards.py` with **zero** call sites.

## Inputs and evidence sources

- Commit `2c89159` and its message ("Its tests were not run here -- pytest is unavailable")
- Commit `419d8a6`, which raised the floor `0.25 → 0.4` and left the probe on `0.25`
- CI job logs for runs `31904270364` and `31968483487` (`gh run view --log`)
- ClickUp `86ak643rc`, `86ak5rnrr`
- `CLAUDE.md` bounded-memory and mutation-verification rules

## Scope

### In scope

- A real degraded-send ceiling in `apps/accounts/services.py`, consuming the unused
  `enforce_budget_reporting_outage` seam, plus its `_reset_degraded_send_window` test seam.
- The `on_commit` harness defect in `test_a_limiter_outage_bounds_the_sending_...`.
- Rewriting `test_response_timing_does_not_distinguish_the_three_cases` so its verdict does
  not depend on the host's PBKDF2 speed.

### Non-goals

- `test_the_eligible_branch_costs_well_under_the_constant_time_floor`. It fails on CI because
  the eligible branch's own work (458–469 ms) exceeds the shipped 400 ms floor on that
  hardware. That is a real production finding about floor sizing, and every remedy (raise the
  floor and pay the thread-parking cost; drop PBKDF2 from a 256-bit token mint) is a
  security/architecture decision. Escalated, not decided here.
- Defect 1 of `86ak643rc` (the ubuntu serif font test) — owned elsewhere.

### Constraints

- Do not weaken an assertion to make it pass; do not stub a helper to silence an error.
- Bounded memory: no per-key map on an unauthenticated endpoint.
- No PR (owner requires Cody/Sana/Vera/Quinn review first).

### Assumptions and unknowns

- ASSUMED: production hardware is faster than a 2-core GitHub runner, so the shipped 400 ms
  floor is adequate there. Validation owner: Security Reviewer (Sana) via the escalation.

## Dependencies and approvals

- `86ak5rc9c` (toolchain fix) must land for CI to reach the api job at all — owner: DevOps.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The file collects and runs with no `AttributeError` | `pytest tests/test_resend_verification.py -q` | exits 0, no errors | `gate-suite.txt` | PASS |
| C-002 | yes | A limiter outage bounds sending without denying the response | same file, `-k limiter_outage` | passes; 2 of 5 sends leave; one report | `after-fix1.txt` | PASS |
| C-003 | yes | A skipped send does not supersede an existing link | same file, `-k skipped_send` | passes; token count 1, `consumed_at is None` | `after-fix1.txt` | PASS |
| C-004 | yes | Removing the degraded ceiling turns C-002/C-003 red | `mutate.py MUT-A` | both tests FAIL, siblings running | `mut-MUT-A-*.txt` | PASS |
| C-005 | yes | Skipping the send but keeping the mint turns C-003 red | `mutate.py MUT-B` | `test_a_skipped_send_...` FAILS | `mut-MUT-B-*.txt` | PASS |
| C-006 | yes | Deleting the constant-time padding turns the probe red | `mutate.py MUT-C` | probe FAILS, siblings running | `mut-MUT-C-*.txt` | PASS |
| C-007 | yes | A deliberate delay in one of the three cases turns the probe red | `mutate.py MUT-D` | probe FAILS and is the ONLY new red | `mut-MUT-D-*.txt` | PASS |
| C-008 | yes | The probe never reds under heavy contention | 6 reps at load 37–71 | 0 probe failures (pass or reasoned skip) | `hard-rep1..6.txt` | PASS |
| C-009 | yes | The full api suite passes | `pytest tests -q` | exits 0 | `gate-suite.txt` | PASS |
| C-010 | yes | CI's other api gates pass | `manage.py check`; `makemigrations --check --noinput` | both exit 0 | `gate-check.txt`, `gate-migrations.txt` | PASS |
| C-011 | yes | The floor the probe uses cannot silently drift again | probe asserts `PRODUCTION_FLOOR == RESEND_MIN_SECONDS_DEFAULT` | assertion present and green | `test_resend_verification.py` | PASS |
| C-012 | yes | Independent review (Cody, Sana, Vera, Quinn + Codex pairs) | review pipeline | no blocking findings | ClickUp | PENDING |

## Verification plan

- Focused verification: the two limiter-outage tests and the probe, always with siblings.
- Broader regression verification: full `pytest tests -q`, plus `manage.py check` and
  `makemigrations --check`, mirroring the `api (django)` job's three steps.
- Independent verifier: Cody, Sana, Vera, Quinn (and their Codex counterparts).
- Required environment: Python 3.14 venv built from `pyproject.toml`, matching CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-003
- Hypothesis: `2c89159` shipped the throttling half and the test half of a feature and dropped
  the consumer half in `accounts/services.py`.
- Change or investigation: read `2c89159` in full; found `enforce_budget_reporting_outage`
  with zero call sites and a commit message admitting its tests were never run.
- Verifier executed: `grep -rn enforce_budget_reporting_outage`
- Result: 0 call sites — the feature, not just the helper, is missing.
- New evidence: the tests describe a coherent, well-motivated design; not speculative.
- Decision: iterate — implement the degraded-send window.

### Iteration 2

- Target criterion: C-002
- Hypothesis: the test also cannot pass as written, because it calls the service directly
  under non-transactional `django_db`, where `on_commit` never fires.
- Change or investigation: wrapped its calls in `TestCase.captureOnCommitCallbacks`.
- Verifier executed: `pytest -k "limiter_outage or skipped_send"`
- Result: 2 passed.
- Decision: iterate — the timing probe.

### Iteration 3

- Target criterion: C-006..C-008
- Hypothesis: the probe is not flaky; it hardcodes a floor (0.25) that `419d8a6` retired, and
  on slow hardware no branch fits inside it, so the padding never runs.
- Change or investigation: measured pre-padding work per branch; read both CI runs.
- Verifier executed: instrumented probe; `gh run view --log`
- Result: on CI every branch costs ~460 ms against a 250 ms floor; the 66–68 ms spread is the
  probe's own injected 60 ms dispatch, unabsorbed. The assertion reduced to `66ms < 30ms`.
- New evidence: the two same-code-path cases agreed to 0.0 ms and 0.7 ms — the instrument was
  resolving sub-millisecond, so the 66 ms was real work.
- Decision: iterate — calibrate the floor to the host.

### Iteration 4

- Target criterion: C-008
- Hypothesis: `min()` calibration under-provisions a floor on a machine that keeps degrading.
- Change or investigation: switched calibration to `max()` of 4 samples; added the null
  control.
- Verifier executed: 6 reps at load 37–71.
- Result: 0 probe failures (previously 2 of 3 red at load 34–40).
- Decision: complete — hand off to review.

## Risks and rollback

- Risks: the degraded ceiling is per-worker, so N workers give N× the limit; stated in the
  setting's comment and in the warning it emits. The probe can skip on a saturated host; it
  cannot skip on a single-branch regression, which is the case that matters.
- Rollback or recovery: three files, one commit, revertable in isolation.

## Pause and escalation conditions

- Sizing the shipped constant-time floor, or removing PBKDF2 from the token mint — owner:
  Security Reviewer / Architect. Raised as a follow-up rather than decided here.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ak643rc-api-red-main.md --completion`
- Validator result: see handoff comment
- Independent verification result: PENDING (C-012)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-012 (review pipeline)
- ClickUp final evidence comment: posted on 86ak643rc and 86ak5rnrr
