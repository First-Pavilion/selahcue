# ADR-0027 — Plan catalogue, effective plan and the weekly usage ledger (Free / Core / Pro)

- Status: **Proposed**, revision 6 (2026-10-02). Not yet `Accepted`: the conditions are listed under "Needed before Accepted" below.
- Date: 2026-09-27 (first revision); revisions 4, 5 and 6 dated 2026-10-02. What each revision changed is under "Revision history" below.
- Confidence: **Medium-High.** The current state was verified against `origin/main` at `f211581`. Revision 4 re-checked the claims it edits on `feaee70`: D3's two refusals, the staff header bridge in the Security dependency section, and the PRD lines and `openai.rs` comment cited below. Revision 5 re-checked the tests and comments around D3 on the merged tree at `08b0382`. Revision 6 edits design text only and re-checked no code. The rest of "What already ships" was not re-run. ClickUp ticket ids were read on 2026-10-02. The ledger design is reasoned from the concurrency pattern that already ships (`select_for_update` on the licence row in `devices/services.py`). It has not been spiked.
- Owner: Software Architect (Aria). Delivery: Backend Engineer (Kenji). Required reviewers before `Accepted`: Security Reviewer (Sana) for D4–D6 and the security dependency section; Performance Engineer (Vera) for D5.
- Companion: **ADR-0028** decides three things this ADR relies on:
  - how the desktop reaches Deepgram and OpenAI directly;
  - how usage is attributed to a church;
  - how reservations are settled from the provider's own usage figures.
- Relates: DEC-004 (licensing model), DEC-008 (tier half superseded by owner D7, billing-anniversary period superseded by owner D8), DEC-009 (Free fallback after grace), DEC-014 (fallback plan gate; its premise is amended by D3), ADR-0021 (admin licensing platform). ClickUp: [EPIC 17tnw2az0g6](https://app.clickup.com/t/17tnw2az0g6) and its build tickets 17tnw2az0gd, 17tnw2az0gg, 17tnw2az0gh, 17tnw2az0gj, 17tnw2az0gn, 17tnw2az0gq, 17tnw2az0gr.
- Also relates to the following, with **amendments still to be made** (open items under "Needed before Accepted"; this PR edits none of these documents):
  - **Platform PRD** (`docs/product/prds/SelahCue-Platform-PRD.md`): FR-533, FR-546, FR-547, AS-P6, AS-P7 and FLOW-507. They still describe a monthly period that resets on the billing anniversary and metering that devices report. D5 and D8 below, and ADR-0028 D2, replace that with a weekly period that resets on Monday 00:00 in the org's time zone, and charging taken from the provider's own records. FR-547 (exhaustion degrades transcription and never blocks live output) is unchanged. Ticket [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu) lists FR-546, AS-P6, FLOW-507 and the tier table in its Scope; it does not name FR-533, FR-547 or AS-P7.
  - **ADR-0010** (AI / provider abstraction, Accepted): cloud is off by default and consent-gated per provider, and user-supplied keys live only in the OS secret store (FR-132 to FR-134). Nothing here weakens either rule. ADR-0028 D8 says how platform-issued credentials fit, and ADR-0010 needs one clause saying so.
  - **ADR-0019** (transcript-provider seam): the Deepgram adapter plugs into its `STTProvider` seam and gets its credential through ADR-0028 D1. ADR-0019 needs no change.
- Decision labels. These are **ClickUp's labels on [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu), used as written**, so a reader can search for them there. Because the owner's decisions D7, D8 and D9 share numbers with this ADR's own sections, the owner's are always written "owner D7", "owner D8" and "owner D9" in this ADR. The crosswalk:

  | Label | What it is | ClickUp | Where it lands |
  |---|---|---|---|
  | owner D7 | Plan lineup (Free / Core / Pro) and the weekly allowances, including the note-counting rule | [17tnw2az0g8](https://app.clickup.com/t/17tnw2az0g8) | Context, D10 |
  | owner D7 amendment | One retry per notes session: the exception to "failures are never charged" (2026-09-27) | On 17tnw2az0g8 and 17tnw2az0gu | ADR-0028 D5 |
  | owner D8 | Weekly window, Monday 00:00 in the account's zone; mid-week plan changes apply at once | [17tnw2az0ga](https://app.clickup.com/t/17tnw2az0ga) | D7, D8 |
  | owner D9 | Staff plan grants | [17tnw2az0gb](https://app.clickup.com/t/17tnw2az0gb) | D1 |
  | OD-1 | How notes reach the provider: option A first, C if the spike fails, B rejected | On 17tnw2az0gu | ADR-0028 D4 |
  | OD-2 | Overrun carry-over: following week only, capped at one week of debt | On 17tnw2az0gu | ADR-0028 D7 |
  | OD-3 | Every denied credential request is recorded | On 17tnw2az0gu | ADR-0028 D1 and D5 |

  - `D<n>` is a decision in this ADR, and `ADR-0028 D<n>` is a decision in the companion.
  - `DEC-###` numbers for the owner's decisions are assigned when 17tnw2az0gu writes them into `DECISION-LOG.md` (it takes the next free number at merge). This ADR does not guess them.
  - `SEC-0027-nn` are Sana's security findings on revision 1.

---

## Revision history

- **Revision 6 (2026-10-02)** answers the third independent review, of head `855b739`. It corrects text and records open items. It adds no new mechanism:
  - D5 slice arithmetic is corrected. Slices add, so a continuous stream renews 12 times an hour whatever the renewal lead, the 15 per hour budget leaves 3 spare, and a 70-minute stream uses 15 rows, not 14. Revision 5's "every 240 s, 15 per hour" was wrong.
  - D5 no longer claims a reconnect adds no hold. It records the reconnect case as an open item with its failure scenario (ADR-0028 OI-13).
  - D5 states that incomplete provider records are excluded from `*_settled`, and that a new week row starts with `high_water_rank` set to the current effective plan's rank. `rank_at_last_reset` is removed as redundant.
  - The timeout invariant has the option C clause that ADR-0028 already relied on.
  - ADR-0028 (revision 5) adds the retry rows to the replay table and open items OI-13 to OI-16.
  - The ticket fallout list now includes 17tnw2az0gq and 17tnw2az0gn.
- **Revision 5 (2026-10-02)** answers the independent re-review of head `255d042`:
  - Ticket ids confirmed in ClickUp are recorded (staff authenticator 17tnw2az0n5, OpenAI spike 17tnw2az0n2, PRD amendment and DECISION-LOG entries 17tnw2az0gu). "None recorded" now appears only where a ClickUp search found no ticket.
  - The owner's decision labels are ClickUp's own (owner D7, D7 amendment, owner D8, owner D9, OD-1, OD-2, OD-3), with a crosswalk. Revision 4's `OD-7` to `OD-9` and `OD-R1` to `OD-R3` are gone.
  - D5: the upgrade reset is a timestamp (`counted_from`) and no longer a settled-figure baseline, which fixes an in-flight reservation permanently reducing the new allowance. Slice renewals, reconnects and the notes retry now have defined rows, columns and budgets. A `RELEASED` row is terminal, and settlement under option C is stated.
  - D3 names the premise-pinning tests and stale comments, and says the issuance refusal came from the implementing code and not from DEC-014's text.
  - SEC-0027-07's week-start rule and test are in D5 step 1.
- **Revision 4 (2026-10-02)** answers the review of revision 3 (PR #111, reviewed at `38755430`):
  - D3 now says what happens to both fallback refusals, and in what order the change ships.
  - D5 has one source of truth for held allowance (the open reservation rows, no `*_reserved` counters), names its index, restates the reserve throttle with its arithmetic, and softens the crash-window claim about `RESERVED` rows.
  - Retention (Consequences) deletes only `SETTLED` and `RELEASED` rows.
  - D7 no longer says an upgrade starts "the week's counters again from 0" in a way that contradicts D5.
  - The staff-authenticator ticket is recorded as a condition of `Accepted`.
  - The header is reordered, the owner's decisions have their own labels, and the new "Needed before Accepted" section lists what is still open.
- **Revision 3 (2026-09-27)** recorded three owner decisions, all settled (details in ADR-0028, "Owner decisions, 2026-09-27"):
  - **Sermon notes: ADR-0028 option A, spiked first; option C if the spike fails; option B rejected** (OD-1). The spike (Nova, [17tnw2az0n2](https://app.clickup.com/t/17tnw2az0n2)) is the only thing still pending.
  - **One retry per notes session** (owner D7 amendment). This is an exception to owner D7's "failures are never charged" rule (see Context and D5). The amendment is already written on 17tnw2az0g8 and 17tnw2az0gu; only the `DECISION-LOG.md` entry is outstanding.
  - **Overrun carries into the following week only, capped at one week of debt** (OD-2, ADR-0028 D7). `UsageWeek` gains two debt columns (D5).
- **Revision 2 (2026-09-27)** covered the owner's direct-to-provider directive, Vera's review (performance) and Sana's review (security):
  - How a spend is settled: D5's commit and release now follow ADR-0028 D5.
  - D6 is replaced by ADR-0028.
  - A security dependency section is new.
  - Every review finding has a recorded outcome (see "Review dispositions").
- **Revision 1 (2026-09-27, `e8e782d`)** was the first architecture review of the plan-limits design, done before the backend build starts.

## Context

The owner replaced DEC-008's Free / Pro / Platinum monthly model with Free / Core / Pro and **weekly** allowances for two cloud-only features: cloud transcript minutes (20 / 50 / 80) and sermon-note generations (1 / 5 / 10). Prices and limits must be data. A SuperAdmin can grant a plan for 1–12 months. The week resets Monday 00:00 in the account's time zone. An upgrade grants the full new allowance at once; a downgrade caps and claws nothing back. Failures caused by SelahCue or the AI provider are never charged. **Amended by the owner, 2026-09-27 (owner D7 amendment):** under the direct-to-provider directive the server cannot see a failed notes generation, so the rule is kept by a **retry grace of one retry per notes session** (ADR-0028 D5). A failed generation and its one retry cost one unit together. The exception is already written on 17tnw2az0gu ("Amendment (owner, 2026-09-27)") and on 17tnw2az0g8 ("Exception (amended 2026-09-27)"). Only the `DECISION-LOG.md` entry is outstanding.

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

Owner D9 says a lapsed grant reverts to "the paid plan, or Free", and DEC-009 says a lapsed licence degrades to Free. Both contradict a permissive `LEGACY` fallback. Pre-launch, with no customers, the fallback moves to Free:

- A new migration (never an edit to `0002`) repoints every `PlanScopeAlias` and any `LicensePlanAssignment` on `LEGACY`, `PLATINUM` or the old `PRO` to the new rows, then removes `LEGACY` and `PLATINUM`. `PROTECT` foreign keys make an unhandled reference fail loudly, which is correct.
- Invariant, tested: **the fallback plan has the lowest rank.** This replaces the reasoning behind the two refusals below.
- **Both fallback refusals are removed.** Revision 3 named only the first. Two refusals exist on `origin/main` (verified on `feaee70`). Both test `plan.is_fallback`, both raise `POLICY_DENIED`, and both exist for the same reason, that the fallback was the *most* permissive plan:
  - `set_license_plan_assignment` (`catalogue/services.py:766`) refuses to assign a licence to the fallback;
  - licence issuance (`license_keys/services.py:224`) refuses to issue a licence on the fallback.

  Both come from the implementing code, which cites DEC-014 for them. DEC-014's own text (`DECISION-LOG.md`, DEC-014) mandates only the gate before client enforcement and that new issuance must name an explicit plan. It does not mandate either refusal.

  Once Free is the fallback and has the lowest rank, neither protects anything: naming Free by mistake grants the least, not the most. Assigning a licence to Free and issuing one on Free become ordinary operations, and the invariant test takes the place of both refusals. The error text and log text of both refusals ("the most permissive values") would also be false, so they go with them.
- **Ordering.** The removal ships in the same release as the migration and never before it. While `LEGACY` is still the fallback, both refusals still guard the most permissive plan.
- **What stays.** The unknown-plan refusal (`NOT_FOUND`) and DEC-014 point 2 (new issuance must name an explicit plan) at the same site, and resolution itself: a licence with no assignment still resolves to the fallback.
- **Tests that pin the refusals are rewritten by the ticket that lands the migration.** They assert the opposite once the refusals are gone. They are `test_issuing_on_the_designated_fallback_is_refused_and_creates_nothing`, `test_the_fallback_refusal_names_why_rather_than_only_refusing`, `test_the_fallback_refusal_reaches_the_log_where_an_operator_will_look` and `test_the_refusal_follows_the_is_fallback_FLAG_not_the_plan_code` in `tests/test_license_issuance_requires_plan.py`, and `test_assigning_a_licence_to_the_designated_fallback_is_refused` and `test_the_assignment_refusal_leaves_resolution_and_the_fallback_untouched` in `tests/test_product_catalogue_slice.py`. Their siblings that prove a sellable plan still issues and assigns stay as they are.
- **Tests that pin the premise "the fallback is `LEGACY` and permissive" are not refusal tests, but they fail once Free is the fallback.** In `tests/test_license_issuance_requires_plan.py` they are the constant `FALLBACK_PLAN_CODE = "LEGACY"`, the helper `_assert_fallback_is_the_permissive_one` (it asserts the fallback's code and that its outputs are unlimited, and six tests call it), and `test_the_fallback_mechanism_itself_is_untouched`. The tests that call the helper include `test_a_novel_feature_scope_cannot_silently_reach_the_fallback` and `test_a_licence_that_predates_this_change_still_resolves_through_the_fallback`. They keep their purpose (a licence with no assignment reaches the fallback) and need a new premise (the fallback is the lowest-rank plan).
- **Stale comments and messages.** Comments in `license_keys/services.py` say the fallback is "the most permissive in the catalogue" (the `plan_code` field note and the refusal at line 224, among others), and so does the refusal in `catalogue/services.py`. They are rewritten or removed with the refusals.

This amends DEC-014's premise, and the amendment must be recorded in `DECISION-LOG.md`. The Scope of 17tnw2az0gu lists entries for owner D7, D8 and D9 and OD-1 to OD-3, but no DEC-014 amendment, so no ticket is recorded for this one.

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

- `UsageWeek(org, week_start_local, tz_name, starts_at, ends_at, counted_from, stt_seconds_settled, notes_settled, stt_seconds_carried_debt, notes_carried_debt, high_water_rank)`. Unique on (org, week_start_local).
  - `counted_from` is a timestamp, equal to `starts_at` until D7's upgrade reset runs, and the instant of the last reset after that. Only usage dated at or after it counts against the limit.
  - `*_settled` is the usage that reconciliation attributes to the church within `[counted_from, ends_at)` (ADR-0028 D5). Transcript usage is dated by the provider's own timestamp on the record. A notes admission's units are dated by its `issued_at`. `*_settled` is **recomputed** from the records on each run and never incremented, so a rerun gives the same figure. It is a sum of non-negative values, so it cannot go negative. It may fall if a provider revises a record down, and the provider's figure wins. **Incomplete provider records are excluded**: a stream that the request log shows as started and not yet finished has no final duration, and counting it would count the running stream twice, once as the open slices that cover it and once as the record, and would cut an honest Pro stream off at about 40 minutes. A completed record counts from the moment reconciliation sees it. The slices that held it stay open until their settle points, so it is counted twice for up to one slice plus lag. That is transient and conservative.
  - `high_water_rank` is set when the row is created, to the rank of the effective plan at that moment, so the first spend of a new week is not mistaken for an upgrade. D7 raises it. (Revision 5 also had `rank_at_last_reset`, which D7 always set to the same value, so it is removed.)
  - The two `carried_debt` columns (revision 3) hold the previous week's overrun, capped at this week's limit (ADR-0028 D7). The upgrade reset never touches them.
  - The time zone and both boundaries are **fixed when the row is created**. That is how "a time-zone change applies from the next reset" works without any extra state.
  - **There are no `*_reserved` counters.** Revision 1 had `stt_seconds_charged`, `notes_committed` and two `*_reserved` columns. Revision 2 removed the `COMMITTED` state but left those names behind. Revisions 4 and 5 replace the stale names and remove the reserved counters (next paragraph). Revision 4's `*_reset_baseline` columns are gone too: a baseline measured in settled usage could not tell usage dated before an upgrade from usage dated after it (see "Upgrade reset").
- `UsageReservation(org, week, meter, units, state = RESERVED | ISSUED | SETTLED | RELEASED, idempotency_key, request_hash, device_id, issued_at, last_minted_at, renews_id, retry_count, expires_at, created_at)`. Unique on (org, meter, idempotency_key).
  - `renews_id` is a nullable reference to the slice this row extends. It is set on a transcript slice renewal and null on an admission (see "Slice renewals").
  - `last_minted_at` is the time of the mint that made the row `ISSUED`, and null when nothing was minted for it. Whether a later reconnect moves it is not decided (ADR-0028 OI-13).

**Revision 2.** Under the owner's direct-to-provider directive, the server never calls the provider on a spend and never sees the outcome. The reservation states and settlement rules are therefore defined in **ADR-0028 D5**: `RESERVED → ISSUED → SETTLED`, with `RELEASED` allowed only from `RESERVED` (a failed mint, or a `RESERVED` row that aged out; see step 4 below). They replace revision 1's COMMITTED state. Compared with revision 1, the table gains these columns: `request_hash`, `issued_at` and `retry_count` (revision 2), and `last_minted_at` and `renews_id` (revision 5).

**One source of truth for held allowance: the open reservation rows.** The allowance a church is holding right now is `Σ units` over the current week's reservations in state `RESERVED` or `ISSUED`, and nowhere else. Two sources would have to agree. A stored `*_reserved` counter would need an adjustment on every transition (`RESERVED → RELEASED`, `ISSUED → SETTLED`, and each retry) from three writers (reserve, the sweeper and reconciliation), and a single missed adjustment drives it negative or leaks allowance. The sum cannot drift. It is cheap, for two reasons:

- It is served by a partial index on `(week_id) WHERE state IN ('RESERVED', 'ISSUED')`, so it reads only open rows of one week.
- The number of open rows is capped by the check itself, because every open row holds at least one note unit or one 300-second slice. At today's limits that is at most 16 transcript rows (Pro: 80 min × 60 = 4,800 s ÷ 300 s) and 10 notes rows (Pro) per org per week: 26 rows at most, whatever the history. A test seeds a week with that many open rows and pins the query count.

Protocol for a spend (both meters):

1. **Reserve.** This is one short `transaction.atomic()`:
   - Find the current `UsageWeek` row by `starts_at ≤ now < ends_at` (SEC-0027-07). Lock it with `select_for_update`. If no row covers `now`, create the next one with `get_or_create` and retry once on `IntegrityError`, which is the house idempotency pattern. **The next row's `starts_at` is `max(previous.ends_at, the week start computed in the org's current zone)`**, and its `ends_at` is the next local Monday 00:00 after that. A time-zone change in mid-week therefore never creates a row before the current row's `ends_at`, and rows never overlap. (Without this rule, a change from UTC−12 to UTC+14 would start the next week about 26 hours early and hand out a fresh allowance.) A test changes the zone mid-week and asserts that no new row appears before the current `ends_at`.
   - Apply D7's upgrade rule.
   - Check `carried_debt + settled + Σ units of open reservations + units ≤ limit`, using the `UsageWeek` row just locked and the indexed sum above. (`settled` already counts only usage dated from `counted_from`.)
   - A notes **retry** (ADR-0028 D5) reserves no new unit and creates no row. Under this same lock it checks that the reservation is `ISSUED`, that `retry_count` is 0 and that `issued_at` is within 10 minutes, and it **claims** the retry by moving `retry_count` from 0 to 1. The claim is what makes parallel retries yield exactly one. The retry's mint then runs outside the lock. **If that mint fails, a second short transaction rolls `retry_count` back to 0**, so a church never burns its only retry on a failed mint (the retry equivalent of `RESERVED → RELEASED`). If the process dies between the claim and the mint's outcome, the retry stays claimed. That fails closed and costs at most one retry.
   - Insert the reservation as `RESERVED`, then commit. The one exception is a transcript slice renewal on a socket that stays open, which is inserted directly as `ISSUED` (see "Slice renewals").

   Reads take **no** lock. A test fails if `remaining()` emits `FOR UPDATE`. Both `remaining()` and reserve have a query budget (`django_assert_num_queries`), and `effective_plan` counts inside it.
2. **Issue.** Close the database connection, then call the provider's mint endpoint with hard timeouts (ADR-0028 D6).
   - If the mint succeeds: a second short transaction moves the reservation to `ISSUED`.
   - If the mint fails: it moves to `RELEASED`. `RELEASED` is terminal: the row is never reused (ADR-0028 D5, replay table).
3. **Settle.** For transcripts, and for notes under option A, only reconciliation settles a reservation. It uses the provider's own usage records (ADR-0028 D5). Under option C (notes only) no credential leaves the server and no row is ever `ISSUED`. The notes task itself moves the row `RESERVED → SETTLED` when it delivers a note, and `RESERVED → RELEASED` when SelahCue or the provider fails (ADR-0028 D4 and D5).
4. **Crash safety.**
   - A `RESERVED` row older than its TTL is treated as "nothing was issued", and is released lazily by the next reserve and by the sweeper. That is **almost always true, but it is not guaranteed.** The mint and the move to `ISSUED` are two transactions with a provider call between them. A process that dies after a successful mint and before the second transaction leaves a live credential behind a `RESERVED` row. Releasing the row is still safe for the ledger, for three reasons:
     - The credential cannot still be used to start a session when the row is released. `RESERVED_TTL` must be longer than the mint timeouts **plus** the longest credential TTL (the timeout invariant below), and a stream can only start while the credential is valid.
     - The charge never depends on the reservation. Usage under the credential is attributed by its identity and charged by reconciliation (ADR-0028 D2 and D5). A released row can understate the church's *held estimate* for a while. It cannot understate the *charge*.
     - A crashed mint leaves at most one such credential. The released row is never reused, so a resend under the same idempotency key gets a refusal and the desktop must start a new admission under a new key (ADR-0028 D5, replay table). That new admission is a separate reservation, and at most one more credential. Both are charged by reconciliation.

     What this does not cover is a stream that was already open when the row was released. Until reconciliation records it, it holds no estimate. That is the same exposure as any held-open stream (ADR-0028 D3 and D7).
   - An `ISSUED` row is **never** released by time. It stays counted until reconciliation settles it.
   - **Correctness never depends on the job**, the same principle 17tnw2az0gh uses for grant expiry.
   - The sweeper is scheduled in `CELERY_BEAT_SCHEDULE`, and a test checks it is registered. It deletes in batches, following the `accounts/maintenance.py` pattern. What it may delete is fixed by the retention rule under Consequences: it never deletes an `ISSUED` row.
   - A second partial index, on `(org, expires_at) WHERE state = 'RESERVED'`, keeps the lazy release cheap while the lock is held. The sum of open reservations does **not** use it; it uses the `(week_id)` index above.

Why row locking and not optimistic concurrency. Both are correct. A conditional `UPDATE … WHERE` on a counter is lock-free, but the check here is over the settled usage and the open reservation rows (above), and the reserve step also has to create the week row, expire stale reservations and apply the upgrade reset. Doing that as one guarded write is more complex than one short lock. The lock is per org, so it serialises only one church's handful of devices, and it is held for milliseconds. It matches the shipped activation pattern.

The rule that makes this safe: **never hold the lock, or the transaction, across any provider call.** That covers the mint call and the reconciliation job's read of the usage API. Under the directive, the server no longer waits on a generation. Vera's worker and connection finding is resolved, with a bounded residual for the mint call; ADR-0028 D6 sets out the residual and its timeouts.

Timeout invariant. `RESERVED_TTL` must be longer than the mint call's connect timeout **plus** its read timeout **plus** the longest credential TTL the mint can return (30 s for a Deepgram grant token, ADR-0028 D3; the client-secret TTL for OpenAI, ADR-0028 D4). That way, by the time a `RESERVED` row can be released, any credential minted in the crash window has expired. Assert this at import, next to the constants it relates (the two mint timeouts, `RESERVED_TTL` and the credential TTLs), in the style of `DEGRADED_MANIFEST_TTL_SECONDS`. For option C notes rows (ADR-0028 D4), `RESERVED_TTL` must also exceed the notes task's hard timeout plus its bounded queue wait, because the task, and not a mint, is what the row waits for. An `ISSUED` reservation has no time-based release, so it needs no TTL invariant. The "one unit per late success" overrun rule from revision 1 no longer applies: late usage is charged by reconciliation, in the week it happened.

Upgrade reset (D7) sets `counted_from` to now and sets `*_settled` to 0 in the same transaction. Records dated before that instant stop counting, which is how "an upgrade grants the full new allowance at once" (owner D8) is met. The reset **never** touches the open reservations or the carried debt, and it never touches the provider records. An open reservation is allowance held right now for a credential already out, and releasing it on an upgrade would let a church spend the same allowance twice. Wiping the debt would turn an upgrade into a debt write-off.

**What an upgrade does to usage that is still in flight.** An open reservation made before the reset keeps counting until it settles, and when it settles its usage is dated before `counted_from`, so it then stops counting. Example: a Free church generates its one note at 10:00 (the row is `ISSUED`; it settles no earlier than about 11:10, 60 minutes plus lag). At 10:20 it upgrades to Core. Until the note settles, `remaining = 5 − 0 − 1 open = 4`. After it settles, `remaining = 5`. So the new allowance is full once what was in flight has settled, and in the meantime it is lower by the in-flight estimate. That is the conservative reading of "straight away" and it needs no second counter. The owner should know about this interval (it is item 8 of "Needed before Accepted"). The alternative, which gives the full allowance at the instant of the upgrade, is to drop the in-flight estimate from the sum at the reset. That would let a church spend the same allowance twice, so it is not proposed.

**Slice renewals (transcript only).** A transcript session is a chain of slices. A slice is one `UsageReservation` row of 300 s (the default slice), and a renewal names the slice it extends in `renews_id`. There are three cases:

| Case | Row | Provider call |
|---|---|---|
| Renewal on a socket that stays open | A new row, **inserted directly as `ISSUED`** in the reserve transaction, with `issued_at = now` and `last_minted_at` null. It never passes through `RESERVED`, so the `RESERVED_TTL` release cannot touch it and the hold on a live stream is not dropped | None |
| Renewal that needs a new socket (the held time has run out) | A new row with `renews_id` set: `RESERVED`, then `ISSUED` after the mint, exactly as an admission | Mint |
| Reconnect inside a live slice (the socket dropped with time left on it) | **Not decided: ADR-0028 OI-13.** For an honest client the intent is that it adds no row, but the server cannot see the socket, and this ADR has no rule for telling this case from a renewal, for gating it on the allowance, or for capping it per slice | Mint |

`ISSUED` therefore means "allowance granted to the desktop": a credential was returned, or, for a renewal on an open socket, the desktop was told it may keep its stream running for another slice. The settle point of each case is in ADR-0028 D5 (a row with no mint has no credential-TTL term). A renewal that would leave the church over its allowance is refused like any reserve, and the stream already open is not touched.

**The reconnect case is open, and the failure scenario is why.** Take a modified client with an exhausted allowance and one still-`ISSUED` slice. If it sends "reconnect" every 330 s or so, and each call returns a fresh 30 s token and moves the row's `last_minted_at`, then the row's settle point (`last_minted_at + 330 s + lag`) moves with it and the row never settles. It costs the client 15 calls an hour against the renewal budget, and it defeats the only control, which is enforcement at the next admission. Revision 5 said a reconnect "never holds a second 300 s" and that it moves `last_minted_at`. Both held only for an honest client, and revision 6 withdraws them until OI-13 is answered.

**Slices add.** A renewal puts another 300 s on top of the time still held. It does not restart a fresh 300 s. So the held time grows by 300 s with every renewal, and the sum of open reservations (the figure the allowance check uses) grows by the same amount.

**Renewal timing is client behaviour, and the budget does not depend on it.** The desktop is expected to ask for the next slice shortly before its held time runs out. This ADR assumes it asks 60 s before (`SLICE_RENEWAL_LEAD_SECONDS`, 60, a client setting that belongs on 86akby3xu). Because slices add, the lead moves only the **first** renewal earlier (to 240 s) and keeps the held time 60 s ahead of the stream. It does not change the steady rate, which is one renewal per 300 s.

Reserve throttles. Until revision 4 there was one budget, of 30 per hour per org and 10 per hour per device. That budget could not carry transcripts, because each slice renewal goes through the same endpoint. Reserve calls are therefore classes with separate budgets:

| Class | What it is | Budget |
|---|---|---|
| Admission | A new session on either meter: a fresh idempotency key that does not extend a live session | 30 per hour per org, 10 per hour per device |
| Slice renewal | Transcript only: the first two cases above. A reconnect (third case) counts here too if it is allowed at all (OI-13) | 30 per hour per org, 15 per hour per device |
| Notes retry | Claims `retry_count` and creates no row (ADR-0028 D5) | **Counts against the admission budget.** Every retry request, granted or refused with `RETRY_EXHAUSTED`, takes the `UsageWeek` lock and writes an audit event (OD-3), so it cannot be free |

**Counting rule, for every class.** A request counts against its budget once it has passed the throttle, whether it then succeeds, is refused for allowance, or fails on the mint. A request that the throttle itself refuses (HTTP 429 with a retry-after) is not counted again. Whether such throttled requests are themselves audited is an open question on 86akby3xu (its open item 7); this ADR does not decide it.

The arithmetic behind the renewal budget (slices add, so each renewal is 300 s of held time on top of what is held):

- **Steady rate.** One renewal per 300 s is 3,600 ÷ 300 = **12 renewals per hour**, whatever the lead. The per-device budget of 15 therefore leaves **3 spare** per hour. The old budget allowed 10 reserve calls an hour per device, and a continuous stream needs 12 renewals an hour (13 requests in the first hour with the admission), so it would have been refused every hour.
- **First hour.** With a 60 s lead, the admission is at 0 s and the renewals are at 240 s, 540 s, 840 s and so on, every 300 s (240 + 300n). Those at n = 0 to 11, up to 3,540 s, are **12 renewals**, plus the admission.
- **A 70-minute stream on Pro (4,200 s).** The renewal for slice k + 1 is asked at 300k − 60 s. Every such request before 4,200 s counts, so 300k − 60 < 4,200, which gives k = 1 to 14, and slices 2 to 15 are requested. That is **15 rows** (one admission and 14 renewals), not 14, because the last renewal fires 60 s before the stream ends. The held time at the end is 15 × 300 = **4,500 s**, which is under Pro's 4,800 s, so every request is admitted. Without any lead it would be 14 rows (4,200 s).
- **A stream that uses the whole Pro week (4,800 s).** Slices 1 to 16 hold 4,800 s. Slice 17 is asked at 300 × 16 − 60 = 4,740 s, and 17 × 300 = 5,100 s is over the allowance, so it is refused and recorded as `DENIED` (OD-3). The desktop stops at its held time of 4,800 s.
- **Per org.** Two devices streaming at once need 2 × 12 = 24 renewals an hour, so the per-org budget of 30 leaves 6 spare.
- Admissions keep their old figures. The review's finding was about renewals only, and a church starts a few sessions a day, not ten an hour.

Row ceiling per org, over the 35-day retention (Consequences): admissions 30 × 24 × 35 = 25,200, plus renewals 30 × 24 × 35 = 25,200, which is **50,400 rows**. Revision 3's 25,200 counted admissions only. This is a ceiling, not a forecast. A row that stays open holds allowance (at most 26 open rows per week, above), so only `RELEASED` rows (failed mints) and rows that settle quickly can pile up at the throttle rate. A church that uses its full Pro allowance creates 16 transcript slices and 10 notes rows a week. Tests pin the budgets, and one test asserts that a 70-minute stream on Pro (one admission and 14 renewals, 4,500 s held) is admitted without a throttle refusal. That test is the one that fails if renewals fall back under the admission budget.

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

If `rank(effective_plan) > high_water_rank`, set `high_water_rank` to the new rank, set `counted_from` to now, and set `*_settled` to 0. The usage that **counts** against the new limit therefore restarts from 0, because only usage dated at or after `counted_from` counts (D5). That is the whole effect. **Open reservations and `carried_debt` are untouched** (D5): an upgrade never releases a held reservation and never wipes debt. A reservation open at the upgrade keeps holding its estimate until it settles, and then its usage, dated before `counted_from`, stops counting (the worked example is in D5, "Upgrade reset"). A downgrade changes nothing, because `remaining = max(0, limit − carried_debt − settled − open reservations)` and `settled` is untouched. The week's **limit for overrun purposes** is the limit of the plan whose rank is `high_water_rank`, so a downgrade later in the week never turns usage that was admitted under the higher plan into an overrun (ADR-0028 D7).

A limit edit (Core 5 → 6) is **not** a plan change, so it never resets anything. The comparison is on rank, never on the limit value.

The high-water mark also closes the downgrade-then-upgrade loophole (open item 6 on 17tnw2az0gu). Pro → Free → Pro in one week does not reset twice, because Pro is already the week's high-water mark. Free → Core → Pro still resets at each step, as owner D8 intends. **This is a recommendation for the owner, not a decision.** Without it, the high-water check becomes "rank increased since the last spend" and the loophole stays open.

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
- Core and Pro "pending" device, output and NDI values (owner D7 sub-item (a)) must be **explicit `PlanGrant` rows**, not left to fall through to the dimension default. `screen_outputs` defaults to `unlimited`, so leaving it undeclared publishes "unlimited". That breaks 17tnw2az0gd's own acceptance criterion that a pending value never resolves to unlimited. Mark them pending in the row's `reason` text and cover them with a test that fails if any active plan resolves `screen_outputs` or `ndi_outputs` to `None`. Enforcement on the desktop is gated by DEC-014 until the owner answers.
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

**The ticket that delivers the authenticator is [17tnw2az0n5](https://app.clickup.com/t/17tnw2az0n5)** ("Real staff sign-in", read in ClickUp on 2026-10-02; status planning/todo). It already carries what this section requires:

- It blocks every SuperAdmin pricing and grant feature from production until it is done, naming 17tnw2az0gg (price and limit edits) and 17tnw2az0gh (plan grants). Those tickets may be built and merged first, but not enabled in production.
- Its acceptance criteria include a production-settings test that fails if header trust is on, and Sana's confirmation that it closes SEC-0027-01.
- **Its mechanism is not decided.** The identity provider or login method, whether MFA is required, how staff permissions are assigned and audited, and session lifetime and revocation are open decisions on that ticket. This ADR does not decide them.
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
| Process 1: title and body describe revision 1 only | PR title and body rewritten to cover both ADRs and the goal contract, with the list below. Updated again for revision 5. |
| Process 2: 18 unresolved threads; no re-review of revisions 2 and 3 | Not fixed here. Resolving threads and the independent re-review (goal contract C-008) belong to the reviewers. |
| a. The twin refusal at `license_keys/services.py:224` | D3: both refusals are removed, in the same release as the migration, never before it. |
| b. Throttle against 5-minute slice renewals | D5, "Reserve throttles": renewals have their own budget; the arithmetic and the new 50,400-row ceiling are shown; Consequences updated. |
| c. Retention versus `ISSUED` rows | Consequences: the sweeper deletes only `SETTLED` and `RELEASED` rows; `ISSUED` rows never age out by time and raise an alert instead. |
| d. Index for the open-estimates sum; two sources of truth; stale column names | D5: the open reservation rows are the single source; the `*_reserved` counters are gone; partial index on `(week_id)`; the columns are `*_settled`, with the upgrade reset as `counted_from` (revision 5; revision 4 had a baseline column). |
| e. D7 wording against D5 and ADR-0028 | D7 reworded: an upgrade moves `counted_from` and touches no open reservation and no debt. |
| f. SEC-0027-01 names no ticket | Revision 4 left the id out. Revision 5 records [17tnw2az0n5](https://app.clickup.com/t/17tnw2az0n5), confirmed in ClickUp. |
| j. "A `RESERVED` row older than its TTL has issued nothing" | D5 step 4: softened for the mint-to-`ISSUED` crash window, with the bound and a stronger timeout invariant. |
| k. PRD, ADR-0010, ADR-0019, desktop custody | Relates section, ADR-0028 D8, and "Needed before Accepted" below. |
| Cosmetic: header order; D7, D8 and D9 naming | Header reordered with a revision history. Revision 5 uses ClickUp's own labels (owner D7, D7 amendment, owner D8, owner D9, OD-1 to OD-3) with a crosswalk, replacing revision 4's `OD-7` to `OD-9` and `OD-R1` to `OD-R3`. |

(g, h and i are in ADR-0028.)

## Review dispositions (PR #111, independent re-review of head `255d042`, 2026-10-02)

| Item | Outcome |
|---|---|
| M1. Finding f not fixed; tickets exist | Fixed. 17tnw2az0n5 (staff authenticator), 17tnw2az0n2 (OpenAI spike) and 17tnw2az0gu (PRD amendment, DECISION-LOG entries) are recorded after reading each in ClickUp. "None recorded" remains only where a ClickUp search found no ticket. The retry exception is recorded as already written on 17tnw2az0g8 and 17tnw2az0gu. |
| M2. Labels conflict with ClickUp | Fixed. ClickUp's own labels with a crosswalk (header). ADR-0028 D1 and D5 now carry OD-3 (denied requests are recorded). |
| S1. Slice renewal rows, `renews_id`, reconnect | D5, "Slice renewals": a renewal on an open socket is inserted directly as `ISSUED`; `renews_id` and `last_minted_at` added. Revision 5 also said a reconnect re-mints the live slice and creates no row; revision 6 withdraws that (the reconnect case is open, ADR-0028 OI-13). |
| S2. Notes retry budget and failed mint | D5 reserve step and throttle table: retry requests count against the admission budget; the claim is rolled back if the retry's mint fails. |
| S3. Overrun's limit across a plan change | ADR-0028 D7: the week's limit for overrun purposes is the high-water plan's limit. The question of `limit` against `limit − carried_debt` is an open item for the owner (ADR-0028 OI-11). |
| S4. Upgrade reset against in-flight usage; negative counts | D5 "Upgrade reset" and D7: a timestamp (`counted_from`) replaces the baseline; the in-flight interval is stated, with an example; `*_settled` is recomputed and cannot go negative. |
| S5. `RELEASED` reuse; no `SETTLED` replay row; option C settlement | ADR-0028 D5: `RELEASED` is terminal and a resend needs a new key; the replay table has a `SETTLED` row; D5 step 3 here and ADR-0028 D4 and D5 say how `RESERVED` reaches `SETTLED` under option C. |
| S6. Renewal budget headroom | D5: a renewal lead and a counting rule were added in revision 5. **The arithmetic in revision 5 was wrong** (it said a 60 s lead makes renewals 240 s apart, which would be true only if a renewal restarted a fresh 300 s). Revision 6 corrects it: slices add, so the steady rate is 12 an hour and the lead moves only the first renewal. |
| Nits | Constants list in the timeout invariant; "fail-closed" wording (ADR-0028 D5); DEC-014 attribution and the premise-pinning tests and stale comments (D3); the two lists of re-checked claims aligned; ticket fallout listed (Needed before Accepted, item 7); SEC-0027-07's rule and test (D5 step 1). |

## Review dispositions (PR #111, third independent review of head `855b739`, 2026-10-02)

That review confirmed the earlier must-fix items, the retry budget, the overrun limit, the upgrade reset and the nits as fixed. It found three blocking defects in the design text added in revision 5, and the scope rule for this revision was to correct facts and record open items, not to invent mechanisms.

| Item | Outcome |
|---|---|
| B1. Renewal arithmetic contradicts itself | Fixed (D5, "Slice renewals"). Slices add. The steady rate is 12 renewals an hour, the budget of 15 leaves 3 spare, the lead moves only the first renewal, and a 70-minute Pro stream uses 15 rows and holds 4,500 s. All other mentions (ADR-0028 D5, tests, ceiling paragraph) agree. |
| B2. Replay table does not cover the notes retry | Fixed in ADR-0028 D5: retry rows, the retry flag excluded from the request hash, the retry path evaluated before the replay table, and a stated result for every row state. The error codes the ADR leaves unnamed are open (ADR-0028 OI-14). |
| B3. Reconnect has no server-checkable rule | Recorded as ADR-0028 OI-13 with the failure scenario. The "never holds a second 300 s" claim and the `last_minted_at` move are withdrawn until it is answered. No rule is designed. |
| N1. Incomplete records | Stated in D5, `*_settled`: excluded, with the transient conservative double count of completed records. |
| N2. Option C TTL clause | Added to the timeout invariant (D5). ADR-0028 says the retry rows apply to option A only. |
| N3. Initial `high_water_rank` | Stated (D5). `rank_at_last_reset` removed as redundant. |
| N4. Week limit snapshot | Recorded as ADR-0028 OI-16. |
| N5. Replay of a direct-`ISSUED` renewal | Recorded as ADR-0028 OI-15. |
| N6. Ticket fallout | 17tnw2az0gq and 17tnw2az0gn read in ClickUp and added to item 7 below. |
| N7. Goal contract and quote | Fixed: C-003 label, the re-check baseline wording (header), maximum iterations extended and noted in the ledger, and the ticket quote made exact. |

## Needed before Accepted

Nothing in this list is done by this PR, except where it says so. Ticket ids below were read in ClickUp on 2026-10-02.

1. **Independent re-review.** Sana for D4–D6 and the security dependency section; Vera for D5. This is goal contract criterion C-008. The 18 inline threads from revision 1 are to be resolved by the reviewers. Sana's earlier note that removing the assignment refusal is safe once the invariant test exists covered only that one refusal; she should confirm D3's removal of the issuance refusal too, and SEC-0027-07's week-start rule in D5 step 1.
2. **Staff authenticator (SEC-0027-01): ticket recorded, [17tnw2az0n5](https://app.clickup.com/t/17tnw2az0n5).** Its mechanism is an open decision on the ticket. It must be done before the staff writes are enabled in production, not before this ADR is `Accepted`.
3. **`DECISION-LOG.md` entries** by Priya (ticket [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu), whose Scope lists entries for owner D7 with its amendment, owner D8, owner D9, OD-1, OD-2 and OD-3; the architect does not edit that ticket). The retry exception is already written on the ticket, so only the log entry is outstanding. **Not covered by that Scope:** the DEC-014 amendment from D3 (the fallback moves to Free and both refusals go). No ticket is recorded for it. The owner's answer on D7's high-water mark is item 6 of that ticket's open list.
4. **Platform PRD amendments.** 17tnw2az0gu's Scope covers FR-546, AS-P6, FLOW-507 and the tier table. It does not name **FR-533, FR-547 or AS-P7**, so someone should confirm it covers them or add them.
5. **ADR-0010 clause and the `implementation/desktop/crates/selahcue-cloud/src/openai.rs` comment (lines 6 to 7).** A ClickUp search found no ticket for either. Ticket ids: **none recorded; owner to supply.** Both are open items in ADR-0028 (OI-8, OI-9).
6. **The open items in ADR-0028**, which also gate this ADR's settlement and enforcement tickets: the OpenAI spike ([17tnw2az0n2](https://app.clickup.com/t/17tnw2az0n2)), the Deepgram spike 86akby344, `NOTE_TOKEN_ENVELOPE`, the transcript held-open ceiling, the provisioning budget, the reconnect rule (OI-13), the unnamed refusal codes (OI-14), the replay of a direct-`ISSUED` renewal (OI-15), whether the week limit is snapshotted (OI-16), and the provider facts that have not been re-read since 2026-09-27.
7. **Ticket fallout, for Priya and Diego to place (this PR edits no ticket).** Each item below was read on the ticket on 2026-10-02:
   - 86akby4e9 (reconciliation), step 7, still computes the overrun as `max(0, settled_usage − limit)`. Under D5 and ADR-0028 D7 it counts only usage dated from `counted_from` and measures against the high-water plan's limit.
   - 17tnw2az0gj (ledger) still says an upgrade restarts "this week's settled-usage counter from 0", computes `remaining` from `settled_usage − Σ estimates of ISSUED reservations`, and says `RELEASED` happens only when a mint fails. It needs `counted_from`, the sum over `RESERVED` and `ISSUED` rows, the TTL release, the `last_minted_at` and `renews_id` columns, the retry claim and rollback, the `ISSUED` backlog alert and the week-start rule of D5 step 1.
   - 86akby3xu (STT session) still provisions "when an org first holds a plan with transcript minutes above 0", says `RELEASED` happens only when the grant call fails, and has no renewal budget, renewal lead time or renewal cases. It needs D3's demand-driven, gated provisioning and D5's "Slice renewals".
   - 17tnw2az0gq (transcript enforcement) computes admission from `Σ estimates of ISSUED slices` only (open `RESERVED` rows also hold allowance), and defines the overrun as usage "beyond that week's limit" without `counted_from` or the high-water plan's limit (ADR-0028 D7).
   - 17tnw2az0gn (notes enforcement) says "same key found `RELEASED`: may re-reserve" (it is now terminal and needs a new key), computes `remaining` from ISSUED estimates only, refers for option C to "in-task commit and release (ADR-0027 revision 1 D5)" (that text no longer exists; see D5 step 3 and ADR-0028 D4), and counts the retry under the lock with no rollback on a failed mint and no admission-budget counting. It lists the retry flag but not the replay-table retry rows (ADR-0028 D5).

8. **Owner confirmations** (the owner's, not the architect's):
   - D7's high-water mark (already open on 17tnw2az0gu, item 6).
   - The upgrade interval in D5: for the time it takes in-flight usage to settle after an upgrade, the new allowance is reduced by that in-flight estimate. Owner D8 says "straight away", and this reading is conservative.
   - ADR-0028 OI-11: whether an overrun is measured against `limit` or `limit − carried_debt`.

## Rollback

- Every schema change is additive except the removal of `LEGACY` and `PLATINUM`. That runs pre-launch and is reversible by a migration that re-creates them from the `0002` constants.
- Removing the two fallback refusals (D3) reverts with the code. It must be reverted together with the migration, never alone, because with `LEGACY` as the fallback the refusals are what keep the most permissive plan from being assigned or issued.
- The ledger can be switched off by making both enforcement points admit without reserving (a settings flag defaulting to on). This rolls back enforcement without losing data. The manifest `usage` object is additive, so removing it breaks no client.
