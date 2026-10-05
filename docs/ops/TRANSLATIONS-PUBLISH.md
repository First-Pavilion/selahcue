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
  When set, every upload is also read back from here first.
- **The S3 endpoint (`TRANSLATIONS_ENDPOINT`)**: `https://sfo3.digitaloceanspaces.com`, used only for uploads.
- These four are repository **variables** (not secret). They are repository-level, not environment-level, because the
  build job has no environment (so a dry run needs no approval).
- **The access key**: two secrets, `SPACES_ACCESS_KEY_ID` and `SPACES_SECRET_ACCESS_KEY`, in the GitHub environment
  `translations-publish`. They exist nowhere else and are used only by the two upload steps.
- **The environment `translations-publish`**: required reviewer = the owner; deployments allowed from `main` only;
  administrators cannot bypass it.

## The key layout, and why

- `translations/<CODE>/<sha256>.tsv.gz` for each translation (for example `translations/BSB/cc27....tsv.gz`).
- `translations/catalog/<sha256>.json` for each catalogue.

The digest is in the name, so **a published key can never change**. Different bytes means a different key. That is
what lets an older app that pinned an old digest keep working, and it is the only layout that is safe behind a CDN, which
may keep any URL cached for as long as it likes. For the same reason these objects carry
`Cache-Control: public, max-age=31536000, immutable`.

The app's `asset_url` (selahcue-scripture `catalog.rs`) must build `{base_url}/translations/{code}/{sha256}.tsv.gz`.
Today it builds `{base_url}/{file_name}`, so that function changes in the follow-up that sets `base_url` (A2).
The catalogue's `file_name` stays the plain local name (`bsb.tsv.gz`).

Each object is uploaded with `public-read` (the Space's default is private, so nothing else becomes public),
`Content-Type: application/gzip` and **no `Content-Encoding`**. DigitalOcean's own documentation says the CDN may
decompress an object marked `Content-Encoding: gzip` for a client that does not accept gzip, and may compress one that is not
marked when the client does accept it. The app asks for `Accept-Encoding: identity` and hashes the bytes it receives, so the
objects are stored as plain gzip bytes with no encoding header, and the workflow reads them back the same way the app does.

## One-time setup (owner)

1. In the DigitalOcean control panel, check the Space `bible-translations`:
   - File listing is restricted (anonymous requests for the bucket or the `translations/` prefix are refused; this was
     checked from outside and returned 403, but the panel is the source of truth).
   - No lifecycle rule deletes anything under `translations/`.
   - Versioning: optional. This job never deletes or overwrites, so it adds nothing here.
   - CDN: note whether it is enabled, the edge cache TTL (default 1 hour) and any custom domain or certificate.
   - CORS: not needed (a desktop app, not a browser).
2. Create a Spaces access key **limited to the `bible-translations` bucket**: Control panel, Spaces Object Storage, Access Keys,
   Create Access Key, Limited Access, choose that one bucket, permission Read/Write (this job never deletes; use
   Read/Write/Delete only if the panel offers nothing narrower). Use this key only for this workflow. Do not paste it into
   chat, a file, a ticket or a PR.
3. Put the two values into the environment. These commands prompt for the value in your own terminal, so it never passes
   through any chat:

   ```
   gh secret set SPACES_ACCESS_KEY_ID --env translations-publish --repo First-Pavilion/selahcue
   gh secret set SPACES_SECRET_ACCESS_KEY --env translations-publish --repo First-Pavilion/selahcue
   ```

4. Prove the key reaches only this Space: with the key, a write to the installers bucket must be refused (this is
   acceptance criterion 6 of the ticket; run it in your own terminal with that key, never in a workflow).

## Run it

**Rehearse first (dry run; any branch; no secrets; uploads nothing):**

```
gh workflow run publish-translations.yml --repo First-Pavilion/selahcue --ref main -f only=BSB -f dry_run=true
```

It runs both self-tests, the positive control against the five bundled Bibles, builds twice and requires the two builds to
be byte-identical, checks every file against `catalog.json`, and prints the exact entries (sha256, size, verse counts, object
key and public URL). The artifact `translations-release-<run id>` holds `out/` (the files and `catalog.json`) and
`report/` (`plan.json`, `catalog.app.json`, `summary.md`).

**Publish for real (only when the owner has said so; from `main` only):**

```
gh workflow run publish-translations.yml --repo First-Pavilion/selahcue --ref main -f only=BSB -f dry_run=false
```

The `publish` job waits for the reviewer's approval in the Actions tab. After approval it:

1. re-checks every downloaded file against `catalog.json`;
2. uploads each asset, never overwriting (an existing key must have the same size and MD5, or the run stops);
3. reads every asset back from the origin URL and the CDN URL and compares every byte, the length and the absence of any
   `Content-Encoding`, retrying a bounded number of times and then failing closed;
4. uploads the catalogue last, only if every asset is already in the bucket, and reads that back too.

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

## When a published file is wrong

**Never overwrite and never delete.** Shipped apps pin the old digest and the old URL.

1. Fix the cause (allowlist, converter), then run the workflow again. The corrected file has different bytes, so it gets a
   new key and the old key still serves the old bytes.
2. Ship an app update whose catalogue names the new digest. Apps that have not updated keep the old, working file.
3. Only a legal takedown justifies removing an object. That is the owner's decision; purge the CDN path afterwards (below).

If two runs of the same inputs give two different digests, compare the decompressed text (`gzip -dc file | sha256sum`). A new
runner image with a different zlib produces different gzip bytes for the same text. It is harmless: the new key is new, the
old key stays, and the catalogue the app embeds names whichever you chose.

## Rotate the key

1. Create a new limited key for `bible-translations` (setup step 2).
2. `gh secret set` both secrets again (setup step 3).
3. Run `-f only=BSB -f dry_run=false` again and approve it. The objects already exist, so it uploads nothing, but it
   re-checks each key with the new credentials and reads every file back, which proves the new key works.
4. Revoke the old key in the control panel.

## The CDN

- The CDN endpoint answers (checked from outside: it resolves, is served through Cloudflare's network, and carries an
  `x-do-cdn-uuid` header). DigitalOcean operates it; requests were answered from an edge in Lagos. The privacy draft (L-16,
  L-34, A6) says files come from DigitalOcean in Frankfurt, which is no longer accurate.
- A CDN caches. The workflow reads the origin first, so the CDN is not asked for a key that is not yet readable. If a CDN
  holds a stale 403 or 404 for a path, the verification fails closed with that message. Purge the path and re-run (the uploads
  are idempotent): `doctl compute cdn flush <endpoint-id> --files "translations/BSB/<sha256>.tsv.gz"`.
- To move to a custom hostname, or to another CDN: create it, point it at the same Space, change `TRANSLATIONS_BASE_URL`,
  and run the workflow again. The assets keep their keys; only the catalogue changes (it records `base_url`) and gets a new
  key. **The old base URL must keep working for as long as any shipped app contains it**: every installed app has its
  catalogue's `base_url` compiled in.

## Known limits and things to check

- Conditional writes (`If-None-Match`) are not documented for Spaces. "Never overwrite" is a read-then-write check, made safe
  by one workflow at a time (the `concurrency` group) and by keys that name their own digest. Nothing else should write here.
- `aws` CLI 2.23 and later add integrity checksums that Spaces rejected from January 2025. The script sets
  `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`.
- The positive control compares eBible's current USFM with the five bundled Bibles. If eBible re-releases WEB or WEBBE, it
  can fail for a reason that has nothing to do with the translation being published; read the report before editing the pinned
  differences in the converter.
- `make ci` runs both self-tests. The CI workflow (`ci.yml`) does not run `publish_translations.py --self-test` yet: the
  publish workflow runs it, and a follow-up adds the CI step once the CI disk fix lands.
