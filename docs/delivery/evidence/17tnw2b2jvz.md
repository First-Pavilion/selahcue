# API-driven Home and Pricing — 17tnw2b2jvz

Task: https://app.clickup.com/t/17tnw2b2jvz. Branch: `codex/17tnw2b2jvz-api-cards`.
Initial source base: reviewed main `85f1fbe7ef9cd12f91e8b698dd8b1db6a64770a7`, normally fast-forwarded from initial `013a84bc`. Current target `2f4dcc25dfe401ceff7cabb7eafb584e9d2eb194` was normally merged, preserving its reviewed App.vue/footer and responsive resolved-child wait. Primary checkout and its user-owned mobile lock were untouched. Root owns independent review, target freshness, hosted CI, merge and verified QA status.

**BLOCKED for full acceptance.** Current-target legal fixture remediation passes419/419 and a real unrelated aborted request still fails its unchanged guard. Current make1256/Home262/core304/Chromium2379 gates pass. The current catalogue matrix completed only7scenarios before a hidden desktop-link click at native WebKit768; full WebKit responsive separately exited2 on375px `/affiliates/payouts` with the unchanged20second navigation deadline (cause UNKNOWN). A visible-control helper attempt then failed its focused sheet-link positive and was explicitly rolled back, without a full matrix retry. Historical476/12 is not presented as a current whole-matrix pass after the relevant footer target change. Backend PR366/shipping HTTP/admin E2E also remains blocked. Maximum6 is exhausted; no merge/QA/completion follows. Root owns four independent reviews and actual current hosted CI.

## Resulting behavior

Both views use `CataloguePlans`, which fetches same-origin `GET /v1/catalogue/plans` on mount/retry with credentials omitted, browser caching disabled and redirects refused. It has one lifecycle-owned request, a10second deadline, generation checks, abort-on-unmount and no persistent data cache. Retry clears prior data. Loading is announced; failures show only a fixed unavailable message and real Retry control. Empty and explicitly unpriced data are distinct. An HTML/error body is never rendered, and its unread stream is cancelled.

The projection validates exact public keys and types, unique plan keys/offer pairs, finite safe weekly counts, coherent price states and the API's64plan/128offer/1MiB bounds. Streaming stops and cancels above1MiB. Price amounts remain decimal strings through display: zero, null and maximum signed64-bit amounts are not rounded or conflated. The API's currency/exponent/interval drives each offer. No arbitrary currency or commercial interval is selected.

Existing `PricingCard` is reused through an optional price slot; existing callers/legacy props remain compatible. Long API labels wrap at the card heading without hiding overflow. The existing one-column below1200px/three-column desktop layout is retained. A plan with multiple actual priced intervals enables the existing keyboard radio group; default **All intervals** preserves every configured offer/currency. Absent interval prices say so. Comparison tables are omitted; the public weekly allowances/watermark are in each card, and no undecided device/output/NDI value is inferred. There is no description/popularity/destination in the current wire: none is invented, and checkout is an explained disabled **Not available yet** button.

Names and commercial values are not typed into Home/Pricing or their copy ledgers. Exact browser card-copy ledgers derive every displayed line from supplied API data plus reviewed static labels, using independent Python integer formatting. A real planted unsupported claim must be rejected. Existing static claim bans/controls remain. The obsolete dormant literal Pro-first assertion is replaced with exact API visual order, using actual card rectangles; no popularity flag exists in the wire. The old one-column tablet geometry assertion remains active. Home's obsolete unpublished FAQ answer now directs visitors to the current cards rather than claiming backend publication state.

## Historical initial-source evidence (fe07)

All listed completed commands finished and their processes were reaped. Local synthetic HTTP fixtures intentionally use different names/allowances from the seed catalogue and contain no customer/account/provider data.

| Verifier | Actual result |
| --- | --- |
| Initial unchanged baseline `npm test` |1250passed,0failed,0skipped |
| Real SSR loading behavior before implementation | RED: Home has no announced catalogue loading state |
| Real SSR loading after implementation | GREEN; both views announce loading without fabricated plans |
| Parser/format/transport regression tests |6passed; zero/null,0/2/3/4 exponents, maximum64-bit, alternate values, malformed/private data, duplicate/oversize/degraded responses, exact public request, unread-body cancellation |
| Unread error-stream control before fix | RED: actual cancellationfalse when requiredtrue; after fix GREEN |
| Current `make marketing-check` |1256passed,0failed,0skipped; type-check/lint/build all exit0 |
| Final serialized catalogue matrix, both engines |476checks,12engine/path/width scenarios PASS; Home and Pricing at320/768/1440 |
| Final serialized Home both-engine gate |262checks,0failed; both engines131each; strict frame8assertions, five nominal widths, five zero-overflow positives and15real1/12/24px overflow negatives PASS |
| Final serialized core both-engine gate |304checks,0failed; original strict geometry,20nominal windows and20real overflow negatives PASS |
| Current Chromium complete responsive suite |2379checks over41routes ×5widths,0failed; all boundary/nav/footer/overlay checks retained |
| WebKit complete responsive suite | **BLOCKED**, exit2; final375px `/signin` navigation deadline20seconds. No full-suite pass |
| Python syntax and whitespace | all changed Python modules compile with owned bytecode cache; `git diff --check` passes |
| Production freeze/parity |144source/package inputs unchanged throughout final set; all117current default bundle files, including index/hashed assets, match the earlier immutable artifact used for Chromium. That external directory also retained51older extras; no whole-directory identity claim |

The final matrix covers actual loading before response, response-only card names/allowances, exact copy with a planted-claim negative, unavailable/HTML redaction and Retry/empty, changed data without rebuilding, escaped HTML-like labels with no injected image/execution, all currency offers, zero/null/max64-bit amounts, conditional interval switching and missing intervals, disabled CTA/description, long-label overflow and actual CSS-removal RED/restoration controls, plus observation that the real fetch signal aborts only after the destination view mounts. It is now chained into the existing `npm run test:core` command so hosted CI will exercise it; a missing engine is a failure.

## Failed attempts and correction boundaries

- First loopback launch was sandbox-denied before browser assertions; an authorized loopback/browser escalation executed it. The retained preimplementation bundle then failed the missing loading behavior.
- Early unit ledger checks caught the obsolete FAQ answer and a positive-control assumption that every sentence ends with a period. Exact copy and the ellipsis-aware rewording control were corrected; no claim ban was removed.
- Initial browser navigation attempted a hidden desktop link on mobile. It now uses the actual mobile menu. The first abort observer waited on an old route h1; it now waits for the real Features root before asserting signal cancellation.
- Actual320px long-label overflow failed before the name-wrapping correction. Removing that correction in the actual browser must reproduce overflow, then restoration must recover.
- Initial responsive source used two tablet columns; the established one-column contract caught it and production CSS was corrected. The API-order check supersedes hardcoded Pro-first behavior; it is not a check removal.
- An initial core frame subprocess timed out while a rebuild overlapped its run. Precise cause was not established; it is not counted passed. The final serialized complete core gate passed with a stable bundle.
- Package-script CI wiring caused the stale-build validator to reject an older bundle; the validator was not bypassed. Subsequent builds were current. A WebKit768px diagnostic captured native1254px logo images before styling was ready, so the harness now awaits actual page assets before measuring; strict overflow checks remain. A later retry-state observation timed out with unknown cause. A focused unchanged-source WebKit768px scenario passed39checks, and the final complete serialized476check matrix passed. Neither pass proves the earlier timeout's cause.
- The earlier WebKit responsive INFRA and final serialized WebKit INFRA remain unresolved. No deadline, performance budget, claim policy, CSP, engine version or required assertion was weakened, and there was no further retry after the final authorized set.

## Evidence receipts and remaining owners

Complete local logs are retained under `/private/tmp/17tnw2b2jvz-*`; compact final matrix receipt is committed beside this document. Root can inspect exact final logs `-marketing-check-final.log`, `-final-matrix.log`, `-final-home.log`, `-final-core.log`, `-responsive-chromium-final.log` and `-final-webkit-responsive.log`. These local paths are not public artifact URLs. The goal records all four iterations and the blocked acceptance rows.

Root explicitly authorized necessary implementation while ClickUp connector quota and native CDP inputs prevented a verified In Progress write. Exact proposed native updates are local `/private/tmp/17tnw2b2jvz-clickup-start.md` and `-clickup-handoff.md`; neither is claimed saved. Root owns backfill/readback when access recovers. The prerequisite remains https://app.clickup.com/t/17tnw2b2jvy /PR366, with actual admin E2E dependency17tnw2az0gg/real staff sign-in. No API, proxy, permissions, App.vue/footer, dependencies/lockfiles, workflow YAML, provider, deployment or installer operation was changed by this ticket.

Next steps: diagnose the exact WebKit full-sweep navigation failure with a new explicit bounded disposition, finish the existing backend acceptance dependency, then all four independent reviews and actual current hosted CI. Only verified merged main permits QA. Rollback is this isolated frontend commit; there is no data/schema change.

## Current target and review remediation (iterations5–6)

Shadow confirmed actual hosted legal41848524912/job126638280109:417passed2failed/419, both Privacy/Terms→Pricing navigation-console guards reported the new catalogue `net::ERR_ABORTED`. The legal SpaHandler returned SPAHTML for the newly mounted GET, and production correctly refused/cancelled it. A deterministic actual-browser response probe failed before the fix: GET200/text-html/index989bytes rather than application/json. This establishes the missing fixture; precise hosted abort scheduling was not claimed reproduced.

`legal_pages_headless.py` now supplies the existing shared synthetic public-wire fixture **only** for localhost HTTPGET `/v1/catalogue/plans` without query/fragment, with JSON/no-store/nosniff headers. Other localhost requests continue normally. Pricing readiness is observed before the existing legal navigation/error and observer checks. Console, pageerror and requestfailed listeners and their assertions are unchanged. No ERR_ABORTED exception/filter, error clearing, policy/content/CSP/budget/engine/dependency or production-loader cancellation change occurred.

The new `scripts/legal_catalogue_guard_regression.py` drives the actual harness and browser. Its positive verifies exact GET JSON, consumed cards and clean guards. Its negative injects a REAL unrelated `/unrelated-request-negative` fetch aborted at the transport boundary with `net::ERR_ABORTED`; the ORIGINAL Privacy navigation-console assertion must fail and its detail must include `requestfailed:` and that URL/error. This is an expected rejection, not a fabricated error-list append or a passing legal suite with ignored errors.

| Current-target verifier, serialized frozen set | Actual completed result |
| --- | --- |
| `make marketing-check` |1256passed,0failed,0skipped; lint/type-check/build exit0 |
| `SELAHCUE_HEADLESS_REQUIRE=1 python3 scripts/legal_pages_headless.py` |419passed,0failed,419checks; original count retained |
| `python3 scripts/legal_catalogue_guard_regression.py --output ...` | exact JSON/readinessPASS; actual unrelatedERR_ABORTED rejected by original guard; proof exit0 |
| Current-target catalogue matrix | **INCOMPLETE/FAIL**,7scenarios completed (all six Chromium +WebKitHome320); WebKitHome768 chose hidden desktop link at30s. No476/12 current pass |
| Home both engines +frame |262checks0failed and all original strict/nominal/real-overflow controlsPASS |
| Core both engines +frame |304checks0failed,20nominal/20real negative controlsPASS |
| Complete Chromium responsive |2379checks/41routes×5widths,0failed |
| Complete WebKit responsive | **BLOCKED**, exit2 on375px `/affiliates/payouts`, Page.goto20s. Exact causeUNKNOWN; no retry |

Read-only probe after the set: requested/innerWidth768, actual clientWidth756, mobile mediaTRUE, desktop displaynone and zerorect, actual Menuvisible, navbar69px. Screenshot was inspected; there was no click/style/viewport change. The old matrix helper's nominalwidth condition is therefore an evidenced test bug. Root authorized explicit maximum5→6 for one narrow correction/proof, with all earlier ledgers retained. Restoring the old helper in a scratch matrix reproduced hidden-desktop failure. The proposed visible-control helper opened Menu, but normal sheet Pricing click reported outsideviewport then detached; the focused positive FAILED. No full matrix/retry or production fix followed. Scroll-lock/breakpoint interaction is a hypothesis, not a confirmed cause.

Root then explicitly ordered cleanup: revert ONLY the unverified helper conditional, exclude its failed proof from the public patch, preserve both under `/private/tmp` with all failure receipts, and publish the independently verified legal fix/proof. This is cleanup, not a seventh iteration. The original nominal helper and observed native768 sheet issue remain visible C003/C008 blockers. The current actual WebKit fullsweep Page.goto failure is separate and unexplained. All219 inputs captured before the serialized set match again after the owned helper rollback. All browser/server/subprocesses finished; no new build or test after cleanup. The production API component/view/transport files are byte-unchanged by the remediation; the only new app input was the already-reviewed target footer, which was rebuilt and tested explicitly.

Compact current legal guard receipt and gate metadata are committed beside this document; full local receipts use `/private/tmp/17tnw2b2jvz-it5-*`, `-it6-navigation*` and `-nav768.*`. Historical full476 JSON remains labelled original fe07 evidence; it is not substituted for the current incomplete matrix. Native In Progress write remains pending external recovery, never claimed saved. Root owns new four reviews/current hostedCI and all remaining acceptance/main/QA decisions. Backend C005 remains blocked regardless of local source checks.
