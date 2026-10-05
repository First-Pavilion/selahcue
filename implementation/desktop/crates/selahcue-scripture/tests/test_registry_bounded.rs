//! The registry keeps at most N decoded indexes in memory (default 3), evicting the least
//! recently used, so a machine with 4 GB of RAM never holds every downloaded Bible at once.
//!
//! What makes these tests bite (the method is in `implementation/desktop/CLAUDE.md`):
//!
//! - **Per-key accessors, one registry per test.** `resident_codes`, `resident_hits_for` and
//!   `loads_for` answer for one translation of one `Registry` instance. There is no global counter
//!   a sibling test's reads could inflate, and no process-wide state to share: every test builds
//!   its own registry over its own directory.
//! - **The premise is pinned at compile time.** The fixtures outnumber the cap, and the cap is the
//!   brief's 3; changing either stops this file compiling instead of silently leaving the eviction
//!   cases vacuous.
//! - **The entity is asserted, not a proxy.** Not "retained bytes <= N * size", but which named
//!   translations are resident and, for memory actually being freed, that the cache's `Arc` is the
//!   one that was dropped (a `Weak` to an evicted index no longer upgrades).
//! - **Positive controls.** A cache hit is shown to have happened (hit count, no extra decode)
//!   before any statement about eviction, so "evicted" cannot be confused with "never cached".
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::fs;
use std::path::PathBuf;
use std::sync::Arc;

use common::{catalogue_json, fixture, tmp_dir, Fixture};
use selahcue_scripture::catalog::{Catalogue, TranslationCode};
use selahcue_scripture::registry::{InstallHooks, Registry, DEFAULT_RESIDENT_INDEXES};

const CODES: [&str; 5] = ["AAA", "BBB", "CCC", "DDD", "EEE"];

// The brief's default, and enough fixtures to go past it with room to tell LRU from FIFO.
const _: () = assert!(DEFAULT_RESIDENT_INDEXES == 3);
const _: () = assert!(CODES.len() > DEFAULT_RESIDENT_INDEXES + 1);
const _: () = assert!(DEFAULT_RESIDENT_INDEXES >= 2);

fn code(s: &str) -> TranslationCode {
    TranslationCode::parse(s).unwrap()
}

/// A registry over a fresh directory with all five fixtures INSTALLED (not yet read).
fn installed_registry(capacity: Option<usize>) -> (Registry, PathBuf) {
    let root = tmp_dir("bounded");
    let dir = root.join("data");
    let fixtures: Vec<Fixture> = CODES.iter().map(|c| fixture(c, 3, 2)).collect();
    let catalogue = Catalogue::parse(&catalogue_json(
        Some("https://downloads.example.org/t/"),
        fixtures.iter().map(|f| f.entry("cleared")).collect(),
    ))
    .unwrap();
    let registry = match capacity {
        Some(n) => Registry::with_capacity(dir, catalogue, n),
        None => Registry::new(dir, catalogue),
    };
    for f in &fixtures {
        let src = root.join(format!("{}.src", f.code));
        fs::write(&src, &f.gz).unwrap();
        registry
            .install_from_file(&f.code, &src, 1, &InstallHooks::default())
            .unwrap();
    }
    (registry, root)
}

fn read(registry: &Registry, c: &str) {
    assert!(
        !registry.index(&code(c)).unwrap().is_empty(),
        "{c} must decode to verses"
    );
}

#[test]
fn n_plus_one_translations_never_leave_more_than_n_indexes_resident() {
    let (reg, _root) = installed_registry(None);
    assert_eq!(reg.capacity(), DEFAULT_RESIDENT_INDEXES);

    // Installing five translations decodes nothing that stays in memory.
    assert_eq!(reg.resident_codes(), Vec::<String>::new());
    for c in CODES {
        assert_eq!(
            reg.loads_for(c),
            0,
            "installing {c} must not leave a decoded index behind"
        );
    }

    // Read them in order: the resident set is capped at every step, and it is the NEWEST ones.
    let mut expected_len = 0;
    for c in CODES {
        read(&reg, c);
        expected_len = (expected_len + 1).min(DEFAULT_RESIDENT_INDEXES);
        let resident = reg.resident_codes();
        assert_eq!(
            resident.len(),
            expected_len,
            "after reading {c}: {resident:?}"
        );
        assert!(resident.len() <= DEFAULT_RESIDENT_INDEXES);
        assert_eq!(
            resident[0], c,
            "the one just read is the most recently used"
        );
    }
    // The PEAK, not just the steady state: room is made before a decode, so the cache plus the
    // index being decoded never reached cap + 1. (And it did reach the cap, so this is not an idle
    // cache.)
    assert_eq!(
        reg.peak_decoded(),
        DEFAULT_RESIDENT_INDEXES,
        "the most indexes ever held at once must be exactly the cap"
    );
    // The entity, by name: AAA and BBB (the two oldest) are gone, EEE, DDD, CCC remain.
    assert_eq!(reg.resident_codes(), ["EEE", "DDD", "CCC"]);
    assert_eq!(
        reg.resident_hits_for("AAA"),
        None,
        "AAA must have been evicted"
    );
    assert_eq!(
        reg.resident_hits_for("BBB"),
        None,
        "BBB must have been evicted"
    );
    for c in ["CCC", "DDD", "EEE"] {
        assert!(
            reg.resident_hits_for(c).is_some(),
            "{c} must still be resident"
        );
    }
}

#[test]
fn a_resident_translation_is_served_from_memory_not_decoded_again() {
    // Positive control for every eviction claim: the cache really is a cache.
    let (reg, _root) = installed_registry(None);
    read(&reg, "AAA");
    assert_eq!(reg.loads_for("AAA"), 1);
    assert_eq!(reg.resident_hits_for("AAA"), Some(0));
    read(&reg, "AAA");
    read(&reg, "AAA");
    assert_eq!(
        reg.loads_for("AAA"),
        1,
        "a hit must not decode the file again"
    );
    assert_eq!(
        reg.resident_hits_for("AAA"),
        Some(2),
        "the cache hit was not exercised, so nothing below says anything about the cache"
    );
}

#[test]
fn eviction_is_least_recently_used_not_first_in() {
    let (reg, _root) = installed_registry(None);
    // Fill the cache: order (most recent first) is CCC, BBB, AAA.
    for c in ["AAA", "BBB", "CCC"] {
        read(&reg, c);
    }
    assert_eq!(reg.resident_codes(), ["CCC", "BBB", "AAA"]);
    // Touch the OLDEST. First-in-first-out would still evict it next; LRU must not.
    read(&reg, "AAA");
    assert_eq!(
        reg.resident_hits_for("AAA"),
        Some(1),
        "premise: the touch was a hit"
    );
    assert_eq!(reg.resident_codes(), ["AAA", "CCC", "BBB"]);
    // A fourth translation must push out BBB (now the least recently used), not AAA.
    read(&reg, "DDD");
    assert_eq!(reg.resident_codes(), ["DDD", "AAA", "CCC"]);
    assert_eq!(
        reg.resident_hits_for("BBB"),
        None,
        "BBB was the least recently used"
    );
    assert!(
        reg.resident_hits_for("AAA").is_some(),
        "AAA was touched, so it stays"
    );
}

#[test]
fn an_evicted_translation_is_decoded_again_when_it_is_read_again() {
    let (reg, _root) = installed_registry(None);
    for c in ["AAA", "BBB", "CCC", "DDD"] {
        read(&reg, c);
    }
    assert_eq!(
        reg.resident_hits_for("AAA"),
        None,
        "premise: AAA was evicted"
    );
    assert_eq!(reg.loads_for("AAA"), 1);
    read(&reg, "AAA");
    assert_eq!(
        reg.loads_for("AAA"),
        2,
        "an evicted translation is reloaded from its file"
    );
    assert!(reg.resident_hits_for("AAA").is_some());
    assert_eq!(reg.resident_codes().len(), DEFAULT_RESIDENT_INDEXES);
}

#[test]
fn evicting_an_index_frees_it_and_does_not_just_hide_it() {
    let (reg, _root) = installed_registry(None);
    let held = reg.index(&code("AAA")).unwrap();
    let weak = Arc::downgrade(&held);
    // While it is resident the cache holds one reference and this test holds the other.
    assert_eq!(
        Arc::strong_count(&held),
        2,
        "premise: the cache holds AAA's index"
    );

    for c in ["BBB", "CCC", "DDD"] {
        read(&reg, c);
    }
    assert_eq!(
        reg.resident_hits_for("AAA"),
        None,
        "premise: AAA was evicted"
    );
    assert_eq!(
        Arc::strong_count(&held),
        1,
        "the cache must have let go of the evicted index"
    );
    drop(held);
    assert!(
        weak.upgrade().is_none(),
        "the evicted index is still in memory after its last holder dropped it"
    );
}

#[test]
fn the_cap_is_configurable_and_never_below_one() {
    for cap in [1usize, 2, 4] {
        let (reg, _root) = installed_registry(Some(cap));
        assert_eq!(reg.capacity(), cap);
        for c in CODES {
            read(&reg, c);
            assert!(reg.resident_codes().len() <= cap, "cap {cap} after {c}");
        }
        assert_eq!(
            reg.resident_codes().len(),
            cap,
            "cap {cap} should be full after 5 reads"
        );
        assert_eq!(
            reg.peak_decoded(),
            cap,
            "cap {cap}: the peak must be the cap, not more"
        );
        // The survivors are the most recently read ones.
        let want: Vec<String> = CODES
            .iter()
            .rev()
            .take(cap)
            .map(|s| s.to_string())
            .collect();
        assert_eq!(reg.resident_codes(), want, "cap {cap}");
    }
    // Zero would mean "cache nothing": every read would decode the whole file. It is one.
    let (reg, _root) = installed_registry(Some(0));
    assert_eq!(reg.capacity(), 1);
    read(&reg, "AAA");
    read(&reg, "BBB");
    assert_eq!(reg.resident_codes(), ["BBB"]);
}

#[test]
fn a_code_that_is_not_installed_is_never_cached() {
    let (reg, _root) = installed_registry(None);
    for _ in 0..50 {
        assert!(reg.index(&code("ZZZ")).is_err());
    }
    assert_eq!(reg.resident_codes(), Vec::<String>::new());
    assert_eq!(reg.loads_for("ZZZ"), 0);
}

#[test]
fn many_threads_reading_many_translations_never_exceed_the_cap() {
    let (reg, _root) = installed_registry(None);
    let stop = std::sync::atomic::AtomicBool::new(false);
    let widest = std::sync::atomic::AtomicUsize::new(0);
    std::thread::scope(|scope| {
        // A sampler that watches the resident count while the readers churn the cache.
        scope.spawn(|| {
            while !stop.load(std::sync::atomic::Ordering::Relaxed) {
                let n = reg.resident_codes().len();
                widest.fetch_max(n, std::sync::atomic::Ordering::Relaxed);
            }
        });
        let readers: Vec<_> = (0..6)
            .map(|t| {
                let reg = &reg;
                scope.spawn(move || {
                    for i in 0..120 {
                        let c = CODES[(t + i * 3) % CODES.len()];
                        assert!(!reg.index(&code(c)).unwrap().is_empty());
                    }
                })
            })
            .collect();
        for r in readers {
            r.join().unwrap();
        }
        stop.store(true, std::sync::atomic::Ordering::Relaxed);
    });
    let widest = widest.load(std::sync::atomic::Ordering::Relaxed);
    assert!(
        widest <= DEFAULT_RESIDENT_INDEXES,
        "the resident count reached {widest} under concurrent reads (cap {DEFAULT_RESIDENT_INDEXES})"
    );
    assert!(reg.resident_codes().len() <= DEFAULT_RESIDENT_INDEXES);
    assert!(
        reg.peak_decoded() <= DEFAULT_RESIDENT_INDEXES,
        "a decode overlapped a full cache: peak {}",
        reg.peak_decoded()
    );
    // The churn really did evict and reload (otherwise the check above saw an idle cache).
    let reloads: u64 = CODES.iter().map(|c| reg.loads_for(c)).sum();
    assert!(
        reloads > CODES.len() as u64,
        "the readers never forced a reload ({reloads} loads), so the cache was not under pressure"
    );
}

#[test]
fn a_damaged_file_does_not_evict_a_good_index() {
    let (reg, root) = installed_registry(None);
    for c in ["AAA", "BBB", "CCC"] {
        read(&reg, c);
    }
    assert_eq!(reg.resident_codes(), ["CCC", "BBB", "AAA"]);

    // DDD's file is damaged in place (same length, one byte flipped).
    let path = root.join("data").join("ddd.tsv.gz");
    let mut bytes = fs::read(&path).unwrap();
    bytes[12] ^= 0xFF;
    fs::write(&path, &bytes).unwrap();

    for _ in 0..5 {
        assert!(
            reg.index(&code("DDD")).is_err(),
            "premise: DDD cannot be read"
        );
    }
    assert_eq!(
        reg.resident_codes(),
        ["CCC", "BBB", "AAA"],
        "reading a file that fails its check must not push a good translation out of memory"
    );
    assert_eq!(reg.loads_for("DDD"), 0);
}
