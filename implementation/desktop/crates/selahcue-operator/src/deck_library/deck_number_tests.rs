//! A deck number that was ever issued is never issued again (17tnw2b9arx - ADR-0031 "Known limits").
//!
//! The defect needs a RESTART: the undo trash is memory-only and the counter was recomputed at load
//! as "highest surviving number + 1", so a number retired by a delete came back for the next deck and
//! a plan link that still held it silently showed that other deck. Every test here therefore uses a
//! real database FILE and drops and reloads the library between steps. Each one fails when the
//! high-water mark is removed (mutation-checked; see the PR).

#![allow(clippy::unwrap_used)]

use super::*;
use selahcue_core::deck_ref::DeckLinkMatch;
use selahcue_core::plan::{ItemKind, ServicePlan};

// --- fixtures --------------------------------------------------------------------------------

/// A directory removed on drop, holding one sqlite file: the "machine" that survives restarts.
struct Machine(std::path::PathBuf);

impl Machine {
    fn new(tag: &str) -> Self {
        let dir =
            std::env::temp_dir().join(format!("selahcue-decknum-{}-{tag}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        Machine(dir)
    }

    fn db(&self) -> Database {
        Database::open(self.0.join("lib.sqlite")).unwrap()
    }

    /// Start the app: load the library from the persisted store, as `main.rs` does at launch.
    fn launch(&self) -> DeckLibrary {
        DeckLibrary::load(Some(self.db()))
    }

    /// The mark as stored on disk, read through a separate connection.
    fn mark(&self) -> u64 {
        deck_repo::high_water(&self.db()).unwrap()
    }

    /// Make the store look like one written by a build from before the mark existed.
    fn forget_the_mark(&self) {
        self.db()
            .conn()
            .execute("DELETE FROM deck_id_counter", [])
            .unwrap();
        assert_eq!(self.mark(), 0, "premise: the mark is gone");
    }

    fn rows(&self, table: &str) -> i64 {
        self.db()
            .conn()
            .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |r| r.get(0))
            .unwrap()
    }
}

impl Drop for Machine {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn id_of(lib: &DeckLibrary, name: &str) -> DeckId {
    lib.list().into_iter().find(|m| m.name == name).unwrap().id
}

/// A plan with one slide-group item linked to deck `name` in `lib`.
fn plan_linking(lib: &DeckLibrary, name: &str) -> ServicePlan {
    let id = id_of(lib, name);
    let mut plan = ServicePlan::new("Sunday");
    let item = plan.add_item(ItemKind::SlideGroup, name);
    plan.set_item_content(
        item,
        Some(ItemContent::Deck {
            deck_id: id.0,
            slide_count: lib.get(id).map(|d| d.len() as u32),
            label: Some(name.to_string()),
        }),
    )
    .unwrap();
    plan
}

/// The plan items the console would flag "Presentation missing" against `lib` (FR-007).
fn missing_items(plan: &ServicePlan, lib: &DeckLibrary) -> usize {
    plan.unresolved_content(|_, _| true, |id| lib.get(DeckId(id)).is_some(), |_| true)
        .len()
}

/// The ticket's scenario up to and including the restart: Welcome, Songs and Communion are decks
/// 1, 2 and 3; Communion goes into a plan item; Communion is deleted; the app restarts.
fn communion_deleted_then_restarted(m: &Machine) -> (DeckLibrary, ServicePlan) {
    let plan = {
        let mut lib = m.launch();
        lib.create("Welcome");
        lib.create("Songs");
        lib.create("Communion");
        let plan = plan_linking(&lib, "Communion");
        assert_eq!(
            id_of(&lib, "Communion"),
            DeckId(3),
            "premise: Communion is deck 3"
        );
        assert!(lib.delete(DeckId(3)));
        plan
    }; // the library is dropped: the app quits, and the memory-only undo trash goes with it
    (m.launch(), plan)
}

// --- the acceptance tests ----------------------------------------------------------------------

#[test]
fn a_deleted_decks_number_is_not_given_to_the_next_deck_after_a_restart() {
    let m = Machine::new("reuse");
    let (mut lib, _) = communion_deleted_then_restarted(&m);

    let youth = lib.create("Youth Night");

    assert_ne!(
        youth.id(),
        DeckId(3),
        "deck 3 was issued to Communion and is retired for good"
    );
    assert_eq!(
        youth.id(),
        DeckId(4),
        "numbering carries on past the highest number ever issued"
    );
}

#[test]
fn the_plan_link_to_a_deleted_deck_stays_missing_after_a_restart_and_after_new_decks() {
    let m = Machine::new("missing");
    let (mut lib, plan) = communion_deleted_then_restarted(&m);
    assert_eq!(
        missing_items(&plan, &lib),
        1,
        "missing straight after the restart"
    );

    lib.create("Youth Night");
    lib.create("Baptism");

    assert_eq!(
        missing_items(&plan, &lib),
        1,
        "still missing once new decks exist: the old number resolves to nothing, never to Youth Night"
    );
    assert!(lib.get(DeckId(3)).is_none());
    assert!(
        lib.slide_list(DeckId(3)).is_none(),
        "the Live Console picker renders its missing state for the dead number (FR-007)"
    );
    // The other half of RULE-LIB-XFER-01: the link can no longer pick up Youth Night's identity.
    let link = lib
        .export_link(plan.items()[0].content.as_ref().unwrap())
        .unwrap();
    assert_eq!(
        link.uid, None,
        "the exported link must not carry any deck's identity"
    );
    let (_, how) = lib.import_link(&link);
    assert_eq!(how, DeckLinkMatch::NotInLibrary);
    // ...and a restart after the new decks changes nothing.
    drop(lib);
    assert_eq!(missing_items(&plan, &m.launch()), 1);
}

#[test]
fn a_library_whose_mark_is_missing_still_loads_and_does_not_reuse_a_surviving_number() {
    // A store from a build that did not know the mark: decks on disk, no mark row.
    let m = Machine::new("old-build");
    {
        let mut lib = m.launch();
        lib.create("Welcome");
        lib.create("Songs");
        lib.create("Communion");
    }
    m.forget_the_mark();

    let mut lib = m.launch();

    assert_eq!(lib.list().len(), 3, "every deck loads");
    assert_eq!(
        m.mark(),
        3,
        "the first load sets the mark to the highest surviving number"
    );
    assert_eq!(lib.create("Youth Night").id(), DeckId(4));
}

#[test]
fn a_library_written_before_the_mark_table_existed_loads_and_migrates() {
    // The same, one level deeper: a v24 database, which does not even have the table.
    let m = Machine::new("v24");
    {
        let mut lib = m.launch();
        lib.create("Welcome");
        lib.create("Songs");
    }
    m.db()
        .conn()
        .execute_batch("DROP TABLE deck_id_counter; PRAGMA user_version = 24;")
        .unwrap();

    let mut lib = m.launch();

    assert_eq!(lib.list().len(), 2);
    assert_eq!(m.mark(), 2);
    assert_eq!(lib.create("Communion").id(), DeckId(3));
}

#[test]
fn a_deleted_number_stays_retired_even_when_the_mark_is_all_that_remembers_it() {
    // Three launches: issue, delete, then create twice. The number is held by nothing but the mark.
    let m = Machine::new("only-the-mark");
    {
        let mut lib = m.launch();
        lib.create("A");
        lib.create("B");
        lib.create("C");
        lib.delete(DeckId(3));
        lib.delete(DeckId(2));
    }
    let mut lib = m.launch();
    assert_eq!(lib.list().len(), 1, "only deck 1 survives");
    assert_eq!(
        lib.create("D").id(),
        DeckId(4),
        "2 and 3 are retired, not just 3"
    );
    drop(lib);
    assert_eq!(m.launch().create("E").id(), DeckId(5));
}

// --- the mark's own contract -------------------------------------------------------------------

#[test]
fn loading_never_lowers_a_mark_that_is_ahead_of_every_surviving_deck() {
    let m = Machine::new("never-lowers");
    {
        let mut lib = m.launch();
        lib.create("Only");
    }
    deck_repo::raise_high_water(&m.db(), 10).unwrap();

    let mut lib = m.launch();

    assert_eq!(
        m.mark(),
        10,
        "a load must not pull the mark down to the surviving deck's 1"
    );
    assert_eq!(lib.create("Next").id(), DeckId(11));
    assert_eq!(m.mark(), 11);
}

#[test]
fn loading_raises_a_mark_that_is_behind_the_surviving_decks() {
    let m = Machine::new("behind");
    {
        let mut lib = m.launch();
        for n in ["A", "B", "C", "D", "E"] {
            lib.create(n);
        }
    }
    m.forget_the_mark();
    deck_repo::raise_high_water(&m.db(), 2).unwrap();

    let mut lib = m.launch();

    assert_eq!(m.mark(), 5, "raised to the highest surviving number");
    assert_eq!(lib.create("F").id(), DeckId(6));
}

#[test]
fn an_empty_library_with_no_mark_loads_and_starts_at_one() {
    let m = Machine::new("fresh");
    let mut lib = m.launch();
    assert!(lib.is_empty());
    assert_eq!(m.mark(), 0, "nothing issued, nothing recorded");
    assert_eq!(lib.create("First").id(), DeckId(1));
    assert_eq!(m.mark(), 1);
}

#[test]
fn the_in_memory_fallback_keeps_numbers_unique_within_the_session() {
    // No database: the mark has nowhere to live, and the in-session counter alone must still hold.
    let mut lib = DeckLibrary::load(None);
    lib.create("A");
    lib.create("B");
    lib.delete(DeckId(2));
    assert_eq!(lib.create("C").id(), DeckId(3));
}

/// Every path that writes a deck row must raise the mark with it. Each is started from "no mark
/// recorded" so that a path that forgot would leave the mark behind the number it just wrote.
mod every_writer_raises_the_mark {
    use super::*;

    /// `tag` must be unique per test: tests run in parallel and each owns its own directory.
    fn fresh_with(tag: &str, names: &[&str]) -> (Machine, DeckLibrary) {
        let m = Machine::new(&format!("writer-{tag}"));
        let mut lib = m.launch();
        for n in names {
            lib.create(n);
        }
        m.forget_the_mark();
        (m, lib)
    }

    #[test]
    fn create() {
        let (m, mut lib) = fresh_with("create", &["A", "B"]);
        let d = lib.create("C");
        assert_eq!(m.mark(), d.id().0);
    }

    #[test]
    fn duplicate() {
        let (m, mut lib) = fresh_with("duplicate", &["A", "B"]);
        let copy = lib.duplicate(DeckId(1)).unwrap();
        assert_eq!(m.mark(), copy.id().0);
    }

    #[test]
    fn adopt_keeps_a_high_incoming_number_retired_too() {
        let (m, mut lib) = fresh_with("adopt_keeps_a_high_incoming_number_retired_too", &["A"]);
        let mut incoming = SlideDeck::new("Imported".to_string());
        incoming.set_id(DeckId(40)); // a free, non-zero number: adopt keeps it
        let adopted = lib.adopt(incoming);
        assert_eq!(adopted.id(), DeckId(40));
        assert_eq!(m.mark(), 40);
        drop(lib);
        assert_eq!(m.launch().create("After").id(), DeckId(41));
    }

    #[test]
    fn store() {
        let (m, mut lib) = fresh_with("store", &["A", "B"]);
        let mut deck = lib.get(DeckId(2)).unwrap();
        deck.add_slide();
        lib.store(&deck);
        assert_eq!(m.mark(), 2);
    }

    #[test]
    fn store_with_a_rename() {
        let (m, mut lib) = fresh_with("store_with_a_rename", &["A", "B"]);
        let mut deck = lib.get(DeckId(2)).unwrap();
        deck.name = "B renamed".to_string();
        lib.store(&deck);
        assert_eq!(m.mark(), 2);
    }

    #[test]
    fn rename() {
        let (m, mut lib) = fresh_with("rename", &["A", "B"]);
        lib.rename(DeckId(2), "B renamed").unwrap();
        assert_eq!(m.mark(), 2);
    }

    #[test]
    fn replace_deck() {
        let (m, mut lib) = fresh_with("replace_deck", &["A", "B"]);
        lib.replace_deck(DeckId(2), SlideDeck::new("whatever".to_string()), None)
            .unwrap();
        assert_eq!(m.mark(), 2);
    }

    #[test]
    fn restore_from_the_undo_trash() {
        let (m, mut lib) = fresh_with("restore_from_the_undo_trash", &["A", "B"]);
        assert!(lib.delete(DeckId(2)));
        m.forget_the_mark();
        lib.restore(DeckId(2)).unwrap();
        assert_eq!(m.mark(), 2);
    }
}

// --- bounded growth ----------------------------------------------------------------------------

#[test]
fn repeated_create_and_delete_cycles_do_not_grow_the_persisted_state() {
    // The mark is ONE integer in ONE row. Churning decks must leave exactly that, plus the decks
    // that still exist: no row per issued number, no log, no accumulating tombstones.
    let m = Machine::new("bounded");
    let mut lib = m.launch();
    lib.create("Keeper");
    let cycles = 250u64;
    for n in 0..cycles {
        let d = lib.create(&format!("Churn {n}"));
        assert!(lib.delete(d.id()));
    }
    assert_eq!(lib.list().len(), 1, "only the keeper remains in memory");
    assert_eq!(m.rows("deck"), 1, "and on disk");
    assert_eq!(
        m.rows("deck_id_counter"),
        1,
        "the mark never grows past one row"
    );
    assert_eq!(
        m.mark(),
        cycles + 1,
        "...while still recording every number ever issued"
    );
    // The undo trash stays bounded too (it is the only other place a deleted deck lingers).
    assert!(
        lib.restorable().len() <= selahcue_present::MAX_TRASH_ENTRIES,
        "the trash is capped, not one entry per delete"
    );
    // Across a restart the whole history collapses to that one integer.
    drop(lib);
    let mut lib = m.launch();
    assert_eq!(m.rows("deck_id_counter"), 1);
    assert_eq!(lib.create("After").id(), DeckId(cycles + 2));
}
