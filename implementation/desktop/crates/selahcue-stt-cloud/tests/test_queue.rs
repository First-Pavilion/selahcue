//! Bounded-memory tests for the inbound segment queue.
//!
//! The bar in this repository is a property of the **test**, not of the suite: each of these
//! must fail if the control it names is removed. Every one of them therefore
//!
//! - asserts on a **per-entity** accessor (`retains_text`, `len`, `retained_bytes`) rather
//!   than on a proxy;
//! - asserts the control was **exercised** before asserting the contract, in a message that
//!   names what went untested if it was not;
//! - pins its premise at **compile time**, so changing a cap breaks the build here instead of
//!   quietly making the test vacuous;
//! - asserts both the queue's **own bound verdict** (`is_within_bounds`, the same expression
//!   the eviction loop consumes) and the **entities** independently. Either alone is
//!   degenerate: neutering the predicate satisfies the first, and reading a copy of the
//!   predicate satisfies the second. Together they are not.

#![allow(clippy::unwrap_used)]
// `%` rather than `is_multiple_of`: this assertion is evaluated at compile time inside a
// `const _`, and the point of it is legible arithmetic about where a byte cap falls.
#![allow(clippy::manual_is_multiple_of)]

use selahcue_core::transcript::{ProviderSegment, TranscriptProvider, MAX_SEGMENT_TEXT_LEN};
use selahcue_stt_cloud::{
    CloudTranscriptProvider, SegmentQueue, MAX_QUEUED_SEGMENTS, MAX_QUEUED_SEGMENT_BYTES,
};

fn seg(text: &str) -> ProviderSegment {
    ProviderSegment::final_text(text, 0, 500)
}

#[test]
fn an_entry_count_flood_stays_within_the_entry_bound_and_drops_the_oldest() {
    // The premise, pinned here as well as beside the constant: the flood below is four times
    // the cap. If the cap ever grew past this, the flood would stop being a flood and this
    // test would stop testing anything.
    const _: () = assert!(
        MAX_QUEUED_SEGMENTS <= 4096,
        "the flood in this test is 4x the cap; past this it stops being a flood in reasonable \
         time and the entry bound goes untested"
    );

    let queue = SegmentQueue::new();
    let oldest = "OLDEST-this-one-must-be-evicted";
    let newest = "NEWEST-this-one-must-survive";

    queue.push(seg(oldest));
    for i in 0..(MAX_QUEUED_SEGMENTS * 4) {
        queue.push(seg(&format!("filler-{i}")));
    }
    queue.push(seg(newest));

    // Exercised before contract. A bound that never bit is a bound that was not tested.
    assert!(
        queue.dropped_for_bound() > 0,
        "the queue evicted nothing, so MAX_QUEUED_SEGMENTS never bound anything and every \
         assertion below this line is vacuous"
    );
    assert_eq!(
        queue.admitted(),
        (MAX_QUEUED_SEGMENTS * 4 + 2) as u64,
        "the queue did not admit every segment this test pushed, so the flood it is supposed \
         to be surviving did not happen"
    );

    // The entity, not a proxy.
    assert_eq!(
        queue.len(),
        MAX_QUEUED_SEGMENTS,
        "the queue holds {} segments against a cap of {MAX_QUEUED_SEGMENTS} — a three-hour \
         service on a stalled poll would grow without limit",
        queue.len()
    );
    // The queue's own verdict — the same expression its eviction loop consumes, so a control
    // that reads a re-assembled copy of the predicate cannot pass here.
    assert!(
        queue.is_within_bounds(),
        "the queue reports itself out of bounds after eviction"
    );

    // The drop policy, by name rather than by count.
    assert!(
        !queue.retains_text(oldest),
        "the oldest segment survived a 4x flood — the drop policy is not oldest-first"
    );
    assert!(
        queue.retains_text(newest),
        "the newest segment was evicted — a live transcript would show stale words and drop \
         the ones just spoken"
    );
}

#[test]
fn a_byte_flood_stays_within_the_byte_bound_before_the_entry_cap_is_reached() {
    // The premise: maximum-length segments exhaust the BYTE budget while the entry count is
    // still well inside its own cap, so this test distinguishes the two bounds rather than
    // re-testing the entry bound with bigger strings.
    const SEGMENTS_TO_FILL_BYTES: usize = MAX_QUEUED_SEGMENT_BYTES / MAX_SEGMENT_TEXT_LEN + 2;
    const _: () = assert!(
        SEGMENTS_TO_FILL_BYTES < MAX_QUEUED_SEGMENTS,
        "filling the byte budget also reaches the entry cap, so this test cannot tell the two \
         bounds apart and the byte bound is untested"
    );

    let queue = SegmentQueue::new();
    let oldest = format!("{}OLDEST", "A".repeat(MAX_SEGMENT_TEXT_LEN - 6));

    queue.push(seg(&oldest));
    for i in 0..SEGMENTS_TO_FILL_BYTES {
        queue.push(seg(&format!(
            "{}{i:06}",
            "B".repeat(MAX_SEGMENT_TEXT_LEN - 6)
        )));
    }

    assert!(
        queue.dropped_for_bound() > 0,
        "nothing was evicted, so MAX_QUEUED_SEGMENT_BYTES never bound anything and every \
         assertion below this line is vacuous"
    );
    // The premise again, this time against what actually happened rather than what was
    // computed: if the entry cap was reached, the byte bound is not what did the work here.
    assert!(
        queue.len() < MAX_QUEUED_SEGMENTS,
        "the entry cap was reached ({} of {MAX_QUEUED_SEGMENTS}), so this test is measuring \
         the entry bound, not the byte bound",
        queue.len()
    );

    assert!(
        queue.retained_bytes() <= MAX_QUEUED_SEGMENT_BYTES,
        "the queue retains {} bytes against a budget of {MAX_QUEUED_SEGMENT_BYTES}",
        queue.retained_bytes()
    );
    assert!(
        queue.is_within_bounds(),
        "the queue reports itself out of bounds after eviction"
    );
    assert!(
        !queue.retains_text(&oldest),
        "the oldest segment survived a byte flood — the byte budget is not evicting"
    );
}

#[test]
fn a_benign_segment_flows_through_the_queue_and_out_of_poll() {
    // The positive control. Without it, "bounded" is indistinguishable from "broken": a queue
    // that silently discarded everything would pass both bound tests above.
    let queue = SegmentQueue::new();
    let text = "Turn with me to John chapter three.";

    queue.push(seg(text));

    assert!(
        queue.retains_text(text),
        "a single benign segment did not reach the queue at all — the bound tests above \
         cannot distinguish a working queue from a dead one without this"
    );
    assert_eq!(
        queue.dropped_for_bound(),
        0,
        "a single benign segment triggered an eviction"
    );

    let mut provider = CloudTranscriptProvider::with_label(queue.clone(), "deepgram-test");
    let drained = provider.poll();

    assert_eq!(drained.len(), 1, "poll did not return the queued segment");
    assert_eq!(drained[0].text, text);
    assert!(queue.is_empty(), "poll did not empty the queue");
    assert_eq!(
        queue.retained_bytes(),
        0,
        "draining left the byte accounting behind; over a service the byte budget would fill \
         with segments that are no longer there and start evicting live text"
    );
}

#[test]
fn a_flood_of_blank_interim_results_is_refused_and_cannot_evict_real_text() {
    // Deepgram emits empty interim transcripts several times a second during silence. If they
    // were queued, a quiet passage would evict the sermon.
    let queue = SegmentQueue::new();
    let real = "And Jesus said unto them,";

    queue.push(seg(real));
    for _ in 0..(MAX_QUEUED_SEGMENTS * 4) {
        queue.push(seg(""));
        queue.push(seg("   \t\n"));
    }

    assert!(
        queue.rejected_empty() > 0,
        "no blank segment was refused, so the blank-transcript guard went unexercised"
    );
    assert_eq!(
        queue.len(),
        1,
        "blank interim results were queued; a silent passage now costs real transcript text"
    );
    assert!(
        queue.retains_text(real),
        "a flood of blank interim results evicted real transcript text"
    );
    assert_eq!(
        queue.dropped_for_bound(),
        0,
        "blank segments caused evictions, which means they were admitted first"
    );
}

#[test]
fn an_over_length_segment_is_truncated_rather_than_refused() {
    let queue = SegmentQueue::new();
    let long = "x".repeat(MAX_SEGMENT_TEXT_LEN * 3);

    queue.push(seg(&long));

    assert_eq!(
        queue.len(),
        1,
        "an over-length segment was refused outright; the operator loses a whole sentence \
         rather than its tail"
    );
    assert_eq!(
        queue.retained_bytes(),
        MAX_SEGMENT_TEXT_LEN,
        "an over-length segment was stored untruncated, so one segment can own the byte budget"
    );
    assert!(queue.is_within_bounds());
}

#[test]
fn truncation_never_splits_a_codepoint() {
    // A three-byte codepoint, so the cap (2000) lands mid-character.
    const _: () = assert!(
        MAX_SEGMENT_TEXT_LEN % 3 != 0,
        "this test needs the cap to fall mid-codepoint for a 3-byte character; with a \
         multiple of 3 it would prove nothing about boundary handling"
    );

    let queue = SegmentQueue::new();
    queue.push(seg(&"…".repeat(MAX_SEGMENT_TEXT_LEN)));

    let out = queue.drain();
    assert_eq!(out.len(), 1);
    assert!(
        out[0].text.chars().all(|c| c == '…'),
        "truncation split a codepoint"
    );
    assert!(out[0].text.len() <= MAX_SEGMENT_TEXT_LEN);
    assert!(
        !out[0].text.is_empty(),
        "truncation removed everything — the positive half of the boundary contract"
    );
}

#[test]
fn clones_share_one_queue() {
    // The transport pushes through a clone while the provider drains through another. If
    // clones did not share, every bound above would be tested on a queue nothing else uses.
    let queue = SegmentQueue::new();
    let other = queue.clone();
    other.push(seg("shared"));
    assert!(
        queue.retains_text("shared"),
        "clones do not share one queue, so the socket's pushes would never reach poll()"
    );
}
