# Goal Contract — TASK-ba-domain-library-organisation

## Identity

- Goal ID: TASK-ba-domain-library-organisation
- Parent goal ID: NONE (commissioned analysis; runs alongside `TASK-pm-sizing-library-grouping` and `TASK-research-library-organisation`)
- Title: A domain-rule model exists for library folders and tags that states every entity relationship, lifecycle rule, and edge case with an explicit decision or an explicitly-routed open question
- Role: business-analyst
- Status: DRAFT
- Execution engine: goal
- ClickUp task: NONE — searched `deck library` and `library folders tags grouping presentation organisation` in the SelahCue — Delivery list; no task covers library grouping. `docs/product/SIZING-library-grouping.md` §8 deliberately created none. No shadow backlog created.
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Produce `docs/product/DOMAIN-library-organisation.md` containing: an entity model relating Folder, Tag, Deck and Plan; a numbered, testable business-rule catalogue in which every rule is either decided with a rationale or explicitly marked as a product decision routed to the Product Manager; an edge-case table with expected behaviour per case; and a short list of the questions that block schema design.

## Baseline

Verified from the repository before work began:

- The library is flat: `DeckLibrary::list()` returns all decks name-sorted; `search(query, limit)` matches deck name and slide text. No grouping concept exists. (`implementation/desktop/crates/selahcue-operator/src/deck_library.rs:172-184,334-381`)
- Decks are keyed in memory by a stable `DeckId` but **persisted by NAME** — `name` is the `deck` table primary key, and `save_one` upserts `ON CONFLICT(name)`. The library therefore forces globally unique deck names via a silent `(n)` suffix (`uniquify`). (`selahcue-data/src/deck_repo.rs:38-77`; `deck_library.rs:11-12,105-153,462-481`)
- Plan items reference decks by id only — `ItemContent::Deck { deck_id, slide_count }` — and resolution is an injected existence probe, `unresolved_content(deck_exists, media_exists)` (FR-007). Nothing in the link carries a name or a location. (`selahcue-core/src/plan.rs:86-89,425-442`)
- `PlanItem.title` is an independent free-text field; it does not follow the linked deck's name. (`selahcue-core/src/plan.rs:174-193`)
- RBAC has 11 `Permission` variants and none concerns the deck library; no `Command` variant lists, browses, or organises decks. The library is unreachable over the wire. (`selahcue-lan/src/rbac.rs:30-96,99-120`)
- Persistence is best-effort: a failed DB open runs the library in memory with `is_persistent() == false`. (`deck_library.rs:8-12,100-102`)
- Migrations are forward-only, tracked by `user_version`, append-only. No timestamp columns exist on plans or decks. (`selahcue-data/src/migrations.rs:1-28`)
- FR-139 plan-bundle export/import (`86ak0qn15`, planning/todo) carries plan + item content references + media. It does not carry decks.
- `86ajy02zq` (host-authoritative deck-link resolution) is planning/todo and explicitly conditional on decks moving host-side or multi-operator.

## Inputs and evidence sources

- `docs/product/SIZING-library-grouping.md` (Priya — framing and prior verified findings)
- `docs/delivery/goals/GOAL-research-library-organisation.md` (Rowan — scope boundary)
- `selahcue-operator/src/deck_library.rs`, `selahcue-data/src/deck_repo.rs`, `selahcue-data/src/migrations.rs`
- `selahcue-core/src/plan.rs`, `selahcue-core/src/media.rs`
- `selahcue-lan/src/rbac.rs`, `selahcue-lan/src/protocol.rs`
- ClickUp: `86ak0qn15`, `86ajy02zq`, epic `86ajp072p`

## Scope

### In scope

- Entity model and cardinality for Folder, Tag, Deck, Plan.
- Lifecycle, referential-integrity, naming, move and default-state rules, each testable.
- The folders-vs-tags division-of-labour rule, or an explicit finding that it cannot be stated crisply.
- Interaction with plan links, deck-link resolution, and search.
- RBAC confirmation (not assumption) and the trigger condition that would make it live.
- Migration default state, and multi-device / import-export consequences.

### Non-goals

- Scope, priority, or scheduling. Priya owns those and is reassessing in parallel.
- Competitor or user evidence. Rowan owns that in parallel.
- Schema design, table/column definitions, API shapes, or implementation.
- Deciding product calls. These are marked and routed, never invented.

### Constraints

- Write only under `docs/`. Nothing under `implementation/`. Nothing staged or committed.
- Every claim about current behaviour carries a file path and line reference.
- Evidence labels: Verified / Inferred / Assumed / Unknown.

### Assumptions and unknowns

- UNKNOWN: whether one deck genuinely needs more than one home. `SIZING-library-grouping.md` §3 records this as unsettled. Validation owner: Rowan's research + Priya's decision. This model must therefore hold rules for both shapes rather than assume one.
- ASSUMED: no deck export/import exists today. Validation: repository sweep (criterion C-007).

## Dependencies and approvals

- Priya (Product Manager) — owner of every rule marked `PRODUCT CALL`. Status: reassessing scope in parallel; not blocking this model.
- Rowan (Product Researcher) — external evidence on folders/tags coexistence. Status: in progress; not blocking.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | `docs/product/DOMAIN-library-organisation.md` exists and contains an entity model stating cardinality for every Folder/Tag/Deck/Plan relationship, and answers whether a folder is a property or a container | Read the document | An entity section with explicit cardinalities and a stated answer | doc §2.2 cardinality table (7 relationships); §2.3 `RULE-LIB-ENT-01..04` answers "both, and only single-valuedness generates rules" | PASS |
| C-002 | yes | Nesting is addressed with a depth position and a bounded-memory rationale consistent with the repository's no-unbounded-growth rule | Read; compare with existing `MAX_*` house style | A depth rule, a cycle rule, and cap rationale citing existing caps | doc §2.4 `ENT-05` (cap, enforced create/move/load), `ENT-06` (no cycles), `ENT-07` (repair on load); §5 bounds table. Cap house style verified: `MAX_PLAN_ITEMS=500` `plan.rs:258`, `MAX_MEDIA_ASSETS=1000` `media.rs:19`, `MAX_DECK_SLIDES=500` `present/src/deck.rs:33`, `MAX_SAVED_THEMES=256` `app/src/controller.rs:228` | PASS |
| C-003 | yes | Every lifecycle question in the tasking has a rule: folder delete, deck delete under plan reference, rename collision, move, duplicate names across folders, unfiled state | Read; check each against the tasking list | Six lifecycle areas each with a numbered, testable rule | doc §4.1 `FLD-01..05`; §4.2 `DEL-01..03`; §4.3 `NAME-01..06`; §4.4 `MOV-01..05`; §4.5 `UNF-01..03`; §4.6 `EMP-01..04`. 65 distinct rule ids total | PASS |
| C-004 | yes | The folders-vs-tags division-of-labour rule is either stated crisply and testably, or the failure to state it is recorded as a finding with its predicted consequence | Read | A stated rule plus an honest assessment of whether it survives this domain | doc §3: `DIV-01` (where-vs-what) and `DIV-02` (the testable form: "if a second value could ever be correct it is a tag"), then §3.2 `FINDING-LIB-01` — the rule is statable but fragile because a library has several independent single-valued axes and a tree encodes one; §3.3 `FINDING-LIB-02..04` record the predicted confusion | PASS |
| C-005 | yes | Interaction rules cover plan-item indifference to deck location, plan behaviour on folder move, search spanning folders, and the deck-link resolution path — each traced to code | Read; verify each citation resolves | Four rules, each with a file:line citation | doc §6.1 `REF-01..04` (`plan.rs:86-89,425-442,174-193`; `deck_library.rs:192,313,390,410`); §6.2 `SRCH-01..06` (`deck_library.rs:334-381`, `28-40`). All citations re-read and confirmed | PASS |
| C-006 | yes | RBAC is confirmed from `rbac.rs` rather than assumed, and the condition under which a role could see a filtered library is stated | Read; cross-check `Permission` enum and `required_permission` | A confirmation with citation plus an explicit future trigger condition | doc §7: eleven `Permission` variants read from `rbac.rs:30-96`, none library-related; no `Command` exposes decks (`rbac.rs:99-120`, `protocol.rs:172`). `RBAC-02` states no role sees a filtered library because none sees the library; `RBAC-03` states the trigger; `RBAC-04` records that no per-user identity exists | PASS |
| C-007 | yes | Migration default state and multi-device/import-export consequences are stated, including whether grouping travels with an exported deck, grounded in the verified export surface | Read; repository sweep for export/import | An honest default-state rule and export/import rules citing FR-139 evidence | doc §8 `MIG-01..04` + `FINDING-LIB-06`; §9 `XFER-01..07` + `FINDING-LIB-07`. Export surface verified: no `deck_export`/`deck_import` in the Tauri command list (only `deck_import_image`, media); `Export deck (.json)…` is design-only (`PRESENTATIONS-LIBRARY-spec.md` §5); FR-139 bundle scope from ClickUp `86ak0qn15` | PASS |
| C-008 | yes | An edge-case table exists with at least 15 cases, each with an expected behaviour and a decided/product-call marker | Count rows; check every row has both columns populated | ≥15 rows, no blank outcome cell | 30 rows; 0 rows with an empty outcome cell (awk check over §10) | PASS |
| C-009 | yes | Every rule that is a product decision rather than a domain constraint is explicitly marked and routed to Priya; no invented product answers | Read; scan for `PRODUCT CALL` markers | Product calls marked and collected in one place | 11 inline `PRODUCT CALL` markers; §11 collects 12 routed decisions (P1–P12) with the reason each is a product call | PASS |
| C-010 | yes | A short list of schema-blocking questions exists, and it leads with the deck-name-uniqueness consequence | Read | A blocking-questions section; name uniqueness is first | doc §12: seven questions; Q1 is deck-name uniqueness scope, with the consequence that per-folder names mean decks can no longer be keyed by name on disk (`deck_repo.rs:38-51` PK = name) | PASS |
| C-011 | yes | No file was created or modified outside `docs/`, and nothing was staged or committed | `git status --porcelain` | Only untracked additions under `docs/`; no staged entries | `?? docs/delivery/goals/GOAL-ba-domain-library-organisation.md` and `?? docs/product/DOMAIN-library-organisation.md` only; `git diff --cached --name-only` returns 0 entries | PASS |
| C-012 | yes | No duplication of Priya's sizing or Rowan's research: the document contains no scope ranking and no competitor evidence claims | Read; cross-check against both goal contracts | No effort sizing, no priority verdict, no competitor findings | Grep for effort/option/rank/competitor-product terms returned no matches. Rowan's contract explicitly cedes "domain rule modelling for SelahCue's own content" to this goal; the one cross-reference to Priya's note (§8.2) is labelled as such and defers scope | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: read the produced document against C-001…C-010; confirm every code citation resolves to the claimed file and line.
- Broader regression verification: `git status --porcelain` proves the write boundary (C-011); cross-read both sibling goal contracts to prove non-duplication (C-012).
- Independent verifier: Priya (Product Manager) for product-call routing correctness; Aria (Software Architect) if any rule is read as prescribing schema.
- Required environment: local repository read access only. No build, no test run — this goal changes no code.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-010 (the document does not yet exist; one authoring pass covers the set, then each is verified individually)
- Hypothesis: the domain rules can be derived from the existing code's established behaviour (id-keyed links, name-keyed persistence, degrade-don't-destroy on missing content) plus the repository's bounded-memory rule, without inventing product policy.
- Change or investigation: read `deck_library.rs`, `deck_repo.rs`, `plan.rs`, `rbac.rs`, `protocol.rs`, `migrations.rs`, `media.rs`; searched ClickUp for existing tickets; swept for export/import surfaces; authored the document.
- Verifier executed: document read-back against C-001…C-010; re-read of every inherited citation; row/marker counts over §10 and §11; `git status --porcelain`; `git diff --cached --name-only`; cross-read of both sibling goal contracts.
- Result: all twelve criteria `PASS`. One internal contradiction was found during read-back and fixed before completion: `RULE-LIB-BND-01` ("nothing silently reassigned") contradicted `RULE-LIB-ENT-07` (load-path repair reattaches an orphaned folder to root). Resolved by scoping `BND-01` to user-initiated operations and adding `RULE-LIB-BND-03`, which states why refusal is unavailable on a load path and bounds repair to structure only — no load-path repair may delete or alter a deck.
- New evidence: (1) deck persistence is name-keyed (`deck` table PK, `ON CONFLICT(name)`), which makes per-folder duplicate names a structural re-keying rather than an additive change — the lead schema-blocking question. (2) `PRESENTATIONS-LIBRARY-spec.md` §5 already decides the deck-delete rule (allow, ⚠ in-plan warning, plan item shows missing, undo-backed), so `RULE-LIB-DEL-01` extends shipped design rather than inventing policy. (3) `DeckId` is a per-library counter from 1, so a foreign `deck_id` imported onto a non-empty library can resolve to an unrelated local deck — recorded as `FINDING-LIB-07`, pre-existing and outside this feature. (4) No hierarchy exists anywhere in the codebase; folders would be its first tree, so there is no depth-cap precedent to follow.
- Decision: complete

## Risks and rollback

- Risks: (1) drifting into schema design, which is Aria's remit — mitigated by stating rules as constraints a schema must satisfy, never as tables or columns; (2) drifting into scope or priority, which is Priya's — mitigated by C-012; (3) manufacturing an answer to the unsettled one-home-or-many question — mitigated by holding rules for both shapes and marking the choice as a product call.
- Rollback or recovery: the deliverable is a single new untracked document under `docs/`. Deleting it restores the prior state exactly; no code, schema, or ClickUp state is touched.

## Pause and escalation conditions

- A rule turns out to require a product policy decision that changes the meaning of other rules — escalate to Priya rather than assume, and record the dependency between rules.
- Evidence in the repository contradicts a claim in `SIZING-library-grouping.md` — report the contradiction rather than silently overriding a sibling artefact.
- Any rule would require changing code, schema, or ClickUp to validate — stop; that is outside this goal.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-ba-domain-library-organisation.md`
- Validator result: `OK (structural)` — exit 0.
- Independent verification result: **not yet performed.** The deliverable is an analysis document, so the meaningful independent checks are Priya confirming the twelve routed product calls are genuinely hers (§11) and Aria confirming no rule reads as prescribing schema. Both are recommended before the model is used to design anything. Every factual claim is independently checkable from the citations in the evidence appendix.
- Terminal state: `VERIFIED_COMPLETE` for the analysis deliverable, with the independent review above outstanding as a recommendation rather than a gate — no code, schema, or delivery state depends on it yet.
- Remaining failed or blocked criteria: none.
- ClickUp final evidence comment: not applicable — no ClickUp task exists for this analysis (see Identity), and none was created, since scope and ticketing are Priya's per the tasking constraints. Findings return to the commissioning agent.
