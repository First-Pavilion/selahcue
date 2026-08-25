# Code Review — Mobile "Design 2.0", Batch B (timer entry + the three enforcement states)

- **Scope:** Batch A re-skinned the app and locked the palette. Batch B builds the four surfaces it deliberately left out: the Timer tab's **HH:MM:SS custom-time well** (§4.6), and the three RBAC enforcement states — **Permission blocked** (§4.10, `357:218`), **Role changed — live** (§4.11, `358:128`) and **Action rejected** (§4.12, `358:149`), against the blocking/dismissal contract in §4.13.
- **Design source:** `docs/design/MOBILE-2.0-SPEC.md`. Goal Contract: `docs/delivery/goals/TASK-mobile-design2-batch-b.md`.
- **Still out (see "Not built", below):** timer `Reset`, `Send "TIME UP" to stage`, stage messages, any role expansion.

## What shipped

Three new files: **`lib/views/widgets/custom_time_well.dart`** (`CustomTimeController` + `CustomTimeWell`) and **`lib/views/widgets/enforcement.dart`** (`PermissionBlockedHost`, `PermissionBlockedSheet`, `RoleChangedBanner`, `ActionRejectedToast`). `LiveController` grew three enforcement states; `rbac.dart` grew the command→permission mirror that lets a refusal be explained in words.

### 1. The HH:MM:SS well (§4.6)

Three two-digit fields with `:` separators and `HOURS`/`MIN`/`SEC` captions, on a `d2Inset` well. The shipped minutes-only field could not express an hour — a limitation of the *client*, not the wire (`cmdStartTimer` has always taken seconds), so this is a pure client fix: `1:05:30` now round-trips as `{'cmd':'start_timer','seconds':3930}`.

Entry rules worth naming: the clamp formatter **declines** an out-of-range edit rather than rewriting it, so typing `60` into MIN leaves `6` instead of silently substituting `59` — a formatter that changes what you typed is worse than one that refuses it. Each pair is a 48-wide tap target (spec §6.6; the frame's digits are far narrower), and a tap on the caption focuses the field rather than falling through to the well.

The state pill (RUNNING → preview · PAUSED → warn · TIME UP → live) was **already correct from Batch A** — verified, not rebuilt.

### 2. Permission blocked (§4.10)

The trigger needs no heuristic. `DenyReason` is a closed set in Rust (`protocol.rs:952` — `forbidden` / `unauthenticated` / `bad_request`), so the rule is exactly one string: **only `forbidden` raises the sheet.** A `bad_request` (unknown reference, stale detection id) keeps the notice banner, because "That's not in your role" would simply be false for it. This also means a *client-mirror drift* case — the app thought it had the capability and the host disagreed — still raises the sheet, which is one of the two cases §4.10 exists for.

`ROLES THAT CAN <ACTION>` needs to name the qualifying roles, so `rbac.dart` gained a transcription of Rust `required_permission()` plus `rolesWith()` / `minimalRoleFor()`. The body line says "needs the **Assistant** role" — singular — which is only honest because the roles form a strict superset ladder; `rbac_test.dart` now **pins that ladder**, so a future backend role that breaks it fails there rather than in a sheet naming a role that would not have helped.

Two spec requirements got explicit treatment:

- **The emergency strip stays reachable.** This is why the sheet is *not* `showModalBottomSheet`: a route-level sheet covers the whole screen. `PermissionBlockedHost` wraps only the region between the connection banner and the emergency strip, so the scrim and the sheet are modal over the *tab*, not over the *app*. The test taps Blackout → Confirm through the raised sheet and asserts the command reached the host — asserting the button merely *exists* would not have caught a scrim stretched one `Column` level too high.
- **"Request access" is absent, not disabled.** There is no request-access command in the wire protocol; the button could only close a sheet and claim something was sent. With one action left, `Got it` takes the full width.

`PermissionBlockedHost` is also mounted on the pushed detections route, which covers the shell — otherwise a denial from Approve/Reject would open the sheet *behind* the route and the operator would watch a control do nothing.

### 3. Role changed — live (§4.11)

The desktop re-roles a device by re-issuing its grant on the next authenticated session, so a role change is only ever visible as a **difference**. `LiveController.role` reads through the live session (right for gating, but it makes the change invisible the moment it lands), so the controller now also holds `_knownRole` and diffs it inside `_reconnect()`. `RoleChange.removed` is the capability-set difference; the banner's rows are built from it.

**FR-090 already held and is now pinned:** every `can()` gate and `visibleTabsFor()` re-evaluates the instant the fresh grant lands. The shell test asserts the Scripture tab and the emergency strip are gone *while* the receipt is still explaining them — that ordering is the requirement.

Three judgement calls:

- **An upgrade is reported too**, with adapted copy and no receipt. Silently handing someone more authority mid-service is also news; the frame only draws the downgrade.
- **The reassurance row is conditional.** "You can still watch previews & the transcript" is shown only when the new role holds `monitor`. An `unknown` grant fails closed to no capabilities, and the sentence would be a lie.
- **The receipt is bounded** to 42 % of screen height and scrolls inside itself. A Producer→Viewer downgrade strips seven capabilities; unbounded, the receipt would push the tab content off a phone. Non-blocking is the point of an inline banner, and a block that takes the whole screen is a modal by another name.

Auto-dismiss is a 20 s injected `Duration` (same seam as `EmergencyStrip.confirmWindow`), cancelled in `dispose`. The announcement is assertive and fires from a **post-frame callback** — `View.of(context)` is an inherited lookup and is illegal in `initState`, which is a real crash the first draft had.

### 4. Action rejected (§4.12)

Set only when a command **reached the wire and was lost** — a `SessionException` mid-flight, or a reply that came back on a different connection epoch. Deliberately *not* set by the pre-flight `syncing` refusal: a control that was already inert did not have an action rejected, it simply never fired, and conflating the two would put "Action rejected" on screen for a button the operator could not have pressed. A poll failing on its own is likewise ambient, not something they did. Both are tested.

It takes the connection-banner slot per §4.12. That is not a compromise: a rejection is *always* followed by a reconnect, so the two would compete every time — and the toast carries its own "Reconnecting to `<host>`…" row, so nothing is lost. It retires when the link is healthy **and** state has been re-read, which is a strictly later moment than "socket back". Nothing is queued: the test completes the replacement session's gate and asserts the dropped command was not replayed onto it.

Reduced motion (in-app preference **or** OS setting) swaps the spinner for a static ring. `selahMotion` was refactored onto a new `selahReduceMotion(context)` predicate — deriving "reduce motion?" from `selahMotion(...) == Duration.zero` would work by accident and read as a trick.

## Changes to shipped code, and why

| File | Change | Why |
|---|---|---|
| `live_controller.dart` | `PermissionDenial`, `RoleChange`, `denyReasonForbidden`, `_knownRole`, `blocked`/`roleChange`/`rejected` + dismissers | the three states, driven from real wire outcomes |
| `rbac.dart` | `CommandAction` table, `commandActionFor`, `rolesWith`, `minimalRoleFor`, `Capability.label` | naming an action and its qualifying roles |
| `primitives.dart` | `roleTone()` moved here; `selahReduceMotion()` extracted | the sheet's role chips must agree with the app-bar chip — two tables would eventually disagree and paint one role two colours on two screens |
| `controller_view.dart` | `RoleBadge.toneFor` delegates to `roleTone`; **`connect` widened to `ControllerSession`** | the seam named the concrete `SelahSession`, which let a test simulate a reconnect that *fails* but not one that *succeeds with a different grant* — the only way a re-role reaches the device. Return types are covariant; no caller changed. |
| `mobile_widgets.dart` | `ConnectionBanner` gains the rejected branch and suppresses the notice while the sheet is up | one refusal, one surface — otherwise the operator dismisses it twice and reads it once |
| `detections_view.dart` | carries `PermissionBlockedHost` | the route covers the shell (same rule as the banner, DETECTIONS-VIEW-spec §7.3) |
| `timer_tab.dart` | minutes field → `CustomTimeWell`; Start gates on an empty well; deferred-controls note | §4.6 |

## Not built — and why, precisely

**`Reset` and `Send "TIME UP" to stage` are not buildable from this client.** `selahcue-lan/src/protocol.rs` carries `StartTimer` / `StopTimer` / `AdjustTimer` / `PauseTimer` / `ResumeTimer` and nothing else, and `TimerSnapshot` (`lib/models/protocol.dart:133`) has no original-duration field — so the device cannot even compute what Reset would restore. `time_up` is host-computed state, not a command a phone can push. Both need new protocol variants **plus** a cross-language fixture update, which is an owner decision.

They are **stated in words** rather than drawn or silently omitted: a non-tappable `d2Inset` note under the timer controls saying the desktop has no command for either. Drawing them would give an operator a button that does nothing mid-service (indistinguishable from a dropped link); omitting them silently means the next person to build from the frame reintroduces them, and an operator who knows the desktop has them wonders why the phone does not. The existing Batch A test `TIME UP and Reset controls are not present (deferred)` **passes unmodified**, which is the proof no control was added; a new test asserts the note carries no `InkWell`, `GestureDetector` or `SelahButton`.

Also not built, and unchanged from Batch A's list: stage messages (no wire command), the "More" tab, and any role expansion (`86ajxuf81` / `86ajxufbg`).

**Known gap, deliberate:** the §4.6 lock note ("Slides, scripture & blackout aren't in your role") is not implemented — it is outside this batch's four items. The role-changed banner rides the shell only, not the pushed detections route; a role change that removes `searchScripture` while the operator sits on the approvals screen leaves that route pushed. Popping it is a DETECTIONS-VIEW-spec question, not a §4.11 one.

## Where the implementation diverges from the frames

| Element | Frame | Shipped | Why |
|---|---|---|---|
| `HOURS`/`MIN`/`SEC` captions, deferred note | `d2TextMuted` | `d2TextSecondary` | **A11Y-FIX** §6.2 item 3 — 3.96:1 on `d2Inset` |
| Custom-time well | fixed 257 × 67 | **min-height** 67, grows | a fixed box clips the digits at a 3.0 text scale (§6.7) |
| Lock circle on the sheet | `d2LiveSoft` fill | `d2GoldSoft` fill | **A11Y-FIX** §6.2 item 4 — the frame transposes the fill; red would say "error" where the app means "not yours" |
| Sheet actions | `Got it` + `Request access`, 170 each | `Got it`, full width | no request-access wire command (§4.10 says hide, not disable) |
| "The tapped control renders disabled" | per-control | the scrim absorbs every tap | threading "which control" into each tab for a cosmetic state was not worth the coupling; while the sheet is up, nothing behind it is reachable, which is the same guarantee |
| Role-changed banner glyph gap | "x=13 + 24 gap" | 10 | the measurement is ambiguous between *gap* and *text origin*; 10 is the spec's own 2-up rhythm |
| `SemanticsService.announce` | spec §6.4 | `sendAnnouncement` | `announce` is deprecated after Flutter 3.35 (multi-window); same channel, same event, same assertiveness |

## Verification

```
make mobile-test  →  flutter analyze: No issues found
                     flutter test:    All tests passed  (147 → 204)
```

New/changed tests: `custom_time_well_test.dart` (13), `permission_blocked_test.dart` (13), `role_changed_test.dart` (14), `action_rejected_test.dart` (10), plus 6 in `rbac_test.dart`.

**No Batch A assertion was weakened.** `test/models/design_tokens_test.dart` and `test/views/token_drift_test.dart` are byte-for-byte unchanged, and `timer_tab_test.dart` / `transport_gate_test.dart` pass as written — including the deferral test and the `syncing`-gate tests over the rewritten timer entry. `design_tokens.dart` is untouched, so the Rust cross-surface pin (`test_tokens.rs`) is unaffected by this batch.

One test-authoring note for the next person: `pumpEventQueue()` does not fire a `Timer.run` under the widget binding's fake clock, so a reconnect never finishes its re-read inside `testWidgets`. The role-changed tests build the tree first and advance with `tester.pump` — which is also the truthful scenario, since the operator is looking at the app when their role changes.

## Open, carried forward

1. **The frames still draw the failing pairings** (Batch A item 1) — plus, now, the transposed lock-circle fill on `357:218`. Code diverges from Figma until someone pushes the fixes back.
2. **`Reset` / `TIME UP` need a protocol decision** — new `Command` variants, a `TimerSnapshot` original-duration field, and the cross-language fixture update in `protocol_test.dart` ↔ `test_protocol.rs`. Blocking the last two rows of §4.6.
3. **No request-access path exists.** §4.10 designs one; the wire has none. Either add a command or drop it from the frame — the current state means an operator refused mid-service has no in-app route to ask for the role.
4. **Role naming** ("Producer" vs "Production Operator") is still open (Batch A item 3); this batch's copy uses `MobileRole.label`, so it follows whatever that decision lands on.
5. **The §4.6 lock note** and the detections-route role-change question, both above.
