# Goal Contract — TASK-86ajp0b0t-session-idle-ttl

## Identity

- Goal ID: TASK-86ajp0b0t-session-idle-ttl
- Parent goal ID: BUILD-selahcue (Stage 8 quality — audit follow-up #8)
- Title: Reclaim idle LAN sessions (active-session idle-TTL) so the cap bounds recently-active, not lifetime, pairings
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: BUILD CONTROL 86ajnx548 (⚠ ClickUp MCP rate-limited — audit report §4 #8)
- Created: 2026-08-01
- Independent verification required: yes (adversarial review + bounded/behaviour tests)
- Maximum iterations: 8

## Objective

Close audit follow-up **#8**: the M3 cap (`MAX_ACTIVE_SESSIONS`) bounds the `active` session map, but the map is reclaimed **only by explicit `revoke`** and the live remote flow mints a fresh random `device_id` per pairing (`server.rs:318`), so a device re-pairing after credential loss consumes a NEW slot and dead sessions accumulate — the cap then bounds *lifetime host-approved pairings within a process*, not *concurrent recently-active* devices. Add a purely **server-side idle-TTL**: a `last_seen` timestamp on each session (set at pairing, refreshed on re-authentication) and a `prune_idle(now, ttl)` reclaimer wired into the same housekeeping where `prune_expired` already runs (before a new pairing) — so a session unused for longer than `SESSION_IDLE_TTL` self-reclaims and a full registry accepts a new device once idle ones age out. No wire/RBAC/protocol change (in-memory, clock-injected like the rest of `session.rs`).

## Baseline

Verified from code: `Session { device_id, role, token }` (session.rs:56) — no timestamp. `redeem` (116) takes `now` + inserts into `active` (bounded by `MAX_ACTIVE_SESSIONS`, audit M3). `authenticate(&self, device_id, token)` (191) is called ONCE per connection at the handshake (server.rs:243-246, an immutable `reg` lock); the request loop trusts the handshake role (no per-request re-auth). `active` shrinks only via `revoke` (196). `prune_expired(now)` (for the *pending-offer* map) is called in the pairing pre-check (server.rs:298-301) + desktop `main.rs:1170`, both mutable-locked with a fresh `Instant::now()`. `active` never TTL-expires. The registry is clock-injected (redeem/offer/prune_expired all take `now`) for testability.

## Scope

### In scope

- `session.rs`: `Session` gains `last_seen: Instant` (set at `redeem` = `now`). `pub fn touch(&mut self, device_id: &DeviceId, now: Instant) -> bool` (refresh `last_seen` if the session exists). `pub fn prune_idle(&mut self, now: Instant, ttl: Duration) -> usize` (`active.retain(|_, s| now.saturating_duration_since(s.last_seen) <= ttl)`; returns the count reclaimed). `pub const SESSION_IDLE_TTL: Duration` (generous — longer than a service, so an active device is never pruned mid-use; reclaims a dead session within the window).
- `server.rs`: `touch` the session on a successful handshake `authenticate` (device is active now); `prune_idle(now, SESSION_IDLE_TTL)` in the pairing pre-check (next to `prune_expired`) and right before `redeem` (so the cap check sees reclaimed slots). `main.rs`: `prune_idle` next to `prune_expired` in the desktop housekeeping.
- Tests: `prune_idle` reclaims sessions idle > ttl and KEEPS fresher ones; `touch` refreshes `last_seen` (a touched session survives a later prune); the cap+prune interaction — a full registry of all-idle sessions accepts a NEW device after `prune_idle`; a recently-active (touched) full registry still rejects a new device (`TooManySessions`). Clock-injected (no wall-clock).

### Non-goals

- A stable client-supplied `device_id` on `PairRequest` (the other #8 option — a wire change + a session-eviction surface; idle-TTL is the cleaner server-only fix). Per-request `last_seen` refresh (handshake-touch + a generous TTL suffices; a single connection open longer than the TTL only re-pairs on its next reconnect — harmless, documented). #10 (WebKit smoke), #11-poll.

### Constraints

- Purely additive + server-side: no wire `VERSION`/RBAC/protocol/migration change; `Session` is not serialized. Clock-injected (`prune_idle`/`touch` take `now`; `SESSION_IDLE_TTL` is the production value). `saturating_duration_since` (no panic if `now < last_seen`). An active device is never pruned mid-service (TTL ≫ a service). The M3 cap + its tests stay green. `make ci` (fmt/clippy/test workspace + `--features server`) + CI green (verified by conclusion).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `Session.last_seen` + `touch` + `prune_idle` + `SESSION_IDLE_TTL`: `prune_idle` reclaims sessions idle > ttl, keeps fresher/touched ones; a bounded/behaviour test pins it (clock-injected) | `cargo test -p selahcue-lan` | idle reclaimed; fresh kept; touch refreshes | test_session (`prune_idle_reclaims_idle_sessions_and_keeps_touched_ones`); 21/0 | PASS |
| C-002 | yes | The cap + idle-TTL interact correctly: a full registry of all-idle sessions accepts a NEW device after `prune_idle`; a recently-touched full registry still rejects (`TooManySessions`) | `cargo test -p selahcue-lan` (+ `--features server`) | prune frees a slot; active stays capped | test_session (`idle_ttl_frees_cap_slots_but_recently_active_sessions_still_reject`) | PASS |
| C-003 | yes | Wired: handshake `authenticate` touches; the pairing housekeeping + pre-redeem prune idle; desktop housekeeping prunes idle; `-p selahcue-lan --features server` + the loopback E2E green | `cargo test --features server` + build | wired; server E2E green | server.rs/main.rs diff; `--features server` green | PASS |
| C-004 | yes | Gate: make ci + independent adversarial review (TTL correctness / no-panic / no active-session prune / additive), findings fixed; 3-OS CI green (verified by run conclusion) | make-ci + Workflow + CI | all green; review fixed | CODE-REVIEW doc; CI run | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `-p selahcue-lan` (prune_idle reclaims/keeps; touch refreshes; cap+prune interaction — all clock-injected with a short test ttl) + `--features server` (the loopback E2E still pairs+authenticates). Broader: make ci + 3-OS CI (verified by conclusion). Independent: an adversarial Workflow review (idle-TTL correctness / `saturating_duration_since` no-panic / an active device is never pruned mid-use / additive-no-drift / the M3 cap still holds).
- Required environment: local + CI.

## Iteration ledger

- Iter 0 (C-001/C-002): `session.rs` — `Session.last_seen: Instant` (set at `redeem = now`), `touch(&mut self, device_id, now) -> bool` (get_mut refresh; false for unknown), `prune_idle(&mut self, now, ttl) -> usize` (`active.retain(|_, s| now.saturating_duration_since(s.last_seen) <= ttl)`, returns reclaimed count), `pub const SESSION_IDLE_TTL = 6h`. Updated the redeem comment (idle-TTL now implemented, not a follow-up). Tests: `prune_idle_reclaims_idle_sessions_and_keeps_touched_ones` (idle > ttl reclaimed; touched kept; unknown-device touch is a no-op; the shipped TTL ≥ 1h) and `idle_ttl_frees_cap_slots_but_recently_active_sessions_still_reject` (a full recently-active registry still rejects `TooManySessions`; once all idle, prune frees the whole registry and a new device pairs). Evidence: `cargo test -p selahcue-lan --test test_session` **21/0** (+2). Result: PASS.
- Iter 1 (C-003): `server.rs` — the handshake `authenticate` now takes a mutable lock + `touch`es on success (device is active now); `prune_idle(now, SESSION_IDLE_TTL)` in the pairing pre-check (next to `prune_expired`) and immediately before `redeem` (so the M3 cap check sees reclaimed slots). `main.rs` — `prune_idle` next to `prune_expired` in the desktop housekeeping. Evidence: `cargo build -p selahcue-lan -p selahcue-desktop` + `--features server` clean; `cargo test -p selahcue-lan --features server` green (the loopback E2E still pairs+authenticates); fmt/clippy (workspace + server) clean. Result: PASS.
- Gate prep: full workspace test + independent adversarial review (`wf_0fb192c5-064`, correctness + safety-wiring lenses) running.

## Risks and rollback

- Risks: pruning an ACTIVE session mid-use (mitigated: TTL ≫ a service; `touch` on each (re)authentication; the request loop already trusts the handshake role, so even a pruned long-connection keeps working and only re-pairs on its next reconnect). A clock panic (mitigated: `saturating_duration_since`). Breaking the M3 cap or its tests (mitigated: prune only reclaims IDLE; the cap tests use `now`-fresh sessions → unaffected). Rollback: git; additive server-side (`session.rs` + `server.rs` + `main.rs`), no wire change.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajp0b0t-session-idle-ttl.md --require-complete`
- Validator result: (pending)
- Independent verification result: (pending)
- Terminal state: (pending)
- ClickUp final evidence comment: (pending — MCP rate-limited; closes audit report §4 #8)
