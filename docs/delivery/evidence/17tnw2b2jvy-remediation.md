# Public catalogue review remediation — 17tnw2b2jvy

## Current scope

The existing public endpoint PR366 is continued, preserving the original frozen439ca56 source and actual prior iterations1–8. The two uncommitted historical evidence documents from its original worktree were copied here; that worktree and its changes are untouched. This user-requested remediation has its own bounded contract, not a silent reset of the exhausted original budget. The frozen admin dependency16eca is integrated normally; its own ticket/PR375 remains separate and must reach main before366 can merge.

The original acceptance criterion requires an actual admin mutation to appear in the next public response. It does not require production staff sign-in. ADR0027 and17tnw2az0n5 explicitly allow built/merged pricing functionality while requiring production disablement. The earlier production-authentication merge blocker was broader than the actual criterion. No criterion is waived: actual TCP HTTP mutation through the real GraphQL route now proves the requested behavior using an honestly labeled exact-dev identity fixture; production startup/service gates remain closed and staff login decisions remain outside this work.

## Production changes

Only the exact public catalogue proxy gains finite DNS/connect/send/read timeouts. Nginx resolver/connect are2seconds; upstream send/read are5seconds. Vite upstream proxyTimeout is5000ms. Existing authentication stripping, path exactness, error JSON, no-store and security headers remain. Other GraphQL/proxy routes and client deadlines are unchanged. The historical stop-request timeout at30.002647seconds remains a real failed observation; its precise historical daemon/network cause is unknown. The previously absent timeout controls are a confirmed exposed failure mode, rather than an invented explanation for that one process.

## Actual verification

- Original unchanged nginx Docker reproduction could not start: docker run timed out40seconds and its cleanup rm timed out30seconds. The daemon answered version29.8.0, but other operations hung. No Docker restart or global cleanup was attempted, and no nginx runtime pass is claimed locally. The explicitly owned names catalogue-remediation-outage/catalogue-remediation-outage-nginx need cleanup/readback when that daemon recovers.
- Exact-route timeout guard first failed against the absent controls, then passed after the fix.
- Actual native Vite old control hit its unchanged10second client deadline in10.0169seconds. The same real stalled upstream through the fixed proxy returned exact JSON503/no-store in5.3016seconds. Both requests prove Cookie/Authorization/Referer were stripped. Processes were terminated as owned groups and temporary config removed. Raw /private/tmp/public-vite-outage-runtime-complete.log; compact result/input hashes in17tnw2b2jvy-remediation-vite.json.
- Diagnostic failures are retained: initial Python3.9 socket.timeout handling was incomplete, and the HTTPError503 branch did not assign the result. Two incorrect-cwd patch commands failed and consequently repeated the old diagnostic. These did not modify the production fix or deadlines. Corrected verifier completed both old and fixed cases; no failed execution is credited as a pass.
- Real TCP HTTP rehearsal uses Django live_server, a real CSRF bootstrap cookie/header, explicit exact-dev actor fixture and real GraphQL mutations. A warmed public response changes Core weekly notes5→6 and unpriced→priced USD/MONTH0 on the next unauthenticated HTTP GET without restart/deploy. An identical retry is replayed and the two changes leave exactly two audit events. This is not a direct writer or synthetic response.
- Final integrated admin/public/proxy focused run:95passed/4explicitPostgreSQL skips in3.46seconds. Hosted PostgreSQL remains mandatory for current full service regressions and lock/concurrency cases.
- Workflow checker:7workflows/21jobs pass. Both new runtime scripts compile. Current marketing gate passes type-check, lint,1250unit tests with0fail/0skip, and production build. Current independent reviews/CI remain pending; pending commands are not passes.

## Retained CI controls

The API job runs catalogue_proxy_outage_runtime.py using actual nginx and a unique disposable Docker network. It checks shipping-config healthy response, actual upstream container stop→bounded JSON503, controlled silent-DNS old-config30second negative versus current2second fallback, and a real accepted-but-stalled TCP upstream→5second fallback. Only external resolver/upstream fixture addresses are substituted for those controlled outages; counts assert substitutions occurred. Resolved image identity is recorded. All owned resources have removal/readback checks, and cleanup failure fails the job.

The marketing job runs catalogue_proxy_outage.py against the actual installed Vite and real local sockets, including the old missing-control negative, credential stripping and current bounded fallback. Neither job silently skips unavailable Docker/npm/runtime behavior. These hosted runs must actually complete before merge; local daemon failure is not substituted for them.

## Integration and remaining gates

Admin integration conflicts were limited to additive README sections and the revision-watch explanatory comment. Both README contracts are preserved; executable watched-model lists include PlanPrice in both parent and child. The actual GraphQL/service/permission/receipt/locking code matches admin16eca. No production credentials, production data changes, collection, deployment or installer release occurred. Four current independent reviews, actual applicable CI and the admin merge are still required before authorized merge/QA.
