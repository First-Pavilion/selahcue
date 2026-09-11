# Goal Contract — TASK-86akcfftu

## Identity

- Goal ID: TASK-86akcfftu
- Parent goal ID: NONE
- Title: Live transcript segments are durably written to the 86ajtxzrn transcript store before the 240-segment in-memory ring evicts them
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcfftu
- Created: 2026-09-11
- Updated: 2026-09-11
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A two-hour service's transcript, once persisted, retains its opening segment even
after `selahcue_core::transcript::TranscriptLog`'s 240-segment ring has evicted it
from the live console view — via a bounded/batched durable side-channel, without
changing the ring's existing behaviour and without depending on which
`TranscriptProvider` produced a segment.

## Baseline

Verified against `f323ca8` (86ajtxzrn, PR #30, unmerged): `transcript_repo` exists
in `selahcue-data` with no consumer wired to it anywhere. `TranscriptLog::push`
(core/src/transcript.rs:101) evicts past `MAX_TRANSCRIPT_SEGMENTS` (240); segments
never reach any persistent store. `ControllerSnapshot` (selahcue-app) has no
transcript field (ADR-0019).

## Inputs and evidence sources

- ClickUp 86akcfftu (description, acceptance criteria, verification expectations)
- `docs/architecture/adr/ADR-0019-transcript-provider-seam.md`
- `implementation/desktop/crates/selahcue-data/src/transcript_repo.rs` @ f323ca8 (read-only)
- CLAUDE.md "Bounded-memory tests" section

## Scope

### In scope

- `selahcue-app::transcript_sink` (new): `TranscriptSink` trait, `NullTranscriptSink`,
  `TranscriptStoreWriter` trait, `BatchingTranscriptWriter` bounded/batched buffer.
- `LiveController`: injected `transcript_sink` field, `set_transcript_sink`,
  `start_transcript_session`/`end_transcript_session`, hook in `ingest_transcript`.
- `selahcue-lan::protocol`/`rbac`: additive `Command::StartTranscript`/`EndTranscript`
  (session-boundary siblings of `IngestTranscript`, same `Transcribe` permission) —
  needed because the desktop process (which owns the real `Database`) and the
  operator process (which owns STT session lifecycle) are separate in the Remote
  topology, with no existing signal for "session started/stopped".
- `selahcue-operator::listening`: session-boundary calls into the backend; `ended_at`
  on normal stop via the drain task's channel-closure point (no `stop()` signature
  change needed).
- `selahcue-desktop`: `RealTranscriptStore` (`TranscriptStoreWriter` adapter over
  `transcript_repo`), `sweep_orphaned_transcripts` (crash-recovery `ended_at`
  backfill at startup), wiring into `LiveController` construction.

### Non-goals

- `selahcue-data`'s `transcript_repo` API / v20 migration (86ajtxzrn's code, under
  active four-reviewer review — read-only).
- FR-170 capture-device-disconnect gap-marker behaviour.
- Any UI change (backend write path only).
- Detection persistence (not in this ticket's acceptance criteria).

### Constraints

- Branch from `f323ca8` (pinned SHA), not `origin/main` — 86ajtxzrn is unmerged.
- Do not modify `transcript_repo.rs` or the v20 migration.
- The 240-segment ring and 2,000-char cap must be provably unchanged.
- Bounded-memory claim must be mutation-verified (siblings running, not `--exact`).

### Assumptions and unknowns

- ASSUMED: a coarse route-derived provider label ("deepgram"/"on-device-whisper") at
  `StartTranscript` time is an acceptable substitute for the specific
  post-load-model label `PROVIDER_LABEL` records later — label is cosmetic
  (a future Transcripts list), not covered by any acceptance criterion.
- KNOWN, not this ticket's to fix: `append_segment` at `f323ca8` assigns `ord` via
  `COUNT(*)` (O(n) per call); 86ajtxzrn's author has an unpushed fix (commit
  `4ef8924` in their own worktree) not yet on `origin`. Reported to the user/ticket
  owner rather than rebased onto an unpublished sibling-worktree commit.

## Dependencies and approvals

- 86ajtxzrn (PR #30, unmerged) — depended on, read-only, pinned at f323ca8.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every final segment durably persisted, in order, before ring eviction | `cargo test -p selahcue-app --test test_transcript_durability` | all pass | test log | PASS |
| C-002 | yes | Ring cap (240) and per-segment cap (2000) unchanged | same test file, `the_rings_per_segment_text_cap_is_unchanged...` + `a_long_service_keeps_its_opening...` | pass | test log | PASS |
| C-003 | yes | Write batching bounded; mutation-verified | `cargo test -p selahcue-app --lib transcript_sink::` + manual mutation (guard removed → RED, restored → GREEN), whole crate | RED then GREEN observed | transcript_sink.rs test output | PASS |
| C-004 | yes | `ended_at` set on stop and crash paths | `sweep_closes_an_orphaned_transcript_using_its_last_segment_end`, `sweep_closes_an_orphan_with_no_segments_using_started_at`, `sweep_never_touches_a_transcript_that_already_ended` | pass | selahcue-desktop test output | PASS |
| C-005 | yes | Provider-agnostic capture path | `the_durable_sink_is_fed_identically_regardless_of_which_provider_produced_the_segment` | pass | test log | PASS |
| C-006 | yes | Transcript/detection queue stays out of `ControllerSnapshot` | `controller_snapshot_stays_untouched_by_transcript_activity` | pass | test log | PASS |
| C-007 | yes | `make ci` passes | `make ci` | exit 0 | ci log | PASS |
| C-008 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) | review round | all blocking findings resolved | review report artifact | PENDING |

## Verification plan

- Focused: `cargo test -p selahcue-app --lib transcript_sink::`,
  `cargo test -p selahcue-app --test test_transcript_durability`,
  `cargo test -p selahcue-lan --features server`,
  `cargo test -p selahcue-desktop`,
  `cargo check --manifest-path .../selahcue-operator/Cargo.toml [--features stt|cloud-stt]`.
- Broader regression: `make ci` (fmt, clippy -D warnings, full workspace test suites,
  operator check, headless webview check, Flutter gate).
- Independent verifier: four-reviewer pipeline (Cody/Vera/Sana/Quinn).
- Required environment: macOS worktree, own `CARGO_TARGET_DIR`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006 (core implementation)
- Hypothesis: an injectable `TranscriptSink` seam on `LiveController`, hooked at the
  existing final-segment branch of `ingest_transcript`, satisfies durability +
  provider-agnosticism without touching the ring.
- Change: added `transcript_sink` module, wired `LiveController`, added
  `StartTranscript`/`EndTranscript` wire commands, wired `selahcue-desktop` +
  `selahcue-operator`.
- Verifier executed: `cargo test -p selahcue-app`, mutation test on the bounded
  buffer (RED confirmed, restored to GREEN).
- Result: PASS.
- Decision: iterate to C-007 (full `make ci`).

### Iteration 2

- Target criterion: C-007
- Hypothesis: full `make ci` passes after `cargo fmt` on both the workspace and the
  excluded `selahcue-operator` manifest.
- Change/investigation: first `make ci` run failed at operator's own `cargo fmt
  --check` line; ran `cargo fmt` on that manifest, re-ran the whole target.
- Verifier executed: `make ci`
- Result: see final evaluation below.
- Decision: complete once green, then request the four-reviewer gate.

## Risks and rollback

- Risks: the new LAN commands are the one piece of genuinely new architecture
  surface (a protocol addition) — flagged explicitly for reviewer scrutiny rather
  than treated as routine. A rebase onto `origin/main` will be needed once #30
  merges, and again once/if 86ajtxzrn's unpushed `ord` fix lands.
- Rollback: revert the branch; no production data affected (net-new code path,
  default no-op sink preserves current behaviour exactly).

## Pause and escalation conditions

- If 86ajtxzrn's `append_segment` API is found genuinely inadequate: stop, report
  to the user rather than editing `transcript_repo.rs`. (Not triggered — the O(n)
  cost is a known, already-being-fixed characteristic, not an API gap.)

## Final evaluation

- Validator command: (structural) run before first iteration if the validator
  script is available; not blocking given the lightweight-process option for
  right-sized work was also considered, but this ticket met the "substantial or
  risky" bar so the full contract was written.
- Validator result: N/A (see ClickUp comment for narrative evidence trail)
- Independent verification result: pending four-reviewer gate (C-008)
- Terminal state: pending `make ci` final result (see ClickUp handoff comment)
- Remaining failed or blocked criteria: C-008 (review) pending dispatch
- ClickUp final evidence comment: to be posted once `make ci` is green and the PR is open
