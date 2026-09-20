# Goal Contract — TASK-86akgqdxr-transcript-workspace-detections-notes

## Identity

- Goal ID: TASK-86akgqdxr-transcript-workspace-detections-notes
- Parent goal ID: NONE
- Title: The Transcripts workspace shows a selected transcript's detected-scripture list and its saved sermon-note draft's actual content, side by side with the transcript, and the notes are editable from that same screen
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdxr
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Opening a stored transcript from the Transcripts list shows, on the SAME screen: the full
transcript (already shipped), every scripture reference detected during that service
(`detection` table, persisted by 86ajtxzrn but never surfaced anywhere), and the sermon-note
draft actually saved against it (86akgqdv0 persists+edits one; today only a `notes_generated`
boolean reaches this screen). The draft is editable in place, reusing the existing edit/save
mechanism unchanged. Detections and notes each get a clear, non-blank empty state. A transcript
with many more detections than the live console ever queues at once (`MAX_DETECTIONS = 32`)
renders completely without unbounded DOM growth.

## Baseline

Verified against the merge base of this branch (2026-09-20) — `origin/main` @ `269591e`
fast-forward-merged with `origin/feat/86akcffy0-generate-from-stored-transcript` @ `64e051d`
and `origin/feat/86akby820-scripture-verification` @ `7bd0fba` (which already contains
`fix/86akc0tua-requested-but-empty-sections`'s commits) — merge commit `5584e09` on this
branch. None of these three dependency branches has merged to `main` yet; the three FORMAL
ClickUp dependencies of 86akgqdxr (86ajtxzrn, 86akcffvt, 86akgqdv0) ARE all `complete` and
already on `origin/main`.

- `selahcue-data::transcript_repo::TranscriptDetail` (`transcript_repo.rs:99-110`) already
  carries `detections: Vec<DetectedReference>` and `corrections: Vec<SegmentCorrection>`,
  populated by `load()` (`transcript_repo.rs:317-431`) from the `detection` table (a plain
  `SELECT ... ORDER BY id`, no JOIN) and `transcript_correction` (JOINed to `transcript_segment`
  for ordering). `DetectedReference` (`selahcue-core/src/detection.rs:47-59`) is `{id: u64,
  reference: String, source_segment: u64, confidence: u8}`; `source_segment == 0` is a
  documented sentinel for "no known segment" (real segment ids start at 1).
- `selahcue-operator/src/main.rs`'s `TranscriptDetailView` (`main.rs:1883-1891`) silently drops
  BOTH `detections` and `corrections` on the way to the wire — `transcript_get`
  (`main.rs:1939-1956`) builds the view field-by-field and never reads `t.detections`/
  `t.corrections`. This is confirmed dead code on the read side, not a missing DB feature.
- `notes_generated` (`main.rs:1890`, `notes_generated_for` at `1923-1933`) is a real boolean
  (86akcffy0) but carries no draft content.
- The actual draft-content read/write plumbing already exists and is transcript-id-generic, NOT
  scoped to "the live/active transcript":
  - `Backend::load_sermon_note_draft(&self, transcript_id: i64)` (`main.rs:838-851`) and
    `Backend::update_sermon_note_draft(&self, transcript_id: i64, edit: SermonNoteEditInput)`
    (`main.rs:873-887`) both take an explicit id and dispatch through the SAME LAN-routed
    `Command::LoadSermonNoteDraft`/`UpdateSermonNoteDraft` path regardless of which transcript.
  - The Tauri command `update_sermon_note_draft(transcript_id, title, summary, sections,
    scriptures, state)` (`main.rs:5781-5824`) is already fully generic over `transcript_id` —
    it is only ever CALLED today from `dist/settings.js`'s live-session panel, but nothing in
    its own body assumes "active". **No backend change is needed to make notes editable from
    the Transcripts workspace — only new frontend wiring that calls this existing command.**
  - `sermon_note_draft_json(view: &SermonNoteDraftView) -> (serde_json::Value, Option<&'static
    str>)` (`main.rs:4802-4837`) is the single place that turns a persisted draft into the wire
    `draft` shape (`title`/`summary`/`sections`/`scriptures`/`caveats`/`scripture_verdicts`,
    each section carrying a derived `empty_requested`) — reused unchanged by both
    `load_sermon_note_draft` and `update_sermon_note_draft`'s Tauri commands. This is the exact
    vocabulary 86akc0tua/86akby820 built and the one this ticket must reuse, not reinvent.
  - `state.transcript_db` (used by `with_transcript_db`, i.e. what `transcript_get` reads
    segments/detections from) is opened via `open_existing_readonly` — **structurally read-only
    at the SQLite level** (`SQLITE_OPEN_READ_ONLY`, no `CREATE`, never migrates), a deliberate,
    Sana-enforced guarantee (86akcffvt review, Sana F1 / Cody Blocker) that this operator shell
    never writes to the transcript store directly. `transcript_repo::correct_segment` and
    `append_detection` exist in `selahcue-data` but are NOT reachable from any operator Tauri
    command today, and must not become reachable via `with_transcript_db` — any write path has
    to go through `state.backend`/LAN the same way notes already do.
- `dist/transcripts.js` (991 lines): `openTranscript(id)` (`559-596`) calls `transcript_get`;
  `renderDetailHeader` (`534-558`) sets the `notes_generated` badge. 86akcffy0 added a
  from-history Generate block (`609-991`) reusing `.pp-generate`/`.pp-gen-preview*`/
  `.pp-gen-result*` CSS from Settings, with `renderDraftReadOnly` (`731-779`) rendering a
  FRESHLY generated draft **read-only only** — its own comment (`729-730`) says explicitly:
  "no edit surface for a from-history draft — that stays the Settings panel's persisted-draft
  flow, unchanged" — i.e. this ticket is the one meant to remove that restriction.
- `dist/settings.js` already has a complete, working edit surface for a persisted draft
  (86akgqdv0): `renderDraftView`/`renderDraftEditForm`/`saveDraftEdit`/`readSectionsFromForm`
  (`859-1162`), calling `invoke("update_sermon_note_draft", {transcriptId, title, summary,
  sections, scriptures})`. It is coupled to "the active session" only through its OWN state
  population (`loadPersistedDraft`/`showGenResult`), not through `saveDraftEdit` itself — the
  save call is already transcript-id-generic. This codebase's established convention (seen in
  86akcffy0 reusing Settings' CSS in transcripts.js) is to PORT/adapt this rendering logic into
  `transcripts.js`, parameterized by whichever transcript is open, rather than extracting a
  shared JS module — `dist/` has no module system, plain `<script>` includes only.
- Live per-service detection cap: `selahcue_core::detection::MAX_DETECTIONS = 32`
  (`detection.rs:27`) — the "more detections than the live console ever queues" floor for the
  bounded-rendering AC.
- `scripts/operator_headless.py`'s stub (`window.__TAURI__.core.invoke`) models `transcript_get`
  via a `TR.detail[id]` object round-tripped through `JSON.parse(JSON.stringify(...))`
  (`operator_headless.py:860-991`) — I must add `detections`/`corrections`/`draft`/etc. to each
  fixture entry to match the real Rust field set, plus a new large-detections fixture. The
  `update_sermon_note_draft` stub (`1349-1382`) is keyed against a SINGLE global `SN.draft`
  (the live-session draft used by Settings' own tests) matched by `args.transcriptId ===
  SN.draft.transcript_id` — it has no concept of "one draft per historical transcript" today,
  so it needs a second branch (checked only when the id does not match `SN.draft`) that reads/
  writes `TR.detail[id].draft` instead, without touching the existing `SN`-keyed behaviour any
  existing Settings-panel test relies on.
- The bounded-DOM test precedent is `scripts/operator_headless.py`'s "TR bounded rendering"
  block (~3251-3280): per-key hit accessors (`window.__trRenderedRowCount()`, `window.
  __trRowFor(id)`), a positive control (absence of the tail segment right after open, eviction
  of the head after scrolling away), explicitly documented as mutation-verified against
  `WINDOW_ROWS`. `implementation/desktop/CLAUDE.md`'s "Bounded-memory tests" section is the
  house style this must follow (per-key accessor, pin the premise at compile time, positive
  control, mutation-verify with siblings running).
- NFR-019/020 assertions live inline in `operator_headless.py`'s `"TR: ..."` block
  (~3160-3280): keyboard parity via native `<button>`/`role="log" tabindex="0"` + focus-
  management checks, contrast via a locally duplicated WCAG luminance helper asserting `>= 4.5`.
  There is no separate a11y test file/runner.
- `the_detail_view_field_names_are_pinned` (`main.rs:2008-2044`) and
  `transcript_get_returns_every_segment_in_order_not_a_tail` (`main.rs:2050-2074`) both
  construct `TranscriptDetailView` via an explicit, exhaustive struct literal (not
  `..Default::default()`) — this codebase's deliberate style so a pinned-contract test lists
  every field by hand. Both call sites, plus `transcript_get` itself, must be updated in the
  SAME change whenever a field is added.

## Inputs and evidence sources

- ClickUp task 86akgqdxr (live description, re-fetched 2026-09-20) and its three complete
  dependencies 86ajtxzrn, 86akcffvt, 86akgqdv0; the not-yet-merged 86akcffy0/86akc0tua/86akby820
  this branch is built on top of.
- Repository source on this branch (merge commit `5584e09`), read directly (citations above).
- `.claude/team/OPERATING_CONTRACT.md`, repo-root `CLAUDE.md`, `implementation/desktop/CLAUDE.md`.
- A full-repository Explore pass (this session, 2026-09-20) confirming the above line references.

## Scope

### In scope

- `selahcue-operator/src/main.rs`: new `DetectedReferenceView`/`SegmentCorrectionView` wire
  structs; extend `TranscriptDetailView` with `detections`, `corrections` (read-only display —
  see non-goals), `draft: Option<Value>`, `scripture_verification_note: Option<&'static str>`,
  `ai_generated: Option<bool>`, `ai_label: Option<&'static str>`, `disclosure: Option<String>`,
  `notes_provider: Option<String>`. `transcript_get` populates them: `detections`/`corrections`
  from the already-loaded `TranscriptDetail` (zero new queries), draft fields from
  `state.backend.load_sermon_note_draft(id).await` + the existing `sermon_note_draft_json`
  helper (reused unchanged) — a second, independent read from `notes_generated_for`'s, kept
  separate deliberately so existing `notes_generated_for` tests/behaviour are untouched.
- Update the three existing `TranscriptDetailView` struct-literal call sites (the two pinned
  tests plus `transcript_get` itself) for the new fields in the same change; extend
  `the_detail_view_field_names_are_pinned` to assert the new field set.
- `dist/transcripts.js` + `dist/index.html` + `dist/app.css`: a detections panel (list:
  reference, confidence, approximate position derived from `source_segment`), a notes panel
  showing the saved draft's real content (title/summary/sections/scriptures/caveats/verdicts,
  reusing the exact `caveats`/`empty_requested`/`scripture_verdicts` vocabulary and
  `.pp-gen-preview*`/`.pp-gen-result*` CSS) with an Edit control wired to the EXISTING
  `update_sermon_note_draft` command (no backend change), and the EXISTING from-history
  Generate affordance (86akcffy0) surfaced as the empty state's call to action when no draft
  exists yet. Clear, non-blank empty states for zero detections and no draft.
  Removes 86akcffy0's own documented restriction ("no edit surface for a from-history draft")
  since this ticket is that restriction's named successor.
- Bounded rendering for the detections list: a fixed-row-height sliding window (simpler than
  the segment virtualizer's Fenwick tree, since detection rows do not need variable-height
  measurement), with its own per-key hit accessors and a mutation-verified bounded-memory test
  in `operator_headless.py`, following the "TR bounded rendering" precedent, against a fixture
  with meaningfully more than `MAX_DETECTIONS = 32` rows.
- Accessibility: keyboard-reachable detection list and notes panel/edit form (native
  interactive elements, visible focus), contrast checks consistent with the existing "TR:
  ...(NFR-019/020)" assertions.
- `scripts/operator_headless.py` stub updates: `detections`/`corrections`/`draft`/etc. added to
  every `TR.detail[...]` fixture; a new large-detections fixture; `update_sermon_note_draft`'s
  stub extended with a second, `TR.detail[id]`-keyed branch that activates only when
  `args.transcriptId` does not match the existing `SN.draft`-keyed live-session branch (zero
  behaviour change for any existing Settings-panel test); `transcript_generate_notes`'s success
  branch additionally populates `TR.detail[id].draft` so a generate-then-reopen round-trips.
  Finish re-measuring `EXPECTED_MIN_CHECKS` (currently a merge placeholder of `1297`, see
  `scripts/operator_headless.py`'s merge-resolution comment) once this ticket's own checks are
  in, per this file's own "always re-measured, never merely incremented" convention.
- A linked ClickUp follow-up ticket for full transcript-correction-layer EDITING (as opposed to
  the read-only display this ticket adds), since building the write path (new LAN
  `Command`/RBAC permission/`selahcue-app` handler/Tauri command) is explicitly named as
  deferrable scope in this ticket's own non-goals.

### Non-goals

- The transcript list/viewer itself (86akcffvt), generating notes from a stored transcript
  (86akcffy0), the notes persistence/edit MECHANISM itself (86akgqdv0) — all already shipped;
  this ticket only surfaces/reuses them from a new location.
- Building NEW write plumbing for the transcript correction layer (a new LAN command, RBAC
  permission, `selahcue-app`/`selahcue-desktop` handler). `transcript_repo::correct_segment`
  already exists in `selahcue-data` but is reachable only from a writable connection this
  operator shell structurally does not hold (Sana-enforced read-only `transcript_db`) — adding
  a write path is out of this ticket's scope per its own non-goals ("Building the transcript
  correction-layer editing UI beyond what's needed... — raise as a follow-up"). This ticket
  satisfies "the correction layer... reachable from one screen" by DISPLAYING any existing
  corrections read-only alongside their segments (the schema/read path already exist; there is
  currently no writer anywhere, so no fixture will show one, but the plumbing is proven).
- Editing detections themselves (approve/dismiss) — that action exists only on the LIVE
  in-session detection queue, not the persisted/historical one; the ticket's own scope text
  asks only for a LIST.
- The RP-12 seven-role RBAC expansion (86ajxuf81) — unaffected, uses whichever roles exist today.

### Constraints

- Never open `state.transcript_db` for a write. Any new write capability must go through
  `state.backend` (LAN-routed), matching the existing notes precedent — or must not be built at
  all this ticket (see non-goals).
- `TranscriptDetailView`'s field set stays pinned by an updated version of
  `the_detail_view_field_names_are_pinned`, per this codebase's existing convention.
- No transcript/detection/note TEXT may reach a diagnostic/log/error string verbatim (FR-082) —
  any new `eprintln!`/error path added here must carry only ids/counts, matching
  `transcript_repo.rs`'s and `notes_generated_for`'s existing convention.
- `make ci` (including the headless operator webview check) must pass; verify with a real
  WebKit render as well as Blink per this console's history of engine-specific breaks (the
  hidden-attribute-vs-computed-display trap already documented in this codebase's memory).

### Assumptions and unknowns

- ASSUMED: displaying existing `corrections` read-only (no edit UI) satisfies "the transcript's
  correction layer... reachable from one screen" for this ticket's slice, given the explicit
  non-goal against building full correction-editing UI and the absence of any writer today (no
  fixture will ever show a non-empty `corrections` array in practice, but the field/rendering
  path is real and tested with a synthetic fixture). Validation owner: ClickUp comment recording
  this call before requesting review; escalate to product/architecture if a reviewer disagrees.
- ASSUMED: reusing `update_sermon_note_draft` UNCHANGED (no new Tauri command) for editing from
  the Transcripts workspace is correct, since its own signature/body already takes an explicit
  `transcript_id` with no "must be active" check anywhere in `main.rs`, `operator.rs`, or the
  LAN `Command::UpdateSermonNoteDraft` handler. Validation owner: confirmed by reading the full
  call chain (`Backend::update_sermon_note_draft` → LAN `Command::UpdateSermonNoteDraft` →
  `selahcue-app::LiveController::apply`) before implementation; re-verify no RBAC check restricts
  it to "the active transcript" specifically.

## Dependencies and approvals

- 86ajtxzrn, 86akcffvt, 86akgqdv0 — all `complete`, merged to `origin/main`. No blocker.
- 86akcffy0 (PR #45), 86akc0tua (PR #46), 86akby820 (PR #47) — `VERIFIED_COMPLETE`, not yet
  merged to `main`; this branch is built on top of all three (merge commit `5584e09`). Owner
  decision to merge is pending; this branch will rebase onto `origin/main` again once they land.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Opening a transcript with detections shows every detection persisted against it (reference, confidence, position) | `cargo test -p selahcue-operator` (new Rust unit tests) + `python3 scripts/operator_headless.py` (new "TR detections" checks) | Rust tests green; headless checks report every seeded detection's reference text present in the DOM | `make ci` log (`transcript_view_tests::every_persisted_detection_is_forwarded_to_the_wire_view ... ok`, 149/149 in `selahcue-operator`); headless suite 1410/1410 within same run | PASS |
| C-002 | yes | Opening a transcript with a saved draft shows the draft's actual content, not just a status badge | `python3 scripts/operator_headless.py` (new "TR notes" checks) | title/summary/sections/scriptures/caveats render from `transcript_get`'s `draft` field | `make ci` log (`transcript_view_tests::a_saved_draft_forwards_its_real_content_not_just_the_generated_flag ... ok`); headless suite 1410/1410 | PASS |
| C-003 | yes | No detections / no draft shows a clear empty state, not a blank area | `python3 scripts/operator_headless.py` | empty-state elements present with `getComputedStyle(...).display !== "none"` when applicable | `make ci` log (`no_detections_forwards_an_empty_array_not_a_missing_field`, `no_saved_draft_leaves_every_draft_field_none` both ok); headless suite 1410/1410 | PASS |
| C-004 | yes | Transcript, detections, and notes are reachable and editable from one screen | `python3 scripts/operator_headless.py` | a single `#surface-transcripts` detail view exposes the log, detections list, and a working save-edit round trip via `update_sermon_note_draft` | headless suite 1410/1410 within verified `make ci` run; WebKit smoke "Transcripts: nav + list + detail exercised... no exception" | PASS |
| C-005 | yes | A transcript with more detections than `MAX_DETECTIONS` (32) renders completely without unbounded DOM growth; mutation-verified | `python3 scripts/operator_headless.py` (new bounded-rendering block) + manual mutation-verify (break the window cap, confirm RED, restore) | mounted node count stays bounded across scroll positions; positive control proves a real window, not visual hiding; documented mutation-verify note in the code comment | headless suite 1410/1410 (verified run); mutation-verify narrated in ClickUp comment 1400430000001310 (two independent mutants, siblings stay green). **Vera (PR #50, V-3) found the original 3 scroll-driven assertions were ALL routed through the `__trDetScrollToFraction` test hook, which calls `recomputeDetWindow()` directly — never exercising the real `onDetScroll` listener** (disabling only its call passed unchanged). Fixed: added 3 checks using the "TR measureObserver disconnect" block's own proven-safe idiom for this harness's `--virtual-time-budget` (dispatch a real `scroll` event; intercept `requestAnimationFrame` to capture rather than race the scheduled callback; invoke it directly). Re-mutation-verified against Vera's exact scenario: disabling only `onDetScroll`'s `recomputeDetWindow()` call now turns RED exactly the 2 new real-path assertions while the 3 original hook-driven ones stay GREEN — proving they test different things. Headless suite now 1423/0 FAIL. | PASS |
| C-006 | yes | Meets this console's NFR-019/020 accessibility baseline | `python3 scripts/operator_headless.py` (new "TR: ...(NFR-019/020)" assertions) | keyboard-reachable via native controls; contrast >= 4.5 on new text | headless suite 1410/1410 (verified run) | PASS |
| C-007 | yes | `make ci` passes end to end, including the headless operator webview check | `make ci` (serialized with any concurrent session) | exit 0 | `/tmp/make_ci_86akgqdxr.log`: `== local Rust/Flutter gate: ALL GREEN ==` / `MAKE_CI_EXIT:0` (real exit code captured in the log itself, not the wrapper's) | PASS |
| C-008 | yes | WebKit smoke passes on the same surface | `python3 scripts/operator_webkit_smoke.py` (or documented equivalent if unavailable locally) | exit 0 / documented pass | `/tmp/webkit_smoke_86akgqdxr.log`: `=== WebKit smoke: 28 checks, 0 FAIL ===` / `WEBKIT_SMOKE_EXIT:0` | PASS |
| C-009 | yes | `TranscriptDetailView`'s field-name contract stays pinned and every existing struct-literal call site is updated in this same change | `cargo test -p selahcue-operator the_detail_view_field_names_are_pinned` | PASS with the new field set asserted | `make ci` log: `transcript_view_tests::the_detail_view_field_names_are_pinned ... ok`, `the_summary_view_field_names_are_pinned ... ok` | PASS |
| C-010 | yes | No transcript/detection/note text reaches a log/diagnostic string verbatim (FR-082) for any new code path | code review + a targeted test mirroring `transcript_repo.rs`'s existing no-speech-in-diagnostics test | no planted marker text leaks | **Original evidence was WRONG, caught by Sana (PR #50 F1) and Cody independently**: `transcript_get` DOES add a new `eprintln!` (the `Backend::load_sermon_note_draft` failure path) — my claim of "no new eprintln!" was false, and `no_segment_or_detection_text_reaches_a_dataerror_diagnostic` (`selahcue-data`, over `DataError`) cannot fail if this line leaks — it guards a different crate's different error type, not the `TransportError`-derived `String` this line actually handles. Sana traced the real reachable leak: `RemoteOperator::load_sermon_note_draft` (`selahcue-app/src/operator.rs`) can return `TransportError::Protocol(format!("expected sermon_note_draft, got: {other:?}"))` on a non-conforming host reply, `Debug`-dumping the entire unexpected `ServerMessage` — including `OperatorState{view}` carrying live `transcript`/`partial_transcript`/`detections` text verbatim (confirmed by reading `ServerMessage`'s `#[derive(Debug,...)]` and `OperatorStateView`'s fields). Reachable only via a non-conforming host (version skew, host bug, or a request/response desync, since `ControlClient::command` doesn't correlate `request_id`) — Inferred, not Verified, per Sana. Fixed: both this new call site AND the identical pre-existing pattern at `main.rs:6189` (`load_sermon_note_draft`'s Tauri command, live-session Settings panel) now drop the error's contents entirely rather than interpolate it — no cheap data-free discriminant exists this far downstream (the error is already a stringified `String` by the time either site sees it), so dropping it is the smallest correct fix. `cargo test`/`clippy`/`fmt` re-verified clean after the fix (169/169, 0 warnings). **Quinn's independent re-check (QA) went further and found the same fix was incomplete**: `operator.rs` has 11 total `TransportError::Protocol(format!("...{other:?}"))` construction sites, and three more callers in `main.rs` still carried the risk unpatched — `active_transcript_id` (`main.rs:5607`) and `save_sermon_note_draft` (`main.rs:5640`), both log-only eprintln! sites matching the already-fixed pattern; and `update_sermon_note_draft`'s Tauri command (`main.rs:6265-6271`), which is WORSE — it returned the raw error as `"message": e` directly to the frontend, rendered visibly on the operator's own screen via `showGenError`/`saveDraftEdit` (`role="alert"`, confirmed by reading `transcripts.js:942`'s `r.appendChild(el("span", null, message))`), not merely logged, and directly reachable through this PR's own new Transcripts Save flow. All three traced and confirmed independently before fixing (same pattern verified in `operator.rs` for all three call sites). Fixed: the two eprintln! sites now drop the error's contents (matching the established fix); `update_sermon_note_draft` now returns a fixed, data-free message instead of the raw error. The remaining 8 systemic construction sites in `operator.rs` are NOT fixed in this PR — Quinn correctly filed the root-cause fix (patch the 11 construction sites directly, name only the expected/received message type, not a Debug dump) as a separate follow-up ticket ([17tnw2axppb](https://app.clickup.com/t/17tnw2axppb)), since it is a genuinely broader architectural change deserving its own dedicated review, not something to fold hastily into this already-large remediation round. `cargo test`/`clippy`/`fmt` re-verified clean again after this second fix (169/169, 0 warnings). **Quinn's spot-check of THAT fix found one more**: her original bug report named the `save_sermon_note_draft` call site TWICE, at two different line numbers, for two genuinely distinct call sites (`generate_sermon_notes` and `transcript_generate_notes`) — only the first was fixed, the second (`main.rs:5855-5859`, inside `transcript_generate_notes`, the Transcripts workspace's own from-history Generate flow, invoked at `transcripts.js:1412` — this ticket's own surface) was left interpolating `{e}` unpatched. Sana independently found and confirmed the identical gap while re-checking the prior fix (tracing the same chain into `operator.rs:1587`), and separately corrected the "8 remaining" count to a precisely-verified 11 total construction sites (962, 976, 1517, 1537, 1587, 1615, 1653, 1681, 1707, 1724, 1736 — 3 immediate-fix sites + 8 deferred = 11, arithmetic confirmed), flagging line 1724 (the generic fallback behind dozens of other commands) as the highest-impact site for whoever picks up the follow-up ticket. She also flagged `main.rs:5688`/`5883` (`NoteError::to_string()` into a frontend `"message"`) as Unknown — a different error type, not traced exhaustively, explicitly not a finding. Exhaustively swept every remaining call site of all four affected `Backend` methods before this fourth fix — none left. `cargo test`/`clippy`/`fmt` clean again (169/169, 0 warnings) | PASS |
| C-011 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) passed, blocking findings remediated and re-checked | reviewer reports (own isolated worktrees), consolidated Artifact | all four report no blocking findings outstanding | All four reported (comments on PR #50): **Quinn** — no blocking findings, all 7 ACs independently re-verified + 2 mutation tests of my fixes. **Vera** — `VERIFIED_COMPLETE`/PASS, no blocking findings; non-blocking V-3 ("the one I'd fix before merge") on the AC5 mutation-verify's own vacuous control — fixed (see C-005 update). **Cody** — Approve with 1 finding to fix before ship (High: `.tr-line-txt-raw` contrast) — fixed; 1 non-blocking nit on C-010's evidence — corrected. **Sana** — "Pass with one required evidence correction" (F1 Medium: the new `eprintln!` leak risk + the C-010 evidence mismatch) — both fixed. All four fixes re-verified locally (`cargo test`/`clippy`/`fmt` clean, headless suite 1423/0, mutation-verified where applicable); re-check from each reviewer against the updated PR head still outstanding — consolidated Artifact not yet published. | PENDING |
| C-012 | yes | Draft PR opened against `main`, rebased onto `origin/main` immediately before marking ready | `git log --oneline origin/main..HEAD` / `git merge-base --is-ancestor origin/main HEAD` | PR open, branch not behind `origin/main` at ready-for-review time | PR #50 (https://github.com/First-Pavilion/selahcue/pull/50), draft, against `main`. Branch rebuilt by cherry-picking this ticket's 3 unique commits onto current `origin/main` (all four prior dependencies, including 86akby820/PR #47, merged) on `rebuild-86akgqdxr`, pushed as the remote `feat/86akgqdxr-transcript-workspace-detections-notes`. `git merge-base --is-ancestor origin/main HEAD` confirms not behind (5 commits ahead, 0 behind). | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: `cargo test -p selahcue-operator` (new/changed unit tests),
  `cargo test -p selahcue-data` (unaffected, but re-run for regression), targeted
  `operator_headless.py` sections by grepping the new "TR detections"/"TR notes"/"TR bounded"
  check names.
- Broader regression verification: full `make ci` (fmt, clippy, all crate tests, headless
  Chrome, Flutter gate) — serialized with any other active session in this shared checkout.
- Independent verifier: Cody (code), Vera (performance — the new detections virtualizer), Sana
  (security — FR-082 no-speech-in-diagnostics, and confirming no new write path opened on the
  read-only `transcript_db`), Quinn (QA — acceptance criteria walkthrough).
- Required environment: this worktree, `origin/main`-based dependency branches merged in as
  documented above; Chrome/Chromium present for `operator_headless.py`; WebKit smoke per its
  own script requirements.

## Iteration ledger

### Iteration 1 — backend wire fields

- Target criterion: C-001, C-002, C-009
- Hypothesis: forwarding `TranscriptDetail.detections`/`.corrections` and the saved draft's real
  content onto `TranscriptDetailView` is additive plumbing (data already loaded / already
  reachable via the existing transcript-id-generic `Backend::load_sermon_note_draft`); a failing
  test first, per TDD.
- Change: added `DetectedReferenceView`/`SegmentCorrectionView`; extended `TranscriptDetailView`;
  extracted pure `build_transcript_detail_view()`; `transcript_get` now also awaits
  `state.backend.load_sermon_note_draft(id)`, fault-isolated independently of `notes_generated_for`.
- Verifier executed: `cargo test --manifest-path implementation/desktop/Cargo.toml -p selahcue-operator`
- Result: 149/149 passed (9 new/updated in `transcript_view_tests`); `cargo clippy --all-targets -- -D warnings` and `cargo fmt --check` clean.
- New evidence: confirmed `update_sermon_note_draft`'s full call chain (Backend → LAN
  `Command::UpdateSermonNoteDraft` → `LiveController::apply`) has no active-transcript
  restriction — no backend change needed for editing from this new location.
- Decision: iterate (frontend next)

### Iteration 2 — frontend: detections panel, saved-draft view/edit, correction overlay

- Target criterion: C-001..C-006
- Hypothesis: a fixed-row-height sliding window (simpler than the segment log's Fenwick tree) is
  sufficient for the detections list, since rows are uniform height; the saved-draft view/edit
  surface can be ported from `settings.js` parameterized by `openId` instead of "the active
  session"; a read-only correction overlay on `.tr-line` satisfies "the correction layer...
  reachable from one screen" without new write plumbing (see the linked follow-up ticket
  `17tnw2axpe3` for actual editing).
- Change: `dist/transcripts.js` (detections virtualizer + test hooks; ported
  `renderDraftHeader`/`renderDraftView`/`renderDraftEditForm`/`saveDraftEdit` with `tr-`-prefixed
  ids to avoid colliding with settings.js's `pp-`-prefixed ones; `segRow` correction overlay);
  `dist/index.html` (new panels + empty states); `dist/app.css` (new classes, deliberately no
  `display` override on the two empty-state classes, per this console's own WKWebView `[hidden]`
  trap); `scripts/operator_headless.py` (new fixtures 7/8, `update_sermon_note_draft` stub's new
  `TR.detail`-keyed branch, ~20 new "TR detections"/"TR notes"/"TR correction layer" assertions,
  the "TR generate" Edit-affordance assertion flipped to match the NEW intended behaviour).
- Verifier executed: `node --check` (syntax) so far; the full headless suite is BLOCKED — see
  below.
- Result: syntax clean; behavioural verification pending.
- New evidence: `dist/transcripts.js` is governed by ADR-0026's statically-enforced D5 invariant
  (exactly 3 named `scrollTop`-write exemptions, hard-capped — "only a revision of the ADR can
  grow this number"). The new detections virtualizer needs the identical two exemption categories
  (initial reset, test-hook simulation) applied to its own scroll container — 2 more sites, 5
  total. Escalated to Aria (software architect) rather than deciding unilaterally, per this
  ticket's non-goals around scope and this repo's role boundaries around architecture decisions.
- Decision: **blocked** pending Aria's verdict on the ADR-0026 extension (see Pause and
  escalation conditions). Continuing non-blocked prep (this contract, the follow-up ticket,
  ClickUp status) in the meantime.

### Iteration 3 — real `make ci` / WebKit smoke verification; branch-currency blocker found

- Target criterion: C-007, C-008, C-012 (plus retroactive evidence for C-001..C-006, C-009, C-010)
- Hypothesis: with Aria's ADR-0026 rev 3 landed and the shared machine's earlier disk-space
  exhaustion resolved, a full `make ci` run plus the WebKit smoke test would close C-007/C-008;
  bringing the branch up to date with `origin/main` (C-012) would be a routine rebase.
- Change: none to source; verification only. `make ci` run to completion, real exit code captured
  inside the log file itself (`echo "MAKE_CI_EXIT:$?" >> log`, not inferred from the wrapper) —
  this mattered in practice: an earlier same-day attempt on this exact ticket had silently reported
  a false "exit 0" from the wrapper while `make ci` itself had failed with `Error 101` on disk
  exhaustion (see ClickUp comment history) and a later attempt was genuinely `SIGTERM`'d by
  machine-wide CPU/memory contention from concurrent sessions' own `make ci` runs — both required
  reading the log's actual captured exit code, not the tool wrapper's, to tell apart from a real
  result.
- Verifier executed: `make ci` (full run) — `/tmp/make_ci_86akgqdxr.log`; `python3
  scripts/operator_webkit_smoke.py` — `/tmp/webkit_smoke_86akgqdxr.log`.
- Result: `make ci` exit 0 (`== local Rust/Flutter gate: ALL GREEN ==`), 149/149 `selahcue-operator`
  unit tests, headless webview suite re-confirmed 1410/1410 checks 0 FAIL within the same run, full
  Flutter suite 223/223. WebKit smoke: 28 checks, 0 FAIL, exit 0, specifically exercising the
  Transcripts surface (nav/list/detail, the WKWebView `[hidden]`-vs-computed-display trap, native
  Home/End/PageUp/PageDown/Space scroll behaviour, Shift+End selection preservation). No genuine
  failures found scanning the full 6855-line `make ci` log.
- New evidence: attempting C-012 (branch currency) surfaced that this branch was built by
  fast-forward-merging its three dependency branches rather than rebasing onto them, so a plain
  `git rebase origin/main` replays now-superseded pre-fix commits against their differently-shaped,
  already-merged equivalents and conflicts immediately (5 files) on the first replayed commit.
  Correct approach — cherry-pick only this ticket's 3 unique commits (`10f776b`, `c737dad`,
  `d317f7c`) onto fresh `origin/main` — validated on a throwaway branch `rebuild-86akgqdxr`
  (original tip preserved at `backup-d317f7c`): first two cherry-pick clean; the third conflicts
  only in `scripts/operator_headless.py`'s `EXPECTED_MIN_CHECKS` (the exact "stray second
  assignment" class this file's own convention and Aria's ADR-0026 review already name), which is
  mechanically resolvable by re-measuring the real count at HEAD. However, this ticket's own
  `transcripts.js` code reads `scripture_verdicts`/`scripture_verification_note` — vocabulary that
  exists only because of **86akby820 (PR #47)**, confirmed via `git merge-base --is-ancestor` to
  be `MERGEABLE` but NOT YET merged to `origin/main`, unlike its two sibling dependency branches
  (86akcffy0/PR #45, 86akc0tua/PR #46) which have merged. Completing the rebuild against bare
  `origin/main` now would silently degrade the scripture-verification part of this ticket's own UI
  (fields resolve to null/empty) rather than reflect real integration.
- Decision: **blocked** on PR #47 (86akby820) actually merging — this was always this ticket's own
  documented dependency (see Baseline/Dependencies sections), not a new one. Not deciding
  unilaterally to strip the scripture-verification integration to force a clean merge onto an
  incomplete base. Worktree returned to `feat/86akgqdxr-transcript-workspace-detections-notes` at
  `d317f7c`, verified clean (`git status`, `git reflog`) and untouched by the exploration.
  `rebuild-86akgqdxr` (2/3 commits already cherry-picked clean) kept as a head start for once PR #47
  lands.

### Iteration 4 — branch rebuilt onto origin/main (all 4 dependencies merged); real gap found and fixed; PR opened

- Target criterion: C-012, C-011 (dispatch)
- Hypothesis: with 86akby820 (PR #47) merged, resuming the cherry-pick plan from `rebuild-86akgqdxr`
  (2/3 commits already validated clean) would close the branch-currency blocker.
- Change: rebased `rebuild-86akgqdxr`'s 2 clean commits onto the new `origin/main`; cherry-picked
  the 3rd (`d317f7c`) — conflicted only in `scripts/operator_headless.py`'s `EXPECTED_MIN_CHECKS`
  history comment, resolved by keeping `origin/main`'s real lineage (the more complete, currently
  accurate narrative — confirmed by reading which side's fragment grammatically continues into the
  unconflicted text either side of the marker) and appending this ticket's own addition, re-measured
  empirically rather than by arithmetic. While verifying, found a genuine gap this ticket's own code
  carried: `transcripts.js`'s `readSectionsFromForm` was ported from `settings.js` before `bfedaf2`
  (86akc0tua's second remediation round, a real Cody-found bug) added a client-side filter dropping
  a caveated-empty note section from the edit-save payload — this ticket's new Transcripts edit
  surface reached the exact same `update_sermon_note_draft` call and so carried the identical bug,
  undetected until this rebuild surfaced the fix it was ported without. Fixed by porting the
  identical filter + `isStillEmpty` helper; added a fixture section and 2 new headless assertions
  (a caveated-empty section never sent; a populated section not dropped by the same filter —
  positive control), mutation-verified (disabling the filter turns exactly the new "never sent"
  assertion red, siblings including the positive control stay green).
- Verifier executed: `python3 scripts/operator_headless.py` standalone (1417, then 1419 after the
  fix, both 0 FAIL); `cargo check`/`cargo test --manifest-path
  implementation/desktop/crates/selahcue-operator/Cargo.toml --features stt` (169/169); full
  `make ci` on the rebuilt branch (`/tmp/make_ci_86akgqdxr_rebuild.log`); `python3
  scripts/operator_webkit_smoke.py` on the rebuilt branch (`/tmp/webkit_smoke_86akgqdxr_rebuild.log`).
- Result: `make ci` real exit 0 (`== local Rust/Flutter gate: ALL GREEN ==`), headless suite 1419/0
  FAIL confirmed inside that same run, Flutter 223/223. WebKit smoke 28/0 FAIL, exit 0. Pushed
  `rebuild-86akgqdxr` to `origin/feat/86akgqdxr-transcript-workspace-detections-notes` (no remote
  branch existed yet under that name — a new ref, not a force-push over existing remote history).
  Opened draft PR #50 against `main`. Confirmed not behind: `git merge-base --is-ancestor
  origin/main HEAD` passes, 5 commits ahead / 0 behind.
- New evidence: the pre-rebuild local `feat/86akgqdxr-transcript-workspace-detections-notes` branch
  and its `backup-d317f7c` safety branch are left untouched and unpushed, superseded but preserved
  locally for reference — no destructive operation was performed on either.
- Decision: iterate — dispatch the four-reviewer gate (C-011) against PR #50.

### Iteration 5 — four-reviewer gate remediation

- Target criterion: C-010, C-011 (and retroactively C-005's evidence quality)
- Hypothesis: three of four reviewers (Quinn, Vera partial, and the non-blocking half of Cody's/
  Sana's reports) would find no blocking issues; any real findings would be small, targeted fixes.
- Change: **Sana (F1, Medium)** — `transcript_get`'s new `eprintln!` (and the identical
  pre-existing pattern at `main.rs:6189`) could Debug-dump a whole `ServerMessage::OperatorState`
  (live transcript/detection text) on a non-conforming host reply; my own C-010 evidence cited the
  wrong test (`selahcue-data`'s `DataError`-typed guard, not the `TransportError`-derived `String`
  this line actually handles) — both traced and confirmed independently before fixing (read
  `ServerMessage`'s `#[derive(Debug)]`, `OperatorStateView`'s `transcript`/`partial_transcript`/
  `detections` fields, and the exact `TransportError::Protocol(format!("...{other:?}"))`
  construction in `selahcue-app/src/operator.rs`). Fixed both call sites by dropping the error's
  contents entirely (no cheap data-free discriminant exists this far downstream). **Cody (High)** —
  `.tr-line-txt-raw` measured 3.79:1/3.96:1, failing AA-normal (the same `--sc-text-muted` trap
  this file's own `app.css` already fixed once); stepped to `--sc-text-secondary`, added a
  mutation-verified NFR-020 check. **Vera (V-3)** — see C-005's updated evidence; the AC5
  mutation-verify's own vacuous control, fixed with 3 new checks using the harness's established
  `--virtual-time-budget`-safe idiom. Both Cody's and Sana's independent findings on the SAME
  underlying C-010 evidence mismatch corroborate each other.
- Verifier executed: `cargo fmt --check` / `cargo clippy --all-targets --features stt -- -D
  warnings` / `cargo test --features stt` (all against `selahcue-operator`); `python3
  scripts/operator_headless.py` standalone, both pre- and post-fix, plus 2 separate mutation-verify
  passes (contrast colour reverted; `onDetScroll`'s real call disabled) each restored after.
- Result: `cargo test` 169/169 unchanged; `clippy`/`fmt` clean; headless suite 1419 -> 1420 (Cody's
  fix) -> 1423 (Vera's fix), 0 FAIL throughout, both new blocks mutation-verified RED/GREEN as
  designed. C-010's evidence corrected to accurately describe the real leak path and its fix
  instead of citing an inapplicable test.
- New evidence: Cody's and Sana's independent reviews caught the SAME underlying C-010 evidence
  problem from two different angles (Cody: "no new eprintln! added" is factually wrong; Sana: the
  cited test cannot fail if this specific line leaks) — a useful cross-check that the four-reviewer
  gate is catching real, non-overlapping classes of issue rather than rubber-stamping.
- Decision: iterate — push the fixes, re-run `make ci` + WebKit smoke on the updated head, then
  request re-check from all four reviewers before claiming `VERIFIED_COMPLETE`.

### Iteration 6 — re-checks land; Vera's V-6 fixed; Quinn's spot-check finds the F1 fix was incomplete

- Target criterion: C-010 (again), C-011
- Hypothesis: Cody's, Sana's, and Vera's re-checks against `c3d83c8` would close C-011 with no
  further findings; Quinn's original 7/7 verdict would stand unchanged.
- Change: **Cody** re-checked at `c3d83c8` and independently re-verified all three fixes (read the
  actual `operator.rs`/`ServerMessage` chain himself for Sana's F1, mutation-verified the contrast
  fix, reproduced Vera's exact V-3 scenario), re-ran the full local gate matching claims exactly —
  no outstanding blocking findings. **Sana** re-checked F1: closed, verified independently; found
  two more pre-existing call sites reaching the same pattern (`main.rs:5607`, `5640` — see below),
  filed as a follow-up, no action needed on this ticket. **Vera** re-checked V-3 more rigorously
  than my own verification: reproduced my mutation, then ran an ADDITIONAL one I hadn't (disabling
  the listener wiring entirely, not just the callback body) to rule out the setup assertion reading
  a foreign callback — confirmed genuinely live. Found V-6 (LOW): the captured callback was invoked
  unconditionally, so a failed setup assertion would throw and abort the driver mid-script (fails
  safe via `EXPECTED_MIN_CHECKS`, but noisily — "most of the suite vanished" rather than named
  reds). Fixed with a one-line `typeof` guard; no new checks, headless suite unchanged 1423/0.
  **Quinn** spot-checked the whole remediation round unprompted (re-ran `cargo test`/headless suite
  herself, independently mutation-verified Vera's fix) and found Sana's F1 fix, while correct, was
  incomplete: `operator.rs` has 11 total `TransportError::Protocol(format!("...{other:?}"))`
  construction sites; three more callers in `main.rs` still carried the risk — two log-only
  eprintln! sites (`active_transcript_id` at 5607, `save_sermon_note_draft` at 5640) matching the
  already-fixed pattern, and `update_sermon_note_draft`'s Tauri command (6265-6271), which was
  WORSE: it returned the raw error as `"message": e` directly to the FRONTEND, rendered visibly on
  the operator's own screen via `showGenError`/`saveDraftEdit` (`role="alert"`, confirmed by reading
  `transcripts.js:942`), not merely logged — and directly reachable through this PR's own new
  Transcripts Save flow. Filed the systemic root-cause fix (patch all 11 construction sites
  directly) as a separate follow-up ([17tnw2axppb](https://app.clickup.com/t/17tnw2axppb)) rather
  than expanding this PR's scope, but flagged the 3 directly-reachable sites as this round's own
  gap. All three traced and confirmed independently (same pattern verified for each) before fixing.
- Verifier executed: `cargo fmt --check`/`clippy -D warnings`/`cargo test --features stt` against
  `selahcue-operator` after both the V-6 fix and the 3-site F1-completion fix; `python3
  scripts/operator_headless.py` standalone after each.
- Result: `cargo test` 169/169 unchanged throughout; `clippy`/`fmt` clean; headless suite unchanged
  at 1423/0 FAIL for both fixes (neither touches JS/test-assertion logic in a way that changes the
  count). One operational hazard hit and resolved while pushing the V-6 fix: it initially landed on
  a detached HEAD rather than the branch, because a review subagent (Vera's) operates in this SAME
  shared worktree and had checked out a pinned commit for her own mutation testing, silently moving
  the checked-out ref. Diagnosed via `git reflog` (confirmed `rebuild-86akgqdxr` itself was never
  touched, and the orphaned commit's parent was exactly the branch's tip), fixed with a zero-risk
  `git merge --ff-only` (no rewrite, no data loss), and re-verified local HEAD matched the pushed
  remote tip exactly before continuing.
- New evidence: this is the second time in this same remediation round that an independent
  reviewer (first Cody+Sana on the original C-010 evidence, now Quinn on the fix's completeness)
  caught a real gap the others' passes did not — reinforcing that the four-reviewer gate, run
  seriously, finds different things through different lenses rather than converging on the same
  surface-level check.
- Decision: iterate — push the F1-completion fix, re-verify, then confirm final status with all
  four reviewers before claiming `VERIFIED_COMPLETE`.

## Risks and rollback

- Risks: (1) the `update_sermon_note_draft` reuse assumption is wrong and RBAC/backend actually
  restricts it to the active transcript — mitigated by reading the full call chain before
  wiring the frontend, and a live headless test that would fail loudly if wrong. (2) The
  detections virtualizer introduces a second, subtly different bounded-rendering
  implementation that could itself hide a bug the segment virtualizer's history (ADR-0026 rev
  1/2, several WKWebView-only regressions) suggests is easy to get wrong — mitigated by keeping
  it deliberately SIMPLER (fixed row height, no Fenwick tree) since detection rows do not need
  variable-height measurement, and by mutation-verifying explicitly. (3) Merging three
  unmerged dependency branches risks carrying a defect none of their own review rounds would
  catch in combination — mitigated by re-running each dependency's own `EXPECTED_MIN_CHECKS`
  floor after the merge (already re-measured, see baseline) and by rebasing onto `origin/main`
  again once they land, re-running `make ci` at that point too.
- Rollback or recovery: this ticket's own commits are additive (new fields with `Option`/`Vec`
  defaults, new frontend panels); reverting the feature branch or its top commits leaves
  `TranscriptDetailView`/`transcripts.js` exactly as 86akcffvt/86akcffy0 left them. No migration,
  no data mutation.

## Pause and escalation conditions

- The `update_sermon_note_draft`-reuse assumption above is found to be wrong (an RBAC/backend
  restriction to "active transcript" is discovered) — escalate to architecture, since it would
  mean either a new command or a change to `Command::UpdateSermonNoteDraft`'s scoping.
- A reviewer holds that read-only correction-layer display is NOT sufficient for "reachable...
  editable" and that a full correction-write path belongs in THIS ticket, not a follow-up —
  escalate to the ticket owner rather than unilaterally expanding scope.
- Three materially different failed attempts at any single criterion without new evidence —
  return `FAILED_LIMIT` naming the smallest unblocker.

## Final evaluation

- Validator command:
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
