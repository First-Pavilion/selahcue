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

/// As [`bounded_transcript`], but for a caller that OWNS the transcript and wants it clamped
/// without ever holding two full copies at once — `String::truncate` is O(1) past the scan that
/// finds the byte offset, unlike `bounded_transcript(...).0.to_string()`, which would allocate a
/// second up-to-400,000-character `String` just to shrink it back down (the same
/// double-resident-bytes trap [`bounded_transcript`]'s own doc comment already avoids for a
/// borrowing caller). Returns how many trailing characters were removed, or `None` if `s` already
/// fit.
///
/// [`generate_sermon_notes`](crate::generate_sermon_notes) calls this on every request right
/// after [`selahcue_core::providers::ProvidersConfig::build_note_request`] builds it (86akcffy0,
/// Cody review) — that is the ONE place every current and future [`crate::CloudNoteProvider`]
/// (the OpenAI direct-key provider today, a hosted `SelahCueCloudClient` tomorrow) is guaranteed
/// to pass through, so the clamp holds regardless of which provider ends up serving the request.
/// Before this, `openai::build_body` was the only call site, which meant a hosted provider that
/// forgot to clamp would silently send an unbounded transcript.
pub fn clamp_transcript_in_place(s: &mut String) -> Option<usize> {
    if s.chars().count() <= MAX_TRANSCRIPT_CHARS {
        return None;
    }
    let end = s
        .char_indices()
        .nth(MAX_TRANSCRIPT_CHARS)
        .map(|(i, _)| i)
        .unwrap_or(s.len());
    let dropped = s[end..].chars().count();
    s.truncate(end);
    Some(dropped)
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

    #[test]
    fn clamp_in_place_leaves_an_under_cap_string_untouched() {
        let mut s = "under the cap".to_string();
        let before = s.clone();
        assert_eq!(clamp_transcript_in_place(&mut s), None);
        assert_eq!(s, before);
    }

    #[test]
    fn clamp_in_place_truncates_to_the_head_matching_the_borrowing_version() {
        let over = MAX_TRANSCRIPT_CHARS + 5_000;
        let mut owned = "a".repeat(over);
        let borrowed = owned.clone();
        let (expected_slice, expected_dropped) = bounded_transcript(&borrowed);
        let expected_slice = expected_slice.to_string();

        let dropped = clamp_transcript_in_place(&mut owned);

        assert_eq!(dropped, expected_dropped);
        assert_eq!(owned, expected_slice);
        assert_eq!(owned.chars().count(), MAX_TRANSCRIPT_CHARS);
    }
}
