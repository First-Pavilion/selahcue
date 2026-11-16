# Android upload signing

Release builds require a separate upload signing identity. Debug builds retain Android's normal development signing. The application does not read these variables at runtime; they configure Gradle signing only.

The publishing owner supplies all four environment variables through the approved local secret manager or CI secret store:

| Variable | Value supplied by owner |
|---|---|
| SELAHCUE_UPLOAD_STORE_FILE | Absolute path to the owner-provisioned keystore outside the checkout |
| SELAHCUE_UPLOAD_STORE_PASSWORD | Keystore password |
| SELAHCUE_UPLOAD_KEY_ALIAS | Approved upload key alias |
| SELAHCUE_UPLOAD_KEY_PASSWORD | Upload private-key password |

Do not put values in source, shell command arguments, checked-in properties, logs or artifacts. On CI, provision a temporary keystore from the approved secret mechanism outside the checkout, restrict access, and remove it after the job. This ticket does not provision CI secrets or accounts. Never enable shell tracing for secret setup or publish Gradle diagnostic/build scans containing credentials.

With that environment supplied, run `flutter build appbundle --release`. Missing or incomplete values prevent release tasks from executing. A missing keystore or invalid password/alias fails release validation/signing. No debug fallback exists. Use `flutter build apk --debug` without these variables for development.

Before upload, the publishing owner must compare the bundle signer certificate SHA-256 against the approved upload certificate in Play Console. Merely configuring a keystore does not establish ownership or store approval. Production key provisioning, identity approval, accounts and upload remain in [the publishing ticket](https://app.clickup.com/t/86ajxz3nj).

## Integration checks

Run `flutter pub get` first, with Flutter, Android SDK and `JAVA_HOME` pointing to the installed JDK. From the mobile app directory run `python3 scripts/check_android_signing.py --case CASE` for each case:

- `missing`: no signing environment; actual release bundle command must fail with safe incomplete-config diagnostic.
- `partial`: password only; same failure and no password in output.
- `malformed`: temporary invalid keystore with all four values; actual release must fail.
- `wrong-password`: generated temporary keystore with an incorrect private-key password; actual signing must fail.
- `debug`: all signing variables removed; actual debug APK must build.
- `fixture`: generate a disposable two-day RSA test key outside the checkout, build the release AAB, verify its JAR signature and compare its signer SHA-256 to the generated certificate. Passwords are random and passed to keytool through environment references. Temporary key material is removed on exit.

The fixture case deletes its **test-signed AAB** after successful verification. If interrupted, the ignored build directory may retain a test-signed artifact: delete or overwrite it before preparing an owner-signed artifact. It must never be uploaded or distributed. Test passwords are never printed; failure diagnostics are shown only after checking that neither test password occurs in output. These checks do not consume any owner signing environment.

References: [Flutter Android signing](https://docs.flutter.dev/deployment/android), [Android app signing and upload keys](https://developer.android.com/studio/publish/app-signing).

## Verified implementation evidence — 2026-10-31

Local tools: Flutter 3.47.5 / Dart 3.13.4; Android SDK target/compile 36; Android Studio JBR 21.0.10. Tests ran serially on macOS using actual Flutter/Gradle builds, not mocks.

- Red baseline on main 6f03aee7: `--case missing` failed its assertion because the existing release AAB succeeded without upload credentials.
- After implementation: missing and partial configuration fail with the safe incomplete-configuration message, including after a successful fixture release build.
- Malformed keystore and wrong private-key password fail at `signReleaseBundle`, confirming rejection occurs in actual release signing.
- Debug APK builds with all four upload variables removed.
- Fixture release AAB builds; `jarsigner -verify` reports a verified signature; `keytool` confirms its SHA-256 matches the generated disposable upload key. No production key was accessed or generated.
- Every captured subprocess output is checked for fixture password disclosure before diagnostics can be emitted. No fixture key material or passwords are committed.
- One initial Kotlin DSL compilation error came from the Gradle `java` accessor shadowing the Java package; adding an explicit `java.io.File` import resolved it before the passing behavior checks.

These results establish fail-closed wiring and key selection. They do not establish ownership of a real upload key, Play Console acceptance, final legal/privacy declarations or physical-device/store readiness. Four independent reviews and current CI remain required before merge.
