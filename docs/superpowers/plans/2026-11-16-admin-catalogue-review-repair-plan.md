# Admin catalogue review remediation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task by task.

**Goal:** Resolve #375's current-main integration and six reviewed correctness findings, retaining its private development-only scope.
**Architecture:** Forward schema integration, real HTTP/transaction/consumer regressions, then minimal shared-writer and admin-boundary corrections.
**Tech Stack:** Django, Strawberry, PostgreSQL, Redis, pytest, existing GitHub Actions API job.
**Spec:** docs/superpowers/specs/2026-11-16-admin-catalogue-review-repair.md

## Global Constraints

Preserve current main and every existing permission, audit, replay, lock-order and deployment guard. No paid launch or production admin enablement. Shared validation is dimension-based, never plan-name based. Weekly note bound is `2**63 - 1`; STT minute bound is `(2**63 - 1)//60`; device bound is one through `2**31 - 1`; normalized raw storage width is 64. Strict tests-first behavioral fixes. Local heavy runtime is held; root owns hosted RED/GREEN and all remote changes. Do not spawn subagents. You are not alone in the codebase: preserve all other edits and plans.

## Review Focus

- A new revision must not accompany an excluded immediate price in the deterministic two-connection race.
- Invalid quota/storage values and invalid rename codes refuse with stable field/error contracts and no persistent changes.
- Canonical retry identity must agree across request fingerprint, receipt and audit, with permission rechecked before replay.
- The migration frontier must preserve existing org grants and accounts dependencies.
- Tests must exercise actual HTTP/CSRF, transactions and current signed-manifest/effective-plan consumers; no mock-only assertions or version-string tests.

### Task 1: Integrate current main and prepare behavioral RED

Read the binding spec first. Original source is `16eca1d43cb036dcf227420419bb221347bd716b`; integrate exact main `46483ac0eced5391112e4c022b0855206dda1262` preserving both ancestries. Root supplied this isolated branch at a design-only dispatch commit. Review findings are in `/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/release-evidence/open-pr-review/pr375-consolidated-review.md`; detailed original reports share its directory as `pr375-{cody,shadow,quinn,vera}-review.md`.

Own integration conflicts in catalogue models/settings, the forward receipt migration, and narrowly required API regression test files. Do not implement behavioral fixes in admin.py/services.py yet. The forward migration is a required prerequisite to execute the existing slice against the current schema; record its exact metadata change separately from behavioral RED.

- [ ] Merge current main without dropping either OrgPlanGrant or CatalogueAdminMutation; preserve unrelated main changes. Rename the unmerged receipt migration to `0010_admin_mutation_receipt.py`, depending on `0009_org_plan_grant`. Keep shipped migration bytes and accounts dependencies unchanged. Commit integration separately and report resolved files.
- [ ] Read test-driven-development/writing-good-tests.md. Add actual regressions for each required behavior and the evidence controls in the spec. Reuse current test helpers where appropriate. Use bounded thread events/barriers and cleanup, not arbitrary sleeps or mocked revisions, for the price-read race. Audit failure injection must observe the real write before raising, then assert database rollback and retry. Keep post-migration cleanup restoring the full leaf frontier.
- [ ] No production behavior correction before intended RED is observed. Commit tests separately; do static parsing and whitespace checks only. Write `task-1-report.md` with exact integration/test commits, production behavior preserved, test names, expected failure per confirmed defect, controls, and hosted execution UNRUN. Return ready for root's hosted RED checkpoint; do not push or start CI.
- [ ] At the RED checkpoint only, use `--maxfail=0` in the existing API workflow command, matching Makefile command and two parity/self-test literals in scripts/check_api_gate.py. No selection or failure-status changes. Record this diagnostic delta separately, including the binding design amendment. Task 2 restores the original `--maxfail=1` setting before final GREEN.
- [ ] Root publishes this checkpoint to the existing PR branch, observes full hosted API output, repairs any fixture defects through a scoped fix loop, and records actual RED before Task 2. Task review confirms spec/quality of the prepared regressions and migration integration. Existing failures remain visible and are not relabeled as successful verification.

### Task 2: Correct the confirmed defects and prove GREEN

Read the binding spec and the root's Task 1 RED receipt in this plan workspace. Start only after root confirms the intended failures. You own minimal production changes in catalogue/admin.py and catalogue/services.py plus only test-fixture corrections justified by evidence. Do not weaken tests to make them pass. Preserve existing concurrent-retry and revision-first lock behavior and the unrelated target tree.

- [ ] Fix price-read ordering, dimension-consumer and width validation, canonical idempotency propagation, and rename's invalid-code handling, matching each observed regression.
- [ ] Use one canonical key in writer/audit/receipt/fingerprint; keep distinct actor-scoped operations and payload conflict detection. Shared writer validation must also protect non-admin callers.
- [ ] Run permitted static checks, commit and document each fix-to-test mapping. Root runs full existing hosted API/migration/tier-sweep CI on the final candidate. Read results and fix any actual regression through the requested TDD/re-review loop. No independent CI polling or remote changes.
- [ ] Restore the temporary RED-only `--maxfail=0` configuration to current-main `--maxfail=1` in all three parity-linked files. The final PR must not retain this diagnostic gate delta.
- [ ] Report exact head/tree, observed verification and remaining limitations. Root obtains scoped Cody/Shadow/Quinn/Vera re-review plus the final whole-branch review before the authorized merge.

## Completion

All confirmed findings addressed with observed RED/GREEN, current API migration and full PostgreSQL/Redis gates pass, independent reviews approve the exact integrated tree, and root verifies live source/target/merge ancestry and external readback.
