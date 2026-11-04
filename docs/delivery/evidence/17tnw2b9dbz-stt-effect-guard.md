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

Pending actual final normal/unsafe builds. Both will include reviewed hygiene1488 and latest main2f4dcc25, real shipped `stt` plus default/read-encrypted-transcripts features, opt3/debuginfo0, locked/offline exact1.98.0. Exclusive task-owned target; complete desktop/toolchain/staged-resource input hashes are compared before/after compilation. Existing empty compile-check sidecars are used only to link the operator. No GUI executable is run.

## Scope and remaining gates

Native aarch64 macOS Mach-O compilation/linking only. No Windows/MSVC/NSIS/full-installer, model/microphone, provider, signing, deployment or dispatch evidence is claimed. Root owns actual hosted CI, all four independent reviews, merge/QA, and the pending authenticated ClickUp start/status write (implementation exception expressly authorized; no saved status claimed). Iteration3 of max4 performs final artifact proof; iteration4 remains reserved for review remediation.
