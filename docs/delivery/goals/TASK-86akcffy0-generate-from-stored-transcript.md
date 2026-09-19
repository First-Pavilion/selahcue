# Goal Contract — TASK-86akcffy0-generate-from-stored-transcript

## Identity

- Goal ID: TASK-86akcffy0-generate-from-stored-transcript
- Parent goal ID: NONE
- Title: From a transcript selected in the Transcripts list, the operator can generate sermon notes from the WHOLE stored transcript, not the live console's 60-segment tail
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akcffy0
- Created: 2026-09-19
- Updated: 2026-09-19
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Opening a stored transcript from the Transcripts list and pressing Generate builds the
note-generation request from that transcript's FULL stored text (read fresh from the
read-only transcript store), not from `window.scCompletedTranscript`'s bounded 60-segment
live tail — while reusing the existing consent gate, provider machinery, and
preview-and-confirm UX pattern unchanged, and while the disclosure copy shown to the
operator is honest for both the live-tail and from-history flows.

## Baseline

Verified against `origin/main` @ 269591e (2026-09-19):

- `OPERATOR_TRANSCRIPT_TAIL = 60` (`selahcue-app/src/controller.rs:302`), used at line 2348
  to trim the transcript sent to the operator every ~1s poll.
- `window.scCompletedTranscript` (`selahcue-operator/dist/app.js` `syncTranscript`,
  ~4053-4076) is the bounded tail; `dist/settings.js`'s `onGenerate`/`confirmGenerate`
  (~567-668) send it via `invoke("generate_sermon_notes", { transcript })`.
- The Tauri command `generate_sermon_notes` (`selahcue-operator/src/main.rs:4757`) resolves
  the transcript id via `state.backend.active_transcript_id()` (the LIVE session), not an
  explicit id.
- `transcript_get`/`transcript_list` (`main.rs:1910-1935`) already read the FULL stored
  transcript read-only via `with_transcript_db` + `selahcue_data::transcript_repo::load`,
  shipped in 86akcffvt (merged).
- `TranscriptDetailView::notes_generated` (`main.rs:1890`) is hardcoded `false`; its own doc
  comment says this ticket is expected to be the one that changes it. `selahcue-data` already
  has `sermon_note_repo::find_by_transcript(db, transcript_id) -> Result<Option<SermonNoteRecord>>`
  reachable from the SAME read-only connection.
- `selahcue_cloud::generate_sermon_notes` (lib fn, `selahcue-cloud/src/lib.rs:89`) is the
  shared, provider-agnostic generation entry point: it calls
  `ProvidersConfig::build_note_request` FIRST (the egress choke point — `NoteError::
  ConsentRequired` with zero network calls when consent is off or Generate wasn't pressed),
  already covered by `selahcue-cloud/tests/test_openai.rs::
  with_consent_off_generate_makes_no_network_call_and_says_consent_is_required`.
- `run_note_generation`/`run_openai_note_generation` (`main.rs` ~4635-4746) pick the concrete
  provider by feature/config and are the reuse target named in scope; `Backend::
  save_sermon_note_draft(transcript_id, draft)` (`main.rs:856`, `selahcue-app/src/
  operator.rs:659`/controller.rs:3156) already accepts an EXPLICIT id with no "must be the
  active transcript" restriction.
- `MAX_TRANSCRIPT_CHARS = 400_000` + `bounded_transcript` (`selahcue-cloud/src/
  openai.rs:211,345`) are pure `&str` functions gated behind the `openai` feature —
  unreachable from a bare/`cloud-live`-only build.
- `.pp-gen-preview-scope` copy (`dist/settings.js:612-614`) is accurate for the live-tail flow
  and stays unchanged; the ticket only requires a NEW, honest copy for the from-history flow
  this ticket adds. Pinned verbatim by "PP F-5 L-2" in `scripts/operator_headless.py`
  (`EXPECTED_MIN_CHECKS = 1297`, line 239).
- No Generate affordance exists yet in `dist/transcripts.js`/`dist/index.html`'s Transcripts
  surface (86akcffvt shipped list + read-only viewer only).

## Inputs and evidence sources

- ClickUp task 86akcffy0 (live description, re-fetched 2026-09-19) and its dependency
  86akcffvt (shipped, PR #34).
- Repository source at `origin/main` @ 269591e, read directly (file/line citations above).
- `.claude/team/OPERATING_CONTRACT.md`, `implementation/desktop/CLAUDE.md`, repo-root
  `CLAUDE.md`.

## Scope

### In scope

- New Tauri command `transcript_generate_notes(id, state)`: reads the full stored transcript
  for `id` via `with_transcript_db` + `transcript_repo::load`, joins segment texts with `"\n"`
  (matching `app.js`'s `syncTranscript`), builds the request through the UNCHANGED
  `run_note_generation` → `selahcue_cloud::generate_sermon_notes` → `ProvidersConfig::
  build_note_request` chain, and on success persists directly against `id` via
  `state.backend.save_sermon_note_draft(id, draft)` (no `active_transcript_id()` involved).
- New Tauri command `note_generation_limits()`: returns the canonical
  `MAX_TRANSCRIPT_CHARS` value so the frontend never hardcodes/duplicates it.
- `selahcue-cloud` refactor: extract `MAX_TRANSCRIPT_CHARS`/`bounded_transcript` into an
  always-compiled `transcript_bounds` module (currently trapped behind `#[cfg(feature =
  "openai")]` inside `openai.rs`), re-exported unchanged from `openai::*` so no existing call
  site or test (`test_openai.rs`) moves.
- `transcript_get`: `notes_generated` becomes the real
  `sermon_note_repo::find_by_transcript(db, id).is_some()` instead of hardcoded `false`.
- `dist/transcripts.js` + `dist/index.html`: a Generate action in the transcript detail view,
  reusing the `.pp-gen-preview*`/`.pp-gen-result*` CSS classes and the preview-then-Confirm
  UX pattern, with ITS OWN honest `.pp-gen-preview-scope` copy stating the complete stored
  transcript (and its character count) is being sent, and a visible truncation notice when the
  transcript exceeds `MAX_TRANSCRIPT_CHARS` (documented strategy: truncate to the head, same
  behaviour `bounded_transcript` already applies at send time — surfaced to the operator
  instead of happening silently).
- `scripts/operator_headless.py`: new checks for the from-history flow (preview text, honest
  scope copy, oversized-transcript truncation notice, consent-off blocks the call, Cancel/
  Confirm, source-unchanged), `EXPECTED_MIN_CHECKS` raised to the real observed count.
- Rust tests: transcript-bounds extraction (existing `test_openai.rs` still green,
  unconditional reachability), the join/request-building helper, consent-off structurally
  blocking (`build_note_request` reached, no transport symbol involved for the bare build),
  `notes_generated` becoming accurate, and the read-only "source unchanged" invariant.

### Non-goals

- The notes-generation backend/provider itself (OpenAI/local fallback) — unchanged from
  86akby7d8.
- Detected-scripture-list-in-history, transcript correction/editing — 86akgqdxr (sequenced
  after this ticket; depends on it).
- Quota/metering, timestamp-linked notes (FR-124), export formats (FR-127).
- A rich edit surface for a from-history draft (title/section editing) — the existing
  `update_sermon_note_draft` path remains reachable only via the Settings panel's persisted-
  draft flow; this ticket renders the freshly generated draft read-only in the Transcripts
  surface.
- Changing `.pp-gen-preview-scope`'s existing live-tail copy — it stays accurate as-is.

### Constraints

- No `dev` branch in this repo; branch from freshly fetched `origin/main`, PR targets `main`.
- TDD: failing test first; never call live OpenAI (stub transport / headless JS stub only).
- `make ci` must pass in full (real exit code), including the headless operator webview gate.
- Shared checkout: serialize `make ci` with any other active agent session.

### Assumptions and unknowns

- ASSUMED: flipping `notes_generated` to a real value (via `sermon_note_repo::
  find_by_transcript`) is in-scope even though not literally listed in the ticket's checkbox
  ACs — justified by `TranscriptDetailView`'s own doc comment ("a future ticket only has to
  change this ONE value") naming this exact ticket. Low risk (one additional read-only query,
  already-tested repo function). Flagged explicitly in the PR description for reviewer
  sign-off; revert-only-this-hunk is trivial if a reviewer disagrees.
- ASSUMED: "documented, visible strategy" for the 400k clamp = truncate-to-head with a visible
  pre-send notice (reusing `bounded_transcript`'s existing head-keep behaviour), not chunked
  generation — chunking would change `NoteRequest`'s one-shot shape and the model's structured-
  output contract, which is out of this ticket's "reuse the OpenAI backend unchanged" scope.

## Dependencies and approvals

- Depends on 86akcffvt (Transcripts surface) — shipped, merged (PR #34, commit 51514a9+).
- Four-reviewer gate (Cody, Vera, Sana, Quinn) before `VERIFIED_COMPLETE`.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `transcript_generate_notes` builds its request from the transcript's full stored text, not a 60-segment tail | `cargo test -p selahcue-operator --no-fail-fast` (`the_full_text_includes_segments_far_past_the_live_tail_bound`) + headless "TR F-5 (AC1)" | PASS | `/tmp/headless_86akcffy0.log`; 128/141 cargo tests pass (bare/dev-keys,openai-notes) | PASS |
| C-002 | yes | `selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS`/`bounded_transcript` reachable without the `openai` feature; `openai::*` re-export unchanged | `cargo test -p selahcue-cloud --no-fail-fast` (bare) and `cargo test -p selahcue-cloud --features openai --no-fail-fast` | both pass; `test_openai.rs` unmodified and green | cargo test output (38 passed, `test_openai.rs` incl. `with_consent_off_generate_makes_no_network_call...` and `an_oversized_transcript_is_bounded_before_it_is_sent`) | PASS |
| C-003 | yes | A stored transcript at/near the 400,000-char clamp gets a visible, documented notice (not silent truncation) | `python3 scripts/operator_headless.py` "TR generate oversize" checks (4) | PASS, and mutation-verified RED when the clamp paragraph is disabled | `/tmp/headless_86akcffy0.log`, `/tmp/headless_mutant3.log` | PASS |
| C-004 | yes | The from-history preview's `.pp-gen-preview-scope` copy states the complete transcript + its size; the live-tail copy is unchanged | `scripts/operator_headless.py` "PP F-5 L-2" (unchanged) + new "TR F-5 L-2" check | both PASS; mutation-verified RED on a 1-word change to the new copy | `/tmp/headless_86akcffy0.log`, `/tmp/headless_mutant1.log` | PASS |
| C-005 | yes | Consent off blocks the network call for the from-history path exactly as it does live-tail | `scripts/operator_headless.py` "TR generate consent" checks (live UI, shared `ProvidersConfig`) + `cargo test -p selahcue-operator` (`consent_off_refuses_the_from_history_text_before_any_provider_is_touched`) + existing `selahcue-cloud` crate test unaffected | all PASS; mutation-verified RED when the frontend is made to ignore a refused result | `/tmp/headless_86akcffy0.log`, `/tmp/headless_mutant2.log`, cargo test output | PASS |
| C-006 | yes | The source transcript is byte-identical before and after generation | `cargo test -p selahcue-operator` (`source_transcript_is_unchanged_by_generation`) + command-level before/after equality check in `transcript_generate_notes` itself | PASS | cargo test output (141 passed) | PASS |
| C-007 | yes | `make ci` passes end to end, including the headless operator webview check | `make ci` | exit 0, "ALL GREEN" | `/tmp/make_ci_86akcffy0.log` ("== local Rust/Flutter gate: ALL GREEN ==", incl. "1330 checks, 0 FAIL" and "Flutter: All tests passed!"); GitHub Actions PR #45 run 35472932995 — every job pass (rust/operator shell/release-features on macOS+Ubuntu+Windows, launch-smoke, dependency audit, supply chain) | PASS |
| C-008 | yes | Four-reviewer gate (Cody/Vera/Sana/Quinn) completed, blocking findings remediated | review artifact + PR comments | no open blocking findings | https://claude.ai/artifact/CCqU44fqZeG21Mw6WfweQq (posted on PR #45); focused re-checks requested from Cody/Sana/Vera on commit f992075 | PENDING |

## Verification plan

- Focused verification: `cargo test -p selahcue-operator --no-fail-fast`, `cargo test -p
  selahcue-cloud --no-fail-fast` (bare + `--features openai`), `python3 scripts/
  operator_headless.py`.
- Broader regression verification: `make ci` (full local Rust/Flutter gate).
- Independent verifier: four-reviewer gate (Cody, Vera, Sana, Quinn) per the operating
  contract's review pipeline.
- Required environment: macOS dev box with Chrome available for the headless gate; no live
  OpenAI credentials used or required.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002 (Rust foundation: transcript_bounds extraction + new command)
- Hypothesis: extracting the pure clamp helpers into an always-compiled `transcript_bounds`
  module and adding `transcript_generate_notes`/`note_generation_limits`, reusing
  `run_note_generation` unchanged, satisfies the request-building + clamp-reachability criteria
  without touching provider behaviour.
- Change or investigation: `selahcue-cloud/src/transcript_bounds.rs` (new); `openai.rs` re-exports
  it; `selahcue-operator/src/main.rs` new command block + 9 unit tests; `transcript_get` flips
  `notes_generated` to a real `sermon_note_repo::find_by_transcript` read.
- Verifier executed: `cargo test -p selahcue-cloud` (bare + `--features openai`), `cargo test -p
  selahcue-operator` (bare, `dev-keys,openai-notes`), `cargo clippy` both crates/feature combos,
  `cargo fmt --check`.
- Result: 38/9 (bare) selahcue-cloud tests pass; 128 (bare) / 141 (dev-keys,openai-notes)
  selahcue-operator tests pass; clippy clean under `-D warnings` in every combo checked; fmt clean.
- New evidence: `test_openai.rs`'s `with_consent_off_generate_makes_no_network_call...` and
  `an_oversized_transcript_is_bounded_before_it_is_sent` unaffected by the extraction.
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-004, C-005, C-006 (frontend: Transcripts-surface Generate flow,
  disclosure copy, clamp notice, consent regression, headless coverage)
- Hypothesis: adding a Generate action to `transcripts.js` that reuses the `.pp-gen-preview*`/
  `.pp-gen-result*` CSS classes and preview-then-Confirm pattern, with its own honest scope copy
  and a live-computed clamp notice (`note_generation_limits`), satisfies AC2-AC5 while leaving the
  live-tail flow's own copy untouched.
- Change or investigation: `dist/transcripts.js` (Generate UI + logic), `dist/index.html` (markup),
  `dist/app.css` (`.tr-gen` + scoped `[hidden]` fix), `scripts/operator_headless.py` (new
  `transcript_generate_notes`/`note_generation_limits` stub handlers, a dedicated 454,499-char
  oversize fixture, and 30 new "TR generate"/"TR F-5" checks).
- Verifier executed: `python3 scripts/operator_headless.py`, three targeted mutation tests (pinned
  disclosure copy, consent-bypass in `showGenResult`, clamp-notice suppression).
- Result: 1330 checks, 0 FAIL on the real change; each of the 3 mutants turned the relevant
  check(s) RED, then was reverted and reconfirmed green. `EXPECTED_MIN_CHECKS` raised 1297 -> 1330
  (the real observed count, per this file's own "never lower it, never let it drift" convention).
- New evidence: `/tmp/headless_86akcffy0.log` (clean run), `/tmp/headless_mutant1.log` (copy
  mutation, 1 FAIL), `/tmp/headless_mutant2.log` (consent-bypass mutation, 2 FAIL),
  `/tmp/headless_mutant3.log` (clamp-notice mutation, 2 FAIL + early abort).
- Decision: iterate (C-007 `make ci` launched; C-008 four-reviewer gate not yet requested)

### Iteration 3

- Target criterion: C-008 (four-reviewer gate) — dispatched Cody, Vera, Sana, Quinn against PR
  #45 @ b5b5648 (with an isolation warning relayed mid-run: each reviewer told to pin to that
  commit and use its own `git worktree add`/`git archive` copy for any hands-on testing, per a
  cross-session collision the coordinator flagged from a parallel ticket).
- Hypothesis: the implementation as shipped in iterations 1-2 would clear all four reviews with
  at most Low/Nit findings.
- Result: PARTIALLY WRONG. Quinn: PASS, no blocking findings (independently re-ran all evidence
  in an isolated `git archive` copy). Vera: PASS WITH ONE FIX REQUESTED (PERF-1, Medium — the
  preview rendered the full transcript into one un-virtualized DOM node, measured ~0.10ms/KB,
  contradicting a comment this PR itself edited). Cody: NOT YET MERGEABLE (High — the 400k clamp
  was never applied on the path to a hosted `CloudNoteProvider`, only the OpenAI dev-key
  transport's own `build_body`; Medium — no computed-display regression test for the new
  `.tr-gen[hidden]` CSS fix). Sana: NOT YET MERGEABLE (High F1 — an in-progress, still-recording
  transcript was eligible for Generate, defeating the "stored transcript is static" premise the
  whole flow's honesty and unchanged-invariant claims depend on; Medium F2 — silent overwrite of
  an existing draft; Medium F3 — no stale-selection guard in `confirmGenerate`; Medium F4 — a
  query error in the new `notes_generated` read could break the whole `transcript_get` command
  on a pre-migration store).
- New evidence: reviews posted on PR #45 (Cody, Sana, Vera, Quinn comments); relayed in full by
  the coordinator/session messages.
- Decision: iterate — remediate all High/Medium findings before re-requesting.

### Iteration 4

- Target criterion: C-008, remediating iteration 3's High/Medium findings.
- Change or investigation: `selahcue-cloud`: `clamp_transcript_in_place` (new) applied inside
  `generate_sermon_notes` itself — the one choke point every provider passes through — plus a
  `MockTransport::requests_handle` addition so a test can inspect what a `SelahCueCloudClient`
  actually sent after taking ownership of the transport, and a new
  `the_hosted_client_never_sends_an_unclamped_transcript` test. `main.rs`:
  `transcript_is_eligible_for_generate`/refuse-if-not-ended (Sana F1), `notes_generated_for`
  fault isolation (Sana F4). `transcripts.js`: disabled-button + explanation for an in-progress
  transcript with `onGenerate` defense-in-depth (F1), an overwrite warning in the preview (F2),
  an `openId !== id` guard in `confirmGenerate`'s callbacks (F3), unicode-scalar-aware
  length/prefix helpers plus a preview bounded to the clamp with corrected wording (Vera PERF-1 +
  Sana F5), and a re-checked guard after the async limit lookup (Vera PERF-2).
  `scripts/operator_headless.py`: a deferred-response stub mode for F3, 17 new checks total,
  `EXPECTED_MIN_CHECKS` 1330 -> 1347.
- Verifier executed: `cargo test`/`clippy`/`fmt` on `selahcue-cloud` (bare + `--features openai`)
  and `selahcue-operator` (bare + `--features dev-keys,openai-notes`); `python3
  scripts/operator_headless.py`; five targeted mutation tests (shared clamp removed, F1 disabled
  write removed, F3 guards removed, PERF-1 bounding removed — each independently confirmed RED
  then restored GREEN).
- Result: all green. selahcue-cloud 9 (bare) / 41 (openai, incl. the 3 new tests) pass;
  selahcue-operator 132 (bare) / 145 (dev-keys,openai-notes) pass, incl. 6 new unit tests;
  clippy clean under `-D warnings` in every combination checked; fmt clean; headless suite 1347
  checks, 0 FAIL, each new/changed check mutation-verified. Pushed as commit f992075; GitHub
  Actions re-triggered; a fresh full local `make ci` launched to confirm end to end.
- New evidence: `/tmp/headless_final_remediation.log` (1347/0 FAIL); `/tmp/headless_mutantF1.log`
  (4 FAIL), `/tmp/headless_mutantF3.log` (2 FAIL), `/tmp/headless_mutantPERF1.log` (1 FAIL); the
  `lib.rs`/`clamp_transcript_in_place`-removed mutant (`test_fallback.rs` FAILED); PR comment
  https://github.com/First-Pavilion/selahcue/pull/45#issuecomment-5745973208 summarising the
  remediation for re-review.
- Decision: iterate — confirm `make ci` (C-007) and GitHub Actions are green on the remediation
  commit, then close out C-008 once reviewers confirm or a reasonable window has passed with no
  objection to the posted remediation.

## Risks and rollback

- Risks: a 400k+ character transcript round-tripped through Tauri IPC/JSON could be slow or
  memory-heavy in the preview render; mitigated by keeping the preview text render bounded the
  same way `transcripts.js` already virtualizes the read-only log (existing bounded-window
  rendering is untouched — the generate preview shows the request text in a scrollable box,
  not a virtualized log, matching `settings.js`'s existing precedent for the live-tail flow at
  a smaller scale — flagged to Vera for a real-size perf check).
- Rollback: single ticket, single branch, single PR — revert the merge commit if a
  post-merge regression appears.

## Pause and escalation conditions

- A reviewer finds the `notes_generated` accuracy fix (assumed in-scope) objectionable —
  escalate to product/delivery rather than force it through.
- `make ci`'s headless gate requires Chrome and none is available on the runner — escalate per
  the script's own documented `SELAHCUE_HEADLESS_REQUIRE` behaviour, do not silently skip.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akcffy0-generate-from-stored-transcript.md --completion`
- Validator result: (recorded before VERIFIED_COMPLETE claim)
- Independent verification result: (recorded after four-reviewer gate)
- Terminal state: (recorded at handoff)
- Remaining failed or blocked criteria: (recorded at handoff)
- ClickUp final evidence comment: (link, recorded at handoff)
