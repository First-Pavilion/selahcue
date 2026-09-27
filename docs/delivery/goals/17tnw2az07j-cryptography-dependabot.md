# Goal Contract — 17tnw2az07j-cryptography-dependabot

## Identity

- Goal ID: 17tnw2az07j-cryptography-dependabot
- Parent goal ID: NONE
- Title: `cryptography` floor excludes every published vulnerable range in `implementation/api`, the API test suite passes on the bump, and `.github/dependabot.yml` gives all four package ecosystems (plus `github-actions`) scheduled update coverage
- Role: devops-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2az07j
- Created: 2026-09-26
- Updated: 2026-09-26
- Maximum iterations: 22
- Independent verification required: yes

**Iteration cap note:** raised from 8 to 12 after Sana's S-1 finding (Iteration 8) required a materially new increment — the exact-pin fix, framing corrections, and a linked follow-up ticket. Raised to 16 after the user explicitly declined to accept the interim gap on Django/strawberry-graphql-django/celery (Iteration 10) — widening this same PR to pin all four direct pip deps, closing the follow-up ticket instead, and re-dispatching all four reviewers against the new head. Raised to 22 after Sana's second-pass S-5 finding (Iteration 15) — an undeclared, directly-imported dependency (`strawberry-graphql`, caught first by Vera) and a live, currently-unpatched dev-dependency CVE (`pytest`), plus a correction that closing the follow-up ticket had itself been premature. Every raise so far is a genuine correction to what "done" means for this ticket, not scope creep — each came from an independent reviewer finding something real that the prior round had missed.

## Objective

**Widened (Iteration 10):** the user declined to accept an interim gap on
Django/strawberry-graphql-django/celery being left as open ranges while only
`cryptography` was pinned — see Iteration 10 below. All four direct pip
dependencies in `implementation/api/pyproject.toml` are now exact pins,
each independently checked against published CVE data, not just `cryptography`.

`implementation/api/pyproject.toml`'s `cryptography` constraint has a floor that
excludes every currently-published vulnerable version range (re-derived from the
actual failed Dependabot job log, not assumed), the full Django API test suite
passes with that version installed (proving `apps/entitlements/signing.py`'s
Ed25519 usage — DEC-004 — still works), and `.github/dependabot.yml` exists
covering cargo (`/implementation/desktop`), pip (`/implementation/api`), npm
(`/implementation/marketing`), pub (`/implementation/mobile/selahcue_controller`)
and `github-actions`, on a weekly schedule. The four-reviewer gate passes and a
Draft PR is open against `main` with green `gh pr checks`.

## Baseline

**Verified** from `gh run view 36129784977 --log-failed`: the `Dependabot Updates`
workflow failed for `cryptography` on **2026-09-05 and 2026-09-25 only**, both with
`dependency_file_not_supported`, because `implementation/api/pyproject.toml` declared
`cryptography>=43,<47` — an open range with no lockfile — and Dependabot's log states
verbatim: "Dependabot can't update vulnerable dependencies for projects without a
lockfile or pinned version requirement as the currently installed version of
cryptography isn't known." **Correction (Sana security review, PR #110, finding S-4):**
an earlier draft of this contract also listed 3 failures on 2026-07-24 as part of this
same pattern. Those three runs are a different package and a different error entirely
— `glib` (cargo, in `selahcue-operator`), `security_update_not_possible`, already an
accepted risk (`docs/delivery/RISK-REGISTER.md` RISK-015). Only the two September runs
are this ticket's `cryptography`/`dependency_file_not_supported` failure.
The same job log's `security-advisories` payload is the authoritative,
machine-emitted list of every affected-version range GitHub's advisory feed
currently has on file for `cryptography`; the highest ceiling among all 24
entries is `>= 44.0.0, < 50.0.0`. **Verified** from PyPI (job log) and the
upstream changelog: latest published release is `50.0.1`. Its own changelog
entry is a wheel rebuild against a newer OpenSSL (4.0.2) — not an additional
CVE fix of its own (corrected per Cody's PR #110 review; an earlier draft of
this Baseline wrongly attributed a buffer-overflow/name-constraint fix to
50.0.1 that actually belongs to an older release, 46.0.6/46.0.7). 50.0.0 is
the one that fixes a CVE directly (Bleichenbacher-oracle, CVE-2026-69247).
**Verified**: `.github/dependabot.yml` does not exist in the repo at all — `git
log`/`ls .github/` show only `ci.yml`, `rust-canary.yml`, `windows-installer.yml`;
nothing references `dependabot-action`, confirming the security-update runs seen
are GitHub's native "Dependabot security updates" repo setting, independent of
any config file.

## Inputs and evidence sources

- `gh run view 36129784977 --log-failed` (2026-09-25 run) and `gh run view 33943911929 --log-failed` (2026-09-05 run) — both `cryptography`/`dependency_file_not_supported`; the 3 earlier 2026-07-24 failures are an unrelated `glib`/`security_update_not_possible` case, not part of this trail (corrected, Sana review S-4)
- `implementation/api/pyproject.toml` — current constraint
- `implementation/api/selahcue_api/apps/entitlements/signing.py` — the only `cryptography` consumer
- `docs/decisions/DECISION-LOG.md` (DEC-004, DEC-005) — why the offline entitlement is signed and cached
- `implementation/api/README.md` — local verification commands, shared venv convention
- `.github/workflows/ci.yml`, `rust-canary.yml` — existing schedule/permissions conventions to match
- `cryptography` upstream changelog (`https://cryptography.io/en/latest/changelog/`) — breaking-change review across 47–50.0.1
- This repo's `CLAUDE.md` — `make ci` does not cover `implementation/api`; run Django's own tooling

## Scope

### In scope

- Bump the `cryptography` floor in `implementation/api/pyproject.toml` to a version provably above every currently-published vulnerable range, with the derivation recorded in a comment
- Confirm `apps/entitlements/signing.py`'s Ed25519 signing/verification still passes under the new version via the full `implementation/api` test suite (Django's own tooling, not `make ci`)
- Add `.github/dependabot.yml` for cargo, pip, npm, pub, and github-actions, weekly cadence
- Record honestly that Dependabot's own re-verification cannot be forced on demand

### Non-goals

- **Superseded (Iteration 10):** exact-pinning Django/strawberry-graphql-django/celery was originally treated as a non-goal, filed to a follow-up (17tnw2az0kw). The user explicitly declined to accept that interim gap; this ticket now pins all four direct pip deps, and 17tnw2az0kw is closed as resolved by this PR rather than left open for redundant tracking.
- Adding a real **lockfile** (`uv.lock`/`pip-tools` or similar) for `implementation/api` — still out of scope. Exact pins close the security exposure (installed version now knowable to Dependabot for all four deps); a lockfile is a separate, larger improvement for smoother *routine* (non-security) dependency management, not a security gap.
- Any other dependency bump not required to resolve this CVE-coverage gap or (after widening) the four direct pip deps' pin requirement
- Changing `implementation/api`'s CI job in `.github/workflows/ci.yml` (not required by the acceptance criteria; `make ci` explicitly does not cover `api` per repo `CLAUDE.md`)
- Rotating or touching `SELAHCUE_ENTITLEMENT_SIGNING_KEY` itself

### Constraints

- Never work on `main`; own worktree + ticket branch, cut from `origin/main`
- Do not merge the PR without explicit user request
- `make ci` is unaffected by this change (verify no desktop/mobile/marketing manifest touched incidentally)
- Dependabot runs are not user-triggerable; do not claim an end-to-end re-verification that didn't happen

### Assumptions and unknowns

- **Assumed:** the security-advisories list captured in the 2026-09-25 job log is complete and current as of that run; a newer advisory published after that run is not covered by this goal (structural — no scheduled or on-demand tool re-emits that exact payload outside a live Dependabot job)
- **Verified:** no Ed25519-specific breaking changes are documented in the `cryptography` changelog between 43 and 50.0.1 (checked via WebFetch of the upstream changelog)
- **Unknown, to be recorded not resolved:** whether the open-range (no-lockfile) approach is sufficient for Dependabot's *routine* version-update job (as opposed to the security-update job that was failing) — the only real proof is the next scheduled/security-triggered run, which is out of this session's control

## Dependencies and approvals

- GitHub Dependabot native security-update setting (repo Security settings) — owned by repo admin, not modified by this goal
- Four-reviewer gate (Cody, Vera, Sana, Quinn) — required before `VERIFIED_COMPLETE`
- User approval required before merging the resulting PR (not requested in this goal)

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `cryptography` version in `implementation/api/pyproject.toml` excludes every affected-version range from the actual failed job's advisory payload | Manual range check: pinned version ≥ max(all affected-version ceilings) = 50.0.0 | Exact pin is `==50.0.1`, strictly above every ceiling in the 24-entry advisory list (Sana independently re-derived the same 24 entries from OSV.dev, a source outside this repo) | `implementation/api/pyproject.toml` diff + this contract's Baseline section | PASS |
| C-002 | yes | `implementation/api` Django system checks pass with the new version installed | `python manage.py check` (venv with cryptography 50.0.1) | `System check identified no issues (0 silenced).` | command output | PASS |
| C-003 | yes | No missing migrations introduced | `python manage.py makemigrations --check --noinput` | `No changes detected` | command output | PASS |
| C-004 | yes | Full `implementation/api` test suite passes with `cryptography==50.0.1`, including entitlement-signing coverage | `python -m pytest tests -q` | All tests pass, `0` failed | `554 passed, 3 skipped in 169.57s` (range, Iteration 2) and re-confirmed `554 passed, 3 skipped in 119.32s` after switching to the exact pin (Iteration 8) | PASS |
| C-005 | yes | `.github/dependabot.yml` exists and declares all four ecosystems + github-actions on a weekly schedule, covering every real lockfile | `cat .github/dependabot.yml`; manual review against directories; `find implementation/desktop -iname Cargo.lock` | cargo→3 directories (root + selahcue-operator + selahcue-stt, each with its own tracked Cargo.lock), pip→/implementation/api, npm→/implementation/marketing, pub→/implementation/mobile/selahcue_controller, github-actions→/, all `interval: weekly` | file content + Iteration 5 (Vera's finding + fix) | PASS |
| C-006 | yes | `make ci` is not required/affected by this change (api excluded per repo CLAUDE.md) — no desktop/mobile/marketing manifest touched | `git diff --stat origin/main...HEAD` | Only `implementation/api/pyproject.toml`, `.github/dependabot.yml`, and `docs/delivery/goals/*` changed | diff output: exactly those 3 files, 1 commit ahead / 0 behind `origin/main` | PASS |
| C-007 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) completed, blocking findings remediated | Reviewer reports, published as Artifact per Operating Contract | No blocking findings outstanding | Artifact URL + ClickUp comment | PENDING |
| C-008 | yes | Draft PR open against `main`, real `gh pr checks` green (or explained if a check is structurally unrelated) | `gh pr checks` against the opened PR number | All applicable checks pass | PR #110: `api (django)` pass 4m55s, `marketing (vue spa)` pass 1m42s, `detect changed areas` pass, `workflows (actionlint+permissions)` pass; all others correctly `skipping` (path-filtered, untouched areas); no open `ci-red` alarm | PASS |
| C-009 | yes | Honest note recorded that Dependabot's own re-verification cannot be forced; real proof is the next scheduled/security-triggered run | ClickUp comment + PR description text present | Statement present, not a false completion claim | ClickUp start comment (id 1400430000022688) + PR #110 description, both state this explicitly | PASS |
| C-010 | yes | The Dependabot automation failure mode itself (not just the CVE) is closed for `cryptography`: the installed version is knowable without a lockfile | `implementation/api/pyproject.toml` declares an exact pin (`==`), matching Dependabot's own stated alternative ("a lockfile or pinned version requirement") | `cryptography==50.0.1`, no range | pyproject.toml diff; independently confirmed the *prior* state's gap via `gh api repos/.../dependency-graph/sbom` showing no `versionInfo` for `cryptography` (Sana, S-1) | PASS |
| C-011 | yes | **Superseded twice.** Iteration 10: required the follow-up be closed once all four direct deps were pinned. Iteration 15 (Sana S-5, corroborated by Quinn): that closure was itself premature — the follow-up's real scope (transitive packages + `psycopg`) wasn't actually resolved. Final form: claims must be precisely scoped (declared + directly-imported packages are pinned; the wider transitive graph and `psycopg` are not, and are honestly tracked as open) | Re-read PR description, ClickUp comments, and this contract for accurate scoping; confirm follow-up ticket reflects its real remaining scope and is not closed prematurely | No unscoped "root cause fixed"/"no gap remains" claim anywhere; 17tnw2az0kw reopened (Planning/Todo) with accurate acceptance criteria | PR #110 description (to be rewritten, Iteration 15); ClickUp 17tnw2az0kw comment id 1400430000022764, moved back to Planning/Todo | PENDING |
| C-012 | yes | `Django` pin excludes every published advisory affecting it | GH Advisory Database (`gh api /advisories?ecosystem=pip&affects=Django`) and OSV.dev (`api.osv.dev/v1/query`), cross-checked | `Django==6.1.1`; 0 advisories in either source affect 6.1.1 | Iteration 10 evidence below; `implementation/api/pyproject.toml` diff | PASS |
| C-013 | yes | `strawberry-graphql-django` pin excludes every published advisory affecting it | Same two sources | `strawberry-graphql-django==0.87.1`; 0 advisories exist for this package in either source | Iteration 10 evidence below | PASS |
| C-014 | yes | `celery[redis]` pin excludes every published advisory affecting it | Same two sources | `celery==5.6.3`; highest advisory ceiling in either source is `<5.2.2` (GHSA-q4xr-rc97-m4xx/CVE-2021-23727), far below 5.6.3 | Iteration 10 evidence below | PASS |
| C-015 | yes | Full `implementation/api` test suite passes with all four direct deps exact-pinned | `python -m pytest tests -q` | All tests pass, `0` failed | `554 passed, 3 skipped in 133.20s` — identical to every prior run (Iteration 10) | PASS |
| C-016 | yes | Every package **directly imported** by `implementation/api` code (not just declared "direct dependencies") has a knowable, safe, exact-pinned version — not left floating as an undeclared transitive dependency | Grep for `import strawberry`/`from strawberry` etc. across `selahcue_api/`; cross-check each undeclared-but-imported package's version against GH Advisory DB + OSV.dev | `strawberry-graphql` (imported in `graphql/{admin,account}_schema.py`, `graphql/views.py`) was undeclared, floating via `strawberry-graphql-django`'s own unbounded `>=0.310.1` requirement, and that permitted range included 7 advisories (highest ceiling `<=0.315.6`); now declared `==0.327.7`, above every ceiling in both sources | Iteration 14 evidence below; `implementation/api/pyproject.toml` diff (Vera finding, PR #110 second pass) | PASS |
| C-017 | yes | Dev dependencies aren't left with a live, currently-unpatched advisory reachable in their declared range | `pip show pytest`; cross-check against GH Advisory DB + OSV.dev | `pytest>=8,<9` resolved to `8.4.2`, affected by CVE-2025-71176/GHSA-6w46-j5rx-g56g (fixed 9.0.3, unreachable within the `<9` cap); now `pytest==9.1.1`, 0 further advisories, verified compatible with `pytest-django==4.14.0` | Iteration 15 evidence below (Sana finding S-5, corroborated by Quinn) | PASS |
| C-018 | yes | Every claim that "no gap remains" / "every dependency's installed version is now knowable" is precisely scoped to what's actually true (declared + directly-imported packages), not overclaimed to cover the full transitive graph or `psycopg` | Re-read `pyproject.toml`, `dependabot.yml`, PR description, ClickUp comments for the exact wording | No remaining unscoped "every dependency"/"no gap remains" claim; the real residual gap (transitive packages, `psycopg`) stated explicitly wherever the claim is made | `pyproject.toml`/`dependabot.yml` comment rewrites (Iterations 15, 17); 17tnw2az0kw reopened with accurate scope, moved back to Planning/Todo, comment id 1400430000022764 | PASS |
| C-019 | yes | The "every package this app's own code imports directly is pinned" claim is verified exhaustively across the WHOLE app, not spot-checked one directory at a time | recursive grep for every top-level `import`/`from` statement under `selahcue_api/`; cross-reference every non-stdlib result against `pyproject.toml` | Every third-party import (`celery`, `cross_web`, `cryptography`, `django`, `graphql`, `strawberry`) has a matching exact-pinned declaration; nothing left unaccounted for | Iteration 17 evidence below (Vera + Sana independently found `graphql-core`/`cross-web` as a third instance of this same gap, S-6) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `python manage.py check`, `python manage.py makemigrations --check --noinput`, `python -m pytest tests -q` — all against a fresh venv with `cryptography==50.0.1` installed from the updated `pyproject.toml`
- Broader regression verification: full `implementation/api` test suite (not just entitlements app) — the ticket's own AC requires this rather than a targeted subset
- Independent verifier: Cody (code), Vera (performance — N/A likely, justify), Sana (security — primary reviewer for CVE-coverage correctness), Quinn (QA)
- Required environment: local venv at `/private/tmp/selahcue-api-venv` (Python 3.14, matching CI's `api` job and this repo's README), isolated from other worktrees' shared state

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-003
- Hypothesis: bumping the floor to `>=50.0.1,<51` clears the vulnerable-range overlap and Django's own checks stay green
- Change or investigation: edited `implementation/api/pyproject.toml`; built venv at `/private/tmp/selahcue-api-venv` with Python 3.14; `pip install -e ".[dev]"`
- Verifier executed: `manage.py check`, `manage.py makemigrations --check --noinput`
- Result: both PASS (`System check identified no issues (0 silenced).`, `No changes detected`)
- New evidence: `cryptography 50.0.1` resolves cleanly with Django 6.1.1 / strawberry-graphql-django 0.87.1 / celery 5.6.3 — no dependency conflict reported by pip
- Decision: iterate (run full test suite next — C-004)

### Iteration 2

- Target criterion: C-004
- Hypothesis: the full test suite (not just the entitlements app) passes unchanged with `cryptography==50.0.1` installed
- Change or investigation: ran `/private/tmp/selahcue-api-venv/bin/python -m pytest tests -q` from `implementation/api`
- Verifier executed: `pytest tests -q`
- Result: PASS — `554 passed, 3 skipped in 169.57s (0:02:49)`, exit code 0
- New evidence: no failures anywhere in the suite, not only the entitlements app; skip count (3) matches pre-existing skips unrelated to this change (confirmed by name in the follow-up `-rs`/`-k entitlement` run)
- Decision: iterate (confirm diff scope — C-006 — then move to review gate)

### Iteration 3

- Target criterion: C-004 (corroborate skip reasons), C-006
- Hypothesis: the 3 skips are pre-existing and unrelated to this change; the committed diff touches only the intended 3 files and the branch is not behind `origin/main`
- Change or investigation: `pytest tests -q -rs` (skip reasons), `pytest tests -k "entitlement or signing" -q` (targeted corroboration), committed (`bd3ebf8`), `git fetch origin main` + `git diff --stat origin/main...HEAD` + `git rev-list --count` both directions
- Verifier executed: as above
- Result: PASS on both — skips are `tests/test_concurrency_postgres.py` (`select_for_update is a no-op on SQLite`), unrelated to cryptography; entitlements/signing subset: `82 passed, 475 deselected`; diff is exactly `implementation/api/pyproject.toml`, `.github/dependabot.yml`, `docs/delivery/goals/*`; 1 commit ahead, 0 behind `origin/main`
- New evidence: no ambiguity left on C-004 or C-006
- Decision: iterate (open the four-reviewer gate next — C-007)

### Iteration 4

- Target criterion: C-001 (independent corroboration)
- Hypothesis: GitHub's own Dependabot Alerts feature (distinct from the failing `Dependabot Updates` workflow) has an authoritative view of this repo's currently-open `cryptography` alerts, independent of my manual derivation from the job log
- Change or investigation: `gh api /repos/First-Pavilion/selahcue/dependabot/alerts?per_page=100` after pushing the branch and opening PR #110
- Verifier executed: inspect the returned alert list for any `dependency.package.name == "cryptography"` entry
- Result: exactly **one** cryptography alert existed in the repo at all — #3, `GHSA-jwv3-5hgf-82ww` / `CVE-2026-69249`, `vulnerable_version_range: >=42.0.0, <49.0.0`, `first_patched_version: 49.0.0`. It is now `"state": "fixed"`, `"fixed_at": "2026-09-26T18:39:37Z"` — recorded by GitHub itself, not asserted by me. (Unrelated: alert #1, `glib`/Rust, is a pre-existing accepted risk per `docs/delivery/RISK-REGISTER.md` RISK-015 — out of scope, not touched.)
- New evidence (as originally recorded — **retracted below, Iteration 8**): independent, GitHub-computed confirmation that the new floor (`>=50.0.1`) resolves the one cryptography alert this repo actually had open, on top of the manual advisory-range derivation
- Caveat recorded honestly: this is the **Dependabot Alerts** feature, not the **Dependabot Updates** workflow that was failing (`dependency_file_not_supported` is a workflow/updater-job failure mode, separate from alert computation). This does not by itself prove the next scheduled/security-triggered `Dependabot Updates` run will succeed — that remains the un-forceable, un-verifiable-in-session proof per AC #4. Both facts are stated in the PR and ClickUp, not conflated.
- Decision: iterate (proceed to reviewer gate; already dispatched Cody/Vera/Sana/Quinn in parallel against PR #110)

> **RETRACTION (Sana security review, PR #110, finding S-1 — see Iteration 8):** the "new evidence" line above is wrong and must not be read as support for the floor. Alert #3's `fixed_at` is `2026-09-26T18:39:37Z`; this branch's first commit (`bd3ebf8`) was made at `2026-09-26T23:11:13+01:00` = `22:11:13Z` UTC (**corrected twice** — a first draft miscalculated the UTC value as `21:11:13Z`; the fix for that then mistranscribed the *local* time as `22:11:13+01:00` instead of the actual `23:11:13+01:00`, which Sana's third-pass review caught. The UTC conversion `22:11:13Z` was right both times; only the displayed local time was wrong. Re-verified directly: `git log --format='%H %ad' --date=iso-strict bd3ebf8 -1` → `2026-09-26T23:11:13+01:00`) — over 3 hours *after* the alert already closed either way, and the PR opened later still. The alert cannot have closed because of a floor that did not exist yet on any branch, and GitHub computes alerts against `main`, where the manifest was (and after Iteration 4, still is at the time of this retraction) unchanged. The timing instead lines up with PR #105 merging to `main` 6 seconds earlier (`2026-09-26T18:39:32Z`), which touched no Python manifest. Sana's read: this is coincidental, not confirmatory, and treating it as corroboration "turns a warning sign into false reassurance" — main is still exposed and nothing is currently warning anyone of that. Left the original text above struck through rather than deleted, per the instruction not to erase a tracked finding.

### Iteration 5

- Target criterion: C-001 (comment accuracy), C-005 (cargo ecosystem completeness), C-007 (remediate reviewer findings)
- Hypothesis: Cody's and Vera's independently-reproduced reviews found two real, fixable issues that don't change the underlying safety conclusion but do need correcting before the gate closes
- Change or investigation:
  - **Cody (approved, 0 blocking, one Medium):** the `pyproject.toml` comment claimed `cryptography` 50.0.1 "carries its own fixes (buffer-overflow and certificate name-constraint issues)". Re-fetched the upstream changelog directly (`https://cryptography.io/en/stable/changelog/`) for 50.0.1/50.0.0/46.0.6 verbatim: 50.0.1's only entry is an OpenSSL 4.0.2 wheel rebuild; the Bleichenbacher-oracle fix is 50.0.0's (correct as stated); the name-constraints/wildcard-DNS-SAN fix (CVE-2026-34073) is actually 46.0.6's, an older release this floor already supersedes and unrelated to the 50.0.1-over-50.0.0 choice. Corrected the comment to state the real reason (PyPI's actual latest, wheel-only change) and explicitly note the earlier claim was wrong, so a future re-derivation doesn't inherit the error. Also confirmed C-006 was already `PASS` (Cody had flagged it as still `PENDING` from his read of an earlier version; it was already updated by Iteration 3).
  - **Vera (approved, 0 blocking performance findings; one out-of-lane correctness finding for Cody/Sana):** independently confirmed via her own `git log`/CI measurements that the Ed25519 signing path has no meaningful performance exposure from this bump (one signature per request, tens of microseconds, next to a DB write). Flagged that `.github/dependabot.yml`'s single `cargo` entry at `/implementation/desktop` misses `crates/selahcue-operator` and `crates/selahcue-stt` — both `exclude`d from the root Cargo workspace, each with its own `[workspace]` and its own tracked `Cargo.lock`. Verified independently: `find implementation/desktop -iname Cargo.lock` returns exactly 3 lockfiles (root, selahcue-operator, selahcue-stt); `grep '^\[workspace\]'` confirms both crates declare their own workspace. The dependabot.yml comment claiming they were "picked up as workspace members" was factually wrong. Fixed by switching the `cargo` entry to `directories:` (confirmed via GitHub's own Dependabot options reference that `directories` is a real, documented, list-valued sibling of `directory`) listing all three paths, and corrected the comment.
  - Also adopted Vera's advisory (non-blocking, but cheap and directly reduces the CI-churn risk her own finding just increased by adding 2 more cargo directories): added `groups` (minor+patch vs. major) and `open-pull-requests-limit: 2` to the `cargo` and `github-actions` entries specifically — the two ecosystems where a single PR's lockfile edit conflicts every other open PR of the same ecosystem and where `ci.yml`'s path filter treats any workflow-file change as touching every area. Left `pip`/`npm`/`pub` ungrouped since they don't share that failure mode.
- Verifier executed: re-fetched and re-read the upstream changelog verbatim for the three versions in question; `find`/`grep` against `implementation/desktop` to confirm the 3-lockfile claim; re-parsed `.github/dependabot.yml` with PyYAML after each edit; re-parsed `pyproject.toml` with `tomllib` to confirm the dependency specifier itself (`cryptography>=50.0.1,<51`) is unchanged, only the comment changed
- Result: PASS — both findings confirmed accurate before acting on them (per `superpowers:receiving-code-review` — verify, don't blindly implement), both fixed, YAML/TOML still valid, no code/behavior change, nothing to re-run in the test suite (comment-only change to pyproject.toml; dependabot.yml is config, not executed by any test)
- New evidence: two independent reviewers each reproduced the core claims themselves from primary sources (job log, changelog, live CI, disk) rather than trusting the PR description — this is exactly the independent-verification bar the operating contract requires, and both surfaced real, distinct issues neither of us would have caught alone
- Decision: iterate (commit and push the fixes; awaiting Sana and Quinn)

### Iteration 6

- Target criterion: C-008 (re-confirm CI on the fixup commit), C-007 (reconcile Quinn's finding with the already-pushed fix)
- Hypothesis: the fixup commit (`6e51343`) keeps CI green and closes Quinn's independently-raised AC #3 finding, which was filed against the prior commit
- Change or investigation: watched CI run `36282989244` to completion; separately, Quinn (QA) posted a review with one blocking finding on AC #3 — the same `cargo`/`directories` gap Vera found — but timestamped against head `bd3ebf8`, before the fixup was pushed
- Verifier executed: `gh pr checks 110` on the new head; direct message to Quinn (agent a4eb6bbecea765a2c) asking her to re-verify against `6e51343`; PR comment and ClickUp comment posted documenting the timing so a human reader isn't confused by an apparently-still-open blocking finding
- Result: CI green — `api (django)` pass (4m56s), `marketing (vue spa)` pass (1m38s), `detect changed areas` pass, `workflows (actionlint+permissions)` pass, and a new check `.github/dependabot.yml` (GitHub's own Dependabot config validator, not something I control) also passes on the corrected file. Quinn's re-check is outstanding.
- New evidence: GitHub's own platform-side Dependabot config validation (distinct from my local PyYAML parse) confirms the file is schema-valid
- Decision: iterate (awaiting Quinn's re-confirmation against `6e51343` and Sana's first pass)

### Iteration 7

- Target criterion: C-007
- Hypothesis: Quinn's blocking AC #3 finding, filed against `bd3ebf8`, closes once she independently re-checks the actual diff on `6e51343` rather than accepting the remediation summary
- Change or investigation: no code change; messaged Quinn directly asking for re-verification against the new head
- Verifier executed: Quinn's own independent re-check (her report): confirmed PR head SHA is `6e51343` via `gh pr view`, diffed `bd3ebf8...6e51343` herself, independently verified `directories:` is real documented Dependabot syntax (not just trusting my claim), re-parsed the YAML herself, confirmed the `pyproject.toml` comment fix is accurate, watched CI run `36282989244` to completion herself, and independently noticed the new `.github/dependabot.yml` GitHub-native validator check (absent on the prior head) now passes
- Result: PASS — Quinn's updated verdict: "No blocking findings remain. AC #1-#5 all independently verified PASS on PR #110 head `6e51343`." Posted on the PR and mirrored to ClickUp.
- New evidence: three of four reviewers (Cody, Vera, Quinn) are now clean against the current head. Sana has not yet posted a review.
- Decision: iterate (awaiting Sana's first pass — the primary reviewer for this ticket's actual purpose)

### Iteration 8

- Target criterion: C-001 (rework), C-005 (rework), C-010 (new), C-011 (new)
- Hypothesis: Sana's security review (head `3120239`) found a real, blocking gap this ticket's own reviewers had not caught — the version-range fix, however correct on the CVE math, did not close the actual mechanism that broke Dependabot's security-update job, and two of the ticket's own evidentiary claims (the July timeline, the Dependabot-alert-as-corroboration) were wrong
- Change or investigation, in order:
  1. Independently re-verified before acting (per `superpowers:receiving-code-review`): `gh api repos/.../dependency-graph/sbom` — confirmed `cryptography` on `main` today has no `versionInfo` field at all, matching Sana's claim exactly. `curl` against `pypi.org/pypi/selahcue-api/json` — confirmed 404, consistent with her "library" classification of this package for Dependabot's pip strategy heuristic. Re-checked commit timestamps: `bd3ebf8` was authored `2026-09-26T23:11:13+01:00` = `22:11:13Z` UTC (this line itself originally miscalculated the UTC conversion as `21:11:13Z`; caught and fixed during Sana's S-5 pass — then the fix mistranscribed the local time as `22:11:13+01:00`, caught by a further Sana pass — see the retraction note above); the Dependabot alert #3 `fixed_at` is `18:39:37Z` the same day — the alert closed **over 3 hours before this branch's first commit existed** either way, confirming her timing objection is correct, not just plausible. Cross-checked PR #105's merge timestamp (`18:39:32Z`, 5 seconds before the alert closed, touching no Python manifest) — consistent with her "coincidental, not confirmatory" read.
  2. **S-1 fix (blocking):** switched `implementation/api/pyproject.toml`'s `cryptography` from a range (`>=50.0.1,<51`) to an exact pin (`==50.0.1`) — this is the specific alternative Dependabot's own error message names ("a lockfile OR a pinned version requirement"). Rewrote the pyproject.toml comment to explain why a pin, not a lockfile, was chosen for this one dependency (bounded scope), and that Django/strawberry-graphql-django/celery remain open ranges with the identical exposure, tracked as a follow-up.
  3. Added `versioning-strategy: increase` to `.github/dependabot.yml`'s `pip` entry — Sana's suggested cheap partial mitigation for the three still-open-range deps, so the weekly routine job at least raises their floors as new releases ship (not advisory-triggered, so not a full fix, and documented as such in the file's own comment).
  4. **S-4 fix (low):** corrected the "since 2026-07-24"/"since July" timeline claim in three places — this contract's Baseline and Inputs sections, and `.github/dependabot.yml`'s header comment — to state the `cryptography` failures were 2026-09-05 and 2026-09-25 only, and that the three 2026-07-24 runs were an unrelated `glib`/`security_update_not_possible` case (RISK-015).
  5. **Retraction:** struck through (not deleted) Iteration 4's claim that the Dependabot Alert's `fixed_at` state was evidence the floor worked, with the timing math showing why that's impossible, per Sana's explicit instruction not to erase a tracked finding.
  6. Filed linked ClickUp follow-up 17tnw2az0kw ("implementation/api needs a lockfile so Dependabot (and CI) can know its installed dependency versions") covering Django/strawberry-graphql-django/celery, with an explicit accepted-interim-gap statement, per Sana's requirement that this not be silently dropped.
  7. Re-installed the venv against the exact pin and re-ran the full verification chain.
- Verifier executed: `python3 -c "import yaml; ..."` (dependabot.yml re-parse), `python -c "import tomllib; ..."` (pyproject.toml re-parse), `pip install -e ".[dev]"`, `manage.py check`, `manage.py makemigrations --check --noinput`, `pytest tests -q`
- Result: PASS on all — YAML/TOML valid, `pip show cryptography` confirms `50.0.1` resolved from the exact pin with no conflicts, Django checks clean, **554 passed, 3 skipped, 0 failed** (re-confirmed identical to the range-based run's counts)
- New evidence: this is the first point in the ticket where the *automation mechanism* itself (not just the CVE) is verifiably closed for `cryptography` — confirmed by matching the fix directly against Dependabot's own stated requirement, not by inference
- Decision: iterate (push the fixup; ask Sana to re-verify against the new head; do not claim VERIFIED_COMPLETE until she does)

### Iteration 9

- Target criterion: C-008 (re-confirm CI on head `44f49fd`)
- Change or investigation: pushed `44f49fd`; watched CI run `36283931486` to completion; also rewrote PR #110's description (C-011) and posted remediation summaries to the PR and ClickUp; messaged Sana directly asking for re-verification
- Verifier executed: `gh pr checks 110`
- Result: PASS — `api (django)` pass (3m52s), `marketing (vue spa)` pass (1m14s), `detect changed areas` pass, `workflows (actionlint+permissions)` pass, `.github/dependabot.yml` (GitHub-native validator) pass. Everything else correctly `skipping`.
- New evidence: none beyond reconfirming green; awaiting Sana's re-check
- Decision: iterate (awaiting Sana's re-verification against `44f49fd` before closing C-007/C-010)

### Iteration 10

- Target criterion: C-011 (rework), C-012, C-013, C-014 (new), C-015 (new)
- Hypothesis: the user, informed that 17tnw2az0kw would leave Django/strawberry-graphql-django/celery on open ranges as an accepted interim risk, declined to accept that risk and asked for this same PR to be widened to pin all four direct pip deps now, with the same CVE-check rigor applied to `cryptography`
- Change or investigation:
  1. Checked currently-resolved/latest-safe versions: `pip show` confirmed `Django 6.1.1`, `celery 5.6.3` (both already the actual PyPI latest within their declared ranges); `strawberry-graphql-django 0.87.1` (PyPI's actual latest is 0.90.0, but the declared range `<0.88` already resolves to 0.87.1).
  2. Checked each against published CVE data from **two independent sources**, same rigor as `cryptography` and matching Sana's own methodology: the GitHub Advisory Database (`gh api /advisories?ecosystem=pip&affects=<pkg>`) and OSV.dev (`api.osv.dev/v1/query`).
     - **Django 6.1.1:** OSV query returned 321 historical vulnerabilities for the `django` PyPI package; wrote a range-matching script (`packaging.version`/`packaging.specifiers`) to check which affect 6.1.1 specifically — 0 do (the first pass had a bug that missed `last_affected`-only ranges, producing a false positive on a 2011 CVE for Django 1.0–1.3.1; fixed and re-run). GitHub Advisory Database query independently returned 160 Django advisories; 0 affect 6.1.1 (cross-confirms OSV).
     - **strawberry-graphql-django 0.87.1:** 0 advisories in either source, for any version of this package.
     - **celery 5.6.3:** OSV returned 4 records (2 unique GHSA IDs, PYSEC mirrors); GitHub Advisory Database independently returned 2. Highest ceiling in both: `< 5.2.2` (GHSA-q4xr-rc97-m4xx / CVE-2021-23727) — 5.6.3 is far above it.
  3. Switched all three from ranges to exact pins in `implementation/api/pyproject.toml`: `Django==6.1.1`, `strawberry-graphql-django==0.87.1`, `celery[redis]==5.6.3`. Rewrote the `cryptography` comment's cross-reference (it previously said the other three were "still open ranges," now stale) and added a shared comment above the dependency list explaining the widened scope and the two-source CVE-check method for all three.
  4. Updated `.github/dependabot.yml`'s `pip` entry comment: `versioning-strategy: increase` was originally framed as a partial mitigation for the three still-open-range deps; now all four are exact pins, so the comment is rewritten to reflect that its role is keeping already-safe pins current, not covering an unknown-version gap that no longer exists.
  5. Reinstalled the venv against all four pins and re-ran the full verification chain.
- Verifier executed: `pip show` (resolved versions), `gh api /advisories?...` + `api.osv.dev/v1/query` (CVE cross-check, both sources, for each of the 3 new pins), `python3 -c "import tomllib; ..."` (pyproject.toml re-parse), `python3 -c "import yaml; ..."` (dependabot.yml re-parse), `pip install -e ".[dev]"`, `manage.py check`, `manage.py makemigrations --check --noinput`, `pytest tests -q`
- Result: PASS on all — TOML/YAML valid, all four packages resolve cleanly with no conflicts (`Django 6.1.1`, `strawberry-graphql-django 0.87.1`, `celery 5.6.3`, `cryptography 50.0.1`), Django checks clean, full test suite **554 passed, 3 skipped, 0 failed** (identical to every prior run — no regression from pinning three more direct dependencies)
- New evidence: this is the first point in the ticket where the automation mechanism is closed for **all four** direct pip dependencies, not `cryptography` alone — matching the user's explicit decision not to accept a partial fix
- Decision: iterate (confirm test suite result, close follow-up ticket 17tnw2az0kw, update PR/ClickUp framing, re-dispatch all four reviewers against the new head)

### Iteration 11

- Target criterion: C-006 (re-confirm diff scope), C-007 (reset to reflect a fresh review round), C-011 (close out)
- Change or investigation: committed (`1b91394`), pushed; closed ClickUp 17tnw2az0kw with a comment linking back to PR #110 and the exact commit, moved it to Code Review rather than leaving it open; rewrote PR #110's description end-to-end to reflect both revisions (S-1's exact-pin fix, then the four-dependency widening); posted a widened-scope summary comment on the PR and a matching comment on ClickUp 17tnw2az07j; re-fetched `origin/main` and re-confirmed diff scope; messaged all four reviewer agents (Cody, Vera, Quinn, Sana) directly, asking each to re-verify against head `1b91394` rather than launching fresh review agents with no context
- Verifier executed: `git diff --stat origin/main...HEAD`, `git rev-list --count` both directions
- Result: PASS — still exactly the same 3 files (`pyproject.toml`, `dependabot.yml`, this Goal Contract), 7 commits ahead / 0 behind `origin/main`
- New evidence: C-007 correctly remains `PENDING` — a prior round's clean sign-off does not carry over automatically to a materially changed diff; each reviewer needs to look at the actual new head, which is why they were re-dispatched rather than assumed still-clean
- Decision: iterate (await all four reviewers' responses to the widened diff; do not claim VERIFIED_COMPLETE until each has confirmed against `1b91394` or later)

### Iteration 12

- Target criterion: C-008 (investigate an apparent CI failure before reacting to it)
- Hypothesis: `gh pr checks 110` showed `api (django)` failed on run `36285608277` (head `1b91394`) — before treating this as a real regression, confirm what actually happened per `superpowers:systematic-debugging` (find root cause before proposing fixes)
- Change or investigation: pulled the actual job log (`gh run view --job 108525797027 --log`) rather than reacting to the summary. Found: install succeeded, `Django==6.1.1`/`celery-5.6.3`/`cryptography-50.0.1`/`strawberry-graphql-django-0.87.1` all installed cleanly; `manage.py check` and `makemigrations --check` both passed; `pytest tests -q` was 25% through (`........ [25%]`) when the log shows `##[error]The operation was canceled.` — not a test assertion failure. Checked `gh run list` for the branch: run `36285608277`'s overall conclusion is `cancelled`, and a newer run `36285797641` started 2 minutes later for the next push (`5ba81a3`, the Goal Contract iteration-11 commit). This matches `ci.yml`'s `cancel-in-progress` concurrency group — pushing a follow-up commit before the prior run's tests finished cancelled it mid-suite. Not a regression from the four-dependency pin; a race I caused by pushing two commits close together.
- Verifier executed: `gh run view --job <id> --log`, `gh run list --branch ... --limit 10`
- Result: confirmed self-inflicted CI cancellation, not a test failure. Watching the superseding run (`36285797641`) for the real, uncancelled signal.
- New evidence: a `cancelled` conclusion in `gh pr checks`'s summary view can render identically to a failure at a glance (an `X`) — worth remembering not to react to the glyph without reading the actual job log first
- Decision: iterate (wait for run `36285797641` to complete; that is the real CI result for this head)

### Iteration 13

- Target criterion: C-008 (confirm real, uncancelled CI result)
- Change or investigation: watched run `36285797641` (triggered by `5ba81a3`, the current head) to completion
- Verifier executed: `gh pr checks 110`
- Result: PASS — `api (django)` pass (3m13s, uncancelled), `marketing (vue spa)` pass (1m36s), `detect changed areas` pass, `workflows (actionlint+permissions)` pass. Everything else correctly `skipping`. This confirms Iteration 12's diagnosis: the prior "failure" was purely the cancellation race, not a real break from the four-dependency widening.
- New evidence: none beyond confirming green; C-008 stands
- Decision: iterate (await the four reviewers' fresh confirmations against `5ba81a3`; hold further pushes until each has had a chance to review the current head, to avoid re-triggering the same cancellation race)

### Iteration 14

- Target criterion: C-016 (new)
- Hypothesis: Vera's second-pass performance review (routed to security/devops rather than a performance finding) identified that `strawberry-graphql` — imported directly in `graphql/admin_schema.py`, `graphql/account_schema.py`, and `graphql/views.py` (whose `GraphQLView` every request goes through) — is never declared in `pyproject.toml` at all, only pulled in transitively via `strawberry-graphql-django`'s own unbounded `strawberry-graphql>=0.310.1` requirement. If true, this is the same undeclared/unknown-installed-version exposure the rest of this ticket has been closing, just one level removed (undeclared rather than merely ranged), and per the same user decision (no interim gaps), it belongs in this same PR.
- Change or investigation:
  1. Independently verified before acting: `grep -rn "^import strawberry\|^from strawberry"` across `selahcue_api/` — confirmed the three import sites Vera named. `grep strawberry pyproject.toml` — confirmed `strawberry-graphql` (as opposed to `strawberry-graphql-django`) does not appear as a declared dependency anywhere.
  2. Checked the CVE claim from two independent sources, same method as every other pin in this ticket: OSV.dev (`api.osv.dev/v1/query`, package `strawberry-graphql`) returned 14 records (7 unique GHSA IDs); GitHub Advisory Database (`gh api /advisories?ecosystem=pip&affects=strawberry-graphql`) independently returned 7 — cross-confirmed. Wrote a range-matching script against both: highest ceiling in either source is `<=0.315.6` / fixed `0.315.7` (two advisories share this ceiling: GHSA-fr49-mhgj-crfc, GHSA-qfwv-87qj-98xq). Confirmed PyPI's actual latest release is `0.327.7` (matches what CI/local already resolve), comfortably above every ceiling.
  3. Declared `strawberry-graphql==0.327.7` directly in `implementation/api/pyproject.toml`, with a comment explaining why an undeclared transitive dependency is the same class of exposure as an open range.
  4. Also applied Vera's non-blocking wording nit on `.github/dependabot.yml`: the comment explaining why `pip`/`npm`/`pub` are left ungrouped wrongly said "each edits an independent lockfile" — false for `pip` specifically (no pip lockfile exists at all, which is this entire ticket's premise). Corrected to state the real reason: all three only ever trigger Ubuntu-only jobs (confirmed `flutter controller`'s `runs-on: ubuntu-latest` in `ci.yml` directly), so there's no macOS-capacity or rebase-cascade risk to guard against the way `cargo`/`github-actions` have.
  5. Reinstalled the venv and re-ran the full verification chain.
- Verifier executed: `grep` (import sites, pyproject.toml declarations), `gh api /advisories?...` + `api.osv.dev/v1/query` (two-source CVE cross-check), `curl pypi.org/pypi/strawberry-graphql/json` (latest-release confirmation), `python3 -c "import tomllib; ..."` / `import yaml` (re-parse both files), `pip install -e ".[dev]"`, `manage.py check`, `manage.py makemigrations --check --noinput`, `pytest tests -q`
- Result: PASS on all — TOML/YAML valid, `strawberry-graphql==0.327.7` resolves with no conflicts alongside the other four pins, Django checks clean, full test suite **554 passed, 3 skipped, 0 failed** (identical to every prior run)
- New evidence: this closes a real gap in the PR's own claim ("every dependency's installed version is now knowable") that would otherwise have been false — Vera found it by checking the claim against the actual codebase rather than only the manifest, which is exactly the kind of check this ticket's own standard demands
- Decision: iterate (confirm test suite, commit, push, notify Vera + Sana, re-request review)

### Iteration 15

- Target criterion: C-017 (new), C-018 (new), C-011 (rework again)
- Hypothesis: Sana's second security pass (finding S-5, against head `bdc78c4`, independently corroborated by Quinn) found that closing 17tnw2az0kw as fully resolved was premature — the PR's "no gap remains" framing overclaims once dev dependencies and the wider transitive graph are counted, and there is one concrete, currently-live, unpatched CVE (pytest) reachable through this repo's own version cap
- Change or investigation:
  1. Independently re-verified before acting: `git log --format='%H %ai %s' bd3ebf8 -1` — confirmed Sana's other catch, a timeline arithmetic error of my own: `bd3ebf8` was authored `2026-09-26T23:11:13+01:00`, which converts to `22:11:13Z` UTC (subtract the `+01:00` offset), not the `21:11:13Z` an earlier draft of the Iteration 8/9 retraction wrongly stated. Corrected both occurrences; the underlying conclusion (the alert closed hours before either time) is unaffected. (A further correction followed in Iteration 16: the fix for this itself mistranscribed the local time as `22:11:13+01:00` instead of the actual `23:11:13+01:00` — same UTC value, wrong displayed local time — caught by Sana's next pass and fixed for real this time, cross-checked three independent ways.)
  2. Checked `pytest`'s advisory data directly: `gh api /advisories?ecosystem=pip&affects=pytest` — exactly 1 advisory, GHSA-6w46-j5rx-g56g/CVE-2025-71176, medium, "vulnerable tmpdir handling," range `<9.0.3`, fixed `9.0.3`. Confirmed via `pip show pytest` that the declared `pytest>=8,<9` resolves to `8.4.2` — squarely inside the affected range, and the `<9` cap makes `9.0.3` unreachable by any routine Dependabot update. Checked PyPI: actual latest is `9.1.1`; checked pytest-django's own declared requirement (`pytest>=7.0.0`, no upper bound) — compatible. Read the pytest 8→9 changelog for breaking changes relevant to Django/pytest-django usage — found none that apply to this project's actual usage (ini-options key renames are internal API, not file-format changes; Python 3.9 drop is irrelevant at 3.12+).
  3. Checked `psycopg` and `pytest-django` for advisories (0 each) and confirmed independently that `psycopg` is genuinely absent from `pyproject.toml` — installed via its own `>=3.2,<4` range directly in `.github/workflows/ci.yml`'s `api` job and this crate's `Dockerfile`, per an existing design-rationale comment ("psycopg is not a project dependency — local dev and a bare pytest stay on SQLite"). This is a deliberate, previously-documented architectural choice, not an oversight — reversing it is a separate, larger decision than this ticket's scope, so it is recorded as an open item rather than force-fixed.
  4. Bumped `pytest>=8,<9` / `pytest-django>=4.11,<5` to exact pins `pytest==9.1.1` / `pytest-django==4.14.0` in `implementation/api/pyproject.toml`, with the CVE/compatibility rationale recorded in a comment.
  5. Corrected every overclaiming statement found: the `pyproject.toml` comment that said a lockfile "is no longer a security gap," and `.github/dependabot.yml`'s comment that said "every dependency's exact installed version is now knowable" — both rewritten to precisely scope what's true (declared + directly-imported packages) versus what remains open (~30 transitive packages, `psycopg`).
  6. Reopened ClickUp 17tnw2az0kw: posted a comment explaining why the earlier closure was premature, rewrote its acceptance criteria to reflect the actual remaining scope (a real lockfile, a `psycopg` decision), and moved its status back to Planning/Todo from Code Review.
  7. Reinstalled the venv against the pytest 9 upgrade and re-ran the full verification chain.
- Verifier executed: `git log` (timestamp re-check), `gh api /advisories?...` ×2 (pytest, psycopg), `curl pypi.org/pypi/pytest/json` + `.../pytest-django/json`, WebFetch (pytest changelog), `python3 -c "import tomllib; ..."` / `import yaml` (re-parse both files), `pip install -e ".[dev]"`, `manage.py check`, `manage.py makemigrations --check --noinput`, `pytest tests -q`
- Result: PASS on all — TOML/YAML valid, `pytest==9.1.1`/`pytest-django==4.14.0` resolve with no conflicts, Django checks clean, full test suite **554 passed, 3 skipped, 0 failed** under the pytest 9 upgrade — identical to every prior run, confirming the major-version bump introduced no regression for this project's actual usage
- New evidence: two independent reviewers (Sana, then Quinn corroborating) caught a real overclaiming gap that neither I nor the first three reviewers (Cody, Vera on her first pass, Quinn on her first pass) had surfaced — the review pipeline is doing exactly what it's for
- Decision: iterate (commit, push, rewrite PR description again, notify all four reviewers of the new head, do not claim VERIFIED_COMPLETE until Sana and Quinn both confirm S-5 is actually closed — not just the two concrete items, but the honesty of the remaining-scope framing)

### Iteration 16

- Target criterion: C-017, C-018 (evidence completion)
- Change or investigation: committed (`1543d74`), pushed; rewrote PR #110's description a third time with an explicit "what this does not close" section; posted remediation summaries to the PR and ClickUp 17tnw2az07j; messaged all four reviewer agents directly asking for re-verification against `1543d74`
- Verifier executed: `gh pr checks 110`; CI watch launched for the triggered run
- Result: PASS — `gh pr checks 110` on head `1543d74`: `api (django)` pass (3m57s), `marketing (vue spa)` pass (1m34s), `detect changed areas` pass, `workflows (actionlint+permissions)` pass, `.github/dependabot.yml` (GitHub-native validator) pass. Everything else correctly `skipping`. All four reviewers re-dispatched, responses pending.
- Decision: iterate (await all four reviewers' responses; this is the third round to find something real, so no assumption of a clean pass this time either)

### Iteration 17

- Target criterion: C-019 (new), C-018 (rework — count language and a second timestamp error)
- Hypothesis: Vera (third performance pass) and Sana (fourth security pass) independently found the same finding (S-6): the pyproject.toml/dependabot.yml comment claiming "every package this app's own code imports directly is pinned" was still false — `graphql/errors.py` imports `graphql-core`, `graphql/views.py` imports `cross-web`, neither declared. Sana also caught two more precision errors: (a) the "7 advisories" claim for `strawberry-graphql`'s permitted range conflated the package's total advisory count with the subset actually affecting the specific floor; (b) the retraction's "corrected" timestamp fixed the UTC value but introduced a NEW error in the displayed local time (`22:11:13+01:00` instead of the actual `23:11:13+01:00`).
- Change or investigation:
  1. Independently verified before acting: `grep` confirmed both import sites; `gh api /advisories?ecosystem=pip&affects=graphql-core` and `...&affects=cross-web` — 0 advisories each; OSV.dev cross-check — 0 each too; `curl pypi.org` — both resolved versions (`3.2.12`, `0.7.0`) are each package's actual latest release.
  2. Declared and pinned `graphql-core==3.2.12` and `cross-web==0.7.0` in `implementation/api/pyproject.toml`.
  3. Went further than a targeted re-check this time: ran `grep -rhoE '^(import|from) [a-zA-Z_]+' selahcue_api/` across the **entire** app (not just `graphql/`), cross-referenced every result against stdlib and the dependency list. Confirms exhaustively — not by spot-check — that every third-party top-level import now has a matching exact pin. Recorded this method directly in the pyproject.toml comment so the claim is falsifiable the same way in the future.
  4. Recomputed the `strawberry-graphql` advisory-range claim precisely with a script (not mental arithmetic, given the two arithmetic errors already caught this session): 7 total unique GHSA advisories exist for the package; exactly 5 of them affect the specific unbounded `>=0.310.1` floor. Corrected the "7 advisories" wording to state this distinction.
  5. Re-verified the commit timestamp a third time, independently, via three different git invocations (`%ai`, `--date=iso-strict`, `--date=iso-strict` under `TZ=UTC`) — all agree: `bd3ebf8` was authored `2026-09-26T23:11:13+01:00` (not `22:11:13+01:00` as the prior "fix" wrongly stated). Corrected the local-time figure in all three places it appears; the UTC value (`22:11:13Z`) and every conclusion drawn from it were already right and remain unchanged.
  6. Softened the "~30 further transitive packages" approximation (an inherently unstable number, already once corrected) to a description that doesn't depend on an exact, easily-stale count.
  7. Reinstalled and re-ran the full verification chain.
- Verifier executed: `grep` (exhaustive import audit), `gh api /advisories?...` ×2, `api.osv.dev/v1/query` ×2, `curl pypi.org` ×2, three independent `git log`/`git` date invocations, custom OSV range-matching script (floor-specific, not just total-count), `python3 -c "import tomllib; ..."` / `import yaml` (re-parse), `pip install -e ".[dev]"`, `manage.py check`, `manage.py makemigrations --check --noinput`, `pytest tests -q`
- Result: PASS — TOML/YAML valid, `graphql-core==3.2.12`/`cross-web==0.7.0` resolve with no conflicts, Django checks clean, full test suite **554 passed, 3 skipped, 0 failed** (identical to every prior run); exhaustive import-audit found no further gaps beyond the two just fixed
- New evidence: two independent reviewers found the *same* gap in the *same* round (Vera first, Sana corroborating and adding two precision corrections on top) — strong signal this specific class of finding (undeclared-but-imported packages) is now genuinely exhausted, verified by the whole-app grep rather than assumed
- Decision: iterate (confirm test suite, commit, push, notify Vera + Sana of the fix, ask for one more confirmation pass)

## Risks and rollback

- Risks: a floor bump could theoretically break something not caught by the test suite (e.g. an environment-specific OpenSSL wheel issue) — mitigated by running the full suite, not a subset, and reviewing the upstream changelog for the crossed range
- Risks: dependabot.yml labels reference labels that didn't previously exist in the repo — mitigated by creating them (`dependencies`, `rust`, `api`, `marketing`, `mobile`, `github-actions`) via `gh label create`
- Rollback or recovery: revert the two file changes (`pyproject.toml`, `.github/dependabot.yml`) via `git revert`; no data/infrastructure state is touched, so rollback is a plain code revert with no migration or runtime impact

## Pause and escalation conditions

- If the test suite reveals a genuine break from the `cryptography` bump that isn't a trivial fix — escalate to Backend Engineer (Kenji), do not silently patch around it
- If a reviewer finds the chosen floor still overlaps a range not present in the captured advisory payload — treat as new evidence, re-derive the floor, do not dismiss
- Merging the PR is explicitly out of scope for this goal — GATE_REVIEW/handoff to the user, not `VERIFIED_COMPLETE` implying merge

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2az07j-cryptography-dependabot.md`
- Validator result: (recorded after first full pass)
- Independent verification result: (recorded after reviewer gate)
- Terminal state: (recorded at handoff)
- Remaining failed or blocked criteria: (recorded at handoff)
- ClickUp final evidence comment: (link recorded at handoff)
