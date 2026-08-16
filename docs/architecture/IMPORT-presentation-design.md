# SelahCue — Presentation import: design specification

Version: 2.0 · Date: 2026-08-15 · Owner: Software Architect (Aria) · Status: For review — Kenji implements from this, not from the tasking
Goal Contract: `docs/delivery/goals/GOAL-arch-presentation-import.md`
Decision Records: `docs/architecture/adr/ADR-0024-presentation-import.md` · `docs/architecture/adr/ADR-0025-jpeg-still-image-decode.md`
Security constraint set: `docs/security/THREAT-MODEL-presentation-import.md` (Sana). **This design is built to her B1–B4 as written.** B5 is superseded for JPEG only by the owner's scope decision (§9); everything else B5 excludes stays excluded.

> This document defines component boundaries, contracts, limits and a test strategy. It does not write code, create ClickUp tickets, amend the PRD, or decide the product questions in §17.

**Changes from v1.0:** the owner resolved the image-scope question in favour of adding JPEG decode as part of this work (§9 is new). Sana's threat model landed and materially changed three things: the archive reader reads through an injected byte source rather than a slice, because her 512 MiB admission cap forbids holding the file in memory (§7.1); decompression caps are enforced on **actual** inflated bytes, because declared ZIP sizes lie (§7.2); and extracted media is staged and committed atomically rather than written straight into the media store (§8.4).

---

## 1. Readiness verdict

**Ready for implementation review.** With the owner's decision to add JPEG decode, the feature is buildable end to end.

One prerequisite remains and it is not optional: **`media_repo` has no production caller** (sweep of the whole tree — hits only in `lib.rs` and its own test), so the operator's `MediaLibrary` is in-memory and is lost on restart. Imported images would vanish when the app closes. There is also **no media store**: nothing in the tree ever copies image bytes into an app-owned directory, and a pptx image exists only inside the archive, so unlike `deck_import_image` there is no user path to reference in place. Both are introduced by this work (§8.4) but the persistence wiring is a distinct piece of work that must land before or with the image stage (§18).

The text half — `.txt`, pasted text, and the text and speaker notes of a `.pptx` — has no prerequisites and can start immediately.

---

## 2. Evidence labels

- **Verified** — observed in the repository at a cited path.
- **Inferred** — follows from verified evidence but is not itself observed.
- **Assumed** — used to make the design concrete; needs confirmation, owner named.
- **Unknown** — unresolved and decision-relevant.

---

## 3. Current-state facts this design stands on

| Fact | Label | Evidence |
|---|---|---|
| No presentation import exists; no PRD requirement covers it | Verified | grep of `SelahCue-PRD.md` for `PowerPoint`/`pptx`/`clipboard` returns only FR-127 (unrelated R5 note export); no ClickUp task found |
| Still-image decode is **PNG only**, **in-process**, and takes a byte slice | Verified | `crates/selahcue-engine/src/media.rs:138` `decode_png(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError>`; signature allowlist `:146`; module doc `:21-23` states the in-process seam explicitly |
| The ADR-0016 out-of-process sandbox is **not shipped**; there is no worker, no seccomp/AppContainer/seatbelt code | Verified (absence) | repository sweep — three `sandbox` hits, all comments |
| Decode limits are caller-supplied and public: `max_width`/`max_height` 8192, `max_pixels` 40 M, `max_encoded_bytes` 64 MiB | Verified | `selahcue-engine/src/media.rs:36-59` |
| Dimension and pixel checks run **before** allocation | Verified | `selahcue-engine/src/media.rs:164-172`, allocation at `:172` |
| There is **no decode timeout anywhere** — only size and dimension budgets | Verified (absence) | no `Duration` or watchdog in the decode path |
| `DecodeError` is `{ Empty, Missing, TooLarge, Unsupported, Oversize, Malformed }`, `Copy`, with no `Display` | Verified | `selahcue-engine/src/media.rs:62-76` |
| No media store: imported media is referenced at the user's path in place | Verified (absence) | sweep of `fs::write` / `File::create` / `OpenOptions` — ten hits, none image-related |
| `media_repo` exists, is tested, and has **no production caller** | Verified (absence) | `media_repo` call sweep |
| `deck_import_image` offers a `jpg`/`jpeg` filter although only PNG decodes, and never probes dimensions | Verified | `crates/selahcue-operator/src/main.rs:1729-1756`; `deck_workspace.rs:696-708` |
| FR-138 is entirely unimplemented; `canonicalize` has zero hits in the tree | Verified (absence) | story `86ak0qmzv`, `planning/todo`; deferral recorded at `engine/src/scene.rs:306-309` |
| `Element::Image` references media by **path** (`MediaRef`, cap 1024 bytes), not by `MediaId` | Verified | `crates/selahcue-present/src/theme.rs:183-204`; `MediaRef::CAP` at `engine/src/scene.rs:314` |
| An `AuthoredSlide` carries only `elements`, `background`, `notes`, `transition`, `auto_advance_secs` — there are no title/body fields | Verified | `crates/selahcue-present/src/deck.rs:86-105` |
| `Theme` carries `title: RegionStyle` and `body: RegionStyle`, each with per-mille geometry, colour, size and fit | Verified | `crates/selahcue-present/src/theme.rs:45-66, 386-418` |
| Existing output caps: `MAX_DECK_SLIDES` 500, `MAX_ELEMENTS` 64/slide, `MAX_TEXT_ELEMENT_LEN` 2000 chars, `MAX_NOTES_LEN` 4000 chars, `MAX_MEDIA_ASSETS` 1000, `MAX_MEDIA_PATH_LEN` 1024 | Verified | `present/deck.rs:33,36`; `present/theme.rs:259,294`; `core/media.rs:19,26` |
| The deck table's primary key is the deck **name**; `DeckLibrary` silently rewrites collisions to `Name (2)` | Verified | `deck_library.rs:462-474`, `:220-231`; `deck_repo.rs:38-51` `ON CONFLICT(name)` |
| The live output runs in a **separate process** from the operator console | Verified | `selahcue-desktop` bin `selahcue-output`; Sana §1 |
| No `zip`, `roxmltree` dependency. `quick-xml` appears only transitively via `wayland-scanner` on Linux | Verified (absence) | all three `Cargo.lock` files |
| `flate2 = "1"` is already a **direct first-party dependency** (of `selahcue-scripture`) | Verified | `crates/selahcue-scripture/Cargo.toml` |
| `png = "0.17"` (image-rs) is already a direct dependency of `selahcue-engine` | Verified | `crates/selahcue-engine/Cargo.toml` |
| The workspace declares no `[workspace.dependencies]`; every crate pins literal versions | Verified | `implementation/desktop/Cargo.toml` |
| The house error style is a hand-rolled enum plus manual `Display` and `Error`. `thiserror` and `anyhow` are used nowhere | Verified (absence) | repository sweep |
| `selahcue-present` has zero error enums — it signals failure with `Option`/`bool` | Verified (absence) | repository sweep |
| Operator is Tauri **v2** with `tauri-plugin-dialog` v2; there is no clipboard plugin | Verified | `crates/selahcue-operator/Cargo.toml` |
| `selahcue-operator` and `selahcue-stt` are excluded from the workspace; CI compile-checks the operator and runs `scripts/operator_headless.py` | Verified | `implementation/desktop/Cargo.toml:14`; `CLAUDE.md` |
| The operator webview uses `textContent` for untrusted deck names but `innerHTML` for structural rebuilds — the discipline is per-callsite | Verified | Sana §1, `dist/app.js` |

---

## 4. Where the work lives

### 4.1 Shape

```
   ┌─ trait ByteSource ─┐                                          ┌─ trait MediaSink ─┐
   │ bounded reads over │                                          │ stage bytes, get  │
   │ a ≤512 MiB file    │                                          │ back a slot id    │
   └─────────┬──────────┘                                          └─────────▲─────────┘
             │                                                               │
   ┌─────────▼───────────────────────────────────────────────────────────────┴─────────┐
   │  selahcue-import              (NEW workspace crate)                               │
   │  PURE. No std::fs. No net. No clipboard. No DB. No unsafe. Deterministic.         │  ──▶ SlideDeck
   │  Covered by `cargo test --workspace`. Fuzzable.                                   │  ──▶ ImportReport
   └───────────────────────────────────────────────────────────────────────────────────┘
             ▲                                                               │
   ┌─────────┴───────────────────────────────────────────────────────────────▼─────────┐
   │  selahcue-operator            (existing, excluded from the workspace)             │
   │  I/O SHELL. File dialog · staging dir · media commit · DeckLibrary · WebView.     │
   │  catch_unwind belt · 30 s timeout · one import at a time.                         │
   └───────────────────────────────────────────────────────────────────────────────────┘

   ┌───────────────────────────────────────────────────────────────────────────────────┐
   │  selahcue-engine::media       (existing workspace crate — EXTENDED, §9)           │
   │  decode_image(): signature allowlist · pre-allocation caps · PNG + JPEG · EXIF     │
   └───────────────────────────────────────────────────────────────────────────────────┘
```

`selahcue-import` depends on `selahcue-present` and, transitively, on `selahcue-engine` for `MediaRef` and the decode seam. It sits above `present`, beside `selahcue-app`. Nothing below it gains a dependency. `selahcue-core` and `selahcue-present` are untouched.

### 4.2 Module layout

```
crates/selahcue-import/
  src/
    lib.rs        pub use; crate-level lints
    limits.rs     every MAX_* constant + within_bounds() predicates
    model.rs      ImportedDocument / ImportedSlide / ImportedPicture / MediaSlot / ImportSource
    report.rs     ImportReport / SkippedItem / SkipKind / Notice / Truncation + string hygiene
    error.rs      ImportError, TextError, PptxError — hand-rolled + Display + Error
    source.rs     trait ByteSource + an in-memory impl for tests
    sink.rs       trait MediaSink + MediaSlot + a test double
    hygiene.rs    the C10 string sanitiser (pure, unit-testable in isolation)
    decode.rs     bytes -> String (BOM, UTF-16, lossy + count, NUL strip, CRLF)
    text.rs       &str -> ImportedDocument
    zip.rs        minimal hardened central-directory reader over a ByteSource
    ooxml.rs      iterative pull-reader for the OOXML part shapes we read
    pkgpath.rs    package-namespace relationship-target normalisation (C6)
    pptx.rs       orchestration: archive -> ImportedDocument
    build.rs      ImportedDocument + Theme + slot resolver -> SlideDeck + ImportReport
  tests/
    test_text.rs  test_decode.rs  test_hygiene.rs  test_zip.rs  test_ooxml.rs
    test_pkgpath.rs  test_pptx.rs  test_build.rs  test_report.rs  test_limits.rs
    test_panic_battery.rs  test_memory.rs
    support/pptx_builder.rs
  fuzz/
    fuzz_targets/fuzz_text.rs  fuzz_targets/fuzz_pptx.rs
```

One test file per module, public-API integration tests, per the house rule.

Crate-level lints, above the inherited `[workspace.lints.clippy] unwrap_used = "warn"`:

```rust
#![forbid(unsafe_code)]
#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic, clippy::todo, clippy::unimplemented)]
```

and, **on `zip.rs`, `ooxml.rs` and `pkgpath.rs` only** — the modules doing untrusted offset arithmetic:

```rust
#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]
```

Applied crate-wide these two are noise; applied to the three modules that parse binary offsets they force `checked_add`, `checked_sub` and `slice::get` exactly where `off + len` overflow is the classic bug. This is the single most effective structural defence in the design and it is a requirement, not a suggestion. It is also what makes C9's `catch_unwind` belt a backstop rather than the primary control.

### 4.3 Why a new workspace crate, and the honest cost

The owner's prior is right and I am not arguing against it. The reasoning, so it survives review:

- `selahcue-operator` is excluded from the workspace. `cargo test --workspace` does not reach it; CI only runs `cargo check` plus a headless WebView script (`CLAUDE.md`). Parsing hostile binary input is precisely the code that must be exhaustively tested, and Sana's §8 battery is large.
- The transform is pure by nature: bytes in, a `SlideDeck` and a report out.
- Fuzzing a workspace crate is routine (Sana R2). Fuzzing a Tauri binary crate is not.
- Sana's B2 requires a **CI assertion that the importer's dependency graph contains no network crate**. That assertion is a one-line `cargo tree -p selahcue-import` check against a named crate. It is only meaningful because the importer is its own crate — inside the operator, whose graph legitimately contains a network stack via `selahcue-scripture`'s `download` feature and `selahcue-cloud`, the property would be unstateable.
- The repository's own precedent is a pure, total, panic-free parser in a workspace crate covered by integration tests — `selahcue-core::scripture`. This is the same problem with a nastier input.

**The honest cost, which the tasking asked me not to skip.** The deck library, the collision logic and the persistence live in the operator and are staying there — the library is operator-owned by design. So *some* import logic is unavoidably in the excluded crate. The seam is drawn so that what remains is mechanically reviewable by eye:

The shell may: open a dialog; provide a `ByteSource` over the chosen file; provide a `MediaSink` that stages bytes; commit staged media; call `DeckLibrary::adopt_with_policy`; run the `catch_unwind` belt, the timeout and the import lock; serialise the report. The shell may **not**: know a file format; parse anything; compute or enforce a content limit; branch on file content; construct an `Element`. If a reviewer sees a `match` on a byte in `main.rs`, the seam has been violated.

**Why not put the build step in `selahcue-present`?** It would fit — it is a presentation-layer transform. Rejected: it would give `present` an import surface and a dependency on an import model, and split one coherent transform across two crates for no coverage gain, since `selahcue-import` is equally a workspace member. Keeping `present` free of import concepts also keeps it available to a future importer for another format without churn.

---

## 5. Data flow

Three sources, one pipeline. They differ only in how bytes become an `ImportedDocument`.

```
 .txt file ─┐                                                       ┌─▶ SlideDeck ─▶ DeckLibrary::adopt_with_policy
            ├─▶ decode::to_text ─▶ text::parse ─┐                   │               (§11 collision policy)
 clipboard ─┘   BOM/UTF-16/CRLF/NUL/lossy       ├─▶ ImportedDocument┤
                                                │                   └─▶ ImportReport ─▶ Tauri ─▶ WebView (§10)
 .pptx ────▶ ByteSource ─▶ zip::open ─▶ ooxml ──┘
             (≤512 MiB,    (actual-byte  (pull, depth-capped,
              chunked)      caps)         no DOCTYPE)
                                │
                                └─ per picture ─▶ decode_image probe ─▶ MediaSink::stage ─▶ MediaSlot
                                                  (reject ⇒ SkippedItem, never an error)
```

`ImportedDocument` is the neutral middle. It exists so all three sources converge on **one** place that decides how a slide's text becomes elements — otherwise pasted text and pptx text would drift into producing structurally different decks, and the difference would only be discovered by a user.

```rust
pub struct ImportedDocument {
    pub source: ImportSource,
    pub slides: Vec<ImportedSlide>,       // <= MAX_IMPORT_SLIDES
    pub report: ReportBuilder,            // accumulated during parse
}

pub struct ImportedSlide {
    pub title: Option<String>,            // <= MAX_TITLE_LEN chars, hygienised
    pub body: Vec<String>,                // <= MAX_SLIDE_LINES lines, each <= MAX_LINE_LEN chars
    pub notes: String,                    // <= MAX_NOTES_LEN chars
    pub pictures: Vec<ImportedPicture>,   // pptx only; <= MAX_PICTURES_PER_SLIDE
}

pub struct ImportedPicture { pub slot: MediaSlot, pub rect: PermilleRect }
pub struct MediaSlot(pub u32);            // resolved to a MediaRef only at commit (§8.4)

pub enum ImportSource { TxtFile { name: String }, Pptx { name: String }, Clipboard }
```

The report is built **during** parsing, not reconstructed afterwards, because only the parser knows which slide a dropped chart was on.

Pictures carry a `MediaSlot`, not a `MediaRef`, because the final media path is not known until the atomic commit (§8.4). This ordering is what makes B4 achievable.

### 5.1 How a slide's text becomes elements

`AuthoredSlide` has no title/body fields — content is `Vec<Element>`. "Imported decks adopt the SelahCue theme" therefore becomes concrete as: **copy geometry and colour from the active `Theme`'s `title` and `body` `RegionStyle`s into the created `Element::Text`s**. That is the theme's own definition of where title and body sit, so an imported slide lands exactly where an authored one would.

Per slide:

- title present ⇒ one `Element::Text` at `theme.title`'s rect, colour, `size_permille`, `line_height_permille`, alignment and `fit`, `z = 0`
- body non-empty ⇒ one `Element::Text` at `theme.body`'s equivalents, lines joined with `\n`, `z = 1`
- each committed picture ⇒ one `Element::Image { source, fit: ImageFit::Contain, rect, z = 2 + n }`

Two text elements, not one per line. A 60-line slide is then 2 elements against `MAX_ELEMENTS = 64`, leaving room for pictures.

> **ASSUMED — Kenji verifies first.** That `Element::Text` renders an embedded `\n` as a line break. Strongly implied (`compose.rs` carries `MAX_WRAP_WORDS`; `AuthoredSlide::confidence_slide` projects element text back into lines at `deck.rs:148-183`) but not run. If it does not hold, the fallback is one `Element::Text` per body line and `MAX_SLIDE_LINES` drops to `MAX_ELEMENTS - 1 - MAX_PICTURES_PER_SLIDE`. A ten-minute check that changes one function; called out so it is not discovered late.

**A consequence worth stating plainly, because it is user-visible:** an imported deck is an *authored* deck, so its text geometry is frozen at import time from whichever theme was active. Changing theme afterwards changes the background but does not reflow the text, unlike a scripture or song `Slide`. This is inherent to `SlideDeck` holding `AuthoredSlide` (ADR-0020 decision 1) and cannot be avoided here. It belongs in the release note.

---

## 6. The parse / I/O seam

Three injected effects, following the pattern the codebase already uses for exactly this purpose — `MediaLibrary::missing(|path| …)` takes an existence probe so core stays I/O-free (`core/media.rs:207`), and `plan::unresolved_content(deck_exists, media_exists)` does the same.

```rust
/// Bounded, random-access reads over the chosen file. The shell owns the File.
pub trait ByteSource {
    fn len(&self) -> u64;
    /// Fill `buf` from `offset`. Short reads are an error, not a silent truncation.
    fn read_exact_at(&mut self, offset: u64, buf: &mut [u8]) -> Result<(), SourceError>;
}

/// Stage validated image bytes. `bytes` have already passed the signature allowlist
/// and a bounded decode probe. Nothing is visible to the media library yet (B4).
pub trait MediaSink {
    fn stage(&mut self, bytes: &[u8], probe: &ImageProbe) -> Result<MediaSlot, StoreError>;
}

pub struct ImageProbe { pub width: u32, pub height: u32, pub byte_len: usize, pub format: ImageFormat }
pub enum StoreError { LibraryFull, WriteFailed, BudgetExceeded }
```

and, at build time, a slot resolver supplied after the media commit:

```rust
pub fn build_deck(
    doc: ImportedDocument,
    theme: &Theme,
    resolve: &dyn Fn(MediaSlot) -> Option<MediaRef>,
) -> (SlideDeck, ImportReport);
```

A slot that resolves to `None` (its commit failed) becomes a `SkipKind::MediaCommitFailed` entry and its `Element::Image` is simply not emitted. The slide keeps its text.

Everything else stays inside the crate — including the decode probe, because `decode_image` takes a byte slice and performs no I/O. That is a useful property of the existing API: the pure crate fully validates an image, and the shell only ever stages bytes that are already known good. **No rejected image is ever written, so there is no cleanup path to get wrong.**

Public entry points:

```rust
pub fn import_text(text: &str, source: ImportSource, theme: &Theme, opts: &TextOptions)
    -> Result<(SlideDeck, ImportReport), ImportError>;

pub fn import_txt_bytes(bytes: &[u8], name: &str, theme: &Theme, opts: &TextOptions)
    -> Result<(SlideDeck, ImportReport), ImportError>;

/// Stage 1 of 2. Parses and stages media; commits nothing.
pub fn read_pptx(
    src: &mut dyn ByteSource, name: &str,
    sink: &mut dyn MediaSink, cancel: &dyn Fn() -> bool,
) -> Result<ImportedDocument, ImportError>;
```

`ImportError` is reserved for **"nothing usable came out"** — an inadmissible archive, a zero-slide result, a cancellation, a timeout. Anything that produced at least one slide returns `Ok` with a report, because the owner's model is to import what is representable and report the rest. Getting this boundary wrong is the most likely way the partial-import rule gets violated in code, so it is stated as a rule: **if one slide survived, it is not an error.**

`cancel` is polled between slides, between pictures, and **inside the streaming inflate loop at chunk granularity** — Sana C13 requires no uninterruptible multi-GiB loop.

Tests supply an in-memory `ByteSource` over a `Vec<u8>` and a `FakeSink` that records what it was asked to stage. The whole pptx path, images included, is therefore testable in the workspace without touching a filesystem.

---

## 7. Reading a `.pptx`

### 7.1 Dependency decision — ZIP: hand-roll it, over `flate2`

**Decision: a minimal central-directory reader in `zip.rs`, inflating through `flate2`, which is already a direct first-party dependency (`selahcue-scripture/Cargo.toml`). The ZIP capability adds no new crate to the SBOM.**

What we need from ZIP is small and has not changed in decades:

1. Locate the End of Central Directory record by scanning back at most 65 557 bytes from the end.
2. Walk the central directory, reading per entry: name, general-purpose flags, compression method, declared sizes, local-header offset.
3. For a part we want **by exact normalised name**, seek to its local header, skip name and extra fields, and stream `compressed_size` bytes through an inflater into a bounded output.

Roughly 350 lines over a `ByteSource`. Reasons to prefer it to the `zip` crate:

- **Sana's B1 and B2 forbid the very APIs a general-purpose crate exists to provide.** Her B1 says the importer must never use an extract-to-directory helper, because several honour symlinks; entry types, mode bits and link targets must be ignored entirely. A crate whose main convenience is "extract this archive to that directory" is a crate whose main feature we are contractually forbidden from calling.
- **Every control we need lives outside the crate anyway.** Entry-count cap, name-length cap, actual-byte caps, ratio guard, compression-method allowlist, refusal of encrypted entries and ZIP64, duplicate-name handling, cancellation inside the inflate loop — all of that is ours regardless. The dependency would buy only format decoding, while adding a surface we never use: AES and ZipCrypto decryption, bzip2 and zstd back-ends (some C-backed by default), deflate64, symlink and permission emulation. Under the NFR-027 SBOM and licence gate (`86ajpew0j`) all of it becomes ours to carry and re-audit on every bump.
- **We never extract to disk and never use an archive name as a path.** XML parts are fetched by exact normalised name; image bytes are staged under a name the shell generates (§8.4). Zip-slip is structurally absent rather than defended against, which is precisely B1's "structural kill".
- `flate2` defaults to the pure-Rust `miniz_oxide` back-end, is already in the build, already audited, and its `Decompress` API gives incremental output with `total_out()` — which is what B3 needs.

**Honest costs, and the escape hatch.** We own our format bugs: a malformed-but-common archive we mis-read is our defect, not upstream's. Mitigation is threefold — Sana's §8 negative battery, a fuzz target, and putting the reader behind a narrow internal trait:

```rust
pub(crate) trait Archive {
    fn entries(&self) -> &[EntryMeta];
    /// Streams the entry through the inflater, enforcing the actual-byte caps.
    fn read_entry(&mut self, idx: usize, max_out: usize, cancel: &dyn Fn() -> bool)
        -> Result<Vec<u8>, ZipError>;
}
```

so swapping in the `zip` crate later is a single-module change with the tests unchanged. If field failures accumulate, take the dependency; do not patch a hand-rolled reader indefinitely.

**Why a `ByteSource` rather than a `&[u8]`.** Sana C1 admits pptx files up to 512 MiB. Holding that in memory would blow the working-set budget on its own. The reader therefore does bounded random-access reads: the EOCD scan reads the tail, the central directory is walked in chunks, and each entry is streamed. Peak from the archive itself is a read buffer, not the file. This is the single largest change from v1.0 of this document.

### 7.2 Decompression caps: count what actually comes out

**The load-bearing control is the actual-byte cap, enforced inside the streaming inflate loop.** Sana B3 is explicit that declared sizes in ZIP headers can lie in both directions, so they may never inform an allocation or an admission decision.

```
loop {
    inflate one chunk (<= 64 KiB output)
    produced += chunk_len
    if produced > per_entry_cap        -> ZipError::EntryTooLarge      (drop entry, report)
    if total   > total_cap             -> ZipError::ArchiveTooLarge    (abort import)
    if produced >= 1 MiB && produced / consumed > 100 -> ZipError::RatioExceeded
    if cancel() -> ZipError::Cancelled
}
```

The declared uncompressed size and declared ratio are used only as a **cheap early abort before the first chunk** — an economy, never a guarantee. Both checks exist; only the second is trusted. A test asserts the lying-header case: an entry declaring 1 KiB that actually inflates to 500 MiB must be stopped by the streaming cap.

Output is never pre-allocated from a declared size. The output `Vec` grows within the cap or, better, is a fixed-capacity buffer sized to the cap the caller passed.

### 7.3 Admission and structural rules (Sana C1, C6, C7)

| Rule | Behaviour |
|---|---|
| File > 512 MiB | Refuse the import with an honest error |
| ZIP64 EOCD locator present | Refuse — no real deck needs >4 GiB structures, and it keeps the offset-parsing surface to one path |
| Encrypted entry (GP flag bit 0) | Refuse the entry; if it is a part we need, that part is dropped and reported |
| Compression method not 0 (stored) or 8 (deflate) | Drop the entry and report |
| Entry count > 4 096 | Refuse the import |
| Entry name > 512 bytes, or containing a NUL | Drop the entry and report |
| Duplicate entry names | First occurrence wins; the rest are dropped and reported, so "parse one copy, extract the other" confusion is impossible |
| Entry types, mode bits, external attributes, link targets | **Never read.** Only regular-file entry *contents* are streamed. Nothing in the reader can distinguish or act on a symlink entry, which is the point |
| Nested containers — nested zip, OLE, `vbaProject.bin`, embedded packages, `.pptm` macro parts | Never opened, never recursed into. Dropped and reported (C7). Kills zip quines and keeps macro/OLE bytes inert |
| Embedded fonts (`ppt/fonts/*.fntdata`) | Never extracted, never parsed (Sana T2.16). Dropped and reported |

### 7.4 Dependency decision — XML: take `quick-xml`, do not hand-roll

XML is the opposite kind of problem from ZIP. It is not narrow: namespaces, prefix rebinding, entities, CDATA, character references, attribute normalisation, encoding declarations. Hand-rolling a parser for adversarial XML is how you get billion-laughs and XXE, and the ways to be wrong are not visible from reading your own code. Take the dependency.

- **`quick-xml`** — MIT, pure Rust, actively maintained, very widely used. A **pull** parser (`Reader::read_event_into(&mut buf)` with a reused buffer), so memory is bounded by construction and no DOM is built. Satisfies Sana's stated properties: streaming, no untrusted-size DOM, DTD processing absent, no network in its graph.
- **`roxmltree`** — rejected. Excellent and safe, but builds a full DOM: the whole part resident plus an arena proportional to node count. That fights C4 for no benefit, since we read four part shapes in a single forward pass.
- **`xml-rs`** — rejected. Pull-based and pure Rust, but slower and less actively maintained, with no compensating advantage.
- **Hand-rolled** — rejected, for the reasons above.

Required configuration, each pinned by a test rather than trusted to a default (Sana B2 is explicit that this must be tested, not assumed):

| Requirement | Why |
|---|---|
| **Reject any XML part whose first 1 KiB contains `<!DOCTYPE`** — drop and report | B2's structural kill. OOXML never legitimately contains a DTD, so this is free, and failing closed on a marker is stronger than trusting a parser's entity configuration. Applied *before* the parser sees the bytes |
| Parser is additionally configured with no DTD or external-entity processing | Defence in depth behind the marker check |
| `check_end_names(true)` | mismatched close tags are an error, not a silent recovery |
| Match on **local names**, never prefixes | real files rebind `p:`/`a:`/`r:` freely; `local_name()` is the only robust key |
| The reader is **iterative with an explicit depth counter**, capped at 256 — never recursive descent | a pull parser will happily stream a million-deep document; recursive descent over it is a stack overflow, which is a console crash mid-service. This is the trap a "safe parser" does not save you from |
| A per-part **event budget** | a legal but pathological part must terminate |
| Per-part inflated cap of 16 MiB — tighter than B3's 64 MiB archive ceiling | no legitimate slide part approaches 16 MiB; the tighter inner bound costs nothing and shrinks the XML layer's exposure |

`quick-xml` is MIT; the workspace is `Proprietary`, and MIT is compatible. It is already in the desktop `Cargo.lock` transitively via `wayland-scanner`, so on Linux it is not a new build artifact; on macOS and Windows it is one new pure-Rust crate. Kenji records it in the SBOM and re-runs the NFR-027 licence and advisory gate (`86ajpew0j`).

### 7.5 Relationship resolution — the part everyone gets wrong (Sana C6)

Relationship targets in OOXML are **package-relative and legitimately contain `..`**. `ppt/slides/_rels/slide1.xml.rels` carries `Target="../media/image1.png"`, which resolves to `ppt/media/image1.png`. So a naive "reject any target containing `..`" breaks every real pptx, and a naive "join it to a directory" is zip-slip.

The rule that satisfies both:

> **`pkgpath.rs` performs string normalisation entirely within the package namespace, and the result must match an entry that is actually in the archive. It never touches, constructs, or resembles a filesystem path.**

Concretely: split the source part's directory and the target on `/`, resolve `.` and `..` segments against the directory stack, refuse to pop above the package root, reject a leading `/` (absolute-in-package) and any backslash, lowercase for comparison only, then **look the result up in the entry set**. A target that does not resolve to a present entry is dropped and reported. Because the output is only ever a lookup key, an attacker who wins the normalisation still only names an entry inside the archive.

Additionally per C6 and T2.13:

- `TargetMode="External"` targets are **never fetched** and are reported as `SkipKind::ExternalImage` — "external image skipped". Sana's point that this is a privacy defect in an offline-first app as much as a security one is the right framing.
- A visited set bounds relationship cycles.
- Shared media parts are **deduplicated by resolved part name before counting against the byte budget**, so one part referenced from 200 slides is extracted, decoded and staged once.

### 7.6 What we read

| Part | Read for |
|---|---|
| `ppt/presentation.xml` | `<p:sldIdLst>` slide order; `<p:sldSz cx cy>` slide size in EMU |
| `ppt/_rels/presentation.xml.rels` | resolve each `<p:sldId r:id>` to a slide part |
| `ppt/slides/slideN.xml` | `<p:cSld><p:spTree>` — shapes, pictures, groups |
| `ppt/slides/_rels/slideN.xml.rels` | `r:embed` → media part; the notesSlide relationship |
| `ppt/notesSlides/notesSlideN.xml` | the `<p:ph type="body"/>` shape's text ⇒ `AuthoredSlide::notes` |
| `ppt/media/*` | image bytes, fetched by resolved part name only |

Within `<p:spTree>`, walked **iteratively with an explicit stack**:

- `<p:sp>` with `<p:txBody>` — paragraphs `<a:p>`, runs `<a:r><a:t>`, breaks `<a:br/>`, fields `<a:fld><a:t>`. Title if `<p:nvSpPr><p:nvPr><p:ph type="title"|"ctrTitle"/>`; everything else, including shapes with no placeholder, is body text. **Placeholder type decides title versus body — nothing else does.** A `<p:sp>` with no `<p:txBody>` is skipped silently; it is decoration, not lost content.
- `<p:grpSp>` — descend. Many real decks group their content; not descending silently loses text, which is the worst failure under a partial-import rule.
- `<p:pic>` — `<a:blip r:embed="rIdN">` plus `<p:spPr><a:xfrm><a:off x y/><a:ext cx cy/></a:xfrm>`. Missing `a:xfrm` (inherited from a layout placeholder) ⇒ a centred default rect and `Notice::PictureGeometryAssumed`.
- `<p:graphicFrame>` — inspect `<a:graphicData uri>`: `.../table` ⇒ `Table`, `.../chart` ⇒ `Chart`, `.../diagram` ⇒ `SmartArt`, `.../ole` ⇒ `OleObject`, otherwise `UnsupportedGraphic`.
- `<p:cxnSp>`, ink, 3D models ⇒ `UnsupportedGraphic`.
- `<p:sld show="0">` ⇒ `SkipKind::HiddenSlide` (§17 P4).

EMU → per-mille conversion uses `<p:sldSz>`; 914 400 EMU per inch, default 16:9 is 12 192 000 × 6 858 000.

**Fallbacks, each producing a `Notice` rather than a failure:** if `presentation.xml` or its rels are missing or malformed, fall back to natural-numeric-sort of `ppt/slides/slide*.xml` and emit `Notice::SlideOrderInferred`. Importing 24 slides in the wrong order is worse than dropping a chart, so it must be visible. If `<p:sldSz>` is missing, assume 16:9 and emit `Notice::SlideSizeAssumed`.

**Not reported as skipped items, by design:** animations, transitions, masters, layouts, fonts, colours. Those are replaced by the SelahCue theme deliberately, and "24 transitions skipped" would bury the two dropped charts. The rule: **a skipped item is content the user would notice missing; a design attribute we deliberately do not map is not one.** The report instead carries one standing notice: *"Layout, fonts and colours were replaced by your SelahCue theme."*

---

## 8. Images: extraction, decode, staging, commit

### 8.1 Per-picture chain

1. Resolve `r:embed` through the slide rels (§7.5) to a part; stream it under the actual-byte caps.
2. **Signature allowlist by magic bytes**, never the extension. Today: PNG and — with §9 — JPEG. Everything else (GIF, BMP, TIFF, WMF, EMF, SVG, JPEG 2000, HEIC…) is dropped and reported, per Sana B5 which stays in force for every format except JPEG. **Never an OS or platform decoder; never rendered in the webview; never shell-opened.**
3. **Bounded decode probe** — `decode_image(bytes, &IMPORT_DECODE_LIMITS)`. Import supplies its **own, tighter** limits, not `Default`: `max_pixels` 16 M and `max_encoded_bytes` 16 MiB against the render path's 40 M and 64 MiB, because one import may process up to 200 images while the render path decodes one at a time. `max_width`/`max_height` stay at 8192 to match `MAX_DIMENSION`.
4. Any `DecodeError` becomes a report entry, never a failure. `DecodeError` has no `Display`, so `report.rs` owns the user-facing mapping:

   | `DecodeError` | Report entry |
   |---|---|
   | `Empty`, `Malformed` | `ImageUnreadable` — "the image data is damaged" |
   | `Unsupported` | `ImageFormatUnsupported` — names the sniffed format |
   | `UnsupportedColour` (§9) | `ImageColourUnsupported` — "CMYK images aren't supported" |
   | `UnsupportedVariant` (§9) | `ImageVariantUnsupported` — names it, e.g. "arithmetic-coded JPEG" |
   | `TooLarge` | `ImageTooLarge` — states the byte cap |
   | `Oversize` | `ImageTooLarge` — states the dimension or pixel cap |
   | `Missing` | unreachable on this path (it is for the file-path decode); treat as `ImageUnreadable` and log |

5. On success keep only `(width, height, byte_len, format)` and **drop the decoded pixels immediately** — up to 64 MiB each and not needed. The dimensions are a real gain: they populate the `media_asset` `width`/`height` columns that `deck_import_image` currently leaves `None`. Note these are the **post-orientation** dimensions (§9.5), which is what the per-mille rect and the media row both want.
6. `MediaSink::stage(bytes, &probe)` ⇒ `MediaSlot`. **The original encoded bytes are staged, not the decoded pixels** — the store holds the file the user's deck contained.

### 8.2 What is stored

The original encoded bytes, under a shell-generated name, inside a staging directory. Never the archive's name, never the decoded buffer.

### 8.3 The media store — a new component

There is no media store (§3). One is introduced at `<app_data_dir>/media/`, alongside the SQLite database the operator already opens there (`operator/src/main.rs:898`).

**Filenames are generated by the store, never derived from archive content** (Sana B1). The scheme needs no new dependency and no schema:

> Try `<app_data>/media/import-<n>.<ext>` with `OpenOptions::new().write(true).create_new(true)`, starting `n` at the current media-library length. `create_new` fails atomically if the name is taken, so the first success is an unclaimed name. Bounded by `MAX_MEDIA_ASSETS` attempts. `<ext>` comes from the **sniffed** format, never from the archive.

A content hash would add cross-import dedup, but it needs a hash dependency, and `MediaId` cannot be the filename because it is minted by an in-memory library whose counter restarts at 1 each launch — ids would collide across sessions and silently overwrite a previous session's file. `create_new` sidesteps it. Cross-import dedup is a possible later refinement.

### 8.4 Staging and atomic commit (Sana B4)

Nothing is visible to the media library or the deck library until the whole parse has passed bounds.

```
 stage    <app_data>/media/.staging/<import-id>/0000.png, 0001.jpg, …   MediaSlot(n) = index
          │
 commit   for each slot, in order:
          │   rename staging file -> <app_data>/media/import-<n>.<ext>   (create_new-reserved)
          │   MediaLibrary::import(final_path, Image, size, w, h, None, now)  -> MediaId
          │   record slot -> MediaRef(final_path)
          ▼
 build    build_deck(doc, theme, &|slot| committed.get(slot))    -> SlideDeck + ImportReport
          │
 adopt    DeckLibrary::adopt_with_policy(deck, policy)           -> visible to the user
          │
 persist  media_repo::save_all(...)                              (prerequisite, §18)
```

- Failure, cancel or timeout at any point before commit: remove the staging directory. Library, media store and live state are byte-identical to before (B4).
- Failure during commit: already-committed media remains and appears in the media panel as **unused** — an honest, visible, user-removable state that already exists (`present::media_usage`, `PRESENTATION-MEDIA-STATES-spec.md` §158, §202). This is deliberately preferred to the alternative, which is a deck referencing media that is not there.
- **Crash cleanup:** on launch the operator removes any `<app_data>/media/.staging/*` directory. Sana B4 requires this explicitly and it is easy to forget.
- Commit ordering is media-then-deck so a deck is never adopted referencing an uncommitted path.

### 8.5 Lifecycle

- Files under `<app_data>/media/` are app-owned. Files referenced at a user's own path (the `deck_import_image` route) are not.
- Deleting a deck does **not** delete media. Another deck may reference the same asset and there is no reference count. This matches the "degrade, never destroy" principle Bianca documents (`DOMAIN-library-organisation.md` §4.1).
- Unused media is already first-class; orphan cleanup is a user action in a surface that already exists, not a background job.
- **A distinction `remove_media` does not currently make and must:** deleting a `MediaAsset` whose path is inside the app media root should delete the file; deleting one that points at a user's own path must **not** touch that file. Deleting a user's photo out of their Pictures folder because they removed it from the media panel would be a serious defect.
- No automatic garbage collection. Explicit non-goal.

### 8.6 Where two house rules collide, and how it resolves

`MAX_MEDIA_ASSETS` is 1000 and `MediaLibrary::import` returns `None` at the cap. The house rule is "refuse at the cap, never truncate"; the owner's rule is "never refuse a whole import over one unsupported element". Both are satisfied by scoping the refusal to the item: the **image** is refused and becomes `SkipKind::LibraryFull`; the **import** proceeds. The report says *"the media library is full — 5 images were not imported."* Recorded here because a reviewer will otherwise read one rule as violated.

---

## 9. JPEG still-image decode (new — `selahcue-engine::media`)

The owner chose to add JPEG decode as part of this work so that "text + images" is true on real decks. This section is the design; `ADR-0025` records the decision. It supersedes Sana's B5 **for JPEG only** — every other format she excludes stays excluded, and every bound she requires is preserved or tightened.

This work lands in `selahcue-engine`, not in `selahcue-import`, because the decode seam is a render-crate concern that the canvas image element and `deck_import_image` benefit from equally. `selahcue-engine` is a workspace member, already owns `DecodeLimits`, `DecodedImage` and `DecodeError`, and already depends on `png` from the same maintainers.

### 9.1 Making the seam format-agnostic

`media.rs` already has the right shape — a signature allowlist and `DecodeError::Unsupported` as an explicit later-format seam. The change generalises it rather than bolting JPEG on beside it:

```rust
pub enum ImageFormat { Png, Jpeg }
pub fn sniff(bytes: &[u8]) -> Option<ImageFormat>;      // magic bytes only, never an extension
pub fn decode_image(bytes: &[u8], limits: &DecodeLimits) -> Result<DecodedImage, DecodeError>;
```

`decode_png` is retained as a thin wrapper so existing callers do not churn.

**The bounded discipline is enforced once, in `decode_image`, in a fixed order that every present and future format follows.** This is the crux of the coordinator's first question: JPEG must not bypass the pre-allocation cap by learning its dimensions later.

| # | Step | Notes |
|---|---|---|
| 1 | non-empty | `Empty` |
| 2 | `bytes.len() <= limits.max_encoded_bytes` | `TooLarge` — before anything is parsed |
| 3 | `sniff()` against the allowlist | `Unsupported` — magic bytes only |
| 4 | **header-only read**, no pixel allocation | `png::Decoder::read_info()` / `jpeg_decoder::Decoder::read_info()` — both expose width, height and pixel format before `decode()` |
| 5 | reject unsupported variants from the header | `UnsupportedVariant` / `UnsupportedColour` (§9.4) — **before** allocation |
| 6 | `w <= max_width && h <= max_height` | `Oversize` |
| 7 | `w * h <= effective_max_pixels` | `Oversize`. `effective_max_pixels` is **halved** when a transposing EXIF orientation applies (§9.5), because that path needs a second buffer |
| 8 | decoder-native second-line budget | `png::Limits { bytes }` / `jpeg_decoder::Decoder::set_max_decoding_buffer_size()` — matters most for progressive JPEG, whose coefficient buffers scale with image size *during* decode |
| 9 | allocate and decode | first allocation happens here, and only here |
| 10 | normalise to RGBA8 | grayscale expands; PNG paths unchanged |
| 11 | apply EXIF orientation | JPEG only (§9.5) |

Steps 4–7 are the answer to "must not bypass the pre-allocation cap": `jpeg-decoder` exposes `read_info()` returning `ImageInfo { width, height, pixel_format }` before any pixel work, so the existing PNG discipline transfers exactly. Step 8 is the belt to step 7's braces, and is what bounds a progressive JPEG whose intermediate coefficient storage is larger than its output.

`DecodeError` gains two variants: `UnsupportedColour` and `UnsupportedVariant`. The enum is `Copy` and in-tree only, so adding variants is a compile-error-guided change; Kenji greps for exhaustive matches first.

### 9.2 Dependency choice — `jpeg-decoder`

**Decision: `jpeg-decoder` (image-rs), pinned to an exact version, `default-features = false` (no `rayon`).**

| Criterion | `jpeg-decoder` | `zune-jpeg` |
|---|---|---|
| Licence | MIT / Apache-2.0 | MIT / Apache-2.0 |
| Maintenance | image-rs org — **the same maintainers as `png`, which we already depend on** | newer project, smaller maintainer base |
| Unsafe | none on stable; SIMD is behind an opt-in nightly feature we do not enable | hand-written `unsafe` SIMD with runtime dispatch |
| Determinism | scalar on stable ⇒ one code path everywhere (§9.3) | runtime SIMD dispatch means the decode path differs by CPU |
| Speed | slower | faster |
| Progressive | supported | supported |

The decisive criteria are the two middle rows, not speed. We decode at import time, once, and cache; throughput is not our constraint. **Runtime SIMD dispatch is actively harmful here** because it means the same binary can produce different pixels on a machine with AVX2 than without — not merely across operating systems, but across CPUs on the same OS. That would break byte-identical golden tests in a way that reproduces only on some CI runners, which is the worst kind of flake.

Taking `jpeg-decoder` also means the still-image decode surface is maintained by one organisation (image-rs) with one release cadence and one advisory feed to track under NFR-027 (`86ajpew0j`) — a real operational saving over adding a second relationship.

`rayon` must be off: multithreaded decode adds threads and working set to a path we deliberately bound, for a speed gain we do not need.

**Verification requirement, not an assumption:** Kenji confirms at implementation time that the pinned version is scalar-only on stable, has no runtime dispatch, and that `read_info()` and `set_max_decoding_buffer_size()` exist with the semantics above. If any of that has changed, the determinism contract in §9.3 is what must be preserved — the crate choice serves the contract, not the other way round.

### 9.3 The determinism contract — what it becomes

This is the part the coordinator most wanted a read on, and the honest answer is that the *wording* of the existing claim has to change even though the *property we need* does not.

**Today's claim** (ADR-0018, `media.rs:4-6`): PNG is lossless and spec-defined, so decoded RGBA8 is byte-identical on every OS, so the deterministic CPU raster path and its golden tests hold.

**Why that argument does not transfer.** The JPEG specification defines the *bitstream*, not an exact inverse DCT. It permits IDCT implementations within an accuracy tolerance, and chroma upsampling is likewise a choice. Two conformant decoders will legitimately disagree by ±1 in places, and so will two versions of one decoder if its IDCT changes. So "any conformant decoder agrees" — the property PNG gives us for free — is simply not available for JPEG, and no crate choice can make it available.

**What we actually need, and what the contract becomes.** SelahCue does not need format-inherent agreement. It needs *our build* to produce the same pixels everywhere, so that golden tests and cross-OS parity mean something. Restated:

> **Determinism contract (revised).** For a **pinned decoder version**, decoding the same bytes yields byte-identical RGBA8 on every supported OS and CPU. For PNG this is guaranteed by the format. For JPEG it is a property of the pinned crate, not of the format.

Three consequences follow, and each is a concrete obligation:

1. **The JPEG decoder joins the pinned-and-gated set.** The repository already has this pattern and states it: wgpu is pinned and upgrades are gated on re-running the parity matrix (ARCHITECTURE §12). A `jpeg-decoder` version bump becomes a golden-test-affecting change that must re-run the image goldens. Record it beside the wgpu pin so it is not treated as a routine dependency bump.
2. **No runtime code-path selection.** Scalar-only, no SIMD dispatch, no `rayon`. This is why §9.2 chooses as it does.
3. **The contract is tested, not asserted.** A determinism test decodes a committed benign JPEG and asserts a pinned hash of the RGBA output, run across the existing CI matrix. If x86-64 and aarch64 ever disagree, the test fails on the day it starts being untrue rather than in a golden diff months later.

**Does this affect the GPU/CPU SSIM ≥ 0.99 parity oracle? No — for two reasons, in increasing order of durability.**

- Today the GPU compositor does not render `Layer::Image` at all. ADR-0018 records that it skips images exactly as it skips text; GPU-native images are a later batch. No image therefore enters the parity comparison, so the oracle cannot be affected today.
- More durably: when GPU-native image compositing does land, **both paths must consume the same decoded RGBA buffer, produced once upstream.** The decoder's choices are then common-mode and cancel exactly. The oracle compares rasterisers, not decoders. It would only be affected if the GPU path ever decoded independently — which it must not, and that is worth recording now as a constraint on the future GPU-image story rather than discovering it then.

**Do golden tests need regenerating? No — but there is a real regression surface, and it is not the goldens.** No existing golden contains a JPEG, because JPEG currently cannot decode. What changes is every test that asserts JPEG is *rejected*: a `DecodeError::Unsupported` assertion on JPEG bytes, or a missing-media-placeholder assertion for a `.jpg` `MediaRef`. Those flip from "rejected" to "decoded" and must be updated deliberately, not deleted when they turn red. Kenji greps for them before starting; that grep is the change's true blast radius.

Also user-visible: `deck_import_image` already offers a `jpg`/`jpeg` filter it cannot currently honour, so a JPEG picked there renders as a placeholder today and will render correctly afterwards. That is a bug fix, and it should be in the release note as one.

### 9.4 The JPEG variant matrix — decided up front

The coordinator is right that these silently produce wrong output if left undecided. Each is decided, and the decisions favour an honest skip over plausible-but-wrong pixels on an audience screen.

| Variant | Decision | Reasoning |
|---|---|---|
| Baseline sequential (SOF0), 8-bit, YCbCr | **Supported** | the common case |
| Extended sequential (SOF1), 8-bit | **Supported** | same coding, different marker |
| **Progressive (SOF2), 8-bit** | **Supported** | very common from "save for web" and web-sourced photos; skipping it would look arbitrary to a user who cannot see the difference. Bounded by step 8's decoding-buffer budget, which matters more here than for baseline |
| Grayscale (1 component) | **Supported** | expand to RGBA |
| **CMYK / YCCK (4 components, Adobe APP14)** | **Dropped and reported** | the highest-risk case. Correct conversion needs the embedded ICC profile; without one the result is plausible-but-wrong colour, and Adobe's inverted-value convention makes photo-negative output a live possibility. Common in print-oriented decks. **An honest "CMYK images aren't supported" beats a wrong-coloured photo on the congregation's screen** — this product's principles do not permit silently wrong output |
| **EXIF orientation (APP1, tag 0x0112, values 1–8)** | **Supported and applied at decode** | ignoring it imports photos sideways, which is common, obvious and embarrassing. §9.5 |
| ICC colour profiles | **Ignored**; pixels treated as sRGB | consistent with how the rest of the pipeline treats colour. Not reported — it is not a loss the user would recognise |
| 12-bit / 16-bit precision | **Dropped and reported** | rare in decks; avoids a second precision path |
| Arithmetic-coded (SOF9/10/11) | **Dropped and reported** | vanishingly rare; not supported by the crate |
| Lossless JPEG (SOF3) | **Dropped and reported** | a different codec wearing the same magic bytes |
| Truncated or corrupt | **Dropped and reported — never a partial image** | some decoders return what they got. A photo that is fine on top and grey on the bottom, on the audience screen, is worse than a placeholder. If the decoder errors, we skip |
| JPEG 2000, JPEG XL, HEIC | fail the signature allowlist | different formats |

Each "dropped and reported" case is detected at step 5 from the header, before allocation.

### 9.5 EXIF orientation

`jpeg-decoder` does not apply orientation; it exposes the raw APP1 payload and the caller decides. Applying it **inside the decoder** is the right place, so every consumer — import, canvas, `deck_import_image` — gets upright pixels with no schema change, no new `Element` field, and no per-callsite discipline to forget.

**A hand-rolled single-tag reader, not an EXIF crate.** This is the same hand-roll-versus-dependency judgement as ZIP, and it lands the same way for the same reason: we need one tag out of a large, untrusted, historically exploit-adjacent format. `kamadak-exif` would bring a whole TIFF/EXIF parser — every tag type, sub-IFDs, maker notes — as new untrusted-input surface to get ~80 lines of value. Bounds on the reader:

- Scan at most the first 64 KiB for an APP1 marker whose payload begins `Exif\0\0`.
- TIFF header must be `II*\0` or `MM\0*`; the IFD0 offset is bounded to the APP1 payload length.
- Walk **IFD0 only**; never follow sub-IFD or maker-note pointers. Entry count capped at 512.
- Tag `0x0112`, type SHORT, count 1, value in 1..=8. Anything absent, malformed or out of range ⇒ orientation 1, silently. A broken EXIF block is not a report entry; it is simply no rotation.
- All offsets checked; `slice::get`, never indexing. Same lint regime as `zip.rs`.

Transforms: 1 identity · 2 flip-H · 3 rot180 · 4 flip-V · 5 transpose · 6 rot90 CW · 7 transverse · 8 rot270 CW. **Values 5–8 swap width and height**, so:

- the probe reports **post-rotation** dimensions, which is what the per-mille rect and the `media_asset` row want; and
- `effective_max_pixels` is halved for those orientations (step 7), because the transpose needs a destination buffer alongside the source. 2, 3 and 4 are done in place.

The staged file keeps the **original** bytes, orientation tag included. Only the decoded pixels are rotated. Re-encoding would be lossy and pointless.

---

## 10. The import report

### 10.1 The type

```rust
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct ImportReport {
    pub source: ImportSource,
    pub slides_imported: usize,
    pub slides_in_source: Option<usize>,   // None for text sources, where it is meaningless
    pub images_imported: usize,
    pub notes_imported: usize,
    pub skipped: Vec<SkippedItem>,         // <= MAX_REPORT_ITEMS (100, Sana C12)
    pub skipped_overflow: usize,           // entries beyond the cap, counted not listed
    pub truncations: Vec<Truncation>,
    pub notices: Vec<Notice>,
}

pub struct SkippedItem { pub slide_index: Option<usize>, pub kind: SkipKind, pub detail: String }

pub enum SkipKind {
    Chart, Table, SmartArt, OleObject, UnsupportedGraphic, HiddenSlide, EmbeddedFont,
    NestedContainer, ExternalImage, DuplicatePart, DoctypeRejected,
    ImageFormatUnsupported, ImageColourUnsupported, ImageVariantUnsupported,
    ImageUnreadable, ImageTooLarge, LibraryFull, MediaCommitFailed,
    UnreadablePart, LimitReached(LimitKind),
}

pub struct Truncation { pub slide_index: usize, pub what: TruncatedField, pub kept: usize, pub dropped: usize }
pub enum TruncatedField { Title, BodyLine, BodyLines, Notes }

pub enum Notice {
    ThemeReplaced, SlideOrderInferred, SlideSizeAssumed, PictureGeometryAssumed,
    EncodingReplaced { count: usize },     // U+FFFD substitutions (Sana C2)
    ControlCharsStripped { count: usize }, // C10 hygiene, so stripping is never silent
}
```

Three categories, kept separate on purpose:

- **`skipped`** — content the user would notice missing. This is what "2 charts skipped" comes from.
- **`truncations`** — content that arrived but was cut to fit a cap. Silent truncation is the quietest way to be lossy and the easiest to miss in review, so it gets its own list and its own assertion.
- **`notices`** — facts that are not losses.

### 10.2 String hygiene (Sana C10) happens in the pure crate

Every string that leaves `selahcue-import` — slide text, notes, deck name, and **every report detail including archive entry names** — passes `hygiene::clean()`:

- strip C0 controls except `\n` and `\t`; strip C1; strip NUL
- strip bidi controls U+202A–U+202E and U+2066–U+2069 — these can visually reverse or splice text on the projector
- **preserve ZWJ and ZWNJ**, which are load-bearing for Arabic, Persian, Indic scripts and emoji. Sana's note that blanket-stripping them would be wrong is correct and easy to get wrong
- cap length; collapse to a single line for the deck name
- count what was stripped, into `Notice::ControlCharsStripped`, so the hygiene is not itself a silent loss

Sanitising at the producer means every consumer is safe by default — the report renderer, the logger and the DB all receive already-clean strings. Sana records that the report renderer is "the sink people forget"; doing it here is what makes forgetting harmless.

Homoglyph spoofing is not machine-detectable in general and is accepted residual (Sana RR3); the operator previewing before Go Live is the real control.

### 10.3 Staying honest when nothing was dropped

The report is **always returned**, never `Option<ImportReport>`. An `Option` invites `if let Some(report)` and a silent path where a loss is not shown.

```rust
impl ImportReport {
    pub fn is_lossless(&self) -> bool {
        self.skipped.is_empty() && self.skipped_overflow == 0 && self.truncations.is_empty()
    }
}
```

UI behaviour, whose visual design Uma owns:

- **Lossless** — a `role="status"` toast: *"Sunday Service imported — 24 slides."* No panel, no warning affordance. A clean import must feel clean.
- **Lossy** — the same toast plus one summary line and an expandable list: *"24 slides imported · 2 charts and 1 table were skipped."* Non-blocking; the user can open the deck immediately.
- **Never** a silent success when `is_lossless()` is false, and never a modal between the user and their deck.

### 10.4 Reaching the UI safely (Sana C11)

Tauri commands here return `Result<serde_json::Value, String>`, so the command returns `serde_json::to_value(report)`.

Report strings originate in an attacker-controlled file. In a Tauri app, webview injection is console compromise — full legitimate IPC control including live output. Two requirements:

- Strings are hygienised and length-capped in the pure crate (§10.2) before they leave it.
- The operator front-end inserts every imported string with `textContent`, never `innerHTML` or `insertAdjacentHTML` — **including the report renderer**. This belongs in the ticket's acceptance criteria and in `scripts/operator_headless.py`, not only in a code comment. Sana §8.6 specifies the assertion: a deck named `<img src=x onerror=alert(1)>` must render inertly as text in the library list *and* in the drop report, checked by computed-DOM assertions.

I also endorse Sana's R1 (a Content-Security-Policy in the operator `dist/` banning inline script). It is console-wide rather than import-scoped so it is not a gate on this feature, but it turns any future `innerHTML` slip from console compromise into a broken layout, and this feature is what makes that slip likely. Recorded as a follow-up I own (§18).

### 10.5 Where the report lives afterwards

MVP: session-scoped — the toast and its expandable panel, re-openable until dismissed — plus the full report written to the structured log via `tracing` (ADR-0011), so it reaches the diagnostics bundle. Logged entry names are escaped and truncated (C11).

It is **not** persisted. Persisting needs a schema decision, and Bianca's `RULE-LIB-MIG-03` rules out `deck_json`, because an older build would deserialise the deck without the field and silently write it back — a real data-loss path under forward-only migrations. A small `import_provenance` table (deck id, source name, source byte length, imported-at, report JSON) is the right shape and would also enable "you imported this file on 3 August" in the collision dialog (§11). Whether "what did I lose?" must be answerable a week later is a product question — P5.

---

## 11. Name collision

### 11.1 Why import makes this urgent rather than cosmetic

The `deck` table's primary key is the deck name, and `DeckLibrary::adopt` routes through `uniquify`, which silently returns `Name (2)`, `Name (3)`, … Import hits this on the second `Sunday Service.pptx` and every time after.

Silent suffixing is tolerable when a user types a name and can see what happened. Import is different: the user picked a *file*, the name is derived, nobody typed anything and nobody is watching that field. When you re-import a corrected file you almost always mean one of three things:

1. *I fixed the source — replace what I imported before.*
2. *Different service, same file name — keep both.*
3. *I already did this — cancel.*

Silent `(2)` always picks (2), invisibly. After a month the library holds `Sunday Service`, `Sunday Service (2)`, `Sunday Service (3)` with no way to tell which is current, and the operator opens the wrong one on a Sunday morning. That is an operational hazard, not an aesthetic complaint.

### 11.2 What is architectural, and is not negotiable

**A. Import must not silently rename.** The collision is surfaced before the deck is committed. Import already has a natural confirmation surface — the report — that "New Presentation" lacks, so this costs no new interaction pattern.

**B. Collision handling becomes a caller-supplied policy, not a library default.**

```rust
pub enum NameCollisionPolicy { KeepBoth, Replace, Fail }

impl DeckLibrary {
    pub fn adopt_with_policy(&mut self, deck: SlideDeck, policy: NameCollisionPolicy)
        -> Result<SlideDeck, AdoptError>;
}
```

`adopt()` keeps its current behaviour and delegates to `adopt_with_policy(deck, KeepBoth)`, so no existing caller changes and no regression is possible. Import always passes an explicit policy. This needs **no re-keying and no migration** — it is additive, which also satisfies Sana T2.20(b): imports route through the existing name-uniqueness path so a hostile name cannot clobber an existing deck.

**C. `Replace` must update the existing deck in place, preserving its `DeckId`.** This is the trap, and it is the highest-value paragraph in this section.

The obvious implementation is delete-then-insert, or an upsert on the name. Both are wrong. The `deck` table upserts `ON CONFLICT(name)`, so replacing by name overwrites the row belonging to a *different* `DeckId` while the in-memory library still holds the old id — and every `PlanItem` linking that old id (`ItemContent::Deck { deck_id }`) resolves to nothing or, worse, to an unrelated deck. Bianca records exactly this failure class: *"the failure is not 'missing' — it is silently the wrong presentation on the audience screen"* (`FINDING-LIB-07`).

So `Replace` is: find the existing deck by name, keep its `DeckId`, swap in the imported slides, `store()` it. Plan links survive because they never depended on the name. **This is why the collision behaviour cannot be a UI-only decision** — a front-end implementing "Replace" as delete-then-import breaks plan links in a way nobody notices until Sunday.

**D. `Replace` is refused while the target deck is live or staged.** Replacing the content of a deck currently on the audience output mid-service is exactly what the "staging never changes Live" invariant exists to prevent. Refuse with a clear message; do not queue it, do not apply it on the next transition.

**E. The default imported name is the source file's stem**, hygienised per §10.2, single line, ≤ 200 chars, with the existing `DeckLibrary` uniqueness path behind it. A path separator cannot appear because we take the stem. Empty or whitespace-only ⇒ `"Imported presentation"` (Sana C10; more informative than the existing `"Untitled presentation"` fallback and does not conflict with it). Clipboard ⇒ `"Pasted presentation — <date>"`.

### 11.3 What is a product call — routed to Priya

Which of Keep both / Replace / Cancel is the default and its copy; whether `Replace` ships in MVP at all given that it is destructive and wants a plan-impact warning nothing implements; whether re-import should be detected by source identity rather than name; and Bianca's pre-existing P4/P5. **Import makes P5 urgent** — silent `(n)` stops being a preference the moment a file import can silently fork a deck. Collected as P6–P9 in §17.

---

## 12. Bounded limits

All in `selahcue-import::limits` as `pub const MAX_*` with a doc comment naming the invariant, plus `within_bounds()` predicates — the house style. Values reconciled with Sana's constraint set; **where we differed, hers are adopted**, so the owner sees one number.

| Constant | Value | Source | Enforced in | Behaviour at the cap |
|---|---|---|---|---|
| `MAX_PPTX_FILE_BYTES` | 512 MiB | Sana C1 | shell, before open | refuse the import |
| `MAX_TXT_FILE_BYTES` | 16 MiB | Sana C2 | shell, **during** read | refuse |
| `MAX_CLIPBOARD_BYTES` | 2 MiB | Sana C3 | Tauri command entry | truncate and report |
| `MAX_ZIP_ENTRIES` | 4 096 | Sana C1 | `zip.rs` | refuse the import |
| `MAX_ZIP_NAME_LEN` | 512 bytes | this design | `zip.rs` | drop the entry, report |
| `MAX_ENTRY_INFLATED_BYTES` | 64 MiB | Sana B3 | `zip.rs`, **actual bytes** | drop the entry, report |
| `MAX_TOTAL_INFLATED_BYTES` | 256 MiB | Sana B3 | `zip.rs`, running total | abort the import (typed error) |
| `MAX_COMPRESSION_RATIO` | 100:1 after ≥1 MiB out | Sana C5 | `zip.rs` | drop the entry, report |
| `MAX_XML_PART_BYTES` | 16 MiB | this design (tighter inner bound) | `zip.rs` read call | drop the part, report |
| `MAX_XML_DEPTH` | 256 | Sana C4 | `ooxml.rs` counter | drop the part, report |
| `MAX_XML_EVENTS_PER_PART` | 1 000 000 | this design | `ooxml.rs` budget | drop the part, report |
| `MAX_IMPORT_SLIDES` | 500 (= `MAX_DECK_SLIDES`) | Sana C8 | `text.rs`, `pptx.rs` | stop reading further slide parts; `LimitReached(Slides)` |
| `MAX_SLIDE_LINES` | 64 | this design | `text.rs`, `pptx.rs` | truncate; `Truncation::BodyLines` |
| `MAX_LINE_LEN` | 2 000 chars (= `MAX_TEXT_ELEMENT_LEN`) | Sana C8 | `text.rs`, `ooxml.rs` | truncate; reported |
| `MAX_TITLE_LEN` | 200 chars | this design | `text.rs`, `ooxml.rs` | truncate; reported |
| `MAX_NOTES_LEN` | 4 000 chars (**existing**) | Sana C8 | `ooxml.rs` | truncate; reported |
| `MAX_ELEMENTS` | 64 (**existing**) | Sana C8 | `build.rs` | stop adding; `LimitReached(Elements)` |
| `MAX_PICTURES_PER_SLIDE` | 16 | this design | `pptx.rs` | `LimitReached(Pictures)` |
| `MAX_IMPORT_IMAGES` | 200 | Sana C8 | `pptx.rs` | `LimitReached(Images)` |
| `MAX_IMAGE_ENCODED_BYTES` | 16 MiB | this design | `IMPORT_DECODE_LIMITS` | `ImageTooLarge` |
| `MAX_IMAGE_PIXELS` | 16 M (halved for transposing EXIF) | this design | `IMPORT_DECODE_LIMITS` | `ImageTooLarge` |
| `MAX_DECK_NAME_LEN` | 200 chars, single line | Sana C10 | `hygiene.rs` | truncate |
| `MAX_REPORT_ITEMS` | 100 | Sana C12 | `report.rs` | stop listing; `skipped_overflow` |
| `MAX_REPORT_DETAIL_LEN` | 200 chars | this design | `report.rs` | truncate |
| `IMPORT_TIMEOUT` | 30 s | Sana C13 | shell | abort, typed error, zero mutation |

Two properties matter as much as the numbers.

**Enforced at the earliest point that knows the value, and on what is real.** The inflate caps count produced bytes, not declared ones (§7.2). The dimension check runs before allocation (§9.1 step 7). A cap enforced after the allocation it was meant to prevent is decoration.

**Re-checked on the way in.** The precedent is explicit: an unbounded ingress was rated a MEDIUM defect even for local SQLite reads (`CODE-REVIEW-batch-element-model.md:18`). `build.rs` therefore asserts `SlideDeck::within_bounds()` before returning, so a limits bug in a parser cannot produce an out-of-bounds deck that later reaches persistence.

### 12.1 Peak memory — how the caps compose

Sana §6.6 requires the caps to compose to a documented, asserted working set of ≤ ~350 MiB. With the `ByteSource` change (§7.1) and one-at-a-time streaming:

```
  archive file                  ~0        read through ByteSource in 64 KiB chunks
+ one inflated XML part         16 MiB    MAX_XML_PART_BYTES
+ one encoded image             16 MiB    MAX_IMAGE_ENCODED_BYTES
+ one decoded image             64 MiB    16 Mpx x 4 bytes RGBA
+ EXIF transpose buffer         64 MiB    only orientations 5-8, and max_pixels is halved there
+ accumulated ImportedDocument  ~10 MiB   500 slides x (2 KB text + 4 KB notes)
  ─────────────────────────────────────
  ~170 MiB peak, one import at a time (C13)
```

Comfortably inside Sana's budget. Two design choices are load-bearing here and neither is an optimisation:

- **`ByteSource` removes the whole-file term.** Without it, C1's 512 MiB admission cap would put 512 MiB in the working set before any parsing began.
- **Streaming images one at a time removes the arena term.** Holding every extracted image before staging any would be 200 × 16 MiB. The `MediaSink` callback exists precisely so no arena is ever built.

Vera should confirm the measured transient against NFR-003's method; `MAX_IMAGE_PIXELS` is the first lever if it is a problem.

---

## 13. Clipboard, and the shared text path

### 13.1 Mechanism

**Recommendation: do not read the clipboard from Rust. Read it in the WebView and pass the string to a Tauri command.**

The operator is Tauri v2 with `tauri-plugin-dialog` and no clipboard plugin. Reading host-side would mean a new plugin, a capability entry, and on macOS a programmatic-clipboard-read prompt. The WebView route needs none of it, and it makes Sana's C3 easy to satisfy exactly:

- A focused textarea in the import dialog accepts a normal paste, or `navigator.clipboard.readText()` behind the user's click.
- On a paste event, take **`clipboardData.getData("text/plain")` explicitly** — never `text/html`, never `text/rtf`, and never the browser's default insertion into a `contenteditable`. Sana T3.1 is the reason: the clipboard is multi-flavoured and attacker-influenceable by any page the volunteer copies lyrics from; an HTML flavour that ever reaches `innerHTML` is direct console compromise, and RTF is an exploit-rich parser we simply never open.
- The user sees what they are about to import before committing, which is the same preview-then-confirm shape the report already wants.

```rust
#[tauri::command]
async fn deck_import_text(text: String, name: Option<String>) -> Result<serde_json::Value, String>
```

`MAX_CLIPBOARD_BYTES` is enforced on arrival, because a WebView can send an arbitrarily large string.

### 13.2 Yes — clipboard and `.txt` share the path entirely

Both call `text::parse(&str, &TextOptions) -> ImportedDocument`. The only deltas are the `ImportSource` label and the default deck name. There is no second splitter and no source-specific branch inside the splitter.

Three things belong in that shared path that are easy to leave out:

**Encoding — the `.txt`-only step.** Clipboard text is already a `String`; a file is bytes. `decode.rs`:

1. Strip a UTF-8 BOM.
2. Valid UTF-8 ⇒ use it.
3. UTF-16 LE/BE BOM ⇒ transcode. Notepad still produces UTF-16, so this is not exotic.
4. Otherwise decode as UTF-8 lossy **and record `Notice::EncodingReplaced { count }`**. Sana C2 requires the substitutions be counted and reported — Windows-1252 lyric files are common in churches, so this path is the normal case, not the edge case. Replacing bytes with U+FFFD silently would violate the partial-import rule at the encoding layer, which is exactly where people forget to apply it.
5. Strip NULs (C2) before the string reaches SQLite or the UI.

**Line endings.** Normalise CRLF and lone CR to LF **once**, before splitting. Without it a CRLF file still splits correctly on blank lines, but every line keeps a trailing `\r` that becomes a rendered glyph on the audience screen. This repository already has a CRLF trap on record.

**What "blank line" means** — each with a plausible wrong answer, so each is pinned by test:

- A line is blank if it is empty **after trimming whitespace** — a line of spaces separates slides, because that is what the user meant.
- **N consecutive blank lines are one separator**, not N−1 empty slides.
- Leading and trailing blank runs are discarded; a trailing newline does not produce an empty final slide.
- An empty slide is never produced. Entirely blank input yields zero slides ⇒ `ImportError::NothingToImport`, the one text case that is genuinely an error rather than a report.

### 13.3 Title or no title — flagged, not invented

The owner's decision says *"consecutive non-blank lines are that slide's lines"* and is silent on whether the first line is the title. The parser carries it as a parameter so either answer is a one-line call:

```rust
pub struct TextOptions { pub layout: TextLayout }
pub enum TextLayout { FirstLineIsTitle, AllBody }
```

**Recommendation: `FirstLineIsTitle` as the default** — every comparable tool works that way, the existing `Slide { title, body }` is shaped that way, and a title-less slide renders worse under a theme that reserves a title region. Routed as P3 rather than decided here.

---

## 14. Testing strategy

Sana's §8 is the merge-gate battery. This section states the architecture-side additions and the mechanics, without restating her cases.

### 14.1 Hostile fixtures are synthesised in-test, never committed

`tests/support/pptx_builder.rs` assembles a minimal valid package — `[Content_Types].xml`, `_rels/.rels`, `ppt/presentation.xml`, per-slide XML and rels, media parts — with an injection point for every hostile mutation. Stored (method 0) entries need no compression, so the builder is ~60 lines; a deflate helper is added only for the bomb cases.

Better than committed binaries in four ways: a reviewer reads the hostile shape in the diff instead of trusting a filename; a malicious fixture never exists as a file for a scanner to flag or a person to double-click; fixtures cannot silently rot; and a 4 GiB-declared bomb costs a few kilobytes of test source.

**Two benign binary fixtures are committed, and only two:** one small real-PowerPoint `.pptx` (three slides, one PNG, one table, speaker notes) and one small real-camera JPEG carrying an EXIF orientation tag. Generated fixtures share the author's misconceptions; these catch "our synthetic XML is not what PowerPoint actually emits" and "our EXIF reader works on our own EXIF". Each ships with a note recording how it was produced.

### 14.2 Architecture-side assertions beyond Sana's battery

| Area | Assertion |
|---|---|
| **Actual-byte caps** | The lying-header case is the *primary* bomb test: an entry declaring 1 KiB that inflates to 500 MiB must be stopped by the streaming counter. The declared-ratio early abort gets its own, secondary test asserting zero bytes were inflated |
| **Stack safety** | The 10 000-deep nesting case runs inside `std::thread::Builder::new().stack_size(128 * 1024)`, so a recursion regression fails instead of passing on a large main stack |
| **`ByteSource` bounds** | A source that returns short reads, lies about `len()`, or errors mid-entry must produce a typed error, never a panic |
| **Package-path normalisation** | `pkgpath` gets its own table-driven test: legitimate `../media/x.png` resolves; `/abs`, `..` above root, backslashes, and doubled separators are refused; the output is only ever matched against the entry set |
| **No network, structurally** | Sana B2's CI check: `cargo tree -p selahcue-import -e normal` must not contain `reqwest`, `hyper`, `ureq`, `curl`, `rustls`, `native-tls`, `tokio` (net features). This is a `make ci` line, and it is only expressible because the importer is its own crate |
| **No filesystem, structurally** | A grep asserting `selahcue-import/src/**` contains no `std::fs` and no `std::net`. This makes XXE file disclosure impossible rather than merely defended |
| **Determinism** | Importing the same bytes twice yields byte-identical `deck_json` apart from `DeckId` — no `HashMap` iteration order in output ordering, no timestamps in the deck. Plus §9.3's pinned-hash JPEG decode test on the CI matrix |
| **Bounded memory** | `tests/test_memory.rs` installs a counting `#[global_allocator]` in that test binary, imports a synthesised worst case, and asserts peak live allocation against §12.1's ceiling, plus every cap and `SlideDeck::within_bounds()`. A per-binary global allocator works precisely because tests are one file per module |
| **Panic containment** | `tests/test_panic_battery.rs` wraps every call in `catch_unwind` over Sana's malformed battery including her fixed-seed 10k random-input mini-fuzz; any panic fails the test. Every input must yield `Ok(report)` or a typed error |
| **Text splitter** | Golden cases pinning §13.2, plus a proptest that arbitrary input respects every clamp and round-trips visible text |

### 14.3 Fuzzing

`cargo-fuzz` targets `fuzz_text` and `fuzz_pptx`, seeded from the builder's minimal valid package. Invariant: **never panic, always terminate, never allocate beyond the caps.** Not in `make ci` — the deterministic battery is the merge gate; the fuzzer is depth, run time-boxed in a scheduled job, per Sana R2 and FR-173's "deep fuzzing → Stage-13".

### 14.4 CI placement

Because `selahcue-import` is a workspace member, `cargo test --workspace` covers all of the above and `make ci` gains only the two structural greps in §14.2 — which is the entire point of the placement decision in §4.3. The crate inherits `clippy::unwrap_used` and adds the lints in §4.2. The `textContent` requirement gets its assertion in `scripts/operator_headless.py`, along with Sana §8.6's console-responsiveness check.

---

## 15. Failure modes, concurrency, observability

| Concern | Design |
|---|---|
| **Placement** (Sana B4/§6.1) | The pipeline runs off the webview and UI threads and off any thread servicing live-console IPC — `tauri::async_runtime::spawn_blocking`. Tauri command handlers never block on import. Note `deck_import_image` already blocks on `blocking_pick_file` inside an `async` command; do not copy that shape |
| **One at a time** | Imports are serialised behind a lock. A second import is refused with an honest "an import is already running", not queued |
| **Cancellation and timeout** | The operator can cancel; a 30 s wall-clock timeout aborts a wedged import with a typed error. `cancel` is polled between slides, between pictures, and inside the inflate loop at chunk granularity — no uninterruptible loop. **This is also what bounds the absent decode timeout** (§3): a pathological image within every size budget but slow to decode is caught by the import-level clock. It does not fix the underlying gap for the render path, which stays flagged for Sana |
| **Atomic commit** | §8.4. Failure, cancel or timeout leaves library, media store and live state byte-identical; staging is removed, including a next-launch sweep after a crash |
| **Panic containment** | A `catch_unwind` belt at the import boundary in the **shell** converts any residual panic into a failed import (Sana C9). **Kenji must verify the operator's release profile does not set `panic = "abort"`,** or the belt is inert — a five-second check that silently invalidates a merge gate if skipped |
| **The output process is untouchable** | No import path calls into the output process, presenter state, autosave checkpointing, or the LAN server. Import touches exactly: importer memory → staging → `DeckLibrary` + `media_repo` |
| **Import never touches live output** | Import creates or replaces a library deck. It never stages, never goes live, and never alters the currently live deck — `Replace` is refused while the target is live or staged (§11.2 D) |
| **Progress** | One Tauri event per 10 slides, not per slide, so the dialog can show progress without flooding IPC |
| **Persistence is best-effort** | `DeckLibrary` runs in memory when the database will not open and already surfaces "changes won't be saved". An import in that state is equally unsaved, and the import dialog must say so **before** the user picks a file — after a 200-slide import is too late |
| **Partial media, whole deck** | A staging or commit failure for one image becomes a report entry and the import continues. Disk-full mid-import degrades to a text-only deck plus an honest report, not a failure |
| **Logging** | One `tracing` span per import: source kind, byte length, slide count, skip counts by kind. **Never** log document text, file paths beyond the stem, or raw archive part names; entry names are escaped and truncated (C11). ADR-0011 and FR-082 redaction applies — imported content is user content |
| **Nothing crosses the wire** | No LAN protocol change. The host stays deck-blind (`protocol.rs:172`); import is operator-local, like the rest of the deck library. The byte-pinned cross-language wire fixtures are untouched |
| **Schema** | The text half needs none. The image half needs `media_repo` wired — a *caller*, not a migration; `media_asset` already exists at v17 |

**Security assumptions, for Sana to confirm at the post-build review:**

1. The file path comes from the OS file dialog — user-chosen, not peer-supplied. Import does not accept a path over the LAN and must not start.
2. Archive content is fully untrusted, is never used as a filesystem path, never executed, never resolved as a URI.
3. The pure crate performs no I/O of any kind (asserted structurally, §14.2), so file-read and network primitives are unreachable from the parsers.
4. Media written by import lands under an app-owned root with a shell-generated name. FR-138 canonicalisation is still needed for the *user-chosen source path* and for the pre-existing arbitrary-path `MediaRef` read (`engine/src/media.rs:260`), neither of which this design fixes.
5. The decoder remains **in-process** (ADR-0018; ADR-0016's worker is not shipped). Import narrows the exposure with tighter limits and a wall clock, and widens it by adding JPEG — a second parser on the same in-process path. I endorse Sana's R3: this feature is the first routine path for internet-downloaded files to reach the decoder, so the ADR-0016 worker should be re-prioritised. Recorded in §18.

---

## 16. What this design does not cover

| Not covered | Owner |
|---|---|
| The attack enumeration — `docs/security/THREAT-MODEL-presentation-import.md` | Sana |
| Visual design and copy for the import dialog, report panel, and collision dialog | Uma |
| Wiring `media_repo` so the media library survives a restart | its own story; §18 |
| FR-138 itself — canonicalisation, symlink and confinement for user-chosen paths (`86ak0qmzv`) | separate story. This design satisfies the zip-slip half **by construction** and states what it still needs |
| The out-of-process sandboxed decoder (ADR-0016) | unchanged and still deferred; re-prioritisation recommended |
| A Content-Security-Policy for the operator webview (Sana R1) | console-wide; recommended, not gating |
| pptx layout, fonts, colours, animations, transitions, masters | excluded by owner decision |
| Embedded video and audio in a pptx | excluded — ADR-0020 defers video render entirely |
| GIF, BMP, TIFF, WMF, EMF, SVG, HEIC decode | dropped and reported; B5 stands for everything except JPEG |
| ICC colour management | out of scope; pixels are treated as sRGB |
| Tables as flattened text | P2 |
| `.odp`, Keynote, Google Slides, ProPresenter, PDF | out of scope |
| Deck **export**, including the `Export deck (.json)…` already drawn in `PRESENTATIONS-LIBRARY-spec.md` §5 | separate work |
| Plan-bundle import (FR-139, `86ak0qn15`) and its pre-existing cross-machine `DeckId` hazard (`FINDING-LIB-07`) | separate story |
| Folders and tags for the library | Priya's open scope decision |
| Automatic garbage collection of orphaned media | explicit non-goal |
| Performance targets beyond "must not block the UI thread" and §12.1's arithmetic | Vera |
| PRD amendment, epic and story creation, sequencing | Priya and Diego |

---

## 17. Product calls routed to Priya

| # | Question | Why it is Priya's | Blocks |
|---|---|---|---|
| ~~P1~~ | ~~Image scope given PNG-only decode~~ | **RESOLVED by the owner: add JPEG decode as part of this work.** §9 | — |
| **P2** | pptx tables: report as skipped, or flatten to text lines with a notice? | Flattening collapses columns and can change meaning; reporting loses the text entirely. Recommendation: report as skipped for MVP | `ooxml.rs`, report copy |
| **P3** | Text import: first line becomes the title, or everything is body? | Visible product behaviour. Recommendation: first line is the title; both are carried as a parameter | `text.rs` default, dialog copy |
| **P4** | Hidden pptx slides: skip and report, or import them? | Users hide slides deliberately. Recommendation: skip and report | `pptx.rs` |
| **P5** | Should "what was dropped" be answerable a week later — does import provenance persist? | Needs an `import_provenance` table; also unlocks "you imported this file on 3 August" in the collision dialog | schema follow-up, collision UX |
| **P6** | Collision default: Keep both, Replace, or Cancel — and the copy | The architectural constraints are fixed (§11.2); the choice is not | import dialog |
| **P7** | Is `Replace` offered in MVP at all? | Destructive, and wants a plan-impact warning nothing implements yet | import dialog, `adopt_with_policy` |
| **P8** | Detect re-import by source identity rather than name? | More useful than a name match; depends on P5 | P5 |
| **P9** | Bianca's P4 and P5 — name-uniqueness scope, and whether silent `(n)` renaming stops | Pre-existing, but **import makes P5 urgent** | library-wide |
| **P10** | Should presentation import get PRD requirements? There are none today | Every other feature maps to an FR. Also needs an epic and stories (Diego) | delivery structure |
| **P11** | CMYK JPEGs are dropped and reported (§9.4). Confirm that an honest skip is preferred to converting without an ICC profile | I have taken an architectural position — wrong colour on the audience screen is worse than a visible skip — but "how many of our users' decks contain CMYK photos" is a product judgement | report copy |
| **P12** | Risk acceptance for Sana's §9 residuals (RR1–RR6) | Explicitly the product owner's, not a technical role's | merge |

---

## 18. Dependencies and sequencing

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │ 1. selahcue-import crate: limits, hygiene, decode, text, report,     │  no dependencies
 │    build. .txt + clipboard import, end to end.                        │  ships standalone
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │
 ┌───────────────────────────────────▼──────────────────────────────────┐
 │ 2. source, zip, pkgpath, ooxml, pptx — pptx TEXT and NOTES only.      │  no new schema
 │    Pictures counted and reported as skipped.                          │  ships standalone
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │
        ┌────────────────────────────┴──────────────────────────┐
        │                                                        │
 ┌──────▼─────────────────────────┐        ┌────────────────────▼───────────────────┐
 │ 3a. Wire media_repo            │        │ 3b. JPEG decode in selahcue-engine     │
 │     media survives a restart   │        │     ADR-0025: seam, EXIF, determinism  │
 │     PREREQUISITE               │        │     independent of import; ships alone │
 └──────┬─────────────────────────┘        └────────────────────┬───────────────────┘
        └──────────────────────────┬────────────────────────────┘
                                   │
 ┌─────────────────────────────────▼────────────────────────────────────┐
 │ 4. Media store + staging/atomic commit + MediaSink + pptx IMAGES      │
 └───────────────────────────────────────────────────────────────────────┘
```

Steps 1 and 2 each ship a complete, honest, useful feature with no prerequisites. Step 3b is independently valuable and independently shippable — it fixes `deck_import_image`'s jpg filter, which currently offers a format it cannot render, and it unblocks the canvas image element for JPEG. Attempting step 4 before 3a produces images that vanish on restart.

**Follow-ups I own and recommend, none gating this feature:**

- Re-prioritise the ADR-0016 out-of-process decode worker (Sana R3). This feature makes internet-downloaded files a routine input to an in-process decoder, and now to two parsers rather than one.
- A Content-Security-Policy in the operator `dist/` banning inline script (Sana R1).
- FR-138 canonicalisation for the user-chosen source path and the pre-existing arbitrary-path `MediaRef` read.

**Related but not blocking:** FR-138 (`86ak0qmzv`). This design does not depend on it — no archive name ever becomes a path — and does not discharge it. Diego should record the relationship so nobody assumes import closed FR-138.

**Suggested delivery structure for Priya and Diego**, not created here: one epic ("Import a presentation") with stories for 1, 2, 3a, 3b and 4.

---

## 19. Notes for Kenji

Small things that will otherwise be discovered the hard way.

- **No `thiserror`, no `anyhow`.** The house pattern is a hand-rolled enum with `#[derive(Debug, Clone, PartialEq, Eq)]` plus manual `Display` and `std::error::Error` — `ParseError` at `core/src/scripture.rs:62-95` is the model.
- **`selahcue-present` has no error type at all** and signals failure with `Option`/`bool`. Do not add one there; `selahcue-import` owns its errors.
- **No `[workspace.dependencies]`.** Pin literal versions in `crates/selahcue-import/Cargo.toml`, as every other crate does.
- **Grep for JPEG-rejection assertions before touching `media.rs`** (§9.3). Tests asserting `DecodeError::Unsupported` on JPEG bytes, or a placeholder for a `.jpg` `MediaRef`, flip behaviour and must be updated deliberately, not deleted when red.
- **Verify the operator release profile does not set `panic = "abort"`** or the `catch_unwind` belt is inert (§15).
- **`decode_image` takes a byte slice and does no I/O**, so the pure crate can call it. Build your own `DecodeLimits`; do not use `Default` (§8.1 step 3).
- **`DecodeError` has no `Display`.** Map it in `report.rs`; do not `format!("{:?}")` it into user-facing text.
- **`Element` is `Clone` but not `Copy`** (`theme.rs:135-136`) — the `Image` variant holds a heap-backed `MediaRef`.
- **`MediaRef::CAP` is 1024 bytes** and `MAX_MEDIA_PATH_LEN` is 1024. The store path must fit; check before constructing.
- **`AuthoredSlide::within_bounds` counts notes in `chars`, not bytes** (`deck.rs:123-127`). Truncate by chars or you will fail the predicate on non-ASCII text.
- **Match OOXML on `local_name()`, never a prefix.** Real files rebind `p:`/`a:`/`r:` freely.
- **Walk `<p:grpSp>`.** Grouped shapes are common and their text is real content.
- **`..` in a relationship target is legitimate** (§7.5). Normalise within the package namespace and look the result up in the entry set; do not reject it and do not join it to a directory.
- **Verify the `\n` assumption in §5.1 before writing `build.rs`.** Ten minutes, one function.
- **`create_new(true)` is the media-store naming primitive** (§8.3) — it fails atomically on an existing name, which is what makes the counter safe without a hash or a persisted sequence.

---

## 20. Evidence appendix

| Claim | Label | Source |
|---|---|---|
| Decode is PNG-only, in-process, byte-slice API, caller-supplied limits, no timeout | Verified | `crates/selahcue-engine/src/media.rs:21-23, 32-207` |
| Dimension and pixel checks run before allocation | Verified | `crates/selahcue-engine/src/media.rs:164-172` |
| `DecodeError` variants, `Copy`, no `Display` | Verified | `crates/selahcue-engine/src/media.rs:62-76` |
| ADR-0016 sandbox is not shipped | Verified (absence) | repository sweep — three `sandbox` hits, all comments |
| No media store; nothing copies image bytes into an app directory | Verified (absence) | sweep of `fs::write` / `File::create` / `OpenOptions` |
| `media_repo` has no production caller | Verified (absence) | `media_repo` call sweep |
| `deck_import_image` offers jpg/jpeg but only PNG decodes; dimensions never probed | Verified | `crates/selahcue-operator/src/main.rs:1729-1756`; `deck_workspace.rs:696-708` |
| FR-138 unimplemented; `canonicalize` has zero hits | Verified (absence) | repository sweep; deferral at `engine/src/scene.rs:306-309` |
| `Element::Image` references media by `MediaRef` path | Verified | `crates/selahcue-present/src/theme.rs:183-204` |
| `Theme.title` / `Theme.body` are `RegionStyle` with per-mille geometry | Verified | `crates/selahcue-present/src/theme.rs:45-66, 386-418` |
| `MAX_ELEMENTS` 64, `MAX_TEXT_ELEMENT_LEN` 2000 chars, `MAX_DECK_SLIDES` 500, `MAX_NOTES_LEN` 4000 chars | Verified | `present/theme.rs:259,294`; `present/deck.rs:33,36` |
| `MAX_MEDIA_ASSETS` 1000; `import` returns `None` at the cap | Verified | `crates/selahcue-core/src/media.rs:19,161` |
| Deck PK is the name; `uniquify` silently suffixes; `adopt` routes through it | Verified | `deck_library.rs:220-231,462-474`; `deck_repo.rs:38-51` |
| Plan items link decks by id only | Verified | `crates/selahcue-core/src/plan.rs:86-89,425-442` |
| Cross-machine `DeckId` collision hazard is pre-existing | Verified | `docs/product/DOMAIN-library-organisation.md` `FINDING-LIB-07` |
| Load paths must re-check caps | Verified | `docs/delivery/CODE-REVIEW-batch-element-model.md:18` |
| No `zip` or `roxmltree` dependency; `quick-xml` only transitive via `wayland-scanner` | Verified (absence) | all three `Cargo.lock` files |
| `flate2 = "1"` and `png = "0.17"` are already direct first-party dependencies | Verified | `selahcue-scripture/Cargo.toml`; `selahcue-engine/Cargo.toml` |
| No `thiserror` or `anyhow` in any first-party crate | Verified (absence) | repository sweep |
| `selahcue-present` has no error enum | Verified (absence) | repository sweep |
| Operator is Tauri v2 with `tauri-plugin-dialog`, no clipboard plugin | Verified | `crates/selahcue-operator/Cargo.toml` |
| Live output runs in a separate process from the operator console | Verified | Sana §1; `selahcue-desktop` bin `selahcue-output` |
| The operator webview uses `textContent` for deck names but `innerHTML` for structural rebuilds | Verified | Sana §1, `dist/app.js` |
| No PRD requirement covers presentation import | Verified (absence) | `SelahCue-PRD.md` grep |
| No ClickUp task covers presentation import; FR-138 story is `86ak0qmzv` | Verified | ClickUp search, 2026-08-15 |
| The JPEG spec permits IDCT implementations within a tolerance, so conformant decoders need not agree bit-for-bit | Inferred | format knowledge; the design does not rely on cross-decoder agreement — see §9.3 |
| `jpeg-decoder` is scalar-only on stable, exposes `read_info()` before decode, and has a decoding-buffer limit | **ASSUMED** | Kenji verifies at the pinned version (§9.2). The determinism contract is what must be preserved if any of it has changed |
| `zune-jpeg` uses runtime-dispatched SIMD | **ASSUMED** | basis for preferring `jpeg-decoder`; Kenji confirms if reconsidering |
| `Element::Text` renders an embedded `\n` as a line break | **ASSUMED** | implied by `compose.rs` `MAX_WRAP_WORDS` and `deck.rs:148-183`; Kenji verifies |
| Cap values not taken from Sana are defensible, not measured | **ASSUMED** | each keeps a test; Vera confirms the memory peak |
| JPEG is the dominant embedded image format in real church pptx decks | **INFERRED** | general knowledge of PowerPoint output; not measured. Rowan can sample if P11 needs evidence |
| Whether real-world decks hit ZIP64 | **UNKNOWN** | refused with a clear reason; revisit on evidence |
