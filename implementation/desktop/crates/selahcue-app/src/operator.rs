//! The operator control surface: a UI-agnostic view-model + an ergonomic action
//! shell over the shared [`LiveController`].
//!
//! This is the "Rust core ↔ operator-UI" contract (ADR-0003). The Tauri operator
//! shell binds its buttons/plan-list to [`OperatorView`] and calls [`OperatorShell`]
//! methods; the same surface is exercised directly by unit tests, so the operator
//! logic is verified independently of any GUI (which can't be runtime-tested here).

use crate::controller::LiveController;
use selahcue_lan::protocol::{
    Command, DetectionView, OperatorStateView, PlanItemView, SavedThemeView, ScreenThemeView,
    TimerSnapshot, TranscriptSegmentView,
};
use selahcue_present::FrameBuffer;
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
    /// Slide count for multi-slide items (songs, S8-1); absent = single slide.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_count: Option<u32>,
    /// Current within-item slide (0-based), present for the live/staged item.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<u32>,
    /// Per-item theme override (built-in name), if this item overrides the global
    /// theme (S8-3d); absent = the global theme.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
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
    /// Translation codes the HOST can stage/search (drives the picker).
    pub translations: Vec<String>,
    /// The active audience-output theme name (drives the picker's selection).
    pub theme: String,
    /// The theme names the HOST offers (drives the picker's options).
    pub themes: Vec<String>,
    /// The saved (named custom) themes in the library (86ajq4xmy). A `SavedThemeView`
    /// (not a tuple) so it serializes as `{name, theme_json}` — the shape the Theme
    /// Designer reads, and identical to the wire `OperatorStateView.saved_themes`.
    pub saved_themes: Vec<SavedThemeView>,
    /// The per-SCREEN theme map (86ajq321k): each Audience screen and its assigned theme,
    /// so the Screens page shows a distinct theme per screen.
    pub screen_themes: Vec<ScreenThemeView>,
    /// The recent live-transcript segments (bounded tail, oldest first) — the transcript
    /// panel (R3).
    pub transcript: Vec<TranscriptSegmentView>,
    /// The pending scripture-detection approval queue (R4) — candidates to one-click stage.
    pub detections: Vec<DetectionView>,
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
            // The stand-alone shell has no output window driving frames: tick
            // here so timers advance in Local/demo mode (the remote path's host
            // ticks every frame; an extra tick is harmless there).
            c.tick(std::time::Instant::now());
            c.operator_view()
        })
    }

    /// The current snapshot without changing anything (for initial render / refresh).
    pub fn view(&self) -> OperatorView {
        self.with(|c| {
            c.tick(std::time::Instant::now());
            c.operator_view()
        })
    }

    /// Downscaled **thumbnails of the current Preview and Live outputs** (86ajtwq28 — the
    /// operator console monitors), each fitted within `max_w × max_h`. A **read-only
    /// readback**: it applies NO command and does NOT tick, so it cannot change what is on
    /// air (rendering the preview must never affect the live output). The frames are
    /// whatever the last action/refresh composited — the true pixels the audience sees,
    /// including blackout / timer / the live scene.
    pub fn console_thumbnails(&self, max_w: u32, max_h: u32) -> (FrameBuffer, FrameBuffer) {
        self.with(|c| {
            let p = c.presenter();
            (
                p.preview_output().thumbnail(max_w, max_h),
                p.live_output().thumbnail(max_w, max_h),
            )
        })
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

    /// Adjust the running countdown by `delta_secs` (e.g. +60 / -60).
    pub fn adjust_timer(&self, delta_secs: i64) -> OperatorView {
        self.act(&Command::AdjustTimer { delta_secs })
    }

    /// Append a plan item (Operator-only via RBAC on the remote path).
    /// `content` is the optional plain-text stanza body for songs (S8-1).
    pub fn add_item(&self, kind: &str, title: &str, content: Option<&str>) -> OperatorView {
        self.act(&Command::AddItem {
            kind: kind.into(),
            title: title.into(),
            content: content.map(Into::into),
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

    /// Feed one live-transcript segment (the STT-provider ingestion channel — the
    /// default provider is operator/host-injected text). Runs scripture detection.
    pub fn ingest_transcript(&self, text: &str, start_ms: u64, end_ms: u64) -> OperatorView {
        self.act(&Command::IngestTranscript {
            text: text.into(),
            start_ms: Some(start_ms),
            end_ms: Some(end_ms),
        })
    }

    /// Approve a queued scripture detection by id: stage its verse in Preview.
    pub fn approve_detection(&self, detection_id: u64) -> OperatorView {
        self.act(&Command::ApproveDetection { detection_id })
    }

    /// Dismiss a queued scripture detection by id without staging it.
    pub fn dismiss_detection(&self, detection_id: u64) -> OperatorView {
        self.act(&Command::DismissDetection { detection_id })
    }

    /// Show the identify overlay on every physical output.
    pub fn identify_outputs(&self) -> OperatorView {
        self.act(&Command::IdentifyOutputs)
    }

    /// Switch the audience-output theme by built-in name (classic/high-contrast/lower-third).
    pub fn set_theme(&self, name: &str) -> OperatorView {
        self.act(&Command::SetTheme { name: name.into() })
    }

    /// Apply a custom audience theme (serialized JSON) from the Theme Designer.
    pub fn set_custom_theme(&self, theme_json: &str) -> OperatorView {
        self.act(&Command::SetCustomTheme {
            theme_json: theme_json.into(),
        })
    }
    /// Set (or clear, with an empty name) a plan item's per-item theme override (S8-3d).
    pub fn set_item_theme(&self, item_id: u64, theme: Option<String>) -> OperatorView {
        self.act(&Command::SetItemTheme { item_id, theme })
    }

    /// Save a NAMED custom theme into the library (86ajq4xmy).
    pub fn save_theme(&self, name: &str, theme_json: &str) -> OperatorView {
        self.act(&Command::SaveTheme {
            name: name.into(),
            theme_json: theme_json.into(),
        })
    }

    /// Delete a saved theme from the library by name (86ajq4xmy).
    pub fn delete_theme(&self, name: &str) -> OperatorView {
        self.act(&Command::DeleteTheme { name: name.into() })
    }

    /// Set (or clear, with an empty name) an Audience screen's own theme (86ajq321k).
    pub fn set_screen_theme(&self, screen: &str, name: &str) -> OperatorView {
        self.act(&Command::SetScreenTheme {
            screen: screen.into(),
            name: name.into(),
        })
    }

    /// Assign an output role ("main"/"stage") to a physical display.
    pub fn assign_output(&self, role: &str, display_key: &str) -> OperatorView {
        self.act(&Command::AssignOutput {
            role: role.into(),
            display_key: display_key.into(),
        })
    }

    /// Search scripture: reference parse first, then keyword search over the
    /// bundled translation. Each hit carries its verse text (stage by reference).
    pub fn scripture_search(
        &self,
        query: &str,
        translation: Option<&str>,
    ) -> Vec<selahcue_lan::protocol::ScriptureHitView> {
        self.with(|c| {
            match c.apply(&Command::ScriptureSearch {
                query: query.into(),
                translation: translation.map(Into::into),
            }) {
                crate::ControllerReply::Message(
                    selahcue_lan::protocol::ServerMessage::ScriptureResults { hits, .. },
                ) => hits,
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
            slide_count: i.slide_count,
            slide_index: i.slide_index,
            theme: i.theme,
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
            slide_count: i.slide_count,
            slide_index: i.slide_index,
            theme: i.theme,
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
            translations: v.translations,
            theme: v.theme,
            themes: v.themes,
            saved_themes: v.saved_themes,
            screen_themes: v.screen_themes,
            transcript: v.transcript,
            detections: v.detections,
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
            translations: v.translations,
            theme: v.theme,
            themes: v.themes,
            saved_themes: v.saved_themes,
            screen_themes: v.screen_themes,
            transcript: v.transcript,
            detections: v.detections,
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

    /// Adjust the host's running countdown by `delta_secs`.
    pub async fn adjust_timer(
        &mut self,
        delta_secs: i64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::AdjustTimer { delta_secs }).await
    }

    /// Append a plan item on the host (requires the Operator role).
    /// `content` is the optional plain-text stanza body for songs (S8-1).
    pub async fn add_item(
        &mut self,
        kind: &str,
        title: &str,
        content: Option<&str>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::AddItem {
            kind: kind.into(),
            title: title.into(),
            content: content.map(Into::into),
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

    /// Feed one live-transcript segment into the host's transcript stream (runs
    /// scripture detection on the host).
    pub async fn ingest_transcript(
        &mut self,
        text: &str,
        start_ms: u64,
        end_ms: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::IngestTranscript {
            text: text.into(),
            start_ms: Some(start_ms),
            end_ms: Some(end_ms),
        })
        .await
    }

    /// Approve a queued scripture detection on the host (stages its verse in Preview).
    pub async fn approve_detection(
        &mut self,
        detection_id: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::ApproveDetection { detection_id }).await
    }

    /// Dismiss a queued scripture detection on the host without staging it.
    pub async fn dismiss_detection(
        &mut self,
        detection_id: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::DismissDetection { detection_id }).await
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

    /// Switch the host's audience-output theme by built-in name.
    pub async fn set_theme(
        &mut self,
        name: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetTheme { name: name.into() }).await
    }

    /// Apply a custom audience theme (serialized JSON) on the host.
    pub async fn set_custom_theme(
        &mut self,
        theme_json: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetCustomTheme {
            theme_json: theme_json.into(),
        })
        .await
    }
    /// Set (or clear, with an empty name) a plan item's per-item theme override (S8-3d).
    pub async fn set_item_theme(
        &mut self,
        item_id: u64,
        theme: Option<String>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetItemTheme { item_id, theme }).await
    }

    /// Save a NAMED custom theme into the host's library (86ajq4xmy).
    pub async fn save_theme(
        &mut self,
        name: &str,
        theme_json: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SaveTheme {
            name: name.into(),
            theme_json: theme_json.into(),
        })
        .await
    }

    /// Delete a saved theme from the host's library by name (86ajq4xmy).
    pub async fn delete_theme(
        &mut self,
        name: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::DeleteTheme { name: name.into() }).await
    }

    /// Set (or clear) an Audience screen's own theme on the host (86ajq321k).
    pub async fn set_screen_theme(
        &mut self,
        screen: &str,
        name: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetScreenTheme {
            screen: screen.into(),
            name: name.into(),
        })
        .await
    }

    /// Search scripture on the host; returns stageable display references.
    pub async fn scripture_search(
        &mut self,
        query: &str,
        translation: Option<&str>,
    ) -> Result<Vec<selahcue_lan::protocol::ScriptureHitView>, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self
            .client
            .command(Command::ScriptureSearch {
                query: query.into(),
                translation: translation.map(Into::into),
            })
            .await?
        {
            ServerMessage::ScriptureResults {
                hits, references, ..
            } => {
                // A pre-7ad host sends only bare references: synthesize
                // text-less hits so results still render (snippets empty).
                if hits.is_empty() && !references.is_empty() {
                    Ok(references
                        .into_iter()
                        .map(|reference| selahcue_lan::protocol::ScriptureHitView {
                            reference,
                            text: String::new(),
                        })
                        .collect())
                } else {
                    Ok(hits)
                }
            }
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected scripture_results, got: {other:?}"
            ))),
        }
    }

    /// Fetch the host's current Preview + Live output as downscaled thumbnails (86ajtwq28),
    /// so the operator console monitors show the TRUE composited pixels the audience sees
    /// (not a text placeholder) when driving the output over the loopback link. A **read** —
    /// never changes what is on air.
    pub async fn console_thumbnails(
        &mut self,
        max_w: u32,
        max_h: u32,
    ) -> Result<
        (
            Option<selahcue_lan::protocol::ThumbView>,
            Option<selahcue_lan::protocol::ThumbView>,
        ),
        selahcue_lan::TransportError,
    > {
        use selahcue_lan::protocol::ServerMessage;
        match self
            .client
            .command(Command::GetConsoleThumbnails { max_w, max_h })
            .await?
        {
            ServerMessage::ConsoleThumbnails { preview, live } => Ok((preview, live)),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected console_thumbnails, got: {other:?}"
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
