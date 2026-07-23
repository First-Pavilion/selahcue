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
