# Installer Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Preserve the root coordinator's supplied execution method: one source task at a time after backend/website priorities. This plan does not authorize additional agents, remote checks, uploads, package builds or deployment.

**Goal:** Implement the finite installer publisher that prepares accepted package evidence, conditionally uploads three immutable objects, independently verifies public bytes, and emits the existing four-target website manifest.

**Architecture:** A thin Python CLI delegates to a small installer-specific package for contracts/preparation, anonymous verification, conditional upload/recovery and manifest projection. AWS CLI v2 owns signing; Python owns finite state/reconciliation, and the actual website TypeScript parser remains the final manifest authority. Source tests use fake subprocesses and loopback HTTP only; manual deployment and real acceptance stay distinct.

**Tech Stack:** Python standard library/unittest; existing AWS CLI v2 convention; Node >=22.18 for the existing TypeScript parser. No new Python, npm or service dependency.

**Spec:** [Accepted installer publication design](2026-11-15-installer-publication-design.md), SHA-256 `686498a1ed1881ad5f11266341190a14ad30810f51d46aa6cfd1958daf661ea1`. Root accepted that engineering design under existing release authorization after the [independent builder check](installer-publication-builder-check-20261115.md) returned “nothing important left.” These documents travel together when integrated into the future worktree; leave accepted design bytes unchanged.

**Amendment, 2026-11-15:** Root's plan review found that CI does not automatically discover new Python script tests. Task4 now owns only the existing marketing path-filter additions and one offline self-test step in `.github/workflows/ci.yml`. This runs already specified source checks in existing CI; it adds no runner, job, dependency, deployment or product/release prerequisite. Accepted design bytes are unchanged.

## Global Constraints

- Exactly three physical artifacts, `windows`, `universalMac`, `ubuntu`, and four manifest targets, `windows-x64`, `macos-arm64`, `macos-x64`, `ubuntu-24.04-x64`. Universal Mac requires real both-slice evidence; macOS signatures are `ad_hoc`, `unsigned`, `not_notarized`, publisher null. No signing/notarization implementation.
- Fixed bucket `selahcue-installers`, API endpoint `https://sfo3.digitaloceanspaces.com`, signing region `sfo3`, public origin `https://selahcue-installers.sfo3.digitaloceanspaces.com`. Keys are `installers/<version>/<installer-sha256>/<actual-basename>`; conditional `If-None-Match:*` applies on every PUT.
- No overwrite/delete/copy/multipart/ACL repair/bucket-policy operations; no translation publisher, credentials, imports or configuration reuse. No separate checksum object is required. No download service, CI deployment, extra product approval or runtime gate.
- Installer limit **4,000,000,000 bytes**; JSON input/evidence documents **1 MiB** each; public manifest **64 KiB**. Preserve exact release-ID/basename grammars, SemVer and one-time URL encoding from the design. Reject duplicate keys, unknown fields, non-finite values, symlinks/traversal and changed snapshots.
- Closed `BuildReceiptV1` CI/local union: real CI identities for CI; reviewed source/toolchain/commands/logs/custody for the authorized reproducible local path. No invented run IDs. Native/provider acceptance remains mandatory for both. Evidence hashes establish custody, not truth or qualification.
- Only `upload` receives `INSTALLER_S3_ACCESS_KEY` and `INSTALLER_S3_SECRET_KEY`; no `.env` loading, secret values in argv/logs/receipts or inherited AWS profiles/metadata credentials. `AWS_MAX_ATTEMPTS=1`; checksum modes `when_required`; TLS verification stays enabled.
- Allowed authenticated operations are exactly `head-object`, `get-object-acl`, `put-object`, with the design's fixed endpoint/region/bucket and content arguments. CLI connect/read limits are **30/120 seconds**, upload wall deadline **60 minutes**, maximum **three conditional PUT attempts** with **1 then 3 second** retry delays. Ambiguous writes are reconciled before another write.
- Anonymous GET uses public HTTPS outside the authenticated SDK, `Accept-Encoding: identity`, HTTP200, exact byte count/hash/headers and EOF; no redirects, auth, cookies, proxy inheritance, decompression or range resumes. **1 MiB** chunks; expected-size-plus-one bound; **30-second connect**, **60-second inactivity**, **60-minute total** per object, maximum **three full attempts**. A fresh credential-free process on the same host is allowed; another physical machine is supplementary.
- Only these public commands exist: `prepare --input --source-tree --out-dir`, `upload --release-dir`, `verify-public --plan --out`, `emit-manifest --release-dir --verification --out`, `--self-test`. Preserve exact exit codes **0/2/3/4/5** and meanings from the design. No skip/force/endpoint/subset/settings additions.
- `Content-Type` is Windows `application/octet-stream`, macOS `application/x-apple-diskimage`, Ubuntu `application/vnd.debian.binary-package`; disposition is `attachment; filename="<actual-basename>"`; cache is `public, max-age=31536000, immutable`; encoding absent. Object-only public-read ACL and full anonymous readback are required.
- Source implementation may produce synthetic receipts only inside temporary tests. No real acceptance, production manifest, upload or deployment is produced by these tasks. Private/source receipts, upload receipts, independent anonymous receipts and final browser/native evidence remain separate.
- Task4 wires the existing offline self-test into the existing marketing CI job after Node/Python setup and npm install, with repository-root working directory. Preserve desktop filters, tier/minute routing, permissions, runners and all unrelated steps; normal marketing Node tests discover the new TypeScript test.

## Review Focus

1. Mixed CI/local receipt fields or stale evidence references must fail before any remote operation; a clean new hash must not launder an unqualified build (Task1).
2. A response that trickles forever, lies about length, duplicates critical headers or returns the right length with wrong bytes must be bounded and rejected (Task2).
3. PUT success followed by a lost response or failed journal write must recover by exact-object verification, with no hidden retry or overwrite; private/taken-down objects stay private (Task3).
4. Same-host independent verification must have a fresh credential-free process and a separate receipt; uploader state alone cannot satisfy it (Tasks2/4).
5. Missing/altered Mac slices, stale verification or a parser rejection must leave no candidate manifest and must not modify an existing website manifest (Task4).

---

## Execution baseline and ownership

Root will choose the actual integration base and create an isolated worktree later. Do not fabricate a base SHA, create a worktree, install dependencies or resolve backend/website changes during planning. At execution, read applicable `AGENTS.md`, verify design hash, inspect only the owning interfaces and record actual base/head. Use the locator report as the existing source map. Ensure the reviewed website parser has landed before Task4; do not copy its source from another checkout or write a replacement validator.

All paths below are relative to the future repository root. The small package split is an implementation organization choice within the accepted design's proposed source table: contracts and custody, network byte verification, write recovery and consumer projection change for different reasons. It avoids one large publisher file while creating no reusable generic framework.

| Source file | Sole responsibility | Owner slice |
| --- | --- | --- |
| `scripts/installer_publication/__init__.py` | Package marker, no import side effects | 1 |
| `scripts/installer_publication/contracts.py` | One closed schema/type boundary, exact constants, canonical JSON and evidence identity rules | 1 |
| `scripts/installer_publication/prepare.py` | Source/evidence validation, immutable snapshots and prepare receipt | 1 |
| `scripts/installer_publication/public_verify.py` | Bounded anonymous byte reader and credential-free child protocol | 2 |
| `scripts/installer_publication/upload.py` | Minimal AWS adapter, lock/journal, conditional write/reconciliation state machine | 3 |
| `scripts/installer_publication/manifest.py` | Accepted-record projection and real parser subprocess; atomic candidate output | 4 |
| `scripts/publish_installers.py` | Only the five accepted CLI forms and exit/diagnostic routing | 4 |
| `implementation/marketing/scripts/validate_release_manifest.ts` | Read bounded file, import/call real parser, report success/failure | 4 |
| `scripts/_installer_publication_fixtures.py` | Explicitly synthetic temp evidence, fake transport and clocks for tests only | 1, then sequential extensions by 2–4 |
| `scripts/test_installer_publication_{prepare,verify,upload,cli}.py` | Four focused Python suites | Corresponding slice |
| `implementation/marketing/tests/installerPublicationManifest.test.ts` | Real parser/validator integration with synthetic fixture files | 4 |
| `.github/workflows/ci.yml` | Only `changes` marketing filter publisher paths and one marketing offline self-test step | 4 |
| `docs/delivery/evidence/installer-publisher-source.md` | Actual implementation SHAs/checks, source-only limits and later manual handoff | 4 |

Workflow ownership is limited to the Task4 filter/step above. No other workflow, packaging script, root `DEPLOYMENT.md`, release ledger, dependency manifest, production `current.json`, website component or translation source is owned by this plan. Workers are not alone: preserve other edits; shared fixtures and imports change sequentially. Each slice gets its own commit/review before the next, with remediation re-reviewed through root's existing method.

## Shared types and interface rules

Task1 owns the only JSON schema/type definitions. Use immutable dataclasses for validated internal records and explicit closed readers/serializers for the design's `ReleaseInputV1`, tagged `BuildReceiptV1`, `ProfileV1`, `InspectionV1`, `AcceptanceV1`, `PrepareReceiptV1`, public plan, upload receipt and verification receipt. Do not add a schema dependency or invent a second permissive JSON validation layer. Arbitrary source logs remain hash-bound files, not executable instructions.

Internal names are fixed for downstream tasks:

- `ArtifactId = Literal["windows", "universalMac", "ubuntu"]`; `JsonValue` is the recursive union of JSON null/bool/finite-number/string/list/string-keyed-object values. `Ref`, `ReleaseInput`, `BuildReceipt`, `Profile`, `Inspection`, `Acceptance`, `PrepareReceipt`, `PublicPlan`, `ObjectPlan`, `ObjectAcl`, `HeadObservation`, `VerifiedObject`, `VerificationReceipt`, `UploadedObject`, `UploadReceipt` map field-for-field to the accepted design. `HeadObservation.request_id` is nullable, never invented. `VerifiedObject` is the design's per-object verification record; `UploadedObject` is one entry of `UploadReceipt`.
- `PreparedRelease(root: Path, input: ReleaseInput, profile: Profile, inspections: tuple[Inspection, ...], acceptance: Acceptance, prepare_receipt: PrepareReceipt, public_plan: PublicPlan)` stores the validated snapshot; original references resolve only through the prepare mapping.
- `PublicationError(exit_code: int, reason: str)` carries bounded safe diagnostics; accepted codes are 2–5. Raw response bodies and credential material must never enter `reason`.
- `canonical_bytes(value: JsonValue) -> bytes`, `parse_release_input(raw: bytes) -> ReleaseInput`, `parse_public_plan(raw: bytes) -> PublicPlan`, `parse_verification(raw: bytes) -> VerificationReceipt`, `parse_upload_receipt(raw: bytes) -> UploadReceipt` enforce the design's exact field sets and bounds. Nested readers for build/profile/inspection/acceptance/preparation are owned by the same module, not duplicated elsewhere.
- `prepare_release(input_path: Path, source_tree: Path, out_dir: Path) -> PreparedRelease` and `load_prepared_release(release_dir: Path) -> PreparedRelease` perform the complete source/snapshot/evidence checks. The latter rehashes retained mappings and rejects altered content; it never follows original external paths.

All injected transports/clocks/process runners below are internal test seams, never CLI overrides. Production paths supply only fixed implementations. Default arguments must not initialize network clients or load credentials on import.

### Task 1: Closed evidence contracts and preparation

**Files:** Create package marker, `contracts.py`, `prepare.py`, synthetic fixture helper and `test_installer_publication_prepare.py` from the ownership table.

**Interfaces:** Produces all shared types/readers above and both preparation functions. No remote transport dependency. Fixed-argv Git inspection verifies the exact source/workflow/profile references; receipt command arrays are never executed.

- [ ] **Write RED tests** named `test_ci_local_union_rejects_mixed_identity`, `test_missing_native_acceptance_is_not_a_boolean_override`, `test_source_profile_version_key_and_artifact_identity_must_agree`, `test_prepare_snapshots_and_reloads_without_original_paths`, `test_duplicate_keys_bounds_symlinks_and_mutation_fail_closed`. Build only synthetic 3-package fixtures in temporary directories and a tiny temporary Git repository; include valid CI and local cases plus thin-Mac evidence. Assert mismatches fail before any remote adapter exists.

```python
with self.assertRaises(PublicationError) as failure:
    prepare_release(fixture.with_local_run_id(), fixture.source_tree, fixture.output)
self.assertEqual(failure.exception.exit_code, 2)
self.assertFalse((fixture.output / "prepare-receipt.json").exists())
```

- [ ] **Run RED:** `python3 -m unittest discover -s scripts -p 'test_installer_publication_prepare.py' -v`. Confirm the intended missing-contract/behavior failure; do not count an unrelated interpreter/import environment failure as evidence.
- [ ] **Implement closed records/readers/constants** in `contracts.py`. Pin the complete design field sets, three/four cardinalities, CI/local tagged union, signature rules, key/name encoding and expected object headers. Purely validate copied acceptance evidence identities; do not pretend to validate the truth of reviewer decisions. Positive verification/upload fixture records can be parsed here, but no runtime receipts are emitted by this module.
- [ ] **Implement preparation/custody** in `prepare.py`: bounded input reads, safe contained regular-file references, source identity and clean build-input checks, 0700 exclusive snapshot directory, descriptor-based copy/hash/change detection, complete recursive evidence mapping and durable atomic prepare files. Use exact original input bytes and canonical public-plan bytes for their respective hashes. On refusal, leave no complete prepare receipt; partial private files confer no success.
- [ ] **Run GREEN:** repeat the focused command; require all named tests pass, including successful reload after the original fixture directory is unavailable and rejection after any snapshot/evidence mutation. No fixture value is copied to production metadata.
- [ ] **Commit/review:** stage only the five Task1 files and commit `feat: prepare installer publication evidence`. Record actual test result and head SHA for the reviewer; address findings before Task2.

### Task 2: Bounded anonymous verifier and process isolation

**Files:** Create `public_verify.py`, `test_installer_publication_verify.py`; extend only the synthetic fixture helper as required. Consume Task1 types without changing their JSON contracts.

**Interfaces:** `verify_object(obj: ObjectPlan) -> VerifiedObject` performs production HTTPS verification. `verify_public_plan(plan: PublicPlan) -> VerificationReceipt` verifies all three in order. `verify_object_in_child(obj: ObjectPlan) -> VerifiedObject` starts a fresh sanitized process for upload reconciliation. Internal `worker_main() -> int` reads one bounded object-plan JSON from stdin and writes one bounded verified-object JSON to stdout; it is a fixed programmatic child entry point, not a new public command. Both paths call the same private `_verify_object(obj: ObjectPlan, connector: Callable, clock: Callable[[], float]) -> VerifiedObject`; its production wrapper supplies only the fixed HTTPS connector and monotonic clock. Loopback/fake-time test injection never changes the production CLI destination rules.

- [ ] **Write RED tests** named `test_exact_full_bytes_headers_and_eof_required`, `test_redirect_auth_encoding_and_duplicate_headers_refused`, `test_size_plus_one_and_total_deadline_are_bounded`, `test_retry_restarts_hash_and_has_finite_attempts`, `test_same_host_child_has_no_credentials_or_ambient_sdk`. Exercise tiny loopback bodies and a fake monotonic clock; same-length corrupted bytes, premature EOF, oversized bytes, slow drip, absent/incorrect length and conflicting transfer framing must fail. Assert complete observed digest/length on success, not just HTTP200.

```python
with self.assertRaises(PublicationError):
    _verify_object(fixture.object, fixture.wrong_bytes_connector, fixture.clock)
self.assertLessEqual(fixture.wrong_bytes_connector.bytes_read, fixture.object.size_bytes + 1)
self.assertEqual(fake_retry.attempts, 3)
self.assertEqual(fake_retry.range_requests, [])
```

- [ ] **Run RED:** `python3 -m unittest discover -s scripts -p 'test_installer_publication_verify.py' -v`. Require failures at the specified verifier behavior/interface.
- [ ] **Implement the byte reader** with HTTPS primitives, exact header/framing checks, bounded 1 MiB streaming SHA-256, expected-length-plus-one/EOF guard and design deadlines/retry count. Retries discard all prior digest state; nonretryable mismatches fail immediately. Preserve failed stage/object only, never response bodies. Serialize complete successful verification receipts only after all three objects pass.
- [ ] **Implement fresh-process isolation** using a fixed subprocess argv and sanitized environment with no credential/profile/proxy inheritance; pass only the object plan on stdin. Reject credential-bearing environment in independently invoked verification. Bound child input/output, kill/reap on deadline and do not render child error bodies. The spawned reader does not import or initialize AWS code.
- [ ] **Run GREEN:** repeat focused verifier tests, then Task1's focused tests once because shared types/fixtures are consumed. Confirm process tests use fake marker credentials, assert no marker in argv/stdout/stderr/receipts, and succeed on the same physical host without SDK access. They do not imply real remote verification.
- [ ] **Commit/review:** stage Task2 files plus fixture changes only; commit `feat: verify installer downloads anonymously`. Resolve review findings before Task3.

### Task 3: Conditional upload, receipts and restart reconciliation

**Files:** Create `upload.py`, `test_installer_publication_upload.py`; extend fixture helper sequentially. Consume preparation, closed receipt types and credential-free child verifier.

**Interfaces:** `upload_release(release_dir: Path) -> UploadReceipt` is the production entry. `AwsCli.head(obj: ObjectPlan) -> HeadObservation | Missing`, `AwsCli.acl(obj: ObjectPlan) -> ObjectAcl`, `AwsCli.put(obj: ObjectPlan, snapshot: Path) -> PutOutcome` are the only remote adapter methods. `Missing` is a sentinel produced only for an explicit object-not-found response. `PutOutcome = Literal["created", "exists", "conflict", "unknown"]`; denied/malformed/unrecognized failures raise `PublicationError` with the design's code. Internal `reconcile_object(obj: ObjectPlan, snapshot: Path, aws: AwsCli, verify: Callable[[ObjectPlan], VerifiedObject], journal: Journal) -> UploadedObject` owns the finite transition loop; `UploadedObject` is exactly one entry of `UploadReceipt`. `Journal` is a local upload implementation detail, not another public contract or service.

- [ ] **Write RED tests** named `test_all_puts_are_conditional_and_cli_retries_disabled`, `test_412_reuses_only_matching_anonymous_bytes_and_headers`, `test_lost_put_response_reconciles_before_retry`, `test_403_is_not_absence_and_private_object_is_not_repaired`, `test_crash_after_put_before_receipt_recovers`, `test_partial_release_and_concurrent_publishers_never_overwrite`. Use a stateful fake AWS executable/adapter; simulate two publisher schedules, not two real remote processes.

```python
receipt = scenario.run(lost_response_after_write=True)
self.assertEqual(scenario.put_count, 1)
self.assertEqual(receipt.put_outcome, "unknown_but_verified")
self.assertEqual(scenario.last_put["if_none_match"], "*")
self.assertEqual(scenario.child_env["AWS_MAX_ATTEMPTS"], "1")
self.assertEqual(scenario.forbidden_calls, [])
```

- [ ] **Run RED:** `python3 -m unittest discover -s scripts -p 'test_installer_publication_upload.py' -v`. Confirm intended missing upload/recovery behavior failures.
- [ ] **Implement minimal AWS subprocess adapter.** Validate the offline CLI version/service model before mutation. Build argv arrays for only HEAD/ACL/PUT using every fixed design argument, including literal `*`, exact Content-Length and public-read. Construct the minimal child environment with mapped installer credentials, empty isolated config files, checksum modes and no hidden retry. Narrowly classify known errors; unrecognized output never means absence/success. Apply subprocess/connect/read limits and bounded redacted output. No shell and no automatic credential loading.
- [ ] **Implement sequential lock/journal/reconciliation.** Reload/revalidate prepared custody, acquire exclusive local lock, snapshot/hash-check around attempts, HEAD/ACL then conditional PUT if absent, and reconcile timeout/409/412/5xx using exact headers/ACL plus Task2 anonymous reader. Honor three PUT attempts and 1/3-second delays; unknown probes stop with exit4. Never repair a private or mismatched object. After a crash, local journal claims cannot skip remote verification. Retain partial evidence but emit the complete upload receipt only after all three objects pass.
- [ ] **Run GREEN:** repeat focused upload tests; add targeted fake scenarios for journal fsync/serialization failure after successful PUT, missing-vs-denied HEAD, metadata conflict despite matching size/hash, unsupported offline CLI model, readback corruption and retry exhaustion. Assert no unconditional PUT/delete/copy/ACL repair or unapproved destination appears anywhere in fake call history.
- [ ] **Commit/review:** stage Task3 files and fixture changes only; commit `feat: publish installers with conditional recovery`. Preserve exact head/test evidence; resolve findings before Task4. No real Spaces canary or upload is part of this task.

### Task 4: Closed CLI, real manifest parser and source handoff

**Files:** Create `manifest.py`, `scripts/publish_installers.py`, `test_installer_publication_cli.py`, marketing validator script/test, source evidence Markdown from ownership table. Modify only `.github/workflows/ci.yml`'s existing `changes` marketing path filter (currently about line280) and marketing job (currently about line1714), as specified below. Extend fixtures only if needed. Existing production parser/manifest, website components and deployment docs remain read-only.

**Interfaces:** `emit_manifest(release_dir: Path, verification_path: Path, out_path: Path) -> Path` reloads all accepted snapshots/receipts, checks the exact plan hash and projects four rows from three observed objects. `main(argv: Sequence[str] | None = None) -> int` routes only the five accepted command forms. TypeScript validator takes exactly one path argument, reads at most 64 KiB and invokes imported `parseReleaseManifest(value)`; exit0 with concise validation result, otherwise nonzero and no output manifest. The Python producer performs receipt checks/projection only; it must not duplicate the website parser's JSON rules.

- [ ] **Write RED tests** named `test_closed_cli_surface_and_exit_codes`, `test_independent_verification_is_required_and_plan_bound`, `test_universal_pair_projects_identical_metadata_to_actual_parser`, `test_parser_failure_and_partial_receipts_leave_no_output`, `test_existing_output_must_be_identical`, `test_no_production_manifest_or_remote_call_during_self_test`. TypeScript tests import the actual parser and exercise the validator on synthetic valid/unpublished/invalid files. Include a thin-Mac inspection, wrong host, duplicate target, altered shared mac metadata, unexpected fields and stale verification digest.
- [ ] **Write CI routing RED tests** in `test_installer_publication_cli.py`: `test_publisher_only_paths_select_existing_marketing_checks` and `test_marketing_runs_offline_publisher_after_runtime_setup`. Inspect only the owning workflow blocks using stdlib text/indentation extraction, not a new YAML/parser dependency. Assert each representative package module, entry point, fixture helper and test file matches a listed marketing glob; assert the existing `changes.outputs.marketing` → `needs.changes.outputs.marketing` job guard remains connected. Check the self-test step has repository-root working directory, exact command, follows Node/Python setup and Install, and has no publication env/secrets or conditional skip. In-memory negative controls remove each added route or the step and must fail. These are narrow source-routing checks, not an emulator or claim that GitHub Actions ran.

```python
candidate = emit_manifest(fixture.release_dir, fixture.independent_verification, fixture.output)
rows = json.loads(candidate.read_bytes())["artifacts"]
self.assertEqual(len(rows), 4)
self.assertEqual(rows[1]["url"], rows[2]["url"])
self.assertEqual(rows[1]["architectures"], ["arm64", "x64"])
self.assertEqual(fixture.production_manifest.read_bytes(), fixture.original_manifest_bytes)
```

- [ ] **Run RED:** `python3 -m unittest discover -s scripts -p 'test_installer_publication_cli.py' -v` and `node --test implementation/marketing/tests/installerPublicationManifest.test.ts`. Use the landed real parser; if it is absent, report the integration dependency rather than copying or mocking it as final authority.
- [ ] **Implement manifest projection and Node validator.** Require complete matching acceptance, prepare/upload and independent verification receipts; rehash all retained evidence and ensure both Mac rows share actual verified metadata. Invoke the fixed Node script via argv, then atomically create candidate output. Existing differing output refuses; identical bytes are idempotent. Validation failure writes no success artifact. Do not edit production `current.json`.
- [ ] **Implement thin CLI and self-test routing.** Reject extra commands/arguments, map typed failures to exact exit codes and bounded safe diagnostics, and invoke only the module named by the command. `--self-test` runs the four isolated Python suites with fake/local adapters; no network preflight, AWS credentials or genuine evidence are needed. Its unit test patches suite dispatch rather than recursively launching the full self-test from inside itself; the outer GREEN command runs the genuine suite. `verify-public` checks its own credential-free environment; keep its independent receipt separate from upload reconciliation. No command emits qualification or deployment success.
- [ ] **Wire the existing marketing CI filter and step.** Add exactly `scripts/installer_publication/**`, `scripts/publish_installers.py`, `scripts/_installer_publication_fixtures.py`, and `scripts/test_installer_publication_*.py` to the existing marketing filter. Keep its existing paths and the existing marketing output/job guard. The inspected workflow already has Node22, Python3.14, `npm ci`, and `make marketing-check`; add the following step immediately after `Install` and before `Reject high and critical npm advisories`, with no extra environment or setup. Existing top-level push/PR patterns include these Python paths; do not change them, desktop routing or minute tiers. `make marketing-check` already invokes normal `npm test`, which discovers `tests/*.test.ts`, so no duplicate TypeScript CI step is needed.

```yaml
      - name: Installer publication offline self-test
        working-directory: .
        run: python3 scripts/publish_installers.py --self-test
```

- [ ] **Run GREEN:** `python3 scripts/publish_installers.py --self-test`; `node --test implementation/marketing/tests/installerPublicationManifest.test.ts implementation/marketing/tests/publicDownloads.test.ts`; `npm --prefix implementation/marketing run type-check`; `npm --prefix implementation/marketing run lint`. Use repository runtime/dependency setup already available; do not install a new dependency to satisfy this plan. If unavailable, retain the explicit unexecuted check as a handoff gap. Review test call history to prove the source suite never touched real AWS/Spaces or wrote production metadata.
- [ ] **Validate workflow amendment:** run existing pinned actionlint1.7.12 as `actionlint -color .github/workflows/ci.yml` using the available matching binary, plus `python3 .github/scripts/check_workflows.py --self-test`, `python3 .github/scripts/check_workflows.py`, `python3 .github/scripts/check_ci_minutes.py --self-test`, and `python3 .github/scripts/check_ci_minutes.py`. The existing workflow-lint job already pins actionlint and PyYAML6.0.3; do not add an install or dependency to the marketing job. If local tooling is unavailable, record that limit and require the existing hosted lint job's actual result during the later authorized delivery. Record the two named routing-test results and a table of publisher-only sample paths → marketing selection → exact offline step, plus normal TS-test discovery. Keep this static evidence separate from hosted results; when later CI runs on the source commit, retain the actual marketing self-test log and workflow-lint result, never relabel skipped/unexecuted CI as passing.
- [ ] **Write the source evidence/handoff document.** Record actual base/head and commands/results, tool versions, isolated failure controls and known source-only limits. Describe the existing later sequence: final accepted CI/local packages and evidence → prepare → authorized conditional upload → independent credential-free full-byte verification → candidate parser validation → reviewed website update → owner manual Coolify deployment → live browser/manifest/download and final native checks. Do not populate genuine release values, fabricate acceptance or execute those later operations. Link the accepted design and plan after root integrates them.
- [ ] **Commit/review:** stage only Task4-owned files and fixture edits; commit `feat: connect installer publisher to release manifest`. Root's final review reconciles all four slices and current integration head. Source completion does not certify real acceptance/publication/deployment.

## Self-review disposition

Completed against the accepted design; no consequential unanswered implementation question remains. The four slices cover every design section: Task1 source/CI-local contracts and snapshot custody, Task2 bounded anonymous reads/process boundary, Task3 exact remote operations/restart state, Task4 closed CLI/consumer projection/manual handoff and narrow existing-CI wiring. Shared names/types match downstream consumption; production JSON validation is owned once in contracts, while public manifest authority stays in the actual website parser. Each Review Focus item has named negative/regression tests in its owning task. The CI amendment's filter/step ownership, repository-root working directory, existing Node/Python availability and normal TypeScript test discovery were checked against the actual workflow; negative routing controls and existing lint/minute checks are explicitly planned.

Resolved organization detail: a cohesive package plus thin CLI replaces the proposed monolithic publisher file; behavior, command surface, settings, limits and release gates are unchanged. No dependencies or generic infrastructure were added. Fixture and type changes are explicitly sequential. The plan preserves the root's same-host verifier and CI/local provenance corrections, and distinguishes missing real acceptance from source implementation readiness.

Execution dependencies remain concrete: root supplies the actual isolated integration base; the existing strict website parser must be present for Task4; genuine safe cloud-profile/build/native/provider evidence is required only for later real preparation/publication. Nothing in this documentation-only planning pass executes tests, installs packages, creates a worktree, builds an installer, accesses Spaces or changes the accepted design.
