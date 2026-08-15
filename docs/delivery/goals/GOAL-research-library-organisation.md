# Goal Contract — TASK-research-library-organisation

## Identity

- Goal ID: TASK-research-library-organisation
- Parent goal ID: NONE (commissioned research; feeds `TASK-pm-sizing-library-grouping`)
- Title: A citable evidence note exists that answers how established church presentation products let users organise and find items in a large content library
- Role: product-researcher
- Status: VERIFIED_COMPLETE
- Execution engine: goal
- ClickUp task: NONE (see "Dependencies and approvals" — the commissioning note deliberately created no ClickUp item; this research is the §3.1 check it specified)
- Created: 2026-08-15
- Updated: 2026-08-15
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Produce a research note under `docs/research/` that answers, for each of ProPresenter, EasyWorship, Proclaim, OpenLP, FreeShow and MediaShout (plus any further product the evidence warrants), with a source URL and an evidence label per finding: (a) whether the content library has folders/hierarchy, whether it nests, and whether one item can live in more than one folder; (b) whether a many-to-many tag/label/category mechanism exists, whether folders and tags coexist in the same product, and how the vendor explains the division of labour; (c) what non-structural findability affordances exist (search, filter, sort, recency, favourites, smart/dynamic groups); (d) what real users say about coping at scale. The note must state plainly whether the evidence supports folders+tags coexisting without confusion, and whether large-library findability in this domain is usually solved by structure at all.

## Baseline

Verified before work began:

- `docs/product/SIZING-library-grouping.md` §3 commissions exactly this check ("Hands-on competitor check (≤1 day)") and names the sharper signal it wants: forum/support evidence of users duplicating items across folders and complaining about divergence.
- `docs/research/COMPETITOR-MATRIX.md` covers service planning/playlists for six products but has no row, cell, or note on library folders, tags, or collections. §7 records `OBSERVED = 0` — the whole matrix is vendor-page/doc evidence, not hands-on.
- `COMPETITOR-MATRIX.md` §8 classification legend defines OBSERVED / DOCUMENTED / INFERRED / UNKNOWN plus a High/Med/Low confidence qualifier. This note must reuse that legend.
- Proclaim (Faithlife) and MediaShout appear nowhere in the matrix as researched products; MediaShout is named once in §4 only as a market-positioning aside.
- SelahCue itself is unlaunched, so no first-party user evidence about library scale exists (`docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md` §10).

## Inputs and evidence sources

- Vendor documentation and support knowledge bases (renewedvision.com, easyworship.com, faithlife.com/proclaim, manual.openlp.org, freeshow.app, mediashout.com)
- Vendor and community forums, Reddit, Facebook-group threads reachable without authentication
- Third-party tutorials and workflow videos where the library UI is visible or described
- `docs/product/SIZING-library-grouping.md`, `docs/research/COMPETITOR-MATRIX.md` (framing, not evidence about competitors' libraries)

## Scope

### In scope

- External, citable evidence about library organisation and findability in comparable products.
- Explicit separation of Observation, Interpretation, and Implication; no recommendation.

### Non-goals

- Deciding what SelahCue should build, or ranking the work. Priya owns scope and is reassessing in parallel.
- Domain rule modelling for SelahCue's own content (Bianca is doing that in parallel).
- Editing or re-scoring any existing row of `COMPETITOR-MATRIX.md`.
- Purchasing trials, creating accounts, or accessing anything behind a paywall or login.

### Constraints

- Write only under `docs/`. Nothing under `implementation/`. Nothing staged or committed.
- Every finding carries an evidence label from the `COMPETITOR-MATRIX.md` legend and a source URL.
- Where a question cannot be verified, record UNKNOWN. Absence of evidence is not evidence of absence.

### Assumptions and unknowns

- ASSUMED: public documentation reflects current shipping versions. Validation owner: whoever next runs a hands-on trial. Recorded as a limitation in the note.
- UNKNOWN before work: whether any product in the set ships folders and tags simultaneously.

## Dependencies and approvals

- Scope decision: Product Manager (Priya). This note ends at evidence; it does not recommend.
- No ClickUp item exists for library grouping (`SIZING-library-grouping.md` §ClickUp records the deliberate absence). ClickUp MCP is available but creating an item here would pre-empt Priya's scope call, so none is created.

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | The note answers the folders question (exists / nests / multi-home) for all six named products, or records UNKNOWN with the reason | Read-through of the per-product section against the six names | Six products covered, no silent gaps | §1 table rows "Folders over items/media/groupings" + "Item in >1 container"; §2.1–2.7. All six commissioned products plus Quelea covered. Multi-home answered positively for 6 of 7 with verbatim vendor quotes; FreeShow single-home verified at source (the `category` field is a nullable scalar ID, not an array). MediaShout lyric-folder nesting recorded UNKNOWN with sources checked listed | PASS |
| C-002 | yes | The note answers the tags question (many-to-many mechanism / coexistence with folders / how the division is explained) for all six named products, or records UNKNOWN with the reason | Read-through | Six products covered | §1 rows "Many-to-many mechanism" and "Division of labour explained?"; §2. Coexistence found in Proclaim, EasyWorship, FreeShow, OpenLP; division of labour quoted verbatim for Proclaim and EasyWorship, recorded as *not explained* for OpenLP and FreeShow with the specific doc pages checked; MediaShout "no tag mechanism found in ~20 sources — not positively denied"; Quelea contradictory evidence retained | PASS |
| C-003 | yes | The note records non-structural findability affordances (search, filter, sort, recency, favourites, smart groups) per product | Read-through | Present per product or UNKNOWN | §1 rows Search / Recency / Favourites / Smart groups / Declutter, all seven columns populated; per-product detail in §2. "None found" is consistently distinguished from "absent" | PASS |
| C-004 | yes | The note contains user-voice evidence about coping at scale, cited to reachable public sources, and distinguishes it from vendor claims | Read-through + URL presence | At least one user-voice source per major finding in the pain section; vendor claims labelled separately | §3, ~40 cited user statements across 7 subsections, each with URL and date. Vendor statements segregated into §3.9 "The vendor as user-proxy"; §3.0 states the three sampling biases up front | PASS |
| C-005 | yes | Every finding carries an evidence label (OBSERVED / DOCUMENTED / INFERRED / UNKNOWN) and a source URL, matching the `COMPETITOR-MATRIX.md` legend | Grep/read-through for unlabelled assertions | No unlabelled external claim | Label counts: DOCUMENTED 100, OBSERVED 77, UNKNOWN 17, INFERRED 11; 144 source URLs; 64-row evidence index at §7 | PASS |
| C-006 | yes | The note answers the two decision-relevant questions — (1) do folders+tags coexisting work or confuse users, (2) is the pain solved by structure at all — and states the strength of the evidence behind each answer without dressing thin evidence as a verdict | Read-through of the synthesis section | Both answered with explicit confidence and named counter-evidence | §4. Q1 answered in three parts with an explicit "I cannot give you a rate" and retained counter-evidence; Q1a records an unlooked-for finding (query composability); Q2 explicitly **declines to resolve** the vendor-behaviour/user-voice tension and says why. Earlier over-weighting of recency was corrected against user evidence and the correction is stated in the note | PASS |
| C-007 | yes | The note makes no build recommendation and no scope call | Read-through for imperative build language | No "SelahCue should build …" statements | A case-insensitive grep for build-recommendation phrasings ("SelahCue should", "we recommend", "should ship", "must build") returns two hits: a verbatim MediaShout vendor quote (§2.4) and the §5 disclaimer itself. §5 is framed "Implications (not recommendations)" | PASS |
| C-008 | yes | `COMPETITOR-MATRIX.md` existing rows are unmodified; no file outside `docs/` is created or modified; nothing staged or committed | `git status --porcelain` and `git diff -- docs/research/COMPETITOR-MATRIX.md` | Matrix shows no diff; only `docs/` additions; index untouched | `git diff --quiet -- docs/research/COMPETITOR-MATRIX.md` → PASS (no diff); `git diff --cached --name-only` → empty; only two additions, both under `docs/`. Pre-existing `implementation/` untracked files belong to other agents and were not touched | PASS |
| C-009 | yes | Contradictory evidence is retained rather than dropped, and access date + method + limitations are recorded | Read-through of the method and limitations sections | Present | Access date in header; method + "no login or paywall bypassed" in §6; 11-row access-failure table; six open questions; explicit volume note. Contradictions retained rather than resolved: EasyWorship Scripture collections (two vendor sources disagree), Quelea tag strings vs absent code path, the OpenLP link-vs-copy debate where users take both sides | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: criterion read-throughs; `git status --porcelain`; `git diff` on the existing matrix to prove it is untouched; spot re-fetch of the load-bearing URLs so the citations resolve.
- Broader regression verification: none required — docs-only change, CI skips docs-only paths.
- Independent verifier: Product Manager (Priya) at the scope reassessment; any reader must be able to reproduce the synthesis from the source URLs.
- Required environment: local repo + public web access.

## Iteration ledger

### Iteration 1

- Target criterion: C-001 … C-004
- Hypothesis: the six products differ materially in shape — at least one ships folders only, at least one ships tags only, and the market leader ships more than one grouping axis at once; user-voice evidence about scale will be easier to find for the market leader than for the smaller tools.
- Change or investigation: evidence sweep — vendor docs/KB/changelogs and, for the open-source products, public schemas and source; then a forum/community/review sweep for organisation pain. Load-bearing claims re-verified by me independently of the sweep (OpenLP forum JSON API for the two pivotal quotes; `Show.ts` fetched directly for the FreeShow cardinality claims).
- Verifier executed: criterion read-throughs; `git diff --quiet` on the existing matrix; `git diff --cached`; label/URL counts; build-recommendation grep.
- Result: PASS on all nine criteria.
- New evidence, including three findings that contradicted the starting hypothesis:
  1. **The hypothesis was wrong about shape.** No product ships a folder tree over *items*. Where hierarchy exists it sits over the *grouping* object (ProPresenter Group Folders over playlists; FreeShow folders over projects; EasyWorship folders that can hold only collections, never resources).
  2. **Six of seven products let one item live in many containers**, and three vendors say so defensively in their own docs. The folders-vs-tags dichotomy the research question assumes has largely collapsed in this market; the observable failure mode is a many-to-many mechanism *wearing a folder's name* (MediaShout's delete asymmetry, EasyWorship's "stays in the parent").
  3. **Query composability, not the labelling mechanism, is the binding constraint** — OpenLP has the richest labels in the set and its users still hack titles, because its nine search modes are mutually exclusive.
  - Correction made mid-note: an early reading over-weighted recency on vendor-documentation evidence. The user corpus does not corroborate it (one data point, and it is a complaint about recency's *absence*). The note now states "shipped ≠ used" and flags the correction rather than hiding it.
- Decision: complete

## Risks and rollback

- Risk: vendor documentation describes an idealised feature set; what users actually do at scale may differ. Mitigation: user-voice evidence is collected separately and labelled separately from vendor claims.
- Risk: temptation to convert thin evidence into a verdict, which the commissioning note explicitly forbids. Mitigation: C-006 requires stated confidence and named counter-evidence.
- Risk: documentation may describe a version newer or older than what churches run. Mitigation: record version/date where visible; otherwise record as a limitation.
- Rollback or recovery: deliverable is new files under `docs/`; delete to revert.

## Pause and escalation conditions

- Any scope or prioritisation question: escalate to Product Manager (Priya), do not answer.
- Any source requiring login, payment, or terms acceptance: stop, record UNKNOWN, do not proceed.

## Final evaluation

- Validator command: `python3 ~/.claude/skills/goal/scripts/validate_goal_contract.py docs/delivery/goals/GOAL-research-library-organisation.md --completion`
- Validator result: OK (structural, before the first iteration) and OK (completion — "satisfies the Goal Contract schema and all mandatory criteria PASS"), both recorded 2026-08-15.
- Independent verification result: pending Product Manager read. The note is reproducible from its 144 source URLs; the two pivotal citations (the OpenLP developer's four-minute self-correction, and the FreeShow `category` cardinality) were re-verified from primary sources independently of the sweep that produced them.
- Terminal state: VERIFIED_COMPLETE for the research deliverable. The scope decision it feeds is owned by the Product Manager and is deliberately outside this predicate.
- Remaining failed or blocked criteria: none. Six substantive questions remain open and are listed in §6 of the note, ranked by how much each would change a decision; the top one (whether ProPresenter edits propagate across playlists) is unresolved because the vendor's user-guide host returned HTTP 521 on every attempt and the live KB is login-gated.
- ClickUp final evidence comment: N/A — no ClickUp item exists for library grouping. `SIZING-library-grouping.md` deliberately created none, and creating one here would pre-empt the Product Manager's scope call. If the owner wants this research tracked, the right shape is a single backlog task linking both the sizing note and this research note.
