# Goal Contract — 17tnw2b2cez-secondary-pages

## Identity

- Goal ID: 17tnw2b2cez-secondary-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The nine secondary marketing pages (Contact, Support, Docs, Changelog, Blog, Careers, Privacy, Terms, Affiliates) match their Figma frames in structure, type, spacing and colour for the 48 class A findings and 2 code defects the audit assigned to them, with no claim added that the repo does not back and no accessibility regression
- Role: frontend-engineer
- Status: IN_PROGRESS
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
| C-001 | yes | Contact opens with the centred hero, then the form first and the method cards second in DOM and Tab order; Figma card, field and button geometry and labels; placeholders and counter pass AA; heading levels never skip | `node --test tests/secondaryPages.test.ts` plus harness | the tests pass and each is red on the old view; contact class A lines closed | pending | PENDING |
| C-002 | yes | Support has Figma's hero, 620 by 52 search field with an AA placeholder and a visible focus ring, 400 wide category cards with icon tiles and no extra heading, the full-width band with one grouped article panel; no AA failure on counts and meta | test file plus harness | tests pass; support class A lines closed or documented | pending | PENDING |
| C-003 | yes | Docs has the centred hero, the grouped 248px sidebar with a visible and programmatic active state, the getting-started intro with callout and topic grid, the shared container; sidebar title and breadcrumb pass AA | test file plus harness | tests pass; docs class A lines closed or documented | pending | PENDING |
| C-004 | yes | Changelog has Figma's hero, one card per release with a meta column and per-change rows, the IMPROVED badge on accent and FIXED on warn, release headings h2 and change titles h3, the release date passes AA | test file plus harness | tests pass; changelog class A lines closed or documented | pending | PENDING |
| C-005 | yes | Blog has Figma's hero, the featured post with a media panel and a Featured Article badge, a three column grid with media thumbnails and per-category pills, the author in the meta line, and AA meta, read links and badges | test file plus harness | tests pass; blog class A lines closed or documented | pending | PENDING |
| C-006 | yes | Careers has the hero type scale, four icon-tile culture cards, the full-bleed roles band with tag pills and a closing line, role meta text that passes AA, Apply links with distinct accessible names; no invented role is presented as an opening beyond what the build already showed | test file plus harness | tests pass; careers class A lines closed or documented | pending | PENDING |
| C-007 | yes | Privacy and Terms match Figma's title, section-heading and body type scale, header spacing and divider, and the terms list markers; the generated legal text and the contents sidebar are untouched | `npm run check:legal`, `npm run test:legal-pages`, `article_pages_headless.py`, harness | gates exit 0; privacy and terms class A lines closed or documented | pending | PENDING |
| C-008 | yes | Affiliates renders How it works, Made for people who talk to churches, Why it is easy to recommend, the closing band and Figma's hero CTAs, four stat cards that carry no invented figure, and the boxed FaqAccordion with its own heading and questions | test file plus harness | tests pass; affiliates class A lines closed or documented | pending | PENDING |
| C-009 | yes | No view of the nine passes `variant="gradient"`; every one uses the shared `.container` and none declares its own container rule; no heading level is skipped on any of the nine | `node --test tests/secondaryPages.test.ts` (source and render checks over the real tree, each with a planted-fault control) | exit 0; each control red | pending | PENDING |
| C-010 | yes | No claim is added: strings the audit marks unbacked in Figma (hello@selahcue.app, community.selahcue.app, Response time, within one business day, commission rates, payout thresholds, invented versions) are absent from the nine views | same test file | exit 0; the control fails on a planted string | pending | PENDING |
| C-011 | yes | Every other offline gate passes, run one at a time with exit codes captured: make marketing-check, npm test, test:states, test:responsive on Chromium and on WebKit, test:legal-pages, article_pages_headless.py, test:components, test:mirrors, check:legal | each command with `SELAHCUE_HEADLESS_REQUIRE=1` and `SELAHCUE_SWEEP_REQUIRE=1` on `/usr/bin/python3` | every command exit 0 | pending | PENDING |
| C-012 | yes | Harness re-run for the nine slugs: each class A finding is closed, and every remaining line is a documented class B, C or D with its source; nothing regressed against the baseline run | `visual_parity.py --suite marketing --engine both --only` the nine slugs; `vp_style_diff.py` per slug compared with the baseline | exit 0; remaining lines each named | pending | PENDING |
| C-013 | yes | The harness self-tests still pass: `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` | run each, exit codes unpiped | all exit 0 | pending | PENDING |
| C-014 | yes | Contrast of every changed foreground and background pair is AA or a recorded class D; no horizontal page scroll at 375, 768 and 1440; keyboard order and focus checked on a real render | contrast table from the harness survey; responsive sweep; Tab walk | no new failing pair; sweep reports none | pending | PENDING |
| C-015 | yes | The diff touches only the footprint plus this contract | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only footprint paths | pending | PENDING |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact | start comment 1400430000059586 read back; handoff pending | PENDING |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/BASE` for each of the three base branches | isDraft true; base correct; behind 0 each | pending | PENDING |
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

## Risks and rollback

- Risks: the legal and article gates (`test:legal-pages`, `article_pages_headless.py`) pin heading text and layout of the pages being restyled; the Contact page is also touched by 17tnw2b0x3h (claims) so edits to its script and success state are kept minimal to avoid a conflict; a vp_style_diff line that is a deliberate honesty deviation can be mistaken for an unfinished finding, so each is listed
- Rollback or recovery: revert the PR; no shared file, token or component is changed

## Pause and escalation conditions

- A fix needs a shared file (Navbar, Footer, UiButton, UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog, tokens.css, main.css, App.vue, scroll.ts): stop and report the exact change to the coordinator
- A class C or D decision is needed: keep the layout, leave the claim out, raise it to Uma or the owner
- Three materially different failed attempts without new evidence: FAILED_LIMIT with the smallest unblocker

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cez-secondary-pages.md --completion`
- Validator result: pending
- Independent verification result: pending (coordinator)
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
