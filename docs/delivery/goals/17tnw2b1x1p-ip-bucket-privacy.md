# Goal Contract — TASK-17tnw2b1x1p

## Identity

- Goal ID: TASK-17tnw2b1x1p
- Parent goal ID: WAVE3-SELAHCUE-20
- Title: Keep visitor IPs out of throttle cache keys and document degraded-send/rotation behavior
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b1x1p
- Created: 2026-10-30
- Updated: 2026-10-30
- Maximum iterations: 8
- Independent verification required: yes

## Objective

All existing IP throttle consumers use purpose-separated keyed HMAC identities rather than revealing raw addresses in cache keys, while IP resolution/sharing and existing budget semantics stay unchanged. The operations runbook accurately explains effective per-worker degraded send ceilings and affected-budget resets on SECRET_KEY rotation.

## Baseline

Fresh actual main e5a1611b728901811b6427f7cff2ded0ccfa4dcd includes reviewed/QA ADV. Complete fresh live task17tnw2b1x1p has no comments/dependencies, one linked predecessor86ak65mj5 (QA, full saved description/comments read during qualification). Native decorator interpolates resolved client_ip directly; generic guards interpolate identities supplied by browser IP budget consumers. Existing IPv4-mapped normalization and IPv6/64 identity sharing are intentional. Global-first bounded cardinality and differentiated native/bootstrap/mail outage behaviors already exist.

## Inputs and evidence sources

- Full api-qualification/17tnw2b1x1p-dispatch-live.json, 86ak65mj5.json and source-backed qualifications.md; parent frozen selected20.
- Current throttling services/guards/decorators, account service budget consumers, existing throttle/IPv6/response/reset/cache/circuit tests and DEPLOYMENT.md.
- Repository CLAUDE.md, backend/goal operating contracts and explicit parent author/root ownership.

## Scope

### In scope

- Dedicated-purpose/key-derived HMAC representation for existing IP bucket identities at all actual cache-key boundaries, with no raw visitor IP in observed keys.
- Reuse existing configured SECRET_KEY with dedicated purpose separation, rather than inventing a new deployment secret or provisioning decision; document derivation and rotation behavior explicitly.
- Preserve IPv4 mapping, IPv6/64 sharing, trusted proxy resolution, distinct scopes, global-first ordering/count/TTL and current outage/circuit/degraded/native-bootstrap policy.
- Runbook ceiling formula limit × number of workers and actual degraded-send configuration knobs; precise affected SECRET_KEY-derived budget reset semantics, without claiming unaffected global counters rotate.
- Owned throttling services/guards/decorators, directly relevant tests and docs/ops/DEPLOYMENT.md plus this contract.

### Non-goals

- Owner-held WQU budget reordering/availability/cardinality trade-off; held PR185/233; new authentication, privacy retention, provisioning or deployment policy.
- Redis round-trip/atomicity optimization (next WVF ticket), new limits/windows, account policy changes, changing client_ip output or audit identity design.

### Constraints

- Own managed isolated codex/17tnw2b1x1p-ip-bucket-privacy branch; not alone, preserve other authors' changes.
- Actual hosted real-consumer key capture RED before minimal production fix; meaningful raw-key mutation/restoration, not copied helper-only evidence.
- No local project runtime/import/test/install/build/container/benchmark under host paging; local stdlib source/AST/Git/goal checks only.
- Root owns ClickUp/status/comments, four independent reviews/publication, conditional merge/tree proof and exact QA. Author ordinary push/draftPR/immediate attachment/bounded workflow-only diagnostics permitted.

### Assumptions and unknowns

- UNKNOWN exact key inventory and executed outcomes until source tracing and hosted key capture; do not infer privacy from helper shape alone.
- Dedicated derivation is a cryptographic namespace for IP cache identities using the already configured secret; independent secret provisioning is not authorized or needed by the stated rotation AC.

## Dependencies and approvals

- User-authorized frozen wave selection and parent assignment cover this existing ticket and valid remediation. ADV predecessor merged/QA; no declared blocker.
- WVF remains queued until this ticket merges and root dispatches. Preserve shared throttle file ownership; do not start later units.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All actual IP cache-key paths inventoried and privacy gap observed in meaningful hosted RED | Source consumer inventory plus hosted request/service key capture with positive controls | Every native/browser IP consumer covered; actual raw-key privacy failures distinct from setup errors | api-ip-bucket-privacy inventory/red manifest/raw | PENDING |
| C-002 | yes | IP cache keys use a dedicated-purpose keyed hash with no raw address in any observed key | Hosted real consumer/cache-key capture, stable-secret/different-IP/rotation and domain-separation controls | No IPv4/full IPv6/prefix leaks; distinct IPs differ, same bucket shares, stable secret stable, changed secret changes affected identities | Focused GREEN and full API raw logs | PENDING |
| C-003 | yes | Existing admission/sharing/state/outage semantics remain intact | Existing full throttle/reset/cache/circuit/response suite plus meaningful new controls and raw-key mutation/restoration | Proxy/mapped IPv4/IPv6/64, global-first cardinality, limits/count/TTL/outage/degraded/native policies preserved; mutant fails and restored source passes | Hosted sensitivity/regression receipts | PENDING |
| C-004 | yes | Operations docs accurately describe degradation and rotation | Source-derived docs cross-check and independent review | Formula/knobs apply to send claims per worker; browser/native distinction explicit; only affected secret-derived budgets reset once | DEPLOYMENT.md diff and review reports | PENDING |
| C-005 | yes | Full final normal API integration gate passes on frozen current source | Hosted normal API20m check, migration drift and full pytest with Postgres16/Redis7 | Required gates pass; existing intentional study skip explicit; no hidden waiver | Exact-source normal CI metadata/raw logs | PENDING |
| C-006 | yes | All four final reviews and root integration/QA gates pass | Cody/Quinn/Vera/Shadow current receipts; reviewed-prefix/actual merge tree and exact qa readback | No unresolved finding; approved result merged and linked ticket qa | Root consolidated/review/merge/QA receipts | PENDING |

## Verification plan

- Focused verification: all real key consumers and purpose/secret/IP sharing controls; observed cache-key boundary captures, actual raw-key mutation/restoration.
- Broader regression verification: normal full API suite with existing budget/outage/socket/TTL/circuit and authentication assertions preserved.
- Independent verifier: root-coordinated Cody/Quinn/Vera/Shadow; author does not independently approve own work.
- Required environment: hosted Linux current Python/API services; local source/stdlib/Git/static/goal checks only.

## Iteration ledger

### Iteration 1

- Target criterion: C-001.
- Hypothesis: native decorator and generic guard cache-key interpolation jointly expose raw resolved IP buckets; one purpose-separated representation can cover all existing consumers without changing admission.
- Change or investigation: full live task and source-qualified prerequisites; fresh isolated worktree at actual e5; source consumer and existing fixture inventory.
- Verifier executed: Git base/branch status, source reads, structural goal validator before substantive edits.
- Result: baseline/scope established; actual key-capture tests and hosted RED pending; no production fix.
- New evidence: full dispatch-live packet, qualifications.md and this contract.
- Decision: iterate

## Risks and rollback

- Risks: missing a key consumer, altering scope/bucket sharing, leaking identity through another cache key, misdescribing degraded availability or rotation, or changing global-first cardinality.
- Rollback or recovery: one scoped PR, immutable real-consumer evidence; retain existing behavior tests and distinguish old keys expiring naturally from once-reset new budgets.

## Pause and escalation conditions

- Stop for new owner/provisioning/product policy or destructive/production operations; do not resolve WQU implicitly.
- Yield immutable checkpoints during hosted waits and route valid findings through implementing author; no next unit before root dispatch.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b1x1p-ip-bucket-privacy.md
- Validator result: PASS structural validation before substantive tests
- Independent verification result: pending
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-006 pending
- ClickUp final evidence comment: root-owned, pending
