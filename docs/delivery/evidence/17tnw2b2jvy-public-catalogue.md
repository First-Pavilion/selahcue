# Public current catalogue — 17tnw2b2jvy

Task: https://app.clickup.com/t/17tnw2b2jvy. This is a read-only slice stacked on catalogue data PR358 (confirmed parent `0d7fbb615fe014d5d246d9ab6534e85bd11075c7`, original data freeze `f65731dd15401097e896b896fb0eccda2f3bd48a`). It does not include staff sign-in or catalogue mutations. Root owns dependency retarget, four independent reviews, current hosted CI, merge and QA.

**Status: BLOCKED for full acceptance.** The read-only source is ready for independent
inspection, but the final bounded shipping API-stop/separately committed price HTTP
proof did not execute because disposable API migrations did not reach readiness. The
original authenticated admin-mutation E2E also remains blocked on its separate task.
No merge/QA/completion claim follows from the passing partial evidence.

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
- Preliminary full API run was deliberately terminated before scalar compatibility correction; it is not a pass. The subsequent final full gate passed2408 tests; see scoped receipts below.
- Shipping source images built successfully. An earlier complete HTTP phase proved production/dev exact paths, real weekly writer5to6 and Redis429; final added API-stop/separate price HTTP proof remains BLOCKED as described below.
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
GraphQL proxy or CORS. Affected public/nginx/CSRF checks69passed. Actual dev refused-upstream probe changed502RED to503JSON/no-store/nosniffPASS. Final production API-stop proof remains BLOCKED.

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
and separately committed price-writer checks remain BLOCKED below; authenticated admin E2E
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

## Final iteration5 result and immutable evidence

The confirmed parent was normally merged into the child as `838e09532fe55e090225f702b590781dd752ad62`,
preserving both README changes. Deliberate `make api-install` with exact uv0.13.4 refreshed
the owned stamp. Install-free stamp verify and affected public/nginx/CSRF suite then
**69passed,22.37s, exit0** (`/private/tmp/17tnw2b2jvy-parent-focused69.log`).

The final API image was actually rebuilt for the new parent metadata, not treated as
identical to the old image: `sha256:797160e272048e9dc55f73db850d3dbafc7d537452bbdff50fa00ca2c4adc7cb`,
build exit0. Final shipping marketing source build exit0, its build step337seconds,
without changing the15minute CI policy (`/private/tmp/17tnw2b2jvy-marketing-final-source.log`).

Exact parity verification passed for all113 API runtime Python files, current
`pyproject.toml`/`uv.lock`/`.uv-version`, and all36 Unix-installed registry versions
against the final image/owned venv. The universal lock contains37 registry packages;
Windows-only `colorama` is correctly absent on both Unix platforms (verified incoming
pytest edge `sys_platform == 'win32'`). The initial parity helper incorrectly expected
every universal-lock package installed; only that verifier was corrected, without
installing an inappropriate dependency or changing package versions. Receipt:
`/private/tmp/17tnw2b2jvy-parent-parity-final.log` and runtime hash manifest
`/private/tmp/17tnw2b2jvy-runtime-parity.json`. This supports retention of the previously
completed full2408/native67 **unchanged-runtime** evidence, not a claim that those
complete suites were executed on the new image metadata.

The **single** root-authorized final attempt used final TCP PostgreSQL readiness
(30seconds/probe,180seconds overall), tmpfs test data and bounded API readiness. It
terminated with `RuntimeError: API migrations not ready` before executing the final
HTTP assertions. Last observed migration progress was catalogue0001; database wait-state
diagnostics showed only the active diagnostic query (zero elapsed), and Redis answered
PONG. This does not establish a product/runtime failure or an SLA pass. It does mean
**production API-stop503 and separate-process committed-price/boundary HTTP proof are
not verified**. Log `/private/tmp/17tnw2b2jvy-iteration5-final-http.log`, exit1. No further
retry or source expansion followed. The process was reaped; task-labelled containers
and network read back empty. All other local verifier/build processes also finished.

The actual refused-loopback dev probe did prove503JSON/no-store/nosniff after observing
502RED, but one prior120second cold-start readiness observation timed out; the diagnostic
run saw `RemoteDisconnected` during startup before eventual503. Precise earlier host
causality is unknown; no timeout was silently reclassified as a pass.

Mandatory remaining gates: shipping API-stop/separate price HTTP proof (root bounded
disposition needed), original admin mutation E2E (`17tnw2az0gg`/real staff sign-in), current
hosted PostgreSQL/Redis CI and independent Cody/Shadow/Quinn/Vera review. Source draft
publication is for review with these explicit blockers, never merge or QA authorization.


## Explicit same-Goal extension6–7: observable attempt, no publication yet

Root expressly extended the existing Goal maximum5to7, retaining the complete1–5 ledger. Iteration6 changed only a private task evidence runner, not product/API/proxy/auth/budget source. The actual subprocess shim exiting17 preserved full stdout/stderr/returncode and stopped; missing readiness marker and nonzero migration status failed, with explicit pending/ready positive controls. The runner uses original180second setup/30second probe and HTTP limits and exact frozen image IDs. It records every command before evaluating status and preserves redirected migrations plus complete container inspect/state/exit/OOM before cleanup. These controls did not compile-check embedded writer scripts, which was a verifier gap.

The ONE iteration7 actual attempt exited1 and was reaped. API migration exit0 and readiness marker were actually observed. Complete migration stdout includes final0008rank and sessionsOK; no earlier unknown setup cause is retroactively diagnosed. Initial production GET became200, seed/unpriced/weekly5 and full security/no-store/no-CORS assertions passed, actual POST without CSRF returned403HTML, neighbor paths returnedSPAHTML and unsupported query returned400. No performance/SLA pass is claimed.

The first separate grant-writer Docker exec actually exited1. Full stderr proves `IndentationError: unexpected indent` at embedded Python line2. This was introduced by the implementer when wrapping the old top-level evidence runner in `main()` and indenting lines inside its triple-quoted writer string. It is an evidence-runner mistake, not a product error. The observer correctly stopped rather than swallowing that error. Separate price commit/boundary and API-stop assertions therefore NEVER executed; C002/C003 remain BLOCKED. No retry/fix or eighth iteration follows this attempt. Staff/admin E2E C005 remains separately blocked; no internal writer substitutes for authenticated admin acceptance.

Before removal, actual API inspect recorded running=true, ExitCode0, OOMKilled=false, Error empty, image `sha256:797160e272048e9dc55f73db850d3dbafc7d537452bbdff50fa00ca2c4adc7cb`. A running container's State.ExitCode0 is not a process-termination result; migration exit0 is separately recorded. Full raw receipts: `/private/tmp/17tnw2b2jvy-iteration7-evidence/`, including `migrations.log`, `migrations.stderr`, `migrations.exit`, readiness marker, complete command stdout/stderr/JSON,12 HTTP responses with headers/body, `summary.json`, and failed `command-0041.*`. Run log: `/private/tmp/17tnw2b2jvy-iteration7-http.log`. Private driver: `/private/tmp/17tnw2b2jvy-observable-rehearsal.py`, SHA256 `0bb42768778120a92ca9658a087d83848a7f3c7ec94bc64ddf6eac584d0b1e56`; shim driver `/private/tmp/test-catalogue-observability.py` and raw `/private/tmp/17tnw2b2jvy-observability-selftest/`.

All child commands finished/reaped; task-labelled containers and network independently read back empty. Product source remains frozen439ca56f; only this evidence and Goal are local uncommitted edits, not published. Root must review this full handoff before any revised publication or further bounded disposition. Existing current hostedCI41839983138 passed independently, but it cannot replace the missing HTTP/admin journeys. No merge/QA claim.


## Final iteration8 — inspected known-regression correction and remaining timeout

Root explicitly extended SAME Goal7to8 only to correct the known evidence-runner indentation defect. Before any Docker execution, AST inventory identified exactly both actual Python-c payloads. Both repaired payload values are byte-identical to the original retained runner, compile successfully, and both oldbroken values fail IndentationError at line2. Root inspected full diff, extracted actual payloads and checks, then authorized ONE originaldeadline attempt. Private repaired runner `/private/tmp/17tnw2b2jvy-observable-rehearsal-iteration8.py`; preflight `/private/tmp/17tnw2b2jvy-iteration8-preflight/`. Previous failed driver and1–7 evidence remain intact. No product/API/proxy/auth/dependency/budget source changed or image rebuilt.

The final attempt exited1/reaped, with actual partial journeys now proved:

- Migration exit0/readiness marker; actual production seed200/unpriced/weekly5 and all expected security/no-store/no-CORS assertions. Unsafe POST403HTML remains middleware behavior; neighborSPA paths/query400 pass.
- Real separate grant writer exits0 and next productionHTTP shows notes5to6. Real separate audited price writer exits0 and reports `PROBE_PRICE_EFFECTIVE=2026-11-04T16:23:30.307491+00:00`. After the actual boundary, productionHTTP200 contains CORE priced, exact single USD/MONTH offer amount_minor string0/exponent2 (receipt `http-0015.json`). Thus C002 separatelycommittedprice/boundary HTTP evidence is now present. These remain INTERNAL SERVICE writers, not authenticated admin mutations.
- Actual dev normalGET observes notes6; neighbor/query checks pass. After real Redisstop, production/dev both return429 JSON/catalogue_rate_limited with positiveRetry-After (`http-0026/0027.json`).
- After real APIstop, the FIRST productionGET receives no response within original30second timeout: `http-0028.json` records timeout at30.002647042seconds. ProductionAPIstop503/header proof remains BLOCKED; devAPIstop check was not reached. This is not a503PASS or evidence of an established nginx/application root cause. No9th attempt, deadline relaxation or source fix follows.

Pre-cleanup APIinspect records stopped/exited137, OOMKilledfalse/Error empty, following the explicit `docker stop` command; this is not classified as a spontaneous startup crash or OOM. Full shipping nginx logs show earlier connection-refused startup observations that produced503 before eventual200; those early responses do not substitute for the later APIstop journey. Shared-host observations are not a performance/SLA pass.

Raw final bundle `/private/tmp/17tnw2b2jvy-iteration8-evidence/` retains every complete commandstdout/stderr/returncode/timeout/reaped receipt,28HTTP success/error/header/body records, full migrations/logstderr/exit/marker, complete containerConfig/State/image and `summary.json`; run log `/private/tmp/17tnw2b2jvy-iteration8-http.log`. Source439 and exact frozen API/production/dev image IDs remain unchanged. Actualtask-labelled containers/network independently read back empty; all child processes finished/reaped. The reviewed source remains frozen and ONLY local uncommitted Goal/evidence edits exist. Root owns revisedpublication/fourreviewrefresh, currentmain integration and the remainingC003/C005 disposition. Native InProgress for17jvy was authenticated/read back by root during this final attempt; no child status mutation claimed.
