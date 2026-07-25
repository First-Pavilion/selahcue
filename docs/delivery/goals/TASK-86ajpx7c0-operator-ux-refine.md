# Goal Contract — TASK-86ajpx7c0-operator-ux-refine

## Identity

- Goal ID: TASK-86ajpx7c0-operator-ux-refine
- Parent goal ID: STAGE7-foundation
- Title: A better Operator console UX that INCLUDES the live transcript + auto-detected scriptures (confidence · Add-to-queue · Present) + a presentation queue, uncramped, on SelahCue's design system
- Role: ui-ux-designer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpx7c0
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Refine the operator console design so it delivers the transcript-driven scripture experience the owner wants (like Pewbeam's live transcript + recent detections), but as a clean, uncramped SelahCue design: a streaming Live transcript → Recent detections (confidence-ranked references with Add-to-queue / Present) → a presentation Queue, integrated with the existing Preview/Live, scripture browser, timer, outputs, and emergency controls.

## Baseline

Verified as of 2026-07-25:
- Batch 7ap built frame `150:124` matching the SHIPPED MVP console, which deliberately excludes live transcript + scripture auto-detection (those are R3/R4 capabilities). The owner has now clarified the DESIGN should include them.
- Owner reference: Pewbeam (2 screenshots) — a "Live transcript" panel (interim + final streaming text, pause/record, waveform) and a "Recent detections" panel (● confidence% REFERENCE + verse text + Add-to-queue / Present), plus a Live display, Output preview, verse list, Preview, and Queue.
- Prior owner feedback (mobile revamp): "cramming all the screens is not a great user experience" — so the new design must NOT be cramped.
- SelahCue "SelahCue Color" variables (VariableID:3:3..3:13): bg/base, bg/panel, bg/elevated, border, text/primary, text/muted, accent/preview (green), accent/live (red), accent/warn (amber), accent/brand, output/black.
- Dependency note: the transcript/detection PANELS depend on R3 (transcription) + R4 (scripture intelligence), which are post-MVP — this is a forward-looking target design (the design leads implementation).

## Inputs and evidence sources

- ClickUp 86ajpx7c0 + this refine's owner feedback + the 2 Pewbeam reference screenshots.
- The shipped console (`dist/index.html`) for the existing panels; frame `150:124`.
- "SelahCue Color" variables.

## Scope

### In scope

- A new Figma frame for the improved Operator console including: Live transcript (interim/final + pause/record + waveform), Recent detections (confidence-ranked scriptures + Add-to-queue / Present), a presentation Queue, and the existing Preview/Live 16:9 + GO LIVE, scripture browser, timer, outputs, emergency footer — in a clean 3-zone (uncramped) layout, bound to the design-system variables.
- Confidence mapped to tokens: high = accent/preview (green), medium = accent/warn (amber).

### Non-goals

- Implementing transcription (R3) or detection (R4) — code is out of scope; this is the target design.
- Redesigning the mobile controller (done in 7ak/7al).

### Constraints

- SelahCue's own design system (green preview / red live / amber warn) — NOT Pewbeam's orange branding.
- Uncramped: clear zones, breathing room, no cramming.
- Every fill bound to the design-system variables.

### Assumptions and unknowns

- ASSUMED: Figma MCP write access. VALIDATION OWNER: the use_figma calls.
- ASSUMED: the transcript/detection are a valid future direction (R3/R4 epics exist). Owner-confirmed via this refine.

## Dependencies and approvals

- Implementation depends on R3 (Transcription) + R4 (Scripture Intelligence) epics — noted, not blocking the design.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The frame includes a **Live transcript** panel (interim=muted + final=primary streaming text · pause/record control · level meter) | get_screenshot | present + legible | Figma node 154:124 (LIVE TRANSCRIPT card) | PASS |
| C-002 | yes | A **Recent detections** panel: confidence-ranked references (● high=green / medium=amber + %) + verse text + **Add to queue** & **Present** actions | get_screenshot | present with confidence semantics | node 154:124 (96% green · 74%/61% amber + actions) | PASS |
| C-003 | yes | The **Service Plan** (running order) + Preview/Live 16:9 + GO LIVE + a "Coming next" plan strip + scripture browser + timer + outputs + emergency footer — all present. (Owner decision: NO separate Queue — it is redundant with the Service Plan + Preview; removed.) | get_metadata/screenshot | all zones present, no redundant queue | node 161:124 (Service Plan + LISTEN + PROGRAM + REFERENCE + footer) | PASS |
| C-004 | yes | Uncramped 3-zone layout; every fill bound to the "SelahCue Color" variables (green preview / red live / amber warn) — not Pewbeam branding | screenshot + bound-var check | clean layout, tokens bound | node 154:124 screenshot; fills bound to VariableID:3:3..3:13 | PASS |
| C-005 | yes | Independent design review; findings fixed; R3/R4 dependency documented | design-reviewer agent | faithful to the intent; findings fixed | reviewer verdict "faithfully delivers the intended better Operator UX"; 2 med + 3 low fixed; CODE-REVIEW-batch7ap-refine.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: get_screenshot of the new frame; confirm the transcript/detections/queue + existing panels + token binding.
- Broader regression verification: the "SelahCue Color" variables unchanged (extend, not fork); frames `150:124`/`4:2` preserved.
- Independent verifier: design-reviewer agent (does it deliver the transcript-driven UX; uncramped; on-brand; confidence semantics correct).
- Required environment: Figma MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: a 3-zone layout — LISTEN (transcript + detections), PROGRAM (preview/live + queue), REFERENCE (scripture browser + timer + outputs) + emergency footer — delivers the transcript-driven UX without cramming.
- Change or investigation: build the frame via use_figma; screenshot-verify.
- Verifier executed: 3 use_figma build calls + get_screenshot (node 154:124); design-reviewer agent.
- Result: **C-001..C-004 PASS** — transcript + detections + queue + existing panels, uncramped, tokens bound. Reviewer verdict: "faithfully delivers the intended better Operator UX", on-brand, confidence mapping correct.
- New evidence: node 154:124 (first version, with a Queue).
- Decision: iterate (design review + owner refinements)

### Iteration 2 — design review + owner refinements

- Target criterion: C-005, C-003
- Change or investigation: (a) design review fixes — added a "listening…" cue + a "bright=final/grey=resolving" legend to the transcript, neutralized the amber Pause, renamed the detection go-live action to **Preview** (stages to preview → GO LIVE, consistent with the safety model), added HIGH/MED/LOW confidence labels (not colour-only), removed the duplicate header BLACKOUT, added an "active" status to Outputs. (b) **Owner refinements**: the owner asked why a Queue is needed when there is a Preview — it is redundant (the Service Plan is the running order, Preview is the single on-deck item), so the **Queue was removed and the Service Plan restored** (it had been dropped when the LISTEN zone was added). Rebuilt as a clean 4-zone frame `161:124` (Service Plan · Listen · Program [Preview/Live + GO LIVE + "Coming next"] · Reference) at 1760 wide; detection actions are now **＋ Add to plan** / **Preview**.
- Verifier executed: get_screenshot of node 161:124.
- Result: **C-003 & C-005 PASS** — Service Plan present, no redundant queue, review fixes applied; the frame delivers the transcript-driven Operator UX with the plan intact, uncramped.
- Decision: iterate (owner layout reorg)

### Iteration 3 — owner layout reorg (OBS studio mode)

- Target criterion: C-003, C-004 (layout/UX smoothness)
- Change or investigation: owner directed a smoother arrangement — (1) move Live transcript + Recent detections to the **right**; (2) make PROGRAM an **OBS studio-mode** pair (Preview | Live **horizontal**, GO LIVE transition below); (3) put **Scripture directly below PROGRAM**; (4) put the **Timer in the bottom-right corner**. Rebuilt as frame `165:124` "Operator Console — OBS studio (target)" at 1760 wide: **LEFT** Service Plan · **CENTER** OBS Preview|Live + GO LIVE → Scriptures → Outputs strip · **RIGHT** Live transcript → Recent detections → Service timer (bottom corner) · emergency footer. All tokens preserved; the transcript/detections review fixes carried over.
- Verifier executed: get_screenshot of `165:124`.
- Result: **PASS** — all four directives satisfied; the OBS-style program pair + scripture-below reads as a smoother operator flow; uncramped.
- Decision: iterate (owner made in-Figma edits)

### Iteration 4 — note the owner's in-Figma edits + fine-tune

- Target criterion: C-004 (layout polish)
- Change or investigation: the owner directly edited frame `165:124` — moved **Live transcript to the bottom-left** (under the Service Plan), the **Service timer to the top-right**, **Recent detections** below it, **Outputs** to the bottom-right, and made **Scriptures taller**. Noted and fine-tuned the resulting rough edges: (1) **reflowed the transcript** for the now-300px-wide column (its text had clipped), (2) **rebuilt Outputs at 628px** (it had overflowed the frame's right edge at w=774), (3) **aligned the right column** (Timer/Detections/Outputs were at x=1112/1124/1128 → all 1112, w=628), (4) **tightened the timer** (removed the dead space, added the "shown on the stage output only" note). Final zones: LEFT Service Plan + Live transcript · CENTER OBS Preview|Live + GO LIVE + Scriptures · RIGHT Service timer + Recent detections + Outputs · emergency footer.
- Verifier executed: get_screenshot of `165:124` — no clipping, no overflow, right column aligned, transcript readable.
- Result: **PASS** — the owner's arrangement preserved and cleaned up.
- Decision: gate-review (all mandatory criteria PASS; final frame = `165:124`)

### Iteration 5 — owner resized panels; placement-only fine-tune

- Target criterion: C-004 (polish)
- Change or investigation: the owner resized panels again (left column → 415w, Scriptures → 789w, right column → ~446–452w) and directed: **leave the sizes as-is, improve the placements**. Placement-only pass: top-aligned the three columns at y=68; right column set on one left edge with even 12px gaps (Timer → Detections → Outputs); inner content reflowed to fit the owner's panel sizes without changing them — plan rows widened to the 415 panel (badges docked right, add-row at the bottom), transcript text/meter/footer spread to 415, Scriptures search stretched + chapter nav docked right + verse rows filled to 789, detection cards/timer controls/outputs fitted to their ~446–452 panels, Preview/Live headers + captions matched to their panels.
- Verifier executed: get_screenshot of `165:124` — no clipping, no overflow, aligned tops/edges/gaps; owner sizes preserved.
- Result: **PASS**.
- Decision: gate-review (final frame = `165:124`)

## Risks and rollback

- Risks: a large from-scratch design; the transcript/detection depend on unbuilt R3/R4. Rollback: additive (a new frame); prior frames preserved; no code.
- Rollback or recovery: delete the new frame.

## Pause and escalation conditions

- If Figma write access is unavailable, return BLOCKED with the connection requirement.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpx7c0-operator-ux-refine.md --require-complete`
- Validator result: PASS (5/5 mandatory)
- Independent verification result: design-reviewer agent — "faithfully delivers the intended better Operator UX"; findings fixed
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajpx7c0
- Note: the transcript + detections panels depend on R3 (transcription) + R4 (scripture intelligence), which are post-MVP — this is the target Operator design (design leads implementation).
