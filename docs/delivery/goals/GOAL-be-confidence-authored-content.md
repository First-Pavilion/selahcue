# Goal Contract — GOAL-be-confidence-authored-content

## Identity

- Goal ID: GOAL-be-confidence-authored-content
- Parent goal ID: 86ajp07k1 (EPIC — Outputs & Displays)
- Title: The Stage/Confidence monitor shows the LIVE authored deck slide's own text + speaker notes, shrunk-to-fit like a scripture verse — never blank, never clipped
- Role: backend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajp0aa4 (STORY — Stage / confidence display output; bug logged as a comment/child)
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 8
- Independent verification required: yes

## Objective

When an operator presents an authored **Presentation & Media** deck slide (Design 2.0 node 329:124), the audience output shows the slide but the **Stage/Confidence** monitor goes blank, and — once wired — long slide text clips off the frame. Deliver the desktop-side backend so the confidence monitor renders a speaker-readable projection of the LIVE authored slide (its own visible text boxes, in reading order, plus the speaker notes) through the existing shrink-to-fit template band, so the whole content shows, scaled to fit, never clipped — with no change to the plain plan/scripture/song confidence path or to audience output.

## Baseline

Verified from a two-agent backend investigation + direct source reading this session:

- **The confidence/stage monitor is fed only from `Presenter::live_slide()`** — a plain title+body [`Slide`]. Controller `tick()` sources `current = self.presenter.live_slide().cloned()` (`selahcue-app/src/controller.rs:1709,1716`) → `StageDisplay::update` → `compose_stage` → per-template composer.
- **Authored deck slides deliberately clear `live_slide`.** `Presenter::present_authored` sets `live_slide = None; live_authored = Some(slide)` (`selahcue-present/src/present.rs:176-178`); `live_slide()` then returns `None` (`present.rs:431`). So while an authored slide is Live the monitor's `current` is `None` and it renders an EMPTY content region. No code converts `live_authored` into a confidence `Slide`. The existing test `present_authored_slide_puts_a_deck_slide_on_live_and_takes_over` (`test_controller.rs:1571`) locks in `live_slide().is_none()`.
- **This is unbuilt intended behaviour, not a design choice.** The `AuthoredSlide::notes` doc comment (`deck.rs:94-95`) already states notes are "shown on the stage/confidence monitor, never on the audience output."
- **The plain plan/scripture/song path works** (via `go_live` → `live_slide = Some`), and IS confidence-tested (`test_controller.rs:265-330,528-553,1252-1373`).
- **Stage text fitting is asymmetric.** Both the worship lyric band and the scripture verse band use `fit_lines` → `autofit_layers(..., Fit::ShrinkToFit, ...)` (binary-search the largest cell that fits width+height, down to 1px — `compose.rs:145-164`), so long BODY text shrinks. But the worship **title pill** and scripture **reference** use `line()` (`stage.rs:305`) — a fixed-`px` single-line `Layer::Text`. The pill's box is SIZED to its text (`stage.rs:483-486`), so a long title runs off the frame's right edge where `draw_text` clips it (`raster.rs:1033-1052`, "never wraps … clipped to the on-screen intersection").
- **Owner decisions this session** (AskUserQuestion): scenario = presenting authored deck slides; confidence content = slide text + speaker notes; follow-up = text must shrink-to-fit like scriptures (not clip).

## Inputs and evidence sources

- Backend investigation (two Explore agents + direct reads): `present.rs`, `deck.rs`, `slide.rs`, `theme.rs`, `stage.rs`, `compose.rs`, `raster.rs`, `controller.rs`, `main.rs`.
- ClickUp: STORY — Stage / confidence display output `86ajp0aa4`; STORY — Stage/confidence themes `86ajxf3bx` (QA); EPIC — Outputs & Displays `86ajp07k1`; BUILD CONTROL `86ajnx548`.
- Design: FR-037 (speaker/confidence view); stage template frames Figma 373-375, behaviour spec 375-139; Presentation & Media node 329:124.
- Owner answers via AskUserQuestion (scenario + desired confidence content + shrink-to-fit directive).

## Scope

### In scope

- **`AuthoredSlide::confidence_slide(&self) -> Slide`** (`selahcue-present/src/deck.rs`): a pure projection — visible `Element::Text` boxes in reading order (top-y, then left-x, then z), blank lines dropped, hidden/shape/image elements ignored, speaker notes appended; ALL of it into `body` with an empty `title` so it renders through the shrink-to-fit band (not the clipping fixed header). Bounded by the slide's own element/notes caps (no-leak).
- **`Presenter::confidence_slide(&self) -> Option<Slide>`** (`selahcue-present/src/present.rs`): returns the plain `live_slide` as-is, else the projection of `live_authored`, else `None`.
- **Controller wiring** (`selahcue-app/src/controller.rs`): the stage-refresh feed uses `confidence_slide()` in place of `live_slide().cloned()` (both refresh sites). No other use of `live_slide()` changes.
- **Tests** (public-API, existing fixture patterns): projection reading-order/notes/hidden/blank/textless (deck); plain-vs-authored + nothing-live (present); end-to-end confidence-not-blank + pixel-reaches-surface (controller); render-level no-clip / shrink-to-fit + no-word-dropped (stage).

### Non-goals

- Changing the plain plan/scripture/song confidence path, or any audience/secondary-screen output.
- Changing shared stage rendering (`line()`, the worship pill, scripture reference, `fit_lines`) — the scripture verse already shrinks correctly and must stay byte-identical.
- The confidence monitor's **"next"** slide for authored deck playback (still `presenter.staged()`); deck-aware "next" is a tracked follow-up.
- A dedicated authored/notes confidence TEMPLATE with a distinct notes band (text + notes currently share the shrink-to-fit body); a later design refinement.
- Committing/merging — the working tree holds concurrent WIP; leave the commit decision to the owner.

### Constraints

- `selahcue-present` is pure/deterministic, no I/O; workspace lint `clippy::unwrap_used = warn` (no `.unwrap()` in the new code).
- No unbounded growth: the projection is a transient transform of already-capped inputs (`MAX_ELEMENTS`, `MAX_TEXT_ELEMENT_LEN`, `MAX_NOTES_LEN`).
- LAN wire fixtures / `OperatorStateView` untouched (byte-stable).

### Assumptions and unknowns

- ASSUMED: the operator's active stage template while presenting a deck is Worship (default) — the fix is template-agnostic (empty title works across Worship/Scripture/Timer-only), so this does not gate correctness. Owner-validated by the shrink-to-fit directive.

## Dependencies and approvals

- Owner scope/behaviour decisions: RESOLVED this session (AskUserQuestion).
- No external service / infra dependency.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | An authored slide projects visible text (reading order) + notes into `body`, empty `title`; hidden/blank/textless handled | `cargo test -p selahcue-present --test test_deck confidence_slide` | 3 confidence tests pass | test_deck.rs:290-343 | PASS |
| C-002 | yes | `Presenter::confidence_slide` returns the plain live slide, else the authored projection, else None | `cargo test -p selahcue-present --test test_present confidence_slide` | both tests pass | test_present.rs | PASS |
| C-003 | yes | Presenting an authored slide feeds text to the confidence monitor (not blank) and pixels reach the surface | `cargo test -p selahcue-app --features server --test test_controller confidence_monitor_shows_the_live_authored_slide_text` | passes | test_controller.rs | PASS |
| C-004 | yes | Long authored slide text shrinks-to-fit the stage, stays on-frame, drops no word (no clip) | `cargo test -p selahcue-present --test test_stage authored_slide_text_shrinks_to_fit_the_stage_never_clips` | passes; failed on old impl with "runs off the 960px frame" | test_stage.rs | PASS |
| C-005 | yes | No regression in the plain confidence path, stage templates, or any crate | `cargo test --workspace` and `cargo test -p selahcue-app --features server` | all suites pass | gate output bkshrqvfn | PASS |
| C-006 | yes | Lint + format gates clean | `cargo fmt --check` and `cargo clippy --workspace --all-targets -- -D warnings` (+ app `server`) | no diff, no warnings | gate output | PASS |
| C-007 | yes | New buffering is bounded (no-leak) | review | projection is a transient transform of `MAX_ELEMENTS`/`MAX_TEXT_ELEMENT_LEN`/`MAX_NOTES_LEN`-capped inputs; no persistent buffer | deck.rs confidence_slide | PASS |
| C-008 | yes | Independent review (code + performance + security) of the diff | 3 independent reviewer passes + owner QA | reviews pass; owner confirms on a real second display | code/perf/security PASS (ClickUp 86ajy4czf); owner QA PASSED | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the four new test groups (deck projection, present confidence_slide, controller end-to-end, stage no-clip). Each was watched to FAIL first (RED) — the stage test reproduced the owner's clip ("runs off the 960px frame (x=67, w=1100)") — then pass after the fix (GREEN).
- Broader regression verification: `cargo test --workspace`, `cargo test -p selahcue-app --features server`; `cargo fmt --check`; `cargo clippy --workspace --all-targets -D warnings` + app `server`.
- Independent verifier: /code-reviewer on the diff; owner QA on a real Stage/confidence display (present a deck slide with a long line + notes; confirm the whole text shows, shrunk, on-screen).
- Required environment: desktop Rust workspace (`implementation/desktop`); a second display for the physical stage output during owner QA.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004 (confidence shows authored content; text shrinks-to-fit).
- Hypothesis: the confidence feed reads only `live_slide()`, which is `None` for authored slides; and routing text into a fixed-header title clips it.
- Change or investigation: added `AuthoredSlide::confidence_slide` (text→body, empty title) + `Presenter::confidence_slide`; wired both controller stage-refresh sites; added deck/present/controller/stage tests.
- Verifier executed: the four test groups (RED → GREEN); the stage no-clip test reproduced the clip before the fix.
- Result: all focused tests PASS.
- New evidence: stage test failure on old impl proved the exact clip; GREEN after routing text through the shrink-to-fit body.
- Decision: gate-review (run full CI, then handoff to review/QA).

## Risks and rollback

- Risks: an authored slide with a very large notes blob renders very small (shrunk) — acceptable (zero content loss, matches scripture-verse behaviour); a dedicated notes band is a tracked follow-up. Confidence "next" is not deck-aware yet (tracked).
- Rollback or recovery: the change is additive and localized (two new pure methods + a two-line controller feed swap); revert the three source hunks to restore prior behaviour with no data/migration impact.

## Pause and escalation conditions

- Any request to change the plain plan/scripture path, shared stage rendering, or audience output → escalate (out of scope; owner/design decision).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-be-confidence-authored-content.md`
- Validator result: PASS (8 criteria, 8 mandatory).
- Test evidence: `selahcue-present` all suites 0 failed (test_deck 15, test_present 28, test_stage 28, + others); `selahcue-app --features server` 0 failed (test_controller 111, + others); clippy `-D warnings` (workspace + app `server`) clean; `cargo fmt --check` clean.
- Independent verification result: PASS — code/performance/security review PASS; owner QA PASSED on a real second display.
- Terminal state: VERIFIED_COMPLETE (committed `37f3bb8`, pushed to origin/main).
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: BUG 86ajy4czf — repro/root-cause/fix/QA + review verdict + commit `37f3bb8` + push logged.
