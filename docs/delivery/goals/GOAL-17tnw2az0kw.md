# Goal Contract — GOAL-17tnw2az0kw

## Identity
- Goal ID: GOAL-17tnw2az0kw
- Parent goal ID: NONE
- Title: API installs reproducibly from uv.lock across local, CI and Docker workflows
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az0kw
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Replace the API's unlocked pip installation with a pinned uv project workflow that consumes a complete committed lock, preserves local safety controls and makes deliberate dependency updates reviewable.

## Baseline
Verified main c0325d52e809847fac141a605b74a7e6d7de7021. Existing pyproject declares exact direct/dev pins and Python >=3.12; CI/Docker use3.14. setuptools84.1.0 and dev psycopg[binary]3.3.6 are already declared. Local api_venv.py installs with pip and stamps only manifest/interpreter; API CI/Docker additionally pass a floating psycopg range. No uv.lock exists. Docker Desktop local context desktop-linux is available after permitted read-only inspection. Status In Progress read back; start comment1400430000278569.

## Inputs and evidence sources
- Complete live ticket, preserved security history and Diego scope update1400430000278565.
- Makefile, API manifest/Docker/docs and local guard/mutation tests, current workflow and Dependabot config.
- Official astral-sh/uv source docs/releases and actual tool behavior; repository pinned interpreter/runtime.

## Scope
### In scope
- API uv.lock/build profile, pinned uv bootstrap, local safety guards, API CI/cache, Docker and update automation/docs.
- Real fresh-install/profile parity, artifact-integrity negatives, install-free verification and targeted update exercise.
### Non-goals
- Application/API/schema/permission/data changes, unrelated dependency upgrades, other ecosystems, deployment or installers.
- Authentication/tenancy/query/migration/business rules remain unchanged; their implementation criteria are inapplicable, regression suite remains required.
### Constraints
- Preserve direct pins/Python support and per-checkout ownership/symlink/concurrency/interruption protections.
- Do not modify primary checkout/user mobile lock or another agent's files. One ticket/branch/PR; root owns four reviews/merge/QA.
- Never claim pre-merge dependency graph indexing or hosted checks from local evidence.
### Assumptions and unknowns
- RESOLVED locally: wheel-only locked third-party/build group sync plus offline non-isolated root build passes, with actual hash-corruption refusal.
- RESOLVED: host/Docker profiles match exactly; fresh pip drift under14-day policy is explicitly documented, with unchanged direct pins.

## Dependencies and approvals
- User selected uv and authorized next wave. Parent assigns Kenji implementation with coordinated DevOps boundaries.
- Official uv version must be fixed; preserve repository update/cooldown policy. No production/provider access.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | API lock covers runtime/dev/driver/transitives and build profile without unrelated direct-version changes | fresh pip baseline, uv lock/sync, parsed profiles/manifests | declared versions unchanged and matching-platform package maps explained | docs/delivery/evidence/17tnw2az0kw.md | PENDING |
| C-002 | yes | Deliberate local sync is locked while verification is install-free and all ownership/freshness controls remain | real guard suite/mutations plus stale/missing lock, touch/hash, foreign/symlink/concurrency/interruption cases | valid checks pass, unsafe/stale cases fail with instruction | guard tests and evidence | PENDING |
| C-003 | yes | Artifact/build integrity is enforced without unlocked build downloads | corrupted-artifact negative, locked backend install and offline project build | corrupt artifact refused, complete valid installation/import succeeds offline build | focused integration evidence | PENDING |
| C-004 | yes | CI and Docker consume same lock/profile with unchanged service behavior | workflow controls, Docker build/outside-cwd API/Celery/driver checks, full API suite | actual commands exit0, no startup downloads or floating driver | evidence and source CI | PENDING |
| C-005 | yes | Updates and dependency visibility use supported uv integration with concrete versions | official integration docs, isolated targeted-update exercise, ingestion-path verification | bounded update diff, complete known-version graph ingestion path | evidence/docs | PENDING |
| C-006 | yes | All required local and independent current-source gates pass | complete API/guard/mutation checks plus root Cody Shadow Quinn Vera and hosted CI | completed local results and four Pass/current CI | PR/root reports | PENDING |
| C-007 | yes | Actual main graph/readback and integration disposition are recorded | root post-merge dependency graph/SBOM and QA readback | actual indexed versions recorded, no premature Complete claim | ClickUp/root follow-up | PENDING |

## Verification plan
- Focused verification: actual local sync/verify, guard mutations, stale lock, artifact mismatch and offline build tests.
- Broader regression verification: full API local checks with named service skips, hosted Postgres/Redis, Docker, workflow/manifest checks.
- Independent verifier: root coordinates Cody, Shadow, Quinn and Vera.
- Required environment: local macOS Python3.14, compatible system3.9 guard launcher, pinned uv; local Docker Desktop; hosted Linux API services.

## Iteration ledger
### Iteration1
- Target criterion: C-001 through C-003.
- Hypothesis: explicit locked build group, binary third-party sync and offline local project build permit one reproducible lock without hidden build downloads.
- Change or investigation: establish actual baseline and failing lock/freshness/integrity tests before implementation.
- Verifier executed: original lock-only regression RED exit1, focused locked install/freshness GREEN.
- Result: first two-stage hypothesis works with real uv; full evidence in docs/delivery/evidence/17tnw2az0kw-api-uv.md.
- New evidence: official release metadata and local pinned-runtime/tool availability inspected.
- Decision: iterate.

### Iteration2
- Target criterion: C-001 through C-005 local portions.
- Hypothesis: fresh cached editable reuse must not hide failed builds; main graph requires explicit submission because static graph lacks uv support.
- Change or investigation: disable cache for final offline build; real hash-bearing HTTP-wheel corruption test; complete selected-extra graph exporter and least-privilege main-only snapshot job.
- Verifier executed: full51-case baseline/57-mutation proof, full2330-test API run, Docker build/outside-cwd/health/profile parity, targeted isolated update and graph negative tests.
- Result: all local exit0;53 intentional service skips await hosted Postgres16/Redis7. Fresh unlocked pip differs by11 newer transitives and six; lock deliberately follows14-day cutoff and all direct pins remain identical.
- New evidence: evidence document records exact versions/provenance and actual run limits. Real artifact hash mismatch rejected; host/Docker maps identical37 installed distributions.
- Decision: local implementation ready for parent independent review and hosted gates; no completion/QA claim.

## Risks and rollback
- Risks: incomplete build graph, resolver drift, accidentally syncing during verification or weakening owned-venv guards.
- Rollback or recovery: revert isolated migration; do not delete foreign environments or touch production data.

## Pause and escalation conditions
- Escalate any required integrity/build exception, incompatible direct-pin drift, unavailable Docker/host gate or owner-level scope decision.
- Stop after four iterations or three materially different failed attempts without useful new evidence; no silent gate waiver.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-17tnw2az0kw.md
- Validator result: structural validation exit0.
- Independent verification result: pending root reviews.
- Terminal state: ACTIVE.
- Remaining failed or blocked criteria: local C-001/C-002/C-003 passed; C-004/C-005 local evidence passed with hosted/main ingestion pending; C-006/C-007 external reviews/CI/merge/indexing gates pending.
- ClickUp review handoff evidence comment:1400430000278609; status code review read back. Final integration evidence remains parent-owned.
