# Loading and footer regression — 17tnw2b2g24

Task: https://app.clickup.com/t/17tnw2b2g24
Design: Uma comment 1400430000277444, with root's measured pending-visibility refinement.
Base: d9fcd524634ab9328231b6d984bd16be11d2ea78 (includes auth PR345 and its2765-check baseline).

App.vue now displays the existing loading status while initial router readiness is pending. Its viewport-minus-navbar reservation and temporarily hidden footer retain layout until readiness succeeds or fails; resolved short pages keep their original natural footer flow. Bare routes use matched target metadata before the initial currentRoute resolves.

Suspense alone did not render the initial pending state: Vue Router resolves its import before RouterView renders. Baseline chunk interception observed no loading status and a visible footer. Reserving height alone then produced CLS0.1811 on short Pricing375 as the footer entered view at y517 from y900. Pending visibility:hidden preserves the reservation while preventing that first visible placement from becoming a shift. It is released on success and rejection; navbar Home navigation recovers after a failed import.

## Complete focused acceptance receipt

`python3 scripts/loading_footer_headless.py --baseline ../../docs/delivery/evidence/17tnw2b2g24/short-baseline.json --output /tmp/footer-green.json` from implementation/marketing (after build).

Exit0,27 measured cases,0 failures. Chromium148.0.7778.96; fresh browser contexts; actual route request held at least700ms; viewport height900. External fonts are aborted and account API responses deterministic. No provider or real account calls. PerformanceObserver uses layout-shift session windows (1s gap/5s maximum) and excludes recent-input entries. The gate refuses stale production bundles.

| Route | Width | Three CLS samples | Median |
|---|---|---|---|
| /pricing | 375 | 0.00000000, 0.00148319, 0.00000000 | 0.00000000 |
| /pricing | 1440 | 0.00003057, 0.00003057, 0.00003057 | 0.00003057 |
| /terms | 375 | 0.00000000, 0.00000000, 0.00000000 | 0.00000000 |
| /terms | 1440 | 0.00003057, 0.00003057, 0.00003057 | 0.00003057 |

All pending long-route footers begin at y900 and are hidden. Loading text is visible, role=status, unfocused and contrast8.7374:1. No overflow at375/768/1440. Resolved404, empty Changelog and short Pricing main/footer geometry match the captured unchanged-shell baseline within1px, with the same computed main minimum auto. Bare Sign up has no nav/footer before or after resolution. Eager Home remains below0.1; failed imports release status/footer protection and navigation to Home recovers. Screenshots show actual pending and resolved375px Pricing.

## Negative proofs

Four independent temporary production builds all exit1 on the intended browser assertions: remove reservation; expose the pending footer; omit readiness rejection release; restore the unchanged App shell. See negative.json and negative.log. Mutants use explicit targeted modes; those modes are diagnostics, not the complete acceptance gate. Original source is restored before serving each retained mutant output and again in finally.

Baseline and reservation-only diagnostics are retained without rewriting their failures. They include an early verifier assumption that the computed main minimum was0px; the real baseline is auto. The final verifier compares captured baseline values/geometry. Neither diagnostic is claimed as a passing command.

## Full command receipts at draft publication

- make marketing-check passed: type-check, lint,1246 unit tests (0 failed/skipped),production build.
- First npm run test:responsive invocation exited1 (1 of2363 checks): old main-child wait sampled the new shell status at Reset375. The scoped fix waits for the resolved route child; every assertion and count remains.
- Final npm run test:responsive passed:2363 checks,41 routes ×5 widths,0 failed (Chromium required, no skip).
- Exact npm run test:states is still running at publication;2765 baseline retained. Its completed receipt and hosted results will be posted on PR and ClickUp without editing frozen source solely for a pending label.
- Independent Cody, Shadow, Quinn and Vera reviews remain with root; no merge, QA transition, deployment or packaging by Farah.
