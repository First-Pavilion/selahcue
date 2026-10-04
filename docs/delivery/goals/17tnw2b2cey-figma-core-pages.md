# Goal Contract — 17tnw2b2cey-figma-core-pages

## Identity

- Goal ID: 17tnw2b2cey-figma-core-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Pricing, Features, Download and About pages match their Figma frames for the 33 class A/E findings and 2 code defects the audit assigned to this ticket, and ship no claim the repo does not back
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cey
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Change only `PricingView.vue`, `FeaturesView.vue`, `DownloadView.vue`, `AboutView.vue`, new page-local components under `implementation/marketing/src/components/core/`, and tests, so that each of the four pages has Figma's section order, hero, 1248px column and spacing, with Figma's layout and styling but wording that follows what the repo backs, and the harness prints no line that belongs to a class A finding of this ticket.

## Baseline

**Verified** on `origin/web/17tnw2b2cew-shared-components` at `5b203064` (PR 173 head, which contains PR 172 and the audit PR 171):

- `npm run build` exit 0. Harness baseline run `.visual-parity/run-20261004-100329` (pricing, features, download, about; Blink, WebKit for pricing and features), exit 0, 0 failures. Similarity (reported, not gated): about 0.68, download 0.76, features 0.67, pricing 0.77.
- Each view declares its own scoped `.container` (1140 or 1200 max-width, 24px gutter) and sizes its own type; `PricingView` passes `text="Save 20%"` to `UiBadge` and shows `$0 / month` on a third plan, a `$19` Pro price and `Annual` arithmetic; `FeaturesView` carries "NDI 5", "4K 60fps", "1080p60", an alpha-channel and a latency claim and a named pastor; `DownloadView` prints OS floors, a requirements table and an empty "Mobile App Mockup" phone; `AboutView` says "Join thousands of churches".
- Heading outline: Pricing h1 then h3 (plan names), Download h2 then h4 (install steps).
- `PricingCard` (PR 173) takes `to` and shows a disabled "Not available yet" button without it; `UiButton` (PR 172) has variants primary, secondary, ghost, outline, inverse, inverse-outline and sizes compact 39, sm 41, md 44, lg 49 (47 for quiet), a `block` prop; `main.css` has the shared `.container` (1248 content, 96/48/20 gutters) and type tokens.

## Inputs and evidence sources

- ClickUp 17tnw2b2cey (Goal, Scope, Findings, Acceptance Criteria, Copy rule, comments 1400430000059526 and 1400430000059535); audit 17tnw2b2c75; epic 86ajy5v6k; claims removal 17tnw2b0x3h; Download honesty 17tnw2b0q9j (PR 134)
- `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md`, `docs/design/visual-parity/marketing/findings/marketing-core.json` (pricing-*, features-*, download-*, about-*, the two bug entries)
- Committed Figma style dumps and reference PNGs under `docs/design/visual-parity/marketing/`
- `docs/decisions/DECISION-LOG.md` DEC-008 (tiers Free/Pro/Platinum, outputs 2/5/10, NDI outputs none/5/10, seats 1/3/7, Free watermark; prices, names and final STT hours open under D1)
- `docs/product/prds/SelahCue-PRD.md` NFR-015, NFR-024, FR-083, FR-101, FR-131 to 133 (the wording the About, Features and Download copy rests on)
- `docs/delivery/goals/17tnw2b2cev-figma-shared-chrome.md`, `17tnw2b2cew-shared-components.md`; `docs/delivery/VISUAL-PARITY-HARNESS.md` section 11
- Owner decisions given with the task: honest content wins; accessibility must not regress; Figma legacy variables versus `--sc-*` is a deliberate layer; class C and D items go to Uma or the owner; Windows, Linux and macOS are available but no page may claim a downloadable macOS or Linux installer, the Download buttons stay disabled, Linux is not drawn

## Scope

### In scope

- The four views; new page-local components in `implementation/marketing/src/components/core/` (hero, CTA band, feature row, segmented billing toggle, controller mock); a new node test file for the pages; `tests/downloadView.test.ts` kept and extended; a browser verification script under `tests/`, run by one npm script `test:core` (review round 1, Cody N9; the single `package.json` line is a declared edit outside the footprint; wiring it into CI stays on follow-up ticket 17tnw2b2fum)
- Deferred items from the two review notes on the ticket: drop the `text="Save 20%"` attribute; pass `to` to the plan buttons only where the destination does not lie; stop passing `variant="gradient"`; adopt the shared container, section padding and type tokens; button geometry against Figma

### Non-goals

- Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, `tokens.css`, `main.css`, `App.vue`, router (PR 172 and PR 173 files: a needed change is reported, not made)
- ConsoleMockup and OutputManagerMockup (Home ticket); HomeView, secondary pages and auth (parallel instances)
- Removing claims from live pages beyond what adopting Figma's structure replaces (17tnw2b0x3h); price, plan, version, size and requirements numbers (D1, 17tnw2b0x3h); the Pricing FAQ section (class D, pricing-20, Uma)
- The audit report and audit data; workflows, Makefile (and `package.json` beyond the one `test:core` line)

### Constraints

- Own worktree `scph-wt/17tnw2b2cey-core`; branch `web/17tnw2b2cey-pricing-features-download-about` cut from `origin/web/17tnw2b2cew-shared-components`; Draft PR with base `web/17tnw2b2cew-shared-components`; stacked (audit 171, 172, 173, then this); merge-order gate: the stack merges in order, the same day; never merged by this role
- Copy rule: structure, type, spacing and colour follow Figma; wording follows the repo wherever a class C finding says the Figma text is not backed; no price, trial, Church tier, SLA, installer size or version, requirement figure, "unlimited outputs", "nothing leaves the machine" or payment method is added
- A Figma colour that fails AA stays accessible in code and is recorded as class B and flagged to Uma
- `git push` with BatchMode SSH; no attribution trailers; no `pkill` by pattern; ephemeral ports

### Assumptions and unknowns

- **Assumed:** tier names Free, Pro and Platinum (DEC-008) stand in for Figma's Free, Pro and Church; names "can change in the nearest future" (owner), so they are copy in one array, not logic.
- **Decided (owner, 2026-10-04, review round 1):** the DEC-008 plan limits are PUBLISHED AS IS: outputs 2, 5, 10; NDI outputs 5 and 10; devices 1, 3, 7; the Free watermark; worded "up to" (`AS-P9`, what an output counts, is open). Speech-to-text HOURS are not shown (D1 says the final values are open); the cards and the table name the hosted allowance and a note says on-device transcription is not metered (FR-533, FR-546).
- **Decided (owner, 2026-10-04, review round 1):** the label "Download free" is KEPT everywhere (Figma's wording; it links to `/download`, which says plainly that nothing downloads yet). The Free plan button goes there; the nav and the Home page say the same.
- **Decided (Cody B1, review round 1):** Pro AND Platinum have no destination and show a disabled button with "Not available yet". Pro: no billing exists. Platinum: its only destination, `/contact`, waits 800 ms and shows "Message Received ... respond within 24 hours" without sending anything (audit contact-04, -06, -07, class C, 17tnw2b0x3h), and it also says "1,200+ on Discord" and "enterprise SLAs". A button must not lead to a form that throws the visitor's words away, so it gets a destination once the contact form really sends (17tnw2b0x3h).
- **Decided:** the billing toggle is operable with arrow keys, but no discount and no price is computed; choosing Annual shows "Annual billing is not available yet." (no annual plan exists: pricing-18).
- **Unknown (owner/Uma):** pricing-15 to -20, features-10 to -13, download-04, -05, -09, -14, about-07, -08 and the brand eyebrow ink; kept as the audit's honest state and listed in the handoff.

## Dependencies and approvals

- PR 171, 172, 173 (stack), review brokered by the coordinator; the PR 173 release gate binds this PR too (all stack PRs ready together)
- Four-reviewer gate is brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The heading outline of Pricing, Features, Download and About never skips a level (pricing-bug-01, download-bug-01) | `node --test tests/corePages.test.ts` (SSR render, walks h1 to h6) | exit 0; a planted h1-to-h3 page fails the same predicate | exit 0 (the file is 59 tests; the whole `npm test` is 834 pass); the test was red on the baseline views (pricing h1 then h3, download h2 then h4); mutations M01 (plans h2 dropped) and M02 (steps back to h4) each turn it red; the browser script re-walks the live DOM on both engines | PASS |
| C-002 | yes | None of the unbacked strings the ticket names appears in the rendered text of the four pages (any dollar price, Save 20%, free trial, Church tier, SLA, Priority support, Unlimited outputs, NDI 5, 4K, 1080p, alpha channel, latency, Pastor, community counts, requirement figures, installer size or version, "nothing leaves"), with the Pricing FAQ named as the one allow-listed exception | `node --test tests/corePages.test.ts` | exit 0; each banned pattern has a planted-string control | exit 0; 35 banned patterns, each with a planted control, plus controls for the currency-agnostic price ban and a page-scoping control; red on the baseline views; mutations M03 ($19), M05 (unlimited outputs), M06 (4 GB RAM), M07 (a customer count in the CTA band, on two pages), M20 (no account required) and, in review round 1, R14 to R22 (fully offline, nothing leaves your machine, a pound price, a 30 day trial, priority response, 99.9% uptime, cloud transcription, never-blank guarantee, compositor) each turn it red; the FAQ exception is itself pinned so it cannot outlive the section. Round 1 widened the list after Cody's planted phrases passed (N8, N12) and added the NFR-015 and cloud rows (Shadow F1, Cody N3, N4) | PASS |
| C-003 | yes | Pricing: eyebrow, 52/56 headline, subline, three plan cards in a 1248 grid, no `$` price, third plan never reads `$0 / month`, plan buttons are a link or a disabled control with a visible note, `text="Save 20%"` and `variant="gradient"` are gone, the plan names sit under an h2 | `node --test tests/corePages.test.ts`; `tests/core_pages_headless.py`; harness DOM | exit 0; card width 400, gap 24, tops equal | node exit 0; browser (Chromium and WebKit): cards 400 wide at x 96, 520, 944, tops equal, Pro taller; hero eyebrow y159, headline y191 h112, subline y319 h54, pill y399 h42 (all equal to Figma 483:139 and 483:143); Free link /download, Pro and Platinum disabled with "Not available yet" and skipped by Tab (Platinum changed in review round 1, Cody B1); no `$` anywhere; the card bullets are pinned against an independent exact list of DEC-008's limits (Cody N7); M04 (text attribute back), M08 (Free loses its destination), M13 (annual maths on), M18 (Church name back) and R01 (Platinum gets /contact back), R02 to R05 (a changed limit), R06 (hosted wording lost), R07 (note lost), R24 turn the node tests red; R01 also turns the browser script red | PASS |
| C-004 | yes | The billing toggle is a segmented pill with a group name, two radios, roving tabindex, arrow keys, Home and End, and an honest note for Annual | `node --test tests/corePages.test.ts` (key function and markup); `tests/core_pages_headless.py` in Chromium and WebKit | exit 0 | node exit 0 (key rules: wrap, skip disabled, lone option, other keys ignored); browser: Tab lands on the one checked radio, ArrowRight chooses Annual and moves focus, shows "Annual billing is not available yet." and no price, ArrowRight wraps, End, Home, ArrowLeft all work, focus ring is a 2px solid outline, the empty note is rendered and in the accessibility tree (not display:none, Cody N6), pill 42 tall and segment 34 tall at desktop, 44 on a phone (the sweep's touch-target rule). `npm run test:core` runs the browser script as a gate (Cody N9) and a source tripwire in the node tests fails when the handler stops moving focus; M09 (no wrap), M10 (all radios in the tab order), R08 (note display:none) and R09 (focus move deleted) turn the node tests red, and a mutated build turns the browser script red for B1, N6 and N9 | PASS |
| C-005 | yes | Pricing comparison: a 1040 card, 45px header band, 48px rows, centred cells, SVG checks with hidden text, rows only where the repo backs them | node test; browser measurement | exit 0; geometry equals Figma | card 1040 wide at x200, header band 45, every body row 48, the Free column 150 wide (Figma 484:126, 127, 129); ticks are drawn in the success green; eight rows, each a DEC-008 limit or a base row; M14 (row header lost) and M15 (hidden "Included" lost) turn the node tests red | PASS |
| C-006 | yes | Features: Figma's hero, six rows (headings, paragraphs, bullets reworded only where a class C finding says so), skeleton panels, CTA band; none of the build-only claims remain | node test; browser; harness style diff | exit 0; no class A line | six rows 336 tall, panels 548x256 at x796 and x96 alternating, text column 644, tiles 60x60, panels aria-hidden, band 1248x337 with buttons 49 and 47 tall (not stretched); harness: features SSIM 0.67 to 0.91 (converged), 2 box lines to 0; M05 and M16 (panel not hidden) turn the node tests red | PASS |
| C-007 | yes | Download: hero, two 610x316 platform cards with disabled buttons and honest status, requirements band with a defined fill and no figure the repo does not back, mobile section without a placeholder phone, install steps; the disabled-controls guard still holds and also covers the new markup | `node --test tests/downloadView.test.ts tests/corePages.test.ts`; browser | exit 0 | node exit 0 (`downloadView.test.ts` gained a guard that the four disabled controls stay in this template); browser: cards 610x316, action 546x47 radius 12 disabled and skipped by Tab, requirement cards 610x349 with 38px rows, band fill rgb(20, 22, 29), controller mock 280x305, steps 400x197; M11, M19, M21, M22 turn the existing guard or the new tests red | PASS |
| C-008 | yes | About: the two-column story, four values in one row on a full-bleed band, CTA band without an invented community claim | node test; browser; harness style diff | exit 0; no class A line | story columns at x96 and x748 (596 wide), values band 1440 wide, four cards 294x222 in one row, CTA band 1248 wide; harness: about SSIM 0.68 to 0.88, box lines 1 to 0; M07 and M17 turn the node tests red | PASS |
| C-009 | yes | The four views use the shared `.container`, the section padding token and the type tokens; no local container rule remains; no horizontal scroll at 320, 375, 768, 1024, 1440 | node test (source check); `npm run test:responsive` on both engines | exit 0 | node exit 0 (real-tree source check plus controls; M12 and M13 turn it red); `npm run test:responsive` exit 0 (2315 checks over 40 routes x 5 widths, 0 failed) and the same sweep on WebKit exit 0 (2315, 0 failed); the browser script re-checks the four routes at five widths on both engines. It needed one declared edit to `scripts/responsive_sweep.py` (see Risks), in its own commit | PASS |
| C-010 | yes | After `npm run build`, `visual_parity.py --suite marketing --engine both --only pricing features download about` exits 0 and `vp_style_diff.py` prints no line that belongs to a class A finding of this ticket; every remaining line is a documented class B or a class C or D | the harness, compared with baseline `run-20261004-100329` | exit 0; the line set is accounted for finding by finding | final run `.visual-parity/run-20261004-184451` (head 1d8e5db9; round 1 was run-20261004-160252, round 2 run-20261004-165832) exit 0, 0 failures, Blink and WebKit; baseline `run-20261004-100329` (since pruned by the harness's five-run cap; its numbers were read before that); similarity (reported, not gated) about 0.68 to 0.87, download 0.76 to 0.85, features 0.67 to 0.91, pricing 0.77 to 0.82; paired-text lines outside the chrome and the token layer 53 to 17 (pricing), 42 to 9 (features), 68 to 19 (download), 7 to 1 (about); box blocks 15 to 7, 2 to 0, 16 to 4, 1 to 0. Review round 1's rewording briefly lengthened four paragraphs and the browser script caught the reflow (a Figma row of 349 for 336, value cards of 244 for 222), so the copy was shortened again before this run. Every remaining line is accounted for in the Findings table below | PASS |
| C-011 | yes | Every text node on the four pages measures AA in the harness contrast survey, except the eyebrow pill ink that class D holds for Uma; every changed colour pair is computed | harness contrast survey in the final run; `vp_core.contrast_ratio` pair table; the browser script's gradient-band check | no failing text except the named one | survey (Blink and WebKit): only the three hero pills (ABOUT, DOWNLOAD, FEATURES at 3.49:1, `UiBadge` featured, class D account-25) and nothing on Pricing; 36 pairs computed, all at or above AA except those three, plus two decorative tile glyphs that were fixed (white on gold 2.0:1 and on green 2.3:1 became dark ink at 9.5 and 8.4); the closing band's text on its gradient (which the harness reports as unknown) is computed from the gradient at the worst corner of each text box: white holds 4.72:1 at the lightest stop and the check runs on both engines | PASS |
| C-012 | yes | Every offline gate passes with its exit code captured, one at a time, headless required: `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:components`, `npm run test:mirrors`, `npm run check:legal` | each command, exit code to a log | all exit 0 | all run at head 1d8e5db9 (review round 3) in one sequential background run (`/usr/bin/python3`, both REQUIRE variables set, exit code captured right after each command): `make marketing-check` 0 (865 tests), `npm test` 0 (865 pass), `test:states` 0 (60 scenarios, 1751 checks), `test:responsive` Chromium 0 (2315 checks) and WebKit 0 (2315), `test:legal-pages` 0 (419), `article_pages_headless.py` 0 (143 of 143), `test:components` 0 (646 checks, both engines), `test:mirrors` 0 (Django 6.1.1 in a scratch virtualenv outside the repo: ALL MIRRORS AGREE), `check:legal` 0, `npm run test:core` 0 (448 browser checks, both engines). Round 1 ran at ce95aa6c with 847 tests and 364 browser checks; round 2 at d3645815 with 861 and 396. `test:states` took 69 minutes of wall time in this run (the machine stalled; it passed with its own result line). A correction: the exit-code capture in my first final run recorded the status of a `date` call, not of the gate; every result in the first round's handoff was confirmed from the logs' own result lines, and this run's codes are the real ones. `make ci` was not run: Rust, Flutter and API are untouched | PASS |
| C-013 | yes | `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` pass | each command | all exit 0 | `vp_selftest.py` 0 (206 checks), `check_fidelity_audit.py --self-test` 0 (97 checks), `--require-tickets` 0 (0 problems), same run as C-012 at head 1d8e5db9 | PASS |
| C-014 | yes | Each new node test fails when the thing it guards breaks (mutation proof on a copy) | 22 planted faults on a scratch copy of `implementation/marketing` (node_modules read-only), the real tree never touched | each turns the named test red; the unmutated copy is green first | round 0: all 22 turned a test red (M01 to M22: plans h2, step headings, a price, the Save attribute, unlimited outputs, a requirement figure, a customer count, a lost destination, key wrap, tab order, a button losing disabled, a local container rule, the annual maths, a row header, hidden Included text, a visible panel, the story heading, the Church name, a lost describedby id, a no-account claim, a missing describedby, a button hidden from the guard's tree); the nodes were also red on the baseline views before any change. Review round 3: three more node mutations (T01 to T03: the PLANS heading cell not pinned, the pinned cell without a fill, the billing note without a reserved line) each turned a test red, and two mutated builds (T01, T03) each turned `tests/core_pages_headless.py` red. Review round 2: 19 more node mutations (S01 to S19: modifiers ignored by the key rule, the toggle not passing the modifiers, four offline sibling phrases and the CTA band line, the coming-soon bullet, a pasted `.sr-only`, Quinn's seven plants on About, two Download plants, a Features and a Pricing plant) each turned a test red, and two mutated builds (modifiers ignored, a subline a line long) each turned `tests/core_pages_headless.py` red. Review round 1: 25 more node mutations (R01 to R25: Platinum gets /contact back, four changed plan limits, a lost hosted wording, a lost table note, the note display:none, the focus move deleted, About losing the container, a static style attribute, a private-class reach, a second hard-coded red, eight deny-list phrases, a bare chip heading, the Church name, a hero saying fully offline) each turned a test red, and three mutated builds (B1, N6, N9) each turned `tests/core_pages_headless.py` red; 12 of the new tests were red on the previous head 7f008ee8's source | PASS |
| C-015 | yes | The diff touches only the footprint plus this contract and one declared gate-script edit | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths; no shared component or token file | the four views, `src/components/core/*` (new: PageHero, CtaBand, ToneChip, FeatureRow, ControllerMock, SegmentedToggle, segmentedKeys.ts), `tests/corePages.test.ts`, `tests/fixtures/htmlTree.ts`, `tests/core_pages_headless.py`, `tests/downloadView.test.ts`, this contract, and two declared edits outside the footprint: `implementation/marketing/scripts/responsive_sweep.py` (its own commit f62b0d04, so it can be dropped or moved without touching anything else) and one line in `implementation/marketing/package.json` (`test:core`, review round 1) | PASS |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact, no table | start comment 1400430000059596, handoff comment 1400430000059616 (QA steps as a list), the owner-decisions and acceptance-amendment comment 1400430000059696 and the review round 1 handoff 1400430000059712 and the round 2 handoff 1400430000059793, all read back: lists intact, no table, no dropped text; ticket in code review | PASS |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, stacked and labelled as such, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` and the same for the chrome and audit branches | isDraft true; base correct; behind 0 | https://github.com/First-Pavilion/selahcue/pull/178 is Draft with base `web/17tnw2b2cew-shared-components`; behind count 0 for all three bases after the last fetch | PASS |
| C-018 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | Round 1 at `7f008ee8`: Shadow CLEAR (PR comment 5979442102); Cody BLOCKING (1: a button sent a visitor to a form that discarded their message, 5979483544). Re-review at `c92f4023` (code head `ce95aa6c`): Cody blocker CLEAR (5982094165), Quinn CLEAR (5982126263), Vera CLEAR (5982492888). Vera's round 3 finding N1 (the Annual note shifting the plan cards) was fixed afterwards (code head `1d8e5db9`, head `0a7d09ff`) with a node predicate and a browser check, both mutation-proven, and was not re-reviewed by the reviewers. The orchestrator verified at `0a7d09ff`: Draft, mergeable, base `web/17tnw2b2cew-shared-components`, 0 behind, `2c055f42` an ancestor, no shared component or token file touched, and the only paths outside the four views, core components, tests and this contract are the declared `package.json` line and `scripts/responsive_sweep.py`. The stack merge gate (the Pricing FAQ proration and payment-method answers, 17tnw2b0x3h) stays in force: the PR is not marked ready or merged until it clears. Closed by the orchestrator 2026-10-04 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: node tests first (red, then green) with planted-fault controls; browser measurement of every changed section against the committed Figma style dumps; harness style diff before and after
- Broader regression verification: every offline gate in C-012 and C-013; the harness on all four pages under both engines
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium, WebKit), network for Inter, a scratch virtualenv outside the repo for Django (`test:mirrors`). Rust, Flutter and API are untouched, so `make ci` is not required.
- Browser gates run one at a time in the background to a log file that is polled; `SELAHCUE_HEADLESS_REQUIRE=1` and `SELAHCUE_SWEEP_REQUIRE=1` are set (a python without Playwright makes the sweep exit 0 while skipped)

## Iteration ledger

### Iteration 1

- Target criterion: baseline
- Hypothesis: the baseline is green and the findings are reproducible
- Change or investigation: read the ticket, both review notes, the audit data for the four surfaces, PR 172 and 173 contracts, the four views, the shared components and the Figma style dumps; created the worktree; installed; built; ran the harness on the four pages
- Verifier executed: `make marketing-install` (exit 0), `npm run build` (exit 0), `visual_parity.py --suite marketing --engine both --only pricing features download about` (exit 0)
- Result: baseline recorded in the Baseline section
- New evidence: the contrast survey for these pages now lists only the eyebrow pill (3.49:1) because the chrome ticket raised `--sc-text-muted`; `responsive_sweep.py` pins `.pricing-grid` as 3 columns on desktop and Pro first below 1200
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-009
- Hypothesis: the pages can be rebuilt on six page-local components with tests that were red first and fail on planted faults
- Change or investigation: wrote `tests/corePages.test.ts` first (48 of 59 red on the baseline views, the other 11 are controls and the guards that already held); then the six components and four views; Figma values read from the committed style dumps; the harness style diff read after each build
- Verifier executed: `node --test tests/corePages.test.ts tests/downloadView.test.ts`; `npm run build`; harness on the four pages
- Result: green; harness similarity rose on all four pages
- New evidence: (1) the shared scratch directory is shared by every instance: my `gates.sh` was overwritten and I once ran the Home instance's script by mistake (stopped by exact PID within a minute; see the report); my files now live in a private subdirectory. (2) `tests/core_pages_headless.py` found two real defects the node tests could not: the visually hidden "Included" spans escaped the table's scroller and widened the page by 124px on a phone, and a requirement row was 39px, not 38. (3) The responsive sweep found three more: a 34px touch target, a hidden heading at x=-1, and its own constant that expected a 24px desktop gutter
- Decision: iterate

### Iteration 3

- Target criterion: C-009 to C-018
- Hypothesis: with the sweep's container constant updated and the three defects fixed, every gate is green on both engines
- Change or investigation: fixed the three sweep findings in the components (phone hit area, the heading placed inside the container, dark ink on the gold and green tiles for legibility); made the one declared edit to `scripts/responsive_sweep.py` in its own commit; re-ran every gate sequentially at the final head; planted 22 faults on a scratch copy; computed 36 contrast pairs; read the 375, 768 and 1440 renders
- Verifier executed: see the predicate table
- Result: all PASS except C-018, which is the coordinator's
- New evidence: the harness reads a text box where Figma draws a line box, so a headline with a tight line height prints a y-shift of 3 to 4px even when its box is at the Figma y (measured: eyebrow y159, headline y191 h112, subline y319 h54 on Pricing, all equal to Figma 483:139)
- Decision: handoff

## Findings (ClickUp 17tnw2b2cey: 33 class A/E findings and 2 code defects)

Every finding is closed at the source named; the lines that remain in the harness are listed with the reason. The harness reads the text box; Figma draws the line box, so a y-shift of up to 4px on a heading or paragraph (and the running shifts that follow it) is a measurement convention: the section tops and block boxes were measured equal to Figma.

- about-01, about-02, about-03, about-04, about-05, about-06 CLOSED. Remaining lines: the fourth value's body and the closing band's subline differ from the frame by the Copy rule (class C about-08 and the "go live this Sunday / Cancel anytime" claims); one story paragraph says "every core live control works with no network" where Figma says "the whole thing runs with no network" (NFR-015 backs the first); the section padding is 88 (token) against Figma's 90 around the band (page 4px shorter); the eyebrow pill ink is the shared pill's (class D about-07, account-25, 3.49:1).
- download-01, download-02, download-06, download-07, download-10, download-11, download-12 CLOSED. Remaining lines: the hero paragraph, trust line, platform sublines, install-step bodies, the third bullet and the requirement values differ by the Copy rule (class C download-04, -05, -09); the store badges stay the disabled dashed badges (class B download-08, PR 134, with its note, which makes the section 41px taller than the frame and shifts everything under it); the controller mock's fills for "Go Live" and "Blank" are the operator's accessible inks (B: white on Figma's green is 2.7:1 and on its red 3.8:1); the harness pairs the inner screen of the mock with Figma's outer frame (the outer box measures 280x305, as drawn); the "01 02 03" and the "MOBILE CONTROL" pill ink read the single brand-ink property (class D, Uma).
- features-01, features-02, features-03, features-04, features-05, features-06, features-08, features-09 CLOSED. Remaining lines: row 5 and row 6 wording (class C features-10, -11), "(NFR-024)" left out (class D features-12), the closing band's subline; the brand-toned chips (SCRIPTURE, STREAMING, WEB, NDI) read the brand-ink property (class D).
- pricing-01, pricing-02, pricing-05, pricing-06, pricing-07, pricing-08, pricing-09, pricing-10, pricing-11, pricing-12, pricing-13, pricing-14 CLOSED. Remaining lines: the cards' prices, descriptions and bullets, the comparison rows, the toggle's second label and the hero subline differ by the Copy rule (class C pricing-15, -16, -17, -18, DEC-008); the toggle pill is narrower because "Annual" is shorter than "Annual · save 20%" (C pricing-18); the Free and Platinum buttons draw no fill because `PricingCard` uses the `outline` variant where Figma draws `secondary` (shared file, reported); card heights differ with the bullet counts; the table card is 431 tall for eight rows where Figma draws ten (C pricing-12); the eyebrow and the "MOST POPULAR" ink (class D pricing-21).
- pricing-bug-01 and download-bug-01 CLOSED, each pinned by a node test that walks the rendered headings and a browser re-walk.
- Reclassifications: none. Three items the audit left open are kept as it recorded them (pricing-19, pricing-20, features-13, download-13, download-14) and are listed in the handoff for Uma.


### Iteration 4 (review round 1)

- Target criterion: C-001 to C-017 (C-018 is the coordinator's)
- Hypothesis: every finding of Shadow and Cody can be fixed or recorded inside the footprint, each fix with a test that fails without it
- Change or investigation: read both comments in full; fixed or recorded every finding; added 13 node tests and several browser checks; planted 25 node faults and 3 faulty builds to prove them; ran every gate at the new head
- Verifier executed: see the predicate table
- Result: all PASS except C-018
- New evidence: (1) the browser script caught a reflow the rewording caused (a Figma row of 349 for 336, About's value cards of 244 for 222), so the new copy was cut back to Figma's line counts; (2) my own gate script recorded the status of a `date` call instead of the gate's, so the first round's "exit 0" lines were never real exit codes (each result was read from the log's own result line); fixed, and every gate was re-run with the real codes
- Decision: handoff

## Review round 1

Comments on PR 178 at head 7f008ee8 (code unchanged since f9afa6ce):
- Shadow (security and privacy), CLEAR, 0 blocking, 3 non-blocking: https://github.com/First-Pavilion/selahcue/pull/178#issuecomment-5979442102
- Cody (code), BLOCKING 1, 19 non-blocking: https://github.com/First-Pavilion/selahcue/pull/178#issuecomment-5979483544

Owner decisions of 2026-10-04 (binding, given with the fix pass; recorded on the ticket in comment 1400430000059696):
- The DEC-008 plan limits are published as is, worded "up to" (Cody N2: no change).
- The label "Download free" is kept everywhere (Cody N1: no change).

Dispositions:
- Cody B1 (blocking), fixed: Platinum "Talk to us" had `to: '/contact'`, a page that waits 800 ms and shows "Message Received ... respond within 24 hours" without sending anything. Platinum now has no destination and is disabled with "Not available yet", like Pro. Pins updated (`corePages.test.ts`, the browser script); the reason is in Assumptions above; it gets `/contact` back when the form sends (17tnw2b0x3h).
- Shadow F1 and Cody N3, fixed: the Download hero and trust line said "fully offline", beyond NFR-015 (only core live functions work with the network off; sign-in, activation, hosted speech-to-text and the speech model's first download need it). They now say "Core live controls work with no network" and "Free plan · Core live controls work offline". A banned row `fully offline` covers all four pages with a planted control; the Features bullet "fully offline" became "no internet needed". About's "stays offline" (weaker) is left for the owner or Uma.
- Shadow F2, fixed: the plan bullets and the table row name the hosted speech-to-text allowance; a note under the table says on-device transcription is not metered (FR-533, FR-546).
- Shadow F3, fixed: the mock's 16px mark size is a scoped rule, and a test fails on a static `style="..."` in any of the ten templates (Vue hoists it into markup a style-src policy would drop). Shadow's note on a function-local `import math` is fixed too.
- Cody N4, fixed: the cloud transcription claim and bullet are gone (`cloud-stt` is RELEASE: UNSAFE and stripped from release builds); the row says the transcript runs on the machine; a `cloud` ban covers every page; the old pin was replaced.
- Cody N6, fixed: the empty billing note is visually hidden, not `display: none`; a source predicate and a browser check keep it in the accessibility tree.
- Cody N7, fixed: the cards and the table read one `LIMITS` constant, and an independent, exact expected list pins every card bullet (mutations R02 to R05 turn it red).
- Cody N8, fixed: the price ban is currency-agnostic (symbols, ISO codes, words, per month, per year, /mo).
- Cody N9, fixed: `npm run test:core` runs the browser script as a gate (one declared `package.json` line; CI wiring stays on 17tnw2b2fum), and a source tripwire in the node tests fails when the key handler stops moving focus.
- Cody N11, fixed: every section of the four pages must hold the shared `.container` as a direct child.
- Cody N12, fixed: deny-list widened ("nothing leaves" on all pages, trial, priority response, uptime and percentages, guarantee, forever, fully offline, cloud, enterprise and compliance claims, jargon) and the card bullets are pinned exactly.
- Cody N15, fixed: the requirement chips keep their look; the headings read "MINIMUM requirements" and "RECOMMENDED requirements".
- Cody N16, fixed: no reach into UiButton's `.content` (the icon and label sit in a local span); the mock's red is one named custom property.
- Cody N18, done: the acceptance-criteria amendment is on the ticket (comment 1400430000059696).
- Cody N19, fixed: "Never-blank guarantee" and "the screen never blanks" became "designed so a fault cannot black out live output" and "designed to stay up"; "compositor" and "desktop-authoritative" became plain words; "Memory use is capped" became "designed to stay within fixed limits"; Download step 1 no longer says an installer can be fetched ("Run the installer for your platform once it is available").
- Cody N1, N2: no change (owner decisions above); the comment in `CtaBand.vue` that claimed one file holds "Download free" is corrected.
- Cody N5, deferred: "MOST POPULAR" is hard-coded in `PricingCard` (a shared file); it joins the shared-components follow-up pass the coordinator will run after all four area PRs are reviewed.
- Cody N10, deferred: the Pricing FAQ's proration and payment-method answers are 17tnw2b0x3h's; added to the stack merge gate on the PR and on the ticket.
- Cody N13, no change: "OBS / vMix" is Unknown (no repo evidence either way); left as Figma wrote it.
- Cody N14, no change: "No charge" is inferred from the tier name; left, and noted here for the owner.
- Cody N17, deferred: the sweep accepts two desktop gutters until every page has migrated; it becomes per-route (96 only) afterwards.

### Iteration 5 (review round 2)

- Target criterion: C-001 to C-017 (C-018 is the coordinator's)
- Hypothesis: the re-check and QA findings can be fixed or recorded inside the footprint, each fix with a test that fails without it
- Change or investigation: read both comments in full; fixed the modifier-key bug, the offline sibling wording, the time-promise bullet and the duplicated rule; added a copy ledger allow-list for all four pages; edited the ticket description and the CI follow-up ticket; planted 19 node faults and two faulty builds; ran every gate at the new head
- Verifier executed: see the predicate table
- Result: all PASS except C-018
- New evidence: the browser script now also checks each subline's line count against Figma's (a copy that runs a line long moves everything under it); the allow-list is generated from the render and then reviewed line by line, so it records what ships rather than proving it is right: a reviewer must read it
- Decision: handoff

## Review round 2

Comments on PR 178 at head c92f4023 (code head ce95aa6c):
- Cody (re-check), blocker B1 CLEAR, 0 blocking, 3 new Low: https://github.com/First-Pavilion/selahcue/pull/178#issuecomment-5982094165
- Quinn (QA), CLEAR, 0 blocking, 8 non-blocking: https://github.com/First-Pavilion/selahcue/pull/178#issuecomment-5982126263

Dispositions:
- Quinn N1 (Medium), fixed: the billing toggle swallowed Alt+Left and Alt+Right (the browser's Back and Forward), Cmd+Left and Cmd+Right, Ctrl+Home and Ctrl+End and Shift+arrow. `nextIndex` now takes the modifier keys and returns unhandled when any is held; the handler passes them. A key-rule node test covers every chord, a tripwire fails when the handler stops reading the four modifiers, and the browser script dispatches each chord and requires it not default-prevented with the choice unchanged (mutations S01, S02; a mutated build turns the browser script red).
- Cody N20 and Quinn N6, fixed: the sibling "offline" phrases are reworded to NFR-015 wording. The About subline says "keeps its core controls working with no network", the value card is "Works without a network" with "core live controls work without it", and the closing band (Features and About) says "Core live controls keep working with no network". The banned row now also catches "stays offline", "offline by default", "offline when it matters", "keeps working offline" and "doesn't either", with planted controls (S03 to S06). The browser script checks each hero subline's height so a longer line cannot slip in.
- Quinn N7, fixed for what this PR added: "iOS and Android apps coming soon" is now "iOS and Android apps are not available yet" (pinned by the ledger, S07). The store badges' "Coming soon" is PR 134's text, recorded by the audit as the honest class B state (download-08); no test pins it, it sits under a note that says the apps are not in the stores yet, and I left it. One line in `DownloadView.vue` changes it to "Not available yet" if the owner wants.
- Quinn N4, fixed: an allow-list test for all four pages. Each page has a copy ledger (every block of text, in order), and a named list of live claims with a reason each (Pricing only: "MOST POPULAR" and the three FAQ answers). Any rendered block on neither fails. Quinn's plants (Available now for Linux, Download the macOS .dmg today, Works on any computer, Rated 4.9 stars, Instant setup, Built by pastors, Never crashes), "Grab the installer ... and run it." and an "Available" store badge each turn it red (S09 to S19).
- Quinn N5, fixed: the ticket description's Pricing acceptance line (it holds both the "Save badge renders" and the plan-button wording) is rewritten to match comment 1400430000059696; read back, one line changed, no table.
- Cody N22, fixed: `.sr-only` lives once, in a new page-local `SrOnly.vue` (the views no longer carry a copy; a test fails on a pasted one, S08). `main.css` is untouched.
- Cody N21, recorded and wired onto the ticket: the three CI-invisible faults need `npm run test:core` in a gate. I did not touch the Makefile or workflows. Follow-up ticket 17tnw2b2fum did not list it; it now has a scope line and an acceptance line for `test:core` (read back), and the PR says the stack merge gate includes that wiring or an explicit owner acceptance.
- Recorded only (PR description, "Not decided here"): Quinn N2 (hosted speech-to-text shown on every plan while no release build can reach a hosted service; the owner's 2026-10-04 decision to publish DEC-008 as is covers it, for the claims pass), Quinn N3 (the comparison table shows only the Free column on a phone with no hint that two plans lie to the right: Uma), Quinn N8 (the document title is the same on every route, pre-existing; below 1200px Pro is shown first by CSS while the DOM order is Free, Pro, Platinum: Uma), Cody's information note (Pricing says hosted speech-to-text on every plan while Features mentions no cloud path: the claims pass).

### Iteration 6 (review round 3)

- Target criterion: C-005, C-009 and the rest of the predicate (C-018 is the coordinator's)
- Hypothesis: the two Vera findings can be fixed in `PricingView.vue` with a node test on the css and a browser check each
- Change or investigation: read Vera's comment in full; pinned the PLANS heading cell on a phone with its own fill; reserved the billing note's line below 1200px; added a node predicate for each and browser checks at 375 (scroll the table all the way right and read where the cells sit) and at six widths (the plan cards' top before and after choosing Annual); planted three node faults and two faulty builds; ran every gate at the new head
- Verifier executed: see the predicate table
- Result: all PASS except C-018
- New evidence: a screenshot at 375 after scrolling the table right shows the heading cell pinned over the row labels with the Platinum column aligned under its heading; the cards' top is identical before and after choosing Annual at 375, 768, 1024, 1199, 1200 and 1440
- Decision: handoff

## Review round 3

Comment on PR 178 at head c92f4023 (code head ce95aa6c); Vera read d3645815 too:
- Vera (performance), CLEAR, 0 blocking, 2 Low, a pre-existing note and one finding outside her lane: https://github.com/First-Pavilion/selahcue/pull/178#issuecomment-5982492888

Dispositions:
- Vera, outside her lane (the one that mattered), fixed: at 375px, after scrolling the comparison table right, the "Free" and "Pro" headings sat above the pinned row labels, because only `tbody th` was pinned and the "PLANS" heading cell scrolled away (the base pinned both). The heading cell is pinned too, with a fill of its own. A node predicate on the css (the heading cell and the row labels are both sticky at left 0 on a phone, each with a fill) and a browser check at 375 (the table scrolled all the way right: the heading cell sits at the card's left edge, as wide as the label column, on top of the sliding headings, and each column heading stays aligned with its cells) cover it; mutations T01, T02, and a mutated build.
- Vera N1 (Low), fixed: choosing Annual pushed the plan cards down 26px below 1200px wide. The note's line (8px + 18px) is now reserved at every width below 1200px, and out of the flow from 1200px as before; the comment that said it moves nothing is corrected. A node predicate on the css and a browser check that records the cards' top before and after choosing Annual, and after choosing Monthly again, at 375, 768, 1024, 1199, 1200 and 1440 and requires zero shift; mutation T03 and a mutated build.
- Vera N2 (Low), recorded only: About's hero re-wraps from two to three lines on phones when Inter arrives (layout shift 0.0518 against 0.0167 on the base, still under 0.1). The fix is site-wide (a fallback font sized to match Inter with `size-adjust`, or self-hosting and preloading Inter), so it is listed for a follow-up ticket in the PR description. The footer's layout shift stays on 17tnw2b2g24.

## Risks and rollback

- Risks: six new components and four rewritten views; the harness reads copy, so wording changes print class C lines by design; Download and Pricing keep their honest disabled and not-yet states; merging before PR 173 would restore the old `Not available yet` look of the stack (gate recorded on the PR)
- Declared edit outside the footprint: `scripts/responsive_sweep.py` encoded the old design (it expected every page container to be padded by the 24px `--page-gutter` at desktop). Adopting the shared `.container` (96px at desktop) turned it red on 11 checks per engine, and CI runs that sweep, so the stack cannot pass without it. The edit accepts either gutter (24 or the shared container's 96) and is in its own commit (f62b0d04) so the coordinator can move it or drop it; the other area tickets that adopt the shared container need the identical change
- Wording that publishes DEC-008 for the first time: outputs 2, 5, 10, NDI outputs 5 and 10, devices 1, 3, 7 and the Free watermark appear on a customer page (the audit calls them backed; AS-P9, what an output counts, is open, so the copy says "up to"); speech-to-text hours are NOT shown (final values open under D1). The owner decided on 2026-10-04 to publish them as is. No shipped binary enforces them yet (Cody N2); that is the owner's call, recorded here
- Stack merge gate, added in review round 1: the Pricing FAQ's proration and payment-method answers (17tnw2b0x3h, class D pricing-20) contradict the new copy on the same page, so the stack must not go Ready until they are gone or the owner accepts them in writing
- Rollback or recovery: revert the PR; no shared file changed

## Pause and escalation conditions

- A fix needs a shared file (UiButton, UiBadge, PricingCard, tokens, main.css, Navbar, Footer): stop and report the exact change to the coordinator
- A wording choice only the owner or Uma can make: keep the audit's honest state and list it
- Three materially different failed attempts without new evidence: FAILED_LIMIT with the smallest unblocker

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cey-figma-core-pages.md --completion`
- Validator result: the structural check passes and the completion check passes (C-018 closed by the orchestrator on 2026-10-04)
- Independent verification result: round 1 at `7f008ee8` (Shadow 5979442102, Cody 5979483544); re-review at `c92f4023` (Cody 5982094165, Quinn 5982126263, Vera 5982492888): all four clear, the one blocker cleared; round 3 fixes at `0a7d09ff` verified by the orchestrator, not re-reviewed
- Terminal state: VERIFIED_COMPLETE for this ticket's criteria. The PR stays Draft under the stack merge gate (Pricing FAQ proration answers, 17tnw2b0x3h)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: round 0 1400430000059616; round 1 handoff 1400430000059712 (decisions 1400430000059696); round 2 handoff 1400430000059793; round 3 handoff 1400430000059855; all on https://app.clickup.com/t/17tnw2b2cey
