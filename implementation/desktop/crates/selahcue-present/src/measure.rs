//! A persistent, thread-local memo for shaped text widths (`measure_line_width`).
//!
//! Auto-fit layout ([`crate::compose::autofit_layers`]) binary-searches the font cell,
//! re-measuring every word of a region at each candidate size, and the stage/confidence
//! monitor re-composes once a second so a running countdown's digits stay current. Shaping
//! is by far the dominant cost of that recompose, and the words themselves almost never
//! change between ticks — so the widths are memoized ACROSS composes here rather than in a
//! per-call map that is thrown away and rebuilt every time.
//!
//! The key carries every input [`selahcue_engine::raster::measure_line_width`] itself takes
//! — text, cell, font family, weight — so a hit can only ever return the width that a fresh
//! shaping would have produced. Nothing else is folded in: a stale or colliding key would
//! silently mis-wrap a verse, which is far worse than the shaping it saves.

use selahcue_engine::scene::FontName;
use std::cell::RefCell;
use std::collections::HashMap;

/// Everything that changes the shaped width of a run of text — i.e. exactly the arguments
/// of [`selahcue_engine::raster::measure_line_width`]. [`FontName`] is `Eq` but not `Hash`,
/// so the hash is written by hand over the same fields the equality compares.
#[derive(PartialEq, Eq)]
struct Key {
    text: Box<str>,
    cell: u32,
    font: Option<FontName>,
    weight: u16,
}

impl Key {
    /// The ONLY place a [`Key`] is built. [`MeasureCache::measure`] (the production
    /// insert/lookup site) and [`measure_cache_hits_for`] (the test-facing per-key hit
    /// accessor) must read the exact same key for the exact same inputs, or the accessor
    /// can silently report on a key that is not the one under test. Routing both through
    /// one constructor makes that true by construction instead of by the two sites happening
    /// to agree.
    fn new(text: &str, cell: u32, font: Option<&FontName>, weight: u16) -> Self {
        Key {
            text: text.into(),
            cell,
            font: font.copied(),
            weight,
        }
    }
}

impl std::hash::Hash for Key {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        // Destructured with no `..`: adding a field to `Key` without extending this pattern
        // is a compile error, not a silently-unhashed field.
        let Key {
            text,
            cell,
            font,
            weight,
        } = self;
        text.hash(state);
        cell.hash(state);
        font.as_ref().map(FontName::as_str).hash(state);
        weight.hash(state);
    }
}

/// Maximum measurements held per thread. One entry is roughly 130 bytes (the key's
/// inline [`FontName`] dominates), so the memo costs on the order of half a megabyte at
/// its cap — comfortably below what re-shaping a service's worth of text would cost in
/// time, and hard-bounded so a long service cannot grow it.
pub const MAX_MEASURE_CACHE_ENTRIES: usize = 4096;

/// Longest text (in bytes) the memo will store. A longer token — a space-less paste is a
/// single token to `split_whitespace`, so the auto-fit does measure such things — is
/// measured normally but never remembered, so the memo's heap stays bounded by
/// `MAX_MEASURE_CACHE_ENTRIES × MAX_MEASURE_CACHE_TEXT_BYTES` regardless of what a paste
/// contains. Real words, including the longest compound forms, are far below it.
pub const MAX_MEASURE_CACHE_TEXT_BYTES: usize = 128;

/// A memoized width plus the access counter that orders eviction.
struct Entry {
    width: f32,
    /// The value of [`MeasureCache::clock`] at this entry's most recent use.
    used_at: u64,
    /// Lookups THIS entry has served since it was inserted. Per-entry rather than only
    /// global, so a test can prove the memo answered for the exact key it cares about —
    /// a global total can be run up by unrelated lookups and hide a miss on that key.
    hits: u64,
}

/// What the memo currently holds and how it has been used — the observable a caller (or a
/// test) needs to tell REUSE from mere population: `misses` counts actual shaping calls.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MeasureCacheStats {
    /// Measurements currently held.
    pub entries: usize,
    /// Lookups served from the memo.
    pub hits: u64,
    /// Lookups that had to shape the text.
    pub misses: u64,
}

/// The memo itself: a flat map under a least-recently-used bound.
#[derive(Default)]
struct MeasureCache {
    map: HashMap<Key, Entry>,
    /// Monotonic access counter; every lookup consumes one value, so no two live entries
    /// share a `used_at` and the LRU order is total.
    clock: u64,
    hits: u64,
    misses: u64,
}

impl MeasureCache {
    fn measure(&mut self, text: &str, cell: u32, font: Option<&FontName>, weight: u16) -> f32 {
        if text.len() > MAX_MEASURE_CACHE_TEXT_BYTES {
            return selahcue_engine::raster::measure_line_width(text, cell, font, weight);
        }
        // Saturating rather than wrapping: at u64::MAX the ordering would flatten and
        // eviction would pick arbitrarily, which is still bounded and still correct —
        // whereas wrapping would make an ancient entry look freshly used.
        self.clock = self.clock.saturating_add(1);
        let used_at = self.clock;
        let key = Key::new(text, cell, font, weight);
        if let Some(entry) = self.map.get_mut(&key) {
            entry.used_at = used_at;
            entry.hits = entry.hits.saturating_add(1);
            self.hits = self.hits.saturating_add(1);
            return entry.width;
        }
        self.misses = self.misses.saturating_add(1);
        let width = selahcue_engine::raster::measure_line_width(text, cell, font, weight);
        if self.map.len() >= MAX_MEASURE_CACHE_ENTRIES {
            self.evict_lru();
        }
        self.map.insert(
            key,
            Entry {
                width,
                used_at,
                hits: 0,
            },
        );
        width
    }

    /// Drop the least-recently-used quarter of the memo. A quarter at a time rather than
    /// a single entry per insert: finding the one oldest entry costs a full scan, so
    /// evicting singly would make every insert past the cap O(n). This is the same scan
    /// amortised over the next `MAX_MEASURE_CACHE_ENTRIES / 4` inserts.
    fn evict_lru(&mut self) {
        let keep = MAX_MEASURE_CACHE_ENTRIES - MAX_MEASURE_CACHE_ENTRIES / 4;
        let mut used: Vec<u64> = self.map.values().map(|e| e.used_at).collect();
        if used.len() <= keep {
            return;
        }
        let drop_count = used.len() - keep;
        // Partition so `used[drop_count]` is the oldest counter that survives.
        used.select_nth_unstable(drop_count);
        let cutoff = used[drop_count];
        self.map.retain(|_, e| e.used_at >= cutoff);
    }
}

thread_local! {
    static MEASURE_CACHE: RefCell<MeasureCache> = RefCell::new(MeasureCache::default());
}

/// The shaped pixel width of `text` at `cell` px in `font` at `weight`, served from the
/// thread-local memo when it has been measured before and shaped (and remembered) otherwise.
/// Bit-identical to calling [`selahcue_engine::raster::measure_line_width`] directly, which
/// is what makes the memo invisible to layout.
pub fn measure_word(text: &str, cell: u32, font: Option<&FontName>, weight: u16) -> f32 {
    MEASURE_CACHE.with(|cell_ref| cell_ref.borrow_mut().measure(text, cell, font, weight))
}

/// Number of measurements currently held — for the bounded-memory test.
pub fn measure_cache_len() -> usize {
    MEASURE_CACHE.with(|cell| cell.borrow().map.len())
}

/// How many lookups the memo has SERVED for this exact measurement key: `None` when the
/// key is not resident at all (never measured, or evicted), `Some(0)` when it is resident
/// but has only ever been inserted. The distinction is the point — it lets a caller tell
/// "the memo answered" from "the memo was bypassed", which an aggregate hit total cannot.
pub fn measure_cache_hits_for(
    text: &str,
    cell: u32,
    font: Option<&FontName>,
    weight: u16,
) -> Option<u64> {
    if text.len() > MAX_MEASURE_CACHE_TEXT_BYTES {
        return None; // never resident by construction
    }
    let key = Key::new(text, cell, font, weight);
    MEASURE_CACHE.with(|cell_ref| cell_ref.borrow().map.get(&key).map(|e| e.hits))
}

/// A snapshot of this thread's memo: what it holds, and how many lookups it has served
/// versus had to shape.
pub fn measure_cache_stats() -> MeasureCacheStats {
    MEASURE_CACHE.with(|cell| {
        let cache = cell.borrow();
        MeasureCacheStats {
            entries: cache.map.len(),
            hits: cache.hits,
            misses: cache.misses,
        }
    })
}

/// Drop every held measurement (test isolation + an explicit free hook).
pub fn reset_measure_cache() {
    MEASURE_CACHE.with(|cell| {
        let cache = &mut *cell.borrow_mut();
        cache.map.clear();
        cache.clock = 0;
        cache.hits = 0;
        cache.misses = 0;
    });
}
