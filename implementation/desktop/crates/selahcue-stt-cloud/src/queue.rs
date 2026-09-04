//! The bounded segment queue the socket fills and [`crate::CloudTranscriptProvider::poll`]
//! drains.
//!
//! This is where this crate's real memory risk lives. A network transcript source filling a
//! queue that a **synchronous** `poll()` drains is the classic unbounded-growth shape: if the
//! operator stops polling, or polls slowly, or Deepgram floods interim results — which it
//! does, several per second per speaker — an unbounded queue grows for as long as the service
//! runs. A three-hour sermon is a long time to be wrong about this.
//!
//! # Two bounds, because either one alone is a hole
//!
//! - [`MAX_QUEUED_SEGMENTS`] bounds the **entry count**. A byte budget alone would admit
//!   unboundedly many tiny entries, which bounds memory but unbounds drain cost.
//! - [`MAX_QUEUED_SEGMENT_BYTES`] bounds the **retained transcript text**. An entry budget
//!   alone would admit a few very large entries.
//!
//! "Bytes" means retained transcript text specifically. The per-segment fixed overhead is not
//! counted here because it is already bounded by the entry cap — which is the other half of
//! why both bounds exist rather than one.
//!
//! The two are pinned at compile time to be **independently reachable**: for maximum-length
//! segments the byte budget binds first, and for minimal segments the entry budget does. Those
//! `const _: () = assert!` blocks are not decoration — they are what stops a later edit to
//! either constant from quietly turning one of the two bounded-memory tests vacuous.
//!
//! # Drop policy: oldest first
//!
//! When the queue is full the **oldest** segments go. For a live transcript the newest words
//! are the ones the operator needs; a stale backlog rendered minutes late is worse than
//! absent. The policy is defined here, tested by name, and reported through
//! [`SegmentQueue::dropped_for_bound`].

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use selahcue_core::transcript::{ProviderSegment, MAX_SEGMENT_TEXT_LEN};

/// Upper bound on **segments** held between the socket and a `poll`.
pub const MAX_QUEUED_SEGMENTS: usize = 256;

/// Upper bound on **retained transcript text bytes** held between the socket and a `poll`.
pub const MAX_QUEUED_SEGMENT_BYTES: usize = 128 * 1024;

// --- The premise both bounded-memory tests rest on, pinned at compile time -----------------
//
// Neither bound can be tested if the other always binds first. These two assertions make the
// two budgets independently reachable *by construction*, so changing either constant breaks
// the build here rather than silently leaving a test that can no longer fail.

const _: () = assert!(
    MAX_QUEUED_SEGMENTS * MAX_SEGMENT_TEXT_LEN > MAX_QUEUED_SEGMENT_BYTES,
    "the byte budget must be reachable before the entry budget for maximum-length segments; \
     otherwise the byte bound can never bite and its bounded-memory test is vacuous"
);

const _: () = assert!(
    MAX_QUEUED_SEGMENT_BYTES > MAX_QUEUED_SEGMENTS,
    "the entry budget must be reachable before the byte budget for minimal segments; \
     otherwise the entry bound can never bite and its bounded-memory test is vacuous"
);

const _: () = assert!(
    MAX_QUEUED_SEGMENTS > 1,
    "a cap of one makes 'the oldest is evicted, the newest is kept' unstateable"
);

// ADMISSIBILITY — see the equivalent note in `audio.rs`. The two assertions above pin that the
// budgets are independently reachable; this pins that a maximum-length segment can actually be
// retained. Without it the eviction loop below could empty the queue on every push while every
// bound stayed satisfied, and the `None => break` arm's comment — which claims the compile-time
// assertions guarantee a single segment fits — would be false.
const _: () = assert!(
    MAX_SEGMENT_TEXT_LEN <= MAX_QUEUED_SEGMENT_BYTES,
    "a segment truncated to the per-segment cap must still fit the queue's byte budget; \
     otherwise every push evicts what it just admitted and the panel stays empty while the \
     bounds report success"
);

#[derive(Debug, Default)]
struct Inner {
    segments: VecDeque<ProviderSegment>,
    retained_bytes: usize,
    admitted: u64,
    dropped_for_bound: u64,
    rejected_empty: u64,
}

impl Inner {
    /// **The** bound predicate — one expression, consumed both by the eviction loop below and
    /// by the tests.
    ///
    /// Defining it once is deliberate. A control that re-derives `count && bytes` from two
    /// separate reads is asserting something about a *copy* of the predicate, and survives a
    /// mutation of the real one (this repo has been bitten by exactly that: 86ak643rc). The
    /// tests therefore assert this verdict **and**, separately, the entities themselves — the
    /// pair is non-degenerate, where either alone can be satisfied by neutering the other.
    fn is_within_bounds(&self) -> bool {
        self.segments.len() <= MAX_QUEUED_SEGMENTS
            && self.retained_bytes <= MAX_QUEUED_SEGMENT_BYTES
    }
}

/// A bounded, cloneable, thread-safe queue of [`ProviderSegment`]s. The socket thread pushes;
/// the host thread drains. Clones share one queue.
#[derive(Debug, Clone, Default)]
pub struct SegmentQueue {
    inner: Arc<Mutex<Inner>>,
}

impl SegmentQueue {
    /// An empty queue.
    pub fn new() -> Self {
        SegmentQueue::default()
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        // A segment is data, not a critical section that can leave an invariant half-applied,
        // so a poisoned lock is recovered rather than propagated. Matching `selahcue-stt`.
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Offer a segment to the queue.
    ///
    /// Segments whose text is blank are **refused, not queued**: Deepgram emits interim frames
    /// with an empty transcript several times a second during silence, and admitting them
    /// would evict real text to store nothing. Text is truncated to
    /// [`MAX_SEGMENT_TEXT_LEN`] so one segment cannot dominate the byte budget. Then the
    /// oldest segments are evicted until the queue is [`Inner::is_within_bounds`] again.
    pub fn push(&self, segment: ProviderSegment) {
        let mut inner = self.lock();
        if segment.text.trim().is_empty() {
            inner.rejected_empty = inner.rejected_empty.saturating_add(1);
            return;
        }
        let segment = truncate_segment(segment);
        inner.retained_bytes = inner.retained_bytes.saturating_add(segment.text.len());
        inner.segments.push_back(segment);
        inner.admitted = inner.admitted.saturating_add(1);
        while !inner.is_within_bounds() {
            match inner.segments.pop_front() {
                Some(evicted) => {
                    inner.retained_bytes = inner.retained_bytes.saturating_sub(evicted.text.len());
                    inner.dropped_for_bound = inner.dropped_for_bound.saturating_add(1);
                }
                // Unreachable while a single segment fits the byte budget (the compile-time
                // assertions above guarantee it does), but written as a terminating loop
                // rather than one that trusts them.
                None => break,
            }
        }
    }

    /// Drain every queued segment in order, leaving the queue empty.
    pub fn drain(&self) -> Vec<ProviderSegment> {
        let mut inner = self.lock();
        inner.retained_bytes = 0;
        inner.segments.drain(..).collect()
    }

    /// Whether a segment with exactly this text is retained **right now**.
    ///
    /// The per-entity accessor the bounded-memory tests assert on. A count cannot answer
    /// "did the oldest segment survive the flood?" — several different queue states produce
    /// the same count, so a test built on one can pass for the wrong reason.
    pub fn retains_text(&self, text: &str) -> bool {
        self.lock().segments.iter().any(|s| s.text == text)
    }

    /// Number of queued segments (never exceeds [`MAX_QUEUED_SEGMENTS`]).
    pub fn len(&self) -> usize {
        self.lock().segments.len()
    }

    /// Whether there are no queued segments.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Retained transcript-text bytes (never exceeds [`MAX_QUEUED_SEGMENT_BYTES`]).
    ///
    /// **Logical length** (`text.len()` summed across queued segments) — the number the byte
    /// bound is defined in terms of, but not, by itself, proof of how much memory is actually
    /// retained. See [`SegmentQueue::retained_capacity_bytes`].
    pub fn retained_bytes(&self) -> usize {
        self.lock().retained_bytes
    }

    /// Total backing-allocation **capacity** across every retained segment's text, in bytes —
    /// the actual memory held, as distinct from [`SegmentQueue::retained_bytes`]'s logical
    /// length.
    ///
    /// The two can diverge: `String::truncate` (unlike the reallocating truncation this queue
    /// actually performs — see `truncate_segment`) sets length without shrinking capacity, so
    /// a queue built on it could report a bounded `retained_bytes()` while holding an
    /// unbounded `retained_capacity_bytes()`. This reads `String::capacity()` directly off the
    /// retained segments — the entity the bound is supposed to be limiting — rather than a
    /// count `truncate_segment` could satisfy without actually releasing anything (86akby4yz,
    /// V-1).
    pub fn retained_capacity_bytes(&self) -> usize {
        self.lock().segments.iter().map(|s| s.text.capacity()).sum()
    }

    /// The queue's own bound verdict — the same expression its eviction loop consumes.
    pub fn is_within_bounds(&self) -> bool {
        self.lock().is_within_bounds()
    }

    /// How many segments this queue has admitted since it was created.
    ///
    /// Per-instance, not global: a sibling test cannot run this number up on your behalf and
    /// make your "the flood actually happened" premise pass without your flood.
    pub fn admitted(&self) -> u64 {
        self.lock().admitted
    }

    /// How many segments have been evicted to stay inside the bounds. A bounded-memory test
    /// asserts this is non-zero **before** asserting the bound, because a bound that never
    /// bit is a bound that was not tested.
    pub fn dropped_for_bound(&self) -> u64 {
        self.lock().dropped_for_bound
    }

    /// How many blank-text segments have been refused.
    pub fn rejected_empty(&self) -> u64 {
        self.lock().rejected_empty
    }
}

/// Truncate a segment's text to [`MAX_SEGMENT_TEXT_LEN`] on a UTF-8 boundary (never panics,
/// never splits a codepoint).
///
/// Reallocates rather than calling `String::truncate` in place. `truncate` only sets the
/// logical length — it keeps the original backing allocation, capacity and all. Text arrives
/// here from `parse_results`' `.to_string()` and `to_segment`'s `.clone()`, with capacity
/// roughly the size of the transcript that produced it, and a transcript can arrive up to
/// `MAX_FRAME_BYTES` (256 KB). Truncating in place would therefore keep the full 256 KB
/// allocation alive behind a 2,000-byte segment: `retained_bytes` (which counts
/// `text.len()`) would report the bound as held while the process actually retained roughly
/// 130x that, under exactly the flood this bound exists to catch (86akby4yz, V-1).
/// `s[..end].to_string()` allocates fresh, at exactly `end` bytes — the same pattern
/// `selahcue_core::transcript::bounded_text` already uses.
fn truncate_segment(mut segment: ProviderSegment) -> ProviderSegment {
    if segment.text.len() > MAX_SEGMENT_TEXT_LEN {
        let mut end = MAX_SEGMENT_TEXT_LEN;
        while end > 0 && !segment.text.is_char_boundary(end) {
            end -= 1;
        }
        segment.text = segment.text[..end].to_string();
    }
    segment
}

// Tests live in `tests/test_queue.rs` (public-API integration tests).
