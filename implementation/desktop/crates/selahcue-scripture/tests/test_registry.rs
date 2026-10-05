//! Installing, storing and removing downloaded translations (`selahcue_scripture::registry`,
//! feature `installed`).
//!
//! Everything runs against a private temp directory and a catalogue built in the test: no real
//! data directory, no network. Each rejection case pins the hostile bytes in the catalogue (so the
//! SHA-256 check passes) where it is the install-time validation that must refuse them, and
//! asserts the same thing every time: nothing was installed, no receipt entry exists, and no
//! staging file is left behind.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::cell::RefCell;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::{Duration, Instant};

use common::{
    big_asset, catalogue_json, entry_pinning, fixture, fixture_labelled, gz, many_tiny_rows, plant,
    read_dir_names, replace_file, tmp_dir, verse_text, Fixture,
};
use selahcue_scripture::catalog::{Catalogue, TranslationCode};
use selahcue_scripture::registry::{
    InstallError, InstallHooks, InstalledTranslation, LoadError, LoadStage, Phase, Progress,
    ReceiptError, Registry, RECEIPT_FILE,
};
use selahcue_scripture::validate::{ValidationError, MAX_DECOMPRESSED_BYTES};
use serde_json::{json, Value};

const BASE: &str = "https://downloads.example.org/translations/";
const NOW: u64 = 1_790_000_000;

fn catalogue(entries: Vec<Value>) -> Catalogue {
    Catalogue::parse(&catalogue_json(Some(BASE), entries)).unwrap()
}

struct Env {
    dir: PathBuf,
    src: PathBuf,
    registry: Registry,
}

impl Env {
    fn new(entries: Vec<Value>) -> Env {
        let root = tmp_dir("registry");
        let dir = root.join("data");
        let src = root.join("src");
        fs::create_dir_all(&src).unwrap();
        Env {
            registry: Registry::new(dir.clone(), catalogue(entries)),
            dir,
            src,
        }
    }

    fn with(fixtures: &[&Fixture]) -> Env {
        Env::new(fixtures.iter().map(|f| f.entry("cleared")).collect())
    }

    fn source(&self, name: &str, bytes: &[u8]) -> PathBuf {
        let p = self.src.join(name);
        fs::write(&p, bytes).unwrap();
        p
    }

    fn install(
        &self,
        code: &str,
        bytes: &[u8],
        now: u64,
    ) -> Result<selahcue_scripture::registry::InstalledTranslation, InstallError> {
        let src = self.source("asset.gz", bytes);
        self.registry
            .install_from_file(code, &src, now, &InstallHooks::default())
    }

    fn names(&self) -> Vec<String> {
        read_dir_names(&self.dir)
    }

    /// The registry holds nothing: no receipt entry, no data file, no staging file.
    fn assert_nothing_installed(&self, what: &str) {
        assert_eq!(
            self.names(),
            Vec::<String>::new(),
            "{what}: the data directory must be empty after a refused install"
        );
        assert_eq!(self.registry.installed().unwrap(), vec![], "{what}");
        assert!(self.registry.bible("TST").is_none(), "{what}");
    }
}

fn code(s: &str) -> TranslationCode {
    TranslationCode::parse(s).unwrap()
}

/// Text rows joined and gzipped.
fn rows_gz(lines: &[&str]) -> Vec<u8> {
    let mut text = lines.join("\n");
    text.push('\n');
    gz(text.as_bytes())
}

#[test]
fn installing_stores_the_file_and_an_atomic_receipt() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let rec = env.install("TST", &f.gz, NOW).unwrap();

    assert_eq!(rec.code.as_str(), "TST");
    assert_eq!(rec.file_name, "tst.tsv.gz");
    assert_eq!(rec.sha256, f.sha256);
    assert_eq!(rec.size_bytes, f.gz.len() as u64);
    assert_eq!(
        rec.installed_at, NOW,
        "installed_at is the injected clock value"
    );
    assert_eq!(rec.catalogue_schema, 1);

    // Exactly the data file and the receipt: no `.part`, no temp receipt.
    assert_eq!(env.names(), ["installed.json", "tst.tsv.gz"]);
    assert_eq!(fs::read(env.dir.join("tst.tsv.gz")).unwrap(), f.gz);
    assert_eq!(env.registry.installed().unwrap(), vec![rec.clone()]);

    // The receipt on disk carries the fields the brief names.
    assert_eq!(RECEIPT_FILE, "installed.json");
    let receipt: Value =
        serde_json::from_slice(&fs::read(env.dir.join(RECEIPT_FILE)).unwrap()).unwrap();
    assert_eq!(receipt["schema"], 1);
    let e = &receipt["translations"][0];
    assert_eq!(e["code"], "TST");
    assert_eq!(e["sha256"], f.sha256.as_str());
    assert_eq!(e["size_bytes"], f.gz.len());
    assert_eq!(e["installed_at"], NOW);
    assert_eq!(e["catalogue_schema"], 1);
    // The verse counts are recorded, so a later load can bound the rows it reads by them.
    assert_eq!(e["verses_ot"], 3);
    assert_eq!(e["verses_nt"], 2);
    assert_eq!((rec.verses_ot, rec.verses_nt), (3, 2));

    // The text is served.
    let index = env.registry.index(&code("TST")).unwrap();
    assert_eq!(index.len(), 5);
    assert_eq!(index[0].text, verse_text("TST", 1, 1, 1));
}

#[test]
fn the_code_is_matched_case_insensitively_and_unknown_codes_are_refused() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    assert!(env.install("tst", &f.gz, NOW).is_ok());
    let err = env.install("NOPE", &f.gz, NOW).unwrap_err();
    assert!(
        matches!(err, InstallError::UnknownCode { ref code } if code == "NOPE"),
        "{err:?}"
    );
    // A bundled code is never in the catalogue.
    let err = env.install("KJV", &f.gz, NOW).unwrap_err();
    assert!(matches!(err, InstallError::UnknownCode { .. }), "{err:?}");
}

#[test]
fn installing_twice_with_a_new_clock_value_updates_the_receipt_and_keeps_one_entry() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    let again = env.install("TST", &f.gz, NOW + 60).unwrap();
    assert_eq!(again.installed_at, NOW + 60);
    assert_eq!(env.registry.installed().unwrap(), vec![again]);
    assert_eq!(env.names(), ["installed.json", "tst.tsv.gz"]);
}

#[test]
fn several_translations_are_listed_in_code_order_and_do_not_disturb_each_other() {
    let (a, b, c) = (
        fixture("AAA", 2, 1),
        fixture("BBB", 3, 2),
        fixture("CCC", 1, 1),
    );
    let env = Env::with(&[&c, &a, &b]);
    for f in [&c, &a, &b] {
        env.install(&f.code, &f.gz, NOW).unwrap();
    }
    let codes: Vec<String> = env
        .registry
        .installed()
        .unwrap()
        .iter()
        .map(|r| r.code.to_string())
        .collect();
    assert_eq!(codes, ["AAA", "BBB", "CCC"]);
    assert_eq!(
        env.names(),
        ["aaa.tsv.gz", "bbb.tsv.gz", "ccc.tsv.gz", "installed.json"]
    );
}

// ---- progress and cancel --------------------------------------------------------------------

#[test]
fn progress_reports_download_then_verifying_then_installing() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let seen: RefCell<Vec<Progress>> = RefCell::new(Vec::new());
    let cb = |p: Progress| seen.borrow_mut().push(p);
    let src = env.source("asset.gz", &f.gz);
    env.registry
        .install_from_file(
            "TST",
            &src,
            NOW,
            &InstallHooks::default().with_progress(&cb),
        )
        .unwrap();

    let seen = seen.into_inner();
    let total = f.gz.len() as u64;
    let phases: Vec<Phase> = seen.iter().map(|p| p.phase).collect();
    assert!(!phases.is_empty(), "no progress was reported at all");
    // Order: every Downloading before the one Verifying before the one Installing.
    let first_verify = phases.iter().position(|p| *p == Phase::Verifying).unwrap();
    let first_install = phases.iter().position(|p| *p == Phase::Installing).unwrap();
    assert!(phases[..first_verify]
        .iter()
        .all(|p| *p == Phase::Downloading));
    assert!(first_verify < first_install);
    assert_eq!(phases.iter().filter(|p| **p == Phase::Verifying).count(), 1);
    assert_eq!(
        phases.iter().filter(|p| **p == Phase::Installing).count(),
        1
    );
    // Bytes only go up, `total` is the pinned size, and the transfer ends at it.
    let downloads: Vec<&Progress> = seen
        .iter()
        .filter(|p| p.phase == Phase::Downloading)
        .collect();
    assert!(downloads.windows(2).all(|w| w[0].done <= w[1].done));
    assert!(downloads.iter().all(|p| p.total == total));
    assert_eq!(downloads.last().unwrap().done, total);
}

#[test]
fn cancel_stops_the_install_and_leaves_nothing_behind() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let cancel = AtomicBool::new(false);
    // Cancel from inside the progress callback, i.e. while the transfer is running.
    let cb = |p: Progress| {
        if p.phase == Phase::Downloading {
            cancel.store(true, Ordering::Relaxed);
        }
    };
    let src = env.source("asset.gz", &f.gz);
    let hooks = InstallHooks::default()
        .with_cancel(&cancel)
        .with_progress(&cb);
    let err = env
        .registry
        .install_from_file("TST", &src, NOW, &hooks)
        .unwrap_err();
    assert!(matches!(err, InstallError::Cancelled), "{err:?}");
    env.assert_nothing_installed("cancelled mid-transfer");

    // Positive control: the same call without the flag installs, so "cancelled" was the flag.
    let ok = env
        .registry
        .install_from_file("TST", &src, NOW, &InstallHooks::default());
    assert!(ok.is_ok());
}

#[test]
fn a_flag_already_set_cancels_before_anything_is_written() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let cancel = AtomicBool::new(true);
    let src = env.source("asset.gz", &f.gz);
    let hooks = InstallHooks::default().with_cancel(&cancel);
    let err = env
        .registry
        .install_from_file("TST", &src, NOW, &hooks)
        .unwrap_err();
    assert!(matches!(err, InstallError::Cancelled), "{err:?}");
    env.assert_nothing_installed("cancelled before starting");
}

/// A source that serves some bytes and then fails, like a dropped connection.
struct DropsAfter {
    data: Vec<u8>,
    pos: usize,
    fail_at: usize,
}

impl Read for DropsAfter {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.pos >= self.fail_at {
            return Err(std::io::Error::new(
                std::io::ErrorKind::ConnectionReset,
                "connection reset",
            ));
        }
        let end = self.data.len().min(self.fail_at);
        let n = buf.len().min(end - self.pos);
        buf[..n].copy_from_slice(&self.data[self.pos..self.pos + n]);
        self.pos += n;
        Ok(n)
    }
}

#[test]
fn a_transfer_that_dies_halfway_leaves_no_partial_install() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let mut source = DropsAfter {
        data: f.gz.clone(),
        pos: 0,
        fail_at: f.gz.len() / 2,
    };
    let err = env
        .registry
        .install_from_reader("TST", &mut source, NOW, &InstallHooks::default())
        .unwrap_err();
    assert!(matches!(err, InstallError::Source(_)), "{err:?}");
    env.assert_nothing_installed("source failed halfway");
}

// ---- rejections: each leaves nothing installed -----------------------------------------------

#[test]
fn a_file_whose_digest_is_wrong_is_rejected() {
    let f = fixture("TST", 3, 2);
    // Same length, one byte flipped: only the digest can tell.
    let mut flipped = f.gz.clone();
    flipped[12] ^= 0xFF;
    let env = Env::with(&[&f]);
    let err = env.install("TST", &flipped, NOW).unwrap_err();
    match err {
        InstallError::Verify { expected, actual } => {
            assert_eq!(expected, f.sha256);
            assert_ne!(actual, f.sha256);
        }
        other => panic!("expected a digest failure, got {other:?}"),
    }
    env.assert_nothing_installed("wrong digest");
}

#[test]
fn a_substituted_file_is_rejected() {
    // A perfectly valid translation, but not the one the catalogue pinned for this code.
    let pinned = fixture("TST", 3, 2);
    let other = fixture_labelled("TST", "OTHER", 3, 2);
    let env = Env::with(&[&pinned]);
    let err = env.install("TST", &other.gz, NOW).unwrap_err();
    assert!(
        matches!(
            err,
            InstallError::Verify { .. } | InstallError::TooLarge { .. }
        ),
        "{err:?}"
    );
    env.assert_nothing_installed("substituted file");
}

#[test]
fn a_truncated_file_is_rejected() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let truncated = &f.gz[..f.gz.len() - 20];
    let err = env.install("TST", truncated, NOW).unwrap_err();
    assert!(matches!(err, InstallError::Verify { .. }), "{err:?}");
    env.assert_nothing_installed("truncated file");

    // And one the catalogue itself pinned (so its digest passes): the gzip stream is incomplete.
    let env = Env::new(vec![entry_pinning("TST", truncated, 3, 2)]);
    let err = env.install("TST", truncated, NOW).unwrap_err();
    assert!(
        matches!(err, InstallError::Invalid(ValidationError::Decode(_))),
        "{err:?}"
    );
    env.assert_nothing_installed("truncated file with a matching digest");
}

#[test]
fn an_oversized_file_is_rejected_at_the_pinned_size() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let mut bigger = f.gz.clone();
    bigger.extend_from_slice(&[0u8; 4096]);
    let err = env.install("TST", &bigger, NOW).unwrap_err();
    assert!(
        matches!(err, InstallError::TooLarge { limit } if limit == f.gz.len() as u64),
        "{err:?}"
    );
    env.assert_nothing_installed("oversized file");
}

#[test]
fn a_decompression_bomb_the_catalogue_vouches_for_is_rejected() {
    // The digest is right (the catalogue pins these exact bytes), so only install-time validation
    // can stop it: 17.6 MB inflated from a few tens of kilobytes (the cap is 16 MiB).
    let bomb = big_asset(1_100);
    assert!(bomb.len() < 1024 * 1024);
    let env = Env::new(vec![entry_pinning("TST", &bomb, 1_100, 0)]);
    let err = env.install("TST", &bomb, NOW).unwrap_err();
    assert!(
        matches!(
            err,
            InstallError::Invalid(ValidationError::TooLarge { limit }) if limit == MAX_DECOMPRESSED_BYTES
        ),
        "{err:?}"
    );
    env.assert_nothing_installed("decompression bomb");
}

#[test]
fn files_that_are_not_shaped_like_a_bible_are_rejected_even_when_the_digest_matches() {
    let pilcrow = char::from_u32(0xB6).unwrap();
    let marked = format!("1\t1\t1\tbefore {pilcrow} after");
    let rlo = char::from_u32(0x202E).unwrap();
    let overridden = format!("1\t1\t1\tbefore {rlo} after");
    let mut two_members = rows_gz(&["1\t1\t1\tone"]);
    two_members.extend(rows_gz(&["1\t1\t2\ttwo"]));
    // (what, the bytes, OT count, NT count, the validation error it must reach)
    let cases: Vec<(&str, Vec<u8>, u32, u32, &str)> = vec![
        (
            "a second gzip member behind the first",
            two_members,
            1,
            0,
            "TrailingData",
        ),
        (
            "a right-to-left override in the text",
            rows_gz(&[overridden.as_str()]),
            1,
            0,
            "Residue { line: 1",
        ),
        (
            "far more rows than the verse counts allow",
            many_tiny_rows(262_140),
            3,
            2,
            "TooManyRows { limit: 5 }",
        ),
        (
            "a verse count that differs from the catalogue",
            rows_gz(&["1\t1\t1\tone", "1\t1\t2\ttwo"]),
            3,
            0,
            "VerseCount",
        ),
        (
            "a bracket in the text",
            rows_gz(&["1\t1\t1\tone [two] three"]),
            1,
            0,
            "Residue { line: 1, character: '[' }",
        ),
        (
            "a pilcrow in the text",
            rows_gz(&[marked.as_str()]),
            1,
            0,
            "Residue { line: 1",
        ),
        (
            "an asterisk in the text",
            rows_gz(&["1\t1\t1\tone*"]),
            1,
            0,
            "Residue { line: 1, character: '*' }",
        ),
        (
            "a book past Revelation",
            rows_gz(&["1\t1\t1\tone", "67\t1\t1\ttwo"]),
            1,
            1,
            "BookOutOfRange { line: 2, book: 67 }",
        ),
        (
            "rows out of order",
            rows_gz(&["1\t1\t2\tone", "1\t1\t1\ttwo"]),
            2,
            0,
            "NotAscending { line: 2 }",
        ),
        (
            "a row that is not a verse",
            rows_gz(&["1\t1\t1\tone", "garbage"]),
            2,
            0,
            "BadRow { line: 2 }",
        ),
    ];
    for (what, bytes, ot, nt, expect) in cases {
        let env = Env::new(vec![entry_pinning("TST", &bytes, ot, nt)]);
        let err = env.install("TST", &bytes, NOW).unwrap_err();
        match &err {
            InstallError::Invalid(v) => {
                let shown = format!("{v:?}");
                assert!(
                    shown.starts_with(expect),
                    "{what}: expected {expect}, got {shown}"
                );
            }
            other => panic!("{what}: expected a validation error, got {other:?}"),
        }
        env.assert_nothing_installed(what);
    }

    // Positive control: the same shape with clean text and the right counts installs.
    let clean = rows_gz(&["1\t1\t1\tone", "1\t1\t2\ttwo"]);
    let env = Env::new(vec![entry_pinning("TST", &clean, 2, 0)]);
    assert!(env.install("TST", &clean, NOW).is_ok());
}

#[test]
fn a_refused_reinstall_leaves_the_existing_install_exactly_as_it_was() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let first = env.install("TST", &f.gz, NOW).unwrap();
    let before = (
        env.names(),
        fs::read(env.dir.join("tst.tsv.gz")).unwrap(),
        fs::read(env.dir.join(RECEIPT_FILE)).unwrap(),
    );

    let mut flipped = f.gz.clone();
    flipped[12] ^= 0xFF;
    let err = env.install("TST", &flipped, NOW + 1).unwrap_err();
    assert!(matches!(err, InstallError::Verify { .. }), "{err:?}");

    let after = (
        env.names(),
        fs::read(env.dir.join("tst.tsv.gz")).unwrap(),
        fs::read(env.dir.join(RECEIPT_FILE)).unwrap(),
    );
    assert_eq!(
        before, after,
        "a refused install changed what was installed"
    );
    assert_eq!(env.registry.installed().unwrap(), vec![first]);
    assert_eq!(env.registry.index(&code("TST")).unwrap().len(), 5);
}

// ---- removal ----------------------------------------------------------------------------------

#[test]
fn removing_deletes_the_file_and_the_receipt_entry_and_nothing_else() {
    let (a, b) = (fixture("AAA", 2, 1), fixture("BBB", 3, 2));
    let env = Env::with(&[&a, &b]);
    env.install("AAA", &a.gz, NOW).unwrap();
    env.install("BBB", &b.gz, NOW).unwrap();
    env.registry.index(&code("AAA")).unwrap(); // make it resident

    assert!(env.registry.remove("AAA").unwrap());
    assert_eq!(env.names(), ["bbb.tsv.gz", "installed.json"]);
    let left: Vec<String> = env
        .registry
        .installed()
        .unwrap()
        .iter()
        .map(|r| r.code.to_string())
        .collect();
    assert_eq!(left, ["BBB"]);
    assert!(
        !env.registry.resident_codes().contains(&"AAA".to_string()),
        "a removed translation must not stay resident in memory"
    );
    assert!(matches!(
        env.registry.index(&code("AAA")),
        Err(LoadError::NotInstalled)
    ));
    assert!(env.registry.bible("AAA").is_none());

    // Removing it again, or removing something never installed, is a harmless `false`.
    assert!(!env.registry.remove("AAA").unwrap());
    assert!(!env.registry.remove("ZZZ").unwrap());
    // The other translation is untouched.
    assert_eq!(env.registry.index(&code("BBB")).unwrap().len(), 5);
}

#[test]
fn a_removed_translation_can_be_installed_again_and_is_served_fresh() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    env.registry.index(&code("TST")).unwrap();
    assert_eq!(env.registry.loads_for("TST"), 1);
    env.registry.remove("TST").unwrap();
    env.install("TST", &f.gz, NOW + 5).unwrap();
    env.registry.index(&code("TST")).unwrap();
    assert_eq!(
        env.registry.loads_for("TST"),
        2,
        "the second install must be decoded from its own file, not served from the old cache"
    );
}

// ---- re-download -------------------------------------------------------------------------------

#[test]
fn a_reinstalled_translation_is_served_from_the_new_file_without_a_restart() {
    // Two processes, one data directory: `host` is a long-running reader that has already decoded
    // the translation; `operator` installs a NEW file for the same code (a new catalogue pin, as a
    // release would carry). The host must serve the new text on its next read.
    let v1 = fixture_labelled("TST", "ONE", 3, 2);
    let v2 = fixture_labelled("TST", "TWO", 4, 2);
    let root = tmp_dir("redownload");
    let dir = root.join("data");
    let host = Registry::new(dir.clone(), catalogue(vec![v1.entry("cleared")]));
    let op1 = Registry::new(dir.clone(), catalogue(vec![v1.entry("cleared")]));
    fs::write(root.join("v1.gz"), &v1.gz).unwrap();
    fs::write(root.join("v2.gz"), &v2.gz).unwrap();
    op1.install_from_file("TST", &root.join("v1.gz"), NOW, &InstallHooks::default())
        .unwrap();

    let first = host.index(&code("TST")).unwrap();
    assert_eq!(first[0].text, verse_text("ONE", 1, 1, 1));
    // Premise for the check below: a second read is a cache HIT, so the change that follows has to
    // invalidate a live entry, not merely find an empty one.
    host.index(&code("TST")).unwrap();
    assert_eq!(
        host.loads_for("TST"),
        1,
        "the second read must come from memory"
    );
    assert_eq!(
        host.resident_hits_for("TST"),
        Some(1),
        "the cache hit was not exercised, so the replacement below would prove nothing"
    );

    let op2 = Registry::new(dir.clone(), catalogue(vec![v2.entry("cleared")]));
    op2.install_from_file(
        "TST",
        &root.join("v2.gz"),
        NOW + 100,
        &InstallHooks::default(),
    )
    .unwrap();

    let second = host.index(&code("TST")).unwrap();
    assert_eq!(second.len(), 6, "the host must see the new file's verses");
    assert_eq!(second[0].text, verse_text("TWO", 1, 1, 1));
    assert_eq!(host.loads_for("TST"), 2);
    assert_eq!(
        host.resident_codes(),
        ["TST"],
        "the replaced index must not stay resident beside the new one"
    );
    // The old Arc a caller still holds keeps working (it is a snapshot), and is the OLD text.
    assert_eq!(first[0].text, verse_text("ONE", 1, 1, 1));
}

// ---- interrupted installs, planted files ------------------------------------------------------

#[test]
fn an_interrupted_install_is_cleaned_up_and_never_counted_as_installed() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    fs::create_dir_all(&env.dir).unwrap();
    // What a crash mid-download leaves: a partial staging file and a half-written temp receipt.
    fs::write(env.dir.join("tst.tsv.gz.part"), &f.gz[..10]).unwrap();
    fs::write(env.dir.join("tst.tsv.gz.1.part"), &f.gz[..20]).unwrap();
    fs::write(
        env.dir.join(".installed.json.tmp"),
        b"{\"schema\":1,\"transl",
    )
    .unwrap();
    // Real, unrelated files in the same folder, including ones that merely look like staging files.
    for mine in [
        "notes.txt",
        "movie.mp4.part",
        "other.part",
        "x.tmp",
        ".installed.json.bak",
    ] {
        fs::write(env.dir.join(mine), b"mine").unwrap();
    }

    // Never counted as installed, with or without cleanup.
    assert_eq!(env.registry.installed().unwrap(), vec![]);
    assert!(env.registry.bible("TST").is_none());

    let report = env.registry.recover().unwrap();
    assert_eq!(report.removed, 3);
    assert_eq!(report.skipped, 0);
    assert_eq!(
        env.names(),
        [
            ".installed.json.bak",
            "movie.mp4.part",
            "notes.txt",
            "other.part",
            "x.tmp"
        ],
        "only the files this module stages are removed, never a user's own"
    );
    assert_eq!(env.registry.installed().unwrap(), vec![]);

    // And a real install after a crash works and cleans leftovers itself.
    fs::write(env.dir.join("tst.tsv.gz.part"), &f.gz[..10]).unwrap();
    env.install("TST", &f.gz, NOW).unwrap();
    assert_eq!(
        env.names(),
        [
            ".installed.json.bak",
            "installed.json",
            "movie.mp4.part",
            "notes.txt",
            "other.part",
            "tst.tsv.gz",
            "x.tmp"
        ]
    );
}

#[cfg(unix)]
#[test]
fn a_planted_symlink_is_never_followed_and_a_file_this_call_did_not_create_is_never_removed() {
    use std::os::unix::fs::symlink;

    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    fs::create_dir_all(&env.dir).unwrap();
    let victim = env.dir.parent().unwrap().join("victim.txt");
    fs::write(&victim, b"precious").unwrap();

    // 1. A symlink sitting where the first staging file would go.
    symlink(&victim, env.dir.join("tst.tsv.gz.part")).unwrap();
    // 2. A symlink where the data file will be installed.
    symlink(&victim, env.dir.join("tst.tsv.gz")).unwrap();

    // Cleanup does not follow it, and does not delete it either.
    let report = env.registry.recover().unwrap();
    assert_eq!((report.removed, report.skipped), (0, 1));
    assert!(fs::symlink_metadata(env.dir.join("tst.tsv.gz.part"))
        .unwrap()
        .is_symlink());

    // Installing does not write through either link.
    env.install("TST", &f.gz, NOW).unwrap();
    assert_eq!(
        fs::read(&victim).unwrap(),
        b"precious",
        "the symlink target was written through"
    );
    let installed = env.dir.join("tst.tsv.gz");
    assert!(
        !fs::symlink_metadata(&installed).unwrap().is_symlink(),
        "the installed file must be a regular file, not the planted link"
    );
    assert_eq!(fs::read(&installed).unwrap(), f.gz);
    assert!(
        fs::symlink_metadata(env.dir.join("tst.tsv.gz.part"))
            .unwrap()
            .is_symlink(),
        "a file this call did not create must still be there"
    );
    assert_eq!(fs::read(&victim).unwrap(), b"precious");
}

#[cfg(unix)]
#[test]
fn a_receipt_that_is_a_symlink_is_not_read_and_is_replaced_not_written_through() {
    use std::os::unix::fs::symlink;

    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    // Replace the receipt by a link to a copy that would be a perfectly valid receipt.
    let real = fs::read(env.dir.join(RECEIPT_FILE)).unwrap();
    let elsewhere = env.dir.parent().unwrap().join("elsewhere.json");
    fs::write(&elsewhere, &real).unwrap();
    fs::remove_file(env.dir.join(RECEIPT_FILE)).unwrap();
    symlink(&elsewhere, env.dir.join(RECEIPT_FILE)).unwrap();

    let err = env.registry.installed().unwrap_err();
    assert!(matches!(err, ReceiptError::Corrupt(_)), "{err:?}");
    assert!(env.registry.bible("TST").is_none());

    // Installing refuses to run over it (it cannot tell what else was installed)...
    let err = env.install("TST", &f.gz, NOW + 1).unwrap_err();
    assert!(
        matches!(err, InstallError::Receipt(ReceiptError::Corrupt(_))),
        "{err:?}"
    );
    assert!(fs::symlink_metadata(env.dir.join(RECEIPT_FILE))
        .unwrap()
        .is_symlink());
    // ...and repairing it replaces the link by a regular file; the target is not written through.
    let rebuilt = env.registry.repair_receipt(NOW + 2).unwrap();
    assert_eq!(rebuilt.len(), 1);
    assert_eq!(
        fs::read(&elsewhere).unwrap(),
        real,
        "written through the receipt symlink"
    );
    assert!(!fs::symlink_metadata(env.dir.join(RECEIPT_FILE))
        .unwrap()
        .is_symlink());
    assert_eq!(env.registry.installed().unwrap().len(), 1);
}

#[cfg(unix)]
#[test]
fn an_installed_file_swapped_for_a_symlink_is_not_read() {
    use std::os::unix::fs::symlink;

    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    // A link to a copy with the SAME bytes: the digest would pass, so only the link check refuses.
    let copy = env.dir.parent().unwrap().join("copy.gz");
    fs::write(&copy, &f.gz).unwrap();
    fs::remove_file(env.dir.join("tst.tsv.gz")).unwrap();
    symlink(&copy, env.dir.join("tst.tsv.gz")).unwrap();

    assert!(matches!(
        env.registry.index(&code("TST")),
        Err(LoadError::Missing)
    ));
    assert_eq!(
        env.registry.installed().unwrap(),
        vec![],
        "a linked file is not an install"
    );
}

// ---- receipts and damaged installs ------------------------------------------------------------

#[test]
fn a_receipt_that_is_not_trustworthy_is_reported_not_used() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    let good: Value =
        serde_json::from_slice(&fs::read(env.dir.join(RECEIPT_FILE)).unwrap()).unwrap();
    let entry = good["translations"][0].clone();

    let tamper = |mutate: &dyn Fn(&mut Value)| -> Vec<u8> {
        let mut doc = good.clone();
        mutate(&mut doc);
        doc.to_string().into_bytes()
    };
    let cases: Vec<(&str, Vec<u8>)> = vec![
        ("garbage", b"{not json".to_vec()),
        ("an empty file", Vec::new()),
        ("an unknown schema", tamper(&|d| d["schema"] = json!(2))),
        (
            "a path-traversal file name",
            tamper(&|d| d["translations"][0]["file_name"] = json!("../evil.tsv.gz")),
        ),
        (
            "a file name with a directory",
            tamper(&|d| d["translations"][0]["file_name"] = json!("sub/tst.tsv.gz")),
        ),
        (
            "an upper-case digest",
            tamper(&|d| d["translations"][0]["sha256"] = json!(f.sha256.to_uppercase())),
        ),
        (
            "a bundled code",
            tamper(&|d| d["translations"][0]["code"] = json!("KJV")),
        ),
        (
            "a duplicated code",
            tamper(&|d| d["translations"] = json!([entry.clone(), entry.clone()])),
        ),
        (
            "a size of zero",
            tamper(&|d| d["translations"][0]["size_bytes"] = json!(0)),
        ),
        (
            "a negative time",
            tamper(&|d| d["translations"][0]["installed_at"] = json!(-1)),
        ),
        (
            "no verse counts at all",
            tamper(&|d| {
                d["translations"][0]
                    .as_object_mut()
                    .unwrap()
                    .remove("verses_ot");
            }),
        ),
        (
            "verse counts that are both zero",
            tamper(&|d| {
                d["translations"][0]["verses_ot"] = json!(0);
                d["translations"][0]["verses_nt"] = json!(0);
            }),
        ),
        (
            "a verse count past the largest a testament can have",
            tamper(&|d| d["translations"][0]["verses_nt"] = json!(100_001)),
        ),
        // Valid JSON in every way except that it is far larger than any receipt can be: only the
        // size cap can refuse it (a receipt that is merely garbage is refused by the parser).
        ("a valid receipt past the size cap", {
            let mut padded = good.to_string().into_bytes();
            padded.extend(vec![b' '; 300 * 1024]);
            padded
        }),
    ];
    let fresh = || Registry::new(env.dir.clone(), env.registry.catalogue().clone());
    for (what, bytes) in cases {
        replace_file(&env.dir.join(RECEIPT_FILE), &bytes);
        let err = env.registry.installed().unwrap_err();
        assert!(matches!(err, ReceiptError::Corrupt(_)), "{what}: {err:?}");
        assert!(
            fresh().bible("TST").is_none(),
            "{what}: served from a bad receipt"
        );
    }

    // Positive control: the unmodified receipt is read.
    replace_file(&env.dir.join(RECEIPT_FILE), good.to_string().as_bytes());
    assert_eq!(env.registry.installed().unwrap().len(), 1);
    assert!(fresh().bible("TST").is_some());
}

#[test]
fn a_receipt_whose_file_is_gone_is_not_an_install() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    fs::remove_file(env.dir.join("tst.tsv.gz")).unwrap();
    assert_eq!(env.registry.installed().unwrap(), vec![]);
    assert!(env.registry.bible("TST").is_none());
    assert!(matches!(
        env.registry.index(&code("TST")),
        Err(LoadError::Missing)
    ));
}

#[test]
fn an_installed_file_damaged_in_place_is_refused_on_read_and_repaired_by_installing_again() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();

    // Same length, one byte changed: the receipt's digest no longer matches the file.
    let path = env.dir.join("tst.tsv.gz");
    let mut bytes = fs::read(&path).unwrap();
    bytes[12] ^= 0xFF;
    fs::write(&path, &bytes).unwrap();
    let err = env.registry.index(&code("TST")).unwrap_err();
    assert!(matches!(err, LoadError::Mismatch { .. }), "{err:?}");
    assert!(
        env.registry.resident_codes().is_empty(),
        "a damaged file must not be cached"
    );

    env.install("TST", &f.gz, NOW + 1).unwrap();
    assert_eq!(env.registry.index(&code("TST")).unwrap().len(), 5);

    // The text already in memory was verified when it was read, so damage to the file afterwards
    // does not change what this process serves...
    fs::write(&path, b"short").unwrap();
    assert_eq!(env.registry.index(&code("TST")).unwrap().len(), 5);
    // ...but a fresh reader (another process, or this one after a restart) refuses the file: it is
    // not the size the receipt records, so it is not listed, and reading it fails.
    let fresh = Registry::new(env.dir.clone(), env.registry.catalogue().clone());
    assert_eq!(fresh.installed().unwrap(), vec![]);
    let err = fresh.index(&code("TST")).unwrap_err();
    assert!(matches!(err, LoadError::Mismatch { .. }), "{err:?}");
}

#[test]
fn the_data_directory_is_created_on_first_install_and_not_before() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    assert!(
        !env.dir.exists(),
        "constructing a registry must not touch the disk"
    );
    assert_eq!(env.registry.installed().unwrap(), vec![]);
    assert!(!env.dir.exists(), "reading must not create the directory");
    assert!(env.registry.recover().is_ok());
    assert!(
        !env.dir.exists(),
        "cleanup of a missing directory must not create it"
    );
    env.install("TST", &f.gz, NOW).unwrap();
    assert!(env.dir.is_dir());
}

#[test]
fn install_from_a_path_that_is_not_a_regular_file_is_refused() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let err = env
        .registry
        .install_from_file(
            "TST",
            Path::new("/definitely/not/here.gz"),
            NOW,
            &InstallHooks::default(),
        )
        .unwrap_err();
    assert!(matches!(err, InstallError::Source(_)), "{err:?}");
    let err = env
        .registry
        .install_from_file("TST", &env.src, NOW, &InstallHooks::default())
        .unwrap_err();
    assert!(matches!(err, InstallError::Source(_)), "{err:?}");
    env.assert_nothing_installed("bad source path");
}

#[test]
fn installing_over_an_older_file_that_is_resident_frees_it_at_once() {
    // A registry that has decoded the OLDER file (installed by another process, under an earlier
    // catalogue pin) and then installs the NEW one itself must drop the older index immediately,
    // not whenever the next read happens to prune it: it is 5 to 6 MB that nothing will ever serve.
    let old = fixture_labelled("TST", "OLD", 3, 2);
    let new = fixture_labelled("TST", "NEW", 4, 2);
    let root = tmp_dir("free-at-once");
    let dir = root.join("data");
    fs::write(root.join("old.gz"), &old.gz).unwrap();
    fs::write(root.join("new.gz"), &new.gz).unwrap();
    let earlier = Registry::new(dir.clone(), catalogue(vec![old.entry("cleared")]));
    earlier
        .install_from_file("TST", &root.join("old.gz"), NOW, &InstallHooks::default())
        .unwrap();

    let reg = Registry::new(dir.clone(), catalogue(vec![new.entry("cleared")]));
    assert_eq!(
        reg.index(&code("TST")).unwrap()[0].text,
        verse_text("OLD", 1, 1, 1)
    );
    assert_eq!(
        reg.resident_codes(),
        ["TST"],
        "premise: the older file is resident"
    );

    reg.install_from_file(
        "TST",
        &root.join("new.gz"),
        NOW + 1,
        &InstallHooks::default(),
    )
    .unwrap();
    assert_eq!(
        reg.resident_codes(),
        Vec::<String>::new(),
        "the replaced index must be dropped by the install that replaced it"
    );
    // Observed by the index itself, not by the cache: it is really gone from memory.
    assert_eq!(
        reg.live_indexes(),
        0,
        "the replaced index is still alive after the install that replaced it"
    );
    assert_eq!(
        reg.index(&code("TST")).unwrap()[0].text,
        verse_text("NEW", 1, 1, 1)
    );
}

/// A source that is interrupted (a signal during a read) once before every real chunk.
struct Interrupted<'a> {
    inner: &'a [u8],
    pending_interrupt: bool,
}

impl Read for Interrupted<'_> {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.pending_interrupt {
            self.pending_interrupt = false;
            return Err(std::io::Error::from(std::io::ErrorKind::Interrupted));
        }
        self.pending_interrupt = true;
        self.inner.read(buf)
    }
}

#[test]
fn an_interrupted_read_is_retried_not_treated_as_the_end_of_the_file() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let mut source = Interrupted {
        inner: &f.gz,
        pending_interrupt: true,
    };
    env.registry
        .install_from_reader("TST", &mut source, NOW, &InstallHooks::default())
        .expect("EINTR on a read is not a failure");
    assert_eq!(env.registry.index(&code("TST")).unwrap().len(), 5);
}

#[test]
fn a_first_install_whose_receipt_cannot_be_written_leaves_no_orphan_file() {
    // A DIRECTORY appears where the receipt goes while the install is underway (planted from the
    // progress callback that reports the final step): the data file is renamed into place, then the
    // receipt rename fails. Nothing was installed before, so the data file would be an orphan with
    // no receipt; it must be taken back out, and no staging or temp file may remain. (A directory
    // there from the start is refused up front instead; see the test for an unreadable receipt.)
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let planted = env.dir.join(RECEIPT_FILE);
    let plant_dir = |p: Progress| {
        if p.phase == Phase::Installing {
            fs::create_dir_all(&planted).unwrap();
        }
    };
    let src = env.source("asset.gz", &f.gz);
    let err = env
        .registry
        .install_from_file(
            "TST",
            &src,
            NOW,
            &InstallHooks::default().with_progress(&plant_dir),
        )
        .unwrap_err();
    assert!(matches!(err, InstallError::Io(_)), "{err:?}");
    assert_eq!(
        env.names(),
        ["installed.json"],
        "only the planted directory may remain: no orphan data file, no .part, no temp receipt"
    );
}

// =============================================================================================
// Round 2
// =============================================================================================

fn installed_codes(registry: &Registry) -> Vec<String> {
    registry
        .installed()
        .unwrap()
        .iter()
        .map(|r| r.code.to_string())
        .collect()
}

/// A source that counts how often it is read.
struct Counting<'a> {
    inner: &'a [u8],
    reads: &'a AtomicUsize,
}

impl Read for Counting<'_> {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        self.reads.fetch_add(1, Ordering::SeqCst);
        self.inner.read(buf)
    }
}

/// A source that serves its first half, then blocks until released (a stalled download), then
/// serves the rest. Dropping the release sender also releases it, so a failing test never leaves a
/// thread blocked for good.
struct Stalls {
    data: Vec<u8>,
    pos: usize,
    stalled: bool,
    started: mpsc::Sender<()>,
    release: mpsc::Receiver<()>,
}

impl Stalls {
    fn new(data: Vec<u8>, started: mpsc::Sender<()>, release: mpsc::Receiver<()>) -> Stalls {
        Stalls {
            data,
            pos: 0,
            stalled: false,
            started,
            release,
        }
    }
}

impl Read for Stalls {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        let half = self.data.len() / 2;
        if self.pos >= half && !self.stalled {
            self.stalled = true;
            let _ = self.started.send(());
            let _ = self.release.recv();
        }
        let end = if self.stalled { self.data.len() } else { half };
        let n = buf.len().min(end - self.pos);
        buf[..n].copy_from_slice(&self.data[self.pos..self.pos + n]);
        self.pos += n;
        Ok(n)
    }
}

// ---- an unreadable receipt (A4) --------------------------------------------------------------

#[test]
fn an_unreadable_receipt_never_makes_install_or_remove_forget_the_other_translations() {
    let (a, b, c) = (
        fixture("AAA", 2, 1),
        fixture("BBB", 3, 2),
        fixture("CCC", 1, 1),
    );
    let env = Env::with(&[&a, &b, &c]);
    env.install("AAA", &a.gz, NOW).unwrap();
    env.install("BBB", &b.gz, NOW).unwrap();
    assert_eq!(installed_codes(&env.registry), ["AAA", "BBB"]);

    let receipt = env.dir.join(RECEIPT_FILE);
    let good = fs::read(&receipt).unwrap();
    // Unreadable: a schema number this build does not know (a newer build wrote it, say).
    let mut doc: Value = serde_json::from_slice(&good).unwrap();
    doc["schema"] = json!(2);
    let unreadable = doc.to_string().into_bytes();
    replace_file(&receipt, &unreadable);
    let before = env.names();

    // Installing a third translation is refused, and the source is never even read: the download
    // could only have been thrown away.
    let reads = AtomicUsize::new(0);
    let mut source = Counting {
        inner: &c.gz,
        reads: &reads,
    };
    let err = env
        .registry
        .install_from_reader("CCC", &mut source, NOW + 1, &InstallHooks::default())
        .unwrap_err();
    assert!(
        matches!(err, InstallError::Receipt(ReceiptError::Corrupt(_))),
        "{err:?}"
    );
    assert_eq!(
        reads.load(Ordering::SeqCst),
        0,
        "the source was read although the install could only be discarded"
    );
    // Removing one is refused too.
    let err = env.registry.remove("BBB").unwrap_err();
    assert!(
        matches!(err, InstallError::Receipt(ReceiptError::Corrupt(_))),
        "{err:?}"
    );

    // Nothing changed: the receipt is byte for byte what it was, both files are still there.
    assert_eq!(fs::read(&receipt).unwrap(), unreadable);
    assert_eq!(env.names(), before);
    assert_eq!(fs::read(env.dir.join("aaa.tsv.gz")).unwrap(), a.gz);
    assert_eq!(fs::read(env.dir.join("bbb.tsv.gz")).unwrap(), b.gz);

    // Positive control: with the receipt back, the same two calls work and NOTHING is forgotten.
    replace_file(&receipt, &good);
    env.install("CCC", &c.gz, NOW + 2).unwrap();
    assert_eq!(installed_codes(&env.registry), ["AAA", "BBB", "CCC"]);
    assert!(env.registry.remove("BBB").unwrap());
    assert_eq!(installed_codes(&env.registry), ["AAA", "CCC"]);
}

#[test]
fn repair_rebuilds_the_receipt_from_the_files_that_match_the_catalogue() {
    let (a, b, c) = (
        fixture("AAA", 2, 1),
        fixture("BBB", 3, 2),
        fixture("CCC", 1, 1),
    );
    let env = Env::with(&[&a, &b, &c]);
    env.install("AAA", &a.gz, NOW).unwrap();
    env.install("BBB", &b.gz, NOW).unwrap();
    // Debris in the folder: a file of the user's, and a file named like a catalogue entry whose
    // bytes are not the pinned ones.
    fs::write(env.dir.join("notes.txt"), b"mine").unwrap();
    fs::write(env.dir.join("ccc.tsv.gz"), b"not the pinned bytes").unwrap();
    replace_file(&env.dir.join(RECEIPT_FILE), b"{not json");
    assert!(
        env.registry.installed().is_err(),
        "premise: it is unreadable"
    );

    let rebuilt = env.registry.repair_receipt(NOW + 9).unwrap();
    let codes: Vec<String> = rebuilt.iter().map(|r| r.code.to_string()).collect();
    assert_eq!(
        codes,
        ["AAA", "BBB"],
        "only files that match a pin are recorded"
    );
    assert!(rebuilt.iter().all(|r| r.installed_at == NOW + 9));
    assert_eq!(
        rebuilt
            .iter()
            .map(|r| (r.verses_ot, r.verses_nt))
            .collect::<Vec<_>>(),
        [(2, 1), (3, 2)],
        "the verse counts come from the catalogue entry that the bytes matched"
    );
    assert_eq!(env.registry.installed().unwrap(), rebuilt);
    // Nothing was deleted, and nothing the receipt does not describe was adopted.
    assert_eq!(
        env.names(),
        [
            "aaa.tsv.gz",
            "bbb.tsv.gz",
            "ccc.tsv.gz",
            "installed.json",
            "notes.txt"
        ]
    );
    assert_eq!(
        fs::read(env.dir.join("ccc.tsv.gz")).unwrap(),
        b"not the pinned bytes"
    );
    assert_eq!(env.registry.index(&code("AAA")).unwrap().len(), 3);
    assert_eq!(env.registry.index(&code("BBB")).unwrap().len(), 5);
    assert!(matches!(
        env.registry.index(&code("CCC")),
        Err(LoadError::NotInstalled)
    ));
}

#[test]
fn repair_with_nothing_to_find_writes_an_empty_valid_receipt() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    assert_eq!(env.registry.repair_receipt(NOW).unwrap(), vec![]);
    assert_eq!(env.registry.installed().unwrap(), vec![]);
    // And now installing works.
    env.install("TST", &f.gz, NOW + 1).unwrap();
    assert_eq!(installed_codes(&env.registry), ["TST"]);
}

// ---- the write lock is not held across the network (A5) --------------------------------------

#[test]
fn remove_and_other_installs_are_not_blocked_behind_a_stalled_install() {
    let (a, b, c) = (
        fixture("AAA", 2, 1),
        fixture("BBB", 3, 2),
        fixture("CCC", 1, 1),
    );
    let env = Env::with(&[&a, &b, &c]);
    env.install("BBB", &b.gz, NOW).unwrap();
    let reg = env.registry.clone();

    let (started_tx, started_rx) = mpsc::channel();
    let (release_tx, release_rx) = mpsc::channel();
    let stalled = std::thread::spawn({
        let reg = reg.clone();
        let data = c.gz.clone();
        move || {
            let mut source = Stalls::new(data, started_tx, release_rx);
            reg.install_from_reader("CCC", &mut source, NOW + 1, &InstallHooks::default())
        }
    });
    started_rx
        .recv_timeout(Duration::from_secs(10))
        .expect("the install never reached its stall");

    // While CCC's download is stuck mid-transfer: remove BBB.
    let (done_tx, done_rx) = mpsc::channel();
    std::thread::spawn({
        let reg = reg.clone();
        move || {
            let started = Instant::now();
            let removed = reg.remove("BBB");
            let _ = done_tx.send((removed.is_ok_and(|r| r), started.elapsed()));
        }
    });
    let (removed, took) = done_rx
        .recv_timeout(Duration::from_secs(5))
        .expect("remove() is blocked behind a stalled install");
    assert!(removed, "BBB was installed, so removing it reports true");
    assert!(
        took < Duration::from_secs(2),
        "remove() took {took:?} while an install was merely waiting for bytes"
    );
    assert_eq!(installed_codes(&reg), Vec::<String>::new());

    // Cleanup of leftovers does not touch the staging file of the install that is running...
    let report = reg.recover().unwrap();
    assert_eq!(
        (report.removed, report.skipped),
        (0, 1),
        "the in-flight staging file must be skipped, not deleted"
    );
    assert!(
        env.names().iter().any(|n| n.ends_with(".part")),
        "premise: the staging file is on disk: {:?}",
        env.names()
    );
    // ...and a different translation installs in the meantime, also without waiting.
    let (done_tx, done_rx) = mpsc::channel();
    std::thread::spawn({
        let reg = reg.clone();
        let src = env.source("a.gz", &a.gz);
        move || {
            let _ =
                done_tx.send(reg.install_from_file("AAA", &src, NOW + 2, &InstallHooks::default()));
        }
    });
    let installed = done_rx
        .recv_timeout(Duration::from_secs(5))
        .expect("a second install is blocked behind a stalled one");
    installed.expect("the second install succeeds");

    // Positive control: release the stall, and the stalled install completes with its bytes intact
    // (the cleanup that ran meanwhile did not take its staging file).
    release_tx.send(()).unwrap();
    let rec = stalled
        .join()
        .unwrap()
        .expect("the stalled install finishes");
    assert_eq!(rec.code.as_str(), "CCC");
    assert_eq!(installed_codes(&reg), ["AAA", "CCC"]);
    assert_eq!(fs::read(env.dir.join("ccc.tsv.gz")).unwrap(), c.gz);
    assert!(!env.names().iter().any(|n| n.ends_with(".part")));
}

#[test]
fn an_install_queued_for_the_write_lock_gives_up_when_cancelled() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let src = env.source("asset.gz", &f.gz);
    let cancel = AtomicBool::new(false);
    let (verifying_tx, verifying_rx) = mpsc::channel::<()>();
    let hold = env.registry.hold_writes_for_tests();
    std::thread::scope(|scope| {
        let queued = scope.spawn(|| {
            let cb = |p: Progress| {
                if p.phase == Phase::Verifying {
                    let _ = verifying_tx.send(());
                }
            };
            let hooks = InstallHooks::default()
                .with_cancel(&cancel)
                .with_progress(&cb);
            env.registry.install_from_file("TST", &src, NOW, &hooks)
        });
        verifying_rx
            .recv_timeout(Duration::from_secs(10))
            .expect("the install never got as far as verifying");
        std::thread::sleep(Duration::from_millis(150));
        assert!(
            !queued.is_finished(),
            "premise: the install is waiting for the write lock, which is held"
        );
        cancel.store(true, Ordering::SeqCst);
        let deadline = Instant::now() + Duration::from_secs(5);
        while !queued.is_finished() {
            assert!(
                Instant::now() < deadline,
                "a cancelled install is still waiting for the write lock"
            );
            std::thread::sleep(Duration::from_millis(5));
        }
        let err = queued.join().unwrap().unwrap_err();
        assert!(matches!(err, InstallError::Cancelled), "{err:?}");
    });
    // It gave up while the lock was STILL held: the cancel is what ended it, not the release.
    drop(hold);
    env.assert_nothing_installed("an install cancelled while queued");

    // Positive control: without the flag, the same install waits for the lock and completes.
    cancel.store(false, Ordering::SeqCst);
    assert!(env.install("TST", &f.gz, NOW).is_ok());
}

// ---- a read that fails because the caller cancelled (A8) -------------------------------------

/// A source whose read raises the cancel flag and then fails, like a blocked read that timed out
/// after the user pressed Cancel.
struct FailsOnCancel<'a> {
    cancel: &'a AtomicBool,
    raise_flag: bool,
}

impl Read for FailsOnCancel<'_> {
    fn read(&mut self, _buf: &mut [u8]) -> std::io::Result<usize> {
        if self.raise_flag {
            self.cancel.store(true, Ordering::SeqCst);
        }
        Err(std::io::Error::new(
            std::io::ErrorKind::TimedOut,
            "timed out",
        ))
    }
}

#[test]
fn a_read_that_fails_after_cancel_was_pressed_is_reported_as_cancelled() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let cancel = AtomicBool::new(false);
    let mut source = FailsOnCancel {
        cancel: &cancel,
        raise_flag: true,
    };
    let err = env
        .registry
        .install_from_reader(
            "TST",
            &mut source,
            NOW,
            &InstallHooks::default().with_cancel(&cancel),
        )
        .unwrap_err();
    assert!(matches!(err, InstallError::Cancelled), "{err:?}");
    env.assert_nothing_installed("a failed read after cancel");

    // Positive control: the very same failure with no cancel is a source failure.
    let cancel = AtomicBool::new(false);
    let mut source = FailsOnCancel {
        cancel: &cancel,
        raise_flag: false,
    };
    let err = env
        .registry
        .install_from_reader(
            "TST",
            &mut source,
            NOW,
            &InstallHooks::default().with_cancel(&cancel),
        )
        .unwrap_err();
    assert!(matches!(err, InstallError::Source(_)), "{err:?}");
}

// ---- a crash between the two renames, and a read that races a reinstall (A8, B14) --------------

#[test]
fn a_crash_between_the_two_renames_fails_closed_and_installing_again_repairs_it() {
    // Two different files of the SAME size, so only the digest can tell them apart (which label
    // compresses to the same length as the first is found, not assumed).
    let v1 = fixture_labelled("TST", "L000", 3, 2);
    let (label, v2) = (1..1000)
        .map(|i| format!("L{i:03}"))
        .map(|l| {
            let f = fixture_labelled("TST", &l, 3, 2);
            (l, f)
        })
        .find(|(_, f)| f.gz.len() == v1.gz.len() && f.sha256 != v1.sha256)
        .expect("no second label compresses to the same length as the first");
    let label = label.as_str();
    let root = tmp_dir("crash");
    let dir = root.join("data");
    fs::write(root.join("v1.gz"), &v1.gz).unwrap();
    fs::write(root.join("v2.gz"), &v2.gz).unwrap();
    let first = Registry::new(dir.clone(), catalogue(vec![v1.entry("cleared")]));
    first
        .install_from_file("TST", &root.join("v1.gz"), NOW, &InstallHooks::default())
        .unwrap();

    // What a commit does is: (1) rename the new data file over the old one, (2) rename the new
    // receipt over the old one. Do (1) and stop, which is exactly the state a crash between the
    // two renames leaves behind: a new data file beside the old receipt.
    replace_file(&dir.join("tst.tsv.gz"), &v2.gz);

    // A fresh process lists it (the size is the receipt's) but will not serve it.
    let fresh = Registry::new(dir.clone(), catalogue(vec![v2.entry("cleared")]));
    assert_eq!(installed_codes(&fresh), ["TST"], "premise: it is listed");
    let err = fresh.index(&code("TST")).unwrap_err();
    assert!(
        matches!(&err, LoadError::Mismatch { expected, .. } if *expected == v1.sha256),
        "{err:?}"
    );
    assert!(matches!(
        fresh.verify(&code("TST")),
        Err(LoadError::Mismatch { .. })
    ));
    assert!(
        fresh.resident_codes().is_empty(),
        "the new text was served under the old receipt"
    );
    let bible = fresh.bible("TST").unwrap();
    assert_eq!(bible.verse_count(), 0);
    assert!(matches!(bible.check(), Err(LoadError::Mismatch { .. })));

    // Installing again repairs it.
    fresh
        .install_from_file(
            "TST",
            &root.join("v2.gz"),
            NOW + 1,
            &InstallHooks::default(),
        )
        .unwrap();
    assert_eq!(
        fresh.index(&code("TST")).unwrap()[0].text,
        verse_text(label, 1, 1, 1)
    );
    assert!(fresh.verify(&code("TST")).is_ok());
}

#[test]
fn a_read_that_races_a_reinstall_retries_against_the_new_receipt() {
    // The reader has read the receipt (it names file ONE) when another writer finishes installing
    // file TWO: the file is now TWO, and the reader's receipt entry is stale. That is a transient
    // mismatch, not damage; the read must look at the receipt again and serve TWO.
    let v1 = fixture_labelled("TST", "ONE", 3, 2);
    let v2 = fixture_labelled("TST", "TWO", 4, 2);
    let root = tmp_dir("race");
    let dir = root.join("data");
    fs::write(root.join("v1.gz"), &v1.gz).unwrap();
    fs::write(root.join("v2.gz"), &v2.gz).unwrap();
    let host = Registry::new(dir.clone(), catalogue(vec![v1.entry("cleared")]));
    host.install_from_file("TST", &root.join("v1.gz"), NOW, &InstallHooks::default())
        .unwrap();
    let writer = Registry::new(dir.clone(), catalogue(vec![v2.entry("cleared")]));

    let fired = Arc::new(AtomicBool::new(false));
    host.set_load_hook_for_tests(Some(Arc::new({
        let (fired, v2_path) = (Arc::clone(&fired), root.join("v2.gz"));
        move |stage| {
            if stage == LoadStage::AfterReceipt && !fired.swap(true, Ordering::SeqCst) {
                writer
                    .install_from_file("TST", &v2_path, NOW + 5, &InstallHooks::default())
                    .unwrap();
            }
        }
    })));
    let index = host
        .index(&code("TST"))
        .expect("a read that raced a reinstall must retry against the new receipt");
    assert!(fired.load(Ordering::SeqCst), "premise: the race happened");
    assert_eq!(index.len(), 6);
    assert_eq!(index[0].text, verse_text("TWO", 1, 1, 1));
    assert_eq!(host.loads_for("TST"), 1);

    // Control: damage that is NOT a reinstall (the receipt is unchanged) is still reported.
    host.set_load_hook_for_tests(None);
    let reg = Registry::new(dir.clone(), catalogue(vec![v2.entry("cleared")]));
    let mut bytes = fs::read(dir.join("tst.tsv.gz")).unwrap();
    bytes[12] ^= 0xFF;
    replace_file(&dir.join("tst.tsv.gz"), &bytes);
    assert!(matches!(
        reg.index(&code("TST")),
        Err(LoadError::Mismatch { .. })
    ));
}

// ---- the row bound at read time (A1) ------------------------------------------------------------

#[test]
fn a_planted_file_with_far_more_rows_than_the_receipt_records_is_refused_unread() {
    // The receipt and the file agree on the digest (someone who can write the folder rewrote both),
    // so only counting rows can refuse it: 262,140 one-letter rows are about 2.6 MB inflated and a
    // few hundred KB on disk, and used to cost hundreds of MB once decoded.
    let (a, b) = (fixture("AAA", 3, 2), fixture("BBB", 3, 2));
    let env = Env::with(&[&a, &b]);
    env.install("AAA", &a.gz, NOW).unwrap();
    env.install("BBB", &b.gz, NOW).unwrap();
    assert_eq!(env.registry.index(&code("AAA")).unwrap().len(), 5);
    assert_eq!(env.registry.peak_live_indexes(), 1);

    let hostile = many_tiny_rows(262_140);
    assert!(
        hostile.len() < 1024 * 1024,
        "premise: small on disk ({} bytes)",
        hostile.len()
    );
    plant(&env.dir, "BBB", &hostile, 3, 2);
    let err = env.registry.index(&code("BBB")).unwrap_err();
    assert!(
        matches!(
            err,
            LoadError::Invalid(ValidationError::TooManyRows { limit: 5 })
        ),
        "{err:?}"
    );
    assert_eq!(
        env.registry.peak_live_indexes(),
        1,
        "the hostile file was decoded (an index of it existed)"
    );
    assert_eq!(
        env.registry.resident_codes(),
        ["AAA"],
        "refusing it must not evict the good index"
    );
    assert!(matches!(
        env.registry.verify(&code("BBB")),
        Err(LoadError::Invalid(ValidationError::TooManyRows {
            limit: 5
        }))
    ));

    // Positive control: a file with as many rows as the receipt records is read, whatever its size
    // (so the bound is the recorded count, not some fixed number).
    let honest = many_tiny_rows(100_000);
    plant(&env.dir, "BBB", &honest, 100_000, 0);
    assert_eq!(env.registry.index(&code("BBB")).unwrap().len(), 100_000);
}

// ---- the receipt and a damaged file are not re-read needlessly (B11) -------------------------

#[test]
fn the_receipt_is_read_again_only_when_it_changed() {
    let (a, b) = (fixture("AAA", 2, 1), fixture("BBB", 3, 2));
    let env = Env::with(&[&a, &b]);
    env.install("AAA", &a.gz, NOW).unwrap();
    env.install("BBB", &b.gz, NOW).unwrap();
    let reg = &env.registry;
    assert!(reg.bible("AAA").is_some(), "primes the cache");
    let base = reg.receipt_reads();

    for _ in 0..200 {
        assert!(reg.bible("AAA").is_some());
        assert!(reg.installed_entry(&code("BBB")).is_some());
    }
    assert_eq!(
        reg.receipt_reads(),
        base,
        "an unchanged receipt was read and parsed again"
    );

    // A change made by someone else is seen on the next call...
    let receipt = env.dir.join(RECEIPT_FILE);
    let mut doc: Value = serde_json::from_slice(&fs::read(&receipt).unwrap()).unwrap();
    doc["translations"][0]["installed_at"] = json!(NOW + 777);
    replace_file(&receipt, doc.to_string().as_bytes());
    let rec = reg.installed_entry(&code("AAA")).unwrap();
    assert_eq!(
        rec.installed_at,
        NOW + 777,
        "the changed receipt was not noticed"
    );
    assert_eq!(reg.receipt_reads(), base + 1);
    // ...once.
    for _ in 0..50 {
        assert!(reg.installed_entry(&code("AAA")).is_some());
    }
    assert_eq!(reg.receipt_reads(), base + 1);
}

#[test]
fn a_file_found_damaged_is_not_hashed_again_until_it_changes() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    env.install("TST", &f.gz, NOW).unwrap();
    let path = env.dir.join("tst.tsv.gz");
    let mut bytes = fs::read(&path).unwrap();
    bytes[12] ^= 0xFF;
    fs::write(&path, &bytes).unwrap();
    let reg = &env.registry;

    let first = reg.index(&code("TST")).unwrap_err();
    assert!(matches!(first, LoadError::Mismatch { .. }), "{first:?}");
    let reads = reg.file_reads();
    assert_eq!(reads, 1, "premise: the first look read the file once");
    for _ in 0..50 {
        assert!(matches!(
            reg.index(&code("TST")),
            Err(LoadError::Mismatch { .. })
        ));
        assert!(matches!(
            reg.verify(&code("TST")),
            Err(LoadError::Mismatch { .. })
        ));
    }
    assert_eq!(
        reg.file_reads(),
        reads,
        "a file already known to be damaged was read and hashed again"
    );

    // A different damaged file in its place (a new inode, other bytes) is looked at afresh.
    let mut other = bytes.clone();
    other[13] ^= 0xFF;
    replace_file(&path, &other);
    assert!(matches!(
        reg.index(&code("TST")),
        Err(LoadError::Mismatch { .. })
    ));
    assert_eq!(reg.file_reads(), reads + 1);

    // And the repair (installing again) is seen at once.
    env.install("TST", &f.gz, NOW + 1).unwrap();
    assert_eq!(reg.index(&code("TST")).unwrap().len(), 5);
    assert_eq!(reg.file_reads(), reads + 2);
    assert!(reg.verify(&code("TST")).is_ok());
}

#[test]
fn installed_translations_come_back_as_plain_values() {
    // The public record type is plain data a screen can hold and compare.
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    let rec: InstalledTranslation = env.install("TST", &f.gz, NOW).unwrap();
    assert_eq!(env.registry.installed_entry(&code("TST")), Some(rec));
}
