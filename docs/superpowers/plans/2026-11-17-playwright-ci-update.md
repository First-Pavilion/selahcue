# Playwright CI update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Advance the pinned CI browsers coherently while retaining the original acceptance gates and bounded diagnostics.

**Architecture:** Change the three Python dependency literals and exact WebKit diagnostic configuration together. Existing subprocess fixtures prove bundle admission and receipt boundaries independently of the production constants. Hosted workflows own runtime browser qualification.

**Tech Stack:** Python3.14, Playwright1.65.2, GitHub Actions, Node22.

**Spec:** docs/superpowers/specs/2026-11-17-playwright-ci-update-design.md

## Global Constraints

- Python Playwright1.65.2; WebKit2388/27.2, Chromium1255/159.0.8154.6; exact WPE root `/home/runner/.cache/ms-playwright/webkit-2388/minibrowser-wpe`.
- Four code/config files only; accompanying design/plan documentation may be committed. No historical evidence edits or lockfile changes.
- Preserve application behavior, original gates/205cells/Home1200ms and95±2/Secondary attempts, runners, job bounds, diagnostic schema/privacy and finite limits.
- Shared WPE path repinning is deliberate; GPU-specific behavior remains unchanged. Reject stale bundle/receipt values rather than accepting arbitrary versions.
- Local standalone fake fixtures only,30s whole-process-group bounds and cleanup. No browser/native/app/DB/install/network execution by worker.
- Root controls all pushes, hosted runs and merges. Retain older failure evidence and current in-flight runs.

## Review Focus

- A stale2311 executable remains rejected while2388 WebProcess and the other three roles are admitted: existing role and WebProcess tests.
- Current receipt producer and export validator disagree: assert actual emitted1.65.2/2388 plus complete metadata; wrong old pair exports null/incomplete.
- Generic semver/revision validation accidentally broadens export: exercise stale pair at encoder boundary.
- Bundle repinning changes bounded exports, correlation or GPU paths: full existing collector suite with saturation and shared-module fixtures.
- Workflow installs drift apart or change runner/cost behavior: existing literal-pin, actionlint, workflows and CI-minutes controls plus exact four-file diff.

---

### Task 1: Repin the CI browsers and exact diagnostic contract

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/legal-drift.yml`
- Modify: `implementation/marketing/scripts/webkit_crash_journal.py`
- Test: `implementation/marketing/tests/test_webkit_crash_journal.py`

**Interfaces:**
- Consumes: existing `CrashJournalCLI` subprocess fixtures and `SourceReceipt` export/producer fixtures, exact bundle path and receipt fields.
- Produces: unchanged collector interface/schema with the selected version/revision, and matching three workflow literals.

- [ ] Step1: Adapt `CrashJournalCLI.test_exact_time_window_and_exact_package_executable_roles` and independent `BUNDLE_BIN` to2388, using explicit2311 for the rejected row; keep3-record cap and original counts. Retain independent `test_sigabrt_metadata_and_only_safe_stack_evidence` to cover WebProcess. Update source producer expected pair in `SourceReceipt.test_source_receipt_actual_checkout_is_distinct_from_candidate`. Extend `test_source_export_revalidates_and_does_not_change_kernel_ownership` so old1.61.0/2311 fields become null and complete=false. Update the saturated complete fixture to1.65.2/2388.
- [ ] Step2: Under the30s group supervisor, run `python3.14 implementation/marketing/tests/test_webkit_crash_journal.py CrashJournalCLI.test_exact_time_window_and_exact_package_executable_roles CrashJournalCLI.test_sigabrt_metadata_and_only_safe_stack_evidence SourceReceipt.test_source_receipt_actual_checkout_is_distinct_from_candidate SourceReceipt.test_source_export_revalidates_and_does_not_change_kernel_ownership`. Require assertion RED against unchanged collector, not import/setup/timeout failure. Save command, status, output and hashes before production edits.
- [ ] Step3: Make minimal exact replacements in the two workflows and collector bundle/receipt producer/validator; preserve all other behavior and literal workflow pin guards. Do not import production constants into fixtures or weaken assertions.
- [ ] Step4: Run the same named command for GREEN, then full `test_webkit_crash_journal.py`, existing `node --test tests/legalWorkflow.test.ts` from marketing under Node22, `actionlint`, `.github/scripts/check_workflows.py --self-test` and without flag, `.github/scripts/check_ci_minutes.py --self-test` and without flag. Each process group gets30s and logs; no application/package setup. If environment/admission prevents a check, report it without calling it a pass or increasing the cap.
- [ ] Step5: Review the complete diff for exact file/boundary preservation, commit the four-file implementation and report BASE/HEAD, RED/GREEN commands and actual outcomes, source hashes and remaining hosted proof. Do not push or merge. A fresh reviewer then owns spec/quality; root owns whole-branch review and CI before merge.
