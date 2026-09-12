//! SelahCue application wiring.
//!
//! [`LiveController`] maps RBAC-checked LAN control commands onto the presenter and
//! service plan, so a remote/mobile controller drives the audience output. With the
//! `server` feature, [`handler_for`] plugs it into the pinned-TLS control server.

#![forbid(unsafe_code)]

mod controller;
pub mod keymap;
mod operator;
pub mod sermon_note_store;
pub mod transcript_pump;
pub mod transcript_sink;

pub use controller::{
    ControllerReply, ControllerSnapshot, LiveController, Screen, ScreenRegistry, ScreenRole,
    AUDIENCE_SCREENS, IDENTIFY_TTL, MAX_SAVED_THEMES, MAX_SCREENS, MAX_THEME_NAME_LEN,
};
pub use keymap::{CanonicalAction, KeyPress, Keymap};
pub use operator::{ItemView, OperatorShell, OperatorView};
pub use sermon_note_store::{NullSermonNoteStore, SermonNoteStore};
pub use transcript_pump::pump_transcript;
pub use transcript_sink::{
    BatchingTranscriptWriter, EpochClock, MonotonicClock, NullTranscriptSink, SystemEpochClock,
    SystemMonotonicClock, TranscriptSink, TranscriptStoreWriter, FLUSH_INTERVAL,
    FLUSH_SEGMENT_THRESHOLD, MAX_PENDING_SEGMENTS, MAX_PENDING_SEGMENT_TEXT_LEN,
};

#[cfg(feature = "server")]
pub use controller::handler_for;
#[cfg(feature = "server")]
pub use operator::RemoteOperator;
