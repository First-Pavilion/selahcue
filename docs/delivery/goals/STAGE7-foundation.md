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

### Decision routed to the owner (Stage-7 gate)

The review confirmed a **HIGH** RBAC consequence: `Clear` maps to `Navigate`, so an
**Assistant can wipe the Live output + lift blackout** over the LAN path. This is the
policy the user kept in [DEC-002](../decisions/DECISION-LOG.md); the concrete consequence
is now surfaced for the user to revise (give `Clear` its own Producer+ permission) or
re-affirm the accepted risk. Not changed unilaterally.

### Iteration ledger — batch 7k

- Target: S7k-001..S7k-008. Change: created `selahcue-app` (`LiveController` + `handler_for`); added `Reply::Deny` to lan. Multi-lens adversarial review → 4 confirmed: staged-scripture-can't-go-live (×2) + scripture-resets-navigation → fixed (`GoLive` off presenter state; `plan_cursor`) + regression tests; Assistant-can-Clear-Live (HIGH RBAC) routed to owner per DEC-002. Verifier: `cargo test` 155 workspace + 2 E2E; clippy clean. Result: PASS. Decision: gate-review.

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
