# Licence qualification cleanup: binding sequencing amendment

Accepted by the controller on 2026-11-17 after reading the complete terminal evidence, independently verifying its archive, and reading the independent builder check. This is the adjudication of the remaining execution-plan defect after Task 2 fix round 5. It does not reopen the five-round allowance or authorize a sixth speculative repair.

## Decision

Remove the already-qualified temporary overlay now, then run the planned canonical acceptance gate. This supersedes only the requirement for an additional successful full overlay run before removal in the capacity and minimal-qualification amendments and Task 2 Step 6. Full final coverage and all runtime bounds remain mandatory. This is a controller engineering ruling under the user's standing repair authorization, not a newly stated user preference.

The exact cleanup is deletion of `.github/scripts/qualify_license_generation.py` and `.github/scripts/test_qualify_license_generation.py`, and removal of the `Qualify licence extension generations on PostgreSQL` and `Retain licence generation qualification evidence` steps with their temporary comment from `.github/workflows/ci.yml`. Preserve all remaining workflow bytes and semantics, command parity, test selection/order, conditions, environments, routing and G1 stages. Keep API snapshot `01413d07e6377c017d5f2d2cbff4244ec4460017` and API tree `0410de586e948265ca1d20d69281ba950c5490d1` unchanged. No application or fixture change is authorized.

## Evidence and cost

The exact seven-control/four-mutant qualification completed twice on that unchanged API source. Current run43993505313 retained seven passing baseline controls, four intended mutant assertion failures, five distinct PostgreSQL16.16 databases, four verified restorations and unchanged canonical bytes. The 13,894-byte ZIP has SHA-256 `412ecb7b1328b1b3b07ee30cd610be9985010c758eef227a4a690c5d4104498d`; all28 members are archived and verified.

The normal API job nevertheless hit its official35-minute cap: 3,296 observed passes, one skip, 449 identities without a verdict, no final summary and no final G1 artifact. All493 original acceptance identities and all10 actual G1 cases passed in that job, but neither this partial run nor the prior e461 complete pytest result supplies a passing final gate. Preserve both failures exactly as recorded.

The removable stages took68+1=69seconds in this run, at whole-second metadata precision. That is observed overhead, not a fit guarantee or an explanation of the distributed336.627-second prefix slowdown. With otherwise unchanged current setup and prefix timing, only about56seconds would remain for the unobserved suffix, reporting and final G1 work. Cache state can also change after removal. The cost if this ruling is wrong is one bounded ordinary workflow and an acceptance gate that remains open; it is not permission to waive or repeatedly retry the gate.

## Required acceptance

Obtain independent removal/custody review before one ordinary canonical candidate push. Keep the API job ceiling at35minutes, operator at30, and all application, SQL, lock, child, qualification and other-job bounds unchanged. The historical180/60/450-second isolated limits remain part of the qualified evidence; the removed lane is not replaced with another job, matrix leg or command.

Before Task2 acceptance or Task3 admission, the resulting exact canonical source and hosted merge must pass the complete normal API suite, reconcile all493 original identities exactly once as PASS, pass both G1 controls and all10 actual G1 scenarios, execute the mandatory final G1 validator successfully, and retain the same-run evidence with verified producer source/hash. Every final result must belong to that run and attempt. Never combine incomplete runs into a successful gate. If the canonical run fails or times out, retain and investigate its actual evidence. No automatic retry, timeout increase or test redesign is authorized.

Keep the original493 manifest byte-for-byte at SHA-256 `5e43389db30bd1e470b5f57d06d52cd389de5e91a4f835908aa9651052257465`, existing identity normalization, immutable qualifier Git history, ZIP and restoration evidence, all normal logs and branch archives. Historical outcomes never enter the fresh join. The canonical tests and G1 paths consume no output from the temporary qualifier, so removal creates no replacement dependency. Do not invent an artificial failing unit test for deleting completed diagnostic scaffolding; verify exact removal and use the existing workflow controls and mandatory real canonical acceptance.

The root custody receipt is `ci-43993505313-root-reverification.json`:12 executed receipts,36 raw/metadata files and63 supporting files,111 distinct verified files. The independent report is `pr233-canonical-cleanup-builder-20261117.md`. Both remain in the release review evidence workspace. No runtime pass or Task2 completion is claimed by this document.
