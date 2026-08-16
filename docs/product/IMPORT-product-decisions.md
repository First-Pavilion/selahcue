# SelahCue — Presentation import: product decisions (design §17)

Date: 2026-08-15 · Role: /product-manager (Priya) · Type: product decisions — policy values, not architecture
Answers: `docs/architecture/IMPORT-presentation-design.md` §17 (P1–P12) + Sana's RR2 report-loudness call
Inputs: design v2.0 (Aria) · `docs/security/THREAT-MODEL-presentation-import.md` v1.1 (Sana) · ADR-0024 / ADR-0025 · `docs/product/DOMAIN-library-organisation.md` (Bianca)
ClickUp: **blocked this session** — the MCP connection is rate-limited (~23 h). Intended records are specified in §15 and must be created when the connection recovers; nothing was substituted locally.

Owner-settled scope is not re-litigated here: .txt / .pptx / clipboard; blank-line slide separator; pptx text + notes + embedded images; partial import with a report; JPEG decode in scope (P1 — resolved).

Kenji reads this to set policy values. Architectural constraints already fixed by Aria (§11.2 A–E: no silent rename at import; `adopt_with_policy`; `Replace` preserves `DeckId`; `Replace` refused while live/staged; name = hygienised file stem) are taken as given and none is reopened.

---

## 1. P6 — Collision default: **prompt on collision; Keep both is the focused default; no prompt otherwise**

**Decision.** When the imported deck's name does not collide, import proceeds with no prompt — the common case stays one action. When it collides, a dialog is shown **before** parsing (the name is the file stem, so the collision is knowable at file-pick time and the prompt costs no waiting) offering exactly three actions:

- **Keep both** — the focused default (Enter). The copy states the resulting name: *"'Sunday Service' already exists. Add this as 'Sunday Service (2)'?"* The suffix survives as a mechanism but never as a surprise.
- **Replace** — updates the existing deck in place (§2 below). Never the focused default. Disabled, with the reason shown, while the target deck is live or staged.
- **Cancel** — nothing happens.

The chosen policy is passed explicitly to `adopt_with_policy` and re-validated at commit time (live/staged state may have changed during the parse).

**Rationale.** Silent `(2)` is the one option that always picks "keep both" invisibly and produces the sprawl the library is already weak at (Bianca P5; owner-observed browse pain, `SIZING-library-grouping.md` §9.1); a modal on *every* import would tax a time-pressed volunteer, but a prompt **only on collision** appears exactly when intent is genuinely ambiguous — and Enter never destroys anything.

**Kenji's interim default ("always create new, never overwrite"): confirmed as the fallback, changed as the shipped behaviour.** `KeepBoth` remains the correct behaviour on every path where the dialog does not exist yet, and the correct focused default once it does. What changes: v1 does not ship silent suffixing at the import boundary — the collision dialog is part of v1 scope, not a follow-up.

**v1.**

## 2. P7 — Replace ships in v1: **yes**

**Decision.** `Replace` is offered in the v1 collision dialog, under all of Aria's §11.2 constraints (in-place update preserving `DeckId`; refused while live/staged). The dialog names what will be replaced ("Replace 'Sunday Service' — 24 slides"). Not required for v1: a plan-impact count ("used in N plans") in the dialog — plan links survive Replace *by design*, so the count is context, not a safety gate; add it as a follow-up alongside the library card's "In a plan" chip work. A Replace undo (keeping the previous content) is a follow-up, not a v1 gate — the deliberate dialog plus the live/staged refusal are the v1 mitigations.

**Rationale.** Replace is the entire fix for the weekly re-import workflow; without it the volunteer's most common intent ("I fixed the source") has no correct path and sprawl continues, just with a prompt — and the destructive risk is bounded by the dialog being explicit, never default, and never possible against the deck on the audience screen.

**v1** (dialog + Replace). Follow-ups: plan-count in dialog; Replace undo.

## 3. P9 — Bianca's P4/P5: uniqueness scope deferred; silent `(n)` stops at import now, library-wide as separate scope

- **P4 (global vs per-folder name uniqueness): defer.** Global uniqueness stands. This is the folders re-keying question (Bianca §12 Q1) and folders are not scheduled (`SIZING-library-grouping.md` — real but not next). **Trigger:** the library-grouping scope decision; Q1 must be answered before any schema there.
- **P5 (silent `(n)` renaming): direction approved — stop it; delivered in two scopes.** Import (this feature) stops it via §1's dialog, in v1. The library-wide change — create/rename in the workspace refusing with *"A presentation called 'Week 1' already exists"* instead of silently suffixing (Bianca `RULE-LIB-NAME-02`) — is approved as direction but is **separate scope with its own ticket**; import does not wait for it and Kenji's blast radius stays inside the import dialog.

**Rationale.** Import made P5 urgent only at the import boundary; forcing a library-wide behaviour change into this feature couples an in-flight build to an unscheduled one.

**v1** for the import boundary; **follow-up ticket** for library-wide; **deferred** for P4.

## 4. Report loudness (Sana RR2) — two lossy tiers, with a concrete escalation predicate

**Decision.** Three presentation tiers, driven by the `ImportReport`:

1. **Lossless** (`is_lossless()` true) — auto-dismissing `role="status"` toast. A clean import must feel clean. (As designed.)
2. **Partial — informational** (lossy, below the threshold) — toast + one-line summary + collapsed expandable panel, exactly Aria §10.3, with one change: it does **not** auto-dismiss; it stays until the operator dismisses it. Missable losses may not time out on their own.
3. **Partial — material (intrusive)** — the panel opens **pre-expanded**, warning-styled, and requires explicit dismissal; the copy leads with what is missing, not what succeeded (*"2 slides and 6 of 8 images are missing from this import"*), with the per-item recovery hints of §10. Still non-blocking — Aria's "never a modal between the user and their deck" stands; the deck is usable behind the panel.

**The threshold — a partial import is material when the congregation could see wrong or missing content that preview alone won't reveal.** Concretely, escalate to tier 3 when ANY of:

- a slide the author meant to show did not arrive: any `SkippedItem` of kind `UnreadablePart`, `DoctypeRejected`, or `LimitReached(Slides)`;
- `Notice::SlideOrderInferred` is present — wrong order is invisible in preview and worse than any single drop (design §7.6);
- any `Truncation` of `BodyLine`/`BodyLines` — visible slide text was cut;
- image loss exceeds **25%** of the images the deck references (dropped ∕ (dropped + imported), where dropped = the `Image*`, `ExternalImage`, `MediaCommitFailed`, `LibraryFull`, `LimitReached(Images/Pictures)` kinds);
- `skipped_overflow > 0` — more than 100 skipped items means the deck is grossly unrepresentable.

Everything else is tier 2: hidden slides, charts/tables/SmartArt, fonts, nested containers, title/notes truncations, `EncodingReplaced` (U+FFFD glyphs are self-evident in the first preview, unlike order), control-char strips.

Suggested shape: `ImportReport::severity() -> {Lossless, Partial, Material}` beside `is_lossless()`, so the predicate is tested in the pure crate rather than re-derived in the webview. Uma owns the visual design of the two lossy presentations.

**Rationale.** The cost of a missed drop is paid on Sunday in front of a congregation, so losses that preview cannot reveal (order, absent slides, gutted imagery) must be unmissable — but a volunteer who sees an intrusive panel for every skipped transition will learn to dismiss all of them, so intrusiveness is spent only where preview is blind.

**v1.**

## 5. P2 — pptx tables: **skip and report**

Flattening collapses columns and can silently change meaning on the audience screen; an honest *"1 table skipped"* preserves trust. **Defer** flatten-to-text as an option; trigger: user evidence that tables carry text people actually need imported. **v1** (skip+report).

## 6. P3 — text import: **first line is the title**, both .txt and clipboard, no v1 toggle

`FirstLineIsTitle` is the default for both text sources — one splitter, one behaviour, matching comparable tools and the `Slide { title, body }` shape; a title-less slide renders worse under a theme that reserves a title region. The `TextOptions` parameter stays so this is a one-line change. No dialog toggle in v1 — every added control taxes the volunteer flow; a mismatch (e.g. pasted lyrics) is visible in the first preview. **Trigger to add the toggle:** feedback that lyric pastes look wrong. **v1.**

## 7. P4 — hidden pptx slides: **skip and report**

Users hide slides deliberately; importing them puts unwanted content one arrow-key from the audience screen. Report copy includes the recovery: *"3 hidden slides skipped — unhide them in PowerPoint to include them."* **v1.**

## 8. P5 — persisted import provenance: **defer**

v1 keeps the report session-scoped plus the `tracing` log (it reaches the diagnostics bundle, so "what was dropped last week" is answerable in support escalations). Do not take a forward-only schema table (`import_provenance`) before its consumer exists. **Trigger:** approving P8, or the first real support case needing week-later answerability. Note P8 depends on this.

## 9. P8 — re-import detection by source identity: **defer**

Name match is the v1 heuristic — cheap and honest. Source-identity detection needs provenance (P5, deferred). **Trigger:** P5 landing.

## 10. P11 — CMYK/YCCK dropped-and-reported: **confirmed, accepted**

I accept the user-visible gap; it is not flagged to the owner. Converting without the embedded ICC profile risks plausible-but-wrong colour up to photo-negative on the audience screen — silently wrong output in front of a congregation is categorically worse than a visible, recoverable skip, and the decision is reversible later (a CMYK+ICC path can be added without unwinding anything). Report copy must carry the recovery hint: *"CMYK images aren't supported — re-save the image as RGB (in most tools: export for web/screen)."* If drop-report telemetry or support cases later show CMYK is common in our users' decks, that evidence reopens this with Rowan sampling real decks (design §20 already notes this). **v1** (drop + report with recovery copy).

## 11. P10 — PRD coverage and delivery structure: **yes to both**

Import gets PRD requirements — every shipped feature maps to FRs and this one currently maps to none (Verified in the design §3). I own a PRD amendment adding FRs for: the three sources, the partial-import + report model (including the §4 severity tiers), the collision dialog behaviour, and the supported/dropped image matrix; `scripts/validate_prd.py` re-run after. The amendment lands **before the feature's QA gate** so QA verifies against requirement IDs, not the design doc. Delivery structure per design §18: one epic, stories for stages 1, 2, 3a, 3b, 4 — see §15. **v1 (process obligation).**

## 12. P12 — acceptance of Sana's residual risks RR1–RR6: **routed to the owner — this genuinely needs him**

Risk acceptance belongs to the product owner (Sana §10 says so explicitly, and RR1's conditional acceptance requires committing a scheduled milestone for the ADR-0016 out-of-process decode worker — a scheduling commitment only the owner can make; the acceptance *lapses* if that milestone is dropped).

**My recommendation to the owner:** accept all six as written — RR2 is discharged by §4 above; RR3/RR4/RR6 are accepted as stated; RR5 with its RTL-milestone revisit trigger; **RR1 on Sana's exact terms**, which means (a) a ClickUp task for the ADR-0016 worker with a committed milestone is created at build time (§15), and (b) if no JPEG decoder crate satisfies her §7 constraint, JPEG waits for the worker and v1 ships PNG-only images — the design keeps that stage severable, so nothing else slips.

**Blocked on owner** — everything else in this document proceeds meanwhile; only the feature's *merge* takes this acceptance as a gate (Sana §10).

## 13. Policy values at a glance (Kenji's table)

| Policy | Value |
|---|---|
| Collision behaviour | Dialog on collision only; no prompt when the name is free |
| Dialog actions | Keep both (focused default) · Replace · Cancel |
| Keep-both copy | States the resulting `(n)` name before it happens |
| Replace in v1 | Yes — in-place, `DeckId` preserved; disabled with reason while target live/staged; never focused |
| Interim policy until the dialog exists | `KeepBoth` (Kenji's current interim stands as fallback) |
| Silent `(n)` at the import boundary | Does not ship |
| Text layout default | `FirstLineIsTitle` (both .txt and clipboard); no v1 toggle |
| pptx tables | `SkipKind::Table` — skip + report |
| Hidden slides | `SkipKind::HiddenSlide` — skip + report |
| CMYK/YCCK | Drop + report, with RGB re-save recovery copy |
| Report, lossless | Auto-dismissing status toast |
| Report, partial | Persistent toast + collapsed panel (no auto-dismiss) |
| Report, material | Panel opens expanded, warning-styled, explicit dismiss; predicate in §4 |
| Provenance table / source-identity re-import | Deferred (triggers in §8/§9) |

## 14. Decisions deferred, with their triggers (so "defer" is auditable)

| Call | Trigger that reopens it |
|---|---|
| P4 name-uniqueness scope | Library folders/grouping scheduled (Bianca §12 Q1 first) |
| Library-wide end of silent `(n)` | Its own follow-up ticket; not gated on import |
| P5 provenance persistence | P8 approval, or first week-later support case |
| P8 source-identity re-import | P5 landing |
| Table flattening option | User evidence tables carry needed text |
| Text-layout dialog toggle | Feedback that lyric pastes look wrong |

## 15. ClickUp records — specified here, blocked by rate limit at time of writing

Searched before specifying: no existing task covers presentation import (workspace search, 2026-08-15, 0 results — corroborates design §3). To create in `SelahCue — Delivery` (`901327960792`) when the MCP connection recovers, per `.claude/team/CLICKUP_TASK_SCHEMA.md`:

1. **Epic — "Import a presentation (.txt / .pptx / clipboard)"** linking this doc, `IMPORT-presentation-design.md`, `THREAT-MODEL-presentation-import.md`, ADR-0024/0025.
2. **Stories** under it per design §18: (1) text import end-to-end (`selahcue-import` crate, .txt + clipboard); (2) pptx text + notes; (3a) wire `media_repo` persistence — prerequisite for images; (3b) JPEG decode in `selahcue-engine` (ADR-0025); (4) media store + atomic commit + pptx images. Story 1 carries the §1–§4 policy values in its acceptance criteria; Sana's B1–B5 are named merge gates on stories 2/3b/4.
3. **Link bug `86ak196cr`** (DeckId resolution hazard, Bianca `FINDING-LIB-07`) to the epic — the §1/§2 Replace decision is constrained by it; its status is not changed (not created by this work).
4. **Follow-up tasks:** library-wide end of silent `(n)` (§3); Replace undo + plan-count in dialog (§2); **ADR-0016 decode worker with a committed milestone** (required by RR1's conditional acceptance, §12).
5. **Owner-decision task:** P12 residual-risk acceptance (RR1–RR6), carrying §12's recommendation.

Sequencing, dependencies and story sizing beyond this are Diego's.
