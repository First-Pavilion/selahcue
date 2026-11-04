# Goal Contract — TASK-17tnw2b0x3m

## Identity
- Goal ID: TASK-17tnw2b0x3m
- Parent goal ID: NONE
- Title: Marketing CI and production CSP hardening
- Role: frontend-engineer
- Status: GATE_REVIEW
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/17tnw2b0x3m
- Created: 2026-11-04
- Updated: 2026-11-04
- Maximum iterations: 4
- Independent verification required: yes

## Objective
Marketing CI rejects high-severity dependency advisories with a read-only token and no persisted checkout credentials; the Node 22 production image serves an enforced CSP compatible with all current routes.

## Baseline
Fresh main c0325d52e809847fac141a605b74a7e6d7de7021. Marketing checkout persists credentials; no job permissions, advisory gate or CSP; Docker Node 20 differs from CI Node 22. npm audit reports zero high/critical and 13 moderate package nodes originating in minimatch GHSA-g3hv-75wg-m249. Docker 29.8 is available.

## Inputs and evidence sources
- Live ClickUp ticket, all comments and dependencies read; no dependencies or previous comments.
- implementation/marketing, .github/workflows/ci.yml, Makefile and workflow guard scripts.
- https://github.com/nodejs/Release#release-schedule
- https://docs.npmjs.com/cli/using-npm/config/
- https://nginx.org/en/docs/http/ngx_http_headers_module.html

## Scope
### In scope
- Marketing checkout/token permissions, npm audit gate and verified install-script suppression.
- Node 22 image, real Docker build, nginx CSP and real-browser regression gate.
- Explicit disposition of optional font self-hosting and action pinning.
### Non-goals
- API dependency migration; packaging dispatch, deployment, secrets, collection activation.
- Unrelated dependency upgrades, visual changes or broad action pinning.
### Constraints
- Preserve existing routes, fonts, API same-origin proxy, visual/installer/NDI controls and 15-minute CI timeout.
- Do not touch primary user-modified mobile lockfile or frozen unpublished branches.
### Assumptions and unknowns
- UNKNOWN: browser CSP compatibility; verify real production nginx in Chromium and WebKit.

## Dependencies and approvals
- User authorizes implementation and draft PR; root coordinates four independent reviews, merge and QA.
- Kenji owns API uv work in another worktree; shared workflow changes must integrate without reverting it.

## Completion predicate
| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Marketing token is read-only, checkout credentials are not persisted and high advisories fail without waivers | focused hardening tests; actionlint; npm audit --audit-level=high | all exit 0; negative fixtures fail | docs/delivery/evidence/17tnw2b0x3m/results.md | PASS |
| C-002 | yes | Node 22 production image builds with install scripts disabled | npm ci; make marketing-check; docker build | all exit 0 | docs/delivery/evidence/17tnw2b0x3m/results.md | PASS |
| C-003 | yes | CSP applies to app, assets and errors; all routes render without CSP violations and injected script is blocked | production CSP browser harness Chromium and WebKit | exits 0; routes and positive/negative probes pass | docs/delivery/evidence/17tnw2b0x3m/results.md | PASS |
| C-004 | yes | Existing marketing/browser and workflow controls remain passing | required marketing suites and workflow policy scripts | all exit 0 | docs/delivery/evidence/17tnw2b0x3m/results.md | PASS |
| C-005 | yes | Four independent reviews and actual CI approve current head | root Cody Shadow Quinn Vera and GitHub checks | four PASS and CI green | pending root review | PENDING |

## Verification plan
- Focused verification: structural hardening tests with failing baseline; real image CSP browser positive and negative checks.
- Broader regression verification: make marketing-check, existing required browser suites and actionlint/workflow policies.
- Independent verifier: root dispatches Cody, Shadow, Quinn and Vera.
- Required environment: Node 22-compatible local toolchain, Docker nginx, Python Playwright Chromium/WebKit; GitHub CI.

## Iteration ledger
### Iteration 1
- Target criterion: C-001 through C-004.
- Hypothesis: exact job permission controls, audit threshold and a restrictive production CSP can preserve current site behavior.
- Change or investigation: baseline traced, Docker confirmed, audit measured; implement focused regression verifier before fixes.
- Verifier executed: npm audit --json; docker info.
- Result: baseline insecure settings confirmed, no high/critical advisories, Docker available.
- New evidence: /tmp/selahcue-marketing-audit.json.
- Decision: iterate

### Iteration 2
- Target criterion: C-002, C-003 and C-004.
- Hypothesis: production-image verification reveals issues that a Vite preview cannot detect.
- Change or investigation: real image found preexisting TS2307 for canonical pilot notice outside context; retained import/content, used repository-root context with Dockerfile-specific deny-all allowlist and explicit COPY. Both image builds now exit 0. Improved browser assertions to observe actual HTTP font responses (CSS-origin font resource timings omit fonts), and used the real accessible Sign in button rather than assuming a type attribute.
- Verifier executed: final Docker build, production security_headers_headless.py, npm audit --audit-level=high against registry and local synthetic-high fixture; make marketing-check; workflow guards.
- Result: Docker and both production browsers PASS; 68 routes per engine, real font HTTP 200, auth submit/mobile menu/header inheritance and script-blocking probes. Real audit exits 0; synthetic high fixture exits 1. Shared gate 1250 tests passes. Existing browser suites pass except auth/WebKit responsive rerun pending after parallel dist rebuild invalidated their initial attempts.
- New evidence: docs/delivery/evidence/17tnw2b0x3m/results.md and /tmp/selahcue-marketing-*.log.
- Decision: iterate

### Iteration 3
- Target criterion: C-004 and final handoff.
- Hypothesis: running affected browser gates sequentially against stable dist resolves the observed harness file race without product changes.
- Change or investigation: terminated and reaped invalidated auth attempt (143); installed CI-pinned PyYAML6.0.3 in isolated verification venv after missing-module failure; reran auth and WebKit responsive strictly serially. No test/product tolerance changes. Separately diagnosed baseline Linux Home Figma helper missing measured scrollbar compensation; root will create separate blocker ticket/PR.
- Verifier executed: final auth state harness, responsive WebKit, individually recorded mirror/workflow/minute/syntax checks, fresh main fetch and structural contract validator.
- Result: auth77 scenarios/2765 checks PASS; WebKit responsive2363 checks PASS; every local final required verifier exits0 except deliberate synthetic high audit refusal exit1. C-001 through C-004 PASS. All verifier processes finished.
- New evidence: docs/delivery/evidence/17tnw2b0x3m/verifier-status.json and results.md.
- Decision: gate-review

## Risks and rollback
- Risks: overly restrictive CSP could block fonts or Vue styles; require actual-browser checks.
- Rollback or recovery: revert this ticket commit; no deployment performed.

## Pause and escalation conditions
- New scope, unavailable required environment or automatic publication rejection: report exact blocker to root; do not bypass.

## Final evaluation
- Validator command: python3 /Users/m.oluwole/.agents/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/TASK-17tnw2b0x3m.md --completion
- Validator result: structural exits0; completion intentionally exits1 while mandatory C-005 independent reviews/actual CI remain pending
- Independent verification result: root to dispatch Cody, Shadow, Quinn and Vera on frozen head; actual GitHub CI pending
- Terminal state: GATE_REVIEW
- Remaining failed or blocked criteria: C-005 pending four independent reviews and actual CI; existing Linux Home harness issue requires separate fix before green CI
- ClickUp final evidence comment: root handoff comment will link the published PR and this evidence
