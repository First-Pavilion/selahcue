# Goal Execution Protocol

## Purpose

Every `/build` stage and every specialist assignment must run toward an explicit, machine-checkable or independently observable completion condition. Work is not complete because an agent says it is complete, because a command exited successfully, or because many files changed.

This protocol is mandatory. A role must not begin substantive work without an active Goal Contract.

## Supported execution engines

Use exactly one engine for each active goal:

1. **Bundled `goal` skill — default.** Use the repository skill at `.claude/skills/goal/SKILL.md`.
2. **Ralph Loop — optional alternative.** Use when the user explicitly requests Ralph, project guidance selects Ralph, or the bundled goal runner is unsuitable and Ralph is installed.

Engine selection order:

1. An explicit user instruction for the current goal.
2. A project-level setting in `CLAUDE.md` under `Goal execution mode`.
3. The bundled `goal` skill.

If the user explicitly requires Ralph and Ralph is unavailable, stop with the exact installation or connection blocker. Do not silently switch engines. If no explicit engine is required, fall back to the bundled `goal` skill.

## Goal hierarchy

Use nested goals rather than one vague instruction:

- **Build goal:** the complete `/build` initiative.
- **Stage goal:** one `/build` stage between user gates.
- **Task goal:** one specialist's bounded assignment, normally tied to one ClickUp task.
- **Verification goal:** an independent review, QA, security, or release check.

A parent goal cannot be complete while a required child goal is incomplete, failed, or blocked without an explicit, authorised disposition.

## Goal Contract

Create a Goal Contract before execution at:

```text
docs/delivery/goals/<goal-id>.md
```

Use `.claude/team/GOAL_CONTRACT_TEMPLATE.md`.

The contract must contain:

- unique goal ID and parent goal ID when applicable;
- active role and execution engine;
- ClickUp task or Build Control link;
- baseline/current state;
- one observable objective;
- scope, constraints, assumptions, and non-goals;
- dependencies and authorised tools/environments;
- a finite completion predicate;
- one verifier and expected result per criterion;
- evidence locations;
- independent-verification requirement;
- maximum iterations;
- pause, escalation, and abort conditions.

Run:

```bash
python3 scripts/validate_goal_contract.py docs/delivery/goals/<goal-id>.md
```

before the first iteration and before claiming completion.

## Completion predicate rules

Every mandatory criterion must be:

- **Boolean:** it can evaluate to `PASS` or `FAIL`.
- **Observable:** another person or agent can inspect the result.
- **Bounded:** it does not depend on endless improvement.
- **Mapped:** it names a verifier, expected result, and evidence location.
- **Independent where needed:** high-risk and final-release claims cannot rely only on the implementation agent.

Good criteria:

- `pytest tests/billing/test_refunds.py -q` exits `0` and all 14 tests pass.
- An unauthorised tenant receives `404` for another tenant's invoice in an integration test.
- Every `FR-*` requirement is linked to at least one ClickUp task or documented deferral.
- The production smoke test passes and error rate remains below the approved threshold for the observation window.

Invalid criteria:

- The feature looks good.
- The code is clean.
- Everything works.
- Tests were added.
- The agent believes the task is finished.

## Bounded execution loop

For each iteration:

1. **Read:** active Goal Contract, ClickUp task, linked artefacts, repository guidance, current code/runtime, and prior iteration evidence.
2. **Select:** the highest-priority failing criterion that is not blocked by another owner.
3. **Hypothesise:** state what small change or investigation should move that criterion toward `PASS`.
4. **Execute:** perform the smallest coherent role-appropriate increment.
5. **Verify:** run the named verifier and inspect actual output or behaviour.
6. **Record:** append the attempt, evidence, result, and changed criterion status to the Goal Contract and ClickUp.
7. **Evaluate:** recompute the full completion predicate.
8. **Decide:** iterate, hand off a child goal, stop at a `/build` gate, or enter a terminal state.

An iteration must produce new evidence. Repeating the same action with the same assumptions is not a new attempt.

## Ralph Loop requirements

When Ralph is selected:

- Supply the full Goal Contract, not only the task title.
- Configure Ralph with the contract's maximum iteration count.
- Use the completion predicate and verifier results as the stop condition.
- Persist each iteration in the Goal Contract and ClickUp task.
- Do not accept a completion phrase or worker self-report without running the verifiers.
- Do not allow Ralph to cross a `/build` user gate, production approval gate, destructive-operation approval, or role boundary.
- Stop after three materially different failed attempts without new evidence even if the configured maximum is higher, unless the latest attempt produced a new diagnostic that justifies another bounded attempt.

## Bundled `goal` skill requirements

When the bundled `goal` skill is selected:

- Invoke it with the Goal Contract path, active role, and ClickUp task.
- It owns the iteration ledger and predicate evaluation.
- The specialist owns domain decisions and artefacts, not the runner.
- The runner must return `VERIFIED_COMPLETE`, `BLOCKED`, `FAILED_LIMIT`, or `GATE_REVIEW`; it may not return a vague success state.

## Terminal states

- `VERIFIED_COMPLETE`: every mandatory criterion is `PASS`, evidence is recorded, required independent checks passed, and the validator exits successfully.
- `GATE_REVIEW`: the stage's verifiable work is complete and `/build` must pause for the user's gate decision.
- `BLOCKED`: progress requires a decision, access, dependency, or approval owned elsewhere.
- `FAILED_LIMIT`: the bounded attempts were exhausted without satisfying the predicate.
- `ABORTED`: the user or authorised owner terminated the goal.

Only `VERIFIED_COMPLETE` satisfies a task completion predicate. `GATE_REVIEW` satisfies a stage's pre-gate execution but does not authorise the next stage.

## Anti-gaming rules

- Do not weaken a criterion after work starts merely to obtain `PASS`; route scope changes through Product Manager and the current `/build` gate.
- Do not replace behavioural verification with mocks when the criterion requires integration or end-to-end evidence.
- Do not mark a criterion `PASS` when its verifier was skipped, flaky, partially executed, or run in the wrong environment.
- Do not hide known failures in follow-up tasks and call the original goal complete unless the approved scope explicitly permits that deferral.
- Do not let the same agent independently approve its own high-risk security, QA, release, or PRD-audit claim.

## ClickUp evidence

The active ClickUp task receives:

- goal ID and Goal Contract path;
- selected engine and maximum iterations;
- start-state predicate summary;
- material iteration evidence;
- blocker or scope-change comments;
- final predicate table and terminal state;
- links to code, PRs, tests, screenshots, logs, dashboards, designs, ADRs, and runbooks.

The repository Goal Contract is execution evidence, not a duplicate ticket.
