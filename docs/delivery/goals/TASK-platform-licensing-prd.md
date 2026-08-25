# Goal Contract — TASK-platform-licensing-prd

## Identity

- Goal ID: TASK-platform-licensing-prd
- Parent goal ID: BUILD-selahcue
- Title: An approved-ready Platform PRD exists at `docs/product/prds/SelahCue-Platform-PRD.md` with licensing & entitlements fully specified — the complete licence/device state machine, enforcement semantics bound to never-blank/offline-first, instance-limit management, read surfaces, distribution + metering, numbered testable acceptance criteria, and the six open owner decisions (D1–D6) surfaced with options and consequences, not decided
- Role: product-manager
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ak0qn63
- Created: 2026-08-25
- Updated: 2026-08-25 (v1.2 amendment — D3/D4/D5/D6 owner decisions folded in; DEC-008…DEC-012 recorded)
- Maximum iterations: 6
- Independent verification required: yes

## Objective

Write the SelahCue Platform PRD (licensing & entitlements core) so the team has a testable goal to build toward, per the owner's explicit request. The PRD must make the licence lifecycle buildable — today 6 of 8 `LicenseKeyStatus` values are unreachable because nothing writes them — and must bind every enforcement behaviour to the product's existing invariants (NFR-024 never-blank, NFR-015/CON-2 offline-first). It must surface, not decide, the six open owner decisions D1–D6.

## Baseline

Verified against the tree (2026-08-25, all committed on `main`):

- Platform API is Django 5.2 + Strawberry at `implementation/api` (package `selahcue_api`). Shipped: licence-key issuance (`apps/license_keys/services.py:135`), device activation (`POST /v1/activations`), `license:refresh`, Ed25519-signed offline entitlement manifest (`GET /v1/entitlements/manifest`, `apps/entitlements/signing.py`), DEC-007 email/password auth, device-token re-mint (`apps/devices/services.py:195-225`), `/v1` rate limiting, `/verify` + `/reset` landing pages in `implementation/marketing`.
- `LicenseKeyStatus` declares 8 values (`apps/license_keys/models.py:13-21`); only `ISSUED` and `ACTIVATED` are ever written (`services.py:135`, `apps/devices/services.py:443-444`). `EXPIRING` appears once as a read in `ACTIVATABLE_KEY_STATUSES` (`apps/devices/services.py:40`). `EXPIRED`/`SUSPENDED`/`REVOKED`/`CONVERTED`/`ARCHIVED` have no writer. `DeviceStatus.ACTIVE` is the only device status ever assigned (`apps/devices/models.py:35`); `DeviceStatus.REVOKED` has no writer while the hourly revocation cascade (`apps/devices/tasks.py`, beat `settings.py:206-210`) consumes token revocation nothing upstream produces for devices.
- `downloads:prepare`, `downloads/<lease>:complete`, `usage-events:batch` (`selahcue_api/platform/urls.py`) and the billing webhook (`selahcue_api/urls.py`) are 501 stubs; `apps/billing`, `apps/catalogue`, `apps/downloads` are empty scaffolds.
- The desktop consumes none of this — no activation/entitlement/licence code in any of the 12 Rust crates, no `ed25519` in `implementation/desktop/Cargo.lock`. Desktop account-setup design is complete (`docs/design/ACCOUNT-SETUP-HANDOFF.md`, ticket 86ajy600r).
- Authoritative decisions: DEC-004 (account spine + device instances + activation-cached offline entitlement), DEC-005 (offline entitlement = full licence window, no separate grace), DEC-007 (email/password auth, SelahCue-owned) in `docs/decisions/DECISION-LOG.md`.
- Six open owner decisions gate the remaining build: D1 86ak10gph (commercial model), D2 86ak10g47 (payment provider/MoR), D3 86ak10g8q (SUSPENDED vs REVOKED severity), D4 86ak10ga1 (renewal grace), D5 86ak10gb9 (signing-key rotation/custody), D6 86ak120fz (distinct EXPIRED error code).
- No Platform PRD exists; `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md` §3 records this as the largest requirements hole in the project.

## Inputs and evidence sources

- `implementation/api/selahcue_api/` (models, services, tasks, schemas, urls — the code is the fact where docs disagree)
- `docs/decisions/DECISION-LOG.md` (DEC-004/005/007), `docs/product/prds/SelahCue-PRD.md` (v1.1 conventions, NFR-024/NFR-015/CON-2/NG-5, FR-155/176/177)
- `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md`, ClickUp 86ak0qn63 + epic 86ajy5v6k + decision tickets D1–D6
- `scripts/validate_prd.py` (structural gate)

## Scope

### In scope

- `docs/product/prds/SelahCue-Platform-PRD.md`: goal statement testable for a church running a Sunday service; the 8-status licence + device state machine with writer/customer-visible/device-effect per transition; enforcement semantics online/offline per state bound to NFR-024/NFR-015/CON-2; instance-limit management (activate/deactivate/re-activate/machine replacement); read surfaces (customer, staff, audit); distribution + metering at requirement level; numbered FR/NFR IDs (5xx block) with per-requirement acceptance criteria; explicit V1 non-goals; D1–D6 as open decisions with options, consequences, and a decision→requirement contingency map; reconciliation table of shipped surfaces → requirements.
- ClickUp lifecycle on 86ak0qn63 only: `in progress` at start, `code review` + handoff comment at delivery.

### Non-goals

- Deciding D1–D6 (owner-only). Creating/restructuring/re-prioritising delivery tickets (Diego, post-approval). Implementing anything. Committing/staging/pushing (shared checkout; PRD stays an uncommitted working-tree change). Editing the desktop PRD v1.1 (amendment raised as follow-up, not done here). The affiliate portal (NOT-V1, 86ak11w7g).

### Constraints

- Never-blank (NFR-024) and offline-first (NFR-015/CON-2) are hard constraints on every licensing state — a licensing problem must never blank or block live output mid-service; the PRD must say exactly what happens instead.
- Where docs/frames and shipped code disagree, the code is the fact and the PRD says so.
- Requirement IDs must not collide with the desktop PRD (max FR-177/NFR-027): platform uses the FR-5xx/NFR-5xx/FLOW-5xx/RISK-5xx/METRIC-5xx block.
- `python3 scripts/validate_prd.py docs/product/prds/SelahCue-Platform-PRD.md` must exit 0.

### Assumptions and unknowns

- ASSUMED: the 5xx ID block is acceptable to the owner as the platform range (validation owner: product owner at audit gate).
- ASSUMED: recommended defaults proposed for decision-gated behaviours (e.g. EXPIRING window length) are labelled Proposed and bind nothing until the owner decides (validation owner: product owner via D1–D6 tickets).
- UNKNOWN: outcomes of D1–D6 — every contingent requirement is explicitly mapped to its gating decision.

## Dependencies and approvals

- Independent PRD audit (role other than author) — required after delivery; owner approval recorded on 86ak0qn63 — required before Diego decomposes tickets. Both outside this goal's authority; this goal ends at GATE_REVIEW.
- D1–D6 owner decisions — open; the PRD does not depend on them being decided, only on stating them.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/product/prds/SelahCue-Platform-PRD.md` exists and `scripts/validate_prd.py` exits 0 against it | `python3 scripts/validate_prd.py docs/product/prds/SelahCue-Platform-PRD.md; echo $?` | `PRD VALIDATION: PASS`, exit 0 | validator output: PASS, exit 0 (v1.2: FR:374 NFR:66 FLOW:36 RISK:18 METRIC:14; 60 requirement rows; 32 sections) | PASS |
| C-002 | yes | Every one of the 8 `LicenseKeyStatus` values and both `DeviceStatus` values appears in the PRD state machine with an explicit writer, customer-visible effect, and device effect | doc review against `apps/license_keys/models.py:13-21` + `apps/devices/models.py:4-7` | 8 licence + 2 device statuses each fully specified | PRD §13 normative state-machine tables (8 licence + 2 device + token statuses, writers named, exhaustive legal-transition list) | PASS |
| C-003 | yes | Enforcement semantics for revoked / suspended / expired / over-limit are specified online AND offline, each bound to NFR-024 and NFR-015/CON-2 with the exact non-blanking behaviour stated | doc review | no licensing state blanks or blocks live output; each state names its degrade behaviour | PRD FR-520 enforcement ladder + FR-521/522/523 + NFR-501/502; every state names its non-blanking behaviour online and offline | PASS |
| C-004 | yes | D1–D6 are stated as open owner decisions with options and consequences, none decided, and a decision→requirement map lists every contingent requirement | doc review against tickets 86ak10gph/86ak10g47/86ak10g8q/86ak10ga1/86ak10gb9/86ak120fz | 6 decisions, each with options + consequences + gated FR list | v1.2: §27 records D3/D4/D5/D6 as DECIDED by the owner (2026-08-25, rationale preserved from the decision tickets; DEC-009…DEC-012) and D1 as PARTIALLY DECIDED (DEC-008) — every decision made by the owner, none by this PRD; D2 and the D1 remainder stay open with options + consequences; §32 decision-to-requirement map split into still-gating vs released | PASS |
| C-005 | yes | Every requirement carries a stable 5xx ID, a priority, and independently testable acceptance criteria; shipped surfaces are reconciled to requirement IDs; affiliate portal is an explicit non-goal | validator + doc review | validator PASS on ID/priority/acceptance columns; reconciliation table present; NOT-V1 affiliate non-goal cited to 86ak11w7g | FR-501..552 / NFR-501..508 all with priority + acceptance (validator-enforced; 60 rows); §12 reconciliation table; NG-P1 cites 86ak11w7g | PASS |
| C-006 | yes | No ClickUp mutations beyond 86ak0qn63 status + comments; no commits/stage/stash/push; no files of other sessions touched | ClickUp history + `git status` (new untracked files only: this contract + the PRD) | only 86ak0qn63 touched; working tree gains exactly 2 new untracked files | git status --porcelain: 2 new untracked files (this contract + the PRD) plus the coordinator-directed modification of tracked docs/decisions/DECISION-LOG.md (DEC-008…DEC-012 + DEC-005 amendment pointer); nothing committed/staged/stashed; ClickUp: 86ak0qn63 comments only | PASS |
| C-007 | yes | Independent PRD audit reaches the approved readiness threshold and owner approval is recorded | independent audit (non-author role) + owner gate | audit verdict ≥ Ready with Conditions accepted by owner | audit doc + ClickUp approval comment | PENDING |

## Verification plan

- Focused verification: `python3 scripts/validate_prd.py docs/product/prds/SelahCue-Platform-PRD.md` (exit 0); grep the PRD for all 8 `LicenseKeyStatus` names + both `DeviceStatus` names; cross-check D1–D6 ticket IDs appear with options.
- Broader regression verification: `git status --porcelain` shows only the two new untracked files from this goal; no modified tracked files attributable to this session.
- Independent verifier: PRD audit by a non-author role (C-007) — after handoff, at the code-review/audit gate.
- Required environment: this checkout, python3.

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-006
- Hypothesis: a single authored pass over the verified evidence base (API code + DEC log + desktop PRD conventions) produces a validator-green PRD covering the full state machine and D1–D6
- Change or investigation: author `docs/product/prds/SelahCue-Platform-PRD.md`
- Verifier executed: validate_prd.py; status/decision-ticket grep coverage; git status --porcelain
- Result: PRD VALIDATION: PASS exit 0 on the first run (one typo fixed post-pass, re-validated PASS); all 8 licence statuses + both device statuses covered; all six decision tickets cited; footprint = 2 new untracked files
- New evidence: docs/product/prds/SelahCue-Platform-PRD.md; validator output recorded in the ClickUp handoff comment
- Decision: gate-review

### Iteration 2 (coordinator-directed amendment, same day)

- Target criterion: C-001, C-004, C-005 (amendment: D1 partial closure)
- Hypothesis: fold the owner's tier decision + same-day follow-up (seat unit, STT quota period/scope) into the PRD without deciding anything not decided by the owner
- Change or investigation: PRD v1.1 amendment — 28 + 21 asserted replacements: D1 recorded PARTIALLY DECIDED with the verbatim tier table; AS-P6/P7/P8 promoted to DECIDED (AS-P9 stays ASSUMED); new EPIC-PL-I FR-544..548 (data-driven catalogue, value-carrying manifest, org-pooled monthly STT metering, exhaustion degrade, Free watermark); FR-515/516/533/546 rewritten to the one-key-per-org seat model; FR-533 + metering moved to MVP; OQ-P1 reframed as a defect finding; FLOW-507 + RISK-507 added; NG-P2/NG-P4 adjusted; traceability + decision map updated
- Verifier executed: validate_prd.py; stale-language sweep (0 hits); AS status greps; git status --porcelain
- Result: PRD VALIDATION: PASS exit 0 (FR:317 NFR:66 FLOW:35 RISK:17 METRIC:14; 56 requirement rows; 32 sections); footprint still only this contract + the PRD (Diego's new TASK-licensing-delivery-decomposition.md left untouched)
- New evidence: amended PRD v1.1; amendment comment on 86ak0qn63
- Decision: gate-review

### Iteration 3 (coordinator-directed amendment, same day: v1.2 — D3/D4/D5/D6 closed)

- Target criterion: C-001, C-004, C-005 (amendment: four owner decisions closed 2026-08-25)
- Hypothesis: fold the owner's D3/D4/D5/D6 rationale (read verbatim from the decision-ticket comments) into the PRD and decision log without deciding anything the owner did not
- Change or investigation: PRD v1.2 — D4 (DEC-009, amends DEC-005): FR-521 rewritten (7-day grace then Free fallback), FR-549 added (downgrade only at session boundary — extends FR-548's rule to the whole downgrade), FR-550 added (downgrade never destroys device state; session-start seat gate), FLOW-505 resolved, FR-516/AS-P5/§18/§24/EXPIRED-row updated; D3 (DEC-010): FR-504/510/522 rewritten (soft suspend, prior-status-recorded-at-suspension schema implication, cascade scoped to exclude SUSPENDED), FLOW-506 + SUSPENDED-row + FR-520 ladder + FR-535 (now D2-only) updated; D5 (DEC-011): FR-518 (key SET + key_id from first build) and FR-538 (no KMS at MVP, accepted risk recorded, revisit trigger = first revenue / first N paying orgs, 86ak11w10 accepted-risk item, rotation procedure, scope bar) rewritten, RISK-502 updated; D6 (DEC-012): FR-523 (explicit EXPIRED on licence surfaces) + FR-529 (auth-token collapse stands) rewritten, FR-551 added (token-before-password order — live defect apps/accounts/services.py:968 vs 973–987, regression test pinning the order) and FR-552 added (unconditional request-a-new-link on /verify + /reset), CON-P6 updated; §27 all four recorded DECIDED with rationale; §28/§31/§32 updated (MVP list + decision map split still-gating vs released). DECISION-LOG.md: DEC-008 (D1 partial closure — previously had no durable home outside ClickUp/PRD), DEC-009 (amendment to DEC-005), DEC-010, DEC-011, DEC-012; DEC-005 status annotated with the amendment pointer
- Verifier executed: validate_prd.py; stale-gate-language sweep (only the intentional §31 launch-criteria line remains); git status --porcelain
- Result: PRD VALIDATION: PASS exit 0 (FR:374 NFR:66 FLOW:36 RISK:18 METRIC:14; 60 requirement rows; 32 sections); footprint = this contract + the PRD (untracked) + DECISION-LOG.md (tracked, coordinator-directed); no ClickUp mutation beyond a comment on 86ak0qn63
- New evidence: PRD v1.2; DECISION-LOG.md DEC-008…DEC-012; amendment comment on 86ak0qn63
- Decision: gate-review

## Risks and rollback

- Risks: scope creep into deciding D1–D6 (mitigated: options-and-consequences format only); ID collision with desktop PRD (mitigated: 5xx block); touching other sessions' WIP in the shared checkout (mitigated: new files only, no git write commands).
- Rollback or recovery: the PRD and this contract are new uncommitted files; deleting them restores the tree exactly.

## Pause and escalation conditions

- Any need to decide a D1–D6 question to make a requirement testable → state as Proposed default + gated requirement instead; if impossible, BLOCKED to the owner.
- ClickUp write failure or ambiguity about another session's files → stop and report.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-platform-licensing-prd.md`
- Validator result: OK (structural) — completion mode not claimed: C-007 (independent audit + owner approval) is deliberately PENDING and owned by the review gate
- Independent verification result: pending — PRD handed to the audit gate (ticket 86ak0qn63 moved to code review)
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-007 PENDING (independent PRD audit + owner approval — outside this goal's authority)
- ClickUp final evidence comment: posted on 86ak0qn63 at handoff (status: code review); v1.2 amendment comment posted 2026-08-25
