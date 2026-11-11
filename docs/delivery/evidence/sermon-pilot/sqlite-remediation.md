# SQLite and SQLCipher release prerequisite evidence

Checked 2026-11-11 for [17tnw2bey9x](https://app.clickup.com/t/17tnw2bey9x),
from base `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0` on
`codex/pilot-sqlite-remediation-20261111`. This is local macOS arm64 verification;
independent review, exact-head hosted CI and release acceptance are separate gates.
No provider was called and no church data was opened.

## Change and prior work

The data manifest now requires rusqlite `0.42.0`, retaining `bundled`, `backup`
and `bundled-sqlcipher-vendored-openssl`. Both affected locks resolve
`libsqlite3-sys 0.40.0` and `sqlcipher-src 420.0.0+sqlcipher-4.20.0-sqlite-3.54.1-libtomcrypt-1.18.2`.
The STT lock is unchanged. No toolchain, migration, encryption key, store API,
wire format or advisory policy changed.

Read-only inspection of [PR #333](https://github.com/First-Pavilion/selahcue/pull/333)
confirmed its older remedy ends at rusqlite 0.41.1 / sys 0.39.1 /
sqlcipher-src 419.0.6. It supplies no application adaptation to reuse and does
not fix the encrypted source. Its remote branch was not modified.

Only targeted `cargo update -p rusqlite --precise 0.42.0` was applied to each
root. Its required WebAssembly dependency graph moves sqlite-wasm-rs
0.5.5 → 0.6.3 and rsqlite-vfs 0.1.1 → 0.2.0. The operator consequently moves
thiserror/thiserror-impl 2.0.19 → 2.0.21 and removes unused hashbrown 0.16.1.
A targeted attempt to retain thiserror 2.0.19 was refused because
rsqlite-vfs 0.2.0 requires `thiserror ^2.0.20`; no unrelated update was performed.

Two compiler-proved API adaptations were reported to and approved by the
controller before expanding the source scope:

- `backup(..., None)` produced E0283 after the upstream callback became generic
  (`F: Fn(Progress)`). `None::<fn(rusqlite::backup::Progress)>` preserves no callback.
- The existing checkpoint counting-handler unit test produced E0596 because
  `busy_handler` now takes `&mut self`. Its local database binding is mutable
  and uses the already accessible private connection. Production accessors and
  the same positive-control/counter assertions remain unchanged.

## Test-first linked runtime evidence

`test_sqlite_runtime.rs` was added and run before changing the manifest.
The old ordinary run failed its SQLite >=3.54.0 assertion; the old encrypted
run failed its SQLCipher 4.20.0 assertion. Both queried the running library,
not a package manifest. The encrypted compatibility check passed even on the
old runtime, establishing that its synthetic fixture was valid before upgrading.

| Configuration | Old runtime (expected RED) | New runtime (GREEN) |
| --- | --- | --- |
| Data `--no-default-features` | SQLite 3.53.2 | SQLite 3.54.1 |
| Data `--features encryption` | SQLCipher 4.14.0 community / SQLite 3.51.3 | SQLCipher 4.20.0 community / SQLite 3.54.1 |

Old ordinary `sqlite_source_id()`:
`2026-06-03 19:12:13 d6e03d8c777cfa2d35e3b60d8ec3e0187f3e9f99d8e2ee9cac695fd6fcdf1a24`.
Old encrypted source:
`2026-03-13 10:38:09 737ae4a34738ffa0c3ff7f9bb18df914dd1cad163f28fd6b6e114a344fe6alt1`.
New ordinary source:
`2026-10-16 14:45:20 555e07ef33f69a0957d24d8e555b702464a131d6f1607f4c3c1e4551e8e6ca76`.
New encrypted source:
`2026-10-16 14:45:20 555e07ef33f69a0957d24d8e555b702464a131d6f1607f4c3c1e4551e8e6alt1`.

The retained 172032-byte encrypted backup was created through the old
application's `backup_to_encrypted`, at schema 25, with only synthetic transcript
and note text and a public test key. See
[fixture provenance and generator](../../../../implementation/desktop/crates/selahcue-data/tests/fixtures/README.md).
The new library reads it through both operator-style read-only and writable
keyed paths, checks integrity, preserves the transcript/segment/saved note and
AI disclosure, rejects wrong/keyless opens, then creates/reopens an encrypted
backup and verifies its contents and lack of plaintext header/marker.

## Fetched source verification

SHA-256 of actual downloaded crate archives matched the researched index values
and both lockfiles. The selected unpacked C files were also compared byte for
byte with their corresponding archive members before inspecting the patch.

| Crate archive | Verified SHA-256 |
| --- | --- |
| rusqlite 0.42.0 | `a4edff0039f148731aee2fd80f76dbfeb12d204ab3d1c544838d34e02151049b` |
| libsqlite3-sys 0.40.0 | `b06e69070b7e12262b0cd90832f0a7396f142a2b330181255562decf9f0c6215` |
| sqlcipher-src 420.0.0 | `fd6b5280ed2593d07b2816ec531821c15c306903bcca224716f1fbcc2bbfedfe` |

- `libsqlite3-sys-0.40.0/sqlite3/sqlite3.c`: SQLite 3.54.1;
  SHA-256 `0c657666d819f261cc4007526ad57e1669de9949df7a8ea847aa284a2bf0ee52`.
  `sqlite3WalReadFrame` lines 70622–70625 contain the zero fill and length adjustment.
- `sqlcipher-src-420.0.0+sqlcipher-4.20.0-sqlite-3.54.1-libtomcrypt-1.18.2/sqlcipher/sqlcipher.c`:
  SQLite 3.54.1;
  SHA-256 `8cd2347d18886fee4651153fabeeeffb7cec008700987dab1c00261febc4220f`.
  The same function at lines 70950–70953 contains both operations.

```c
if( nOut>sz ){
  memset(pOut+sz, 0, nOut-sz);
  nOut = sz;
}
```

This matches the [upstream WAL fix](https://github.com/sqlite/sqlite/commit/e5bf119821f25be1d7f10ef0a2edbe175289166e).
The inspected sys build script selects sqlcipher-src's amalgamation when
`bundled-sqlcipher` is enabled and uses the vendored OpenSSL include/link path
when the existing vendored feature is active. Feature trees confirm both that
path and the operator default `read-encrypted-transcripts` path. Existing
openssl-sys 0.9.117 / openssl-src 300.6.1+3.6.3 versions remain unchanged.

Verbose Cargo and native build-script output records the actual crate source,
selected C file and static library paths: plain `libsqlite3-sys-1986279c9c20653c/out`
(`static=sqlite3`), encrypted `libsqlite3-sys-bd5bb52101b55cd6/out`
(`static=sqlcipher`) under the target directory below. The encrypted verbose
build explicitly names the selected `sqlcipher-src.../sqlcipher/sqlcipher.c`.
The package-version change compiled a new sys artifact; the new runtime/source
queries independently reject accidentally retained old binaries.

## Environment and commands

`sh scripts/check_toolchain.sh` passed: rustc 1.98.0 + clippy 0.1.98, matching
`rust-toolchain.toml`. Host: Darwin arm64. Every build/test below used
`CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`.

At baseline and verification, no SQLite/SQLCipher/OpenSSL/CC/CFLAGS build
override was set. Explicit checks found these unset:
`LIBSQLITE3_SYS_USE_PKG_CONFIG`, `SQLITE3_LIB_DIR`, `SQLITE3_INCLUDE_DIR`,
`SQLITE3_STATIC`, `SQLCIPHER_LIB_DIR`, `SQLCIPHER_INCLUDE_DIR`, `SQLCIPHER_STATIC`,
`OPENSSL_DIR`, `OPENSSL_NO_VENDOR`, `CC`, `CFLAGS`, `RUSTFLAGS`,
`CARGO_ENCODED_RUSTFLAGS`, `BINDGEN_EXTRA_CLANG_ARGS`.
Only presence/absence was inspected; no secret environment values were printed.

Commands below are from repository root; `WS` abbreviates
`--locked --manifest-path implementation/desktop/Cargo.toml` and `OP` abbreviates
`--locked --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml`.
The abbreviations describe literal command arguments, not executable shell variables.

| Command | Result |
| --- | --- |
| `cargo test WS -p selahcue-data --no-default-features --test test_sqlite_runtime -- --nocapture` before upgrade | Expected runtime assertion failure, SQLite 3.53.2 |
| `cargo test WS -p selahcue-data --features encryption --test test_sqlite_runtime -- --nocapture` before upgrade | Expected runtime assertion failure, SQLCipher 4.14.0; fixture compatibility passed |
| Same two commands after upgrade, with `-vv` | 1/1 plain and 2/2 encrypted pass; versions/source IDs above |
| `cargo test WS -p selahcue-data --no-default-features --no-fail-fast` | 180 passed, 0 failed |
| `cargo test WS -p selahcue-data --features encryption --no-fail-fast` | 191 passed, 0 failed |
| `cargo test WS -p selahcue-app --features server --no-fail-fast` | 368 passed, 0 failed, 1 measurement probe ignored |
| `cargo test WS -p selahcue-desktop --features encryption --no-fail-fast` | 138 passed, 0 failed, 6 child-process helpers ignored at top level |
| `cargo check OP` | Passed |
| `cargo test OP --no-fail-fast` | 460 passed, 0 failed, 1 child-process helper ignored at top level |
| `cargo test WS --workspace --no-fail-fast` | 2083 passed, 0 failed, 13 ignored; 177 top-level binaries/doc-tests, nested child summaries excluded |
| Affected data plain/encrypted, app server, desktop encryption and operator `cargo clippy ... --all-targets -- -D warnings` | All five configurations passed |
| `cargo fmt --manifest-path implementation/desktop/Cargo.toml --all -- --check`; fixture-generator `rustfmt --check`; `git diff --check` | Passed |
| `python3 scripts/check_dependency_audit_coverage.py` | Passed, all three roots covered |
| `python3 scripts/check_launch_reachability.py --self-test` and without self-test | Passed, 46 self-tests and default/release feature checks |
| `sh scripts/import_guards.sh` | Passed |
| `sh scripts/cargo_audit_all.sh` before upgrade | Expected failure: RUSTSEC-2026-0459 in workspace/operator; STT passed |
| Same unchanged audit after upgrade | All three roots passed, no vulnerability; advisory DB `901cf64f2d04dc7f9f26bbbd50a3010378de034d`, 1453 advisories |

The unchanged audit policy still prints allowed warnings for ttf-parser and
rustix, plus proc-macro-error and glib in the operator; none was hidden or
changed. Standalone STT's lockfile did not change.

The workspace ignored set comprises measurement, live TLS network and host-font
probes plus ten child-process helpers. No ignored live probe was manually run.

## Boundaries

The initial compound attempt to stage Tauri placeholders and check the operator
was rejected by automatic approval review because staging was outside its
interpreted narrow scope. Inspection showed both placeholders already existed;
the successful narrower operator check/tests performed no staging. These empty,
gitignored pre-existing files establish no shipping-artifact or packaging claim.

This verifies linked versions, selected patched source and application
compatibility, not an advisory-specific memory-initialization property under a
crafted hostile DB/WAL. No new exploit/ASan/Valgrind regression was executed.
Native Windows, Linux runtime, Windows 10/4 GB/128 GB constraints, installer,
real-provider and full exact-head hosted CI/release gates are unproven here.
The controller owns the four independent reviews, CI and any external PR action.

## Fix round 1: package-scoped license exception

The source `62c9e1ea5eefeaac46765806df20e87258d9c439` reached the hosted
supply-chain job [130481899479 in run 43008461665](https://github.com/First-Pavilion/selahcue/actions/runs/43008461665/job/130481899479).
Its cargo-deny 0.20.2 check rejected the newly declared expression
`MIT AND BSD-3-Clause AND blessing AND WTFPL` from sqlcipher-src 420.0.0.
This was a real policy failure, separate from the passing RustSec audit.
The identical desktop command locally reproduced exit 4 with
`bans ok, licenses FAILED, sources ok` before the correction.

The fetched crate retains its MIT wrapper notice (Luca Cappelletti), SQLCipher's
BSD-3-Clause ZETETIC notice and source/binary redistribution conditions, and the
LibTomCrypt dual public-domain/WTFPL notice. These upstream files and the declared
conjunctive SPDX expression were not rewritten or omitted because the runtime
selects OpenSSL. The exception changes policy matching only; all existing
copyright and redistribution notice requirements remain.

The desktop and operator `deny.toml` now each add only:

```toml
[[licenses.exceptions]]
crate = "sqlcipher-src@420.0.0"
allow = ["blessing", "WTFPL"]
```

This uses cargo-deny's documented [per-package exceptions](https://embarkstudios.github.io/cargo-deny/checks/licenses/cfg.html#exceptions)
and [exact-version package specification](https://embarkstudios.github.io/cargo-deny/checks/cfg.html#exact).
It adds these two identifiers only for the named package at SemVer `=420.0.0`;
MIT and BSD-3-Clause continue to come from the unchanged global allowlist.
The STT policy is unchanged because its graph has no SQLCipher dependency.
No global license allowance, dependency/source exclusion, build-dependency
omission, upstream metadata clarification, audit suppression or other source/bans
policy change was added. The existing all-features graph selection is intact.

Exact scope limit: Cargo-deny uses SemVer requirements, whose comparisons
[ignore build metadata](https://docs.rs/semver/latest/semver/struct.VersionReq.html#syntax).
This exception is not a checksum or arbitrary-file identity check. Both unchanged
locks retain the full reviewed `420.0.0+sqlcipher-4.20.0-sqlite-3.54.1-libtomcrypt-1.18.2`
registry version and archive checksum recorded above. A different major/minor/patch
release needs fresh policy review; source identity remains governed by the lock
and unchanged source controls.

### Focused policy regression

`python3 scripts/check_sqlcipher_license_exception.py` invokes the actual
cargo-deny executable against each real policy and disposable synthetic Cargo
path dependencies. The dependencies are publishable so the existing private-crate
exemption cannot mask the result. It does not modify any upstream manifest or
repository lock. Both reviewed-package positive controls failed before the
exception (exit 4); the complete 14-case run passes afterward, including with
`CARGO_TERM_COLOR=always` as used by CI. The harness requests uncolored output
for deterministic diagnostics and never suppresses policy warnings.

Each policy now demonstrably:

- accepts sqlcipher-src 420.0.0 with the complete reviewed expression;
- rejects each new license separately on a different package (exit 4);
- rejects each new license separately on sqlcipher-src 420.0.1 (exit 4),
  so an accidental caret/range allowance is detected;
- rejects GPL-3.0-only even on the reviewed package/version (exit 4);
- still accepts an ordinary MIT dependency (exit 0).

### Actual CI policy commands and warnings

`cargo-deny check licenses sources bans` was run from each existing Cargo root
with the same cargo-deny 0.20.2 as the hosted job. All three returned exit 0 and
`bans ok, licenses ok, sources ok`:

| Root | Duplicate warnings | Wildcard warnings | Unencountered license warnings |
| --- | ---: | ---: | ---: |
| `implementation/desktop` | 36 | 11 | 5 |
| `implementation/desktop/crates/selahcue-operator` | 42 | 9 | 3 |
| `implementation/desktop/crates/selahcue-stt` | 6 | 1 | 5 |

These existing warning classes remain visible under the unchanged policy;
a pass does not mean warning-free output. No full functional Rust suites were
repeated for this policy-only change. The pinned-toolchain check and
`git diff --check` also passed.

### SBOM generation and coverage

CI's cargo-cyclonedx 0.5.9 was installed into a temporary tool directory and
used for the existing commands:

```sh
# In implementation/desktop:
cargo cyclonedx --format json
# In implementation/desktop/crates/selahcue-operator:
cargo cyclonedx --format json --features stt --target all
# From repository root, before retaining the artifacts under /private/tmp:
python3 scripts/check_operator_sbom.py --self-test
python3 scripts/check_operator_sbom.py implementation/desktop/crates/selahcue-operator/selahcue-operator.cdx.json
```

Both generation commands returned exit 0. The existing guard's 11 self-tests
passed, and its actual operator-SBOM check found cpal, selahcue-stt, ureq,
whisper-rs and whisper-rs-sys. Additional traversal from each desktop/operator
SBOM root verified rusqlite 0.42.0, libsqlite3-sys 0.40.0 and the full reviewed
sqlcipher-src 420.0.0 version are reachable dependency components. The source
package retains the complete `MIT AND BSD-3-Clause AND blessing AND WTFPL`
license expression in both SBOMs, including the build dependency.

Generation printed 38 desktop and 11 operator warnings converting the existing
private crates' non-SPDX `Proprietary` label into named licenses; none concerned
sqlcipher-src. Fourteen generated SBOMs were retained under
`/private/tmp/sqlite-sbom-round1/`; no generated SBOM was added to Git, and no
pre-existing SBOM or ignored native artifact was replaced. This is metadata
inventory evidence, not installer notice/packaging verification.

### Subsequent native evidence and remaining gates

The controller's separately verified `sqlite-native-verification.md` records
native Linux and Windows encrypted-runtime assertions and retained legacy-backup
compatibility passing at source 62c9e1ea in the run linked above. Windows operator
encrypted-read/key behavior also passed. These are scoped passes in a run whose
Windows Rust job failed on separate A1/A2 endpoint/HTTP-test issues and whose
Linux browser gates also failed. Successful harness captures do not expose the
exact queried source/version strings; the exact strings above remain local
macOS observations.

The isolated ordinary bundled-SQLite runtime on Linux/Windows is still missing;
the two hosted data invocations both selected encryption. The original local-only
boundary above describes the initial verification, not a denial of this later
controller evidence. Independent fix re-review and exact-head hosted CI remain
pending; this local policy/SBOM pass does not promise a future all-jobs or release
pass and does not change provider, installer, device-resource or hostile-WAL
memory-check boundaries.
