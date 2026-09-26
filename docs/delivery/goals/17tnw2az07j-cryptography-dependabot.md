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
| C-005 | yes | `.github/dependabot.yml` exists and declares all four ecosystems + github-actions on a weekly schedule | `cat .github/dependabot.yml`; manual review against directories | cargo→/implementation/desktop, pip→/implementation/api, npm→/implementation/marketing, pub→/implementation/mobile/selahcue_controller, github-actions→/, all `interval: weekly` | file content | PASS |
| C-006 | yes | `make ci` is not required/affected by this change (api excluded per repo CLAUDE.md) — no desktop/mobile/marketing manifest touched | `git diff --stat origin/main...HEAD` | Only `implementation/api/pyproject.toml`, `.github/dependabot.yml`, and `docs/delivery/goals/*` changed | diff output | PENDING |
| C-007 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) completed, blocking findings remediated | Reviewer reports, published as Artifact per Operating Contract | No blocking findings outstanding | Artifact URL + ClickUp comment | PENDING |
| C-008 | yes | Draft PR open against `main`, real `gh pr checks` green (or explained if a check is structurally unrelated) | `gh pr checks` against the opened PR number | All applicable checks pass | PR URL + checks output | PENDING |
| C-009 | yes | Honest note recorded that Dependabot's own re-verification cannot be forced; real proof is the next scheduled/security-triggered run | ClickUp comment + PR description text present | Statement present, not a false completion claim | ClickUp comment link | PENDING |

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
