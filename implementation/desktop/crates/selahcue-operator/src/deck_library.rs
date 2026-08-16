//! The operator-local **Presentations Library** (design 86ajvpngr · `PRESENTATIONS-LIBRARY-spec.md`).
//!
//! Owns the authoritative set of saved decks (each a [`SlideDeck`] with a stable [`DeckId`]) plus an
//! optional persistence handle. It surfaces the deck list for the Library UI and backs the
//! create/open/rename/duplicate/delete commands; the currently-*open* deck is edited by the separate
//! [`DeckWorkspace`](crate::deck_workspace::DeckWorkspace) and synced back here (autosave).
//!
//! **Persistence is best-effort** (recovery, not a hard dependency): if the SQLite DB can't open, the
//! library runs in memory — editing is never blocked — and reports `is_persistent() == false` so the
//! UI can surface an honest "changes won't be saved" state. It is keyed by a stable `DeckId` but
//! **persisted by NAME** (the `deck` table PK, `deck_repo`), so names are kept **unique** (a `(n)`
//! suffix on collision) — otherwise an upsert on a name owned by a *different* deck would clobber it.

use selahcue_data::{deck_repo, Database};
use selahcue_present::{render_authored_slide, DeckId, FrameBuffer, SlideDeck, SlideId, Theme};

/// Lightweight row for the Library list (`deck_list`) — never carries the slide bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeckMeta {
    pub id: DeckId,
    pub name: String,
    pub slides: usize,
}

/// One hit from the global presentation search (`deck_search`): the matched deck (id + name) and —
/// for a SLIDE-CONTENT match — the matched slide's id/index + a short snippet of the matched line.
/// A NAME match carries no slide fields. Serializes to the JSON the search modal renders.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct SearchHit {
    pub deck_id: u64,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_id: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub snippet: Option<String>,
    /// `"name"` for a title match, `"content"` for a slide-text match.
    pub kind: &'static str,
}

/// A short, char-boundary-safe excerpt of `line`, capped to `max` chars (ellipsis when trimmed).
/// Slide text lines are short, so the first window is enough context for a search snippet.
fn search_snippet(line: &str, max: usize) -> String {
    if line.chars().count() > max {
        let head: String = line.chars().take(max).collect();
        format!("{head}…")
    } else {
        line.to_string()
    }
}

/// Lightweight per-slide row for the Live Console slide picker (`plan_deck_slides`,
/// `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §6): the slide's stable id, a speaker-readable
/// label (its first on-screen text line, falling back to a notes line), and whether it carries
/// speaker notes. Never the slide bytes — the picker fetches pixels separately, on demand, via
/// [`DeckLibrary::render_slide`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlideMeta {
    pub id: SlideId,
    pub label: Option<String>,
    pub has_notes: bool,
}

/// What [`DeckLibrary::adopt_with_policy`] does when the deck being adopted carries a name a saved
/// deck already holds (ADR-0024 decision 5; design §11.2 B).
///
/// The library deliberately has **no default**. Silent suffixing is tolerable when a human typed
/// the name and can see what happened; it is an operational hazard when the name was *derived* — a
/// presentation import names the deck after the file stem, nobody typed anything and nobody is
/// watching that field, so `Sunday Service (2)`, `(3)`, `(4)` accumulate with no way to tell which
/// one is this week's, and the wrong deck opens on a Sunday morning (design §11.1). Making the
/// choice a caller argument is what forces every derived-name path to state its intent.
// DELETE THIS ALLOW once `main.rs` wires the import commands. The operator is a *binary* crate, so
// `pub` exempts nothing from `dead_code`, and its clippy gate is `-D warnings`; `#[expect]` cannot be
// used because `--all-targets` compiles the bin both with and without `cfg(test)` and the tests below
// already exercise this API, so the lint fires in one build and not the other.
#[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NameCollisionPolicy {
    /// Keep the existing deck and adopt this one under a `(n)` suffix — today's [`uniquify`]
    /// behaviour, and what [`DeckLibrary::adopt`] has always done.
    KeepBoth,
    /// Update the existing deck **in place**, preserving its [`DeckId`] (see
    /// [`DeckLibrary::replace_deck`] for why the id must survive).
    Replace,
    /// Refuse: report the collision to the caller and change nothing.
    Fail,
}

/// Why [`DeckLibrary::adopt_with_policy`] / [`DeckLibrary::replace_deck`] refused. Refusals are
/// **total and side-effect-free** — on any `Err` the library, its ids and its persisted rows are
/// exactly as they were, so a caller can safely report the error and offer a different policy.
///
/// Hand-rolled with a manual `Display` + [`std::error::Error`], the house pattern (`ParseError` in
/// `selahcue-core::scripture`); the tree carries no `thiserror`/`anyhow`.
#[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AdoptError {
    /// A saved deck already holds this name and the policy was [`NameCollisionPolicy::Fail`].
    NameTaken,
    /// The deck that would be overwritten is the one currently live or staged. Replacing the
    /// content of the deck on the audience output mid-service is exactly what the presenter's
    /// "staging never changes Live" invariant exists to prevent, so this is **refused outright** —
    /// never queued, never applied at the next transition (design §11.2 D).
    TargetIsLive,
    /// [`DeckLibrary::replace_deck`] was given a [`DeckId`] the library does not hold — the deck the
    /// caller meant to replace was deleted (or its id was never valid) between the moment the choice
    /// was offered and the moment it was committed. Refused rather than silently adopted as a new
    /// deck, because "replace *that* one" and "add a new one" are different user intents.
    UnknownTarget,
}

impl std::fmt::Display for AdoptError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            AdoptError::NameTaken => "a presentation with that name already exists",
            AdoptError::TargetIsLive => {
                "that presentation is on the audience output — it can't be replaced right now"
            }
            AdoptError::UnknownTarget => "that presentation is no longer in the library",
        };
        f.write_str(s)
    }
}

impl std::error::Error for AdoptError {}

/// The persisted deck library.
pub struct DeckLibrary {
    /// The persistence handle, or `None` when running in the in-memory fallback.
    db: Option<Database>,
    /// The saved decks — each with a unique, non-zero [`DeckId`] and a unique `name`.
    decks: Vec<SlideDeck>,
    /// Monotonic library-level deck-id counter (never reused; self-heals past loaded ids).
    next_id: u64,
}

impl DeckLibrary {
    /// Build the library from an optional DB: load every persisted deck, deserialize, and
    /// **self-heal** to unique non-zero ids + unique names. A missing/failed DB → an empty
    /// in-memory library (never an error — persistence is best-effort).
    pub fn load(db: Option<Database>) -> Self {
        let mut decks: Vec<SlideDeck> = Vec::new();
        if let Some(db) = &db {
            if let Ok(rows) = deck_repo::load_all(db) {
                for (_name, json) in rows {
                    if let Ok(deck) = serde_json::from_str::<SlideDeck>(&json) {
                        decks.push(deck);
                    }
                    // A single corrupt blob is skipped, never fatal (FR-070-style tolerance).
                }
            }
        }
        let mut lib = DeckLibrary {
            db,
            decks,
            next_id: 1,
        };
        lib.heal();
        lib
    }

    /// Whether edits are actually being persisted (false = in-memory fallback).
    pub fn is_persistent(&self) -> bool {
        self.db.is_some()
    }

    /// Ensure every deck has a unique non-zero id and a unique, non-empty name; set `next_id` past
    /// the highest id. Mirrors the slide `mint_id` self-heal — a stale/tampered/duplicated blob can
    /// never leave two decks sharing an id (which would make `deck_open`/`delete` target the wrong
    /// one) or a name (which would make a `save_one` upsert clobber a sibling).
    fn heal(&mut self) {
        use std::collections::HashSet;
        self.next_id = self
            .decks
            .iter()
            .map(|d| d.id().0)
            .max()
            .unwrap_or(0)
            .saturating_add(1)
            .max(1);
        // Pass 1 — ids: reserve every distinct non-zero id in order; anything zero or duplicate gets
        // a freshly minted id (always > all existing, so it can't collide with a reserved one).
        let mut seen_ids: HashSet<u64> = HashSet::new();
        let mut need_id: Vec<usize> = Vec::new();
        for (i, d) in self.decks.iter().enumerate() {
            let id = d.id().0;
            if id == 0 || !seen_ids.insert(id) {
                need_id.push(i);
            }
        }
        for i in need_id {
            let id = self.mint_id();
            self.decks[i].set_id(id);
        }
        // Pass 2 — names: reserve every distinct non-empty name in order; anything empty or duplicate
        // is uniquified against the reserved set.
        let mut seen_names: HashSet<String> = HashSet::new();
        let mut need_name: Vec<usize> = Vec::new();
        for (i, d) in self.decks.iter().enumerate() {
            if !d.name.trim().is_empty() && seen_names.insert(d.name.clone()) {
                continue; // unique as-is
            }
            need_name.push(i);
        }
        for i in need_name {
            let base = if self.decks[i].name.trim().is_empty() {
                "Untitled presentation".to_string()
            } else {
                self.decks[i].name.clone()
            };
            let unique = uniquify(&base, &seen_names);
            seen_names.insert(unique.clone());
            self.decks[i].name = unique;
        }
    }

    /// Mint a fresh library deck id (monotonic, never reused). **Self-healing** (mirrors
    /// `SlideDeck::mint_id`): it advances `next_id` past every existing deck id before minting, so a
    /// deck adopted with a non-zero id, or a stale `next_id`, can never make a mint return a live id
    /// (which would make `get`/`delete`/`store` target the wrong deck). Saturating — never panics
    /// (an overflow at `u64::MAX` is unreachable under memory bounds; a crafted `u64::MAX` blob is
    /// the one boundary where two ids could tie, harmless to persistence which is name-keyed).
    fn mint_id(&mut self) -> DeckId {
        if let Some(highest) = self.decks.iter().map(|d| d.id().0).max() {
            self.next_id = self.next_id.max(highest.saturating_add(1));
        }
        let id = DeckId(self.next_id);
        self.next_id = self.next_id.saturating_add(1);
        id
    }

    /// The Library list — decks ordered by name (matches `deck_repo::load_all`'s deterministic order
    /// and the design's default sort). Bounded by the library size (user data, not a leak).
    pub fn list(&self) -> Vec<DeckMeta> {
        let mut metas: Vec<DeckMeta> = self
            .decks
            .iter()
            .map(|d| DeckMeta {
                id: d.id(),
                name: d.name.clone(),
                slides: d.len(),
            })
            .collect();
        metas.sort_by_key(|m| m.name.to_lowercase());
        metas
    }

    /// Whether the library has no decks (the empty-state).
    pub fn is_empty(&self) -> bool {
        self.decks.is_empty()
    }

    /// A clone of the deck with `id` (for opening it into the editor), or `None`.
    pub fn get(&self, id: DeckId) -> Option<SlideDeck> {
        self.decks.iter().find(|d| d.id() == id).cloned()
    }

    fn index_of(&self, id: DeckId) -> Option<usize> {
        self.decks.iter().position(|d| d.id() == id)
    }

    /// The index of the deck holding EXACTLY `name`. Exact, not case- or whitespace-folded, because
    /// [`uniquify`] is exact: any looser comparison here would let a policy decide a name collides
    /// while the uniquify path decides it does not, and the two must never disagree.
    #[allow(dead_code)] // reached via adopt_with_policy, wired in main.rs (ADR-0024)
    fn index_of_name(&self, name: &str) -> Option<usize> {
        self.decks.iter().position(|d| d.name == name)
    }

    /// Create a new **blank** deck (one empty slide, per the design's "Blank deck") with a unique id
    /// and a unique name, persist it, and return it (the caller opens it in the editor).
    pub fn create(&mut self, name: &str) -> SlideDeck {
        let base = if name.trim().is_empty() {
            "Untitled presentation"
        } else {
            name.trim()
        };
        let unique = uniquify(base, &self.name_set());
        let mut deck = SlideDeck::new(unique);
        let id = self.mint_id();
        deck.set_id(id);
        deck.add_slide(); // "One empty slide, ready to edit"
        self.persist_one(&deck);
        self.decks.push(deck.clone());
        deck
    }

    /// Adopt an EXISTING deck (e.g. the startup demo deck) into the library: give it a fresh id if
    /// it is unassigned or collides, a unique name, persist it, and return it (the caller opens it).
    ///
    /// This is [`adopt_with_policy`](Self::adopt_with_policy) under
    /// [`NameCollisionPolicy::KeepBoth`] with no live deck, minus the `Result` that policy can never
    /// produce — `KeepBoth` has no refusal path, so `adopt` stays total and every existing caller is
    /// untouched. Both entry points run the *same* private [`adopt_keep_both`](Self::adopt_keep_both)
    /// body rather than one calling the other through a `Result` it would have to unwrap, so the two
    /// cannot drift apart and no `unwrap`/`expect` enters a non-test path.
    pub fn adopt(&mut self, deck: SlideDeck) -> SlideDeck {
        self.adopt_keep_both(deck)
    }

    /// The one implementation of "add this deck beside whatever is already here": a fresh id if the
    /// deck's own is unassigned or already taken, a `(n)`-suffixed name if its own is taken, persist,
    /// return. Shared verbatim by [`adopt`](Self::adopt) and the `KeepBoth` arm of
    /// [`adopt_with_policy`](Self::adopt_with_policy).
    fn adopt_keep_both(&mut self, mut deck: SlideDeck) -> SlideDeck {
        if deck.id().0 == 0 || self.index_of(deck.id()).is_some() {
            let id = self.mint_id();
            deck.set_id(id);
        }
        let base = adopt_base_name(&deck);
        let unique = uniquify(&base, &self.name_set());
        deck.name = unique;
        self.persist_one(&deck);
        self.decks.push(deck.clone());
        deck
    }

    /// Adopt `deck`, stating explicitly what to do if its name is already taken (ADR-0024 decision 5).
    ///
    /// `live_deck` is the [`DeckId`] currently live or staged on the audience output, or `None`. It
    /// is passed **in** rather than read out of a presenter the library holds: `DeckLibrary` owns
    /// saved decks and nothing else, and giving it a handle on presenter state would make every
    /// library operation depend on the live pipeline it must never disturb. An `Option<DeckId>`
    /// argument keeps the refusal rule (`Replace` is refused against the live deck, design §11.2 D)
    /// enforceable *inside* the library — where it cannot be forgotten by a caller — while leaving
    /// the library itself presenter-free and unit-testable with no live output at all. The caller
    /// re-supplies it at commit time, because live state can change while a long import parses
    /// (`IMPORT-product-decisions.md` §1).
    ///
    /// **When the name is free, every policy behaves identically** — the deck is adopted under the
    /// name it carries. A policy is a collision *rule*, not a mode.
    ///
    /// On any `Err` nothing was mutated: no deck added, no id minted, no row written.
    #[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
    pub fn adopt_with_policy(
        &mut self,
        deck: SlideDeck,
        policy: NameCollisionPolicy,
        live_deck: Option<DeckId>,
    ) -> Result<SlideDeck, AdoptError> {
        // Resolve the collision on the SAME normalised name `adopt` would have used, so a policy
        // can never disagree with the uniquify path about whether a collision exists.
        let base = adopt_base_name(&deck);
        let Some(i) = self.index_of_name(&base) else {
            // No collision: policy-independent by construction — `uniquify` returns `base` verbatim
            // when it is free, so this is the same adopt for all three.
            return Ok(self.adopt_keep_both(deck));
        };
        match policy {
            NameCollisionPolicy::KeepBoth => Ok(self.adopt_keep_both(deck)),
            NameCollisionPolicy::Fail => Err(AdoptError::NameTaken),
            // Resolve the collision to the id the NAME holder actually has, then replace by id. The
            // name is how the collision was found; the id is what the replacement is keyed on.
            NameCollisionPolicy::Replace => {
                let target = self.decks[i].id();
                self.replace_deck(target, deck, live_deck)
            }
        }
    }

    /// Overwrite the deck with id `target` with `deck`'s slides, **keeping the target's own
    /// [`DeckId`] and name**, and persist through the ordinary content-upsert path.
    ///
    /// Preserving the id is the whole point, not an implementation detail. The `deck` table's
    /// primary key is the *name*, so the obvious implementations — delete-then-insert, or an upsert
    /// keyed on the name — write the row belonging to a **different** `DeckId` while the in-memory
    /// library still holds the old one. Every `PlanItem` that links the old id
    /// (`ItemContent::Deck { deck_id }`) then resolves to nothing or, worse, to an unrelated deck:
    /// the service plan does not fail loudly, it silently shows the wrong presentation to the
    /// congregation (`FINDING-LIB-07`, ClickUp `86ak196cr`). Because plan links never depended on the
    /// name, keeping the id makes them survive a replace for free — and because the stored name is
    /// kept too, the persisted row is *updated*, never orphaned and re-created.
    ///
    /// Refused, with nothing mutated, when `target` is unknown ([`AdoptError::UnknownTarget`]) or is
    /// the live/staged deck ([`AdoptError::TargetIsLive`]).
    #[allow(dead_code)] // consumed by the import commands in main.rs (ADR-0024)
    pub fn replace_deck(
        &mut self,
        target: DeckId,
        deck: SlideDeck,
        live_deck: Option<DeckId>,
    ) -> Result<SlideDeck, AdoptError> {
        // Both refusals are checked BEFORE any mutation, so an `Err` is always a no-op.
        let Some(i) = self.index_of(target) else {
            return Err(AdoptError::UnknownTarget);
        };
        if live_deck == Some(target) {
            return Err(AdoptError::TargetIsLive);
        }
        let mut updated = deck;
        updated.set_id(target); // the id plan items link — never re-minted
        updated.name = self.decks[i].name.clone(); // the row key — so this upserts, not orphans
        self.decks[i] = updated.clone();
        self.persist_one(&updated);
        Ok(updated)
    }

    /// Sync the open deck's edited content back into the library and persist it (per-edit autosave).
    /// No-op if `deck` is not a library deck (e.g. an id-less transient). Names are NOT changed here
    /// (that is [`rename`](Self::rename)); if the caller renamed the open deck out of band, the name
    /// is re-uniquified defensively.
    pub fn store(&mut self, deck: &SlideDeck) {
        let Some(i) = self.index_of(deck.id()) else {
            return;
        };
        let old_name = self.decks[i].name.clone();
        let mut updated = deck.clone();
        // Guard the name-PK invariant even if the caller mutated name directly.
        if updated.name != old_name {
            let unique = uniquify_excluding(&updated.name, &self.name_set(), &old_name);
            updated.name = unique;
        }
        let new_name = updated.name.clone();
        self.decks[i] = updated.clone();
        if new_name != old_name {
            self.persist_rename(&old_name, &updated); // atomic drop-old + upsert-new
        } else {
            self.persist_one(&updated);
        }
    }

    /// Rename the deck with `id` to a unique form of `new_name`; persist. Returns the applied name,
    /// or `None` if `id` is unknown.
    pub fn rename(&mut self, id: DeckId, new_name: &str) -> Option<String> {
        let i = self.index_of(id)?;
        let old_name = self.decks[i].name.clone();
        let base = if new_name.trim().is_empty() {
            "Untitled presentation"
        } else {
            new_name.trim()
        };
        let unique = uniquify_excluding(base, &self.name_set(), &old_name);
        if unique == old_name {
            return Some(old_name); // no change
        }
        self.decks[i].name = unique.clone();
        let deck = self.decks[i].clone();
        self.persist_rename(&old_name, &deck); // atomic drop-old + upsert-new (no lost row on crash)
        Some(unique)
    }

    /// Duplicate the deck with `id` into an independent copy ("<name> copy", unique) with a fresh id;
    /// persist. Returns the new deck (not opened), or `None` if `id` is unknown.
    pub fn duplicate(&mut self, id: DeckId) -> Option<SlideDeck> {
        let src = self.decks.iter().find(|d| d.id() == id)?.clone();
        let mut copy = src.clone();
        let new_id = self.mint_id();
        copy.set_id(new_id);
        let copy_name = uniquify(&format!("{} copy", src.name), &self.name_set());
        copy.name = copy_name;
        self.persist_one(&copy);
        self.decks.push(copy.clone());
        Some(copy)
    }

    /// Delete the deck with `id`; persist. Returns `true` if a deck was removed.
    pub fn delete(&mut self, id: DeckId) -> bool {
        let Some(i) = self.index_of(id) else {
            return false;
        };
        let name = self.decks[i].name.clone();
        self.decks.remove(i);
        self.delete_persisted(&name);
        true
    }

    // --- Live Console slide picker: read-only bridge (LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec §6) --

    /// List a saved deck's slides for the Live Console picker — id + a speaker-readable label + a
    /// notes flag, in deck order. `None` when the deck id is unknown (the picker renders its
    /// "presentation missing" state, FR-007). Reads the library only; never loads or mutates the
    /// open editor [`DeckWorkspace`](crate::deck_workspace::DeckWorkspace). Pure and bounded by the
    /// deck's own slide/element caps (no-leak).
    pub fn slide_list(&self, id: DeckId) -> Option<Vec<SlideMeta>> {
        let deck = self.get(id)?;
        Some(
            deck.slides()
                .iter()
                .map(|s| SlideMeta {
                    id: s.id,
                    label: s.confidence_slide().body.into_iter().next(),
                    has_notes: !s.notes.is_empty(),
                })
                .collect(),
        )
    }

    /// Global presentation search (`deck_search`): case-insensitive substring match on deck NAME and
    /// each slide's on-screen text, returning at most `limit` hits — NAME matches (whole deck) before
    /// per-slide CONTENT matches (one hit per matching slide). Decks are visited name-sorted (same
    /// deterministic order as [`list`](Self::list)). Bounded by `limit` and each deck's own slide/
    /// element caps; `confidence_slide()` is a cheap text extraction (no pixel render), so scanning
    /// the whole library is safe. An empty/whitespace query returns no hits. Reads the library only —
    /// never touches the open editor workspace.
    pub fn search(&self, query: &str, limit: usize) -> Vec<SearchHit> {
        let q = query.trim().to_lowercase();
        if q.is_empty() || limit == 0 {
            return Vec::new();
        }
        let mut order: Vec<&SlideDeck> = self.decks.iter().collect();
        order.sort_by_key(|d| d.name.to_lowercase());
        let mut hits: Vec<SearchHit> = Vec::new();
        for deck in order {
            if hits.len() >= limit {
                break;
            }
            // NAME match — the whole presentation.
            if deck.name.to_lowercase().contains(&q) {
                hits.push(SearchHit {
                    deck_id: deck.id().0,
                    name: deck.name.clone(),
                    slide_id: None,
                    slide_index: None,
                    snippet: None,
                    kind: "name",
                });
            }
            // CONTENT match — the first matching text line of each slide (one hit per slide).
            for (i, slide) in deck.slides().iter().enumerate() {
                if hits.len() >= limit {
                    break;
                }
                let matched = slide
                    .confidence_slide()
                    .body
                    .into_iter()
                    .find(|line| line.to_lowercase().contains(&q));
                if let Some(line) = matched {
                    hits.push(SearchHit {
                        deck_id: deck.id().0,
                        name: deck.name.clone(),
                        slide_id: Some(slide.id.0),
                        slide_index: Some(i),
                        snippet: Some(search_snippet(&line, 80)),
                        kind: "content",
                    });
                }
            }
        }
        hits.truncate(limit);
        hits
    }

    /// Render ONE slide of a saved deck to a bounded RGBA framebuffer for the picker/preview — the
    /// SAME native compositor and preview theme ([`Theme::dark`]) as the editor canvas, so a
    /// filmstrip thumbnail matches the editor. `None` when the deck OR slide id is unknown.
    /// Dimensions are clamped (≤960×540, mirroring the editor's own preview) so a hostile/oversized
    /// request can never allocate without bound (no-leak). Reads the library only — the open editor
    /// workspace is never loaded or mutated. Routing these pixels to the physical audience output is
    /// a separate seam (Dep 2, ADR ~0022); this is Preview/thumbnail composition only.
    pub fn render_slide(
        &self,
        deck_id: DeckId,
        slide_id: SlideId,
        max_w: u32,
        max_h: u32,
    ) -> Option<FrameBuffer> {
        let deck = self.get(deck_id)?;
        let slide = deck.get(slide_id)?;
        let w = max_w.clamp(1, 960);
        let h = max_h.clamp(1, 540);
        Some(render_authored_slide(slide, &Theme::dark(), w, h))
    }

    /// The `(slide_json, theme_json)` for ONE slide of a SAVED deck — the payload the console sends
    /// via `present_authored_slide` to route a plan-linked presentation slide to the LIVE audience
    /// output (the SAME authored-slide present path the deck editor's `deck_go_live` uses, but for a
    /// plan-linked saved deck rather than the open workspace). `None` when the deck OR slide id is
    /// unknown or serialization fails. Theme = [`Theme::dark`] (the console preview theme), so the
    /// audience output matches the filmstrip thumbnail. Reads the library only.
    pub fn present_payload(
        &self,
        deck_id: DeckId,
        slide_id: SlideId,
    ) -> Option<(String, String, Option<String>)> {
        let deck = self.get(deck_id)?;
        let idx = deck.index_of(slide_id)?;
        let slide = deck.get_index(idx)?;
        let slide_json = serde_json::to_string(slide).ok()?;
        let theme_json = serde_json::to_string(&Theme::dark()).ok()?;
        // The COMING deck slide feeds the host Stage/Confidence monitor's "next" (Approach A). `None`
        // at the end of the deck (no wrap).
        let next_json = deck
            .get_index(idx + 1)
            .and_then(|next| serde_json::to_string(next).ok());
        Some((slide_json, theme_json, next_json))
    }

    // --- persistence (best-effort; a DB error is swallowed, never blocks editing) ---

    fn persist_one(&self, deck: &SlideDeck) {
        if let Some(db) = &self.db {
            if let Ok(json) = serde_json::to_string(deck) {
                let _ = deck_repo::save_one(db, &deck.name, &json);
            }
        }
    }

    fn delete_persisted(&self, name: &str) {
        if let Some(db) = &self.db {
            let _ = deck_repo::delete_one(db, name);
        }
    }

    /// Atomically move a deck's on-disk row from `old_name` to `deck.name` (one transaction) — a
    /// crash mid-rename can never lose the row. Best-effort (a DB error is swallowed).
    fn persist_rename(&self, old_name: &str, deck: &SlideDeck) {
        if let Some(db) = &self.db {
            if let Ok(json) = serde_json::to_string(deck) {
                let _ = deck_repo::rename_one(db, old_name, &deck.name, &json);
            }
        }
    }

    fn name_set(&self) -> std::collections::HashSet<String> {
        self.decks.iter().map(|d| d.name.clone()).collect()
    }
}

/// The name an adopted deck is filed under before uniqueness is applied: its own name, trimmed,
/// falling back to `"Untitled presentation"` when it carries none. Factored out so collision
/// detection and the `(n)` suffixing operate on the *same* string — if one trimmed and the other did
/// not, `"Sermon "` would be judged collision-free and then filed as `"Sermon (2)"`, which is
/// exactly the silent fork the policy argument exists to prevent. (A caller with a better fallback —
/// import uses `"Imported presentation"` — supplies it in the deck's own name; the library's
/// fallback is unchanged so no existing behaviour moves.)
fn adopt_base_name(deck: &SlideDeck) -> String {
    let trimmed = deck.name.trim();
    if trimmed.is_empty() {
        "Untitled presentation".to_string()
    } else {
        trimmed.to_string()
    }
}

/// Return `base` if unused, else `base (2)`, `base (3)`, … — the first form not in `taken`. Total
/// and collision-free: it searches until a free suffix is found, guaranteed within `|taken|+1`
/// iterations (there are only `|taken|` names to dodge), so it can never return a taken name.
fn uniquify(base: &str, taken: &std::collections::HashSet<String>) -> String {
    if !taken.contains(base) {
        return base.to_string();
    }
    let mut n = 2u64;
    loop {
        let cand = format!("{base} ({n})");
        if !taken.contains(&cand) {
            return cand;
        }
        n += 1;
    }
}

/// Like [`uniquify`] but treats `keep` as free (renaming a deck to a suffix of its own base).
fn uniquify_excluding(base: &str, taken: &std::collections::HashSet<String>, keep: &str) -> String {
    let mut set = taken.clone();
    set.remove(keep);
    uniquify(base, &set)
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;

    #[test]
    fn in_memory_library_is_not_persistent_and_starts_empty() {
        let lib = DeckLibrary::load(None);
        assert!(!lib.is_persistent());
        assert!(lib.is_empty());
        assert!(lib.list().is_empty());
    }

    #[test]
    fn create_mints_unique_ids_and_names_with_one_slide() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("Sermon");
        let b = lib.create("Sermon"); // same display name → uniquified
        let c = lib.create("   "); // blank → "Untitled presentation"
        assert_ne!(a.id(), b.id(), "distinct ids");
        assert_ne!(a.id().0, 0, "assigned a non-zero id");
        assert_eq!(a.name, "Sermon");
        assert_eq!(b.name, "Sermon (2)", "duplicate name uniquified");
        assert_eq!(c.name, "Untitled presentation");
        assert_eq!(a.len(), 1, "a blank deck has one editable slide");
        assert_eq!(lib.list().len(), 3);
    }

    #[test]
    fn slide_list_lists_slides_with_labels_and_notes_flag() {
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Sermon"); // starts with one editable slide
        let s2 = deck.add_slide().unwrap();
        deck.get_mut(s2).unwrap().notes = "Closing prayer".into();
        lib.store(&deck); // sync the edit back into the library

        let metas = lib
            .slide_list(deck.id())
            .expect("a known deck lists its slides");
        assert_eq!(metas.len(), 2, "both slides listed, in deck order");
        assert_eq!(metas[1].id, s2);
        assert!(metas[1].has_notes, "the slide with notes is flagged");
        assert_eq!(
            metas[1].label.as_deref(),
            Some("Closing prayer"),
            "label falls back to a notes line when there is no on-screen text"
        );
        assert!(!metas[0].has_notes, "the default slide carries no notes");
    }

    /// A visible slide text box carrying `s` (mirrors the editor's `text_element` seed) so a test
    /// can author searchable on-screen content.
    fn text_el(s: &str) -> selahcue_present::Element {
        use selahcue_present::{Element, Fit, Rgba, TextAlign, VAlign};
        Element::Text {
            x_permille: 100,
            y_permille: 100,
            w_permille: 800,
            h_permille: 200,
            text: s.to_string(),
            color: Rgba::rgb(240, 240, 245),
            size_permille: 90,
            line_height_permille: 1100,
            align_h: TextAlign::Left,
            align_v: VAlign::Top,
            fit: Fit::ShrinkToFit,
            opacity: 255,
            z: 0,
            font: None,
            weight: 400,
            letter_spacing_permille: 0,
            visible: true,
        }
    }

    #[test]
    fn search_matches_names_and_slide_content_and_is_bounded() {
        let mut lib = DeckLibrary::load(None);
        // A deck whose NAME matches "grace".
        lib.create("Grace Fellowship");
        // A deck whose name does NOT match, but a slide's on-screen TEXT contains "amazing grace".
        let mut hymns = lib.create("Hymnbook"); // one blank slide
        let sid = hymns.slides()[0].id;
        hymns
            .get_mut(sid)
            .unwrap()
            .elements
            .push(text_el("Amazing Grace, how sweet the sound"));
        lib.store(&hymns); // sync the authored text back into the library

        // NAME query → a name hit (whole deck, no slide fields).
        let by_name = lib.search("grace", 50);
        assert!(
            by_name
                .iter()
                .any(|h| h.name == "Grace Fellowship" && h.kind == "name" && h.slide_id.is_none()),
            "a deck whose NAME matches is a name hit"
        );

        // CONTENT query → a content hit via slide text, with the matched slide id/index + a snippet.
        let by_content = lib.search("amazing grace", 50);
        let hit = by_content
            .iter()
            .find(|h| h.kind == "content")
            .expect("a slide-content hit");
        assert_eq!(hit.name, "Hymnbook");
        assert!(hit.slide_id.is_some() && hit.slide_index == Some(0));
        assert!(hit
            .snippet
            .as_deref()
            .unwrap()
            .to_lowercase()
            .contains("amazing grace"));

        // No match / empty query → no hits (empty query never scans).
        assert!(lib.search("zzz-not-found", 50).is_empty());
        assert!(lib.search("   ", 50).is_empty());

        // The result cap is honoured (both decks match "e"; cap to 1).
        assert!(
            lib.search("e", 1).len() <= 1,
            "search is bounded by the limit"
        );
    }

    #[test]
    fn slide_list_is_none_for_an_unknown_deck() {
        let lib = DeckLibrary::load(None);
        assert!(
            lib.slide_list(DeckId(999_999)).is_none(),
            "unknown deck → None"
        );
    }

    #[test]
    fn render_library_slide_is_bounded_and_matches_the_editor_theme() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;

        let fb = lib
            .render_slide(deck.id(), sid, 320, 180)
            .expect("a known deck+slide renders");
        assert!(
            fb.width() > 0 && fb.height() > 0,
            "never a blank/zero frame (NFR-024)"
        );
        assert!(
            fb.width() <= 320 && fb.height() <= 180,
            "honours the request"
        );

        // An oversized request is clamped — no unbounded allocation (no-leak).
        let big = lib
            .render_slide(deck.id(), sid, 5000, 5000)
            .expect("renders, clamped");
        assert!(
            big.width() <= 960 && big.height() <= 540,
            "dimensions clamped to the preview bound"
        );
    }

    #[test]
    fn render_library_slide_is_none_for_unknown_deck_or_slide() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;
        assert!(
            lib.render_slide(DeckId(999_999), sid, 320, 180).is_none(),
            "unknown deck → None"
        );
        assert!(
            lib.render_slide(deck.id(), SlideId(888_888), 320, 180)
                .is_none(),
            "unknown slide → None"
        );
    }

    #[test]
    fn present_payload_serialises_a_saved_deck_slide_or_none_for_unknown() {
        let mut lib = DeckLibrary::load(None);
        let deck = lib.create("Sermon");
        let sid = deck.slides()[0].id;
        let (slide_json, theme_json, next_json) = lib
            .present_payload(deck.id(), sid)
            .expect("a known deck+slide yields a present payload");
        assert!(
            slide_json.contains("\"id\""),
            "the slide serialises to JSON"
        );
        assert!(!theme_json.is_empty(), "the theme serialises");
        assert!(
            next_json.is_none(),
            "a single-slide deck has no coming slide (end of deck)"
        );
        assert!(
            lib.present_payload(DeckId(999_999), sid).is_none(),
            "unknown deck → None"
        );
        assert!(
            lib.present_payload(deck.id(), SlideId(888_888)).is_none(),
            "unknown slide → None"
        );
    }

    #[test]
    fn present_payload_supplies_the_coming_slide_before_the_last() {
        // Before the last slide, the payload carries the NEXT deck slide (Approach A) so the host
        // confidence/stage monitor's "next" is deck-aware.
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Deck");
        deck.add_slide(); // 2 slides now
        lib.store(&deck);
        let first = deck.slides()[0].id;
        let (_, _, next_json) = lib
            .present_payload(deck.id(), first)
            .expect("a known deck+slide yields a present payload");
        let next_json = next_json.expect("a non-last slide has a coming slide");
        let next: selahcue_present::AuthoredSlide =
            serde_json::from_str(&next_json).expect("next_json is a valid AuthoredSlide");
        assert_eq!(
            next.id,
            deck.slides()[1].id,
            "the coming slide is the NEXT slide in deck order"
        );
    }

    #[test]
    fn store_autosaves_the_open_deck_content() {
        let mut lib = DeckLibrary::load(None);
        let mut deck = lib.create("Deck");
        deck.add_slide(); // now 2 slides
        lib.store(&deck);
        assert_eq!(lib.get(deck.id()).unwrap().len(), 2, "the edit synced back");
    }

    #[test]
    fn rename_is_unique_and_duplicate_makes_an_independent_copy() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("Grace");
        let _b = lib.create("Grace copy"); // occupy the natural duplicate name
        let dup = lib.duplicate(a.id()).unwrap();
        assert_ne!(dup.id(), a.id());
        assert_eq!(dup.name, "Grace copy (2)", "copy name avoids the taken one");
        // Rename to an existing name → uniquified; renaming to its own name is a no-op.
        let applied = lib.rename(dup.id(), "Grace").unwrap();
        assert_eq!(applied, "Grace (2)");
        assert_eq!(
            lib.rename(a.id(), "Grace").unwrap(),
            "Grace",
            "self-rename no-op"
        );
    }

    #[test]
    fn delete_removes_only_the_target() {
        let mut lib = DeckLibrary::load(None);
        let a = lib.create("A");
        let b = lib.create("B");
        assert!(lib.delete(a.id()));
        assert!(!lib.delete(a.id()), "second delete is a no-op");
        assert_eq!(lib.list().len(), 1);
        assert_eq!(lib.get(b.id()).unwrap().name, "B");
    }

    #[test]
    fn self_heals_missing_and_duplicate_ids_and_names_on_load() {
        // A tampered/legacy blob set: two decks with id 0, two sharing id 7, duplicate names.
        let db = selahcue_data::Database::open_in_memory().unwrap();
        deck_repo::save_one(&db, "Dup", r#"{"name":"Dup","slides":[],"next_id":1}"#).unwrap();
        // A second row can't share the PK name, so give it a distinct name but a colliding id.
        deck_repo::save_one(
            &db,
            "Seven A",
            r#"{"name":"Seven A","id":7,"slides":[],"next_id":1}"#,
        )
        .unwrap();
        deck_repo::save_one(
            &db,
            "Seven B",
            r#"{"name":"Seven B","id":7,"slides":[],"next_id":1}"#,
        )
        .unwrap();
        let lib = DeckLibrary::load(Some(db));
        let metas = lib.list();
        assert_eq!(metas.len(), 3);
        let ids: std::collections::HashSet<u64> = metas.iter().map(|m| m.id.0).collect();
        assert_eq!(ids.len(), 3, "all ids unique after heal");
        assert!(!ids.contains(&0), "no unassigned id remains");
        let names: std::collections::HashSet<&str> =
            metas.iter().map(|m| m.name.as_str()).collect();
        assert_eq!(names.len(), 3, "all names unique after heal");
    }

    #[test]
    fn adopt_keeping_a_nonzero_id_never_lets_a_later_mint_collide() {
        // Review regression: adopt keeps a deck's own non-zero id; the next mint must not return it.
        // `mint_id` self-heals past every existing id (mirrors SlideDeck::mint_id).
        let mut lib = DeckLibrary::load(None); // next_id starts at 1
        let mut d = SlideDeck::new("Kept");
        d.set_id(DeckId(1)); // non-zero, and equal to next_id
        let adopted = lib.adopt(d);
        assert_eq!(adopted.id(), DeckId(1), "adopt kept its own id");
        let created = lib.create("Fresh");
        assert_ne!(
            created.id(),
            adopted.id(),
            "the next mint jumps past the kept id — no collision"
        );
    }

    #[test]
    fn library_survives_a_reopen_of_the_same_db_file() {
        let dir = std::env::temp_dir().join(format!("selahcue-lib-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("lib.sqlite");
        let (grace_id, sermon_id);
        {
            let mut lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            let mut g = lib.create("Grace");
            g.add_slide();
            g.add_slide(); // 3 slides
            lib.store(&g);
            let s = lib.create("Sermon");
            grace_id = g.id();
            sermon_id = s.id();
        }
        {
            let lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            assert_eq!(lib.list().len(), 2, "both decks survived the reopen");
            assert_eq!(
                lib.get(grace_id).unwrap().len(),
                3,
                "Grace's 3 slides persisted"
            );
            assert!(lib.get(sermon_id).is_some(), "the stable id round-tripped");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    // --- adopt_with_policy (ADR-0024 decision 5) ------------------------------------------------

    /// A deck named `name` carrying `slides` slides — stands in for a parsed import.
    fn incoming(name: &str, slides: usize) -> SlideDeck {
        let mut d = SlideDeck::new(name);
        for _ in 0..slides {
            d.add_slide();
        }
        d
    }

    #[test]
    fn replace_updates_in_place_preserving_the_deck_id_that_plan_items_link() {
        // FINDING-LIB-07 / 86ak196cr: the id is what `ItemContent::Deck { deck_id }` holds. If a
        // replace re-mints it, every plan link silently resolves to nothing or to another deck.
        let mut lib = DeckLibrary::load(None);
        let original = lib.create("Sunday Service"); // 1 slide
        let id_before = original.id();
        assert_eq!(original.len(), 1);

        let replaced = lib
            .adopt_with_policy(
                incoming("Sunday Service", 7),
                NameCollisionPolicy::Replace,
                None,
            )
            .expect("replacing a non-live deck is allowed");

        assert_eq!(
            replaced.id(),
            id_before,
            "the DeckId is byte-identical — plan links survive"
        );
        assert_eq!(replaced.name, "Sunday Service", "no (n) suffix was minted");
        assert_eq!(lib.list().len(), 1, "replaced in place, not added beside");
        let stored = lib
            .get(id_before)
            .expect("the deck is still reachable by its ORIGINAL id");
        assert_eq!(stored.len(), 7, "the slides were swapped for the new ones");
        assert_eq!(stored.id(), id_before);
    }

    #[test]
    fn replace_against_the_live_deck_is_refused_and_mutates_nothing() {
        // "staging never changes Live" — refused outright, never queued (design §11.2 D).
        let mut lib = DeckLibrary::load(None);
        let live = lib.create("Sunday Service");
        let other = lib.create("Midweek");
        let before: Vec<DeckMeta> = lib.list();
        let live_content = lib.get(live.id()).expect("live deck present");
        let other_content = lib.get(other.id()).expect("other deck present");

        let err = lib
            .adopt_with_policy(
                incoming("Sunday Service", 42),
                NameCollisionPolicy::Replace,
                Some(live.id()),
            )
            .expect_err("replacing the deck on the audience output is refused");
        assert_eq!(err, AdoptError::TargetIsLive);

        assert_eq!(lib.list(), before, "deck list, ids and names are unchanged");
        assert_eq!(
            lib.get(live.id()).as_ref(),
            Some(&live_content),
            "the live deck's content is untouched"
        );
        assert_eq!(
            lib.get(other.id()).as_ref(),
            Some(&other_content),
            "no collateral change"
        );
    }

    #[test]
    fn replace_targets_the_name_holder_and_cannot_corrupt_a_different_deck() {
        // The imported deck carries ANOTHER library deck's id. Replace resolves the target by NAME
        // and keys the write on that target's id, so the id it happened to carry is irrelevant.
        let mut lib = DeckLibrary::load(None);
        let sermon = lib.create("Sermon");
        let mut notes = lib.create("Notes");
        notes.add_slide();
        notes.add_slide(); // 3 slides
        lib.store(&notes);

        let mut hostile = incoming("Sermon", 5);
        hostile.set_id(notes.id()); // claims to BE the other deck

        let replaced = lib
            .adopt_with_policy(hostile, NameCollisionPolicy::Replace, None)
            .expect("replace proceeds");

        assert_eq!(
            replaced.id(),
            sermon.id(),
            "resolved by name — not by the id the incoming deck claimed"
        );
        assert_eq!(lib.get(sermon.id()).map(|d| d.len()), Some(5));
        let survivor = lib.get(notes.id()).expect("the other deck still exists");
        assert_eq!(survivor.name, "Notes", "its name is intact");
        assert_eq!(survivor.len(), 3, "its slides are intact");
        assert_eq!(lib.list().len(), 2, "nothing added, nothing lost");
    }

    #[test]
    fn replace_deck_with_an_unknown_target_is_refused_and_mutates_nothing() {
        // The deck the caller meant to replace was deleted while the import parsed.
        let mut lib = DeckLibrary::load(None);
        let keep = lib.create("Sermon");
        let before = lib.list();
        let err = lib
            .replace_deck(DeckId(999_999), incoming("Sermon", 3), None)
            .expect_err("an unknown target is refused, not adopted as a new deck");
        assert_eq!(err, AdoptError::UnknownTarget);
        assert_eq!(lib.list(), before);
        assert_eq!(lib.get(keep.id()).map(|d| d.len()), Some(1));
    }

    #[test]
    fn keep_both_suffixes_and_fail_errors_on_a_taken_name() {
        let mut lib = DeckLibrary::load(None);
        lib.create("Sunday Service");

        let kept = lib
            .adopt_with_policy(
                incoming("Sunday Service", 4),
                NameCollisionPolicy::KeepBoth,
                None,
            )
            .expect("KeepBoth never refuses");
        assert_eq!(kept.name, "Sunday Service (2)", "today's uniquify path");
        assert_eq!(lib.list().len(), 2);

        let err = lib
            .adopt_with_policy(
                incoming("Sunday Service", 4),
                NameCollisionPolicy::Fail,
                None,
            )
            .expect_err("Fail refuses a taken name");
        assert_eq!(err, AdoptError::NameTaken);
        assert_eq!(lib.list().len(), 2, "the refusal added nothing");
    }

    #[test]
    fn a_free_name_is_adopted_identically_under_every_policy() {
        // A policy is a collision RULE, not a mode: with no collision all three agree exactly.
        let outcome = |policy: NameCollisionPolicy| {
            let mut lib = DeckLibrary::load(None);
            lib.create("Occupied");
            let adopted = lib
                .adopt_with_policy(incoming("Fresh", 3), policy, None)
                .expect("a free name never refuses");
            (
                adopted.id(),
                adopted.name.clone(),
                adopted.len(),
                lib.list(),
            )
        };
        let keep_both = outcome(NameCollisionPolicy::KeepBoth);
        assert_eq!(keep_both.1, "Fresh", "adopted under the name it carried");
        assert_eq!(keep_both, outcome(NameCollisionPolicy::Replace));
        assert_eq!(keep_both, outcome(NameCollisionPolicy::Fail));
    }

    #[test]
    fn adopt_is_exactly_adopt_with_policy_keep_both() {
        // The no-regression gate for every pre-existing `adopt` caller: same ids, same names, same
        // list, on both a free and a taken name.
        let via_adopt = {
            let mut lib = DeckLibrary::load(None);
            lib.create("Sermon");
            let a = lib.adopt(incoming("Sermon", 2)); // taken
            let b = lib.adopt(incoming("Fresh", 1)); // free
            let c = lib.adopt(incoming("   ", 1)); // blank → fallback name
            (a.id(), a.name, b.id(), b.name, c.id(), c.name, lib.list())
        };
        let via_policy = {
            let mut lib = DeckLibrary::load(None);
            lib.create("Sermon");
            let p = NameCollisionPolicy::KeepBoth;
            let a = lib
                .adopt_with_policy(incoming("Sermon", 2), p, None)
                .expect("KeepBoth never refuses");
            let b = lib
                .adopt_with_policy(incoming("Fresh", 1), p, None)
                .expect("KeepBoth never refuses");
            let c = lib
                .adopt_with_policy(incoming("   ", 1), p, None)
                .expect("KeepBoth never refuses");
            (a.id(), a.name, b.id(), b.name, c.id(), c.name, lib.list())
        };
        assert_eq!(via_adopt, via_policy);
    }

    #[test]
    fn replace_upserts_the_same_persisted_row_and_survives_a_reopen() {
        // The persistence half of FINDING-LIB-07: the deck table is keyed by NAME, so a replace must
        // update that row rather than orphan it and write a second one.
        let dir = std::env::temp_dir().join(format!(
            "selahcue-lib-replace-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("lib.sqlite");
        let id_before;
        {
            let mut lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            let original = lib.create("Sunday Service");
            id_before = original.id();
            lib.adopt_with_policy(
                incoming("Sunday Service", 9),
                NameCollisionPolicy::Replace,
                None,
            )
            .expect("replace proceeds");
        }
        {
            let lib = DeckLibrary::load(Some(selahcue_data::Database::open(&path).unwrap()));
            assert_eq!(
                lib.list().len(),
                1,
                "one row, not two — the row was updated"
            );
            let stored = lib
                .get(id_before)
                .expect("the ORIGINAL DeckId round-tripped through persistence");
            assert_eq!(stored.len(), 9, "the replacement content persisted");
            assert_eq!(stored.name, "Sunday Service");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn adopt_assigns_an_id_to_an_existing_deck() {
        let mut lib = DeckLibrary::load(None);
        let mut demo = SlideDeck::new("Sermon: Grace That Feeds");
        demo.add_slide();
        assert_eq!(demo.id().0, 0, "precondition: unassigned");
        let adopted = lib.adopt(demo);
        assert_ne!(adopted.id().0, 0, "adopt assigned a stable id");
        assert_eq!(lib.list().len(), 1);
        assert_eq!(lib.get(adopted.id()).unwrap().len(), 1, "kept its slide");
    }
}
