# Goal Contract — TASK-86akgqdv0

## Identity

- Goal ID: TASK-86akgqdv0
- Parent goal ID: NONE
- Title: Generated sermon-note drafts (`NoteDraft`) are persisted against their source
  transcript and the operator can edit them afterward, with the source transcript
  provably untouched (FR-123 "editable" half)
- Role: backend-engineer
- Status: GATE_REVIEW (four-reviewer gate ran and returned findings; every
  blocking/routed finding remediated this session; cascade-on-delete product
  sign-off was already confirmed on the ticket before this iteration; PR
  remains Draft pending the reviewers' own re-verification of the remediation)
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdv0
- Created: 2026-09-11
- Updated: 2026-09-12 (Iteration 5: second four-reviewer-gate round's findings
  remediated — LAN frame cap vs. data-layer draft cap (Vera F5/Sana N1, High),
  disclosure/ai_generated pairing + no-downgrade enforcement (Sana N2, Medium),
  provider/disclosure/model bounds (Sana N3, Low), masked `purge_expired` test
  (Cody/Sana N4, Medium/Low), `sermon_note` encryption marker (Sana N5, Low) —
  `make ci` re-verified green)
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
  at session start; RE-VERIFIED against the live ticket once the connector came
  back up, before opening the PR — the reconstructed text matched, with two
  additions the live ticket carries that the reconstruction had softened: (1) the
  cascade-on-delete decision is asked to be "confirmed with product/architecture...
  before the migration merges", handled here as an explicitly-flagged proposal
  rather than an actual confirmation, since that confirmation is outside this
  role's authority; (2) "Verification expectations" explicitly asks for a headless
  webview check on the edit UI asserting computed style, not `.hidden` — added as
  the `PP SN-*` checks in `scripts/operator_headless.py`)
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
- `scripts/operator_headless.py`: new headless-webview checks for the edit UI
  (added once the live ticket text — re-verified after ClickUp came back up —
  confirmed this was explicitly asked for, asserting computed style not
  `.hidden`).

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
| C-001 | yes | `sermon_note` table + repo (create/read-by-transcript/update) exist, migration is v21 | `cargo test -p selahcue-data --test test_sermon_note_repo` | all pass | 13/13 pass | PASS |
| C-002 | yes | Draft persists across a fresh `Database::open` on the same file (restart-survives) | `a_draft_survives_a_fresh_database_open_of_the_same_file` | pass | pass | PASS |
| C-003 | yes | Editing title/summary/section items+outline points persists and survives a re-open | `editing_title_summary_and_sections_persists_and_survives_reopen` + headless `PP SN-4`/`PP SN-5` | pass | pass | PASS |
| C-004 | yes | Source transcript stored text byte-identical before generation / after generation / after editing | `generating_persisting_and_editing_a_draft_leaves_the_stored_transcript_byte_identical` | pass, mutation-verified | RED (bug injected) then GREEN | PASS |
| C-005 | yes | Editing a draft never drops `ai_generated`/`disclosure` | `editing_a_draft_never_drops_the_ai_generated_label_or_disclosure` + headless `PP SN-3`/`PP SN-5` (computed style) | pass | pass | PASS |
| C-006 | yes | Cascade-on-delete proposal implemented + explicitly flagged as needing sign-off | code comments + `transcript_repo` tests (cascade true deletes note; false detaches note) + PR/ClickUp comment | pass + comment posted | 3 new tests pass; PR description + PR comment + ClickUp comment all posted | PASS |
| C-007 | yes | Oversized/malformed edit rejected, storage stays bounded; mutation-verified | `cargo test -p selahcue-data` bounded-memory test, manual mutation (guard removed → RED, restored → GREEN, whole file w/ siblings) | RED then GREEN observed | RED then GREEN observed | PASS |
| C-008 | yes | `make ci` passes | `make ci` | exit 0 | `MAKE_CI_EXIT_CODE=0`, "ALL GREEN" | PASS |
| C-009 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) | review round | all blocking findings resolved | Ran TWICE now. Round 1 (PR #33 comments against `4a44df4`): Sana filed one High (F1) + two Medium (F2/F3); Vera filed two Low (F1/F2) + routed one correctness defect (F3) + one behaviour note (F4); Cody approved with one Low; Quinn passed all ACs with one Low/Medium gap — all remediated in Iteration 4 (`cd92ddf`). Round 2, against that remediation (`d7d89f9`): Vera filed one NEW High (F5, LAN frame cap) and confirmed F1-F4 fixed; Sana filed one NEW High (N1, same LAN-cap class), one NEW Medium (N2, disclosure/ai_generated pairing), two NEW Low (N3 bounds, N4 masked test) and confirmed F1 fixed; Cody filed one NEW Medium (masked `purge_expired` test, independently matching Sana N4) and confirmed everything else fixed; Quinn re-verified all ACs PASS with no new finding. All Round-2 findings remediated in Iteration 5 below. The four reviewers have not yet re-verified THIS remediation. | PENDING |

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
- Change: migration v21 + `sermon_note_repo` (selahcue-data); cascade wiring in
  `transcript_repo::delete`/`purge_expired`; `generate_sermon_notes` persist-on-
  generate + `load_sermon_note_draft`/`update_sermon_note_draft` commands
  (selahcue-operator); edit surface in `dist/settings.js` + `app.css`.
- Verifier executed: `cargo test -p selahcue-data` (+ `--features encryption`),
  `cargo test`/`cargo clippy --all-targets -- -D warnings` for
  `selahcue-operator` (default and `dev-keys,openai-notes`).
- Result: PASS (C-001..C-007).
- Decision: iterate to C-008 (full `make ci`, plus the headless webview checks
  the re-verified live ticket asked for).

### Iteration 2

- Target criterion: C-008, and the headless webview check the live ClickUp
  ticket's "Verification expectations" asks for (missed in the initial
  reconstructed-prompt read; caught on re-verifying against ClickUp once the
  connector came back up).
- Hypothesis: 27 new `PP SN-*` checks in `scripts/operator_headless.py`,
  asserting `getComputedStyle(...).display` (not `.hidden`) for the Edit button,
  the edit form, and the AI label/disclosure through open-edit/save/cancel, give
  this the same behavioural cover the rest of the Providers & Privacy panel
  already has.
- Change: extended the mock Tauri host in `operator_headless.py` with
  `load_sermon_note_draft`/`update_sermon_note_draft` handlers and a
  single-slot `SN` persisted-draft mock state; added the 27 checks.
- Verifier executed: `python3 scripts/operator_headless.py`.
- Result: PASS — 1227 checks, 0 FAIL (27 new).
- Decision: run full `make ci`.

### Iteration 3

- Target criterion: C-008.
- Hypothesis: `make ci` is green once both `cargo fmt` targets (the workspace
  manifest AND the operator's own, excluded, manifest) are applied.
- Change/investigation: first `make ci` run failed at the desktop workspace's own
  `cargo fmt --check` (new `sermon_note_repo.rs`/test files unformatted); fixed,
  reran — failed at the OPERATOR's separate `cargo fmt --check` (excluded
  manifest, not covered by the first `cargo fmt`); fixed, reran clean. Separately
  caught `clippy::unwrap_used` in a new operator unit test (added after the fmt
  fixes, verified directly rather than via a fourth full `make ci` run, since
  `make ci` has no dedicated operator `cargo test` step — confirmed by reading
  the Makefile's `ci` recipe) and fixed it.
- Verifier executed: `make ci` (run 3, on the fully settled file state) plus a
  final standalone re-check of `selahcue-operator` (`fmt --check`, `clippy
  --all-targets -- -D warnings` for default and `dev-keys,openai-notes`, `cargo
  test`) and `selahcue-data` (`cargo test`), since those two crates were mid-edit
  during run 3's own execution and its coverage of them could not be trusted at
  face value.
- Result: PASS — `make ci` run 3: `MAKE_CI_EXIT_CODE=0`, "ALL GREEN". Standalone
  re-check: all green.
- Decision: complete. Committed (`81a2474`), pushed, Draft PR #33 opened against
  `main`, PR + ClickUp comments posted, ClickUp status moved to `code review`.
  Terminal state: `GATE_REVIEW` (C-009, the four-reviewer gate, is the
  remaining criterion — owned by the review pipeline, not this role, per the
  Operating Contract's review pipeline section).

### Iteration 4

- Target criterion: C-009 (four-reviewer gate remediation), re-verify C-001..C-008
  against the remediated diff.
- Hypothesis: the four review rounds already run against `4a44df4` (Sana, Cody,
  Vera, Quinn — all posted as PR #33 comments) named a closed, fixable set of
  findings; addressing every blocking/routed one without re-litigating the
  cascade-on-delete decision or the five 86ajtxzrn open questions restores a
  green `make ci` and a real (not fabricated-id) end-to-end proof of the fix.
- Findings addressed (this session recovered substantial uncommitted work
  already on disk in this worktree from carrying out most of this iteration
  before a prior session stalled; this session verified, fixed one bug found
  during verification, and closed it out):
  - **Sana F1 (High)** — the operator and desktop opened different SQLite
    files, so no real launch could ever attribute a draft to a real
    `transcript_id`. Fixed by routing sermon-note load/save/update through new
    LAN commands (`GetActiveTranscriptId`/`LoadSermonNoteDraft`/
    `SaveSermonNoteDraft`/`UpdateSermonNoteDraft`) to the desktop's
    `LiveController`, mirroring 86akcfftu's `TranscriptSink` seam exactly
    (`selahcue-app::SermonNoteStore` trait, `NullSermonNoteStore` default,
    `RealSermonNoteStore` adapter in `selahcue-desktop`). Real end-to-end proof
    added: `selahcue-app/tests/test_sermon_note_remote.rs`
    (`a_real_transcript_id_flows_from_start_transcript_through_a_saved_and_loaded_draft`),
    a real on-disk SQLite file + real `ControlServer`/`RemoteOperator` TLS
    round trip, no fabricated id anywhere (replaces the `SN_TRANSCRIPT_ID = 42`
    the headless harness alone could never disprove). RBAC/protocol fixtures
    added matching this codebase's own conventions
    (`sermon_note_draft_commands_require_the_same_permission_as_transcribe` in
    `test_rbac.rs`; `every_command_round_trips` + a new
    `sermon_note_server_messages_round_trip` in `test_protocol.rs`).
  - **Sana F2 (Medium)** — both cascade-ON tests asserted only
    `find_by_transcript(...).is_none()`, satisfied by the schema's own
    `ON DELETE SET NULL` floor alone. Fixed: both now assert
    `SELECT COUNT(*) FROM sermon_note WHERE id = ?` is `0` (and `1` before, as
    a positive control).
  - **Sana F3 (Medium)** — a cascade-OFF detached note (`transcript_id = NULL`)
    was unreachable by every public `sermon_note_repo` function and survived
    `purge_expired` forever. Fixed: `sermon_note_repo::list_detached`/
    `delete_by_id` give it a path; `transcript_repo::purge_expired` now also
    purges detached notes past their own `edited_at` retention window.
  - **Vera F3 (correctness)** — `sermon_note_repo::create`'s upsert returned a
    stale `last_insert_rowid()` on the `DO UPDATE` branch. Fixed with
    `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING id`; new test
    interleaves an unrelated insert between two `create` calls and asserts the
    second still returns the first row's real id.
  - **Vera F1 (Low)** — migration v21 carried a redundant explicit index
    alongside the `UNIQUE` constraint's own autoindex. Fixed: dropped the
    explicit `CREATE INDEX`; added
    `sermon_note_has_exactly_one_index_from_its_unique_constraint`.
  - **Vera F2 / Cody Low** — `most_recent_transcript_id` resolved via the
    unbounded `transcript_repo::list(db).first()`. Fixed: new
    `transcript_repo::most_recent_id` (`SELECT id ... ORDER BY started_at DESC,
    id DESC LIMIT 1`), with a dedicated test asserting the query plan carries
    no separate sort step.
  - **Vera F4** — confirmed intentional and now documented:
    `transcript_repo::delete` reads only the cascade flag
    (`load_cascade_setting`), never routes through `load_retention_settings`,
    so a malformed `retention_days` (which `delete` never consults) can no
    longer fail-closed a manual deletion request — `purge_expired` is
    unaffected and still fails closed on that same malformed value, since it
    genuinely needs the window.
  - **Quinn's Low** — `loadPersistedDraft()`'s UI restore path had no headless
    test simulating a real page reload. Added `window.__resetSermonNoteDraftForTest()`
    (test-only hook in `settings.js`) plus a new `PP SN-9` headless check
    sequence in `scripts/operator_headless.py`.
- Bug found and fixed during this session's own verification (not a reviewer
  finding): the first cut of `PP SN-9` was placed AFTER `SN-7`/`SN-8`, both of
  which call `generate_sermon_notes` again and so overwrite the mock backend's
  single-slot persisted draft — by the time `PP SN-9` ran, the "last saved"
  title was no longer the one it asserted, and the check was genuinely RED
  (`1232 checks, 1 FAIL`) the first time `scripts/operator_headless.py` was
  actually run this session. Fixed by moving the whole `SN-9` block to
  immediately after `SN-6` (before `SN-7`/`SN-8` mutate the persisted draft
  again) — re-run: `1232 checks, 0 FAIL`. This is exactly the class of bug
  mutation-verification and "actually run the test" discipline exist to catch;
  it was caught here by executing the suite, not by inspection.
- Verifier executed: `python3 scripts/operator_headless.py` (1232 checks, 0
  FAIL, including the fixed `PP SN-9`); `make ci` — first run failed at the
  operator's own separate `cargo fmt --check` (one line over the 100-col
  limit in `main.rs`, introduced by this iteration's own edits), fixed and
  reran; second run failed at the `PP SN-9` bug above, fixed and reran; third
  run: full `make ci`, clean checkout of the actual state committed next,
  **ALL GREEN** (`== local Rust/Flutter gate: ALL GREEN ==`; 1232/1232
  headless checks; full Rust workspace incl. feature-gated suites; Flutter
  analyze+test; zero `error`/`FAILED`/`panicked` matches anywhere in the log
  outside expected test-name substrings like `a_failed_open_...`).
- Result: PASS on C-001..C-008; C-009 PENDING — every finding from the gate's
  first pass is remediated, but the four reviewers have not yet independently
  re-verified this exact diff (not re-requested as a fresh review round in
  this session; see Final evaluation).
- Decision: commit, push, leave PR in Draft (per this task's own "do not mark
  ready yourself" instruction), post PR + ClickUp evidence comments. Terminal
  state: `GATE_REVIEW` — independent re-verification of THIS remediation by
  the four reviewers has not yet happened and is not this role's to claim.

### Iteration 5

- Target criterion: C-009 (four-reviewer gate remediation, round 2), re-verify
  C-001..C-008 against this remediation.
- Hypothesis: Round 2 of the four-reviewer gate, run against Iteration 4's
  `d7d89f9`, named a second closed, fixable set of findings — the SAME
  underlying bug class independently found by Vera (F5, High) and Sana (N1,
  High), plus Sana N2 (Medium), N3/N4/N5 (Low), and Cody's independently-found
  Medium (matching Sana N4) — and addressing all of them restores a green
  `make ci` without re-litigating the cascade-on-delete decision or the five
  86ajtxzrn open questions.
- Findings addressed:
  - **Vera F5 / Sana N1 (High) — LAN frame cap vs. data-layer draft cap.**
    Both reviewers independently reproduced the identical failure: a
    save/update above ~64.8 KB caused `request_loop`
    (`selahcue-lan/src/server.rs`) to turn tungstenite's over-cap-frame error
    into a DROPPED TCP CONNECTION, and `selahcue-operator` never re-dials — a
    single oversized sermon-note save could silently kill GO LIVE/Next/
    Blackout/Clear until the console restarts. Fixed with the two-part
    approach both reviewers suggested, choosing the NARROWER cap-reconciliation
    direction over raising the shared transport cap (reasoning below):
    1. `selahcue_lan::MAX_MESSAGE_BYTES` made `pub` and re-exported — the
       single source of truth for the frame cap.
    2. `sermon_note_repo::MAX_SECTIONS_JSON_BYTES` shrunk `200_000` ->
       `15_000`, `MAX_SCRIPTURES_JSON_BYTES` shrunk `20_000` -> `3_500` — sized
       so a REALISTIC draft at every declared maximum fits ~5.4 KB (8%) under
       the 64 KiB transport cap even under the worst-case per-field JSON
       escaping (worked example in the PR description).
    3. `RemoteOperator::would_exceed_wire_cap` (new, `selahcue-app/src/
       operator.rs`) measures the EXACT serialized `Request` envelope before
       every `SaveSermonNoteDraft`/`UpdateSermonNoteDraft` send and refuses to
       send (returns `Ok(None)`, the same fail-soft shape as a host `Denied`)
       anything that would still exceed the cap — the backstop for hostile
       content whose JSON escaping inflates far past the reconciled caps
       (verified: a payload built entirely of JSON control characters at the
       SAME declared maxima still overflows ~111 KB, so the guard — not
       merely the shrunk caps — is what keeps the connection alive for that
       case).
    Real-wire regression tests added in
    `selahcue-app/tests/test_sermon_note_remote.rs`:
    `a_draft_at_every_data_layer_maximum_with_realistic_content_persists_over_the_real_wire`
    (positive control — a realistic draft at the new maxima persists cleanly)
    and
    `a_draft_whose_escaped_wire_size_exceeds_the_frame_cap_is_refused_without_dropping_the_connection`
    (the regression proper — a hostile draft is refused with `Ok(None)`, the
    link survives, and a normal save on the SAME connection afterward still
    works). Both run over a REAL on-disk SQLite file and a REAL `ControlServer`/
    `RemoteOperator` TLS round trip.
  - **Sana N2 (Medium) — no server-side enforcement of the disclosure/
    ai_generated pairing.** `LiveController::apply`'s `SaveSermonNoteDraft`
    handler (`selahcue-app/src/controller.rs`) now enforces, before ever
    calling the store: (1) `SermonNoteDraftInput::disclosure_pairing_is_consistent`
    (new method, `selahcue-lan/src/protocol.rs`) — a non-empty disclosure must
    be present EXACTLY WHEN `ai_generated` is true, refused otherwise; (2) an
    existing draft's `ai_generated` can never be flipped from `true` to
    `false` by a later save — "once AI-generated, always AI-generated." Also
    narrowed `SaveSermonNoteDraft`'s RBAC tier from `Transcribe` to a new,
    Operator-only `Permission::SaveSermonNotes` (see the PR comment for the
    full reasoning on this judgment call). New tests in
    `selahcue-app/tests/test_sermon_note_durability.rs` (both pairing
    directions, the no-downgrade rule, and two positive controls) and
    `selahcue-lan/tests/test_rbac.rs`
    (`save_sermon_note_draft_requires_operator_not_merely_transcribe`).
  - **Sana N3 (Low) — provider/disclosure/model unbounded at the data
    layer.** Added `MAX_PROVIDER_CHARS`/`MAX_DISCLOSURE_CHARS`/
    `MAX_MODEL_CHARS` (`sermon_note_repo.rs`), enforced in a new
    `check_create_only_bounds` (these three fields are set only at `create`
    time — `DraftEdit`/`update` cannot touch them). Four new tests in
    `test_sermon_note_repo.rs` (three oversized-refused, one positive control
    at all three bounds simultaneously).
  - **Cody + Sana N4 (Medium/Low) — masked `purge_expired` cascade test,
    found independently by both reviewers.**
    `purge_expired_cascade_deletes_notes_for_every_purged_transcript`
    (`test_transcript_repo.rs`) didn't prove the explicit cascade-delete
    branch inside `purge_expired` fires — the fixture note's `created_at_ms`
    (`sample_note`'s default `1_000`) was old enough that the SEPARATE
    detached-note retention sweep (Sana F3, Iteration 4) deleted it anyway
    even with the cascade branch disabled. Fixed: the fixture note's
    `created_at_ms` is now `now - 1 day` (well inside the test's 7-day
    retention window), so only the cascade branch can produce the expected
    row count.
  - **Sana N5 (Low, carried from the original round) — no `sermon_note`
    marker in `test_encryption.rs`.** Added
    `encrypted_sermon_note_round_trips_and_leaves_no_plaintext_on_disk`,
    mirroring the existing `encrypted_transcript_...` test's pattern,
    exercising every text-bearing column (title/summary/sections/disclosure).
- Mutation-verified by hand, whole file with siblings (not `--exact`), every
  new/fixed test:
  - `would_exceed_wire_cap`'s guard removed from `save_sermon_note_draft`:
    the escaped-wire-size regression test went RED with the EXACT symptom
    Vera/Sana described (`Ws(Io(... ConnectionReset ...))`), not merely a
    changed return value.
  - Data caps reverted to their pre-fix values (`200_000`/`20_000`) with the
    guard still in place: the POSITIVE-CONTROL test
    (`a_draft_at_every_data_layer_maximum_...`) went RED — proving the cap
    reconciliation (not merely the guard) is load-bearing for the feature to
    remain USEFUL for realistic content, not merely safe.
  - `disclosure_pairing_is_consistent` check removed: both pairing-direction
    tests went RED; the no-downgrade test and positive controls stayed GREEN.
  - The no-downgrade check removed: `..._cannot_flip_an_existing_ai_generated_draft_to_false`
    went RED; its positive control
    (`..._can_be_resaved_ai_generated_when_no_draft_exists_yet`) stayed GREEN.
  - `check_create_only_bounds` call removed from `create`: all three new
    oversized-field tests went RED; the positive control stayed GREEN.
  - The explicit cascade `DELETE` inside `purge_expired`'s loop disabled
    (line-641-class mutation, matching Sana's own M6c/N4 probe): the fixed
    test went RED (`left: 1, right: 0`); all 36 sibling tests in the file
    stayed GREEN.
  All mutations reverted; `git diff` confirmed empty before moving on from
  each.
- Decision on the LAN-cap fix direction (per the PR's own request to state
  reasoning): reconciled the data-layer caps DOWN to fit under the existing
  64 KiB `MAX_MESSAGE_BYTES`, rather than raising the shared transport cap.
  `MAX_MESSAGE_BYTES` bounds EVERY command on this LAN protocol, not just
  sermon notes (it exists specifically to bound pre-auth buffering against a
  slowloris-class attack); raising it would weaken that bound for every other
  command to accommodate one feature's content size, and a hosted sermon-note
  draft realistically needs 3-10 KB (Vera's own measurement of real provider
  output), so the shrunk caps (15 KB / 3.5 KB) remain generous for genuine use
  while closing the gap. The pre-send guard is the belt-and-suspenders
  backstop for content that defeats that budget's escaping assumptions.
- Decision on RBAC narrowing (per the PR's own request to use judgment and
  document reasoning either way): narrowed `SaveSermonNoteDraft` to a new
  Operator-only permission. The pairing/no-downgrade invariants close the
  SPECIFIC label-stripping/relabeling exploits Sana proved, but they cannot
  stop a Producer-tier device from submitting an internally-consistent but
  entirely FABRICATED "AI-generated" draft (a false `ai_generated: true` with
  its own matching disclosure), or from wholesale-replacing the operator's
  already-edited draft (`create` is an upsert). The operator console's own
  `generate_sermon_notes` flow is the only legitimate caller of Save today;
  `LoadSermonNoteDraft`/`UpdateSermonNoteDraft` stay at `Transcribe` since
  Load is read-only and Update is structurally incapable of touching
  provenance. See the PR comment for the full reasoning, including the
  counter-argument considered and why Save specifically (not Load/Update)
  warranted the narrower tier.
- Verifier executed: `cargo fmt --check` (clean); `cargo clippy --all-targets
  -D warnings` for `selahcue-lan --features server`, `selahcue-data --features
  encryption`, `selahcue-app --features server`, and `selahcue-operator`
  (both default features and via its own manifest) — clean; targeted `cargo
  test` runs for every touched crate/feature combination, all green, before a
  full `make ci`: **ALL GREEN** (`== local Rust/Flutter gate: ALL GREEN ==`,
  exit 0; grepped the full log for `error`/`FAILED`/`panicked` — zero matches
  outside expected test-name substrings); `python3 scripts/operator_headless.py`
  — 1232 checks, 0 FAIL (unchanged from Iteration 4 — this round touched no
  UI-visible behaviour); `python3 scripts/check_launch_reachability.py` — OK.
- Result: PASS on C-001..C-008 (re-verified against this diff); C-009 PENDING
  — every Round-2 finding is remediated, but the four reviewers have not yet
  independently re-verified THIS diff.
- Decision: commit, push, leave PR in Draft, post a new PR remediation comment
  + ClickUp evidence comment. Terminal state: `GATE_REVIEW` — a SECOND
  independent re-verification by the four reviewers has not yet happened and
  is not this role's to claim.

## Risks and rollback

- Risks: the "most recent transcript" resolution heuristic (see Assumptions) is
  the one genuinely new architectural judgment call in this ticket — flagged
  explicitly for reviewer scrutiny. Flipping `delete_cascade_to_notes`'s default
  changes already-merged, already-reviewed behaviour from 86ajtxzrn and needs
  product sign-off before merge. Narrowing `SaveSermonNoteDraft` to a new
  Operator-only permission (Iteration 5) is this role's own judgment call, not
  product/architecture-confirmed — flagged prominently in the PR comment for
  scrutiny, since it is a real RBAC-surface change (though additive: it only
  narrows one already-untested-in-production command, and the mobile
  controller never sends it, per the cross-language fixture check).
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
- Validator result: structural OK (run before iteration 1); not re-run
  `--completion` this iteration (see note below).
- Independent verification result: the four-reviewer gate ran TWICE. Round 1
  (Sana, Vera, Cody, Quinn, against `4a44df4`) is fully remediated in
  Iteration 4. Round 2 (the same four, against `d7d89f9`) posted: Vera F5
  (High, LAN cap) + confirmation F1-F4 fixed; Sana N1 (High, same class as
  Vera F5) + N2 (Medium, pairing) + N3/N4 (Low) + confirmation F1 fixed; Cody
  a Medium (masked test, independently matching Sana N4) + confirmation
  everything else fixed; Quinn re-verified all ACs PASS with no new finding.
  Every Round-2 finding is remediated in Iteration 5 above. This session did
  not re-dispatch the four reviewers against this remediation — that
  re-verification is the reviewers' own next step, not fabricated here.
- Terminal state: **GATE_REVIEW**. C-001..C-008 PASS by this role's own
  re-verification of this diff (`make ci` ALL GREEN, mutation checks on every
  new/fixed test, two real end-to-end wire-cap tests against a real
  `ControlServer`/`RemoteOperator`). C-009 is PENDING: the four-reviewer gate
  mechanism has now run twice and every finding either round raised is
  remediated, but the reviewers have not yet independently re-verified THIS
  diff (`124cb8b13a8a4296d18e8d0548c967713c92cc99`) — that gap is what keeps this GATE_REVIEW rather than
  VERIFIED_COMPLETE, per the Operating Contract's review-pipeline section.
- Remaining failed or blocked criteria: none FAILED, none BLOCKED. C-009
  PENDING only — a third reviewer pass over a diff that has changed since
  their second pass, not a new decision or dependency.
- ClickUp final evidence comment: Iteration 4's comment id `90130320019781`
  ("Review remediation complete — PR #33 now at commit 0bc9ebe"); this
  iteration's own evidence comment is posted after this file's commit (see
  the ClickUp task for the current comment). Task status: `code review`
  (unchanged).
- PR: https://github.com/First-Pavilion/selahcue/pull/33 (Draft, base `main`) —
  Iteration 4 head `d7d89f91adfa8fb8db9c491a67bb380d9c1e45f9`; Iteration 5 head
  `124cb8b13a8a4296d18e8d0548c967713c92cc99` (this commit's parent — the code fix; this Goal Contract update
  follows as its own commit, matching every prior iteration's own split).
