# SelahCue installer publication design

Date: 2026-11-15. Status: engineering design for builder check; no implementation or publication performed. Existing authorization covers the Free release, Windows x64/macOS arm64+x64/Ubuntu 24.04 x64 installers through the existing CI and authorized reproducible local packaging paths, the installer Space, website links and owner-operated Coolify deployment. No new product decision is requested.

Root scope corrections, 2026-11-15: independent verification means a separate credential-free process using public HTTPS, not a mandatory second physical machine; final build provenance may be CI or the authorized reproducible local path. These correct this author's assumptions and are not new owner approvals. The [prior design](2026-11-15-installer-publication-design-before-root-scope-corrections.md) is retained unchanged with SHA-256 `76f0f2fab629929db6b7118c92415f1b9a81cf8919f11e852a74ef2534cfbbc3`.

## Outcome and boundary

Add a finite release-operator command that takes the **exact accepted cloud-enabled packages**, creates immutable public installer objects, verifies their complete anonymous responses through an independent credential-free process over the public HTTPS endpoint, and emits the existing website manifest. It must not turn a source review, private canary, synthetic test, filename or `passed:true` into native/provider qualification.

Keep provider credentials on the server. Installer write credentials exist only in the operator upload process; neither builds, packages, website, receipts nor anonymous verifier receive them. Do not implement a download service, custom SigV4, signing/notarization, CI deployment, bucket administration, translation publishing or new release approval workflow. Apple Developer ID/notarization are intentionally omitted. The owner still deploys manually through Coolify.

## Engineering choice and alternatives

**Choose Python standard library plus AWS CLI v2.** Existing packaging scripts are Python; `scripts/publish_translations.py:385-409` already demonstrates the CLI subprocess convention and checksum compatibility settings. Implement a separate installer module with its own closed destination and credential names; do not import, extend or invoke that publisher. Its overwrite/ACL retry behavior is unsuitable here. Use Node >=22.18 only to execute the website's real TypeScript parser locally.

An isolated boto3 publisher would offer structured service errors but introduce a new release dependency/lock surface (no boto3/botocore entry was found in the API dependency files inspected). Handwritten HTTP signing duplicates a maintained client and adds unnecessary credential-handling risk. A generic `aws s3 sync/cp` command would conceal conditional writes and multipart behavior. These are engineering choices, not additional user choices.

No new Python package is required. Require AWS CLI v2 with an offline service model exposing `PutObject.IfNoneMatch`; record the exact executable version. Pin the tested operator CLI version in the eventual implementation evidence. Before mutation, locally validate the command shape with `--generate-cli-skeleton input`, including ACL and header fields. Use `s3api put-object`, never a transfer manager. Cap each installer at **4,000,000,000 bytes**, a deliberately conservative application limit; larger input fails preflight and needs an explicit multipart design, not an implicit fallback. This cap is not a claim about actual candidate sizes.

## Closed command surface

Proposed new source: `scripts/publish_installers.py`, focused `scripts/test_publish_installers.py`, and `implementation/marketing/scripts/validate_release_manifest.ts` importing `parseReleaseManifest` directly. No existing build script is rewritten by this seam. Producers separately supply the normalized evidence described below.

```
python3 scripts/publish_installers.py prepare --input RELEASE_INPUT.json --source-tree CLEAN_CHECKOUT --out-dir RELEASE_DIR
python3 scripts/publish_installers.py upload --release-dir RELEASE_DIR
python3 scripts/publish_installers.py verify-public --plan PUBLIC_PLAN.json --out VERIFICATION.json
python3 scripts/publish_installers.py emit-manifest --release-dir RELEASE_DIR --verification VERIFICATION.json --out CURRENT_CANDIDATE.json
python3 scripts/publish_installers.py --self-test
```

All flags are required exactly as shown; no endpoint, bucket, prefix, arbitrary URL, credential, skip-validation, force, overwrite, target subset or publish-anyway flags. `prepare`, `emit-manifest` and self-test are offline. `upload` is the only mutating command. `verify-public` performs only bounded anonymous GETs to the fixed origin. Output paths are explicit regular files in caller-owned directories, never repository files selected implicitly. Refuse symlink input/output components, duplicate JSON keys, unknown/missing fields, non-finite numbers and unsupported schema versions. JSON input/evidence documents are bounded to 1 MiB each; public manifest to 64 KiB. Never execute command text found in receipts.

Exit codes: 0 means that command's named stage completed; 2 invalid input/provenance; 3 remote mismatch or forbidden operation; 4 transient/unknown remote outcome; 5 local/tool failure. None means website deployment or final release acceptance. Print a concise stage/result and receipt path; do not print raw service error bodies, credentials, signed request headers or debug traces.

`prepare` creates a new 0700 directory exclusively, snapshots the three packages into its private `packages/` directory, validates their hashes against independent build receipts, snapshots the referenced nonsecret evidence under `evidence/`, and writes `input.json`, `public-plan.json` and `prepare-receipt.json`. Copy from already-open regular file descriptors, check original identity/size/mtime before and after copying, and hash the copy. Refuse any source change. The retained immutable snapshot is the upload body. Do not infer bytes from file name or trust a writable original after preparation. Inputs/evidence originals remain retained independently.

`input.json` preserves the exact original input bytes. `PrepareReceiptV1` has exactly `{schema_version:1,input_sha256,plan_sha256,source_commit,publisher_source_sha256,created_at,packages,evidence}`. Each of the three package mappings is `{id,original_path,snapshot_path,size_bytes,sha256}`; each evidence mapping is `{original_path,snapshot_path,sha256}`. Snapshot paths are contained below `packages/` or `evidence/` respectively. Resolve original references through this complete mapping; never follow a stale path outside the snapshot on restart. Every recursively referenced evidence file must have a mapping. Evidence hashes bind originals, not a reserialized substitute. `publisher_source_sha256` covers the actual publisher source used, and its identity also appears in verification tool-version evidence. No private log or credential source is accepted as evidence.

`upload` acquires an exclusive local run lock, revalidates prepared inputs and all copied bytes, then handles the three installer objects sequentially. Local receipts are durably written with temp-file/fsync/atomic replacement and an append-only sequence of bounded operation events. Concurrent processes with another directory still cannot overwrite remote keys. A lost local lock is not evidence of a failed remote write.

`emit-manifest` revalidates all local evidence/digests, successful remote receipts and the exact plan hash. It calls the real website parser through the small Node script using an argv array, never a shell. It writes the candidate atomically only on success; it never edits `public/releases/current.json` or deploys. An existing output file is accepted only if byte-identical; otherwise refuse.

## Source and qualification input contract

All records below reject extra fields. `Ref = {path,sha256}` names a regular evidence file relative to the input directory, contained below it with no traversal/symlinks; hashes are lowercase SHA-256. Source refs are local bytes, not URLs fetched by the publisher. Timestamps are UTC RFC3339. Paths and strings are bounded to 4 KiB; arrays have the stated finite cardinality. Package paths obey the same containment rule.

```
ReleaseInputV1 = {
  schema_version: 1,
  release_id: string,
  version: string,
  source_commit: 40-lowercase-hex,
  profile: Ref,
  acceptance: Ref,
  artifacts: [WindowsArtifact, UniversalMacArtifact, UbuntuArtifact]
}
Artifact = {
  id: "windows" | "universalMac" | "ubuntu",
  path: string, filename: string, size_bytes: positive-integer, sha256: 64-lowercase-hex,
  build: Ref, inspection: Ref
}
BuildReceiptCommon = {
  schema_version: 1, artifact_id: Artifact.id,
  source_commit: 40-lowercase-hex, version: string, profile_sha256: 64-lowercase-hex,
  repository: string, toolchain: Ref,
  build_commands: [{cwd: string, argv: string[]}],
  build_log: Ref, build_input_custody: Ref, package_metadata: Ref,
  filename: string, size_bytes: positive-integer, sha256: 64-lowercase-hex
}
BuildReceiptV1 = BuildReceiptCommon & (
  {kind: "ci", workflow_path: string, workflow_sha256: 64-lowercase-hex,
   run_id: positive-integer, run_attempt: positive-integer, artifact_id_in_ci: string}
  | {kind: "local", build_id: string, operator: string,
     host_os: string, host_arch: "arm64" | "x64"}
)
ProfileV1 = {
  schema_version: 1, source_commit: 40-lowercase-hex, version: string,
  api_origin: "https://api.selahcueapp.com",
  entitlement_key_id: string, entitlement_public_key_sha256: 64-lowercase-hex,
  source_evidence: Ref,
  builds: [WindowsProfile, UniversalMacProfile, UbuntuProfile]
}
BuildProfile = {
  id: Artifact.id, target_triples: string[],
  command_argv: string[], default_features: boolean, selected_features: string[],
  resolved_features: Ref, release_boundary_check: Ref
}
InspectionV1 = {
  schema_version: 1, artifact_id: Artifact.id, package_sha256: 64-lowercase-hex,
  architectures: ["x64"] | ["arm64","x64"],
  architecture_evidence: Ref, version_evidence: Ref,
  app_signature: "unsigned" | "ad_hoc" | "verified" | "not_applicable",
  package_signature: "unsigned" | "verified",
  notarization: "not_notarized" | "not_applicable",
  publisher: string | null, signature_evidence: Ref,
  bundle_scan: Ref, payload_scan: Ref, development_key_scan: Ref,
  scan_positive_controls: Ref, build_input_custody: Ref
}
AcceptanceV1 = {
  schema_version: 1, source_commit: 40-lowercase-hex, version: string,
  profile_sha256: 64-lowercase-hex,
  artifacts: [{id: Artifact.id, sha256: 64-lowercase-hex}],
  reviewer: string, reviewed_at: UTC-timestamp,
  decision: "accepted_for_publication",
  gates: [{id: GateId, evidence: Ref}]
}
```

`release_id` is `[A-Za-z0-9][A-Za-z0-9._-]{0,95}`. Version is the exact packaged SemVer (including actual prerelease/build suffix if present), not a guessed release label. Match the version to build/package inspection on every platform and reviewed source configuration. The profile is a release-owner-produced snapshot of the **landed safe cloud build**, not a user-editable assertion that `stt` is sufficient. Each build has the exact resolved dependency/feature graph and default-feature choice for its separate Cargo root. Confirm the key ID and digest against the actual reviewed public-key bytes and emitted-package evidence; an ID such as the historically bundled `e506b735` alone does not qualify the package. No private key appears in these records.

`--source-tree` must identify the exact clean reviewed commit. Verify source/profile-linked paths and, for CI, workflow paths against that commit; check absence of uncommitted build-input changes. A dedicated clean checkout is the default. The tagged union is closed: CI rejects local-only fields, and local rejects CI-only fields. Both variants retain exact source, toolchain/dependency versions, ordered command argv and working directories, complete build logs, package metadata and build-input/output custody evidence. The toolchain reference includes SDK/compiler/bundler versions, lockfile digests and the architecture/toolchain configuration needed to repeat the build; no secret settings are retained. Command arrays are evidence, never instructions executed by the publisher.

For `kind:ci`, review the repository/run/attempt/artifact identity and workflow digest against the trusted CI result. For `kind:local`, retain a unique build ID (using the release-ID grammar), operator/host identity, the reviewed source snapshot and the exact command/toolchain/log/custody chain that produced the final bytes. The existing authorized reproducible local macOS wrapper is valid for this variant; CI is not mandatory for that artifact. A local build ID is not a fabricated CI run ID. Historical local-STT packages remain unqualified baselines until an actual final cloud-enabled build and native acceptance exist. Merely hashing a downloaded executable establishes neither CI nor local build provenance; both variants require the same final package and native acceptance gates.

Exactly three acceptance artifact entries must match input bytes. Exactly these gate IDs are required, each with retained concrete evidence: `reviewed-source-profile`, `build-artifact-custody`, `windows-native`, `macos-arm64-native`, `macos-x64-native`, `ubuntu-24.04-native`, `package-secret-controls`, `entitlement-key-enforcement`, `cloud-transcription`, `cloud-notes`, `quota-provider-reconciliation`, `presentation-offline-degradation`. Evidence must identify tested package digests, actual commands/scenarios/results and environments. Native acceptance includes install/run/upgrade where applicable/uninstall, output and runtime closure; record Windows SmartScreen/macOS Gatekeeper observations. macOS x64 acceptance must distinguish native Intel from emulation, never label emulation native. Cloud evidence preserves the existing final policy/cost/privacy criteria and historical failures. Reviewers, not the upload command, judge those test results against `DEPLOYMENT.md` and the existing delivery evidence.

**Trust boundary:** reference hashes prove custody and detect edits, not truth. The publisher validates closed shape, presence, identity and consistency; it cannot cryptographically authenticate a manually authored acceptance decision or rerun provider/native acceptance. The existing release coordinator must review the referenced evidence and prepare this record in a protected operator directory. There is no `qualified:true`, `--accept`, synthetic fallback or automatic conversion of scan success into acceptance. A forged JSON file is outside this trusted-operator boundary, not made trustworthy by a digest. Fixtures stay in isolated tests and cannot produce a production acceptance record. Final cloud-enabled acceptance is currently missing, so a real preparation run remains blocked even after implementation.

## Genuine universal macOS and signature mapping

Choose one universal DMG, `id=universalMac`, for this finite release. Both macOS rows use `architectures:["arm64","x64"]` in that order and the identical object URL, basename, size, digest and signature fields. Inspect the mounted **final DMG**, the operator executable, output sidecar and required bundled native libraries for the required slices; retain `hdiutil verify`, `lipo -archs`, and `codesign --verify --all-architectures --deep --strict` output. A file named `universal.dmg`, a cross-build target or a previous baseline receipt is insufficient. If either slice or runtime acceptance is missing, stop; do not publish a four-row manifest with two names for one thin package.

The macOS mapping is fixed: `app_signature:ad_hoc`, `package_signature:unsigned`, `notarization:not_notarized`, `publisher:null`. Windows requires x64 PE/application and installer inspection with actual Authenticode results; Ubuntu requires amd64 package metadata and x86_64 ELF/output inspection. For non-Mac targets, notarization is `not_applicable`; reject ad-hoc. A non-null publisher requires an independently verified signer and corresponding evidence; unsigned packages use null. No signer/vendor label is inferred from the product name. A Linux app signature may be `not_applicable`; package-signature state must be observed.

## Deterministic objects and headers

Fixed bucket `selahcue-installers`, API endpoint `https://sfo3.digitaloceanspaces.com`, signing region `sfo3`, public origin `https://selahcue-installers.sfo3.digitaloceanspaces.com`. Object keys are exactly:

```
installers/<version>/<installer-sha256>/<actual-basename>
```

Encode each URL path segment once using UTF-8 percent encoding with only RFC3986 unreserved characters left literal; include version and digest as complete segments. Restrict actual basenames to ASCII `[A-Za-z0-9][A-Za-z0-9._ ()+-]{0,179}`, no trailing dot/space, dot-only segments, slash, backslash, quote or controls. This accepts existing space-containing package names safely; it does not rename a package. Enforce `.exe`/`.dmg`/`.deb` extensions for the respective IDs. If a producer emits an unsupported name, fix that producer before acceptance. Version must not contain path separators.

The three accepted packages and the website manifest already expose complete hashes. No separate checksum object is required; it is an optional later addition, never a release gate in this seam. The root runbook permits a matching checksum list **or release manifest**; the existing website manifest supplies the latter. No mutable `latest`/`current` object is written to Spaces.

| Object | Content-Type | Content-Disposition | Cache-Control |
| --- | --- | --- | --- |
| Windows `.exe` | `application/octet-stream` | `attachment; filename="<actual-basename>"` | `public, max-age=31536000, immutable` |
| macOS `.dmg` | `application/x-apple-diskimage` | same | same |
| Ubuntu `.deb` | `application/vnd.debian.binary-package` | same | same |

Create each object with `ACL=public-read`, full Content-Length, those exact headers and **`If-None-Match:*` on every PUT**. Omit Content-Encoding, website redirects and custom metadata. This exposes only already accepted exact objects; a partially uploaded release may have unadvertised public objects, but no incomplete website manifest. There is no bucket ACL/policy change, public listing, staging object, delete, copy, multipart or overwrite operation. Immutability here is enforced by this command, not a claim that the bucket's credential owner can never delete/replace objects.

The upload subprocess receives an explicit minimal environment: map only `INSTALLER_S3_ACCESS_KEY`/`INSTALLER_S3_SECRET_KEY` to AWS credential variables, set fixed region, disable metadata/interactive prompting/pager, set empty isolated AWS config/shared-credential files, remove session/profile/web-identity/container credentials and endpoint/proxy overrides, set `AWS_MAX_ATTEMPTS=1`, and use the repository's `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` / `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`. No shell, no `--debug`, no command-line credential arguments. TLS verification stays enabled. Do not read any `.env` automatically. Credential loading remains the existing operator's protected-secret procedure.

The only allowed authenticated operations are `head-object`, `get-object-acl` and `put-object`. Each receives `--bucket selahcue-installers --key <derived-key> --endpoint-url https://sfo3.digitaloceanspaces.com --region sfo3 --no-cli-pager --output json --cli-connect-timeout 30 --cli-read-timeout 120`. PUT additionally receives `--body <snapshot-path> --content-length <verified-size> --if-none-match '*' --acl public-read --content-type <type> --content-disposition <attachment> --cache-control 'public, max-age=31536000, immutable'`. The displayed quotes denote argument boundaries; actual execution uses an argv array with literal `*`. Never invoke `aws s3 cp/sync`. With `AWS_MAX_ATTEMPTS=1`, only the explicit reconciliation loop below may issue another write; test this environment and argument invariant through the fake adapter. Parse the CLI's service error code narrowly (`PreconditionFailed`, `ConditionalRequestConflict`, `NoSuchKey`/object 404); unrecognized errors are unknown/failure, never success or absence.

CLI connect/read timeouts are 30/120 seconds; enforce a 60-minute wall deadline per complete upload and at most three conditional PUT attempts per object per invocation. Use bounded subprocess output and a 4 KiB redacted diagnostic limit. Kill/reap timed-out subprocesses, then reconcile remotely; never assume the timeout means no write.

## Idempotency and uncertain writes

Local state is a restart aid, never remote truth. For each object:

1. Authenticated HEAD and object ACL read. Only an explicit object-not-found response permits initial create; permission failures, malformed responses or transient errors stop/reconcile rather than being treated as absence. A preflight HEAD is not the no-overwrite protection.
2. If absent, make the conditional PUT. On success, record its observed completion and re-read headers/ACL. On `412`, treat it as an existing-object race. On timeout, connection loss, `409` or `5xx`, mark `write_outcome_unknown` and probe the exact key. Do not change keys or remove the condition.
3. If present, require exact size/headers and object ACL (owner full control plus AllUsers READ; no public WRITE or authenticated-users grant), then perform complete anonymous byte/hash verification. Matching bytes/headers may be adopted as an existing object; record `reused_verified`. ETag alone, metadata digest or length alone is never enough. The current process's PUT result may remain unknown even when the desired remote object is independently verified.
4. If a reconciliation HEAD explicitly reports missing, a bounded retry uses the same key and same conditional PUT. A delayed first request cannot authorize an overwrite. Retry delays are 1 then 3 seconds; after three attempts or any ambiguous probe, stop with exit 4 and retain evidence. A later invocation repeats verification.
5. Existing bytes, ACL or headers that differ are a hard conflict. Never repair by re-upload, copy, delete or `put-object-acl`; this also prevents an ordinary retry from undoing an operator's deliberate takedown. A conflict requires owner reconciliation outside the publisher, not an automatic new URL for the same bad receipt.

Do not remove completed objects if a later object fails. Receipt serialization failures after a PUT follow the same reconciliation path on restart. Rehash snapshots before each attempt and after sending; no manifest is possible if local bytes changed. Retained read-only snapshots and a trusted operator process are the local custody boundary.

## Anonymous verifier and closed output receipts

`public-plan.json` contains only `{schema_version:1,release_id,version,source_commit,objects}`. `objects` has exactly three entries, ordered `windows`, `universalMac`, `ubuntu`, each `{id,key,url,filename,size_bytes,sha256,content_type,content_disposition,cache_control}`. Values are derived, not independently supplied. Recompute each key/URL from its version/digest/name. Serialize deterministic JSON (UTF-8, sorted object keys, compact separators, one trailing LF); the hash of those exact bytes is `plan_sha256`.

`upload-receipt.json` has exactly `{schema_version:1,plan_sha256,input_sha256,prepare_receipt_sha256,tool_version,started_at,finished_at,objects}`. Each object entry is `{id,key,sha256,size_bytes,put_outcome,head,acl,anonymous_readback}`. `put_outcome` is `created|reused_verified|unknown_but_verified`; `head` is `{content_type,content_disposition,cache_control,content_length,content_encoding,request_id}` (encoding null, request ID string or null); `acl` is `{owner_id,grants}`, with each normalized grant `{grantee_type,grantee_id,permission}` and exactly the owner `CanonicalUser/FULL_CONTROL` and AllUsers `Group/READ` grants. `anonymous_readback` uses the per-object verification record below. Emit this complete receipt only after all three objects pass; retain separate journal events for failures/partial uploads. Do not fabricate a request ID or HTTP status if AWS CLI does not expose one.

The upload stage's anonymous reconciliation runs the same byte reader in a fresh child process whose environment excludes every credential, receiving only the exact public object plan on stdin. Its readback is upload/reconciliation evidence. A separate `verify-public` invocation supplies independent anonymous full-byte verification outside the authenticated SDK path. It may run on the same physical machine in a fresh credential-free process; the upload receipt, independent verification receipt and final browser evidence remain distinct. A separately operated external machine is useful supplementary evidence when available, not a launch prerequisite.

Run `verify-public` in an independent process without installer/provider credentials, using only the public plan and verifier code against the public HTTPS endpoint. The same physical host is allowed; no Spaces client or authenticated SDK path participates. It rejects credential-bearing environment variables and makes requests using Python HTTPS primitives with no credential lookup, `.netrc`, cookie jar, proxy inheritance, redirects, decompression or ambient Authorization. Production destination is fixed; loopback injection exists only in tests, never through a production CLI flag.

GET each exact URL with `Accept-Encoding: identity`, no Range or conditional request. Require HTTP 200, no redirects, exact positive Content-Length, expected MIME/charset, exact attachment filename, equivalent cache directives, and absence of Content-Encoding. Reject duplicate conflicting critical headers, HTML/XML error bodies and chunked/length ambiguity. Stream 1 MiB chunks into SHA-256; bound reads to expected length plus one byte and require EOF at exactly the expected length. Do not hold installers in RAM. Enforce 30-second connect, 60-second inactivity and 60-minute total deadlines per object, maximum three full attempts, no range resumes; each retry restarts hashing. Check absolute deadline on every chunk, not just socket timeout. Larger-than-plan responses abort immediately. A quick HEAD or a first-megabyte hash does not qualify delivery.

`VerificationV1` is exactly `{schema_version:1,plan_sha256,verifier_version,started_at,finished_at,objects}`. Three ordered object records are exactly `{id,url,http_status,headers,observed_size_bytes,observed_sha256,completed_at}`. `headers` is `{content_type,content_disposition,cache_control,content_length,content_encoding}` with observed encoding null; `http_status` must be 200 and observations must equal the plan. Retain the verifier invocation, sanitized process context, operator/host identity and original terminal result as independent release evidence, not inferred from this JSON. If a separate external machine is used, record it as supplementary coverage. Report hashes and shapes alone cannot prove the verifier actually ran anonymously. A self-authored verification file is not a substitute for executing and reviewing the real verifier. Failure emits no successful verification document; bounded diagnostics identify the failed object/stage without rendering response bodies.

## Website manifest and manual deployment handoff

Only after all acceptance, upload and independent anonymous verification evidence agrees does `emit-manifest` create:

```
{schema_version:1,status:"published",release_id,version,source_commit,artifacts:[
  windows-x64, macos-arm64, macos-x64, ubuntu-24.04-x64
]}
```

Each artifact has **only** `{target,architectures,url,filename,size_bytes,sha256,app_signature,package_signature,notarization,publisher}`. These are projections of the accepted inspection and observed object records, not operator-entered URLs. Four targets appear exactly once; only the genuine universalMac pair shares an object. Pass the generated bytes through `implementation/marketing/src/lib/releases/downloads.ts:136-174` using the imported parser. Unknown fields, partial target sets, unsupported origins or inconsistent shared macOS metadata must fail. Keep private evidence in the handoff receipt, not as extra website schema fields.

The website owner reviews/copies the exact candidate bytes to `implementation/marketing/public/releases/current.json` through the existing delivery path, runs its focused parser/download tests, and gives the owner the website commit/manifest digest for manual Coolify deployment. Until then the website stays at its current unpublished manifest (or an existing complete prior release, if one has since deployed). No automatic commit/deploy is part of the publisher.

After manual deployment, independently fetch the same-origin manifest without credentials and verify its complete bytes/hash, JSON Content-Type and `no-cache, must-revalidate`. Verify home/download cards show all four intended links, hashes, versions and signature caveats. In a browser without installer credentials, follow each exact link and repeat full bytes/header verification through the independent credential-free verifier; the universal object can be downloaded once while both link destinations are checked. Retain deployment identity and screenshots/response evidence separately from upload and verifier receipts. A separately operated external browser/machine can add coverage but is not required. Install the publicly downloaded packages and complete any remaining public-download Gatekeeper/SmartScreen/native journey acceptance. Source tests, object availability and live website/native acceptance remain separate reported stages.

## Small, isolated verification scope

Use Python `unittest`, temporary directories, an injected fake AWS subprocess and a bounded loopback HTTP server. No AWS/Spaces calls in self-test or CI unit tests; no real secrets, package builds or provider calls. Cover behavior, not command-string snapshots alone:

- CI/local receipt variants reject mixed or missing tag-specific fields; neither variant bypasses package/native acceptance. Inconsistent build/profile/source/version/hash or acceptance evidence is rejected before any remote operation; missing cloud acceptance cannot be replaced by a Boolean. Reject symlinks/traversal, duplicate JSON fields, unsafe filenames, oversized inputs and snapshot mutation.
- Initial conditional create; existing exact object reuse; concurrent `412`; response loss after successful write; loss before write; `409`/`5xx`; permission failure versus 404; bounded exhaustion; crash after PUT before journal save; two simultaneous publishers. Assert no unconditional PUT, delete/copy/ACL repair or extra destination operation is ever emitted.
- Three-package partial failure leaves no manifest. Restart preserves verified objects but rechecks remote bytes/headers. Private/taken-down object or mismatched headers is not silently republished.
- Anonymous response with redirects, auth challenge, wrong MIME/disposition/cache, encoding, duplicate headers, truncated/oversized/slow stream, same-length wrong bytes is refused. Record bounded memory and deadlines with small fixtures.
- A real universal inspection projects to four parser-valid rows; thin-Mac evidence, altered shared metadata, missing target and wrong host fail. Execute the real TypeScript parser; no second permissive Python manifest validator is the final authority.
- Credential isolation tests use fake marker values and ensure they reach only the intended fake upload child, never argv/logs/verifier/artifacts. The same-host independent verifier must succeed only with a credential-free process and retain a distinct receipt; merely reusing the uploader receipt fails. These are synthetic safety controls, not emitted-package secret scans or cloud qualification.

Later real acceptance uses the exact final artifacts and authorized Space, not a new canary. Retain upload receipt, independent anonymous verification receipt, matching public manifest, parser validation, manual deployment receipt and real public-download evidence. Any provider limitation encountered fails closed; tests or earlier private canary success cannot waive it.

## Concrete source gaps and their resolution

| Gap established by source locator | Resolution / owner boundary |
| --- | --- |
| No installer-specific publisher or anonymous verifier | Add the finite command and tests above after builder check. |
| Windows metadata omits version/size/profile/key/signature evidence; Linux has more fields but local-only profile | Build owners emit normalized BuildReceipt/Profile/Inspection for the actual final CI output. Keep existing receipts as inputs/evidence; do not reinterpret them as accepted. |
| macOS baseline is local, without a normalized final package receipt | Build owner supplies the closed local receipt with exact reviewed source/toolchain/commands/logs/custody, final universal package and both-slice inspections using the authorized wrapper; a real CI receipt is also valid if built in CI. No CI migration, invented run identity or acceptance is required. |
| Final safe cloud profile not landed/qualified in located baseline | Native/build owner supplies exact reviewed profile and emitted-package evidence; publisher validates identity without guessing a feature combination. This is a dependency, not a new product question. |
| Provider/native final acceptance still pending | Existing release coordinator supplies evidence-backed AcceptanceV1 only when existing release gates genuinely pass. Preserve previous failed/unknown gates. |
| Private canary proves conditional private create/refusal, not public delivery | Real conditional uploads plus ACL/header/full anonymous readback verify public behavior; no new check was run during design. |
| Website manifest remains unpublished | Generate candidate only from completed receipts, then normal website delivery and owner manual deployment. |

No unresolved user-facing engineering question remains. Builder check should resolve schema/implementation ambiguity before an implementation plan is written. This document itself grants no new remote action and is not an implementation plan. The design task intentionally stops here; independent builder review is coordinated by the parent, with no additional agents spawned by this author.

## Source pointers and externally verified limits

The authoritative [locator report](../release-evidence/installer-publication-seam-20261115.md) fixes provider checkout `caa1b42fb21d7943e5104c9c61e4a26954a82c53` and website checkout `2d8e0a856117135d2d758a4778387da34e87b455`. It distinguishes working-tree edits and source evidence from tests/deployment. Relevant exact interfaces inspected for this design:

- Website checkout `/Users/m.oluwole/.codex/worktrees/selahcue-public-download/scph`: `implementation/marketing/src/lib/releases/downloads.ts` (closed parser/manifest), `docs/superpowers/plans/2026-11-14-free-public-website.md` shared contract and Task1. Four rows, 64 KiB, approved host and observed signature constraints are existing consumer requirements.
- Provider checkout `/Users/m.oluwole/.codex/worktrees/selahcue-provider-qualification/scph`: `DEPLOYMENT.md:206-221` (private canary and package/publication obligations), `docs/superpowers/plans/2026-11-14-native-public-cloud.md:219` (profile/key/source gap), operator `Cargo.toml` feature definitions. No `.env`, secrets or private provider settings were inspected.
- Packaging pointers retained from the locator: `.github/workflows/windows-installer.yml:66-87,212-220,264-277`; `.github/workflows/linux-installer.yml:44-102`; `scripts/build_linux_installer.py:191-211`; `scripts/build_macos_installer.py:104-121,159-186`. These are baselines, not final accepted packages.
- Current design workspace: `scripts/publish_translations.py:385-409` demonstrates AWS CLI dependency/use only; `scripts/check_installer_features.py` enforces literal feature/default matching and explicitly does not prove a Windows build; marketing `package.json` provides Node >=22.18 and TypeScript test conventions. API dependency manifests inspected contained no boto3/botocore dependency.

Primary documentation checked on 2026-11-15, without any real AWS/Spaces API call:

- [DigitalOcean S3 compatibility](https://docs.digitalocean.com/products/spaces/reference/s3-compatibility/) describes partial S3 compatibility and per-object `public-read`. It does not establish this bucket's public policy or final response behavior.
- [DigitalOcean Spaces API](https://docs.digitalocean.com/reference/api/spaces/) documents PutObject content/cache/disposition/ACL fields. Its PutObject supported-header table inspected here does **not** explicitly list If-None-Match; do not extrapolate the HEAD entry. Conditional private PUT/412 support in this exact bucket is the separate recorded canary evidence; combined public-read/headers and final artifact sizes remain real-upload checks.
- [AWS CLI PutObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-object.html) exposes `--if-none-match`, ACL and content/cache/disposition flags, describing S3's `412`/`409` outcomes. These are CLI/AWS semantics, not a guarantee of every Spaces implementation detail. No claim is made that a successful CLI result proves anonymous bytes.
- [AWS CLI environment settings](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) documents `when_required` checksum modes. Existing repository compatibility settings are retained; final CLI-version/Spaces behavior is checked during the actual authorized upload, not assumed from the historical comment.

Document hashes identify this design and source evidence only. They do not establish final installer qualification, publication or deployment.
