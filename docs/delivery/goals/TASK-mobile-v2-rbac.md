# Goal Contract — TASK-mobile-v2-rbac

## Identity

- Goal ID: TASK-mobile-v2-rbac
- Parent goal ID: NONE
- Title: v2 mobile role-aware controller — consume the granted role and render only role-permitted controls (4-role backend)
- Role: mobile-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxuf5j
- Design ref: Figma 342-124 (Mobile Remote) · RBAC matrix 354-124
- Spec: docs/superpowers/specs/2026-08-07-mobile-v2-rbac-design.md
- Plan: docs/superpowers/plans/2026-08-07-mobile-v2-rbac.md
- Created: 2026-08-07
- Updated: 2026-08-07
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The Flutter controller consumes its server-granted role and renders **only role-permitted
controls** across the v2 screens (Connect / Live / Scriptures / Timer), gated by a Dart mirror
of the desktop's 4-role RBAC — enforcement stays 100% server-side.

## Baseline

- **Verified**: the mobile app already has the v2 shell — Launcher → PairingView, a 4-tab
  ControllerView (Live/Plan/Scripture/Timer) over a pinned-TLS WebSocket. The granted role is
  captured (`SelahSession.role`, `session.dart:99,127`) but **unused**: the About sheet hardcodes
  `'Producer'` (`controller_view.dart:274,305`) and no control is gated. No `Role`/`Capability`
  model exists on the client.
- **Verified**: the backend enforces **4 roles / 11 permissions** (`selahcue-lan/src/rbac.rs:13-91`),
  `authorize()` the single choke point (`rbac.rs:171`, called `server.rs:703`); remote devices can
  never be `Operator` (`server.rs:594-596`). `PauseTimer`/`ResumeTimer` exist server-side
  (`protocol.rs:64,67`, Timer permission) but have no Dart builders. No TIME UP / ResetTimer command.
- **Verified**: mobile tests are pure `flutter_test` with hand-written fakes; `protocol_test.dart`
  byte-pins the wire against the Rust fixtures. `make mobile-test` is the gate.

## Inputs and evidence sources

- Figma 342-124 (design) + 354-124 (RBAC matrix); PERSONAS.md §2; PRD §16.
- `implementation/desktop/crates/selahcue-lan/src/rbac.rs` (the mirror source of truth).
- `implementation/mobile/selahcue_controller/` (current app + tests).
- The plan `docs/superpowers/plans/2026-08-07-mobile-v2-rbac.md`.

## Scope

### In scope

- `lib/models/rbac.dart` (role/capability mirror) + test.
- Surface the role through `ControllerSession.grantedRole` → `LiveController.can(Capability)`.
- `cmdPauseTimer`/`cmdResumeTimer` builders + contract fixtures (no VERSION bump).
- Role-gated (hide-not-disable) controls on Live, Scripture, Timer + emergency strip; real role
  badge + About sheet; Connect v2 visual alignment (no behaviour change).

### Non-goals

- Any change to `selahcue-lan` RBAC, the wire `VERSION`, or backend commands.
- 7-role model, TIME UP command, ResetTimer, live role-change push → follow-up tickets
  (backend 86ajxuf81, mobile 86ajxufbg).

### Constraints

- Server stays authoritative; the Dart mirror is UX-only. Mirror `rbac.rs:62-91` verbatim.
- Wire `v` stays 2. No new dependencies. AA (Semantics on controls). Bounded memory (no new queues).
- `make mobile-test` green; diff limited to `implementation/mobile/…` + `docs/…`.

### Assumptions and unknowns

- **ASSUMED**: `rbac.rs` stays at 4 roles during this pass (it is NOT in the concurrent-WIP
  modified set; `protocol.rs`/`server.rs` are). Re-verify `rbac.rs:62-91` at Task 1. Owner: executor.

## Dependencies and approvals

- Design + scope decisions (D1 hide, D2 omit+track, D3 real role badge) — approved by owner this
  session. Follow-up tickets created (86ajxuf81, 86ajxufbg).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `rbac.dart` mirrors `rbac.rs:62-91` role→capability table exactly | `flutter test test/models/rbac_test.dart` | PASS | rbac_test 4/4 PASS | PASS |
| C-002 | yes | Role travels session→controller (`grantedRole`, `can()`) | `flutter test test/controllers/live_controller_rbac_test.dart` | PASS | live_controller_rbac_test PASS | PASS |
| C-003 | yes | `cmdPauseTimer`/`cmdResumeTimer` pinned; wire `v` still 2 | `flutter test test/models/protocol_test.dart` + grep `wireVersion` | PASS + `const int wireVersion = 2` | protocol_test PASS; `wireVersion = 2` | PASS |
| C-004 | yes | App-bar badge + About sheet show the real role (no hardcoded 'Producer') | `flutter test test/views/controller_view_role_test.dart` | PASS | controller_view_role_test 2/2 PASS | PASS |
| C-005 | yes | Live/Scripture/Timer/emergency-strip render only role-permitted controls (Producer/Assistant/Viewer) | `flutter test test/views/live_tab_test.dart test/views/scripture_tab_role_test.dart test/views/timer_tab_test.dart test/views/emergency_strip_test.dart` | PASS | live/scripture/timer/emergency role tests PASS | PASS |
| C-006 | yes | Full gate green; no backend/wire change | `make mobile-test` + `git diff --name-only` scoped to mobile+docs | analyze clean, tests PASS, no `selahcue-lan` files | `make mobile-test` 62/62 PASS; analyze clean; diff = mobile+docs only | PASS |
| C-007 | yes | TIME UP/Reset/7-role omitted; two follow-ups created + linked | review | absent in Timer UI; 86ajxuf81 + 86ajxufbg exist, dependency set | ClickUp 86ajxuf81, 86ajxufbg (waiting_on) | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: the per-task `flutter test <file>` above.
- Broader regression verification: `make mobile-test` (flutter analyze + full test suite).
- Independent verifier: /qa-engineer (or /code-reviewer) on the branch diff + representative-device
  screenshots per role.
- Required environment: Flutter SDK `^3.12.0`; a desktop host (`make output`) for the device check.

## Iteration ledger

### Iteration 1

- Target criterion: C-001…C-006 (the full mobile role-awareness build).
- Hypothesis: a pure Dart mirror of `rbac.rs` + `LiveController.can()` gate lets each
  v2 screen hide the controls the granted role lacks, with no backend/wire change.
- Change or investigation: 10-task TDD plan executed — `rbac.dart` mirror; role surfaced via
  `ControllerSession.grantedRole` → `LiveController.can()`; `pause_timer`/`resume_timer` builders +
  fixtures; app-bar `RoleBadge` + real About-sheet role; hide-gating on Live transport, emergency
  strip, Scripture, Timer (+ Pause/Resume); Connect header aligned to v2.
- Verifier executed: per-task `flutter test <file>`; then `make mobile-test`; `flutter analyze`;
  `git diff --name-only c6a868b..HEAD`.
- Result: 62/62 tests PASS; analyze "No issues found"; diff = mobile + docs only; `wireVersion = 2`.
- New evidence: 11 mobile commits f7106e4…72d3b6f; two follow-up tickets 86ajxuf81 / 86ajxufbg.
- Deviation: Task 9 shipped the presentation-only Connect header alignment but **no** full-`PairingView`
  widget test — pumping it starts real mDNS sockets + a ~4s timer (flaky/plugin-hazardous under the
  test binding); the flow stays covered by existing `discovery`/`pair_uri` unit tests, behaviour
  untouched. Not a mandatory criterion (C-005 covers Live/Scripture/Timer/emergency only).
- Decision: gate-review — all automated criteria PASS; independent QA + representative-device
  screenshots per role are still required before VERIFIED_COMPLETE.

## Risks and rollback

- Risks: mirror drift (mitigated by `rbac_test.dart` + server-authoritative deny); concurrent
  backend WIP touching `protocol.rs`/`server.rs` (re-verify `rbac.rs` at Task 1; stage only mobile
  files).
- Rollback or recovery: all changes are additive mobile-only; revert the mobile commits. No wire or
  backend change to roll back.

## Pause and escalation conditions

- If `rbac.rs` has already been expanded to 7 roles by concurrent WIP → pause and re-scope with the
  owner (this pass targets 4 roles). Owner: executor → owner.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-mobile-v2-rbac.md
- Validator result: PASS (7/7 mandatory) at authoring; re-run after status edits.
- Independent verification result: PENDING — handed to /qa-engineer (or /code-reviewer): device
  screenshots per role (Producer/Assistant/Viewer) + branch-diff review.
- Terminal state: GATE_REVIEW.
- Remaining failed or blocked criteria: none FAIL; all 7 criteria PASS. Independent QA/device check
  outstanding before VERIFIED_COMPLETE.
- ClickUp final evidence comment: posted on 86ajxuf5j; story moved to QA.
