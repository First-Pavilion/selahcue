# CSP-safe shipping-gate waits

Base/main6b096771d3d65c1dacf105523a4ee48edc2d4f93; branch codex/17tnw2b0x3m-csp-wait.
Owning follow-up: https://github.com/First-Pavilion/selahcue/issues/364 . Original task https://app.clickup.com/t/17tnw2b0x3m and implementation PR352 are already merged/QA per coordinator. This is a separate new goal; the original ledger is unchanged. Native tracker bug/status backfill remains pending: connector quota1000/1000 and browser inputs unavailable. Root explicitly authorized proceeding through this external write blocker; no InProgress write is claimed.

## Actual failure and independently reproduced cause

Hosted shipping job126550763358/run41823034596 reached Chromium68 routes, then its authentication wait threw unsafe-eval EvalError. Raw owning log: /private/tmp/wave2-350-final-marketing-ci.log, lines12010 onward; durable job https://github.com/First-Pavilion/selahcue/actions/runs/41823034596/job/126550763358 . Installed pinned Playwright1.60.0 coreBundle.js waitForFunctionExpression invokes globalThis.eval(expression) in the main world. All three old expression waits share that mechanism.

An intercepted synthetic strict-CSP fixture independently reproduced the same old authentication API EvalError in real Chromium and WebKit (`controlled-baseline.json`). That is controlled reproduction, not a second shipping-run trace. The full shipping-image verification below is separate. No CSP rule, bypassCSP flag, browser pin, app source, nginx/Vite policy or timeout relaxation was used.

## Final wait contract

- App readiness uses a locator innerText regex equivalent to trim().length>20, retaining the exact21-character threshold.
- Authentication uses the real form's aria-busy attribute exactly equal to false; missing or busy forms cannot pass.
- The real securitypolicyviolation listener retains its full directive/URI array and publishes its positive count through an HTML data attribute. A locator waits for that marker; the existing actual violation/directive and inline-script-not-executed assertions remain intact.
- All three helpers retain the old30,000ms default budget. Controlled negative fixtures shorten their own wait to150ms only; there is no production sleep or longer deadline.

## Executed verification

| Verifier | Result |
|---|---|
| Controlled real-browser wait regression | exit0;3 positive +4 negative cases per engine, both engines |
| Missing-wait early-return mutants in disposable copies | each actual regression CLI exits1 for rendered-app/auth/event wait removal |
| Exact-base existing production Docker build/nginx-t | exit0; image policy config byte-matches unchanged source |
| Full shipping production probe | exit0; Chromium68 +WebKit68 routes, actual fonts/auth/mobile/header/error and injected-inline refusal,240.205s shared-local observation |
| Existing API nginx proxy/bypass file in task-owned locked uv environment | exit0;28 passed, source unchanged |
| Workflow controls/self-tests and minute rules | exit0;6 workflows/20jobs,118 self-tests |
| Shared visual/audit gate first observation | exit1 solely11.383s>unchanged10s budget; all206+97 content/control checks pass |
| Shared visual/audit gate serial observation after browsers finish | exit0;9.257s<10s, no gate/policy/source change |
| Python compilation and diff whitespace | exit0 |

Both timing observations are retained. The serial pass is a local observation, not a general speedup or hosted-budget promise. Actual current-source CI remains required. Controlled fixture output and source are separate from the actual full shipping proof; all68-route assertions, real fonts, auth POST/menu behavior, response headers and actual blocked script checks remain enabled. Only API responses use the unchanged synthetic account fixtures; no live account/provider/registration/deployment/installer operation occurs.

All local verifiers finished and the isolated container stopped/removed successfully before handoff. Root owns full diff inspection, four independent reviews, actual CI, fresh main merge and native tracker/QA updates. Pending tracker write and review/CI gates must not be treated as completed.


## Current-main private verification — actual iteration3, maximum5

The sections above are historical6b-baseline results. Root explicitly authorized this SAME Goal maximum4to5 and one current-target verification iteration; only original iterations1–2 existed, so this is actual iteration3, not fabricated executed slots3–4. NEWprivate branch `codex/17tnw2b0x3m-csp-current-local` normally merged current maina6cbd07dd4684621ffb8bb8d6f08f790fa6946d3 at8178a69926ba57eaf12ae556c19f122e1f63de6c, without conflicts. The original exact6297c7db worktree remains clean and unchanged for its pending public-publication approval. No push, PR, hosted CI, merge or QA transition occurred here.

The two CSP wait/verifier scripts, nginx policy, Dockerfile, package/lock, Vite configuration and pilot notice are byte-identical to6297. Target marketing changes are App.vue/footer readiness, responsive_sweep.py and the separately reviewed loading-footer verifier. Because App.vue is a production input, a fresh actual shipping image and both-engine probe were executed rather than reusing old68+68 evidence. Current image `sha256:7980c6716c9cd689b7ea230a3b2b2c7f09e3a9b2737bbc020353ec454703c365`; actual nginx configuration byte-matches source, `nginx -t` exits0, and the actual117-file shipping bundle is copied and hashed.

| Current verifier | Actual result |
|---|---|
| Current Docker production build | exit0;15.597s; no source input changed during build |
| Actual shipping browser gate | exit0;Chromium68 +WebKit68, real fonts/auth/mobile375/headers/assets/errors/blocked-inline-event controls;156.063s shared-local observation |
| Real strict-CSP readiness fixture | exit0;3positive +4negative per engine |
| Three actual CLI helper-removal mutants | each exits1 specifically for accepting an incomplete condition |
| Fresh own locked API environment/proxy guards | verifieduv0.13.4/Python3.14.5; actual28passed,0.42s; helper verifies current checkout |
| Current workflow coverage |118legacy +39CLI cache cases;6workflows/20jobs normalcheck PASS |
| Current affected supply/canary/minute controls |8policy mutants +36actualalias/status probes;16canary drift refusals +2real shell probes; minute self-test/normal PASS |
| ONE serial current visual/audit gate after browser/container cleanup | exit0; internal3.324s<unchanged10s; wrapper3.434s; no retry |

The new elapsed observations are scoped shared-host results, not controlled performance comparisons. Historical11.383s failure and9.257s pass remain above and are not relabelled current results. No full responsive sweep, browser-pin/policy/default30-second change, live account/provider/collection, deployment or installer action was performed. API tests were rerun in a new owned locked environment because current main changed catalogue model/bootstrap inputs even though the proxy test/config bytes are unchanged. Read-only pinneduv binary reused; no global install/toolchain change.

Raw current command argv, stdout/stderr, elapsed/exit/timeout/reaped receipts, exact source and image bundle manifests, mutant copies and summary are in `/private/tmp/csp-current-local-evidence/`. Private evidence driver `/private/tmp/csp-current-local-run.py`. An explicit initial Python syntax compile was denied while attempting the host's external bytecode-cache path before tests; using a task-owned PYTHONPYCACHEPREFIX completed it. Native worktree API could not identify the repository, and the sandbox denied Git metadata creation before authorized task-owned fallback succeeded. These setup observations are not product-test retries.

All verifier/browser processes completed; owned Docker container was removed and independently read back absent. Local image/bundle/environment remain available for independent review. Native Bug17tnw2bcj0m was independently read InProgress, while root owns final audit/status. Current C001–C003 local evidence is ready; C004 remains BLOCKED for four current affected reviews, exact publication approval, actual hosted CI and root main/QA verification. The automatic rejection of the original exact public payload is not bypassed by this private branch.
