# Goal Contract — 17tnw2b2cf1-figma-auth-pages

## Identity

- Goal ID: 17tnw2b2cf1-figma-auth-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Sign in page and the Verify (V1-V6) and Reset (R1-R7) states match the Figma frames the audit compared them with, the accessibility failures the audit measured are fixed, no account-existence oracle is introduced, and the harness shows each class A finding of this ticket closed
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cf1
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Make `/signin`, `/verify` and `/reset` match Figma frames 505:124 and 743:125 to 749:217 for the 23 findings the audit gave to this ticket (V4 and R5 stay deliberately unrendered), by editing only the auth views, the auth components and `auth.css`, while using the shared `FormField` options that PR 173 added (`revealStyle="text"`, `errorStyle="glyph"`, the label-action slot) and without weakening any no-account-existence control. Class C and D items are left exactly as the audit records them.

## Baseline

**Verified** on `origin/web/17tnw2b2cew-shared-components` at `5b203064` (the stacked base: audit PR 171, chrome PR 172 and components PR 173 merged together):

- `make marketing-install` exit 0; `npm run build` exit 0.
- Harness baseline run `.visual-parity/baseline-auth` (Chromium and WebKit, 13 auth slugs), `visual_parity.py` exit 0. Style diffs saved per slug before any change.
- Card heights against Figma (Chromium, 1440 wide): Sign in 589.3 vs 518; V1 272 vs 239; V2 432.3 vs 418; V3 598.3 vs 554; V5 491.3 vs 472; V6 473 vs 438; R1 607.8 vs 557; R2 607.8 vs 448; R3 645.8 vs 435; R4 590.3 vs 547; R6 454.3 vs 440; R7 588.8 vs 540.
- Fields: label 14px/600 in the primary ink; input fill `--sc-elevated`, 45px tall, padding 12/16; a 20px reserved row under every field; 3px halo on focus; hint 13px/19.5px; placeholder is `--sc-text-muted` on the elevated fill.
- Primary button 49px tall and 700 weight (Figma 47 and 600); link buttons 55px; the loading label is hidden behind a generic spinner; the info banner shows on R2 and R3; the R7 footer links to /signin; the password toggle is the eye icon on every page; V1 is left-aligned and its live region holds no text; New password is not focused on arrival.
- The auth views carry `.is-submitting :deep(.form-field) { opacity: .5 }`, which dims a field twice (FormField already dims its input).
- `auth_pages_headless.py` pins `EXPECTED_MIN_CHECKS = 1751` and a Sign in title check for "Sign in to SelahCue".

## Inputs and evidence sources

- ClickUp 17tnw2b2cf1 (Goal, Scope, Findings, Acceptance Criteria) and its two comments (the shared chrome review note and the shared components review note N3); audit ticket 17tnw2b2c75; epic 86ajy5v6k
- `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` and `docs/design/visual-parity/marketing/findings/auth.json` (finding ids signin-01 to -16, verify-v1-01 to -03, verify-v2-01 to -03, verify-v3-01/02, verify-v5-01/02, verify-v6-01, reset-r1-01 to -03, reset-r2-01 to -04, reset-r3-01/02, reset-r4-01/02, reset-r6-01, reset-r7-01/02)
- `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` sections 1, 2, 4, 5, 8, 10, 12 and 13
- Committed Figma style dumps `docs/design/visual-parity/marketing/figma-style/*.json`
- `docs/delivery/VISUAL-PARITY-HARNESS.md` section 11
- Goal contracts of PR 172 (`17tnw2b2cev-figma-shared-chrome.md`) and PR 173 (`17tnw2b2cew-shared-components.md`)

## Scope

### In scope

- `implementation/marketing/src/views/{SignInView,VerifyView,ResetView}.vue`, `src/components/auth/*`, `src/assets/styles/auth.css`
- Tests: `tests/authCopy.test.ts`, `tests/authViews.test.ts`, `scripts/auth_pages_headless.py` (`EXPECTED_MIN_CHECKS` raised to the measured count), and new tests (`tests/authFidelity.test.ts`)
- Adoption of the PR 173 options where Figma draws them: the text Show/Hide reveal and the visible cross error on the Reset fields, the label-action slot for the Forgot link on Sign in
- Declared edits outside the footprint, accessibility and the busy cue only, no Figma change (Sign up and Forgot password have no frames): `aria-required="true"` on the sign-up Country select (`SignUpView.vue`, hand-rolled outside `FormField`), with a test; and, from review round 1, the busy glyph (`<AuthSpinner />`) on the loading buttons of `SignUpView.vue` (two) and `ForgotPasswordView.vue` (one), nothing else in those two files
- Re-measuring the four "acceptance row" findings (V3, V6, R4, R6) and reporting the numbers

### Non-goals

- `FormField`, `UiButton`, `tokens.css`, `main.css`, `App.vue`, `router/scroll.ts`, `Navbar`, `Footer`, `UiBadge`, `FaqAccordion`, `PricingCard`, `ConfirmDialog` (shared files from PR 172 and 173: stop and report if a fix needs one)
- "Continue with Google" and the "or" divider (signin-03, class C: DEC-007 rejected OIDC; the harness gate `signin-has-no-google-button` keeps it out)
- Class C and D items: signin-02, -04, -12, -14, -16, verify-v1-03, verify-v2-02, verify-v3-02, reset-r4-02, reset-r7-02, and the Figma/AUTH versus GAP-FILL form-field conflict (contact-19)
- Sign up and Forgot password pages (no frames); V4 and R5 (documented non-render until the backend can prove expiry)
- The Home, Pricing/Features/Download/About and secondary page tickets (other instances)

### Constraints

- Stacked branch: cut from `origin/web/17tnw2b2cew-shared-components`; Draft PR with `--base web/17tnw2b2cew-shared-components`; retargeted and rebased as each of audit #171, chrome #172, components #173 lands; the merge-order gate holds (the stack merges in order, the same day); never merged by this role
- Own worktree `scph-wt/17tnw2b2cf1-auth`, branch `web/17tnw2b2cf1-auth-pages`; no push to the base branch (the branch's upstream was unset because it would have pointed at the base)
- Owner decisions: honest content wins (no invented claim, no Google button); accessibility must not regress (a Figma colour below AA stays accessible in code, recorded as B and flagged to Uma; the Figma brand link ink at 3.7:1 is class D, the current readable ink stays); Figma legacy variables versus `--sc-*` is a deliberate layer; class C and D items are not decided here; NO account-existence oracle (handoff sections 1 and 10): no copy or state may reveal whether an address is registered, V5 stays "If you@... has a SelahCue account waiting to be verified...", Sign in must not hint at password length, the `authViews` guard that bans timers on the auth path stays untouched, and account or licensing state never blocks or implies blocking of live presentation; platform claims are not touched
- No timer, `requestAnimationFrame` or second transport on the auth path (the new focus-on-arrival and error clearing use Vue's `nextTick` and a `watch`)
- `required` is passed only where the design draws a required marker: Sign in, Reset and Verify draw none, so none is passed (decision recorded for Uma)
- Commits carry no attribution trailers; `git push` with BatchMode SSH; `make ci` is not required (Rust, Flutter and the API are untouched)

### Assumptions and unknowns

- **Assumed (decided here, flagged for Uma):** the Figma R2 and R3 frames drop the "This signs you out everywhere" banner; the ticket's acceptance criterion says to hide it during R2 and R3, so it is hidden while field errors show and while submitting, and returns when the user edits a field. The never-blank sentence stays on R1, R4 and R6.
- **Assumed:** editing either R1 field while errors show clears both messages and the button dimming (the audit: "clear it when either field changes"); submitting re-validates, so nothing is submitted unchecked.
- **Assumed:** a disabled `<fieldset>` around the password fields is the way to disable the Show/Hide toggles while a request is in flight without editing `FormField`.
- **Unknown (Uma):** whether Sign in, Reset and Verify should mark fields required (Figma draws no star); whether V1's title may wrap (verify-v1-03); the accessible brand link ink (signin-12); whether the cross glyph on field errors (handoff section 12) should also apply to Sign in, Verify and the pages with no frame.
- **Known limit:** at a device pixel ratio of 1 a browser snaps a 1.5px border to 1px, so the 1.5px focus and error stroke is a 1px border plus a 0.5px inset ring (crisp at 2x, anti-aliased at 1x).

## Dependencies and approvals

- PR 171 (audit), PR 172 (chrome), PR 173 (components): this branch is built on all three and cannot merge before them
- Four-reviewer gate (Cody, Vera, Shadow, Quinn) is brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Sign in reads "Welcome back"; labels are 13px/500 in the secondary ink; inputs are 44px on the inset fill with a 1.5px focus and error stroke and no halo; fields sit 7px apart inside a field and 18px between fields; primary buttons are 47px and secondary 44px with a border; the card content is 358px wide | `node --test tests/authFidelity.test.ts` and `scripts/auth_pages_headless.py` computed styles in real Chrome | exit 0; every value read from the rendered page | 62 node tests pass in `authFidelity.test.ts` (33 of the first 43 were red on the stacked base); `npm run test:states` exit 0: 67 scenarios, 2505 checks, 0 FAIL (207 of 2147 checks were red on the base bundle). Heading "Welcome back", labels 13px/500 in rgb(167,174,190), inputs 44px on rgb(15,17,22), text 14px in, label 7px above its input, a field with no hint or error 67px tall (the Sign in Password field was 75px: the label-action wrapper inherited the page's 24px line), fields 18px apart, no empty meta row, 1.5px stroke (1px border + 0.5px ring) on focus and error with no 3px halo, primary 47px/600 and secondary 44px with a 1px hairline and the content column 358px on every auth state | PASS |
| C-002 | yes | V1 and V2 centre the disc, title and body; V3 to V6 and every Reset state stay left-aligned; the V1 live region contains announcing text | `auth_pages_headless.py` per-state alignment checks; WebKit and Chromium probe | exit 0 | V1 and V2: title and body `text-align: center`, disc centred in the card (offset 0 on both engines); V3, V5, V6, the transport-failure state, R1, R4, R6, R7, Sign in and no-token: left-aligned, disc at the left of the content column; the V2 banner stays left; V1 live region text is "Verifying your email address…" (aria snapshot `status: Verifying your email address…` on both engines) | PASS |
| C-003 | yes | Placeholder, field hint and note text on the auth cards measure at least 4.5:1; the harness contrast survey lists no failing text on any auth slug except the class D link ink held for Uma | `vp_compare` contrast survey over `.visual-parity/final-auth`; computed contrast in `auth_pages_headless.py` | placeholder, hint and note at least 4.5; survey lists only the brand link ink | placeholder 8.49:1, hint 8.12:1, note 8.12:1, label 8.12:1 (asserted in the driver). Review round 1: the harness lists the diamond no more as text (it is an SVG now). The survey on the 13 auth slugs lists only: footer links 4.12:1, Forgot? 3.83:1 (class D, brand ink, Uma) and the decorative info-banner diamond 3.46:1 (passes 3:1 as a graphic; same brand-ink decision). Before: those three plus the diamond at 13px | PASS |
| C-004 | yes | Reset: Show/Hide text reveal; field errors start with the cross; the submit button is dimmed and `aria-disabled` while errors show and clears on edit; while submitting the "Updating password..." label with its glyph is visible, fields are dimmed once and the toggles are disabled; the info banner is hidden on R2 and R3; New password is focused on arrival | `auth_pages_headless.py` scenarios reset-form, reset-both-errors, reset-submitting; keyboard probe on Chromium and WebKit | exit 0 | Show/Hide are words (aria-label and aria-pressed kept, 44px targets, spell-check stays off when revealed); errors start with the cross, 12.5px/500/17px, role alert; both fields 1.5px live stroke; submit held at 50% as the Figma file says (747:194 and 749:143 are both `o: 0.5`; the handoff prose says 45%), aria-disabled, focusable; pressing it with bad input moves focus to the first invalid field, which is described by its message (review of PR 179, Cody 7 and Quinn Q6); released with the banner back after an edit; in flight: "↻ Updating password…" at full strength, button 50%, inputs 50% in total, labels 100%, both toggles disabled and dimmed to 50% with their inputs, hint and banner gone, Tab reaches only the footer link; New password focused on arrival on both engines | PASS |
| C-005 | yes | The R7 footer offers "Request a new reset link" pointing at /forgot-password | `auth_pages_headless.py` reset-unreachable; node source test | link text and href asserted | R7 footer: "Still stuck?" and "Request a new reset link", href /forgot-password, no /signin link (both engines) | PASS |
| C-006 | yes | Sign in's Forgot link sits in the Password label row (visible "Forgot?", accessible name "Forgot your password?"), after the input in DOM order; tab order is Email, Password, Show password, Forgot, Sign in, Create an account; the eye icon stays on Sign in | `auth_pages_headless.py` signin-form; real Tab presses on Chromium and WebKit | order asserted | Forgot? is in the Password label row at the field's right edge (visible "Forgot?", aria-label "Forgot your password?", 24px target without moving the layout); Tab order Email, Password, Show password, Forgot your password?, Sign in, Create an account on Chromium and on WebKit with Option+Tab; the eye icon stays; Sign in in flight: label visible, fields dimmed once, only the Forgot link stays tabbable | PASS |
| C-007 | yes | A test fails if the heading copy, the label colour, the V1 centring, the R3 visible label or the R7 link target regresses; each new test is mutation-proved on a copy | planted fault per test on a copy of the tree | each named fault turns its test red | 33 node faults each turned the named test red (label ink, heading copy, V1 and V2 centring, R7 target, loading label, padding, placeholder ink, Country aria-required, text reveal, AuthShell align, live-region words, password-policy import, halo, note ink, centring scope, button height, label row, banner gap, title line height, input well, glyph column, Forgot target, the busy glyph on a Sign up button, the envelope and the diamond back to text, the forced-colors block moved above the select rule, the held opacity, the label-action line height, the toggle dim, the focus move, the banner glyph box); 33 faults each turned a named headless check red on a rebuilt copy, among them the five the ticket names (heading copy, label colour, V1 centring, R3 visible label, R7 link target). Two of my first checks passed their own mutant because a CSS transition had not finished when they read the value, and one focus check passed because New password already had focus; both are fixed (the driver finishes transitions before a read, and the user starts on the held button) | PASS |
| C-008 | yes | After `npm run build`, `visual_parity.py --suite marketing --engine both` exits 0 for the 13 auth slugs and `vp_style_diff.py` prints no line that belongs to a class A finding of this ticket; every remaining difference is a documented class B, C or D | `visual_parity.py --suite marketing --engine both`; `vp_style_diff.py` per slug on both engines; compared with the baseline run | exit 0; remaining lines each have an owner | `.visual-parity/r1-auth` (first head `.visual-parity/final-auth`, baseline `.visual-parity/baseline-auth`), exit 0 on 13 auth slugs. No line belonging to a class A finding of this ticket is printed on either engine, and verify-v5-02 is now closed as class A: the envelope is a 22px SVG on both engines instead of a symbol-font glyph that measured 13.2px, so no reclassification is needed. Remaining lines: class C or D (Sign in body, divider, Google, banner; V1 title wrap; apostrophes), class B (bullets and unpaired input frames, the 1.5px border snapping, the cross in a field error sitting in its own aria-hidden span (FormField), the fixture address, the hover fill under the capture pointer, and the drawn marks: the harness compares text nodes, so the cross, diamond and envelope Figma sets as text show as design-only lines by intent) | PASS |
| C-009 | yes | The four acceptance rows are re-measured: V3 card 554, V6 438, R4 547, R6 440 at 1440 wide on Chromium and WebKit; any residual is explained | `vp_style_diff` card lines on both engines' DOM dumps (run `.visual-parity/r1-auth`) | numbers reported | Chromium and WebKit identical: V3 554 (was 598.3), V6 438 (473), R4 547 (590.3), R6 440 (454.3), V2 418 (432.3), V5 472 (491.3), R1 557 (607.8), R2 448 (607.8), R3 435 (645.8), R7 540 (588.8), all equal to Figma; V1 268 against 239 (class D wrap: the title is two 29px lines); Sign in 499 against 518 (was 507 before the Password label row was set to Figma's 16px; the 19px left is class C body copy and divider and Google button, and the class D banner) | PASS |
| C-010 | yes | `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:components`, `npm run test:mirrors`, `npm run check:legal` all pass, each with its REQUIRE variable and an exit code captured | run each from `run-gates.sh`, one at a time, unpiped, with `SELAHCUE_HEADLESS_REQUIRE=1` and `SELAHCUE_SWEEP_REQUIRE=1` under `/usr/bin/python3` | all exit 0 | `make marketing-check` exit 0 (type-check, lint, 836 node tests, build); `npm run test:states` exit 0 (2505 checks); `npm run test:responsive` exit 0 on Chromium (2315 checks, 40 routes x 5 widths) and `responsive_sweep.py --engine webkit` exit 0 (2315); `test:legal-pages` exit 0 (419); `article_pages_headless.py` exit 0 (143); `test:components` exit 0 (646 on both engines); `test:mirrors` exit 0 (Django 6.1.1 in a scratch virtualenv outside the repo); `check:legal` exit 0; no SKIPPED marker in any sweep. `make ci` not run: Rust, Flutter and the API are untouched | PASS |
| C-011 | yes | `vp_selftest.py` and `check_fidelity_audit.py` (`--self-test` and `--require-tickets`) pass | run each | all exit 0 | `vp_selftest.py` exit 0 (206 checks); `check_fidelity_audit.py --self-test` exit 0 (97); `--require-tickets` exit 0 (0 problems) | PASS |
| C-012 | yes | No account-existence oracle: the enumeration-equality probe and the timer ban pass unchanged; no copy reveals whether an address is registered; Sign in adds no password-length hint | `npm run test:states` enumeration groups; `tests/authViews.test.ts`; diff review of copy | exit 0; no copy change except the Sign in heading and the R7 footer link | all enumeration groups (card, page, ops, tone, attrs, elapsed; presubmit and in flight) PASS unchanged: the in-flight checks are their own scenarios (`signin-submitting`, `signup-submitting`, `signup-resend-pending`, `forgot-submitting`, `reset-submitting`, `verify-resend-pending`), so no measurement is added to half of a pair; `authViews.test.ts` (timer ban, address ban, transport ban) is green and now also covers `AuthSpinner.vue`; focus on arrival and focus on the first invalid field use `nextTick`, and a test fails if either uses a timer; the only copy changes are "Welcome back" and "Request a new reset link" (plus the visually hidden V1 words, a copy of the existing title); a node tripwire fails if Sign in imports the password policy or states a length; V5 wording unchanged | PASS |
| C-013 | yes | Contrast of every changed foreground and background pair is AA or recorded as B or D; keyboard order, focus, live regions and labels are correct in real renders; no horizontal page scroll at 375, 768 and 1440 | contrast table from `vp_core`; keyboard probe; responsive sweep | no new failing pair; probe order as designed; no horizontal scroll | 30 changed pairs computed: all AA or better except the brand link ink 4.12:1 and Forgot? 3.83:1 (class D, same colours as before) and the decorative diamond 3.46:1 (3:1 graphic); the held and in-flight button label is about 2.8:1 at 50% (Figma draws it dim; inactive controls are exempt; raised to Uma); focus and error strokes 4.00:1 and 5.77:1 against the well; responsive sweep 2315 checks per engine, none failed (320, 375, 768, 1024, 1440); the drawn marks are the same size and weight on Chromium and WebKit at 2x | PASS |
| C-014 | yes | The sign-up Country select is announced as required (`aria-required="true"`, not the native attribute) | node test over the SignUp template; `signup-form` headless check | attribute present, native `required` absent | `select#signup-country` has `aria-required="true"` and no `required` (node test and driver check on Chromium; both red on the base); probe: ["true", false, 44] | PASS |
| C-015 | yes | The diff touches only the footprint, the declared SignUp edit, this contract and new test files | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths | 14 paths: this contract; `auth.css`; `AuthShell.vue`, `AuthBanner.vue`, `StatusDisc.vue`, `AuthSpinner.vue` (new) under `components/auth/`; `SignInView.vue`, `VerifyView.vue`, `ResetView.vue`; `SignUpView.vue` and `ForgotPasswordView.vue` (declared: the Country `aria-required` and the busy glyph on three loading buttons, nothing else); `tests/authFidelity.test.ts` (new), `tests/authViews.test.ts` (AuthSpinner added to the guarded modules); `scripts/auth_pages_headless.py`. No shared file from PR 172 or 173, and `package.json` is not touched | PASS |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact | start comment 1400430000059595, handoff comment 1400430000059619 and the review round 1 handoff 1400430000059798 (QA steps as a list), all read back; decisions comment 1400430000059796 on 17tnw2b2cf3 and shared-components note 1400430000059797 on 17tnw2b2cew, read back; the ticket is in code review; follow-up ticket 17tnw2b2gmm created and read back | PASS |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge-order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` and the same for the chrome and audit branches | isDraft true; behind 0 | https://github.com/First-Pavilion/selahcue/pull/179: isDraft true, base `web/17tnw2b2cew-shared-components`, mergeable; 0 behind and reachable for the audit, chrome and components branches after the last fetch; the description opens with the stack and the merge-order gate | PASS |
| C-018 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow and Quinn, brokered by the coordinator | all four report; no open blocking finding | the coordinator closes this row | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-007 test-first: node tests and headless scenarios written and shown failing on the baseline before the change
- Broader regression verification: C-008 to C-014 on the final head (every offline gate with its exit code, the harness, the self-tests)
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22.18 or newer, `/usr/bin/python3` with Pillow and Playwright (Chromium and WebKit) and `SELAHCUE_HEADLESS_REQUIRE=1`, `SELAHCUE_SWEEP_REQUIRE=1`, network for Inter, a scratch virtualenv outside the repo with Django for `test:mirrors`

## Iteration ledger

### Iteration 1

- Target criterion: all (baseline)
- Hypothesis: the baseline is green and every finding is reproducible from the audit data and the harness
- Change or investigation: read the ticket and its comments, the audit data, the handoff sections, the harness doc and both prior contracts; read the three views, the three auth components, `auth.css`, `FormField` and `UiButton`; built the base and ran the harness on the 13 auth slugs on both engines; saved the per-slug style diffs
- Verifier executed: `make marketing-install` (exit 0), `npm run build` (exit 0), `visual_parity.py --suite marketing --engine both --only <13 auth slugs>` (exit 0)
- Result: baseline recorded (see Baseline)
- New evidence: the primary button weight (700 against Figma 600) and the title line height (30px against 29px) are class A lines the audit text does not list but the diff prints, and both feed the acceptance-row card heights; the build runs the auth Chrome driver with `--virtual-time-budget`, so no new timer may be used for focus or announcements
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-007 (test first)
- Hypothesis: node tripwires and computed-style checks in real Chrome can pin every finding, and they are red on the base
- Change or investigation: wrote `tests/authFidelity.test.ts` and the driver checks first; ran them on the unchanged bundle (33 of 43 node tests and 207 of 2147 checks red); then changed `auth.css`, `AuthShell.vue` and the three views; added a probe with real Tab presses on Chromium and WebKit
- Verifier executed: `node --test tests/authFidelity.test.ts`; `npm run test:states`; the probe
- Result: green after fixes to my own checks (see iteration 3)
- New evidence: card heights land exactly on Figma once the 35px padding, 44px inputs, 7px and 18px rhythm, 47px and 44px buttons, 12.5px/17px notes and banners and the 29px and 31px title lines are in; the layout needs no hack
- Decision: iterate

### Iteration 3

- Target criterion: C-007, C-008, C-009
- Hypothesis: every new check bites, and the harness shows every class A line closed
- Change or investigation: planted faults on copies of the tree (24 node, 23 headless); the headless run found that two checks passed their own mutant because a CSS transition had not finished when the value was read under `--virtual-time-budget`, so `css()` now finishes running transitions first; I had also cut two existing scenarios out of the driver with an over-wide edit (the run reported "no such scenario", restored from the base); the style diff then showed banner copy up to 5px left of Figma because the symbol-font advance of the diamond and cross is narrower than Figma's, fixed with a minimum glyph width; the Forgot link got a 24px target
- Verifier executed: `mutate_node.py`, `mutate_headless.py` (scratch, outside the repo), the full gate run, the harness on both engines
- Result: all PASS; 2266 checks over 64 scenarios; harness exit 0; no class A line left
- New evidence: the shared scratchpad directory is shared by all four instances; my scratch files were moved to my own subdirectory and only my scripts were run
- Decision: handoff

### Iteration 4 (review round 1)

- Target criterion: C-001 to C-017 (every row re-run on the new head)
- Hypothesis: the 23 non-blocking findings of the four reviews can be fixed or recorded inside the footprint and the declared edits, each fix with a check that goes red without it
- Change or investigation: read the four comments in full; tests first for each fix (red on the previous head), then the code; planted 33 node and 33 headless faults on copies; re-ran every gate, the harness on both engines and the card measurements
- Verifier executed: see the predicate table and the Review round 1 section
- Result: all PASS except C-018, which is the coordinator's
- New evidence: an explicit `--user-data-dir` makes `--headless=new --dump-dom` hang on this machine (Chrome 154, macOS: 4 of 4 launches past 20s, with and without the usual flags, and with the directory inside Chrome's own folder), so the leaked-profile fix is a reaper keyed on this run's own server address, not a profile directory; the first focus check could not fail because New password already had focus; a 16px line height on the label-action wrapper still left the row at 17px until its font size was set too
- Decision: handoff

## Review round 1

Four reviewers, all CLEAR, 0 blocking, on head bb6994e2 (code head abc5991d):

- Shadow (security): https://github.com/First-Pavilion/selahcue/pull/179#issuecomment-5979503834
- Cody (code): https://github.com/First-Pavilion/selahcue/pull/179#issuecomment-5979592063
- Quinn (QA): https://github.com/First-Pavilion/selahcue/pull/179#issuecomment-5981783295
- Vera (performance): https://github.com/First-Pavilion/selahcue/pull/179#issuecomment-5981999586

Disposition of every finding:

- Cody 1 and Quinn Q1 (Sign up and Forgot password lose the busy cue): FIXED. One `AuthSpinner.vue` replaces the seven hand-written spans; it is on every loading button including `SignUpView.vue` (two) and `ForgotPasswordView.vue` (one), the two views declared above. A node test fails if any `UiButton` with `:loading` in the five auth views lacks it; three new headless scenarios hold those buttons in flight.
- Cody 2 and Quinn Q7 (forced-colors outline never reached the Country select): FIXED. The block moved below the select's own `outline: none`; a node test resolves the cascade for that exact selector in forced colors. The Chrome driver cannot emulate forced colors; the rule was also read in Chromium forced-colors emulation.
- Cody 3 and Quinn Q4 (glyph sizes depend on the engine; verify-v5-02 partial): FIXED. The envelope (22px), the status-disc cross (16px), the info diamond (14px) and the danger-banner cross (10px) are inline SVG in `StatusDisc.vue` and `AuthBanner.vue`; the three views' selector and the Sign up and Forgot password envelope discs are covered without editing those views. verify-v5-02 closes as class A.
- Cody 4 (dead `.has-reveal-text` rule and its test): FIXED, both deleted.
- Cody 5 (toggle dim unguarded): FIXED, a node test and a driver check, both mutation-proved.
- Cody 6 (nothing announced as required): POSTED, decisions ticket 17tnw2b2cf3 (comment 1400430000059796) and the shared-components ticket 17tnw2b2cew (comment 1400430000059797).
- Cody 7 and Quinn Q6 (held button gives a screen reader nothing): FIXED. A failed re-check moves focus to the first invalid field with `nextTick`, no timer.
- Cody 8 (AuthShell `align` type; `.au-sr-only`): FIXED for the type. The visually-hidden rule stays in `auth.css`: no shared rule exists (BlogView and SupportView carry scoped copies and `main.css` is a shared file); recorded on 17tnw2b2cew.
- Cody 9 (counts in two places): FIXED (23 findings; five checks per state).
- Quinn Q2 (Sign in Password field 8px taller than Figma): FIXED. The Password field is 67px, Sign in card 499 (was 507).
- Quinn Q3 (held opacity 0.45, Figma file 0.5): FIXED to 0.5, the comment corrected, the handoff discrepancy posted (decision 3).
- Quinn Q5 (held button label contrast) and Q9 (border and placeholder contrast): POSTED, decisions 4 and 8.
- Quinn Q8 (error rows no longer reserve space): NO CHANGE, accepted (it follows signin-09 and Figma); noted in the PR and decision 8.
- Vera 1 (/verify card jumps on phones): POSTED, decision 7. Vera 2 (auth.css is global, +405 B gzip): note only, in the PR.
- Vera 3 (headless Chrome leaves profiles): FIXED in a different way than asked. An explicit `--user-data-dir` hangs `--dump-dom` here, so the driver removes the new `scoped_dir*` profiles that hold this run's own `127.0.0.1:<port>` address, proved on a real killed Chrome and a synthetic folder; a full run left none.
- Shadow N1 (R2 and R3 drop the banner): POSTED, decision 1. Shadow N2 (`new Function` in a test): FIXED, a structural reader over the parsed expression.

## Risks and rollback

- Risks: the global `auth.css` overrides also reach the Sign up and Forgot password cards (same `.au-card` and `FormField`); they are checked by the same headless suite and the responsive sweep, and the hand-rolled Country select is restyled to stay consistent with the new field. A scoped override can lose to FormField's scoped rule on specificity; each override is therefore asserted as a computed style in a real browser
- Rollback: revert the PR; every change is in the auth footprint and the one declared SignUp line

## Pause and escalation conditions

- A fix needs a shared file from PR 172 or 173: stop and report the exact change to the coordinator
- A class C or D decision is needed: raise it to Uma or the owner, do not decide it
- The independent-review row stays for the coordinator to close

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cf1-figma-auth-pages.md --completion`
- Validator result: structural OK before work and at the end (exit 0); `--completion` exits 1 with exactly one error, "Predicate C-018: mandatory criterion is PENDING", the independent-review row the coordinator closes; every other mandatory row is PASS
- Independent verification result: pending (the coordinator brokers Cody, Vera, Shadow and Quinn)
- Terminal state: GATE_REVIEW (every mandatory row except the independent review is PASS; review round 1 fixes are in)
- Remaining failed or blocked criteria: C-018 (the coordinator's)
- ClickUp final evidence comment: 1400430000059798 (review round 1 handoff; the first handoff is 1400430000059619)
