# Goal Contract — TASK-86akgqdx8

## Identity

- Goal ID: TASK-86akgqdx8
- Parent goal ID: NONE
- Title: Regenerate produces a new sermon-note draft through the existing
  consent-gated generation path while retaining the currently-saved draft
  ("prior version") until the operator explicitly accepts the new one (FR-129)
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdx8
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

An operator with an existing saved sermon-note draft can regenerate it. The
regeneration runs through the exact same consent-gated `generate_sermon_notes`
pipeline (same gate, same degraded-fallback, same fabrication disclosure) as a
first-time Generate. The currently-saved draft (the "prior version") is never
overwritten by the regeneration attempt itself — it is retained, untouched and
retrievable, until the operator explicitly confirms the new draft (at which
point it replaces the prior one) or discards the new draft (at which point the
prior one is untouched and nothing changes). A transport failure during
regeneration never loses the prior draft, because nothing is written to the
"new draft" slot unless generation actually succeeded.

**Retention model decided by this contract (documented per the ticket's
explicit request):**
- **Single prior version, not a history.** Matches the PRD's singular
  "prior version retained until replaced." Only the currently-accepted draft
  is guaranteed retained; there is no multi-version stack.
- **Explicit-confirm-before-replace, not automatic-replace-with-undo.** The
  ticket's own scope/expected-behaviour text says the prior draft is
  retained "until the new draft is confirmed/accepted by the operator" and
  "available until they explicitly accept the new one" — both phrasings
  describe a pending state requiring an explicit accept action, not an
  immediate replace with an undo affordance.

## Baseline

Verified against `origin/main` @ `4b21c399d07f3010c6dad141e50c11cd4fdb1a48`
(PRs #44-#50 merged: bugfix, generate-from-stored-transcript 86akcffy0,
scripture verification 86akby820, the Transcripts workspace 86akgqdxr, podcast/
short-description artifacts 86akgqdwc). `implementation/desktop/crates/
selahcue-data/src/migrations.rs` has exactly 21 migrations (`MIGRATIONS.len()
== 21`, counted fresh via `grep -c '^    r#"'`) — the last is v20->v21,
`sermon_note`. `sermon_note_repo::create` is a plain `INSERT ... ON
CONFLICT(transcript_id) DO UPDATE`, replacing the row wholesale with no
retention, exactly as the ticket describes. The operator process
(`selahcue-operator`) never opens `selahcue-data` directly for this feature
(PR #33 / Sana F1) — persistence goes `selahcue-operator` ->
`selahcue_app::Backend` (Local shell or `RemoteOperator` LAN client) ->
`Command::{Save,Update}SermonNoteDraft` -> `LiveController::apply` (in
`selahcue-app::controller`) -> `SermonNoteStore` trait -> (on the desktop
process) `RealSermonNoteStore` in `selahcue-desktop/src/main.rs` ->
`sermon_note_repo`. Any new persistence surface for regenerate must follow
this exact same chain — the ticket's stated file footprint
(`selahcue-data`, `selahcue-cloud`, `selahcue-operator/src/main.rs`,
`dist/settings.js`) under-states this: it omits `selahcue-lan` (wire
protocol + RBAC) and `selahcue-app` (the trait + both `Backend` impls),
which the existing architecture requires touching for ANY new persistence
verb, matching the PR #33 precedent this ticket sits on top of. This is
flagged and will be explained in the MR description; deviating from a
stale/incomplete footprint the ticket itself describes as approximate is not
a scope change.

`generate_sermon_notes` (`selahcue-cloud/src/lib.rs`) needs no change: it
already returns a `GenerationOutcome` from the SAME fallback ladder for every
caller; regenerate reuses it unmodified by calling the same
`run_note_generation` helper in `selahcue-operator/src/main.rs` that
first-time Generate already uses.

Sermon-note wire messages (`SermonNoteDraftInput`/`SermonNoteDraftView`/
`Command::{Load,Save,Update}SermonNoteDraft`/`ServerMessage::SermonNoteDraft`)
are NOT part of the cross-language pinned contract
(`selahcue-lan/tests/test_protocol.rs`'s
`wire_fixtures_are_stable_for_cross_language_clients` only pins
Hello/Auth/Pair/PublishState fixtures; grep of
`implementation/mobile/selahcue_controller` finds zero references to
`SermonNote`), so new sermon-note wire messages need no Dart-side fixture
change.

## Inputs and evidence sources

- ClickUp 86akgqdx8, fetched live via `clickup_get_task` (full description,
  scope, non-goals, acceptance criteria, file footprint, verification
  expectations — reproduced in this contract's Objective/Scope sections).
- `docs/product/prds/SelahCue-PRD.md` §EPIC-M, FR-129 (as cited by the ticket).
- `implementation/desktop/crates/selahcue-data/src/sermon_note_repo.rs` +
  `migrations.rs` (v20->v21 `sermon_note` table + its doc comment, which
  explicitly anticipates this ticket).
- `implementation/desktop/crates/selahcue-lan/src/protocol.rs` + `rbac.rs`
  (`SaveSermonNotes` permission + its doc comment, which explicitly names
  "a legitimate regenerate" as a scenario the existing `SaveSermonNoteDraft`
  handler already had to reason about).
- `implementation/desktop/crates/selahcue-app/src/{sermon_note_store,
  controller,operator}.rs` (the full LAN-mediated persistence chain).
- `implementation/desktop/crates/selahcue-desktop/src/main.rs`
  (`RealSermonNoteStore`, the only real implementation of the trait).
- `implementation/desktop/crates/selahcue-operator/src/main.rs`
  (`generate_sermon_notes`, `transcript_generate_notes`, `run_note_generation`,
  `Backend` enum, `draft_json`/`sermon_note_draft_json`).
- `implementation/desktop/crates/selahcue-operator/dist/{settings,
  transcripts}.js` (both consoles render a saved/generated draft — CLAUDE.md's
  note on the earlier caveat-rendering MAJOR bug applies equally here).

## Scope

### In scope

- **Migration v21->v22** (`selahcue-data/src/migrations.rs`): additive,
  nullable "pending regeneration" columns on `sermon_note`
  (`pending_title`, `pending_summary`, `pending_sections`,
  `pending_scriptures`, `pending_ai_generated`, `pending_disclosure`,
  `pending_provider`, `pending_model`, `pending_generated_at`). NULL (the
  default for every existing row) = no pending regeneration. Re-verify the
  actual next free version number immediately before writing the migration
  and again immediately before finalizing (sibling tickets in this batch may
  add migrations concurrently).
- **`sermon_note_repo.rs`**: `PendingRegeneration` input type,
  `SermonNoteRecord.pending: Option<PendingRegenerationRecord>`,
  `stage_regeneration` (requires an existing row; same bounds checks as
  `create`; overwrites any not-yet-confirmed pending regeneration — single
  pending slot, documented), `confirm_regeneration` (moves pending -> current,
  clears pending; `NotFound` if nothing is pending), `discard_regeneration`
  (clears pending; idempotent no-op if nothing was pending). `create`/
  `update`/`find_by_transcript`/`list_detached`/`delete_by_id`/
  `delete_for_transcript` behaviour is UNCHANGED (existing tests for these
  keep passing unmodified) — retention logic is additive, not a rewrite of
  the upsert-replace `create` path.
- **`selahcue-lan/src/protocol.rs`**: three new `Command` variants
  (`StageSermonNoteRegeneration`, `ConfirmSermonNoteRegeneration`,
  `DiscardSermonNoteRegeneration`) and one new `ServerMessage` variant
  (`SermonNoteRegenerationState { transcript_id, current, pending }`) —
  additive; the existing `SermonNoteDraft`/`SermonNoteDraftView`/
  `Load/Save/UpdateSermonNoteDraft` wire shapes are untouched, so the pinned
  `sermon_note_server_messages_round_trip` fixture needs no byte change.
- **`selahcue-lan/src/rbac.rs`**: the three new commands require
  `Permission::SaveSermonNotes` (same tier as `SaveSermonNoteDraft`, same
  reasoning — they attach new provenance / replace persisted content and the
  operator console's own regenerate flow is the only legitimate caller).
- **`selahcue-app`**: `SermonNoteStore` trait gains
  `stage_regeneration`/`confirm_regeneration`/`discard_regeneration`;
  `NullSermonNoteStore` gets honest no-op/refusal implementations;
  `LiveController::apply` gets three new match arms (mirroring
  `SaveSermonNoteDraft`'s existing disclosure-pairing enforcement where
  relevant); `OperatorShell` and `RemoteOperator` each get the three new
  methods, mirroring the existing `save_sermon_note_draft`/
  `update_sermon_note_draft` pattern exactly (including `RemoteOperator`'s
  `would_exceed_wire_cap` pre-send guard).
- **`selahcue-desktop/src/main.rs`**: `RealSermonNoteStore` implements the
  three new trait methods against `sermon_note_repo`.
- **`selahcue-operator/src/main.rs`**: `Backend` enum gets the three new
  dispatch methods (mirroring existing `save_sermon_note_draft` dispatch).
  `generate_sermon_notes` and `transcript_generate_notes` are changed so
  that, on a successful generation, IF a draft already exists for the
  resolved transcript id, the new draft is staged (not upserted directly) and
  the response reports `pending_confirmation: true` + the still-current prior
  draft; when no draft exists yet, behaviour is completely unchanged (a plain
  `create`, no confirmation step — first-time generation is not this
  ticket's concern). Two new Tauri commands:
  `confirm_sermon_note_regeneration`/`discard_sermon_note_regeneration`.
  RBAC-equivalent command registration in the `tauri::generate_handler!` list.
- **`dist/settings.js` and `dist/transcripts.js`**: both surfaces that render
  a saved/generated draft gain the "a regenerated draft is awaiting your
  decision" affordance (show new draft + prior draft, Accept/Discard), OR (if
  only one surface currently exposes a Regenerate entry point) an explicit,
  documented justification for why the other does not need it — mirroring
  the ticket's explicit warning about the earlier both-consoles caveat bug.
- Tests at every layer above, focused on: happy-path stage->confirm,
  stage->discard, consent-off regression (regenerate still gates exactly like
  generate), transport-failure-during-regenerate leaves the prior draft
  intact (explicit test, not inferred), degraded/local-fallback regenerate
  still requires confirm and still carries `ai_generated: false` +
  `degraded_notice`, AI-generated label/disclosure carried through confirm
  unchanged from the pending draft's own values.

### Non-goals

- The model/settings picker (86akbzxyc) — regenerate uses whatever
  provider/model is current.
- The sermon-note persistence layer itself (86akgqdv0, shipped) — this ticket
  adds retention on top of it.
- Per-section regenerate (86akc0tua's territory, explicitly ruled out).
- Export of a specific historical version (86akby7d8/FR-127's territory).
- A durable "pending regeneration is still awaiting your decision" banner
  that survives a Notes-panel reload/app restart. The underlying pending
  data DOES survive (proven at the repo/store layer — `LoadSermonNoteDraft`
  and `sermon_note_repo::find_by_transcript` are unaffected and a pending
  regeneration is only ever cleared by an explicit confirm/discard call), but
  `LoadSermonNoteDraft`'s wire reply is deliberately left unchanged (see
  Scope) so the front-end does not currently re-surface the banner on
  reload. Flagged as a reasonable, cheap follow-up if the product owner wants
  it, not built here, to keep this ticket's blast radius to what the stated
  acceptance criteria require.

### Constraints

- No new `dev` branch exists in this repo; branch from `origin/main`.
- One ticket, one branch (`feat/86akgqdx8-regenerate-notes-version-retention`),
  one MR against `main`.
- Test against a stub transport; never live OpenAI.
- `make ci` must pass, including the headless operator webview check.
- Shared machine: check for concurrent `cargo`/`make`/`flutter` activity
  before running the full `make ci` gate; re-check `migrations.rs`'s latest
  version number immediately before finalizing (a sibling ticket, 86akgqdw0,
  may land a migration concurrently).

### Assumptions and unknowns

- ASSUMED: "an existing saved draft" means `sermon_note_repo::find_by_transcript`
  returns `Some` for the resolved transcript id at the moment Generate is
  pressed again — this is the same signal already used elsewhere in this
  codebase (`SaveSermonNoteDraft`'s "once AI-generated, always AI-generated"
  check already calls `load_draft` for this exact purpose).
- ASSUMED: the Regenerate affordance in the UI is "press Generate again on a
  transcript that already has a draft" (the ticket's own Goal wording), not a
  separate button — so the retention/staging behaviour is keyed off draft
  presence inside the EXISTING `generate_sermon_notes`/
  `transcript_generate_notes` commands, not a parallel command surface for a
  literal new button. Validation owner: UI wiring in `dist/settings.js`/
  `dist/transcripts.js` can still label the button "Regenerate" once a draft
  exists, purely as a client-side label change with no new command needed for
  that label swap.
- UNKNOWN: whether product wants a durable cross-reload pending-regeneration
  banner (see Non-goals) — flagged as a follow-up, not blocking this ticket.

## Dependencies and approvals

- 86akgqdv0 (sermon-note persistence) — shipped, merged, this ticket builds on it.
- 86akbzxyc (model/settings picker) — open, unrelated; not blocking.
- 86akc0tua (per-section regenerate ruled out) — informs non-goals only.
- 86akgqdw0 (FR-124, sibling ticket in this batch) — may run concurrently and
  touch overlapping files (`main.rs`, `settings.js`) and/or add a migration;
  rebase risk flagged, not a hard dependency.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Migration v21->v22 adds the pending-regeneration columns additively; a v21 database opens unchanged | `cargo test -p selahcue-data` | all pass, including a new migration test opening a pre-migration fixture | test output | PASS |
| C-002 | yes | `stage_regeneration`/`confirm_regeneration`/`discard_regeneration` behave per spec (existing-row-required, single pending slot, idempotent discard, NotFound on confirm-with-nothing-pending) | `cargo test -p selahcue-data` | all pass | test output | PASS |
| C-003 | yes | `create`/`update`/`find_by_transcript`/`list_detached`/`delete_by_id`/`delete_for_transcript` are behaviourally unchanged | `cargo test -p selahcue-data` (existing `test_sermon_note_repo.rs` suite) | all pre-existing tests still pass unmodified | test output | PASS |
| C-004 | yes | New LAN commands round-trip on the wire and the existing pinned sermon-note fixture is unchanged | `cargo test -p selahcue-lan` | all pass, `sermon_note_server_messages_round_trip` byte-identical | test output | PASS |
| C-005 | yes | The three new commands require `SaveSermonNotes`; a lower-privileged role is refused | `cargo test -p selahcue-lan` (rbac tests) | all pass | test output | PASS |
| C-006 | yes | `LiveController::apply` handles all three new commands correctly (stage requires an existing draft, confirm requires a pending one, discard is idempotent) | `cargo test -p selahcue-app` | all pass | test output | PASS |
| C-007 | yes | Regenerate (`generate_sermon_notes`/`transcript_generate_notes`) with an existing draft stages instead of upserting; the prior draft is retrievable/unchanged before confirm | `cargo test -p selahcue-operator` (via `cargo check`/unit tests — operator crate is workspace-excluded, see `implementation/desktop/CLAUDE.md`) | new tests pass | test output | PASS |
| C-008 | yes | Consent-off still blocks Regenerate's network call exactly as Generate (regression test) | `cargo test -p selahcue-operator` | test passes | test output | PASS |
| C-009 | yes | A transport failure during regenerate never loses the prior draft; no pending row is created | `cargo test -p selahcue-operator` and/or `-p selahcue-app` | test passes | test output | PASS |
| C-010 | yes | A degraded (local-fallback) regenerate still requires confirm, still carries `ai_generated:false` + `degraded_notice`, and the confirmed result matches | `cargo test -p selahcue-operator` | test passes | test output | PASS |
| C-011 | yes | The regenerated draft carries the AI-generated label + fabrication disclosure exactly like first-generation, once confirmed | `cargo test -p selahcue-operator`/`-p selahcue-data` | test passes | test output | PASS |
| C-012 | yes | Both `dist/settings.js` and `dist/transcripts.js` handle the pending-regeneration state (or a documented reason one doesn't need to) | code review + `scripts/operator_headless.py` | headless checks pass; MR documents the decision | headless output + MR text | PASS |
| C-013 | yes | `make ci` passes in full, including the headless operator webview check, with the real exit code captured in the log file | `make ci` output redirected to a log file, exit code appended to that same file | exit code 0 recorded in the log | ci log file under the scratchpad or repo tmp dir | PENDING |
| C-014 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) run in isolated worktrees pinned to the reviewed commit; blocking findings remediated | reviewer reports + re-check | no outstanding blocking findings | PR comments + published report artifact | PENDING |
| C-015 | yes | Retention-model decision (single prior version; explicit-confirm-before-replace) is documented in the MR description | MR body review | present and matches what shipped | PR description | PENDING |

## Verification plan

- Focused verification: `cargo test -p selahcue-data`, `-p selahcue-lan`,
  `-p selahcue-app`, `cargo check --manifest-path
  .../selahcue-operator/Cargo.toml` + operator crate's own `#[cfg(test)]`
  unit tests, `python3 scripts/operator_headless.py`.
- Broader regression verification: `make ci` end to end, real exit code
  captured in the log file.
- Independent verifier: Cody (code review), Vera (performance), Sana
  (security), Quinn (QA) — each in an isolated `git worktree` pinned to the
  exact reviewed commit.
- Required environment: local dev machine, shared with other concurrent
  agent sessions — check `ps aux`/`ListAgents` before the full `make ci` run.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-003 (data layer)
- Hypothesis: additive nullable `pending_*` columns on `sermon_note` +
  three new repo functions satisfy the retention model without touching
  `create`/`update`'s existing behaviour.
- Change or investigation: implemented by a prior session of this same role
  (stopped by an external signal, not a failure) — migration v21->v22, the
  three new repo functions, and matching wire/RBAC/controller/backend/
  operator-command plumbing were all written before this session picked the
  ticket back up.
- Verifier executed: `cargo test -p selahcue-data`, `-p selahcue-lan`,
  `-p selahcue-app` (bare and `--features server`), `cargo check` +
  `cargo test --manifest-path .../selahcue-operator/Cargo.toml` (both run
  fresh from this session, not trusted from the handoff), `cargo clippy
  --all-targets -- -D warnings` and `cargo fmt --check` across every touched
  crate, `python3 scripts/operator_headless.py`.
- Result: selahcue-data 36+10+37 tests pass (incl. every new
  stage/confirm/discard/migration test); selahcue-lan 31 tests pass
  including the pinned `sermon_note_server_messages_round_trip` and
  `wire_fixtures_are_stable_for_cross_language_clients` fixtures unchanged,
  plus the new RBAC test; selahcue-app 15 test files pass under both default
  and `--features server` (the `RemoteOperator`/LAN-mediated path silently
  no-ops without the feature flag — confirmed by re-running with it and
  seeing `test_sermon_note_remote.rs`'s 7 tests actually execute).
  selahcue-operator: found a genuine gap — `persist_generated_draft`'s own
  stage-vs-upsert branch, the regenerate-specific consent-off regression,
  and the degraded-regenerate-requires-confirm case (C-007/C-008/C-010) had
  NO coverage anywhere in this crate (155 tests, none touching regen/stage/
  confirm/discard) even though the app/data layers covered the retention
  model itself thoroughly. Added `regenerate_with_retention_tests` (6 new
  tests: no-existing-draft saves immediately, existing-draft stages and
  leaves it untouched, a refused stage leaves no pending row, consent-off
  refuses before touching the accepted draft, a degraded regenerate over a
  never-AI draft still requires confirm and survives it unchanged, and the
  two new Tauri commands' own JSON shape round-trips through a real
  DB-backed store) — 161 tests now pass, 0 failed. Also found and fixed:
  11 `clippy::unwrap_used` violations in the new operator tests, and
  pre-existing `cargo fmt` drift across selahcue-app/selahcue-data (from
  before this session) plus the operator crate's own new code — all fixed,
  `cargo fmt --check` now clean across every touched crate.
  `scripts/operator_headless.py`: 1490 checks, 0 FAIL — independently
  re-run, matching `EXPECTED_MIN_CHECKS` and the prior session's report;
  confirmed the regenerate flow is exercised on BOTH consoles (19 REGEN-*
  checks spanning `TR` (transcripts.js) and `PP` (settings.js) prefixes),
  satisfying C-012.
  Migration count re-verified at 22 (`grep -c '^    r#"'`), origin/main
  unchanged at `4b21c39`, branch not behind — no rebase needed yet.
- New evidence: log files under `/tmp/scph-a4658-*.log` (data/lan/app/
  operator test runs, clippy, fmt, headless).
- Decision: iterate — C-001 through C-012 now have real, independently
  verified evidence; C-013 (`make ci`), C-014 (four-reviewer gate), and
  C-015 (MR description) remain.

### Iteration 2

- Target criterion: C-014 (four-reviewer gate remediation).
- Hypothesis: PR #55 opened Draft against `main`; Cody/Vera/Sana/Quinn each
  reviewed commit `65121da` in their own isolated worktree
  (`scph-worktrees/review-86akgqdx8-{cody,vera,sana,quinn}`); their findings
  can be triaged and remediated without a further architecture change.
- Change or investigation: all four verdicts received —
  **Cody: APPROVE WITH NITS** (1 Minor, 3 Nits). **Vera: CHANGES REQUESTED**
  (1 Major — F1; 2 Minor — F2/F3; 3 Nits). **Sana: APPROVE WITH NITS**
  (0 Blocker/Major; 2 Minor; 3 Nits; security verdict Pass). **Quinn: PASS
  WITH FOLLOW-UPS** (1 Low finding).
  Remediated in this iteration:
  - **Vera F1 (Major, required)**: `sermon_note_repo.rs`'s hand-reconciled
    ~60,060 B wire-cap budget covered only a SINGLE draft
    (`SaveSermonNoteDraft`/`UpdateSermonNoteDraft`), never
    `ServerMessage::SermonNoteRegenerationState`'s TWO drafts. Added a new
    test (`a_two_draft_regeneration_state_reply_is_measured_against_the_wire_
    cap_both_ways`, `test_sermon_note_remote.rs`) measuring the REAL
    serialized size via `protocol::to_json` (not arithmetic): ordinary
    Latin-script content at every field's maximum is 48,824 B (fits, 74% of
    the 64 KiB cap); ordinary 3-byte-UTF-8 content at the SAME maxima is
    71,624 B (exceeds it) — both numbers corroborate Vera's own independent
    measurement (48,860 B / 71,660 B) within rounding. Rewrote the doc
    comment on `MAX_SECTIONS_JSON_BYTES` to scope the original reconciliation
    to the request direction and document the reply-direction gap honestly.
    Confirmed this is NOT a live defect (no transport-level enforcement
    exists on the reply/write direction at all, pre-dating this ticket) and
    filed a follow-up, [17tnw2axpt1](https://app.clickup.com/t/17tnw2axpt1),
    for adding a symmetric `WebSocketConfig` to the client.
  - **Cody Minor**: `RealSermonNoteStore::discard_regeneration` (both
    `selahcue-desktop/src/main.rs` and its hand-mirrored test copy in
    `test_sermon_note_remote.rs`) turned "no `sermon_note` row at all" into
    a store-layer `Err` (via `.ok_or_else` on the post-write read-back),
    which `LiveController::apply` turns into `ControllerReply::Deny` —
    observable as a denied command rather than the trait's documented
    "never errors for nothing was pending" no-op. Fixed to return
    `RegenerationSlot::default()` in that case. Added
    `discarding_with_no_draft_ever_generated_is_a_harmless_success_over_the_
    real_wire` and mutation-verified it (reverted the fix, confirmed RED
    with exactly the predicted symptom, restored the fix, confirmed GREEN).
  - **Sana Minor 2**: this contract's own "a rollback is reverting the
    branch" claim was inaccurate — `migrations.rs::run` refuses
    `DataError::SchemaTooNew` for a `user_version` ahead of the running
    build's `target_version()`, so a reverted v21 binary cannot open a store
    a v22 binary already migrated. Corrected in this document's Risks
    section (no data loss either way, but "revert the branch" alone does
    not restore access).
  - **Quinn (Low)**: `dist/transcripts.js`'s REGEN-* headless checks proved
    the happy path/discard/confirm/degraded cases but never the
    regenerate-specific consent-off or transport-failure cases PP REGEN-4/
    PP REGEN-5 prove on `dist/settings.js` — the same "proven on one
    console, assumed on the other" shape this batch has hit as a real MAJOR
    bug before. Added TR REGEN-5/TR REGEN-6 to
    `scripts/operator_headless.py`, re-derived `EXPECTED_MIN_CHECKS` fresh
    (1490 -> 1496, confirmed by an actual standalone run), both new checks
    pass.
  - **Vera N1 (Nit, addressed anyway)**: `a_second_stage_before_confirm_
    overwrites_the_first_pending_regeneration` proved last-writer-wins but
    not boundedness (would still pass against a history-table
    implementation). Strengthened to loop 5 re-stages, asserting
    `SELECT COUNT(*) FROM sermon_note WHERE transcript_id = ?` stays at
    exactly 1 after every one.
  Deferred, with reasoning recorded rather than silently dropped:
  - **Vera F2 (Minor)**: `find_by_transcript`'s widened 12->21 columns cost
    every plain load an unnecessary ~19 KB decode/allocation of a pending
    payload it discards. Vera's own suggested fix (a lean
    `find_accepted_by_transcript` for the load path) is real but touches a
    well-tested, multiply-consumed production function under time pressure
    for a perf-only (not correctness) gain; deferred rather than rushed.
  - **Vera F3(a) (non-goal)**: no UI reclaim path for an abandoned pending
    slot once its banner is gone — Vera herself ties this to the durable
    cross-reload pending-banner follow-up already recorded in this
    contract's Non-goals section; not built here, for the same reason.
  - **Vera F3(b) / Sana Minor 1 (Minor, independently converged)**:
    `persist_generated_draft`'s load-then-branch is two separate calls, not
    one atomic operation — a narrow TOCTOU window if two Operator-tier LAN
    clients race on the same transcript (single-console double-submission
    is already blocked by both consoles' `generating` flag). Both reviewers
    rated this non-blocking and said risk-acceptance, if deferred, belongs
    to the human owner. Filed as a follow-up,
    [17tnw2axpt3](https://app.clickup.com/t/17tnw2axpt3), rather than
    attempt an under-reviewed atomicity redesign
    (a new `create_or_stage` repo-level primitive) inside review
    remediation.
  - **Cody's remaining 2 Nits** (duplicated `PendingRegenerationRecord`->
    `SermonNoteDraftView` mapping across selahcue-desktop/selahcue-app's
    test files/selahcue-operator's test module; duplicated confirm/discard/
    banner JS between `settings.js`/`transcripts.js`): both match an
    ALREADY-established, explicitly-documented convention in this codebase
    (`RealTranscriptStore`/`RealSermonNoteStore` "kept in sync by hand,
    that binary crate is excluded from the workspace and cannot be
    depended on from here"; both consoles independently implementing the
    same UI state is what C-012 itself requires). Not fixed — consistent
    with precedent, not an oversight.
  - **Sana's 3 Nits** (a `.map_err(|e| e.to_string())` that materializes a
    potentially large string even though every caller today discards it;
    one unreachable corrupt-row shape; orphaned pending regenerations after
    a reload — a documented, bounded non-goal): all explicitly rated
    low-value/acceptable by Sana herself; not fixed.
- Verifier executed: `cargo test -p selahcue-data -p selahcue-lan`,
  `-p selahcue-app` (`--features server`), `cargo test --manifest-path
  .../selahcue-operator/Cargo.toml`, `cargo clippy --all-targets
  -- -D warnings` + `cargo fmt --check` across every touched crate,
  `python3 scripts/operator_headless.py`,
  `python3 scripts/validate_goal_contract.py` — all re-run fresh AFTER
  every remediation edit above, not trusted from before the fixes.
- Result: selahcue-data + selahcue-lan 24 test-result blocks all `ok`, 0
  FAILED; selahcue-app 15 test-result blocks all `ok` (0 FAILED),
  `test_sermon_note_remote.rs` now 9 tests (was 7; +2 from this iteration);
  selahcue-operator 161 tests pass, 0 failed; clippy clean across every
  touched crate; `cargo fmt --check` clean; headless 1496 checks, 0 FAIL;
  goal-contract validator PASS (15/15 mandatory criteria present).
- New evidence: log files under `/tmp/scph-a4658-final-*.log`; follow-up
  tickets 17tnw2axpt1, 17tnw2axpt3; PR #55 review comments from all four
  reviewers.
- Decision: iterate — C-013 (a fresh, uninterrupted `make ci` run against
  the fully remediated tree) and re-checks from Vera/Cody/Sana/Quinn on
  the remediation itself remain before C-014/C-015 can be marked PASS.

## Risks and rollback

- Risks: the LAN/RBAC/SermonNoteStore footprint is larger than the ticket's
  own stated file list — mitigated by keeping every new surface strictly
  additive (no existing wire shape, permission, or repo function changes
  behaviour) so a revert is a clean subtraction. Concurrent sibling ticket
  86akgqdw0 may collide on `main.rs`/`settings.js`/migration numbering —
  mitigated by re-checking `migrations.rs` immediately before finalizing and
  rebasing before requesting review.
- Rollback or recovery: the migration is additive-only (new nullable
  columns), so applying it is always safe and never destroys pre-existing
  data. **Correction (86akgqdx8 review, Sana — Minor 2): "a rollback is
  reverting the branch" is not quite right as originally written.**
  `migrations.rs::run` refuses to open a database whose `user_version` is
  AHEAD of the running build's `target_version()` (`DataError::SchemaTooNew`)
  — so a reverted v21 binary cannot open a store a v22 binary already
  migrated; it has to stay on v22 (or later) until a v22-or-newer build is
  reinstalled. No data is lost either way (the v22 columns are simply
  unreadable to the older binary, not deleted), and this "cannot open a
  newer schema" behaviour is a pre-existing property of every one of this
  crate's 22 migrations, not something FR-129 introduces — but "revert the
  branch" alone does not restore a working v21 binary against an
  already-migrated store; reinstalling v22-or-later does.

## Pause and escalation conditions

- A rebase conflict requiring a judgement call this role is not equipped to
  make (e.g. a genuine schema collision with a concurrently-merged sibling
  migration).
- Product sign-off needed on the cross-reload pending-banner follow-up (not
  blocking; escalate only if asked to build it in-scope).

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akgqdx8-regenerate-notes-version-retention.md --completion`
- Validator result: (recorded at completion)
- Independent verification result: (recorded at completion)
- Terminal state: (recorded at completion)
- Remaining failed or blocked criteria: (recorded at completion)
- ClickUp final evidence comment: (recorded at completion)
