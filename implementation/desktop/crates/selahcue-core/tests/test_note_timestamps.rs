//! `link_timestamps` — timestamp-linked note items (86akgqdw0; FR-124).
//!
//! Linking strategy: **post-hoc matched, never model-estimated.** `NoteRequest::transcript`
//! is a flattened `String` by construction (FR-132's own egress choke point) — the model
//! never sees segment boundaries, so this function derives a timestamp by matching a note
//! item's own text against the transcript's real segments, the same "compute independently,
//! join by value" shape `verify_scriptures`/`ScriptureVerdict` already established for
//! scripture (86akby820). These tests guard the algorithm: matching, the monotonic forward
//! cursor, the chapter-markers positional fallback, outline points' stricter (match-only, no
//! fallback) rule, bounding, and adversarial/malformed segment data never crashing or
//! producing a nonsensical (out-of-plausible-range) offset.

use selahcue_core::providers::{
    link_timestamps, NoteDraft, NotePoint, NoteSection, NoteTimestamp, CHAPTER_MARKERS_HEADING,
    MAX_LINK_ITEMS, MAX_LINK_SEGMENTS, MAX_PLAUSIBLE_OFFSET_MS, OUTLINE_HEADING,
};
use selahcue_core::transcript::TranscriptSegment;

fn seg(id: u64, start_ms: u64, end_ms: u64, text: &str) -> TranscriptSegment {
    TranscriptSegment {
        id,
        start_ms,
        end_ms,
        text: text.to_string(),
    }
}

fn ts(heading: &str, text: &str, offset_ms: u64) -> NoteTimestamp {
    NoteTimestamp {
        heading: heading.to_string(),
        text: text.to_string(),
        offset_ms,
    }
}

// ===========================================================================
// 1 · Happy path — a real textual match wins
// ===========================================================================

#[test]
fn a_chapter_marker_matches_the_segment_that_shares_its_vocabulary() {
    let segments = vec![
        seg(
            0,
            0,
            4_000,
            "Good morning church, let us open in prayer this morning.",
        ),
        seg(
            1,
            4_000,
            30_000,
            "Turn with me to the story of the prodigal son in Luke fifteen.",
        ),
        seg(
            2,
            30_000,
            34_000,
            "Let's close in a word of prayer together.",
        ),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string(), "The prodigal son".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out,
        vec![
            ts(CHAPTER_MARKERS_HEADING, "Opening prayer", 0),
            ts(CHAPTER_MARKERS_HEADING, "The prodigal son", 4_000),
        ]
    );
}

#[test]
fn an_outline_point_matches_the_same_way_a_chapter_marker_does() {
    let segments = vec![
        seg(
            0,
            0,
            5_000,
            "The first point is that faith requires action, not just belief.",
        ),
        seg(
            1,
            5_000,
            9_000,
            "The second point is that grace covers every failure.",
        ),
    ];
    let sections = vec![NoteSection::outline(
        OUTLINE_HEADING,
        vec![
            NotePoint {
                text: "Faith requires action".to_string(),
                sub_points: vec![],
            },
            NotePoint {
                text: "Grace covers every failure".to_string(),
                sub_points: vec![],
            },
        ],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out,
        vec![
            ts(OUTLINE_HEADING, "Faith requires action", 0),
            ts(OUTLINE_HEADING, "Grace covers every failure", 5_000),
        ]
    );
}

#[test]
fn only_chapter_markers_and_outline_points_are_considered_other_sections_are_ignored() {
    let segments = vec![seg(
        0,
        0,
        1_000,
        "prayer points about healing and provision",
    )];
    let sections = vec![NoteSection::flat(
        "Prayer points",
        vec!["healing and provision".to_string()],
    )];
    assert!(
        link_timestamps(&sections, &segments).is_empty(),
        "a section that is neither the chapter-markers heading nor the outline heading must \
         never receive a timestamp — this ticket's scope is chapter markers and outline points \
         only"
    );
}

#[test]
fn a_draft_with_chapter_markers_off_carries_no_timestamp_data() {
    // AC4: "A draft generated with chapter markers off carries no timestamp data" — the
    // section simply never exists in `sections`, so there is nothing to match against.
    let sections = vec![NoteSection::flat(
        "Illustrations",
        vec!["a lantern".to_string()],
    )];
    let segments = vec![seg(0, 0, 1_000, "a lantern in the dark")];
    assert!(link_timestamps(&sections, &segments).is_empty());
}

// ===========================================================================
// 2 · Monotonic ordering — later markers never bind to an earlier moment
// ===========================================================================

#[test]
fn markers_are_matched_in_a_forward_only_pass_never_binding_backward() {
    // Both markers share the word "prayer" with BOTH prayer-shaped segments (0 and 3). A
    // naive "best score anywhere" search could bind marker 2 ("Closing prayer") to segment
    // 0, which occurs BEFORE marker 1's own match — nonsensical for a chronological chapter
    // list. The monotonic cursor must instead walk forward, giving marker 2 segment 3.
    let segments = vec![
        seg(0, 0, 1_000, "prayer prayer prayer"),
        seg(
            1,
            1_000,
            20_000,
            "the sermon body has an entirely different topic altogether",
        ),
        seg(
            2,
            20_000,
            21_000,
            "still sermon body, still no matching vocabulary",
        ),
        seg(3, 21_000, 22_000, "prayer prayer prayer"),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string(), "Closing prayer".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out[0].offset_ms, 0);
    assert_eq!(
        out[1].offset_ms, 21_000,
        "the second marker must never bind to an earlier segment than the first, even though \
         segment 0 scores identically well against BOTH marker texts"
    );
}

#[test]
fn an_unmatched_marker_between_two_matched_ones_lands_strictly_between_them_never_before_the_earlier_one(
) {
    // Cody's code-review finding on PR #51: a prior revision of the positional fallback
    // interpolated an unmatched marker by its ordinal position among only the OTHER
    // unmatched markers, ignoring where already-matched neighbours actually landed. Traced
    // example: markers [M1@5000 match, M2 no match, M3@10000 match, M4 no match] over a
    // 0..20000ms transcript used to yield M2=0 — landing chronologically BEFORE M1's own
    // 5000, breaking the monotonic, sermon-order guarantee this module's own "Matching"
    // doc section promises, and unusable as a strictly-ordered exportable chapter list
    // (YouTube's own chapter-marker convention requires strictly increasing timestamps).
    let segments = vec![
        seg(0, 0, 1_000, "welcome and greetings this morning"),
        seg(1, 5_000, 6_000, "the story of the prodigal son begins"),
        seg(2, 10_000, 11_000, "now we turn to grace and mercy"),
        seg(3, 20_000, 21_000, "closing remarks and benediction"),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec![
            "The prodigal son".to_string(),        // M1: matches segment 1 @ 5_000
            "Xylophone zephyr quokka".to_string(), // M2: matches nothing
            "Grace and mercy".to_string(),         // M3: matches segment 2 @ 10_000
            "Bumblebee marmalade jamboree".to_string(), // M4: matches nothing
        ],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out.len(), 4, "every marker must still carry SOME timestamp");
    assert_eq!(
        out[0].offset_ms, 5_000,
        "M1's real match must be unaffected"
    );
    assert_eq!(
        out[2].offset_ms, 10_000,
        "M3's real match must be unaffected"
    );
    assert!(
        out[1].offset_ms > out[0].offset_ms,
        "M2 (unmatched) must land AFTER M1's real match (5_000), got {}",
        out[1].offset_ms
    );
    assert!(
        out[1].offset_ms < out[2].offset_ms,
        "M2 (unmatched) must land BEFORE M3's real match (10_000), got {}",
        out[1].offset_ms
    );
    assert!(
        out[3].offset_ms > out[2].offset_ms,
        "M4 (unmatched, trailing) must land AFTER M3's real match (10_000), got {}",
        out[3].offset_ms
    );
    // The whole list — matched and fallback-derived alike — must be non-decreasing in item
    // order, not merely each subset non-decreasing on its own.
    for pair in out.windows(2) {
        assert!(
            pair[0].offset_ms <= pair[1].offset_ms,
            "the full chapter-marker list must be monotonically non-decreasing, got {out:?}"
        );
    }
}

// ===========================================================================
// 3 · Positional fallback — chapter markers ALWAYS get an offset
// ===========================================================================

#[test]
fn a_chapter_marker_with_zero_vocabulary_overlap_still_gets_an_interpolated_offset() {
    // AC1 says "each marker carries a timestamp" — unconditionally. A model-authored label
    // ("The Prodigal Son Returns") often shares no vocabulary with the actual sentence
    // spoken at that moment, so this must not simply come back empty.
    let segments = vec![
        seg(0, 0, 1_000, "xyzzy plugh qux"),
        seg(1, 1_000, 2_000, "wibble wobble flob"),
        seg(2, 2_000, 3_000, "corge grault garply"),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["The Prodigal Son Returns".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out.len(),
        1,
        "a marker must never come back with NO timestamp at all"
    );
    assert!(
        out[0].offset_ms <= 3_000,
        "the fallback offset must stay within the transcript's own real span, got {}",
        out[0].offset_ms
    );
}

#[test]
fn multiple_unmatched_markers_get_distinct_evenly_spaced_fallback_offsets_in_order() {
    let segments = vec![
        seg(0, 0, 10_000, "alpha beta gamma"),
        seg(1, 10_000, 20_000, "delta epsilon zeta"),
        seg(2, 90_000, 100_000, "eta theta iota"),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec![
            "First unmatched".to_string(),
            "Second unmatched".to_string(),
            "Third unmatched".to_string(),
        ],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out.len(), 3);
    assert!(
        out[0].offset_ms < out[1].offset_ms && out[1].offset_ms < out[2].offset_ms,
        "fallback offsets for unmatched markers must preserve their original order: {out:?}"
    );
}

#[test]
fn an_outline_point_with_zero_vocabulary_overlap_gets_no_fallback() {
    // The ticket's own "ideally"/"where feasible" wording for outline points, unlike
    // chapter markers' unconditional "each marker carries a timestamp" — a point with no
    // confident textual match is simply left unlinked, never assigned a guessed position.
    let segments = vec![seg(0, 0, 1_000, "xyzzy plugh qux")];
    let sections = vec![NoteSection::outline(
        OUTLINE_HEADING,
        vec![NotePoint {
            text: "Something entirely unrelated".to_string(),
            sub_points: vec![],
        }],
    )];
    assert!(
        link_timestamps(&sections, &segments).is_empty(),
        "an outline point with no textual match must NOT receive a fallback timestamp"
    );
}

#[test]
fn an_empty_transcript_yields_no_timestamps_at_all_not_a_fabricated_zero() {
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string()],
    )];
    assert!(
        link_timestamps(&sections, &[]).is_empty(),
        "with nothing to derive a timestamp FROM, the honest answer is none at all — never a \
         fabricated 0"
    );
}

// ===========================================================================
// 4 · Adversarial / malformed segment data — never crash, never a nonsensical offset
// ===========================================================================

#[test]
fn a_segment_with_an_absurdly_large_start_ms_is_excluded_from_matching_entirely() {
    // Stands in for a corrupted store row (e.g. a negative-to-u64 wraparound reading a
    // damaged `transcript_segment.start_ms`). Must never win a match, never be clamped into
    // range, and must never crash the linker.
    let segments = vec![
        seg(0, u64::MAX, u64::MAX, "opening prayer this morning"),
        seg(1, 5_000, 9_000, "an entirely unrelated sentence"),
    ];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out.len(), 1);
    assert!(
        out[0].offset_ms <= MAX_PLAUSIBLE_OFFSET_MS,
        "a corrupt segment's absurd start_ms must never reach the wire as a jump target, got {}",
        out[0].offset_ms
    );
}

#[test]
fn every_segment_being_implausible_yields_no_timestamp_never_a_panic() {
    let segments = vec![seg(0, u64::MAX, u64::MAX, "opening prayer this morning")];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string()],
    )];
    assert!(
        link_timestamps(&sections, &segments).is_empty(),
        "with every segment implausible, there is nothing safe to derive a timestamp from"
    );
}

#[test]
fn a_segment_with_end_ms_less_than_start_ms_does_not_panic() {
    // `TranscriptLog::push` clamps this, but a row loaded straight from SQL
    // (`transcript_repo::load`) does not go through that clamp — this function must not
    // assume it.
    let segments = vec![seg(0, 5_000, 1_000, "opening prayer this morning")];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out,
        vec![ts(CHAPTER_MARKERS_HEADING, "Opening prayer", 5_000)]
    );
}

#[test]
fn an_item_of_pure_punctuation_is_skipped_rather_than_matched_by_accident() {
    let segments = vec![seg(0, 0, 1_000, "!!! ??? ...")];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["???".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out.len(),
        1,
        "the ticket still requires SOME timestamp for a chapter marker even when its own \
         text has no significant words — the positional fallback applies"
    );
}

#[test]
fn an_empty_item_text_is_never_assigned_a_timestamp() {
    let segments = vec![seg(0, 0, 1_000, "opening prayer this morning")];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["".to_string(), "Opening prayer".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out, vec![ts(CHAPTER_MARKERS_HEADING, "Opening prayer", 0)]);
}

// ===========================================================================
// 5 · Bounds — independent of any upstream cap, mutation-provable
// ===========================================================================

const _: () = assert!(
    MAX_LINK_SEGMENTS < 50_000,
    "test feeds MAX_LINK_SEGMENTS + 1 segments to prove the scan cap bites; raising this past \
     50_000 makes that test far too slow to run routinely"
);
const _: () = assert!(
    MAX_LINK_ITEMS < 1_000,
    "test feeds MAX_LINK_ITEMS + 1 items to prove the item cap bites"
);

#[test]
fn segments_past_the_scan_bound_are_never_considered() {
    // One segment, right at the end, uniquely matches the marker text. Push it past
    // `MAX_LINK_SEGMENTS` with filler segments ahead of it that share NOTHING with the
    // marker — if the cap did not bite, the unique match would still be found (this
    // function has no reason to reject a real match); the cap's own presence is proven by
    // a SEPARATE, direct assertion on the returned offset never reaching past the bound.
    let mut segments: Vec<TranscriptSegment> = (0..MAX_LINK_SEGMENTS)
        .map(|i| {
            seg(
                i as u64,
                i as u64 * 10,
                i as u64 * 10 + 5,
                "filler filler filler",
            )
        })
        .collect();
    segments.push(seg(
        MAX_LINK_SEGMENTS as u64,
        (MAX_LINK_SEGMENTS as u64) * 10,
        (MAX_LINK_SEGMENTS as u64) * 10 + 5,
        "uniqueneedle opening prayer",
    ));
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["uniqueneedle".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(out.len(), 1);
    assert_ne!(
        out[0].offset_ms,
        (MAX_LINK_SEGMENTS as u64) * 10,
        "the one segment past the scan bound must never be reachable as a match target — the \
         positional fallback (from the filler segments actually scanned) is the honest answer \
         instead"
    );
}

#[test]
fn items_past_the_link_item_bound_are_never_linked() {
    let segments = vec![seg(0, 0, 1_000, "alpha marker text here")];
    let mut items: Vec<String> = (0..MAX_LINK_ITEMS).map(|i| format!("filler {i}")).collect();
    items.push("alpha marker text here".to_string());
    let sections = vec![NoteSection::flat(CHAPTER_MARKERS_HEADING, items)];
    let out = link_timestamps(&sections, &segments);
    assert!(
        !out.iter().any(|t| t.text == "alpha marker text here"),
        "an item past MAX_LINK_ITEMS must never be linked, even though it would otherwise \
         match perfectly"
    );
}

// ===========================================================================
// 6 · Join-by-value semantics — mirrors `ScriptureVerdict`
// ===========================================================================

#[test]
fn a_duplicate_item_text_within_one_section_carries_one_shared_timestamp() {
    let segments = vec![seg(0, 0, 1_000, "opening prayer this morning")];
    let sections = vec![NoteSection::flat(
        CHAPTER_MARKERS_HEADING,
        vec!["Opening prayer".to_string(), "Opening prayer".to_string()],
    )];
    let out = link_timestamps(&sections, &segments);
    assert_eq!(
        out.len(),
        1,
        "a repeated item text must be reported once, matching ScriptureVerdict's own \
         dedup-by-value precedent, not once per occurrence"
    );
}

#[test]
fn draft_default_carries_no_timestamps() {
    assert!(NoteDraft::default().timestamps.is_empty());
}
