//! The operator control surface: a UI-agnostic view-model + an ergonomic action
//! shell over the shared [`LiveController`].
//!
//! This is the "Rust core ↔ operator-UI" contract (ADR-0003). The Tauri operator
//! shell binds its buttons/plan-list to [`OperatorView`] and calls [`OperatorShell`]
//! methods; the same surface is exercised directly by unit tests, so the operator
//! logic is verified independently of any GUI (which can't be runtime-tested here).

use crate::controller::LiveController;
use selahcue_lan::protocol::Command;
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
