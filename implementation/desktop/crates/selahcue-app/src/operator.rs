//! The operator control surface: a UI-agnostic view-model + an ergonomic action
//! shell over the shared [`LiveController`].
//!
//! This is the "Rust core ↔ operator-UI" contract (ADR-0003). The Tauri operator
//! shell binds its buttons/plan-list to [`OperatorView`] and calls [`OperatorShell`]
//! methods; the same surface is exercised directly by unit tests, so the operator
//! logic is verified independently of any GUI (which can't be runtime-tested here).

use crate::controller::LiveController;
use selahcue_lan::protocol::{Command, OperatorStateView, PlanItemView, TimerSnapshot};
use serde::Serialize;
use std::sync::{Arc, Mutex};

/// One plan item as the operator UI renders it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ItemView {
    /// Stable plan-item id (what the UI sends back to `select`).
    pub id: u64,
    /// Stable item-kind tag (e.g. `"song"`, `"scripture"`), for an icon/label.
    pub kind: String,
    pub title: String,
    /// This item is currently on the audience (Live) output.
    pub is_live: bool,
    /// This item is currently staged in Preview.
    pub is_staged: bool,
}

/// A serializable snapshot of everything the operator UI needs to render: the plan,
/// which item is Live vs staged in Preview, and the blackout state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct OperatorView {
    pub plan_name: String,
    pub items: Vec<ItemView>,
    /// Index into `items` currently on Live, if any.
    pub live_index: Option<usize>,
    /// Index into `items` currently staged in Preview, if any (`None` when Preview
    /// holds a non-plan slide such as a staged scripture).
    pub staged_index: Option<usize>,
    pub blackout: bool,
    /// The active timer, if one is running (updated by [`LiveController::tick`]).
    pub timer: Option<TimerSnapshot>,
    /// The scripture reference staged in Preview, when Preview holds one.
    pub staged_scripture: Option<String>,
    /// The scripture reference on the Live output, when Live shows one.
    pub live_scripture: Option<String>,
    /// A removed-but-still-on-screen plan item's title on Live (a free slide).
    pub live_free_text: Option<String>,
    /// Physical outputs and their display assignments (desktop host only).
    pub outputs: Vec<selahcue_lan::protocol::OutputStatusView>,
    /// Attached physical displays for the assignment picker (desktop host only).
    pub displays: Vec<selahcue_lan::protocol::DisplayView>,
}

/// An ergonomic, UI-facing wrapper over the shared [`LiveController`]. Each action
/// applies the corresponding control command and returns the fresh [`OperatorView`]
/// so the UI can re-render from a single round trip.
///
/// Cloning yields another handle to the *same* controller (it is an `Arc`), so once an
/// output window is given a clone it and the operator shell would drive one live state.
/// (In this batch the Tauri shell drives its own in-process controller; wiring it to the
/// on-screen output window is a later slice.)
#[derive(Clone)]
pub struct OperatorShell {
    controller: Arc<Mutex<LiveController>>,
}

impl OperatorShell {
    /// Wrap a shared controller.
    pub fn new(controller: Arc<Mutex<LiveController>>) -> Self {
        OperatorShell { controller }
    }

    /// Run `f` under the controller lock, recovering from a poisoned lock (a prior
    /// panic elsewhere) rather than propagating it — the operator UI must stay usable.
    fn with<R>(&self, f: impl FnOnce(&mut LiveController) -> R) -> R {
        let mut guard = self.controller.lock().unwrap_or_else(|e| e.into_inner());
        f(&mut guard)
    }

    fn act(&self, command: &Command) -> OperatorView {
        self.with(|c| {
            let _ = c.apply(command);
            c.operator_view()
        })
    }

    /// The current snapshot without changing anything (for initial render / refresh).
    pub fn view(&self) -> OperatorView {
        self.with(|c| c.operator_view())
    }

    /// Stage the next plan item in Preview.
    pub fn next(&self) -> OperatorView {
        self.act(&Command::Next)
    }

    /// Stage the previous plan item in Preview.
    pub fn previous(&self) -> OperatorView {
        self.act(&Command::Previous)
    }

    /// Commit whatever is staged to the Live output.
    pub fn go_live(&self) -> OperatorView {
        self.act(&Command::GoLive)
    }

    /// Stage a specific plan item (by id) in Preview.
    pub fn select(&self, item_id: u64) -> OperatorView {
        self.act(&Command::SelectItem { item_id })
    }

    /// Clear the Live output back to idle.
    pub fn clear(&self) -> OperatorView {
        self.act(&Command::Clear)
    }

    /// Set the blackout state of the Live output.
    pub fn blackout(&self, on: bool) -> OperatorView {
        self.act(&Command::Blackout { on })
    }

    /// Start a countdown timer of `seconds` on the Live output.
    pub fn start_timer(&self, seconds: u32) -> OperatorView {
        self.act(&Command::StartTimer { seconds })
    }

    /// Stop and clear the active timer.
    pub fn stop_timer(&self) -> OperatorView {
        self.act(&Command::StopTimer)
    }

    /// Append a plan item (Operator-only via RBAC on the remote path).
    pub fn add_item(&self, kind: &str, title: &str) -> OperatorView {
        self.act(&Command::AddItem {
            kind: kind.into(),
            title: title.into(),
        })
    }

    /// Remove a plan item by id.
    pub fn remove_item(&self, item_id: u64) -> OperatorView {
        self.act(&Command::RemoveItem { item_id })
    }

    /// Move a plan item to a new position.
    pub fn move_item(&self, item_id: u64, to: u32) -> OperatorView {
        self.act(&Command::MoveItem { item_id, to })
    }

    /// Rename a plan item.
    pub fn rename_item(&self, item_id: u64, title: &str) -> OperatorView {
        self.act(&Command::RenameItem {
            item_id,
            title: title.into(),
        })
    }

    /// Stage a scripture reference in Preview (its verse text composes from the
    /// chosen bundled translation; `None` = the KJV default).
    pub fn stage_scripture(&self, reference: &str, translation: Option<&str>) -> OperatorView {
        self.act(&Command::StageScripture {
            reference: reference.into(),
            translation: translation.map(Into::into),
        })
    }

    /// Show the identify overlay on every physical output.
    pub fn identify_outputs(&self) -> OperatorView {
        self.act(&Command::IdentifyOutputs)
    }

    /// Assign an output role ("main"/"stage") to a physical display.
    pub fn assign_output(&self, role: &str, display_key: &str) -> OperatorView {
        self.act(&Command::AssignOutput {
            role: role.into(),
            display_key: display_key.into(),
        })
    }

    /// Search scripture: reference parse first, then keyword search over the
    /// bundled translation. Returns display references (stageable directly).
    pub fn scripture_search(&self, query: &str, translation: Option<&str>) -> Vec<String> {
        self.with(|c| {
            match c.apply(&Command::ScriptureSearch {
                query: query.into(),
                translation: translation.map(Into::into),
            }) {
                crate::ControllerReply::Message(
                    selahcue_lan::protocol::ServerMessage::ScriptureResults { references, .. },
                ) => references,
                _ => Vec::new(),
            }
        })
    }
}

// --- Wire conversions: the local view-model <-> the protocol DTO carried over the LAN
// control link, so the same `OperatorView` type renders whether the operator drives an
// in-process controller or a remote host output window. ---

impl From<ItemView> for PlanItemView {
    fn from(i: ItemView) -> Self {
        PlanItemView {
            id: i.id,
            kind: i.kind,
            title: i.title,
            is_live: i.is_live,
            is_staged: i.is_staged,
        }
    }
}

impl From<PlanItemView> for ItemView {
    fn from(i: PlanItemView) -> Self {
        ItemView {
            id: i.id,
            kind: i.kind,
            title: i.title,
            is_live: i.is_live,
            is_staged: i.is_staged,
        }
    }
}

impl From<OperatorView> for OperatorStateView {
    fn from(v: OperatorView) -> Self {
        OperatorStateView {
            plan_name: v.plan_name,
            items: v.items.into_iter().map(Into::into).collect(),
            live_index: v.live_index,
            staged_index: v.staged_index,
            blackout: v.blackout,
            timer: v.timer,
            staged_scripture: v.staged_scripture,
            live_scripture: v.live_scripture,
            live_free_text: v.live_free_text,
            outputs: v.outputs,
            displays: v.displays,
        }
    }
}

impl From<OperatorStateView> for OperatorView {
    fn from(v: OperatorStateView) -> Self {
        OperatorView {
            plan_name: v.plan_name,
            items: v.items.into_iter().map(Into::into).collect(),
            live_index: v.live_index,
            staged_index: v.staged_index,
            blackout: v.blackout,
            timer: v.timer,
            staged_scripture: v.staged_scripture,
            live_scripture: v.live_scripture,
            live_free_text: v.live_free_text,
            outputs: v.outputs,
            displays: v.displays,
        }
    }
}

/// A remote operator: drives the **host's authoritative controller** over the pinned-TLS
/// control link and renders from the host's [`OperatorView`]. This is how the Tauri
/// operator shell (and, later, the mobile client) drive the on-screen output window —
/// the host owns the one live state; this is a thin, authenticated remote.
#[cfg(feature = "server")]
pub struct RemoteOperator {
    client: selahcue_lan::ControlClient,
}

#[cfg(feature = "server")]
impl RemoteOperator {
    /// Connect + authenticate to the host output window's control server, trusting it
    /// only if its certificate matches `pin`.
    pub async fn connect(
        addr: std::net::SocketAddr,
        server_name: &str,
        pin: selahcue_lan::CertPin,
        device_id: &str,
        token: &str,
    ) -> Result<Self, selahcue_lan::TransportError> {
        Ok(Self {
            client: selahcue_lan::ControlClient::connect(addr, server_name, pin, device_id, token)
                .await?,
        })
    }

    /// Fetch the current operator view from the host (no state change).
    pub async fn view(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.request_state().await
    }

    /// Stage the next plan item in the host's Preview.
    pub async fn next(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Next).await
    }

    /// Stage the previous plan item in the host's Preview.
    pub async fn previous(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Previous).await
    }

    /// Commit whatever is staged to the host's Live output.
    pub async fn go_live(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::GoLive).await
    }

    /// Stage a specific plan item (by id) in the host's Preview.
    pub async fn select(
        &mut self,
        item_id: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SelectItem { item_id }).await
    }

    /// Clear the host's Live output.
    pub async fn clear(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Clear).await
    }

    /// Set the host's blackout state.
    pub async fn blackout(
        &mut self,
        on: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Blackout { on }).await
    }

    /// Start a countdown timer of `seconds` on the host's Live output.
    pub async fn start_timer(
        &mut self,
        seconds: u32,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::StartTimer { seconds }).await
    }

    /// Stop and clear the host's active timer.
    pub async fn stop_timer(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::StopTimer).await
    }

    /// Append a plan item on the host (requires the Operator role).
    pub async fn add_item(
        &mut self,
        kind: &str,
        title: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::AddItem {
            kind: kind.into(),
            title: title.into(),
        })
        .await
    }

    /// Remove a plan item on the host.
    pub async fn remove_item(
        &mut self,
        item_id: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::RemoveItem { item_id }).await
    }

    /// Move a plan item on the host.
    pub async fn move_item(
        &mut self,
        item_id: u64,
        to: u32,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::MoveItem { item_id, to }).await
    }

    /// Rename a plan item on the host.
    pub async fn rename_item(
        &mut self,
        item_id: u64,
        title: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::RenameItem {
            item_id,
            title: title.into(),
        })
        .await
    }

    /// Stage a scripture reference on the host (verse text from its bundle;
    /// `None` = the KJV default).
    pub async fn stage_scripture(
        &mut self,
        reference: &str,
        translation: Option<&str>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::StageScripture {
            reference: reference.into(),
            translation: translation.map(Into::into),
        })
        .await
    }

    /// Show the identify overlay on the host's physical outputs.
    pub async fn identify_outputs(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::IdentifyOutputs).await
    }

    /// Assign an output role to a physical display on the host.
    pub async fn assign_output(
        &mut self,
        role: &str,
        display_key: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::AssignOutput {
            role: role.into(),
            display_key: display_key.into(),
        })
        .await
    }

    /// Search scripture on the host; returns stageable display references.
    pub async fn scripture_search(
        &mut self,
        query: &str,
        translation: Option<&str>,
    ) -> Result<Vec<String>, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self
            .client
            .command(Command::ScriptureSearch {
                query: query.into(),
                translation: translation.map(Into::into),
            })
            .await?
        {
            ServerMessage::ScriptureResults { references, .. } => Ok(references),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected scripture_results, got: {other:?}"
            ))),
        }
    }

    /// Send a mutating command, then read back the fresh authoritative view. A command
    /// the host denies (RBAC/app) is **not** an error — the returned view simply shows
    /// the unchanged state, which the UI reflects.
    async fn act(
        &mut self,
        command: Command,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self.client.command(command).await? {
            ServerMessage::Ack { .. } | ServerMessage::Denied { .. } => {}
            other => {
                return Err(selahcue_lan::TransportError::Protocol(format!(
                    "unexpected reply to command: {other:?}"
                )))
            }
        }
        self.request_state().await
    }

    async fn request_state(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self.client.command(Command::GetOperatorState).await? {
            ServerMessage::OperatorState { view } => Ok(view.into()),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected operator_state, got: {other:?}"
            ))),
        }
    }
}
