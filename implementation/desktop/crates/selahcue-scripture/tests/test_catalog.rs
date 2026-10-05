//! The embedded translation catalogue (`assets/catalog.json`, schema 1; feature `installed`).
//!
//! It is parsed and validated at first use. Every refusal below names the specific error it must
//! reach, so a generic failure cannot satisfy two different cases; each refusal is paired with a
//! benign document that is accepted, so "refused" is distinguishable from "the parser rejects
//! everything".
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

// These tests call the test-only constructors (`..._for_tests`), which exist only when debug
// assertions are on. In a build without them this file would not compile; say why instead.
#[cfg(not(debug_assertions))]
compile_error!("run these tests without --release: the test-only constructors exist only with debug assertions");

mod common;

use common::{catalogue_json, catalogue_value, fixture};
use selahcue_scripture::catalog::{
    asset_url, CatalogError, Catalogue, CodeError, LegalReview, TranslationCode, MAX_ASSET_BYTES,
    MAX_CATALOGUE_BYTES, MAX_ENTRIES,
};
use selahcue_scripture::url_policy::UrlPolicy;
use serde_json::{json, Value};

const BASE: &str = "https://downloads.example.org/translations/";

/// A one-entry document (`TST`), tampered with by `mutate`, parsed with the product policy.
fn parse_tampered(mutate: impl FnOnce(&mut Value)) -> Result<Catalogue, CatalogError> {
    let f = fixture("TST", 3, 2);
    let mut doc = catalogue_value(Some(BASE), vec![f.entry("cleared")]);
    mutate(&mut doc);
    Catalogue::parse(&doc.to_string())
}

fn entry_mut(doc: &mut Value) -> &mut Value {
    &mut doc["translations"][0]
}

#[test]
fn a_well_formed_document_parses_and_exposes_every_field() {
    let f = fixture("TST", 3, 2);
    let cat = Catalogue::parse(&catalogue_json(Some(BASE), vec![f.entry("cleared")])).unwrap();
    assert_eq!(cat.schema(), 1);
    assert_eq!(cat.base_url(), Some(BASE));
    assert!(cat.is_published());
    let e = cat.find("TST").expect("TST is in the catalogue");
    assert_eq!(e.code.as_str(), "TST");
    assert_eq!(e.name, "TST Test Bible");
    assert_eq!(e.language, "eng");
    assert_eq!(e.language_name, "English");
    assert_eq!(e.file_name, "tst.tsv.gz");
    assert_eq!(e.size_bytes, f.gz.len() as u64);
    assert_eq!(e.sha256, f.sha256);
    assert_eq!((e.verses_ot, e.verses_nt), (3, 2));
    assert_eq!(e.omitted_verses, 0);
    assert_eq!(e.licence.id, "cc0");
    assert!(!e.licence.attribution_required);
    assert!(!e.licence.share_alike);
    assert_eq!(
        e.licence.url.as_deref(),
        Some("https://creativecommons.org/publicdomain/zero/1.0/")
    );
    assert_eq!(e.legal_review, LegalReview::Cleared);
    assert_eq!(e.source.ebible_id, "engtst");
    assert!(e.attribution.is_none() && e.trademark_note.is_none() && e.modifications.is_none());
    // Lookup is case-insensitive, like the bundled codes on the wire.
    assert!(cat.find("tst").is_some());
    assert!(cat.find("NOPE").is_none());
}

#[test]
fn the_embedded_catalogue_is_valid_and_matches_the_file() {
    Catalogue::embedded_status().expect("assets/catalog.json must parse and validate");
    let on_disk =
        std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/catalog.json"))
            .unwrap();
    let reparsed = Catalogue::parse(&on_disk).unwrap();
    assert_eq!(&reparsed, Catalogue::embedded());
}

#[test]
fn the_shipped_catalogue_is_an_honest_placeholder() {
    let cat = Catalogue::embedded();
    // Nothing is published, so nothing may be requested.
    assert_eq!(cat.base_url(), None, "no bucket URL may be invented");
    assert!(!cat.is_published());
    let note = cat.note().expect("the placeholder must say it is one");
    assert!(
        note.contains("PLACEHOLDER"),
        "the shipped digests must be labelled as placeholders, got: {note}"
    );
    // The four v1 translations: BSB cleared, the three Biblica texts waiting on legal review.
    let codes: Vec<&str> = cat.translations().iter().map(|e| e.code.as_str()).collect();
    assert_eq!(codes, ["BSB", "HAU", "IBO", "YOR"]);
    assert_eq!(cat.find("BSB").unwrap().legal_review, LegalReview::Cleared);
    for code in ["HAU", "IBO", "YOR"] {
        assert_eq!(
            cat.find(code).unwrap().legal_review,
            LegalReview::Pending,
            "{code} awaits legal review"
        );
    }
    // YLT and MSB are out of v1.
    assert!(cat.find("YLT").is_none() && cat.find("MSB").is_none());
}

#[test]
fn only_cleared_entries_are_offered_for_download() {
    let a = fixture("AAA", 1, 1);
    let b = fixture("BBB", 1, 1);
    let cat = Catalogue::parse(&catalogue_json(
        Some(BASE),
        vec![a.entry("cleared"), b.entry("pending")],
    ))
    .unwrap();
    let offered: Vec<&str> = cat.offered().map(|e| e.code.as_str()).collect();
    assert_eq!(offered, ["AAA"], "a pending entry must not be offered");
    // The pending entry is still listed, with its status exposed, so a UI can show "pending".
    assert_eq!(cat.find("BBB").unwrap().legal_review, LegalReview::Pending);
    assert_eq!(cat.translations().len(), 2);
}

#[test]
fn the_url_template_is_one_function_and_unpublished_entries_have_no_url() {
    let f = fixture("TST", 3, 2);
    let cat = Catalogue::parse(&catalogue_json(Some(BASE), vec![f.entry("cleared")])).unwrap();
    let e = cat.find("TST").unwrap();
    assert_eq!(
        asset_url(BASE, e),
        "https://downloads.example.org/translations/tst.tsv.gz"
    );
    // A base without a trailing slash still joins correctly.
    assert_eq!(
        asset_url("https://downloads.example.org/translations", e),
        "https://downloads.example.org/translations/tst.tsv.gz"
    );
    assert_eq!(cat.download_url(e).unwrap(), asset_url(BASE, e));

    // No base URL: "not published yet", and never a URL.
    let unpublished = Catalogue::parse(&catalogue_json(None, vec![f.entry("cleared")])).unwrap();
    assert!(!unpublished.is_published());
    let e = unpublished.find("TST").unwrap();
    let err = unpublished.download_url(e).unwrap_err();
    assert_eq!(err.to_string(), "not published yet");
}

#[test]
fn input_that_is_not_a_catalogue_is_refused() {
    assert!(matches!(
        Catalogue::parse("{not json"),
        Err(CatalogError::BadJson(_))
    ));
    assert!(matches!(
        Catalogue::parse("[]"),
        Err(CatalogError::WrongType { .. })
    ));
    let huge = format!("{{\"pad\": \"{}\"}}", "x".repeat(MAX_CATALOGUE_BYTES));
    assert!(matches!(
        Catalogue::parse(&huge),
        Err(CatalogError::TooLarge { .. })
    ));
}

#[test]
fn an_unknown_or_missing_schema_is_refused() {
    let err = parse_tampered(|d| d["schema"] = json!(2)).unwrap_err();
    assert!(matches!(err, CatalogError::UnsupportedSchema { found: 2 }));
    let err = parse_tampered(|d| {
        d.as_object_mut().unwrap().remove("schema");
    })
    .unwrap_err();
    assert!(matches!(err, CatalogError::Missing { ref field } if field == "schema"));
    // Positive control: the unmodified document is accepted.
    assert!(parse_tampered(|_| {}).is_ok());
}

#[test]
fn duplicate_codes_are_refused() {
    let a = fixture("AAA", 1, 1);
    let mut b = a.entry("cleared");
    b["file_name"] = json!("other.tsv.gz");
    let err =
        Catalogue::parse(&catalogue_json(Some(BASE), vec![a.entry("cleared"), b])).unwrap_err();
    assert!(matches!(err, CatalogError::DuplicateCode { ref code } if code == "AAA"));
}

#[test]
fn a_code_that_collides_with_a_bundled_translation_is_refused() {
    for code in ["KJV", "WEB", "ASV", "WEBBE", "DBY"] {
        let err = parse_tampered(|d| entry_mut(d)["code"] = json!(code)).unwrap_err();
        assert!(
            matches!(
                err,
                CatalogError::BadCode {
                    reason: CodeError::CollidesWithBundled,
                    ..
                }
            ),
            "{code}: {err:?}"
        );
    }
    // The same codes are refused by the code type directly, in any case.
    assert_eq!(
        TranslationCode::parse("KJV").unwrap_err(),
        CodeError::CollidesWithBundled
    );
    // Positive control: a code that merely LOOKS bundled is fine.
    assert!(TranslationCode::parse("WEBX").is_ok());
}

#[test]
fn a_code_with_the_wrong_shape_is_refused() {
    for code in [
        "",
        "A",
        "bsb",
        "Bsb",
        "1BS",
        "BS_B",
        "BS B",
        "BSB.X",
        "../X",
        "ABCDEFGHIJKLMNOPQ", // 17 characters
    ] {
        assert_eq!(
            TranslationCode::parse(code).unwrap_err(),
            CodeError::BadShape,
            "{code:?}"
        );
    }
    // Boundaries: 2 and 16 characters, digits and hyphens after the first letter.
    assert!(TranslationCode::parse("AB").is_ok());
    assert!(TranslationCode::parse("ABCDEFGHIJKLMNOP").is_ok());
    assert!(TranslationCode::parse("A1-B2").is_ok());
    let err = parse_tampered(|d| entry_mut(d)["code"] = json!("bsb")).unwrap_err();
    assert!(matches!(
        err,
        CatalogError::BadCode {
            reason: CodeError::BadShape,
            ..
        }
    ));
}

#[test]
fn a_file_name_that_is_not_a_plain_name_is_refused() {
    let mut bad: Vec<String> = [
        "../tst.tsv.gz",
        "a/tst.tsv.gz",
        "/tst.tsv.gz",
        "..\\tst.tsv.gz",
        "C:tst.tsv.gz",
        ".tst.tsv.gz",
        "..tsv.gz",
        "tst.tsv",
        "tst.txt",
        "a..b.tsv.gz",
        "tst.tsv.gz ",
        " tst.tsv.gz",
        "tst .tsv.gz",
        "t\u{0}st.tsv.gz",
        "ts\tt.tsv.gz",
        "",
        "con.tsv.gz",
        "NUL.tsv.gz",
        "com1.tsv.gz",
        "lpt9.tsv.gz",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect();
    // Longer than the 64-character cap, with a valid suffix, so only the length can refuse it.
    bad.push(format!("{}.tsv.gz", "a".repeat(80)));
    for name in &bad {
        let err = parse_tampered(|d| entry_mut(d)["file_name"] = json!(name)).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadFileName { .. }),
            "{name:?} must be refused as a bad file name, got {err:?}"
        );
    }
    // Positive control: ordinary plain names pass.
    for name in ["tst.tsv.gz", "a-b.tsv.gz", "tst.2026.tsv.gz", "T1.tsv.gz"] {
        parse_tampered(|d| entry_mut(d)["file_name"] = json!(name))
            .unwrap_or_else(|e| panic!("{name} should be accepted: {e:?}"));
    }
}

#[test]
fn two_entries_may_not_share_a_file_name() {
    let a = fixture("AAA", 1, 1);
    let b = fixture("BBB", 1, 1);
    let mut be = b.entry("cleared");
    be["file_name"] = json!("AAA.tsv.gz"); // same file on a case-insensitive disk
    let err =
        Catalogue::parse(&catalogue_json(Some(BASE), vec![a.entry("cleared"), be])).unwrap_err();
    assert!(matches!(err, CatalogError::DuplicateFileName { .. }));
}

#[test]
fn a_digest_that_is_not_64_lowercase_hex_is_refused() {
    let good = "a".repeat(64);
    parse_tampered(|d| entry_mut(d)["sha256"] = json!(good)).expect("positive control");
    for bad in [
        "a".repeat(63),
        "a".repeat(65),
        "A".repeat(64),
        format!("{}g", "a".repeat(63)),
        String::new(),
        format!(" {}", "a".repeat(63)),
    ] {
        let err = parse_tampered(|d| entry_mut(d)["sha256"] = json!(bad)).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadDigest { ref field } if field.contains("sha256")),
            "{bad:?}: {err:?}"
        );
    }
    // The source zip digest is held to the same rule.
    let err =
        parse_tampered(|d| entry_mut(d)["source"]["usfm_zip_sha256"] = json!("xyz")).unwrap_err();
    assert!(matches!(err, CatalogError::BadDigest { .. }));
}

#[test]
fn sizes_and_counts_must_be_sane() {
    for size in [json!(0), json!(MAX_ASSET_BYTES + 1)] {
        let err = parse_tampered(|d| entry_mut(d)["size_bytes"] = size.clone()).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadSize { .. }),
            "{size}: {err:?}"
        );
    }
    parse_tampered(|d| entry_mut(d)["size_bytes"] = json!(MAX_ASSET_BYTES))
        .expect("the cap itself is allowed");
    let err = parse_tampered(|d| entry_mut(d)["verses"] = json!({"ot": 0, "nt": 0})).unwrap_err();
    assert!(matches!(err, CatalogError::BadCount { .. }));
    let err = parse_tampered(|d| entry_mut(d)["size_bytes"] = json!("12")).unwrap_err();
    assert!(
        matches!(err, CatalogError::WrongType { ref field, .. } if field.contains("size_bytes"))
    );
    let err = parse_tampered(|d| entry_mut(d)["size_bytes"] = json!(-1)).unwrap_err();
    assert!(matches!(err, CatalogError::WrongType { .. }));
}

#[test]
fn legal_review_must_be_cleared_or_pending() {
    let err = parse_tampered(|d| entry_mut(d)["legal_review"] = json!("approved")).unwrap_err();
    assert!(matches!(err, CatalogError::BadLegalReview { ref value, .. } if value == "approved"));
    let err = parse_tampered(|d| {
        entry_mut(d).as_object_mut().unwrap().remove("legal_review");
    })
    .unwrap_err();
    assert!(matches!(err, CatalogError::Missing { ref field } if field.contains("legal_review")));
    let err = parse_tampered(|d| entry_mut(d)["legal_review"] = json!(true)).unwrap_err();
    assert!(matches!(err, CatalogError::WrongType { .. }));
    let pending = parse_tampered(|d| entry_mut(d)["legal_review"] = json!("pending")).unwrap();
    assert_eq!(
        pending.find("TST").unwrap().legal_review,
        LegalReview::Pending
    );
}

#[test]
fn every_required_field_is_required_on_its_own() {
    for field in [
        "code",
        "name",
        "language",
        "language_name",
        "file_name",
        "size_bytes",
        "sha256",
        "verses",
        "licence",
        "legal_review",
        "source",
    ] {
        let err = parse_tampered(|d| {
            entry_mut(d).as_object_mut().unwrap().remove(field);
        })
        .unwrap_err();
        assert!(
            matches!(err, CatalogError::Missing { field: ref f } if f.contains(field)),
            "removing {field} must report that field missing, got {err:?}"
        );
    }
    for field in [
        "id",
        "name",
        "summary",
        "attribution_required",
        "share_alike",
    ] {
        let err = parse_tampered(|d| {
            entry_mut(d)["licence"]
                .as_object_mut()
                .unwrap()
                .remove(field);
        })
        .unwrap_err();
        assert!(
            matches!(err, CatalogError::Missing { field: ref f } if f.contains(field)),
            "removing licence.{field} must report that field missing, got {err:?}"
        );
    }
    // Optional fields may be absent or null.
    parse_tampered(|d| {
        let o = entry_mut(d).as_object_mut().unwrap();
        o.remove("attribution");
        o.remove("trademark_note");
        o.remove("modifications");
        o.remove("omitted_verses");
    })
    .expect("optional fields may be absent");
}

#[test]
fn the_base_url_must_be_an_https_url_without_a_query() {
    for bad in [
        "http://downloads.example.org/t/",
        "ftp://downloads.example.org/t/",
        "downloads.example.org/t/",
        "https://downloads.example.org/t/?x=1",
        "https://downloads.example.org/t/#frag",
        "https://user:pw@downloads.example.org/t/",
        "https://",
    ] {
        let f = fixture("TST", 1, 1);
        let err =
            Catalogue::parse(&catalogue_json(Some(bad), vec![f.entry("cleared")])).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadBaseUrl { .. }),
            "{bad:?} must be refused as a base URL, got {err:?}"
        );
    }
    // The test policy accepts a loopback http base, and nothing off the machine.
    let f = fixture("TST", 1, 1);
    let doc = catalogue_json(Some("http://127.0.0.1:9/t/"), vec![f.entry("cleared")]);
    assert!(
        Catalogue::parse(&doc).is_err(),
        "the product policy refuses it"
    );
    assert!(Catalogue::parse_with(&doc, UrlPolicy::allow_loopback_http_for_tests()).is_ok());
    let doc = catalogue_json(Some("http://example.org/t/"), vec![f.entry("cleared")]);
    assert!(Catalogue::parse_with(&doc, UrlPolicy::allow_loopback_http_for_tests()).is_err());
}

#[test]
fn the_number_of_entries_is_bounded() {
    let many: Vec<Value> = (0..=MAX_ENTRIES)
        .map(|i| {
            let f = fixture("TST", 1, 1);
            let mut e = f.entry("cleared");
            e["code"] = json!(format!("T{i:03}"));
            e["file_name"] = json!(format!("t{i:03}.tsv.gz"));
            e
        })
        .collect();
    let err = Catalogue::parse(&catalogue_json(Some(BASE), many)).unwrap_err();
    assert!(matches!(err, CatalogError::TooManyEntries { .. }));
}

#[test]
fn text_fields_are_length_bounded() {
    let err = parse_tampered(|d| entry_mut(d)["name"] = json!("x".repeat(100_000))).unwrap_err();
    assert!(matches!(err, CatalogError::TooLong { ref field } if field.contains("name")));
}

#[test]
fn the_urls_shown_to_the_user_must_be_https() {
    // The licence page and the source page are rendered as links, so only https ones are allowed.
    for bad in [
        "http://creativecommons.org/licenses/by-sa/4.0/",
        "javascript:alert(1)",
        "ftp://example.org/licence",
        "//example.org/licence",
        "not a url",
    ] {
        let err = parse_tampered(|d| entry_mut(d)["licence"]["url"] = json!(bad)).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadUrl { ref field } if field.contains("licence.url")),
            "{bad:?}: {err:?}"
        );
        let err = parse_tampered(|d| entry_mut(d)["source"]["url"] = json!(bad)).unwrap_err();
        assert!(
            matches!(err, CatalogError::BadUrl { ref field } if field.contains("source.url")),
            "{bad:?}: {err:?}"
        );
    }
    // Positive controls: an https URL passes, and a licence with no page (public domain) is fine.
    parse_tampered(|d| entry_mut(d)["licence"]["url"] = json!("https://example.org/licence"))
        .unwrap();
    parse_tampered(|d| entry_mut(d)["licence"]["url"] = Value::Null).unwrap();
}
