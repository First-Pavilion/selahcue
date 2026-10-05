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
- Updated: 2026-10-05
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

- `origin/main` is `c99ad4c7`. A1 (`scripts/build_translation_catalog.py`, PR 181) is NOT on `main`, so this branch is cut from A1's head `940e262d` and its PR says so.
- The owner supplied: Space `bible-translations`, region `sfo3`, CDN endpoint `https://bible-translations.sfo3.cdn.digitaloceanspaces.com`, origin `https://bible-translations.sfo3.digitaloceanspaces.com`, S3 endpoint `https://sfo3.digitaloceanspaces.com`. A separate installers bucket exists and is never touched.
- This machine has no `doctl`, no `aws`, no S3 profile and no Spaces credentials in its environment. `gh` is logged in as the repo's only collaborator, who has admin on `First-Pavilion/selahcue` (public repository, free organisation plan).
- Before this work the repository had no environments, no variables and no secrets.
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
- `.github/scripts/check_workflows.py` (edit: check 4, protected-environment workflows, with self-test cases)
- `Makefile` (edit: one self-test line in `ci`)
- this contract
- outside the repository: the GitHub environment `translations-publish` and four repository variables (see the evidence)

### Non-goals

- `.github/workflows/ci.yml` and `scripts/ci_disk.sh` (another ticket's files); the CI step that runs the publish self-test is a follow-up
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
| C-002 | yes | The workflow is manual, ubuntu-only, `contents: read`, has secrets only in the two upload steps' `env:` of the environment job, and uses only `actions/*` | `actionlint .github/workflows/publish-translations.yml`; `python3 .github/scripts/check_workflows.py --self-test` then without the flag | exit 0; 46 cases pass; `5 workflow(s), 17 job(s) OK`; check 4 rejects a `push` trigger added to a copy | Iteration 1 | PASS |
| C-003 | yes | A dry run on GitHub from this branch builds twice byte-identically, passes both self-tests and the positive control, prints the entries, uploads nothing and the publish job is skipped | `gh workflow run publish-translations.yml --ref ci/17tnw2b2jqd-publish-translations -f only=BSB -f dry_run=true`, then `gh run view` | run succeeds; `publish` job skipped; entries printed | run URL on the PR and ClickUp | PENDING |
| C-004 | yes | The GitHub environment exists with the owner as required reviewer, restricted to `main`, and the four non-secret variables are set; no secret is set by this role | `gh api repos/First-Pavilion/selahcue/environments/translations-publish`; `.../deployment-branch-policies`; `gh api repos/First-Pavilion/selahcue/actions/variables`; `.../environments/translations-publish/secrets` | reviewer is the owner, policy `branch:main`, four variables, zero secrets | Iteration 1 | PASS |
| C-005 | yes | What can be checked about the Space from outside is checked and reported: not listable, not writable, CDN answering, access findings | anonymous `curl` of the bucket root, the prefix, a PUT, an unknown key, the CDN hostname | 403, 403, 403, 403; CDN answers with `x-do-cdn-uuid` | Iteration 1; ClickUp comment | PASS |
| C-006 | yes | The Space's own settings are reported from the control panel: default ACL private, listing restricted, no lifecycle rule under `translations/`, CDN TTL and custom domain | the owner's control panel or `doctl`/an authenticated S3 profile | each setting stated | none available to this role | BLOCKED |
| C-007 | yes | A real publish is proven: after upload, each object downloaded anonymously through the CDN URL has the build's sha256, a re-run changes nothing, the key can write only this Space, no pending translation is in the bucket | the workflow's own read-back, run with `dry_run=false` after the owner says "publish BSB now" | verify steps green; evidence attached | none yet: no key, no go | BLOCKED |
| C-008 | yes | A runbook explains how to publish, add a translation, roll back, rotate the key, set up the key, and what a CDN switch changes | read `docs/ops/TRANSLATIONS-PUBLISH.md` | all six present | the file | PASS |
| C-009 | yes | The diff changes only the files listed under In scope, relative to A1's head | `git diff --name-only origin/feat/17tnw2b2jfy-translation-mirror-pipeline...HEAD` | the seven paths listed under In scope | PR description | PENDING |
| C-010 | yes | The branch contains `origin/main` and a Draft PR is open against `main`, saying it carries A1's commits until PR 181 merges | `git merge-base --is-ancestor origin/main HEAD`; `gh pr view` | exit 0; Draft; base `main` | PR link | PENDING |
| C-011 | yes | Independent review passed: Cody, Shadow and Quinn each reviewed at the head SHA and every blocking finding is fixed (dispatched by the coordinator) | review round report page linked on the PR | zero open blocking findings | report page URL | PENDING |
| C-012 | no | Performance review (Vera) | not applicable: a manual job that moves about 1.3 MB; it ships nothing to users | recorded as not applicable | this row | NOT_APPLICABLE |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-001, C-002, C-004, C-005 and C-008 run from the worktree; C-003 on GitHub from the pushed branch.
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
- Remaining failed or blocked criteria: C-003, C-006, C-007, C-009, C-010, C-011
- ClickUp final evidence comment: pending
