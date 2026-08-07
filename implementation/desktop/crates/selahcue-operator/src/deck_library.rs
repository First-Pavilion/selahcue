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
use selahcue_present::{DeckId, SlideDeck};

/// Lightweight row for the Library list (`deck_list`) — never carries the slide bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeckMeta {
    pub id: DeckId,
    pub name: String,
    pub slides: usize,
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
