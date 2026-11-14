# Public release browser gates — 2026-11-14

Source baseline: `40661b4fde38f1e670bc8fde522c17b30bdb93a7`. The [hosted marketing job](https://github.com/First-Pavilion/selahcue/actions/runs/43599653181/job/132461514543) ran on Ubuntu 26.04.1 x64, Python 3.14.10 and Playwright 1.61.0 (WebKit 26.5 revision 2311; Chromium 149.0.7827.55).

- **Responsive WebKit, `/blog`, 375×800:** navigation returned at 74 ms and the real route content was visible at 218 ms. The 10-second `wait_for_function` timed out before geometry checks. Resources shown in the trace returned 200, with no reported page error. The only animation sample came at 1 ms, before content rendered: `readyState=loading`, no animations, no completed animation frame, `rafPending=false`. The successful detail-route control also recorded only its pre-content sample. The failure gives no evidence of a particular running animation or stopped frame; losing renderer timers, losing console delivery, and a finite animation keeping the predicate false remain distinct possibilities. A route-load timeout is excluded for this run. The earlier macOS failure on `/blog/no-such-post` during navigation was at a different stage.
- **Secondary WebKit, `/contact`, 800 px high:** keyboard focus reached the email link after skipping disabled Send, but the link's top was 40 px under the 79 px sticky navbar. Chromium passed the same check. The page supplies a per-element scroll margin (95 px locally); on unchanged macOS WebKit 26.5, the same hidden link moved from 40 px to 95 px on Option+Tab. The local behavior does not explain the Linux failure by itself.

The responsive diagnostic records a compact marker on the first settlement poll. It includes the predicate result, elapsed time, poll count and frame heartbeat. The periodic observer records animation state, uses recognized labels and opaque per-document target IDs, and validates console payloads before logging them. The marker has its own slot and survives output trimming. The contact assertion records scroll position before and after Tab, computed scroll margin, viewport width and whether the browser marked the element as keyboard focused.

The focused tests observed three animation scans within the original first poll and verified that the revised poll scans once. The browser test with a planted private animation name and target identifiers reproduced the original exposure and verified the revised redaction. The long-animation timeout now runs on its own page and confirms that the timed-out wait produced its own poll and frame evidence.

Local commands from `implementation/marketing` (macOS 26.3 arm64; Node 26.7.0/npm 11.19.0; Python 3.14 and Playwright 1.61.0; `SELAHCUE_SWEEP_REQUIRE=1 SELAHCUE_HEADLESS_REQUIRE=1`):

| Command | Result |
| --- | --- |
| `npm test` | 1,250 passed; zero failed or skipped |
| `npm run lint` | Passed with zero warnings |
| `npm run build` | Passed; type-check and production Vite build |
| `python3 tests/responsive_diagnostic_regression.py` | 12 passed after review (WebKit 26.5) |
| `python3 scripts/responsive_sweep.py --engine webkit --widths 375 --routes /blog` | 33 checks across the blog index and two article cells, zero failed after review (WebKit 26.5) |
| `python3 scripts/responsive_sweep.py --engine chromium` | 2,363 checks, 41 routes × 5 widths, zero failed (149.0.7827.55) |
| `python3 scripts/responsive_sweep.py --engine webkit` | 2,363 checks, 41 routes × 5 widths, zero failed (26.5) |
| `python3 tests/secondary_pages_headless.py --engine both` | Chromium 183 and WebKit 179 checks, zero failed; original WebKit forced-colors skip |

Before the first marker was minimized, the successful local WebKit `/blog` cell first saw three running 200 ms header transitions (prefixed and unprefixed backdrop filter, and background color), then settled after 196 ms. The revised focused run again settled locally and recorded the first false predicate result at 161 ms, with one completed heartbeat. The hosted timeout trace lacks evidence about whether those transitions were active. No Vue/CSS or browser-gate behavior was changed. The Ubuntu 26.04 Playwright image transfer did not complete within this investigation; there is no local Linux reproduction or causal fix for either hosted failure. The hosted browser gates remain unresolved pending independently reviewed Linux evidence.

## Hosted Linux follow-up

[Marketing run 43603654800](https://github.com/First-Pavilion/selahcue/actions/runs/43603654800) tested `1059e697`. The 375 px `/blog` cell settled. The responsive sweep later timed out at `/admin/payouts` at 1440×800. Content was visible at 252 ms, and the first settlement poll returned false at 253 ms with one completed animation frame. The trace has no subsequent timer sample. It cannot distinguish a stalled frame callback, an animation whose predicate stayed false, or an interruption in the renderer or console event delivery.

On Contact at both 700 and 800 px, Linux WebKit set keyboard focus on the email link and left the page at `scrollY=452`. The link remained at 40 px under the 79 px sticky navbar with a computed 95 px scroll margin. The email link now checks the navbar's position on the next animation frame and scrolls it clear if keyboard focus remains on the covered link. Blur and unmount cancel the scheduled check.

The responsive diagnostic now also records the first frame-driven poll and one independent timer marker scheduled 100 ms after a false first poll. The three markers have fixed labels, bounded scalar fields, and at most one entry each. The predicate still uses Playwright's frame polling with the original 10-second deadline. In the local settled `/blog` cell the first poll returned false at 91 ms, poll two ran at 100 ms, and the independent timer recorded poll seven at 192 ms. A missing marker can still reflect failed console delivery.

| Local command from `implementation/marketing` | Result |
| --- | --- |
| `python3 tests/secondary_pages_headless.py --engine both --only contact-focus-fallback` against the original build | One expected failure per engine. With native focus scroll suppressed, the link stayed at 40 px under the 79 px navbar |
| `npm run build` and `npm run lint` | Passed |
| `node --test tests/secondaryPages.test.ts` | 186 passed |
| `python3 tests/secondary_pages_headless.py --engine both` | Chromium 189 and WebKit 185 checks passed, with the existing WebKit forced-colors skip. Includes the original keyboard assertions and fallback cases |
| `python3 tests/responsive_diagnostic_regression.py` | 13 passed on WebKit 26.5 |
| `python3 scripts/responsive_sweep.py --engine webkit --widths 1440 --routes /admin/payouts` | 10 checks passed on WebKit 26.5 |
| `python3 scripts/responsive_sweep.py --engine webkit --widths 375 --routes /blog` | 33 checks passed on WebKit 26.5 |

All browser checks used macOS 26.3 arm64, Python 3.14.5 and Playwright 1.61.0, with the required-engine environment variables set for the acceptance scripts. The Contact change awaits the original keyboard check on Linux. The responsive timeout remains unresolved.

## Recurrent responsive settlement timeout

[Full CI run 43610134102](https://github.com/First-Pavilion/selahcue/actions/runs/43610134102) at `c40990f7` failed the marketing job. The responsive Chromium sweep passed 2,363 checks. The later shared component, core, home and secondary browser suites passed, including Contact. WebKit 26.5 revision 2311 timed out at `/this-route-does-not-exist` at 1440×800 on Ubuntu 26.04.1 x64, Python 3.14.10 and Playwright 1.61.0. The document and local asset responses completed by 90 ms, including the loaded 404 view and stylesheet. The `/css2` request failure matches the deliberate external font stub. Route content was visible at 233 ms. The first actual predicate was false at 234 ms, the first frame callback also returned false at 272 ms, and the independent timer reported that the count was still two at 334 ms. The 10-second wait timed out before geometry. No page errors were reported. Only the pre-content snapshot arrived, with no samples dropped or observer errors recorded. The previous hosted failure was `/admin/payouts` at the same width in run 43603654800. Hosted run 43605891632 passed the full matrix.

The pinned Playwright driver evaluates the predicate synchronously before scheduling the next native `requestAnimationFrame` callback on each false result. One frame callback and one timer prove those callbacks ran. Neither establishes that the main thread, frame scheduler, observer or console delivery continued. A finite animation may keep the predicate false while polls advance. The route snapshot did not enumerate animations after content loaded, so it cannot implicate a particular animation or component. The first periodic observer callback calls animation APIs before emitting a snapshot, and `pagehide` intentionally stops the observer. Both are gaps in the old evidence.

The diagnostic now emits a scalar marker before the existing periodic animation read while the wait is still pending, and schedules one independent scalar timer 1.25 s after the first false poll. Marker records include the document visibility enum. The existing `pagehide` listener emits one marker immediately before stopping observation. The per-document marker slots and output byte cap still apply. The browser still runs the same animation predicate on the same frame scheduler and deadline. This adds no reads of layout or animation state to the gate.

On a reproduced failure, increasing poll counts plus a false rich snapshot would prioritize inspecting animation identity and timeline progress. A late marker with a frozen count establishes continued timer and console activity during a wait. A periodic-start marker with no subsequent rich snapshot localizes the gap to the read, serialization or delivery of that snapshot. A pagehide marker accounts for intentional observer shutdown, and its visibility field helps interpret lost frames. If all new signals remain absent, the trace still cannot distinguish a blocked renderer, suspended timer execution and lost protocol delivery. No hosted cause has been confirmed.

With the final marker changes, macOS WebKit 26.5 passed all 15 diagnostic controls and 20 real geometry checks across the reported 1440 px `/admin/payouts` and `/this-route-does-not-exist` cells. The earlier version with pending-wait markers passed all 2,363 local WebKit checks. The pinned Linux AMD64 container download did not finish, leaving exact-host reproduction and the cause of the timeout open.
