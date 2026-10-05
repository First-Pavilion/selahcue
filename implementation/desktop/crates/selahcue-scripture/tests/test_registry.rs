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
use std::sync::atomic::{AtomicBool, Ordering};

use common::{
    big_asset, catalogue_json, entry_pinning, fixture, fixture_labelled, gz, read_dir_names,
    tmp_dir, verse_text, Fixture,
};
use selahcue_scripture::catalog::{Catalogue, TranslationCode};
use selahcue_scripture::registry::{
    InstallError, InstallHooks, LoadError, Phase, Progress, ReceiptError, Registry, RECEIPT_FILE,
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
    // can stop it: 70 MB inflated from under a megabyte.
    let bomb = big_asset(4_400);
    assert!(bomb.len() < 1024 * 1024);
    let env = Env::new(vec![entry_pinning("TST", &bomb, 4_400, 0)]);
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
    // (what, the bytes, OT count, NT count, the validation error it must reach)
    let cases: Vec<(&str, Vec<u8>, u32, u32, &str)> = vec![
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

    // Installing heals it: the link is replaced by a regular file; the target is not touched.
    env.install("TST", &f.gz, NOW + 1).unwrap();
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
        // Valid JSON in every way except that it is far larger than any receipt can be: only the
        // size cap can refuse it (a receipt that is merely garbage is refused by the parser).
        ("a valid receipt past the size cap", {
            let mut padded = good.to_string().into_bytes();
            padded.extend(vec![b' '; 300 * 1024]);
            padded
        }),
    ];
    for (what, bytes) in cases {
        fs::write(env.dir.join(RECEIPT_FILE), bytes).unwrap();
        let err = env.registry.installed().unwrap_err();
        assert!(matches!(err, ReceiptError::Corrupt(_)), "{what}: {err:?}");
        assert!(
            env.registry.bible("TST").is_none(),
            "{what}: served from a bad receipt"
        );
    }

    // Positive control: the unmodified receipt is read.
    fs::write(env.dir.join(RECEIPT_FILE), good.to_string()).unwrap();
    assert_eq!(env.registry.installed().unwrap().len(), 1);
    assert!(env.registry.bible("TST").is_some());
}

#[test]
fn installing_over_a_corrupt_receipt_heals_it() {
    let f = fixture("TST", 3, 2);
    let env = Env::with(&[&f]);
    fs::create_dir_all(&env.dir).unwrap();
    fs::write(env.dir.join(RECEIPT_FILE), b"{not json").unwrap();
    assert!(env.registry.installed().is_err());
    env.install("TST", &f.gz, NOW).unwrap();
    assert_eq!(env.registry.installed().unwrap().len(), 1);
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
    // not whenever the next read happens to prune it: it is ~7 MiB that nothing will ever serve.
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
    assert_eq!(
        reg.index(&code("TST")).unwrap()[0].text,
        verse_text("NEW", 1, 1, 1)
    );
}
