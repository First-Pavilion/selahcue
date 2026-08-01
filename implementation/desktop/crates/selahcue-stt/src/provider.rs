//! The [`selahcue_core::transcript::TranscriptProvider`] implementation and the bounded,
//! thread-safe segment queue shared between the engine (producer, worker thread) and the
//! provider (consumer, host thread).
//!
//! [`SttProvider::poll`] only drains the queue — it never runs recognition — so the host's
//! poll is O(pending) and never blocks on audio or the model (FR-083 / NFR-024). The queue
//! is hard-capped ([`MAX_PENDING_SEGMENTS`]): if the host stops polling, the oldest pending
//! segments are dropped rather than growing memory without bound (no-leak).

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use selahcue_core::transcript::{ProviderSegment, TranscriptProvider};

/// Upper bound on segments buffered between the engine and a `poll`. The operator view only
/// shows a recent window; a host that stops draining cannot make this grow without limit.
pub const MAX_PENDING_SEGMENTS: usize = 256;

/// A bounded, cloneable, thread-safe queue of finished [`ProviderSegment`]s. The engine
/// pushes (worker thread); the provider drains (host thread). Clones share one queue.
#[derive(Debug, Clone, Default)]
pub struct SegmentSink {
    inner: Arc<Mutex<VecDeque<ProviderSegment>>>,
}

impl SegmentSink {
    /// An empty shared sink.
    pub fn new() -> Self {
        SegmentSink {
            inner: Arc::new(Mutex::new(VecDeque::new())),
        }
    }

    /// Push a finished segment, evicting the oldest if at [`MAX_PENDING_SEGMENTS`].
    /// A poisoned lock is recovered (never panics) — a segment is data, not a critical
    /// section that can leave an invariant broken.
    pub fn push(&self, segment: ProviderSegment) {
        let mut q = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        q.push_back(segment);
        while q.len() > MAX_PENDING_SEGMENTS {
            q.pop_front();
        }
    }

    /// Drain every pending segment in order, leaving the queue empty.
    pub fn drain(&self) -> Vec<ProviderSegment> {
        let mut q = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        q.drain(..).collect()
    }

    /// Number of pending (undrained) segments (never exceeds the cap).
    pub fn len(&self) -> usize {
        self.inner.lock().unwrap_or_else(|e| e.into_inner()).len()
    }

    /// Whether there are no pending segments.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

/// The on-device STT provider: a [`TranscriptProvider`] whose `poll` drains segments the
/// engine has recognized. Swapping this in for `ManualProvider` never touches the core.
#[derive(Debug, Clone)]
pub struct SttProvider {
    sink: SegmentSink,
    label: String,
}

impl SttProvider {
    /// A provider draining `sink`, disclosing itself as `label` (FR-120 honest disclosure).
    pub fn new(sink: SegmentSink, label: impl Into<String>) -> Self {
        SttProvider {
            sink,
            label: label.into(),
        }
    }
}

impl TranscriptProvider for SttProvider {
    fn label(&self) -> &str {
        &self.label
    }

    fn poll(&mut self) -> Vec<ProviderSegment> {
        self.sink.drain()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seg(text: &str) -> ProviderSegment {
        ProviderSegment::final_text(text, 0, 20)
    }

    #[test]
    fn poll_drains_in_order_then_empties() {
        let sink = SegmentSink::new();
        sink.push(seg("a"));
        sink.push(seg("b"));
        let mut provider = SttProvider::new(sink, "stt:fake");
        let out = provider.poll();
        assert_eq!(
            out.iter().map(|s| s.text.as_str()).collect::<Vec<_>>(),
            ["a", "b"]
        );
        assert!(provider.poll().is_empty());
        assert_eq!(provider.label(), "stt:fake");
    }

    #[test]
    fn queue_is_bounded_under_flood() {
        let sink = SegmentSink::new();
        for i in 0..(MAX_PENDING_SEGMENTS * 4) {
            sink.push(seg(&format!("{i}")));
        }
        assert_eq!(sink.len(), MAX_PENDING_SEGMENTS);
    }
}
