//! Live sermon-transcript segments and the pluggable transcription seam
//! (R3; ADR-0010 `STTProvider`).
//!
//! Transcription is an **assistant, never a gate** (ADR-0010 / FR-083): this module
//! is pure, deterministic, side-effect-free domain data. It defines the bounded,
//! timestamped [`TranscriptSegment`] stream, a hard-capped [`TranscriptLog`] (no
//! unbounded growth — the no-leak invariant), and the [`TranscriptProvider`] seam
//! behind which a real on-device engine (whisper.cpp / Vosk) plugs in without
//! touching the presentation core. The always-present default is the deterministic
//! [`ManualProvider`] (operator/host-injected text) — the offline, zero-dependency
//! baseline the tests and the standalone operator use; a heavy cloud/model runtime
//! is a documented follow-up behind the same trait, exactly as ADR-0010 requires.

use std::collections::VecDeque;

/// Upper bound on retained transcript segments. A live sermon is long; the panel
/// only ever shows a recent window, so the log is a fixed-size ring — a flood of
/// ingests can never grow memory without limit (no-leak; asserted by the
/// bounded-memory tests).
pub const MAX_TRANSCRIPT_SEGMENTS: usize = 240;

/// Upper bound on a single segment's stored text. One spoken utterance is short;
/// a wire-legal but absurdly long payload is truncated (at a UTF-8 boundary) so
/// one segment cannot smuggle in unbounded memory.
pub const MAX_SEGMENT_TEXT_LEN: usize = 2_000;

/// One bounded, timestamped transcript segment (a recognised utterance).
///
/// Timestamps are milliseconds from an arbitrary session origin supplied by the
/// caller — the module reads no clock itself (determinism, ADR-0015 spirit).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TranscriptSegment {
    /// Monotonic per-log id (stable while the segment is retained).
    pub id: u64,
    /// Utterance start, in ms from the session origin.
    pub start_ms: u64,
    /// Utterance end, in ms from the session origin (`>= start_ms`).
    pub end_ms: u64,
    /// The recognised text (already length-bounded).
    pub text: String,
}

/// A segment as it leaves a [`TranscriptProvider`] — no id yet (the log assigns one).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProviderSegment {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    /// Whether this is a final (committed) result vs an interim hypothesis. The
    /// default provider only emits finals; a streaming STT engine may emit interims.
    pub is_final: bool,
}

impl ProviderSegment {
    /// A final segment spanning `start_ms..=end_ms`.
    pub fn final_text(text: impl Into<String>, start_ms: u64, end_ms: u64) -> Self {
        ProviderSegment {
            text: text.into(),
            start_ms,
            end_ms,
            is_final: true,
        }
    }
}

/// Truncate `s` to at most `max` bytes, on a UTF-8 char boundary (never panics,
/// never splits a codepoint).
fn bounded_text(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    s[..end].to_string()
}

/// A hard-capped ring of the most recent [`TranscriptSegment`]s.
///
/// `push` appends and evicts the oldest once [`MAX_TRANSCRIPT_SEGMENTS`] is reached,
/// so `len()` is bounded for any input volume. Ids keep counting up (they identify
/// a segment, not a slot), so an id is never silently reused while its segment lives.
#[derive(Debug, Clone, Default)]
pub struct TranscriptLog {
    segments: VecDeque<TranscriptSegment>,
    next_id: u64,
}

impl TranscriptLog {
    /// An empty log.
    pub fn new() -> Self {
        TranscriptLog {
            segments: VecDeque::new(),
            next_id: 0,
        }
    }

    /// Append a segment (text length-bounded, `end_ms` clamped to be `>= start_ms`),
    /// evicting the oldest if at capacity. Returns the new segment's id.
    pub fn push(&mut self, text: &str, start_ms: u64, end_ms: u64) -> u64 {
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        let segment = TranscriptSegment {
            id,
            start_ms,
            end_ms: end_ms.max(start_ms),
            text: bounded_text(text, MAX_SEGMENT_TEXT_LEN),
        };
        self.segments.push_back(segment);
        while self.segments.len() > MAX_TRANSCRIPT_SEGMENTS {
            self.segments.pop_front();
        }
        id
    }

    /// The retained segments, oldest first.
    pub fn segments(&self) -> impl Iterator<Item = &TranscriptSegment> {
        self.segments.iter()
    }

    /// The most recent `n` segments, oldest first (bounded view for the panel).
    pub fn recent(&self, n: usize) -> Vec<&TranscriptSegment> {
        let skip = self.segments.len().saturating_sub(n);
        self.segments.iter().skip(skip).collect()
    }

    /// Number of retained segments (never exceeds [`MAX_TRANSCRIPT_SEGMENTS`]).
    pub fn len(&self) -> usize {
        self.segments.len()
    }

    pub fn is_empty(&self) -> bool {
        self.segments.is_empty()
    }

    /// Drop every retained segment (id counter is preserved so ids never repeat).
    pub fn clear(&mut self) {
        self.segments.clear();
    }
}

/// The transcription seam (ADR-0010 `STTProvider`): a source of transcript segments
/// the host drains out-of-band and feeds into the detection engine. Implementations
/// range from the deterministic [`ManualProvider`] (default) to a real on-device
/// engine — swapping one never touches the presentation core.
pub trait TranscriptProvider {
    /// A stable, human-readable provider name for honest disclosure (FR-120 — the
    /// UI states which engine produced the transcript; no false "perfect STT" claim).
    fn label(&self) -> &str;

    /// Drain any segments available since the last poll. Deterministic providers
    /// return exactly what was injected, in order; a streaming engine returns freshly
    /// decoded audio. Never blocks the caller (the render path never awaits AI).
    fn poll(&mut self) -> Vec<ProviderSegment>;
}

/// The always-present default provider: a deterministic queue of operator/host-injected
/// segments. It performs no I/O and reads no clock, so tests and the standalone operator
/// get a fully offline, reproducible transcript. A real on-device STT engine implements
/// the same [`TranscriptProvider`] trait behind this seam (documented follow-up).
#[derive(Debug, Clone, Default)]
pub struct ManualProvider {
    pending: VecDeque<ProviderSegment>,
}

impl ManualProvider {
    pub fn new() -> Self {
        ManualProvider {
            pending: VecDeque::new(),
        }
    }

    /// Queue a final segment to be returned by the next [`poll`](TranscriptProvider::poll).
    pub fn submit(&mut self, text: impl Into<String>, start_ms: u64, end_ms: u64) {
        self.pending
            .push_back(ProviderSegment::final_text(text, start_ms, end_ms));
    }

    /// Queue an already-built [`ProviderSegment`].
    pub fn submit_segment(&mut self, segment: ProviderSegment) {
        self.pending.push_back(segment);
    }
}

impl TranscriptProvider for ManualProvider {
    fn label(&self) -> &str {
        "manual"
    }

    fn poll(&mut self) -> Vec<ProviderSegment> {
        self.pending.drain(..).collect()
    }
}

// Tests live in `tests/test_transcript.rs` (public-API integration tests).
