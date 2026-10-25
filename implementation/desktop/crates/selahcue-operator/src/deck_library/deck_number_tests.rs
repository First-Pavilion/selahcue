//! A deck number that was ever issued is never issued again (17tnw2b9arx - ADR-0031 "Known limits").
//!
//! The defect needs a RESTART: the undo trash is memory-only and the counter was recomputed at load
//! as "highest surviving number + 1", so a number retired by a delete came back for the next deck and
//! a plan link that still held it silently showed that other deck. Every test here therefore uses a
//! real database FILE and drops and reloads the library between steps. Every test fails when the
//! high-water mark is removed, except the in-memory control and the in-session adopt-versus-undo-trash
//! test, which the in-memory counter alone satisfies (mutation-checked; see the PR).

#![allow(clippy::unwrap_used)]

use super::*;
use selahcue_core::deck_ref::DeckLinkMatch;
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::deck_repo::MAX_DECK_NUMBER;

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

/// A deck row as a build from before the mark stored it.
fn legacy_row(id: u64, name: &str) -> String {
    format!(r#"{{"name":"{name}","id":{id},"slides":[{{"id":1}}],"next_id":2}}"#)
}

/// Make the database refuse every write to the mark, as a full disk or a long lock would.
fn refuse_mark_writes(m: &Machine) {
    m.db()
        .conn()
        .execute_batch(
            "CREATE TRIGGER refuse_mark_insert BEFORE INSERT ON deck_id_counter
             BEGIN SELECT RAISE(ABORT, 'disk says no'); END;
             CREATE TRIGGER refuse_mark_update BEFORE UPDATE ON deck_id_counter
             BEGIN SELECT RAISE(ABORT, 'disk says no'); END;",
        )
        .unwrap();
}

fn accept_mark_writes(m: &Machine) {
    m.db()
        .conn()
        .execute_batch("DROP TRIGGER refuse_mark_insert; DROP TRIGGER refuse_mark_update;")
        .unwrap();
}

/// Put a value in the mark that the table's CHECK refuses, as a damaged file or a hand edit could.
fn corrupt_the_mark(m: &Machine, literal: &str) {
    m.db()
        .conn()
        .execute_batch(&format!(
            "PRAGMA ignore_check_constraints = ON;
             DELETE FROM deck_id_counter;
             INSERT INTO deck_id_counter (id, high_water) VALUES (1, {literal});
             PRAGMA ignore_check_constraints = OFF;"
        ))
        .unwrap();
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

/// Shadow F1: after a restart the undo trash is gone, so nothing but the mark remembers that 3 was
/// issued. An adopted deck that happens to carry 3 must NOT get it back, and the plan link to the
/// deleted deck must stay missing.
#[test]
fn adopting_a_deck_that_carries_a_retired_number_after_a_restart_gets_a_new_number() {
    let m = Machine::new("adopt-after-restart");
    let (mut lib, plan) = communion_deleted_then_restarted(&m);
    let mut incoming = SlideDeck::new("Imported".to_string());
    incoming.set_id(DeckId(3));

    let adopted = lib.adopt(incoming);

    assert_ne!(adopted.id(), DeckId(3));
    assert_eq!(adopted.id(), DeckId(4));
    assert_eq!(
        missing_items(&plan, &lib),
        1,
        "the link to deleted deck 3 stays missing"
    );
    assert!(lib.get(DeckId(3)).is_none());
}

/// The in-session variant: while Communion (3) sits in the undo trash an adopted deck carrying 3 must
/// not take the number, or "Undo delete" would then put TWO decks under 3. `restore` needs no change of
/// its own: every trashed deck's number is below the counter, and adopt no longer takes such a number.
#[test]
fn adopting_while_a_deck_is_in_the_undo_trash_never_leaves_two_decks_with_one_number() {
    let m = Machine::new("adopt-vs-trash");
    let mut lib = m.launch();
    lib.create("Welcome");
    lib.create("Songs");
    lib.create("Communion");
    assert!(lib.delete(DeckId(3))); // now in the memory-only undo trash
    let mut incoming = SlideDeck::new("Imported".to_string());
    incoming.set_id(DeckId(3));

    let adopted = lib.adopt(incoming);
    assert_ne!(adopted.id(), DeckId(3));
    assert_eq!(lib.restore(DeckId(3)).unwrap(), "Communion");

    let mut ids: Vec<u64> = lib.list().iter().map(|d| d.id.0).collect();
    ids.sort_unstable();
    ids.dedup();
    assert_eq!(ids.len(), lib.list().len(), "no two decks share a number");
    assert_eq!(
        id_of(&lib, "Communion"),
        DeckId(3),
        "Undo delete kept its own number"
    );
    drop(lib);
    let lib = m.launch();
    let mut ids: Vec<u64> = lib.list().iter().map(|d| d.id.0).collect();
    ids.sort_unstable();
    ids.dedup();
    assert_eq!(
        ids.len(),
        lib.list().len(),
        "and it is still true after a restart"
    );
}

/// Quinn Q-1: nothing used to test "every deck deleted, then restart". With no surviving deck there
/// is no row to count from, so the mark is the ONLY thing standing between the next deck and number 1.
#[test]
fn deleting_every_deck_and_restarting_does_not_restart_numbering_at_one() {
    let m = Machine::new("all-deleted");
    {
        let mut lib = m.launch();
        lib.create("A");
        lib.create("B");
        assert!(lib.delete(DeckId(1)));
        assert!(lib.delete(DeckId(2)));
    }
    let mut lib = m.launch();
    assert!(lib.is_empty());
    // The counter itself starts past the mark (white box: it is only a hint, because the database
    // also checks every new number against the mark, so without this a seed that ignored the mark
    // when no deck survives would pass the line below on the database's strength alone).
    assert_eq!(
        lib.next_id, 3,
        "the counter is seeded from the mark when no deck survives"
    );
    assert_eq!(
        lib.create("C").id(),
        DeckId(3),
        "1 and 2 are retired, not reissued"
    );
}

/// Quinn Q-2, Shadow F5, Cody M2: a deck row that FAILS to write (disk full, database locked past the
/// busy timeout) used to leave the mark behind the number the library had just handed out. The plan is
/// stored by the host in a different file, so a link to that number can be saved while the deck is not;
/// after a restart the number was reissued and the link showed the wrong deck. A number must therefore
/// be recorded durably BEFORE it is issued.
#[test]
fn a_number_whose_deck_write_failed_is_not_reissued_after_a_restart() {
    let m = Machine::new("failed-write");
    let communion_number;
    {
        let mut lib = m.launch();
        lib.create("Welcome");
        lib.create("Songs");
        // From here the database refuses every new deck row, as a full disk or a long lock would.
        m.db()
            .conn()
            .execute_batch(
                "CREATE TRIGGER refuse_deck_rows BEFORE INSERT ON deck
                 BEGIN SELECT RAISE(ABORT, 'disk says no'); END;",
            )
            .unwrap();
        communion_number = lib.create("Communion").id();
        assert_eq!(
            m.rows("deck"),
            2,
            "premise: Communion's row was never written"
        );
    }
    m.db()
        .conn()
        .execute_batch("DROP TRIGGER refuse_deck_rows;")
        .unwrap();

    let mut lib = m.launch();
    assert!(
        lib.get(communion_number).is_none(),
        "premise: Communion did not survive"
    );
    let youth = lib.create("Youth Night");

    assert_ne!(
        youth.id(),
        communion_number,
        "a number handed out in a session whose write failed must still never be reissued"
    );
}

// --- recording a number before issuing it (review round 1) ---------------------------------------

#[test]
fn when_the_database_will_not_record_a_number_nothing_is_created_and_nothing_is_skipped() {
    let m = Machine::new("refused");
    let mut lib = m.launch();
    lib.create("Welcome");
    lib.create("Songs");
    refuse_mark_writes(&m);

    assert_eq!(lib.try_create("Communion").unwrap_err(), NumberNotRecorded);
    assert_eq!(
        lib.duplicate(DeckId(1)).map(|d| d.id()),
        None,
        "a copy needs a number too"
    );
    assert_eq!(
        lib.try_adopt(SlideDeck::new("Imported".to_string()))
            .unwrap_err(),
        NumberNotRecorded
    );
    assert_eq!(
        lib.adopt_with_policy(
            SlideDeck::new("Imported".to_string()),
            NameCollisionPolicy::KeepBoth,
            None
        )
        .unwrap_err(),
        AdoptError::NumberNotRecorded
    );
    assert_eq!(lib.list().len(), 2, "no deck was added by any refused call");
    assert_eq!(m.rows("deck"), 2, "and no row was written");

    accept_mark_writes(&m);
    assert_eq!(
        lib.try_create("Communion").unwrap().id(),
        DeckId(3),
        "refusals issued nothing, so the next number is the one that would have been"
    );
}

#[test]
fn a_mark_that_cannot_be_read_refuses_new_decks_instead_of_counting_as_zero() {
    for literal in ["'abc'", "12.5", "x'00'"] {
        let m = Machine::new(&format!("unreadable-{}", literal.len()));
        {
            let mut lib = m.launch();
            lib.create("A");
            lib.create("B");
        }
        corrupt_the_mark(&m, literal);
        assert!(
            deck_repo::high_water(&m.db()).is_err(),
            "premise: {literal} cannot be read"
        );

        let mut lib = m.launch();

        assert_eq!(lib.list().len(), 2, "{literal}: the library still loads");
        assert_eq!(
            lib.try_create("C").unwrap_err(),
            NumberNotRecorded,
            "{literal}: an unreadable mark must refuse, not restart numbering from the surviving decks"
        );
        // Repaired (by hand: the table refuses to UPDATE a text value downward, so replace the row).
        m.db()
            .conn()
            .execute_batch(
                "DELETE FROM deck_id_counter; INSERT INTO deck_id_counter VALUES (1, 7);",
            )
            .unwrap();
        assert_eq!(
            lib.try_create("C").unwrap().id(),
            DeckId(8),
            "{literal}: past the repaired mark"
        );
    }
}

#[test]
fn two_libraries_on_one_database_file_are_never_issued_the_same_number() {
    // Two operator processes on one file (Shadow I4) each load a snapshot and keep a private counter.
    // The database issues the numbers, so the counters being stale no longer matters.
    let m = Machine::new("two-processes");
    let mut a = m.launch();
    let mut b = m.launch();
    let mut issued = Vec::new();
    for n in 0..10 {
        issued.push(a.create(&format!("From A {n}")).id().0);
        issued.push(b.create(&format!("From B {n}")).id().0);
    }
    let mut unique = issued.clone();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(
        unique.len(),
        issued.len(),
        "a number was issued twice: {issued:?}"
    );
    drop((a, b));
    assert_eq!(
        m.launch().list().len(),
        20,
        "every deck is on disk with its own number"
    );
}

// --- numbers above the JSON-safe ceiling (review round 1) ----------------------------------------

#[test]
fn a_deck_number_beyond_the_json_safe_ceiling_is_renumbered_and_never_recorded() {
    // The webview carries deck numbers as JSON numbers, which hold integers exactly only up to
    // 2^53 - 1: above that two different decks alias. Such a row is treated like a zero or duplicate
    // number, and the mark never goes above the ceiling because of it.
    let m = Machine::new("ceiling");
    {
        let db = m.db();
        deck_repo::save_one(&db, "Small", &legacy_row(1, "Small")).unwrap();
        deck_repo::save_one(&db, "Huge", &legacy_row(1 << 63, "Huge")).unwrap();
        deck_repo::save_one(
            &db,
            "JustOver",
            &legacy_row(MAX_DECK_NUMBER + 1, "JustOver"),
        )
        .unwrap();
    }

    let mut lib = m.launch();

    let mut ids: Vec<u64> = lib.list().iter().map(|d| d.id.0).collect();
    ids.sort_unstable();
    assert_eq!(
        ids,
        vec![1, 2, 3],
        "the two out-of-range decks were given the next small numbers"
    );
    assert!(ids.iter().all(|id| *id <= MAX_DECK_NUMBER));
    assert_eq!(
        m.mark(),
        3,
        "the mark follows the repaired numbers, not the bogus ones"
    );
    assert_eq!(lib.create("Next").id(), DeckId(4));
}

#[test]
fn when_the_numbers_run_out_creating_a_deck_is_refused_without_a_panic_or_a_wrap() {
    let m = Machine::new("exhausted");
    {
        let db = m.db();
        deck_repo::save_one(&db, "Last", &legacy_row(MAX_DECK_NUMBER, "Last")).unwrap();
    }
    let mut lib = m.launch();
    assert_eq!(m.mark(), MAX_DECK_NUMBER);

    assert_eq!(
        lib.try_create("One too many").unwrap_err(),
        NumberNotRecorded
    );
    assert_eq!(lib.list().len(), 1);
    assert_eq!(
        m.mark(),
        MAX_DECK_NUMBER,
        "the mark never goes above the ceiling"
    );
    // The in-memory fallback is bounded the same way.
    let mut memory = DeckLibrary::load(None);
    memory.next_id = MAX_DECK_NUMBER;
    assert_eq!(
        memory.try_create("Last").unwrap().id(),
        DeckId(MAX_DECK_NUMBER)
    );
    assert_eq!(memory.try_create("Past it").unwrap_err(), NumberNotRecorded);
}

// --- load-time write discipline (review round 1) -------------------------------------------------

#[test]
fn a_load_whose_identity_backfill_gave_up_does_not_attempt_a_second_write() {
    // With the database refusing writes, the backfill stops after its first failed write so startup
    // does not wait out the busy timeout once per deck. Raising the mark is one more write: it must
    // be skipped too (Vera V-02), or a locked database costs the timeout twice.
    let m = Machine::new("gave-up");
    {
        let db = m.db();
        for (id, name) in [(1, "One"), (2, "Two"), (3, "Three")] {
            deck_repo::save_one(&db, name, &legacy_row(id, name)).unwrap();
        }
        // Row updates fail (the backfill rewrites each legacy row), mark writes would succeed.
        db.conn()
            .execute_batch(
                "CREATE TRIGGER refuse_deck_updates BEFORE UPDATE ON deck
                 BEGIN SELECT RAISE(ABORT, 'locked'); END;",
            )
            .unwrap();
    }

    let (lib, stats) = DeckLibrary::load_reporting(Some(m.db()), os_entropy);

    assert_eq!(
        stats.failed, 1,
        "premise: the backfill hit a failed write and gave up"
    );
    assert_eq!(lib.list().len(), 3);
    assert_eq!(
        m.mark(),
        0,
        "no further write was attempted after the backfill gave up"
    );
    drop(lib);
    m.db()
        .conn()
        .execute_batch("DROP TRIGGER refuse_deck_updates;")
        .unwrap();
    let _ = m.launch();
    assert_eq!(m.mark(), 3, "the next launch records it");
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

    /// `adopt` keeps an incoming number only from BEYOND every number issued here (>= the counter,
    /// which is already past the mark, every live deck and the undo trash). A number below that was
    /// issued before -- possibly to a deck that was deleted and is still linked from a plan -- so
    /// handing it back would reopen the very hole this ticket closes. (Before this rule adopt kept
    /// any number no LIVE deck held, which could return a retired one; Shadow F1, Cody M3.)
    #[test]
    fn adopt_keeps_a_number_from_beyond_everything_issued_and_retires_it() {
        let (m, mut lib) = fresh_with("adopt_keeps_beyond", &["A"]);
        let mut incoming = SlideDeck::new("Imported".to_string());
        incoming.set_id(DeckId(40)); // well beyond the counter (2): nothing was ever issued as 40
        let adopted = lib.adopt(incoming);
        assert_eq!(adopted.id(), DeckId(40));
        assert_eq!(m.mark(), 40);
        drop(lib);
        assert_eq!(m.launch().create("After").id(), DeckId(41));
    }

    #[test]
    fn adopt_does_not_reuse_a_number_that_was_issued_and_deleted() {
        let (m, mut lib) = fresh_with("adopt_retired", &["A", "B", "C"]);
        lib.delete(DeckId(3));
        let mut incoming = SlideDeck::new("Imported".to_string());
        incoming.set_id(DeckId(3));
        let adopted = lib.adopt(incoming);
        assert_ne!(adopted.id(), DeckId(3), "3 was issued to C; it is retired");
        assert_eq!(adopted.id(), DeckId(4));
        assert_eq!(m.mark(), 4);
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

/// The row count of every table in the database: what "persisted state" is made of.
fn all_table_rows(m: &Machine) -> std::collections::BTreeMap<String, i64> {
    let db = m.db();
    let names: Vec<String> = db
        .conn()
        .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        .unwrap()
        .query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect();
    names.into_iter().map(|n| (n.clone(), m.rows(&n))).collect()
}

fn mark_columns(m: &Machine) -> Vec<String> {
    m.db()
        .conn()
        .prepare("SELECT name FROM pragma_table_info('deck_id_counter') ORDER BY cid")
        .unwrap()
        .query_map([], |r| r.get(0))
        .unwrap()
        .map(Result::unwrap)
        .collect()
}

#[test]
fn repeated_create_and_delete_cycles_do_not_grow_the_persisted_state() {
    // The mark is ONE integer in ONE row. Churning decks must leave exactly that, plus the decks
    // that still exist: no row per issued number, no log, no accumulating tombstones. Counting two
    // tables would miss a log table or a growing column, so EVERY table's row count is compared
    // before and after, and the mark's columns are pinned (Vera V-01).
    let m = Machine::new("bounded");
    let mut lib = m.launch();
    lib.create("Keeper");
    let before = all_table_rows(&m);
    assert_eq!(mark_columns(&m), ["id", "high_water"]);
    let cycles = 250u64;
    for n in 0..cycles {
        let d = lib.create(&format!("Churn {n}"));
        assert!(lib.delete(d.id()));
    }
    assert_eq!(lib.list().len(), 1, "only the keeper remains in memory");
    assert_eq!(
        all_table_rows(&m),
        before,
        "no table grew: the churn left no trace but the mark's value"
    );
    assert_eq!(
        mark_columns(&m),
        ["id", "high_water"],
        "the mark holds exactly one integer"
    );
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
    assert_eq!(all_table_rows(&m), before);
    assert_eq!(lib.create("After").id(), DeckId(cycles + 2));
}
