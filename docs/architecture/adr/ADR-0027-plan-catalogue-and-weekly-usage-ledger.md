# ADR-0027 — Plan catalogue, effective plan and the weekly usage ledger (Free / Core / Pro)

- Status: **Proposed**, revision 2. This is the architecture review of the 2026-09-27 plan-limits design, done before the backend build starts.
- Date: 2026-09-27. Revision 2, the same day, covers three things:
  - the owner's direct-to-provider directive;
  - Vera's review (performance);
  - Sana's review (security).
- **What revision 2 changed:**
  - How a spend is settled: D5's commit and release now follow ADR-0028 D5.
  - D6 is replaced by ADR-0028.
  - A security dependency section is new.
  - Every review finding has a recorded outcome (see "Review dispositions").
- Confidence: **Medium-High.** The current state is verified against `origin/main` at `f211581`. The ledger design is reasoned from the concurrency pattern that already ships (`select_for_update` on the licence row in `devices/services.py`). It has not been spiked.
- Owner: Software Architect (Aria). Delivery: Backend Engineer (Kenji). Required reviewers before `Accepted`: Security Reviewer (Sana) for D4–D6 and the security dependency section; Performance Engineer (Vera) for D5.
- Companion: **ADR-0028** decides three things this ADR relies on:
  - how the desktop reaches Deepgram and OpenAI directly;
  - how usage is attributed to a church;
  - how reservations are settled from the provider's own usage figures.
- Relates: DEC-004 (licensing model), DEC-008 (superseded in part by D7/D8), DEC-009 (Free fallback after grace), DEC-014 (fallback plan gate), ADR-0021 (admin licensing platform). ClickUp: [EPIC 17tnw2az0g6](https://app.clickup.com/t/17tnw2az0g6) and its build tickets 17tnw2az0gd, 17tnw2az0gg, 17tnw2az0gh, 17tnw2az0gj, 17tnw2az0gn, 17tnw2az0gq, 17tnw2az0gr.
- Decision text for D7 / D8 / D9 is the product owner's and is recorded in `DECISION-LOG.md` by [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu). This ADR records only **how** the platform implements them.

---

## Context

The owner replaced DEC-008's Free / Pro / Platinum monthly model with Free / Core / Pro and **weekly** allowances for two cloud-only features: cloud transcript minutes (20 / 50 / 80) and sermon-note generations (1 / 5 / 10). Prices and limits must be data. A SuperAdmin can grant a plan for 1–12 months. The week resets Monday 00:00 in the account's time zone. An upgrade grants the full new allowance at once; a downgrade caps and claws nothing back. Failures caused by SelahCue or the AI provider are never charged.

What already ships (verified on `origin/main` `f211581`):

- `apps/catalogue`: `Plan`, `GrantDimension`, `PlanGrant`, `LicensePlanAssignment` (one per **licence key**), `LicenseGrantOverride`, `PlanScopeAlias`, `CatalogueRevision`. Resolution is licence-key based: assignment, then scope alias, then the `is_fallback` plan.
- The fallback plan is `LEGACY` (migration `0002`): unlimited outputs, unlimited NDI, no watermark, 0 STT. DEC-014 calls it "the most permissive plan in the catalogue", and `set_license_plan_assignment` refuses to assign the fallback for that reason.
- The seed migration `0002` says "never edit this file", and the tier-name sweep in `tests/test_product_catalogue_slice.py` exempts **only** that file.
- `GrantDimension` keys are a wire contract: they travel in the signed manifest, which is cached offline until the licence expires (years).
- `screen_outputs` defaults to `unlimited` by design (NFR-024: never take away live output). Only `ndi_outputs` and the STT dimension default to 0.
- `CustomerOrg` has `timezone` (free text, default `"UTC"`, never validated as an IANA name) and a legacy `plan` string (`"TRIAL"`). `AppLicenseKey` has its own `timezone` field.
- An org can hold several active licence keys. `_resolve_org_active_license_key` picks the one with the furthest expiry. DEC-008 AS-P8 says an org has one licence key, but nothing enforces it.
- Concurrency precedent: activation locks the licence-key row with `select_for_update` so the count-then-insert is atomic. `select_for_update` is a no-op on SQLite; CI runs Postgres 16 and `tests/test_concurrency_postgres.py` skips on SQLite.
- The API calls no AI provider today. The hosted notes endpoint (86ajy04hz) and the STT token mint (86akby3xu) do not exist yet.

## Decisions

### D1 — The plan is resolved per **organisation**, through one function

Allowances are pooled per organisation, but plans are attached per licence key. That mismatch has to be closed in one place.

`effective_plan(org, at)` is the only answer to "which plan is this account on". It returns the higher-ranked of:

1. the org's **paid plan**: the plan of the licence key `_resolve_org_active_license_key` would pick (same tie-break, so activation and metering never disagree about which key counts), with DEC-009 grace applied;
2. an **active staff grant** (start ≤ at < end, not ended early);

and, if neither exists, the fallback plan.

`resolve_entitlement(license_key)` calls it (licence key → org → effective plan) so the manifest reflects grants. The ledger and both enforcement points call it too. `CustomerOrg.plan` (the `"TRIAL"` string) is **never read** for entitlement; it is a legacy label.

### D2 — "Higher" is a data field, not a name

The catalogue gains `Plan.rank` (positive integer, unique). "Higher of granted and paid", "is this an upgrade" and "the fallback" all compare `rank`. `sort_order` stays display-only; overloading it would let a display reorder silently change who gets which allowance.

### D3 — Free becomes the fallback; `LEGACY` is retired

D9 says a lapsed grant reverts to "the paid plan, or Free", and DEC-009 says a lapsed licence degrades to Free. Both contradict a permissive `LEGACY` fallback. Pre-launch, with no customers, the fallback moves to Free:

- A new migration (never an edit to `0002`) repoints every `PlanScopeAlias` and any `LicensePlanAssignment` on `LEGACY`, `PLATINUM` or the old `PRO` to the new rows, then removes `LEGACY` and `PLATINUM`. `PROTECT` foreign keys make an unhandled reference fail loudly, which is correct.
- Invariant, tested: **the fallback plan has the lowest rank.** This replaces the reasoning behind `set_license_plan_assignment`'s refusal to assign the fallback. That refusal exists because the fallback was the *most* permissive plan; once it is the least permissive, the refusal would only block assigning Free explicitly. The refusal is removed and the invariant test takes its place.
- DEC-014 point 2 (new issuance must name a plan) still stands.

This amends DEC-014's premise. It must be recorded with D7 on 17tnw2az0gu.

### D4 — Price is its own effective-dated table and never enters the manifest

`PlanPrice(plan, currency, interval, amount_minor, effective_from, changed_by_actor_id, reason)`:

- `amount_minor` is a nullable integer. `NULL` means "unpriced", which is distinct from `0`. A plan with no price row is also unpriced.
- Rows are append-only. A price change inserts a row. The current price for a (plan, currency, interval) is the row with the latest `effective_from` that is not after now. Unique on (plan, currency, interval, effective_from).
- `currency` is checked against an ISO 4217 allow-list, and the allow-list carries each currency's minor-unit exponent. "Minor units" is not always cents: JPY has 0 decimal places and KWD has 3.
- `interval` is an enum (`WEEK`, `MONTH`, `YEAR`); billing intervals are code, not tier names.
- Same accountability constraints as `PlanGrant` (actor and reason required at the database).
- Price is **not** published in the signed manifest. No client decision needs it, and a signed, offline-cached price would be stale for years.

### D5 — The weekly ledger: one locked counter row per org per week, a reservation table, no lock held across a provider call

Tables (new `apps/usage`, so retention and ownership stay separate from the catalogue):

- `UsageWeek(org, week_start_local, tz_name, starts_at, ends_at, stt_seconds_charged, stt_seconds_reserved, notes_committed, notes_reserved, high_water_rank, rank_at_last_reset)`. Unique on (org, week_start_local). The time zone and both boundaries are **fixed when the row is created**. That is how "a time-zone change applies from the next reset" works without any extra state.
- `UsageReservation(org, week, meter, units, state = RESERVED | ISSUED | SETTLED | RELEASED, idempotency_key, request_hash, device_id, issued_at, retry_count, expires_at, created_at)`. Unique on (org, meter, idempotency_key).

**Revision 2.** Under the owner's direct-to-provider directive, the server never calls the provider on a spend and never sees the outcome. The reservation states and settlement rules are therefore defined in **ADR-0028 D5**: `RESERVED → ISSUED → SETTLED`, with `RELEASED` allowed only before a credential is issued. They replace revision 1's COMMITTED state. Compared with revision 1, the table gains three columns:

- `request_hash`;
- `issued_at`;
- `retry_count`.

Protocol for a spend (both meters):

1. **Reserve.** This is one short `transaction.atomic()`:
   - Find the current `UsageWeek` row by `starts_at ≤ now < ends_at` (SEC-0027-07). Lock it with `select_for_update`. If it does not exist, create it with `get_or_create` and retry once on `IntegrityError`, which is the house idempotency pattern.
   - Apply D7's upgrade rule.
   - Check `settled + Σ open estimates + units ≤ limit`.
   - Insert the reservation as `RESERVED`, then commit.

   Reads take **no** lock. A test fails if `remaining()` emits `FOR UPDATE`. Both `remaining()` and reserve have a query budget (`django_assert_num_queries`), and `effective_plan` counts inside it.
2. **Issue.** Close the database connection, then call the provider's mint endpoint with hard timeouts (ADR-0028 D6).
   - If the mint succeeds: a second short transaction moves the reservation to `ISSUED`.
   - If the mint fails: it moves to `RELEASED`.
3. **Settle.** Only reconciliation settles a reservation. It uses the provider's own usage records (ADR-0028 D5).
4. **Crash safety.**
   - A `RESERVED` row older than its TTL has issued nothing, so it is released lazily by the next reserve and by the sweeper.
   - An `ISSUED` row is **never** released by time. It stays counted until reconciliation settles it.
   - **Correctness never depends on the job**, the same principle 17tnw2az0gh uses for grant expiry.
   - The sweeper is scheduled in `CELERY_BEAT_SCHEDULE`, and a test checks it is registered. It deletes in batches, following the `accounts/maintenance.py` pattern.
   - A partial index on `(org, expires_at) WHERE state = 'RESERVED'` keeps the lazy release cheap while the lock is held.

Why row locking and not optimistic concurrency. Both are correct. A conditional `UPDATE … WHERE committed + reserved < limit` is lock-free, but the reserve step also has to create the week row, expire stale reservations and apply the upgrade reset. Doing that as one guarded write is more complex than one short lock. The lock is per org, so it serialises only one church's handful of devices, and it is held for milliseconds. It matches the shipped activation pattern.

The rule that makes this safe: **never hold the lock, or the transaction, across any provider call.** That covers the mint call and the reconciliation job's read of the usage API. Under the directive, the server no longer waits on a generation. Vera's worker and connection finding is resolved, with a bounded residual for the mint call; ADR-0028 D6 sets out the residual and its timeouts.

Timeout invariant. `RESERVED_TTL` must be longer than the mint call's connect and read timeouts. Assert this at import, next to both constants, in the style of `DEGRADED_MANIFEST_TTL_SECONDS`. An `ISSUED` reservation has no time-based release, so it needs no TTL invariant. The "one unit per late success" overrun rule from revision 1 no longer applies: late usage is charged by reconciliation, in the week it happened.

Upgrade reset (D7) resets only the settled counters and their estimate baseline. It **never** zeroes the open reservations. Zeroing them would drive the counters negative when those reservations settle.

Lock order: the org first, then the licence key (`AppLicenseKey`, as activation and the state machine lock it), then `UsageWeek`. Every path that takes more than one of these locks takes them in this order.

Reads. `remaining(org)` is one read of `UsageWeek` through its unique index, plus `effective_plan` and one indexed sum of the open estimates. It takes no lock, and a query budget pins its cost. It meets the manifest p95 budget and **writes nothing**. If D7's upgrade reset is due but has not been written yet, the read computes it virtually.

Usage is per org, so it **must not** go into the catalogue `GRANT_CACHE`. That cache is keyed per plan and shared across tenants. Putting org usage in it would leak one tenant's figures to another and grow the key space with the number of orgs.

### D6 — Cloud transcript and sermon notes: replaced by ADR-0028

Revision 1 said the transcript overrun was "bounded by one stream". **That was wrong.** Sana's SEC-0027-02 showed why:

- One Deepgram token can open several streams while it is valid.
- Every stream is logged under the one server key that minted it.
- The only per-request label is a tag the client sets itself.

ADR-0028 replaces this section, and for both providers it decides the following:

- **Attribution** uses only the identity of the credential the server issued. For Deepgram that is a durable key per church; for OpenAI it is a project per church.
- **Usage nobody can attribute** fails closed. It raises an alert and is charged to nobody.
- **Reconciliation** is a read-only, server-to-server call to the provider's usage API.
- **Transcript reservations** are taken in fixed slices (Vera, High 2).
- **The stated overrun bound** is honest: *(streams opened within the token's lifetime) × (how long each is held open)*.

"Only delivered time counts" (still open on 17tnw2az0gu) is defined as the provider's recorded duration for the church's credential. That is the only figure the server can check.

### D7 — Upgrade reset uses a weekly rank high-water mark

The reset is applied lazily and exactly. It is applied at reserve time, under the D5 lock, because every spend goes through reserve.

If `rank(effective_plan) > high_water_rank`, set `rank_at_last_reset` and `high_water_rank` to the new rank and start the week's counters again from 0. Usage events keep their full history. A downgrade changes nothing, because `remaining = max(0, limit − counted)`.

A limit edit (Core 5 → 6) is **not** a plan change, so it never resets anything. The comparison is on rank, never on the limit value.

The high-water mark also closes the downgrade-then-upgrade loophole (open item 6 on 17tnw2az0gu). Pro → Free → Pro in one week does not reset twice, because Pro is already the week's high-water mark. Free → Core → Pro still resets at each step, as D8 intends. **This is a recommendation for the owner, not a decision.** Without it, the high-water check becomes "rank increased since the last spend" and the loophole stays open.

### D8 — Time: IANA zone, validated on write, never raising on read

- `CustomerOrg.timezone` is the account's zone. `AppLicenseKey.timezone` is not used for the week.
- Writes are validated against `zoneinfo.available_timezones()`. On the read path, an unknown or corrupt value falls back to UTC and logs a warning. It never raises (NFR-024).
- The week starts at the first instant at or after local Monday 00:00. Where a DST change skips midnight, that is the first valid local instant. A pinned test uses a zone that has had a midnight transition.
- Grant month arithmetic runs in the org's zone, with the end clamped to the last day of a shorter month (31 Jan + 1 month = 28/29 Feb, same local time). Instants are stored in UTC.

### D9 — Offline: the manifest carries a snapshot for display; enforcement stays on the server

This matches DEC-004. Both meters are cloud-only, so nothing is ever spent offline and there is nothing to reconcile.

The manifest gains `usage` as an **additive** object: for each meter, the limit, used, remaining, `as_of` and `resets_at`. It does not earn an `ENTITLEMENT_VERSION` bump, under that constant's own rule.

A manifest lives as long as the licence (years), so the snapshot is stale almost at once. Clients must:

- show it with its `as_of` time;
- treat it as display only;
- after `resets_at` has passed, show the full limit for the plan in the snapshot, marked as an estimate.

Live figures come from `GET /v1/quota`. Clients must not re-issue manifests to refresh usage. Every issuance signs a payload and writes an audit row, so polling would grow the audit table in step with how often clients look at a meter.

`GET /v1/quota` has its own rules:

- It is throttled per **device token**, not per IP, because a church's devices share one NAT address.
- It does not audit every read.
- Clients poll at 60 s plus jitter, and refresh after their own spends.
- After `resets_at`, clients also add jitter, so that no time zone polls all at once each Monday.

Under ADR-0028 the figures are eventually consistent. `remaining` includes an estimate for sessions not yet reconciled. The response carries `settled_as_of`.

### D10 — Catalogue dimensions: new keys, old key deactivated, pending values explicit

- Add `cloud_transcript_minutes_per_week` and `sermon_notes_per_week`, both INTEGER defaulting to `0`. Set `stt_minutes_per_period` to `is_active = False` rather than renaming it. Keys ship in signed artefacts, and a rename silently changes what an old key means. Deactivating it is safe now: no desktop code reads the old key (verified by `git grep` on `f211581`).
- Core and Pro "pending" device, output and NDI values (D7 sub-item a) must be **explicit `PlanGrant` rows**, not left to fall through to the dimension default. `screen_outputs` defaults to `unlimited`, so leaving it undeclared publishes "unlimited". That breaks 17tnw2az0gd's own acceptance criterion that a pending value never resolves to unlimited. Mark them pending in the row's `reason` text and cover them with a test that fails if any active plan resolves `screen_outputs` or `ndi_outputs` to `None`. Enforcement on the desktop is gated by DEC-014 until the owner answers.
- The tier-name sweep must exempt the **set** of seed migrations. A new seed migration necessarily contains "Core" and "CORE", and today only `0002` is exempt, so the sweep would flag the new file. The positive control must also run against the new file.

## Options considered for the ledger

- **Row lock on a per-org, per-week counter plus reservation rows (chosen).** Exact, O(1) reads, one short lock per spend, matches the shipped pattern. Needs Postgres for real concurrency tests.
- **Counting from an event log (`SUM` over events on every read).** No counter to drift, but reads cost O(events) on the manifest path, still needs a lock or serialisable isolation to stop two last-unit spends, and makes retention harder.
- **Redis counters.** Fast, but a second source of truth for money-shaped data, lost on eviction, and outside the audit trail. Rejected.
- **Optimistic conditional `UPDATE`.** Viable for the bare decrement (see D5), but not simpler once lazy expiry and the upgrade reset are included.

## Consequences

- A new `apps/usage` Django app, two tables, and one sweeper task. Retention: `UsageReservation` rows age out after 35 days; `UsageWeek` rows are kept for 104 weeks. Both bounds are tested so the test fails if a bound is removed. Storage grows linearly with orgs and is bounded per org.
- Concurrency tests must run on Postgres. On SQLite they pass without testing anything, because `select_for_update` does nothing there. The rules:
  - With `REQUIRE_POSTGRES=1` set in the api CI job, a skip in the concurrency tests becomes a failure.
  - The last-units race runs N threads, where N is more than the remaining allowance, and asserts that exactly `limit` succeed.
  - A test-only pause between the check and the write is the positive control. With the lock disabled, the same test must fail.
- Both meters are enforced at admission and settled by reconciliation (ADR-0028). **Neither has a hard cap.** ADR-0028 D3 and D7 state the true bounds.
- **The note-body replay cache from revision 1 is removed.** Under the directive the server never receives a note body, so it has nothing to cache. Replaying a request returns a coded `ALREADY_ISSUED` (ADR-0028 D5). This removes the sermon-content storage question (SEC-0027-04 cache rules) and Vera's byte-cap comment.
- Released-row growth is bounded by a reserve throttle of 30 per hour per org and 10 per hour per device. That gives at most 30 × 24 × 35 ≈ 25,200 rows per org over the 35-day retention. A test pins the throttle.

## Security dependency: there is no real staff login yet (SEC-0027-01)

Verified on `f211581`: the only way to act as STAFF is the header bridge in `graphql/context.py`. With `SELAHCUE_TRUST_ACTOR_HEADERS` on, the caller supplies its own identity and its own `X-SelahCue-Staff-Permissions`. With the flag off, which production requires, no STAFF actor can exist at all.

So the staff-initiated writes in this ADR cannot ship to production until a **real staff authenticator** produces the STAFF `ActorContext` and header trust is off in that environment. Those writes are:

- plan grants (D1);
- price edits (D4);
- limit edits (D10).

Closing 86ajyq86g does **not** meet this. Its finding 6 is marked "Partly": the header is stripped at the edge, but that is not a login. A new ticket must deliver the authenticator; Priya or Diego will create it. The grant and price tickets each gain one criterion: a test of the production settings fails if these mutations are enabled while header trust is on.

Permissions and audit (SEC-0027-05):

- A new `StaffPermission.GRANT_PLAN` gates plan grants.
- A new `StaffPermission.MANAGE_PLAN_PRICING` gates price and limit edits. Neither reuses `GRANT_ENTITLEMENT`.
- Each write calls `record_audit_event` with the before and after values, the reason, and `request_id = idempotency_key`.
- `PlanPrice.effective_from` must not be in the past.
- The price service offers no update or delete path.

Other rules:

- **Plan rank (SEC-0027-06).** `Plan.rank` changes **only by migration**. No admin mutation edits it.
- **Kill switch (SEC-0027-08).** The enforcement kill switch is read at startup and logs a warning when it is off. In production it writes an ops audit event. It is listed in `docs/ops/DEPLOYMENT.md` next to `SELAHCUE_TRUST_ACTOR_HEADERS`.
- **Overrun audit.** Overruns are recorded as a `SERVICE` actor, with the action `usage.overrun_recorded`.

**Tenant scoping (SEC-0027-04):**

- The org for every reserve, issue, settle, `GET /v1/quota` and `remaining()` call comes only from the authenticated device: device token, then licence key, then org.
- Every lookup of a reservation filters by that org. A reservation that belongs to another org returns `NOT_FOUND`.
- A replay must also match `device_id`.

## Review dispositions (PR #111, revision 1)

| Finding | Outcome |
|---|---|
| Vera High 1: worker and connection held during the LLM call | Resolved by the directive. The residual mint call is bounded (ADR-0028 D6). If the owner picks ADR-0028 D4 option C, it is resolved by a Celery task and a 202 response instead. |
| Vera High 2: STT starvation and TTL | Reservations are taken in fixed slices, and `ISSUED` has no time-based release (ADR-0028 D5). |
| Vera Medium: read path | Reads take no lock and have a query budget; the quota throttle is per device; polling uses jitter (D5, D9). |
| Vera Medium: retention | Sweeper scheduled, batched deletes, partial index, reserve throttle with a stated row bound (D5, Consequences). |
| Vera Medium: vacuous Postgres tests | `REQUIRE_POSTGRES`, an N-thread race and a positive control (Consequences). |
| Vera Low: counters and lock order | Reset never zeroes open reservations; full lock order stated (D5). |
| Vera Medium: replay cache bytes | Cache removed (Consequences). |
| SEC-0027-01 | Security dependency section above. |
| SEC-0027-02 | ADR-0028 D2, D3 and D5. |
| SEC-0027-03 | Replay table in ADR-0028 D5. Charging from provider totals closes "N calls charged as one" by construction. |
| SEC-0027-04 to 08 | Tenant scoping, permissions, rank, time zone and kill-switch rules above, plus D5. |

## Rollback

- Every schema change is additive except the removal of `LEGACY` and `PLATINUM`. That runs pre-launch and is reversible by a migration that re-creates them from the `0002` constants.
- The ledger can be switched off by making both enforcement points admit without reserving (a settings flag defaulting to on). This rolls back enforcement without losing data. The manifest `usage` object is additive, so removing it breaks no client.
