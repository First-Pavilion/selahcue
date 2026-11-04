# Installer scanner self-test in ordinary CI

Ticket: https://app.clickup.com/t/86akc4ec5

Base: c0325d52e809847fac141a605b74a7e6d7de7021. Goal: TASK-86akc4ec5.

The existing stdlib-only self-test now runs directly in `ci.yml` before its
other workflow gates. A second, tiny `installer-scanner-controls.yml` workflow
has unfiltered main-push and ordinary PR lifecycle triggers, so docs-only and
API-only changes cannot omit the control. It checks out only the scanner,
persists no checkout credential, grants only contents read, and has a two-minute
Ubuntu timeout. No dependencies, cache, installer build, full scan or artifact
access are added. The duplicate subsecond call on ordinary code changes is the
explicit cost of preserving the expensive workflow's existing docs exclusions
and visual-audit trigger contract. Root approved this routing choice.

## Executed local evidence (2026-11-04)

All commands completed; no background verifier remains running.

| Check | Result |
|---|---|
| Actual `python3 scripts/installer_secret_scan.py --self-test` command, copied unchanged into temporary directory | exit0,45 cases,0.427 seconds |
| Same command after inserting an immediate return into temporary `run_scan` | exit1,30 failed cases including poisoned artifacts/missing targets; temporary copy removed |
| `python3 .github/scripts/check_installer_scanner_ci.py` | exit0;8 main-push/PR representative docs/API/source path cases;7 rejected path-filter/failure-masking mutations |
| `python3 .github/scripts/check_workflows.py --self-test` | exit0;118 cases |
| `python3 .github/scripts/check_workflows.py` | exit0;7 workflows,20 jobs |
| `python3 .github/scripts/check_ci_minutes.py --self-test` and checker | both exit0;7 workflows, no macOS, Windows remains tier-only |
| `python3 .github/scripts/check_visual_audit_ci.py` | exit0;20 ordered push/PR path cases and existing shared/browser gates |
| `actionlint` | exit0 |
| `git diff --check` | exit0 |

The dedicated workflow has only checkout and the exact direct self-test command;
there is no step/job condition, continuation or shell failure suppression. This
links the observed mutant exit1 to normal GitHub Actions step/job failure
semantics. Local trigger controls inspect committed configuration; actual GitHub
event delivery and hosted runtime are pending exact-head hosted CI, not claimed
as locally executed. Runner startup/checkout time is outside the measured
subsecond added scanner command.

Scanner source, signatures, `windows-installer.yml`, installer admission,
visual/NDI/SBOM gates and application sources remain unchanged.

## Handoff gate

GATE_REVIEW: Cody, Shadow, Quinn and Vera must independently pass the final
head; parent owns hosted CI/freshness, merge to main and ticket QA transition.
No installer packaging dispatch or deployment is part of this ticket.
