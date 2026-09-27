# ADR-0027 — Plan catalogue, effective plan and the weekly usage ledger (Free / Core / Pro)

- Status: **Proposed** — architecture review of the 2026-09-27 plan-limits design, before backend build starts
- Date: 2026-09-27
- Confidence: **Medium-High.** Current state is verified against `origin/main` at `f211581`. The ledger design is reasoned from the shipped concurrency pattern (`devices/services.py` `select_for_update` on the licence row) and has not been spiked. The STT finding in D6 is verified against Deepgram's own documentation.
- Owner: Software Architect (Aria). Delivery: Backend Engineer (Kenji). Required reviewers before `Accepted`: Security Reviewer (Sana) for D4–D6, Performance Engineer (Vera) for D5.
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
- `UsageReservation(org, week, meter, units, state = RESERVED | COMMITTED | RELEASED, idempotency_key, device_id, expires_at, created_at)`. Unique on (org, meter, idempotency_key).

Protocol for a spend (notes, and STT in D6):

1. **Reserve.** One short `transaction.atomic()`. Lock the `UsageWeek` row with `select_for_update` (create it with `get_or_create`, retrying once on `IntegrityError`, which is the house idempotency pattern). Lazily release this org's expired reservations. Apply D7's upgrade rule. Check `committed + reserved + units ≤ limit`. Insert the reservation and bump `*_reserved`. **Commit.** The provider is called only after this transaction commits.
2. **Commit or release.** A second short transaction, locking the same row: move the reservation to COMMITTED (bump committed, drop reserved) or RELEASED (drop reserved).
3. **Crash safety.** A reservation not settled by `expires_at` is released lazily by the next reserve for that org, and by a sweeper job for tidiness. **Correctness never depends on the job**, the same principle 17tnw2az0gh uses for grant expiry.

Why row locking and not optimistic concurrency. Both are correct. A conditional `UPDATE … WHERE committed + reserved < limit` is lock-free, but the reserve step also has to create the week row, expire stale reservations and apply the upgrade reset. Doing that as one guarded write is more complex than one short lock. The lock is per org, so it serialises only one church's handful of devices, and it is held for milliseconds. It matches the shipped activation pattern.

The rule that makes this safe: **never hold the lock, or the transaction, across the provider call.** Wrapping the whole generate request in `transaction.atomic()` would hold a row lock and a database connection for the full LLM latency (tens of seconds). That serialises every device in the org and can exhaust the connection pool under load.

Timeout invariant. The reservation TTL must be longer than the provider hard timeout plus processing time. Assert this at import, beside both constants, in the style of `DEGRADED_MANIFEST_TTL_SECONDS`. If a success does arrive after its reservation expired, the commit re-reserves if a unit is free. If none is free, the note is still delivered (the provider has already been paid), it is committed as a recorded overrun, and it is audited. That bounds the overrun to one unit per late success.

Lock order. Any path that locks both the org (grants, plan assignment) and a `UsageWeek` row locks the org first.

Reads. `remaining(org)` is one primary-key read of `UsageWeek` plus `effective_plan`. It meets the manifest p95 budget and **writes nothing**. If D7's upgrade reset is due but has not been written yet, the read computes it virtually.

Usage is per org, so it **must not** go into the catalogue `GRANT_CACHE`. That cache is keyed per plan and shared across tenants. Putting org usage in it would leak one tenant's figures to another and grow the key space with the number of orgs.

### D6 — Cloud transcript: the token mint can admit a session but cannot bound it

Verified from Deepgram's documentation: a temporary token only has to be valid when the WebSocket opens. An open stream is **not** re-authenticated when the token expires. Capping the token's TTL at the remaining allowance therefore caps nothing: an admitted stream runs until the client closes it.

So:

- **Admission.** At `stt/session`, reserve `min(remaining, session_cap)` seconds (D5). A second device then sees only what is left. Without the reservation, N devices can each be admitted against the same remaining balance.
- **Charging comes from server-side truth, not client reports.** A client that under-reports would get unlimited transcription, one capped session at a time, because its balance would never go down. Settle each reservation from the provider's own usage records for that session (Deepgram's usage API, which depends on the attribution spike 86akby344). A client report through `usage-events:batch` (86ak10amq) is only a provisional figure for display.
- **The overrun is bounded by the length of one stream, which the client controls.** The honest bound is enforced after the fact: when reconciliation shows an org over its limit, the next admission is refused. A hard cap needs a server-side stream proxy, which is out of scope and should be decided on its own.
- **"Only delivered time counts"** (the refund analogy, still open on 17tnw2az0gu) should be defined as "what the provider billed us for this session". That is the only definition the server can check.

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

Live figures come from `GET /v1/quota`. Clients must not re-issue manifests to refresh usage. Every issuance signs a payload and writes an audit row, so polling would grow the audit table in step with how often clients look at a meter. `GET /v1/quota` is throttled and does not audit every read.

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
- Concurrency tests must run on Postgres. On SQLite they pass vacuously, because `select_for_update` does nothing there.
- STT enforcement (17tnw2az0gq) depends on server-side usage reconciliation with the provider, which today is a non-goal of 86akby3xu. The worst-case overrun is honestly "one stream" until a proxy exists.
- Notes idempotency replay cannot return the note body without storing sermon content, and the ledger ticket forbids storing it. A replay of a committed request returns the charge outcome plus the body only from a short-lived, size-bounded cache. After that, it returns a coded "already delivered".

## Rollback

- Every schema change is additive except the removal of `LEGACY` and `PLATINUM`. That runs pre-launch and is reversible by a migration that re-creates them from the `0002` constants.
- The ledger can be switched off by making both enforcement points admit without reserving (a settings flag defaulting to on). This rolls back enforcement without losing data. The manifest `usage` object is additive, so removing it breaks no client.
