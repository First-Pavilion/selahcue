# Workflow cache-save coverage — 17tnw2b1wvd

Task: https://app.clickup.com/t/17tnw2b1wvd. Branch: `codex/17tnw2b1wvd-cache-coverage`.
Initial baseline: `c0325d52e809847fac141a605b74a7e6d7de7021`; integrated current main `b3ae75f824fe8e43b18836d3d661dc996dce98bc` before final verification. The uv migration remains intact. No workflow, installer or application source is changed by this ticket.

## Observable behavior

The checker follows repository-local reusable workflow calls and local composite actions, carrying the root caller's event context through nested calls. An unsafe Rust or Flutter cache reports the caller, job/step and reached metadata file. It never downloads remote actions, executes workflow code or evaluates expressions.

Normal `pull_request` Rust cache saves require the existing canonical main-ref comparison, optionally surrounded by balanced outer parentheses, or literal `false`. `pull_request_target`, `workflow_run` and `issue_comment` use a default-branch ref; a ref-only comparison cannot distinguish those PR-like runs. Those paths must disable Rust saving with `save-if: false` and leave Flutter caches off. This is intentionally conservative: a main-saving workflow can be split from those event paths. No such workflow exists at the inspected baseline, and no live workflow is rewritten here.

Calls retain the caller's context rather than adopting a called file's independent triggers. Local paths are repository-bounded after symlink resolution. Missing/malformed targets, call cycles and excessive graph depth/size fail closed. The traversal bounds are 32 nested files and 256 distinct target files per root workflow, with repeated targets memoized. Manual-only workflows remain outside this PR-like cache policy; existing installer main-only dispatch rules remain unchanged.

Malformed YAML now produces one filename/line/column diagnostic and exit 1 without a parser traceback. Invalid workflow/job/step container shapes needed by this traversal also produce actionable diagnostics.

## Completed verification

Local macOS, Python 3.9.6 and existing PyYAML 6.0.3. All reported commands completed; no verifier subprocess remains at handoff.

| Check | Actual result |
| --- | --- |
| Original checker baseline | 118 existing cases and six workflows/nineteen jobs pass |
| New on-disk fixtures against original checker | exit 1; reusable/composite and default-ref event bypasses reproduce; harmless grouping rejects and malformed YAML prints traceback |
| Final `check_workflows.py --self-test` | exit 0; all 118 existing cases plus 39 actual CLI fixtures pass |
| Final `check_workflows.py` after uv main integration | exit 0; six workflows/twenty jobs pass, including uv's restricted main-only dependency submission job |
| Handler-removal proof | exit 0; nine independent scratch mutants make the real committed `--self-test` gate fail |
| `check_ci_minutes.py --self-test` and normal checker | exit 0; existing runner/tier/alarm policies pass |
| `check_visual_audit_ci.py` | exit 0; all20 existing ordered path and browser-gate controls pass |
| Python syntax compile with task-owned temporary bytecode cache | exit 0 |
| Standalone module import and normal CLI, without the test module beside it | exit 0; current workflow controls pass |
| `actionlint .github/workflows/*.yml` | exit 0 |
| `git diff --check` | exit 0 |

The39 CLI fixtures cover unsafe and guarded reusable/composite chains, nested Rust/Flutter behavior, each default-ref event directly and through calls, explicit disabled saves, zero-change manual exemption, harmless versus unsafe expressions, both action metadata extensions, non-composite local metadata, missing/non-reusable targets, cycles/path escape/depth bounds, malformed syntax and invalid container shapes. Assertions run the actual checker CLI over disposable on-disk trees; no local fixture dispatches a GitHub workflow.

The nine proof mutations remove reusable traversal, composite traversal, each of the three default-ref event handlers, grouping normalization, YAML error handling, cycle detection and explicit-disabled handling respectively. Each mutant is checked by the exact production self-test entry point, not an expected-error mock. The first proof attempt intentionally stopped at a non-unique mutation anchor after catching three handlers; the anchor was narrowed to the exact event constant, and the complete proof was rerun successfully. An initial syntax compile hit macOS's external bytecode-cache sandbox path; rerunning with an explicit task-owned temporary cache completed successfully. Neither initial process is represented as a passing command.

Three serial normal-check observations on the shared local host were0.2480s,0.1760s and0.1557s. One complete118-plus 39 self-test observed2.3405s. These are small local observations rather than a hosted latency guarantee; the normal checker performs no child process or network operation, while its self-test launches bounded CLI fixtures. Each fixture subprocess has a15-second timeout.

## Boundaries and recovery

Remote reusable workflows/actions, renamed action forks, non-composite implementation scripts and other cache APIs remain review responsibilities. This change extends only the established Rust/Flutter cache policy; it does not claim coverage of setup-uv, setup-node or every Actions cache mechanism. More complex boolean expressions remain unsupported; only balanced outer grouping around the exact existing comparison is accepted. No arbitrary expression interpreter or new package is introduced.

Revert this isolated checker commit to recover the previous gate. No production state, service configuration, secret, installed artifact or user checkout file changed. No packaging workflow, deployment or provider operation was run.

## Remaining integration gates

Root owns independent Cody, Shadow, Quinn and Vera reviews, actual current-source CI, source/target freshness, merge into main and verified QA readback. Separate Home harness ticket17tnw2bcadw remains a CI integration dependency where applicable; no gate waiver or QA claim is made here. ClickUp connector daily quota is exhausted; root owns authenticated UI status/evidence updates, including the saved/read-back In Progress start comment.

## Primary behavior references

- https://docs.github.com/en/actions/reference/workflows-and-actions/contexts
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations
- https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax
