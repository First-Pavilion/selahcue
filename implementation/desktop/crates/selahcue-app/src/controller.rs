//! The live controller: maps RBAC-checked control commands onto the presenter and
//! service plan, so a remote controller drives the audience output.
//!
//! Preview/live separation is preserved (FR-012): navigation (`Next`/`Previous`/
//! `SelectItem`) stages the item in **Preview**; only `GoLive` commits it to the
//! **Live** output. `Clear`/`Blackout` act on Live.

use crate::operator::{ItemView, OperatorView};
use selahcue_core::detection::TranscriptEngine;
use selahcue_core::plan::{ItemId, ServicePlan};
use selahcue_core::scripture;
use selahcue_core::timer::Timer;
use selahcue_lan::protocol::{
    Command, ContentLinkView, DenyReason, DetectionView, DisplayView, ImportItemView,
    OutputConfigView, OutputHealthView, OutputStatusView, PlanSummaryView, PlanTemplateView,
    PublishStateView, SavedThemeView, ScaleFit, ScreenThemeView, ScreenView, ServerMessage,
    SessionHealthView, StorageHealthView, ThumbView, TimerSnapshot, TranscriptSegmentView,
    VerseView, MAX_FRAME_RATE, MAX_NDI_NAME_LEN, MAX_OUTPUT_DELAY_MS, MIN_FRAME_RATE,
};
use selahcue_present::{
    AuthoredSlide, FrameBuffer, LayerMask, Presenter, Slide, StageDisplay, StageTheme, Theme,
    TimerView, WallClock,
};
use std::time::{Duration, Instant};

/// Seconds-remaining threshold at which the countdown enters its amber "warning" state.
const TIMER_WARN_SECS: u32 = 30;

/// The displayed value of a timer view (whole-second granularity + state) — used to gate
/// confidence-monitor recomposition to ~1/sec rather than every frame.
type TimerKey = Option<(Option<u32>, u32, bool, bool)>;
fn timer_key(view: Option<TimerView>) -> TimerKey {
    view.map(|v| (v.remaining_secs, v.elapsed_secs, v.time_up, v.warn))
}

/// The controller's decision for a command. The transport frames `Ack`/`Deny` with
/// the request id; `Message` is returned as-is.
#[derive(Debug, Clone, PartialEq, Eq)]
// One short-lived value per command application (never stored in collections),
// so the size skew from the operator view inside `Message` is harmless — boxing
// here would only push the cost into every test's pattern match.
#[allow(clippy::large_enum_variant)]
pub enum ControllerReply {
    Ack,
    Deny(DenyReason),
    Message(ServerMessage),
}

/// A persistable snapshot of the live session (crash recovery). Pure data — the
/// desktop maps it to/from the persistence layer; the controller stays storage-free.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct ControllerSnapshot {
    pub live_idx: Option<u32>,
    pub staged_idx: Option<u32>,
    pub plan_cursor: Option<u32>,
    pub blackout: bool,
    pub timer_total_secs: Option<u32>,
    pub timer_elapsed_secs: Option<u32>,
    pub timer_running: bool,
    /// A scripture reference on the Live output (a non-plan slide), if any.
    pub live_scripture: Option<String>,
    /// A scripture reference staged in Preview, if any.
    pub staged_scripture: Option<String>,
    /// A removed-but-still-on-screen plan item's title (a free slide) — restored
    /// verbatim, never recomposed as scripture.
    pub live_free_text: Option<String>,
    /// The BODY lines of a free live slide (a removed song keeps its lyrics on
    /// screen — S8-1). Newline-joined; None/empty = a title-only free slide.
    pub live_free_body: Option<String>,
    /// Within-item slide position of the LIVE item (songs, story S8-1).
    pub live_slide: Option<u32>,
    /// Within-item slide position of the STAGED item.
    pub staged_slide: Option<u32>,
    /// Slide position paired with `plan_cursor` (survives a scripture
    /// interruption, like the cursor itself).
    pub cursor_slide: Option<u32>,
    /// The active audience-output theme name; `None` = the default ("classic"), so
    /// a default session persists the pre-v8 (NULL) shape (S8-3b).
    pub theme: Option<String>,
    /// The active custom theme (serialized JSON), when one is applied via the Theme
    /// Designer; takes precedence over `theme` on restore. `None` otherwise (S8-3c).
    pub custom_theme: Option<String>,
}

/// Drives the live/preview presentation from a [`ServicePlan`].
pub struct LiveController {
    plan: ServicePlan,
    presenter: Presenter,
    /// The plan item currently in Preview (`None` if Preview holds a non-plan slide
    /// such as a staged scripture, or nothing).
    staged_idx: Option<usize>,
    /// The plan navigation cursor — persists across staging a scripture, so `Next`
    /// resumes from the last plan position rather than snapping to item 0.
    plan_cursor: Option<usize>,
    live_idx: Option<usize>,
    blackout: bool,
    /// The active countdown timer, if any (`StartTimer`/`StopTimer`).
    timer: Option<Timer>,
    /// The countdown target (for the progress fraction).
    timer_total: Option<Duration>,
    /// Set on `StartTimer`; the timer starts on the next [`tick`](Self::tick) so its
    /// start instant is the injected render time, not a wall-clock read in `apply`.
    timer_pending_start: bool,
    /// Set on `PauseTimer`; the timer is banked on the next [`tick`](Self::tick) so the
    /// pause instant is the injected render time (mirrors `timer_pending_start`; `apply`
    /// has no clock — ADR-0015).
    timer_pending_pause: bool,
    /// The countdown is paused (banked, not counting). Surfaced in the operator snapshot
    /// so the UI distinguishes paused from stopped; `running` is `false` while paused.
    timer_paused: bool,
    /// The last timer view computed by `tick`, surfaced in the operator view.
    last_timer_view: Option<TimerView>,
    /// The stage/confidence monitor (a second output surface, FR-037): current + next
    /// line + the timer, composed from the same live state.
    stage: StageDisplay,
    /// Set by any state-changing command so the confidence monitor recomposes next tick.
    stage_dirty: bool,
    /// The timer key the monitor was last composed with (recompose on change).
    last_stage_key: TimerKey,
    /// While pairing mode is active: the invite URI shown as a QR on the stage
    /// output, and when it stops being valid (auto-cleared by `tick`).
    pairing_qr: Option<(String, Instant)>,
    /// Identify-overlay request (armed by the command, started on the next tick).
    identify_pending: bool,
    /// While set (and in the future), every output shows its identify number.
    identify_until: Option<Instant>,
    /// Latest requested display assignment per role (drained by the desktop
    /// shell, which owns the windows). Keyed by role — bounded by role count.
    pending_assignments: Vec<(String, String)>,
    /// Output/display status injected by the desktop shell for the operator view.
    output_status: Vec<OutputStatusView>,
    display_status: Vec<DisplayView>,
    /// Set by any state-changing command; the host's autosave loop consumes it via
    /// [`take_state_dirty`](Self::take_state_dirty).
    state_dirty: bool,
    /// Monotonic LIVE-OUTPUT GENERATION: advanced by every mutation that can change a
    /// composed audience frame ([`compose_screen`](Self::compose_screen)) — the dirty-gate
    /// the desktop's NDI reconcile keys its per-screen frame cache on. Deliberately an
    /// over-approximation (any potentially state-changing command bumps it, plus the
    /// loaders and [`restore`](Self::restore)): a MISSED bump would freeze a stale frame
    /// on the wire, while an extra bump merely costs one recompose.
    live_generation: u64,
    /// Set by plan-edit commands; the host persists the plan when it sees this.
    plan_dirty: bool,
    /// Service-Plan undo history (plan-editing · undo/redo): whole-plan snapshots taken BEFORE
    /// each real plan edit, newest last. `undo_plan` pops here and pushes the current plan onto
    /// `plan_redo`. Bounded by [`MAX_PLAN_UNDO`] (oldest dropped) — no unbounded growth.
    plan_undo: Vec<ServicePlan>,
    /// The redo counterpart of [`plan_undo`](Self::plan_undo): plans peeled off by `undo_plan`,
    /// replayed by `redo_plan`. Cleared whenever a fresh plan edit is recorded (a new edit
    /// invalidates the redo branch). Bounded by [`MAX_PLAN_UNDO`].
    plan_redo: Vec<ServicePlan>,
    /// Monotonic revision of the plan DOCUMENT (FR-006 publish / hand-off). Bumped exactly
    /// where an undo snapshot is recorded — that block is already this file's single
    /// definition of "a plan edit really happened and really changed the plan", and deriving
    /// the revision anywhere else would let the badge and the undo history disagree about
    /// whether the plan moved. Also bumped by undo and redo, which move it too.
    ///
    /// Saturating: a `u64` of plan edits is unreachable, but wrapping to zero would silently
    /// re-equal a published baseline and hide a real change.
    plan_revision: u64,
    /// The [`plan_revision`](Self::plan_revision) captured by the last `PublishPlan`.
    /// `None` = never published, i.e. the plan is a draft.
    published_revision: Option<u64>,
    /// The plan DOCUMENT exactly as it was at the last publish — the baseline the change badge
    /// compares against. `None` = never published.
    ///
    /// A whole clone, deliberately, so that "has the plan changed since publish" is answered by
    /// comparing documents rather than by comparing revision counters. A counter cannot tell
    /// "edited" from "edited and undone": undo moves the revision but restores the content, and
    /// a counter would leave the operator staring at a "Plan updated · Review changes" badge
    /// over a plan identical to the one they published, with nothing to review.
    ///
    /// The cost is one plan-sized clone against the [`MAX_PLAN_UNDO`] (60) that `plan_undo`
    /// already holds — a 1/60 increase on an accepted bound, itself capped because the plan is
    /// capped at `MAX_PLAN_ITEMS`.
    published_plan: Option<ServicePlan>,
    /// Whether the plan differs from [`published_plan`](Self::published_plan) right now.
    ///
    /// Recomputed when the document MOVES and when it is published — never while building a
    /// view. The comparison is O(plan) and view building is per-frame, so deriving it on read
    /// would put a deep compare of every item into the render path to answer a question that
    /// can only change when someone edits.
    changed_since_publish: bool,
    /// How many times this plan has been published — the `v4 (published)` label. Saturating.
    publish_count: u32,
    /// The scripture reference staged in Preview, if Preview holds one (non-plan slide).
    staged_scripture: Option<String>,
    /// The scripture reference on the Live output, if Live shows one (verse text
    /// recomposes from the bundled translation on restore).
    live_scripture: Option<String>,
    /// The title of a removed-but-still-on-screen plan item (a free slide) —
    /// restored VERBATIM as a title-only slide, never recomposed as scripture
    /// even when the title happens to parse as a reference (review 7y-B).
    live_free_text: Option<String>,
    /// The body lines of a free live slide (a removed song's lyrics stay on
    /// screen and must recover verbatim, not as a bare title — S8-1 review fix).
    live_free_body: Vec<String>,
    /// Within-item slide position of the staged item (0 for title-only items).
    staged_slide: usize,
    /// Within-item slide position of the live item.
    live_slide: usize,
    /// Slide position paired with `plan_cursor` — like the cursor, it survives
    /// staging a scripture so `Next` resumes mid-song, not at stanza 0.
    cursor_slide: usize,
    /// The active audience-output theme name (a built-in; persisted + reported in
    /// the operator view). Switching it restyles both outputs without losing content.
    /// `"custom"` when a Theme-Designer theme is active (see `custom_theme_json`).
    theme_name: String,
    /// The active CUSTOM theme (serialized JSON), when `theme_name == "custom"`
    /// (Theme Designer, S8-3c). Persisted verbatim so recovery restores the exact
    /// custom design; `None` when a built-in theme is active.
    custom_theme_json: Option<String>,
    /// The saved-theme LIBRARY (S8-3d follow-up 86ajq4xmy): NAMED custom themes the
    /// operator authored + saved, `name → canonical theme JSON`. Persisted separately
    /// from the live session (like the plan), so `saved_themes_dirty` signals the host
    /// to write it. Bounded by [`MAX_SAVED_THEMES`] + [`MAX_THEME_NAME_LEN`].
    saved_themes: std::collections::BTreeMap<String, String>,
    saved_themes_dirty: bool,
    /// The per-SCREEN theme map (86ajq321k): `audience screen id → theme NAME` (a built-in
    /// or a saved-library name). An absent screen follows the per-item override / global.
    /// `main`'s entry drives the physical audience output (via the Presenter); secondary
    /// screens (`lower-third`/`stream`) are composed on-demand ([`Self::compose_screen`]).
    /// Bounded to [`AUDIENCE_SCREENS`]. Persisted separately (like `saved_themes`).
    screen_themes: std::collections::BTreeMap<String, String>,
    screen_themes_dirty: bool,
    /// The SCREEN REGISTRY (Screens page — dynamic registry): every managed screen
    /// (built-in + virtual) with its role, enable state, and deletability. Supersedes the
    /// fixed [`AUDIENCE_SCREENS`] set — a disabled screen composes safe-black, a virtual
    /// screen can be added/deleted. Bounded by [`MAX_SCREENS`]. Persisted separately (like
    /// `screen_themes`); `screen_themes`' keys stay a subset of the registry's ids.
    screen_registry: ScreenRegistry,
    screen_registry_dirty: bool,
    /// Per-SCREEN OUTPUT CONFIG (Screens page inspector): `screen id → OutputConfigView`
    /// (orientation, scaling/fit, mirror, output delay, frame-rate target, safe-area guides,
    /// per-layer visibility). A screen with no entry uses [`OutputConfigView::default`] (all
    /// identity), so only a configured screen occupies the map — bounded by the registry
    /// ([`MAX_SCREENS`], no-leak). Persisted separately (like `screen_themes`); keys stay a
    /// subset of the registry's ids (dropped when a virtual screen is removed).
    output_configs: std::collections::BTreeMap<String, OutputConfigView>,
    output_configs_dirty: bool,
    /// The live-transcript + scripture-detection engine (R3/R4; ADR-0010). Runs
    /// out-of-band from the render/output path — it is fed transcript segments and
    /// surfaces bounded transcript + a detection approval queue in the operator view,
    /// but never blocks or blanks Live (FR-083). In-memory only this slice (encrypted
    /// persistence + retention is a documented follow-up seam).
    transcript: TranscriptEngine,
    /// The host's storage headroom for autosave, as last reported by the host
    /// ([`set_storage_health`](Self::set_storage_health)). `None` until the host reports —
    /// which a client must render as *unknown*, never as healthy.
    storage_health: Option<StorageHealthView>,
    /// The host's session-recovery state ([`set_session_health`](Self::set_session_health)).
    /// `None` until the host reports.
    session_health: Option<SessionHealthView>,
    /// A tiny rolling window of the most recent transcript segments, joined and fed to the
    /// fuzzy quote matcher — so a paraphrase spoken across an utterance boundary ("…and
    /// strangers shall" / "feed your flock") is still matched, not just single-segment quotes.
    /// Bounded to [`QUOTE_WINDOW_SEGMENTS`] (no-leak).
    recent_texts: std::collections::VecDeque<String>,
    /// The current streaming INTERIM transcript line (recognised words for the utterance still
    /// being spoken). Shown live below the finalised transcript; replaced by each interim and
    /// cleared when the utterance finalises. Not logged and not run through detection.
    partial: Option<String>,
}

/// How many recent transcript segments the fuzzy quote matcher looks back over, so a
/// paraphrase split across utterances still resolves. Small + bounded.
const QUOTE_WINDOW_SEGMENTS: usize = 3;

/// How many recent transcript segments the operator view carries (a bounded tail of the
/// already-capped log — keeps the view payload small on the 1 s poll).
pub const OPERATOR_TRANSCRIPT_TAIL: usize = 60;

/// Upper bounds on the saved-theme library so it cannot grow without limit (no-leak):
/// a sane cap on the count and each name's length. Each theme's JSON is the canonical
/// fixed-size [`Theme`] (a few hundred bytes), so total storage is bounded.
pub const MAX_SAVED_THEMES: usize = 256;
pub const MAX_THEME_NAME_LEN: usize = 64;

/// The BUILT-IN Audience-class screen(s) that carry their own per-screen theme (86ajq321k):
/// just the physical `main` projector by default. Secondary Audience feeds (lower-third /
/// stream) are added on demand and also carry per-screen themes, but they are not default
/// outputs; the `stage` confidence monitor is NOT audience-class (it renders a stage layout,
/// not a theme). The per-screen theme map is bounded by the registry ([`MAX_SCREENS`]).
pub const AUDIENCE_SCREENS: [&str; 1] = ["main"];

/// The hard cap on the number of screens in the registry (no-leak): the built-ins plus
/// any virtual screens the operator adds. Small — a church stage has a handful of outputs
/// — so `AddScreen` cannot grow the registry without limit (the exact reason
/// [`AUDIENCE_SCREENS`] was a fixed const before the registry). At most **8** outputs: the
/// two physical built-ins (`main` + `stage`) plus up to six virtual audience feeds.
pub const MAX_SCREENS: usize = 8;

/// The hard cap on the Service-Plan undo/redo history depth (no-leak · plan-editing · undo/redo).
/// Each entry is a whole [`ServicePlan`] snapshot, so the stack cannot grow without limit — the
/// oldest entry is dropped once a push would exceed this. Mirrors the deck workspace's `MAX_UNDO`.
const MAX_PLAN_UNDO: usize = 60;

/// A screen's role in the registry (Screens page — dynamic registry). Audience-class
/// roles (`Main`/`LowerThird`/`Stream`) render the live content under a per-screen theme
/// ([`LiveController::compose_screen`]); `Stage` is the confidence monitor (a stage
/// layout, not a theme).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScreenRole {
    Main,
    LowerThird,
    Stream,
    Stage,
}

impl ScreenRole {
    /// The stable wire/persist tag.
    pub fn as_tag(self) -> &'static str {
        match self {
            ScreenRole::Main => "main",
            ScreenRole::LowerThird => "lower-third",
            ScreenRole::Stream => "stream",
            ScreenRole::Stage => "stage",
        }
    }

    /// Parse a wire/persist tag; `None` for an unknown role (a corrupt persisted row).
    pub fn from_tag(tag: &str) -> Option<ScreenRole> {
        match tag {
            "main" => Some(ScreenRole::Main),
            "lower-third" => Some(ScreenRole::LowerThird),
            "stream" => Some(ScreenRole::Stream),
            "stage" => Some(ScreenRole::Stage),
            _ => None,
        }
    }

    /// Audience-class screens render a themed frame; the stage confidence monitor does not.
    pub fn is_audience(self) -> bool {
        matches!(
            self,
            ScreenRole::Main | ScreenRole::LowerThird | ScreenRole::Stream
        )
    }

    /// Whether a VIRTUAL screen of this role may be added — only the secondary audience
    /// feeds (`main` and `stage` are singleton built-ins).
    pub fn is_addable(self) -> bool {
        matches!(self, ScreenRole::LowerThird | ScreenRole::Stream)
    }
}

/// One entry in the [`ScreenRegistry`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Screen {
    pub id: String,
    pub role: ScreenRole,
    pub enabled: bool,
    /// True only for virtual screens the operator added — a built-in may be DISABLED but
    /// never DELETED.
    pub deletable: bool,
}

/// Why [`ScreenRegistry::add_virtual`] refused.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AddScreenError {
    /// The role is not addable (only the `lower-third`/`stream` secondary feeds).
    BadRole,
    /// The registry is already at [`MAX_SCREENS`].
    Full,
}

/// The outcome of [`ScreenRegistry::remove`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RemoveOutcome {
    /// The screen was removed.
    Removed,
    /// The id names a built-in — never deletable (a caller maps this to a denial).
    NotDeletable,
    /// No screen with that id (an idempotent delete — a caller acks).
    Absent,
}

/// A bounded, deterministically-ordered registry of managed screens (Screens page —
/// dynamic registry). Built-ins (`main`/`lower-third`/`stream`/`stage`) are seeded first
/// and never deletable; virtual audience screens append in add order. Bounded by
/// [`MAX_SCREENS`] (no-leak). A `Vec` (not a `HashMap`) so iteration / compose / preview
/// order is stable and reproducible (determinism).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScreenRegistry {
    screens: Vec<Screen>,
}

impl Default for ScreenRegistry {
    fn default() -> Self {
        Self::with_builtins()
    }
}

impl ScreenRegistry {
    /// The default registry: the four built-in screens, all enabled, none deletable.
    pub fn with_builtins() -> Self {
        // Only the two PHYSICAL outputs are built in: the Audience (`main`) projector and the
        // Stage Display (`stage`) confidence monitor. Secondary Audience feeds (lower-third /
        // stream, e.g. an NDI output) are NOT default outputs — the operator adds them on demand
        // via "+ Add virtual output" ([`ScreenRegistry::add_virtual`]).
        Self {
            screens: vec![
                Screen {
                    id: "main".into(),
                    role: ScreenRole::Main,
                    enabled: true,
                    deletable: false,
                },
                Screen {
                    id: "stage".into(),
                    role: ScreenRole::Stage,
                    enabled: true,
                    deletable: false,
                },
            ],
        }
    }

    /// Rebuild a registry from persisted rows `(id, role_tag, enabled, deletable)`,
    /// RECOVERING robustly: always start from the built-in default (so the four built-ins
    /// are never lost), apply each built-in's persisted `enabled` flag, and append only
    /// valid VIRTUAL rows (a deletable, addable-role, non-duplicate id) up to
    /// [`MAX_SCREENS`]. A corrupt row (unknown role) or an over-cap row is dropped, never
    /// a crash — so a tampered/oversized store degrades to a sane registry.
    pub fn from_persisted<I>(rows: I) -> Self
    where
        I: IntoIterator<Item = (String, String, bool, bool)>,
    {
        let mut reg = Self::with_builtins();
        for (id, role_tag, enabled, deletable) in rows {
            let Some(role) = ScreenRole::from_tag(&role_tag) else {
                continue; // corrupt role — drop
            };
            if let Some(existing) = reg.screens.iter_mut().find(|s| s.id == id) {
                // A built-in (or an already-restored id): restore its enable state only —
                // never flip a built-in's role/deletable.
                existing.enabled = enabled;
                continue;
            }
            // A virtual screen: only a deletable, addable-role entry, within the cap.
            if deletable && role.is_addable() && reg.screens.len() < MAX_SCREENS {
                reg.screens.push(Screen {
                    id,
                    role,
                    enabled,
                    deletable: true,
                });
            }
        }
        reg
    }

    /// Deterministic iteration order (built-ins first, then virtuals in add order).
    pub fn iter(&self) -> impl Iterator<Item = &Screen> {
        self.screens.iter()
    }

    pub fn len(&self) -> usize {
        self.screens.len()
    }

    pub fn is_empty(&self) -> bool {
        self.screens.is_empty()
    }

    pub fn get(&self, id: &str) -> Option<&Screen> {
        self.screens.iter().find(|s| s.id == id)
    }

    /// Whether the screen `id` is enabled. An UNKNOWN id defaults to `true`: a caller
    /// gating a physical window must not black it merely because the registry lacks the
    /// row (e.g. an older persisted registry) — only an explicit `enabled = false` mutes.
    pub fn is_enabled(&self, id: &str) -> bool {
        self.get(id).map(|s| s.enabled).unwrap_or(true)
    }

    /// Set a screen's enabled flag. Returns `true` if the id existed.
    pub fn set_enabled(&mut self, id: &str, enabled: bool) -> bool {
        match self.screens.iter_mut().find(|s| s.id == id) {
            Some(s) => {
                s.enabled = enabled;
                true
            }
            None => false,
        }
    }

    /// Add a virtual screen of `role`, minting a stable id: the bare role tag (`stream`,
    /// `lower-third`) when free, else `role-N` for the smallest `N >= 2` whose id is free —
    /// deterministic. (These roles are no longer default outputs, so the first one added takes
    /// the plain name.) `Err` if the role is not addable or the cap is reached.
    pub fn add_virtual(&mut self, role: ScreenRole) -> Result<String, AddScreenError> {
        if !role.is_addable() {
            return Err(AddScreenError::BadRole);
        }
        if self.screens.len() >= MAX_SCREENS {
            return Err(AddScreenError::Full);
        }
        let base = role.as_tag();
        // Try the bare role name first, then role-2, role-3, … until one is free.
        let candidates =
            std::iter::once(base.to_string()).chain((2usize..).map(|n| format!("{base}-{n}")));
        for candidate in candidates {
            if self.get(&candidate).is_none() {
                self.screens.push(Screen {
                    id: candidate.clone(),
                    role,
                    enabled: true,
                    deletable: true,
                });
                return Ok(candidate);
            }
        }
        unreachable!("the candidate stream is infinite, so a free id always exists")
    }

    /// Remove a screen by id — only a deletable (virtual) screen. A built-in yields
    /// [`RemoveOutcome::NotDeletable`]; an absent id yields [`RemoveOutcome::Absent`].
    pub fn remove(&mut self, id: &str) -> RemoveOutcome {
        match self.screens.iter().position(|s| s.id == id) {
            Some(i) if self.screens[i].deletable => {
                self.screens.remove(i);
                RemoveOutcome::Removed
            }
            Some(_) => RemoveOutcome::NotDeletable,
            None => RemoveOutcome::Absent,
        }
    }
}

/// Resolve a theme NAME to a `Theme`: a built-in (classic/high-contrast/lower-third)
/// first, else a SAVED-library name (its canonical JSON). `None` for an unknown name
/// (86ajq69ft). A **free** fn (takes the library map, not `&self`) so a caller can
/// re-resolve overrides while holding a mutable borrow of another controller field
/// (the plan, the per-screen map) — avoiding a partial-borrow conflict on `self`.
fn resolve_theme_name(
    name: &str,
    saved: &std::collections::BTreeMap<String, String>,
) -> Option<Theme> {
    Theme::builtin(name).or_else(|| {
        saved
            .get(name)
            .and_then(|json| serde_json::from_str::<Theme>(json).ok())
    })
}

/// The compose-time [`LayerMask`] for an output config (Design 2.0 VISIBLE LAYERS). Maps the
/// four AUDIENCE-compositing layers (background/text/lower-third/logo); the `timer` layer is
/// composed only on the stage/confidence monitor, not by this audience mask.
fn to_layer_mask(cfg: &OutputConfigView) -> LayerMask {
    LayerMask {
        background: cfg.layers.background,
        text: cfg.layers.text,
        lower_third: cfg.layers.lower_third,
        logo: cfg.layers.logo,
    }
}

/// Whether an NDI source name is acceptable: bounded ([`MAX_NDI_NAME_LEN`] chars) and printable
/// (no control chars). Emptiness is checked separately — an empty name is fine when NDI is off.
/// Shared by the command path ([`LiveController::set_ndi_output`]) and the defensive load path.
fn ndi_name_valid(name: &str) -> bool {
    name.chars().count() <= MAX_NDI_NAME_LEN && !name.chars().any(|c| c.is_control())
}

/// How long the identify overlay stays on the outputs once triggered (FR-040).
pub const IDENTIFY_TTL: Duration = Duration::from_secs(5);

/// Compose the slide for a scripture reference: the parsed reference as the
/// title and the bundled translation's verse text as wrapped body lines
/// (FR-025/story 86ajpew05). Falls back to a title-only slide when the text is
/// not a resolvable reference (e.g. the free-slide recovery path).
fn scripture_slide(reference: &str) -> Slide {
    scripture_slide_in(selahcue_scripture::Translation::default(), reference)
}

/// Narrow a WHOLE-CHAPTER reference (e.g. a spoken "Isaiah 61" — no verse) to just its first
/// verse for Preview/Live, so a chapter detection stages a single readable verse rather than a
/// wall of the whole chapter on one slide. A reference that already names a verse (or doesn't
/// parse) is returned unchanged. `Reference`'s Display is `"Book Chapter"` for a whole chapter,
/// so appending `":1"` reparses cleanly to the first verse.
fn stage_reference_for_detection(reference: &str) -> String {
    match scripture::parse_one(reference) {
        Ok(r) if r.verses.is_none() => format!("{r}:1"),
        _ => reference.to_string(),
    }
}

/// The wire view of a plan item's linked content (ADR-0020 follow-up), so the
/// operator UI shows link status. Pure mapping of `ItemContent`.
/// Project the compositor's health record onto the wire view.
///
/// `fault` is carried as a stable snake_case string rather than a shared enum because
/// `selahcue-lan` is the control plane and must not depend on the presentation crate —
/// the same boundary that keeps `theme_json` opaque to the wire. The tag mapping itself
/// lives in `selahcue-present::fault_tag`, so the operator-facing strings are pinned by
/// that crate's tests.
///
/// A recovered output never names a stale reason, because `OutputHealth` itself clears the
/// fault on recovery — that invariant is enforced and mutation-tested at its single source
/// (`selahcue-present`, `output_health_never_names_a_reason_when_not_held`). This mapper
/// deliberately does NOT re-check it: a second copy of an invariant, in a place no test can
/// reach, is a control that guards nothing, which is the exact defect class this seam was
/// built to remove.
fn output_health_view(h: selahcue_present::OutputHealth) -> OutputHealthView {
    OutputHealthView {
        held: h.held,
        fault: h.fault.map(selahcue_present::fault_tag).map(str::to_string),
        holds: h.holds,
        recoveries: h.recoveries,
    }
}

/// Whether a link resolves **from this host's point of view**.
///
/// The host can always answer for scripture, because resolving it is a pure parse. It can
/// never answer for a deck or a media asset: both libraries are operator-owned by design and
/// this process has no store for either, so it reports
/// [`Unknown`](selahcue_core::plan::LinkResolution::Unknown) rather than guessing. Reporting
/// `Resolved` there would be a fabrication, and reporting `Missing` would flag every healthy
/// deck in the plan.
fn host_resolution(c: &selahcue_core::plan::ItemContent) -> selahcue_core::plan::LinkResolution {
    c.resolve(
        // The host DOES own the bundled scripture corpus, so it answers this one for real — and
        // with the SAME lookup the renderer uses, so "resolved" means "will actually present
        // verses", not merely "the reference is well-formed". Parsing alone accepts "Jude 2:1"
        // and "Romans 99:1", which present nothing.
        |reference, translation| {
            // `resolve` only consults this probe once the reference has parsed, so this cannot
            // fail in practice; `None` (= Unknown) is the honest answer if that ever changes,
            // rather than claiming the passage is missing.
            let parsed = selahcue_core::scripture::parse_one(reference).ok()?;
            let t = translation
                .and_then(selahcue_scripture::Translation::from_code)
                .unwrap_or_default();
            Some(!selahcue_scripture::verses_in(t, &parsed).is_empty())
        },
        // Decks and media are operator-owned and this process has no store for either, so it
        // declines rather than guessing.
        |_| None,
        |_| None,
    )
}

/// Map a domain link to its wire form. `resolution` is supplied by the caller because the
/// answer depends on WHICH layer is asking — the host cannot see the deck library, an
/// operator-side caller can.
fn content_link_view(
    c: &selahcue_core::plan::ItemContent,
    resolution: selahcue_core::plan::LinkResolution,
) -> ContentLinkView {
    use selahcue_core::plan::{ItemContent, LinkResolution};
    // `Resolved` is the absent case on the wire, so a healthy link stays byte-identical to a
    // pre-status host's frame.
    let status = (resolution != LinkResolution::Resolved).then(|| resolution.as_tag().to_string());
    match c {
        ItemContent::Scripture {
            reference,
            translation,
            verses_per_slide,
            verse_numbers,
        } => ContentLinkView {
            kind: "scripture".to_string(),
            reference: Some(reference.clone()),
            translation: translation.clone(),
            verses_per_slide: *verses_per_slide,
            id: None,
            slide_count: None,
            verse_numbers: verse_numbers.map(|n| n.as_tag().to_string()),
            status,
            label: None,
        },
        ItemContent::Deck {
            deck_id,
            slide_count,
            label,
        } => ContentLinkView {
            kind: "deck".to_string(),
            reference: None,
            translation: None,
            verses_per_slide: None,
            id: Some(*deck_id),
            slide_count: *slide_count,
            verse_numbers: None,
            status,
            label: label.clone(),
        },
        ItemContent::Media { media_id } => ContentLinkView {
            kind: "media".to_string(),
            reference: None,
            translation: None,
            verses_per_slide: None,
            id: Some(*media_id),
            slide_count: None,
            verse_numbers: None,
            status,
            label: None,
        },
    }
}

/// Parse a wire [`ContentLinkView`] into a domain `ItemContent`, or `None` if it is
/// malformed — an unknown `kind`, a blank/absent scripture reference, or a missing
/// deck/media id. The `SetItemContent` handler rejects a `None` here (the plan is
/// left unchanged).
fn item_content_from_link(link: &ContentLinkView) -> Option<selahcue_core::plan::ItemContent> {
    use selahcue_core::plan::ItemContent;
    match link.kind.as_str() {
        "scripture" => {
            // Clean BEFORE the parse check in `set_item_content`, so the reference that is
            // validated is byte-for-byte the one that gets stored. Sanitizing afterwards could
            // change a string that had already been accepted.
            let reference = selahcue_core::plan::sanitize_text(&link.reference.clone()?);
            if reference.trim().is_empty() {
                return None;
            }
            Some(ItemContent::Scripture {
                reference,
                translation: link.translation.clone(),
                verses_per_slide: link.verses_per_slide,
                // An unrecognised mode degrades to the plan default rather than rejecting the
                // link — the passage still displays, which is the point of the link.
                verse_numbers: link
                    .verse_numbers
                    .as_deref()
                    .and_then(selahcue_core::plan::VerseNumbers::from_tag),
            })
        }
        "deck" => Some(ItemContent::Deck {
            deck_id: link.id?,
            slide_count: link.slide_count,
            // The caller supplies the deck's name; the domain bounds its length. Sending the
            // link again with a fresh label is how a rename is recorded — no extra command.
            label: link.label.clone(),
        }),
        "media" => Some(ItemContent::Media { media_id: link.id? }),
        _ => None,
    }
}

/// Compose the slide for one within-item position (story S8-1). A **scripture-linked**
/// item (ADR-0020 follow-up) renders its passage from the linked reference/translation,
/// not its title. A title-only item (no stanzas, no link) is its single title slide —
/// the exact pre-8a shape. A song stanza renders as the item title plus the stanza's
/// wrapped lines, capped by the same physical budget as scripture slides (verses-per-slide
/// pagination is a later slice). A deck/media link falls through to the title slide here —
/// deck slides are composed by the presenting layer (which holds the deck library).
fn item_slide(item: &selahcue_core::plan::PlanItem, slide: usize) -> Slide {
    if let Some(selahcue_core::plan::ItemContent::Scripture {
        reference,
        translation,
        ..
    }) = &item.content
    {
        let t = translation
            .as_deref()
            .and_then(selahcue_scripture::Translation::from_code)
            .unwrap_or_default();
        return scripture_slide_in(t, reference);
    }
    if item.stanzas.is_empty() {
        return Slide::title(item.title.clone());
    }
    let idx = slide.min(item.stanzas.len() - 1);
    // Pass the stanza's lines VERBATIM as paragraphs — the compositor word-wraps each
    // to the region width and auto-sizes so the whole stanza fits (zero content loss).
    let lines: Vec<String> = item.stanzas[idx].lines.clone();
    Slide::new(item.title.clone(), lines)
}

/// Compose the scripture slide from a specific bundled translation. Recovery
/// paths use the default (KJV): the chosen translation is session state, not
/// yet persisted (documented gap; the reference itself recovers faithfully).
fn scripture_slide_in(t: selahcue_scripture::Translation, reference: &str) -> Slide {
    let Ok(parsed) = selahcue_core::scripture::parse_one(reference) else {
        return Slide::title(reference);
    };
    let verses = selahcue_scripture::verses_in(t, &parsed);
    if verses.is_empty() {
        return Slide::title(reference);
    }
    let multi = verses.len() > 1;
    // Each verse is one PARAGRAPH — the full text, never truncated. The compositor
    // word-wraps it to the region width and auto-sizes the font so the WHOLE passage
    // fits + fills the box (zero content loss, FR-010 — no more "…" on long verses).
    let lines: Vec<String> = verses
        .iter()
        .map(|v| {
            if multi {
                format!("{} {}", v.verse, v.text)
            } else {
                v.text.clone()
            }
        })
        .collect();
    Slide::new(format!("{parsed} ({})", t.code()), lines)
}

impl LiveController {
    /// A controller for `plan`, rendering at `width×height` with `theme`. Both
    /// surfaces start blank.
    pub fn new(plan: ServicePlan, width: u32, height: u32, theme: Theme) -> Self {
        // Report the theme by its built-in name; an off-registry theme (only test
        // code builds one) falls back to "classic" for the picker's selection.
        let theme_name = theme.name_of().unwrap_or("classic").to_string();
        LiveController {
            plan,
            presenter: Presenter::new(width, height, theme),
            staged_idx: None,
            plan_cursor: None,
            live_idx: None,
            blackout: false,
            timer: None,
            timer_total: None,
            timer_pending_start: false,
            timer_pending_pause: false,
            timer_paused: false,
            last_timer_view: None,
            stage: StageDisplay::new(width, height, StageTheme::dark()),
            stage_dirty: true,
            last_stage_key: None,
            pairing_qr: None,
            identify_pending: false,
            identify_until: None,
            pending_assignments: Vec::new(),
            output_status: Vec::new(),
            display_status: Vec::new(),
            state_dirty: false,
            live_generation: 0,
            plan_dirty: false,
            plan_undo: Vec::new(),
            plan_redo: Vec::new(),
            plan_revision: 0,
            published_revision: None,
            published_plan: None,
            changed_since_publish: false,
            publish_count: 0,
            staged_scripture: None,
            live_scripture: None,
            live_free_text: None,
            live_free_body: Vec::new(),
            staged_slide: 0,
            live_slide: 0,
            cursor_slide: 0,
            theme_name,
            custom_theme_json: None,
            saved_themes: std::collections::BTreeMap::new(),
            saved_themes_dirty: false,
            screen_themes: std::collections::BTreeMap::new(),
            screen_themes_dirty: false,
            screen_registry: ScreenRegistry::with_builtins(),
            screen_registry_dirty: false,
            output_configs: std::collections::BTreeMap::new(),
            output_configs_dirty: false,
            transcript: TranscriptEngine::new(),
            storage_health: None,
            session_health: None,
            recent_texts: std::collections::VecDeque::new(),
            partial: None,
        }
    }

    /// Ingest one live-transcript segment (the STT-provider ingestion path) and run
    /// scripture detection over it. Host-facing: the desktop's transcription provider
    /// pumps segments here directly (out-of-band from render); the same path backs the
    /// `IngestTranscript` wire command. Returns the number of NEW detections queued.
    pub fn ingest_transcript(
        &mut self,
        text: &str,
        start_ms: u64,
        end_ms: u64,
        is_final: bool,
    ) -> usize {
        if !is_final {
            // Streaming interim (R3): show the live in-progress line, but do NOT log it or run
            // detection — a later final for the same utterance supersedes it.
            self.partial = (!text.trim().is_empty()).then(|| text.to_string());
            return 0;
        }
        // Final: the utterance closed, so the interim is superseded.
        self.partial = None;
        // Exact reference detection PLUS the fuzzy quote/paraphrase rung (R4): the corpus
        // matcher lives in selahcue-scripture (the pure core cannot see the corpus), so its
        // most-likely-verse suggestion for a spoken quotation is enqueued alongside exact
        // hits, deduped, for operator confirmation (never auto-live, FR-115).
        // Run the fuzzy matcher over a small rolling window of recent segments (joined), so a
        // paraphrase spoken across an utterance boundary still resolves; the queue's dedup rings
        // suppress the repeats as the window slides. Exact detection stays per-segment (a spoken
        // reference lands in one segment).
        self.recent_texts.push_back(text.to_string());
        while self.recent_texts.len() > QUOTE_WINDOW_SEGMENTS {
            self.recent_texts.pop_front();
        }
        let window = self
            .recent_texts
            .iter()
            .map(String::as_str)
            .collect::<Vec<_>>()
            .join(" ");
        let quotes = selahcue_scripture::match_quote_scored(&window);
        self.transcript
            .ingest_with_quotes(text, start_ms, end_ms, &quotes)
            .len()
    }

    /// The live-transcript + detection engine (read-only), for the desktop host to pump
    /// a [`TranscriptProvider`](selahcue_core::transcript::TranscriptProvider) into.
    pub fn transcript_engine(&self) -> &TranscriptEngine {
        &self.transcript
    }

    /// Switch the audience theme by built-in name, restyling Preview + Live with no
    /// content loss and preserving blackout. Returns `false` for an unknown name.
    /// Selecting a built-in clears any active custom theme.
    fn set_theme(&mut self, name: &str) -> bool {
        let Some(theme) = Theme::builtin(name) else {
            return false;
        };
        self.presenter.set_theme(theme);
        // Re-styling re-issues SetScene on Live; re-apply blackout so a themed
        // switch never un-blacks the audience output (theme ⟂ blackout).
        self.presenter.blackout(self.blackout);
        self.theme_name = name.to_string();
        self.custom_theme_json = None;
        true
    }

    /// Apply a CUSTOM theme from its serialized JSON (Theme Designer, S8-3c),
    /// restyling Preview + Live with no content loss and preserving blackout.
    /// Returns `false` for malformed JSON (the current theme is unchanged).
    fn set_custom_theme(&mut self, theme_json: &str) -> bool {
        let Ok(theme) = serde_json::from_str::<Theme>(theme_json) else {
            return false;
        };
        // Bound the element list (Canvas Editing, 86ajq6j2q) so a hostile/hand-edited
        // theme JSON cannot grow the design without limit (no-leak): the COUNT and each
        // Text box's content length (86ajq6j64).
        if !theme.elements_bounded() {
            return false;
        }
        // Persist the CANONICAL re-serialized theme, not the raw input. `Theme` is a
        // fixed struct of scalars, so this bounds the stored/snapshotted size to a few
        // hundred bytes and strips any ignored or duplicate JSON a client may have
        // padded the (Operator-authorized) payload with — recovery restores the same
        // Theme either way. Falls back to the raw string only if re-serialization fails
        // (it cannot for a value that just deserialized).
        let canonical = serde_json::to_string(&theme).unwrap_or_else(|_| theme_json.to_string());
        self.presenter.set_theme(theme);
        self.presenter.blackout(self.blackout);
        self.theme_name = "custom".to_string();
        self.custom_theme_json = Some(canonical);
        true
    }

    /// Present a Design 2.0 authored deck slide (node 329:124) on the LIVE audience output.
    /// `slide_json`/`theme_json` are a serialized [`AuthoredSlide`] and [`Theme`] (opaque to the
    /// wire — this layer deserializes them, mirroring [`set_custom_theme`](Self::set_custom_theme)).
    /// Rejects (Live unchanged) on malformed JSON, an over-bounds slide (element count / text
    /// length), or an over-bounds theme (no-leak — a hostile/hand-edited payload cannot grow the
    /// design without limit). Returns whether the slide reached the Live output.
    fn present_authored_slide(
        &mut self,
        slide_json: &str,
        theme_json: &str,
        next_slide_json: Option<&str>,
    ) -> bool {
        let Ok(slide) = serde_json::from_str::<AuthoredSlide>(slide_json) else {
            return false;
        };
        if !slide.within_bounds() {
            return false;
        }
        let Ok(theme) = serde_json::from_str::<Theme>(theme_json) else {
            return false;
        };
        if !theme.elements_bounded() {
            return false;
        }
        if !self.presenter.present_authored(&slide, &theme) {
            return false;
        }
        // Best-effort: the COMING deck slide feeds the confidence monitor's "next" (Approach A —
        // the operator supplies it). A malformed / over-bounds next is simply dropped (no next),
        // never failing the present — the current slide is already Live.
        let next = next_slide_json
            .and_then(|j| serde_json::from_str::<AuthoredSlide>(j).ok())
            .filter(AuthoredSlide::within_bounds);
        self.presenter.set_authored_next(next);
        true
    }

    /// Save a NAMED custom theme into the library (S8-3d follow-up 86ajq4xmy). The name
    /// is trimmed + bounded; the JSON must deserialize to a `Theme` (stored CANONICAL,
    /// bounded). Overwriting an existing name is allowed; a NEW name past the cap is
    /// rejected. Rejects an empty/over-long name, invalid JSON, or a **built-in** name.
    fn save_theme(&mut self, name: &str, theme_json: &str) -> ControllerReply {
        let name = name.trim();
        if name.is_empty() || name.len() > MAX_THEME_NAME_LEN {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        // A built-in name is RESERVED: since a saved theme is now applied BY NAME
        // (86ajq69ft) and built-ins resolve first, a saved theme named like a built-in
        // would be silently shadowed + unreachable. Reject it so names stay unambiguous.
        if Theme::builtin(name).is_some() {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let Ok(theme) = serde_json::from_str::<Theme>(theme_json) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        // Bound the element list (Canvas Editing, 86ajq6j2q) — no unbounded design growth
        // (the COUNT + each Text box's content length, 86ajq6j64).
        if !theme.elements_bounded() {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        // A NEW name must fit under the cap; overwriting an existing one always may.
        if !self.saved_themes.contains_key(name) && self.saved_themes.len() >= MAX_SAVED_THEMES {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let canonical = serde_json::to_string(&theme).unwrap_or_else(|_| theme_json.to_string());
        self.saved_themes.insert(name.to_string(), canonical);
        self.saved_themes_dirty = true;
        // An EDIT of a name a plan item / screen references must reach its physical output
        // (and never leave a stale cached theme) — re-sync the overrides (86ajq69ft).
        self.resync_theme_overrides();
        ControllerReply::Ack
    }

    /// Delete a saved theme by name (idempotent — deleting an absent name is a no-op Ack).
    fn delete_theme(&mut self, name: &str) -> ControllerReply {
        if self.saved_themes.remove(name).is_some() {
            self.saved_themes_dirty = true;
            // A DELETE drops any per-item / per-screen reference to the removed theme and
            // falls those outputs back to the global — no stale frame (86ajq69ft).
            self.resync_theme_overrides();
        }
        ControllerReply::Ack
    }

    /// The saved-theme library (`name → canonical JSON`), for the operator view + persist.
    pub fn saved_themes(&self) -> &std::collections::BTreeMap<String, String> {
        &self.saved_themes
    }

    /// Whether the saved-theme library changed since the last check (persist signal).
    pub fn take_saved_themes_dirty(&mut self) -> bool {
        std::mem::take(&mut self.saved_themes_dirty)
    }

    /// Re-arm the saved-theme persist signal (a failed write must be retried).
    pub fn mark_saved_themes_dirty(&mut self) {
        self.saved_themes_dirty = true;
    }

    /// Load the saved-theme library at startup (from the store). Replaces the in-memory
    /// map without marking it dirty (nothing new to persist). Over-cap / invalid entries
    /// are dropped defensively so a corrupt store can never exceed the bound or crash.
    pub fn load_saved_themes(&mut self, themes: impl IntoIterator<Item = (String, String)>) {
        // Can change composed audience output without passing through `apply` — advance
        // the live generation so the NDI frame cache recomposes (dirty-gate, no stale frame).
        self.live_generation = self.live_generation.wrapping_add(1);
        self.saved_themes = themes
            .into_iter()
            .filter(|(name, json)| {
                !name.trim().is_empty()
                    && name.len() <= MAX_THEME_NAME_LEN
                    // Bound the element list too (not just name/count/JSON): the write paths
                    // (set_custom_theme / save_theme) reject over-cap themes, so a corrupt or
                    // version-skewed store row is the one ingress that could otherwise smuggle
                    // an unbounded element Vec straight into compose. Drop it defensively.
                    && serde_json::from_str::<Theme>(json)
                        .map(|t| t.elements_bounded())
                        .unwrap_or(false)
            })
            .take(MAX_SAVED_THEMES)
            .collect();
        self.saved_themes_dirty = false;
    }

    // --- Per-screen theme map (86ajq321k) + saved-theme resolution (86ajq69ft) ------
    //
    // A per-item / per-screen theme is a built-in OR a saved-library name. The Presenter
    // caches the resolved CONCRETE theme, so [`resync_theme_overrides`] re-applies it when
    // the library changes (an edit/delete of a name a screen or plan item references),
    // keeping no cached theme stale.

    /// Resolve a theme name against the built-ins + this controller's saved-theme library.
    fn resolve_theme(&self, name: &str) -> Option<Theme> {
        resolve_theme_name(name, &self.saved_themes)
    }

    /// Re-sync per-item + per-screen theme overrides after the saved-theme LIBRARY changed
    /// (86ajq69ft) — a name a plan item or screen references was edited or deleted. First
    /// DROPS any override whose theme no longer resolves (a deleted theme → that item/screen
    /// falls back to the global), then RE-APPLIES the currently-displayed overrides (the
    /// `main` screen, the LIVE item, and a re-stage of the STAGED item) with freshly-resolved
    /// themes — so an edit reaches the physical output live and a delete never leaves a stale
    /// frame. Idempotent (recomposes to the same bytes when nothing referencing changed).
    fn resync_theme_overrides(&mut self) {
        // 1. Drop plan-item overrides that no longer resolve (deleted theme → global).
        let stale_items: Vec<ItemId> = {
            let saved = &self.saved_themes;
            self.plan
                .items()
                .iter()
                .filter(|it| {
                    it.theme
                        .as_deref()
                        .is_some_and(|n| resolve_theme_name(n, saved).is_none())
                })
                .map(|it| it.id)
                .collect()
        };
        if !stale_items.is_empty() {
            for id in stale_items {
                let _ = self.plan.set_item_theme(id, None);
            }
            self.plan_dirty = true;
        }
        // 2. Drop per-screen entries that no longer resolve.
        let stale_screens: Vec<String> = {
            let saved = &self.saved_themes;
            self.screen_themes
                .iter()
                .filter(|(_, n)| resolve_theme_name(n, saved).is_none())
                .map(|(s, _)| s.clone())
                .collect()
        };
        if !stale_screens.is_empty() {
            for s in &stale_screens {
                self.screen_themes.remove(s);
            }
            self.screen_themes_dirty = true;
        }
        // 3. Re-apply the `main` screen theme (edit → new design; delete → dropped above).
        let main = {
            let saved = &self.saved_themes;
            self.screen_themes
                .get("main")
                .and_then(|n| resolve_theme_name(n, saved))
        };
        self.presenter.set_main_screen_theme(main);
        // 4. Re-apply the LIVE item's override (edit reaches the live output; delete → global).
        if let Some(idx) = self.live_idx {
            let live = {
                let saved = &self.saved_themes;
                self.plan.items()[idx]
                    .theme
                    .as_deref()
                    .and_then(|n| resolve_theme_name(n, saved))
            };
            self.presenter.set_live_theme(live);
        }
        // 5. Re-stage the STAGED item so Preview reflects the change too.
        if let Some(idx) = self.staged_idx {
            self.stage_slide(idx, self.staged_slide);
        }
        // Theme ⟂ blackout — a recompose re-issues SetScene, so re-assert blackout.
        self.presenter.blackout(self.blackout);
    }

    /// Set (or clear, with an empty `name`) an Audience-class screen's own theme
    /// (86ajq321k). The `main` screen drives the physical audience output via the
    /// Presenter (recomposed on its effective theme, blackout preserved); secondary
    /// screens (`lower-third`/`stream`) are stored + composed on-demand. Rejects an
    /// unknown screen or an unknown theme name (`BadRequest`).
    ///
    /// The name may be a built-in OR a saved-library theme (86ajq69ft). A saved theme's
    /// cached copy on the physical `main` output is kept fresh by [`resync_theme_overrides`]
    /// when the library changes.
    fn set_screen_theme(&mut self, screen: &str, name: &str) -> ControllerReply {
        // A theme applies to any Audience-class screen in the registry (a built-in OR a
        // virtual feed) — never the stage confidence monitor or an unknown id.
        if !self
            .screen_registry
            .get(screen)
            .is_some_and(|s| s.role.is_audience())
        {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        if name.is_empty() {
            // Clear the screen's override — it falls back to the per-item / global theme.
            if self.screen_themes.remove(screen).is_some() {
                self.screen_themes_dirty = true;
            }
            if screen == "main" {
                self.presenter.set_main_screen_theme(None);
                self.presenter.blackout(self.blackout);
            }
            return ControllerReply::Ack;
        }
        let Some(theme) = self.resolve_theme(name) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        self.screen_themes
            .insert(screen.to_string(), name.to_string());
        self.screen_themes_dirty = true;
        if screen == "main" {
            self.presenter.set_main_screen_theme(Some(theme));
            // Re-styling re-issues SetScene on Live; re-apply blackout (theme ⟂ blackout).
            self.presenter.blackout(self.blackout);
        }
        ControllerReply::Ack
    }

    /// Compose the current LIVE content for an Audience-class `screen` under ITS theme
    /// (86ajq321k) — a `FrameBuffer` a physical/NDI/stream output would show. `main` and
    /// the secondaries all render the SAME live item, each under its own theme, so N calls
    /// prove simultaneous multi-theme output. Blackout blacks every screen (audience-wide
    /// emergency). `None` for an unknown screen id.
    pub fn compose_screen(&self, screen: &str) -> Option<FrameBuffer> {
        // Only an Audience-class registry screen composes a themed frame — the stage
        // confidence monitor (its own surface) and an unknown id yield `None`.
        let sc = self.screen_registry.get(screen)?;
        if !sc.role.is_audience() {
            return None;
        }
        let out = self.presenter.live_output();
        // A DISABLED screen (a per-screen mute) or a global blackout blacks this screen —
        // reuse the existing safe all-black path (no new None/panic).
        if !sc.enabled || self.blackout {
            return Some(FrameBuffer::filled(
                out.width(),
                out.height(),
                selahcue_present::Rgba::BLACK,
            ));
        }
        let theme = self
            .screen_themes
            .get(screen)
            .and_then(|name| self.resolve_theme(name));
        // Gate the composed layers by THIS screen's VISIBLE-LAYERS config (Design 2.0), so a
        // hidden layer (e.g. lyrics off on the livestream feed) is actually dropped from the
        // preview + the composed output — not merely stored.
        let mask = to_layer_mask(&self.output_config(screen));
        Some(self.presenter.compose_screen_live(theme.as_ref(), mask))
    }

    /// The per-screen theme map (`screen → theme name`), for the operator view + persist.
    pub fn screen_themes(&self) -> &std::collections::BTreeMap<String, String> {
        &self.screen_themes
    }

    /// Whether the per-screen theme map changed since the last check (persist signal).
    pub fn take_screen_themes_dirty(&mut self) -> bool {
        std::mem::take(&mut self.screen_themes_dirty)
    }

    /// Re-arm the per-screen persist signal (a failed write must be retried).
    pub fn mark_screen_themes_dirty(&mut self) {
        self.screen_themes_dirty = true;
    }

    /// Load the per-screen theme map at startup (from the store). Keeps only known
    /// screens with a known built-in theme name (so a stale/removed name is dropped,
    /// never crashes), applies `main` to the Presenter, and does not dirty.
    pub fn load_screen_themes(&mut self, themes: impl IntoIterator<Item = (String, String)>) {
        // Can change composed audience output without passing through `apply` — advance
        // the live generation so the NDI frame cache recomposes (dirty-gate, no stale frame).
        self.live_generation = self.live_generation.wrapping_add(1);
        // Keep only a theme whose screen is an Audience-class registry screen (built-in or
        // a restored virtual feed) with a resolvable name. Load the registry BEFORE the
        // per-screen themes so a virtual screen's theme survives; a theme for an
        // absent/deleted screen is dropped, never a crash.
        let saved = &self.saved_themes;
        let registry = &self.screen_registry;
        self.screen_themes = themes
            .into_iter()
            .filter(|(screen, name)| {
                registry.get(screen).is_some_and(|s| s.role.is_audience())
                    && resolve_theme_name(name, saved).is_some()
            })
            .collect();
        self.screen_themes_dirty = false;
        // Reflect the restored `main` screen theme on the physical output (a no-op when
        // nothing is staged/live yet; recovery re-stages afterwards using it).
        if let Some(theme) = self
            .screen_themes
            .get("main")
            .and_then(|name| self.resolve_theme(name))
        {
            self.presenter.set_main_screen_theme(Some(theme));
            self.presenter.blackout(self.blackout);
        }
    }

    /// Enable or disable a screen by id (Screens page — dynamic registry). A disabled
    /// VIRTUAL screen composes safe all-black and stops its NDI delivery. For the BUILT-IN
    /// `main`/`stage` screens the flag means the desktop's OS WINDOW EXISTS: the host opens
    /// or closes that window to match (see `reconcile_windows` in selahcue-desktop), which
    /// is also what the window's own close button does. An unknown id is rejected. Marks
    /// the registry for persistence.
    fn set_screen_enabled(&mut self, screen: &str, enabled: bool) -> ControllerReply {
        if self.screen_registry.set_enabled(screen, enabled) {
            self.screen_registry_dirty = true;
            ControllerReply::Ack
        } else {
            ControllerReply::Deny(DenyReason::BadRequest)
        }
    }

    /// Add a VIRTUAL Audience-class screen (`role` is `lower-third`/`stream`), minting a
    /// stable id. Rejected for a bad role or at the bounded [`MAX_SCREENS`] cap. Marks the
    /// registry for persistence.
    fn add_screen(&mut self, role: &str) -> ControllerReply {
        let Some(role) = ScreenRole::from_tag(role) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        match self.screen_registry.add_virtual(role) {
            Ok(_id) => {
                self.screen_registry_dirty = true;
                ControllerReply::Ack
            }
            Err(_) => ControllerReply::Deny(DenyReason::BadRequest),
        }
    }

    /// Remove a screen by id — ONLY a deletable (virtual) screen; a built-in is rejected
    /// server-side. Also drops the screen's per-screen theme override. Idempotent for an
    /// already-absent id. Marks the registry (and theme map, if changed) for persistence.
    fn remove_screen(&mut self, screen: &str) -> ControllerReply {
        match self.screen_registry.remove(screen) {
            RemoveOutcome::Removed => {
                self.screen_registry_dirty = true;
                if self.screen_themes.remove(screen).is_some() {
                    self.screen_themes_dirty = true;
                }
                // Drop the removed screen's per-output config too (keys stay a subset of the
                // registry ids), so a re-minted id never inherits a stale config.
                if self.output_configs.remove(screen).is_some() {
                    self.output_configs_dirty = true;
                }
                ControllerReply::Ack
            }
            // Deleting a built-in is a client bug (the UI hides the control) — deny.
            RemoveOutcome::NotDeletable => ControllerReply::Deny(DenyReason::BadRequest),
            // Idempotent: an already-absent id acks (a double-delete is not an error).
            RemoveOutcome::Absent => ControllerReply::Ack,
        }
    }

    /// The screen registry (for the operator view + persistence).
    pub fn screen_registry(&self) -> &ScreenRegistry {
        &self.screen_registry
    }

    /// Whether a screen is enabled — the desktop consults this to decide whether the
    /// physical `main`/`stage` WINDOW should exist, and to gate a virtual screen's NDI
    /// delivery. An unknown id defaults to enabled (see [`ScreenRegistry::is_enabled`]).
    pub fn is_screen_enabled(&self, id: &str) -> bool {
        self.screen_registry.is_enabled(id)
    }

    /// Whether the screen registry changed since the last check (persist signal).
    pub fn take_screen_registry_dirty(&mut self) -> bool {
        std::mem::take(&mut self.screen_registry_dirty)
    }

    /// Re-arm the registry persist signal (a failed write must be retried).
    pub fn mark_screen_registry_dirty(&mut self) {
        self.screen_registry_dirty = true;
    }

    /// Load the screen registry at startup from persisted rows `(id, role_tag, enabled,
    /// deletable)` — recovers robustly to the built-in default (see
    /// [`ScreenRegistry::from_persisted`]). Does not dirty.
    pub fn load_screen_registry<I>(&mut self, rows: I)
    where
        I: IntoIterator<Item = (String, String, bool, bool)>,
    {
        // Can change composed audience output without passing through `apply` — advance
        // the live generation so the NDI frame cache recomposes (dirty-gate, no stale frame).
        self.live_generation = self.live_generation.wrapping_add(1);
        self.screen_registry = ScreenRegistry::from_persisted(rows);
        self.screen_registry_dirty = false;
    }

    /// Mutate a screen's output config via `f`, normalizing the result: an UNKNOWN screen is
    /// rejected; a mutation that leaves the config all-default removes the map entry (so only
    /// a configured screen occupies the bounded map); a genuine change marks the persist
    /// signal. A no-op mutation acks without dirtying. The single choke point for every
    /// `SetOutput*` handler.
    fn mutate_output_config<F: FnOnce(&mut OutputConfigView)>(
        &mut self,
        screen: &str,
        f: F,
    ) -> ControllerReply {
        if self.screen_registry.get(screen).is_none() {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let before = self.output_configs.get(screen).cloned().unwrap_or_default();
        let mut cfg = before.clone();
        f(&mut cfg);
        if cfg == before {
            return ControllerReply::Ack; // no-op — do not dirty
        }
        if cfg.is_default() {
            self.output_configs.remove(screen);
        } else {
            self.output_configs.insert(screen.to_string(), cfg);
        }
        self.output_configs_dirty = true;
        ControllerReply::Ack
    }

    /// Set a screen's orientation (quarter-turns clockwise). `>= 4` is rejected (a client bug).
    fn set_output_orientation(&mut self, screen: &str, quarter_turns: u8) -> ControllerReply {
        if quarter_turns >= 4 {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        self.mutate_output_config(screen, |c| c.orientation = quarter_turns)
    }

    /// Set a screen's scaling/fit mode.
    fn set_output_scale_fit(&mut self, screen: &str, fit: ScaleFit) -> ControllerReply {
        self.mutate_output_config(screen, |c| c.scale_fit = fit)
    }

    /// Mirror a screen's output horizontally.
    fn set_output_mirror(&mut self, screen: &str, on: bool) -> ControllerReply {
        self.mutate_output_config(screen, |c| c.mirror = on)
    }

    /// Set a screen's output delay (ms), clamped to [`MAX_OUTPUT_DELAY_MS`] (no-leak bound).
    fn set_output_delay(&mut self, screen: &str, ms: u32) -> ControllerReply {
        let ms = ms.min(MAX_OUTPUT_DELAY_MS);
        self.mutate_output_config(screen, |c| c.delay_ms = ms)
    }

    /// Set a screen's target frame rate (fps), clamped to `[MIN_FRAME_RATE, MAX_FRAME_RATE]`.
    fn set_output_frame_rate(&mut self, screen: &str, fps: u16) -> ControllerReply {
        let fps = fps.clamp(MIN_FRAME_RATE, MAX_FRAME_RATE);
        self.mutate_output_config(screen, |c| c.frame_rate = fps)
    }

    /// Toggle a screen's safe-area guides (operator preview overlay only).
    fn set_output_safe_area(&mut self, screen: &str, on: bool) -> ControllerReply {
        self.mutate_output_config(screen, |c| c.safe_area_guides = on)
    }

    /// Show/hide one compositing layer on a screen. An unknown `layer` tag is rejected.
    fn set_screen_layer_visible(
        &mut self,
        screen: &str,
        layer: &str,
        visible: bool,
    ) -> ControllerReply {
        // Validate the layer tag BEFORE touching config, so a bogus layer never mutates state.
        if !matches!(
            layer,
            "background" | "text" | "lower-third" | "logo" | "timer"
        ) {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let reply = self.mutate_output_config(screen, |c| match layer {
            "background" => c.layers.background = visible,
            "text" => c.layers.text = visible,
            "lower-third" => c.layers.lower_third = visible,
            "logo" => c.layers.logo = visible,
            "timer" => c.layers.timer = visible,
            _ => {}
        });
        // The physical `main` output (and its preview) is composed by the Presenter, so push
        // main's new layer mask there to recompose Preview + Live immediately (secondary
        // screens gate at `compose_screen` time; the `timer` layer is the stage path). A
        // recompose re-issues SetScene, so re-apply blackout (mask ⟂ blackout).
        if matches!(reply, ControllerReply::Ack) && screen == "main" {
            let mask = to_layer_mask(&self.output_config("main"));
            self.presenter.set_main_layer_mask(mask);
            self.presenter.blackout(self.blackout);
        }
        // The stage screen's `timer` layer gates the confidence monitor — mark it dirty so the
        // next tick recomposes with/without the countdown immediately.
        if matches!(reply, ControllerReply::Ack) && screen == "stage" && layer == "timer" {
            self.stage_dirty = true;
        }
        reply
    }

    /// Configure a screen's NDI output (Audience-class `stream`/`lower-third` feed only): set
    /// its source `name` and whether NDI delivery is `enabled`, atomically. Validates:
    /// audience-class screen; a bounded, printable (no control-char) name; a non-empty name
    /// when enabling; and NAME UNIQUENESS across every OTHER enabled NDI screen (two live NDI
    /// sources must not share a name). Persists via the shared output-config store.
    fn set_ndi_output(&mut self, screen: &str, name: &str, enabled: bool) -> ControllerReply {
        // Audience-class only — never the stage confidence monitor or an unknown id.
        if !self
            .screen_registry
            .get(screen)
            .is_some_and(|s| s.role.is_audience())
        {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let name = name.trim();
        // A bounded, printable name (NDI source names are conventionally simple text); a
        // control char / newline is rejected, never sanitized silently.
        if !ndi_name_valid(name) {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        // Enabling NDI requires a name; disabling may clear it.
        if enabled && name.is_empty() {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        // Uniqueness: no OTHER currently-enabled NDI screen may broadcast the same source name
        // (two NDI senders sharing a name collide on the network).
        if enabled
            && self
                .output_configs
                .iter()
                .any(|(id, cfg)| id != screen && cfg.ndi_enabled && cfg.ndi_name == name)
        {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        self.mutate_output_config(screen, |c| {
            c.ndi_name = name.to_string();
            c.ndi_enabled = enabled;
        })
    }

    /// A screen's per-output config (its default/identity value when unconfigured).
    pub fn output_config(&self, screen: &str) -> OutputConfigView {
        self.output_configs.get(screen).cloned().unwrap_or_default()
    }

    /// The full per-screen output-config map (for the operator view + persistence).
    pub fn output_configs(&self) -> &std::collections::BTreeMap<String, OutputConfigView> {
        &self.output_configs
    }

    /// Whether the per-screen output-config map changed since the last check (persist signal).
    pub fn take_output_configs_dirty(&mut self) -> bool {
        std::mem::take(&mut self.output_configs_dirty)
    }

    /// Re-arm the output-config persist signal (a failed write must be retried).
    pub fn mark_output_configs_dirty(&mut self) {
        self.output_configs_dirty = true;
    }

    /// Load per-screen output configs at startup. Keeps only a config whose screen exists in
    /// the registry (load the registry FIRST) and drops any all-default entry, so a
    /// stale/removed screen's config is discarded rather than crashing. Does not dirty.
    pub fn load_output_configs(
        &mut self,
        configs: impl IntoIterator<Item = (String, OutputConfigView)>,
    ) {
        // Can change composed audience output without passing through `apply` — advance
        // the live generation so the NDI frame cache recomposes (dirty-gate, no stale frame).
        self.live_generation = self.live_generation.wrapping_add(1);
        let registry = &self.screen_registry;
        self.output_configs = configs
            .into_iter()
            .filter(|(screen, cfg)| registry.get(screen).is_some() && !cfg.is_default())
            .collect();
        // Defensively re-apply the NDI invariants the command path enforces, so a tampered /
        // forward-compat store cannot reintroduce a forbidden NDI state (a non-audience or
        // invalid-name phantom source, or two enabled sources sharing a name). Mirrors the
        // audience-filter `load_screen_themes` applies on load. Iteration order is deterministic
        // (a BTreeMap keyed by screen id), so the first enabled screen keeps a contested name.
        let mut claimed_ndi: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
        for (screen, cfg) in self.output_configs.iter_mut() {
            if !cfg.ndi_enabled {
                continue;
            }
            let name = cfg.ndi_name.trim();
            let ok = self
                .screen_registry
                .get(screen)
                .is_some_and(|s| s.role.is_audience())
                && !name.is_empty()
                && ndi_name_valid(name)
                && claimed_ndi.insert(name.to_string());
            if !ok {
                cfg.ndi_enabled = false; // disable a phantom / invalid / duplicate NDI source
            }
        }
        // A config that normalized back to default (e.g. NDI was its only non-default field) is
        // dropped so it never re-surfaces or re-persists.
        self.output_configs.retain(|_, cfg| !cfg.is_default());
        self.output_configs_dirty = false;
        // Reflect the restored MAIN screen's layer mask on the Presenter (a no-op recompose
        // while nothing is live yet; recovery re-stages afterwards with the mask in place).
        let mask = to_layer_mask(&self.output_config("main"));
        self.presenter.set_main_layer_mask(mask);
    }

    /// A persistable snapshot of the live session at `now` (injected clock, so the
    /// timer's elapsed is exact at the save instant).
    pub fn snapshot(&self, now: Instant) -> ControllerSnapshot {
        let (timer_total_secs, timer_elapsed_secs, timer_running) =
            match (&self.timer, self.timer_total) {
                (Some(timer), Some(total)) => (
                    Some(total.as_secs() as u32),
                    Some(timer.elapsed(now).as_secs() as u32),
                    // Mirror the wire guard (see `running` in the operator view): a paused
                    // timer — including the pending-pause window before the banking tick —
                    // must persist as NOT running, so recovery derives `timer_paused` back
                    // (restore: `timer_paused = !timer_running`) and never resumes a paused
                    // countdown as RUNNING (review: snapshot/restore paused asymmetry).
                    (timer.is_running() || self.timer_pending_start) && !self.timer_paused,
                ),
                _ => (None, None, false),
            };
        ControllerSnapshot {
            live_idx: self.live_idx.map(|i| i as u32),
            staged_idx: self.staged_idx.map(|i| i as u32),
            plan_cursor: self.plan_cursor.map(|i| i as u32),
            blackout: self.blackout,
            timer_total_secs,
            timer_elapsed_secs,
            timer_running,
            live_scripture: self.live_scripture.clone(),
            staged_scripture: self.staged_scripture.clone(),
            live_free_text: self.live_free_text.clone(),
            live_free_body: (!self.live_free_body.is_empty())
                .then(|| self.live_free_body.join("\n")),
            live_slide: self.live_idx.map(|_| self.live_slide as u32),
            staged_slide: self.staged_idx.map(|_| self.staged_slide as u32),
            cursor_slide: self.plan_cursor.map(|_| self.cursor_slide as u32),
            // Persist only a non-default theme (a "classic" session stays a NULL
            // theme row — the pre-v8 shape).
            theme: (self.theme_name != "classic").then(|| self.theme_name.clone()),
            custom_theme: self.custom_theme_json.clone(),
        }
    }

    /// Restore a persisted session onto this (freshly constructed) controller —
    /// the crash-recovery path. State is rebuilt through the same code paths the
    /// commands use, so the outputs re-render exactly. Indices that don't fit the
    /// current plan are ignored (defensive: a snapshot from a different plan must
    /// never panic or point past the end). A running countdown resumes from its
    /// persisted elapsed on the next [`tick`](Self::tick).
    pub fn restore(&mut self, snap: &ControllerSnapshot) {
        // Can change composed audience output without passing through `apply` — advance
        // the live generation so the NDI frame cache recomposes (dirty-gate, no stale frame).
        self.live_generation = self.live_generation.wrapping_add(1);
        let len = self.plan.len();
        let ok = |v: Option<u32>| v.map(|i| i as usize).filter(|i| *i < len);

        // Apply the persisted theme FIRST so all restored content composes with it.
        // A custom theme (Theme Designer) takes precedence over a built-in name; an
        // unknown/absent/corrupt value leaves the default. Blackout is re-applied later.
        if let Some(json) = snap.custom_theme.as_deref() {
            if !self.set_custom_theme(json) {
                if let Some(name) = snap.theme.as_deref() {
                    self.set_theme(name);
                }
            }
        } else if let Some(name) = snap.theme.as_deref() {
            self.set_theme(name);
        }

        // A slide position only applies if it exists on the (possibly edited)
        // item — otherwise fall back to slide 0, never past the stanza list.
        fn slide_ok(plan: &ServicePlan, idx: usize, v: Option<u32>) -> usize {
            let count = plan.items()[idx].slide_count();
            v.map(|s| s as usize).filter(|s| *s < count).unwrap_or(0)
        }
        // Rebuild LIVE first: a plan item by index, or a scripture by its reference.
        if let Some(live) = ok(snap.live_idx) {
            let slide = slide_ok(&self.plan, live, snap.live_slide);
            self.stage_slide(live, slide);
            if self.presenter.go_live() {
                self.live_idx = Some(live);
                self.live_slide = slide;
            }
        } else if let Some(reference) = snap.live_scripture.as_ref() {
            self.presenter.stage(scripture_slide(reference));
            if self.presenter.go_live() {
                self.live_idx = None;
                self.live_scripture = Some(reference.clone());
            }
        } else if let Some(text) = snap.live_free_text.as_ref() {
            // A removed item's slide: restore exactly what was on screen — title
            // AND body (a removed song keeps its lyrics), never recomposed as
            // scripture even if the title parses as a reference (review 7y-B/8a).
            let body: Vec<String> = snap
                .live_free_body
                .as_ref()
                .filter(|b| !b.is_empty())
                .map(|b| b.split('\n').map(str::to_string).collect())
                .unwrap_or_default();
            self.presenter.stage(Slide::new(text.clone(), body.clone()));
            if self.presenter.go_live() {
                self.live_idx = None;
                self.live_free_text = Some(text.clone());
                self.live_free_body = body;
            }
        }
        // Then PREVIEW: a plan item, a scripture, or — explicitly — nothing (go_live
        // leaves its input in the staged slot, so an empty preview must be cleared or
        // the monitor would show a phantom "next" and a later GoLive would desync).
        if let Some(staged) = ok(snap.staged_idx) {
            let slide = slide_ok(&self.plan, staged, snap.staged_slide);
            self.stage_slide(staged, slide);
        } else if let Some(reference) = snap.staged_scripture.as_ref() {
            self.presenter.stage(scripture_slide(reference));
            self.staged_idx = None;
            self.staged_scripture = Some(reference.clone());
        } else {
            self.presenter.clear_preview();
            self.staged_idx = None;
        }
        if let Some(cursor) = ok(snap.plan_cursor) {
            self.plan_cursor = Some(cursor);
            self.cursor_slide = slide_ok(&self.plan, cursor, snap.cursor_slide);
        }

        self.blackout = snap.blackout;
        self.presenter.blackout(snap.blackout);

        if let Some(total) = snap.timer_total_secs {
            let total = Duration::from_secs(u64::from(total));
            let elapsed = Duration::from_secs(u64::from(snap.timer_elapsed_secs.unwrap_or(0)));
            self.timer = Some(Timer::count_down(total).with_elapsed(elapsed));
            self.timer_total = Some(total);
            self.timer_pending_start = snap.timer_running;
            // A recovered timer that is present but not running was paused (only Pause
            // yields a non-running active timer). Recover it as paused, not silently
            // running (the snapshot has no separate paused bit — this is derived).
            self.timer_paused = !snap.timer_running;
            self.timer_pending_pause = false;
            self.last_timer_view = None;
        }

        self.stage_dirty = true;
        self.state_dirty = false; // we just loaded this state — nothing new to save
    }

    /// Whether state changed since the last [`take_state_dirty`] (autosave signal).
    /// The live-output GENERATION (NDI dirty-gate seam): while this value is unchanged,
    /// every [`compose_screen`](Self::compose_screen) frame is guaranteed unchanged, so a
    /// per-frame consumer (the desktop's NDI reconcile) may re-send its cached frame
    /// instead of recomposing. It advances on any mutation that can change composed
    /// output; it may over-count (see the field doc) but never under-counts.
    pub fn live_generation(&self) -> u64 {
        self.live_generation
    }

    pub fn take_state_dirty(&mut self) -> bool {
        std::mem::take(&mut self.state_dirty)
    }

    /// Re-arm the autosave signal (e.g. the save loop consumed it but deferred the
    /// write to respect its throttle).
    pub fn mark_state_dirty(&mut self) {
        self.state_dirty = true;
    }

    /// Whether the plan itself changed since the last check (persist signal).
    pub fn take_plan_dirty(&mut self) -> bool {
        std::mem::take(&mut self.plan_dirty)
    }

    /// Re-arm the plan persist signal (a failed write must be retried).
    pub fn mark_plan_dirty(&mut self) {
        self.plan_dirty = true;
    }

    /// Arm the identify overlay (host-local `I` key; same path as the command).
    pub fn trigger_identify(&mut self) {
        self.identify_pending = true;
    }

    /// While `Some`, outputs show their identify numbers (window-level overlay —
    /// presentation state is untouched and resumes by itself at expiry).
    pub fn identify_until(&self) -> Option<Instant> {
        self.identify_until
    }

    /// Drain the requested display assignments (role, display key) — the desktop
    /// shell applies them to real windows and persists them.
    pub fn take_pending_assignments(&mut self) -> Vec<(String, String)> {
        std::mem::take(&mut self.pending_assignments)
    }

    /// Inject the physical output/display status the operator view reports
    /// (desktop shell only; other hosts leave these empty).
    pub fn set_output_status(
        &mut self,
        outputs: Vec<OutputStatusView>,
        displays: Vec<DisplayView>,
    ) {
        self.output_status = outputs;
        self.display_status = displays;
    }

    /// The current service plan (for persistence).
    pub fn plan(&self) -> &ServicePlan {
        &self.plan
    }

    /// Whether a countdown is active (the autosave loop refreshes the persisted
    /// elapsed periodically while one runs).
    pub fn timer_active(&self) -> bool {
        self.timer.is_some()
    }

    /// Show the pairing invite as a QR on the stage/confidence output until
    /// `expires_at` (auto-cleared by [`tick`](Self::tick)) — the audience output is
    /// never used for pairing.
    pub fn show_pairing_qr(&mut self, invite_uri: String, expires_at: Instant) {
        self.pairing_qr = Some((invite_uri, expires_at));
        self.stage_dirty = true;
    }

    /// Dismiss the pairing QR (e.g. pairing completed or the operator cancelled).
    pub fn clear_pairing_qr(&mut self) {
        if self.pairing_qr.take().is_some() {
            self.stage_dirty = true;
        }
    }

    /// Whether pairing mode (the QR overlay) is currently active.
    pub fn pairing_qr_active(&self) -> bool {
        self.pairing_qr.is_some()
    }

    /// Push the current local wall clock (a pre-formatted date line and 12-hour time) onto the
    /// confidence monitor's Timer-only chrome (Figma 374-151). The desktop backend calls this
    /// each refresh with `chrono::Local::now()`; composition itself never reads the OS clock,
    /// so the monitor only re-composes when the displayed minute actually changes (no busy
    /// redraw). Blank strings clear the chrome.
    pub fn set_wall_clock(&mut self, date: &str, time: &str) {
        let next = if date.trim().is_empty() && time.trim().is_empty() {
            None
        } else {
            Some(WallClock::new(date.trim(), time.trim()))
        };
        if self.stage.clock() != next.as_ref() {
            self.stage.set_clock(next);
            self.stage_dirty = true;
        }
    }

    /// The stage/confidence monitor output (a second display surface). Updated by
    /// [`tick`](Self::tick) from the same live state as the main output.
    pub fn stage_output(&self) -> &FrameBuffer {
        self.stage.output()
    }

    /// Advance the active timer to `now` and overlay it on the Live output. Call once per
    /// render frame; time is **injected** (no wall-clock read) so it stays deterministic
    /// and frame-rate independent (NFR-022). A no-op when no timer is running.
    pub fn tick(&mut self, now: Instant) {
        let view = match self.timer.as_mut() {
            Some(timer) => {
                if self.timer_pending_start {
                    timer.start(now);
                    self.timer_pending_start = false;
                }
                // Bank a pending pause with the injected clock (apply has none). A paused
                // Timer has `running_since == None`, so `TimerView::from_timer` reads the
                // frozen `accumulated` — remaining/elapsed/warn/time_up all freeze.
                if self.timer_pending_pause {
                    timer.pause(now);
                    self.timer_pending_pause = false;
                }
                Some(TimerView::from_timer(
                    timer,
                    now,
                    self.timer_total,
                    TIMER_WARN_SECS,
                ))
            }
            None => None,
        };
        self.last_timer_view = view;
        // The countdown is a speaker aid: it appears on the stage/confidence monitor
        // (below), NOT on the audience/program output.

        // Identify overlay: armed by the command/key, started here (injected
        // clock), auto-expired — never a destructive presentation change.
        if self.identify_pending {
            self.identify_pending = false;
            self.identify_until = Some(now + IDENTIFY_TTL);
        }
        if self.identify_until.is_some_and(|t| now >= t) {
            self.identify_until = None;
        }

        // Auto-dismiss an expired pairing QR (its code is TTL-bound anyway).
        if self.pairing_qr.as_ref().is_some_and(|(_, exp)| now >= *exp) {
            self.pairing_qr = None;
            self.stage_dirty = true;
        }

        // The stage "Service timer" LAYER (Design 2.0 VISIBLE LAYERS): the confidence
        // monitor's countdown is gated by the STAGE screen's config — hidden when the operator
        // toggles it off (the countdown is stage-only, so this is the only output it affects).
        // The operator's own timer chip (`last_timer_view`, above) is ungated.
        let show_stage_timer = self
            .output_configs
            .get("stage")
            .map(|c| c.layers.timer)
            .unwrap_or(true);
        let stage_view = if show_stage_timer { view } else { None };

        // Refresh the confidence monitor when the timer's displayed value changed or a
        // command marked it dirty — not every frame. While pairing mode is active the
        // stage output shows the invite QR instead of the speaker scene.
        let key = timer_key(stage_view);
        if self.stage_dirty || key != self.last_stage_key {
            self.stage_dirty = false;
            self.last_stage_key = key;
            // Feed the worship header its live stanza position ("Verse 2 of 4"). Derived from
            // the live plan item; `None` for non-song items. (Computed before the mutable
            // borrow of `self.stage` below.)
            let position = self.stage_song_position();
            self.stage.set_song_position(position);
            match &self.pairing_qr {
                Some((uri, _)) => {
                    if !self.stage.show_qr(uri) {
                        // Unencodable data: fall back to the normal scene rather than
                        // freezing a stale frame.
                        self.pairing_qr = None;
                        let current = self.presenter.confidence_slide();
                        let next = self.stage_next_slide();
                        self.stage
                            .update(current.as_ref(), next.as_ref(), stage_view.as_ref());
                    }
                }
                None => {
                    let current = self.presenter.confidence_slide();
                    let next = self.stage_next_slide();
                    self.stage
                        .update(current.as_ref(), next.as_ref(), stage_view.as_ref());
                }
            }
        }
    }

    /// What the confidence monitor should show as "next": mid-song, the NEXT
    /// stanza of the LIVE song (the speaker needs the coming line, which may
    /// differ from Preview); otherwise whatever is staged in Preview. Public so
    /// the stage-output contract is directly observable (like [`Presenter::staged`]).
    pub fn stage_next_slide(&self) -> Option<Slide> {
        if let Some(i) = self.live_idx {
            if let Some(item) = self.plan.items().get(i) {
                if !item.stanzas.is_empty() && self.live_slide + 1 < item.slide_count() {
                    return Some(item_slide(item, self.live_slide + 1));
                }
            }
        }
        // During authored deck playback the operator supplies the COMING deck slide (Approach A —
        // the host is deck-blind); show its projection so the speaker sees the next deck slide,
        // not the stale Preview slide. `None` at the end of a deck → falls back to Preview.
        if let Some(next) = self.presenter.authored_next_confidence_slide() {
            return Some(next);
        }
        self.presenter.staged().cloned()
    }

    /// The live song's stanza position as 1-based `(index, total)` for the worship confidence
    /// header ("Verse 2 of 4"). `None` when the live item is not a multi-stanza song (a
    /// title-only or single-stanza item has no verse count to show). Public so the stage-output
    /// contract is directly observable (like [`stage_next_slide`](Self::stage_next_slide)).
    pub fn stage_song_position(&self) -> Option<(u16, u16)> {
        let item = self.plan.items().get(self.live_idx?)?;
        let total = item.stanzas.len();
        if total <= 1 {
            return None;
        }
        let idx = (self.live_slide.min(total - 1) + 1) as u16;
        Some((idx, total as u16))
    }

    /// The presenter (for the output window / stage display to render).
    /// Report the host's storage headroom for autosave (`guard::DiskStatus`).
    ///
    /// The host is the only layer that knows which volume backs its data directory, so it owns
    /// this verdict; the operator previously received a raw byte count and had to guess the
    /// thresholds. `status` is `"ok"` / `"low"` / `"critical"` / `"unknown"`, and `"unknown"`
    /// is a real outcome — the platform can fail to report free space, which is neither
    /// healthy nor critical.
    pub fn set_storage_health(
        &mut self,
        status: &str,
        available_bytes: Option<u64>,
        checkpoints_paused: bool,
    ) {
        self.storage_health = Some(StorageHealthView {
            status: status.to_string(),
            available_bytes,
            checkpoints_paused,
        });
    }

    /// Report the host's session-recovery state (`guard.rs` + `session_repo.rs`), which until
    /// now reached only stderr.
    ///
    /// `autosave_error` is truncated to a bounded length: exactly one is retained and each
    /// replaces the last, so nothing accumulates, but an uncapped host error string would still
    /// be unbounded growth.
    pub fn set_session_health(
        &mut self,
        restored: bool,
        crash_loop: bool,
        rapid_launches: Option<u32>,
        autosave_error: Option<&str>,
    ) {
        self.session_health = Some(SessionHealthView {
            restored,
            crash_loop,
            rapid_launches,
            autosave_error: autosave_error.map(|e| {
                selahcue_lan::protocol::truncate_for_wire(
                    e,
                    selahcue_lan::protocol::MAX_ERROR_TEXT_LEN,
                )
            }),
        });
    }

    /// Report a fault against the LIVE audience output (NFR-024).
    ///
    /// The host owns the real backend, so it is the only layer that learns a surface was
    /// lost or a decode failed; this is how it tells the controller, and therefore the
    /// operator. The audience keeps seeing the last good frame — reporting a fault never
    /// blanks or clears the output — and the hold shows up in the next
    /// [`operator_view`](Self::operator_view) as `output_health.held`.
    ///
    /// Recovery needs no call: the next successful compose presents a good frame and the
    /// engine clears the hold by itself.
    pub fn report_fault(&mut self, fault: selahcue_present::Fault) {
        self.presenter.inject_fault(fault);
    }

    pub fn presenter(&self) -> &Presenter {
        &self.presenter
    }

    /// The plan index currently on Live, if any.
    pub fn live_index(&self) -> Option<usize> {
        self.live_idx
    }

    /// The plan index currently staged in Preview, if any.
    pub fn staged_index(&self) -> Option<usize> {
        self.staged_idx
    }

    /// Whether the audience output is blacked out.
    pub fn is_blackout(&self) -> bool {
        self.blackout
    }

    /// The plan-level roll-up behind the builder's Plan Summary panel and run-sheet header
    /// (FR-004).
    ///
    /// `missing` counts ONLY the links this host actually resolved, which today means
    /// scripture. Every deck and media link lands in `unknown` instead, because the host has
    /// no store for either library. Keeping those two totals apart is the whole point: folding
    /// `unknown` into `missing` would flag every healthy deck in the plan, and folding it into
    /// the clean count would report a plan verified that nothing ever checked.
    fn plan_summary(
        &self,
        resolutions: &[Option<selahcue_core::plan::LinkResolution>],
    ) -> PlanSummaryView {
        use selahcue_core::plan::{ItemKind, LinkResolution};
        // One roll-up, so the total and its completeness flag come from the same pass and can
        // never disagree (FR-202 · PLAN-SECTIONS-DURATIONS-spec §4.3).
        let planned = self.plan.planned_total();
        let mut sum = PlanSummaryView {
            planned_total_secs: planned.secs,
            planned_items: planned.counted.min(u32::MAX as usize) as u32,
            partial: planned.is_partial(),
            ..Default::default()
        };
        for (item, resolution) in self.plan.items().iter().zip(resolutions) {
            // Saturating throughout: MAX_PLAN_ITEMS puts these far below u32, so this can
            // never actually bite — it just means a pathological plan cannot panic a release
            // build or wrap to a smaller count in a debug one.
            // A Section is a DIVIDER, not an item. It is counted only as a section, and is
            // excluded from `items`, `assigned` and the link tallies. The design draws it that
            // way — node 608:875 reads "6 items" and "Assigned 6 / 6" over six rows and three
            // dividers — and the reasoning is the same one that keeps dividers out of
            // `partial`: a divider is not a staffable thing, so counting it in the assigned
            // denominator would make a fully staffed plan read as incomplete forever.
            // `sections` keeps the count, so nothing is lost, only unconflated.
            if item.kind == ItemKind::Section {
                sum.sections = sum.sections.saturating_add(1);
                continue;
            }
            sum.items = sum.items.saturating_add(1);
            let bucket = match item.kind {
                ItemKind::Song => &mut sum.songs,
                ItemKind::Scripture => &mut sum.scripture,
                ItemKind::SlideGroup => &mut sum.presentations,
                ItemKind::Media => &mut sum.media,
                ItemKind::Announcement => &mut sum.announcements,
                ItemKind::Timer => &mut sum.timers,
                // Unreachable: handled by the `continue` above. Kept as a real arm rather than
                // an `unreachable!()` so adding an ItemKind is a compile error here, never a
                // panic in front of an audience.
                ItemKind::Section => &mut sum.sections,
            };
            *bucket = bucket.saturating_add(1);
            if item.owner.is_some() {
                sum.assigned = sum.assigned.saturating_add(1);
            }
            match resolution {
                Some(LinkResolution::Missing) => sum.missing = sum.missing.saturating_add(1),
                Some(LinkResolution::Unknown) => sum.unknown = sum.unknown.saturating_add(1),
                // An unlinked item is not a problem, and a resolved one is not either.
                Some(LinkResolution::Resolved) | None => {}
            }
        }
        sum
    }

    /// A serializable snapshot for the operator UI: the plan with per-item Live/Preview
    /// flags, plus the current live/staged indices and blackout state.
    ///
    /// # Cadence assumption
    ///
    /// This is built **per poll and per action — never per frame.** Its dominant cost is link
    /// resolution: one scripture parse, and a corpus lookup, for every linked item in the plan.
    /// That is fine at the rate the operator console asks for state and after each command, and
    /// far too heavy for the render loop.
    ///
    /// Nothing in the type system enforces that. If a future caller reaches for this from a
    /// frame callback, the cost does not announce itself — it shows up as a frame-rate drop
    /// under a plan with many scripture links, which is the hardest kind of regression to trace
    /// back to its cause. Cache the view or resolve links ahead of time instead.
    pub fn operator_view(&self) -> OperatorView {
        // Resolve each item's link ONCE per build and share it with the summary below.
        // Resolving twice doubles this function's dominant cost — a scripture parse per linked
        // item — for no benefit (Vera, PR #13).
        let resolutions: Vec<Option<selahcue_core::plan::LinkResolution>> = self
            .plan
            .items()
            .iter()
            .map(|it| it.content.as_ref().map(host_resolution))
            .collect();
        let items = self
            .plan
            .items()
            .iter()
            .zip(&resolutions)
            .enumerate()
            .map(|(i, (item, resolution))| ItemView {
                id: item.id.0,
                kind: item.kind.as_tag().to_string(),
                title: item.title.clone(),
                is_live: self.live_idx == Some(i),
                is_staged: self.staged_idx == Some(i),
                // Truthful slide bookkeeping (S8-1): only multi-slide items
                // advertise a count; the position shows for the live/staged item.
                slide_count: (item.slide_count() > 1).then(|| item.slide_count() as u32),
                slide_index: if item.slide_count() > 1 {
                    if self.live_idx == Some(i) {
                        Some(self.live_slide as u32)
                    } else if self.staged_idx == Some(i) {
                        Some(self.staged_slide as u32)
                    } else {
                        None
                    }
                } else {
                    None
                },
                // The STAGED slide, always reported for the staged multi-slide item (even when it is
                // ALSO live at a different slide) — so the slide picker can mark PREVIEW and LIVE on
                // different slides. `slide_index` above stays LIVE-first for the plan-row badge.
                staged_slide_index: (item.slide_count() > 1 && self.staged_idx == Some(i))
                    .then_some(self.staged_slide as u32),
                theme: item.theme.clone(),
                // The linked content (scripture/deck/media), so the operator UI shows
                // link status (ADR-0020 follow-up). `None` = an unlinked item.
                link: item
                    .content
                    .as_ref()
                    .zip(*resolution)
                    .map(|(c, r)| content_link_view(c, r)),
                // Owner + planned duration for the run-sheet row (FR-004); `None` passes through
                // untouched so unassigned/unplanned items stay byte-stable on the wire.
                owner: item.owner.clone(),
                planned_secs: item.planned_secs,
            })
            .collect();
        // Wrapped here, not returned as an `Option` from `plan_summary`: this host always
        // reports a summary, and `None` on the wire means "this host does not report one".
        let summary = Some(self.plan_summary(&resolutions));
        OperatorView {
            plan_name: self.plan.name.clone(),
            items,
            summary,
            live_index: self.live_idx,
            staged_index: self.staged_idx,
            blackout: self.blackout,
            timer: self.last_timer_view.map(|v| TimerSnapshot {
                remaining_secs: v.remaining_secs,
                elapsed_secs: v.elapsed_secs,
                time_up: v.time_up,
                warn: v.warn,
                // Report NOT running the moment a pause is intended (paused), even before the
                // deferred `Timer::pause(now)` lands next tick — the wire never shows the
                // contradictory running && paused (review #3).
                running: self.timer.as_ref().is_some_and(Timer::is_running) && !self.timer_paused,
                paused: self.timer_paused,
                // The original countdown length, so the UI can reset to full even in overrun
                // (where remaining+elapsed no longer equals it — review #1).
                total_secs: self.timer_total.map(|d| d.as_secs() as u32),
            }),
            staged_scripture: self.staged_scripture.clone(),
            live_scripture: self.live_scripture.clone(),
            live_free_text: self.live_free_text.clone(),
            live_authored_id: self.presenter.authored_live_id(),
            outputs: self.output_status.clone(),
            displays: self.display_status.clone(),
            // Advertise only translations that can actually be rendered RIGHT NOW: bundled
            // translations are always available; a downloadable one (YLT) is withheld until its
            // verified asset is present (in the host, compiled without the `download` feature, it
            // is never available). This keeps an unavailable translation out of the operator
            // picker AND out of the cross-language wire list — matching download.rs's documented
            // boundary — so it can never be selected into a verse-less "title-only" slide.
            translations: selahcue_scripture::Translation::ALL
                .iter()
                .filter(|t| selahcue_scripture::is_available(**t))
                .map(|t| t.code().to_string())
                .collect(),
            theme: self.theme_name.clone(),
            themes: Theme::BUILTIN_NAMES.iter().map(|s| s.to_string()).collect(),
            saved_themes: self
                .saved_themes
                .iter()
                .map(|(name, json)| SavedThemeView {
                    name: name.clone(),
                    theme_json: json.clone(),
                })
                .collect(),
            screen_themes: self
                .screen_themes
                .iter()
                .map(|(screen, theme)| ScreenThemeView {
                    screen: screen.clone(),
                    theme: theme.clone(),
                })
                .collect(),
            // The screen registry (Screens page — dynamic registry): every managed screen
            // with its role, enable state, deletability, and theme (Audience-class only),
            // in deterministic registry order.
            screens: self
                .screen_registry
                .iter()
                .map(|s| ScreenView {
                    screen: s.id.clone(),
                    role: s.role.as_tag().to_string(),
                    enabled: s.enabled,
                    deletable: s.deletable,
                    theme: if s.role.is_audience() {
                        self.screen_themes.get(&s.id).cloned()
                    } else {
                        None
                    },
                    // Per-output config (identity/default when the screen is unconfigured;
                    // skipped on the wire then, keeping the v2 fixtures byte-identical).
                    config: self.output_configs.get(&s.id).cloned().unwrap_or_default(),
                })
                .collect(),
            // The stage/confidence template + production message (stage-only) — drive the Live
            // Console's Stage sub-tab and the confidence monitor's layout / message overlay.
            stage_template: self.stage.template().as_tag().to_string(),
            stage_message: self.stage.message().map(|m| m.to_string()),
            // The live output's fault/recovery health, read from the REAL compositor
            // (NFR-024). Always `Some` here: this controller owns a presenter, so it can
            // always answer — `held == false` is a positive "the output is healthy", not a
            // shrug. `None` is reserved for a view that arrives WITHOUT health, i.e. an
            // older host, which the UI must show as unknown rather than as a fault.
            output_health: Some(output_health_view(self.presenter.output_health())),
            // Storage + session health pass through exactly as the host reported them. They stay
            // `None` on a controller no host is driving (the stand-alone operator shell), which
            // is the honest answer there: nothing is autosaving, so there is nothing to report.
            storage: self.storage_health.clone(),
            session: self.session_health.clone(),
            // The bounded recent transcript tail (oldest first) — the log is already
            // capped; this trims the wire payload further.
            transcript: self
                .transcript
                .transcript()
                .recent(OPERATOR_TRANSCRIPT_TAIL)
                .into_iter()
                .map(|s| TranscriptSegmentView {
                    id: s.id,
                    start_ms: s.start_ms,
                    end_ms: s.end_ms,
                    text: s.text.clone(),
                })
                .collect(),
            // The live in-progress line (streaming interim), shown below the finalised tail.
            partial_transcript: self.partial.clone(),
            // The pending detection queue, each with its verse text (default translation)
            // so the operator sees WHAT they would stage before approving.
            detections: self
                .transcript
                .detections()
                .pending()
                .map(|d| {
                    let text = scripture::parse_one(&d.reference)
                        .ok()
                        .and_then(|r| selahcue_scripture::passage_text(&r))
                        .unwrap_or_default();
                    // Label the snippet with the translation it is in (the host default) — honest-
                    // empty when the verse text itself is unresolved, so the two stay consistent.
                    let translation = if text.is_empty() {
                        String::new()
                    } else {
                        selahcue_scripture::Translation::default()
                            .code()
                            .to_string()
                    };
                    DetectionView {
                        id: d.id,
                        reference: d.reference.clone(),
                        text,
                        // R4 confidence: NAMED_REFERENCE_CONFIDENCE for an explicitly-spoken
                        // reference, or the fuzzy quote matcher's coverage score for a paraphrase.
                        confidence: Some(d.confidence),
                        translation,
                        // Provenance: the transcript segment the reference was heard in — the UI
                        // resolves the spoken phrase + "spoken Ns ago" from the transcript tail.
                        source_segment: Some(d.source_segment),
                    }
                })
                .collect(),
            // The publish / hand-off state (FR-006). Always `Some` here: this controller owns
            // the plan document, so it can always answer. `None` on the wire is reserved for a
            // host that does not report it at all.
            publish: Some(self.publish_state()),
            // WHO is asking is not something this controller knows — it holds the plan, not the
            // session. The layers that DO know stamp it: the operator shell for the local
            // console, and the LAN handler for a remote session's authenticated role. `None`
            // here is therefore the honest answer, not a restriction.
            viewer: None,
            // The starter templates this build offers (FR-005), reported so the picker renders
            // the host's list rather than a client-side copy of it.
            plan_templates: selahcue_core::plan::PLAN_TEMPLATES
                .iter()
                .map(|t| PlanTemplateView {
                    id: t.id.to_string(),
                    name: t.name.to_string(),
                    items: t.items.len() as u32,
                })
                .collect(),
        }
    }

    fn slide_for(&self, idx: usize, slide: usize) -> Option<Slide> {
        self.plan
            .items()
            .get(idx)
            .map(|item| item_slide(item, slide))
    }

    /// Stage the plan item at `idx` in Preview at slide 0 (Live is untouched),
    /// advancing the navigation cursor to it.
    fn stage_index(&mut self, idx: usize) -> ControllerReply {
        self.stage_slide(idx, 0)
    }

    /// Stage a specific within-item slide of the plan item at `idx` (story
    /// S8-1). The slide is clamped to the item's slide count by [`item_slide`].
    fn stage_slide(&mut self, idx: usize, slide: usize) -> ControllerReply {
        match self.slide_for(idx, slide) {
            Some(composed) => {
                let count = self.plan.items()[idx].slide_count();
                let slide = slide.min(count - 1);
                // Per-item theme override (S8-3d): render this item on its own template
                // (a built-in or a saved-library theme, 86ajq69ft), falling back to the
                // global theme when it has no override or the name no longer resolves.
                let item_theme = self.plan.items()[idx]
                    .theme
                    .clone()
                    .and_then(|name| self.resolve_theme(&name));
                self.presenter.stage_themed(composed, item_theme);
                self.staged_idx = Some(idx);
                self.staged_slide = slide;
                self.plan_cursor = Some(idx);
                self.cursor_slide = slide;
                self.staged_scripture = None; // Preview now holds a plan item
                ControllerReply::Ack
            }
            None => ControllerReply::Deny(DenyReason::BadRequest),
        }
    }

    /// Apply one (already RBAC-authorized) command, returning the reply.
    pub fn apply(&mut self, command: &Command) -> ControllerReply {
        // Any command may change what the confidence monitor should show; refresh it on
        // the next tick (gated there, so a read just costs one recompose).
        self.stage_dirty = true;
        // Mutating commands mark the session for autosave (reads don't).
        match command {
            Command::GetState
            | Command::GetOperatorState
            | Command::GetConsoleThumbnails { .. }
            | Command::GetScreenFrame { .. }
            | Command::ScriptureSearch { .. }
            | Command::GetChapter { .. }
            // Transcript ingest + dismissing a detection change the operator VIEW but
            // not the persisted LIVE session, so they do not trigger an autosave (the
            // transcript is in-memory only this slice). Approving a detection stages a
            // scripture (a real Preview change), so it falls through to `state_dirty`.
            | Command::IngestTranscript { .. }
            | Command::DismissDetection { .. } => {}
            _ => {
                self.state_dirty = true;
                // NDI dirty-gate: any potentially state-changing command may change a composed
                // audience frame — advance the generation. Sharing this arm with `state_dirty`
                // keeps the read-command exclusion set in ONE audited place; over-counting is
                // safe (one extra recompose), under-counting would freeze a stale frame.
                self.live_generation = self.live_generation.wrapping_add(1);
            }
        }
        // Snapshot the plan before a plan-EDITING command so the edit can be undone (plan-editing
        // · undo/redo). Cloned up front but RECORDED only post-dispatch, once the edit is known to
        // apply (Ack) AND to have actually changed the plan document — a denied or no-op edit
        // records nothing and preserves the redo stack (no phantom history). Transport/timer/theme
        // /screen commands are not plan edits, so they never touch this history. The presenter's
        // Live output is never part of the snapshot — undo restores the plan DOCUMENT, not Live.
        let plan_before = Self::is_plan_edit(command).then(|| self.plan.clone());
        let len = self.plan.len();
        let reply = match command {
            Command::Next => {
                if len == 0 {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Resume from the plan cursor (unaffected by staging a scripture).
                // Advance WITHIN the current item's slide sequence first (songs,
                // S8-1); cross to the next plan item only when it is exhausted.
                match self.plan_cursor {
                    Some(i) => {
                        let slides = self.plan.items()[i].slide_count();
                        if self.cursor_slide + 1 < slides {
                            self.stage_slide(i, self.cursor_slide + 1)
                        } else {
                            let next = (i + 1).min(len - 1);
                            if next == i {
                                // Clamped at the end: re-stage the LAST slide (the
                                // pre-8a clamp semantics — never loop to stanza 0).
                                self.stage_slide(i, self.cursor_slide)
                            } else {
                                self.stage_slide(next, 0)
                            }
                        }
                    }
                    None => self.stage_slide(0, 0),
                }
            }
            Command::Previous => {
                if len == 0 {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Step back within the item first; crossing back into the previous
                // item enters at its LAST slide (symmetric traversal).
                match self.plan_cursor {
                    Some(i) if self.cursor_slide > 0 => self.stage_slide(i, self.cursor_slide - 1),
                    Some(i) => {
                        let prev = i.saturating_sub(1);
                        if prev == i {
                            self.stage_slide(i, 0)
                        } else {
                            let last = self.plan.items()[prev].slide_count() - 1;
                            self.stage_slide(prev, last)
                        }
                    }
                    None => self.stage_slide(0, 0),
                }
            }
            Command::SelectItem { item_id } => {
                match self.plan.items().iter().position(|it| it.id.0 == *item_id) {
                    Some(idx) => self.stage_index(idx),
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::SelectSlide {
                item_id,
                slide_index,
            } => {
                // Stage a specific within-item slide in Preview (the Live Console slide picker).
                // Preview only — Live is untouched (FR-012); `stage_slide` clamps the index to the
                // item's slide count. An unknown item id is rejected, leaving Preview unchanged.
                match self.plan.items().iter().position(|it| it.id.0 == *item_id) {
                    Some(idx) => self.stage_slide(idx, *slide_index as usize),
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::GoLive => {
                // Commit whatever is staged (a plan item OR a staged scripture); the
                // presenter reports whether anything was staged.
                if self.presenter.go_live() {
                    self.live_idx = self.staged_idx; // None for a non-plan scripture
                    self.live_slide = self.staged_slide;
                    self.live_scripture = self.staged_scripture.clone();
                    self.live_free_text = None;
                    self.live_free_body = Vec::new();
                    // Going live from blackout reveals the new content (UX-STATE-MATRIX).
                    self.blackout = false;
                    ControllerReply::Ack
                } else {
                    ControllerReply::Deny(DenyReason::BadRequest)
                }
            }
            Command::PresentAuthoredSlide {
                slide_json,
                theme_json,
                next_slide_json,
            } => {
                // Route a Design 2.0 authored deck slide to the LIVE audience output. It takes
                // over the live surface, so clear the plan/scripture/free-text live cursors
                // (mirrors Clear) and reveal it (mirrors GoLive's un-blackout). A malformed or
                // over-bounds payload is rejected — the live output is unchanged. `next_slide_json`
                // (the coming deck slide) feeds the confidence monitor's "next" (best-effort).
                if self.present_authored_slide(slide_json, theme_json, next_slide_json.as_deref()) {
                    self.live_idx = None;
                    self.live_scripture = None;
                    self.live_free_text = None;
                    self.live_free_body = Vec::new();
                    self.blackout = false;
                    ControllerReply::Ack
                } else {
                    ControllerReply::Deny(DenyReason::BadRequest)
                }
            }
            Command::Clear => {
                self.presenter.clear_live();
                self.live_idx = None;
                self.live_scripture = None;
                self.live_free_text = None;
                self.live_free_body = Vec::new();
                self.blackout = false;
                ControllerReply::Ack
            }
            Command::Blackout { on } => {
                self.blackout = *on;
                self.presenter.blackout(*on);
                ControllerReply::Ack
            }
            Command::StartTimer { seconds } => {
                let duration = Duration::from_secs(u64::from(*seconds));
                self.timer = Some(Timer::count_down(duration));
                self.timer_total = Some(duration);
                self.timer_pending_start = true;
                // A fresh timer is never paused (guards a stale paused flag from a prior run).
                self.timer_paused = false;
                self.timer_pending_pause = false;
                // Drop any prior view so the operator snapshot never mixes an old timer's
                // displayed value with the fresh timer's state before the next tick.
                self.last_timer_view = None;
                // The overlay appears on the next tick (which supplies the start instant).
                ControllerReply::Ack
            }
            Command::PauseTimer => {
                // Denied when no timer is active (mirrors AdjustTimer). The actual
                // `Timer::pause(now)` runs on the next tick (apply has no clock).
                if self.timer.is_none() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.timer_pending_pause = true;
                self.timer_paused = true;
                // Symmetric to ResumeTimer: clear any latched pending-start so a
                // pause-immediately-after-start cannot be snapshotted/recovered as RUNNING
                // (review #4). Harmless for the live path — pause banks a zero segment.
                self.timer_pending_start = false;
                self.state_dirty = true;
                ControllerReply::Ack
            }
            Command::ResumeTimer => {
                // Denied when no timer is active. Resume banks-then-starts via
                // `timer_pending_start` (Timer::start resumes from the banked elapsed).
                if self.timer.is_none() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.timer_pending_start = true;
                self.timer_pending_pause = false;
                self.timer_paused = false;
                self.state_dirty = true;
                ControllerReply::Ack
            }
            Command::AdjustTimer { delta_secs } => {
                let Some(timer) = self.timer.as_mut() else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                match timer.adjust(*delta_secs) {
                    Some(new_total) => {
                        self.timer_total = Some(new_total);
                        // The adjusted readout appears on the next tick; recovery
                        // persists the new total via the normal snapshot path.
                        self.state_dirty = true;
                        ControllerReply::Ack
                    }
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::StopTimer => {
                self.timer = None;
                self.timer_total = None;
                self.timer_pending_start = false;
                self.timer_pending_pause = false;
                self.timer_paused = false;
                self.last_timer_view = None;
                // `apply` marked the stage dirty; the next tick recomposes the monitor
                // without the timer. The audience output is untouched (no timer there).
                ControllerReply::Ack
            }
            Command::ScriptureSearch { query, translation } => {
                // Reference queries ("Rom 8:28") parse directly; anything else
                // keyword-searches the CHOSEN translation's verse text (the
                // search box sits beside the picker — they must agree).
                let t = match translation.as_deref() {
                    None => selahcue_scripture::Translation::default(),
                    Some(code) => match selahcue_scripture::Translation::from_code(code) {
                        Some(t) => t,
                        None => return ControllerReply::Deny(DenyReason::BadRequest),
                    },
                };
                let mut hits: Vec<selahcue_lan::protocol::ScriptureHitView> =
                    scripture::parse(query)
                        .iter()
                        .filter_map(|r| {
                            selahcue_scripture::passage_text_in(t, r).map(|text| {
                                selahcue_lan::protocol::ScriptureHitView {
                                    reference: r.to_string(),
                                    text,
                                }
                            })
                        })
                        .collect();
                if hits.is_empty() {
                    hits = selahcue_scripture::search_in(t, query, 8)
                        .into_iter()
                        .map(|hit| selahcue_lan::protocol::ScriptureHitView {
                            reference: hit.reference,
                            text: hit.text,
                        })
                        .collect();
                }
                ControllerReply::Message(ServerMessage::ScriptureResults {
                    query: query.clone(),
                    references: hits.iter().map(|h| h.reference.clone()).collect(),
                    hits,
                })
            }
            Command::StageScripture {
                reference,
                translation,
            } => {
                let t = match translation.as_deref() {
                    None => selahcue_scripture::Translation::default(),
                    Some(code) => match selahcue_scripture::Translation::from_code(code) {
                        Some(t) => t,
                        None => return ControllerReply::Deny(DenyReason::BadRequest),
                    },
                };
                // LAN peers are untrusted: a client can name a real-but-unavailable translation
                // (a downloadable one whose asset isn't present). Composing it would yield a
                // verse-less "title-only" slide yet still Ack — reject it instead of staging blank.
                if !selahcue_scripture::is_available(t) {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.presenter.stage(scripture_slide_in(t, reference));
                self.staged_idx = None; // a scripture slide is not a plan index
                self.staged_scripture = Some(reference.clone());
                ControllerReply::Ack
            }
            Command::FollowScripture {
                reference,
                translation,
            } => {
                let t = match translation.as_deref() {
                    None => selahcue_scripture::Translation::default(),
                    Some(code) => match selahcue_scripture::Translation::from_code(code) {
                        Some(t) => t,
                        None => return ControllerReply::Deny(DenyReason::BadRequest),
                    },
                };
                // Untrusted peer + never push blank to the audience: reject an unavailable
                // translation before it could be staged and (when a scripture is live) followed
                // straight onto Live as a verse-less slide. See StageScripture above.
                if !selahcue_scripture::is_available(t) {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Always stage the verse in Preview (identical to StageScripture).
                self.presenter.stage(scripture_slide_in(t, reference));
                self.staged_idx = None;
                self.staged_scripture = Some(reference.clone());
                // FOLLOW (owner refine #8): advance the LIVE output to the same verse ONLY
                // when a scripture is ALREADY live — never promotes non-live / non-scripture
                // content, so preview⟂live isolation holds when nothing is on air.
                if self.live_scripture.is_some() && self.presenter.go_live() {
                    self.live_idx = None; // a scripture is not a plan index
                    self.live_slide = self.staged_slide;
                    self.live_scripture = Some(reference.clone());
                    self.live_free_text = None;
                    self.live_free_body = Vec::new();
                    // Following updates the live CONTENT, not the blackout state (unlike
                    // GoLive, which reveals). `go_live()` re-issues SetScene on Live, which
                    // reveals the engine — so re-assert blackout to preserve it (theme ⟂
                    // blackout; same pattern as the recompose handlers).
                    if self.blackout {
                        self.presenter.blackout(true);
                    }
                }
                ControllerReply::Ack
            }
            Command::GetChapter {
                reference,
                translation,
            } => {
                let t = match translation.as_deref() {
                    None => selahcue_scripture::Translation::default(),
                    Some(code) => match selahcue_scripture::Translation::from_code(code) {
                        Some(t) => t,
                        None => return ControllerReply::Deny(DenyReason::BadRequest),
                    },
                };
                // Any parseable reference identifies the chapter (the verse part
                // is ignored by chapter_in); an unparseable one is a bad request.
                let Some(parsed) = scripture::parse(reference).into_iter().next() else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                match selahcue_scripture::chapter_in(t, &parsed) {
                    Some(ch) => ControllerReply::Message(ServerMessage::Chapter {
                        book_name: ch.book_name,
                        chapter: ch.chapter,
                        translation: t.code().to_string(),
                        verses: ch
                            .verses
                            .into_iter()
                            .map(|(number, text)| VerseView { number, text })
                            .collect(),
                        prev_ref: selahcue_scripture::adjacent_chapter_in(t, &parsed, false),
                        next_ref: selahcue_scripture::adjacent_chapter_in(t, &parsed, true),
                    }),
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::GetState => {
                let live_item = self
                    .live_idx
                    .and_then(|i| self.plan.items().get(i))
                    .map(|it| it.id.0);
                ControllerReply::Message(ServerMessage::State {
                    live_item,
                    blackout: self.blackout,
                })
            }
            Command::GetOperatorState => ControllerReply::Message(ServerMessage::OperatorState {
                view: self.operator_view().into(),
            }),
            Command::GetConsoleThumbnails { max_w, max_h } => {
                // A READ: downscale the host's current Preview + Live output to thumbnails so a
                // remote operator's console monitors show the TRUE composited pixels. No state
                // change, no tick — the audience output is untouched. Size clamped host-side so
                // the payload stays bounded regardless of the requested panel size.
                let mw = (*max_w).clamp(1, 480);
                let mh = (*max_h).clamp(1, 270);
                let pv = self.presenter().preview_output().thumbnail(mw, mh);
                // The Live monitor IS the `main` audience output — a disabled `main` screen
                // mutes it to black (matching the physical main window + the Screens preview),
                // so the operator never sees "airing" content while main is muted. (Preview is
                // the STAGED feed, unaffected by a per-screen main disable.)
                let lv = if self.is_screen_enabled("main") {
                    self.presenter().live_output().thumbnail(mw, mh)
                } else {
                    let out = self.presenter().live_output();
                    FrameBuffer::filled(out.width(), out.height(), selahcue_present::Rgba::BLACK)
                        .thumbnail(mw, mh)
                };
                ControllerReply::Message(ServerMessage::ConsoleThumbnails {
                    preview: Some(ThumbView::from_rgba(pv.width(), pv.height(), pv.bytes())),
                    live: Some(ThumbView::from_rgba(lv.width(), lv.height(), lv.bytes())),
                })
            }
            Command::GetScreenFrame {
                screen,
                max_w,
                max_h,
            } => {
                // A READ (86ajq321k): compose the current LIVE content for the named Audience
                // screen under ITS per-screen theme + downscale, so the operator Screens page can
                // preview each screen's design (the secondaries have no physical output yet). No
                // state change, no tick — the audience output is untouched. Size clamped host-side.
                let mw = (*max_w).clamp(1, 480);
                let mh = (*max_h).clamp(1, 270);
                let frame = self.compose_screen(screen).map(|fb| {
                    let t = fb.thumbnail(mw, mh);
                    ThumbView::from_rgba(t.width(), t.height(), t.bytes())
                });
                ControllerReply::Message(ServerMessage::ScreenFrame {
                    screen: screen.clone(),
                    frame,
                })
            }
            Command::IdentifyOutputs => {
                self.identify_pending = true;
                ControllerReply::Ack
            }
            Command::AssignOutput { role, display_key } => {
                if !matches!(role.as_str(), "main" | "stage") {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Only keys from the advertised display list are acceptable (a
                // stale/unknown key is denied here, so the client sees it —
                // the shell re-validates against live monitors before applying).
                if !self.display_status.is_empty()
                    && !self.display_status.iter().any(|d| d.key == *display_key)
                {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Latest request per role wins; keyed insert keeps this bounded.
                self.pending_assignments.retain(|(r, _)| r != role);
                self.pending_assignments
                    .push((role.clone(), display_key.clone()));
                ControllerReply::Ack
            }
            // --- Plan editing (Operator-only via RBAC). Edits NEVER change the Live
            // output (FR-012 spirit): removing the live item keeps its slide on
            // screen; only the index bookkeeping adjusts. ---
            Command::AddItem {
                kind,
                title,
                content,
            } => {
                let Some(kind) = selahcue_core::plan::ItemKind::from_tag(kind) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                let title = title.trim();
                if title.is_empty() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Bound the plan (audit M2 no-leak rule): refuse a remote AddItem once the
                // run sheet is at MAX_PLAN_ITEMS so a buggy/hostile authenticated client loop
                // cannot grow `items` without limit. Far above any real plan, so this never
                // fires in legitimate use.
                if self.plan.len() >= selahcue_core::plan::MAX_PLAN_ITEMS {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                let id = self.plan.add_item(kind, title);
                // Optional stanza content (S8-1): the PD-hymn plain-text format,
                // stanzas separated by blank lines. Parsing is total.
                if let Some(text) = content {
                    if let Some(item) = self.plan.get_mut(id) {
                        item.stanzas = selahcue_core::plan::stanzas_from_text(text);
                    }
                }
                self.plan_dirty = true;
                ControllerReply::Ack
            }
            Command::RemoveItem { item_id } => {
                let Some(idx) = self.index_of(*item_id) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                if self
                    .plan
                    .remove(selahcue_core::plan::ItemId(*item_id))
                    .is_err()
                {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.plan_dirty = true;
                // Index fixup: shift anything after the removed slot; the removed
                // item's own references clear (Live keeps its rendered slide).
                let fix = |v: Option<usize>| match v {
                    Some(i) if i == idx => None,
                    Some(i) if i > idx => Some(i - 1),
                    other => other,
                };
                // The removed item's slide stays on the audience output (edits never
                // change Live). It is no longer a plan item, so track it as a FREE
                // live slide by its title — crash recovery restores that title slide
                // verbatim (never as recomposed scripture, review 7y-B).
                if self.live_idx == Some(idx) {
                    if let Some(slide) = self.presenter.live_slide() {
                        self.live_free_text = Some(slide.title.clone());
                        self.live_free_body = slide.body.clone();
                    }
                }
                // Slide positions follow their item; a removed item's positions reset.
                if self.live_idx == Some(idx) {
                    self.live_slide = 0;
                }
                if self.staged_idx == Some(idx) {
                    self.staged_slide = 0;
                }
                if self.plan_cursor == Some(idx) {
                    self.cursor_slide = 0;
                }
                self.live_idx = fix(self.live_idx);
                self.staged_idx = fix(self.staged_idx);
                self.plan_cursor = match self.plan_cursor {
                    Some(i) if i >= idx => i.checked_sub(1),
                    other => other,
                };
                if self.staged_idx.is_none() && self.staged_scripture.is_none() {
                    self.presenter.clear_preview();
                }
                ControllerReply::Ack
            }
            Command::MoveItem { item_id, to } => {
                let Some(from) = self.index_of(*item_id) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                let to = (*to as usize).min(self.plan.len().saturating_sub(1));
                if self.plan.reorder(from, to).is_err() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.plan_dirty = true;
                // Index fixup: a move renumbers everything between `from` and `to`.
                let fix = |v: Option<usize>| {
                    v.map(|i| {
                        if i == from {
                            to
                        } else if from < to && i > from && i <= to {
                            i - 1
                        } else if to < from && i >= to && i < from {
                            i + 1
                        } else {
                            i
                        }
                    })
                };
                self.live_idx = fix(self.live_idx);
                self.staged_idx = fix(self.staged_idx);
                self.plan_cursor = fix(self.plan_cursor);
                ControllerReply::Ack
            }
            Command::RenameItem { item_id, title } => {
                let title = title.trim();
                if title.is_empty() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                let Some(item) = self.plan.get_mut(selahcue_core::plan::ItemId(*item_id)) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                item.title = title.to_string();
                self.plan_dirty = true;
                // A renamed item that is staged re-renders in Preview (Live is never
                // changed by an edit — the operator re-commits when ready).
                if self.staged_idx == self.index_of(*item_id) {
                    if let Some(idx) = self.staged_idx {
                        let slide = self.staged_slide;
                        self.stage_slide(idx, slide);
                    }
                }
                ControllerReply::Ack
            }
            Command::SetTheme { name } => {
                // Restyle both outputs in place — content is untouched (only its
                // design changes). An unknown built-in name is rejected.
                if self.set_theme(name) {
                    ControllerReply::Ack
                } else {
                    ControllerReply::Deny(DenyReason::BadRequest)
                }
            }
            Command::SetCustomTheme { theme_json } => {
                // Apply a Theme-Designer custom theme (content untouched). Malformed
                // JSON is rejected and leaves the current theme unchanged.
                if self.set_custom_theme(theme_json) {
                    ControllerReply::Ack
                } else {
                    ControllerReply::Deny(DenyReason::BadRequest)
                }
            }
            Command::SetItemTheme { item_id, theme } => {
                self.set_item_theme(*item_id, theme.clone())
            }
            Command::SetItemContent { item_id, link } => self.set_item_content(*item_id, link),
            Command::SetItemOwner { item_id, owner } => {
                self.set_item_owner(*item_id, owner.clone())
            }
            Command::SetItemDuration { item_id, secs } => self.set_item_duration(*item_id, *secs),
            Command::SaveTheme { name, theme_json } => self.save_theme(name, theme_json),
            Command::DeleteTheme { name } => self.delete_theme(name),
            Command::SetScreenTheme { screen, name } => self.set_screen_theme(screen, name),
            Command::SetScreenEnabled { screen, enabled } => {
                self.set_screen_enabled(screen, *enabled)
            }
            Command::AddScreen { role } => self.add_screen(role),
            Command::RemoveScreen { screen } => self.remove_screen(screen),
            // --- Per-output config (Screens page inspector). Each persists per screen and,
            // where a physical output exists, the desktop host applies it to the frame. ---
            Command::SetOutputOrientation {
                screen,
                quarter_turns,
            } => self.set_output_orientation(screen, *quarter_turns),
            Command::SetOutputScaleFit { screen, fit } => self.set_output_scale_fit(screen, *fit),
            Command::SetOutputMirror { screen, on } => self.set_output_mirror(screen, *on),
            Command::SetOutputDelay { screen, ms } => self.set_output_delay(screen, *ms),
            Command::SetOutputFrameRate { screen, fps } => self.set_output_frame_rate(screen, *fps),
            Command::SetOutputSafeArea { screen, on } => self.set_output_safe_area(screen, *on),
            Command::SetScreenLayerVisible {
                screen,
                layer,
                visible,
            } => self.set_screen_layer_visible(screen, layer, *visible),
            Command::SetNdiOutput {
                screen,
                name,
                enabled,
            } => self.set_ndi_output(screen, name, *enabled),
            // Stage/confidence template + production message (stage-only). Both mark the stage
            // dirty so the confidence monitor re-composes on the next tick.
            Command::SetStageTemplate { template } => {
                self.stage
                    .set_template(selahcue_present::stage::StageTemplate::from_tag(template));
                self.stage_dirty = true;
                ControllerReply::Ack
            }
            Command::SetStageMessage { text } => {
                self.stage.set_message(text);
                self.stage_dirty = true;
                ControllerReply::Ack
            }
            // --- Live transcript + scripture detection (R3/R4; ADR-0010). Assistive:
            // never touches the render/output path directly — ingestion feeds the
            // out-of-band engine; approving stages to Preview (operator Goes Live). ---
            Command::IngestTranscript {
                text,
                start_ms,
                end_ms,
                is_final,
            } => {
                let start = start_ms.unwrap_or(0);
                // A missing/backwards end clamps to start inside the engine.
                let end = end_ms.unwrap_or(start);
                // Run the FULL R4 detection (exact + fuzzy quote/paraphrase over the rolling
                // window), not just exact — this is the wire path a remote/mobile controller and
                // the STT worker feed, so paraphrases must resolve here too. A streaming interim
                // (`is_final == false`) only updates the live partial line.
                self.ingest_transcript(text, start, end, *is_final);
                ControllerReply::Ack
            }
            Command::ApproveDetection { detection_id } => {
                // Approving stages the detected verse in Preview (never auto-live,
                // FR-115) exactly as a manual StageScripture would, then drops it from
                // the queue. An unknown/stale id is a bad request.
                match self.transcript.approve(*detection_id) {
                    Some(detected) => {
                        // A whole-chapter detection stages just its first verse (never a full
                        // chapter of text on one slide); a specific verse stages as-is.
                        let staged = stage_reference_for_detection(&detected.reference);
                        self.presenter.stage(scripture_slide(&staged));
                        self.staged_idx = None; // a scripture slide is not a plan index
                        self.staged_scripture = Some(staged);
                        ControllerReply::Ack
                    }
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::DismissDetection { detection_id } => {
                if self.transcript.dismiss(*detection_id) {
                    ControllerReply::Ack
                } else {
                    ControllerReply::Deny(DenyReason::BadRequest)
                }
            }
            // --- Plan publish / hand-off (FR-006) + the plan lifecycle actions (FR-005) ---
            Command::PublishPlan => {
                // A statement about the DOCUMENT, not a cue. It moves the published marker and
                // counts the hand-off; it touches no cursor, no Preview and no Live output.
                //
                // Deliberately NOT a plan edit: `is_plan_edit` excludes it, so publishing takes
                // no undo snapshot and does not bump `plan_revision`. If it did, the act of
                // publishing would immediately mark the plan changed-since-publish and the badge
                // would be on the moment it was cleared.
                self.published_revision = Some(self.plan_revision);
                self.published_plan = Some(self.plan.clone());
                // Just published: the document IS the baseline. Set directly rather than by
                // calling the refresh below, so publishing cannot leave a badge standing even
                // if the comparison were ever wrong.
                self.changed_since_publish = false;
                self.publish_count = self.publish_count.saturating_add(1);
                ControllerReply::Ack
            }
            Command::NewPlan { name } => match valid_plan_name(name) {
                Some(name) => {
                    self.install_plan(ServicePlan::new(name));
                    ControllerReply::Ack
                }
                None => ControllerReply::Deny(DenyReason::BadRequest),
            },
            Command::TemplatePlan { template, name } => {
                let Some(name) = valid_plan_name(name) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                // An unknown template is refused, never silently downgraded to a blank plan: a
                // coordinator who asked for "Sunday Morning" and silently received an empty run
                // sheet has been told nothing about what went wrong.
                let Some(template) = selahcue_core::plan::plan_template(template) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                self.install_plan(template.build(name));
                ControllerReply::Ack
            }
            Command::DuplicatePlan { name } => match valid_plan_name(name) {
                Some(name) => {
                    // Duplicates the plan that is LOADED (FR-005) — the wire caller
                    // `ServicePlan::duplicate` never had. Not a library copy: this host keeps
                    // exactly one plan row and this crate cannot reach the data layer.
                    let copy = self.plan.duplicate(name);
                    self.install_plan(copy);
                    ControllerReply::Ack
                }
                None => ControllerReply::Deny(DenyReason::BadRequest),
            },
            Command::ImportPlan { name, items } => self.import_plan(name, items),

            // Remote Control device management is handled at the transport/session layer
            // (server.rs, which owns the SessionRegistry), NOT the operational controller — the
            // server intercepts these before the handler, so this arm is a defensive fallback
            // that never runs in practice (it only keeps the match exhaustive).
            Command::ListRemoteDevices
            | Command::ApprovePairing { .. }
            | Command::DenyPairing { .. }
            | Command::RevokeSession { .. }
            | Command::SetSessionRole { .. }
            | Command::NewPairingCode => ControllerReply::Deny(DenyReason::BadRequest),
        };
        // Record the undo entry only for a real, applied plan edit (see `plan_before` above).
        // Bounded by MAX_PLAN_UNDO — the oldest snapshot is dropped rather than growing forever.
        if let Some(before) = plan_before {
            if matches!(reply, ControllerReply::Ack) && self.plan != before {
                self.plan_undo.push(before);
                if self.plan_undo.len() > MAX_PLAN_UNDO {
                    self.plan_undo.remove(0);
                }
                self.plan_redo.clear();
                // The publish badge's revision is bumped HERE, inside the block that already
                // decides "an edit was applied AND the document actually changed" (FR-006).
                // Deriving it from a second predicate elsewhere is how a badge and an undo
                // history come to disagree about whether the plan moved; there is one predicate
                // and both consume it. A denied or no-op edit reaches neither.
                self.plan_revision = self.plan_revision.saturating_add(1);
                self.refresh_published_delta();
            }
        }
        reply
    }

    /// Whether `command` is a plan-EDITING command whose effect participates in the Service-Plan
    /// undo/redo history (plan-editing · undo/redo). Exactly the commands that mutate the plan
    /// document; transport (`Next`/`GoLive`/`Stage*`), timer, theme-library, and screen commands
    /// are deliberately absent — undo must ignore them.
    fn is_plan_edit(command: &Command) -> bool {
        matches!(
            command,
            Command::AddItem { .. }
                | Command::RemoveItem { .. }
                | Command::MoveItem { .. }
                | Command::RenameItem { .. }
                | Command::SetItemTheme { .. }
                | Command::SetItemContent { .. }
                | Command::SetItemOwner { .. }
                | Command::SetItemDuration { .. }
                // Replacing the plan wholesale is the largest plan edit there is, so it takes an
                // undo snapshot like any other — an import or a mistaken "new plan" is exactly
                // the edit an operator most needs to take back.
                //
                // `PublishPlan` is absent because it edits nothing, but do not mistake this for
                // what keeps a publish from raising its own badge. It is NOT load-bearing:
                // listing `PublishPlan` here changes no observable behaviour, because the block
                // that consumes this predicate also requires `self.plan != before`, and
                // publishing leaves the plan identical. Verified by mutation — adding it here
                // leaves the whole `selahcue-app` suite green. What it saves is a pointless
                // plan-sized clone on every publish; what actually holds the badge down is the
                // document comparison in `refresh_published_delta`.
                | Command::NewPlan { .. }
                | Command::TemplatePlan { .. }
                | Command::DuplicatePlan { .. }
                | Command::ImportPlan { .. }
        )
    }

    /// Undo the last Service-Plan edit (plan-editing · undo/redo): restore the previous plan
    /// document, banking the current plan onto the redo stack. A no-op on an empty history.
    ///
    /// INVARIANT: this restores the plan DOCUMENT only and NEVER changes what is on the Live
    /// audience output — the presenter keeps its already-rendered Live slide (FR-012 spirit;
    /// NFR-024 never-blank). Only the plan-index bookkeeping is reconciled against the restored
    /// plan (see [`reconcile_plan_cursors`](Self::reconcile_plan_cursors)). Bounded by
    /// [`MAX_PLAN_UNDO`].
    pub fn undo_plan(&mut self) {
        if let Some(prev) = self.plan_undo.pop() {
            self.plan_redo.push(std::mem::replace(&mut self.plan, prev));
            if self.plan_redo.len() > MAX_PLAN_UNDO {
                self.plan_redo.remove(0);
            }
            self.after_plan_swap();
        }
    }

    /// Redo the last undone Service-Plan edit (the inverse of [`undo_plan`](Self::undo_plan)):
    /// restore the next plan document, banking the current plan back onto the undo stack. A no-op
    /// on an empty redo stack. Same Live-integrity invariant as `undo_plan`. Bounded by
    /// [`MAX_PLAN_UNDO`].
    pub fn redo_plan(&mut self) {
        if let Some(next) = self.plan_redo.pop() {
            self.plan_undo.push(std::mem::replace(&mut self.plan, next));
            if self.plan_undo.len() > MAX_PLAN_UNDO {
                self.plan_undo.remove(0);
            }
            self.after_plan_swap();
        }
    }

    /// Shared bookkeeping after an undo/redo swaps in a different plan document: reconcile the
    /// cursors against it and mark the plan (persist) + stage (confidence-monitor) dirty. The
    /// Live output is untouched here — the presenter keeps its rendered slide.
    fn after_plan_swap(&mut self) {
        self.reconcile_after_plan_change();
        // Undo and redo move the plan document without passing through `apply`, so they never
        // reach the revision bump in the undo-record block and need their own. A plan restored
        // by undo is not the plan that was published, and a badge that ignored undo would tell
        // the operator the two still matched.
        self.plan_revision = self.plan_revision.saturating_add(1);
        self.refresh_published_delta();
    }

    /// Re-answer "does the plan differ from what was published?".
    ///
    /// Called from the two places the document can move — an applied edit in `apply`, and an
    /// undo/redo swap — and nowhere else. Uses the domain's own `PartialEq` rather than a
    /// hand-picked subset of fields: a subset would silently stop covering a field the moment
    /// `ServicePlan` grows one.
    ///
    /// That equality includes the internal id counter, so add-then-remove leaves the plan
    /// marked changed even though the visible run sheet matches. That is the safe direction and
    /// the only one available without inventing a second definition of what a plan is: this can
    /// show a badge that turns out to be uninteresting, never hide a real edit.
    fn refresh_published_delta(&mut self) {
        self.changed_since_publish = self
            .published_plan
            .as_ref()
            .is_some_and(|baseline| *baseline != self.plan);
    }

    /// The bookkeeping every plan-document change shares: re-point the cursors at the new
    /// document and mark it for persistence and a stage recompose.
    ///
    /// Split out of [`after_plan_swap`](Self::after_plan_swap) so that the wholesale-replacement
    /// commands can share the reconciliation WITHOUT sharing its revision bump — they go through
    /// `apply` and are counted there, and calling `after_plan_swap` would count them twice.
    fn reconcile_after_plan_change(&mut self) {
        self.reconcile_plan_cursors();
        self.plan_dirty = true;
        self.stage_dirty = true;
    }

    /// Clamp the live/preview/navigation cursors to the (just-restored) plan so no index points
    /// past the end and each within-item slide position fits its item — the same invariants
    /// `RemoveItem` reconciles after a plan change. An index that no longer exists becomes `None`;
    /// a slide position is clamped to its item's `slide_count()`. Never touches the Live output.
    fn reconcile_plan_cursors(&mut self) {
        let len = self.plan.len();
        let in_range = |v: Option<usize>| v.filter(|i| *i < len);
        self.live_idx = in_range(self.live_idx);
        self.staged_idx = in_range(self.staged_idx);
        self.plan_cursor = in_range(self.plan_cursor);
        // Clamp each slide position to its item's slide count (a shrunk item must not leave a
        // stale over-range position). A cursor with no item keeps its position untouched.
        let clamp_slide = |plan: &ServicePlan, idx: Option<usize>, slide: usize| -> usize {
            match idx {
                Some(i) => slide.min(plan.items()[i].slide_count().saturating_sub(1)),
                None => slide,
            }
        };
        self.live_slide = clamp_slide(&self.plan, self.live_idx, self.live_slide);
        self.staged_slide = clamp_slide(&self.plan, self.staged_idx, self.staged_slide);
        self.cursor_slide = clamp_slide(&self.plan, self.plan_cursor, self.cursor_slide);
    }

    /// Set (or clear, with `None`) a plan item's per-item theme override (S8-3d). An
    /// unknown item id or an unknown built-in name is rejected; content is never touched.
    /// If the item is currently staged and/or live, its surface re-renders immediately.
    fn set_item_theme(&mut self, item_id: u64, theme: Option<String>) -> ControllerReply {
        let Some(idx) = self.index_of(item_id) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        // A set (not a clear) must name a known theme — a built-in or a saved-library
        // theme (86ajq69ft). A stale reference is later re-synced on library change.
        let override_theme = match theme.as_deref() {
            Some(name) => match self.resolve_theme(name) {
                Some(t) => Some(t),
                None => return ControllerReply::Deny(DenyReason::BadRequest),
            },
            None => None,
        };
        let _ = self.plan.set_item_theme(ItemId(item_id), theme);
        // The override lives ONLY in the plan (not the session snapshot), so mark the
        // plan dirty — otherwise the desktop never persists it and it is lost on restart.
        self.plan_dirty = true;
        // Reflect on the live surface in place; re-stage to reflect on preview.
        if self.live_idx == Some(idx) {
            self.presenter.set_live_theme(override_theme);
            self.presenter.blackout(self.blackout);
        }
        if self.staged_idx == Some(idx) {
            self.stage_slide(idx, self.staged_slide);
        }
        ControllerReply::Ack
    }

    /// Set (or clear, with a `None` link) a plan item's linked content — the scripture
    /// passage, deck, or media it shows (ADR-0020 follow-up · plan editing). An unknown
    /// item id, a malformed link (unknown kind / blank scripture reference / missing
    /// deck-media id), or a scripture reference that does not parse is rejected with the
    /// plan unchanged. Editing the plan never touches Live; if the edited item is the one
    /// staged in Preview, it is re-staged so a newly linked scripture resolves at once.
    fn set_item_content(
        &mut self,
        item_id: u64,
        link: &Option<ContentLinkView>,
    ) -> ControllerReply {
        let Some(idx) = self.index_of(item_id) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        let content = match link {
            None => None,
            Some(l) => {
                let Some(c) = item_content_from_link(l) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                // A scripture link must reference a passage that parses (FR-026) —
                // reject an unparseable ref rather than store a dangling link.
                if let selahcue_core::plan::ItemContent::Scripture { reference, .. } = &c {
                    if selahcue_core::scripture::parse_one(reference).is_err() {
                        return ControllerReply::Deny(DenyReason::BadRequest);
                    }
                }
                Some(c)
            }
        };
        // Propagated, not dropped: a divider refuses a content link, and silently acking a
        // refused edit would leave the operator believing the link had been made.
        if self
            .plan
            .set_item_content(ItemId(item_id), content)
            .is_err()
        {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        // The link lives ONLY in the plan (not the session snapshot), so mark the plan
        // dirty — otherwise the desktop never persists it and it is lost on restart.
        self.plan_dirty = true;
        // Re-stage in place so a newly linked scripture resolves into Preview (never Live).
        if self.staged_idx == Some(idx) {
            self.stage_slide(idx, self.staged_slide);
        }
        ControllerReply::Ack
    }

    /// Set (or clear, with `None`) a plan item's responsible owner/role (FR-004 · plan editing).
    /// A blank owner clears it (domain-normalized); an unknown item id is rejected with the plan
    /// unchanged. Plan metadata only — never touches the Live output or the staged slide.
    fn set_item_owner(&mut self, item_id: u64, owner: Option<String>) -> ControllerReply {
        if self.plan.set_item_owner(ItemId(item_id), owner).is_err() {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        self.plan_dirty = true;
        ControllerReply::Ack
    }

    /// Set (or clear, with `None`) a plan item's planned duration in seconds (FR-004 · plan
    /// editing). An unknown item id is rejected with the plan unchanged. Plan metadata only —
    /// never touches the Live output or the staged slide.
    fn set_item_duration(&mut self, item_id: u64, secs: Option<u32>) -> ControllerReply {
        if self
            .plan
            .set_item_planned_secs(ItemId(item_id), secs)
            .is_err()
        {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        self.plan_dirty = true;
        ControllerReply::Ack
    }

    /// Install a wholesale-replaced plan document (New / Template / Duplicate / Import).
    ///
    /// # The live output is never changed
    ///
    /// Replacing the plan is a document edit, and edits never change Live (FR-012); a
    /// coordinator starting next week's run sheet must not blank the service that is currently
    /// running (NFR-024). Whatever is on air keeps airing: a live PLAN ITEM is carried over as a
    /// free live slide, by exactly the mechanism `RemoveItem` already uses for the same reason.
    /// A live SCRIPTURE needs nothing — it is tracked by reference, not by plan index.
    ///
    /// # Why the indices are dropped rather than clamped
    ///
    /// [`reconcile_plan_cursors`](Self::reconcile_plan_cursors) clamps an index into range,
    /// which is right for undo (the two plans are versions of one document) and wrong here (the
    /// incoming plan has no relationship to the outgoing one). A clamped `live_index` would
    /// point at whichever unrelated row now occupies that position, and the view would report an
    /// item as LIVE that the audience has never seen. Reporting a false Live row is worse than
    /// reporting none, so every cursor is dropped.
    fn install_plan(&mut self, next: ServicePlan) {
        // Replacing the plan with an IDENTICAL one changes nothing, so it must do nothing.
        //
        // This is reachable: "Duplicate" with the pre-filled name left alone produces a plan
        // equal to the current one in every field. Without this guard the cursor reset below
        // would still run — dropping the LIVE row marking and clearing Preview — while the
        // post-dispatch block in `apply` skipped the undo snapshot, because that block asks
        // `self.plan != before` and the plan did not change. The operator would lose the live
        // marking with no undo entry to take it back.
        //
        // Returning early keeps the two in step: no document change, no cursor churn, no undo
        // entry, no revision bump, and the run sheet keeps saying which row is on air.
        if next == self.plan {
            return;
        }
        if self.live_idx.is_some() {
            // Read the composed slide BEFORE the plan goes away — it is the only remaining
            // record of what the audience is looking at.
            if let Some(slide) = self.presenter.live_slide() {
                self.live_free_text = Some(slide.title.clone());
                self.live_free_body = slide.body.clone();
            }
        }
        self.live_idx = None;
        self.staged_idx = None;
        self.plan_cursor = None;
        self.live_slide = 0;
        self.staged_slide = 0;
        self.cursor_slide = 0;
        self.plan = next;
        // Preview held a row of the outgoing plan; that row is gone. A staged SCRIPTURE is not
        // a plan row and survives, so it is checked first — same condition as `RemoveItem`.
        if self.staged_scripture.is_none() {
            self.presenter.clear_preview();
        }
        self.reconcile_after_plan_change();
    }

    /// Replace the plan with an imported run sheet, or refuse the import whole.
    ///
    /// Validates every row and builds the plan into a LOCAL value, installing it only once the
    /// last row has been accepted. A prefix-applied import is worse than a refused one: the
    /// coordinator is left with a partial run sheet and nothing tells them where it stopped.
    fn import_plan(&mut self, name: &str, items: &[ImportItemView]) -> ControllerReply {
        let Some(name) = valid_plan_name(name) else {
            return ControllerReply::Deny(DenyReason::BadRequest);
        };
        // Bound the untrusted ingress at the cap the domain documents (no-leak): an import is
        // the only path that can create hundreds of items in one frame, and each of those items
        // is also snapshotted onto the bounded undo stack.
        if items.len() > selahcue_core::plan::MAX_PLAN_ITEMS {
            return ControllerReply::Deny(DenyReason::BadRequest);
        }
        let mut built = ServicePlan::new(name);
        for item in items {
            let Some(kind) = selahcue_core::plan::ItemKind::from_tag(&item.kind) else {
                return ControllerReply::Deny(DenyReason::BadRequest);
            };
            // Titles get the plan-name rule: non-blank, bounded, no control characters. Bounding
            // matters most here — 500 rows of unbounded title is unbounded memory.
            let Some(title) = valid_plan_name(&item.title) else {
                return ControllerReply::Deny(DenyReason::BadRequest);
            };
            let id = built.add_item(kind, title);
            if let Some(owner) = item.owner.as_deref() {
                // Present-but-invalid is refused rather than dropped. A client that wants no
                // owner omits the field; one that sent a blank or hostile string made a mistake
                // worth reporting. The domain also refuses an owner on a `section` divider
                // (`PlanError::NotApplicable`), which surfaces here as a rejected import rather
                // than a silently unstaffed row.
                let Some(owner) = valid_plan_name(owner) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                if built.set_item_owner(id, Some(owner.to_string())).is_err() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
            }
            if let Some(secs) = item.planned_secs {
                // Likewise refused on a divider — an inert label is not schedulable.
                if built.set_item_planned_secs(id, Some(secs)).is_err() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
            }
        }
        self.install_plan(built);
        ControllerReply::Ack
    }

    /// The plan's publish / hand-off state for the operator view (FR-006).
    ///
    /// `changed` reports whether the plan DIFFERS from the published baseline, not merely
    /// whether it has been touched since. It is `false` whenever the plan has never been
    /// published — with no baseline there is no comparison to report, and a badge there would
    /// describe a review that was never possible — and it is `false` again once an edit is
    /// undone back to the published document.
    ///
    /// `revision` and `published_revision` can therefore differ while `changed` is `false`.
    /// That is not a contradiction: the revisions say the document was TOUCHED, `changed` says
    /// whether it actually DIFFERS, and only the second is worth an operator's attention
    /// mid-service.
    pub fn publish_state(&self) -> PublishStateView {
        PublishStateView {
            revision: self.plan_revision,
            published_revision: self.published_revision,
            version: self.publish_count,
            changed: self.changed_since_publish,
        }
    }

    /// The current index of a plan item id, if present.
    fn index_of(&self, item_id: u64) -> Option<usize> {
        self.plan.items().iter().position(|it| it.id.0 == item_id)
    }
}

/// The trimmed form of a wire-supplied plan name / item title / owner, or `None` when it is not
/// acceptable ([`selahcue_core::plan::plan_name_valid`]: non-blank, bounded, no control chars).
///
/// One helper for all three because they are the same kind of value — a short single-line label
/// that a coordinator types and later searches for — and giving them one rule means a reviewer
/// checks one predicate instead of three that drift apart.
fn valid_plan_name(name: &str) -> Option<&str> {
    selahcue_core::plan::plan_name_valid(name).then(|| name.trim())
}

/// Build a [`ControlServer`](selahcue_lan::ControlServer) handler that drives a
/// shared [`LiveController`]. RBAC is already enforced by the server before the
/// handler runs.
#[cfg(feature = "server")]
pub fn handler_for(
    controller: std::sync::Arc<std::sync::Mutex<LiveController>>,
) -> selahcue_lan::server::Handler {
    use selahcue_lan::protocol::ViewerView;
    use selahcue_lan::server::Reply;
    std::sync::Arc::new(move |role, command| match controller.lock() {
        Ok(mut controller) => match controller.apply(command) {
            ControllerReply::Ack => Reply::Ack,
            ControllerReply::Deny(reason) => Reply::Deny(reason),
            ControllerReply::Message(mut message) => {
                // Stamp the AUTHENTICATED role onto the operator view (FR-006 view-only).
                //
                // This is the only layer that can: the controller holds the plan but not the
                // session, and the server holds the session but not the view. `role` is the
                // role the server just ran `authorize()` against to let this very command
                // through, and `ViewerView::for_role` asks that same choke point what it
                // permits — so what the client renders and what the host enforces are one
                // policy read twice, never two policies kept in step by hand.
                if let ServerMessage::OperatorState { view } = &mut message {
                    view.viewer = Some(ViewerView::for_role(role));
                }
                Reply::Message(Box::new(message))
            }
        },
        Err(_) => Reply::Message(Box::new(ServerMessage::Error {
            message: "controller unavailable".into(),
        })),
    })
}

#[cfg(test)]
mod plan_undo_tests {
    //! Service-Plan undo/redo (86 plan-editing · undo/redo). White-box: the bounded-history
    //! and no-phantom invariants read the private `plan_undo`/`plan_redo` stacks directly,
    //! mirroring the deck workspace's proven undo tests. Undo restores the plan DOCUMENT only
    //! and never changes the Live audience output (FR-012).
    use super::*;
    use selahcue_core::plan::ItemKind;

    fn fresh() -> LiveController {
        LiveController::new(ServicePlan::new("Test"), 320, 180, Theme::dark())
    }

    fn add(c: &mut LiveController, title: &str) {
        assert_eq!(
            c.apply(&Command::AddItem {
                kind: ItemKind::Song.as_tag().into(),
                title: title.into(),
                content: None,
            }),
            ControllerReply::Ack
        );
    }

    #[test]
    fn undo_and_redo_restore_the_plan_document() {
        let mut c = fresh();
        add(&mut c, "One");
        add(&mut c, "Two");
        add(&mut c, "Three");
        assert_eq!(c.plan().len(), 3);
        c.undo_plan();
        c.undo_plan();
        assert_eq!(c.plan().len(), 1, "two undos peel back to a single item");
        c.redo_plan();
        assert_eq!(c.plan().len(), 2, "redo restores the second add");
        c.redo_plan();
        assert_eq!(c.plan().len(), 3, "redo restores the third add");
    }

    #[test]
    fn plan_undo_history_is_bounded_and_recovers_at_least_twenty_steps() {
        // No-leak: many edits never grow the undo stack past MAX_PLAN_UNDO, and >=20 steps are
        // recoverable. A starting item keeps the plan non-empty so undo never underflows.
        let mut c = fresh();
        add(&mut c, "Base");
        let base = c.plan().len();
        for i in 0..(MAX_PLAN_UNDO + 40) {
            add(&mut c, &format!("Item {i}"));
        }
        assert!(
            c.plan_undo.len() <= MAX_PLAN_UNDO,
            "undo stack stays bounded (no unbounded growth)"
        );
        let before = c.plan().len();
        for _ in 0..20 {
            c.undo_plan();
        }
        assert_eq!(
            c.plan().len(),
            before - 20,
            ">=20 undo steps are recoverable"
        );
        assert!(
            c.plan().len() >= base,
            "undo never goes below the starting plan"
        );
    }

    #[test]
    fn a_denied_plan_edit_never_pushes_a_phantom_undo_or_wipes_redo() {
        // A denied/no-op edit must record NOTHING — no phantom undo entry, redo preserved.
        let mut c = fresh();
        add(&mut c, "One"); // one real edit
        c.undo_plan(); // now redo carries one entry
        assert!(!c.plan_redo.is_empty(), "precondition: redo is populated");
        let undo_before = c.plan_undo.len();
        // RemoveItem on an unknown id is denied — it must not touch the history.
        assert_eq!(
            c.apply(&Command::RemoveItem { item_id: 999_999 }),
            ControllerReply::Deny(DenyReason::BadRequest)
        );
        assert_eq!(
            c.plan_undo.len(),
            undo_before,
            "a denied edit records no undo entry"
        );
        assert!(
            !c.plan_redo.is_empty(),
            "a denied edit never wipes the redo stack"
        );
    }

    #[test]
    fn undo_of_an_unrelated_edit_leaves_live_output_and_cursors_valid() {
        // Live-integrity: with an item live, undoing an UNRELATED plan edit restores the plan
        // DOCUMENT but never changes the rendered Live output (FR-012 / NFR-024).
        let mut c = fresh();
        add(&mut c, "One");
        add(&mut c, "Two");
        let id_one = c.plan().items()[0].id.0;
        c.apply(&Command::SelectItem { item_id: id_one });
        c.apply(&Command::GoLive);
        assert_eq!(c.live_index(), Some(0));
        let live_before = c.presenter().live_output().bytes().to_vec();
        // An unrelated edit (append a third item), then undo it.
        add(&mut c, "Three");
        assert_eq!(c.plan().len(), 3);
        c.undo_plan();
        assert_eq!(c.plan().len(), 2, "undo removes the unrelated add");
        assert_eq!(
            c.presenter().live_output().bytes(),
            live_before.as_slice(),
            "undo never changes the Live audience output"
        );
        assert_eq!(c.live_index(), Some(0), "the live cursor stays valid");
        // Every surviving cursor is in range for the restored plan (no panic / no overflow).
        let len = c.plan().len();
        assert!(c.live_index().is_none_or(|i| i < len));
        assert!(c.staged_index().is_none_or(|i| i < len));
    }

    #[test]
    fn undo_and_redo_on_a_fresh_controller_are_safe_noops() {
        let mut c = fresh();
        c.undo_plan();
        c.redo_plan();
        assert_eq!(c.plan().len(), 0);
        assert!(c.plan_undo.is_empty());
        assert!(c.plan_redo.is_empty());
    }
}
