---
name: goal
description: Internal bounded execution engine used by /build and specialist skills. Executes a validated Goal Contract toward an explicit completion predicate, records iteration evidence, and returns only a defined terminal state.
user-invocable: false
disable-model-invocation: false
effort: high
version: 3.0.0
---

# Goal — Verifiable Execution Engine

## Mission

Execute one supplied Goal Contract until its finite completion predicate is independently evidenced or a defined terminal stop condition is reached. Never replace the domain specialist; enforce path, bounded iteration, verification, evidence, and honest termination.

## Required inputs

- Goal Contract path under `docs/delivery/goals/`
- Active specialist role
- Active ClickUp task or Build Control task when applicable
- Repository `CLAUDE.md` and relevant nested guidance
- Linked PRD, business rules, design, ADRs, tests, runbooks, and prior evidence

Read `.claude/team/GOAL_EXECUTION_PROTOCOL.md` before execution.

## Preflight

1. Run `python3 scripts/validate_goal_contract.py <goal-contract>`.
2. Refuse substantive work if the contract is missing, invalid, vague, unbounded, or has no verifier per mandatory criterion.
3. Confirm the selected engine is `goal`; if it is `ralph`, return control to the Ralph runner.
4. Confirm scope, non-goals, constraints, dependencies, approvals, maximum iterations, and pause conditions.
5. Set the Goal Contract status to `ACTIVE` and add a ClickUp start comment with goal ID, path, predicate summary, and iteration limit.

## Execution loop

For each bounded iteration:

1. Read the full current contract and prior iteration ledger.
2. Recompute which mandatory criteria are `PENDING`, `FAIL`, or `BLOCKED`.
3. Select the highest-priority unblocked criterion.
4. Ask the active specialist to state one falsifiable hypothesis and the smallest coherent increment.
5. Execute only role-appropriate work inside approved scope.
6. Run the criterion's named verifier in the required environment.
7. Inspect behaviour and output; do not infer success from exit code alone when behavioural evidence is required.
8. Append the attempt, result, evidence, and criterion status to the Goal Contract.
9. Add material evidence or blockers to ClickUp.
10. Re-run the Goal Contract validator.
11. Stop immediately for approval, destructive action, production access, role-boundary decisions, or a `/build` user gate.

## No-progress detection

An attempt is materially different only when it changes at least one of:

- hypothesis;
- evidence source;
- implementation approach;
- diagnostic method;
- dependency or owner input.

After three materially different failed attempts without useful new evidence, return `FAILED_LIMIT` even if the contract allows more total iterations. A new diagnostic that materially narrows the problem may justify continuing within the configured maximum.

## Independent verification

Before `VERIFIED_COMPLETE`:

- invoke the required independent role or verifier;
- rerun all mandatory final checks from a clean or representative state;
- ensure evidence links are accessible and correspond to the current revision/environment;
- ensure no mandatory criterion is `PENDING`, `FAIL`, `BLOCKED`, or `NOT_APPLICABLE` without an approved contract change;
- run `python3 scripts/validate_goal_contract.py <goal-contract>` successfully.

The implementation role cannot independently approve its own final security, QA, PRD audit, or production-release criterion.

## Completion condition

Return `VERIFIED_COMPLETE` only when:

- every mandatory completion criterion is `PASS`;
- every `PASS` includes concrete evidence;
- required independent verification passed;
- the Goal Contract validator exits `0`;
- ClickUp contains the final predicate summary and evidence links;
- no known blocker contradicts the completion claim.

## Terminal outputs

Return exactly one status with a concise evidence summary:

- `VERIFIED_COMPLETE`
- `GATE_REVIEW`
- `BLOCKED`
- `FAILED_LIMIT`
- `ABORTED`

`GATE_REVIEW` is used when a `/build` stage has completed its verifiable work and must pause for the user. It never authorises the next stage.

## Boundaries

- Never weaken criteria to manufacture completion.
- Never extend scope without Product Manager and gate traceability.
- Never cross a user gate, production approval, destructive operation, or external-access boundary.
- Never mark the active ClickUp task `Done` when independent review or another stage remains.
- Never suppress failed checks, flaky results, or untested areas.

## Handoff

Update the Goal Contract and ClickUp with:

- terminal status;
- final predicate table;
- verifier commands/tools/environments;
- evidence paths and links;
- failed attempts and diagnostics;
- residual risks and unknowns;
- exact next owner or gate action.
