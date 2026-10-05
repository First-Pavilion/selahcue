//! `Bible::from_code` resolves an installed translation through the process-wide registry
//! (`Registry::global`, the embedded catalogue over `default_data_dir`).
//!
//! This file holds exactly one test, and sets `SELAHCUE_SCRIPTURE_DATA` before the first use of the
//! global registry (it resolves its directory once, on first use), which is why it is its own test
//! binary. The translation is put on disk the way an install leaves it: a data file and a receipt.
//! The text is a small fixture filed under the code `BSB`; loading checks the file against the
//! receipt, so it needs no copy of the real asset.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

mod common;

use std::fs;

use common::{fixture, tmp_dir, verse_text};
use selahcue_core::scripture::parse_one;
use selahcue_scripture::registry::{Registry, DATA_DIR_ENV, RECEIPT_FILE};
use selahcue_scripture::Bible;
use serde_json::json;

#[test]
fn the_wire_helper_finds_an_installed_translation_in_the_global_registry() {
    let data = tmp_dir("global").join("data");
    fs::create_dir_all(&data).unwrap();
    let f = fixture("BSB", 3, 2);
    fs::write(data.join("bsb.tsv.gz"), &f.gz).unwrap();
    let receipt = json!({
        "schema": 1,
        "translations": [{
            "code": "BSB",
            "file_name": "bsb.tsv.gz",
            "sha256": f.sha256,
            "size_bytes": f.gz.len(),
            "installed_at": 1_790_000_000u64,
            "catalogue_schema": 1
        }]
    });
    fs::write(data.join(RECEIPT_FILE), receipt.to_string()).unwrap();
    std::env::set_var(DATA_DIR_ENV, &data);

    let registry = Registry::global().expect("a data directory is configured");
    assert_eq!(registry.dir(), data);

    // An installed code resolves (case-insensitively), carries the catalogue's name, and answers.
    let bsb = Bible::from_code("bsb").expect("BSB is installed");
    assert_eq!(bsb.code(), "BSB");
    assert_eq!(bsb.name(), "Berean Standard Bible");
    assert!(bsb.bundled_translation().is_none());
    assert!(bsb.is_available());
    let r = parse_one("Genesis 1:1").unwrap();
    assert_eq!(bsb.passage_text(&r), Some(verse_text("BSB", 1, 1, 1)));
    assert_eq!(bsb.verse_count(), 5);

    // A catalogued translation that is NOT installed has no handle, and a bundled code still
    // resolves to the bundled translation, not the registry.
    for code in ["YOR", "IBO", "HAU"] {
        assert!(Bible::from_code(code).is_none(), "{code} is not installed");
    }
    let kjv = Bible::from_code("KJV").unwrap();
    assert!(kjv.bundled_translation().is_some());
    assert!(Bible::from_code("NOT-A-CODE").is_none());
}
