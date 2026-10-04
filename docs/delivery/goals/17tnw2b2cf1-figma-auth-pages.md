# Goal Contract — 17tnw2b2cf1-figma-auth-pages

## Identity

- Goal ID: 17tnw2b2cf1-figma-auth-pages
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The Sign in page and the Verify (V1-V6) and Reset (R1-R7) states match the Figma frames the audit compared them with, the accessibility failures the audit measured are fixed, no account-existence oracle is introduced, and the harness shows each class A finding of this ticket closed
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cf1
- Created: 2026-10-04
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Make `/signin`, `/verify` and `/reset` match Figma frames 505:124 and 743:125 to 749:217 for the 22 findings the audit gave to this ticket (V4 and R5 stay deliberately unrendered), by editing only the auth views, the auth components and `auth.css`, while using the shared `FormField` options that PR 173 added (`revealStyle="text"`, `errorStyle="glyph"`, the label-action slot) and without weakening any no-account-existence control. Class C and D items are left exactly as the audit records them.

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
- One declared edit outside the footprint, accessibility only: `aria-required="true"` on the sign-up Country select (`SignUpView.vue`, hand-rolled outside `FormField`), with a test. Sign-up has no frames; this is not a Figma change
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
| C-001 | yes | Sign in reads "Welcome back"; labels are 13px/500 in the secondary ink; inputs are 44px on the inset fill with a 1.5px focus and error stroke and no halo; fields sit 7px apart inside a field and 18px between fields; primary buttons are 47px and secondary 44px with a border; the card content is 358px wide | `node --test tests/authFidelity.test.ts` (CSS source) and `scripts/auth_pages_headless.py` computed styles in real Chrome | exit 0; every value read from the rendered page | pending | PENDING |
| C-002 | yes | V1 and V2 centre the disc, title and body; V3 to V6 and every Reset state stay left-aligned; the V1 live region contains announcing text | `auth_pages_headless.py` scenarios (computed text-align and disc position per state); node source test | exit 0 | pending | PENDING |
| C-003 | yes | Placeholder, field hint and note text on the auth cards measure at least 4.5:1; the harness contrast survey lists no failing text on any auth slug except the class D link ink held for Uma | `vp_compare` contrast survey over the run; computed contrast in `auth_pages_headless.py` | placeholder, hint and note at least 4.5; survey lists only the link ink | pending | PENDING |
| C-004 | yes | Reset: Show/Hide text reveal; field errors start with the cross; the submit button is dimmed and `aria-disabled` while errors show and clears on edit; while submitting the "Updating password..." label with its glyph is visible, fields are dimmed once and the toggles are disabled; the info banner is hidden on R2 and R3; New password is focused on arrival | `auth_pages_headless.py` reset scenarios (computed opacity, disabled toggles, focus, banner absence) | exit 0 | pending | PENDING |
| C-005 | yes | The R7 footer offers "Request a new reset link" pointing at /forgot-password | `auth_pages_headless.py` `reset-unreachable`; node source test | link text and href asserted | pending | PENDING |
| C-006 | yes | Sign in's Forgot link sits in the Password label row (visible "Forgot?", accessible name "Forgot your password?"), after the input in DOM order; tab order is Email, Password, Show password, Forgot, Sign in, Create an account; the eye icon stays on Sign in | `auth_pages_headless.py` `signin-form`; real keyboard Tab probe | order asserted | pending | PENDING |
| C-007 | yes | A test fails if the heading copy, the label colour, the V1 centring, the R3 visible label or the R7 link target regresses; each new test is mutation-proved on a copy | planted fault per test on a scratch copy | each named fault turns its test red | pending | PENDING |
| C-008 | yes | After `npm run build`, `visual_parity.py --suite marketing --engine both` exits 0 for the 13 auth slugs and `vp_style_diff.py` prints no line that belongs to a class A finding of this ticket; every remaining difference is a documented class B, C or D | harness run and style-diff comparison with the baseline run | exit 0; remaining lines each have an owner | pending | PENDING |
| C-009 | yes | The four acceptance rows are re-measured: V3 card 554, V6 438, R4 547, R6 440 at 1440 wide on Chromium and WebKit; any residual is explained | `vp_style_diff` card lines on both engines' DOM dumps | numbers reported | pending | PENDING |
| C-010 | yes | `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:components`, `npm run test:mirrors`, `npm run check:legal` all pass, each with its REQUIRE variable and an exit code captured | run each, one at a time, unpiped | all exit 0 | pending | PENDING |
| C-011 | yes | `vp_selftest.py` and `check_fidelity_audit.py` (`--self-test` and `--require-tickets`) pass | run each | all exit 0 | pending | PENDING |
| C-012 | yes | No account-existence oracle: the enumeration-equality probe and the timer ban pass unchanged; no copy reveals whether an address is registered; Sign in adds no password-length hint | `npm run test:states` enumeration groups; `tests/authViews.test.ts`; diff review of copy | exit 0; no copy change except the Sign in heading and the R7 footer link | pending | PENDING |
| C-013 | yes | Contrast of every changed foreground and background pair is AA or recorded as B or D; keyboard order, focus, live regions and labels are correct in real renders; no horizontal page scroll at 375, 768 and 1440 | contrast table from `vp_core`; keyboard probe in Chromium and WebKit; responsive sweep | no new failing pair; probe order as designed | pending | PENDING |
| C-014 | yes | The sign-up Country select is announced as required (`aria-required="true"`, not the native attribute) | node test over the SignUp template; `signup-form` headless check | attribute present, native `required` absent | pending | PENDING |
| C-015 | yes | The diff touches only the footprint, the declared SignUp edit, this contract and new test files | `git diff --name-only origin/web/17tnw2b2cew-shared-components` | only those paths | pending | PENDING |
| C-016 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | present, lists intact | pending | PENDING |
| C-017 | yes | A Draft PR is open with base `web/17tnw2b2cew-shared-components`, the description says it is stacked and states the merge-order gate, and the branch is not behind any of the three base branches | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2cew-shared-components` and the same for the chrome and audit branches | isDraft true; behind 0 | pending | PENDING |
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

## Risks and rollback

- Risks: the global `auth.css` overrides also reach the Sign up and Forgot password cards (same `.au-card` and `FormField`); they are checked by the same headless suite and the responsive sweep, and the hand-rolled Country select is restyled to stay consistent with the new field. A scoped override can lose to FormField's scoped rule on specificity; each override is therefore asserted as a computed style in a real browser
- Rollback: revert the PR; every change is in the auth footprint and the one declared SignUp line

## Pause and escalation conditions

- A fix needs a shared file from PR 172 or 173: stop and report the exact change to the coordinator
- A class C or D decision is needed: raise it to Uma or the owner, do not decide it
- The independent-review row stays for the coordinator to close

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cf1-figma-auth-pages.md --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: C-018 (the coordinator's)
- ClickUp final evidence comment: pending
