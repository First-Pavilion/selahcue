//! In-test builders for ZIP containers and `.pptx` packages.
//!
//! **Policy: no hostile file is ever committed to this repository.** Every adversarial input in
//! these tests is constructed programmatically from bytes the test itself writes. That is better
//! than committed binaries in four ways: a reviewer reads the hostile shape in the diff instead
//! of trusting a filename; a malicious fixture never exists as a file for a scanner to flag or a
//! person to double-click; fixtures cannot silently rot; and a bomb declaring four gigabytes
//! costs a few kilobytes of test source.
//!
//! The ZIP writer below emits local headers and a central directory at documented fixed offsets,
//! rather than going through a ZIP library, precisely so it can write the entry names and the
//! lying size fields a library would refuse to produce.

#![allow(dead_code)]

use std::io::Write;

// --- a hand-written ZIP writer ---------------------------------------------------------

pub const STORE: u16 = 0;
pub const DEFLATE: u16 = 8;

/// One member, with every field a hostile archive might lie about left under test control.
#[derive(Debug, Clone)]
pub struct Entry {
    pub name: String,
    /// The bytes as they appear in the file (already compressed, if `method` says so).
    pub payload: Vec<u8>,
    pub method: u16,
    /// General-purpose flags; bit 0 is the encryption flag.
    pub flags: u16,
    /// What the headers CLAIM the entry inflates to. `None` = the truth.
    pub declared_size: Option<u32>,
    /// The name of another entry whose local header and payload this record points at.
    ///
    /// ZIP central-directory records carry a local offset each, and nothing in the format stops
    /// two of them naming the same one: an archive may declare four thousand distinct entries that
    /// all resolve to a single sixteen-mebibyte member. That is how a small file asks to be read
    /// many times its own size, and it is the shape the whole-archive WORK budget exists for —
    /// which cannot be tested at all without the ability to write one.
    pub alias_of: Option<String>,
}

impl Entry {
    pub fn stored(name: &str, data: &[u8]) -> Self {
        Entry {
            name: name.to_string(),
            payload: data.to_vec(),
            method: STORE,
            flags: 0,
            declared_size: None,
            alias_of: None,
        }
    }

    pub fn deflated(name: &str, data: &[u8]) -> Self {
        Entry {
            name: name.to_string(),
            payload: deflate(data),
            method: DEFLATE,
            flags: 0,
            declared_size: Some(data.len() as u32),
            alias_of: None,
        }
    }

    /// Claim a different uncompressed size than the truth — the lying-header case, which is the
    /// PRIMARY bomb test: a correct reader must be stopped by the streaming counter, not by this.
    pub fn claiming(mut self, size: u32) -> Self {
        self.declared_size = Some(size);
        self
    }

    pub fn encrypted(mut self) -> Self {
        self.flags |= 1;
        self
    }

    pub fn with_method(mut self, method: u16) -> Self {
        self.method = method;
        self
    }

    /// A member whose already-deflated `payload` is supplied directly — for bombs, whose inflated
    /// form must never exist in the test process. `declared` is what the headers claim.
    pub fn raw_deflated(name: &str, payload: Vec<u8>, declared: u32) -> Self {
        Entry {
            name: name.to_string(),
            payload,
            method: DEFLATE,
            flags: 0,
            declared_size: Some(declared),
            alias_of: None,
        }
    }

    /// A central-directory record with **no local header of its own**, pointing at `target`'s.
    /// Both records then serve the same bytes under different names — legal ZIP, and the only way
    /// an archive can ask to be read many times its own size.
    pub fn aliasing(name: &str, target: &str, size: u32) -> Self {
        Entry {
            name: name.to_string(),
            payload: Vec::new(),
            method: STORE,
            flags: 0,
            declared_size: Some(size),
            alias_of: Some(target.to_string()),
        }
    }
}

/// Raw-deflate `data` (no zlib header), as a ZIP member stores it.
pub fn deflate(data: &[u8]) -> Vec<u8> {
    let mut e = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::best());
    e.write_all(data).expect("in-memory write cannot fail");
    e.finish().expect("in-memory finish cannot fail")
}

/// A raw-deflate stream that inflates to `n` zero bytes, built **without ever holding `n` bytes**.
///
/// The bomb payloads are hundreds of mebibytes inflated. Materialising one to compress it would
/// put that whole buffer in the test process, which is fatal in the very tests that measure the
/// importer's own allocation — the measurement would be swamped by the fixture.
pub fn deflate_zeros(n: usize) -> Vec<u8> {
    let mut e = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::best());
    let chunk = [0u8; 64 * 1024];
    let mut left = n;
    while left > 0 {
        let take = left.min(chunk.len());
        e.write_all(&chunk[..take])
            .expect("in-memory write cannot fail");
        left -= take;
    }
    e.finish().expect("in-memory finish cannot fail")
}

/// Assemble a ZIP container from `entries`.
pub fn zip(entries: &[Entry]) -> Vec<u8> {
    zip_declaring(entries, None)
}

/// Assemble a ZIP container from `entries`, optionally making the end-of-central-directory record
/// **lie** about how many records follow.
///
/// The lie is not decoration: the reader has two entry-count controls — a cheap refusal on the
/// declared count in the EOCD, and a cap inside the directory walk itself — and while the EOCD
/// number is honest the second one is unreachable, so a test aimed at it silently proves the
/// first. Under-declaring is exactly how a hostile archive would slip past the cheap check.
pub fn zip_declaring(entries: &[Entry], declared_entries: Option<u16>) -> Vec<u8> {
    let mut out: Vec<u8> = Vec::new();
    let mut offsets: Vec<u32> = Vec::new();
    for e in entries {
        if e.alias_of.is_some() {
            // No local header and no payload: this record borrows another entry's. Patched below,
            // once every real member's offset is known.
            offsets.push(u32::MAX);
            continue;
        }
        offsets.push(out.len() as u32);
        let declared = e.declared_size.unwrap_or(e.payload.len() as u32);
        out.extend_from_slice(&0x0403_4b50u32.to_le_bytes()); // local header signature
        out.extend_from_slice(&20u16.to_le_bytes()); // version needed
        out.extend_from_slice(&e.flags.to_le_bytes());
        out.extend_from_slice(&e.method.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes()); // mod time
        out.extend_from_slice(&0u16.to_le_bytes()); // mod date
        out.extend_from_slice(&0u32.to_le_bytes()); // crc (not verified by the reader)
        out.extend_from_slice(&(e.payload.len() as u32).to_le_bytes());
        out.extend_from_slice(&declared.to_le_bytes());
        out.extend_from_slice(&(e.name.len() as u16).to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes()); // extra len
        out.extend_from_slice(e.name.as_bytes());
        out.extend_from_slice(&e.payload);
    }
    // Resolve aliases now that every real member has an offset.
    let resolved: Vec<u32> = entries
        .iter()
        .zip(offsets.iter())
        .map(|(e, off)| match &e.alias_of {
            None => *off,
            Some(target) => {
                let i = entries
                    .iter()
                    .position(|c| &c.name == target && c.alias_of.is_none())
                    .expect("Entry::aliasing must name a real member of the same archive");
                offsets[i]
            }
        })
        .collect();

    let cd_offset = out.len() as u32;
    for (e, offset) in entries.iter().zip(resolved.iter()) {
        let declared = e.declared_size.unwrap_or(e.payload.len() as u32);
        // An alias's central record must state the SHARED member's extent, not its own (empty)
        // payload — that extent is what the reader copies.
        let compressed = match &e.alias_of {
            None => e.payload.len() as u32,
            Some(_) => declared,
        };
        out.extend_from_slice(&0x0201_4b50u32.to_le_bytes()); // central directory signature
        out.extend_from_slice(&20u16.to_le_bytes()); // version made by
        out.extend_from_slice(&20u16.to_le_bytes()); // version needed
        out.extend_from_slice(&e.flags.to_le_bytes());
        out.extend_from_slice(&e.method.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u32.to_le_bytes()); // crc
        out.extend_from_slice(&compressed.to_le_bytes());
        out.extend_from_slice(&declared.to_le_bytes());
        out.extend_from_slice(&(e.name.len() as u16).to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes()); // extra
        out.extend_from_slice(&0u16.to_le_bytes()); // comment
        out.extend_from_slice(&0u16.to_le_bytes()); // disk
        out.extend_from_slice(&0u16.to_le_bytes()); // internal attrs
                                                    // External attributes carry the Unix mode on archives that record one. A SYMLINK entry
                                                    // sets `0o120000 << 16` here. This reader never reads the field, which is the point: it
                                                    // cannot act on a link because it cannot see one.
        out.extend_from_slice(&0u32.to_le_bytes());
        out.extend_from_slice(&offset.to_le_bytes());
        out.extend_from_slice(e.name.as_bytes());
    }
    let cd_size = out.len() as u32 - cd_offset;
    let count = declared_entries.unwrap_or(entries.len() as u16);
    out.extend_from_slice(&0x0605_4b50u32.to_le_bytes()); // EOCD signature
    out.extend_from_slice(&0u16.to_le_bytes()); // this disk
    out.extend_from_slice(&0u16.to_le_bytes()); // cd start disk
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&cd_size.to_le_bytes());
    out.extend_from_slice(&cd_offset.to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes()); // comment length
    out
}

/// A symlink entry as a real archiver would write one: the Unix mode in the external attributes
/// and the link target as the entry's content. Our writer does not emit external attributes, so
/// this is expressed the only way it can matter here — as an entry whose *content* is a path.
pub fn symlink_entry(name: &str, target: &str) -> Entry {
    Entry::stored(name, target.as_bytes())
}

// --- a minimal .pptx package -----------------------------------------------------------

// --- a synthesised hostile archive, served rather than held ------------------------------

/// A [`ByteSource`](selahcue_import::ByteSource) that **synthesises** a hostile archive from a rule
/// instead of holding one.
///
/// The central directory only becomes dangerous at sizes no test could afford to materialise: the
/// measured worst case is a half-gigabyte file whose directory declares four thousand entries with
/// 65 000-byte names. A `Vec` of that would make the test process the thing being measured — the
/// fixture would swamp the very allocation the assertion is about. Serving the bytes from a rule
/// costs a few dozen bytes, so the only memory in play is the importer's own.
///
/// Nothing here is compressed or even real: the entries point at nothing and the file is mostly
/// zeros. That is the point. Every allocation the reader makes from this archive is one it made on
/// the archive's *say-so*, which is exactly what must not happen.
pub struct HostileDirectory {
    len: u64,
    cd_offset: u64,
    /// What the end-of-central-directory record CLAIMS the directory's size is.
    declared_cd_size: u64,
    /// How much of that is actually filled with well-formed records (0 = none at all).
    record_area: u64,
    entries: u16,
    name_len: u16,
}

impl HostileDirectory {
    /// `entries` records, each declaring a `name_len`-byte name. The whole directory is real and
    /// well-formed; it is simply enormous, and every name is far over the reader's name cap.
    pub fn long_names(entries: u16, name_len: u16) -> Self {
        let record = 46u64 + u64::from(name_len);
        let cd_size = record * u64::from(entries);
        HostileDirectory {
            len: cd_size + 22,
            cd_offset: 0,
            declared_cd_size: cd_size,
            record_area: cd_size,
            entries,
            name_len,
        }
    }

    /// A file of `len` bytes whose end-of-central-directory record claims a directory of
    /// `declared_cd_size` — with no records in it at all. The entry-count cap does not bound this
    /// in the slightest: the archive declares ONE entry and a directory of any size it likes.
    pub fn lying_size(len: u64, declared_cd_size: u64) -> Self {
        HostileDirectory {
            len,
            cd_offset: 0,
            declared_cd_size,
            record_area: 0,
            entries: 1,
            name_len: 0,
        }
    }

    fn byte_at(&self, at: u64) -> u8 {
        let eocd_at = self.len.saturating_sub(22);
        if at >= eocd_at {
            let i = (at - eocd_at) as usize;
            let mut eocd = [0u8; 22];
            eocd[..4].copy_from_slice(&0x0605_4b50u32.to_le_bytes());
            eocd[8..10].copy_from_slice(&self.entries.to_le_bytes());
            eocd[10..12].copy_from_slice(&self.entries.to_le_bytes());
            eocd[12..16].copy_from_slice(&(self.declared_cd_size as u32).to_le_bytes());
            eocd[16..20].copy_from_slice(&(self.cd_offset as u32).to_le_bytes());
            return eocd[i];
        }
        if at < self.cd_offset || at >= self.cd_offset + self.record_area {
            return 0;
        }
        let record = 46u64 + u64::from(self.name_len);
        let within = (at - self.cd_offset) % record;
        if within >= 46 {
            return b'n'; // the name, all 65 000 bytes of it
        }
        let mut header = [0u8; 46];
        header[..4].copy_from_slice(&0x0201_4b50u32.to_le_bytes());
        header[20..24].copy_from_slice(&1u32.to_le_bytes()); // compressed size
        header[24..28].copy_from_slice(&1u32.to_le_bytes()); // uncompressed size
        header[28..30].copy_from_slice(&self.name_len.to_le_bytes());
        header[within as usize]
    }
}

impl selahcue_import::ByteSource for HostileDirectory {
    fn len(&self) -> u64 {
        self.len
    }

    fn read_exact_at(
        &mut self,
        offset: u64,
        buf: &mut [u8],
    ) -> Result<(), selahcue_import::SourceError> {
        let end = offset
            .checked_add(buf.len() as u64)
            .ok_or(selahcue_import::SourceError::OutOfRange)?;
        if end > self.len {
            return Err(selahcue_import::SourceError::OutOfRange);
        }
        for (i, b) in buf.iter_mut().enumerate() {
            *b = self.byte_at(offset + i as u64);
        }
        Ok(())
    }
}

/// A raw-deflate stream that inflates to `n` bytes at a compression ratio **below** the importer's
/// ratio guard, built without ever holding `n` bytes.
///
/// [`deflate_zeros`] cannot exercise the byte counters at all: pure zeros compress at roughly
/// 1000:1, so the ratio guard refuses such a member after one mebibyte and neither the per-entry
/// cap nor the whole-archive total ever sees it. Diluting every block with two per cent
/// incompressible bytes buys a ratio near 50:1 — high enough that the fixture stays small, low
/// enough that the ratio guard stays out of the way and the byte counters are what fire.
pub fn deflate_lowish_ratio(n: usize) -> Vec<u8> {
    let mut e = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::fast());
    let mut block = [0u8; 64 * 1024];
    let mut state: u32 = 0x9E37_79B9;
    let mut left = n;
    while left > 0 {
        let noise = block.len() / 50;
        for b in block.iter_mut().take(noise) {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            *b = (state >> 24) as u8;
        }
        let take = left.min(block.len());
        e.write_all(&block[..take])
            .expect("in-memory write cannot fail");
        left -= take;
    }
    e.finish().expect("in-memory finish cannot fail")
}

/// One slide's content, as the builder should emit it.
#[derive(Debug, Clone, Default)]
pub struct SlideSpec {
    pub title: Option<String>,
    pub body: Vec<String>,
    pub notes: Option<String>,
    /// Media part names to reference with `r:embed`, paired with their bytes.
    pub images: Vec<(String, Vec<u8>)>,
    /// Emit a slide-number placeholder (`<p:ph type="sldNum"/>`) carrying this text, written the
    /// way PowerPoint writes it — inside an `<a:fld>`, not an `<a:r>`.
    ///
    /// Real decks carry one of these on very nearly every slide, and the builder emitted none, so
    /// the whole suite was blind to the importer treating them as body text. Measured across seven
    /// genuinely PowerPoint-authored decks: 124 `sldNum` placeholders carrying text, plus 5 `ftr`.
    pub slide_number: Option<String>,
    /// Emit a footer placeholder (`<p:ph type="ftr"/>`) carrying this text.
    pub footer: Option<String>,
    /// Emit a date placeholder (`<p:ph type="dt"/>`) carrying this text.
    pub date: Option<String>,
    /// Emit `show="0"` on `<p:sld>`.
    pub hidden: bool,
    /// A `<p:graphicFrame>` with this `uri` (a chart, a table, …).
    pub graphic_uri: Option<String>,
    /// Reference an image with `TargetMode="External"` pointing at this URL.
    pub external_image: Option<String>,
    /// Replace the whole slide XML with this, for the hostile cases.
    pub raw_xml: Option<String>,
}

impl SlideSpec {
    pub fn text(title: &str, body: &[&str]) -> Self {
        SlideSpec {
            title: Some(title.to_string()),
            body: body.iter().map(|s| s.to_string()).collect(),
            ..Default::default()
        }
    }
}

/// A `.pptx` package builder with an injection point for every hostile mutation the tests need.
///
/// # `entry` versus `replacing` — and why the difference is load-bearing
///
/// [`entry`](Self::entry) APPENDS a part. If it names a part the builder also generates, the
/// archive ends up holding two entries with that name, the reader flags the later one a duplicate
/// (correctly — first occurrence wins), and the *generated, benign* copy is the one that gets read.
/// A hostile override written that way is silently inert: the test still passes, but it passes
/// against the benign part, and it would go on passing with the control it guards deleted.
///
/// [`replacing`](Self::replacing) is the injection point for a hostile version OF a generated
/// part: it substitutes at generation time, so exactly one entry with that name exists and it is
/// the hostile one. A replacement that matches no generated part is a **panic**, not a no-op —
/// that mismatch is precisely how a test goes hollow, so it fails loudly instead.
#[derive(Debug, Clone, Default)]
pub struct PptxBuilder {
    pub slides: Vec<SlideSpec>,
    /// Replace `ppt/presentation.xml` (or omit it entirely with `Some(None)`).
    pub presentation_override: Option<Option<String>>,
    /// Entries spliced in **before** every generated part.
    ///
    /// Order in the central directory is not cosmetic: first occurrence wins for duplicate names,
    /// so an entry can only shadow a part it precedes. A test that appends its hostile entry can
    /// therefore never observe shadowing at all, whatever the code does.
    pub before: Vec<Entry>,
    /// Extra entries spliced into the archive verbatim, IN ADDITION to the generated parts.
    pub extra: Vec<Entry>,
    /// Entries that SUBSTITUTE for the generated part of the same name.
    pub replace: Vec<Entry>,
    /// Store every generated part rather than deflating it.
    ///
    /// Hand-checked offsets stay simple, and — the reason it is now wired up rather than merely
    /// declared, which it was until the stack tests needed it — a stored archive never enters
    /// `flate2`, which is where all but three kilobytes of the import's stack goes. Measuring the
    /// *walk's* stack use is impossible while a fixed ninety-kilobyte dependency cost sits in the
    /// same number.
    pub stored: bool,
    /// Make the end-of-central-directory record CLAIM this many entries instead of the truth.
    pub declared_entries: Option<u16>,
}

impl PptxBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn slide(mut self, spec: SlideSpec) -> Self {
        self.slides.push(spec);
        self
    }

    /// Append an extra part. Use [`replacing`](Self::replacing) instead when the part shares a
    /// name with one the builder generates.
    pub fn entry(mut self, e: Entry) -> Self {
        self.extra.push(e);
        self
    }

    /// Splice an entry in BEFORE every generated part — the only position from which an entry can
    /// shadow one, because first occurrence wins.
    pub fn first(mut self, e: Entry) -> Self {
        self.before.push(e);
        self
    }

    /// Substitute `e` for the generated part of the same name. Panics at `build()` if no generated
    /// part has that name.
    pub fn replacing(mut self, e: Entry) -> Self {
        self.replace.push(e);
        self
    }

    /// STORE every generated part instead of deflating it — the same package, never handed to the
    /// inflater.
    pub fn stored(mut self) -> Self {
        self.stored = true;
        self
    }

    /// The assembled archive bytes.
    pub fn build(&self) -> Vec<u8> {
        let mut entries: Vec<Entry> = self.before.clone();
        let mut used = vec![false; self.replace.len()];
        // Every generated part goes through here, so a replacement can substitute for ANY of them
        // — and is recorded as used, so an override that matched nothing is caught below.
        let mut add = |entries: &mut Vec<Entry>, name: &str, data: &[u8]| match self
            .replace
            .iter()
            .position(|r| r.name == name)
        {
            Some(i) => {
                used[i] = true;
                entries.push(self.replace[i].clone());
            }
            None if self.stored => entries.push(Entry::stored(name, data)),
            None => entries.push(Entry::deflated(name, data)),
        };

        add(
            &mut entries,
            "[Content_Types].xml",
            br#"<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>"#,
        );
        add(
            &mut entries,
            "_rels/.rels",
            br#"<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>"#,
        );

        match &self.presentation_override {
            Some(None) => {} // deliberately absent, to exercise the inferred-order fallback
            Some(Some(xml)) => add(&mut entries, "ppt/presentation.xml", xml.as_bytes()),
            None => {
                let ids: String = (0..self.slides.len())
                    .map(|i| format!(r#"<p:sldId id="{}" r:id="rId{}"/>"#, 256 + i, i + 1))
                    .collect();
                add(
                    &mut entries,
                    "ppt/presentation.xml",
                    format!(
                        r#"<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>"#
                    )
                    .as_bytes(),
                );
                let rels: String = (0..self.slides.len())
                    .map(|i| {
                        format!(
                            r#"<Relationship Id="rId{}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{}.xml"/>"#,
                            i + 1,
                            i + 1
                        )
                    })
                    .collect();
                add(
                    &mut entries,
                    "ppt/_rels/presentation.xml.rels",
                    format!(
                        r#"<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>"#
                    )
                    .as_bytes(),
                );
            }
        }

        for (i, slide) in self.slides.iter().enumerate() {
            let n = i + 1;
            let xml = slide.raw_xml.clone().unwrap_or_else(|| slide_xml(slide));
            add(
                &mut entries,
                &format!("ppt/slides/slide{n}.xml"),
                xml.as_bytes(),
            );

            let mut rels = String::new();
            if slide.notes.is_some() {
                rels.push_str(&format!(
                    r#"<Relationship Id="rIdNotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide{n}.xml"/>"#
                ));
                add(
                    &mut entries,
                    &format!("ppt/notesSlides/notesSlide{n}.xml"),
                    notes_xml(slide.notes.as_deref().unwrap_or_default()).as_bytes(),
                );
            }
            for (k, (media, bytes)) in slide.images.iter().enumerate() {
                // The `../media/x.png` form is what a real PowerPoint file writes, and it is the
                // case a naive "reject any `..`" would break.
                rels.push_str(&format!(
                    r#"<Relationship Id="rIdImg{k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{media}"/>"#
                ));
                let part = format!("ppt/media/{media}");
                if !entries.iter().any(|e| e.name == part) {
                    add(&mut entries, &part, bytes);
                }
            }
            if let Some(url) = &slide.external_image {
                rels.push_str(&format!(
                    r#"<Relationship Id="rIdExt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{url}" TargetMode="External"/>"#
                ));
            }
            add(
                &mut entries,
                &format!("ppt/slides/_rels/slide{n}.xml.rels"),
                format!(
                    r#"<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>"#
                )
                .as_bytes(),
            );
        }

        // A replacement that matched no generated part means the test believes it substituted
        // something and did not. That is exactly how the three hollow tests in this suite came to
        // pass against a broken implementation, so it fails loudly rather than silently.
        for (i, r) in self.replace.iter().enumerate() {
            assert!(
                used[i],
                "PptxBuilder::replacing({:?}) matched no generated part — the override would have \
                 been silently inert and the test would pass vacuously",
                r.name
            );
        }

        entries.extend(self.extra.iter().cloned());
        zip_declaring(&entries, self.declared_entries)
    }
}

fn text_body(lines: &[String]) -> String {
    lines
        .iter()
        .map(|l| format!("<a:p><a:r><a:t>{}</a:t></a:r></a:p>", escape(l)))
        .collect()
}

fn escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

/// A placeholder shape whose single paragraph sits in an `<a:fld>` rather than an `<a:r>` — which
/// is exactly how PowerPoint writes a slide number, a footer and a date.
fn field_placeholder(kind: &str, text: &str) -> String {
    format!(
        r#"<p:sp><p:nvSpPr><p:nvPr><p:ph type="{kind}" sz="quarter" idx="10"/></p:nvPr></p:nvSpPr><p:txBody><a:bodyPr/><a:p><a:fld id="{{B8A0F4E1-0000-0000-0000-000000000000}}" type="slidenum"><a:t>{}</a:t></a:fld></a:p></p:txBody></p:sp>"#,
        escape(text)
    )
}

fn slide_xml(spec: &SlideSpec) -> String {
    let mut shapes = String::new();
    if let Some(title) = &spec.title {
        shapes.push_str(&format!(
            r#"<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{}</a:t></a:r></a:p></p:txBody></p:sp>"#,
            escape(title)
        ));
    }
    // Furniture goes in BEFORE the body, as PowerPoint's own shape tree usually does — so a
    // regression that treats it as body text lands it at the FRONT of the joined body, which is
    // where a real deck put its page number: `2026 Market Report | 2 | The market is moving…`.
    if let Some(n) = &spec.slide_number {
        shapes.push_str(&field_placeholder("sldNum", n));
    }
    if let Some(f) = &spec.footer {
        shapes.push_str(&field_placeholder("ftr", f));
    }
    if let Some(d) = &spec.date {
        shapes.push_str(&field_placeholder("dt", d));
    }
    if !spec.body.is_empty() {
        shapes.push_str(&format!(
            r#"<p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody>{}</p:txBody></p:sp>"#,
            text_body(&spec.body)
        ));
    }
    for (k, _) in spec.images.iter().enumerate() {
        shapes.push_str(&format!(
            r#"<p:pic><p:blipFill><a:blip r:embed="rIdImg{k}"/></p:blipFill><p:spPr><a:xfrm><a:off x="1219200" y="685800"/><a:ext cx="6096000" cy="3429000"/></a:xfrm></p:spPr></p:pic>"#
        ));
    }
    if spec.external_image.is_some() {
        shapes.push_str(
            r#"<p:pic><p:blipFill><a:blip r:embed="rIdExt"/></p:blipFill><p:spPr/></p:pic>"#,
        );
    }
    if let Some(uri) = &spec.graphic_uri {
        shapes.push_str(&format!(
            r#"<p:graphicFrame><a:graphic><a:graphicData uri="{uri}"/></a:graphic></p:graphicFrame>"#
        ));
    }
    let show = if spec.hidden { r#" show="0""# } else { "" };
    format!(
        r#"<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"{show}><p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>"#
    )
}

fn notes_xml(text: &str) -> String {
    let lines: Vec<String> = text.lines().map(str::to_string).collect();
    format!(
        r#"<?xml version="1.0"?><p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody>{}</p:txBody></p:sp></p:spTree></p:cSld></p:notes>"#,
        text_body(&lines)
    )
}

// --- image fixtures --------------------------------------------------------------------

// --- a decodable JPEG ------------------------------------------------------------------

/// A minimal but genuinely decodable baseline JPEG: `w`×`h` grayscale, flat blocks, optionally
/// carrying an EXIF orientation tag.
///
/// There is no JPEG *encoder* in this tree, and JPEG is the format real church decks overwhelmingly
/// embed — so without this the dominant case never went through the `.pptx` path at all, and
/// "text + images" was only ever proven for PNG. The bitstream is hand-assembled: one quantisation
/// table, a DC table whose codes are their own category, an end-of-block AC code, and one flat
/// block per 8×8 cell.
pub fn jpeg(w: u16, h: u16, orientation: Option<u16>) -> Vec<u8> {
    fn segment(marker: u8, payload: &[u8]) -> Vec<u8> {
        let len = (payload.len() + 2) as u16;
        let mut v = vec![0xFF, marker];
        v.extend_from_slice(&len.to_be_bytes());
        v.extend_from_slice(payload);
        v
    }

    let mut bytes = vec![0xFF, 0xD8];

    if let Some(o) = orientation {
        let mut tiff = vec![b'I', b'I', 0x2A, 0x00];
        tiff.extend_from_slice(&8u32.to_le_bytes()); // IFD0 at offset 8
        tiff.extend_from_slice(&1u16.to_le_bytes()); // one entry
        tiff.extend_from_slice(&0x0112u16.to_le_bytes()); // tag: Orientation
        tiff.extend_from_slice(&3u16.to_le_bytes()); // type: SHORT
        tiff.extend_from_slice(&1u32.to_le_bytes()); // count: 1
        tiff.extend_from_slice(&o.to_le_bytes());
        tiff.extend_from_slice(&[0, 0]);
        tiff.extend_from_slice(&0u32.to_le_bytes()); // no next IFD
        let mut payload = b"Exif\0\0".to_vec();
        payload.extend_from_slice(&tiff);
        bytes.extend(segment(0xE1, &payload));
    }

    // DQT: every entry 16.
    let mut dqt = vec![0x00];
    dqt.extend(std::iter::repeat_n(16u8, 64));
    bytes.extend(segment(0xDB, &dqt));

    // SOF0: 8-bit, one component, 1x1 sampled.
    let mut sof = vec![8u8];
    sof.extend_from_slice(&h.to_be_bytes());
    sof.extend_from_slice(&w.to_be_bytes());
    sof.extend_from_slice(&[1, 1, 0x11, 0x00]);
    bytes.extend(segment(0xC0, &sof));

    // DHT DC table 0: twelve codes of length four, each equal to its index.
    let mut dc = vec![0x00];
    let mut bits = [0u8; 16];
    bits[3] = 12;
    dc.extend_from_slice(&bits);
    dc.extend(0u8..12u8);
    bytes.extend(segment(0xC4, &dc));

    // DHT AC table 0: one code of length two for end-of-block.
    let mut ac = vec![0x10];
    let mut bits = [0u8; 16];
    bits[1] = 1;
    ac.extend_from_slice(&bits);
    ac.push(0x00);
    bytes.extend(segment(0xC4, &ac));

    bytes.extend(segment(0xDA, &[1, 1, 0x00, 0x00, 0x3F, 0x00]));

    // One MCU per 8x8 cell: DC category 0 (no difference) then end-of-block.
    let mcus = (w.div_ceil(8) as usize) * (h.div_ceil(8) as usize);
    let mut stream = String::new();
    for _ in 0..mcus {
        stream.push_str("0000"); // DC category 0, code = index 0, length 4
        stream.push_str("00"); // AC end-of-block
    }
    while !stream.len().is_multiple_of(8) {
        stream.push('1'); // pad with ones, per the specification
    }
    for chunk in stream.as_bytes().chunks(8) {
        let mut byte = 0u8;
        for (i, c) in chunk.iter().enumerate() {
            if *c == b'1' {
                byte |= 1 << (7 - i);
            }
        }
        bytes.push(byte);
        if byte == 0xFF {
            bytes.push(0x00); // byte stuffing
        }
    }
    bytes.extend_from_slice(&[0xFF, 0xD9]);
    bytes
}

/// A tiny valid PNG. Built with the encoder already in the tree rather than committed, for the
/// same reason as everything else here.
pub fn png(w: u32, h: u32) -> Vec<u8> {
    let mut out = Vec::new();
    {
        let mut enc = png::Encoder::new(&mut out, w, h);
        enc.set_color(png::ColorType::Rgba);
        enc.set_depth(png::BitDepth::Eight);
        let mut writer = enc.write_header().expect("header");
        let data: Vec<u8> = (0..(w * h))
            .flat_map(|i| [(i % 251) as u8, 0x40, 0x80, 0xFF])
            .collect();
        writer.write_image_data(&data).expect("pixels");
    }
    out
}
