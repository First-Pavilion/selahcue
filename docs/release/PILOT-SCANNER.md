# Pilot scanner — Python phase, not installer acceptance

Ticket: https://app.clickup.com/t/17tnw2bbhwz . Root-accepted Aria contract defines this source unit. P04 remains In Progress; no CLI/workflow is enabled and no pilot package has been accepted. This phase adds only a Python policy core and offline controls. Existing installer_secret_scan.py remains unchanged.

## Frozen frame contract for the later native integration

The byte sequence is `MAGIC || little-endian-u32 JSON_length || JSON || TRAILER`.

- MAGIC: ASCII `SCUE-PILOT-PAYLOAD-V1` with one NUL before and after.
- TRAILER: ASCII `SCUE-PILOT-END-V1` with one NUL before and after.
- JSON length1–16384 bytes; canonical ASCII JSON uses sorted keys, compact comma/colon separators and no whitespace.
- Exact top-level fields: schema1, cohort, cutoff1809129599, openai, deepgram. Each provider has exactly key/expires_at/model. Deepgram model is nova-3; OpenAI model and cohort come from the reviewed admission input. Every provider expiry must be after the supplied current time and at/before the fixed cutoff2027-04-30T23:59:59Z.
- Credential admission is deliberately narrower than P02 runtime:16–4096 ASCII characters drawn from letters/digits/underscore/dot/hyphen. No JSON escaping. The two values must differ, cannot contain each other or collide with the declared forbidden markers, and each quoted value must be unique within the canonical JSON.

The eventual native accessor must consume this exact frame, pass its JSON slice to P02's parser and retain exactly one complete frame per expected architecture image. It must remove the earlier raw include_str payload copy. Native integration files are reserved until P03 freezes/merges and root coordinates the exact base. No Rust files were edited in this phase.

## Core interfaces and bounds

`scripts/pilot_installer_scan.py` provides:

- `admit_payload`: explicit build-owned input only, fixed error codes; no file discovery/environment reads or secret formatting.
- `scan_component`: original1MB real-artifact floor. Pilot operator exceptions require exact main/manual-dispatch/source/hash/architecture evidence and exactly one bound complete frame per slice. Only the two raw credential value spans pass. All-occurrence matching detects overlapping and8MiB-boundary copies, UTF16LE/base64/hex copies and duplicate payloads; those representations never gain an exception.
- `scan_resource`: deny-only resource scan, including small/empty files, with no native exception. It cannot stand in for required operator/sidecar/installer scans.
- `native_images`: bounded executable ELF64/x86_64, PE32+/x86_64 and Mach-O64 thin/Universal arm64+x86_64 header/loader-range validation. Universal slices cannot overlap; keys in fat headers/padding/outside their exact field spans fail. Synthetic format fixtures are not actual platform installer proof.
- `verify_inventory`: closed uncompressed file inventory/hash verification; rejects escaping/ambiguous names, symlinks/special/hardlinked members, missing/extra/mismatched files. Limits:1024files,16path components,2GiB total,30seconds with checks during reads. This does **not** perform extraction or establish that a caller-supplied directory is fresh.

Each scanned file gets a private positive-control copy seeded from its leading bytes. The control must rediscover every applicable marker/credential encoding and explicit known-secret needle. The shipped file is never modified, and whole-file hashes before/after must agree. Matcher hit count and longest-needle memory are bounded. No raw key, key fragment, payload fingerprint, parser input or surrounding bytes is diagnostic content.

All six developer loader/environment markers remain forbidden everywhere. The two public endpoint markers are allowed only in the exact provenance-verified pilot operator; ordinary and every other component deny all eight original markers. This finite capability allowance grants no credential exception and is not a package hostname allowlist. Aria explicitly ruled native endpoint call-site/symbol attribution unnecessary; reviewed fixed constructors and build/package provenance remain the source contract.

The known development inventory reads only the two exact committed, explicitly public licensing fixture files: dev-signing-key.NOT-A-SECRET and src/trust.rs. It checks seed/public-key consistency and fails if parsing changes. It never reads a production signing key, .env, keychain or arbitrary process environment. Additional known CI/test secrets must be explicitly supplied by the authorized build driver. This byte scanner does not promise detection of every arbitrary unknown/transformed secret.

## Verification observed in this phase

Python3.9.6 on this Mac: `python3 scripts/test_pilot_installer_scan.py` —28tests pass; `python3 scripts/installer_secret_scan.py --self-test` —45original controls pass. Tests were observed red before missing matcher/inventory/resource/positive-control behavior was implemented. A truncated-trailer fixture initially had zero padding accidentally restore its last NUL; the fixture was corrected to truncate a nonzero trailer byte before passing.

Coverage includes canonical schema/model/expiry/duplicate-field failures; ordinary marker denials in both encodings; valid two-span pilot; allowed-first/forbidden-later copies at an actual8MiB boundary; UTF16/base64/hex copies; known unrelated/development fixtures; malformed frames/provenance; ELF/PE/Mach-O/Universal bounds and slices; inventory hash/extra/symlink/limits; disabled-matcher positive control failure; and secret-fragment checks on output/error/repr paths. Two tiny native fixtures were actually compiled with local cc, never executed: real native-header parsing and one consumed synthetic frame retained once. That proves this local compiler fixture only, not the Rust operator or another architecture.

A separate py_compile attempt hit sandbox denial writing its default cache outside this worktree. It is not reported passing. Both Python modules were imported/executed successfully by the focused suite; subsequent explicit test invocation used a task-owned temporary cache prefix.

## Required remaining work

1. Fetch/audit/integrate current main after P03 freeze; add only root-authorized build.rs/provider_source/native accessor/module/test hooks, preserving P02/P03 parsing, expiry, transport and consent behavior. No late edits in another agent's worktree.
2. Implement authoritative **actual produced installer** extraction adapters and a driver that performs fresh bounded extraction itself, binds exact source/build/component hashes and scans every closed-inventory member plus the installer. The core's BuildEvidence object and inventory helper are trusted inputs, not authenticated CI receipts or extraction evidence. No platform acceptance passes from handcrafted objects/directories.
3. Bind platform formats/expected architectures and required primary targets to actual build metadata; prove retention/no raw JSON copy with the real Rust operator per supported architecture, and preserve ordinary-build absence.
4. Complete P01 real provider restriction/model/expiry proof before any real credential injection. No account/key access or provider call occurred here.
5. Four independent integrated source reviews, remediation/re-review, current CI and root merge remain mandatory. Actual P05/P07/P09 installer proof and P17/P18/P19 clean-location QA remain separate. Do not enable a workflow, publish a bucket artifact or call full P04 complete from these fixtures.
