# SelahCue — Web

Placeholder for a browser-based control surface (planned for a later release).

Nothing is built here yet. The web target is expected to be a thin control/monitor
client that speaks the same LAN protocol as the mobile controller (see
`../../docs/architecture/ARCHITECTURE.md`), not a second rendering engine — live
compositing stays in the desktop app.

Stack, bundler, and framework are **not yet decided**; that choice will be recorded
as an ADR under `../../docs/architecture/adr/` before any code lands here. If this
client needs to share domain logic with `desktop/` (e.g. the scripture parser
compiled to WASM), the shared crates are hoisted into a top-level `shared/` workspace
at that time.
