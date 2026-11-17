# Native APFS admission repair implementation plan

> Execute with superpowers:subagent-driven-development and superpowers:test-driven-development. Root owns remote publication, CI observation, review/merge and any manual native dispatch.

**Goal:** admit the actual owned clone directory using a supported macOS filesystem query while retaining all existing clone/resource/proof gates.

**Architecture:** one operating-system adapter correction in `SystemHost.clone_probe`, exercised through its real implementation with fake external process and ctypes boundaries. No workflow or native fixture changes.

**Binding spec:** [native APFS admission design](../specs/2026-11-17-native-apfs-admission-design.md). Target/base is reviewed main `9c93a5d6da402ae9bc308da91a136ce51e2cf6ce`. The original hosted failure remains archived.

### Task 1: Correct the filesystem query and cover the adapter

**Owned executable files:** `scripts/macos_native_proof.py`, `scripts/test_macos_native_proof.py`. No application, fixtures, workflow, timeout or golden changes. The worker is not alone and must preserve other edits and ignored audit records.

1. Read the spec, real adapter and existing tests. Add a positive regression and required negatives through real `SystemHost.clone_probe` with only process/ctypes boundaries replaced. Use independent observed df output, a space-bearing directory/mountpoint and the old invalid-operand failure. No production changes yet.
2. Run the named regression under pinned Python3.14 with a 30-second process-group limit. Preserve the actual expected RED and source/test hashes. Failure must establish the old adapter cannot complete the supported directory query, not an import/setup mistake. If test design needs correction, retain the first result.
3. Replace the single query and validate the observed Type-bearing output exactly as the spec says. Keep all existing actual clone/COW operations and return shape. No unrelated cleanup or fallback.
4. Run the same focused controls GREEN and then the full existing native proof unittest suite once. Run diff-check; workflow/actionlint guards are needed only if affected or required by a newly discovered concern. No build, app import, service, browser, provider, dependency install or local full CI under the resource hold.
5. Commit only the two owned files. Record full command output, process caps, exact parent/head/tree, named RED/GREEN and full-suite results, change rationale and runtime limits in the task report. Do not push or dispatch.
6. Root obtains independent spec/code review; fixes return to the implementer for TDD and re-review. Obtain whole-branch review of the final actual main composition. Root publishes one normal PR and requires applicable CI before the already-authorized guarded merge. Fresh main/head/tree checks and actual merge readback are mandatory.
7. After source acceptance, root records one additional changed-source manual proof decision under the binding spec, then observes it through terminal receipt verification. A failed proof is not native acceptance and is not automatically retried.

## Plan self-review

The only production consumer is the unchanged admission call and receipt field; task1 preserves both. The command checks the actual probe directory; clone success and write independence retain separate oracles. Fixture success is source evidence and cannot replace actual host admission. The plan explicitly separates source merge, ordinary CI and the later finite native proof. The public artifact correction changes no content or workflow guard. No tasks depend on PR233's separately running canonical API/G1 gate.
