# Goal Contract — TASK-86ajp0bpn-foundation-demo-rescore

## Identity

- Goal ID: TASK-86ajp0bpn-foundation-demo-rescore
- Parent goal ID: STAGE7-foundation
- Title: The MVP Foundation demo is re-scored against current evidence (post-7aq), with an audited v2 verdict table, an honest remaining-gap list, and a Stage-7 closure recommendation
- Role: qa-engineer
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajp0bpn
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

The milestone's last full review (batch 7t, updated through 7y) scored 2 PASS · 5 PASS(scoped) · 2 PARTIAL and kept the milestone open with an 8-item gap list. Batches 7u–7aq have since closed most of it. Re-score all 9 demo steps against current repository/CI/doc evidence — independently audited, not self-scored — and recommend the honest Stage-7 disposition.

## Baseline

Verified as of 2026-07-25:
- `docs/delivery/FOUNDATION-DEMO-REVIEW.md` (7t-era): step 1 PARTIAL (GUI launch unexercised on runners), step 8 PARTIAL-strong (camera QR pending), 5 scoped passes; gap list items 1–8; 5 ClickUp closure deltas.
- Since then: 7u recovery live-verified · 7v plan authoring+library · 7w design system/keybindings · 7x console · 7y verse text E2E · 7aa displays+identify · 7ab chapter browser+KJV · 7ac timers · 7ad highlighting+guard · 7ae 5 PD translations · 7af double-click verse · 7ag shorthand · 7ah SBOM+device-loss · 7ai SQLCipher keys · 7aj mDNS+SAS · 7ak/7al mobile revamp+verse list+GetChapter · 7am emergency closeout · 7an launch smoke+per-OS NFR (Linux/macOS green; Windows launch recorded once, then documented runner limitation) · 7ao MulticastLock · 7ap console design · 7aq licensing spike. Tests: 269 Rust + 39 Flutter; CI green (run 30143889962-era).

## Inputs and evidence sources

- FOUNDATION-DEMO-REVIEW.md, STAGE7-foundation.md (all predicate blocks), BUILD_STATE.md, CODE-REVIEW-batch7*.md, ci.yml + recent run IDs, the repo's tests, ClickUp stories.

## Scope

### In scope

- An independent per-step evidence audit (9 demo steps) via a Workflow fan-out (auditors read code/tests/CI/docs; they do NOT take the old verdicts on faith).
- FOUNDATION-DEMO-REVIEW.md v2: updated verdict table + the remaining honest gaps + the ClickUp-delta reconciliation status.
- Milestone ticket update + a Stage-7 disposition recommendation at the gate (the disposition itself is the owner's).

### Non-goals

- Running new on-device/multi-monitor demos (owner hardware; recorded as owner-QA gaps, not blockers manufactured into passes).
- Closing the milestone (owner's gate decision).

### Constraints

- Audited wording discipline: every verdict cites evidence; downgrades allowed; no verdict upgraded without concrete new evidence.
- Owner-pending visual confirmations stay explicitly pending.

### Assumptions and unknowns

- ASSUMED: repo/docs/CI evidence is sufficient to re-score without new live walks (the 7t review's live-walk evidence remains valid where the code paths are unchanged and regression-tested). VALIDATION OWNER: the auditors.

## Dependencies and approvals

- Stage-7 closure is the owner's gate decision.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All 9 demo steps re-audited independently against current evidence (auditors cite file/test/CI/doc evidence per verdict; no unevidenced upgrades) | Workflow audit fan-out | 9 audited verdicts with citations | run `wf_4e58027d-bb3` (9 auditors, 323 tool calls, test suites re-run + live CI logs) | PASS |
| C-002 | yes | FOUNDATION-DEMO-REVIEW.md v2: updated verdict table, score line, remaining honest gaps, ClickUp-delta reconciliation status | doc review | v2 section complete + honest | FOUNDATION-DEMO-REVIEW.md V2 (2·7·0·0 score, gap classes, disposition) | PASS |
| C-003 | yes | The milestone ticket reflects the re-score with the gap list and the recommended disposition; owner-QA items enumerated | ClickUp comment | posted + status honest | 86ajp0bpn comment + hardening follow-up 86ajpzbxf | PASS |
| C-004 | yes | A clear Stage-7 disposition recommendation at the gate (close / conditionally close / keep open), grounded in the audited score | gate report | recommendation + rationale | "conditionally met — owner QA then close" in the V2 disposition + gate | PASS |
| C-005 | yes | Independent verification: the v2 verdicts spot-checked (auditors are fresh-context; synthesis cross-checked against their citations) | audit outputs vs v2 diff | no synthesis claim exceeds its audit evidence | v2 table built solely from auditor citations incl. their corrections (library wording, step-9 label refinement); CODE-REVIEW-batch7ar.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: per-step auditor citations checked against the repo.
- Broader regression verification: the v2 score line arithmetic matches the table; no old gap silently dropped without evidence of closure.
- Independent verifier: the fresh-context auditors themselves + a synthesis cross-check.
- Required environment: repo + CI history (gh) + docs.

## Iteration ledger

### Iteration 1

- Target criterion: C-001
- Hypothesis: 9 fresh-context auditors, each given one demo step + pointers, produce evidence-cited verdicts that upgrade most scoped/partial steps and surface any regressions.
- Change or investigation: Workflow fan-out; then synthesis.
- Verifier executed: Workflow `wf_4e58027d-bb3` — 9 fresh-context auditors, 323 tool calls; they re-ran the cited test suites (test_controller 36/36, test_plan_repo 11/11, wire E2Es) and pulled live CI runner logs (SMOKE OK lines, gated NFR figures, the verbatim Windows 522ms launch).
- Result: **V2 score 2 PASS · 7 PASS(scoped) · 0 PARTIAL · 0 FAIL** (7t: 2·5·2·0). Upgrades: step 1 PARTIAL→PASS_SCOPED (launch-smoke CI), step 5 →PASS (owner closed 86ajphu98 QA), step 8 PARTIAL→PASS_SCOPED (mDNS+MulticastLock+revamp). Honest corrections: step 2 library wording (data-layer only, no user surface), step 9 PASS→PASS_SCOPED (live kill-walk is 7u-era; no process-level test). Gap classes: [owner-QA] (steps posted on tickets), [toolchain], [descoped-tracked], [missing]→follow-up 86ajpzbxf.
- New evidence: FOUNDATION-DEMO-REVIEW.md V2 section; hardening follow-up ticket.
- Decision: gate-review (all mandatory criteria PASS)

## Risks and rollback

- Risks: auditors over-trust docs — mitigated by requiring file/test/CI citations. Rollback: docs-only; git-versioned.

## Pause and escalation conditions

- Stage-7 closure decision → owner at the gate.

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajp0bpn-foundation-demo-rescore.md --require-complete`
- Validator result: PASS (5/5 mandatory)
- Independent verification result: 9 fresh-context auditors (no self-scoring); synthesis cross-checked against their citations
- Terminal state: GATE_REVIEW (milestone disposition = owner decision after on-device QA)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajp0bpn
