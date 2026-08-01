//! Audio-feedback guard (FR-172): suppress transcription while the app's own audio is
//! playing to a shared output, so SelahCue never transcribes itself (a video's dialogue,
//! a played song) as if it were the preacher.
//!
//! The guard is a shared boolean the host flips when it routes audio to an output device
//! that the capture microphone can hear. The engine consults it before accumulating any
//! captured audio; while suppressed, captured frames are dropped, so no utterance forms.
//! It is a cheap atomic — reading it never blocks the render path.
//!
//! Wiring the host to actually *set* the flag (from the output/audio subsystem) is a
//! documented follow-up seam; this crate provides the mechanism and the gate.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// A shareable suppression flag. Clones share the same underlying atomic, so the host and
/// the engine hold two handles to one switch.
#[derive(Debug, Clone, Default)]
pub struct FeedbackGuard {
    output_active: Arc<AtomicBool>,
}

impl FeedbackGuard {
    /// A guard that starts un-suppressed (output not active).
    pub fn new() -> Self {
        FeedbackGuard {
            output_active: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Signal whether the app is currently playing audio to a shared output. The host calls
    /// this from its output/audio path; `true` suppresses ingestion.
    pub fn set_output_active(&self, active: bool) {
        self.output_active.store(active, Ordering::Relaxed);
    }

    /// Whether ingestion is currently suppressed (output audio is active).
    pub fn is_suppressed(&self) -> bool {
        self.output_active.load(Ordering::Relaxed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_unsuppressed() {
        assert!(!FeedbackGuard::new().is_suppressed());
    }

    #[test]
    fn toggles_and_shares_across_clones() {
        let a = FeedbackGuard::new();
        let b = a.clone();
        a.set_output_active(true);
        assert!(a.is_suppressed());
        // The clone sees the same switch.
        assert!(b.is_suppressed());
        b.set_output_active(false);
        assert!(!a.is_suppressed());
    }
}
