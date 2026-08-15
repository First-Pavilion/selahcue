# SelahCue — Sizing note: grouping in the presentation library

Date: 2026-08-15 · Role: /product-manager · Type: sizing / prioritisation (not a PRD, not a design)
Trigger: owner question — "What do you think about having folders for presentations so they can be correctly grouped?"
Goal Contract: `docs/delivery/goals/GOAL-pm-sizing-library-grouping.md` · ClickUp: **none created** (see §8)

**Verdict in one line: the problem is real but cannot yet have hurt anyone — the product is unlaunched and the MVP bar (flat + fast search, FR-003) is met. Do not schedule now. When library work next opens, the cheapest first step is derived, zero-curation groups — not folders — and the folders-vs-tags choice should be made on user evidence we do not yet have.**

> **Updated same day — see §9 addendum.** The owner's response (folders *and* tags; a browse-surface rationale; "Library" naming) is genuinely new evidence: it is the **first observed report of the pain** (owner-as-user), and it reframes the problem in a way that makes a much smaller slice buy most of the value. §9 revises §7's recommendation in part — a small **Library View slice (S)** is now worth scheduling on owner approval; the folders+tags compound waits for the in-flight research. §8's ranking of the *full* grouping build otherwise stands.

Evidence labels follow the team contract: **Verified** (path cited), **Inferred**, **Assumed**, **Unknown**.

---

## 1. What exists today (Verified)

- The library is **flat**: `deck_library.rs` `list()` returns all decks ordered by name; `search(query, limit)` (name + slide-content match) is the only findability tool. `DeckMeta` carries `{id, name, slides}` — **no timestamps of any kind**. (`implementation/desktop/crates/selahcue-operator/src/deck_library.rs:17-23,170-186`)
- **Per-service grouping is already solved**: `ServicePlan` with ordered `PlanItem`s is the playlist, and plan items link decks via `ItemContent::Deck { deck_id }` — one deck is reusable across many plans today. (`implementation/desktop/crates/selahcue-core/src/plan.rs:72-201`; PRD FR-003 acceptance: "items reusable across plans")
- The library is **operator-local by design**: the host is "deck-blind — Approach A" (`selahcue-lan/src/protocol.rs:172`); the mobile app contains zero deck references (`grep -rln deck implementation/mobile/selahcue_controller/lib/` → empty); deck-link resolution is operator-local (prior finding, 86ajy02zq closed as by-design).
- **No date columns exist anywhere relevant**: `service_plan(id, name, next_id)`, no created/edited timestamps on plans or decks (`selahcue-data/src/migrations.rs:16-28`). Migrations are forward-only.
- **No PRD requirement, ADR, decision, or design spec covers folders/tags/collections** for the library (grep of the PRD, `docs/design/*.md`, `DECISION-LOG.md`, `OPEN-DECISIONS.md` — the only "collection" hits are Figma variable collections and media-panel states). FR-003 *is* the library requirement, and it specifies flat + searchable: "Library search returns matches <300ms for ≤5k items."

So grouping would be a **new capability against a problem the PRD never claimed to solve** — findability in a grown library — not a gap against an existing requirement.

## 2. The user problem and the honest status of its evidence

The problem: as a church accumulates decks (sermon series, announcements, seasonal specials), a flat name-sorted list stops being browsable, and search only works when you remember what a thing was called.

- **Inferred (medium):** accumulation rate is roughly 1–3 decks/week for an active church (weekly sermon + announcements + occasional specials) → ~50–150/year. Browsing pain plausibly begins somewhere past ~100 items, i.e. **6–12 months into real use**.
- **Verified (absence):** no persona names library organisation as a pain. The persona pains are live-operation and plan-mismatch pains (`docs/business/PERSONAS.md` §1.1, §1.8) — and PERSONAS.md itself is flagged un-validated/INFERRED throughout.
- **Verified (absence):** the competitor matrix documents *service playlists/schedules* for every competitor (the ProPresenter/EasyWorship rows) — the concept SelahCue already ships as `ServicePlan` — but records **nothing about library folders/tags/collections for any product** (`docs/research/COMPETITOR-MATRIX.md` §1). Library organisation was not a researched dimension.
- **Verified:** zero customers can have hit the problem — the product is unlaunched (`PRODUCT-GAP-AUDIT-2026-08-14.md` §10: `Not Ready`; no distribution, licensing, or billing).

Net: the problem is **anticipated, not observed**. That does not make it imaginary — FR-003 itself anticipates 5k-item libraries — but it caps how much we should invest before launch.

## 3. The deciding question: does one deck need more than one home?

If yes, a folder tree is the wrong shape (single-home forces duplication; duplicated decks silently diverge when edited — a real cost here because decks are edited in place in the workspace). If no, folders are simpler and win.

**Verdict: UNSETTLED on the evidence in this repo.** Specifically:

- Personas are silent on it and are themselves un-validated (Verified absence, §2).
- The competitor matrix does not cover library organisation for any product (Verified absence, §2).
- The PRD and design corpus never model the concept (Verified absence, §1).
- Domain reasoning cuts both ways (Inferred, low-medium): the natural church groupings — sermon series, season (Christmas/Easter), ministry (youth/kids), recurring type (announcements) — are *mostly* single-home, but genuine multi-home cases exist (a "Christmas youth night" deck is both season and ministry; a recurring announcements deck spans every season). Whether those cases are 2% or 20% of a real library is exactly what we do not know.

Per the tasking instruction, no confident answer is manufactured from this. **What would settle it** (research Rowan can run when triggered — see §7):

1. **Hands-on competitor check (≤1 day):** how ProPresenter (multiple Libraries + playlists + tags), EasyWorship (collections/resource databases), and FreeShow (show categories) actually shape library organisation, and — the sharper signal — forum/support evidence of users duplicating items across folders and complaining about divergence. This fills a dimension the matrix explicitly did not research.
2. **A card-sort with 3–5 real operators (≤1 week elapsed):** give each their own (or a realistic sample) deck list; ask them to sort into piles; count decks placed in two piles. Decision rule: if a material fraction (rule of thumb: >~10%) is multi-pile, folders force duplication and tags/collections win; otherwise folders win on simplicity.

## 4. Decks, plans, or both?

**Decks only.** Plans accrue linearly (~1/week), are conventionally named by date/service, and their reuse path is already the shipped `plan_repo::duplicate` plus the open save-as-template work (FR-005, `86ajy0hxg`). A "plans archive by year" want may emerge, but it is a smaller, later, and different problem. (Verified for the mechanisms; Inferred for the accrual rate.)

## 5. Operator-only or synced? (the biggest cost driver)

**Legitimately operator-only.** The mobile controller never browses the deck library — it drives the plan and live state, and the host itself is deck-blind by design (Verified, §1). Grouping metadata therefore never needs to cross the wire: no host deck store, no versioned-protocol change, no cross-language fixture churn (`test_protocol.rs` ↔ Dart fixtures), no mobile UI. Any "synced grouping" scoping would multiply the cost by roughly an order of magnitude and contradict the deliberate operator-owned-library architecture — it should be treated as a different product decision, not a variant of this one. (Verified for the architecture; Inferred for the cost multiple.)

## 6. Options

Effort is relative, anchored loosely on recent single-batch operator features (a batch = schema + repo + UI + tests through review). All options are operator-local per §5. None of this specifies internals — shapes and costs only.

### Option A — Folders (single-home tree)

- **What it is:** each deck lives in exactly one folder; the library lists by folder.
- **Effort:** **M** — one forward-only migration, library-surface UI (create/rename/move/delete, search-across-folders preserved), tests. Roughly one batch.
- **Solves:** browsable structure; matches the owner's stated mental model.
- **Does not solve:** multi-home decks — if §3 resolves "yes", folders actively cause duplication-and-divergence. Also curation-dependent: volunteer-run teams must file things correctly forever (see Option C for why that is doubtful).
- **Risk:** it is the option most likely to be *the wrong shape*, and the shape question is the one we cannot yet answer.

### Option B — Tags / collections (many-to-many)

- **What it is:** a deck carries any number of labels; the library filters by label.
- **Effort:** **M+** — same order as A plus a second UI surface (label management, multi-select filter, label-at-save affordance). Slightly above one batch.
- **Solves:** multi-home decks; never forces duplication.
- **Does not solve:** curation decay — worse than folders, because an untagged deck is invisible to every filter, and volunteer teams demonstrably optimise for minimal training (Verified: volunteer-operability is the recurring market pain, `COMPETITOR-MATRIX.md` §4 point 2). A tag scheme that is 60% applied is worse than no scheme.

### Option C — Derived groups (zero curation)

- **What it is:** groups computed from what the operator already does: "Used in recent services", "Recently edited", "Never used", "In the current plan".
- **Tested against the personas, as tasked:** the parent's reasoning *holds*. Every persona is a volunteer or a time-pressed operator; the market's dominant demand is "anyone can run it with minimal training" (Verified, matrix §4); nothing in any persona suggests anyone owns, or would maintain, a taxonomy. A scheme that requires no maintenance is the only one guaranteed not to decay. (Inferred from Verified persona/market material — but the personas are themselves un-validated, so this is a strong hypothesis, not fact.)
- **One correction to the tasking assumption** — the data is *not* all already stored (Verified, §1):
  - "Used in recent services" **is computable today**: plan→deck links exist (`ItemContent::Deck`) and plan ids are monotonic, giving a coarse but honest recency order. Zero schema change.
  - "Recently edited" / "Never used (never planned)" need **deck timestamps that do not exist** — a small forward-only migration. Cheap, but not free.
- **Effort:** **S** — the smallest option; no new user-facing management surface at all.
- **Solves:** the two highest-frequency findability jobs (what did we use lately; what was I working on) with zero maintenance; also sidesteps §3 entirely — it forecloses neither folders nor tags later.
- **Does not solve:** thematic retrieval ("all our Easter decks"). Search covers that only as well as deck names do.

## 7. Recommendation

1. **Now: nothing.** Do not schedule any grouping work. Rationale in §8 — everything above it in the queue is launch-blocking or MVP-committed, and no user can yet have the problem this solves.
2. **First move when library work next opens (post-launch / R2 horizon): Option C.** Smallest, curation-free, robust to the unsettled shape question, and its one data prerequisite is a small migration that any future option needs anyway.
3. **Folders vs tags: decide on evidence, not preference.** Commission the §3 research (Rowan: competitor hands-on + operator card-sort) when a trigger fires, and only then choose A or B. Reasonable triggers: first real user request for library organisation; field evidence of libraries approaching ~100+ decks; or search-driven support complaints. Until a trigger fires, the research itself is also not worth scheduling — it would go stale before it is used.
4. **Keep it operator-only.** Any pull toward synced grouping is a separate architecture-level product decision (§5) and should be refused within this feature's scope.

Direct answer to the owner's question: folders are a reasonable instinct for a real future problem, but they are the one shape we might regret, the maintenance burden lands on volunteers, and a cheaper zero-maintenance step exists that we can ship first without closing any door. And none of it should displace what is currently in the queue.

## 8. Where this ranks against the open gaps (the part that decides scheduling)

Against `docs/product/audits/PRODUCT-GAP-AUDIT-2026-08-14.md` (verdict `Not Ready`, §10):

| Above it (all of) | Why |
|---|---|
| Track 1 — make it sellable: activation/entitlement client, billing, downloads, packaging, signed updates (FR-155), `/verify`+`/reset` pages (§11.3) | Launch-blocking; the product cannot be sold or safely updated |
| Owner decisions §8: KJV exposure, video/audio MVP boundary, commercial model | Block the launch definition itself |
| Track 2 — MVP feature debt: ~16 unbuilt FRs (incl. security-relevant FR-138) + 15 partials | These are *committed* PRD MVP scope; grouping is not among the 85 MVP FRs at all |
| Track 3 — the test programme, soak, security review | Proves the above |
| FR-031 scripture history/favourites (`86ak0qn2u`, ticketed) | The nearest comparable — also a findability feature — and it is a PRD requirement with a ticket; grouping is neither |

**Rank: below all of the above — post-launch backlog, R2-or-later horizon.** Plainly: **real but not next.** It earns a slot when the first trigger in §7.3 fires, and Option C is small enough to ride along with whatever library-adjacent batch comes first after launch.

## ClickUp

**No epic or task was created.** The tasking permitted creation only on a "worth scheduling now" conclusion; the conclusion is "real but not next". No existing task's status was changed. If the owner wants the §7.3 trigger tracked anyway, a single backlog task ("Library grouping — revisit on trigger", linking this note) is the right shape — say the word and it will be created.

## 9. Addendum — 2026-08-15 (same day): reassessment after the owner's response

Owner, verbatim: *"We can use Folders for the presentation grouping and add tags. The reason for the folders is for when we open the presentation view and we have multiple items, it's a pain to search for one item in many places. Maybe we call it Library or something. Is there value in this?"*

Three genuinely new inputs: (1) folders **and** tags, not either/or; (2) a stated rationale that is a **browse-surface** pain; (3) the "Library" name. Reassessed below — including one correction to this note's own §2.

### 9.1 Correction to §2: the pain is now observed, not merely anticipated

§2 said the problem was "anticipated, not observed" because no customer exists. That undercounted the owner-as-user: the response above is a present-tense report from using the product. Status upgrade: **observed, n=1** — a founder/power-user, not a volunteer persona, so it is weak evidence for *shape* but real evidence for *existence*, and it moves the pain onset earlier than §2's estimate (pain at tens of decks, not ~100+). It does not, by itself, move the work up the queue — but §9.2 does change what the cheapest relief is.

### 9.2 The stated pain is a browse-surface problem — which changes the cheapest fix

"Pain to search for one item in many places" describes **scanning and navigating a view**, not missing data structure. (Reading taken: one long undifferentiated list. If the owner instead means "which plan is this deck in?", that is a different fix — a reverse lookup from the existing plan→deck links — and also needs no new structure. Worth one confirming question.)

What relieves scanning pain with **no schema change and no curation** (Verified mechanisms, §1/§6C):

- an inline filter-as-you-type on the library list itself — today search lives in a separate modal (`deck_search`);
- derived ordering/sections on the existing flat list — "in the current plan", "used in recent services", "everything else" — computable today from plan links + monotonic plan ids;
- name order retained as the fallback.

Call this the **Library View slice** — a sharper cut of Option C aimed squarely at the stated sentence. **Effort: S** (view work + derived ordering; zero migration if plan-id-order recency is accepted; one small forward-only migration only if "recently edited" is wanted too). Honest expectation: this relieves **most of the stated pain** at a fraction of the folders+tags cost. What it does not give is thematic browsing ("all our Easter decks") — that is the part only folders/tags add, and it is *not* the pain the owner described.

### 9.3 Folders + tags: what the compound fixes, and what it doesn't

- **It does dissolve §3's duplication objection.** With tags for cross-cutting cases, a single-home tree no longer forces copies that diverge. The shape question stops being either/or.
- **It does not dissolve curation decay — it doubles the surface.** Two organising systems to maintain, plus a real "which one do I use?" confusion risk: folder-as-home vs tag-as-facet is obvious to information architects and not to volunteers (volunteer operability being the market's dominant pain — §6C, Verified).
- **Effort: L** — folders (M) + tags (M+) + the interplay UX (combined browse/filter semantics, untagged/empty states, move-vs-label affordances). Roughly two-plus batches versus one; the compound is *more* than the sum of its parts in UI surface.
- **Both in-flight research streams bear on exactly this.** Rowan is running the §3 competitor evidence and Bianca the domain rules. Committing to the compound today would pre-empt evidence arriving imminently. The compound is a plausible end state, not a scope to commit as a unit.

### 9.4 Naming: "Library"

- **No PRD collision — it is the PRD's own word.** FR-003 is literally "Presentation library of reusable documents", and the code type is already `DeckLibrary` (Verified, §1). Calling the surface "Library" is alignment, not a rename.
- **One disambiguation:** Design 2.0 already names the asset panel **"Media Library"** (`DESIGN-2.0-HANDOFF.md:177`) — the only "library" in the design corpus. If the deck surface becomes "Library", the pair must stay visibly distinct. Small product-naming decision; record it in the decision log when the first slice is approved, not before.

### 9.5 Revised recommendation (supersedes §7 items 1–2 in part)

**Answer to "Is there value in this?" — yes, real value. But most of the *stated* value is buyable for S, not L.**

1. **Schedule the Library View slice (S) on the owner's nod** — as, or riding along with, the next operator-surface batch. It attacks the exact sentence the owner wrote, needs no curation, no migration, no wire change, and is not throwaway: inline filter + recency ordering remain useful inside any future folder view. It is small enough not to displace Track 1/2 launch work — §8's ranking was about the full grouping build, and that ranking stands.
2. **Hold folders (M)** until (a) the slice lands and the pain is re-checked against real use, and (b) Rowan/Bianca report. If thematic-browsing pain persists after the slice, folders are the natural next increment.
3. **Hold tags (M+)** until multi-home evidence exists (Rowan's card-sort / competitor findings). Tags are the most decay-prone surface and the least evidenced today.
4. **Principle: earn the compound stepwise.** Folders+tags is the maximal scope; each increment should be justified by what the previous one failed to relieve, not committed up front because the combination is conceptually tidy.

### 9.6 ClickUp

Still **nothing created**. The owner's message ends in a question, not an approval, and PM-contract ticket creation follows explicit approval. On approval, the right first ticket is the **Library View slice (S)** with acceptance criteria written against the stated pain (an operator finds one deck quickly in a populated library view), plus a linked decision point for folders/tags scheduled after Rowan's and Bianca's outputs land.

## Evidence appendix

| Claim | Label | Source |
|---|---|---|
| Library flat, name-ordered; search only tool; no timestamps in `DeckMeta` | Verified | `selahcue-operator/src/deck_library.rs:17-23,170-186` |
| Plans link decks; decks reusable across plans | Verified | `selahcue-core/src/plan.rs:72-201`; PRD FR-003 |
| No date columns on plans; migrations forward-only | Verified | `selahcue-data/src/migrations.rs:16-28` |
| Host deck-blind; library operator-local; mobile deck-free | Verified | `selahcue-lan/src/protocol.rs:161-173`; empty grep over `mobile/.../lib/`; 86ajy02zq disposition |
| No FR/ADR/decision/design covers library grouping | Verified (absence) | greps over PRD, `docs/design/`, `DECISION-LOG.md`, `OPEN-DECISIONS.md` |
| Competitor matrix silent on library organisation | Verified (absence) | `docs/research/COMPETITOR-MATRIX.md` §1, §6 |
| Volunteer operability is the dominant market pain | Verified | `COMPETITOR-MATRIX.md` §4 |
| Personas un-validated; silent on library taxonomy | Verified | `docs/business/PERSONAS.md` header + §1 |
| Product unlaunched; launch-blocking gaps open | Verified | `PRODUCT-GAP-AUDIT-2026-08-14.md` §7, §10, §11 |
| Deck accrual ~50–150/yr; pain onset 6–12 months | Inferred | domain reasoning, uncorroborated |
| Multi-home decks exist but at unknown frequency | Unknown | §3 research would settle (Rowan in flight) |
| Browse pain observed in real use | Verified (n=1, owner-as-user) | owner response quoted in §9, 2026-08-15 |
| Search is a separate modal, not inline on the list | Verified | `deck_library.rs:25-29` (`deck_search` "the JSON the search modal renders") |
| "Media Library" is the only design-corpus "library" | Verified | `docs/design/DESIGN-2.0-HANDOFF.md:177`; grep over `docs/design/` |
