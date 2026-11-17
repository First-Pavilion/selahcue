# Installer publication evidence linkage ruling

Root execution ruling, 2026-11-15. Supplements the accepted design SHA-256 `686498a1ed1881ad5f11266341190a14ad30810f51d46aa6cfd1958daf661ea1` without changing its bytes or its trusted-operator boundary. Task1 identified that source/version/public-key evidence needed an explicit machine-readable format to implement the already required identity checks. This note fixes that format; it does not create acceptance evidence or certify its truth.

## Closed structured leaf records

`ProfileV1.source_evidence` resolves to exactly:

```text
SourceEvidenceV1 = {
  schema_version: 1,
  version_config: SourceFile,
  public_key_config: SourceFile,
  public_key_symbol: "PILOT_PUBLIC_KEY",
  public_key: Ref,
  build_inputs: [SourceFile, ...]
}
SourceFile = {source_path: string, evidence: Ref}
```

`Ref` retains the design's meaning: a regular contained evidence file relative to the original input directory, with its exact SHA-256. It never changes into a repository path. `source_path` is separately a normalized repository-relative regular tracked path without traversal, symlinks, absolute paths, control characters or Git revision syntax; source bytes must agree with both the exact committed blob and clean checkout bytes. The publisher does not execute source or receipt command arrays.

The finite first-release source roles are `implementation/desktop/crates/selahcue-operator/tauri.conf.json` for `version_config` and `implementation/desktop/crates/selahcue-licensing/src/trust.rs` for `public_key_config`. Parse the former as bounded duplicate-free JSON and compare its exact SemVer `version` with all release/profile/build/inspection versions. For the latter, require the exact named `PILOT_PUBLIC_KEY` constant's `[u8; 32]` literal to contain exactly 32 hexadecimal byte literals (whitespace and the current trailing comma permitted), with no executable expression or fallback interpretation. Compare those bytes with the `public_key` evidence file, which must contain exactly the raw 32 bytes. Its SHA-256 equals `entitlement_public_key_sha256`, and the first eight lowercase hex characters equal `entitlement_key_id`, matching the current client/server signer algorithm. A future source shape/key-injection change requires an explicit reviewed adjustment; do not silently guess or evaluate Rust.

`build_inputs` contains 1–4096 unique source paths and their exact retained evidence. It must include the two fixed configuration paths above and every referenced CI workflow, with consistent evidence/digests. These are reviewed build inputs, not credential sources; do not accept `.env` or private-key/config paths as source evidence. The complete source checkout must still be clean at the exact `source_commit`; a partial list cannot authorize uncommitted inputs. Missing an actual build input or falsifying the reviewed list remains within the design's explicit operator-review trust boundary.

Each `InspectionV1.version_evidence` resolves to exactly:

```text
InspectionVersionEvidenceV1 = {
  schema_version: 1,
  artifact_id: "windows" | "universalMac" | "ubuntu",
  package_sha256: lowercase-SHA256,
  version: SemVer,
  entitlement_key_id: string,
  entitlement_public_key_sha256: lowercase-SHA256,
  evidence: Ref
}
```

These identity fields must equal the owning inspection/artifact and accepted profile. `evidence` retains concrete package-inspection output as an opaque, hash-bound leaf. The publisher checks identity and custody; reviewers still determine that the output actually demonstrates packaged version/key enforcement. No per-gate acceptance wrapper is added. Existing `AcceptanceV1` and its exact twelve gates remain unchanged.

Known structured records and these two leaf schemas are traversed recursively through their declared references. Opaque logs, tool output, scenario evidence and source blobs are retained unchanged as leaves; arbitrary JSON-shaped log content is not treated as another schema or executed. Every declared reference needs a complete prepare mapping, so reload never depends on the original paths.

## Repository, command and workflow linkage

The only source repository for this finite publisher is `First-Pavilion/selahcue` on `github.com`. `BuildReceiptV1.repository` uses canonical `First-Pavilion/selahcue`. The clean source checkout's `origin` may use the ordinary HTTPS or SSH GitHub spelling (optional `.git` suffix) but must normalize to that same owner/repository; reject credential-bearing URLs, other hosts and other repositories. Temporary tests set a synthetic repository's origin to this URL without making any network request.

The artifact profile's exact `command_argv` must appear in that artifact's ordered `build_commands`; no substitution or shell evaluation is allowed. A CI workflow is a committed regular `.github/workflows/*.yml` or `*.yaml` file. Its supplied digest must match the exact source bytes and the corresponding retained `SourceFile` in `build_inputs`. CI identity truth remains reviewed against the trusted original run; a local receipt must never invent CI identity.

Ruling: implement these explicit formats as part of Task1's sole contracts/preparation ownership — they make already mandated identity validation executable while preserving the meaning of Ref and the boundary between custody and qualification — if final producers change the source shape, a small reviewed producer/contract amendment will be required before real preparation. Cover mismatch, missing linkage and unchanged opaque leaf behavior with meaningful synthetic tests. The independent Task1 reviewer must assess this ruling together with the original design.

## Opaque evidence bounds

The design's 1 MiB document limit applies to the input and recognized structured JSON evidence schemas, regardless of filename extension. Complete opaque build logs, inspection outputs and raw source blobs are separate hash-bound leaves: at most 64 MiB each and at most 512 MiB in aggregate across unique retained evidence files (a shared reference counts once). A raw Git source blob that happens to contain JSON remains opaque source evidence; it is not thereby another structured receipt. Retain complete bytes or refuse, never truncate evidence. Package limits remain unchanged.

Copy and hash opaque leaves in at most 1 MiB chunks with the same descriptor, no-follow, before/after change and snapshot readback checks used for package custody. Check aggregate size before writing complete prepare receipts and enforce the bound during traversal/copy. No production CLI setting can raise these limits. Tests may inject smaller internal limits to exercise rejection without allocating large files.

Ruling: reject the worker's provisional 1 MiB opaque-log limit — the design requires complete logs and names 1 MiB for JSON documents — use the finite streaming limits above. If a final producer exceeds them, preparation refuses and needs explicit review; it never silently truncates or accepts a partial build log.
