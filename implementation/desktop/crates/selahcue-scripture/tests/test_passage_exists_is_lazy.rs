//! `passage_exists_in` must NEVER decode a translation, and must not allocate (86ak84fbd).
//!
//! Why this is its own binary holding exactly ONE test: the verse indices are process-wide
//! `OnceLock`s, so "has translation X been decoded yet?" is only a meaningful question in a
//! process where nothing else has touched X. A sibling test calling `verses_in` first would turn
//! every assertion below into a statement about test ordering. The allocation counter is
//! per-thread for the same reason (the harness thread must not be able to add to it), and the
//! precedent for a counting allocator in a one-test binary is `selahcue-engine`'s
//! `test_jpeg_alloc.rs`.
//!
//! What it guards: the probe sits on the operator's view-build path, which runs after EVERY
//! command including Blackout and Clear. Answering "does this passage exist?" by decoding the
//! whole translation (≈4 MB of text, ≈31k `String`s, ≈15 MB of RSS each) put a first-press cost
//! of 68–260 ms (debug) on the emergency controls.

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{is_index_loaded, passage_exists_in, verses_in, Translation};
use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::Cell;

thread_local! {
    /// Bytes this thread has asked the allocator for (never decremented, so a free cannot hide it).
    static ALLOCATED: Cell<usize> = const { Cell::new(0) };
}

struct Counting;

fn count(bytes: usize) {
    // `try_with`: the allocator also runs while a thread is being torn down.
    let _ = ALLOCATED.try_with(|c| c.set(c.get().saturating_add(bytes)));
}

unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        count(layout.size());
        System.alloc(layout)
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        System.dealloc(ptr, layout)
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        count(new_size.saturating_sub(layout.size()));
        System.realloc(ptr, layout, new_size)
    }
}

#[global_allocator]
static ALLOC: Counting = Counting;

fn allocated_now() -> usize {
    ALLOCATED.with(Cell::get)
}

const BUNDLED: [Translation; 5] = [
    Translation::Kjv,
    Translation::Web,
    Translation::Asv,
    Translation::Webbe,
    Translation::Dby,
];

#[test]
fn probing_a_passage_decodes_no_translation_and_allocates_nothing() {
    let real = parse_one("John 3:16").unwrap();
    let real_range = parse_one("Romans 8:28-30").unwrap();
    let whole_chapter = parse_one("Psalm 23").unwrap();
    let gap = parse_one("Luke 17:36").unwrap(); // absent in WEB/ASV/WEBBE
    let jude = parse_one("Jude 2:1").unwrap(); // parses, names nothing
    let past_end = parse_one("Romans 99:1").unwrap();

    // Premise: nothing has decoded anything yet. If a test-harness change or a sibling made this
    // false, every "still not loaded" below would be vacuous — say so by name.
    for t in BUNDLED {
        assert!(
            !is_index_loaded(t),
            "{}: already decoded before the probe ran — the laziness assertions would be vacuous",
            t.code()
        );
    }

    // The probes. Both verdicts, because "no decode" must hold for a hit AND a miss — a miss is
    // exactly what the old implementation was most tempted to pay a full decode for.
    let before = allocated_now();
    let mut found = 0usize;
    let mut missed = 0usize;
    for _ in 0..1_000 {
        for t in BUNDLED {
            for r in [&real, &real_range, &whole_chapter, &gap, &jude, &past_end] {
                if passage_exists_in(t, r) {
                    found += 1;
                } else {
                    missed += 1;
                }
            }
        }
    }
    let allocated = allocated_now() - before;

    // Positive control on the verdicts: the loop exercised hits and misses, and the answers are
    // the right ones (John 3:16, Romans 8:28-30, Psalm 23 exist everywhere = 15 hits per pass;
    // Luke 17:36 exists only in KJV + DBY = 2; Jude 2:1 and Romans 99:1 never = 0).
    assert_eq!(found, 1_000 * (15 + 2), "hits per pass");
    assert_eq!(missed, 1_000 * (30 - 17), "misses per pass");

    for t in BUNDLED {
        assert!(
            !is_index_loaded(t),
            "{}: passage_exists_in decoded the whole translation — that is the cost this probe exists to avoid",
            t.code()
        );
    }
    assert_eq!(
        allocated, 0,
        "30,000 probes allocated {allocated} bytes; the probe must answer from static data"
    );

    // Positive control on the accessor itself: it must see a real decode, and only of the
    // translation that was actually touched — otherwise `!is_index_loaded` above proves nothing.
    assert!(!verses_in(Translation::Web, &real).is_empty());
    assert!(is_index_loaded(Translation::Web), "verses_in decodes WEB");
    for t in [
        Translation::Kjv,
        Translation::Asv,
        Translation::Webbe,
        Translation::Dby,
    ] {
        assert!(
            !is_index_loaded(t),
            "{}: touching WEB must not decode any other translation",
            t.code()
        );
    }

    // And a probe after a decode agrees with itself (the loaded index is not consulted differently).
    assert!(passage_exists_in(Translation::Web, &real));
    assert!(!passage_exists_in(Translation::Web, &gap));
}
