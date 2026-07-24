# SelahCue — Mobile

The **Flutter controller app** lives in [`selahcue_controller/`](selahcue_controller/):
a phone/tablet (and macOS, for local testing) remote that pairs with the desktop
operator by **QR code** and drives the service over the **TLS-pinned** LAN control
protocol with server-side RBAC (ADR-0009). It controls presentation (plan navigation,
Go Live, blackout/clear, timer) and monitors state — it does not composite video.

## Try it (with the desktop app running)

```sh
make output      # 1. start the desktop output windows (from the repo root)
                 # 2. press P in the output window → a pairing QR appears on the
                 #    stage window + in the terminal
make mobile      # 3. run the controller on this Mac (or `flutter run` on a phone
                 #    from selahcue_controller/) → scan or paste the invite
                 # 4. press Y in the output window to allow the pairing
```

The pairing invite (`selahcue://pair?...`) carries the host address, the operator's
certificate pin (SHA-256), and a single-use 2-minute code; the host must confirm every
pairing (Y/N). Issued credentials are stored in the platform keystore
(`flutter_secure_storage`) and reused on reconnect.

## Verification

```sh
make mobile-test   # flutter analyze + unit tests
```

The wire protocol is contract-tested **cross-language**: the JSON fixtures in
`selahcue_controller/test/models/protocol_test.dart` are pinned byte-for-byte by
`implementation/desktop/crates/selahcue-lan/tests/test_protocol.rs`
(`wire_fixtures_are_stable_for_cross_language_clients`). Change both together.

If the app later needs to share Rust domain logic with `desktop/` (via FFI/uniffi),
the shared crates are hoisted into a top-level `shared/` workspace at that time.
