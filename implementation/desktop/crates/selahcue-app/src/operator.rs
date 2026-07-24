//! The operator control surface: a UI-agnostic view-model + an ergonomic action
//! shell over the shared [`LiveController`].
//!
//! This is the "Rust core ↔ operator-UI" contract (ADR-0003). The Tauri operator
//! shell binds its buttons/plan-list to [`OperatorView`] and calls [`OperatorShell`]
//! methods; the same surface is exercised directly by unit tests, so the operator
//! logic is verified independently of any GUI (which can't be runtime-tested here).

use crate::controller::LiveController;
use selahcue_lan::protocol::{Command, OperatorStateView, PlanItemView};
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
    pub async fn select(&mut self, item_id: u64) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SelectItem { item_id }).await
    }

    /// Clear the host's Live output.
    pub async fn clear(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Clear).await
    }

    /// Set the host's blackout state.
    pub async fn blackout(&mut self, on: bool) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::Blackout { on }).await
    }

    /// Send a mutating command, then read back the fresh authoritative view. A command
    /// the host denies (RBAC/app) is **not** an error — the returned view simply shows
    /// the unchanged state, which the UI reflects.
    async fn act(&mut self, command: Command) -> Result<OperatorView, selahcue_lan::TransportError> {
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
