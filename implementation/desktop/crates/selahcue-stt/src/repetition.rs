//! Back-to-back phrase repetition in recognized text (86akcgmuh / 17tnw2b0nkq).
//!
//! When the engine force-closes an utterance at its hard sample cap, the cut usually lands
//! mid-word, and whisper.cpp's greedy decoder sometimes answers the abrupt ending by saying the
//! phrase just before the cut again ("…and then wait long and then wait long and then wait").
//! [`trim_trailing_repeat`] is the production correction the engine applies to exactly those
//! finals; `back_to_back_repeat` is the test-only detector the real-model repro test uses.

/// Minimum length, in words, of a repeated span [`trim_trailing_repeat`] will collapse. Shorter
/// spans are left alone: one- and two-word repeats are common in legitimate speech ("Holy, holy,
/// holy", "amen, amen", "praise him, praise him"), and every loop the 86akcgmuh spike observed
/// repeated three or more words.
pub const MIN_TRIM_SPAN_WORDS: usize = 3;

/// Collapse a back-to-back repeat that runs to the very END of `text` into its first copy.
///
/// Returns `Some(trimmed)` when `text` ends inside a verbatim back-to-back repeat of a span of at
/// least [`MIN_TRIM_SPAN_WORDS`] words — two or more complete copies, where the last copy may be
/// cut short by the end of the text — and `None` otherwise (the caller keeps `text` unchanged).
/// The kept part is `text`'s own tokens up to the end of the first copy, re-joined with single
/// spaces, so its punctuation and casing are preserved.
///
/// Words are compared by [`normalize_word`]: lower-cased, letters and digits of ANY script kept
/// (so Yoruba "ọlọ" and "ẹlẹ" stay two different words), apostrophes kept, other punctuation
/// removed, so "screen." matches "screen" and "Look" matches "look". A token that normalises to
/// nothing (a bare "-", "—", "…") is not a word: it is neither a match nor a break, it is ignored
/// like whitespace, so a loop whose copies are separated by a dash is still found and a run of
/// dashes can never be mistaken for a repeated phrase. The trimmed text ends at the last WORD of
/// the first copy; separator tokens between the copies go with the removed repeat. A repeat that
/// does not reach the end of the text is never touched, and neither is a refrain or anaphora that
/// recurs with other words in between.
///
/// Known limitation, accepted by 17tnw2b0nkq: a LEGITIMATE back-to-back repeat that happens to
/// end the text ("…we worship you, we worship you") is collapsed too. That is why the engine
/// applies this only to force-closed finals — the one place the decoder loop occurs — and never
/// to finals that closed on a pause or to interims.
///
/// Cost: at most O(w²) word comparisons for a w-word line (a 10 s final is ~30-60 words) and two
/// small allocations (the token list and the normalised words); nothing is retained between calls.
pub fn trim_trailing_repeat(text: &str) -> Option<String> {
    let raw: Vec<&str> = text.split_whitespace().collect();
    // `words[i]` = (index into `raw`, normalised form) of the i-th real word; see `indexed_words`.
    let words = indexed_words(&raw);
    let m = words.len();
    // Shortest period first: a loop of a 4-word span is also periodic at 8, 12, ... words, and
    // the shortest period is the one whose first copy is the phrase actually spoken.
    for n in MIN_TRIM_SPAN_WORDS..=m / 2 {
        // Walk back from the end while every word equals the word one period earlier: `k` ends
        // at the first word of the SECOND copy of the longest n-periodic tail, so `words[k - 1]`
        // is the last word of the first copy.
        let mut k = m;
        while k > n && words[k - 1].1 == words[k - 1 - n].1 {
            k -= 1;
        }
        // At least one full extra copy after the first (the final copy may still be partial).
        if m - k >= n {
            return Some(raw[..=words[k - 1].0].join(" "));
        }
    }
    None
}

/// The single definition of "what is a word" that [`trim_trailing_repeat`] and the test-only
/// [`back_to_back_repeat`] detector (via `normalized_words`) both consume: each token of `raw`
/// that still has a letter or digit after [`normalize_word`], as (its index in `raw`, its
/// normalised form). Tokens that normalise to nothing are dropped, so they can never compare
/// equal to one another.
fn indexed_words(raw: &[&str]) -> Vec<(usize, String)> {
    raw.iter()
        .enumerate()
        .filter_map(|(i, token)| {
            let word = normalize_word(token);
            (!word.is_empty()).then_some((i, word))
        })
        .collect()
}

/// The comparison form of one whitespace-delimited token, or an empty string when the token is
/// not a word at all.
///
/// - Lower-cased with Unicode rules (`str::to_lowercase`).
/// - Letters and digits of every script are kept (`char::is_alphanumeric`), as are apostrophes
///   (U+0027), so "don't" stays one word. Everything else (punctuation, symbols) is removed. This
///   used to keep ASCII only, which deleted every non-ASCII letter: "ọlọ" and "ẹlẹ" both became
///   "l" and compared equal, so a line of distinct Yoruba, Igbo, French or Spanish words could
///   read as a loop and have real words cut off.
/// - Combining diacritical marks are kept ([`is_combining_mark`]): they are not alphanumeric, but
///   they are part of the word — Yoruba tone and dot-below marks are lexical, and "bà", "bá" and
///   "bè" are different words.
/// - Canonical equivalence: the same word can arrive precomposed (NFC, "ọ" = U+1ECD) or
///   decomposed (NFD, "o" + U+0323), and the two must compare equal. This crate carries no
///   Unicode-normalisation dependency, so [`compose_marks`] composes the base+mark pairs of a
///   fixed table — the Latin-1 Supplement accented lowercase letters plus the Yoruba letters ẹ ọ ṣ
///   ń ǹ ḿ ([`COMPOSED`]). Anything outside that table (other scripts, accented letters beyond
///   Latin-1, marks stacked in non-canonical order) is compared exactly as written: the failure
///   mode is two copies of one word that differ only in normalisation form not matching, i.e. a
///   missed trim, never a false one. Full canonical equivalence needs a normalisation crate
///   (for example `unicode-normalization`), which is a dependency decision for the owner.
/// - A token with no letter or digit left (a lone "-", "—", "…", "'" or a bare mark) is not a
///   word: the result is empty, and callers must not count it as a match.
pub(crate) fn normalize_word(word: &str) -> String {
    let kept: String = word
        .chars()
        .filter(|&c| c.is_alphanumeric() || c == '\'' || is_combining_mark(c))
        .collect();
    if !kept.chars().any(char::is_alphanumeric) {
        return String::new();
    }
    compose_marks(&kept.to_lowercase())
}

/// Whether `c` is in one of the Unicode combining-diacritical-mark blocks: Combining Diacritical
/// Marks (U+0300-036F, which holds every Yoruba tone mark and the dot below U+0323), its Extended
/// and Supplement blocks, Combining Marks for Symbols, and Combining Half Marks. Marks in other
/// scripts (Indic, Arabic, Hebrew vowel signs) are already `is_alphanumeric`.
fn is_combining_mark(c: char) -> bool {
    matches!(
        c,
        '\u{0300}'..='\u{036F}'
            | '\u{1AB0}'..='\u{1AFF}'
            | '\u{1DC0}'..='\u{1DFF}'
            | '\u{20D0}'..='\u{20FF}'
            | '\u{FE20}'..='\u{FE2F}'
    )
}

/// (base letter, combining mark, precomposed letter) for the lower-case pairs [`compose_marks`]
/// folds to the precomposed form. Every row is the canonical decomposition of its third field,
/// checked against Python's `unicodedata` when the table was written.
const COMPOSED: &[(char, char, char)] = &[
    ('a', '\u{0300}', '\u{00E0}'), // à
    ('a', '\u{0301}', '\u{00E1}'), // á
    ('a', '\u{0302}', '\u{00E2}'), // â
    ('a', '\u{0303}', '\u{00E3}'), // ã
    ('a', '\u{0308}', '\u{00E4}'), // ä
    ('a', '\u{030A}', '\u{00E5}'), // å
    ('c', '\u{0327}', '\u{00E7}'), // ç
    ('e', '\u{0300}', '\u{00E8}'), // è
    ('e', '\u{0301}', '\u{00E9}'), // é
    ('e', '\u{0302}', '\u{00EA}'), // ê
    ('e', '\u{0308}', '\u{00EB}'), // ë
    ('i', '\u{0300}', '\u{00EC}'), // ì
    ('i', '\u{0301}', '\u{00ED}'), // í
    ('i', '\u{0302}', '\u{00EE}'), // î
    ('i', '\u{0308}', '\u{00EF}'), // ï
    ('n', '\u{0303}', '\u{00F1}'), // ñ
    ('o', '\u{0300}', '\u{00F2}'), // ò
    ('o', '\u{0301}', '\u{00F3}'), // ó
    ('o', '\u{0302}', '\u{00F4}'), // ô
    ('o', '\u{0303}', '\u{00F5}'), // õ
    ('o', '\u{0308}', '\u{00F6}'), // ö
    ('u', '\u{0300}', '\u{00F9}'), // ù
    ('u', '\u{0301}', '\u{00FA}'), // ú
    ('u', '\u{0302}', '\u{00FB}'), // û
    ('u', '\u{0308}', '\u{00FC}'), // ü
    ('y', '\u{0301}', '\u{00FD}'), // ý
    ('y', '\u{0308}', '\u{00FF}'), // ÿ
    // Yoruba: the dot-below letters and the tone-marked nasals that have precomposed forms.
    ('e', '\u{0323}', '\u{1EB9}'), // ẹ
    ('o', '\u{0323}', '\u{1ECD}'), // ọ
    ('s', '\u{0323}', '\u{1E63}'), // ṣ
    ('n', '\u{0301}', '\u{0144}'), // ń
    ('n', '\u{0300}', '\u{01F9}'), // ǹ
    ('m', '\u{0301}', '\u{1E3F}'), // ḿ
];

/// `text` (already lower-cased) with each base letter + combining mark pair in [`COMPOSED`]
/// replaced by its precomposed letter, so NFC and NFD spellings of the covered letters come out
/// identical. Marks that do not form a covered pair are left in place after their base.
fn compose_marks(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        if is_combining_mark(c) {
            let composed = out.chars().next_back().and_then(|base| {
                COMPOSED
                    .iter()
                    .find(|&&(b, m, _)| b == base && m == c)
                    .map(|&(_, _, precomposed)| precomposed)
            });
            if let Some(precomposed) = composed {
                out.pop();
                out.push(precomposed);
                continue;
            }
        }
        out.push(c);
    }
    out
}

/// `text`'s words normalised by [`normalize_word`], dropping any token that is not a word.
#[cfg(test)]
pub(crate) fn normalized_words(text: &str) -> Vec<String> {
    let raw: Vec<&str> = text.split_whitespace().collect();
    indexed_words(&raw).into_iter().map(|(_, w)| w).collect()
}

/// 86akcgmuh — the repetition-loop failure shape, as a test-only detector: the longest
/// BACK-TO-BACK verbatim repeat of a word span anywhere in `text` — a span of >= 4 words repeated
/// at least twice in a row ("and then wait long and then wait long and then wait"), or a 2-3 word
/// span repeated at least three times in a row ("Phil Philadelphian Phil Philadelphian Phil
/// Philadelphian"). Returns the repeated span and how many times it occurs in a row.
///
/// Deliberately does NOT flag a repeat that is not adjacent (a refrain like Psalm 136's "for his
/// loving kindness endures forever" recurring between different lines, or anaphora like "He is
/// faithful when ... he is faithful when ..."), a single repeated word ("Holy, holy, holy"), or a
/// short phrase said exactly twice ("who was and who is and who is to come" contains "and who is
/// and who is" — Revelation 4:8, legitimately). The fixtures this guards contain no such repeat
/// of their own, so any hit is the decoder looping. Used by the default-build unit test below
/// (positive + negative controls) and the real-model repro test in `recognizer.rs`'s
/// `whisper_tests`, so the control and the assertion cannot drift apart.
///
/// Stricter than [`trim_trailing_repeat`] about SHORT spans on purpose: it is a loop detector
/// over whole lines, the trim is a correction applied only at a force-close boundary.
#[cfg(test)]
pub(crate) fn back_to_back_repeat(text: &str) -> Option<(String, usize)> {
    let words = normalized_words(text);
    let m = words.len();
    let mut best: Option<(usize, String, usize)> = None;
    for n in 2..=20 {
        if 2 * n > m {
            break;
        }
        for i in 0..=(m - 2 * n) {
            if words[i..i + n] != words[i + n..i + 2 * n] {
                continue;
            }
            let mut k = 2;
            while i + (k + 1) * n <= m && words[i..i + n] == words[i + k * n..i + (k + 1) * n] {
                k += 1;
            }
            if n < 4 && k < 3 {
                continue;
            }
            if best.as_ref().is_none_or(|b| n * k > b.0) {
                best = Some((n * k, words[i..i + n].join(" "), k));
            }
        }
    }
    best.map(|(_, span, k)| (span, k))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Legitimate repetition from sermons and scripture that neither function may treat as a
    /// decoder loop. Shared by both tests below so the controls cannot drift apart.
    const LEGITIMATE: [&str; 6] = [
        // single repeated word (liturgy)
        "Holy, holy, holy is the Lord God Almighty, who was and who is and who is to come.",
        // non-adjacent refrain (Psalm 136, WEB)
        "Give thanks to Yahweh, for he is good; for his loving kindness endures forever. \
         Give thanks to the God of gods; for his loving kindness endures forever.",
        // anaphora (sermon rhetoric)
        "He is faithful when the harvest is plentiful, and he is faithful when the field is bare.",
        "It was the starting point. It was the foundation poured before the first brick was laid.",
        // a two-word repeat at the very end (shorter than MIN_TRIM_SPAN_WORDS)
        "so we say amen, amen",
        "",
    ];

    /// 86akcgmuh: the detector the real-model repro test relies on must (a) flag every loop
    /// shape actually observed at the 10 s force-close (verbatim model outputs from the scoping
    /// spike, large-v3-turbo, audio_ctx=512) and (b) NOT flag legitimate repetition that
    /// sermons and scripture are full of — otherwise "no loop" would be either vacuous or a
    /// false alarm. Runs in the default build: no model, no native toolchain.
    #[test]
    fn back_to_back_repeat_flags_observed_loops_and_spares_legitimate_repetition() {
        for (loop_text, span) in [
            (
                "Ask them how they are really doing, and then wait long and then wait long and then wait",
                "and then wait long",
            ),
            (
                "Do not just sing the words on the screen. Look at the one the words on the \
                 screen. Look at the one the words on the",
                "the words on the screen look at the one",
            ),
            (
                "It was the starting point. It was the starting point. It was the foundation \
                 poured before the first.",
                "it was the starting point",
            ),
            (
                "Pierre Clovis around the throne Poor Phil Philadelphian Phil Philadelphian Phil \
                 Philadelphian Phil Philadelphian was",
                "phil philadelphian",
            ),
        ] {
            let hit = back_to_back_repeat(loop_text);
            assert_eq!(
                hit.as_ref().map(|(s, _)| s.as_str()),
                Some(span),
                "must flag the observed loop in {loop_text:?}, got {hit:?}"
            );
        }
        for clean in LEGITIMATE {
            assert_eq!(
                back_to_back_repeat(clean),
                None,
                "false alarm on legitimate text {clean:?}"
            );
        }
    }

    /// 17tnw2b0nkq: the trim collapses every TRAILING loop shape the spike observed — with the
    /// last copy complete or cut short — to the text's first copy, keeping its original
    /// punctuation; and it leaves alone both legitimate repetition and a loop that does not reach
    /// the end of the line (the trim only ever touches a line's tail).
    #[test]
    fn trim_trailing_repeat_collapses_trailing_loops_to_their_first_copy() {
        for (looped, expected) in [
            // last copy cut short by the force-close (fixture A, verbatim)
            (
                "So this week, reach out to someone in this room you do not usually talk to. Ask \
                 them how they are really doing, and then wait long and then wait long and then wait",
                "So this week, reach out to someone in this room you do not usually talk to. Ask \
                 them how they are really doing, and then wait long",
            ),
            // span crossing a sentence boundary, last copy partial (fixture B, verbatim)
            (
                "Do not just sing the words on the screen. Look at the one the words on the \
                 screen. Look at the one the words on the",
                "Do not just sing the words on the screen. Look at the one",
            ),
            // two complete copies
            (
                "It does not come from the valley getting shorter. It comes from the one who \
                 walks. It comes from the one who walks.",
                "It does not come from the valley getting shorter. It comes from the one who walks.",
            ),
            // three complete copies, case differs between copies
            (
                "and he is faithful when the doctor calls with good news, And he is faithful when \
                 the doctor calls with good news, and he is faithful when the doctor calls with \
                 good news.",
                "and he is faithful when the doctor calls with good news,",
            ),
        ] {
            assert_eq!(
                trim_trailing_repeat(looped).as_deref(),
                Some(expected),
                "must collapse the trailing loop in {looped:?}"
            );
        }
        // A loop in the middle of the line, followed by new words, is not a TRAILING repeat.
        let mid = "It was the starting point. It was the starting point. It was the foundation \
                   poured before the first.";
        assert_eq!(
            trim_trailing_repeat(mid),
            None,
            "mid-line loop must be left alone"
        );
        for clean in LEGITIMATE {
            assert_eq!(
                trim_trailing_repeat(clean),
                None,
                "trimmed legitimate text {clean:?}"
            );
        }
    }

    // --- Unicode words, canonical equivalence and punctuation-only tokens -------------------
    //
    // Every non-ASCII string below is written with \u escapes on purpose: the whole point is
    // WHICH normalisation form (NFC precomposed vs NFD base + combining mark) reaches the
    // function, and a source-level literal can be silently re-normalised by an editor or tool.

    /// "ọlọ" and "ẹlẹ" — Yoruba words that differ only in non-ASCII letters (NFC).
    const OLO: &str = "\u{1ECD}l\u{1ECD}";
    const ELE: &str = "\u{1EB9}l\u{1EB9}";
    /// The same two words, decomposed (NFD): base letter + U+0323 COMBINING DOT BELOW.
    const OLO_NFD: &str = "o\u{323}lo\u{323}";
    const ELE_NFD: &str = "e\u{323}le\u{323}";
    /// "ọlọ́run ni ọba wa" (NFC; the tone mark U+0301 has no precomposed form after ọ).
    const OLORUN_NI_OBA_WA: &str = "\u{1ECD}l\u{1ECD}\u{301}run ni \u{1ECD}ba wa";
    /// The same phrase decomposed (NFD).
    const OLORUN_NI_OBA_WA_NFD: &str = "o\u{323}lo\u{323}\u{301}run ni o\u{323}ba wa";
    /// "ọlọ́run ni" — the same phrase cut short mid-copy by the force-close.
    const OLORUN_NI: &str = "\u{1ECD}l\u{1ECD}\u{301}run ni";
    const OLORUN_NI_NFD: &str = "o\u{323}lo\u{323}\u{301}run ni";

    /// Decompose the covered letters of `text` (the inverse of [`COMPOSED`]), to build NFD
    /// spellings of lower-case test text. Uncovered characters pass through unchanged.
    fn decompose(text: &str) -> String {
        text.chars()
            .flat_map(|c| {
                let pair = COMPOSED.iter().find(|&&(_, _, pre)| pre == c);
                let (first, second) = match pair {
                    Some(&(base, mark, _)) => (base, Some(mark)),
                    None => (c, None),
                };
                std::iter::once(first).chain(second)
            })
            .collect()
    }

    /// The review of 17tnw2b0nkq's PR: `normalize_word` kept only ASCII alphanumerics, so every
    /// non-ASCII letter was deleted. It must keep letters and digits of every script, lower-case
    /// them, and never let two different words collapse to one comparison form.
    #[test]
    fn normalize_word_keeps_unicode_letters_so_distinct_words_stay_distinct() {
        // English is unchanged: case, trailing/leading punctuation, apostrophes, digits.
        assert_eq!(normalize_word("Screen."), "screen");
        assert_eq!(normalize_word("(Look),"), "look");
        assert_eq!(normalize_word("don't"), "don't");
        assert_eq!(normalize_word("1,000"), "1000");

        // Yoruba: the two words of the review's reproduction keep their letters (and lower-case
        // Unicode upper-case) instead of both collapsing to "l".
        assert_eq!(normalize_word(OLO), OLO);
        assert_eq!(normalize_word(ELE), ELE);
        assert_ne!(normalize_word(OLO), normalize_word(ELE));
        assert_eq!(normalize_word("\u{1ECC}L\u{1ECC}!"), OLO);

        // Accented Latin, Greek and Cyrillic keep their letters.
        assert_eq!(normalize_word("Caf\u{E9},"), "caf\u{E9}");
        assert_ne!(normalize_word("caf\u{E9}"), normalize_word("cafe"));
        assert_eq!(
            normalize_word("\u{39B}\u{3CC}\u{3B3}\u{3BF}\u{3C2}"),
            "\u{3BB}\u{3CC}\u{3B3}\u{3BF}\u{3C2}"
        );
        assert_eq!(
            normalize_word("\u{411}\u{43E}\u{433}"),
            "\u{431}\u{43E}\u{433}"
        );

        // Combining marks are part of the word: tone-only minimal pairs are different words.
        let (low, high, mid) = (
            normalize_word("ba\u{300}"),
            normalize_word("ba\u{301}"),
            normalize_word("ba"),
        );
        assert!(
            low != high && low != mid && high != mid,
            "{low:?} {high:?} {mid:?}"
        );
    }

    /// A token with no letter or digit is not a word: its normalised form is empty, which the
    /// callers drop rather than compare.
    #[test]
    fn normalize_word_gives_an_empty_form_to_tokens_that_are_not_words() {
        for token in [
            "-",
            "\u{2014}",
            "...",
            "\u{2026}",
            "'",
            "''",
            "\u{301}",
            "-\u{301}",
            "(\u{2022})",
        ] {
            assert_eq!(normalize_word(token), "", "{token:?} is not a word");
        }
        assert_eq!(normalized_words("a - \u{2014} b ... c"), ["a", "b", "c"]);
    }

    /// NFC and NFD spellings of the same word must compare equal, for every letter the crate's
    /// table covers — Yoruba dot-below letters and tone-marked words, and the Latin-1 accented
    /// letters — including upper-case input, which is lower-cased before composing.
    #[test]
    fn nfc_and_nfd_spellings_of_the_same_word_compare_equal() {
        for (nfc, nfd) in [
            // Yoruba: ẹ ọ ṣ, whole words, and a tone mark stacked on a dot-below letter.
            ("\u{1EB9}", "e\u{323}"),
            ("\u{1ECD}", "o\u{323}"),
            ("\u{1E63}", "s\u{323}"),
            (OLO, OLO_NFD),
            (ELE, ELE_NFD),
            ("\u{1ECD}\u{301}", "o\u{323}\u{301}"),
            ("\u{1ECC}\u{300}", "O\u{323}\u{300}"),
            ("\u{1E62}\u{E9}", "S\u{323}e\u{301}"),
            ("\u{144}", "n\u{301}"),
            ("\u{1F9}", "n\u{300}"),
            ("\u{1E3F}", "m\u{301}"),
            // Latin-1: acute, grave, circumflex, tilde, diaeresis, ring, cedilla.
            ("caf\u{E9}", "cafe\u{301}"),
            ("se\u{F1}or", "sen\u{303}or"),
            ("\u{DC}ber", "U\u{308}ber"),
            ("fa\u{E7}ade", "fac\u{327}ade"),
            ("\u{E5}ngstr\u{F6}m", "a\u{30A}ngstro\u{308}m"),
            (
                "cr\u{E8}me br\u{FB}l\u{E9}e",
                "cre\u{300}me bru\u{302}le\u{301}e",
            ),
        ] {
            assert_eq!(
                normalize_word(nfc),
                normalize_word(nfd),
                "NFC {nfc:?} and NFD {nfd:?} must normalise identically"
            );
            assert_ne!(normalize_word(nfd), "", "{nfd:?} lost every letter");
        }
        // ... and a base letter with a DIFFERENT mark, or none, is still a different word.
        assert_ne!(normalize_word("o\u{323}"), normalize_word("o\u{301}"));
        assert_ne!(normalize_word("o\u{323}"), normalize_word("o"));
    }

    /// The composition table's own invariants, so a bad row cannot hide behind the examples
    /// above: a lower-case ASCII base, a mark that `is_combining_mark` accepts (else it would
    /// be filtered out before composing), a lower-case alphabetic result, and no duplicate pair.
    #[test]
    fn the_composition_table_is_well_formed() {
        for (i, &(base, mark, composed)) in COMPOSED.iter().enumerate() {
            assert!(base.is_ascii_lowercase(), "row {i}: base {base:?}");
            assert!(
                is_combining_mark(mark),
                "row {i}: mark {mark:?} would be filtered out"
            );
            assert!(
                composed.is_alphabetic() && composed.to_lowercase().eq(std::iter::once(composed)),
                "row {i}: {composed:?} must be a lower-case letter"
            );
            assert!(
                !composed.is_ascii(),
                "row {i}: {composed:?} is not precomposed"
            );
            assert!(
                !COMPOSED[..i]
                    .iter()
                    .any(|&(b, m, _)| (b, m) == (base, mark)),
                "row {i}: duplicate ({base:?}, {mark:?})"
            );
        }
        // `decompose` (the tests' NFD builder) round-trips through `normalize_word`.
        for &(_, _, composed) in COMPOSED {
            let nfc = composed.to_string();
            assert_ne!(decompose(&nfc), nfc, "{composed:?} did not decompose");
            assert_eq!(normalize_word(&decompose(&nfc)), nfc);
        }
    }

    /// The review's reproduction: "ọlọ ẹlẹ ọlọ ẹlẹ ọlọ ẹlẹ" used to normalise to six "l"s and be
    /// "trimmed" to "ọlọ ẹlẹ ọlọ", cutting real words. Two alternating Yoruba words are not a
    /// loop of a 3-word span, in NFC or NFD, with either word order.
    #[test]
    fn trim_leaves_distinct_yoruba_words_alone() {
        for (a, b) in [(OLO, ELE), (ELE, OLO), (OLO_NFD, ELE_NFD)] {
            let line = format!("{a} {b} {a} {b} {a} {b}");
            assert_eq!(trim_trailing_repeat(&line), None, "trimmed {line:?}");
        }
        // The same shape in accented Latin: six different words that differ only in an accent.
        let accents = [
            "s\u{E9}", "s\u{ED}", "s\u{F3}", "s\u{FA}", "s\u{E1}", "s\u{E0}",
        ];
        assert_eq!(trim_trailing_repeat(&accents.join(" ")), None);
        // ... and in tone-marked Yoruba, where tone is lexical.
        let tones = [
            "ba\u{300}",
            "ba\u{301}",
            "be\u{300}",
            "bi\u{300}",
            "bo\u{300}",
            "bu\u{300}",
        ];
        assert_eq!(trim_trailing_repeat(&tones.join(" ")), None);
        let tones_nfd = [
            "ba\u{300}",
            "ba\u{301}",
            "be\u{300}",
            "bi\u{301}",
            "bo\u{323}\u{300}",
            "bu\u{300}",
        ];
        assert_eq!(trim_trailing_repeat(&tones_nfd.join(" ")), None);
        // Marks with no precomposed form (macron, caron) must survive too: dropping them would
        // turn these six different words into "ba" six times.
        let bare_marks = [
            "ba\u{300}",
            "ba\u{301}",
            "ba\u{304}",
            "ba\u{30C}",
            "ba\u{302}",
            "ba\u{303}",
        ];
        assert_eq!(trim_trailing_repeat(&bare_marks.join(" ")), None);
    }

    /// A REAL loop in Yoruba / code-switched text is still trimmed (the positive control for the
    /// test above: "never trims non-ASCII" would pass it vacuously), with the last copy complete
    /// or cut short, and the output keeps the speaker's own spelling and punctuation.
    #[test]
    fn trim_collapses_a_trailing_loop_in_yoruba_and_accented_text() {
        // Code-switched English + Yoruba, last copy cut short.
        let looped =
            format!("Let us say it together, {OLORUN_NI_OBA_WA} {OLORUN_NI_OBA_WA} {OLORUN_NI}");
        assert_eq!(
            trim_trailing_repeat(&looped).as_deref(),
            Some(format!("Let us say it together, {OLORUN_NI_OBA_WA}").as_str())
        );
        // Accented Latin, two complete copies.
        assert_eq!(
            trim_trailing_repeat("we met at the caf\u{E9} we met at the caf\u{E9}").as_deref(),
            Some("we met at the caf\u{E9}")
        );
    }

    /// NFC vs NFD: a loop whose copies are spelled in DIFFERENT normalisation forms is still one
    /// loop (the decoder emitting the same word two ways must not hide it), and the trimmed text
    /// keeps the first copy exactly as spelled.
    #[test]
    fn trim_sees_through_nfc_and_nfd_spelling_differences_between_copies() {
        // Copy 1 NFC, copy 2 NFD, copy 3 (partial) NFC.
        let line = format!("go on {OLORUN_NI_OBA_WA} {OLORUN_NI_OBA_WA_NFD} {OLORUN_NI}");
        assert_eq!(
            trim_trailing_repeat(&line).as_deref(),
            Some(format!("go on {OLORUN_NI_OBA_WA}").as_str())
        );
        // Copy 1 NFD, copy 2 NFC, copy 3 (partial) NFD.
        let line = format!("go on {OLORUN_NI_OBA_WA_NFD} {OLORUN_NI_OBA_WA} {OLORUN_NI_NFD}");
        assert_eq!(
            trim_trailing_repeat(&line).as_deref(),
            Some(format!("go on {OLORUN_NI_OBA_WA_NFD}").as_str())
        );
        // Accented Latin, NFC then NFD (the mixed-form loop `decompose` builds for every row).
        let nfc = "we sat in the caf\u{E9} we sat in the caf\u{E9} we sat";
        assert_eq!(
            decompose(nfc),
            "we sat in the cafe\u{301} we sat in the cafe\u{301} we sat"
        );
        let mixed = format!(
            "we sat in the caf\u{E9} {} we sat",
            decompose("we sat in the caf\u{E9}")
        );
        assert_eq!(
            trim_trailing_repeat(&mixed).as_deref(),
            Some("we sat in the caf\u{E9}")
        );
        assert_eq!(
            trim_trailing_repeat(&decompose(nfc)).as_deref(),
            Some(decompose("we sat in the caf\u{E9}").as_str())
        );
    }

    /// Punctuation-only tokens ("-", "—", "…") used to normalise to the empty string, and every
    /// empty string equalled every other, so a run of dashes read as a repeated phrase. They are
    /// not words: a run of them is never a loop, and they neither match nor break a real one.
    #[test]
    fn trim_ignores_punctuation_only_tokens() {
        // Never a loop on their own, nor after real words ("a b c - - - - - -" used to come
        // back as "a b c - - -").
        for line in [
            "- - - - - -",
            "\u{2014} \u{2014} \u{2014} \u{2014} \u{2014} \u{2014} \u{2014}",
            "... ... ... ... ... ...",
            "' ' ' ' ' '",
            "a b c - - - - - -",
            "so we say - - - - - - - - -",
            "a \u{2026} b \u{2026} c \u{2026} d \u{2026}",
        ] {
            assert_eq!(trim_trailing_repeat(line), None, "trimmed {line:?}");
        }
        // A real loop whose copies are separated by a dash token is still found, and the
        // separator goes with the removed copy instead of dangling after the first.
        assert_eq!(
            trim_trailing_repeat(
                "Ask them how they are, and then wait long \u{2014} and then wait long \u{2014} \
                 and then wait"
            )
            .as_deref(),
            Some("Ask them how they are, and then wait long")
        );
        // ... including a dash that is the very last token.
        assert_eq!(
            trim_trailing_repeat("and then wait long and then wait long and then wait -")
                .as_deref(),
            Some("and then wait long")
        );
        // A dash INSIDE the first copy is the speaker's own punctuation and is kept.
        assert_eq!(
            trim_trailing_repeat("so - and then wait long so - and then wait long so - and then")
                .as_deref(),
            Some("so - and then wait long")
        );
    }

    /// The test-only detector and the production trim share one definition of a word, so a
    /// punctuation-only token cannot be a word to one and not the other, and neither mistakes
    /// accent-only variants for a loop. (The real-model repro test in `recognizer.rs` relies on
    /// `normalized_words`/`back_to_back_repeat` exactly as the engine's trim relies on
    /// `indexed_words`.)
    #[test]
    fn the_detector_and_the_trim_agree_on_unicode_and_punctuation_tokens() {
        // Accent-only variants: six different words, not a "b b b b b b" loop.
        let tones = [
            "ba\u{300}",
            "ba\u{301}",
            "be\u{300}",
            "bi\u{300}",
            "bo\u{300}",
            "bu\u{300}",
        ];
        assert_eq!(back_to_back_repeat(&tones.join(" ")), None);
        // Dashes are not words to the detector either.
        assert_eq!(back_to_back_repeat("- - - - - - - - -"), None);
        // A real Yoruba loop is flagged, in NFC and with NFD copies mixed in.
        for line in [
            format!("{OLORUN_NI_OBA_WA} {OLORUN_NI_OBA_WA} {OLORUN_NI}"),
            format!("{OLORUN_NI_OBA_WA} {OLORUN_NI_OBA_WA_NFD} {OLORUN_NI}"),
        ] {
            let hit = back_to_back_repeat(&line);
            assert_eq!(
                hit.as_ref().map(|(_, times)| *times),
                Some(2),
                "must flag the loop in {line:?}, got {hit:?}"
            );
            assert!(
                trim_trailing_repeat(&line).is_some(),
                "the trim must see it too: {line:?}"
            );
        }
        // Consistency on the shared tokenizer: the trimmed text's words are a prefix of the
        // original's, and what follows is a repeat of the span.
        let looped =
            "Ask them how, and then wait long \u{2014} and then wait long \u{2014} and then wait";
        let trimmed = trim_trailing_repeat(looped).expect("a trailing loop");
        let (all, kept) = (normalized_words(looped), normalized_words(&trimmed));
        assert_eq!(all[..kept.len()], kept[..]);
        assert_eq!(kept.join(" "), "ask them how and then wait long");
    }
}
