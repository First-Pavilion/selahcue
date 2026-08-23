//! The bounded, thread-local text-measurement cache that backs the auto-fit layout
//! (`compose::autofit_layers`) — key correctness, reuse across composes, and its bound.
//!
//! Several tests here name a control in their title ("at the wrong cell", "differing only
//! in typography"). The bar for those is stated in each one: **the test must fail if the
//! control it names is removed.** Two of them did not meet that bar and were rewritten —
//! see the comments in place for what was wrong and what now carries the contract.

#![allow(clippy::unwrap_used)]

use selahcue_engine::raster::measure_line_width;
use selahcue_engine::scene::Frame;
use selahcue_present::measure::{
    measure_cache_hits_for, measure_cache_len, measure_cache_stats, measure_word,
    reset_measure_cache, MAX_MEASURE_CACHE_ENTRIES, MAX_MEASURE_CACHE_TEXT_BYTES,
};
use selahcue_present::stage::StageTemplate;
use selahcue_present::{
    compose_slide, compose_stage, FontName, Slide, StageContext, StageTheme, Theme, TimerView,
};

#[test]
fn every_shaping_attribute_is_part_of_the_cache_key() {
    // THE BAR FOR THIS TEST: it must fail if any attribute it names is dropped from the
    // key. Mutation-checked — dropping `font` or `weight` from `measure::Key` turns it
    // red. It is also the PORTABLE guard for those two attributes: the layout-level test
    // at the bottom of this file can only see an attribute that moves a shaped width on
    // the host it runs on, and weight does not (see there). This one compares keys, so it
    // holds everywhere.
    reset_measure_cache();
    // The family need not be installed — the KEY must distinguish it either way, or a
    // themed region would silently be laid out with the default face's widths.
    let font = FontName::new("Arial").unwrap();
    // One shaping attribute changed per case, same text throughout.
    let cases: [(u32, Option<FontName>, u16); 4] = [
        (40, None, 400),
        (41, None, 400),       // differs by cell only
        (40, None, 700),       // differs by weight only
        (40, Some(font), 400), // differs by font only
    ];
    for (cell, f, w) in cases {
        measure_word("Hallelujah", cell, f.as_ref(), w);
    }
    assert_eq!(
        measure_cache_len(),
        cases.len(),
        "each distinct (text, cell, font, weight) needs its OWN entry — sharing one \
         would hand a caller another attribute's width and corrupt the layout"
    );
    // Separate entries is not the whole contract: none of those four lookups may have
    // been ANSWERED from another's entry. An entry that has served nothing yet reports
    // `Some(0)`; anything above zero means one variant was handed another's width.
    for (cell, f, w) in cases {
        assert_eq!(
            measure_cache_hits_for("Hallelujah", cell, f.as_ref(), w),
            Some(0),
            "the entry for cell={cell} weight={w} SERVED one of the other three variants"
        );
    }
    // Every cached read must equal the uncached shaping truth.
    for (cell, f, w) in cases {
        assert_eq!(
            measure_word("Hallelujah", cell, f.as_ref(), w),
            measure_line_width("Hallelujah", cell, f.as_ref(), w),
            "cached width diverged from a fresh shaping at cell={cell} weight={w}"
        );
    }
    // POSITIVE CONTROL: that second pass was SERVED FROM THE MEMO. Without this, every
    // assertion above holds just as well with the memo bypassed — nothing stored, nothing
    // shared, nothing to get wrong — and the test would be green while guarding nothing.
    for (cell, f, w) in cases {
        assert_eq!(
            measure_cache_hits_for("Hallelujah", cell, f.as_ref(), w),
            Some(1),
            "the second read at cell={cell} weight={w} was not served from the memo — the \
             memo is inert here, so nothing above says anything about the key"
        );
    }
}

/// Distinct words fed at the cache in the bound tests — chosen well above any plausible
/// cap so the assertion is about the POLICY, not about a particular cap value.
const PROBES: usize = 12_000;

#[test]
fn a_flood_of_distinct_words_cannot_grow_the_cache_without_limit() {
    reset_measure_cache();
    for i in 0..PROBES {
        measure_word(&format!("w{i}"), 40, None, 400);
    }
    let held = measure_cache_len();
    assert!(
        held <= MAX_MEASURE_CACHE_ENTRIES,
        "the cache holds {held} entries after {PROBES} distinct words — past its \
         {MAX_MEASURE_CACHE_ENTRIES} cap, so a long free-text service would grow it forever"
    );
    // Eviction must never be allowed to answer from a wrong or stale slot: whether a word
    // survived or was evicted and re-shaped, it reports the uncached truth.
    for i in [0, PROBES / 2, PROBES - 1] {
        let word = format!("w{i}");
        assert_eq!(
            measure_word(&word, 40, None, 400),
            selahcue_engine::raster::measure_line_width(&word, 40, None, 400),
            "{word} reported a width no fresh shaping would produce"
        );
    }
    assert!(
        measure_cache_len() <= MAX_MEASURE_CACHE_ENTRIES,
        "re-measuring after eviction must respect the bound too"
    );
}

#[test]
fn a_giant_token_is_measured_but_never_stored() {
    reset_measure_cache();
    // A space-less paste is ONE token to `split_whitespace`, so the auto-fit measures it
    // whole. Capping entries alone would not bound the memo's heap against a run of these
    // — the key bytes would. The width itself must still be the real one.
    let giant = "x".repeat(MAX_MEASURE_CACHE_TEXT_BYTES + 1);
    assert_eq!(
        measure_word(&giant, 40, None, 400),
        selahcue_engine::raster::measure_line_width(&giant, 40, None, 400),
    );
    assert_eq!(
        measure_cache_len(),
        0,
        "an over-cap token parked its bytes in the memo — entry count alone does not \
         bound the heap, so {MAX_MEASURE_CACHE_ENTRIES} entries could hold any amount"
    );

    // The cap is the boundary, not a vague ceiling: a token AT it is still worth keeping.
    let at_cap = "y".repeat(MAX_MEASURE_CACHE_TEXT_BYTES);
    let _ = measure_word(&at_cap, 40, None, 400);
    assert_eq!(
        measure_cache_len(),
        1,
        "a token at the cap must still be memoized"
    );
}

/// A worship stage/confidence frame with the countdown showing `remaining` seconds — the
/// exact shape `StageDisplay::update` composes once a second while a timer runs.
fn stage_frame(remaining: u32) -> Frame {
    stage_frame_at(remaining, 1280, 720)
}

/// The same stage at an arbitrary output size — every region scales, so the SAME words are
/// shaped at different cells.
fn stage_frame_at(remaining: u32, width: u32, height: u32) -> Frame {
    let timer = TimerView {
        elapsed_secs: 300 - remaining,
        remaining_secs: Some(remaining),
        time_up: false,
        warn: false,
        progress: f64::from(remaining) / 300.0,
    };
    let current = Slide::new(
        "Amazing Grace",
        [
            "Amazing grace how sweet the sound",
            "That saved a wretch like me",
        ],
    );
    let next = Slide::new(
        "Amazing Grace",
        [
            "I once was lost but now am found",
            "Was blind but now I see",
        ],
    );
    compose_stage(
        Some(&current),
        Some(&next),
        Some(&timer),
        StageTemplate::Worship,
        None,
        &StageContext::default(),
        &StageTheme::default(),
        width,
        height,
    )
}

#[test]
fn recomposing_an_unchanged_stage_shapes_no_text_at_all() {
    reset_measure_cache();
    let first = stage_frame(120);
    let cold = measure_cache_stats();
    assert!(
        cold.misses > 0,
        "compose never reached the shared memo — its measurements are still thrown \
         away at the end of the call"
    );

    let second = stage_frame(120);
    let warm = measure_cache_stats();
    assert_eq!(
        second, first,
        "the same input must compose to the same frame"
    );
    assert_eq!(
        warm.misses - cold.misses,
        0,
        "an identical recompose re-shaped {} runs of text",
        warm.misses - cold.misses
    );
    assert!(
        warm.hits > cold.hits,
        "no measurement was served from the memo on the second compose"
    );
}

#[test]
fn a_countdown_tick_reshapes_only_the_digits_that_changed() {
    // The reported burn: `LiveController::tick` re-composes the confidence monitor on every
    // whole second so the countdown stays current, and the whole stage layout was re-shaped
    // to change four digits.
    reset_measure_cache();
    let _ = stage_frame(120);
    let cold = measure_cache_stats();
    let _ = stage_frame(119); // one second later — only the clock digits differ
    let ticked = measure_cache_stats();

    let reshaped = ticked.misses - cold.misses;
    assert!(
        reshaped * 4 < cold.misses,
        "a one-second tick re-shaped {reshaped} runs of text against {} for the cold \
         compose — the recompose is still paying for the whole layout",
        cold.misses
    );
}

/// The verse the audience-path tests lay out — one long paragraph the auto-fit must
/// word-wrap, so both the line breaks and the chosen cell are decided by measured widths.
const VERSE: &str = "For I am persuaded that neither death, nor life, nor angels, nor \
     principalities, nor things present, nor things to come, nor powers, nor height, nor \
     depth, nor any other created thing will be able to separate us from the love of God \
     which is in Christ Jesus our Lord.";

/// One real token of [`VERSE`] — the key controls below stand in for a measurement the
/// auto-fit genuinely makes rather than an invented one.
const CONTROL_WORD: &str = "principalities,";

/// A cell far above any this frame's auto-fit will choose, and one well below it. Nothing
/// about the pair is magic: the controls need two sizes whose shaped widths differ, and
/// they assert that they do instead of assuming it.
const SEED_CELL: u32 = 300;
const PROBE_CELL: u32 = 60;

/// A themed audience frame carrying [`VERSE`].
fn verse_frame(theme: &Theme, width: u32, height: u32) -> Frame {
    compose_slide(
        &Slide::new("Romans 8:38-39 (WEB)", [VERSE]),
        theme,
        width,
        height,
    )
}

#[test]
fn a_lookup_at_a_second_cell_is_never_answered_with_the_first_cells_width() {
    // THE BAR FOR THIS TEST: it must fail if the control it names — the `cell` inside
    // `measure::Key` — is removed. Mutation-checked: it does, on the very first assertion.
    //
    // Why the cell needs a DIRECT control and not only the warm-vs-cold frame differential
    // below: the auto-fit binary-searches the cell and re-measures every word at each
    // probe, so a cell-blind key poisons even a COLD compose from its own first probe
    // onwards. The defect corrupts both sides of a differential equally, and a differential
    // can only see what corrupts one of them. The one reference a cell-blind key cannot
    // corrupt is a memo-free shaping, which is what this compares against.
    let theme = Theme::dark();
    let (font, weight) = (theme.font, theme.weight);
    assert!(
        VERSE.split_whitespace().any(|w| w == CONTROL_WORD),
        "{CONTROL_WORD} is no longer one of the verse's words, so these controls have \
         stopped standing in for a measurement the layout actually makes"
    );

    reset_measure_cache();
    let big = measure_word(CONTROL_WORD, SEED_CELL, font.as_ref(), weight);
    let small = measure_word(CONTROL_WORD, PROBE_CELL, font.as_ref(), weight);

    // (1) THE HOSTILE CASE IS REFUSED — a memo already holding this word at SEED_CELL must
    // not answer a PROBE_CELL lookup with it.
    assert_ne!(
        big, small,
        "a {PROBE_CELL}px lookup was answered with the {SEED_CELL}px width — the key is \
         blind to the cell, so every auto-fit probe after the first is handed the first \
         probe's widths and the verse wraps at the wrong size"
    );
    // Not merely "different": each must be exactly the width a memo-free shaping produces.
    assert_eq!(
        big,
        measure_line_width(CONTROL_WORD, SEED_CELL, font.as_ref(), weight),
        "the memo's {SEED_CELL}px width is not the one a fresh shaping produces"
    );
    assert_eq!(
        small,
        measure_line_width(CONTROL_WORD, PROBE_CELL, font.as_ref(), weight),
        "the memo's {PROBE_CELL}px width is not the one a fresh shaping produces"
    );

    // (2) POSITIVE CONTROL — the benign case genuinely RAN. Every assertion above would
    // hold just as well if `measure_word` had stopped consulting the memo at all (an early
    // `return measure_line_width(..)` bypass, a key that matches nothing, a reset on every
    // call): no entry would ever be served, every width would be correct, and (1) would be
    // green while guarding nothing. This half is what makes (1) mean something.
    let held = measure_cache_len();
    assert_eq!(
        held, 2,
        "one word at two cells must occupy TWO entries; {held} means the cells share a slot"
    );
    assert_eq!(
        measure_cache_hits_for(CONTROL_WORD, SEED_CELL, font.as_ref(), weight),
        Some(0),
        "the {SEED_CELL}px entry SERVED a lookup, and the only lookup since it was stored \
         asked for {PROBE_CELL}px — the cell is not part of the key"
    );
    assert_eq!(
        measure_word(CONTROL_WORD, SEED_CELL, font.as_ref(), weight),
        big,
        "the memo returned a width it never stored"
    );
    assert_eq!(
        measure_cache_hits_for(CONTROL_WORD, SEED_CELL, font.as_ref(), weight),
        Some(1),
        "a repeat lookup at the SAME cell was NOT served from the memo — the memo is inert \
         here, so the refusal asserted above proves nothing about the key"
    );
}

#[test]
fn a_memo_warmed_at_the_wrong_cell_still_wraps_the_verse_identically() {
    // THE BAR FOR THIS TEST: it must fail if the control it names — the `cell` inside
    // `measure::Key` — is removed. It now does, twice; it previously did not, and the two
    // reasons are worth keeping written down:
    //
    //   * The FRAME differential at the end cannot carry the claim. A cell-blind key
    //     corrupts the cold side too (the auto-fit's own binary search re-measures every
    //     word at each probe, so the first probe poisons the rest), so both frames come
    //     out equally wrong and equal to each other.
    //   * The old positive control, `consulted > 0`, was satisfied by the SEED LOOP. The
    //     verse repeats "nor" and "things", so 13 seeded entries already had hits before
    //     the compose ran; the compose then made 72 memo reads and added exactly zero of
    //     them to a seeded key. Measured, not guessed.
    //
    // What carries it now is the per-entry hit counter: the compose searches cells around
    // the design size and never asks for SEED_CELL, so if a SEED_CELL counter MOVES across
    // the compose, its lookups were answered from the wrong cell. That is the leak itself,
    // observed directly rather than through a layout that hides it.
    let theme = Theme::dark();
    let (font, weight) = (theme.font, theme.weight);
    let cold = std::thread::spawn(|| verse_frame(&Theme::dark(), 960, 540))
        .join()
        .unwrap();

    // Which cells the auto-fit really probes — read back from the memo rather than assumed,
    // since a cold compose leaves exactly its own probes resident. (Here: 1, 21, 32, 37,
    // 40, 41, 42 — the binary search over 1..=42, the body region's design cell.)
    reset_measure_cache();
    let _ = verse_frame(&theme, 960, 540);
    let probed: Vec<u32> = (1..=SEED_CELL)
        .filter(|c| measure_cache_hits_for(CONTROL_WORD, *c, font.as_ref(), weight).is_some())
        .collect();
    assert!(
        probed.len() > 1,
        "the auto-fit measured {CONTROL_WORD} at only {probed:?} — it no longer searches \
         over several cells, so a cell-blind key could not mis-wrap anything and the \
         hostile seeding below has stopped being hostile"
    );
    assert!(
        !probed.contains(&SEED_CELL),
        "the memo answers a {SEED_CELL}px query after a compose whose search never went \
         near that size ({} cells resident) — either the layout changed and {SEED_CELL} is \
         no longer the WRONG cell, or the key has stopped distinguishing cells at all",
        probed.len()
    );

    reset_measure_cache();
    // Seed the verse's OWN words, in the theme's OWN face and weight, at a cell far larger
    // than any this frame will choose — and seed them FIRST, so a key blind to the cell
    // would serve these oversized widths to every probe of the auto-fit's binary search.
    // (An earlier version warmed a face the compose never asks for, so a broken key was
    // never consulted at all.)
    for word in VERSE.split_whitespace() {
        measure_word(word, SEED_CELL, font.as_ref(), weight);
    }
    // Derived, never a magic number: the memo holds ONE entry per DISTINCT word, and the
    // verse repeats "nor" and "things". An exact count is strictly stronger than a floor
    // and cannot rot — a hand-picked floor is precisely how the earlier `> 40` stopped
    // holding without anyone noticing.
    let mut distinct: Vec<&str> = VERSE.split_whitespace().collect();
    distinct.sort_unstable();
    distinct.dedup();
    assert_eq!(
        measure_cache_len(),
        distinct.len(),
        "the seed must populate the memo with this frame's own distinct words"
    );

    let seed_cell_hits = || -> Vec<Option<u64>> {
        distinct
            .iter()
            .map(|w| measure_cache_hits_for(w, SEED_CELL, font.as_ref(), weight))
            .collect()
    };
    // The baseline the compose must not move. It is NOT all zeroes — the seed loop hit its
    // own entries on the verse's repeated words, which is exactly what made the bare
    // `consulted > 0` check vacuous. Taking the baseline turns the same observable into one
    // only the compose can move.
    let before = seed_cell_hits();
    let hits_before = measure_cache_stats().hits;

    let warm = verse_frame(&theme, 960, 540);

    // POSITIVE CONTROL: the compose genuinely READ the memo. Without it, "no seeded entry
    // was served" would be satisfied just as well by a memo nothing consults — green, and
    // guarding nothing.
    let served = measure_cache_stats().hits - hits_before;
    assert!(
        served > 0,
        "the compose never read the memo at all, so proving it read no {SEED_CELL}px entry \
         says nothing about the key"
    );
    // THE GUARD: none of those {served} memo reads may have been answered from a SEED_CELL
    // entry, because the compose never asks for that cell.
    assert_eq!(
        seed_cell_hits(),
        before,
        "the compose was SERVED a width the memo holds for {SEED_CELL}px — of its {served} \
         memo reads, at least one landed on a cell it never asked for"
    );
    assert_eq!(
        warm, cold,
        "a memo holding these words at another cell changed how the verse wrapped"
    );
}

#[test]
fn themes_differing_only_in_typography_never_share_a_measurement() {
    // THE BAR FOR THIS TEST: it must fail if either control it names — the `font` or the
    // `weight` inside `measure::Key` — is removed. Mutation-checked for both. Note WHICH
    // half catches which, because it is not the obvious one; see the controls below.
    //
    // Same verse, same geometry — only the face and the weight differ. If the key were
    // blind to either, the second theme would be laid out with the first theme's widths.
    let plain = Theme::dark();
    let bold = Theme {
        weight: 800,
        ..Theme::dark()
    };
    let serif = Theme {
        font: FontName::new("Times New Roman"),
        ..Theme::dark()
    };

    // Cold baselines: a fresh thread gets its own, empty thread-local memo.
    let cold = |t: Theme| {
        std::thread::spawn(move || verse_frame(&t, 960, 540))
            .join()
            .unwrap()
    };
    let (cold_plain, cold_bold, cold_serif) =
        (cold(plain.clone()), cold(bold.clone()), cold(serif.clone()));

    // What the FRAME comparisons in this test can and cannot see, measured rather than
    // assumed. `widths_move` asks whether a typography actually changes a shaped width,
    // which is the only way it can change a wrap — and therefore the only way a key blind
    // to it can change a frame.
    let widths_move = |t: &Theme| {
        VERSE.split_whitespace().any(|w| {
            measure_line_width(w, 40, t.font.as_ref(), t.weight)
                != measure_line_width(w, 40, plain.font.as_ref(), plain.weight)
        })
    };
    assert!(
        widths_move(&serif),
        "the serif family shapes identically to the default on this host, so the serif \
         frame comparisons below cannot tell a font-blind key from a correct one"
    );
    // The bundled face has ONE weight, so 800 is a synthetic embolden that moves no
    // advance: `measure_line_width` returns the same width at 400 and at 800 for every
    // word of the verse. A weight-blind key therefore cannot change this layout at all,
    // and NO frame comparison here can catch one — mutation-checked, it does not. The
    // control that used to sit here, `assert_ne!(cold_plain, cold_bold)`, read as though
    // it ruled that out. It does not: the two frames differ in the `Layer::Text` style
    // field, which carries the weight whatever the widths do. Asserting the limitation
    // keeps the claim honest and makes the day it stops being true a red test rather than
    // a stale comment.
    assert!(
        !widths_move(&bold),
        "weight 800 now MOVES the shaped widths, so the bold frames below could carry the \
         weight contract after all — strengthen them and drop this assertion"
    );
    assert_ne!(
        cold_plain, cold_bold,
        "the bold theme's weight never reached the composed layer at all"
    );

    // PORTABLE CONTROL — this is the half that goes red on a font- or weight-blind key.
    // It compares KEYS, not frames, so it holds whether or not a typography moves a width
    // on this host: three typographies of one word must occupy three entries, and none of
    // the three lookups may have been answered from another's.
    reset_measure_cache();
    for t in [&plain, &bold, &serif] {
        let _ = measure_word(CONTROL_WORD, 40, t.font.as_ref(), t.weight);
    }
    let held = measure_cache_len();
    assert_eq!(
        held, 3,
        "one word in three typographies must occupy THREE entries; {held} means two of \
         them share a slot and a theme is being handed another's width"
    );
    for t in [&plain, &bold, &serif] {
        assert_eq!(
            measure_cache_hits_for(CONTROL_WORD, 40, t.font.as_ref(), t.weight),
            Some(0),
            "the entry for weight {} face {:?} SERVED another typography's lookup",
            t.weight,
            t.font
        );
    }
    // ...and the memo is not simply inert here: asking again IS served from it.
    let _ = measure_word(CONTROL_WORD, 40, bold.font.as_ref(), bold.weight);
    assert_eq!(
        measure_cache_hits_for(CONTROL_WORD, 40, bold.font.as_ref(), bold.weight),
        Some(1),
        "a repeat lookup was not served from the memo — the memo is inert here, so the \
         three-entry claim above says nothing about the key"
    );

    reset_measure_cache();
    // Interleave, so each theme composes with the OTHER themes' measurements resident.
    let warm_plain = verse_frame(&plain, 960, 540);
    let hits_before_bold = measure_cache_stats().hits;
    let warm_bold = verse_frame(&bold, 960, 540);
    let bold_reads = measure_cache_stats().hits - hits_before_bold;
    let warm_serif = verse_frame(&serif, 960, 540);
    let warm_plain_again = verse_frame(&plain, 960, 540);

    // Prove the memo was actually in play for the bold pass — a delta taken across that
    // pass alone, so no other pass's reads can stand in for it. Without this the four
    // equalities below would hold just as well with the memo switched off
    // (`compose(x) == compose(x)` for any deterministic composer) and would guard nothing.
    assert!(
        bold_reads > 0,
        "no measurement was served from the memo during the bold pass — the contract was \
         never exercised"
    );

    assert_eq!(
        warm_bold, cold_bold,
        "the bold theme was served the plain theme's widths"
    );
    assert_eq!(
        warm_serif, cold_serif,
        "the serif theme was served another face's widths"
    );
    assert_eq!(
        warm_plain, cold_plain,
        "the plain theme's own layout drifted"
    );
    assert_eq!(
        warm_plain_again, cold_plain,
        "composing the plain theme after two others changed its layout"
    );
}
