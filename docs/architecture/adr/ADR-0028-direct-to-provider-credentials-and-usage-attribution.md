# ADR-0028 — Direct-to-provider AI access: credential issue, server-side attribution and reconciliation

- Status: **Proposed**, revision 2. All three owner questions from revision 1 are now **decided** (see "Owner decisions, 2026-09-27" below). One thing is still **pending**: the result of the OpenAI Realtime spike, which decides whether notes are built on option A or on fallback C.
- Date: 2026-09-27. Revision 2, the same day, records the owner's answers.
- Confidence: **Medium for Deepgram** (the mechanism is documented; two numbers need the spike). **Low-Medium for OpenAI** until the spike reports (the chosen option rests on a capability nobody has tested for this use). The fallback, C, is well understood.

### Owner decisions, 2026-09-27 (settled; not open questions)

| # | Question in revision 1 | Owner's decision | Where it lands |
|---|---|---|---|
| 1 | Sermon notes: option A, B or C | **A (Realtime text-only with a client secret), spiked first.** If the spike fails, **C** (server-side, off the web worker, 202 + poll). **B is rejected**: a real OpenAI key never goes to a church laptop, spike or no spike. | D4 |
| 2 | Retry grace for failed notes generations | **Allowed: one retry per notes session** (per ISSUED admission), within 10 minutes, against the same reservation. This is a stated exception to owner decision D7's "failures are never charged" rule. | D5 |
| 3 | Overrun policy | **Carry into the following week only, capped at one week of debt.** Not written off. Anything beyond the cap is written off with an alert. | D7 |

**Still pending (not a decision):** the OpenAI spike (AI Engineer, Nova). It checks four things, listed under "What the providers actually support → OpenAI → Unknown". Its result picks A or C. It does not reopen B.
- Owner: Software Architect (Aria). Required reviewers before `Accepted`: Security Reviewer (Sana), Performance Engineer (Vera), AI Engineer (Nova) for D4.
- Relates: ADR-0027 (the weekly ledger; its D5 settlement rules and D6 are replaced by this ADR), DEC-004, 86ajy04hz (hosted AI service), 86akby3xu (STT mint), 86akby344 (attribution spike), 86akby4e9 (reconciliation), 17tnw2az0gn / 17tnw2az0gq (enforcement). ClickUp epic [17tnw2az0g6](https://app.clickup.com/t/17tnw2az0g6).
- Evidence labels: **Verified (docs)** = read in the provider's own documentation on 2026-09-27; **Verified (code)** = read on `origin/main` `f211581`; **Unknown** = not established, with the owner of the check named.

---

## Context

The product owner has directed that the Platform API is **never in the data path** of an AI provider call. For both cloud transcription (Deepgram) and sermon-note generation (OpenAI), the API's job is:

1. authenticate the device;
2. check the plan and the remaining weekly allowance;
3. hand back a credential scoped to the provider;
4. the desktop then connects **directly** to the provider.

For transcription this was already the plan (86akby3xu). For sermon notes it is new: ADR-0027 and 17tnw2az0gn assumed the API itself calls OpenAI and holds the request open while it does.

Two review findings on ADR-0027 (PR #111) shape this ADR:

- **Vera, High.** A notes request held a web worker and a database connection for the whole OpenAI call.
- **Sana, SEC-0027-02, High.** The transcript design could not tell which church a Deepgram stream belonged to. Temporary tokens are recorded under the one server key that minted them, and the only per-request label is a `tag` the client sets itself. A modified client could leave it off (free transcription) or set another church's tag (charge that church). One token can also open several streams while it is valid.

The pivot does not fix Sana's finding by itself. Copying the current STT design to OpenAI would copy the flaw. This ADR decides how attribution works when the server never sees the call.

## What the providers actually support

### Deepgram

- **Verified (docs).** Temporary tokens from `POST /v1/auth/grant` last 30 s by default and up to 3600 s. They "have the same accessor as the API key used to generate them". Minting needs a key with Member scope or higher. (Token-based auth guide.)
- **Verified (docs).** A token only has to be valid when the WebSocket opens. The connection "will then stay open ... until you close it". Deepgram staff confirm that expiring or deleting the key does not end an open stream (discussion deepgram/673).
- **Verified (docs).** The request log, `GET /v1/projects/{project_id}/requests`, can filter by `accessor`. Each record carries `request_id`, `created`, `api_key_id`, and `response.details` with `duration` and `tags`. The usage breakdown can also filter or group by `accessor`.
- **Verified (docs).** API keys created with an expiry ("temporary API keys") are limited to **250 created per day**. Unique request tags are limited to **500 per day** (Creating API Keys; discussion deepgram/1409).
- **Verified (docs).** Concurrency limits apply per **project**. All keys in a project share one pool of 45 to 300+ concurrent streams, depending on plan and model (API rate limits).
- **Unknown (spike 86akby344).** Whether Deepgram limits the number of durable (non-expiring) keys per project. How long a finished stream takes to appear in the request log. Whether a stream that is still open appears there at all.

### OpenAI

- **Verified (docs).** OpenAI's only short-lived client credential is the Realtime **client secret**: `POST /v1/realtime/client_secrets`, with a TTL of 10 to 7200 s (default 600). It "grants access to the Realtime API". Nothing in the reference says it works with `/v1/responses` or `/v1/chat/completions`, and both of those authenticate only with a normal API key.
- **Verified (docs).** A Realtime session can be text-only (`output_modalities: ["text"]`). The session settings set at mint time "can also be overridden by the client connection". A session ends at 60 minutes at most. As with Deepgram, the credential's expiry limits when a session can **start**, not how long it runs.
- **Verified (docs).** The Admin API can create projects, create and delete project service accounts (creating one returns an unredacted API key), delete project API keys, and set per-project, per-model rate limits (requests per minute and per day, tokens per minute).
- **Verified (docs).** The Usage API (`/v1/organization/usage/completions`) groups by `project_id` and `api_key_id` in buckets of 1 minute, 1 hour or 1 day. It needs an **Admin key**.
- **Verified (code).** Today's desktop notes path (`selahcue-cloud/src/openai.rs`) calls `POST /v1/responses` with a JSON schema for structured output. Its module doc says a client-held OpenAI key is "not acceptable in a shipped product": it cannot be rotated centrally, metered per account, or revoked for one church.
- **Unknown (spike in progress, Nova; owner-approved 2026-09-27).** Whether Realtime client-secret usage appears in the Usage API under the parent project or key. Whether one client secret can open more than one session. Whether a text-only Realtime session can produce the structured note draft (schema-constrained JSON) at acceptable quality and cost. Whether the client can override the **model** of the session, not just its instructions. How many projects an OpenAI organisation may hold.

**The plain answer to the crux question:** OpenAI has **no** short-lived credential for an ordinary Responses or Chat Completions call. For the call shape SelahCue uses today, "hand the client a token" means "hand the client a real, reusable API key". That is a different and much larger risk, and the owner has ruled it out (D4).

## Decisions

### D1 — The boundary: the API issues credentials and never relays

- `POST /v1/stt/session` (86akby3xu) and a new `POST /v1/notes/session` authenticate the device, reserve allowance (ADR-0027 D5), and return a provider credential plus connection details.
- `POST /v1/notes:generate` from 86ajy04hz's contract is **withdrawn** under the directive. It comes back, in the async 202 form of D4 option C, **only if the Realtime spike fails**. In that case the next bullet's "never receives transcripts" does not hold for notes: the transcript passes through a worker transiently (D4, option C). It still does not hold note bodies at rest.
- The API never receives audio, transcripts or note bodies. Under the directive, it stores no sermon content, so the note-body replay cache from ADR-0027 (and SEC-0027-04's cache rules and Vera's byte-cap comment) **no longer exists**. The data still goes to the provider on SelahCue's account, so the DPA and disclosure work (86akby942) still applies.

### D2 — Attribution comes only from the identity of the credential the server chose

The rule for both providers: **usage is attributed to a church by the provider-side identity of the credential SelahCue issued, never by anything the client sets or reports.**

- **Server-controlled (usable for charging):** the Deepgram accessor (the key id behind a grant token); the OpenAI `project_id`, and `api_key_id` if the spike shows it is populated.
- **Client-controlled (never used for charging):** the Deepgram `tag` query parameter; OpenAI `user`, `metadata` and `safety_identifier`; any count, duration or success flag the desktop reports (`usage-events:batch`, 86ak10amq). These may be shown as provisional figures only.
- A new table `ProviderCredential(org, provider, provider_credential_id, provider_scope_id, secret_ciphertext, state = PROVISIONING | ACTIVE | REVOKED, created_at, revoked_at)` maps each provider identity to exactly one org. It is unique on `(provider, provider_credential_id)`. Rows are **never deleted**, so usage that arrives after revocation still maps to the right org.
- **Fail closed.** A provider usage record whose identity maps to no org is stored as `UNATTRIBUTED`. It raises an alert and is never charged to any church. It is never dropped either. This covers our shared minting key, keys created outside this table, and provisioning crashes. If unattributed usage passes a configured threshold, minting for that provider switches off (the SEC-0027-08 kill-switch rules apply).
- **Crash-safe provisioning.** Write the `ProviderCredential` row as `PROVISIONING` **before** calling the provider's create-key endpoint, and put the row id in the key's comment or name. Reconciliation can then map a key whose create call succeeded but whose response was lost.

### D3 — Deepgram: one durable key per church; grant tokens minted from it

- **Credential.** Each org gets one Deepgram API key with Member scope (the lowest scope that can mint grant tokens) and **no expiry**. It is created by a worker task, stored encrypted, and never leaves the server. `POST /v1/stt/session` decrypts it and mints a grant token from it, with `ttl_seconds` = 30 (enough to open a socket). The desktop receives only the grant token.
- **Why not per-session keys.** Keys with an expiry are capped at 250 created per day (Verified, docs). Per-session keys would stop working at 250 sessions a day across all churches.
- **Why not tags.** The client sets them, and they are capped at 500 unique values per day (Verified, docs). That is Sana's finding.
- **Attribution.** Grant tokens carry the parent key's accessor (Verified, docs). So every stream opened with a church's token is logged under that church's key, whatever the client does with `tag`. A client cannot move usage onto another church, because it only ever holds tokens derived from its own church's key.
- **Reconciliation input.** `GET /v1/projects/{id}/requests` filtered by accessor, or unfiltered and mapped through `ProviderCredential`. It is idempotent per `request_id` (unique constraint). The charge is `response.details.duration`, dated at `created`.
- **Honest bound (replaces "one stream").** Attribution across churches is **exact**. Enforcement is not. After one admission, a modified client can open any number of streams during the token's 30 s life and keep each one open indefinitely. Deleting the church's key stops new tokens but does not close open streams (Verified, discussion 673). The overrun per admission is therefore *(streams opened within the token TTL) × (how long each is held open)*. It is capped only by the project concurrency pool. It is **detected** at the next reconciliation and **enforced** at the next admission. The bound is financial and after the fact. A hard cap needs a stream proxy, which the directive rules out.
- **New risk: shared concurrency pool.** Every church's streams draw on one project-wide concurrency pool. One abusive church holding many streams open can use up the pool and block transcription for **every** church, not just itself. Mitigations: an anomaly alert when a church's concurrent requests in the log exceed its device count; revoking that church's key; and, if Deepgram supports it (Unknown), one Deepgram project per church, which isolates the pool. The spike should check whether projects can be created through the API.
- **Custody.** Creating keys needs `keys:write`. That credential lives only in the worker tier, never in the web tier. The web tier holds only the ability to decrypt per-org keys. Reading usage uses a separate key with only `usage:read`, also worker-only. This separates minting from reporting, as Sana asked.
- **Provisioning.** Provision the key when an org first holds a plan with transcript minutes above 0. If an admission finds no ACTIVE key, it enqueues provisioning and returns a coded `PROVIDER_PROVISIONING` with a retry-after. It never falls back to the shared key.

### D4 — OpenAI (sermon notes): option A, spiked first; C is the fallback; B is rejected

**Decided by the owner, 2026-09-27.**

- **Chosen: option A**, subject to the spike. The spike is running now (AI Engineer, Nova). No notes build ticket starts until it reports.
- **Fallback: option C**, if the spike fails any of its pass criteria below. The owner has approved C as the notes exception to the directive in that case, so a failed spike needs no new owner decision; it needs only a recorded spike result.
- **Rejected: option B.** It is not a fallback and not a later option. The analysis stays below as the record of why.

**Spike pass criteria (all four must hold for A).** Each is one of the OpenAI Unknowns above.
1. Usage from a Realtime client secret appears in the Usage API under the church's `project_id` (D2 attribution).
2. One client secret can open **at most one** session, **or**, if it can open more, the per-project rate limit bounds the extra usage and it is still attributed to the right church. The spike must say which.
3. A text-only Realtime session produces the structured note draft at acceptable quality and cost (Nova's evaluation, against today's `/v1/responses` output).
4. Whether a client can override the session **model**. If it can, A passes only if per-project rate limits still bound the spend. This finding also feeds the D7 overrun figures.

Criterion 1 or 3 failing sends notes to C. Criteria 2 and 4 set the abuse bound Sana reviews; they send notes to C only if the bound cannot be capped by per-project limits.

Option A (and C, if it comes to that) uses a **per-org OpenAI project**, created through the Admin API. That gives D2 its server-controlled attribution (`project_id`) and lets per-project rate limits bound the damage. Each project holds one service account, and its key is the **parent** credential. It never leaves the server.

**Option A — Realtime API, text-only, with a client secret (chosen; meets the directive; build only after the spike passes).**
- The API mints a Realtime client secret from the church's project key, with the shortest workable TTL (for example 60 s). The desktop opens a text-only Realtime session, sends the transcript, and reads the draft.
- For: the church gets a genuinely short-lived credential, and the long-lived key stays on the server.
- Against:
  - The model is limited to the realtime family, not the model Nova chose.
  - Structured output may be weaker or missing.
  - The client can override session instructions, and the model too if the spike finds that possible. A modified client could therefore get a general-purpose session of up to 60 minutes per admission. That usage is still attributed to the right church, and it is bounded by the session cap and the per-project token rate limit.
  - Realtime text pricing is higher.
- Blocked on the spike (pass criteria above). **Do not build until it reports.**

**Option B — Give the desktop the church's real project key (REJECTED by the owner, 2026-09-27; kept as the record of why).**
- The API returns the church's service-account key. The desktop calls `/v1/responses` exactly as it does today.
- For: no change to the prompt, schema or model. Attribution is exact by `project_id`. The key can be deleted server-to-server at any time, and per-project rate limits cap spend per day.
- Against:
  - This is a long-lived, reusable secret on church laptops. Anyone who extracts it can use it until SelahCue notices and revokes it.
  - It works for **any** endpoint and model the project allows. Service-account keys cannot be scoped to one endpoint in OpenAI's permission model, and a per-project model allow-list is not confirmed in the API (Unknown).
  - Nothing revokes it automatically when a session ends.
  - The allowance becomes advisory between reconciliations. A church can spend until the project's daily rate limit, and the ledger only catches up afterwards.
  - This is exactly the posture `openai.rs` calls unacceptable for shipping.
- A per-session service account deleted after use narrows the exposure window. But deletion then depends on a job, and if that job fails the key stays open. That is fail-open.

**Option C — Keep the call server-side, but off the web worker (the owner-approved fallback if the spike fails; an exception to the directive for notes only).**
- `POST /v1/notes:generate` reserves allowance, enqueues a Celery task, and returns 202. The desktop polls for the result.
- For: this also resolves Vera's finding. The key never leaves the server. Attribution is trivial, because the server reads the `usage` in the provider's response. Owner decision D7's rule that "provider failures are never charged" stays fully enforceable, because the server sees the outcome.
- Against: the backend is in the data path for notes. The transcript passes through SelahCue briefly. Transcription (Deepgram) stays direct either way.
- If C is used: the task holds no web worker; it has its own hard timeout and a bounded queue; the result is held only until the desktop fetches it or a short TTL passes, with a byte cap and a test that bites (Vera's replay-cache comment applies again); and the D5 settlement for notes is the in-task commit and release from ADR-0027 revision 1, not reconciliation.

**Outcome, in one line.** Spike passes → build A. Spike fails → build C. There is no path to B.

### D5 — Settlement: charges come from reconciliation, for both meters

The server never sees whether a provider call succeeded, so ADR-0027 D5's in-request commit and release is replaced by the following.

**Reservation states:** `RESERVED` → `ISSUED` → `SETTLED`, with `RELEASED` allowed **only** from `RESERVED`.

- `RESERVED`: the allowance is held and no credential has left the server yet.
- `ISSUED`: a credential has been returned to the desktop. From here, the reservation can **never** be released by time. When `expires_at` passes, it stays counted until reconciliation settles it. This is SEC-0027-02's expiry-refund fix, applied to both meters.
- `RELEASED`: the mint failed before any credential was issued (for example, the provider's grant call errored). The server knows nothing left the building, so the church is not charged.
- `SETTLED`: reconciliation's watermark has passed `issued_at + credential TTL + max session + measured lag`. The reservation's estimate then stops counting, because the provider's actual figures have replaced it.

**What is charged:**
- The weekly charge is **the sum of provider-reported usage for the org's credentials**, dated by the provider's own timestamp in the org's week boundaries (ADR-0027 D8, found by `starts_at ≤ t < ends_at` per SEC-0027-07).
- Late records are charged to the week they happened in.
- Formula: `remaining = max(0, limit − carried_debt − settled_usage − Σ estimates of ISSUED reservations)`. `carried_debt` is the previous week's capped overrun (D7) and is 0 in most weeks.
- **Transcript:** charged in seconds of `duration`.
- **Notes:** each ISSUED admission with any usage in its window costs 1 unit. Usage beyond `used_admissions × NOTE_TOKEN_ENVELOPE` is charged as extra units, `ceil(excess / envelope)`, and recorded as an audited overrun. An admission whose window shows **no** usage for that org is refunded (settled at 0). That is the only provider-side failure the server can see.
- Because charges come from provider totals, N parallel calls cost N. The "N provider calls charged as one" attack from SEC-0027-03 is closed by construction, not by request-handling logic.

**Idempotency and replay (SEC-0027-03).** The key is `(org, meter, idempotency_key)`, with `org` taken only from the authenticated device (SEC-0027-04). The reservation stores `device_id` and a hash of the request.
- Same key, different request hash: refused.
- Same key, found `RESERVED` or `ISSUED`: returns a coded `ALREADY_ISSUED`. **No second credential is issued**, and the desktop must start a new request.
- Same key, found `RELEASED`: it may re-reserve.
- Parallel requests with one key: serialised by the unique constraint and the `UsageWeek` lock, so exactly one credential is issued.
- Commit and release happen only on the server. The desktop has no call for either.

**Owner decision D7's rule that "provider failures are never charged" cannot be fully kept under the directive.** (That D7 is the owner's product decision recorded on [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu), not ADR-0027's section D7.) OpenAI bills tokens for a generation that failed partway, or one the desktop rejected as malformed. The server cannot tell either case from success.

**Decided by the owner, 2026-09-27: one retry per notes session.** This amends owner decision D7 with one stated exception.
- A "notes session" is one ISSUED notes admission (one reservation, one paid unit).
- Within **10 minutes** of that admission being ISSUED, the desktop may request **one** retry credential against the **same** reservation, with the same idempotency key plus a retry flag. No new unit is reserved.
- The retry is counted under the `UsageWeek` lock (`retry_count` goes 0 → 1). A second retry request, or one after 10 minutes, is refused with a coded `RETRY_EXHAUSTED`; the desktop must start a new, paid admission.
- The reservation's token envelope doubles (`2 × NOTE_TOKEN_ENVELOPE`), so the retry's usage is not charged as overrun.
- Abuse bound, stated honestly: at most one extra generation per paid unit.
- The retry is charged nothing whether the first attempt failed or not. The server cannot tell, so the grace is unconditional within its limits. That is the exception to D7: a failed generation and its retry together cost one unit, and if the retry also fails, the church is still charged that one unit.
- **If the spike fails and notes use option C,** the server sees each outcome, so D7 is kept exactly and the retry grace is unnecessary. It may stay as a client convenience; it is not needed for fairness.
- **Recording:** the D7 text lives on 17tnw2az0gu. Priya or Diego must add this exception there and in `DECISION-LOG.md`. The architect does not edit that ticket.

**Reconciliation job (one per provider, in Celery beat, worker tier only).**
1. Read provider usage **server-to-server** with the read-only credential over HTTPS. Never accept a provider callback or usage relayed by the client.
2. Upsert into `ProviderUsageRecord`:
   - Deepgram: one row per `request_id`, unique.
   - OpenAI: one row per `(bucket_start, project_id, api_key_id, model)`, unique. Each run **replaces** the values, because a bucket fills in as late data arrives.
3. Map each record through `ProviderCredential`, or mark it `UNATTRIBUTED` (D2).
4. In one short transaction per org, lock `UsageWeek` (org, then licence key, then `UsageWeek`, as Vera asked), recompute `settled_usage` from the records, and advance settled reservations. **Never hold that lock across a provider HTTP call.**
5. Re-scan a trailing window of the length the spike measured, so every run is safe to repeat.
6. **If the provider's usage API fails, change nothing.** ISSUED reservations stay counted, so a church sees less remaining, never more. Raise an alert after a configured number of consecutive failures. There is **no automatic release**. The cost is that a long provider-reporting outage lowers what churches appear to have left. That is the fail-closed choice, and it is deliberate.
7. Retention: `ProviderUsageRecord` rows are kept for 104 weeks. They are deleted in batches by a scheduled sweeper. A test fails if the bound is removed.

**Transcript fairness (Vera, High 2).** Reserve STT in fixed slices (default 5 minutes) per admission, not `min(remaining, session_cap)`. A still-streaming desktop asks for the next slice through the same endpoint, and gets a fresh grant token only if it reconnects. So one device cannot lock up a church's whole balance. The slice is an admission estimate only. The charge is always Deepgram's `duration`.

### D6 — Performance: Vera's worker finding is resolved; a bounded residual stays

- **Resolved.** Under the directive, the API never waits on a generation or a stream. A notes request no longer holds a worker or a database connection for the tens of seconds of an LLM call. Manifest reads (NFR-507) no longer queue behind note generation.
- **Residual.** The mint itself still makes one outbound call on the request worker: Deepgram `auth/grant`, or the OpenAI client-secret create under D4 option A. (Under fallback C, the notes request makes no outbound call on the web worker at all; the Celery task does.) Rules:
  - hard connect and read timeouts, 2 s each, asserted at import;
  - close the database connection before the outbound call (`connection.close()`) so the worker does not hold a connection during it;
  - a circuit breaker per provider, which returns a coded `PROVIDER_UNAVAILABLE`;
  - its own throttle budget per device, not per IP (Vera's `/v1/quota` point applies here too).
- **Worst-case capacity.** With W sync workers, at most W mints are in flight. Each holds a worker for at most 4 s (connect plus read timeout) and no database connection. Mint number W+1 queues at the app server. The fix is the timeout, not a queue.
- **Reconciliation** runs in the worker tier and never touches the web workers.

### D7 — What stays unsolved, stated plainly

- **No hard cap for either provider** under the directive. Enforcement is at admission, and reconciliation catches up afterwards.
- **Deepgram:** a modified client's overrun can run for as long as it holds streams open, and it can drain the shared concurrency pool (D3).
- **OpenAI option A:** a modified client may override session instructions (and the model, if the spike finds that possible) for up to 60 minutes per admission. Attributed correctly, bounded by the session cap and the per-project rate limit, charged by reconciliation.

**Overrun policy — decided by the owner, 2026-09-27: carry into the following week only, capped at one week of debt.**
- An **overrun** is settled usage in a week beyond that week's limit: `overrun = max(0, settled_usage − limit)`, per meter, computed when reconciliation settles the week (after `ends_at` plus the settle watermark).
- **Carry.** The overrun is deducted from the **immediately following** week's allowance only: that week's `remaining = limit − carried_debt − settled_usage − Σ open estimates`.
- **Cap.** `carried_debt = min(overrun, that following week's limit)`. At most one full week of allowance can be lost.
- **No further roll.** Debt never passes on to a third week. Any debt the following week cannot absorb, and any overrun above the cap, is **written off**: recorded, audited (`usage.overrun_written_off`, `SERVICE` actor) and alerted. It is never charged later.
- **Plan changes.** The cap uses the following week's limit for the plan in effect when that week's row is created. An upgrade reset in the following week (ADR-0027 D7) resets settled usage, **not** carried debt. Otherwise an upgrade would wipe debt. A downgrade to Free with a limit of 0 means the carried debt is 0 and the whole overrun is written off.
- **Every overrun alerts,** carried or not (`usage.overrun_recorded`, per ADR-0027's audit rule).
- Late records that settle a week after its carry has been applied adjust the carry only while the following week is still current. Once that week has ended, the extra is written off, never charged backwards.
- Figures Priya can quote: Core notes are 5 a week, so a Core church that overruns by 7 units loses at most 5 next week and 2 are written off. Transcript minutes on Pro are 80 a week, so an overrun of 30 minutes leaves 50 the next week.

## Options considered for attribution

- **Per-org durable key, tokens minted from it (chosen for Deepgram).** Attribution is server-controlled, with no daily creation cap. Custody is on us.
- **Per-session keys with an expiry.** Attribution per session. Rejected: capped at 250 a day (Deepgram); no TTL and job-dependent deletion (OpenAI).
- **Client-set tags or metadata.** Rejected: forgeable, and capped at 500 a day (SEC-0027-02).
- **Server-side stream proxy.** Gives a hard cap. Rejected by the owner's directive.

## Consequences

- `UsageWeek` gains `stt_seconds_carried_debt` and `notes_carried_debt` (D7), written once when the previous week settles, and tested for the cap, the no-further-roll rule and the upgrade-reset rule.
- Notes build tickets are gated on the spike result, not on an owner decision. Transcript tickets are not gated on it.
- New `apps/providers` app: `ProviderCredential`, `ProviderUsageRecord`, two reconciliation tasks, a provisioning task, and an encrypted-secret field. Its key custody follows `ENTITLEMENT_SIGNING_KEY`'s fail-loud pattern.
- The web tier and the worker tier need different secrets. The ops runbook must list them (DEPLOYMENT.md).
- Allowances become eventually consistent. Displayed remaining figures lag real use by up to the reconciliation interval plus the provider's reporting lag.
- Tests must include an explicit cross-tenant test at the reconciliation layer: a record under church A's credential can never change church B's `UsageWeek`, and an unmapped record charges nobody.

## Rollback

Docs only today. Once built: minting can be switched off per provider (the desktop falls back to on-device transcription; notes show "unavailable"), and settlement tables are additive. Revoking every `ProviderCredential` stops new sessions but not open ones (D3).
