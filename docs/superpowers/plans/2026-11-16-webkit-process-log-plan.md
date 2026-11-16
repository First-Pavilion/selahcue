# WebKit browser process logging plan

Spec: `docs/superpowers/specs/2026-11-16-webkit-process-log.md`.

## Global Constraints

- Own only `.github/workflows/ci.yml`, the existing `Responsive sweep (WebKit)` step. Add only `DEBUG: "pw:browser"` and optionally one explanatory comment.
- Keep all commands, assertion sets, timeouts, browser/version/runner selection, conditions, permissions and other steps unchanged. No retries, environment dumps or broad protocol/DOM logging.
- Existing synthetic loopback job only. No product-fix or behavioral-RED claim. Root owns a single new capture and evidence-led diagnosis.
- No local project runtime under paging hold. Static actionlint/Git only. One source implementer, no subagents, no remote mutations; preserve others' work.

## Task 1: Enable process stderr for the existing WebKit sweep

Read the spec first. Use the controller-prepared branch in `/Users/m.oluwole/.codex/worktrees/selahcue-rust-release-fixes/scph`; root supplies the exact dispatch HEAD. The previous socket plan is complete and its reports archived; do not read or edit sibling workspaces.

1. Inspect the existing step and apply the exact environment entry from the spec. Do not alter command handling or test code.
2. Run existing actionlint and Git diff/whitespace checks. Confirm the single environment value is the only executable configuration change. No tests, installs or local browser launches.
3. Commit the workflow only and write this plan's `task-1-report.md` with exact SHA, preserved failure behavior, static checks and hosted capture UNRUN. Return concise status/commit/checks and release the source slot. No push or CI dispatch.

## Completion

The logging change passes review and required static/current CI checks, its first actual process capture is inspected and archived, and any source claims retain the diagnostic's limited scope. Root independently investigates the crash cause without treating a clean run as a fix.
