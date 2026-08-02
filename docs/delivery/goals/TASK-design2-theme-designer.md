# Goal Contract — TASK-design2-theme-designer

## Identity

- Goal ID: TASK-design2-theme-designer
- Parent goal ID: TASK-design2-operator-console
- Title: Rewrite the Theme Designer to the full Design 2.0 (Figma 317:124)
- Role: frontend-engineer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: 86ajuptvy (impl story, epic 86ajp07ce, linked to design story 86ajq14ud; status QA)
- Design spec: docs/superpowers/specs/2026-08-01-theme-designer-design2.md
- Created: 2026-08-01
- Updated: 2026-08-01
- Maximum iterations: 10
- Independent verification required: yes (token/pin suite + present/theme/compose tests +
  node --check + fmt/clippy; adversarial /code-review + /qa + /performance + /security workflow)

## Objective

Rewrite the Theme Designer webview surface (`dist/index.html` `#surface-theme-designer` +
`app.css`, with targeted `app.js` and a small additive Rust model slice) to the Figma
"Theme Designer — Design 2.0" (node 317:124): topbar (Duplicate / Preview on output /
Save theme), a two-column body (canvas zone with add-bar + zoom + bottom Templates strip;
360px sectioned inspector BACKGROUND / TYPOGRAPHY / LAYERS), and a real LAYERS panel with
drag-reorder + a truthful per-layer visibility toggle backed by a new additive
`Element.visible` field. Preserve every pinned DOM/token invariant and JS id hook. See the
design spec for the full mapping and locked decisions.

## Baseline

- Current Theme Designer: 3-column (list | stage | inspector) on the Design 2.0 vars.
  `app.js` (~2,669 lines) drives all behaviour off exact element ids; `test_tokens.rs`
  pins the Theme Designer needles (§theme-designer editor, saved-theme library, font
  picker enabled) plus the operator-console pins.
- Theme model (`selahcue-present/src/theme.rs`): `RegionStyle` has `visible: bool`
  (gated in `compose.rs`). The `Element` enum (`Shape` / `Image` / `Text`) has `opacity`
  + `z` but **no** `visible` field.
- Elements cap: 64 per theme (`app.js`). Regions: title + body.

## Scope

### In scope

- Restructure `#surface-theme-designer` markup to the 2.0 two-column shell; re-home (never
  rename) all pinned ids.
- Restyle `app.css` for the D2 topbar, canvas zone, zoom control, Templates strip,
  sectioned inspector, and LAYERS panel.
- Wire `app.js`: the LAYERS panel (select / reorder→z-order / visibility toggle), the zoom
  control, Duplicate, and the re-homed Preview-on-output button.
- Add the additive `Element.visible` field + `compose.rs` gate + `theme`/`compose` tests.
- Update `test_tokens.rs` needles for any changed-but-still-pinned markup.

### Non-goals

- Import/Export theme files; Slides templates; native file pickers; persisting zoom;
  per-screen theme; any wire change beyond the additive `visible`; other surfaces.

### Constraints

- No pinned needle or JS id hook may break. `visible` must be byte-identical-when-true
  (serde skip). No unbounded memory (LAYERS list bounded by the 64-element cap + 2 regions).
  WKWebView-safe (no `window.prompt`; class-based hiding; pointer DnD). AA contrast.

### Assumptions and unknowns

- ASSUMED: "Duplicate" = clone current design into a new unsaved working theme (reuses the
  new-from-current path). VALIDATION: owner visual QA / review.
- ASSUMED: LAYERS lists the 2 regions + all elements, topmost-first. VALIDATION: review.

## Dependencies and approvals

- Builds on the uncommitted Operator Console Design 2.0 batch (same dist files). No
  blocking external dependency. Owner approved the design direction (Q&A 2026-08-01).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | 2.0 shell implemented (topbar Duplicate/Preview-on-output/Save; canvas zone + zoom + Templates strip; sectioned inspector BACKGROUND/TYPOGRAPHY/LAYERS) matching Figma 317:124 | markup review + headless | shell matches design | `operator_theme_designer_is_design_2` pins the topbar/zoom/strip/LAYERS; 116/0 headless checks | PASS |
| C-002 | yes | All pinned Theme Designer needles + JS id hooks preserved | `cargo test -p selahcue-present --test test_tokens` + `node --check app.js` | all pins green; parse OK | 14/14 token tests pass; `node --check` OK; boot fix restored (guarded `#td-new`) | PASS |
| C-003 | yes | LAYERS panel: select + reorder (→z-order) + visibility toggle wired for real | headless + code review | rows select/reorder/hide | 14 D2 headless checks (select/eye/reorder) + a11y focus + drag-cancel checks pass | PASS |
| C-004 | yes | Additive `Element.visible` field: serde byte-identical-when-true, round-trips, compose gates hidden layers | `cargo test -p selahcue-present` (theme + compose) | tests green | 3 new compose visibility tests (TDD red→green) + byte-stable serde assertion; present suite green | PASS |
| C-005 | yes | Zoom + Duplicate + re-homed Preview-on-output wired; honest-later (Import/Export, Slides) preserved | headless + review | controls behave; later affordances honest | D2 headless zoom/Duplicate checks pass; Import/Export/Slides remain disabled `td-later` | PASS |
| C-006 | yes | Accessibility: keyboard-operable LAYERS/zoom, aria state, reduced-motion, AA contrast | review + audit test | criteria met | QA finding on focus loss FIXED + regression-checked (headless a11y checks); `--sc-` palette WCAG-audited | PASS |
| C-007 | yes | Full CI gate green | `make ci` | fmt+clippy+all suites pass | `make ci` == ALL GREEN both pre-fix and after the 6 review fixes | PASS |
| C-008 | yes | Independent multi-lens review (code-review/QA/perf/security) run; findings triaged/fixed | review workflow | no unresolved blocking finding | 4-lens adversarial workflow: 11 filed → 6 confirmed (0 security) → all 6 fixed + re-verified | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- `node --check app.js`; `cargo test -p selahcue-present` (tokens + theme + compose);
  `cargo check --manifest-path …/selahcue-operator/Cargo.toml`; `python3
  scripts/operator_headless.py`; `make ci`; adversarial review workflow. Environment: the
  desktop Rust workspace + headless Chrome.

## Iteration ledger

### Iteration 1 — build

- Target: C-001..C-007.
- Change: (model) additive `Element.visible` on Shape/Image/Text + `Element::visible()` +
  `compose_slide` gate over both z-passes + `default_true`/`is_true` serde helpers; updated all
  `Element` construction sites; 3 new compose visibility tests (TDD red→green) + byte-stable serde
  assertion. (webview) rewrote `#surface-theme-designer` to the 2-col Design 2.0 shell; new
  Design-2.0 CSS block; app.js LAYERS panel (select/reorder→z-order/real visibility), zoom,
  Duplicate, re-homed Preview-on-output, tdList thumbnail cards, guarded `#td-new`. (tests) new
  `operator_theme_designer_is_design_2` pin test + 14 D2 headless checks.
- Result: caught a boot-abort (dropped `#td-new` header button → unguarded `.onclick`); fixed by
  guarding the legacy binding. All gates green: fmt/clippy/present/app/lan, operator compile,
  14/14 token tests, 113/0 headless, `make ci` ALL GREEN.

### Iteration 2 — independent review + fixes

- Target: C-006, C-008.
- Change: ran a 4-lens adversarial review workflow (code-review/QA/perf/security), 11 filed → 6
  confirmed (0 security). Fixed all 6: (medium a11y) LAYERS rebuild dropped keyboard focus →
  capture+restore across the innerHTML rebuild (mirrors the Screens-registry pattern); (low ×2)
  layer pointer-drag had no `pointercancel` teardown → added pointercancel + idempotent teardown
  removing all window listeners; (nit) equal-z tie-break inverted stacking vs compose paint order
  → reversed to descending index; (nit ×2) dead `.dragging`/`.drop-*` CSS → wired `.dragging`,
  removed the unused drop rules. Added 3 headless checks (focus retention ×2, drag-cancel teardown).
- Result: 116/0 headless, 14/14 token tests, `make ci` ALL GREEN after the fixes.
- Decision: complete.

## Risks and rollback

- Risk: a pinned needle / id hook breaks. Mitigation: re-home ids; run the pin suite +
  node --check each iteration. Rollback: revert the dist files.
- Risk: the `visible` field ripples through theme consumers/GPU parity. Mitigation:
  `skip_serializing_if` (byte-identical JSON); trace every `Element` site; Shape/Image/Text
  are documented GPU-skip seams. Rollback: the field is additive-only.

## Pause and escalation conditions

- Stop at the `make ci` + review gate for owner visual QA (no in-repo render harness).
- After three materially different failed attempts on a criterion, return FAILED_LIMIT with
  the smallest unblocker.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-theme-designer.md --require-complete`
- Validator result: see below
- Terminal state: VERIFIED_COMPLETE (8/8 mandatory criteria PASS; independent 4-lens review run,
  all 6 confirmed findings fixed + re-verified; `make ci` ALL GREEN)
- ClickUp final evidence comment: impl story 86ajuptvy created (epic 86ajp07ce, linked to design
  story 86ajq14ud, status QA with list-form QA steps) + batch evidence posted to BUILD CONTROL
  86ajnx548 (comment 90130300031958).

## ClickUp

- Design story exists: **86ajq14ud** "STORY — Theme Designer + theme model: DESIGN in
  Figma (S8-3a)" (status: code review), epic **86ajp07ce** (Presentation & Slides).
- No implementation story for the Theme Designer 2.0 rewrite exists yet. Queued pending
  update (mirrors the sibling operator-console contract): at the batch gate, create the
  implementation story under epic 86ajp07ce linked to 86ajq14ud, and post the batch
  evidence to BUILD CONTROL **86ajnx548**.
