# Goal Contract — 17tnw2b2cev-figma-shared-chrome

## Identity

- Goal ID: 17tnw2b2cev-figma-shared-chrome
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The marketing site's shared chrome (navbar, footer, UiButton, design tokens, app shell) matches the Figma chrome that every page frame shares, without regressing accessibility, and the harness shows each class A finding of this ticket closed
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cev
- Created: 2026-10-03
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Implement the 26 class A findings that the Figma fidelity audit (ClickUp 17tnw2b2c75, Draft PR 171)
assigned to shared chrome, plus `reset-r2-04` (the primary button's hover fill fails AA), which the audit review pass added to this ticket (ClickUp comment 1400430000059472; class A in the merged audit data). The navbar, footer, `UiButton`, `tokens.css`, the global rules in `main.css`,
`App.vue` and `router/scroll.ts` must match what Figma draws on all 14 page frames at 1440 wide, and the
diff the harness prints for the affected surfaces must contain no line that belongs to one of these
findings. Class C and D items (decisions for the owner or Uma) are left exactly as they are.

## Baseline

**Verified** on `origin/web/17tnw2b2c75-figma-fidelity-audit` at `0990433e` (the harness exists only there):

- `make marketing-check` exit 0; `npm test` 612 pass, 0 fail.
- Marketing harness baseline run (Blink, 35 surfaces): `.visual-parity/run-20261003-212326`, 0 failures.
- Navbar is 69px tall with its content inset to x=124; footer is four equal columns with a `/how-it-works`
  link that renders the 404 page; `UiButton` is a 999px pill whose height follows the parent line-height;
  `--sc-text-muted` is 3.79:1 on `--sc-surface`; `--sc-surface-alt` and `--sc-success` are used and never defined.
- `scripts/responsive_sweep.py` asserts a 68px navbar container and four footer link columns on desktop.

## Inputs and evidence sources

- ClickUp 17tnw2b2cev (scope, findings, acceptance criteria), audit ticket 17tnw2b2c75, epic 86ajy5v6k
- `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` (shared-chrome-01 to 34, pricing-25)
- `docs/design/visual-parity/marketing/findings/shared-chrome.json`, `figma-style/*.json` (Figma values)
- `docs/delivery/VISUAL-PARITY-HARNESS.md` section 11; `docs/design/MARKETING-SITE-HANDOFF.md`, `AUTH-LANDING-PAGES-HANDOFF.md` (token mapping, 2.2)
- Owner decisions given with the task: honest content wins; accessibility must not regress; Figma legacy variables versus `--sc-*` is a deliberate layer

## Scope

### In scope

Footprint (the only files this ticket edits), under `implementation/marketing/`:

- `src/components/Navbar.vue`, `Footer.vue`, `UiButton.vue`
- `src/assets/styles/tokens.css` and the global rules in `src/assets/styles/main.css`
- `src/App.vue`, `src/router/scroll.ts`
- their tests under `tests/`

Plus declared edits outside that list, each made in its own commit because it follows directly from the requested change:

- `scripts/responsive_sweep.py`: the 68px navbar height and four-column footer assertions (see Assumptions), and, from review round 1, a negative assertion that bare routes render no navbar or footer and one that "How it works" is not the current page on Home
- `scripts/legal_pages_headless.py`: its hard-coded 69px bar and 82..96px anchor window (review round 1, Quinn B1)
- `docs/design/DESIGN-TOKENS.md`: one paragraph recording the web-only `--sc-text-muted` raise (review round 1, Cody)

### Non-goals

- Home steps section id (`id="how-it-works"` is the Home ticket's); UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog (17tnw2b2cew, a parallel instance)
- Any view's content, mobile and tablet layouts (17tnw2b0q9g), the 404 view's nested main (17tnw2b0x3h)
- Class C and D decisions: `account-25`, `shared-chrome-11`, `-12`, `-13`, `-19`, `-31`, `-33`
- The audit report and the audit data under `docs/design/visual-parity/marketing/`

### Constraints

- Own worktree and branch; one ticket, one Draft PR, never merged by this role; the PR is stacked on the audit branch
- Honest content wins: the footer tagline and legal line keep their current wording (decision 19 is pending)
- Accessibility must not regress; a Figma colour below AA stays accessible in code
- No new brand ink, and no hover colour for the quiet variants: decisions held for Uma. The one hover fill that IS changed is the primary's (`--sc-primary-hover-fill` #5f4de6, the audit's example): it is a shipped accessibility failure (reset-r2-04), so it must measure at least 4.5:1 with the white label; the exact colour stays Uma's under shared-chrome-31
- ClickUp: lists only, no Markdown tables; read every write back

### Assumptions and unknowns

- **Assumed:** the two gate scripts that encode the old design (`responsive_sweep.py` barHeight 68, footer 4 columns) count as this ticket's tests; the edit is the smallest that follows the requested design change. Reported to the coordinator.
- **Assumed:** `--sc-text-muted` may be raised on the web layer only (the ticket allows "fix the token"); the cross-platform Design 2.0 token and the Rust/Flutter copies are untouched. Flagged to Uma.
- **Assumed:** `gradient` stays a valid `UiButton` variant for the area tickets that still pass it, and renders as the solid primary until they migrate (Figma draws no gradient button).
- **Unknown:** whether the Home ticket will land before this one; the nav anchor is verified with the target id stubbed.

## Dependencies and approvals

- Audit branch `web/17tnw2b2c75-figma-fidelity-audit` (PR 171, four reviewers in progress): this branch is stacked on it and must be retargeted and rebased after it merges
- Home ticket (adds the `how-it-works` id): not blocking, stubbed in verification
- Four-reviewer gate (Cody, Vera, Shadow, Quinn) is brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | At 1440 the navbar is 79px tall, runs at 48px gutters, the mark is visibly 32px, the active route is Semi Bold in the primary text colour, Sign in is the primary text colour with an 18px gap, Download free is a 10px rectangle at weight 700 (shared-chrome-01 to 06) | harness run plus `vp_style_diff.py` on every page that carries the chrome; browser measurement | no printed line for the nav texts or the nav CTA box other than the token-layer colour lines | browser: header 79, container 78, mark 32x32, active 600, Sign in 18px gap, CTA 137.5x39 radius 10px weight 700 (Blink and WebKit); style diff: nav text lines are only `colour~` (class B) on all 15 pages | PASS |
| C-002 | yes | Nav How it works is a router link to the Home route with the hash and Home scrolls it clear of the sticky bar (shared-chrome-07) | `node --test tests/scroll.test.ts tests/chrome.test.ts` and a browser run with the id stubbed | tests pass; stubbed target lands below the 79px bar | tests pass (699 of 699); browser with the id stubbed: target top 94.5px (79 bar plus 16 gap) from Pricing, on Home, and on a cold load of the hash; not marked active on Home | PASS |
| C-003 | yes | The footer has Figma's three columns and bottom bar with exactly the listed entries; Privacy and Terms are in the bottom bar; every footer link resolves to a real route (shared-chrome-14, 15) | `node --test tests/chrome.test.ts` (walks footer links against the router table) | exit 0; a missing target fails the test | tests pass; the walk has a control that turns red on a path with no route; browser footer link list matches (16 links, none `/how-it-works`) | PASS |
| C-004 | yes | Footer layout and type match (3 hugging columns at 96px gutters, 55px plus border top padding, 30px link pitch, muted 12px uppercase headings over bright links, page-colour fill) (shared-chrome-16, 17, 18) | harness DOM and `vp_style_diff.py` on the footer; browser measurement | no printed footer line for these findings | browser: columns at x=974, 1109, 1280 (Figma 973, 1109, 1280), link pitch 30, headings 12px 700 uppercase 0.1px; footer 358px (Figma 358); style diff footer box: only the token-layer border line | PASS |
| C-005 | yes | Footer copyright, the route-loading fallback and every small text in nav and footer measure at least 4.5:1; the harness contrast survey lists no failing nav or footer text on any page (shared-chrome-20, 21, 34, pricing-25) | harness contrast survey in `report.json` for all captured pages; node tests pin the pairs | survey lists no nav, footer or loading entry; every chrome pair at least 4.5 | survey (Blink) 166 entries before, 74 after, none in nav, footer or loading; chrome pair test passes; token ratios 5.9, 5.5, 5.0 | PASS |
| C-006 | yes | UiButton renders radius 10 (compact, sm) and 11 (md, lg), fixed heights 39, 41, 44, 47, 49 independent of the parent line-height, variants primary, secondary (bordered), ghost, outline, inverse and inverse-outline, a focus ring that shows in forced-colors mode (shared-chrome-27 to 30), and a primary hover that holds 4.5:1 with the white label (reset-r2-04) | `node --test tests/uiButton.test.ts` and a browser measurement in a parent with a hostile line-height | tests pass; measured heights equal the table | 28 tests pass, four mutations shown red; browser heights identical with line-height 3 forced on every container (6 pages, Blink and WebKit); forced-colors emulation shows a 2px solid outline and no box-shadow; primary and gradient-alias hover measured rgb(95, 77, 230) with a white label = 5.69:1 in Blink and WebKit, on the nav button and on page buttons (the old hover was 3.78:1); the guard turns red when the hover fill is put back to the old value | PASS |
| C-007 | yes | One 1248px content-width token with 96, 48 and 20px gutters and one shared container exist; section padding is 88px; `--sc-surface-alt` and `--sc-success` are defined; a test fails if a `var(--x)` used in `src/` has no definition (shared-chrome-22, 23, 24, 25, pricing-25) | `node --test tests/tokens.test.ts` (and a mutation: an undefined var makes it fail) | exit 0; the mutation turns it red | the guard was red before the change on exactly `--sc-surface-alt` and `--sc-success`, green after; in-memory controls cover undefined, fallback, other-file and comment cases | PASS |
| C-008 | yes | Desktop nav links, brand and CTA show a visible focus-visible ring and the nav surface uses tokens, not the hard-coded dark band (shared-chrome-08, 09) | `node --test tests/chrome.test.ts` and a browser keyboard pass | tests pass; ring present on each control; computed header background equals the base token | Tab order measured in Blink: brand, Features, How it works, Pricing, Download, Sign in, Download free each show a 2px solid brand ring at 2px offset; header background rgb(11, 13, 18) = base; scrolled state computed on a hash jump | PASS |
| C-009 | yes | After `npm run build`, `visual_parity.py --suite marketing --only home pricing features` exits 0 and `vp_style_diff.py` prints no line belonging to a class A finding of this ticket; the full suite on both engines shows no regression on any surface | `python3 scripts/visual_parity.py --suite marketing --engine both` and `vp_style_diff.py` per slug, before and after | exit 0; remaining chrome lines are documented class B, C or D | runs `.visual-parity/run-20261003-213858` (only home pricing features, exit 0) and `.visual-parity/run-20261003-215149` (all surfaces, both engines, exit 0, before the review fixes); final, at the merged head with the AA hover: `.visual-parity/run-20261004-080255` (re-run after the audit branch's last commit b37d9ea5 was merged; the earlier full gate run at b8cdb34a used run-20261004-075836) (all surfaces, both engines, exit 0, survey Blink 70 and WebKit 65 entries, none in nav, footer or loading); baseline `run-20261003-212326`; chrome lines not in the token layer 1023 to 150 over 15 pages (about 8 each: the nav border read as top-only by the harness, Affiliates ink, class C wording, page text pairings); Blink and WebKit identical | PASS |
| C-010 | yes | `make marketing-check`, `npm test`, `npm run test:states` and `npm run test:responsive` pass (headless required) | each command with its exit code captured to a file, never piped | all exit 0 | browser gates at b8cdb34a, code-identical to the final head (later commits are this contract and the audit branch's harness-only commit b37d9ea5, merged in; `make marketing-check`, `npm test` and the harness suite re-run on that final merge): `make marketing-check` exit 0 (724 pass, 0 fail); `npm test` exit 0 (724); `test:states` exit 0 (60 scenarios, 1751 checks, 0 FAIL); the sweep under `/usr/bin/python3` with `SELAHCUE_SWEEP_REQUIRE=1` exit 0 on Chromium (2315 checks, 0 failed) and on WebKit (2315, 0 failed); `vp_selftest.py` 206 checks 0 FAIL; `check_fidelity_audit.py --self-test` 97 checks 0 FAIL, `--require-tickets` 0 problems | PASS |
| C-011 | yes | No horizontal page scroll at 375, 768 and 1440 on the changed pages and the mobile nav sheet and 44px touch targets still pass | `npm run test:responsive` and real renders | sweep reports none; renders checked | sweep above (it caught the 37px Terms link on phones, fixed); renders at 1440, 1024, 768 and 375 read; scrollWidth equals innerWidth at 1440, 1024, 768, 375 | PASS |
| C-012 | yes | The PR touches only this ticket's footprint plus the named gate edit; shared files owned by other tickets are untouched | `git diff --name-only origin/web/17tnw2b2c75-figma-fidelity-audit` | every path is in the footprint or the named gate script | the file list: Navbar.vue, Footer.vue, UiButton.vue, tokens.css, main.css, App.vue, scroll.ts, the test files and fixtures for them; outside the list and declared: `responsive_sweep.py`, `legal_pages_headless.py`, `DESIGN-TOKENS.md`, and this contract | PASS |
| C-013 | yes | A Draft PR is open against the audit branch, stacked and labelled as such, and the branch is not behind the audit branch | `gh pr view` and `git rev-list --count HEAD..origin/web/17tnw2b2c75-figma-fidelity-audit` | isDraft true; base is the audit branch; behind count 0 | https://github.com/First-Pavilion/selahcue/pull/172 draft, base `web/17tnw2b2c75-figma-fidelity-audit`; behind count 0 at the last fetch (see the final message for the head) | PASS |
| C-014 | yes | ClickUp 17tnw2b2cev is in progress with a start comment and carries the handoff comment with QA steps as a list | ClickUp read-back | both comments present, no dropped table | start comment 1400430000059199; handoff comment 1400430000059466 (read back, lists render, no table); ticket moved to code review | PASS |
| C-015 | yes | Independent review (code, performance, security, QA) has passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | not requested by this role; the coordinator brokers it on the PR head | PENDING |
| C-016 | yes | The other headless gates that run on these files still pass: the legal pages gate and the article pages gate (review round 1, Quinn B1) | `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:legal-pages` and `/usr/bin/python3 scripts/article_pages_headless.py` | both exit 0 | `test:legal-pages` exit 0, 419 passed, 0 failed (it was 395 passed, 24 failed with the 69px bar hard-coded); `article_pages_headless.py` exit 0, 143 of 143 | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: new node tests first (red, then green); browser measurement of each changed control; harness style diff and contrast survey before and after
- Broader regression verification: `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive`, `vp_selftest.py`, `check_fidelity_audit.py --self-test`, the harness on all captured surfaces under Blink and WebKit
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium, WebKit), headless Chrome, network for the Inter font. Rust, Flutter and API are untouched, so `make ci` is not required.
- **`npm run test:responsive` can exit 0 while SKIPPED.** If the first `python3` on PATH has no Playwright, the sweep prints "SWEEP SKIPPED" and exits 0. A passing result counts only with `SELAHCUE_SWEEP_REQUIRE=1` (and `SELAHCUE_HEADLESS_REQUIRE=1` for the other headless gates) and `/usr/bin/python3`; every result recorded here was run that way. Pre-existing, not from this change (review round 1, Quinn N11).
- Browser-driven gates run one at a time, in the background, to a log file that is polled; a gate that dies oddly (closed connection, killed browser) is re-run before it is trusted or reported, because another session's cleanup once killed browser processes that were not its own.

## Iteration ledger

### Iteration 1

- Target criterion: baseline and C-007
- Hypothesis: a token guard test that scans for undefined custom properties fails today for `--sc-surface-alt` and `--sc-success`
- Change or investigation: baseline gates and harness run captured; worktree cut from the audit branch
- Verifier executed: `make marketing-check` (exit 0), harness run `.visual-parity/run-20261003-212326`
- Result: baseline green; every gate that encodes the old design identified
- New evidence: `responsive_sweep.py` asserts a 68px bar and four footer columns
- Decision: iterate

### Iteration 2

- Target criterion: C-006, C-007
- Hypothesis: heights, radius, variants and the focus ring can be resolved from the stylesheet, so a test can fail on each; and the undefined-property guard fails before the tokens exist
- Change or investigation: a small CSS resolver for tests (cascade, media blocks, px arithmetic); `uiButton.test.ts` and `tokens.test.ts` written first and seen red (16 and 14 failures for the right reasons); then `UiButton.vue`, `tokens.css`, `main.css`
- Verifier executed: `node --test tests/uiButton.test.ts tests/tokens.test.ts`; four UiButton mutations (padding, line-height, outline, radius)
- Result: green; each mutation turned a test red; one pinned-props test updated on purpose (`block` added)
- New evidence: the guard names exactly the two undefined properties the audit found
- Decision: iterate

### Iteration 3

- Target criterion: C-001 to C-005, C-008
- Hypothesis: navbar, footer and shell can be rebuilt to the Figma values with the existing mobile sheet and phone footer left alone
- Change or investigation: `chrome.test.ts` written first (36 of 42 red); `Navbar.vue`, `Footer.vue`, `App.vue`, `scroll.ts`; sweep gate updated in its own commit
- Verifier executed: `npm test`; `test:responsive`; browser measurement in Blink and WebKit; style diff before and after
- Result: the first sweep failed on a real defect (the Terms link was 37px wide on phones), fixed with a test; browser check found the scrolled bar had no blur in Chrome (a hand-written prefix made the minifier drop the unprefixed property), fixed with a test; footer height trimmed to Figma's 358
- New evidence: the harness reads only the top border, so the bottom-bordered bar always prints a border line (a measurement limit, not a defect)
- Decision: iterate

### Iteration 4

- Target criterion: C-009, C-010, C-011, C-013, C-014
- Hypothesis: every gate is green on the final code and the PR can be opened stacked
- Change or investigation: all gates re-run fresh on the final head; label contrast test added for every UiButton variant and hover; PR 172 opened as Draft against the audit branch
- Verifier executed: see the predicate table
- Result: all PASS except the handoff comment (written next) and independent review (brokered)
- New evidence: contrast survey 166 to 74 entries with none in nav, footer or loading
- Decision: gate-review

### Iteration 5 (review round 1)

- Target criterion: C-010, C-012, C-016 and the review findings
- Hypothesis: every finding is fixable inside the footprint plus declared gate edits, and each guard can be shown to bite
- Change or investigation: read the four reviews; fixed the legal pages gate; wrote each guard first and mutation-proved it (main.css ratio, unreachable media block, deleted rule, default router-link, bare route rendering chrome, footer using the navbar's variable); replaced the first-task scroll read with an observer; merged the audit branch
- Verifier executed: the whole verify set on the merged head (see C-010 and C-016)
- Result: all green; the legal gate fix was the only red; one first attempt (requestAnimationFrame) was rejected by an existing guard that bans timers on the auth path, so the observer replaced it
- New evidence: the legal pages gate was the second hard-coded copy of the bar height
- Decision: gate-review

## Review round 1

Reviewers on head `84e64ddd` (PR 172), brokered by the coordinator. Comments:

- Shadow, CLEAR (2 Low): https://github.com/First-Pavilion/selahcue/pull/172#issuecomment-5976919528
- Cody, CLEAR (9 non-blocking): https://github.com/First-Pavilion/selahcue/pull/172#issuecomment-5977020898
- Quinn, BLOCKING (1 blocking, 12 non-blocking): https://github.com/First-Pavilion/selahcue/pull/172#issuecomment-5977568559
- Vera, CLEAR (4 non-blocking): https://github.com/First-Pavilion/selahcue/pull/172#issuecomment-5977571224

Fixed in this round:

- Quinn B1: `legal_pages_headless.py` hard-coded a 69px bar and an 82..96px anchor window; it now follows the real bar (79px from 768, 69px below). `test:legal-pages` 395 of 419 before, 419 of 419 after. No other hard-coded bar height in `scripts/` or `tests/` is asserted (the 68px fallbacks and a stale comment are listed in the PR).
- Cody 1: the three global rules with no guard (logo crop, global focus default, `#how-it-works` margin) now have tests that resolve the rule and compare it with the logo file's alpha box, the Figma reference frame and the anchor token; each was mutated and went red.
- Cody 3 and Quinn N1: "How it works" is a custom router-link that renders a plain anchor, so it is never `aria-current`; asserted in node and in the sweep (bar and sheet), mutation-proved.
- Cody 5: the undefined-property guard is scope-aware (global stylesheet or the same file); `var(--nav-cta-hover)` from the footer fails it; its remaining limit is documented and tested.
- Cody 6 and Quinn N3: UiButton transitions named properties, so the focus ring appears at once (2px brand, measured right after Tab).
- Cody 7 and Quinn N8: counts corrected (722 now).
- Cody judgement call 1: DESIGN-TOKENS.md records the web-only muted ink.
- Shadow 2: the sweep asserts bare routes render no navbar or footer, mutation-proved.
- Quinn N5: the mark's ink measured 30 x 32 against Figma's 26 x 28; the crop is tuned to 87.5% of the box and now measures 26 x 28 in the build, guarded.
- Quinn N11: recorded above.
- `reset-r2-04` (found in ClickUp on this ticket after the first handoff, class A in the merged audit data): the primary hover fill is now `--sc-primary-hover-fill` #5f4de6, 5.69:1 with the white label, for every primary including the navbar button (whose private #4f5ec7 hover is removed, so there is one primary hover). The platform `--sc-primary-hover` (#7e6eff) is unchanged: 14 files use it as link ink.
- Vera 1: the scrolled state is observed with an IntersectionObserver on a 10px sentinel instead of read in the first task; the threshold matches the old rule exactly (false at 10px, true at 11px) and a cold load onto a deep anchor starts scrolled.

Declared, no code change: new hover treatments (Cody 4), the first-time Chromium backdrop blur (Vera 2, keep or drop is Uma's), the visible effects outside the chrome (Cody 8), "Windows · macOS" stays with no Linux (Cody 9, shared-chrome-35).

Deferred with a note to the downstream tickets: Shadow 1 (reanchor.ts, Home ticket), Quinn N4, N9, N10, N12, N7 and N2 (page, responsive and Home tickets). Follow-up ticket for Vera 4: https://app.clickup.com/t/17tnw2b2g24 (footer visible under the loading fallback, CLS 0.4).

Not changed on purpose: Quinn N6 (1.5px wider buttons; the border was taken out of the vertical padding only; Figma's own buttons vary by about 2px).

Vera's measurements, recorded as positive results: the logo-load sideways shift is gone (Home CLS 0.0002 to 0), the footer at 1440 is 358px (was 405.5), the bundle grows 630 bytes gzip with the chunk count unchanged, and 120 mount and unmount cycles leak no listener and no heap.

Gates re-run on the merged head (the audit branch final `1b70306d` merged in): see C-009, C-010 and C-016. Harness run `.visual-parity/run-20261004-080255`.

## Risks and rollback

- Risks: the chrome is on every page, so a layout regression is site-wide; the shared `.container` and section tokens move page rhythm for pages that consume them; raising the muted ink changes every consumer by a few percent luminance
- Rollback or recovery: the PR is confined to the chrome files; revert the merge commit. Tokens added are additive except `--section-padding` (no consumers) and the raised `--sc-text-muted`.

## Pause and escalation conditions

- A fix needs a file outside the footprint beyond the named gate edits: stop and report to the coordinator
- A finding turns out to need a design or scope decision: leave it as the audit records it and report it for Uma or the owner
- The harness cannot run (Pillow, Playwright or network): report BLOCKED with the exact missing piece

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cev-figma-shared-chrome.md --completion`
- Validator result: the structural check passes; the completion check fails on C-015 only (independent review is brokered by the coordinator, not requested by this role)
- Independent verification result: pending (Cody, Vera, Shadow and Quinn, brokered by the coordinator on PR 172)
- Terminal state: GATE_REVIEW (all verifiable work done; independent review pending)
- Remaining failed or blocked criteria: C-015
- ClickUp final evidence comment: 1400430000059466 on https://app.clickup.com/t/17tnw2b2cev
