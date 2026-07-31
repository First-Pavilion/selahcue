# Goal Contract — TASK-86ajnx548-memory-caps

## Identity

- Goal ID: TASK-86ajnx548-memory-caps
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-ups M2/M3/M4)
- Title: Hard-cap the three unbounded-growth structures the audit flagged (plan items · LAN sessions · transcript DOM)
- Role: backend-engineer (M2 core/data, M3 lan) + frontend-engineer (M4 operator webview)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — follow-ups queued in the audit report §4)
- Created: 2026-07-31
- Independent verification required: yes (adversarial Workflow review + bounded-memory tests per structure)
- Maximum iterations: 10

## Objective

Close the three MEDIUM no-leak-rule gaps from [`docs/quality/AUDIT-memory-perf-latency.md`](../../quality/AUDIT-memory-perf-latency.md): each is a collection that grows on a reachable (authenticated/host-driven) path with **no hard cap and no bounded-memory test**. Add a hard cap enforced at the growth ingress AND a bounded-memory test for each — satisfying the project rule that every collection is bounded with a test. Additive, no wire/RBAC/migration break.

- **M2 — `ServicePlan.items`:** grows one item per remote `Command::AddItem` (RBAC `EditPlan`, Operator/Producer) with no cap; the bloat is also persisted and reloaded with no `LIMIT`. Add `MAX_PLAN_ITEMS` (in `selahcue-core::plan`, the single source of truth); reject `AddItem` past the cap in the controller; cap the `plan_repo::load` item loop.
- **M3 — LAN `active` session map:** `SessionRegistry.active` grows one permanent entry per distinct paired device (`redeem`), removed only on explicit `revoke`, no cap/idle-TTL. Add `MAX_ACTIVE_SESSIONS`; `redeem` refuses a NEW device when full (re-pairing an already-active device still replaces, no growth) via a new additive `PairingError::TooManySessions`; the offer is left intact so the operator can revoke a stale session and the user retries.
- **M4 — transcript-log DOM:** `syncTranscript` is append-only and bounded only by the host tail (`OPERATOR_TRANSCRIPT_TAIL=60`); no client cap/test. Slice incoming `view.transcript` to the newest N (120) before the prune/append so `#transcript-log` stays bounded even if a Remote/older/newer host ever returns an untailed list.

## Baseline

Verified from code:
- `plan.rs`: `add_item` (151) / `insert_item` (176) push/insert unconditionally; `ServicePlan::len()` (241) exists. Controller `Command::AddItem` (controller.rs:1403-1425) validates kind + non-empty title then `add_item` — no count check; returns `ControllerReply::Deny(DenyReason::BadRequest)` on bad input. `plan_repo::load` (plan_repo.rs:124-187) pushes every row into `items` with no cap.
- `session.rs`: `active: HashMap<DeviceId, Session>` (80); `redeem` (116) `self.active.insert(...)` (137) with no cap; `revoke` (179) the only removal; `active_count()` (184) exists; `PairingError` (63) has UnknownCode/ExpiredCode. Re-pairing the same `DeviceId` replaces (no growth).
- `app.js`: `syncTranscript` (2303) reads `view.transcript` (2304), prunes rows not in the id-set (2316-2319), appends new (2323-2337) — bounded only because the host tails to 60; no client slice.

## Scope

### In scope

- M2: `pub const MAX_PLAN_ITEMS: usize` in `selahcue-core::plan`; controller `AddItem` denies past the cap (re-using `DenyReason`); `plan_repo::load` stops past the cap. Bounded tests: controller flood → plan capped + subsequent deny; repo load of > cap rows → loaded plan capped.
- M3: `pub const MAX_ACTIVE_SESSIONS: usize` + `PairingError::TooManySessions` in `selahcue-lan::session`; `redeem` caps NEW devices; re-pair of an active device still works. Bounded test: redeem > cap distinct devices → `active_count() == MAX_ACTIVE_SESSIONS`, further `TooManySessions`, re-pair of an existing device succeeds at cap.
- M4: client slice to the newest 120 in `syncTranscript`. Headless test: feed > 120 segments → `#transcript-log` children ≤ 120 (newest kept).

### Non-goals

- The other audit findings (M1 done; M5 console decode; the LOW cluster) — separate follow-ups.
- Idle/TTL eviction of active sessions or LRU (a noted seam — reject-when-full is the bounded fix this slice; `Session` carries no last-seen timestamp).
- Changing `add_item`/`insert_item` return types (≈90 call sites) — the cap is enforced at the untrusted ingress (controller) + persistence, which are the only unbounded vectors; trusted seeding/tests keep the infallible API.

### Constraints

- Additive: no wire `VERSION`/RBAC/migration change; `PairingError`/`DenyReason` additions are additive. Caps generous (no legit plan/pairing hits them). Determinism unaffected. `make ci` (fmt/clippy/test workspace + server + encryption) + operator `node --check` + headless green.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | M2: `MAX_PLAN_ITEMS` caps the plan — the controller denies `AddItem` past it AND `plan_repo::load` stops past it; a bounded-memory test pins both | `cargo test -p selahcue-app -p selahcue-data -p selahcue-core` | flood → capped + deny; load → capped | test_controller/test_plan_repo | PASS |
| C-002 | yes | M3: `MAX_ACTIVE_SESSIONS` caps the active map — `redeem` refuses a new device when full (re-pair still works) via `TooManySessions`; a bounded-memory test pins it | `cargo test -p selahcue-lan` | > cap distinct → capped + TooManySessions; re-pair ok | test_session | PASS |
| C-003 | yes | M4: `syncTranscript` slices to the newest 120 so `#transcript-log` stays bounded regardless of the host; pinned by a COMMITTED CI-gated content guard + a dev-time behavioural headless check | `cargo test -p selahcue-present` (content guard, CI-gated) + dev-time headless | guard asserts the slice present; headless: >120 segs → ≤120 rows (newest) | test_tokens::operator_transcript_log_is_client_capped + headless | PASS |
| C-004 | yes | Gate: make ci + operator gate green; independent adversarial Workflow review, findings fixed; 3-OS CI green (verified by run conclusion) | make-ci + operator + Workflow + CI | all green; review fixed | CODE-REVIEW-batch-memory-caps.md; CI 30651447222 (completed→success, 11/11) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `-p selahcue-core` (const), `-p selahcue-app` (controller AddItem cap + flood test), `-p selahcue-data` (plan_repo load cap test), `-p selahcue-lan` (redeem cap + re-pair test), operator headless (transcript slice). Broader: make ci + operator gate + 3-OS CI (verified by run conclusion, not the watcher exit code). Independent: adversarial Workflow review (cap-correctness/off-by-one · re-pair-still-works/eviction-safety · frontend-slice lenses → refute-by-default).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001, M2): `pub const MAX_PLAN_ITEMS: usize = 500` in `selahcue-core::plan`; controller `Command::AddItem` denies (`BadRequest`) once `self.plan.len() >= MAX_PLAN_ITEMS`; `plan_repo::load` breaks the item loop past the cap (the lazy `query_map` stops fetching). Tests: `plan_is_bounded_under_add_item_flood` (controller floods MAX+50 → plan == MAX, ≥50 denied, a further add denied), `load_is_bounded_to_max_plan_items` (persist MAX+25 → reload == MAX). Result: PASS.
- Iter 1 (C-002, M3): `pub const MAX_ACTIVE_SESSIONS: usize = 256` + `PairingError::TooManySessions` in `selahcue-lan::session`; `redeem` consumes the single-use code first (pending strictly shrinks) then refuses a NEW device past the cap (re-pairing an already-active `DeviceId` still replaces, no growth); `server.rs` reject distinguishes the cap message. **Design correction:** the first cut used cap 64 + left the offer intact on reject — that broke the pre-existing `redeeming_consumes_the_offer_so_pending_does_not_grow` (pairs 100 devices; 100 > 64) AND weakened the single-use invariant. Revised to cap 256 (comfortably above the 100-device test; a pure anti-OOM bound) + consume-on-reject (single-use holds universally). Test: `active_sessions_are_hard_capped` (pair 256 → capped + pending 0; new device → TooManySessions + code consumed; re-pair at cap → ok; revoke + fresh code → ok). Result: PASS.
- Iter 2 (C-003, M4): `syncTranscript` slices `view.transcript` to the newest `MAX_TRANSCRIPT_ROWS=120` (2× the host `OPERATOR_TRANSCRIPT_TAIL=60`) before the prune/append, so `#transcript-log` stays bounded even against an untailed host. Dev-time headless (feed 200 segments → exactly 120 rows, newest id 199 kept + oldest id 0 pruned): **63/63**. Result: PASS.
- Iter 3 (C-004 review, M4 evidence correction): the adversarial review's no-drift lens raised (HIGH→verified MEDIUM) that the M4 headless harness lives in the SCRATCHPAD — it is **not committed, not in `make ci`, not in the CI operator job** — so the M4 slice had no in-repo/CI regression gate and the "headless 63/63" C-003 evidence overstated a dev-time check as a committed test (a real integrity gap; the slice code itself is correct + double-bounded). **Fixed:** added a committed, CI-gated content guard `test_tokens::operator_transcript_log_is_client_capped` (runs under `cargo test --workspace`) asserting the `MAX_TRANSCRIPT_ROWS=120` + `slice(-MAX_TRANSCRIPT_ROWS)` cap is present, so the slice can never be silently dropped; corrected the C-003 evidence to name both the committed guard (behavioural gate: content) and the dev-time headless (behavioural gate: DOM count); registered a follow-up for real operator JS/jsdom CI test infra (the systemic gap — the operator webview has no JS test runner, so ALL prior "headless N/N" evidence this session was likewise dev-time). The cap-correctness + no-drift lenses otherwise returned all-INFO (exact bounds, full ingress coverage, additive, strong M2/M3 tests). Result: PASS.
- Iter 4 (C-004, review complete): adversarial review `wf_8c8761f2-1eb` (3 lenses, refute-by-default) + a behaviour-safety re-run `wf_3ec5695a-894` (the first run stubbed that lens). **2 above-INFO findings, both addressed:** (1) no-drift HIGH→MEDIUM (verified) — the M4 headless harness is scratchpad-only (not committed/CI), so the slice had no in-repo gate and "63/63" overstated it → **fixed** with a committed CI-gated content guard (`test_tokens::operator_transcript_log_is_client_capped`) + honest C-003 evidence + a DEVOPS follow-up. (2) behaviour-safety MEDIUM→LOW (refuted-down) — the M3 re-pair branch is unreachable in the live remote flow (`server.rs` mints a fresh random `device_id` per pairing), so the cap bounds concurrent (not lifetime) sessions and a remote re-pair takes a new slot; the cap still fully achieves the no-leak goal (exhaustion needs 256 approved pairings in one process lifetime, zero revokes — fail-closed, far beyond real use) → **addressed** by correcting the misleading `session.rs` comment + a LOW follow-up (stable remote id / idle-TTL). cap-correctness all-INFO (exact bounds, full ingress coverage); additive confirmed; M2/M3 tests genuinely fail without their caps. Full review: `docs/delivery/CODE-REVIEW-batch-memory-caps.md`. Re-verified after fixes: `cargo test --workspace` **469 passed / 0 failed**, server/encryption green, fmt/clippy clean, `test_tokens` 11/11, headless 63/63. Result: PASS pending only the 3-OS CI run (this push, verified by conclusion).

## Risks and rollback

- Risks: an off-by-one (cap lets N+1 through) — mitigated by a flood test asserting the exact bound; rejecting a legit re-pair at the cap — mitigated by allowing an already-active `DeviceId` to replace + a test; the transcript slice dropping a still-wanted row — mitigated (slice keeps the NEWEST, matching the host tail order) + a headless test. Rollback: git; additive across core/app/data/lan/operator.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajnx548-memory-caps.md --require-complete`
- Validator result: PASS (run below)
- Independent verification result: adversarial review `wf_8c8761f2-1eb` + behaviour-safety re-run `wf_3ec5695a-894` — 2 above-INFO findings, both addressed (M4 committed guard added + evidence corrected; M3 comment corrected + follow-up queued); cap-correctness all-INFO. See `CODE-REVIEW-batch-memory-caps.md`.
- Terminal state: **VERIFIED_COMPLETE** — M2/M3/M4 hard-capped + bounded-tested; **3-OS CI `30651447222` GREEN (completed→success, 11/11 jobs)**, verified by run conclusion; no release-blocking defect; 2 LOW/MEDIUM follow-ups queued (#8 M3 remote re-pair/idle-TTL, #9 operator JS CI infra).
- ClickUp final evidence comment: (queued — MCP rate-limited; closes audit follow-ups M2/M3/M4 in the report §4; adds §4 items #8/#9; BUILD CONTROL `86ajnx548` update queued)
