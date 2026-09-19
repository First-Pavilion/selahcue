# Goal Contract — TASK-86akc0tua-requested-but-empty-sections

## Identity

- Goal ID: TASK-86akc0tua-requested-but-empty-sections
- Parent goal ID: NONE
- Title: A note section the operator switched ON that comes back empty is reported as requested-but-empty, never silently absent
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akc0tua
- Created: 2026-09-19
- Updated: 2026-09-19
- Maximum iterations: 8
- Independent verification required: yes

## Objective

When the operator switches a note section (outline, any flat section, the short
summary, or the scriptures list) ON and the generated draft returns no content for
it, the console tells the operator so — a distinct, unmissable state from "the
operator left this off" (silence) and from "the cloud path is degraded" (the
existing FR-135 notice, which must not be duplicated under it).

## Baseline

Verified against `origin/main` @ `269591e043d3edb96f66cafef512025a374b603a`
(2026-09-19):

- `implementation/desktop/crates/selahcue-cloud/src/openai.rs:672-694` — the outline
  and `FLAT_SECTIONS` loop each silently omit the `NoteSection` when the parsed
  content is empty; no signal is carried anywhere that the section was requested.
- `implementation/desktop/crates/selahcue-cloud/src/openai.rs:636-649` (`summary`)
  and `:652-668` (`scriptures`) have the identical drop shape: `Option`/`Vec` ends up
  empty/`None` with no record that it was requested.
- `implementation/desktop/crates/selahcue-operator/dist/settings.js:796`
  (`if (d.summary) …`) and `:816` (`if (d.scriptures && d.scriptures.length) …`)
  independently drop the same two cases on the render side.
- `selahcue_core::providers::NoteDraft` has no field to carry this signal.
- `selahcue-cloud/src/local.rs`'s offline fallback already pushes deliberately-empty
  placeholder sections for `prayer_points`/`notable_quotations`/`social_excerpts`
  (never for `chapter_markers`, `summary`, or `scriptures`) — any generic
  "requested-but-empty" computation must not fire on these when the outcome is
  degraded.
- No recorded fixture files (the reported zero-marker / seven-marker OpenAI
  responses) exist anywhere in the repository or as ticket attachments (checked).

## Inputs and evidence sources

- ClickUp task 86akc0tua (description + 0 comments as of start) — authoritative scope
  and acceptance criteria.
- `implementation/desktop/crates/selahcue-cloud/src/openai.rs`,
  `implementation/desktop/crates/selahcue-cloud/src/local.rs`,
  `implementation/desktop/crates/selahcue-cloud/src/lib.rs` (`GenerationOutcome`).
- `implementation/desktop/crates/selahcue-core/src/providers.rs` (`NoteDraft`,
  `NoteSection`, `IncludeInNotes`).
- `implementation/desktop/crates/selahcue-operator/src/main.rs` (`draft_json`,
  `generate_sermon_notes` command).
- `implementation/desktop/crates/selahcue-operator/dist/settings.js` + `app.css`.
- Uma (ui-ux-designer) — wording sign-off, dispatched at task start.

## Scope

### In scope

- A `DraftCaveat` enum on `selahcue_core::providers`, starting with a
  `SectionRequestedEmpty { heading: String }` variant, and `NoteDraft.caveats:
  Vec<DraftCaveat>`.
- Populate `caveats` in `openai.rs::parse_draft` for: the outline, every
  `FLAT_SECTIONS` entry, `summary`, and `scriptures` — all four drop sites, not only
  the two the ticket names as strictly in-scope (see Assumptions).
- A field-present-as-JSON-array guard so a missing/wrong-typed field (malformed or
  truncated response) is never read as a confirmed empty answer.
- `local.rs` never populates `caveats` — the degraded-suppression rule falls out of
  this rather than needing a special case, verified with an explicit test regardless.
- `draft_json` (main.rs) emits `caveats` in the live-generation response JSON.
- `settings.js`/`app.css`: render the caveats as an unmissable callout, reusing the
  `--sc-warn` register, only when the draft is not degraded.
- Table-driven Rust tests: outline empty, each flat section empty, summary empty,
  scriptures empty, a disabled section (no caveat), a degraded result (no caveats
  regardless), a truncated/malformed response (no false "confirmed empty").
- Headless webview check asserting computed style, not class name.
- `make ci` green, including the headless operator check.

### Non-goals

- Automatic retry or per-section regenerate.
- Detecting *why* a section is empty.
- Prompt tuning (86akbzxyc's territory).
- Relaxing `draft_schema`'s `required`/`additionalProperties: false` strictness.
- Persisting `caveats` through the LAN wire protocol / SQLite round trip
  (`selahcue_lan::protocol::SermonNoteDraftView`, `sections_to_json`/
  `parse_json_column`) — out of the ticket's stated file footprint, and touching the
  cross-language wire contract is a materially bigger, separately-reviewable change.
  A draft reloaded after a restart (`load_sermon_note_draft`) will not show a caveat
  computed on a prior generation. Documented as a known, deliberate limitation, not
  silently dropped.

### Constraints

- Offline, no network, no automatic retry.
- Never weaken `draft_schema`'s strictness.
- `settings.js` change and backend change land in the same commit/MR (ticket
  requirement).

### Assumptions and unknowns

- **ASSUMED**: widening scope from the ticket's two named "in-scope" drop sites
  (`openai.rs` outline + `FLAT_SECTIONS` loop) to include the two `settings.js`
  drop sites Uma found (summary, scriptures) — the ticket explicitly left this to
  the owner ("Owner decides whether to widen scope now or file a follow-up").
  Recorded to the requesting session and in the ClickUp start comment. Validation
  owner: the requesting session / ticket owner, informed before implementation.
- **ASSUMED**: no real recorded zero-marker/seven-marker OpenAI response exists to
  use as a fixture. Reconstructed fixtures matching the reported shape and the
  documented wire format (per `openai.rs`'s own module doc, "taken from the live API
  on 2026-09-04") are used instead, labelled as reconstructed. Validation owner:
  Cody/Quinn review — flagged explicitly rather than presented as a literal capture.
- **UNKNOWN until Uma responds**: exact wording for the callout. Blocks the
  `settings.js` acceptance criterion on wording sign-off; tracked as its own
  completion criterion below.

## Dependencies and approvals

- Uma (ui-ux-designer) — wording sign-off. Dispatched; response pending.
- No ClickUp blocking dependency on this ticket itself (it is the blocker for
  86akby820, not blocked by anything).

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A section requested (enabled) and returned empty carries a `SectionRequestedEmpty` caveat | `cargo test -p selahcue-cloud --features openai` | PASS, 46 tests | test output | PASS |
| C-002 | yes | The outline is covered, not only the `FLAT_SECTIONS` loop | `the_outline_is_flagged_requested_but_empty_when_points_comes_back_as_an_empty_array` | PASS | test output | PASS |
| C-003 | yes | Every flat section the toggles can enable is covered | `every_enabled_flat_section_is_flagged_requested_but_empty_when_it_comes_back_as_an_empty_array` (table-driven, 8 rows) | PASS | test output | PASS |
| C-004 | yes | `summary` and `scriptures` empty-but-requested are covered | `summary_and_scriptures_are_flagged_requested_but_empty_too` | PASS | test output | PASS |
| C-005 | yes | A degraded (`local.rs`) result carries zero caveats | `a_degraded_local_fallback_carries_zero_caveats_even_though_its_placeholders_are_empty` | PASS | test output | PASS |
| C-006 | yes | A disabled section produces no caveat and no message | `a_section_the_operator_switched_off_never_gets_a_caveat` | PASS | test output | PASS |
| C-007 | yes | A truncated/malformed response is never read as "legitimately empty" | `a_truncated_or_partial_response_is_never_read_as_legitimately_empty` | PASS | test output | PASS |
| C-008 | yes | Wording is agreed with Uma | Uma's response recorded on the ClickUp task | agreed copy in comment | ClickUp comment 90130316130904 (settled), reaffirmed 90130323184524 | PASS |
| C-009 | yes | Console renders the caveat unmissably, suppressed when degraded | `scripts/operator_headless.py`, computed-style assertion; mutation-verified | PASS, 1300→1311 checks, mutation RED confirmed then reverted GREEN | headless output | PASS |
| C-010 | yes | `settings.js` change and backend change are one commit/MR | will confirm at commit time (`git show --stat`) | both files present | git log | PENDING |
| C-011 | yes | `make ci` passes in full | `make ci` | exit 0, ALL GREEN | `MAKE_CI_EXIT:0`, `1311 checks, 0 FAIL`, zero FAIL/error[/FAILED in ~6500-line log | PASS |
| C-012 | yes | Four-reviewer gate passed | Cody/Vera/Sana/Quinn findings remediated | no blocking findings outstanding | review artifact | PENDING |

Design note (for 86akby820 and future reuse, per the requesting session's ask): the shared
vocabulary is `selahcue_core::providers::DraftCaveat` (currently one variant,
`SectionRequestedEmpty { heading: String }`), carried as `NoteDraft.caveats: Vec<DraftCaveat>`.
Populated only in `openai.rs::parse_draft` (never in `local.rs`, which is how the degraded
suppression holds without a special case). `draft_json` (main.rs) computes a per-section
`empty_requested: bool` and a flat `caveats: [heading, ...]` array for the live-generation
response; this is NOT persisted through the LAN wire protocol (documented non-goal).

## Verification plan

- Focused: `cargo test -p selahcue-cloud`, `-p selahcue-core`, `-p selahcue-operator`.
- Broader regression: full `make ci` (fmt, clippy, all workspace tests, headless
  operator check, Flutter gate).
- Independent verifier: Cody, Vera, Sana, Quinn.
- Required environment: macOS dev machine, no network required for tests.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-007 (core Rust behaviour)
- Hypothesis: adding `DraftCaveat`/`NoteDraft.caveats` and populating it at the four
  drop sites, guarded by a present-as-array/present-as-string check, satisfies the
  table-driven set.
- Change or investigation: TDD — wrote the six new tests first (confirmed they failed
  to compile against the not-yet-existing `DraftCaveat` type), then implemented
  `DraftCaveat`/`NoteDraft.caveats` in `providers.rs`, the four call sites in
  `openai.rs::parse_draft`, and updated the four other `NoteDraft` construction sites
  (`local.rs`, `contract.rs`, two in `main.rs`) to carry the new field.
- Verifier executed: `cargo test -p selahcue-cloud --features openai --test test_openai`
- Result: 44 tests pass (one pre-existing test,
  `wrong_types_and_missing_fields_degrade_to_empty_rather_than_failing`, needed its
  assertions updated — its `illustrations: [1,2,{"nested":true}]` fixture is a
  well-typed-but-unusable array, which this ticket's own design now correctly treats
  as a legitimate empty answer rather than silence; this is the fix working as
  intended, not a regression).
- New evidence: `cargo check`/`clippy -D warnings` clean on `selahcue-core`,
  `selahcue-cloud --features openai`, `selahcue-operator --features
  dev-keys,openai-notes` (after `make stage-operator-binaries`, the documented
  fresh-worktree prerequisite).
- Decision: iterate → target C-008/C-009 (wording + console rendering)

### Iteration 2

- Target criterion: C-008, C-009 (wording sign-off, console rendering)
- Hypothesis: Uma's settled copy (dispatched at task start, and — discovered only
  after dispatching her a second time, because I had not fetched this ticket's
  comment history before starting — already fully worked and posted on this ticket
  on 2026-09-04, comment 90130316130904) can be wired directly; her visual-treatment
  correction (no `--sc-warn`, a quiet inline `.pp-gen-empty` line + a chromatically
  neutral once-per-draft explainer) supersedes my original `--sc-warn`-based plan.
- Change or investigation: revised `openai.rs` to push an EMPTY `NoteSection` (not
  omit it) for the caveated cases, so the heading holds its natural position per
  Uma's design; added `draft_json`'s per-section `empty_requested` + top-level
  `caveats`; rewrote `settings.js::renderDraftView` and `app.css` per Uma's exact
  spec (copy, placement, suppression when degraded); added headless assertions
  covering ON+empty (computed style, exact text), a populated positive control in
  the SAME render, an absent never-requested section, the Summary/Scriptures
  analogues, and the once-per-draft explainer; added a mutation-catching case to the
  existing "degraded" fixture (a caveated empty section that must still be
  suppressed) since the real backend can never produce that combination itself.
- Verifier executed: `python3 scripts/operator_headless.py`; a manual mutation
  (disabling the `empty_requested` render branch) to confirm the new checks are not
  vacuous.
- Result: 1311 checks, 0 FAIL (verified baseline before this change, on a clean
  `origin/main` worktree: 1300 — `EXPECTED_MIN_CHECKS` updated with the real
  observed number, not a derived one). Mutation run: exactly 1 FAIL (the targeted
  check), 1310 siblings still PASS; reverted, back to 0 FAIL.
- New evidence: `cargo fmt --check` clean on both the desktop workspace and the
  operator crate after `cargo fmt`.
- Decision: iterate → target C-010..C-012 (single-commit/MR, full `make ci`,
  four-reviewer gate)

### Iteration 3

- Target criterion: C-011 (`make ci` full gate)
- Hypothesis: `make ci` passes cleanly, no concurrent contention (checked immediately
  before starting: no other `make ci`/cargo/flutter processes running).
- Change or investigation: ran `make ci` in the background (it exceeded the 600s
  foreground timeout). The wrapper command chained `make ci > log 2>&1; echo
  EXIT_CODE=$?; tail ...` with `;`, not `&&` — this is the documented
  piping-swallows-the-gate's-exit-code trap (own memory note): the completion
  notification reported "exit code 0" because that is the exit code of the trailing
  `tail`, not of `make ci`. Reading the actual log showed `make: *** [ci] Error 2`
  and `FAIL: headless Chrome timed out (infra) — no RESULTS produced` — a real
  failure the notification's headline number did not reflect.
- Verifier executed: inspected `/tmp/make_ci_86akc0tua.log` directly; checked `ps
  aux`/`uptime` for concurrent activity at the time of failure.
- Result: system load average was 33–40 (14 users on a shared machine) with at least
  two OTHER sessions' `make ci` runs and a `flutter test` run active concurrently in
  other worktrees, none related to this ticket. I had checked for concurrent
  activity before starting mine (none was running then); other sessions started
  theirs after mine was already underway, which this checkout has no lock against.
  The same headless script run standalone, twice, immediately before `make ci`
  (once clean, once under a deliberate mutation) both completed normally with no
  timeout — strong evidence this is the documented class of false RED from
  concurrent heavy CI runs on this shared machine, not a defect in this change.
  `operator_headless.py` itself labels the failure "(infra)", distinguishing it from
  an assertion failure in its own output.
- New evidence: none yet confirming a clean re-run — retry queued, waiting for the
  other sessions' load to clear before re-running rather than re-diagnosing a likely
  infra flake under contention.
- Decision: iterate → re-run `make ci` once contention clears, capturing the exit
  code directly (not through a `;`-chained trailing command) this time.

### Iteration 4

- Target criterion: C-011 (`make ci` full gate), re-run
- Hypothesis: with the other sessions' `make ci`/`flutter test` no longer running,
  the same code passes cleanly — confirming iteration 3's failure was infra
  contention, not a defect.
- Change or investigation: re-ran `make ci`, this time with the exit code captured
  via `{ make ci > log 2>&1; echo "MAKE_CI_EXIT:$?" >> log; }` — written INTO the
  log file itself, immediately after `make ci`, so no later command in any wrapper
  can mask it.
- Verifier executed: `grep -n "MAKE_CI_EXIT" /tmp/make_ci_86akc0tua_v2.log`;
  `grep -c "^FAIL"`, `grep -n "error\["`, `grep -n "FAILED"` over the whole log.
- Result: `MAKE_CI_EXIT:0`. `== local Rust/Flutter gate: ALL GREEN ==`. The headless
  check specifically: `=== 1311 checks, 0 FAIL ===` — identical to both standalone
  runs before this `make ci` attempt. Zero `FAIL`/`error[`/`FAILED` lines anywhere
  in the ~6500-line log. Confirms iteration 3 was the documented false-RED class
  from concurrent heavy CI runs on this shared machine, not a defect in this change.
- New evidence: `git status` after the run showed one unexpected, unrelated diff —
  `implementation/mobile/selahcue_controller/pubspec.lock` (three transitive
  package version bumps: matcher, meta, test_api) — a side effect of `make ci`'s own
  `flutter test`/`flutter pub get` step resolving newer compatible versions, not
  anything this ticket touched. Reverted with `git checkout --` to keep the diff
  scoped to exactly this ticket's file footprint; `git status --porcelain` after
  matches the nine files declared in the ClickUp ticket and the start comment.
- Decision: complete → proceed to commit, Draft PR, four-reviewer gate.

### Iteration 5

- Target criterion: C-012 (four-reviewer gate)
- Hypothesis: N/A — this is the review round itself.
- Change or investigation: dispatched Cody, Vera, Sana, Quinn against PR #46 in parallel,
  each in an isolated worktree.
- Verifier executed: each reviewer's own independent build/test run against the PR head.
- Result: Vera (performance) — PASS, no findings. Sana (security) — PASS, non-blocking
  (three informational/low findings, none requiring a code change beyond what's already
  planned). Quinn (QA) — GATE_REVIEW, all in-scope acceptance criteria PASS; filed one
  out-of-scope gap (86akmfn54: caveats don't survive the persisted-draft-reload path) as a
  linked follow-up, correctly not blocking. Cody (code) — **one BLOCKER**: the same
  persistence gap Quinn/Vera/Sana treated as a disclosed non-goal, but sharpened: after a
  reload or the next edit-save, a caveated-empty section reappears as a bare heading over
  a silently empty list with NO explanation at all — objectively worse than this ticket's
  own pre-fix behaviour (fully silent), not merely "the improvement doesn't persist."
- New evidence: traced the exact mechanism Cody named — `sections_to_json`/
  `sermon_note_draft_json`'s round trip has no caveat-carrying field, and `draft_json`'s
  caveat computation only ever runs for the live-generation response.
- Decision: iterate → remediate Cody's blocker (the only one), re-verify, re-run `make
  ci`, reply on the PR, do not claim `VERIFIED_COMPLETE` until this is closed.

### Iteration 6

- Target criterion: C-012 (remediate Cody's blocking finding)
- Hypothesis: filtering caveated-empty sections out of what gets PERSISTED (not changing
  the wire protocol) restores the pre-86akc0tua persisted shape for exactly those
  sections, closing the "worse than silence" gap without the larger, cross-language wire
  contract change threading full caveat data through would require.
- Change or investigation: added `sections_to_persist(&NoteDraft) -> Vec<NoteSection>` in
  `main.rs`, called at the one persistence call site instead of passing
  `outcome.draft.sections` straight to `sections_to_json`. Filters by heading against
  `SectionRequestedEmpty` caveats only — `local.rs`'s uncaveated, deliberately-empty
  placeholder sections are untouched. Three new unit tests (`sections_to_persist_tests`):
  a caveated-empty section is dropped; an uncaveated empty section still persists; a
  populated section sharing a caveat's heading (a combination `parse_draft` never
  actually produces) is still filtered, with that heading-keyed-not-emptiness-keyed
  behaviour documented explicitly rather than silently relied upon.
- Verifier executed: `cargo test --features dev-keys,openai-notes` (targeted, then full),
  `cargo clippy --features dev-keys,openai-notes --all-targets -- -D warnings`, `cargo fmt
  --check` (both the workspace and the operator crate), full `make ci`.
- Result: 138 operator tests pass (135 + 3 new). Clippy clean after one fix (an
  exhaustive-single-variant `filter_map` that should be a `map` today — deliberately
  documented as becoming a real `filter_map` again once 86akby820 adds `DraftCaveat`'s
  second variant). `cargo fmt --check` clean. Full `make ci` re-run pending at time of
  writing this entry; see the next entry for its result.
- New evidence: replied on PR #46 describing the fix and its scope, including what was
  deliberately NOT done (making the headless mock's `load_sermon_note_draft` simulate the
  real backend's field loss, which is a separate, smaller test-fidelity improvement, not
  part of this remediation).
- Decision: iterate → confirm `make ci` green, then push and request Cody re-check.

### Iteration 7

- Target criterion: C-011, C-012 (re-verify `make ci`; close Cody's blocker)
- Verifier executed: `make ci` (system load had dropped to 4.97/9.96/15.51 with zero
  concurrent make/cargo/flutter processes — checked before running).
- Result: `MAKE_CI_EXIT:0`, `ALL GREEN`, `1311 checks, 0 FAIL` (headless — unchanged, this
  remediation touched no JS/CSS), zero `^FAIL` lines anywhere in the log,
  `git status --porcelain` shows only the two intended files changed (no repeat of the
  earlier `pubspec.lock` drift). Replied on PR #46 describing the fix, its scope, and the
  one thing deliberately left out (headless-mock fidelity for the persisted-reload path).
- Decision: complete → C-011 and C-012 both PASS pending Cody's re-check acknowledgement.
  Proceeding to push and continue 86akby820 in parallel.

## Risks and rollback

- Risks: `settings.js` render path is shared with the FR-135 degraded notice and
  FR-123 disclosure in the same header block — a regression there is caught by
  existing headless checks. Wording sign-off from Uma is a soft dependency — if her
  response is delayed, implementation proceeds with a documented placeholder
  constant that is trivial to swap once she responds, and C-008 stays PENDING until
  then.
- Rollback: single feature branch, not merged until reviewed; revertible by not
  merging the PR.

## Pause and escalation conditions

- Uma's wording does not land before the rest of the ticket is otherwise complete —
  hold C-008 PENDING, do not fabricate sign-off.
- Any conflict between this ticket's scope-widening decision and the requesting
  session's expectation — already flagged in the ClickUp start comment.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: (recorded after execution)
- Independent verification result: (recorded after execution)
- Terminal state: (recorded after execution)
- Remaining failed or blocked criteria: (recorded after execution)
- ClickUp final evidence comment: (recorded after execution)
