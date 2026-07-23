# SelahCue — Stage-6 Delivery Plan Review (Independent)

Date: 2026-07-23 · Reviewer: Delivery Manager (independent — did NOT author the plan) · Scope: Stage-6 gate before Stage-7 implementation authorisation

## Verdict: PASS WITH CONDITIONS

The delivery plan is sound and may proceed to Stage 7 **subject to the low-cost reconciliations below** (no blocker/critical). MVP requirement coverage is complete, the dependency graph is acyclic and sensibly ordered, the first implementation batch is a coherent, demonstrable, bounded vertical slice, and every epic/story carries the required schema. The conditions are release-tag and mapping-hygiene corrections in the traceability index; none change scope or block foundation work.

Issues by severity: **0 blocker · 0 critical · 2 medium · 3 low.**

## What I checked

Sources: `REQUIREMENTS-TRACEABILITY.md`, `IMPLEMENTATION-READINESS.md`, `SelahCue-PRD.md` §30/§31/§33, and ClickUp tickets (list `SelahCue — Delivery` 901327960792) as the stated source of truth.

**1. MVP coverage (PRD §33 → epic/foundation story).** Verified the **full** 85-FR PRD §33 MVP list (not just a 10-FR spot-check): every MVP FR maps to an MVP epic in the traceability. Sampled tickets confirm the mapping downstream — e.g. Walking-skeleton story `86ajp09c2` (ADR-0001/2/3; NFR-001/002/014) and Mobile-pairing story `86ajp0b0t` (FR-085…093, 097, 098, 174; NFR-016). No MVP requirement is unmapped or dropped. **PASS.**

**2. Later-release (R2–R6) deferral.** All R2–R6 FRs are mapped and explicitly deferred with rationale — none silently dropped. R3/R4/R5/R6 epics enumerate their FRs; R2 FRs are carried as "Later:" rows under the functionally-related MVP epics. Three release-tag/mapping defects found (below). **PASS with conditions.**

**3. Dependency graph (IMPLEMENTATION-READINESS.md).** Traced both the epic-level and 14-story graphs. **Acyclic** at both levels. Topological order is sensible: Foundation is the sole root (blocks all), Mobile is the sink (depends on Presentation + Timers + Scripture + Admin). Story-level: S1 walking-skeleton is root; render-seam gates presentation/stage/timer; persistence gates autosave/serviceplan/scripture; mobile is terminal. No story depends on anything that must ship after it (one cosmetic list-ordering nit, below). **PASS.**

**4. First batch = vertical slice (RISK-001).** The 14 foundation stories are a coherent set, not a grab-bag: they light up the core live loop (service plan → static slide → main output → preview/live → stage display → timer/TIME UP → PD scripture) plus every reliability guarantee (autosave + crash recovery + crash-loop breaker + storage guard, emergency clear/blackout, missing-media/pre-service) and the secure mobile control plane (QR + pinned TLS + RBAC + slide advance). The Stage-7 gate demo (`86ajp0bpn`) is genuinely end-to-end and demonstrable across 3 OSes including force-kill recovery of exact live state. Bounded per RISK-001/AS-6 (small team, foundation-first, core-MVP decomposed at Stage 8/9). **PASS.**

**5. Schema (owner role, requirement IDs, AC, required tests).** Spot-checked epic `86ajp06yv` and stories `86ajp09c2`, `86ajp0b0t` in ClickUp. Each ticket description carries Owner role, Requirements (FR/ADR/NFR IDs), In/Out scope, Acceptance, Tests, Dependencies, and DoD; stories are correctly parented to their epics. **PASS.**

## Gaps / conditions

| # | Sev | Finding | Recommended fix |
|---|-----|---------|-----------------|
| 1 | Medium | **FR-156 mis-tagged MVP.** Traceability lists FR-156 (Local AI-model integrity verification) in the Admin epic's **MVP** requirement row, but PRD §33 classifies it **R3**. MVP ships no local AI model (transcription/detection are R3), so as an MVP acceptance item it is vacuous and pollutes the MVP launch-criteria set. | Move FR-156 to the Admin "Later:" row tagged R3; keep it mapped to the Admin epic. |
| 2 | Medium | **FR-154 dual-release conflict.** Traceability + the Foundation epic ticket list FR-154 (at-rest confidentiality: datastore + captured audio) as **MVP-Foundation**, but PRD §33 classifies it **R3**, violating §33's "every FR maps to exactly one release." The promotion is defensible — SQLCipher datastore encryption ships in foundation story `86ajp09he` and pairing-token custody is MVP (FR-159) — but the conflict is undocumented. | Split FR-154 (datastore-at-rest → MVP; captured-audio-at-rest → R3) **or** add an explicit promotion note in both the PRD and the traceability so the single-release rule holds. |
| 3 | Low | **FR-157 wrong release label.** Grouped under the Admin "Later: …(R3)" tag, but PRD §33 places it in **R2**. Still deferred (not dropped), only mislabelled. | Relabel FR-157 as R2. |
| 4 | Low | **Incomplete R2 mapping surface.** FR-140, FR-141, FR-163, FR-165 are mapped only in the HTML-comment footnote, and there is no R2-epic FR-enumeration section (R2 FRs live only as scattered "Later:" rows). Every requirement is technically accounted for, but R2 mapping is harder to audit than R3–R6. | Add an explicit "R2 · Media & Output Expansion" FR list (mirroring R3–R6) so all 29 R2 FRs have a visible epic row. |
| 5 | Low | **List/graph ordering + ClickUp dependency links.** The batch list numbers Stage display (#9) before Timer foundation (#10), yet the graph edge `S9-timer -> S8-stage` makes Stage depend on Timer; the DAG (which governs sequencing) is still acyclic, but the printed order is misleading. Separately, sampled ClickUp tickets have **empty native dependency links** — the graph lives only in IMPLEMENTATION-READINESS.md. | Renumber Timer before Stage in the batch list; optionally encode the graph as ClickUp blocking relationships for live tracking. |

None of the above blocks Stage-7 foundation work: the first-batch stories (skeleton, persistence, render-seam, CI, design system, autosave, service plan, presentation, stage, timer, scripture, emergency, missing-media, mobile) are unaffected by findings 1–4, which concern later-release tagging in the index.

## Independence statement

I did not author, edit, or contribute to the SelahCue PRD, the requirements-traceability index, the implementation-readiness document, or any ClickUp epic/story reviewed here. This review was conducted independently against the PRD as the requirements baseline and ClickUp as the delivery source of truth. Findings are my own judgement; the verdict reflects verified evidence, not the plan authors' assertions.
