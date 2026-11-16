# C1: saved-draft generation preflight

Ticket: [Check the draft before generation](https://app.clickup.com/t/17tnw2b9dq9).
Date: 2026-11-11. Base: `7f6dbcbb4782854cbb0fea14a3bb5a9ffcf7fcd0`.

The native transcript-note command now checks the authoritative host's saved draft before
requesting generation. A failed check returns a fixed content-free error and spends no
generation. The existing save-time check remains necessary because notes can change while
the provider operation is in progress.

The public Tauri signature and production provider selection remain unchanged. The command
body is shared with a private provider-operation seam, allowing the real orchestration to
run against a configured synthetic OpenAI provider and the existing counting HTTP transport.
No environment credentials, live provider or new app/store API was used.

## Behavioral evidence

- Three failed-store attempts produced **three transport requests before the fix** and
  **zero after it**, not merely an unconfigured-provider refusal.
- The exact transcript detail, accepted draft and previous pending draft survived all three
  failures; no save or stage reached the store. A synthetic diagnostic canary did not enter
  the fixed error response. The host also strips raw store diagnostics before the backend
  returns, so this canary verifies the response boundary rather than an independent raw-error
  redaction branch in the operator.
- With reads recovered, the same provider/orchestration sent exactly one request and staged
  the parsed response. This is the positive control for provider readiness and counting.
- Notes created after a successful absent-draft preflight remained accepted, and generation
  staged its result instead of replacing them. Reads failing after successful preflight
  refused persistence and retained both accepted and pending payloads.
- Temporarily replacing the save-time check with `ExistingDraft::Absent` made both new race
  tests fail. The guard was restored before final tests.

## Verification

All Cargo commands used `CARGO_TARGET_DIR=/private/tmp/selahcue-pilot-a1-target`. Existing
compile-only sidecar/NDI placeholders were reused unchanged. Local loopback tests and the
Chrome harness ran with the required host permissions after a sandbox run refused socket
binds. No target cleanup, provider keys or environment activation was needed.

| Command | Result |
| --- | --- |
| `cargo test --offline --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features openai-notes regenerate_with_retention_tests --no-fail-fast` before fix | 30 passed; only new preflight regression failed, requests 3 versus 0 |
| Same focused command after fix | 31 passed |
| `cargo test --offline --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features openai-notes regenerate_with_retention_tests::draft_ --no-fail-fast` with save-time guard mutated | Both race tests failed as intended |
| `cargo test --offline --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features openai-notes --no-fail-fast` final restored source | 467 passed, 0 failed, 1 ignored |
| `cargo test --offline --manifest-path implementation/desktop/Cargo.toml -p selahcue-app --features server --test test_sermon_note_durability --no-fail-fast` | 26 passed |
| `SELAHCUE_HEADLESS_REQUIRE=1 make operator-headless` | Browser executed: 2,906 checks, 0 failures; existing generation transport-error alert passed |
| `cargo clippy --offline --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --all-targets --features openai-notes -- -D warnings` | Passed after replacing new test `unwrap()` calls with descriptive assertions |
| `cargo fmt --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml -- --check`; `git diff --check` | Passed |

The ignored operator test is the XDG-runtime child-process entry point invoked only by its
parent. The pilot-source integration binary has no tests under these feature flags.

## Evidence limits and handoff

This is local macOS source/fixture and Blink browser evidence. It does not establish live
provider fidelity, installed Tauri/WebView behavior, hosted CI, deployment or Windows package
acceptance. Native **Windows 10 / 4 GB** memory, paging, timer/manual-output responsiveness and
full-service performance remain **unmeasured**. The full unrelated repository CI suite was
outside this task's verification scope. Independent Cody, Shadow, Quinn and Vera review and
external/native integration remain with the delivery controller.

C3 owns the separate terminal-generation-error UI that hides a previously rendered draft.
No UI redesign is included here. C3 can reuse `counting_notes_provider` and
`transcript_generate_notes_with` for deterministic provider-ready orchestration scenarios.
