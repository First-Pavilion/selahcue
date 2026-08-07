# Design — v2 Mobile Remote (role-aware, on the current 4-role backend)

- Date: 2026-08-07
- Role: /mobile-engineer
- Epic: [EPIC — Mobile Control & LAN Security](https://app.clickup.com/t/86ajp086b)
- Design ref: Figma `342-124` (Mobile Remote, 4 screens) · RBAC matrix `354-124`
- RBAC source of truth: `docs/business/PERSONAS.md` §2 · PRD §16 (`docs/product/prds/SelahCue-PRD.md`)
- Scope decision (owner, this session): **mobile-only on the current 4 backend roles**; the
  7-role backend expansion is a tracked follow-up, not this pass.

---

## 1. Context and problem

The Flutter controller (`implementation/mobile/selahcue_controller/`) already has the v2 shell:
a Launcher → Pairing flow and a 4-tab `ControllerView` (Live / Plan / Scripture / Timer) over a
pinned-TLS WebSocket. Two gaps make it *not* the v2 design:

1. **The granted role is captured but never used.** `SelahSession.role` is set from
   `PairGranted.role` / `AuthGranted.role` (`session.dart:99,127`) but the UI hardcodes the badge
   to `'Producer'` (`controller_view.dart:305`) and gates **no** control. There is no capability
   model on the client.
2. **The screens don't yet render the v2 layouts** (Connect device list + QR, Live transport,
   Scripture search+stage, Timer custom-time) with **role-appropriate controls only**.

Enforcement is and remains **100% server-side**: `selahcue-lan::rbac::authorize(role, cmd)` is the
single choke point (`rbac.rs:171`), fail-closed, called before every command (`server.rs:703`).
The client mirror is a UX affordance — it decides what to *offer*, never what is *allowed*.

## 2. The real role space (verified against `rbac.rs`)

The backend has **4 roles / 11 permissions**. Remote paired devices can **never** be `Operator`
(fail-closed clamp, `server.rs:594-596,618-619`), so the achievable role space for a phone is
**Producer / Assistant / Viewer**.

| Role (backend) | Permissions held (`rbac.rs:62-91`) |
|---|---|
| Producer | GoLive, Navigate, ClearLive, Blackout, Timer, SearchScripture, Transcribe, Monitor |
| Assistant | SearchScripture, Navigate, Monitor |
| Viewer | Monitor |

Command → permission (subset this build touches, from `rbac.rs:100-168`):

| UI action | Command | Permission | Producer | Assistant | Viewer |
|---|---|---|:--:|:--:|:--:|
| View previews / state / timer readout | `GetOperatorState` | Monitor | ✅ | ✅ | ✅ |
| Prev / Next (stage to Preview) | `Previous`/`Next` | Navigate | ✅ | ✅ | ❌ |
| Select plan item (stage) | `SelectItem` | Navigate | ✅ | ✅ | ❌ |
| GO LIVE | `GoLive` | GoLive | ✅ | ❌ | ❌ |
| Clear | `Clear` | ClearLive | ✅ | ❌ | ❌ |
| Blackout | `Blackout` | Blackout | ✅ | ❌ | ❌ |
| Scripture search / chapter | `GetChapter` | SearchScripture | ✅ | ✅ | ❌ |
| Stage scripture (→) | `StageScripture` | SearchScripture | ✅ | ✅ | ❌ |
| Timer start / adjust / pause / resume / stop | `StartTimer`…`ResumeTimer` | Timer | ✅ | ❌ | ❌ |

**Not serveable on the current backend (any remote role):**
- **Send "TIME UP" to stage** — no command exists; `time_up` is a *derived* boolean the desktop
  computes at countdown-zero (`present/stage.rs`). The nearest command, `SetStageMessage`, requires
  `ConfigureOutputs` → Operator-only → denied to every remote device.
- **Reset (timer)** — no `ResetTimer` command exists.
- **7-role labels/badges** — the backend cannot grant Observer / Worship Leader / Scripture
  Operator / Timer Operator / Production Operator / Administrator as *distinct enforced* roles.

## 3. Decisions (owner, this session)

- **D1 — Denied controls are hidden, not disabled.** A control the granted role cannot use does
  not render. Where a whole screen has nothing actionable for a role, it renders read-only.
- **D2 — Unbuildable bits are omitted this pass and tracked.** TIME UP, Reset, and the 7-role
  labels are **not** shipped in this build. Two follow-up ClickUp tickets are created:
  - **Backend follow-up:** 7-role RBAC expansion (matrix §2) + a TIME UP command + a `ResetTimer`
    command + (optional) live role-change push. Owner /backend-engineer + /security-reviewer.
  - **Mobile follow-up:** consume the 7 roles, wire TIME UP / Reset, render the 7-role badges,
    once the backend lands.
- **D3 — The role badge shows the *real* granted role** (Producer / Assistant / Viewer),
  replacing the hardcoded `'Producer'`. Honest, not the 7-role vocabulary.

## 4. Client RBAC mirror — `lib/models/rbac.dart` (new)

A small, pure, unit-tested Dart mirror of `rbac.rs`:

- `enum MobileRole { operator, producer, assistant, viewer, unknown }` with
  `MobileRole.parse(String?)` (snake_case, matching the wire strings; unknown → deny-all).
- `enum Capability { goLive, navigate, clearLive, blackout, timer, searchScripture, transcribe,
  monitor, editPlan, manageDevices, configureOutputs }` — the 11 permissions from `rbac.rs`.
- `Set<Capability> capabilitiesOf(MobileRole)` — mirrors `Role::permissions()` **exactly**
  (Operator=all, Producer=8, Assistant=3, Viewer=1, unknown=∅).
- `bool can(MobileRole, Capability)`.

`SelahSession` exposes `MobileRole get grantedRole => MobileRole.parse(role)` (keeps the raw
string too, for the About sheet / diagnostics). Views ask `session.grantedRole.can(...)`.

**Drift guard:** `test/models/rbac_test.dart` pins the four role→capability sets against the exact
table transcribed from `rbac.rs:62-91`, with a comment pointing at the Rust source and the
enforcement invariant (server authoritative; mirror is UX-only). If the backend expands to 7 roles
later, this test is the single place the mirror is updated.

## 5. Screens

Every screen renders **only** the controls the granted role holds (D1). The persistent
`EmergencyStrip`, reconnect banner, and `Denied`-frame banner are retained as defense-in-depth.

### 5.1 Connect (pairing / discovery)
No RBAC (pre-session). Restyle the existing `PairingView` to the v2 layout: discovered-host list
(mDNS) with paired/connect affordances + status, the anti-phishing fingerprint confirm (kept),
QR-scan entry, and the manual `selahcue://pair?...` path. Behaviour unchanged; visual only.

### 5.2 Live
- **Read (all roles):** ON AIR NOW (current live slide) + UP NEXT, from `GetOperatorState`.
- **Navigate (Producer, Assistant):** `◀ Prev` / `Next ▶` (stage to Preview).
- **GoLive (Producer):** `GO LIVE`.
- **ClearLive / Blackout (Producer):** `Clear` / `Blackout`.
- **Viewer:** read-only — no transport row, no emergency actions; just the live/next readout.

### 5.3 Scriptures
- Search box (reference, e.g. "Isaiah 61") + translation selector → `GetChapter{reference,
  translation}`. Verse list with a stage (`→`) affordance → `StageScripture{reference,
  translation}`; the staged verse shows the "staged, awaiting operator" state. Footer copy:
  "Tap → to stage on the operator's preview — they confirm before it goes live."
- **Enabled for Producer, Assistant.** **Viewer:** read-only empty state ("Scripture control is not
  part of your role").

### 5.4 Timer
- **Read (all roles):** live countdown / elapsed readout from `GetOperatorState.timer`.
- **Timer (Producer):** custom time entry (HH:MM:SS) + `Start` (`StartTimer{seconds}`),
  `− 1:00` / `+ 1:00` (`AdjustTimer{delta_secs}`), `Pause` / `Resume`
  (`PauseTimer`/`ResumeTimer` — **new Dart builders**), `Stop` (`StopTimer`).
- **Omitted this pass (D2):** `Send "TIME UP" to stage`, `Reset`.
- **Assistant / Viewer:** read-only readout, no controls.

## 6. Wire-protocol delta (client-only, no VERSION bump)

`PauseTimer` / `ResumeTimer` already exist server-side as additive unit variants
(`protocol.rs:64,67`) mapped to the `Timer` permission (`rbac.rs:117`). This build adds the two
Dart command builders `cmdPauseTimer()` / `cmdResumeTimer()` and pins them with new fixtures in
`test/models/protocol_test.dart` against the Rust wire bytes
(`{"cmd":"pause_timer"}` / `{"cmd":"resume_timer"}`). No new command, no shape change, **`v` stays
2** — this only extends the client's coverage of the existing protocol. No Rust changes required.
(If a Rust-side fixture is needed for symmetry it is additive to `test_protocol.rs`; the byte
strings are fixed by existing serde `#[serde(tag="cmd", rename_all="snake_case")]`.)

## 7. Architecture and file plan

Follows the app's hand-rolled MVC (`main.dart:1-7`), plain `ChangeNotifier` (no new state lib).

- **New** `lib/models/rbac.dart` — the role/capability mirror (§4).
- **Edit** `lib/models/protocol.dart` — add `cmdPauseTimer` / `cmdResumeTimer`.
- **Edit** `lib/models/session.dart` — expose `grantedRole` (parsed) alongside `role`.
- **Edit** `lib/views/controller_view.dart` — badge shows `grantedRole` (drop hardcoded
  `'Producer'`); pass role/capabilities down to tabs; About sheet shows real role.
- **Edit** `lib/views/tabs/live_tab.dart` — gate transport + emergency controls by capability (D1).
- **Edit** `lib/views/tabs/scripture_tab.dart` — search + stage layout; gate by `searchScripture`.
- **Edit** `lib/views/tabs/timer_tab.dart` — custom-time + pause/resume; gate by `timer`.
- **Edit** `lib/views/pairing_view.dart` — v2 Connect restyle.
- Reuse `lib/views/widgets/mobile_widgets.dart`; add a tiny capability helper only if needed.
  No new dependencies.

## 8. Testing

- **Unit** `test/models/rbac_test.dart` — role parse + the four capability sets (pinned to
  `rbac.rs`) + `can()` truth table.
- **Contract** `test/models/protocol_test.dart` — add `pause_timer` / `resume_timer` fixtures.
- **Widget** (reuse the `FakeSession implements ControllerSession` pattern):
  - `live_tab` — Producer shows GO LIVE / Blackout / Clear + transport; Assistant shows only
    Prev/Next; Viewer shows read-only (none of the above rendered).
  - `scripture_tab` — Producer/Assistant can search+stage; Viewer sees read-only empty state.
  - `timer_tab` — Producer shows Start/±1:00/Pause/Resume/Stop; Assistant/Viewer read-only.
- **Gate:** `make mobile-test` (flutter analyze + test) green. `make ci` unaffected for desktop.

## 9. Non-goals (this pass)

- Any change to `selahcue-lan` RBAC, the wire `VERSION`, or backend commands.
- 7-role model, TIME UP command, ResetTimer, live role-change push (→ follow-up tickets, D2).
- Plan-editing, output/screen config, transcription, macros from mobile (server commands exist but
  are Operator-only / out of the v2 mobile scope).

## 10. Risks and mitigations

- **Mirror drift** (client offers a control the server denies, or hides one it allows) → the pinned
  `rbac_test.dart`, and the server remains authoritative (a stray command returns `Denied`, already
  surfaced). Low blast radius.
- **Mid-session downgrade** — the client's role label reflects the pairing grant; a `SetSessionRole`
  downgrade is enforced server-side (next command → `Denied`; `RevokeSession` drops the socket) and
  the new role applies on reconnect. Live in-session role reflection needs a protocol push → noted
  in the mobile follow-up.
- **Bounded-memory** — no new queues/caches; scripture results and timer state are bounded by the
  existing single-snapshot model. No regression to the no-unbounded-growth rule.

## 11. Acceptance criteria (Boolean — seed the Goal Contract)

1. `lib/models/rbac.dart` exists; `capabilitiesOf` matches `rbac.rs:62-91` exactly;
   `rbac_test.dart` passes.
2. The `ControllerView` badge and About sheet show the real `grantedRole` (no hardcoded `'Producer'`).
3. Live/Scripture/Timer render **only** role-permitted controls (D1), verified by widget tests for
   Producer / Assistant / Viewer.
4. `cmdPauseTimer` / `cmdResumeTimer` exist and are pinned by contract fixtures matching the Rust
   wire bytes.
5. The four v2 screens visually match Figma `342-124` for the shipped controls; TIME UP / Reset /
   7-role labels are absent (per D2) with follow-up tickets created and linked.
6. `make mobile-test` is green; no `selahcue-lan` / wire `VERSION` change.
