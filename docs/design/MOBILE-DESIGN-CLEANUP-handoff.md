# Mobile Design Cleanup — /ui-ux-designer handoff

- Date: 2026-08-08 · Role: /ui-ux-designer → /mobile-engineer
- ClickUp: [86ajxxu0r](https://app.clickup.com/t/86ajxxu0r) · epic [86ajp086b](https://app.clickup.com/t/86ajp086b)
- Design system: `lib/models/design_tokens.dart` (canonical) + Design-2.0 `d2*` tokens; Figma
  SYQn5hFY8YVQKm3c6rw0eJ (mobile v2 frames 342 Mobile Remote, 363 Nav & Config)
- Logo: `assets/selahcue-logo.png` (indigo open-book + flame, 1254² transparent = brand `#6E5CF0`)

**Goal:** sleek + responsive so the controller renders correctly on **tablets** (and landscape),
the logo is used where it belongs, the splash is redesigned, and the look is store-ready. This is a
*polish* pass over the shipped v2 design — not a re-layout of every control.

---

## 1. Responsive system (the core of "renders correctly on tablets")

Use Material 3 **window size classes** by width:

| Class | Width (dp) | Devices |
|---|---|---|
| compact | < 600 | phones (portrait) |
| medium | 600–839 | small tablets, phone landscape |
| expanded | ≥ 840 | tablets, large tablets |

**Global rule — constrain + centre.** The control surface is a phone-shaped column even on a
tablet; never let cards/buttons stretch edge-to-edge on a wide screen.
- **Max content width = 560 dp.** Every screen body (tabs, pairing, config sheet, dialogs, splash)
  is wrapped so its content is capped at 560 dp and **centred**, with the surplus as side gutters
  (`bgBase`). Provide one reusable wrapper, e.g. `ResponsiveBody({maxWidth: 560, child})` using a
  `Center` + `ConstrainedBox`.
- **Adaptive horizontal padding:** compact 16 · medium 20 · expanded 24 (outside the 560 cap).
- **Bottom `NavigationBar` stays** on all sizes (single, learnable nav — matches 363). It spans full
  width; only the *content* above it is constrained/centred. (A `NavigationRail` is an optional
  future enhancement, not required for go-live.)
- **Emergency strip** is constrained to the same 560 dp and centred (so Blackout/Clear don't become
  giant on a tablet).

**Per-screen tablet behaviour** (all within the 560 cap unless noted):
- **Live:** at ≥ 600 dp show the **Preview and Live cards side-by-side** (two equal columns) with the
  transport row full-width beneath; < 600 dp keeps them stacked. Transcript panel spans the column.
- **Plan / Scripture:** single constrained column; verse/plan rows keep comfortable line length
  (the 560 cap already fixes the "full-tablet-width line" problem). Scripture approval card spans the
  column.
- **Timer:** big readout centred; the custom-time + button grid stays within the 560 cap (don't let
  Start/±1:00 become full-tablet-width).
- **Config/About sheet & dialogs:** cap at 560 dp, centred; the sheet already scrolls.
- **Landscape:** same rules; the constrained column + scroll handles short heights. Splash uses a
  `Center` so it survives landscape.

**Touch targets** ≥ 48×48 dp everywhere (audit the verse rows, link rows, translation picker).

## 2. Splash redesign (Figma reference + spec)

Replace the "S"-in-a-box with the real brand mark. Two layers must match to avoid a cold-start flash:

**A. Native splash** (`flutter_native_splash`): background `#0E1116` (`bgBase`), centred logo image
at ~30% width. Dark-mode + Android 12 branded splash configured. This is what shows before Flutter
boots.

**B. In-app splash** (the Dart `Launcher`): on `bgBase`,
- centred **logo mark** 96–112 dp,
- **"SelahCue"** wordmark below, 26/700, `textPrimary`,
- **"CONTROLLER"** overline, 12/600, letter-spacing 3, `textMuted`,
- a slim progress indicator (2–3 dp) in `accentBrand`,
- reconnect status line (`_status`) under it when present.
- Subtle brand touch: a faint radial/vertical gradient `bgBase → #12131c` behind the mark (optional).
- **Reduced motion:** static (no logo animation); the spinner is acceptable, or swap for a static
  "Connecting…" label when `disableAnimations`.

## 3. Logo integration inventory

| Surface | Use | Notes |
|---|---|---|
| App launcher icon (iOS/Android) | **required** | Generate via `flutter_launcher_icons`: foreground = logo, adaptive background `#0E1116`; iOS needs an opaque 1024² (logo on `#0E1116`). |
| In-app splash | **required** | §2B — logo mark + wordmark. |
| Native splash | **required** | §2A. |
| Pairing / Connect header | **required** | Replace the plain "Connect to a host" title area with logo mark (28 dp) + "SelahCue" wordmark; keep the existing copy beneath. |
| Config/About sheet header | **required** | Replace the "S" box (`controller_view.dart` `_AboutSheet`) with the logo image at 44 dp. |
| App bar (ControllerView) | optional | A 20 dp logo mark left of the plan name is nice but not required; keep the bar uncluttered (role badge + clock already there). |

Logo images are **decorative** (`Semantics(excludeSemantics)`, empty alt) everywhere the brand name
is also present in text; on the splash it's the brand, so label the wordmark, not the image.

## 4. Polish (design-system consistency)

- **Spacing scale:** 4 / 8 / 12 / 16 / 20 / 24. Card radius 12; panels `bgPanel`; 1 dp `border`.
- **Section labels:** 11 / 800 / uppercase / letter-spacing 0.7 / `textMuted` (already the pattern —
  apply consistently to any new sections).
- **Buttons:** primary = `accentBrand` filled; destructive = `liveInk` outline/fill; secondary =
  outlined on `bgPanel`. Consistent vertical padding 14.
- **Elevation:** flat; separation by 1 dp borders + surface tint, not shadows (matches current).

## 5. Accessibility (testable)

- Contrast AA — tokens already audited (`test_tokens.rs`); keep text on `bgBase`/`bgPanel` at
  `textPrimary`/`textMuted`.
- Touch ≥ 48 dp (§1). Semantics on every actionable control (already the pattern).
- Reduced motion honoured (already wired app-wide via `disableAnimations` + the Config toggle) —
  splash respects it (§2B).
- Dynamic type: text should not clip when the OS font scale is large — the 560 cap + scroll views
  handle this; verify the Timer readout and splash wordmark wrap/scale.

## 6. State coverage (already designed — keep on tablet)

Loading (splash + per-tab spinners), empty (Scripture "type a reference"), error (denial/reconnect
banners), permission (role-gated hide + Scripture "not in your role"), revoked (Access-removed
screen, Figma 357), detection-approval (Figma 355). All must remain correct within the responsive
constraints above (i.e., centred/constrained on tablet).

## 7. Handoff → /mobile-engineer (implementation notes)

1. Add `ResponsiveBody` (560 dp cap + adaptive padding) and wrap each screen body + the emergency
   strip + dialogs.
2. Live tab: `LayoutBuilder` → side-by-side Preview/Live at ≥ 600 dp.
3. Splash: rebuild `Launcher` per §2B; add `flutter_native_splash` config (§2A).
4. Logo: wire `assets/selahcue-logo.png` into splash, pairing header, About header; add
   `flutter_launcher_icons` config and generate icons.
5. Keep `make mobile-test` green; add widget tests asserting the constrained width on a wide surface
   and the logo's presence on splash/About.

**Not designed here (owned elsewhere / follow-up):** net-new Figma frames for each tablet layout
(this spec + the existing 342/363 frames + tokens are implementation-ready; a Figma frame set is an
optional design-artifact follow-up); the store-listing visual assets (screenshots) are a release
task.
