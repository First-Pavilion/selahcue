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
//! whole translation (≈4 MB of text, ≈31k `String`s; ≈15 MB of RSS each in a debug build, ≈7 MiB
//! in release) put a first-press cost of 68–260 ms (the ticket's debug-build wall-clock figures)
//! on the emergency controls.

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

/// Every translation compiled into the binary, derived rather than listed: a sixth bundled
/// translation joins this test automatically (and fails it if it decodes, allocates, or has an
/// `is_index_loaded` arm that watches the wrong index).
fn bundled() -> Vec<Translation> {
    Translation::ALL
        .into_iter()
        .filter(|t| !t.is_downloadable())
        .collect()
}

#[test]
fn probing_a_passage_decodes_no_translation_and_allocates_nothing() {
    let bundled = bundled();
    assert!(
        bundled.len() >= 5,
        "premise: the five bundled translations are all in scope, got {}",
        bundled.len()
    );
    let real = parse_one("John 3:16").unwrap();
    let real_range = parse_one("Romans 8:28-30").unwrap();
    let whole_chapter = parse_one("Psalm 23").unwrap();
    let gap = parse_one("Luke 17:36").unwrap(); // absent in WEB/ASV/WEBBE
    let jude = parse_one("Jude 2:1").unwrap(); // parses, names nothing
    let past_end = parse_one("Romans 99:1").unwrap();
    let refs = [&real, &real_range, &whole_chapter, &gap, &jude, &past_end];

    // Premise: nothing has decoded anything yet. If a test-harness change or a sibling made this
    // false, every "still not loaded" below would be vacuous — say so by name.
    for t in &bundled {
        assert!(
            !is_index_loaded(*t),
            "{}: already decoded before the probe ran — the laziness assertions would be vacuous",
            t.code()
        );
    }

    // The probes. Both verdicts, because "no decode" must hold for a hit AND a miss — a miss is
    // exactly what the old implementation was most tempted to pay a full decode for.
    const PASSES: usize = 1_000;
    let before = allocated_now();
    let mut found = 0usize;
    let mut missed = 0usize;
    for _ in 0..PASSES {
        for t in &bundled {
            for r in refs {
                if passage_exists_in(*t, r) {
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
            "{}: passage_exists_in decoded the whole translation — that is the cost this probe exists to avoid",
            t.code()
        );
    }
    assert_eq!(
        allocated, 0,
        "{probes} probes allocated {allocated} bytes; the probe must answer from static data"
    );

    // Positive control on the accessor, ONE PER TRANSLATION: decode the translations one at a
    // time and require `is_index_loaded` to flip for exactly the one just touched. A copy-paste
    // slip in any arm of `is_index_loaded` (say `Asv => KJV_INDEX.get()...`) leaves its
    // translation reading "not loaded" after a real decode, or a neighbour reading "loaded"
    // early, and fails here — without this, `!is_index_loaded` above could be blind for one
    // translation and nothing would say so. Decoding is fine from this point on.
    //
    // The same pass is the ORACLE for the verdict counts above: how many of the probes should
    // have been hits is whatever the renderer's own lookup says, per translation, so the
    // expectation extends to a sixth bundled translation instead of being a hand-counted 15 + 2.
    let mut expected_hits_per_pass = 0usize;
    for (i, t) in bundled.iter().enumerate() {
        for r in refs {
            if !verses_in(*t, r).is_empty() {
                expected_hits_per_pass += 1;
            }
        }
        for (j, u) in bundled.iter().enumerate() {
            assert_eq!(
                is_index_loaded(*u),
                j <= i,
                "after decoding {} (translation #{i}): is_index_loaded({}) is wrong — \
                 `verses_in` decodes exactly the translation it was asked about",
                t.code(),
                u.code()
            );
        }
    }
    let total_per_pass = bundled.len() * refs.len();
    assert!(
        expected_hits_per_pass > 0 && expected_hits_per_pass < total_per_pass,
        "premise: the probe set mixes hits and misses ({expected_hits_per_pass} of {total_per_pass})"
    );
    assert_eq!(found, PASSES * expected_hits_per_pass, "hits");
    assert_eq!(
        missed,
        PASSES * (total_per_pass - expected_hits_per_pass),
        "misses"
    );

    // And a probe after a decode agrees with itself (the loaded index is not consulted differently).
    assert!(passage_exists_in(Translation::Web, &real));
    assert!(!passage_exists_in(Translation::Web, &gap));
}
