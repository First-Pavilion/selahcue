# Pilot private-download grant (P12)

Ticket: https://app.clickup.com/t/17tnw2bbhxm . This source increment is disabled by default. It has **no production storage signer** and cannot deliver a real private URL until P10 supplies and verifies one. Existing licensed/device download APIs remain separate501 stubs. P12's real-read/full-journey criterion remains blocked; synthetic test results do not complete it.

`POST /v1/pilot/downloads:grant` is n8n server-to-server only. Its dedicated Bearer token must differ from all three registration keys. Customer cookies, device tokens and public form fields confer no authority. Authentication occurs before reading/parsing the body or querying registration. An authenticated IP has a separate30-per60-second fail-closed budget. There is no CORS grant or cookie issuance.

The exact JSON body is `{ "schema_version": 1, "receipt": "<P13 server receipt>", "artifact_id": "<opaque allowlisted ID>" }`. Bodies over8192bytes, duplicate keys, malformed/deep JSON, extra fields or caller-supplied paths/URLs/TTL/platform/required_platforms/signing_requirements are rejected. The P13 verifier remains the authority for receipt signature/audience, actual confirmed ledger row, retention, platform and original expiry. A failed Sheet write has no valid receipt and cannot obtain a grant.

Successful source contract: schema_version, artifact_id, release_id, platform, architectures, sha256, size_bytes, download_url, expires_at. No registration/contact/church fields, receipt or provider keys are returned. URLs and signer exceptions must never be logged. The URL is bearer authority until its short expiry; previously issued links are not promised immediate individual revocation.

## P11 promoted server-manifest interface

P11 must agree and implement this producer contract before claiming compatibility. The grant consumes a **server-owned local regular file**, at an absolute path with an independently configured SHA256 digest. It reads/hash-checks the exact bytes on each grant, at most65536bytes. Final symlinks and nonregular files fail closed. A missing, changed, malformed, unknown or incomplete snapshot yields503. No marketing JSON, caller URL, remote manifest fetch, mutable latest alias or automatic platform fallback is used.

Root object has exactly these fields:

- `schema_version`: integer1, `manifest_id`, `release_id`, `cohort_id`, `version`: nonempty ASCII identifiers, each≤80chars. `cohort_id` equals the configured approved cohort.
- `source_sha`:40lowercase hex; `promoted`:true; `promoted_at`:positive epoch UTC seconds≤now; `expires_at`:epoch UTC seconds>now and≤1809129599.
- `artifacts`: exactly the server-declared required set of verified available entries. Omitted `SELAHCUE_PILOT_GRANT_REQUIRED_PLATFORMS` retains the three-platform default: Windows x86_64, Ubuntu x86_64, and macOS x86_64+aarch64 in that order within the architectures array. Explicit `Windows` permits exactly one Windows x86_64 entry for a private pilot. No other partial set, blank, duplicate or unknown platform configuration is accepted. Entry order in artifacts does not matter. IDs/platforms cannot duplicate. Missing declared or extra undeclared entries refuse. Payloads, receipts and marketing metadata cannot choose this policy.

Each artifact has exactly: `artifact_id`, `platform`, `architectures`, `object_key`, `sha256`, `size_bytes`, `available`, `verified`, `credentials_expires_at`, `signing`.

- Artifact ID is an opaque ASCII identifier≤80chars; SHA256 is64lowercase hex; size is a positive integer≤20GiB; `available` and `verified` must be literaltrue; expiry is actual provider/build upper bound>now and≤fixed cutoff.
- Object key is exactly `pilot/<release_id>/<sha256>/<filename>`. Filename is an ASCII identifier≤160chars, with no slash, percent encoding or traversal. P10 must enforce immutable/no-overwrite delivery at this content-addressed key. The API does not fetch/inspect storage bytes; P11 owns actual byte/hash/package/signature verification before promoting. No arbitrary key or object URL is accepted from n8n/browser.
- Signing policy keys must exactly equal the server-declared required platform set, and each artifact signing state equals its configured approved per-platform policy. Allowed Windows policies are `authenticode_verified` or explicitly `unsigned_pilot_approved`; neither is silently selected. Ubuntu is `not_required`; macOS must be `developer_id_notarized_stapled`, preserving the existing Universal signed/notarized/stapled requirement. Unknown/missing policy refuses configuration.

This schema is a strict consumer handoff, not a populated manifest or proof that all platforms are ready. Rollout/promotion must coordinate the immutable file and digest; intermediate mismatches refuse grants. Rollback must select an unrevoked, still-unexpired snapshot matching its approved required platform and signing policy; never revive expired credentials/releases.

## P10 signer port

`PrivateReadSigner.sign_read(PrivateReadRequest)` receives only an approved opaque storage target, exact content-addressed object key, artifact hash and absolute deadline. It must authorize GET of that exact object only, no write/list/admin, mutable redirects or alternative paths, and enforce bounded connect/read/total timeouts. P10 must prove anonymous reads denied, CI prefix-limited writes, immutable keys, bounded signed GETs and outage/rotation/revocation behavior. The provider/account/region/owner are still undecided; no existing public translation bucket is reused.

It returns `SignedRead(url, expires_at)`. The service validates exact configured lowercase HTTPS origin and exact object path, no userinfo/fragment/control/non-ASCII bytes, bounded8192-character URL, no duplicate query keys, and only explicitly approved provider signature query names. Query values are bounded and may not contain the receipt, registration UUID or any registration/grant key. No arbitrary PII/redirect fields may be configured. Provider-required signature fields are permitted; raw signing secrets and OpenAI/Deepgram credentials are not.

`configured_private_read_signer()` deliberately returnsNone until P10 implements the real provider adapter. There is no production fake or default/public URL builder. Tests inject an explicitly synthetic signer; they do not exercise storage authentication or real bytes. P10's adapter requires its own independent review and actual provider evidence before enabling.

## Time, retries and concurrency

Fixed cohort cutoff is **2027-04-30T23:59:59Z**, not six months from download. URL deadline is min(original receipt expiry, configured pilot expiry, fixed cutoff, approved manifest expiry, artifact/provider expiry, now+explicit read TTL). Configured TTL is1–300seconds, rounded down to epoch seconds; equality fails. The clock is rechecked after signing, and a slow/invalid/overlong signer result is refused. A manifest digest/configuration change or revoked/retired registration prevents new grants. Already issued URLs can remain valid until their expiry, as determined by the eventual provider.

A valid receipt can retry until its **original** expiry. Each retry revalidates the live ledger and current manifest, may request any available artifact on the registered OS, and cannot extend confirmation time/deadline or switch platform. Concurrent retries may obtain several links to the same approved artifact within that window. There is no one-use grant table, new registration allocation or remote call under a DB row lock.

## Configuration and safe failure

All11`SELAHCUE_PILOT_GRANT_*` fields are documented in `deployments.md`. Disabled returns404. Missing/invalid configuration, manifest or real signer returns503. Unauthorized server/invalid receipt returns403; malformed input400, unsupported media415, oversized413, method405withAllow:POST, selection/platform mismatch409, expiry410, limiter/store refusal429withRetry-After. Existing P13 pending/unknown/retired receipt errors remain intact. Errors use fixed codes without raw bodies, URL, exceptions or secret values. All responses have no-store/no-referrer/nosniff headers.

## Integration and remaining evidence

Root accepted a fixed per-entry production form deployment with a configured allowlisted artifact ID. The form must visibly confirm platform/architecture/version, match P11's public projection, call this endpoint only after both fresh-save and confirmed-retry joins, keep receipts server-side and validate/escape the returned link/metadata. Platform mismatch must offer return-and-select-platform, not a mismatched installer. This PR does not edit n8n or marketing. Actual pinned n8n and real private-read/bytes evidence remain mandatory before the registration-to-download journey is ready.

P15 owner/retention/approved notice, protected Google Sheet, P01 provider expiry/revocation evidence, P02/P03/P04 credentials/cutoff/scanner policy, all real platform builds and P10/P11 publication remain external gates. Disable grants independently to recover; preserve P13 ledger/counters and Sheet layout. No production data migration or cleanup is added.
