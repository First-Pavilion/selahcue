# Goal Contract - 17tnw2b9ax2-reqwest-os-trust-store

## Identity

- Goal ID: 17tnw2b9ax2-reqwest-os-trust-store
- Parent goal ID: NONE
- Title: The cloud HTTP client runs on reqwest 0.13 trusting the operating-system certificate store, with ring as the only crypto provider, and a regression in either choice fails a gate
- Role: backend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9ax2
- Created: 2026-10-24
- Updated: 2026-10-24
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Land reqwest 0.12.28 to 0.13.5 for `selahcue-cloud` (feature `http`) under the owner's decision of 2026-10-24 (DEC-019): trust roots are the operating-system store (reqwest 0.13's `rustls-platform-verifier` default), `ring` stays the only crypto provider (`rustls-no-provider` plus an explicit, once-only install), both lock files are regenerated, the decision is recorded, the stale text is fixed, and tests and an import guard pin the choice. This supersedes Dependabot PR #190, which cannot merge as written.

## Baseline

**Verified** on `origin/main` at `013ec7af` (2026-10-24):

- `selahcue-cloud/Cargo.toml` asks reqwest 0.12 for `rustls-tls`; `ReqwestTransport::new()` builds a blocking client with a 10 s connect and a 60 s total timeout. Trust roots are the bundled `webpki-roots` set (hyper-rustls). `ring` is the only provider (selahcue-lan and selahcue-stt-cloud use it; no `aws-lc*` package is in any of the three lock files).
- PR #190 changes only that manifest line to `0.13` and edits the operator lock into an unrelated windows-sys/getrandom downgrade; `cargo metadata` then exits 101 in the workspace and in `selahcue-operator` (reqwest 0.13 has no `rustls-tls` feature).
- `cargo audit` on `origin/main`: workspace 8 vulnerabilities and 2 warnings, operator 8 and 4, stt 2 and 0 (five of the eight are `quinn-proto` entries that come with reqwest 0.12's lock entries).
- `tests/test_wire.rs` already pins the transport's headers and the absence of cookies; nothing tests TLS at all, and nothing pins the crypto provider for the cloud client.

## Inputs and evidence sources

- ClickUp 17tnw2b9ax2 (decision and acceptance criteria), Dependabot PR #190, the dependency review of 2026-10-24 (Kenji, Shadow), ClickUp 17tnw2b9aaz (redirect body replay: unchanged, not in scope)
- reqwest 0.13.0 to 0.13.5 CHANGELOG and source (`tls.rs`, `async_impl/client.rs`); `rustls-platform-verifier` 0.7.1 source (`verification/apple.rs`, `others.rs`, `windows.rs`)
- `selahcue-stt-cloud`'s `the_rustls_crypto_provider_is_actually_installed` (the pattern for the provider observable)
- `docs/decisions/DECISION-LOG.md` (format and numbering: DEC-019 is next)

## Scope

### In scope

Footprint:

- `implementation/desktop/crates/selahcue-cloud/` (Cargo.toml, `src/transport.rs`, `src/transport/tls_tests.rs`, `tests/test_tls_provider*.rs`, `tests/test_tls_system_store_linux.rs`, `tests/test_proxy_env.rs`, `tests/test_redirect_credentials.rs`)
- `implementation/desktop/Cargo.lock` and `implementation/desktop/crates/selahcue-operator/Cargo.lock` (regenerated; `selahcue-stt`'s lock checked, unchanged)
- both `deny.toml` files and `selahcue-stt-cloud/Cargo.toml` (stale comments only)
- `scripts/import_guards.sh` (one new section), `implementation/desktop/CLAUDE.md` (one bullet), `docs/decisions/DECISION-LOG.md` (DEC-019), this contract

### Non-goals

- The redirect policy and the 307/308 body replay (17tnw2b9aaz): pinned as unchanged in the PR description, not fixed, not asserted in a test
- Bumping `webpki-roots`, `rustls-webpki`, `ctutils` (the remaining RUSTSEC findings in the locks): a separate lock-refresh change
- Any change to `selahcue-stt-cloud`'s trust roots (it keeps `webpki-roots` through tokio-tungstenite) or to the LAN transport
- Windows installer or Android work

### Constraints

- One ticket, one branch, one Draft PR off `origin/main`; not merged and not marked ready by this role; no `Co-Authored-By` trailer
- No aws-lc crate in any lock file; no bundled root set in the cloud client's graph
- The only constructor that can widen the trust set is private and compiled for unit tests only
- Newly pulled crates younger than 14 days are listed and justified (team two-week window)
- Source ASCII-only

### Assumptions and unknowns

- **Verified on macOS only** (the host): the TLS refusals and the happy path through the platform verifier. **Verified on Linux** in a Debian bookworm arm64 container (`rust:1.98.0-slim-bookworm`): the same suite plus the system-store test. **Unknown**: Windows (verifier behaviour, revocation-check latency, the NSIS bundle build) and any real corporate TLS-inspecting root. CI is the first real run on Windows; Windows is not a CI target of the pull-request workflow today (Linux-only), so it waits for the next Windows installer build.
- **Unknown**: whether Apple's verifier treats a root the user installed in the keychain differently from the anchor the tests hand it; the tests cover the anchor path only.
- **Assumed**: a live GET to a public HTTPS host from the production constructor is an adequate manual check that a public CA's certificate is accepted (run once on macOS, recorded in the PR description).

## Dependencies and approvals

- Owner decision 2026-10-24, option P (recorded as DEC-019 by this change). Reviewers (Cody, Shadow, Quinn) are dispatched by the coordinator after the Draft PR is open.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. This contract stops at `GATE_REVIEW`: C-013 is open by design and C-014 is blocked.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `cargo metadata --locked` passes in all three Cargo roots | `cargo metadata --format-version 1 --locked` in `implementation/desktop`, `.../selahcue-operator`, `.../selahcue-stt` | exit 0 x3 | iteration 1 | PASS |
| C-002 | yes | The lock diff contains only what the reqwest change requires, no checksum changes on an unchanged version, no aws-lc package anywhere, and every crate younger than 14 days is justified | a package-set diff against `origin/main` (script in the PR description); `grep -c 'name = "aws-lc'` over the three lock files; crates.io release dates | workspace +7/-8 crates, operator +6/-9, stt unchanged; 0 changed checksums; 0 aws-lc; one crate younger than 14 days (`webpki-root-certs` 1.0.10, 5 days) with its justification | iteration 1 | PASS |
| C-003 | yes | The crypto provider is installed before the first client is built, idempotently, from many threads, over a provider someone else installed first, and a second `new()` in one process works | `cargo test -p selahcue-cloud --features http --test test_tls_provider --test test_tls_provider_preinstalled --test test_tls_provider_race` (one process each) | exit 0; 3 tests | iteration 2 | PASS |
| C-004 | yes | A certificate from an unknown signer, for another name, expired, or signed by a different root than the one trusted is refused before any request byte is sent, with a positive control (a server signed by a root the client was given is accepted) and a check that the failure is a certificate failure | `cargo test -p selahcue-cloud --features http --lib` (`transport::tls_tests`) | exit 0; 8 tests | iteration 2 | PASS |
| C-005 | yes | A root handed to one client does not leak into a production client; a client that cannot be built is a `TransportError` with a reason, not a panic; on Linux an empty CA bundle fails closed and a bundle holding the CA is honoured by the production constructor | the same `--lib` run; `test_tls_system_store_linux` in a `rust:1.98.0-slim-bookworm` container | exit 0; the Linux test passed in the container (not run on macOS: compiled out) | iterations 2 and 3 | PASS |
| C-006 | yes | Proxy, cookie, header and redirect-credential behaviour is unchanged from reqwest 0.12.28 | `test_proxy_env`, `test_redirect_credentials`, the existing `test_wire`; the probe of 2026-10-24 on 0.12.28 and 0.13.5 | exit 0; the probe results identical | iteration 2 | PASS |
| C-007 | yes | Every new test fails when the behaviour it names is altered | the mutation set M1 to M15 and L1, L2 (PR description) | each mutation turns the named test(s) red; the tree is restored | iteration 3 | PASS |
| C-008 | yes | `scripts/import_guards.sh` fails when reqwest's `rustls` feature, a webpki-roots bundle, or an aws-lc lock entry appears | mutations M13, M14, M15 | exit 1 with the named message each time; exit 0 on the real tree | iteration 3 | PASS |
| C-009 | yes | fmt, clippy -D warnings (cloud `http` and `openai`; operator default, `openai-notes`, `cloud-live`, `dev-keys,openai-notes`), tests, `cargo deny check licenses sources bans` in both roots, `check_launch_reachability.py` | the commands in the PR description | all exit 0 | iteration 4 | PASS |
| C-010 | yes | `cargo audit` is not worse than `origin/main` in any root | `cargo audit` before and after, three roots | workspace 8 to 3, operator 8 to 3, stt 2 to 2 vulnerabilities; no new warning | iteration 4 | PASS |
| C-011 | yes | The decision is recorded and the stale text is fixed | DEC-019 in `DECISION-LOG.md`; both `deny.toml` comments, `selahcue-cloud/Cargo.toml`, `transport.rs` docs, `selahcue-stt-cloud/Cargo.toml` | present; a grep for the old feature name and the old comment wording finds none outside history | iteration 1 | PASS |
| C-012 | yes | One `make ci` at the end is green | `make ci` | exit 0 | `make ci` ALL GREEN at the final code head (3e394fd6 plus docs): 5,690 Rust tests passed, 0 failed; Flutter 380 passed; API 1,127 passed, 19 skipped, 1 xfailed; import guards and launch reachability OK; `make ci` rewrote `pubspec.lock` (a Flutter version stamp), reverted and not committed | PASS |
| C-013 | yes | Independent review passed (code, security, QA) at the head SHA | review report pages | verdicts recorded, zero open blocking findings | to be dispatched by the coordinator | PENDING |
| C-014 | no | Windows behaviour of the chosen option is checked on Windows | a Windows build and the TLS suite | pass | no Windows host available to this role | BLOCKED |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: C-003 to C-008 from the worktree, each integration test file run alone and with its siblings (never `--exact`), every gate captured to a file and its exit code read (no piped gate)
- Broader regression verification: C-009 to C-012
- Independent verifier: Cody, Shadow and Quinn, dispatched by the coordinator
- Required environment: macOS arm64 host, Rust 1.98.0 (pinned), own `CARGO_TARGET_DIR`; a Linux arm64 container for the Linux path

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002, C-011
- Hypothesis: the working fix of the dependency review (variant P) applies to current `origin/main` with regenerated locks
- Change or investigation: re-applied the manifest change by hand on `013ec7af`; regenerated both locks with cargo; pinned three newly pulled crates to older compatible versions to respect the two-week window (`rustls-native-certs` 0.8.4, `schannel` 0.1.29, `webpki-root-certs` 1.0.10); wrote DEC-019; fixed the stale comments
- Verifier executed: `cargo metadata --locked` in three roots; package-set diff; crates.io dates
- Result: all three roots lock-consistent; workspace +7/-8 crates, operator +6/-9; no checksum changes; no aws-lc
- New evidence: `webpki-root-certs` is reachable only under `--target all` (wasm32), not on macOS, Windows or Linux; 1.0.10 is the oldest version that fixes RUSTSEC-2026-0383
- Decision: iterate

### Iteration 2

- Target criterion: C-003 to C-006
- Hypothesis: the existing suite cannot see a missing provider or a trust regression; tests must come first as observables
- Change or investigation: `ensure_crypto_provider` returning how the provider came about; private `ReqwestTransport::build(extra_roots)`; a loopback TLS server with a throwaway CA; five integration files each in its own process
- Verifier executed: cloud tests with `--features http` under `NO_PROXY=127.0.0.1,localhost`
- Result: the first run of the positive control FAILED on macOS (Apple's verifier rejects a server certificate valid for more than 398 days with an opaque -67901, even from a root handed in); the refusal tests had passed for that wrong reason. Fixed with a short validity window around the clock, and every refusal test now asserts the cause is a certificate failure
- New evidence: reqwest's `Certificate::from_der` defers validation to build time
- Decision: iterate

### Iteration 3

- Target criterion: C-005 (Linux), C-007, C-008
- Hypothesis: a Linux container can run what macOS cannot (the system-store path) and prove the fail-closed claim that was only read from source
- Change or investigation: `tests/test_tls_system_store_linux.rs`; mutation checks on macOS and in the container; guard mutations
- Verifier executed: `docker run rust:1.98.0-slim-bookworm`, the mutation driver
- Result: the Linux test passed first time and turns red under accept-any-certificate and under an opaque build error; all guard mutations exit 1
- New evidence: with `SSL_CERT_FILE` naming an empty bundle `new()` returns `could not set up TLS: ... No CA certificates were loaded from the system`
- Decision: iterate

### Iteration 4

- Target criterion: C-009, C-010, C-012
- Hypothesis: nothing outside the cloud crate moved
- Change or investigation: full gate set; audit before and after; one `make ci`
- Verifier executed: see the PR description
- Result: every gate green; `make ci` ALL GREEN; audit workspace 8 to 3, operator 8 to 3, stt 2 to 2 vulnerabilities
- New evidence: the three remaining findings (`webpki-roots`, `rustls-webpki`, `ctutils`) are lock-only and outside this change
- Decision: gate-review

## Risks and rollback

- Risks: trust now depends on the machine (a TLS-inspecting root installed there is trusted); Linux and Windows are unverified beyond the container run; a future `cargo update` of `rustls-platform-verifier` changes the verifier without a code diff here (the tests and the guard would show it)
- Rollback or recovery: revert the change (the bundled-roots alternative, variant W, is about ten lines and was built and tested during the review)

## Pause and escalation conditions

- A reviewer finds the OS-store posture contradicts a security requirement: stop and return to the owner (the decision, not this code, would change)
- `make ci` or a gate fails for a reason outside this change: report it, do not mask it

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9ax2-reqwest-os-trust-store.md`
- Validator result: recorded in the PR description
- Independent verification result: pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-013 pending (reviewers), C-014 blocked (no Windows host)
- ClickUp final evidence comment: written by the coordinator
