//! The bundled WEB translation: canonical lookup, keyword search, perf, and
//! bounded-memory behaviour (story 86ajpew05 acceptance).

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{
    is_available, passage_text, passage_text_in, search, verse_count, verse_count_in, verses,
    verses_in, Translation, TRANSLATION,
};

#[test]
fn both_protestant_canons_are_bundled_and_kjv_is_the_default() {
    // Owner decision (2026-07-24): KJV is the default translation.
    assert_eq!(TRANSLATION, "KJV");
    assert_eq!(Translation::default(), Translation::Kjv);
    assert_eq!(Translation::ALL[0], Translation::Kjv);
    // ebible.org VPL exports.
    assert_eq!(verse_count_in(Translation::Kjv), 31_102);
    assert_eq!(verse_count_in(Translation::Web), 31_098);
    assert_eq!(verse_count_in(Translation::Asv), 31_086);
    assert_eq!(verse_count_in(Translation::Webbe), 31_098);
    assert_eq!(verse_count_in(Translation::Dby), 31_099);
    assert_eq!(verse_count(), 31_102, "default count is the KJV's");
    // First and last verses of the canon resolve in every BUNDLED translation (wording
    // varies legitimately — BBE opens "At the first God made…"). Downloadable translations
    // (YLT) are excluded here: their assets are not present in the test environment.
    let gen = parse_one("Genesis 1:1").unwrap();
    let rev = parse_one("Revelation 22:21").unwrap();
    for t in Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
    {
        assert!(
            passage_text_in(t, &gen).unwrap().contains("God"),
            "{} Genesis 1:1",
            t.code()
        );
        assert!(
            !passage_text_in(t, &rev).unwrap().is_empty(),
            "{} Revelation 22:21",
            t.code()
        );
    }
    assert!(
        passage_text(&gen).unwrap().contains("In the beginning"),
        "KJV default wording"
    );
    // Codes round-trip (wire/UI selector), case-insensitively — for ALL.
    for t in Translation::ALL {
        assert_eq!(Translation::from_code(t.code()), Some(t));
        assert_eq!(Translation::from_code(&t.code().to_lowercase()), Some(t));
    }
    assert_eq!(Translation::from_code("NIV"), None);
}

#[test]
fn youngs_literal_translation_is_registered_as_downloadable() {
    // YLT (Young's Literal Translation, 1898 — public domain) joins the selectable set as the
    // DOWNLOADABLE exemplar: it is a real, parseable translation code that is not bundled.
    assert_eq!(Translation::ALL.len(), 6, "YLT joins the translation set");
    // Parses from the wire/UI code, case-insensitively, with the right code + name.
    assert_eq!(Translation::from_code("YLT").map(|t| t.code()), Some("YLT"));
    assert_eq!(
        Translation::from_code("ylt").map(|t| t.code()),
        Some("YLT"),
        "case-insensitive"
    );
    assert_eq!(
        Translation::from_code("YLT").map(|t| t.name()),
        Some("Young's Literal Translation (1898)")
    );
    // Unknown codes still reject.
    assert_eq!(Translation::from_code("NIV"), None);
    // Classified downloadable; bundled ones are not (pure classification, no I/O).
    assert!(Translation::Ylt.is_downloadable());
    for t in [
        Translation::Kjv,
        Translation::Web,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
    ] {
        assert!(!t.is_downloadable(), "{} is bundled", t.code());
        assert!(is_available(t), "{} is always available", t.code());
    }
}

#[cfg(not(feature = "download"))]
#[test]
fn downloadable_translation_is_unavailable_and_degrades_gracefully_without_the_feature() {
    // With the `download` feature OFF, YLT exists in the enum but is NEVER available — no
    // runtime file I/O is compiled — and every lookup degrades to "nothing", never a panic.
    use selahcue_scripture::verses_in;
    assert!(!is_available(Translation::Ylt));
    let r = parse_one("John 3:16").unwrap();
    assert!(passage_text_in(Translation::Ylt, &r).is_none());
    assert!(verses_in(Translation::Ylt, &r).is_empty());
    assert_eq!(verse_count_in(Translation::Ylt), 0);
    // A chapter/adjacency lookup is None, not a panic.
    assert!(selahcue_scripture::chapter_in(Translation::Ylt, &r).is_none());
}

#[test]
fn romans_8_28_reads_correctly_in_each_translation() {
    let r = parse_one("Romans 8:28").unwrap();
    // Default (KJV) wording — with the ebible supplied-word brackets stripped.
    let kjv = passage_text(&r).unwrap();
    assert!(
        kjv.contains("all things work together for good to them that love God"),
        "unexpected KJV text: {kjv}"
    );
    assert!(!kjv.contains('[') && !kjv.contains('¶'), "markup stripped");
    // Each alternative translation keeps its own wording.
    let web = passage_text_in(Translation::Web, &r).unwrap();
    assert!(web.contains("work together for good for those who love God"));
    let asv = passage_text_in(Translation::Asv, &r).unwrap();
    assert!(asv.contains("to them that love God all things work together"));
    let webbe = passage_text_in(Translation::Webbe, &r).unwrap();
    assert!(webbe.contains("work together for good for those who love God"));
    let dby = passage_text_in(Translation::Dby, &r).unwrap();
    assert!(dby.contains("all things work together for good to those who love"));
}

#[test]
fn ranges_and_whole_chapters_resolve() {
    let range = parse_one("Romans 8:28-30").unwrap();
    assert_eq!(verses(&range).len(), 3);
    // Psalm 117 is the shortest chapter: exactly 2 verses.
    let chapter = parse_one("Psalm 117").unwrap();
    assert_eq!(verses(&chapter).len(), 2);
    // Single-chapter books address explicitly (the parser reads "Jude 9" as
    // chapter 9 — bare-number shorthand is a later parser nicety).
    let jude = parse_one("Jude 1:9").unwrap();
    assert_eq!(verses(&jude).len(), 1);
    // A chapter outside the canon yields nothing (never panics).
    let no_such = parse_one("Psalm 151:1").unwrap();
    assert!(verses(&no_such).is_empty());
}

#[test]
fn keyword_search_finds_verses_and_is_bounded() {
    let hits = search("work together for good", 8);
    assert!(
        hits.iter().any(|h| h.reference == "Romans 8:28"),
        "hits: {:?}",
        hits.iter().map(|h| &h.reference).collect::<Vec<_>>()
    );
    // Search results can be staged directly: the reference round-trips.
    let r = parse_one(&hits[0].reference).unwrap();
    assert!(passage_text(&r).is_some());
    // The limit bounds the result set on common words.
    assert_eq!(search("the", 5).len(), 5);
    // Case-insensitive; empty query is empty.
    assert!(!search("SHEPHERD", 8).is_empty());
    assert!(search("   ", 8).is_empty());
}

#[test]
fn keyword_search_meets_the_500ms_budget() {
    // Story acceptance: search <500ms. Worst case: a rare phrase forces a scan
    // of all 31k verses. The one-time index decode is warmed first — the budget
    // measures SEARCH, and test ordering must not decide which test pays init.
    let _ = verse_count();
    let start = std::time::Instant::now();
    let hits = search("Mephibosheth", 20);
    let elapsed = start.elapsed();
    assert!(!hits.is_empty());
    assert!(
        elapsed < std::time::Duration::from_millis(500),
        "full-scan search took {elapsed:?}"
    );
}

#[test]
fn the_indexes_are_bounded_and_idempotent() {
    // No-leak rule: repeated use never grows EITHER decoded index — one fixed
    // decode per translation.
    let first: Vec<usize> = Translation::ALL
        .iter()
        .map(|t| verse_count_in(*t))
        .collect();
    for _ in 0..50 {
        let r = parse_one("John 3:16").unwrap();
        for t in Translation::ALL {
            let _ = passage_text_in(t, &r);
            let _ = selahcue_scripture::search_in(t, "love", 4);
        }
        let _ = passage_text(&r);
        let _ = search("love", 4);
    }
    let after: Vec<usize> = Translation::ALL
        .iter()
        .map(|t| verse_count_in(*t))
        .collect();
    assert_eq!(after, first);
    assert_eq!(verse_count(), first[0], "default remains the KJV index");
}

#[test]
fn chapter_browser_returns_full_chapters_with_paging() {
    use selahcue_scripture::{adjacent_chapter, chapter};
    // A verse-level reference yields its WHOLE chapter.
    let r = parse_one("Genesis 1:3").unwrap();
    let ch = chapter(&r).unwrap();
    assert_eq!((ch.book_name.as_str(), ch.chapter), ("Genesis", 1));
    assert_eq!(ch.verses.len(), 31);
    assert_eq!(ch.verses[0].0, 1);
    assert!(!ch.has_prev, "nothing before Genesis 1");
    assert!(ch.has_next);

    // Paging crosses book boundaries in both directions.
    assert_eq!(adjacent_chapter(&r, true).as_deref(), Some("Genesis 2"));
    assert_eq!(adjacent_chapter(&r, false), None);
    let mal = parse_one("Malachi 4").unwrap();
    assert_eq!(adjacent_chapter(&mal, true).as_deref(), Some("Matthew 1"));
    let rev = parse_one("Revelation 22").unwrap();
    assert!(chapter(&rev).unwrap().has_prev);
    assert!(adjacent_chapter(&rev, true).is_none(), "end of the canon");
    // The returned display string parses back (round-trips into the browser).
    let next = adjacent_chapter(&mal, true).unwrap();
    assert!(chapter(&parse_one(&next).unwrap()).is_some());

    // Out-of-canon chapters are None, never a panic.
    assert!(chapter(&parse_one("Psalm 151").unwrap()).is_none());
}

#[test]
fn no_markup_residue_in_any_bundled_translation() {
    // Every marker class seen in ebible exports must be stripped everywhere:
    // supplied-word brackets, pilcrows, and footnote-apparatus asterisks (the
    // review found '*' residue in Darby's Psalm 119 and BBE placeholders).
    use selahcue_scripture::verses_in;
    let whole_bible = selahcue_core::scripture::parse_one("Genesis 1").unwrap();
    let _ = whole_bible; // per-translation full scans below
                         // BUNDLED translations only: downloadable ones (YLT) have no asset in the test env, so a
                         // full-canon markup scan does not apply.
    for t in Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
    {
        let mut scanned = 0usize;
        for book in 1..=66u8 {
            for chapter in 1..=200u16 {
                let r = selahcue_core::scripture::Reference {
                    book,
                    book_name: "",
                    chapter,
                    verses: None,
                };
                let vs = verses_in(t, &r);
                if vs.is_empty() {
                    break;
                }
                for v in vs {
                    scanned += 1;
                    assert!(
                        !v.text.contains(['[', ']', '¶', '*']),
                        "{} {}:{}:{} has residue: {}",
                        t.code(),
                        book,
                        chapter,
                        v.verse,
                        v.text
                    );
                }
            }
        }
        assert!(scanned > 30_000, "{} scanned {scanned}", t.code());
    }
}

// ---- Headings are not scripture (17tnw2b2g7q) ---------------------------------------------
//
// The ebible VPL exports flatten a psalm's superscription into verse 1, so Psalm 42:1 used to
// read "To the chief Musician, Maschil, for the sons of Korah. As the hart panteth…" and the
// congregation saw the title as if it were the verse. `scripts/strip_bible_headings.py` removed
// the titles (and the other non-verse notes below) from all five assets. Numbering never
// changed — the titles lived inside verse 1, not in a verse 0 — so the count pins above and
// the chapter-bound tests are the proof that no verse was lost with them.

/// Text of the first verse a reference resolves to, in a given translation.
fn verse_text(t: Translation, reference: &str) -> String {
    let r = parse_one(reference).unwrap();
    verses_in(t, &r)
        .first()
        .unwrap_or_else(|| panic!("{} {reference} resolves to nothing", t.code()))
        .text
        .clone()
}

fn bundled() -> impl Iterator<Item = Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
}

/// Title openers seen in the five bundled translations' psalm superscriptions. Case-sensitive on
/// purpose: it is matched at the START of a psalm's verse 1, where none of these is a genuine
/// verse. A list can never be exhaustive, so this is the corpus net; the exact pins below are
/// the proof for the cases that matter most.
const TITLE_OPENERS: &[&str] = &[
    "To the chief",
    "For the chief",
    "For the Chief",
    "For the music",
    "For the Director",
    "A Psalm",
    "A Song",
    "A song",
    "A Prayer",
    "A Contemplation",
    "A contemplation",
    "A contemplative",
    "A meditation",
    "A Poem",
    "A praise psalm",
    "A teaching",
    "A Miktam",
    "A Shiggaion",
    "Maschil",
    "Michtam",
    "Miktam",
    "Shiggaion",
    "An instruction",
    "By David",
    "By Solomon",
    "For Solomon",
    "For Jeduthun",
    "Of David",
    "Of the sons of Korah",
    "David\u{2019}s Psalm",
    "Psalm of David",
];

/// The Hebrew letter names the bundled translations use for Psalm 119's acrostic sections.
const ACROSTIC_LETTERS: &[&str] = &[
    "ALEPH", "BETH", "GIMEL", "DALETH", "HE", "VAV", "VAU", "ZAIN", "ZAYIN", "HETH", "CHETH",
    "TETH", "YOD", "YODH", "KAPF", "CAPH", "KAPH", "LAMED", "LAMEDH", "MEM", "NUN", "SAMEKH",
    "SAMECH", "AYIN", "AIN", "PE", "TZADHE", "TZADE", "TSADDI", "TSADHE", "QOPH", "KOPH", "RESH",
    "SHIN", "SIN", "TAV", "TAU",
];

fn opens_with_title(text: &str) -> Option<&'static str> {
    TITLE_OPENERS.iter().copied().find(|o| {
        text.strip_prefix(o)
            .is_some_and(|rest| !rest.starts_with(char::is_alphanumeric))
    })
}

fn is_acrostic_label(text: &str) -> bool {
    let first = text.split_whitespace().next().unwrap_or("");
    ACROSTIC_LETTERS.contains(&first.trim_end_matches('.'))
}

/// Psalm 119's letter labels also sit at the END of the verse BEFORE the section they introduce
/// ("…forsake me. BETH"): VPL hangs a heading on the previous line. WEB and WEBBE carry 21 of
/// them. A check that only looks at how verses START never sees these (that is how the first
/// version of this change shipped them). Case-sensitive: the labels are upper case, and a verse
/// can legitimately end in a lower-case "sin" or "he".
fn ends_with_acrostic_label(text: &str) -> bool {
    if text.ends_with("SIN AND SHIN") {
        return true;
    }
    let last = text.split_whitespace().last().unwrap_or("");
    ACROSTIC_LETTERS.contains(&last.trim_end_matches('.'))
}

#[test]
fn psalm_verse_one_is_the_verse_not_the_title() {
    // (translation, reference, what the verse must now OPEN with). Psalm 18's superscription
    // ends "…hand of Saul: And he said," in the KJV — the verse proper is "I will love thee".
    let pins: &[(Translation, &str, &str)] = &[
        (
            Translation::Kjv,
            "Psalm 42:1",
            "As the hart panteth after the water brooks",
        ),
        (
            Translation::Kjv,
            "Psalm 18:1",
            "I will love thee, O LORD, my strength.",
        ),
        (
            Translation::Kjv,
            "Psalm 3:1",
            "LORD, how are they increased",
        ),
        (Translation::Kjv, "Psalm 51:1", "Have mercy upon me, O God"),
        // Psalms 3 and 51 in the other four translations (the description of this change claims all
        // five, so they are pinned, not just the KJV).
        (
            Translation::Web,
            "Psalm 3:1",
            "LORD, how my adversaries have increased",
        ),
        (
            Translation::Webbe,
            "Psalm 3:1",
            "LORD, how my adversaries have increased",
        ),
        (
            Translation::Asv,
            "Psalm 3:1",
            "Jehovah, how are mine adversaries increased",
        ),
        (
            Translation::Dby,
            "Psalm 3:1",
            "Jehovah, how many are they that trouble me",
        ),
        (Translation::Web, "Psalm 51:1", "Have mercy on me, God"),
        (Translation::Webbe, "Psalm 51:1", "Have mercy on me, God"),
        (Translation::Asv, "Psalm 51:1", "Have mercy upon me, O God"),
        (Translation::Dby, "Psalm 51:1", "Be gracious unto me, O God"),
        (
            Translation::Kjv,
            "Psalm 145:1",
            "I will extol thee, my God, O king",
        ),
        (
            Translation::Web,
            "Psalm 42:1",
            "As the deer pants for the water brooks",
        ),
        (
            Translation::Web,
            "Psalm 18:1",
            "I love you, LORD, my strength.",
        ),
        (
            Translation::Web,
            "Psalm 119:1",
            "Blessed are those whose ways are blameless",
        ),
        (
            Translation::Webbe,
            "Psalm 42:1",
            "As the deer pants for the water brooks",
        ),
        (
            Translation::Webbe,
            "Psalm 18:1",
            "I love you, LORD, my strength.",
        ),
        (
            Translation::Webbe,
            "Psalm 119:1",
            "Blessed are those whose ways are blameless",
        ),
        (
            Translation::Asv,
            "Psalm 42:1",
            "As the hart panteth after the water brooks",
        ),
        (
            Translation::Asv,
            "Psalm 18:1",
            "I love thee, O Jehovah, my strength.",
        ),
        (
            Translation::Dby,
            "Psalm 42:1",
            "As the hart panteth after the water-brooks",
        ),
        (
            Translation::Dby,
            "Psalm 18:1",
            "I will love thee, O Jehovah, my strength.",
        ),
        (
            Translation::Dby,
            "Psalm 119:1",
            "Blessed are the perfect in the way",
        ),
        (
            Translation::Dby,
            "Psalm 119:9",
            "Wherewithal shall a young man cleanse his path?",
        ),
    ];
    for (t, reference, opening) in pins {
        let got = verse_text(*t, reference);
        assert!(
            got.starts_with(opening),
            "{} {reference} should open {opening:?}, got {got:?}",
            t.code()
        );
    }
}

#[test]
fn no_psalm_opens_with_its_title_in_any_bundled_translation() {
    // Positive control FIRST: the matcher must flag a real title, or the corpus scan below could
    // pass on a typo'd list. (A scan that cannot fail guards nothing.)
    assert!(opens_with_title(
        "To the chief Musician, Maschil, for the sons of Korah. As the hart panteth"
    )
    .is_some());
    assert!(opens_with_title("For the Chief Musician. A Psalm by David. Have mercy").is_some());
    assert!(
        opens_with_title("Toward the chief of the hills").is_none(),
        "word boundary"
    );
    assert!(is_acrostic_label("ALEPH Blessed are those"));
    assert!(is_acrostic_label("BETH. Wherewithal shall a young man"));
    assert!(!is_acrostic_label(
        "LORD, your word is settled in heaven forever."
    ));
    // The END-of-verse matcher flags the real WEB shapes, and not ordinary endings (a lower-case
    // "He"/"sin" is a word, not the letters HE/SIN).
    assert!(ends_with_acrostic_label(
        "I will observe your statutes. Don\u{2019}t utterly forsake me. BETH"
    ));
    assert!(ends_with_acrostic_label(
        "Every one of your righteous ordinances endures forever. SIN AND SHIN"
    ));
    assert!(ends_with_acrostic_label("Deal bountifully. HE."));
    assert!(!ends_with_acrostic_label(
        "LORD, your word is settled in heaven forever."
    ));
    assert!(!ends_with_acrostic_label("Hear, and forgive us our sin."));
    assert!(!is_acrostic_label("He taught me the way."));

    for t in bundled() {
        let mut psalms = 0usize;
        for chapter in 1..=150u16 {
            let r = selahcue_core::scripture::Reference {
                book: 19,
                book_name: "",
                chapter,
                verses: None,
            };
            let vs = verses_in(t, &r);
            let first = vs
                .first()
                .unwrap_or_else(|| panic!("{} Psalm {chapter} empty", t.code()));
            psalms += 1;
            assert_eq!(
                first.verse,
                1,
                "{} Psalm {chapter} must still open at verse 1",
                t.code()
            );
            if let Some(opener) = opens_with_title(&first.text) {
                panic!(
                    "{} Psalm {chapter}:1 still opens with title text ({opener:?}): {}",
                    t.code(),
                    first.text
                );
            }
            if chapter == 119 {
                for v in &vs {
                    assert!(
                        !is_acrostic_label(&v.text),
                        "{} Psalm 119:{} still carries an acrostic letter label: {}",
                        t.code(),
                        v.verse,
                        v.text
                    );
                    assert!(
                        !ends_with_acrostic_label(&v.text),
                        "{} Psalm 119:{} still ends with the label of the NEXT section: {}",
                        t.code(),
                        v.verse,
                        v.text
                    );
                }
                assert_eq!(vs.len(), 176, "{} Psalm 119 must keep 176 verses", t.code());
            }
        }
        assert_eq!(
            psalms,
            150,
            "{} must still have exactly 150 psalms",
            t.code()
        );
    }
}

#[test]
fn psalm_119_labels_are_gone_from_both_ends_of_the_verses_they_touched() {
    // WEB and WEBBE: VPL hung each of the 21 later letter labels on the END of the verse before
    // its section (119:8 "… forsake me. BETH"), so the verse AFTER it (119:9) always started clean.
    // These pins are the ones a start-only check cannot make. (The corpus scan above covers every
    // verse in all five translations; these name the shapes.)
    for t in [Translation::Web, Translation::Webbe] {
        let v8 = verse_text(t, "Psalm 119:8");
        assert!(
            v8.ends_with("forsake me."),
            "{} 119:8 must end at the verse, got {v8:?}",
            t.code()
        );
        assert!(
            verse_text(t, "Psalm 119:9").starts_with("How can a young man"),
            "{} 119:9",
            t.code()
        );
        let v160 = verse_text(t, "Psalm 119:160");
        assert!(
            v160.ends_with("endures forever."),
            "{} 119:160 must not end in SIN AND SHIN, got {v160:?}",
            t.code()
        );
        assert!(
            verse_text(t, "Psalm 119:161").starts_with("Princes have persecuted me"),
            "{} 119:161",
            t.code()
        );
    }
    // DBY puts its letters at the START of the verse; KJV and ASV carry none.
    assert!(verse_text(Translation::Dby, "Psalm 119:169").starts_with("Let my cry come near"));
    assert!(
        verse_text(Translation::Kjv, "Psalm 119:9").starts_with("Wherewithal shall a young man")
    );
}

#[test]
fn habakkuk_3_19_no_longer_ends_with_the_musical_direction() {
    // The note ("To the chief singer on my stringed instruments.") closes the chapter in every
    // translation; the real verse ends at "…high places".
    for t in bundled() {
        let v19 = verse_text(t, "Habakkuk 3:19");
        assert!(
            !v19.contains("stringed instruments"),
            "{} Habakkuk 3:19 still carries the note: {v19}",
            t.code()
        );
        assert!(
            v19.ends_with("places."),
            "{} Habakkuk 3:19 ends oddly: {v19}",
            t.code()
        );
        // Habakkuk 3:1 is a NUMBERED verse in the KJV, so it stays everywhere.
        assert!(
            verse_text(t, "Habakkuk 3:1")
                .to_lowercase()
                .contains("prayer of habakkuk"),
            "{} Habakkuk 3:1 must be untouched",
            t.code()
        );
    }
}

#[test]
fn numbered_verses_that_read_like_titles_are_not_stripped() {
    // Hebrew treats these as headings, but they are numbered verses in the KJV the console
    // cites by number — removing them would renumber nothing and lose real scripture.
    for t in bundled() {
        assert!(
            verse_text(t, "Isaiah 38:9").starts_with("The writing of Hezekiah"),
            "{} Isaiah 38:9",
            t.code()
        );
        assert!(
            verse_text(t, "Song of Solomon 1:1")
                .to_lowercase()
                .starts_with("the song of songs"),
            "{} Song of Solomon 1:1",
            t.code()
        );
    }
    // And the surrounding psalm text is intact: Psalm 42 still has all 11 KJV verses.
    assert_eq!(
        verses_in(Translation::Kjv, &parse_one("Psalm 42").unwrap()).len(),
        11
    );
}
