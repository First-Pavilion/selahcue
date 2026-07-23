# AI Development Team Workflow

## Purpose

Coordinate specialist Claude skills through nested, bounded, evidence-driven goals with ClickUp as the delivery source of truth and `/build` as the manually invoked controller.

## Hard execution invariant

No `/build` stage or specialist task begins without a valid Goal Contract. Every assignment uses exactly one engine:

- bundled `goal` skill by default; or
- Ralph Loop when explicitly selected and available.

Read `.claude/team/GOAL_EXECUTION_PROTOCOL.md`. Unstructured “start working” execution is prohibited.

## Goal tree

`Build Goal → Stage Goal → Specialist Task Goal → Independent Verification Goal`

Each child goal has its own finite completion predicate. A parent cannot be complete while a required child remains incomplete, failed, or blocked without an authorised disposition.

## Bounded evidence loop

For each goal:

1. Validate the Goal Contract.
2. Inspect the active ClickUp task, linked artefacts, repository guidance, code, tests, runtime, and prior evidence.
3. Select one failing criterion.
4. Plan the smallest coherent increment that could change that criterion.
5. Execute through the selected goal engine.
6. Run the named verifier and inspect actual behaviour.
7. Record the iteration and evidence in the Goal Contract and ClickUp.
8. Recompute the whole predicate.
9. Return `VERIFIED_COMPLETE`, `GATE_REVIEW`, `BLOCKED`, `FAILED_LIMIT`, or `ABORTED`.

## Standard gated lifecycle

`Bootstrap → Product Discovery → Architecture & Design → ClickUp Plan → Implementation Batches → Independent Verification → Release Readiness → Release & Closeout`

The `/build` skill pauses after every stage. A `continue` response authorises only the next Stage Goal. Implementation may contain multiple batch gates.

## Evidence labels

- **Verified:** directly observed in code, tool output, authorised running product, or authoritative artefact.
- **Inferred:** conclusion supported by evidence but not directly observed.
- **Assumed:** temporary premise with a validation plan.
- **Unknown:** unresolved and potentially decision-relevant.

## Conflict authority

1. User-approved product requirement defines intended outcome.
2. Approved business rules define domain behaviour.
3. Approved ADRs define cross-cutting technical decisions.
4. Approved design artefacts define experience intent.
5. ClickUp defines delivery ownership, state, dependencies, and approved scope decomposition.
6. Repository conventions define local implementation patterns.
7. Tests and runtime behaviour provide evidence; they do not automatically override approved intent.

Route conflicts to the owning role and return to the earliest affected `/build` gate. Do not edit a Goal Contract's completion criteria to conceal the conflict.
