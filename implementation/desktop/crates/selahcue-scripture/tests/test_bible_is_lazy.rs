//! A bundled [`Bible`] handle must not make the table-backed questions cost a decode.
//!
//! `passage_exists` and `chapter_verse_bounds` answer from a compile-time verse-run table so the
//! operator can ask them after every command without a first-press stall (86ak84fbd). The handle
//! delegates to those functions for a bundled translation, and this is the check that it does: it
//! asks every bundled handle both questions and then verifies that no translation's index was
//! decoded, with a positive control (a lookup that DOES need the text does decode).
//!
//! It holds exactly one test and has no feature gate: the verse indices are process-wide
//! `OnceLock`s, so "has X been decoded yet?" is only a meaningful question in a process where
//! nothing else has touched X, and the property must hold in every feature configuration.

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{is_index_loaded, Bible, Translation};

#[test]
fn the_table_backed_questions_on_a_bundled_handle_decode_nothing() {
    // Keep the registry (when that feature is on) away from the developer's real data directory.
    #[cfg(feature = "installed")]
    std::env::set_var(
        selahcue_scripture::registry::DATA_DIR_ENV,
        std::env::temp_dir().join(format!("selahcue-lazy-{}", std::process::id())),
    );

    let refs = [
        parse_one("Psalm 23").unwrap(),
        parse_one("Romans 8:28-30").unwrap(),
        parse_one("Luke 17").unwrap(),
        parse_one("Jude 2:1").unwrap(),
    ];
    // Premise: nothing has decoded anything yet.
    for t in Translation::ALL {
        assert!(
            !is_index_loaded(t),
            "{} was decoded before the test began",
            t.code()
        );
    }

    for t in Translation::ALL {
        let h = Bible::from_code(t.code()).expect("a bundled code resolves");
        assert!(h.is_available());
        for r in &refs {
            let _ = h.passage_exists(r);
            let _ = h.chapter_verse_bounds(r);
        }
    }
    for t in Translation::ALL {
        assert!(
            !is_index_loaded(t),
            "{}: asking exists/bounds through the handle decoded the translation",
            t.code()
        );
    }

    // Positive control: a question that needs the text does decode, so the check above could fail.
    let kjv = Bible::bundled(Translation::Kjv);
    assert!(!kjv.verses(&refs[0]).is_empty());
    assert!(is_index_loaded(Translation::Kjv));
    // And the others are still untouched.
    assert!(!is_index_loaded(Translation::Web));

    // Without the registry feature a downloaded code resolves to nothing; with it (and no data
    // directory configured for this process) it is simply not installed.
    assert!(Bible::from_code("NOT-A-CODE").is_none());
    assert!(
        Bible::from_code("YLT").is_none(),
        "the placeholder Young's translation is gone"
    );
}
