# ADR-0031 — Cross-machine deck identity: a uid per presentation, translated at the machine boundary, failing closed to "missing"

- Status: Accepted (implementation in ClickUp 86ak196cr; consumer is FR-139 plan-bundle import, 86ak0qn15)
- Date: 2026-10-24
- Confidence: High that the failure is real and that failing closed is the right default. Medium-high on the choice of where the translation happens (see "Options considered"); the main residual is listed under "Known limits".
- Owner: Backend Engineer, for Software Architect and Security Reviewer review
- Relates: ADR-0024 (presentation import; its decision 5 already keeps `DeckId` stable on `Replace` for the same reason), ADR-0020 (authored decks, plan content links), ADR-0007 (persistence)
- Domain: `docs/product/DOMAIN-library-organisation.md` section 9.2 (`FINDING-LIB-07`, `RULE-LIB-XFER-01`, `RULE-LIB-MIG-03`)
- Goal: `docs/delivery/goals/86ak196cr-deck-identity.md`

---

## Context

A service-plan item links a presentation as `ItemContent::Deck { deck_id, slide_count, label }`. `deck_id` is `DeckLibrary::mint_id()`: a counter that starts at 1 in every library and only counts up inside it. Two machines therefore hand out 1, 2, 3 to unrelated presentations.

Nothing in the product moves a plan between machines today (the run-sheet `ImportPlan` command carries kind, title, owner and seconds, and no content links; the FR-139 bundle is unbuilt), so the defect is latent. The first feature that does carry a plan across a machine boundary switches it on: a bundle exported on machine A holds `Deck { deck_id: 3 }`, and importing it on machine B, whose own deck 3 is something else, shows that other deck on the audience output with no marker of any kind. The failure is silent and lands on the highest-consequence surface in the product, which is why `RULE-LIB-XFER-01` says a cross-machine deck reference must be resolved by something globally distinguishable, or must fail closed to the missing-content state.

## Decision

1. **Every presentation has a `DeckUid`**: 128 random bits written as 32 lowercase hex digits, minted once when the deck is created, adopted, or duplicated, and stored **with the deck** (`SlideDeck.uid`, an additive optional field in `deck_json`, omitted from the JSON while unset). Renaming, editing, replacing (ADR-0024 decision 5) and undo-delete keep it. A **duplicate gets a new one**: it is a different presentation.
2. **The local number stays the local handle.** Plan rows, the wire protocol, the webview and the mobile app keep using `deck_id` exactly as before. Nothing about how a plan is stored or sent between the operator and the host changes.
3. **The number never crosses a machine boundary.** A deck link leaves a machine as a `PortableDeckLink { uid, label, slide_count }` (`selahcue_core::deck_ref::export_deck_link`). On the receiving side `import_deck_link` asks the receiving library "which of your presentations has this uid?" and binds the link to **that** deck, or, if there is none, to `UNRESOLVED_DECK_ID` (`0`, a number no library ever assigns) with the exporter's last known name. The operator then sees the existing missing-content state (FR-007 / FR-070) with the presentation's name, before the service. The exporter's local number is not an input to the import function at all, so it cannot be used by mistake.
4. **Fail closed in every non-match case**: absent uid (the exporter could no longer identify the deck), malformed uid (wrong length, upper case, non-hex, all zero, hostile length), a uid the library does not hold, or a library that answers with the sentinel.
5. **Legacy decks are backfilled once.** On load, a deck with no valid uid, or whose uid duplicates another deck's, is given a fresh one and the row is written back, so the identity is stable from the second launch. This rides the existing load-time self-heal; there is no schema change, because the field lives in `deck_json` next to the `id` that already lives there.

## Options considered

- **(Chosen) Identity in the library, translated at the boundary.** Plan storage, wire and webview stay byte-identical, so every plan that exists today keeps opening and resolving to the same decks on the machine that made it (acceptance criterion 4) with no migration of plan rows and no change to the cross-language wire fixtures. The guarantee is concentrated in one pure function that the future bundle import has to call.
- **Carry the uid in `ItemContent::Deck` and resolve by uid everywhere.** Strongest against a path nobody has thought of (a copied database, two operators on one host), but it touches the plan codec, the wire (`ContentLinkView`), the Dart model and its byte-pinned fixtures, and about ten resolution sites in the webview (`planDecks.some(d => d.id === link.id)` and its neighbours), each of which would have to be right for a wrong deck not to reach the audience. Rejected for this ticket as a large, risky change to the live path whose benefit is for scenarios the product does not support; tracked as a follow-up so the choice is visible.
- **Content hash as the identity.** An edit changes the hash, so a deck would stop matching its own links the moment someone fixed a typo. Rejected.
- **Fail closed only (a bundle never resolves a deck link).** Safe, but "the same presentation genuinely travels with the plan" (acceptance criterion 3) could never resolve. Rejected as the end state; it remains the behaviour for every case the uid cannot prove.
- **Name matching.** Names are operator-typed, uniquified with a "(n)" suffix, and unrelated across churches ("Communion" is not one presentation). A name match is exactly the silent wrong deck. Rejected; the name travels only as the label that describes a missing deck.

## Persistence and compatibility

- `deck_json` gains `"uid":"<32 hex>"` for decks that have one. `RULE-LIB-MIG-03` argues against putting *grouping* in `deck_json`, because an older build re-serialises the deck without fields it does not know and silently drops the user's filing. The same would happen to the uid on a downgrade-then-upgrade. The consequence here is different in kind and safe: the deck gets a **fresh uid** on the next load, so a bundle exported before the downgrade imports as missing on the machines that held the old uid. That is the fail-closed direction, never a wrong deck; the loss is recorded under "Known limits" rather than hidden.
- No SQL migration: the `deck` table is unchanged (name primary key, opaque `deck_json`). The "migration" is the load-time backfill above, covered by an equivalence test over legacy rows (ids, names, slides and every plan link unchanged; uids stable across a second load).
- `serde`: the uid is read leniently. A uid that is not a string, or not a valid uid, loads as "no uid" and is healed; it can never make a deck fail to load, because a corrupt identity must not cost the operator the deck.

## Consequences

**Positive.** The wrong-presentation failure becomes unrepresentable at the import boundary; the fix does not touch the live path; local behaviour is byte-identical; FR-139 has a single, tested function to call and a stated test-matrix requirement (a non-empty destination whose numbering overlaps).

**Negative / watch.**
- A uid is one more field to carry correctly. The library is its authority: `store()` re-applies the library's uid over whatever the editor handed back, and `duplicate()`/`adopt()` never keep a uid that is already held (including by a deck in the undo-delete trash).
- `getrandom` (already in the dependency tree for the transcript key) becomes a non-optional dependency of the operator.

## Known limits (deliberate, tracked)

1. **A link that imported as missing does not remember the uid.** It carries the label only, so re-exporting it to a third machine that does hold the deck cannot match it, and it cannot heal if the deck arrives later. It stays missing, which is the safe direction. Carrying the uid on the item is the "uid everywhere" option above.
2. **Paths that move a plan without going through an import** (copying the SQLite file to another machine; two operators with different libraries attached to one host) still resolve a link by local number. The ticket classes the first as unsupported, and decks are operator-owned by design, so the second is a different question (86ajy02zq). Both are closed by the "uid everywhere" option if the product ever supports them.
3. **Media has the same per-library numbering** (`ItemContent::Media { media_id }`). FR-139 says media is embedded or re-linked with an explicit missing-media report; the same rule applies and the same hazard exists if it is resolved by number. Out of scope here; follow-up filed.
4. Looking a uid up is a scan of the library (bounded by the number of decks, a few hundred at most). A bundle holds at most `MAX_PLAN_ITEMS` links, so an import is bounded work.

## Contract for FR-139 (86ak0qn15)

- Export every deck link with `export_deck_link`, using the exporting library's `DeckLibrary::export_link`. Never write `deck_id` into the bundle.
- Import every deck link with `DeckLibrary::import_link`, then set it with `ServicePlan::set_item_content`. Never construct `ItemContent::Deck` from a bundle field.
- The import preview should report the `NotInLibrary` count ("3 presentations are not in this library").
- The test matrix must include a **non-empty destination whose numbering overlaps the source** alongside the clean-install case. `identity_tests.rs` in `selahcue-operator` is the worked example.
