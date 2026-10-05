//! Shared fixtures for the installed-translation tests. Not a test file: each test binary pulls it
//! in with `mod common;` and uses the part it needs.
#![allow(dead_code)]
#![allow(clippy::unwrap_used)]

use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

/// A unique temp directory for one test (no external tempfile dependency).
pub fn tmp_dir(tag: &str) -> PathBuf {
    static SEQ: AtomicU32 = AtomicU32::new(0);
    let n = SEQ.fetch_add(1, Ordering::Relaxed);
    let d = std::env::temp_dir().join(format!(
        "selahcue-scripture-{}-{}-{}",
        tag,
        std::process::id(),
        n
    ));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// Deterministic gzip of `bytes`.
pub fn gz(bytes: &[u8]) -> Vec<u8> {
    let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
    enc.write_all(bytes).unwrap();
    enc.finish().unwrap()
}

/// Lowercase-hex SHA-256 of `bytes`.
pub fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|b| format!("{b:02x}")).collect()
}

/// One synthetic translation: a tiny verse index in the real row format, its gzip, and the digest
/// a catalogue entry would pin. `ot` verses in Genesis 1 and `nt` verses in John 1.
pub struct Fixture {
    pub code: String,
    pub ot: u32,
    pub nt: u32,
    pub tsv: Vec<u8>,
    pub gz: Vec<u8>,
    pub sha256: String,
}

/// Text of a fixture verse: names the translation so a test can tell WHICH file it was served from.
pub fn verse_text(code: &str, book: u32, chapter: u32, verse: u32) -> String {
    format!("{code} fixture verse {book}:{chapter}:{verse}")
}

pub fn tsv_rows(code: &str, ot: u32, nt: u32) -> Vec<u8> {
    let mut out = String::new();
    for v in 1..=ot {
        out.push_str(&format!("1\t1\t{v}\t{}\n", verse_text(code, 1, 1, v)));
    }
    for v in 1..=nt {
        out.push_str(&format!("43\t1\t{v}\t{}\n", verse_text(code, 43, 1, v)));
    }
    out.into_bytes()
}

pub fn fixture(code: &str, ot: u32, nt: u32) -> Fixture {
    fixture_labelled(code, code, ot, nt)
}

/// A fixture for `code` whose verse text says `label` instead, so two different files can be
/// installed under the same code and a test can tell which one it was served from.
pub fn fixture_labelled(code: &str, label: &str, ot: u32, nt: u32) -> Fixture {
    let tsv = tsv_rows(label, ot, nt);
    let gz = gz(&tsv);
    let sha256 = sha256_hex(&gz);
    Fixture {
        code: code.to_string(),
        ot,
        nt,
        tsv,
        gz,
        sha256,
    }
}

impl Fixture {
    pub fn file_name(&self) -> String {
        format!("{}.tsv.gz", self.code.to_ascii_lowercase())
    }

    /// A schema-1 catalogue entry that pins this fixture.
    pub fn entry(&self, legal_review: &str) -> Value {
        json!({
            "code": self.code,
            "name": format!("{} Test Bible", self.code),
            "language": "eng",
            "language_name": "English",
            "file_name": self.file_name(),
            "size_bytes": self.gz.len(),
            "sha256": self.sha256,
            "verses": {"ot": self.ot, "nt": self.nt},
            "omitted_verses": 0,
            "licence": {
                "id": "cc0",
                "name": "Creative Commons Zero (CC0 1.0)",
                "summary": "Free to copy, share and project.",
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "attribution_required": false,
                "share_alike": false
            },
            "attribution": null,
            "trademark_note": null,
            "modifications": null,
            "legal_review": legal_review,
            "source": {
                "ebible_id": format!("eng{}", self.code.to_ascii_lowercase()),
                "url": "https://ebible.org/Scriptures/engtest_usfm.zip",
                "title": "Test Bible",
                "copyright": "public domain",
                "ebible_update_date": "2026-01-01",
                "usfm_zip_sha256": "0".repeat(64)
            }
        })
    }
}

/// A whole schema-1 catalogue document.
pub fn catalogue_json(base_url: Option<&str>, entries: Vec<Value>) -> String {
    json!({
        "schema": 1,
        "base_url": base_url,
        "translations_csv_sha256": "0".repeat(64),
        "translations": entries,
    })
    .to_string()
}

/// A catalogue document with every field of the first entry reachable for tampering.
pub fn catalogue_value(base_url: Option<&str>, entries: Vec<Value>) -> Value {
    serde_json::from_str(&catalogue_json(base_url, entries)).unwrap()
}

pub fn read_dir_names(dir: &Path) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(dir)
        .map(|rd| {
            rd.filter_map(|e| e.ok())
                .map(|e| e.file_name().to_string_lossy().into_owned())
                .collect()
        })
        .unwrap_or_default();
    names.sort();
    names
}

/// A valid asset that inflates to `rows` rows of one 16,000-byte verse each (about 16 KB per row,
/// so 1,000 rows are 16.0 MB and 1,100 are 17.6 MB), compressed on the fly so a test never holds
/// the inflated bytes. Every row is valid and ascending, so only its size can refuse it.
pub fn big_asset(rows: u32) -> Vec<u8> {
    let text = "a".repeat(16_000);
    let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    for v in 1..=rows {
        writeln!(enc, "1\t1\t{v}\t{text}").unwrap();
    }
    enc.finish().unwrap()
}

/// `rows` valid, ascending, one-letter verse rows (`1<TAB>chapter<TAB>verse<TAB>a`), four verses to
/// a chapter, up to 262,140 of them: every row passes the row grammar, so only COUNTING them can
/// refuse the file. Compressed on the fly; the inflated text is never held.
pub fn many_tiny_rows(rows: u32) -> Vec<u8> {
    assert!(rows <= 65_535 * 4, "chapters are 16 bits");
    let mut enc = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::fast());
    let mut written = 0u32;
    'chapters: for chapter in 1..=65_535u32 {
        for verse in 1..=4u32 {
            if written == rows {
                break 'chapters;
            }
            writeln!(enc, "1\t{chapter}\t{verse}\ta").unwrap();
            written += 1;
        }
    }
    enc.finish().unwrap()
}

/// Replace the file at `path` with `bytes` by writing a sibling and renaming it over, so the
/// replacement is a NEW inode. The registry notices a changed file by its length, modification time
/// and inode; a plain in-place `fs::write` of the same length within one clock tick of the last
/// change would leave all three equal on some file systems, which would make a test flaky for a
/// reason that has nothing to do with what it checks.
pub fn replace_file(path: &Path, bytes: &[u8]) {
    let name = path.file_name().unwrap().to_string_lossy().into_owned();
    let swap = path.with_file_name(format!(".swap-{name}"));
    std::fs::write(&swap, bytes).unwrap();
    std::fs::rename(&swap, path).unwrap();
}

/// Plant `bytes` as `code`'s installed file AND make the receipt describe them (digest, size and
/// verse counts), as someone who can write the data directory could. The digest then matches, so
/// only the registry's own checks of the file's content can refuse it.
pub fn plant(dir: &Path, code: &str, bytes: &[u8], ot: u32, nt: u32) {
    replace_file(
        &dir.join(format!("{}.tsv.gz", code.to_ascii_lowercase())),
        bytes,
    );
    let receipt = dir.join("installed.json");
    let mut doc: Value = serde_json::from_slice(&std::fs::read(&receipt).unwrap()).unwrap();
    let mut found = false;
    for e in doc["translations"].as_array_mut().unwrap() {
        if e["code"] == code {
            e["sha256"] = json!(sha256_hex(bytes));
            e["size_bytes"] = json!(bytes.len());
            e["verses_ot"] = json!(ot);
            e["verses_nt"] = json!(nt);
            found = true;
        }
    }
    assert!(found, "{code} is not in the receipt");
    replace_file(&receipt, doc.to_string().as_bytes());
}

/// One catalogue entry that pins arbitrary bytes (a hostile or broken file the catalogue vouches
/// for), claiming `ot`/`nt` verses.
pub fn entry_pinning(code: &str, bytes: &[u8], ot: u32, nt: u32) -> Value {
    let mut e = fixture(code, ot, nt).entry("cleared");
    e["size_bytes"] = json!(bytes.len());
    e["sha256"] = json!(sha256_hex(bytes));
    e
}
