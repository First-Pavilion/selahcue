# Goal Contract — 17tnw2b2cew-shared-components

## Identity

- Goal ID: 17tnw2b2cew-shared-components
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The five shared marketing components (UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog) match the Figma designs for the 13 class A/E findings the audit assigned to them, so the area tickets only compose them, and no page that uses them regresses
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cew
- Created: 2026-10-03
- Updated: 2026-10-03
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

- The five component files and tests that guard them (a node test, a small component gallery, a headless behaviour script)
- Opt-in props and slots for new looks; accessible, backward-compatible defaults
- Re-running the harness on the surfaces that use these components

### Non-goals

- Any view, page layout or copy (area tickets); Navbar, Footer, UiButton, tokens.css, main.css, App.vue, router (the chrome ticket 17tnw2b2cev, parallel)
- Choosing the accessible brand ink or the accessible destructive-button ink (class D, Uma: account-25, home-44, pricing-21, account-31)
- Removing the unbacked annual-discount maths in `PricingCard` (class C, owner decision, 17tnw2b0x3h)
- Editing the audit report or audit data

### Constraints

- Stacked branch: cut from the audit branch, Draft PR with `--base web/17tnw2b2c75-figma-fidelity-audit`; must be retargeted to `main` and rebased after #171 merges; never merged by this role
- Footprint: the five components and tests. Anything else is stopped and reported. New files limited to this contract, `tests/sharedComponents.test.ts`, `tests/gallery/*`, `scripts/shared_components_headless.py`
- Owner decisions: honest content wins over Figma; fidelity must not regress accessibility (a Figma colour that fails AA stays accessible, recorded as B, flagged to Uma); Figma legacy variables versus `--sc-*` is a deliberate layer
- No new token in `tokens.css`; any colour that Uma must choose is one overridable custom property inside UiBadge, defaulting to today's rendering
- Existing props and defaults stay backward compatible; no unbounded state; `git push` with BatchMode SSH; no attribution trailers

### Assumptions and unknowns

- **Assumed:** `text` on UiBadge is a mistake in `PricingView` (the badge has never rendered it); rendering it would newly show the unbacked "Save 20%" claim (pricing-18, class C), so UiBadge does not render it and warns in development instead. The slot is the one content API.
- **Assumed:** the area tickets switch Home's six section labels to `variant="eyebrow"` and pass `to` to PricingCard; until then those render as chips and disabled-with-note CTAs.
- **Unknown (Uma):** the accessible brand ink and destructive-button ink; flagged, not chosen.
- **Unknown:** whether the owner wants `scripts/shared_components_headless.py` wired into `package.json` (outside this footprint).

## Dependencies and approvals

- Chrome ticket 17tnw2b2cev (Farah 1a) runs in parallel on other files; no shared file
- Four-reviewer gate brokered by the coordinator, not requested by this role

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | UiBadge defines accent, warn and eyebrow besides the six it had; every variant a view passes is defined; a test fails when a view passes an undefined variant | `node --test tests/sharedComponents.test.ts` | exit 0; the real-tree check passes and its positive control fails on a planted bad variant | test output | PENDING |
| C-002 | yes | The page eyebrow pill (`featured`) is 12px/700, 0.1em, 6px 12px, elevated fill; its ink is one overridable custom property | gallery computed styles via `scripts/shared_components_headless.py` | computed values equal Figma; setting the property changes featured, accent and eyebrow ink | script output | PENDING |
| C-003 | yes | FormField has a `label-action` slot (DOM order kept), a text Show/Hide reveal option and a visible ✕ error option; default markup and computed styles of every existing form are unchanged | node SSR golden of default markup; gallery computed-style baseline vs after | identical default output; tab order Email, Password, Forgot | test output; baseline JSON | PENDING |
| C-004 | yes | FaqAccordion answers have id, `role=region`, `aria-labelledby`; buttons have `aria-controls` and `aria-expanded`; collapsed answers are out of the accessibility tree; a boxed option matches the Affiliates frame | node SSR test; headless accessibility snapshot and computed style | attributes present; collapsed answer absent from the snapshot; boxed card 880px, r16, 18px 22px | test and script output | PENDING |
| C-005 | yes | PricingCard takes a destination (link) or renders an honest disabled CTA, never a dead button; lays out as Figma (top aligned, r18, 2px primary border on the popular plan, CTA above the divider, SVG ticks) | node AST and SSR test; gallery geometry | no enabled button without an action; geometry equals Figma boxes | test output | PENDING |
| C-006 | yes | ConfirmDialog is extended, not forked: 420px, banner slot, hint, cancel initial focus, red confirm, focus trapped and restored, Escape cancels, aria-labelledby and describedby; the default dialogs look and behave as before | node SSR test; headless focus script; responsive sweep overlay check | all assertions pass | script output | PENDING |
| C-007 | yes | Every consumer still renders and behaves: Home, Pricing, Account, Admin, Affiliates, Contact, Sign up, Sign in, Forgot, Verify, Reset | `npm run test:states` (SELAHCUE_HEADLESS_REQUIRE=1), `npm run test:responsive` | exit 0 | logs | PENDING |
| C-008 | yes | Harness re-run: each of the 13 findings is shown closed at the component (or its remaining line is named with the area ticket that adopts it); nothing regressed | `visual_parity.py --suite marketing --engine both` and `vp_style_diff.py` per slug, compared with the baseline | exit 0; diff of line sets saved | run directory and diff files | PENDING |
| C-009 | yes | `make marketing-check`, `npm test`, `vp_selftest.py` and `check_fidelity_audit.py --self-test` pass | run each, capture exit codes unpiped | all exit 0 | logs | PENDING |
| C-010 | yes | Contrast of every changed foreground/background pair is AA or recorded as B/D; no horizontal page scroll at 375, 768, 1440 | contrast table from `vp_core`; responsive sweep | no new failing pair; sweep reports none | table; sweep log | PENDING |
| C-011 | yes | The diff touches only the footprint plus this contract, the node test, the gallery and the headless script | `git diff --name-only origin/web/17tnw2b2c75-figma-fidelity-audit` | only those paths | diff list | PENDING |
| C-012 | yes | ClickUp has a start comment and a handoff comment with QA steps as a list, read back | ClickUp read-back | both present, lists intact | comment ids | PENDING |
| C-013 | yes | A Draft PR is open with base `web/17tnw2b2c75-figma-fidelity-audit`, the description says it is stacked, and the branch is not behind its base | `gh pr view`; `git rev-list --count HEAD..origin/web/17tnw2b2c75-figma-fidelity-audit` | isDraft true; base correct; behind 0 | PR URL | PENDING |
| C-014 | yes | Independent review (code, performance, security, QA) passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | not requested by this role | PENDING |

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

## Risks and rollback

- Risks: a badge scale change touches every page with a badge; the default FormField must stay pixel-identical; merging before the area tickets leaves Home section labels as chips and PricingCard CTAs disabled
- Rollback or recovery: revert the PR; every new look is opt-in except UiBadge geometry and the FaqAccordion accessibility attributes

## Pause and escalation conditions

- A fix needs a file outside the footprint: stop and report to the coordinator
- A fix needs a token that is not in `tokens.css`: stop and report to the chrome ticket owner
- An ink or destructive-button colour that only Uma can choose: keep the accessible value, flag it

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cew-shared-components.md --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
