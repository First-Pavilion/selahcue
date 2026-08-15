# SelahCue — Domain rules: Library organisation (folders and tags)

Date: 2026-08-15 · Role: /business-analyst · Type: domain rule model
Trigger: owner proposal — the deck/presentation library gains **both** folders (browsing hierarchy) and tags (many-to-many labels), possibly renamed "Library". Stated rationale: *"when we open the presentation view and we have multiple items, it's a pain to search for one item in many places."*
Goal Contract: `docs/delivery/goals/GOAL-ba-domain-library-organisation.md` · ClickUp: **none** (no task covers library grouping; searched before writing)

**This document models rules, not scope, schema, or design.** Priya owns scope and is reassessing in parallel (`docs/product/SIZING-library-grouping.md`). Rowan owns competitor evidence in parallel (`GOAL-research-library-organisation.md`). Neither is duplicated here. Where a rule is a product decision rather than a domain constraint it is marked **`PRODUCT CALL`** and collected in §11 for Priya.

Evidence labels follow the team contract: **Verified** (path cited), **Inferred**, **Assumed**, **Unknown**.

---

## 1. The three findings that matter most

Read these first; the rest of the document supports them.

1. **Deck names are the persistence key, so "same name in two folders" is not a small change.** The `deck` table's primary key is `name`, and the library silently rewrites colliding names to `Name (2)` to protect it. The single most natural expectation of folders — *"Week 1" can exist in both Advent and Lent* — is therefore unavailable without changing how decks are keyed on disk. This is a structural consequence, not a preference. (§4.3, §12 Q1)

2. **Folders do not fail because a deck has two homes; they fail because a library has several independent single-valued axes and a tree can express only one.** Series, ministry, media type and season are each individually single-valued for most decks, which makes each of them look like a valid folder tree — but the tree can only be one of them, and everything filed along the chosen axis becomes hard to find along the others. This is why the folders-vs-tags rule is statable but fragile. (§3)

3. **Grouping delivers zero value on the day it ships, and its cost scales with library size.** Migration honestly creates no folders and no tags, so every existing deck is unfiled and untagged — exactly today's flat list. The entire benefit is unlocked by filing work the user must do, at the moment their library is largest. Any scheme that requires ongoing curation inherits this. (§8.2)

---

## 2. Entity model

### 2.1 What exists today (Verified)

| Entity | Identity | Uniqueness | Persisted | Owner |
|---|---|---|---|---|
| **Deck** (`SlideDeck`) | `DeckId(u64)`, monotonic, never reused, serialized inside the deck blob | Name is **globally unique**, enforced by silent `(n)` suffix | `deck` table, **PK = `name`**, body an opaque `deck_json` | Operator machine, local |
| **Slide** | `SlideId` within its deck | — | inside `deck_json` | its deck |
| **MediaAsset** | `MediaId(u64)` | Idempotent by **path**; **no name field, no name-uniqueness rule** | `media_repo` exists but is **not wired** — the media library is lost on restart | Operator machine, local |
| **ServicePlan** | row id | name not enforced unique | `service_plan (id, name, next_id)` + `plan_item` | Operator machine, local |
| **PlanItem** | `ItemId` within its plan | — | `plan_item` row | its plan |

Citations: `selahcue-operator/src/deck_library.rs:11-12,66-73,105-153,462-481`; `selahcue-data/src/deck_repo.rs:38-51` (`ON CONFLICT(name)`); `selahcue-core/src/media.rs:19-26,63-107,148-159`; `selahcue-data/src/migrations.rs:16-28`.

There is **no hierarchy anywhere in the codebase** — no `parent_id`, no `children`, no tree. Every domain collection is a flat `Vec`. Folders would introduce the first hierarchy SelahCue has ever had. (Verified, repository sweep.)

### 2.2 The proposed entities and their cardinality

| Relationship | Cardinality | Notes |
|---|---|---|
| Deck → Folder | **0..1** | A deck has at most one folder. Zero = unfiled (§4.5). |
| Folder → Deck | 0..* | A folder holds any number of decks, including none. |
| Folder → Folder (parent) | **0..1** | At most one parent. Zero = a root folder. |
| Deck ↔ Tag | **0..\* ↔ 0..\*** | Many-to-many. A tag may exist with zero decks. |
| Plan → Deck | 0..* by **id**, non-owning | A `PlanItem` may link one deck; many plans may link the same deck. |
| Deck → Plan | none | A deck holds no back-reference. Any "used in a plan" answer must be computed by scanning plans. |
| Folder ↔ Tag | **none** | Folders are not tagged and tags do not belong to folders. Keeping these orthogonal is what makes each rule statable on its own. |

### 2.3 Is a folder a property of a deck, or a container?

**Both descriptions are true and they are the same relation read from opposite ends.** The question only matters for what it implies, so answer it that way:

- **`RULE-LIB-ENT-01`** — The deck↔folder relation is **single-valued on the deck side**. That single-valuedness is what makes the structure a tree, and it is the only property that generates rules. Whether a schema stores it as a column on the deck or a membership row is an implementation choice with no domain consequence, and is out of scope here.
- **`RULE-LIB-ENT-02`** — A folder is **not an owner**. It does not own, contain, or control the lifetime of its decks. Deleting a folder therefore cannot delete a deck by default (§4.1). This is the domain distinction that drives every folder lifecycle rule.
- **`RULE-LIB-ENT-03`** — A tag is an **independent entity with its own lifecycle**, not a string on a deck. It can be created, renamed, and deleted while attached to zero decks, and renaming it must change how every deck carrying it is described, in one action. A design that stores tags only as strings inside each deck cannot satisfy this and would make "rename the Christmas tag" an N-deck rewrite with no atomicity.

**The sharpest asymmetry, worth stating as its own rule because it explains most of §4:**

- **`RULE-LIB-ENT-04`** — **Deleting a folder is a question; deleting a tag is not.** A folder is a deck's only home, so removing it strands the deck and the product must decide where the deck goes. A tag is never a home, so removing it merely removes a label and no deck is ever stranded. Any proposal that makes folder-deletion feel as harmless as tag-deletion has misunderstood the model.

### 2.4 Nesting

**`RULE-LIB-ENT-05`** — Nesting, if offered, is **capped at a fixed maximum depth**, and the cap is enforced on create, on move, and **on load**.

Rationale, and why "just allow any depth" is not available here:

- The repository has a hard bounded-memory rule (`CLAUDE.md`: no unbounded queues/caches/logs; new buffering code gets a bounded-memory test), and the house style is a `pub const MAX_*` with a doc comment naming the invariant, rejection at the cap rather than truncation, and a `within_bounds()` predicate — e.g. `MAX_PLAN_ITEMS = 500` (`plan.rs:258`), `MAX_MEDIA_ASSETS = 1000` (`media.rs:19`), `MAX_DECK_SLIDES = 500`, `MAX_SAVED_THEMES = 256`. (Verified.)
- A code-review precedent already treats an **unbounded ingress as a defect even for local SQLite reads**, i.e. load paths must re-check caps, not only write paths (`docs/delivery/CODE-REVIEW-batch-element-model.md:18`). A depth cap enforced only in the UI is therefore not compliant.
- Unbounded depth means unbounded recursion in every tree walk — rendering the tree, counting decks beneath a folder, deleting a subtree. With a corrupt or hostile persisted row this is a crash, and a crash in the operator console during a service is exactly what the never-blank principle exists to prevent.

**`RULE-LIB-ENT-06`** — A folder may **never** become its own ancestor. A move that would place a folder inside its own subtree is **refused** with a clear message; it is not silently reinterpreted as a move to root. Without this rule a cycle makes every tree walk non-terminating, and cycles are reachable through ordinary drag-and-drop, not just corruption.

**`RULE-LIB-ENT-07`** — The load path must **repair** rather than trust: a persisted folder whose parent is missing, whose parent forms a cycle, or that sits past the depth cap is reattached to root rather than dropped or allowed to stand. This mirrors the existing `DeckLibrary::heal()` contract, which already repairs duplicate ids and duplicate names on load instead of failing (`deck_library.rs:105-153`). Never lose the user's deck to fix the user's tree.

**`PRODUCT CALL` — the depth number itself.** Domain reasoning gives a shape, not a number: real church groupings are shallow (a series, or a ministry containing series). Deep trees in a volunteer-operated tool are a filing burden, not a feature. A defensible starting position is **two or three levels**, and a cap is easier to raise later than to lower. Routed to Priya (§11).

### 2.5 Deck count is currently unbounded

**`RULE-LIB-ENT-08`** — The library needs a maximum deck count for the same reason everything else has one. There is **no `MAX_DECKS` constant today** — `DeckLibrary` holds a plain `Vec<SlideDeck>` (`deck_library.rs:70`) and `list()` notes only "bounded by the library size (user data, not a leak)". (Verified.) This is pre-existing and not caused by grouping, but any library-organisation work will be reviewed against the no-leak rule, so it will surface then. FR-003 already names **5,000 items** as the performance target, which is the natural anchor.

---

## 3. Folders vs tags: the division of labour

The tasking asked for the rule that tells a user which to reach for, and said that failing to state it crisply is itself a finding. Here is the honest position: **the rule is statable, it is testable, and it will still be ignored.** All three parts matter.

### 3.1 The rule

- **`RULE-LIB-DIV-01`** — A **folder** answers *where does this live*: one home, mutually exclusive, permanent until moved. A **tag** answers *what is this about*: any number, non-exclusive, freely added and removed.
- **`RULE-LIB-DIV-02`** (the operational test) — **If a second value could ever be correct, it is a tag. If a second value is always an error, it is a folder.**

That is crisp and a person can apply it. The problem is what happens when you apply it to this domain.

### 3.2 Why it is fragile here

Apply `RULE-LIB-DIV-02` to the natural church groupings (Inferred, domain reasoning — the personas are silent and un-validated, `PERSONAS.md`; the competitor matrix never researched library organisation, `COMPETITOR-MATRIX.md` §1):

| Axis | Second value ever correct? | Verdict by the rule |
|---|---|---|
| Sermon series ("Rooted", weeks 1–6) | No | Folder |
| Content type (announcements, welcome, offering) | No | Folder |
| Season (Christmas, Easter, Advent) | Rarely | Folder |
| Ministry (youth, kids, main) | Sometimes (a joint youth+main night) | Tag |
| Year / archive | For a recurring deck, yes | Tag |

Three or four of these pass the folder test individually. That is the trap: **each axis is single-valued, but they are different axes, and a tree can encode only one of them as the browsing hierarchy.** The user must choose whether the tree is Series, or Type, or Season — and every deck someone later looks for along a different axis is now filed somewhere they will not think to look. Nesting does not rescue this; it fixes an order (Ministry ▸ Series) and thereby makes "all series across ministries" unbrowsable.

So the precise finding is not *"decks have multiple homes"* — that question is genuinely unsettled (`SIZING-library-grouping.md` §3, Unknown). It is:

- **`FINDING-LIB-01`** — **Libraries have multiple independent single-valued axes. A folder tree can express exactly one. Tags can express all of them.** Tags are strictly more expressive; folders are strictly more browsable. Shipping both is a real trade, not a free superset.

### 3.3 The consequence to expect in production

- **`FINDING-LIB-02`** — If both ship without the product telling the user **which axis the tree is for**, different volunteers will pick different axes, and two people in the same church will disagree about where a deck belongs. One files by series; the next looks by type; neither finds it. This is a predictable support pattern, and it is the specific confusion the tasking asked about.
- **`FINDING-LIB-03`** — The rule is stated in a sentence but is **not visible in the interface**. The repository's own market evidence says volunteer operability and minimal training are the dominant demand (`COMPETITOR-MATRIX.md` §4). A rule that must be taught is a rule that will decay. This is a design and product risk, not a gap in the domain model — the model is complete; adherence is what is doubtful.
- **`FINDING-LIB-04`** — A curation-dependent scheme has an asymmetric failure mode worth naming: an **unfiled deck still appears in the library** (it is merely in "Unfiled"), whereas an **untagged deck is invisible to every tag filter**. Tags fail more silently than folders. Both fail more silently than search, which needs no maintenance at all.

**`PRODUCT CALL`** — Whether to ship folders, tags, both, or neither, and which axis a tree would represent, are product decisions. Rowan's research is the evidence input; Priya decides. This document holds rules for every shape so no option is foreclosed.

---

## 4. Lifecycle and referential integrity

### 4.1 Deleting a folder

The domain already has a governing principle, and it is visible in shipped behaviour: **degrade, never destroy.** Deleting a deck referenced by a plan does not delete the plan item — the item survives and reports itself unresolved (`unresolved_content`, FR-007, `plan.rs:425-442`). The library repairs corrupt data on load rather than dropping it (`heal()`). A failed database opens in memory rather than blocking editing (`is_persistent()`, `deck_library.rs:100-102`). All Verified.

- **`RULE-LIB-FLD-01`** — Deleting a folder **never deletes a deck**. Every deck in the deleted folder becomes **unfiled**. A folder is a label with a tree shape (`RULE-LIB-ENT-02`); its removal cannot destroy content whose value is independent of it.
- **`RULE-LIB-FLD-02`** — A delete acts on the **whole subtree as one organisational unit**: descendant folders are removed with it, and every deck anywhere beneath becomes unfiled. The alternative — promoting children to the deleted folder's parent — strands "Kids" at the root with no memory that it meant "Christmas ▸ Kids", which is a worse outcome than a clean unfile.
- **`RULE-LIB-FLD-03`** — Deleting a folder that contains anything **states the count before it happens** ("Delete 'Christmas'? 3 sub-folders and 12 presentations will move to Unfiled. No presentations are deleted."). Silent structural change is the failure this whole rule set exists to prevent.
- **`RULE-LIB-FLD-04`** — If a **cascade** variant is offered ("delete the folder *and* its presentations"), it is a **separate, explicitly-labelled destructive action**, never the default, and it must show the **plan impact** — how many saved plan items across how many plans will become unresolved. Without this, one click can silently break dozens of plan links.
- **`RULE-LIB-FLD-05`** — Folder deletion is **undoable**, consistent with the shipped deck-delete pattern: `PRESENTATIONS-LIBRARY-spec.md` §5 specifies an undo-backed "Presentation deleted — Undo" toast and a Cancel-focused confirm dialog. (Verified.) A structural delete must not be *less* recoverable than a single-deck delete.

Note this ordering is what makes an edge case disappear: because deletion orphans rather than cascades, **deleting the folder of a deck currently open in the editor is a non-event** — the deck simply becomes unfiled. Under a cascade default the same action would delete a deck the user is actively editing.

**`PRODUCT CALL`** — whether the cascade variant exists at all (§11).

### 4.2 Deleting a deck

- **`RULE-LIB-DEL-01`** — Deleting a deck referenced by a saved plan is **allowed, warned, and non-cascading**: the plan item survives and renders its missing-content state. This is not a new rule — it is already shipped behaviour plus an already-written design decision. `unresolved_content()` is the FR-007 check run at plan open and pre-service (`plan.rs:425-442`), and `PRESENTATIONS-LIBRARY-spec.md` §5 already specifies "A ⚠ in-plan warning appears when the deck is referenced by a service plan ('that plan item will show missing')". (Verified.) **Grouping must not change this.**
- **`RULE-LIB-DEL-02`** — Deleting a deck removes its tag attachments and its folder membership. It never deletes the tag itself, and never deletes the folder even if the folder becomes empty (§4.6).
- **`RULE-LIB-DEL-03`** — There is **no back-reference from deck to plan** (§2.2), so the in-plan warning requires scanning saved plans. The design already depends on this in two places — the §5 warning and the "In a plan" chip on the library card (`PRESENTATIONS-LIBRARY-spec.md` §3). (Verified.) Folder-level bulk operations multiply the cost of that scan from one deck to a whole subtree, which is where it stops being free.

### 4.3 Naming and collisions — the structural finding

Today (Verified): deck names are **globally unique**, enforced silently. `create`, `adopt`, `rename` and `store` all route through `uniquify`, which returns `Name (2)`, `Name (3)`… on collision (`deck_library.rs:202-279,462-481`). This exists because the `deck` table's primary key is `name` and `save_one` upserts `ON CONFLICT(name)` — an upsert on a name owned by a different deck would overwrite that deck (`deck_repo.rs:38-51`, and the module doc at `deck_library.rs:11-12` says so explicitly).

- **`FINDING-LIB-05`** — **The most natural expectation of folders is currently unavailable.** Users expect to create "Week 1" inside both "Advent" and "Lent". Today the second one silently becomes "Week 1 (2)" — a visible artefact of exactly the disorganisation folders were meant to fix. Resolving this means deck names become unique **per folder**, which means the persistence key can no longer be the name. That is a change to how every deck is stored, not a column added beside it.
- **`RULE-LIB-NAME-01`** — Name-uniqueness **scope** must be decided before anything else, because it is the difference between an additive change and a re-keying. `PRODUCT CALL` → §12 Q1, and the lead schema-blocking question.
- **`RULE-LIB-NAME-02`** — Whatever scope is chosen, **silent renaming should stop**. Silently mutating a name the user just typed is tolerable in a flat list and corrosive in a filing system, where the user is actively reasoning about names. Preferred: refuse with "A presentation called 'Week 1' already exists in this folder" and let the user choose. `PRODUCT CALL` on the exact treatment.
- **`RULE-LIB-NAME-03`** — Folder names are unique **among siblings only**, case-insensitively. Two folders named "Week 1" under different parents is normal and expected — this is the universally understood convention and matching it costs nothing.
- **`RULE-LIB-NAME-04`** — Tag names are unique **library-wide**, compared case-insensitively after trimming and collapsing internal whitespace. A tag *is* its name; two tags that differ only by case or spacing split every filter and are always a defect. Display casing is preserved as first written.
- **`RULE-LIB-NAME-05`** — Creating a tag that already exists is **idempotent**: it attaches the existing tag. It never creates a second tag and never produces `Christmas (2)`. Applying the deck-style `uniquify` behaviour to tags would be a serious modelling error.
- **`RULE-LIB-NAME-06`** — Empty and whitespace-only names are rejected for folders and tags. The deck library's equivalent (substituting "Untitled presentation") suits a document that must exist; a folder or tag the user declined to name should simply not be created.

### 4.4 Moving

- **`RULE-LIB-MOV-01`** — Moving a deck between folders changes **only** its folder membership. It does not change the deck's id, its name, its content, its tags, or any plan link. (§6.1)
- **`RULE-LIB-MOV-02`** — Moving a folder moves its **entire subtree**. Subject to `RULE-LIB-ENT-06` (no cycles) and the depth cap applied to the **deepest descendant**, not just the moved folder — otherwise a legal-looking move of a shallow folder can push its grandchildren past the cap.
- **`RULE-LIB-MOV-03`** — A move that violates a cap or would create a cycle is **refused whole**. There is no partial move: a subtree move either happens completely or not at all. A half-moved tree has no valid interpretation.
- **`RULE-LIB-MOV-04`** — If names are unique per folder (`RULE-LIB-NAME-01`), a **move can collide** and is therefore fallible. This is easy to miss: a move is not a pure re-parent, and the collision must be resolved by the user, not silently by suffixing. If names stay globally unique, moves cannot collide — a genuine simplification worth weighing in Q1.
- **`RULE-LIB-MOV-05`** — Moving a deck that is currently **live or staged** on the audience output changes nothing about the output. Organisation is metadata; it can never touch the presenter. This follows the shipped invariant that staging never changes Live and only Go Live does (`CLAUDE.md`, `selahcue-present`).

### 4.5 Unfiled

- **`RULE-LIB-UNF-01`** — **Unfiled is a real state, not a real folder.** A deck's folder membership is genuinely absent; the interface presents an "Unfiled" group, but no folder entity exists for it.
- **`RULE-LIB-UNF-02`** — Consequently Unfiled cannot be renamed, deleted, moved, nested into, or given a parent. It is a **valid destination** ("move to Unfiled" = remove from folder) but not a manipulable **entity**. Modelling it as a real folder row means special-casing it against every one of those operations anyway, and adds a row that must never be deleted — strictly more work for strictly less clarity.
- **`RULE-LIB-UNF-03`** — Unfiled is never hidden. It is the honest default after migration (§8), the destination after folder deletion (`RULE-LIB-FLD-01`), and the state of every deck a user has not filed. A library that hides it hides most of its content on day one.

### 4.6 Empty folders and unused tags

- **`RULE-LIB-EMP-01`** — An empty folder **persists**. Users create folders ahead of filling them; auto-deleting one because its last deck moved out would destroy deliberate structure as a side effect of an unrelated action.
- **`RULE-LIB-EMP-02`** — An unused tag (attached to zero decks) also persists, but is a reasonable candidate for a "clean up unused tags" maintenance action. Never automatic. `PRODUCT CALL` on whether that action exists.
- **`RULE-LIB-EMP-03`** — Deleting a tag detaches it from every deck and deletes nothing else. No deck is ever affected beyond losing that label.
- **`RULE-LIB-EMP-04`** — Renaming a tag onto an existing tag's name is a **merge**, not a rename, and merges are not reversible by re-renaming. Recommended initial rule: **refuse**, with a separate explicit "merge into…" action if the need is demonstrated. `PRODUCT CALL`.

---

## 5. Bounds (the no-leak rule applied)

Per `CLAUDE.md` and the house style in §2.4, each of the following needs a named constant, rejection (never truncation) at the cap, and enforcement on **create, move, and load** — plus on import, which is the one untrusted ingress (§9).

| Bound | Why it must exist | Anchor |
|---|---|---|
| Max folder depth | Unbounded recursion in every tree walk (`RULE-LIB-ENT-05`) | no precedent — folders would be the first tree |
| Max folders per library | Unbounded row growth; the tree UI must render bounded | `MAX_SAVED_THEMES = 256` |
| Max children per folder | A single folder holding everything defeats the cap above | — |
| Max tags per library | Unbounded distinct-label growth | `MAX_SAVED_THEMES = 256` |
| Max tags per deck | Bounds the per-deck payload and the filter UI | — |
| Max folder/tag name length | Bounds persisted and rendered strings | `MAX_THEME_NAME_LEN = 64` |
| Max decks per library | Pre-existing gap (`RULE-LIB-ENT-08`) | FR-003 states 5,000 items |

**`RULE-LIB-BND-01`** (user-initiated operations) — When a **user action** would breach a cap it is **refused with a readable message**. Nothing is silently dropped, truncated, or reassigned behind the user's back.

**`RULE-LIB-BND-02`** (load) — Caps are re-checked when loading persisted data, not only when writing it, per the review precedent that an unbounded ingress is a defect even for local SQLite reads (`CODE-REVIEW-batch-element-model.md:18` — a load path that skipped `MAX_ELEMENTS` was a MEDIUM defect precisely because the column is local SQLite, not transport-bounded).

**`RULE-LIB-BND-03`** (how the two differ, stated because they look contradictory) — Refusal is not available on a load path: there is no user present and no operation to reject, and refusing to load would cost the user their library. The repository holds both precedents — `load_saved_themes` **drops** over-cap rows, while `DeckLibrary::heal()` **repairs** duplicate ids and names. The deciding question is whether the repair loses user content. So: an over-cap or malformed **grouping** row is **repaired** (reattached to root, `RULE-LIB-ENT-07`), never dropped, because dropping a folder row strands the decks beneath it. Repair on load is silent by necessity; it is the one place `BND-01`'s "nothing silently reassigned" does not apply, and it is bounded to structure — **no load-path repair may ever delete or alter a deck.**

---

## 6. Interaction with existing concepts

### 6.1 Plans do not care where a deck lives — and must not start caring

Verified: a plan item links a deck by id alone — `ItemContent::Deck { deck_id, slide_count }` (`plan.rs:86-89`) — and resolution is an injected existence probe, `unresolved_content(deck_exists, media_exists)` (`plan.rs:425-442`). Nothing in the link carries a name or a location. The whole deck-facing surface is id-keyed: `get(DeckId)`, `slide_list(DeckId)`, `render_slide(DeckId, SlideId, …)`, `present_payload(DeckId, SlideId)` (`deck_library.rs:192,313,390,410`).

- **`RULE-LIB-REF-01`** — Moving a deck between folders, or changing its tags, **has no effect on any plan**. Links are by id; organisation is not part of a deck's identity.
- **`RULE-LIB-REF-02`** — **Location must never enter the deck-link resolution path.** A path-shaped address ("Christmas/Week 1") would break every plan link the moment a deck is moved or a folder renamed — converting an organisational action into live-service breakage. This is the kind of change an implementer might add helpfully, so it is stated as a prohibition rather than left implied.
- **`RULE-LIB-REF-03`** — Ticket `86ajy02zq` (host-authoritative deck-link resolution) is explicitly conditional on decks moving host-side or becoming multi-operator. Grouping does neither, so it is **not** a trigger for that work. (Verified: ticket scope; `protocol.rs:172` host is deck-blind.)
- **`RULE-LIB-REF-04`** (pre-existing, worth recording) — `PlanItem.title` is an independent free-text field and does **not** follow the linked deck's name (`plan.rs:174-193`). Renaming a deck leaves a stale title in every plan referencing it. Not caused by grouping, but library work will surface it.

### 6.2 Search

- **`RULE-LIB-SRCH-01`** — **Search spans the entire library, always, regardless of the folder being browsed.** This is not a preference. The owner's stated problem is *"a pain to search for one item in many places"*; a search scoped to the current folder would recreate that problem inside the feature meant to solve it. Today's `search()` already scans every deck (`deck_library.rs:334-381`), so this rule preserves behaviour rather than adding a requirement.
- **`RULE-LIB-SRCH-02`** — Search results must show **where each hit lives**. Finding a deck without learning its location leaves the user unable to return to it by browsing, and unable to trust the tree. Concretely this means `SearchHit` gains a location field — it currently carries `deck_id, name, slide_id, slide_index, snippet, kind` and no location (`deck_library.rs:28-40`). This is the one place where grouping unavoidably changes an existing contract.
- **`RULE-LIB-SRCH-03`** — Results are **not grouped by folder**. Global ordering is kept and location is shown as metadata; grouping results by folder re-fragments exactly what search exists to flatten.
- **`RULE-LIB-SRCH-04`** — A "search within this folder" scope, if offered, is an explicit opt-in filter layered on top, never the default and never sticky across sessions. `PRODUCT CALL` on whether it exists.
- **`RULE-LIB-SRCH-05`** — Tag filtering and text search **compose** (tag filter AND text match), and multiple selected tags need a stated combinator. Recommended: **AND** (narrowing), because filters that widen as you add them confuse users. `PRODUCT CALL`.
- **`RULE-LIB-SRCH-06`** — Search must still meet FR-003's "<300ms for ≤5k items". Filtering after the existing scan preserves this; per-folder indexes are unnecessary at this scale.

### 6.3 What "Library" would rename

**`RULE-LIB-SRCH-07`** (naming hygiene) — SelahCue already uses "library" for two distinct things: the **deck library** and the **media library** (`media.rs`), which is a separate registry with its own rules — keyed by path, no name uniqueness, and **not persisted at all today** (`media_repo` exists but is unwired; the media library is lost on restart. Verified). Renaming the presentation view to "Library" without deciding whether media joins it creates an ambiguous term in the product and in the codebase. If both are organised, the rules here must be restated for media, where they differ materially (path-keyed identity, no names, intrinsic `MediaKind` filtering already present). `PRODUCT CALL` on the naming and on whether media is in scope.

---

## 7. Permissions and RBAC

**Confirmed from the code, not assumed** (as tasked):

- `Permission` has eleven variants — `GoLive, Navigate, ClearLive, Blackout, Timer, SearchScripture, Transcribe, Monitor, EditPlan, ManageDevices, ConfigureOutputs` (`rbac.rs:30-96`). **None concerns the deck library.**
- `required_permission()` maps every `Command`; there is no command that lists, browses, creates, or organises decks (`rbac.rs:99-120`). The whole deck surface is Tauri-local: `deck_list`, `deck_new`, `deck_rename`, `deck_search`, … (`selahcue-operator/src/main.rs`). Verified: no `deck_export`/`deck_import` command exists either.
- The host is deck-blind by design (`protocol.rs:172`), and `PresentAuthoredSlide` ships serialized slide and theme JSON — pixels' worth of content, never deck identity or location (`protocol.rs:~165-180`).

Therefore:

- **`RULE-LIB-RBAC-01`** — Folders and tags introduce **no new permission** and require **no change to `authorize()`**. The library is unreachable over the wire; the only actor is the person at the operator machine, who has full local access by definition.
- **`RULE-LIB-RBAC-02`** — **No role can see a filtered library today, because no role can see the library at all.** This is a confirmation, not an assumption.
- **`RULE-LIB-RBAC-03`** (the trigger to watch) — The moment **any** `Command` variant returns deck-library contents — for example letting an Assistant browse and queue a deck — a browse-style permission becomes required **and** folder visibility becomes a live RBAC question: does an Assistant see every folder, or a subset? Stating the trigger precisely means it gets caught at the point it arises rather than discovered after shipping.
- **`RULE-LIB-RBAC-04`** — There is **no per-user identity on the operator machine** — the library has no owner field and no ACL. "Private folder", "my folders", and per-volunteer views are therefore **not expressible** in the current model, and would be a substantially larger change than grouping. Worth saying plainly because "can I have my own folder?" is a natural request once folders exist.

---

## 8. Migration and back-compat

Verified: migrations are forward-only, tracked by SQLite's `user_version`, applied one per transaction, append-only — never edit an existing migration (`migrations.rs:1-14`). No timestamp columns exist on plans or decks.

### 8.1 The honest default

- **`RULE-LIB-MIG-01`** — Migration creates **zero folders and zero tags**. Every existing deck is unfiled and untagged.
- **`RULE-LIB-MIG-02`** — **No inference from names.** Do not parse "Advent — Week 1" into a folder "Advent". It guesses at intent, produces structure the user never created, and is tedious to undo across a large library. If assisted filing is wanted it is an explicit, previewed, user-confirmed action — never a migration side effect.

### 8.2 The consequence, stated plainly

- **`FINDING-LIB-06`** — After migration a user with 200 decks sees 200 unfiled decks: **exactly today's flat list**. The feature delivers nothing until the user files things, and the filing effort is proportional to library size — largest for precisely the users who have the problem. This is the domain-level version of the point Priya's sizing note makes about curation decay, arrived at independently, and it is the strongest argument for preferring zero-curation grouping first. (Cross-reference only; scope remains Priya's.)

### 8.3 Where grouping data may not live

- **`RULE-LIB-MIG-03`** — Grouping must **not** be stored inside `deck_json`. The data layer treats that blob as opaque and never deserializes it (`deck_repo.rs` module doc, Verified). More decisively: an older build that loads a deck, deserializes it without the grouping fields, and writes it back would **silently drop the user's filing** — a real data-loss path, since forward-only migrations mean a rollback leaves new columns present but unknown to old code. Grouping belongs in structures an older build ignores rather than rewrites. This is stated as a constraint a schema must satisfy; the schema itself is Aria's.
- **`RULE-LIB-MIG-04`** — Persistence is **best-effort**: a failed database open runs the library in memory with `is_persistent() == false`, and the interface already surfaces an honest "changes won't be saved" state (`deck_library.rs:8-12,100-102`). Folders and tags created in that session are equally unsaved, and the existing warning must be understood to cover them. A user who spends an evening filing a library in a degraded session must not be led to believe the work was kept.

---

## 9. Multi-device, import and export

### 9.1 What exists

- **No deck export or import exists** (Verified: the full Tauri command list has `deck_import_image`, which imports an *image into the media library*, and no deck-level export/import; no save dialog exists anywhere in the workspace).
- **The design already specifies one**: `PRESENTATIONS-LIBRARY-spec.md` §5 lists `Export deck (.json)…` in the card ⋯ menu. Design only, no code. (Verified.)
- **FR-139 plan-bundle export/import** (`86ak0qn15`, MVP, planning/todo) carries plan + item content references + media. It does **not** carry decks.
- **Database backup** exists as a library capability — `backup_to` / `backup_to_encrypted` copy the whole main database, which would include the `deck` table — but there is **no restore function and no caller outside tests**. (Verified, `selahcue-data/src/db.rs:110-134`.)

### 9.2 A pre-existing hazard that library work will collide with

- **`FINDING-LIB-07`** — `DeckId` is a **per-library monotonic counter starting at 1** (`deck_library.rs:161-168`). Two machines independently mint 1, 2, 3… A plan bundle exported from machine A carries `Deck { deck_id: 3 }`; imported on machine B it resolves against **machine B's unrelated deck 3**. The failure is not "missing" — it is **silently the wrong presentation on the audience screen**.
- FR-139's acceptance criterion 1 tests import on a **clean install**, where no decks exist and links resolve to nothing (the FR-007 missing state, which is correct and safe). The collision only bites on a **non-empty** install — the normal case, and not covered by the stated criteria. Recorded here as a referential-integrity finding for whoever picks up `86ak0qn15`; **it is pre-existing and not caused by grouping**.
- **`RULE-LIB-XFER-01`** — Any cross-machine deck reference must be resolved by something globally distinguishable, or must fail closed to the missing-content state. Resolving a foreign id against a local id space is never acceptable, because the failure is silent and lands on the audience output.

### 9.3 Does grouping travel with an exported deck?

- **`RULE-LIB-XFER-02`** — **Grouping is a property of a library, not of a deck.** A folder path means something only inside the library that defines it; carrying it to another machine imports one church's taxonomy into another's.
- **`RULE-LIB-XFER-03`** — **Tags travel.** A tag is descriptive and self-contained: "Christmas" means the same thing anywhere. On import, attach to the existing same-named tag if present, otherwise create it — the idempotent behaviour of `RULE-LIB-NAME-05`, applied at the import boundary.
- **`RULE-LIB-XFER-04`** — **Folder placement does not travel silently.** An import must **never restructure the destination library**. The imported deck lands **Unfiled** by default; the origin path may be carried as advisory metadata and offered in the import preview ("place in Christmas ▸ 2025?"), chosen by the user. This matches FR-139's existing acceptance criterion that import never overwrites silently and the operator confirms what will be created.
- **`RULE-LIB-XFER-05`** — Import is the library's **only untrusted ingress**, so every cap in §5, plus the depth and cycle rules, must be enforced there — a hostile or corrupt bundle must not be able to create a 10,000-deep tree. FR-139 already routes import through the FR-138 safe-import choke point (`86ak0qmzv`); grouping validation belongs at the same point.

### 9.4 Two machines, two libraries

- **`RULE-LIB-XFER-06`** — Grouping is **per-install and does not converge**. There is no sync, no reconciliation, and none is proposed. Two operators will legitimately hold different taxonomies over overlapping decks, and neither is wrong.
- **`RULE-LIB-XFER-07`** — Making taxonomy shared is a **synchronisation problem, not a grouping feature** — it needs an authority, a conflict rule, and a merge story, none of which exist. `SIZING-library-grouping.md` §5 already refuses synced grouping within this feature's scope; this model agrees on independent grounds and records why: the domain has no owner, no clock (no timestamps anywhere), and no identity, which are the three things a merge needs.

---

## 10. Edge cases

`D` = decided here on domain grounds. `P` = product call, routed to Priya (§11).

| # | Case | Expected behaviour | Rule | |
|---|---|---|---|---|
| 1 | Delete a folder containing decks | Folder goes; every deck becomes Unfiled; count shown first; undoable | `FLD-01/03/05` | D |
| 2 | Delete a folder containing sub-folders | Whole subtree removed as one unit; all decks beneath become Unfiled; no promotion of children | `FLD-02` | D |
| 3 | Delete a folder whose deck is open in the editor | Non-event — the open deck becomes Unfiled | `FLD-01` | D |
| 4 | Cascade-delete a folder's decks | If offered: separate destructive action, never default, must show how many plan items across how many plans break | `FLD-04` | P |
| 5 | Delete a deck referenced by saved plans | Allowed; ⚠ in-plan warning; plan items survive and show missing content; undoable | `DEL-01` | D |
| 6 | Delete a deck that is currently live | Live output unchanged; organisation never touches the presenter | `MOV-05` | D |
| 7 | Move a folder into its own descendant | Refused with a clear message; never silently reinterpreted | `ENT-06` | D |
| 8 | Move a folder whose grandchildren would exceed the depth cap | Refused whole; cap applies to the deepest descendant, not the moved node | `MOV-02/03` | D |
| 9 | Create a deck named "Week 1" in a second folder | Depends entirely on Q1. Today: silently becomes "Week 1 (2)" | `NAME-01`, `FINDING-05` | P |
| 10 | Move a deck into a folder already holding that name | Only possible under per-folder uniqueness; then a move is fallible and the user resolves it — never a silent suffix | `MOV-04` | P |
| 11 | Rename a deck to a taken name | Today: silent `(2)` suffix. Proposed: refuse and say why | `NAME-02` | P |
| 12 | Create a tag that already exists, differing only in case or spacing | Idempotent — attaches the existing tag; never a second tag, never "Christmas (2)" | `NAME-04/05` | D |
| 13 | Rename a tag onto another tag's name | It is a merge, not a rename, and is not reversible. Recommended: refuse; separate explicit merge action if needed | `EMP-04` | P |
| 14 | Delete a tag applied to 40 decks | Tag detached everywhere; no deck otherwise affected; no deck deleted | `EMP-03` | D |
| 15 | Last deck leaves a folder | Folder persists — deliberate structure is not auto-destroyed | `EMP-01` | D |
| 16 | Deck belongs to no folder | Real state, not a real folder. Unfiled is a valid destination but not a manipulable entity, and is never hidden | `UNF-01/02/03` | D |
| 17 | Search while browsing a folder | Spans the whole library, always; results show location; not grouped by folder | `SRCH-01/02/03` | D |
| 18 | Deck moved between folders while linked in a plan | Plan entirely unaffected — links are by id | `REF-01` | D |
| 19 | Deck renamed while linked in a plan | Link survives (id-keyed); the DB row moves atomically; but the plan item's title is stale (pre-existing) | `REF-04` | D |
| 20 | Existing library upgraded | Zero folders, zero tags; everything Unfiled; no inference from names | `MIG-01/02` | D |
| 21 | Database unavailable (in-memory fallback) | Folders and tags created that session are equally unsaved; the existing "changes won't be saved" state must cover them | `MIG-04` | D |
| 22 | Rollback to an older build after filing | Filing must survive. Storing grouping inside `deck_json` would silently drop it on the first old-build write | `MIG-03` | D |
| 23 | Import a deck whose origin folder path does not exist locally | Lands Unfiled; origin path advisory only, offered in the preview; import never restructures the destination | `XFER-04` | D |
| 24 | Import a deck carrying tags | Tags travel; attach to existing same-named tags, else create | `XFER-03` | D |
| 25 | Import a plan bundle onto a non-empty library | **Hazard**: `deck_id` is machine-local, so a foreign id can resolve to an unrelated local deck — the wrong presentation, silently. Must fail closed to missing content | `XFER-01`, `FINDING-07` | D |
| 26 | Import a hostile bundle with a 10,000-deep tree | Rejected at the FR-138 safe-import choke point; every cap enforced at import | `XFER-05`, `BND-01` | D |
| 27 | Persisted folder with a missing parent, a cycle, or past the depth cap | Reattached to root on load — repair, never drop the deck | `ENT-07` | D |
| 28 | Library reaches a cap (folders, tags, depth, decks) | Refused with a readable message; nothing silently dropped or truncated | `BND-01/02` | D |
| 29 | A paired controller asks to browse the library | Cannot happen today — no command exposes it. If one is added, a new permission and a folder-visibility rule become required | `RBAC-03` | D |
| 30 | User asks for a folder only they can see | Not expressible — no per-user identity or ACL exists on the operator machine | `RBAC-04` | D |

---

## 11. Product calls routed to Priya

These are decisions, not domain facts. None is answered here.

| # | Question | Why it is a product call | Blocks |
|---|---|---|---|
| P1 | Folders, tags, both, or neither | Depends on user evidence (Rowan) and scope (Priya), not on domain structure | Everything |
| P2 | If a tree ships, **which axis is it for** — series, type, season, ministry? | A tree encodes one axis; the choice is a product/IA decision with a support-cost consequence (`FINDING-01/02`) | Design, help content |
| P3 | Maximum nesting depth (the number) | Domain requires *a* cap; the value is a usability judgement. Easier to raise than lower | Schema, UI |
| P4 | Deck-name uniqueness scope — global or per folder | Structural: per-folder means decks can no longer be keyed by name on disk | **Schema — see Q1 in §12** |
| P5 | Keep silent `(n)` renaming, or refuse collisions and tell the user | Existing behaviour vs. a change in feel; affects create, rename, move and import | UI, import |
| P6 | Is cascade delete ("folder and its presentations") offered at all? | A dangerous convenience; may not be worth its risk | UI, undo |
| P7 | Tag rename onto an existing tag: refuse, or merge? | Merge is useful and irreversible | UI |
| P8 | Does a "clean up unused tags" action exist? | Maintenance affordance, not a domain requirement | UI |
| P9 | Multi-tag filter combinator — AND or OR | Recommended AND; user-expectation call | UI, search |
| P10 | Does "search within this folder" exist as an opt-in scope? | Default is settled (`SRCH-01`); the opt-in is optional | UI |
| P11 | Does the **media** library get the same organisation, and does "Library" name both? | Media has materially different rules (path-keyed, unnamed, unpersisted) | Naming, scope |
| P12 | Import default placement — always Unfiled, or offer the origin path? | Domain forbids silent restructuring; the offer is a product choice | Import UX |

---

## 12. Questions that must be answered before anyone designs a schema

Short, and in order. Q1 is the one that changes the shape of the work.

1. **Are deck names unique globally, or per folder?** (P4) Today `name` is the `deck` table primary key and the library silently suffixes collisions to protect it. Global keeps grouping additive. Per-folder means decks must be keyed by id on disk — a change to how every deck is stored, plus a fallible move (`MOV-04`), plus a migration that re-keys existing rows. Answering this first tells everyone whether this is a small feature or a re-keying. Nothing else should be designed until it is settled.
2. **Folders, tags, or both?** (P1) The three shapes have different entity models. Tags alone need no tree, no depth cap, no cycle rule, and no move semantics — most of §2 and §4 disappears.
3. **Does nesting exist, and what is the depth cap?** (P3) "No nesting" is a legitimate answer that removes `ENT-05`, `ENT-06`, `ENT-07`, `FLD-02` and `MOV-02` entirely.
4. **Where does grouping data live, given forward-only migrations and rollback?** It cannot live in `deck_json` without a silent data-loss path on an older build (`MIG-03`). The constraint is settled; confirming no one intends the blob is not.
5. **Is cascade delete offered?** (P6) It is the only rule here that can destroy user content, and it needs the plan-impact scan (`DEL-03`) that nothing currently implements.
6. **Will the library ever be readable over the LAN?** (`RBAC-03`) The answer is no today and grouping does not change it — but if a controller will ever browse decks, permission and folder visibility must be modelled now rather than retrofitted around a shipped schema.
7. **Does the media library share this model?** (P11) It is path-keyed, has no names, and is not persisted at all today. If "Library" is to name both, its rules must be written before a schema assumes they are alike.

---

## Evidence appendix

| Claim | Label | Source |
|---|---|---|
| Library is flat; `list()` name-sorted; `search()` scans all decks | Verified | `selahcue-operator/src/deck_library.rs:172-184,334-381` |
| Decks keyed by stable `DeckId` but **persisted by name**; names forced globally unique via `(n)` suffix | Verified | `deck_library.rs:11-12,105-153,462-481`; `selahcue-data/src/deck_repo.rs:38-51` |
| `DeckId` is a per-library monotonic counter from 1 | Verified | `deck_library.rs:161-168` |
| Plan items link decks by id only; resolution is an injected existence probe (FR-007) | Verified | `selahcue-core/src/plan.rs:86-89,425-442` |
| `PlanItem.title` is independent of the deck name | Verified | `selahcue-core/src/plan.rs:174-193` |
| Deck delete: allowed, ⚠ in-plan warning, plan item shows missing, undo-backed | Verified | `docs/design/PRESENTATIONS-LIBRARY-spec.md` §5 |
| "In a plan" chip on library cards implies a plan→deck scan | Verified | `PRESENTATIONS-LIBRARY-spec.md` §3 |
| Library spec covers search, sort and Grid/List only — **no** folder/tag/collection concept | Verified (absence) | `PRESENTATIONS-LIBRARY-spec.md` (whole file) |
| No `Permission` variant and no `Command` concerns the deck library | Verified | `selahcue-lan/src/rbac.rs:30-120`; `protocol.rs:172` |
| No deck export/import command exists; `deck_import_image` imports media | Verified | `selahcue-operator/src/main.rs` command list |
| `Export deck (.json)…` is specified in design only | Verified | `PRESENTATIONS-LIBRARY-spec.md` §5 |
| DB backup copies the whole database (would include `deck`); no restore, no caller outside tests | Verified | `selahcue-data/src/db.rs:110-134` |
| FR-139 plan bundle carries plan + content refs + media, not decks; clean-install AC only | Verified | ClickUp `86ak0qn15` |
| `86ajy02zq` is conditional on host-side/multi-operator decks | Verified | ClickUp `86ajy02zq` |
| Migrations forward-only via `user_version`, append-only; no timestamp columns | Verified | `selahcue-data/src/migrations.rs:1-28` |
| Persistence best-effort; in-memory fallback with `is_persistent() == false` | Verified | `deck_library.rs:8-12,100-102` |
| `heal()` repairs duplicate ids and names on load rather than failing | Verified | `deck_library.rs:105-153` |
| No hierarchy, no `parent_id`, no depth cap anywhere in the codebase | Verified (absence) | repository sweep, all desktop crates |
| No `MAX_DECKS`; deck count currently unbounded | Verified (absence) | `deck_library.rs:70,170-171` |
| Cap house style: `MAX_PLAN_ITEMS=500`, `MAX_MEDIA_ASSETS=1000`, `MAX_DECK_SLIDES=500`, `MAX_SAVED_THEMES=256` | Verified | `plan.rs:258`; `media.rs:19`; `present/src/deck.rs:33`; `app/src/controller.rs:228` |
| Load paths must re-check caps (unbounded ingress is a defect even for local reads) | Verified | `docs/delivery/CODE-REVIEW-batch-element-model.md:18` |
| Media library: path-keyed, idempotent by path, no name field, `media_repo` unwired → lost on restart | Verified | `selahcue-core/src/media.rs:63-107,148-159`; `media_repo` call sweep |
| Volunteer operability is the dominant market pain | Verified | `docs/research/COMPETITOR-MATRIX.md` §4 |
| Personas silent on library taxonomy and themselves un-validated | Verified | `docs/business/PERSONAS.md` |
| Which church axes are single- vs multi-valued | Inferred | domain reasoning; uncorroborated — Rowan's research is the evidence input |
| Whether one deck needs more than one home | Unknown | `SIZING-library-grouping.md` §3 records it unsettled |
