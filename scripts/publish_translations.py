#!/usr/bin/env python3
"""Publish the translation mirror to the translations Space (17tnw2b2jqd, A7).

`scripts/build_translation_catalog.py` (A1) turns the cleared allowlist entries into `<code>.tsv.gz` assets and a
`catalog.json` that pins each asset by SHA-256. This script is the other half: it checks what was built, uploads it
to the DigitalOcean Space, and proves from the PUBLIC URLs that the bytes a user's app will download are the bytes
that were built. It is run by `.github/workflows/publish-translations.yml`, never by hand: gzip bytes can differ
between zlib builds, so the digests the app pins must be those of the files THAT RUN uploaded.

    publish_translations.py check-inputs --only-text="BSB" --base-url URL [--bucket B --endpoint E --origin-url U]
    publish_translations.py fetch-bundled --work-dir DIR
    publish_translations.py plan   --out-dir DIR --only BSB --base-url URL --report-dir DIR
    publish_translations.py upload --stage assets|catalogue --out-dir DIR --only BSB --base-url URL --bucket B --endpoint E
    publish_translations.py verify --stage assets|catalogue --out-dir DIR --only BSB --base-url URL [--origin-url U]
    publish_translations.py --self-test

KEY LAYOUT (decided here; the reasons are the point):

    translations/<CODE>/<sha256>.tsv.gz       one object per asset, named by the digest of its own bytes
    translations/catalog/<sha256>.json        the catalogue, named by the digest of its own bytes

* A published key can never change. The digest is in the key, so "different bytes" means "different key", and an
  older app that pinned the old digest keeps getting the old bytes. Rolling back is shipping a catalogue that
  names the old key; nothing is ever deleted or overwritten.
* The Space has a CDN in front of it. A cache may hold any object for as long as it likes, so the one safe rule is
  that no cached URL ever changes meaning. Content-addressed keys make that true by construction, which is also
  why the objects carry `Cache-Control: public, max-age=31536000, immutable`.
* Re-running with unchanged inputs finds every key already present with the same size and MD5, uploads nothing,
  and still re-verifies every byte through the public URLs.
* `<CODE>` is the catalogue's own upper-case code (`BSB`). `base_url` is only the host (the CDN endpoint today):
  moving to a custom hostname changes `base_url` and nothing else.
* The app's `asset_url` (selahcue-scripture `catalog.rs`) must build `{base_url}/translations/{code}/{sha256}.tsv.gz`
  to match. That is a follow-up on A2; the catalogue's `file_name` stays the plain local file name (`bsb.tsv.gz`).

WHAT IT REFUSES (each is a message, and each stops the run before anything more is written):
an input that does not look right; a catalogue entry that is not `cleared`; a code that was not asked for or is
missing; a file whose size or SHA-256 is not the catalogue's; an extra file in the output folder; a key outside the
layout above; an existing object whose size or MD5 differs from the file (never overwritten); a catalogue upload
while any asset is missing from the bucket; any response from the public URL that is not exactly the built bytes.

OBJECT SETTINGS. `public-read` is set per object, because the Space's default is private and nothing else in the
Space should become public. `Content-Type: application/gzip` and NO `Content-Encoding`: the client asks for
`Accept-Encoding: identity` and hashes the bytes it receives, and DigitalOcean's CDN may decompress an object
that is marked `Content-Encoding: gzip` for a client that does not accept gzip. Verification asks the same way
the client does and fails on any `Content-Encoding`, a redirect, or any byte that differs.

Standard library only (plus the converter next door, for the bundled-Bible download helper).
"""
import argparse
import contextlib
import hashlib
import http.server
import io
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import build_translation_catalog as btc
import strip_bible_headings as sbh

CODE_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,15}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
PLAIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# The ONLY keys this script will ever write or read. A bug elsewhere cannot make it touch another prefix.
KEY_RE = re.compile(r"^translations/(?:catalog/[0-9a-f]{64}\.json|[A-Z][A-Z0-9-]{1,15}/[0-9a-f]{64}\.tsv\.gz)$")
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
ENDPOINT_RE = re.compile(r"^https://([a-z0-9]+)\.digitaloceanspaces\.com$")
BASE_URL_RE = re.compile(r"^https://[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{1,5})?(?:/[A-Za-z0-9._~-]+)*$")

ASSET_CONTENT_TYPE = "application/gzip"
CATALOGUE_CONTENT_TYPE = "application/json"
IMMUTABLE = "public, max-age=31536000, immutable"
ACL = "public-read"
# The limits selahcue-scripture's catalog.rs applies on the way in: an asset or catalogue over these would be refused by
# every app, so it is refused here first.
MAX_ASSET_BYTES = 16 * 1024 * 1024
MAX_CATALOGUE_BYTES = 1024 * 1024
MAX_CODES = 16
SCHEMA = 1
USER_AGENT = "selahcue-translation-publish/1 (+https://selahcue.app)"
HTTP_TIMEOUT = 60
DEFAULT_ATTEMPTS = 6
MAX_BACKOFF = 30
VERIFY_BUDGET_SECONDS = 15 * 60
AWS_TIMEOUT = 300


class Refusal(Exception):
    """A reason to stop. The message names what was wrong and, where there is one, what to do."""


def say(text=""):
    print(text, flush=True)


def summary(text):
    """Append a line to the GitHub job summary when running in Actions; a no-op anywhere else."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path):
    # Only to compare with the ETag the Space reports for a single-part upload; integrity, not security.
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --- inputs ------------------------------------------------------------------------------------
def parse_codes(text):
    codes = (text or "").split()
    if not codes:
        raise Refusal("no translation codes given: name the cleared ones to publish, for example BSB")
    if len(codes) > MAX_CODES:
        raise Refusal(f"more than {MAX_CODES} codes given")
    for code in codes:
        if not CODE_RE.fullmatch(code):
            raise Refusal(f"{code[:40]!r} is not a translation code (upper-case letters, digits and '-', 2 to 16 characters, "
                          f"starting with a letter)")
    if len(set(codes)) != len(codes):
        raise Refusal("a code is listed more than once")
    return codes


def check_base_url(url, what="base URL"):
    if not isinstance(url, str) or not url:
        raise Refusal(f"{what} is not set")
    if len(url) > 512 or not BASE_URL_RE.fullmatch(url):
        raise Refusal(f"{what} {url[:80]!r} must be https, a host and an optional plain path, with no trailing slash, "
                      f"no user name, no query and no fragment")
    return url


def check_endpoint(endpoint):
    m = ENDPOINT_RE.fullmatch(endpoint or "")
    if not m:
        raise Refusal(f"S3 endpoint {(endpoint or '')[:80]!r} must look like https://sfo3.digitaloceanspaces.com "
                      f"(a DigitalOcean Spaces region endpoint, no path)")
    return m.group(1)


def check_bucket(bucket):
    if not BUCKET_RE.fullmatch(bucket or ""):
        raise Refusal(f"bucket name {(bucket or '')[:80]!r} is not a valid Space name")
    return bucket


def object_url(base_url, key):
    return f"{base_url}/{key}"


# --- the release on disk ------------------------------------------------------------------------
def load_release(out_dir, codes, base_url):
    """Read the converter's output folder and return (catalogue entries, objects to publish).

    Everything that would make a publish wrong is checked here, before any object is written: the catalogue
    is exactly what was asked for, every entry is legally cleared, every file is exactly what the catalogue says,
    and nothing else is lying in the folder. The assets come first and the catalogue is the LAST object."""
    out_dir = pathlib.Path(out_dir)
    catalog_path = out_dir / "catalog.json"
    if not catalog_path.is_file() or catalog_path.is_symlink():
        raise Refusal(f"{catalog_path} is missing (the converter writes it beside the assets)")
    raw = catalog_path.read_bytes()
    if len(raw) > MAX_CATALOGUE_BYTES:
        raise Refusal(f"catalog.json is larger than {MAX_CATALOGUE_BYTES} bytes, which no app would read")
    try:
        catalog = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise Refusal(f"catalog.json is not valid UTF-8 JSON ({type(e).__name__})")
    if not isinstance(catalog, dict) or catalog.get("schema") != SCHEMA:
        raise Refusal(f"catalog.json schema is not {SCHEMA}")
    if catalog.get("base_url") != base_url:
        raise Refusal(f"catalog.json records base_url {str(catalog.get('base_url'))[:80]!r} but this run publishes for "
                      f"{base_url!r}: rebuild with --base-url {base_url}")
    entries = catalog.get("translations")
    if not isinstance(entries, list) or not entries:
        raise Refusal("catalog.json lists no translations")

    seen, objects, expected_files, problems = [], [], {"catalog.json"}, []
    for i, e in enumerate(entries):
        where = f"translations[{i}]"
        if not isinstance(e, dict):
            raise Refusal(f"{where} is not an object")
        code = e.get("code")
        if not isinstance(code, str) or not CODE_RE.fullmatch(code):
            raise Refusal(f"{where}.code {str(code)[:40]!r} is not a translation code")
        where = f"{code}"
        if code in seen:
            raise Refusal(f"{where} appears twice in catalog.json")
        seen.append(code)
        if e.get("legal_review") != "cleared":
            raise Refusal(f"{where}: legal_review is {str(e.get('legal_review'))[:20]!r}, not 'cleared'. A translation that "
                          f"has not been through legal review is never published (A6, 17tnw2b2jg3)")
        sha, size, name = e.get("sha256"), e.get("size_bytes"), e.get("file_name")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise Refusal(f"{where}: sha256 is not 64 lowercase hex characters")
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= MAX_ASSET_BYTES:
            raise Refusal(f"{where}: size_bytes {str(size)[:20]} is outside 1..{MAX_ASSET_BYTES}")
        if not isinstance(name, str) or not PLAIN_NAME_RE.fullmatch(name) or ".." in name or not name.endswith(".tsv.gz") \
                or len(name) == len(".tsv.gz"):
            raise Refusal(f"{where}: file_name {str(name)[:40]!r} is not a plain '*.tsv.gz' name")
        verses = e.get("verses")
        if not (isinstance(verses, dict) and all(isinstance(verses.get(k), int) and not isinstance(verses.get(k), bool)
                                                  for k in ("ot", "nt"))):
            raise Refusal(f"{where}: verses.ot and verses.nt must be whole numbers")
        if name in expected_files:
            raise Refusal(f"{where}: file_name {name!r} is used twice")
        expected_files.add(name)
        path = out_dir / name
        if not path.is_file() or path.is_symlink():
            raise Refusal(f"{where}: {path} is missing")
        actual_size = path.stat().st_size
        if actual_size != size:
            problems.append(f"{where}: {name} is {actual_size} bytes but the catalogue says {size}")
        elif sha256_file(path) != sha:
            problems.append(f"{where}: {name} does not hash to the catalogue's sha256 {sha[:12]}..")
        objects.append({"kind": "asset", "code": code, "key": f"translations/{code}/{sha}.tsv.gz", "path": path,
                        "sha256": sha, "size": size, "content_type": ASSET_CONTENT_TYPE, "cache_control": IMMUTABLE,
                        "entry": e})
    if problems:
        raise Refusal("the built files do not match catalog.json:\n  " + "\n  ".join(problems))
    if set(seen) != set(codes):
        raise Refusal(f"catalog.json holds {sorted(seen)} but this run was asked to publish {sorted(codes)}")
    actual = {p.name for p in out_dir.iterdir()}
    if actual != expected_files:
        raise Refusal(f"{out_dir} must hold exactly catalog.json and the listed assets; unexpected: "
                      f"{sorted(actual - expected_files)}, missing: {sorted(expected_files - actual)}")
    cat_sha = sha256_bytes(raw)
    objects.sort(key=lambda o: o["code"])
    objects.append({"kind": "catalogue", "code": None, "key": f"translations/catalog/{cat_sha}.json", "path": catalog_path,
                    "sha256": cat_sha, "size": len(raw), "content_type": CATALOGUE_CONTENT_TYPE,
                    "cache_control": IMMUTABLE, "entry": None})
    for o in objects:
        if not KEY_RE.fullmatch(o["key"]):
            raise Refusal(f"internal: key {o['key']!r} is outside the publishing layout")
    return entries, objects


def stage_objects(objects, stage):
    if stage not in ("assets", "catalogue"):
        raise Refusal(f"unknown stage {stage!r}")
    kind = "asset" if stage == "assets" else "catalogue"
    return [o for o in objects if o["kind"] == kind]


# --- plan ---------------------------------------------------------------------------------------
def cmd_plan(a):
    codes = parse_codes(" ".join(a.only))
    base_url = check_base_url(a.base_url)
    entries, objects = load_release(a.out_dir, codes, base_url)
    report = pathlib.Path(a.report_dir)
    report.mkdir(parents=True, exist_ok=True)
    lines = []
    say("RELEASE PLAN (nothing has been uploaded)")
    for o in objects:
        if o["kind"] == "asset":
            e = o["entry"]
            v = e["verses"]
            say(f"  {o['code']:6} {e.get('name', '')}")
            say(f"         file_name   {e['file_name']}")
            say(f"         sha256      {o['sha256']}")
            say(f"         size_bytes  {o['size']}")
            say(f"         verses      OT {v['ot']} + NT {v['nt']} = {v['ot'] + v['nt']}   omitted {e.get('omitted_verses')}")
            say(f"         object      {o['key']}")
            say(f"         public URL  {object_url(base_url, o['key'])}")
            lines.append(f"- {o['code']}: sha256 `{o['sha256']}`, {o['size']} bytes, OT {v['ot']} + NT {v['nt']} verses, "
                         f"object `{o['key']}`")
        else:
            say(f"  catalogue   {o['key']}  ({o['size']} bytes, sha256 {o['sha256']})")
            lines.append(f"- catalogue: sha256 `{o['sha256']}`, {o['size']} bytes, object `{o['key']}`")
    plan = {"schema": SCHEMA, "base_url": base_url,
            "objects": [{k: (str(v) if isinstance(v, pathlib.Path) else v) for k, v in o.items() if k != "entry"}
                        for o in objects]}
    (report / "plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The app's embedded catalogue holds the escaped form (the repo's non-ASCII scan flags literal UTF-8); same data.
    catalog = json.loads((pathlib.Path(a.out_dir) / "catalog.json").read_text(encoding="utf-8"))
    (report / "catalog.app.json").write_text(json.dumps(catalog, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                                             encoding="utf-8")
    (report / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary("### Release plan (nothing uploaded yet)")
    for line in lines:
        summary(line)
    return 0


# --- check-inputs --------------------------------------------------------------------------------
def cmd_check_inputs(a):
    codes = parse_codes(a.only_text)
    check_base_url(a.base_url, "TRANSLATIONS_BASE_URL")
    if a.origin_url:
        check_base_url(a.origin_url, "TRANSLATIONS_ORIGIN_URL")
    if a.bucket is not None or a.endpoint is not None:
        check_bucket(a.bucket)
        check_endpoint(a.endpoint)
    say(f"inputs ok: publishing {' '.join(codes)} for {a.base_url}")
    return 0


# --- the aws CLI --------------------------------------------------------------------------------
def aws_env(region):
    env = dict(os.environ)
    env.update({
        "AWS_DEFAULT_REGION": region,
        "AWS_PAGER": "",
        "AWS_EC2_METADATA_DISABLED": "true",
        # aws-cli 2.23+ adds trailing integrity checksums that DigitalOcean Spaces rejects on PutObject; ask for them
        # only when the API requires one (documented DigitalOcean incident, January 2025).
        "AWS_REQUEST_CHECKSUM_CALCULATION": "when_required",
        "AWS_RESPONSE_CHECKSUM_VALIDATION": "when_required",
        "AWS_MAX_ATTEMPTS": "3",
    })
    return env


def run_aws(args, env, bucket, endpoint):
    cmd = ["aws", "s3api", *args[:1], "--bucket", bucket, "--endpoint-url", endpoint, "--no-cli-pager",
           "--cli-connect-timeout", "30", "--cli-read-timeout", "120", *args[1:]]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=AWS_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        raise Refusal(f"aws s3api {args[0]} timed out after {AWS_TIMEOUT} seconds")
    except OSError as e:
        raise Refusal(f"could not run the aws CLI ({type(e).__name__}: {e})")


def head_object(key, env, bucket, endpoint):
    """None when the key is absent; {'size', 'etag'} when present. Any other answer is a refusal: a key whose state
    cannot be read must never be assumed to be free."""
    r = run_aws(["head-object", "--key", key, "--output", "json"], env, bucket, endpoint)
    if r.returncode == 0:
        try:
            meta = json.loads(r.stdout)
            return {"size": int(meta["ContentLength"]), "etag": str(meta.get("ETag", "")).strip('"')}
        except (ValueError, KeyError, TypeError):
            raise Refusal(f"head-object {key}: unreadable answer from the Space")
    err = r.stderr or ""
    if "(404)" in err or "Not Found" in err or "NoSuchKey" in err:
        return None
    raise Refusal(f"head-object {key}: cannot tell whether it exists (exit {r.returncode}): {err.strip()[:300]}")


def cmd_upload(a):
    codes = parse_codes(" ".join(a.only))
    base_url = check_base_url(a.base_url)
    bucket = check_bucket(a.bucket)
    region = check_endpoint(a.endpoint)
    entries, objects = load_release(a.out_dir, codes, base_url)
    todo = stage_objects(objects, a.stage)
    if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
        raise Refusal("SPACES_ACCESS_KEY_ID / SPACES_SECRET_ACCESS_KEY are not set in this step. They come from the "
                      "'translations-publish' environment; see docs/ops/TRANSLATIONS-PUBLISH.md")
    if shutil.which("aws") is None:
        raise Refusal("the aws CLI is not on PATH")
    env = aws_env(region)
    if a.stage == "catalogue":
        # Never point a catalogue at a file that is not there: every asset must already be in the bucket, same size.
        for o in stage_objects(objects, "assets"):
            found = head_object(o["key"], env, bucket, a.endpoint)
            if found is None or found["size"] != o["size"]:
                raise Refusal(f"refusing to upload the catalogue: {o['key']} is not in the bucket with the built size")
    published = skipped = 0
    for o in todo:
        found = head_object(o["key"], env, bucket, a.endpoint)
        if found is not None:
            etag = found["etag"]
            etag_known = bool(re.fullmatch(r"[0-9a-f]{32}", etag))
            if found["size"] != o["size"] or (etag_known and etag != md5_file(o["path"])):
                raise Refusal(f"{o['key']} already exists with different bytes (size {found['size']}, ETag {etag[:12]}). "
                              f"A published key is never overwritten: older apps pin its digest. Nothing was changed")
            r = run_aws(["put-object-acl", "--key", o["key"], "--acl", ACL], env, bucket, a.endpoint)
            if r.returncode != 0:
                raise Refusal(f"put-object-acl {o['key']} failed: {(r.stderr or '').strip()[:300]}")
            say(f"  already published, same bytes, left alone: {o['key']}")
            skipped += 1
            continue
        r = run_aws(["put-object", "--key", o["key"], "--body", str(o["path"]), "--acl", ACL,
                     "--content-type", o["content_type"], "--cache-control", o["cache_control"]], env, bucket, a.endpoint)
        if r.returncode != 0:
            raise Refusal(f"put-object {o['key']} failed (exit {r.returncode}): {(r.stderr or '').strip()[:300]}")
        found = head_object(o["key"], env, bucket, a.endpoint)
        if found is None or found["size"] != o["size"]:
            raise Refusal(f"{o['key']} is not in the bucket with the built size after the upload")
        say(f"  uploaded: {o['key']} ({o['size']} bytes)")
        published += 1
    say(f"upload {a.stage}: {published} uploaded, {skipped} already there, 0 overwritten")
    summary(f"- upload {a.stage}: {published} uploaded, {skipped} already there, 0 overwritten")
    return 0


# --- reading it back from the public URL ----------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect (not followed)", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch_once(url, accept_encoding, max_bytes, opener=None, allow_http=False):
    """GET `url` without following redirects. Returns (status, headers with lower-case names, body), reading at most
    max_bytes + 1 bytes. Sends the same Accept-Encoding the app sends, and never decodes what comes back."""
    if urllib.parse.urlsplit(url).scheme != "https" and not allow_http:
        raise Refusal(f"{url}: not an HTTPS URL; refusing to request it")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": accept_encoding})
    try:
        resp = (opener or _OPENER.open)(req, timeout=HTTP_TIMEOUT)
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read(512)
    except (urllib.error.URLError, OSError) as e:
        return 0, {}, f"{type(e).__name__}: {e}".encode()
    with contextlib.closing(resp):
        return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read(max_bytes + 1)


def response_problems(o, status, headers, body):
    """Why this response is not the object. An empty list means the bytes are exactly what was built."""
    if status != 200:
        return [f"HTTP {status}" + (f" ({body[:120].decode('utf-8', 'replace')})" if status == 0 else "")]
    problems = []
    if len(body) != o["size"]:
        problems.append(f"{len(body)} bytes received, {o['size']} expected" + (" (or more)" if len(body) > o["size"] else ""))
    elif sha256_bytes(body) != o["sha256"]:
        problems.append(f"sha256 {sha256_bytes(body)[:12]}.. received, {o['sha256'][:12]}.. expected")
    length = headers.get("content-length")
    if length is not None and length != str(o["size"]):
        problems.append(f"Content-Length {length}, expected {o['size']}")
    encoding = headers.get("content-encoding", "").strip().lower()
    if encoding not in ("", "identity"):
        problems.append(f"Content-Encoding {encoding!r}: the server re-encoded the object, and the app hashes the bytes it "
                        f"receives")
    return problems


def describe(headers):
    keys = ("content-type", "content-length", "content-encoding", "etag", "cache-control", "age", "cf-cache-status",
            "x-do-cdn-uuid", "server")
    return ", ".join(f"{k}={headers[k]}" for k in keys if k in headers) or "(no headers)"


def notes_for(o, headers):
    notes = []
    ctype = headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype != o["content_type"]:
        notes.append(f"Content-Type is {ctype!r}, expected {o['content_type']!r}")
    if "immutable" not in headers.get("cache-control", ""):
        notes.append(f"Cache-Control is {headers.get('cache-control')!r}, expected {o['cache_control']!r}")
    return notes


def verify_one(label, base, o, attempts, sleep, opener, deadline, allow_http=False):
    """Fetch base/key until it is exactly the built object, a bounded number of times; fail closed after that."""
    url = object_url(base, o["key"])
    last = []
    for n in range(1, attempts + 1):
        status, headers, body = fetch_once(url, "identity", o["size"], opener, allow_http)
        last = response_problems(o, status, headers, body)
        if not last:
            say(f"  {label}: {o['key']} OK ({len(body)} bytes, sha256 {o['sha256'][:12]}..) {describe(headers)}")
            for note in notes_for(o, headers):
                say(f"    note: {note}")
            return headers
        say(f"  {label}: {o['key']} attempt {n}/{attempts}: {'; '.join(last)}")
        if n < attempts:
            if time.monotonic() > deadline:
                last.append("the verification time budget ran out")
                break
            sleep(min(2 ** n, MAX_BACKOFF))
    raise Refusal(f"{label}: {url} is not the built object after {attempts} attempts: {'; '.join(last)}. "
                  f"If it is a stale 403 or 404 held by the CDN, purge that path (docs/ops/TRANSLATIONS-PUBLISH.md) "
                  f"and re-run: the uploads are idempotent")


def gzip_probe(base, o, opener, allow_http=False):
    """Information only, never a failure: what a client that DOES accept gzip gets from the CDN for this object."""
    status, headers, body = fetch_once(object_url(base, o["key"]), "gzip", MAX_ASSET_BYTES, opener, allow_http)
    same = status == 200 and len(body) == o["size"] and sha256_bytes(body) == o["sha256"]
    line = (f"  probe with Accept-Encoding: gzip: HTTP {status}, Content-Encoding "
            f"{headers.get('content-encoding', '(none)')}, bytes identical to the object: {same}")
    say(line)
    summary("- " + line.strip())


def cmd_verify(a, sleep=time.sleep, opener=None, allow_http=False):
    codes = parse_codes(" ".join(a.only))
    base_url = check_base_url(a.base_url)
    origin = check_base_url(a.origin_url, "origin URL") if a.origin_url else None
    entries, objects = load_release(a.out_dir, codes, base_url)
    todo = stage_objects(objects, a.stage)
    deadline = time.monotonic() + VERIFY_BUDGET_SECONDS
    # The origin first: it is the authority on whether the object is public, and asking it first means the CDN is never
    # asked for a key that is not yet readable (a CDN may hold on to a 403 or 404).
    targets = ([("origin", origin)] if origin else []) + [("CDN", base_url)]
    for o in todo:
        for label, base in targets:
            verify_one(label, base, o, a.attempts, sleep, opener, deadline, allow_http)
        if o["kind"] == "asset":
            try:
                gzip_probe(base_url, o, opener, allow_http)
            except Refusal as e:
                say(f"  probe skipped: {e}")
    say(f"verify {a.stage}: {len(todo)} object(s) read back from {', '.join(l for l, _ in targets)}, every byte identical")
    summary(f"- verify {a.stage}: {len(todo)} object(s) read back from {', '.join(l for l, _ in targets)}, every byte identical")
    return 0


# --- the positive control's inputs -------------------------------------------------------------------
def fetch_bundled(work_dir, opener=None):
    """Download the five bundled Bibles' USFM zips the converter's `--verify-bundled` needs, with the converter's own
    download rules (HTTPS only, size cap, no partial file). A zip already in the folder is kept."""
    work = pathlib.Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    for _name, (ebible_id, _note) in sorted(sbh.SOURCES.items()):
        try:
            btc.ensure(work, f"{ebible_id}_usfm.zip", f"{btc.EBIBLE}/{ebible_id}_usfm.zip", False, opener)
        except sbh.Mismatch as e:
            raise Refusal("; ".join(e.problems))
        say(f"  {ebible_id}_usfm.zip")


def cmd_fetch_bundled(a):
    fetch_bundled(a.work_dir)
    return 0


# --- self-test ---------------------------------------------------------------------------------------
FAKE_AWS = r'''#!/usr/bin/env python3
"""A stand-in for `aws s3api` backed by a folder. Used by publish_translations.py --self-test only."""
import hashlib, json, os, pathlib, sys

root = pathlib.Path(os.environ["FAKE_BUCKET_DIR"])
log = root / "_calls.log"
args = sys.argv[1:]
assert args[0] == "s3api", args
op, rest = args[1], args[2:]
opts, i = {}, 0
while i < len(rest):
    assert rest[i].startswith("--"), rest
    name = rest[i][2:]
    if name == "no-cli-pager":
        i += 1
        continue
    opts[name] = rest[i + 1]
    i += 2
with open(log, "a") as f:
    f.write(op + " " + opts.get("key", "") + "\n")
assert os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")
assert os.environ.get("AWS_REQUEST_CHECKSUM_CALCULATION") == "when_required"
objects = root / "objects"
objects.mkdir(exist_ok=True)
key = opts.get("key", "")
data_path = objects / key.replace("/", "__")
meta_path = objects / (key.replace("/", "__") + ".meta")
if op == "head-object":
    if os.environ.get("FAKE_HEAD_ERROR"):
        sys.stderr.write(os.environ["FAKE_HEAD_ERROR"])
        sys.exit(254)
    if not data_path.exists():
        sys.stderr.write("An error occurred (404) when calling the HeadObject operation: Not Found\n")
        sys.exit(254)
    data = data_path.read_bytes()
    etag = os.environ.get("FAKE_ETAG") or hashlib.md5(data).hexdigest()
    print(json.dumps({"ContentLength": len(data), "ETag": '"%s"' % etag}))
elif op == "put-object":
    puts = sum(1 for l in log.read_text().splitlines() if l.startswith("put-object "))
    fail_after = os.environ.get("FAKE_FAIL_PUT_AFTER")
    if fail_after is not None and puts > int(fail_after):
        sys.stderr.write("An error occurred (InternalError) when calling the PutObject operation\n")
        sys.exit(1)
    if os.environ.get("FAKE_PUT_NOOP"):
        print("{}")
        sys.exit(0)
    data_path.write_bytes(pathlib.Path(opts["body"]).read_bytes())
    meta_path.write_text(json.dumps({k: opts[k] for k in ("acl", "content-type", "cache-control") if k in opts}
                                    | {"has_content_encoding": "content-encoding" in opts}))
    print("{}")
elif op == "put-object-acl":
    meta = json.loads(meta_path.read_text())
    meta["acl"] = opts["acl"]
    meta_path.write_text(json.dumps(meta))
    print("{}")
else:
    sys.stderr.write("unsupported " + op + "\n")
    sys.exit(2)
'''


class _FakeResponse:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n):
        chunk = self.data[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk


class _FakeHttp:
    def __init__(self, status, headers, body):
        self.status, self.headers, self._body, self._pos = status, dict(headers), body, 0

    def read(self, n):
        chunk = self._body[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def close(self):
        pass


def _write_release(out, code="BSB", legal="cleared", base="https://cdn.example", body=b"gzip-bytes-" * 50, extra=None):
    out.mkdir(parents=True, exist_ok=True)
    name = code.lower() + ".tsv.gz"
    (out / name).write_bytes(body)
    entry = {"code": code, "name": "Fixture", "file_name": name, "size_bytes": len(body), "sha256": sha256_bytes(body),
             "verses": {"ot": 2, "nt": 1}, "omitted_verses": 0, "legal_review": legal}
    entry.update(extra or {})
    catalog = {"schema": 1, "base_url": base, "translations": [entry]}
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def self_test():
    """Run the checks with the progress output captured: it is shown only when something fails."""
    saved = os.environ.pop("GITHUB_STEP_SUMMARY", None)  # a self-test run inside Actions must not write to the job summary
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            failures = _self_test_checks()
    finally:
        if saved is not None:
            os.environ["GITHUB_STEP_SUMMARY"] = saved
    if failures:
        print(buffer.getvalue(), file=sys.stderr)
        print("publish_translations self-test FAILED:", file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        return 1
    print("publish_translations self-test: ok")
    return 0


def _self_test_checks():
    failures = []

    def check(cond, label):
        if not cond:
            failures.append(label)

    def raises(fn, needle, label):
        try:
            fn()
        except Refusal as e:
            check(needle in str(e), f"{label}: refused with the wrong reason: {e}")
            return
        failures.append(f"{label}: expected a refusal containing {needle!r}, got none")

    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)

        # --- inputs ---
        check(parse_codes("BSB YOR") == ["BSB", "YOR"], "codes parse")
        for bad in ("bsb", "B", "BSB BSB", "BSB;rm", "--base-url", "X" * 17, "BS$"):
            try:
                parse_codes(bad)
                failures.append(f"parse_codes accepted {bad!r}")
            except Refusal:
                pass
        raises(lambda: parse_codes(""), "no translation codes", "empty codes")
        good_url = "https://bible-translations.sfo3.cdn.digitaloceanspaces.com"
        check(check_base_url(good_url) == good_url and check_base_url("https://dl.example.org/mirror") == "https://dl.example.org/mirror",
              "good base URLs")
        for bad in ("", "http://x.example", good_url + "/", good_url + "?a=b", good_url + "#f", "https://u:p@x.example",
                    "https://x.example//a", "ftp://x.example", "https://", "https://x.example/a b"):
            try:
                check_base_url(bad)
                failures.append(f"check_base_url accepted {bad!r}")
            except Refusal:
                pass
        check(check_endpoint("https://sfo3.digitaloceanspaces.com") == "sfo3", "endpoint region")
        for bad in ("http://sfo3.digitaloceanspaces.com", "https://sfo3.digitaloceanspaces.com/", "https://evil.example",
                    "https://sfo3.digitaloceanspaces.com.evil.example", "https://bucket.sfo3.digitaloceanspaces.com", ""):
            try:
                check_endpoint(bad)
                failures.append(f"check_endpoint accepted {bad!r}")
            except Refusal:
                pass
        check(check_bucket("bible-translations") == "bible-translations", "bucket ok")
        for bad in ("", "A", "Bible", "a/b", "-x-", "a" * 64):
            try:
                check_bucket(bad)
                failures.append(f"check_bucket accepted {bad!r}")
            except Refusal:
                pass

        # --- the release on disk ---
        base = "https://cdn.example"
        out = d / "out"
        _write_release(out, base=base)
        entries, objects = load_release(out, ["BSB"], base)
        a_obj, c_obj = objects
        check([o["kind"] for o in objects] == ["asset", "catalogue"], "assets first, catalogue last")
        check(a_obj["key"] == f"translations/BSB/{a_obj['sha256']}.tsv.gz", "asset key is content-addressed")
        check(c_obj["key"] == f"translations/catalog/{sha256_file(out / 'catalog.json')}.json", "catalogue key is content-addressed")
        check(a_obj["cache_control"] == IMMUTABLE and a_obj["content_type"] == "application/gzip", "asset headers")
        raises(lambda: load_release(out, ["BSB", "YOR"], base), "asked to publish", "missing requested code")
        raises(lambda: load_release(out, [], base), "asked to publish", "no code requested")
        raises(lambda: load_release(out, ["BSB"], "https://other.example"), "base_url", "base_url mismatch")
        pend = d / "pend"
        _write_release(pend, legal="pending", base=base)
        raises(lambda: load_release(pend, ["BSB"], base), "not 'cleared'", "pending legal review is refused")
        odd = d / "odd"
        _write_release(odd, legal="Cleared", base=base)
        raises(lambda: load_release(odd, ["BSB"], base), "not 'cleared'", "legal_review must be exactly 'cleared'")
        gone = d / "gone"
        _write_release(gone, base=base)
        (gone / "catalog.json").unlink()
        raises(lambda: load_release(gone, ["BSB"], base), "catalog.json is missing", "no catalogue")
        extra = d / "extra"
        _write_release(extra, base=base)
        (extra / "yor.tsv.gz").write_bytes(b"legal pending text")
        raises(lambda: load_release(extra, ["BSB"], base), "unexpected", "a stray file in the folder")
        corrupt = d / "corrupt"
        _write_release(corrupt, base=base)
        (corrupt / "bsb.tsv.gz").write_bytes(b"x" * len((corrupt / "bsb.tsv.gz").read_bytes()))
        raises(lambda: load_release(corrupt, ["BSB"], base), "does not hash", "same size, different bytes")
        short = d / "short"
        _write_release(short, base=base)
        (short / "bsb.tsv.gz").write_bytes(b"short")
        raises(lambda: load_release(short, ["BSB"], base), "but the catalogue says", "different size")
        for label, patch in (("slash in file_name", {"file_name": "a/b.tsv.gz"}), ("dotdot", {"file_name": "..x.tsv.gz"}),
                             ("bad suffix", {"file_name": "bsb.tsv"}), ("bad sha", {"sha256": "AB" * 32}),
                             ("short sha", {"sha256": "ab" * 31}), ("zero size", {"size_bytes": 0}),
                             ("bool size", {"size_bytes": True}), ("huge size", {"size_bytes": MAX_ASSET_BYTES + 1}),
                             ("lower-case code", {"code": "bsb"}), ("no verses", {"verses": {"ot": "x", "nt": 1}})):
            p = d / ("bad-" + label.replace(" ", "-"))
            _write_release(p, base=base, extra=patch)
            try:
                load_release(p, ["BSB"], base)
                failures.append(f"load_release accepted {label}")
            except Refusal:
                pass
        dup = d / "dup"
        _write_release(dup, base=base)
        cat = json.loads((dup / "catalog.json").read_text())
        cat["translations"].append(dict(cat["translations"][0], file_name="other.tsv.gz"))
        (dup / "catalog.json").write_text(json.dumps(cat))
        raises(lambda: load_release(dup, ["BSB"], base), "appears twice", "duplicate code")
        dupf = d / "dupf"
        _write_release(dupf, base=base)
        cat = json.loads((dupf / "catalog.json").read_text())
        cat["translations"].append(dict(cat["translations"][0], code="HAU"))
        (dupf / "catalog.json").write_text(json.dumps(cat))
        raises(lambda: load_release(dupf, ["BSB", "HAU"], base), "used twice", "duplicate file name")
        link = d / "link"
        _write_release(link, base=base)
        real = d / "real.bin"
        real.write_bytes((link / "bsb.tsv.gz").read_bytes())
        (link / "bsb.tsv.gz").unlink()
        (link / "bsb.tsv.gz").symlink_to(real)
        raises(lambda: load_release(link, ["BSB"], base), "is missing", "a symlink is not a file")
        bom = d / "bom"
        _write_release(bom, base=base)
        (bom / "catalog.json").write_bytes(b"\xef\xbb\xbf" + (bom / "catalog.json").read_bytes())
        raises(lambda: load_release(bom, ["BSB"], base), "not valid UTF-8 JSON", "a BOM is not what the converter writes")

        # --- upload, with a fake aws ---
        fake_bin = d / "bin"
        fake_bin.mkdir()
        fake = fake_bin / "aws"
        fake.write_text(FAKE_AWS)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        bucket_dir = d / "bucket"
        bucket_dir.mkdir()
        saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_BUCKET_DIR", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                                                "FAKE_FAIL_PUT_AFTER", "FAKE_HEAD_ERROR", "FAKE_ETAG", "FAKE_PUT_NOOP")}
        os.environ["PATH"] = f"{fake_bin}{os.pathsep}{os.environ['PATH']}"
        os.environ["FAKE_BUCKET_DIR"] = str(bucket_dir)
        os.environ.pop("FAKE_FAIL_PUT_AFTER", None)
        os.environ.pop("FAKE_HEAD_ERROR", None)
        os.environ.pop("FAKE_ETAG", None)
        os.environ.pop("FAKE_PUT_NOOP", None)

        def up(stage, release=out, only=("BSB",), url=base):
            ns = argparse.Namespace(stage=stage, out_dir=str(release), only=list(only), base_url=url,
                                    bucket="bible-translations", endpoint="https://sfo3.digitaloceanspaces.com")
            return cmd_upload(ns)

        def calls():
            f = bucket_dir / "_calls.log"
            return f.read_text().splitlines() if f.exists() else []

        def stored():
            o = bucket_dir / "objects"
            return sorted(p.name for p in o.iterdir() if not p.name.endswith(".meta")) if o.exists() else []

        try:
            os.environ.pop("AWS_ACCESS_KEY_ID", None)
            os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
            raises(lambda: up("assets"), "are not set", "no credentials, no upload")
            check(calls() == [], "nothing was called without credentials")
            os.environ["AWS_ACCESS_KEY_ID"] = "test-id-not-a-secret"
            os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-not-a-secret"

            raises(lambda: up("catalogue"), "refusing to upload the catalogue", "no catalogue before the assets")
            check(stored() == [], "the catalogue stage wrote nothing when an asset was missing")
            up("assets")
            check(len(stored()) == 1 and stored()[0].startswith("translations__BSB__"), "the asset is uploaded under its key")
            meta = json.loads(next((bucket_dir / "objects").glob("*.meta")).read_text())
            check(meta["acl"] == "public-read" and meta["content-type"] == "application/gzip"
                  and meta["cache-control"] == IMMUTABLE and meta["has_content_encoding"] is False,
                  f"object settings: {meta}")
            up("catalogue")
            check(len(stored()) == 2, "the catalogue is uploaded after the assets")
            puts_after_first = sum(1 for c in calls() if c.startswith("put-object "))
            up("assets")
            up("catalogue")
            check(sum(1 for c in calls() if c.startswith("put-object ")) == puts_after_first, "a second run uploads nothing")

            # an existing key whose bytes differ is never overwritten
            key_file = next(p for p in (bucket_dir / "objects").iterdir() if p.name.startswith("translations__BSB__")
                            and not p.name.endswith(".meta"))
            key_file.write_bytes(b"tampered but same length?")
            before = key_file.read_bytes()
            raises(lambda: up("assets"), "never overwritten", "an existing key with other bytes")
            check(key_file.read_bytes() == before, "the existing object was not touched")
            key_file.write_bytes(b"x" * a_obj["size"])  # same size, different bytes: only the ETag can tell
            raises(lambda: up("assets"), "never overwritten", "same size, different MD5")
            key_file.write_bytes(a_obj["path"].read_bytes())
            # When the Space reports an ETag that is not a plain MD5 (a multipart upload), the size is what is left to compare.
            os.environ["FAKE_ETAG"] = "0123456789abcdef0123456789abcdef-2"
            up("assets")  # same size: accepted here, and the byte-for-byte read-back through the public URL is the real check
            key_file.write_bytes(b"short")
            raises(lambda: up("assets"), "never overwritten", "a different size is refused even when the ETag cannot be compared")
            key_file.write_bytes(a_obj["path"].read_bytes())
            os.environ.pop("FAKE_ETAG")

            # a put that reports success but stored nothing is caught
            shutil.rmtree(bucket_dir / "objects")
            os.environ["FAKE_PUT_NOOP"] = "1"
            raises(lambda: up("assets"), "is not in the bucket with the built size after the upload", "a put that stored nothing")
            os.environ.pop("FAKE_PUT_NOOP")
            up("assets")
            up("catalogue")

            # a partial failure leaves no catalogue behind
            two = d / "two"
            two.mkdir()
            body_b, body_c = b"second-" * 40, b"third-" * 40
            (two / "bsb.tsv.gz").write_bytes(a_obj["path"].read_bytes() + b"1")
            (two / "hau.tsv.gz").write_bytes(body_b)
            cat2 = {"schema": 1, "base_url": base, "translations": [
                {"code": c, "name": c, "file_name": c.lower() + ".tsv.gz", "size_bytes": len(p.read_bytes()),
                 "sha256": sha256_bytes(p.read_bytes()), "verses": {"ot": 1, "nt": 1}, "omitted_verses": 0, "legal_review": "cleared"}
                for c, p in (("BSB", two / "bsb.tsv.gz"), ("HAU", two / "hau.tsv.gz"))]}
            (two / "catalog.json").write_text(json.dumps(cat2, indent=2, sort_keys=True) + "\n")
            shutil.rmtree(bucket_dir / "objects")
            (bucket_dir / "_calls.log").unlink()
            os.environ["FAKE_FAIL_PUT_AFTER"] = "1"
            raises(lambda: up("assets", two, ("BSB", "HAU")), "put-object", "the second upload fails")
            check(len(stored()) == 1, "exactly the first asset was uploaded before the failure")
            raises(lambda: up("catalogue", two, ("BSB", "HAU")), "refusing to upload the catalogue", "no catalogue after a partial upload")
            check(not any("catalog__" in s for s in stored()), "no catalogue object exists after the partial failure")
            os.environ.pop("FAKE_FAIL_PUT_AFTER")
            up("assets", two, ("BSB", "HAU"))
            up("catalogue", two, ("BSB", "HAU"))
            check(len(stored()) == 3, "a re-run after the failure completes the set")

            # a head-object answer that is not a clean 404 is never read as 'absent'
            os.environ["FAKE_HEAD_ERROR"] = "An error occurred (403) when calling the HeadObject operation: Forbidden\n"
            raises(lambda: up("assets"), "cannot tell whether it exists", "a 403 is not an absent key")
            os.environ.pop("FAKE_HEAD_ERROR")
            raises(lambda: up("assets", pend, ("BSB",)), "not 'cleared'", "upload refuses a pending translation")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # --- verify, with a fake network ---
        good_body = a_obj["path"].read_bytes()
        hdr = {"content-type": "application/gzip", "content-length": str(len(good_body)), "cache-control": IMMUTABLE,
               "etag": '"abc"'}
        sleeps = []
        verify_calls = []

        def make_opener(script):
            def opener(req, timeout=None):
                verify_calls.append((req.full_url, req.get_header("Accept-encoding")))
                status, headers, body = script(req)
                if status != 200:
                    raise urllib.error.HTTPError(req.full_url, status, "x", headers, io.BytesIO(body))
                resp = _FakeHttp(status, headers, body)
                return resp
            return opener

        def verify(script, origin=None, attempts=3, stage="assets"):
            verify_calls.clear()
            sleeps.clear()
            ns = argparse.Namespace(stage=stage, out_dir=str(out), only=["BSB"], base_url=base, origin_url=origin,
                                    attempts=attempts)
            return cmd_verify(ns, sleep=sleeps.append, opener=make_opener(script), allow_http=False)

        check(verify(lambda r: (200, dict(hdr), good_body)) == 0, "verify: exact bytes pass")
        check(all(enc in ("identity", "gzip") for _u, enc in verify_calls) and verify_calls[0][1] == "identity",
              f"verify asks with Accept-Encoding: identity first: {verify_calls}")
        check(verify_calls[0][0] == f"{base}/{a_obj['key']}", "verify asks the public URL of the key")
        verify(lambda r: (200, dict(hdr, **{"content-type": "text/plain"}), good_body))  # a note, not a failure
        verify(lambda r: (200, dict(hdr), good_body), origin="https://origin.example")
        check(verify_calls[0][0].startswith("https://origin.example/"), "the origin is asked first")
        check(any(u.startswith(base) for u, _ in verify_calls), "and the CDN too")

        def fails(script, needle, label, **kw):
            try:
                verify(script, **kw)
            except Refusal as e:
                check(needle in str(e), f"{label}: wrong reason: {e}")
                return
            failures.append(f"{label}: verify passed")

        fails(lambda r: (200, dict(hdr), good_body[:-1] + b"X"), "sha256", "one byte different")
        fails(lambda r: (200, dict(hdr), good_body + b"!"), "bytes received", "longer than built")
        fails(lambda r: (200, dict(hdr), good_body[:-5]), "bytes received", "shorter than built")
        fails(lambda r: (200, dict(hdr, **{"content-encoding": "gzip"}), good_body), "Content-Encoding", "re-encoded")
        fails(lambda r: (200, dict(hdr, **{"content-length": "1"}), good_body), "Content-Length", "length header lies")
        fails(lambda r: (403, {}, b"<Error>AccessDenied</Error>"), "HTTP 403", "private object")
        fails(lambda r: (301, {"location": "https://elsewhere.example/x"}, b""), "HTTP 301", "a redirect is not followed")
        check(len(sleeps) == 2 and sleeps == [2, 4], f"bounded retries with backoff: {sleeps}")
        fails(lambda r: (200, dict(hdr), b"x"), "after 3 attempts", "attempt count is reported", attempts=3)
        # propagation: the first two answers are 403, then it is there
        seen = {"n": 0}

        def late(r):
            seen["n"] += 1
            return (403, {}, b"denied") if seen["n"] <= 2 else (200, dict(hdr), good_body)

        verify(late)
        check(sleeps == [2, 4], "a late object passes after the retries")
        # the gzip probe is information only: even an error there does not fail the run
        def probe_fails(r):
            return (500, {}, b"boom") if r.get_header("Accept-encoding") == "gzip" else (200, dict(hdr), good_body)

        check(verify(probe_fails) == 0, "a failing gzip probe is not a failure")

        # the real fetch: identity request header, no redirect, a hard byte cap, against a throwaway local server
        seen_headers = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen_headers.update({k.lower(): v for k, v in self.headers.items()})
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "https://elsewhere.example/")
                    self.end_headers()
                    return
                body = b"0123456789" * 100
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}"
            raises(lambda: fetch_once(url + "/x", "identity", 10), "not an HTTPS URL", "plain http is refused")
            status, headers, body = fetch_once(url + "/x", "identity", 10, allow_http=True)
            check(status == 200 and len(body) == 11, "the read is capped at max_bytes + 1")
            check(seen_headers.get("accept-encoding") == "identity", f"identity is sent: {seen_headers}")
            status, headers, body = fetch_once(url + "/redirect", "identity", 10, allow_http=True)
            check(status == 302 and "location" in headers, "a redirect comes back as a 302, not followed")
        finally:
            server.shutdown()
            server.server_close()

        # --- bundled-Bible download helper ---
        def opener(req, timeout=None):
            return _FakeResponse(b"zip:" + req.full_url.encode())

        work = d / "work"
        fetch_bundled(work, opener)
        names = sorted(p.name for p in work.iterdir())
        check(names == sorted(f"{v[0]}_usfm.zip" for v in sbh.SOURCES.values()), f"the five zips are fetched: {names}")
        before = {p.name: p.read_bytes() for p in work.iterdir()}
        fetch_bundled(work, lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not download again")))
        check({p.name: p.read_bytes() for p in work.iterdir()} == before, "an existing zip is kept, not fetched again")

        # --- plan ---
        report = d / "report"
        ns = argparse.Namespace(out_dir=str(out), only=["BSB"], base_url=base, report_dir=str(report))
        check(cmd_plan(ns) == 0 and sorted(p.name for p in report.iterdir()) == ["catalog.app.json", "plan.json", "summary.md"],
              "plan writes its three report files")
        app = (report / "catalog.app.json").read_text()
        check(all(ord(c) < 128 for c in app), "the app copy of the catalogue is ASCII")

        # --- main wiring ---
        for argv in (["check-inputs", "--only-text=BSB", f"--base-url={good_url}", "--bucket=bible-translations",
                      "--endpoint=https://sfo3.digitaloceanspaces.com"],):
            check(main(argv) == 0, f"main {argv[0]} passes")
        with contextlib.redirect_stderr(io.StringIO()):
            check(main(["check-inputs", "--only-text=bsb", f"--base-url={good_url}"]) == 1, "main reports a refusal as exit 1")
            check(main(["check-inputs", "--only-text=BSB", "--base-url=http://x.example"]) == 1, "an http base URL exits 1")

    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("check-inputs", help="refuse inputs that do not look right, before anything is built")
    p.add_argument("--only-text", required=True, help="the codes as one string, for example 'BSB'")
    p.add_argument("--base-url", default=None)
    p.add_argument("--origin-url", default=None)
    p.add_argument("--bucket", default=None)
    p.add_argument("--endpoint", default=None)

    p = sub.add_parser("fetch-bundled", help="download the five bundled Bibles' USFM zips for --verify-bundled")
    p.add_argument("--work-dir", required=True)

    def common(p, upload=False):
        p.add_argument("--out-dir", required=True, help="the converter's output folder")
        p.add_argument("--only", nargs="+", required=True, metavar="CODE")
        p.add_argument("--base-url", required=True)

    p = sub.add_parser("plan", help="check the build against its catalogue and print what would be published")
    common(p)
    p.add_argument("--report-dir", required=True)

    p = sub.add_parser("upload", help="upload one stage (never overwrites a published key)")
    common(p)
    p.add_argument("--stage", choices=("assets", "catalogue"), required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--endpoint", required=True)

    p = sub.add_parser("verify", help="read one stage back from the public URLs and compare every byte")
    common(p)
    p.add_argument("--stage", choices=("assets", "catalogue"), required=True)
    p.add_argument("--origin-url", default=None)
    p.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)

    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    handlers = {"check-inputs": cmd_check_inputs, "fetch-bundled": cmd_fetch_bundled, "plan": cmd_plan,
                "upload": cmd_upload, "verify": cmd_verify}
    if args.cmd not in handlers:
        ap.error("a command is required")
    if args.cmd == "verify" and not 1 <= args.attempts <= 10:
        ap.error("--attempts must be 1 to 10")
    try:
        return handlers[args.cmd](args)
    except Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
