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
            sections.push(NoteSection {
                heading: "Outline".to_string(),
                items: outline,
            });
        }
        // Each enabled include-flag becomes an honest, empty-for-operator-to-fill
        // heading — the offline scaffold cannot generate these, but it names them so
        // the operator knows what the cloud path would add.
        if inc.prayer_points {
            sections.push(NoteSection {
                heading: "Prayer points".to_string(),
                items: Vec::new(),
            });
        }
        if inc.notable_quotations {
            sections.push(NoteSection {
                heading: "Notable quotations".to_string(),
                items: Vec::new(),
            });
        }
        if inc.social_excerpts {
            sections.push(NoteSection {
                heading: "Social excerpts".to_string(),
                items: Vec::new(),
            });
        }

        Ok(NoteDraft {
            title,
            summary,
            sections,
            scriptures: Vec::new(),
        })
    }
}
