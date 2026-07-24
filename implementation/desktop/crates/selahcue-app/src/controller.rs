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

        // Refresh the confidence monitor when the timer's displayed value changed or a
        // command marked it dirty — not every frame.
        let key = timer_key(view);
        if self.stage_dirty || key != self.last_stage_key {
            self.stage_dirty = false;
            self.last_stage_key = key;
            let current = self.presenter.live_slide().cloned();
            let next = self.presenter.staged().cloned();
            self.stage
                .update(current.as_ref(), next.as_ref(), view.as_ref());
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
        }
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
