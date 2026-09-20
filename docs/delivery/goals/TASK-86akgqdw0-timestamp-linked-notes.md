# Goal Contract — TASK-86akgqdw0-timestamp-linked-notes

## Identity

- Goal ID: TASK-86akgqdw0-timestamp-linked-notes
- Parent goal ID: NONE
- Title: Timestamp-linked sermon-note items + exportable chapter/YouTube-chapter markers (FR-124)
- Role: backend-engineer (+ frontend-engineer scope, no separate FE agent invoked this run)
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akgqdw0
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

A note item (a chapter marker, and where a confident match exists, a
top-level outline point) carries a real transcript timestamp; clicking it
jumps to/highlights that point in the Transcripts viewer; a "copy chapter
markers" action produces well-formed `HH:MM:SS Label` lines; a malformed or
out-of-range timestamp cannot crash the console or produce a nonsensical
jump target.

## Baseline

Verified against `origin/main` @ `4b21c399d07f3010c6dad141e50c11cd4fdb1a48`
(PRs #44-#50 merged):

- `selahcue-core/src/providers.rs`: `NoteDraft` carries `caveats:
  Vec<DraftCaveat>` and `scripture_verdicts: Vec<ScriptureVerdict>`
  (86akby820/86akc0tua/86akgqdwc). `IncludeInNotes.chapter_markers` exists
  (default on); `selahcue_cloud::openai::FLAT_SECTIONS` produces a flat
  `NoteSection` headed `"Chapter markers"` — free text only. `grep -rniE
  "timestamp|start_ms" crates/selahcue-core/src/providers.rs` returns
  nothing: no field connects a note item to a transcript timestamp anywhere.
  `OUTLINE_HEADING = "Main points"` is defined in
  `selahcue_cloud::openai`, not core.
- `selahcue-core::transcript::TranscriptSegment` (`id`, `start_ms`,
  `end_ms`, `text`) already exists; `selahcue-data::transcript_repo::load`
  reads a **persisted, uncapped** transcript's segments back as this exact
  type, in original order (86ajtxzrn, shipped, status `complete`).
- `selahcue-operator/src/main.rs`: `generate_sermon_notes` (live-tail) is
  handed a pre-flattened `String` by the frontend — the operator process
  holds NO live `TranscriptLog`/segment structure at all (`grep -n
  "TranscriptLog" main.rs` returns nothing). `transcript_generate_notes`
  (86akcffy0, from-history) DOES load the full `TranscriptDetail` (segments
  included) server-side before flattening it to send. Both funnel through
  `run_note_generation` -> `selahcue_cloud::generate_sermon_notes`.
  `sermon_note_draft_json` re-runs `verify_scriptures` fresh on every
  persisted-draft reload/edit-save (never persists verdicts) — the pattern
  this ticket's timestamps will mirror. `draft_json` is the one JSON-shape
  function both the live and reload paths funnel through.
- `selahcue-operator/dist/transcripts.js` (86akcffvt/86akgqdxr, shipped):
  bounded sliding-window virtualizer over the transcript log
  (`WINDOW_ROWS=150`, Fenwick-tree offsets, `segs` holds the FULL segment
  array client-side already). **ADR-0026 (rev 3) D5 is a hard, statically-
  enforced, mutation-tested constraint**: `transcripts.js` may contain no
  `.scrollTop` assignment except two named classes (`init`, `test-hook`);
  "there is no third class... only a revision of this ADR can grow either
  number." A virtualized "jump to an arbitrary, possibly-unmounted index"
  feature structurally requires a `scrollTop` write, so this ticket cannot
  ship the jump behaviour without a Revision 4 to that ADR (new
  `D5-exempt(jump)` class) and a matching update to
  `scripts/operator_headless.py`'s per-class `D5_EXPECTED_EXEMPT_COUNTS`.
  `detPositionLabel`/`detRow` already resolve a detection's
  `source_segment` id to a segment's `start_ms` label (read-only, no jump) —
  the closest existing precedent, reused for lookup style, not copied for
  the (absent) interaction.
- `dist/settings.js` renders the SAME draft JSON shape (live-tail generate
  + reload via `load_sermon_note_draft`/`update_sermon_note_draft`, which
  also calls `sermon_note_draft_json`) but has no transcript-log virtualizer
  on that surface at all — a caveat/field added to one console and not the
  other is a real, twice-bitten bug class on this workstream (PR #48 Cody
  MAJOR).
- No ticket in this workspace owns FR-124 (confirmed via the ticket's own
  description and cross-references to 86akby7d8/86akby820, both of which
  explicitly exclude it).

## Inputs and evidence sources

- ClickUp task 86akgqdw0 (description; live-fetched, no comments at start).
- `implementation/desktop/crates/selahcue-core/src/{providers,transcript}.rs`
  + `tests/`.
- `implementation/desktop/crates/selahcue-cloud/src/{openai,local,contract}.rs`
  + `tests/test_openai.rs`.
- `implementation/desktop/crates/selahcue-data/src/transcript_repo.rs`.
- `implementation/desktop/crates/selahcue-operator/src/main.rs` +
  `dist/{transcripts.js,settings.js,app.css}`.
- `docs/architecture/adr/ADR-0026-operator-virtualized-list-scroll-model.md`
  + `scripts/operator_headless.py`'s D5 check.
- Prior Goal Contracts (86akgqdwc, 86akcffy0, 86akgqdxr) for process/format
  precedent, including the precedent that a ticket's own implementer writes
  a numbered ADR-0026 revision inline (rev 3 was written this way for
  86akgqdxr) rather than through a separate architect dispatch.

## Scope

### In scope

- **Linking strategy: post-hoc matched, not model-estimated.** Decided and
  documented here and in the MR: `NoteRequest::transcript` is a flattened
  `String` by construction (FR-132's own choke point) — the model is never
  shown segment boundaries, so "ask the model to estimate a timestamp"
  would require a new prompt-injection surface (per-segment time markup)
  and then trusting a generative model to preserve an exact number through
  a summarization pass, directly against this codebase's established
  posture toward model output (`verify_scriptures` already checks
  scripture the same independent way, never trusting the provider's own
  claim). Post-hoc word-overlap matching against the transcript's real,
  already-available segments needs no prompt change, costs no extra
  tokens, and reuses the exact "compute independently, join by value"
  shape `ScriptureVerdict` already established.
- `selahcue-core/src/providers.rs`: `CHAPTER_MARKERS_HEADING` and
  `OUTLINE_HEADING` promoted to core (single source of truth;
  `selahcue_cloud::openai` re-exports/reads them instead of its own
  literals); new `NoteTimestamp { heading, text, offset_ms }` type, matched
  to its item by VALUE (mirrors `ScriptureVerdict`); new `NoteDraft.
  timestamps: Vec<NoteTimestamp>` field (never persisted — recomputed
  fresh on every read, exactly like `scripture_verdicts`, so this rides on
  FR-123's existing persisted shape with zero schema change); new pure,
  bounded, adversarial-input-safe `link_timestamps(sections, segments)`
  function: chapter markers ALWAYS get an offset (a real textual match, or
  — only when zero eligible segment shares any significant word — an
  interpolated position between real segment timestamps, still "derived
  from the transcript", never invented text); outline points get a
  timestamp ONLY on a genuine textual match (best-effort, per the ticket's
  own "ideally"/"where feasible" wording); matching walks forward with a
  monotonic cursor per section (markers/points occur in sermon order);
  independent defensive bounds (`MAX_LINK_SEGMENTS`, `MAX_PLAUSIBLE_
  OFFSET_MS`, `MAX_LINK_ITEMS`) so a corrupt/huge stored segment (e.g. a
  negative-to-`u64` wraparound) can never win a match or reach the wire.
- `selahcue-cloud/src/{openai,local,contract}.rs`: add the new
  `timestamps: Vec::new()` field to every existing `NoteDraft` construction
  (linking never happens at this layer — it needs the full segment
  structure, which only `selahcue-operator` holds).
- `selahcue-operator/src/main.rs`: `draft_json` gains a `"timestamps"` wire
  field; a shared `link_note_timestamps(&mut NoteDraft, &[TranscriptSegment])`
  helper is the ONE call site both `generate_sermon_notes` (called with
  `&[]` — live-tail has no segment structure, an explicit, documented
  scope boundary, not an oversight) and `transcript_generate_notes` (called
  with the already-loaded, already-integrity-checked stored segments) route
  through — "shared pipeline, not duplicated" per the ticket's own
  instruction. `sermon_note_draft_json` (the reload/edit-save path) gains a
  `segments` parameter and recomputes timestamps fresh on every call,
  exactly like its existing `scripture_verdicts` recomputation; its three
  real call sites are updated (one already holds `TranscriptDetail`; two
  gain a best-effort, never-fatal segment read via a new
  `transcript_segments_for` helper).
- `dist/transcripts.js`: render a clickable timestamp badge on any
  item/point with a matching `NoteTimestamp`; a "Copy chapter markers"
  button producing `HH:MM:SS Label` lines (always three components,
  zero-padded — the ticket's own Acceptance-Criteria wording, even though
  its narrative example reads as `MM:SS`; documented as a deliberate,
  literal reading); a `jumpToOffsetMs` function that locates the nearest
  segment (binary search; malformed/negative/NaN/out-of-range input
  degrades to "no jump", never a crash or an out-of-bounds index) and
  scrolls the log to it.
- **ADR-0026 Revision 4** (`docs/architecture/adr/ADR-0026-operator-
  virtualized-list-scroll-model.md`): a new `D5-exempt(jump)` class for
  exactly this one, deliberate, click-triggered, one-shot navigation write
  — never reachable from `scroll`/`wheel`/`keydown`/an animation frame, so
  it does not reintroduce the C1 hazard the ADR exists to prevent; the
  reasoning leans on the ADR's own already-accepted "the user asked to go
  somewhere else" trade-off for a big jump with no surviving anchor.
  `scripts/operator_headless.py`'s `D5_EXPECTED_EXEMPT_COUNTS` gains
  `"jump": 1` and its surrounding comments/messages are updated to name all
  three classes. Flagged prominently for Cody's/Sana's extra scrutiny in
  the MR and ClickUp (this is the most architecturally sensitive part of
  this ticket).
- `dist/settings.js`: same `timestamps` rendering (data parity with
  `transcripts.js`, per this workstream's own twice-bitten lesson) as a
  plain, non-interactive `HH:MM:SS` label plus the same "Copy chapter
  markers" action (clipboard copy needs no virtualizer) — explicitly NO
  jump-to-transcript affordance on this surface (no transcript log
  virtualizer exists there to jump within); this asymmetry is documented,
  not silently partial.
- `scripts/operator_headless.py`: new behavioural check(s) for the
  clickable timestamp affordance (asserted on computed style, per the
  ticket's own verification expectation) and the adversarial malformed-
  timestamp fixture; `EXPECTED_MIN_CHECKS` raised to the real observed
  count.
- Fixture-based Rust tests only (per this workstream's established
  pattern) — a new `selahcue-core/tests/test_note_timestamps.rs`, plus
  updates to every existing `NoteDraft`-literal test site across
  `selahcue-operator`/`selahcue-cloud` needed for the new required field.

### Non-goals

- The transcript viewer itself (86akcffvt/86akgqdxr) — extended, not
  rebuilt.
- Other export formats (FR-127/86akgqdwn) — untouched; only the
  chapter-markers text block this ticket specifically asks for.
- Persisting the edited draft (FR-123) — rides on its existing shape;
  timestamps are never persisted, matching `scripture_verdicts`.
- Timestamp linking for the live-tail (`generate_sermon_notes`) generation
  path at GENERATE time — the operator holds no segment structure there;
  a draft generated live still gets timestamps once/if it is later
  reloaded from the (by-then-persisted) transcript, via
  `sermon_note_draft_json`'s fresh recomputation.
- A jump-to-transcript affordance on the Settings surface (no virtualizer
  to jump within there).
- Fixing the pre-existing, independently-observed gap that
  `transcript_generate_notes` never calls `verify_scriptures` at all
  (unlike `generate_sermon_notes`) — out of this ticket's scope; flagged
  as a separate follow-up rather than folded in here.

### Constraints

- No `dev` branch in this repo. Branch from `origin/main`, fetched fresh,
  pinned by SHA (`4b21c39`). Draft PR against `main`. Own worktree, own
  branch, one ticket / one branch / one MR.
- Fixture-based tests only; never live OpenAI.
- `make ci` must pass, including the headless operator webview check.
- ADR-0026 D5's per-class exemption budget can only be grown by a
  numbered revision of that ADR, never by adding a marker comment alone —
  followed to the letter (Revision 4, not an ad hoc marker).

### Assumptions and unknowns

- **ASSUMED**: the "HH:MM:SS" export format is read literally per the
  Acceptance Criteria text (always three zero-padded components), not the
  narrative example's apparent `MM:SS` shorthand, since the AC is what QA
  verifies against. Validation owner: Quinn/Cody review; revert to the
  YouTube mixed convention if either disagrees.
- **ASSUMED**: writing ADR-0026 Revision 4 inline, as this ticket's own
  implementer, is the correct process — mirrored directly on Revision 3's
  own precedent (written inline by 86akgqdxr's implementer, not through a
  separate architect dispatch) — rather than escalating to a fresh
  Software Architect session. Validation owner: Cody's review is asked
  explicitly to confirm or reject this call; if rejected, the jump
  behaviour is reverted to a no-op (data/copy-export only) pending a real
  Aria-authored revision.
  Validation owner: Cody/Sana review, given this file's review history.
- **ASSUMED**: outline-point timestamps are attached with NO positional
  fallback (unlike chapter markers) — the ticket's own "ideally"/"where
  feasible" wording, read as explicitly softer than chapter markers' "each
  marker carries a timestamp". Validation owner: Quinn/Cody review.
- **ASSUMED**: timestamp linking for `transcript_generate_notes` runs
  after the existing `after.segments != before.segments` unchanged-source
  check, using the confirmed-unchanged segments — never on data that could
  have moved under the generation call. Validation owner: Sana review
  (this is the exact class of race that ticket's own doc comments already
  guard).

## Dependencies and approvals

- 86ajtxzrn (transcript + detection persistence) — status `complete`,
  confirmed via `clickup_get_task`. No blocking dependency.
- Sibling ticket 86akgqdx8 (FR-129) may be running in parallel and touch
  overlapping files (`main.rs`, `settings.js`, `operator_headless.py`'s
  `EXPECTED_MIN_CHECKS`) — expect a rebase before merge.
- No blocking ClickUp dependency owned by another role for the Rust/JS
  work. ADR-0026 Revision 4 is flagged for architecture-authority
  confirmation during review (see Assumptions above), not blocked on it
  before implementation, given the strong Revision-3 precedent and the
  four-reviewer gate as backstop.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `link_timestamps` attaches a real, transcript-derived timestamp to every chapter marker and, on a genuine match, to outline points; monotonic, bounded, never panics on adversarial fixtures (huge/negative-wrapped `start_ms`, empty segments, thousands of segments/items) | `cargo test -p selahcue-core --test test_note_timestamps` | PASS | test output: 18 passed; 0 failed | PASS |
| C-002 | yes | `draft_json` and `sermon_note_draft_json` both emit/recompute the new `timestamps` wire field; a draft generated with chapter markers off carries no timestamp data | `cargo test --manifest-path implementation/desktop/crates/selahcue-operator/Cargo.toml --features dev-keys,openai-notes` | PASS | test output: 170 passed; 0 failed (incl. `sermon_note_draft_json_re_links_timestamps_fresh_from_the_passed_segments`, `sermon_note_draft_json_with_no_segments_carries_no_timestamps`) | PASS |
| C-003 | yes | Every existing `NoteDraft` construction site across the workspace compiles with the new required field | `cargo check --workspace` (+ operator/stt-cloud manifests) | PASS, zero errors | `cargo check --workspace` finished clean (1m37s); `cargo check --manifest-path .../selahcue-operator/Cargo.toml --features dev-keys,openai-notes` finished clean (1m15s) | PASS |
| C-004 | yes | `transcripts.js` renders a clickable timestamp on a matching item and jumps to/highlights the corresponding transcript row on click; a malformed/out-of-range timestamp does not crash the console or produce a nonsensical jump target | `python3 scripts/operator_headless.py` (new checks) | PASS, 0 FAIL | headless output: `=== 1449 checks, 0 FAIL ===`; `TR timestamps` + `TR timestamps (adversarial fixture)` checks all PASS (clickable, jumps, clamps out-of-range to last real segment, malformed offset renders no badge but keeps item text) | PASS |
| C-005 | yes | ADR-0026 Revision 4 lands with a `D5-exempt(jump)` marker on exactly the one new write; `scripts/operator_headless.py`'s per-class D5 check passes at the new counts | `python3 scripts/operator_headless.py` (D5 check specifically) + mutation-verify (add a second unmarked write, confirm RED, revert) | PASS; mutation confirms non-vacuous | headless output: `D5 (ADR-0026) — exactly 1 marked D5-exempt(jump) write(s), matching the ADR` PASS; mutation battery documented inline in ADR rev 4 text ("Rev 4 re-ran the narrow slice... confirm the per-class check goes RED on jump specifically... then revert"). Flagged explicitly for Cody/Sana in C-009. | PASS (pending Cody/Sana process-call confirmation under C-009) |
| C-006 | yes | "Copy chapter markers" produces well-formed `HH:MM:SS Label` lines, one per marker with a resolved timestamp, in source order, on both `transcripts.js` and `settings.js` | headless check(s) + manual fixture inspection | well-formed lines, matching order | Verified by source inspection: `fmtHmsFull` in both `transcripts.js` and `settings.js` emits `two(h)+":"+two(m)+":"+two(s)` (always 3 zero-padded components); headless `PP 86akgqdw0: the 'Copy chapter markers' action is offered...` PASS on settings.js; `TR 86akgqdw0`-equivalent copy checks PASS on transcripts.js | PASS |
| C-007 | yes | `settings.js` renders the same `timestamps` data (plain label, no jump) — data parity between the two consoles | headless check | PASS | Source diff confirms `settings.js` ported `timestampFor`/`fmtHmsFull`/`makeTimestampLabel`/`chapterMarkerLines`/`copyChapterMarkersBtn` from `transcripts.js`, rendered as non-interactive `pp-item-ts` labels; headless `PP 86akgqdw0: the label is genuinely NON-interactive on this surface` PASS | PASS |
| C-008 | yes | `make ci` passes in full, real exit code captured in the log file itself | `make ci` (exit code appended to log, never piped through a filter) | `MAKE_CI_EXIT:0`, `ALL GREEN` | Dispatched to `/tmp/scph-86akgqdw0-make-ci.log` (background task bwwd7ye5x); checked no concurrent `make ci`/Flutter build/test process was active before launch (sibling ticket 86akgqdx8's worktree only had an isolated `cargo test` running, own target dir, no collision) | PENDING |
| C-009 | yes | Four-reviewer gate passed (Cody, Vera, Sana, Quinn), each in an isolated worktree pinned to the reviewed SHA; Cody/Sana explicitly asked to confirm or reject the ADR-0026 Revision 4 process call | dispatched reviews, blocking findings remediated | no blocking findings outstanding | review artifact link | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test -p selahcue-core`, `-p selahcue-cloud --features
  openai`, `--manifest-path crates/selahcue-operator/Cargo.toml --features
  dev-keys,openai-notes`; `cargo fmt --check`; `cargo clippy -- -D
  warnings` on every touched crate.
- Broader regression: full `make ci` (fmt, clippy, all workspace tests,
  headless operator check, Flutter gate) — check `ps aux`/other active
  sessions first (shared machine).
- Independent verifier: Cody, Vera, Sana, Quinn, each in an isolated
  `git worktree add` pinned to the exact reviewed commit.
- Required environment: macOS dev machine, no network required (fixture-
  based tests only); headless Chrome for `operator_headless.py`.

## Iteration ledger

### Iteration 1 (verification of pre-existing uncommitted work; picked up after an external stop)

- Target criterion: C-001..C-007 (baseline verification of the substantial uncommitted diff already present in this worktree from a prior, externally-stopped run).
- Hypothesis: the uncommitted diff (~1100 lines across 10 files) implements the full scope described in this Goal Contract's own "Scope" section correctly and compiles/tests clean; nothing was assumed — every criterion was independently re-verified from scratch per the launching instruction.
- Change or investigation: confirmed worktree state (`git status`, `git fetch origin main`, `git rev-list --count HEAD..origin/main` = 0, merge-base = `4b21c39`, matching this contract's Baseline); re-fetched the live ClickUp task 86akgqdw0 and confirmed its Acceptance Criteria match this contract's scope and the "ASSUMED" `HH:MM:SS` literal-format decision; read the full `providers.rs` diff (`link_timestamps`, `NoteTimestamp`, bounds, doc comments) and the `settings.js`/`transcripts.js` diffs; read the full ADR-0026 Revision 4 diff.
- Verifier executed: `cargo check --workspace`; `cargo test -p selahcue-core --test test_note_timestamps`; `cargo test -p selahcue-core` (full, regression); `cargo test -p selahcue-cloud --features openai` (full, regression); `cargo check --manifest-path .../selahcue-operator/Cargo.toml --features dev-keys,openai-notes`; `cargo test --manifest-path .../selahcue-operator/Cargo.toml --features dev-keys,openai-notes`; `cargo fmt --check`; `cargo clippy -p selahcue-core -p selahcue-cloud --all-targets -- -D warnings`; `cargo clippy --manifest-path .../selahcue-operator/Cargo.toml --features dev-keys,openai-notes --all-targets -- -D warnings`; `python3 scripts/operator_headless.py`; `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <this file>` (structural).
- Result: every command above passed clean — no failures, no clippy/fmt warnings. `test_note_timestamps`: 18/18. Full `selahcue-core`: all suites green. Full `selahcue-cloud --features openai`: 49+3+4+9 tests green. Operator crate: 170/170, including the two timestamp-specific tests. Headless: `=== 1449 checks, 0 FAIL ===`, matching `EXPECTED_MIN_CHECKS = 1449` exactly (no silently-lowered count). Structural goal-contract validation: OK.
- New evidence: the prior agent's uncommitted work is sound, not a stub — it independently re-derives timestamps (never trusts a model estimate), mirrors the established `ScriptureVerdict` join-by-value pattern, has an 18-case adversarial test file covering monotonicity/bounds/malformed data, ported the `settings.js`/`transcripts.js` rendering in parity (this workstream's own twice-bitten bug class), and the ADR-0026 Revision 4 text is unusually candid about its own Medium confidence and explicitly names Cody/Sana for the process-call and safety-argument confirmation this contract already anticipated.
- Decision: commit the verified diff as-is (no code changes needed in this iteration); proceed to full `make ci` (C-008, dispatched to background, log at `/tmp/scph-86akgqdw0-make-ci.log`) and then the four-reviewer gate (C-009).

## Risks and rollback

- Risks: ADR-0026 D5 is a heavily-reviewed, mutation-tested static
  invariant (seven prior review rounds on the underlying virtualizer); a
  wrong or unconvincing extension is the single highest-risk part of this
  ticket and is called out for extra reviewer scrutiny rather than
  papered over. Shared-checkout `make ci` contention with sibling ticket
  86akgqdx8 touching the same files.
- Rollback: single feature branch, not merged until reviewed; revertible
  by not merging the PR. If the ADR-0026 extension is rejected on review,
  the fallback is data/copy-export only (drop `jumpToOffsetMs` and its
  click handler), never a silent, unreviewed `scrollTop` write.

## Pause and escalation conditions

- Cody or Sana rejects the ADR-0026 Revision 4 process call (inline by the
  ticket implementer) — stop shipping the jump behaviour and either loop
  in a dedicated Software Architect session or ship the data/copy-only
  fallback.
- Sibling ticket 86akgqdx8 merges first and changes
  `EXPECTED_MIN_CHECKS`/overlapping files materially — rebase before
  continuing rather than guessing at the merge.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-86akgqdw0-timestamp-linked-notes.md --completion`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: PENDING
- Remaining failed or blocked criteria: PENDING
- ClickUp final evidence comment: PENDING
