# SelahCue — Mobile

Placeholder for the Android/iOS controller app (planned for a later release).

Nothing is built here yet. The mobile controller is a **Flutter/Dart** app (ADR-0002
selects Flutter for the mobile client) that connects to the desktop operator over the
TLS-pinned LAN WebSocket protocol with RBAC (see `../../docs/architecture/ARCHITECTURE.md`).
It drives presentation control, scripture search/display, and monitoring — it does not
composite video itself.

The Flutter project (`pubspec.yaml`, `lib/`, platform runners) will be scaffolded in a
dedicated Stage-7 batch. If the app later needs to share Rust domain logic with
`desktop/` (via FFI/uniffi), the shared crates are hoisted into a top-level `shared/`
workspace at that time.
