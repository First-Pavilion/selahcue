//! Allocation growth across canonical candidates is a resource regression, not a timing test.
use selahcue_core::scripture::{parse_one, ParseError};
use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::Cell;
use std::hint::black_box;

struct CountingAllocator;
std::thread_local! {
    static ALLOCATIONS: Cell<Option<usize>> = const { Cell::new(None) };
}

fn record_allocation() {
    // No heap allocation or shared state in the observer; ignore thread teardown.
    let _ = ALLOCATIONS.try_with(|counter| {
        if let Some(count) = counter.get() {
            counter.set(Some(count + 1));
        }
    });
}

// This test-only allocator delegates every operation, unchanged, to System.
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        record_allocation();
        // SAFETY: forward the allocator contract's unchanged layout.
        unsafe { System.alloc(layout) }
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        record_allocation();
        // SAFETY: forward the allocator contract's unchanged layout.
        unsafe { System.alloc_zeroed(layout) }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        // SAFETY: the same System allocator supplied this pointer/layout pair.
        unsafe { System.dealloc(ptr, layout) }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, size: usize) -> *mut u8 {
        record_allocation();
        // SAFETY: forward the original allocation and caller's new size unchanged.
        unsafe { System.realloc(ptr, layout, size) }
    }
}

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

fn measured<T>(operation: impl FnOnce() -> T) -> (T, usize) {
    ALLOCATIONS.with(|counter| counter.set(Some(0)));
    let result = operation();
    let count = ALLOCATIONS
        .with(|counter| counter.replace(None))
        .expect("measurement active");
    (result, count)
}

#[test]
fn scanning_more_canonical_books_does_not_allocate_more_strings() {
    // Positive control: observing real allocation, not an inert or optimized-away counter.
    let (owned, observed) = measured(|| black_box(Vec::<u8>::with_capacity(64)));
    assert_eq!(observed, 1);
    drop(owned);

    // Equal-length book names keep the parser's front-end allocation work identical.
    // Reinstating normalize(b.name) in lookup_book must make late/missed searches fail.
    let (early, early_allocs) = measured(|| black_box(parse_one(black_box("Genesis 1:1"))));
    let (late, late_allocs) = measured(|| black_box(parse_one(black_box("Malachi 1:1"))));
    let (miss, miss_allocs) = measured(|| black_box(parse_one(black_box("abcdefg 1:1"))));
    assert_eq!(early.expect("early book").book, 1);
    assert_eq!(late.expect("late book").book, 39);
    assert_eq!(miss, Err(ParseError::UnknownBook));
    assert_eq!(
        late_allocs, early_allocs,
        "canonical candidate traversal allocated Strings"
    );
    assert_eq!(
        miss_allocs, early_allocs,
        "a full-canon miss allocated per candidate"
    );
}
