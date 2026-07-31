//! The live controller: maps RBAC-checked control commands onto the presenter and
//! service plan, so a remote controller drives the audience output.
//!
//! Preview/live separation is preserved (FR-012): navigation (`Next`/`Previous`/
//! `SelectItem`) stages the item in **Preview**; only `GoLive` commits it to the
//! **Live** output. `Clear`/`Blackout` act on Live.

use crate::operator::{ItemView, OperatorView};
use selahcue_core::plan::{ItemId, ServicePlan};
use selahcue_core::scripture;
use selahcue_core::timer::Timer;
use selahcue_lan::protocol::{
    Command, DenyReason, DisplayView, OutputStatusView, SavedThemeView, ScreenThemeView,
    ServerMessage, ThumbView, TimerSnapshot, VerseView,
};
use selahcue_present::{
    FrameBuffer, Presenter, Slide, StageDisplay, StageTheme, Theme, TimerView, MAX_ELEMENTS,
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
}

/// Upper bounds on the saved-theme library so it cannot grow without limit (no-leak):
/// a sane cap on the count and each name's length. Each theme's JSON is the canonical
/// fixed-size [`Theme`] (a few hundred bytes), so total storage is bounded.
pub const MAX_SAVED_THEMES: usize = 256;
pub const MAX_THEME_NAME_LEN: usize = 64;

/// The Audience-class SCREENS that carry their own per-screen theme (86ajq321k; Screens
/// design §3): the physical `main` projector plus the virtual `lower-third` / `stream`
/// feeds. A fixed, bounded set this batch (dynamic Add/Delete virtual screens is a
/// Screens-page follow-up); the `stage` confidence monitor is NOT here — it keeps its
/// stage layout, not an audience theme. The per-screen theme map is bounded to these ids.
pub const AUDIENCE_SCREENS: [&str; 3] = ["main", "lower-third", "stream"];

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

/// How long the identify overlay stays on the outputs once triggered (FR-040).
pub const IDENTIFY_TTL: Duration = Duration::from_secs(5);

/// Compose the slide for a scripture reference: the parsed reference as the
/// title and the bundled translation's verse text as wrapped body lines
/// (FR-025/story 86ajpew05). Falls back to a title-only slide when the text is
/// not a resolvable reference (e.g. the free-slide recovery path).
fn scripture_slide(reference: &str) -> Slide {
    scripture_slide_in(selahcue_scripture::Translation::default(), reference)
}

/// Compose the slide for one within-item position (story S8-1). A title-only
/// item (no stanzas) is its single title slide — the exact pre-8a shape. A song
/// stanza renders as the item title plus the stanza's wrapped lines, capped by
/// the same physical budget as scripture slides (pagination is a later slice).
fn item_slide(item: &selahcue_core::plan::PlanItem, slide: usize) -> Slide {
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
        }
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
        // theme JSON cannot grow the design without limit (no-leak).
        if theme.elements.len() > MAX_ELEMENTS {
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
        // Bound the element list (Canvas Editing, 86ajq6j2q) — no unbounded design growth.
        if theme.elements.len() > MAX_ELEMENTS {
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
                        .map(|t| t.elements.len() <= MAX_ELEMENTS)
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
        if !AUDIENCE_SCREENS.contains(&screen) {
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
        if !AUDIENCE_SCREENS.contains(&screen) {
            return None;
        }
        let out = self.presenter.live_output();
        if self.blackout {
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
        Some(self.presenter.compose_screen_live(theme.as_ref()))
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
        let saved = &self.saved_themes;
        self.screen_themes = themes
            .into_iter()
            .filter(|(screen, name)| {
                AUDIENCE_SCREENS.contains(&screen.as_str())
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
                        let next = self.stage_next_slide();
                        self.stage
                            .update(current.as_ref(), next.as_ref(), view.as_ref());
                    }
                }
                None => {
                    let current = self.presenter.live_slide().cloned();
                    let next = self.stage_next_slide();
                    self.stage
                        .update(current.as_ref(), next.as_ref(), view.as_ref());
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
        self.presenter.staged().cloned()
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
                theme: item.theme.clone(),
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
            translations: selahcue_scripture::Translation::ALL
                .iter()
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
            | Command::ScriptureSearch { .. }
            | Command::GetChapter { .. } => {}
            _ => self.state_dirty = true,
        }
        let len = self.plan.len();
        match command {
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
                let lv = self.presenter().live_output().thumbnail(mw, mh);
                ControllerReply::Message(ServerMessage::ConsoleThumbnails {
                    preview: Some(ThumbView::from_rgba(pv.width(), pv.height(), pv.bytes())),
                    live: Some(ThumbView::from_rgba(lv.width(), lv.height(), lv.bytes())),
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
            Command::SaveTheme { name, theme_json } => self.save_theme(name, theme_json),
            Command::DeleteTheme { name } => self.delete_theme(name),
            Command::SetScreenTheme { screen, name } => self.set_screen_theme(screen, name),
        }
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
