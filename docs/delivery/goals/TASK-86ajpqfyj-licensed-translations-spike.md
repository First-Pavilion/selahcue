# Goal Contract — TASK-86ajpqfyj-licensed-translations-spike

## Identity

- Goal ID: TASK-86ajpqfyj-licensed-translations-spike
- Parent goal ID: STAGE7-foundation
- Title: The licensing route for each owner-requested copyrighted translation (NIV, NLT, AMPC, NKJV, TPT, MSG) is researched with cited evidence, and a pluggable translation-provider architecture (ADR) exists so licensed versions can be added without re-architecting
- Role: product-researcher (+ software-architect for the ADR)
- Status: IN_PROGRESS
- Execution engine: goal
- ClickUp task: https://app.clickup.com/t/86ajpqfyj
- Created: 2026-07-25
- Updated: 2026-07-25
- Maximum iterations: 8
- Independent verification required: yes

## Objective

Close the story's Track 2: the owner wants NIV, NLT, AMPC, NKJV, TPT, and MSG. All are copyrighted, so this spike answers HOW each can legally reach SelahCue (aggregator API vs direct publisher licence vs user-supplied), at what constraints (offline/caching/attribution/cost where public), and designs the provider seam that makes them addable.

## Baseline

Verified as of 2026-07-25:
- `docs/research/LICENSING-REGISTER.md` (2026-07-23/24) already documents: NIV/NLT/NKJV/MSG/AMP = copyrighted, **API-only or user-supplied, never bundled**; ESV API non-commercial-only terms OBSERVED; **API.Bible** two tiers OBSERVED (open-access PD/CC vs copyright-protected; Starter = ≤3 licensed versions non-commercial; commercial = paid; **FUMS** usage reporting; caching/offline of licensed text **not granted by default**); NLT api.nlt.to free tier non-commercial.
- Gaps: **TPT** (The Passion Translation) is absent from the register; **AMPC** (Amplified Classic) is only covered as "AMP"; no research on **commercial licensing routes/costs** for a church presentation app; no evidence on **what comparable products** (ProPresenter, EasyWorship, Proclaim, MediaShout…) do; no provider-seam ADR (highest ADR = 0016).
- `selahcue-scripture` is bundled-PD-only (gzipped TSV, lazy OnceLock decode); the wire advertises the host's translation list (7ae), so remote/licensed providers must slot behind the same host-side surface.

## Inputs and evidence sources

- ClickUp 86ajpqfyj (owner's requested list) + `docs/research/LICENSING-REGISTER.md` + `selahcue-scripture` code.
- Public web: publisher permissions pages (Biblica/Zondervan, Tyndale, Lockman, Thomas Nelson/HarperCollins Christian, NavPress, BroadStreet/Passion & Fire), docs.api.bible, comparable products' documentation/stores.

## Scope

### In scope

- Per-translation licensing dossier (rights holder, available routes, constraints, cost where public, confidence class per the register's discipline).
- Aggregator-vs-direct-vs-user-supplied comparison, incl. comparable products' observed approaches.
- ADR-0017: a pluggable `TranslationProvider` seam (bundled PD offline + licensed remote providers; licence-honouring caching; attribution; usage-reporting hook; honest degradation when offline/unlicensed).
- Register updates (TPT + AMPC rows) + follow-up ClickUp tickets.

### Non-goals

- Implementing any provider (follow-up work).
- Legal advice or signing licences (owner + counsel).
- Bundling any copyrighted text (already ruled out).

### Constraints

- Research discipline per the register: OBSERVED/DOCUMENTED/INFERRED/UNKNOWN + confidence + access dates; no paywall/auth bypass; marketing claims labelled.
- The ADR must fit the existing host-side architecture (host advertises translations; clients never offer codes the host denies).

### Assumptions and unknowns

- ASSUMED: public pages document enough to classify each route; anything not public is recorded UNKNOWN with the exact contact path. VALIDATION OWNER: the research itself.

## Dependencies and approvals

- Owner decision + counsel required before any licence is signed (escalation, not a blocker for the spike).

## Completion predicate

All mandatory rows must be `PASS` for `VERIFIED_COMPLETE`.

| ID | Mandatory | Criterion | Verifier | Expected result | Evidence | Status |
|---|---|---|---|---|---|---|
| C-001 | yes | Each of NIV, NLT, AMPC, NKJV, TPT, MSG has a dossier row: rights holder, viable route(s) for a commercial church presentation app, constraints (offline/caching/attribution), cost where public — each claim classed OBSERVED/DOCUMENTED/INFERRED/UNKNOWN with source + access date | doc review | 6 complete rows, no unclassified claims | docs/research/LICENSED-TRANSLATIONS.md §1 (all six rows, classed + dated 2026-07-25) | PASS |
| C-002 | yes | Routes compared: API.Bible commercial tier vs direct publisher licences vs user-supplied, including at least 3 comparable products' observed approaches, with a recommendation for SelahCue | doc review | comparison + recommendation present, cited | dossier §2–§4 (4 aggregators; 7 comparable products; phased recommendation) | PASS |
| C-003 | yes | ADR-0017 defines the pluggable TranslationProvider seam (bundled offline + remote licensed; licence-honouring cache policy; attribution surface; usage-reporting hook; honest offline/unlicensed degradation) consistent with the host-advertised-translations architecture | ADR review vs selahcue-scripture + protocol | ADR complete and consistent | ADR-0017 (Status: Proposed; zero client changes — rides the 7ae advertised-translations surface) | PASS |
| C-004 | yes | LICENSING-REGISTER gains TPT + AMPC rows (dated); follow-up ClickUp tickets exist for the owner licensing decision + provider implementation | register diff + ClickUp | rows added; tickets created + linked | register §1 updated (TPT, AMPC, AMP/MSG refinements, 2026-07-25); DECISION 86ajpzb09 + STORY 86ajpzb0c (waiting_on the decision) | PASS |
| C-005 | yes | Independent verification: the dossier's load-bearing claims adversarially checked against their sources; discrepancies fixed | Workflow verify pass `wf_e9bd0579-d32` (6 fact-checkers re-fetching primary sources) | claims verified or corrected/downgraded | 4 CONFIRMED + 2 CORRECTED (0 unverifiable); corrections applied — headline: **NIV commercial exclusion on API.Bible verified** (reroutes NIV to direct Biblica); 14-day cache = recommendation not conflict; ProPresenter free-list corrected. CODE-REVIEW-batch7aq.md | PASS |

Allowed criterion statuses: `PENDING`, `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`.

## Verification plan

- Focused verification: doc completeness review against the criteria.
- Broader regression verification: register discipline preserved (classes, dates); no claim contradicts the existing register without noting why.
- Independent verifier: a Workflow adversarial verify pass over the dossier's load-bearing claims (re-fetching sources).
- Required environment: web access (WebSearch/WebFetch) via Workflow agents.

## Iteration ledger

### Iteration 1

- Target criterion: C-001, C-002
- Hypothesis: a 4-lens research fan-out (TPT+AMPC rights; API.Bible commercial specifics; direct publisher routes; comparable products) yields citable answers for every route.
- Change or investigation: Workflow fan-out; synthesize the dossier.
- Verifier executed: Workflow research fan-out `wf_b038fdfb-839` (4 web lenses, 140 tool calls) + doc synthesis.
- Result: **C-001 & C-002 PASS** — all six translations mapped with primary-source evidence (TPT permissions page, Lockman 1,000-verse policy incl. the electronic-retrieval cap, Biblica Express-vs-Standard licensing, HCC digital routing, Tyndale/NavPress print-eBook-only gratis grants, API.Bible Pro pricing/FUMS/cache rules, 7 comparable products). One cross-lens contradiction (TPT on YouVersion: OBSERVED-live vs reported-removed) retained per register discipline, resolved in favour of the live observation.
- New evidence: the dominant industry model is per-translation one-time in-app purchase ($15–$39); API.Bible is the only lawful aggregator for any of the six; NLT/MSG gratis grants are print/eBook-only (stricter); Lockman's policy is 1,000 verses (correcting an older 500-verse secondary claim).
- Decision: iterate

### Iteration 2

- Target criterion: C-003, C-004
- Change or investigation: authored ADR-0017 (TranslationProvider seam — Proposed, acceptance gated on the owner's route decision); updated the register (TPT + AMPC rows, AMP/MSG refinements); created DECISION `86ajpzb09` + implementation STORY `86ajpzb0c` (waiting_on the decision) under 86ajpqfyj.
- Verifier executed: doc/ADR consistency review vs `selahcue-scripture` + the 7ae wire surface; ClickUp task creation confirmed.
- Result: **C-003 & C-004 PASS**.
- Decision: iterate (C-005 verification pass running — `wf_e9bd0579-d32`, 6 adversarial fact-checkers re-fetching primary sources)

### Iteration 3 — verification + corrections

- Target criterion: C-005
- Change or investigation: verify pass returned **4 CONFIRMED + 2 CORRECTED, 0 unverifiable**. Corrections applied to the dossier + register: (1) **NIV is verifiably EXCLUDED from commercial use on API.Bible** (upgraded from an untraced Low-confidence snippet to OBSERVED/High) — NIV's only commercial route is the direct Biblica Standard Publishing License; recommendation §4 rerouted accordingly. (2) The 14-vs-30-day cache "conflict" is not one: 30 days is the binding T&C rule, 14 is a docs recommendation. (3) API.Bible per-translation tiers pinned ($10 @ 5k users → $250 @ 100k+; overage "may be" $1/1k). (4) ProPresenter: 67 free translations (not all PD), $15/licence per computer confirmed, "one-time" unsupported. Confirmed as written: Lockman 1,000-verse policy (+ not-for-sale slide nuance), NLT print/eBook-only gratis grant, TPT status incl. the live YouVersion page, Biblica Express-vs-Standard licensing.
- Verifier executed: `wf_e9bd0579-d32`; corrected docs re-read.
- Result: **C-005 PASS** — every load-bearing claim now primary-source-verified or explicitly corrected.
- Decision: gate-review (all mandatory criteria PASS)

## Risks and rollback

- Risks: pricing/terms often behind contact-us walls → recorded UNKNOWN with contact path (acceptable per acceptance). Rollback: docs-only spike; no code.
- Rollback or recovery: git-versioned.

## Pause and escalation conditions

- Licence signing / cost commitment → owner + counsel (escalate at the gate).

## Final evaluation

- Validator command: `python3 scripts/validate_goal_contract.py docs/delivery/goals/TASK-86ajpqfyj-licensed-translations-spike.md --require-complete`
- Validator result: PASS (5/5 mandatory)
- Independent verification result: verify pass `wf_e9bd0579-d32` — 4 CONFIRMED + 2 CORRECTED, corrections applied
- Terminal state: GATE_REVIEW (licence signing is the owner's DECISION task 86ajpzb09 — never this goal's)
- Remaining failed or blocked criteria: none
- ClickUp final evidence comment: posted on 86ajpqfyj
