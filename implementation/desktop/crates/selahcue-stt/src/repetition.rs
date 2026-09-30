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
/// The kept part is `text`'s own words up to the end of the first copy, re-joined with single
/// spaces, so its punctuation and casing are preserved.
///
/// Matching compares words lower-cased with everything except ASCII letters, digits and
/// apostrophes removed, so "screen." matches "screen" and "Look" matches "look". A repeat that
/// does not reach the end of the text is never touched, and neither is a refrain or anaphora that
/// recurs with other words in between.
///
/// Known limitation, accepted by 17tnw2b0nkq: a LEGITIMATE back-to-back repeat that happens to
/// end the text ("…we worship you, we worship you") is collapsed too. That is why the engine
/// applies this only to force-closed finals — the one place the decoder loop occurs — and never
/// to finals that closed on a pause or to interims.
///
/// Cost: at most O(w²) word comparisons for a w-word line (a 10 s final is ~30-60 words) and one
/// allocation for the normalised words; nothing is retained between calls.
pub fn trim_trailing_repeat(text: &str) -> Option<String> {
    let raw: Vec<&str> = text.split_whitespace().collect();
    let words: Vec<String> = raw.iter().map(|w| normalize_word(w)).collect();
    let m = words.len();
    // Shortest period first: a loop of a 4-word span is also periodic at 8, 12, ... words, and
    // the shortest period is the one whose first copy is the phrase actually spoken.
    for n in MIN_TRIM_SPAN_WORDS..=m / 2 {
        // Walk back from the end while every word equals the word one period earlier: `k` ends
        // at the first word of the SECOND copy of the longest n-periodic tail, so `raw[..k]` is
        // everything up to and including the first copy.
        let mut k = m;
        while k > n && words[k - 1] == words[k - 1 - n] {
            k -= 1;
        }
        // At least one full extra copy after the first (the final copy may still be partial).
        if m - k >= n {
            return Some(raw[..k].join(" "));
        }
    }
    None
}

/// One word, lower-cased, with everything except ASCII letters, digits and apostrophes removed.
/// May return an empty string for a token that is pure punctuation.
pub(crate) fn normalize_word(word: &str) -> String {
    word.chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '\'')
        .collect::<String>()
        .to_lowercase()
}

/// `text`'s words normalised by [`normalize_word`], dropping any that normalise to nothing.
#[cfg(test)]
pub(crate) fn normalized_words(text: &str) -> Vec<String> {
    text.split_whitespace()
        .map(normalize_word)
        .filter(|w| !w.is_empty())
        .collect()
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
}
