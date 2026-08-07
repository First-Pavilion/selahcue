# Goal Contract — TASK-mobile-gap-fill

## Identity

- Goal ID: TASK-mobile-gap-fill
- Parent goal ID: NONE
- Title: Mobile gap-fill — scripture-detection approval + access-revoked screen + live transcript view + privacy link
- Role: mobile-engineer
- Status: DRAFT
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajxx4uv
- Design ref: Figma 355 (Role home screens: Scripture-Op approval, transcript) · 357 (Enforcement: access-revoked)
- Audit: mobile coverage gap analysis (docs + Figma + backend serveability), this session
- Created: 2026-08-08
- Updated: 2026-08-08
- Maximum iterations: 10
- Independent verification required: yes

## Objective

Close the mobile gaps that are already designed and serveable on the current 4-role backend: the
scripture-detection approval card (FR-095), the access-revoked screen + reconnect-on-revoke fix
(FR-089), the read-only live transcript view (cap #10), and the in-product privacy link (FR-176).

## Baseline

- **Verified**: backend `OperatorStateView` (protocol.rs) already ships `detections:
  Vec<DetectionView{id,reference,text,confidence}>`, `transcript: Vec<TranscriptSegmentView{id,
  start_ms,end_ms,text}>`, and `partial_transcript: Option<String>`; commands `ApproveDetection
  {detection_id}` / `DismissDetection {detection_id}` exist and require `SearchScripture` (Producer +
  Assistant hold it). The mobile Dart `OperatorStateView.fromJson` parses **none** of these.
- **Verified**: on revoke the backend sends `AuthRejected`; `SelahSession.connect` throws
  `SessionException('authentication rejected: …')`; `LiveController._reconnect` retries with stored
  creds forever on any `SessionException` → a revoked device loops "Reconnecting…" indefinitely (bug).
- **Verified**: `ConfigSheet` ABOUT lists Version/Licenses/Help — no privacy link.
- **Note**: `live_controller.dart` was concurrently hardened (`unpair()` now stops the poll before
  closing) — build on top, do not revert.

## Inputs and evidence sources

- Figma 355 / 357; protocol.rs (OperatorStateView, ApproveDetection/DismissDetection, DetectionView,
  TranscriptSegmentView); rbac.rs (SearchScripture → Producer/Assistant).
- Mobile app under `implementation/mobile/selahcue_controller/`.

## Scope

### In scope

- protocol.dart: `DetectionView`, `TranscriptSegmentView` models; parse `detections`, `transcript`,
  `partial_transcript`; `cmdApproveDetection`/`cmdDismissDetection` + contract fixtures.
- session.dart: `SessionRevoked` (a `SessionException` subtype) thrown on `AuthRejected`.
- live_controller.dart: injectable connect fn; `_reconnect` stops + sets `revoked` + clears creds on
  `SessionRevoked`; `bool get revoked`.
- controller_view.dart: `AccessRemovedScreen` shown when revoked (→ re-pair); privacy link in ABOUT.
- scripture_tab.dart: "NEEDS YOUR APPROVAL" card (Approve/Reject) from `detections`.
- live_tab.dart: read-only LIVE TRANSCRIPT section from `transcript` + `partial_transcript`.

### Non-goals

- Any backend/wire change (all fields/commands already exist). Editable transcript (Admin). Stage
  messages (86ajxx4wf), contested (86ajxx4ww), blackout-confirm/sync-gate (86ajxx4x8), 7-role model.

### Constraints

- Server stays authoritative. Wire `v` stays 2 (new builders match existing serde). Injected connect
  fn keeps `_reconnect` testable without real sockets. Bounded memory (transcript is a bounded tail).
  `make mobile-test` green.

### Assumptions and unknowns

- **ASSUMED**: `ApproveDetection` stages in Preview (does not auto-go-live, FR-115) — Approve = stage.
  Confirmed from protocol.rs doc comment.

## Dependencies and approvals

- Owner approved building the serveable set + filing tickets for the rest (this session).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | protocol parses detections/transcript/partial; approve/dismiss builders pinned | `flutter test test/models/protocol_test.dart` | PASS | test output | PENDING |
| C-002 | yes | `SessionRevoked` thrown on AuthRejected; `_reconnect` sets `revoked` + clears creds, stops | `flutter test test/controllers/live_controller_revoked_test.dart` | PASS | test output | PENDING |
| C-003 | yes | Access-removed screen renders on revoke with a re-pair action | `flutter test test/views/access_removed_test.dart` | PASS | test output | PENDING |
| C-004 | yes | Scripture approval card shows detections + Approve/Reject send the right commands | `flutter test test/views/scripture_approval_test.dart` | PASS | test output | PENDING |
| C-005 | yes | Live tab renders the read-only transcript (+ partial) when present | `flutter test test/views/live_transcript_test.dart` | PASS | test output | PENDING |
| C-006 | yes | Privacy link present in Config/About ABOUT | `flutter test test/views/config_sheet_test.dart` | PASS | test output | PENDING |
| C-007 | yes | Full gate green; no backend/wire change | `make mobile-test`; `wireVersion = 2` | analyze clean, tests PASS | CI output | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: per-criterion `flutter test <file>`.
- Broader: `make mobile-test`.
- Independent verifier: /qa-engineer (device: trigger a detection + approve/reject; revoke a device
  from the console → access-removed → re-pair; transcript renders) + /code-reviewer on the diff.
- Required environment: Flutter ^3.12; a desktop host with STT/detection to exercise approval.

## Iteration ledger

### Iteration 1

- Target criterion:
- Hypothesis:
- Change or investigation:
- Verifier executed:
- Result:
- New evidence:
- Decision: iterate | handoff | blocked | gate-review | complete

## Risks and rollback

- Risks: `_reconnect` uses static `SelahSession.connect` (hard to test) → mitigated by an injected
  connect fn. Concurrent WIP in live_controller.dart → re-read before editing, preserve `unpair()`.
- Rollback: additive mobile-only changes; revert the mobile commits.

## Pause and escalation conditions

- If `detections`/`transcript` are not actually populated by the running host (older host) → the UI
  degrades to empty (no card / no transcript), which is correct; not a blocker.

## Final evaluation

- Validator command: python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-mobile-gap-fill.md
- Validator result:
- Independent verification result:
- Terminal state:
- Remaining failed or blocked criteria:
- ClickUp final evidence comment:
