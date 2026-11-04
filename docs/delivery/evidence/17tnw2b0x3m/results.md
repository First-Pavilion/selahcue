# Marketing production / CI hardening — 17tnw2b0x3m

Final integration target: `13bb3c255dd83ef9917a344964ce55725ec91db2` on main, including reviewed uv and Home harness changes. Initial implementation base was `c0325d52e809847fac141a605b74a7e6d7de7021`.
Branch: `codex/17tnw2b0x3m-marketing-hardening`. No deployment or registration activation.

## Implemented behavior

- Marketing job has only contents:read and disables persisted checkout credentials.
- `.npmrc` suppresses dependency lifecycle scripts. Explicit npm tasks remain enabled.
- Unsuppressed `npm audit --audit-level=high` rejects high/critical findings and registry errors; no overrides or advisory waivers.
- Supported Node 22 builder matches CI. Actual production build exposed preexisting TS2307: PilotPrivacyView imported canonical notice.json outside the old marketing context. Kept the reviewed notice/import unchanged, corrected compose/CI build context, copied only explicit required files. Dockerfile-specific ignore denies unrelated repository contents and credentials/local caches.
- Enforced CSP denies inline scripts/styles, eval, objects, foreign connections/forms/frames. Identical security directives are inline in the server and asset location, preserving asset/error headers despite nginx inheritance. No server include hides directives from the unchanged forwarded-proto trust guard.
- Preserve existing fonts and privacy disclosure via exact Google stylesheet/font hosts. Self-hosting considered and deferred pending verified font artifact/licensing and coordinated disclosure update. Existing desktop Inter-named assets carry a Noto license attribution, so they were not reused blindly.
- Repository-wide Actions SHA pinning belongs to separate ticket 17tnw2b1wx5. Existing action versions, visual/installer/NDI controls and 15-minute timeout preserved. Public-repository workflow comments corrected.

## Initial implementation verification (historical f76e6a9f)

The following records the first implementation. Final inline-config verification and the actual CI compatibility correction are recorded in iteration5 below.

### Verification environment

Local Node v26.7.0/npm11.19.0; shipping Docker build runs actual Node22-alpine. Python3.14.5, pinned Django6.1.2/PyYAML6.0.3, Playwright1.60.0 (Chromium148 and WebKit), Docker29.8.0. Both actual browser engines ran against built production nginx on loopback, not Vite preview. Only GraphQL data was stubbed; real Google stylesheet/font HTTP responses were verified. No live account, registration or collection request.

| Check | Actual result |
|---|---|
| New focused regression tests before implementation | exit1, 3 failing hardening cases |
| Final focused hardening tests | exit0, 4 passing cases |
| Fresh npm ci --ignore-scripts | exit0, 188 packages installed |
| npm audit --audit-level=high, real registry | exit0, 0 high/critical; 13 moderate package nodes |
| Same audit threshold, local synthetic high advisory fixture | exit1, 13 high package nodes; expected refusal |
| make marketing-check | exit0, type-check/lint/build and 1250 tests pass |
| docker build --pull -f implementation/marketing/Dockerfile .; nginx -t | both exit0, real Node22 build and nginx1.31.8 image/config |
| Production CSP browser gate | exit0, Chromium68 + WebKit68 routes, fonts/auth/mobile/header/error and blocked-inline-script probes |
| Client/server mirrors | exit0, 6453 generated email addresses agree with pinned Django |
| Shared components both engines | exit0, 646 checks |
| Core pages both engines + frame regression | exit0, exact geometry /20 nominal widths/20 overflow negatives |
| Home both engines | exit0, 260 checks |
| Secondary pages both engines | exit0, 362 checks |
| Responsive Chromium | exit0, 2363 checks, 41 routes ×5 widths |
| Final sequential auth states | exit0, 77 scenarios /2765 checks /0 FAIL |
| Final sequential responsive WebKit | exit0, 2363 checks /41 routes ×5 widths /0 failed |
| actionlint .github/workflows/ci.yml | exit0 |
| check_workflows.py --self-test / normal | both exit0, 118 self-tests and6 workflows/19 jobs |
| check_ci_minutes.py --self-test / normal | both exit0; runner/matrix/alarm controls preserved |
| py_compile production harness; git diff --check | both exit0 |

`production-csp.txt` and `audit-summary.json` retain compact actual output. Full local verifier logs are `/tmp/selahcue-marketing-*.log` for independent review.

The initial parallel browser run let a rebuilding suite remove dist while auth/WebKit responsive were reading it. Those attempts are invalidated; affected auth process was explicitly terminated (143) and reaped. Final affected checks run sequentially against stable dist; no result is inferred from launch or output alone.

## Policy sources

- [Node release schedule](https://github.com/nodejs/Release#release-schedule): Node20 EOL and Node22 supported line.
- [npm configuration](https://docs.npmjs.com/cli/using-npm/config/): ignore-scripts and explicit npm run semantics.
- [nginx header module](https://nginx.org/en/docs/http/ngx_http_headers_module.html): add_header inheritance and always behavior.
- [CSP style-src-attr](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr): attribute restrictions and direct style property behavior.
- [Docker build context](https://docs.docker.com/build/concepts/context/): Dockerfile-specific ignore precedence and context exclusion.

## Remaining gate

Root must obtain independent Cody, Shadow, Quinn and Vera PASS verdicts on the final head, real GitHub CI success and fresh-main integration before merge. Ticket moves to QA only after confirmed merge on main. This implementation has no self-approval or deployment claim.

The first implementation's browser checks finished exit0. Its separate Linux WebKit Home layout-viewport issue is now fixed upstream by17tnw2bcadw/PR354, merged on main13bb3c25. This branch preserves that reviewed fix. Final current-source/target CI and four refreshed reviews remain required; there is no deployment or QA claim.

## Historical trigger remediation — iteration4 (d17d41b5)

All four first-round reviews of f76e6a9f identified one root cause: the downstream notice JSON area filter could not run because both top-level events excluded docs/**. The active ticket remained In Progress; root posted the consolidated review and remediation start via authenticated ClickUp UI after connector quota exhaustion.

The regression was added first: the real checker exited1 naming push and the canonical notice. Both event lists now re-include only `docs/release/pilot-registration/notice.json` after their exclusions. The existing checker explicitly recognizes that path and preserves its original20 cases, adding8 cases across push/PR: the notice is included; neighboring markdown, other JSON and a notice backup remain excluded. The complete28-case check passes. In scratch copies, removing either exception makes the actual CLI exit1 naming the corresponding event and notice; compact receipts are in `trigger-mutations.json`. These verify committed ordered configuration, not delivery of a synthetic GitHub event.

Final focused rerun: `npm test`1250 pass/0 fail; workflow118 self-tests and6workflow/19job normal checks; minute self-test/rules; actionlint; shared visual/audit check,28 path cases and browser wiring all exit0. Shared visual gate measured3.968s, below its unchanged10-second cap. Each exit is captured individually under `verifier-status.json` review-remediation. Initial sandbox runs could not open the visual test's loopback listener or write Vite's managed-worktree temporary config (two npm tests); these are explicitly failed attempts. Scoped permission reruns completed all checks successfully.

This correction changes only workflow event routing, its ordered-path regression data and execution evidence. Product source, Docker context/configuration, CSP, fonts, test geometry and browser suites are byte-unchanged from f76e6a9f. Retain that revision's actual author and independent production/browser evidence for those unchanged paths; no new browser execution is claimed here. Root confirmed that revision's hosted marketing job126339030128 succeeded at02:15:40UTC with production build/CSP step02:13:13–02:15:38 (145s), within the unchanged15-minute job budget. Corrected-head CI and four refreshed reviews remain required before merge.

Fresh-main integration: fetched main `b3ae75f824fe8e43b18836d3d661dc996dce98bc` (reviewed uv PR351) and merged normally without conflicts. The PR diff against that target excludes uv's files. Re-ran all affected controls on the integrated source:1250 npm tests/0 failures;118 workflow self-tests;6workflow/20job normal controls; minute self-test/rules; actionlint;28 ordered path cases and all existing browser wiring; shared visual self-test206 checks/0FAIL plus fidelity controls. Shared gate3.618s (<10s). Every command individually exited0; compact exits/timings are in verifier-status.json postmerge-main-b3ae75f8. No source, dist or verifier process remains mutable/running at handoff. A final documentation-only receipt commit does not change tested executable inputs.

## Final proxy-guard compatibility correction — iteration5

Actual corrected-source CI41760267170/job126346113177 failed five existing API tests. The new shared server include hid directives from the existing fail-closed proxy guard. Reproduced locally using this worktree's actual locked uv environment:5 failed/23 passed. The focused marketing header-layout regression was also RED (3 pass/1 fail) before changing production config. This was a real integration defect, not a flaky browser or service failure.

The final nginx configuration repeats the same five security directives inline at server and asset scopes. All values and always semantics compare identically with the old policy; asset Cache-Control behavior and the trusted forwarded-proto map/header remain unchanged. Remove the unused include file, Docker COPY and allowlist entry. The existing API parser/tests are byte-unchanged from main and still reject all six quoted/header/map/server-include bypass cases, including uppercase/mixed-case overrides. The new focused marketing check compares both inline policies; real scratch CLI mutants changing only the asset CSP or removing asset nosniff fail it. Compact RED/GREEN and mutation receipts: `proxy-guard-regression.json`.

Root explicitly authorized one additional bounded iteration5 after the actual CI failure, saved/read back In Progress and posted its remediation start. The Goal Contract now has maximum5 and retains iterations1–4. Integrated main13bb3c25 normally, preserving reviewed uv and Home controls. One preparatory editor command initially used a wrong relative path and made no edit; corrected it before the focused RED. One follow-up npm invocation from repository root exited254 (no package manifest); the actual final make marketing-check target then passed. Neither invocation is counted as passing verification.

| Final verifier | Actual result |
|---|---|
| Existing API nginx proxy file in locked uv environment | exit0,28 passed, all bypass/benign cases retained |
| make marketing-check | exit0, typecheck/lint/build and1250 tests/0 failures |
| Workflow self-test and normal controls | exit0,118 cases and6workflows/20jobs |
| CI-minute self-test/rules, actionlint | each exit0 |
| Visual/shared gate and notice routing | exit0,28 path cases, existing browser wiring/shared controls |
| Actual Docker build and nginx -t | exit0; image config byte-matches final source; unused include absent |
| Shipping production CSP Chromium/WebKit | exit0,68 routes each; real fonts/auth/mobile/header/error and inline-script refusal;149.440s local total |
| Review-owned production container stop | exit0, removed after verifier |

The final production output replaces production-csp.txt; individual exits/timings are under verifier-status.json iteration5. All local verifier processes and the container completed. No new API dependencies, schema, parser exceptions, product CSS, geometry tolerance, browser/runner version or CI timeout changes. Root must now refresh all four independent reviews against the final immutable source/target and obtain actual current CI before merge, main verification and QA. Earlier actual hosted success at d17/f76 does not override the later API failure or approve this correction.
