# Goal Contract — 17tnw2b2cex-figma-home

## Identity

- Goal ID: 17tnw2b2cex-figma-home
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Home page matches Figma frame 468:125 section by section for the 24 class A findings and the one code defect the audit assigned to it, ships no claim the repo does not back, and adds no claim the live page does not already make
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cex
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Change `HomeView.vue`, the five Home-only components (`ConsoleMockup`, `OutputManagerMockup`, `TestimonialCard`, `FeatureCard`, `ReliabilityPillar`), one new Home-only icon component, one out-of-footprint line pair in `src/lib/reanchor.ts` (the fragment lookup) and `tests/` so the page composes the shared chrome, tokens, container, `UiButton`, `UiBadge`, `PricingCard` and `FaqAccordion` that PRs 172 and 173 introduced, with Figma's layout, type, spacing and colour, and with every sentence either backed by the repo or already live on the page today.

## Baseline

**Verified** on `origin/web/17tnw2b2cew-shared-components` at `5b203064` (PR 173, which contains PR 172 and the audit PR 171):

- `HomeView.vue` (770 lines) ships a local `.container` (1140 max, 24px gutter = 1092 content), `--section-pad` rhythm with 56px header gaps, literal greys (`#8c97a8`, `#717d93`, `#ffffff`, `#090a0f`, `#12151e`), 800-weight headings, six section labels as `variant="accent"`, `variant="gradient"` on the hero button, a `.cta-btn-white` `!important` override, and no `id` on the steps section.
- The five components render emoji and text glyphs as icons (`📊 📖 📋 🖥️ 📡 🎤 ⚡ 📶 ✓ ✨`), literal hex fills, headings at `h4` (output rows, testimonial names) under an `h2`, and a console mock with no accessible name.
- `src/lib/reanchor.ts:106` runs `document.querySelector(position.el)` on the raw URL hash; Home is an anchored route since PR 172, so a cold load of `/#1abc` or `/#%` makes `querySelector` throw and the one-shot ends as `reapply-failed`.
- `npm run build` exit 0. Harness baseline for Home on this commit: run `.visual-parity/run-20261004-100629`, Chromium SSIM 0.6684 and WebKit 0.6704, build 51 px shorter than the frame; `vp_style_diff` for Home prints 651 lines (saved in the scratchpad as `sd_base_blink.txt`).

## Inputs and evidence sources

- ClickUp 17tnw2b2cex (Goal, Scope, Findings, Acceptance Criteria, and the two hand-over comments from the chrome and components reviews); audit ticket 17tnw2b2c75; epic 86ajy5v6k; claims removal 17tnw2b0x3h; decisions ticket 17tnw2b2cf3
- `docs/design/visual-parity/marketing/findings/home.json` (ids home-04 to home-41 except the C and D ones, home-bug-01) and the audit report `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md`
- Committed Figma style dump `docs/design/visual-parity/marketing/figma-style/home.json` and reference `home.png`; Figma frame 468:125 read through the Figma MCP only for the four copy strings the dump truncates (hero sub, showcase body, NDI and billing FAQ answers) and for the vector path data of the icons
- `docs/design/MARKETING-SITE-HANDOFF.md` sections 2, 3, 5, 6, 7; `docs/decisions/DECISION-LOG.md` DEC-008; PRD CON-3 (licensed translations are later); ADR-0010 (offline transcription by default, cloud opt-in)
- Goal contracts `17tnw2b2cev-figma-shared-chrome.md` and `17tnw2b2cew-shared-components.md`

## Scope

### In scope

- `src/views/HomeView.vue`, `src/components/{ConsoleMockup,OutputManagerMockup,TestimonialCard,FeatureCard,ReliabilityPillar}.vue`, new `src/components/home/HomeIcon.vue` (the feather-style SVG set, Home-only), `tests/` (new files only)
- Home items the chrome and components passes deferred to this ticket: `id="how-it-works"` and its test; `reanchor.ts` decoded `getElementById` (declared out-of-footprint, with node tests); the six labels to `variant="eyebrow"`; `to` on the plan buttons where a real destination exists; the quiet large button at 47px; `variant="gradient"` removed; the shared `.container` and type tokens adopted and the local container rule deleted
- Heading-level fix (home-bug-01) pinned by a test that walks the rendered headings

### Non-goals

- Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, `tokens.css`, `main.css`, `App.vue`, `router/scroll.ts`: shared files, not edited
- Removing claims the live page already makes (`$19`, `/ month`, `MOST POPULAR`, `Cancel anytime`, the invented testimonials, the platform version numbers in the platforms answer, the Church tier): that is ClickUp 17tnw2b0x3h and the decisions ticket 17tnw2b2cf3. Not duplicated here and not added to
- Choosing between the options of the class C and D findings (home-18, 19, 22, 23, 33, 34, 36, 40, 42, 43, 44, 45): raised to Uma and the owner, with the honest state that this change ships recorded below
- The Features, Pricing, Download, About, secondary and auth pages and their files

### Constraints

- Stacked branch `web/17tnw2b2cex-home`, cut from `origin/web/17tnw2b2cew-shared-components`; Draft PR with `--base web/17tnw2b2cew-shared-components`; stack order audit PR 171, then 172, then 173, then this; retargeted and rebased as each lands; the stack merges in order, the same day; never merged by this role
- Owner decisions: honest content wins over Figma (layout and styling followed, no claim the repo does not back); a Figma colour that fails WCAG AA stays accessible in code, recorded as B and flagged to Uma; Figma legacy variables against `--sc-*` is a deliberate layer; the app runs on Windows, Linux and macOS but no page may claim a downloadable macOS or Linux installer and Linux is not added where Figma does not draw it
- Copy rule applied line by line (the copy ledger below): a sentence a finding replaces is replaced by Figma's wording unless Figma's wording is unbacked, in which case the backed part ships and the rest is left out; a sentence no finding replaces is left exactly as it is
- No new token in `tokens.css`; colours are `--sc-*` tokens, with a documented local custom property only for Figma's mock-slide canvases (content, not chrome)
- Memory bounded: static markup only, no timers, observers or growing state
- `git push` with BatchMode SSH; no attribution trailers; no `pkill` by pattern

### Assumptions and unknowns

- **Verified:** Figma draws the showcase columns `items-center` (the 306px mock sits 15px below the 336px text top), so the audit's "top-aligned" is read as the frame's own centring; the harness box positions decide.
- **Decided (owner, 2026-10-04):** the hero "Watch 2-min demo" button stays, disabled, with a visible reason ("Demo video not available yet"), as the Pro plan shows its note. Status quo was a link to `#demo`, which does nothing.
- **Decided (owner, 2026-10-04):** the label "Download free" is kept everywhere, so the Free plan's button goes to `/download`, a page that says honestly that nothing downloads yet (the hero and navbar buttons already do the same).
- **Decided (review round 1):** Church "Talk to us" has no destination and is disabled with "Not available yet": `/contact` waits 800 ms, shows "Message Received ... we will respond within 24 hours" and sends nothing (audit contact-04, 06, 07, ClickUp 17tnw2b0x3h). It goes back to `/contact` once the form really sends; Pricing (PR 178) makes the same change.
- **Decided (owner, 2026-10-04):** 17tnw2b0x3h (claims removal) is implemented after the four area PRs finish review, as a separate branch and PR on top of them, and joins the merge gate. This PR keeps every claim the live page already made exactly as it was.
- **Unknown (Uma):** accessible inks for small brand text and for the three avatar fills (home-44); whether the reliability metric badges, hover lift, hero glow return (home-19, home-22).
- **Unknown (owner):** options of home-18, 23, 33, 34, 36, 40, 42, 43.

## Dependencies and approvals

- PR 171, 172, 173 (stack); PR 172 must not merge before this PR carries `id="how-it-works"`
- Four-reviewer gate brokered by the coordinator, not requested by this role
- The merge gate's named items are listed under Risks and rollback (the stack order, 17tnw2b0x3h, and the owner's acceptance of the -63px on 17tnw2b2cex)
- Three other area tickets run in parallel on other files; no shared file edited here

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Layout: nine sections in Figma's order; content column 1248 at 96px gutters from the shared `.container` (local rule deleted); section rhythm 88/90, hero 96/72, per-section header gaps; Reliability and Testimonials are full-width `--sc-surface` bands with `--sc-border` edges and `--sc-base` cards; showcase 470 / 706 at gap 72. (The ticket's "page within 40px of the frame once the FAQ is ignored" is its own row, C-018, and is not met.) | `vp_style_diff.py --slug home` boxes and y-shifts; per-section height measurement; `tests/homeView.test.ts` source checks | no class A width, height, gap or fill line for home-04, 05, 06, 26; hero, features, reliability, showcase, how it works and the final band exactly the frame's height | Final run on head `066fcee1` (unchanged by the round 1 changes): the shared container (96px gutters; Features grid 1248, cards 402.7 x 218, gap 20; pillars 397 x 223, gap 28; steps 397 x 232, gap 28; plans 400, gap 24; CTA card 1248 x 337; console 1140 x 348; output window 706 x 306, text 470, gap 72, columns centred) measured by `tests/home_page_headless.py` against the frame's numbers, and by `vp_style_diff.py --slug home` on both engines: no width, height, gap or fill line is left for home-04, 05, 06, 26. Section heights against the frame: hero, features, reliability, showcase, how it works and final band +0.0 exactly. The three that differ are explained in C-018. Review round 2: the Showcase title breaks after "moment," and the three designed title breaks are checked as the browser drew them; the hero trust line breaks between its items at 768, 375 and 320. | PASS |
| C-002 | yes | Copy follows the ledger: Figma wording where backed (home-20, 21, 24, 28, 31, 38), the backed part only where Figma overclaims, existing sentences untouched elsewhere; none of the forbidden claims (`NDI 5`, `Wirecast`, `4K`, `60fps`, `alpha`, `NFR-`, `Whisper`, `zero lag`, `Sub-3-second`, `≤3s`, `Add more translations`, `save 20%` in new text, `Priority support`, `Guided onboarding`, a Linux installer) is added | `node --test tests/homeView.test.ts` (rendered text per section, positive and negative) | exit 0; each ledger line pinned; planted claim turns it red | `node --test tests/homeView.test.ts`: 58 tests, the ledger line by line per section plus 18 forbidden claims with a planted sample each; mutations T1 to T9 (NDI 5 and Wirecast, the cold-start number, translations, Priority support, the annual discount, the tech-booth label, "no account", Linux in the platforms answer, the quote marks) each turn it red. | PASS |
| C-003 | yes | Icons are the feather-style SVG set: no emoji and no text glyph used as an icon anywhere in the rendered Home page; every icon is `aria-hidden`; the hero eyebrow carries the brand logo mark; the play glyph is `aria-hidden` | render test over the real tree with a Unicode property scan | zero `Extended_Pictographic` or `✓` outside an `aria-hidden` element; no `✨` | homeView.test.ts: Unicode scan of the rendered page finds no emoji, tick, dot or play glyph; every svg is aria-hidden; the Figma icon names in order; the hero pill holds the 18px `.brand-mark`. Mutations I1 to I4 red. Browser: every svg in main aria-hidden (0 exposed). | PASS |
| C-004 | yes | Hero console mock and Screens & Outputs mock show the designed structure (Preview pane then Live pane; title bar, LIVE chip; rows with thumbnail, name, tag chip, status chip, `+ Add output`), are one `role="img"` with a name and expose none of their fake UI text, contribute no heading | render test; accessibility snapshot in a real browser | one named image each; no `h1`-`h6` inside; PREVIEW before LIVE in DOM order | homeView.test.ts and `home_page_headless.py`: two `role=img` mocks with names, content hidden by `aria-hidden`, PREVIEW before LIVE, rows with thumbnail, name, tag, status and `+ Add output`, no heading, link or tab stop inside; the aria snapshot of `main` names both and reads none of their text. Mutations K1 to K5 and B4 red. | PASS |
| C-005 | yes | The steps section has `id="how-it-works"`; every in-page `#fragment` link on Home, Navbar and Footer resolves to an element id on Home; `reanchor.ts` resolves the decoded fragment with `getElementById`, so `#1abc` and `#%` on the home route end as `reapplied` and `#how-it-works` finds its target | `node --test tests/homeAnchor.test.ts` and a cold load in Chromium and WebKit | exit 0; target lands clear of the 79px bar | `tests/homeAnchor.test.ts` (10 tests) drives the real `reanchorForBrowser`: `#1abc` and `#%` reach "reapplied" (6 of 9 were red on the baseline lookup), a percent-encoded fragment is decoded, the lookup is by id; homeView.test.ts: `id="how-it-works"` on the steps section and every fragment the navbar and footer link to resolves; Home stays synchronous. Browser (the page's font set is stubbed to settle after 250 ms, so the one-shot correction really runs and its `instant` scroll is recorded): a cold load of `/#how-it-works` lands the section 95px from the top (clear of the 79px bar) in Chromium and WebKit, `/#1abc`, `/#%`, `/#%E0%A4%A` and `/#nope` raise no page error, and the navbar link clicked on `/pricing` lands it too. Mutations A1 to A5, B2 red. Caveat found in review round 2 (Vera N2): on a REAL cold load the correction does not run (it reads the font status before Inter starts to load, 24 of 24 cold loads in Chromium) and the section still lands by scroll anchoring; the stub in the script makes it run, so the script proves the lookup, not the timing. Logic unchanged from the base; follow-up in the PR. | PASS |
| C-006 | yes | Pricing teaser: Free reads `$0 / forever`; Free's button goes to `/download` (a link); Pro's and Church's buttons have no destination and show the disabled state with its "Not available yet" note (no billing exists; the contact form sends nothing); the hero demo button is disabled with a VISIBLE reason; no enabled button without an action anywhere on Home | render test over the real tree | exactly one plan link (Free); two disabled plan buttons with `Not available yet`; the demo button disabled and described by a visible note; no link to `/contact` on Home | homeView.test.ts over the real tree: `$0 / forever`; exactly one plan link, Free `/download`; Pro and Church disabled buttons with the note; nothing on Home links to `/contact`; the hero demo button disabled, described by a plain visible sibling note that no class hides or clips; every link goes somewhere and every enabled button is a disclosure. Browser: the note is on screen (width and height, opaque, secondary ink), centred under the button, below it and clear of the trust line, and on screen at 768 and 375. Mutations C1 to C8, R1, R12 to R14, RB1, RB3, RB4 red. Church `to` returns when the contact page tells the truth (17tnw2b0x3h). | PASS |
| C-007 | yes | Type and ink: H1 60/64/700, section H2 per section at 700, card, step and plan titles at the Figma sizes and weights, secondary copy `--sc-text-secondary`, no off-token grey or pure white in Home's CSS; section labels use `variant="eyebrow"`; no `variant="gradient"`; no `!important`; hero button row centred so the quiet large button is 47px next to the 49px solid one | source tests plus `vp_style_diff.py` font and colour lines; computed button heights in a real browser | no class A font, weight, tracking or colour line for home-07, 08, 16; buttons 49 and 47 | Source tests (type tokens, sizes, weights, gaps, bands, gradient token, centred button rows) plus the browser: H1 60/64/700, section titles 40/42/38/44, card, step and plan titles at the Figma sizes, secondary copy `--sc-text-secondary`, hero buttons 49 and 47, final-band buttons 49 and 47. Style diff: no font, weight, tracking or off-token colour line left for home-07, 08, 16. The six labels are `variant="eyebrow"`; no `variant="gradient"`, no `!important`, no local `.container`. Mutations S1 to S10, B1, B3, B5 red. | PASS |
| C-008 | yes | Heading outline never skips a level and has one `h1`; output rows and testimonial names are not headings | render test walking the rendered headings; positive control on a planted skip | exit 0; planted `h4` under `h2` turns it red | homeView.test.ts walks the rendered headings: one h1, no level skipped, card, step and plan titles h3, output rows and testimonial names not headings; the browser re-walks `main` at 1440, 768 and 375. Mutations H1 to H3 red; the CONTROL fails on a planted skip, a second h1 and an outline starting at h2. | PASS |
| C-009 | yes | Contrast of every changed foreground and background pair is AA (or recorded as B or D with its source); no horizontal page scroll at 375, 768, 1440 | pair table from the same luminance formula as `vp_core`; `npm run test:responsive` on Chromium and WebKit | no new failing pair; sweep reports none | Contrast of every changed pair (same luminance formula as the harness): headings 17.97 and 16.71; secondary copy 8.74 on base and 8.12 on surface; hero pill ink 9.62; MAIN tag ink 8.26; white on `--sc-primary` 4.72 (step marker, Add output, SJ avatar, inverse label); LIVE 5.03, PREVIEW 7.10, READY 8.06 on elevated; dark initials 8.38 on green and 10.86 on gold; scripture gold 11.01 and white 19.70 on the slide; white CTA copy 4.72 to 6.18 across the gradient. The harness contrast survey lists no text for Home. `npm run test:responsive` Chromium 0 and WebKit 0, 2315 checks each, no horizontal scroll at 320, 375, 768, 1024, 1440; my own browser check also at 375 and 768. | PASS |
| C-010 | yes | Harness: `visual_parity.py --suite marketing --engine both` for home and the pages that share Home's components (none other consume them; recorded) exits 0; `vp_style_diff.py` for home prints no line that belongs to a class A finding listed in the ticket; every remaining line is named class B, C or D with its owner | `visual_parity.py --only home`, `vp_style_diff.py --slug home --limit 0` on Chromium and WebKit dumps | exit 0; line set compared with the baseline `sd_base_blink.txt` | `visual_parity.py --suite marketing --engine both` exit 0, run `.visual-parity/run-20261004-192536` (all 35 surfaces); Home SSIM 0.6684 and 0.6704 before, 0.8212 and 0.8210 after (Blink and WebKit; run `.visual-parity/run-20261004-192536`). `vp_style_diff.py --slug home --limit 0` on both dumps: 38 and 38 box lines and 122 text lines remain, every one in the list below (token-layer `colour~`/`fill~` lines are the deliberate layer). Only the five Home components are mine and no other page consumes them, so no other page can change from them. | PASS |
| C-011 | yes | Every other offline gate passes with its REQUIRE variable set: `make marketing-check`, `npm test`, `test:states`, `test:responsive` (Chromium and WebKit), `test:legal-pages`, `article_pages_headless.py`, `test:components`, `test:mirrors`, `check:legal`, `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` | each run one at a time, exit code captured unpiped | all exit 0 | On head `e4af73d1` (the round 2 code; the later commits change only this contract), one at a time, exit codes captured unpiped, to my own log directory, `/usr/bin/python3` with `SELAHCUE_HEADLESS_REQUIRE=1` and `SELAHCUE_SWEEP_REQUIRE=1`: `make marketing-check` 0; `npm test` 0 (861 pass); `test:states` 0 (60 scenarios, 1751 checks); `test:responsive` 0 and `responsive_sweep.py --engine webkit` 0 (2315 checks each); `test:legal-pages` 0 (419); `article_pages_headless.py` 0 (143); `test:components` 0 (646); `test:mirrors` 0 (Django 6.1.1 in a scratch virtualenv outside the repo); `check:legal` 0; `home_page_headless.py --engine both` 0 (276 checks, 138 per engine); `visual_parity.py --suite marketing --engine both` 0; `vp_selftest.py` 0 (206); `check_fidelity_audit.py --self-test` 0 (97) and `--require-tickets` 0; `git diff --check` clean. | PASS |
| C-012 | yes | Every new test fails when the thing it guards breaks: each is mutation-proved on a scratch copy | planted faults, one per test group | each turns the named test red | 96 planted faults on scratch copies (node_modules symlinked, the worktree untouched), the unmutated copy green first, each turned the named test red: 51 in the first pass, 23 in review round 1 and 22 in review round 2 (18 node, 4 in a real browser on both engines). Tables below. | PASS |
| C-013 | yes | The diff touches only the footprint, the declared `reanchor.ts` edit, this contract and new test files; no shared file | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths | `git diff --name-only origin/web/17tnw2b2cew-shared-components`: this contract, `HomeView.vue`, the five components, `src/components/home/HomeIcon.vue`, `src/lib/reanchor.ts` (declared), `scripts/responsive_sweep.py` (declared; cherry-pick of `f62b0d04` as `a71d16a6` so all four area branches carry the identical hunk), `tests/homeView.test.ts`, `tests/homeAnchor.test.ts`, `tests/fixtures/renderPage.ts`, `tests/home_page_headless.py`. No shared file from PR 172 or 173. | PASS |
| C-014 | yes | Keyboard order and focus: Tab order is nav, hero buttons (the disabled one skipped), sections top to bottom, footer; every stop shows the focus ring; nothing in the mocks is focusable | Playwright Tab walk on Chromium and WebKit | order as stated; no ring missing; no mock stop | `tests/home_page_headless.py`, Chromium and WebKit: Tab order is Download free, the Free plan's Download free, the five questions, the band's Download free and See pricing; the disabled demo, Pro and Church buttons are skipped; every stop shows a 2px focus outline; nothing in a mock is focusable. WebKit needs Option+Tab on macOS and the script says so. | PASS |
| C-015 | yes | ClickUp: in progress with a start comment; a handoff comment with QA steps as a list; each write read back | ClickUp read-back | present, lists intact | Start comment 1400430000059598 (task set in progress); handoff comment 1400430000059625 with the QA steps as a list (a typo fixed by an update and read back); status moved to code review and confirmed by a list query; the round 1 handoff comment 1400430000059728 and the round 2 handoff comment 1400430000059913 (both read back), and the list comments on 17tnw2b0x3h (1400430000059706) and 17tnw2b2fum (1400430000059707), both read back; all read back. | PASS |
| C-016 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge-order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components`, then the same for the chrome and audit branches | isDraft true; base correct; behind 0 | https://github.com/First-Pavilion/selahcue/pull/180: isDraft true, base `web/17tnw2b2cew-shared-components`, the description opens with the stacked, Draft and merge-order gate text; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` is 0, and so is the count for the shared-chrome and audit branches after the last fetch (all three heads unchanged: 5b203064, 066d3a90, 191287ff). | PASS |
| C-017 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | Round 1 at `4c8ec794`: Shadow BLOCKING (1: the Church "Talk to us" button sent a visitor to a form that sends nothing, the same fault Cody raised, PR comment 5981640917) and Cody BLOCKING (1 and 11 non-blocking, 5981756155). Round 2 at `4572bfb5` (code head `e8732233`): Shadow CLEAR (5982129832, the blocker and all five non-blocking items fixed), Cody CLEAR (5982214201, 4 new Low), Quinn CLEAR (5982415054, 7 non-blocking), Vera CLEAR (5983297177, 1 Low and 1 Info). 0 blocking. The final pass (code head `e4af73d1`, head `8484ca64`) fixed the round 2 findings (attribute text in the copy allow-list, the named live-claims list, the colour scan, the Showcase title break, the hero trust line, the Inter probe), each with tests mutation-proven on a scratch copy. None of it was re-reviewed by the reviewer who raised the finding. The orchestrator verified at `8484ca64`: mergeable, base `web/17tnw2b2cew-shared-components`, 0 behind, `4572bfb5` an ancestor, no shared component, token, router or App file touched, and the diff since the reviewed head is only `HomeView.vue`, `tests/homeView.test.ts`, `tests/home_page_headless.py` and this contract. The gate results at this head are the author's; the orchestrator did not re-run them, and CI on the PR is the independent run. This row is the independent review only. C-018 (the 63px shortfall against the frame) stays BLOCKED on the owner's written acceptance and is a named item on the stack merge gate, beside the claims ticket 17tnw2b0x3h. Closed by the orchestrator 2026-10-04 | PASS |
| C-018 | no | The ticket's acceptance criterion: the page is within 40px of the frame's height once the FAQ is ignored | per-section height measurement (`secs.py`, Playwright) and the harness line for home | each section within 40px and the page within 40px of 6814 without the FAQ difference | NOT MET. Home is 316px shorter than the frame (6498 against 6814). FAQ -253 (class B home-37, collapsed by design, which the ticket says to ignore). Without it the page is 63px short: pricing -89 (class C: the cards lose bullets the repo does not back, and the Pro description loses its annual sentence) and testimonials +26 (class C home-36: the three live quotes wrap to four lines). It can only be met by shipping the unbacked bullets or changing the live quotes, which the honest-content decision forbids and 17tnw2b0x3h owns. DECISION NEEDED: the owner accepts the -63 on the ticket, after which this row is reworded and passes; until then it stays open and is not counted as PASS. | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Copy ledger

Every line of Home copy, with where it comes from. Figma wording is used verbatim unless the line says otherwise.

- Hero: eyebrow, H1, sub, `Download free`, trust line: unchanged text (equal to Figma). `Watch 2-min demo`: label unchanged (the removal of the claim belongs to 17tnw2b0x3h); the control is disabled, with a VISIBLE reason under it, "Demo video not available yet" (owner decision 2026-10-04, as the Pro plan shows its "Not available yet"), wired to the button with `aria-describedby`.
- Features: subtitle verbatim. Blurb 1, 3, 4 verbatim. Blurb 2 drops "Add more translations any time" (PRD CON-3: licensed translations are later). Blurb 5 keeps "NDI source for OBS or vMix" and the per-output settings, drops "any feed". Blurb 6 drops "captions" and "computed entirely on-device" and says the transcript and suggestions run on the machine by default (ADR-0010, home-43). Card titles unchanged.
- Reliability: eyebrow `WHY SELAHCUE`, subtitle and pillar 1 verbatim; pillar 2 reads "Every core live control works with no internet and no cloud dependency during the service. It just works." (Figma says "Everything runs on-device"; NFR-015 backs core live functions only, and sign-in, activation and the first speech-model download need the network; "no account" is also gone, DEC-007); pillar 3 reads "Starts fast and keeps memory bounded" without the number (home-23, the owner's own wording option); the three metric badges are not drawn (the frame has none; home-22, Uma).
- Showcase: eyebrow, H2, body and the three one-line checks verbatim (NDI named only as an output for OBS, vMix or another machine, home-42).
- How it works: subtitle and the first two step bodies verbatim; step 3 reads "Drive it from the console — or pair your phone over the local network. No internet needed." (Figma adds "no lag, no surprises": an unmeasured promise, the PRD targets under 200 ms on the LAN).
- Pricing: subtitle verbatim (it drops the live "save 20% annually" sentence); Free: description and three bullets verbatim, "One physical output" left out (DEC-008 gives Free two outputs); Pro: description without "Billed monthly, or save 20% yearly", bullets "Everything in Free", "NDI + multiple simultaneous outputs", "Mobile control over your local network"; "Theme Designer & saved templates", "On-device transcript & scripture detection" and "Always on the latest version" are left out (tier gating DEC-008 does not decide; no update channel ships); Church: description verbatim, button disabled with "Not available yet" (the contact form sends nothing, audit contact-04, 06, 07), bullets "Everything in Pro" and "Multi-campus / site licensing" (the live page already says multi-campus); "Guided onboarding & training" and "Priority support" left out (no such service exists). `$19`, `/ month`, `MOST POPULAR`, `Custom` stay as they are today (home-33, 17tnw2b0x3h).
- Testimonials: quotes, names and churches unchanged (home-36); the role separator becomes `·` and the quotes get typographic marks (the finding's format change); the label stays `TESTIMONIALS`, not Figma's `FROM THE TECH BOOTH`, which would attribute the live quotes to tech teams (home-36).
- FAQ: the five Figma questions. Answer 1 reads "No. SelahCue is offline-first — every core live control works with no internet, so a dropped connection never stops the service." (not "the whole service runs on-device": NFR-015). Answer 2 keeps the live platforms answer unchanged (home-38, 40, 45 held). Answers 3 and 4 verbatim. Answer 5 is Figma's wording with "or annual" taken out ("a simple monthly subscription"), because the repo has no annual plan; "free forever" and "Cancel anytime" are already live in this answer and stay (home-33).
- Final CTA: H2 and sub unchanged text; buttons `Download free` and `See pricing`.

## Findings: closed and not closed

Closed (the harness lines they named are gone, and a test pins each): home-04, 05 (see C-001 for the three sections that differ and why), 06, 07, 08, 09, 11, 12, 13 (the skeleton the finding asks for is not built: the mock is static markup in a fixed-size box, there is nothing loading that could shift the layout), 14, 16, 17 (the play mark is an SVG and the button is disabled with a visible reason, see the decisions), 20, 21, 24, 25, 26, 27, 28, 29, 31, 35 (typography, avatar, role and quote format; the label and the quotes are held by home-36), 38 (the five questions and sizes; answers narrowed or held as the copy ledger says), 41, and the defect home-bug-01.

Reclassifications: none of the findings changes class. Two readings are corrected: home-26 says the showcase is "top-aligned"; the frame centres the columns (the 306px window sits 15px below the 336px text column's top, which is what `align-items: center` gives), so the build centres them. home-12/25 draw status dots as the text glyph `●` and home-17 a `▶` glyph; the acceptance criteria forbid text glyphs as icons, so they are CSS dots and an SVG (class B, same look).

## Remaining differences against the frame (Home, 1440 wide, both engines identical)

- Token layer (deliberate, AUTH-LANDING-PAGES-HANDOFF 2.2): every `colour~`, `fill~` and `border-colour~` line.
- Class D home-44 (Uma picks the tint): eyebrows (`#5b6bd6` against the readable default ink), the MAIN tag and the hero pill (`#a5b4fc`, class B home-15).
- Class B: the CTA sub copy is white against Figma's `#dbe0fa` (3.61:1 on the lightest end of the gradient); the status dots and play mark are CSS and SVG, not text glyphs; the FAQ ships collapsed with the first answer open (home-37), so the FAQ is 253px shorter and its rows 71 against 133.
- Class C, honest narrowing, held for the owner: features blurbs 2, 5 and 6 (CON-3, home-42, home-43), reliability pillars 2 and 3 (DEC-007, home-23), the Pro description (home-33), the plan bullets (Free loses one, Pro three, Church two; the cards are 31, 89 and 62px shorter, home-33 and home-34), the Church button (disabled until the contact form sends), FAQ answers 1, 4 and 5; the three live testimonials against Figma's invented ones, and the label (home-36), which also make the band 26px taller.
- Shared files, not mine: the FAQ rows' rule above and below and the `+` glyph (FaqAccordion), the Pro card's "Not available yet" note, the plan buttons' elevated fill, "/ month" 3.6px left (PricingCard), the nav bar's bottom border, the footer's Affiliates ink.
- Build-only: the visible sentence under the demo button that says why it is disabled (owner decision, 2026-10-04).

## Decisions and hand-offs

For Uma and the owner (class C and D, not decided here): the hero demo button's final form (home-18: the owner chose "keep, disabled, with a visible reason"; remove or relabel stay open for later); the metric badges (home-22: not drawn); the hero glow and card hover lift (home-19: kept as they were); the wordings chosen for home-23, 42 and 43; the accessible tints for small brand text and the dark initials on the green and gold avatars (home-44); the platforms answer (home-38, 40, 45: unchanged, Linux not added, no installer claimed); whether Home should say that Free output carries a watermark (DEC-008).

For the coordinator (shared files, not edited): `FaqAccordion.vue` defaults (questions 18/600, answers 15.5/24, 10px between an open question and its answer, the rule above rows 2 to 5; Home skins it with a `:deep` block in `HomeView.vue`, guarded by a node test, to delete when the shared change lands: a shared-components follow-up); `PricingCard.vue` (Free and Church buttons are the elevated secondary button in Figma 477:137 and 477:200); `package.json` is NOT edited here (the Pricing branch adds `test:core` in the same block and two edits would conflict at merge): the exact lines to wire `tests/home_page_headless.py`, `tests/core_pages_headless.py`, `tests/secondary_pages_headless.py` and `scripts/shared_components_headless.py` into CI are on follow-up ticket 17tnw2b2fum (comment 1400430000059707), whose title covers only the self-tests, so the scope there must be widened; the sweep's permanent 24 or 96 px acceptance is on the same ticket.

## Mutation proof

Each fault was planted alone in a scratch copy of `implementation/marketing` (src, tests and public copied, `node_modules` symlinked, the worktree untouched), after the unmutated copy passed `tests/homeView.test.ts` and `tests/homeAnchor.test.ts`; each turned the named test red. The browser faults (B, RB) build the mutated copy and run `tests/home_page_headless.py --engine both`.

First pass (51 faults):

- A1: the old raw-hash querySelector lookup: red, 6 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- A2: decode without the catch (#% throws): red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- A3: no percent-decoding: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- A4: the steps section loses its id: red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- A5: Home gets a top-level await: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- H1: testimonial name becomes an h4 again: red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- H2: output row name becomes an h4 again: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- H3: feature title skips a level (h2 to h4): red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- I1: the sparkle emoji returns: red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- I2: icons lose aria-hidden: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- I3: the logo mark is replaced: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- I4: feature icons rendered as text again: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- K1: the console mock loses role=img: red, 5 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- K2: the console mock content is not aria-hidden: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- K3: the first pane is LIVE again: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- K4: "+ Add output" becomes a real button: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- K5: hyphen instead of the em dash: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C1: the demo button is a link to #demo again: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C2: the disabled demo button loses its reason: red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C3: Free reads $0 / month: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C4: Free loses its destination: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C5: Pro gets a destination that does not exist as a purchase: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C6: the band button is not the inverse-outline variant: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C7: the hero button is variant gradient again: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- C8: a section label is a filled chip again: red, 3 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T1: NDI 5 and Wirecast are added: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T2: the cold-start number returns: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T3: the unbacked translations claim returns: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T4: Priority support is added to Church: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T5: the annual discount is added to Pro: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T6: the tech-booth label is added: red, 6 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T7: "no account" returns: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T8: Linux is added to the platforms answer: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- T9: the quote loses its typographic marks: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S1: an off-token grey returns: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S2: an !important appears: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S3: the feature grid gap is 24 again: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S4: the showcase columns are top aligned: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S5: the hero button row stretches its buttons: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S6: the CTA glow shadow returns: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S7: the local 1092px container returns: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S8: the Reliability band loses its panel fill: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S9: white initials on the green avatar: red, 2 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- S10: the H1 is 58/800 again: red, 4 failing (tests/homeView.test.ts or homeAnchor.test.ts)
- B1: the hero row stretches the quiet button to 49px: red, 2 failing lines (tests/home_page_headless.py, both engines)
- B2: the steps section loses its id: red, 6 failing lines (tests/home_page_headless.py, both engines)
- B3: step card padding is 32/28 again (234 tall): red, 2 failing lines (tests/home_page_headless.py, both engines)
- B4: the mock text is exposed to the aria snapshot: red, 2 failing lines (tests/home_page_headless.py, both engines)
- B5: the showcase is 50/50 again: red, 6 failing lines (tests/home_page_headless.py, both engines)
- B6: white initials on the gold avatar: red, 2 failing lines (tests/home_page_headless.py, both engines)
- L1: the space before the designed line break in the Reliability title removed: red, 1 failing (tests/homeView.test.ts)

Review round 1 (23 faults, runner `mutate-r1.py` in the private scratch directory):

- R1: Church goes to /contact again (the form that sends nothing): red, 4 failing (tests/homeView.test.ts)
- R2: "Everything runs on-device" returns in the pillar: red, 5 failing (tests/homeView.test.ts)
- R3: "the whole service runs on-device" returns in the FAQ: red, 5 failing (tests/homeView.test.ts)
- R4: "no lag" returns in step 3: red, 5 failing (tests/homeView.test.ts)
- R5: the logo size is a style attribute again: red, 3 failing (tests/homeView.test.ts)
- R6: the hero glow types the brand colour out as rgba: red, 2 failing (tests/homeView.test.ts)
- R7: the icon lookup reads inherited properties again: red, 2 failing (tests/homeView.test.ts)
- R8: a sentence nobody banned ("Trusted by 5,000 churches.") is added: red, 2 failing (tests/homeView.test.ts)
- R9: the FAQ skin loses its 18px rule: red, 2 failing (tests/homeView.test.ts)
- R10: the FAQ skin reaches into a class that does not exist: red, 2 failing (tests/homeView.test.ts)
- R11: the shared accordion renames .faq-question (scratch copy only): red, 2 failing (tests/homeView.test.ts)
- R12: the demo note is clipped off the screen: red, 2 failing (tests/homeView.test.ts)
- R13: the demo note is a screen-reader-only class again: red, 2 failing (tests/homeView.test.ts)
- R14: the demo note says something else: red, 5 failing (tests/homeView.test.ts)
- R15: an hsl() literal replaces a token: red, 2 failing (tests/homeView.test.ts)
- R16: a style attribute appears on the page: red, 2 failing (tests/homeView.test.ts)
- R17: an unlisted sentence is added to a plan: red, 3 failing (tests/homeView.test.ts)
- RB1: Church goes to /contact again: Tab order gains a stop: red, 2 failing lines (tests/home_page_headless.py, both engines)
- RB2: the correction ignores the bar clearance (it now really runs in the browser): red, 1 failing lines (tests/home_page_headless.py, both engines)
- RB3: the demo note is display:none: red, 8 failing lines (tests/home_page_headless.py, both engines)
- RB4: the demo note lands on the trust line: red, 4 failing lines (tests/home_page_headless.py, both engines)
- RB5: the page asks a third party for an image: red, 2 failing lines (tests/home_page_headless.py, both engines)
- RB6: Inter is blocked: the probe must fail instead of measuring the fallback face: red, 12 failing lines (tests/home_page_headless.py, both engines)

Review round 2 (22 faults, runner `mutate-r2.py` in the private scratch directory; the browser ones require the named failure in BOTH engines):

- P1: a claim in the console mock aria-label: red, 4 failing (tests/homeView.test.ts)
- P2: a claim in the output window aria-label: red, 4 failing (tests/homeView.test.ts)
- P3: a claim in a title on the hero button: red, 2 failing (tests/homeView.test.ts)
- P4: a claim in the logo alt: red, 4 failing (tests/homeView.test.ts)
- P5: a claim in an aria-label on the trust line: red, 2 failing (tests/homeView.test.ts)
- P6: "Cancel anytime" is reworded stronger: red, 4 failing (tests/homeView.test.ts)
- P7: the Mobile control bullet is reworded: red, 2 failing (tests/homeView.test.ts)
- P8: the final band sub gains a claim: red, 2 failing (tests/homeView.test.ts)
- P9: the test file vouches for a live claim again (a named-list entry added to the ledger): red, 2 failing (tests/homeView.test.ts)
- P10: an oklch() literal replaces a token: red, 2 failing (tests/homeView.test.ts)
- P11: a named colour replaces a token: red, 4 failing (tests/homeView.test.ts)
- P12: a named colour in a border shorthand: red, 2 failing (tests/homeView.test.ts)
- P13: a literal colour in a template fill: red, 2 failing (tests/homeView.test.ts)
- P14: the Showcase title loses its designed break: red, 3 failing (tests/homeView.test.ts)
- P15: the Showcase title runs two words together without its br: red, 3 failing (tests/homeView.test.ts)
- P16: the Showcase break is not hidden on a phone: red, 2 failing (tests/homeView.test.ts)
- P17: the trust line breaks inside an item again: red, 2 failing (tests/homeView.test.ts)
- P18: no breakable space after a dot: red, 2 failing (tests/homeView.test.ts)
- PB1: the trust line splits an item at 375 and 320: red, 4 failing lines (tests/home_page_headless.py, both engines)
- PB2: the Showcase title breaks after "every": red, 2 failing lines (tests/home_page_headless.py, both engines)
- PB3: the Reliability title loses its break: red, 2 failing lines (tests/home_page_headless.py, both engines)
- PB4: the font hosts are blocked: the Inter check itself must go red in both engines: red, 14 failing lines (tests/home_page_headless.py, both engines)

Why the old Inter check is replaced (PB4): with the font hosts blocked, `document.fonts.check('600 16px Inter')` is `true` in Chromium and WebKit (no Inter face exists, so there is nothing to fail); the new check, a loaded `FontFace` of family Inter for each of 400, 600 and 700, is `[false, false, false]` in both (probe `inter_probe.py`).

## Review round 1

Comments on PR 180 at head `4c8ec794`:
- Shadow (security and privacy), BLOCKING 1, non-blocking 5: https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5981640917
- Cody (code), BLOCKING 1, non-blocking 11: https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5981756155

Owner decisions received 2026-10-04: the DEC-008 plan limits are published as they are; the label "Download free" is kept everywhere; the hero demo button stays, disabled, with a VISIBLE reason; claims removal (17tnw2b0x3h) is a separate branch and PR on top of the four area PRs and joins the merge gate, so this PR keeps every pre-existing live claim exactly as it was.

Dispositions (the coordinator closes C-017):
- Shadow B1 and Cody B1 (the same finding): fixed. Church "Talk to us" has no destination and is disabled with "Not available yet" (`HomeView.vue`); the pins are `tests/homeView.test.ts` (exactly one plan link, nothing on Home links to `/contact`) and the Tab order in `tests/home_page_headless.py`; the QA step in the PR description is changed. The honest reason is in the assumptions above: it gets a real destination once the contact form sends (17tnw2b0x3h). Mutations R1 and RB1 red.
- Shadow N1 and Cody N2: fixed. Pillar 2 and FAQ answer 1 say what NFR-015 backs ("every core live control works with no internet"); `FORBIDDEN` gains `/Everything runs on-device/i` and `/whole service runs on-device/i` with planted samples. R2, R3 red.
- Shadow N2: fixed. The logo size is the scoped rule `.hero-eyebrow .brand-mark { --mark-size: 18px }`; a node test and a browser check assert the page has no `style` attribute. R5, R16 red.
- Shadow N3: fixed. `tests/home_page_headless.py` aborts every request that is not to its own loopback server. One explicit allow stays for `fonts.googleapis.com` and `fonts.gstatic.com`, on purpose: the heights it checks are the heights of text in Inter, so the run checks that Inter loaded and fails if it did not, and fails if the page asks any other third party for anything. The cold-load checks now stub the font set (as Shadow's probe did) so the one-shot correction really runs in the browser and its `instant` scroll is recorded. RB2, RB5, RB6 red.
- Shadow N4 (info): the three invented testimonials are more prominent after the restyle. Recorded on 17tnw2b0x3h (comment 1400430000059706), nothing changed here by the owner's decision.
- Shadow N5: fixed. `Object.hasOwn(ICONS, props.name)`; a node test renders `__proto__`, `constructor`, `toString`, `hasOwnProperty` and `valueOf` and requires no svg. R7 red.
- Cody N1: fixed. C-001 is reworded to what is true (six sections exactly the frame's height, PASS) and the ticket's 40px criterion is its own row, C-018, marked BLOCKED with the numbers and the decision it needs (the owner accepts the -63).
- Cody N3: fixed. `tests/homeView.test.ts` now has one copy ledger (every block of text, per section, in order) and a named list of the live claims no finding replaces (each with its reason); an allow-list test fails on any rendered block of text that is on neither. Planting "Trusted by 5,000 churches." (his M14) or "Dedicated account manager." turns it red. R8, R17 red.
- Cody N4: fixed. A node test pins the three FAQ overrides and their numbers, and that the rendered accordion still has the classes they reach into (a rename in `FaqAccordion` fails it; R11 does that in a scratch copy). The shared change (FaqAccordion defaults) is listed above as a shared-components follow-up; `FaqAccordion` is not edited. R9, R10, R11 red.
- Cody N5: posted. 17tnw2b2fum read back (its title and scope cover only the self-tests); the exact CI lines for the four browser scripts, and a step to tighten the sweep (N11), are on it (comment 1400430000059707). The references in this contract and the PR now say so. `package.json` is not edited, to avoid a conflicting hunk with the Pricing branch.
- Cody N6: the owner decided: the demo button stays, disabled, with a visible "Demo video not available yet" under it, wired by `aria-describedby`. Tests and browser checks pin it (not hidden, not clipped, on screen, clear of the trust line at 1440, 768 and 375). R12 to R14, RB3, RB4 red. The label is on 17tnw2b0x3h's list.
- Cody N7: posted on 17tnw2b0x3h (comment 1400430000059706), as a list, with the claims it did not name.
- Cody N8 (tier gating applied unevenly), N9 (three inks for small brand text): recorded in the PR description under "Not decided here". The rule that was applied: a line that would newly gate a feature between tiers (Theme Designer, transcript, "latest version") was left out; lines the live page already carried (Free "themes", Pro "Mobile control") were left as they were, and "Mobile control" is on 17tnw2b0x3h's list.
- Cody N10: fixed. `homeAnchor.test.ts` is 10 tests (the contract and PR said 11); the hero glow uses `color-mix()` of the brand token and the colour scan now covers `rgb()`, `rgba()` and `hsl()` literals (R6, R15 red); "No lag" is gone from step 3 and `/\bno lag\b/i` is a forbidden row (R4 red); the trailing spaces and cut-off words in the mutation tables are gone (`git diff --check` is clean). `.visually-hidden` is no longer declared in this view (the note is visible); Blog and Support keep their own `.sr-only`, and a shared utility would be a `main.css` (chrome) change, listed in the PR.
- Cody N11: posted on 17tnw2b2fum (comment 1400430000059707): tighten the sweep to 96 / 48 / 20 once every page has migrated.

## Review round 2

Comments on PR 180 at head `4572bfb5` (code head `e8732233`): all four reviewers CLEAR, 0 blocking.
- Cody (code): https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5982214201
- Quinn (QA): https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5982415054
- Shadow (security and privacy): https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5982129832
- Vera (performance): https://github.com/First-Pavilion/selahcue/pull/180#issuecomment-5983297177

Shadow had nothing open. The remaining non-blocking items, each with a disposition (C-017 stays the coordinator's):
- Cody N-A and Quinn N4 (the allow-list read visible text only; "trusted by 5,000 churches" in an `aria-label` or a `title` stayed green): fixed. `blocks()` now also reads `aria-label`, `aria-description`, `aria-roledescription`, `title`, `alt` and `placeholder`; the two mock labels are on the ledger; controls plant the claim in each attribute. P1 to P5 red.
- Cody N-B and Quinn N7 (the named list was shorter than the owner's list on 17tnw2b0x3h): fixed. "Cancel anytime" (title, subtitle, FAQ 5, band), the Mobile control bullet, "controlled from anywhere" and "Control from anywhere", "Start free and go live this Sunday", "a simple monthly subscription" and "Trusted on Sunday" moved from the ledger to the named list, each with a reason, and a test fails if a named-list entry is also on the ledger (the test file does not vouch for them). Quinn's three thin lines are there too: "each with its own theme", "give any item its own theme", "Everything to run a service on one machine.", and "in minutes, no manual, no setup weekend". P6 to P9 red.
- Cody N-D (the colour scan was a list of function names): fixed. The scan is now an allow-list over every colour-bearing declaration (`var(--...)`, `color-mix()` of tokens, `transparent`, `currentColor`, the documented hexes, the documented `rgba()` channels); any other colour, in any notation (a name, `oklch()`, `hwb()`, `lab()`, `lch()`, `color()`, `light-dark()`, inside `color-mix()`, in a `var()` fallback) is reported; a template `fill=` or `stroke=` literal too. `oklch()` and `rebeccapurple` planted: red. P10 to P13 red.
- Quinn N2 (the Showcase title broke "One live moment, every / output"): fixed. A designed `<br />` after "moment,", hidden under 768 like the other titles' breaks; pinned by a node test and by a browser check of the lines the browser drew (hero, Reliability and Showcase titles). P14 to P16, PB2, PB3 red.
- Quinn N3 (the hero trust line wrapped inside a phrase at 375): fixed. Each of the three items is held together with non-breaking spaces and the break is between items; a browser check at 768, 375 and 320 requires that no item is split across lines. P17, P18, PB1 red.
- Vera N1 (the "Inter loaded" check could not fail): fixed. A loaded `FontFace` of family Inter for each of 400, 600 and 700; the docstring says what it does and why `document.fonts.check()` is not used. With the font hosts blocked it fails in both engines. PB4 red.
- Cody N-C and Quinn N1 (C-018 is non-mandatory, so the validator ignores it): the owner's written acceptance of the -63px is now a named item on the stack merge gate, in Risks below and in the PR description. C-018 stays BLOCKED.
- Vera N2 (recorded, no code change): `reanchorForBrowser` reads `document.fonts.status` when `router.isReady()` resolves, before Inter has started to load, so on a real cold load the one-shot correction returns `fonts-already-loaded` and does nothing (24 of 24 Chromium cold loads). The section still lands (95px at 768 and 1440, 85px at 375) through scroll anchoring and fixed line heights; the logic is unchanged from the base. The browser script only sees the correction because its font-set stub reports `loading`; the comment in the script now says so. Follow-up, listed in the PR under "Not decided here".
- Quinn N6 (recorded): the Home FAQ says "macOS 12+" and `/download` says "macOS 11.0 or later". Named in the PR under "Not decided here"; already on the claims list.
- Quinn N5 (recorded): `tests/home_page_headless.py` is wired nowhere; the existing line stays on 17tnw2b2fum.
- Quinn, "differences the fix missed": section subtitles sit 3 to 5px lower and the hero title 4px higher than the frame (style-diff y-shifts, text box metrics). Cosmetic, listed in the PR as a remaining difference, not changed.

## Verification plan

- Focused verification: C-001 to C-008 by test-first node tests (`tests/homeView.test.ts`, `tests/homeAnchor.test.ts`, `tests/homeIcons.test.ts`) shown failing on the baseline, then the harness style diff
- Broader regression verification: C-009 to C-014 (all offline gates, harness, contrast, keyboard)
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium, WebKit), network for Inter, Django in a scratch virtualenv outside the repo for `test:mirrors`; four Farah instances share the machine, so ephemeral ports and a re-run before reporting a gate that dies oddly

## Iteration ledger

### Iteration 1

- Target criterion: all (baseline)
- Hypothesis: the baseline is green and the 24 findings reproduce from the committed style diff
- Change or investigation: read the ticket and its two comments, the audit data for home, the marketing handoff, the shared components from PR 172 and 173, DEC-008, PRD CON-3, ADR-0010; read Figma frame 468:125 for the truncated strings and the icon vector paths; built and ran the harness
- Verifier executed: `npm run build` exit 0; `visual_parity.py --suite marketing --engine both --only home` exit 0
- Result: baseline recorded; the sparse truth about which claims are backed is in the copy ledger
- New evidence: Figma centres the showcase columns; the CTA sub colour `#dbe0fa` is 3.61:1 on the lightest end of the gradient, so the sub copy ships white (B)
- Decision: iterate

### Iteration 2

- Target criterion: C-002 to C-008
- Hypothesis: the page can be pinned by render tests over the real tree plus source tests, and each goes red on the baseline
- Change or investigation: wrote `tests/homeAnchor.test.ts` and `tests/homeView.test.ts` first (on the baseline: 5 of the first 9 anchor tests red, and the Home tests for the container, section titles, eyebrows, the id, glyphs, mocks, headings and icons red; a stand-in browser whose `querySelector` throws on the selectors a browser rejects, so the old lookup fails here for the real reason), then `reanchor.ts`, `HomeIcon.vue`, the five components and `HomeView.vue`
- Verifier executed: `node --test tests/homeView.test.ts tests/homeAnchor.test.ts`; `npm run lint`; `vue-tsc`; the full `npm test`
- Result: green, except one existing guard (`tokens.test.ts`) that rightly refused a custom property declared in one component and used in another: the mock now declares its own ink
- New evidence: the harness style diff moved Home from SSIM 0.67 to 0.77; hero and feature geometry were off by the border (Figma measures padding from the outer edge) and by two line heights
- Decision: iterate

### Iteration 3

- Target criterion: C-001, C-004, C-010
- Hypothesis: geometry can match the frame to the pixel once padding, line heights and the two mocks are measured from the dump
- Change or investigation: took the 1px border off every outer-edge padding, fixed the hero pill, the trust line (one text node, as Figma draws it), the checklist line height, the titles' line heights and the explicit break in the Reliability title; wrapped each mock's content in `aria-hidden` after the aria snapshot showed Playwright still reads children of an image; wrote `tests/home_page_headless.py` (212 checks) and fixed the test for what it found (a hash-only goto is not a cold load, WebKit needs Option+Tab)
- Verifier executed: the harness for Home on both engines, `home_page_headless.py`, the per-section height measurement
- Result: six of nine sections exactly the frame's height; hero console 1140 x 348 at x=150, feature cards 402.7 x 218 at the frame's y; SSIM 0.82
- New evidence: `responsive_sweep.py` expects 24px at desktop for any page container and fails on the shared 96px `.container` (a gate-script edit outside the footprint; the Pricing branch made the same edit, so its commit was cherry-picked)
- Decision: iterate

### Iteration 4

- Target criterion: C-011, C-012
- Hypothesis: every gate passes on the final head and every new test fails when its fault is planted
- Change or investigation: 51 planted faults on scratch copies; a missing word space before the Reliability title's `<br>` found by the harness's text dump (textContent read "momentyou") and pinned by a new test; the scratchpad is shared by all four area instances and one instance ran this ticket's gate script by mistake and overwrote three logs, so every gate was re-run on the final head into a private directory
- Verifier executed: see the predicate table
- Result: all PASS except C-017, which is the coordinator's
- New evidence: see the findings sections above
- Decision: handoff

### Iteration 5 (review round 1)

- Target criterion: C-001, C-005, C-006, C-011, C-012, C-018
- Hypothesis: the two blockers (one finding) and the non-blocking findings can be fixed inside the footprint, each with a test that goes red without the fix
- Change or investigation: read both comments in full; wrote the tests first (the plan test, the copy ledger and its allow-list, the style-attribute test, the own-property icon test, the FAQ skin test, the rgb/hsl colour scan, the visible-note test, a hermetic browser script with the font set stubbed), watched them go red, then changed `HomeView.vue`, `HomeIcon.vue` and the script; two owner decisions arrived while working (a visible demo note; claims removal on top of the area PRs) and were applied; 23 planted faults on scratch copies; read back and appended to ClickUp 17tnw2b2fum and 17tnw2b0x3h
- Verifier executed: see the predicate table
- Result: all PASS except C-017 (the coordinator's) and C-018 (the ticket's 40px, not met for content reasons and BLOCKED on an owner decision)
- New evidence: the earlier browser script never ran the cold-load correction (a fast font load returns "fonts-already-loaded"); with the font set stubbed it does, and breaking the clearance turns it red
- Decision: handoff

### Iteration 6 (review round 2)

- Target criterion: C-010, C-011, C-012, C-018 (and the gate item)
- Hypothesis: the seven remaining non-blocking items can be fixed in the footprint with tests that fail when they break, and the owner's -63px acceptance can be made a named gate item
- Change or investigation: read all four reviews; wrote the tests first where the code was already right (announced attributes, the named list, the allow-list colour scan, the Showcase title, the trust line, the Inter probe), watched the controls go red against the old scan and the old check, then changed `HomeView.vue` and the script; 22 planted faults on scratch copies; a probe showing the old Inter check passes with the font hosts blocked and the new one does not; every gate re-run on the result
- Verifier executed: see the predicate table
- Result: all PASS except C-017 (the coordinator's) and C-018 (BLOCKED on the owner)
- New evidence: on a real cold load the anchor correction never runs (Vera N2); the earlier "fast local font load" explanation in the script was wrong, the cause is the time of the status read
- Decision: handoff

## Risks and rollback

- Risks: a page-wide restyle can regress the responsive layouts that PR 172 and the existing sweep pin; the new copy removes sentences some reader may expect; the disabled demo button changes the hero
- Rollback or recovery: one revert of this PR restores the previous Home; no shared file, schema or route changed

### Merge gate (named items; this PR does not go Ready until every one is met)

- The stack merges in order, the same day: audit PR 171, then 172, then 173, then this one. PR 172 must not merge before this PR (it carries `id="how-it-works"`).
- ClickUp 17tnw2b0x3h (claims removal) is built after the four area PRs finish review, as a separate branch and PR on top of them, and is on the gate (owner decision, 2026-10-04).
- **The owner's written acceptance of the -63px shortfall (acceptance criterion 1b: pricing -89 and testimonials +26 once the FAQ is ignored) on ClickUp 17tnw2b2cex, and the criterion reworded to match.** Until then C-018 stays BLOCKED, the ticket does not move to Done, and this PR does not go Ready. The goal validator ignores non-mandatory rows, so this item is written here and in the PR description and not left to the validator.
- Church "Talk to us" (and Pricing's Platinum) get `to: '/contact'` back only when the contact page tells the truth (17tnw2b0x3h).

## Pause and escalation conditions

- A fix that needs a shared file (FaqAccordion defaults, UiBadge ink, PricingCard, UiButton): stop and report the exact change to the coordinator
- A class C or D choice that cannot be left as the honest state: Uma or the owner
- Three materially different failed attempts on one criterion without new evidence: `FAILED_LIMIT`

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cex-figma-home.md --completion`
- Validator result: the structural check passes and the completion check passes (C-017 closed by the orchestrator on 2026-10-04; C-018 is non-mandatory and BLOCKED on the owner, a named item on the merge gate)
- Independent verification result: round 1 at `4c8ec794` (Shadow 5981640917, Cody 5981756155, both blocking on the same button); round 2 at `4572bfb5` (Shadow 5982129832, Cody 5982214201, Quinn 5982415054, Vera 5983297177): all four clear, both blockers cleared; the final pass at `8484ca64` verified by the orchestrator, not re-reviewed
- Terminal state: VERIFIED_COMPLETE for the mandatory criteria. The PR stays under the stack merge gate: the owner's written acceptance of the 63px shortfall (C-018) and the claims ticket 17tnw2b0x3h
- Remaining failed or blocked criteria: C-018 (non-mandatory, BLOCKED on the owner)
- ClickUp final evidence comment: 1400430000059913
