# Goal Contract — TASK-pm-sizing-library-grouping

## Identity

- Goal ID: TASK-pm-sizing-library-grouping
- Parent goal ID: NONE
- Title: A sizing note exists that lets the owner decide whether library grouping is worth scheduling now
- Role: product-manager
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: NONE (deliberate — per tasking, a ClickUp item is created only if the conclusion is "worth scheduling now"; the sizing note records the conclusion)
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Produce `docs/product/SIZING-library-grouping.md`: an evidence-labelled sizing and prioritisation note for grouping in the presentation library (folders vs tags vs derived groups), answering the many-to-many question from repo evidence or declaring it unsettled with the research that would settle it, sizing 2–3 scoped options, and ranking the work against `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md`. This is a sizing exercise — no solution internals, no code, no design.

## Baseline

Verified before work began:

- `selahcue-operator/src/deck_library.rs` — `list()` is a flat, name-ordered library; `search()` is the only findability tool; `DeckMeta` = `{id, name, slides}` (no timestamps).
- `selahcue-core/src/plan.rs` — `ServicePlan` with ordered `PlanItem`s is the per-service grouping; `ItemContent::Deck { deck_id }` links plans→decks.
- `selahcue-data/src/migrations.rs` — `service_plan(id, name, next_id)`; no created/updated/date columns on plans or decks; migrations forward-only.
- `selahcue-lan/src/protocol.rs:172` — "the host stays deck-blind — Approach A"; `grep -rln deck implementation/mobile/selahcue_controller/lib/` returns nothing: deck library is operator-local and off the wire.
- PRD FR-003 defines the library flat + searchable (<300 ms at ≤5k items); no FR/ADR/decision covers folders/tags/collections (grep of PRD, `docs/design/`, DECISION-LOG, OPEN-DECISIONS).
- No ClickUp item covers library grouping (per parent-agent search; not re-verified here).

## Inputs and evidence sources

- `docs/business/PERSONAS.md` (explicitly un-validated / INFERRED)
- `docs/research/COMPETITOR-MATRIX.md`
- `docs/product/prds/SelahCue-PRD.md` (FR-003, FR-005, MVP boundary §32)
- `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md`
- Code baselines listed above

## Scope

### In scope

- The sizing note deliverable, with every claim labelled Verified / Inferred / Assumed / Unknown.

### Non-goals

- Any design or implementation; any PRD amendment; any ClickUp status change; any ClickUp creation unless the verdict is "schedule now".

### Constraints

- Write only under `docs/`. Touch nothing under `implementation/`. No git stage/commit/stash/reset (large owner WIP in tree).

### Assumptions and unknowns

- ASSUMED: parent-agent code findings (flat `list()`, operator-local library) — spot-re-verified above, now Verified.
- UNKNOWN: whether one deck needs multiple homes (the folders-vs-tags decider) — the note must either settle it from evidence or specify the research that would.

## Dependencies and approvals

- Scheduling decision: owner. The note ends at that gate; it does not approve itself.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/product/SIZING-library-grouping.md` exists and contains: user problem + evidence, many-to-many verdict (or "unsettled" + the settling research), 2–3 scoped options with relative effort and what each does/doesn't solve, a recommendation, and an explicit rank against PRODUCT-GAP-AUDIT-2026-08-14 | Read-through against this list | All six elements present | The note: §2 problem, §3 verdict (unsettled + settling research), §6 options A/B/C, §7 recommendation, §8 rank | PASS |
| C-002 | yes | Every load-bearing factual claim in the note carries an evidence label and a repo path (or is marked Inferred/Assumed/Unknown) | Read-through | No unlabelled project facts | Note evidence appendix — 11 rows, each labelled with source | PASS |
| C-003 | yes | No file outside `docs/` created or modified; nothing staged or committed | `git status --porcelain` diff vs session start | Only `docs/` additions; index untouched | Session additions: `?? docs/product/SIZING-library-grouping.md`, `?? docs/delivery/goals/GOAL-pm-sizing-library-grouping.md`; all pre-existing entries unchanged, nothing staged | PASS |
| C-004 | yes | ClickUp action matches the verdict: item created only if "schedule now", and the note states which happened | Note §ClickUp + absence/presence of created task | Consistent | Verdict "real but not next" → no item created; note §ClickUp states this and offers the trigger-task shape if the owner wants it | PASS |

## Verification plan

- Focused verification: criterion read-throughs + `git status --porcelain`.
- Broader regression verification: none required (docs-only change; CI skips docs-only).
- Independent verifier: the owner, at the scheduling decision. `validate_prd.py` not applicable — the deliverable is a sizing note, not a PRD.
- Required environment: local repo.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: repo evidence (personas, competitor matrix, PRD, schema) is sufficient to size the options but NOT to settle the many-to-many question
- Change or investigation: evidence sweep (personas, competitor matrix, PRD greps, `deck_library.rs`, `plan.rs`, `migrations.rs`, `protocol.rs`, mobile lib, design docs, decisions) then author the note
- Verifier executed: read-through against C-001 element list
- Result: PASS — note authored with all six elements; many-to-many declared unsettled with a two-part settling plan
- New evidence: no timestamps exist on decks/plans (corrects the "derived groups need zero new data" assumption); host is deck-blind by design (protocol.rs:172)
- Decision: complete

### Iteration 2 (same day — owner responded; coordinator requested reassessment)

- Target criterion: C-001, C-002, C-004 (re-verified after in-place update)
- Hypothesis: the owner's response (folders+tags; browse-surface rationale; "Library" name) is genuinely new evidence that changes the cheapest-relief analysis but not the ranking of the full grouping build
- Change or investigation: §9 addendum added to the note in place (audit trail preserved; header pointer added). Corrections/decisions: (a) §2 corrected — the pain is now observed n=1 (owner-as-user), no longer merely anticipated; (b) stated pain reframed as browse-surface → new smallest option "Library View slice" (S, no schema change, inline filter + derived ordering); (c) folders+tags compound sized L with a two-system confusion risk, held pending Rowan/Bianca (both in flight — not duplicated here); (d) "Library" naming verified consistent with PRD FR-003 / `DeckLibrary`, sole disambiguation = Design 2.0 "Media Library" (`DESIGN-2.0-HANDOFF.md:177`); (e) recommendation revised: value = yes; S slice worth scheduling on owner approval; §8 ranking of the full build stands
- Verifier executed: read-through of updated note against C-001 element list; evidence appendix extended (+4 labelled rows); `git status --porcelain` re-checked (same two docs files, nothing staged)
- Result: PASS — all criteria hold after the update; C-004 still consistent (no ClickUp item — owner's message is a question, not an approval; first ticket shape documented in §9.6)
- New evidence: first observed user report of the pain (owner, n=1); search is modal-only today (`deck_library.rs:25-29`)
- Decision: complete

## Risks and rollback

- Risks: personas are un-validated — any grouping-shape conclusion drawn from them would be weak; the note therefore declares the shape question unsettled rather than manufacturing confidence.
- Rollback or recovery: deliverable is a single new docs file; delete to revert.

## Pause and escalation conditions

- Scheduling decision and any research commissioning: owner.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-pm-sizing-library-grouping.md --completion`
- Validator result: OK (structural + completion) — recorded 2026-08-15
- Independent verification result: pending owner read — the note defers the scheduling decision to the owner by design
- Terminal state: VERIFIED_COMPLETE (deliverable criteria); the scheduling decision itself is owner-gated and intentionally outside this predicate
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: N/A — no ClickUp item (verdict is "real but not next"; creation was conditional on "schedule now")
