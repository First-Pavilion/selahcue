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
