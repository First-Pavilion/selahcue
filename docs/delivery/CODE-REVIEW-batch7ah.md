# Code Review — Batch 7ah (SBOM + license policy + GPU device-loss assertion)

- **Scope:** story `86ajpew0j` — the CI reconciliation follow-up: a license/source/bans policy (`deny.toml`, both cargo trees), CycloneDX SBOM generation + artifact upload per build, and an NFR-024 whole-device GPU-loss assertion.
- **Verification approach:** this batch is CI configuration + one test seam, so the **hosted run itself is the independent verifier** (the new `supply chain` job executes the policy and SBOM generation on a clean runner; the device-loss test executes inside the 3-OS matrix wherever an adapter exists — lavapipe guarantees Ubuntu). Both policies also ran locally green (`bans ok, licenses ok, sources ok` on the workspace AND the operator's standalone Tauri tree). An agent review was judged redundant for the config surface (precedent: batch 7s); the Rust seam carries its own test.
- **Fixed forward from the 7ag review (1 confirmed, low):** the chapter browser's absent-verse guard exited falsy, so the Enter handler clobbered its explanatory status with a "No matches" search and kept focus in the box — the guard now reports the render truthfully.

## What shipped

- **`deny.toml`** (workspace + operator tree): permissive-license allowlist — **no GPL/AGPL/LGPL anywhere in the shipped tree**; unknown registries/git sources denied; duplicate-version hygiene warned. Own crates marked `publish = false` and exempted as private.
- **CI `supply chain` job**: `cargo deny check licenses sources bans` on both trees + `cargo cyclonedx` SBOMs uploaded as a build artifact (`sbom-cyclonedx`).
- **GPU device-loss (NFR-024)**: `Compositor::on_device_lost` (take-once callback seam) + `simulate_device_loss` fault injection; the new test asserts the loss signal fires, nothing panics, and a recreated compositor renders **pixel-identical** output — recreation being the production recovery path.

## Verification

- Local: 262 workspace tests (device-loss test green on Metal), clippy clean, operator clean, both `cargo deny` trees green, YAML validated.
- Hosted: the pushed run must show the new job green on a cold runner (recorded at the gate).

## Residual notes

- The Flutter dependency tree has no SBOM yet (Rust trees covered) — noted on the story.
- The RustSec advisories job is unchanged and complementary.
