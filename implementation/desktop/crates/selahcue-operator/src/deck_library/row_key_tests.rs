//! AWR: real SQLite rows and the production ordinary deck_open leave/store body.
//! Triggers detect even a byte-identical SQL rewrite of a sibling, not only lost content.
#![allow(clippy::unwrap_used)]
use super::*;
use crate::deck_workspace::DeckWorkspace;
use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU32, Ordering};

struct FileDb(std::path::PathBuf);
impl FileDb {
    fn new(rows: &[(&str, SlideDeck)]) -> Self {
        static SEQUENCE: AtomicU32 = AtomicU32::new(0);
        let path = std::env::temp_dir().join(format!(
            "awr-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::SeqCst)
        ));
        std::fs::create_dir_all(&path).unwrap();
        let this = Self(path);
        let db = this.open();
        for (key, deck) in rows {
            deck_repo::save_one(&db, key, &serde_json::to_string(deck).unwrap()).unwrap();
        }
        db.conn().execute_batch("CREATE TABLE awr_writes (row_key TEXT NOT NULL, op TEXT NOT NULL);
            CREATE TRIGGER awr_insert AFTER INSERT ON deck BEGIN INSERT INTO awr_writes VALUES (NEW.name, 'insert'); END;
            CREATE TRIGGER awr_update AFTER UPDATE ON deck BEGIN INSERT INTO awr_writes VALUES (NEW.name, 'update'); END;
            CREATE TRIGGER awr_delete AFTER DELETE ON deck BEGIN INSERT INTO awr_writes VALUES (OLD.name, 'delete'); END;").unwrap();
        this
    }
    fn open(&self) -> Database {
        Database::open(self.0.join("library.sqlite")).unwrap()
    }
    fn rows(&self) -> BTreeMap<String, String> {
        deck_repo::load_all(&self.open())
            .unwrap()
            .into_iter()
            .collect()
    }
    fn trace(&self) -> Vec<(String, String)> {
        let db = self.open();
        let mut query = db
            .conn()
            .prepare("SELECT row_key, op FROM awr_writes ORDER BY rowid")
            .unwrap();
        let rows = query
            .query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
            .unwrap()
            .map(Result::unwrap)
            .collect();
        rows
    }
    fn clear_trace(&self) {
        self.open()
            .conn()
            .execute("DELETE FROM awr_writes", [])
            .unwrap();
    }
}
impl Drop for FileDb {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn deck(id: u64, name: &str, slides: usize, identity: bool) -> SlideDeck {
    let mut deck = SlideDeck::new(name);
    deck.set_id(DeckId(id));
    if identity {
        deck.set_uid(DeckUid::parse(&format!("{:032x}", id + 100)));
    }
    for i in 0..slides {
        let slide = deck.add_slide().unwrap();
        deck.get_mut(slide).unwrap().notes =
            format!("deck {id} slide {i}: historical speaker notes");
    }
    deck
}
fn opened_first(lib: &DeckLibrary) -> DeckWorkspace {
    let mut workspace = DeckWorkspace::demo();
    // Same first-deck selection used by main setup; no test-only alternate authority.
    workspace.load_deck(lib.list().first().and_then(|m| lib.get(m.id)).unwrap());
    workspace
}
fn assert_untouched(file: &FileDb, before: &BTreeMap<String, String>, keys: &[&str]) {
    let after = file.rows();
    let trace = file.trace();
    for key in keys {
        assert_eq!(
            after.get(*key),
            before.get(*key),
            "untouched row {key} changed bytes"
        );
        assert!(
            !trace.iter().any(|(written, _)| written == key),
            "untouched row {key} was SQL-written"
        );
    }
}
fn assert_saved(file: &FileDb, key: &str, expected_id: u64, expected_slides: usize) -> SlideDeck {
    let rows = file.rows();
    let deck: SlideDeck = serde_json::from_str(rows.get(key).expect("own row retained")).unwrap();
    assert_eq!(deck.id(), DeckId(expected_id));
    assert_eq!(deck.len(), expected_slides);
    deck
}
#[test]
fn awr_leaving_stale_alpha_preserves_real_zed_and_only_touches_alpha() {
    let file = FileDb::new(&[
        ("Alpha", deck(1, "Zed", 1, false)),
        ("Zed", deck(2, "Zed", 3, true)),
        ("ZZ Untouched", deck(3, "ZZ Untouched", 2, true)),
    ]);
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    assert_untouched(&file, &before, &["Zed", "ZZ Untouched"]);
    let mut workspace = opened_first(&library);
    assert_eq!(workspace.open_deck().id(), DeckId(1));
    assert_eq!(workspace.open_deck().len(), 1);
    let uid = library.uid_of(DeckId(1));
    assert!(uid.is_some());
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    println!(
        "AWR_SHARED_LEAVE outgoing=1 incoming={} writes={:?}",
        workspace.open_deck().id().0,
        file.trace()
    );
    assert_eq!(workspace.open_deck().id(), DeckId(2));
    assert_eq!(workspace.open_deck().len(), 3);
    assert_untouched(&file, &before, &["Zed", "ZZ Untouched"]);
    assert_eq!(file.trace(), vec![("Alpha".into(), "update".into())]);
    let saved = assert_saved(&file, "Alpha", 1, 1);
    assert_eq!(saved.name, "Alpha");
    assert_eq!(saved.uid().cloned(), uid);
    drop(library);
    file.clear_trace();
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.list().iter().map(|m| m.slides).sum::<usize>(), 6);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 3);
    assert_eq!(again.uid_of(DeckId(1)), uid);
    assert_untouched(&file, &before, &["Zed", "ZZ Untouched"]);
    assert!(file.trace().is_empty());
}
#[test]
fn awr_duplicate_json_names_survive_edits_and_relaunch_as_distinct_rows() {
    let file = FileDb::new(&[
        ("One", deck(1, "Shared", 1, true)),
        ("Two", deck(2, "Shared", 3, true)),
        ("Untouched", deck(3, "Untouched", 2, true)),
    ]);
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let uid1 = library.uid_of(DeckId(1));
    let uid2 = library.uid_of(DeckId(2));
    let mut workspace = DeckWorkspace::demo();
    workspace.load_deck(library.get(DeckId(1)).unwrap());
    workspace.add_slide();
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    workspace.add_slide();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 1);
    assert_eq!(
        file.rows().keys().cloned().collect::<Vec<_>>(),
        vec!["One", "Two", "Untouched"]
    );
    assert_untouched(&file, &before, &["Untouched"]);
    assert_eq!(
        file.trace(),
        vec![
            ("One".into(), "update".into()),
            ("Two".into(), "update".into())
        ]
    );
    assert_eq!(assert_saved(&file, "One", 1, 2).name, "One");
    assert_eq!(assert_saved(&file, "Two", 2, 4).name, "Two");
    drop(library);
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.get(DeckId(1)).unwrap().len(), 2);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 4);
    assert_eq!(again.uid_of(DeckId(1)), uid1);
    assert_eq!(again.uid_of(DeckId(2)), uid2);
    assert_ne!(uid1, uid2);
}
fn blank_file() -> FileDb {
    FileDb::new(&[
        ("", deck(1, "Zed", 1, true)),
        ("Zed", deck(2, "Zed", 3, true)),
    ])
}
#[test]
fn awr_blank_row_key_leaves_store_on_its_own_row() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let uid = library.uid_of(DeckId(1));
    let mut workspace = DeckWorkspace::demo();
    workspace.load_deck(library.get(DeckId(1)).unwrap());
    workspace.add_slide();
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    assert_untouched(&file, &before, &["Zed"]);
    assert_eq!(file.rows().len(), 2);
    assert_eq!(file.trace(), vec![("".into(), "update".into())]);
    assert_eq!(assert_saved(&file, "", 1, 2).uid().cloned(), uid);
    drop(library);
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.get(DeckId(1)).unwrap().len(), 2);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 3);
}
#[test]
fn awr_successful_blank_rename_drops_the_old_binding_before_another_store() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    file.clear_trace();
    assert_eq!(
        library.rename(DeckId(1), "Renamed").as_deref(),
        Some("Renamed")
    );
    let mut editing = library.get(DeckId(1)).unwrap();
    editing.add_slide();
    library.store(&editing);
    assert_untouched(&file, &before, &["Zed"]);
    assert_eq!(
        file.rows().keys().cloned().collect::<Vec<_>>(),
        vec!["Renamed", "Zed"]
    );
    assert_eq!(assert_saved(&file, "Renamed", 1, 2).name, "Renamed");
    drop(library);
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.get(DeckId(1)).unwrap().len(), 2);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 3);
}
#[test]
fn awr_failed_atomic_rename_retains_own_row_binding_for_later_store() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    file.clear_trace();
    file.open().conn().execute_batch("CREATE TRIGGER awr_refuse_rename BEFORE INSERT ON deck WHEN NEW.name = 'Renamed' BEGIN SELECT RAISE(ABORT, 'fixture refuses rename'); END;").unwrap();
    library.rename(DeckId(1), "Renamed");
    assert_eq!(
        file.rows(),
        before,
        "failed atomic rename must roll back every row"
    );
    assert!(file.trace().is_empty());
    file.open()
        .conn()
        .execute_batch("DROP TRIGGER awr_refuse_rename;")
        .unwrap();
    let mut editing = library.get(DeckId(1)).unwrap();
    editing.add_slide();
    library.store(&editing);
    assert_eq!(
        file.rows().keys().cloned().collect::<Vec<_>>(),
        vec!["", "Zed"]
    );
    assert_untouched(&file, &before, &["Zed"]);
    assert_eq!(file.trace(), vec![("".into(), "update".into())]);
    assert_saved(&file, "", 1, 2);
}
#[test]
fn awr_failed_delete_retains_own_binding_for_undo_and_store() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    file.clear_trace();
    file.open().conn().execute_batch("CREATE TRIGGER awr_refuse_delete BEFORE DELETE ON deck WHEN OLD.name = '' BEGIN SELECT RAISE(ABORT, 'fixture refuses delete'); END;").unwrap();
    assert!(library.delete(DeckId(1)));
    assert_eq!(file.rows(), before);
    assert!(file.trace().is_empty());
    file.open()
        .conn()
        .execute_batch("DROP TRIGGER awr_refuse_delete;")
        .unwrap();
    assert!(library.restore(DeckId(1)).is_some());
    let mut editing = library.get(DeckId(1)).unwrap();
    editing.add_slide();
    library.store(&editing);
    assert_eq!(
        file.rows().keys().cloned().collect::<Vec<_>>(),
        vec!["", "Zed"]
    );
    assert_untouched(&file, &before, &["Zed"]);
    assert_saved(&file, "", 1, 2);
}
#[test]
fn awr_successful_delete_restore_and_new_copy_never_reuse_old_binding() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let mut incoming = library.get(DeckId(1)).unwrap();
    let original_uid = incoming.uid().cloned();
    file.clear_trace();
    assert!(library.delete(DeckId(1)));
    assert!(!file.rows().contains_key(""));
    assert_untouched(&file, &before, &["Zed"]);
    incoming.name = "Imported copy".into(); // still carries the removed deck's external id/uid.
    let adopted = library.try_adopt(incoming).unwrap();
    assert_ne!(adopted.id(), DeckId(1));
    assert_ne!(adopted.uid().cloned(), original_uid);
    let restored_name = library.restore(DeckId(1)).unwrap();
    let mut restored = library.get(DeckId(1)).unwrap();
    restored.add_slide();
    library.store(&restored);
    assert!(
        !file.rows().contains_key(""),
        "successful delete must not leave a stale storage binding"
    );
    assert_untouched(&file, &before, &["Zed"]);
    assert_saved(&file, "Imported copy", adopted.id().0, 1);
    assert_eq!(
        assert_saved(&file, &restored_name, 1, 2).uid().cloned(),
        original_uid
    );
    drop(library);
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.list().len(), 3);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 3);
}
fn exact_key(key: &str, json_name: &str, sibling: &str) {
    let file = FileDb::new(&[
        (key, deck(1, json_name, 1, true)),
        (sibling, deck(2, sibling, 3, true)),
    ]);
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let mut workspace = DeckWorkspace::demo();
    workspace.load_deck(library.get(DeckId(1)).unwrap());
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    assert_untouched(&file, &before, &[sibling]);
    assert_eq!(file.trace(), vec![(key.into(), "update".into())]);
    assert_eq!(assert_saved(&file, key, 1, 1).name, key);
    assert_eq!(file.rows().len(), 2);
    drop(library);
    let again = DeckLibrary::load(Some(file.open()));
    assert_eq!(again.get(DeckId(1)).unwrap().name, key);
    assert_eq!(again.get(DeckId(2)).unwrap().len(), 3);
}
#[test]
fn awr_case_sensitive_row_key_is_not_normalized_into_its_sibling() {
    exact_key("zed", "Zed", "Zed");
}
#[test]
fn awr_space_sensitive_row_key_is_not_trimmed_into_its_sibling() {
    exact_key("Gamma ", "Gamma", "Gamma");
}
#[test]
fn awr_already_open_keeps_edits_without_any_store() {
    let file = FileDb::new(&[
        ("Alpha", deck(1, "Alpha", 1, true)),
        ("Zed", deck(2, "Zed", 3, true)),
    ]);
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let mut workspace = opened_first(&library);
    workspace.add_slide();
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 1);
    assert_eq!(workspace.open_deck().len(), 2);
    assert_eq!(library.get(DeckId(1)).unwrap().len(), 1);
    assert_eq!(file.rows(), before);
    assert!(file.trace().is_empty());
}
#[test]
fn awr_ordinary_matching_rows_autosave_only_the_outgoing_deck() {
    let file = FileDb::new(&[
        ("Alpha", deck(1, "Alpha", 1, true)),
        ("Zed", deck(2, "Zed", 3, true)),
    ]);
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let mut workspace = opened_first(&library);
    workspace.add_slide();
    file.clear_trace();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    assert_eq!(workspace.open_deck().len(), 3);
    assert_eq!(file.trace(), vec![("Alpha".into(), "update".into())]);
    assert_saved(&file, "Alpha", 1, 2);
    assert_untouched(&file, &before, &["Zed"]);
}
#[test]
fn awr_readonly_store_keeps_every_database_row_unchanged() {
    let file = blank_file();
    let before = file.rows();
    let db = Database::open_existing_readonly(file.0.join("library.sqlite")).unwrap();
    let mut library = DeckLibrary::load(Some(db));
    let mut workspace = DeckWorkspace::demo();
    workspace.load_deck(library.get(DeckId(1)).unwrap());
    workspace.add_slide();
    let _ = crate::deck_open_in(&mut workspace, &mut library, 2);
    assert_eq!(workspace.open_deck().len(), 3);
    assert_eq!(file.rows(), before);
    assert!(file.trace().is_empty());
}
#[test]
fn awr_copy_and_import_get_fresh_numbers_without_borrowing_loaded_row_ownership() {
    let file = blank_file();
    let before = file.rows();
    let mut library = DeckLibrary::load(Some(file.open()));
    let source = library.get(DeckId(1)).unwrap();
    file.clear_trace();
    let copy = library.duplicate(DeckId(1)).unwrap();
    assert_ne!(copy.id(), source.id());
    assert_ne!(copy.uid(), source.uid());
    let mut external = source.clone();
    external.name = "Imported".into();
    let imported = library.try_adopt(external).unwrap();
    assert_ne!(imported.id(), source.id());
    assert_ne!(imported.uid(), source.uid());
    let mut copy = library.get(copy.id()).unwrap();
    copy.add_slide();
    library.store(&copy);
    let mut imported = library.get(imported.id()).unwrap();
    imported.add_slide();
    library.store(&imported);
    assert_untouched(&file, &before, &["", "Zed"]);
    assert_eq!(file.rows().len(), 4);
    assert_saved(&file, &copy.name, copy.id().0, 2);
    assert_saved(&file, "Imported", imported.id().0, 2);
}
