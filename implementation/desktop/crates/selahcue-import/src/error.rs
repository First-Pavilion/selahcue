//! Typed errors, hand-rolled in the house style — a plain enum plus manual `Display` and
//! `std::error::Error`, exactly like `selahcue_core::scripture::ParseError`. No `thiserror`, no
//! `anyhow`; neither is used anywhere in this tree.
//!
//! **The boundary that matters most.** [`ImportError`] is reserved for *"nothing usable came
//! out"* — an inadmissible archive, a zero-slide result, a cancellation, a timeout. Anything
//! that produced at least one slide returns `Ok` with a report, because the product model is to
//! import what is representable and report the rest. Getting this boundary wrong is the most
//! likely way the partial-import rule gets violated in code, so it is stated as a rule:
//!
//! > **If one slide survived, it is not an error.**

use std::fmt;

/// Why a whole import produced nothing usable.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ImportError {
    /// The input contained no slide at all — an empty or entirely blank text source, or an
    /// archive with no readable slide part. The one text case that is genuinely an error.
    NothingToImport,
    /// The file is larger than the importer admits.
    FileTooLarge { limit: u64 },
    /// The bytes are not the container they claim to be: no end-of-central-directory record, a
    /// truncated directory, or structural nonsense.
    NotAnArchive,
    /// A ZIP64 archive. No real deck needs structures above 4 GiB, and refusing them keeps the
    /// offset-parsing surface to a single path.
    Zip64Unsupported,
    /// The archive holds encrypted entries, which cannot be inspected. Refused honestly rather
    /// than half-read.
    EncryptedArchive,
    /// More entries than [`MAX_ZIP_ENTRIES`](crate::limits::MAX_ZIP_ENTRIES).
    TooManyEntries { limit: usize },
    /// The archive's parts inflated past the whole-archive budget. The one cap breach that
    /// aborts the import rather than dropping an item, because past it nothing further can be
    /// trusted to be proportionate.
    ArchiveTooLarge { limit: usize },
    /// The operator cancelled, or the wall clock ran out. Both leave the library, the media store
    /// and live output byte-identical.
    Cancelled,
    /// The `ByteSource` failed underneath the parser.
    Source(SourceError),
}

impl fmt::Display for ImportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ImportError::NothingToImport => {
                write!(f, "there was nothing to import — no slides were found")
            }
            ImportError::FileTooLarge { limit } => write!(
                f,
                "the file is too large to import (the limit is {} MB)",
                limit / (1024 * 1024)
            ),
            ImportError::NotAnArchive => {
                write!(f, "this file isn't a readable PowerPoint presentation")
            }
            ImportError::Zip64Unsupported => write!(
                f,
                "this presentation uses a ZIP64 archive, which SelahCue doesn't import"
            ),
            ImportError::EncryptedArchive => write!(
                f,
                "this presentation is password-protected — remove the password and try again"
            ),
            ImportError::TooManyEntries { limit } => write!(
                f,
                "this presentation has more than {limit} internal parts, which is beyond what SelahCue imports"
            ),
            ImportError::ArchiveTooLarge { limit } => write!(
                f,
                "this presentation expands to more than {} MB, which is beyond what SelahCue imports",
                limit / (1024 * 1024)
            ),
            ImportError::Cancelled => write!(f, "the import was cancelled"),
            ImportError::Source(e) => write!(f, "the file couldn't be read: {e}"),
        }
    }
}

impl std::error::Error for ImportError {}

impl From<SourceError> for ImportError {
    fn from(e: SourceError) -> Self {
        ImportError::Source(e)
    }
}

/// Why a bounded read over the injected byte source failed. A short read is an error here, never
/// a silent truncation — a parser that treats "fewer bytes than asked for" as "end of data" is
/// how offset arithmetic quietly goes wrong.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceError {
    /// The requested range runs past the end of the source.
    OutOfRange,
    /// The underlying reader failed (an I/O error in the shell).
    ReadFailed,
}

impl fmt::Display for SourceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SourceError::OutOfRange => write!(f, "a read ran past the end of the file"),
            SourceError::ReadFailed => write!(f, "the file could not be read"),
        }
    }
}

impl std::error::Error for SourceError {}

/// Why staging one image failed. Every variant becomes a report entry and lets the import
/// continue — a disk-full mid-import degrades to a text-only deck plus an honest report, never a
/// failed import.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StoreError {
    /// The media library is at `MAX_MEDIA_ASSETS`. The *image* is refused; the *import* proceeds.
    LibraryFull,
    /// The staging write failed (disk full, permissions).
    WriteFailed,
    /// Staging this image would exceed the import's own media budget.
    BudgetExceeded,
}

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            StoreError::LibraryFull => write!(f, "the media library is full"),
            StoreError::WriteFailed => write!(f, "the image couldn't be saved"),
            StoreError::BudgetExceeded => write!(f, "this import's media budget is used up"),
        }
    }
}

impl std::error::Error for StoreError {}

/// Why one archive entry could not be produced. Most of these drop the entry and are reported;
/// only [`ArchiveTooLarge`](ZipError::ArchiveTooLarge) and
/// [`Cancelled`](ZipError::Cancelled) escalate to aborting the import.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ZipError {
    /// The entry's ACTUAL inflated size passed the per-entry cap. Note "actual": the declared
    /// size is a hint used only for a cheap early abort, never a guarantee.
    EntryTooLarge,
    /// The running total of INFLATED bytes across the archive passed the bomb cap. Escalates:
    /// past it nothing further in the file can be trusted to be proportionate.
    ArchiveTooLarge,
    /// The running total of EXTRACTED bytes (inflated or merely copied) passed the work cap.
    /// Drops the entry and is reported — a stored member cannot expand, so reaching this means an
    /// enormous archive rather than a hostile one.
    ExtractionBudgetExhausted,
    /// The entry inflated at a ratio past the guard, after enough output to judge it.
    RatioExceeded,
    /// The entry's compression method is neither stored nor deflate.
    UnsupportedMethod,
    /// The entry is encrypted.
    Encrypted,
    /// The entry's local header disagrees with the central directory, the stream is truncated, or
    /// the deflate data is corrupt.
    Malformed,
    /// The caller's cancel predicate fired inside the inflate loop.
    Cancelled,
    /// A read against the byte source failed.
    Source(SourceError),
}

impl From<SourceError> for ZipError {
    fn from(e: SourceError) -> Self {
        ZipError::Source(e)
    }
}
