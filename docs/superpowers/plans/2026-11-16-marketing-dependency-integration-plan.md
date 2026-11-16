# Marketing dependency integration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve all four reviewed dependency increments and the merged Router privacy fix in one verifiable candidate.
**Architecture:** Merge the prepared three-PR stack then the TypeScript ESLint PR, resolving only manifest/lock records from original reviewed sources.
**Tech Stack:** npm lock v3, Node22, Vite8, Vue3, Vue Router5, ESLint10.
**Spec:** docs/superpowers/specs/2026-11-16-marketing-dependency-integration.md

## Global Constraints

Only implementation/marketing/package.json and package-lock.json are worker-owned. Preserve current target source, Router5.5 record, all four exact original package increments and original PR ancestry. No npm resolution or unrelated version drift. Local runtime held; no project imports, installation, builds, browsers, provider requests or external mutations. Protected backend plan hash must remain unchanged. One implementer; no subagents.

## Review Focus

- Conflict-side selection losing a reviewed update: compare exact original record deltas and all four ancestors.
- Router regression: retain current target manifest range, lock record and privacy/test source bytes.
- Lock/manifest mismatch: compare root dependency maps and Node engine after both merges.
- Supply-chain drift: compare every changed record's full value and all untouched records to their authoritative source.
- Integration/runtime regression: current full hosted install/audit/lint/build/browser/image gates; no inferred pass from static JSON.

### Task 1: Reconcile only the reviewed package records

Read the binding spec first. Work in the controller-prepared account-overview isolated worktree on codex/marketing-dependency-integration-20261116 at the supplied design-only dispatch HEAD. You are not alone: preserve other work and do not read/edit sibling plan workspaces.

- [ ] Inspect the two package files, all original increments and prepared stack. Record actual merge conflicts and distinguish them from behavioral RED. Do not run project code.
- [ ] Merge the prepared #418 stack without losing main changes, resolving the two JSON files by the first three original deltas described in the spec. Stage only these files plus automatic unchanged-source merge results, confirm every other target path remains unchanged and commit the merge. If any unexpected path conflicts, return the exact conflict for root adjudication without guessing.
- [ ] Merge original #415 and resolve its eleven package records and single root devDependency range by the same rule. Commit the merge, preserving all previous ancestors.
- [ ] Statically verify both merge commits, final exact-record composition, root-map/engine equality, no unrelated path edits, clean diff/check, and protected plan hash. Store the focused verification receipt in this plan workspace.
- [ ] Write task-1-report.md with exact commits, changed paths, conflict resolution, commands/results, current runtime UNRUN and remaining hosted requirements. Return concise status/commit/checks; no push or CI dispatch. Root obtains current hosted evidence and independent task/final reviews before merging.

## Completion

Current candidate integrates all four original requests, current hosted owning gates and independent reviews pass, and root verifies live refs and actual merge ancestry. Old failing results remain preserved.
