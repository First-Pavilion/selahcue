# SelahCue Controller — Go-Live Release Checklist

> Prepared by /mobile-engineer. Items marked **[owner]** are owned outside mobile-engineering
> (legal, devops/release, signing, store accounts) and are **not** done in this story.

## Build config (done in code)
- [x] Real app icons generated from the brand logo (`flutter_launcher_icons`) — iOS opaque + Android adaptive.
- [x] Native splash generated (`flutter_native_splash`, `#0E1116` + logo) matching the in-app `SplashView`.
- [x] DEBUG banner hidden (`debugShowCheckedModeBanner: false`).
- [x] Responsive/tablet layouts; landscape safe.
- [x] Privacy policy + Terms drafts (`docs/legal/`) + in-app screens.
- [ ] Bump `version:` in `pubspec.yaml` for the release (currently `1.0.0+1`).
- [ ] Review adaptive-icon safe zone — the logo is line-art; confirm it isn't clipped by the round/mask on Android and looks right at small sizes.

## iOS **[owner: release/devops]**
- [ ] Add `ios/Runner/PrivacyInfo.xcprivacy` to the Runner target (Build Phases → Copy Bundle Resources); verify accessed-API declarations against the "required reason API" report for the final build.
- [ ] Signing: Apple Developer account, App ID, provisioning profiles, distribution certificate (via approved secret mechanism — **not** committed).
- [ ] `Info.plist`: confirm `NSCameraUsageDescription` (QR pairing) + `NSLocalNetworkUsageDescription` + `NSBonjourServices` (`_selahcue._tcp`) copy is present and accurate.
- [ ] Archive + upload to App Store Connect; TestFlight internal test; submit for review.

## Android **[owner: release/devops]**
- [ ] Signing: upload keystore + Play App Signing (approved secret mechanism — **not** committed).
- [ ] `AndroidManifest.xml`: confirm `CAMERA`, `INTERNET`, `CHANGE_WIFI_MULTICAST_STATE` (mDNS) permissions + rationale.
- [ ] `targetSdk`/`compileSdk` at the current Play requirement; build an app bundle (`.aab`).
- [ ] Play Console: internal testing track → production; complete Data safety form (matches PRIVACY.md).

## Legal **[owner: legal]**
- [ ] Legal review + sign-off on `docs/legal/PRIVACY.md` and `docs/legal/TERMS.md`; fill all `{{PLACEHOLDERS}}`.
- [ ] Host the policy + terms at public URLs; put those URLs in the store listings + in-app links.

## Store listing **[owner: product/release]**
- [ ] Finalise `docs/release/mobile/STORE-LISTING.md`; capture screenshots (phone + tablet), feature graphic, age rating, categories.

## Verification
- [x] `make mobile-test` green.
- [ ] Manual smoke on a real phone + a real tablet (portrait + landscape): pair, drive live, splash/icon look, revoke → re-pair.
