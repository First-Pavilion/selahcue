//! The LAN control wire protocol (FR-118; ADR-0009).
//!
//! JSON messages exchanged over the (separately-layered) TLS WebSocket transport.
//! Controllers send an [`AuthRequest`] to establish a session, then [`Request`]s
//! carrying a [`Command`]; the operator replies with [`ServerMessage`]s. Every
//! frame carries the protocol [`VERSION`] so mismatched peers fail fast and
//! explicitly rather than misinterpreting fields.

use crate::rbac::Role;
use serde::{Deserialize, Serialize};

/// Wire protocol version. Bumped on any breaking change to the message shapes.
/// v2: the first client frame is a tagged [`Hello`] (auth **or** pair) instead of a
/// bare [`AuthRequest`], so devices can redeem a pairing code over the wire.
pub const VERSION: u16 = 2;

/// `serde(skip_serializing_if)` predicate: omit a `bool` field when it is `false`, so the
/// common frame stays byte-identical to a peer that never had the field (additive fields).
fn is_false(b: &bool) -> bool {
    !*b
}

/// Upper bound on per-output present delay. Bounds the desktop host's delay-buffer ring so a
/// large `delay_ms` cannot grow output memory without limit (no-leak). Values above are
/// clamped to this ceiling by the controller.
pub const MAX_OUTPUT_DELAY_MS: u32 = 1_000;
/// Lowest selectable per-output frame-rate target (fps). Below this the output would visibly
/// stutter; the controller clamps up to it.
pub const MIN_FRAME_RATE: u16 = 24;
/// Highest selectable per-output frame-rate target (fps). The compositor is paced at 60Hz; a
/// higher target is meaningless, so the controller clamps down to it.
pub const MAX_FRAME_RATE: u16 = 60;
/// Longest permitted NDI source name (the name broadcast on the network for a Stream/NDI
/// output). Bounded so the persisted/wire name cannot grow without limit (no-leak); NDI itself
/// tolerates longer, but a church stage needs only a short human-readable source name.
pub const MAX_NDI_NAME_LEN: usize = 64;

/// A command from a controller to the operator. `request_id` (in [`Request`])
/// correlates the eventual [`ServerMessage::Ack`] / [`ServerMessage::Denied`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "cmd", rename_all = "snake_case")]
pub enum Command {
    /// Push the current selection to the live output.
    GoLive,
    /// Advance to the next plan item / slide.
    Next,
    /// Return to the previous plan item / slide.
    Previous,
    /// Select a specific plan item by id.
    SelectItem { item_id: u64 },
    /// Clear the live output (return to logo/idle).
    Clear,
    /// Toggle blackout of the live output.
    Blackout { on: bool },
    /// Start a countdown/count-up timer on the live output.
    StartTimer { seconds: u32 },
    /// Stop the running timer.
    StopTimer,
    /// Adjust the RUNNING countdown's target by `delta_secs` (e.g. +60 / -60).
    /// Clamps at zero (landing in TIME UP); denied when no timer is active.
    AdjustTimer { delta_secs: i64 },
    /// Pause the running countdown, banking the elapsed time. Denied when no timer
    /// is active. Additive/back-compatible (a unit variant, like [`StopTimer`]).
    PauseTimer,
    /// Resume a paused countdown from its banked elapsed time. Denied when no timer
    /// is active. Additive/back-compatible.
    ResumeTimer,
    /// Search scripture (does not push live). `translation` is a bundled code
    /// (`"KJV"`/`"WEB"`); omitted = the KJV default. Skip-if-none keeps fixtures.
    ScriptureSearch {
        query: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        translation: Option<String>,
    },
    /// Stage a scripture reference for the operator to review before going live.
    /// `translation` is a bundled-translation code (`"KJV"`/`"WEB"`); omitted =
    /// the product default (KJV). Skip-if-none keeps the v2 fixtures identical.
    StageScripture {
        reference: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        translation: Option<String>,
    },
    /// Stage a scripture verse in Preview AND — **only when a scripture is already live** —
    /// advance the Live output to the same verse (86ajtwq2b, owner refine #8: scrolling
    /// through verses follows the audience once a scripture is live). When nothing (or a
    /// non-scripture item) is live, it behaves exactly like [`StageScripture`] (Preview only),
    /// so preview⟂live isolation holds. Blackout + non-scripture live content are untouched.
    /// Because it can change Live, it requires the `GoLive` permission (never `SearchScripture`
    /// — a separate command so a lower role cannot escalate to Live via a flag). Skip-if-none
    /// `translation` keeps the pinned fixtures byte-identical.
    FollowScripture {
        reference: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        translation: Option<String>,
    },
    /// Fetch a whole chapter's numbered verses (read-only; does NOT push live)
    /// so a remote controller can render the verse list the desktop browser
    /// holds locally. `reference` is any parseable ref (`"Romans 8"`, `"gen 1 1"`
    /// — the verse part is ignored); `translation` omitted = the KJV default.
    /// Skip-if-none keeps the v2 fixtures identical.
    GetChapter {
        reference: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        translation: Option<String>,
    },
    /// Show the identify overlay (a distinct number) on every physical output.
    IdentifyOutputs,
    /// Assign an output role to a physical display (persisted; applied live).
    AssignOutput { role: String, display_key: String },
    /// Request the current live/preview state.
    GetState,
    /// Request the full operator view (plan + per-item live/preview flags + blackout),
    /// so a remote operator UI can render authoritative state from the host.
    GetOperatorState,
    /// Request the host's current **Preview + Live output** as downscaled RGBA thumbnails
    /// (86ajtwq28), so a remote operator's console monitors show the TRUE composited pixels
    /// (not a text placeholder) when the operator drives the output over the loopback link.
    /// A **read** (RBAC `Monitor`) — never changes what is on air. The host clamps the size.
    GetConsoleThumbnails { max_w: u32, max_h: u32 },
    /// Request the current LIVE content composed for one Audience-class `screen`
    /// (`main`/`lower-third`/`stream`) under ITS per-screen theme (86ajq321k), as a downscaled
    /// RGBA thumbnail — so the operator's Screens page can PREVIEW each screen's own design
    /// (the secondaries have no physical output yet; this is the only way to see them). A
    /// **read** (RBAC `Monitor`) — never changes what is on air. The host clamps the size.
    GetScreenFrame {
        screen: String,
        max_w: u32,
        max_h: u32,
    },
    /// Append a plan item (plan editing — Operator only). `kind` is the stable
    /// item-kind tag (e.g. `"song"`); unknown tags are rejected.
    AddItem {
        kind: String,
        title: String,
        /// Optional stanza content for songs (plain text, stanzas separated by
        /// blank lines — S8-1). Skip-if-none keeps the pinned fixtures.
        #[serde(default, skip_serializing_if = "Option::is_none")]
        content: Option<String>,
    },
    /// Remove a plan item by id (Operator only). Never changes the Live output.
    RemoveItem { item_id: u64 },
    /// Move a plan item to a new position (Operator only).
    MoveItem { item_id: u64, to: u32 },
    /// Rename a plan item (Operator only).
    RenameItem { item_id: u64, title: String },
    /// Switch the audience-output theme by its stable built-in name
    /// (`"classic"`/`"high-contrast"`/`"lower-third"`). Restyles Preview + Live
    /// without changing content; an unknown name is rejected. Operator-only.
    SetTheme { name: String },
    /// Apply a CUSTOM audience theme authored in the Theme Designer. `theme_json`
    /// is a serialized `selahcue-present::Theme` (opaque to the wire — this layer
    /// does not depend on the presentation crate; the controller deserializes it).
    /// Malformed JSON is rejected. Operator-only (output config).
    SetCustomTheme { theme_json: String },
    /// **Present an authored deck slide** (Design 2.0 deck editor, node 329:124) on the LIVE
    /// audience output. `slide_json` is a serialized `selahcue-present::AuthoredSlide` and
    /// `theme_json` a serialized `Theme` — both opaque to the wire (this layer does not depend
    /// on the presentation crate; the controller deserializes them, mirroring
    /// [`Command::SetCustomTheme`]). The slide is composed with the SAME compositor as
    /// scripture/plan content and TAKES OVER the live surface (a later plan/scripture Go-Live
    /// replaces it). Malformed or over-bounds JSON is rejected (the live output is unchanged).
    /// Requires `GoLive` — it changes what the audience sees (never an escalation).
    PresentAuthoredSlide {
        slide_json: String,
        theme_json: String,
    },
    /// Set (or clear, with `None`) a plan item's per-item theme OVERRIDE by built-in
    /// name (S8-3d). That item then renders on its own template instead of the global
    /// theme; an unknown item or name is rejected. Operator-only (output config).
    SetItemTheme {
        item_id: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        theme: Option<String>,
    },
    /// Save a NAMED custom theme into the library (Theme Designer "Save changes",
    /// 86ajq4xmy). `theme_json` is a serialized `Theme` (opaque to the wire). An empty/
    /// over-long name, invalid JSON, or a new name past the cap is rejected.
    /// Operator-only (output config).
    SaveTheme { name: String, theme_json: String },
    /// Delete a saved theme from the library by name (idempotent). Operator-only.
    DeleteTheme { name: String },
    /// Set (or clear, with an empty `name`) an Audience-class SCREEN's own theme
    /// (86ajq321k): `screen` is `main` / `lower-third` / `stream`; `name` is a built-in
    /// or a saved-library name. Each screen renders the same live content under its own
    /// theme. An unknown screen or unresolvable name is rejected. Operator-only.
    SetScreenTheme { screen: String, name: String },
    /// Enable or disable a SCREEN by id (Screens page — dynamic registry). A disabled
    /// screen composes safe all-black (a per-screen MUTE, distinct from global
    /// [`Command::Blackout`]) and its preview goes black; re-enabling restores it. Any
    /// registry screen (built-in or virtual) may be enabled/disabled. An unknown screen
    /// is rejected. Operator-only (`ConfigureOutputs`).
    SetScreenEnabled { screen: String, enabled: bool },
    /// Add a VIRTUAL Audience-class screen to the registry (Screens page): `role` is
    /// `lower-third` or `stream` (never `main`/`stage` — those are built-in). The host
    /// mints a stable id (e.g. `stream-2`), enabled + deletable. Rejected at the bounded
    /// screen cap. Physical NDI/SDI/stream DELIVERY is a later affordance — a virtual
    /// screen composes + previews on-demand but does not stream yet. Operator-only.
    AddScreen { role: String },
    /// Remove a screen from the registry by id (Screens page). ONLY a `deletable`
    /// (virtual) screen — a built-in (`main`/`lower-third`/`stream`/`stage`) is rejected
    /// server-side. Also drops that screen's per-screen theme override. Idempotent for an
    /// already-absent id. Operator-only (`ConfigureOutputs`).
    RemoveScreen { screen: String },
    /// Set a SCREEN's output orientation as `quarter_turns` clockwise (`0`=Landscape,
    /// `1`=Portrait, `2`=Landscape flipped, `3`=Portrait flipped). Values `>= 4` are rejected.
    /// Persisted per screen; applied as a pure buffer transform. Operator-only
    /// (`ConfigureOutputs`).
    SetOutputOrientation { screen: String, quarter_turns: u8 },
    /// Set a SCREEN's scaling/fit mode (how the live frame fills the display surface).
    /// Persisted; applied as a pure buffer transform. Operator-only (`ConfigureOutputs`).
    SetOutputScaleFit { screen: String, fit: ScaleFit },
    /// Mirror a SCREEN's output horizontally (row-reverse). Persisted; applied as a pure
    /// buffer transform. Operator-only (`ConfigureOutputs`).
    SetOutputMirror { screen: String, on: bool },
    /// Set a SCREEN's output delay in milliseconds (a bounded present-buffer ring; capped at
    /// [`MAX_OUTPUT_DELAY_MS`], values above are clamped). Persisted. Operator-only.
    SetOutputDelay { screen: String, ms: u32 },
    /// Set a SCREEN's target frame rate in fps (clamped to `[MIN_FRAME_RATE, MAX_FRAME_RATE]`).
    /// Persisted; paces that output's redraw. Operator-only (`ConfigureOutputs`).
    SetOutputFrameRate { screen: String, fps: u16 },
    /// Toggle safe-area guides for a SCREEN. Guides draw on the OPERATOR preview/monitor only
    /// — never on the audience output. Persisted. Operator-only (`ConfigureOutputs`).
    SetOutputSafeArea { screen: String, on: bool },
    /// Show or hide one compositing LAYER on a SCREEN's output (`layer` ∈
    /// `background`/`text`/`lower-third`/`logo`/`timer`). Hiding a layer never blanks the
    /// frame. Persisted per screen; applied at compose. An unknown layer is rejected.
    /// Operator-only (`ConfigureOutputs`).
    SetScreenLayerVisible {
        screen: String,
        layer: String,
        visible: bool,
    },
    /// Configure a SCREEN's NDI output (an Audience-class `stream`/`lower-third` feed): set its
    /// NDI source `name` (broadcast on the network) and whether NDI delivery is `enabled`, both
    /// atomically. Rejected when: an empty/blank name is enabled, the name exceeds
    /// [`MAX_NDI_NAME_LEN`], the name has a control char, the screen is not audience-class, or
    /// the name is already used by ANOTHER enabled screen. Actual NDI transmission is a
    /// feature-gated host sink; the config persists + surfaces regardless. Operator-only
    /// (`ConfigureOutputs`).
    SetNdiOutput {
        screen: String,
        name: String,
        enabled: bool,
    },
    /// Choose the STAGE / confidence template (`worship` / `scripture` / `timer-only`) — the
    /// layout the confidence monitor renders and how it behaves at TIME UP (Figma 375-139). An
    /// unknown tag falls back to the default (`worship`), never a panic. Stage-output config;
    /// Operator-only (`ConfigureOutputs`).
    SetStageTemplate { template: String },
    /// Set (or clear, with a blank/whitespace string) the STAGE / confidence production
    /// message — an operator→speaker note overlaid on the confidence monitor ONLY (never the
    /// audience). Bounded host-side (`MAX_STAGE_MESSAGE_LEN`). Stage-output config; Operator-only.
    SetStageMessage { text: String },
    /// Feed one segment into the live-transcript stream (R3). This is the
    /// STT-provider ingestion channel — the default provider is operator/host-injected
    /// text; a real on-device engine feeds the same path. The detection engine scans
    /// the text for spoken scripture references. `start_ms`/`end_ms` are optional
    /// session-relative timestamps; omitted keeps the pinned fixtures byte-identical.
    /// Requires the `Transcribe` permission.
    IngestTranscript {
        text: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        start_ms: Option<u64>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        end_ms: Option<u64>,
        /// `false` marks a streaming INTERIM (a live in-progress preview that a later `true`
        /// supersedes); `true` is a finalised line that lands in the transcript and runs
        /// detection. Defaults to `true` and skips-when-true, so a client that never streams
        /// interims (and the pinned fixtures) stay byte-identical.
        #[serde(default = "default_true", skip_serializing_if = "is_true")]
        is_final: bool,
    },
    /// Approve a queued scripture detection by id (R4): stage its verse in Preview (the
    /// operator Goes Live when ready — detections never auto-display, FR-115) and remove
    /// it from the queue. Requires `SearchScripture` (stages scripture).
    ApproveDetection { detection_id: u64 },
    /// Dismiss a queued scripture detection by id without staging it. Requires
    /// `SearchScripture`.
    DismissDetection { detection_id: u64 },

    // --- Remote Control device management (86ajxer8n): operator→host, all Operator-only
    //     (`ManageDevices`), handled in the server request loop against the SessionRegistry.
    //     The Dart mobile controller never sends these, so the pinned fixtures stay stable. ---
    /// List paired controller devices + outstanding pairing requests (reply:
    /// [`ServerMessage::RemoteDevices`]).
    ListRemoteDevices,
    /// Approve a device's pending pairing request, granting it `role` (RBAC assigned at approval).
    ApprovePairing { device_id: String, role: Role },
    /// Deny (drop) a device's pending pairing request.
    DenyPairing { device_id: String },
    /// Revoke a paired device's session immediately.
    RevokeSession { device_id: String },
    /// Change a paired device's role (effective on its next authenticated request).
    SetSessionRole { device_id: String, role: Role },
    /// Mint a fresh single-use pairing code + fingerprint for the "Pair a device" QR (reply:
    /// [`ServerMessage::PairingCode`]).
    NewPairingCode,
}

/// A controller → operator request frame.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Request {
    /// Protocol version of the sender.
    pub v: u16,
    /// Client-chosen id used to correlate the response.
    pub request_id: u64,
    /// The command to perform.
    pub command: Command,
}

impl Request {
    /// Build a request stamped with the current protocol [`VERSION`].
    pub fn new(request_id: u64, command: Command) -> Self {
        Self {
            v: VERSION,
            request_id,
            command,
        }
    }

    /// Whether the sender speaks a protocol version this build understands. The
    /// transport MUST call this on every inbound frame and reject mismatches
    /// before acting, so peers fail fast rather than misinterpreting fields.
    pub fn version_supported(&self) -> bool {
        self.v == VERSION
    }
}

/// An operator → controller message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "event", rename_all = "snake_case")]
// `OperatorState` carries the full view (the largest variant by far), but a ServerMessage
// is a short-lived per-request value that is serialized and dropped — never stored in a
// collection — so the size skew is harmless; boxing the view would only add an allocation
// on the hot reply path. (Same rationale as `ControllerReply`.)
#[allow(clippy::large_enum_variant)]
pub enum ServerMessage {
    /// The referenced request was accepted and performed.
    Ack { request_id: u64 },
    /// The referenced request was refused (e.g. RBAC denial); `reason` is a stable code.
    Denied { request_id: u64, reason: DenyReason },
    /// A snapshot of live/preview state (unsolicited or in reply to `GetState`).
    State {
        live_item: Option<u64>,
        blackout: bool,
    },
    /// Results of a `ScriptureSearch`. `references` remains for compatibility;
    /// `hits` adds the verse text so the operator can see WHY a result matched
    /// (omitted when empty — the pinned fixtures are unchanged).
    ScriptureResults {
        query: String,
        references: Vec<String>,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        hits: Vec<ScriptureHitView>,
    },
    /// Reply to [`Command::GetChapter`]: a whole chapter's numbered verses so a
    /// remote controller can render the verse list. Each verse stages via the
    /// reference `"{book_name} {chapter}:{number}"`. `prev_ref`/`next_ref`
    /// address the neighbouring chapters for ‹ › paging (absent at the ends of
    /// the canon). Skip-if-none/empty keeps the pinned fixtures compact.
    Chapter {
        book_name: String,
        chapter: u16,
        translation: String,
        #[serde(default, skip_serializing_if = "Vec::is_empty")]
        verses: Vec<VerseView>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        prev_ref: Option<String>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        next_ref: Option<String>,
    },
    /// The full operator view (reply to [`Command::GetOperatorState`]).
    OperatorState { view: OperatorStateView },
    /// Reply to [`Command::GetConsoleThumbnails`] (86ajtwq28): the host's current Preview +
    /// Live output as downscaled RGBA thumbnails, so a remote operator's console monitors
    /// render the TRUE composited pixels. `None` for a surface the host has no frame for.
    ConsoleThumbnails {
        #[serde(default, skip_serializing_if = "Option::is_none")]
        preview: Option<ThumbView>,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        live: Option<ThumbView>,
    },
    /// Reply to [`Command::GetScreenFrame`] (86ajq321k): the named Audience `screen`'s current
    /// LIVE content rendered under its own per-screen theme, as a downscaled RGBA thumbnail —
    /// so the operator Screens page can preview each screen's design. `None` for an unknown
    /// screen id (`frame` also `None` if the host has no live content).
    ScreenFrame {
        screen: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        frame: Option<ThumbView>,
    },
    /// Reply to [`Command::ListRemoteDevices`] and every device-management mutator: the operator's
    /// paired devices + outstanding pairing requests for the Remote Control surface (86ajxer8n).
    RemoteDevices {
        devices: Vec<RemoteDeviceView>,
        pending: Vec<RemotePendingView>,
    },
    /// Reply to [`Command::NewPairingCode`]: a fresh single-use pairing code + fingerprint for the
    /// "Pair a device" QR, valid for `expires_in_secs`.
    PairingCode {
        code: String,
        fingerprint: String,
        expires_in_secs: u64,
    },
    /// A protocol-level or transport-level error not tied to a single request.
    Error { message: String },
}

/// A paired controller device for the operator's Remote Control list — a JS-friendly wire view of
/// [`SessionSummary`](crate::session::SessionSummary) (seconds, not `Duration`; never the token).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RemoteDeviceView {
    pub device_id: String,
    pub name: String,
    pub platform: String,
    pub role: Role,
    pub idle_secs: u64,
    pub pinned: bool,
}

/// An outstanding pairing request awaiting operator approval — a wire view of
/// [`PendingRequestSummary`](crate::session::PendingRequestSummary).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RemotePendingView {
    pub device_id: String,
    pub name: String,
    pub platform: String,
    pub fingerprint: String,
    pub waiting_secs: u64,
}

/// A single downscaled output thumbnail (86ajtwq28): `w×h` RGBA8 pixels, the bytes carried
/// **base64**-encoded so they ride the JSON wire compactly. Built by [`ThumbView::from_rgba`]
/// on the host from a [`FrameBuffer::thumbnail`](selahcue_present::FrameBuffer) readback; the
/// operator forwards `rgba` straight to its `<canvas>` (the webview `atob`-decodes it).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ThumbView {
    pub w: u32,
    pub h: u32,
    /// Base64 (standard) of the row-major RGBA8 bytes (`4·w·h` before encoding).
    pub rgba: String,
}

impl ThumbView {
    /// Build a thumbnail from raw row-major RGBA8 `bytes` (`4·w·h`), base64-encoding them for
    /// the JSON wire. The wire crate owns this encoding so the host + operator agree exactly.
    pub fn from_rgba(w: u32, h: u32, bytes: &[u8]) -> Self {
        use base64::Engine;
        ThumbView {
            w,
            h,
            rgba: base64::engine::general_purpose::STANDARD.encode(bytes),
        }
    }
}

/// One plan item as the operator UI renders it — the wire form of an item view.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanItemView {
    /// Stable plan-item id (what the UI sends back via [`Command::SelectItem`]).
    pub id: u64,
    /// Stable item-kind tag (e.g. `"song"`, `"scripture"`).
    pub kind: String,
    pub title: String,
    /// This item is currently on the audience (Live) output.
    pub is_live: bool,
    /// This item is currently staged in Preview.
    pub is_staged: bool,
    /// Slide count for multi-slide items (songs, story S8-1). Skip-if-none
    /// keeps every pinned fixture byte-identical; absent = a single slide.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub slide_count: Option<u32>,
    /// Current within-item slide (0-based), present for the live/staged item.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<u32>,
    /// Per-item theme override (built-in name), if this item overrides the global
    /// theme (S8-3d). Skip-if-none keeps every pinned fixture byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
}

/// A snapshot of the active timer for the operator UI (`None` when no timer is running).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TimerSnapshot {
    /// Seconds remaining (countdown); `None` for a count-up timer.
    pub remaining_secs: Option<u32>,
    pub elapsed_secs: u32,
    pub time_up: bool,
    /// Within the warning threshold (and not yet up).
    pub warn: bool,
    pub running: bool,
    /// The countdown is paused (banked, not counting). `running` is `false` while
    /// paused; this field lets the UI distinguish paused from stopped. `serde(default)`
    /// keeps older-host frames (no `paused` key) parseable; skip-if-false keeps the common
    /// (not-paused) frame byte-identical to a pre-pause host — matching `total_secs`.
    #[serde(default, skip_serializing_if = "is_false")]
    pub paused: bool,
    /// The countdown's full length in seconds (`None` for a count-up timer). Lets the UI
    /// reset to the original duration even after overrun, where `remaining + elapsed` no
    /// longer equals the original (elapsed keeps growing past TIME UP). Skip-if-none keeps
    /// the change additive/byte-stable.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub total_secs: Option<u32>,
}

/// A snapshot of the full operator view: the plan with per-item Live/Preview flags,
/// plus the current live/staged indices, blackout, and any active timer. Carried by
/// [`ServerMessage::OperatorState`] so a remote operator UI renders host-authoritative
/// state rather than a local guess.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OperatorStateView {
    pub plan_name: String,
    pub items: Vec<PlanItemView>,
    /// Index into `items` currently on Live, if any.
    pub live_index: Option<usize>,
    /// Index into `items` currently staged in Preview, if any.
    pub staged_index: Option<usize>,
    pub blackout: bool,
    /// The active timer, if one is running.
    pub timer: Option<TimerSnapshot>,
    /// The scripture reference staged in Preview (when `staged_index` is None
    /// because Preview holds a scripture slide). Omitted when absent, so the
    /// v2 byte-pinned fixtures are unchanged.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub staged_scripture: Option<String>,
    /// The scripture reference on the Live output, if Live shows one.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub live_scripture: Option<String>,
    /// A removed-but-still-on-screen plan item's title on Live (a free slide —
    /// NOT a scripture). Omitted when absent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub live_free_text: Option<String>,
    /// The id of the authored deck slide on Live (Design 2.0), if an authored slide is presented
    /// rather than plan/scripture content. Host-truth for the operator grid's LIVE ring. Omitted
    /// when absent so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub live_authored_id: Option<u64>,
    /// The physical outputs (main/stage) and their display assignments — filled
    /// by the desktop host; empty (and omitted on the wire) elsewhere.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub outputs: Vec<OutputStatusView>,
    /// The attached physical displays (for the assignment picker) — desktop-only.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub displays: Vec<DisplayView>,
    /// Translation codes THIS host can stage/search (the picker must offer the
    /// host's list, not the shell's — they can differ across versions).
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub translations: Vec<String>,
    /// The active audience-output theme name (empty = the host did not report one,
    /// e.g. an older host). Omitted on the wire when empty so the v2 byte-pinned
    /// fixtures are unchanged.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub theme: String,
    /// The theme names this host offers (drives the picker). Omitted when empty.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub themes: Vec<String>,
    /// The SAVED (named custom) themes in the library (86ajq4xmy) — each `name` + its
    /// serialized `Theme`, so the Theme Designer can list + load them. Omitted when
    /// empty so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub saved_themes: Vec<SavedThemeView>,
    /// The per-SCREEN theme map (86ajq321k): each Audience-class `screen` and its assigned
    /// theme `name`, so the Screens page shows a distinct theme per screen. Omitted when
    /// empty so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub screen_themes: Vec<ScreenThemeView>,
    /// The SCREEN REGISTRY (Screens page — dynamic registry): every managed screen
    /// (built-in + virtual) with its role, enable state, deletability, and theme. Drives
    /// the Screens page rows, the Enable toggle, and the delete-on-virtual affordance.
    /// Omitted when empty (an older/non-desktop host) so the pinned v2 fixtures stay
    /// byte-identical; the shell falls back to `screen_themes` when this is absent.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub screens: Vec<ScreenView>,
    /// The recent live-transcript segments (a bounded tail, oldest first) for the
    /// operator's transcript panel (R3). Omitted when empty so the pinned v2 fixtures
    /// stay byte-identical.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub transcript: Vec<TranscriptSegmentView>,
    /// The current streaming INTERIM line (recognised words for the utterance still being
    /// spoken), shown live below the finalised transcript and cleared when it finalises.
    /// `None` when nothing is mid-utterance; omitted then so the pinned fixtures stay
    /// byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub partial_transcript: Option<String>,
    /// The pending scripture-detection approval queue (R4) — candidates the operator
    /// one-click stages. Omitted when empty so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub detections: Vec<DetectionView>,
    /// The stage/confidence template the confidence monitor is rendering
    /// (`worship` / `scripture` / `timer-only`). Empty = the host did not report one (an older
    /// host); omitted on the wire when empty so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub stage_template: String,
    /// The production message on the confidence monitor, if any (stage-only). Omitted when
    /// absent so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub stage_message: Option<String>,
}

/// serde default/skip for a bool that defaults to `true`: an absent field deserialises as
/// `true`, and a `true` value is omitted on serialisation — so an additive `is_final`-style
/// flag stays byte-identical for clients/fixtures that predate it.
fn default_true() -> bool {
    true
}
fn is_true(v: &bool) -> bool {
    *v
}

/// One live-transcript segment as the operator UI renders it (wire form of a
/// `selahcue_core::transcript::TranscriptSegment`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TranscriptSegmentView {
    /// Stable segment id (monotonic within the session).
    pub id: u64,
    /// Utterance start, in ms from the session origin.
    pub start_ms: u64,
    /// Utterance end, in ms from the session origin.
    pub end_ms: u64,
    /// The recognised text (already length-bounded by the core).
    pub text: String,
}

/// One queued scripture detection awaiting operator approval (the approval queue row).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DetectionView {
    /// Queue id — echoed back by [`Command::ApproveDetection`] / [`Command::DismissDetection`].
    pub id: u64,
    /// The canonical, parseable reference (e.g. `"Romans 8:28"`) — stages directly.
    pub reference: String,
    /// The verse text for the reference in the host's default translation, so the
    /// operator sees WHAT they would stage. Omitted when the host cannot resolve it
    /// (e.g. an older host, or a reference outside the bundle).
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub text: String,
    /// Detector match confidence as a whole percent (`0..=100`), e.g. `94` renders as
    /// "94% MATCH". Populated by the R4 detection engine: a high fixed score for an
    /// explicitly-spoken reference, or the fuzzy quote matcher's coverage score for a
    /// paraphrase. `None` only when the host reports no score (e.g. an older host). `u8`
    /// (not `f32`) keeps the `Eq` derive; skip-if-none keeps the pinned v2 fixtures
    /// byte-identical when absent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub confidence: Option<u8>,
}

/// One saved (named custom) theme in the library (86ajq4xmy).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SavedThemeView {
    pub name: String,
    /// The serialized `Theme` (opaque to the wire — the shell/Designer deserializes it).
    pub theme_json: String,
}

/// One Audience-class screen's assigned theme (86ajq321k).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScreenThemeView {
    /// The screen id (`main` / `lower-third` / `stream`).
    pub screen: String,
    /// The assigned theme name (a built-in or a saved-library name).
    pub theme: String,
}

/// One entry in the SCREEN REGISTRY (Screens page — dynamic registry): a screen the
/// operator manages, with its role, enable state, and whether it may be deleted. The
/// registry supersedes the fixed audience-screen set — built-ins (`main`/`lower-third`/
/// `stream`/`stage`) plus any virtual screens the operator added.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScreenView {
    /// The screen id (`main` / `lower-third` / `stream` / `stage`, or a minted virtual id).
    pub screen: String,
    /// Stable role tag: `main` / `lower-third` / `stream` (Audience-class) or `stage`.
    pub role: String,
    /// Whether the screen is currently enabled (a disabled screen composes safe-black).
    pub enabled: bool,
    /// Whether the operator may DELETE this screen (true only for virtual screens;
    /// built-ins may be disabled but never deleted).
    pub deletable: bool,
    /// The screen's assigned theme name (Audience-class only), if any. `None` for the
    /// `stage` screen (it renders a stage layout, not a theme) or a screen following the
    /// global theme.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
    /// The screen's per-output configuration (orientation, scaling/fit, mirror, delay, frame
    /// rate, safe-area guides, per-layer visibility). Omitted on the wire when every field is
    /// at its default, so the pinned v2 fixtures stay byte-identical for a screen nobody has
    /// configured.
    #[serde(default, skip_serializing_if = "OutputConfigView::is_default")]
    pub config: OutputConfigView,
}

/// How an output fits the composed live frame into its display surface. Applied as a pure
/// integer buffer transform on the host (deterministic, NFR-014). Additive on the wire via
/// [`Default`] + `skip_serializing_if`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum ScaleFit {
    /// Cover the surface, cropping overflow (preserve aspect). The default.
    #[default]
    Fill,
    /// Contain within the surface, letterboxing (preserve aspect, no crop).
    Fit,
    /// Stretch to the exact surface, distorting aspect.
    Stretch,
}

/// Per-layer visibility mask for one output. Each flag gates a compositing layer category at
/// compose time; hiding a layer never blanks the frame. Defaults to all-visible.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct LayerVisibility {
    pub background: bool,
    pub text: bool,
    pub lower_third: bool,
    pub logo: bool,
    pub timer: bool,
}

impl Default for LayerVisibility {
    fn default() -> Self {
        Self {
            background: true,
            text: true,
            lower_third: true,
            logo: true,
            timer: true,
        }
    }
}

/// One screen's per-output configuration, surfaced on [`ScreenView`] and driven by the
/// `SetOutput*` / `SetScreenLayerVisible` commands. Every field defaults to a
/// no-op/identity value, so [`is_default`](OutputConfigView::is_default) lets an
/// unconfigured screen stay off the wire (pinned-fixture safe).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OutputConfigView {
    /// Orientation as quarter-turns clockwise (`0`=Landscape … `3`=Portrait flipped).
    pub orientation: u8,
    /// Scaling/fit mode.
    pub scale_fit: ScaleFit,
    /// Whether the output is mirrored horizontally.
    pub mirror: bool,
    /// Present delay in milliseconds (bounded by [`MAX_OUTPUT_DELAY_MS`]).
    pub delay_ms: u32,
    /// Target frame rate in fps (within `[MIN_FRAME_RATE, MAX_FRAME_RATE]`).
    pub frame_rate: u16,
    /// Whether safe-area guides show on the OPERATOR preview (never the audience output).
    pub safe_area_guides: bool,
    /// Per-layer visibility mask.
    pub layers: LayerVisibility,
    /// Whether this screen is delivered as an NDI output (Audience-class `stream`/`lower-third`
    /// feeds only). The config persists + surfaces even without the host's NDI feature; actual
    /// transmission is a feature-gated sink. Default `false`.
    #[serde(default, skip_serializing_if = "is_false")]
    pub ndi_enabled: bool,
    /// The NDI source NAME broadcast on the network (bounded by [`MAX_NDI_NAME_LEN`]). Empty
    /// when NDI is not configured; skipped on the wire then, so a non-NDI screen's config stays
    /// byte-stable.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub ndi_name: String,
}

impl Default for OutputConfigView {
    fn default() -> Self {
        Self {
            orientation: 0,
            scale_fit: ScaleFit::Fill,
            mirror: false,
            delay_ms: 0,
            frame_rate: MAX_FRAME_RATE,
            safe_area_guides: false,
            layers: LayerVisibility::default(),
            ndi_enabled: false,
            ndi_name: String::new(),
        }
    }
}

impl OutputConfigView {
    /// Whether every field is at its default (identity) value — the `skip_serializing_if`
    /// predicate that keeps an unconfigured screen off the wire.
    pub fn is_default(&self) -> bool {
        *self == Self::default()
    }
}

/// One output role (main/stage) and where it currently renders.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OutputStatusView {
    /// Stable role tag: `"main"` or `"stage"`.
    pub role: String,
    /// The display it renders on (its name), if known.
    pub display: Option<String>,
    /// Output surface size in pixels.
    pub width: u32,
    pub height: u32,
    /// Whether the role has a persisted display assignment.
    pub assigned: bool,
    /// The persisted display key for this role (drives the picker's selection).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub assigned_key: Option<String>,
    /// The measured output frame rate (fps), derived honestly from the desktop present loop
    /// (an EWMA of present intervals). `None` when unmeasured (older/non-desktop host) — the
    /// UI shows a neutral dash, never a fabricated number.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fps: Option<u16>,
    /// Frames the host deferred (a lost/outdated swapchain) on this output since launch — the
    /// honest dropped-frame count. `None` when unmeasured.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub dropped_frames: Option<u64>,
    /// Honest signal-health label: `"healthy"` (monitor attached + presenting), `"degraded"`
    /// (recent dropped frames), or `"no_signal"` (no monitor). `None` when the host reports
    /// nothing — the UI shows a neutral dash, never a fabricated status.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub signal: Option<String>,
}

/// One scripture search hit: the stageable reference plus its verse text
/// (so operators never pick a verse blind).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ScriptureHitView {
    /// e.g. `"Romans 8:28"` — parseable, stages directly.
    pub reference: String,
    /// The verse text in the searched translation.
    pub text: String,
}

/// One verse in a fetched chapter (reply to [`Command::GetChapter`]).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerseView {
    /// Verse number within the chapter.
    pub number: u16,
    /// The verse text in the fetched translation.
    pub text: String,
}

/// One attached physical display (for the assignment picker).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayView {
    /// Stable key used by [`Command::AssignOutput`].
    pub key: String,
    pub name: String,
    pub width: u32,
    pub height: u32,
}

/// Why a request was denied. A closed set so clients can react programmatically.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DenyReason {
    /// The device's role lacks the required permission.
    Forbidden,
    /// The session token was missing, unknown, or revoked.
    Unauthenticated,
    /// The command was malformed or referenced something unknown.
    BadRequest,
}

/// A controller's request to establish a session, presenting its device identity
/// and the bearer token it received at pairing time.
///
/// `Debug` is hand-written to **redact the token** (mirroring
/// [`SessionToken`](crate::session::SessionToken)): this frame carries a live
/// credential, and a transport that logged it via a derived `Debug` would write
/// the token to logs in cleartext.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuthRequest {
    pub v: u16,
    pub device_id: String,
    pub token: String,
}

impl AuthRequest {
    /// Whether the sender speaks a protocol version this build understands (see
    /// [`Request::version_supported`]).
    pub fn version_supported(&self) -> bool {
        self.v == VERSION
    }
}

impl std::fmt::Debug for AuthRequest {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AuthRequest")
            .field("v", &self.v)
            .field("device_id", &self.device_id)
            .field("token", &"<redacted>")
            .finish()
    }
}

/// The operator's reply to an [`AuthRequest`].
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "auth", rename_all = "snake_case")]
pub enum AuthResponse {
    /// Session established; the device holds `role`.
    Granted { role: Role },
    /// Authentication failed.
    Rejected { reason: DenyReason },
}

/// The first frame a client sends after the WebSocket handshake: authenticate an
/// already-paired device, or redeem a pairing code to become one.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "hello", rename_all = "snake_case")]
pub enum Hello {
    /// Authenticate with previously issued credentials.
    Auth(AuthRequest),
    /// Redeem a single-use pairing code (from the operator's QR) for credentials.
    Pair(PairRequest),
}

/// A device's request to redeem a pairing code (FR-086/174). The code is short-lived
/// and single-use; the server additionally requires **host confirmation** before
/// granting. `Debug` redacts the code — it is a live (if brief) credential.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairRequest {
    pub v: u16,
    /// The pairing code shown/encoded by the operator.
    pub code: String,
    /// Human-readable device name shown to the operator for confirmation
    /// (e.g. "Dami's iPhone"). Untrusted display text.
    pub device_name: String,
    /// Device platform / OS shown alongside the name on the operator's Remote Control
    /// list (e.g. "iOS", "Android", "iPadOS"). Untrusted display text; optional and
    /// declared LAST with skip-when-empty so a client that omits it (and the pinned
    /// cross-language fixtures) stay byte-identical.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub platform: String,
}

impl PairRequest {
    /// Whether the sender speaks a protocol version this build understands.
    pub fn version_supported(&self) -> bool {
        self.v == VERSION
    }
}

impl std::fmt::Debug for PairRequest {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PairRequest")
            .field("v", &self.v)
            .field("code", &"<redacted>")
            .field("device_name", &self.device_name)
            .field("platform", &self.platform)
            .finish()
    }
}

/// The operator's reply to a [`PairRequest`]. On success the connection continues
/// **already authenticated** with `role`; the device stores `device_id` + `token`
/// for later reconnects. `Debug` redacts the token.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "pair", rename_all = "snake_case")]
pub enum PairResponse {
    Granted {
        device_id: String,
        token: String,
        role: Role,
    },
    /// Interim: the request is parked, awaiting the operator's approve/deny (86ajxhv0q). Sent ONCE
    /// right after parking; the terminal `Granted`/`Rejected` follows. Additive — lets the device
    /// show a "waiting for the operator" state instead of an opaque wait (older clients that don't
    /// know this variant simply keep waiting for the terminal reply).
    Parked,
    /// The code was invalid/expired, the host declined, or pairing is not enabled.
    Rejected { reason: DenyReason },
}

impl std::fmt::Debug for PairResponse {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PairResponse::Granted {
                device_id, role, ..
            } => f
                .debug_struct("PairResponse::Granted")
                .field("device_id", &device_id)
                .field("token", &"<redacted>")
                .field("role", &role)
                .finish(),
            PairResponse::Parked => f.write_str("PairResponse::Parked"),
            PairResponse::Rejected { reason } => f
                .debug_struct("PairResponse::Rejected")
                .field("reason", &reason)
                .finish(),
        }
    }
}

/// The out-of-band pairing invite the operator displays (as a QR / URI): where to
/// connect, which certificate to trust (the pin), and the single-use code.
///
/// URI form: `selahcue://pair?host=<h>&port=<p>&pin=<hex64>&code=<c>`. Field values
/// are restricted to URL-safe characters ([`PairingInvite::to_uri`] refuses others),
/// so no percent-encoding is needed on either side.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PairingInvite {
    pub host: String,
    pub port: u16,
    /// Lowercase hex SHA-256 pin of the operator's certificate.
    pub pin_hex: String,
    /// The single-use pairing code.
    pub code: String,
}

impl PairingInvite {
    /// Characters allowed in `host`/`pin_hex`/`code` values (URL-safe, no escaping).
    fn value_ok(s: &str) -> bool {
        !s.is_empty()
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | ':' | '_'))
    }

    /// Encode as the `selahcue://pair?...` URI (the QR payload). Returns `None` if a
    /// field contains characters outside the URL-safe set.
    pub fn to_uri(&self) -> Option<String> {
        if !(Self::value_ok(&self.host)
            && Self::value_ok(&self.pin_hex)
            && Self::value_ok(&self.code))
        {
            return None;
        }
        Some(format!(
            "selahcue://pair?host={}&port={}&pin={}&code={}",
            self.host, self.port, self.pin_hex, self.code
        ))
    }

    /// Parse a `selahcue://pair?...` URI. Returns `None` for anything malformed;
    /// never panics on untrusted input.
    pub fn parse_uri(uri: &str) -> Option<Self> {
        let query = uri.strip_prefix("selahcue://pair?")?;
        let mut host = None;
        let mut port = None;
        let mut pin = None;
        let mut code = None;
        for pair in query.split('&') {
            let (k, v) = pair.split_once('=')?;
            if !Self::value_ok(v) {
                return None;
            }
            match k {
                "host" => host = Some(v.to_string()),
                "port" => port = Some(v.parse::<u16>().ok()?),
                "pin" => pin = Some(v.to_string()),
                "code" => code = Some(v.to_string()),
                _ => {} // ignore unknown params (forward compatibility)
            }
        }
        Some(PairingInvite {
            host: host?,
            port: port?,
            pin_hex: pin?,
            code: code?,
        })
    }
}

/// Serialize any protocol message to a JSON string for transport.
pub fn to_json<T: Serialize>(msg: &T) -> Result<String, serde_json::Error> {
    serde_json::to_string(msg)
}

/// Parse a protocol message from a JSON string received over the wire.
pub fn from_json<'a, T: Deserialize<'a>>(s: &'a str) -> Result<T, serde_json::Error> {
    serde_json::from_str(s)
}
