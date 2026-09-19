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
/// (social excerpts OFF by default; the rest ON).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct IncludeInNotes {
    pub prayer_points: bool,
    pub scripture_extraction: bool,
    pub social_excerpts: bool,
    pub chapter_markers: bool,
    pub notable_quotations: bool,
    pub short_summary: bool,
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
    /// The reference exactly as it appeared — canonical form when it parsed (e.g. the
    /// extracted-list entry or a text match, both already in `parse_one`'s accepted
    /// shape), or the original text verbatim when it did not parse at all.
    pub reference: String,
    /// True when the reference parsed AND resolved to at least one verse. False for
    /// EITHER an unparseable reference OR one that parses but is outside the canon
    /// (wrong book, chapter past the book's end, verse past the chapter's end) — both are
    /// "unverified", never dropped, never an error.
    pub verified: bool,
}

/// Upper bound on scripture references actually verified per draft, across the extracted
/// list AND every section's body text combined. Independent of any upstream bound (e.g.
/// `selahcue-cloud`'s per-provider caps) so this guarantee holds for any `NoteDraft`
/// regardless of which provider built it — a hostile or absurdly long draft cannot make
/// verification do unbounded work or grow the verdict list without limit.
pub const MAX_VERIFIED_REFERENCES: usize = 64;

/// Verify every scripture reference in a draft — the extracted `scriptures` list AND
/// references embedded in a section's body text (flat items, outline point text, and
/// sub-point text) — against `exists`, an injected lookup so this function stays testable
/// with a stub oracle and has no dependency on `selahcue-scripture` (which depends on this
/// crate, not the other way round; the real caller wires `exists` to
/// `|r| !selahcue_scripture::verses(r).is_empty()`).
///
/// Bounded and total: never panics on adversarial input, and never verifies more than
/// [`MAX_VERIFIED_REFERENCES`] references regardless of how large or hostile `scriptures`
/// or `sections` are. A reference that cannot be parsed at all is retained as unverified,
/// never silently dropped (unlike [`crate::scripture::parse`], which is the wrong entry
/// point here for exactly that reason). Duplicate reference text (by exact string) is
/// verified once; a fabricated reference repeated ten times in one draft is reported once,
/// not ten times.
pub fn verify_scriptures(
    scriptures: &[String],
    sections: &[NoteSection],
    mut exists: impl FnMut(&crate::scripture::Reference) -> bool,
) -> Vec<ScriptureVerdict> {
    let mut verdicts = Vec::new();
    let mut seen = std::collections::HashSet::new();

    let mut consider = |raw: &str,
                        verdicts: &mut Vec<ScriptureVerdict>,
                        seen: &mut std::collections::HashSet<String>| {
        if verdicts.len() >= MAX_VERIFIED_REFERENCES {
            return;
        }
        let raw = raw.trim();
        if raw.is_empty() || !seen.insert(raw.to_string()) {
            return;
        }
        let verdict = match crate::scripture::parse_one(raw) {
            Ok(reference) => ScriptureVerdict {
                reference: reference.to_string(),
                verified: exists(&reference),
            },
            Err(_) => ScriptureVerdict {
                reference: raw.to_string(),
                verified: false,
            },
        };
        verdicts.push(verdict);
    };

    for raw in scriptures {
        consider(raw, &mut verdicts, &mut seen);
    }

    'sections: for section in sections {
        for item in section.items() {
            for candidate in crate::detection::detect(item) {
                consider(&candidate, &mut verdicts, &mut seen);
                if verdicts.len() >= MAX_VERIFIED_REFERENCES {
                    break 'sections;
                }
            }
        }
        for point in section.points() {
            for candidate in crate::detection::detect(&point.text) {
                consider(&candidate, &mut verdicts, &mut seen);
            }
            for sub in &point.sub_points {
                for candidate in crate::detection::detect(sub) {
                    consider(&candidate, &mut verdicts, &mut seen);
                }
            }
            if verdicts.len() >= MAX_VERIFIED_REFERENCES {
                break 'sections;
            }
        }
    }

    verdicts
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
