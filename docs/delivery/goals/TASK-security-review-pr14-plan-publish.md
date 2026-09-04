# Goal Contract — TASK-security-review-pr14-plan-publish

## Identity

- Goal ID: TASK-security-review-pr14-plan-publish
- Parent goal ID: NONE
- Title: PR #14 (feat/86ajy0hwg-plan-publish-handoff) is security-reviewed with findings posted on the PR and blocking findings reported to the requester
- Role: security-reviewer
- Status: COMPLETE
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajy0hwg
- Created: 2026-08-29
- Updated: 2026-08-29
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Every attacker-relevant property of PR #14's diff is assessed with code-level and empirical evidence, findings are posted as PR review comments, and a security verdict is issued. The tasked head was 02a8095; the branch moved to 69c3161 mid-review (identity-guard fix + goal contract), and the verdict is anchored to 69c3161.

## Baseline

PR #14 is an open Draft against main (3b39fb5) adding five EditPlan-gated LAN commands (publish_plan, new_plan, template_plan, duplicate_plan, import_plan), three additive OperatorStateView fields (viewer{role,can_edit}, publish, plan_templates), plan-name validation (plan_name_valid), and wholesale plan replacement (install_plan) with a live-slide carry-over. No security review posted yet. CI will not run (Actions minutes exhausted) — local evidence only.

## Inputs and evidence sources

- Worktree at /Users/m.oluwole/Documents/code/scph-wt-86ajy0hwg (read-only; head verified 69c3161, clean)
- `git diff 3b39fb5..02a8095` and `git diff 02a8095..69c3161` in that worktree
- PR #14 description and metadata (gh)
- selahcue-lan/src/{rbac,protocol,server}.rs, selahcue-app/src/{controller,operator}.rs, selahcue-core/src/plan.rs, selahcue-operator/dist/*.js, mobile protocol.dart
- Test suites run with CARGO_TARGET_DIR in the session scratchpad; empirical probe crate against the worktree crates by path

## Scope

### In scope

- Privilege: all five commands map to EditPlan through the single authorize() choke point; no existing command's permission widened; no role below Operator reaches any of the five
- viewer.can_edit is an affordance only — nothing anywhere applies or refuses a command based on it
- Untrusted-input handling of import_plan / plan_name_valid (control chars, Cf/bidi/zero-width, char-vs-byte bounds, atomicity of a refused import)
- Resource exhaustion: undo/redo bounds, published_plan clone, whether the 64KiB frame cap binds, amplification of the pre-existing unbounded AddItem/RenameItem titles
- Live-output integrity (NFR-024) across publish and the four plan-replacing commands
- Information disclosure of viewer.role, publish counters, plan_templates

### Non-goals

- Modifying the code under review; building in the worktree with the default target dir
- Re-reviewing pre-existing surfaces except where adjacent to the diff (reported as non-blocking notes)
- Merging or approving the human gate

### Constraints

- No `make ci` (shared-checkout false reds); per-crate runs only; `-p selahcue-app` requires `--features server`; gates never piped
- Review is read-only against the reviewed branch; scratch experiments live in the session scratchpad

### Assumptions and unknowns

- ASSUMED → corrected: the worktree head equals the tasked head 02a8095. It did at start; the author pushed 649badb + 69c3161 mid-review. Detected via a test asserting a guard absent at 02a8095; resolved by re-anchoring to 69c3161 and re-verifying.
- UNKNOWN → resolved: ClickUp MCP is not connected in this session; ClickUp evidence posting is pending (owner: requester).

## Dependencies and approvals

- gh CLI authenticated for First-Pavilion/selahcue — available
- ClickUp MCP — NOT connected; structured pending update returned to requester

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | All five commands require EditPlan; EditPlan is Operator-only; no existing arm moved; the choke point runs before the handler | Code read of rbac.rs required_permission/permissions + server.rs:776; test_rbac suite | Verified with line cites; suite green | rbac.rs:65-90,138-155; server.rs:776; scratchpad/lan.log (exit=0) | PASS |
| C-002 | yes | can_edit is consulted nowhere to apply/refuse a command | grep of can_edit across .rs/.dart/.js/.ts/.html | Only view construction + tests | grep output (protocol.rs, rbac.rs, operator.rs, tests only) | PASS |
| C-003 | yes | import_plan refuses hostile input whole, leaves no partial state, and its bounds bind | Empirical probe against worktree crates + test_publish suite | Deny leaves plan/revision untouched; cap binds at MAX_PLAN_ITEMS exactly | probe run (atomicity, over/at-cap); scratchpad/app_publish.log 18 passed | PASS |
| C-004 | yes | plan_name_valid assessed for bypasses incl. Cf/bidi/zero-width, char-vs-byte, trim interplay | Empirical probe of plan_name_valid + full import path | Cc refused; Cf accepted end-to-end (finding F1); bounds hold (120 chars ≤ 480 bytes) | probe runs (20 cases + end-to-end RLO/ZWSP/ZWJ import Ack) | PASS |
| C-005 | yes | No new unbounded growth; frame cap is the binding ingress constraint; no amplification beyond +1 plan clone | Code read (MAX_PLAN_UNDO=60, redo bound, published_plan replace-not-grow, saturating sums) | Verified; pre-existing title unboundedness documented in-source, not worsened | controller.rs:147-175,297,3121-3135; plan.rs:798 doc, 878-881 | PASS |
| C-006 | yes | NFR-024: none of the five can blank/alter Live; carry-over verified | Code read of install_plan/PublishPlan + pixel-identity test + no-op probe | Live pixels byte-identical; cursors dropped not clamped; identity guard at 69c3161 | test_publish.rs:230-302,792-860; probe (same-name dup keeps live row) | PASS |
| C-007 | yes | Disclosure assessed: viewer.role, publish counters, plan_templates; webview/Dart rendering of new wire strings | Code read of handler_for stamp, Dart fromJson, dist/*.js innerHTML audit | Own-role only; static templates; textContent everywhere, innerHTML only clears/constants | controller.rs:3516-3536; protocol.dart:262-293; grep of dist/*.js | PASS |
| C-008 | yes | Findings posted as PR review comments with a security verdict | gh pr review / gh api | Review visible on PR #14 | https://github.com/First-Pavilion/selahcue/pull/14#pullrequestreview-5059019301 | PASS |
| C-009 | yes | Blocking findings (if any) reported to the requester | Final response text | Verdict and blocking count stated | Final assistant message | PASS |

## Verification plan

- Focused verification: per-crate test runs (core test_plan, lan --features server, app --features server, all --no-fail-fast, exit codes checked unpiped); empirical probe crate (path deps on the worktree) for plan_name_valid, full import path, atomicity, caps, and the same-name no-op
- Broader regression verification: pinned wire-fixture test inside the lan suite (byte-identical v2 fixtures prove the new fields additive)
- Independent verifier: requester and the other three reviewers on the same PR
- Required environment: read-only worktree at scph-wt-86ajy0hwg; CARGO_TARGET_DIR in the session scratchpad

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: EditPlan gates all five through authorize(); can_edit gates nothing
- Change or investigation: full diff read (rbac, protocol, controller, operator); permissions table; server dispatch; Operator-clamp trace (ApprovePairing/SetSessionRole refuse Operator; host-local operator-shell session is the only Operator on the wire); can_edit grep across languages
- Verifier executed: code reads; lan suite green (scratchpad/lan.log exit=0)
- Result: C-001, C-002 PASS; no widening; serde tag "cmd" rules out variant aliasing
- New evidence: rbac.rs/server.rs/main.rs line cites
- Decision: iterate

### Iteration 2

- Target criterion: C-003..C-007
- Hypothesis: import is atomic and bounded; plan_name_valid stops Cc but not Cf; nothing reaches Live; disclosure immaterial
- Change or investigation: probes (20-case plan_name_valid battery; end-to-end RLO/ZWSP/ZWJ import; atomicity; caps; same-name duplicate). Mid-probe contradiction — a passing test asserted a guard absent at the tasked head — exposed that the branch had moved 02a8095 → 69c3161; re-anchored and re-verified at 69c3161
- Verifier executed: probe runs (exit=0); core/lan/app suites (all exit=0); webview innerHTML audit; Dart fromJson read
- Result: C-003..C-007 PASS; one advisory finding (F1: Cf characters pass plan_name_valid, inconsistent with the is_invisible_formatting sanitizer link labels got after the PR-13 review)
- New evidence: scratchpad logs core_plan.log, lan.log, app.log, app_publish.log; probe outputs
- Decision: iterate (post review → C-008, C-009)

### Iteration 3

- Target criterion: C-008, C-009
- Hypothesis: posting the consolidated review with the advisory completes the deliverable
- Change or investigation: posted PR review (verdict Pass, 0 blocking, 1 low advisory + head-drift note)
- Verifier executed: gh api response (review URL returned)
- Result: C-008, C-009 PASS
- New evidence: https://github.com/First-Pavilion/selahcue/pull/14#pullrequestreview-5059019301
- Decision: complete

## Risks and rollback

- Risk: review comments name exploit preconditions on a private repo PR — acceptable audience (team-only)
- Risk: the branch may move again after this review; the verdict names its commit (69c3161) so a later head needs a delta re-review
- Rollback: none required; review is additive commentary
