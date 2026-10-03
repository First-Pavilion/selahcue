# Goal Contract — 17tnw2b2c75-figma-fidelity-audit

## Identity

- Goal ID: 17tnw2b2c75-figma-fidelity-audit
- Parent goal ID: NONE
- Title: Every Figma page and auth/device state for the SelahCue marketing site and account screens has a recorded node id, a rendered counterpart and a classified list of differences, and each non-empty fix list has its own ticket
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2c75
- Created: 2026-10-03
- Updated: 2026-10-03
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Phase 0 only. Produce the evidence needed to make the built marketing site and account screens
match Figma: an audit of 16 pages and 19 states, a repeatable comparison (the visual-parity
harness extended to the marketing `dist/`), a stand-alone side-by-side Artifact, and fix tickets
created from the audit. **No fix is implemented in this goal.**

## Baseline

**Verified** on `origin/main` at `3fb96da8`:

- `implementation/marketing` is a Vue 3 SPA with a view for each of the 16 Figma pages, plus
  `/signup` and `/forgot-password` (no Figma frame), `/verify`, `/reset`, `/admin/*`, `/affiliates/*`.
- There is no `/account/devices` route. `AccountView.vue` is 926 lines, renders from hard-coded
  data, and does not call the API.
- The visual-parity harness (`scripts/vp_*.py`, `docs/design/visual-parity/`) covers the desktop
  operator only: 13 committed references, caps of 32 entries and 24 MB for the whole store.
- No Figma comparison tooling exists for the marketing site.
- ClickUp 17tnw2b0x3h (remove unbacked claims) is `planning/todo`; 17tnw2b0x3g, 17tnw2b0q9g,
  17tnw2b0q9h, 17tnw2b0q9j overlap in time.

## Inputs and evidence sources

- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, page "Marketing Website" `468:124`, section `743:124`
- `docs/design/MARKETING-SITE-HANDOFF.md`, `AUTH-LANDING-PAGES-HANDOFF.md` (section 2.2 token mapping),
  `MARKETING-PORTAL-GAP-FILL-HANDOFF.md`, `docs/delivery/VISUAL-PARITY-HARNESS.md`
- `implementation/marketing` source and built `dist/`; `implementation/api` device schema
- ClickUp 17tnw2b2c75, epic 86ajy5v6k, 17tnw2b0x3h, Build Control 86ajnx548
- Owner-approved plan `~/.claude/plans/pasted-content-id-f317-https-www-figma-zesty-karp.md`

## Scope

### In scope

- Fetch and commit the Figma reference PNG for all 16 pages and 19 states, with node ids
- A `marketing` suite in the visual-parity harness: catalogue, capture from `dist/`, compare, deviations, self-test
- Classify every difference A, B, C, D or E with evidence
- The audit report under `docs/delivery/`, the consolidated C and D lists, the side-by-side Artifact page
- Fix tickets, a Sign Out bug ticket and (if needed) a backend ticket, all in ClickUp
- A Draft PR containing docs and harness changes only

### Non-goals

- Implementing any fix, in any view, component or token file
- `/admin/*`, `/affiliates/dashboard|referrals|payouts|resources|settings|help`, web Sign up, Forgot password
- Mobile and tablet layouts (17tnw2b0q9g); pricing, version and download numbers (17tnw2b0x3h, D1)
- Changing design intent, product scope or API contracts

### Constraints

- Own worktree and branch from `origin/main`; one ticket, one PR; Draft; never merge
- Honest content wins over Figma where the repo does not back a claim (owner decision); layout stays
- Fidelity must not regress accessibility: a Figma colour that fails WCAG AA is kept accessible in code, recorded as class B
- Figma legacy variables versus code `--sc-*` tokens is a deliberate divergence (class B), never a defect
- ClickUp: no Markdown tables (silently dropped); lists only; verify by reading back
- New scripts are bounded (no unbounded caches or logs) and carry a self-test that bites
- Shared checkout is not touched; `git push` uses BatchMode SSH; no attribution trailers on commits

### Assumptions and unknowns

- **Assumed:** Playwright Chromium and WebKit render close enough to the browsers owners use that a Blink and WebKit capture is fair evidence of layout. Neither is a claim about Safari on iOS or real devices.
- **Unknown:** whether Figma's Inter renders with identical metrics to the font the site loads; any residual sub-pixel text drift is recorded rather than chased.
- **Unknown:** whether the owner wants the unframed Bible Entitlements section kept; raised to Uma as class D, not decided here.

## Dependencies and approvals

- Four-reviewer gate (Cody, Vera, Shadow, Quinn) is brokered by the coordinator; not requested from this role
- Owner or Uma decisions needed for class C and D lists; none block the fix tickets

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All 35 Figma references (16 pages, 19 states) are committed with node ids and their checksums verify | `python3 scripts/vp_reference.py --suite marketing verify` | exit 0, 35 entries, 0 problems | command output | PENDING |
| C-002 | yes | The marketing suite captures every catalogued surface from the built `dist/` and compares it to its reference with one command | `python3 scripts/visual_parity.py --suite marketing --engine blink` | exit 0 from capture, report written, 35 pairs, none blank | command output, report | PENDING |
| C-003 | yes | The harness self-test passes and a deliberately wrong input makes each new control fail | `python3 scripts/vp_selftest.py` | exit 0; the new marketing controls each demonstrated in both directions | command output | PENDING |
| C-004 | yes | The audit report lists every page and state with node id and verdict, and every difference carries a class A to E, evidence and a fix or source | `python3 scripts/check_fidelity_audit.py` (structural checker, self-tested) | exit 0; 35 surfaces; 0 unclassified differences | command output, report file | PENDING |
| C-005 | yes | The consolidated class C list and class D list exist for Uma and the owner | read the report sections | both sections present and non-empty or explicitly empty | report file | PENDING |
| C-006 | yes | A side-by-side Artifact opens and shows Figma next to the render for every surface | Artifact publish and read-back | URL returned; page lists 35 surfaces with both images | Artifact URL | PENDING |
| C-007 | yes | One fix ticket exists per non-empty area, each with observable acceptance criteria and links to the audit ticket and the epic | ClickUp read-back of each ticket | lists render (no `undefined`); parent epic set; audit linked | ticket URLs | PENDING |
| C-008 | yes | The Sign Out bug has its own ticket; a backend ticket exists if device endpoints are missing | ClickUp read-back | tickets exist and describe exactly what is missing | ticket URLs | PENDING |
| C-009 | yes | `make marketing-check` and `npm test` pass on the audit branch | run both, capture exit codes (never piped) | both exit 0 | command output | PENDING |
| C-010 | yes | The PR touches docs, scripts and the harness data only; no `implementation/marketing/src` file changed | `git diff --stat origin/main...HEAD` | no path under `implementation/marketing/src` | diff stat | PENDING |
| C-011 | yes | A Draft PR is open against `main` and the branch is not behind it | `gh pr view`; `git rev-list --count HEAD..origin/main` | isDraft true; behind count 0 | PR URL, command output | PENDING |
| C-012 | yes | Build Control 86ajnx548 has a progress note and the audit ticket has the standard handoff comment | ClickUp read-back | both comments present | comment ids | PENDING |
| C-013 | yes | Independent review (code, performance, security, QA) has passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | review report | PENDING |

## Verification plan

- Focused verification: C-001 to C-004 with real exit codes captured to files, never piped
- Broader regression verification: `make marketing-check`, `npm test`, `npm run test:states` is not run here because no `src` file changes; the harness self-test covers the new code
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, Python 3.9 with Pillow 11 and Playwright (Chromium, WebKit), network for Figma MCP only

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: the existing harness can host a second suite with its own catalogue and reference store, capturing the marketing `dist/` through Playwright
- Change or investigation: downloaded all 35 Figma frames at native size (5.8 MB); read `vp_core`, `vp_capture_web`, `vp_compare`
- Verifier executed: pending
- Result: pending
- New evidence: the operator reference store caps at 32 entries, so the 35 marketing references need their own bounded store
- Decision: iterate

## Risks and rollback

- Risks: the reference store grows the repo by about 6 MB of PNG; Figma may change after the export date, so each manifest entry records its export time
- Rollback or recovery: the PR is docs and harness only; revert the merge commit

## Pause and escalation conditions

- Figma MCP unavailable or rate-limited for longer than a few minutes: report `BLOCKED` with the node ids still needed
- ClickUp MCP and REST both unavailable: return `BLOCKED` with a structured pending update
- A finding needs a design or scope decision: record it as a linked follow-up for Uma or the owner, do not decide it

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2c75-figma-fidelity-audit.md --completion`
- Validator result: pending
- Independent verification result: pending (coordinator-brokered)
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
