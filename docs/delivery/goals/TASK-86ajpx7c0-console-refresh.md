# Goal Contract — TASK-86ajpx7c0-console-refresh

## Identity

- Goal ID: TASK-86ajpx7c0-console-refresh
- Parent goal ID: STAGE7-foundation
- Title: The Figma operator-console design reflects the SHIPPED desktop console (3-column IA, scriptures centered, 16:9 preview/live, timer, outputs, emergency footer), bound to the design-system variables
- Role: ui-ux-designer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpx7c0
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Bring the Figma console frame current: the existing node `4:2` is the pre-shipping concept; the shipped operator console (`crates/selahcue-operator/dist/index.html`) has a different, simpler MVP layout. Produce a faithful shipped-console frame so the design source-of-truth matches the running app.

## Baseline

Verified from the repository + Figma as of 2026-07-25:
- Shipped console (`dist/index.html`): header (`#plan-name` · `● LIVE` chip · `#clock`); a 3-column `main` — **left** Service plan (list + add-row: kind select + title + Add); **center** Scriptures (`#translation` picker · `#scripture-q` search · `#scripture-hits` · `.chapter-nav` `‹ #chapter-ref ›` · numbered `#verse-list` with cursor); **right** `#preview-panel` (PREVIEW · STAGED) → GO LIVE row (◀ / GO LIVE / ▶) → `#live-panel` (● LIVE · ON AIR, blackout state) → Service timer (readout · 5:00/10:00 · minutes+Start · −1:00/+1:00 · Stop) → Outputs (role rows) → Identify displays; a footer `#emergency` (■ BLACKOUT · ✕ CLEAR ALL · hints).
- Figma node `4:2` ("SelahCue — Operator Console") is the OLD concept: Preview/Live 2-up in the center, a LIVE-TRANSCRIPT band and a scripture-DETECTION/approve band (R3/R4, NOT shipped), a "Cloud OFF" chip.
- Design-system variables (collection "SelahCue Color"): text/primary #eef1f6, text/muted #9aa4b2, bg/base #0e1116, bg/panel #171b22, border #2b323d, accent/brand #5b6bd6, accent/preview #2bb673, accent/live #ef4444, output/black #000000.

## Inputs and evidence sources

- ClickUp 86ajpx7c0 (acceptance).
- `crates/selahcue-operator/dist/index.html` (the shipped console — source of truth).
- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, node `4:2`, "SelahCue Color" variables.

## Scope

### In scope

- A Figma frame reflecting the shipped console's 3-column IA + all panels, built from the "SelahCue Color" variables (extend, don't fork).
- Preserve node `4:2` (the concept) for history; note it superseded.

### Non-goals

- Post-MVP surfaces (live transcript = R3, scripture auto-detection/confidence = R4) — deliberately NOT in the shipped-console frame.
- Every hover/empty/error micro-state (the shipped app is authoritative for interaction states; this frame captures the default IA faithfully).

### Constraints

- Fills bound to the design-system variables (no forked hex).
- Canonical colour semantics: preview=green, live=red.

### Assumptions and unknowns

- ASSUMED: Figma MCP write access is available. VALIDATION OWNER: the use_figma calls.

## Dependencies and approvals

- None blocking.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | A console frame exists with the shipped 3-column IA: header (plan name · ● LIVE · clock), Service plan panel (+add-row), Scriptures CENTER panel (translation · search · hits · ‹chapter› nav · numbered verse list w/ cursor), right column (Preview 16:9 · GO LIVE · Live 16:9 · Service timer · Outputs · Identify), emergency footer | get_metadata on the new frame | all named panels present in the expected columns | Figma node 150:124 "Operator Console — shipped (86ajpx7c0)" | PASS |
| C-002 | yes | Panel/chip fills are bound to the "SelahCue Color" variables (not forked hex); preview=green / live=red | use_figma bound-variable check | every panel background + preview/live accent bound | fills bound via setBoundVariableForPaint to VariableID:3:3..3:13 | PASS |
| C-003 | yes | The post-MVP concept elements (live-transcript band, scripture auto-detection/approve) are NOT in the shipped-console frame | screenshot review | absent | screenshot (no transcript/detection bands) | PASS |
| C-004 | yes | Screenshot matches the shipped console layout (3-col, scriptures center, 16:9 preview/live, timer, outputs, emergency footer) | get_screenshot | visual match | node 150:124 screenshot vs dist/index.html | PASS |
| C-005 | yes | Independent design-consistency review; findings fixed | design-reviewer agent (frame vs shipped index.html) | structurally faithful; 3 mediums fixed; lows documented | CODE-REVIEW-batch7ap.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: get_metadata + get_screenshot of the new frame vs the shipped `index.html` layout.
- Broader regression verification: the "SelahCue Color" variables are unchanged (extend, not fork).
- Independent verifier: Workflow adversarial review (does the frame match the shipped console; are variables bound; are post-MVP elements correctly excluded).
- Required environment: Figma MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: a wrapper frame + the header/plan/scriptures/right/footer sections, variable-bound, reproduces the shipped console.
- Change or investigation: build the frame via use_figma; screenshot-verify.
- Verifier executed: 2 use_figma build calls (wrapper/header/plan/scriptures; right column/footer) + get_screenshot of node 150:124; design-reviewer agent vs `dist/index.html`.
- Result: **C-001..C-004 PASS** — the frame reproduces the shipped 3-column console (scriptures centered, 16:9 preview/live stacked, timer, outputs, emergency footer), fills bound to the SelahCue Color variables, post-MVP transcript/detection bands correctly excluded.
- New evidence: node 150:124 "Operator Console — shipped (86ajpx7c0)".
- Decision: iterate (design review)

### Iteration 2 — review remediation

- Target criterion: C-005
- Change or investigation: independent design-reviewer agent compared node 150:124 to `dist/index.html`. Verdict: **structurally faithful; no high-severity; post-MVP bands correctly absent.** 3 medium divergences fixed via a corrective use_figma: (1) BLACKOUT off-state → dark panel button (was rendering light) — canonical emergency control; (2) timer controls → the shipped **3 rows** (presets · minutes+Start · −1:00/+1:00/Stop) + "stage output only" note; (3) Outputs → the shipped role labels (Main output / Stage display) + per-row **Assign** picker + full-width **Identify displays**. LOW stylization items (enriched plan subtitles, preview/live big=title nuance, header sub) accepted as reference-design latitude and documented.
- Verifier executed: re-screenshot of node 150:124.
- Result: **C-005 PASS** — mediums fixed; frame faithful.
- Decision: gate-review (all mandatory criteria PASS)

## Risks and rollback

- Risks: a from-scratch console build is large. Rollback: additive (a new frame); node `4:2` preserved; no code touched.
- Rollback or recovery: delete the new frame if wrong.

## Pause and escalation conditions

- If Figma write access is unavailable, return BLOCKED with the connection requirement.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpx7c0-console-refresh.md --require-complete`
- Validator result: PASS (5/5 mandatory PASS)
- Independent verification result: design-reviewer agent — structurally faithful; 3 mediums fixed
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajpx7c0
