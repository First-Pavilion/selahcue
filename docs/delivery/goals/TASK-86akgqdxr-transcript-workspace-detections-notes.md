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
| C-001 | yes | Opening a transcript with detections shows every detection persisted against it (reference, confidence, position) | `cargo test -p selahcue-operator` (new Rust unit tests) + `python3 scripts/operator_headless.py` (new "TR detections" checks) | Rust tests green; headless checks report every seeded detection's reference text present in the DOM | test output | PENDING |
| C-002 | yes | Opening a transcript with a saved draft shows the draft's actual content, not just a status badge | `python3 scripts/operator_headless.py` (new "TR notes" checks) | title/summary/sections/scriptures/caveats render from `transcript_get`'s `draft` field | test output | PENDING |
| C-003 | yes | No detections / no draft shows a clear empty state, not a blank area | `python3 scripts/operator_headless.py` | empty-state elements present with `getComputedStyle(...).display !== "none"` when applicable | test output | PENDING |
| C-004 | yes | Transcript, detections, and notes are reachable and editable from one screen | `python3 scripts/operator_headless.py` | a single `#surface-transcripts` detail view exposes the log, detections list, and a working save-edit round trip via `update_sermon_note_draft` | test output | PENDING |
| C-005 | yes | A transcript with more detections than `MAX_DETECTIONS` (32) renders completely without unbounded DOM growth; mutation-verified | `python3 scripts/operator_headless.py` (new bounded-rendering block) + manual mutation-verify (break the window cap, confirm RED, restore) | mounted node count stays bounded across scroll positions; positive control proves a real window, not visual hiding; documented mutation-verify note in the code comment | test output + code comment | PENDING |
| C-006 | yes | Meets this console's NFR-019/020 accessibility baseline | `python3 scripts/operator_headless.py` (new "TR: ...(NFR-019/020)" assertions) | keyboard-reachable via native controls; contrast >= 4.5 on new text | test output | PENDING |
| C-007 | yes | `make ci` passes end to end, including the headless operator webview check | `make ci` (serialized with any concurrent session) | exit 0 | terminal output | PENDING |
| C-008 | yes | WebKit smoke passes on the same surface | `python3 scripts/operator_webkit_smoke.py` (or documented equivalent if unavailable locally) | exit 0 / documented pass | terminal output | PENDING |
| C-009 | yes | `TranscriptDetailView`'s field-name contract stays pinned and every existing struct-literal call site is updated in this same change | `cargo test -p selahcue-operator the_detail_view_field_names_are_pinned` | PASS with the new field set asserted | test output | PENDING |
| C-010 | yes | No transcript/detection/note text reaches a log/diagnostic string verbatim (FR-082) for any new code path | code review + a targeted test mirroring `transcript_repo.rs`'s existing no-speech-in-diagnostics test | no planted marker text leaks | test output | PENDING |
| C-011 | yes | Four-reviewer gate (Cody, Vera, Sana, Quinn) passed, blocking findings remediated and re-checked | reviewer reports (own isolated worktrees), consolidated Artifact | all four report no blocking findings outstanding | Artifact URL on PR | PENDING |
| C-012 | yes | Draft PR opened against `main`, rebased onto `origin/main` immediately before marking ready | `git log --oneline origin/main..HEAD` / `git merge-base --is-ancestor origin/main HEAD` | PR open, branch not behind `origin/main` at ready-for-review time | PR URL | PENDING |

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

### Iteration 1

- Target criterion: C-001, C-009 (backend: detections on the wire)
- Hypothesis: forwarding `TranscriptDetail.detections`/`.corrections` onto `TranscriptDetailView`
  is a pure plumbing change (data already loaded); a failing test asserting the new field first,
  per TDD.
- Change or investigation: (recorded as implementation proceeds)
- Verifier executed:
- Result:
- New evidence:
- Decision: iterate

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
