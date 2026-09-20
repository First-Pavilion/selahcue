//! Providers & Privacy domain: where transcription and AI sermon-notes run, and
//! what — if anything — leaves the device (R3; FR-131/132/135/137, NFR-018, CON-5).
//!
//! This module is **pure, deterministic, no I/O** — like the rest of the core it
//! reads no clock, opens no socket, and never panics on untrusted input
//! (`from_kv` tolerates missing/garbage values by falling back to the safe
//! default). It owns three things:
//!
//! 1. The **settings** an operator chooses ([`ProvidersSettings`]) and the
//!    **consent** state that ungates cloud egress ([`ConsentState`]), bundled as
//!    [`ProvidersConfig`] with a `(key, value)` persistence mapping (the repo layer
//!    stores those pairs exactly like `saved_theme_repo`).
//! 2. The **privacy invariants** as testable pure functions:
//!    [`ProvidersConfig::may_stream_cloud_audio`] and
//!    [`ProvidersConfig::build_note_request`] — the single choke points that decide
//!    whether anything may leave the device. **Offline by default**: cloud is OFF
//!    until a per-provider opt-in is set, and a note request is only ever built on
//!    an explicit Generate and only ever carries the *completed transcript text* —
//!    there is no audio field, so live audio can never be sent (FR-132: "only your
//!    completed transcript … never live audio").
//! 3. The [`NoteProvider`] seam (parallel to [`crate::transcript::TranscriptProvider`])
//!    behind which the SelahCue-hosted cloud client — or a local fallback — plugs in
//!    without the core depending on any network runtime.

/// Where live transcription runs. Default is [`TranscriptionMode::OnDevice`]
/// (Whisper, offline — audio never leaves the machine, FR-101).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum TranscriptionMode {
    /// On-device Whisper. Private; works offline; the always-safe default.
    #[default]
    OnDevice,
    /// A cloud speech service. Streams live microphone audio while active, so it is
    /// gated behind [`ConsentState::cloud_transcription`] and only ever effective
    /// when that opt-in is set (see [`ProvidersConfig::may_stream_cloud_audio`]).
    Cloud,
}

impl TranscriptionMode {
    pub fn as_str(self) -> &'static str {
        match self {
            TranscriptionMode::OnDevice => "on_device",
            TranscriptionMode::Cloud => "cloud",
        }
    }

    /// Parse, tolerating anything unknown by returning the safe default (never panics).
    pub fn parse(s: &str) -> Self {
        match s {
            "cloud" => TranscriptionMode::Cloud,
            _ => TranscriptionMode::OnDevice,
        }
    }
}

/// The sermon-notes template an operator prefers. Open set kept small and typed so
/// the value round-trips through persistence and the cloud contract deterministically.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum NotesTemplate {
    /// Full outline with in-line scripture references (the design default).
    #[default]
    FullOutlineWithScriptures,
    /// Full outline without scriptures interleaved.
    FullOutline,
    /// A concise summary only.
    Summary,
    /// A short devotional treatment.
    Devotional,
}

impl NotesTemplate {
    /// Every variant (stable order) — for populating a picker.
    pub const ALL: [NotesTemplate; 4] = [
        NotesTemplate::FullOutlineWithScriptures,
        NotesTemplate::FullOutline,
        NotesTemplate::Summary,
        NotesTemplate::Devotional,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            NotesTemplate::FullOutlineWithScriptures => "full_outline_scriptures",
            NotesTemplate::FullOutline => "full_outline",
            NotesTemplate::Summary => "summary",
            NotesTemplate::Devotional => "devotional",
        }
    }

    /// A human-readable label (matches the design copy).
    pub fn label(self) -> &'static str {
        match self {
            NotesTemplate::FullOutlineWithScriptures => "Full outline + scriptures",
            NotesTemplate::FullOutline => "Full outline",
            NotesTemplate::Summary => "Summary",
            NotesTemplate::Devotional => "Devotional",
        }
    }

    /// Parse, tolerating unknown values by returning the default (never panics).
    pub fn parse(s: &str) -> Self {
        match s {
            "full_outline" => NotesTemplate::FullOutline,
            "summary" => NotesTemplate::Summary,
            "devotional" => NotesTemplate::Devotional,
            _ => NotesTemplate::FullOutlineWithScriptures,
        }
    }
}

/// Upper bound on the stored translation code — a short code like `KJV`/`WEBBE`.
/// Bounds a wire-legal but absurd value (no unbounded memory via settings).
pub const MAX_TRANSLATION_CODE_LEN: usize = 16;

/// Which sections the AI sermon notes should include. Defaults match the design
/// (social excerpts, podcast show notes and short description OFF by default; the
/// rest ON).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct IncludeInNotes {
    pub prayer_points: bool,
    pub scripture_extraction: bool,
    pub social_excerpts: bool,
    pub chapter_markers: bool,
    pub notable_quotations: bool,
    pub short_summary: bool,
    /// Ready-to-publish podcast show-notes copy (FR-126) — a blurb, key discussion
    /// points and scripture referenced. Distinct in shape from the full outline and
    /// from `short_summary` (a fuller paragraph): this is publish-ready listing copy.
    /// OFF by default, matching `social_excerpts`'s precedent for a secondary,
    /// publishing-oriented artifact rather than a core note.
    pub podcast_show_notes: bool,
    /// A one-to-two sentence description suitable for a listing/thumbnail caption
    /// (FR-126) — distinct from `short_summary`, which is a fuller paragraph-level
    /// summary. OFF by default, same reasoning as `podcast_show_notes`.
    pub short_description: bool,
}

impl Default for IncludeInNotes {
    fn default() -> Self {
        IncludeInNotes {
            prayer_points: true,
            scripture_extraction: true,
            social_excerpts: false,
            chapter_markers: true,
            notable_quotations: true,
            short_summary: true,
            podcast_show_notes: false,
            short_description: false,
        }
    }
}

/// Operator-chosen Providers & Privacy settings (no consent here — consent lives in
/// [`ConsentState`] so the egress gate reads only from one place).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProvidersSettings {
    pub transcription_mode: TranscriptionMode,
    pub notes_template: NotesTemplate,
    /// Preferred Bible translation code (e.g. `"KJV"`); validated for length here and
    /// against the installed translation set by the caller.
    pub preferred_translation: String,
    pub include: IncludeInNotes,
}

impl Default for ProvidersSettings {
    fn default() -> Self {
        ProvidersSettings {
            transcription_mode: TranscriptionMode::default(),
            notes_template: NotesTemplate::default(),
            // KJV matches the shipped `selahcue-scripture` default and the design.
            preferred_translation: "KJV".to_string(),
            include: IncludeInNotes::default(),
        }
    }
}

/// Per-provider cloud opt-in. **Everything defaults to `false`** — the app is offline
/// by default and no audio/transcript/notes leave the host until one of these is set
/// (CON-5, FR-132, NFR-018). Changing consent is Administrator-gated at the command
/// layer (FR-137); this struct is the persisted truth the egress gate reads.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct ConsentState {
    /// Opt-in to streaming live microphone audio to a cloud speech service.
    pub cloud_transcription: bool,
    /// Opt-in to sending the completed transcript to the SelahCue cloud for notes.
    pub cloud_notes: bool,
}

impl ConsentState {
    /// True when *any* cloud egress is permitted — drives the "cloud active" style
    /// disclosure. When false the app is fully offline.
    pub fn any_cloud_enabled(self) -> bool {
        self.cloud_transcription || self.cloud_notes
    }
}

/// Options carried on a note-generation request — derived purely from settings.
/// Deliberately contains no audio and no secrets.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NoteOptions {
    pub template: NotesTemplate,
    pub preferred_translation: String,
    pub include: IncludeInNotes,
}

impl NoteOptions {
    pub fn from_settings(s: &ProvidersSettings) -> Self {
        NoteOptions {
            template: s.notes_template,
            preferred_translation: s.preferred_translation.clone(),
            include: s.include,
        }
    }
}

/// A note-generation request. **Carries only the completed transcript text** — there
/// is no audio field by construction, so live audio can never be sent (FR-132). Built
/// only by [`ProvidersConfig::build_note_request`], only on an explicit Generate, and
/// only once cloud-notes consent is set.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NoteRequest {
    /// The operator's completed transcript (post-service), never live audio.
    pub transcript: String,
    pub options: NoteOptions,
}

/// Upper bound on how deep a sermon outline may nest. FR-122 asks for "points/
/// sub-points" — exactly two levels — so the type provides exactly two levels and
/// nothing deeper. See [`NotePoint`] for why this is a constant and not a recursion.
pub const NOTE_OUTLINE_DEPTH: usize = 2;

/// One point of a sermon outline, together with its subordinate sub-points (FR-122).
///
/// **Deliberately one level of nesting, not a recursive tree.** FR-122 requires
/// "points/sub-points" and nothing deeper, and a recursive `children: Vec<NotePoint>`
/// would let an untrusted provider response nest without bound — an unbounded-memory
/// hole opened to satisfy a requirement that never asked for it. Two levels is the
/// requirement, so two levels is the type, and the bound is structural rather than a
/// runtime check somebody can forget.
///
/// The alternative — flattening sub-points into the parent's `items` with an indent
/// prefix — was rejected: it makes subordination a rendering convention rather than a
/// fact, so nothing downstream can tell a sub-point from a point, and no test can
/// assert the hierarchy the requirement is about.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct NotePoint {
    /// The point itself.
    pub text: String,
    /// Its sub-points, subordinate to `text`. Empty for a point with no sub-points.
    pub sub_points: Vec<String>,
}

/// One structured section of a generated sermon-note draft.
///
/// A section is **either** a flat list (illustrations, quotes, prayer points, key
/// lessons — no internal hierarchy) **or** a hierarchical outline (the sermon's points,
/// where sub-points are subordinate to their parent, FR-122). Never both, and never
/// neither-but-shaped-like-both.
///
/// # Why the fields are private
///
/// "Exactly one of these is populated" is an invariant, and an invariant that depends on
/// every future caller remembering it is not an invariant — it is a convention with a
/// countdown. With `items` and `points` public, a section holding both would be
/// constructible, and the renderer on the other side of the wire is a webview that will
/// draw whatever it is handed: it would cheerfully print the same content twice, once
/// flat and once nested.
///
/// So the fields are private and the only ways in are [`NoteSection::flat`] and
/// [`NoteSection::outline`], each of which populates one and empties the other. The
/// illegal state is not tested for; it cannot be built. Read them back with
/// [`NoteSection::items`] and [`NoteSection::points`].
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct NoteSection {
    pub heading: String,
    /// Flat list entries. **Private**, with `points`, so the two cannot both be
    /// populated — see the type docs.
    items: Vec<String>,
    /// Hierarchical outline points. **Private**, with `items`.
    points: Vec<NotePoint>,
}

impl NoteSection {
    /// A flat section — the shape the offline scaffold and the hosted contract produce.
    pub fn flat(heading: impl Into<String>, items: Vec<String>) -> Self {
        NoteSection {
            heading: heading.into(),
            items,
            points: Vec::new(),
        }
    }

    /// A hierarchical outline section (FR-122 points/sub-points).
    pub fn outline(heading: impl Into<String>, points: Vec<NotePoint>) -> Self {
        NoteSection {
            heading: heading.into(),
            items: Vec::new(),
            points,
        }
    }

    /// The flat entries; empty for an outline section.
    pub fn items(&self) -> &[String] {
        &self.items
    }

    /// The outline points; empty for a flat section.
    pub fn points(&self) -> &[NotePoint] {
        &self.points
    }

    /// True when this section carries hierarchy rather than a flat list.
    pub fn is_outline(&self) -> bool {
        !self.points.is_empty()
    }

    /// Total sub-points across every point — the cheap way for a caller to ask whether
    /// any hierarchy actually survived, without walking the structure itself.
    pub fn sub_point_count(&self) -> usize {
        self.points.iter().map(|p| p.sub_points.len()).sum()
    }
}

/// A caveat attached to part of a generated draft — something the operator should not
/// take on trust without a second look, carried on [`NoteDraft`] so the console and any
/// later export read the same verdict rather than each computing their own.
///
/// Every variant answers the same question about a different part of the draft: "you
/// asked for this; here is why what you got (or didn't get) is not settled." Rendering
/// them together, in one unmissable place, is what keeps two related but independently
/// built checks (86akc0tua's requested-but-empty reporting, 86akby820's scripture
/// verification) from inventing two different vocabularies for the same kind of
/// statement — Cody's review of PR #19 flagged exactly that risk before either existed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DraftCaveat {
    /// A section the operator explicitly requested (an enabled `IncludeInNotes` flag, or
    /// one of the handful of sections FR-122 always asks for) came back with no content
    /// at all (86akc0tua). Distinct from a section the operator left off, which stays
    /// silently absent, and never raised for a degraded/offline draft — the offline
    /// scaffold already carries its own [`DEGRADED_FALLBACK_NOTICE`] and must not repeat
    /// the same fact in a second, contradictory-sounding voice.
    ///
    /// `heading` matches the heading that would have appeared had the section returned
    /// content, or a fixed label for the two fields that are not sections at all
    /// (`"Summary"`, `"Scripture references"`) so the console can render one uniform
    /// list regardless of which kind of "requested" it was.
    SectionRequestedEmpty { heading: String },
    /// A scripture reference in this draft — in the extracted `scriptures` list, or
    /// embedded in a section's body text — did not resolve to any verse in the bundled
    /// Bible text (86akby820; FR-125/FR-128). Covers a wrong book, a chapter past a real
    /// book's end, a verse past a real chapter's end, AND a reference that could not be
    /// parsed at all — the parser's own silent-drop behaviour is exactly what this ticket
    /// exists to stop happening at this layer.
    ///
    /// Confirms only that the address does not exist; it says nothing about whether any
    /// words the draft attributes to it are accurate; that is a different, unchecked
    /// claim (see `SCRIPTURE_VERIFICATION_WORDING`).
    ScriptureUnverified {
        /// The reference exactly as it appeared in the draft — an unparseable string is
        /// kept verbatim, since there is no canonical form to normalise it to.
        reference: String,
    },
    /// The embedded-scripture-reference scan (body text of sections, as opposed to the
    /// extracted `scriptures` list) hit [`MAX_EMBEDDED_REFERENCES`] before every section
    /// had been scanned (86akgqdwc, Sana's F2 finding on this ticket's own security
    /// review). Names no section and no reference: it is a draft-wide statement that
    /// [`verify_scriptures`] stopped early, so a reference in one of the LATER sections
    /// (by [`crate::providers::NoteDraft::sections`] order) may carry no verdict at all —
    /// not even an `Unverified` mark — purely because the budget ran out before reaching
    /// it. Distinct from [`ScriptureUnverified`](DraftCaveat::ScriptureUnverified), which
    /// means a specific reference WAS checked and failed; this means some references were
    /// never checked in the first place. The two new artifacts 86akgqdwc added
    /// (`podcast_show_notes`, `short_description`) sit last in scan order and are
    /// therefore structurally the most exposed to this — the exact reason the finding
    /// surfaced on this ticket rather than an earlier one.
    ScriptureVerificationIncomplete,
}

/// The address-only scope of scripture verification, stated once so every place that
/// renders a verdict says the same true thing (86akby820; FR-125). This check confirms a
/// reference resolves to real verses in the bundled text; it never reads what the draft
/// claims those verses say, so it cannot and does not vouch for a quotation's accuracy.
pub const SCRIPTURE_VERIFICATION_WORDING: &str =
    "Verified means the reference address exists in the bundled Bible text — it does not \
     confirm that any words this draft attributes to it are accurate. Always check a \
     quotation against the actual text before you use it.";

/// One scripture reference found anywhere in a draft, and whether it resolves to real
/// verses in the bundled Bible text (86akby820; FR-125/FR-128).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScriptureVerdict {
    /// The reference exactly as the caller supplied it (trimmed), whether or not it
    /// parsed — NEVER re-serialised through `Reference::to_string()`. Security review
    /// finding (Sana F1 on PR #47): an earlier version canonicalised a successfully-
    /// parsed reference, which silently broke the exact-string match a console uses to
    /// attach this verdict to a `scriptures` list entry, since the parser accepts
    /// abbreviations the model may have written instead of the canonical spelling.
    pub reference: String,
    /// True when the reference parsed AND resolved to at least one verse. False for
    /// EITHER an unparseable reference OR one that parses but is outside the canon
    /// (wrong book, chapter past the book's end, verse past the chapter's end) — both are
    /// "unverified", never dropped, never an error.
    pub verified: bool,
}

/// Upper bound on scripture references verified from the extracted `scriptures` list.
/// Set well above every upstream cap this crate is aware of
/// (`selahcue-cloud::openai::MAX_SCRIPTURES = 128` at review time) — this crate cannot
/// import that constant directly (the dependency runs the other way), so the margin here
/// is deliberate insurance, not a tight fit. This must never be the reason a real list
/// entry goes unchecked: an entry beyond this cap would render identically to a verified
/// one, which is precisely Sana's F2 finding on PR #47.
pub const MAX_LIST_REFERENCES: usize = 256;

/// Upper bound on scripture references found by scanning section body text (flat items,
/// outline point text, sub-point text). This bound stays tight: unlike the extracted
/// list (bounded upstream to a small, deliberate count), body text is bounded only by
/// character count, and a hostile draft could cram many reference-shaped substrings into
/// it — this is the genuinely adversarial-input-prone half of this function.
pub const MAX_EMBEDDED_REFERENCES: usize = 64;

/// Verify every scripture reference in a draft — the extracted `scriptures` list AND
/// references embedded in a section's body text (flat items, outline point text, and
/// sub-point text) — against `exists`, an injected lookup so this function stays testable
/// with a stub oracle and has no dependency on `selahcue-scripture` (which depends on this
/// crate, not the other way round; the real caller wires `exists` to
/// `|r| !selahcue_scripture::verses(r).is_empty()`).
///
/// `ScriptureVerdict::reference` is always the CALLER's own string, verbatim (trimmed) —
/// never re-serialised through `Reference::to_string()`. Security review finding (Sana,
/// F1 on PR #47): the parser accepts aliases (`"Obad"`, `"3jn"`, the space-shorthand
/// form, …), so re-serialising a successfully-parsed reference to its canonical form
/// silently broke the exact-string match the console uses to attach a verdict to a
/// `scriptures` list entry — an abbreviated fabricated reference parsed fine, verified
/// `false`, and then rendered with NO mark at all, because the console was looking for
/// the canonical spelling, not the one actually in the list. Echoing the input back
/// verbatim makes that match reliable by construction rather than by convention.
///
/// Bounded and total: never panics on adversarial input. The list is capped at
/// [`MAX_LIST_REFERENCES`], embedded-text scanning separately at
/// [`MAX_EMBEDDED_REFERENCES`] (see each constant's doc for why they differ). A reference
/// that cannot be parsed at all is retained as unverified, never silently dropped (unlike
/// [`crate::scripture::parse`], which is the wrong entry point here for exactly that
/// reason). Duplicate reference text (by exact string, shared across both phases) is
/// verified once; a fabricated reference repeated ten times in one draft is reported
/// once, not ten times.
///
/// Returns the verdicts AND a second value: `true` iff the embedded-text scan hit
/// [`MAX_EMBEDDED_REFERENCES`] before every section had been considered (86akgqdwc, Sana's
/// F2 finding). `MAX_LIST_REFERENCES` is deliberately set above every known upstream cap
/// and so is not expected to truncate in practice (see its own doc comment) — only the
/// embedded-text budget is reported here. The caller turns a `true` into
/// [`DraftCaveat::ScriptureVerificationIncomplete`] so a reference in a section past the
/// budget reads as "not checked", never as silently clean.
pub fn verify_scriptures(
    scriptures: &[String],
    sections: &[NoteSection],
    mut exists: impl FnMut(&crate::scripture::Reference) -> bool,
) -> (Vec<ScriptureVerdict>, bool) {
    let mut verdicts = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut embedded_truncated = false;

    // Returns `true` iff a NEW verdict was pushed — the caller's own cap counter only
    // advances on an actual push, so a run of duplicates never eats into either budget.
    let mut consider = |raw: &str,
                        verdicts: &mut Vec<ScriptureVerdict>,
                        seen: &mut std::collections::HashSet<String>|
     -> bool {
        let raw = raw.trim();
        if raw.is_empty() || !seen.insert(raw.to_string()) {
            return false;
        }
        let verified = crate::scripture::parse_one(raw)
            .map(|reference| exists(&reference))
            .unwrap_or(false);
        verdicts.push(ScriptureVerdict {
            reference: raw.to_string(),
            verified,
        });
        true
    };

    let mut list_count = 0usize;
    for raw in scriptures {
        if list_count >= MAX_LIST_REFERENCES {
            break;
        }
        if consider(raw, &mut verdicts, &mut seen) {
            list_count += 1;
        }
    }

    let mut embedded_count = 0usize;
    'sections: for section in sections {
        for item in section.items() {
            if embedded_count >= MAX_EMBEDDED_REFERENCES {
                embedded_truncated = true;
                break 'sections;
            }
            for candidate in crate::detection::detect(item) {
                if embedded_count >= MAX_EMBEDDED_REFERENCES {
                    embedded_truncated = true;
                    break 'sections;
                }
                if consider(&candidate, &mut verdicts, &mut seen) {
                    embedded_count += 1;
                }
            }
        }
        for point in section.points() {
            if embedded_count >= MAX_EMBEDDED_REFERENCES {
                embedded_truncated = true;
                break 'sections;
            }
            for candidate in crate::detection::detect(&point.text) {
                if embedded_count >= MAX_EMBEDDED_REFERENCES {
                    embedded_truncated = true;
                    break 'sections;
                }
                if consider(&candidate, &mut verdicts, &mut seen) {
                    embedded_count += 1;
                }
            }
            for sub in &point.sub_points {
                if embedded_count >= MAX_EMBEDDED_REFERENCES {
                    embedded_truncated = true;
                    break 'sections;
                }
                for candidate in crate::detection::detect(sub) {
                    if embedded_count >= MAX_EMBEDDED_REFERENCES {
                        embedded_truncated = true;
                        break 'sections;
                    }
                    if consider(&candidate, &mut verdicts, &mut seen) {
                        embedded_count += 1;
                    }
                }
            }
        }
    }

    (verdicts, embedded_truncated)
}

// ---------------------------------------------------------------------------
// Timestamp linking (86akgqdw0; FR-124)
// ---------------------------------------------------------------------------

/// The heading of FR-122's chapter-marker section (gated by
/// [`IncludeInNotes::chapter_markers`]) — the single definition
/// [`link_timestamps`] matches against. `selahcue_cloud::openai`'s `FLAT_SECTIONS` table
/// reads this constant instead of its own string literal, so "which heading means chapter
/// markers" cannot drift between the two crates.
pub const CHAPTER_MARKERS_HEADING: &str = "Chapter markers";

/// The heading of FR-122's one hierarchical section (points/sub-points). Promoted here from
/// `selahcue_cloud::openai::OUTLINE_HEADING` (which now re-exports this constant) so
/// [`link_timestamps`] — which lives in this crate and cannot depend on `selahcue-cloud`,
/// the dependency runs the other way — has a single definition to match against too.
pub const OUTLINE_HEADING: &str = "Main points";

/// A transcript timestamp linked to one note item — a chapter marker (always attempted) or,
/// where a confident match exists, a top-level outline point (best-effort only; no
/// sub-points) — attached AFTER generation by matching the item's own text against the
/// transcript's real segments. See [`link_timestamps`].
///
/// Matched to its item by VALUE (`heading` + the item's own exact `text`), the same pattern
/// [`ScriptureVerdict`] uses against `scriptures`/section body text, and for the same
/// reason: a console reading this list back does not need it to stay in lockstep by
/// position with `NoteDraft::sections`, and (like `scripture_verdicts`) a duplicate item
/// text within one section carries one shared timestamp rather than a second entry nothing
/// could distinguish it from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NoteTimestamp {
    /// The heading of the section this item belongs to — currently only
    /// [`CHAPTER_MARKERS_HEADING`] or [`OUTLINE_HEADING`] ever produce one.
    pub heading: String,
    /// The note item's own text, exactly as it appears in the section — the join key.
    pub text: String,
    /// Offset from the recording's start, in milliseconds. **Never a model estimate**: this
    /// is always either a real transcript segment's own `start_ms`, or (chapter markers
    /// only, only when no segment shares any significant word with the marker at all) a
    /// position interpolated between two real segments' timestamps — see
    /// [`link_timestamps`]'s "Positional fallback" section. Bounded by
    /// [`MAX_PLAUSIBLE_OFFSET_MS`].
    pub offset_ms: u64,
}

/// Upper bound on transcript segments considered by one [`link_timestamps`] call —
/// independent of any upstream count, since a STORED transcript's segments are explicitly
/// UNCAPPED (`selahcue_data::transcript_repo`'s own reason to exist: see that module's doc
/// comment). A segment past this bound is simply unreachable as a match target; never a
/// crash, never unbounded work.
pub const MAX_LINK_SEGMENTS: usize = 5_000;

/// A segment whose own `start_ms` sits at or past this bound is treated as corrupt, not
/// merely long — no realistic single continuous recording comes anywhere close to half a
/// day, so a value this large can only be an upstream defect (most plausibly a
/// negative-to-`u64` wraparound reading a damaged store row). Excluded from matching and
/// from the positional fallback's span entirely: never clamped into range, never permitted
/// to win a match or anchor a fallback by default. This is the bound that keeps a malformed
/// stored segment from ever reaching the console as a "nonsensical jump target" (this
/// ticket's own adversarial-fixture acceptance criterion).
pub const MAX_PLAUSIBLE_OFFSET_MS: u64 = 12 * 60 * 60 * 1000; // 12h

/// Items considered per section, per [`link_timestamps`] call — bounds the
/// O(items x segments) matching cost independent of whatever the caller's own section/point
/// counts happen to be. This crate cannot assume every caller already respects
/// `selahcue_cloud::openai`'s own, tighter caps (`MAX_SECTION_ITEMS`/`MAX_POINTS`) — a
/// degraded/local draft or a hand-built test is not bound by them at all.
pub const MAX_LINK_ITEMS: usize = 128;

// The premises the bounded-input tests in `tests/test_note_timestamps.rs` rest on, pinned
// at COMPILE time — the same discipline `selahcue_cloud::openai` already uses for its own
// caps (see that module's `const _: () = assert!(...)` block).
const _: () = assert!(
    MAX_LINK_SEGMENTS < 50_000,
    "test_note_timestamps feeds MAX_LINK_SEGMENTS + 1 segments to prove the scan cap bites; \
     raising this past 50_000 makes that test far too slow to run routinely"
);
const _: () = assert!(
    MAX_LINK_ITEMS < 1_000,
    "test_note_timestamps feeds MAX_LINK_ITEMS + 1 items to prove the item cap bites"
);

/// A small, hand-picked set of very common English connective words excluded from
/// timestamp-matching scoring, so a marker text of mostly connective words does not
/// spuriously "match" every segment that merely contains "the". Deliberately short — good
/// enough for the coarse containment score [`overlap_score`] computes, not a claim of
/// linguistic completeness.
const STOPWORDS: &[&str] = &[
    "the", "and", "for", "that", "this", "with", "from", "have", "your", "our", "his", "her",
    "she", "they", "them", "but", "not", "into", "who", "what", "when", "where", "was", "were",
    "are", "you", "all", "one", "out", "now", "then", "than", "will",
];

/// Lowercase alphanumeric-run tokens of at least 3 characters, minus [`STOPWORDS`] — the
/// vocabulary [`overlap_score`] compares. Never panics on adversarial input (arbitrary
/// Unicode, all-punctuation text, empty strings all degrade to an empty set).
fn match_words(s: &str) -> std::collections::HashSet<String> {
    s.to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() >= 3 && !STOPWORDS.contains(w))
        .map(str::to_string)
        .collect()
}

/// How well `item_words` is covered by `segment_words` — the fraction of the ITEM's own
/// significant words that also appear in the segment (containment, not Jaccard), so a short
/// marker matched against a long segment is not penalised for words the segment has that the
/// marker does not. `0.0` when `item_words` is empty, rather than dividing by zero.
fn overlap_score(
    item_words: &std::collections::HashSet<String>,
    segment_words: &std::collections::HashSet<String>,
) -> f64 {
    if item_words.is_empty() {
        return 0.0;
    }
    item_words.intersection(segment_words).count() as f64 / item_words.len() as f64
}

/// Find, from `eligible[start..]` (never before `start` — see [`link_timestamps`]'s
/// monotonic-cursor rationale), the PLAUSIBLE segment (`start_ms <= MAX_PLAUSIBLE_OFFSET_MS`)
/// with the highest [`overlap_score`] against `item_words`, breaking a tie toward the
/// EARLIEST such segment (a later index only replaces the current best on a STRICTLY higher
/// score). `segment_words[i]` must correspond to `eligible[i]` — precomputed once by the
/// caller so this is never re-tokenized per item (an O(items x segments) re-tokenization of
/// every segment for every item would be the actual hot spot at this function's own maximum
/// item AND segment counts). Returns `None` only when there is no PLAUSIBLE segment in range
/// at all — a real, implausible-filtered segment with a `0.0` score still returns `Some`.
fn best_match(
    eligible: &[crate::transcript::TranscriptSegment],
    segment_words: &[std::collections::HashSet<String>],
    start: usize,
    item_words: &std::collections::HashSet<String>,
) -> Option<(usize, f64)> {
    let mut best: Option<(usize, f64)> = None;
    for idx in start..eligible.len() {
        if eligible[idx].start_ms > MAX_PLAUSIBLE_OFFSET_MS {
            continue;
        }
        let score = overlap_score(item_words, &segment_words[idx]);
        let better = match best {
            Some((_, best_score)) => score > best_score,
            None => true,
        };
        if better {
            best = Some((idx, score));
        }
    }
    best
}

/// The `(earliest, latest)` `start_ms` among `eligible`'s PLAUSIBLE segments, in scan order
/// — the span [`link_timestamps`]'s positional fallback interpolates across. `None` when no
/// segment in `eligible` is plausible at all (including an empty `eligible`), which is the
/// one case the fallback has nothing safe to derive a position from and must simply not run.
fn plausible_bounds(eligible: &[crate::transcript::TranscriptSegment]) -> Option<(u64, u64)> {
    let mut first: Option<u64> = None;
    let mut last: Option<u64> = None;
    for s in eligible {
        if s.start_ms > MAX_PLAUSIBLE_OFFSET_MS {
            continue;
        }
        first.get_or_insert(s.start_ms);
        last = Some(s.start_ms);
    }
    first.zip(last)
}

/// Attach a transcript timestamp to each chapter-marker item (always attempted) and each
/// top-level outline point (best-effort only — see below) by matching the item's own text
/// against the transcript's real segments (86akgqdw0; FR-124).
///
/// # Strategy: post-hoc matched, never model-estimated
///
/// This is the strategy decided and documented for this ticket, over asking the model to
/// estimate a timestamp itself, for two independent reasons. First, the model is never
/// shown segment boundaries in the first place: [`NoteRequest::transcript`] is a flattened
/// `String`, by the same FR-132 egress-choke-point design that keeps live audio off the
/// wire, so there is nothing for the model to estimate FROM without a new prompt field
/// carrying per-segment timing — a new prompt-injection surface this ticket does not need
/// to open. Second, even if it were shown timing, trusting a generative model to preserve an
/// exact number through a summarization pass runs against this codebase's whole established
/// posture toward model output: see [`verify_scriptures`], which checks a scripture
/// reference the SAME way — independently, against ground truth this crate already holds,
/// never by trusting what the provider claims about itself. Matching against the
/// transcript's real segments needs no prompt change, costs no extra tokens, and reuses the
/// exact "compute independently, join by value" shape [`ScriptureVerdict`] already
/// established.
///
/// # Matching
///
/// For each item (in the order it appears in the draft), eligible segments are scanned in a
/// single forward pass **starting from where the previous item's match left off** — a
/// chapter marker or outline point occurs in the order the sermon was preached, so a later
/// item is never matched to an earlier moment than one already assigned to an earlier item.
/// This is enforced by construction (the search cursor only advances), not merely expected.
///
/// A segment is *eligible* when its own `start_ms` is at or under
/// [`MAX_PLAUSIBLE_OFFSET_MS`]; at most [`MAX_LINK_SEGMENTS`] segments are ever scanned
/// regardless of how many the caller supplies (the persisted store's segment count is
/// explicitly UNCAPPED — see that constant's own doc comment).
///
/// # Positional fallback (chapter markers only)
///
/// This ticket's Acceptance Criteria say "each marker carries a timestamp" —
/// unconditionally, not "each marker for which a confident textual match exists". A
/// model-authored chapter-marker LABEL ("The Prodigal Son Returns") often shares little or
/// no vocabulary with the actual spoken sentence at that moment, so requiring a positive
/// word-overlap score for every marker would silently leave many markers unlinked in
/// ordinary, non-adversarial use — failing the acceptance criterion in the common case, not
/// just the edge case. So: when a marker's best textual match scores `0.0` against every
/// eligible remaining segment (or none is eligible at all), it is placed at an
/// evenly-interpolated point between the transcript's earliest and latest eligible segment,
/// according to its ordinal position among the markers still needing one. This is still
/// "derived from the source transcript" — the offset is computed from that transcript's own
/// real span, never invented — it is simply a coarser derivation than a text match, and is
/// exactly as far as "we could not find a confident match" can honestly be pushed without
/// fabricating content the way this codebase otherwise refuses to.
///
/// Outline points get NO positional fallback: a top-level point is FR-124's explicitly
/// "ideally"/best-effort half, so a point with no confident textual match is simply left
/// unlinked (absent from the returned list) rather than assigned a guessed position — the
/// console must already tolerate an item with no timestamp (true of every item in a draft
/// generated with chapter markers off, an existing, required case).
///
/// # Bounded and total
///
/// Never panics on adversarial input: an empty `segments`, a segment with
/// `start_ms == u64::MAX`, a segment whose `end_ms < start_ms` (this function never reads
/// `end_ms` at all — a row loaded straight from SQL is not guaranteed to have gone through
/// [`crate::transcript::TranscriptLog::push`]'s clamp), thousands of segments, or a section
/// with hundreds of items all degrade gracefully rather than erroring.
pub fn link_timestamps(
    sections: &[NoteSection],
    segments: &[crate::transcript::TranscriptSegment],
) -> Vec<NoteTimestamp> {
    let scan_end = segments.len().min(MAX_LINK_SEGMENTS);
    let eligible = &segments[..scan_end];
    // Precomputed once, not per item: segment text does not change across items in one
    // call, so this drops the tokenization cost to O(segments) instead of
    // O(items x segments) at this function's own maximum item AND segment counts.
    let segment_words: Vec<std::collections::HashSet<String>> =
        eligible.iter().map(|s| match_words(&s.text)).collect();
    let bounds = plausible_bounds(eligible);

    let mut out = Vec::new();
    let mut seen: std::collections::HashSet<(String, String)> = std::collections::HashSet::new();

    for section in sections {
        let is_chapter_markers = section.heading == CHAPTER_MARKERS_HEADING;
        let is_outline = section.heading == OUTLINE_HEADING;
        if !is_chapter_markers && !is_outline {
            continue;
        }
        let texts: Vec<&str> = if is_chapter_markers {
            section
                .items()
                .iter()
                .map(String::as_str)
                .take(MAX_LINK_ITEMS)
                .collect()
        } else {
            section
                .points()
                .iter()
                .map(|p| p.text.as_str())
                .take(MAX_LINK_ITEMS)
                .collect()
        };
        if texts.is_empty() {
            continue;
        }

        // Pass 1: a real textual match, monotonic forward cursor.
        let mut offsets: Vec<Option<u64>> = vec![None; texts.len()];
        let mut cursor = 0usize;
        for (i, text) in texts.iter().enumerate() {
            if text.trim().is_empty() {
                continue;
            }
            let words = match_words(text);
            if words.is_empty() {
                continue;
            }
            if let Some((idx, score)) = best_match(eligible, &segment_words, cursor, &words) {
                if score > 0.0 {
                    offsets[i] = Some(eligible[idx].start_ms);
                    cursor = idx + 1;
                }
            }
        }

        // Pass 2 (chapter markers only): positional fallback for anything still
        // unmatched, interpolated across the transcript's own real, plausible span.
        if is_chapter_markers {
            if let Some((first, last)) = bounds {
                let span = last.saturating_sub(first) as f64;
                let pending: Vec<usize> = (0..texts.len())
                    .filter(|&i| offsets[i].is_none() && !texts[i].trim().is_empty())
                    .collect();
                let n = pending.len();
                for (k, &i) in pending.iter().enumerate() {
                    let frac = if n <= 1 {
                        0.0
                    } else {
                        k as f64 / (n - 1) as f64
                    };
                    offsets[i] = Some(first + (span * frac) as u64);
                }
            }
        }

        for (i, offset) in offsets.into_iter().enumerate() {
            if let Some(offset_ms) = offset {
                let key = (section.heading.clone(), texts[i].to_string());
                if seen.insert(key.clone()) {
                    out.push(NoteTimestamp {
                        heading: key.0,
                        text: key.1,
                        offset_ms,
                    });
                }
            }
        }
    }

    out
}

/// A generated sermon-note draft. Always labelled AI-generated by the UI (FR-123);
/// never overwrites the source transcript.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct NoteDraft {
    pub title: String,
    pub summary: Option<String>,
    pub sections: Vec<NoteSection>,
    /// Extracted scripture references (present only when `include.scripture_extraction`).
    pub scriptures: Vec<String>,
    /// Caveats about parts of this draft the operator should not take on trust without a
    /// second look (86akc0tua, 86akby820). Empty for a provider that cannot distinguish
    /// "empty" from "not requested" — most notably `selahcue_cloud::LocalNoteProvider`'s
    /// offline scaffold, whose deliberately empty placeholder sections must never appear
    /// here (that crate depends on this one, not the other way round, so this doc comment
    /// names it in prose rather than as an intra-doc link).
    pub caveats: Vec<DraftCaveat>,
    /// Every scripture reference found in this draft — the extracted `scriptures` list
    /// AND references embedded in a section's body text — each carrying its own verified
    /// verdict (86akby820; FR-125/FR-128). Populated only when
    /// `include.scripture_extraction` is on; empty otherwise, matching `scriptures`
    /// itself. An UNVERIFIED entry here also appears as a
    /// [`DraftCaveat::ScriptureUnverified`] in `caveats`, so a console that only reads the
    /// shared caveat list still sees it.
    pub scripture_verdicts: Vec<ScriptureVerdict>,
    /// A transcript-derived timestamp for a chapter marker or (best-effort) outline point
    /// (86akgqdw0; FR-124). Populated by [`link_timestamps`] — never by a `NoteProvider`
    /// itself, since deriving one needs the transcript's real segments, which no
    /// `NoteProvider` implementation holds (`NoteRequest::transcript` is a flattened
    /// `String` by construction, FR-132). Empty for a provider/caller that never linked
    /// timestamps at all — most notably every `NoteProvider::generate` call site, and the
    /// live-tail generation path, which has no segment structure to link against (see
    /// `link_timestamps`'s own doc comment).
    pub timestamps: Vec<NoteTimestamp>,
}

/// Why a note generation could not proceed. Stable, actionable, and — importantly —
/// carries no secret or transcript content in its message.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NoteError {
    /// Cloud-notes consent is not set — nothing was sent.
    ConsentRequired,
    /// The cloud provider has no endpoint/account configured — nothing was sent.
    NotConfigured,
    /// The monthly quota is exhausted.
    QuotaExceeded,
    /// A transport/network failure reaching the provider.
    Transport(String),
    /// The provider returned a malformed/unusable response.
    Malformed(String),
}

impl core::fmt::Display for NoteError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            NoteError::ConsentRequired => write!(f, "cloud notes consent is required"),
            NoteError::NotConfigured => write!(f, "cloud notes provider is not configured"),
            NoteError::QuotaExceeded => write!(f, "monthly note-generation quota exceeded"),
            NoteError::Transport(e) => write!(f, "note provider transport error: {e}"),
            NoteError::Malformed(e) => {
                write!(f, "note provider returned a malformed response: {e}")
            }
        }
    }
}

impl std::error::Error for NoteError {}

/// The monthly note-generation quota, as reported by the provider. Server-owned; the
/// client only displays it. `remaining` is derived, never trusted from the wire.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Quota {
    pub used: u32,
    pub limit: u32,
    /// A human-readable reset label as supplied by the provider (e.g. `"Sep 1"`).
    pub resets_label: String,
}

impl Quota {
    /// Generations left this period (saturating; never underflows).
    pub fn remaining(&self) -> u32 {
        self.limit.saturating_sub(self.used)
    }

    /// True when no generations remain.
    pub fn is_exhausted(&self) -> bool {
        self.remaining() == 0
    }
}

/// The label a generative provider's draft always carries (FR-123). The operator may
/// edit the draft freely; the label states what it started life as, and it is never
/// applied to the source transcript, which a draft never overwrites.
pub const AI_GENERATED_LABEL: &str = "AI-generated draft";

/// The fabrication-risk disclosure shown with every generative draft (FR-128).
///
/// This is about accuracy, not data handling. It says what a language model can get
/// wrong. It deliberately says **nothing** about retention, training, or a data
/// processing agreement — those claims need the DPA work (86akby942) behind them, and
/// a disclosure that promises something nobody has verified is worse than none.
pub const FABRICATION_DISCLOSURE: &str = "AI-generated. It can invent quotations, \
misattribute scripture and state things the sermon did not say. Check every \
reference and quotation against the transcript before you publish or project it.";

/// Shown with a draft the **offline fallback** served after the cloud path failed
/// (FR-135).
///
/// This is a different disclosure from [`FABRICATION_DISCLOSURE`] and neither substitutes
/// for the other. The offline scaffold invents nothing, so the fabrication warning does
/// not apply to it — but the operator asked for AI sermon notes and did not get them, and
/// a scaffold presented in silence reads as though it were the notes they requested.
/// Saying nothing here would be an under-reporting bug of exactly the kind the AI label
/// exists to prevent, pointing the other way.
pub const DEGRADED_FALLBACK_NOTICE: &str = "The AI provider could not be reached, so this \
is an offline outline built from your transcript — not AI-generated notes. The headings \
are placeholders for you to fill in. Try again when you are back online.";

/// The note-generation seam. A cloud client (SelahCue-hosted) or a local fallback
/// implements this; the core never depends on a network runtime.
pub trait NoteProvider {
    /// A stable, human-readable provider name for honest disclosure (FR-120/123).
    fn label(&self) -> &str;

    /// Generate a draft from an already-consent-gated request. Implementations must
    /// not perform egress for anything not present in `req` (only the completed
    /// transcript + options are ever sent).
    fn generate(&self, req: &NoteRequest) -> std::result::Result<NoteDraft, NoteError>;

    /// Whether this provider's drafts come out of a generative model, and so must be
    /// labelled AI-generated (FR-123) and carry the fabrication disclosure (FR-128).
    ///
    /// **Defaults to `true`,** which is the direction the default should fail in: an
    /// unlabelled model draft is a trust failure, while a label on something that is
    /// not a model is only noise. A provider that is genuinely not a model — the
    /// offline scaffold, which shapes text the operator already has and invents
    /// nothing — overrides this to `false` and says why.
    fn is_generative(&self) -> bool {
        true
    }
}

/// Settings + consent together — the single value the repo persists and the egress
/// gate reads.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ProvidersConfig {
    pub settings: ProvidersSettings,
    pub consent: ConsentState,
}

// Persistence keys — one flat `(key, value)` set stored exactly like `saved_theme`.
const K_MODE: &str = "transcription_mode";
const K_TEMPLATE: &str = "notes_template";
const K_TRANSLATION: &str = "preferred_translation";
const K_INC_PRAYER: &str = "include.prayer_points";
const K_INC_SCRIPTURE: &str = "include.scripture_extraction";
const K_INC_SOCIAL: &str = "include.social_excerpts";
const K_INC_CHAPTER: &str = "include.chapter_markers";
const K_INC_QUOTES: &str = "include.notable_quotations";
const K_INC_SUMMARY: &str = "include.short_summary";
const K_INC_PODCAST: &str = "include.podcast_show_notes";
const K_INC_SHORT_DESC: &str = "include.short_description";
const K_CONSENT_TRANSCRIPTION: &str = "consent.cloud_transcription";
const K_CONSENT_NOTES: &str = "consent.cloud_notes";

fn bool_str(b: bool) -> String {
    if b { "true" } else { "false" }.to_string()
}

/// Parse a persisted bool, defaulting to `default` for anything unrecognised.
fn parse_bool(s: &str, default: bool) -> bool {
    match s {
        "true" => true,
        "false" => false,
        _ => default,
    }
}

fn bounded(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    s[..end].to_string()
}

impl ProvidersConfig {
    /// Serialise to the flat `(key, value)` pairs the repo persists (stable order).
    pub fn to_kv(&self) -> Vec<(String, String)> {
        let s = &self.settings;
        let i = &s.include;
        let c = &self.consent;
        vec![
            (K_MODE.into(), s.transcription_mode.as_str().into()),
            (K_TEMPLATE.into(), s.notes_template.as_str().into()),
            (K_TRANSLATION.into(), s.preferred_translation.clone()),
            (K_INC_PRAYER.into(), bool_str(i.prayer_points)),
            (K_INC_SCRIPTURE.into(), bool_str(i.scripture_extraction)),
            (K_INC_SOCIAL.into(), bool_str(i.social_excerpts)),
            (K_INC_CHAPTER.into(), bool_str(i.chapter_markers)),
            (K_INC_QUOTES.into(), bool_str(i.notable_quotations)),
            (K_INC_SUMMARY.into(), bool_str(i.short_summary)),
            (K_INC_PODCAST.into(), bool_str(i.podcast_show_notes)),
            (K_INC_SHORT_DESC.into(), bool_str(i.short_description)),
            (
                K_CONSENT_TRANSCRIPTION.into(),
                bool_str(c.cloud_transcription),
            ),
            (K_CONSENT_NOTES.into(), bool_str(c.cloud_notes)),
        ]
    }

    /// Rebuild from persisted pairs. **Tolerant by construction**: unknown keys are
    /// ignored and any missing/garbage value falls back to the safe default — so a
    /// truncated or hand-edited store can never panic and can never silently *enable*
    /// cloud egress (a bad consent value parses back to `false`).
    pub fn from_kv<I, K, V>(pairs: I) -> Self
    where
        I: IntoIterator<Item = (K, V)>,
        K: AsRef<str>,
        V: AsRef<str>,
    {
        let mut cfg = ProvidersConfig::default();
        for (k, v) in pairs {
            let (k, v) = (k.as_ref(), v.as_ref());
            match k {
                K_MODE => cfg.settings.transcription_mode = TranscriptionMode::parse(v),
                K_TEMPLATE => cfg.settings.notes_template = NotesTemplate::parse(v),
                K_TRANSLATION => {
                    cfg.settings.preferred_translation = bounded(v, MAX_TRANSLATION_CODE_LEN)
                }
                K_INC_PRAYER => cfg.settings.include.prayer_points = parse_bool(v, true),
                K_INC_SCRIPTURE => cfg.settings.include.scripture_extraction = parse_bool(v, true),
                K_INC_SOCIAL => cfg.settings.include.social_excerpts = parse_bool(v, false),
                K_INC_CHAPTER => cfg.settings.include.chapter_markers = parse_bool(v, true),
                K_INC_QUOTES => cfg.settings.include.notable_quotations = parse_bool(v, true),
                K_INC_SUMMARY => cfg.settings.include.short_summary = parse_bool(v, true),
                K_INC_PODCAST => cfg.settings.include.podcast_show_notes = parse_bool(v, false),
                K_INC_SHORT_DESC => cfg.settings.include.short_description = parse_bool(v, false),
                // Consent defaults to false for anything not explicitly "true".
                K_CONSENT_TRANSCRIPTION => cfg.consent.cloud_transcription = parse_bool(v, false),
                K_CONSENT_NOTES => cfg.consent.cloud_notes = parse_bool(v, false),
                _ => {} // unknown key — ignore (forward/backward tolerant)
            }
        }
        cfg
    }

    // ---- Privacy invariants (the egress choke points) ----

    /// Whether live microphone audio may be streamed to a cloud speech service.
    /// Requires **both** the Cloud transcription mode **and** the opt-in — so the
    /// default config (OnDevice, no consent) can never stream audio.
    pub fn may_stream_cloud_audio(&self) -> bool {
        self.settings.transcription_mode == TranscriptionMode::Cloud
            && self.consent.cloud_transcription
    }

    /// Build a consent-gated note-generation request, or explain why not.
    ///
    /// - `generate_pressed` models the design's "Nothing is sent until you press
    ///   Generate": callers pass `true` only from the explicit Generate action.
    /// - Returns [`NoteError::ConsentRequired`] unless cloud-notes consent is set
    ///   **and** Generate was pressed.
    /// - The returned request carries only the completed `transcript` text; there is
    ///   no path by which live audio can be included.
    pub fn build_note_request(
        &self,
        transcript: &str,
        generate_pressed: bool,
    ) -> std::result::Result<NoteRequest, NoteError> {
        if !self.consent.cloud_notes || !generate_pressed {
            return Err(NoteError::ConsentRequired);
        }
        Ok(NoteRequest {
            transcript: transcript.to_string(),
            options: NoteOptions::from_settings(&self.settings),
        })
    }
}

// Tests live in `tests/test_providers.rs` (public-API integration tests).
