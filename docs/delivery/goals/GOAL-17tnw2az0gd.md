# Goal Contract — GOAL-17tnw2az0gd

## Identity
- Goal ID: GOAL-17tnw2az0gd
- Parent goal ID: NONE
- Title: Data-driven unpriced plan catalogue and weekly allowances
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az0gd
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Implement Aria's approved data-only catalogue contract: append-only effective prices, independent positive ranks, exactly three unpriced plans, conservative pending limits and weekly dimensions.

## Baseline
Verified main b3ae75f824fe8e43b18836d3d661dc996dce98bc. Existing four-plan seed0002 must remain unchanged; two fallback refusals block Free once reseeded. Plan has display order but no rank/prices. Scope aliases and licence assignments PROTECT Plan. Existing key device_limit is copied once at issuance and must never be rewritten. Root read Aria PASS1400430000278606 and actual In Progress/start comment before implementation.

## Inputs and evidence sources
- Complete task17tnw2az0gd and historical comments1400430000022719/1400430000204335.
- Refreshed Aria contract1400430000278606, consolidated approved snapshot; ADR0027 D2-D4/security/rollback.
- Existing catalogue models/services/cache/signals, issuance/manifest and tests; official SIX ISO4217 current/historical snapshots.

## Scope
### In scope
- Price data/service/history, pinned offline currency metadata, rank and transactional reseed/ref safety, fallback refusal removal and regression/migration evidence.
### Non-goals
- Staff/public endpoints, billing, usage/provider enforcement, org effective plan, commercial price/currency/interval decisions or final Core/Pro launch limits.
- No deployment, credentials, other ticket changes or primary/frozen worktree edits.
### Constraints
- No price rows seeded; explicit1-device/2-screen/0-NDI pending grants for undecided tiers; weekly20/50/80 and notes1/5/10; watermark on/off/off.
- New dimension keys, inactive old monthly key, private device grant unpublished, existing seat limits preserved.
- Unexpected custom migration shapes fail clearly; backup restore required for destructive ref repoints; price history never silently erased.
### Assumptions and unknowns
- Verified root-approved conservative oldPRO/obsolete reference repoints to Free; no commercial equivalence is inferred.
- Historical SIX list omits minor-unit exponents: preserve readable historical codes/raw stored amounts; never infer cents or permit new pricing on an unknown/non-numeric exponent.
- Independent reviews, hosted service-backed tests and final integration are parent-owned gates.

## Dependencies and approvals
- Aria prerequisite PASS1400430000278606; root UI In Progress/start evidence readback authorizes implementation.
- Final price/launch-limit decisions remain deferred; this build seeds unpriced/restrictive data.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| C-001 | yes | Effective append-only accountable prices distinguish absent/null/zero with currency/interval validation | model/service/history/invalid tests | exact as-of/boundary/future/history, invalid writes atomic | tests and evidence | PASS |
| C-002 | yes | Concurrent duplicate timestamps deterministically conflict and preserve history | unique/atomic/concurrent tests | one price/audit success; other conflict | Postgres/local evidence | PASS |
| C-003 | yes | Exactly three ranked unpriced plans with conservative pending grants and new weekly dimensions | seed/data tests | exact approved rows, no inherited unlimited limits | tests | PASS |
| C-004 | yes | Both fallback gates removed together; explicit/unknown/finite-seat rules preserved | assignment/issuance/manifest negatives | Free/Core/Pro work; invalid seat no partial key/audit | tests | PASS |
| C-005 | yes | Data edits update next signed manifest without restart; private device/price never published | actual note5-to6 and signed payload tests | fresh manifest6, instances_limit unchanged | tests | PASS |
| C-006 | yes | Transactional migration safely repoints known old references, preserves keys, rejects unsafe shapes and documents recovery | forward/recovery/migration tests | original0002 unchanged, revision bumped, no price history loss | migration evidence | PASS |
| C-007 | yes | Tier-name sweep/mutation and bounded stale-cache protections remain effective | sweep CORE mutation/cache tests | forbidden branch caught, cache bounds/stale behavior pass | tests | PASS |
| C-008 | yes | Current API checks, full regression and four independent reviews pass | makemigrations/fullpytest/Cody Shadow Quinn Vera/currentCI | all actual completed gates | parent PR reports | PENDING |

## Verification plan
- Focused verification: RED seed contract; prices valid/invalid/history/accountability/concurrency, migration/ref/revision and real signed manifest transition.
- Broader regression verification: current uv install-free API gate, complete suite with explicit local service skips; hosted Postgres16/Redis7.
- Independent verifier: parent dispatches Cody, Shadow, Quinn and Vera.
- Required environment: owned managed worktree, pinned uv0.13.4/Python3.14; task-owned temporary databases only.

## Iteration ledger
### Iteration1
- Target criterion: C-001/C-003/C-006.
- Hypothesis: additive schema then transactional audited data migration then rank constraints safely separates data changes from PostgreSQL pending-trigger DDL.
- Change or investigation: trace all protected Plan refs, explicit seat contract, price audit boundaries and pinned ISO metadata before code.
- Verifier executed: first RED seed contract exits1, showing old LEGACY/PLATINUM present and CORE absent.
- Result: seed regression GREEN after staged schema/data/rank migrations; real migration/recovery probes pass, including preserved key fields and protected history.
- New evidence: only scope aliases and licence assignments currently protect Plan; root confirms oldPRO refs must not silently receive newPro grants.
- Decision: iterate within approved scope.

### Iteration2
- Target criterion: C-001/C-002/C-004/C-005/C-007/C-008.
- Hypothesis: existing fixture assumptions must move to weekly/pending data while preserving positive controls; price writes need actual database concurrency and atomic audit proof.
- Change or investigation: internal append-only price service, explicit permission/validation, temporal/history/DB negatives, new signed note5-to6 proof, CORE runtime-branch mutation and migration-backed fixture adaptation.
- Verifier executed:169 focused catalogue tests; actual PostgreSQL16 price suite34 passed including two-writer collision; four isolated migration/recovery probes; full API gate.
- Result: focused/PG checks pass. Full suite2365 passed/54 service skips/57 subtests, one obsoletePlatinum positive fixture failed; no production-code failure. Corrected both positive and NUL-prefixed old plan fixtures to Core.
- New evidence: source clone mutation caught; history end reads bounded to one query; unsupported custom state and destructive reverse refuse atomically.
- Decision: iterate to final full-gate verification after the identified fixture correction.

### Iteration3
- Target criterion: C-008 and final criterion readback.
- Hypothesis: correcting the remaining obsolete fixture yields a clean complete API gate without weakening input guards or seed contract.
- Change or investigation: current Core fixture in control-character positive/negative cases; final documentation and source checks.
- Verifier executed: final full install-free API gate2369 passed/54 service skips/57 subtests exit0; final actual PostgreSQL36 passed including concurrent/NUL controls; four migration/recovery probes and CORE branch mutation pass.
- Result: all local criteria pass. Actual PostgreSQL NUL lookup RED2fail led to scalar validation before queries; final PG and full API reruns pass. All local subprocesses complete and task containers removed; parent owns hosted CI/four-review gates.
- New evidence: no package/uv/0002 changes; same protected migration and actual PostgreSQL evidence retained.
- Decision: review only after actual completed gates; maximum4 retained for independent-review remediation if needed.

## Risks and rollback
- Risks: existing assignments inheriting new commercial rights, unlimited defaults, stale cache, price history edits, PostgreSQL schema/data transaction interactions.
- Rollback or recovery: pre-migration database backup; revert code and restore data together. Never reconstruct custom assignments from seed constants or erase prices to force a downgrade.

## Pause and escalation conditions
- Escalate unexpected protected refs/custom plans, missing authoritative currency facts or a required architecture/security exception.
- Stop after four iterations or three materially different failed attempts without useful evidence; no gate waiver.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2az0gd.md
- Validator result: structural validation exit0 after correcting the predicate heading.
- Independent verification result: pending.
- Terminal state: GATE_REVIEW for implementation; overall Goal ACTIVE pending independent integration gates.
- Remaining failed or blocked criteria: C-001 through C-007 local PASS; C-008 current hosted CI and all four independent reviews pending. No owner launch-configuration decision blocks this unpriced build.
- ClickUp final evidence comment: parent UI tracking.
