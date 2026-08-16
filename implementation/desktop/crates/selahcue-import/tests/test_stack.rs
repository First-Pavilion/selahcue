//! The stack gate: the third resource the importer spends on an attacker's say-so, and the last
//! one to get a number.
//!
//! # Why this file exists
//!
//! A stack overflow is not a catchable panic. It is an immediate process abort — `catch_unwind`
//! cannot contain it, the import lock and the panic belt in the shell cannot contain it, and the
//! typed-error guarantee that every import failure degrades to a report is simply void. On the
//! operator console that is the whole application going away mid-service. So stack is a merge
//! gate exactly like the byte caps and the memory budget, and for the same reason: it is a
//! resource an attacker-supplied file can drive.
//!
//! It exists because it did not, and the bill arrived. The suite's only stack control was one test
//! spawning a 128 KiB thread — a number picked, never measured — around an import that needs
//! 97 KiB in the `debug` profile on aarch64 and 117 KiB on x86_64:
//!
//! ```text
//!   ubuntu   x86_64   128 KiB usable   needs 117 KiB    passed, 11 KiB to spare
//!   macos    aarch64  128 KiB usable   needs  97 KiB    passed, 31 KiB to spare
//!   windows  x86_64   104 KiB usable   needs 117 KiB+   ABORTED
//! ```
//!
//! (The two `needs` figures are measured here; the Windows row carries the x86_64 measurement,
//! which Win64 can only exceed. The 104 is measured too, in the sense that it is what `std`'s own
//! source says a 128 KiB Windows thread has left after `SetThreadStackGuarantee` and a guard page.)
//!
//! Windows is the only platform that is both the expensive architecture and the one that keeps
//! 24 KiB of every thread back for itself, so it is the only one where the two margins multiplied
//! out to less than one. `STATUS_STACK_OVERFLOW` then took the whole test binary down on the
//! platform this project ships an installer for.
//!
//! # What makes a green run here mean something on Windows
//!
//! **Every thread below is spawned at `budget - HOST_STACK_RESERVATION`.** Windows keeps 20 KiB
//! of every thread's reservation back for `std`'s own overflow handler, plus a guard page, so
//! `stack_size(N)` yields materially less than `N` there and rather more than that here.
//! Subtracting it means these tests run on the *usable* stack of the tightest platform, and a
//! green run on a developer's Mac is evidence about the one that broke. A test that spawns the
//! full budget and passes locally is precisely the reassurance that failed last time.
//!
//! # The two budgets, and which one can actually regress
//!
//! [`MAX_IMPORT_STACK_BYTES`] covers the whole path, and is dominated by one fixed cost — the
//! ~90 KiB `flate2::Decompress::new` spends building `miniz_oxide`'s `InflateState` in stack
//! temporaries before boxing it. No input changes that number, which is what makes it useless as
//! a regression control on its own: a parser that started recursing a frame per element would have
//! several hundred kilobytes to hide in before it showed.
//!
//! [`MAX_WALK_STACK_BYTES`] is the one that bites. Fed a STORED archive the inflater is never
//! reached, so what remains is exactly the input-driven part — the central-directory walk, the XML
//! pull loop, the slide and picture loops, the deck build. That is the number
//! [`MAX_XML_DEPTH`](selahcue_import::limits::MAX_XML_DEPTH) exists to protect, and it is asserted
//! here against inputs whose depth and breadth vary by four orders of magnitude.
//!
//! # Both budgets are sized from the worst architecture, not this one
//!
//! The walk needs 3 KiB on aarch64 and 21 KiB on x86_64 — the same work, seven times the stack.
//! That gap was found by building this file for `x86_64-apple-darwin` and running it under
//! Rosetta, and it is worth doing again before either budget is trimmed: a margin that looks
//! comfortable on the machine in front of you can be 1.1x somewhere else, which is the entire
//! content of the bug this file exists for.

#![allow(clippy::unwrap_used)]

mod support;

use support::{Entry, PptxBuilder, SlideSpec};

use selahcue_import::limits::{
    HOST_STACK_RESERVATION, MAX_IMPORT_STACK_BYTES, MAX_WALK_STACK_BYTES, MAX_XML_DEPTH,
    MAX_XML_EVENTS_PER_PART,
};
use selahcue_import::{
    build_deck, ImportError, ImportReport, ImportSource, MemorySource, RecordingSink,
};
use selahcue_present::{MediaRef, Theme};

/// Run one import on a thread whose usable stack matches `budget` **on the tightest platform we
/// ship**, and return its report.
///
/// The thread is deliberately NAMED. The unnamed one is what produced `thread '<unknown>' has
/// overflowed its stack` in CI, a message that names neither the test nor the input and cost real
/// time to attribute.
fn import_within(budget: usize, label: &'static str, bytes: Vec<u8>) -> Result<ImportReport, ()> {
    let stack = budget
        .checked_sub(HOST_STACK_RESERVATION)
        .expect("a budget below what the host reserves is not a budget");
    std::thread::Builder::new()
        .name(format!("import-{label}"))
        .stack_size(stack)
        .spawn(move || {
            let mut src = MemorySource::new(bytes);
            let mut sink = RecordingSink::new();
            let doc = selahcue_import::read_pptx(
                &mut src,
                ImportSource::Pptx {
                    name: "Sunday Service".into(),
                },
                &mut sink,
                &|| false,
            )
            .map_err(|_: ImportError| ())?;
            Ok(
                build_deck(doc, &Theme::classic(), "Sunday Service", &|slot| {
                    MediaRef::new(&format!("/app/media/import-{}.png", slot.0))
                })
                .1,
            )
        })
        .unwrap()
        .join()
        .unwrap_or_else(|_| panic!("`{label}` must not take the process down"))
}

/// A slide part `depth` levels of `<p:grpSp>` deep, with real text at the bottom.
fn nested_slide(depth: usize) -> String {
    let mut xml =
        String::from(r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree>"#);
    for _ in 0..depth {
        xml.push_str("<p:grpSp>");
    }
    xml.push_str(r#"<p:sp><p:txBody><a:p><a:r><a:t>DEEP</a:t></a:r></a:p></p:txBody></p:sp>"#);
    for _ in 0..depth {
        xml.push_str("</p:grpSp>");
    }
    xml.push_str("</p:spTree></p:cSld></p:sld>");
    xml
}

/// The walk, on a STORED package, against inputs whose shape varies enormously.
///
/// **The assertion is that the budget does not move.** Every case here runs on the same usable
/// stack; if any of them needed more than a two-element document does, stack use would depend on
/// the input, which is the definition of the bug this bounds. On both architectures measured, the
/// trivial case and the ten-thousand-deep one need *exactly* the same stack.
///
/// A walker recursing one frame per level would want megabytes over the ten-thousand-deep case and
/// abort on every platform — which is the point, because the control it replaces could only fail
/// on the platform with the smallest stack, and did. Note what that implies about
/// [`MAX_XML_DEPTH`]: at 256 levels a recursive walker would breach this budget too, so the depth
/// cap was never what made deep XML safe here. Iteration is; the cap is the backstop.
#[test]
fn the_walks_stack_use_does_not_depend_on_the_input() {
    let cases: Vec<(&'static str, Vec<u8>)> = vec![
        (
            "trivial",
            PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .build(),
        ),
        (
            "at-the-depth-cap",
            PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .slide(SlideSpec {
                    raw_xml: Some(nested_slide(MAX_XML_DEPTH - 4)),
                    ..Default::default()
                })
                .build(),
        ),
        (
            "far-past-the-depth-cap",
            PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .slide(SlideSpec {
                    raw_xml: Some(nested_slide(10_000)),
                    ..Default::default()
                })
                .build(),
        ),
        (
            "element-flood",
            PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .slide(SlideSpec {
                    raw_xml: Some({
                        let mut xml = String::from(
                            r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree><p:sp><p:txBody>"#,
                        );
                        for _ in 0..(MAX_XML_EVENTS_PER_PART + 10) {
                            xml.push_str("<a:x/>");
                        }
                        xml.push_str("</p:txBody></p:sp></p:spTree></p:cSld></p:sld>");
                        xml
                    }),
                    ..Default::default()
                })
                .build(),
        ),
        (
            // Attribute normalisation is the one place in the reader's dependency that genuinely
            // recurses — `quick_xml::escape::normalize_attr_step` calls itself to expand an entity
            // inside an attribute value. It is bounded: `normalized_value` seeds that recursion at
            // a depth of ONE and only the predefined entities resolve, because a DTD-declared one
            // would have needed a DOCTYPE and those are refused on the raw bytes. This case is
            // here so the bound is measured rather than read — a hundred thousand entity
            // references in one attribute value, on the same stack as everything else.
            "entity-dense-attributes",
            PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .slide(SlideSpec {
                    raw_xml: Some(format!(
                        r#"<?xml version="1.0"?><p:sld xmlns:p="p" xmlns:a="a" show="{}"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>X</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"#,
                        "&amp;&lt;&#65;&gt;\t\r\n".repeat(100_000)
                    )),
                    ..Default::default()
                })
                .build(),
        ),
        ("many-slides", {
            let mut b = PptxBuilder::new().stored();
            for i in 0..200 {
                b = b.slide(SlideSpec {
                    title: Some(format!("Slide {i}")),
                    body: (0..30).map(|l| format!("line {l} of slide {i}")).collect(),
                    notes: Some("n".repeat(2000)),
                    ..Default::default()
                });
            }
            b.build()
        }),
        ("many-entries", {
            let mut b = PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]));
            for i in 0..1_000 {
                b = b.entry(Entry::stored(&format!("ppt/junk/{i}.bin"), b"x"));
            }
            b.build()
        }),
    ];

    for (label, bytes) in cases {
        let report = import_within(MAX_WALK_STACK_BYTES, label, bytes)
            .unwrap_or_else(|()| panic!("`{label}` must import, not fail"));
        assert!(
            report.slides_imported >= 1,
            "`{label}` must produce a deck, or the walk was never exercised"
        );
    }
}

/// The whole path — inflater included — inside the budget the shell must honour.
///
/// The battery is the hostile one, not one input: a bomb whose header lies, an entry flood, a
/// deeply nested part, an encrypted member, an oversized image and a real photograph, each of
/// which takes a different route through the reader.
#[test]
fn the_whole_hostile_battery_fits_the_declared_import_budget() {
    let png = support::png(64, 64);
    let jpeg = support::jpeg(64, 64, Some(6));

    let cases: Vec<(&'static str, Vec<u8>)> = vec![
        (
            "deflated-text",
            PptxBuilder::new()
                .slide(SlideSpec::text("Good", &["body", "and more"]))
                .build(),
        ),
        (
            "nested-part",
            PptxBuilder::new()
                .slide(SlideSpec::text("Good", &["body"]))
                .slide(SlideSpec {
                    raw_xml: Some(nested_slide(10_000)),
                    ..Default::default()
                })
                .build(),
        ),
        (
            "lying-header-bomb",
            PptxBuilder::new()
                .slide(SlideSpec {
                    title: Some("Text survives".into()),
                    images: vec![("bomb.png".into(), Vec::new())],
                    ..Default::default()
                })
                .replacing(Entry::raw_deflated(
                    "ppt/media/bomb.png",
                    support::deflate_lowish_ratio(64 * 1024 * 1024),
                    1024,
                ))
                .build(),
        ),
        (
            "images",
            PptxBuilder::new()
                .slide(SlideSpec {
                    title: Some("Pictures".into()),
                    images: vec![("a.png".into(), png), ("b.jpg".into(), jpeg)],
                    ..Default::default()
                })
                .build(),
        ),
        (
            "encrypted-member",
            PptxBuilder::new()
                .slide(SlideSpec::text("Good", &["body"]))
                .entry(Entry::deflated("ppt/media/locked.png", b"x").encrypted())
                .build(),
        ),
        ("entry-flood", {
            let mut b = PptxBuilder::new().slide(SlideSpec::text("Good", &["body"]));
            for i in 0..1_000 {
                b = b.entry(Entry::deflated(&format!("ppt/junk/{i}.bin"), b"xxxx"));
            }
            b.build()
        }),
    ];

    for (label, bytes) in cases {
        let report = import_within(MAX_IMPORT_STACK_BYTES, label, bytes)
            .unwrap_or_else(|()| panic!("`{label}` must import, not fail"));
        assert!(
            report.slides_imported >= 1,
            "`{label}` must produce a deck, or the path was never exercised"
        );
    }
}

/// An import that legitimately FAILS must fail inside the budget too.
///
/// The threat model's rule is that every failure degrades to a typed error leaving the library and
/// live state untouched. A typed error returned from a thread that has already overflowed its
/// stack does not exist, so the failure paths need the same gate as the success ones — and they
/// take different routes: refusal before the walk, refusal during it, and nothing usable at the
/// end.
#[test]
fn the_failure_paths_degrade_to_a_typed_error_inside_the_budget() {
    let cases: Vec<(&'static str, Vec<u8>)> = vec![
        ("not-an-archive", b"this is not a zip file at all".to_vec()),
        ("truncated", {
            let mut bytes = PptxBuilder::new()
                .stored()
                .slide(SlideSpec::text("Good", &["body"]))
                .build();
            bytes.truncate(bytes.len() / 2);
            bytes
        }),
        (
            "no-slides",
            support::zip(&[Entry::stored("docProps/app.xml", b"<x/>")]),
        ),
    ];

    for (label, bytes) in cases {
        assert!(
            import_within(MAX_WALK_STACK_BYTES, label, bytes).is_err(),
            "`{label}` is expected to fail — and it must do so by returning, not by aborting"
        );
    }
}
