# Goal Contract — TASK-86ajpztgr-console-obs-layout

## Identity

- Goal ID: TASK-86ajpztgr-console-obs-layout
- Parent goal ID: STAGE8-core-presentation
- Title: The operator console (Tauri webview) renders the OBS-studio layout from Figma 165:124, preserving every wired behaviour and pinned invariant, with forward-looking (honest-empty) transcript + detections panels
- Role: frontend-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpztgr
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Restructure `crates/selahcue-operator/dist/index.html` into the approved OBS-studio layout (Figma node 165:124) — LEFT Service Plan + Live Transcript · CENTER OBS Preview|Live + GO LIVE + Scriptures · RIGHT Timer + Recent Detections + Outputs · emergency footer — without regressing any wired control or pinned test.

## Baseline

Verified: the shipped console (`dist/index.html`, ~1240 lines) is fully functional — plan editing, scripture (translation/search/chapter/verse-list/double-click-live), Preview/Live + GO LIVE, timer, outputs, Identify, the emergency keymap + modal-pierce chords, all in the single `<script>`. 44 element ids are wired by `getElementById`. Pinned tests: `test_keymap.rs` (keymap JS logic, capture-phase, chords-before-input-bailout) + `test_tokens.rs` (`id="emergency"`, `#clear-all.armed .key`, `id="preview-panel"/"live-panel"/"translation"/"verse-list"`). The GPU parity oracle is unaffected (this is webview HTML/CSS, not the wgpu path).

## Inputs and evidence sources

- Story 86ajpztgr + epic 86ajp07ce; Figma 165:124 (design context + screenshot); the current index.html; test_keymap.rs; test_tokens.rs.

## Scope

### In scope

- Rewrite the `<style>` layout + the `<main>` container arrangement (and header/footer as needed) into the 3-zone OBS grid, keeping ALL 44 element ids and the ENTIRE `<script>` untouched (elements move containers; ids and JS wiring stay).
- Move the GO LIVE transport + Preview/Live panels into the CENTER OBS row; Scriptures below them; Timer + Outputs into the RIGHT column.
- Add two forward-looking panels — **Live Transcript** (left, under the plan) + **Recent Detections** (right) — as UI shells with honest empty states (labelled "on-device transcription — arrives with R3" / "auto-detected scriptures — arrives with R4"); no fabricated data.
- Update the pinned tests to the new DOM only where structure moved, keeping the SAME guarantees; add a test pinning the two new panels + their honest empty state.

### Non-goals

- The R3/R4 backends that feed the panels; any change to the wire protocol, the controller, or the GPU compositor; restyling the design-system tokens.

### Constraints

- Every wired control keeps working (regression); the canonical keymap + modal-pierce chords preserved exactly (test-pinned); emergency footer always-on; no fabricated transcript/detection data (honest empty states); CRLF-safe (the newline-sensitive keymap test).

### Assumptions and unknowns

- ASSUMED: moving DOM elements between containers (same ids) does not break the JS (it uses getElementById). VALIDATION: the keymap/token tests + a manual JS-reference audit.

## Dependencies and approvals

- Design 165:124 (delivered, 7ap refine). None blocking.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The console HTML renders the 165:124 3-zone OBS layout: LEFT plan+transcript, CENTER preview/live + GO LIVE + scriptures, RIGHT timer+detections+outputs, emergency footer | screenshot of the rendered page (headless) + structure review | layout matches the design | headless-Chrome screenshot matches 165:124; index.html | PASS |
| C-002 | yes | All 44 wired element ids preserved; every existing control still reachable (plan edit, scripture, preview/live, GO LIVE, timer, outputs, identify, emergency) | id-inventory diff + JS getElementById audit | zero ids dropped; JS resolves all | id-inventory audit (0 missing of 41) + review confirmed all 54 getElementById targets resolve | PASS |
| C-003 | yes | Pinned invariants hold: keymap JS logic + capture-phase + chords-before-input-bailout; `id="emergency"`, `#clear-all.armed .key`, preview-panel/live-panel/translation/verse-list | `cargo test -p selahcue-app --test test_keymap` + `-p selahcue-present --test test_tokens` | both pass | test_keymap + test_tokens green | PASS |
| C-004 | yes | Live Transcript + Recent Detections panels present with HONEST empty states (labelled R3/R4-pending; no fabricated data); a test pins them | new pinning test | present + honest | #transcript/#detections empty states + test_tokens pins | PASS |
| C-005 | yes | Full verification: workspace tests green, fmt/clippy clean, CI green; independent review, confirmed findings fixed | make-ci + Workflow review | all green; review record | workspace + fmt/clippy green; review (0 high/med, 1 low closed); CI; CODE-REVIEW-batch-console-obs.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: keymap + token tests; a new panel-presence test; a headless screenshot of the page for the layout.
- Broader: full workspace tests + fmt/clippy + CI (the operator shell is CI-built).
- Independent: adversarial Workflow review (regression/id-preservation lens · design-fidelity lens · honest-placeholder lens).

## Iteration ledger

### Iteration 1

- Target criterion: C-001/C-002
- Hypothesis: re-arranging the `<main>` into a 3-zone CSS grid + moving the preview/live/golive nodes to the center, keeping all ids + the `<script>`, reproduces the design without breaking wiring.
- Change or investigation: read the full index.html; rewrite style + main; screenshot.
- Verifier executed: keymap + token tests; headless-Chrome render of the page; adversarial review agent; workspace + fmt.
- Result: **C-001..C-005 PASS.** The console renders the 165:124 3-zone OBS layout; all 41 wired ids preserved (0 dropped); pinned keymap + token invariants hold; the two forward-looking panels carry honest R3/R4 empty states (test-pinned). Review: 0 high/med findings; 1 low (a defensive `#outputs` overflow guard) closed; 1 low (unused `.side-panel` hook) accepted.
- New evidence: headless screenshot matches the design; the `<script>` is byte-unchanged (elements moved CSS containers only).
- Decision: gate-review (all mandatory criteria PASS)

## Risks and rollback

- Risks: a dropped id silently breaks a control (JS null-deref); the keymap test's newline-sensitive checks. Rollback: git; the whole change is one file (+ tests).

## Pause and escalation conditions

- If the design implies R3/R4 data the console can't produce, keep an honest empty state (do not fabricate) — noted, not blocking.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpztgr-console-obs-layout.md --require-complete`
- Validator result: PASS (5/5 mandatory)
- Independent verification result: review agent — 0 high/med; 1 low closed
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajpztgr
