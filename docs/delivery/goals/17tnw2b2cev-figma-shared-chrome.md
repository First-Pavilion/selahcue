# Goal Contract — 17tnw2b2cev-figma-shared-chrome

## Identity

- Goal ID: 17tnw2b2cev-figma-shared-chrome
- Parent goal ID: 17tnw2b2c75-figma-fidelity-audit
- Title: The marketing site's shared chrome (navbar, footer, UiButton, design tokens, app shell) matches the Figma chrome that every page frame shares, without regressing accessibility, and the harness shows each class A finding of this ticket closed
- Role: frontend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2cev
- Created: 2026-10-03
- Updated: 2026-10-03
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Implement the 26 class A findings that the Figma fidelity audit (ClickUp 17tnw2b2c75, Draft PR 171)
assigned to shared chrome. The navbar, footer, `UiButton`, `tokens.css`, the global rules in `main.css`,
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

Plus two test-gate edits that follow directly from the requested change and are made in a separate commit
(see Assumptions): the 68px navbar height and four-column footer assertions in `scripts/responsive_sweep.py`.

### Non-goals

- Home steps section id (`id="how-it-works"` is the Home ticket's); UiBadge, FormField, FaqAccordion, PricingCard, ConfirmDialog (17tnw2b2cew, a parallel instance)
- Any view's content, mobile and tablet layouts (17tnw2b0q9g), the 404 view's nested main (17tnw2b0x3h)
- Class C and D decisions: `account-25`, `shared-chrome-11`, `-12`, `-13`, `-19`, `-31`, `-33`
- The audit report and the audit data under `docs/design/visual-parity/marketing/`

### Constraints

- Own worktree and branch; one ticket, one Draft PR, never merged by this role; the PR is stacked on the audit branch
- Honest content wins: the footer tagline and legal line keep their current wording (decision 19 is pending)
- Accessibility must not regress; a Figma colour below AA stays accessible in code
- No new hover colour, no new brand ink: both are decisions held for Uma
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
| C-001 | yes | At 1440 the navbar is 79px tall, runs at 48px gutters, the mark is visibly 32px, the active route is Semi Bold in the primary text colour, Sign in is the primary text colour with an 18px gap, Download free is a 10px rectangle at weight 700 (shared-chrome-01 to 06) | harness run plus `vp_style_diff.py` on home, pricing, features, about | no printed line for the nav texts or the nav CTA box | style-diff output in the scratchpad and the run path | PENDING |
| C-002 | yes | Nav How it works is a router link to the Home route with the hash and Home scrolls it clear of the sticky bar (shared-chrome-07) | `node --test tests/scroll.test.ts tests/chrome.test.ts` and a browser run with the id stubbed | tests pass; stubbed target lands below the 79px bar | test output; browser measurement | PENDING |
| C-003 | yes | The footer has Figma's three columns and bottom bar with exactly the listed entries; Privacy and Terms are in the bottom bar; every footer link resolves to a real route (shared-chrome-14, 15) | `node --test tests/chrome.test.ts` (walks footer links against the router table) | exit 0; a missing target fails the test | test output | PENDING |
| C-004 | yes | Footer layout and type match (3 hugging columns at 96px gutters, 56px top padding, 30px link pitch, muted 12px uppercase headings over bright links, page-colour fill) (shared-chrome-16, 17, 18) | harness DOM and `vp_style_diff.py` on the footer | no printed footer line for these findings | style-diff output | PENDING |
| C-005 | yes | Footer copyright, the route-loading fallback and every small text in nav and footer measure at least 4.5:1; the harness contrast survey lists no failing nav or footer text on any page (shared-chrome-20, 21, 34, pricing-25) | harness contrast survey in `report.json` for all captured pages; a unit test pins the token ratios | survey lists no nav, footer or loading entry; token ratio at least 4.5 on every surface | report.json filter output; test output | PENDING |
| C-006 | yes | UiButton renders radius 10 (compact, sm) and 11 (md, lg), fixed heights 39, 41, 44, 47, 49 independent of the parent line-height, variants primary, secondary (bordered), ghost, outline, inverse and inverse-outline, and a focus ring that shows in forced-colors mode (shared-chrome-27 to 30) | `node --test tests/uiButton.test.ts` and a browser measurement in a parent with a hostile line-height | tests pass; measured heights equal the table | test output; browser measurement | PENDING |
| C-007 | yes | One 1248px content-width token with 96, 48 and 20px gutters and one shared container exist; section padding is 88px; `--sc-surface-alt` and `--sc-success` are defined; a test fails if a `var(--x)` used in `src/` has no definition (shared-chrome-22, 23, 24, 25, pricing-25) | `node --test tests/tokens.test.ts` (and a mutation: an undefined var makes it fail) | exit 0; the mutation turns it red | test output | PENDING |
| C-008 | yes | Desktop nav links, brand and CTA show a visible focus-visible ring and the nav surface uses tokens, not the hard-coded dark band (shared-chrome-08, 09) | `node --test tests/chrome.test.ts` and a browser keyboard pass | tests pass; ring present on each control; computed header background equals the base token | test output; browser measurement | PENDING |
| C-009 | yes | After `npm run build`, `visual_parity.py --suite marketing --only home pricing features` exits 0 and `vp_style_diff.py` prints no line belonging to a class A finding of this ticket; the full suite on both engines shows no regression on any surface | `python3 scripts/visual_parity.py --suite marketing --engine both` and `vp_style_diff.py` per slug, before and after | exit 0; remaining chrome lines are documented class B, C or D | run directory, before and after diff summary | PENDING |
| C-010 | yes | `make marketing-check`, `npm test`, `npm run test:states` and `npm run test:responsive` pass (headless required) | each command with its exit code captured to a file, never piped | all exit 0 | exit codes and counts | PENDING |
| C-011 | yes | No horizontal page scroll at 375, 768 and 1440 on the changed pages and the mobile nav sheet and 44px touch targets still pass | `npm run test:responsive` and real renders | sweep reports none; renders checked | sweep output; screenshots | PENDING |
| C-012 | yes | The PR touches only this ticket's footprint plus the two named gate edits; shared files owned by other tickets are untouched | `git diff --name-only origin/web/17tnw2b2c75-figma-fidelity-audit` | every path is in the footprint or the named gate script | the file list | PENDING |
| C-013 | yes | A Draft PR is open against the audit branch, stacked and labelled as such, and the branch is not behind the audit branch | `gh pr view` and `git rev-list --count HEAD..origin/web/17tnw2b2c75-figma-fidelity-audit` | isDraft true; base is the audit branch; behind count 0 | PR URL; command output | PENDING |
| C-014 | yes | ClickUp 17tnw2b2cev is in progress with a start comment and carries the handoff comment with QA steps as a list | ClickUp read-back | both comments present, no dropped table | comment ids | PENDING |
| C-015 | yes | Independent review (code, performance, security, QA) has passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | not requested by this role | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: new node tests first (red, then green); browser measurement of each changed control; harness style diff and contrast survey before and after
- Broader regression verification: `make marketing-check`, `npm test`, `npm run test:states`, `npm run test:responsive`, `vp_selftest.py`, `check_fidelity_audit.py --self-test`, the harness on all captured surfaces under Blink and WebKit
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, `/usr/bin/python3` with Pillow and Playwright (Chromium, WebKit), headless Chrome, network for the Inter font. Rust, Flutter and API are untouched, so `make ci` is not required.

## Iteration ledger

### Iteration 1

- Target criterion: baseline and C-007
- Hypothesis: a token guard test that scans for undefined custom properties fails today for `--sc-surface-alt` and `--sc-success`
- Change or investigation: baseline gates and harness run captured; worktree cut from the audit branch
- Verifier executed: `make marketing-check` (exit 0), harness run `.visual-parity/run-20261003-212326`
- Result: baseline green; every gate that encodes the old design identified
- New evidence: `responsive_sweep.py` asserts a 68px bar and four footer columns
- Decision: iterate

## Risks and rollback

- Risks: the chrome is on every page, so a layout regression is site-wide; the shared `.container` and section tokens move page rhythm for pages that consume them; raising the muted ink changes every consumer by a few percent luminance
- Rollback or recovery: the PR is confined to the chrome files; revert the merge commit. Tokens added are additive except `--section-padding` (no consumers) and the raised `--sc-text-muted`.

## Pause and escalation conditions

- A fix needs a file outside the footprint beyond the named gate edits: stop and report to the coordinator
- A finding turns out to need a design or scope decision: leave it as the audit records it and report it for Uma or the owner
- The harness cannot run (Pillow, Playwright or network): report BLOCKED with the exact missing piece

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2cev-figma-shared-chrome.md --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
