# Goal Contract — 17tnw2b2cey-figma-core-pages

## Identity

- Goal ID: 17tnw2b2cey-figma-core-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Pricing, Features, Download and About pages match their Figma frames for the 33 class A/E findings and 2 code defects the audit assigned to this ticket, and ship no claim the repo does not back
- Role: frontend-engineer
- Status: IN_PROGRESS
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
| C-001 | yes | The heading outline of Pricing, Features, Download and About never skips a level (pricing-bug-01, download-bug-01) | `node --test tests/corePages.test.ts` (SSR render, walks h1 to h6) | exit 0; a planted h1-to-h3 page fails the same predicate | PENDING | PENDING |
| C-002 | yes | None of the unbacked strings the ticket names appears in the rendered text of the four pages (any dollar price, Save 20%, free trial, Church tier, SLA, Priority support, Unlimited outputs, NDI 5, 4K, 1080p, alpha channel, latency, Pastor, community counts, requirement figures, installer size or version, "nothing leaves"), with the Pricing FAQ named as the one allow-listed exception | `node --test tests/corePages.test.ts` | exit 0; each banned pattern has a planted-string control | PENDING | PENDING |
| C-003 | yes | Pricing: eyebrow, 52/56 headline, subline, three plan cards in a 1248 grid, no `$` price, third plan never reads `$0 / month`, plan buttons are a link or a disabled control with a visible note, `text="Save 20%"` and `variant="gradient"` are gone, the plan names sit under an h2 | `node --test tests/corePages.test.ts`; browser measurement at 1440 | exit 0; card width 400, gap 24, tops equal | PENDING | PENDING |
| C-004 | yes | The billing toggle is a segmented pill with a group name, two radios, roving tabindex, arrow keys, Home and End, and an honest note for Annual | `node --test tests/corePages.test.ts` (key function and markup); `tests/core_pages_headless.py` in Chromium and WebKit | exit 0 | PENDING | PENDING |
| C-005 | yes | Pricing comparison: a 1040 card, 45px header band, 48px rows, centred cells, SVG checks with hidden text, rows only where the repo backs them | node test; browser measurement | exit 0; geometry equals Figma | PENDING | PENDING |
| C-006 | yes | Features: Figma's hero, six rows (headings, paragraphs, bullets reworded only where a class C finding says so), skeleton panels, CTA band; none of the build-only claims remain | node test; harness style diff | exit 0; no class A line | PENDING | PENDING |
| C-007 | yes | Download: hero, two 610x316 platform cards with disabled buttons and honest status, requirements band with a defined fill and no figure the repo does not back, mobile section without a placeholder phone, install steps; the disabled-controls guard still holds and also covers the new markup | `node --test tests/downloadView.test.ts tests/corePages.test.ts` | exit 0 | PENDING | PENDING |
| C-008 | yes | About: the two-column story, four values in one row on a full-bleed band, CTA band without an invented community claim | node test; harness style diff | exit 0; no class A line | PENDING | PENDING |
| C-009 | yes | The four views use the shared `.container`, the section padding token and the type tokens; no local container rule remains; no horizontal scroll at 320, 375, 768, 1024, 1440 | node test (source check); `npm run test:responsive` on both engines | exit 0 | PENDING | PENDING |
| C-010 | yes | After `npm run build`, `visual_parity.py --suite marketing --engine both --only pricing features download about` exits 0 and `vp_style_diff.py` prints no line that belongs to a class A finding of this ticket; every remaining line is a documented class B or a class C or D | the harness, compared with baseline `run-20261004-100329` | exit 0; the line set is accounted for finding by finding | PENDING | PENDING |
| C-011 | yes | Every text node on the four pages measures AA in the harness contrast survey, except the eyebrow pill ink that class D holds for Uma; every changed colour pair is computed | harness `report.json` contrast survey; `vp_core` pair table | no failing text except the named one | PENDING | PENDING |
| C-012 | yes | Every offline gate passes with its exit code captured, one at a time, headless required: `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:components`, `npm run test:mirrors`, `npm run check:legal` | each command, exit code to a log | all exit 0 | PENDING | PENDING |
| C-013 | yes | `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` pass | each command | all exit 0 | PENDING | PENDING |
| C-014 | yes | Each new node test fails when the thing it guards breaks (mutation proof on a copy) | planted faults on a scratch copy | each turns the named test red | PENDING | PENDING |
| C-015 | yes | The diff touches only the footprint plus this contract | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths; no shared file | PENDING | PENDING |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact, no table | PENDING | PENDING |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, stacked and labelled as such, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` and the same for the chrome and audit branches | isDraft true; base correct; behind 0 | PENDING | PENDING |
| C-018 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | PENDING (coordinator) | PENDING |

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

## Risks and rollback

- Risks: five new components and four rewritten views; the harness reads copy, so wording changes print class C lines by design; Download and Pricing keep their honest disabled and not-yet states; merging before PR 173 would restore the old `Not available yet` look of the stack (gate recorded on the PR)
- Rollback or recovery: revert the PR; no shared file changed

## Pause and escalation conditions

- A fix needs a shared file (UiButton, UiBadge, PricingCard, tokens, main.css, Navbar, Footer): stop and report the exact change to the coordinator
- A wording choice only the owner or Uma can make: keep the audit's honest state and list it
- Three materially different failed attempts without new evidence: FAILED_LIMIT with the smallest unblocker

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cey-figma-core-pages.md --completion`
- Validator result: PENDING
- Independent verification result: PENDING (coordinator)
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
