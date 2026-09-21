//! The offline local fallback [`NoteProvider`] (FR-135).
//!
//! There is no local LLM: when the cloud path is unreachable, this provider produces
//! a **deterministic structural scaffold** from the completed transcript and the
//! chosen include-flags — honest, clearly degraded, and never blank. It performs no
//! I/O and reads no clock. It never sends anything anywhere (it only shapes text the
//! operator already has locally).

use selahcue_core::providers::{NoteDraft, NoteError, NoteProvider, NoteRequest, NoteSection};

/// The always-available offline fallback. Its label makes the degraded state honest.
#[derive(Debug, Clone, Default)]
pub struct LocalNoteProvider;

impl LocalNoteProvider {
    pub fn new() -> Self {
        LocalNoteProvider
    }
}

/// The most sentences the offline scaffold ever consumes (title/summary use the first,
/// the outline the first 8). Capping the collect avoids copying a whole long transcript
/// when only the head is used.
const MAX_SCAFFOLD_SENTENCES: usize = 8;

/// The first `MAX_SCAFFOLD_SENTENCES` trimmed, non-empty sentences (bounded work + memory).
fn sentences(transcript: &str) -> Vec<String> {
    transcript
        .split(['.', '!', '?', '\n'])
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .take(MAX_SCAFFOLD_SENTENCES)
        .map(str::to_string)
        .collect()
}

impl NoteProvider for LocalNoteProvider {
    fn label(&self) -> &str {
        "Local (offline)"
    }

    /// **Not** generative. There is no local model here: this provider slices sentences
    /// the operator already has and names the headings the cloud path would have filled.
    /// It cannot invent a quotation or misattribute a verse, so labelling its output
    /// "AI-generated" and attaching a fabrication warning would be a false statement on
    /// the one screen whose job is being truthful about what the machine did.
    fn is_generative(&self) -> bool {
        false
    }

    fn generate(&self, req: &NoteRequest) -> Result<NoteDraft, NoteError> {
        let s = sentences(&req.transcript);
        let inc = &req.options.include;

        // Title: the first sentence (bounded), or a stable default.
        let title = s
            .first()
            .map(|first| {
                let t: String = first.chars().take(80).collect();
                t
            })
            .unwrap_or_else(|| "Sermon notes".to_string());

        let summary = if inc.short_summary {
            s.first().cloned()
        } else {
            None
        };

        let mut sections: Vec<NoteSection> = Vec::new();
        // A single "Outline" section from the first handful of sentences keeps the
        // scaffold useful without pretending to be AI analysis.
        let outline: Vec<String> = s.iter().take(8).cloned().collect();
        if !outline.is_empty() {
            sections.push(NoteSection::flat("Outline", outline));
        }
        // Each enabled include-flag becomes an honest, empty-for-operator-to-fill
        // heading — the offline scaffold cannot generate these, but it names them so
        // the operator knows what the cloud path would add.
        if inc.prayer_points {
            sections.push(NoteSection::flat("Prayer points", Vec::new()));
        }
        if inc.notable_quotations {
            sections.push(NoteSection::flat("Notable quotations", Vec::new()));
        }
        if inc.social_excerpts {
            sections.push(NoteSection::flat("Social excerpts", Vec::new()));
        }
        if inc.podcast_show_notes {
            sections.push(NoteSection::flat("Podcast show notes", Vec::new()));
        }
        if inc.short_description {
            sections.push(NoteSection::flat("Short description", Vec::new()));
        }

        Ok(NoteDraft {
            title,
            summary,
            sections,
            scriptures: Vec::new(),
            // Deliberately always empty (86akc0tua). This scaffold cannot tell "the sermon
            // had none" from "nothing came back" any more than the cloud path can — it
            // simply doesn't try, and it already says its own honest thing via
            // `DEGRADED_FALLBACK_NOTICE`. A requested-but-empty caveat here would repeat
            // that fact in a second, contradictory-sounding voice underneath it.
            caveats: Vec::new(),
            // The scaffold invents nothing and extracts no scriptures at all (86akby820) —
            // there is nothing here to verify.
            scripture_verdicts: Vec::new(),
            // No "Chapter markers"/"Main points" section exists in this scaffold at all
            // (86akgqdw0) — there is nothing for `link_timestamps` to find here even once
            // the operator layer runs it.
            timestamps: Vec::new(),
        })
    }
}
