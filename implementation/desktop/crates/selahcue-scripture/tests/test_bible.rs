//! [`Bible`]: one handle that answers lookups for a bundled and an installed translation alike.
//!
//! The strongest check available is to give both kinds THE SAME TEXT. The bundled King James
//! asset is installed as a downloaded translation (`KJX`), and every method of the handle is then
//! compared between `KJX` and the bundled `KJV` over every chapter of every book (and the
//! out-of-canon neighbours), with several verse selections each. Any disagreement means the
//! installed path selects, pages or searches differently from the bundled one, which is the one
//! thing a handle exists to rule out.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::fs;

use common::{catalogue_json, entry_pinning, fixture, tmp_dir};
use selahcue_core::scripture::{book_name, parse_one, Reference, VerseRange};
use selahcue_scripture::catalog::Catalogue;
use selahcue_scripture::registry::{InstallHooks, Registry};
use selahcue_scripture::validate::scan;
use selahcue_scripture::{
    adjacent_chapter_in, chapter_in, chapter_verse_bounds_in, passage_exists_in, passage_text_in,
    search_in, verse_count_in, verses_in, Bible, Translation,
};

fn reference(book: u8, chapter: u16, verses: Option<(u16, u16)>) -> Reference {
    Reference {
        book,
        book_name: book_name(book).unwrap_or("?"),
        chapter,
        verses: verses.map(|(start, end)| VerseRange { start, end }),
    }
}

fn parsed(s: &str) -> Reference {
    parse_one(s).unwrap_or_else(|e| panic!("test reference {s:?} must parse: {e:?}"))
}

/// A registry with the bundled KJV text installed as translation `KJX`.
fn kjx() -> (Registry, Bible) {
    let bytes = fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/kjv.tsv.gz")).unwrap();
    let counts = scan(bytes.as_slice(), |_| {})
        .expect("the bundled KJV asset must satisfy the installed-asset rules");
    let root = tmp_dir("bible-kjx");
    let catalogue = Catalogue::parse(&catalogue_json(
        Some("https://downloads.example.org/t/"),
        vec![entry_pinning("KJX", &bytes, counts.ot, counts.nt)],
    ))
    .unwrap();
    let registry = Registry::new(root.join("data"), catalogue);
    let src = root.join("kjx.src");
    fs::write(&src, &bytes).unwrap();
    registry
        .install_from_file("KJX", &src, 1, &InstallHooks::default())
        .expect("the bundled KJV asset installs as KJX");
    let bible = registry.bible("KJX").expect("KJX is installed");
    (registry, bible)
}

#[test]
fn a_bundled_handle_is_the_bundled_free_functions() {
    let refs = [
        parsed("Genesis 1"),
        parsed("John 3:16"),
        parsed("Luke 17"),
        parsed("Psalm 119"),
        parsed("Jude 1:1-3"),
        parsed("Revelation 22:21"),
        reference(45, 99, None),
        reference(0, 1, None),
        reference(67, 1, Some((1, 1))),
    ];
    for t in Translation::ALL {
        let h = Bible::bundled(t);
        assert_eq!(h, Bible::from(t));
        assert_eq!(
            Bible::from_code(&t.code().to_ascii_lowercase()),
            Some(h.clone())
        );
        assert_eq!((h.code(), h.name()), (t.code(), t.name()));
        assert_eq!(h.bundled_translation(), Some(t));
        assert!(h.is_available());
        assert_eq!(h.verse_count(), verse_count_in(t));
        for r in &refs {
            let want: Vec<_> = verses_in(t, r).into_iter().cloned().collect();
            assert_eq!(h.verses(r), want, "{} {r:?}", t.code());
            assert_eq!(h.passage_text(r), passage_text_in(t, r));
            assert_eq!(h.chapter(r), chapter_in(t, r));
            assert_eq!(h.adjacent_chapter(r, true), adjacent_chapter_in(t, r, true));
            assert_eq!(
                h.adjacent_chapter(r, false),
                adjacent_chapter_in(t, r, false)
            );
            assert_eq!(h.passage_exists(r), passage_exists_in(t, r));
            assert_eq!(h.chapter_verse_bounds(r), chapter_verse_bounds_in(t, r));
        }
        assert_eq!(h.search("love", 5), search_in(t, "love", 5));
    }
}

#[test]
fn an_installed_translation_answers_exactly_like_the_same_text_bundled() {
    let (registry, installed) = kjx();
    let bundled = Bible::bundled(Translation::Kjv);

    // Premise: this really is the installed path, not a bundled one in disguise.
    assert_eq!(installed.code(), "KJX");
    assert!(installed.bundled_translation().is_none());
    assert_eq!(installed.verse_count(), bundled.verse_count());
    assert_eq!(
        registry.resident_codes(),
        ["KJX"],
        "KJX was read through the registry"
    );

    let mut compared = 0usize;
    let mut present = 0usize;
    for book in 0u8..=70 {
        let mut chapters: Vec<u16> = (0..=152).collect();
        chapters.push(u16::MAX);
        for chapter in chapters {
            for verses in [
                None,
                Some((1, 1)),
                Some((2, 5)),
                Some((9_000, 9_001)),
                Some((7, 3)),
            ] {
                let r = reference(book, chapter, verses);
                assert_eq!(
                    installed.verses(&r),
                    bundled.verses(&r),
                    "verses {book} {chapter} {verses:?}"
                );
                assert_eq!(
                    installed.passage_text(&r),
                    bundled.passage_text(&r),
                    "passage_text {book} {chapter} {verses:?}"
                );
                assert_eq!(
                    installed.passage_exists(&r),
                    bundled.passage_exists(&r),
                    "passage_exists {book} {chapter} {verses:?}"
                );
                assert_eq!(
                    installed.chapter_verse_bounds(&r),
                    bundled.chapter_verse_bounds(&r),
                    "chapter_verse_bounds {book} {chapter} {verses:?}"
                );
                compared += 1;
                if bundled.passage_exists(&r) {
                    present += 1;
                }
            }
            // Chapter paging does not depend on the verse selection.
            let r = reference(book, chapter, None);
            assert_eq!(
                installed.chapter(&r),
                bundled.chapter(&r),
                "chapter {book} {chapter}"
            );
            for forward in [true, false] {
                assert_eq!(
                    installed.adjacent_chapter(&r, forward),
                    bundled.adjacent_chapter(&r, forward),
                    "adjacent {book} {chapter} forward={forward}"
                );
            }
        }
    }
    // Positive control: the sweep covered the canon (so "all equal" is not "all empty").
    assert!(compared > 50_000, "swept only {compared} references");
    assert!(present > 3_000, "only {present} of them present a verse");

    for query in [
        "love",
        "in the beginning",
        "God said light",
        "xyzzy-not-in-the-bible",
        "   ",
        "",
    ] {
        for limit in [0usize, 1, 5, 50] {
            assert_eq!(
                installed.search(query, limit),
                bundled.search(query, limit),
                "search {query:?} limit {limit}"
            );
        }
    }
    assert!(!installed.search("love", 5).is_empty());
    assert_eq!(
        installed.passage_text(&parsed("John 3:16")),
        bundled.passage_text(&parsed("John 3:16"))
    );
}

#[test]
fn an_installed_handle_carries_its_catalogue_name_and_is_not_equal_to_a_bundled_one() {
    let f = fixture("TST", 3, 2);
    let root = tmp_dir("bible-handle");
    let cat = Catalogue::parse(&catalogue_json(
        Some("https://d.example.org/t/"),
        vec![f.entry("cleared")],
    ))
    .unwrap();
    let registry = Registry::new(root.join("data"), cat.clone());
    fs::write(root.join("a.gz"), &f.gz).unwrap();
    registry
        .install_from_file("TST", &root.join("a.gz"), 1, &InstallHooks::default())
        .unwrap();

    let h = registry.bible("tst").expect("lookup is case-insensitive");
    assert_eq!((h.code(), h.name()), ("TST", "TST Test Bible"));
    assert!(h.is_available());
    assert_eq!(h, registry.bible("TST").unwrap());
    assert_ne!(h, Bible::bundled(Translation::Kjv));
    assert_eq!(format!("{h:?}"), "Bible(TST, installed)");
    assert_eq!(
        format!("{:?}", Bible::bundled(Translation::Kjv)),
        "Bible(KJV, bundled)"
    );

    // The same code in a DIFFERENT registry is a different translation.
    let other = Registry::new(root.join("other"), cat);
    fs::create_dir_all(root.join("other")).unwrap();
    other
        .install_from_file("TST", &root.join("a.gz"), 1, &InstallHooks::default())
        .unwrap();
    assert_ne!(h, other.bible("TST").unwrap());
    assert_eq!(h.clone(), h);
}

#[test]
fn a_code_that_is_not_installed_has_no_handle() {
    let f = fixture("TST", 3, 2);
    let root = tmp_dir("bible-none");
    let cat = Catalogue::parse(&catalogue_json(
        Some("https://d.example.org/t/"),
        vec![f.entry("cleared")],
    ))
    .unwrap();
    let registry = Registry::new(root.join("data"), cat);
    assert!(
        registry.bible("TST").is_none(),
        "in the catalogue but not installed"
    );
    assert!(registry.bible("NOPE").is_none());
    // Bundled codes are not the registry's business, and nonsense is nothing.
    for code in ["KJV", "kjv", "", "  ", "../etc", "A", "TST/../X"] {
        assert!(registry.bible(code).is_none(), "{code:?}");
    }
    // The wire path: bundled codes always resolve; an unknown one does not.
    assert!(Bible::from_code("KJV").is_some());
    assert!(Bible::from_code("webbe").is_some());
    assert!(Bible::from_code("NOT-A-TRANSLATION").is_none());
    assert!(Bible::from_code("").is_none());
}

#[test]
fn an_installed_translation_whose_file_vanishes_answers_nothing_and_does_not_panic() {
    let f = fixture("TST", 3, 2);
    let root = tmp_dir("bible-gone");
    let cat = Catalogue::parse(&catalogue_json(
        Some("https://d.example.org/t/"),
        vec![f.entry("cleared")],
    ))
    .unwrap();
    let dir = root.join("data");
    let installer = Registry::new(dir.clone(), cat.clone());
    fs::write(root.join("a.gz"), &f.gz).unwrap();
    installer
        .install_from_file("TST", &root.join("a.gz"), 1, &InstallHooks::default())
        .unwrap();
    let r = parsed("Genesis 1:1");
    assert_eq!(
        installer.bible("TST").unwrap().verse_count(),
        5,
        "premise: the translation reads while its file is there"
    );

    // A reader that has not read anything yet holds a handle, then the file disappears.
    let reader = Registry::new(dir.clone(), cat);
    let h = reader.bible("TST").unwrap();
    assert!(h.is_available());
    fs::remove_file(dir.join("tst.tsv.gz")).unwrap();

    assert!(!h.is_available());
    assert!(h.verses(&r).is_empty());
    assert_eq!(h.passage_text(&r), None);
    assert!(h.search("fixture", 5).is_empty());
    assert_eq!(h.chapter(&r), None);
    assert_eq!(h.adjacent_chapter(&r, true), None);
    assert!(!h.passage_exists(&r));
    assert_eq!(h.chapter_verse_bounds(&r), None);
    assert_eq!(h.verse_count(), 0);
}
