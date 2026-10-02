//! `chapter_verse_bounds_in` must NEVER decode a translation, and must not allocate (86ak84fbd).
//!
//! Why this is its own binary holding exactly ONE test: the verse indices are process-wide
//! `OnceLock`s, so "has translation X been decoded yet?" is only a meaningful question in a process
//! where nothing else has touched X (see `test_passage_exists_is_lazy.rs`, whose shape this
//! follows). The allocation counter is per-thread for the same reason.
//!
//! What it guards: a plan's scripture links are fitted to their chapter when a plan loads and on
//! every link edit. Asking "how far does this chapter run?" by decoding the whole translation
//! (≈4 MB of text, ≈31k `String`s) put that cost on controller start-up, one translation at a time
//! for every translation the plan names.

#![allow(clippy::unwrap_used)]

use selahcue_core::scripture::parse_one;
use selahcue_scripture::{chapter_verse_bounds_in, is_index_loaded, verses_in, Translation};
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

fn bundled() -> Vec<Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
        .collect()
}

#[test]
fn asking_where_a_chapter_ends_decodes_no_translation_and_allocates_nothing() {
    let bundled = bundled();
    assert!(
        bundled.len() >= 5,
        "premise: the five bundled translations are all in scope, got {}",
        bundled.len()
    );
    let whole_chapter = parse_one("Psalm 23").unwrap();
    let range = parse_one("Romans 8:28-30").unwrap();
    let gap = parse_one("Luke 17").unwrap(); // a verse missing in WEB/ASV/WEBBE
    let long = parse_one("Psalm 119").unwrap();
    let jude = parse_one("Jude 2:1").unwrap(); // a chapter that does not exist
    let past_end = parse_one("Romans 99").unwrap();
    let refs = [&whole_chapter, &range, &gap, &long, &jude, &past_end];

    // Premise: nothing has decoded anything yet. If a harness change or a sibling made this false,
    // every "still not loaded" below would be vacuous — say so by name.
    for t in &bundled {
        assert!(
            !is_index_loaded(*t),
            "{}: already decoded before the probe ran — the laziness assertions would be vacuous",
            t.code()
        );
    }

    // Both outcomes: "no decode" must hold for a chapter that exists AND one that does not.
    const PASSES: usize = 1_000;
    let before = allocated_now();
    let mut found = 0usize;
    let mut missed = 0usize;
    for _ in 0..PASSES {
        for t in &bundled {
            for r in refs {
                if chapter_verse_bounds_in(*t, r).is_some() {
                    found += 1;
                } else {
                    missed += 1;
                }
            }
        }
    }
    let allocated = allocated_now() - before;
    let probes = PASSES * bundled.len() * refs.len();

    for t in &bundled {
        assert!(
            !is_index_loaded(*t),
            "{}: chapter_verse_bounds_in decoded the whole translation — that is the cost it \
             exists to avoid",
            t.code()
        );
    }
    assert_eq!(
        allocated, 0,
        "{probes} lookups allocated {allocated} bytes; the answer must come from static data"
    );
    // 4 of the 6 chapters exist in every translation, 2 never do.
    assert_eq!(found, PASSES * bundled.len() * 4, "chapters found");
    assert_eq!(missed, PASSES * bundled.len() * 2, "chapters not found");

    // Positive control, ONE PER TRANSLATION: decode them one at a time and require
    // `is_index_loaded` to flip for exactly the one just touched. A copy-paste slip in any arm of
    // `is_index_loaded` would leave its translation reading "not loaded" after a real decode, and
    // the `!is_index_loaded` above could be blind for it without anything saying so.
    for (i, t) in bundled.iter().enumerate() {
        assert!(!verses_in(*t, &whole_chapter).is_empty(), "premise");
        for (j, u) in bundled.iter().enumerate() {
            assert_eq!(
                is_index_loaded(*u),
                j <= i,
                "after decoding {} (translation #{i}): is_index_loaded({}) is wrong",
                t.code(),
                u.code()
            );
        }
    }
}
