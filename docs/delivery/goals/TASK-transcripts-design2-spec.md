# Goal Contract — TASK-transcripts-design2-spec

## Identity

- Goal ID: TASK-transcripts-design2-spec
- Parent goal ID: NONE
- Title: A design handoff and matching Figma frames exist for the Transcripts surface — the only major desktop surface with zero prior Figma coverage — grounded in the live implementation, not a guess.
- Role: ui-ux-designer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: NONE — no matching task found by search; pending ClickUp update recorded below.
- Created: 2026-09-20
- Updated: 2026-09-20
- Maximum iterations: 8
- Independent verification required: yes

## Objective

`docs/design/TRANSCRIPTS-2.0-HANDOFF.md` exists, is grounded in a full read of
`implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (and its `index.html`/`app.js`/`app.css`
seams), enumerates every state the surface can be in, and cross-references the adjacent already-designed
territory (`DETECTIONS-VIEW-spec.md`, `UX-CANONICAL.md`, `UX-FLOWS.md`, `UX-STATE-MATRIX.md`,
`DESIGN-TOKENS.md`). Real frames for the surface's primary states exist in the live Figma file
(`SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1`), under one clearly-named top-level section, and render correctly.
`docs/design/DESIGN-2.0-HANDOFF.md`'s node map includes the new section.

## Baseline

- Confirmed during planning (full 79-node top-level enumeration of page `0:1`): Transcripts has no Figma frame
  anywhere in the file — the only major desktop surface with zero design coverage.
- `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` is 1605 lines, actively developed this
  month (86akcffvt core slice; 86akgqdxr detections + saved-draft view/edit; 86akgqdw0/86akgqdwc/86akgqdx8
  sermon-notes generation iterations; commit `7afcbc9` on `main` — the scripture-verification-incomplete caveat
  fix — is the most recent change and is already reflected in the file read for this handoff).
- No design doc previously existed for this surface at all (not even a stale one to reconcile).

## Inputs and evidence sources

- `implementation/desktop/crates/selahcue-operator/dist/transcripts.js` (full read, all 1605 lines)
- `implementation/desktop/crates/selahcue-operator/dist/index.html` `#surface-transcripts` (lines 1191–1276)
- `implementation/desktop/crates/selahcue-operator/dist/app.js` (surface routing, `APP_SURFACES`, `trActivate`)
- `implementation/desktop/crates/selahcue-operator/dist/app.css` (`.tr-*`, `.pp-gen-*` rules, lines ~6855–7443)
- `git show 7afcbc9` (the scripture_verification_incomplete fix, most recent change to this file on `main`)
- `docs/design/{DETECTIONS-VIEW-spec.md,UX-CANONICAL.md,UX-FLOWS.md,UX-STATE-MATRIX.md,DESIGN-TOKENS.md,DESIGN-2.0-HANDOFF.md,SETTINGS-2.0-HANDOFF.md,SERVICE-PLAN-2.0-HANDOFF.md}`
- Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, page `0:1` (full top-level enumeration + node `312:124`/`344:124` chrome
  precedent read via `get_metadata`)

## Scope

### In scope

- Reading the current Transcripts implementation end-to-end to understand every reachable state.
- Producing `docs/design/TRANSCRIPTS-2.0-HANDOFF.md` in the project's existing handoff house style.
- Pushing real, clearly-named Figma frames for the surface's primary states into the live file.
- Updating `docs/design/DESIGN-2.0-HANDOFF.md`'s node map with the new section (additive only — not a full
  repair of that doc's other known staleness).

### Non-goals

- Editing any implementation file (`implementation/**`) — docs + Figma only.
- A from-scratch redesign of the surface — this records what already ships (RISK-205 "code is truth" pattern),
  it does not propose new interaction design.
- Auditing any other surface (that is Phases A/B/B2 of the parent plan, run separately).
- Resolving the FR-124 timestamp-linked-navigation gap noted in §9 of the handoff — flagged as an open product
  question, not decided here.

### Constraints

- Never guess an implemented behaviour — every state claim in the handoff traces to a specific line in
  `transcripts.js`/`index.html`/`app.css`.
- Figma frames must be built from the shipped `--sc-*` tokens (`DESIGN-TOKENS.md`), not new hardcoded values.
- No application code may be modified to produce this deliverable.

### Assumptions and unknowns

- ASSUMED: the shipped single-column layout (not `UX-FLOWS.md` Flow 11's split-pane sketch) is the surface of
  record, per RISK-205. Validation owner: product owner (flagged, not silently reconciled — see handoff §9).
- UNKNOWN: whether FR-124 (timestamp-linked note navigation) should be scheduled for this surface. Owner
  decision, flagged in the handoff §10.

## Dependencies and approvals

- None blocking — this is a design-record deliverable with no code dependency.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `TRANSCRIPTS-2.0-HANDOFF.md` exists with the house-style section set (scope/what-it-does, tokens, frames table, state matrix, copy, accessibility, component inventory, divergence note, implementation notes). | `grep -c '^## ' docs/design/TRANSCRIPTS-2.0-HANDOFF.md` | 10 sections present | the file | PASS |
| C-002 | yes | Every state claim in the handoff cites a real code location. | manual re-read of §2–§5 against `transcripts.js`/`index.html`/`app.css` | no unsourced state claims | the file + source | PASS |
| C-003 | yes | The new Figma section is clearly named (not a generic "Frame") and contains frames for the list default/empty/error states and the detail default, still-recording, consent-preview, and edit-mode states. | `get_metadata` / `get_screenshot` on section `1050:2` | section named "Transcripts — Design 2.0"; 7 child frames, clearly named | Figma file, section `1050:2` | PASS |
| C-004 | yes | The pushed frames render correctly (no cropped/overlapping content) when screenshotted. | `get_screenshot` on each of the 7 frame node ids | text and layout legible, no major clipping | screenshots captured this session (`/tmp/tr_*.png`) | PASS |
| C-005 | yes | `DESIGN-2.0-HANDOFF.md`'s node map includes the new section. | `grep -n Transcripts docs/design/DESIGN-2.0-HANDOFF.md` | a new row referencing the Transcripts section and node `1050:2` | the file | PASS |
| C-006 | yes | No implementation file was modified. | `git status --porcelain implementation/` | unchanged from the session baseline (only peer-session pre-existing WIP, if any) | git status output | PASS |
| C-007 | yes | This goal contract validates structurally and on completion. | `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-transcripts-design2-spec.md --completion` | OK | validator output | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: re-read each handoff section against the cited `transcripts.js`/`index.html`/`app.css`
  lines; re-screenshot each of the 7 Figma frames.
- Broader regression verification: `git status --porcelain implementation/` proves the work was docs+Figma only.
- Independent verifier: the user / product owner reviewing the open questions in handoff §10.
- Required environment: local checkout + Figma MCP.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-007
- Hypothesis: the shipped surface has enough internal structure (list/detail, bounded virtualizer, detections
  panel, generate/notes panel with view/edit modes) to map cleanly onto a Design 2.0 frame set without inventing
  new interaction patterns.
- Change or investigation: read all 1605 lines of `transcripts.js` plus its `index.html`/`app.js`/`app.css`
  seams; read the five grounding docs; inspected Figma chrome precedent (`312:124`, `344:124`); built the
  section + 7 frames via `use_figma`; screenshotted each; wrote the handoff doc.
- Verifier executed: per-frame `get_screenshot`; `grep` section-count checks on the handoff; `git status
  --porcelain implementation/`.
- Result: handoff written, 7 frames pushed and verified by screenshot, no implementation file touched.
- New evidence: see the handoff document and this session's Figma node ids.
- Decision: complete

## Risks and rollback

- Risks: the surface is under active development this month (three recent branches) — this handoff is a
  point-in-time record and says so; a future change to `transcripts.js` may drift from it without a reconcile
  pass (the same risk every other Design 2.0 handoff already carries).
- Rollback or recovery: this is a new document plus new Figma frames — delete the doc / remove the Figma section
  to revert; no code was touched.

## Pause and escalation conditions

- The §9 divergence from `UX-FLOWS.md` Flow 11 (split-pane vision vs. shipped single column) and the FR-124 open
  question are owner decisions, not resolved here.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-transcripts-design2-spec.md --completion`
- Validator result: OK (structural) and OK (completion).
- Independent verification result: pending owner review of the two open questions (§9/§10 of the handoff).
- Terminal state: GATE_REVIEW — the design record is complete; the divergence note and FR-124 scheduling are
  owner decisions, not blockers to this deliverable.
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: pending — no ClickUp task exists yet for this work; see
  `docs/delivery/BUILD_STATE.md` pointer entry for the interim record.
