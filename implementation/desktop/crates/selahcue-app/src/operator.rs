//! The operator control surface: a UI-agnostic view-model + an ergonomic action
//! shell over the shared [`LiveController`].
//!
//! This is the "Rust core ↔ operator-UI" contract (ADR-0003). The Tauri operator
//! shell binds its buttons/plan-list to [`OperatorView`] and calls [`OperatorShell`]
//! methods; the same surface is exercised directly by unit tests, so the operator
//! logic is verified independently of any GUI (which can't be runtime-tested here).

use crate::controller::LiveController;
use selahcue_lan::protocol::{
    Command, ContentLinkView, DetectionView, OperatorStateView, OutputHealthView, PlanItemView,
    SavedThemeView, ScaleFit, ScreenThemeView, ScreenView, SessionHealthView, StorageHealthView,
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
    /// Current within-item slide (0-based); the LIVE slide when this item is live, else the staged
    /// slide (drives the plan-row badge). Present for the live/staged item.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<u32>,
    /// The STAGED (Preview) within-item slide (0-based), present only when this item is staged.
    /// Distinct from `slide_index` so the Live Console slide picker can mark PREVIEW and LIVE on
    /// different slides of the same presentation (item both staged and live).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub staged_slide_index: Option<u32>,
    /// Per-item theme override (built-in name), if this item overrides the global
    /// theme (S8-3d); absent = the global theme.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
    /// The content this item links — scripture / deck / media (ADR-0020 follow-up);
    /// absent = an unlinked item.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub link: Option<ContentLinkView>,
    /// Responsible person/role for this item (FR-004); absent = unassigned. Skip-if-none
    /// keeps the run-sheet rows byte-stable for items without an owner.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner: Option<String>,
    /// Planned duration in seconds (FR-004); absent = unplanned.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub planned_secs: Option<u32>,
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
    /// The id of the authored deck slide currently on Live (Design 2.0), if an authored slide is
    /// presented rather than plan/scripture content. Host-truth for the presentation grid's LIVE
    /// ring — the deck editor's local `live` annotation can go stale when the console drives plan
    /// content, so the grid rings THIS instead.
    pub live_authored_id: Option<u64>,
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
    /// The screen registry (Screens page — dynamic registry): every managed screen with
    /// its role, enable state, deletability, and theme — drives the Enable toggle and the
    /// delete-on-virtual affordance.
    pub screens: Vec<ScreenView>,
    /// The recent live-transcript segments (bounded tail, oldest first) — the transcript
    /// panel (R3).
    pub transcript: Vec<TranscriptSegmentView>,
    /// The current streaming interim line (words for the utterance still being spoken), shown
    /// live below the finalised transcript; `None` when nothing is mid-utterance.
    pub partial_transcript: Option<String>,
    /// The pending scripture-detection approval queue (R4) — candidates to one-click stage.
    pub detections: Vec<DetectionView>,
    /// The stage/confidence template the confidence monitor renders
    /// (`worship`/`scripture`/`timer-only`) — drives the Live Console's Stage sub-tab.
    pub stage_template: String,
    /// The production message shown on the confidence monitor, if any (stage-only).
    pub stage_message: Option<String>,
    /// The LIVE output's fault/recovery health (NFR-024). `None` = this view was built
    /// without health (an older host over the wire); the UI must render that as *unknown*,
    /// never as a fault.
    pub output_health: Option<OutputHealthView>,
    /// The host's storage headroom for autosave. `None` = not reported by this host.
    pub storage: Option<StorageHealthView>,
    /// The host's session-recovery state. `None` = not reported by this host.
    pub session: Option<SessionHealthView>,
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
            let preview = p.preview_output().thumbnail(max_w, max_h);
            // The Live monitor IS the `main` audience output — a disabled `main` screen mutes
            // it to black here too (matching the physical main window + the Screens preview),
            // so the local operator never sees "airing" content while main is muted.
            let live = if c.is_screen_enabled("main") {
                p.live_output().thumbnail(max_w, max_h)
            } else {
                let out = p.live_output();
                FrameBuffer::filled(out.width(), out.height(), selahcue_present::Rgba::BLACK)
                    .thumbnail(max_w, max_h)
            };
            (preview, live)
        })
    }

    /// The named Audience `screen`'s current LIVE content composed under ITS per-screen theme,
    /// downscaled — for the operator Screens-page preview (86ajq321k). `None` for an unknown
    /// screen id. A read — never changes the audience output.
    pub fn screen_frame(&self, screen: &str, max_w: u32, max_h: u32) -> Option<FrameBuffer> {
        self.with(|c| {
            c.compose_screen(screen)
                .map(|fb| fb.thumbnail(max_w, max_h))
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

    /// Stage a specific within-item slide of a plan item (by id) in Preview — the Live Console
    /// slide picker. Preview only; Live is untouched (FR-012). The index is clamped to the item's
    /// slide count by the controller.
    pub fn select_slide(&self, item_id: u64, slide_index: u32) -> OperatorView {
        self.act(&Command::SelectSlide {
            item_id,
            slide_index,
        })
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

    /// Pause the running countdown (banks elapsed; denied when no timer is active).
    pub fn pause_timer(&self) -> OperatorView {
        self.act(&Command::PauseTimer)
    }

    /// Resume a paused countdown from its banked elapsed.
    pub fn resume_timer(&self) -> OperatorView {
        self.act(&Command::ResumeTimer)
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

    /// Undo the last Service-Plan edit (plan-editing · undo/redo). Restores the plan DOCUMENT
    /// only — never changes what is on the Live audience output. Returns the fresh view.
    pub fn plan_undo(&self) -> OperatorView {
        self.with(|c| {
            c.undo_plan();
            c.tick(std::time::Instant::now());
            c.operator_view()
        })
    }

    /// Redo the last undone Service-Plan edit (the inverse of [`plan_undo`](Self::plan_undo)).
    /// Restores the plan DOCUMENT only — never changes the Live audience output.
    pub fn plan_redo(&self) -> OperatorView {
        self.with(|c| {
            c.redo_plan();
            c.tick(std::time::Instant::now());
            c.operator_view()
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

    /// Stage a scripture verse in Preview AND advance Live to it **only when a scripture is
    /// already live** (86ajtwq2b — scrolling verses follows the audience). Preview-only when
    /// nothing / a non-scripture item is live.
    pub fn follow_scripture(&self, reference: &str, translation: Option<&str>) -> OperatorView {
        self.act(&Command::FollowScripture {
            reference: reference.into(),
            translation: translation.map(Into::into),
        })
    }

    /// Feed one live-transcript segment (the STT-provider ingestion channel — the default
    /// provider is operator/host-injected text). A final segment runs scripture detection; an
    /// interim (`is_final == false`) only updates the live partial line.
    pub fn ingest_transcript(
        &self,
        text: &str,
        start_ms: u64,
        end_ms: u64,
        is_final: bool,
    ) -> OperatorView {
        self.act(&Command::IngestTranscript {
            text: text.into(),
            start_ms: Some(start_ms),
            end_ms: Some(end_ms),
            is_final,
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
    /// Present a Design 2.0 authored deck slide on the LIVE audience output — the deck editor's
    /// "Present". `slide_json`/`theme_json` are a serialized `AuthoredSlide` and `Theme` (opaque;
    /// the controller deserializes + composes them with the same compositor as plan content).
    pub fn present_authored_slide(
        &self,
        slide_json: &str,
        theme_json: &str,
        next_slide_json: Option<&str>,
    ) -> OperatorView {
        self.act(&Command::PresentAuthoredSlide {
            slide_json: slide_json.into(),
            theme_json: theme_json.into(),
            next_slide_json: next_slide_json.map(Into::into),
        })
    }
    /// Set (or clear, with an empty name) a plan item's per-item theme override (S8-3d).
    pub fn set_item_theme(&self, item_id: u64, theme: Option<String>) -> OperatorView {
        self.act(&Command::SetItemTheme { item_id, theme })
    }

    /// Set (or clear, with `None`) a plan item's linked content — scripture / deck / media
    /// (ADR-0020 follow-up). A plan edit; never changes Live.
    pub fn set_item_content(&self, item_id: u64, link: Option<ContentLinkView>) -> OperatorView {
        self.act(&Command::SetItemContent { item_id, link })
    }

    /// Set (or clear, with `None`) a plan item's responsible owner/role (FR-004). Plan edit; never Live.
    pub fn set_item_owner(&self, item_id: u64, owner: Option<String>) -> OperatorView {
        self.act(&Command::SetItemOwner { item_id, owner })
    }

    /// Set (or clear, with `None`) a plan item's planned duration in seconds (FR-004). Plan edit; never Live.
    pub fn set_item_duration(&self, item_id: u64, secs: Option<u32>) -> OperatorView {
        self.act(&Command::SetItemDuration { item_id, secs })
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

    /// Enable or disable a screen by id (Screens page — dynamic registry).
    pub fn set_screen_enabled(&self, screen: &str, enabled: bool) -> OperatorView {
        self.act(&Command::SetScreenEnabled {
            screen: screen.into(),
            enabled,
        })
    }

    /// Add a virtual Audience-class screen (`role` is `lower-third`/`stream`).
    pub fn add_screen(&self, role: &str) -> OperatorView {
        self.act(&Command::AddScreen { role: role.into() })
    }

    /// Remove a virtual screen by id (a built-in is rejected by the controller).
    pub fn remove_screen(&self, screen: &str) -> OperatorView {
        self.act(&Command::RemoveScreen {
            screen: screen.into(),
        })
    }

    /// Set a screen's output orientation (quarter-turns clockwise, `0..=3`).
    pub fn set_output_orientation(&self, screen: &str, quarter_turns: u8) -> OperatorView {
        self.act(&Command::SetOutputOrientation {
            screen: screen.into(),
            quarter_turns,
        })
    }

    /// Set a screen's scaling/fit mode.
    pub fn set_output_scale_fit(&self, screen: &str, fit: ScaleFit) -> OperatorView {
        self.act(&Command::SetOutputScaleFit {
            screen: screen.into(),
            fit,
        })
    }

    /// Mirror a screen's output horizontally.
    pub fn set_output_mirror(&self, screen: &str, on: bool) -> OperatorView {
        self.act(&Command::SetOutputMirror {
            screen: screen.into(),
            on,
        })
    }

    /// Set a screen's output delay (ms; clamped by the controller).
    pub fn set_output_delay(&self, screen: &str, ms: u32) -> OperatorView {
        self.act(&Command::SetOutputDelay {
            screen: screen.into(),
            ms,
        })
    }

    /// Set a screen's target frame rate (fps; clamped by the controller).
    pub fn set_output_frame_rate(&self, screen: &str, fps: u16) -> OperatorView {
        self.act(&Command::SetOutputFrameRate {
            screen: screen.into(),
            fps,
        })
    }

    /// Toggle a screen's safe-area guides (operator preview overlay only).
    pub fn set_output_safe_area(&self, screen: &str, on: bool) -> OperatorView {
        self.act(&Command::SetOutputSafeArea {
            screen: screen.into(),
            on,
        })
    }

    /// Show/hide one compositing layer on a screen.
    pub fn set_screen_layer_visible(
        &self,
        screen: &str,
        layer: &str,
        visible: bool,
    ) -> OperatorView {
        self.act(&Command::SetScreenLayerVisible {
            screen: screen.into(),
            layer: layer.into(),
            visible,
        })
    }

    /// Configure a screen's NDI output (source name + enabled), atomically.
    pub fn set_ndi_output(&self, screen: &str, name: &str, enabled: bool) -> OperatorView {
        self.act(&Command::SetNdiOutput {
            screen: screen.into(),
            name: name.into(),
            enabled,
        })
    }

    /// Choose the stage/confidence template (`worship`/`scripture`/`timer-only`).
    pub fn set_stage_template(&self, template: &str) -> OperatorView {
        self.act(&Command::SetStageTemplate {
            template: template.into(),
        })
    }

    /// Set (or clear, with a blank string) the stage/confidence production message.
    pub fn set_stage_message(&self, text: &str) -> OperatorView {
        self.act(&Command::SetStageMessage { text: text.into() })
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
            staged_slide_index: i.staged_slide_index,
            theme: i.theme,
            link: i.link,
            owner: i.owner,
            planned_secs: i.planned_secs,
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
            staged_slide_index: i.staged_slide_index,
            theme: i.theme,
            link: i.link,
            owner: i.owner,
            planned_secs: i.planned_secs,
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
            live_authored_id: v.live_authored_id,
            outputs: v.outputs,
            displays: v.displays,
            translations: v.translations,
            theme: v.theme,
            themes: v.themes,
            saved_themes: v.saved_themes,
            screen_themes: v.screen_themes,
            screens: v.screens,
            transcript: v.transcript,
            partial_transcript: v.partial_transcript,
            detections: v.detections,
            stage_template: v.stage_template,
            stage_message: v.stage_message,
            output_health: v.output_health,
            storage: v.storage,
            session: v.session,
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
            live_authored_id: v.live_authored_id,
            outputs: v.outputs,
            displays: v.displays,
            translations: v.translations,
            theme: v.theme,
            themes: v.themes,
            saved_themes: v.saved_themes,
            screen_themes: v.screen_themes,
            screens: v.screens,
            transcript: v.transcript,
            partial_transcript: v.partial_transcript,
            detections: v.detections,
            stage_template: v.stage_template,
            stage_message: v.stage_message,
            output_health: v.output_health,
            storage: v.storage,
            session: v.session,
        }
    }
}

/// The host's Remote Control snapshot: (paired devices, outstanding pairing requests) — the
/// operator's device-management view (86ajxer8n).
#[cfg(feature = "server")]
pub type RemoteSnapshot = (
    Vec<selahcue_lan::protocol::RemoteDeviceView>,
    Vec<selahcue_lan::protocol::RemotePendingView>,
);

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

    // --- Remote Control device management (86ajxer8n): operator→host, all Operator-only.
    //     Each mutator returns the fresh (devices, pending) snapshot from the host. ---

    /// List the host's paired controller devices + outstanding pairing requests.
    pub async fn remote_devices(&mut self) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        self.remote_command(Command::ListRemoteDevices).await
    }

    /// Approve a pending pairing request, granting it `role`.
    pub async fn approve_pairing(
        &mut self,
        device_id: &str,
        role: selahcue_lan::Role,
    ) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        self.remote_command(Command::ApprovePairing {
            device_id: device_id.into(),
            role,
        })
        .await
    }

    /// Deny (drop) a pending pairing request.
    pub async fn deny_pairing(
        &mut self,
        device_id: &str,
    ) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        self.remote_command(Command::DenyPairing {
            device_id: device_id.into(),
        })
        .await
    }

    /// Revoke a paired device's session immediately.
    pub async fn revoke_session(
        &mut self,
        device_id: &str,
    ) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        self.remote_command(Command::RevokeSession {
            device_id: device_id.into(),
        })
        .await
    }

    /// Change a paired device's role.
    pub async fn set_session_role(
        &mut self,
        device_id: &str,
        role: selahcue_lan::Role,
    ) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        self.remote_command(Command::SetSessionRole {
            device_id: device_id.into(),
            role,
        })
        .await
    }

    /// Mint a fresh single-use pairing code + fingerprint for the "Pair a device" QR. The fourth
    /// element is the full `selahcue://pair?…` invite URI to encode as the scannable QR (`None`
    /// when the host did not supply its LAN endpoint).
    pub async fn new_pairing_code(
        &mut self,
    ) -> Result<(String, String, u64, Option<String>), selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self.client.command(Command::NewPairingCode).await? {
            ServerMessage::PairingCode {
                code,
                fingerprint,
                expires_in_secs,
                uri,
            } => Ok((code, fingerprint, expires_in_secs, uri)),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected pairing_code, got: {other:?}"
            ))),
        }
    }

    /// Send a device-management command and parse the host's `RemoteDevices` snapshot reply.
    async fn remote_command(
        &mut self,
        cmd: Command,
    ) -> Result<RemoteSnapshot, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self.client.command(cmd).await? {
            ServerMessage::RemoteDevices { devices, pending } => Ok((devices, pending)),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected remote_devices, got: {other:?}"
            ))),
        }
    }

    /// Stage a specific plan item (by id) in the host's Preview.
    pub async fn select(
        &mut self,
        item_id: u64,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SelectItem { item_id }).await
    }

    /// Stage a specific within-item slide of a plan item (by id) in the host's Preview — the Live
    /// Console slide picker. Preview only; Live is untouched (FR-012).
    pub async fn select_slide(
        &mut self,
        item_id: u64,
        slide_index: u32,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SelectSlide {
            item_id,
            slide_index,
        })
        .await
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

    /// Pause the host's running countdown (banks elapsed; denied when no timer is active).
    pub async fn pause_timer(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::PauseTimer).await
    }

    /// Resume the host's paused countdown from its banked elapsed.
    pub async fn resume_timer(&mut self) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::ResumeTimer).await
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

    /// Stage a scripture verse in Preview AND advance the host's Live to it **only when a
    /// scripture is already live** (86ajtwq2b). Preview-only otherwise. Requires `GoLive`.
    pub async fn follow_scripture(
        &mut self,
        reference: &str,
        translation: Option<&str>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::FollowScripture {
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
        is_final: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::IngestTranscript {
            text: text.into(),
            start_ms: Some(start_ms),
            end_ms: Some(end_ms),
            is_final,
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
    /// Present a Design 2.0 authored deck slide on the host's LIVE audience output — the deck
    /// editor's "Present". `slide_json`/`theme_json` are opaque serialized values.
    pub async fn present_authored_slide(
        &mut self,
        slide_json: String,
        theme_json: String,
        next_slide_json: Option<String>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::PresentAuthoredSlide {
            slide_json,
            theme_json,
            next_slide_json,
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

    /// Set (or clear) a plan item's linked content on the host (ADR-0020 follow-up).
    pub async fn set_item_content(
        &mut self,
        item_id: u64,
        link: Option<ContentLinkView>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetItemContent { item_id, link }).await
    }

    /// Set (or clear, with `None`) a plan item's responsible owner/role over the host link (FR-004).
    pub async fn set_item_owner(
        &mut self,
        item_id: u64,
        owner: Option<String>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetItemOwner { item_id, owner }).await
    }

    /// Set (or clear, with `None`) a plan item's planned duration (seconds) over the host link (FR-004).
    pub async fn set_item_duration(
        &mut self,
        item_id: u64,
        secs: Option<u32>,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetItemDuration { item_id, secs }).await
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

    /// Enable or disable a screen by id on the host (Screens page — dynamic registry).
    pub async fn set_screen_enabled(
        &mut self,
        screen: &str,
        enabled: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetScreenEnabled {
            screen: screen.into(),
            enabled,
        })
        .await
    }

    /// Add a virtual Audience-class screen on the host (`role` is `lower-third`/`stream`).
    pub async fn add_screen(
        &mut self,
        role: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::AddScreen { role: role.into() }).await
    }

    /// Remove a virtual screen by id on the host (a built-in is rejected).
    pub async fn remove_screen(
        &mut self,
        screen: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::RemoveScreen {
            screen: screen.into(),
        })
        .await
    }

    /// Set a screen's output orientation on the host (quarter-turns clockwise).
    pub async fn set_output_orientation(
        &mut self,
        screen: &str,
        quarter_turns: u8,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputOrientation {
            screen: screen.into(),
            quarter_turns,
        })
        .await
    }

    /// Set a screen's scaling/fit mode on the host.
    pub async fn set_output_scale_fit(
        &mut self,
        screen: &str,
        fit: ScaleFit,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputScaleFit {
            screen: screen.into(),
            fit,
        })
        .await
    }

    /// Mirror a screen's output horizontally on the host.
    pub async fn set_output_mirror(
        &mut self,
        screen: &str,
        on: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputMirror {
            screen: screen.into(),
            on,
        })
        .await
    }

    /// Set a screen's output delay (ms) on the host.
    pub async fn set_output_delay(
        &mut self,
        screen: &str,
        ms: u32,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputDelay {
            screen: screen.into(),
            ms,
        })
        .await
    }

    /// Set a screen's target frame rate (fps) on the host.
    pub async fn set_output_frame_rate(
        &mut self,
        screen: &str,
        fps: u16,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputFrameRate {
            screen: screen.into(),
            fps,
        })
        .await
    }

    /// Toggle a screen's safe-area guides on the host (operator preview overlay only).
    pub async fn set_output_safe_area(
        &mut self,
        screen: &str,
        on: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetOutputSafeArea {
            screen: screen.into(),
            on,
        })
        .await
    }

    /// Show/hide one compositing layer on a screen on the host.
    pub async fn set_screen_layer_visible(
        &mut self,
        screen: &str,
        layer: &str,
        visible: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetScreenLayerVisible {
            screen: screen.into(),
            layer: layer.into(),
            visible,
        })
        .await
    }

    /// Configure a screen's NDI output (source name + enabled) on the host.
    pub async fn set_ndi_output(
        &mut self,
        screen: &str,
        name: &str,
        enabled: bool,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetNdiOutput {
            screen: screen.into(),
            name: name.into(),
            enabled,
        })
        .await
    }

    /// Choose the stage/confidence template on the host.
    pub async fn set_stage_template(
        &mut self,
        template: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetStageTemplate {
            template: template.into(),
        })
        .await
    }

    /// Set (or clear) the stage/confidence production message on the host.
    pub async fn set_stage_message(
        &mut self,
        text: &str,
    ) -> Result<OperatorView, selahcue_lan::TransportError> {
        self.act(Command::SetStageMessage { text: text.into() })
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

    /// Fetch a named Audience screen's LIVE content rendered under its per-screen theme, as a
    /// downscaled thumbnail (86ajq321k) — for the operator Screens-page preview. `None` for an
    /// unknown screen (or no live content). A read (RBAC `Monitor`).
    pub async fn screen_frame(
        &mut self,
        screen: &str,
        max_w: u32,
        max_h: u32,
    ) -> Result<Option<selahcue_lan::protocol::ThumbView>, selahcue_lan::TransportError> {
        use selahcue_lan::protocol::ServerMessage;
        match self
            .client
            .command(Command::GetScreenFrame {
                screen: screen.to_string(),
                max_w,
                max_h,
            })
            .await?
        {
            ServerMessage::ScreenFrame { frame, .. } => Ok(frame),
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected screen_frame, got: {other:?}"
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

#[cfg(test)]
mod plan_undo_shell_tests {
    //! The operator shell's Service-Plan undo/redo actions (plan-editing · undo/redo) — a thin
    //! wrapper over the controller's `undo_plan`/`redo_plan` that returns the fresh view.
    use super::*;
    use selahcue_core::plan::ServicePlan;
    use selahcue_present::Theme;

    fn shell() -> OperatorShell {
        let c = LiveController::new(ServicePlan::new("Test"), 320, 180, Theme::dark());
        OperatorShell::new(Arc::new(Mutex::new(c)))
    }

    #[test]
    fn plan_undo_and_redo_restore_the_plan_via_the_shell() {
        let sh = shell();
        sh.add_item("song", "One", None);
        sh.add_item("song", "Two", None);
        assert_eq!(sh.view().items.len(), 2);
        let v = sh.plan_undo();
        assert_eq!(v.items.len(), 1, "undo peels back the last add");
        let v = sh.plan_redo();
        assert_eq!(v.items.len(), 2, "redo restores it");
    }
}
