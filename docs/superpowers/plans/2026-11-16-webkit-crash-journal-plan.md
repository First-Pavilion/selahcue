# WebKit existing crash-journal plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task by task.

**Goal:** Attribute a captured native allocator failure using existing runner journal summaries without changing the browser gate.
**Architecture:** A bounded, allowlisted standard-library CLI collector and a post-sweep CI step; no crash dump access or browser changes.
**Tech Stack:** Python stdlib, journalctl/systemd-coredump metadata, GitHub Actions, pinned Playwright 1.61.0.
**Spec:** docs/superpowers/specs/2026-11-16-webkit-crash-journal.md

## Global Constraints

Only the diagnostic collector, its CLI tests and narrow workflow additions are owned. Preserve the original sweep command, assertions, timeouts, engine and failure propagation. No retry or runtime version change. Existing journal only: no core access/creation/policy change or raw sensitive output. Five-second query timeout, 256 KiB raw cap, three records, twelve frames per record and 8 KiB sanitized output. Local small stdlib CLI tests are permitted; all heavy runtime remains held. No subagents, remote mutation or CI polling. You are not alone; preserve all other work and the untracked backend plan.

## Review Focus

- A passing sweep can still contain an allocator abort; collect on both passing and failing WebKit outcomes.
- Raw journal metadata can contain secrets and large bodies; allowlisting and enforced read/output caps are required.
- Diagnostic failure must never erase the original browser exit, hang the job or kill unrelated processes.
- No existing crash record is not proof that no crash occurred.

### Task 1: Build and verify the bounded journal diagnostic

Read the binding spec first and its linked preflight. Work in the supplied marketing integration worktree at the design-only dispatch commit. Own `implementation/marketing/scripts/webkit_crash_journal.py`, `implementation/marketing/tests/test_webkit_crash_journal.py` and only the narrowly described `.github/workflows/ci.yml` additions. Preserve protected `docs/superpowers/plans/2026-11-14-free-public-backend.md` and every sibling SDD workspace.

- [ ] Read test-driven-development/writing-good-tests.md. Add actual CLI tests first, using small temp fixture files and sequential bounded children. Run them against the missing behavior and record intended assertion failures, not unrelated interpreter/fixture errors. Commit the test checkpoint before collector implementation.
- [ ] Implement the minimal fixed-command collector plus offline replay surface, strict output allowlist and bounded child lifecycle. Use the existing observed pinned WebKit paths and actual systemd field formats. Reject unknown/malformed material safely. Preserve empty/unavailable/truncated distinctions and original-browser independence.
- [ ] Observe GREEN for the whole new CLI suite. Add that suite to existing workflow lint. Give the original WebKit step an id and start-time output, keep its Python command and failure result, then run the bounded collector after that step on success or failure under the existing cancellation policy. No new jobs or artifacts are needed; the sanitized small JSON appears in the existing job log.
- [ ] Run AST/actionlint/diff checks; record exact RED/GREEN commands, full outputs, commits and clean owned scope. Write task-1-report.md beside the brief. Hosted journal availability, actual crash attribution and whole CI remain UNRUN until root's one normal candidate run. No push, workflow dispatch, browser run or other-source edits.

## Completion

Task review approves spec, correctness, privacy and lifecycle; one normal hosted capture is inspected with its actual browser result; final whole-branch review and live target/head checks precede any merge. This diagnostic is not a claim that the browser fault was repaired.
