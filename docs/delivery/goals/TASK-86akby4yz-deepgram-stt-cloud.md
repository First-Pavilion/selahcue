# Goal Contract — TASK-86akby4yz-deepgram-stt-cloud

## Identity

- Goal ID: TASK-86akby4yz-deepgram-stt-cloud
- Parent goal ID: NONE
- Title: A Deepgram streaming `TranscriptProvider` lives in its own crate, behind an off-by-default feature, with bounded buffers that a mutation battery cannot get past
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby4yz
- Created: 2026-09-04
- Updated: 2026-09-04
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`selahcue-stt-cloud` exists as a workspace member that implements
`selahcue_core::transcript::TranscriptProvider` over a real Deepgram streaming
WebSocket, converts interim and final results into `ProviderSegment`s with the
provisional-versus-settled distinction preserved, buffers both directions
(audio in, segments out) inside bounds that are pinned at compile time and
proven by tests that fail when the bound is removed, and reports its own
readiness as a crate API that ticket 86akby7th can render without guessing.

## Baseline

Verified at `origin/main` = `cb006fc6ce12df1f03341203c3894da2c6c57429`
(fetched fresh 2026-09-04; local `main` was level with it at that moment):

- There is no streaming transport anywhere in the desktop tree. `TranscriptionMode::Cloud`
  exists as a persisted setting (`selahcue-core/src/providers.rs:35`) and
  `ProvidersConfig::may_stream_cloud_audio()` gates it (`providers.rs:404`), but nothing
  reads either value. Verified by reading both.
- The seam is `TranscriptProvider` in `selahcue-core/src/transcript.rs` — `label()` and a
  synchronous, non-blocking `poll()`. Verified by reading the file.
- The on-device mirror is `selahcue-stt/src/provider.rs`: an `Arc<Mutex<VecDeque<_>>>`
  bounded by entry count only (`MAX_PENDING_SEGMENTS = 256`), drop-oldest. Verified by
  reading the file. It has **no byte bound**, which this crate adds.
- The intended dependency stack is already in `implementation/desktop/Cargo.lock`:
  `tokio` 1.53.1, `tokio-tungstenite` 0.24.0, `tungstenite` 0.24.0, `rustls`,
  `webpki-roots` 0.26.11/1.0.9, `futures-util`. `webpki-roots`' CDLA-Permissive-2.0
  licence is already allowlisted in `implementation/desktop/deny.toml`. Verified by
  reading the lockfile and `deny.toml`.
- `make ci` and `.github/workflows/ci.yml` run feature-gated Rust suites only from
  explicit per-crate lines. Verified by reading both. A new crate's feature-gated tests
  would therefore be run by nothing — the condition `CLAUDE.md` records for
  `selahcue-stt`.
- `.env` at the repository root reads 0 bytes; no `DEEPGRAM_API_KEY` is available.

## Inputs and evidence sources

- ClickUp 86akby4yz, including the two amendment comments (Diego's scope boundary and
  readiness-shape amendment; the owner's branch-base correction to `main`).
- `implementation/desktop/crates/selahcue-core/src/transcript.rs` and `providers.rs`.
- `implementation/desktop/crates/selahcue-stt/src/provider.rs` (the mirror).
- `implementation/desktop/crates/selahcue-engine/tests/test_raster.rs` (the worked example
  for bounded-memory tests).
- `CLAUDE.md`, "Bounded-memory tests".
- Deepgram live documentation, fetched 2026-09-04: the streaming reference
  (`developers.deepgram.com/reference/speech-to-text-api/listen-streaming`) and the
  authentication page.

## Scope

### In scope

- A new workspace member `implementation/desktop/crates/selahcue-stt-cloud/`.
- A `TranscriptProvider` implementation draining a bounded segment queue.
- Deepgram frame parsing, interim-versus-final mapping, and the request specification
  (URL, query parameters, authorization header).
- Bounded retry with backoff and a clean give-up.
- Error classification that distinguishes a rejected credential from a network failure.
- A readiness API shaped for 86akby7th to render.
- The real WebSocket driver behind an off-by-default `deepgram` feature.

### Non-goals

- Any operator-crate change, any `dist/` change, any `selahcue-cloud` or `selahcue-core`
  change. 86akby7th renders this; lane B owns the notes side.
- Quota, minutes counters, heartbeats, self-terminate behaviour.
- Server-minted `/v1/stt/session` tokens (Phase 2) beyond modelling the credential shape.
- Microphone capture — this crate receives PCM chunks; it does not open a device.

### Constraints

- Footprint is the new crate, one workspace-member line, and this contract. Nothing else.
- The credential is an injected constructor parameter. Exactly one function in the crate
  reads the process environment, so a change to the shared `.env` loader (86akby6yy, under
  security review) costs one function here, not a refactor.
- The consent gate `ProvidersConfig::may_stream_cloud_audio()` stays authoritative and must
  not be re-derived; this crate consumes its verdict.
- The default workspace build must pull in no async runtime and no WebSocket stack.

### Assumptions and unknowns

- ASSUMED: `nova-3` is the current recommended model. Validated against Deepgram's live
  streaming reference on 2026-09-04, which lists `nova-3` first.
- UNKNOWN: measured first-token and interim-to-final latency against the live service.
  Requires a real key, which does not exist yet. Owner supplies the key; this is recorded
  as a criterion that stops rather than one that is faked.
- UNKNOWN: whether the owner wants the two CI lines that would run the feature-gated
  suite. Raised on the ticket; not taken unilaterally.

## Dependencies and approvals

- 86akby6yy (shared `.env` loader) — merged-ready, PR #18 Draft, under security review by
  Sana. This crate's entire coupling to it is one environment-variable name, so the review
  outcome does not block this work.
- 86akby7th consumes the readiness API defined here. Blocked on this ticket by design.
- Lane B (sermon notes) owns `cloud_status` / `cloud_connected` / `notes_provider` in
  `providers_view_of()`. This crate mirrors its state vocabulary rather than inventing one.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The provider implements `TranscriptProvider`; `poll()` drains queued segments in order and empties | `cargo test -p selahcue-stt-cloud --test test_provider` | exits 0 | test output | PENDING |
| C-002 | yes | `poll()` returns promptly while the producer is still streaming — it does not wait for the stream to end | `cargo test -p selahcue-stt-cloud --test test_provider` | exits 0; the test asserts a segment arrived mid-stream before asserting latency | test output | PENDING |
| C-003 | yes | `label()` names Deepgram and differs from the on-device engine's label | `cargo test -p selahcue-stt-cloud --test test_provider` | exits 0 | test output | PENDING |
| C-004 | yes | Interim and final Deepgram frames map onto `ProviderSegment` with `is_final` preserved in both directions | `cargo test -p selahcue-stt-cloud --test test_protocol` | exits 0 | test output | PENDING |
| C-005 | yes | The segment queue is bounded in entry count **and** bytes, both bounds pinned by `const _: () = assert!` beside the constants and inside the tests | `cargo test -p selahcue-stt-cloud --test test_queue` | exits 0 | test output | PENDING |
| C-006 | yes | Each bound's test fails when that bound is removed — mutation-verified with siblings running, never `--exact` | mutate, run `cargo test -p selahcue-stt-cloud`, restore | RED on mutation, GREEN restored, recorded per mutation | ClickUp comment | PENDING |
| C-007 | yes | A positive control proves a benign segment still flows through the queue and out of `poll()` | `cargo test -p selahcue-stt-cloud --test test_queue` | exits 0 | test output | PENDING |
| C-008 | yes | The inbound audio ring is bounded in chunk count and bytes, with the same test treatment | `cargo test -p selahcue-stt-cloud --test test_audio` | exits 0 | test output | PENDING |
| C-009 | yes | Reconnect backoff is bounded and gives up rather than retrying forever; a rejected credential is not retried at all | `cargo test -p selahcue-stt-cloud --test test_retry` | exits 0 | test output | PENDING |
| C-010 | yes | With no credential the provider fails with an error naming `DEEPGRAM_API_KEY`; it does not hang or panic | `cargo test -p selahcue-stt-cloud --test test_credential` | exits 0 | test output | PENDING |
| C-011 | yes | A rejected credential and a network failure are distinguishable, and their prescribed operator actions differ | `cargo test -p selahcue-stt-cloud --test test_error` | exits 0 | test output | PENDING |
| C-012 | yes | The secret never appears in any `Debug` or `Display` output of any public type in the crate | `cargo test -p selahcue-stt-cloud --test test_credential` | exits 0 | test output | PENDING |
| C-013 | yes | Streaming is unreachable without `may_stream_cloud_audio()`: the full 2×2 of mode × consent is asserted, and no other constructor for the authorization exists | `cargo test -p selahcue-stt-cloud --test test_consent` | exits 0 | test output | PENDING |
| C-014 | yes | The readiness API is a tri-state (not a boolean) and reports all three states | `cargo test -p selahcue-stt-cloud --test test_readiness` | exits 0 | test output | PENDING |
| C-015 | yes | The default build pulls in no async runtime and no WebSocket stack | `cargo tree -p selahcue-stt-cloud -e normal` | no `tokio`, `tokio-tungstenite`, `tungstenite`, `rustls` in the tree | command output | PENDING |
| C-016 | yes | The feature build compiles and its stub-socket suite passes | `cargo clippy -p selahcue-stt-cloud --features deepgram --all-targets -- -D warnings` and `cargo test -p selahcue-stt-cloud --features deepgram` | both exit 0 | command output | PENDING |
| C-017 | yes | The module's own documentation states the developer-key path is temporary and replaced by server-minted grant tokens | read `src/lib.rs` | the statement is present in the crate-level doc comment | file | PENDING |
| C-018 | yes | No file under `crates/selahcue-cloud/`, `crates/selahcue-core/` or `crates/selahcue-operator/` is modified | `git diff --stat origin/main...HEAD` | none of those paths appear | command output | PENDING |
| C-019 | yes | `make ci` passes end to end | `make ci` | ALL GREEN | terminal output | PENDING |
| C-020 | yes | `cargo deny check licenses sources bans` and `cargo audit` are clean | both commands | exit 0 | command output | PENDING |
| C-021 | no | Live-service wire parameters and measured latency recorded | manual run against Deepgram with a real key | parameters and P50 recorded on the ticket | ClickUp comment | PENDING |

C-021 is non-mandatory **only because the key does not exist yet**. It is not waived: it
is the one criterion that a stub socket cannot satisfy, and it is reported as an open gate
rather than marked passed.

## Verification plan

- Focused verification: the per-module test files listed above, run as a whole crate
  (`cargo test -p selahcue-stt-cloud`) so siblings are present, never with `--exact`.
- Mutation verification: for each named bound and each named guard, remove or invert it,
  confirm the suite goes RED with siblings running, restore, confirm GREEN. Recorded per
  mutation on the ticket.
- Broader regression verification: the whole `make ci` target, run once end to end after
  the last fix rather than trusting an earlier green line.
- Supply chain: `cargo deny` and `cargo audit` from `implementation/desktop`.
- Independent verifier: Cody (code), Vera (performance — the queue under load), Sana
  (security — credential handling and egress), Quinn (QA).
- Required environment: this Mac; the Rust toolchain pinned by `rust-toolchain.toml`. No
  network dependency in the suite. `make ci` serialised with lane B.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-017 (the crate itself)
- Hypothesis: keeping every control in the default, dependency-free build — with only the
  socket driver behind the `deepgram` feature — makes the controls reachable by
  `cargo test --workspace`, which CI already runs, without touching `make ci` or the
  workflow and therefore without leaving the crate linted by nothing.
- Change or investigation: write the crate.
- Verifier executed: pending
- Result: pending
- New evidence: pending
- Decision: iterate

## Risks and rollback

- Risks:
  - The feature-gated suite is run by no gate unless two lines are added outside this
    ticket's footprint. Mitigated by putting the controls in the default build; the
    residual gap is reported, not hidden.
  - A timing-based "poll does not block" test is a flakiness risk. Mitigated by asserting
    the structural property (a segment arrived while the producer was still running) as
    the primary claim and treating wall-clock only as a generous ceiling.
  - `cargo deny`'s `multiple-versions = "warn"` could become noisier. Checked explicitly.
- Rollback or recovery: the work is one new crate plus one manifest line on its own
  branch. Reverting is deleting the directory and the line; nothing existing depends on it
  until 86akby7th wires it.

## Pause and escalation conditions

- The live-key criteria (C-021) require a real `DEEPGRAM_API_KEY`. Stop and report rather
  than fabricate a latency number. Owner supplies the key.
- Any need to change `cloud_status` / `cloud_connected` / `notes_provider`: lane B owns
  that definition. Escalate rather than define a parallel one.
- Any need to touch `make ci` or `.github/workflows/ci.yml`: outside the fixed footprint.
  Escalate to the owner with the exact lines.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akby4yz-deepgram-stt-cloud.md --completion`
- Validator result: pending
- Independent verification result: pending
- Terminal state: pending
- Remaining failed or blocked criteria: pending
- ClickUp final evidence comment: pending
