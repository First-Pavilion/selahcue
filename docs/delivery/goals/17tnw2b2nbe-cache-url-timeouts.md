# Goal Contract — 17tnw2b2nbe

## Identity

- Goal ID: 17tnw2b2nbe
- Parent goal ID: NONE
- Title: Refuse cache URL query timeout overrides at startup
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/90131572460/17tnw2b2nbe
- Created: 2026-10-29
- Updated: 2026-10-29
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Reject either Redis socket timeout query option in the cache URL, including in-range values, with a secret-free startup error. Keep the two validated environment variables as the supported timeout channels.

## Baseline

Verified main 8f7d610e includes prerequisite PR186 (d064bd96). Redis-py parses URL query arguments and gives them precedence over Django backend options. Existing tests only prove URL-free timeout options.

## Inputs and evidence sources

- Live ClickUp description, comments and coordinator policy: /private/tmp/selahcue-batch20-20261029/additional-live-payloads.md.
- API settings, cache timeout tests, pinned Redis client parser and deployment documentation.

## Scope

### In scope

- Settings startup guard, cache timeout tests, deployment documentation and this execution record.

### Non-goals

- Broader URL validation, broker transport, circuit breakers, throttle budgets and account semantics.

### Constraints

- Match Redis query-name decoding; never echo URL, credentials or query values.
- Preserve other query options and URLs without timeout options.
- Root owns publication, independent reviews, CI, merge and ClickUp updates. Shared workspace: do not revert others.

### Assumptions and unknowns

- Verified coordinator chooses strict refusal, including valid timeout values; no owner decision pending.

## Dependencies and approvals

- Prerequisite PR186 verified merged. User authorizes existing-ticket delivery and conditional merge. Parent provides live source of truth and owns external actions.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Reproduce effective pool override then reject both timeout names and encoded keys | cache timeout regression tests and pool baseline probe | Baseline RED; corrected startup refuses with safe diagnostic | /private/tmp/selahcue-batch20-20261029/17tnw2b2nbe-red.log and focused.log | PASS |
| C-002 | yes | Preserve other query options, environment bounds and healthy/stalled cache behavior | entire test_cache_socket_timeouts.py against Redis | All tests pass, no skipped Redis control | /private/tmp/selahcue-batch20-20261029/17tnw2b2nbe-focused.log | PASS |
| C-003 | yes | Document supported channels and pass documentation guards after final prose | test_deployment_env_docs.py plus system/migration/goal/diff checks | All checks pass | /private/tmp/selahcue-batch20-20261029/17tnw2b2nbe-static.log and focused.log | PASS |
| C-004 | yes | Full API CI passes on frozen final revision | Root hosted CI | Clean full API job | Root CI evidence pending | BLOCKED |
| C-005 | yes | All four independent reviews pass after remediation | Cody, Quinn, Shadow and Vera reports | All PASS at final revision | Root review reports pending | BLOCKED |
| C-006 | yes | Merge and QA handoff verified | Root remote merge and ClickUp read-back | Merged PR and linked ticket QA persisted | Root delivery evidence pending | BLOCKED |

## Verification plan

- Focused verification: RED regression first, then entire cache timeout module with real Redis.
- Broader regression verification: deployment docs/guards and frozen-head hosted full API CI.
- Independent verifier: root dispatches Cody, Quinn, Vera and Shadow.
- Required environment: existing Python runtime, dedicated Redis namespace; no production data or new services.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: rejecting decoded timeout query names before constructing the backend prevents Redis URL precedence bypass without changing other options.
- Change or investigation: inspect pinned client and reproduce actual lazy pool kwargs; add regression cases before implementation.
- Verifier executed: whole test_cache_socket_timeouts.py using dedicated PostgreSQL database batch20_cache_url and Redis db14; actual lazy pool baseline probe.
- Result: baseline 32 failed, 67 passed in 14.88s. Actual pool timeout was 86400 or 0 despite supplied 0.5; encoded socket%5ftimeout also became 86400. Initial settings-only selection hit existing session catalogue fixture before test bodies; whole-module DB setup resolves that environment issue.
- New evidence: source parser uses urllib.parse.urlparse and parse_qs; query kwargs replace supplied pool kwargs.
- Decision: iterate.

### Iteration 2

- Target criterion: C-001, C-002, C-003.
- Hypothesis: reject decoded query names before backend construction; leave other options untouched.
- Change or investigation: add strict name guard and deployment migration instructions, plus compatibility controls.
- Verifier executed: complete cache timeout, deployment environment documentation and deployment guard modules on PostgreSQL with real Redis; manage.py check; makemigrations --check --dry-run; structural Goal Contract validation and git diff --check.
- Result: 216 passed in 19.45s, no skips; system check exits zero with existing proxy-count warning W001 at default count zero; no migration changes. Startup, encoded/blank/in-range/duplicate query refusal and secret redaction pass. Redis/rediss/unix lazy pool compatibility, unrelated query options, environment bounds, real healthy Redis and stalled-server controls pass.
- New evidence: guard emits fixed names only, never user-controlled values.
- Decision: handoff after a fresh gate covering this final evidence edit; root owns full CI and independent reviews.

## Risks and rollback

- Risks: deployments using URL timeouts intentionally must move them to the documented environment variables before startup.
- Rollback or recovery: remove timeout query arguments and set the two existing timeout variables; revert this ticket only if necessary, which reopens bypass.

## Pause and escalation conditions

- Stop for scope-changing owner policy or unexpected unrelated source conflict; root owns final delivery gates.

## Final evaluation

- Validator command: python /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2nbe-cache-url-timeouts.md
- Validator result: structurally valid; completion intentionally remains blocked by C-004, C-005 and C-006.
- Independent verification result: pending root dispatch.
- Terminal state: BLOCKED pending independent reviews, full CI and delivery.
- Remaining failed or blocked criteria: C-004, C-005, C-006.
- ClickUp final evidence comment: parent owns updates using this evidence record.
