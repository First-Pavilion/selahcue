//! The versioned SelahCue cloud API **contract** — the serde wire types for
//! note-generation and quota, plus the mapping to/from the pure core domain.
//!
//! This is the single source of truth the real hosted service must satisfy. Keeping
//! it here (not in the pure core) lets the core stay dependency-free while the
//! contract carries serde. Every field is explicit so a schema change is a visible
//! diff, and every inbound value is treated as untrusted (parsed via the core's
//! tolerant `parse`, never `unwrap`).
//!
//! ## Endpoints (v1)
//! - `POST {base}/v1/notes:generate` — [`GenerateNotesRequest`] → [`GenerateNotesResponse`]
//! - `GET  {base}/v1/quota` — → [`QuotaDto`]
//!
//! Auth is `Authorization: Bearer <account/session token>` (never a user-pasted
//! third-party key — the hosted model, FR-134).
//!
//! ## Error responses (what the client reads; not yet a defined envelope) -- 86akbzxjg
//! The client never shows any part of a non-2xx body (a provider's 401 carries a clear-text
//! fragment of the key). It reads only `error.type` and `error.code`, exactly and
//! case-sensitively, against a closed list (see [`crate::provider_error`]), and the parse is
//! bounded.
//! - **Terminal exhaustion** (the "quota used up" state that stops the local fallback) must be
//!   HTTP **402**, or a 429 whose `error.code` or `error.type` is `insufficient_quota` or
//!   `credit_balance_exhausted`. Any other 429 is a transient rate limit, and a 5xx is a server
//!   blip; both serve the degraded local draft.
//! - **Upstream provider exhaustion must be translated, never forwarded.** A thin proxy that
//!   forwards a provider's exhaustion would report the provider's empty balance as the
//!   operator's own quota and deny them the local draft, and its body would be untrusted text.
//!   Translate it (for example to a 5xx) and answer 402 only for the account's own quota.
//! - The platform API's /v1 envelope (`implementation/api/selahcue_api/platform/responses.py`)
//!   uses UPPER_SNAKE codes such as `RATE_LIMITED`, and ADR-0028 records a coded refusal
//!   `QUOTA_EXHAUSTED`. None of those match the closed list, so under this client a 429
//!   `RATE_LIMITED` reads as transient (correct) but an exhaustion signalled only by an
//!   UPPER_SNAKE code on a 429 would read as transient too. 86akby3xu defines the hosted
//!   envelope and must reconcile the two vocabularies.

use selahcue_core::providers::{
    IncludeInNotes, NoteDraft, NoteOptions, NoteRequest, NoteSection, NotesTemplate, Quota,
};
use serde::{Deserialize, Serialize};

/// The path (relative to the configured base URL) for note generation.
pub const NOTES_GENERATE_PATH: &str = "/v1/notes:generate";
/// The path (relative to the configured base URL) for the standalone quota probe.
pub const QUOTA_PATH: &str = "/v1/quota";

/// Request body for note generation. Carries only the completed transcript + options
/// — there is no audio field, mirroring the core's [`NoteRequest`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GenerateNotesRequest {
    pub transcript: String,
    pub options: OptionsDto,
}

impl GenerateNotesRequest {
    /// Build the wire request from a core [`NoteRequest`].
    pub fn from_core(req: &NoteRequest) -> Self {
        GenerateNotesRequest {
            transcript: req.transcript.clone(),
            options: OptionsDto::from_core(&req.options),
        }
    }
}

/// Wire form of [`NoteOptions`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OptionsDto {
    pub template: String,
    pub preferred_translation: String,
    pub include: IncludeDto,
}

impl OptionsDto {
    pub fn from_core(o: &NoteOptions) -> Self {
        OptionsDto {
            template: o.template.as_str().to_string(),
            preferred_translation: o.preferred_translation.clone(),
            include: IncludeDto::from_core(&o.include),
        }
    }

    pub fn to_core(&self) -> NoteOptions {
        NoteOptions {
            template: NotesTemplate::parse(&self.template),
            preferred_translation: self.preferred_translation.clone(),
            include: self.include.to_core(),
        }
    }
}

/// Wire form of [`IncludeInNotes`].
///
/// `#[serde(default)]` on every field (Cody + Sana, independently, on PR #48's review):
/// with none of the 8 booleans defaulted, a peer payload that predates a field fails to
/// deserialize rather than defaulting to off. Fails closed today (there is no live
/// consumer of this unshipped v1 contract), but costs nothing to fix now rather than
/// leave as a note for whoever ships the real hosted client.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct IncludeDto {
    #[serde(default)]
    pub prayer_points: bool,
    #[serde(default)]
    pub scripture_extraction: bool,
    #[serde(default)]
    pub social_excerpts: bool,
    #[serde(default)]
    pub chapter_markers: bool,
    #[serde(default)]
    pub notable_quotations: bool,
    #[serde(default)]
    pub short_summary: bool,
    /// Wire form of [`IncludeInNotes::podcast_show_notes`] (86akgqdwc/FR-126).
    #[serde(default)]
    pub podcast_show_notes: bool,
    /// Wire form of [`IncludeInNotes::short_description`] (86akgqdwc/FR-126).
    #[serde(default)]
    pub short_description: bool,
}

impl IncludeDto {
    pub fn from_core(i: &IncludeInNotes) -> Self {
        IncludeDto {
            prayer_points: i.prayer_points,
            scripture_extraction: i.scripture_extraction,
            social_excerpts: i.social_excerpts,
            chapter_markers: i.chapter_markers,
            notable_quotations: i.notable_quotations,
            short_summary: i.short_summary,
            podcast_show_notes: i.podcast_show_notes,
            short_description: i.short_description,
        }
    }

    pub fn to_core(self) -> IncludeInNotes {
        IncludeInNotes {
            prayer_points: self.prayer_points,
            scripture_extraction: self.scripture_extraction,
            social_excerpts: self.social_excerpts,
            chapter_markers: self.chapter_markers,
            notable_quotations: self.notable_quotations,
            short_summary: self.short_summary,
            podcast_show_notes: self.podcast_show_notes,
            short_description: self.short_description,
        }
    }
}

/// Response body for note generation: the draft plus the caller's current quota.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GenerateNotesResponse {
    pub draft: NoteDraftDto,
    pub quota: QuotaDto,
}

/// Wire form of [`NoteDraft`].
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct NoteDraftDto {
    pub title: String,
    #[serde(default)]
    pub summary: Option<String>,
    #[serde(default)]
    pub sections: Vec<NoteSectionDto>,
    #[serde(default)]
    pub scriptures: Vec<String>,
}

impl NoteDraftDto {
    pub fn to_core(&self) -> NoteDraft {
        NoteDraft {
            title: self.title.clone(),
            summary: self.summary.clone(),
            sections: self
                .sections
                .iter()
                // The hosted v1 contract has no hierarchy of its own: its sections are
                // flat. `points` stays empty rather than being faked out of `items`.
                .map(|s| NoteSection::flat(s.heading.clone(), s.items.clone()))
                .collect(),
            scriptures: self.scriptures.clone(),
            // The hosted v1 contract has no equivalent of 86akc0tua's requested-but-empty
            // signal yet; this stays empty rather than guessing one from `Dto` shape.
            caveats: Vec::new(),
            // Likewise no scripture-verification equivalent yet (86akby820) — the operator
            // is the layer that runs verification today (see `main.rs`), and this contract
            // has no wire field to carry a pre-computed verdict even if it wanted to.
            scripture_verdicts: Vec::new(),
            // No timestamp-linking equivalent either (86akgqdw0) — same reasoning: the
            // operator is the layer that runs `link_timestamps`, and this unshipped v1
            // contract has no wire field for it.
            timestamps: Vec::new(),
        }
    }
}

/// Wire form of [`NoteSection`].
///
/// The hosted v1 contract carries flat sections only. When the hosted service grows an
/// outline it gains a `points` field here and [`NoteDraftDto::to_core`] switches on which
/// arrived — the core type already models both, so that is an additive change.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct NoteSectionDto {
    pub heading: String,
    #[serde(default)]
    pub items: Vec<String>,
}

/// Wire form of [`Quota`]. `remaining` is intentionally derived on the core side
/// ([`Quota::remaining`]) rather than trusted from the wire.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct QuotaDto {
    pub used: u32,
    pub limit: u32,
    #[serde(default)]
    pub resets_label: String,
}

impl QuotaDto {
    pub fn to_core(&self) -> Quota {
        Quota {
            used: self.used,
            limit: self.limit,
            resets_label: self.resets_label.clone(),
        }
    }
}
