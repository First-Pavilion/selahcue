# Goal Contract — GOAL-design-settings-2.0

## Identity

- Goal ID: GOAL-design-settings-2.0
- Parent goal ID: 86ajp08bx (EPIC — Accessibility & Design System)
- Title: Design the 8 remaining Settings pages (Design 2.0) plus every meaningful state as its own full frame, grounded in the PRD
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxucue
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 20
- Independent verification required: yes

## Objective

In the Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, produce Design-2.0 high-fidelity frames for the 8 undesigned Settings pages (General, Scripture & Translations, Outputs & Displays, Network & Mobile, Appearance, Security, Storage & Backups, About & Licensing) — each visually consistent with the existing Providers & Privacy page (`338:124`), each with its non-default states as their own full frames — accompanied by a repository design handoff that traces every control to a requirement and specifies accessibility, states, and design-system usage precisely enough to implement and QA without guessing.

## Baseline

- The Settings sidebar (`338:137`, within frame `338:124` "Settings — Design 2.0") lists 9 pages. Only **Providers & Privacy** has content designed. The other 8 pages have no frames.
- Design 2.0 visual language and tokens are established (DESIGN-TOKENS.md `--sc-*`; reference page `338:124`). `bg/panel #171b22` is the only bound Figma variable; other values are literal hex.
- Product requirements for each page were mined from the PRD/architecture/UX docs + implemented code (see Inputs). A PRD-vs-code discrepancy exists for scripture translations (KJV).
- No prior ClickUp task existed for this design; task `86ajxucue` was created under epic `86ajp08bx`.

## Inputs and evidence sources

- Figma reference: `338:124` (Settings — Providers & Privacy), sidebar `338:137`
- docs/product/prds/SelahCue-PRD.md (FR/NFR)
- docs/architecture/ARCHITECTURE.md
- docs/design/DESIGN-2.0-HANDOFF.md (§5.7 defines the 9-page sidebar), DESIGN-TOKENS.md, UX-CANONICAL.md, UX-STATE-MATRIX.md, NAV-IA-spec.md, COMPONENT-SPECS.md, THEME-MODEL-spec.md
- Implemented code: selahcue-scripture (Translation::ALL), selahcue-data (open_encrypted, backup_to, integrity_check), selahcue-desktop/src/keys.rs, selahcue-lan (cert fingerprint)
- Research report (this session): per-page content spec with FR citations

## Scope

### In scope

- 8 default (happy-path) Settings page frames at Design 2.0 fidelity, reusing the reference chrome + component primitives.
- Every meaningful non-default state per page (empty, loading, error, permission-denied, destructive-confirm, recovery) as its own full-page frame.
- Accessibility annotations (contrast, keyboard/focus order, screen-reader semantics, touch targets, reduced motion) and content/copy for labels, help, errors, destructive confirmations.
- A repository design handoff doc with per-page/per-state Figma node IDs and an FR/NFR traceability table.
- A visible annotation on the Scripture page flagging the PRD/OD-24-vs-code KJV discrepancy.

### Non-goals

- Re-designing the existing Providers & Privacy page or the global app shell.
- Designing the dedicated Screens & Outputs (`327:124`) or Remote Control · Devices (`359:124`) surfaces — Settings links out to them.
- Implementing any of the settings in code (frontend/backend). This is design only.
- Resolving the KJV product discrepancy (flag only; product owns the decision).
- Adding a light/dark UI colour-mode switch (a SelahCue "theme" is a slide template, not a colour mode).

### Constraints

- Match the established Design 2.0 tokens and existing component primitives; introduce no new pattern language.
- Deferred (R2–R5) controls are shown as honest "later" affordances, not omitted or faked.
- Administrator-gated controls are hidden (removed from tab order) for non-admins, never greyed-teased.
- Emergency chrome (BLACKOUT / CLEAR-ALL footer + global chords) persists and is never occluded by a settings modal.
- Writes go into the existing Figma file additively (new frames beside `338:124`); existing frames are not mutated.

### Assumptions and unknowns

- ASSUMED: full high-fidelity in the same Figma file is wanted (owner said "build the others also"). Owner: user (confirmed this session).
- ASSUMED: "every state as its own full frame" means every *meaningful* enumerated state per the state matrix, not a combinatorial explosion. Owner: ui-ux-designer, reviewed by user.
- UNKNOWN: final scripture translation set (PRD vs code). Owner: product-manager. Design reflects shipped code + flags the conflict.

## Dependencies and approvals

- Figma MCP (desktop app) connection — required for reads/writes. Status: connected.
- ClickUp MCP — required for task evidence. Status: connected (task 86ajxucue).
- Independent design-QA pass — owner: qa-engineer / code-reviewer (design review against the state matrix). Status: pending.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All 8 default Settings page frames exist in Figma, each with the correct sidebar active-item and Design-2.0 chrome | get_metadata on the Settings section lists 8 new named page frames; get_screenshot of each | 8 frames named "Settings · <Page> — Design 2.0", each showing the correct active nav item + top bar | Figma node IDs table in handoff; screenshots in scratchpad | PASS |
| C-002 | yes | Each default page's content is populated with the requirement-traced sections/controls (not placeholder) | Visual review of each frame screenshot against the per-page spec | Every section listed in the handoff's per-page spec is visibly present on its frame | Screenshots + handoff per-page spec | PASS |
| C-003 | yes | Every enumerated non-default state has its own full-page frame | State matrix in handoff maps each state → a Figma node ID; get_screenshot confirms each | 100% of enumerated states have a corresponding frame that renders the state delta | State matrix table (handoff) + screenshots | PASS |
| C-004 | yes | Every control traces to a requirement (FR/NFR/doc) or is explicitly labelled Assumed | Traceability table in handoff reviewed for completeness | No control lacks a source tag; Assumed items are marked | docs/design/SETTINGS-2.0-HANDOFF.md traceability table | PASS |
| C-005 | yes | Accessibility is specified and testable (contrast, keyboard/focus order, SR semantics, ≥44px targets, reduced motion) | Review of the handoff accessibility section + on-frame annotations | Each page has explicit a11y annotations; contrast values cite tokens audited AA | Handoff a11y section + annotation layer | PASS |
| C-006 | yes | Design-system primitives are reused; no invented pattern language | Review that all controls map to COMPONENT-SPECS §4 primitives / reference-page components | Every control type is one of the specced primitives; deviations justified | Handoff design-system-usage section | PASS |
| C-007 | yes | The Scripture page visibly flags the PRD/OD-24-vs-code KJV discrepancy | get_screenshot of the Scripture frame; handoff note | An on-frame annotation + a handoff note describe the conflict and the design choice | Scripture frame screenshot + handoff | PASS |
| C-008 | yes | Deferred (R2–R5) controls are shown as honest "later" affordances | Review of frames + handoff release-tag column | Deferred controls render with a visible "later/Rn" treatment, not hidden or faked | Screenshots + handoff release tags | PASS |
| C-009 | yes | A repository handoff doc exists, precise enough to implement + QA without guessing, with per-page/per-state node IDs | File exists; review for node IDs, copy, states, tokens | docs/design/SETTINGS-2.0-HANDOFF.md present and complete | docs/design/SETTINGS-2.0-HANDOFF.md | PASS |
| C-010 | yes | Independent design-QA review confirms state/requirement coverage with no critical gaps | Independent reviewer (qa/code-reviewer subagent) checks frames + handoff vs state matrix and requirements | Review returns no critical (must-fix) coverage gaps, or gaps are resolved | Review report appended to handoff / ClickUp comment | PASS |
| C-011 | yes | ClickUp task 86ajxucue carries goal ID, engine, iteration evidence, node IDs and terminal state | Inspect task comments | Start comment + final evidence comment present with links | ClickUp task 86ajxucue | PASS |
| C-012 | no | Screenshots of all frames archived for review | Files exist in scratchpad | One PNG per frame | scratchpad/settings-2.0/*.png | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-frame `get_screenshot` reviewed against the per-page spec + state matrix; handoff traceability table cross-checked against the frames.
- Broader regression verification: confirm no existing frame was mutated (existing node IDs unchanged); confirm token/contrast values match audited AA tokens; confirm emergency-chrome invariant present on every frame.
- Independent verifier: a qa-engineer / code-reviewer subagent performs a design-QA pass against UX-STATE-MATRIX and the PRD FR list; the implementing role does not self-certify C-010.
- Required environment: Figma desktop app connected via MCP; repository working tree.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-011)
- Hypothesis: a validated contract + ClickUp task + build-ready specs are prerequisites to any frame build.
- Change or investigation: researched requirements; created task 86ajxucue; authored this contract.
- Verifier executed: python3 scripts/validate_goal_contract.py (pending run)
- Result: pending
- New evidence: task 86ajxucue; research report
- Decision: iterate

### Iteration 2 — build

- Target criteria: C-001..C-009
- Change: extracted the reference component styling from `338:124`; built a helper library that clones the reference chrome and rebuilds the content column; built 8 default page frames + 43 state frames (51 total) reusing Design-2.0 tokens/components; wrote `docs/design/SETTINGS-2.0-HANDOFF.md` with node IDs, FR trace, state matrix, a11y.
- Verifier executed: per-frame `get_screenshot` reviewed against per-page specs.
- Result: 51 frames present and populated; node IDs recorded.
- New evidence: Figma section `593:124`; handoff doc; NODE-IDS.
- Decision: iterate (independent QA)

### Iteration 3 — independent QA + fixes

- Target criterion: C-010 (and defects it surfaced)
- Change: ran an 8-reviewer design-QA workflow over all 51 frames (visual/state/copy/a11y/design-system). Fixed 6 critical (collapsed dialogs), 6 major (state contradictions), and ~13 minor findings; documented the rest as accepted polish. Re-verified fixed frames by screenshot.
- Verifier executed: design-QA workflow (`wf_454c75b7-ad1`) + targeted re-screenshots (change-passphrase `590:1280`, restore `591:1102`, Outputs permission `587:1629`).
- Result: no outstanding critical/major; coverage complete.
- New evidence: QA report + fix log appended to handoff §9.
- Decision: complete

## Risks and rollback

- Risks: (1) large frame count → partial completion; mitigate by building + verifying page-by-page so progress is real. (2) Figma MCP write errors mid-build; mitigate with clone-of-reference base + incremental verification. (3) inventing settings that contradict the product; mitigate with FR tracing + independent QA.
- Rollback or recovery: new frames are additive; any faulty frame can be deleted without touching existing designs. The handoff doc is version-controlled.

## Pause and escalation conditions

- Pause and escalate to product-manager if the KJV discrepancy blocks the Scripture layout (it should not — design reflects code + flags).
- Pause if Figma MCP disconnects (BLOCKED with the connection requirement).
- Escalate scope changes (e.g. designing the linked-out surfaces) through product/delivery rather than absorbing silently.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-design-settings-2.0.md --require-complete
- Validator result: PASS (all mandatory criteria PASS)
- Independent verification result: 8-reviewer design-QA workflow ran; 6 critical + 6 major resolved and re-verified; remaining minors documented/accepted.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted to task 86ajxucue
