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
//! - **The peak is observed by the indexes, not by the cache.** `peak_live_indexes` counts decoded
//!   indexes from the first moment a decode starts to the moment the index is dropped, using a
//!   guard each index owns. A cache that decoded the new index and only then evicted the old one
//!   would show its cap in a counter it kept for itself; it cannot hide from this one.
//! - **Concurrency is made deterministic with a gate**, not a sleep-and-hope: a load hook that parks
//!   every thread at a named point lets a test count exactly how many got there.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::fs;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{mpsc, Arc};
use std::time::{Duration, Instant};

use common::{catalogue_json, fixture, fixture_labelled, plant, tmp_dir, verse_text, Fixture};
use selahcue_scripture::catalog::{Catalogue, TranslationCode};
use selahcue_scripture::registry::{
    InstallHooks, LoadError, LoadStage, Registry, DEFAULT_RESIDENT_INDEXES,
};
use selahcue_scripture::validate::ValidationError;

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
    // cache.) The count is the one the INDEXES keep about themselves: each registers when its
    // decode starts and unregisters when it is dropped, so it cannot be fooled by where the cache
    // chooses to update its own bookkeeping.
    assert_eq!(
        reg.peak_live_indexes(),
        DEFAULT_RESIDENT_INDEXES,
        "the most indexes ever alive at once must be exactly the cap"
    );
    assert_eq!(reg.live_indexes(), DEFAULT_RESIDENT_INDEXES);
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
            reg.peak_live_indexes(),
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
    // Under concurrency a caller may still hold the Arc of an index that has just been evicted (a
    // snapshot is the point of an `Arc`), so the live count can exceed the cap by the number of
    // such callers, never by more: six readers here. The strict statement, that decodes never run
    // beyond the free slots, is made deterministically by the gate tests below.
    assert!(
        reg.peak_live_indexes() <= DEFAULT_RESIDENT_INDEXES + 6,
        "indexes alive at once reached {} with a cap of {DEFAULT_RESIDENT_INDEXES} and 6 readers",
        reg.peak_live_indexes()
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

// =============================================================================================
// Round 2: the peak seen by the indexes themselves, slots, and decoding outside the lock
// =============================================================================================

fn catalogue_of(fixtures: &[&Fixture]) -> Catalogue {
    Catalogue::parse(&catalogue_json(
        Some("https://downloads.example.org/t/"),
        fixtures.iter().map(|f| f.entry("cleared")).collect(),
    ))
    .unwrap()
}

/// A load hook that parks every thread that reaches `stage` until the gate is opened (or a long
/// timeout passes, so a failing test cannot hang), counting arrivals.
struct Gate {
    arrived: Arc<AtomicUsize>,
    release: Arc<AtomicBool>,
}

/// Opens its gate when dropped, so a test that fails while threads are parked still lets them go.
struct OpenOnDrop(Arc<AtomicBool>);

impl Drop for OpenOnDrop {
    fn drop(&mut self) {
        self.0.store(true, Ordering::SeqCst);
    }
}

impl Gate {
    fn install(reg: &Registry, stage: LoadStage) -> Gate {
        let arrived = Arc::new(AtomicUsize::new(0));
        let release = Arc::new(AtomicBool::new(false));
        let (a, r) = (Arc::clone(&arrived), Arc::clone(&release));
        reg.set_load_hook_for_tests(Some(Arc::new(move |s: LoadStage| {
            if s == stage {
                a.fetch_add(1, Ordering::SeqCst);
                let deadline = Instant::now() + Duration::from_secs(20);
                while !r.load(Ordering::SeqCst) && Instant::now() < deadline {
                    std::thread::sleep(Duration::from_millis(2));
                }
            }
        })));
        Gate { arrived, release }
    }

    fn arrived(&self) -> usize {
        self.arrived.load(Ordering::SeqCst)
    }

    fn open(&self) {
        self.release.store(true, Ordering::SeqCst);
    }

    fn opener(&self) -> OpenOnDrop {
        OpenOnDrop(Arc::clone(&self.release))
    }

    /// Wait until `n` threads have arrived, then keep watching for a while to see whether any
    /// more do. Returns how many had arrived by then.
    fn settle(&self, n: usize) -> usize {
        let deadline = Instant::now() + Duration::from_secs(10);
        while self.arrived() < n && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(2));
        }
        std::thread::sleep(Duration::from_millis(300));
        self.arrived()
    }
}

#[test]
fn reading_in_sequence_never_has_more_than_the_cap_alive_even_for_a_moment() {
    for cap in [1usize, 2, 3] {
        let (reg, _root) = installed_registry(Some(cap));
        for c in CODES {
            read(&reg, c);
        }
        for c in CODES.iter().rev() {
            read(&reg, c);
        }
        assert_eq!(
            reg.peak_live_indexes(),
            cap,
            "cap {cap}: a decode ran while a full cache still held its indexes"
        );
        assert_eq!(reg.live_indexes(), cap, "cap {cap}");
    }
}

#[test]
fn a_file_replaced_by_another_process_is_swapped_in_without_both_copies_alive() {
    // The host holds ONE slot. Another process installs a new file for the same code. The host's
    // next read must free the old index BEFORE it decodes the new file, so the two are never
    // alive together.
    let v1 = fixture_labelled("TST", "ONE", 3, 2);
    let v2 = fixture_labelled("TST", "TWO", 4, 2);
    let root = tmp_dir("swap");
    let dir = root.join("data");
    fs::write(root.join("v1.gz"), &v1.gz).unwrap();
    fs::write(root.join("v2.gz"), &v2.gz).unwrap();
    let host = Registry::with_capacity(dir.clone(), catalogue_of(&[&v1]), 1);
    let writer = Registry::new(dir.clone(), catalogue_of(&[&v2]));
    host.install_from_file("TST", &root.join("v1.gz"), 1, &InstallHooks::default())
        .unwrap();
    assert_eq!(
        host.index(&code("TST")).unwrap()[0].text,
        verse_text("ONE", 1, 1, 1)
    );
    assert_eq!(host.live_indexes(), 1, "premise: the old index is resident");

    writer
        .install_from_file("TST", &root.join("v2.gz"), 2, &InstallHooks::default())
        .unwrap();
    assert_eq!(
        host.index(&code("TST")).unwrap()[0].text,
        verse_text("TWO", 1, 1, 1)
    );
    assert_eq!(
        host.peak_live_indexes(),
        1,
        "the replaced index was still alive while the new file was decoded"
    );
    assert_eq!(host.live_indexes(), 1);
}

#[test]
fn a_file_that_passes_its_digest_but_fails_validation_never_evicts_a_good_index() {
    let (reg, root) = installed_registry(None);
    for c in ["AAA", "BBB", "CCC"] {
        read(&reg, c);
    }
    assert_eq!(reg.resident_codes(), ["CCC", "BBB", "AAA"]);
    assert_eq!(reg.peak_live_indexes(), 3);

    // DDD's file and receipt agree on the digest (rewritten together), but the text has a
    // right-to-left override in it.
    let rlo = char::from_u32(0x202E).unwrap();
    let bad = common::gz(format!("1\t1\t1\tbefore {rlo} after\n").as_bytes());
    plant(&root.join("data"), "DDD", &bad, 1, 0);

    for _ in 0..5 {
        let err = reg.index(&code("DDD")).unwrap_err();
        assert!(
            matches!(err, LoadError::Invalid(ValidationError::Residue { .. })),
            "{err:?}"
        );
    }
    assert_eq!(
        reg.resident_codes(),
        ["CCC", "BBB", "AAA"],
        "a file that fails validation pushed a good translation out of memory"
    );
    assert_eq!(
        reg.peak_live_indexes(),
        3,
        "a file that fails validation was decoded"
    );
    assert_eq!(reg.loads_for("DDD"), 0);
}

#[test]
fn decodes_in_flight_never_exceed_the_free_slots() {
    // Four threads each want a different translation; the cache has two slots. Exactly two decodes
    // may be under way at once; the other two wait for a slot instead of decoding a third and a
    // fourth index beside them.
    let (reg, _root) = installed_registry(Some(2));
    let gate = Gate::install(&reg, LoadStage::BeforeDecode);
    std::thread::scope(|scope| {
        let _opener = gate.opener();
        let readers: Vec<_> = ["AAA", "BBB", "CCC", "DDD"]
            .into_iter()
            .map(|c| {
                let reg = &reg;
                scope.spawn(move || assert!(!reg.index(&code(c)).unwrap().is_empty()))
            })
            .collect();
        let at_gate = gate.settle(2);
        assert_eq!(
            at_gate, 2,
            "two slots, so two decodes may run at once, but {at_gate} reached their decode"
        );
        assert_eq!(reg.live_indexes(), 0, "premise: nothing is decoded yet");
        gate.open();
        for r in readers {
            r.join().unwrap();
        }
    });
    assert_eq!(gate.arrived(), 4, "every thread decoded its own file once");
    assert_eq!(reg.resident_codes().len(), 2);
}

#[test]
fn the_gate_does_let_more_threads_through_when_there_are_more_slots() {
    // Positive control for the test above: with four slots the same four threads all get to their
    // decode at once, so "two" there is the slot count and not a limit of the harness.
    let (reg, _root) = installed_registry(Some(4));
    let gate = Gate::install(&reg, LoadStage::BeforeDecode);
    std::thread::scope(|scope| {
        let _opener = gate.opener();
        let readers: Vec<_> = ["AAA", "BBB", "CCC", "DDD"]
            .into_iter()
            .map(|c| {
                let reg = &reg;
                scope.spawn(move || assert!(!reg.index(&code(c)).unwrap().is_empty()))
            })
            .collect();
        assert_eq!(gate.settle(4), 4);
        gate.open();
        for r in readers {
            r.join().unwrap();
        }
    });
}

#[test]
fn threads_reading_the_same_uncached_translation_decode_it_once() {
    let (reg, _root) = installed_registry(None);
    let gate = Gate::install(&reg, LoadStage::AfterReceipt);
    std::thread::scope(|scope| {
        let _opener = gate.opener();
        let readers: Vec<_> = (0..4)
            .map(|_| {
                let reg = &reg;
                scope.spawn(move || reg.index(&code("AAA")).unwrap().len())
            })
            .collect();
        let owners = gate.settle(1);
        assert_eq!(
            owners, 1,
            "{owners} threads set out to load the same file at once"
        );
        gate.open();
        for r in readers {
            assert_eq!(r.join().unwrap(), 5);
        }
    });
    assert_eq!(reg.loads_for("AAA"), 1, "the same file was decoded twice");
}

#[test]
fn a_resident_translation_is_served_while_another_is_being_decoded() {
    let (reg, _root) = installed_registry(None);
    read(&reg, "AAA");
    let gate = Gate::install(&reg, LoadStage::BeforeDecode);
    std::thread::scope(|scope| {
        let _opener = gate.opener();
        let loader = scope.spawn(|| reg.index(&code("CCC")).unwrap().len());
        assert_eq!(
            gate.settle(1),
            1,
            "premise: CCC's decode is parked at the gate"
        );

        // AAA is resident: neither reading it nor asking whether it is installed may wait for CCC.
        let (tx, rx) = mpsc::channel();
        let reg = &reg;
        let reader = scope.spawn(move || {
            let started = Instant::now();
            let n = reg.index(&code("AAA")).unwrap().len();
            let listed = reg.bible("AAA").is_some();
            let _ = tx.send((n, listed, started.elapsed()));
        });
        let (n, listed, took) = rx
            .recv_timeout(Duration::from_secs(5))
            .expect("a resident translation is blocked behind another one's decode");
        assert_eq!(n, 5);
        assert!(listed);
        assert!(took < Duration::from_secs(2), "took {took:?}");

        gate.open();
        reader.join().unwrap();
        assert_eq!(loader.join().unwrap(), 5);
    });
}

#[test]
fn a_load_that_panics_gives_its_slot_back() {
    // One slot. A decode that panics (here, the test hook does) must not keep the slot reserved
    // for good: the next read would wait for it forever.
    let (reg, _root) = installed_registry(Some(1));
    reg.set_load_hook_for_tests(Some(Arc::new(|s: LoadStage| {
        if s == LoadStage::BeforeDecode {
            panic!("injected failure while a slot is reserved");
        }
    })));
    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _ = reg.index(&code("AAA"));
    }));
    assert!(result.is_err(), "premise: the load panicked");
    reg.set_load_hook_for_tests(None);

    // A detached thread, not a scoped one: if the slot did leak, that thread would wait forever and
    // a scope would wait for it, hanging the test instead of failing it.
    let (tx, rx) = mpsc::channel();
    let reader = reg.clone();
    std::thread::spawn(move || {
        let _ = tx.send(reader.index(&code("BBB")).map(|i| i.len()));
    });
    let got = rx
        .recv_timeout(Duration::from_secs(5))
        .expect("the slot of a load that panicked is still reserved: the next read waits forever");
    assert_eq!(got.unwrap(), 5);
    assert_eq!(reg.resident_codes(), ["BBB"]);
}
