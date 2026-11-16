# Home layout viewport CI unblock — 17tnw2bcadw

Current integrated base main: b3ae75f824fe8e43b18836d3d661dc996dce98bc.
Original red baseline: c0325d52e809847fac141a605b74a7e6d7de7021. Owned branch:
`codex/17tnw2bcadw-home-viewport`. Separate from PR352 hardening; no product files/CSS,
geometry values/tolerances, runner/browser versions or skip conditions change.

Root created the live High-priority ticket and saved/read back In Progress with a visible
start comment beginning “Farah started the focused Home layout-viewport CI fix”. Root
owns ClickUp UI writes while its connector quota is exhausted; no connector retry here.

## Baseline and correction

PR350 [Linux job](https://github.com/First-Pavilion/selahcue/actions/runs/41756526885/job/126333884624)
showed130 Chromium checks pass and eight WebKit geometry failures. The unchanged-main
local real-DOM red probe reproduced client1428 with actual values:
`[144,1236,1428,398.65625,1428,694,393.328125,1236]`, versus strict expected
`[150,1248,1440,402.67,1440,706,397.33,1248]`. It exits1 before the fix.

Home now reuses Core's existing measured `fit_figma_frame` only for explicit1440px Figma
measurement. Its default nominal measurement remains unadjusted. Eight original strict
assertion expressions were moved verbatim into a callable used by both the normal suite
and regression; a direct before/after source comparison confirms identical expressions,
values and tolerances. All130 checks per engine remain present.

Overflow uses real document scrollWidth/clientWidth rather than outer innerWidth. The same
assertion function runs on normal pages and genuine overflow fixtures, including the
compensated1440 frame. This catches1px/12px overflow previously concealed by outer chrome.

The regression adapter reserves12 real browser-viewport pixels. A host's native scrollbar
may reserve up to12 more and can change across navigations; the test records the exact
current-load clientWidth read and proves the helper compensates that measured gap. Only
the external window boundary is adapted. Product styles and clientWidth/scrollWidth are
never replaced. A fixture-only innerWidth getter models outer chrome to demonstrate the
old comparison would miss1px/12px overflow. Zero-gap Chromium retains outer/client1440.

## Verification

Node26.7.0/npm11.19.0, Python3.14.5, Playwright1.60.0 with actual Chromium/WebKit.
A fresh npm ci --ignore-scripts and production build preceded RED. Final shared build and
browser checks ran sequentially; no concurrent dist mutation or unfinished verifier counts.

| Command or check | Actual result |
|---|---|
| Unchanged-main12px real-DOM baseline | exit1; client1428, all eight strict values fail |
| Focused frame regression | exit0; zero-gap, exact1440 strict widths, five nominal requests |
| Real overflow controls | five0px controls PASS; fifteen1px/12px/24px cases rejected by actual Home assertion; old innerWidth test demonstrably misses1px/12px |
| make marketing-check | exit0; type/lint/build and1246 tests pass |
| Home both required engines + automatic focused subprocess | exit0;130+130 checks/0 failed and focused regression PASS |
| Core both engines + existing frame/nominal-overflow regression | exit0;300 checks/0 failed,20 nominal windows and20 real overflow negatives PASS |
| Python syntax and git diff --check | both exit0 |
| Four independent reviews/current hosted Linux CI/main merge/QA | pending root gate |

See baseline-red.txt, home-green.txt and verifier-status.json. Full local outputs are
`/tmp/selahcue-home-*-final.log`. Root must obtain four independent PASS verdicts and real
current Linux CI before merge, verify main and only then save/read back QA. No deployment,
provider operation, installer dispatch or primary user mobile lockfile modification.

Final base b3ae75f824fe8e43b18836d3d661dc996dce98bc was normally fast-forward integrated,
with API uv workflow/helper/lock/dependency graph preserved. Baseline Home source blobs
on c032 and b3ae are identical (efc106a922b8cd745a332bf44751a738867fd409). All final checks
were then rerun against b3ae and finished exit0. No verifier remains running. Fresh fetch
confirmed zero commits behind main before freeze. Both-engine CI always runs the focused
subprocess after both original engines complete; original optional missing-engine and
single-engine CLI behavior is preserved. README instructions sit beside Commands so the
separate PR352 hardening README append can integrate independently.
