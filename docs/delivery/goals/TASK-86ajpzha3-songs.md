# Goal Contract — TASK-86ajpzha3-songs

## Identity

- Goal ID: TASK-86ajpzha3-songs
- Parent goal ID: STAGE8-core-presentation
- Title: Song plan items are multi-slide (stanza-structured), navigated slide-by-slide within the item, truthful on the wire, recoverable mid-song, and importable from plain text
- Role: backend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpzha3
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Turn one-slide plan items into real songs: stanza-structured content persisted with the plan, Next/Previous advancing within the song before crossing items, the stage output's current/next line following the slide sequence, an additive wire slide count, and mid-song recovery.

## Baseline

Verified: PlanItem = id + kind + title only (no content); the controller stages exactly one composed Slide per item (`stage_index`), Next/Previous move BETWEEN items (`plan_cursor`); the stage view derives current/next from the single slide's lines; session snapshots persist indices/scripture/timer but no intra-item position; plan_repo schema at v5; PlanItemView carries id/kind/title/is_live/is_staged (fixtures pinned). Exact insertion points being mapped by `wf_247548a0-429`.

## Inputs and evidence sources

- Story 86ajpzha3 (S8-1) + epic 86ajp07ce (FR-009/010/019/020); the map workflow; ADR-0007 (persistence), the pinned wire fixtures.

## Scope

### In scope

- Song content model (ordered stanzas → slides) in `selahcue-core`, persisted via a plan_repo migration (v6) with safe backfill (existing items = no content, unchanged behaviour).
- Controller: in-item slide navigation (Next/Previous advance the slide first, then the item), staging composes the CURRENT slide, GoLive commits it; slide position in the operator view; mid-song position in the session snapshot + recovery.
- Stage output: current/next line from the slide sequence (next slide's first line when at a slide boundary).
- Wire: additive `slide_count`/`slide_index` on PlanItemView (skip-if-none; pinned fixtures byte-identical); console + mobile display "Song · N slides" truthfully (display-only change).
- Plain-text stanza import (blank-line-separated) as a parser + a console path to create a song with content.

### Non-goals

- Themes, editor UI (S8-3/4), CCLI footer (S8-5), verse/chorus REPEAT ordering semantics (a labelled stanza is enough this batch), media.

### Constraints

- FR-012 preview→live safety unchanged; NFR-024; no-unbounded-growth; additive wire only (fixtures preserved); migration safe for existing stores (v5→v6 with intact data); recovery honesty (never restore a position that doesn't exist).

### Assumptions and unknowns

- ASSUMED: slide-per-stanza (no per-slide line cap splitting this batch — the 6-line compose cap truncates long stanzas as it does today; pagination is a tracked stage item). VALIDATION: review.

## Dependencies and approvals

- None blocking (S8-1 is the stage's first batch).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Song model: stanza-structured content on plan items, persisted via migration v6; existing stores upgrade losslessly; plain-text import parses blank-line-separated stanzas (bounded) | `cargo test -p selahcue-core -p selahcue-data` | model + migration + import tests pass | plan.rs (Stanza/slide_count/stanzas_from_text); plan_repo.rs (content col); migrations.rs v6 — 4 core + 3 data tests | PASS |
| C-002 | yes | In-item navigation: Next/Previous advance slide-by-slide within a song, then cross items; staging composes the current slide; GoLive commits it; a 6-stanza song walks end-to-end | controller tests | navigation tests pass incl. boundaries | test_controller.rs (next/prev in-song, 6-stanza walk, add-with-content) | PASS |
| C-003 | yes | Stage output shows current/next line from the slide sequence (incl. next-slide first line at boundaries) | stage next-slide test | `stage_next_slide()` accessor test passes | test_controller.rs the_stage_next_line_follows_the_song_sequence | PASS |
| C-004 | yes | Wire: slide_count/slide_index additive on PlanItemView; pinned fixtures byte-identical; console + mobile show "Song · N slides"; round-trips | protocol tests both sides | fixtures unchanged + new fields covered | test_protocol.rs (+3, fixtures green); protocol_test.dart (+2) | PASS |
| C-005 | yes | Mid-song position survives force-kill recovery (snapshot + restore; never restores an out-of-range slide) | recovery tests | recovery tests pass | test_controller.rs (mid-song recovery, out-of-range clamp, removed-live-song body recovery) | PASS |
| C-006 | yes | Full verification: workspace + Flutter suites green, clippy/fmt clean, CI green; independent adversarial review, confirmed findings fixed | make-ci equivalents + Workflow review | all green; review record | CI run 30156606042 green; review wf_bee2e975-576 (1 confirmed → fixed); CODE-REVIEW-batch8a.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-criterion test suites above. Broader: full workspace + Flutter + fmt/clippy (the pre-push CI gate per memory). Independent: adversarial Workflow review (navigation semantics, migration safety, wire compat, recovery honesty lenses).
- Required environment: local + 3-OS CI.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: stanza content as a new nullable column (JSON or delimited text) on plan_items with v6 migration keeps existing rows untouched and round-trips.
- Change or investigation: awaiting the map (`wf_247548a0-429`); then implement model + migration + import.
- Verifier executed: full workspace + Flutter suites, fmt/clippy, CI run 30156606042 (11 jobs green), review `wf_bee2e975-576`.
- Result: **C-001..C-006 PASS.** Song model + v6 migration (NULL backfill) + in-song navigation both directions + stage next-stanza + additive wire (fixtures byte-identical) + mid-song recovery, all tested (+22 Rust, +2 Dart). CI green.
- New evidence: adversarial review raised **1 confirmed medium** — a regression: removing a LIVE song then crashing recovered only the title (the free-slide capture stored `slide.title`, lossless pre-8a when live slides were title-only, but songs now carry a body). **Fixed**: capture + persist the free-slide body (`live_free_body`, migration **v7**), restore `Slide::new(title, body)` verbatim; regression test added. Re-verified green.
- Decision: gate-review (all mandatory criteria PASS)

## Risks and rollback

- Risks: navigation semantics regressions (Next means more than before — every existing test touching Next must stay truthful); migration on real stores. Rollback: git; migration additive (new column), old binaries ignore it.

## Pause and escalation conditions

- Any wire fixture break → stop (additive-only rule).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpzha3-songs.md --require-complete`
- Validator result: PASS (6/6 mandatory)
- Independent verification result: review wf_bee2e975-576 — 1 confirmed → fixed + re-verified
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajpzha3
