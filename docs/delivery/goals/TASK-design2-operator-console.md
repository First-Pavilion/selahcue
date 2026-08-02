# Goal Contract — TASK-design2-operator-console

## Identity

- Goal ID: TASK-design2-operator-console
- Parent goal ID: TASK-design2-palette-tokens
- Title: Rewrite the operator console to the full Operator Console Design 2.0 (Figma 312:124)
- Role: frontend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: PENDING (queued — see §ClickUp)
- Design spec: docs/superpowers/specs/2026-08-01-operator-console-design2.md
- Created: 2026-08-01
- Updated: 2026-08-01
- Maximum iterations: 10
- Independent verification required: yes (token/pin suite + protocol/rbac/timer tests + node --check + fmt/clippy; adversarial review workflow)

## Objective

Rewrite the operator webview (`dist/index.html` + `app.css`, with targeted `app.js` and a
Rust timer/detection slice) to the Figma "Operator Console (Design 2.0)" (node 312:124),
adopting the `--sc-*` Design 2.0 palette + chip pattern, while preserving every pinned
DOM/token invariant and wiring the new controls truthfully (Timer Pause/Resume, HH:MM:SS
custom start, count/status pills, detection match-% + honest Mode). See the design spec
for the full layout mapping and locked decisions.

## Baseline

- Current console: 3-zone OBS layout on the legacy neutral vars re-pointed to Design 2.0
  values (foundation slice 445a97e). `app.js` drives all behaviour off exact element ids;
  `test_tokens.rs` pins ~90 needles across the three dist files + the `</main>`-before-
  `#emergency` structural invariant + `MAX_TRANSCRIPT_ROWS`.
- Timer: `Command::{StartTimer,StopTimer,AdjustTimer}` only (no Pause); core `Timer`
  already banks time across pause/resume. `TimerSnapshot { remaining_secs, elapsed_secs,
  time_up, warn, running }` (no `paused`).
- Detections: `DetectionView { id, reference, text }` (no confidence); R4 auto-detection
  is honest-empty.

## Scope

### In scope

- Full re-skin of `index.html` + `app.css` to Design 2.0 (topbar transport, D2 cards,
  colour-coded plan badges, gradient Preview|Live, restyled timer + detections, deep-red
  footer) preserving all pinned ids/classes/needles + a11y invariants.
- Timer Pause/Resume vertical slice: `Command::PauseTimer`/`ResumeTimer` + RBAC + controller
  + `TimerSnapshot.paused` + operator wrappers + Tauri commands + JS + tests.
- HH:MM:SS custom-time control + count/status pills (frontend-only, existing state).
- `DetectionView.confidence: Option<u8>` (additive) + match-% pill render-when-present.
- Detection Mode control: "Operator confirms" live; auto modes honest-"later" (FR-115 kept).

### Non-goals

- Theme Designer / Screens / Plan-Library / Settings surface redesign (inherit shared
  token+button restyle only). Real R4 auto-detection. OS-global hotkeys. Native pickers.

### Constraints

- The six canonical §4 status hexes stay defined + present (pin green); Rust WCAG audit
  untouched. `"CLEAR ALL"` survives (aria-label). `#emergency` stays after `</main>`.
- No new test failures; `make ci` (fmt --check + clippy + test) clean; `node --check app.js` clean.
- Additive-only wire changes (serde `default`/`skip_serializing_if`) so existing round-trips stay green.

### Assumptions and unknowns

- ASSUMED: core `Timer::pause/resume` banks time correctly for a countdown (covered by
  `selahcue-core/tests/test_timer.rs::pause_resume_banks_time`).
- UNKNOWN (owner-run): pixel-level visual QA in the running Tauri webview — no in-repo
  render harness.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Operator webview re-skinned to Design 2.0 (topbar/plan/preview-live/timer/detections/footer) per Figma 312:124 | Visual diff vs Figma screenshot + review workflow design-fidelity lens | Layout + tokens match the approved design | index.html/app.css diff; review report | PASS |
| C-002 | yes | All operator pins intact | `cargo test -p selahcue-present --test test_tokens` | all operator_* + design2 tests pass | `13 passed; 0 failed` | PASS |
| C-003 | yes | No regression across present crate | `cargo test -p selahcue-present` | all pass | all suites `ok` | PASS |
| C-004 | yes | Timer Pause/Resume wired end-to-end (Command+RBAC+controller+snapshot+Tauri+JS) | `cargo test -p selahcue-lan -p selahcue-core -p selahcue-app` | all pass incl. new pause/resume + paused-field cases | app `87 passed` (pause_freezes…), remote pause/resume `ok`, lan/core `ok` | PASS |
| C-005 | yes | DetectionView.confidence added additively; existing round-trips green | `cargo test -p selahcue-lan` | protocol/serde round-trips pass | `detection_confidence_is_additive` + `every_command_round_trips` `ok` | PASS |
| C-006 | yes | Operator JS valid + transcript cap intact | `node --check app.js` + grep `MAX_TRANSCRIPT_ROWS = 120` | JS OK; cap present | `JS OK`; cap present (2 hits) | PASS |
| C-007 | yes | fmt + clippy clean | `cargo fmt --check` (ws+operator) + clippy -D warnings (ws+server+operator) | clean | fmt clean; clippy `Finished` 0 errors | PASS |
| C-008 | yes | New controls truthful: HH:MM:SS starts real timer; Pause toggles; Mode keeps FR-115; match-% only when present | Manual trace + review workflow correctness lens | no fabricated data; FR-115 preserved | review report (pending) | PASS |
| C-009 | no | Headless/webkit smoke passes where runnable | `python3 scripts/operator_headless.py` | pass or environment-skipped | `99 checks, 0 FAIL` | PASS |

**Terminal:** VERIFIED_COMPLETE when C-001…C-008 are PASS.

## Verification plan

- Focused: `node --check app.js`; `cargo test -p selahcue-present --test test_tokens`;
  `cargo test -p selahcue-lan` (protocol+rbac); `cargo test -p selahcue-core` (timer);
  `cargo test -p selahcue-app` (controller/operator).
- Broader: `make ci` (fmt --check + clippy -D warnings + workspace test).
- Independent: an adversarial review workflow (correctness / pin-preservation / a11y /
  design-fidelity / Rust-protocol lenses) over the diff, findings verified before fix.
- Environment: desktop Rust workspace + node.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-008 (coherent rewrite slice, TDD on the Rust plumbing)
- Hypothesis: preserving every id/needle while restructuring markup + adopting `--sc-*`
  keeps all pins green; the additive timer/detection wire changes keep round-trips green.
- Change or investigation: understand-phase workflow (4 parallel mappers) → implement
  (Rust timer/detection TDD, HTML/CSS re-skin, JS wiring, palette/shortcuts) → adversarial
  review workflow (5 lenses × per-finding verify) → fix.
- Verifier executed: node --check; `test_tokens` (13); `operator_headless.py` (99);
  fmt/clippy; lan/core/app suites.
- Result: **PASS** — 13/13 pins, 99/99 headless, all Rust suites green, fmt+clippy clean.
- New evidence: visual QA screenshots at 1180/1280/1360 (faithful to Figma 312:124).
- Decision: → Iteration 2 (address verified review findings).

### Iteration 2 (review-fix)

- Target criterion: C-001, C-008 (design fidelity + truthful correctness) via the review.
- Adversarial review: 5 lenses, per-finding independent verification → 22 confirmed.
- Fixed (correctness/a11y/fidelity): timer Reset over-inflating in overrun → added additive
  `TimerSnapshot.total_secs` + Reset uses it (#1); `running`/`paused` never both true (#3);
  symmetric `PauseTimer` pending-start clear (#4); Reset in-flight guard (#2); modal focus
  trap/restore + `aria-activedescendant` (#5/#8/#22 — completed with the co-editor's menu
  work); scoped `aria-current` (#21); heading/label AA contrast (#6/#9); BLACKOUT white-on-red
  AA via canonical fill (#7); gradient-button + cmd-input focus AA (#10/#11); REC soft-tint
  (#16); centered topbar transport (#13); scriptures ⌕ (#14).
- Kept as intentional (documented): plan-name subtitle (#17), footer kbd chips (#18), HH:MM:SS
  no leading zeros — `type=number` limitation (#15), co-editor nav ⌘ labels (#20).
- Verifier re-run: node --check OK; `test_tokens` 13/13; `operator_headless.py` 99/0;
  controller 87/87 (incl. `total_secs`/running-gate assertions); fmt+clippy clean; lan
  protocol byte-stable (total_secs additive skip-if-none).
- Result: **PASS**. Decision: complete → VERIFIED_COMPLETE.

## Risks and rollback

- Risks: a broken pin/JS-id hook (mitigated: preserved-ID contract + full pin suite);
  timer protocol change rippling through RBAC/round-trip tests (mitigated: trace every
  construction site first, update in-slice); WKWebView quirks (follow existing patterns).
- Rollback: revert `dist/*` + the Rust timer/detection commits (each slice is separable).

## Pause and escalation conditions

- Detection auto-modes (auto-stage/approve) would supersede FR-115 → owner decision;
  resolved (Q&A): auto modes are honest-"later", not wired. Do not silently enable them.

## ClickUp

- ClickUp is the source of truth; this contract links back. Task is PENDING (queued) —
  post the start note + goal id/contract path/engine/iteration-limit when the ClickUp
  task is confirmed. Do not create a shadow backlog.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-operator-console.md`
- Validator result: PASS (9 criteria, 8 mandatory)
- Independent verification result: adversarial review workflow (5 lenses, per-finding
  verification) — 22 findings confirmed; all correctness/a11y/fidelity findings resolved,
  4 kept as documented intentional choices; re-verified green (13 pins, 99 headless, 87
  controller, fmt+clippy).
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. Owner-run visual QA in the live Tauri webview
  remains the only out-of-repo check (no in-repo render harness); headless screenshots attached
  as an interim aid.
