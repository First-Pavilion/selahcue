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
    /// Edit the service plan (add/remove/move/rename items). Also covers the session-recovery
    /// commands that wholesale-replace live/session state (`RestoreAutosave`/`Resume`/
    /// `StartClean`/`UndoPlan`/`RedoPlan`, 86ajy0hxg) — an earlier version of this doc said
    /// "never the live output," which stopped being true the moment those five commands were
    /// added here (Sana, PR #102 security review — S-2): `RestoreAutosave` and `Resume` DO
    /// change what is live, via `LiveController::restore`'s `presenter.go_live()`. Not
    /// exploitable in practice today — every role holding `EditPlan` also holds `GoLive` and
    /// `Blackout` (see `permission_sets_are_strictly_ordered_supersets` /
    /// `edit_plan_implies_go_live_and_blackout_for_every_role` in `test_rbac.rs`, which PIN
    /// that containment rather than leave it accidental) — but a future role table that granted
    /// `EditPlan` without those two would silently gain live-output control too.
    EditPlan,
    /// Pair, revoke, or re-role other devices.
    ManageDevices,
    /// Enumerate/assign physical outputs and trigger identify (host config).
    ConfigureOutputs,
    /// Persist (create, or wholesale-replace) a sermon-note draft's full content INCLUDING
    /// its `ai_generated`/`disclosure`/`provider`/`model` provenance (`SaveSermonNoteDraft`
    /// — PR #33 review, Sana N2 — Medium; also `StageSermonNoteRegeneration`/
    /// `ConfirmSermonNoteRegeneration`/`DiscardSermonNoteRegeneration`, FR-129, 86akgqdx8,
    /// the same reasoning extended to the regenerate-with-retention trio). Operator-only:
    /// deliberately narrower than `Transcribe`, which still governs
    /// `LoadSermonNoteDraft`/`UpdateSermonNoteDraft`/`GetActiveTranscriptId`. See
    /// [`Command`]'s doc on `SaveSermonNoteDraft` for the full reasoning — in short, Save is
    /// the one command that can attach a label/disclosure to NEW content or
    /// wholesale-replace an already-persisted (possibly operator-edited) draft, and its
    /// only legitimate caller today is the operator console's own `generate_sermon_notes`
    /// flow (the same is true of Stage/Confirm/Discard).
    SaveSermonNotes,
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
                SaveSermonNotes,
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
        Command::IngestTranscript { .. }
        | Command::StartTranscript { .. }
        | Command::EndTranscript
        // Sermon-note draft READ/EDIT persistence (86akgqdv0) reads/writes AI-derived content
        // generated from congregation speech — the same privilege tier as feeding/opening the
        // transcript stream that content is derived from, never a narrower or wider one.
        // `SaveSermonNoteDraft` is DELIBERATELY EXCLUDED from this arm — see below.
        | Command::GetActiveTranscriptId
        | Command::LoadSermonNoteDraft { .. }
        | Command::UpdateSermonNoteDraft { .. } => Transcribe,
        // Persisting (creating/replacing) a draft's full content + provenance is narrower than
        // the above (PR #33 review, Sana N2 — Medium; see `SaveSermonNotes`'s and
        // `Command::SaveSermonNoteDraft`'s doc comments for the full reasoning). Reconsidered
        // from this feature's original "same tier as IngestTranscript" design specifically
        // because Save — unlike Load/Update — can plant a fully-formed, validly-labelled but
        // FABRICATED "AI-generated" draft, or silently discard the operator's own edits, from
        // any Transcribe-tier Producer device. The operator console's own generate flow is the
        // only legitimate caller today.
        // The FR-129 regenerate-with-retention trio (86akgqdx8) is the SAME tier as Save,
        // for the same reasoning: Stage attaches new provenance to content the operator has
        // not reviewed yet, Confirm replaces the accepted draft outright, and Discard is
        // kept at this tier for consistency with the rest of its own lifecycle even though
        // it cannot itself alter accepted content — see each command's own doc comment.
        Command::SaveSermonNoteDraft { .. }
        | Command::StageSermonNoteRegeneration { .. }
        | Command::ConfirmSermonNoteRegeneration { .. }
        | Command::DiscardSermonNoteRegeneration { .. } => SaveSermonNotes,
        Command::GetState
        | Command::GetOperatorState
        | Command::GetConsoleThumbnails { .. }
        | Command::GetScreenFrame { .. }
        // Listing the autosave-slot history (FR-005; 86ajy0hxg) is read-only — same tier as any
        // other state read. RESTORING a slot is a separate, EditPlan-tier command below.
        | Command::ListAutosaveSlots => Monitor,
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
        | Command::ImportPlan { .. }
        // Item Undo/Redo (86ajy0hxg) reverse/replay a plan edit — the same EditPlan privilege
        // as the edits themselves; no role may undo a change it could not have made.
        | Command::UndoPlan
        | Command::RedoPlan
        // Restoring an autosave slot (FR-005) or the crash-loop preserved session (FR-169) both
        // wholesale-replace the plan/session state — at least as consequential as any other
        // plan-lifecycle action in this arm (NewPlan/ImportPlan), so the SAME EditPlan
        // privilege, Operator-only. No new `Permission` variant: every one of these five is
        // Operator-only in effect already (every candidate tier in this table below Operator
        // lacks EditPlan), so a dedicated "ManageSession" permission would not change a single
        // role's verdict — it would only grow the table's surface for no observable behaviour
        // change.
        | Command::RestoreAutosave { .. }
        | Command::Resume
        | Command::StartClean => EditPlan,
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
/// `Role::permissions()` table, so changing either moves both.
///
/// **It does not remove every expression only one side consults, and an earlier version of this
/// comment claimed it did.** The verdict is pinned to `PLAN_EDIT_PROBE` alone; the mapping for
/// every OTHER plan-edit command is still an expression the gate consults and this does not.
/// What closes that is a test (`test_rbac.rs`) asserting all of them agree with this verdict for
/// all four roles — a guard that moved from the type system into a test, rather than one that
/// vanished. That test's command list is hand-maintained, which is where the residual risk now
/// sits.
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
