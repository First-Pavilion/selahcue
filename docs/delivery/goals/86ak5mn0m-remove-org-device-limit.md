# Goal Contract — 86ak5mn0m-remove-org-device-limit

## Identity

- Goal ID: 86ak5mn0m-remove-org-device-limit
- Parent goal ID: NONE
- Title: An organisation's device limit is one number, the one on its licence key, copied from the plan at issuance; the dead org-level field is gone and a second valid key per org is refused
- Role: backend-engineer
- Status: DRAFT
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
| C-001 | yes | `CustomerOrg` has no `device_limit` field and the schema change is a single forward `RemoveField` | `pytest tests/test_org_device_limit_removed.py -q` and a read of `accounts/migrations/0004_*` | tripwire raises FieldDoesNotExist; migration operations are exactly one RemoveField | pytest output; migration file | PENDING |
| C-002 | yes | New activation is refused at the key's `device_limit` on both `/v1/activations` and `:with-session`, and the refusal point moves when the key's limit changes | `pytest tests/test_key_device_limit_is_the_only_limit.py -q` | key limit 2 admits 2 and refuses the 3rd on each route; raised to 3 admits the 3rd | pytest output | PENDING |
| C-003 | yes | Mutating the enforced read at `devices/services.py` :480 and :354 to a constant or a `customer.` attribute turns the tests red | mutation script run, each mutant fails then reverts | every mutant RED, revert GREEN | mutation log | PENDING |
| C-004 | yes | Issuing a key whose dates overlap another blocking key of the same org is refused with POLICY_DENIED and nothing is written; non-blocking statuses and the date edges behave as decided | `pytest tests/test_one_valid_key_per_org.py -q` | parametrised matrix passes incl. start==expiry allowed and one second earlier refused; no key, assignment or audit row on refusal | pytest output | PENDING |
| C-005 | yes | A retry of a successful issuance is still an idempotent replay, and another org's key never blocks | same file | passes | pytest output | PENDING |
| C-006 | yes | Two simultaneous issuances to one org produce exactly one key (Postgres), and removing the org lock turns that test red | `pytest tests/test_concurrency_postgres.py -q` on Postgres, with mutation | exactly one success; mutant RED | pytest output and mutation log, or an explicit statement that Postgres could not be run | PENDING |
| C-007 | yes | The key's `device_limit` is read from the plan's `device_instances` at issuance; changing the plan value changes the next key only; a plan with an absent, unlimited or sub-1 value is refused | `pytest tests/test_key_seats_from_plan.py -q` | passes with tests' own plans and `set_plan_grant` | pytest output | PENDING |
| C-008 | yes | One org reports the same number in the admin console, the manifest, the refresh response and at the activation refusal point; `AdminCustomer.deviceLimit` and the generate-key `deviceLimit` input are gone from the schema | `pytest tests/test_one_device_limit_everywhere.py -q` | all four equal; introspection lacks both | pytest output | PENDING |
| C-009 | yes | Migrating forward preserves what every existing key grants, across org value equal, higher and lower than the key's, an org with no keys, an org with two overlapping keys, every status including SUSPENDED and ACTIVATED past expiry, keys at and below their limit | `pytest tests/test_migration_remove_org_device_limit.py -q` | before and after snapshots identical through the real services | pytest output | PENDING |
| C-010 | yes | No reader or writer of `CustomerOrg.device_limit` remains in code, tests or the evidence seed, and no client reads it; the scan has a positive control | scan script run on the tree and on a copy with a known site re-added | zero sites on the tree; the planted site is found | scan log | PENDING |
| C-011 | yes | The full API suite shows no regression against the origin/main baseline | `python -m pytest tests -q` | same pass set as baseline plus new tests; any failure that exists on baseline is named | pytest output | PENDING |
| C-012 | yes | Django checks and migrations are clean | `python manage.py check`; `python manage.py makemigrations --check --noinput` | both exit 0 | command output | PENDING |
| C-013 | yes | No lint or format tool is configured for the API, so none is run; no new function-local import; the changed Python compiles | `python -m compileall` and a grep of the diff for indented imports | exit 0; no new local imports | command output | PENDING |
| C-014 | yes | Docs record the owner's decision: PRD section 12, FR-515, OQ-P1; ADR-0022; ADMIN-CONSOLE-UX-HANDOFF | review of the diff | the three docs state the approved design, no other PRD text changed | git diff | PENDING |
| C-015 | yes | Branch is up to date with origin/main, pushed with no upstream on main, and a Draft PR exists against main | `git rev-list --count origin/main..HEAD`, `git merge-base --is-ancestor origin/main HEAD`, `gh pr view` | ancestor true; PR is Draft against main | command output | PENDING |
| C-016 | yes | The goal contract validates, structurally now and with `--completion` before the claim | `validate_goal_contract.py` | exit 0 both times | validator output | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: each new test file above, run by name without `--exact`; mutation scripts for the activation reads, the overlap guard, the org lock and the plan derivation.
- Broader regression verification: the full API suite, `manage.py check`, `makemigrations --check --noinput`, mirroring the `api (django)` CI job as far as a local SQLite run (and a local Postgres if one can be provisioned) allows.
- Independent verifier: the orchestrator dispatches the reviewers (Cody, Shadow, Quinn, Vera); this run does not.
- Required environment: Python 3.14 virtualenv in the scratchpad; SQLite; Postgres only if it can be provisioned without Docker.

## Iteration ledger

### Iteration 0

- Target criterion: baseline
- Hypothesis: the suite is green or has known failures on origin/main 4e744ac3
- Change or investigation: ran the full API suite on the untouched worktree
- Verifier executed: `python -m pytest tests -q -p no:cacheprovider`
- Result: recorded below once complete
- New evidence: scratchpad log w1-86ak5mn0m-impl-baseline.log
- Decision: iterate

## Risks and rollback

- Risks: the migration drops a column, so a rollback to the previous release needs the column back; it holds no data the platform reads, but a re-added column would carry its default of 1. Two simultaneous issuance requests rely on a row lock that SQLite does not provide, so the race guard is only observable on Postgres. A key's limit is copied at issuance, so moving a licence to another plan afterwards does not move its limit (unchanged from today; FR-516 is not built). Rebase conflicts with `chore/strip-dead-seat-limit` in the same service and test files.
- Rollback or recovery: revert the merge commit; a reverse migration is not provided (forward-only by decision). To restore the old column on a deployed database, add it back as a PositiveIntegerField default 1; no behaviour depended on it.

## Pause and escalation conditions

- A conflict with `chore/strip-dead-seat-limit` that needs a judgement call: stop and ask the orchestrator.
- Disk free below 15 GiB: stop.
- Any need to change `settings.py`, `deployments.md` or `docs/ops/DEPLOYMENT.md`: stop, it belongs to another agent.
- Any request to change the approved design: escalate to the orchestrator and the owner.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/86ak5mn0m-remove-org-device-limit.md --completion`
- Validator result: PENDING
- Independent verification result: PENDING (reviewers dispatched by the orchestrator)
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
