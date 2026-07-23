# Goal Contract — BUILD-selahcue

## Identity

- Goal ID: BUILD-selahcue
- Parent goal ID: NONE
- Title: Deliver a production-ready, cross-platform SelahCue church presentation & ministry-assistance application satisfying the approved requirements in product/PRODUCT-BRIEF.md
- Role: build
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajnx548
- Created: 2026-07-23
- Updated: 2026-07-23
- Maximum iterations: 13
- Independent verification required: yes

## Objective

Deliver, through the stage-gated `/build` workflow, a production-ready cross-platform (Windows, macOS, Linux desktop; Android, iOS/iPadOS mobile controller) church presentation, scripture, multi-output, timer, lower-third, live-transcription, automatic-scripture-detection, AI-sermon-notes, text-to-speech, and mobile-control application named **SelahCue**, whose released scope maps to approved requirements in `product/PRODUCT-BRIEF.md`, with every mandatory completion criterion evidenced and independently verified.

## Baseline

Verified 2026-07-23:

- Working directory `/Users/m.oluwole/Documents/code/scph` is **not** a git repository. No source code, tests, build tooling, CI, or infrastructure exist.
- Only content present: `product/PRODUCT-BRIEF.md` (research/PRD/decomposition brief) and `.claude/` (team process docs + specialist skills + build skill).
- The referenced `scripts/validate_goal_contract.py` did not exist and has been created this stage; a "PM artifact validator" is referenced by the brief/skill but does not yet exist (tracked RISK-006).
- ClickUp MCP is accessible. Workspace `First Pavilion (Engineering)` (space 90136583508). Existing empty folder `SelahCue` (901318653689); new delivery list `SelahCue — Delivery` (901327960792) created this stage.
- No prior SelahCue tasks, PRD, architecture, designs, or ClickUp work exist. This is a greenfield build.

## Inputs and evidence sources

- product/PRODUCT-BRIEF.md (authoritative product brief)
- .claude/team/*.md (GOAL_EXECUTION_PROTOCOL, BUILD_STAGE_COMPLETION, BUILD_GATES, CLICKUP_WORKFLOW, CLICKUP_TASK_SCHEMA, QUALITY_GATES, ROLE_MATRIX, ARTIFACTS, GOAL_CONTRACT_TEMPLATE, WORKFLOW)
- .claude/skills/* (specialist skills)
- ClickUp workspace First Pavilion (Engineering); Build Control task 86ajnx548
- docs/research/, docs/product/, docs/architecture/, docs/security/, docs/quality/, docs/design/ (to be produced by later stages)

## Scope

### In scope

- Full product discovery, research, PRD, independent PRD audit, architecture, UX design, ClickUp delivery plan, implementation of approved MVP + later-release scope, testing, security review, documentation, and release-readiness verification for SelahCue across the approved platforms.
- Desktop apps, mobile controllers, rendering, media playback, multiple independent outputs, stage/confidence displays, scripture system, local-network communication, transcription, scripture detection, sermon-note generation, TTS, offline operation, persistence, crash recovery, security, privacy, packaging, observability, and update strategy.

### Non-goals

- Production deployment (requires separate explicit user instruction; Stage 13 stops at the release gate).
- Voice cloning (excluded unless separately approved with consent + safeguards).
- Bundling copyrighted Bible translations, song lyrics, fonts, codecs, voices, or AI models without verified permission.
- Copying proprietary product code, interfaces pixel-for-pixel, branding, or protected assets (PewBeam, ProPresenter, etc.).

### Constraints

- Stage-gated: complete one stage per user approval; `continue` authorises only the next stage.
- ClickUp is the delivery source of truth; repository Markdown holds durable technical/product artefacts only.
- Reliability-first: AI/transcription/scripture-detection/TTS failures must never block core live presentation; desktop stays authoritative on mobile connectivity loss; core live functions work offline.
- Every specialist assignment runs a Goal Contract via the `goal` engine (or Ralph); no self-approval of high-risk claims.

### Assumptions and unknowns

- ASSUMED: Product name is "SelahCue" (confirmed by user 2026-07-23). Owner: user.
- ASSUMED: Target platform scope is the full brief list (Win/macOS/Linux desktop + Android/iOS/iPadOS mobile). To be confirmed/bounded in Stage 2–3. Owner: Product Manager + user.
- UNKNOWN: Final technology stack — brief lists Rust/Tauri/wgpu/GStreamer/SQLite/local AI as candidates but forbids choosing on brief assumption alone; decided by Stage 5 trade-off analysis + ADRs. Owner: Software Architect.
- UNKNOWN: Which Bible translations are licensable/bundlable; transcription/TTS/AI provider choices and costs. Owner: Product Researcher + Security Reviewer + user.

## Dependencies and approvals

- User gate approval required at each of the 13 stages. Owner: user. Status: Stage 1 pending.
- ClickUp MCP availability. Owner: platform. Status: available.
- User-supplied AI/transcription/TTS provider credentials and licensing decisions. Owner: user. Status: pending (Stage 2–3).
- Production release approval. Owner: user. Status: not requested.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`. Rows aggregate the 68 global completion predicates in the brief (predicate numbers cited in Criterion).

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Repository, MCP tools, docs, code, tests, infra, and ClickUp inspected (pred 1) | Review of baseline audit | Baseline documented with verified facts | docs/product/audits/BASELINE.md | PENDING |
| C-002 | yes | Required product/user/workflow/competitor/market/feasibility/licensing/privacy/security/reliability/accessibility/offline/performance research complete and classified OBSERVED/DOCUMENTED/INFERRED/UNKNOWN (pred 2-4) | Stage 2 discovery review | Research evidence register complete; independent review passes | docs/research/ | PENDING |
| C-003 | yes | Complete PRD with stable requirement IDs and measurable/testable acceptance criteria; MVP/later/non-goals/risks/assumptions/constraints/deferrals separated (pred 5-7) | PM artifact validator | Validator exits 0 | docs/product/prds/, scripts PM validator | PENDING |
| C-004 | yes | Fresh-context independent PRD audit returns exactly PASS; blockers/major findings resolved and re-audited (pred 8-9) | Stage 4 audit agent | Verdict == PASS | docs/product/audits/ | PENDING |
| C-005 | yes | Approved architecture covers all 21 listed domains; ADRs recorded; tech choices backed by trade-off analysis (pred 10-12) | Architecture review | Coverage matrix complete; ADRs present | docs/architecture/, docs/architecture/adr/ | PENDING |
| C-006 | yes | UX flows and all interface/failure/loading/empty/permission/accessibility/recovery states defined; designs+architecture independently reviewed pre-implementation (pred 13-14) | UX + independent design review | Reviews pass | docs/design/ | PENDING |
| C-007 | yes | ClickUp is source of truth (Build Control, epics, stories, tasks, spikes, bugs, deps, ownership, priority, status, release) and every requirement maps to a ticket or justified deferral (pred 15-16) | Traceability check | 100% requirement coverage | ClickUp; docs/product/prds traceability | PENDING |
| C-008 | yes | Every ticket has all 20 required schema fields (pred 17) | Ticket schema audit | All tickets conform | ClickUp tickets | PENDING |
| C-009 | yes | Dependency graph has no cycles/orphans/unresolved blockers; plan is coherent vertical slices; first release bounded; IMPLEMENTATION-READINESS.md == READY; PM validator succeeds (pred 18-22) | Graph validation + validator | No cycles; report READY; validator exits 0 | docs/product/IMPLEMENTATION-READINESS.md | PENDING |
| C-010 | yes | Every approved implementation ticket completed or deferred via approved scope change (pred 23) | ClickUp status audit | All tickets Done or approved-deferred | ClickUp | PENDING |
| C-011 | yes | Production code follows repo architecture/conventions/quality/security; reuses existing components; no unnecessary duplication (pred 24-26) | Fresh-context code review | Review passes | docs/quality/release-evidence/ | PENDING |
| C-012 | yes | DB queries reviewed for N+1/indexes/unnecessary/unbounded reads/concurrency/transactions; background work bounded/cancellable/retried/timed-out/idempotent (pred 27-28) | Code review + tests | No unmitigated findings | code review report | PENDING |
| C-013 | yes | AI/transcription/scripture-detection/TTS failures cannot block core presentation controls; desktop authoritative on mobile loss; core live functions work without cloud; destructive ops have safeguards+rollback (pred 29-32) | Reliability/fault-injection tests | All scenarios pass | docs/quality/release-evidence/ | PENDING |
| C-014 | yes | No specialist marked own implementation complete without independent verification (pred 33) | Process audit | Independent verification present for each | Goal Contracts + ClickUp | PENDING |
| C-015 | yes | Unit/integration/API-protocol/UI/E2E tests cover logic/boundaries/contracts/interaction/journeys incl. happy/edge/permission/malformed/recovery/provider-failure; regression tests per fixed defect (pred 34-40) | Test suite | All pass; coverage adequate | CI logs, docs/quality/test-plans/ | PENDING |
| C-016 | yes | Cross-platform verified for approved scope; soak tests show bounded memory/resources; performance tests meet approved latency/resource targets (pred 41-43) | Cross-platform + soak + perf tests | Targets met | docs/quality/release-evidence/ | PENDING |
| C-017 | yes | Crash-recovery/autosave/missing-media/display-disconnect/audio-disconnect/network-loss/provider-failure/forced-shutdown scenarios tested; full suite passes; flaky tests fixed not ignored; no test disabled to pass (pred 44-47) | Test suite + review | All pass; no disabled tests | CI logs | PENDING |
| C-018 | yes | Independent security review complete; auth/authz/pairing/local-net/roles/revocation/command-validation/replay/rate-limit/secret-storage verified; import/path-traversal/media/deps/local-model/update/backup reviewed (pred 48-50) | Fresh-context security review | Review passes | docs/security/reviews/ | PENDING |
| C-019 | yes | Transcript/audio/sermon-note/AI/TTS privacy controls match requirements; cloud transmission opt-in + disclosed; user provider credentials stored securely (pred 51-53) | Security + privacy review | Controls verified | docs/security/reviews/ | PENDING |
| C-020 | yes | No unresolved critical/high security finding; medium findings resolved or explicitly accepted with justification (pred 54-55) | Security verification | Zero open critical/high | docs/security/reviews/ | PENDING |
| C-021 | yes | User/operator/admin/developer/API/architecture docs, deployment instructions, troubleshooting, recovery runbooks, release notes, known limitations complete; packaging validated for approved platforms; migration+rollback tested; monitoring/logs/diagnostics/backup/recovery documented+verified (pred 56-60) | Documentation review | Complete + accurate | docs/ , docs/operations/runbooks/, docs/release/ | PENDING |
| C-022 | yes | Fresh-context code review, QA verification, security verification, and release-readiness audit all pass (pred 61-64) | Stage 13 fresh-context agents | All pass | docs/quality/release-evidence/, docs/security/reviews/ | PENDING |
| C-023 | yes | Every mandatory Goal Contract criterion has evidence; Goal Contract validator succeeds; final implementation-readiness report states READY FOR RELEASE; user reviewed final release gate (pred 65-68) | Validator + user review | Validator exits 0; report READY FOR RELEASE; user confirms | scripts/validate_goal_contract.py; docs/release/ | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: each stage runs its own Stage Goal Contract with stage-specific Boolean predicates from `.claude/team/BUILD_STAGE_COMPLETION.md`, verified before its gate.
- Broader regression verification: full automated test suite + soak + performance + recovery tests before Stage 12/13 gates.
- Independent verifier: fresh-context agents that did not author the work perform PRD audit (Stage 4), design/architecture review (Stage 5), and final code/QA/security/release-readiness verification (Stage 13). No self-approval of high-risk claims.
- Required environment: approved target platforms for cross-platform/soak/perf tests; local-network test harness for mobile pairing.

## Iteration ledger

### Iteration 1 (Stage 1 — Bootstrap and verified baseline)

- Target criterion: C-001 (baseline) + Stage 1 completion condition (baseline documented, Build Control task exists, Build Goal Contract validates, research plan complete, blockers identified).
- Hypothesis: Inspecting the repo/MCP/ClickUp and producing baseline + contract + research plan + risk register satisfies the Stage 1 gate.
- Change or investigation: Inspected repo (greenfield), read team process docs, verified ClickUp MCP, confirmed product name + delivery-list location with user, created delivery list + Build Control task, authored this contract, baseline audit, research plan, risk register, BUILD_STATE pointer, and the missing goal-contract validator.
- Verifier executed: `python3 scripts/validate_goal_contract.py docs/delivery/goals/BUILD-selahcue.md` (structural).
- Result: pending run at end of Stage 1.
- New evidence: docs/product/audits/BASELINE.md, docs/research/RESEARCH-PLAN.md, docs/delivery/RISK-REGISTER.md, docs/delivery/BUILD_STATE.md, ClickUp task 86ajnx548, list 901327960792.
- Decision: gate-review (present Stage 1 gate; await user).

## Risks and rollback

- Risks: see docs/delivery/RISK-REGISTER.md (RISK-001..RISK-010). Top: platform/scope breadth vs. one release, licensing of translations/voices/models, realistic AI/scripture-detection accuracy, offline transcription feasibility, missing validators/tooling.
- Rollback or recovery: greenfield — no production state to roll back. Each stage's artefacts are additive and version-controlled once git is initialised (proposed Stage 1 follow-up). Scope changes route through the scope-change policy and the current stage gate.

## Pause and escalation conditions

- Pause: user issues `pause` at any gate; state persists in ClickUp Build Control + docs/delivery/BUILD_STATE.md.
- Escalation: any material scope/feasibility/architecture/cost/licensing/privacy/security/schedule problem sets the affected child goal to BLOCKED, updates ClickUp, and requests a user decision at the current gate.
- Abort: user issues `abort`; work preserved, recovery guidance recorded; no deletion.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/BUILD-selahcue.md --require-complete`
- Validator result: PENDING (structural PASS expected now; completion check only at Stage 13)
- Independent verification result: PENDING (Stage 13)
- Terminal state: IN_PROGRESS (Stage 1 → GATE_REVIEW)
- Remaining failed or blocked criteria: all PENDING (build not started)
- ClickUp final evidence comment: PENDING
