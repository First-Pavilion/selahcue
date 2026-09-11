# Goal Contract — TASK-86akgqdv0

## Identity

- Goal ID: TASK-86akgqdv0
- Parent goal ID: NONE
- Title: Generated sermon-note drafts (`NoteDraft`) are persisted against their source
  transcript and the operator can edit them afterward, with the source transcript
  provably untouched (FR-123 "editable" half)
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdv0
- Created: 2026-09-11
- Updated: 2026-09-11
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A generated sermon-note draft survives beyond the confirm-and-generate dialog: it is
saved against its source transcript's row id, the operator can edit its title/
summary/section content afterward and the edit survives a restart, and the source
transcript's stored text is byte-identical before generation, after generation, and
after editing the draft. The AI-generated label and FR-128 fabrication disclosure
remain attached to the draft through an edit. A working proposal for whether
deleting a transcript cascades to delete its notes is implemented and flagged for
explicit product sign-off, mirroring how 86ajtxzrn handled its own open questions.

## Baseline

Verified against `origin/main` @ `2ca32e8` (86ajtxzrn PR #30 and 86akcfftu PR #31
both merged): `selahcue-data::transcript_repo` persists transcripts/segments/
corrections/detections with a `transcript_setting` key/value table that already
carries an inert `delete_cascade_to_notes` flag (`RetentionSettings`, default
`false`) explicitly reserved by 86ajtxzrn for "whichever future ticket adds the
notes table" — that is this ticket. `selahcue_core::providers::NoteDraft`/
`NoteSection`/`NotePoint` exist and are produced by `generate_sermon_notes()`
(`selahcue-cloud/src/lib.rs`), labelled via `GenerationOutcome::{ai_generated,
disclosure}`. `selahcue-operator/src/main.rs`'s `generate_sermon_notes` Tauri
command renders the draft into `dist/settings.js`'s `#pp-gen-result` panel and does
not persist it — the draft is lost when the panel closes/app restarts. Migration
head is v20 (`MIGRATIONS.len() == 20`, confirmed by counting `r#"` blocks in
`migrations.rs`). No file in `selahcue-operator` references `transcript_repo` —
the operator has no existing channel to a transcript's row id.

## Inputs and evidence sources

- ClickUp 86akgqdv0 description as reconstructed in this session's prompt (ClickUp
  MCP unreachable — `getaddrinfo ENOTFOUND mcp-proxy.anthropic.com` on two attempts
  at session start; to be re-verified against the live ticket before claiming
  completion, per the ticket's own instruction)
- `docs/product/prds/SelahCue-PRD.md` §EPIC-M, FR-123
- `implementation/desktop/crates/selahcue-data/src/transcript_repo.rs` (closest
  precedent: repo API shape, `RetentionSettings` seam, cascade doc comments)
- `implementation/desktop/crates/selahcue-core/src/providers.rs` (`NoteDraft`,
  `NoteSection`, `NotePoint`, `AI_GENERATED_LABEL`, `FABRICATION_DISCLOSURE`)
- `implementation/desktop/crates/selahcue-cloud/src/lib.rs` + `tests/test_openai.rs`
  (existing FR-123 byte-identical invariant test, `GenerationOutcome`)
- `implementation/desktop/crates/selahcue-operator/src/main.rs` +
  `dist/settings.js` (existing generate/preview/render flow to extend)

## Scope

### In scope

- `selahcue-data`: migration v21 (`sermon_note` table), new `sermon_note_repo`
  module (create/upsert, find-by-transcript, update), a `DataError::TooLarge`
  variant, cascade-on-delete wiring in `transcript_repo::delete`/`purge_expired`
  reading the existing `RetentionSettings::delete_cascade_to_notes` seam.
- `selahcue-operator/src/main.rs`: persist-on-generate (best-effort, mirrors
  `with_providers`' persistence-never-blocks pattern), new Tauri commands to load
  and edit the persisted draft.
- `selahcue-operator/dist/settings.js`: edit surface (title/summary/section items
  and outline points editable; AI label + disclosure always shown, including on an
  edited draft); load the persisted draft on panel activation.
- Tests: `selahcue-data` repo tests incl. a mutation-verified bounded-memory test
  and a persisted-storage byte-identical-transcript regression test; updated
  `test_transcript_repo.rs` for the cascade default change.
- A documented, explicitly-flagged proposal (code comments + PR/ClickUp comment)
  that transcript deletion cascades to notes BY DEFAULT going forward, reversing
  86ajtxzrn's placeholder `false` — pending product sign-off, not presented as
  decided.

### Non-goals

- FR-129 (regenerate / version retention, 86akgqdx8) — `create` upserts (replaces)
  the one draft row per transcript; no history is kept.
- FR-127 export formats (86akgqdwn).
- FR-130's remaining scope: surfacing the draft inside a Transcripts post-service
  viewer (86akgqdxr) — no such viewer exists yet in the operator.
- Per-section empty-state messaging (86akc0tua).
- Generating notes from a selected stored transcript (86akcffy0) — this ticket
  persists whatever draft the existing live-confirm-dialog flow produces.
- Any change to the LAN wire protocol (no transcript identity currently crosses
  operator↔desktop over the control link; see Assumptions).

### Constraints

- Branch from a freshly-fetched `origin/main`, own worktree, own
  `CARGO_TARGET_DIR` (`scph-worktrees/.cargo-target-86akgqdv0`).
- Migration is append-only (new v21 entry; never edit v0..v20).
- `selahcue-core` gains no new dependency (kept dependency-free); JSON encoding of
  section content happens in `selahcue-operator` (already depends on serde_json),
  not in `selahcue-core` or `selahcue-data`.
- Editing a draft must never clear `ai_generated`/`disclosure`/`provider` —
  enforced by `sermon_note_repo::update` only ever touching the editable columns.
- `make ci` must pass; mutation-verify the bounded-memory test and the
  byte-identical-transcript regression test (siblings running, not `--exact`).

### Assumptions and unknowns

- ASSUMED: the live-confirm-dialog generate flow has no transcript_id available
  to it today (the LAN control link carries only the finalized transcript TEXT,
  `window.scCompletedTranscript`, never a row id — confirmed by grep: `transcript_
  id` appears only in `selahcue-data`/`selahcue-app`/`selahcue-desktop`, never in
  `selahcue-lan` or `selahcue-operator`). Save-on-generate therefore resolves the
  target transcript as **the most recently started row** via
  `transcript_repo::list(db).first()`, opened through the operator's existing
  best-effort second connection to the shared `selahcue.db3` (same pattern as
  `providers_db`). This is a reasonable, explicitly-flagged working assumption for
  a single-active-session desktop app; a future ticket (86akgqdxr's viewer, or
  86akcffy0) that lets the operator address a specific transcript id directly can
  pass one through instead of relying on "most recent". Flagged in the PR/ClickUp
  comment, not silently decided.
- PROPOSED, not decided: `delete_cascade_to_notes` defaults to `true` going
  forward (notes cascade-delete with their source transcript by default) —
  reverses 86ajtxzrn's placeholder `false`. Needs explicit product-owner sign-off
  before merge; implemented against so the mechanism is real and testable, per
  the ticket's own instruction to "implement against" a proposed default.

## Dependencies and approvals

- 86ajtxzrn (PR #30) — MERGED, precedent for repo pattern + `RetentionSettings`
  seam.
- 86akcfftu (PR #31) — MERGED, not directly touched (live write path, separate
  `selahcue-app::transcript_sink`).
- Product-owner sign-off — PENDING — on the cascade-default proposal above.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `sermon_note` table + repo (create/read-by-transcript/update) exist, migration is v21 | `cargo test -p selahcue-data --test test_sermon_note_repo` | all pass | test log | PENDING |
| C-002 | yes | Draft persists across a fresh `Database::open` on the same file (restart-survives) | dedicated repo test opening a file-backed DB twice | pass | test log | PENDING |
| C-003 | yes | Editing title/summary/section items+outline points persists and survives a re-open | repo test + operator command test | pass | test log | PENDING |
| C-004 | yes | Source transcript stored text byte-identical before generation / after generation / after editing | new persisted-storage regression test in `selahcue-data` (companion to `selahcue-cloud`'s existing FR-123 in-memory test) | pass | test log | PENDING |
| C-005 | yes | Editing a draft never drops `ai_generated`/`disclosure` | repo test asserting both fields unchanged by `update` | pass | test log | PENDING |
| C-006 | yes | Cascade-on-delete proposal implemented + explicitly flagged as needing sign-off | code comments + `transcript_repo` tests (cascade true deletes note; false detaches note) + PR/ClickUp comment | pass + comment posted | test log + PR/ClickUp comment link | PENDING |
| C-007 | yes | Oversized/malformed edit rejected, storage stays bounded; mutation-verified | `cargo test -p selahcue-data` bounded-memory test, manual mutation (guard removed → RED, restored → GREEN, whole file w/ siblings) | RED then GREEN observed | test output | PENDING |
| C-008 | yes | `make ci` passes | `make ci` | exit 0 | ci log | PENDING |
| C-009 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) | review round | all blocking findings resolved | review report artifact | PENDING |

## Verification plan

- Focused: `cargo test -p selahcue-data --test test_sermon_note_repo`,
  `cargo test -p selahcue-data --test test_transcript_repo`,
  `cargo test -p selahcue-cloud`,
  `cargo check --manifest-path .../selahcue-operator/Cargo.toml`,
  `python3 scripts/operator_headless.py`.
- Broader regression: `make ci` (fmt, clippy -D warnings, full workspace test
  suites incl. feature-gated ones, operator check, headless webview check,
  Flutter gate).
- Independent verifier: four-reviewer pipeline (Cody/Vera/Sana/Quinn).
- Required environment: macOS worktree, own `CARGO_TARGET_DIR`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-007
- Hypothesis: a new `sermon_note` table + `sermon_note_repo` module, keyed 1:1 by
  `transcript_id`, with save-on-generate (upsert) and an explicit edit command
  that only touches editable columns, satisfies persistence + editability +
  label-preservation without touching `NoteDraft`'s shape or adding dependencies
  to `selahcue-core`.
- Change: (recorded after implementation below)
- Verifier executed: (recorded below)
- Result: (recorded below)
- Decision: (recorded below)

## Risks and rollback

- Risks: the "most recent transcript" resolution heuristic (see Assumptions) is
  the one genuinely new architectural judgment call in this ticket — flagged
  explicitly for reviewer scrutiny. Flipping `delete_cascade_to_notes`'s default
  changes already-merged, already-reviewed behaviour from 86ajtxzrn and needs
  product sign-off before merge.
- Rollback: revert the branch; migration is additive/forward-only and touches no
  existing table, so no data-loss risk from reverting pre-merge.

## Pause and escalation conditions

- If ClickUp MCP remains unreachable at completion: report plainly rather than
  silently skipping the ClickUp comment (per the ticket's explicit instruction).
- If the cascade-default flip is found too risky to implement against safely:
  stop and report rather than silently keeping the old default while claiming the
  proposal was implemented.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akgqdv0.md`
- Validator result: (recorded once run)
- Independent verification result: pending four-reviewer gate (C-009)
- Terminal state: (recorded once `make ci` is green and the PR is open)
- Remaining failed or blocked criteria: (recorded)
- ClickUp final evidence comment: to be posted once `make ci` is green and the PR
  is open (connector permitting)
