# Goal Contract — TASK-86ajq14ud-theme-design

## Identity

- Goal ID: TASK-86ajq14ud-theme-design
- Parent goal ID: STAGE8-core-presentation
- Title: Design the Theme Designer surface + a written theme-model spec (FR-010) — Figma + spec, no code — so S8-3b/c can build without guessing
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq14ud
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 6
- Independent verification required: no (design gate is the user)

## Objective

Design the **Theme Designer** and the **theme data-model** for SelahCue. A theme is a slide-design template the audience output uses to render scriptures/songs/lower-thirds (FR-010: fonts, colours, safe areas, positions; restyle without content loss; editable centrally) — modelled on ProPresenter Themes + the owner's Pewbeam Theme Designer. Deliverables: (1) a written, implementation-ready theme-model spec; (2) Figma frames — the Theme Designer UI + default templates for scripture/song/lower-third + all states — bound to the SelahCue design system.

## Baseline

Verified: COMPONENT-SPECS.md §Presentation Editor already frames this — states `empty/new · editing · dirty · saved · applying-template`; "Template dropdown restyles the whole group **without losing content** (FR-010)"; "Template application that would clip content: warn + overflow indicator, do not silently truncate"; content-type variants scripture/song/announcement/sermon-point/lower-third; stage/audience text ≥48px floor + high-contrast selectable (NFR-020). Design tokens: `DESIGN-TOKENS.md` + `tokens.rs` (bg/base #0e1116, bg/panel #171b22, border #2b323d, text/primary #eef1f6, accent green/red/amber). The compositor now shapes text via cosmic-text (S8-2) → glyph measurement enables real alignment. Figma file SYQn5hFY8YVQKm3c6rw0eJ holds the shipped console + design system.

## Inputs and evidence sources

- Story 86ajq14ud + umbrella 86ajpzhak + epic 86ajp07ce; FR-009/010/011 (PRD); COMPONENT-SPECS.md; DESIGN-TOKENS.md; tokens.rs; ADR-0014 (shaping); ProPresenter Themes docs + the Pewbeam Theme Designer screenshot (owner-supplied); memory themes-are-design-templates.

## Scope

### In scope

- A written **theme-model spec** (`docs/design/THEME-MODEL-spec.md`): the data model (Theme → per-role Layout → positioned Regions with typography; background; reference styling + gap; Template concept; per-item override seam); resolution-independent units; content-preservation + overflow rules; feasibility notes vs the current compositor (what renders now vs deferred: image backgrounds, multi-weight fonts, custom-font import); a state matrix; accessibility (contrast, ≥48px floor, focus order); the Theme Designer interaction spec.
- **Figma frames** (file SYQn5hFY8YVQKm3c6rw0eJ): the Theme Designer UI (New/Import/Export · Scriptures/Slides tabs · canvas + Add-content · right inspector Layout+Typography · theme list) and default template mocks for **scripture · song · lower-third**; states default/editing/applying-template/empty/import-error/save. Bound to the design-system tokens (extend, don't fork).

### Non-goals

- Any code/implementation (S8-3b/c/d). Image/gradient backgrounds + custom-font import as final (note the seam, mark deferred). Redefining product acceptance (trace to FR-010).

### Constraints

- Every FR-010 acceptance maps to a designed interaction; all listed states present; tokens reused (no forked palette); the model must be feasible on the current CPU compositor + cosmic-text shaper (flag anything that isn't); precise enough for independent build + QA.

### Assumptions and unknowns

- ASSUMED: bundled OFL font set is the only font source for MVP (custom import = FR-173, later); the designer offers only bundled families. ASSUMED: percent-of-frame units for position + size (resolution-independent). VALIDATION: the gate + S8-3b feasibility.

## Dependencies and approvals

- None blocking. The design gates S8-3b (engine). S8-2 (shaping) done.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Theme-model spec exists: data model (Theme/Layout/Region/typography/background/reference/template/per-item override), resolution-independent units, content-preservation + overflow rules | doc review | complete, implementation-ready | docs/design/THEME-MODEL-spec.md (§2 model, §3 templates+override) | PASS |
| C-002 | yes | Feasibility documented against the current compositor + cosmic-text shaper; deferred parts (image bg, multi-weight, custom fonts) flagged with seams | doc review | feasibility explicit | spec §4 Feasibility (MVP cut + deferred seams) | PASS |
| C-003 | yes | Figma: the Theme Designer UI frame designed (New/Import/Export, tabs, canvas, Add-content, Layout+Typography inspector, theme list), bound to design-system tokens | figma screenshot | frame matches the Pewbeam model, tokenised | Figma frame 204:124 (Theme Designer, element model) | PASS |
| C-004 | yes | Figma: default template mocks for scripture, song, AND lower-third (audience-output look) | figma screenshot | 3 role templates mocked | Figma frame 208:124 — Scripture/Song/Lower-third audience-output mocks | PASS |
| C-005 | yes | States covered (default/editing/applying-template/empty/import-error/save) in Figma or the spec state matrix; accessibility (contrast, ≥48px floor, focus) noted; every FR-010 acceptance maps to an interaction | doc + figma review | states + a11y + traceability complete | spec §6 state matrix + §7 a11y + §1 content⟂theme traceability | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Read back the spec doc for completeness + feasibility; screenshot the Figma frames (Theme Designer + 3 templates + states). Environment: repo + Figma MCP.

## Iteration ledger

### Iteration 1

- Target: C-001..C-005
- Change: wrote docs/design/THEME-MODEL-spec.md (data model + feasibility + states + a11y); discovered the existing model-aligned Theme Designer (20:2); built a new element-model frame 204:124 (tabs, New/Import/Export, Add-content, per-region inspector: 9-point alignment / position / dimension / lock-aspect / reference-gap + typography) + 3 audience-output template mocks 208:124 (scripture/song/lower-third), matching the design-system tokens.
- Verifier: doc review + Figma screenshots (204:124, 208:124).
- Result: all 5 criteria PASS.
- Decision: gate-review (design gates S8-3b).

## Risks and rollback

- Risk: designing beyond compositor feasibility. Mitigated: an explicit feasibility section + deferred seams. Rollback: design doc + Figma frames are non-destructive.

## Pause and escalation conditions

- The design gates the build; the user approves before S8-3b starts.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq14ud-theme-design.md --require-complete`
- Validator result: PASS --require-complete (5/5)
- Terminal state: GATE_REVIEW (design done; gates S8-3b build)
- ClickUp final evidence comment: on 86ajq14ud
