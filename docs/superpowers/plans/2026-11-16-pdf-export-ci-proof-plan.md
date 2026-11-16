# Operator PDF export CI proof plan

Spec: `docs/superpowers/specs/2026-11-16-pdf-export-ci-proof.md`.

## Global Constraints

- Own only `.github/workflows/ci.yml` in the existing Linux operator job. Keep source, tests, locks, frozen evidence, other jobs, permissions, OS tier and existing bounds unchanged.
- Use the existing exact single ignored Rust authoring test and its independent oracle. No layout assertion changes or test-spelling mirrors. Preserve actual failures and mark unexecuted work UNRUN.
- Exact parser versions pypdf6.21.4/pdfplumber0.11.9, Python3.14, binary distributions only, isolated runner-temp environment; Poppler144dpi; synthetic fixture artifacts only,20MiB maximum/seven-day retention. Five-minute parser and proof steps within existing30-minute job.
- No local project runtime under paging hold. Static actionlint/syntax/Git checks only. Root owns marker, remote execution, artifacts, visual acceptance, reviews and merge.
- One global source implementer. You are not alone; preserve others' edits and sibling plans. No subagents or remote mutations.

## Task 1: Execute the existing PDF oracle in hosted operator CI

Read the binding spec first. Use `/private/tmp/selahcue-operator-dependency-fix-20261116`, branch `codex/operator-dependency-fix-20261116`; root supplies the exact design-only dispatch HEAD. HarfRust caller has already been repaired in1afa6026; do not touch that source or its separate plan workspace.

1. Read only the existing operator job and its setup/gate conventions plus the authoring test and embedded independent oracle. Confirm the test binary and exact qualified test name against source. The current workflow has no invocation; ordinary Test ignores it. No behavioral RED is claimed for this wiring.
2. Implement the spec's Linux parser setup before Format, Poppler dependency, exact ignored-test proof after default Test, bounded render/hash/size steps and successful-proof artifact upload. Preserve all existing conditions and downstream gates. No YAML-text regression test or unrelated cleanup.
3. Run read-only actionlint on the workflow and static diff/whitespace checks. Do not run project tests or install dependencies locally. Fix only issues introduced by this task. Record actual commands and results; report all hosted/parser/PDF/native results as UNRUN until root supplies them.
4. Commit only the workflow. Write this plan workspace's `task-1-report.md`: exact commit and changed scope, producer/consumer paths, step conditions and failure propagation, artifact contents/bounds, marker ownership and verification limits. Return status, commit, one-line checks and concerns; release the source slot. No push/CI dispatch or subdelegation.

## Completion

Hosted normal and Windows gates for the repaired dependency composition pass, the existing oracle and artifact upload execute, all nine pages receive visual acceptance, required task/domain reviews and final whole-branch review pass. Root verifies live refs and merge composition before the authorized merge. Historical compiler/layout/platform evidence retains its exact original scope.
