# Goal Contract — TASK-security-review-pr13-plan-links

## Identity

- Goal ID: TASK-security-review-pr13-plan-links
- Parent goal ID: NONE
- Title: PR #13 (feat/86ajxxqtp-plan-link-missing-state) is security-reviewed with findings posted on the PR and blocking findings reported to the requester
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hw0
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every attacker-relevant property of PR #13's diff (head 6aee657, base origin/main) is assessed with code-level evidence, findings are posted as PR review comments, and a security verdict is issued.

## Baseline

PR #13 is an open Draft against main adding `verse_numbers`/`status`/`label` to `ContentLinkView`, a TAB-delimited codec extension carrying the label, `LinkResolution`, and `PlanSummaryView`. `label` is untrusted wire input (SetItemContent), persisted and echoed. No security review has been posted yet.

## Inputs and evidence sources

- Worktree at /Users/m.oluwole/Documents/code/scph-wt-plan-links (head 6aee657)
- `git diff origin/main...HEAD` in that worktree
- PR #13 description and files (gh)
- selahcue-core/src/plan.rs, selahcue-lan/src/{protocol,rbac,server}.rs, selahcue-app/src/{controller,operator}.rs, selahcue-data/src/plan_repo.rs, selahcue-operator/dist/app.js, mobile protocol.dart
- Test suites run in the worktree with CARGO_TARGET_DIR=.target

## Scope

### In scope

- Inescapability of MAX_LINK_LABEL_LEN across wire, in-memory, and persistence paths
- Codec field-boundary integrity and control-character survival
- RBAC: no new privilege path; edits cannot reach Live output
- Information disclosure of the label to lower-privileged Monitor roles

### Non-goals

- Modifying the code under review
- Re-reviewing pre-existing surfaces except where adjacent to the diff (reported as non-blocking follow-ups)
- Merging or approving the human gate

### Constraints

- No `make ci` (concurrent-session false reds); per-crate runs only; `-p selahcue-app` requires `--features server`; never pipe a gate into tail
- Review is read-only against the reviewed branch; scratch experiments live in the session scratchpad

### Assumptions and unknowns

- ASSUMED: the worktree head equals the PR head (verified: 6aee657 == headRefOid)
- UNKNOWN → resolved: ClickUp MCP is not connected in this session; ClickUp evidence posting is pending (owner: requester)

## Dependencies and approvals

- gh CLI authenticated for First-Pavilion/selahcue — available
- ClickUp MCP — NOT connected; structured pending update to be returned to requester

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Every path that can place a Deck label into a plan, the wire, or the DB applies the character bound | Code trace of set_item_content, encode, decode, plan_repo, serde derivability, pub-field production writes | No unbounded path exists; each site names its sanitizer | plan.rs:195-207,514-536; plan_repo.rs:35,78,202; ItemContent has no Serialize derive; only production `.content =` write is plan.rs:536 | PASS |
| C-002 | yes | No codec field can shift TAB boundaries and Cc control chars cannot survive encode | Code read of encode/sanitize_field + core test suite run | All string fields sanitized at encode; tests green incl. tab-injection tests | scratchpad/core_plan.log (27 passed, exit=0) | PASS |
| C-003 | yes | SetItemContent maps to EditPlan through the single authorize() choke point and no diff code reaches the Live surface | Code read of rbac.rs, server.rs:776, controller set_item_content + app suite run | EditPlan Operator-only; re-stage touches Preview only; NFR-024 test passes | rbac.rs:88-89,138; server.rs:776; controller.rs:3076-3109; scratchpad/app.log (exit=0) | PASS |
| C-004 | yes | Disclosure of the label to Viewer/Assistant is assessed against what those roles already receive | Code read of GetOperatorState gating + mobile fromJson | Explicit verdict with reasoning recorded in the review | rbac Monitor grant; controller.rs:2626; protocol.dart:262-293 | PASS |
| C-005 | yes | Findings are posted as PR review comments with a security verdict | gh pr review / gh api | Review visible on PR #13 | https://github.com/First-Pavilion/selahcue/pull/13#pullrequestreview-5056922896 | PASS |
| C-006 | yes | Blocking findings (if any) are reported back to the requester | Final response text | Verdict and blocking count stated | Final assistant message | PASS |

## Verification plan

- Focused verification: per-crate test runs (core, lan --features server, app --features server); scratch empirical probes of parse_one and char classification
- Broader regression verification: pinned wire-fixture test within lan suite
- Independent verifier: requester and the other three reviewers on the same PR
- Required environment: worktree at scph-wt-plan-links, CARGO_TARGET_DIR=.target

## Iteration ledger

### Iteration 1

- Target criterion: C-001..C-004
- Hypothesis: the label bound is inescapable; codec safe; RBAC unchanged; disclosure immaterial
- Change or investigation: full diff read, trust-boundary trace, test runs, scratch empirical probes (60KB padded ref parses; NUL parses; RLO/ZWSP not Cc; TAB is Cc)
- Verifier executed: cargo test per-crate (exit=0 each); code reads cited above
- Result: C-001..C-004 satisfied; two non-blocking adjacent findings (Cf bidi chars survive sanitizer; pre-existing unbounded reference/translation)
- New evidence: scratchpad logs core_plan.log, lan.log, app.log; refcheck output
- Decision: iterate (post review → C-005, C-006)

### Iteration 2

- Target criterion: C-005, C-006
- Hypothesis: posting the consolidated review with two inline advisories completes the deliverable
- Change or investigation: posted review 5056922896 (verdict Pass, 0 blocking, 2 low advisories inline on plan.rs:206 and controller.rs:664)
- Verifier executed: gh api response (state COMMENTED, html_url returned)
- Result: C-005 PASS; C-006 PASS via final report to requester (verdict Pass, zero blocking findings)
- New evidence: https://github.com/First-Pavilion/selahcue/pull/13#pullrequestreview-5056922896
- Decision: complete

## Risks and rollback

- Risk: review comments name exploit preconditions on a private repo PR — acceptable audience (team-only)
- Rollback: none required; review is additive commentary
