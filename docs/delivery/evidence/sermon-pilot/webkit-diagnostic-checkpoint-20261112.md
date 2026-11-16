# WebKit diagnostic checkpoint — 2026-11-12

Task base: `d00ca93351d0bde0d2dde1bbd197410eb2952075`. This change closes an observation gap; it does **not** resolve the failing WebKit acceptance gate.

All WebKit route/width cells now install the same bounded observer. Traces identify the planned route, viewport and current phase, include bounded load/DOMContentLoaded events, and emit on navigation/content/settlement failures, geometry exceptions or assertion failures. Successful cells stay quiet except customer-list/768 and the original detail/320 control. Existing page/context lifetime removes observers. The observer still stops at 12 seconds, retains at most 13 samples / 12 animations each / 24 events / 6 historical stage records, and emits at most 32,768 ASCII bytes. No arbitrary page text, console text, query strings or credentials are added.

The exact readiness predicate, all 21 existing main browser API calls/arguments, 41 routes, five widths, geometry guards, behavior checks and REQUIRE semantics are unchanged. The original 20,000ms navigation, 10,000ms visible-content and 10,000ms animation-settlement deadlines remain. No polling, reduced-motion, route/content selector, application, dependency or lifecycle correction was made.

## Source, bundle and runtime

Before editing, all 243 retained marketing file hashes matched the earlier fresh-build manifest, and all 117 production bundle files matched. Only the Python observer and new diagnostic tests change; no application/build input changed, so that production bundle was reused under the controller ruling. Full installed-lock comparison still reports zero version mismatches or missing required packages. Lock SHA-256: `de7db7264608fe201b473d4dc75c44eb688f6321ab0ceebe188b0521712dcb23`.

Diagnostic script SHA-256: `6fe2b4a8838e6d96c1490effad27b0f616caded33fe49234681787079f62ee34`. Original predicate SHA-256: `c570231d0ee66ae75bb46cd26f0d2c2b113b3d901bcf18f2ccc5b6b48bf63e30`.

Actual runtime: macOS26.3 arm64, Python3.14.5, Playwright1.61.0, WebKit26.5/revision2311, Chromium149.0.7827.55, Node26.7.0/npm11.19.0. This differs from hosted Ubuntu/Node22.

## Outcomes

Commands ran from `implementation/marketing` using `/private/tmp/selahcue-task4-venv/bin/python -B` and `SELAHCUE_SWEEP_REQUIRE=1`:

- `scripts/responsive_sweep.py --engine webkit --widths 768 --routes /admin/customers`: exit0, 20 checks / 2 routes / 1 width, 1.652s. Prefix selection includes detail; behavior checks are excluded by the existing focused CLI.
- `scripts/responsive_sweep.py --engine webkit`: **exit2**, 54.411s. The single instrumented full original-order run reproduced `/blog/no-such-post` at375×800 during `Page.goto`, timeout20,000ms. The detail320 control settled in361ms. Remaining WebKit cells and behaviors were not completed.
- `scripts/responsive_sweep.py --engine chromium`: exit0, 2,363 checks / 41 routes ×5 widths / 0 failed, 37.970s.
- Under a separate controller ruling, `scripts/responsive_sweep.py --engine webkit --widths 375 --routes /blog/no-such-post` with `DEBUG=pw:browser`: exit0, 11 checks / 1 route / 1 width / 0 failed, 1.913s. Browser log741 bytes, clean process exit0. This cold pass does not erase either original-order failure.
- `npm test`: 1,250 passed / 0 failed / 0 skipped.
- Real-WebKit regression controls cover failed-cell observation, quiet success/failure emission, trace identity/bounds and untrusted payload rejection; original short/long/infinite-plus-finite/delayed/pending animation semantics; missing content refusal; malformed content/page errors through the actual harness; and overflow/clipping/gutter/touch guards. Their initial observation regression failed on both newly observed cells before the observer change. Controls are synthetic mechanism checks, not actual application reproductions.

Actual failed-cell trace (no post-timeout renderer probes):

```json
{"route":"/blog/no-such-post","viewport":{"width":375,"height":800},"stage":"navigation-start","outcome":"infra","pageErrorCount":0,"events":[],"samples":[],"stages":[{"category":"navigation-start","elapsedMs":2}],"dropped":{"events":0,"samples":0,"observerErrors":0},"truncated":false}
```

Within the unchanged first12-second observation window, no request events, init-script samples or page errors were retained for that failing navigation. Activity during the remainder of the20-second navigation interval is unknown. Its renderer timers/rAF/predicate/animation state is therefore **unknown**. Numeric polling, finite-animation attribution and a Vue change have no demonstrated basis. The hosted Ubuntu customer-list768 settlement cause remains separately unresolved.

The repeated local original-order failure plus cold-route pass supports a bounded browser-lifecycle investigation, without proving accumulation. A separately authorized single scratch width-boundary experiment was performed; its terminal failure and limits are recorded below. The committed harness lifecycle remains unchanged.

Full commands, RED/GREEN receipts, source/bundle manifests, dependency identities, retained failures and detailed limitations are in `.superpowers/sdd/2026-11-12-pilot-windows-webkit-remediation/task-3-report.md` and `task-3-evidence/`. Independent review and hosted verification remain root-owned.

## Terminal scratch lifecycle experiment — not a source correction

The root authorized exactly one scratch experiment that restarts WebKit only between the original five width passes. It retained all41 routes and all original behaviors/order/deadlines/predicates, plus bounded process metadata at width/main-page boundaries. All original functions other than main were AST-identical; all15 page/context API calls in main were AST-identical. Scratch source SHA-256: `57a93e94020985e88e20fbb95cdd652555d1a73ba9d40f096e7e90702bad9de1`; its diagnostic base SHA-256 was `31aaa86d0173a0fe42f660ecd320dd448e180e8c2df0924a3752d7bb7492fa1c`, before the final trace-label-only privacy correction. The full scratch source/patch is retained rather than applied to the harness.

**Result: outer timeout at600.025s. No full acceptance summary.** The driver terminated its owned process group at the pre-existing600s outer bound. Width-end records exist for320/375/768/1024, meaning their matrix/behavior functions returned (possibly through existing guarded failure handling; this does not prove all assertions passed). The final retained record is before the last main route, `/this-route-does-not-exist`1440×800. The preceding204 main iterations reached the next iteration; whether the final main route, later boundary/footer/signed-in checks or cleanup stalled is unknown from these boundary records. The complete final-width behavior suite cannot be claimed.

The214 process snapshots stayed within the256-record,24-process-per-record and524,288-byte caps; all recorded counts were4. Sampled subtree RSS ranges in KiB were 215,968–308,624 at320px; 227,744–304,992 at375px; 225,888–348,672 at768px; 189,264–326,224 at1024px; and219,168–321,840 at1440px. These are snapshots including the scratch Python/Node/launcher/browser subtree. They do not establish a leak, resource pressure or an engine defect. Metadata excludes process arguments/application payloads. Main-page-only boundary sampling does not identify a later behavior phase. Buffered normal stdout was not guaranteed to flush on outer termination, so its absent final summaries/traces are not proof of passing assertions or lack of errors. No post-timeout renderer probes or further browser experiments followed.

The scratch result does not supply full acceptance, so per-width isolation is **not committed** and no cause is inferred. Disposition: retain the diagnostic-only change for independent review and one reviewed hosted Ubuntu/Linux retry to observe the original customer-list768 settlement case. Existing local navigation failures remain distinct evidence; neither is erased by the cold-blog pass.

Resource release: all12 process IDs collected from the scratch subtree were absent after termination (`resource-release.json`, ps exit1 means no selected processes). Other browser/control commands completed and closed their contexts/browser sessions. No manual kill, shared cache cleanup or unrelated process/service shutdown was needed. Browser/build ownership is released.
