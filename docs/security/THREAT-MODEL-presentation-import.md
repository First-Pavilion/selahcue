# Threat Model — Presentation Import (.txt / .pptx / clipboard)

- Status: **Condition re-verification complete (v1.3)** — v1.2's merge conditions have been independently re-adjudicated against the remediated working tree (see §12): condition 2 (the F1 test fix) is **discharged**, the change set **merges**, condition 1 (the shell-slice review) **stands** as a pre-wiring gate. §§1–10 remain the pre-build constraint set; §11 the v1.2 post-build verdicts; §12 the v1.3 re-verification.
- Date: 2026-08-15 (pre-build) · 2026-08-16 (post-build verification, §11) · 2026-08-16 (condition re-verification, §12)
- Reviewer role: Security Reviewer (Sana)
- Goal Contract: `docs/delivery/goals/GOAL-sec-presentation-import-threat-model.md` (pre-build); `docs/delivery/goals/GOAL-sec-presentation-import-postbuild-review.md` (post-build, §11); `docs/delivery/goals/GOAL-sec-presentation-import-condition-reverify.md` (condition re-verification, §12)
- Relates: PRD FR-138 (safe import) / FR-173 (bomb defense) / FR-070 (placeholder, never blank) / NFR-024 (no component failure blanks live output); ADR-0016 (decode isolation end-state), ADR-0018 (bounded in-process PNG decode — the shipped interim); `docs/security/reviews/threat-model-draft.md` T11/T12/T20.
- Deployment model for severity: **single-operator, offline-first desktop app** operated by a church volunteer. Not a server; no tenants; the hostile input arrives by explicit operator action ("download a deck from the internet and import it") or via the clipboard. Severity below is calibrated to that — the dominant *product* harm is disrupting a live service or compromising the operator PC, not data-at-scale.

- Revision history:
  - **1.0 (2026-08-15):** initial pre-build model. The image seam admitted PNG only; JPEG was listed as dropped-and-reported.
  - **1.1 (2026-08-15):** owner decision — **JPEG decode is added to `selahcue-engine` as part of this work** (real .pptx files overwhelmingly embed JPEG; a "text + images" import dropping JPEG would have dropped nearly every image in a typical deck). Scoped revision only: B5 revised in place + new **B5-J JPEG admission profile** (§7); JPEG decoder **crate constraint** added to the dependency note (§7) — the one dependency choice this review gates; hostile-JPEG test battery added (§8.4); T2.15 annotated (§3.3); R6 likelihood updated (§5); RR1 revised to conditional, time-bounded acceptance and RR2 wording updated (§9); verdict note (§10). All other sections are unchanged from 1.0.
  - **1.2 (2026-08-16):** **post-build security review.** The importer is built (new `selahcue-import` crate; `selahcue-engine` `jpeg.rs`/`exif.rs`/`media.rs`; operator `media_store.rs` + `deck_library.rs` policy; `scripts/import_guards.sh`). Every blocker B1–B5, every B5-J clause and every control C1–C14 was re-adjudicated against code, not comments — new **§11** records the per-constraint verdicts, the four scepticism-target findings, the ranked findings, the restated RR1 position, and the release verdict (**merge with conditions**). §§1–10 are unchanged and stand as the pre-build constraint set.
  - **1.3 (2026-08-16):** **condition re-verification.** Remediation landed across all tiers (streamed central directory; `PptxBuilder::replacing()` with panic-on-no-match; new `tests/test_zip.rs`; F2 allowlist guard; F3 `ooxml.rs` lints; F4 always-on repair-and-report; `read_stored` compressed-size extent; `quick-xml` exact pin). New **§12** re-adjudicates each item against code and — new instrument — by **mutation runs in a scratchpad replica**, answers the gate-integrity question the coordinator raised (the renamed lying-header test alone would only *apparently* satisfy the condition; the battery genuinely discharges it), records why the v1.2 pass missed the central-directory allocation and which controls are measurement-only, closes F1–F4, adds **F6 (LOW)**, restates the DEFERRED shell constraints and the outstanding RR1 milestone, and issues the verdict: **condition 2 discharged, the change set merges; condition 1 stands**. §§1–11 are unchanged.

Evidence labels: **Verified** (inspected in this repo), **Inferred**, **Assumed**, **Unknown**.

---

## 1. Feature and trust boundary

Owner-approved scope (settled): import a presentation into the operator's deck library from
(1) a `.txt` file (blank line separates slides), (2) a `.pptx` file — per-slide text, speaker
notes, **and embedded images**, (3) clipboard text. **Partial import** is the model: import what
is representable, report what was dropped.

The importer is a new **untrusted-input boundary** in the operator process:

```
 attacker-supplied file / clipboard
        │  (operator explicitly chooses to import)
        ▼
 ┌──────────────────────── OPERATOR PROCESS (Tauri console) ───────────────────────┐
 │  IMPORTER (new)  ──►  SlideDeck (bounded, selahcue-present)  ──►  DeckLibrary   │
 │     │  extracted image bytes                                        │ deck_repo │
 │     └───────────►  media store (media_repo, path-referenced files)  ▼ SQLite    │
 └──────────────────────────────────────────────────────────────────────────────────┘
        separate PROCESS: selahcue-output (live output + LAN server) — never touched
```

Integration facts this model is grounded in (all **Verified**):

- Deck library is operator-local (`crates/selahcue-operator/src/deck_library.rs`); decks are
  persisted **by name** (the `deck` table PK) with a "(n)" suffix on collision; DB access is
  parameterized rusqlite throughout (`deck_repo`, `media_repo`).
- Deck/slide bounds already exist and are the natural import budget:
  `MAX_DECK_SLIDES = 500`, `MAX_NOTES_LEN = 4000` chars, `MAX_ELEMENTS = 64` per slide,
  `MAX_TEXT_ELEMENT_LEN = 2000` chars (`selahcue-present/src/{deck.rs,theme.rs}`).
- Still-image decode is ADR-0018's **bounded in-process** pure-Rust path
  (`selahcue-engine/src/media.rs`): PNG-only signature allowlist, 64 MiB encoded cap,
  40 MP / dimension caps enforced **before allocation**, `Result`-based and panic-contained,
  failure contains to the missing-media placeholder. **The ADR-0016 out-of-process sandbox is
  the deferred end-state and is NOT shipped.** Any claim that extracted images hit a "sandboxed"
  decoder today would be wrong; what exists is a bounded, memory-safe, panic-contained decoder.
  *[Rev 1.1: by owner decision, JPEG decode joins this same seam as part of the import work —
  admission profile and crate constraint in §7 (B5-J); the seam properties (allowlist, caps
  before allocation, panic containment, placeholder) are unchanged.]*
- The live output window (`selahcue-output`) is a **separate process** from the operator
  console; the operator webview renders untrusted strings via `textContent` in audited spots
  (e.g. `dist/app.js` "untrusted deck name → textContent") but uses `innerHTML` for structural
  rebuilds — the discipline is per-callsite, not enforced by a framework.
- Workspace rules: parsers never panic on untrusted input; bounded memory with bounded-memory
  tests; no unbounded queues/caches.

Assets at risk: the operator PC (arbitrary file write → persistence/code execution), the
operator console (webview injection → Tauri IPC → full legitimate control of the app, including
live output), live-service availability (console hang/OOM/crash mid-service), audience-facing
content integrity (spoofed/invisible text), and privacy (a document must never cause network I/O
from an offline-first app).

---

## 2. Attack surface — source 1: `.txt` file

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T1.1 | Oversized file → OOM / hang | **Confirmed** | A multi-GiB "txt" read with `fs::read` lands wholly in RAM in the operator process. Control: hard size cap enforced **before/while reading** (streamed or metadata-checked then capped read), not after. |
| T1.2 | Pathological slide structure (millions of blank-line separators → millions of slides; or one 100 MiB "slide") | **Confirmed** | Must clamp during parse to the existing deck bounds (500 slides / 2000 chars per slide text / 4000 notes) and report drops — never build an unbounded intermediate `Vec` and truncate afterwards. |
| T1.3 | Invalid encoding (non-UTF-8, lone surrogates, overlong sequences, NUL bytes, BOMs) | **Confirmed (low)** | Rust `String` rejects invalid UTF-8 by construction; the risk is importer error paths, mojibake, and NULs reaching SQLite/UI. Windows-1252 lyric files are common in churches: decode lossy (U+FFFD) and **report** the substitution per the partial model rather than reject. Strip NULs. |
| T1.4 | Control chars / ANSI escapes / bidi overrides reaching audience output or logs | **Confirmed (low sev, cheap fix)** | See §7 string hygiene (C10). ANSI escapes matter only for terminal logs; bidi/zero-width matter on the projector. |
| T1.5 | Zip-slip / XXE / decoder exploits | **Dismissed** | No archive, no XML, no image decode on this path. |
| T1.6 | Filename → deck name injection | **Confirmed** | Shared with all file sources; see §7 (C10/C11). |

## 3. Attack surface — source 2: `.pptx`

A `.pptx` is a ZIP of OOXML parts plus media. This is the widest surface; a volunteer importing
an internet-downloaded deck is the design-basis attacker delivery.

### 3.1 Archive layer

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T2.1 | **Zip-slip / path traversal** (`../../x`, absolute paths `/etc/...`, `C:\...`, drive-relative, backslash separators) | **Confirmed — Blocker B1** | Arbitrary file write on the church PC → startup-folder persistence / code execution. **Structural kill:** the importer must never construct a filesystem path from an archive entry name. Entries are read into bounded memory; images are written under **app-generated names** (content hash or sequential id) inside the media root. With that rule, traversal, absolute paths, Windows reserved device names (`CON`, `NUL`, `COM1`…), and case-insensitive collisions (APFS/NTFS default) are all impossible by construction — but each still gets a test (§7) because the rule is only as good as its enforcement. |
| T2.2 | **Symlink / hardlink entries** (unix mode bits in external attrs; a symlink extracted first, a later entry written *through* it) | **Confirmed — Blocker B1** | Same structural kill: only regular-file entry *contents* are ever read; entry types, mode bits, and link targets are ignored. The importer must not use any zip library "extract-to-directory" convenience API (several honour symlinks). Dismissed *as an outcome* only because B1 forbids the vulnerable operation. |
| T2.3 | **Decompression bombs — absolute** (small file inflating to tens of GiB; DEFLATE peaks near 1032:1, so a 10 MiB member can inflate toward ~10 GiB) | **Confirmed — Blocker B3** | Caps on **actual inflated bytes, enforced during streaming decompression**: per-entry cap and total-across-archive cap; abort the entry (partial model) or the import at breach. **Never trust the declared uncompressed size in the zip headers** — it can lie in both directions; a correct reader counts what actually comes out of the inflater. |
| T2.4 | **Decompression bombs — ratio** | **Confirmed** | Secondary heuristic to the absolute caps: ratio guard (e.g. 100:1, evaluated only after ≥1 MiB of output to avoid false positives on tiny highly-compressible parts). The absolute caps are load-bearing; the ratio cap is early-abort economy. |
| T2.5 | **Zip quines / nested archives** (Cox-style self-containing zips, zip-in-zip) | **Dismissed with condition** | Dangerous only under *recursive* extraction. The importer never recurses into any nested container (nested zip, OLE, `vbaProject.bin`, embedded `.pptx`); such parts are dropped-and-reported (C7). With no recursion, a quine is just one bounded entry. |
| T2.6 | **Oversized member counts** (100k+ entries; central-directory abuse; duplicate entry names) | **Confirmed** | Cap entry count (real decks have ~4 parts per slide + media; 4,096 is generous). Duplicate part names: first occurrence wins, rest dropped-and-reported (prevents "parse one copy, extract the other" confusion). |
| T2.7 | Encrypted zip entries / zip64 | **Confirmed (reject)** | Encrypted entries cannot be scanned → reject with an honest error. zip64 implies >4 GiB structures no real slide deck needs → reject (C1). Keeps the parser surface small. |
| T2.8 | Lying zip metadata (bad CRCs, overlapping local headers vs central directory, truncated streams) | **Confirmed** | Must degrade per the partial model or fail cleanly — never panic, never trust offsets without bounds checks. Covered by the no-panic battery (§7.5) and B3's actual-bytes accounting. |

### 3.2 OOXML / XML layer

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T2.9 | **XXE / external DTD or entity fetch** | **Confirmed — Blocker B2** | Doubly disqualifying here: (a) classic file disclosure — and the external fetch itself is the exfil channel (file content smuggled into the fetched URL); (b) **this app is offline-first — ANY document-triggered network I/O is a security AND privacy defect**, full stop. OOXML never legitimately contains a DTD: **reject any XML part containing `<!DOCTYPE`** (drop-and-report per the partial model) and require the parser to have DTD/external-entity processing disabled regardless. The property must be *tested*, not assumed from the crate's defaults (Aria owns crate choice; this is the property it must satisfy). |
| T2.10 | **Entity expansion / billion laughs / quadratic blowup** | **Dismissed via B2** | Expansion attacks require DTD-declared entities; rejecting `<!DOCTYPE` kills the class. Only the XML built-ins (`&lt; &gt; &amp; &apos; &quot;` and numeric refs) are expanded, which cannot amplify. Numeric-ref floods are bounded by the part-size cap. |
| T2.11 | **Malformed OOXML → panic** (missing/duplicate relationships, broken `[Content_Types].xml`, dangling `r:embed` ids, wrong types where numbers are expected) | **Confirmed** | Workspace rule already: never panic on untrusted input. Every structural surprise degrades to dropped-and-reported (slide, image, or note level) or a clean typed import error. A `catch_unwind` belt at the import boundary backstops unforeseen panics (C9, B4) so the worst case is a failed import, not a console crash. |
| T2.12 | **Pathological XML structure** (10k-deep nesting → stack exhaustion; single multi-hundred-MiB attribute/text node; element floods) | **Confirmed** | Nesting-depth cap (256), streaming/pull parsing (no untrusted-size DOM), per-part size already bounded by B3, per-slide accumulated-text cap = existing `MAX_TEXT_ELEMENT_LEN`. |
| T2.13 | **Relationship indirection abuse** (`.rels` targets: `TargetMode="External"` URLs; package-relative `../` targets; cycles; many-to-one) | **Confirmed** | External targets are **never fetched** (B2) — recorded as dropped ("external image skipped"). Internal targets resolve **only against the set of entries actually in the archive** (string-normalised within the package namespace — never against the real filesystem). Cycles bounded by visited-set; shared media parts deduplicated so one part cannot be extracted N times against the byte budget. |
| T2.14 | Slide/element count exhaustion via valid OOXML (10,000 slides, 100k text runs on one slide) | **Confirmed** | Clamp during parse to `MAX_DECK_SLIDES`/`MAX_ELEMENTS`/`MAX_TEXT_ELEMENT_LEN`/`MAX_NOTES_LEN`; stop reading further slide parts once the deck cap is hit; report counts. |

### 3.3 Embedded media layer

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T2.15 | **Image decoder exploitation via extracted media** | **Confirmed — Blocker B5** | Real pptx media includes PNG, JPEG, GIF, BMP, TIFF, **WMF/EMF metafiles** (a historically exploit-rich Windows format) and, in modern decks, SVG (scriptable XML). The ONLY decode path is the existing bounded seam (`selahcue_engine::media`): PNG signature-verified, 64 MiB encoded / 40 MP decoded caps pre-allocation, panic-contained. Everything not decodable through that seam is **dropped-and-reported** — never handed to an OS/platform decoder (GDI/WIC/ImageIO/gdk-pixbuf), never rendered in the webview, never shell-opened. Format expansion later must go through the same seam with the same caps. Residual (honest): decode is **in-process** until the ADR-0016 worker ships — memory-safe pure-Rust decoder + pre-allocation caps bound it; see §9. *[Rev 1.1: JPEG moves from dropped to supported under the B5-J admission profile — 8-bit baseline/extended/progressive YCbCr/grayscale only; caps enforced at SOF parse before allocation; DNL height, arithmetic coding, lossless/hierarchical, 12/16-bit, CMYK, and non-standard sampling refused. GIF/BMP/TIFF/WMF/EMF/SVG remain dropped-and-reported.]* |
| T2.16 | **Embedded fonts** (`ppt/fonts/*.fntdata`) | **Confirmed (drop)** | Font parsing is its own decoder surface (ADR-0016 explicitly covers fonts as untrusted decode). The importer never extracts, installs, or parses embedded fonts — drop-and-report. |
| T2.17 | VBA macros / OLE / ActiveX (`vbaProject.bin`, embedded objects; `.pptm`) | **Dismissed with condition** | SelahCue contains no macro engine and no OLE loader; these bytes are inert *provided* C7 holds (never opened, never recursed into, never written to disk under an attacker-influenced name). Dropped-and-reported. Recorded so nobody later adds "open embedded object" casually. |
| T2.18 | Hyperlinks in slide text | **Dismissed** | Text-only import; link targets are not imported and never followed. If link *text* is imported it is plain text under C10/C11. |
| T2.19 | Image-count / media-byte exhaustion (500 slides × many images) | **Confirmed** | Per-deck image count cap and total-extracted-media byte cap (shares the B3 total); drops reported. |

### 3.4 Metadata / presentation layer

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T2.20 | **Filename / docProps metadata injection into deck name or UI** | **Confirmed** | The deck name comes from the filename (or `docProps/core.xml` title). Three sinks: (a) the **webview** — a name like `<img src=x onerror=...>` becomes operator-console XSS if any new import UI uses `innerHTML`; in a Tauri app webview XSS ≈ console compromise → full legitimate IPC control of the app including live output. `textContent`-only is already the repo's discipline for deck names (Verified, `app.js`) and must hold for ALL import UI including the **drop report**, which echoes hostile entry names — the report renderer is the sink people forget. (b) the **DB** — name is the deck PK: parameterized writes (Verified) kill SQL injection; imports must route through the existing `DeckLibrary` name-uniqueness path so a hostile name cannot clobber an existing deck. (c) **logs** — entry names with ANSI/newlines: escape/truncate before logging. Plus length/line caps (C10). |

## 4. Attack surface — source 3: clipboard

| # | Class | Verdict | Reasoning |
|---|---|---|---|
| T3.1 | **Non-text clipboard flavors** (HTML, RTF, image flavors) | **Confirmed — kill by policy** | The clipboard is attacker-influenceable (any website the volunteer copies "lyrics" from writes it; any local app can too) and multi-flavored. The importer requests **the plain-text flavor only** (`text/plain` UTF-8). RTF is an exploit-rich parser surface we simply never open; an HTML flavor pasted into the webview and ever rendered via `innerHTML` is direct operator-console XSS → Tauri IPC (same blast radius as T2.20a). If paste arrives via the WebView paste event, take `clipboardData.getData("text/plain")` explicitly — never `text/html`, never `paste` default insertion into a contenteditable. |
| T3.2 | Oversized paste (tens of MiB from a hostile page) | **Confirmed** | Cap bytes read from the clipboard (C3); truncate-and-report per the partial model. |
| T3.3 | **Control / bidi / zero-width / homoglyph characters reaching audience output** | **Confirmed (low sev)** | This is presentation software: what is imported gets **projected to a congregation**. Bidi overrides (U+202A–U+202E, U+2066–U+2069) can visually reverse or splice text; zero-width chars poison search/dedup and hide content diffs. Strip per C10. **Homoglyphs (lookalike glyphs) are NOT fully mitigable** and are accepted residual (§9) — a human operator previews slides before Go Live, which is the real control. Note: do **not** blanket-strip ZWJ/ZWNJ — they are load-bearing for Arabic/Persian/Indic text and emoji; MVP text stack is Latin-first (ADR-0014) so stripping the bidi-control set now is safe, with a documented revisit when RTL lands. |
| T3.4 | Paste-of-archive / binary garbage | **Confirmed (trivial)** | Clipboard path parses text only — binary junk is just characters; bounds + hygiene apply. No file parsing on this path. |

---

## 5. Ranked risks (product-realistic severity)

Severity here weighs a live Sunday service: an import that hangs or kills the operator console
mid-service is rated for *that* harm, not for a generic CVSS server model.

| Rank | Risk | Sev | Likelihood | Why |
|---|---|---|---|---|
| R1 | Resource exhaustion during `.pptx` import **while live** (bomb, member flood, XML pathology → console OOM/hang) | **High** | **Medium-High** — includes *non-malicious* huge real decks, so it WILL happen | Output survives (separate process, Verified) but the operator loses the console mid-service. The parent controls: B3 streaming caps, C13 off-thread + cancel + timeout, B4 atomic commit. |
| R2 | Zip-slip / symlink write escape → arbitrary file write → persistence/code exec on the church PC | **High** | Low-Medium (crafted file; internet-deck story makes delivery plausible) | Worst confidentiality/integrity outcome available here. Structurally eliminated by B1. |
| R3 | Webview injection via imported strings (deck name, slide text, **drop report**) → operator-console compromise → legitimate IPC control incl. live output | **High** | Medium (one `innerHTML` in new import UI is all it takes) | C11 + headless render test. |
| R4 | Malformed OOXML/zip → importer panic → console crash | **Medium** | High (garbage files are common) | No-panic rule + typed errors + `catch_unwind` belt (C9, B4); crash contains to failed import. |
| R5 | XXE / external-entity or external-relationship fetch → file disclosure **and** offline-first privacy break | **Medium** | Low (Rust XML crates don't resolve external entities by default — but that must be pinned by test, not assumed) | B2 kills the class; also covers billion-laughs. |
| R6 | Image decoder exploitation (in-process decode until ADR-0016) | **Medium** | Low-Medium *(Rev 1.1: JPEG materially enlarges the surface — Huffman, progressive coefficient handling, upsampling are the historically CVE-dense parts of C decoders; still pure-Rust memory-safe with pre-allocation caps and the B5-J profile refusing every rare variant)* | B5/B5-J keep metafiles/SVG/OS decoders out entirely; crate constraint gates the decoder pick (§7); residual documented §9 RR1. |
| R7 | Audience content spoofing via bidi/invisible chars | **Low** | Medium | C10 strip; operator preview is the human backstop. |
| R8 | Deck-name PK abuse (clobber/rename confusion) | **Low** | Low | Existing "(n)" uniqueness path + C10 caps; parameterized SQL (Verified). |

---

## 6. Live-service isolation and failure mode (the requirement, not advice)

**Verified baseline:** live output runs in `selahcue-output`, a separate OS process from the
operator console; the deck library is operator-local. So the maximum blast radius of any importer
failure is the **operator console**, not the projected image. That containment is necessary but
not sufficient — losing the console mid-service is still a service incident.

Required properties (testable):

1. **Placement.** Import executes asynchronously off the webview/UI thread and off any thread
   servicing live-console IPC (Tauri command handlers must not block on import). One import at a
   time (serialize; reject a second with an honest "import in progress").
2. **The output process is untouchable.** No importer code path may call into the output process,
   presenter state, autosave checkpointing, or the LAN server. The import touches exactly:
   importer memory → staged media temp area → (on success) `DeckLibrary` + `media_repo`.
3. **Atomic commit.** Nothing is visible to the library or media store until the parsed deck has
   fully passed bounds: build the bounded `SlideDeck` + staged media files, then commit through
   the existing `DeckLibrary` add path in one step. Failure/cancel/timeout leaves library, media
   store, and live state **byte-identical**; staged temp files are cleaned (including
   next-launch cleanup after a crash).
4. **Cancellation + timeout.** The operator can cancel; a wall-clock timeout (default 30 s)
   aborts a wedged import with a typed error. Cancellation must interrupt streaming
   decompression and XML parsing at chunk granularity (no uninterruptible multi-GiB loop).
5. **Failure mode.** Every failure — cap breach, malformed input, timeout, cancel, panic caught
   at the boundary — produces: (a) a typed error + the partial-import report in the console,
   (b) zero mutation, (c) live output and the LAN session unaffected. Never `process::exit`,
   never `abort`, never an unhandled panic escaping the import boundary. A **rejected file is
   the good outcome**; the design goal is that rejection is boring.
6. **Memory budget.** The caps must *compose*: per-entry cap × concurrency (1) + total inflated
   cap + staged bytes ⇒ worst-case importer working set ≤ ~350 MiB, documented and asserted
   structurally (repo bounded-memory rule). The load-bearing cap is the **total** inflated cap —
   a per-entry cap alone times 4,096 entries is not a bound.

---

## 7. Constraint list for the implementer (Kenji)

Numbers are enforceable defaults; the owner may tune them, but each MUST exist, be enforced at
the stated point, and have the stated test. **B-x = build blocker** (feature must not merge
without it); **C-x = required this slice**; **R-x = recommended hardening**.

### Blockers

- **B1 — No filesystem path is ever derived from archive content.** Entry names, relationship
  targets, and metadata never touch path construction. Only regular-file entry *contents* are
  read; symlink/hardlink/directory semantics, mode bits, and any extract-to-directory library
  helper are never used. Extracted images are written under app-generated names (content hash or
  id) inside the media root, registered via `media_repo`. *Test:* hostile entry names (`../`,
  absolute, drive, backslash, `CON`, case-collisions, symlink entries) — assert nothing outside
  the staging dir is created and names never appear in paths (§8.2).
- **B2 — No DTD, no network. Ever.** Any XML part containing `<!DOCTYPE` is dropped-and-reported;
  the XML parser has DTD/external-entity processing disabled regardless; `TargetMode="External"`
  relationship targets are never fetched (dropped-and-reported). The importer module has **no
  network capability by construction** — no network dependency in its dependency graph.
  *Test:* §8.3 + CI dependency assertion.
- **B3 — Streaming decompression caps on actual bytes.** Per-entry inflated cap **64 MiB**;
  total inflated cap across the archive **256 MiB**; enforced inside the streaming inflate loop
  on bytes actually produced — declared sizes from zip headers are never trusted for any
  allocation or admission decision. Breach ⇒ drop entry / abort import (typed error), per the
  partial model. *Test:* §8.2 lying-header and bomb cases.
- **B4 — Live isolation + atomic commit + contained failure** exactly as §6 (placement, atomicity,
  cancel/timeout, typed-failure-only, no output-process interaction). *Test:* §8.5/§8.6.
- **B5 (revised in 1.1) — Extracted images decode only through the bounded seam; supported
  formats are PNG and B5-J-conforming JPEG.** The seam properties are unchanged and remain the
  blocker: signature/structure allowlist, 64 MiB encoded cap, pixel caps enforced **before
  allocation**, panic-contained, placeholder on failure, output only via the checked
  `DecodedImage::from_rgba` path. Formats outside {PNG, B5-J JPEG} — GIF/BMP/TIFF/WMF/EMF/SVG/…
  — are dropped-and-reported. **Never an OS/platform still-image decoder; never rendered via
  the webview; no embedded-font extraction.** *Test:* §8.4.
  *(Audit trail: 1.0 admitted PNG only and listed JPEG among the dropped formats. Superseded
  2026-08-15 by the owner decision to add JPEG decode to `selahcue-engine` within this work,
  because real decks overwhelmingly embed JPEG.)*
- **B5-J — the JPEG admission profile** (every clause mandatory; a JPEG failing any clause is
  dropped-and-reported like any other unsupported format — never "best-effort" decoded):
  1. **Structural allowlist before decode:** SOI present; accepted frame types **SOF0
     (baseline), SOF1 (extended sequential), SOF2 (progressive) only**.
  2. **Dimension caps enforced at SOF parse, before any pixel or coefficient allocation** —
     hardened against the ways JPEG defeats a naive pre-check: **reject `height == 0` in SOF**
     (the DNL deferred-height mechanism, where the real height arrives in a DNL marker *after*
     the first scan, is refused, not supported); reject a second SOF marker; if the decoder
     reports any dimension change after header acceptance, treat it as `Malformed`. Caps: same
     dimension bounds as PNG; pixel cap **40 MP for SOF0/SOF1, 24 MP for SOF2** (clause 4).
  3. **The amplification bound is the pixel cap, not a ratio.** JPEG legitimately exceeds 100:1
     (a few hundred KiB decodes to 160 MiB of RGBA), so encoded/decoded ratio checks are
     meaningless for images — the image-level analogue of B3 is `max_pixels` enforced
     pre-allocation plus the shared 64 MiB encoded cap.
  4. **Decode-time working set is budgeted, not just the output buffer.** Progressive decode
     holds full-image coefficient planes (≈ W×H×components×2 bytes) in addition to the RGBA
     output and upsampling buffers; the tighter 24 MP progressive cap keeps the worst-case JPEG
     working set ≈ 240 MiB and inside the §6.6 import budget. The C14 bounded-memory
     composition must be re-documented to include coefficient planes.
  5. **Precision/component profile:** 8-bit precision only; 1-component grayscale and
     3-component YCbCr only; sampling factors restricted to {1×1, 1×2, 2×1, 2×2} (unusual
     factors multiply upsampling buffers and have a history of decoder edge-case bugs).
  6. **Metadata is length-skipped, never parsed:** EXIF/ICC/XMP/APPn segments are skipped by
     declared length only; EXIF orientation is NOT applied (the image renders as encoded); ICC
     profiles are never parsed or applied (ICC parsing is its own exploit-rich surface); EXIF
     thumbnails are never decoded.
  7. **Failure semantics as PNG:** truncated or garbage entropy data yields a typed
     `Malformed` → placeholder; never partially-initialized pixels, never a panic escaping the
     seam.

  **Refused variants — refused on risk grounds, not effort** (each lands in the drop report):
  arithmetic coding (SOF9–11/13–15 — its patent-era rarity means a near-zero real-world corpus
  and therefore near-zero fuzzing attention on those decoder paths), lossless and hierarchical
  modes (SOF3, SOF5–7), 12/16-bit precision, 4-component CMYK/YCCK (Adobe APP14), DNL /
  `height == 0`, non-standard sampling factors, multiple SOF markers. Rationale: every one of
  these multiplies rarely-exercised decode paths while contributing approximately zero coverage
  of real decks — PowerPoint and every mainstream photo pipeline emit 8-bit baseline or
  progressive YCbCr/grayscale.

### Required controls

- **C1 — `.pptx` admission:** reject files > **512 MiB**, zip64 archives, and encrypted entries
  with honest errors. Entry count cap **4,096**; duplicate part names → first wins, rest reported.
- **C2 — `.txt` admission:** read cap **16 MiB** (enforced during read); lossy UTF-8 decode with
  U+FFFD substitutions counted in the report; NULs stripped.
- **C3 — Clipboard:** plain-text flavor only (never HTML/RTF/image flavors); read cap **2 MiB**;
  truncation reported.
- **C4 — XML structure:** streaming/pull parser (no DOM sized by untrusted input); nesting depth
  cap **256**; per-part size bounded by B3.
- **C5 — Ratio guard (secondary to B3):** abort an entry exceeding **100:1** inflate ratio once
  ≥ 1 MiB has been produced.
- **C6 — Relationship resolution:** internal targets resolve only against the in-archive entry
  set (package-namespace normalisation, never the real filesystem); cycles bounded by a visited
  set; shared media parts deduplicated before counting against byte budgets.
- **C7 — No recursion into nested containers:** nested zip / OLE / `vbaProject.bin` / embedded
  packages are dropped-and-reported (kills zip-quine recursion and keeps macros/OLE inert).
- **C8 — Content clamps during parse (not after):** slides ≤ `MAX_DECK_SLIDES` (500; stop reading
  further slide parts at the cap), per-slide text ≤ `MAX_TEXT_ELEMENT_LEN` (2000, truncate),
  elements ≤ `MAX_ELEMENTS` (64), notes ≤ `MAX_NOTES_LEN` (4000, truncate); images ≤ **200** per
  deck and total extracted media ≤ the B3 total budget. All clamps appear in the report.
- **C9 — No-panic discipline:** no `unwrap`/`expect`/panicking index
  on parsed structure (workspace lint already warns); `catch_unwind` belt at the import boundary
  converts any residual panic into a failed-import error.
- **C10 — String hygiene at the boundary** (all three sources + any archive entry name destined
  for the report): strip C0 controls except `\n` `\t`, strip C1, strip bidi controls
  U+202A–U+202E and U+2066–U+2069 (documented revisit at the RTL milestone; ZWJ/ZWNJ preserved).
  Deck name additionally: single line, length ≤ **200** chars, non-empty fallback
  ("Imported presentation"), uniqueness via the existing `DeckLibrary` "(n)" path.
- **C11 — Sink discipline:** every imported string (deck name, slide text, notes, and every
  drop-report line including entry names) reaches the operator webview as DOM text
  (`textContent`) — never `innerHTML`/`insertAdjacentHTML`; all persistence via the existing
  parameterized repos; entry names escaped/truncated before logging.
- **C12 — Bounded report:** the drop report itemises at most **100** entries + aggregate counts
  (the report must not itself be an unbounded buffer).
- **C13 — Serialized, cancellable, time-boxed import** per §6 (timeout default **30 s**).
- **C14 — Bounded-memory test** per the repo rule: the cap composition of §6.6 asserted
  structurally.

### Recommended (not gating this slice)

- **R1 —** Content-Security-Policy in the operator `dist/` that bans inline script — turns any
  future `innerHTML` slip from console compromise into a broken layout. (Owner: Aria/Kenji;
  interacts with existing webview code, so it is a console-wide change, not import-scoped.)
- **R2 —** A short time-boxed fuzz target for the importer entry point in CI (§8.7).
- **R3 (revised 1.1) —** Schedule the ADR-0016 out-of-process decode worker with a **committed
  milestone** — no longer merely "re-prioritise": this feature is the first path where
  *internet-downloaded* files routinely reach the decoder, and 1.1 adds JPEG to that in-process
  surface. §9 RR1 carries the conditional-acceptance terms.

**Dependency note (for Aria, stated as properties not picks):** the zip reader must expose
streaming per-entry read with caller-controlled output limits and must not offer/require
extract-to-directory; the XML parser must be a streaming/pull parser with DTD processing
disabled or absent and a way to bound depth; neither may pull in a network stack. Whatever
crates are chosen, §8's tests pin the properties.

**JPEG decoder crate constraint (Rev 1.1 — the one dependency choice this review gates as
security-critical):** Aria owns the pick; the pick is invalid unless ALL of the following hold.
(a) **Pure Rust end-to-end** — no FFI to libjpeg / libjpeg-turbo / mozjpeg (C, long CVE
history) under any feature flag or transitive dependency. (b) **Unsafe posture:**
`forbid(unsafe_code)`, or unsafe confined to SIMD paths that are **feature-disabled for this
build**; a crate whose unsafe/SIMD paths cannot be disabled fails the constraint. (This also
protects NFR-014: platform-variant SIMD IDCT can produce ±1-LSB per-architecture differences
that would break the byte-parity golden tests — §8.4 adds a cross-platform byte-identity
assertion.) (c) **Caller-side limit enforcement before allocation:** the crate exposes
header/SOF metadata pre-decode or accepts configured memory/dimension limits; if it offers
neither, the importer pre-parses the SOF marker itself (a cheap, bounded marker walk over the
encoded bytes) before invoking the decoder, and the B5-J caps are enforced from that walk.
(d) **Maintained and audited:** RustSec advisory history reviewed at selection, version
pinned, covered by the NFR-027 SBOM/CVE scan, and upgrades gated on re-running the §8.4
battery. If no available crate satisfies (a)–(c), JPEG-in-process is not acceptable — see §9
RR1 for the fallback.

---

## 8. Testing the hostile cases — no malicious fixtures in the repo

Policy: **no hostile file is ever committed.** Every adversarial input is constructed
programmatically inside the test, from bytes the test itself writes. One tiny *benign*
self-authored `.pptx` fixture is acceptable for the happy path; everything hostile comes from a
builder. Suggested shape: a `tests/support/` helper (e.g. `pptx_builder.rs`) that assembles a
minimal valid package — `[Content_Types].xml`, `_rels/.rels`, `ppt/presentation.xml`,
per-slide XML + `.rels`, media parts — with injection points for every hostile mutation below.

1. **Zip-slip / symlinks / absolute paths / device names (B1).** Most zip-writing libraries
   happily write arbitrary entry *names* (they don't validate `../`); where a library refuses,
   hand-craft the container: a zip local-file-header + central-directory record is ~30 lines of
   test helper writing documented fixed offsets. For symlink entries, set the Unix external
   attributes (mode `0o120000 << 16`) on an entry whose content is the target path. Assert:
   import completes/fails per the partial model, **no file exists outside the staging dir**
   (walk a canary temp tree before/after), and no attacker-controlled string appears in any
   created path.
2. **Bombs and lying headers (B3/C5).** Generate a large inflate payload at test time —
   deflate-compressing tens/hundreds of MiB of zeros is fast and yields a tiny archive; write it
   as a member and assert the typed cap error fires and peak staging usage stays bounded
   (structural assertion on the importer's counters, per the repo's bounded-memory test style).
   For lying headers, write a valid member then patch the central-directory's declared
   uncompressed-size field to a small value — assert the cap still fires on **actual** inflated
   bytes. Member-count flood: write 100k zero-byte entries in a loop (fast) — assert the C1
   entry-count rejection.
3. **DOCTYPE / XXE / external fetch (B2).** Use the builder to emit a slide XML part prefixed
   with `<!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/hosts">]>` (and a parameter-entity variant),
   and a `.rels` with `TargetMode="External"` pointing at a URL. Assert: the part/image is
   dropped-and-reported, file content never appears in any imported string, and — the network
   claim — enforce **structurally**: a CI assertion that the importer's dependency graph
   contains no network crate (e.g. `cargo tree -p <importer> -e normal` grepped for
   `reqwest|hyper|ureq|curl|tokio-native-tls|rustls` allow-listed to fail), which is stronger
   and less flaky than socket interception on three OSes.
4. **Hostile media (B5/B5-J).** In-test bytes: a PNG whose IHDR declares 1,000,000 × 1,000,000
   (assert `Oversize` → placeholder path, no allocation — the existing `selahcue-engine` tests
   already model this; extend at the import boundary); truncated PNG; a GIF/BMP/TIFF/WMF/EMF/SVG
   magic-number stub each asserted **dropped-and-reported, never decoded**; a valid 1×1 PNG
   asserted imported. Assert no embedded-font part is ever staged.
   **JPEG battery (Rev 1.1)** — every case is a byte-patch of one tiny valid in-test JPEG
   (encode it at test time, or embed ~300 handwritten bytes in the builder; JPEG marker offsets
   are fixed and easy to document in the helper):
   - SOF dimensions patched to 65,500 × 65,500 → refused at header parse, **before any pixel or
     coefficient allocation** (structural counter assertion, per the repo bounded-memory style);
   - `height = 0` in SOF plus a DNL marker after the first scan → refused at header;
   - SOF0 marker byte `0xC0` patched to `0xC9` (arithmetic) and to `0xC3` (lossless) → refused;
   - precision byte 8 → 12 → refused; component count 3 → 4 with an Adobe APP14 segment →
     refused; sampling-factor bytes → 4×4 → refused; a second SOF appended → refused;
   - a valid **progressive** header at 30 MP (over the 24 MP SOF2 cap, under the 40 MP SOF0
     cap) → refused before coefficient-plane allocation;
   - a valid stream truncated mid-entropy-data → typed `Malformed`, placeholder, no panic;
   - a valid JPEG with EXIF orientation 6 and an embedded EXIF thumbnail → pixels are
     as-encoded (orientation ignored) and the thumbnail is never decoded;
   - boundary sanity: solid-colour JPEGs at exactly the pixel caps, one pixel under and one
     over → accept/reject exactly at the boundary;
   - determinism: decode one in-test JPEG on every CI platform and assert **byte-identical**
     RGBA output (protects the golden/parity oracle against platform-variant IDCT rounding).
5. **Panic containment (C9).** A malformed-input battery: truncated zip, truncated deflate
   stream, random bytes (fixed-seed RNG, e.g. 10k iterations of ≤4 KiB inputs — a cheap
   deterministic mini-fuzz that runs in CI), valid zip wrapping garbage XML, garbage UTF-8 in
   `.txt`/clipboard paths. Harness wraps each call in `catch_unwind` and fails the test on any
   panic; every input must yield `Ok(report)` or a typed error.
6. **Live isolation (B4).** Integration test in the operator crate: start an import of a
   slow/pathological (builder-generated) archive, assert (a) a concurrent deck-library/console
   operation completes promptly (event-loop not blocked), (b) cancel/timeout yields the typed
   error and **zero mutation** — deck list, media dir, and DB byte-identical to pre-import
   snapshots, staging dir empty. The existing `scripts/operator_headless.py` gate can additionally
   assert the console stays responsive during an import and that a deck named
   `<img src=x onerror=alert(1)>` renders **inertly as text** in the library list and in the
   drop report (computed DOM assertions, per the repo's headless-check pattern).
7. **(R2) Fuzzing.** A `cargo-fuzz` target `fuzz_import_pptx(bytes) -> ImportResult` seeded with
   the builder's minimal valid package; run time-boxed (minutes) in a nightly job, not the PR
   gate. Proportionate: the deterministic battery in (5) is the merge gate; the fuzzer is depth.
8. **String hygiene (C10).** Pure-function unit tests with escaped literals
   (`"\u{202E}"`, `"\u{200B}"`, C0/C1 samples, ZWJ-bearing emoji that must survive) — no
   fixtures needed. Property test (proptest) for the `.txt` slide-splitter: for arbitrary input,
   output respects all clamps and round-trips visible text.

---

## 9. Residual risks for explicit owner acceptance

| # | Residual | Why it remains | Mitigation in place | Owner decision |
|---|---|---|---|---|
| RR1 *(revised 1.1)* | **In-process image decode** until the ADR-0016 worker ships — now PNG **and JPEG**. JPEG multiplies decode paths (Huffman, progressive coefficient handling, upsampling — the historically CVE-dense parts of C decoders), which is why 1.0 made its worker recommendation on a PNG-only surface. | ADR-0018 accepted the in-process interim for PNG; the owner's 2026-08-15 decision adds JPEG within this work; this feature is the first routine path for *internet-downloaded* files to reach the decoder. | B5-J profile (variant refusal, caps at SOF parse pre-allocation, budgeted working set), the §7 crate constraint (pure-Rust, unsafe/SIMD disabled, RustSec-reviewed, pinned), panic containment, §8.4 battery. | **Revised position, stated plainly:** JPEG makes the 1.0 recommendation **stronger, but conditionally — not into a feature gate.** With the crate constraint held, the realistic marginal failure of memory-safe JPEG decode is a panic or over-allocation, both contained by existing controls, so gating the whole import feature on the sandbox worker remains disproportionate for this product. Acceptance is now **conditional and time-bounded**: (a) the ADR-0016 worker moves from "re-prioritise" to **scheduled with a committed milestone** — a ClickUp follow-up created at build time, and this acceptance lapses if that milestone is dropped; (b) **if no decoder crate satisfies the §7 constraint, JPEG-in-process is NOT accepted** — JPEG then waits for the sandbox worker and the feature ships PNG-only (the 1.0 posture) in the interim. Owner accepts on those terms, or gates JPEG on the worker. |
| RR2 | **Partial-import fidelity**: dropped content (unsupported images — non-PNG/JPEG formats and B5-J-refused JPEG variants — external images, fonts, SmartArt/shapes text nuances) means a volunteer can present a deck missing pieces if the report is ignored. | Chosen product model. | Bounded, explicit drop report (C12); preview before Go Live. | Product/UX: how loud the report is. |
| RR3 | **Homoglyph/lookalike spoofing** in imported text is not machine-detectable in general. | Unicode reality. | C10 strips controls/bidi; operator preview is the human control. | Accept. |
| RR4 | **No malware/reputation scanning** of imported files. | Offline-first desktop app; OS-level AV applies; we never execute imported content. | B1/B2/B5 make the file inert to SelahCue. | Accept. |
| RR5 | **Bidi stripping vs future RTL support**: C10 removes bidi controls that legitimate RTL text may need post-MVP. | ADR-0014 MVP is Latin-first. | Documented revisit trigger: the RTL milestone must revisit C10 before shipping RTL. | Accept with trigger. |
| RR6 | **Console loss ≠ output loss, but is still a service incident**: a novel exhaustion vector inside the caps could still make the console sluggish. | Bounds reduce, not abolish, resource use. | §6 budget composition + timeout + cancel. | Accept. |

---

## 10. Verdict

**Pass as a design constraint set** — build may proceed against §7. The five blockers B1–B5 are
merge gates for the feature: a presentation-import implementation missing any of them must not
merge, and the post-build security review will re-verify each constraint against code and the
§8 tests. Release security verdict for the feature: **Not Assessed** (nothing is built).

Revision 1.1 revises B5 in place: JPEG is admitted under the B5-J profile with the §7 crate
constraint as a hard precondition, and RR1 acceptance becomes conditional and time-bounded —
if the crate constraint cannot be met, JPEG support gates on the ADR-0016 worker while the
rest of the feature proceeds PNG-only.

Risk acceptance for §9 belongs to the product owner, not this role.

---

## 11. Post-build verification (v1.2 — 2026-08-16)

The importer has been built and this section re-verifies each constraint **against the code, not
against comments claiming compliance**. Where a control is enforced structurally (by construction)
rather than by a check, that is stated; where a check could be bypassed on some path, the path is
named.

**What was reviewed (working tree, uncommitted, at HEAD `f9d132a`):** the new `selahcue-import`
crate (`zip.rs`, `ooxml.rs`, `pkgpath.rs`, `pptx.rs`, `text.rs`, `decode.rs`, `hygiene.rs`,
`report.rs`, `build.rs`, `model.rs`, `error.rs`, `source.rs`, `sink.rs`, `limits.rs`, `lib.rs`,
plus `tests/` and `tests/support/mod.rs`); `selahcue-engine` `src/jpeg.rs`, `src/exif.rs`,
`src/media.rs`, `Cargo.toml`, `tests/test_jpeg.rs`, `tests/test_jpeg_alloc.rs`; operator
`src/media_store.rs` and the `deck_library.rs` collision-policy additions and `main.rs` module
declaration; `scripts/import_guards.sh` and its wiring into `Makefile` and `.github/workflows/ci.yml`.

**Method (all Verified unless labelled).** Full read of every source and test file named above;
`cargo test -p selahcue-import` (48 tests green) and `cargo test -p selahcue-engine` (JPEG battery +
`test_jpeg_alloc` green); `sh scripts/import_guards.sh` (passes); `cargo tree -p selahcue-import -e
normal` inspected in full (≈70 crates, all non-network); the pinned `jpeg-decoder 0.3.2` source
inspected in the registry cache; and one **empirical** reproduction built against the real crate in
a scratch harness (the referenced-bomb test described under Finding F1).

### 11.1 Scope reality — what is built, and what is not

The **library layer** is built: the pure `selahcue-import` transform, the `selahcue-engine` JPEG
decode seam, the operator media store, and the `DeckLibrary` collision policy. The **operator shell
wiring is not**: `main.rs` only *declares* `mod media_store;` — there is no Tauri import command, no
file dialog, no clipboard command, no 30 s wall-clock timeout, no single-import lock, no
`catch_unwind` belt at the shell boundary, and no webview report renderer. **The importer is
therefore not reachable by an operator yet**: no code path invokes `read_pptx`/`import_text` in the
running app. That is central to the release calibration below — hostile input cannot reach any of
this code in a running build today, so the constraints that live in the still-unwritten shell are
recorded as **DEFERRED**, to be re-verified when that slice is built, not as failures now.

### 11.2 Blockers

| # | Verdict | Evidence and enforcement |
|---|---|---|
| **B1 — no filesystem path from archive content** | **PASS (structural)** | `zip::EntryMeta` deliberately never records entry type, mode bits, external attributes or link target; `pkgpath::resolve` output is only ever a **lookup key** into the in-archive entry set (`pptx::find`), never joined to a directory; the store (`media_store.rs`) takes **no name of any kind** — it names files `import-<n>.<ext>` from a slot index and a `MediaFormat` *enum*, so there is no parameter through which an archive string can reach a path. Tests walk a canary tree before/after and assert nothing is created outside the media root on both the parser side (`hostile_entry_names_are_inert…`) and the store side (`hostile_archive_names_cannot_influence_any_created_path`). |
| **B2 — no DTD, no network** | **PASS (with a guard caveat — Finding F2)** | `ooxml::has_doctype` rejects any part whose first 1 KiB contains `<!doctype` (case-insensitive) *before the parser is constructed*, and `Event::DocType` is independently mapped to `XmlError::Doctype` (defence in depth, and it covers a DOCTYPE pushed past the first 1 KiB); `resolve_entity` expands only the five XML built-ins and numeric refs, unknown names → empty, so billion-laughs and entity smuggling are dead; `TargetMode="External"` rels are recorded as `ExternalImage`, never fetched. The importer's `cargo tree -e normal` graph is network-free (Verified across all ≈70 crates). The CI guard is a **denylist** — see F2. |
| **B3 — streaming caps on actual inflated bytes** | **Code PASS (structural), test coverage PARTIAL — Finding F1** | `zip::read_deflate` accounts **produced** bytes chunk-by-chunk via `account()` (`entry_total > entry_cap → EntryTooLarge`; `total_out > MAX_TOTAL_INFLATED_BYTES → ArchiveTooLarge`), entirely independent of the declared size; the declared size is used only for a cheap early abort. Empirically confirmed correct: a **referenced** member declaring 1 KiB that inflates to 200 MiB is stopped, stages nothing, and the slide's text survives (scratch harness). **But no committed test exercises this** — see F1. |
| **B4 — live isolation + atomic commit + contained failure** | **PARTIAL — atomic-commit half PASS, placement half DEFERRED** | The atomic-commit machinery is built and strongly tested: `ImportStaging` stages under `<app_data>/media/.staging/<import-id>/`, commits by `create_new`-reserved rename, and **cleans up in a `Drop` destructor** so every exit path (early return, `?`, timeout, cancel, panic-unwind) leaves the media root byte-identical; `sweep_stale_staging` covers the crash path at next launch. The `<import-id>` is minted internally and cannot be caller-supplied. **DEFERRED:** off-thread placement, one-import-at-a-time lock, output-process untouchability, the 30 s timeout and the `catch_unwind` belt all live in the unwritten shell. |
| **B5 — images only via the bounded seam; PNG + B5-J JPEG only** | **PASS (structural)** | `media::sniff` is a closed allowlist (PNG, JPEG) by magic bytes only; every other format (GIF/BMP/TIFF/WMF/EMF/SVG/JPEG 2000/HEIC) returns `Unsupported` → dropped-and-reported and never handed to an OS decoder, the webview, or a shell-open (`unsupported_image_formats_are_dropped_and_never_handed_to_a_decoder`). Embedded fonts and nested containers are surveyed and dropped, never opened (`survey_entries`). |

### 11.3 B5-J — the JPEG admission profile (clause by clause)

Enforced by `jpeg::probe` (a bounded, allocation-free marker walk) **before** any decoder is
constructed in `media::decode_jpeg_inner`. All **PASS**:

1. **Frame allowlist** — SOF0/1/2 only; lossless (C3), differential/hierarchical (C5–7, CD–CF) and
   arithmetic (C9–CB) refused on the marker byte alone, before the payload is read; a `DAC` marker
   (0xCC) and a `DNL` marker (0xDC) are refused too. *Verified* `jpeg.rs:99–113,95–97`; test
   `arithmetic_lossless_and_hierarchical_frames_are_refused`.
2. **Caps at SOF parse, before any pixel or coefficient allocation** — `height == 0` and
   `width == 0` → `Malformed`; a **second SOF** → `Malformed`; **caps-before-allocation proven** by a
   counting global allocator (`test_jpeg_alloc.rs`: a 65 500² frame and a 30 MP progressive frame
   each allocate < 64 KiB before refusal, and an admitted frame allocates > 0 as a positive control);
   a decoder-reported dimension change after header acceptance → `Malformed` (`media.rs:370`).
3. **Amplification bound is the pixel cap, not a ratio** — `admit_dimensions` enforces `w·h ≤
   min(max_pixels, format_pixel_cap)` pre-allocation.
4. **Budgeted working set** — `MAX_PIXELS_SEQUENTIAL = 40 MP`, `MAX_PIXELS_PROGRESSIVE = 24 MP`
   selected by `format_pixel_cap()`; `set_max_decoding_buffer_size` is the decoder-internal belt.
   Test `progressive_frames_get_the_tighter_pixel_cap` proves the 24 MP refusal precedes any
   coefficient plane.
5. **Precision/component/sampling** — 8-bit only; 1-component grayscale or 3-component YCbCr only,
   4-component → `UnsupportedColour`; sampling factors restricted to {1×1,1×2,2×1,2×2}. Tests
   `twelve_bit_precision_is_refused`, `cmyk_four_component_frames_are_dropped_as_a_colour_problem`,
   `unusual_sampling_factors_are_refused`.
6. **Metadata length-skipped, never parsed — EXCEPT EXIF orientation (owner-approved override,
   ADR-0025 decision 5).** This is the one v1.1 clause the build intentionally relaxes. See Finding
   F5; the relaxation is bounded and **I do not object**. ICC, XMP and EXIF thumbnails remain inert
   (length-skipped in the marker walk's `_ =>` arm).
7. **Failure semantics as PNG** — truncated/garbage entropy → typed `Malformed` → placeholder, never
   a partial image, never a panic; the third-party decode call is wrapped in `catch_unwind` at the
   engine boundary (`media.rs:351`). Tests `truncated_entropy_data_never_yields_a_partial_image` and
   `every_mutation_of_a_valid_jpeg_yields_a_typed_result_never_a_panic`.

**JPEG crate constraint (the one dependency this review gates) — fully met.** `jpeg-decoder =
"=0.3.2", default-features = false, features = ["platform_independent"]`: exact pin (Verified in
`Cargo.toml` and `Cargo.lock`); `platform_independent` promotes the crate to `forbid(unsafe_code)`
and compiles out the SSSE3/NEON kernels *and* their runtime dispatch (Verified in the crate source:
`#![cfg_attr(feature = "platform_independent", forbid(unsafe_code))]` and `#[cfg(not(feature =
"platform_independent"))] mod arch`); `rayon` is off; `jpeg-decoder` has **zero transitive
dependencies** so no libjpeg FFI or unsafe SIMD is reintroduced on any path; `zune` appears nowhere
in any lockfile. The determinism contract is pinned by a hash test across the CI matrix
(`jpeg_decode_is_byte_identical_across_the_ci_matrix`) and the pin/features are re-asserted by the CI
guard. Because the constraint is met, RR1's PNG-only fallback is **not** triggered.

### 11.4 Required controls C1–C14

| # | Verdict | Note |
|---|---|---|
| C1 — pptx admission | **PARTIAL** | zip64 refused, encrypted refused, entry-count 4096 and duplicate-name handling all enforced and tested in `zip.rs`. The **512 MiB file cap is shell-enforced** (`MAX_PPTX_FILE_BYTES` defined; not yet wired) — DEFERRED with the shell. |
| C2 — txt admission | **PARTIAL** | Lossy UTF-8 with counted U+FFFD, UTF-16/BOM handling, NUL strip all in `decode.rs` (PASS). The 16 MiB read cap is shell-enforced — DEFERRED. |
| C3 — clipboard | **PARTIAL** | `clamp_clipboard` enforces the 2 MiB char-boundary cap and reports it (PASS). **Plain-text-flavor-only** is a webview responsibility and is unbuilt — DEFERRED. |
| C4 — XML structure | **PASS** | `ooxml::Pull` is a pull reader with an explicit depth counter (256) and a 1 M-event budget; no DOM. Stack-safety proven on a 128 KiB stack (`deeply_nested_xml_is_dropped_rather_than_overflowing_the_stack`). |
| C5 — ratio guard | **PASS (code)** | `read_deflate` applies 100:1 after a 1 MiB floor. Mechanism present; shares F1's test gap for behavioural coverage. |
| C6 — relationship resolution | **PASS (stronger than required)** | `pptx` resolves relationships **one hop only** (slide→media, slide→notes); there is no recursive rel-following, so cycles are structurally impossible, not merely visited-set-bounded. Shared media deduplicated by resolved name (`staged` map; `one_media_part_referenced_from_many_slides_is_staged_exactly_once`). |
| C7 — no recursion into nested containers | **PASS** | `survey_entries` reports `NestedContainer` for `vbaproject`/`ppt/embeddings/`/`.zip`/`.pptx`/`.docx`/`.xlsx`; never opened. |
| C8 — content clamps during parse | **PASS** | Slides ≤ 500 (stop reading), lines ≤ 64, line ≤ 2000, notes ≤ 4000, title ≤ 200, pictures ≤ 16/slide, images ≤ 200/deck — all applied during parse in `text.rs`/`pptx.rs`/`build.rs`, all reported. |
| C9 — no-panic discipline | **PASS (pure crate) / DEFERRED (shell belt)** | `#![forbid(unsafe_code)]` + `deny(unwrap/expect/panic/todo/unimplemented)` crate-wide; `indexing_slicing`/`arithmetic_side_effects` denied on `zip`, `pkgpath`, `jpeg`, `exif` — **but not on `ooxml` (Finding F3)**. Panic battery: 10 k random inputs, pseudo-archives, every-byte-corruption, truncations — all total. The third-party JPEG decode is `catch_unwind`-wrapped at the engine boundary; no `panic = "abort"` in any Cargo.toml (Verified), so that belt is live. The **shell** `catch_unwind` belt is DEFERRED. |
| C10 — string hygiene at the boundary | **PASS** | `hygiene::clean` strips C0 (except `\n`,`\t`), C1, NUL and bidi U+202A–202E/U+2066–2069, **preserves ZWJ/ZWNJ**, counts what it removed; deck name single-lined, capped, fallback "Imported presentation". Applied at the producer for every string that leaves the crate, including report detail lines. |
| C11 — sink discipline | **PARTIAL** | Producer half PASS (all strings hygienised + length-capped before leaving the crate; DB writes go through parameterized repos). **Consumer half (report/deck-name rendered via `textContent`, headless computed-DOM assertion) is unbuilt** — no report renderer exists yet — DEFERRED. |
| C12 — bounded report | **PASS** | `MAX_REPORT_ITEMS = 100`, overflow counted not listed (`skipped_overflow`); asserted under a 400-drop flood in `test_memory`. |
| C13 — serialized, cancellable, time-boxed | **PARTIAL** | Cancellation is plumbed through the pure crate — polled between slides, between pictures and **inside the inflate loop at chunk granularity** (`cancellation_is_honoured_and_mutates_nothing`). The **30 s timeout and the single-import lock are shell-resident** — DEFERRED. |
| C14 — bounded-memory test | **PASS** | `test_memory.rs` installs a counting global allocator and asserts a worst-case import peaks under the documented 350 MiB across three scenarios (wide text, many-image pptx, drop flood). |

### 11.5 The four scepticism targets

**Target 1 — `exif.rs` (Finding F5, the owner-approved relaxation of B5-J clause 6). The bounds are
real; I do not object.** `orientation_from_tiff` requires an 8-byte TIFF header with an `II*\0`/`MM\0*`
byte order, walks **IFD0 only**, and — the property that matters most — **never follows a sub-IFD or
maker-note pointer**: the loop `continue`s past every non-orientation tag and the only offset it ever
dereferences is IFD0's, taken from the TIFF header. Entry count is `min`-capped at 512; every read is
`slice::get` and every offset is `checked_*`; the module carries the `indexing_slicing` /
`arithmetic_side_effects` denials. Reachability is bounded to the first 64 KiB and to the first
`Exif\0\0` APP1 segment, whose length is itself bounded by the 2-byte segment length. Out-of-range,
wrong-magic and truncated blocks all fall back to orientation 1 silently (`a_broken_exif_block_is_
silently_no_rotation`), and the whole stream is in the every-byte-corruption panic battery. This is a
genuine but small enlargement of parsing surface versus v1.1 (≈80 lines of bounded, allocation-free
slice reads with no pointer-chasing); it is now covered by its own lint regime and tests. Given the
product cost of importing photographs sideways, the relaxation is proportionate. **Verdict: accept.**

**Target 2 — `jpeg.rs` (B5-J caps). All the named properties hold against code** — see §11.3 clauses
1–7 and the `test_jpeg_alloc` counting-allocator proof. On the flagged provenance (written just
before the author's session ended, then reviewed only by its author): I read the module in full and
independently. The marker walk is total and allocation-free (every read bounds-checked, every offset
`checked_*`, each loop step consumes ≥ 1 byte so it terminates), and the caps genuinely run before
the decoder is constructed. I found **no defect** in it. (The one substantive observation is not in
`jpeg.rs` but in test coverage — see F1 — and it concerns the ZIP layer, not JPEG.)

**Target 3 — the hostile-input tests. Mostly strong; one is hollow (Finding F1).** The batteries are
genuinely fixture-free and genuinely adversarial: the DOCTYPE/XXE cases assert the part is dropped
*and* that the good slide still imports *and* that severity escalates; the B1 cases walk a canary
tree; the panic battery is a real deterministic mini-fuzz. **The exception is the B3 "lying header"
test** (`a_lying_header_does_not_get_past_the_streaming_counter`), which was my specific correction to
Aria and is therefore the one I scrutinised hardest. As written it does **not** exercise the streaming
counter: the 200 MiB under-declared bomb is added as a second `ppt/media/bomb.png`, which collides
with the empty `ppt/media/bomb.png` the builder already wrote; duplicate-name handling marks the bomb
a duplicate, `find()` resolves the slide's reference to the *first* (empty) entry, and the bomb is
never read. The test passes vacuously (`sink` is empty, so `all(|b| b.len() < 64 MiB)` is trivially
true) and **would pass equally against an implementation with no streaming counter at all** — the
definition of a worthless bomb test. The underlying code is nonetheless correct: I confirmed
empirically, with a scratch harness feeding a *referenced* under-declared bomb through the real
crate, that it stages nothing, keeps the slide's text, and does not balloon memory. So this is a
**gate-integrity / regression-risk** finding, not a live vulnerability.

**Target 4 — `import_guards.sh` and B2 (Finding F2).** The script runs in the gate and its no-I/O grep
is sound (it filters comment-only lines, so it cannot be silenced by prose, and it greps the real
`std::fs`/`std::net`/`std::process`/`std::env`/`File::open`/`OpenOptions` primitives). Its network
check, however, is a **denylist of 15 named crates**, not an allowlist. It catches the async
building blocks most stacks funnel through (`tokio`, `mio`, `socket2`) and the common clients, so a
transitive network crate would *usually* be caught — but a synchronous `std::net` socket opened
inside a **transitive** dependency (which the src-only grep does not cover) whose crate name is not on
the list would slip through. Today the property genuinely holds (I inspected the entire ≈70-crate
`-e normal` graph; it is network-free) and the lockfile is pinned, so the realistic path to a
regression is a deliberate dependency change under the NFR-027 SBOM gate. The check delivers B2 for
the current graph; as a *guard against future regressions* it has a real, nameable gap.

### 11.6 Findings, ranked for an offline single-operator desktop app

- **F1 — MEDIUM (merge condition).** The B3 "lying declared size" test is hollow: its bomb is an
  unreferenced duplicate, so the streaming actual-byte counter — the load-bearing bomb defense — is
  never exercised by any test that would fail against a declared-size-trusting implementation. Code
  is correct (empirically confirmed); the risk is that a future regression to trusting declared sizes
  would ship undetected. **Resolution:** add a test that references an under-declared member which
  inflates past the per-entry cap and asserts the typed `EntryTooLarge`/`ArchiveTooLarge` (and,
  ideally, a bounded peak). Not a code change; a test change.
- **F2 — LOW (hardening).** The B2 network guard is a denylist, not an allowlist, and the src no-I/O
  grep does not reach transitive dependencies, so an unlisted network crate entering transitively
  would not be caught. Holds today. **Resolution:** prefer an allowlist (or an SBOM-diff gate) so a
  new network dependency fails closed rather than requiring the denylist to have anticipated its name.
- **F3 — LOW (hardening).** `ooxml.rs` is missing the `indexing_slicing` / `arithmetic_side_effects`
  denials that design §4.2 explicitly mandated for it (the other three offset-parsing modules have
  them). The module runs on `quick-xml` events over already-bounded input and the panic battery finds
  no panic, so the residual is small, but the design's named structural control is absent on one of
  the three modules it was specified for. **Resolution:** add the two denials to `ooxml.rs`
  (`has_doctype` will need `slice::get`).
- **F4 — LOW.** `build.rs` re-checks `SlideDeck::within_bounds()` with `debug_assert!`, so the ingress
  backstop the design specified as always-on is compiled out of release builds. The per-step clamps
  are always applied, so `within_bounds` holds structurally regardless; only the backstop is weakened.
  **Resolution:** promote to `assert!` (or return a typed error), matching the design intent.
- **F5 — INFO / accepted.** EXIF orientation is applied (owner-approved override of B5-J clause 6).
  Bounds verified real; **no objection** (see Target 1).
- **INFO — DEFERRED shell integration.** The Tauri import commands, file dialog, clipboard-flavor
  discipline (C3), 30 s timeout + single-import lock (C13), off-thread placement + `catch_unwind`
  belt (B4 placement half), the shell-enforced admission caps (C1/C2 file sizes), and the webview
  report renderer with `textContent` (C11 consumer half) are **not built** — `main.rs` only declares
  the module, so the importer is not user-reachable. These constraints are neither PASS nor FAIL; they
  are unbuilt, and must get their own post-build review when that slice lands (see conditions).

### 11.7 RR1 — does the built code change my risk position?

No — and if anything it strengthens the basis for the owner's acceptance. The JPEG crate constraint
is **fully met** (pure Rust, `forbid(unsafe_code)`, no SIMD/`rayon`, no libjpeg FFI, no `zune`, exact
pin, determinism hash-pinned), so the RR1 fallback ("if no crate qualifies, JPEG waits for the
ADR-0016 worker and the feature ships PNG-only") is **not triggered**. The caps run before allocation
(proven by a counting allocator), variant refusal is complete, and a decoder panic is contained at
the engine boundary. In-process decode remains the interim exactly as RR1 assumed; the **standing
condition of RR1's time-bounded acceptance — the ADR-0016 out-of-process worker scheduled with a
committed milestone — remains outstanding and must be tracked**, and this acceptance lapses if that
milestone is dropped. Risk acceptance for RR1–RR6 remains the product owner's, not this role's
(unchanged from §9/§10).

### 11.8 Release verdict

**MERGE WITH CONDITIONS.** No blocker-level code defect was found: every B1–B5 and B5-J constraint
that is *built* is correctly implemented, and several (B1, B5, B5-J caps, atomic commit) are enforced
structurally rather than by a bypassable check. The library layer is sound and may merge. The
conditions are:

1. **Before the importer is wired to any Tauri command (i.e. before it is user-reachable), the
   shell-resident constraints get their own post-build security review:** B4 placement (off-thread,
   one-import-at-a-time, output-process untouchable) + the `catch_unwind` belt + a re-confirmation of
   no `panic = "abort"`; C13 (30 s timeout + import lock); C3 (clipboard plain-text flavor only); C11
   consumer half (report and deck name rendered via `textContent`, asserted by a headless
   computed-DOM check with a `<img src=x onerror=…>` name); and the shell-enforced admission caps
   (512 MiB / 16 MiB / 2 MiB). Merging the library now is safe *because* it is not yet reachable;
   wiring it without that review is not.
2. **Fix F1** — replace the hollow lying-header test with one that actually inflates a referenced,
   under-declared member past the cap, so the streaming actual-byte counter (my correction to Aria)
   is genuinely exercised and protected against regression.
3. **Recommended, not gating:** F3 (add the `ooxml.rs` lints) and F4 (promote the `build.rs` ingress
   check to an always-on assertion).

Release security verdict for the **feature** remains **Not Assessed as shippable** until the shell
slice exists and passes condition 1 — what is verified here is the library layer, which is not itself
user-reachable. RR1–RR6 acceptance (and the ADR-0016 milestone that RR1 is conditioned on) remain the
product owner's to hold.

---

## 12. Condition re-verification (v1.3 — 2026-08-16)

v1.2's verdict was **merge with conditions** — and a conditioned verdict is not an authorisation
until someone independent confirms the conditions were met. This section is that confirmation,
run against the still-uncommitted working tree at HEAD `f9d132a` (the `implementation/` status
hash is recorded in the goal contract; any later change to the reviewed files invalidates this
section for them). Method as §11 — code, not comments — plus one instrument §11 lacked:
**mutation runs against a scratchpad copy of the workspace** (the working tree itself was never
modified), in which one named control is neutered and the suites re-run, so "this test protects
that control" is demonstrated by a failing run rather than asserted from a test's name. Test
names have now twice proven unreliable evidence in this feature; mutation runs are the standard
here from now on.

### 12.1 Condition 2 — the F1 lying-header test (the adjudication this revision exists for)

**Condition DISCHARGED — by the new `tests/test_zip.rs` battery, not by the renamed lying-header
test, which still does not isolate the control its name claims.** Both halves of that sentence
matter; the second is Finding F6.

What landed (all Verified):

- `a_lying_header_does_not_get_past_the_streaming_counter` (test_pptx.rs:666) now injects its
  bomb with `PptxBuilder::replacing()`, so the 200 MiB member declaring 1 KiB is genuinely
  referenced by the slide and genuinely read — v1.2's hollowness (an unreferenced duplicate) is
  fixed. `tests/support/mod.rs` makes the fix structural: a replacement that matches no generated
  part **panics at `build()`** (mod.rs:506–513), so the whole class of silently-inert override
  is now unwritable, not merely fixed in one place.
- New `tests/test_zip.rs` (8 tests) gives the previously test-free archive constants their own
  battery — `ArchiveTooLarge`, `RatioExceeded`, `EntryTooLarge` (stored path, lying header),
  the stored-entry extent, `MAX_IMPORT_IMAGES`, and entry-name refusal — each case constructed
  so that *removing the named control produces a different observable outcome*.

The mutation matrix (every row Verified by execution; unmutated in-tree control run: **81/81
green, exit 0**):

| Mutation (scratchpad replica only) | `test_zip.rs` | lying-header e2e |
|---|---|---|
| none (control) | 8 pass | pass |
| `account()`'s `EntryTooLarge` + `ArchiveTooLarge` returns neutered | **2 FAIL** — the stored-member test degrades to `[ImageFormatUnsupported]` vs required `[ImageTooLarge]` (test_zip.rs:209); the archive-budget test's import **succeeds**, 17 slides, every bomb fully inflated — "nothing looks wrong from the outside while the memory goes" | passes — the ratio guard (zip.rs:363) refuses the ~1000:1 zeros bomb at ~1 MiB |
| ratio guard (zip.rs:363) neutered | **1 FAIL** — `a_high_ratio_member_is_refused…` | passes — the byte counter refuses the bomb at the 16 MiB entry cap |
| both of the above neutered | not run | **FAIL** — the bomb inflates in full and degrades to `[ImageFormatUnsupported]` |

The gate-integrity question, answered directly: **had the remediation been only the rewritten
lying-header test, the condition would be only APPARENTLY satisfied.** That test still passes
with the streaming counter's cap returns deleted, because its `deflate_zeros` payload compresses
near 1000:1 and the ratio guard refuses it at ~1 MiB — before either byte cap is in range — and
because `RatioExceeded` and `EntryTooLarge` collapse to the same `SkipKind::ImageTooLarge` at
pptx.rs:456, its assertion cannot tell the two apart. That is the same gate-integrity defect one
layer down, exactly as the coordinator put it.

What genuinely discharges the condition is the battery: **each of the three archive-layer
controls now has at least one test that fails when that control alone is removed.** In
particular, F1's stated resolution — a referenced, under-declared member driven past the
per-entry cap with the typed refusal asserted — exists verbatim as
`a_stored_member_past_the_per_entry_cap_is_stopped_by_the_produced_byte_counter`: the lying
header (claiming 1 KiB) defeats the declared-size early abort, the stored method leaves no ratio
to judge, incompressible content keeps every other guard out of range — so the produced-byte
counter is the *only* control able to refuse it, and the mutation run proves the test notices
its loss. The counter's whole-archive half is isolated the same way by
`the_whole_archive_budget_aborts…`, whose members are deliberately ~50:1
(`deflate_lowish_ratio`) because — as that test's own comment records — a bomb of pure zeros
never reaches either byte counter. The bomb's memory claim is measured, not asserted:
`test_memory` scenario 7 bounds the lying-header bomb's peak under the 32 MiB `HOSTILE_BUDGET`.

The lying-header test is right to keep: it is now a genuine end-to-end defence-in-depth gate —
it fails only when BOTH actual-byte guards are gone (row 4), which is the catastrophic
regression. But:

**Finding F6 — LOW (test self-description; not gating).** The test's name and inline comment
("the produced-byte counter is what must stop this") attribute its refusal to the wrong control
in the shipped configuration: for its ~1000:1 payload the ratio guard fires first, and the
counter stops the bomb only when the ratio guard is absent. A future reader deleting the ratio
guard "because the byte caps are the guarantee" would be told by this test's name that the
counter path is covered end-to-end when the deflate-path entry cap in fact has no isolating
test of its own. Resolution (one line): build the bomb with `deflate_lowish_ratio` instead of
`deflate_zeros` — the ratio guard leaves the picture, the entry cap becomes the only guard in
range, the test isolates the deflate-path byte counter, and the name becomes true.

### 12.2 The other landed remediation items

| Item | Verdict | Evidence |
|---|---|---|
| **Streamed central directory** (the realised-R1 defect; see §12.3) | **PASS (structural + measured)** | `read_central_directory` (zip.rs:440–527) walks one 46-byte header plus one reused 512-byte name buffer through the `ByteSource`; the name cap is consulted **before** any name allocation; `vec![0u8; cd_size]` is gone. Iterations are bounded: ≤ 4,096 signature-valid records (`MAX_ZIP_ENTRIES`, checked before push) and every iteration advances ≥ 46 bytes. Measured: `test_memory` scenarios 5–6 reproduce the attack shapes — a 200 MiB *declared* directory inside a synthesised 512 MiB file, and 4,090 records × 65,000-byte names (the shape that measured **1015 MiB** peak pre-fix) — under a **32 MiB** `HOSTILE_BUDGET`, green in-tree. The fixture is synthesised from a rule (`HostileDirectory`), so the measurement weighs the importer alone. |
| **`read_stored` reads `compressed_size`, not `declared_size`** | **PASS — no new path opened** | zip.rs:271–307. For a stored member the on-disk extent *is* the compressed size; `declared_size` stays untrusted (cheap early abort only, zip.rs:254). The extent remains attacker-chosen — but it is clamped to `available` (bytes physically present), chunk-read at 64 KiB, and charged to `account()` **before** `out` grows (zip.rs:302–303), so the worst a lying extent achieves is serving *other attacker-controlled archive bytes* as this part's content — content confusion inside the attacker's own file, no trust boundary crossed, everything downstream still structurally validated. Both directions of the lie are tested (`a_stored_members_extent_is_its_compressed_size_not_the_size_it_declares`, incl. the adjacent-member-bytes assertion). |
| **`PptxBuilder::replacing()` panic-on-no-match** | **PASS (structural)** | mod.rs:394–517: every generated part routes through one substitution closure; each replacement is marked used; an unused replacement is an `assert!` failure at `build()` naming the vacuous-pass failure mode. All 81 in-tree tests green ⇒ every replacement in the suite matches a real part today. |
| **F2 — `import_guards.sh` B2 guard** | **CLOSED — delivers B2 as a regression guard** | The graph check is now a ~62-name transitive **allowlist** over `cargo tree -p selahcue-import -e normal` (the 15-name denylist is retained as a second tripwire with an explanatory failure). Any crate entering the graph at any depth under any name fails closed and forces a reviewed, reasoned diff. Verified: the script passes against the real graph in the gate; a simulated injection of `ureq` and of an arbitrary unlisted name are both caught. Honest residual (unchanged in kind from v1.2): a version bump of an *already-allowlisted* crate that grows network behaviour internally (e.g. via `libc`, legitimately present) is invisible to any name list — that is the NFR-027 SBOM/CVE gate's job, and the lockfile pins versions in the meantime. |
| **F3 — `ooxml.rs` lint denials** | **CLOSED** | `#![deny(clippy::indexing_slicing, clippy::arithmetic_side_effects)]` at ooxml.rs:34, with the module doc naming the design rationale; `has_doctype` now bounds via `slice::get` (ooxml.rs:64–68). `cargo clippy -p selahcue-import --all-targets` is clean. All three modules the design named (`zip`, `pkgpath`, `ooxml`) now carry the pair, plus `jpeg`/`exif` in the engine. |
| **F4 — `build.rs` ingress backstop** | **CLOSED — resolved better than the fix F4 named** | The `debug_assert!` became an always-on **repair-and-report** (build.rs:86–118): an out-of-bounds slide is removed and reported (`SkipKind::SlideOutOfBounds`) instead of panicking the operator console over a file the user merely opened — a live `assert!`, which F4 literally suggested, would have traded the backstop for a console-crash path in a crate that denies `clippy::panic`. The deck-level repair loop's termination does not depend on `remove` succeeding (it stops on any pass that fails to shrink). Accepted. Noted honestly: the repair path has no test hit and is unreachable through the public API precisely because the per-step clamps hold — it is a backstop against future drift, verifiable today by inspection only. |
| **`quick-xml` pinned `=0.41.0`** | **PASS** | Exact pin + `default-features = false` (selahcue-import/Cargo.toml:35); lockfile resolves 0.41.0 — the same version the previous caret range had already resolved, so no parser code moved under the pin; `import_guards.sh` now enforces this pin's presence exactly as it enforces the jpeg-decoder pin, closing the asymmetry that let the range be written in the first place. |

### 12.3 Method: why §11 missed the central-directory allocation — and what is verifiable only by measurement

The defect Cody found — `vec![0u8; cd_size]`, an attacker-chosen allocation bounded only by the
512 MiB admission cap, **measured at 1015 MiB peak against the ~350 MiB §6.6 budget** — is
**B3's own constraint text violated** ("declared sizes from zip headers are never trusted for
any allocation or admission decision") and **R1 realised**, in a section §11 marked "Code PASS
(structural)". The miss has a precise, repeatable shape, so it is worth naming exactly: B3
states a *universal negative* ("never … any allocation"), and §11 verified it by inspecting the
*named positive mechanism* — the streaming inflate loop and `account()` — and stopping there. A
universal negative is not verified by finding the right control present; it is verified by
proving the wrong pattern absent, **everywhere**. The central-directory read sat outside the
decompression path that B3's text foregrounds, so a mechanism-focused pass never read it as a
B3 site. Two method changes follow, both now embodied in the tree and standing policy for my
future reviews here: (a) every universal-negative constraint gets an exhaustive allocation-site
sweep (`vec![0u8; n]` / `with_capacity` / `reserve` / `String` construction against any
attacker-derived length) across the whole boundary crate, not a mechanism check; (b) every such
constraint also gets an **adversarial measurement** — a counting-allocator test fed the hostile
shape — because inspection cannot see the site it does not think to read, and v1.2's C14 PASS
was measuring only benign worst cases, under whose 350 MiB assertion a 200 MiB attacker-sized
buffer would have sailed unnoticed (the new hostile scenarios assert 32 MiB).

The direct answer to the standing question — **yes, several controls in this model are
verifiable only by measurement, not by inspection**, and each now has (or already had) its
instrument:

- **§6.6 / C14 — the composed memory budget.** The working set includes `flate2`, `quick-xml`
  and `jpeg-decoder` internals; no reading of first-party code bounds it. Instrument: the
  `test_memory` counting allocator — now including the hostile-metadata scenarios (5–7), the
  piece v1.2's C14 verdict lacked.
- **B5-J clauses 2/4 — "no pixel or coefficient allocation before refusal"** — a claim about a
  third-party crate's internal allocation order; provable only by `test_jpeg_alloc`'s counting
  allocator (measured since v1.2).
- **C4's stack safety at depth** — proven by the 128 KiB-stack run, not by reading an iterative
  loop and believing it.
- **JPEG cross-platform byte-determinism** — a CI-matrix measurement by construction.
- **B4's placement half** (event-loop responsiveness during a hostile import) — a timing
  property; when the shell lands, its review must measure it, not read it.

Everything else across B1/B2/B5/C1–C12 remains inspection-verifiable (structural absence of a
parameter, closed allowlists, seams) — with mutation runs now required before this document
claims any test protects any control.

### 12.4 DEFERRED — restated in full, so this revision is not mistaken for clearance

Nothing in this revision wires the shell. Re-verified today: no code path outside
`media_store`'s own tests invokes `read_pptx`/`import_text`; the operator's `main.rs` still only
*declares* `mod media_store` (`deck_import_image` at main.rs:1741 is the pre-existing
deck-library image picker, present at HEAD, and does not touch `selahcue-import`). The importer
remains unreachable by an operator, and the following constraints remain **DEFERRED — unbuilt
and unreviewed**, exactly as in §11:

- **B4 placement half** — off-thread execution, the one-import-at-a-time lock, output-process
  untouchability, the shell-boundary `catch_unwind` belt (+ re-confirming no `panic = "abort"`);
- **C13** — the 30 s wall-clock timeout and the single-import serialisation;
- **C3** — clipboard **plain-text-flavor-only** discipline in the webview/shell;
- **C11 consumer half** — report lines and deck name rendered via `textContent`, asserted by a
  headless computed-DOM check with a hostile name;
- **C1/C2 admission caps** — 512 MiB / 16 MiB / 2 MiB, defined in `limits.rs` but enforceable
  only by the shell.

**v1.2 condition 1 therefore stands in full:** before the importer is wired to any Tauri
command — before it is user-reachable — that shell slice gets its own post-build security
review covering exactly this list. Merging the library now is safe *because* it is not
reachable; wiring it without that review is not.

### 12.5 RR1 — the standing condition, still outstanding

Unchanged in substance and **still open**: the owner's RR1 acceptance is conditional on the
ADR-0016 out-of-process decode worker being **scheduled with a committed milestone**, and as of
this review **no ClickUp ticket for that milestone exists** — creation was blocked by ClickUp
rate-limiting at build time, ClickUp MCP is unavailable in this session too, and the delivery
record still lists the worker only as ADR-0018's "deferred end-state" (Verified against
`docs/delivery/BUILD_STATE.md`). The acceptance lapses if the milestone is dropped; until the
ticket exists, the condition is unmet in the only form the acceptance recognises. This is the
one open item that belongs to nobody's code. It must be created and linked to Build Control
`86ajnx548` the moment ClickUp is writable; this section is the standing reminder, and it
should not survive into a v1.4 as still-open.

### 12.6 Verdict

**Condition 2 is DISCHARGED, and the change set MERGES.** The streaming actual-byte counter is
now genuinely exercised and protected against regression — proven by mutation runs, not by test
names — and every other landed remediation item passes independent re-verification, several
structurally. For the audit trail, stated plainly: the renamed lying-header test **alone** would
not have discharged the condition — it passing under a neutered counter is precisely the
gate-integrity defect one layer down — and the discharge rests on the `test_zip.rs` battery,
whose per-control isolation was verified by executing the mutations, and on the measured
hostile-memory scenarios.

Remaining, unchanged: **condition 1** (the shell-slice security review, §12.4) is a standing
pre-wiring gate, not a blocker on merging this library layer. **F6** and the F2 residual are
recommended, not gating. The release security verdict for the **feature** remains **Not
Assessed as shippable** until the shell slice exists and passes its own review. RR1–RR6
acceptance — and the ADR-0016 milestone ticket that RR1's acceptance is conditioned on (§12.5)
— remain the product owner's to hold, not this role's.
