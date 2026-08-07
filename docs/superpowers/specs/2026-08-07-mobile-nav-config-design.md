# Design — v2 Mobile Navigation & Config

- Date: 2026-08-07
- Role: /mobile-engineer
- Epic: [EPIC — Mobile Control & LAN Security](https://app.clickup.com/t/86ajp086b)
- Design ref: Figma `363-124` (Mobile — Navigation & Config)
- Builds on: [2026-08-07-mobile-v2-rbac-design.md](2026-08-07-mobile-v2-rbac-design.md) (role-aware controls)
- Scope decisions (owner, this session): **omit the "More" tab** (fold into mobile 7-role
  follow-up 86ajxufbg); **full Config with new deps** (`wakelock_plus` + `package_info_plus`).

---

## 1. Context

The v2 RBAC pass gave each tab role-aware *contents*. This design adds the two remaining pieces of
node `363-124`:

1. **Role-scoped navigation** — the bottom tab bar hides/dims whole tabs per role (◐ = view-only,
   removed = hidden), not just controls inside them. One nav system: bottom tabs + a top-bar ⓘ
   session overflow (already the pattern; no hamburger).
2. **Config / About session sheet** — expand the existing About sheet (opened from ⓘ) into the
   design's three sections: CONNECTION, PREFERENCES, ABOUT.

The "More" tab (Production/Admin tools: lower-thirds · macros · output-health · editable transcript)
is `ConfigureOutputs`/Admin — Operator-only, unreachable by remote devices on the 4-role backend —
so it is **omitted this pass** and folded into follow-up 86ajxufbg (same treatment as TIME UP).

## 2. Role-scoped tabs (mapped to the 4 real backend roles)

A pure function `visibleTabsFor(MobileRole)` returns the ordered visible tabs, each flagged
view-only. Rules (capabilities from `rbac.dart`):

| Tab | Visible when | View-only (◐) when |
|-----|--------------|--------------------|
| Live | always (`Monitor`) | `!navigate && !goLive` |
| Plan | always (`Monitor`) | `!navigate` |
| Scripture | `searchScripture` | never (hidden otherwise) |
| Timer | always (`Monitor`) | `!timer` |

Resulting bars:
- **Producer** → Live · Plan · Scripture · Timer (all interactive)
- **Assistant** → Live · Plan · Scripture · Timer ◐
- **Viewer** → Live ◐ · Plan ◐ · Timer ◐ (Scripture hidden)
- **unknown** (fail-closed) → Live ◐ · Plan ◐ · Timer ◐

The view-only tabs already render read-only content (RBAC pass). The ◐ is a visual marker on the
destination (a `Badge` dot) plus a `tooltip`/semantic "view only". `_tab` index is clamped to the
current visible list so a role change (reconnect) can't land on a removed tab.

## 3. Plan tab gating (was ungated)

`plan_tab` taps `SelectItem` (`Navigate`) and double-taps `selectAndGoLive` (`GoLive`). Gate:
- tap-to-stage enabled only if `can(navigate)`;
- double-tap-go-live enabled only if `can(goLive)`;
- a role with neither (Viewer) → read-only list (no `InkWell` actions), footer hint updated.

## 4. Config / About session sheet (`_AboutSheet` → three sections)

Opened from the top-bar ⓘ (unchanged entry). Sections:

- **CONNECTION** (mostly exists): Status, Host, Role (real granted role), Fingerprint, the note
  "Your role is assigned & managed on the desktop.", and the red **Disconnect this device** button.
- **PREFERENCES** (new — persisted): **Keep screen awake** (real, `wakelock_plus`), **Haptic
  feedback** (app pref; fires `HapticFeedback` on GO LIVE + emergency actions when on), **Reduce
  motion** (app pref; ORs into the existing `MediaQuery.disableAnimations` transition-suppression in
  `main.dart`, so it also gates page transitions).
- **ABOUT** (new): **Version** (real, `package_info_plus` → e.g. `1.0.0 (1)`), **Open-source
  licenses** (Flutter built-in `showLicensePage`), **Help & support** (static entry).

### 4.1 Settings architecture
- `lib/models/settings.dart` — `SettingsController extends ChangeNotifier` holding `keepAwake`,
  `haptics`, `reduceMotion`; `load()`/persist to `flutter_secure_storage` (reused; injectable for
  tests); an injected `WakelockControl` (defaults to `wakelock_plus`, a no-op fake in tests) applied
  on `setKeepAwake`/`load`; a `haptic()` helper that fires `HapticFeedback.selectionClick()` iff
  `haptics`.
- `SettingsScope extends InheritedNotifier<SettingsController>` placed **above** `MaterialApp` in
  `SelahCueApp`, so `SettingsScope.of(context)` reaches the `builder` (reduce-motion), the sheet
  (toggles), and the emergency/GO-LIVE buttons (haptics) without constructor threading.
- `main()` becomes async: `WidgetsFlutterBinding.ensureInitialized()` → `SettingsController.load()`
  → `runApp(SelahCueApp(settings: settings))`.

## 5. Architecture & file plan

- **New** `lib/models/tab_scope.dart` — `ControllerTab` enum, `TabSpec`, `visibleTabsFor(MobileRole)`.
- **New** `lib/models/settings.dart` — `SettingsController` + `SettingsScope`.
- **Edit** `lib/main.dart` — async main, wrap `SettingsScope`, OR reduce-motion into the builder.
- **Edit** `lib/views/controller_view.dart` — build the NavigationBar + IndexedStack from
  `visibleTabsFor(live.role)`; clamp index; view-only ◐; pass `SettingsController` to `_AboutSheet`;
  expand `_AboutSheet` to the three sections.
- **Edit** `lib/views/tabs/plan_tab.dart` — gate stage/go-live.
- **Edit** `lib/views/widgets/mobile_widgets.dart` + `lib/views/tabs/live_tab.dart` — fire
  `SettingsScope.of(context).haptic()` on emergency + GO LIVE taps.
- **Edit** `pubspec.yaml` — add `wakelock_plus`, `package_info_plus` (via `flutter pub add`).

Follows the app's hand-rolled MVC; no state-management package.

## 6. Testing

- **Unit** `tab_scope_test.dart` — `visibleTabsFor` for Producer/Assistant/Viewer/unknown (order,
  visibility, view-only flags).
- **Unit** `settings_test.dart` — load/persist round-trip + injected wakelock called on
  `setKeepAwake`; `haptic()` respects the flag (via injected sink).
- **Widget** `controller_view_nav_test.dart` — Viewer bar has no Scripture destination; Producer has
  all four; index clamps.
- **Widget** `plan_tab_test.dart` — Producer taps stage; Viewer rows are non-interactive.
- **Widget** `config_sheet_test.dart` — the three sections render; toggling Keep-awake calls the
  injected wakelock; version shown via `PackageInfo.setMockInitialValues`.
- **Gate:** `make mobile-test` green.

## 7. Non-goals (this pass)

- The "More" tab + its tools (lower-thirds, macros, output-health, editable transcript) → follow-up
  86ajxufbg.
- Any backend/wire change. 7-role model. Deep haptics on every command (only GO LIVE + emergency).

## 8. Risks

- **Plugin channels in tests** — `wakelock_plus`/`package_info_plus` use platform channels; both are
  isolated behind injection (`WakelockControl`) / `setMockInitialValues`, so widget tests never hit a
  real channel. `flutter analyze` + `make mobile-test` remain the gate.
- **Index churn** — clamping `_tab` to the visible list prevents an out-of-range tab after a role
  change; covered by a widget test.
- **Bounded memory** — no new queues/caches; settings is three bools. No regression.

## 9. Acceptance criteria (Boolean — seed the Goal Contract)

1. `visibleTabsFor` matches §2 exactly (unit test); the bottom bar renders only those tabs with ◐ on
   view-only ones.
2. Viewer's bar omits Scripture; Producer's has all four; index clamps on role change.
3. `plan_tab` is read-only for Viewer; tap-stage gated by `navigate`, double-tap-go-live by `goLive`.
4. Config sheet shows CONNECTION + PREFERENCES + ABOUT; Keep-awake drives injected `wakelock_plus`;
   Version via `package_info_plus`; licenses via `showLicensePage`.
5. Preferences persist (round-trip test) and Reduce-motion ORs into the app-wide transition suppress.
6. `make mobile-test` green; "More" tab absent; no backend/wire change.
