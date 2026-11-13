# Goal Contract — TASK-17tnw2b9b8u

## Identity

- Goal ID: TASK-17tnw2b9b8u
- Parent goal ID: NONE
- Title: Local note fallback after cloud HTTP construction failure
- Role: backend-engineer
- Status: ACTIVE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b9b8u
- Created: 2026-11-13
- Updated: 2026-11-13
- Maximum iterations: 8
- Independent verification required: yes

## Objective

An eligible, consented sermon-note request whose HTTP client cannot initialize produces the existing local draft with a safe, useful transient reason. Configuration, consent and pilot refusals remain terminal and never permit rejected persistence.

## Baseline

Source inspected at 218e14140e8df0e1089dbbc3ce09096f26e08310; exact execution base is `40661b4fde38f1e670bc8fde522c17b30bdb93a7` after PR397. Both native provider routes build transport before entering shared fallback; Direct can hide missing-key state. Shared fallback discards the transport cause. Existing pilot pre/post/save guards must be preserved.

## Inputs and evidence sources

- https://app.clickup.com/t/17tnw2b9b8u (live task read 2026-11-13)
- docs/superpowers/plans/2026-11-13-cloud-note-construction-fallback.md
- selahcue-cloud generator, provider constructors and typed transport errors; operator provider_source and note persistence boundary.
- Architecture ruling: one fallible provider factory; one shared request gate/clamp/fallback; fixed typed TLS categories. Immediate notice only.

## Scope

### In scope

- Fallible provider factory and credential-aware constructor ordering.
- Fixed safe reason categories for client setup, empty roots, rejected certificates and generic unavailability.
- Native command/save integration, actual loopback TLS and native Linux root-store tests.

### Non-goals

- Persistent failure notices, schema changes, retries, provider admission relaxation, automatic projection, new dependencies or Windows CI setup.

### Constraints

- Preserve HTTPS, OS trust, redirect refusal, deadlines, release key refusal, Hosted priority and pilot admission.
- Terminal NoteError variants remain terminal; only Transport falls back.
- Never display raw diagnostic text; added fixed reason <=160 bytes.
- One existing ticket and one reviewed PR; local CI, authorized merge and exact QA readback.

### Assumptions and unknowns

- UNKNOWN: real 4 GB Windows performance; outside this scoped bug verification and not claimed.
- ASSUMED: existing local Linux Docker runtime can run isolated native trust-store fixtures after resource admission; preserve runtime limits if unavailable.

## Dependencies and approvals

- Referenced OS trust-store implementation is already merged.
- No unresolved native task dependency was visible on the selected ticket.
- User authorized subagent implementation, reviewed merge after local CI and QA handoff; Windows CI setup cancelled.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Factory/request Transport errors share local fallback after consent/configuration; terminal errors retained | factory counters and request/clamp tests | exact terminal variants; zero construction on refusal; one eligible factory call | PENDING | PENDING |
| C-002 | yes | Actual TLS refusal and safe reason reach immediate operator notice | loopback TLS, typed chain, hostile-string and UI tests | fixed plain text, no planted secret/URL/markup, trusted control succeeds | PENDING | PENDING |
| C-003 | yes | Empty Linux roots produce a local draft and missing key still wins | native Linux child-process fixture | local fallback with empty-root reason; zero-build missing-key case | PENDING | PENDING |
| C-004 | yes | Pilot/Hosted and accepted/pending persistence policy unchanged | native command and pilot regression matrix | no unauthorized save/stage; Hosted independent; accepted artifact preserved | PENDING | PENDING |
| C-005 | yes | Full local CI and independent reviews pass on final source | make ci and Cody/Shadow/Quinn/Vera/final review | exit0 with audit; no unresolved findings | PENDING | PENDING |
| C-006 | yes | Reviewed source merged and linked task moved to QA | GitHub tree/ancestry and ClickUp readback | verified merge and qa | PENDING | PENDING |

## Verification plan

- Focused verification: cloud default/http/openai, native provider feature combinations, isolated environment fixtures, actual TLS, browser notice.
- Broader regression verification: full local make ci with live RustSec audit.
- Independent verifier: code, security, QA, performance and final branch reviewer.
- Required environment: macOS plus existing local Linux container for Linux trust-store behavior; no Windows VM.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 through C-004
- Hypothesis: move construction into the existing admitted error boundary and retain a fixed reason without changing terminal policy.
- Change or investigation: architecture source trace and explicit factory design completed.
- Verifier executed: source review only.
- Result: plan ready; runtime verification pending.
- New evidence: architecture ruling and implementation plan.
- Decision: iterate

### Iteration 2

- Target criterion: C-001 through C-004
- Change: implemented the one-shot, consented cloud factory, credential-first transport construction, fixed typed reasons, and cloud/command/browser fixtures.
- Verifier executed: reconstructed base cloud library compilation with `CARGO_BUILD_JOBS=1 cargo test -p selahcue-cloud --test test_fallback`, standalone Rust formatting, Git whitespace check, and Python plus embedded JavaScript parsing.
- Result: reconstructed baseline refused to compile on the two new public imports (exit 101 in 2.38s, no assertions ran); static checks passed. Original library blob `65edbcdff0f1684e0c223ac3defdf5004fb6f4a7` was restored for the baseline and the implementation then restored. Focused runtime work was paused for sustained host swap activity.
- New evidence: local source-implementation report and `cloud-evidence/fallback-red.log`.
- Decision: independent source review and runtime verification pending; do not advance any completion criterion on the static checks alone.

## Risks and rollback

- Risks: erasing pilot/configuration errors, weakening TLS or leaking diagnostic data; explicit error enum, fixed copy and guard tests cover these boundaries.
- Rollback or recovery: revert scoped PR; no data conversion required.

## Pause and escalation conditions

- Active host paging: stop heavy compilation and retain logs; do not start Windows setup.
- Any destructive operation or new product-policy choice: report before acting.

## Final evaluation

- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/17tnw2b9b8u-cloud-note-construction-fallback.md --completion
- Validator result: PENDING
- Independent verification result: PENDING
- Terminal state: ACTIVE
- Remaining failed or blocked criteria: C-001 through C-006 pending
- ClickUp final evidence comment: PENDING
