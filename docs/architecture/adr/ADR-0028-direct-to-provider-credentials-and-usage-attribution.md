# ADR-0028 — Direct-to-provider AI access: credential issue, server-side attribution and reconciliation

- Status: **Proposed**, revision 5 (2026-10-02). The owner's questions from revision 1 are **decided** (see "Owner decisions, 2026-09-27" below). One thing is still **pending**: the result of the OpenAI Realtime spike, which decides whether notes are built on option A or on fallback C. Not yet `Accepted`: the conditions are under "Open items before Accepted".
- Date: 2026-09-27 (revisions 1 and 2); revisions 3, 4 and 5 dated 2026-10-02.
- Confidence: **Medium for Deepgram** (the mechanism is documented; two numbers need the spike). **Low-Medium for OpenAI** until the spike reports (the chosen option rests on a capability nobody has tested for this use). The fallback, C, is well understood.
- Owner: Software Architect (Aria). Required reviewers before `Accepted`: Security Reviewer (Sana) for D2, D3, D5 and D8; Performance Engineer (Vera) for D5 and D6; AI Engineer (Nova) for D4.
- Relates:
  - ADR-0027 (the weekly ledger; its D5 settlement rules and D6 are replaced by this ADR), DEC-004, 86ajy04hz (hosted AI service), 86akby3xu (STT mint), 86akby344 (attribution spike), 86akby4e9 (reconciliation), 17tnw2az0gn / 17tnw2az0gq (enforcement). ClickUp epic [17tnw2az0g6](https://app.clickup.com/t/17tnw2az0g6).
  - **ADR-0010** (AI / provider abstraction, Accepted) and **ADR-0019** (transcript-provider seam): D8 says how platform-issued credentials fit their consent and key rules. ADR-0010 needs one clause (OI-8). ADR-0019 needs no change.
  - **Platform PRD** FR-533, FR-546, FR-547, AS-P6, AS-P7 and FLOW-507: D2 and D5 demote device-reported metering to a provisional figure, and ADR-0027 replaces the monthly billing-anniversary period with a weekly one. The PRD still says the old thing (OI-7). Ticket [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu) lists FR-546, AS-P6, FLOW-507 and the tier table in its Scope, and does not name FR-533, FR-547 or AS-P7.
  - **SelahCue PRD** FR-082, FR-132 to FR-134 and FR-177 (logging, consent, key storage, DPA): D8.
- Decision labels. These are **ClickUp's labels on [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu), used as written**, so a reader can search for them there. Because the owner's decisions D7, D8 and D9 share numbers with this ADR's own sections, the owner's are always written "owner D7", "owner D8" and "owner D9" in this ADR. The crosswalk:

  | Label | What it is | ClickUp | Where it lands |
  |---|---|---|---|
  | owner D7 | Plan lineup and weekly allowances, including the rule that failures are never charged | [17tnw2az0g8](https://app.clickup.com/t/17tnw2az0g8) | ADR-0027 Context |
  | owner D7 amendment | One retry per notes session, the exception to "failures are never charged" (2026-09-27) | On 17tnw2az0g8 and 17tnw2az0gu | D5 |
  | owner D8 | Weekly window; mid-week plan changes apply at once; no clawback on a downgrade | [17tnw2az0ga](https://app.clickup.com/t/17tnw2az0ga) | ADR-0027 D7, D8 |
  | owner D9 | Staff plan grants | [17tnw2az0gb](https://app.clickup.com/t/17tnw2az0gb) | ADR-0027 D1 |
  | OD-1 | How notes reach the provider: option A first, C if the spike fails, B rejected | On 17tnw2az0gu | D4 |
  | OD-2 | Overrun carry-over: following week only, capped at one week of debt | On 17tnw2az0gu | D7 |
  | OD-3 | Every denied credential request is recorded | On 17tnw2az0gu | D1, D5 |

  - `D<n>` is a decision in this ADR, and `ADR-0027 D<n>` is a decision in the companion.
  - `DEC-###` numbers for the owner's decisions are assigned when 17tnw2az0gu writes them into `DECISION-LOG.md`. This ADR does not guess them.
  - `OI-n` is an open item in the list under "Open items before Accepted".
- Evidence labels: **Verified (docs)** = read in the provider's own documentation on 2026-09-27. **Revisions 3, 4 and 5 did not re-read the provider documentation, so every such line is unverified since that date until OI-6 is done.** **Verified (code)** = read on `origin/main` `f211581`; revision 3 re-checked the `openai.rs` lines it cites on `feaee70`. **Unknown** = not established, with the owner of the check named.

---

## Revision history

- **Revision 5 (2026-10-02)** answers the third independent review, of head `855b739`. It corrects text and records open items, and adds no new mechanism:
  - D5: the replay table is followed by a retry table. The retry flag is excluded from the request hash, retries are evaluated before the replay table, and every row state has a stated result. The retry rows apply to option A only.
  - D5: incomplete provider records are excluded from the settled figure, and a reconnect no longer moves the settle point (OI-13).
  - D5 and D7: the slice arithmetic follows ADR-0027 revision 6 (slices add; 12 renewals an hour; a 70-minute stream is 15 rows).
  - Open items OI-13 to OI-16 are new (reconnect rule, unnamed refusal codes, replay of a direct-`ISSUED` renewal, week-limit snapshot). OI-12 now lists 17tnw2az0gq and 17tnw2az0gn.
- **Revision 4 (2026-10-02)** answers the independent re-review of head `255d042`:
  - OD-3 is carried: D1 and D5 say every denied credential request is recorded.
  - The owner's decision labels are ClickUp's own, with a crosswalk (revision 3's `OD-7` to `OD-9` and `OD-R1` to `OD-R3` are gone), and the owner decisions table has the OD-3 row.
  - D5: `RELEASED` is terminal and a resend needs a new key; the replay table has `SETTLED` and "recorded as" columns; settlement under option C is stated (D4 and D5); slice renewals, reconnects and the settle point of a row with no mint are defined; the notes retry has a claim and a rollback; formulas use ADR-0027's `counted_from`; the "fail-closed" wording for held-open streams is corrected.
  - D7: the week's limit for overrun purposes is the high-water plan's limit; whether to measure against `limit − carried_debt` is an open item (OI-11).
  - Open items: ticket ids confirmed in ClickUp are recorded; OI-11 and OI-12 are new.
- **Revision 3 (2026-10-02)** answers the review of revision 2 (PR #111, reviewed at `38755430`):
  - D5: the `max session` in the settle point is defined per meter, and for Deepgram transcripts it is the granted slice plus a guard for held-open streams; `NOTE_TOKEN_ENVELOPE` has no value and is an open item; the replay rules are a table; the crash window is covered; the formula uses the single source of truth of ADR-0027 D5; renewal slices have their own throttle.
  - D3: provisioning is demand-driven, rate-bounded and gated on the spike results, not triggered by a plan.
  - D8 is new: desktop consent, custody, and what this changes elsewhere.
  - "Open items before Accepted" is new.
  - The owner's decisions moved out of the metadata block and have their own labels.
- **Revision 2 (2026-09-27)** recorded the owner's three answers.
- **Revision 1 (2026-09-27)** was the first version.

## Owner decisions, 2026-09-27 (settled; not open questions)

| Label | Question | Owner's decision | Where it lands |
|---|---|---|---|
| OD-1 | Sermon notes: option A, B or C (revision 1 question) | **A (Realtime text-only with a client secret), spiked first.** If the spike fails, **C** (server-side, off the web worker, 202 + poll). **B is rejected**: a real OpenAI key never goes to a church laptop, spike or no spike. | D4 |
| owner D7 amendment | Retry grace for failed notes generations (revision 1 question) | **Allowed: one retry per notes session** (per ISSUED admission), within 10 minutes, against the same reservation. This is a stated exception to owner D7's "failures are never charged" rule. | D5 |
| OD-2 | Overrun policy (revision 1 question) | **Carry into the following week only, capped at one week of debt.** Not written off. Anything beyond the cap is written off with an alert. | D7 |
| OD-3 | Should denied credential requests be recorded? (not a revision 1 question; added in revision 4 after the owner confirmed it on 2026-09-27) | **Every denied credential request is recorded**, not only successful reservations, so a church and staff can see how often it hit its limit. Recorded through `record_audit_event` with `result=AuditResult.DENIED`. Whether anything can *read* that history is open (17tnw2az0gu, open item 8). | D1, D5 |

**Still pending (not a decision):** the OpenAI spike ([17tnw2az0n2](https://app.clickup.com/t/17tnw2az0n2), AI Engineer, Nova). It checks four things, listed under "What the providers actually support → OpenAI → Unknown". Its result picks A or C. It does not reopen B.

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
- **Verified (code, re-checked on `feaee70`).** Today's desktop notes path (`selahcue-cloud/src/openai.rs`) calls `POST /v1/responses` with a JSON schema for structured output. Its module doc (lines 6 to 11) says the shipping path keeps note generation proxied through the SelahCue platform API, because a desktop-held OpenAI key cannot be rotated centrally, metered per account, or revoked for one church, and adds: "None of that is acceptable in a shipped product". That comment is the one D1 reverses for notes under option A (OI-9).
- **Unknown (spike in progress, Nova; owner-approved 2026-09-27).** Whether Realtime client-secret usage appears in the Usage API under the parent project or key. Whether one client secret can open more than one session. Whether a text-only Realtime session can produce the structured note draft (schema-constrained JSON) at acceptable quality and cost. Whether the client can override the **model** of the session, not just its instructions. How many projects an OpenAI organisation may hold.

**The plain answer to the crux question:** OpenAI has **no** short-lived credential for an ordinary Responses or Chat Completions call. For the call shape SelahCue uses today, "hand the client a token" means "hand the client a real, reusable API key". That is a different and much larger risk, and the owner has ruled it out (D4).

## Decisions

### D1 — The boundary: the API issues credentials and never relays

- `POST /v1/stt/session` (86akby3xu) and a new `POST /v1/notes/session` authenticate the device, reserve allowance (ADR-0027 D5), and return a provider credential plus connection details.
- `POST /v1/notes:generate` from 86ajy04hz's contract is **withdrawn** under the directive. It comes back, in the async 202 form of D4 option C, **only if the Realtime spike fails**. In that case the next bullet's "never receives transcripts" does not hold for notes: the transcript passes through a worker transiently (D4, option C). It still does not hold note bodies at rest.
- **Every denied credential request is recorded (OD-3).** Each request from an authenticated device writes exactly one audit event through `record_audit_event`, on a DEVICE actor with the org as target and `request_id = idempotency_key`: `result=AuditResult.SUCCESS` for a grant and `result=AuditResult.DENIED` for a refusal. The `reason` is the coded refusal: `QUOTA_EXHAUSTED` (including a week reduced by carried debt), a licence that does not permit it, `PROVIDER_UNAVAILABLE`, `PROVIDER_PROVISIONING`, `ALREADY_ISSUED` or a request-hash mismatch, or `RETRY_EXHAUSTED` (D5). `after` carries the meter, the week, and remaining and limit at decision time, and never a key, token or secret. Limits of this rule: a request with no valid device token cannot be tied to a church and is not covered (86akby3xu, open item 8, for Sana); whether requests that the throttle itself refuses are audited is open (86akby3xu, open item 7); and whether anyone can *read* the history is open (17tnw2az0gu, item 8). This ADR records, it does not expose. The volume of denied events is bounded by the budgets in ADR-0027 D5, which is one reason a refused notes retry counts against the admission budget.
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
- **Provisioning is demand-driven, rate-bounded and gated. It is not triggered by a plan.** Revision 2 provisioned a key when an org first held a plan with transcript minutes above 0. Free has 20 minutes, so every signup would have created a durable Deepgram key (and, for OpenAI, a per-org project) whether the church ever used the feature, while the provider's limits on durable keys and projects are Unknown. Revision 3 changes that:
  - **Trigger.** An admission that has already passed the allowance check, for an org with no ACTIVE key, enqueues provisioning and returns a coded `PROVIDER_PROVISIONING` with a retry-after. Signup, plan assignment and a staff grant never provision. The number of keys therefore follows the churches that actually transcribe, not the number of signups. (Repeated signups to collect free allowances remain the signup and anti-abuse work's problem, as Sana noted; this only stops them costing a provider key each.)
  - **One per church.** At most one non-`REVOKED` `ProviderCredential` per `(org, provider)`, by a partial unique index, so concurrent first admissions provision once.
  - **Rate bound.** A global per-provider provisioning budget per day, checked in the worker tier before the create call (a setting, `PROVIDER_PROVISIONS_PER_DAY`). Over budget, admissions get the same coded `PROVIDER_PROVISIONING` with a longer retry-after, and an alert fires. **The value is not set** (OI-5). It has to sit below the provider's own limits, and those are Unknown: Deepgram's limit on durable keys per project (spike 86akby344) and OpenAI's limit on projects per organisation (Nova's spike).
  - **Gate.** The provisioning task ships behind a settings flag that stays off in production until the spikes have reported those limits and the budget is set (OI-5). Until then nothing is provisioned automatically.
  - If an admission finds no ACTIVE key it never falls back to the shared key.

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
- For: this also resolves Vera's finding. The key never leaves the server. Attribution is trivial, because the server reads the `usage` in the provider's response. Owner D7's rule that "provider failures are never charged" stays fully enforceable, because the server sees the outcome.
- Against: the backend is in the data path for notes. The transcript passes through SelahCue briefly. Transcription (Deepgram) stays direct either way.
- If C is used: the task holds no web worker; it has its own hard timeout and a bounded queue; the result is held only until the desktop fetches it or a short TTL passes, with a byte cap and a test that bites (Vera's replay-cache comment applies again); and the settlement is done by the task, not by reconciliation. **How a row reaches `SETTLED` under C:** no credential leaves the server, so no row is ever `ISSUED`. The task moves its row `RESERVED → SETTLED` (one unit) when it delivers a note, and `RESERVED → RELEASED` (nothing charged) when SelahCue or the provider fails, each in its own short transaction with no lock held across the provider call. When the task starts it re-checks that its row is still `RESERVED` and does nothing if it is not. `RESERVED_TTL` for these rows must exceed the task's hard timeout plus the bounded queue wait (ADR-0027 D5, timeout invariant), so a task that crashes has its row released by TTL and the church is not charged for a SelahCue failure.

**Outcome, in one line.** Spike passes → build A. Spike fails → build C. There is no path to B.

### D5 — Settlement: charges come from reconciliation, for both meters

The server never sees whether a provider call succeeded, so ADR-0027 D5's in-request commit and release is replaced by the following.

**Reservation states:** `RESERVED` → `ISSUED` → `SETTLED`, with `RELEASED` allowed **only** from `RESERVED`. `RELEASED` and `SETTLED` are terminal: a row never leaves them. (Under option C a notes row goes `RESERVED → SETTLED` directly; see D4.)

- `RESERVED`: the allowance is held and the mint is in flight or not yet confirmed.
- `ISSUED`: the allowance has been granted to the desktop. Normally that means a credential was returned. For a transcript slice renewal on a socket that stays open, nothing is minted and the desktop is told it may keep its stream running for another slice, so the row is inserted directly as `ISSUED` (ADR-0027 D5, "Slice renewals"). From here, the reservation can **never** be released by time. When `expires_at` passes, it stays counted until reconciliation settles it. This is SEC-0027-02's expiry-refund fix, applied to both meters.
- `RELEASED` (terminal): either the mint failed before any credential was issued (for example, the provider's grant call errored), or a `RESERVED` row passed its TTL and was released lazily. In the first case the server knows nothing left the building. In the second it presumes so, and the presumption can be wrong in one case: a crash between a successful mint and the move to `ISSUED`. ADR-0027 D5 step 4 gives the three reasons the ledger stays correct anyway. The main one is that charges come from provider records and never from reservation state. A `RELEASED` row is never reused, even under the same idempotency key (replay table below).
- `SETTLED` (terminal): reconciliation's watermark has passed the reservation's **settle point** (next block). The reservation's estimate then stops counting, because the provider's actual figures have replaced it. Under option C the notes task settles its own row when it delivers a note (D4).

**Settle point.** It is `issued_at + credential TTL + max session + measured lag`, where `credential TTL` is counted only for a row that had a mint (it is the time from the latest mint, `last_minted_at`, and zero for a row that was inserted as `ISSUED` with no mint). Revision 2 left `max session` undefined, and for Deepgram it has no finite value. It is now defined per meter:

- **Notes: 60 minutes.** This is OpenAI's documented Realtime session limit (D4; Verified (docs) on 2026-09-27, not re-read since). If a retry credential was issued (`retry_count = 1`), the settle point is `issued_at + 10 min (the retry window) + credential TTL + 60 min + lag`. Under option C there is no held-open session, and the task's own hard timeout takes its place.
- **Transcript: the granted slice, plus a guard for held-open streams.** A Deepgram stream "will then stay open ... until you close it" (D3), so no clock gives a maximum for a stream that a modified client holds open. For an honest client the granted time **is** the bound, because it must renew a slice to extend a stream. So a transcript slice's `max session` is its own length (default 300 s), and its settle point is `last_minted_at + 30 s + 300 s + lag` for a row that had a mint, and `issued_at + 300 s + lag` for a renewal row inserted with no mint. Whether a reconnect inside a live slice moves `last_minted_at`, and so the settle point, is not decided (OI-13). A reconnect that moved it on every call would let a modified client keep a row from ever settling. A slice settles at that point **only if the church has no incomplete request record**, meaning no stream that the request log shows as started and not yet finished. While a stream is running, all of the church's open slices stay `ISSUED` and counted. Together they approximate the stream's length, so the balance stays conservative while it runs. **An incomplete record is not charged**: it is excluded from the settled figure until it completes (ADR-0027 D5), because counting it would count the running stream twice, once as these open slices and once as the record. When the stream's record completes, its recorded duration is charged to the week it happened in (D7's carry rules apply), and the slices settle. For up to one slice plus lag the completed record and the slices that held it are both counted. That is transient and conservative.
- **What is not known (OI-2, OI-4).** Whether the request log shows a stream that is still open, and with what duration, is Unknown (spike 86akby344). If it does not show one, a held-open stream looks like "no usage" until it ends, its slices settle at 0 on the clock, and the stream is charged late, when its record appears. Whether to add a ceiling (a maximum held-open time, after which the pinned estimate is replaced by the ceiling and the church's key is flagged) is an open item. **No figure is proposed here**, because it depends on the spike result and on the longest service the owner wants to support. Until it is closed, the rule above is the defined behaviour. It is **fail-closed only while the request log shows the stream as incomplete.** If open streams are invisible in the log (OI-2), the guard cannot see the stream, its slices settle at 0 on the clock, and the church's balance is **fail-open** for that stream until its record appears: in the meantime it can be admitted again. That window is the cost of the unknown, and it is why OI-2 matters.

**What is charged:**
- The weekly charge is **the sum of provider-reported usage for the org's credentials**, dated by the provider's own timestamp in the org's week boundaries (ADR-0027 D8, found by `starts_at ≤ t < ends_at` per SEC-0027-07).
- Late records are charged to the week they happened in.
- Formula: `remaining = max(0, limit − carried_debt − settled_usage − Σ units of open reservations)`. `carried_debt` is the previous week's capped overrun (D7) and is 0 in most weeks. `settled_usage` counts only usage dated at or after the week's `counted_from`, the instant of the last upgrade reset (ADR-0027 D5 and D7), so a reset needs no second figure. "Open reservations" are the week's `RESERVED` and `ISSUED` rows. They are the **single source of truth** for held allowance: `UsageWeek` has no separate reserved counter (ADR-0027 D5).
- **Transcript:** charged in seconds of `duration`.
- **Notes:** each ISSUED admission with any usage in its window costs 1 unit, dated by the admission's `issued_at`. The window runs from `issued_at` to the settle point. Usage beyond `used_admissions × NOTE_TOKEN_ENVELOPE` is charged as extra units, `ceil(excess / envelope)`, and recorded as an audited overrun. An admission whose window shows **no** usage for that org is refunded (settled at 0). That is the only provider-side failure the server can see.
  - **`NOTE_TOKEN_ENVELOPE` has no value yet.** It is the number of tokens one admission may use before the excess is charged as a further unit. Its source is Nova's spike: pass criterion 3 (D4) measures real token use per generated draft on representative sermon transcripts, and the figure depends on the model the spike settles on and that model's text-token pricing. It is therefore a per-model setting, held server-side, re-measured whenever the model changes, and never sent to the client. Nova proposes it and the owner approves it, because it decides how much an admission can use before it costs more (OI-3).
  - **Until it is set, the "extra units" branch of the notes charge cannot be built or switched on.** The rest of the notes charge does not depend on it: 1 unit for an admission with usage, and a refund when the window shows none. The retry's doubled envelope (below) depends on it too.
- Because charges come from provider totals, N parallel calls cost N. The "N provider calls charged as one" attack from SEC-0027-03 is closed by construction, not by request-handling logic.

**Idempotency and replay (SEC-0027-03).** The key is `(org, meter, idempotency_key)`, with `org` taken only from the authenticated device (SEC-0027-04). The reservation stores `device_id` and a hash of the request. **A request that carries the retry flag is not a replay.** It is evaluated by the retry table further below, before this one, and this table applies only to requests without the flag.

| Replay case | Result | Audit event (OD-3) |
|---|---|---|
| Same key, different request hash | Refused. | `DENIED` |
| Same key, different device | Refused. A replay must match the device that made the reservation (ADR-0027, tenant scoping). | `DENIED` |
| Same key, found `RESERVED` or `ISSUED` | Coded `ALREADY_ISSUED`. **No second credential is issued**, and the desktop must start a new request. | `DENIED` |
| Same key, found `SETTLED` | Coded `ALREADY_ISSUED`: that admission is complete, and the desktop must start a new request under a new key. A `SETTLED` row is kept for up to 35 days (ADR-0027, retention). After it is deleted the same key would look new, so a key must be unique per request (a fresh identifier each time). | `DENIED` |
| Same key, found `RELEASED` | **Refused with a coded error (its name is chosen at build, beside `ALREADY_ISSUED`).** `RELEASED` is terminal and the row is not reused, because the state machine only moves forward. The desktop retries under a **new** idempotency key. If the row was released by TTL in the crash window (ADR-0027 D5 step 4), the new admission is a separate reservation and can mean one more credential. Both are charged by reconciliation. | `DENIED` |
| Parallel requests, one key | Serialised by the unique constraint and the `UsageWeek` lock, so exactly one request is processed. The others find its row and get the result for that state, as above. | `DENIED` for each refusal |

Two gaps in this table are open items and are not designed here. The codes for the refusals it names only as "refused" (hash mismatch, device mismatch, a `RELEASED` row) are unnamed (OI-14). And a client that resends a transcript renewal after losing the response finds a row that was inserted directly as `ISSUED` with no credential, so it gets `ALREADY_ISSUED` and must start a new request, which adds a second 300 s hold while the first row also stays open (OI-15).

Commit and release happen only on the server. The desktop has no call for either.

**Owner D7's rule that "provider failures are never charged" cannot be fully kept under the directive.** (Owner D7 is the product owner's decision on [17tnw2az0g8](https://app.clickup.com/t/17tnw2az0g8), also recorded on [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu).) OpenAI bills tokens for a generation that failed partway, or one the desktop rejected as malformed. The server cannot tell either case from success.

**Decided by the owner, 2026-09-27 (owner D7 amendment): one retry per notes session.** This amends owner D7 with one stated exception.
- A "notes session" is one ISSUED notes admission (one reservation, one paid unit).
- Within **10 minutes** of that admission being ISSUED, the desktop may request **one** retry credential against the **same** reservation, with the same idempotency key plus a retry flag, which is not part of the request hash. No new unit is reserved.
- The retry is claimed under the `UsageWeek` lock (`retry_count` goes 0 → 1), and the retry's mint runs outside the lock. **If that mint fails, `retry_count` is rolled back to 0** in a second short transaction, so a failed mint does not burn the church's only retry (ADR-0027 D5, reserve step). A second retry request, or one after 10 minutes, is refused with a coded `RETRY_EXHAUSTED`; the desktop must start a new, paid admission. Every retry request, granted or refused, counts against the admission budget (ADR-0027 D5, throttle table) and writes its audit event (OD-3, D1): a refused retry is recorded as `DENIED` with `RETRY_EXHAUSTED`.
- The reservation's token envelope doubles (`2 × NOTE_TOKEN_ENVELOPE`), so the retry's usage is not charged as overrun.
- Abuse bound, stated honestly: at most one extra generation per paid unit.
- The retry is charged nothing whether the first attempt failed or not. The server cannot tell, so the grace is unconditional within its limits. That is the exception to owner D7: a failed generation and its retry together cost one unit, and if the retry also fails, the church is still charged that one unit.
- **If the spike fails and notes use option C,** the server sees each outcome, so owner D7 is kept exactly and the retry grace is unnecessary. It may stay as a client convenience; it is not needed for fairness.
- **Recording:** the exception is **already written** on 17tnw2az0g8 and 17tnw2az0gu ("Amendment (owner, 2026-09-27)"). Only the `DECISION-LOG.md` entry is outstanding, and 17tnw2az0gu's Scope covers it (OI-10). The architect does not edit that ticket.

**Retry requests (option A only).** The retry flag is excluded from the request hash, so a retry carries the same hash as the original request. The device must match the one that made the reservation. The row found under `(org, meter, idempotency_key)` decides the result, and every row of this table is a retry, never a replay:

| Row found | Result | Audit event (OD-3) |
|---|---|---|
| No row for this org | `NOT_FOUND`, as for any reservation lookup (ADR-0027, tenant scoping) | `DENIED` |
| `ISSUED`, `retry_count` 0, within 10 minutes of `issued_at` | Granted. The retry is claimed, a credential is minted, and no new unit is reserved. If the mint fails, the claim is rolled back and the refusal is `PROVIDER_UNAVAILABLE` | `SUCCESS`, or `DENIED` if the mint fails |
| `ISSUED`, `retry_count` already 1 (claimed or used), or more than 10 minutes since `issued_at` | `RETRY_EXHAUSTED` | `DENIED` |
| `SETTLED` | `RETRY_EXHAUSTED`. A notes row settles no earlier than `issued_at` plus the credential TTL plus 60 minutes, which is after its 10-minute retry window | `DENIED` |
| `RESERVED` (the first mint has not finished) | `ALREADY_ISSUED`. Nothing is issued yet, and no second credential is issued | `DENIED` |
| `RELEASED` | The same refusal as a plain replay on a `RELEASED` row (unnamed, OI-14). Nothing was issued, so there is nothing to retry | `DENIED` |
| Different device | Refused, as in the replay table (OI-14) | `DENIED` |

Parallel retries are serialised by the `UsageWeek` lock: exactly one claims, and the others get `RETRY_EXHAUSTED`. Under option C no row is ever `ISSUED`, so none of these rows can apply: a failed task releases its row without charge and the desktop starts a new admission. If the retry flag stays as a client convenience under C (17tnw2az0gn, open item 3), it has nothing to claim.

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

A request for the next slice is a **slice renewal**. Its rows, columns and cases (renewal on an open socket, renewal that needs a new socket, and a reconnect inside a live slice, which is open: OI-13) are in ADR-0027 D5, "Slice renewals". It has its own throttle budget (ADR-0027 D5, "Reserve throttles": 15 per hour per device and 30 per hour per org), separate from the admission budget of 30 per hour per org and 10 per hour per device. Slices add, so a continuous stream needs 12 renewals an hour whatever the renewal lead, and a 70-minute sermon on Pro uses 15 rows (one admission and 14 renewals, 4,500 s held), so the admission budget alone would refuse it. The arithmetic is in ADR-0027 D5. A renewal on an open socket mints nothing and makes no provider call, so D6's capacity analysis of the mint covers admissions, renewals that need a new socket, and reconnects only.

### D6 — Performance: Vera's worker finding is resolved; a bounded residual stays

- **Resolved.** Under the directive, the API never waits on a generation or a stream. A notes request no longer holds a worker or a database connection for the tens of seconds of an LLM call. Manifest reads (NFR-507) no longer queue behind note generation.
- **Residual.** The mint itself still makes one outbound call on the request worker: Deepgram `auth/grant`, or the OpenAI client-secret create under D4 option A. (Under fallback C, the notes request makes no outbound call on the web worker at all; the Celery task does.) Rules:
  - hard connect and read timeouts, 2 s each, asserted at import. `RESERVED_TTL` must also exceed these timeouts plus the credential TTL (ADR-0027 D5, timeout invariant), so a crash between mint and `ISSUED` cannot leave a usable credential behind a released row;
  - close the database connection before the outbound call (`connection.close()`) so the worker does not hold a connection during it;
  - a circuit breaker per provider, which returns a coded `PROVIDER_UNAVAILABLE`;
  - its own throttle budget per device, not per IP (Vera's `/v1/quota` point applies here too).
- **Worst-case capacity.** With W sync workers, at most W mints are in flight. Each holds a worker for at most 4 s (connect plus read timeout) and no database connection. Mint number W+1 queues at the app server. The fix is the timeout, not a queue.
- **Reconciliation** runs in the worker tier and never touches the web workers.

### D7 — What stays unsolved, stated plainly

- **No hard cap for either provider** under the directive. Enforcement is at admission, and reconciliation catches up afterwards.
- **Deepgram:** a modified client's overrun can run for as long as it holds streams open, and it can drain the shared concurrency pool (D3).
- **OpenAI option A:** a modified client may override session instructions (and the model, if the spike finds that possible) for up to 60 minutes per admission. Attributed correctly, bounded by the session cap and the per-project rate limit, charged by reconciliation.

**Overrun policy — decided by the owner, 2026-09-27 (OD-2): carry into the following week only, capped at one week of debt.**
- An **overrun** is settled usage in a week beyond that week's limit: `overrun = max(0, settled_usage − week_limit)`, per meter, computed when reconciliation settles the week (after `ends_at` plus the settle watermark). `settled_usage` counts only usage dated from the week's `counted_from` (ADR-0027 D5), so usage before an upgrade reset is not an overrun.
  - **`week_limit` is the limit of the plan whose rank is the week's `high_water_rank`**, read at settlement. It is not the limit of the plan the church is on at the end of the week. Measured against the end-of-week plan, a downgrade would turn admitted usage into an overrun. Example: a Pro church uses 8 notes (limit 10), then its grant ends and it falls to Free (limit 1). Against the end-of-week plan the overrun is 7 and the carried debt is `min(7, next limit)`, which is a clawback, and owner D8 says "usage already recorded stands, with no clawback". Against the high-water plan the overrun is 0. Whether that limit is read at settlement or snapshotted when the week row is created is not decided (OI-16). Read at settlement, a limit edit in mid-week (Core 5 to 3) would turn admitted usage of 5 into an overrun of 2.
  - **Measured against `limit`, not `limit − carried_debt`.** This follows the owner's wording (OD-2: "settled usage above a week's limit"). The consequence is that admission lets a church use only `limit − carried_debt`, but usage that nobody admitted, between that figure and `limit`, records no overrun. A church could burn its carried debt allowance again without a new overrun. Whether the owner means that, or means `limit − carried_debt`, is an open question for the owner (OI-11). The ADR follows the owner's wording until it is answered.
- **Carry.** The overrun is deducted from the **immediately following** week's allowance only: that week's `remaining = limit − carried_debt − settled_usage − Σ units of open reservations` (the formula in D5).
- **Cap.** `carried_debt = min(overrun, that following week's limit)`. At most one full week of allowance can be lost.
- **No further roll.** Debt never passes on to a third week. Any debt the following week cannot absorb, and any overrun above the cap, is **written off**: recorded, audited (`usage.overrun_written_off`, `SERVICE` actor) and alerted. It is never charged later.
- **Plan changes.** The cap uses the following week's limit for the plan in effect when that week's row is created. An upgrade reset in the following week (ADR-0027 D7) moves `counted_from`, **not** carried debt. Otherwise an upgrade would wipe debt. A downgrade to Free with a limit of 0 means the carried debt is 0 and the whole overrun is written off.
- **Every overrun alerts,** carried or not (`usage.overrun_recorded`, per ADR-0027's audit rule).
- Late records that settle a week after its carry has been applied adjust the carry only while the following week is still current. Once that week has ended, the extra is written off, never charged backwards.
- Figures Priya can quote: Core notes are 5 a week, so a Core church that overruns by 7 units loses at most 5 next week and 2 are written off. Transcript minutes on Pro are 80 a week, so an overrun of 30 minutes leaves 50 the next week.

### D8 — The desktop's side: consent, custody and what this changes elsewhere

New in revision 3 (review finding k). The desktop is the other half of the boundary D1 draws, and two sets of existing rules govern it.

**Consent comes first.** ADR-0010 and the SelahCue PRD keep cloud providers off by default and consent-gated per provider (FR-132, FR-177), with a live "cloud active" indicator while data is sent (FR-133) and a graceful local fallback (FR-135). None of that moves. The desktop asks for a credential (`POST /v1/stt/session`, `POST /v1/notes/session`) only after the church has opted in to that provider. It shows the indicator while a stream or notes session is open. When a request is refused or the provider is down, it falls back to on-device transcription or shows notes as unavailable, and live output is never affected (FR-547, FR-135).

**Custody: issued credentials are held in memory only.** The Deepgram grant token and the OpenAI client secret exist in the desktop process for as long as it takes to open the connection (30 s for the grant token; the client-secret TTL for OpenAI), and are then dropped.

- They are **never written to disk**: not to SQLite, the config, the crash-recovery snapshot or the OS secret store. The secret store is for user-supplied keys (FR-134, ADR-0010), and the platform has none: it is hosted-only, with no BYOK (Platform PRD NG-P5).
- They are **never logged and never in a diagnostic bundle** (FR-082). A test captures the logs of a full session and asserts that neither credential's value appears in them.
- A credential is used once. The desktop does not keep a spent or expired one for reuse.
- The church's long-lived provider credentials (the Deepgram key, the OpenAI project key) never leave the server (D3, D4), so there is nothing durable on a church laptop to extract.

**What this changes elsewhere.** This PR is docs-only and edits none of these. Each is an open item (OI-7 to OI-9). OI-7 is on 17tnw2az0gu for FR-546, AS-P6, FLOW-507 and the tier table. The rest of OI-7, OI-8 and OI-9 have no ticket id recorded:

- **Platform PRD.** FR-533, FR-546, FR-547, AS-P6, AS-P7 and FLOW-507 still say the STT period is per calendar month and resets on the billing anniversary, that usage is recorded per device through `usage-events:batch` (FR-546), and that the cloud service enforces the org's balance (FR-533). They also carry the old tier table (Free 30 min, Pro 5 h, Platinum 10 h). ADR-0027 and this ADR replace these with a weekly period that resets on Monday 00:00 in the org's time zone, usage taken from the provider's own records (device-reported figures are provisional only, D2), the platform API admitting and reconciling, and Free / Core / Pro with weekly transcript minutes and note generations. FR-547 (exhaustion degrades, never blocks) and FLOW-507's shape are unchanged.
- **ADR-0010.** Its Context (item 3), the cloud-adapters paragraph of its Decision and its Invariants paragraph say keys are user-supplied and live only in the OS secret store. That stays true for the user-supplied keys ADR-0010 describes. It needs one clause for platform-issued credentials, which are short-lived, server-issued and held in memory only (this section).
- **ADR-0019.** No change. The Deepgram adapter implements `STTProvider`, and getting its token through `POST /v1/stt/session` is the adapter's business behind the seam. ADR-0019 already lists cloud STT adapters and consent gating as ADR-0010 seams, unchanged.
- **`implementation/desktop/crates/selahcue-cloud/src/openai.rs`, lines 6 to 7.** The module doc says the shipping path keeps note generation proxied through the platform API. D1 reverses that for notes under option A, and keeps it (in the async 202 form) under option C. The comment is not edited here: it is code, and its right wording depends on the spike result.

## Options considered for attribution

- **Per-org durable key, tokens minted from it (chosen for Deepgram).** Attribution is server-controlled, with no daily creation cap. Custody is on us.
- **Per-session keys with an expiry.** Attribution per session. Rejected: capped at 250 a day (Deepgram); no TTL and job-dependent deletion (OpenAI).
- **Client-set tags or metadata.** Rejected: forgeable, and capped at 500 a day (SEC-0027-02).
- **Server-side stream proxy.** Gives a hard cap. Rejected by the owner's directive.

## Consequences

- `UsageWeek` gains `stt_seconds_carried_debt` and `notes_carried_debt` (D7), written once when the previous week settles, and tested for the cap, the no-further-roll rule and the upgrade-reset rule.
- Notes build tickets are gated on the spike result, not on an owner decision. Transcript tickets are not gated on the OpenAI spike, but they are gated on the Deepgram spike 86akby344 (D3 provisioning, D5 settle point).
- Provider provisioning ships off in production until the provider limits are known and the provisioning budget is set (D3, OI-5).
- The "extra units" branch of the notes charge cannot be built until `NOTE_TOKEN_ENVELOPE` has a value (D5, OI-3).
- New `apps/providers` app: `ProviderCredential`, `ProviderUsageRecord`, two reconciliation tasks, a provisioning task, and an encrypted-secret field. Its key custody follows `ENTITLEMENT_SIGNING_KEY`'s fail-loud pattern.
- The web tier and the worker tier need different secrets. The ops runbook must list them (DEPLOYMENT.md).
- Allowances become eventually consistent. Displayed remaining figures lag real use by up to the reconciliation interval plus the provider's reporting lag.
- Tests must include an explicit cross-tenant test at the reconciliation layer: a record under church A's credential can never change church B's `UsageWeek`, and an unmapped record charges nobody.

## Open items before Accepted

Nothing here is done by this PR. "Ticket" is the ClickUp ticket that carries the item. Each ticket id below was read in ClickUp on 2026-10-02. **Where the ticket column says "None recorded", a ClickUp search that day found no ticket for the item. The owner supplies an id if one exists or is created, and this ADR does not invent one.**

| ID | Item | Who checks or decides | Ticket |
|---|---|---|---|
| OI-1 | The four OpenAI Realtime spike criteria (D4). The result picks A or C. | Nova | [17tnw2az0n2](https://app.clickup.com/t/17tnw2az0n2) |
| OI-2 | Deepgram unknowns: limit on durable keys per project, request-log lag, whether a stream that is still open appears in the log, and whether projects can be created through the API (D3, D5) | Spike owner | [86akby344](https://app.clickup.com/t/86akby344) |
| OI-3 | Value and source of `NOTE_TOKEN_ENVELOPE` (D5). Gates the "extra units" branch of the notes charge. | Nova proposes, owner approves | The proposal is an acceptance criterion of 17tnw2az0n2 and open item 3 of [86akby4e9](https://app.clickup.com/t/86akby4e9). The owner's approval: none recorded |
| OI-4 | Whether to cap how long a held-open Deepgram stream can pin an estimate, and at what figure (D5 settle point). No figure is proposed. | Owner, after OI-2 | None recorded |
| OI-5 | `PROVIDER_PROVISIONS_PER_DAY` and the provider limits it must sit under (D3). Gates turning provisioning on. | After OI-1 and OI-2 | None recorded |
| OI-6 | Re-read the provider documentation. Every `Verified (docs)` line is from 2026-09-27 and was not re-read in revisions 3 or 4. | Spike owners | None recorded |
| OI-7 | Platform PRD amendments: FR-533, FR-546, FR-547, AS-P6, AS-P7, FLOW-507 and the tier table (D8) | Priya | [17tnw2az0gu](https://app.clickup.com/t/17tnw2az0gu). Its Scope names FR-546, AS-P6, FLOW-507 and the tier table. It does **not** name FR-533, FR-547 or AS-P7 |
| OI-8 | ADR-0010: one clause on platform-issued, memory-only credentials (D8) | Owner to assign | None recorded |
| OI-9 | `selahcue-cloud/src/openai.rs` module-doc comment (D8). Wording depends on OI-1. | Owner to assign | None recorded |
| OI-10 | `DECISION-LOG.md` entries for owner D7 with its amendment, owner D8, owner D9 and OD-1 to OD-3. The amendment text is already written on 17tnw2az0g8 and 17tnw2az0gu. | Priya | 17tnw2az0gu. The DEC-014 amendment from ADR-0027 D3 is **not** in its Scope: none recorded |
| OI-11 | Whether the overrun is measured against `limit` (the owner's wording, as built here) or against `limit − carried_debt` (D7) | Owner | OD-2 is on 17tnw2az0gu. No separate ticket recorded |
| OI-12 | Ticket fallout from revisions 4 to 6 (ADR-0027) and 4 to 5 (this ADR) for the build tickets: see ADR-0027, "Needed before Accepted", item 7. Placed, not edited, by this PR. | Priya, Diego | 86akby4e9, 17tnw2az0gj, 86akby3xu, 17tnw2az0gq, 17tnw2az0gn |
| OI-13 | **Reconnect inside a live slice has no server-checkable rule.** The server cannot see the socket, so it has no way, yet, to tell a reconnect from a renewal, no allowance gate for it, and no cap per slice. Failure scenario: a modified client with an exhausted allowance and one still-`ISSUED` slice sends "reconnect" every 330 s or so. If each call returns a fresh 30 s token and moves the row's settle point, the row never settles. It costs the client 15 calls an hour against the renewal budget, and it defeats the only control, which is enforcement at the next admission. Questions: what makes a reconnect valid (a window after `issued_at`?), whether it is gated on the allowance, whether there is a cap per slice, and whether it should move the settle point at all. Until answered, the claim that a reconnect adds no hold holds only for honest clients. | Aria and Sana | None recorded |
| OI-14 | Error codes for the refusals this ADR names only as "refused": request-hash mismatch, device mismatch, and a request (plain or retry) against a `RELEASED` row. 17tnw2az0gn also says "refused" for a hash mismatch. | Aria, at build | None recorded |
| OI-15 | A client that resends a renewal after losing the response finds a row inserted directly as `ISSUED` (no credential) and gets `ALREADY_ISSUED`, so it must start a new request. That adds a second 300 s hold while the first row also stays open. Whether to accept this, or return the original result for such a row, is not decided. | Aria and Vera | None recorded |
| OI-16 | Whether the week's limit (used for the overrun, D7) is snapshotted when the week row is created, or read at settlement. Read at settlement, a limit edit in mid-week (Core 5 to 3, ADR-0027 D10) would turn admitted usage of 5 into an overrun of 2. | Aria, with the owner | None recorded |

ADR-0027's own list ("Needed before Accepted") adds the independent re-review and the staff authenticator (SEC-0027-01, 17tnw2az0n5, which gates production use and not `Accepted`).

## Rollback

Docs only today. Once built: minting can be switched off per provider (the desktop falls back to on-device transcription; notes show "unavailable"), and settlement tables are additive. Revoking every `ProviderCredential` stops new sessions but not open ones (D3).
