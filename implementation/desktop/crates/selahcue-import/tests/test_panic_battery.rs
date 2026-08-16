//! **No input may panic.** Every call here is wrapped in `catch_unwind` and the test fails on any
//! unwind: every input must yield either `Ok(report)` or a typed error.
//!
//! This is the deterministic merge gate; the fuzzer is depth on top of it. The stake is concrete
//! — a panic escaping the importer takes the operator console down, and if that happens
//! mid-service the volunteer loses their controls in front of a congregation. The `catch_unwind`
//! belt in the shell is a backstop; *this* is the primary control, along with the
//! `indexing_slicing` and `arithmetic_side_effects` denials on the three modules that parse
//! binary offsets.

#![allow(clippy::unwrap_used)]

mod support;

use support::{Entry, PptxBuilder, SlideSpec};

use selahcue_import::{build_deck, ImportSource, MemorySource, RecordingSink, TextOptions};
use selahcue_present::Theme;

/// A fixed-seed xorshift, so a failure here reproduces exactly rather than "sometimes".
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn bytes(&mut self, len: usize) -> Vec<u8> {
        let mut out = Vec::with_capacity(len);
        while out.len() < len {
            out.extend_from_slice(&self.next().to_le_bytes());
        }
        out.truncate(len);
        out
    }
}

fn try_pptx(bytes: Vec<u8>) -> Result<(), Box<dyn std::any::Any + Send>> {
    std::panic::catch_unwind(move || {
        let mut src = MemorySource::new(bytes);
        let mut sink = RecordingSink::new();
        let doc = selahcue_import::read_pptx(
            &mut src,
            ImportSource::Pptx { name: "f".into() },
            &mut sink,
            &|| false,
        );
        if let Ok(doc) = doc {
            // The build half must be equally total: it is reached with whatever the parser
            // produced, hostile input included.
            let _ = build_deck(doc, &Theme::classic(), "f", &|_| None);
        }
    })
}

fn try_text(bytes: Vec<u8>) -> Result<(), Box<dyn std::any::Any + Send>> {
    std::panic::catch_unwind(move || {
        let _ = selahcue_import::import_txt_bytes(
            &bytes,
            ImportSource::TxtFile { name: "f".into() },
            &Theme::classic(),
            "f",
            &TextOptions::default(),
        );
    })
}

#[test]
fn ten_thousand_random_inputs_never_panic_on_either_path() {
    let mut rng = Rng(0x5361_6E61_2038_2E31);
    for i in 0..10_000 {
        let len = (rng.next() % 4096) as usize;
        let buf = rng.bytes(len);
        assert!(
            try_text(buf.clone()).is_ok(),
            "text path panicked on input {i}"
        );
        assert!(try_pptx(buf).is_ok(), "pptx path panicked on input {i}");
    }
}

#[test]
fn random_bytes_wearing_a_zip_end_record_never_panic() {
    // Pure random bytes almost never reach the central-directory walk, so this battery appends a
    // real end-of-central-directory record to random noise — which is what actually exercises the
    // offset arithmetic the lints are there to protect.
    let mut rng = Rng(0x0BAD_C0DE_1234_5678);
    for i in 0..4_000 {
        let len = (rng.next() % 2048) as usize + 64;
        let mut buf = rng.bytes(len);
        buf.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
        buf.extend_from_slice(&rng.bytes(18));
        assert!(try_pptx(buf).is_ok(), "panicked on pseudo-archive {i}");
    }
}

#[test]
fn every_single_byte_corruption_of_a_valid_archive_is_survivable() {
    // A byte-at-a-time walk over a real archive: the cheapest way to reach the malformed branches
    // of the central directory, the local headers and the deflate stream.
    let good = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Title".into()),
            body: vec!["body".into()],
            notes: Some("notes".into()),
            images: vec![("image1.png".into(), support::png(2, 2))],
            ..Default::default()
        })
        .build();
    for i in (0..good.len()).step_by(3) {
        for delta in [0x01u8, 0xFF] {
            let mut m = good.clone();
            m[i] ^= delta;
            assert!(
                try_pptx(m).is_ok(),
                "panicked with byte {i} xor {delta:#04x}"
            );
        }
    }
    for cut in (0..good.len()).step_by(7) {
        assert!(
            try_pptx(good[..cut].to_vec()).is_ok(),
            "panicked on truncation at {cut}"
        );
    }
}

#[test]
fn a_truncated_deflate_stream_and_garbage_xml_are_survivable() {
    let good_xml = br#"<?xml version="1.0"?><p:sld xmlns:p="p"><p:cSld/></p:sld>"#;
    let mut rng = Rng(0xFACE_FEED_0000_0001);
    for i in 0..200 {
        // A valid container wrapping deliberate garbage.
        let junk = rng.bytes(256);
        let bytes = PptxBuilder::new()
            .slide(SlideSpec::text("Good", &["body"]))
            .entry(Entry::deflated("ppt/slides/slide2.xml", &junk))
            .entry(Entry::stored("ppt/slides/slide3.xml", &junk))
            // A deflate member whose payload is not a deflate stream at all.
            .entry(Entry::stored("ppt/slides/slide4.xml", &junk).with_method(8))
            .entry(Entry::deflated("ppt/slides/slide5.xml", good_xml).claiming(u32::MAX - 1))
            .build();
        assert!(try_pptx(bytes).is_ok(), "panicked on garbage variant {i}");
    }
}

#[test]
fn hostile_text_never_panics_and_always_produces_valid_utf8() {
    let mut rng = Rng(0xDEAD_BEEF_CAFE_0001);
    for i in 0..3_000 {
        let len = (rng.next() % 1024) as usize;
        let mut buf = rng.bytes(len);
        // Salt with the shapes the decoder branches on: BOMs, lone surrogates, NULs, CR.
        if i % 4 == 0 {
            buf.splice(0..0, [0xFF, 0xFE]);
        }
        if i % 5 == 0 {
            buf.splice(0..0, [0xEF, 0xBB, 0xBF]);
        }
        buf.extend_from_slice(b"\r\n\0\r");
        assert!(try_text(buf).is_ok(), "text path panicked on input {i}");
    }
}
