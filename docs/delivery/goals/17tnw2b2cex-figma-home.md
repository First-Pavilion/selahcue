# Goal Contract — 17tnw2b2cex-figma-home

## Identity

- Goal ID: 17tnw2b2cex-figma-home
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Home page matches Figma frame 468:125 section by section for the 24 class A findings and the one code defect the audit assigned to it, ships no claim the repo does not back, and adds no claim the live page does not already make
- Role: frontend-engineer
- Status: IN_PROGRESS
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
- **Assumed:** the hero "Watch 2-min demo" button ships disabled with a spoken explanation, until Uma or the owner decides home-18 (remove or relabel). Status quo was a link to `#demo`, which does nothing.
- **Assumed:** the Free plan's `Download free` goes to `/download`, a page that says honestly that nothing downloads yet (the hero and navbar buttons already do the same).
- **Unknown (Uma):** accessible inks for small brand text and for the three avatar fills (home-44); whether the reliability metric badges, hover lift, hero glow return (home-19, home-22).
- **Unknown (owner):** options of home-18, 23, 33, 34, 36, 40, 42, 43.

## Dependencies and approvals

- PR 171, 172, 173 (stack); PR 172 must not merge before this PR carries `id="how-it-works"`
- Four-reviewer gate brokered by the coordinator, not requested by this role
- Three other area tickets run in parallel on other files; no shared file edited here

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Layout: eleven sections in Figma's order; content column 1248 at 96px gutters from the shared `.container` (local rule deleted); section rhythm 88/90, hero 96/72, per-section header gaps; Reliability and Testimonials are full-width `--sc-surface` bands with `--sc-border` edges and `--sc-base` cards; showcase 470 / 706 at gap 72; page within 40px of the frame once the FAQ is ignored | `vp_style_diff.py --slug home` boxes and y-shifts; `tests/homeView.test.ts` source checks | no class A width, height, gap or fill line for home-04, 05, 06, 26; document height within 40px of 6814 after the FAQ difference | harness run, style-diff comparison | PENDING |
| C-002 | yes | Copy follows the ledger: Figma wording where backed (home-20, 21, 24, 28, 31, 38), the backed part only where Figma overclaims, existing sentences untouched elsewhere; none of the forbidden claims (`NDI 5`, `Wirecast`, `4K`, `60fps`, `alpha`, `NFR-`, `Whisper`, `zero lag`, `Sub-3-second`, `≤3s`, `Add more translations`, `save 20%` in new text, `Priority support`, `Guided onboarding`, a Linux installer) is added | `node --test tests/homeView.test.ts` (rendered text per section, positive and negative) | exit 0; each ledger line pinned; planted claim turns it red | test output, mutation list | PENDING |
| C-003 | yes | Icons are the feather-style SVG set: no emoji and no text glyph used as an icon anywhere in the rendered Home page; every icon is `aria-hidden`; the hero eyebrow carries the brand logo mark; the play glyph is `aria-hidden` | render test over the real tree with a Unicode property scan | zero `Extended_Pictographic` or `✓` outside an `aria-hidden` element; no `✨` | test output | PENDING |
| C-004 | yes | Hero console mock and Screens & Outputs mock show the designed structure (Preview pane then Live pane; title bar, LIVE chip; rows with thumbnail, name, tag chip, status chip, `+ Add output`), are one `role="img"` with a name and expose none of their fake UI text, contribute no heading | render test; accessibility snapshot in a real browser | one named image each; no `h1`-`h6` inside; PREVIEW before LIVE in DOM order | test output; Playwright aria snapshot | PENDING |
| C-005 | yes | The steps section has `id="how-it-works"`; every in-page `#fragment` link on Home, Navbar and Footer resolves to an element id on Home; `reanchor.ts` resolves the decoded fragment with `getElementById`, so `#1abc` and `#%` on the home route end as `reapplied` and `#how-it-works` finds its target | `node --test tests/homeAnchor.test.ts` and a cold load in Chromium and WebKit | exit 0; target lands clear of the 79px bar | test output; browser measurement | PENDING |
| C-006 | yes | Pricing teaser: Free reads `$0 / forever`; Free's button goes to `/download` and Church's to `/contact` (links); Pro's button has no destination and shows the disabled state with its note; no enabled button without an action anywhere on Home | render test over the real tree | exactly two plan links, one disabled plan button with `Not available yet`; the hero demo button disabled and described | test output | PENDING |
| C-007 | yes | Type and ink: H1 60/64/700, section H2 per section at 700, card, step and plan titles at the Figma sizes and weights, secondary copy `--sc-text-secondary`, no off-token grey or pure white in Home's CSS; section labels use `variant="eyebrow"`; no `variant="gradient"`; no `!important`; hero button row centred so the quiet large button is 47px next to the 49px solid one | source tests plus `vp_style_diff.py` font and colour lines; computed button heights in a real browser | no class A font, weight, tracking or colour line for home-07, 08, 16; buttons 49 and 47 | test output; style diff; browser measurement | PENDING |
| C-008 | yes | Heading outline never skips a level and has one `h1`; output rows and testimonial names are not headings | render test walking the rendered headings; positive control on a planted skip | exit 0; planted `h4` under `h2` turns it red | test output | PENDING |
| C-009 | yes | Contrast of every changed foreground and background pair is AA (or recorded as B or D with its source); no horizontal page scroll at 375, 768, 1440 | pair table from the same luminance formula as `vp_core`; `npm run test:responsive` on Chromium and WebKit | no new failing pair; sweep reports none | contrast table; sweep output | PENDING |
| C-010 | yes | Harness: `visual_parity.py --suite marketing --engine both` for home and the pages that share Home's components (none other consume them; recorded) exits 0; `vp_style_diff.py` for home prints no line that belongs to a class A finding listed in the ticket; every remaining line is named class B, C or D with its owner | `visual_parity.py --only home`, `vp_style_diff.py --slug home --limit 0` on Chromium and WebKit dumps | exit 0; line set compared with the baseline `sd_base_blink.txt` | run path; closed and remaining lists | PENDING |
| C-011 | yes | Every other offline gate passes with its REQUIRE variable set: `make marketing-check`, `npm test`, `test:states`, `test:responsive` (Chromium and WebKit), `test:legal-pages`, `article_pages_headless.py`, `test:components`, `test:mirrors`, `check:legal`, `vp_selftest.py`, `check_fidelity_audit.py --self-test` and `--require-tickets` | each run one at a time, exit code captured unpiped | all exit 0 | commands and exit codes | PENDING |
| C-012 | yes | Every new test fails when the thing it guards breaks: each is mutation-proved on a scratch copy | planted faults, one per test group | each turns the named test red | mutation table below | PENDING |
| C-013 | yes | The diff touches only the footprint, the declared `reanchor.ts` edit, this contract and new test files; no shared file | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths | path list | PENDING |
| C-014 | yes | Keyboard order and focus: Tab order is nav, hero buttons (the disabled one skipped), sections top to bottom, footer; every stop shows the focus ring; nothing in the mocks is focusable | Playwright Tab walk on Chromium and WebKit | order as stated; no ring missing; no mock stop | walk output | PENDING |
| C-015 | yes | ClickUp: in progress with a start comment; a handoff comment with QA steps as a list; each write read back | ClickUp read-back | present, lists intact | comment ids | PENDING |
| C-016 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge-order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components`, then the same for the chrome and audit branches | isDraft true; base correct; behind 0 | PR URL; counts | PENDING |
| C-017 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | review comments | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Copy ledger

Every line of Home copy, with where it comes from. Figma wording is used verbatim unless the line says otherwise.

- Hero: eyebrow, H1, sub, `Download free`, trust line: unchanged text (equal to Figma). `Watch 2-min demo`: label unchanged (the claim is the decision of home-18 and the removal belongs to 17tnw2b0x3h); the control is disabled with a spoken explanation instead of a link to nothing.
- Features: subtitle verbatim. Blurb 1, 3, 4 verbatim. Blurb 2 drops "Add more translations any time" (PRD CON-3: licensed translations are later). Blurb 5 keeps "NDI source for OBS or vMix" and the per-output settings, drops "any feed". Blurb 6 drops "captions" and "computed entirely on-device" and says the transcript and suggestions run on the machine by default (ADR-0010, home-43). Card titles unchanged.
- Reliability: eyebrow `WHY SELAHCUE`, subtitle and pillars 1 and 2 verbatim except pillar 2 drops "no account" (account sign-in is the primary activation path, DEC-007); pillar 3 reads "Starts fast and keeps memory bounded" without the number (home-23, the owner's own wording option); the three metric badges are not drawn (the frame has none; home-22, Uma).
- Showcase: eyebrow, H2, body and the three one-line checks verbatim (NDI named only as an output for OBS, vMix or another machine, home-42).
- How it works: subtitle and three step bodies verbatim (the audit marks "no internet, no lag" acceptable for LAN control).
- Pricing: subtitle verbatim (it drops the live "save 20% annually" sentence); Free: description and three bullets verbatim, "One physical output" left out (DEC-008 gives Free two outputs); Pro: description without "Billed monthly, or save 20% yearly", bullets "Everything in Free", "NDI + multiple simultaneous outputs", "Mobile control over your local network"; "Theme Designer & saved templates", "On-device transcript & scripture detection" and "Always on the latest version" are left out (tier gating DEC-008 does not decide; no update channel ships); Church: description verbatim, bullets "Everything in Pro" and "Multi-campus / site licensing" (the live page already says multi-campus); "Guided onboarding & training" and "Priority support" left out (no such service exists). `$19`, `/ month`, `MOST POPULAR`, `Custom` stay as they are today (home-33, 17tnw2b0x3h).
- Testimonials: quotes, names and churches unchanged (home-36); the role separator becomes `·` and the quotes get typographic marks (the finding's format change); the label stays `TESTIMONIALS`, not Figma's `FROM THE TECH BOOTH`, which would attribute the live quotes to tech teams (home-36).
- FAQ: the five Figma questions. Answer 1 drops "or extra Bible translations" and states only that a dropped connection never stops the service. Answer 2 keeps the live platforms answer unchanged (home-38, 40, 45 held). Answers 3 and 4 verbatim. Answer 5 is Figma's wording with "or annual" taken out ("a simple monthly subscription"), because the repo has no annual plan; "free forever" and "Cancel anytime" are already live in this answer and stay (home-33).
- Final CTA: H2 and sub unchanged text; buttons `Download free` and `See pricing`.

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

## Risks and rollback

- Risks: a page-wide restyle can regress the responsive layouts that PR 172 and the existing sweep pin; the new copy removes sentences some reader may expect; the disabled demo button changes the hero
- Rollback or recovery: one revert of this PR restores the previous Home; no shared file, schema or route changed

## Pause and escalation conditions

- A fix that needs a shared file (FaqAccordion defaults, UiBadge ink, PricingCard, UiButton): stop and report the exact change to the coordinator
- A class C or D choice that cannot be left as the honest state: Uma or the owner
- Three materially different failed attempts on one criterion without new evidence: `FAILED_LIMIT`

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cex-figma-home.md --completion`
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
