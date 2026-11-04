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
