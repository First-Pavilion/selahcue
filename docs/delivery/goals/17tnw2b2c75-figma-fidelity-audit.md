# Goal Contract — 17tnw2b2c75-figma-fidelity-audit

## Identity

- Goal ID: 17tnw2b2c75-figma-fidelity-audit
- Parent goal ID: NONE
- Title: Every Figma page and auth/device state for the SelahCue marketing site and account screens has a recorded node id, a rendered counterpart and a classified list of differences, and each non-empty fix list has its own ticket
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2c75
- Created: 2026-10-03
- Updated: 2026-10-04
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
- The owner's decisions for this work are quoted in full under Constraints below (the approved plan lives outside the repo, so nothing here depends on it)

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

Owner decisions, quoted (binding; they are the owner's words as given to this role, repeated here so the contract stands on its own):

- Scope: "audit and fix straight through". Phase 0 (this contract) is the audit and the fix tickets; each fix is its own later ticket with no owner pause between the phases.
- Honest content wins: "Where Figma shows content the repo does not back (Pro `$19/month` and \"Annual · save 20%\", named testimonials, `v1.0 · ~84 MB / ~92 MB` installers, \"Sub-3-second cold start\", FAQ answers marked Assumed, \"NDI 5\"/1080p60 style claims, support/privacy email addresses, etc.): HONEST CONTENT WINS. Keep Figma's layout and styling, do not ship the invented claim, list it for Uma/owner." Removal of such claims from the live pages belongs to ClickUp 17tnw2b0x3h, which is linked, not duplicated.
- Accessibility: "Fidelity must not regress accessibility: if a Figma colour fails WCAG AA, keep the accessible ink in code, record it as class B and flag it to Uma."
- Tokens: Figma's legacy colour variables against the code's `--sc-*` tokens are a deliberate divergence (AUTH-LANDING-PAGES-HANDOFF section 2.2), never reported as a defect.
- Platforms (product, 2026-10-04): "SelahCue is available for Windows, Linux and macOS." So the footer's "Windows · macOS" (drawn in Figma) stays as drawn. Linux is drawn nowhere (footer, Download cards, Home FAQ) and Figma's FAQ says "Linux is on the roadmap"; that is a class D item for Uma (`shared-chrome-35`), and nobody adds Linux to a page until it is drawn. Two sentences in the live copy say "There is no macOS or Linux installer yet" (`implementation/marketing/src/lib/content/support.ts:108` and `docs.ts:317`): recorded as class C for the owner (`support-11`, `docs-09`), not as code bugs. The Download page's macOS card says "macOS 11.0 or later" where Figma says "macOS 12 Monterey+" (already audited as `download-04`). Until the owner answers the open question below, no page may claim a downloadable macOS or Linux installer, and the Download buttons stay disabled (PR #134).
- Not in scope: `/admin/*`; `/affiliates/dashboard|referrals|payouts|resources|settings|help`; web Sign up and Forgot password (no Figma frames); mobile and tablet layouts (ClickUp 17tnw2b0q9g); pricing, version and download numbers (17tnw2b0x3h and pricing decision D1).

Working constraints:

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
- **Unknown, asked of the owner (decisions ticket 17tnw2b2cf3):** whether "available for Windows, Linux and macOS" means a downloadable installer exists today on each platform, or that the app supports all three while only the Windows installer is packaged. For: PRD G-2 (`docs/product/prds/SelahCue-PRD.md:33`), and CI builds and tests on all three. Against: the Tauri bundle target is only `nsis` and the installer workflow uploads only the Windows setup. Not decided here.

## Dependencies and approvals

- Four-reviewer gate (Cody, Vera, Shadow, Quinn) is brokered by the coordinator; not requested from this role
- Review round 1 (head `0990433e`), all on PR #171: Shadow https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5973660650 (clear); Cody https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5973711731 (1 blocking, 10 non-blocking); Vera https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5973802193 (1 blocking, 8 non-blocking); Quinn https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5973849595 (clear). The four reports on one page, team-only like the audit page: https://claude.ai/artifact/WRHJ1V3GJdfbRLDuLctcse (PR comment https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5973889070). Remediation is on the branch. Re-check at head `1b70306d`: Cody https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5977732714 (his blocking finding is clear; one new non-blocking finding, N1) and Vera https://github.com/First-Pavilion/selahcue/pull/171#issuecomment-5977774823 (B1 is clear; two new low findings, R2-1 and R2-2); both were fixed afterwards (Iteration 5). The review gate itself is brokered by the orchestrator
- Owner or Uma decisions needed for class C and D lists; none block the fix tickets

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All 35 Figma references (16 pages, 19 states) are committed with node ids, and their checksums and style dumps verify | `python3 scripts/vp_reference.py --suite marketing verify` | exit 0, 35 entries, 0 problems | `=== reference store [marketing]: 35/48 entries, 6335237/12582912 bytes, 0 problem(s) ===`, exit 0 | PASS |
| C-002 | yes | The marketing suite captures every catalogued surface from the built `dist/` and compares it to its reference with one command | `python3 scripts/visual_parity.py --suite marketing` | exit 0 from capture and compare; 29 captured pairs compared, 6 unbuilt probes confirmed, none blank, run under the 300-file cap | exit 0 on the final run (35 records, 0 failures); 91 files (Blink), 172 files with `--engine both` (exit 0, 62 records); report.html and report.md written | PASS |
| C-003 | yes | The harness self-test passes, and each new control fails when fed a deliberately wrong input | `python3 scripts/vp_selftest.py` | exit 0; 45 operator controls unchanged plus the marketing controls, each shown failing as well as passing | `=== visual-parity selftest: 206 checks, 0 FAIL ===`, exit 0. Every cap, the banding, every fail-closed gate and wiring path is mutation-proved: `python3 scripts/vp_mutation_proof.py` applies each of 75 listed edits (`docs/design/visual-parity/marketing/mutations.json`) to a scratch copy of real copies (no symlinks) and requires a self-test to go red; a hang counts as not proved and the unmutated baseline must pass first: 75 of 75 red (248 s), real checkout untouched, exit 0; its own `--self-check` exit 0. Ctrl-C proved by hand on a real capture, before and after the fix (harness doc, section 11) | PASS |
| C-004 | yes | The audit data lists every page and state with node id and verdict, and every difference carries a class A to E, evidence and a fix or source | `python3 scripts/check_fidelity_audit.py --require-tickets` (self-tested: `--self-test`) | exit 0; 35 surfaces plus shared chrome; 0 problems | exit 0, 0 problems, 298 findings counted (182 A, 27 B, 47 C, 34 D, 8 E; the 2 owned by 17tnw2b0x3h are in these totals and only left out of the severity tally); 32 duplicates set aside; `--check-report` exit 0 (the committed report matches the data); self-test 97 checks, 0 FAIL; passes in a `--depth 1` clone and still rejects a made-up commit in a full clone | PASS |
| C-005 | yes | The consolidated class C list and class D list exist for Uma and the owner | read the report sections and the decisions ticket | both sections present and non-empty | `docs/delivery/FIGMA-FIDELITY-AUDIT-marketing-account-2026-10-03.md` (C: 47, D: 34, plus the owner's open question about macOS and Linux installers and the form-field decision); ClickUp 17tnw2b2cf3 read back | PASS |
| C-006 | yes | A side-by-side Artifact opens for a member of the team who was not in the session (team-only sharing, decided by the owner 2026-10-04; an anonymous request returning 403 is the intended state) and shows Figma next to the render for every surface | Artifact publish and file listing; local render at 1280 and 400 wide; a team member opens the URL after the owner sets sharing | URL returned; 36 cards (35 surfaces plus shared chrome); and a team member who was not in the session opens it | https://claude.ai/artifact/5s6P3eHuirLfQXLMKTTAha (version 3, 65 files, 36 cards, no horizontal scroll at 1280 and 400 wide, all 64 images load once a card is opened). Sharing is private to the author today. **OWNER ACTION OPEN: the owner sets sharing to the team (organisation members) from the Artifact's Share menu; the author cannot do it. After that, a team member opens the page and this row can move to PASS.** No public build exists or is wanted; the page keeps its evidence, API-gap and bug sections (security review finding 2: RESOLVED BY DECISION, team-only sharing). | PENDING |
| C-007 | yes | One fix ticket exists per non-empty area, each with observable acceptance criteria and links to the audit ticket and the epic | ClickUp read-back of each ticket | lists render (no dropped table); parent epic set; audit linked; dependencies set | 17tnw2b2cev, cew, cex, cey, cez, cf1, cf2 created through the REST API: parent 86ajy5v6k, checkbox lists present on read-back (chrome, home, account, decisions, backend checked), linked to the audit; area tickets depend on chrome and components | PASS |
| C-008 | yes | The Sign Out bug has its own ticket; a backend ticket exists if device endpoints are missing | ClickUp read-back | tickets exist and describe exactly what is missing | Sign Out bug 17tnw2b2cbr (verified in `AccountView.vue:136`); backend 17tnw2b2cf4 (10 API gaps: 7 missing, 3 partial) | PASS |
| C-009 | yes | `make marketing-check` and `npm test` pass on the audit branch | run both, capture exit codes (never piped) | both exit 0 | `make marketing-check` exit 0; `npm test` exit 0, 612 pass, 0 fail | PASS |
| C-010 | yes | The PR touches docs, scripts and the harness data only; no `implementation/` file changed | `git diff --name-only origin/main` | no path under `implementation/` | 0 paths under `implementation/`; every path is under `scripts/`, `docs/design/visual-parity/` or `docs/delivery/` | PASS |
| C-011 | yes | A Draft PR is open against `main` and the branch is not behind it | `gh pr view 171 --json isDraft,baseRefName`; `git rev-list --count HEAD..origin/main` | isDraft true; behind count 0 | `gh pr view 171`: isDraft true, base `main`; `git rev-list --count HEAD..origin/main` printed 0 at the head of the fix pass (the head SHA and this check are quoted in the PR's fix-status comment) | PASS |
| C-012 | yes | Build Control 86ajnx548 has a progress note and the audit ticket has the standard handoff comment | ClickUp read-back | both comments present | BUILD CONTROL comment 1400430000059184; audit handoff comment 1400430000059177 | PASS |
| C-013 | yes | Independent review (code, performance, security, QA) has passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn brokered by the coordinator | all four report; no open blocking finding | review round 1 done (the four reports are linked under Dependencies). Round 1 at `0990433e`: Shadow clear, Quinn clear, Cody 1 blocking, Vera 1 blocking. Re-check at `1b70306d` by the same reviewers: Cody's blocking finding (C-006 wording) clear, PR comment 5977732714; Vera's blocking finding (caps untested) clear, PR comment 5977774823. Their three small non-blocking re-check findings were then fixed at `b37d9ea5` and are not re-reviewed by them. The orchestrator verified at `c9e25e30`: history is linear on top of `0990433e`, nothing under `implementation/` changed, the PR body is intact, and a `--depth 1` clone passes `--check-report` and the 97-check self-test. Closed by the orchestrator 2026-10-04; not requested by this role | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001 to C-004 with real exit codes captured to files, never piped
- Broader regression verification: `make marketing-check`, `npm test`, `npm run test:states` is not run here because no `src` file changes; the harness self-test covers the new code
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+, Python 3.9 with Pillow 11 and Playwright (Chromium, WebKit), network for Figma MCP only

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: the existing harness can host a second suite with its own catalogue and reference store, capturing the marketing `dist/` through Playwright
- Change or investigation: downloaded all 35 Figma frames at native size (5.8 MB); read `vp_core`, `vp_capture_web`, `vp_compare`; added suites, a marketing capture, top-aligned compare, a bundle probe and deviation metrics
- Verifier executed: `vp_reference.py --suite marketing verify`, `visual_parity.py --suite marketing`
- Result: 35 references ingested; the first run captured 35 surfaces but drew V1 as its own failure state (waiting for `networkidle` sat out the app's 15s timeout), and a source probe fired on a code comment
- New evidence: the operator store caps at 32 entries so marketing needs its own bounded store; a held request must be waited on with `load`; the probe must read the shipped bundle, not source
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-004
- Hypothesis: comparing values, not just pixels, needs the Figma side as data and a program to diff it against computed styles
- Change or investigation: a read-only Figma style extractor, `vp_style_diff.py`, style dumps registered in the bounded store, the findings schema and checker; seven parallel read-only auditors produced the findings
- Verifier executed: `vp_selftest.py` (112 checks), `check_fidelity_audit.py --self-test` (34 checks), spot checks of agent claims against source
- Result: 0 FAIL; spot checks of the dead nav anchor, the `/how-it-works` footer link, pricing buttons with no action, UiBadge variants, nav height and DEC-008 all agreed with the findings
- New evidence: area tickets cannot avoid shared files, so a shared-components ticket was added beside shared chrome; 31 findings are duplicates and 2 are owned by 17tnw2b0x3h
- Decision: iterate

### Iteration 3

- Target criterion: C-006 to C-012
- Hypothesis: the tickets, artifact, PR and ClickUp notes can be generated from the audit data so they cannot disagree with it
- Change or investigation: generated the report, the ticket bodies and the artifact page from the data; created nine tickets through the REST helper; ran every verifier fresh
- Verifier executed: see the predicate table
- Result: all PASS except C-006 (the Artifact's sharing is team-only by the owner's decision and still has to be set from the Share menu) and C-013 (independent review, brokered by the coordinator)
- New evidence: a Homebrew `python3` earlier on PATH has no Pillow, and the verifiers pass with `/usr/bin/python3`; a count first written in a ClickUp comment (33 diverging surfaces) was wrong (27) and was corrected from the data
- Decision: gate-review

### Iteration 4 (review round 1 remediation, 2026-10-04)

- Target criterion: C-003, C-004, C-006, C-013 (and the findings of the four reviewers)
- Hypothesis: every cap needs a test that fails when the cap is removed, the checker must read meaning and not just shape, and the report must be unable to drift from the data
- Change or investigation: fixed the two caps that did not hold (`vp_slice`, the bundle probe); a test per cap and per gate, proved by mutation (62 edits, repeatable with `vp_mutation_proof.py`); a semantic checker with `--check-report`; fail-closed deviation gate; corrected findings and the report wording; Ctrl-C proved by hand; follow-up ticket for `make ci` raised, not wired here; product's platform statement recorded
- Verifier executed: every command in the predicate table again, with exit codes captured to files
- Result: all green; C-006 stays PENDING on the owner's sharing step, C-013 on the orchestrator's re-check
- New evidence: a vacuous test can only be found by breaking the thing it guards (five mutations survived their first test, four early and one in the final list, and each was fixed); two controls were vacuous until a non-vacuity assertion was added
- Decision: gate-review

### Iteration 5 (re-check follow-ups, 2026-10-04)

- Target criterion: C-003, C-004 (the re-checkers' non-blocking findings)
- Hypothesis: the new checks must not depend on this repository's history (CI checks out `--depth 1`), the memory saving needs a control of its own, and the mutation proof's safety claim must be true
- Change or investigation: commit existence is "cannot tell" in a shallow clone and the two controls run on a scratch repository; a control that counts the bands of every banded step, and the comparison cost quoted by the pixel budget replaced by a measured fit (peak = 234 MB + 12.2 MB per Mpx); the mutation proof now uses real copies, fails on a hang or an unmutated baseline that is not green, and checks the real checkout is unchanged; the follow-up ticket 17tnw2b2fum says shallow clones must pass and recommends `fetch-depth: 0`
- Verifier executed: every command in the predicate table again, plus a `--depth 1` clone and a full clone of the head, with exit codes captured to files
- Result: all green; 13 new mutations (75 in all), each red
- New evidence: a symlink writes through, so the earlier "nothing real can be written" was a claim without a guarantee; the memory saving was invisible to every test until the band count was asserted
- Decision: gate-review

## Risks and rollback

- Risks: the reference store grows the repo by about 6 MB of PNG; Figma may change after the export date, so each manifest entry records its export time
- Rollback or recovery: the PR is docs and harness only; revert the merge commit

## Pause and escalation conditions

- Figma MCP unavailable or rate-limited for longer than a few minutes: report `BLOCKED` with the node ids still needed
- ClickUp MCP and REST both unavailable: return `BLOCKED` with a structured pending update
- A finding needs a design or scope decision: record it as a linked follow-up for Uma or the owner, do not decide it

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2c75-figma-fidelity-audit.md --completion`
- Validator result: the structural check passes; the completion check fails on C-006 only (the owner must set team-only sharing, then a team member opens the page)
- Independent verification result: round 1 done (Shadow clear, Quinn clear, Cody and Vera one blocking finding each, remediated); re-check at `1b70306d`: Cody and Vera report their blocking findings clear (PR comments 5977732714 and 5977774823) with three small non-blocking findings, fixed at `b37d9ea5`; the review gate (C-013) was closed by the orchestrator on 2026-10-04
- Terminal state: GATE_REVIEW (all verifiable work done and independently reviewed; the owner's sharing step for C-006 is open)
- Remaining failed or blocked criteria: C-006
- ClickUp final evidence comment: 1400430000059177 on https://app.clickup.com/t/17tnw2b2c75
