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
pub const VERSION: u16 = 1;

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
    /// Search scripture (does not push live).
    ScriptureSearch { query: String },
    /// Stage a scripture reference for the operator to review before going live.
    StageScripture { reference: String },
    /// Request the current live/preview state.
    GetState,
    /// Request the full operator view (plan + per-item live/preview flags + blackout),
    /// so a remote operator UI can render authoritative state from the host.
    GetOperatorState,
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
    /// Results of a `ScriptureSearch`.
    ScriptureResults {
        query: String,
        references: Vec<String>,
    },
    /// The full operator view (reply to [`Command::GetOperatorState`]).
    OperatorState { view: OperatorStateView },
    /// A protocol-level or transport-level error not tied to a single request.
    Error { message: String },
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

/// Serialize any protocol message to a JSON string for transport.
pub fn to_json<T: Serialize>(msg: &T) -> Result<String, serde_json::Error> {
    serde_json::to_string(msg)
}

/// Parse a protocol message from a JSON string received over the wire.
pub fn from_json<'a, T: Deserialize<'a>>(s: &'a str) -> Result<T, serde_json::Error> {
    serde_json::from_str(s)
}
