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

## Historical initial evidence on c0325d52 (45 controls; not current)

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


## Manual current-source review cycle3 — actual Goal iteration2

Root explicitly authorized one additional implementation/integration iteration after two automatic review refreshes, to integrate published CSP93e5875c0a83eabbda1808693b31c70d09ebbf23/currentmaina6 and the reviewed ninth STT marker. The actual existing Goal has maximum4 and only iteration1 previously recorded: this work is iteration2, preserving original numbering and historical failures, not inventing two implementation iterations or resetting a budget.

Normal merge31f2939fd1b9afd6227dda87c7bc7201b0a0491a integrated93 without conflicts, preserving current cache/audit/canary gates, ordinary scanner call and tiny two-minute readonly sparse unfiltered workflow. The initial attempted fetch used an absent guessed branchname; exact provider PR373 ref/currentmain were fetched instead. No protected branch, forced history or cherry-pick used. Published CSP93 is included; PR350 must wait until PR373 merges to main. Source publication approval is no longer a pending CSP blocker, but merge ordering remains required.

### Current additive baseline controls

The original wiring checker did not independently pin any scanner semantics. A scratch actual scanner rollback removing the STT declared row AND required pin AND lowering signature count9to8/self-test floor47to45 still passed all45 old self-tests (exit0). This is the meaningful RED premise: internally coordinated rollback can make the old controls green while losing STT coverage.

The existing CI-only helper now independently protects all nine baseline public needles, required pins/count>=9/self-test floor>=47, both encodings/pins, four current target paths/pins, every1MB byte floor, and the existing single allowed unreadable-file skip. Additions remain allowed. The same actual old8/45 source is now rejected with lost-declared-baseline-signature. Nine policy mutants are rejected, including individual STT row/pin/count/floor removal, coordinated all-four rollback, encoding removal, target/pin/count removal, all byte floors lowered and expanded skip allowance. No production scanner string/logic/redaction/runtime feature/Windows workflow was changed by this ticket. A future authorized scheduled provider removal must deliberately update this independent baseline too.

### One completed current focused set

- Current scanner47normalPython PASS in0.435s;47optimizedPython PASS in0.480s. The old45 receipt above is historical, not current.
- Current wiring checker PASS: eight event/path cases, seven original bypass mutants, nine new scanner-policy mutants. The original `check(workflow,ci)` function is byte-identical and all original cases were actually executed again, not inferred as retained.
- Actual scratch disabled-run_scan scanner exits1 (all raw failure diagnostics retained); this preserves normal job failure propagation, including current STT injection controls. Neither these fixtures nor the coordinatedrollback copy alters committed scanner source.
- Workflow selftests118 legacy plus39 cache CLI fixtures PASS; actual checker7workflows/21jobs PASS; cachecoverage39 PASS; minute selftest/check PASS (no macOS, Windows tier-only); visual28 orderedpaths PASS; Linuxinstaller contracts PASS; supply8mutants/36actualalias probes and actual3roots PASS; canary16drift/2shelloutcome probes and8config actualcoverage PASS. Actionlint and whitespace PASS. No Rust/native/Tauri/package/browser/provider/installer build or dispatch ran.
- Current scanner and Windows installer workflow bytes equal published93 exactly; scanner SHA256377204530b549809cf403a2c7abe9e36d4c0f82870c1e1acc94b00ce730a2662. Existing targets, encodings, floors and redaction remain governed by the unchanged47 scanner cases plus new independent data policy.

Raw receipts `/private/tmp/350-scanner-refresh/`: `checks.json`,check00–15stdout/stderr, actualdisabledscanner diagnostics/exit, coordinatedold8 before/afterpolicy receipts, baselineidentity and verifier driver. All commands completed/reaped. Final authored range vs93 remains exactly five files: CI wiring/helper/dedicatedworkflow plus Goal/evidence. Root owns current hostedCI, four MANUAL refresh3 verdicts, PR373-before350 merge ordering and actualmain/QA; no current CI pass is fabricated from prior b7failedrun.
