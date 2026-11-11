# Required browser CI: Ubuntu 26 compatibility

Ticket: [17tnw2beykq](https://app.clickup.com/t/17tnw2beykq). Evidence recorded 2026-11-11.

## Failure and selected release

The pre-change [CI run 43008461665](https://github.com/First-Pavilion/selahcue/actions/runs/43008461665), head `62c9e1ea`, used Ubuntu 26.04 image `20261101.186`. The marketing job `130481899591` rejected installation with `ERROR: Playwright does not support chromium on ubuntu26.04-x64`; the operator job `130481899556` also failed WebKit installation. The original marketing log is retained locally at `/private/tmp/sqlite-native-marketing-failure.log`. Subsequent missing-browser failures were required-gate failures, not successful browser coverage.

Select exact Python package **`playwright==1.61.0`**: the first stable release in the minor line whose [official Python release notes](https://playwright.dev/python/docs/release-notes#version-161) introduce Ubuntu 26.04 support. The [published PyPI 1.61.0 metadata](https://pypi.org/pypi/playwright/1.61.0/json) confirms version `1.61.0`, not yanked, Python `>=3.10`, and a Linux x86-64 wheel uploaded `2026-06-29T10:32:59.903990Z`. This is the smallest supported minor update from `1.60.0`, rather than a floating latest release.

The [tagged 1.61.0 browser manifest](https://github.com/microsoft/playwright/blob/v1.61.0/packages/playwright-core/browsers.json) and release notes identify the intended bundled browsers:

| Required engine | Version | Playwright revision |
| --- | --- | --- |
| Chromium and Chromium headless shell | 149.0.7827.55 | 1228 |
| WebKit | 26.5 | 2311 |

These identities were initially verified from package/source metadata; the subsequent Ubuntu 26 installer observations below confirm them for the reviewed source head. The [tagged download registry](https://github.com/microsoft/playwright/blob/v1.61.0/packages/playwright-core/src/server/registry/index.ts) includes Ubuntu 26.04 download entries for Chromium, its headless shell and WebKit.

## Change and regression coverage

All three existing Python Playwright installations now pin `1.61.0`: operator WebKit and marketing Chromium/WebKit in `ci.yml`, and legal-drift Chromium. Existing pip options, `--with-deps`, engines, required-run flags, failure propagation, runner policy, shipping-image CSP checks and visual/content assertions are retained. No production dependencies or visual baselines changed.

The existing legal workflow contract had allowed operator and marketing to pin different versions as long as legal-drift matched either one. Its version-independent assertions now require exactly two CI pins sharing one version, legal-drift parity, and pinned pip installation lines in both workflows. With only the operator pin updated, the contract failed as intended (`2 !== 1`, eight passed/one failed). After updating the remaining pins, all nine focused tests passed.

## Local verification

Host: macOS 26.3 / arm64; Node `v22.23.4`; validation interpreter Python 3.14. Local execution does not establish Ubuntu 26 browser installation.

| Command | Observed result |
| --- | --- |
| `node --test implementation/marketing/tests/legalWorkflow.test.ts` | 9 passed, 0 failed/skipped after coordinated update |
| `python3.14 .github/scripts/check_workflows.py --self-test` | 118 legacy cases; 39 cache CLI fixtures; 0 fixture failure diagnostics |
| `python3.14 .github/scripts/check_workflows.py` | 7 workflows / 21 jobs OK |
| `python3.14 .github/scripts/check_ci_minutes.py --self-test` | All cases passed |
| `python3.14 .github/scripts/check_ci_minutes.py` | 7 workflows OK; existing runner policy retained |
| `actionlint` | Exit 0, no diagnostics |
| `make marketing-install` | Exit 0; 188 packages installed from existing lockfile |
| `make marketing-check` | Exit 0: type-check, lint, all 1,250 Node tests in 250 suites, production build; 0 failures/skips |
| `git diff --check` | Exit 0 |

The full marketing-gate log is retained locally at `/private/tmp/sermon-pilot-browser-marketing-check.log`. Node emitted its MockTimers experimental warning and the malformed-URL fixture emitted Vue Router decoding diagnostics; the suite still reported zero failures. Installation reported 11 moderate npm audit findings in the existing dependency tree; no dependency remediation is part of this pin change.

## Native verification of the pin update

Independent Quinn verification inspected the completed logs and authenticated metadata for reviewed source head `9b1f58b58929b7303e6726c677c64e173b1c68a1`, base `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`, [PR 384](https://github.com/First-Pavilion/selahcue/pull/384). These jobs executed PR merge checkout `4928496` combining that source and base, on Ubuntu `26.04`, image `20261101.186.1`. Marketing and legal logs establish Python `3.14.10`; the operator log establishes CPython 3.14 wheel compatibility, with its exact Python patch version unverified.

- [Legal-drift run 43021502436](https://github.com/First-Pavilion/selahcue/actions/runs/43021502436), job `130525563475`: successful pinned installation and Chromium/headless-shell **149.0.7827.55, build 1228** downloads; required legal-page browser suite **419 passed, 0 failed**.
- [CI run 43021502286](https://github.com/First-Pavilion/selahcue/actions/runs/43021502286), operator job `130525654339`: installed package output explicitly reports `playwright-1.61.0`; Ubuntu 26 WebKit **26.5, build 2311** download succeeded; required operator headless script **2,906 checks, 0 FAIL**, and required WebKit smoke **44 checks, 0 FAIL**. The headless script count includes its static/fake-browser controls, not 2,906 separate end-to-end journeys.
- Same CI run, marketing job `130525654194`: successful pinned installation and both Chromium/headless-shell **149.0.7827.55 / build 1228** and Ubuntu 26 WebKit **26.5 / build 2311** downloads. These are observed installer identities; no separate browser-process version query is logged. Quiet pip in marketing/legal does not print a separate installed-package listing.

Completed marketing results before timeout:

| Required execution | Observed result |
| --- | --- |
| Auth states, before Playwright installation | 77 scenarios / 2,765 checks, 0 FAIL; does not establish the new bundled engines |
| Responsive Chromium | 2,363 checks over 41 routes × 5 widths, 0 failed |
| Responsive WebKit | 2,363 checks over 41 routes × 5 widths, 0 failed |
| Shared components, both engines | 324 Chromium + 322 WebKit checks, 0 failure lines; WebKit forced-colors box-shadow assertion explicitly skipped because unsupported, not passed |
| Menu breakpoint regression, both engines | PASS, 93 checks across Chromium/WebKit at widths 320/768 |
| Core pages, both engines | 300 checks, 0 failed |
| Core frame/overflow regression | PASS: exact geometry, 20 nominal widths, 20 overflow negatives |
| Home, both engines | Interrupted by timeout; no completed result or count |
| Secondary pages, both engines | Skipped after cancellation; no execution/count |
| Shipping-image security headers/CSP, both engines | Skipped after cancellation; no execution/count |

Marketing started `12:34:40Z` and completed/cancelled at `12:49:56Z`. The check annotation explicitly states that the job exceeded its **15m0s** maximum. Cancellation occurred at `12:49:53.3276062Z` while home was running. This is incomplete required coverage, not an observed failed product assertion or evidence that the pin update caused a slowdown. The full CI run completed/failure; its separate RustSec audit job also failed, with cause/provenance outside this browser investigation.

Completed logs: `/private/tmp/selahcue-browser-legal-9b1f58b5.log`, `/private/tmp/selahcue-browser-operator-9b1f58b5.log`, `/private/tmp/selahcue-browser-marketing-9b1f58b5.log`. Independent review records: `browser-native-verification.md` and `browser-ci-timing-followup.md` under the session artifact directory `/Users/m.oluwole/.codex/visualizations/2026/11/11/01a1c999-1923-7970-83c1-650fe3817d16/`.

## Fix round 1: finite marketing measurement window

Vera's timestamp analysis measured approximately **52s installation, 84s Chromium sweep, 228s WebKit sweep, 94s components/menu and 118s core**. Home began **14m17s** into the job. The observed duplicate builds cost about 38s total; removing them does not establish sufficient tail headroom. No comparable successful baseline establishes a pin-induced performance change.

The controller approved one functional change from reviewed head `9b1f58b5`: marketing job `timeout-minutes` **15 → 20**. Every serial command, engine, required flag, assertion, build, output, job/runner/trigger/matrix and other timeout remains unchanged. This adds at most **five configured Linux runner-minutes of exposure per marketing execution**; actual billed rounding/cleanup can differ. Twenty minutes is a finite measurement cap, not a prediction that home, secondary and shipping-image CSP will complete.

Fix-round local checks: workflow self-test (118 legacy cases, 39 cache CLI fixtures), workflow validation (7 workflows / 21 jobs), runner-policy self-test/validation (7 workflows), actionlint, and existing legal/security workflow contracts (13 tests, 0 failures/skips) passed. Semantic comparison against `9b1f58b5` confirmed that only the marketing job timeout changed in parsed workflow data. The 1,250-test Node gate was not repeated for this timeout/documentation-only change; its earlier result remains scoped to `9b1f58b5`.

The controller owns four-role re-review and **one** exact-new-head hosted measurement. Full marketing browser/CSP completion remains **blocked pending that execution**. Record actual head, runner image, step durations/counts/outcomes and installed engine identities. If the twenty-minute cap is exhausted or any required suite remains incomplete, retain the block and report the measured tail; do not retry blindly, increase the cap automatically or adjust visual baselines. Legal/operator native passes above remain explicitly scoped to their reviewed head's PR merge. No merge, release, QA completion or overall green CI is claimed.


## Legal sticky diagnostic continuation

The subsequent [legal-drift run 43028035092](https://github.com/First-Pavilion/selahcue/actions/runs/43028035092), job `130547604794`, source `762c86d770d5b0c36b94a187b573fe473703a10f` / PR merge `8c62fa3`, installed Chromium successfully but failed **418 passed / 1 failed / 419 checks**. The failure is `privacy@1024: sidebar is sticky below the navbar`, TOC top `796.6875` outside the unchanged navbar-relative `79..120` window. No CI root-scroll measurement exists at that failed instant. This supersedes the older legal pass for current gate status; it does not establish a layout cause or a flaky test.

The diagnostic continuation adds only passive, bounded `STICKY_TRACE` JSON at the original desktop checkpoint. Existing pre/post TOC evaluation calls now also capture root position/range, navbar and TOC rectangles, TOC scroll dimensions, relevant ancestor position/overflow/transform/contain, and wheel coordinates/deltas/fixed target-region labels/final observable cancellation. It retains at most **4 wheel events**, **10 ancestors per snapshot**, **32 characters per computed-style/tag string**, and **12,000 JSON characters per checkpoint** (plus the fixed log prefix). Oversize output falls back to valid JSON retaining root/TOC geometry. No text, full DOM, arbitrary attribute values, environment or credentials are logged. The capture listener is passive and removed after the original post-wheel read; no timer, extra evaluation checkpoint, scroll, input, assertion retry or longer wait is added.

Local validation used pinned Playwright **1.61.0**, Python **3.14.5**, existing unchanged production `dist/`, and the unchanged launch resolver's system **Chrome 157.0.8103.40 on macOS 26.3 arm64**. The complete legal suite passed **419/0**, including all four original desktop sticky assertions and the existing route/width/anchor matrix. The four traces were 5,549–5,671 characters including prefix, and recorded rootY `0→1600`, TOC top `88`, a `(0,0)` navbar-region wheel hit and `defaultPrevented=false`. A temporary no-wheel negative control preserved the original geometry assertion and failed at top `796.6875`, with rootY `0→0` and an empty wheel record. An oversize-output control produced valid bounded fallback JSON with root/TOC geometry intact. Python syntax, unchanged existing assertion/wheel/wait/width AST comparisons and diff checks passed. No broad marketing/operator suite was rerun.

Validation artifacts are under `/Users/m.oluwole/.codex/visualizations/2026/11/11/01a1c999-1923-7970-83c1-650fe3817d16/sticky-telemetry-validation/`, including full/negative logs, parsed traces and the temporary runner. These are local telemetry checks, **not Ubuntu 26 / Chromium 149 acceptance or a claimed repair**. Instrumentation can affect scheduling; an instrumented pass alone cannot prove root cause. The source leaves every original wheel action, 400ms wait, geometry bound, route, width, failure exit and product/workflow/dependency input unchanged. Four-role scoped review must precede the controller's normal push; no manual CI rerun or release was performed or authorized by this continuation.


## Selected-browser launch provenance

The Chromium **149.0.7827.55 / build 1228** identities in the earlier CI records are **installed Playwright bundle identities**. Those records did not query the selected browser object's process version. The unchanged resolver can select a system Chrome channel before falling back to bundled Chromium; neither installation success nor local Chrome157 observations establish which process version those earlier Ubuntu jobs actually selected.

Immediately after successful launch, before page execution and outside the sticky checkpoint, the script now emits one content-free `BROWSER_IDENTITY` JSON line from the selected object's existing `browser_type.name` and `version` APIs. Engine/version strings are capped at **16/64 characters** and ASCII-escaped, bounding the line below **1,024 characters**. No path, environment, user agent, page content or user data is added, and launch choice remains unchanged.

The local provenance check launched the real browser through the unchanged resolver, compared the emitted fields with that same selected object, and observed `BROWSER_IDENTITY {"engine":"chromium","version":"157.0.8103.40"}`. Syntax and AST invariants passed: all previous functions except the single metadata call in `main` are unchanged, including resolver, original wheel/wait/geometry/matrix and passive checkpoint telemetry. The prior **419/0** full legal-suite result remains scoped to telemetry head `5e54e9bb`; no unrelated suite was repeated for this metadata-only follow-up. This record adds provenance for future runs and does not repair or explain the earlier sticky failure. Actual new-head Ubuntu selected-process identity and geometry evidence remain pending controller-reviewed normal publication.


## Bounded auth initial-readiness correction

The earlier `verify-resend` observation at source `ca7bb24f` passed 52 checks locally, while a single controlled **800ms initial VerifyEmail fulfillment delay** reproduced **52 checks / 14 failures**, with no resend call. This establishes a harness readiness weakness under injected latency. The historical Ubuntu page's actual initial state/operation/fulfillment timeline remains unknown; matching failure names do not establish the same cause or a product defect.

The harness retains the original 600ms wait, then reuses unchanged `settle("This verification link didn't work")` before its original input attempt. The existing initial-state check requires the returned boolean **and the original title predicate**. Helper defaults remain 3,000ms search / 20ms polling / 120ms success grace; errors are not newly caught and timeout false is not ignored. Original typing, 50ms wait, submission, final 600ms wait and all 52 original checks remain. The helper writes shared `settledAt`; these two cases do not record elapsed branch facets and execute on fresh pages, while every existing helper caller is unchanged.

Exactly one normal-suite regression, `verify-resend-delayed`, aliases the original scenario body and delegates replies to the original reply function. Only its named initial VerifyEmail response fulfillment is delayed 800ms, resolving the same unchanged Response; resend reply/body/status remain unchanged. Original 77 scenarios are retained, for 78 total. No product, API, router, workflow, pin, engine, 8,000ms virtual-time budget, 90s process limit or 20-minute job cap changed.

Meaningful local proofs used existing native **Chrome 157.0.8103.40 on macOS 26.3 arm64**, the original real freshness guard (accepted existing dist), and synthetic loopback-only fixtures. Before correction the new delayed case failed 14 of 52 checks, VerifyEmail=1 / resend=0. After correction immediate and delayed cases each passed **52/0**, VerifyEmail=1 / resend=1. A temporary never-ready initial fixture still failed the original initial-state check (**52 checks / 21 failures**, VerifyEmail=1 / resend=0), without replay/retry or process timeout. These are controlled harness checks, not new Ubuntu acceptance.

The first complete local run measured **78 scenarios / 2,817 checks / 0 behavioral failures** and exited 4 solely because the strict expected count still read 2,765. The count was updated from that completed output, preserving exact equality. The controller authorized one final complete run for the resulting source, which passed **78 scenarios / 2,817 checks / 0 failures, exit 0**. Both runs completed all 78 browser processes without timeout; the count includes the original cross-scenario comparisons, not 2,817 distinct user journeys. No blind rerun loop or count-derived assertion waiver is authorized.

Focused red/green/refusal logs and full-run receipts are retained under the session artifact directory `auth-readiness-validation/`. Python/injected-JavaScript syntax, original driver/helper/fixture invariants and original 77-case inventory checks passed. Loopback DNS/proxy confinement is a local diagnostic difference from hosted execution; timing and macOS/native-Chrome differences remain material limits. No global install, real credentials/provider, unrelated full marketing/operator suite, CI dispatch, publication or release action occurred.


## Bounded WebKit settlement observation

The subsequent required WebKit sweep at source `8103d5125761cfe2b3af802ac89681d77bd3aadc` reached `/admin/customers/cus_001` at 320px, then the original animation predicate timed out after **10,000ms**. Navigation and the visible-content selector had returned. The available log (`/private/tmp/selahcue-browser-marketing-final-8103d512.log`) lacks animation identity, poll/frame cadence and timeout-path page-error observations. Customer details use synchronous fixture data. No product, fixture or engine defect is established.

The continuation adds only passive observation on that exact WebKit route/width. A document init script records an initial sample plus at most twelve one-second samples over twelve seconds, at most twelve animations per sample, 96-character strings, explicit nonfinite timing values, readiness/DOM-presence booleans and the **unchanged** predicate result. One rAF heartbeat may be requested per sample, with at most one pending; there is no continuous extra animation loop. Python retains at most 24 fixed-category page/request events and six stage markers. Request records contain only pathname, method, resource type, status and content type; arbitrary console/error text, query strings, headers, cookies, bodies and DOM text are excluded. The existing page-error collector and assertions remain; the trace exposes its count and bounded event categories on the early-return path.

`WEBKIT_SETTLE_TRACE` JSON is ASCII-encoded and capped at **32,768 bytes**, with explicit dropped/truncated indicators. Oversize traces discard older samples first; stages and the newest bounded event ring remain. Console sample intake also rejects oversized or excess records. The renderer timer stops at twelve seconds or page teardown, and Python ignores events after its twelve-second deadline/close. Success and original infrastructure-failure paths emit already-received observations; timeout reporting makes no additional browser evaluation. Observer setup/callback/report errors cannot turn the original failure into a pass. The selected browser object's bounded engine/version are emitted once after launch as `BROWSER_IDENTITY`.

Focused local checks passed: Python syntax, injected-JavaScript syntax, five host-ledger controls, five disposable JavaScript animation/timer/rAF controls, and two original-timeout integration controls (including observer setup failure). The latter retain **exit 2**, original INFRA output and no post-timeout browser evaluation. AST comparison against `8103d512` preserves all **21 existing constants**, **11 existing non-main functions/classes**, and the complete original main body after removing only observer assignments/calls: predicate, fixtures, route/width order, navigation/selector/wait timeouts, lifecycle, interactions, assertions and exit codes are unchanged.

Exactly one local target-page control used existing Playwright **1.61.0**, selected **WebKit 26.5 / installed build 2311**, macOS arm64, unchanged existing production `dist/`, and synthetic loopback fixtures: **11 checks / 1 route × 1 width / 0 failed, exit 0**. Its trace was 4,124 JSON bytes, with 24 events, 14 explicit event drops, six stage markers, one initial sample and zero page errors/observer errors. Settlement completed at approximately 304ms; the single initial sample preceded route rendering, so it contains no post-render animation evidence. This is local diagnostic nonreproduction, not Ubuntu acceptance or proof of repair. No complete sweep, suite repetition, installation, workflow/timeout/fixture/product change or remote execution was performed. The historical cause and current-head hosted coverage remain pending the controller's four-role review and single normal publication/run.

Disposable controls, red/green logs, exact commands and limitations are retained in `.superpowers/sdd/2026-11-11-sermon-pilot-browser-ci/task-1-webkit-settle-report.md` and its `webkit-settle-validation/` directory. They add no permanent generic test framework.
