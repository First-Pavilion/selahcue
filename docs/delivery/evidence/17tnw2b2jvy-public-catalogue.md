# Public current catalogue — 17tnw2b2jvy

Task: https://app.clickup.com/t/17tnw2b2jvy. This is a read-only slice stacked on catalogue data PR358 (`f65731dd15401097e896b896fb0eccda2f3bd48a`). It does not include staff sign-in or catalogue mutations. Root owns dependency retarget, four independent reviews, current hosted CI, merge and QA.

## Browser/API contract

Call same-origin `GET /v1/catalogue/plans`, without query parameters or authentication. Both marketing nginx and Vite forward only this exact path (query suffix allowed through to the API, which rejects parameters). No general `/v1` proxy or CORS permission is added. The new proxy strips Cookie, Authorization and Referer; existing GraphQL behavior remains intact.

A seeded response is:

```json
{"plans":[
  {"key":"FREE","name":"Free","price_state":"unpriced","offers":[],"cloud_transcript_minutes_per_week":20,"sermon_notes_per_week":1,"watermark":true},
  {"key":"CORE","name":"Core","price_state":"unpriced","offers":[],"cloud_transcript_minutes_per_week":50,"sermon_notes_per_week":5,"watermark":false},
  {"key":"PRO","name":"Pro","price_state":"unpriced","offers":[],"cloud_transcript_minutes_per_week":80,"sermon_notes_per_week":10,"watermark":false}
]}
```

Names, keys, ordering and values come from rows. Plan ordering uses `sort_order`, then `code`, independently of entitlement rank. The projection contains exactly the shown plan keys and root `plans`. It does not expose internal IDs, actors/reasons, account/customer/licence/usage information, private device grants, or undecided Core/Pro screen/NDI/device placeholders.

Each **current** configured currency/interval pair appears once in `offers`, ordered by currency then interval. No commercial default currency/interval is chosen. The exact offer keys are:

```json
{"currency":"JPY","interval":"MONTH","price_state":"priced","amount_minor":"0","minor_unit_exponent":0}
```

- `interval` is `WEEK`, `MONTH` or `YEAR` from data. `minor_unit_exponent` is the pinned ISO4217 exponent, not a divisor or an assumed number of cents.
- `amount_minor` is a base10 integer **string**, preserving all signed64-bit nonnegative amounts in JavaScript. An explicitly configured zero is `"0"` and `priced`.
- A current version with null amount remains an offer with its configured currency/interval, `amount_minor:null` and `price_state:"unpriced"`.
- No currently effective version means no offer for that pair. Future-only versions do not appear prematurely. An empty offers array means unpriced; no currency/interval/zero is fabricated.
- Plan `price_state` is `priced` when at least one current offer is priced; otherwise it is `unpriced`. Clients still inspect each offer's state, so a mixed set is not mistaken for every pair having a price.
- All three public grant fields must exist on active dimensions with the correct type. Weekly values must be finite nonnegative JavaScript-safe integers; watermark must be a valid boolean. Missing, unlimited, malformed, inactive or unknown-scale current price data refuses the whole projection instead of publishing a misleading default. The existing governed grant parser supplies accepted numeric/boolean vocabulary.

For GET failures handled by this route/proxy, the exact error body is `{"error":{"code":"..."}}`:

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `catalogue_invalid_request` | Query parameters are unsupported |
| 405 | `get_required` | GET-only view refuses another method; `Allow: GET` |
| 429 | `catalogue_rate_limited` | Budget denied **or limiter store unavailable**; positive `Retry-After` |
| 503 | `catalogue_unavailable` | Missing/malformed/degraded/over-capacity data, changed-during-build revision or database failure |

Normal CSRF middleware remains enabled. Unsafe methods without valid CSRF can be
refused earlier with403 and middleware HTML; only requests reaching the GET-only view
receive405 JSON/AllowGET. The default Django Client405 test is explicitly view-level;
a separate `Client(enforce_csrf_checks=True)` POST proves actual403 and no writes.
Frontend callers use GET and do not depend on a non-GET error schema.

All route-handled endpoint responses use `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. Shared/browser caching cannot bypass admission or hide the next write. Error text does not include database/cache exceptions. No session or CSRF bootstrap is required for this public read.

## Bounds, invalidation and effective time

There is exactly one immutable in-process cache entry, never a request-keyed map. Bounds are64 plans,128 current offers per plan and1MiB serialized response. Exceeding a bound refuses with503; it never silently truncates a plan or a currency pair. Cold reads materialize bounded plans/grants/current offers; SQL selects the newest already-effective price for each plan/currency/interval using `ROW_NUMBER`, so old versions cannot displace another current pair. Existing price composite index supports partition/lookup order. Future boundary comes from one SQL minimum query. Query inspection on actual history: cold6 reads, warm1 primary-key revision read, independent of plan/offer cardinality within bounds; no N+1 lookup.

Every GET still reads the database revision. Plan, dimension, grant and now price saves bump the shared revision inside the writer's transaction; a cold projection rechecks revision before caching and refuses if it changed. Cache expires at30seconds **or the earliest future effective price**, whichever occurs first. Backward wall/monotonic time also rebuilds. Thus a scheduled price takes effect even with no write at the boundary. The TTL bounds signal-bypassing SQL updates; model/service changes invalidate immediately. A database outage never serves a warm commercial snapshot.

Admission reuses the shared trusted-proxy-aware client-IP resolver, IPv4-mapped normalization, IPv6 /64 bucketing, opaque cache identity, atomic Redis counter, bounded outage reporting and positive retry hint. The dedicated budget is `SELAHCUE_THROTTLE_PUBLIC_CATALOGUE=(120,60)`, fail closed. No untrusted forwarded-header override or local fail-open allowance is introduced. Production requires the existing shared cache/trusted edge configuration; local LocMem behavior remains process-local as before.

## Proxy trust test fixture change

Adding a second legitimate proxy made the old bypass fixture's whole-file `HEADER_LINE` literal-count assumption invalid. The security parser and policy assertions are unchanged. Fixture selection now locates the named flat protected location and mutates that location's own mapped setter. Every original malicious case still must fail for its intended policy reason; the six bypass cases run for both GraphQL and the exact catalogue location. No count2 workaround, skip, server include, mapped-variable override, or differently formatted setter evasion is used. Both locations use the normal mapped proto directive and retain their own forwarding headers; nginx security/CSP header inheritance is unchanged.

## Verification ledger

- Verified RED: initial exact public HTTP seed assertion404;19 initial route/price/privacy/throttle/writer cases failed before production implementation.
- Verified GREEN: initial19 cases passed.
- Verified RED: deep test29passed/1failed exposed missing exact marketing proxy; then actual Node negative-path probe caught an overbroad escaped Vite regex. Corrected with an unambiguous `[?]` class; exact/query match, suffix/trailing-slash do not.
- Verified RED: real governed writer accepted `+7`/Arabic digit7, initial public projection refused. Reused existing `coerce_grant_value`; finite bounds remain enforced.
- Verified focused: **67passed**, including real writer invalidation, all current price pairs/null/zero/64-bit amounts, scheduled time, clock rollback/TTL, revision race, bounded cold/warm queries, degraded data, both proxy trust locations and retained bypass shapes. Log `/private/tmp/17tnw2b2jvy-focused-final.log`.
- Preliminary full API run was deliberately terminated before scalar compatibility correction; it is not a pass. Fresh final full gate pending at this checkpoint.
- Shipping production/dev images and disposable actual HTTP/Redis-outage rehearsal pending at this checkpoint.
- Actual hosted PostgreSQL/Redis CI and independent Cody/Shadow/Quinn/Vera review pending; local service skips cannot substitute.

## Original acceptance dependency — remains blocked

**The actual admin-mutation-to-public E2E criterion is BLOCKED** on `17tnw2az0gg` and real staff sign-in. Existing `/graphql/admin` has no price/grant mutation; its legacy header bridge is not an acceptable substitute. Tests through `set_plan_grant` and `append_plan_price` demonstrate internal service-writer invalidation only. They do **not** demonstrate an authenticated admin mutation. This ticket does not add permissions, roles, staff resolvers, an auth bridge, or a hidden administrative endpoint. Parent must preserve this acceptance dependency and decide the aggregate disposition before QA; this evidence does not claim full ticket completion.

Rollback: revert this route/projection/proxy slice. No migrations, catalogue price configuration or source-data changes are performed by deployment of this ticket.

## Additional actual upstream-failure finding

The shipping-image rehearsal exposed a real degraded-state error: while API startup was
unavailable, inherited nginx `error_page 502 ... /50x.html` redirected to an absent file
and returned404. Production GET became200 once Django started. This was independently
verified in the actual runtime config/API startup logs, rather than treated as a missing
route. The new exact catalogue location now sends only its upstream502/504 failures to
an internal JSON503 `catalogue_unavailable` fallback. Adding no-store disables nginx
header inheritance, so that fallback repeats **every** existing server security header
unchanged, including CSP. Shared/GraphQL error handling remains unchanged. The new guard
was observed RED before the scoped fix; all68 public/trust tests then passed.

A separate actual dev probe observed Vite's default unavailable-upstream502 with an empty
body (RED). Its installed8.3.4 implementation registers `configure` handlers before the
built-in error handler, which respects `headersSent`/`writableEnded`. An exact-route
handler therefore supplies the equivalent JSON503/no-store/nosniff without touching the
GraphQL proxy or CORS. Final affected runtime checks remain pending at this checkpoint.

These proxy-only changes leave API runtime/SQL source unchanged. Retained full gate:
**2408passed,54explicitservice skips,57subtests in537.66s, exit0**; system checks and
migration consistency clean. Log `/private/tmp/17tnw2b2jvy-full-api-inventory-final.log`.
The preceding completed full run correctly found the new route missing from the existing
contract inventory (2failed,2406passed); `public_catalogue_contracts()` and both complete
inventory comparisons were updated, preserving the missing-route positive control.
Targeted inventory checks4passed before the final complete passing rerun.

Retained actual native PostgreSQL16/Redis7 focused evidence: **67passed, no service skips,
46.67s** in the source API image, before this proxy-only follow-up. All12 malicious nginx
fixtures were also valid under actual shipping `nginx -t` while the policy suite refused
them for their intended reason. The final added proxy guard passes locally (68total).

The initial service rehearsal needed an explicit loopback `api` hosts entry for the
malicious fixture's intentional literal upstream, then a cheap post-migration readiness
marker instead of repeated cold Django imports. These were harness corrections, with
cleanup on each failure. A later5second post-write HTTP observation timed out; this alone
did not establish server blocking. The bounded30second HTTP-only observation then passed
(production seed1.901s, committed weekly writer next response1.559s, dev7.574s, actual
Redis outage429 production0.765s/dev9.332s). These are shared-host observations, **not a
performance/SLA pass**, and no shipping/CI timeout or budget was changed. Final API-stop
and separately committed price-writer checks are pending below; authenticated admin E2E
remains blocked regardless of these service-writer receipts.

## Explicit bounded continuation and prerequisite refresh

Root confirmed prerequisite freeze `0d7fbb615fe014d5d246d9ab6534e85bd11075c7`, the normal
main/uv-compat integration into PR358. It changes uv metadata/tool docs and CI guards,
not catalogue/runtime Python source. Root explicitly authorized extending the original
Goal maximum4to5 with its full ledger retained: normal parent merge, deliberate exact
uv0.13.4 venv-stamp refresh, source-matching API image build and **one** final unfinished
HTTP phase. Disposable PostgreSQL readiness is bounded30seconds per probe/180seconds
overall; this changes no production/CI budget. The previous5second setup timeout
occurred before API creation; diagnostic cache PONG and missing PostgreSQL socket were
recorded, and cleanup completed. No further silent retries or source expansion are
authorized; remaining failed proof must be handed back honestly. All113 runtime Python
files were proven byte-identical to the completed native API image; recheck after merge.
Changed image metadata must be rebuilt and identified honestly.
