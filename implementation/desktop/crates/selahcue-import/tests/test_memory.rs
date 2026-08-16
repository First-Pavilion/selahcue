//! The bounded-memory gate: the caps must **compose** to a documented working set, asserted
//! structurally, per the repository's no-unbounded-growth rule and the security review's §6.6.
//!
//! The design's arithmetic for a worst-case import is:
//!
//! ```text
//!   archive file                  ~0        read through a ByteSource in 64 KiB chunks
//! + one inflated XML part         16 MiB    MAX_XML_PART_BYTES
//! + one encoded image             16 MiB    MAX_IMAGE_ENCODED_BYTES
//! + one decoded image             64 MiB    16 Mpx x 4 bytes RGBA
//! + EXIF transpose buffer         64 MiB    orientations 5-8 only, where max_pixels is halved
//! + accumulated ImportedDocument  ~10 MiB   500 slides x (2 KB text + 4 KB notes)
//!   ────────────────────────────────────────
//!   ~170 MiB peak, one import at a time
//! ```
//!
//! against a ~350 MiB budget. Two of those lines are load-bearing design choices rather than
//! optimisations: the byte source removes the whole-file term (without it the 512 MiB admission
//! cap would be in the working set before parsing began), and staging images one at a time
//! removes the arena term (holding every extracted image would be 200 × 16 MiB).
//!
//! This is a separate test binary holding exactly **one** test, on purpose: a global allocator is
//! per-binary and its counters are process-wide, so a second concurrently-running test would make
//! the measurement meaningless.

#![allow(clippy::unwrap_used)]

mod support;

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

use support::{PptxBuilder, SlideSpec};

use selahcue_import::{build_deck, ImportSource, MemorySource, RecordingSink, TextOptions};
use selahcue_present::Theme;

static LIVE: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
/// Bytes handed out since the last [`reset`], counting every allocation whether or not it is
/// freed again a moment later.
///
/// [`PEAK`] is blind to churn by construction: a buffer allocated and dropped once per entry never
/// raises the high-water mark, however many entries there are. That is the shape of repeated work
/// this crate refuses — a per-member inflater, a per-slide arena — so it needs its own counter.
static CHURN: AtomicUsize = AtomicUsize::new(0);

struct Tracking;

fn bump(delta: usize) {
    let live = LIVE.fetch_add(delta, Ordering::Relaxed) + delta;
    PEAK.fetch_max(live, Ordering::Relaxed);
    CHURN.fetch_add(delta, Ordering::Relaxed);
}

unsafe impl GlobalAlloc for Tracking {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        bump(layout.size());
        System.alloc(layout)
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        LIVE.fetch_sub(layout.size(), Ordering::Relaxed);
        System.dealloc(ptr, layout)
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        if new_size > layout.size() {
            bump(new_size - layout.size());
        } else {
            LIVE.fetch_sub(layout.size() - new_size, Ordering::Relaxed);
        }
        System.realloc(ptr, layout, new_size)
    }
}

#[global_allocator]
static ALLOC: Tracking = Tracking;

/// The design's documented ceiling. Asserted rather than assumed, so a future change that starts
/// buffering fails here instead of on a church PC mid-service.
const PEAK_BUDGET: usize = 350 * 1024 * 1024;

/// The budget for the sections that feed the reader a HOSTILE archive.
///
/// [`PEAK_BUDGET`] cannot do that job: it is the whole import's ceiling, and none of the benign
/// worst cases here comes within an order of magnitude of it, so a defect that put two hundred
/// mebibytes of attacker-sized buffer in the working set would sail under it unnoticed. These
/// sections are structural — the reader must allocate essentially *nothing* on an archive's say-so
/// — so they get a budget sized to what a correct reader actually needs, which is a few read
/// buffers and a bounded entry table.
const HOSTILE_BUDGET: usize = 32 * 1024 * 1024;

/// Live bytes at the last [`reset`], so the peak can be reported ABOVE it.
static BASE: AtomicUsize = AtomicUsize::new(0);

fn reset() {
    let live = LIVE.load(Ordering::Relaxed);
    BASE.store(live, Ordering::Relaxed);
    PEAK.store(live, Ordering::Relaxed);
    CHURN.store(0, Ordering::Relaxed);
}

/// Bytes allocated since the last [`reset`], freed or not.
fn churn_since_reset() -> usize {
    CHURN.load(Ordering::Relaxed)
}

/// Peak live bytes since the last [`reset`], **above the baseline that was already live then**.
///
/// Subtracting the baseline captured at reset, not the CURRENT live figure. Subtracting the
/// current one — as this did — quietly cancels every allocation that is still alive at the moment
/// of measurement, which on this path is the deck and the report: exactly the things a
/// buffering regression would leave behind. The metric therefore under-reported precisely the
/// growth it exists to catch.
fn peak_since_reset() -> usize {
    PEAK.load(Ordering::Relaxed)
        .saturating_sub(BASE.load(Ordering::Relaxed))
}

#[test]
fn a_worst_case_import_stays_inside_the_documented_budget() {
    // 1. A wide text import: the slide cap, the line cap and the character cap all at once.
    reset();
    let mut text = String::new();
    for i in 0..(selahcue_import::limits::MAX_IMPORT_SLIDES + 20) {
        text.push_str(&format!("Slide {i}\n"));
        for line in 0..80 {
            text.push_str(&"x".repeat(64));
            text.push(' ');
            text.push_str(&format!("{line}\n"));
        }
        text.push('\n');
    }
    let source_bytes = text.len();
    let (deck, report) = selahcue_import::import_text(
        &text,
        ImportSource::Clipboard,
        &Theme::classic(),
        "Peak",
        &TextOptions::default(),
    )
    .unwrap();
    let text_peak = peak_since_reset();
    assert_eq!(deck.len(), selahcue_import::limits::MAX_IMPORT_SLIDES);
    assert!(deck.within_bounds());
    assert!(
        !report.is_lossless(),
        "the caps must be visible in the report"
    );
    assert!(
        text_peak < PEAK_BUDGET,
        "text import peaked at {text_peak} bytes over a {source_bytes}-byte source"
    );

    // 1b. A file with NO blank line anywhere — the splitter's worst shape, because every line
    //     accumulates into one group before anything is flushed, so nothing is bounded by the
    //     per-slide clamps until the very end. The absolute budget cannot see a regression here
    //     (a 16 MiB `.txt` is the admission cap and a bad multiple of it still fits 350 MiB), so
    //     this is asserted as a RATIO to the input: the transient must stay proportionate to the
    //     source rather than a growing multiple of it.
    let mut wide = String::new();
    for i in 0..40_000 {
        wide.push_str(&format!("line {i} of a file with no blank line anywhere\n"));
    }
    let wide_bytes = wide.len();
    reset();
    let (deck, _) = selahcue_import::import_text(
        &wide,
        ImportSource::Clipboard,
        &Theme::classic(),
        "Wide",
        &TextOptions::default(),
    )
    .unwrap();
    let wide_peak = peak_since_reset();
    assert_eq!(
        deck.len(),
        1,
        "no blank line anywhere means exactly one slide"
    );
    assert!(deck.within_bounds());
    assert!(
        wide_peak < wide_bytes.saturating_mul(12),
        "the splitter peaked at {wide_peak} bytes over a {wide_bytes}-byte blank-line-free source"
    );

    // 2. A pptx with many slides and many distinct images: the shape that would build an arena if
    //    images were collected rather than staged one at a time.
    reset();
    let png = support::png(64, 64);
    let mut builder = PptxBuilder::new();
    for i in 0..120 {
        builder = builder.slide(SlideSpec {
            title: Some(format!("Slide {i}")),
            body: (0..40).map(|l| format!("line {l} of slide {i}")).collect(),
            notes: Some("x".repeat(3000)),
            images: vec![(format!("image{i}.png"), png.clone())],
            ..Default::default()
        });
    }
    let archive = builder.build();
    let archive_len = archive.len();
    reset();
    let mut src = MemorySource::new(archive);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Peak".into(),
        },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let staged = sink.len();
    let (deck, report) = build_deck(doc, &Theme::classic(), "Peak", &|_| None);
    let pptx_peak = peak_since_reset();

    assert_eq!(deck.len(), 120);
    assert_eq!(staged, 120, "each distinct image is staged exactly once");
    assert!(deck.within_bounds());
    assert!(report.notices.len() <= selahcue_import::limits::MAX_REPORT_ITEMS);
    assert!(
        report.skipped.len() <= selahcue_import::limits::MAX_REPORT_ITEMS,
        "the report must not itself be an unbounded buffer"
    );
    assert!(
        pptx_peak < PEAK_BUDGET,
        "pptx import peaked at {pptx_peak} bytes over a {archive_len}-byte archive"
    );

    // 3. The report's own bound, under a deck that drops far more than it can list.
    reset();
    let mut flood = PptxBuilder::new();
    for _ in 0..400 {
        flood = flood.slide(SlideSpec {
            title: Some("Chart".into()),
            graphic_uri: Some("http://schemas.openxmlformats.org/drawingml/2006/chart".into()),
            ..Default::default()
        });
    }
    let mut src = MemorySource::new(flood.build());
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Flood".into(),
        },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let (_, report) = build_deck(doc, &Theme::classic(), "Flood", &|_| None);
    assert_eq!(
        report.skipped.len(),
        selahcue_import::limits::MAX_REPORT_ITEMS,
        "drops past the cap are counted, not listed"
    );
    assert!(report.skipped_overflow > 0);
    assert_eq!(report.severity(), selahcue_import::Severity::Material);
    assert!(peak_since_reset() < PEAK_BUDGET);

    // 3b. The reader's WORKING SET is per ARCHIVE, not per entry.
    //
    //     A high-water mark cannot see this and never could: the reader allocated two 64 KiB chunk
    //     buffers and a whole `flate2::Decompress` on entry to every member read, filled them, and
    //     dropped them again before the next member, so `PEAK` was identical whether that happened
    //     once or four thousand times. What it costs is churn — and a `Decompress` is not a cheap
    //     churn, because `miniz_oxide`'s `InflateState` is a 32 KiB LZ dictionary plus the Huffman
    //     tables, allocated and zeroed every time.
    //
    //     A deck reads at least two parts per slide, so this is roughly 172 KiB of
    //     allocate-fill-free per slide on the path that handles attacker-supplied bytes. The
    //     assertion is stated per part read, so it stays meaningful if the fixture changes.
    reset();
    let mut many = PptxBuilder::new();
    for i in 0..150 {
        many = many.slide(SlideSpec::text(&format!("Slide {i}"), &["one short line"]));
    }
    let archive = many.build();
    reset();
    let mut src = MemorySource::new(archive);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Churn".into(),
        },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let churn = churn_since_reset();
    assert_eq!(doc.slides.len(), 150);
    // Two parts per slide (the slide and its `.rels`) plus the presentation and its own.
    let parts_read = 150 * 2 + 2;
    // Half a chunk buffer per part, which sits between the two behaviours rather than beside
    // either: measured at 7.6 KiB per part with the buffers and the inflater owned by the archive,
    // and at 177 KiB per part with them allocated per entry. Four times over the first and five
    // times under the second — a regression here cannot be a rounding difference.
    let budget = parts_read * 32 * 1024;
    assert!(
        churn < budget,
        "reading {parts_read} parts churned {churn} bytes ({} KiB per part) — the chunk buffers \
         and the inflater must belong to the archive, not to each entry",
        churn / parts_read / 1024
    );

    // 4. ONE large image, and the assertion that the importer **never decodes it**.
    //
    //    The importer used to validate every embedded image by decoding it in full and throwing
    //    the pixels away — on a decoder deliberately pinned to one scalar code path — only for the
    //    render path to decode the same bytes again later. That was measured at over 99 % of import
    //    time: eleven seconds for 150 × 16 MP on a fast machine, around fifteen at the cap, which
    //    extrapolates past a thirty-second timeout on church hardware and then keeps nothing.
    //
    //    A functional test cannot see the difference — the probe and the decode report the same
    //    dimensions, which is the point of `test_probe.rs`. Only a weighing machine can, so this
    //    is where the property lives: a 4 Mpx image whose RGBA plane alone is sixteen mebibytes
    //    must cost less than one such plane, twice over.
    let big = support::png(2048, 2048);
    let big_encoded = big.len();
    /// The RGBA plane a decode of this image would allocate — and the decoder's own intermediate
    /// buffer is a second one the same size.
    const DECODED_PLANE: usize = 2048 * 2048 * 4;
    let archive = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("A real photograph".into()),
            images: vec![("big.png".into(), Vec::new())],
            ..Default::default()
        })
        // STORED, as a real `.pptx` holds its photographs: an already-compressed image gains
        // nothing from deflate, and PowerPoint stores them. Deflating this one would also make the
        // fixture trip the ratio guard rather than reach the decoder, and the whole point of this
        // section is to get a real decode into the measurement.
        .replacing(support::Entry::stored("ppt/media/big.png", &big))
        .build();
    reset();
    let mut src = MemorySource::new(archive);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx { name: "Big".into() },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let big_peak = peak_since_reset();
    assert_eq!(sink.len(), 1, "the image was really admitted and staged");
    assert_eq!(doc.slides.len(), 1);
    assert_eq!(
        (sink.staged()[0].1.width, sink.staged()[0].1.height),
        (2048, 2048),
        "and its dimensions came from the header, not from a decode"
    );
    assert!(
        big_peak < PEAK_BUDGET,
        "a 4 Mpx image peaked at {big_peak} bytes"
    );
    // Bounded against the ENCODED size, which is what a correct import actually holds: the bytes
    // once while reading them and once inside the sink. A decode adds two {DECODED_PLANE}-byte
    // planes on top of that — several times the encoded figure — so the two outcomes are far
    // apart and this discriminates between them rather than sitting between two similar numbers.
    assert!(
        big_peak < big_encoded * 3,
        "a 4 Mpx image peaked at {big_peak} bytes over {big_encoded} encoded; a decode would add \
         two {DECODED_PLANE}-byte planes, so the importer is decoding pixels it does not need — \
         which was over 99 % of import time"
    );

    // 4b. And the same weighing on the negative path, which is what makes "never handed to a
    //     decoder" a measured property rather than a claim in a test's name. There is now exactly
    //     ONE signature allowlist — inside `probe_image` — so a format off it cannot reach a
    //     decoder at all, and the scales say so.
    let gif = {
        let mut v = b"GIF89a".to_vec();
        v.extend(std::iter::repeat_n(0x41u8, 4 * 1024 * 1024));
        v
    };
    let gif_len = gif.len();
    let archive = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Not an image".into()),
            images: vec![("thing.gif".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(support::Entry::stored("ppt/media/thing.gif", &gif))
        .build();
    reset();
    let mut src = MemorySource::new(archive);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx { name: "Gif".into() },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let gif_peak = peak_since_reset();
    assert!(sink.is_empty(), "an unsupported format is never staged");
    let (_, report) = build_deck(doc, &Theme::classic(), "Gif", &|_| None);
    assert!(report
        .skipped
        .iter()
        .any(|s| s.kind == selahcue_import::SkipKind::ImageFormatUnsupported));
    assert!(
        gif_peak < gif_len * 3,
        "an off-allowlist image peaked at {gif_peak} bytes over {gif_len} encoded — anything \
         beyond the read buffer itself means a decoder saw the bytes"
    );

    // --- the hostile half: allocations an archive asks for, under a budget it cannot reach ---

    // 5. A central directory the archive merely CLAIMS is 200 MiB, inside a 512 MiB file. The
    //    entry-count cap does not bound this at all — the archive declares one entry — so a reader
    //    that allocates the directory it was told about holds 200 MiB before parsing a byte. The
    //    file is synthesised rather than held, so what this measures is the importer alone.
    reset();
    let mut src = support::HostileDirectory::lying_size(512 * 1024 * 1024, 200 * 1024 * 1024);
    let mut sink = RecordingSink::new();
    let outcome = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Lying".into(),
        },
        &mut sink,
        &|| false,
    );
    let claimed_peak = peak_since_reset();
    assert!(outcome.is_err(), "a directory of nothing is not an archive");
    assert!(
        claimed_peak < HOSTILE_BUDGET,
        "a 200 MiB declared central directory cost {claimed_peak} bytes — the size an archive \
         CLAIMS may never size an allocation"
    );

    // 6. And the same directory made real, with every name over the reader's name cap: four
    //    thousand records of 65 000 bytes each. This is the measured worst case — a 507 MiB file
    //    that peaked at 1015 MiB against a 350 MiB budget, because the directory was buffered
    //    whole AND every name became two `String`s before the length cap was consulted.
    reset();
    let mut src = support::HostileDirectory::long_names(4090, 65_000);
    let mut sink = RecordingSink::new();
    let outcome = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Names".into(),
        },
        &mut sink,
        &|| false,
    );
    let names_peak = peak_since_reset();
    assert!(outcome.is_err(), "no slide part is reachable in there");
    assert!(
        names_peak < HOSTILE_BUDGET,
        "a directory of 4090 x 65 000-byte names cost {names_peak} bytes — the name cap must be \
         consulted BEFORE the allocation it bounds"
    );

    // 7. The lying-header bomb: a member declaring one kilobyte that inflates to sixty-four
    //    mebibytes, four times the per-entry image cap. Counting produced bytes is what stops it,
    //    and the only way to see that from outside the reader is to weigh what it allocated.
    //
    //    Diluted to roughly 50:1 rather than built from zeros. A zeros bomb compresses at about
    //    1000:1, which the RATIO guard refuses after one mebibyte — so the byte counter this
    //    section is about never saw the stream, and the section held with `account`'s caps removed.
    let bomb = support::deflate_lowish_ratio(64 * 1024 * 1024);
    let archive = PptxBuilder::new()
        .slide(SlideSpec {
            title: Some("Text survives".into()),
            images: vec![("bomb.png".into(), Vec::new())],
            ..Default::default()
        })
        .replacing(support::Entry::raw_deflated(
            "ppt/media/bomb.png",
            bomb,
            1024,
        ))
        .build();
    reset();
    let mut src = MemorySource::new(archive);
    let mut sink = RecordingSink::new();
    let doc = selahcue_import::read_pptx(
        &mut src,
        ImportSource::Pptx {
            name: "Bomb".into(),
        },
        &mut sink,
        &|| false,
    )
    .unwrap();
    let bomb_peak = peak_since_reset();
    assert_eq!(doc.slides.len(), 1, "the slide's text survives");
    assert!(sink.is_empty());
    assert!(
        bomb_peak < HOSTILE_BUDGET,
        "a 200 MiB bomb declaring 1 KiB cost {bomb_peak} bytes"
    );
}
