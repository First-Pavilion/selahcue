# Goal Contract — TASK-86ajq6j29-canvas-editing-design

## Identity

- Goal ID: TASK-86ajq6j29-canvas-editing-design
- Parent goal ID: EPIC-86ajq6j01-canvas-editing
- Title: On-canvas element editing — DESIGN spec (spec-first; Figma frames follow after owner approval)
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq6j29
- Created: 2026-07-27
- Independent verification required: yes
- Maximum iterations: 10

## Objective

Produce the **implementation-ready design spec** for on-canvas element editing in the Theme Designer — the source of truth the interactions (`86ajq6j4p`), image-element authoring (`86ajq6j49`), and text/shape (`86ajq6j64`) engineers build from. It **extends `THEME-MODEL-spec.md §5`** (which already gives the Theme Designer's center canvas region drag/resize, S8-3c) from **region** editing to full **element** editing (`Element::Shape` + `Element::Image`, with the Text element as a noted seam), grounded in the **already-implemented engine model** (`theme::Element`, per-mille rect, `opacity: u8`, `z: i16`, `MediaRef`, the missing-media placeholder, `MAX_ELEMENTS = 64`). The owner reviews this spec at the `/build` design gate; the **Figma frame set is the explicit next phase** after approval (per the owner's "spec first, then Figma" choice).

## Baseline

Verified from repo + code:
- **THEME-MODEL-spec.md** (S8-3a) §5 already specifies the Theme Designer's 3-zone layout (Left rail · Center 16:9 canvas · Right inspector) with elements "selectable (click), movable (drag), resizable (handles)" + an Add-content bar (Text · Scripture · Shape · Image[was deferred]); §6 a state matrix; §7 a11y (WCAG-AA chrome, keyboard path); §8 tokens. This design **extends** it, does not fork it.
- **The Theme Designer UI EXISTS** (`selahcue-operator/dist/app.js`, S8-3c): a `td-preview` canvas (`td-canvas-box`, `td-sel` selection), region drag/resize, a right inspector bound per selected **region** (body/title), a live engine preview (`render_sample`), autosave + `Save changes`. This batch designs the extension to **elements**.
- **Engine model already shipped** (this epic): `Element::Shape { per-mille rect, fill, border, border_permille, opacity: u8, z: i16 }` (86ajq6j2q) + `Element::Image { per-mille rect, source: MediaRef, opacity: u8, z: i16 }` (86ajq6j49); `Theme.elements: Vec<Element>` bounded by `MAX_ELEMENTS = 64`; `compose_slide` renders `z < 0` behind the text, `z >= 0` in front; the engine decodes PNG deterministically + draws a **non-black missing-media placeholder** on failure; opacity is `u8` (0–255), z is `i16`. The image currently **stretches to its rect** (aspect-preserving Fit is a seam).
- **Design system:** `DESIGN-TOKENS.md` / `tokens.rs` — bg/base `#0e1116`, bg/panel `#171b22`, border `#2b323d`, text/primary `#eef1f6`, PREVIEW/LIVE/WARN/NEUTRAL semantic tokens, `contrast_ratio` AA guard. `COMPONENT-SPECS.md §11` keybindings (Tab cycle, arrow nudge + Shift×10, `Cmd/Ctrl+]`/`[` reorder, `Esc` exit edit). `UX-STATE-MATRIX.md` ten-state vocabulary + the four invariants (preview⟂live, emergency chrome always reachable, desktop authoritative, no AI auto-action). Figma: the Theme Designer shell is node **204-124** (file `SYQn5hFY8YVQKm3c6rw0eJ`).

**Key framing:** the engine model is DONE, so this design is unusually low-risk — the spec's job is to define the **authoring interactions + states + controls + a11y** that map onto existing fields (z-order buttons ↔ `z`, opacity slider 0–100% ↔ `u8`, X/Y/W/H ↔ per-mille rect, image replace ↔ `MediaRef`, missing-media state ↔ the engine placeholder), reusing the existing shell + tokens. No new engine capability is proposed; anything that would need one is flagged as a seam.

## Scope

### In scope (design spec — `docs/design/CANVAS-EDITING-spec.md`)

- **Interaction model:** select (click; `Tab`/`Shift+Tab` cycle), move (drag + arrow nudge, `Shift`×10), **resize** (8 handles — 4 corner + 4 edge; `Lock aspect`), delete, and **arrange** — send-to-back / bring-to-front / forward / backward (`Cmd/Ctrl+]`/`[`), mapped to the `z: i16` field; multi-select noted as a seam.
- **Snapping + safe area:** the 5% safe-area guides, edge/centre snap, alignment hints.
- **Add-content flow:** Text / Scripture / Image / Shape — where a new element is placed (default rect), auto-selected, and (for Image) the file-pick → `MediaRef` + the loading/missing states.
- **Per-element controls panel** (right inspector, per selected element): position/size **X/Y/W/H** (per-mille), **opacity** (0–100% ↔ `u8`), **z-order** buttons, and per-kind controls — image: replace / fit(seam) / opacity; text: font / size / colour; shape: fill / border / border-width.
- **All states** (mapped to the ten-state vocabulary): empty canvas, element selected, multi-element z-stack, image loading, **missing-media** (↔ engine placeholder), resize/drag in progress, out-of-bounds (clamped to safe area / frame), disabled (no displays). Each: what the user sees · what they can do · trigger · a11y contract · audience effect (preview-only).
- **Accessibility:** full keyboard operation of select/move/resize/arrange; focus + ARIA roles for the 8 handles; screen-reader **announcement of z-order changes** + selection; colour-never-the-only-cue; the AA contrast guard.
- **Model↔implementation contract:** an explicit table mapping every control/interaction to the implemented engine field (or a flagged seam), so the impl stories build without guessing. Honour the four invariants (esp. preview⟂live — the designer stages to preview only, never Live).
- **Binding:** the existing design tokens + the Theme Designer shell (204-124 / the `td-*` structure). Handoff notes for `86ajq6j4p` / `86ajq6j49` / `86ajq6j64`.

### Non-goals (seams — note)

- The **Figma frame set** itself — the explicit **next phase** after the owner approves this spec (owner's "spec first, then Figma" choice). This batch scopes + storyboards the frames (frame list + per-frame intent) but does not build them.
- Any **implementation** (the interactions/image/text impl stories). **Multi-select**, group/align-distribute, animation, **video** elements (R2). Aspect-preserving image **Fit** modes (the engine stretches today — flagged). Custom-font import (FR-173).

### Constraints

- Extends (does not fork) THEME-MODEL-spec + reuses the existing shell + tokens. Every interaction maps to an already-implemented engine field or is a flagged seam — no new engine capability proposed. Honours the four invariants + WCAG-AA + the NFR-020 audience-text floor. Traces design decisions to FR/NFR/story IDs. Precise enough to implement + QA-verify without guessing.

## Completion predicate

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Interaction model complete: select / move / 8-handle resize / delete / arrange (send-to-back·bring-to-front·forward·backward) / keyboard nudge / lock-aspect; snapping + 5% safe area; the Add-content flow (Text/Scripture/Image/Shape) — each specified with its trigger, result, and keyboard equivalent | completeness check vs the ticket's design deliverables | every listed interaction specified unambiguously | CANVAS-EDITING-spec.md §Interactions | PASS |
| C-002 | yes | All states specified in the ten-state vocabulary: empty · selected · multi-element z-stack · image loading · missing-media · resize/drag-in-progress · out-of-bounds · disabled(no displays) — each with what-the-user-sees, can-do, trigger, a11y, and audience effect (preview-only) | completeness check vs UX-STATE-MATRIX vocabulary | every state present + populated | CANVAS-EDITING-spec.md §State matrix | PASS |
| C-003 | yes | Model↔implementation contract + a11y: an explicit table mapping every control/interaction to the implemented engine field (`z`/`opacity u8`/per-mille rect/`MediaRef`/placeholder/`MAX_ELEMENTS`) or a flagged seam; a11y (keyboard + ARIA handles + z-order announcements) specified; the four invariants honoured; tokens + the 204-124 shell reused — no engineer guessing | completeness + consistency check vs the shipped engine model + the design system | maps cleanly; seams flagged; no contradiction | CANVAS-EDITING-spec.md §Model-contract + §A11y | PASS |
| C-004 | yes | Gate: independent completeness/consistency review (Workflow), findings fixed; the spec is linked in ClickUp + validated; the Figma frame set is scoped as the explicit next phase; gated at the `/build` design gate for owner review (design does NOT auto-advance to impl) | Workflow review + validator + gate | review clean/fixed; spec linked; gated | review result; ClickUp; gate report | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: a completeness check of `docs/design/CANVAS-EDITING-spec.md` against (a) the ticket's design-deliverables list, (b) the `UX-STATE-MATRIX` ten-state vocabulary, (c) the shipped engine model (every control maps to a real field or a flagged seam), (d) `COMPONENT-SPECS §11` keybindings + WCAG-AA. Independent: an adversarial Workflow review (completeness · implementability/engine-consistency · a11y/invariants/tokens lenses) — does the spec leave anything ambiguous, contradict the implemented model, or miss a state/invariant? Design gate: owner review (design does not cross into implementation).
- Required environment: repo (docs + code cross-check).

## Iteration ledger

- **Iter 1 — spec authored (C-001/C-002/C-003).** Wrote `docs/design/CANVAS-EDITING-spec.md`, grounded in the shipped engine model + the existing Theme Designer shell/tokens/THEME-MODEL-spec. §0 grounding (opacity u8↔%, z↔arrange, MAX_ELEMENTS cap, preview⟂live); §1 canvas/per-mille/safe-area; §2 interactions (select/move/8-handle resize/delete/arrange + keyboard); §3 snapping; §4 add-content (Text/Scripture/Image/Shape + image file-pick→MediaRef); §5 per-element controls; §7 the ten-state matrix (empty/selected/z-stack/image-loading/missing-media/drag-resize/out-of-bounds/no-displays/at-cap/save-error); §8 a11y (keyboard + ARIA handles + z-order announcements + contrast); §9 the model↔field contract table (every control → a shipped field or a flagged seam); §10 token/shell binding; §11 the Figma frame plan; §12 handoff. C-001/C-002/C-003 evidence in place. **PASS** (pending review confirmation).
- **Iter 2 — gate (C-004).** Independent adversarial Workflow review launched (completeness · implementability/engine-consistency · a11y/invariants/tokens). Findings + owner design gate pending.
- **Iter 3 — review findings fixed (C-004).** Review `wf_f517e739-257` (3 lenses, 21 findings verified): **15 confirmed / 6 refuted / 0 unverified.** (The first pass's implementability + a11y verifiers hit a weekly subagent cap; a null-safe **resume** replayed the cache + completed them cleanly — 24/24 agents.) **All 15 confirmed fixed** in `CANVAS-EDITING-spec.md`: 2 HIGH z-order — the arrange algorithm was undefined vs `compose_slide`'s stable sort-by-z, so a list-reorder impl is a no-op → new **§2a** pins the exact `z` arithmetic (front=max+1 · back=min−1 · forward/backward=swap-nearest-neighbour · text-plane crossing · i16 renormalize · composite-paint-order tiebreak); HIGH Permission-denied state + HIGH resize-handle focus/ARIA/keyboard-reachability + HIGH apply-to-Live reconciliation (editing→library+preview; applying=a separate RBAC-gated Console action); MED Text/Scripture unbuildable (Shape/Image only in R1, Text disabled) + MED missing states (Recovery/Degraded + Offline/Mobile N/A) + MED element↔region hit-testing/traversal + MED FR-138 path-confinement seam (this story owns it) + MED keyboard-resize disambiguation + MED contrast-guard scope (solid now, composited seam) + MED selection-token (neutral, not reserved PREVIEW/LIVE) + LOW shape alpha (RGB pickers, opacity single alpha) + LOW visible shape defaults. The 6 refuted verified NOT real. **PASS.**

## Risks and rollback

- Risks: designing an interaction that needs a NOT-yet-built engine capability (mitigated: the model↔field table forces every control onto a shipped field or a flagged seam — image Fit, multi-select, text-content editing are explicit seams). Forking the existing shell/tokens instead of extending (mitigated: bind to 204-124 + `tokens.rs`, reference THEME-MODEL-spec). Missing a state the impl then guesses (mitigated: the ten-state vocabulary checklist + the adversarial review). Over-reaching scope (mitigated: Figma frames + multi-select + video are non-goals). Rollback: docs-only; the spec gates before any implementation.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq6j29-canvas-editing-design.md --require-complete`
- Validator result: PASS (4/4 mandatory)
- Independent verification result: adversarial Workflow review `wf_f517e739-257` (3 lenses, 24 agents) — 15 confirmed / 6 refuted; ALL 15 fixed in CANVAS-EDITING-spec.md. See the iteration ledger + the ClickUp handoff.
- Terminal state: GATE_REVIEW (spec + independent review done; paused at the /build DESIGN gate for owner approval — the Figma frame set is the next phase, NOT auto-advanced)
- ClickUp final evidence comment: posted on 86ajq6j29 + BUILD CONTROL 86ajnx548
