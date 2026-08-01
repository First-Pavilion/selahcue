//! The host pump loop that wires an STT (or any) [`TranscriptProvider`] into the detection
//! engine — the STT↔detection link.
//!
//! The desktop host owns the [`LiveController`]; on a worker thread (out-of-band from render)
//! it drains the provider and feeds each recognized segment into
//! [`LiveController::ingest_transcript`], which runs BOTH exact reference detection and the
//! fuzzy quote/paraphrase matcher. Taking the core [`TranscriptProvider`] trait (not a
//! concrete engine) means this works with the on-device `SttProvider`, the `ManualProvider`,
//! or any test double — with no dependency on the STT crate.

use crate::LiveController;
use selahcue_core::transcript::TranscriptProvider;

/// Drain `provider` once (a single non-blocking [`poll`](TranscriptProvider::poll)) into the
/// controller's detection engine, running exact + fuzzy scripture detection over each
/// segment. Returns the number of segments ingested.
///
/// The host calls this on an interval from a worker thread; a test drives it with a fake
/// provider. It never blocks the render/output path: `poll` is non-blocking and detection is
/// out-of-band (FR-083 / NFR-024).
pub fn pump_transcript(
    controller: &mut LiveController,
    provider: &mut dyn TranscriptProvider,
) -> usize {
    let segments = provider.poll();
    let n = segments.len();
    for seg in segments {
        controller.ingest_transcript(&seg.text, seg.start_ms, seg.end_ms);
    }
    n
}
