# HarfRust caller port plan

Spec: `docs/superpowers/specs/2026-11-16-harfrust-caller-port.md`.

## Global Constraints

- Own only `implementation/desktop/crates/selahcue-operator/src/notes_export.rs` and the task report. One call changes to default ShapeOptions; preserve empty feature behavior, unscaled font units and all surrounding conversion/render/save code.
- Preserve dependency pins/locks, tests, workflow and frozen proof inputs. Current existing checks and independent PDF/Windows validation remain controller-owned merge gates.
- No local project execution, imports, compiler, install, service, resource probe, secret/provider request or remote mutation under the paging hold. Static source and Git checks only.
- One global source implementer. No subagents. You are not alone; preserve others' work, do not revert unrelated edits or stage other paths.

## Task 1: Port the existing shape call without changing PDF units

Read the binding spec, then `/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/release-evidence/open-pr-review/pr395-cody-review.md`, `pr395-quinn-review.md`, and their linked actual compiler/API evidence. Work in `/private/tmp/selahcue-operator-dependency-fix-20261116`, branch `codex/operator-dependency-fix-20261116`; root supplies the exact design-only dispatch SHA. Do not read the full unrelated release plans.

1. Confirm the existing owning source and pinned HarfRust API/default against the evidence. The archived E0308 is actual build-gate RED with zero assertions, and the source inputs relevant to it are unchanged.
2. Change exactly `self.face.shape(buffer, &[])` to `self.face.shape(buffer, harfrust::ShapeOptions::default())`. No scale, custom feature, test, dependency or workflow edit.
3. Read the surrounding shaping/unit conversion and statically verify the single-line diff, clean whitespace, sole path and unchanged unrelated checkout state. Commit only that source path.
4. Write this workspace's `task-1-report.md` with exact source/commit, API and unit reasoning, actual historical compiler RED and current UNRUN commands. Root owns current hosted GREEN, PDF oracle/visual inspection, Windows gates and independent reviews. Return only status, commit, one-line checks and concerns; release the source slot. No push or CI dispatch.

## Completion

The minimal port is implemented, current owning checks and required PDF/Windows evidence pass, all material findings are addressed and re-reviewed, final whole-branch review passes, and live refs and merge composition are verified before the authorized merge. This plan's scratch stays until these gates are complete.
