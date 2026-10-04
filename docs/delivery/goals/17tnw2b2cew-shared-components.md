# Goal Contract — 17tnw2b2cew-shared-components

## Identity

- Goal ID: 17tnw2b2cew-shared-components
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The five shared marketing components (UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog) match the Figma designs for the 13 class A/E findings the audit assigned to them, so the area tickets only compose them, and no page that uses them regresses
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cew
- Created: 2026-10-03
- Updated: 2026-10-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Change only `implementation/marketing/src/components/{UiBadge,FormField,FaqAccordion,PricingCard,ConfirmDialog}.vue` (and their tests) so the 13 findings the Figma fidelity audit assigned to this ticket are closed at the component, with every existing prop and default look kept backward compatible and every consumer page unharmed.

## Baseline

**Verified** on `origin/web/17tnw2b2c75-figma-fidelity-audit` at `0990433e` (the unmerged audit branch, PR #171; the harness exists only there):

- `UiBadge` accepts and styles `live|preview|ready|ndi|featured|new`. Views pass `accent` (Home x6, ReliabilityPillar, OutputManagerMockup, PricingCard) and `warn` (ReliabilityPillar, Features, Account, Admin x6, Affiliates x2, Changelog); both render unstyled. `PricingView` passes `text="Save 20%"`, a prop UiBadge does not have (nothing renders).
- `FormField` has an icon reveal toggle (28px), an icon-plus-message error, no label-row slot. `auth_pages_headless.py` (1751 checks, exact count) depends on `.password-toggle` with `aria-label` and `aria-pressed`.
- `FaqAccordion` has `aria-expanded` only; collapsed answers stay in the accessibility tree; no `aria-controls`.
- `PricingCard` renders `<UiButton ... block>` with no `to`, so the CTA is a `<button>` with no action; `block` is not a UiButton prop.
- `ConfirmDialog` has no focus management, `aria-label` only, centred 440px card, grey confirm for `warning`.
- `npm test`: 612 pass, 0 fail. `npm run build`: exit 0. Harness baseline run: `.visual-parity/run-20261003-213112` (pricing, careers, changelog, signin, reset-r1, reset-r2, home, affiliates, account; Blink and WebKit); per-slug `vp_style_diff` output saved before any change.

## Inputs and evidence sources

- ClickUp 17tnw2b2cew (Goal, Scope, Findings, Acceptance Criteria); audit ticket 17tnw2b2c75; epic 86ajy5v6k; claims removal 17tnw2b0x3h
- `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` and the finding data under `docs/design/visual-parity/marketing/findings/*.json` (ids devices-d2-01, home-32, pricing-04, affiliates-08, careers-02, changelog-03, home-10, home-30, reset-r1-01, reset-r2-01, signin-05, account-12, home-39)
- Committed Figma style dumps `docs/design/visual-parity/marketing/figma-style/*.json` and reference PNGs (Figma values are read from these, not from live Figma)
- `docs/delivery/VISUAL-PARITY-HARNESS.md` section 11; `AUTH-LANDING-PAGES-HANDOFF.md` sections 7.2, 8.4, 12; `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` sections 3d, 7a, 7b

## Scope

### In scope

- The five component files and tests that guard them (a node test, a small component gallery, a headless behaviour script), plus one out-of-footprint line: the `test:components` script in `implementation/marketing/package.json` (review round 1, Cody 2 and Quinn 3)
- Opt-in props and slots for new looks; accessible, backward-compatible defaults
- Re-running the harness on the surfaces that use these components

### Non-goals

- Any view, page layout or copy (area tickets); Navbar, Footer, UiButton, tokens.css, main.css, App.vue, router (the chrome ticket 17tnw2b2cev, parallel)
- Choosing the accessible brand ink or the accessible destructive-button ink (class D, Uma: account-25, home-44, pricing-21, account-31)
- Removing the unbacked annual-discount maths in `PricingCard` (class C, owner decision, 17tnw2b0x3h)
- Editing the audit report or audit data

### Constraints

- Stacked branch: cut from the audit branch, Draft PR with `--base web/17tnw2b2c75-figma-fidelity-audit`; must be retargeted to `main` and rebased after #171 merges; never merged by this role
- Footprint: the five components and tests. Anything else is stopped and reported. New files limited to this contract, `tests/sharedComponents.test.ts` and its golden fixture, `tests/gallery/*` (including `outDir.ts`), `scripts/shared_components_headless.py`; the one out-of-footprint edit is the `test:components` line in `package.json`. `.github/workflows` and the Makefile are not touched (CI wiring is on follow-up ticket 17tnw2b2fum)
- Owner decisions: honest content wins over Figma; fidelity must not regress accessibility (a Figma colour that fails AA stays accessible, recorded as B, flagged to Uma); Figma legacy variables versus `--sc-*` is a deliberate layer
- No new token in `tokens.css`; any colour that Uma must choose is one overridable custom property inside UiBadge, defaulting to today's rendering
- Existing props and defaults stay backward compatible; no unbounded state; `git push` with BatchMode SSH; no attribution trailers

### Assumptions and unknowns

- **Assumed:** `text` on UiBadge is a mistake in `PricingView` (the badge has never rendered it); rendering it would newly show the unbacked "Save 20%" claim (pricing-18, class C), so UiBadge does not render it and warns in development instead. The slot is the one content API.
- **Decided (coordinator, review round 1):** a RELEASE GATE. The PR stays Draft and is not marked Ready or merged to `main` before the Home (17tnw2b2cex) and Pricing (17tnw2b2cey) PRs, which pass `to` and switch Home's six section labels to `variant="eyebrow"`, are ready to merge beside it. Until then Home and Pricing would show disabled "Not available yet" plan buttons and filled section chips.
- **Unknown (Uma):** the accessible brand ink and destructive-button ink; flagged, not chosen.
- **Decided:** `npm run test:components` runs the headless script (`--require`, both engines). Running it in CI is added to follow-up ticket 17tnw2b2fum.

## Dependencies and approvals

- Chrome ticket 17tnw2b2cev (Farah 1a) runs in parallel on other files; no shared file
- Four-reviewer gate brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | UiBadge defines accent, warn and eyebrow besides the six it had; every variant a view passes is defined; a test fails when a view passes an undefined variant | `node --test tests/sharedComponents.test.ts` | exit 0; the real-tree check passes and its positive control fails on a planted bad variant | exit 0, 50 tests (the whole `npm test`: 662 pass); 23 of the first 39 were red on the audit-branch components; 12 planted faults in round 0 and 19 more in round 1 each turned the node tests or the browser script red and were restored | PASS |
| C-002 | yes | The page eyebrow pill (`featured`) is 12px/700, 0.1em, 6px 12px, elevated fill; its ink is one overridable custom property | gallery computed styles via `scripts/shared_components_headless.py` | computed values equal Figma; setting the property changes featured, accent and eyebrow ink | featured 12px/700/1.2px, 5px 11px plus the 1px border, 27px tall, `rgb(28,31,40)`; `--ui-badge-ink` on an ancestor re-inks all three; harness DOM dump for /careers: 11px/600/0.55px/#201f3a/26.5px before, 12px/700/1.2px/#1c1f28/27px after | PASS |
| C-003 | yes | FormField has a `label-action` slot (DOM order kept, and reactive to a slot added later), a text Show/Hide reveal option and a visible cross error option; required fields are announced; a password is never spell-checked; the default look is unchanged | node SSR golden; gallery computed-style comparison against the audit branch, per engine | identical default styles; tab order Email, Password, Forgot | golden pinned: 8 default cases, equal to the audit branch's output once the three named additions are removed (aria-required on a required field; spellcheck, autocorrect and autocapitalize off on a password input; Vue's empty comment placeholder and scope hash are ignored); `--compare-defaults` against recordings of the audit-branch components, per engine: 90 elements, 0 differences on Chromium and on WebKit (three runs in round 1, six in the re-check, five more inside the final gate run); the scrim's width is recorded as the viewport's rather than dropped, and `backdrop-filter` is recorded (see Re-check round); a planted difference is reported on both engines and without the transition wait it fails on 2 values in 3 of 3 runs; password attributes read after Show in the browser; a slot added after the first render appears; tab order `s-email, s-password, Show password, Forgot your password?, Sign in` | PASS |
| C-004 | yes | FaqAccordion answers have id, `role=region`, `aria-labelledby`; buttons have `aria-controls` and `aria-expanded`; collapsed answers are out of the accessibility tree; a boxed option matches the Affiliates frame | node SSR test; headless accessibility snapshot and computed style | attributes present; collapsed answer absent from the snapshot; boxed card 880px, r16, 18px 22px | node tests pass; `aria_snapshot` holds only the open answer, follows a click, Enter and Space toggle; boxed card 880 wide and 333 tall, radius 16, rows 55 closed (the last included) and 113 open as drawn; in forced colors (Chromium emulation) the card keeps a 1px outline where the inset ring is turned off | PASS |
| C-005 | yes | PricingCard takes a destination (link) or renders an honest disabled CTA, never a dead button; lays out as Figma (top aligned, r18, 2px primary border on the popular plan, CTA above the divider, SVG ticks) | node AST and SSR test; gallery geometry | no enabled button without an action; geometry equals Figma boxes | cards 400 wide, tops equal in a grid that says stretch, r18, 2px primary border on the popular plan, CTA 340x44 r11 above the divider, chip 22 tall right-aligned in the header row, SVG ticks; links for Free and Church, a disabled button described by a visible note for Pro; Tab skips it | PASS |
| C-006 | yes | ConfirmDialog is extended, not forked: 420px, banner slot, hint, cancel initial focus, red confirm, focus trapped and restored, Escape cancels, aria-labelledby and describedby; two stacked dialogs are safe; focus has a fallback when the opener is gone; the default dialogs look and behave as before | node SSR test; headless focus script; responsive sweep overlay check | all assertions pass | initial focus is Keep active; Tab and Shift+Tab cycle inside; focus pushed outside is pulled back; Escape, scrim click and confirm return focus; the shared reference-counted lock holds the page; two dialogs at once: no page error and at most 12 focus events (89 and a stack overflow before), page locked until both are closed in either order or by Escape twice; content 364 and buttons 177 (to 0.5); safe action on top at 375px; `fallbackFocus` takes focus when the opener is removed, also when the dialog was opened and confirmed with the mouse in WebKit (the page body is not an opener), and an unparseable selector throws nothing; closing the newest of two script-opened dialogs refocuses the one still open; default dialogs: 90 computed-style elements identical, per engine | PASS |
| C-007 | yes | Every consumer still renders and behaves, and every other offline gate under `implementation/marketing/scripts` passes | `npm run test:states`, `npm run test:responsive` (Chromium and WebKit), `npm run test:legal-pages`, `article_pages_headless.py`, `npm run test:mirrors`, `npm run check:legal`, each with its REQUIRE variable set | exit 0 | `test:states` exit 0, 60 scenarios, 1751 checks, 0 FAIL; `test:responsive` exit 0, 2281 checks over 40 routes x 5 widths, 0 failed; the same sweep on WebKit exit 0, 2281 checks; `test:legal-pages` exit 0, 419 checks; `article_pages_headless.py` exit 0, 143 of 143; `test:mirrors` exit 0 (Django 6.1.1 on Python 3.14.5, in a scratch virtualenv outside the repo); `check:legal` exit 0; re-run on head eef2b05c in the re-check pass with the same results | PASS |
| C-008 | yes | Harness re-run, stated honestly: at the component, each of the 13 findings' own harness lines are closed; every remaining line is named with the page that adopts it, and none regressed. The ticket's wording (no class A line printed for signin, reset-r1, reset-r2 and changelog) cannot be met inside the footprint and is restated here | `visual_parity.py --suite marketing --engine both`; `vp_style_diff.py` per slug; compared with a fresh run on the audit-branch components with the same tools | exit 0; line sets compared; every remaining line has an owner | run `.visual-parity/run-20261004-081749` (baseline `run-20261004-082056` in the throwaway baseline tree), exit 0; lines closed: pricing 19, home 36, changelog 4, account 2, features 2, blog 2. signin, reset-r1 and reset-r2 are line-for-line identical to the baseline because those pages do not pass the new options until the auth ticket. changelog IMPROVED is the view's variant choice (`ndi`); after it moves to `accent` its ink will be `--sc-text`, not brand blue, until Uma chooses, so one colour line remains by design. Home's six labels stay chip-sized until the Home ticket uses `eyebrow` | PASS |
| C-009 | yes | `make marketing-check`, `npm test`, `vp_selftest.py` and `check_fidelity_audit.py` (self-test and `--require-tickets`) pass | run each, capture exit codes unpiped | all exit 0 | `make marketing-check` exit 0; `npm test` exit 0 (662 pass); `vp_selftest.py` exit 0 (206 checks); `check_fidelity_audit.py --self-test` exit 0 (97 checks); `check_fidelity_audit.py --require-tickets` exit 0 (0 problems); eslint and vue-tsc inside marketing-check exit 0 | PASS |
| C-010 | yes | Contrast of every changed foreground/background pair is AA or recorded as B/D; no horizontal page scroll at 375, 768, 1440 | contrast table from `vp_core`; responsive sweep | no new failing pair; sweep reports none | 24 pairs computed in round 0 and no colour changed since; three fail and none is new: the page-eyebrow ink 3.49:1 (was 3.38, class D, one property), the label-row link primary on surface 3.83:1 (same colour as the current Forgot link, class D) and white on the live red 3.27:1 in the unchanged centred dialog (class D); the new devices dialog uses 5.94:1 dark ink instead of Figma's white; sweep: no horizontal scroll at 320, 375, 768, 1024, 1440, both engines | PASS |
| C-011 | yes | The diff touches only the footprint plus this contract, the node test and its golden, the gallery, the headless script and one `package.json` line | `git diff --name-only origin/web/17tnw2b2c75-figma-fidelity-audit` | only those paths | 15 paths: this contract; the five components; `tests/sharedComponents.test.ts`; `tests/fixtures/formfield-default.json`; five files under `tests/gallery/`; `scripts/shared_components_headless.py`; `package.json` (the `test:components` script, declared out of footprint); no chrome file, no `tokens.css`, no view, no audit data, no workflow, no Makefile | PASS |
| C-012 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, plus the gate and the round 1 handoff, read back | ClickUp read-back | present, lists intact | start 1400430000059200, handoff 1400430000059468, release gate 1400430000059548; round 1 handoff 1400430000059551; re-check handoff 1400430000059580, harness restatement 1400430000059575, correction 1400430000059576, auth note 1400430000059574; notes on 17tnw2b2cex (1400430000059534) and 17tnw2b2cey (1400430000059535), all read back | PASS |
| C-013 | yes | A Draft PR is open with base `web/17tnw2b2c75-figma-fidelity-audit`, the description says it is stacked and states the release gate at the top, and the branch is not behind its base | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2c75-figma-fidelity-audit` | isDraft true; base correct; behind 0 | PR https://github.com/First-Pavilion/selahcue/pull/173: isDraft true, base web/17tnw2b2c75-figma-fidelity-audit; behind count 0 after the last fetch; description rewritten for review round 1 and again for the re-check (the gate now binds both page PRs) | PASS |
| C-014 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | Round 1 at `e1f7f73b`: Shadow CLEAR, Vera CLEAR, Cody BLOCKING (1) and Quinn BLOCKING (1), both the same finding (merge order: the "Not available yet" buttons and filled chips on Home and Pricing if this PR merges before the page tickets). Re-check at `9228a485`: Shadow CLEAR (PR comment 5978141933), Cody blocker CLEAR (5978305615) and Quinn blocker CLEAR (5978296795): the release gate is accepted. Six Low findings from the re-check were fixed afterwards (code head `eef2b05c`, head `0628e4e1`) and not re-reviewed by the reviewers who raised them; each came with a mutation proof. The orchestrator verified at `0628e4e1`: Draft, mergeable, 0 behind the audit branch, linear history, files inside the footprint plus the declared package.json line. The RELEASE GATE stays in force: the PR stays Draft and is not marked ready or merged before the Home and Pricing PRs are ready beside it, and the gate binds both page PRs. Closed by the orchestrator 2026-10-04 | PASS |
| C-015 | yes | The release gate is recorded where it will be read, so the PR cannot go Ready or merge alone | PR description, ClickUp read-back | gate at the top of the PR; comment on 17tnw2b2cew; one note each on 17tnw2b2cex and 17tnw2b2cey | PR 173 description opens with the gate; ClickUp comments 1400430000059548, 1400430000059534 and 1400430000059535 read back | PASS |
| C-016 | yes | Every finding of review round 1 has a disposition: fixed, documented, deferred with a ticket, or disagreed with a reason | the Review round 1 section below | every finding of the four reviews listed | see the section below | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-006 by test-first node tests and the headless script, each shown failing before the change
- Broader regression verification: C-007 to C-010 (full suites, harness re-run, selftests)
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium, WebKit), network for Inter

## Iteration ledger

### Iteration 1

- Target criterion: all (baseline)
- Hypothesis: the baseline is green and the 13 findings are reproducible from the audit data
- Change or investigation: read the ticket, audit findings, harness doc, the five components and every consumer (about 70 call sites); built the baseline and ran the harness
- Verifier executed: `npm run build` (exit 0), `npm test` (612 pass), `visual_parity.py` baseline (exit 0)
- Result: baseline recorded; two traps found: `text="Save 20%"` would newly show an unbacked claim if rendered; `auth_pages_headless.py` pins an exact check count and `.password-toggle` semantics
- New evidence: harness lines for signin, reset and changelog cannot clear until the views adopt the new options, so component-level evidence is the closure test
- Decision: iterate

### Iteration 2

- Target criterion: C-001 to C-006
- Hypothesis: component behaviour can be pinned by node render tests plus a gallery measured in a real browser, and each check goes red on the old components
- Change or investigation: wrote the node tests first (23 of 39 red on the audit-branch components), then the five components; added a gallery and a headless script (116 checks, 75 failures on the old components; 232 checks, 0 failures on the new, in Chromium and WebKit)
- Verifier executed: `node --test tests/sharedComponents.test.ts`; `scripts/shared_components_headless.py --engine both`
- Result: green; the first headless runs failed for test reasons, each understood: a rotated icon widens its box, smooth scrolling and a running accordion transition move the page between two measurements (the script now settles first), a border snaps to whole device pixels at a ratio of 1, WebKit on macOS does not Tab to buttons without Option, and a click does not focus a button in Safari
- New evidence: the gallery's own CSS leaked into the Show toggle (fixed by scoping it); an empty badge would draw a dark pill beside "Annual" now that accent has a fill (fixed with `:empty`)
- Decision: iterate

### Iteration 3

- Target criterion: C-007 to C-011
- Hypothesis: the change harms no page and closes the harness lines it should
- Change or investigation: ran every suite on the final head; compared the harness style-diff line sets with the baseline; computed contrast for every changed pair; planted 12 faults in the components and confirmed each turns the node tests red; merged the chrome branch into a scratch tree to confirm both change sets coexist (738 node tests and 468 headless checks pass there)
- Verifier executed: see the predicate table
- Result: all PASS; the signin, reset-r1 and reset-r2 pages are unchanged line for line, because they adopt the new options in the auth ticket
- New evidence: Home's six section labels render as chips until the Home ticket switches them to `variant="eyebrow"`; `PricingCard` CTAs on Home and Pricing are disabled with a note until the area tickets pass `to`
- Decision: handoff

### Iteration 4 (review round 1)

- Target criterion: C-001 to C-016
- Hypothesis: the four reviews' findings can be fixed inside the footprint, each with a test that goes red without the fix
- Change or investigation: read the four comments in full; fixed or documented every finding; added 11 node tests and a larger browser script (586 checks); planted 19 faults to prove each new test; re-recorded the audit branch's default look per engine and compared (90 elements, 0 differences, both engines, three runs); merged the audit branch three times as it moved (no source change in it); ran every offline gate on the merge result
- Verifier executed: see the predicate table
- Result: all PASS except C-014, which is the coordinator's
- New evidence: the earlier "90 elements, 0 differences" was a measurement race (a 150 ms focus-ring fade), not a product difference; two of my own first mutations were unfaithful (an undefined name broke the static case too) and were redone properly
- Decision: handoff

## Review round 1

Comments on PR 173 at head e1f7f73b:
- Shadow (security and privacy), CLEAR, 0 blocking: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5977665664
- Cody (code), BLOCKING 1: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5977706964
- Vera (performance), CLEAR, 0 blocking: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5977778817
- Quinn (QA), BLOCKING 1: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5977807423

Coordinator decision on the blocker (Cody 1 and Quinn B1, the same finding): option (a), a release gate. The PR stays Draft until the Home and Pricing page PRs are ready beside it.

Dispositions:
- Cody 1 / Quinn B1 (blocking): gate recorded on the PR, on 17tnw2b2cew and as a note on 17tnw2b2cex and 17tnw2b2cey; QA step 1 reworded.
- Shadow 1 (Medium, privacy): fixed. A password input renders spellcheck false, autocorrect off and autocapitalize off, hidden and shown. Proof: node tests, a browser test after Show; removing spellcheck turned 5 node tests and 4 browser checks red, and losing autocorrect only after Show turned 2 browser checks red.
- Shadow 2 (Low): documented in a code comment; no code change (Vue writes the typed value into the value attribute, vuejs/core#6007; nothing serialises the DOM today).
- Shadow 3 (Low): fixed. `tests/gallery/outDir.ts` refuses a non-empty folder that is not a gallery build. Proof: with the guard removed the real-build test goes red.
- Shadow 4 (informational): not changed; no consumer passes undeclared attributes and the hardening lives in the component.
- Vera 1 (Medium): fixed. The shared `pageScrollLock` and a newest-only stack. Proof: with the stack disabled the browser script shows a stack overflow and 89 focus events (10 red); with the dialog writing its own overflow, 13 checks and 2 node tests go red.
- Vera 2 / Quinn 4 / Cody 4: fixed. The comparison waits for the transition and runs per engine. Proof: without the wait it fails on exactly the reviewers' 2 values in 3 of 3 runs. The scrim's width is excluded on purpose: it is the viewport's, which grows by one scrollbar width when the lock removes the scrollbar (12px in WebKit). Accepted and documented; a page-level `scrollbar-gutter: stable` in `main.css` (chrome ticket) would remove it.
- Vera, footer layout shift (pre-existing): deferred; it needs its own ticket in the chrome area and none was created here.
- Cody 2 / Quinn 3: `npm run test:components` added (a one-line `package.json` edit, out of footprint). CI wiring deferred to 17tnw2b2fum.
- Cody 3 (Medium): fixed. Slots are read from `$slots` in the template. Proof: with `useSlots()` again, the browser test and a node tripwire go red for both components.
- Cody 5: fixed. One comparison function, called by the control; the scope hash is ignored. Proof: with the comparison neutered the control goes red.
- Cody 6: fixed (dead class, comment, `annual` pointer to 17tnw2b0x3h).
- Cody 7: fixed in the PR text.
- Quinn 1: restated in C-008 above.
- Quinn 2: fixed, default unchanged. Optional `fallbackFocus`. Proof: without the fallback line the browser check goes red; without the try/catch an unparseable selector throws (2 red).
- Quinn 5: fixed (364 and 177, tolerance 0.5). Proof: padding back to 28 turned 6 checks red.
- Quinn 6: fixed (14px). Proof: back to 16px turns the check red.
- Quinn 7: fixed (55, 113, 333). Proof: a real border gives 335 and 56-high rows give 336 (red).
- Quinn 8: fixed (safe action on top at 375px). Proof: column-reverse turns the check red.
- Quinn 9: fixed (label tied to input). Proof: removing the `for` turns 2 node tests red.
- Quinn 10 (contact-12): fixed for the component and tested on the real call sites (sign-up 4, forgot-password 1, contact 3). Sign in, Reset and Verify mark no field `required`; whether they should is the auth ticket's call. Proof: removing `aria-required` from the input turns 4 node tests red including the real-tree one.
- Quinn 11 (informational): noted (scroll-lock shift as above; the Affiliate lockup growth is the new badge scale).

### Iteration 5 (re-check)

- Target criterion: C-003, C-004, C-006, C-007, C-012, C-013
- Hypothesis: the six Low findings of the re-check share two root causes (the opener is the page body; the measurement is not yet at rest) and can be fixed in the footprint
- Change or investigation: read both comments in full; treated the body as no opener and refocused a remaining dialog; kept the scrim width and the backdrop filter in the comparison; added a forced-colors outline; loaded all four font weights and waited for the font set; added a mouse-opened case and script-opened stacked cases; planted five faults; re-recorded the audit branch's default look and compared it eleven times; re-ran every gate
- Verifier executed: see the predicate table
- Result: all PASS except C-014, which is the coordinator's
- New evidence: forced colors is reported by WebKit but not applied, so that check runs in Chromium only (a printed note says so); one rm of a shell-variable path was refused by the safety check and was rewritten without it (the throwaway tree held nothing to remove)
- Decision: handoff

## Re-check round

Comments on PR 173 at head 9228a485:
- Cody (code), CLEAR, 0 blocking, 3 new Low: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5978305615
- Quinn (QA), CLEAR, 0 blocking, 3 new Low: https://github.com/First-Pavilion/selahcue/pull/173#issuecomment-5978296795

Both accepted the release gate. Cody's note, recorded in the PR description: when the Home and Pricing page PRs are opened on top of this branch, merging either one carries PR 173's commits to `main`, so the gate must bind BOTH page PRs, not only 173.

Dispositions:
- Quinn N1 (Low, accessibility): fixed. Closing the newest of two stacked dialogs refocuses the one still open. Proof: with that line removed, the three script-opened cases go red on both engines.
- Cody B (Low): fixed. The page body is not an opener, so `fallbackFocus` applies after a mouse click in WebKit. Proof: with the body counted as an opener again, the mouse-opened case is red in WebKit (landing on the body).
- Cody A (Low): fixed. The scrim width is recorded as the viewport's (a number only when it does not match), and `backdrop-filter` is recorded. Proof: `inset: 0 40px 0 0` on the scrim and removing the default dialog's blur are each red on both engines.
- Cody C (Low): fixed. The boxed FAQ card has a transparent 1px outline inset by its width, so forced colors still draws its edge. Proof: with the outline removed the new forced-colors check is red in Chromium. WebKit does not apply forced colors, so it is skipped with a note.
- Quinn N2 (Low, test reliability): fixed. All four Inter weights are loaded and the font set is awaited before measuring; opening the gallery retries once, with a printed note, and a second failure is raised. Proof of stability: six consecutive defaults comparisons on both engines before the gate run and five inside it, all clean (a failure cannot be provoked on demand, so this is a stability count, not a mutation).
- Quinn N3 (Low, auth ticket): posted on 17tnw2b2cf1 (1400430000059574); not mine to edit.
- Bookkeeping: harness criterion restated on 17tnw2b2cew (1400430000059575); the 18-to-19 correction is 1400430000059576; the existing footer layout shift ticket https://app.clickup.com/t/17tnw2b2g24 is linked from the PR description instead of creating another.

## Risks and rollback

- Risks: a badge scale change touches every page with a badge; the default FormField must stay pixel-identical; merging before the area tickets leaves Home section labels as chips and PricingCard CTAs disabled
- Rollback or recovery: revert the PR; every new look is opt-in except UiBadge geometry and the FaqAccordion accessibility attributes

## Pause and escalation conditions

- A fix needs a file outside the footprint: stop and report to the coordinator
- A fix needs a token that is not in `tokens.css`: stop and report to the chrome ticket owner
- An ink or destructive-button colour that only Uma can choose: keep the accessible value, flag it

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cew-shared-components.md --completion`
- Validator result: the structural check passes and the completion check passes (C-014 closed by the orchestrator on 2026-10-04)
- Independent verification result: round 1 at `e1f7f73b` (Shadow 5977665664, Cody 5977706964, Vera 5977778817, Quinn 5977807423); re-check at `9228a485` (Shadow 5978141933, Cody 5978305615, Quinn 5978296795): all four clear, blockers cleared by the recorded release gate
- Terminal state: VERIFIED_COMPLETE for this ticket's criteria. The PR stays Draft under the RELEASE GATE (not ready or merged before the Home and Pricing PRs are ready beside it) and is retargeted to main after the audit PR merges
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: 1400430000059468 on https://app.clickup.com/t/17tnw2b2cew
