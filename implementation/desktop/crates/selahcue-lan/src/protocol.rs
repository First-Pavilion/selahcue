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
    /// Stage a specific WITHIN-ITEM slide of a plan item in Preview (the Live Console slide picker,
    /// `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §6). Like [`SelectItem`] but jumps straight to
    /// slide `slide_index` (clamped to the item's slide count) instead of slide 0 — Preview only,
    /// never Live (FR-012/FR-115). Additive/back-compatible; the same `Navigate` permission as
    /// [`SelectItem`]/[`Next`]/[`Previous`] (staging is not an escalation to Live).
    SelectSlide { item_id: u64, slide_index: u32 },
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
    ///
    /// `next_slide_json` (additive, skip-if-none) is the serialized `AuthoredSlide` that comes
    /// AFTER this one in the deck, sent so the host-rendered Stage/Confidence monitor can show a
    /// deck-aware "next" line (the host stays deck-blind — Approach A — so the operator, which
    /// owns the deck cursor, supplies it). Absent (`None`) at the end of a deck or from a caller
    /// that does not provide it; the wire stays byte-identical to the pre-field fixture when it
    /// is `None`.
    PresentAuthoredSlide {
        slide_json: String,
        theme_json: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        next_slide_json: Option<String>,
    },
    /// Set (or clear, with `None`) a plan item's per-item theme OVERRIDE by built-in
    /// name (S8-3d). That item then renders on its own template instead of the global
    /// theme; an unknown item or name is rejected. Operator-only (output config).
    SetItemTheme {
        item_id: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        theme: Option<String>,
    },
    /// Set (or clear, with `None`) a plan item's linked CONTENT — the scripture
    /// passage, deck, or media asset it shows (ADR-0020 follow-up · plan editing).
    /// A `Scripture` link whose reference is blank clears the link (no half-linked
    /// item). An unknown item id, an unknown `link.kind`, or a scripture reference
    /// that does not parse is rejected; the plan is unchanged. Operator-only — this
    /// edits the plan, never the Live output.
    SetItemContent {
        item_id: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        link: Option<ContentLinkView>,
    },
    /// Set (or clear, with `None`) a plan item's responsible OWNER/role (FR-004 · plan editing).
    /// A blank owner clears it; an unknown item id is rejected. Operator-only — plan metadata,
    /// never the Live output.
    SetItemOwner {
        item_id: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        owner: Option<String>,
    },
    /// Set (or clear, with `None`) a plan item's planned DURATION in seconds (FR-004 · plan
    /// editing). An unknown item id is rejected. Operator-only — plan metadata, never Live.
    SetItemDuration {
        item_id: u64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        secs: Option<u32>,
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
    /// Open a new durable transcript session (86akcfftu): a session-boundary sibling of
    /// [`IngestTranscript`], sent once when listening starts, so the desktop-authoritative
    /// host (which owns the persistent transcript store) can open a transcript record with
    /// `started_at` before segments start arriving. `label`/`provider` describe the session
    /// for a future Transcripts list — `provider` is provider-erased free text (e.g.
    /// `"on-device-whisper"`/`"deepgram"`), never interpreted by the wire protocol itself, so
    /// this command needs no change when a new `TranscriptProvider` ships. Additive,
    /// back-compatible: an older desktop that has never heard of it is out of scope (same
    /// wire-version discipline as every other addition here); it changes no existing fixture.
    /// Requires the `Transcribe` permission (the same one `IngestTranscript` requires).
    StartTranscript { label: String, provider: String },
    /// Close the current durable transcript session, if one is open (a no-op otherwise):
    /// sets `ended_at` so a Transcripts list can show a real duration. Sent once when
    /// listening stops normally; a crash that skips this is handled separately, by a
    /// startup sweep over any transcript left with no `ended_at` — not by this command.
    /// Requires the `Transcribe` permission.
    EndTranscript,
    /// Resolve the transcript id that new AI-derived content (a generated sermon-note draft)
    /// should be attributed to right now (86akgqdv0; FR-123 "editable" half). Replaces the
    /// operator's former LOCAL query against its own (differently-located, Tauri
    /// `app_data_dir()`) database file — which could never see a real transcript id in a real
    /// launch, because only the desktop process ever creates a `transcript` row (PR #33 review,
    /// Sana F1). The desktop answers from the store it actually owns: the currently OPEN
    /// transcript if one is listening, else the most recently started one. `None` if no
    /// transcript has ever been recorded. A read — never changes state. Reply:
    /// [`ServerMessage::ActiveTranscriptId`]. Requires `Transcribe` — the same tier that may
    /// feed/open a transcript session, since this answers a question ABOUT that same stream.
    GetActiveTranscriptId,
    /// Load the persisted sermon-note draft for `transcript_id`, if any (86akgqdv0) — sent on
    /// Settings-panel activation so a draft from a prior session (or an edit left unread)
    /// reappears after a restart. Reply: [`ServerMessage::SermonNoteDraft`] with `draft: None`
    /// when nothing is persisted (not a `Denied` — an absent draft is a normal, common state,
    /// not a refusal). Requires `Transcribe` (see [`Self::GetActiveTranscriptId`]): loading
    /// AI-derived content generated from congregation speech is the same privilege tier as
    /// generating or feeding it.
    LoadSermonNoteDraft { transcript_id: i64 },
    /// Persist (upsert) a freshly generated sermon-note draft against `transcript_id` —
    /// `selahcue-operator`'s `generate_sermon_notes` persist-on-success path (86akgqdv0). A
    /// second call for the same `transcript_id` REPLACES the existing draft wholesale
    /// (regenerate-with-history is FR-129's separate, not-yet-built territory). Reply:
    /// [`ServerMessage::SermonNoteDraft`] (the row re-read from the store, the source of truth,
    /// never an echo of what was sent) on success, [`ServerMessage::Denied`] with
    /// [`DenyReason::BadRequest`] if the desktop refuses it (e.g. an oversized field, an
    /// inconsistent `ai_generated`/`disclosure` pairing, or an attempt to flip an existing
    /// draft's `ai_generated` from `true` to `false` — see
    /// [`SermonNoteDraftInput::disclosure_pairing_is_consistent`] and
    /// `selahcue_app::LiveController::apply`'s `SaveSermonNoteDraft` handler, PR #33 review,
    /// Sana N2 — Medium).
    ///
    /// **Requires [`crate::rbac::Permission::SaveSermonNotes`] — Operator only, NOT the
    /// broader `Transcribe` tier `LoadSermonNoteDraft`/`UpdateSermonNoteDraft`/
    /// `GetActiveTranscriptId` use (PR #33 review, Sana N2).** This feature originally gated
    /// the whole command family at `Transcribe`, reasoning that "the operator process that may
    /// generate/feed a transcript's derived content is the same one trusted to attach a label/
    /// disclosure/provider to it" — the same tier as `IngestTranscript`. Sana proved that
    /// reasoning wrong for Save specifically: unlike Load (read-only) and Update (structurally
    /// cannot touch the label — see [`SermonNoteEditInput`]), Save can plant a fully-formed,
    /// VALIDLY-LABELLED but entirely fabricated "AI-generated" draft (a Producer device can
    /// supply its own consistent `ai_generated: true` + non-empty `disclosure` — the pairing
    /// check above cannot catch a lie that is internally consistent), or wholesale-replace an
    /// already-persisted, possibly operator-edited draft outright, since `create` is an upsert.
    /// The operator console's own `generate_sermon_notes` flow is the ONLY legitimate caller of
    /// this command today; nothing else needs to attach new provenance or replace existing
    /// content. Narrowing to Operator closes both exploits with one RBAC-table change, rather
    /// than inventing an ownership/precondition mechanism this protocol has nowhere else.
    SaveSermonNoteDraft {
        transcript_id: i64,
        draft: SermonNoteDraftInput,
    },
    /// Apply an operator edit to an existing draft's TEXT only — title/summary/section content
    /// (86akgqdv0). See [`SermonNoteEditInput`] for why the AI-generated label/disclosure/
    /// provider cannot be reached from this command: there is no field to carry them. Reply:
    /// [`ServerMessage::SermonNoteDraft`] on success, [`ServerMessage::Denied`] with
    /// [`DenyReason::BadRequest`] if no draft exists for `transcript_id` yet or the desktop
    /// refuses an oversized field. Requires `Transcribe` (see [`Self::SaveSermonNoteDraft`]).
    UpdateSermonNoteDraft {
        transcript_id: i64,
        edit: SermonNoteEditInput,
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

    // --- Plan publish / hand-off (FR-006) and the plan lifecycle actions on the empty-plan
    //     frame `611:124` (FR-005). All five require the SAME existing `EditPlan` permission,
    //     because all five are statements about the plan DOCUMENT and none of them touches the
    //     live output. Deliberately not a new `PublishPlan` permission: no role in the table
    //     distinguishes publishing from editing, so a separate permission would be policy that
    //     nothing can express — dead by construction. The view-only frame `612:342` hides
    //     "edit/add/reorder/publish" as ONE group, which is the same grouping. ---
    /// Mark the plan's CURRENT revision as published — the coordinator→operator hand-off
    /// (FR-006). The operator's open copy is never force-refreshed: this only moves the
    /// published marker, so the client can show "Plan updated · Review changes" and let the
    /// operator choose when to reload (frame `612:1020`).
    ///
    /// **Changes nothing on the live output, and nothing in Preview.** Publishing is a
    /// statement about the document, not a cue.
    ///
    /// Repeatable and safe, but NOT idempotent: publishing an unchanged plan re-marks the same
    /// revision and clears no badge that was not already clear, yet it does increment `version`,
    /// which is on the wire and on screen. Calling it twice is harmless; it is not invisible.
    /// (An earlier version of this line said "idempotent" and then described the increment that
    /// makes it not so.)
    PublishPlan,
    /// Replace the plan with a fresh EMPTY one called `name` — "Create a service" on the
    /// empty-plan frame. The outgoing plan is not saved anywhere by this command; it is
    /// recoverable only through plan undo.
    ///
    /// A blank, over-long or control-character `name` is rejected
    /// ([`selahcue_core::plan::plan_label_valid`]). Never changes the live output: whatever is
    /// on air keeps airing as a free slide, exactly as removing the live item already does.
    NewPlan { name: String },
    /// Replace the plan with one built from the named starter template
    /// ([`selahcue_core::plan::PLAN_TEMPLATES`]), called `name`. An unknown `template` is
    /// rejected rather than silently falling back to a blank plan — a coordinator who asked
    /// for "Sunday Morning" and got an empty run sheet has been told nothing.
    ///
    /// The offered templates are reported on [`OperatorStateView::plan_templates`] so the
    /// picker renders the HOST's list rather than a transcribed copy of it.
    TemplatePlan { template: String, name: String },
    /// Replace the plan with a deep, independent copy of the CURRENT plan under `name`
    /// (FR-005) — the wire caller [`selahcue_core::plan::ServicePlan::duplicate`] never had.
    ///
    /// **This duplicates the plan that is loaded, not a previous one from a library.** The
    /// empty-plan frame's "Duplicate previous" needs a saved-plan library that does not exist:
    /// the desktop host persists exactly one plan row and `selahcue-app` cannot reach the data
    /// layer. Naming that limit here because a caller reading only the command name would
    /// reasonably assume the other meaning.
    DuplicatePlan { name: String },
    /// Replace the plan with `items` under `name` — the "Import" action on the empty-plan
    /// frame, as an explicit run-sheet list.
    ///
    /// A deliberately narrow surface: kind, title, and the two plan-metadata fields. Content
    /// LINKS are set afterwards with [`Command::SetItemContent`], so link parsing and
    /// resolution are not reimplemented on a second, less-tested path. This is **not** FR-139's
    /// portable plan bundle (items plus media refs), which is a separate piece of work.
    ///
    /// Rejected as a whole — never partially applied — when the name is invalid, any item's
    /// kind tag or title is invalid, or the list exceeds
    /// [`selahcue_core::plan::MAX_PLAN_ITEMS`]. A half-imported run sheet is worse than a
    /// refused one, because nothing tells the coordinator which half arrived.
    ImportPlan {
        name: String,
        items: Vec<ImportItemView>,
    },
}

/// A freshly generated sermon-note draft's content — [`Command::SaveSermonNoteDraft`]'s payload
/// (86akgqdv0). Carries no timestamps: the desktop stamps `created_at`/`edited_at` from its own
/// clock when it persists the row (the store's authority, not the operator's), mirroring every
/// other desktop-owned timestamp on this control link (e.g. a transcript's `started_at`).
///
/// `sections_json`/`scriptures_json` are themselves opaque JSON (`selahcue_core::providers::
/// NoteSection`'s items-XOR-points shape, FR-122) — this crate does not interpret them, the same
/// "opaque to the wire" precedent as [`Command::SetCustomTheme`]'s `theme_json` and
/// [`Command::PresentAuthoredSlide`]'s `slide_json`. Only `selahcue-operator` (which already
/// depends on `serde_json` for the wire to the JS UI) and the desktop's own `sermon_note_repo`
/// layer parse them.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SermonNoteDraftInput {
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
    /// FR-123: whether a generative model produced this draft.
    pub ai_generated: bool,
    /// FR-128: the fabrication-risk disclosure. `Some` exactly when `ai_generated` — the
    /// caller's (`GenerationOutcome`'s) invariant to keep; this layer stores whatever it is
    /// given without re-deriving or checking the pairing.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub disclosure: Option<String>,
    /// The serving provider's human-readable label (e.g. `"SelahCue AI"`, `"Local (offline)"`).
    pub provider: String,
    /// A model identifier, when the serving provider reports one. Honestly `None` when it
    /// doesn't — never invented data.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
}

impl SermonNoteDraftInput {
    /// FR-123/FR-128 (PR #33 review, Sana N2 — Medium): a non-empty fabrication disclosure
    /// must be present EXACTLY WHEN `ai_generated` is true — never present on a
    /// human-authored draft (nothing to disclose) and never absent on an AI-generated one.
    /// Before this check existed, `SaveSermonNoteDraft`'s handler accepted whatever pairing a
    /// caller sent, so any Transcribe-tier device could relabel an AI draft as human-authored
    /// by sending `ai_generated: false, disclosure: null`, silently stripping the FR-128
    /// warning.
    ///
    /// A SINGLE definition, consumed by both `selahcue_app::LiveController::apply`'s
    /// enforcement and this crate's own tests, so neither can drift from the other (this
    /// codebase has already been bitten once by a control that re-derived a conjunction
    /// instead of consuming the real one — see `CLAUDE.md`'s bounded-memory-tests notes).
    pub fn disclosure_pairing_is_consistent(&self) -> bool {
        let disclosure_present = self
            .disclosure
            .as_deref()
            .is_some_and(|d| !d.trim().is_empty());
        disclosure_present == self.ai_generated
    }
}

/// An operator-supplied edit to an existing draft's TEXT only — [`Command::UpdateSermonNoteDraft`]'s
/// payload (86akgqdv0). Deliberately carries none of `ai_generated`/`disclosure`/`provider`/
/// `model` — there is no field to smuggle them through, which is what makes "an edit cannot
/// touch the AI-generated label" a property of the WIRE CONTRACT itself, not a convention the
/// desktop's handler must remember to enforce.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SermonNoteEditInput {
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
}

/// A persisted sermon-note draft read back in full (86akgqdv0) — the desktop's reply to
/// [`Command::LoadSermonNoteDraft`], and the read-AFTER-write reply to
/// [`Command::SaveSermonNoteDraft`]/[`Command::UpdateSermonNoteDraft`]: the operator re-reads
/// the label/disclosure/timestamps from the store rather than trusting its own copy, the same
/// discipline the pre-LAN-redesign command handlers already followed.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SermonNoteDraftView {
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<String>,
    pub sections_json: String,
    pub scriptures_json: String,
    pub ai_generated: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub disclosure: Option<String>,
    pub provider: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    pub created_at_ms: i64,
    pub edited_at_ms: i64,
}

/// One row of a [`Command::ImportPlan`] run sheet.
///
/// Its own type rather than a reuse of [`PlanItemView`]: that view carries host-DERIVED state
/// (live/staged flags, slide counts, resolved link status) which an importing client cannot
/// know and must not be able to assert. Accepting it here would let a client claim an item was
/// live.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImportItemView {
    /// The stable item-kind tag (`"song"`, `"scripture"`, `"section"`, …). An unknown tag
    /// rejects the whole import.
    pub kind: String,
    /// Display title. Validated exactly like a plan name — non-blank, bounded, no control
    /// characters — because an import is the one path that can create hundreds of them at once.
    pub title: String,
    /// Optional owner (FR-004). Skip-if-none, so a minimal import stays compact.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner: Option<String>,
    /// Optional planned duration in seconds (FR-004).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub planned_secs: Option<u32>,
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
        /// The full `selahcue://pair?host=…&port=…&pin=…&code=…` invite the operator encodes as the
        /// scannable QR — the SAME payload the native output window's QR carries and the mobile
        /// controller's [`PairingInvite::parse_uri`] expects. `None` when the host cannot supply its
        /// LAN endpoint (an older host, or one built without [`crate::ControlServer::with_pairing_endpoint`]);
        /// the operator then shows the code without a fake QR rather than an unscannable one.
        #[serde(default, skip_serializing_if = "Option::is_none")]
        uri: Option<String>,
    },
    /// Reply to [`Command::GetActiveTranscriptId`] (86akgqdv0): the transcript id new
    /// AI-derived content should attach to right now, or `None` if no transcript has ever been
    /// recorded.
    ActiveTranscriptId {
        #[serde(default, skip_serializing_if = "Option::is_none")]
        transcript_id: Option<i64>,
    },
    /// Reply to [`Command::LoadSermonNoteDraft`]/[`Command::SaveSermonNoteDraft`]/
    /// [`Command::UpdateSermonNoteDraft`] (86akgqdv0): the draft as the store actually holds it
    /// after the operation, keyed to `transcript_id`. `draft: None` means no draft is persisted
    /// for this transcript yet (a normal state for `LoadSermonNoteDraft` — never for a
    /// successful Save/Update, which always has something to read back).
    SermonNoteDraft {
        transcript_id: i64,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        draft: Option<SermonNoteDraftView>,
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

/// The content a plan item links (ADR-0020 follow-up): the scripture passage, deck,
/// or media asset it shows. The wire form of `core::plan::ItemContent`, kept as
/// plain fields (a `kind` tag + the relevant payload) so the receiving client
/// renders link status (linked / unlinked / missing) and the reference/deck.
/// Absent on a [`PlanItemView`] = an *unlinked* / title-only item.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ContentLinkView {
    /// `"scripture"` | `"deck"` | `"media"`.
    pub kind: String,
    /// Scripture link: the canonical reference (e.g. `"Romans 8:28-30"`). Absent for deck/media.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reference: Option<String>,
    /// Scripture link: the bundled-translation code (`None` = the plan default).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub translation: Option<String>,
    /// Scripture link: verses-per-slide override (`None` = the plan default).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub verses_per_slide: Option<u16>,
    /// Deck link: the deck library id. Media link: the media library id. Absent for scripture.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub id: Option<u64>,
    /// Deck link: the deck's slide count, as synced by the deck-owning operator (the host has no
    /// deck store). Absent for scripture/media or a not-yet-synced link. Lets a presentation report
    /// its real slide count + stage a specific within-item slide (the Live Console slide picker).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub slide_count: Option<u32>,
    /// Scripture link: the verse-numbers mode — `"superscript"` | `"inline"` | `"hidden"`.
    /// Absent = the plan default. Absent for deck/media.
    ///
    /// **Carried, not yet applied.** It round-trips so the inspector can hold the coordinator's
    /// choice, but the host's slide composition does not read it yet; an unknown value degrades
    /// to the default rather than rejecting the link.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub verse_numbers: Option<String>,
    /// Whether the link RESOLVES, as far as the layer that built this view could tell:
    /// `"missing"` = checked and gone, `"unknown"` = **not checked**, absent = checked and fine.
    ///
    /// `"unknown"` is not a hedge, it is the honest answer for deck and media links coming from
    /// the host: decks are operator-owned by design and the host has no deck store, so it
    /// cannot answer. A client must render `"unknown"` as *not yet known* and let the layer
    /// that owns the library (the operator) supply the verdict — never as "fine". This mirrors
    /// [`OperatorStateView::output_health`], where `None` likewise means "not reported", not
    /// "healthy". Absent-equals-fine is the failure this field exists to prevent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    /// The link target's LAST KNOWN GOOD display name (e.g. a deck's title). The deck-owning
    /// operator supplies it on every link and relink, and an update that omits it leaves the
    /// stored name alone — so it is what lets a missing link be described by name once the
    /// library row is gone and the id resolves to nothing. A deck renamed in place keeps the
    /// older name until the item is next linked. Absent = no name was ever captured.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
}

/// Plan-level roll-up for the builder's right-hand Plan Summary panel and the run-sheet
/// header (FR-004). Every count is derived from the same items the view already carries, so
/// it never disagrees with them.
///
/// `missing` and `unknown` are deliberately SEPARATE totals rather than one "problem" count.
/// The host can only resolve scripture links, so folding decks and media into `missing` would
/// overstate what it knows, and folding them into a clean bill would understate it. `unknown`
/// is the count the operator still has to resolve against its own library.
///
/// **A `section` divider is not an item.** Every count and total here describes the
/// TRIGGERABLE run sheet: dividers are excluded from `items`, `assigned`, `missing`,
/// `unknown`, `planned_total_secs`, `planned_items` and `partial`, and reported only by
/// `sections`. The design draws it that way — node 608:875 reads "6 items" and
/// "Assigned 6 / 6" over six rows and three dividers. A divider is an inert label that never
/// fires, so it is not staffable and not schedulable; counting one in the assigned denominator
/// would make a fully staffed plan read as incomplete forever.
///
/// This is an invariant, not a filter applied on the way out: the domain REFUSES to put an
/// owner, a duration or a content link on a divider (`PlanError::NotApplicable`), and strips
/// any that an older build stored. So no frame can report `missing: 0` beside a row whose own
/// link says `"missing"`.
/// `serde(default)` on the container, matching every other view in this file: a field added
/// here later must not make an older host's frame unparseable to a newer client, which would
/// take the whole `OperatorStateView` down with it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct PlanSummaryView {
    /// Total TRIGGERABLE items — `section` dividers are **not** counted here (see the type
    /// doc). `items` is the denominator the UI renders `assigned` against.
    pub items: u32,
    pub songs: u32,
    pub scripture: u32,
    /// Slide-group items — "Presentation" in the UI.
    pub presentations: u32,
    pub media: u32,
    pub announcements: u32,
    pub timers: u32,
    /// Non-triggerable dividers. Reported separately and deliberately EXCLUDED from `items`,
    /// so `songs + scripture + presentations + media + announcements + timers == items`.
    pub sections: u32,
    /// Triggerable items with an owner assigned (FR-004). Never exceeds `items`: a divider
    /// cannot be given an owner, so it can neither be assigned nor inflate the denominator.
    pub assigned: u32,
    /// Triggerable items whose link was CHECKED and does not resolve.
    pub missing: u32,
    /// Triggerable items whose link could NOT be checked by the layer that built this view.
    pub unknown: u32,
    /// Sum of every item's planned duration, saturating. **Read `partial` before displaying
    /// this**: on its own it cannot say whether it covers the whole plan.
    pub planned_total_secs: u32,
    /// How many items carried a duration and so contributed to `planned_total_secs`.
    ///
    /// This separates the spec's two partial renderings: `0` with items present is "no
    /// durations at all" (`— · partial`), a non-zero count is a real subtotal
    /// (`12:30 · partial`). `planned_total_secs == 0` alone cannot tell them apart, because
    /// zero is a legitimate duration meaning "instant" (PLAN-SECTIONS-DURATIONS-spec §4.1-4.2).
    pub planned_items: u32,
    /// Whether `planned_total_secs` OMITS at least one item that could have had a duration —
    /// i.e. the total is a FLOOR for the service, not its length
    /// (PLAN-SECTIONS-DURATIONS-spec §4.2 · FR-202).
    ///
    /// A client rendering the total without this shows a number that reads as confidently
    /// precise while being wrong — the defect design-QA rejected these frames for once already
    /// ("8 items · 1:12:00" over rows summing 53:12). Computed in the SAME pass as the sum
    /// ([`selahcue_core::plan::ServicePlan::planned_total`]), because a separately-derived flag
    /// drifts from the number it describes and the drift is silent.
    ///
    /// Inert `section` dividers never set it: carrying no duration is their normal state, so
    /// counting them would mark every sectioned plan partial. Skip-if-false — a complete total
    /// simply omits the key.
    #[serde(default, skip_serializing_if = "is_false")]
    pub partial: bool,
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
    /// Current within-item slide (0-based); for the live/staged item this is the LIVE slide when
    /// the item is live, else the staged slide (drives the plan-row badge, back-compat).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub slide_index: Option<u32>,
    /// The STAGED (Preview) within-item slide (0-based), present only when this item is staged.
    /// Distinct from [`slide_index`] so the Live Console slide picker can mark PREVIEW and LIVE on
    /// DIFFERENT slides of the same presentation (when an item is both staged and live).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub staged_slide_index: Option<u32>,
    /// Per-item theme override (built-in name), if this item overrides the global
    /// theme (S8-3d). Skip-if-none keeps every pinned fixture byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub theme: Option<String>,
    /// The content this item links — scripture passage / deck / media (ADR-0020
    /// follow-up). Absent = an *unlinked* item. Skip-if-none keeps every pinned
    /// fixture byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub link: Option<ContentLinkView>,
    /// Responsible person/role for this item (FR-004); absent = unassigned. Skip-if-none keeps
    /// every pinned fixture byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner: Option<String>,
    /// Planned duration in seconds (FR-004); absent = unplanned. Skip-if-none keeps every pinned
    /// fixture byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub planned_secs: Option<u32>,
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
    /// The LIVE output's fault/recovery health (NFR-024 observability).
    ///
    /// **`None` means "this host does not report output health"** — an older host, or a
    /// peer with no compositor — and a client must render that as *unknown*, never as a
    /// fault. That distinction is the entire point: absent telemetry displayed as a hard
    /// failure is one of the fabrications this field was added to remove. Omitted on the
    /// wire when `None`, so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_health: Option<OutputHealthView>,
    /// The host's storage headroom for autosave. `None` = this host does not report it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub storage: Option<StorageHealthView>,
    /// The host's session-recovery state. `None` = this host does not report it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session: Option<SessionHealthView>,
    /// Plan-level roll-up (counts, assigned, planned total) for the Plan Summary panel.
    /// `None` = this host does not report it; omitted on the wire then, so the pinned v2
    /// fixtures stay byte-identical and an older client is unaffected.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub summary: Option<PlanSummaryView>,
    /// Who this frame was built FOR, and what the host says they may do (FR-006 view-only,
    /// frame `612:342`). `None` = this host does not report it.
    ///
    /// **`None` is not "view only".** It is the same third state `output_health`, `storage` and
    /// `session` use: an older host, or a view built by a layer with no authenticated session
    /// (the bare controller knows the plan but not who is asking). A client that renders absent
    /// telemetry as a restriction takes controls away from someone who has them, which is the
    /// mirror image of the fabrication this codebase already refuses on the health fields.
    /// Skip-if-none, so the pinned v2 fixtures stay byte-identical.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub viewer: Option<ViewerView>,
    /// The plan's publish / hand-off state (FR-006). `None` = this host does not report it.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub publish: Option<PublishStateView>,
    /// The starter templates THIS host offers, in picker order (FR-005). Omitted when empty.
    ///
    /// Reported rather than transcribed, for the reason `themes` and `translations` are: the
    /// set is a product decision that will change, and a client holding its own copy shows a
    /// template the host cannot build the moment the two disagree.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub plan_templates: Vec<PlanTemplateView>,
}

/// The authenticated session a frame was built for, and the host's own verdict on what it may
/// do (FR-006 view-only).
///
/// Both fields are present deliberately, and they are not redundant. `role` is an IDENTITY, for
/// the "connected as Assistant" label. `can_edit` is a POLICY VERDICT, and it is on the wire so
/// that no client has to re-derive it: the Dart controller already keeps a hand-transcribed copy
/// of `Role::permissions()` (`lib/models/rbac.dart`, "transcribed verbatim from rbac.rs"), and a
/// transcription is a copy that drifts silently the first time the table moves. They cannot
/// disagree with each other because both are produced by [`ViewerView::for_role`], which asks
/// the RBAC choke point rather than restating its policy.
///
/// # This is an affordance, never a gate
///
/// `can_edit` decides which controls a client OFFERS. It decides nothing about what the host
/// ACCEPTS: every command is still checked by [`authorize`](crate::rbac::authorize) at the
/// server before the handler runs, so a client that ignores this field entirely and sends
/// `RenameItem` as a Viewer is refused with `Denied{forbidden}` exactly as before. Nothing here
/// widens what any role can do.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct ViewerView {
    /// The role the host granted this session.
    pub role: Role,
    /// Whether that role may edit the plan document — and therefore whether the edit, add,
    /// reorder and publish controls should be shown at all. The view-only frame hides them
    /// rather than greying them, because the persona pain being fixed is "seeing controls they
    /// can't use" (`UX-STATE-MATRIX.md:111`).
    pub can_edit: bool,
}

impl ViewerView {
    /// The view for `role`, asking the RBAC choke point what it may do.
    ///
    /// The ONE place `can_edit` is computed. It consumes
    /// [`can_edit_plan`](crate::rbac::can_edit_plan), which in turn runs the real
    /// `authorize()` — so this field cannot drift from enforcement without the drift
    /// showing up in enforcement too.
    pub fn for_role(role: Role) -> Self {
        ViewerView {
            role,
            can_edit: crate::rbac::can_edit_plan(role),
        }
    }
}

/// The plan's publish / hand-off state (FR-006) — enough for a client to render the version
/// label, the draft/published distinction, and the "Plan updated · Review changes" badge, and
/// nothing more.
///
/// # Why counters on the WIRE, and not the plan twice over
///
/// Frame `612:1020` asks for a *badge* and a reload-vs-keep choice, not a diff. So this carries
/// scalars and the client decides when to re-read; the host never force-refreshes anyone and
/// never reorders the live run sheet, which is the whole point of the badge.
///
/// This is a statement about the WIRE only. It is not an argument that no published copy exists
/// anywhere: the host keeps one, because `changed` reports whether the plan DIFFERS rather than
/// whether it was touched, and only a document can answer that. See
/// `LiveController::published_plan`, which prices that copy against the 60 undo snapshots it
/// sits beside. What is avoided here is shipping a whole second plan to every client on every
/// frame, which is a different cost from holding one in the host.
///
/// # In-session only, this slice
///
/// These counters live in the running controller and are NOT persisted. After a restart the
/// plan reads as a draft again until it is republished. That degrades quietly and in the safe
/// direction — it can only ever fail to show a badge, never show a false one — but it is a real
/// limitation and persisting it needs a `session_repo` migration that this slice does not make.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct PublishStateView {
    /// Monotonic revision of the plan DOCUMENT. Bumped once per applied plan edit, and by undo
    /// and redo — both move the document, and a badge that ignored undo would tell an operator
    /// the plan matched what was published when it no longer did.
    ///
    /// An opaque ordinal for change detection; it is not the `v4` a user sees.
    pub revision: u64,
    /// The `revision` captured by the last [`Command::PublishPlan`]. `None` = never published,
    /// i.e. the plan is a DRAFT.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub published_revision: Option<u64>,
    /// How many times this plan has been published — the `v4 (published)` label in the plan
    /// header (`COMPONENT-SPECS.md:150`). `0` = never published.
    ///
    /// Separate from `revision` because the two count different things and the UI shows this
    /// one: `revision` counts edits, `version` counts hand-offs. Saturating.
    #[serde(default, skip_serializing_if = "is_zero_u32")]
    pub version: u32,
    /// The plan DIFFERS from what was published → show "Plan updated · Review changes".
    ///
    /// Compared against the published DOCUMENT, not against `published_revision`. The two are
    /// not the same question and only this one is worth interrupting an operator with: an edit
    /// that is then undone moves the revision but restores the content, and a badge derived
    /// from the counter would sit over a plan identical to the published one with nothing in it
    /// to review. So `revision != published_revision` with `changed: false` is a normal,
    /// meaningful state — touched, but not different.
    ///
    /// **Always `false` while `published_revision` is `None`.** With no baseline there is
    /// nothing to review against, and a badge on a plan that was never published would be
    /// telling the operator about a comparison that never happened. Skip-if-false.
    #[serde(default, skip_serializing_if = "is_false")]
    pub changed: bool,
}

/// One starter template the host offers (FR-005), as the picker renders it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PlanTemplateView {
    /// Stable id to send back as [`Command::TemplatePlan`]`::template`.
    pub id: String,
    /// Display name.
    pub name: String,
    /// How many items the template seeds, so the picker can say "5 items" without the client
    /// holding the template's contents.
    pub items: u32,
}

/// serde skip for a `u32` counter that has not moved yet.
fn is_zero_u32(v: &u32) -> bool {
    *v == 0
}

/// The live output's fault/recovery health, as the operator UI renders it (NFR-024).
///
/// The engine has always held the last good frame on a fault; until this view existed
/// nothing outside the engine could observe that it had. Present on this struct at all
/// means the host DOES report health — `held == false` here is a positive statement that
/// the output is healthy, which is different from the field's absence on
/// [`OperatorStateView`] meaning the host cannot say.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct OutputHealthView {
    /// The live output is holding its last good frame right now. The audience still sees
    /// content — this is the never-blank guarantee working, not a blank screen.
    pub held: bool,
    /// Stable snake_case reason for the current hold (`"gpu_device_lost"`,
    /// `"decoder_fault"`, `"ipc_stall"`, `"disk_full"`). Absent when the output is not
    /// held, so a stale reason can never appear beside a healthy output.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fault: Option<String>,
    /// Times the live output has been held this session (monotonic).
    ///
    /// Counters, not a fault log: a log would be an unbounded queue. They also carry
    /// information the `held` flag cannot — a client polling at 1 Hz sees this increment
    /// even when the hold began and ended between two polls, which is how a recovery
    /// becomes observable without any event channel. Skip-if-zero keeps a healthy host's
    /// frame compact.
    #[serde(default, skip_serializing_if = "is_zero_u64")]
    pub holds: u64,
    /// Times the live output has recovered this session (monotonic). See [`Self::holds`].
    #[serde(default, skip_serializing_if = "is_zero_u64")]
    pub recoveries: u64,
}

/// serde skip for a counter that has not moved yet.
fn is_zero_u64(v: &u64) -> bool {
    *v == 0
}

/// Longest operator-facing error text carried on the wire.
///
/// Host errors (a SQLite message, a transport failure with a nested cause) can be arbitrarily
/// long. Health fields retain exactly one at a time and each replaces the last, but an uncapped
/// single string is still unbounded growth, so every one is truncated through
/// [`truncate_for_wire`].
pub const MAX_ERROR_TEXT_LEN: usize = 200;

/// Truncate to at most `max` bytes without splitting a UTF-8 character.
///
/// Slicing a `String` at an arbitrary byte index panics mid-character, and error text is exactly
/// where non-ASCII arrives — a hostname, a path, an OS message in the user's locale. A panic
/// while reporting a failure would take out the reporting path along with the thing it reports.
///
/// This lives in ONE place and every health field routes through it. A second copy of a rule
/// this fiddly is a copy that will be got wrong: the first version of its test was itself
/// vacuous, because a 2-byte character against a 200-byte cap always lands on a boundary.
pub fn truncate_for_wire(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    s[..end].to_string()
}

/// The host's storage headroom for autosave/checkpoint writes (`guard::DiskStatus`).
///
/// The operator previously received only a raw `disk_free` byte count and had to invent the
/// thresholds, so the host's own verdict — the one that actually decides whether checkpoint
/// writes continue — never reached the UI.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorageHealthView {
    /// `"ok"` | `"low"` | `"critical"` | `"unknown"`.
    ///
    /// `"unknown"` is a real, distinct outcome: the platform can fail to report free space, and
    /// that is neither healthy nor critical. Collapsing it into either would be a fabrication.
    pub status: String,
    /// Free bytes on the volume backing the host's data directory. Absent when the platform
    /// could not report it — never a zero standing in for "do not know".
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub available_bytes: Option<u64>,
    /// Checkpoint writes are halted because free space is below the floor (or unknowable while
    /// already halted). The audience output is unaffected; only persistence stops.
    #[serde(default, skip_serializing_if = "is_false")]
    pub checkpoints_paused: bool,
}

/// The host's session-recovery state (`guard.rs` + `session_repo.rs`), previously reported by
/// `eprintln!` only and therefore invisible to the operator running the service.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionHealthView {
    /// A persisted session was restored at launch (crash/restart recovery).
    #[serde(default, skip_serializing_if = "is_false")]
    pub restored: bool,
    /// The crash-loop breaker tripped, so this launch started CLEAN.
    ///
    /// The persisted session is *skipped, never deleted* — a later healthy launch can still
    /// resume it deliberately. The UI must say so, because "started clean" reads as data loss
    /// otherwise.
    #[serde(default, skip_serializing_if = "is_false")]
    pub crash_loop: bool,
    /// Unstable launches counted inside the breaker window, when it tripped.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rapid_launches: Option<u32>,
    /// The most recent autosave failure. Absent when the last attempt succeeded, so a recovered
    /// autosave never keeps displaying an old failure. Bounded via [`truncate_for_wire`].
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub autosave_error: Option<String>,
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
    /// Short code of the translation the verse `text` is in (e.g. `"KJV"`, `"WEB"`), so the
    /// operator sees WHICH translation the snippet is. Omitted when `text` is (honest-empty on an
    /// older host or an unresolved reference); additive, so the pinned fixtures stay byte-stable.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub translation: String,
    /// The transcript segment id this reference was heard in (provenance) — the UI resolves it to
    /// the spoken phrase + "spoken Ns ago". `None` on an older host; additive + skipped when absent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_segment: Option<u64>,
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
