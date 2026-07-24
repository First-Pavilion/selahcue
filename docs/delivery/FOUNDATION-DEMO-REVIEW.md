# Foundation-Demo Milestone Review (Stage 7 · milestone `86ajp0bpn`)

**Date:** 2026-07-24 · **Method:** live demo walk on the release binary (driven over the
real pinned-TLS control link; state transitions captured programmatically) + the
continuous evidence base (CI matrix, E2E suites, user-confirmed visuals).
**This review was itself adversarially audited** (claims-vs-evidence, 2 fresh-context
agents cross-checking the code, tests, CI logs, and live ClickUp): **17 findings — every
verdict below reflects the corrected wording, plus one new E2E test added to close a
gap rather than re-word it.**

**Demo script under review** (IMPLEMENTATION-READINESS.md): *launch on 3 OSes → build a
plan → static slide on main output → stage display → countdown to TIME UP (stage-only) →
search & display a PD scripture → emergency blackout/clear offline → pair mobile by QR +
advance a slide → force-kill + recover exact live state.*

## Verdict table

| # | Demo step | Verdict | Evidence (audited wording) |
|---|---|---|---|
| 1 | Launch on 3 OSes | **PARTIAL** | macOS: real (live walk, control-ready ~1 s; **both app windows — output + stage — user-confirmed on macOS**; NFRs measured: cold 1.13 s, idle 121.5 MB). Linux: full suite green in hosted CI. Windows: full suite **minus the encryption-feature tests** (skipped per ci.yml — perl/nasm toolchain gap). GUI *launch* is not exercised on any runner. |
| 2 | Build a plan | **PARTIAL** | Plan model + CRUD unit-complete (11 plan-model tests of the 39-test core crate); the SQLite plan repository is **round-trip/cascade/corruption-tested** (writes are transactional in implementation, but no fault-injection test proves rollback). The shipping binary uses a **hardcoded demo plan** — no authoring UI, no persistence wiring, and the **library half of story `86ajp0a4z`** (library models, search, duplicate/template) is unimplemented. |
| 3 | Static slide on main output | **PASS** | Live walk: `go-live` → `live_item 1→2`; Preview→Live isolation held over the wire (`next` left Live untouched); glyph text user-confirmed on screen (7j); FR-012 test-enforced. |
| 4 | Stage display | **PASS (scoped)** | Second native window renders the speaker scene from the same live state (7p); main-vs-stage distinctness test-enforced. **Caveat:** the window is not yet assignable to a chosen physical display, and identify-per-display is composition-tested but not wired to the second window. |
| 5 | Countdown → TIME UP (stage-only) | **PASS (scoped)** | Timer state transitions captured remotely in the live walk + the post-`582d9dc` stage-compose regression suite (M:SS readout, ceil, warn, TIME UP red, audience-never-shows-a-timer). **User visual re-confirmation of the stage readout since the `582d9dc` fix is pending.** |
| 6 | Search & display a PD scripture | **PARTIAL (weak)** | Reference **parse + staging** are unit-tested at the controller; scripture commands are covered by RBAC-mapping and protocol-serialization tests only — **no wire E2E, and no shipped client (CLI, operator shell, or Flutter app) can issue a scripture command yet**. A staged scripture displays the **reference text**; keyword search and verse content are blocked on bundling a PD translation (none exists in the repo). |
| 7 | Emergency blackout/clear (offline) | **PASS (scoped)** | Live walk: blackout on→off (state true→false), clear (live→None) — **remote-driven over the LAN-local link with zero internet dependency**. The local-keyboard path (B / C keys) is compile-verified + unit-covered at the present crate; a physical-keys, network-cable-out demo has not been recorded. `Clear` RBAC-gated to Producer+ (DEC-002), E2E-enforced. |
| 8 | Pair mobile by QR + advance | **PARTIAL (strong)** | **New E2E (added by this review): one wire flow pairs with the invite code against the real `LiveController` and advances — `Next` stages, `GoLive` flips the host's live output** (`wire_paired_device_advances_the_live_output`). Plus the 6 pairing E2E (decline / replay / expiry / opt-in / reconnect-with-issued-credentials) and the QR-URI round-trip unit tests. The Flutter controller builds (macOS app, analyze + 12 tests). **A QR has not yet been scanned by a real camera — on-device phone QA pending.** |
| 9 | Force-kill + recover exact live state | **FAIL — not implemented** | Live walk: `live_item Some(3)` → `kill -9` → relaunch → `Some(1)` (demo-plan reset). Story `86ajp09td` (urgent) never started; the data layer has crash-safe primitives, nothing persists live state. |

**Score: 1 PASS · 3 PASS (scoped) · 4 PARTIAL · 1 FAIL.**

## What the foundation provably is (audited wording)
A cross-platform core that runs end-to-end today: plan → Preview → Live on a real
audience window; a speaker confidence monitor with a live countdown; emergency
blackout/clear with tightened RBAC over a LAN-local link; **pinned-TLS remote control**
(operator shell via a local endpoint hand-off, a CLI, and a built Flutter controller),
with **QR pairing E2E-verified at the wire level** (camera-scan on a phone pending);
**rect-compositor GPU parity verified continuously on three backends**
(Vulkan/Metal/DX12 in CI) with glyph text rendering via the verified CPU path
(GPU-native glyphs are a future ADR-0002 slice); measured NFRs (cold 1.13 s, idle
121.5 MB, slide-trigger ≤150 ms release); 199 Rust + 12 Dart tests. Code batches
7c–7r were independently adversarially reviewed (7a/7b had plain independent reviews;
7s was verified by the hosted 3-OS matrix itself, review waived as redundant).

## ClickUp status reconciliation (owner attention required)
Five foundation stories are closed **complete** in ClickUp while this review's evidence
shows undelivered acceptance items. The closures are the owner's call and are not
reopened here — but the deltas must not silently vanish. Each needs either a recorded
descope decision on the task or a follow-up story:

| Story (closed complete) | Delta vs its own acceptance text |
|---|---|
| `86ajp09c2` walking skeleton | Cross-OS GUI launch + per-OS NFR measurement unverified (CI covers build+test) |
| `86ajp0a4z` plan + CRUD + library | Persistence binding to the shipping binary; the entire library scope (models, search, duplicate/template); "survives restart" contradicted by step 9 |
| `86ajp0afa` scripture | Bundled PD translations (scope: ≥4), keyword search, verse-text display — none delivered; only parse/search-of-references shipped |
| `86ajp0aa4` stage display | Identify-on-each-physical-display + display assignment not wired |
| `86ajp09nk` CI | SBOM + license (GPL/AGPL) scanning and a GPU device-loss assertion — absent from the pipeline; not descoped anywhere |

## The honest gap list (to close the milestone)
1. **Autosave + crash recovery** (`86ajp09td`, urgent) — the demo's only outright FAIL.
2. **Plan authoring/persistence wiring** + the **library scope** of `86ajp0a4z`.
3. **Verse-text scripture**: bundle ≥1 PD translation, render verse content, add a wire
   E2E, and give at least one shipped client a scripture command.
4. Unstarted foundation stories: design system/keybindings/a11y (`86ajp0b3d`),
   missing-media + pre-service check (`86ajp0az9`), per-layer emergency clearing
   (`86ajp0awx`), app-shell key acquisition (`86ajp5vp6`).
5. On-device (phone) mobile QA incl. a real camera QR scan; mDNS; per-offer roles.
6. Physical-display enumeration/assignment + identify on the second window.
7. Cross-OS GUI launch smoke; Windows encryption-test toolchain; SBOM/license scan +
   GPU device-loss assertion in CI.
8. User visual re-confirmation of the stage timer readout post-`582d9dc`.

## Milestone disposition
**Not met — the milestone stays open.** Only 1 of 9 steps passes unscoped; the scripted
demo cannot yet run end-to-end as written (no plan authoring, reference-only scripture,
no crash recovery), and 4 of the 14 foundation stories are unstarted. The strong core
(steps 3/4/5/7/8) is real and live-evidenced — but an honest demo day needs gaps 1–3
closed at minimum. Recommended path: recovery (`86ajp09td`) and plan wiring next, then
re-run this review; the reconciliation table goes to the owner at the gate.
