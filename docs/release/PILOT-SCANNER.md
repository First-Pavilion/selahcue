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

## Architecture-audit correction

At checkpoint609855cc, Aria independently reproduced a complete second frame with body `[]` being ignored because the matcher classified candidates only by an opening object brace. Owner reproduced RED with complete `[]`, non-JSON, empty and overlength framed bodies (four failures). The correction first recognizes bounded complete framing independently of body syntax, then applies existing length and exact authorized-input binding. Standalone public MAGIC constants adjacent to the real frame remain tolerated; object-started truncated/bad-trailer candidates still fail.

After correction:31focused tests pass (3.269s), including all previous28, plus45unchanged selftests. No native code, original scanner or admission/platform gates changed. This is owner remediation evidence; Aria's recheck and the integrated four-reviewer round are still required.

## Final bounded Python asset phase (Iteration3)

`pilot_asset_provenance.py` separates known-actual-secret/devseed checks from public frontend labels: reviewed `OPENAI_API_KEY` help passes this asset-input policy, while the original raw8marker gate is unchanged. No outer executable scan is described as decoding Brotli. Closed frontend inventory is verified/scanned and rechecked; stale/extra/changed/symlink files fail. An empty task-owned output directory is observed before synthetic codegen; generated outputs have a separate exact inventory. Explicit reviewed config/toolchain/Cargo lock/codegen transform/runtime source hashes and compression feature are helper inputs; frontendDist is checked against parsed config. Cargo executable selection/debug status/hash and emitted-versus-packaged hashes have separate bindings.

These are helpers, not a production admission driver. Their manifests and Cargo messages are supplied trusted data, not authenticated build receipts. A real driver still must select exact locked Tauri/codegen versions/features/config, verify the complete transform/build-hook input set, own the fresh actual OUT_DIR/build invocation, bind generated output selection and Cargo output to that invocation, freshly extract the produced installer and verify the package chain. No native build or extraction happened here. `AssetChain` explicitly reports synthetic-helper-chain-only with actual_build_verified=false and actual_extraction_verified=false. No workflow/CLI was enabled.

Observed RED5missing-module tests before implementation; final9focused synthetic asset controls pass, alongside31existing policy controls and45unchanged scanner selftests. A synthetic fixture initially placed generated files inside its closed frontend tree; the helper correctly rejected the extra members. The fixture now separates frontend and generated output, matching the intended build boundary. Error/repr/output controls use synthetic actual-key canaries; no production secrets or source environments were read. Public committed development seed/public-key inventory remains the only automatically read known-key source.

Iteration3 consumes the existing max3budget. Native P03 ownership/retention, real extraction/package, P01 provider proof and four integrated reviews/currentCI remain open. No Iteration4 or native continuation is authorized by this phase; root must explicitly disposition the contract budget after the dependency is satisfied.

## Bounded phase-review remediation (Iteration4)

Root explicitly amended maximum3to5 before work via p04-review-remediation-disposition.md, preserving original criteria and iterations1–3. Iteration4 addresses P04-SHADOW-01 (Medium) and V-P04-1 (Low); iteration5 is reserved only for verified re-review corrections. No iteration6/native work or whole-ticket completion follows.

The diagnostic regression first failed: full traceback and standard logger.exception rendered an underlying PermissionError containing a synthetic private pathname, despite a fixed str(error). Central core errors and asset-helper policy raises now suppress implicit context (`from None`). A regular1MB synthetic selected artifact with injected filesystem refusal exercises both the actual core entry and asset helper; full traceback/logger output preserves the public refusal and excludes every8byte private canary fragment. This is stronger than testing str(error) alone.

The read-count regression first failed: increasing explicit known-secret inventory0to16 raised target opens7to23. Both helpers now validate/cap and deduplicate all deny-only raw/base64/hex/ASCII-UTF16 probes and match them in one pass. The regression checks equal target-open counts for0and16 values in both core and asset paths, independent of elapsed time. The two intended credential span/owner loops, supported representations, private positive controls, before/after hashes, eight-marker ordinary policy, size floors and45legacy controls are unchanged. No large-file latency/capacity claim is made.

Observed GREEN:11asset/helper tests,31core tests,45unchanged legacy controls; structural goal and diff checks pass. All four reviewers must re-review this corrected phase. Native retention/actual extraction/provider/current-integrated-CI gates remain blocked/pending.

## Final reserved correction (Iteration5)

P04-QUINN-02 identified uncaught metadata/source-root failures before the existing sanitized handlers. Owner observed RED6failures, including real own mode000 parent-directory refusal (restored0700 in finally). The correction applies a shared/public filesystem boundary catching only OSError, including iteration-time failures of generator helpers. Native source-root resolution uses a separate operation-local OSError/RuntimeError handler for Path.resolve's documented symlink-loop failure. All converted errors have fixed public codes and suppressed context. Unrelated RuntimeError remains visible, demonstrated by a control outside resolve; no catch-all Exception production handler was added.

Full traceback and standard logger controls cover component metadata, inventory-root metadata/inherited assets, source resolution in core/assets, and real filesystem permission/symlink-loop cases. GREEN15asset/helper tests with no skips on this host,31core tests and45legacy selftests. The0vs16 inventory read-count test remains green, with match/span/encoding/positive-control/ordinary policy unchanged. Structural goal/diff checks pass. This exhausts the explicitly authorized max5; no6 or native continuation is authorized. Root owns the second/final four-review snapshot refresh. Whole native/driver/extraction/package/P01/current-integrated-CI gates remain blocked/pending.
