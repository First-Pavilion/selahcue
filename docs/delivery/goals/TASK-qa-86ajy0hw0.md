# Goal Contract — TASK-qa-86ajy0hw0

## Identity

- Goal ID: TASK-qa-86ajy0hw0
- Parent goal ID: NONE
- Title: Independent QA verdict on PR #13 (plan link resolution, deck label, plan summary, verse-numbers) — acceptance criteria verified and every claimed guard proven to bite
- Role: qa-engineer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hw0
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every acceptance criterion on 86ajy0hw0 is independently confirmed PASS, FAIL or
ALREADY-DELIVERED against PR #13 head `6aee657`, and every control the new tests claim to
guard is shown by mutation to fail RED when that control is removed — or reported as
vacuous when it does not.

## Baseline

- Worktree `/Users/m.oluwole/Documents/code/scph-wt-plan-links`, branch
  `feat/86ajxxqtp-plan-link-missing-state`, head `6aee657`, merge-base with `origin/main`
  = `f770a6c` (branch is NOT behind origin/main).
- Diff: 9 files, +931/-23. Production code in `selahcue-core/src/plan.rs`,
  `selahcue-lan/src/protocol.rs`, `selahcue-app/src/controller.rs`,
  `selahcue-app/src/operator.rs`, `selahcue-operator/dist/app.js` (comment only).
- `CARGO_TARGET_DIR=/Users/m.oluwole/Documents/code/scph-wt-plan-links/.target` (isolated;
  does NOT poison the main checkout's cache).
- PR #13 is Draft, no reviews posted, no PR comments.

## Inputs and evidence sources

- ClickUp 86ajy0hw0 description (4 scope items) + 5 comments, incl. Kenji's gap
  re-verification recording which 2 of 4 were already delivered.
- GitHub PR #13 body and commit message.
- `docs/architecture/ARCHITECTURE.md` NFR-024 (no component failure may blank live output).
- Repo `CLAUDE.md` bounded-memory-test bar (per-key accessor, assert-hit-before-contract,
  compile-time premise pin, assert the entity, positive control, mutation-verify).
- `implementation/mobile/selahcue_controller/lib/models/protocol.dart` (cross-language client).

## Scope

### In scope

- Independent verification of the 4 ticket scope items against the PR head.
- Mutation verification of the guards the author names, plus guards the author did NOT name
  — in particular the NFR-024 test.
- Edge cases the author asked to have challenged: live+staged with a missing link;
  kind/field disagreement; persistence round-trip of the new fields; summary at empty plan
  and at MAX_PLAN_ITEMS.
- Cross-language impact of the new always-present `summary` object on the Dart client.
- ClickUp bugs with reproducible evidence for blocking findings; review posted on PR #13.

### Non-goals

- Correctness review (Cody), security review (Sana), performance review (Vera).
- Implementing fixes. QA reports; Kenji remediates.
- Frontend rendering of the new fields (explicitly a follow-up; unblocks Farah).
- Merging PR #13.

### Constraints

- Do NOT run `make ci` (concurrent Flutter runs give false reds in this shared checkout).
- Never pipe a gate into `tail` — capture output, then check `$?`.
- `-p selahcue-app` REQUIRES `--features server`.
- Diff against `origin/main`, never local `main`.
- Never commit, stage, stash or revert another session's work in the shared checkout.

### Assumptions and unknowns

- ASSUMED: `Theme::dark()` is the theme used by the NFR-024 test's controller — to be
  VERIFIED by reading `LiveController::new` call in the test helper.
- UNKNOWN: whether the shipped operator webview ever populates a deck `label` — to be
  verified by reading every `set_item_content` call site in `dist/app.js`.

## Dependencies and approvals

- Media library does not exist in any layer (Kenji's escalation on 86ajy0hw0) — owner
  decision, not a QA blocker for this PR.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The three named test suites are green at head `6aee657` | `cargo test -p selahcue-core --test test_plan`; `-p selahcue-lan --features server --test test_protocol`; `-p selahcue-app --features server --test test_controller` | exit 0, 0 failed, each | core test_plan 31 passed / lan test_protocol 27 passed / app test_controller 122 passed, all exit 0; plus fmt --check exit 0, clippy -D warnings exit 0, data test_plan_repo 17 passed | PASS |
| C-002 | yes | `deck_label_is_bounded_by_character_and_a_normal_name_is_kept_verbatim` fails RED when the character cap is removed | remove `.take(MAX_LINK_LABEL_LEN)` in `sanitize_label`, run test_plan with siblings | test FAILS | M1 (`.take(MAX_LINK_LABEL_LEN)` removed) -> test RED, 26 passed 1 failed | PASS |
| C-003 | yes | The same test fails RED when the on-the-way-in bound in `set_item_content` is removed | delete the Deck normalization arm, run test_plan | test FAILS | M2 (Deck arm deleted from set_item_content) -> test RED; M2b (decode re-bound removed) -> test RED | PASS |
| C-004 | yes | `operator_view_reports_unknown_for_operator_owned_links_and_never_calls_them_healthy` fails RED when the host claims decks resolve | make `host_resolution` probe Some(true) for both libraries, run test_controller | test FAILS | M3 (host_resolution probes Some(true)) -> 2 tests RED incl. this one | PASS |
| C-005 | yes | `an_unresolvable_link_degrades_to_a_titled_slide_and_never_blanks_live` fails RED when the degraded slide loses its title text | make `item_slide`/`scripture_slide_in` return an EMPTY-title slide on the unresolvable path, run test_controller | test FAILS (if it PASSES the guard is vacuous for the "titled slide" half) | M4 (missing content renders NO text) -> this test stayed GREEN; only unrelated sibling `staged_scripture_composes_verse_text_and_survives_recovery` went red. Probe: empty-title deck item after Go Live = luminance 0.0404 vs a 1e-6 threshold. Bug 86ak84d15 | FAIL |
| C-006 | yes | `plan_summary_counts_the_run_sheet_and_keeps_missing_apart_from_unknown` fails RED when unknown is folded into resolved | change the summary match to drop the `Unknown` arm, run test_controller | test FAILS | M5 (Unknown folded into Resolved) -> test RED | PASS |
| C-007 | yes | Each of the 4 ticket scope items is classed PASS / FAIL / already-delivered with evidence | read PR diff against the ticket's 4 numbered scope items | 4 explicit verdicts | items 1a + 2 verified already on origin/main (`git show origin/main:.../protocol.rs` lines 204/211/570/574, rbac.rs 140-141); items 1b, 3, 4 delivered by this PR | PASS |
| C-008 | yes | The always-present `summary` object does not break the byte-pinned cross-language contract in production | read `protocol.dart` `fromJson`; confirm unknown-key tolerance; confirm host always emits `Some` | explicit verdict, either safe or a raised bug | `protocol.dart` OperatorStateView.fromJson reads keys individually with defaults, ignores unknown -> the always-present 176-byte `summary` object cannot break the Flutter client | PASS |
| C-009 | yes | The author's four named edge cases are each covered or reported as a gap | targeted reading + scratch probes | 4 explicit verdicts | live+staged, kind/field disagreement, persistence round-trip and empty/MAX_PLAN_ITEMS summary all probed; behaviour correct in every case, coverage gaps filed as 86ak84d1e | PASS |
| C-010 | yes | Every blocking finding has a reproducible ClickUp bug linked to 86ajy0hw0, and the review is posted on PR #13 | ClickUp MCP + `gh pr review` | bug IDs recorded and a PR review posted | bugs 86ak84d15 / 86ak84d17 / 86ak84d1e / 86ak84d1g; PR review posted | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-crate `cargo test` on the three changed suites; mutation
  battery C-002..C-006 run WITH siblings (never `--exact`), each mutation reverted via
  `git checkout --` before the next.
- Broader regression verification: `cargo test -p selahcue-data --features encryption
  --test test_plan_repo` (the persistence round-trip the diff touched); `cargo fmt --check`.
- Independent verifier: this QA pass IS the independent verification of Kenji's claims.
- Required environment: worktree at `6aee657`, isolated CARGO_TARGET_DIR, no `make ci`.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 .. C-009
- Hypothesis: the label and unknown-vs-resolved guards bite as claimed; the NFR-024 guard
  does NOT, because `live_is_black` tests `average_luminance() < 1e-6` while the classic
  theme paints a non-black background `rgb(8,10,20)` — so any composed slide passes,
  text or no text.
- Change or investigation: read the oracle, the theme, and the degradation path; then
  mutate and measure.
- Verifier executed: three per-crate `cargo test` suites; `cargo fmt --check`; `cargo clippy -D warnings`; a 7-mutation battery (M1, M2, M2b, M3, M4, M5, M7), each run with siblings and never `--exact`, each reverted with `git checkout --` before the next; six scratch probes in `selahcue-app` and one in `selahcue-data`, all deleted afterwards.
- Result: hypothesis CONFIRMED. Six of seven mutations produced the expected RED. M4 did not: making every unresolvable link render no text at all left `an_unresolvable_link_degrades_to_a_titled_slide_and_never_blanks_live` GREEN.
- New evidence: `Theme::dark()` is `Theme::classic()` with `background: Solid(rgb(8,10,20))`; an empty-title deck item measures 0.0404 average luminance after Go Live against a 1e-6 threshold, so the theme background alone satisfies the assertion. Blackout measures exactly 0.0, so a positive control IS available. Separately, all three deck-link writers in `dist/app.js` (lines 6734, 6751, 7650) omit `label`, so the label is never populated in production.
- Decision: gate-review — 1 blocking and 1 high finding returned to the implementation owner.

### Iteration 2 — not required

The predicate was computed in full after iteration 1. C-005 is FAIL and is owned by the
implementation role (Kenji), not by QA: fixing the test is remediation, not verification.
Returning `GATE_REVIEW` rather than iterating.

## Verdict

`GATE_REVIEW` — 9 of 10 mandatory criteria PASS. C-005 FAILS: the NFR-024 guard does not
detect the loss of the guarantee it names (86ak84d15, blocking). One further High finding
(86ak84d17) is not a code defect in the diff but makes the PR's stated design outcome
unreachable and its description inaccurate. The product behaviour in this PR is correct
throughout; both findings are about assurance and about claims, not about broken behaviour.

Findings raised: 86ak84d15 (High, blocking), 86ak84d17 (High), 86ak84d1e (Medium,
coverage), 86ak84d1g (Low).

Process note: the ticket requires "Author a Goal Contract before implementation". No
contract under `docs/delivery/goals/` references 86ajy0hw0 apart from this QA one.

## Risks and rollback

- Mutations are applied to the worktree and reverted with `git checkout --` immediately.
  No commit, no push, no change to the shared main checkout.
