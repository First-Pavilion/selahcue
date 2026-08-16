//! The read seam: bounded random-access reads over the chosen file, injected by the shell.
//!
//! **Why a trait rather than a `&[u8]`.** The importer admits `.pptx` files up to 512 MiB.
//! Holding one in memory would put the whole admission cap into the working set before any
//! parsing began — on its own, more than the entire import budget. Reading through a source
//! instead means the peak from the archive is a 64 KiB read buffer, not the file. That single
//! choice is what makes the memory arithmetic work, and it is not an optimisation.
//!
//! It also keeps this crate honest: it performs **no I/O of any kind**. The shell owns the
//! `File`; a grep over `src/` finding no `std::fs` and no `std::net` is a structural CI
//! assertion, which is what makes file disclosure through a parser bug unreachable rather than
//! merely defended against.

use crate::error::SourceError;

/// Bounded, random-access reads over a file the shell has opened.
pub trait ByteSource {
    /// The total length in bytes.
    fn len(&self) -> u64;

    /// Whether the source is empty. (Present because `len` without `is_empty` is a lint, and
    /// because an empty archive is a real case the caller checks.)
    fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Fill `buf` completely, starting at `offset`.
    ///
    /// A short read is an **error**, never a silent truncation. A parser that treats "fewer bytes
    /// than I asked for" as "end of data" is how offset arithmetic quietly goes wrong on a
    /// crafted file, so the contract forbids it.
    fn read_exact_at(&mut self, offset: u64, buf: &mut [u8]) -> Result<(), SourceError>;
}

/// An in-memory source over a `Vec<u8>`. Its purpose is tests: with it, the entire `.pptx` path
/// — images included — is exercised inside `cargo test --workspace` without touching a
/// filesystem.
#[derive(Debug, Clone)]
pub struct MemorySource {
    bytes: Vec<u8>,
}

impl MemorySource {
    pub fn new(bytes: Vec<u8>) -> Self {
        MemorySource { bytes }
    }
}

impl ByteSource for MemorySource {
    fn len(&self) -> u64 {
        self.bytes.len() as u64
    }

    fn read_exact_at(&mut self, offset: u64, buf: &mut [u8]) -> Result<(), SourceError> {
        let start = usize::try_from(offset).map_err(|_| SourceError::OutOfRange)?;
        let end = start
            .checked_add(buf.len())
            .ok_or(SourceError::OutOfRange)?;
        let src = self.bytes.get(start..end).ok_or(SourceError::OutOfRange)?;
        buf.copy_from_slice(src);
        Ok(())
    }
}
