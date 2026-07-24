//! The live controller: maps RBAC-checked control commands onto the presenter and
//! service plan, so a remote controller drives the audience output.
//!
//! Preview/live separation is preserved (FR-012): navigation (`Next`/`Previous`/
//! `SelectItem`) stages the item in **Preview**; only `GoLive` commits it to the
//! **Live** output. `Clear`/`Blackout` act on Live.

use crate::operator::{ItemView, OperatorView};
use selahcue_core::plan::ServicePlan;
use selahcue_core::scripture;
use selahcue_core::timer::Timer;
use selahcue_lan::protocol::{
    Command, DenyReason, DisplayView, OutputStatusView, ServerMessage, TimerSnapshot,
};
use selahcue_present::{FrameBuffer, Presenter, Slide, StageDisplay, StageTheme, Theme, TimerView};
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
    /// Set by plan-edit commands; the host persists the plan when it sees this.
    plan_dirty: bool,
    /// The scripture reference staged in Preview, if Preview holds one (non-plan slide).
    staged_scripture: Option<String>,
    /// The scripture reference on the Live output, if Live shows one (verse text
    /// recomposes from the bundled translation on restore).
    live_scripture: Option<String>,
    /// The title of a removed-but-still-on-screen plan item (a free slide) —
    /// restored VERBATIM as a title-only slide, never recomposed as scripture
    /// even when the title happens to parse as a reference (review 7y-B).
    live_free_text: Option<String>,
}

/// How long the identify overlay stays on the outputs once triggered (FR-040).
pub const IDENTIFY_TTL: Duration = Duration::from_secs(5);

/// Maximum verse-text lines on a scripture slide INCLUDING the ellipsis marker.
/// The compositor renders at most 7 text lines per frame (title + 6 body:
/// line height 10% + gap 3% inside the 5% safe margin — pinned by the
/// `compose_slide_renders_title_plus_six_body_lines` test in selahcue-present),
/// so longer passages truncate to 5 verse lines + "…" (pagination is a later
/// slice).
const SCRIPTURE_MAX_LINES: usize = 6;
/// Word-wrap budget per rendered line (the compositor does not wrap).
const SCRIPTURE_WRAP_COLS: usize = 42;

/// Compose the slide for a scripture reference: the parsed reference as the
/// title and the bundled translation's verse text as wrapped body lines
/// (FR-025/story 86ajpew05). Falls back to a title-only slide when the text is
/// not a resolvable reference (e.g. the free-slide recovery path).
fn scripture_slide(reference: &str) -> Slide {
    scripture_slide_in(selahcue_scripture::Translation::default(), reference)
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
    let mut lines: Vec<String> = Vec::new();
    for v in &verses {
        let text = if multi {
            format!("{} {}", v.verse, v.text)
        } else {
            v.text.clone()
        };
        lines.extend(wrap_words(&text, SCRIPTURE_WRAP_COLS));
        if lines.len() > SCRIPTURE_MAX_LINES {
            break;
        }
    }
    if lines.len() > SCRIPTURE_MAX_LINES {
        lines.truncate(SCRIPTURE_MAX_LINES - 1);
        lines.push("…".to_string());
    }
    Slide::new(format!("{parsed} ({})", t.code()), lines)
}

/// Greedy word wrap (the raster layer renders one text layer per line).
fn wrap_words(text: &str, cols: usize) -> Vec<String> {
    let mut lines = Vec::new();
    let mut current = String::new();
    for word in text.split_whitespace() {
        if !current.is_empty() && current.len() + 1 + word.len() > cols {
            lines.push(std::mem::take(&mut current));
        }
        if !current.is_empty() {
            current.push(' ');
        }
        current.push_str(word);
    }
    if !current.is_empty() {
        lines.push(current);
    }
    lines
}

impl LiveController {
    /// A controller for `plan`, rendering at `width×height` with `theme`. Both
    /// surfaces start blank.
    pub fn new(plan: ServicePlan, width: u32, height: u32, theme: Theme) -> Self {
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
            plan_dirty: false,
            staged_scripture: None,
            live_scripture: None,
            live_free_text: None,
        }
    }

    /// A persistable snapshot of the live session at `now` (injected clock, so the
    /// timer's elapsed is exact at the save instant).
    pub fn snapshot(&self, now: Instant) -> ControllerSnapshot {
        let (timer_total_secs, timer_elapsed_secs, timer_running) =
            match (&self.timer, self.timer_total) {
                (Some(timer), Some(total)) => (
                    Some(total.as_secs() as u32),
                    Some(timer.elapsed(now).as_secs() as u32),
                    timer.is_running() || self.timer_pending_start,
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
        }
    }

    /// Restore a persisted session onto this (freshly constructed) controller —
    /// the crash-recovery path. State is rebuilt through the same code paths the
    /// commands use, so the outputs re-render exactly. Indices that don't fit the
    /// current plan are ignored (defensive: a snapshot from a different plan must
    /// never panic or point past the end). A running countdown resumes from its
    /// persisted elapsed on the next [`tick`](Self::tick).
    pub fn restore(&mut self, snap: &ControllerSnapshot) {
        let len = self.plan.len();
        let ok = |v: Option<u32>| v.map(|i| i as usize).filter(|i| *i < len);

        // Rebuild LIVE first: a plan item by index, or a scripture by its reference.
        if let Some(live) = ok(snap.live_idx) {
            self.stage_index(live);
            if self.presenter.go_live() {
                self.live_idx = Some(live);
            }
        } else if let Some(reference) = snap.live_scripture.as_ref() {
            self.presenter.stage(scripture_slide(reference));
            if self.presenter.go_live() {
                self.live_idx = None;
                self.live_scripture = Some(reference.clone());
            }
        } else if let Some(text) = snap.live_free_text.as_ref() {
            // A removed item's slide: restore exactly what was on screen (a
            // title-only slide) — even if the title parses as a reference.
            self.presenter.stage(Slide::title(text.clone()));
            if self.presenter.go_live() {
                self.live_idx = None;
                self.live_free_text = Some(text.clone());
            }
        }
        // Then PREVIEW: a plan item, a scripture, or — explicitly — nothing (go_live
        // leaves its input in the staged slot, so an empty preview must be cleared or
        // the monitor would show a phantom "next" and a later GoLive would desync).
        if let Some(staged) = ok(snap.staged_idx) {
            self.stage_index(staged);
        } else if let Some(reference) = snap.staged_scripture.as_ref() {
            self.presenter.stage(scripture_slide(reference));
            self.staged_idx = None;
            self.staged_scripture = Some(reference.clone());
        } else {
            self.presenter.clear_preview();
            self.staged_idx = None;
        }
        self.plan_cursor = ok(snap.plan_cursor).or(self.plan_cursor);

        self.blackout = snap.blackout;
        self.presenter.blackout(snap.blackout);

        if let Some(total) = snap.timer_total_secs {
            let total = Duration::from_secs(u64::from(total));
            let elapsed = Duration::from_secs(u64::from(snap.timer_elapsed_secs.unwrap_or(0)));
            self.timer = Some(Timer::count_down(total).with_elapsed(elapsed));
            self.timer_total = Some(total);
            self.timer_pending_start = snap.timer_running;
            self.last_timer_view = None;
        }

        self.stage_dirty = true;
        self.state_dirty = false; // we just loaded this state — nothing new to save
    }

    /// Whether state changed since the last [`take_state_dirty`] (autosave signal).
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

        // Refresh the confidence monitor when the timer's displayed value changed or a
        // command marked it dirty — not every frame. While pairing mode is active the
        // stage output shows the invite QR instead of the speaker scene.
        let key = timer_key(view);
        if self.stage_dirty || key != self.last_stage_key {
            self.stage_dirty = false;
            self.last_stage_key = key;
            match &self.pairing_qr {
                Some((uri, _)) => {
                    if !self.stage.show_qr(uri) {
                        // Unencodable data: fall back to the normal scene rather than
                        // freezing a stale frame.
                        self.pairing_qr = None;
                        let current = self.presenter.live_slide().cloned();
                        let next = self.presenter.staged().cloned();
                        self.stage
                            .update(current.as_ref(), next.as_ref(), view.as_ref());
                    }
                }
                None => {
                    let current = self.presenter.live_slide().cloned();
                    let next = self.presenter.staged().cloned();
                    self.stage
                        .update(current.as_ref(), next.as_ref(), view.as_ref());
                }
            }
        }
    }

    /// The presenter (for the output window / stage display to render).
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

    /// A serializable snapshot for the operator UI: the plan with per-item Live/Preview
    /// flags, plus the current live/staged indices and blackout state.
    pub fn operator_view(&self) -> OperatorView {
        let items = self
            .plan
            .items()
            .iter()
            .enumerate()
            .map(|(i, item)| ItemView {
                id: item.id.0,
                kind: item.kind.as_tag().to_string(),
                title: item.title.clone(),
                is_live: self.live_idx == Some(i),
                is_staged: self.staged_idx == Some(i),
            })
            .collect();
        OperatorView {
            plan_name: self.plan.name.clone(),
            items,
            live_index: self.live_idx,
            staged_index: self.staged_idx,
            blackout: self.blackout,
            timer: self.last_timer_view.map(|v| TimerSnapshot {
                remaining_secs: v.remaining_secs,
                elapsed_secs: v.elapsed_secs,
                time_up: v.time_up,
                warn: v.warn,
                running: self.timer.as_ref().is_some_and(Timer::is_running),
            }),
            staged_scripture: self.staged_scripture.clone(),
            live_scripture: self.live_scripture.clone(),
            live_free_text: self.live_free_text.clone(),
            outputs: self.output_status.clone(),
            displays: self.display_status.clone(),
        }
    }

    fn slide_for(&self, idx: usize) -> Option<Slide> {
        self.plan
            .items()
            .get(idx)
            .map(|item| Slide::title(item.title.clone()))
    }

    /// Stage the plan item at `idx` in Preview (Live is untouched), advancing the
    /// navigation cursor to it.
    fn stage_index(&mut self, idx: usize) -> ControllerReply {
        match self.slide_for(idx) {
            Some(slide) => {
                self.presenter.stage(slide);
                self.staged_idx = Some(idx);
                self.plan_cursor = Some(idx);
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
            Command::GetState | Command::GetOperatorState | Command::ScriptureSearch { .. } => {}
            _ => self.state_dirty = true,
        }
        let len = self.plan.len();
        match command {
            Command::Next => {
                if len == 0 {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                // Resume from the plan cursor (unaffected by staging a scripture).
                let next = match self.plan_cursor {
                    Some(i) => (i + 1).min(len - 1),
                    None => 0,
                };
                self.stage_index(next)
            }
            Command::Previous => {
                if len == 0 {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                let prev = self.plan_cursor.map(|i| i.saturating_sub(1)).unwrap_or(0);
                self.stage_index(prev)
            }
            Command::SelectItem { item_id } => {
                match self.plan.items().iter().position(|it| it.id.0 == *item_id) {
                    Some(idx) => self.stage_index(idx),
                    None => ControllerReply::Deny(DenyReason::BadRequest),
                }
            }
            Command::GoLive => {
                // Commit whatever is staged (a plan item OR a staged scripture); the
                // presenter reports whether anything was staged.
                if self.presenter.go_live() {
                    self.live_idx = self.staged_idx; // None for a non-plan scripture
                    self.live_scripture = self.staged_scripture.clone();
                    self.live_free_text = None;
                    // Going live from blackout reveals the new content (UX-STATE-MATRIX).
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
                // Drop any prior view so the operator snapshot never mixes an old timer's
                // displayed value with the fresh timer's state before the next tick.
                self.last_timer_view = None;
                // The overlay appears on the next tick (which supplies the start instant).
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
                self.presenter.stage(scripture_slide_in(t, reference));
                self.staged_idx = None; // a scripture slide is not a plan index
                self.staged_scripture = Some(reference.clone());
                ControllerReply::Ack
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
            Command::AddItem { kind, title } => {
                let Some(kind) = selahcue_core::plan::ItemKind::from_tag(kind) else {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                };
                let title = title.trim();
                if title.is_empty() {
                    return ControllerReply::Deny(DenyReason::BadRequest);
                }
                self.plan.add_item(kind, title);
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
                    }
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
                        self.stage_index(idx);
                    }
                }
                ControllerReply::Ack
            }
        }
    }

    /// The current index of a plan item id, if present.
    fn index_of(&self, item_id: u64) -> Option<usize> {
        self.plan.items().iter().position(|it| it.id.0 == item_id)
    }
}

/// Build a [`ControlServer`](selahcue_lan::ControlServer) handler that drives a
/// shared [`LiveController`]. RBAC is already enforced by the server before the
/// handler runs.
#[cfg(feature = "server")]
pub fn handler_for(
    controller: std::sync::Arc<std::sync::Mutex<LiveController>>,
) -> selahcue_lan::server::Handler {
    use selahcue_lan::server::Reply;
    std::sync::Arc::new(move |_role, command| match controller.lock() {
        Ok(mut controller) => match controller.apply(command) {
            ControllerReply::Ack => Reply::Ack,
            ControllerReply::Deny(reason) => Reply::Deny(reason),
            ControllerReply::Message(message) => Reply::Message(Box::new(message)),
        },
        Err(_) => Reply::Message(Box::new(ServerMessage::Error {
            message: "controller unavailable".into(),
        })),
    })
}
