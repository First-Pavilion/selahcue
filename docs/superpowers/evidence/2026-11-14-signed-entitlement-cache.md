# Signed entitlement verification and cache evidence

Task [86ak5mn1d](https://app.clickup.com/t/86ak5mn1d) implements FR-518 for desktop licensing. Source baseline is `40661b4fde38f1e670bc8fde522c17b30bdb93a7`.

## Consumer contract

`verify_entitlement(&[u8], &TrustedKeys, device_public_id, device_fingerprint)` returns an opaque `VerifiedEntitlement` after admitting at most 64 KiB, validating the v1 envelope and exact Ed25519 algorithm, selecting the named key and verifying the transmitted base64url string. After verification it decodes the v1 payload and checks both signed identity fields. It exposes grants, signed timing facts and the signed lower bound. Older v1 payloads without grants remain valid and have an empty grant map. The caller supplies the activated public ID and the normalized install fingerprint it used for activation. The verifier does no wall-clock checks; interpreting signed times and authorizing features belong to later consumers.

`EntitlementCache::new(app_data_dir)` takes an existing app-owned directory. `load` re-verifies the current trust set and both identity fields against the stored envelope. `replace` accepts the same raw envelope input as the verifier, runs the existing replay/expiry/grant replacement rules and keeps fractional timestamp precision so same-second issuances order correctly. Its fixed cache, lock and staging filenames never use device or response data. Writes serialize under an OS file lock, sync bounded staging bytes, then rename over the destination. A restart can still read the previous cache after an interrupted pre-rename write. The next admitted replacement reclaims its single staging file. The cache only persists the five envelope fields. Unsigned HTTP fields are discarded. Credential types and the secret store have no cache dependency.

The app-owned directory is a trusted caller input. The cache refuses observed links, reparse points and non-regular paths and uses non-following file opens on Unix and Windows. Namespace replacement by the same OS user, arbitrary filesystem behavior, and power-loss durability are outside the tested guarantee. Future integration must keep cache calls off live-control and render paths.

## Interoperability and tests

The fixture under the licensing crate's `tests/fixtures` was minted by the repository's Python `apps/entitlements/signing.py::sign_envelope`, loaded directly with `importlib` and `cryptography` 50.0.2, using the synthetic 32-byte seed `[41; 32]`. The reference `verify_envelope` recovered the fixture payload. It contains Python-escaped non-ASCII display text and a fractional `+00:00` issue timestamp. Fixture bytes and test public key are scoped to integration tests. Independent Rust-signed cases cover both original keys, a third key added to the existing set, and rejection when another trusted key is named. Temporarily changing verification to look up only the first key made the rotation test fail. Restoring lookup by envelope ID made the same test pass.

The integration suite initially failed to compile on the absent public verifier/cache API. The same-second replay and interrupted staging tests then each reproduced behavioral failures against the first implementation before both passed with the corresponding fixes. The final owning crate suite passed 174 tests on macOS arm64, including 11 credential custody, 7 never-blank, 72 licensing client cases and 15 verifier/cache tests. That includes a real rename failure with staging cleanup, an interrupted staging file, a corrupt/truncated or oversize cached envelope, reopen under changed trust/device, safe refusal of a symlink or directory, replay and degradation refusal, and prior-envelope retention on a failed write.

Commands used from the desktop workspace with Rust 1.98.0, `CARGO_BUILD_JOBS=1` and a dedicated temporary target directory:

- `cargo test --offline --locked -p selahcue-licensing --no-fail-fast`
- `cargo clippy --offline --locked -p selahcue-licensing --all-targets -- -D warnings`
- `cargo fmt -p selahcue-licensing -- --check`
- `cargo-deny --locked check licenses bans sources` passed with existing duplicate and wildcard warnings.
- `cargo-audit audit --no-fetch` passed against advisory snapshot `af7b3ec3` (2026-11-12). Both the base and updated lockfiles report the same allowed warnings for `ttf-parser` 0.25.1 (RUSTSEC-2026-0192) and `rustix` 1.1.4 (RUSTSEC-2026-0486).
- Repository-root `sh scripts/dev_key_not_in_release.sh` confirmed the development key was present in the debug rlib and absent from the release rlib.
- Repository-root `python3 scripts/check_dependency_audit_coverage.py` confirmed all Cargo lock roots have matching audit jobs.

Cargo resolved the primary `ed25519-dalek` 3.0.0 from crates.io (BSD-3-Clause, Rust 1.85 minimum) with default features disabled. No new license exceptions were required. [Published crate metadata](https://docs.rs/crate/ed25519-dalek/3.0.0)

Scope is the licensing workspace crate. Linux and Windows cache runtime, native UI, deployed issuance, production public-key provisioning, manifest fetching and entitlement enforcement were outside this local evidence.
