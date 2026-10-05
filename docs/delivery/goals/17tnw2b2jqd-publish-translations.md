# Goal Contract — 17tnw2b2jqd-publish-translations

## Identity

- Goal ID: 17tnw2b2jqd-publish-translations
- Parent goal ID: 17tnw2b2jfv-user-downloaded-translations
- Title: A manual, protected GitHub workflow builds the cleared Bible translations and publishes them to the translations Space under keys that can never change, then proves from the public CDN URL that every byte matches the build
- Role: devops-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b2jqd
- Created: 2026-10-05
- Updated: 2026-10-05 (review round 1 remediation)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Ship the publish half of the translation mirror (A7 of story 17tnw2b2jfv): `.github/workflows/publish-translations.yml`,
`scripts/publish_translations.py` and a runbook. The workflow is `workflow_dispatch` only, dry run by default, ubuntu only.
A real publish runs in the protected environment `translations-publish`, uploads each asset under a key named by its own
SHA-256 (never overwriting), reads each back from the public CDN URL byte for byte, and uploads the catalogue last. Out of
scope: the installers bucket and its job (17tnw0wqj), the app's embedded catalogue and `asset_url` (A2), legal clearance of the
Biblica texts (A6), turning the CDN on or off or giving it a custom domain, and creating the access key.

## Baseline

**Verified** on 2026-10-05:

- At the START of this work (2026-10-05 morning) `origin/main` was `c99ad4c7` and A1 (`scripts/build_translation_catalog.py`, PR 181) was NOT on it, so this branch was cut from A1's head `940e262d` and the PR said it carried A1's commits. Later the same day A1 merged into `main` as `6a05a94d` and PR 184 (CI disk guard, `ci.yml`) as `1ff06ffe`; this branch was brought up to date with `main` at the end of the remediation round (the commit is on the PR).
- The owner supplied: Space `bible-translations`, region `sfo3`, CDN endpoint `https://bible-translations.sfo3.cdn.digitaloceanspaces.com`, origin `https://bible-translations.sfo3.digitaloceanspaces.com`, S3 endpoint `https://sfo3.digitaloceanspaces.com`. A separate installers bucket exists and is never touched.
- This machine has no `doctl`, no `aws`, no S3 profile and no Spaces credentials in its environment. `gh` is logged in as the repo's only collaborator, who has admin on `First-Pavilion/selahcue` (public repository, free organisation plan).
- Before this work the repository had no environments, no variables and no secrets. The owner then set the two environment secrets on `translations-publish` (`SPACES_ACCESS_KEY_ID` at 09:02 UTC and `SPACES_SECRET_ACCESS_KEY` at 09:03 UTC on 2026-10-05; names read with `gh secret list --env`, values never read); there are no repository-level secrets. The key is limited to the `bible-translations` bucket (the owner's statement; not verified by this role).
- From outside (no credentials): the bucket exists; an anonymous GET of the bucket root and of `?prefix=translations/` returns 403 `AccessDenied`; an anonymous PUT is refused with 403; an anonymous GET of an unknown key returns 403.
- The CDN hostname resolves, answers through Cloudflare's network and carries an `x-do-cdn-uuid` header; a control hostname for a bucket that does not exist does not resolve.
- A2's `asset_url` builds `{base_url}/{file_name}` and `validate_file_name` allows no `/` in a name; A2's client sends `Accept-Encoding: identity`, follows redirects by hand over https only, and hashes the bytes it receives.
- DigitalOcean's documentation says the CDN may compress an unmarked object for a client that accepts gzip, and may decompress an object marked `Content-Encoding: gzip` for one that does not.

## Inputs and evidence sources

- ClickUp 17tnw2b2jqd (this task) and its 2026-10-05 owner comments, story 17tnw2b2jfv
- `scripts/build_translation_catalog.py` (A1, docstring and `--help`), `scripts/translation_allowlist.json`, `docs/delivery/goals/17tnw2b2jfy-translation-mirror.md`
- A2 `implementation/desktop/crates/selahcue-scripture/src/catalog.rs` and `download.rs` at `a17be531` (PR 188), read only
- DigitalOcean Spaces documentation (CDN, object metadata, S3 compatibility, access keys) and the AWS CLI checksum incident notice

## Scope

### In scope

Footprint (new files unless noted):

- `.github/workflows/publish-translations.yml`
- `scripts/publish_translations.py`
- `docs/ops/TRANSLATIONS-PUBLISH.md`
- `.github/scripts/check_workflows.py` (edit: check 4, secrets and protected-environment workflows, with 67 self-test cases)
- `Makefile` (edit: one self-test line in `ci`)
- `.github/workflows/ci.yml` (edit, review round: ONE step running the publish script's self-test, next to the converter's, same `if:`)
- this contract
- outside the repository: the GitHub environment `translations-publish`; its four environment variables (`TRANSLATIONS_BASE_URL`, `TRANSLATIONS_ORIGIN_URL`, `TRANSLATIONS_BUCKET`, `TRANSLATIONS_ENDPOINT`); and two repository variables (`TRANSLATIONS_BASE_URL`, `TRANSLATIONS_ORIGIN_URL`, which the `build` job reads because it has no environment). The repository-level `TRANSLATIONS_BUCKET` and `TRANSLATIONS_ENDPOINT` that were first created were removed in the review round, so a write-access account cannot change them

### Non-goals

- `scripts/ci_disk.sh`, and any other part of `ci.yml` (another ticket's files)
- Any real upload: it needs the owner's access key and the owner's explicit "publish BSB now"
- Changing the Space, its CDN, its access keys or its lifecycle rules; the app

### Constraints

- One ticket, one branch (`ci/17tnw2b2jqd-publish-translations`), one Draft PR against `main`; never merged by this role; no `Co-Authored-By` trailer
- No credential is read, created, rotated, printed or logged by this role; none is in any file, commit, PR or message
- Ubuntu runner only; no third-party action (`actions/*` at a pinned major); Python standard library only; imports at module top

### Assumptions and unknowns

- **Unknown** (needs the control panel): the Space's default object ACL, versioning state, lifecycle rules, CDN edge TTL, any custom domain, and whether an access key limited to one bucket can be created at Read/Write.
- **Unknown**: how the DigitalOcean CDN treats a `.tsv.gz` object stored with `Content-Type: application/gzip` and no `Content-Encoding`. No test object can be uploaded without credentials; the publish run's read-back checks it and fails closed.
- **Assumed**: `aws s3api head-object`, `put-object` and `put-object-acl` work against Spaces with `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` (documented by DigitalOcean's incident notice; not exercised here).
- **Inferred**: one admin collaborator on the repository is the owner, so the environment's required reviewer is that account.

## Dependencies and approvals

- A1 (PR 181) must merge before the first real publish; until it does this PR carries A1's commits.
- The owner creates the Spaces access key and sets the two environment secrets, then says "publish BSB now".
- A6 (legal) before any Yoruba, Igbo or Hausa publish; the workflow refuses them until then.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The publish script's self-test passes offline and covers the guards: no overwrite, catalogue last, byte-for-byte read-back, cleared only | `python3 scripts/publish_translations.py --self-test`; throwaway mutation run over 36 listed guard breaks | exit 0 and `self-test: ok`; 36 of 36 breaks make it fail | ClickUp evidence comment; Iteration 1 | PASS |
| C-002 | yes | The workflow is manual, ubuntu-only, dry run by default, `contents: read`, and its secrets are where the checker says. EXACTLY what `check_workflows.py` check 4 enforces (docstring of that file is the source): in EVERY workflow, a secret other than GITHUB_TOKEN, in any spelling inside an expression (`secrets.X`, `secrets["X"]`, `secrets['X']`, `toJSON(secrets)`, bare `secrets`), may appear only in the `env:` of a step of a job that declares `environment:`, and only in a step whose `run:` calls `publish_translations.py upload`; no job-level `secrets:`. In a workflow with an `environment:` job: `workflow_dispatch` is the only trigger; workflow `permissions` is exactly `contents: read` and no job is wider; a boolean `dry_run` input defaults to true; each environment job names a known protected environment, has exactly `if: ${{ !inputs.dry_run }}`, a concurrency group with `cancel-in-progress` false, and a first step that mentions `refs/heads/main`; every job runs on `ubuntu-*`; every step uses an `actions/*` action pinned by a 40-character SHA. HELD ONLY BY REVIEW: that there are exactly two upload steps and what the scripts do with the key; that the main-only guard really refuses (only that the first step mentions `refs/heads/main`); anything on GitHub rather than in the file (the environment's reviewer and branch policy, that the secrets are environment secrets, that `main` is protected); secrets handed to a reusable workflow; a workflow with no `environment:` job is held only to the first rule | `actionlint .github/workflows/publish-translations.yml .github/workflows/ci.yml`; `python3 .github/scripts/check_workflows.py --self-test` then without the flag; 27 mutated copies of the real workflow run through the checker | exit 0; 101 cases pass; `5 workflow(s), 17 job(s) OK`; 26 of 26 breaks rejected (push, pull_request, schedule and workflow_run triggers; environment removed or renamed; concurrency removed or cancelling; `dry_run` default false or missing; `if` removed or inverted; guard reduced; permissions wider, missing or extra; third-party action; unpinned tag; windows runner; secret in workflow env, job env, `secrets[...]`, `toJSON(secrets)`, another step, the build job, `secrets: inherit`); the 27th (a THIRD upload step that holds the key) is accepted, which is the review-held row above | Iteration 1 and Iteration 3 | PASS |
| C-003 | yes | The build job's steps run green on a real ubuntu runner: both self-tests, the positive control, two byte-identical builds, the plan with the entries printed, the release kept as an artifact, nothing uploaded. A new `workflow_dispatch` file cannot be dispatched before it is on `main` (GitHub answers 404), so a throwaway push-triggered copy of the exact build job was run on this branch and then removed | push the copy, `gh run view 37273822708 --log` | job succeeds in about 30 seconds; `KJV`, `ASV`, `DBY` IDENTICAL, `WEB` 17 and `WEBBE` 20 DIFFERS AS PINNED; `two builds are byte-identical`; BSB sha256 `cc27e77a2a4a...`; artifact `translations-release-37273822708` | run 37273822708 (rehearsal commit `6cf6fe77`); Iteration 2 | PASS |
| C-004 | yes | The GitHub environment exists with the owner as required reviewer, restricted to `main`; the four non-secret settings are defined at the environment level (and the two the `build` job needs also at repository level); this role set no secret (the owner set both on 2026-10-05, 09:02 and 09:03 UTC) | `gh api repos/First-Pavilion/selahcue/environments/translations-publish`; `.../deployment-branch-policies`; `.../environments/translations-publish/variables`; `gh api repos/First-Pavilion/selahcue/actions/variables`; `gh secret list --env translations-publish` and `gh secret list` (names only) | reviewer is the owner, policy `branch:main`, four environment variables, two repository variables, two environment secrets, zero repository secrets | Iterations 1 and 3 | PASS |
| C-005 | yes | What can be checked about the Space from outside is checked and reported: not listable, not writable, CDN answering, access findings | anonymous `curl` of the bucket root, the prefix, a PUT, an unknown key, the CDN hostname | 403, 403, 403, 403; CDN answers with `x-do-cdn-uuid` | Iteration 1; ClickUp comment | PASS |
| C-006 | yes | The Space's own settings are reported from the control panel: default ACL private, listing restricted, no lifecycle rule under `translations/`, CDN TTL and custom domain | the owner's control panel or `doctl`/an authenticated S3 profile | each setting stated | none available to this role | BLOCKED |
| C-007 | yes | A real publish is proven: after upload, each asset downloaded anonymously through the CDN URL has the build's sha256; a second run uploads no object and leaves every ASSET key unchanged (the catalogue key may be new, because the catalogue records eBible's live catalogue digest); the key can reach only this Space (a read-only listing of the installers bucket with it is refused); no pending translation is in the bucket | the workflow's own read-back, run with `dry_run=false` after the owner says "publish BSB now"; the second run's `upload assets: 0 uploaded, N already there` line; the owner's read-only probe (runbook setup step 4) | verify steps green; evidence attached | none yet: the owner's go has not been given | BLOCKED |
| C-008 | yes | A runbook explains how to publish, add a translation, roll back, rotate the key, set up the key, and what a CDN switch changes | read `docs/ops/TRANSLATIONS-PUBLISH.md` | all six present | the file | PASS |
| C-009 | yes | The diff changes only the files listed under In scope, relative to `origin/main` once A1 is on it | `git diff --name-only origin/main...HEAD` | the seven paths listed under In scope (and no rehearsal workflow) | PR description | PENDING |
| C-010 | yes | The branch contains `origin/main` and a Draft PR is open against `main`, saying it carries A1's commits until PR 181 merges | `git merge-base --is-ancestor origin/main HEAD`; `gh pr view` | exit 0; Draft; base `main` | PR link | PENDING |
| C-011 | yes | Independent review passed: Cody, Shadow and Quinn each reviewed at the head SHA and every blocking finding is fixed (dispatched by the coordinator) | review round report page linked on the PR | zero open blocking findings | report page URL | PENDING |
| C-013 | yes | After the PR merges and the owner has protected `main`, the first-publish order holds: (b) the real workflow dispatched from `main` with `dry_run=true` succeeds with the `publish` job skipped; (c) `dry_run=false` from a NON-`main` ref is refused before any publish step runs; (d) only then `dry_run=false` from `main` (that is C-007). Also seen live once: repository-level `TRANSLATIONS_BASE_URL` changed to a wrong value and the publish job stops at "Re-check the release" with the base_url refusal (a rehearsal with the secrets absent, then restored), and "Re-run failed jobs" versus "Re-run all jobs" | `gh workflow run publish-translations.yml --ref main -f only=BSB -f dry_run=true`; then from a branch with `dry_run=false`; `gh run view` | `build` green and `publish` skipped; the branch run refused by the environment | run URLs | PENDING |
| C-012 | no | Performance review (Vera) | not applicable: a manual job that moves about 1.3 MB; it ships nothing to users | recorded as not applicable | this row | NOT_APPLICABLE |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001, C-002, C-004, C-005 and C-008 run from the worktree; C-003 on GitHub from the pushed branch; C-013 only after merge.
- Broader regression verification: `python3 scripts/build_translation_catalog.py --self-test` (A1, unchanged) and the new Makefile line. The Rust and Flutter gates are unaffected by construction (nothing under `implementation/` changes) and are not claimed.
- Independent verifier: Cody, Shadow and Quinn, dispatched by the coordinator, each in their own worktree pinned to the head SHA.
- Required environment: Python 3.9 or later, network for the dry run only. No credentials.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-004, C-005, C-008.
- Hypothesis: the guards can be built and proven without the access key, by faking only `aws` and the network.
- Change or investigation: read A1's converter and A2's `catalog.rs` and `download.rs`; wrote the publish script, workflow, runbook and check 4; created the environment and variables; probed the Space from outside; read DigitalOcean's documentation for the CDN, object metadata and CLI behaviour.
- Verifier executed: `--self-test`; a mutation run (36 guard breaks, 3 survived at first and were closed with new tests: size-only comparison when the ETag is not an MD5, a duplicate code, a put that stored nothing); `actionlint`; `check_workflows.py` self-test and run; a `push` trigger added to a copy of the workflow (rejected); `gh api` read-backs of the environment, branch policy, variables and secrets.
- Result: all pass.
- New evidence: (1) A2's `file_name` cannot contain `/` and `asset_url` is `{base_url}/{file_name}`, so a digest-addressed key needs `asset_url` to change; that is the one-function change A2 anticipated. (2) DigitalOcean's CDN may re-encode a response depending on `Content-Encoding` and `Accept-Encoding`, so the objects are stored with no `Content-Encoding` and the read-back fails on any. (3) The CDN endpoint already answers, so it is on. (4) The build job has no environment, so the settings it needs (the base URL) must be repository variables, not environment variables.
- Decision: iterate (dry run on GitHub, then review).

### Iteration 2

- Target criterion: C-003.
- Hypothesis: the build job runs green on a real ubuntu runner and gives the same bytes as a macOS build.
- Change or investigation: `gh workflow run` answered `HTTP 404: workflow publish-translations.yml not found on the default branch`, so the real file cannot be dispatched before it is on `main`. A push-triggered copy of the exact build job (fixed to BSB and dry run, triggered only by a change to its own file, on this branch only) was committed, run, and removed in the next commit. No protection was weakened and nothing was uploaded.
- Verifier executed: run 37273822708 on commit `6cf6fe77` (ubuntu-latest, 33 seconds), its log, and its artifact.
- Result: PASS. Both self-tests, the positive control (KJV, ASV and Darby identical to the shipped assets; WEB 17 and WEBBE 20 rows differ exactly as pinned), a first build and an offline rebuild that `diff -r` found identical, the plan, and the artifact upload all succeeded.
- New evidence: the Linux runner's BSB asset is 1,308,393 bytes with sha256 `cc27e77a2a4a362d485c5871a1c1302c3091401dc23d5d6eeac9dd416c88f8e9` and 31,086 verses (OT 23,145, NT 7,941): byte-identical to the macOS build and equal to the PLACEHOLDER digest in A2's embedded catalogue. That is one matching sample on one day, not a guarantee: the digests the app pins must still come from the real publish run.
- Decision: iterate (open the Draft PR, request review).

### Iteration 3 (review round 1 at 69cb54b3: Cody APPROVE WITH CONDITIONS, Shadow APPROVE WITH CONDITIONS, Quinn PASS WITH CONDITIONS)

- Target criteria: the four conditions before the first real publish (read errors, SHA pins, admin-controlled settings, check 4), plus the small items.
- Verdicts: nothing blocked the merge. Conditions 1 to 4 had to be fixed before the first real publish.
- Changes:
  - **Read errors in the read-back (Cody 1, Quinn Q1).** The body was read outside the `try`, so a reset, a timeout or an `IncompleteRead` part-way through 1.3 MB escaped as a traceback after one attempt. The read is now inside the `try`; `OSError` and `http.client.HTTPException` are a failed attempt (status 0), retried with the same backoff, in `verify_one` and `gzip_probe` alike (the probe still never fails the run). Tests for six exception types, each before an answer, while reading the body, while reading an error body, once-then-success, and in the probe.
  - **Actions pinned by commit SHA (Shadow C2).** checkout v7.0.1, upload-artifact v7.0.1, download-artifact v8.0.1, each resolved through the GitHub API (lightweight tags, so the tag object is the commit; the floating `v7` and `v8` tags resolve to the same commits; the commits show as verified). Check 4 now refuses any step that is not an `actions/*` action pinned by 40 hex characters.
  - **Settings an administrator controls (Shadow C3).** Chose the environment-level option: the four variables now exist on `translations-publish` (the publish job reads those), the repository-level bucket and endpoint were deleted, and the repository-level base URL and origin URL stay because the `build` job has no environment. A tamper at repository level makes the catalogue's `base_url` differ from the publish job's and is refused at "Re-check the release". Added: the script refuses a bucket, region and base URL that disagree when the base URL is a DigitalOcean host. Reason for not pinning in the script: a CDN switch must stay a settings change, not a code change. Not verified live: that the environment value wins in the job-level `env:` (GitHub's documented precedence; to be seen once in C-013).
  - **Check 4 widened (Cody 2, Shadow R2, Quinn Q3).** See C-002: every spelling of a secret, secrets only in upload-step env of an environment job, no secret in a job without an environment in any workflow, concurrency, `dry_run` default, permissions, the `if`, the main-only guard step, runner and action pinning. 67 self-test cases (101 in all). The docstring and C-002 now say exactly what is enforced and what review holds.
  - **Codes as one argument (Shadow R1).** Every step passes `--only-text="$ONLY"`; the converter, which takes separate arguments, gets them from `publish_translations.py codes`. `parse_codes` refuses any control or non-ASCII character (a newline used to pass `check-inputs` and then publish a subset).
  - **Test gaps (Quinn Q2).** Retry cap (number of fetches), the Cache-Control value as a literal, `put-object-acl` on an existing key (and its failure, and that it re-asserts `public-read`), `KEY_RE` directly, the schema check (now also `true` and `1.0`), the catalogue size cap, the verify time budget, Windows device names (mirroring the app).
  - **Runbook and text (Quinn D, Cody 4, Shadow R3 and R4).** The key permission levels (Read or Read/Write/Delete: the key can delete); a read-only scope probe with commands; the rotation text; the takedown path; the catalogue key can be new; `shasum -a 256`; the `doctl` flush with `cdn list` (syntax from DigitalOcean's reference, not run); the artifact command; the approver checklist; "Re-run failed jobs"; never repository secrets; the first-publish order; protect `main`; the note-lines reminder; why SHA pins here. The CI step for the publish self-test was added to `ci.yml` (PR 184 had merged).
  - **Catalogue key difference (Quinn Q4), explained.** The catalogue records eBible's catalogue-file digest. A2's Oct 4 scratch catalogue has `translations_csv_sha256` `33e486e8...`; the Oct 5 build has `fceee8a3...`; BSB's source zip digest, update date and asset digest are identical in both. My own fresh local build and the CI run both produced catalogue key `96cefb91...`; Quinn's local rebuild from a cached Oct 4 catalogue gave a different key of the same size. Inferred, not read from the artifact (I did not download it).
- Verifier executed: both self-tests; two mutation runs over the publish script (36 earlier guards, 36 of 36; 26 new, 26 of 26 after one test was added for the one survivor); the checker's self-test (101) and 27 mutated copies of the real workflow; `actionlint` on both workflows; the contract validators.
- Result: all pass locally. CI at the merged head is read after the push.
- Decision: iterate (push once, read CI, update the PR and ClickUp, hand back).

## Risks and rollback

- Risks: (1) the CDN may alter a `.tsv.gz` response in a way only a live object shows: the read-back fails closed and nothing points at it; (2) the positive control depends on eBible's current WEB and WEBBE and can fail for reasons unrelated to a publish; (3) a runner image with a different zlib gives different gzip bytes for the same text: a new key, never an overwrite; (4) a CDN may cache a 403 or 404 for a key read before it was public: the runbook says how to purge; (5) an `asset_url` that does not match the key layout makes every download fail until A2 changes it: it is refused before any byte is used.
- Rollback: revert the PR; delete the environment and the four variables (`gh api -X DELETE repos/First-Pavilion/selahcue/environments/translations-publish`, `gh variable delete`). Nothing was uploaded, so the Space is unchanged.

## Pause and escalation conditions

- The owner has not said "publish BSB now": no real upload, whatever else passes.
- A credential would have to be read, created or pasted: stop and hand the owner the command to run in their own terminal.
- The read-back shows the CDN changing the bytes: stop, record the headers, and decide the layout with the owner before any publish.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b2jqd-publish-translations.md --require-complete`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: C-006, C-007, C-009, C-010, C-011, C-013
- ClickUp final evidence comment: pending
