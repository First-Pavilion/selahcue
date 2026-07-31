//! Role-based access control for the LAN control link (FR-119; ADR-0009).
//!
//! Every controller device is granted a [`Role`] at pairing time. Each inbound
//! [`Command`](crate::protocol::Command) maps to exactly one required
//! [`Permission`]; [`authorize`] is the single choke point the server calls before
//! acting on a command. The mapping is data, not scattered `if role == …` checks,
//! so the policy is auditable in one place.

use crate::protocol::Command;
use serde::{Deserialize, Serialize};

/// What a paired device is allowed to do. Ordered most-privileged first.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    /// Full control, including going live, editing, and managing other devices.
    Operator,
    /// Drives live output (go-live / navigate / blackout / timers) but cannot
    /// manage devices or edit the underlying plan.
    Producer,
    /// Prepares content — searches and queues scripture, stages items — but cannot
    /// push to the live output.
    Assistant,
    /// Read-only monitoring (confidence/state), no control.
    Viewer,
}

/// A discrete capability a [`Role`] may or may not hold.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Permission {
    /// Push the current selection to the live output.
    GoLive,
    /// Move through the plan / slides (next, previous, select) — stages Preview, does
    /// not itself change the live output.
    Navigate,
    /// Wipe all live output layers to empty (a disruptive live-output change, so it
    /// is gated separately from Preview navigation).
    ClearLive,
    /// Toggle blackout of the live output.
    Blackout,
    /// Drive timers on the live output.
    Timer,
    /// Search and stage scripture (does not itself push live). Also gates approving or
    /// dismissing an auto-detected scripture (both merely stage / drop a candidate).
    SearchScripture,
    /// Drive live transcription: feed transcript segments into the stream (the STT
    /// ingestion channel). Distinct from `SearchScripture` so transcription can be
    /// granted (or withheld) independently of scripture staging.
    Transcribe,
    /// Observe live/preview state.
    Monitor,
    /// Edit the service plan (add/remove/move/rename items) — never the live output.
    EditPlan,
    /// Pair, revoke, or re-role other devices.
    ManageDevices,
    /// Enumerate/assign physical outputs and trigger identify (host config).
    ConfigureOutputs,
}

impl Role {
    /// The capabilities this role holds. Higher roles are supersets of lower ones.
    pub fn permissions(self) -> &'static [Permission] {
        use Permission::*;
        match self {
            Role::Operator => &[
                GoLive,
                Navigate,
                ClearLive,
                Blackout,
                Timer,
                SearchScripture,
                Transcribe,
                Monitor,
                ManageDevices,
                EditPlan,
                ConfigureOutputs,
            ],
            Role::Producer => &[
                GoLive,
                Navigate,
                ClearLive,
                Blackout,
                Timer,
                SearchScripture,
                Transcribe,
                Monitor,
            ],
            Role::Assistant => &[SearchScripture, Navigate, Monitor],
            Role::Viewer => &[Monitor],
        }
    }

    /// Whether this role holds `permission`.
    pub fn can(self, permission: Permission) -> bool {
        self.permissions().contains(&permission)
    }
}

/// The single permission a command requires to be accepted.
pub fn required_permission(cmd: &Command) -> Permission {
    use Permission::*;
    match cmd {
        Command::GoLive => GoLive,
        Command::Next | Command::Previous | Command::SelectItem { .. } => Navigate,
        Command::Clear => ClearLive,
        Command::Blackout { .. } => Blackout,
        Command::StartTimer { .. } | Command::StopTimer | Command::AdjustTimer { .. } => Timer,
        Command::ScriptureSearch { .. }
        | Command::StageScripture { .. }
        | Command::GetChapter { .. } => SearchScripture,
        // Approving / dismissing a detection merely stages or drops a scripture
        // candidate — the same privilege as staging scripture, not going live.
        Command::ApproveDetection { .. } | Command::DismissDetection { .. } => SearchScripture,
        Command::IngestTranscript { .. } => Transcribe,
        Command::GetState | Command::GetOperatorState => Monitor,
        Command::AddItem { .. }
        | Command::RemoveItem { .. }
        | Command::MoveItem { .. }
        | Command::RenameItem { .. } => EditPlan,
        Command::IdentifyOutputs
        | Command::AssignOutput { .. }
        | Command::SetTheme { .. }
        | Command::SetCustomTheme { .. }
        | Command::SetItemTheme { .. }
        | Command::SaveTheme { .. }
        | Command::DeleteTheme { .. }
        | Command::SetScreenTheme { .. } => ConfigureOutputs,
    }
}

/// The authorization choke point: may `role` perform `cmd`?
pub fn authorize(role: Role, cmd: &Command) -> bool {
    role.can(required_permission(cmd))
}
