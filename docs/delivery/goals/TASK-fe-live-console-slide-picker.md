# Goal Contract — TASK-fe-live-console-slide-picker

## Identity

- Goal ID: TASK-fe-live-console-slide-picker
- Parent goal ID: NONE (design: docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md §1–§4; backend: [[TASK-be-live-console-slide-bridge]])
- Title: Live Console tabbed Content panel (Scriptures | Slides) + presentation slide-picker filmstrip
- Role: frontend-engineer
- Status: GATE_REVIEW (all mandatory criteria PASS; awaiting independent review + owner gate)
- Execution engine: goal
- ClickUp task: NONE (to link/create under Presentation & Slides epic 86ajp07ce)
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 8
- Independent verification required: yes

## Objective

In the operator webview console, wrap the center `#scriptures` panel in a 2-tab Content panel and add a
`Slides` filmstrip that lists a staged presentation's slides, renders thumbnails, stages a slide to Preview,
and auto-switches on plan selection — reusing the shipped right-tabs + presentation-grid patterns.

## Baseline

Verified in `crates/selahcue-operator/dist/`:
- The center zone holds `#scriptures` (search + hits + chapter nav + verse list). The right column already
  ships a 2-tab pattern (`wireRightTabs`, `role="tablist"`, roving tabindex, ←/→, `aria-controls`).
- `render(view)` (app.js:7) is the central view-apply; `blitFrame(cv, frame)` blits RGBA; `act(fn)` runs a
  command then re-renders; `goLive = () => act(() => invoke("go_live"))`.
- The presentation editor grid (`pmGrid`, app.js ~5686+) already implements a filmstrip: bounded LRU thumb
  cache (`PM_THUMB_MAX=60`), `IntersectionObserver` lazy render, `role="option"` tiles + roving tabindex,
  honest "no audience output" state — all WKWebView-tested. It is workspace-bound (`render_deck_slide`,
  `deck_*`); the console filmstrip mirrors it but wires the NEW plan/console commands.
- Backend Phase 1 (Dep 1) is in place: `plan_deck_slides({deckId})`, `render_plan_deck_slide({deckId,
  slideId,maxW,maxH})`, `select_slide({itemId,slideIndex})` (Tauri camelCases snake_case params).
- `ItemView` exposes `kind`, `link{kind,id}`, `slide_index`, `slide_count` — enough to detect a staged
  presentation and its deck id with no extra round-trip.

## Inputs and evidence sources

- docs/design/LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md §1 (anatomy), §2 (states), §4 (keyboard/a11y)
- dist/index.html (right-tabs pattern 217+, #scriptures 194+), dist/app.js (render 7, wireRightTabs 4011,
  pmGrid 5686+, blitFrame 353, act 2913), dist/app.css (right-tabs + pm-tile styles)
- scripts/operator_headless.py (the webview behavioural gate; window.__TAURI__ stub + `ok()` assertions)

## Scope

### In scope

- 2-tab Content panel (`Scriptures | Slides`) wrapping `#scriptures`; Slides disabled until a presentation is
  staged; tablist a11y (roving tabindex, ←/→, aria-selected/-controls) mirroring `wireRightTabs`.
- Filmstrip: list via `plan_deck_slides`; lazy bounded thumbnails via `render_plan_deck_slide`; PREVIEW/LIVE
  text markers (never colour-only); empty-deck / missing-deck / no-output honest states.
- Stage a slide to Preview on click via `select_slide`; Enter = stage-then-`go_live` the focused slide.
- Auto-switch to Slides when a presentation is staged (without stealing focus); back to Scriptures otherwise.
- Filmstrip keyboard: `role="listbox"`, ←/→ move+stage, Enter=go-live, Home/End; `stopPropagation` so the
  global ← Space ⏎ console shortcuts don't double-fire.

### Non-goals

- Dep 2 audience routing; Dep 3 inline editing.
- Any backend change (the three commands already exist).

### Constraints

- FR-012: staging never touches Live; only Go Live does. FR-115: operator-confirmed.
- Bounded memory: reuse the `PM_THUMB_MAX`-style LRU thumb cache; no unbounded growth.
- WKWebView traps: assert COMPUTED display (a class `display` rule can defeat `hidden`); no grid implicit
  auto-row overflow past the console footer (prefer the horizontal filmstrip row).
- Live tree holds ~5k lines of unrelated WIP in index.html/app.js/app.css — additive hunks, staged as mine.

### Assumptions and unknowns

- ASSUMED: the console's Preview/Live panels + `output_connected` already carry the honest "no audience
  output" story; the filmstrip's LIVE marker reflects the plan live cursor (Dep 2 routes the real pixels).
  Validation owner: QA + owner review.

## Dependencies and approvals

- Backend Dep 1 ([[TASK-be-live-console-slide-bridge]]) — status: GATE_REVIEW (commands present in tree).
- Independent review (code-reviewer) + QA — status: PENDING (returns GATE_REVIEW).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Content panel renders 2 tabs; Scriptures active by default; Slides tab disabled + its panel hidden (computed display) when no presentation is staged | `python3 scripts/operator_headless.py` (added assertions) | assertions PASS | headless output | PASS |
| C-002 | yes | Staging a presentation plan item auto-switches to Slides and lists its slides (`plan_deck_slides`) as `role=option` cards; staging a scripture returns to Scriptures | `python3 scripts/operator_headless.py` | assertions PASS | headless output | PASS |
| C-003 | yes | Clicking a slide invokes `select_slide` (Preview only); Enter stages then `go_live`; no direct Live mutation on click (FR-012) | `python3 scripts/operator_headless.py` (`__calls` spy) | assertions PASS | headless output | PASS |
| C-004 | yes | Thumbnails render via `render_plan_deck_slide`, lazily (IntersectionObserver) into a bounded cache | code review + headless (canvas has-render) | bounded + lazy | app.js diff + headless | PASS |
| C-005 | yes | Filmstrip is a `role=listbox`; ←/→ move+stage, Enter go-live, Home/End; keydown `stopPropagation` | `python3 scripts/operator_headless.py` (key dispatch) | assertions PASS | headless output | PASS |
| C-006 | yes | PREVIEW/LIVE + missing/empty states carry non-colour text; Slides count badge reflects slide_count | headless + review | PASS | headless output | PASS |
| C-007 | yes | Operator crate still compiles (dist is embedded) | `cargo check --manifest-path crates/selahcue-operator/Cargo.toml` | no errors | build output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: extend `scripts/operator_headless.py` with `plan_deck_slides`/`render_plan_deck_slide`/
  `select_slide` stubs + a presentation plan item, and assertions for C-001..C-006.
- Broader regression verification: the full headless gate must stay green (no existing assertion breaks);
  `make ci` before any push.
- Independent verifier: code-reviewer + qa-engineer; owner design review for visual parity (Figma frames are
  a tracked follow-up).
- Required environment: headless Chrome (the gate) + desktop Rust toolchain.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-007
- Hypothesis: mirroring `wireRightTabs` (tabs) + `pmGrid` (filmstrip) wired to the new plan/console commands,
  plus a `syncSlides(view)` hook in `render()`, satisfies the predicate with no backend change.
- Change or investigation: traced render/act/blitFrame/pmGrid/wireRightTabs + the headless stub model.
- Verifier executed: `scripts/operator_headless.py` (extended with plan_deck_slides/render_plan_deck_slide/
  select_slide stubs + a presentation plan item + 20 slide-picker assertions); `cargo check` (operator).
- Result: all mandatory C-001..C-007 PASS. Headless gate stable across 3 runs: **537 checks, 0 FAIL**,
  exit 0 (raised `--virtual-time-budget` 6000→9000 + `EXPECTED_MIN_CHECKS` 517→537 for the added scenario).
  Operator crate compiles clean.
- New evidence: `wireRightTabs` + `pmGrid` patterns transplanted cleanly; the existing 517-check gate stayed
  green (the `#scriptures` wrap broke nothing); WKWebView `[hidden]` trap covered by computed-display asserts.
- Decision: gate-review

## Risks and rollback

- Risks: (a) additive edits to WIP-heavy dist files could overlap the owner's WIP — mitigated by isolated,
  appended hunks; (b) a class `display` rule defeating `hidden` (WKWebView) — mitigated by computed-display
  assertions; (c) grid overflow past the footer — mitigated by a horizontal filmstrip.
- Rollback: all additive; revert the specific hunks. No backend/data change.

## Pause and escalation conditions

- A visual-design decision beyond the spec (exact spacing/type) → note as a Figma follow-up, don't invent.
- ClickUp unavailable → pending update, no shadow backlog.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-fe-live-console-slide-picker.md`
- Validator result: PASS (structural + `--require-complete`).
- Independent verification result: PENDING — owner review, then code-reviewer/qa-engineer.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: none (all mandatory PASS).
- ClickUp final evidence comment: to post once the Presentation & Slides story is linked (epic 86ajp07ce).
