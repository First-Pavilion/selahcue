# Router landing privacy implementation plan

Spec: `docs/superpowers/specs/2026-11-16-router-landing-privacy.md`.

Goal: close the confirmed PR #417 interrupted-initial-landing token retention with an observed behavioral RED, minimal production correction, independent review and authorized merge.

## Global Constraints

- Preserve the existing synchronous `takeLandingToken(): string`, lazy views, router scroll behavior, account guard, layouts and server-controlled token validation.
- Sanitize supported initial `/verify` and `/reset` links (case and single trailing slash variants included) before `createWebHistory()`. First query value wins even when empty. A token field causes full query/hash removal; a missing field preserves the URL. Preserve classic malformed-percent behavior without logging values.
- Use one-use private memory bound to the exact initial normalized navigation. Clear on transfer, a different/later attempt, failure/error and pagehide. Never store or log a token for handoff. Replacement failure aborts before router history with a fixed credential-free error.
- Preserve unrelated history metadata while cleaning token-bearing relative auth URLs in existing classic `back`, `current`, `forward` fields. Do not broaden into a general history scrubber.
- Keep plain-Chrome auth pages and their measured 2,816-check contract unchanged. Use fresh contexts in the existing production-build Playwright public-routes gate for the actual interrupted-landings regression.
- Host paging hold: no local runtime tests/build/install/browser/service/project import. Controller owns hosted CI and actual RED/GREEN evidence, remote updates, review publication and merge. No provider or secret access. No weakened tests, timeout changes or retry-until-pass.
- Single source implementer; no subdelegation. Other agents are reviewing independently. Do not revert their work. Preserve the unrelated untracked whole-backend plan and all sibling SDD workspaces.

## Task 1: Close the initial auth landing token retention

Read the Spec and `/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/designs/router-landing-preflight-20261116.md` for already researched construction details. Read the exact #417 review findings. Base is `45ba636155eed0382bc1136679c9fc38c35872fe` in the reused isolated account worktree, now on `codex/router-landing-privacy-20261116`.

Ownership under `implementation/marketing/`: `tests/public_routes_headless.py`, `tests/landingToken.test.ts`, `src/router/index.ts`, `src/lib/auth/useLandingToken.ts`, `src/lib/auth/tokenParam.ts`, and one new pure module `src/lib/auth/landingTokenHandoff.ts` if needed. Do not edit other paths without a controller ruling. The existing package bump is part of the integrated PR baseline, not a new implementation task.

Phase A — tests first:

1. Read the existing public routes fixture and the bounded pending-chunk example identified in preflight. Add only production-build pending-departure browser cases, in fresh contexts, for `/verify`, `/reset`, `/VeRiFy/` and `/ReSeT/`. Both engines already execute through `python3 tests/public_routes_headless.py --engine both`.
2. Hold the matching lazy chunk, prove genuine loading/no API or mount, write a harmless session continuity marker, then navigate the same page to an inert same-origin document. Use explicit finite navigation/assertion waits and close contexts in a finally block. Assert the retained scroll storage leak first and then the remaining absence/preservation contracts; never emit raw canaries or browser state. Do not change existing scenario counts or source.
3. Perform only allowed static checks, commit the tests-only checkpoint with exactly the owned test path, report its expected assertion and stop source authoring. The controller will update the original PR without rewriting history, run hosted CI and return actual assertion RED. An unrelated gate failure does not authorize production authoring.

Phase B — after the controller supplies actual RED:

4. Add meaningful pure behavior tests for parsing/history and handoff lifecycle and implement the minimal production module/wiring per the Spec. Keep current hook consumers and source tripwires intact. Use exact destination identity, initial START_LOCATION qualification, synchronous capture/replacement, guarded failure disposal and finite temporary listener lifetime. The initial source baseline and later query fallback must remain distinct.
5. Self-review privacy, lifecycle, compatibility and test independence. Static whitespace/type syntax inspection is permitted; do not claim a runtime pass. Commit owned production/unit tests, record exact changed paths, protected-plan hash and source/test identities, and hand the covering commands to the controller.
6. Controller obtains the real selected/browser GREEN and all affected normal CI, then independent task spec+code review, security and QA re-review of #417's finding. Resume this implementer for requested fixes using TDD and scoped re-review. Final whole-branch review follows task approval before merge.

Report: the plan workspace's `task-1-report.md`. Include requirement mapping, exact source commits, actual commands/output or explicit UNRUN status, protected-file custody, concerns, and distinction between predicted versus observed RED. Return only status, commit(s), a one-line test summary and concerns. No pushes, CI dispatches, comments, merges, ticket changes or subagents from the implementer.

## Completion

All material findings addressed and re-reviewed; actual current tests pass; final whole-branch review clean; live target/head and composed tree verified before the authorized merge. Record post-merge observation separately. Preserve historical failures and external release qualification still pending.
