//! How much transcript text a single note-generation request may carry, and the pure
//! string-bounding logic behind it.
//!
//! **Extracted from [`crate::openai`] (86akcffy0).** The cap and the function that applies it
//! used to live entirely inside `openai.rs`, gated behind the `openai` Cargo feature — reachable
//! only from a build that compiles the direct-to-OpenAI developer-key path. That was fine while
//! the only caller was `openai::build_body`, but the from-history Generate flow
//! (`selahcue-operator`'s `transcript_generate_notes` command) needs to report the SAME clamp to
//! the operator, in every build configuration, including one with neither `openai` nor
//! `cloud-live` compiled in — a build in which `run_note_generation` never gets past
//! `ProvidersConfig::build_note_request` (no provider is configured) but the from-history
//! preview still wants to say honestly "your transcript is N characters; the limit is 400,000"
//! *before* Confirm is even pressed, not just report `NotConfigured` after the fact.
//!
//! This module has no HTTP/OpenAI-specific dependencies — it is pure `&str` arithmetic — so it
//! moves here, unconditionally compiled, and [`crate::openai`] re-exports both names unchanged
//! (`pub use crate::transcript_bounds::{bounded_transcript, MAX_TRANSCRIPT_CHARS};`) so no
//! existing call site or test (`tests/test_openai.rs`) needed to change paths.

/// The most transcript text ever sent in one request.
///
/// Speech runs about 130 words a minute and roughly 6 characters a word, so this is
/// something over eight hours of continuous preaching — far past any real service, and
/// finite. The point is not to trim normal input (it never will) but that a corrupted
/// or maliciously-grown transcript file cannot become an arbitrarily large request body.
pub const MAX_TRANSCRIPT_CHARS: usize = 400_000;

/// The slice of `transcript` that may be sent, plus how many characters were dropped.
///
/// Returns a **borrowed** slice on purpose. The transcript is already one owned `String`
/// inside the `NoteRequest`; taking a second owned copy just to cap it would double
/// the resident bytes of the very value the cap exists to bound — the bug hides in the
/// fix. Callers push this slice straight into the request body.
///
/// The head is kept rather than the tail. Truncation only happens on input past eight
/// hours of speech, and when it does the model is told the transcript was cut, so it
/// reports a missing conclusion instead of inventing one.
pub fn bounded_transcript(transcript: &str) -> (&str, Option<usize>) {
    if transcript.chars().count() <= MAX_TRANSCRIPT_CHARS {
        return (transcript, None);
    }
    let end = transcript
        .char_indices()
        .nth(MAX_TRANSCRIPT_CHARS)
        .map(|(i, _)| i)
        .unwrap_or(transcript.len());
    let dropped = transcript[end..].chars().count();
    (&transcript[..end], Some(dropped))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_transcript_at_the_cap_is_not_truncated() {
        let t = "a".repeat(MAX_TRANSCRIPT_CHARS);
        let (slice, dropped) = bounded_transcript(&t);
        assert_eq!(slice.chars().count(), MAX_TRANSCRIPT_CHARS);
        assert_eq!(dropped, None, "exactly at the cap must not report a drop");
    }

    #[test]
    fn a_transcript_over_the_cap_is_truncated_to_the_head_with_an_honest_drop_count() {
        let over = MAX_TRANSCRIPT_CHARS + 5_000;
        let t = "a".repeat(over);
        let (slice, dropped) = bounded_transcript(&t);
        assert_eq!(slice.chars().count(), MAX_TRANSCRIPT_CHARS);
        assert_eq!(dropped, Some(5_000));
    }
}
