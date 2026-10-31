# Goal Contract — TASK-17tnw2bbhw1-pilot-source

## Identity

- Goal ID: TASK-17tnw2bbhw1-pilot-source
- Parent goal ID: NONE
- Title: Release-capable pilot credential source
- Role: ai-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2bbhw1
- Created: 2026-10-31
- Updated: 2026-10-31
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Native generated configuration feeds readiness and request construction; invalid/expired config fails closed.

## Baseline

Verified source baseline 3f651d143ad73de262cab1d74c6fb577b73adf5a; developer sources refuse release. Rebased for review onto cbc1e541f66f4f99fae0591733e2497a670b9fbd after PR325; verified no Rust/Cargo/Make changes and unchanged P02 source.

## Inputs and evidence sources

- Approved scope relayed by root; /private/tmp/selahcue-continuation-20261031/aria-continuation.md

## Scope

### In scope

- Synthetic credential source integration only; no real credentials, publication, workflows or scanner changes; active-session expiry is P03.

### Non-goals

- Synthetic credential source integration only; no real credentials, publication, workflows or scanner changes; active-session expiry is P03.

### Constraints

- Fixed cutoff 2027-04-30T23:59:59Z; earlier provider expiry wins; preserve consent, license and completed-transcript gates. No model/prompt change, deterministic evaluation only.

### Assumptions and unknowns

- UNKNOWN actual provider permissions and revoke owner; P01 prerequisite.

## Dependencies and approvals

- Root owns ClickUp browser updates and merge; four independent reviews required; P01/P04 block real credential embedding/release, not synthetic implementation.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Config validation, earliest expiry, authorization and consent tests pass in release | Focused cargo tests | zero failures | docs/delivery/evidence/p02-pilot-source.md | PASS |
| C-002 | yes | Readiness/request source consistency and ordinary release guards pass | Operator tests and feature registry check | zero failures | docs/delivery/evidence/p02-pilot-source.md | PASS |
| C-003 | yes | Four independent reviews approve head | Cody Shadow Quinn Vera reports | no blocking findings | docs/reviews/ | PENDING |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: Focused cloud/STT/operator tests, release mode, synthetic credentials only
- Broader regression verification: Focused cloud/STT/operator tests, release mode, synthetic credentials only
- Independent verifier: Cody Shadow Quinn Vera via root
- Required environment: Local macOS Rust; full make ci coordinated by root

## Iteration ledger

### Iteration 1
- Target criterion: C-001
- Hypothesis: bounded native parsing and an injected clock enforce an all-or-nothing cohort source.
- Change or investigation: implemented private raw input, admitted config, strict cutoff/model/key validation and native constructors.
- Verifier executed: release test_pilot, then full cloud release suite.
- Result: initial missing API RED, initial 3 GREEN; expanded 5 boundary tests GREEN; full cloud suite 101 passed, zero failed/ignored.
- New evidence: docs/delivery/evidence/p02-pilot-source.md
- Decision: iterate

### Iteration 2
- Target criterion: C-002
- Hypothesis: a single operator selector keeps readiness, generation/regeneration and worker construction consistent without weakening dev guards.
- Change or investigation: added off-by-default pilot capability, generated build input and shared selector; retained existing license/consent entry points.
- Verifier executed: feature registry guard; full Deepgram release suite; strict cloud/STT clippy; operator release integration build.
- Result: feature guard PASS; Deepgram 93 passed zero failed/ignored. Strict provider lint PASS after applying existing test unwrap policy. Initial operator release compile passed; final ordinary/pilot full release suites and source matrix passed.
- New evidence: source integration harness exercises actual selectors and request builders with synthetic keys only.
- Decision: iterate

### Iteration 3
- Target criterion: C-001 and C-002 final verification
- Hypothesis: release fixture builds demonstrate selection and authorization without environment fallback; negative mutation controls catch deadline and bound regressions.
- Change or investigation: full source matrix, ordinary/pilot operator suites, native OpenAI/Deepgram authorization and consent controls; corrected pilot-specific unavailable diagnostic without developer .env instructions.
- Verifier executed: full cloud release suite (101), full Deepgram release suite (93), ordinary operator release suite (455), pilot suite (476), strict release provider/operator/developer-route clippy, source matrix and feature guard.
- Result: zero failures; only explicit operator child-process/real-model entries ignored. Expiry-equality and size-cap mutations caught, source restored. Test-only err-expect lint corrected and strict checks repeated.
- New evidence: docs/delivery/evidence/p02-pilot-source.md; all configuration inputs synthetic, no provider egress.
- Decision: gate-review

## Risks and rollback

- Risks: embedded keys are extractable; local clocks can be changed; provider expiry is authoritative; active-session shutdown is P03. Real embedding remains gated by P01/P04.
- Rollback or recovery: revert this ticket branch/PR.

## Pause and escalation conditions

- Real credentials, provider calls or out-of-scope workflow changes require root.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2bbhw1-pilot-source.md
- Validator result: structural validation PASS; completion evaluation waits for C-003
- Independent verification result: Cody, Shadow, Quinn and Vera pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-003 independent reviews pending; real embedding/release separately gated by P01/P04 and P03 active-session work
- ClickUp final evidence comment: root owns browser update; no remote status mutation claimed
