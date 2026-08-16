# ADR-0024 — Presentation import: a pure workspace crate, a hand-rolled ZIP reader, and an injected I/O seam

- Status: Proposed (for review)
- Date: 2026-08-15
- Confidence: High for the crate placement and the seam (both follow existing repository patterns and are test-verifiable). Medium for the hand-rolled ZIP reader — the reasoning is strong but we take on format bugs, so the decision ships with a documented escape hatch.
- Owner: Software Architect, with Security Reviewer (constraint set) and Backend Engineer (delivery)
- Relates: **ADR-0018** (bounded in-process still-image decode — the decode seam this consumes), **ADR-0025** (JPEG decode, the sibling decision), ADR-0016 (out-of-process sandbox, still deferred), ADR-0020 (authored decks + media library), ADR-0007 (persistence), ADR-0011 (observability/redaction)
- Design: `docs/architecture/IMPORT-presentation-design.md`
- Security: `docs/security/THREAT-MODEL-presentation-import.md` (blockers B1–B4 are merge gates)
- Requirements: PRD FR-138 (safe import), FR-173 (decode hardening), FR-070 (never blank), NFR-003 (memory), NFR-027 (SBOM/licence)
- ClickUp: none yet — no task covers presentation import (searched 2026-08-15). Epic and stories are Priya's and Diego's.

---

## Context

The owner approved importing a presentation into the deck library from three sources: a `.txt` file, a `.pptx` file, and pasted text. For `.pptx` the approved fidelity is **text plus images** — per-slide title and body text, speaker notes, and embedded images placed as image elements — with no attempt at layout, font or colour mapping, because imported decks adopt the SelahCue theme. Slides in text sources are separated by a blank line. Partial import is the model: import what is representable and report what was dropped.

This is the first untrusted **binary** input SelahCue has ever parsed. Everything the product parses today is either operator-typed text (`selahcue-core::scripture`), a byte-pinned wire message from a paired peer (`selahcue-lan`), or a still image handed to a single bounded decoder (`selahcue-engine::media`). A `.pptx` is a ZIP of OOXML parts plus media — three nested untrusted formats, delivered by the most plausible attacker path this product has: a volunteer downloading a deck from the internet and importing it.

Three properties of the existing tree shape the decision:

1. **`selahcue-operator` is excluded from the cargo workspace.** `cargo test --workspace` does not reach it; CI compile-checks it and runs a headless WebView script. Code placed there is effectively untested.
2. **The deck library is operator-owned and operator-local.** The host is deck-blind by design, and no LAN command touches the library. Any import must commit through `DeckLibrary`, which lives in the excluded crate.
3. **There is no ZIP or XML dependency anywhere in the tree**, and there is an SBOM and licence-scanning gate. Choosing one is a real decision with a compliance dimension, not a detail.

---

## Decisions

### 1. The transform lives in a new pure workspace crate, `selahcue-import`

Bytes in, a `SlideDeck` and an `ImportReport` out. No `std::fs`, no `std::net`, no clipboard, no database, no `unsafe`, deterministic. It depends on `selahcue-present` (for `SlideDeck`, `AuthoredSlide`, `theme::Element`, `RegionStyle`) and transitively on `selahcue-engine` for `MediaRef` and the decode seam. Nothing below it gains a dependency.

The crate additionally denies `clippy::unwrap_used`, `expect_used`, `panic`, `todo` and `unimplemented`, and — on the three modules that parse binary offsets — `clippy::indexing_slicing` and `clippy::arithmetic_side_effects`, which force `checked_add`, `checked_sub` and `slice::get` exactly where `off + len` overflow is the classic bug.

### 2. The seam between parsing and I/O is three injected effects

`trait ByteSource` (bounded random-access reads over the chosen file), `trait MediaSink` (stage validated image bytes, return a slot), and a slot resolver supplied after the media commit. This is the pattern the codebase already uses to keep pure layers pure — `MediaLibrary::missing(|path| …)` takes an existence probe, and `plan::unresolved_content(deck_exists, media_exists)` does the same.

The operator shell may open a dialog, read a file, stage and commit media, call `DeckLibrary`, run the timeout, the import lock and the `catch_unwind` belt, and serialise the report. It may **not** know a file format, parse anything, compute or enforce a content limit, branch on file content, or construct an `Element`. A `match` on a byte in `main.rs` means the seam has been violated.

### 3. ZIP is hand-rolled over `flate2`; XML takes `quick-xml`

Two different answers, and the asymmetry is the point.

**ZIP: a ~350-line central-directory reader over `flate2`**, which is already a direct first-party dependency (`selahcue-scripture`). The ZIP capability adds **no new crate to the SBOM**. The job is narrow and stable — locate the end-of-central-directory record, walk the directory, stream one named entry through an inflater with a hard output cap. Critically, the security constraint set forbids the very API a general-purpose ZIP crate exists to provide: no extract-to-directory helper may be used, because several honour symlinks, and entry types, mode bits and link targets must be ignored entirely. Every other control we need — entry-count cap, actual-byte caps, ratio guard, method allowlist, encrypted-entry and ZIP64 refusal, duplicate-name handling, cancellation inside the inflate loop — is ours regardless. The dependency would buy only format decoding while adding AES and ZipCrypto decryption, bzip2 and zstd back-ends, deflate64 and permission emulation, all of which we would carry under the SBOM gate and never call.

**XML: `quick-xml`, pinned, no optional features.** XML is the opposite kind of problem — namespaces, prefix rebinding, entities, CDATA, character references, encoding declarations — and hand-rolling a parser for adversarial XML is how you get billion-laughs and XXE. `quick-xml` is MIT, pure Rust, actively maintained, and pull-based, so memory is bounded by construction and no DOM is built. `roxmltree` was rejected for building a DOM sized by untrusted input; `xml-rs` for being slower and less maintained with no compensating advantage.

**Caps are enforced on actual inflated bytes, never on declared ones.** ZIP headers can lie in both directions, so the declared size and ratio are used only as a cheap early abort; the streaming counter is the guarantee.

### 4. Extracted media is staged and committed atomically

Images are decoded and validated in the pure crate, then staged under a shell-generated name in `<app_data>/media/.staging/<import-id>/`. On success the staged files are renamed into `<app_data>/media/` under names claimed with `create_new`, registered with `MediaLibrary`, and only then is the deck built and adopted. Failure, cancellation or timeout removes the staging directory and leaves the library, the media store and live state byte-identical; a staging directory found at launch is swept.

**No filesystem path is ever derived from archive content.** Relationship targets are normalised entirely within the package namespace and used only as a lookup key into the archive's own entry set — never joined to a directory. Zip-slip is therefore structurally absent rather than defended against.

### 5. Import-time name collision becomes an explicit caller policy, and `Replace` preserves `DeckId`

`DeckLibrary::adopt_with_policy(deck, NameCollisionPolicy)` is added; `adopt()` keeps its current silent-uniquify behaviour by delegating with `KeepBoth`, so no existing caller changes. Import always passes an explicit policy.

`Replace` **must** update the existing deck in place, keeping its `DeckId`. Implementing it as delete-then-insert, or as an upsert on the name, would overwrite the row of a different `DeckId` while the in-memory library still held the old id — and every `PlanItem` linking that id would resolve to nothing or to an unrelated deck. `Replace` is also refused while the target deck is live or staged.

Which policy is the default, and whether `Replace` ships at all, are product decisions and are routed, not decided here.

---

### 6. Two whole-archive budgets, because expansion and work are different risks (remediation round 2)

`MAX_TOTAL_INFLATED_BYTES` (256 MiB) counted STORED members as well as inflated ones, and a stored
member is an already-compressed photograph copied out byte for byte. It expands by nothing, so it
cannot be a bomb, and its total is bounded by the file the shell already admitted — yet a legitimate
278 MiB photo deck was refused wholesale, zero slides in 0.54 s, while a 242 MiB one passed with
14 MiB to spare.

The budget therefore splits in two, along the line that actually separates the risks:

- **`MAX_TOTAL_INFLATED_BYTES` (256 MiB)** charges DEFLATE output only. It is the bomb bound, and
  breaching it still **aborts** the import: past it nothing further in the file can be trusted to
  be proportionate.
- **`MAX_TOTAL_EXTRACTED_BYTES` (768 MiB = the 512 MiB admission cap plus the inflate cap)** charges
  every produced byte, copied or inflated. It bounds WORK rather than expansion, because ZIP
  central-directory records may share a local offset and an archive can therefore ask to be read
  many times its own size. Breaching it **degrades**: the slides' text imports, every image that
  did not fit is reported as `MediaBudgetExhausted`, and the operator gets their words. Aborting
  there would contradict the partial-import rule every other failure in the crate keeps.

### 7. Placeholder type decides body text too, not only the title (remediation round 2)

`assemble_text` treated every non-title shape as body without consulting `<p:ph type>`. Measured
across seven genuinely PowerPoint-authored decks: **124 `sldNum` placeholders carrying text plus 5
`ftr`**, about one per slide, so a real slide imported as `2026 Market Report | 2 | The market is
moving from…` — the footer and the page number on the audience screen. Slide numbers, footers,
dates and notes-page headers are page furniture: a design attribute SelahCue replaces on purpose,
so they are dropped **and not reported**, exactly like transitions and colours. The predicate is
shared with the notes path, which already filtered `sldNum` — the two rules had drifted precisely
because there were two.

Embedded fonts move from a skipped item per file to **one standing notice** for the same reason: a
real deck carried 25 of them and itemising each consumed a quarter of the whole report budget.

## Options considered

**Crate placement.**

- *(Chosen) A new pure workspace crate.* Pros: `cargo test --workspace` and `cargo-fuzz` both reach it; the security constraint "the importer's dependency graph contains no network crate" becomes a one-line CI assertion, which is unstateable inside the operator whose graph legitimately contains a network stack; it matches the existing precedent of a total, panic-free parser in a workspace crate. Cons: the collision and persistence logic unavoidably stays in the excluded operator crate, so the seam has to be drawn tightly enough that the remainder is reviewable by eye.
- *Everything in `selahcue-operator`.* Rejected: the code that most needs exhaustive hostile-input tests would sit where tests do not run.
- *The build step in `selahcue-present`.* Rejected: it would give the presentation layer an import surface and split one coherent transform across two crates for no coverage gain.

**ZIP.**

- *(Chosen) Hand-rolled over `flate2`.* Pros: no new SBOM entry; the forbidden extract-to-directory API cannot be called because it does not exist; every hostile-input control is in code we own and test; `Read`-based inflate gives an exact output bound. Cons: we own our format bugs, and a malformed-but-common archive we mis-read is our defect. Mitigated by the negative-path battery, a fuzz target, and an internal `Archive` trait so swapping to the `zip` crate later is a single-module change.
- *The `zip` crate.* Rejected for this job: its convenience APIs are contractually unusable here, its default feature set pulls codec back-ends we never use into an audited dependency graph, and it does not remove a single control we must write.

**XML.**

- *(Chosen) `quick-xml`.* Pull-based, bounded, maintained, MIT.
- *`roxmltree`.* Rejected: a DOM sized by untrusted input.
- *Hand-rolled.* Rejected: XML is wide and adversarial; this is the case where the dependency is the safer choice, and saying so plainly is the point of the asymmetry.

---

## Consequences

**Positive.** The transform is covered by `cargo test --workspace` and is fuzzable; the "no network, no filesystem" properties become structural CI assertions rather than review discipline; zip-slip is impossible by construction rather than defended; the ZIP capability costs nothing in the SBOM and the XML capability costs one pure-Rust MIT crate; the media store gains atomic commit, which the tree did not previously have anywhere; and `adopt_with_policy` closes a plan-link corruption path that a UI-level "Replace" would otherwise have opened.

**Negative / watch.** We own ZIP format bugs, with a documented escape hatch. A new pure-Rust XML dependency enters the SBOM and licence gate (NFR-027) and must be pinned. The importer's peak working set is ~170 MiB transient, which is bounded and documented but wants confirmation against NFR-003's measurement method. Some import logic — the collision policy, staging commit, the timeout and the `catch_unwind` belt — necessarily lives in the CI-uncovered operator crate; the seam is what keeps that surface small, and the operator headless check carries the assertions that can be automated. The decoder remains in-process (ADR-0018), and this feature makes internet-downloaded files a routine input to it, which strengthens the case for re-prioritising the ADR-0016 worker.

**Deliberate non-goals.** pptx layout, fonts, colours, animations and masters; embedded video and audio; formats other than PNG and JPEG; deck export; plan-bundle import (FR-139); FR-138's canonicalisation for user-chosen paths, which this design neither depends on nor discharges; and automatic garbage collection of orphaned media.

## References

PRD: FR-070, FR-138, FR-139, FR-173, NFR-003, NFR-014, NFR-027. ADRs: 0007, 0011, 0016, **0018**, 0020, **0025**. Design: `docs/architecture/IMPORT-presentation-design.md`. Security: `docs/security/THREAT-MODEL-presentation-import.md`. Domain: `docs/product/DOMAIN-library-organisation.md` (`FINDING-LIB-05`, `FINDING-LIB-07`, `RULE-LIB-MIG-03`). Goal: `docs/delivery/goals/GOAL-arch-presentation-import.md`.
