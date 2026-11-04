# STT override artifact guard — 17tnw2b9dbz

Task: https://app.clickup.com/t/17tnw2b9dbz

The actual DeveloperOverride branch now emits a fixed debug-only, once-only notice containing `SELAHCUE_UNSAFE_STT_DEVELOPER_OVERRIDE_V1`. Its observable Write consumes the marker; it is neither an unused static nor an injected fixture. It contains no caller path/hash. Release resolution remains pinned. The scanner permanently checks this ninth signature in UTF-8 and UTF-16LE while retaining all existing guards, targets and the 1 MB operator floor.

## Completed local checks

- Scanner self-tests: 47 PASS under normal and optimized Python (previous baseline45).
- Complete owning module:25 debug/24 release tests PASS, including once-only/no-input-echo test observed RED before implementation.
- Source-exact supplemental native probes: eight PASS (normal, profile assertions, inline profile, profile environment, valueless RUSTFLAGS, encoded flags, legacy config, thin LTO). Optimized fat/thin LTO and stripped matchers follow actual runtime pinned/override selection. These small probes are explicitly supplemental; they do not satisfy the full operator scan floor.
- Import guards PASS. Toolchain pinned Rust/Cargo1.98.0.

## Historical RED evidence

On unmodified main013a84bc module988c62b5723ae86180485f58b3c5b90fde2f9338a4aae1374090398e699fe4d3, actual native normal operator38375504bytes scanned GREEN (sha2564c890031804842ae83172d4e90b35b2cf092e9e4fb7009a17ddcac3c519803cb). Assertions-on operator35545088bytes already scanned RED for existing DEEPGRAM_API_KEY (sha256d8fc56e8d32620b863dfad3e66b4679b52fb1ac9304154ba56636ca9477d26c5), but had no STT marker. Therefore the specific STT-effect assertion failed; this is an additive missing STT guard, not a claim that the whole old scanner passed unsafe global assertions.

Raw historical builds: `/private/tmp/17tnw2b9dbz-operator-baseline` and `/private/tmp/17tnw2b9dbz-operator-unsafe-baseline`. Specific full-effect RED: `/private/tmp/17tnw2b9dbz-full-effect-red`; new notice test RED: `/private/tmp/17tnw2b9dbz-new-notice-red.log`.

## Final full-artifact proof

Both final native builds exited 0 from source commit `fd57dd2e3b760ec75e2a0c118a267f599e6d1927` and module SHA-256 `8bc6b286a98faa05d8238cc6eadf0f5c8e6c2bff4494eb949ecb21c65a0edcc0`. Both included reviewed hygiene1488 and main2f4dcc25. All455 desktop/toolchain/staged-resource input hashes matched before/after each build and between builds. The source manifest still matches the final tree; subsequent evidence-only changes do not alter compiled inputs.

| Actual operator | Debug assertions | Bytes | Full scanner | SHA-256 |
|---|---|---|---|---|
| Normal release | false | 38,379,104 | GREEN, no hits | `ee12eb2f57cbe28b7391df006ac44060ddd48d65b8782af206446dfa05da4c88` |
| Unsafe release | true | 35,546,096 | RED, explicit STT marker and retained Deepgram hit | `163b2145c03a213fecac88f054327e39d6df48402a1e0079b2b1af41da0b7dbf` |

STT marker: UTF-8 offset15864354; existing Deepgram: UTF-8 offset17313760. Scanner SHA-256 `377204530b549809cf403a2c7abe9e36d4c0f82870c1e1acc94b00ce730a2662`. Both actual Cargo receipts report opt-level3/debuginfo0, `default`, `read-encrypted-transcripts`, `stt`, no development key/cloud/pilot features. Locked/offline pinned Rust/Cargo1.98.0, exclusive task-owned target. The normal and unsafe full binaries were not executed; actual override/pinned runtime behavior is independently demonstrated by the source-exact eight compiled probes. No GUI/model operation was performed.

Raw final command/compiler/stdout/stderr/exit/scan/artifact receipts and455-file input manifests: `/private/tmp/17tnw2b9dbz-operator-normal-final/` and `/private/tmp/17tnw2b9dbz-operator-unsafe-final/`. Build driver: `/private/tmp/17tnw2b9dbz-build-operator.py`. Existing empty compile-check sidecars were used only to link the operator; no installer acceptance is inferred. All build processes finished and were reaped.

Supplemental final proof and module logs: `/private/tmp/17tnw2b9dbz-supplement-final/` and `/private/tmp/17tnw2b9dbz-supplement-final.log`. Scanner47 logs: `/private/tmp/17tnw2b9dbz-scanner47.log` and `/private/tmp/17tnw2b9dbz-scanner47-optimized.log`. Import guards: `/private/tmp/17tnw2b9dbz-import-guards.log`. Rustfmt and diff whitespace checks PASS.

## Scope and remaining gates

Native aarch64 macOS Mach-O compilation/linking only. No Windows/MSVC/NSIS/full-installer, model/microphone, provider, signing, deployment or dispatch evidence is claimed. Root owns actual hosted CI, all four independent reviews, merge/QA, and the pending authenticated ClickUp start/status write (implementation exception expressly authorized; no saved status claimed). Iteration3 of max4 performs final artifact proof; iteration4 remains reserved for review remediation.
