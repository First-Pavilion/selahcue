# Native splash theme alignment — 2026-10-31

Ticket: https://app.clickup.com/t/17tnw2bbjvc. Baseline: main `c6fa1b4b01e53f49a348ccc9e812d7b7a4fe520c`.

The existing locked `flutter_native_splash` 2.4.8 generator ran against the existing pubspec color/logo configuration, using the already-installed package cache and package configuration. No dependency/SDK download or whole-app build was needed. Its only tracked output changes were three background PNGs and the two Android 12 theme colors. The iOS launch storyboard's root fallback color was then aligned manually; the generator leaves that root color white even though its full-size background image covers it. Constraints and logo layout remain unchanged. The obsolete pubspec generator note and checklist color were corrected.

## Focused verification

- Decoded the Android drawable/drawable-v21 and iOS LaunchBackground PNGs: each is a 1×1 opaque `(11, 13, 18, 255)` bitmap, exactly `#0B0D12`.
- Parsed both Android 12 day/night styles: `windowSplashScreenBackground` is `#0B0D12`. Parsed all Android resource XML successfully.
- Parsed the iOS storyboard root color: normalized channels resolve to `(11, 13, 18, 255)`. Compared its complete XML tree with baseline after substituting only that color; all other attributes/layout remain identical.
- Compared all other 57 tracked PNGs byte-for-byte with baseline: unchanged. No launcher icons, logo pixels, identities, version/build values, permissions, signing or dependencies changed.
- Android SDK build-tools 36.0.0 `aapt2 compile --dir implementation/mobile/selahcue_controller/android/app/src/main/res -o /private/tmp/selahcue-continuation-20261031/splash-compiled-res.zip`: exit 0. This compiles resources, not an APK/AAB.
- `xcrun ibtool --compile /private/tmp/selahcue-continuation-20261031/LaunchScreen.storyboardc implementation/mobile/selahcue_controller/ios/Runner/Base.lproj/LaunchScreen.storyboard --minimum-deployment-target 13.0 --target-device iphone --target-device ipad`: exit 0. This compiles the storyboard, not an app/archive.
- `git diff --check`: pass. All generated diffs inspected; generator made no unrelated tracked edits.

Local static preview: `/private/tmp/selahcue-continuation-20261031/mika-splash-static-preview.png`. It composites the unchanged logo over the verified background and is explicitly labelled as an asset sample, not emulator/device evidence. It does not reproduce the native launch layout or timing.

One initial invocation rejected unsupported `--no-web` before making changes. The supported invocation then completed; the repository has no web folder to update.

## Limits and handoff

No observed device flash was reproduced or claimed fixed. No emulator or physical-device launch was performed. The reversible color-only change has no new mirroring tests, per the ticket; the full mobile suite was not repeated. No credentials, keychains or accounts were accessed.

Cody, Shadow, Quinn and Vera must independently review the final head before root merges. Physical phone/tablet QA, real signing identities, final artifacts/privacy reports and store submission remain under M01 (`17tnw2bbhyu`) and publishing (`86ajxz3nj`). Revert this ticket's commit to roll back the resource alignment.
