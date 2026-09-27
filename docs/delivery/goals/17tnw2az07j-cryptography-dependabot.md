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
- Maximum iterations: 8
- Independent verification required: yes

## Objective

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
workflow has failed on every attempt since 2026-07-24 (2026-07-24 ×3, 2026-09-05,
2026-09-25) with `dependency_file_not_supported` for `cryptography`, because
`implementation/api/pyproject.toml` declared `cryptography>=43,<47` — an open
range with no lockfile — and Dependabot's log states verbatim: "Dependabot can't
update vulnerable dependencies for projects without a lockfile or pinned version
requirement as the currently installed version of cryptography isn't known."
The same job log's `security-advisories` payload is the authoritative,
machine-emitted list of every affected-version range GitHub's advisory feed
currently has on file for `cryptography`; the highest ceiling among all 24
entries is `>= 44.0.0, < 50.0.0`. **Verified** from PyPI (job log) and the
upstream changelog: latest published release is `50.0.1`, which is itself a
security release (buffer-overflow and certificate name-constraint fixes) on top
of 50.0.0 (Bleichenbacher-oracle fix, CVE-2026-69247).
**Verified**: `.github/dependabot.yml` does not exist in the repo at all — `git
log`/`ls .github/` show only `ci.yml`, `rust-canary.yml`, `windows-installer.yml`;
nothing references `dependabot-action`, confirming the security-update runs seen
are GitHub's native "Dependabot security updates" repo setting, independent of
any config file.

## Inputs and evidence sources

- `gh run view 36129784977 --log-failed` (and the other 4 failed runs) — root cause and advisory payload
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

- Adding a pip lockfile (`uv.lock` or similar) — out of scope for this ticket; flagged as a residual risk/follow-up per the ticket's AC #4 if the version-range approach still isn't sufficient for Dependabot's *routine* (non-security) updates
- Any other dependency bump not required to resolve this CVE-coverage gap
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
| C-001 | yes | `cryptography` floor in `implementation/api/pyproject.toml` excludes every affected-version range from the actual failed job's advisory payload | Manual range check: floor ≥ max(all affected-version ceilings) = 50.0.0 | Floor is `>=50.0.1`, strictly above every ceiling in the 24-entry advisory list | `implementation/api/pyproject.toml` diff + this contract's Baseline section | PASS |
| C-002 | yes | `implementation/api` Django system checks pass with the new version installed | `python manage.py check` (venv with cryptography 50.0.1) | `System check identified no issues (0 silenced).` | command output | PASS |
| C-003 | yes | No missing migrations introduced | `python manage.py makemigrations --check --noinput` | `No changes detected` | command output | PASS |
| C-004 | yes | Full `implementation/api` test suite passes with `cryptography==50.0.1`, including entitlement-signing coverage | `python -m pytest tests -q` | All tests pass, `0` failed | `554 passed, 3 skipped in 169.57s` — see Iteration 2 | PASS |
| C-005 | yes | `.github/dependabot.yml` exists and declares all four ecosystems + github-actions on a weekly schedule, covering every real lockfile | `cat .github/dependabot.yml`; manual review against directories; `find implementation/desktop -iname Cargo.lock` | cargo→3 directories (root + selahcue-operator + selahcue-stt, each with its own tracked Cargo.lock), pip→/implementation/api, npm→/implementation/marketing, pub→/implementation/mobile/selahcue_controller, github-actions→/, all `interval: weekly` | file content + Iteration 5 (Vera's finding + fix) | PASS |
| C-006 | yes | `make ci` is not required/affected by this change (api excluded per repo CLAUDE.md) — no desktop/mobile/marketing manifest touched | `git diff --stat origin/main...HEAD` | Only `implementation/api/pyproject.toml`, `.github/dependabot.yml`, and `docs/delivery/goals/*` changed | diff output: exactly those 3 files, 1 commit ahead / 0 behind `origin/main` | PASS |
| C-007 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) completed, blocking findings remediated | Reviewer reports, published as Artifact per Operating Contract | No blocking findings outstanding | Artifact URL + ClickUp comment | PENDING |
| C-008 | yes | Draft PR open against `main`, real `gh pr checks` green (or explained if a check is structurally unrelated) | `gh pr checks` against the opened PR number | All applicable checks pass | PR #110: `api (django)` pass 4m55s, `marketing (vue spa)` pass 1m42s, `detect changed areas` pass, `workflows (actionlint+permissions)` pass; all others correctly `skipping` (path-filtered, untouched areas); no open `ci-red` alarm | PASS |
| C-009 | yes | Honest note recorded that Dependabot's own re-verification cannot be forced; real proof is the next scheduled/security-triggered run | ClickUp comment + PR description text present | Statement present, not a false completion claim | ClickUp start comment (id 1400430000022688) + PR #110 description, both state this explicitly | PASS |

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
- New evidence: independent, GitHub-computed confirmation that the new floor (`>=50.0.1`) resolves the one cryptography alert this repo actually had open, on top of the manual advisory-range derivation
- Caveat recorded honestly: this is the **Dependabot Alerts** feature, not the **Dependabot Updates** workflow that was failing (`dependency_file_not_supported` is a workflow/updater-job failure mode, separate from alert computation). This does not by itself prove the next scheduled/security-triggered `Dependabot Updates` run will succeed — that remains the un-forceable, un-verifiable-in-session proof per AC #4. Both facts are stated in the PR and ClickUp, not conflated.
- Decision: iterate (proceed to reviewer gate; already dispatched Cody/Vera/Sana/Quinn in parallel against PR #110)

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
