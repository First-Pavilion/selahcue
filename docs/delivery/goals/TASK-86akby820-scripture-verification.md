# Goal Contract — TASK-86akby820-scripture-verification

## Identity

- Goal ID: TASK-86akby820-scripture-verification
- Parent goal ID: NONE (was blocked by TASK-86akc0tua-requested-but-empty-sections,
  since resolved — see Dependencies below)
- Title: Every scripture reference in a generated sermon-note draft is verified against
  the local Bible text; unverified references (including unparseable ones) are marked,
  never silently dropped
- Role: backend-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86akby820
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

An operator generating AI sermon notes sees every scripture reference — in the
extracted `scriptures` list and embedded in a section's body text — checked against the
bundled Bible text. A reference that resolves to real verses is marked verified. A
reference that does not (wrong book, chapter/verse past the real book's end, or
unparseable text) is marked unverified, visibly and unmissably, never silently dropped.

## Baseline

Verified against `origin/main` @ `269591e043d3edb96f66cafef512025a374b603a` (2026-09-20),
rebased onto `origin/fix/86akc0tua-requested-but-empty-sections` (that ticket's
not-yet-merged branch — see Dependencies):

- `selahcue-core/src/providers.rs`: `NoteDraft` had no verified/unverified field.
- `selahcue-core/src/scripture.rs`: `parse_one`/`parse`/`parse_strict` never panic on
  untrusted input. `parse()` silently drops unparseable segments
  (`filter_map(...ok())`) and is unbounded — confirmed by direct read, matching the
  ticket's own prior investigation recorded in its ClickUp comments.
- `selahcue-core/src/detection.rs`: `detect(&str) -> Vec<String>` already exists — a
  bounded, deterministic prose scanner built for live-transcript scripture detection
  (R4/ADR-0010), reusable as-is for scanning note-section body text. Confirmed NOT to
  need any changes.
- `selahcue-scripture::verses(&Reference) -> Vec<&'static Verse>` is a sound offline
  oracle: empty exactly when the reference is outside the canon.
- `selahcue-core` has no dependency on `selahcue-scripture` (dependency runs the other
  way), so the verification ALGORITHM (parsing, iteration, bounding, dedup) must live in
  `selahcue-core` with an INJECTED lookup, and the real oracle can only be wired in one
  layer up, in `selahcue-operator` (the only crate depending on both).
- 86akc0tua (landed first per the requesting session's explicit sequencing decision)
  added `DraftCaveat`/`NoteDraft.caveats: Vec<DraftCaveat>` as the shared vocabulary this
  ticket is asked to extend with a second variant, plus a `match` (not an irrefutable
  destructure) in `draft_json` specifically so a second variant forces that function to
  be revisited rather than silently ignored — exercised for real by this ticket.

## Inputs and evidence sources

- ClickUp task 86akby820 — full description + 6 comments (a stale illustrative example
  corrected twice, the prose-scanner-exists correction, the PR #19 field-rename note).
- ClickUp task 86akc0tua and its four-reviewer-gate outcome (PR #46) — the dependency
  this ticket was formally blocked on; see the requesting session's sequencing decision.
- `selahcue-core/src/{scripture.rs,detection.rs,providers.rs}`,
  `selahcue-scripture/src/lib.rs`, `selahcue-cloud/src/openai.rs`,
  `selahcue-operator/src/main.rs`, `selahcue-operator/dist/{settings.js,app.css}`.

## Scope

### In scope

- `selahcue_core::providers::ScriptureVerdict { reference: String, verified: bool }` and
  `NoteDraft.scripture_verdicts: Vec<ScriptureVerdict>`.
- `DraftCaveat::ScriptureUnverified { reference: String }` — the second variant of
  86akc0tua's shared enum.
- `selahcue_core::providers::verify_scriptures(scriptures, sections, exists: impl FnMut)
  -> Vec<ScriptureVerdict>` — pure, bounded (`MAX_VERIFIED_REFERENCES = 64`,
  independent of any upstream provider bound), dependency-injected so it is testable in
  `selahcue-core` with a stub oracle and has no dependency on `selahcue-scripture`.
  Covers the extracted `scriptures` list AND text embedded in flat section items,
  outline point text, and sub-point text (via `detection::detect`). Never uses
  `scripture::parse()` (silently drops failures) — every candidate gets a verdict.
- Wiring in `selahcue-operator`'s `generate_sermon_notes` command handler: runs
  `verify_scriptures` with the real `selahcue_scripture::verses` oracle, gated on
  `include.scripture_extraction`, regardless of `degraded` (a real transcript quote
  echoed into the offline scaffold is worth confirming too).
- `draft_json` extended: per-reference `scripture_verdicts` array; `caveats` restructured
  to kind-tagged objects (`{kind:"section_empty",...}` / `{kind:"scripture_unverified",
  reference}`) so the two purposes 86akc0tua's flat array served can no longer
  cross-fire on each other.
- `SCRIPTURE_VERIFICATION_WORDING` — a fixed, honest string stating the check confirms
  the reference *exists*, not that quoted words are accurate. Surfaced once per draft
  when at least one reference was actually checked.
- Console rendering: unverified references marked inline (extracted list) and in a
  supplementary block (embedded-only), computed-style-visible, using the `--sc-warn`
  register deliberately (unlike 86akc0tua's empty-section case — this IS a genuine
  fabrication-safety concern, not a routine/neutral outcome).
- Table-driven tests: valid reference, nonexistent book, chapter past a real book's end,
  verse past a real chapter's end, unparseable text, AND the four single-chapter-book
  "looks plausible but isn't" cases from the ticket's own comment history (Obadiah 2:1,
  3 John 4:12, Jude 2:1, Philemon 2:3) — verified against the REAL bundled KJV text in
  `selahcue-operator`'s tests, not just a stub oracle.
- Bounded-memory test, mutation-verified (constant temporarily set to `usize::MAX`,
  confirmed the positive-control assertion goes red with siblings green, reverted).

### Non-goals

- Note generation itself (86akby7d8, already shipped).
- Checking quotation accuracy — this ticket confirms the reference address exists, not
  that words attributed to it are accurate. Stated explicitly in the UI copy.
- Licensed translations.
- Timestamp-linking (FR-124) and export formats (FR-127) — separate, later tickets.
- Persisting `scripture_verdicts`/the `ScriptureUnverified` caveat through the LAN wire
  protocol. Same non-goal decision as 86akc0tua and for the same reason (cross-language
  contract change, out of footprint) — but with a materially different consequence:
  losing the verdict on reload/edit-save degrades to the PRE-ticket rendering (a plain
  reference list, no marks), never to a confusing half-state, because no placeholder
  structure is pushed into persisted data for scripture verdicts the way 86akc0tua's
  empty-section placeholders were. This asymmetry is deliberate and is called out
  explicitly for Cody's review, given his blocking finding on 86akc0tua's persistence
  path.

### Constraints

- Offline, no network — the check runs entirely against the bundled text.
- Never weaken `draft_schema`'s strictness (not touched by this ticket at all).
- `selahcue-core` must not gain a dependency on `selahcue-scripture` (would be
  circular) — enforced by the dependency-injection design.

### Assumptions and unknowns

- **ASSUMED**: it is correct to run verification unconditionally regardless of
  `degraded`, rather than skipping it for the offline scaffold as 86akc0tua does for its
  own caveat. Rationale recorded in Scope above; flagged for reviewer scrutiny since it
  is the one place this ticket's design diverges from 86akc0tua's precedent.
  Validation owner: Cody/Sana review.
- **ASSUMED**: showing embedded-only unverified references in a supplementary UI block
  (rather than inline-highlighting the substring inside the rendered item text) meets
  the ticket's "checked, not dropped, and visibly marked" bar without requiring
  substring-position tracking through the render pipeline. Validation owner: Quinn/UX
  judgement on review.

## Dependencies and approvals

- TASK-86akc0tua-requested-but-empty-sections — formal ClickUp blocking dependency.
  RESOLVED: PR #46 opened, four-reviewer gate run (Vera/Sana/Quinn pass, Cody's one
  blocker remediated and pushed), `make ci` green. This ticket branches from that PR's
  head and will rebase onto `origin/main` once it merges.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A valid reference verifies | `cargo test -p selahcue-core --test test_scripture_verify` + operator real-oracle test | PASS | test output | PASS |
| C-002 | yes | A reference naming no real book is unverified, not dropped | `a_reference_naming_no_real_book_is_unverified` (real oracle) | PASS | test output | PASS |
| C-003 | yes | A chapter past a real (short) book's end is unverified | `a_chapter_past_a_real_short_books_end_is_unverified` | PASS | test output | PASS |
| C-004 | yes | A verse past a real chapter's end is unverified | `a_verse_past_a_real_chapters_end_is_unverified` | PASS | test output | PASS |
| C-005 | yes | Unparseable text is unverified and still shown, never dropped | `unparseable_text_in_the_list_is_unverified_and_still_shown`, `an_unparseable_reference_is_unverified_and_kept_verbatim_never_dropped` | PASS | test output | PASS |
| C-006 | yes | Four plausible-but-fake references (real books, fake chapters) all caught | `four_plausible_but_nonexistent_references_are_all_caught` (real bundled text) | PASS | test output | PASS |
| C-007 | yes | A fabricated reference embedded in a sermon point is found and marked unverified | `a_fabricated_reference_embedded_in_a_sermon_point_is_caught_against_the_real_text` | PASS | test output | PASS |
| C-008 | yes | The verdict is carried on the draft (`NoteDraft.scripture_verdicts`) | `draft_json_carries_scripture_verdicts_and_the_matching_caveats` | PASS | test output | PASS |
| C-009 | yes | Console renders unverified marks unmissably, computed-style | `scripts/operator_headless.py`, computed-style assertions + mutation-verify | PASS, 1311→1317 checks, mutation RED confirmed then reverted | headless output | PASS |
| C-010 | yes | Wording states existence-only scope, not quotation accuracy | Exact string check in headless test + `SCRIPTURE_VERIFICATION_WORDING` | PASS | test output | PASS |
| C-011 | yes | Offline, no network | Design review — no HTTP/network code added | no network calls in `verify_scriptures`/its call sites | inspection | PASS |
| C-012 | yes | Bounded memory, mutation-verified | `an_absurd_number_of_distinct_scriptures_is_bounded_not_unbounded` + manual mutation (`MAX_VERIFIED_REFERENCES = usize::MAX`) | PASS live; FAIL under mutation, reverted | test output | PASS |
| C-013 | yes | Toggle off → no verification work, nothing displayed | Gated on `include.scripture_extraction` in `main.rs` | `scripture_verdicts` stays empty when off, mirroring `scriptures` itself | inspection + existing toggle tests | PASS |
| C-014 | yes | `make ci` passes in full | `make ci` | exit 0, ALL GREEN | `MAKE_CI_EXIT:0`, `1317 checks, 0 FAIL`, zero `^FAIL`/`error[`/`FAILED` in log | PASS |
| C-015 | yes | Four-reviewer gate passed | Cody/Vera/Sana/Quinn findings remediated | no blocking findings outstanding | PENDING | PENDING |

## Verification plan

- Focused: `cargo test -p selahcue-core --test test_scripture_verify`,
  `cargo test -p selahcue-operator --features dev-keys,openai-notes
  scripture_verification_tests`.
- Broader regression: full `make ci`.
- Independent verifier: Cody, Vera, Sana, Quinn.
- Required environment: macOS dev machine, no network required.

## Iteration ledger

### Iteration 1 — design and core algorithm

- Target criterion: C-001 through C-008
- Hypothesis: a dependency-injected `verify_scriptures` in `selahcue-core`, wired to the
  real oracle one layer up in `selahcue-operator`, satisfies the full table without
  `selahcue-core` gaining a circular dependency.
- Change: `ScriptureVerdict`, `DraftCaveat::ScriptureUnverified`,
  `NoteDraft.scripture_verdicts`, `verify_scriptures` in `providers.rs`; wiring in
  `main.rs`'s `generate_sermon_notes`; `draft_json` restructured to kind-tagged caveats.
- Verifier executed: `cargo test -p selahcue-core --test test_scripture_verify` (13
  tests, stub oracle), `cargo test -p selahcue-operator scripture_verification_tests` (9
  tests, real bundled-text oracle).
- Result: all 22 pass, including the exact four-single-chapter-book table from the
  ticket's own comment history, against the REAL KJV text.
- Decision: iterate → console rendering (C-009, C-010).

### Iteration 2 — console rendering

- Target criterion: C-009, C-010
- Change: `settings.js`/`app.css` — per-reference inline marks on the extracted list, a
  supplementary block for embedded-only unverified references, the verification-scope
  note. Fixed a design bug caught before it shipped: 86akc0tua's `hasCaveat`/"any
  caveat" checks would have cross-fired on scripture caveats (a `ScriptureUnverified`
  caveat would have wrongly triggered 86akc0tua's empty-section explainer) — resolved by
  splitting into `hasEmptySectionCaveat`/`anySectionEmptyCaveat` (kind-scoped) instead of
  a generic "any caveat" check.
- Verifier executed: `scripts/operator_headless.py`; manual mutation (disabled the
  unverified-mark render branch) to confirm non-vacuous.
- Result: 1311 → 1317 checks, 0 FAIL. One assertion bug in my own test caught and fixed
  along the way (a `nextElementSibling` check that didn't account for the " · "
  separator being a text node, not an element — `nextElementSibling` correctly skips
  text nodes, so it found the NEXT reference's span, not "no next element"). Mutation
  run: exactly 1 targeted FAIL, reverted to 0.
- Decision: iterate → make ci (C-014).

### Iteration 3 — full make ci

- Target criterion: C-014
- Verifier executed: `make ci` (checked for concurrent make/cargo/flutter activity
  first; waited once for another session's `make ci` to clear before starting, per
  CLAUDE.md's serialisation rule for this shared checkout).
- Result: `MAKE_CI_EXIT:0`, `ALL GREEN`, `1317 checks, 0 FAIL`, zero `^FAIL`/`error[`/
  `FAILED` lines in the ~8200-line log. `git status --porcelain` after the run showed
  the same unrelated `pubspec.lock` drift seen on 86akc0tua's runs (a `flutter test`
  side effect) — reverted with `git checkout --`, leaving exactly the ticket's declared
  file footprint plus the new `test_scripture_verify.rs` and this Goal Contract.
- Decision: complete → commit, push, open Draft PR, dispatch four-reviewer gate.

## Risks and rollback

- Risk: this ticket's design deliberately diverges from 86akc0tua's precedent (verifies
  regardless of `degraded`) — flagged for explicit reviewer attention rather than
  assumed correct by analogy.
- Risk: built on 86akc0tua's not-yet-merged branch; will need a rebase onto `main` once
  that PR merges, before this PR is marked ready.
- Rollback: single feature branch, not merged until reviewed.

## Pause and escalation conditions

- If 86akc0tua's PR requires further remediation that changes `DraftCaveat`'s shape
  again, rebase and re-verify before continuing.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py <path> --completion`
- Validator result: (recorded after execution)
- Independent verification result: (recorded after execution)
- Terminal state: (recorded after execution)
- Remaining failed or blocked criteria: (recorded after execution)
- ClickUp final evidence comment: (recorded after execution)
