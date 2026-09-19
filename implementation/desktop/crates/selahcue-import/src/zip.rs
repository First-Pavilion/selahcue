//! A minimal, hardened ZIP central-directory reader over an injected [`ByteSource`], inflating
//! through `flate2`.
//!
//! # Why this is hand-rolled rather than a dependency
//!
//! Not for fun, and not to save a crate for its own sake:
//!
//! - **The security constraint set forbids the very API a general-purpose ZIP crate exists to
//!   provide.** No extract-to-directory helper may be used, because several honour symlinks, and
//!   entry types, mode bits and link targets must be ignored entirely. A crate whose main
//!   convenience is "extract this archive to that directory" is a crate whose main feature we are
//!   contractually forbidden from calling.
//! - **Every control we need lives outside such a crate anyway** — entry-count cap, name cap,
//!   actual-byte caps, the ratio guard, the compression-method allowlist, refusal of encrypted
//!   entries and ZIP64, duplicate-name handling, and cancellation *inside* the inflate loop. The
//!   dependency would buy only format decoding, while adding AES and ZipCrypto decryption, bzip2
//!   and zstd back-ends, deflate64 and permission emulation — all of it ours to carry and
//!   re-audit under the SBOM gate, none of it ever called.
//! - **`flate2` is already a direct first-party dependency**, so the whole ZIP capability adds no
//!   new SBOM entry.
//!
//! The honest cost is that we own our format bugs. That is mitigated three ways: the negative
//! battery in `tests/test_zip.rs`, a fuzz target, and the [`Archive`] trait below — so swapping in
//! a general ZIP crate later is a single-module change with the tests unchanged. If field failures
//! accumulate, take the dependency; do not patch a hand-rolled reader indefinitely.
//!
//! # The load-bearing control
//!
//! **Caps are enforced on bytes that actually come out of the inflater.** Declared sizes in ZIP
//! headers lie in both directions, so they may never inform an allocation or an admission
//! decision. The declared size is used only as a cheap early abort *before* the first chunk — an
//! economy, never a guarantee. The primary bomb test is therefore the *lying-header* case.
//!
//! # One thing this reader deliberately does NOT do
//!
//! It does not verify entry CRCs. That is a decision, not an omission: no archive byte is ever
//! written to disk under an archive-derived name, and every consumer downstream — the XML parser
//! and the image decoder — validates its own input structurally and refuses anything malformed.
//! A CRC check would add a redundant gate and a second failure mode, without closing a path that
//! the structural validation leaves open.
//!
//! This module parses untrusted binary offsets, so it denies `indexing_slicing` and
//! `arithmetic_side_effects`: `off + len` overflow is the classic bug here.

#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]

use std::collections::HashSet;

use crate::error::{ImportError, ZipError};
use crate::limits::{
    MAX_COMPRESSION_RATIO, MAX_ENTRY_INFLATED_BYTES, MAX_TOTAL_EXTRACTED_BYTES,
    MAX_TOTAL_INFLATED_BYTES, MAX_ZIP_ENTRIES, MAX_ZIP_NAME_LEN, RATIO_GUARD_FLOOR,
};
use crate::pkgpath;
use crate::source::ByteSource;

/// End-of-central-directory signature.
const EOCD_SIG: u32 = 0x0605_4b50;
/// ZIP64 end-of-central-directory **locator** signature. Its presence refuses the archive.
const ZIP64_LOCATOR_SIG: u32 = 0x0706_4b50;
/// Central-directory file-header signature.
const CDIR_SIG: u32 = 0x0201_4b50;
/// Local file-header signature.
const LOCAL_SIG: u32 = 0x0403_4b50;

/// The EOCD record is 22 bytes plus a comment of at most 65 535 — so it starts no further back
/// than this from the end of the file.
const EOCD_SEARCH_SPAN: u64 = 22 + 65_535;

/// The fixed part of one central-directory file header, before its variable-length name, extra
/// field and comment.
const CDIR_HEADER_LEN: usize = 46;

/// Bytes moved per iteration of the streaming loops. Small enough that cancellation is prompt and
/// the working set is a buffer rather than a file.
const CHUNK: usize = 64 * 1024;

/// Stored (no compression).
const METHOD_STORE: u16 = 0;
/// Deflate.
const METHOD_DEFLATE: u16 = 8;

/// What the central directory says about one entry. This reader still never acts on entry type,
/// mode bits or link targets for the in-memory OOXML path — [`find`](Archive::find)/
/// [`read_entry`](Archive::read_entry) treat a symlink entry as just an entry whose contents
/// happen to be a string, which is safe because that path never writes a byte to disk. But
/// `safe_extract` (which does write to disk) needs to tell a symlink entry apart from a regular
/// one, so the two fields below are recorded — read, never interpreted, by anything in this file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct EntryMeta {
    pub name: String,
    /// Case-folded name, for the lookup that APFS and NTFS would fold anyway.
    pub folded: String,
    pub method: u16,
    pub encrypted: bool,
    /// The size the header CLAIMS. Used only for a cheap early abort; never for an allocation.
    pub declared_size: u64,
    pub compressed_size: u64,
    pub local_offset: u64,
    /// A later entry sharing an earlier entry's folded name. First occurrence wins; this one is
    /// dropped and reported, so "parse one copy, extract the other" confusion is impossible.
    pub duplicate: bool,
    /// The name is over the length cap or carries a NUL, so the entry is unusable. Tracked
    /// separately from [`duplicate`](Self::duplicate) because the two are different facts about
    /// the archive and reporting one as the other tells the operator something untrue — "the
    /// first copy was used" is simply wrong when there was no first copy. For an over-long name
    /// only the capped prefix is ever read, so [`name`](Self::name) may be a truncated quote
    /// suitable for a report and nothing else.
    pub bad_name: bool,
    /// The host-OS byte of the central-directory "version made by" field. Only a value of
    /// [`UNIX_HOST_OS`] makes [`external_attrs`](Self::external_attrs)'s upper 16 bits a Unix file
    /// mode at all — on every other host OS that field means something else (or nothing), so
    /// [`is_symlink`](Self::is_symlink) must and does check this first.
    pub host_os: u8,
    /// Raw external file attributes, exactly as the central directory declares them. Interpreted
    /// nowhere except [`is_symlink`](Self::is_symlink).
    pub external_attrs: u32,
}

/// Host-OS byte (central-directory "version made by", high byte) for Unix-originated archives —
/// the only origin on which `external_attrs`'s upper 16 bits are a Unix file mode.
const UNIX_HOST_OS: u8 = 3;
/// `st_mode`'s format mask (the top 4 bits of the 16-bit mode).
const UNIX_MODE_FMT_MASK: u32 = 0o170_000;
/// `S_IFLNK` — the format bits that mark a Unix symlink.
const UNIX_MODE_SYMLINK: u32 = 0o120_000;

impl EntryMeta {
    /// Whether this entry may be looked up and read at all. A shadowed duplicate and an entry
    /// whose name we refused are both unusable, and neither may ever resolve a part name.
    pub fn usable(&self) -> bool {
        !self.duplicate && !self.bad_name
    }

    /// Whether the central directory marks this entry as a Unix symlink.
    ///
    /// Judged **only** from a Unix-origin archive's own mode bits, never guessed at or inferred
    /// from a name or a missing field: on a non-Unix host OS `external_attrs` is either zero or
    /// means something entirely unrelated (an MS-DOS attribute byte, for instance), and reading a
    /// mode out of it there would be reading a mode nobody wrote.
    pub fn is_symlink(&self) -> bool {
        self.host_os == UNIX_HOST_OS
            && (self.external_attrs >> 16) & UNIX_MODE_FMT_MASK == UNIX_MODE_SYMLINK
    }
}

/// The narrow surface the rest of the importer uses. Keeping it this small is what makes swapping
/// the implementation a single-module change.
pub(crate) trait Archive {
    fn entries(&self) -> &[EntryMeta];

    /// The index of the usable entry with this package name, if the archive holds one.
    ///
    /// On the trait rather than in the caller so the caller never needs to hold a borrow of the
    /// entry table across a read — the borrow that a full-table clone used to buy its way out of,
    /// at the cost of a second copy of every name in the archive.
    fn find(&self, name: &str) -> Option<usize> {
        let folded = pkgpath::fold(name);
        self.entries()
            .iter()
            .position(|e| e.usable() && e.folded == folded)
    }

    /// Stream entry `idx` through the inflater, enforcing the ACTUAL-byte caps.
    fn read_entry(
        &mut self,
        idx: usize,
        max_out: usize,
        cancel: &dyn Fn() -> bool,
    ) -> Result<Vec<u8>, ZipError>;
}

/// How an entry's bytes came into being — which decides which whole-archive budget they are
/// charged to, and therefore whether breaching it aborts the import or degrades it.
///
/// The distinction is the whole point. A DEFLATE member can produce arbitrarily more than it
/// occupies, so its aggregate is the bomb surface and its breach is a refusal. A STORED member is
/// copied byte for byte out of a file the shell already admitted, so it can expand by nothing;
/// its aggregate bounds *work* (entries may overlap and be read many times), not expansion, and
/// its breach is a degrade.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Production {
    Inflated,
    Copied,
}

pub(crate) struct ZipArchive<'a> {
    src: &'a mut dyn ByteSource,
    entries: Vec<EntryMeta>,
    /// Bytes the inflater PRODUCED across the whole archive so far. This is the bomb bound: a
    /// per-entry cap alone, times four thousand entries, is not a bound.
    total_inflated: usize,
    /// Bytes produced across the whole archive by any method. Bounds the total work an archive
    /// can ask for, including overlapping stored entries read over and over.
    total_extracted: usize,
    /// The buffers and the inflater every entry read reuses. See [`Scratch`].
    scratch: Scratch,
}

/// The working set one archive read needs, owned by the archive and reused for every member.
///
/// All three of these were allocated **per entry**, inside the read: two 64 KiB chunk buffers and
/// a `flate2::Decompress`. An archive may hold [`MAX_ZIP_ENTRIES`] members and an ordinary deck
/// holds several hundred, so that is roughly 172 KiB of allocate-fill-free per part, on the path
/// that reads attacker-supplied bytes — precisely the repeated unbounded work this crate refuses
/// everywhere else, and invisible to a high-water-mark measurement because each one is freed
/// before the next is taken.
#[derive(Default)]
struct Scratch {
    /// Raw bytes from the source, one [`CHUNK`] at a time.
    input: Vec<u8>,
    /// What the inflater produced, one [`CHUNK`] at a time.
    output: Vec<u8>,
    /// The archive's ONE inflater: built on first use, `reset` for every member after that, and
    /// never built at all for an archive with no deflated member to read.
    ///
    /// **Lazy, not eager, and that is load-bearing.** Building it in `open` was tidier and cost
    /// the crate its one cheap path: because `miniz_oxide` assembles `InflateState` (a 32 KiB LZ
    /// dictionary plus the Huffman tables) in stack temporaries before boxing it, constructing one
    /// spends most of [`MAX_IMPORT_STACK_BYTES`](crate::limits::MAX_IMPORT_STACK_BYTES) — so doing
    /// it eagerly charged a stored-only archive ninety-odd kilobytes of stack to read nothing.
    /// Deferring it keeps a package that never reaches the inflater inside
    /// [`MAX_WALK_STACK_BYTES`](crate::limits::MAX_WALK_STACK_BYTES), which is what makes that
    /// budget tight enough to catch a recursion regression at all.
    inflate: Option<flate2::Decompress>,
}

impl Scratch {
    /// `buf` as exactly one [`CHUNK`], grown once and reused thereafter.
    fn chunk(buf: &mut Vec<u8>) -> &mut [u8] {
        if buf.len() != CHUNK {
            buf.resize(CHUNK, 0);
        }
        buf
    }
}

impl<'a> ZipArchive<'a> {
    /// Locate the central directory and read every entry's metadata.
    pub(crate) fn open(src: &'a mut dyn ByteSource) -> Result<Self, ImportError> {
        let len = src.len();
        if len < 22 {
            return Err(ImportError::NotAnArchive);
        }
        let span = EOCD_SEARCH_SPAN.min(len);
        let start = len.saturating_sub(span);
        let mut tail = vec![0u8; usize::try_from(span).map_err(|_| ImportError::NotAnArchive)?];
        src.read_exact_at(start, &mut tail)?;

        // A ZIP64 locator anywhere in the tail refuses the archive: no real deck needs structures
        // above 4 GiB, and refusing keeps the offset-parsing surface to one path.
        if find_sig(&tail, ZIP64_LOCATOR_SIG).is_some() {
            return Err(ImportError::Zip64Unsupported);
        }
        let eocd = rfind_sig(&tail, EOCD_SIG).ok_or(ImportError::NotAnArchive)?;
        let total_entries = le_u16(
            &tail,
            eocd.checked_add(10).ok_or(ImportError::NotAnArchive)?,
        )
        .ok_or(ImportError::NotAnArchive)?;
        let cd_size = le_u32(
            &tail,
            eocd.checked_add(12).ok_or(ImportError::NotAnArchive)?,
        )
        .ok_or(ImportError::NotAnArchive)?;
        let cd_offset = le_u32(
            &tail,
            eocd.checked_add(16).ok_or(ImportError::NotAnArchive)?,
        )
        .ok_or(ImportError::NotAnArchive)?;
        // The ZIP64 sentinels: a real ZIP64 archive without a locator in range still says so here.
        if total_entries == u16::MAX || cd_size == u32::MAX || cd_offset == u32::MAX {
            return Err(ImportError::Zip64Unsupported);
        }
        if usize::from(total_entries) > MAX_ZIP_ENTRIES {
            return Err(ImportError::TooManyEntries {
                limit: MAX_ZIP_ENTRIES,
            });
        }
        let cd_size = u64::from(cd_size);
        let cd_offset = u64::from(cd_offset);
        if cd_offset.checked_add(cd_size).is_none_or(|end| end > len) {
            return Err(ImportError::NotAnArchive);
        }
        let entries =
            read_central_directory(&mut *src, cd_offset, cd_size, usize::from(total_entries))?;
        Ok(ZipArchive {
            src,
            entries,
            total_inflated: 0,
            total_extracted: 0,
            scratch: Scratch::default(),
        })
    }

    /// The byte offset of an entry's DATA, computed from its own local header. The local header's
    /// name and extra lengths can legitimately differ from the central directory's, so this must
    /// be read rather than assumed.
    fn data_offset(&mut self, meta: &EntryMeta) -> Result<u64, ZipError> {
        let mut header = [0u8; 30];
        self.src.read_exact_at(meta.local_offset, &mut header)?;
        if le_u32(&header, 0) != Some(LOCAL_SIG) {
            return Err(ZipError::Malformed);
        }
        let name_len = u64::from(le_u16(&header, 26).ok_or(ZipError::Malformed)?);
        let extra_len = u64::from(le_u16(&header, 28).ok_or(ZipError::Malformed)?);
        meta.local_offset
            .checked_add(30)
            .and_then(|o| o.checked_add(name_len))
            .and_then(|o| o.checked_add(extra_len))
            .filter(|o| *o <= self.src.len())
            .ok_or(ZipError::Malformed)
    }
}

impl Archive for ZipArchive<'_> {
    fn entries(&self) -> &[EntryMeta] {
        &self.entries
    }

    fn read_entry(
        &mut self,
        idx: usize,
        max_out: usize,
        cancel: &dyn Fn() -> bool,
    ) -> Result<Vec<u8>, ZipError> {
        let meta = self.entries.get(idx).ok_or(ZipError::Malformed)?.clone();
        // Belt to `find`'s braces: an entry we refused by name can never be read, even by index.
        if !meta.usable() {
            return Err(ZipError::Malformed);
        }
        if meta.encrypted {
            return Err(ZipError::Encrypted);
        }
        if !matches!(meta.method, METHOD_STORE | METHOD_DEFLATE) {
            return Err(ZipError::UnsupportedMethod);
        }
        let entry_cap = max_out.min(MAX_ENTRY_INFLATED_BYTES);
        // CHEAP EARLY ABORT, not a guarantee: if the header already admits to being over budget
        // we can decline without inflating a byte. The streaming counter below is what actually
        // holds, because this number is attacker-controlled and can equally well under-report.
        if meta.declared_size > entry_cap as u64 {
            return Err(ZipError::EntryTooLarge);
        }
        let data_at = self.data_offset(&meta)?;
        let available = self.src.len().saturating_sub(data_at);

        let mut out: Vec<u8> = Vec::new();
        // Lend the archive its own scratch for the read and take it back whatever happens, so a
        // member that is dropped mid-read does not cost the next one a fresh set of buffers.
        let mut scratch = std::mem::take(&mut self.scratch);
        let read = match meta.method {
            METHOD_STORE => self.read_stored(
                &mut scratch,
                data_at,
                available,
                &meta,
                entry_cap,
                cancel,
                &mut out,
            ),
            _ => self.read_deflate(
                &mut scratch,
                data_at,
                available,
                entry_cap,
                cancel,
                &mut out,
            ),
        };
        self.scratch = scratch;
        read?;
        Ok(out)
    }
}

impl ZipArchive<'_> {
    /// Copy a stored entry, still counting what actually comes out.
    ///
    /// The extent is **`compressed_size`**, not `declared_size`: for a stored member the on-disk
    /// extent is the compressed size by definition, and the two fields are independent numbers an
    /// archive may set to anything. Reading `declared_size` bytes instead means an over-declaring
    /// entry serves the archive bytes that follow it — the next local header and the next member's
    /// payload — as this part's content, and an under-declaring one silently truncates the part to
    /// whatever prefix it named.
    #[allow(clippy::too_many_arguments)]
    fn read_stored(
        &mut self,
        scratch: &mut Scratch,
        data_at: u64,
        available: u64,
        meta: &EntryMeta,
        entry_cap: usize,
        cancel: &dyn Fn() -> bool,
        out: &mut Vec<u8>,
    ) -> Result<(), ZipError> {
        let want = meta.compressed_size.min(available);
        let mut done: u64 = 0;
        let buf = Scratch::chunk(&mut scratch.input);
        while done < want {
            if cancel() {
                return Err(ZipError::Cancelled);
            }
            let take = usize::try_from(want.saturating_sub(done))
                .unwrap_or(CHUNK)
                .min(CHUNK);
            let slice = buf.get_mut(..take).ok_or(ZipError::Malformed)?;
            let at = data_at.checked_add(done).ok_or(ZipError::Malformed)?;
            self.src.read_exact_at(at, slice)?;
            self.account(
                out.len().saturating_add(take),
                take,
                entry_cap,
                Production::Copied,
            )?;
            out.extend_from_slice(slice);
            done = done.saturating_add(take as u64);
        }
        Ok(())
    }

    /// Stream a deflate entry, enforcing the caps on **produced** bytes, chunk by chunk.
    ///
    /// The buffers and the inflater come from the archive's [`Scratch`] rather than being built
    /// here — see that type for why one set per archive rather than one per member.
    #[allow(clippy::too_many_arguments)]
    fn read_deflate(
        &mut self,
        scratch: &mut Scratch,
        data_at: u64,
        available: u64,
        entry_cap: usize,
        cancel: &dyn Fn() -> bool,
        out: &mut Vec<u8>,
    ) -> Result<(), ZipError> {
        let Scratch {
            input,
            output,
            inflate,
        } = scratch;
        // Built on the first deflated member of the archive and reused for the rest. `reset`
        // clears the stream state and zeroes the counters, so each member starts clean; `false`
        // keeps it on raw deflate, no zlib header, which is what a ZIP member is.
        let inflate = inflate.get_or_insert_with(|| flate2::Decompress::new(false));
        inflate.reset(false);
        let input = Scratch::chunk(input);
        let output = Scratch::chunk(output);
        let mut read_at = data_at;
        let mut consumed_total: usize = 0;
        let mut remaining = available;

        loop {
            if cancel() {
                return Err(ZipError::Cancelled);
            }
            let take = usize::try_from(remaining).unwrap_or(CHUNK).min(CHUNK);
            if take == 0 {
                // Ran out of input before the stream ended: a truncated member.
                return Err(ZipError::Malformed);
            }
            let in_slice = input.get_mut(..take).ok_or(ZipError::Malformed)?;
            self.src.read_exact_at(read_at, in_slice)?;

            let mut offset = 0usize;
            loop {
                let before_in = inflate.total_in();
                let before_out = inflate.total_out();
                let src = in_slice.get(offset..).ok_or(ZipError::Malformed)?;
                let status = inflate
                    .decompress(src, output, flate2::FlushDecompress::None)
                    .map_err(|_| ZipError::Malformed)?;
                let produced = usize::try_from(inflate.total_out().saturating_sub(before_out))
                    .map_err(|_| ZipError::Malformed)?;
                let ate = usize::try_from(inflate.total_in().saturating_sub(before_in))
                    .map_err(|_| ZipError::Malformed)?;
                offset = offset.saturating_add(ate);
                consumed_total = consumed_total.saturating_add(ate);

                if produced > 0 {
                    let produced_total = out.len().saturating_add(produced);
                    self.account(produced_total, produced, entry_cap, Production::Inflated)?;
                    // The ratio guard, applied only once there is enough output to judge — a tiny,
                    // legitimately compressible part must not trip it.
                    // `checked_div` rather than `/`: the lint on this module exists precisely to
                    // stop a division that a crafted archive could drive to zero.
                    let ratio = produced_total
                        .checked_div(consumed_total)
                        .unwrap_or(usize::MAX);
                    if produced_total >= RATIO_GUARD_FLOOR && ratio > MAX_COMPRESSION_RATIO {
                        return Err(ZipError::RatioExceeded);
                    }
                    let chunk = output.get(..produced).ok_or(ZipError::Malformed)?;
                    out.extend_from_slice(chunk);
                }
                match status {
                    flate2::Status::StreamEnd => return Ok(()),
                    // No progress on either side: the inflater cannot use what it has been given.
                    _ if ate == 0 && produced == 0 => break,
                    _ => {}
                }
                if offset >= take {
                    break;
                }
                if cancel() {
                    return Err(ZipError::Cancelled);
                }
            }
            // Advance by what the inflater ACTUALLY consumed, not by the size of the chunk we
            // handed it. The inner loop can leave early with input still unread — on the
            // no-progress branch above — and advancing by `take` there would skip those bytes and
            // resume the stream in the middle of a deflate block, quietly decoding a different
            // member's content than the archive holds.
            //
            // **Both this and the stall guard below are unobservable through the public API
            // today, and that was measured rather than assumed.** With `flate2` pinned as it is,
            // the inner loop only ever leaves with `offset == take` or through `StreamEnd`, so
            // advancing by `take` produces identical output on every input the suite can build,
            // and deleting the stall guard hangs nothing. They are kept as defence in depth
            // against a decompressor that behaves differently — a version bump, or the general
            // ZIP crate the module header contemplates taking — because the failure they guard
            // against is *quietly wrong content*, which no cap and no report would catch. The
            // property they exist to protect IS pinned, by
            // `a_deflate_member_is_never_served_its_neighbours_content`: a multi-chunk member
            // arrives whole, in order, and never carries its neighbour's bytes.
            if offset == 0 {
                // Nothing consumed and nothing produced from a full chunk: more of the same input
                // cannot help, and re-reading it would spin. A stalled stream is malformed.
                return Err(ZipError::Malformed);
            }
            read_at = read_at
                .checked_add(offset as u64)
                .ok_or(ZipError::Malformed)?;
            remaining = remaining.saturating_sub(offset as u64);
        }
    }

    /// Charge `produced` bytes against the per-entry cap and both whole-archive budgets.
    ///
    /// Which budget applies is decided by `how`, and the two failures are deliberately different
    /// errors because the caller does deliberately different things with them: an inflation
    /// breach aborts the import (a bomb), an extraction breach drops the item and keeps going
    /// (a genuinely enormous, genuinely legitimate deck).
    fn account(
        &mut self,
        entry_total: usize,
        produced: usize,
        entry_cap: usize,
        how: Production,
    ) -> Result<(), ZipError> {
        if entry_total > entry_cap {
            return Err(ZipError::EntryTooLarge);
        }
        if how == Production::Inflated {
            let inflated = self.total_inflated.saturating_add(produced);
            if inflated > MAX_TOTAL_INFLATED_BYTES {
                return Err(ZipError::ArchiveTooLarge);
            }
            self.total_inflated = inflated;
        }
        let extracted = self.total_extracted.saturating_add(produced);
        if extracted > MAX_TOTAL_EXTRACTED_BYTES {
            return Err(ZipError::ExtractionBudgetExhausted);
        }
        self.total_extracted = extracted;
        Ok(())
    }
}

/// Walk the central directory **through the byte source, one record at a time**. Encrypted
/// entries and unsupported methods are recorded rather than refused here, so the caller can drop
/// just the affected part and report it.
///
/// # Why this streams rather than reading the directory into a buffer
///
/// `cd_size` is a 32-bit field the archive chooses freely, bounded only by the file length — and
/// admission allows 512 MiB. The entry-count cap does **not** bound it: an archive may declare one
/// entry and a half-gigabyte directory. So `vec![0u8; cd_size]` would put an attacker-sized
/// allocation in the working set, which is precisely the term the [`ByteSource`] exists to remove;
/// reading the file through a source and then materialising a slab of it would give the memory
/// arithmetic back with one line.
///
/// The same argument applies one level down, to the names: 4 096 entries each declaring a
/// 65 000-byte name is half a gigabyte of `String` before any cap is consulted. So the name cap is
/// applied to `name_len` **before** any name is read or allocated, and an over-long name is only
/// ever read up to [`MAX_ZIP_NAME_LEN`] bytes — enough for the report to quote it, never enough to
/// be a budget.
///
/// Peak here is therefore one 46-byte header plus one 512-byte name buffer, plus the entry table
/// itself, which the entry cap and the name cap bound together at a few mebibytes — whatever the
/// archive claims about itself.
fn read_central_directory(
    src: &mut dyn ByteSource,
    cd_offset: u64,
    cd_size: u64,
    declared: usize,
) -> Result<Vec<EntryMeta>, ImportError> {
    let mut entries: Vec<EntryMeta> = Vec::new();
    let mut seen: HashSet<String> = HashSet::new();
    let mut header = [0u8; CDIR_HEADER_LEN];
    // The one name buffer, reused for every record.
    let mut name_buf = [0u8; MAX_ZIP_NAME_LEN];
    let mut at: u64 = 0;

    while let Some(header_end) = at.checked_add(CDIR_HEADER_LEN as u64) {
        if header_end > cd_size {
            break; // the directory ended (or never was one); take what we have
        }
        let base = cd_offset.checked_add(at).ok_or(ImportError::NotAnArchive)?;
        src.read_exact_at(base, &mut header)?;
        if le_u32(&header, 0) != Some(CDIR_SIG) {
            break;
        }
        if entries.len() >= MAX_ZIP_ENTRIES {
            return Err(ImportError::TooManyEntries {
                limit: MAX_ZIP_ENTRIES,
            });
        }
        // Byte 5 of the fixed header is "version made by"'s high byte — the host OS. Byte 4, the
        // spec-version low byte, is never used by this reader.
        let host_os = *header.get(5).ok_or(ImportError::NotAnArchive)?;
        let external_attrs = le_u32(&header, 38).ok_or(ImportError::NotAnArchive)?;
        let flags = le_u16(&header, 8).ok_or(ImportError::NotAnArchive)?;
        let method = le_u16(&header, 10).ok_or(ImportError::NotAnArchive)?;
        let comp = le_u32(&header, 20).ok_or(ImportError::NotAnArchive)?;
        let uncomp = le_u32(&header, 24).ok_or(ImportError::NotAnArchive)?;
        let name_len = usize::from(le_u16(&header, 28).ok_or(ImportError::NotAnArchive)?);
        let extra_len = u64::from(le_u16(&header, 30).ok_or(ImportError::NotAnArchive)?);
        let comment_len = u64::from(le_u16(&header, 32).ok_or(ImportError::NotAnArchive)?);
        let local_offset = le_u32(&header, 42).ok_or(ImportError::NotAnArchive)?;
        if local_offset == u32::MAX || comp == u32::MAX || uncomp == u32::MAX {
            return Err(ImportError::Zip64Unsupported);
        }

        // THE CAP IS CONSULTED BEFORE THE ALLOCATION IT BOUNDS. An over-long or NUL-bearing name
        // is dropped rather than refusing the archive — it may still hold everything we need — and
        // it is never a path component either way.
        let over_long = name_len > MAX_ZIP_NAME_LEN;
        let take = name_len.min(MAX_ZIP_NAME_LEN);
        let name_end = header_end
            .checked_add(name_len as u64)
            .ok_or(ImportError::NotAnArchive)?;
        if name_end > cd_size {
            return Err(ImportError::NotAnArchive);
        }
        let raw = name_buf.get_mut(..take).ok_or(ImportError::NotAnArchive)?;
        if take > 0 {
            src.read_exact_at(
                base.checked_add(CDIR_HEADER_LEN as u64)
                    .ok_or(ImportError::NotAnArchive)?,
                raw,
            )?;
        }
        let bad_name = over_long || raw.contains(&0);
        let name = String::from_utf8_lossy(raw).into_owned();
        let folded = pkgpath::fold(&name);
        // A refused name is never inserted into the duplicate set: a truncated or NUL-bearing name
        // must not be able to shadow the legitimate part it happens to fold onto.
        let duplicate = !bad_name && !seen.insert(folded.clone());

        entries.push(EntryMeta {
            name,
            folded,
            method,
            // General-purpose bit 0 is the encryption flag.
            encrypted: flags & 1 != 0,
            declared_size: u64::from(uncomp),
            compressed_size: u64::from(comp),
            local_offset: u64::from(local_offset),
            duplicate,
            bad_name,
            host_os,
            external_attrs,
        });

        at = name_end
            .checked_add(extra_len)
            .and_then(|v| v.checked_add(comment_len))
            .ok_or(ImportError::NotAnArchive)?;
    }
    if entries.is_empty() && declared > 0 {
        return Err(ImportError::NotAnArchive);
    }
    Ok(entries)
}

/// The LAST occurrence of a 4-byte signature — the EOCD is at the end, and a comment could
/// contain a decoy signature earlier.
fn rfind_sig(buf: &[u8], sig: u32) -> Option<usize> {
    let needle = sig.to_le_bytes();
    (0..buf.len().saturating_sub(3))
        .rev()
        .find(|&i| buf.get(i..i.saturating_add(4)) == Some(&needle[..]))
}

/// The FIRST occurrence of a 4-byte signature.
fn find_sig(buf: &[u8], sig: u32) -> Option<usize> {
    let needle = sig.to_le_bytes();
    (0..buf.len().saturating_sub(3)).find(|&i| buf.get(i..i.saturating_add(4)) == Some(&needle[..]))
}

fn le_u16(buf: &[u8], at: usize) -> Option<u16> {
    let end = at.checked_add(2)?;
    let s = buf.get(at..end)?;
    Some(u16::from_le_bytes([*s.first()?, *s.get(1)?]))
}

fn le_u32(buf: &[u8], at: usize) -> Option<u32> {
    let end = at.checked_add(4)?;
    let s = buf.get(at..end)?;
    Some(u32::from_le_bytes([
        *s.first()?,
        *s.get(1)?,
        *s.get(2)?,
        *s.get(3)?,
    ]))
}

/// White-box tests, inline by exception — the same documented exception `pkgpath.rs` and
/// `selahcue_core::scripture` use: a private, total, pure predicate whose exact behaviour is a
/// merge gate, where routing it through a whole archive just to reach it would obscure what is
/// actually being asserted. `EntryMeta` is `pub(crate)`, so an integration test in `tests/` cannot
/// construct one at all — `is_symlink`'s only other coverage is indirect, through
/// `safe_extract`'s own integration tests.
#[cfg(test)]
mod tests {
    use super::*;

    fn entry(host_os: u8, external_attrs: u32) -> EntryMeta {
        EntryMeta {
            name: "x".into(),
            folded: "x".into(),
            method: METHOD_STORE,
            encrypted: false,
            declared_size: 0,
            compressed_size: 0,
            local_offset: 0,
            duplicate: false,
            bad_name: false,
            host_os,
            external_attrs,
        }
    }

    #[test]
    fn a_unix_entry_with_the_symlink_mode_bits_is_a_symlink() {
        // 0o120777: S_IFLNK | 0777, exactly what `ln -s` produces, in the upper 16 bits.
        assert!(entry(UNIX_HOST_OS, 0o120_777 << 16).is_symlink());
    }

    #[test]
    fn a_unix_entry_with_a_regular_file_mode_is_not_a_symlink() {
        // 0o100644: S_IFREG | 0644 — an ordinary file, same host OS.
        assert!(!entry(UNIX_HOST_OS, 0o100_644 << 16).is_symlink());
    }

    #[test]
    fn a_unix_entry_with_no_mode_recorded_is_not_a_symlink() {
        // The common case for an archive nobody bothered to set attributes on: zero is not a
        // valid S_IFLNK value under the format mask, so this must read as "not a symlink", never
        // panic or default the other way.
        assert!(!entry(UNIX_HOST_OS, 0).is_symlink());
    }

    #[test]
    fn the_symlink_mode_bits_on_a_non_unix_host_are_never_interpreted_as_a_mode() {
        // The load-bearing case: host_os=0 (MS-DOS/FAT) with the SAME bit pattern a Unix symlink
        // would carry. On DOS this field is a DOS attribute byte, not a mode, and reading it as
        // one would be reading a mode nobody wrote — exactly the bug this predicate exists to
        // avoid. Removing the `host_os == UNIX_HOST_OS` guard is the mutation this pins.
        assert!(!entry(0, 0o120_777 << 16).is_symlink());
    }

    #[test]
    fn only_the_format_bits_are_consulted_not_the_permission_bits() {
        // Same format (S_IFLNK) with different, unusual permission bits: the verdict must not
        // move, because only the top 4 bits identify the entry TYPE.
        assert!(entry(UNIX_HOST_OS, 0o120_000 << 16).is_symlink());
        assert!(entry(UNIX_HOST_OS, 0o120_444 << 16).is_symlink());
        // And a directory (S_IFDIR = 0o040000) sharing no bits with S_IFLNK's format nibble must
        // read as not-a-symlink regardless of its permission bits.
        assert!(!entry(UNIX_HOST_OS, 0o040_755 << 16).is_symlink());
    }
}
