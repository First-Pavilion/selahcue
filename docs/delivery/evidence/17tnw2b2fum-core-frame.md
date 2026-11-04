# Core browser frame investigation — iteration 3

Ticket: [Visual/audit CI gates](https://app.clickup.com/t/17tnw2b2fum). PR348 remediation of independently observed WebKit Download geometry variance. Parent source fdf464b71d4a81ea61f495846934a9181bcc2e0a; normally integrated main059ed20827197938a2131eb4fd544c2ebc66fb7d before final checks. No marketing product source, CSS, copy, oracle value or tolerance changes.

## Verified observations and remaining uncertainty

Quinn's original exact full core run failed nine WebKit widths: cards604 vs610, actions540 vs546, steps396 vs400. Chromium passed. Product source trees and executable core code (excluding its module documentation) matched base/head. Quinn's unmodified base command and Farah's unmodified head command subsequently both completed300checks/0failures. Eight unchanged WebKit Pricing→Features→Download repeats also passed, with document client/body widths1440, loaded fonts and card610.

The secondary-page harness already documents and compensates a reserved classic scrollbar reducing the layout frame1428 inside a nominal1440 window. A controlled real WebKit1428 layout reproduces exactly604/540/396; at1440 it produces610/546/400. Current runs used overlay scrollbars; scrollbar-gutter/overflow-scroll diagnostics could not force native reservation. **The native scrollbar and the original failed run's cause were not reproduced or proved.** This is a correction of an independently demonstrated harness assumption, not retrospective attribution or a layout waiver.

## Rendering contracts retained

- Four fixed desktop Figma geometry loads explicitly require measured `document.documentElement.clientWidth === 1440`. They may widen the external window by the measured shortfall, following the existing secondary-suite approach. The adjustment rejects gaps outside1..32px and requires the target within2seconds. It never changes page styles or expected boxes.
- All original300 assertions, Figma values/tolerances, disabled controls, headings, contrast and Tab checks remain.
- Overflow loads retain nominal320/375/768/1024/1440 windows, including nominal1440 separately from Figma geometry. They receive no frame compensation and compare actual scrollWidth to actual clientWidth, so external chrome cannot hide overflow.
- No product CSS/style injection, hidden scrollbar, product layout/copy change, wider tolerance or new dependency.

## Executed proof

`tests/core_frame_regression.py` simulates only12px of external chrome through a real Page's viewport setter. DOM measurements and product styles remain real. This is explicitly not native-classic-scrollbar reproduction.

1. Before the fix, regression exits1 with exactly the original nine geometry values; actual client1428/card604/action540/step396. Accepted RED log: `/private/tmp/wave10-farah-348-frame-red.log`.
2. After compensation, final regression exits0: actual client1440/card610/action546/step400. All20 nominal route/width loads remain unadjusted. A separate overflow HTML fixture simulates an outer-window width including12px chrome; genuine DOM overflow of12px is rejected at all20 nominal cases. Final receipt: `/private/tmp/wave10-farah-348-frame-final.log`.
3. A temporary copy restores only the old `scrollWidth - innerWidth` comparison. Final regression exits1 because that fault hides all20 overflow fixtures, demonstrating the new overflow guard is meaningful. Assigned source never changed for this mutant. Receipt: `/private/tmp/wave10-farah-348-overflow-mutant.log`.
4. Actual `npm run test:core --prefix implementation/marketing`, including its production build and both required engines, completes exit0: **300checks/0failed**, then automatically launches the isolated focused regression, which also completes exit0. The child uses the same dist and existing WebKit dependency, has a120second bound, and propagates nonzero/timeout to the core gate. Receipt: `/private/tmp/wave10-farah-348-core-integrated-final.log`. A final fixture-only portability refinement then changed100vw to100% (genuine overflow remains12px even with a native bar) and verifies the simulated external-window cost without assuming native overlay mode; its affected standalone positive and old-comparison negative were rerun to completion using final source. Core gate wiring and original300 checks were unchanged by that refinement.
5. `make marketing-check` completes exit0: type-check, lint, **1246tests/0fail/0skip**, production build. Receipt: `/private/tmp/wave10-farah-348-marketing-check.log`.

Two preliminary shell setup invocations used an incorrect directory-relative path and did not provide regression evidence. An intermediate regression run predates the stronger outer-window overflow fixture and is superseded by the final receipts above. All actual owned verifier processes terminated before handoff; temporary diagnostic source was never published.

The regression is automatically exercised whenever the existing core gate selects WebKit (the default `npm run test:core` selects both engines). Standalone invocation is `python3 implementation/marketing/tests/core_frame_regression.py` after a build. Its initial RED is historical TDD proof; ongoing CI executes the GREEN assertion and the nominal-window/overflow protections, so removing compensation or restoring the old overflow comparison fails. Expected fixture failures are isolated from the original300 assertions, not waived.

## Gate and next owner

GATE_REVIEW locally. Root owns inspection, publication of the new PR348 head, affected four-review refresh and hosted CI. Earlier hosted timing5.045s and marketing10m39s belong to the prior head; they are not new-head CI results. Original failed-run attribution remains unknown; no failure is waived. The rejected footer payload remains frozen/unpublished and outside this remediation.
