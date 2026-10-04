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

- The four views; new page-local components in `implementation/marketing/src/components/core/` (hero, CTA band, feature row, segmented billing toggle, controller mock); a new node test file for the pages; `tests/downloadView.test.ts` kept and extended; a browser verification script under `tests/` (not wired into npm scripts or CI)
- Deferred items from the two review notes on the ticket: drop the `text="Save 20%"` attribute; pass `to` to the plan buttons only where the destination does not lie; stop passing `variant="gradient"`; adopt the shared container, section padding and type tokens; button geometry against Figma

### Non-goals

- Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, `tokens.css`, `main.css`, `App.vue`, router (PR 172 and PR 173 files: a needed change is reported, not made)
- ConsoleMockup and OutputManagerMockup (Home ticket); HomeView, secondary pages and auth (parallel instances)
- Removing claims from live pages beyond what adopting Figma's structure replaces (17tnw2b0x3h); price, plan, version, size and requirements numbers (D1, 17tnw2b0x3h); the Pricing FAQ section (class D, pricing-20, Uma)
- The audit report and audit data; `package.json`, workflows, Makefile

### Constraints

- Own worktree `scph-wt/17tnw2b2cey-core`; branch `web/17tnw2b2cey-pricing-features-download-about` cut from `origin/web/17tnw2b2cew-shared-components`; Draft PR with base `web/17tnw2b2cew-shared-components`; stacked (audit 171, 172, 173, then this); merge-order gate: the stack merges in order, the same day; never merged by this role
- Copy rule: structure, type, spacing and colour follow Figma; wording follows the repo wherever a class C finding says the Figma text is not backed; no price, trial, Church tier, SLA, installer size or version, requirement figure, "unlimited outputs", "nothing leaves the machine" or payment method is added
- A Figma colour that fails AA stays accessible in code and is recorded as class B and flagged to Uma
- `git push` with BatchMode SSH; no attribution trailers; no `pkill` by pattern; ephemeral ports

### Assumptions and unknowns

- **Assumed:** tier names Free, Pro and Platinum (DEC-008) stand in for Figma's Free, Pro and Church; names "can change in the nearest future" (owner), so they are copy in one array, not logic.
- **Assumed:** DEC-008's output, NDI and seat numbers may be shown (the audit lists them as backed; `AS-P9`, what an output counts, is open and the wording says "up to"). STT hours are NOT shown (D1 says the final values are open); the cards say "monthly allowance".
- **Decided:** the Free plan button goes to `/download` with Figma's label. The Download page states plainly that nothing downloads yet; the site-wide wording of "Download free" belongs to 17tnw2b0x3h and the nav already says the same. Pro has no destination (no billing exists) and stays disabled with "Not available yet". The third plan button goes to `/contact`.
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
| C-002 | yes | None of the unbacked strings the ticket names appears in the rendered text of the four pages (any dollar price, Save 20%, free trial, Church tier, SLA, Priority support, Unlimited outputs, NDI 5, 4K, 1080p, alpha channel, latency, Pastor, community counts, requirement figures, installer size or version, "nothing leaves"), with the Pricing FAQ named as the one allow-listed exception | `node --test tests/corePages.test.ts` | exit 0; each banned pattern has a planted-string control | exit 0; 27 banned patterns, each with a planted control, plus a page-scoping control; red on the baseline views; mutations M03 ($19), M05 (unlimited outputs), M06 (4 GB RAM), M07 (a customer count in the CTA band, on two pages), M20 (no account required) each turn it red; the FAQ exception is itself pinned so it cannot outlive the section | PASS |
| C-003 | yes | Pricing: eyebrow, 52/56 headline, subline, three plan cards in a 1248 grid, no `$` price, third plan never reads `$0 / month`, plan buttons are a link or a disabled control with a visible note, `text="Save 20%"` and `variant="gradient"` are gone, the plan names sit under an h2 | `node --test tests/corePages.test.ts`; `tests/core_pages_headless.py`; harness DOM | exit 0; card width 400, gap 24, tops equal | node exit 0; browser (Chromium and WebKit): cards 400 wide at x 96, 520, 944, tops equal, Pro taller; hero eyebrow y159, headline y191 h112, subline y319 h54, pill y399 h42 (all equal to Figma 483:139 and 483:143); Free link /download, Pro disabled and skipped by Tab, Platinum link /contact; no `$` anywhere; M04 (text attribute back), M08 (Free loses its destination), M13 (annual maths on), M18 (Church name back) turn the node tests red | PASS |
| C-004 | yes | The billing toggle is a segmented pill with a group name, two radios, roving tabindex, arrow keys, Home and End, and an honest note for Annual | `node --test tests/corePages.test.ts` (key function and markup); `tests/core_pages_headless.py` in Chromium and WebKit | exit 0 | node exit 0 (key rules: wrap, skip disabled, lone option, other keys ignored); browser: Tab lands on the one checked radio, ArrowRight chooses Annual and moves focus, shows "Annual billing is not available yet." and no price, ArrowRight wraps, End, Home, ArrowLeft all work, focus ring is a 2px solid outline, pill 42 tall and segment 34 tall at desktop, 44 on a phone (the sweep's touch-target rule); M09 (no wrap) and M10 (all radios in the tab order) turn the node tests red | PASS |
| C-005 | yes | Pricing comparison: a 1040 card, 45px header band, 48px rows, centred cells, SVG checks with hidden text, rows only where the repo backs them | node test; browser measurement | exit 0; geometry equals Figma | card 1040 wide at x200, header band 45, every body row 48, the Free column 150 wide (Figma 484:126, 127, 129); ticks are drawn in the success green; eight rows, each a DEC-008 limit or a base row; M14 (row header lost) and M15 (hidden "Included" lost) turn the node tests red | PASS |
| C-006 | yes | Features: Figma's hero, six rows (headings, paragraphs, bullets reworded only where a class C finding says so), skeleton panels, CTA band; none of the build-only claims remain | node test; browser; harness style diff | exit 0; no class A line | six rows 336 tall, panels 548x256 at x796 and x96 alternating, text column 644, tiles 60x60, panels aria-hidden, band 1248x337 with buttons 49 and 47 tall (not stretched); harness: features SSIM 0.67 to 0.91 (converged), 2 box lines to 0; M05 and M16 (panel not hidden) turn the node tests red | PASS |
| C-007 | yes | Download: hero, two 610x316 platform cards with disabled buttons and honest status, requirements band with a defined fill and no figure the repo does not back, mobile section without a placeholder phone, install steps; the disabled-controls guard still holds and also covers the new markup | `node --test tests/downloadView.test.ts tests/corePages.test.ts`; browser | exit 0 | node exit 0 (`downloadView.test.ts` gained a guard that the four disabled controls stay in this template); browser: cards 610x316, action 546x47 radius 12 disabled and skipped by Tab, requirement cards 610x349 with 38px rows, band fill rgb(20, 22, 29), controller mock 280x305, steps 400x197; M11, M19, M21, M22 turn the existing guard or the new tests red | PASS |
| C-008 | yes | About: the two-column story, four values in one row on a full-bleed band, CTA band without an invented community claim | node test; browser; harness style diff | exit 0; no class A line | story columns at x96 and x748 (596 wide), values band 1440 wide, four cards 294x222 in one row, CTA band 1248 wide; harness: about SSIM 0.68 to 0.88, box lines 1 to 0; M07 and M17 turn the node tests red | PASS |
| C-009 | yes | The four views use the shared `.container`, the section padding token and the type tokens; no local container rule remains; no horizontal scroll at 320, 375, 768, 1024, 1440 | node test (source check); `npm run test:responsive` on both engines | exit 0 | node exit 0 (real-tree source check plus controls; M12 and M13 turn it red); `npm run test:responsive` exit 0 (2315 checks over 40 routes x 5 widths, 0 failed) and the same sweep on WebKit exit 0 (2315, 0 failed); the browser script re-checks the four routes at five widths on both engines. It needed one declared edit to `scripts/responsive_sweep.py` (see Risks), in its own commit | PASS |
| C-010 | yes | After `npm run build`, `visual_parity.py --suite marketing --engine both --only pricing features download about` exits 0 and `vp_style_diff.py` prints no line that belongs to a class A finding of this ticket; every remaining line is a documented class B or a class C or D | the harness, compared with baseline `run-20261004-100329` | exit 0; the line set is accounted for finding by finding | final run `.visual-parity/run-20261004-111017` exit 0, 0 failures, Blink and WebKit; baseline `run-20261004-100329`; similarity (reported, not gated) about 0.68 to 0.88, download 0.76 to 0.85, features 0.67 to 0.91, pricing 0.77 to 0.83; paired-text lines outside the chrome and the token layer 53 to 16 (pricing), 42 to 8 (features), 68 to 19 (download), 7 to 2 (about); box blocks 15 to 7, 2 to 0, 16 to 4, 1 to 0. Every remaining line is accounted for in the Findings table below | PASS |
| C-011 | yes | Every text node on the four pages measures AA in the harness contrast survey, except the eyebrow pill ink that class D holds for Uma; every changed colour pair is computed | harness contrast survey in the final run; `vp_core.contrast_ratio` pair table; the browser script's gradient-band check | no failing text except the named one | survey (Blink and WebKit): only the three hero pills (ABOUT, DOWNLOAD, FEATURES at 3.49:1, `UiBadge` featured, class D account-25) and nothing on Pricing; 36 pairs computed, all at or above AA except those three, plus two decorative tile glyphs that were fixed (white on gold 2.0:1 and on green 2.3:1 became dark ink at 9.5 and 8.4); the closing band's text on its gradient (which the harness reports as unknown) is computed from the gradient at the worst corner of each text box: white holds 4.72:1 at the lightest stop and the check runs on both engines | PASS |
| C-012 | yes | Every offline gate passes with its exit code captured, one at a time, headless required: `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:components`, `npm run test:mirrors`, `npm run check:legal` | each command, exit code to a log | all exit 0 | all run at head f9afa6ce in one sequential background run (`/usr/bin/python3`, both REQUIRE variables set): `make marketing-check` 0 (834 tests), `npm test` 0 (834 pass), `test:states` 0 (60 scenarios, 1751 checks), `test:responsive` Chromium 0 (2315 checks) and WebKit 0 (2315), `test:legal-pages` 0 (419), `article_pages_headless.py` 0 (143 of 143), `test:components` 0 (646 checks, both engines), `test:mirrors` 0 (Django 6.1.1 in a scratch virtualenv outside the repo: ALL MIRRORS AGREE), `check:legal` 0, `tests/core_pages_headless.py` 0 (360 checks, both engines). `make ci` was not run: Rust, Flutter and API are untouched | PASS |
| C-013 | yes | `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` pass | each command | all exit 0 | `vp_selftest.py` 0 (206 checks), `check_fidelity_audit.py --self-test` 0 (97 checks), `--require-tickets` 0 (0 problems), same run as C-012 | PASS |
| C-014 | yes | Each new node test fails when the thing it guards breaks (mutation proof on a copy) | 22 planted faults on a scratch copy of `implementation/marketing` (node_modules read-only), the real tree never touched | each turns the named test red; the unmutated copy is green first | all 22 turned a test red (M01 to M22: plans h2, step headings, a price, the Save attribute, unlimited outputs, a requirement figure, a customer count, a lost destination, key wrap, tab order, a button losing disabled, a local container rule, the annual maths, a row header, hidden Included text, a visible panel, the story heading, the Church name, a lost describedby id, a no-account claim, a missing describedby, a button hidden from the guard's tree); the nodes were also red on the baseline views before any change | PASS |
| C-015 | yes | The diff touches only the footprint plus this contract and one declared gate-script edit | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths; no shared component or token file | the four views, `src/components/core/*` (new: PageHero, CtaBand, ToneChip, FeatureRow, ControllerMock, SegmentedToggle, segmentedKeys.ts), `tests/corePages.test.ts`, `tests/fixtures/htmlTree.ts`, `tests/core_pages_headless.py`, `tests/downloadView.test.ts`, this contract, and the one declared edit outside the footprint, `implementation/marketing/scripts/responsive_sweep.py`, in its own commit f62b0d04 so it can be dropped or moved without touching anything else | PASS |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact, no table | start comment 1400430000059596 read back; the handoff comment id is in the Final evaluation section and was read back | PASS |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, stacked and labelled as such, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` and the same for the chrome and audit branches | isDraft true; base correct; behind 0 | https://github.com/First-Pavilion/selahcue/pull/178 is Draft with base `web/17tnw2b2cew-shared-components`; behind count 0 for all three bases after the last fetch | PASS |
| C-018 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | PENDING (coordinator): not requested by this role | PENDING |

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


## Risks and rollback

- Risks: six new components and four rewritten views; the harness reads copy, so wording changes print class C lines by design; Download and Pricing keep their honest disabled and not-yet states; merging before PR 173 would restore the old `Not available yet` look of the stack (gate recorded on the PR)
- Declared edit outside the footprint: `scripts/responsive_sweep.py` encoded the old design (it expected every page container to be padded by the 24px `--page-gutter` at desktop). Adopting the shared `.container` (96px at desktop) turned it red on 11 checks per engine, and CI runs that sweep, so the stack cannot pass without it. The edit accepts either gutter (24 or the shared container's 96) and is in its own commit (f62b0d04) so the coordinator can move it or drop it; the other area tickets that adopt the shared container need the identical change
- Wording that publishes DEC-008 for the first time: outputs 2, 5, 10, NDI outputs 5 and 10, devices 1, 3, 7 and the Free watermark appear on a customer page (the audit calls them backed; AS-P9, what an output counts, is open, so the copy says "up to"); speech-to-text hours are NOT shown (final values open under D1)
- Rollback or recovery: revert the PR; no shared file changed

## Pause and escalation conditions

- A fix needs a shared file (UiButton, UiBadge, PricingCard, tokens, main.css, Navbar, Footer): stop and report the exact change to the coordinator
- A wording choice only the owner or Uma can make: keep the audit's honest state and list it
- Three materially different failed attempts without new evidence: FAILED_LIMIT with the smallest unblocker

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cey-figma-core-pages.md --completion`
- Validator result: structural check passes; the completion check lists only C-018 (independent review), which the coordinator closes
- Independent verification result: PENDING (coordinator brokers Cody, Vera, Shadow and Quinn)
- Terminal state: GATE_REVIEW (every criterion this role owns is PASS; the review pipeline is the coordinator's)
- Remaining failed or blocked criteria: C-018 only
- ClickUp final evidence comment: see the handoff comment on https://app.clickup.com/t/17tnw2b2cey
