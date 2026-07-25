# Goal Contract — STAGE7-foundation (batch 7a: domain core)

## Identity

- Goal ID: STAGE7-foundation-7a
- Parent goal ID: BUILD-selahcue
- Title: Implement and unit-test the SelahCue domain core (scripture reference parser, service-plan model, monotonic timer) as a Cargo workspace
- Role: backend-engineer (+ software-architect)
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548 (stories 86ajp0afa scripture, 86ajp0a4z plan, 86ajp0ac9 timer)
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Deliver the first production-code slice of the SelahCue foundation: a `selahcue-core` Rust crate implementing (1) a deterministic Bible **scripture reference parser** (FR-027), (2) the **service-plan domain model** with CRUD/reorder (FR-001/002), and (3) a **monotonic timer core** (FR-054/065, NFR-022) — each with comprehensive unit tests that pass under `cargo test`.

## Baseline

Toolchain verified: Rust/cargo 1.97.1, Node 22, Flutter (Apple Silicon). Greenfield — no code yet. ClickUp delivery plan + foundation stories exist (Stage 6). GPU compositor, Tauri shell, Flutter mobile, and CI require a full dev environment/display and are subsequent Stage-7 batches.

## Inputs and evidence sources

- docs/product/prds/SelahCue-PRD.md (FR-027, FR-001/002, FR-054/065, NFR-022); docs/architecture/ARCHITECTURE.md (§8 data model); ADR-0001/0007
- ClickUp stories 86ajp0afa, 86ajp0a4z, 86ajp0ac9

## Scope

### In scope

- Cargo workspace + `selahcue-core` crate (project structure — partial Story S1).
- Scripture reference parser: 66 books + aliases/abbreviations; chapter:verse, verse ranges, whole-chapter, numbered books, multi-reference — pure, deterministic; tests for happy/edge/malformed (Story S10).
- Service-plan domain model: plan + ordered items + CRUD + reorder + duplicate — pure logic (Story S6).
- Monotonic timer core: countdown/count-up on `Instant`, drift-independent, start/pause/resume/reset/adjust, TIME UP/overrun state (Story S9).

### Non-goals

- GPU/wgpu rendering, native windows, Tauri shell, Flutter mobile, SQLite persistence layer, CI (subsequent batches — need display/toolchains/build time).

### Constraints

- Real, compiling, tested code — no placeholders presented as complete. `cargo test` must pass. No panics on malformed input (parser returns Result/None).

### Assumptions and unknowns

- ASSUMED: this batch is the domain-logic slice; the walking skeleton (GPU/Tauri) is a later Stage-7 batch presented at its own gate.

## Dependencies and approvals

- Stage 6 gate approved (yes — authorises implementation). User gate at Stage 7 (pending).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7a-001 | yes | Cargo workspace + selahcue-core crate builds | `cargo build` | Compiles with no errors | build output (Finished) | PASS |
| S7a-002 | yes | Scripture parser handles the FR-027 acceptance cases + edges | `cargo test scripture` | "Rom 8:28-30", "Ps 23", "Jn 3:16; 1 Cor 13:4" parse correctly; malformed rejected without panic (fuzzed ~70 hostile inputs) | test output | PASS |
| S7a-003 | yes | Service-plan model CRUD + reorder correct | `cargo test plan` | All plan tests pass | test output | PASS |
| S7a-004 | yes | Monotonic timer core correct (drift-independent) | `cargo test timer` | All timer tests pass | test output | PASS |
| S7a-005 | yes | Full test suite passes; clippy clean | `cargo test` + `cargo clippy` | 37/37 tests pass; clippy 0 warnings | test output | PASS |
| S7a-006 | yes | Independent code review of the slice | fresh-context reviewer | PASS WITH CONDITIONS (0 high, 1 medium, 3 low) → all findings fixed + regression tests added | implementation/CODE-REVIEW-batch7a.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused: `cargo test` (unit + integration) + `cargo clippy`.
- Independent verifier: fresh-context code review of the crate.
- Environment: local (Apple Silicon).

## Iteration ledger

### Iteration 1

- Target: S7a-001..S7a-006.
- Hypothesis: a well-structured selahcue-core crate with the three modules + tests satisfies the predicate.
- Change: create workspace + crate; implement scripture parser, plan model, timer core, each with tests; run cargo test/clippy; independent review.
- Verifier executed: pending.
- Result: pending.
- Decision: iterate → gate-review.

## Batch 7b — persistence (`selahcue-data`)

- Goal ID: STAGE7-foundation-7b · Status: GATE_REVIEW · Engine: goal · Independent verification: yes
- ClickUp story: 86ajp09he (Persistence). Requirements: ADR-0007; FR-079, FR-154; NFR-017.
- Objective: a crash-safe, migration-versioned SQLite data layer with integrity checks and a plan repository. At-rest encryption (SQLCipher, FR-154) is an explicitly deferred follow-up (feature swap; schema/repos unchanged).

### Completion predicate — batch 7b

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7b-001 | yes | `selahcue-data` crate builds (rusqlite bundled — no system libs) | `cargo build` | Compiles, no errors | build output | PASS |
| S7b-002 | yes | WAL config + integrity check correct | `cargo test db` | WAL/pragmas set; integrity_check ok; reopen idempotent; newer-schema DB refused | test output | PASS |
| S7b-003 | yes | Versioned, atomic, append-only migrations | `cargo test` | user_version tracking; per-migration transaction; forward-compat guard | test output | PASS |
| S7b-004 | yes | Plan repository round-trips faithfully; order + no-reuse id preserved; cascade delete | `cargo test plan_repo` | insert→load equal; order via UNIQUE(plan_id,ord)+tie-breaker; cascade confirmed | test output | PASS |
| S7b-005 | yes | Stored-data errors handled (no panic): unknown tag, out-of-range int | `cargo test plan_repo` | both → DataError::Corrupt | test output | PASS |
| S7b-006 | yes | Crash-safe backup via online backup API (FR-079) | `cargo test backup` | backup restores + passes integrity | test output | PASS |
| S7b-007 | yes | Full suite passes; clippy clean | `cargo test` + `cargo clippy --all-targets` | 50/50 tests pass; 0 warnings | test output | PASS |
| S7b-008 | yes | Independent code review of the crate | fresh-context reviewer | PASS WITH CONDITIONS (0 high, 1 med, 3 low) → M1/L1/L2 fixed + regression tests | implementation/desktop/CODE-REVIEW-batch7b.md | PASS |
| S7b-009 | no | SQLCipher at-rest encryption (FR-154) + no-plaintext-DB security test | — | Deferred: `bundled-sqlcipher` + PRAGMA key feature swap | ClickUp 86ajp09he | NOT_APPLICABLE (deferred follow-up) |

### Iteration ledger — batch 7b

- Target: S7b-001..S7b-008. Change: created `selahcue-data` (error/migrations/db/plan_repo); WAL + integrity + online backup + transactional repo. Independent review → M1 (downgrade guard), L1 (deterministic order), L2 (no silent truncation) fixed with regression tests. Verifier: `cargo test` 50/50, `cargo clippy` clean; fresh-context review PASS WITH CONDITIONS → all conditions resolved. Result: PASS. Decision: gate-review.

## Batch 7c — at-rest encryption (FR-154) + test reorg

- Goal ID: STAGE7-foundation-7c · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- ClickUp story: 86ajp09he (Persistence) → **QA** (data-layer scope complete). Requirements: FR-154; FR-079.
- Objective: SQLCipher at-rest encryption for `selahcue-data`, behind an `encryption` feature; no plaintext on disk; crash-safe *encrypted* backup. Key acquisition (OS secret store / Argon2id) is app-shell scope, deferred to a follow-up.

### Completion predicate — batch 7c

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7c-001 | yes | Encrypted DB round-trips + integrity | `cargo test --features encryption` | round-trip + integrity pass | test_encryption.rs | PASS |
| S7c-002 | yes | No plaintext on disk (marker + header magic absent; WAL encrypted) | `cargo test --features encryption` | scan finds neither | test_encryption.rs | PASS |
| S7c-003 | yes | Wrong key / unkeyed open rejected | `cargo test --features encryption` | both error | test_encryption.rs | PASS |
| S7c-004 | yes | Crash-safe encrypted backup (FR-079+FR-154) | `cargo test --features encryption` | keyed backup reopens, integrity ok, plaintext-free | encrypted_backup test | PASS |
| S7c-005 | yes | Encryption gated so keyless-encrypted-open is impossible | code + `cargo test` (default) | keyed API absent without feature | lib.rs cfg | PASS |
| S7c-006 | yes | Default + encryption builds pass; clippy clean both | `cargo test` / `--features encryption` + clippy | 50 default / 16 data-enc; 0 warnings | test output | PASS |
| S7c-007 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 8 raised → 2 confirmed (H1,L1) → fixed + regression tests; 6 dismissed | CODE-REVIEW-batch7c-encryption.md | PASS |
| S7c-008 | no | OS secret-store key acquisition + Argon2id | — | Deferred: app-shell scope (ADR-0007) | ClickUp 86ajp09he | NOT_APPLICABLE (follow-up) |

### Test organisation (user refine)

Per-crate tests moved to a `tests/` folder, one file per source module (`test_db.rs`,
`test_plan_repo.rs`, `test_encryption.rs`; `test_scripture.rs`, `test_plan.rs`,
`test_timer.rs`) — public-API integration tests. Exception (documented): the one
white-box test that reads the private scripture `BOOKS` table stays inline in
`src/scripture.rs`, since integration tests cannot reach crate-private items.

### Iteration ledger — batch 7c

- Target: S7c-001..S7c-007. Change: added `encryption` feature (SQLCipher + vendored OpenSSL), `EncryptionKey` (raw key, zeroize), `open_encrypted`/`open_in_memory_encrypted`/`backup_to_encrypted`; reorganised tests into `tests/`. Multi-lens adversarial review → H1 (encrypted backup broken) + L1 (key lingers) fixed with regression tests; 6 findings dismissed on verification. Verifier: `cargo test` 50 default + 16 data-encryption; clippy clean both. Result: PASS. Decision: gate-review.

## Batch 7d — LAN control core (`selahcue-lan`)

- Goal ID: STAGE7-foundation-7d · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: FR-118 (protocol), FR-119 (RBAC), FR-120 (pairing/sessions); ADR-0009.
- Objective: the transport-independent operator↔controller control logic — wire protocol, role-based access control, device pairing/sessions — pure and exhaustively testable. The TLS-pinned WebSocket transport is batch 7e.

### Completion predicate — batch 7d

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7d-001 | yes | `selahcue-lan` crate builds; added to workspace | `cargo build` | compiles | build output | PASS |
| S7d-002 | yes | Wire protocol serde round-trips; unknown tags rejected without panic | `cargo test -p selahcue-lan` (protocol) | 8 protocol tests pass; stable tag strings | test_protocol.rs | PASS |
| S7d-003 | yes | RBAC: single authorize() choke point; roles are strict supersets; matrix correct | `cargo test` (rbac) | 9 rbac tests pass incl. superset invariant | test_rbac.rs | PASS |
| S7d-004 | yes | Pairing: single-use, TTL-bounded codes; constant-time token auth; no cross-device confusion | `cargo test` (session) | 13 session tests pass | test_session.rs | PASS |
| S7d-005 | yes | Bearer tokens never printable (SessionToken + AuthRequest Debug redacted) | `cargo test` | redaction tests pass | test_session/test_protocol | PASS |
| S7d-006 | yes | Full suite + clippy clean | `cargo test` + `cargo clippy --all-targets` | 80/80; 0 warnings | test output | PASS |
| S7d-007 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 10 raised → 1 confirmed (M1 token-in-Debug) → fixed + regression test; 9 dismissed; hardening added | CODE-REVIEW-batch7d-lan.md | PASS |
| S7d-008 | no | TLS-pinned WebSocket transport (async server) | — | Deferred: batch 7e (tokio/rustls/tungstenite loopback) | — | NOT_APPLICABLE (next batch) |

### Open design question (routed to product)

RBAC policy: `Clear` maps to `Navigate`, so an **Assistant** can blank the live output. This is deliberate and tested, but whether an Assistant should affect the live output at all (vs. only prepare/stage) is a product decision — flagged at the gate, unchanged pending confirmation.

### Iteration ledger — batch 7d

- Target: S7d-001..S7d-007. Change: created `selahcue-lan` (protocol/rbac/session), pure + injected token/clock. Multi-lens adversarial review → M1 (AuthRequest Debug leaked token) fixed + regression test; added empty-token/empty-code guards, version-check helpers, and cross-device/boundary regression tests. Verifier: `cargo test` 80 workspace (30 in lan); clippy clean. Result: PASS. Decision: gate-review.

## Batch 7e — TLS-pinned WebSocket transport (`selahcue-lan` `server` feature)

- Goal ID: STAGE7-foundation-7e · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: FR-118 (transport), FR-119 (RBAC over the wire); ADR-0009. Pure-Rust crypto (rustls + ring — no OpenSSL/C).
- Objective: carry the LAN control protocol over a certificate-pinned TLS WebSocket, authenticate devices, and enforce RBAC on every command — proven end-to-end over a real loopback socket.

### Completion predicate — batch 7e

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7e-001 | yes | `server` feature builds (pure-Rust TLS, no system libs) | `cargo build --features server` | compiles | build output | PASS |
| S7e-002 | yes | Certificate pinning: correct pin accepted, wrong pin rejected; handshake signature verified | `cargo test --features server` | E2E + wrong-pin tests pass; TLS-security review found no bypass | test_server.rs; review | PASS |
| S7e-003 | yes | Device auth over the wire; wrong/unknown token rejected | `cargo test --features server` | wrong-token test passes | test_server.rs | PASS |
| S7e-004 | yes | RBAC enforced over the wire (Assistant GoLive → Denied; Next → Ack) | `cargo test --features server` | E2E asserts denial + allow | test_server.rs | PASS |
| S7e-005 | yes | No resource leak: half-open connections reaped; connection count bounded; registry bounded | `cargo test --features server` | reaping + leak-guard tests pass | test_server.rs | PASS |
| S7e-006 | yes | Full suites + clippy clean (default + server) | `cargo test` / `--features server` + clippy | 84 default / 39 server; 0 warnings | test output | PASS |
| S7e-007 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 8 raised → 4 confirmed (DoS/resource) → fixed + regression tests; TLS lens clean | CODE-REVIEW-batch7e-transport.md | PASS |

### DoS-hardening applied (from review; serves the no-leak requirement)

Handshake/auth timeout (reaps slowloris half-open connections), `Semaphore` connection
cap (bounds fds/tasks/memory), resilient accept loop (transient accept errors no longer
fatal), and a bounded WebSocket message size (64 KiB, stops large pre-auth buffering).

### Iteration ledger — batch 7e

- Target: S7e-001..S7e-007. Change: added the `server` feature — `pinning` (rustls pinned verifier), `tls` (rcgen self-signed + configs), `server`/`client`/`wire`; loopback E2E. Multi-lens adversarial review → TLS-security clean; 4 confirmed DoS/resource findings (accept-loop-dies, no handshake timeout/cap ×2, 64 MiB frame) → all fixed with a slowloris-reaping regression test. Verifier: `cargo test` 84 default + 39 server; clippy clean both. Result: PASS. Decision: gate-review.

## Batch 7f — testable render-engine seam (`selahcue-engine`)

- Goal ID: STAGE7-foundation-7f · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: ADR-0015; NFR-024, FR-160, FR-175, NFR-004, METRIC-002. ClickUp story 86ajp09m9.
- Objective: the day-one test-harness contract — GPU-free deterministic render + pixel readback, fault-injection proving output-failure isolation, the FR-175 flash analyzer, the NFR-004 latency proxy, and the render↔control IPC contract — so the reliability guarantees are verifiable before the wgpu backend exists.

### Completion predicate — batch 7f

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7f-001 | yes | Crate builds; deterministic headless render + pixel readback | `cargo test` (raster) | golden-image parity; determinism | test_raster.rs | PASS |
| S7f-002 | yes | Fault injection proves output-failure isolation (never-blank NFR-024) | `cargo test` (fault) | all 4 faults hold last good frame; cross-output isolation; recovery | test_fault.rs | PASS |
| S7f-003 | yes | FR-175 flash analyzer operates (worst 1s-window, per-tile, fractional) | `cargo test` (analysis) | strobe/burst/localized/boundary all fail; calm passes | test_analysis.rs | PASS |
| S7f-004 | yes | NFR-004 latency proxy operates | `cargo test` (analysis) | first-content-frame + seconds | test_analysis.rs | PASS |
| S7f-005 | yes | Render↔control IPC contract (serde round-trip, versioned) | `cargo test` (engine) | commands/events round-trip | test_engine.rs | PASS |
| S7f-006 | yes | Bad/oversized frames rejected (held), no panic/abort (no-leak/robustness) | `cargo test` (engine) | Rejected + output held; extreme dims clamp | test_engine.rs | PASS |
| S7f-007 | yes | Full suite + clippy clean | `cargo test` + clippy | 28 engine / 112 workspace; 0 warnings | test output | PASS |
| S7f-008 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 7 raised → 4 confirmed (2 flash false-pass, 1 crash, 1 boundary) → fixed + regression tests | CODE-REVIEW-batch7f-engine.md | PASS |
| S7f-009 | no | wgpu-shared on-screen path + cross-GPU SSIM parity + GPU CI matrix | — | Deferred: needs the wgpu backend + CI (walking skeleton / CI batches) | ADR-0015 | NOT_APPLICABLE (later batches) |

### Iteration ledger — batch 7f

- Target: S7f-001..S7f-008. Change: created `selahcue-engine` (scene/raster/analysis/fault/engine). Multi-lens adversarial review → 4 confirmed: flash whole-capture-average (H) and whole-frame-mean (M) false-passes, /2-truncation boundary (M), and unvalidated-dimension crash (H, defeats never-blank). Reworked the flash analyzer to worst-1s-window + per-tile + fractional; added frame-dimension validation (reject+hold, clamp, usize/checked math). Verifier: `cargo test` 28 engine / 112 workspace; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7g — basic presentation rendering (`selahcue-present`)

- Goal ID: STAGE7-foundation-7g · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: FR-009, FR-012, FR-013, FR-036, FR-046; canonical keybindings. ClickUp story 86ajp0a6q.
- Objective: the core live loop — compose static slides into engine frames and drive Preview→Live, with the invariant that staging never changes Live until Go Live, ≤150ms slide-trigger latency, and clear/blackout on live. Built on the 7f engine seam so it is verifiable headlessly.

### Completion predicate — batch 7g

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7g-001 | yes | Slide + theme compose deterministically into a frame; text within safe area | `cargo test` (compose) | pixel checks; top+bottom margins honored | test_compose.rs | PASS |
| S7g-002 | yes | Preview/Live isolation: staging never changes Live (FR-012) | `cargo test` (present) | live unchanged on stage; only go_live pushes | test_present.rs | PASS |
| S7g-003 | yes | Go Live pushes preview→live; Next/stage distinct | `cargo test` (present) | live == staged after go_live | test_present.rs | PASS |
| S7g-004 | yes | Clear blanks live only; blackout toggles + restores (FR-077) | `cargo test` (present) | clear/blackout correct | test_present.rs | PASS |
| S7g-005 | yes | Slide-trigger latency ≤150ms (real wall-clock at 1080p) | `cargo test` (present) | go_live under budget | test_present.rs | PASS |
| S7g-006 | yes | Tracked state truthful (no "LIVE" while rejected); dims clamped | `cargo test` (present) | consistent under degenerate dims | test_present.rs | PASS |
| S7g-007 | yes | Full suite + clippy clean; bounded state (no-leak) | `cargo test` + clippy | 18 crate / 130 workspace; 0 warnings | test output | PASS |
| S7g-008 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 6 raised → 4 confirmed → fixed + regression tests | CODE-REVIEW-batch7g-present.md | PASS |
| S7g-009 | no | Operator green/red preview/live chrome + labels + borderless fullscreen main output | — | Deferred: operator-console UI (walking skeleton batch) | UX-CANONICAL | NOT_APPLICABLE (UI batch) |

### Iteration ledger — batch 7g

- Target: S7g-001..S7g-008. Change: created `selahcue-present` (slide/compose/present) on the engine seam. Multi-lens adversarial review → 4 confirmed (dimension clamp/tracked-state truthfulness, bottom safe margin, tautological latency test) → fixed + regression tests; blackout-vs-go-live dismissed (matches UX-STATE-MATRIX/FR-077). Verifier: `cargo test` 18 crate / 130 workspace; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7h — stage/confidence display output (`selahcue-present::stage`)

- Goal ID: STAGE7-foundation-7h · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow — 0 findings)
- Requirements: FR-037 (stage monitor: current/next/clock/timer), FR-040 (display identify). ClickUp story 86ajp0aa4.
- Objective: a second independent output — the stage/confidence monitor — showing current + next line, the active timer, and a clock, from the same live state as the main output; plus display identification.

### Completion predicate — batch 7h

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7h-001 | yes | Timer view derived from Timer (ok/warn/TIME UP + progress) | `cargo test` (stage) | state + progress correct at boundaries | test_stage.rs | PASS |
| S7h-002 | yes | Timer bar colour reflects state; TIME UP fills the bar | `cargo test` (stage) | ok/warn/alert pixels | test_stage.rs | PASS |
| S7h-003 | yes | Current + next line regions render content; empty shows none | `cargo test` (stage) | text present/absent | test_stage.rs | PASS |
| S7h-004 | yes | Main + stage show DIFFERENT content from one live state (acceptance) | `cargo test` (stage) | main ≠ stage bytes | test_stage.rs | PASS |
| S7h-005 | yes | Display identify — distinct number per display (FR-040) | `cargo test` (stage) | identify(1) ≠ identify(3); markers | test_stage.rs | PASS |
| S7h-006 | yes | compose_slide unchanged by the layout refactor (no regression) | `cargo test` (compose) | prior pixel tests pass | test_compose.rs | PASS |
| S7h-007 | yes | Full suite + clippy clean; bounded state (no-leak) | `cargo test` + clippy | 26 crate / 138 workspace; 0 warnings | test output | PASS |
| S7h-008 | yes | Independent multi-lens review | fresh-context workflow | 0 findings (clean); regression lens confirmed no pixel drift | CODE-REVIEW-batch7h-stage.md | PASS |
| S7h-009 | no | Second native output window + physical-display enumeration/identify | — | Deferred: native windows (walking skeleton batch) | FR-040 | NOT_APPLICABLE (UI batch) |

### Iteration ledger — batch 7h

- Target: S7h-001..S7h-008. Change: added `stage` (TimerView, compose_stage, compose_identify, StageDisplay) + Presenter::identify; refactored compose.rs to share layout_lines (compose_slide pixel-identical). Multi-lens adversarial review → **0 findings** (regression lens confirmed no compose_slide drift). Verifier: `cargo test` 26 crate / 138 workspace; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7i — walking skeleton: wgpu compositor + native output window (`selahcue-gpu`, `selahcue-desktop`)

- Goal ID: STAGE7-foundation-7i · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: ADR-0002 (wgpu compositor), ADR-0015 (cross-GPU SSIM parity). ClickUp story 86ajp09c2.
- Objective: bring up the GPU compositor — render the engine's scene on wgpu — with an offscreen path verified against the CPU rasterizer (SSIM ≥ 0.99), plus a native output window presenting the live output.

### Completion predicate — batch 7i

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7i-001 | yes | wgpu compositor renders engine scenes offscreen + reads back | `cargo test -p selahcue-gpu` | GPU render succeeds | test_parity.rs | PASS |
| S7i-002 | yes | Cross-backend parity: wgpu ≈ CPU rasterizer, SSIM ≥ 0.99 (ADR-0015) | `cargo test` (GPU present) | opaque/translucent/overlap/blackout/non-aligned all ≥0.99 | test_parity.rs | PASS |
| S7i-003 | yes | Parity oracle is meaningful (alpha, row-padding, per-channel chroma) | review + test | oracle catches blend/stride/chroma regressions | CODE-REVIEW | PASS |
| S7i-004 | yes | `ssim` per-channel + `FrameBuffer::from_rgba` correct | `cargo test -p selahcue-engine` | 30/30 | test_analysis.rs | PASS |
| S7i-005 | yes | Native output window builds (winit + wgpu surface) | `cargo build -p selahcue-desktop` | compiles; surface-loss + keys handled | main.rs | PASS (compile-only) |
| S7i-006 | yes | Full suite + clippy clean | `cargo test` + clippy | 141 workspace; 0 warnings (ex-transitive advisory) | test output | PASS |
| S7i-007 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 11 raised → 6 confirmed (oracle gaps + desktop) → fixed + regression scenes | CODE-REVIEW-batch7i-gpu.md | PASS |
| S7i-008 | no | On-screen window runtime verification; Tauri operator shell | — | Deferred: needs a display (their Mac) / Tauri batch | ADR-0002 | NOT_APPLICABLE (display/UI batch) |

### Environment note

GPU is present here (Metal, Apple M5), so the **offscreen compositor + SSIM parity is
runtime-verified**. The on-screen `selahcue-desktop` window is **compile-verified only**
(no display in this environment) and runs on a Mac via `cargo run -p selahcue-desktop`.

### Iteration ledger — batch 7i

- Target: S7i-001..S7i-007. Change: created `selahcue-gpu` (wgpu compositor: instanced rects, offscreen render + readback) + engine `ssim`/`from_rgba` + `selahcue-desktop` (winit+wgpu window). Multi-lens adversarial review → 6 confirmed: parity oracle never exercised alpha/row-padding and was luminance-only (would pass a broken compositor); desktop surface-loss freeze + case-sensitive blackout key → all fixed (per-channel SSIM, translucent + non-aligned parity scenes, surface-error redraw, case-insensitive key). Verifier: GPU parity ≥0.99; `cargo test` 141 workspace; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7j — glyph text rendering (`Layer::Text` + font8x8)

- Goal ID: STAGE7-foundation-7j · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: FR-009 (basic slide render — real text over background). ClickUp story 86ajp0a6q.
- Objective: replace the placeholder text bars with real, legible glyphs on the output window, using a bundled public-domain 8×8 bitmap font in the CPU rasterizer.

### Completion predicate — batch 7j

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7j-001 | yes | `Layer::Text` renders real glyphs (font8x8), clipped to its rect | `cargo test -p selahcue-engine` | glyph coverage in rect; none outside | test_raster.rs | PASS |
| S7j-002 | yes | Glyphs not mirrored (correct bit order) | `cargo test` | 'L' bar on the left | test_raster.rs | PASS |
| S7j-003 | yes | Text work bounded by the framebuffer (no oversized-px hang) | `cargo test` | 100000-px text renders promptly | test_raster.rs | PASS |
| S7j-004 | yes | compose emits Text; layout + bottom-margin preserved | `cargo test -p selahcue-present` | 26/26 | test_compose.rs | PASS |
| S7j-005 | yes | Desktop output window shows real text (compile + user-run) | build + user | text visible on Mac | main.rs | PASS (user-verified visual) |
| S7j-006 | yes | Full suite + clippy clean; GPU parity intact (Fill-only) | `cargo test` + clippy | 145 workspace; 0 warnings | test output | PASS |
| S7j-007 | yes | Independent multi-lens review; confirmed findings fixed | fresh-context workflow | 4 raised → 2 confirmed (unbounded draw_text, stale doc) → fixed | CODE-REVIEW-batch7j-text.md | PASS |
| S7j-008 | no | GPU-native glyph rendering (glyph atlas) so the compositor can drive a surface | — | Deferred: future ADR-0002 path | ADR-0002 | NOT_APPLICABLE (later batch) |

### Iteration ledger — batch 7j

- Target: S7j-001..S7j-007. Change: added `Layer::Text` + font8x8 CPU glyph rasterizer (LSB-first, verified non-mirrored, clipped); compose emits Text; wgpu compositor skips Text (CPU-composite+blit for on-screen). Multi-lens adversarial review → 2 confirmed: draw_text unbounded work for oversized px/rect (fixed: scale cap + framebuffer-clipped block loop + regression test); stale compositor doc (fixed). Verifier: `cargo test` 145 workspace; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7k — LAN control → presenter (`selahcue-app::LiveController`)

- Goal ID: STAGE7-foundation-7k · Status: GATE_REVIEW · Engine: goal · Independent verification: yes (multi-lens adversarial workflow)
- Requirements: FR-012 (preview/live), FR-118/119 (control + RBAC over the wire). ClickUp story 86ajp0b0t (partial).
- Objective: a remote/mobile controller's commands drive the live output — the complete control loop (client → TLS → server RBAC → handler → controller → presenter), verified end-to-end.

### Completion predicate — batch 7k

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| S7k-001 | yes | Navigation stages Preview; Live untouched until Go Live (FR-012) | `cargo test -p selahcue-app` | Next→preview, live unchanged | test_controller.rs | PASS |
| S7k-002 | yes | Go Live commits staged (plan item OR scripture) to Live | `cargo test` | live shows content; scripture too | test_controller.rs | PASS |
| S7k-003 | yes | Clear/Blackout act on Live; GetState/ScriptureSearch correct | `cargo test` | state + scripture parse | test_controller.rs | PASS |
| S7k-004 | yes | Plan navigation persists across scripture staging | `cargo test` | Next resumes from cursor | test_controller.rs | PASS |
| S7k-005 | yes | E2E: remote Producer drives live over pinned TLS; RBAC + app denials | `cargo test --features server` | 2 E2E pass | test_remote.rs | PASS |
| S7k-006 | yes | RBAC enforced by server before handler (no unauthorized reach) | review + E2E | Assistant GoLive denied | test_remote.rs; review | PASS |
| S7k-007 | yes | Full suite + clippy clean | `cargo test` + clippy | 155 workspace; 0 warnings | test output | PASS |
| S7k-008 | yes | Independent multi-lens review; code findings fixed | fresh-context workflow | 4 confirmed → 3 fixed; 1 RBAC policy routed to owner | CODE-REVIEW-batch7k-app.md | PASS |

### RBAC decision — RESOLVED (tightened per user refine, 2026-07-24)

The review confirmed a **HIGH** RBAC consequence: `Clear` mapped to `Navigate`, so an
**Assistant could wipe the Live output + lift blackout** over the LAN path. Routed to the
owner at the gate; the user chose **"refine: tighten it."** `Clear` now requires a
dedicated `Permission::ClearLive` (Operator + Producer only); Assistant keeps preview
navigation but cannot wipe Live. [DEC-002](../decisions/DECISION-LOG.md) updated to
REVISED. Verified: unit rbac denials + an **E2E Assistant-`Clear`-denied** assertion; a
focused adversarial re-verification found 0 defects.

### Iteration ledger — batch 7k

- Target: S7k-001..S7k-008. Change: created `selahcue-app` (`LiveController` + `handler_for`); added `Reply::Deny` to lan. Multi-lens adversarial review → 4 confirmed: staged-scripture-can't-go-live (×2) + scripture-resets-navigation → fixed (`GoLive` off presenter state; `plan_cursor`) + regression tests; Assistant-can-Clear-Live (HIGH RBAC) routed to owner per DEC-002. Verifier: `cargo test` 155 workspace + 2 E2E; clippy clean. Result: PASS. Decision: gate-review.

## Batch 7l predicate — desktop output window ← remote control

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7l-001 | yes | Desktop `selahcue-output` runs the pinned-TLS control server + a shared `LiveController` | `cargo build -p selahcue-desktop` | builds clean | main.rs | PASS (compile) |
| S7l-002 | yes | A remote command drives the on-screen output (window renders `presenter().live_output()`; continuous vsync repaint reflects remote-only changes) | code review + app E2E of the control loop | remote→server→controller→presenter verified E2E | test_remote.rs; main.rs | PASS |
| S7l-003 | yes | Local keys drive the SAME controller (Space=Next, Enter=GoLive, B=blackout toggle, C=Clear) | compile + review | one shared `Arc<Mutex<LiveController>>` | main.rs | PASS (compile) |
| S7l-004 | yes | Server failure disables remote control only (does not crash the window); binds loopback | review | `eprintln!` + `127.0.0.1:0` | main.rs | PASS |
| S7l-005 | yes | `CertPin::from_hex` round-trips `to_hex`, rejects bad input without panic | `cargo test -p selahcue-lan --features server --lib` | `pin_hex_round_trips` passes | pinning.rs | PASS |
| S7l-006 | yes | Runnable `selahcue-remote` CLI connects + sends a command over the same authenticated path | `cargo build -p selahcue-lan --features server --examples` | example builds | examples/remote.rs | PASS (compile) |
| S7l-007 | yes | Full suite + clippy clean (incl. new example) | `cargo test` + clippy | 155 workspace; lan 40 server; app 10+2 E2E; 0 warnings | test output | PASS |
| S7l-008 | yes | Independent multi-lens adversarial review; confirmed findings fixed | fresh-context workflow `wag2rpohk` | 4 raised → 0 confirmed (4 dismissed) | CODE-REVIEW-batch7l-desktop.md | PASS |

**Compile-only scope (honest):** the on-screen window path cannot be runtime-verified here
(no display). It is compile-verified; the control loop it packages is E2E-verified in
`selahcue-app`. Runnable on the user's Mac via `cargo run -p selahcue-desktop` + the
`remote` CLI. One acknowledged non-blocking nit (UI mutex held across the vsync present)
recorded in the review doc — verified immaterial, no fix warranted (a naive fix is
net-negative and unverifiable here); it dissolves under GPU-native compose (ADR-0002).

### Iteration ledger — batch 7l

- Target: S7l-001..S7l-008. Change: rewired `selahcue-desktop` to run the control server + a shared `LiveController` (local keys + remote both drive it; continuous vsync repaint); added `CertPin::from_hex` (+ unit test) and a lean `selahcue-remote` example CLI. Multi-lens adversarial review (concurrency · wiring · parser/CLI · security) → 4 raised → **0 confirmed** (all adversarially dismissed). Verifier: `cargo test` 155 workspace; lan 40 server; app 10 unit + 2 E2E; clippy clean incl. examples. Result: PASS. Decision: gate-review.

## Batch 7m predicate — operator shell (view-model + shell + Tauri app)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7m-001 | yes | UI-agnostic operator view-model (`OperatorView`) faithfully snapshots controller state (plan + per-item live/preview flags + blackout) | `cargo test -p selahcue-app` | 8 operator tests | test_operator.rs; operator.rs | PASS |
| S7m-002 | yes | `OperatorShell` actions apply-then-snapshot atomically under one lock; poison-safe; clone shares the controller | `cargo test` + review | tests + review | operator.rs | PASS |
| S7m-003 | yes | View-model serializes to the exact JSON fields the UI reads | `cargo test` | `view_serializes_to_the_ui` | test_operator.rs | PASS |
| S7m-004 | yes | Tauri operator app: `#[tauri::command]`s over the shell; commands ↔ frontend arg mapping correct; generate_handler complete | `cargo check` (operator) + review | compiles; review 0 wiring findings | selahcue-operator/src/main.rs | PASS (compile) |
| S7m-005 | yes | Self-contained webview UI renders plan + LIVE/PREVIEW badges and drives the shell; local-desktop security config sound | review | 0 frontend/security findings | dist/index.html; tauri.conf.json | PASS (compile) |
| S7m-006 | yes | Tauri app excluded from the default workspace (heavy/GUI-unrunnable) yet compile-checked | `cargo check` in-crate; workspace test unaffected | operator excluded; 171 workspace | Cargo.toml (exclude) | PASS |
| S7m-007 | yes | Full suite + clippy clean | `cargo test` + clippy | 171 workspace; operator check+clippy clean | test output | PASS |
| S7m-008 | yes | Independent multi-lens adversarial review; confirmed findings fixed | fresh-context workflow `w4d8xq56o` | 3 raised → 1 confirmed (docstring overclaim) → fixed; code logic 0 findings | CODE-REVIEW-batch7m-operator.md | PASS |

**Compile-only + integration scope (honest):** the Tauri GUI cannot be runtime-tested
headless (compile-verified via `cargo check`; operator *logic* verified by unit tests).
The operator shell drives its **own** in-process controller and is **not yet connected**
to the batch-7l on-screen output window — that operator↔output integration is the next
slice. The review's one confirmed finding was a docstring that overclaimed this link;
fixed to a qualified capability statement.

### Iteration ledger — batch 7m

- Target: S7m-001..S7m-008. Change: added the operator control surface (`OperatorView`/`OperatorShell` + `LiveController::operator_view`) to `selahcue-app` with 8 unit tests; built the `selahcue-operator` Tauri 2 app (commands + self-contained webview console), excluded from the workspace and compile-checked separately. Multi-lens adversarial review (view-model · shell-concurrency · tauri-frontend · integration-honesty) → 3 raised → **1 confirmed** (docstring overclaimed the operator↔output link) → **fixed** (qualified); code logic 0 findings. Verifier: `cargo test` 171 workspace; operator `cargo check` + clippy clean. Result: PASS. Decision: gate-review.

## Batch 7n predicate — operator ↔ output-window wiring

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7n-001 | yes | Protocol carries a full operator view: `Command::GetOperatorState` + `ServerMessage::OperatorState{OperatorStateView}` | `cargo test -p selahcue-lan --features server` | 40 server tests | protocol.rs; rbac.rs | PASS |
| S7n-002 | yes | `RemoteOperator` drives the **host's authoritative controller** over pinned TLS and renders the host view | `cargo test -p selahcue-app --features server` | remote-operator E2E | operator.rs; test_operator_remote.rs | PASS |
| S7n-003 | yes | E2E: operator drives host (Next→preview, GoLive→live, blackout/clear) and host controller state reflects it | `cargo test --features server` | 2 E2E pass | test_operator_remote.rs | PASS |
| S7n-004 | yes | A host-denied command is not a client error; the view shows unchanged state (RBAC over the operator path) | `cargo test --features server` | Assistant GoLive denied, no error | test_operator_remote.rs | PASS |
| S7n-005 | yes | Output window advertises a local endpoint (token chmod 0600 unix); removed on clean exit | build + review | write_endpoint/endpoint_path | selahcue-desktop/main.rs | PASS (compile) |
| S7n-006 | yes | Tauri shell connects to a running output window (`RemoteOperator`) or falls back to a standalone demo | `cargo check` (operator) + review | Backend Remote/Local | selahcue-operator/main.rs | PASS (compile) |
| S7n-007 | yes | Client connect is time-bounded (no window-less hang) | `cargo test` + review | `CONNECT_TIMEOUT` mirrors server | client.rs | PASS |
| S7n-008 | yes | Full suite + clippy clean; independent adversarial review; confirmed findings fixed | workflow `wwzeesec0` | 4 raised → 1 confirmed → fixed | CODE-REVIEW-batch7n-wiring.md | PASS |

**Makefile:** a repo-root `Makefile` was added (`make launch` runs the output window +
operator shell together; `make output`/`operator`/`remote`/`demo`/`test`/`check`/`clippy`).

**Honest scope:** the operator↔output loop is verified **headlessly** (the E2E host
controller stands in for the one the output window renders); the Tauri GUI and the
on-screen rendering are compile-verified/prior-verified. Runnable on a Mac via `make launch`.

### Iteration ledger — batch 7n

- Target: S7n-001..S7n-008. Change: extended the LAN protocol (`GetOperatorState`/`OperatorState`/`OperatorStateView`, RBAC Monitor); added `RemoteOperator` (control client) + apply arm + 2 E2E tests; the output window writes a local endpoint (0600, cleaned on exit); the Tauri shell connects to it (Remote) or falls back (Local); added a repo-root Makefile. Multi-lens adversarial review (protocol-rbac · conversion · remote-client · integration-security) → 4 raised → **1 confirmed** (client had no connect timeout → possible window-less hang under `block_on`) → **fixed** (`ControlClient` connect timeout mirroring the server + endpoint cleanup on exit). Verifier: workspace 173; app server 8+2+2 E2E; lan 40; operator check + clippy clean. Result: PASS. Decision: gate-review.

## Batch 7o predicate — timers on the output

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7o-001 | yes | `StartTimer`/`StopTimer` drive a real countdown (were no-ops); injected-clock `tick(now)` starts it | `cargo test -p selahcue-app` | timer lifecycle test | controller.rs; test_controller.rs | PASS |
| S7o-002 | yes | The running timer overlays the live output (bar + `M:SS`/`TIME UP`, state colours) | `cargo test -p selahcue-present` | overlay + TIME-UP tests | compose.rs; test_present.rs | PASS |
| S7o-003 | yes | **An operator blackout is preserved across the per-second timer recompose** | `cargo test` | blackout-preservation test | present.rs; test_present.rs; test_controller.rs | PASS |
| S7o-004 | yes | Countdown display ceils (start value holds a full second; 0:00/TIME UP at expiry) | `cargo test` | ceil regression | stage.rs; test_controller.rs | PASS |
| S7o-005 | yes | Timer in the operator view (`TimerSnapshot`); no stale snapshot on restart | `cargo test --features server` | restart regression + remote E2E | protocol.rs; operator.rs; test_operator_remote.rs | PASS |
| S7o-006 | yes | Triggerable via the CLI (`timer`/`stop-timer`) and the operator UI (Start/Stop + poll); desktop ticks each frame | build + review | CLI + Tauri commands | remote.rs; operator/main.rs; desktop/main.rs | PASS (compile) |
| S7o-007 | yes | Seizure-safe (no flash hazard) + bounded timer state (no-leak) | review + tests | safety lens clean; O(1) state | review | PASS |
| S7o-008 | yes | Full suite + clippy clean; independent adversarial review; confirmed findings fixed | workflow `wgymksqae` | 3 raised → 2 confirmed → fixed | CODE-REVIEW-batch7o-timers.md | PASS |

### Iteration ledger — batch 7o

- Target: S7o-001..S7o-008. Change: wired `StartTimer`/`StopTimer` to a `LiveController` timer + injected-clock `tick`; the presenter overlays it on Live with a blackout-preserving recompose (`show_timer`/`recompose_live`, `timer_display_key`); `compose_live`/`timer_bar_layers`; `TimerSnapshot` in the operator view; CLI + Tauri Start/Stop + poll; desktop ticks each frame; Makefile `remote CMD=timer SECS=`. Multi-lens adversarial review (timer-correctness · **blackout-invariant** · integration-staleness · safety-memory) → 3 raised → **2 confirmed** (floor→ceil display; stale snapshot on restart) → **fixed** + regression tests; 1 dismissed (overrun re-rasterize) → improved anyway; blackout lens clean. Verifier: workspace 181; present overlay + blackout; app timer lifecycle/ceil/restart + remote E2E; operator check + clippy clean. Result: PASS. Decision: gate-review.

## Batch 7p predicate — stage/confidence second window (+ refine: timer → stage)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7p-001 | yes | `LiveController` owns a `StageDisplay`; `tick` refreshes it (gated) from the same live state; `stage_output()` accessor | `cargo test -p selahcue-app` | stage-surface test | controller.rs; test_controller.rs | PASS |
| S7p-002 | yes | The stage/confidence monitor is a **distinct, non-blank** surface (current + next + timer + clock) vs the audience output | `cargo test` | distinct-surface test | test_controller.rs | PASS |
| S7p-003 | yes | Desktop opens **two windows** (audience + stage), each rendering its own surface from one shared controller | `cargo build` + review | two-window App | selahcue-desktop/main.rs | PASS (compile) |
| S7p-004 | yes | **Refine:** the timer renders **only** on the stage/confidence monitor, never on the audience output | `cargo test` | audience-has-no-timer + stage-shows-timer tests | present.rs; test_present.rs; test_controller.rs | PASS |
| S7p-005 | yes | The operator view + CLI + Tauri still trigger/show the timer (moved off Live, not lost) | `cargo test --features server` | remote timer E2E | operator.rs; test_operator_remote.rs | PASS |
| S7p-006 | yes | The two-window loop is deadline-paced: no CPU busy-spin when a window can't present; no starvation under continuous input | review + build | fixed-schedule `new_events`/`about_to_wait` | selahcue-desktop/main.rs | PASS (compile) |
| S7p-007 | yes | Full suite + clippy clean (present/app/desktop/operator) | `cargo test` + clippy | 181 workspace; 0 warnings | test output | PASS |
| S7p-008 | yes | Independent adversarial review (×2 passes); confirmed findings fixed | workflows `we7hbankn`, `wt28silw6` | 2 raised → 2 confirmed → fixed | CODE-REVIEW-batch7p-stage.md | PASS |

**Refine (2026-07-24):** the user directed that the timer belongs on the stage/confidence
output. Removed the entire live-timer overlay (`show_timer`/`recompose_live`/`compose_live`/
`timer_bar_layers`) and reverted the audience `go_live`/`clear`/`blackout` behavior; the timer
now flows only to the `StageDisplay` + the operator view. Tests assert the audience output has
no timer and the monitor shows it.

### Iteration ledger — batch 7p

- Target: S7p-001..S7p-008. Change: `LiveController` owns a `StageDisplay` refreshed (gated) in `tick`; `stage_output()`; `FrameBuffer` re-exported from present; the desktop opens two windows dispatched by `WindowId`. **Refine:** moved the timer to the stage/confidence monitor only. Review pass 1 (`we7hbankn`) → 1 confirmed (continuous-redraw CPU spin) → fixed (deadline-paced loop); pass 2 (`wt28silw6`, post-refine) → 1 confirmed (continuous-input starvation of the paced loop) → fixed (**fixed-schedule** deadline); timer-placement lens clean. Verifier: workspace 181; clippy clean (present/app/desktop/operator); both binaries build. Result: PASS. Decision: gate-review.

## Batch 7q predicate — mobile pairing (QR + host confirmation) + Flutter client

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7q-001 | yes | Pairing redeemable **over the wire**: `Hello{auth\|pair}` v2; server validates the single-use TTL code, requires **host confirmation**, issues server-generated credentials; connection continues authenticated | `cargo test -p selahcue-lan --features server` | 6 pairing E2E over real TLS | protocol.rs; server.rs; test_pairing.rs | PASS |
| S7q-002 | yes | Denial paths verified: host decline, unknown code (no prompt raised), disabled-by-default, single-use replay, expired code | `cargo test` | dedicated E2E per path | test_pairing.rs | PASS |
| S7q-003 | yes | Issued credentials reconnect (graceful-reconnect path) | `cargo test` | pair→control→reconnect E2E | test_pairing.rs | PASS |
| S7q-004 | yes | QR invite (`selahcue://pair?...`) round-trips; rendered on the **stage** output (audience never shows pairing) + ASCII terminal; TTL auto-expiry; cancel **withdraws** the code | `cargo test` | invite + QR + controller tests; withdraw regression | protocol.rs; qr.rs; test_qr.rs; test_controller.rs; test_session.rs | PASS |
| S7q-005 | yes | Desktop pairing UX: P offers (prune + 2min TTL) with QR; Y/N confirms (role disclosed; dead-prompt safe; slot self-heals after a timed-out prompt); LAN bind with a per-run random operator token | build + review + re-verify pass | fixes 1/2/3/5/8/9 verified | selahcue-desktop/main.rs | PASS (compile) |
| S7q-006 | yes | Cross-language wire contract **byte-pinned symmetrically** (every command the app sends) | `cargo test` + `flutter test` | Rust + Dart fixture tests | test_protocol.rs; test/models/protocol_test.dart | PASS |
| S7q-007 | yes | Flutter controller (MVC: models/controllers/views): pinned-TLS session, scan/paste pairing, keystore credentials, plan+controls UI, 1s poll (in-flight-guarded), reconnect (closes the old socket — no-leak) | `flutter analyze` + `flutter test` + `flutter build macos` | analyze clean; 12 tests; macOS app builds | implementation/mobile/ | PASS |
| S7q-008 | yes | Independent adversarial review; confirmed findings fixed + fixes re-verified | workflows `wvg07j8r0` + `w9g29ap5m` | 21 raised → 11 unique → all fixed | CODE-REVIEW-batch7q-pairing.md | PASS |

**Honest scope:** pairing/denial/reconnect are E2E-verified over real TLS; the Flutter
app is analyze/test/macOS-build-verified but **not run on a physical phone here** (user
QA: `make output` → P → `make mobile` → scan → Y). mDNS deferred (QR carries the
address). Pairing grants Producer (disclosed in the prompt); per-offer role choice is a
follow-up. **User refine mid-batch:** the mobile app restructured to **MVC**
(models/controllers/views) — review run against the final structure.

### Iteration ledger — batch 7q

- Target: S7q-001..S7q-008. Change: wire pairing (protocol v2 `Hello`, `complete_pairing` + `PairingApproval` seam + ring credentials), `PairingInvite` URI + `qr.rs` + stage overlay, desktop P/Y/N + 0.0.0.0 bind + random operator token, CLI `pair`, Flutter controller app (MVC) + cross-language fixtures + `make mobile`/`mobile-test`. Review (5 lenses, 26 agents): **21 raised → 21 confirmed → 11 unique defects → all fixed** (approval-slot wedge, withdraw-on-cancel, Dart socket leaks ×2, poll backlog, stale-reply correlation, prune wiring, loopback warning, Producer disclosure, symmetric fixtures, doc drift) + re-verification pass. Verifier: workspace 198; lan server 50; clippy clean; flutter analyze + 12 tests + macOS build. Result: PASS. Decision: gate-review.

## Batch 7r predicate — CI + test infrastructure (per-OS + GPU matrix, NFR evidence)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7r-001 | yes | A per-OS CI pipeline exists: Linux/macOS/Windows matrix — fmt, clippy `-D warnings` (all feature combos), full tests, feature-gated E2E, encryption, operator (Tauri) check, Flutter analyze/test, RustSec audit | YAML structural validation + review | 4 jobs, 3-OS matrices | .github/workflows/ci.yml | PASS (authored) |
| S7r-002 | yes | GPU parity runs in the matrix where an adapter exists and cannot false-fail without one | code check + CI mesa install | test_parity.rs skips gracefully; ubuntu gets lavapipe | ci.yml; test_parity.rs | PASS |
| S7r-003 | yes | A local gate runs the same steps (`make ci`) | **executed here** | ALL GREEN (fmt/clippy/198 tests/E2E/encryption/operator/Flutter) | Makefile | PASS (run) |
| S7r-004 | yes | Both Rust workspaces are fmt-clean so the fmt gate is enforceable | `cargo fmt --check` ×2 | 0 diffs; tests+clippy green after the one-time churn | commit | PASS (run) |
| S7r-005 | yes | Walking-skeleton NFRs measured on a release build with a crash-safe harness | **executed here** (`make nfr`) | cold start **1.13s** ≤3s; idle **121.5MB** ≤300MB (Darwin arm64) | scripts/measure_nfr.sh | PASS (run) |
| S7r-006 | yes | Hosting decided with eyes open (Free-tier runner realities compared) | user decision | **GitHub** (full 3-OS free matrix); GitLab variant authored then removed (in git history) | review doc | PASS |
| S7r-007 | yes | Independent adversarial review; confirmed findings fixed | workflow `wdbqc81qc` | 5 raised → 4 confirmed → fixed (incl. a fabricated-PASS hole in the NFR harness) | CODE-REVIEW-batch7r-ci.md | PASS |
| S7r-008 | yes | Honest activation boundary: hosted execution requires the user-approved repo push | disclosed | no remote/credentials in this env; exact activation steps at the gate | gate report | PASS |

### Iteration ledger — batch 7r

- Target: S7r-001..S7r-008. Change: authored `.github/workflows/ci.yml` (rust 3-OS + operator 3-OS + flutter + audit; PR-only cancel); one-time `cargo fmt` normalization; `make ci` (run: ALL GREEN) + `make nfr` (run: 1.13s / 121.5MB PASS with liveness-checked sampling + endpoint cleanup); a GitLab Free-tier variant authored for comparison and removed after the user chose GitHub. Review (3 lenses, 8 agents): 5 raised → **4 confirmed** (NFR fabricated-PASS ×2 lenses, main-push cancel, stale endpoint) → **fixed** + re-measured; 1 dismissed. Result: PASS. Decision: gate-review.

## Batch 7s predicate — CI-run stabilization (hosted matrix green)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7s-001 | yes | CI activated on a remote (user-created private repo) | `git ls-remote` + `gh run list` | github.com/First-Pavilion/selahcue; runs executing | — | PASS |
| S7s-002 | yes | First-run failures root-caused and fixed (not suppressed) | run logs | 3 red jobs → 2 causes: debug-build latency NFR; missing Windows ICO | 6ef8d9e | PASS |
| S7s-003 | yes | The 150ms latency NFR stays enforced where meaningful | release test via `make nfr` | release run passes in 0.01s; debug keeps a 1.5s tripwire | test_present.rs; measure_nfr.sh | PASS |
| S7s-004 | yes | **The full hosted matrix is green** | `gh run view 30077797265` (independently confirmed) | **8/8 jobs success** (rust ×3, operator ×3, flutter, audit) | Actions run | PASS |
| S7s-005 | yes | GPU parity **executes** on all three backends in CI | runner logs | Vulkan/lavapipe 3.43s · Metal 0.65s · DX12/WARP 2.02s — all ok | run logs | PASS |
| S7s-006 | yes | Independent Linux-leg evidence beyond the runner image | ubuntu:24.04 container repro | all workspace/feature/encryption suites passed | task log | PASS |

### Iteration ledger — batch 7s

- Target: S7s-001..S7s-006. Change: profile-scaled latency budget (release 150ms / debug 1.5s tripwire) + release-budget enforcement in `make nfr`; multi-size Windows `icon.ico` + tauri.conf wiring; docs-only `paths-ignore`. Verified by the hosted 3-OS matrix itself: **8/8 jobs green, GPU parity executed on Vulkan/Metal/DX12** (confirmed via `gh`, run 30077797265). Story 86ajp09nk → QA. Result: PASS. Decision: gate-review.

## Batch 7t predicate — foundation-demo milestone review

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7t-001 | yes | The Gate-6 demo script executed as far as it can run, on the release binary, with recorded state evidence | live demo walk over the real control link | 9-step verdict table incl. a recorded kill→no-recovery FAIL | FOUNDATION-DEMO-REVIEW.md | PASS |
| S7t-002 | yes | Every verdict adversarially audited against code/tests/CI/live ClickUp | 2-agent claims-vs-evidence workflow | **17 findings → all corrected** (no verdict left overstated) | audit `wlzm38x0f` | PASS |
| S7t-003 | yes | Gaps closed with code where cheap, not re-worded | new E2E | `wire_paired_device_advances_the_live_output` (pair→advance vs the real controller, one wire flow); workspace 199 | test_operator_remote.rs | PASS |
| S7t-004 | yes | ClickUp closures reconciled against evidence (owner-facing) | live cross-check | 5 closed-complete stories with undelivered acceptance items tabled for owner disposition | review §reconciliation | PASS |
| S7t-005 | yes | Milestone disposition honest | review | **Not met — stays open** (1 unscoped PASS · 3 scoped · 4 partial · 1 fail); gap list 1–8 | review §disposition | PASS |

### Iteration ledger — batch 7t

- Target: S7t-001..S7t-005. Change: live demo walk (launch→next→go-live→timer→blackout→clear→kill→relaunch, all state-recorded); FOUNDATION-DEMO-REVIEW.md authored → adversarially audited (17 findings: wrong-evidence ×5, overclaim ×7, omission ×5) → **all corrected** + 1 new E2E closing the pair→advance evidence gap. Milestone `86ajp0bpn` stays open; reconciliation table + gap list to the owner. Verifier: workspace 199; fmt+clippy clean. Result: PASS (review complete; milestone honestly NOT met). Decision: gate-review.

## Batch 7u predicate — autosave + crash recovery

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7u-001 | yes | Live session persisted: plan + live/staged/cursor/blackout/timer (+ scripture refs) in SQLite (migrations v2+v3) | `cargo test -p selahcue-data` | 7 session-repo tests incl. FK SET-NULL + corruption | session_repo.rs | PASS |
| S7u-002 | yes | Snapshot/restore rebuilds the exact state through the command paths (byte-identical outputs; timer resumes; blackout returns dark; stale indices safe; no phantom preview) | `cargo test -p selahcue-app` | 6 recovery regressions | controller.rs; test_controller.rs | PASS |
| S7u-003 | yes | Desktop autosave: throttled (≥1s; 5s timer refresh), retry-on-failure, reported degradation, clean-exit save, XDG-correct data dir | build + review | fixes C/D/F verified | selahcue-desktop/main.rs | PASS |
| S7u-004 | yes | **Force-kill + recover, live** | release-binary walk | `Some(2)`+blackout → kill -9 → identical restore | walk transcript | PASS |
| S7u-005 | yes | Real-store migration works | user's v2 DB | upgraded to v3 in place; restored across builds; 1 plan row | sqlite inspection | PASS |
| S7u-006 | yes | Independent adversarial review; confirmed findings fixed | run `wf_9fb846eb-bb6` | 10 raised → 9 confirmed → 6 unique → all fixed | CODE-REVIEW-batch7u-recovery.md | PASS |

### Iteration ledger — batch 7u

- Target: S7u-001..S7u-006. Change: migration v2 (`session_state`) + v3 (scripture refs); `session_repo`; `Timer::with_elapsed`; `ControllerSnapshot`/`snapshot`/`restore` + dirty tracking; `Presenter::clear_preview`; desktop `SessionStore` + throttled autosave + clean-exit save. Review (13 agents, resumed across a session restart): 9 confirmed → **6 unique defects → all fixed** (phantom staged preview — empirically reproduced by a verifier; scripture-on-live blank recovery → schema v3; autosave retry; corrupt-load diagnostics; silent degradation; XDG spec) + regression tests. Verifier: workspace 212; live kill -9 recovery; real-store v2→v3 migration. Demo step 9: FAIL → **PASS**. Result: PASS. Decision: gate-review.

## Batch 7v predicate — plan authoring + persistence wiring + library

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7v-001 | yes | Plan editing over the wire: Add/Remove/Move/Rename commands, **Operator-only** RBAC (`Permission::EditPlan`; Producer denied) | `cargo test -p selahcue-app --features selahcue-lan/server` | `plan_editing_is_operator_only_over_the_wire` (edit lands on the host; Producer edit denied) | protocol.rs; rbac.rs; operator.rs | PASS |
| S7v-002 | yes | Edit arms keep live/staged/cursor indices coherent; removing the LIVE item never blanks the audience output **and survives crash recovery** | `cargo test -p selahcue-app` | index-fixup + never-blanks + `removing_the_live_item_survives_crash_recovery` | controller.rs; test_controller.rs | PASS |
| S7v-003 | yes | Edited plans persist: `plan_repo::update` (transactional re-write) wired to the desktop autosave; plan+session written **jointly** (no stale-index crash window); failed writes retried; clean exit flushes pending edits | `cargo test -p selahcue-data` + review fixes B/C/E | update round-trip; joint-write + retry re-arm in `autosave()` | plan_repo.rs; selahcue-desktop/main.rs | PASS |
| S7v-004 | yes | Library: search (wildcards literal, <300ms at 5k plans) + duplicate-as-template | `cargo test -p selahcue-data` | perf guard 111 hits <300ms; literal-wildcard regression | plan_repo.rs; test_plan_repo.rs | PASS |
| S7v-005 | yes | Operator shell edits the plan in-page (WKWebView has no native dialogs); poll never clobbers an open editor | operator crate check + review fixes A/I | inline rename + two-click delete + render guards | selahcue-operator/dist/index.html | PASS |
| S7v-006 | yes | Independent adversarial review; confirmed findings fixed | run `wcdpt578m` | 14 raised → 14 confirmed → 9 unique (A–I) → **all fixed** | CODE-REVIEW-batch7v.md | PASS |

### Iteration ledger — batch 7v

- Target: S7v-001..S7v-006. Change: 4 plan-edit wire commands + `Permission::EditPlan` (Operator-only; Producer denied over the wire); controller edit arms with index fixup + `plan_dirty`; `plan_repo::update/search/duplicate`; desktop `save_plan` wiring; operator-shell editing UI + add-item row; 5k-plan perf guard. Review (run `wcdpt578m`): 14 confirmed → **9 unique defects (A–I) → all fixed** — dead native dialogs → in-page editing; poll-vs-editor races; **plan/session joint autosave** (stale-index crash window); clean-exit plan flush; failed-plan-write retry; raw token off stdout; removed-LIVE-item recovery; first-run orphan rows; LIKE-wildcard escaping. Verifier: workspace **220** (+2 regressions), clippy clean, operator crate clean, perf guard green. Demo step 2: PARTIAL → **PASS(scoped)** (authoring UI + persistence + library delivered; verse-text and mobile editing remain elsewhere). Result: PASS. Decision: gate-review.

## Batch 7w predicate — design system + canonical keybindings + emergency chrome (86ajp0b3d)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7w-001 | yes | Canonical tokens match UX-CANONICAL §4 **exactly**; one meaning per colour family; Figma design-system inks reconciled (fill/ink roles) | `cargo test -p selahcue-present --test test_tokens` | exactness + drift tests | tokens.rs; DESIGN-TOKENS.md | PASS |
| S7w-002 | yes | Every rendered colour pairing meets **WCAG-AA** (white-on-fills, inks on all dark surfaces, key hints on filled buttons) | Rust + Dart contrast audits | computed ≥4.5:1 in tests on both stacks | test_tokens.rs; design_tokens_test.dart | PASS |
| S7w-003 | yes | Canonical keybindings match §1: Space/→, ←, Enter, Esc Esc (1000ms double-tap), B, Backspace; auto-repeat filtered; any intervening key (incl. host P/Y/N + chords) disarms; emergency bindings non-unbindable | `cargo test -p selahcue-app --test test_keymap` | 7 contract tests incl. disarm + bounded state | keymap.rs; desktop main.rs; webview JS mirror | PASS |
| S7w-004 | yes | Always-on emergency chrome: BLACKOUT (B) + CLEAR ALL (Esc Esc) footer, operable in every state incl. while editing; chords pierce text fields (physical-key matched); non-colour state cues (labels, aria-pressed) | webview pin test + review fixes A/C/D/G/J | `#emergency` needles pinned; blackout state synced outside the editor guard | index.html; test_tokens.rs | PASS |
| S7w-005 | yes | Cross-surface consistency: webview + Flutter + stage display pinned to the same canonical values; no stale hexes; reduced-motion honoured on both UI surfaces | pin tests + residue sweep + `flutter test` | pinning needles (exact badge calls); accent/brand adopted on mobile; MediaQuery.disableAnimations handled | test_tokens.rs; design_tokens.dart; main.dart | PASS |
| S7w-006 | yes | Independent adversarial review; confirmed findings fixed | run `wf_f4a4b8dc-747` (40 agents) | 33 confirmed → 14 unique (A–N) → **all fixed**; 2 refuted | CODE-REVIEW-batch7w.md | PASS |

### Iteration ledger — batch 7w

- Target: S7w-001..S7w-006. Change: `selahcue-present::tokens` (canonical fills + Figma inks + WCAG math) grounded in the live Figma variables (file SYQn5hFY8YVQKm3c6rw0eJ); `selahcue_app::keymap` state machine (double-Esc, disarm, bounded); desktop key rewiring (Esc-quit removed); operator webview retokenized + JS key mirror + `#emergency` footer (Figma console design) + reduced-motion; stage display on semantic inks; Flutter tokens + retokenized views + reduced-motion. Review (40 agents, 5 lenses + adversarial verify): **14 unique defects → all fixed** — headline catches: the `Ctrl/Cmd+Shift+.` emergency chord was dead code (Shift makes `e.key` `">"`), key auto-repeat defeated the double-Esc gate, focused buttons hijacked Enter/Space, stale blackout state while editing could re-assert blackout. Verifier: workspace **232** + Flutter **16**, clippy/analyze clean. Result: PASS. Decision: gate-review.

## Batch 7x predicate — operator console build-out per Figma (86ajpgz4t)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7x-001 | yes | Console structure per Figma node 4:2 within story scope: top bar (name, LIVE chip, clock), plan panel, labeled PREVIEW·STAGED / LIVE·ON AIR panels + GO LIVE, SERVICE TIMER panel | pin test needles | `PREVIEW · STAGED` / `LIVE · ON AIR` / panel ids / blackout overlay pinned | index.html; test_tokens.rs | PASS |
| S7x-002 | yes | On-air truth never stale: panels + LIVE chip + blackout overlay sync on EVERY view (emergency actions land while editing) | review fix A | `setPanel` in `syncChrome` | index.html | PASS |
| S7x-003 | yes | All 14 batch-7w invariants preserved (chords, repeat filter, disarm, blur, aria, AA hints) | regression lens (run `wf_f9323e54-033`) | walked A–N against the new file; all present | CODE-REVIEW-batch7x.md | PASS |
| S7x-004 | yes | A11y on the new chrome: accessible names, aria-live on-air announcements, responsive floor, AA pairings | review fixes B/C/D | aria-labels; aria-live=polite; minmax grid | index.html | PASS |
| S7x-005 | yes | Independent adversarial review; confirmed findings fixed | run `wf_f9323e54-033` (11 agents) | 8 confirmed → 4 unique → **all fixed**; 0 refuted | CODE-REVIEW-batch7x.md | PASS |

### Iteration ledger — batch 7x

- Target: S7x-001..S7x-005. Change: operator webview restructured to the Figma console (story 86ajpgz4t, created this batch under the Accessibility & Design System epic): grid console layout, output panels with canonical fill headers, LIVE chip + clock top bar, timer panel with 5:00/10:00 presets, blackout overlay on the live panel; all 7w systems (tokens/keymap/emergency footer) preserved. Review (11 agents, 3 lenses): 4 unique defects → all fixed — headline: the on-air panel could show stale truth while an editor was open (same class as 7w's blackout fix; panels moved into the every-view chrome sync). Verifier: workspace 232 + Flutter 16, clippy clean. Result: PASS. Decision: gate-review.

## Batch 7y predicate — bundled scripture verse text end to end (86ajpew05)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7y-001 | yes | ≥1 PD translation bundled and audited (WEB, 31,098 verses, offline) | `cargo test -p selahcue-scripture` + review data lens | canon counts + verbatim spot-checks against WEB; bounded one-time index | selahcue-scripture crate | PASS |
| S7y-002 | yes | Verse lookup + keyword search <500ms | perf test (init warmed) | full-scan rare-phrase search under budget | test_scripture_data.rs | PASS |
| S7y-003 | yes | Verse TEXT composes on the audience output within the compositor's real capacity (title + 6 body lines; truncation marker always visible) | capacity pin + cap tests | `compose_slide_renders_title_plus_six_body_lines`; Psalm 119 truncates with "…" | compose.rs test; controller.rs | PASS |
| S7y-004 | yes | **Acceptance:** "Romans 8:28" verse text on the audience output, triggered from a remote client, E2E-tested | `wire_scripture_search_stage_golive_shows_verse_text` | search → stage → GoLive over real TLS; host slide body contains the WEB text | test_operator_remote.rs | PASS |
| S7y-005 | yes | Scripture UI in both clients (operator search-as-you-type + stage; mobile stage command + PREVIEW/LIVE display); recovery fidelity (free slides verbatim — schema v4) | suites + review fixes B/C/F | race-free staging; verbatim-restore regression; v4 round-trip | index.html; controller_view.dart; migrations.rs | PASS |
| S7y-006 | yes | Wire compatibility: v2 fixtures unchanged; NEW fields pinned cross-language | fixture tests both sides | serialize-side Rust fixture == Dart-parsed literal | test_protocol.rs; protocol_test.dart | PASS |
| S7y-007 | yes | Independent adversarial review; confirmed findings fixed | run `wf_516d2959-967` (15 agents) | 10 confirmed → 7 unique (A–G) → **all fixed** | CODE-REVIEW-batch7y.md | PASS |

### Iteration ledger — batch 7y

- Target: S7y-001..S7y-007. Change: new `selahcue-scripture` crate (WEB bundled as gzipped TSV, canonical books 1–66, OnceLock index, lookup/passage/keyword search); `scripture_slide` verse-text composition at StageScripture + both restore paths; keyword fallback in ScriptureSearch; scripture fields on the operator views (skip-if-none — v2 fixtures byte-identical); operator + mobile scripture UI; wire E2E. Review (15 agents, 4 lenses incl. an audit of the decompressed asset and a wire-contract mutation test): **7 unique defects → all fixed** — headline: scripture slides overflowed the compositor's real 7-line capacity (tail + ellipsis silently clipped); recovery could recompose a removed item's title into verse text (→ `live_free_text`, schema **v4**); stale-hit staging races in the operator search. Verifier: workspace **244** + Flutter **18**, clippy/analyze clean. Result: PASS. Decision: gate-review.

## Batch 7aa predicate — display enumeration/assignment + identify (86ajpew0c)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7aa-001 | yes | Display enumeration with stable, collision-free identities (identical-monitor venues assignable) | `cargo test -p selahcue-desktop` | position-ordered ordinal keys, unit-tested incl. re-enumeration | display_keys() in main.rs | PASS |
| S7aa-002 | yes | Per-output assignment persisted (schema v5) and applied as borderless fullscreen at startup + live; a stale key can never destroy a working profile or yank the live output | repo tests + review fix B | validate-before-persist; deny unknown keys at the controller | output_repo.rs; main.rs | PASS |
| S7aa-003 | yes | Identify overlay: host `I` key + wire command, TTL-bound, window-level blit — presentation state untouched | identify lifecycle test | arm → tick-start → expiry; live output byte-identical throughout | controller.rs; main.rs | PASS |
| S7aa-004 | yes | Console OUTPUTS panel: role/display/resolution/assignment picker + Identify; focus-safe rebuilds; truthful async status | review fixes C/E/F/G | republish on Moved/Resized; picker reflects assigned_key; deferred rebuilds | index.html | PASS |
| S7aa-005 | yes | RBAC: ConfigureOutputs Operator-only, wire-tested | E2E | Operator identifies/assigns; Producer denied (no pending change) | test_operator_remote.rs | PASS |
| S7aa-006 | yes | Independent adversarial review; confirmed findings fixed | run `wf_5b9ebabf-34e` (15 agents) | 11 confirmed → 7 unique (A–G) → **all fixed** | CODE-REVIEW-batch7aa.md | PASS |

### Iteration ledger — batch 7aa

- Target: S7aa-001..S7aa-006. Change: outputs wire surface (OperatorStatusView outputs/displays/assigned_key, skip-if-empty — v2 fixtures byte-identical, new fixtures pinned), Commands IdentifyOutputs/AssignOutput behind new Operator-only `Permission::ConfigureOutputs`; controller identify TTL (pairing-QR pattern) + bounded latest-per-role pending assignments + key validation; schema v5 `output_config` + repo; desktop monitor enumeration with collision-free position-ordinal keys, persisted placement (Fullscreen::Borderless), validate-before-persist application, async-truthful status republish on Moved/Resized, window-level identify blit (I key + command); console OUTPUTS panel with focus-safe rebuilds. Review (rerun after a session-limit abort; 15 agents): 11 confirmed → **7 unique (A–G) → all fixed** — headline: identical-projector key collisions (winit-source-verified), persist-before-validate that could drop a live output to windowed mid-service, and the panel rebuild stealing focus so Enter fired GO LIVE. Verifier: workspace **252** + Flutter **19**, clippy clean. On-device 2+-display acceptance pending (headless CI cannot place windows). Result: PASS. Decision: gate-review.

## Batch 7ab predicate — chapter browser + KJV default + console rebalance (86ajpkfcd · 86ajpkfg7)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ab-001 | yes | KJV bundled (31,102 verses, audited verbatim, markup stripped) and the DEFAULT everywhere; WEB retained; per-translation APIs | `cargo test -p selahcue-scripture` | data audit + default tests; both indexes bounded | selahcue-scripture | PASS |
| S7ab-002 | yes | Chapter browser: reference → full numbered chapter; ↑/↓ (incl. held-arrow repeat) move + stage the highlighted verse; ‹ › chapter paging across books; Enter (canonical Go Live) commits — the owner's arrow-to-live flow with preview→live safety intact | acceptance walk + chapter/paging tests | "Genesis 1" → ↓↓ → Enter = Genesis 1:3 on air | index.html; get_chapter | PASS |
| S7ab-003 | yes | Search agrees with the picker (translation-aware, wire-optional field); Enter is never a silent dead-end; ranges stage whole passages; translation switches carry verse NUMBERS (divergent numbering safe) | review fixes A–D | status line; range staging; number-carry with absent-verse guard | protocol.rs; controller.rs; index.html | PASS |
| S7ab-004 | yes | Console rebalance: Preview/Live as 16:9 thumbnails + timer + outputs in the right column; every prior invariant (pins, emergency chrome, focus machinery, outputs panel) preserved | pin tests + regression lens | all needles + 7z/7aa behaviours verified in context | index.html; test_tokens.rs | PASS |
| S7ab-005 | yes | Independent adversarial review; confirmed findings fixed | run `wf_c5226f85-e91` (13 agents) | 9 confirmed → 6 unique (A–F) → **all fixed** | CODE-REVIEW-batch7ab.md | PASS |

### Iteration ledger — batch 7ab

- Target: S7ab-001..S7ab-005. Change: KJV bundle (ebible eng-kjv, brackets/pilcrows stripped) + Translation enum (Kjv default per owner) + per-translation APIs + Chapter/adjacent_chapter paging; optional `translation` on StageScripture AND ScriptureSearch (skip-if-none, fixtures byte-identical); operator get_chapter command (local bundle); console restructure (SCRIPTURES center panel with picker/search/verse list; 16:9 thumbnails right); owner ticket 86ajpqfyj created for further translations (PD bundles vs licensed spike). Review (13 agents): 9 confirmed → **6 unique (A–F) → all fixed** — headline: Enter-on-keywords was a silent dead-end that destroyed the pending search; ranges collapsed to single verses; translation switches could silently stage a different verse where KJV/WEB numbering diverges (asset-verified). Verifier: workspace **253** + Flutter **19**, clippy clean. Translation persistence across recovery = documented gap. Result: PASS. Decision: gate-review.

## Batch 7ac predicate — timer manual entry + live add/subtract (86ajphu98)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ac-001 | yes | Core: adjust a running countdown monotonic-safely; clamps 0..=u32::MAX s (the persisted domain); reduce-below-elapsed lands in TIME UP | `cargo test -p selahcue-core` | adjust semantics + clamp tests; legacy helpers delegate | timer.rs | PASS |
| S7ac-002 | yes | Wire `AdjustTimer{delta_secs}` (fixture-pinned), Timer permission; denied when idle | fixture + controller tests | pinned JSON; idle denial | protocol.rs; rbac.rs | PASS |
| S7ac-003 | yes | **Acceptance:** +1:00 at 1:20 into a 5:00 → 4:40 remaining; adjustment survives crash/restore; −overshoot → TIME UP | controller + E2E tests | `adjust_timer_extends_reduces_and_survives_recovery`; remote E2E | test_controller.rs; test_operator_remote.rs | PASS |
| S7ac-004 | yes | Both clients: bounded minutes entry (1..=999, sanitized) + ±1:00 enabled only with an active timer; demo mode ticks; state-race denials silent on mobile | review fixes B/C/D | webview + mobile controls | index.html; controller_view.dart | PASS |
| S7ac-005 | yes | Independent adversarial review; confirmed findings fixed | run `wf_e358648f-a84` (8 agents) | 6 confirmed → 4 unique (A–D) → **all fixed** | CODE-REVIEW-batch7ac.md | PASS |

### Iteration ledger — batch 7ac

- Target: S7ac-001..S7ac-005. Change: `Timer::adjust` (clamped to the persistable domain; legacy add/subtract delegate), wire `AdjustTimer` + Timer-permission mapping, controller arm with snapshot persistence, console minutes-entry + ±1:00 (disabled without a timer), mobile equivalents, demo-shell ticking. Review (8 agents): 6 confirmed → **4 unique (A–D) → all fixed** — headline: a wire-legal delta could make the recovery snapshot wrap modulo 2³², restoring a different timer than the pre-crash session. Verifier: workspace **256** + Flutter **20**, clippy clean. Owner request ticketed: search-snippet highlighting (86ajpv0ub). Result: PASS. Decision: gate-review.

## Batch 7ad predicate — search-hit highlighting + crash-loop breaker + storage guard (86ajpv0ub · 86ajp09td)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ad-001 | yes | Search hits carry verse text; the console shows reference + translation chip + snippet with ALL query words highlighted (windowed to the first match; escape-safe; AA + bold) | E2E snippet assert + review fixes F/H | wire hits field (skip-if-empty, fixtures byte-identical); compat fallback for pre-7ad hosts | protocol.rs; index.html | PASS |
| S7ad-002 | yes | ↑/↓ select hits in the input, Enter opens the selection | review fix G | first-press cases correct | index.html | PASS |
| S7ad-003 | yes | Crash-loop breaker (FR-169): 3 unstable launches/60s → start clean with checkpointing DISABLED — the preserved session is never touched; stability (10s/clean exit) forgives | guard unit tests + review fix A | pure assess() tests; clean-mode skips every persist path | guard.rs; main.rs | PASS |
| S7ad-004 | yes | Storage guard (NFR-023): low-disk warn, critical halt enforced from STARTUP, exit save honours halts, unknown-space-while-halted keeps reporting — never silent | threshold tests + review fixes B/C/D | disk_status_from tests; startup seeding | guard.rs; main.rs | PASS |
| S7ad-005 | yes | Independent adversarial review; confirmed findings fixed | run `wf_a3c5448f-f47` (12 agents) | 10 confirmed → 8 unique (A–H) → **all fixed** | CODE-REVIEW-batch7ad.md | PASS |

### Iteration ledger — batch 7ad

- Target: S7ad-001..S7ad-005. Change: ScriptureResults.hits (verse text on the wire, compat kept), highlighted windowed snippets + keyboard hit selection in the console; new guard.rs (pure breaker assess + disk thresholds + bounded launch journal) wired through App::new/autosave/exit. Review (12 agents): 10 confirmed → **8 unique (A–H) → all fixed** — headline: the breaker's start-clean would have CLOBBERED the preserved session via the singleton UPSERT (now a checkpointing-disabled clean mode); a critical startup disk wasn't actually halted for 60s; deep-verse highlights invisible past the ellipsis. Verifier: workspace **259** + Flutter **20**, clippy clean. Honest deltas on 86ajp09td for owner disposition: GUI Resume-choice dialog; per-item disable. Result: PASS. Decision: gate-review.

## Batch 7ae predicate — PD translation bundles (86ajpqfyj Track 1)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ae-001 | yes | ≥3 more PD translations selectable in the chapter browser | `cargo test -p selahcue-scripture` | ASV + WEBBE + Darby bundled (5 total, KJV default unchanged); picker offers all five | selahcue-scripture | PASS |
| S7ae-002 | yes | Every bundled text is PD **worldwide**, register-documented | review data lens (live ebible copyright fetch) | BBE excluded (US-only PD — owner decision recorded); WEBBE substituted | LICENSING-REGISTER.md | PASS |
| S7ae-003 | yes | No markup residue anywhere (brackets/pilcrows/apparatus asterisks) | full-corpus scan test (~155k verses) | DBY Ps119 asterisks stripped; pipeline hardened | test_scripture_data.rs | PASS |
| S7ae-004 | yes | Version-safe picker: the HOST advertises its translation list on the wire; shells never offer codes a host denies | fixtures + review fix D | OperatorStateView.translations (skip-if-empty, fixtures byte-identical) | protocol.rs; index.html | PASS |
| S7ae-005 | yes | Independent adversarial review; confirmed findings fixed | run `wf_aa9ffec5-e06` | 4 confirmed → 4 unique (A–D) → **all fixed** | CODE-REVIEW-batch7ae.md | PASS |

### Iteration ledger — batch 7ae

- Target: S7ae-001..S7ae-005. Change: ASV/WEBBE/Darby bundled (lazy per-translation decode, bounded), Translation enum ×5, host-advertised translation list on the wire, full-corpus residue test, licensing register corrected. Review (6 agents incl. a live copyright-page fetch): **4 unique (A–D) → all fixed** — headline: BBE's PD status is US-only (Cambridge UP, plausibly copyrighted to 2038 in life+70 jurisdictions) → dropped and substituted with the worldwide-safe WEB British Edition; BBE also carried literal `***` placeholder verses. Verifier: workspace **260** + Flutter **20**, clippy clean. Result: PASS. Decision: gate-review.

## Batch 7ai predicate — SQLCipher key acquisition (86ajp5vp6)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ai-001 | yes | Key acquired from the OS secret store (random 256-bit, first-run generated) or an Argon2id passphrase (OWASP params, persisted salt); source reported, never silent | `cargo test -p selahcue-desktop --features encryption` | derivation determinism/sensitivity, salt round-trip, hex guards | keys.rs | PASS |
| S7ai-002 | yes | The open path can NEVER wedge or lie: header-discriminated state machine (plaintext stays plain; encrypted+bad-key hard-stops with the true cause, file byte-untouched; unencrypted creation only for a nonexistent file) | state-machine tests | 3 scenario tests with byte-level assertions | main.rs open_store | PASS |
| S7ai-003 | yes | Key hygiene: EncryptionKey + intermediates zeroized (passphrase, hex, buffers); accepted residuals documented | review fix F | zeroize throughout | keys.rs | PASS |
| S7ai-004 | yes | CI exercises the encrypted desktop build (Linux/macOS lanes; Windows skip documented) | ci.yml + make ci | extended encryption lanes | ci.yml; Makefile | PASS |
| S7ai-005 | yes | Independent security review; confirmed findings fixed | run `wf_e8603008-4db` (7 agents, empirical repro) | 6 confirmed (A–F) → **all fixed** | CODE-REVIEW-batch7ai.md | PASS |

### Iteration ledger — batch 7ai

- Target: S7ai-001..S7ai-005. Change: keys.rs (keychain + Argon2id + salt lifecycle + zeroization), header-discriminated open_store state machine, feature plumbing, CI/make lanes. Security review (empirical — the verifier built SQLCipher and reproduced the failure modes): **6 findings (A–F) → all fixed** — headline: a first-run keychain hiccup could mint a plaintext store that permanently wedged persistence behind corruption-looking errors, with a false "opening UNENCRYPTED" message inviting data deletion. Recorded remainder: a rekey/plaintext-migration tool. Verifier: 11 encryption-lane + 262 workspace + 20 Flutter tests, clippy clean both ways, deny green. Result: PASS. Decision: gate-review.

## Batch 7aj predicate — mDNS host discovery (86ajp0b0t remainder)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7aj-001 | yes | Host advertises `_selahcue._tcp` while running (auto-detected addresses, unique instance); phone browses + lists nearby hosts on demand | `flutter test` + build | advertise_mdns + DiscoveryController | main.rs; discovery_controller.dart | PASS |
| S7aj-002 | yes | Discovery does NOT downgrade the pairing trust model: a short-authentication-string (pin fingerprint) must be confirmed before the code is disclosed (defeats rogue-mDNS phishing) | fingerprint tests (Rust+Dart) + SAS gate | `pin_fingerprint` pinned both sides; confirm-before-code dialog | main.rs; discovery.dart; pairing_view.dart | PASS |
| S7aj-003 | yes | Platform declarations so discovery actually works: iOS local-network + Bonjour; Android multicast permission | manifest inspection | Info.plist + AndroidManifest | ios/android manifests | PASS |
| S7aj-004 | yes | Independent adversarial review; confirmed findings fixed | run `wf_bd3f4a1c-0b4` (6 agents) | 5 confirmed (A–E) → **all fixed** | CODE-REVIEW-batch7aj.md | PASS |

### Iteration ledger — batch 7aj

- Target: S7aj-001..S7aj-004. Change: host mDNS advertising (mdns-sd, auto-addr, fingerprint-bearing name), mobile DiscoveryController + Nearby-hosts UI, pin-fingerprint SAS gate (Rust+Dart, pinned), iOS/Android manifest declarations. Security review (6 agents, manifest-aware): **5 findings (A–E) → all fixed** — headline: mDNS supplied the cert pin, enabling a rogue host to phish the pairing code and pivot to Producer control; closed with a confirm-the-fingerprint gate that restores the QR-model's atomic trust. Verifier: workspace **263** + Flutter **23**, clippy/deny/analyze clean. Recorded remainders on 86ajp0b0t: Android MulticastLock (native), on-device phone QA. Result: PASS. Decision: gate-review.

## Batch 7al predicate — mobile Producer revamp: tabbed shell + connection flow (86ajpx7bd)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7al-001 | yes | The crammed single screen is replaced by a progressive-disclosure tabbed shell (Live/Plan/Scripture/Timer via IndexedStack) with a PERSISTENT emergency strip (Blackout/Clear All) above the nav on every tab | `flutter analyze` + build | tabbed ControllerView + EmergencyStrip | controller_view.dart; mobile_widgets.dart | PASS |
| S7al-002 | yes | Splash→Connect→Controller flow: returning user reconnects behind a brief brand moment; first-run/failure lands on the "Nearby hosts / Scan QR / paste" Connect screen; nearby hosts auto-browse on entry | `flutter test` + build | branded Splash; auto `_discovery.refresh()` | main.dart; pairing_view.dart | PASS |
| S7al-003 | yes | Single-tap stages to Preview; double-tap sends live in one verified gesture (stage must actually land before commit — never commits stale Preview) | controller tests + build | `selectAndGoLive`/`stageScriptureAndGoLive` (verify staged before go-live) | live_controller.dart; plan_tab.dart; scripture_tab.dart | PASS |
| S7al-004 | yes | About/connection drawer with connection details (host:port, role, pin fingerprint, live status) and a Disconnect (un-pair); scripture reference autocomplete (offline 66-book suggester) | `flutter test` | `_AboutDrawer`; `bible_books.dart` + chips | controller_view.dart; bible_books.dart; scripture_tab.dart | PASS |
| S7al-005 | yes | Independent adversarial review; confirmed findings fixed; no unbounded growth (bounded suggester; sticky-denial tested) | run `wf_40675e8e-899` (13 agents) | 6 confirmed → 5 unique (A–E) → **all fixed** | CODE-REVIEW-batch7al.md | PASS |

### Iteration ledger — batch 7al

- Target: S7al-001..S7al-005. Change: tabbed `ControllerView` (bottom NavigationBar + IndexedStack + persistent EmergencyStrip), four focused tabs (Live/Plan/Scripture/Timer), branded Splash + "Nearby hosts" Connect flow, single-tap-preview/double-tap-live with verified staging, About drawer + Disconnect, offline scripture autocomplete, and a `ControllerSession` interface extracted for testability. Adversarial review (13 agents, 3 lenses each verified to refute): **6 confirmed → 5 unique (A–E) → all fixed**; 3 refuted — headline: the new command-denial banner was **inert** (`act()`'s refresh and the 1s poll both nulled `_error`, so a denied CLEAR ALL/BLACKOUT flashed sub-frame and the RBAC-limited Producer got no feedback mid-service) → closed by splitting the transient connection status from a **sticky denial** that survives the poll (regression-tested). Also fixed: glyph-only transport buttons had no accessible name (a11y), blank AppBar on an unnamed plan, Nearby-hosts never auto-searching, and a splash session-leak window. Verifier: `flutter analyze` clean + **29** Flutter tests (+3 controller denial-lifecycle). Recorded remainder on 86ajpx7bd: on-device QA; mobile verse-list parity needs a wire path. Result: PASS. Decision: gate-review.

- **Refine (2026-07-25, owner: 3 asks).** (1) The About/connection nav **drawer** was removed (a second nav surface competing with the bottom tabs) → relocated to a top-bar action opening a modal sheet (live status + Disconnect) + a wall clock. (2) A real **chapter verse list on mobile** — mobile has no local bundle, so this added a **read-only `GetChapter` wire command** (Rust `Command::GetChapter` + `ServerMessage::Chapter` + `VerseView`, gated on `SearchScripture`, served via the existing `chapter_in`/`adjacent_chapter_in`; Dart `cmdGetChapter`/`ChapterResult`/`fetchChapter`; NO version bump — additive at v2, old hosts degrade to reference-only). The Scripture tab is now the desktop browser on the phone: translation picker · `‹ Book Chapter ›` nav · numbered verses · **single-tap → Preview / double-tap → Live**, staged verse green / live red, with translation threaded through staging. (3) **Figma ↔ implementation synced**: the Scripture frame already specified the verse list (built to it), the drawer was never in Figma, and the About/info affordance was added to the `MobileTopBar` component — both now read plan name · ● LIVE · clock · ⓘ About. Adversarial review (run `wf_eff76b11-dca`, 11 agents, 3 lenses each verified): **8 confirmed → 5 unique (A–E) fixed + 1 accepted tradeoff (F); 0 refuted; wire-compat lens clean** — headline: a verse that was both staged and live rendered **green (preview) instead of red (live)** because `_VerseRow` tested staged before live while the host reports staged==live after go-live → reordered to live-first (matches plan_tab), regression-tested. Also fixed: silent failed-lookup (SnackBar + field re-sync), transient-blip false "old host" fallback (retry across reconnect), initial-preload never firing (listen-until-view), stale reference field after ‹ › nav. Verifier: **266** Rust tests (+3) + **36** Flutter tests (+ verse-coloring widget test), clippy/analyze clean, cross-language fixtures pinned both sides. Result: PASS. Decision: gate-review.

## Batch 7am predicate — emergency-controls closeout + per-layer deferral (86ajp0awx)

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7am-001 | yes | Canonical keybindings match UX-CANONICAL exactly, on the Rust map AND the operator webview's JS mirror | `cargo test -p selahcue-app --test test_keymap` | Rust contract (8 tests) + webview mirror pinned by content (incl. Space→Next) | keymap.rs; test_keymap.rs; index.html | PASS |
| S7am-002 | yes | Emergency keys fire even over a dialog (modal-pierce): the global chords are handled BEFORE the input-focus early-return, capture-phase | webview contract test (structural ordering assertion) | chord positions precede the input bail-out; capture arg pinned structurally | test_keymap.rs; index.html | PASS |
| S7am-003 | yes | Blackout/clear act <200ms with the network disabled | `cargo test -p selahcue-app --test test_controller` | in-process presenter (no LAN on the desktop emergency path); Ack + effect within 200ms (~1000× margin) | test_controller.rs | PASS |
| S7am-004 | yes | Per-layer clearing correctly deferred (not faked): the single-slide model makes ClearLayer==Clear today; split to an R2 follow-up, comments consistent | review closeout-soundness lens | live output is one Slide; ClearLayer→86ajpy59e in keymap.rs/main.rs/index.html | 86ajpy59e | PASS |
| S7am-005 | yes | Independent review; confirmed findings fixed | run `wf_4dd40dc7-881` (7 agents) | 3 confirmed → 2 unique (low, test gaps) → **fixed**; 2 refuted | CODE-REVIEW-batch7am.md | PASS |

### Iteration ledger — batch 7am

- Target: S7am-001..S7am-005. Change: verified/hardened the already-shipped emergency controls with the story's required tests — a webview keybinding + **modal-pierce** contract test (reads `index.html`, pins the JS keymap to the canonical map and asserts the emergency chords are matched before the input-focus early-return, capture-phase) and a **blackout/clear offline+<200ms** locality/latency test; comment-only edits pointing the "ClearLayer aliases to Clear-all" note at the new follow-up. **Scoping decision (owner-approved): per-layer clearing deferred** — the live output is a single `Slide` (no independently-addressable layers), so real per-layer clearing needs the R2 multi-layer/overlay model; split into `86ajpy59e` under R2. Review (2 lenses, verified): **3 confirmed → 2 unique (both low, in the new tests) → fixed** (Space→Next now pinned; capture-phase check made structural); 2 refuted; closeout-soundness lens confirmed the deferral is sound. Verifier: workspace **268** (+2), clippy clean. Result: PASS. Decision: gate-review.

## Batch 7an predicate — cross-OS GUI-launch smoke + per-OS NFR (86ajpevzp)

Executed via the `/goal` engine against `docs/delivery/goals/TASK-86ajpevzp-launch-smoke.md` (validator `--require-complete` PASS; 5/5 mandatory PASS).

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7an-001 | yes | A GUI-launch smoke mode presents the first frame + exits 0; a watchdog + CI timeout fail loudly instead of hanging | `cargo run --release -p selahcue-desktop -- --smoke` + unit test | exit 0, "SMOKE OK … (from App init)"; `smoke_mode_requested` test | main.rs | PASS |
| S7an-002 | yes | `launch-smoke` CI job proves cross-OS launch (windows created + first frame presented + exit 0) | CI run 30142530116 | ubuntu (Xvfb+lavapipe) + macOS green; Windows documented limitation + recorded run | ci.yml | PASS |
| S7an-003 | yes | Per-OS cold-start ≤3s + idle ≤300MB, GATED in CI on Linux; macOS baseline; Windows POSIX limitation | `make nfr` (gated) | Linux 0.058s / 203MB; macOS 1.13s / 121.5MB | measure_nfr.sh | PASS |
| S7an-004 | yes | Cross-OS NFR script actually works (was broken on Linux) | `xvfb-run make nfr` in CI | `mktemp` portability fixed; Linux figures produced | measure_nfr.sh | PASS |
| S7an-005 | yes | Independent review; confirmed findings fixed | run `wf_12f98261-a6c` (13 agents) | 11 raised → 7 confirmed → **all fixed**; 4 refuted | CODE-REVIEW-batch7an.md | PASS |

### Iteration ledger — batch 7an

- Target: S7an-001..S7an-005. Change: a GUI-launch **smoke mode** (`--smoke`/`SELAHCUE_SMOKE`) in `selahcue-desktop` (present first frame → exit 0 + time-to-first-frame; 30s watchdog + CI `timeout-minutes` backstop; unit-tested flag detection; no session persistence), a **`launch-smoke` CI job** (ubuntu headless under Xvfb + lavapipe; macOS on the runner; Windows a documented headless-present limitation), and a **`measure_nfr.sh` portability fix** (`mktemp -t <prefix>` was broken on GNU/Linux — the NFR script only ever ran on macOS). Executed through the `/goal` engine (5 iterations). Adversarial review (13 agents, 2 lenses each verified): **11 raised → 7 confirmed → all fixed** (headline: the review caught that C-004 overstated the ≤3s cold-start by using the 5.2s software-lavapipe first-frame instead of the `make nfr` proxy — reframed honestly; also added the CI hang backstop and made the NFR budgets gate). Verifier: CI run 30142530116 green — launch proven on Linux headless + macOS; NFR budgets gate (Linux 0.058s / 203MB); 269 workspace tests, clippy `-D warnings` + fmt clean. Windows launch recorded once (522ms) then documented as an intermittent runner limitation. Result: PASS. Decision: gate-review.

## Batch 7ao predicate — Android MulticastLock for mDNS discovery (86ajp0b0t remainder)

Executed via the `/goal` engine against `docs/delivery/goals/TASK-86ajp0b0t-android-multicastlock.md` (validator `--require-complete` PASS; 5/5 mandatory).

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ao-001 | yes | A MulticastLock abstraction + best-effort Android-only PlatformMulticastLock; refresh() acquires around the browse and always releases; never throws | `flutter analyze` | clean | multicast_lock.dart; discovery_controller.dart | PASS |
| S7ao-002 | yes | Unit tests prove acquire→browse→release, no-wedge on browse error, no double-acquire on concurrent refresh | `flutter test` | 3 lock tests pass | discovery_controller_test.dart | PASS |
| S7ao-003 | yes | Android host registers `selahcue/multicast` + acquires/releases a WifiManager.MulticastLock (isHeld-guarded; released on destroy); compiles | `flutter build apk --debug` (CI) | APK builds — Kotlin compiles | MainActivity.kt; ci.yml | PASS |
| S7ao-004 | yes | flutter analyze + test + apk build green in CI | CI run | green | run 30143369094 (+ re-run landing the review fix) | PASS |
| S7ao-005 | yes | Independent review; confirmed findings fixed | run `wf_96cabb67-4a5` | 3 raised → 1 confirmed → **fixed**; 2 refuted | CODE-REVIEW-batch7ao.md | PASS |

### Iteration ledger — batch 7ao

- Target: S7ao-001..S7ao-005. Change: a Dart `MulticastLock` abstraction + best-effort `PlatformMulticastLock` (`selahcue/multicast` channel, Android-only), `DiscoveryController.refresh()` holding the lock across the browse and **always releasing** it (mDNS browse extracted behind an injectable seam), a Kotlin `MainActivity` channel handler (non-ref-counted lock, `isHeld`-guarded, released on destroy), 3 lock-lifecycle unit tests, and a `flutter build apk --debug` CI step compile-verifying the Kotlin. The `CHANGE_WIFI_MULTICAST_STATE` permission (7aj) is now matched by the runtime lock — so Android multicast reception actually works. Executed via the `/goal` engine (3 iterations). Adversarial review (2 lenses, each verified): **3 raised → 1 confirmed → fixed** (headline: `refresh()` lacked a `catch`, so a throwing browse would leave `_searching=true` forever — a permanent discovery lockout, masked in production but undefended; now best-effort, never wedges); 2 refuted. Verifier: `flutter analyze` clean + **39** Flutter tests; CI green incl. the APK build. On-device discovery (real phone finds a host over mDNS) is explicit owner QA. Result: PASS. Decision: gate-review.

## Batch 7ap predicate — Figma operator-console refresh (86ajpx7c0 remaining half)

Executed via the `/goal` engine against `docs/delivery/goals/TASK-86ajpx7c0-console-refresh.md` (validator `--require-complete` PASS; 5/5 mandatory). Design deliverable — no repository code.

| ID | Required | Criterion | Verify | Evidence | Artifact | Status |
|---|---|---|---|---|---|---|
| S7ap-001 | yes | A console frame reproduces the shipped 3-column IA (header · plan · scriptures CENTER · preview/live 16:9 + timer + outputs · emergency footer) | get_metadata/get_screenshot | all panels in the correct columns | Figma node 150:124 | PASS |
| S7ap-002 | yes | Fills bound to the "SelahCue Color" variables (not forked); preview=green / live=red | use_figma bound vars | bound to VariableID:3:3..3:13 | Figma | PASS |
| S7ap-003 | yes | Post-MVP concept bands (transcript, auto-detection) excluded | screenshot | absent | screenshot | PASS |
| S7ap-004 | yes | Screenshot matches the shipped console | get_screenshot vs index.html | visual match | node 150:124 PNG | PASS |
| S7ap-005 | yes | Independent design review; findings fixed | design-reviewer agent | faithful; 3 mediums fixed | CODE-REVIEW-batch7ap.md | PASS |

### Iteration ledger — batch 7ap

- Target: S7ap-001..S7ap-005. Change: built a new Figma frame `150:124` "Operator Console — shipped (86ajpx7c0)" reproducing the shipped 3-column operator console (header · Service plan · **Scriptures centered** with the numbered verse list + cursor · right column Preview/Live 16:9 + GO LIVE + Service timer + Outputs + Identify · emergency footer), every fill bound to the "SelahCue Color" variables. The pre-shipping concept frame `4:2` (Preview/Live 2-up + R3 transcript band + R4 scripture-detection band + "Cloud OFF") is preserved for history; the R3/R4 bands were deliberately dropped. Independent design review (reviewer agent vs the shipped `index.html`): **structurally faithful; no high-severity; 3 medium divergences fixed** — BLACKOUT off-state made dark (was light), timer controls laid out across the shipped 3 rows, Outputs given the real role labels (Main output / Stage display) + Assign picker + full-width Identify. Verifier: get_screenshot before/after vs the shipped console. Result: PASS. Decision: gate-review.

- **Refine (2026-07-25, owner: better Operator UX + remove the queue).** The owner wants the Operator design to INCLUDE a **Live transcript** + **Recent detections** (auto-detected scriptures with confidence · Add-to-plan · Preview — like Pewbeam) but uncramped and on SelahCue's own tokens; the transcript (R3) + detection (R4) are post-MVP, so this is the target design (design leads implementation). Built a new 4-zone frame `161:124`: **Service Plan** (running order) · **Listen** (transcript + detections) · **Program** (Preview/Live 16:9 + GO LIVE + "Coming next") · **Reference** (scripture browser + timer + outputs) + emergency footer, all bound to the "SelahCue Color" variables. A design-reviewer agent judged the first version "faithfully delivers the intended better Operator UX"; 2 med + 3 low findings fixed (transcript "listening…" cue + legend, detection action renamed **Preview**, HIGH/MED/LOW confidence labels, dup header BLACKOUT removed, neutral Pause). **Owner insight adopted:** the **Queue was removed** (redundant with the Service Plan + Preview — the plan is the running order, Preview is the on-deck) and the **Service Plan restored** (it had been dropped when the Listen zone was added). Verifier: get_screenshot of `161:124`; Goal Contract `--require-complete` PASS. Then the owner directed a smoother OBS-native reorg → final frame `165:124`: transcript + detections moved right (timer bottom-right corner), PROGRAM as OBS studio-mode (Preview | Live horizontal + GO LIVE transition), Scriptures directly below PROGRAM. Result: PASS. Decision: gate-review.

## Risks and rollback

- Risks: scope creep into GPU/UI (out of scope this batch). Rollback: git-versioned; additive crate.

## Pause and escalation conditions

- Escalate at the gate; present remaining foundation batches (skeleton, persistence, CI, UI, mobile) as next steps.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/STAGE7-foundation.md` + `cargo test`
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: IN_PROGRESS → GATE_REVIEW
- Remaining failed or blocked criteria: all PENDING
- ClickUp final evidence comment: PENDING
