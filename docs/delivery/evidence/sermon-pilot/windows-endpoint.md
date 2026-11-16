# Windows endpoint staging collision — A1

Ticket: [17tnw2bey5m](https://app.clickup.com/t/17tnw2bey5m). Recorded 2026-11-11 against base `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`.

## Status

Source fix and macOS checks complete. **Acceptance remains pending a current Windows run with default features and with `--features encryption`.** No current Windows runtime was supplied to this task. Historical Windows RED and current macOS GREEN below are separate evidence; a macOS pass does not exercise the Windows-only error branch. Independent review is coordinated separately by the controller. No release or pilot-readiness claim follows from this change.

## Root cause and historical RED

The controller retrieved [scheduled Windows CI run 42471432588](https://github.com/First-Pavilion/selahcue/actions/runs/42471432588), dated 2026-11-08, on the exact base above. Its `cargo test --workspace --no-fail-fast` and desktop encryption test both fail `endpoint::tests::a_directory_at_the_staging_name_is_skipped_and_left_intact`:

```text
publish must succeed on a fresh name: Os { code: 5, kind: PermissionDenied, message: "Access is denied." }
test result: FAILED. 118 passed; 1 failed; 1 ignored
```

The retained local log is `.superpowers/sdd/2026-11-11-sermon-pilot-foundation/windows-main-failures.log`, lines 5373–5383 and 12274–12284. It is controller evidence, not a file changed by A1.

The owning operation is `create_staging`'s `OpenOptions::write(true).create_new(true).open(&tmp)`, reached before writing or renaming. A directory already occupies the injected first name. Windows returns access denied for that file-open attempt; the old match retried only `AlreadyExists`, immediately returning this `PermissionDenied`. This is staging-name selection, not the final rename's sharing-violation retry policy.

The change handles `PermissionDenied` only on Windows and only when `symlink_metadata` confirms that the failed name is itself a directory. It then consumes another name within the existing eight-attempt limit. Metadata is checked after the failed exclusive open and does not follow a final symlink. Other errors, absent/unreadable names, and ordinary permission failures still return unchanged. No contender is removed or opened for writing. The create-new open, private-directory verification, owner-only mode, atomic rename, rename retry budget, and cleanup of only an owned staging file remain intact.

## Regression

The existing named directory test now puts a sentinel inside the competing directory, asserts exactly two names were requested, reads the unchanged sentinel, and checks that no extra staging entry remains. It publishes a complete endpoint fixture and reads it through `selahcue_lan::local_endpoint::read_descriptor_as`, the hardened reader shared with the operator. The strengthened test was written before the production fix. The historical Windows failure supplies RED for the existing regression; no new Windows RED/GREEN was produced locally.

## Current macOS verification

Host: arm64 macOS/Darwin 25.3.0. All Cargo commands used the repository-pinned toolchain, `--offline --locked`, and `CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`; no dependency downloads were performed. This stable isolated target can be reused by later sequential foundation tasks.

| Check | Command after the environment prefix | Result |
| --- | --- | --- |
| Baseline publication implementation | `cargo test --offline --locked --manifest-path implementation/desktop/Cargo.toml -p selahcue-desktop endpoint::tests -- --nocapture` | 42 passed, 0 failed, 4 ignored, 98 filtered; local baseline does not reproduce Windows |
| Patched default endpoint siblings | same command | 42 passed, 0 failed, 4 ignored, 98 filtered |
| Patched encryption endpoint siblings | `cargo test --offline --locked --manifest-path implementation/desktop/Cargo.toml -p selahcue-desktop --features encryption endpoint::tests -- --nocapture` | 42 passed, 0 failed, 4 ignored, 98 filtered |
| Hardened reader/path suites, outside sandbox | `cargo test --offline --locked --manifest-path implementation/desktop/Cargo.toml -p selahcue-lan --test test_local_endpoint --test test_local_endpoint_decisions -- --nocapture` | 64 passed, 4 ignored; then 3 passed, 0 failed |
| Affected lints | `cargo clippy --offline --locked --manifest-path implementation/desktop/Cargo.toml -p selahcue-desktop --all-targets --features encryption -- -D warnings` | exit 0 |
| File formatting | `rustfmt --check --edition 2021 implementation/desktop/crates/selahcue-desktop/src/endpoint.rs` | exit 0 |
| Patch whitespace | `git diff --check` | exit 0 |

Ignored entries are intentional child-process entry points, exercised by their passing parent tests. The endpoint siblings cover collision exhaustion, symlinks, permission failures, private-directory rejection, partial writes, concurrent readers/publishers, and owned-file cleanup. Reader checks include oversized/non-text files, FIFO/symlink rejection, ownership, modes, and unsafe parent directories; they do not claim arbitrary JSON schema validation.

The exact brief command initially stopped before compiling because the restricted worktree target directory was unwritable (`Operation not permitted .../implementation/desktop/target...`). Moving only the build target to the isolated temporary directory resolved that restriction.

The first additional reader run inside the sandbox reported 63 passed, 1 failed, 4 ignored: `any_mode_other_than_0600_is_refused` requested mode `04600` but the OS retained `0600`. An independent temporary-file probe observed `04600 -> 0600`, `02600 -> 0600`, and `01600 -> 01600`. The same focused suites outside the sandbox then passed as recorded above; no LAN source or test was weakened. The directory-decision suite was also run separately inside the sandbox: 3 passed.

Local detailed outputs are `/private/tmp/selahcue-pilot-a1-default.log`, `/private/tmp/selahcue-pilot-a1-encryption.log`, `/private/tmp/selahcue-pilot-a1-reader.log` (sandbox limitation), `/private/tmp/selahcue-pilot-a1-reader-unsandboxed.log`, `/private/tmp/selahcue-pilot-a1-reader-decisions.log`, and `/private/tmp/selahcue-pilot-a1-clippy.log`. Temporary logs are session evidence, not durable CI artifacts.

## Still required

Run the endpoint sibling command on Windows with default features, then repeat with `--features encryption`, on the final reviewed commit. Retain actual counts and output proving the named regression runs, the sentinel survives, and the hardened reader accepts the new descriptor. These current Windows checks and independent review remain acceptance gates. No unrelated full workspace, GUI, provider, deployment, timer, output-device, or production verification was performed by A1.
