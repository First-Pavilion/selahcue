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
use selahcue_lan::protocol::{Command, DenyReason, ServerMessage, TimerSnapshot};
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
    /// Set by any state-changing command; the host's autosave loop consumes it via
    /// [`take_state_dirty`](Self::take_state_dirty).
    state_dirty: bool,
    /// Set by plan-edit commands; the host persists the plan when it sees this.
    plan_dirty: bool,
    /// The scripture reference staged in Preview, if Preview holds one (non-plan slide).
    staged_scripture: Option<String>,
    /// The text of a NON-PLAN slide on the Live output (a scripture reference, or a
    /// removed plan item whose slide deliberately stays on screen), if any — persisted
    /// so crash recovery restores what the audience actually sees.
    live_scripture: Option<String>,
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
            state_dirty: false,
            plan_dirty: false,
            staged_scripture: None,
            live_scripture: None,
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
            self.presenter.stage(Slide::title(reference.clone()));
            if self.presenter.go_live() {
                self.live_idx = None;
                self.live_scripture = Some(reference.clone());
            }
        }
        // Then PREVIEW: a plan item, a scripture, or — explicitly — nothing (go_live
        // leaves its input in the staged slot, so an empty preview must be cleared or
        // the monitor would show a phantom "next" and a later GoLive would desync).
        if let Some(staged) = ok(snap.staged_idx) {
            self.stage_index(staged);
        } else if let Some(reference) = snap.staged_scripture.as_ref() {
            self.presenter.stage(Slide::title(reference.clone()));
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
            Command::StopTimer => {
                self.timer = None;
                self.timer_total = None;
                self.timer_pending_start = false;
                self.last_timer_view = None;
                // `apply` marked the stage dirty; the next tick recomposes the monitor
                // without the timer. The audience output is untouched (no timer there).
                ControllerReply::Ack
            }
            Command::ScriptureSearch { query } => {
                let references = scripture::parse(query)
                    .iter()
                    .map(|r| r.to_string())
                    .collect();
                ControllerReply::Message(ServerMessage::ScriptureResults {
                    query: query.clone(),
                    references,
                })
            }
            Command::StageScripture { reference } => {
                self.presenter.stage(Slide::title(reference.clone()));
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
                // change Live). It is no longer a plan item, so track it as a free
                // live slide by its text — crash recovery then restores what is
                // actually on screen instead of a blank surface.
                if self.live_idx == Some(idx) {
                    if let Some(slide) = self.presenter.live_slide() {
                        self.live_scripture = Some(slide.title.clone());
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
            ControllerReply::Message(message) => Reply::Message(message),
        },
        Err(_) => Reply::Message(ServerMessage::Error {
            message: "controller unavailable".into(),
        }),
    })
}
