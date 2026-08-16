//! Every bound the importer enforces, in one place, with the invariant each one protects.
//!
//! Two properties matter as much as the numbers themselves.
//!
//! **Each cap is enforced at the earliest point that knows the value, and on what is real.** The
//! inflate caps count bytes actually produced, never the sizes declared in ZIP headers, which
//! can lie in both directions. The image dimension check runs before allocation. *A cap enforced
//! after the allocation it was meant to prevent is decoration.*
//!
//! **They are re-checked on the way in.** `build::build_deck` asserts `SlideDeck::within_bounds`
//! before returning, so a limits bug in a parser cannot produce an out-of-bounds deck that later
//! reaches persistence. The repository has already rated an unbounded ingress a defect even for
//! local SQLite reads.

use selahcue_present::{MAX_DECK_SLIDES, MAX_ELEMENTS, MAX_NOTES_LEN, MAX_TEXT_ELEMENT_LEN};

// --- admission (enforced by the shell, before the pure crate sees a byte) --------------

/// Largest `.pptx` admitted at all. Above this the import is refused with an honest error rather
/// than attempted — and the reader streams through a [`ByteSource`](crate::ByteSource) precisely
/// so this number never lands in the working set.
pub const MAX_PPTX_FILE_BYTES: u64 = 512 * 1024 * 1024;

/// Largest `.txt` admitted. Enforced **during** the read, not after it: a metadata check followed
/// by an unbounded read is not a bound.
pub const MAX_TXT_FILE_BYTES: u64 = 16 * 1024 * 1024;

/// Largest pasted text accepted. A WebView can hand the command an arbitrarily large string, so
/// this is enforced on arrival. Over-long input is truncated and reported, never silently cut.
pub const MAX_CLIPBOARD_BYTES: usize = 2 * 1024 * 1024;

// --- archive ---------------------------------------------------------------------------

/// Entries admitted in one archive. Real decks run to roughly four parts per slide plus media, so
/// this is generous; a 100k-entry central directory is an exhaustion attempt.
pub const MAX_ZIP_ENTRIES: usize = 4_096;

/// Longest archive entry name read. Names are only ever lookup keys into the archive's own entry
/// set — never path components — but an unbounded name is still an unbounded allocation.
pub const MAX_ZIP_NAME_LEN: usize = 512;

/// Cap on the bytes ONE entry may actually inflate to. Counted inside the streaming inflate loop
/// on bytes produced, because DEFLATE peaks near 1032:1 and a declared size is not evidence.
pub const MAX_ENTRY_INFLATED_BYTES: usize = 64 * 1024 * 1024;

/// Cap on the bytes ALL entries may **inflate** to across one import — bytes the archive
/// *conjured* rather than carried. **This is the load-bearing bomb bound:** a per-entry cap
/// alone, times 4096 entries, is not a bound at all. Breaching it aborts the import, because past
/// it nothing further in the file can be trusted to be proportionate.
///
/// It counts DEFLATE output only. It used to count stored members too, and that was wrong in a
/// way that cost users real decks: a stored member is an already-compressed photograph copied out
/// byte for byte, so it expands by nothing and cannot be a bomb, and its total contribution is
/// bounded by the file the shell already admitted. Charging it to an *inflation* budget refused
/// a legitimate 278 MiB photo deck outright — zero slides, in half a second — while a 242 MiB one
/// passed with 14 MiB to spare.
pub const MAX_TOTAL_INFLATED_BYTES: usize = 256 * 1024 * 1024;

/// Cap on the bytes ALL entries may **produce** across one import, inflated or copied.
///
/// Stored members still need a total, because ZIP entries may overlap: four thousand entries can
/// all point at the same sixteen mebibytes and ask to be read four thousand times. This bounds
/// that work. It is set to the admission cap because a well-formed archive's stored content is by
/// definition no larger than the file holding it, so no real deck can reach it — which is what
/// makes degrading rather than aborting the right response when it *is* reached.
pub const MAX_TOTAL_EXTRACTED_BYTES: usize = MAX_PPTX_FILE_BYTES as usize;

/// Inflate-ratio guard, evaluated only after at least [`RATIO_GUARD_FLOOR`] bytes have been
/// produced so a tiny, legitimately compressible part cannot trip it. Secondary to the absolute
/// caps: this is early-abort economy, they are the guarantee.
pub const MAX_COMPRESSION_RATIO: usize = 100;

/// Output produced before the ratio guard starts applying.
pub const RATIO_GUARD_FLOOR: usize = 1024 * 1024;

/// Cap on one inflated XML part — deliberately tighter than the per-entry archive ceiling. No
/// legitimate slide part approaches 16 MiB, so the tighter inner bound costs nothing and shrinks
/// the XML layer's exposure.
pub const MAX_XML_PART_BYTES: usize = 16 * 1024 * 1024;

// --- XML -------------------------------------------------------------------------------

/// Element nesting depth admitted. A pull parser will happily stream a million-deep document;
/// recursive descent over one is a stack overflow, which here is a console crash mid-service.
/// The reader is iterative with an explicit counter, and this is that counter's ceiling.
pub const MAX_XML_DEPTH: usize = 256;

/// Events read from one part before it is abandoned. Bounds a part that is legal but
/// pathological — element floods that are individually tiny and collectively unbounded.
pub const MAX_XML_EVENTS_PER_PART: usize = 1_000_000;

// --- content ---------------------------------------------------------------------------

/// Slides imported. Equal to the deck's own bound, so the importer can never build a deck the
/// presentation layer would reject.
pub const MAX_IMPORT_SLIDES: usize = MAX_DECK_SLIDES;

/// Body lines kept per slide. Two text elements carry a slide (title + body), so this is a
/// content bound rather than an element one.
pub const MAX_SLIDE_LINES: usize = 64;

/// Characters kept per line. Equal to the element bound it will eventually occupy.
pub const MAX_LINE_LEN: usize = MAX_TEXT_ELEMENT_LEN;

/// Characters kept in a slide title.
pub const MAX_TITLE_LEN: usize = 200;

/// Characters kept in speaker notes. `AuthoredSlide::within_bounds` counts notes in **chars**,
/// not bytes, so truncation here is by chars too — truncating by bytes would fail the predicate
/// on non-ASCII text.
pub const MAX_IMPORT_NOTES_LEN: usize = MAX_NOTES_LEN;

/// Elements built onto one slide. The deck's own bound; `build` stops adding at it.
pub const MAX_SLIDE_ELEMENTS: usize = MAX_ELEMENTS;

/// Pictures taken from one slide.
pub const MAX_PICTURES_PER_SLIDE: usize = 16;

/// Images taken from one deck, across all slides.
pub const MAX_IMPORT_IMAGES: usize = 200;

// --- images ----------------------------------------------------------------------------

/// Encoded bytes admitted for one embedded image — tighter than the render path's 64 MiB,
/// because one import may process up to [`MAX_IMPORT_IMAGES`] of them while the render path
/// decodes one at a time.
pub const MAX_IMAGE_ENCODED_BYTES: usize = 16 * 1024 * 1024;

/// Decoded pixels admitted for one embedded image — again tighter than the render path's 40 MP,
/// for the same reason. Halved again by the decoder for a transposing EXIF orientation.
pub const MAX_IMAGE_PIXELS: u64 = 16_000_000;

// --- report ----------------------------------------------------------------------------

/// Skipped items ITEMISED in a report. Beyond this they are counted, not listed — the report
/// must not itself become an unbounded buffer, and a hundred lines is already past what anyone
/// reads.
pub const MAX_REPORT_ITEMS: usize = 100;

/// Characters kept in one report detail string.
pub const MAX_REPORT_DETAIL_LEN: usize = 200;

/// Characters kept in an imported deck name, single-line.
pub const MAX_DECK_NAME_LEN: usize = 200;

/// The decode limits the import path hands the engine — its **own**, deliberately tighter than
/// `DecodeLimits::default()`, which is sized for the render path decoding one image at a time.
pub fn image_decode_limits() -> selahcue_engine::DecodeLimits {
    selahcue_engine::DecodeLimits {
        // Match the raster frame bound; an imported image never needs to exceed the output.
        max_width: 8192,
        max_height: 8192,
        max_pixels: MAX_IMAGE_PIXELS,
        max_encoded_bytes: MAX_IMAGE_ENCODED_BYTES,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The bounds that are shared with the presentation layer must stay *equal* to it, not merely
    /// close. If `selahcue-present` tightens one, the importer must tighten with it, or it will
    /// happily build a deck that `within_bounds` then rejects at the ingress.
    #[test]
    fn content_bounds_track_the_presentation_layer() {
        assert_eq!(MAX_IMPORT_SLIDES, MAX_DECK_SLIDES);
        assert_eq!(MAX_LINE_LEN, MAX_TEXT_ELEMENT_LEN);
        assert_eq!(MAX_IMPORT_NOTES_LEN, MAX_NOTES_LEN);
        assert_eq!(MAX_SLIDE_ELEMENTS, MAX_ELEMENTS);
    }

    /// A slide's worth of text plus its pictures must fit the element budget, or a full slide
    /// would silently lose its images to `LimitReached(Elements)`.
    #[test]
    fn a_full_slide_fits_the_element_budget() {
        // title + body + pictures
        const { assert!(2 + MAX_PICTURES_PER_SLIDE <= MAX_SLIDE_ELEMENTS) };
    }

    /// The per-entry cap must not exceed the whole-archive cap, or the "total" bound would be
    /// unreachable and the composition in the design's memory arithmetic would be wrong.
    #[test]
    fn the_archive_caps_compose() {
        const { assert!(MAX_ENTRY_INFLATED_BYTES <= MAX_TOTAL_INFLATED_BYTES) };
        const { assert!(MAX_XML_PART_BYTES <= MAX_ENTRY_INFLATED_BYTES) };
        const { assert!(MAX_IMAGE_ENCODED_BYTES <= MAX_ENTRY_INFLATED_BYTES) };
        // The extraction budget is the outer one: every inflated byte is also an extracted byte,
        // so an inflate budget above it would be unreachable and the abort could never fire.
        const { assert!(MAX_TOTAL_INFLATED_BYTES <= MAX_TOTAL_EXTRACTED_BYTES) };
        // And a deck the shell admitted must be able to have all of its stored content read, or
        // the degrade path would fire on files that are inside every stated limit.
        const { assert!(MAX_TOTAL_EXTRACTED_BYTES >= MAX_PPTX_FILE_BYTES as usize) };
    }

    #[test]
    fn the_import_decode_limits_are_tighter_than_the_render_paths() {
        let import = image_decode_limits();
        let render = selahcue_engine::DecodeLimits::default();
        assert!(import.max_pixels < render.max_pixels);
        assert!(import.max_encoded_bytes < render.max_encoded_bytes);
    }
}
