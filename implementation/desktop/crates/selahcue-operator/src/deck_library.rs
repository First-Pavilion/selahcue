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
    pub fn adopt(&mut self, mut deck: SlideDeck) -> SlideDeck {
        if deck.id().0 == 0 || self.index_of(deck.id()).is_some() {
            let id = self.mint_id();
            deck.set_id(id);
        }
        let base = if deck.name.trim().is_empty() {
            "Untitled presentation"
        } else {
            deck.name.trim()
        };
        let unique = uniquify(base, &self.name_set());
        deck.name = unique;
        self.persist_one(&deck);
        self.decks.push(deck.clone());
        deck
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
