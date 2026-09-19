//! SelahCue presentation import (ADR-0024): bytes in, a bounded [`SlideDeck`] and an
//! [`ImportReport`] out.
//!
//! # Why this is its own crate
//!
//! The deck library lives in the Tauri operator shell, which is **excluded from the cargo
//! workspace** — `cargo test --workspace` does not reach it, and CI only compile-checks it plus
//! runs a headless webview script. Parsing hostile binary input is precisely the code that must
//! be exhaustively tested, so the transform lives here instead, where the whole hostile-input
//! battery runs on every commit and a fuzz target is routine.
//!
//! It also makes two security properties **structural rather than aspirational**:
//!
//! - *No network.* `cargo tree -p selahcue-import -e normal` contains no network crate. That
//!   assertion is a one-line CI check only because this is its own crate — inside the operator,
//!   whose graph legitimately contains a TLS stack, the property would be unstateable.
//! - *No filesystem primitive is reachable from this crate's own code.* `src/` names no `fs`,
//!   `net`, `process` or `env` module, in any import form, asserted by a CI grep. File disclosure
//!   through a parser bug is therefore unreachable, not merely defended against.
//!
//!   Stated at that width deliberately. The stronger-sounding "the importer performs no filesystem
//!   I/O at all" is not true of the LINKED GRAPH and never was: `selahcue-engine` pulls
//!   `cosmic-text` for text layout, which pulls `fontdb`, which links `memmap2` to memory-map
//!   system font files and `rayon` to enumerate them. Neither is reachable from anything here —
//!   this crate calls no layout — but a claim about the graph has to be true of the graph.
//!
//! # The seam
//!
//! Three injected effects, following the pattern this codebase already uses to keep pure layers
//! pure: [`ByteSource`] for bounded reads, [`MediaSink`] for staging validated image bytes, and a
//! slot resolver supplied after the media commit.
//!
//! The shell **may**: open a dialog, provide a byte source, stage and commit media, call the deck
//! library, run the timeout, the import lock and the panic belt, and serialise the report. It
//! **may not**: know a file format, parse anything, compute or enforce a content limit, branch on
//! file content, or construct an element. *If a reviewer sees a `match` on a byte in the shell's
//! `main.rs`, the seam has been violated.*
//!
//! # The partial-import rule
//!
//! Import what is representable; report what was dropped. [`ImportError`] is reserved for
//! "nothing usable came out". **If one slide survived, it is not an error.**

#![forbid(unsafe_code)]
#![deny(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::todo,
    clippy::unimplemented
)]

pub mod build;
pub mod decode;
pub mod error;
pub mod hygiene;
pub mod limits;
pub mod model;
mod ooxml;
mod pkgpath;
pub mod pptx;
pub mod report;
pub mod safe_extract;
pub mod sink;
pub mod source;
pub mod text;
mod zip;

pub use build::{build_deck, deck_name_for};
pub use error::{ImportError, SourceError, StoreError};
pub use model::{
    ImportSource, ImportedDocument, ImportedPicture, ImportedSlide, MediaSlot, PermilleRect,
};
pub use report::{
    ImportReport, LimitKind, Notice, Severity, SkipKind, SkippedItem, TruncatedField, Truncation,
};
pub use safe_extract::{
    safe_extract_zip, ExtractedFile, RefusalReason, RefusedEntry, SafeExtractResult,
};
pub use sink::{ImageProbe, MediaSink, RecordingSink, RefusingSink};
pub use source::{ByteSource, MemorySource};
pub use text::{TextLayout, TextOptions};

use selahcue_present::{SlideDeck, Theme};

/// Import already-decoded text (the clipboard path, and the tail of the `.txt` path).
pub fn import_text(
    text: &str,
    source: ImportSource,
    theme: &Theme,
    name: &str,
    opts: &TextOptions,
) -> Result<(SlideDeck, ImportReport), ImportError> {
    let doc = text::parse(text, source, opts, report::ReportBuilder::new())?;
    Ok(build_deck(doc, theme, name, &|_| None))
}

/// Import the bytes of a `.txt` file: decode the encoding (counting and reporting any
/// substitution), then take the same path as pasted text.
pub fn import_txt_bytes(
    bytes: &[u8],
    source: ImportSource,
    theme: &Theme,
    name: &str,
    opts: &TextOptions,
) -> Result<(SlideDeck, ImportReport), ImportError> {
    let decoded = decode::to_text(bytes);
    let mut report = report::ReportBuilder::new();
    report.record_replacements(decoded.replacements);
    let doc = text::parse(&decoded.text, source, opts, report)?;
    Ok(build_deck(doc, theme, name, &|_| None))
}

/// Clamp pasted text to the clipboard budget, reporting what was cut.
///
/// A webview can hand a command an arbitrarily large string, so this runs on arrival. Truncation
/// is on a **character boundary**, so the result is always valid text.
pub fn clamp_clipboard(text: &str, report: &mut report::ReportBuilder) -> String {
    if text.len() <= limits::MAX_CLIPBOARD_BYTES {
        return text.to_string();
    }
    let mut end = limits::MAX_CLIPBOARD_BYTES;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    let kept = text.get(..end).unwrap_or_default().to_string();
    report.notice(report::Notice::ClipboardTruncated {
        dropped_bytes: text.len() - kept.len(),
    });
    kept
}

/// Read a `.pptx`: parse it and stage its images, committing nothing.
///
/// This is stage one of two. Pictures come back carrying a [`MediaSlot`], not a media reference,
/// because the final path is not known until the shell's atomic commit — that ordering is what
/// makes "nothing is visible until the whole parse passed bounds" achievable.
///
/// `cancel` is polled between slides, between pictures, and **inside the streaming inflate loop
/// at chunk granularity**, so there is no uninterruptible multi-gigabyte loop for a cancel or a
/// timeout to fail to interrupt.
pub fn read_pptx(
    src: &mut dyn ByteSource,
    source: ImportSource,
    sink: &mut dyn MediaSink,
    cancel: &dyn Fn() -> bool,
) -> Result<ImportedDocument, ImportError> {
    pptx::read(src, source, sink, cancel)
}
