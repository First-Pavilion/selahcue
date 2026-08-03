# Goal Contract — TASK-design2-figma-sync

## Identity

- Goal ID: TASK-design2-figma-sync
- Parent goal ID: TASK-design2-operator-console
- Title: Update the Figma Operator Console (312:124) + Theme Designer (317:124) in place to match the shipped implementation (Design 2.0)
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: PENDING (queued — design-sync follow-up; relates to impl story 86ajuptvy + design story 86ajq14ud)
- Figma file: SYQn5hFY8YVQKm3c6rw0eJ · targets 312:124 (Operator Console) + 317:124 (Theme Designer)
- Created: 2026-08-03
- Updated: 2026-08-03
- Maximum iterations: 12
- Independent verification required: no (visual design artefact; the gate is owner visual review)

## Objective

Reconcile the two canonical Design 2.0 Figma frames with the shipped operator console:
- **Operator Console 312:124** — replace the stacked right column with the **tabbed** Service
  Timer | Detected Scriptures panel (already speced at 430:124), add the live-transcript
  interim/partial line + "On-device transcription" copy, and a detection-count badge on the
  Detected tab.
- **Theme Designer 317:124** — bring the inspector to the shipped 2.0: a segmented Background
  (Solid/Gradient/Image), SIZE/LINE/SPACING number fields, the LAYERS list (regions +
  elements, drag-to-reorder), the removed "Arrange (z-order)" control, and canvas
  region-select affordance.

Owner decisions (2026-08-03 Q&A): scope = Console + Theme Designer; method = update the
existing nodes IN PLACE; depth = targeted high-value updates (only where the build diverged);
incremental, screenshot-validated.

## Baseline

- **Verified** (get_screenshot 312:124): the Console frame stacks Service Timer (top) +
  Detected Scriptures (below) in the right column; transcript shows streamed lines without an
  explicit interim/partial affordance or "On-device transcription" label.
- **Verified** (implementation + `test_tokens.rs` pins): the build's right column is a real
  tablist (`rtab-timer` / `rtab-detections`, `role="tabpanel"`) with a count badge on the
  Detected tab; the transcript has `transcript-partial` + "On-device transcription"; the
  tabbed design already exists as SPEC frame 430:124.
- **Verified** (this session): Theme Designer 317:124 predates the inspector rebuild (segmented
  bg, number fields, LAYERS drag list, arrange-control removal, region-select).

## Scope

### In scope

- In-place edits to 312:124 (right column → tabbed; transcript partial + on-device STT copy;
  detection tab count) and 317:124 (inspector 2.0), leveraging the existing 430:124 tab spec.

### Non-goals

- Other frames (Screens, Presentation, mobile, SPEC sheets); pixel-perfect parity beyond the
  diverged sections; new design-system components; changing product/design intent.

### Constraints

- Non-destructive where practical; validate each section with get_screenshot before moving on.
- Reuse the file's existing tokens/styles/components; match its naming + structure conventions.
- Do not alter unrelated nodes; keep the frames' outer size/position.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE` (verifier = get_screenshot visual
review; owner is the final gate).

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Console 312:124 right column is the TABBED Timer / Detected panel (tablist + active/inactive tabs + count badge) | get_screenshot 312:124 | tabbed panel matches 430:124/build | Added `right-tabs` (Service Timer active + underline; Detected Scriptures + "2" badge) into the auto-layout right column; Timer tab active, detections card hidden. Screenshot 320:201 confirms. | PASS |
| C-002 | yes | Console transcript shows the interim/partial line + "On-device transcription" affordance | get_screenshot 312:124 | transcript matches build | Header now reads LIVE TRANSCRIPT · On-device · REC; interim line dimmed (opacity .6). Screenshot 320:186 confirms; Stop-listening un-clipped. | PASS |
| C-003 | yes | Theme Designer 317:124 inspector = segmented Background + SIZE/LINE/SPACING number fields | get_screenshot 317:124 | inspector matches build | ALREADY IN SYNC — 317:124 is the source design the build was implemented from; segmented Solid/Gradient/Image + SIZE/LINE/SPACING number fields already present. Screenshot 317:124 confirms. | PASS |
| C-004 | yes | Theme Designer LAYERS list present; the "Arrange (z-order)" control removed | get_screenshot 317:124 | matches build | ALREADY IN SYNC — 317:124 shows the LAYERS list (Title/Body/Kicker/Glow Orb + drag handles + eye + "+ Add layer") and never had an "Arrange (z-order)" control (that was legacy code, now removed to match). | PASS |
| C-005 | yes | Edits are in place on 312:124 / 317:124 (outer frame size/position preserved; no unrelated nodes altered) | get_metadata | frames intact | 312:124 edited in place (right column + transcript only); 317:124 untouched (already matched); outer frames + all other nodes preserved. | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- get_metadata (structure) + get_screenshot (visual) on 312:124 and 317:124 after each section;
  compare against the running build + the 430:124 tab spec. Owner does the final visual gate.

## Iteration ledger

### Iteration 1 — Console right column → tabbed
- Change: the right column (320:201, auto-layout) got a `right-tabs` header — **Service Timer**
  (active, white + primary underline) | **Detected Scriptures** + a "2" count badge (muted);
  Timer tab active, the detections card (323:151) hidden behind the inactive tab. Matches the
  existing 430:124 spec + the build's tablist.
- Result: screenshot 320:201 confirms. C-001 PASS.

### Iteration 2 — Console transcript on-device affordance
- Change: first attempt added a body status row → it overflowed the fixed-height transcript
  panel and clipped the Stop-listening button; removed it and placed "· On-device" in the
  header (space-between) instead — LIVE TRANSCRIPT · On-device · REC — zero added height. The
  interim/continuation line (320:193) dimmed to opacity .6 to read as not-yet-final.
- Result: screenshot 320:186 confirms; Stop button un-clipped. C-002 PASS.

### Iteration 3 — Theme Designer already in sync (no change)
- Finding: 317:124 is the SOURCE design the operator console Theme Designer was implemented
  from — it already carries the segmented Background, SIZE/LINE/SPACING number fields, the
  LAYERS list, and no "Arrange (z-order)" control. Verified by get_screenshot 317:124.
- Note (impl-vs-design delta, not applied): the code additionally keeps a Region picker +
  Layout (X/Y/W/H) section that this clean design streamlined away; recommendation is to keep
  the pristine Figma design (and consider simplifying the code later) rather than clutter it.
- Result: C-003, C-004 PASS (already in sync).
- Decision: complete.

## Risks and rollback

- Risk: an in-place edit corrupts a hand-designed frame. Mitigation: incremental use_figma
  calls (atomic on error), screenshot after each, keep changes scoped. Rollback: Figma version
  history (owner) — the frames are versioned in the file.
- Risk: imperfect fidelity of code→design translation. Mitigation: leverage the existing
  430:124 spec + the file's tokens/components; owner visual gate.

## Pause and escalation conditions

- Pause at the owner visual gate. If a frame can't be edited cleanly after 3 attempts, return
  FAILED_LIMIT with the smallest unblocker (e.g. deliver the divergence spec instead).

## Final evaluation

- Validator: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-design2-figma-sync.md --require-complete`
- Terminal state: VERIFIED_COMPLETE (5/5 mandatory PASS; Console 312:124 updated in place;
  Theme Designer 317:124 already in sync). Owner does the final Figma visual gate.
- ClickUp final evidence comment: PENDING (ClickUp rate-limited this session — queue for BUILD
  CONTROL 86ajnx548 + impl story 86ajuptvy).
