# SelahCue — Build State

Lightweight pointer only. ClickUp is the delivery source of truth. Do not duplicate the backlog here.

- Product: **SelahCue** (cross-platform church presentation & ministry-assistance app)
- Build Control task: https://app.clickup.com/t/86ajnx548 (`86ajnx548`)
- ClickUp delivery list: `SelahCue — Delivery` (`901327960792`) in folder `SelahCue` (`901318653689`), space `First Pavilion (Engineering)` (`90136583508`)
- Build Goal Contract: `docs/delivery/goals/BUILD-selahcue.md`
- Current stage: **Stage 7 — Implementation foundation** (batches 7a + 7b + 7c + 7d + 7e done, at gate)
- Stage state: `GATE_REVIEW` (awaiting user gate decision — this gate authorises production implementation)
- Last approved gate: Gate 6 (Stage 6) — user replied `continue`, authorising Stage 7 (production implementation)
- Execution engine: `goal`
- Execution model: **Opus 4.8 (1M context)** — Stage 2+ runs under the current session model.

## Stage 2 outcome (2026-07-23)

Discovery complete. 6 parallel research specialists + a 4-lens independent review workflow (PASS WITH CONDITIONS, 0 blockers) + a follow-up adjacent-product study (condition C1). Integrity conditions resolved; architecture conditions formally deferred with recorded recommendations. Artefacts in docs/research/, docs/business/, docs/security/reviews/. Awaiting Stage 2 gate decision.

Key Stage 2 artefacts: DISCOVERY-REPORT.md, EVIDENCE-REGISTER.md, OPEN-DECISIONS.md, DISCOVERY-REVIEW.md, CONDITION-DISPOSITIONS.md (all under docs/research/); Stage 2 contract docs/delivery/goals/STAGE2-discovery.md.

**Refine (2026-07-23):** user de-scoped **TTS** entirely — removed from roadmap ([DEC-001](../decisions/DECISION-LOG.md)). Discovery artefacts, OPEN-DECISIONS OD-02, risk register RISK-008, and Build Goal Contract non-goals updated.

## Stage 3 outcome (2026-07-23)

PRD authored: `docs/product/prds/SelahCue-PRD.md` — 168 FR + 26 NFR + 10 FLOW + 13 RISK + 10 METRIC, all sections, testable acceptance criteria, MVP/R2-R6/non-goal boundary, full traceability. PM artifact validator `scripts/validate_prd.py` built (closes RISK-006) and passes. Independent 4-lens pre-audit review (`docs/product/audits/PRD-REVIEW-stage3.md`): PASS WITH CONDITIONS, 0 blockers; all 10 majors + 12 minors discharged (PRD §34).

## Stage 4 outcome (2026-07-23)

Formal 5-auditor independent PRD audit (`docs/product/audits/PRD-AUDIT-stage4.md`): PASS WITH CONDITIONS, **0 blockers**, 17 majors, 16 minors. All 17 majors discharged (PRD §35, adding FR-169…FR-177, NFR-026/027, RISK-014, AS-6) + material minors. Fresh-context re-audit (`docs/product/audits/PRD-AUDIT-stage4-reaudit.md`): **verdict PASS**, 17/17 discharged, 0 regressions; 5 advisory doc-hygiene minors also folded in. PRD now 177 FR + 27 NFR; validator passes. **PRD has cleared its mandatory independent audit.** Stakeholder report added: `docs/stakeholder/SelahCue-Build-Report.pdf`.

## Stage 5 outcome (2026-07-23)

Architecture spine (`docs/architecture/ARCHITECTURE.md`) + **16 ADRs** (`docs/architecture/adr/`) + UX (`docs/design/`: UX-FLOWS 12 flows, UX-STATE-MATRIX, COMPONENT-SPECS, UX-CANONICAL). Independent 5-lens review: **FAIL** (2 blockers, 12 majors) → remediated (added ADR-0015 testable engine, ADR-0016 decode sandbox, UX-CANONICAL) → re-review **PASS WITH CONDITIONS** (both blockers cleared, 12/14 majors) → remaining M2/M11/NM-1/NM-3 closed. **Figma designs** added to file `SYQn5hFY8YVQKm3c6rw0eJ` (user refine, expanded to full app): **19 frames** — Operator Console, Mobile Controller, Stage/Confidence output, TIME UP output, Design Tokens, Scripture (search & present), Presentation/Slide Editor, Theme/Template Designer, Song/Lyrics Editor, Media & Library, Service Plan builder, Settings (AI & providers), Add Bible (translation import), Displays & Outputs, Devices & Roles (pairing + RBAC), Pre-service Checks, Transcription/STT, Scripture Detection queue, Sermon Notes. **Refine (user):** Operator Console unified into one work screen — added Plan/Scripture tabs + a bottom work dock (live transcript/STT + scripture search & auto-detect approval); scripture search & display added to the Mobile Controller. PRD validator passes. Awaiting Stage 5 gate. Next: **Stage 6 — ClickUp delivery planning** (gate to begin implementation).

## Key artefacts

- Baseline audit: `docs/product/audits/BASELINE.md`
- Research plan: `docs/research/RESEARCH-PLAN.md`
- Risk register: `docs/delivery/RISK-REGISTER.md`
- Goal Contract validator: `scripts/validate_goal_contract.py`
- Stage 1 Goal Contract: `docs/delivery/goals/STAGE1-bootstrap.md`

## Recovery note

Greenfield build; not yet under git version control (RISK-011). To resume, read the Build Control task and this file, validate the BUILD + active STAGE contracts, then resume at the last unapproved gate (currently the Stage 1 gate).

## Stage 6 outcome (2026-07-23)

ClickUp delivery plan created in list SelahCue — Delivery (901327960792): **16 epics** (11 MVP + 5 later-release) + **14 foundation vertical-slice stories** + **3 milestones**. Requirement traceability (`docs/delivery/REQUIREMENTS-TRACEABILITY.md`): all 204 FR+NFR mapped. `docs/delivery/IMPLEMENTATION-READINESS.md`: **READY** with a 37-edge acyclic dependency graph + critical path. New validator `scripts/validate_delivery_plan.py` (coverage + acyclicity + READY) passes. Independent review (`DELIVERY-PLAN-REVIEW.md`): PASS WITH CONDITIONS, 0 blockers; medium/low traceability nits fixed. Awaiting Stage 6 gate — **this gate authorises Stage 7 (production implementation)**.

## Stage 7 outcome — batch 7a (2026-07-23)

First production code: `implementation/crates/selahcue-core` (scripture parser FR-027, service-plan model FR-001/002, monotonic timer FR-054/065). **Verified: cargo test 37/37, clippy clean.** Independent review PASS WITH CONDITIONS → all findings fixed. Stories 86ajp0afa/86ajp0a4z/86ajp0ac9 in progress. Git e794a7e. Next batches: walking skeleton (wgpu+Tauri, needs display), persistence (SQLite/SQLCipher), CI/GPU matrix, presentation/outputs/mobile → foundation demo.

## Stage 7 outcome — batch 7b (2026-07-23)

Persistence layer: `implementation/desktop/crates/selahcue-data` — WAL SQLite (rusqlite bundled), versioned append-only migrations + forward-compat guard, integrity checks, crash-safe online backup (FR-079), transactional `ServicePlan` repository. **Verified: cargo test 50/50, clippy clean.** Independent review (`implementation/desktop/CODE-REVIEW-batch7b.md`) PASS WITH CONDITIONS (0 high, 1 med, 3 low) → M1/L1/L2 fixed with regression tests. **Repo restructured** by platform: `implementation/{desktop,web,mobile}/` (user refine — separation of concerns). Git 4e6612a.

## Stage 7 outcome — batch 7c (2026-07-23)

At-rest encryption (FR-154): `selahcue-data` `encryption` feature (SQLCipher + vendored OpenSSL, self-contained); `EncryptionKey` (256-bit raw key, zeroize), `open_encrypted`/`open_in_memory_encrypted`, and crash-safe `backup_to_encrypted`. Keyed-open API is feature-gated so a keyless "encrypted" open is impossible. **Verified: cargo test 50 default + 16 data-encryption, clippy clean both; no plaintext on disk (header + WAL encrypted).** Independent **multi-lens adversarial review** (workflow, 4 lenses find→verify): 8 raised → **2 confirmed** (H1 encrypted-backup-broken, L1 key-lingers) → fixed + regression-tested; 6 dismissed (`CODE-REVIEW-batch7c-encryption.md`). **Tests reorganised** into per-crate `tests/` folders (user refine; one white-box scripture test stays inline). Story 86ajp09he → **QA** (data-layer scope); OS secret-store key acquisition (app-shell, ADR-0007) deferred to follow-up story 86ajp5vp6. Batch-7a stories (scripture/plan/timer) → QA. Next batches: walking skeleton (wgpu+Tauri, needs display), CI/GPU matrix, presentation/outputs/mobile → foundation demo.

## Stage 7 outcome — batch 7d (2026-07-23)

LAN control core: new crate `implementation/desktop/crates/selahcue-lan` (FR-118/119/120; ADR-0009) — wire **protocol** (versioned JSON, stable tags, `version_supported`), **RBAC** (Operator>Producer>Assistant>Viewer, single `authorize()` choke point, strict-superset roles), **session/pairing** (single-use TTL codes → opaque bearer tokens; constant-time auth via `subtle`; redacted-Debug tokens; no cross-device confusion). Pure + injected token/clock. **Verified: cargo test 80/80 workspace (30 in lan), clippy clean.** Independent **multi-lens adversarial review** (workflow): 10 raised → **1 confirmed** (M1 AuthRequest Debug leaked token) → fixed + regression test; 9 dismissed; empty-token/code guards + cross-device/boundary tests added (`CODE-REVIEW-batch7d-lan.md`). Story 86ajp0b0t → **in progress** (RBAC+pairing core done; TLS transport = batch 7e, QR+mobile client pending). **Design question resolved:** Assistant keeps `Clear`/`Navigate` on the live output ([DEC-002](../decisions/DECISION-LOG.md), user "keep as is"). Next batch: **7e — TLS-pinned WebSocket transport**.

## Stage 7 outcome — batch 7e (2026-07-23)

TLS-pinned WebSocket transport: `selahcue-lan` `server` feature (pure-Rust rustls + ring — no OpenSSL/C). `pinning` (custom rustls verifier: trusts the operator's self-signed cert by SHA-256 pin while still verifying the handshake signature), `tls` (rcgen self-signed + server/client configs), `server`/`client`/`wire`. **E2E over real loopback TLS:** pinned + authenticated + RBAC-enforced command flow; wrong pin rejected; wrong token rejected; half-open (slowloris) connections reaped; connection/registry bounded. **Verified: cargo test 84 default + 39 server-feature, clippy clean both.** Independent **multi-lens adversarial review**: TLS-security lens **clean (no bypass)**; 8 raised → **4 confirmed** — all pre-auth DoS/resource (accept-loop-dies-on-error, no handshake-timeout/connection-cap ×2, 64 MiB frame) → **fixed** with handshake timeout + `Semaphore` cap + resilient accept + 64 KiB frame cap + slowloris-reaping regression test (`CODE-REVIEW-batch7e-transport.md`). **No-leak requirement** ([memory note] the user added): bounded `SessionRegistry` tests + connection-reaping test. Story 86ajp0b0t stays **in progress** (transport done; QR pairing + Flutter mobile client pending). Next batch: walking skeleton (wgpu+Tauri, needs display) or QR/mobile client. Then CI/GPU matrix, presentation/outputs → foundation demo.
