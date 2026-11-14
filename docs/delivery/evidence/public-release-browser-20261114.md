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
