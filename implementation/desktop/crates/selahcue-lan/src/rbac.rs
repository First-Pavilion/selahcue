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
        // FollowScripture can advance the LIVE output (only when a scripture is already
        // live), so it requires GoLive — never SearchScripture (no escalation, 86ajtwq2b).
        // PresentAuthoredSlide puts a deck slide on the LIVE audience output — the same
        // "changes what the audience sees" privilege as GoLive/FollowScripture, no escalation.
        Command::GoLive
        | Command::FollowScripture { .. }
        | Command::PresentAuthoredSlide { .. } => GoLive,
        Command::Next
        | Command::Previous
        | Command::SelectItem { .. }
        | Command::SelectSlide { .. } => Navigate,
        Command::Clear => ClearLive,
        Command::Blackout { .. } => Blackout,
        Command::StartTimer { .. }
        | Command::StopTimer
        | Command::AdjustTimer { .. }
        | Command::PauseTimer
        | Command::ResumeTimer => Timer,
        Command::ScriptureSearch { .. }
        | Command::StageScripture { .. }
        | Command::GetChapter { .. } => SearchScripture,
        // Approving / dismissing a detection merely stages or drops a scripture
        // candidate — the same privilege as staging scripture, not going live.
        Command::ApproveDetection { .. } | Command::DismissDetection { .. } => SearchScripture,
        Command::IngestTranscript { .. } => Transcribe,
        Command::GetState
        | Command::GetOperatorState
        | Command::GetConsoleThumbnails { .. }
        | Command::GetScreenFrame { .. } => Monitor,
        Command::AddItem { .. }
        | Command::RemoveItem { .. }
        | Command::MoveItem { .. }
        | Command::RenameItem { .. }
        // Linking a plan item's content (scripture/deck/media) is plan editing, not an
        // output/go-live authority — the same EditPlan privilege (ADR-0020 follow-up).
        | Command::SetItemContent { .. }
        // Owner + planned duration are plan metadata edits — the same EditPlan privilege (FR-004).
        | Command::SetItemOwner { .. }
        | Command::SetItemDuration { .. }
        // Publish / hand-off and the plan lifecycle actions (FR-006, FR-005) are statements
        // about the plan DOCUMENT — none of them changes the live output — so they carry the
        // SAME EditPlan privilege as any other plan edit. No new permission: no role in the
        // table distinguishes publishing from editing, and the view-only frame hides
        // "edit/add/reorder/publish" as one group, so a separate permission would express a
        // distinction the product does not make.
        | Command::PublishPlan
        | Command::NewPlan { .. }
        | Command::TemplatePlan { .. }
        | Command::DuplicatePlan { .. }
        | Command::ImportPlan { .. } => EditPlan,
        Command::IdentifyOutputs
        | Command::AssignOutput { .. }
        | Command::SetTheme { .. }
        | Command::SetCustomTheme { .. }
        | Command::SetItemTheme { .. }
        | Command::SaveTheme { .. }
        | Command::DeleteTheme { .. }
        | Command::SetScreenTheme { .. }
        | Command::SetScreenEnabled { .. }
        | Command::AddScreen { .. }
        | Command::RemoveScreen { .. }
        // Per-output config (orientation/scale/mirror/delay/frame-rate/safe-area/layers) is
        // the SAME output-config authority — Operator-only, denied for everyone below.
        | Command::SetOutputOrientation { .. }
        | Command::SetOutputScaleFit { .. }
        | Command::SetOutputMirror { .. }
        | Command::SetOutputDelay { .. }
        | Command::SetOutputFrameRate { .. }
        | Command::SetOutputSafeArea { .. }
        | Command::SetScreenLayerVisible { .. }
        // Configuring a screen's NDI output is the SAME output-config authority — Operator-only.
        | Command::SetNdiOutput { .. }
        // The stage/confidence template + production message are stage-OUTPUT config — the same
        // Operator-only authority (they never touch the audience output).
        | Command::SetStageTemplate { .. }
        | Command::SetStageMessage { .. } => ConfigureOutputs,
        // Remote Control device management is the operator's authority over WHO may connect and
        // with what role — the highest control-plane privilege, Operator-only (86ajxer8n).
        Command::ListRemoteDevices
        | Command::ApprovePairing { .. }
        | Command::DenyPairing { .. }
        | Command::RevokeSession { .. }
        | Command::SetSessionRole { .. }
        | Command::NewPairingCode => ManageDevices,
    }
}

/// The authorization choke point: may `role` perform `cmd`?
pub fn authorize(role: Role, cmd: &Command) -> bool {
    role.can(required_permission(cmd))
}

/// The plan-edit command [`can_edit_plan`] asks the choke point about.
///
/// Any command from the `EditPlan` arm would do; this one is a plain `u64` so the verdict
/// allocates nothing. Which one it is must not matter, and `test_rbac.rs` pins that it does not
/// by checking every plan-edit command against the verdict for every role.
const PLAN_EDIT_PROBE: Command = Command::RemoveItem { item_id: 0 };

/// Whether `role` may edit the plan document — the verdict the operator view reports as
/// `can_edit`, which a client uses to decide whether to SHOW the edit / add / reorder / publish
/// controls at all (view-only frame `612:342`).
///
/// # Why it runs `authorize` instead of stating the rule
///
/// The obvious implementations — `role == Role::Operator`, or `role.can(Permission::EditPlan)`
/// — are both *copies* of the policy, and this repository has already been bitten by a control
/// that re-derived a predicate instead of consuming it. Going through `authorize` means the
/// affordance and the gate read the same `required_permission` match and the same
/// `Role::permissions()` table: changing either moves both, and there is no expression left
/// that only one of them consults.
///
/// # This is an affordance, not a gate
///
/// It decides what a client offers, never what the host accepts. Enforcement is unchanged and
/// unconditional: the server calls `authorize` on every inbound command before the handler
/// runs, so a client that ignores this verdict and sends a plan edit as a Viewer is refused. It
/// is reported so that clients stop transcribing the permission table — not so that they become
/// responsible for it.
pub fn can_edit_plan(role: Role) -> bool {
    authorize(role, &PLAN_EDIT_PROBE)
}
