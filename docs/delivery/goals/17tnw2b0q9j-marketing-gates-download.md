# Goal Contract — 17tnw2b0q9j-marketing-gates-download

## Identity

- Goal ID: 17tnw2b0q9j-marketing-gates-download
- Parent goal ID: NONE
- Title: `make ci` and the CI `marketing (vue spa)` job run the same type-check, lint, test and build gate for `implementation/marketing`, and `/download` has no control that looks clickable but does nothing
- Role: frontend-engineer
- Status: IN_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0q9j
- Created: 2026-10-01
- Updated: 2026-10-01
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A type error or a lint error in `implementation/marketing` fails `make ci` and the CI `marketing`
job, both through one shared Makefile target. The Download page shows honest disabled states in
place of its fake store badges and fake download buttons. The Vite-template README is replaced.

## Baseline

**Verified** on `origin/main` at `b73d389`:

- `package.json` had no `type-check` or `lint` script. `build` was `vue-tsc -b && vite build`.
- `make ci` ran nothing for `implementation/marketing`. The root `CLAUDE.md` and the Makefile header both said so.
- The CI `marketing (vue spa)` job ran `npm ci`, `npm run build`, `npm test`, then the Django-backed mirrors and the headless states, as separate steps listed in the workflow only.
- `DownloadView.vue` rendered `App Store` and `Google Play` as black `<div class="badge-placeholder">` boxes, and two `UiButton`s with no `to`, `href` or handler, over the text `Version 1.2.0 (Stable)`.
- `README.md` was the unedited Vite template.
- Real status: the downloads backend is `planning/todo` and both endpoints return 501 (ClickUp 86ak10afm). Mobile store publishing is `planning/todo` (86ajxz3nj) and every item in `docs/release/mobile/RELEASE-CHECKLIST.md` for iOS and Android is unticked. The desktop crate version is `0.1.0`, not `1.2.0`.

## Inputs and evidence sources

- ClickUp 17tnw2b0q9j (task body, acceptance criteria), 86ak5rjh7 (wider gap, marketing half only), 86ak10afm (downloads backend), 86ajxz3nj (store publishing)
- Root `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml` (`marketing` job and path filter)
- `docs/release/mobile/RELEASE-CHECKLIST.md`, `docs/architecture/adr/ADR-0012-packaging-updates.md`
- `implementation/marketing/package.json`, `src/views/DownloadView.vue`, `src/components/UiButton.vue`, `src/router/index.ts`

## Scope

### In scope

- `type-check` and `lint` npm scripts; ESLint as dev-only dependencies; fix what lint finds
- A `marketing-check` Makefile target wired into `make ci`; the CI marketing job calls the same target
- Disabled coming-soon states on `/download` (store badges, and the two desktop download buttons)
- A real README; a minimal accurate `CLAUDE.md` edit

### Non-goals

- Wiring the Download buttons to the downloads backend (blocked on 86ak10afm)
- The Django API gate, billing, the downloads backend
- Type-checking `tests/` and `scripts/*.ts` (found failing today; recorded as a known gap)
- Formatting or style lint rules (about 1,300 existing sites; no formatter exists)
- Responsive layout work (separate agent and ticket)

### Constraints

- Own worktree and branch cut from `origin/main`; one ticket, one PR; Draft; do not merge
- Dependency change is not verified by tests: run the guard scripts and explain every lockfile line
- No `make ci` run concurrently with another session's Flutter run
- Keep CSS additions local to the Download section; another agent is editing `<style>` blocks across views

### Assumptions and unknowns

- **Verified:** `make ci` reaches the marketing line before any Rust or Flutter step, so the deliberate-failure proof does not start a Flutter run.
- **Verified (was unknown):** a step-level `working-directory: .` resolves to the workspace root. The `marketing (vue spa)` job passed every step, including `Type-check, lint, test, build (make marketing-check)`, `Client/server mirrors` and `Auth page states (headless)`, on ubuntu-latest with Node 22, in CI run 36815337410 (https://github.com/First-Pavilion/selahcue/actions/runs/36815337410), which completed successfully (every job) on commit `3a7d338`. That is the only citation this file makes, on purpose: `ci.yml` cancels a PR's in-progress run whenever a newer commit is pushed (`cancel-in-progress` for `pull_request`), so any run id written into a commit on this branch is for a commit that is no longer the head and may itself end up cancelled. An earlier version of this contract cited run 36815083374, which was cancelled exactly that way and proves nothing. The result for the current head is recorded where editing it triggers no new run: the PR description (PR #134), section "Evidence", and the PR's checks.
- **Unknown:** whether the Dockerfile's Node 20 builds the site with the new `build` script. Only `type-check` and `vite build` run in the image, both unchanged in substance; not run in a container here.

## Dependencies and approvals

- Four-reviewer gate (Cody, Vera, Shadow, Quinn) before `VERIFIED_COMPLETE`; dispatched by the coordinator
- Owner decision to disable the Windows/macOS buttons as well as the store badges (see C-006); easy to drop, it is its own commit

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `make marketing-check` exits non-zero on a deliberate type error and zero once reverted | add `export const x: number = 'a'` to `src/lib/auth/countries.ts`, run `make marketing-check`, `git checkout` the file, run again | exit 2 with `error TS2322`, then exit 0 | PR description, "Deliberate-failure proof" | PASS |
| C-002 | yes | The same target exits non-zero on a deliberate lint error, in a `.ts` file and in a `.vue` template, and on a lint warning | `any` in a `.ts`; `v-for` without `:key` in `AboutView.vue`; an unused `eslint-disable` directive through `npm run lint` | exit 2 naming `no-explicit-any`; exit 2 naming `vue/require-v-for-key`; exit 1 for the warning | PR description | PASS |
| C-003 | yes | `make ci` fails on a marketing error | deliberate type error, then `make ci` | exit 2, stopping at `make[1]: *** [marketing-check] Error 2` | PR description | PASS |
| C-004 | yes | The CI job and the local gate run the same commands | read `.github/workflows/ci.yml`; `make -n ci`; `actionlint` | the job's step is `make marketing-check`; `make -n ci` lists `marketing-check`; actionlint exits 0 | `git diff`, command output | PASS |
| C-005 | yes | The lockfile change is additive, dev-only, and every line is explained; guards pass | structural diff of the two lockfiles; `npm audit`; `sh scripts/import_guards.sh`; clean `npm ci` | 76 to 176 packages, 0 versions changed, 0 removed, 100 added all `dev: true`; audit 0; guard exit 0; `npm ci` exit 0 | PR description | PASS |
| C-006 | yes | `/download` has no element that looks clickable but does nothing | inspect the rendered DOM and screenshots at 1280 and 375 | store badges and both download buttons are `disabled` with `aria-disabled="true"`, no `href`, visible status text, none in the tab order, no horizontal overflow at 375 | PR #134 description, section "Evidence: Download page DOM" (the `outerHTML` and computed state of all four controls, plus the text each one is described by); guarded from now on by `tests/downloadView.test.ts` | PASS |
| C-007 | yes | Every step of the CI `marketing` job passes locally | `make marketing-check`; `SELAHCUE_MIRRORS_REQUIRE=1 npm run test:mirrors` with the pinned Django 6.1.1; `SELAHCUE_HEADLESS_REQUIRE=1 npm run test:states` | all exit 0; "ALL MIRRORS AGREE"; "60 scenarios, 1751 checks, 0 FAIL" | local command output, and the CI marketing job (same steps, all green; see the Assumptions note above and the PR description for the run on the head) | PASS |
| C-008 | yes | The repo's other CI check scripts still pass after the Makefile and workflow edits | `check_launch_reachability.py` (self-test and real), `check_dependency_audit_coverage.py` (self-test and real), `check_toolchain.sh`, `ci_alarm.py --self-test`, `actionlint` | all exit 0 | command output | PASS |
| C-009 | yes | README is accurate and root `CLAUDE.md` no longer says `make ci` ignores the marketing site | read both against the code; every claim checked | claims verified against router, Makefile, workflow, nginx.conf | `git diff` | PASS |
| C-010 | yes | Independent review (code, performance, security, QA) has passed and blocking findings are remediated | Cody, Vera, Shadow, Quinn on the Draft PR | all four report; no open blocking finding | review report | PENDING |
| C-011 | yes | Review round 1 findings are fixed and each fix is proven to bite | a scratch element with a `v-html` directive through `npm run lint`; rename a `describedby` id and remove `disabled` against `tests/downloadView.test.ts`; a scratch single-word component through `npm run lint`; `eslint --print-config` before and after the `defineConfig` change | lint exit 1 naming `vue/no-v-html`; test exit 1 for each mutation; lint exit 1 naming `vue/multi-word-component-names`; configs byte-identical | PR #134 description, section "Review round 1" | PASS |

## Verification plan

- Focused verification: C-001 to C-004 with real exit codes captured to files, never piped
- Broader regression verification: every CI marketing step, the repo's check scripts, both viewports in a real browser
- Independent verifier: the four-reviewer gate (coordinator-dispatched)
- Required environment: Node 22+ (run on 26.7.0 locally; CI uses 22), Python 3.14 venv with `Django==6.1.1`, Chrome for `test:states`

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: a `marketing-check` target that runs the four npm scripts, wired into `make ci`, fails on type and lint errors
- Change or investigation: eslint (flat config), scripts, Makefile target, CI step swap; first lint run found 9 real errors (and 1,326 style warnings under `flat/recommended`, so the `essential` tier was chosen)
- Verifier executed: deliberate-failure runs listed in C-001 to C-003
- Result: all fail non-zero as expected and pass after revert
- New evidence: `vue-tsc` surfaced three type errors the removed `any`s had hidden (a nullable `targetDevice`, a slot `row` type, an unknown sort comparison); fixed rather than cast
- Decision: iterate

### Iteration 2

- Target criterion: C-004, C-007, C-008
- Hypothesis: the CI job can call the make target, and the Makefile edit must also re-trigger the marketing job
- Change or investigation: replaced the Build and Tests steps with `make marketing-check`; added `Makefile` to the marketing path filter
- Verifier executed: actionlint, the check scripts, then every remaining marketing step locally
- Result: all exit 0
- New evidence: none contradicting the plan
- Decision: iterate

### Iteration 3

- Target criterion: C-006, C-009
- Hypothesis: native disabled buttons with visible status text satisfy "no fake control" without adding a dead tab stop
- Change or investigation: DownloadView badges and buttons; README; CLAUDE.md
- Verifier executed: DOM inspection, screenshots at 1280 and 375
- Result: pass
- New evidence: the card said `Version 1.2.0 (Stable)` for a product with no served installer and crate version 0.1.0; replaced with the real status
- Decision: handoff

### Iteration 4

- Target criterion: C-011
- Hypothesis: the reviewers' findings are real gaps, not preferences (the config header claimed a v-html check that was not on; nothing guarded the Download states; the README's Node floor was too low)
- Change or investigation: enabled `vue/no-v-html`; added `tests/downloadView.test.ts`; `engines` and README to Node 22.18; narrowed the component-name exemption to three files; moved to `defineConfig`; CLAUDE.md fresh-worktree note
- Verifier executed: the bite proofs listed in C-011, `make marketing-check`, `test:mirrors`, the repo's check scripts; `test:states` could not complete locally under machine load (see the PR description) and was verified by the CI marketing job
- Result: every fix bites; the full gate is green locally and in CI
- New evidence: `npm install --package-lock-only` also rewrites `node_modules/.package-lock.json`, so the stale-install guard (which compares the two files' ages) does not notice a lockfile edited that way; every other route to a changed lockfile (pull, checkout, a real `npm install`) is caught. Recorded, not fixed
- Decision: handoff

## Risks and rollback

- Risks: the disabled desktop buttons go beyond the literal "store badges" wording; ESLint 10 and typescript-eslint 8 are new dev dependencies (100 packages, none shipped)
- Rollback or recovery: each concern is its own commit and reverts cleanly; the Makefile target and CI step revert together

## Pause and escalation conditions

- A reviewer finds the desktop-button change out of scope: drop commit "disable the Windows and macOS download buttons" and re-run C-006 for the badges alone (owner: coordinator)
- First CI run fails on the `marketing` job for a reason local runs did not show: fix on the branch before review (owner: frontend-engineer)

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b0q9j-marketing-gates-download.md`
- Validator result: structural check green; `--completion` withheld until C-010 is PASS
- Independent verification result: pending (C-010)
- Terminal state: GATE_REVIEW (handoff to the four-reviewer gate)
- Remaining failed or blocked criteria: C-010
- ClickUp final evidence comment: to be posted by the coordinator
