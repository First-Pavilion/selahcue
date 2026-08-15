# Goal Contract — GOAL-design-auth-landing-pages

## Identity

- Goal ID: GOAL-design-auth-landing-pages
- Parent goal ID: NONE
- Title: Four blocking auth/account surfaces designed to implementation-ready fidelity in Figma with a complete state matrix and a handoff doc
- Role: ui-ux-designer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: NONE — no ticket exists (workspace search 2026-08-14 returns none); pending ClickUp update recorded in §Dependencies
- Created: 2026-08-14
- Updated: 2026-08-14
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every state of the four design gaps named in `PRODUCT-GAP-AUDIT-2026-08-14.md` §11.4 — `/verify`, `/reset`,
desktop sign-up + verify-pending, and the account-portal Manage-devices page — exists as a rendered Figma frame
built from the surface's existing visual language, and a handoff doc under `docs/design/` specifies each frame's
node ID, states, user-visible copy, tokens and components precisely enough for a frontend engineer to implement
without guessing.

## Baseline

Verified 2026-08-14:

- `implementation/api/.../accounts/tasks.py:55,64` build `{FRONTEND_BASE_URL}/verify?token=` and `/reset?token=`.
  No surface serves either route (`marketing/src/router/index.ts` has no such route; `implementation/web/` is a README).
- `TRANSACTIONAL-EMAIL-spec.md` §"Open, owned elsewhere" disowns both landing pages.
- `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §5 specifies request-reset + email-sent **in prose only** — no Figma frames
  exist on page `468:124` for either (page has 16 frames; none is an auth state).
- `ACCOUNT-SETUP-HANDOFF.md` covers desktop A0–A10, sign-IN only; `GOAL-design-account-setup.md` names
  "Manage devices" as an explicit non-goal (§9.4).
- Figma `SYQn5hFY8YVQKm3c6rw0eJ` has 5 pages. Marketing frames bind fills to the local `SelahCue Color`
  collection (19 vars, legacy layer); Design-2.0 desktop frames in section `651:124` use raw Design-2.0 hex
  (0 bound fills on `652:124`).
- Account frame `506:124` already contains a device summary (`506:210`), an activation meter (`506:204`) and a
  **"Manage devices"** button (`506:223`) that leads nowhere — the target page is undesigned.

## Inputs and evidence sources

- `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md` §11.3, §11.4
- `docs/design/DESIGN-2.0-HANDOFF.md`, `DESIGN-TOKENS.md`, `ACCOUNT-SETUP-HANDOFF.md`,
  `MARKETING-PORTAL-GAP-FILL-HANDOFF.md`, `TRANSACTIONAL-EMAIL-spec.md`
- `implementation/api/selahcue_api/apps/accounts/{services.py,tasks.py}`, `graphql/account_schema.py`,
  `apps/devices/models.py`, `selahcue_api/settings.py`
- `implementation/marketing/src/{router/index.ts,views/SignInView.vue,views/AccountView.vue,assets/styles/tokens.css}`
- Figma nodes `505:124`, `506:124`, `652:124`, `654:124`, `468:124`, `651:124`

## Scope

### In scope

- `/verify` email-verification landing (web, marketing SPA) — all states incl. 24h TTL expiry + resend
- `/reset` set-new-password landing (web) — all states incl. 1h TTL expiry, password rules at 10 chars
- Desktop sign-up frame + verify-email-pending state, matching A0–A10 conventions
- Manage devices page (web account portal) — list, per-device deactivate + confirm, at-limit, empty, error
- One handoff doc under `docs/design/` with node IDs, state matrix, full copy deck, token/component references

### Non-goals

- Checkout, plan-change, payment-method, dunning, tax flows (blocked on an undecided commercial model)
- Admin console elevation (v0.1 gate draft pending a Platform PRD)
- Mobile/tablet breakpoint frames (GAP-07 — tracked separately)
- Any code change; any git commit
- Creating ClickUp tickets (PM-owned, requires owner approval)

### Constraints

- Reuse the existing visual language of the target surface. Web frames bind to the existing `SelahCue Color`
  variables exactly as `505:124` does; desktop frames use the Design-2.0 hex used by `652:124`/`654:124`.
- "Theme" is never used to mean a light/dark colour mode (a SelahCue theme is a slide-design template).
- Auto-layout cards hug via `layoutSizingVertical='HUG'`, never `resize(w, 10)`.
- Copy must not create an account-existence oracle (matches the API's deliberate no-enumeration design).

### Assumptions and unknowns

- **Verified:** verification TTL 24h, reset TTL 1h, `ACCOUNT_MIN_PASSWORD_LENGTH = 10`, max 200, length-only policy.
- **Verified:** `verify_email` and `confirm_password_reset` collapse unknown/consumed/expired/wrong-purpose to a
  single `VALIDATION_FAILED` — the client **cannot** distinguish invalid from expired today.
- **Verified:** no resend-verification mutation exists in `account_schema.py`.
- **Verified:** `Device` has no `last_seen_at` field.
- **Assumed:** the portal Manage-devices route is `/account/devices`; owner to confirm.

## Dependencies and approvals

- Backend `resendVerification` mutation — owner: backend; status: **does not exist**, design depends on it
- Backend expired-vs-invalid discrimination for token failures — owner: backend/security; status: **open decision**
- `Device.last_seen_at` (or an equivalent) — owner: backend; status: **does not exist**
- ClickUp ticket for this design work — owner: PM/owner; status: **none exists**, pending update below

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every `/verify` state (verifying, success, link-not-valid, expired+resend, resend-sent, missing-token) exists as a distinct rendered Figma frame | `use_figma` structural read + per-frame screenshot | 6 frames present, visually distinct, non-empty | `743:125`, `743:139`, `746:124`, `746:148`, `746:172`, `747:124`; handoff §3.1/§4 | PASS |
| C-002 | yes | Every `/reset` state (form, validation, submitting, link-not-valid, expired, success) exists as a distinct rendered frame and the password rule reads 10 characters | screenshot + text read-back | ≥6 frames; rule string reads "At least 10 characters." | 7 frames delivered (6 required + R7 server error): `747:143`, `747:173`, `749:124`, `749:150`, `749:174`, `749:198`, `749:217`; handoff §3.2/§5 | PASS |
| C-003 | yes | Desktop sign-up + verify-pending frames exist inside section `651:124`, sized 1760×1000, on the A0–A10 grid, using the A-frame chrome | `use_figma` read of `651:124` | new children at row-4 grid slots, 1760×1000, topbar + card present | `752:124`, `752:172`, `752:219` at y=3600, x=120/2020/3920; handoff §3.3/§6 | PASS |
| C-004 | yes | Manage-devices frames exist for populated, confirm, at-limit, empty and error states in the `506:124` portal shell | per-frame screenshot | ≥5 frames, each with nav + header + sidebar + card + footer | 6 frames delivered (5 required + D6 over-limit): `753:124`, `754:124`, `754:257`, `755:124`, `755:256`, `755:385`; handoff §3.4/§7 | PASS |
| C-005 | yes | No frame contains clipped, overlapping or zero-height content at readable zoom | pairwise bounding-box overlap check + screenshots of all 22 frames | 0 overlaps; no clipped text observed | overlap check returned `[]` across 19 web frames; all 22 screenshotted and inspected | PASS |
| C-006 | yes | Handoff doc exists under `docs/design/` and enumerates node ID, state, full user-visible copy and token references per frame | read the file; cross-check node IDs resolve | every new node ID appears in the doc and resolves in Figma | `docs/design/AUTH-LANDING-PAGES-HANDOFF.md` §3 (node map) + §8 (copy deck) | PASS |
| C-007 | yes | Every copy string naming a TTL or password rule matches the API constant | grep `settings.py`; compare to the copy deck | 24h / 1h / 10 characters match `ACCOUNT_*` settings | `settings.py:269,270,273`; handoff §9 traceability table | PASS |
| C-008 | yes | Backend capabilities the design needs but that do not exist are listed as explicit dependencies, not silently assumed | read handoff §10 | resend mutation, expired-vs-invalid signal, `last_seen_at`, devices query, device deactivation each listed with owner | handoff §10.1–§10.5 | PASS |
| C-009 | yes | Web frames reuse the existing `SelahCue Color` variables; no parallel variable collection created | `getLocalVariableCollectionsAsync` before/after | still exactly 1 collection, 19 variables | read-back after final build: 1 collection / 19 vars | PASS |
| C-010 | no | Light-appearance variants produced where the design system defines both | inspect the design system | N/A — product surfaces are dark-only; only transactional email is light, deliberately | handoff §2.2 | NOT_APPLICABLE |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-frame screenshot at readable zoom after each section build; text read-back of every
  copy string that encodes a backend constant.
- Broader regression verification: `get_metadata`/`use_figma` reads on both parent containers confirming no
  pre-existing frame was mutated, moved or overlapped; variable-collection count unchanged.
- Independent verifier: a separate read-only design-QA agent against the state matrix, the API contract and the
  never-blank / no-enumeration invariants (ACCOUNT-SETUP-HANDOFF §10 protocol). **Not yet run.**
- Required environment: Figma MCP against file `SYQn5hFY8YVQKm3c6rw0eJ`.

## Iteration ledger

### Iteration 1 — evidence base

- Target criterion: C-009 plus grounding for all others
- Hypothesis: the two target surfaces use different token layers, so "match what exists" needs per-page rules
- Change or investigation: read the four handoff docs, the API account/device services, the marketing SPA; dumped
  `505:124`, `506:124`, `652:124`, `654:124`, the page list and the variable collection
- Verifier executed: `use_figma` read-only dumps; greps over `implementation/api` and `implementation/marketing`
- Result: PASS — marketing frames bind to `SelahCue Color`; Design-2.0 desktop frames use raw hex; Figma (legacy)
  and shipped Vue (`--sc-*`) token layers confirmed divergent
- New evidence: `verify_email`/`confirm_password_reset` give no expired-vs-invalid signal; no resend mutation;
  `Device` has no `last_seen_at`; `506:124` already ships a device summary + a dead "Manage devices" button
- Decision: iterate

### Iteration 2 — `/verify` (C-001)

- Target criterion: C-001
- Hypothesis: `/verify` is a continuation of `505:124` and must clone its card geometry exactly
- Change or investigation: created section `743:124`; built V1–V6
- Verifier executed: per-frame screenshots
- Result: PASS after two defect fixes — bare `createAutoLayout` frames default to a **white** fill (5 containers
  cleared); a banner's inner column collapsed because `FILL` was set before the banner itself was `FILL` in its
  parent (helper reordered to append → parent FILL → child FILL)
- New evidence: an invalid token leaves the page with no user identity, so every resend state needs its own
  email field
- Decision: iterate

### Iteration 3 — `/reset` (C-002)

- Target criterion: C-002
- Hypothesis: reset mirrors verify but must carry the shorter TTL and the 10-character rule
- Change or investigation: built R1–R7, including a server-error frame beyond the required set
- Verifier executed: screenshots of R5, R6, R7 (novel layouts); structural read of the rest
- Result: PASS
- New evidence: `confirm_password_reset` validates the password *before* the token and returns the same
  `VALIDATION_FAILED`, so a short password is indistinguishable from a dead link — client-side length validation
  is mandatory, recorded in handoff §5
- Decision: iterate

### Iteration 4 — desktop sign-up (C-003)

- Target criterion: C-003
- Hypothesis: sign-up should extend the A0–A10 grid rather than open a new section
- Change or investigation: added A11–A13 at row-4 slots; grew section `651:124` to 7700×4720
- Verifier executed: screenshots of A11, A12, A13; section read-back
- Result: PASS after one fix — `layoutPositioning='ABSOLUTE'` is rejected on children of a plain (non-auto-layout)
  frame; the topbar was rebuilt as a plain frame. Script atomicity meant nothing partial landed.
- New evidence: the no-enumeration signup response means A11 has **no** "email already registered" error and
  always proceeds to A13 — contradicting `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §4c
- Decision: iterate

### Iteration 5 — Manage devices (C-004)

- Target criterion: C-004
- Hypothesis: cloning the shipped Account page gives an exact portal shell and guarantees consistency
- Change or investigation: cloned `506:124` → D1, added a `Devices` sidebar item, replaced the content column;
  cloned D1/D3 → D2, D3, D4, D5, D6
- Verifier executed: screenshots of D1–D6; meter fill read-back
- Result: PASS after one fix — re-binding a colour variable that a **cloned** node already had bound drops to the
  literal placeholder (rendered black). Fixed by carrying the real hex in the base paint passed to
  `setBoundVariableForPaint`, then re-verifying all five meters by read-back.
- New evidence: `AccountView.vue`'s IP-address column has no backing model field (dropped); device deactivation
  has no backend code path at all (handoff §10.5)
- Decision: iterate

### Iteration 6 — handoff + close (C-005…C-009)

- Target criterion: C-005, C-006, C-007, C-008, C-009
- Hypothesis: remaining criteria are documentation plus whole-set visual QA
- Change or investigation: wrote `docs/design/AUTH-LANDING-PAGES-HANDOFF.md`; ran a pairwise overlap check; resized
  both sections to their content bounds
- Verifier executed: overlap check (0 across 19 web frames); variable-collection read-back (1 / 19); constants
  grep against the copy deck
- Result: PASS
- Decision: complete → GATE_REVIEW

## Risks and rollback

- Risks: V4/R5 (the discrete expired states) cannot be implemented until the backend exposes a distinguishing
  signal — mitigated by shipping the merged V3/R4 and flagging the decision. Resend and device deactivation have
  no backend at all — designed as target states and flagged, not faked.
- Rollback or recovery: all work is additive — one new Figma section (`743:124`), three frames appended to an
  existing section, and two new Markdown files. Deleting them restores the prior state. No pre-existing node was
  mutated; the `Devices` sidebar item and content changes live only inside cloned copies.

## Pause and escalation conditions

- Commercial-model decisions (checkout/billing) — owner: product; escalated, not designed.
- Exposing a distinguishable `EXPIRED` token error — owner: product + security; it changes the no-oracle posture.
- ClickUp ticket creation — owner: PM/owner; not created unilaterally (handoff §15).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/GOAL-design-auth-landing-pages.md`
- Validator result: PASS (10 criteria, 9 mandatory)
- Independent verification result: **not yet run** — required before acceptance (handoff §16)
- Terminal state: **GATE_REVIEW** — all mandatory criteria PASS and self-verified; the independent design-QA pass
  and the owner decisions in handoff §10 are the remaining gates
- Remaining failed or blocked criteria: none. C-010 NOT_APPLICABLE (dark-only product surfaces).
- ClickUp final evidence comment: **pending** — no ticket exists to receive it; proposed items in handoff §15
