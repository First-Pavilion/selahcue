# Publishing the downloadable Bible translations (runbook)

ClickUp: 17tnw2b2jqd (A7). Story: 17tnw2b2jfv. Workflow: `.github/workflows/publish-translations.yml`.
Script: `scripts/publish_translations.py`. Build half: `scripts/build_translation_catalog.py` (A1).

The app downloads extra Bibles from a SelahCue-hosted mirror and checks each file against a SHA-256 that is
compiled into the app. So the bytes in the Space must be exactly the bytes a build produced. One workflow builds
and uploads in the same run, then reads every file back from the public URL and compares it.

## What lives where

- **The Space**: DigitalOcean Spaces, bucket `bible-translations`, region `sfo3`. It is separate from the installers
  bucket, which this workflow never names, lists or writes.
- **The public base URL (`TRANSLATIONS_BASE_URL`)**: the CDN endpoint `https://bible-translations.sfo3.cdn.digitaloceanspaces.com`.
  This is what the app downloads from. It is recorded in `catalog.json`, so it ends up in every installed app.
- **The origin URL (`TRANSLATIONS_ORIGIN_URL`, optional)**: `https://bible-translations.sfo3.digitaloceanspaces.com`.
  When set, every object is also read back from here first.
- **The bucket and S3 endpoint (`TRANSLATIONS_BUCKET`, `TRANSLATIONS_ENDPOINT`)**: `bible-translations` and
  `https://sfo3.digitaloceanspaces.com`, used only for uploads.
- **Where the four settings are defined, and why twice.** They are not secret. The `publish` job reads them from the
  **environment** `translations-publish`, which only an administrator can change (an environment variable overrides a
  repository variable of the same name for a job that uses the environment). A write-access account can change
  repository variables, so nothing the publish job relies on is left only at that level:
  - `TRANSLATIONS_BUCKET` and `TRANSLATIONS_ENDPOINT` exist at the **environment level only**.
  - `TRANSLATIONS_BASE_URL` and `TRANSLATIONS_ORIGIN_URL` exist at **both levels**, because the `build` job has no
    environment (so a dry run needs no approval) and still needs them. If the two levels differ, the build records one
    `base_url` in `catalog.json` and the publish job holds the other, and the publish job **refuses at "Re-check the
    release"** with the `base_url` message. That is how a repository-level tamper is caught.
  - Independently, the script refuses a bucket, region and base URL that disagree about which Space this is, whenever the
    base URL is a DigitalOcean host (`<bucket>.<region>[.cdn].digitaloceanspaces.com`). A custom hostname cannot be checked
    that way.
- **The access key**: two secrets, `SPACES_ACCESS_KEY_ID` and `SPACES_SECRET_ACCESS_KEY`, in the GitHub environment
  `translations-publish` (set by the owner on 2026-10-05, 09:02 and 09:03 UTC). They exist nowhere else and are used only by
  the two upload steps. **Never create them as repository secrets**: an environment secret is available only to a job that
  uses the environment (and so only after the approval); a repository secret would be available to any workflow on any branch
  that a write-access account can create, and `check_workflows.py` cannot see which kind a secret is.
- **The environment `translations-publish`**: required reviewer = the owner; deployments allowed from `main` only;
  administrators cannot bypass it; self-review is allowed (one-person owner; turn it off and add a second reviewer the day a
  second maintainer exists).

## The key layout, and why

- `translations/<CODE>/<sha256>.tsv.gz` for each translation (for example `translations/BSB/cc27....tsv.gz`).
- `translations/catalog/<sha256>.json` for each catalogue.

The digest is in the name, so **a published key can never change**. Different bytes means a different key. That is
what lets an older app that pinned an old digest keep working, and it is the only layout that is safe behind a CDN, which
may keep any URL cached for as long as it likes. For the same reason these objects carry
`Cache-Control: public, max-age=31536000, immutable`.

The app's `asset_url` (selahcue-scripture `catalog.rs`) must build `{base_url}/translations/{code}/{sha256}.tsv.gz`.
Today it builds `{base_url}/{file_name}`, so that function changes in the follow-up that sets `base_url` (A2).
The catalogue's `file_name` stays the plain local name (`bsb.tsv.gz`) and, like the app, the publish script refuses a
file name that is a Windows device name (`con`, `prn`, `aux`, `nul`, `com1` to `com9`, `lpt1` to `lpt9`).

Each object is uploaded with `public-read` (the Space's default is private, so nothing else becomes public),
`Content-Type: application/gzip` and **no `Content-Encoding`**. DigitalOcean's own documentation says the CDN may
decompress an object marked `Content-Encoding: gzip` for a client that does not accept gzip, and may compress one that is not
marked when the client does accept it. The app asks for `Accept-Encoding: identity` and hashes the bytes it receives, so the
objects are stored as plain gzip bytes with no encoding header, and the workflow reads them back the same way the app does.

**Only the asset keys are stable between runs.** The catalogue records `translations_csv_sha256` (a digest of eBible's whole
catalogue file) and, per translation, the source zip's digest and update date. So the catalogue's own key changes whenever
eBible changes its catalogue, even when no asset byte changed. Evidence (Verified): the scratch catalogue in A2 (built on
2026-10-04) records `translations_csv_sha256` `33e486e8...`; a build on 2026-10-05 records `fceee8a3...`; BSB's source zip
digest (`b77cc2d5...`), its update date and its asset digest (`cc27e77a...`) are identical in both. That is also why a local
rebuild from a cached eBible catalogue gives a different catalogue key than a fresh run, with the same size.

## One-time setup (owner)

1. **Check the Space in the DigitalOcean control panel** (this runbook cannot see it):
   - File listing is restricted (anonymous requests for the bucket or the `translations/` prefix are refused; checked from
     outside on 2026-10-05 and answered 403, but the panel is the source of truth).
   - No lifecycle rule deletes anything under `translations/`.
   - Versioning: optional. This job never deletes or overwrites, so it adds nothing here.
   - CDN: note whether it is enabled, the edge cache TTL (default 1 hour) and any custom domain or certificate.
   - CORS: not needed (a desktop app, not a browser).
2. **Create a Spaces access key limited to the `bible-translations` bucket**: control panel, Spaces Object Storage, Access Keys,
   Create Access Key, Limited Access, choose that one bucket. DigitalOcean offers exactly two permission levels per bucket,
   **Read** and **Read/Write/Delete**; there is no "Read/Write". Publishing needs the second, so **this key can delete and
   overwrite objects in `bible-translations`** even though this job never does. That is the reason the key is limited to one
   bucket, used only by this workflow's environment, and rotated if it is ever exposed. Do not paste it into chat, a file, a
   ticket or a PR.
3. **Put the two values into the environment** (never as repository secrets). These commands prompt for the value in your own
   terminal, so it never passes through any chat:

   ```
   gh secret set SPACES_ACCESS_KEY_ID --env translations-publish --repo First-Pavilion/selahcue
   gh secret set SPACES_SECRET_ACCESS_KEY --env translations-publish --repo First-Pavilion/selahcue
   ```

   Check the names only (never values): `gh secret list --env translations-publish --repo First-Pavilion/selahcue`, and
   `gh secret list --repo First-Pavilion/selahcue` must NOT show them.
4. **Prove the key reaches only this Space, with a read-only probe** (never a write: a write probe leaves a stray object behind if
   the key turns out not to be limited). In your own terminal, store the key under a throwaway profile (it prompts; use region
   `sfo3`) and ask each bucket to list ONE key (a read; these commands have not been run by the author of this runbook):

   ```
   aws configure --profile translations-probe
   aws s3api list-objects-v2 --bucket bible-translations --max-keys 1 --endpoint-url https://sfo3.digitaloceanspaces.com --profile translations-probe
   aws s3api list-objects-v2 --bucket <installers-bucket> --max-keys 1 --endpoint-url https://sfo3.digitaloceanspaces.com --profile translations-probe
   ```

   The first must succeed. The second must FAIL with a 403 or AccessDenied. If it succeeds, the key is not limited: revoke it
   at once. Afterwards delete the `[translations-probe]` sections from `~/.aws/credentials` and
   `~/.aws/config`. Nothing in the workflow checks the key's scope.
5. **Protect `main`** (before the first real publish). The environment only runs code from `main`, and the approver sees a
   commit; both mean "code someone reviewed" only if `main` itself is controlled. On 2026-10-05, read through the API:
   `main` has no branch protection, and the one ruleset, "Protect Main" (id 22868466), is `enforcement: disabled` (it would
   block only deletion and force-push, not direct pushes). The repository is public, so rulesets are free. Enable that ruleset
   for the default branch and add "Require a pull request before merging" (one approval; you can still merge your own pull
   request), keeping deletion and non-fast-forward blocked. Verify that a direct `git push origin main` from a write-access clone
   is refused. This is a repository setting and the owner's decision; this workflow does not change it.
6. **Confirm the environment's four variables** exist (`gh variable list --env translations-publish --repo First-Pavilion/selahcue`)
   with the values listed above, and that the repository holds only `TRANSLATIONS_BASE_URL` and `TRANSLATIONS_ORIGIN_URL`.

## Run it

**Prerequisite.** A new `workflow_dispatch` workflow cannot be dispatched until its file is on the default branch: before the
pull request merges, `gh workflow run` answers `HTTP 404: workflow publish-translations.yml not found on the default branch`.

**The order for the first publish (do not skip a step):**

1. The owner protects `main` (setup step 5).
2. Dry run from `main`: `-f dry_run=true`. It needs no secret and no approval.
3. `dry_run=false` from a branch that is NOT `main`: it must be **refused**. The environment's branch policy stops the `publish`
   job before any step runs; the workflow's own first step would stop it a second time. Do this only now, with the secrets in
   place, to see the refusal live.
4. `dry_run=false` from `main`, with the owner's "publish BSB now", and approve it.

**Rehearse (dry run; any branch once the file is on `main`; no secrets; uploads nothing):**

```
gh workflow run publish-translations.yml --repo First-Pavilion/selahcue --ref main -f only=BSB -f dry_run=true
```

It runs both self-tests, the positive control against the five bundled Bibles, builds twice and requires the two builds to
be byte-identical, checks every file against `catalog.json`, and prints the exact entries (sha256, size, verse counts, object
key and public URL). The artifact `translations-release-<run id>` holds `out/` (the files and `catalog.json`) and
`report/` (`plan.json`, `catalog.app.json`, `summary.md`). To fetch it:

```
gh run download RUN_ID --repo First-Pavilion/selahcue -n translations-release-RUN_ID
```

**Publish for real (only when the owner has said so; from `main` only):**

```
gh workflow run publish-translations.yml --repo First-Pavilion/selahcue --ref main -f only=BSB -f dry_run=false
```

**Approver checklist** (the approval dialog shows the ref and commit; the `build` job's summary shows the plan). Approve only if
all three hold:

- the run is on `main`, at the commit you expect;
- `dry_run` is false;
- the `build` job summary names exactly the codes and the digests you intended.

The `publish` job then:

1. re-checks every downloaded file against `catalog.json`;
2. uploads each asset, never overwriting (an existing key must have the same size and MD5, or the run stops);
3. reads every asset back from the origin URL and the CDN URL and compares every byte, the length and the absence of any
   `Content-Encoding`, retrying a bounded number of times (a read that fails part-way counts as a failed attempt) and then
   failing closed;
4. uploads the catalogue last, only if every asset is already in the bucket, and reads that back too.

**Read the `note:` lines after the first publish.** A wrong `Content-Type` or `Cache-Control` on read-back is a note, not a
failure, because an existing key can never be rewritten. After the first publish those objects are what they are, so this is
the only chance to catch it: check the log for any `note:` line, and do not publish anything else until it is understood.

**If a run fails, use "Re-run failed jobs", not "Re-run all jobs".** The artifact name carries the run id and an artifact name is
immutable within a run, so a full re-run may fail at the artifact upload with a name conflict (fail-closed, but pointless). The
failed-jobs re-run reuses the attempt-1 artifact and asks for approval again. Every step is idempotent: an object that is already
there with the same bytes is left alone.

Only codes the allowlist marks `legal_review: cleared` can be published. A pending code (Yoruba, Igbo, Hausa until A6) stops
the run at the build, and the publish step refuses it a second time.

## After a publish: what the app needs

The first publish decides the digests. Copy them from the run, not from anyone's local build: gzip bytes can differ
between zlib builds.

1. Take `report/catalog.app.json` from the run's artifact (the same data as `catalog.json`, with non-ASCII characters
   escaped for the repo's non-ASCII scan) into the app's `assets/catalog.json` (A2). Its `base_url` is the CDN URL.
2. Change `asset_url` to the key layout above, with a test that pins it.
3. Release the app. Until then no installed app requests anything.

## Add a translation

1. Add or edit its entry in `scripts/translation_allowlist.json` (licence, `expect_copyright`, `licence_text`, verse counts).
2. Legal review (A6) decides it; only then is `legal_review` set to `cleared` in a reviewed commit.
3. Dry run, then publish: `-f only="BSB NEWCODE"`. Files that already exist are left alone.
4. Update the app's embedded catalogue from the new run, and release the app.

## When a published file is wrong, or must come down

**Never overwrite and never delete as a fix.** Shipped apps pin the old digest and the old URL.

1. Fix the cause (allowlist, converter), then run the workflow again. The corrected file has different bytes, so it gets a
   new key and the old key still serves the old bytes.
2. Ship an app update whose catalogue names the new digest. Apps that have not updated keep the old, working file.
3. Only a legal takedown justifies removing an object. That is the owner's decision, and it needs all three of these, because
   each alone does not hold:
   - set that translation's `legal_review` back to `pending` in a reviewed commit (the build then refuses the code, so a later
     run cannot republish it);
   - delete the object in the control panel (the access key can delete; do it as the owner, never in the workflow);
   - purge the CDN path (below).

   **Why the first is not optional.** A re-run re-asserts `public-read` on every existing key (`put-object-acl`), so an object an
   operator made private as a takedown becomes public again when its code is run again. A run that does not name the code leaves
   its objects alone, but a later run that does would put it back; only a `pending` code is out of reach of every run.

If two runs of the same inputs give two different asset digests, compare the decompressed text (`gzip -dc file | sha256sum` on
Linux, `gzip -dc file | shasum -a 256` on macOS). A new runner image with a different zlib produces different gzip bytes for the
same text. It is harmless: the new key is new, the old key stays, and the catalogue the app embeds names whichever you chose.

If the **positive control** fails, the build stops and nothing is published. It compares eBible's current USFM with the five
bundled Bibles, so it can fail because eBible re-released WEB or WEBBE, not because of the translation being published. Do not
bypass it. Read its report; if the cause is a legitimate upstream change, the pinned differences live in the converter
(`KNOWN_DIVERGENCE` in `scripts/build_translation_catalog.py`, A1) and changing them is a reviewed change there, not here.

## Rotate the key

1. Create a new limited key for `bible-translations` (setup step 2) and probe its scope (setup step 4).
2. `gh secret set` both secrets again (setup step 3).
3. Run `-f only=BSB -f dry_run=false` again from `main` and approve it. **This does not prove that the new key can write.**
   Every object already exists, so the job calls `head-object` and `put-object-acl public-read` on each one and reads every file
   back; `PutObject` is first exercised when something new is published. So it shows that the new key can read and set ACLs. It
   also re-asserts `public-read` on every published object (see "When a published file is wrong"), and the catalogue may be a NEW
   key, because eBible's catalogue may have changed since the last run (see the key layout section); the asset keys do not
   change.
4. Revoke the old key in the control panel.

## The CDN

- The CDN endpoint answers (checked from outside on 2026-10-05: it resolves, is served through Cloudflare's network, and
  carries an `x-do-cdn-uuid` header). DigitalOcean operates it; a request made from Lagos was answered from an edge in Lagos. The privacy draft
  (L-16, L-34, A6) says files come from DigitalOcean in Frankfurt, which is no longer accurate. The CDN also sets a `__cf_bm`
  cookie on its responses; whether the app's HTTP client stores cookies was not verified here (A6 and A2 should confirm).
- A CDN caches. The workflow reads the origin first, so the CDN is not asked for a key that is not yet readable. If a CDN
  holds a stale 403 or 404 for a path, the verification fails closed with that message. Purge the path and re-run with "Re-run
  failed jobs" (the uploads are idempotent). With `doctl` (find the endpoint's id first; the syntax below is from DigitalOcean's
  reference page and has **not been run** here):

  ```
  doctl compute cdn list
  doctl compute cdn flush <cdn-id> --files "translations/BSB/<sha256>.tsv.gz"
  ```

  DigitalOcean's page writes its examples with a leading slash (`--files /path/to/file`); if the first form purges nothing,
  use `"/translations/BSB/<sha256>.tsv.gz"`. The control panel's purge dialog does the same job.
- **To move to a custom hostname, or to another CDN**: create it, point it at the same Space, then change
  `TRANSLATIONS_BASE_URL` in **both places**, the repository variable (build job) and the environment variable (publish job).
  If they differ the publish job refuses; that is intended. Run the workflow again: the assets keep their keys, and only the
  catalogue changes (it records `base_url`) and gets a new key. **The old base URL must keep working for as long as any shipped
  app contains it**: every installed app has its catalogue's `base_url` compiled in.

## Why this workflow pins actions by commit SHA when the rest of the repository pins tags

This is the one workflow that holds a secret, and its checkout and artifact-download steps run in the same workspace as the steps
that hold the key: an action swapped under a movable tag could edit `scripts/publish_translations.py` and the next step would run
it with the key. The three actions (`actions/checkout` v7.0.1, `actions/upload-artifact` v7.0.1, `actions/download-artifact`
v8.0.1) are pinned by the full commit SHA of those tags (each resolved through the GitHub API on 2026-10-05; all three are plain
tags that point straight at a commit, and the commits show as verified), with the tag in a trailing comment.
`check_workflows.py` refuses any step in this workflow that is not an `actions/*` action pinned by a 40-character SHA. Dependabot
keeps SHA pins current; a bump is a normal reviewed change. Every other workflow holds no secret and keeps tags.

## Known limits and things to check

- Conditional writes (`If-None-Match`) are not documented for Spaces. "Never overwrite" is a read-then-write check, made safe
  by one workflow at a time (the `concurrency` group) and by keys that name their own digest. Nothing else should write here.
- `aws` CLI 2.23 and later add integrity checksums that Spaces rejected from January 2025. The script sets
  `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`.
- The read-back runs from GitHub's datacenter addresses with a script User-Agent. If the CDN treats those differently from a
  user's request, the verify fails closed with an HTTP error; that is unknown until the first run.
- What `check_workflows.py` enforces about this workflow, and what is held only by review, is written at the top of that file
  (check 4).
- `make ci` runs both self-tests, and so does the `rust` job in `ci.yml` (next to the converter's, on Linux and macOS: the fake
  `aws` is a POSIX script).
