# Goal Contract — 17tnw2b2cez-secondary-pages

## Identity

- Goal ID: 17tnw2b2cez-secondary-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The nine secondary marketing pages (Contact, Support, Docs, Changelog, Blog, Careers, Privacy, Terms, Affiliates) match their Figma frames in structure, type, spacing and colour for the 48 class A findings and 2 code defects the audit assigned to them, with no claim added that the repo does not back and no accessibility regression
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cez
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Change only the nine page views, `src/components/legal/*`, `src/components/article/*` and `tests/` (plus this contract) so that every class A finding of ClickUp 17tnw2b2cez is closed in the marketing harness (`vp_style_diff` prints no line that belongs to it, or the line is a documented class B, C or D with its source), the two heading-order defects are fixed and pinned by tests, the deferred items from the chrome review are done (no `variant="gradient"`, the shared `.container` and type tokens adopted, local container rules deleted, Changelog IMPROVED on `accent`, Affiliates on the boxed `FaqAccordion`), and every gate that ran green on the base still runs green.

## Baseline

**Verified** on `origin/web/17tnw2b2cew-shared-components` at `5b203064` (PR 173, which contains the audit PR 171 and the chrome PR 172):

- `npm ci` then `npm run build` exit 0. `npm test`: 774 pass, 0 fail.
- Marketing harness baseline for the nine slugs (Blink): `.visual-parity/run-20261004-095808`, exit 0; per-slug `vp_style_diff --limit 0` saved before any change (contact 172 lines, support 186, docs 235, changelog 195, blog 164, careers 158, privacy 527, terms 645, affiliates 195).
- Contrast survey of that run lists 25 reported entries for these slugs: every one is the brand ink (`--sc-primary` on surface or elevated, 3.49 to 3.83:1, class D, held for Uma) or the Support search placeholder in the browser default grey (3.92:1, support-03). The muted-ink failures the audit listed (careers-05, docs-07, support-10 meta, changelog-06) no longer print: the chrome ticket raised `--sc-text-muted` to 5.0:1 or better on every surface.
- Contact: the page has no hero, h1 jumps to h4 for the method cards, the form is the right column, a local `.container` is 1140 wide, the three Contact method cards use emoji, and the Send button is `variant="gradient"`. Changelog: h1 then h3 for every change.

## Inputs and evidence sources

- ClickUp 17tnw2b2cez (Goal, Scope, Findings, Acceptance Criteria, the two bugs, the chrome review comment 1400430000059527); audit ticket 17tnw2b2c75; epic 86ajy5v6k; claims removal 17tnw2b0x3h
- `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` and `docs/design/visual-parity/marketing/findings/secondary-1.json`, `secondary-2.json`
- Committed Figma style dumps `docs/design/visual-parity/marketing/figma-style/{contact,support,docs,changelog,blog,careers,privacy,terms,affiliates}.json` and the reference PNGs (Figma values are read from these, not from live Figma)
- `docs/delivery/VISUAL-PARITY-HARNESS.md` section 11; `docs/delivery/goals/17tnw2b2cev-figma-shared-chrome.md` (PR 172); `docs/delivery/goals/17tnw2b2cew-shared-components.md` (PR 173)
- `docs/design/MARKETING-SITE-HANDOFF.md`, `MARKETING-PORTAL-GAP-FILL-HANDOFF.md`, `AUTH-LANDING-PAGES-HANDOFF.md` (token mapping 2.2)

## Scope

### In scope

- `implementation/marketing/src/views/{Contact,Support,Docs,Changelog,Blog,Careers,Privacy,Terms,Affiliates}View.vue`, `src/components/legal/*`, `src/components/article/*`, `tests/`
- The items deferred to this ticket in its comment: no `variant="gradient"`; the shared `.container` and type tokens; Changelog IMPROVED on `accent`; Affiliates owns its FAQ heading and questions and opts into the boxed FaqAccordion; heading order on Contact and Changelog; button sizes against Figma
- Re-running the harness and every offline gate

### Non-goals

- Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, tokens.css, main.css, App.vue, router/scroll.ts (PRs 172 and 173): a fix that needs one is reported, not made
- Every class C and D item: Contact channels and replies (contact-04 to 07, 19), the Support and Docs content layer (support-05, docs-05, docs-06), the macOS and Linux installer sentences (support-11 and docs-09: owner), invented Changelog versions (changelog-04, 05), Blog counts (blog-04), Careers roles and claims (careers-07 to 09), legal mailboxes and plan names (privacy-11, terms-12), Affiliates programme figures (affiliates-10, 12 to 15)
- Claim REMOVAL from live pages: ClickUp 17tnw2b0x3h. This ticket never adds a claim and does not duplicate that work
- The generated legal files (`src/lib/legal/*.generated.ts`, `docs/legal`): `npm run check:legal` and `npm run test:legal-pages` stay green
- Adding Linux anywhere (Figma does not draw it)
- The Home, Pricing/Features/Download/About and auth pages (three other Farah instances)

### Constraints

- Own worktree and branch `web/17tnw2b2cez-secondary-pages`, one ticket, one Draft PR with base `web/17tnw2b2cew-shared-components`; stacked (audit 171, chrome 172, components 173, this); retargeted and rebased as each lands; the stack merges in order the same day; never merged by this role
- Honest content wins over Figma; fidelity must not regress accessibility (a Figma colour below AA stays accessible in code); Figma legacy variables against `--sc-*` is a deliberate layer
- Prefer new test files; any edit to a shared fixture is additive and declared
- `git push` with BatchMode SSH; no attribution trailers; ClickUp lists only, no Markdown tables; every write read back

### Assumptions and unknowns

- **Assumed:** where Figma's hero copy makes a promise the repo does not back ("here's how to reach a real person"), the layout and size follow Figma and the sentence is reworded to carry no promise; each such line stays in the harness as a documented class B (honest content, owner decision 1)
- **Assumed:** the three Contact method cards keep the build's three channels in the Figma card styling; the Figma-only addresses (hello@, community.selahcue.app), the response-time note card and the form footnote are not shipped (contact-04, 05 are class C)
- **Unknown (owner):** whether a downloadable installer exists for macOS and Linux (support-11, docs-09); the sentences are left as they are
- **Unknown (Uma):** the accessible brand ink for small brand-coloured text (class D); no ink is chosen here

## Dependencies and approvals

- PR 171, 172, 173 (merge order gate: the stack merges in order, the same day), owned by the coordinator
- Four-reviewer gate brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Contact opens with the centred hero, then the form first and the method cards second in DOM and Tab order; Figma card, field and button geometry and labels; placeholders and counter pass AA; heading levels never skip | `node --test tests/secondaryPages.test.ts` plus harness | the tests pass and each is red on the old view; contact class A lines closed | 128 node tests in tests/secondaryPages.test.ts (904 pass in the whole suite, 774 before); the browser script tests/secondary_pages_headless.py, 178 checks per engine on Chromium and WebKit, 0 failed: form 604 wide at x96 and first in Tab order then the three card links, cards 604 at x740 and 99 high, 46px r12 tiles, fields 44, textarea 120, Send 49 by 540, placeholder and counter in the secondary ink (AA), blur validation, a 101 character name refused; 13 planted faults in the view each turned a named test red | PASS |
| C-002 | yes | Support has Figma's hero, 620 by 52 search field with an AA placeholder and a visible focus ring, 400 wide category cards with icon tiles and no extra heading, the full-width band with one grouped article panel; no AA failure on counts and meta | test file plus harness | tests pass; support class A lines closed or documented | node tests plus the browser script: search 620 by 52 r14 with a secondary placeholder and a 2px brand ring on keyboard focus, typing replaces the grid with results, 400 wide r18 cards 24 apart with six SVG tiles, a full-width band holding one 880 panel, a row click anywhere opens the article; counts pass AA; 18 planted faults red. Remaining lines named in the closure list (content layer: support-05, 06, 09) | PASS |
| C-003 | yes | Docs has the centred hero, the grouped 248px sidebar with a visible and programmatic active state, the getting-started intro with callout and topic grid, the shared container; sidebar title and breadcrumb pass AA | test file plus harness | tests pass; docs class A lines closed or documented | node tests plus the browser script: sidebar 248 at x96, 40 to the 960 column, exactly one aria-current=location item that moves on click with a visible fill, tiles 471 by 83, group labels AA; the router no longer marks the hub's same-page hash links aria-current=page (the article gate caught it); the sections keep the class the global anchor rule uses so a typed #hash lands under the navbar (the article gate caught the rename); 24 planted faults red | PASS |
| C-004 | yes | Changelog has Figma's hero, one card per release with a meta column and per-change rows, the IMPROVED badge on accent and FIXED on warn, release headings h2 and change titles h3, the release date passes AA | test file plus harness | tests pass; changelog class A lines closed or documented | node tests plus the browser script: 900 wide r20 card at x270 per release with an h2 version, a label per group (New preview, Improved accent, Fixed warn), sentence case labels, date 14px secondary AA, 21px pills, 6px dots; heading outline h1 h2 h3; 15 planted faults red. The IMPROVED badge uses accent | PASS |
| C-005 | yes | Blog has Figma's hero, the featured post with a media panel and a Featured Article badge, a three column grid with media thumbnails and per-category pills, the author in the meta line, and AA meta, read links and badges | test file plus harness | tests pass; blog class A lines closed or documented | node tests plus the browser script: featured card 1248 by 348 r22 with a 584 by 300 media panel and no button, the title is one stretched link (Tab stop with a card-wide ring; a click in the card's corner opens the post), three 400 wide r18 cards 24 apart with 150px thumbnails, per-category pills, meta 12.5px AA; 14 planted faults red. The brand-ink Read links and pills are class D | PASS |
| C-006 | yes | Careers has the hero type scale, four icon-tile culture cards, the full-bleed roles band with tag pills and a closing line, role meta text that passes AA, Apply links with distinct accessible names; no invented role is presented as an opening beyond what the build already showed | test file plus harness | tests pass; careers class A lines closed or documented | node tests plus the browser script: h1 50/56/700 about 498 wide, four 294 wide cards with 50px r13 SVG tiles, a full-bleed band, a 940 list at x250, tag pills 12/500 on elevated AA, three distinct Apply names; 19 planted faults red. No Figma role or mailbox is shipped | PASS |
| C-007 | yes | Privacy and Terms match Figma's title, section-heading and body type scale, header spacing and divider, and the terms list markers; the generated legal text and the contents sidebar are untouched | `npm run check:legal`, `npm run test:legal-pages`, `article_pages_headless.py`, harness | gates exit 0; privacy and terms class A lines closed or documented | title 44/700/50, pill 96px under the navbar, no header rule, section headings 20/600/26 with the number in the heading ink, body 16/26, 780 column, primary list dots, pill reads LEGAL on the page pill; check:legal exit 0; test:legal-pages exit 0 (419 checks, run on the final head); article_pages_headless.py exit 0 (143 of 143); 24 planted faults red (one survived at first: the child-heading test was vacuous, strengthened and re-proved) | PASS |
| C-008 | yes | Affiliates renders How it works, Made for people who talk to churches, Why it is easy to recommend, the closing band and Figma's hero CTAs, four stat cards that carry no invented figure, and the boxed FaqAccordion with its own heading and questions | test file plus harness | tests pass; affiliates class A lines closed or documented | node tests plus the browser script: hero buttons both 49 high 14 apart (neither to /signin), four 295.5 stat cards, three 400 step cards in a full-bleed band, four audience cards with 50px r14 tiles, two checklist rows, the 420 calculator beside them with a named slider, the boxed 880 FAQ, a gradient 1248 r24 band with one white button; no programme figure in any new section; 30 planted faults red | PASS |
| C-009 | yes | No view of the nine passes `variant="gradient"`; every one uses the shared `.container` and none declares its own container rule; no heading level is skipped on any of the nine | `node --test tests/secondaryPages.test.ts` (source and render checks over the real tree, each with a planted-fault control) | exit 0; each control red | tests/secondaryPages.test.ts, per page: no heading level skipped and one h1, no gradient button, no local container rule, no text coloured with the muted ink, no claim the audit marks unbacked added (the two legal pages are excluded from the last: they render the generated drafts); controls fail on a planted fault; the shared container is used on the seven non-legal pages | PASS |
| C-010 | yes | No claim is added: strings the audit marks unbacked in Figma (hello@selahcue.app, community.selahcue.app, Response time, within one business day, commission rates, payout thresholds, invented versions) are absent from the nine views | same test file | exit 0; the control fails on a planted string | the same file: hello@selahcue.app, community.selahcue.app, within one business day, We usually reply, Response time, 10 minutes, Windows & macOS install, careers@selahcue.app, We're a small remote team, Ship features churches use live, Sustainable pace and the five Figma role titles are absent from the seven pages; a planted string turned it red in Contact, Docs and Careers | PASS |
| C-011 | yes | Every other offline gate passes, run one at a time with exit codes captured: make marketing-check, npm test, test:states, test:responsive on Chromium and on WebKit, test:legal-pages, article_pages_headless.py, test:components, test:mirrors, check:legal | each command with `SELAHCUE_HEADLESS_REQUIRE=1` and `SELAHCUE_SWEEP_REQUIRE=1` on `/usr/bin/python3` | every command exit 0 | final head, each run alone in the background with its exit code captured: make marketing-check 0; npm test 0 (904 pass); test:states 0 (60 scenarios, 1751 checks, 0 FAIL); test:responsive Chromium 0 (2315 checks, 0 failed) and WebKit 0 (2315 checks, 0 failed); test:legal-pages 0 (419 checks); article_pages_headless.py 0 (143 of 143); test:components 0 (646 checks); test:mirrors 0 (Django 6.1.1, Python 3.14.5, scratch virtualenv outside the repo); check:legal 0; tests/secondary_pages_headless.py 0 (178 per engine). /usr/bin/python3 with SELAHCUE_HEADLESS_REQUIRE=1 and SELAHCUE_SWEEP_REQUIRE=1. Two gate scripts needed a declared edit (see Out-of-footprint edits). make ci was not run: Rust, Flutter and the API are untouched | PASS |
| C-012 | yes | Harness re-run for the nine slugs: each class A finding is closed, and every remaining line is a documented class B, C or D with its source; nothing regressed against the baseline run | `visual_parity.py --suite marketing --engine both --only` the nine slugs; `vp_style_diff.py` per slug compared with the baseline | exit 0; remaining lines each named | real harness, both engines: .visual-parity/run-20261004-113233 in this worktree captured and compared eight slugs and REFUSED changelog (Inter probe: the page has no 600 weight text, so that face never loads; a harness limitation, reported). The same command on a scratch copy of scripts/ with that one probe line fixed exits 0 for all nine on both engines: run path scratchpad/cez-farah-secondary/vps/.visual-parity/run-20261004-113451 (outside the repo). vp_style_diff per slug on Blink and WebKit prints the same line counts (the closure list names what remains: Figma-only copy and content-layer words, class B, C, D). No page got a new class A line; line counts moved contact 172 to 159, support 186 to 167, docs 235 to 216, changelog 195 to 163, privacy 527 to 523, terms 645 to 641, and rose where the build now has real content the frame does not draw (blog 164 to 165, careers 158 to 185, affiliates 195 to 247) | PASS |
| C-013 | yes | The harness self-tests still pass: `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` | run each, exit codes unpiped | all exit 0 | vp_selftest.py exit 0 (206 checks, 0 FAIL); check_fidelity_audit.py --self-test exit 0 (97 checks, 0 FAIL); --require-tickets exit 0 (0 problems) | PASS |
| C-014 | yes | Contrast of every changed foreground and background pair is AA or a recorded class D; no horizontal page scroll at 375, 768 and 1440; keyboard order and focus checked on a real render | contrast table from the harness survey; responsive sweep; Tab walk | no new failing pair; sweep reports none | harness contrast survey on the final run (both engines) lists only brand-ink text, class D held for Uma: the page eyebrow pills 3.49:1 (UiBadge featured, one property), Contact's three card links 3.83:1 (already brand ink before) and Blog's Read links 3.83:1. Gone from the baseline's 25 entries: the Support placeholder (3.92), the counts (3.83), the article meta, the Contact placeholder and counter, the calculator labels (3.34 to 3.45). New: the LEGAL pill on Privacy and Terms (3.49, class D; the green status badge it replaced passed). The browser script asserts AA for the placeholder, counter, group labels, release date, tag pills, card meta, counts. No horizontal scroll on the nine pages at 375, 768 and 1440 on both engines (script and the sweep). Keyboard: Tab order, focus rings and the one stretched link are asserted in the browser script | PASS |
| C-015 | yes | The diff touches only the footprint plus this contract | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only footprint paths | git diff --name-only origin/web/17tnw2b2cew-shared-components: this contract; the nine views; src/components/legal and src/components/article; tests (a new test, two fixtures, a browser script, and one edit to tests/contentSearch.test.ts); and two declared gate-script edits (see Out-of-footprint edits). No shared component, token, chrome file or generated legal file | PASS |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact | start comment 1400430000059586 and handoff comment 1400430000059620 on ClickUp 17tnw2b2cez, read back with the QA steps as a list and no table | PASS |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/BASE` for each of the three base branches | isDraft true; base correct; behind 0 each | https://github.com/First-Pavilion/selahcue/pull/177: isDraft true, base web/17tnw2b2cew-shared-components, mergeable; the description opens with the stacked order (audit 171, chrome 172, components 173, this) and the in-order same-day merge gate; after a fetch the branch is 0 behind origin/web/17tnw2b2c75-figma-fidelity-audit, origin/web/17tnw2b2cev-shared-chrome, origin/web/17tnw2b2cew-shared-components and origin/main | PASS |
| C-018 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | not requested by this role; the coordinator closes this row | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: tests first for each page (the node render and source tests in `tests/secondaryPages.test.ts`), each shown red on the base before the change and mutation-proved afterwards on a copy
- Broader regression verification: every offline gate in C-011, the harness in C-012, the self-tests in C-013
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium and WebKit), network for Inter, a scratch virtualenv outside the repo with Django for `test:mirrors`

## Iteration ledger

### Iteration 1

- Target criterion: baseline
- Hypothesis: the base is green and the findings are reproducible from the audit data
- Change or investigation: created the worktree from the PR 173 head, `npm ci`, build, `npm test` (774 pass), harness baseline for the nine slugs, per-slug style diffs saved; read the ticket, its two comments, the audit data for the nine pages and the PR 172 and 173 contracts
- Verifier executed: `npm run build` (exit 0), `npm test` (exit 0, 774 pass), `visual_parity.py --suite marketing --only` the nine slugs (exit 0)
- Result: baseline recorded; the contrast survey shows only brand-ink (class D) and the Support placeholder
- New evidence: the branch was created with the base branch as its upstream; the upstream was unset so a plain push cannot write to the base
- Decision: iterate

### Iteration 2 (the pages, test first)

- Target criterion: C-001 to C-010
- Hypothesis: each page can be brought to its frame with a render test and a source test written first and shown red on the base, then a browser script that measures what those cannot see
- Change or investigation: one page at a time in the ticket's order (Contact, Support, Docs, Changelog, Blog, Careers, Privacy and Terms, Affiliates); for each, read the findings and the committed Figma values, wrote the failing test, wrote the view, ran the harness on that slug, then planted faults in a scratch copy to prove every new test; one small shared component, CategoryIcon, serves the Support, Docs, Blog, Careers and Affiliates tiles; pushed after each page
- Verifier executed: `node --test tests/secondaryPages.test.ts`; `visual_parity.py --suite marketing --only` the slug; `vp_style_diff.py`; mutation runs on a scratch copy
- Result: all new tests green; about 150 planted faults each turned a named test red (six of my first mutations were unfaithful or did not apply and were redone; one real survivor, the vacuous child-heading test, was strengthened and re-proved)
- New evidence: FormField draws a `*` for every required field and puts `maxlength` on a textarea only; the changelog page has no 600 weight text, so the harness refuses it; the featured blog card and the support rows had markup that two gates pinned; the global anchor rule is keyed to the class `.docs-content`
- Decision: iterate

### Iteration 3 (browser script and gates)

- Target criterion: C-011, C-014
- Hypothesis: the pages behave in a real browser as the node tests say, on both engines
- Change or investigation: wrote tests/secondary_pages_headless.py (178 checks per engine); WebKit reserves a 12px scrollbar, so the window is widened by it to make the layout 1440; WebKit drew a 15px input 45 high, so the Contact inputs now have an explicit 44; planted 14 faults in built copies; ran every gate alone in the background
- Verifier executed: the gate list in C-011
- Result: three real regressions found by existing gates and fixed: the shared tree test could not read my badge variants (now literal choices), the search placeholder promise test pinned the old placeholder (now follows the frame and keeps its rule), and the Docs rename of the anchor class plus the router's aria-current=page on the hub's hash links (article gate); two gate scripts pinned the old markup or the old 24px gutter and were edited (declared)
- New evidence: the sweep fix is the same one the Pricing ticket needed, so f62b0d04 was cherry-picked instead of writing a second variant (coordinator instruction)
- Decision: handoff

## Finding closure

Every class A finding of ClickUp 17tnw2b2cez, with what closed it and what remains printed by `vp_style_diff` (each remaining line is a named class B, C or D with its source). "Honest copy" means the sentence was written without the claim Figma draws (owner decision 1); the Figma wording is not shipped.

- contact-01 closed: centred hero (CONTACT pill, h1 "Let's talk" 50/56, subline 19/30, padding 96/32, gap 20). One line remains: the subline's words, honest copy (Figma says "reach a real person"; who answers is not backed).
- contact-02 closed: form left and first in the DOM, cards right, two 604 columns 40 apart, Tab order form then cards (test and browser script).
- contact-03 closed: 46px r12 icon tiles with SVG, cards r16, 99 high, 16px apart, title 16.5, text 13.5, link 14/500 without the arrow. Remaining: the card words are the build's own (contact-04 and contact-07, class C and D, left as they were).
- contact-08 closed except: Send button weight 700 and radius 11 against Figma's 600 and 12 (UiButton lg, chrome ticket); the form card is 26px taller because the message counter stays (contact-11, class B).
- contact-09: labels, placeholders and button label are Figma's verbatim; the red `*` after a required label stays, because FormField draws it for every `required` field and `required` is what gives contact-12 its aria-required. Needs a FormField opt-out (outside the footprint): reported.
- contact-12 done in the view: form named, three fields aria-required, validation on blur and submit, 100 character limits on name and church as rules (FormField puts `maxlength` on a textarea only). Not done, on purpose: the "Sending…" label, the success announcement text and the send and network error banners all presuppose a send path; adding them now would add a claim that the form sends (owner decision 1, ClickUp 17tnw2b0x3h and the send ticket). The textarea counter as aria-describedby needs FormField.
- contact-13 closed: placeholder and counter in the secondary ink, 7.4:1.
- contact-bug-01 closed: card titles are h2; a test walks every heading.
- support-01 closed (HELP CENTER pill, "How can we help?" 48/54, subline, no glow, 96/48, gap 22). support-02 closed (620x52, r14, 20px magnifier, "Search help articles…"). support-03 closed (placeholder secondary, 2px brand focus ring). support-04 closed: six 400-wide r18 cards, 48px r13 icon tiles, no heading above; remaining: category titles and descriptions come from the content layer (support-09, class B) and a card is taller than 170 because the article lists stay (support-05, class D). support-07 closed: full-width band, one grouped 880 panel, whole-row links with a chevron; remaining: "Start here" heading and two rows (support-06, class C). support-10 closed: counts and meta in the secondary ink.
- docs-01 closed (DOCS pill, h1 46/52, lead, 88/36, gap 18, no card); the lead keeps the build's honest sentence (Figma: "install"). docs-02 closed: three groups, 248 wide, one current item with aria-current=location and a visible fill, weight 600 and a brand bar (the label ink is the primary text colour, not Figma's brand blue, which is 3.4:1: class D). docs-03 closed: h2, intro, callout to a real article, 2x3 tile grid; copy honest (docs-04, class C). docs-07 closed. docs-08 closed (248, 40, 960).
- changelog-01 closed (CHANGELOG pill, "What's new" 48/54; the subline stays the build's: changelog-05, class C). changelog-02 closed: one 900-wide r20 card per release, version h2 and date, a label per group of changes, dotted lines; the per-change titles and descriptions stay (content, changelog-04, class C; the heading bug requires the h3 titles). changelog-03: Improved on accent, Fixed on warn, New on preview. changelog-06 closed. changelog-bug-01 closed.
- blog-01 closed. blog-02 closed: two-column r22 card, 584x300 media panel with the 102px tile, category pill and Featured label, no button, the title is one stretched link. blog-03 closed: 400 wide r18 cards on a three-column grid, 150px thumbnail panel with an icon tile, per-category pills (none is the red LIVE look); the fourth card makes a short last row (blog-04, class D). blog-06 closed: "SelahCue Team ·" leads every meta line. blog-07: meta in the secondary ink; the "Read →" links and the brand pills keep the brand ink (class D, Uma).
- careers-01 closed (CAREERS pill, 50/56, 96/44, gap 20; the subline stays the build's). careers-03 closed: four icon-tile cards in Figma's fills, no heading; the first three keep the build's words (careers-08, class C), the fourth is backed by the offline-first rule. careers-04 closed: full-bleed band, centred "Open roles" 30/700, 940 list, r16 rows, three tag pills, a closing line to the contact page (no mailbox); the three roles are the build's own and no Figma role is added (careers-07 and careers-09, class C and D). careers-05 closed. careers-06 closed: each Apply link names its role.
- privacy-05, terms-05 closed (44/700/50, 16px gaps). privacy-07, terms-07 closed (96px from the navbar, no rule under the header, 40px below it). privacy-08, terms-08 closed (20/600/26, number in the heading ink, 28 above and 10 below). privacy-09, terms-09 closed (16/26, 780 column). terms-11 closed (primary 5px dots, flush left, 10px to the text). privacy-06 and terms-06 (the pill) done as well: LEGAL on the page pill, not the green status badge. The generated legal files are untouched.
- affiliates-01 to 04 closed with copy that carries no figure: How it works (three numbered steps), four audience cards (Figma's words), the checklist (the two lines the repo backs), the closing gradient band (one white Apply now; no "Read the terms": no terms document exists). affiliates-05 closed (54/60, 19/30, 96/56, gap 22; the headline and subline stay the build's own words). affiliates-06 closed: Apply now and Affiliate sign in, both 49 high, neither the customer sign-in; the targets are interim (/contact and the affiliate portal) because the affiliate Apply and Sign in screens have no route (a missing screen). affiliates-07 closed: four 295.5 cards, left aligned, no h3; three are the build's figures, the fourth is "Offline" (no programme figure added). affiliates-09 and the boxed FAQ are PR 173's component, used with `boxed`. The calculator stays beside the checklist (affiliates-10, class D) with a named slider.

## Out-of-footprint edits (declared)

- scripts/responsive_sweep.py: cherry-pick of f62b0d04 from the Pricing ticket's branch (the shared container pads 96px at desktop; the sweep expected 24px on every page container). Identical hunk on every branch so they merge cleanly.
- scripts/article_pages_headless.py: four lines. The gate looked for the Blog's "Read story" button and the Support "Read article" buttons; the frames draw neither (blog-02, support-07). It now asserts the featured title is the real link to the post and that the Start here rows are real whole-row links, requires at least two of them (the old check passed on an empty list), and clicks the title instead of the button.
- tests/contentSearch.test.ts: the placeholder promise test found the old placeholder text with a regular expression and required three examples; the frame's placeholder offers none (support-02). It still requires any example it offers to return an article, and now has a positive control for its own extractor.

## Needs a change outside this footprint (reported, not made)

- FormField (shared, PR 173): an opt-out of the red `*` for a required field (contact-09), `maxlength` on an input, and the textarea counter in `aria-describedby` (contact-12).
- scripts/vp_capture_marketing.py (the audit PR): the Inter probe checks weight 600, which never loads on a page without 600-weight text (the Changelog frame has none), so the harness refuses a faithful page. One line fixes it: await `document.fonts.load('600 16px Inter')` after `document.fonts.ready`. Verified in a scratch copy: the nine slugs then capture and compare on both engines.
- package.json and CI: `tests/secondary_pages_headless.py` is run by hand; it needs a `test:secondary` script and a workflow line.
- The affiliate Apply and Sign in screens have no route (audit affiliates-06, a missing screen): Apply now goes to /contact and Affiliate sign in to the affiliate portal as interim targets.

## Decisions for Uma and the owner (not made here)

- The accessible brand ink for small brand-coloured text (class D, one property `--ui-badge-ink` for the pills): eyebrows 3.49:1, Contact card links and Blog Read links 3.83:1. The Privacy and Terms pill now joins them (it was the green status badge, which passed).
- Whether the Docs active item keeps the primary text colour with a brand bar (done) or takes a lighter brand ink.
- Every class C and D item named in the ticket stays as the build had it: contact-04 to 07, 19; support-05, 06, 08, 11; docs-04 to 06, 09; changelog-04, 05; blog-04; careers-07 to 09; privacy-11; terms-12; affiliates-10, 12 to 15. The "no macOS or Linux installer yet" sentences (docs-09, support-11) were not edited.

## Risks and rollback

- Risks: the legal and article gates (`test:legal-pages`, `article_pages_headless.py`) pin heading text and layout of the pages being restyled; the Contact page is also touched by 17tnw2b0x3h (claims) so edits to its script and success state are kept minimal to avoid a conflict; a vp_style_diff line that is a deliberate honesty deviation can be mistaken for an unfinished finding, so each is listed
- Rollback or recovery: revert the PR; no shared file, token or component is changed

## Pause and escalation conditions

- A fix needs a shared file (Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, tokens.css, main.css, App.vue, scroll.ts): stop and report the exact change to the coordinator
- A class C or D decision is needed: keep the layout, leave the claim out, raise it to Uma or the owner
- Three materially different failed attempts without new evidence: FAILED_LIMIT with the smallest unblocker

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cez-secondary-pages.md --completion`
- Validator result: the structural check passes; the completion check passes for every row except C-018, which is the coordinator's to close
- Independent verification result: not requested by this role; the coordinator brokers Cody, Vera, Shadow and Quinn
- Terminal state: GATE_REVIEW (the verifiable work is complete and every offline gate is green; the review gate is the coordinator's, so VERIFIED_COMPLETE waits for C-018)
- Remaining failed or blocked criteria: none failed; C-018 (independent review) is open by design
- ClickUp final evidence comment: 1400430000059620 on https://app.clickup.com/t/17tnw2b2cez
