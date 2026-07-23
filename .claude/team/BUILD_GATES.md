# `/build` Stage Gate Contract

At the end of every `/build` stage, output this structure and stop.

## Gate <number> — <stage name>

**Terminal state:** GATE_REVIEW | BLOCKED | FAILED_LIMIT | ABORTED

**Execution engine:** goal | ralph

**Goal IDs:** Build `<id>` → Stage `<id>` → Child goals `<ids>`

**Iterations:** <used>/<maximum>

### Stage goal

State the goal interpreted for this stage.

### Specialists invoked

List each skill and its concrete contribution.

### Completion predicate

List every mandatory criterion with `PASS`, `FAIL`, or `BLOCKED`, its verifier, and evidence. Do not summarise away failed rows.

### Verified outcomes

List observable results with repository, ClickUp, test, design, runtime, or tool evidence.

### Artefacts

List created or changed repository paths and external artefact references.

### ClickUp changes

List the Build Control task, epics/tasks created or updated, dependencies, owners, and status changes. Do not expose opaque internal IDs unless useful; prefer task titles and links.

### Decisions

List decisions made, decision owners, and rationale.

### Risks and unknowns

Separate Verified risks, Assumptions, Unknowns, and Blockers.

### Intentionally not done

State what is deferred to later stages so the user understands the boundary.

### Recommendation

State the next stage or the exact refinement required.

Respond with exactly one of:

- `continue`
- `refine: <specific changes>`
- `pause`
- `abort`

The Stage Goal must be updated to `GATE_REVIEW`, `BLOCKED`, `FAILED_LIMIT`, or `ABORTED` before output. The assistant must end the response after this gate. No additional specialist invocation, file change, or ClickUp update occurs until the next user message.
