# Goal Contract — GOAL-design-account-setup

## Identity

- Goal ID: GOAL-design-account-setup
- Parent goal ID: 86ajp08bx (EPIC — Accessibility & Design System)
- Title: Design the desktop Account setup page (account activation + licensing/entitlement status) at Design-2.0 fidelity — every meaningful state as its own full frame — grounded in DEC-004 and the Platform API activation contract
- Role: ui-ux-designer
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy600r
- Created: 2026-08-09
- Updated: 2026-08-09
- Maximum iterations: 16
- Independent verification required: yes

## Objective

In the Figma file `SYQn5hFY8YVQKm3c6rw0eJ`, produce Design-2.0 high-fidelity frames for the SelahCue **desktop** Account setup experience — the flow by which a church activates an install against its SelahCue account and sees its licensing/entitlement status — covering the first-run activation entry (focused screen) and the in-Settings **Account** page, with every meaningful state (signed-out/chooser, sign-in, enrollment-key, activating, activated, invalid-key, instance-limit, expired/not-yet-active, offline, deactivate/type-to-confirm, admin-gated) as its own full frame; accompanied by a repository handoff that traces every control to DEC-004 + the relevant FR/NFR and the Platform API activation contract, and specifies accessibility, states, copy, and design-system usage precisely enough to implement and QA without guessing. Live presentation must never read as blocked by account/licensing state (NFR-024/NFR-015/CON-2).

## Baseline

- The Settings surface (`338:124` "Settings — Design 2.0" + the Settings-2.0 section `593:124`) has a **9-item sidebar** (General, Providers & Privacy, Scripture & Translations, Outputs & Displays, Network & Mobile, Appearance, Security, Storage & Backups, About & Licensing). There is **no Account page** and **no first-run activation** screen.
- Providers & Privacy (`338:124`) is the reference chrome (top bar, left sidebar, deep-ink base) and owns the cloud AI/transcription features that depend on the account; it links to Account for the account/device/entitlement relationship.
- DEC-004 (2026-08-09) fixes the licensing model: account-identity spine + account-bound device *instances* + activation-cached offline entitlement. Enrollment key is an optional bootstrap token, not the primary unit.
- The Platform API device-activation slice is implemented (`POST /v1/activations`, `GOAL-be-api-device-activation`, task 86ajy5v7h): activation sends enrollment key + device fingerprint + platform + app_version + display_name + idempotency key and receives a Device instance (device_public_id, platform, display_name, status) + a show-once device token (masked triple, issued_at, expires_at, timezone) + license validity (device_limit = instance limit, starts_at, expires_at, status). Errors: NOT_FOUND (unknown/invalid key), POLICY_DENIED (instance-limit reached / expired / not-yet-started / revoked / suspended), plus client-side offline/unreachable.
- Open owner decisions (deferred, flagged): account sign-in / customer IdP; signed policy-envelope crypto + offline-grace duration; plan tiers/price points.

## Inputs and evidence sources

- Figma reference: `338:124` (Settings — Providers & Privacy), sidebar `338:137`; Settings-2.0 section `593:124`.
- docs/decisions/DECISION-LOG.md DEC-004 (authoritative licensing model).
- docs/product/prds/SelahCue-PRD.md — NFR-015 (offline), CON-2 (offline core), NFR-024 (output-failure isolation / never-blank), FR-137 (consent/retention admin-gated), FR-176/FR-177 (privacy policy / DPA + cross-border), FR-132 (cloud opt-in).
- implementation/api device-activation slice: `apps/devices/models.py` (Device, DeviceToken, DeviceStatus), `apps/devices/services.py` (activate_device, error mapping), `apps/license_keys` (device_limit, statuses, validity window), README open decisions.
- docs/delivery/goals/GOAL-be-api-device-activation.md (activation contract + error map).
- docs/design/SETTINGS-2.0-HANDOFF.md (tokens, chrome, component primitives, a11y conventions), DESIGN-2.0-HANDOFF.md.

## Scope

### In scope

- First-run activation entry as its own focused full-screen frame (chooser: sign in to SelahCue account OR enter organisation enrollment key), with an honest "works offline — activate anytime" affordance. A fresh install has no account yet, so this is a distinct entry from the in-Settings page.
- Sign-in path (email + continue) and enrollment-key path (key entry) frames.
- Activating (loading) frame.
- In-Settings **Account** page (default, activated): device name + platform, "instance N of M", plan name, license validity (valid through …), offline-grace status ("works offline for N more days"), cloud-connected status, links to "Manage devices" + "Providers & Privacy". Adds an **Account** item to the Settings sidebar (additive, does not mutate existing frames).
- Error frames: invalid/unknown key (inline), instance-limit reached (+ manage-devices path), license expired / not-yet-active (renew/contact), offline (honest: keeps working; activate later — never reads as "app broken").
- Deactivate / sign out this device (type-to-confirm destructive dialog).
- Admin-gated variant (account changes Administrator-only, consistent with FR-137).
- Accessibility annotations (contrast, keyboard/focus order, SR semantics, ≥44px targets, reduced motion) and copy for all labels/help/errors/empty/loading states.
- A repository handoff doc with per-frame node IDs, an FR/DEC traceability table, and the state matrix.

### Non-goals

- Re-designing Providers & Privacy, the Settings-2.0 pages, or the global app shell.
- Designing the dedicated "Manage devices" surface (Account links out to it); a device-list management console is a separate story.
- Implementing any activation/account code (frontend/backend). Design only.
- Resolving deferred owner decisions (account IdP, policy-envelope crypto, offline-grace duration, plan tiers/pricing) — reflect the decided model, flag the open items.
- Mobile controller account UI (this is the desktop/operator app).

### Constraints

- Match Design-2.0 tokens (`--sc-*`, deep-ink) and reuse the existing component primitives; introduce no new pattern language. Clone the Settings shell chrome from `338:124`.
- Account/licensing state must **never** block or imply blocking of live presentation (NFR-024/NFR-015/CON-2) — the offline and error frames must state the app keeps working.
- The enrollment key is an *optional* bootstrap token, not the primary unit — sign-in and key entry are co-equal activation paths (DEC-004).
- Never render a full/secret token or key on screen; show masked values only (mirrors the show-once backend contract).
- Admin-gated controls are hidden/locked for non-admins, never greyed-teased into revealing structure (FR-137 pattern).
- Writes go into the existing Figma file additively (new frames beside the Settings section); existing frames are not mutated.

### Assumptions and unknowns

- ASSUMED: full high-fidelity in the same Figma file, one frame per meaningful state (consistent with the Settings-2.0 owner decision). Owner: user.
- ASSUMED: first-run activation is a focused full-screen entry (not the emergency-footer app shell), shown before the operator console when no cached entitlement exists. Owner: ui-ux-designer.
- ASSUMED: offline-grace copy uses "works offline for N more days" phrasing; the actual grace duration is an open owner decision (shown as a token value, data-driven). Owner: product.
- UNKNOWN: account sign-in / customer IdP is not yet built (enrollment-key activation is the shipped path). Design shows both paths; the sign-in path is marked as depending on the IdP decision. Owner: product.

## Dependencies and approvals

- Figma MCP (desktop app) connection — required for reads/writes. Status: connected.
- ClickUp MCP — required for task evidence. Status: connected.
- DEC-004 — decided (authoritative). Platform API activation slice — implemented (86ajy5v7h).
- Independent design-QA pass — owner: independent reviewer subagent; not self-certified.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The in-Settings Account page default (activated) frame exists at Design-2.0 fidelity, cloning the reference chrome with an **Account** sidebar item active | get_screenshot of the frame | Frame shows the Settings shell (top bar + sidebar incl. Account active) + activated device/plan/entitlement content | A8 `659:124`; handoff §4.9 | PASS |
| C-002 | yes | The first-run activation entry exists as a focused full-screen frame offering both sign-in and enrollment-key paths + an honest "works offline" affordance | get_screenshot | A chooser frame presents both activation paths and the offline note | A0 `652:124`; handoff §4.1 | PASS |
| C-003 | yes | Every enumerated state has its own full frame: chooser, sign-in, enrollment-key, activating, activated, invalid-key, instance-limit, expired/not-yet-active, offline, deactivate-confirm, admin-gated | State matrix in handoff maps each → node ID; get_screenshot confirms each | 100% of enumerated states have a corresponding frame rendering the state delta | Handoff §5 state matrix (11 frames); screenshots | PASS |
| C-004 | yes | Offline + every error frame make clear the app keeps working / live presentation is not blocked (NFR-024/NFR-015/CON-2) | Visual review of offline + error frames | Each carries explicit reassurance copy; none reads as "app broken/blocked" | A4/A5/A6/A7 + A8 footer + A9 banner; QA §10 criterion 1 PASS | PASS |
| C-005 | yes | Both activation paths are co-equal (sign-in + enrollment key), enrollment key labelled optional/bootstrap; no full key/token rendered (masked only) | Visual review of chooser + key + activated frames | Both paths present; key marked optional; only masked token/plan values shown | A0/A1/A2; no device token rendered (QA §10 crit 2+3 PASS) | PASS |
| C-006 | yes | Every control/field traces to DEC-004 + a requirement (FR/NFR) or the activation contract, or is labelled Assumed | Traceability table in handoff reviewed | No control lacks a source tag; Assumed items marked | Handoff §6 traceability table | PASS |
| C-007 | yes | Accessibility specified + testable (contrast tokens AA, keyboard/focus order, SR semantics, ≥44px targets, reduced motion, type-to-confirm modal semantics) | Review of handoff a11y section + annotations | Each frame has explicit a11y annotations; contrast cites audited tokens | Handoff §7 | PASS |
| C-008 | yes | Design-system primitives reused; no invented pattern language (banner/card/input/select/badge/toggle/type-to-confirm from COMPONENT-SPECS) | Review of frames vs reference primitives | Every control maps to a specced primitive; deviations justified | Handoff §3; cloned reference chrome `338:124` | PASS |
| C-009 | yes | Admin-gated variant hides/locks account changes for non-admins (FR-137) without greying-teasing structure | get_screenshot of the admin-gated frame | Non-admin frame removes/locks change controls + shows the neutral managed-by-admin line | A10 `666:124`; handoff §4.11 (QA crit 5 PASS) | PASS |
| C-010 | yes | A repository handoff doc exists, precise enough to implement + QA without guessing, with per-frame node IDs, DEC/FR trace, state matrix, copy | File exists; review | docs/design/ACCOUNT-SETUP-HANDOFF.md present + complete | docs/design/ACCOUNT-SETUP-HANDOFF.md | PASS |
| C-011 | yes | Independent design-QA review confirms state/requirement coverage with no unresolved critical/major gaps | Independent reviewer subagent checks frames + handoff vs the state matrix, DEC-004, and the never-blank invariant | Review returns no unresolved critical/major, or they are fixed + re-verified | Handoff §10: PASS, 0 critical/0 major; 2 minors fixed, 2 accepted | PASS |
| C-012 | yes | ClickUp task carries goal ID, engine, iteration evidence, node IDs, and terminal state | Inspect task comments | Start + final evidence comments present with links | ClickUp 86ajy600r start + final comments | PASS |
| C-013 | no | Screenshots of all frames archived for review | Files exist in scratchpad | One PNG per frame | Inline per-frame screenshots reviewed during build; node IDs (§4/§5) are the durable archive | PASS |
| C-014 | no | Goal Contract structural validator passes | `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-design-account-setup.md` | Exits 0 | validator output (final eval) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-frame `get_screenshot` reviewed against the per-frame spec + state matrix; handoff traceability table cross-checked against the frames and the activation contract.
- Broader regression verification: confirm no existing frame was mutated (existing node IDs unchanged); confirm token/contrast values match audited AA tokens; confirm the never-blank/offline invariant copy is present on every error + offline frame.
- Independent verifier: an independent reviewer subagent performs a design-QA pass against the state matrix, DEC-004, the activation contract, and the never-blank invariant; the implementing role does not self-certify C-011.
- Required environment: Figma desktop app connected via MCP; repository working tree.

## Iteration ledger

### Iteration 1

- Target criterion: setup (C-012, C-014)
- Hypothesis: a validated contract + a registered ClickUp task + grounding in DEC-004 and the activation contract are prerequisites to any frame build.
- Change or investigation: read DEC-004, the device-activation slice (models/services/goal), the Settings-2.0 handoff + reference chrome; authored this contract; creating the ClickUp task.
- Verifier executed: python3 scripts/validate_goal_contract.py → PASS (14 criteria, 12 mandatory)
- Result: setup complete; ClickUp 86ajy600r created + linked (epic 86ajy5v6k, slice 86ajy5v7h, Settings story 86ajxucue), start comment posted.
- New evidence: reference metadata + screenshot; activation contract fields; section `651:124`.
- Decision: iterate (build)

### Iteration 2 — build

- Target criteria: C-001..C-010
- Change: built Design-2.0 section `651:124` with 11 additive frames — 8 focused first-run frames (A0 chooser `652:124`, A1 sign-in `654:124`, A2 enrollment-key `654:157`, A3 activating `655:124`, A4 invalid-key `655:144`, A5 instance-limit `656:124`, A6 expired/not-yet-active `656:151`, A7 offline `657:124`) built fresh on the deep-ink base with a reusable helper set, and 3 in-Settings frames cloned from the reference chrome `338:124` with an added active **Account** sidebar item (A8 activated `659:124`, A9 deactivate type-to-confirm `665:124`, A10 admin-gated `666:124`). Wrote `docs/design/ACCOUNT-SETUP-HANDOFF.md` (per-frame specs, DEC/FR/contract trace, state matrix, a11y, copy deck, open questions). No existing frame mutated.
- Verifier executed: per-frame `get_screenshot`/inline screenshot reviewed against the per-frame spec; section-bounds check confirmed 11 frames gridded with no overlaps.
- Result: all frames present + populated; node IDs recorded.
- Decision: iterate (independent QA)

### Iteration 3 — independent QA + fixes

- Target criterion: C-011 (+ defects surfaced)
- Change: dispatched an independent reviewer subagent (read-only) to inspect all 11 frames vs the state matrix, DEC-004, the `apps/devices` activation contract, and the never-blank invariant. Verdict PASS — 0 critical, 0 major, 4 minor. Fixed 2 minors (A7 amber-emoji icon → neutral `◇`; handoff §4 masked-key wording reconciled for the A4 error-echo case); 2 accepted/flagged (A0 sign-in leads the not-yet-shipped IdP path — already in §9.1; §10 filled). Re-verified A7 by screenshot.
- Verifier executed: independent subagent review; targeted re-screenshot (A7).
- Result: no outstanding critical/major; coverage complete.
- New evidence: handoff §10 QA writeup.
- Decision: complete

## Risks and rollback

- Risks: (1) implying account/licensing can block live output — mitigated by the C-004 never-blank criterion + explicit reassurance copy on every error/offline frame. (2) rendering a secret key/token — mitigated by masked-only constraint (C-005). (3) inventing settings that contradict the shipped activation contract — mitigated by tracing to `apps/devices` + DEC-004 and independent QA. (4) mutating existing Figma frames — mitigated by additive-only writes verified against existing node IDs.
- Rollback or recovery: new frames are additive; any faulty frame can be deleted without touching existing designs. The handoff doc is version-controlled.

## Pause and escalation conditions

- Pause and escalate to product-manager if a state cannot be honestly designed without an undecided owner input (account IdP, offline-grace duration) — reflect the decided model + flag the open item rather than inventing policy.
- Pause if Figma MCP disconnects (BLOCKED with the connection requirement).
- Escalate scope changes (e.g. designing the linked-out Manage-devices surface) through product/delivery rather than absorbing silently.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-design-account-setup.md --require-complete
- Validator result: PASS (all 12 mandatory criteria PASS; 2 optional PASS)
- Independent verification result: independent design-QA subagent — PASS, 0 critical / 0 major; 2 minors fixed + re-verified, 2 accepted/flagged.
- Terminal state: VERIFIED_COMPLETE
- Remaining failed or blocked criteria: none. Deferred/flagged for product (not blockers): account sign-in / customer IdP; offline-grace duration; "Manage devices" in-app console; plan tiers/pricing (OD-04).
- ClickUp final evidence comment: posted to task 86ajy600r
