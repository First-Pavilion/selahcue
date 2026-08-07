# Presentation Browse→Present→Edit — Delivery Tracks (specialist routing)

**Purpose.** Route the implementation plan
([2026-08-07-presentation-browse-present-flow.md](2026-08-07-presentation-browse-present-flow.md))
into two specialist tracks so they can run largely in parallel:

- **Track A — Backend** → the `/backend-engineer` skill (Rust: render engine + Tauri host commands + API).
- **Track B — Frontend** → the `/frontend-engineer` skill (the `dist/` operator webview flow).

Design authority: the approved spec
([2026-08-04-presentation-browse-present-flow-design.md](../specs/2026-08-04-presentation-browse-present-flow-design.md)).
Both tracks are execution evidence and must link back to the ClickUp story (epic `86ajp07ce`).

---

## 0. Frozen integration contract (freeze FIRST — the seam both tracks build against)

Backend **produces** and Frontend **consumes** exactly this. Freezing it up front lets Track B start
Tasks 7–8 immediately and stub 9–13 while Track A lands the real thing.

| Symbol | Shape | Owner |
|---|---|---|
| Tauri command `deck_go_live_delta` | `invoke("deck_go_live_delta", { delta: number /* ±1 */ }) -> DeckView` (advances live, clamped; presents atomically) | Backend (Task 5) |
| `OperatorView.live_authored_id` | field on `invoke("view")` → `number \| null` (host-truth id of the authored slide on Live) | Backend (Task 6) |
| Tauri command `output_connected` | `invoke("output_connected") -> boolean` (real audience output attached?) | Backend (Task 6) |
| existing (unchanged) | `deck_open`, `deck_view`, `deck_select_slide`, `deck_go_live`, `render_deck_slide({id,maxW,maxH})`, `view().blackout` | already shipped |

Any change to this table is a cross-track event — update both Goal Contracts and notify the other track.

---

## Track A — Backend (`/backend-engineer`)

**Scope:** implementation-plan **Phase 1 (Tasks 1–3)** + **Phase 2 (Tasks 4–6)**.
- Engine (`selahcue-present`, `selahcue-gpu`): retain the authored slide as live content; mirror it in `compose_screen_live`; recompose it on theme/layer switch; add the authored-representative SSIM parity scene.
- Host (`selahcue-operator`, `selahcue-app`): `DeckWorkspace::go_live_delta`; `deck_go_live_delta` command; `OperatorView.live_authored_id`; `output_connected` + `Backend::is_remote`.

**Goal Contract completion criteria (Boolean, verifiable):**
- `cargo test -p selahcue-present` green, including the four new tests (authored-live tracked/cleared; secondary mirroring; zero-element never-blank; theme-switch survival).
- `cargo test -p selahcue-gpu` green (SSIM ≥ 0.99; GPU-absent SKIP acceptable locally, REQUIRED in CI).
- `cargo test -p selahcue-app` green, including `operator_view_reports_the_live_authored_slide_id`.
- `cargo test --manifest-path .../selahcue-operator/Cargo.toml go_live_delta` green (clamp at both ends + empty-deck no-op).
- `cargo check --manifest-path .../selahcue-operator/Cargo.toml` clean.
- The §0 contract is delivered exactly (command names, arg names, field name, types).
- `make ci` passes for the Rust gates (fmt, clippy -D warnings, all suites).

**Verification evidence:** test output pasted into the ClickUp task; the commit shas for Tasks 1–6.

---

## Track B — Frontend (`/frontend-engineer`)

**Scope:** implementation-plan **Phase 3 (Tasks 7–13)** — the `dist/` webview browse/present/edit flow.

**Dependency split:**
- **No backend dependency (start immediately):** Task 7 (three-mode state, land on Library, remove Back-to-editor), Task 8 (grid DOM, styles, lazy bounded-cache thumbnails via the already-shipped `render_deck_slide`).
- **Depends on the §0 contract:** Task 9 (`deck_go_live_delta`, `view().live_authored_id`), Task 10 (`output_connected`, `view().blackout`). Until Track A lands, build against the headless stubs the plan already specifies (they mimic the contract), then re-verify against the real host.
- Task 11 (relocate present entry points), Task 12 (a11y + tokens), Task 13 (full CI gate).

**Goal Contract completion criteria (Boolean, verifiable):**
- `python3 scripts/operator_headless.py` green with `EXPECTED_MIN_CHECKS` bumped by the number of added checks (no lost checks).
- Every §8 state renders: empty-deck, loading/render-fail, nothing-live, live (host-truth ring), first/last disabled, go-live-failed (no ring), preview-only, blackout, deck-open-failed, reconnecting.
- a11y: `role="grid"` + roving `tabindex`; three separable rings by geometry (inset selection / outset focus / red live+label); `aria-live` announcements.
- Token audit: no legacy `--live`/`--panel`/`--line`/`--accent` in the new `.pm-grid*`/`.pm-tile*`/`.pm-transport` rules.
- Manual smoke (`make launch`): library → grid → double-click go-live → arrows advance live across ALL outputs → Edit ▸ / ‹ Done.
- `make ci` green end-to-end (Task 13).

**Verification evidence:** headless output + `make ci` output in the ClickUp task; commit shas for Tasks 7–13.

---

## Sequencing & dependency graph

```
FREEZE §0 contract (joint, 15 min)
        │
        ├──────────────► Track A: Tasks 1→2→3 (engine) → 4→5→6 (host)        [backend-engineer]
        │
        └──────────────► Track B: Tasks 7→8 (parallel, no dep)               [frontend-engineer]
                                    │
                    (Track A Tasks 5–6 landed) ──► Track B: 9→10→11→12
                                                              │
                                              Track B: Task 13 = FULL `make ci` (integration gate)
```

- **Parallelism:** Track A and Track B Tasks 7–8 start together. Track B Tasks 9–10 verify against the real host once Track A Tasks 5–6 land (before then, the headless stubs stand in).
- **Integration gate:** Task 13 (`make ci`) is the join point — owned by whichever track lands last (normally Frontend). It must run the whole suite: engine + gpu + app + operator check + headless webview.

---

## Prerequisites (before either skill starts substantive work)

1. **ClickUp story** under epic **Presentation & Slides `86ajp07ce`** (parent for both tracks; or one story with a backend + a frontend sub-task). Record goal IDs, contract paths, engine, and iteration limits per the specialist-skill protocol. *(Outward-facing — create only with owner go-ahead.)*
2. **Goal Contracts** under `docs/delivery/goals/` — one per track, decomposing the criteria above; validate each with `python3 scripts/validate_goal_contract.py <contract>` before work and before any completion claim.
3. Keep the **Build Control** task (`86ajnx548`) updated as batches land.

## Risks / watch-items

- **Contract drift** (§0) — freeze it; any change is a two-track event.
- **`DeckWorkspace.live` staleness** — the grid must ring from host `live_authored_id`, never the editor-local annotation (Track A delivers the signal; Track B must consume it, not `dv.live`).
- **Thumbnail fan-out** — `render_deck_slide` has no batch path and each call takes the deck lock; Track B lazy-renders visible tiles with a bounded cache (no unbounded growth).
- **Secondary/NDI mirroring** is in-scope engine work (Track A Tasks 2–3), not a follow-up — multi-screen rigs must show the authored slide, verified by the mirroring + never-blank tests.
