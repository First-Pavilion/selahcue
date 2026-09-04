//! The [`TranscriptProvider`] implementation, and the session state the console reads.
//!
//! [`CloudTranscriptProvider::poll`] **only drains the queue** — it never touches the socket,
//! never awaits, and never takes a lock the network holds. That is the architectural
//! requirement, not a performance preference: the render path never waits on AI (FR-083 /
//! NFR-024), so a Deepgram outage must be incapable of delaying a slide change. The socket
//! runs on its own thread and fills [`SegmentQueue`]; the host's poll is O(pending).

use selahcue_core::transcript::{ProviderSegment, TranscriptProvider};
use std::sync::{Arc, Mutex};

use crate::error::OperatorAction;
use crate::queue::SegmentQueue;
use crate::session::StreamParams;

/// The default honest label (FR-120). Follows the on-device engine's `engine-model`
/// convention (`whisper-large-v3-turbo`) so the console can show either without special
/// cases, while remaining unmistakably a different engine.
pub const DEEPGRAM_LABEL: &str = "deepgram-nova-3";

/// What the console must say once cloud transcription has given up and the transcript is
/// coming from the on-device engine instead.
///
/// The operator asked for cloud transcription and is getting something else. Silence there
/// reads as though the fallback were what they asked for — so the notice is a constant here,
/// beside the state that triggers it, rather than a string invented at the render site where
/// it could drift or be forgotten. It names the cause and it names the consequence, because
/// only one of those is enough to mislead.
///
/// This mirrors the sermon-notes lane's degraded-fallback notice deliberately: the two halves
/// of the same panel should say the same kind of thing in the same voice.
pub const DEGRADED_FALLBACK_NOTICE: &str = "Cloud transcription could not be reached. The \
     transcript below is coming from the on-device engine instead.";

/// A [`TranscriptProvider`] whose `poll` drains segments the Deepgram socket has queued.
/// Swapping this in for the on-device provider never touches the presentation core.
#[derive(Debug, Clone)]
pub struct CloudTranscriptProvider {
    queue: SegmentQueue,
    label: String,
}

impl CloudTranscriptProvider {
    /// A provider draining `queue`, labelled from the model actually being requested — so the
    /// label the console shows cannot drift away from what is really on the wire.
    pub fn new(queue: SegmentQueue, params: &StreamParams) -> Self {
        CloudTranscriptProvider {
            queue,
            label: format!("deepgram-{}", params.model),
        }
    }

    /// A provider with an explicit label (tests, and any future non-default disclosure).
    pub fn with_label(queue: SegmentQueue, label: impl Into<String>) -> Self {
        CloudTranscriptProvider {
            queue,
            label: label.into(),
        }
    }

    /// The queue this provider drains — the handle the transport pushes into.
    pub fn queue(&self) -> &SegmentQueue {
        &self.queue
    }
}

impl TranscriptProvider for CloudTranscriptProvider {
    fn label(&self) -> &str {
        &self.label
    }

    /// Drain what the socket has queued. **Never blocks on the network**: it takes the
    /// queue's mutex, moves the pending segments out, and returns.
    fn poll(&mut self) -> Vec<ProviderSegment> {
        self.queue.drain()
    }
}

/// Where a streaming session currently is. The console reads this to say honestly what is
/// happening — including, and especially, that it has stopped.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum SessionState {
    /// Not started.
    #[default]
    Idle,
    /// Opening the socket (first attempt).
    Connecting,
    /// Connected and receiving transcripts.
    Streaming,
    /// The socket dropped; waiting to retry. `attempt` is zero-based, `of` is the bound —
    /// both carried so the console can say "2 of 5" rather than an unbounded-looking spinner.
    Reconnecting { attempt: u32, of: u32 },
    /// Stopped on request.
    Stopped,
    /// Stopped for good. Carries what the operator should do and a message safe to display —
    /// never the credential.
    Failed {
        action: OperatorAction,
        message: String,
    },
}

impl SessionState {
    /// Whether transcripts are arriving right now.
    pub fn is_streaming(&self) -> bool {
        matches!(self, SessionState::Streaming)
    }

    /// Whether the session has stopped for good — not merely paused between retries. The
    /// console needs this distinction to decide between "reconnecting…" and an actionable
    /// message.
    pub fn is_terminal(&self) -> bool {
        matches!(self, SessionState::Stopped | SessionState::Failed { .. })
    }
}

/// A shared, cheaply-readable handle on the current [`SessionState`].
///
/// Bounded by construction: exactly one state, replaced rather than accumulated, so polling
/// it at 1 Hz for three hours retains nothing.
#[derive(Debug, Clone, Default)]
pub struct SessionStatus {
    inner: Arc<Mutex<SessionState>>,
}

impl SessionStatus {
    /// A status starting at [`SessionState::Idle`].
    pub fn new() -> Self {
        SessionStatus::default()
    }

    /// The current state.
    pub fn get(&self) -> SessionState {
        self.inner.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }

    /// Replace the current state.
    pub fn set(&self, state: SessionState) {
        *self.inner.lock().unwrap_or_else(|e| e.into_inner()) = state;
    }
}

// Tests live in `tests/test_provider.rs` (public-API integration tests).
