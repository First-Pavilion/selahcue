//! Fuzzy quote/paraphrase detection (R4 fuzzy rung). Public-API tests over the bundled KJV
//! corpus: a spoken quotation → the most-likely verse; ordinary speech → nothing
//! (precision over recall, FR-121); deterministic; fuzzy-tolerant; bounded.

use selahcue_scripture::match_quote;

#[test]
fn quote_of_john_3_16_matches_the_verse() {
    // A near-verbatim KJV quotation of John 3:16, reference NOT named.
    let spoken = "For God so loved the world, that he gave his only begotten Son, \
                  that whosoever believeth in him should not perish, but have everlasting life";
    assert_eq!(match_quote(spoken), vec!["John 3:16".to_string()]);
}

#[test]
fn quote_of_psalm_23_matches_the_passage() {
    // KJV Psalm 23:1-2 (a distinctive multi-clause quotation). A very short verse alone
    // (e.g. "the Lord is my shepherd") is intentionally NOT recovered — too few rare words
    // to clear the precision bar — but a fuller quote is.
    let spoken = "the Lord is my shepherd I shall not want he maketh me to lie down \
                  in green pastures he leadeth me beside the still waters";
    let out = match_quote(spoken);
    assert_eq!(out.len(), 1, "expected one suggestion, got {out:?}");
    assert!(
        out[0].starts_with("Psalm") && out[0].contains("23:"),
        "expected a Psalm 23 verse, got {out:?}"
    );
}

#[test]
fn precision_ordinary_speech_yields_no_match() {
    // Ordinary service speech shares no distinctive verse vocabulary → no detection.
    for spoken in [
        "welcome to church today we are so glad that you came to worship with us this morning",
        "please find your seats and turn off your phones as we prepare our hearts to begin",
        "the offering baskets are coming around now so please give generously and cheerfully",
        "let us all stand together and greet the people sitting right next to us with a smile",
    ] {
        assert!(
            match_quote(spoken).is_empty(),
            "ordinary speech falsely matched: {spoken:?} -> {:?}",
            match_quote(spoken)
        );
    }
}

#[test]
fn precision_too_few_distinctive_words_yields_no_match() {
    // A couple of common words must not fire.
    assert!(match_quote("god is good all the time").is_empty());
    assert!(match_quote("let us pray together now").is_empty());
}

#[test]
fn fuzzy_partial_quote_of_a_long_verse_matches() {
    // Only the first clause of John 3:16 — a partial quote must still resolve the verse.
    let spoken = "for God so loved the world that he gave his only begotten Son";
    assert_eq!(match_quote(spoken), vec!["John 3:16".to_string()]);
}

#[test]
fn fuzzy_quote_with_a_misheard_word_still_matches() {
    // ASR mishears "begotten" as "forgotten" — the other distinctive words carry the match.
    let spoken = "For God so loved the world that he gave his only forgotten Son, \
                  that whosoever believeth in him should not perish but have everlasting life";
    assert_eq!(match_quote(spoken), vec!["John 3:16".to_string()]);
}

#[test]
fn determinism_same_input_same_output() {
    let spoken =
        "the Lord is my shepherd I shall not want he maketh me to lie down in green pastures";
    let a = match_quote(spoken);
    let b = match_quote(spoken);
    assert_eq!(a, b);
    assert!(!a.is_empty());
}

#[test]
fn bounded_pathological_input_is_handled() {
    // A very long, repetitive input must not blow up (candidate scoring is capped) and must
    // return a bounded result (at most one suggestion). Repeated calls stay consistent (the
    // index is built once).
    let spoke = "hallelujah ".repeat(5_000);
    let out = match_quote(&spoke);
    assert!(out.len() <= 1);
    assert_eq!(out, match_quote(&spoke));
}
