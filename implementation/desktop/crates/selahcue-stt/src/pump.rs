//! The host pump loop: drain a [`TranscriptProvider`] and hand each segment to a sink.
//!
//! This is the missing piece the seam was designed for. The host owns the `LiveController`;
//! it calls [`pump`] on an interval with a closure that forwards each segment into
//! `LiveController::ingest_transcript`:
//!
//! ```ignore
//! // On a host worker thread, out-of-band from render:
//! pump(&mut provider, |seg| {
//!     controller.ingest_transcript(&seg.text, seg.start_ms, seg.end_ms);
//! });
//! ```
//!
//! `pump` takes a closure (not a controller type) so this crate needs no dependency on
//! `selahcue-app`; wiring the closure to the real controller is host code (not this crate,
//! and not any UI). One `pump` call performs exactly one non-blocking `poll` and forwards
//! each returned segment exactly once.

use selahcue_core::transcript::{ProviderSegment, TranscriptProvider};

/// Drain `provider` once (a single non-blocking `poll`) and pass every returned segment to
/// `sink`, in order. Returns the number of segments forwarded.
pub fn pump(provider: &mut dyn TranscriptProvider, mut sink: impl FnMut(ProviderSegment)) -> usize {
    let segments = provider.poll();
    let n = segments.len();
    for seg in segments {
        sink(seg);
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;
    use selahcue_core::transcript::ManualProvider;

    #[test]
    fn forwards_each_segment_once_in_order() {
        // ManualProvider is a ready-made fake TranscriptProvider.
        let mut provider = ManualProvider::new();
        provider.submit("first", 0, 10);
        provider.submit("second", 10, 20);

        let mut seen: Vec<String> = Vec::new();
        let n = pump(&mut provider, |seg| seen.push(seg.text));
        assert_eq!(n, 2);
        assert_eq!(seen, vec!["first".to_string(), "second".to_string()]);

        // A second pump with nothing queued forwards nothing (no double-delivery).
        let n2 = pump(&mut provider, |_| panic!("should not be called"));
        assert_eq!(n2, 0);
    }
}
