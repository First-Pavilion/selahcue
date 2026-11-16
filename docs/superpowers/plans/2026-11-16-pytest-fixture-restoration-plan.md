# Pytest connection fixture restoration plan

Spec: `docs/superpowers/specs/2026-11-16-pytest-fixture-restoration.md`.

## Global Constraints

- Own only `implementation/api/tests/test_usage_retained_history_load.py`, limited to the two affected test functions and any necessary existing import adjustment. Preserve all measurement helpers and unrelated tests.
- Concrete default wrapper; connected before original state capture; local monkeypatch context; exact original deque identity and flag restored before Django teardown; a real proxy query after restoration.
- Preserve parameter values 4 and 5, maxlen 4, exact capacity error, original exception identity, inner false flags and the exception control's existing query while patched. No skips, retries, production, dependency or workflow changes.
- Local runtime remains held. Root owns hosted CI, refs, review publication and merge. Static reads, syntax/AST parsing without project imports and Git metadata are permitted.
- One global source implementer; no subagents. You are not alone: preserve others' work and do not revert unrelated edits.

## Task 1: Restore the real database wrapper before fixture teardown

Read the binding spec first, then the complete source preflight at `/Users/m.oluwole/.codex/visualizations/2026/11/14/01a1d9e8-f42c-7583-89ee-386ea3167ba8/designs/pytest-fixture-restoration-preflight-20261116.md`, and its actual candidate failure and predecessor success evidence. Work in `/private/tmp/selahcue-pytest-fixture-fix-20261116` on `codex/pytest-fixture-restoration-20261116`; root supplies the exact design-only dispatch HEAD. The candidate includes the original pytest/Strawberry stack and merged current-main WebKit diagnostics; those reviewed inputs are not yours to edit.

1. Read the two test functions, capture helper and relevant Django/pytest source references. Confirm the saved actual failure matches the unchanged test source; do not manufacture a new RED or run local project code.
2. Apply the minimal concrete-wrapper and scoped-restoration correction described by the Spec. Retain every existing behavioral assertion. Add the post-context identity, flag and normal SELECT/fetch checks. Avoid shared helper abstraction for these two short fixture scopes unless duplication creates an actual correctness problem.
3. Statically confirm original measurement helpers and unrelated tests are unchanged. Check syntax and whitespace, self-review error paths and restoration on assertion/operation exceptions, and commit only the owned test file.
4. Write the full report to this plan workspace's `task-1-report.md`, with exact commit and source diff, actual historical RED versus current UNRUN evidence, all retained/new checks and commands. Return only status, commit, one-line test summary and concerns; release the source slot. Do not push or dispatch CI.
5. Root runs normal hosted API/marketing CI and verifies all owning cases and the full formerly unreached suffix. Required reviews follow; original worker handles requested corrections through scoped re-review, then final whole-branch review before authorized merge.

## Completion

The actual regression is corrected, all existing and added observations run on the exact candidate, full CI passes, material review findings are resolved and re-reviewed, and final live refs/merge composition are verified. The original failed dependency trials remain archived.
