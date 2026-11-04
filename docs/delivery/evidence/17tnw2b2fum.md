# Visual/audit CI gate evidence

Ticket: https://app.clickup.com/t/17tnw2b2fum

## Result and scope

Implementation wires existing no-browser checks through `make visual-audit-check`, called early by `make ci` and by the existing Pillow-enabled always-run workflow job. It runs visual harness controls, fidelity audit controls, and actual ticket/report drift validation. No new dependency is installed. CI fetches full history and measures the target against the explicit under-10-second criterion. Full visual capture stays outside CI.

Ordered push and pull-request paths retain ordinary-doc/Markdown/TODO exclusions and reinclude `docs/design/visual-parity/**` last. Thus audit-data-only edits can start the cheap unconditional workflow job without forcing desktop/browser jobs. Scripts already match ordinary source paths. The existing marketing job separately runs components/core/home/secondary suites after installing both existing required engines. Its 15-minute timeout, runner tier, permissions and packaging controls remain unchanged.

## Existing-scope reconciliation

Historical ticket comments assign components/home/secondary browser wiring here too. Home/Secondary scripts were stale against already approved source. Root authorized harness-only repairs after observed failures:

- Home CTA and Tab/trust literals now match approved registration-first pilot copy from `6f6a50bc`; exact 49px/44px, fonts and item-wrapping checks remain.
- Claims corrections `a526a5ec` and pilot descriptions `6f6a50bc` lengthened content in the second feature row. Existing content-sized cards/grid produce exact heights `[218,218,218,240,240,240]`: one extra 22px line in the stretched second row. The oracle retains the original 0.5px tolerance and exactly six cards, with an additional visibility/no-overflow assertion. No layout/copy changed.
- Support's result-count status assertion is scoped to its search landmark, retaining the assertion, because Navbar now has its own sign-out status region.
- A measured 180 non-bare route/width cases met the shared 96/48/20 container contract. Only that full-bleed container allowance was tightened; the distinct --page-gutter token remains 24 desktop and is still checked. No other responsive assertion/count changed.

The old AC's Pricing arrow-focus negative refers to a control removed under approved `17tnw2b0x3h`: current core tests explicitly forbid a billing radiogroup. Wrong-index SegmentedToggle focus mutation survives current core, exit0, and is NOT accepted as evidence. Root approved replacing it with a current disabled-download/Tab-order negative before the next iteration. All existing core assertions and 300 checks remain intact. The existing shared-components gallery has no SegmentedToggle/arrow scenario, so no extra arrow-focus result is claimed. Its existing keyboard controls remain unchanged.

## Executed positives

- `make marketing-check`: type-check, lint, **1246 unit tests passed**, production build passed.
- `python3 .github/scripts/check_visual_audit_ci.py --run`: actual shared target exit0, **8.068s locally**, visual controls pass, audit self-test **97 checks/0 FAIL**, actual audit/report **0 problems**. Local timing is not the required hosted measurement.
- `npm run test:components`, required engines: **646 checks/0 failures** (324 Chromium,322 WebKit).
- `npm run test:core`, required engines: **300 checks/0 failures**. Current no-pricing UI, geometry, disabled controls, contrast and five widths remain checked.
- Reconciled `npm run test:home`: **260 checks/0 failures** (130 each engine, including new content-visibility check).
- Reconciled `npm run test:secondary`: **362 checks/0 failures** (183 Chromium,179 WebKit).
- Tightened responsive Chromium: **2363 checks,41 routes,5 widths,0 failed**, exit0. WebKit's initial run also completed2363/0 exit0 but had background requests race with a bundle rebuild; clean immutable-bundle repeat is recorded separately at handoff.
- Actionlint passes; workflow controls118 pass and normal check6 workflows/19 jobs; minute controls pass. No new browser/dependency/runner installation was added to CI.

## Executed negatives and history/path controls

1. Existing mutation helper assembled real scratch copies; positive shared target passed first. Removed the real comparator's per-run cap: actual `make ci` exits2 with the expected over-cap refusal control failing, before installer/Rust gates. Removed audit minimum-title validation: actual `make ci` exits2 at its own expected self-test failure, likewise before later gates. Source checkout unchanged.
2. Correct-layout scratch copy builds positive. Enabled the real Windows download button by changing native disabled/aria-disabled state, then ran actual `npm run test:core`: exits1, **four failures** (disabled-state and Tab-order assertions in both engines). No source failure is hidden or waived.
3. Actual committed-branch depth-one sparse clone (`is-shallow=true`) and full shared-object clone (`is-shallow=false`) both pass `make visual-audit-check`. In the full clone, replacing cited origin_main with fabricated `0123456789abcdef0123456789abcdef01234567` makes actual audit/report validation exit1 with `not a commit`.
4. Actual wiring control checks **20 ordered event-path cases** across push/pull_request, including visual JSON/Markdown, vp scripts, unrelated docs, root/nested Markdown and TODO. Four scratch mutations—remove exception or place it before Markdown exclusion, for each event—are all rejected at the corresponding actual path case. This models the workflow's documented simple glob subset, not GitHub's hosted event service.

Rejected diagnostic attempts stay distinct: first core-focus scratch lacked imported notice.json and failed before tests; rebuilt correct-layout scratch fixed infrastructure but demonstrated obsolete focus mutant survival. Neither is called a valid negative. The first geometry probe collided with a concurrent dist rebuild and was discarded; a stable snapshot probe then passed180 cases. Final browser results come from completed actual commands, not these failed attempts.

## Remaining gates and limits

Required hosted target <10s, full source CI, four independent reviews, source freshness and merge/QA remain root-owned gates. No deployment, provider/account call, installer dispatch, package or actual visual capture. Existing browser tests use loopback scripts and their existing allowed Inter font requests. No live customer state is used.

Task-owned raw logs: `/private/tmp/wave10-visual-*`, geometry `/private/tmp/wave10-gutter-probe.json`; cloned/mutated source trees are removed after checks. The core stale-focus run is retained in `wave10-visual-core-focus-negative.log` as an inapplicable surviving mutant; accepted replacement is `wave10-visual-core-disabled-negative.log`.
