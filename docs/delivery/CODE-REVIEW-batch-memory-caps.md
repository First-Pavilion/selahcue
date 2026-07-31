# Code Review — Batch: memory caps M2/M3/M4 (audit follow-ups, 86ajnx548)

- **Scope:** hard-cap the three MEDIUM no-leak-rule gaps from [`docs/quality/AUDIT-memory-perf-latency.md`](../quality/AUDIT-memory-perf-latency.md) — each a collection that grew on a reachable path with no cap and no bounded-memory test. **M2** `ServicePlan.items` (remote `AddItem` + persistence reload), **M3** the LAN `active` session map, **M4** the operator transcript DOM. Additive; no wire `VERSION` / RBAC / migration change. Executed via `/goal` (`TASK-86ajnx548-memory-caps.md`, validator PASS 4/4 `--require-complete`).
- **Method:** an adversarial Workflow review — **cap-correctness** (off-by-one / ingress-coverage), **behaviour-safety** (broken flows / security / aria-live), **no-drift** (additive / test-quality) → refute-by-default verify. The first run (`wf_2127bac1-f29`) was **stopped and relaunched** (`wf_8c8761f2-1eb`) because I'd revised M3 after launching it, so it had read stale code; the behaviour-safety lens returned a stub in that run and was **re-run standalone** (`wf_3ec5695a-894`) for a real verdict.
- **Outcome:** across the lenses, **2 findings raised above INFO → both addressed.** cap-correctness: all-INFO (exact bounds, full ingress coverage). no-drift: 1 HIGH→**MEDIUM (verified)** — the M4 test was scratchpad-only, not committed/CI — **fixed**. behaviour-safety: 1 MEDIUM→**LOW (refuted-down)** — the M3 re-pair "safety net" is unreachable in the live remote flow — **comment corrected + follow-up queued**. Everything else INFO.

## What shipped

- **M2** — `pub const MAX_PLAN_ITEMS: usize = 500` (`selahcue-core::plan`, single source of truth). The controller's `Command::AddItem` denies (`DenyReason::BadRequest`) once `self.plan.len() >= MAX_PLAN_ITEMS` — the sole remote grower of `items` (verified: the only `add_item` call from a `Command`). `plan_repo::load` breaks the (lazy) row loop past the cap, so a corrupt/oversized persisted plan can't materialize unbounded. Tests: `plan_is_bounded_under_add_item_flood`, `load_is_bounded_to_max_plan_items`.
- **M3** — `pub const MAX_ACTIVE_SESSIONS: usize = 256` + additive `PairingError::TooManySessions` (`selahcue-lan::session`). `redeem` consumes the single-use code first (`pending` strictly shrinks, no replay) then refuses a NEW `device_id` past the cap; `server.rs` maps it to a distinct reject message. Test: `active_sessions_are_hard_capped`. (Cap raised 64→256 after the first cut broke the pre-existing 100-device `redeeming_consumes_the_offer` test; consume-on-reject adopted so single-use holds universally.)
- **M4** — `syncTranscript` slices `view.transcript` to the newest `MAX_TRANSCRIPT_ROWS=120` (2× the host `OPERATOR_TRANSCRIPT_TAIL=60`) before the unchanged prune-by-id + append-new, so `#transcript-log` stays bounded even against an untailed host and the aria-live append-only contract is preserved. Guard: `test_tokens::operator_transcript_log_is_client_capped` (committed, CI-gated) + a dev-time headless behavioural check.

## Findings and dispositions

| # | Lens | Sev (raised→verified) | Finding | Disposition |
|---|------|------|---------|-------------|
| 1 | no-drift | HIGH → **MEDIUM** | The M4 headless harness lives in the **scratchpad** — not committed, not in `make ci`, not in the CI operator job — so the M4 slice had no in-repo regression gate and "headless 63/63" overstated a dev-time check as a committed test (an integrity/coverage gap; the slice code itself is correct + double-bounded). | **Fixed.** Added a committed, CI-gated content guard (`operator_transcript_log_is_client_capped`) that fails if the cap is dropped; corrected the C-003 evidence to name both the guard and the dev-time headless; queued a DEVOPS follow-up for real operator JS/jsdom CI infra (a systemic gap — all operator "headless N/N" this session was dev-time). |
| 2 | behaviour-safety | MEDIUM → **LOW** | The registry-level "re-pair replaces, no growth" branch is **unreachable in the live remote flow**: `server.rs:318` mints a fresh random `device_id` per pairing and `PairRequest` carries no client id, so a remote re-pair takes a NEW slot; `active` is reclaimed only by `revoke`. So the cap bounds *concurrent* sessions and a legit remote device re-pairing after credential loss consumes a slot. | **Addressed (accept + document + follow-up).** The cap fully achieves the no-leak goal; exhaustion needs 256 host-approved pairings in one process lifetime (the map resets on restart) with zero revokes — fail-closed and far beyond any real setup. Corrected the misleading `session.rs` comment to state the live semantics honestly; queued a LOW follow-up (stable client `device_id` on `PairRequest` OR an active-session idle-TTL). |
| 3 | cap-correctness | INFO ×4 | Each guard hits the **exact** bound (collection reaches MAX, never MAX+1) and every growth path funnels through the single capped chokepoint (`add_item` sole remote grower; `redeem` sole `active` insert; `syncTranscript` sole `#transcript-log` builder). | No change — correct. |
| 4 | no-drift / behaviour-safety | INFO | Additive (no wire/RBAC/migration drift; `PairingError`/`DenyReason` break no exhaustive match — `Err(_)` wildcards + Debug-format callers); consume-before-cap safe (no replay); M2 `next_id`/ordering consistent after a capped load; M4 aria-live append-only preserved, 120 ≥ host tail 60 so normal operation is never truncated; determinism unaffected; M2/M3 tests genuinely fail if the cap is removed. | No change — safe. |

**Deferred INFO notes (not fixed this batch):** a distinct `DenyReason`/capacity reason vs reusing `Unauthenticated`/`BadRequest` (cosmetic UX); a warning-log on the (out-of-spec-only) M2 load truncation (no logging facility in `selahcue-data` — not worth a new dependency).

## Verification

- **Workspace:** `cargo test --workspace` **469 passed / 0 failed** (+3 bounded tests +1 M4 guard = the deltas); `--features server` (incl. the loopback E2E exercising `redeem`) + `--features encryption` green; `cargo fmt --check` + `clippy --workspace --all-targets` clean.
- **Operator:** `node --check dist/app.js` OK; committed guard `operator_transcript_log_is_client_capped` green; dev-time headless **63/63** (+2 M4: 200 segs → 120 rows, newest kept).
- **CI:** 3-OS matrix — pending this push (verified by run **conclusion**).

## Follow-ups (queued — ClickUp rate-limited; audit report §4)

- **#8 (LOW)** remote re-pair replaces / active-session idle-TTL (M3 live-flow nuance).
- **#9 (DEVOPS/MEDIUM)** real operator JS/jsdom test infra wired into CI (systemic — the interim committed content guard is in place for M4).
- Prior audit follow-ups unchanged: M5 console decode; the LOW cluster.
