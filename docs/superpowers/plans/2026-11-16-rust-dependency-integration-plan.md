# Rust dependency integration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retain the reviewed Rust dependency group and the repaired HarfRust/WinSafe operator in one verifiable candidate.
**Architecture:** One original414 merge into the prepared current-main/395/428 branch; resolve only exact authoritative Cargo records.
**Tech Stack:** Rust1.98, two Cargo workspaces and lockfiles, Tauri operator, PrintPDF/HarfRust.
**Spec:** docs/superpowers/specs/2026-11-16-rust-dependency-integration.md

## Global Constraints

Worker owns only both Cargo.lock files and the operator Cargo.toml. Preserve exact original414record changes plus all395versions, source/fixtures/CI, current target paths and PR ancestry. No new resolution or local runtime/imports/build/install/browser. No subagents, secrets or remote mutations. Root owns hosted gates/reviews/push/merge.

## Review Focus

- Conflict resolution dropping a group: exact TOML record/delta and manifest comparison.
- Dependency edge ambiguity: each final lock reference resolves to exactly one included package; compare updated constraints separately.
- Unrelated resolution drift: every changed record/checksum/version matches original reviewed input.
- PDF behavior: unchanged full-content independent oracle and fresh nine-page output on finalPrintPDF.
- False feature/platform evidence: bind results to actual lock root, feature command, OS and adapter/non-skip paths.

### Task 1: Merge only the reviewed Cargo records

Read the binding spec first. Use the controller-prepared temporary worktree on codex/rust-dependency-integration-20261116 at the supplied dispatch HEAD. You are not alone; preserve other agents' work and sibling plan workspaces.

- [ ] Inspect original414diff and prepared current blobs. Record the exact manifest/lock conflict, not a behavioral RED. No project runtime.
- [ ] Merge original414 with no fast-forward and resolve only the three owned paths using the spec. Unexpected conflict paths require a report to root before guessing. Preserve both exactnum_enum_derive records as they agree; no dependency refresh.
- [ ] Parse both final locks and manifest via Python standard-library TOML; reconstruct exact record additions/changes/removals against original414base, retaining all prepared-parent records outside those deltas. Assert all dependency references resolve, direct pins match, all other source/tree entries unchanged, correct modes and originalheads ancestry. Run git diff/check. Commit the merge.
- [ ] Write task-1-report.md and focused verification receipt with exactbase/head/tree/conflicts, staticcommands/results and currenthostedUNRUN. Return concise status/commit/checks. Root runs current full hosted gates/PDF proof and independent integration/final reviews before any merge.

## Completion

Current graph passes required hosted checks and independent reviews, final refs/tree/ancestry verified. Historical failures and unexecuted native release qualification remain explicit.
