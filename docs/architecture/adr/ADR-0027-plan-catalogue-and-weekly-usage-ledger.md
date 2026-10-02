# ADR-0027 — Plan catalogue, effective plan and the weekly usage ledger (Free / Core / Pro)

- Status: **Proposed**, revision 4 (2026-10-02). Not yet `Accepted`: the conditions are listed under "Needed before Accepted" below.
- Date: 2026-09-27 (first revision); revision 4 dated 2026-10-02. What each revision changed is under "Revision history" below.
- Confidence: **Medium-High.** The current state was verified against `origin/main` at `f211581`. Revision 4 re-checked only the claims it edits (D3's two refusals, the PRD lines and the `openai.rs` comment cited below) on `feaee70`. The rest of "What already ships" was not re-run. The ledger design is reasoned from the concurrency pattern that already ships (`select_for_update` on the licence row in `devices/services.py`). It has not been spiked.
- Owner: Software Architect (Aria). Delivery: Backend Engineer (Kenji). Required reviewers before `Accepted`: Security Reviewer (Sana) for D4–D6 and the security dependency section; Performance Engineer (Vera) for D5.
- Companion: **ADR-0028** decides three things this ADR relies on:
  - how the desktop reaches Deepgram and OpenAI directly;
  - how usage is attributed to a church;
  - how reservations are settled from the provider's own usage figures.
- Relates: DEC-004 (licensing model), DEC-008 (superseded in part by OD-7 and OD-8), DEC-009 (Free fallback after grace), DEC-014 (fallback plan gate; its premise is amended by D3), ADR-0021 (admin licensing platform). ClickUp: [EPIC 17tnw2az0g6](https://app.clickup.com/t/17tnw2az0g6) and its build tickets 17tnw2az0gd, 17tnw2az0gg, 17tnw2az0gh, 17tnw2az0gj, 17tnw2az0gn, 17tnw2az0gq, 17tnw2az0gr.
- Also relates to the following, with **amendments still to be made** (they are open items under "Needed before Accepted"; this PR edits none of these documents):
  - **Platform PRD** (`docs/product/prds/SelahCue-Platform-PRD.md`): FR-533, FR-546, FR-547, AS-P6, AS-P7 and FLOW-507. They still describe a monthly period that resets on the billing anniversary and metering that devices report. D5 and D8 below, and ADR-0028 D2, replace that with a weekly period that resets on Monday 00:00 in the org's time zone, and charging taken from the provider's own records. FR-547 (exhaustion degrades transcription and never blocks live output) is unchanged.
  - **ADR-0010** (AI / provider abstraction, Accepted): cloud is off by default and consent-gated per provider, and user-supplied keys live only in the OS secret store (FR-132 to FR-134). Nothing here weakens either rule. ADR-0028 D8 says how platform-issued credentials fit, and ADR-0010 needs one clause saying so.
  - **ADR-0019** (transcript-provider seam): the Deepgram adapter plugs into its `STTProvider` seam and gets its credential through ADR-0028 D1. ADR-0019 needs no change.
- Decision labels. "D7", "D8" and "D9" used to mean three different things across the owner's decisions and the two ADRs, so this PR uses these labels:
  - `D<n>` is a decision in this ADR, and `ADR-0028 D<n>` is a decision in the companion.
  - `OD-7`, `OD-8` and `OD-9` are the product owner's decisions D7, D8 and D9. Their text is the owner's and is recorded in `DECISION-LOG.md` by [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu). This ADR records only **how** the platform implements them.
  - `OD-R1` to `OD-R3` are the owner's three answers of 2026-09-27 (notes provider, retry grace, overrun carry). They are recorded in ADR-0028.
  - `SEC-0027-nn` are Sana's security findings on revision 1.

---

## Revision history

- **Revision 4 (2026-10-02)** answers the review of revision 3 (PR #111, reviewed at `38755430`):
  - D3 now says what happens to both fallback refusals, and in what order the change ships.
  - D5 has one source of truth for held allowance (the open reservation rows, no `*_reserved` counters), names its index, restates the reserve throttle with its arithmetic, and softens the crash-window claim about `RESERVED` rows.
  - Retention (Consequences) deletes only `SETTLED` and `RELEASED` rows.
  - D7 no longer says an upgrade starts "the week's counters again from 0" in a way that contradicts D5.
  - The staff-authenticator ticket is recorded as a condition of `Accepted`.
  - The header is reordered, the owner's decisions have their own labels, and the new "Needed before Accepted" section lists what is still open.
- **Revision 3 (2026-09-27)** recorded three owner decisions, all settled (details in ADR-0028, "Owner decisions, 2026-09-27"):
  - **Sermon notes: ADR-0028 option A, spiked first; option C if the spike fails; option B rejected** (OD-R1). The spike (Nova) is the only thing still pending.
  - **One retry per notes session** (OD-R2). This is an exception to OD-7's "failures are never charged" rule (see Context and D5). It must be added to 17tnw2az0gu.
  - **Overrun carries into the following week only, capped at one week of debt** (OD-R3, ADR-0028 D7). `UsageWeek` gains two debt columns (D5).
- **Revision 2 (2026-09-27)** covered the owner's direct-to-provider directive, Vera's review (performance) and Sana's review (security):
  - How a spend is settled: D5's commit and release now follow ADR-0028 D5.
  - D6 is replaced by ADR-0028.
  - A security dependency section is new.
  - Every review finding has a recorded outcome (see "Review dispositions").
- **Revision 1 (2026-09-27, `e8e782d`)** was the first architecture review of the plan-limits design, done before the backend build starts.

## Context

The owner replaced DEC-008's Free / Pro / Platinum monthly model with Free / Core / Pro and **weekly** allowances for two cloud-only features: cloud transcript minutes (20 / 50 / 80) and sermon-note generations (1 / 5 / 10). Prices and limits must be data. A SuperAdmin can grant a plan for 1–12 months. The week resets Monday 00:00 in the account's time zone. An upgrade grants the full new allowance at once; a downgrade caps and claws nothing back. Failures caused by SelahCue or the AI provider are never charged. **Amended by the owner, 2026-09-27 (OD-R2):** under the direct-to-provider directive the server cannot see a failed notes generation, so the rule is kept by a **retry grace of one retry per notes session** (ADR-0028 D5). A failed generation and its one retry cost one unit together. The OD-7 text on 17tnw2az0gu needs this exception added.

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

OD-9 says a lapsed grant reverts to "the paid plan, or Free", and DEC-009 says a lapsed licence degrades to Free. Both contradict a permissive `LEGACY` fallback. Pre-launch, with no customers, the fallback moves to Free:

- A new migration (never an edit to `0002`) repoints every `PlanScopeAlias` and any `LicensePlanAssignment` on `LEGACY`, `PLATINUM` or the old `PRO` to the new rows, then removes `LEGACY` and `PLATINUM`. `PROTECT` foreign keys make an unhandled reference fail loudly, which is correct.
- Invariant, tested: **the fallback plan has the lowest rank.** This replaces the reasoning behind the two refusals below.
- **Both fallback refusals are removed.** Revision 3 named only the first. Two refusals exist on `origin/main` (verified on `feaee70`). Both test `plan.is_fallback`, both raise `POLICY_DENIED`, and both exist for the same reason, that the fallback was the *most* permissive plan:
  - `set_license_plan_assignment` (`catalogue/services.py:766`) refuses to assign a licence to the fallback;
  - licence issuance (`license_keys/services.py:224`, the second half of DEC-014's issuance rule) refuses to issue a licence on the fallback.

  Once Free is the fallback and has the lowest rank, neither protects anything: naming Free by mistake grants the least, not the most. Assigning a licence to Free and issuing one on Free become ordinary operations, and the invariant test takes the place of both refusals. The error text and log text of both refusals ("the most permissive values") would also be false, so they go with them.
- **Ordering.** The removal ships in the same release as the migration and never before it. While `LEGACY` is still the fallback, both refusals still guard the most permissive plan.
- **What stays.** The unknown-plan refusal (`NOT_FOUND`) and DEC-014 point 2 (new issuance must name an explicit plan) at the same site, and resolution itself: a licence with no assignment still resolves to the fallback.
- **Tests that pin the refusals are rewritten by the ticket that lands the migration.** They assert the opposite once the refusals are gone. They are `test_issuing_on_the_designated_fallback_is_refused_and_creates_nothing`, `test_the_fallback_refusal_names_why_rather_than_only_refusing`, `test_the_fallback_refusal_reaches_the_log_where_an_operator_will_look` and `test_the_refusal_follows_the_is_fallback_FLAG_not_the_plan_code` in `tests/test_license_issuance_requires_plan.py`, and `test_assigning_a_licence_to_the_designated_fallback_is_refused` and `test_the_assignment_refusal_leaves_resolution_and_the_fallback_untouched` in `tests/test_product_catalogue_slice.py`. Their siblings that prove a sellable plan still issues and assigns stay as they are.

This amends DEC-014's premise. It must be recorded with OD-7 on 17tnw2az0gu.

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

- `UsageWeek(org, week_start_local, tz_name, starts_at, ends_at, stt_seconds_settled, notes_settled, stt_seconds_reset_baseline, notes_reset_baseline, stt_seconds_carried_debt, notes_carried_debt, high_water_rank, rank_at_last_reset)`. Unique on (org, week_start_local).
  - `*_settled` is the usage reconciliation has taken from the provider's records for this week (ADR-0028 D5). It only grows within a week, so recomputing it from the records is repeatable.
  - `*_reset_baseline` is the value of `*_settled` when D7's upgrade reset last ran. Usage that **counts** against the limit is `*_settled − *_reset_baseline`.
  - The two `carried_debt` columns (revision 3) hold the previous week's overrun, capped at this week's limit (ADR-0028 D7). The upgrade reset never touches them.
  - The time zone and both boundaries are **fixed when the row is created**. That is how "a time-zone change applies from the next reset" works without any extra state.
  - **There are no `*_reserved` counters.** Revision 1 had `stt_seconds_charged`, `notes_committed` and two `*_reserved` columns. Revision 2 removed the `COMMITTED` state but left those names behind. Revision 4 replaces the stale names and removes the reserved counters (next paragraph).
- `UsageReservation(org, week, meter, units, state = RESERVED | ISSUED | SETTLED | RELEASED, idempotency_key, request_hash, device_id, issued_at, retry_count, expires_at, created_at)`. Unique on (org, meter, idempotency_key).

**Revision 2.** Under the owner's direct-to-provider directive, the server never calls the provider on a spend and never sees the outcome. The reservation states and settlement rules are therefore defined in **ADR-0028 D5**: `RESERVED → ISSUED → SETTLED`, with `RELEASED` allowed only from `RESERVED` (a failed mint, or a `RESERVED` row that aged out; see step 4 below). They replace revision 1's COMMITTED state. Compared with revision 1, the table gains three columns:

- `request_hash`;
- `issued_at`;
- `retry_count`.

**One source of truth for held allowance: the open reservation rows.** The allowance a church is holding right now is `Σ units` over the current week's reservations in state `RESERVED` or `ISSUED`, and nowhere else. Two sources would have to agree. A stored `*_reserved` counter would need an adjustment on every transition (`RESERVED → RELEASED`, `ISSUED → SETTLED`, and each retry) from three writers (reserve, the sweeper and reconciliation), and a single missed adjustment drives it negative or leaks allowance. The sum cannot drift. It is cheap, for two reasons:

- It is served by a partial index on `(week_id) WHERE state IN ('RESERVED', 'ISSUED')`, so it reads only open rows of one week.
- The number of open rows is capped by the check itself, because every open row holds at least one note unit or one 300-second slice. At today's limits that is at most 16 transcript rows (Pro: 80 min × 60 = 4,800 s ÷ 300 s) and 10 notes rows (Pro) per org per week: 26 rows at most, whatever the history. A test seeds a week with that many open rows and pins the query count.

Protocol for a spend (both meters):

1. **Reserve.** This is one short `transaction.atomic()`:
   - Find the current `UsageWeek` row by `starts_at ≤ now < ends_at` (SEC-0027-07). Lock it with `select_for_update`. If it does not exist, create it with `get_or_create` and retry once on `IntegrityError`, which is the house idempotency pattern.
   - Apply D7's upgrade rule.
   - Check `carried_debt + (settled − reset_baseline) + Σ units of open reservations + units ≤ limit`, using the `UsageWeek` row just locked and the indexed sum above.
   - A notes **retry** (ADR-0028 D5) reserves no new unit. It only moves `retry_count` from 0 to 1 on the existing ISSUED reservation, under this same lock, within 10 minutes of `issued_at`.
   - Insert the reservation as `RESERVED`, then commit.

   Reads take **no** lock. A test fails if `remaining()` emits `FOR UPDATE`. Both `remaining()` and reserve have a query budget (`django_assert_num_queries`), and `effective_plan` counts inside it.
2. **Issue.** Close the database connection, then call the provider's mint endpoint with hard timeouts (ADR-0028 D6).
   - If the mint succeeds: a second short transaction moves the reservation to `ISSUED`.
   - If the mint fails: it moves to `RELEASED`.
3. **Settle.** Only reconciliation settles a reservation. It uses the provider's own usage records (ADR-0028 D5).
4. **Crash safety.**
   - A `RESERVED` row older than its TTL is treated as "nothing was issued", and is released lazily by the next reserve and by the sweeper. That is **almost always true, but it is not guaranteed.** The mint and the move to `ISSUED` are two transactions with a provider call between them. A process that dies after a successful mint and before the second transaction leaves a live credential behind a `RESERVED` row. Releasing the row is still safe for the ledger, for three reasons:
     - The credential cannot still be used to start a session when the row is released. `RESERVED_TTL` must be longer than the mint timeouts **plus** the longest credential TTL (the timeout invariant below), and a stream can only start while the credential is valid.
     - The charge never depends on the reservation. Usage under the credential is attributed by its identity and charged by reconciliation (ADR-0028 D2 and D5). A released row can understate the church's *held estimate* for a while. It cannot understate the *charge*.
     - A crashed mint leaves at most one such credential, and a re-reserve under the same idempotency key (ADR-0028 D5, replay table) can add at most one more. Both are charged by reconciliation.

     What this does not cover is a stream that was already open when the row was released. Until reconciliation records it, it holds no estimate. That is the same exposure as any held-open stream (ADR-0028 D3 and D7).
   - An `ISSUED` row is **never** released by time. It stays counted until reconciliation settles it.
   - **Correctness never depends on the job**, the same principle 17tnw2az0gh uses for grant expiry.
   - The sweeper is scheduled in `CELERY_BEAT_SCHEDULE`, and a test checks it is registered. It deletes in batches, following the `accounts/maintenance.py` pattern. What it may delete is fixed by the retention rule under Consequences: it never deletes an `ISSUED` row.
   - A second partial index, on `(org, expires_at) WHERE state = 'RESERVED'`, keeps the lazy release cheap while the lock is held. The sum of open reservations does **not** use it; it uses the `(week_id)` index above.

Why row locking and not optimistic concurrency. Both are correct. A conditional `UPDATE … WHERE` on a counter is lock-free, but the check here is over the settled usage and the open reservation rows (above), and the reserve step also has to create the week row, expire stale reservations and apply the upgrade reset. Doing that as one guarded write is more complex than one short lock. The lock is per org, so it serialises only one church's handful of devices, and it is held for milliseconds. It matches the shipped activation pattern.

The rule that makes this safe: **never hold the lock, or the transaction, across any provider call.** That covers the mint call and the reconciliation job's read of the usage API. Under the directive, the server no longer waits on a generation. Vera's worker and connection finding is resolved, with a bounded residual for the mint call; ADR-0028 D6 sets out the residual and its timeouts.

Timeout invariant. `RESERVED_TTL` must be longer than the mint call's connect timeout **plus** its read timeout **plus** the longest credential TTL the mint can return (30 s for a Deepgram grant token, ADR-0028 D3; the client-secret TTL for OpenAI, ADR-0028 D4). That way, by the time a `RESERVED` row can be released, any credential minted in the crash window has expired. Assert this at import, next to all three constants, in the style of `DEGRADED_MANIFEST_TTL_SECONDS`. An `ISSUED` reservation has no time-based release, so it needs no TTL invariant. The "one unit per late success" overrun rule from revision 1 no longer applies: late usage is charged by reconciliation, in the week it happened.

Upgrade reset (D7) moves `*_reset_baseline` up to the current `*_settled`, so the usage that counts restarts from 0. It **never** touches the open reservations or the carried debt, and it never lowers `*_settled`. Open reservations are allowance that is held right now for a credential already out. Releasing it on an upgrade would let a church spend the same allowance twice, and wiping the debt would turn an upgrade into a debt write-off.

Reserve throttles. Until revision 4 there was one budget, of 30 per hour per org and 10 per hour per device. That budget could not carry transcripts, because a transcript session is reserved in 5-minute slices (ADR-0028 D5) and each slice renewal goes through the same endpoint. Reserve calls are therefore three classes with separate budgets:

| Class | What it is | Budget |
|---|---|---|
| Admission | A new session on either meter: a fresh idempotency key that does not extend a live session | 30 per hour per org, 10 per hour per device |
| Slice renewal | Transcript only. Extends the device's own live session by the next slice, naming that session's latest `ISSUED` slice. A renewal that does not need a new token makes no provider call | 30 per hour per org, 15 per hour per device |
| Notes retry | Moves `retry_count` from 0 to 1 and creates no row (ADR-0028 D5) | None. One per notes session, by rule |

The arithmetic behind the renewal budget:

- One device streaming continuously needs 60 min ÷ 5 min = **12 slices per hour**. Under the old 10-per-hour device budget it would have been refused from the 11th slice of every hour. A 70-minute sermon on Pro needs 70 ÷ 5 = **14 slices** (one admission and 13 renewals).
- The per-device budget of 15 is those 12, plus 3 for a reconnect that asks for a slice again.
- The per-org budget of 30 is two devices streaming at once (2 × 12 = 24), plus 6.
- Admissions keep their old figures. The review's finding was about renewals only, and a church starts a few sessions a day, not ten an hour.

Row ceiling per org, over the 35-day retention (Consequences): admissions 30 × 24 × 35 = 25,200, plus renewals 30 × 24 × 35 = 25,200, which is **50,400 rows**. Revision 3's 25,200 counted admissions only. This is a ceiling, not a forecast. A row that stays open holds allowance (at most 26 open rows per week, above), so only `RELEASED` rows (failed mints) and rows that settle quickly can pile up at the throttle rate. A church that uses its full Pro allowance creates 16 transcript slices and 10 notes rows a week. Tests pin all three budgets, and one test asserts that a 70-minute stream on Pro (one admission and 13 renewals) is admitted without a throttle refusal. That test is the one that fails if renewals fall back under the admission budget.

Lock order: the org first, then the licence key (`AppLicenseKey`, as activation and the state machine lock it), then `UsageWeek`. Every path that takes more than one of these locks takes them in this order.

Reads. `remaining(org)` is one read of `UsageWeek` through its unique index, plus `effective_plan` and the one indexed sum of open reservations (at most 26 rows at today's limits). It takes no lock, and a query budget pins its cost. It meets the manifest p95 budget and **writes nothing**. If D7's upgrade reset is due but has not been written yet, the read computes it virtually.

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

If `rank(effective_plan) > high_water_rank`, set `rank_at_last_reset` and `high_water_rank` to the new rank and move each `*_reset_baseline` up to the current `*_settled`. The usage that **counts** against the new limit therefore restarts from 0 (`counted = settled − baseline`). That is the whole effect. **Open reservations and `carried_debt` are untouched** (D5): an upgrade never releases a held reservation and never wipes debt, and no settled figure goes down. Provider usage records keep their full history. A downgrade changes nothing, because `remaining = max(0, limit − carried_debt − counted − open reservations)`.

A limit edit (Core 5 → 6) is **not** a plan change, so it never resets anything. The comparison is on rank, never on the limit value.

The high-water mark also closes the downgrade-then-upgrade loophole (open item 6 on 17tnw2az0gu). Pro → Free → Pro in one week does not reset twice, because Pro is already the week's high-water mark. Free → Core → Pro still resets at each step, as OD-8 intends. **This is a recommendation for the owner, not a decision.** Without it, the high-water check becomes "rank increased since the last spend" and the loophole stays open.

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
- Core and Pro "pending" device, output and NDI values (OD-7 sub-item a) must be **explicit `PlanGrant` rows**, not left to fall through to the dimension default. `screen_outputs` defaults to `unlimited`, so leaving it undeclared publishes "unlimited". That breaks 17tnw2az0gd's own acceptance criterion that a pending value never resolves to unlimited. Mark them pending in the row's `reason` text and cover them with a test that fails if any active plan resolves `screen_outputs` or `ndi_outputs` to `None`. Enforcement on the desktop is gated by DEC-014 until the owner answers.
- The tier-name sweep must exempt the **set** of seed migrations. A new seed migration necessarily contains "Core" and "CORE", and today only `0002` is exempt, so the sweep would flag the new file. The positive control must also run against the new file.

## Options considered for the ledger

- **Row lock on a per-org, per-week counter plus reservation rows (chosen).** Exact, O(1) reads, one short lock per spend, matches the shipped pattern. Needs Postgres for real concurrency tests.
- **Counting from an event log (`SUM` over events on every read).** No counter to drift, but reads cost O(events) on the manifest path, still needs a lock or serialisable isolation to stop two last-unit spends, and makes retention harder.
- **Redis counters.** Fast, but a second source of truth for money-shaped data, lost on eviction, and outside the audit trail. Rejected.
- **Optimistic conditional `UPDATE`.** Viable for the bare decrement (see D5), but not simpler once lazy expiry and the upgrade reset are included.

## Consequences

- A new `apps/usage` Django app, two tables, and one sweeper task.
- **Retention.** The sweeper deletes **only `SETTLED` and `RELEASED` rows**, and only once their `created_at` is more than 35 days old.
  - A `RESERVED` row is released by its TTL first (D5 step 4) and then ages out as `RELEASED`.
  - An `ISSUED` row is **never deleted by time**. It is the only record that a credential left the building and has not yet been reconciled. If a provider's usage reporting is down, `ISSUED` rows stay and stay counted until reconciliation settles them (ADR-0028 D5, reconciliation step 6). Their number is bounded anyway: each holds an estimate against its week's allowance, so there are at most 26 open rows per org per week at today's limits (D5), and once the allowance is held, further reserves are refused. An outage therefore adds at most 26 rows per org per week. The sweeper counts `ISSUED` rows older than 35 days and raises an alert with that count. It deletes none.
  - `UsageWeek` rows are kept for 104 weeks. A week that still has an `ISSUED` reservation is not deleted.
  - The retention tests seed old `SETTLED`, `RELEASED` and `ISSUED` rows and assert that the first two go and the third stays. They fail if a bound is removed, and they fail if the sweeper starts deleting `ISSUED` rows.
  - Storage grows linearly with orgs and is bounded per org: the throttle ceiling of 50,400 rows per 35 days (D5, "Reserve throttles") plus the `ISSUED` backlog above.
- Concurrency tests must run on Postgres. On SQLite they pass without testing anything, because `select_for_update` does nothing there. The rules:
  - With `REQUIRE_POSTGRES=1` set in the api CI job, a skip in the concurrency tests becomes a failure.
  - The last-units race runs N threads, where N is more than the remaining allowance, and asserts that exactly `limit` succeed.
  - A test-only pause between the check and the write is the positive control. With the lock disabled, the same test must fail.
- Both meters are enforced at admission and settled by reconciliation (ADR-0028). **Neither has a hard cap.** ADR-0028 D3 and D7 state the true bounds.
- **The note-body replay cache from revision 1 is removed.** Under the directive the server never receives a note body, so it has nothing to cache. Replaying a request returns a coded `ALREADY_ISSUED` (ADR-0028 D5). This removes the sermon-content storage question (SEC-0027-04 cache rules) and Vera's byte-cap comment.
- Row growth is bounded by the reserve throttles in D5: admissions at 30 per hour per org and 10 per hour per device, and slice renewals at 30 per hour per org and 15 per hour per device. Over the 35-day retention that is at most 25,200 + 25,200 = 50,400 rows per org (revision 3's 25,200 counted admissions only). Tests pin the budgets.

## Security dependency: there is no real staff login yet (SEC-0027-01)

Verified on `f211581` and re-checked on `feaee70`: the only way to act as STAFF is the header bridge in `graphql/context.py`. With `SELAHCUE_TRUST_ACTOR_HEADERS` on, the caller supplies its own identity and its own `X-SelahCue-Staff-Permissions`. With the flag off, which production requires, no STAFF actor can exist at all.

So the staff-initiated writes in this ADR cannot ship to production until a **real staff authenticator** produces the STAFF `ActorContext` and header trust is off in that environment. Those writes are:

- plan grants (D1);
- price edits (D4);
- limit edits (D10).

Closing 86ajyq86g does **not** meet this. Its finding 6 is marked "Partly": the header is stripped at the edge, but that is not a login.

**No ticket id is recorded for the authenticator.** A ticket must exist for it, and its id must be recorded here, before this ADR moves to `Accepted`. If one has already been created, the owner supplies its id. This revision does not invent one.

- Ticket id: **none recorded. Owner to supply.**
- What it must deliver: a real staff authenticator that produces the STAFF `ActorContext`, so that `SELAHCUE_TRUST_ACTOR_HEADERS` can be off in production while staff still work.
- The grant and price tickets each gain one criterion: a test of the production settings fails if these mutations are enabled while header trust is on.

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
| Vera High 1: worker and connection held during the LLM call | Resolved by the directive. The residual mint call is bounded (ADR-0028 D6). If the Realtime spike fails and notes fall back to ADR-0028 D4 option C (owner-approved), it is resolved by a Celery task and a 202 response instead. |
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

## Review dispositions (PR #111, review of revision 3 at `38755430`, 2026-10-02)

| Finding | Outcome |
|---|---|
| Process 1: title and body describe revision 1 only | PR title and body rewritten to cover ADR-0027 revision 4, ADR-0028 revision 3 and the goal contract, with the list below. |
| Process 2: 18 unresolved threads; no re-review of revisions 2 and 3 | Not fixed here. Resolving threads and the independent re-review (goal contract C-008) belong to the reviewers. |
| a. The twin refusal at `license_keys/services.py:224` | D3: both refusals are removed, in the same release as the migration, never before it. |
| b. Throttle against 5-minute slice renewals | D5, "Reserve throttles": renewals have their own budget; the arithmetic and the new 50,400-row ceiling are shown; Consequences updated. |
| c. Retention versus `ISSUED` rows | Consequences: the sweeper deletes only `SETTLED` and `RELEASED` rows; `ISSUED` rows never age out by time and raise an alert instead. |
| d. Index for the open-estimates sum; two sources of truth; stale column names | D5: the open reservation rows are the single source; the `*_reserved` counters are gone; partial index on `(week_id)`; the columns are `*_settled` and `*_reset_baseline`. |
| e. D7 wording against D5 and ADR-0028 | D7 reworded: an upgrade moves the baseline and touches nothing else. |
| f. SEC-0027-01 names no ticket | Security dependency: the ticket must be created and its id recorded here before `Accepted`. Id: none recorded; owner to supply. |
| j. "A `RESERVED` row older than its TTL has issued nothing" | D5 step 4: softened for the mint-to-`ISSUED` crash window, with the bound and a stronger timeout invariant. |
| k. PRD, ADR-0010, ADR-0019, desktop custody | Relates section, ADR-0028 D8, and "Needed before Accepted" below. |
| Cosmetic: header order; D7, D8 and D9 naming | Header reordered with a revision history. Owner decisions are `OD-7` to `OD-9` and `OD-R1` to `OD-R3`. |

(g, h and i are in ADR-0028.)

## Needed before Accepted

Nothing in this list is done by this PR, except where it says so.

1. **Independent re-review.** Sana for D4–D6 and the security dependency section; Vera for D5. This is goal contract criterion C-008. The 18 inline threads from revision 1 are to be resolved by the reviewers. Sana's earlier note that removing the assignment refusal is safe once the invariant test exists covered only that one refusal; she should confirm D3's removal of the issuance refusal too.
2. **Staff-authenticator ticket (SEC-0027-01).** Make sure the ticket exists and record its id in the Security dependency section. Id: **none recorded; owner to supply.**
3. **Recorded on 17tnw2az0gu and in `DECISION-LOG.md`**, by Priya or Diego (the architect does not edit that ticket):
   - the OD-7 exception for the notes retry (OD-R2);
   - the DEC-014 amendment from D3, including the removal of both fallback refusals;
   - the owner's answer on D7's high-water mark (a recommendation today).
4. **Platform PRD amendments** for FR-533, FR-546, FR-547, AS-P6, AS-P7 and FLOW-507 (see Relates). No ticket id is recorded. Ticket id: **none recorded; owner to supply.** It is an open item in ADR-0028 ("Open items").
5. **ADR-0010 clause and the `implementation/desktop/crates/selahcue-cloud/src/openai.rs` comment (lines 6 to 7).** No ticket id is recorded for either. Both are open items in ADR-0028 ("Open items"), with ticket ids **none recorded; owner to supply**.
6. **The open items in ADR-0028**, which also gate this ADR's settlement and enforcement tickets: the OpenAI spike, the Deepgram spike 86akby344, `NOTE_TOKEN_ENVELOPE`, the transcript held-open ceiling, the provisioning budget, and the provider facts that have not been re-read since 2026-09-27.

## Rollback

- Every schema change is additive except the removal of `LEGACY` and `PLATINUM`. That runs pre-launch and is reversible by a migration that re-creates them from the `0002` constants.
- Removing the two fallback refusals (D3) reverts with the code. It must be reverted together with the migration, never alone, because with `LEGACY` as the fallback the refusals are what keep the most permissive plan from being assigned or issued.
- The ledger can be switched off by making both enforcement points admit without reserving (a settings flag defaulting to on). This rolls back enforcement without losing data. The manifest `usage` object is additive, so removing it breaks no client.
