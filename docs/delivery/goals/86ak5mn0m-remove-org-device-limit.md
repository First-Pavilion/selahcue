# Goal Contract — 86ak5mn0m-remove-org-device-limit

## Identity

- Goal ID: 86ak5mn0m-remove-org-device-limit
- Parent goal ID: NONE
- Title: An organisation's device limit is one number, the one on its licence key, copied from the plan at issuance; the dead org-level field is gone and a second valid key per org is refused
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak5mn0m
- Created: 2026-10-25
- Updated: 2026-10-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`CustomerOrg.device_limit` no longer exists (forward-only migration, no key row touched). `generate_license_key` refuses with POLICY_DENIED, writing nothing, when the same organisation already holds a key whose dates overlap the new key's, and sets the new key's `device_limit` from the plan's catalogue `device_instances` value instead of a number typed by staff. The admin console, the signed manifest, the refresh endpoint and both activation routes then all report and enforce the same single number, `AppLicenseKey.device_limit`.

## Baseline

Verified on origin/main 4e744ac3 (2026-10-25):

- Two `device_limit` fields exist: `CustomerOrg.device_limit` (`apps/accounts/models.py:25`), read by nothing that enforces, and `AppLicenseKey.device_limit` (`apps/license_keys/models.py:50`), enforced at `apps/devices/services.py:480` (new activation) and `:354` (re-mint allowance), published as `instances_limit` at `apps/entitlements/services.py:152` and `apps/devices/services.py:698` (refresh, surfaced at `platform/views.py:351`).
- `GenerateLicenseKeyData.device_limit` is typed by staff; nothing links it to the catalogue's `device_instances`, so staff can issue a key whose limit contradicts its plan.
- `generate_license_key` has no guard against a second key for the same org, so an org's effective capacity is the sum of its keys' limits.
- `AdminCustomer.deviceLimit` (the org value) is the only surface that disagrees with the enforced number.
- `seat_limit` is still present on origin/main; branch `chore/strip-dead-seat-limit` (230c45cd, owner's, no PR) removes it and edits the same files. This ticket does not touch it.
- API suite baseline on this commit: see iteration 0 in the ledger.

## Inputs and evidence sources

- ClickUp 86ak5mn0m: description, the owner's seat-model comment, and the architect decision (Aria, 2026-10-25) which the owner approved as written.
- Owner approval, quoted from the orchestrator brief: "Approve Aria's #7 design as written: remove CustomerOrg.device_limit, at most one valid key per org, seats derived from the plan at issuance. Go ahead."
- `docs/product/prds/SelahCue-Platform-PRD.md` section 12, FR-515, FR-516, OQ-P1, AS-P8.
- `docs/architecture/adr/ADR-0022-customer-identity-oidc-logto.md`, `docs/design/ADMIN-CONSOLE-UX-HANDOFF.md`.
- `apps/license_keys/state_machine.py` (which statuses can still be revived), `apps/catalogue/services.py` (`set_plan_grant`, `_plan_grant_map`).
- `.github/workflows/ci.yml` job `api (django)`.

## Scope

### In scope

- Remove `CustomerOrg.device_limit` and every reader and writer: model, `CreateCustomerData`, `create_customer` (validation, write, audit copy), self-signup, `AdminCustomer.deviceLimit`, `AdminCreateCustomerInput.deviceLimit`, and every test and evidence-seed site. Migration `selahcue_accounts` 0004, `RemoveField` only.
- Overlap guard in `generate_license_key`: lock the `CustomerOrg` row, keep the idempotent replay before the guard, one function holds the rule so a future extend or renew writer can call it. Blocking statuses ISSUED, ACTIVATED, EXPIRING, EXPIRED, SUSPENDED; non-blocking REVOKED, ARCHIVED, CONVERTED. Start equal to the other key's expiry is allowed. Existing overlapping orgs are grandfathered.
- Seats at issuance: the key's `device_limit` is set from the plan's resolved `device_instances`; issuance is refused when that value is absent, unlimited or below 1. `GenerateLicenseKeyData.device_limit` and the admin GraphQL `deviceLimit` input on `adminGenerateLicenseKey` are removed. A narrow issuance-only accessor in `catalogue/services.py`, not on the wire.
- Tests: activation limit on both routes (with mutation checks), re-mint allowance, overlap matrix, Postgres race, data-driven derivation, same number on every surface, schema introspection, first `MigrationExecutor` equivalence test in the repo.
- Docs: PRD section 12 row, FR-515 and OQ-P1 recording the owner's decision only; ADR-0022 lines 22 and 78; ADMIN-CONSOLE-UX-HANDOFF line 92.

### Non-goals

- `seat_limit` (separate branch `chore/strip-dead-seat-limit`, do not touch or merge it).
- A customer-portal limit API (follow-up).
- Changing the oldest-activated re-mint policy, devices/services.py behaviour, or publishing `device_instances` in the manifest.
- Renew, extend, revoke or convert writers (none exist on main); plan changes after issuance moving `device_limit` (FR-516, not built).
- Owner questions (c) and (d): left open, listed in the PR.
- `implementation/api/selahcue_api/settings.py`, root `deployments.md` and `docs/ops/DEPLOYMENT.md` (another agent's files).

### Constraints

- Strict TDD: failing test first, then the code; each guard is mutation-verified.
- Python imports at module top level; a function-local import only where a top-level one would create a cycle, with the cycle named in a comment.
- Forward-only migration; it removes one column and touches no key row.
- No Co-Authored-By trailer; plain commit messages; push only to the ticket branch; PR opened as Draft against main; no merge, no ready, no QA move.
- Tests create their own plans and seat values; the catalogue seed is not a fixture for seat counts (the reseed ticket 17tnw2az0gd will change it).
- Disk free above 15 GiB; no Docker.

### Assumptions and unknowns

- ASSUMED: the owner's approval covers the design including POLICY_DENIED on a plan with no seat value (Core and Pro seat counts are open under D7, so issuance on such a plan is refused until the owner sets them). Validation owner: the owner, in PR review.
- UNKNOWN: whether a local Postgres can be provisioned without Docker. If not, the Postgres race test is written and skip-guarded as the suite already does, and the report says exactly what ran.
- UNKNOWN: owner questions (c) one licence with a seat count different from its plan, and (d) ending a trial early before revoke and convert writers exist. Not decided here.

## Dependencies and approvals

- Architect decision (Aria): posted on the ticket, approved by the owner as written.
- 86ak10abc: ClickUp dependency on the ticket; not a code dependency of this change.
- Branch `chore/strip-dead-seat-limit` (owner): may land before or after; rebase when needed.
- Otto's ticket 17tnw2b9ab0 (settings.py, deployments docs): disjoint files; rebase if it merges first.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `CustomerOrg` has no `device_limit` field and the schema change is a single forward `RemoveField` | `pytest tests/test_org_device_limit_removed.py -q` and a read of `accounts/migrations/0004_*` | tripwire raises FieldDoesNotExist; migration operations are exactly one RemoveField | tests/test_org_device_limit_removed.py 4 passed; tests/test_migration_remove_org_device_limit.py::test_the_migration_is_a_single_forward_remove_field passed; mutants T1 (field re-added) and M3 (extra operation) RED | PASS |
| C-002 | yes | New activation is refused at the key's `device_limit` on both `/v1/activations` and `:with-session`, and the refusal point moves when the key's limit changes | `pytest tests/test_key_device_limit_is_the_only_limit.py -q` | key limit 2 admits 2 and refuses the 3rd on each route; raised to 3 admits the 3rd | tests/test_key_device_limit_is_the_only_limit.py: 7 tests across both routes passed; red-first evidence in the PR (collection errors / TypeError before the change) | PASS |
| C-003 | yes | Mutating the enforced read at `devices/services.py` :480 and :354 to a constant or a `customer.` attribute turns the tests red | mutation script run, each mutant fails then reverts | every mutant RED, revert GREEN | mutation harness: A1-A4 (:480 constant, customer.device_limit, customer.seat_limit, plan number) RED on both routes; R1-R3 (:354 constant, customer attr, customer.seat_limit) RED; every revert GREEN | PASS |
| C-004 | yes | Issuing a key whose dates overlap another blocking key of the same org is refused with POLICY_DENIED and nothing is written; non-blocking statuses and the date edges behave as decided | `pytest tests/test_one_valid_key_per_org.py -q` | parametrised matrix passes incl. start==expiry allowed and one second earlier refused; no key, assignment or audit row on refusal | tests/test_one_valid_key_per_org.py: 5 blocking statuses x 10 windows + 3 finished statuses x 7 overlapping windows passed; mutants G1-G7 RED | PASS |
| C-005 | yes | A retry of a successful issuance is still an idempotent replay, and another org's key never blocks | same file | passes | same file: replay, corrected-retry, other-org, grandfathered and guard-exclude tests passed; mutants G8 (guard before replay) and G9 (exclude ignored) RED | PASS |
| C-006 | yes | Two simultaneous issuances to one org produce exactly one key (Postgres), and removing the org lock turns that test red | `pytest tests/test_concurrency_postgres.py -q` on Postgres, with mutation | exactly one success; mutant RED | local Postgres 16.2 (pgserver, no Docker): test_concurrency_postgres.py 23 passed incl. 5 new tests (two-issuer race, retry-races-original, different orgs, lock strength, hash outside the lock); mutants L1 (org lock removed), L2 (no replay look under lock), L3 (FOR UPDATE instead of FOR NO KEY UPDATE), H1b (hash inside the lock) RED | PASS |
| C-007 | yes | The key's `device_limit` is read from the plan's `device_instances` at issuance; changing the plan value changes the next key only; a plan with an absent, unlimited or sub-1 value is refused | `pytest tests/test_key_seats_from_plan.py -q` | passes with tests' own plans and `set_plan_grant` | tests/test_key_seats_from_plan.py 14 passed (own plans, set_plan_grant, absent/unlimited/0/overflow/boolean/switched-off refused); mutants S1-S6 RED | PASS |
| C-008 | yes | One org reports the same number in the admin console, the manifest, the refresh response and at the activation refusal point; `AdminCustomer.deviceLimit` and the generate-key `deviceLimit` input are gone from the schema | `pytest tests/test_one_device_limit_everywhere.py -q` | all four equal; introspection lacks both | tests/test_one_device_limit_everywhere.py 2 passed (admin = manifest = refresh = refusal point = plan seats; schema introspection); mutants E1-E3 RED | PASS |
| C-009 | yes | Migrating forward preserves what every existing key grants, across org value equal, higher and lower than the key's, an org with no keys, an org with two overlapping keys, every status including SUSPENDED and ACTIVATED past expiry, keys at and below their limit | `pytest tests/test_migration_remove_org_device_limit.py -q` | before and after snapshots identical through the real services | tests/test_migration_remove_org_device_limit.py 5 passed on SQLite and on Postgres (13 scenarios, an org with no keys, 2 grandfathered keys; key table identical before and after); mutants M1, M2, M3 RED; runtime of the file went from 46.7 s (loaded machine) and 27.9 s (quieter, run back to back with the change) to 0.9 s and 1.6 s with a fast password hasher for this file only and the assertions unchanged; the grandfathered probes are now proven real (a refused, b admitted) instead of two identical VALIDATION_FAILED answers | PASS |
| C-010 | yes | No reader or writer of `CustomerOrg.device_limit` remains in code, tests or the evidence seed, and no client reads it; the scan has a positive control | scan script run on the tree and on a copy with a known site re-added | zero sites on the tree; the planted site is found | scan run during the work (the scanner and its logs are working files outside the repository, summarised here): 0 org sites in selahcue_api and tests (one intentional historical-model write in the migration test); planted control found; no client reads the field | PASS |
| C-011 | yes | The full API suite shows no regression against the origin/main baseline | `python -m pytest tests -q` | same pass set as baseline plus new tests; any failure that exists on baseline is named | Final head after merging origin/main 87786835 (PR #225), SQLite under env -i with SQL_DATABASE=:memory: as in make api-check: 1345 passed, 24 skipped, 1 xfailed, exit 0. Postgres 16.2: 1368 passed, 1 skipped, 1 xfailed, exit 0. Baseline on origin/main 4e744ac3 before this work: 1127 passed, 19 skipped, 1 xfailed | PASS |
| C-012 | yes | Django checks and migrations are clean | `python manage.py check`; `python manage.py makemigrations --check --noinput` | both exit 0 | manage.py check exit 0; makemigrations --check --noinput exit 0; makemigrations --check --dry-run --noinput exit 0 | PASS |
| C-013 | yes | No lint or format tool is configured for the API, so none is run; no new function-local import; the changed Python compiles | `python -m compileall` and a grep of the diff for indented imports | exit 0; no new local imports | no lint or format tool is configured for the API (pyproject.toml, CI api job); ruff F-rules on changed files report only 4 findings that exist on origin/main; compileall exit 0; no new indented import in the diff | PASS |
| C-014 | yes | Docs record the owner's decision: PRD section 12, FR-515, OQ-P1; ADR-0022; ADMIN-CONSOLE-UX-HANDOFF | review of the diff | the three docs state the approved design, no other PRD text changed | PRD section 12 row, FR-515, OQ-P1; ADR-0022 lines 22 and 78; ADMIN-CONSOLE-UX-HANDOFF line 92; validate_prd.py PASS | PASS |
| C-015 | yes | Branch is up to date with origin/main, pushed with no upstream on main, and a Draft PR exists against main | `git rev-list --count origin/main..HEAD`, `git merge-base --is-ancestor origin/main HEAD`, `gh pr view` | ancestor true; PR is Draft against main | origin/main d9aed4cb is an ancestor of the branch head (main moved by 4 desktop-only commits during the work, merged in, no API or docs file touched); branch tracks origin/fix/86ak5mn0m-remove-org-device-limit; Draft PR https://github.com/First-Pavilion/selahcue/pull/227 against main | PASS |
| C-016 | yes | The goal contract validates, structurally now and with `--completion` before the claim | `validate_goal_contract.py` | exit 0 both times | validator output: structural OK before work and after; --completion OK before this claim | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: each new test file above, run by name without `--exact`; mutation scripts for the activation reads, the overlap guard, the org lock and the plan derivation.
- Broader regression verification: the full API suite, `manage.py check`, `makemigrations --check --noinput`, mirroring the `api (django)` CI job as far as a local SQLite run (and a local Postgres if one can be provisioned) allows.
- Independent verifier: the orchestrator dispatches the reviewers (Cody, Shadow, Quinn, Vera); this run does not.
- Required environment: a Python 3.14 virtualenv outside the repository; SQLite; a local Postgres 16.2 from the `pgserver` pip package (no Docker), stopped and deleted afterwards.

## Iteration ledger

### Iteration 0

- Target criterion: baseline
- Hypothesis: the suite is green or has known failures on origin/main 4e744ac3
- Change or investigation: ran the full API suite on the untouched worktree
- Verifier executed: `python -m pytest tests -q -p no:cacheprovider`
- Result: 1127 passed, 19 skipped, 1 xfailed, exit 0 (7 min 3 s) on origin/main 4e744ac3
- New evidence: console output of that run (working logs are kept outside the repository; every result is summarised in this contract, the PR description and the ClickUp comments)
- Decision: iterate

### Iteration 1

- Target criterion: C-001 to C-009 (all new behaviour)
- Hypothesis: with the new tests written first, the existing services already enforce the key's limit, and the missing pieces are the field removal, the overlap guard and the plan-derived seats
- Change or investigation: wrote the seven new test files and the Postgres race tests first and ran them against the untouched code (RED: 23 failed, 6 errors, 1 collection error); then removed the field and the readers/writers, added the migration, the guard, the lock helper and the plan accessor
- Verifier executed: the new test files, then the full suite
- Result: new tests GREEN; the full suite showed one regression (test_the_refusal_follows_the_is_fallback_FLAG_not_the_plan_code: the former fallback plan has no seat count, so it is now correctly refused) which was fixed in the test by giving that plan a seat count
- New evidence: a retry that raced the original issuance was refused by the overlap guard; fixed by looking up the replay again after the org lock is taken, with a Postgres test
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-006 and every guard (mutation verification)
- Hypothesis: each guard turns at least one test RED when removed
- Change or investigation: mutation harness over 31 single-line mutants (activation reads, re-mint read, overlap window and status set, org lock, replay order, plan accessor bounds, surfaces, tripwire, migration)
- Verifier executed: a mutation harness kept outside the repository (it applies one textual change to one production file, runs the named tests with siblings, requires RED, restores the file byte for byte); the mutants and their killers are listed under "Mutation record" below
- Result: all mutants RED; two migration mutants first died of a setup error and not of an assertion, so they were rewritten with a proper dependency and re-run; the tripwire file also errored when run alone, fixed by marking it django_db
- New evidence: the final full suites on the final head are green on SQLite and Postgres 16.2
- Decision: gate-review

### Iteration 3 (round-1 review follow-up)

- Target criterion: findings of the four round-1 reviews (no blockers)
- Hypothesis: each finding is closed by a test that fails first or by a mutant it kills
- Change or investigation: merged origin/main 87786835; deploy order written down in the migration docstring and docs/ops/DEPLOYMENT.md 6d; lock changed to FOR NO KEY UPDATE; the secret hashed before the org lock; `deviceLimit` asserted on the suspend/reinstate payloads; the grandfathered probe keys fixed and proven real; the blocking set tied to LEGAL_TRANSITIONS; the remaining tests moved off seeded seat counts; the migration tests sped up; the blocking set renamed, neutral guard wording, latest-expiry hint; docs hygiene
- Verifier executed: the new and changed tests, 10 new mutants and a re-run of the 3 migration mutants, then both full suites
- Result: all new tests GREEN, all 10 new mutants and the 3 re-run migration mutants RED; full suites green on SQLite and Postgres (counts in C-011)
- New evidence: new code against the old schema fails to create an org (NOT NULL), which is why the split-release advice says to make the column nullable first
- Decision: gate-review

## Mutation record

Each line is one textual change to one production file, run against the named tests, expected RED, file restored afterwards. All were RED.

- Activation read (devices/services.py, new activation): constant 99; `customer.device_limit`; `customer.seat_limit`; the plan's number 5. Killer: test_key_device_limit_is_the_only_limit.py, both routes.
- Re-mint read (devices/services.py): constant 99; `customer.device_limit`; `customer.seat_limit`. Killer: test_remint_allowance_follows_the_key_limit.
- Overlap guard (license_keys/services.py): guard not called; window start inclusive; window end inclusive; SUSPENDED removed; EXPIRED removed; REVOKED added; other-org filter dropped; guard placed before the replay; `exclude_key_id` ignored; hint uses the earliest expiry; offset ignored when coercing. Killers: test_one_valid_key_per_org.py.
- Blocking set against the state machine: a fake CONVERTED -> ACTIVATED edge in LEGAL_TRANSITIONS; EXPIRED or SUSPENDED removed from the set, with only the state-machine test selected. Killer: test_the_blocking_statuses_cover_every_status_the_state_machine_can_revive.
- Concurrency (Postgres): org lock removed; second replay look removed; lock back to FOR UPDATE; hashing back inside the lock (also killed on SQLite by the ordering test). Killers: test_concurrency_postgres.py.
- Plan accessor: constant seats; 0 allowed; overflow allowed; boolean allowed; unlimited read as 1; refusal removed. Killers: test_key_seats_from_plan.py.
- Surfaces: manifest, refresh, admin key type and the lifecycle summary each off by one. Killers: test_one_device_limit_everywhere.py and the suspend/reinstate GraphQL test.
- Tripwire: the org field re-added. Killer: test_org_device_limit_removed.py.
- Migration: one that rewrites every key limit to 1; one that aligns each key to its org's value; one that does more than drop the column. Killers: test_migration_remove_org_device_limit.py.

## Risks and rollback

- Risks: the migration drops a column, so the previous release cannot run against the migrated schema and the new release cannot create an org against the old one; deploy order is therefore part of the change (see Rollback). The column holds no data the platform reads, and a re-added column carries its default of 1. Two simultaneous issuance requests rely on a row lock that SQLite does not provide, so the race guard is only observable on Postgres. A key's limit is copied at issuance, so moving a licence to another plan afterwards does not move its limit (unchanged from today; FR-516 is not built). Rebase conflicts with `chore/strip-dead-seat-limit` in the same service and test files.
- Rollback or recovery: Django reverses this RemoveField (it re-adds the column as NOT NULL with the Python default 1, about 12 ms on Postgres), and the migration test migrates backwards through it. Roll back with `manage.py migrate selahcue_accounts 0003` BEFORE starting the previous image. Deploy order is stop old instances, migrate (with `PGOPTIONS='-c lock_timeout=5000'`), start the new release; see the migration docstring and docs/ops/DEPLOYMENT.md section 6d. How deploys sequence `migrate` is unknown to the engineering team and is an owner question.

## Pause and escalation conditions

- A conflict with `chore/strip-dead-seat-limit` that needs a judgement call: stop and ask the orchestrator.
- Disk free below 15 GiB: stop.
- Any need to change `settings.py` or `deployments.md`: stop, they belong to another agent. (`docs/ops/DEPLOYMENT.md` gained section 6d in the round-1 follow-up, after that agent's PR #225 merged, at the coordinator's instruction.)
- Any request to change the approved design: escalate to the orchestrator and the owner.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5mn0m-remove-org-device-limit.md --completion`
- Validator result: OK (structural) and OK (--completion) on the final head
- Independent verification result: NOT YET RUN. Code, security, QA and performance reviews are dispatched by the orchestrator after this hand-off; the PR stays Draft until they clear
- Terminal state: GATE_REVIEW (all mandatory criteria PASS; not VERIFIED_COMPLETE because the independent reviews have not run)
- Remaining failed or blocked criteria: none. Not run locally: hosted CI (not a gate for this run), the Windows and macOS matrix, the marketing and desktop jobs (untouched)
- ClickUp final evidence comment: posted on 86ak5mn0m at hand-off
