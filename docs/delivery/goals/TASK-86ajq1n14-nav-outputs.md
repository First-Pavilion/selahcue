# Goal Contract — TASK-86ajq1n14-nav-outputs

## Identity

- Goal ID: TASK-86ajq1n14-nav-outputs
- Parent goal ID: STAGE8-core-presentation
- Title: Design the app navigation/menu + move the Output manager to its own surface (Figma + IA spec, no code)
- Role: ui-ux-designer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajq1n14
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 6
- Independent verification required: no (design gate is the user)

## Objective

The app is gaining surfaces (live Operator Console, Theme Designer, Displays & Outputs, Plan/Library, Settings) but has no navigation, and the Output manager is crammed into a console right-zone `aside`. Design (1) the **menu/navigation pattern** that reaches every surface while keeping the pinned emergency footer + canonical keymap intact and live controls always reachable, and (2) move the **Output manager into its own surface** (modal/page) with only a compact status left in the console. Design + spec only.

## Baseline

Verified: `dist/index.html` — a bare `<header><h1 id="plan-name">SelahCue Operator</h1></header>` (no nav), the OBS 3-zone `<main>`, an `<aside aria-label="Outputs">` (outputs list + Identify) + the new theme picker `aside`, and a pinned `<footer id="emergency">`. Figma frames: `165:124` (shipped OBS console), `204:124` (Theme Designer S8-3a), `28:2` ("SelahCue — Displays & Outputs" — an existing page to build on). Design tokens: `DESIGN-TOKENS.md`/`tokens.rs`. Emergency-pierce + canonical-keymap invariants are pinned by tests (must not break).

## Inputs and evidence sources

- Story 86ajq1n14 + epic 86ajp08bx (Accessibility & Design System); COMPONENT-SPECS.md; UX-CANONICAL.md; DESIGN-TOKENS.md; dist/index.html; Figma 165:124/204:124/28:2; FR-014/040/151.

## Scope

### In scope

- **Nav/menu design (Figma + spec):** choose + design the pattern (recommend a **top-bar app menu**) reaching Live Console (home) · Theme Designer · Displays & Outputs · Plan/Library · Settings; states default/open/active-surface; keyboard + focus + SR semantics; the emergency footer + live controls persist on every surface.
- **Output manager → own surface (Figma + spec):** move the console Outputs `aside` into its own modal/page (build on `28:2`): role-assignment rows + display pickers + Identify + drag-arrange + per-output settings; states empty/assigned/mismatch/identify-active. Leave a **compact read-only outputs status** + a **"Manage outputs"** entry in the console.
- Bind to the design-system tokens; an IA/nav handoff spec (`docs/design/NAV-IA-spec.md`).

### Non-goals

- Any code/implementation (a follow-up frontend story). Redesigning the console's live zones. Building the Settings/Plan-Library surfaces (only the menu ENTRY to them).

### Constraints

- Emergency footer + canonical keymap intact + live controls reachable on every surface; tokens reused (no fork); every surface ≤1 action from the console; precise enough to implement without guessing.

### Assumptions and unknowns

- ASSUMED (owner to confirm at the gate): a top-bar app menu (vs a left nav rail); the Output manager as a full-page surface (vs a modal overlay). VALIDATION: the gate.

## Dependencies and approvals

- None blocking. Informs a later frontend implementation story + S8-3c (Theme Designer UI reached via this menu).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Nav/menu pattern chosen + designed in Figma (reaches all 5 surfaces; states default/open/active); rationale recorded | figma + doc | menu frame + spec | Figma 212:124 (menu open, 5 surfaces + accesskeys) + NAV-IA-spec §1 | PASS |
| C-002 | yes | Emergency footer + live controls + canonical keymap remain reachable on every surface (shown/annotated); keyboard + focus + SR specified | doc + figma review | reachability + a11y specified | Figma 212:124 (pinned emergency footer annotated) + NAV-IA-spec §2 + §5 | PASS |
| C-003 | yes | Output manager designed as its own surface (modal/page) on 28:2: assignment rows + pickers + Identify + arrange + per-output settings; states empty/assigned/mismatch/identify | figma | manager frame + states | **Figma 215:124 — redesigned "Output settings" page** (per-output enable toggle + Select theme / Output monitor / Output format; enabled/disabled/mismatch states) + NAV-IA-spec §3/§3a (per-output theme) | PASS |
| C-004 | yes | Console de-cluttered: a compact read-only outputs status + a "Manage outputs" entry replace the Outputs aside (designed) | figma | compact console status | Figma 212:124 compact outputs status + "Manage outputs" route + NAV-IA-spec §4 | PASS |
| C-005 | yes | Bound to design-system tokens (no fork); IA/nav spec is implementation-ready; decisions trace to the requirements | doc review | tokenised + spec complete | NAV-IA-spec.md (tokens bound; §6 handoff) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Read the IA/nav spec for completeness; screenshot the Figma frames (menu open + active-surface, the output-manager surface + states, the console compact status). Environment: repo + Figma MCP.

## Iteration ledger

### Iteration 1

- Target: C-001..C-005.
- Change: wrote docs/design/NAV-IA-spec.md (top-bar app-menu decision + emergency/keymap invariants on every surface + Output-manager-as-its-own-surface reusing 28:2 + states + a11y + handoff); built Figma 212:124 (app menu OPEN with 5 surfaces + accesskeys, the compact console outputs status with the mismatch state + "Manage outputs" route, and the pinned emergency footer). The Output-manager page already exists at 28:2 — this adds the navigation glue + de-clutters the console.
- Verifier: doc review + Figma screenshot (212:124) + the existing 28:2.
- Result: all 5 criteria PASS.
- Decision: gate-review (design gates a frontend impl story).

### Iteration 2 — owner refine (menu decision · easy output manager · shrink-to-fit)

- Target: refine per owner direction.
- Change: (a) **committed the top-bar app menu** with a UX rationale vs the rejected left-rail (NAV-IA §1). (b) **Redesigned the Output manager** into an easy per-output "Output settings" page matching the owner's screenshot — Figma **215:124** (per-output enable toggle → Select theme / Output monitor / Output format; Advanced disclosure; enabled/disabled/mismatch states) + **per-output theme** established as the model (NAV-IA §3/§3a; flags a per-output-theme engine follow-up). (c) **Fit control** — relabelled the Theme Designer inspector (204:124) to **Fit: Shrink to fit (default) / Clip / Paginate**; THEME-MODEL-spec §2/§4/§5 makes **ShrinkToFit the default overflow for all built-ins** (resolves the S8-3b lower-third clip finding), user-selectable.
- Verifier: Figma screenshots (215:124 output settings; 204:140 Fit control) + spec review.
- Result: criteria remain PASS; the output-manager evidence now points to 215:124 (supersedes 28:2).
- Decision: gate-review. Engine shrink-to-fit + per-output theme are implementation follow-ups (backend).

## Risks and rollback

- Risk: a menu that hides emergency controls. Mitigated: the emergency footer stays pinned on every surface (explicit invariant + annotation). Rollback: design artefacts are non-destructive.

## Pause and escalation conditions

- The pattern choice (top-bar menu vs nav rail) + output-manager form (page vs modal) are surfaced at the gate for owner confirmation.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajq1n14-nav-outputs.md --require-complete`
- Validator result: PASS --require-complete (5/5)
- Terminal state: GATE_REVIEW (design done; gates a frontend impl story)
- ClickUp final evidence comment: on 86ajq1n14
