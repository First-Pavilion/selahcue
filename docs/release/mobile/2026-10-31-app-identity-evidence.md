# Mobile app identity — native build evidence, 31 October 2026

Ticket: [M01](https://app.clickup.com/t/17tnw2bbhyu). This is the app-name continuation after PR316, not store acceptance. Source base: `add4702e3474fb9c6c793beccbd2d38b59993db0` plus the scoped Android/iOS native-name changes in this PR. IDs, version/build numbers, permissions, signing configuration and dependency versions are unchanged.

## Changed app behavior

- Android launcher label: `selahcue_controller` → `SelahCue Controller`.
- iOS Home-screen display name: `Selahcue Controller` → `SelahCue Controller`.
- iOS short fallback bundle name: `selahcue_controller` → `SelahCue`. This keeps the short name below 16 characters; the full name remains in `CFBundleDisplayName`.
- Existing Dart app title and store-listing draft already use `SelahCue Controller`.

## Verification performed

Local tooling: Flutter 3.47.5 / Dart 3.13.4; Xcode 26.6 with iOS 26.5 SDK; Android Studio JBR 21.0.10; Android compile/target SDK 36.

1. Parsed the original Android manifest and iOS plist: branding comparison failed on the placeholder/capitalization values. After the native-name changes the same comparison passed. No persistent test duplicates these simple reversible configuration strings.
2. `make mobile-test`: analysis reported no issues; all 499 tests passed. This includes existing lifecycle/reconnect/permission/UI tests; it is not a physical-device smoke run.
3. `flutter build apk --debug --no-pub`: passed. `aapt2 dump badging` on the actual APK reported app label `SelahCue Controller`, package `com.selahcue.selahcue_controller`, version 1.0.0/build 1, compile/target SDK 36, and arm64-v8a/armeabi-v7a/x86_64 code. This debug artifact is not a store candidate.
4. In `android/`, with the installed Android Studio JBR as `JAVA_HOME`, `./gradlew :app:processReleaseMainManifest --console=plain`: passed. Parsed `build/app/intermediates/merged_manifest/release/processReleaseMainManifest/AndroidManifest.xml`: correct label, unchanged package, target SDK 36, and no `android:debuggable=true`.
5. `flutter build ios --release --no-codesign --no-pub`: passed, producing `build/ios/iphoneos/Runner.app` (18.4 MB). Parsed the compiled Info.plist: correct display/short names, unchanged `com.selahcue.selahcueController`, version 1.0.0/build 1, `iphoneos26.5`, minimum iOS 15.0, camera/local-network purpose strings and `_selahcue._tcp` service. The built app includes `PrivacyInfo.xcprivacy`, parsed equal to the unchanged source manifest. This is unsigned compilation/resource evidence, not an installable distribution archive or App Store acceptance.
6. Existing `scripts/check_ios_privacy_manifest.py`, Info.plist lint and `git diff --check`: passed. Goal Contract structural validator passed; independent-review criterion remains pending until reviewed.

Native outputs are gitignored local evidence, not uploaded release artifacts:

| Artifact | SHA-256 |
|---|---|
| Android debug APK | `fa32c8901987305b2deb322f293cd11c2d4a6845c563b3122e23bdea6884122c` |
| Unsigned iOS release app executable | `e8c2924fff32f024e00cd435d93dab40097242e9a0d9d6275095c46c9472044c` |

Existing tooling warnings were not hidden: Gradle reports namespace attributes in third-party plugin manifests and features deprecated for Gradle 10. Flutter reports that all current iOS plugins are Swift Packages while this app retains CocoaPods integration. No dependency upgrade or CocoaPods migration is bundled into branding cleanup. Flutter setup changed only the generated minimum-Flutter line in pubspec.lock; that setup-only churn was restored, leaving all dependency versions unchanged.

## Current primary-source requirement check

These are dated observations, not an enduring store-policy guarantee. Recheck at submission.

- [Google Play target API requirements](https://developer.android.com/google/play/requirements/target-sdk): since 31 August 2026, new phone/tablet apps and updates need target API 36 or later. Actual built/merged metadata here is36.
- [Apple submission requirements](https://developer.apple.com/news/upcoming-requirements/): Xcode 26+ and iOS 26 SDK+ for uploads; current minimum deployment target is iOS 13+. The local unsigned build uses Xcode 26.6/iOS 26.5 and deployment 15.0.
- [Apple CFBundleName reference](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html): the bundle name is short; [CFBundleDisplayName](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundledisplayname) is the longer user-visible Home-screen name.
- [Android 16 KB page-size guidance](https://developer.android.com/guide/practices/page-sizes): native compatibility still needs validation on the actual release bundle/libraries and a representative 16 KB runtime. A debug APK or target-SDK value does not prove it.
- [Apple required-reason API documentation](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api): including the app manifest does not verify third-party SDK declarations or the final privacy report. No declarations were invented by this patch.

## Remaining release gates

M01 remains In Progress. A separate atomic Android signing follow-up is needed: the current Gradle release configuration still selects the debug signing configuration. Production release packaging must fail closed without approved upload-signing configuration; provisioning belongs to the release owner.

No Android AAB, signed iOS distribution archive,16 KB runtime check, physical phone/tablet matrix, final privacy report, legal sign-off, store listing approval, TestFlight/Play upload or store submission is claimed. Signing/accounts/legal/submission remain in [86ajxz3nj](https://app.clickup.com/t/86ajxz3nj). All four independent code/security/QA/performance reviews and current hosted CI remain required before this scoped PR is merged.
