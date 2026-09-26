//! SelahCue desktop walking skeleton: a native output window that presents the
//! **live** output on the GPU, driven by a LAN control server.
//!
//! This is the render half of the walking skeleton (native window + Rust core) with
//! the control loop wired in: a shared [`LiveController`] is driven by **both** the
//! local keyboard **and** a remote controller connected over the pinned-TLS control
//! link, so a remote command (Next / Go Live / Blackout) changes what is on screen.
//! Slides are composited on the CPU (via `selahcue-present`) and blitted to a wgpu
//! surface. The Tauri operator shell is a subsequent batch.
//!
//! Local keys follow the canonical map (UX-CANONICAL §1, `selahcue_app::keymap`):
//! `Space`/`→` stage next · `←` previous · `Enter` Go Live · `B` blackout ·
//! `Esc Esc` clear all · `Backspace` clear staged — plus host-only `P` pairing QR
//! (devices are approved/denied from the operator console).
//!
//! Window lifecycle: for the BUILT-IN screens (`main`, `stage`), the registry's `enabled`
//! flag means **the OS window exists**. Toggling a screen off on the Screens page and
//! clicking that window's close button are the same action (`close_screen`), and toggling
//! it back on re-opens the window from the per-frame reconcile. Closing a window therefore
//! does NOT quit — this process owns the other window, the LAN server and the live state
//! paired controllers depend on. Quit with **Cmd-Q (macOS) / Ctrl-Q (elsewhere)**.

#![forbid(unsafe_code)]
// In release builds on Windows, run as a GUI app so no console window appears behind the
// audience output when the operator auto-launches this binary. No effect on other platforms or in
// debug builds (dev keeps the console banner). The endpoint file — not stdout — is how the operator
// discovers this window, so suppressing the console changes no behaviour.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod guard;
#[cfg(feature = "encryption")]
mod keys;
mod video_sink;

use selahcue_app::{
    handler_for, CanonicalAction, ControllerSnapshot, CrashDecision, KeyPress, Keymap,
    LiveController,
};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::session_repo::SessionState;
use selahcue_data::{
    autosave_repo, output_repo, plan_repo, saved_theme_repo, screen_config_repo, screen_repo,
    screen_theme_repo, sermon_note_repo, session_repo, transcript_repo, DataError, Database,
};
use selahcue_engine::raster::{Fit, FrameBuffer};
use selahcue_lan::protocol::{
    Command, DisplayView, LayerVisibility, OutputConfigView, OutputStatusView, PairingInvite,
    ScaleFit, MAX_FRAME_RATE, MIN_FRAME_RATE,
};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{generate_pairing_code, generate_token, ControlServer, Role, SelfSigned};
use selahcue_present::qr_modules;
use selahcue_present::{Fault, Theme};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, KeyEvent, StartCause, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key, NamedKey};
use winit::window::{Window, WindowId};

const OUTPUT_W: u32 = 1920;
const OUTPUT_H: u32 = 1080;
/// Target frame interval for the paced redraw loop (~60 Hz). Pacing with a deadline —
/// not only the Fifo present block — keeps the loop from busy-spinning when a window
/// cannot present (minimized / occluded / surface lost).
const FRAME: Duration = Duration::from_millis(16);
/// Validity window of a pairing offer (code + QR). Short-lived by design (FR-086).
const PAIRING_TTL: Duration = Duration::from_secs(120);
/// Minimum spacing between autosave writes (bounds disk I/O under command bursts).
const AUTOSAVE_MIN_INTERVAL: Duration = Duration::from_secs(1);
/// While a countdown runs, refresh its persisted elapsed at least this often — so a
/// crash loses at most this much timer progress.
const TIMER_AUTOSAVE_INTERVAL: Duration = Duration::from_secs(5);
/// Minimum spacing between autosave-SLOT captures (FR-005 "last-3"; 86ajy0hxg) — deliberately
/// much wider than [`AUTOSAVE_MIN_INTERVAL`], so the bounded 3-slot ring holds meaningfully
/// distinct restore points instead of three near-duplicates of the same instant under a burst
/// of commands.
const AUTOSAVE_SLOT_INTERVAL: Duration = Duration::from_secs(60);
/// After an NDI sender fails to construct, wait at least this long before retrying it — so a
/// persistent failure (feature-on) is a slow poll, not a per-frame native re-init storm.
const NDI_RETRY_BACKOFF: Duration = Duration::from_secs(5);

/// GUI-launch smoke watchdog (story 86ajpevzp): in `--smoke` mode, if the main
/// window has not presented a frame within this budget, exit non-zero so CI
/// catches a genuine launch failure instead of hanging. This runs in
/// `about_to_wait`, so it only covers a stall AFTER the event loop starts — a
/// hang INSIDE window/adapter creation (before the first `about_to_wait`) is
/// bounded by the CI job's `timeout-minutes` backstop instead.
const SMOKE_TIMEOUT: Duration = Duration::from_secs(30);

/// Whether the GUI-launch smoke mode was requested (`--smoke` argument or the
/// `SELAHCUE_SMOKE` env var set). Pure over its inputs so it is unit-testable.
fn smoke_mode_requested(mut args: impl Iterator<Item = String>, env_set: bool) -> bool {
    env_set || args.any(|a| a == "--smoke")
}

/// A monitor's raw identity facts, in a plain shape the key math can be tested on.
#[derive(Debug, Clone, PartialEq, Eq)]
struct MonitorFacts {
    name: Option<String>,
    width: u32,
    height: u32,
    x: i32,
    y: i32,
}

fn monitor_facts(m: &winit::monitor::MonitorHandle) -> MonitorFacts {
    let size = m.size();
    let pos = m.position();
    MonitorFacts {
        name: m.name(),
        width: size.width,
        height: size.height,
        x: pos.x,
        y: pos.y,
    }
}

/// Stable, collision-free monitor identities for assignment persistence:
/// `name|WxH`, with a `#n` ordinal appended for DUPLICATE name+size monitors
/// (the classic two-identical-projectors venue — macOS names same-model
/// monitors identically). Ordinals are ordered by desktop position (left-to-
/// right, top-to-bottom), not enumeration order, so OS re-enumeration across
/// boots does not swap them; physically swapping the cables of two identical
/// projectors is indistinguishable to software and needs re-assignment.
/// Returns one key per input, same order. Display NAMES get the same ordinal
/// suffix so the operator picker can tell duplicates apart.
fn display_keys(facts: &[MonitorFacts]) -> Vec<(String, String)> {
    let base = |f: &MonitorFacts, i: usize| {
        (
            f.name
                .clone()
                .unwrap_or_else(|| format!("Display {}", i + 1)),
            format!(
                "{}|{}x{}",
                f.name
                    .clone()
                    .unwrap_or_else(|| format!("Display {}", i + 1)),
                f.width,
                f.height
            ),
        )
    };
    // Position-ordered ordinal among same-key monitors.
    let mut order: Vec<usize> = (0..facts.len()).collect();
    order.sort_by_key(|&i| (facts[i].x, facts[i].y));
    let mut seen: Vec<(String, u32)> = Vec::new();
    let mut ordinal = vec![0u32; facts.len()];
    for &i in &order {
        let (_, key) = base(&facts[i], i);
        match seen.iter_mut().find(|(k, _)| *k == key) {
            Some((_, n)) => {
                *n += 1;
                ordinal[i] = *n;
            }
            None => seen.push((key, 0)),
        }
    }
    let dup: Vec<bool> = (0..facts.len())
        .map(|i| {
            let (_, key) = base(&facts[i], i);
            facts
                .iter()
                .enumerate()
                .filter(|(j, f)| base(f, *j).1 == key)
                .count()
                > 1
        })
        .collect();
    (0..facts.len())
        .map(|i| {
            let (name, key) = base(&facts[i], i);
            if dup[i] {
                (
                    format!("{name} #{}", ordinal[i] + 1),
                    format!("{key}#{}", ordinal[i] + 1),
                )
            } else {
                (name, key)
            }
        })
        .collect()
}

/// A BUILT-IN screen that owns a real OS window. Only `main` and `stage` are here:
/// VIRTUAL screens (`lower-third` / `stream`) never have a window — their `enabled`
/// flag gates NDI delivery instead (see [`reconcile_ndi`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum WindowRole {
    Main,
    Stage,
}

impl WindowRole {
    /// The registry screen id this window role is the physical output for.
    fn screen_id(self) -> &'static str {
        match self {
            WindowRole::Main => "main",
            WindowRole::Stage => "stage",
        }
    }

    fn title(self) -> &'static str {
        match self {
            WindowRole::Main => "SelahCue Output",
            WindowRole::Stage => "SelahCue Stage / Confidence",
        }
    }
}

/// The registry screen id → window role mapping. `None` for every VIRTUAL screen, so a
/// virtual feed can never produce a window action however it is toggled.
fn window_role_for_screen(id: &str) -> Option<WindowRole> {
    match id {
        "main" => Some(WindowRole::Main),
        "stage" => Some(WindowRole::Stage),
        _ => None,
    }
}

/// One window lifecycle action the reconcile decided on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum WindowAction {
    Open(WindowRole),
    Close(WindowRole),
}

/// Which built-in windows FAILED to be created this run — the retry suppressor, held
/// **only in memory**.
///
/// A window-server or GPU failure is environmental and usually transient, so it must never
/// be recorded in the screen registry: `Command::SetScreenEnabled` marks the registry dirty
/// and the autosave persists it, which would turn a one-off hiccup at launch into a durable
/// "this screen is off" that survives every later launch. Keeping the suppression here also
/// means it cannot silently fail to take effect the way a registry write can (a rejected
/// command, or a poisoned controller mutex, leaves `enabled` true and the reconcile
/// re-deciding `Open` every frame — a ~60 Hz window-creation storm).
///
/// Bounded by construction: one flag per built-in role, so it cannot grow.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
struct OpenFailures {
    main: bool,
    stage: bool,
}

impl OpenFailures {
    fn get(self, role: WindowRole) -> bool {
        match role {
            WindowRole::Main => self.main,
            WindowRole::Stage => self.stage,
        }
    }

    fn set(&mut self, role: WindowRole, failed: bool) {
        match role {
            WindowRole::Main => self.main = failed,
            WindowRole::Stage => self.stage = failed,
        }
    }
}

/// THE window-lifecycle decision, decided without a windowing system so it is unit-testable.
///
/// For a built-in screen, `enabled` means **the OS window exists** — so the toggle on
/// the Screens page and the window's own close button are the same action, resolved
/// here. Given each registry screen's `(id, enabled)` and whether each built-in window
/// currently exists, it returns the opens/closes that make reality match the registry.
///
/// `failed` is the in-memory record of roles whose window creation already failed this run.
/// A role in it is not re-opened, so a failing open costs ONE attempt rather than one per
/// frame; the flag is forgotten as soon as that screen is switched OFF, so switching it back
/// ON is a single deliberate retry — the operator's gesture, never a loop. This is why the
/// suppression is threaded through here instead of being expressed as a registry write.
///
/// Properties the tests pin: it is idempotent (no action when already in the desired
/// state), it drives both directions, a VIRTUAL screen never yields an action, and a failed
/// open is retried once per enable even when the registry still reports the screen enabled.
fn reconcile_windows<'a>(
    screens: impl IntoIterator<Item = (&'a str, bool)>,
    main_open: bool,
    stage_open: bool,
    failed: &mut OpenFailures,
) -> Vec<WindowAction> {
    // Empty in the steady state — `Vec::new` does not allocate until something is pushed,
    // so the per-frame reconcile costs nothing when nothing changed.
    let mut actions = Vec::new();
    for (id, enabled) in screens {
        // A virtual screen has no window; skipping it here is what makes rule 7 hold.
        let Some(role) = window_role_for_screen(id) else {
            continue;
        };
        let open = match role {
            WindowRole::Main => main_open,
            WindowRole::Stage => stage_open,
        };
        match (enabled, open) {
            // Enabled but absent: open it — unless opening it already failed this run, in
            // which case retrying now would just repeat the failure at frame rate.
            (true, false) => {
                if !failed.get(role) {
                    actions.push(WindowAction::Open(role));
                }
            }
            (false, true) => actions.push(WindowAction::Close(role)),
            // Already where it should be: no action (idempotence).
            (true, true) => {}
            // Switched OFF and already closed. This is the operator clearing the failure:
            // the screen is off, so the next switch-ON gets a fresh attempt.
            (false, false) => failed.set(role, false),
        }
    }
    actions
}

/// Whether the QUIT CHORD can still reach this process.
///
/// winit delivers `KeyboardInput` through `window_event` only — that is, only to a FOCUSED
/// WINDOW — and [`App`] implements no `device_event` and no `user_event`. So a running
/// process with no window has **no keyboard route out at all**: not the chord, not anything.
/// This fact is what makes closing the last window a quit rather than a screen edit.
fn quit_chord_reachable(main_open: bool, stage_open: bool) -> bool {
    main_open || stage_open
}

/// What a window's own close button must do.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CloseOutcome {
    /// Close just that screen and keep running. The process still owns the other window,
    /// the LAN server, and the presentation state paired mobile controllers depend on — and
    /// the remaining window can still receive the quit chord.
    CloseScreen,
    /// That was the LAST window: quit. Leaving the process running here would leave it
    /// unquittable (see [`quit_chord_reachable`]), with the banner promising a chord that
    /// nothing could deliver.
    Quit,
}

/// Resolve a close-button press. Derived from [`quit_chord_reachable`] rather than stated
/// separately, so the exit rule cannot drift from the reason for it.
fn close_button_outcome(main_open: bool, stage_open: bool, closing: WindowRole) -> CloseOutcome {
    let (main_after, stage_after) = match closing {
        WindowRole::Main => (false, stage_open),
        WindowRole::Stage => (main_open, false),
    };
    if quit_chord_reachable(main_after, stage_after) {
        CloseOutcome::CloseScreen
    } else {
        CloseOutcome::Quit
    }
}

/// Whether a key press is the explicit QUIT chord: **Cmd-Q on macOS, Ctrl-Q elsewhere**.
/// Closing a window no longer quits (it closes just that screen), so this is the only
/// keyboard way out of the output process. Pure over its inputs — including the platform
/// — so both platform behaviours are testable on one CI runner.
fn is_quit_chord(character: Option<&str>, super_key: bool, control_key: bool, macos: bool) -> bool {
    let modifier = if macos { super_key } else { control_key };
    modifier && character.is_some_and(|c| c.eq_ignore_ascii_case("q"))
}

/// Report a non-Ok disk status loudly (the storage guard is never silent).
/// Map the storage guard's verdict onto the operator-facing tag + figure.
///
/// `None` becomes `"unknown"`, NOT `"ok"`: the platform genuinely failing to report free space
/// is a third outcome, and calling it healthy would be a fabrication of exactly the kind this
/// work removes.
fn storage_tag(status: Option<guard::DiskStatus>) -> (&'static str, Option<u64>) {
    match status {
        None => ("unknown", None),
        Some(guard::DiskStatus::Ok { available }) => ("ok", Some(available)),
        Some(guard::DiskStatus::Low { available }) => ("low", Some(available)),
        Some(guard::DiskStatus::Critical { available }) => ("critical", Some(available)),
    }
}

fn report_disk(status: guard::DiskStatus) {
    match status {
        guard::DiskStatus::Ok { .. } => {}
        guard::DiskStatus::Low { available } => eprintln!(
            "SelahCue: LOW DISK at the data dir ({} MB free) — checkpoints continue, \
             but free space soon.",
            available / (1024 * 1024)
        ),
        guard::DiskStatus::Critical { available } => eprintln!(
            "SelahCue: DISK CRITICALLY FULL ({} MB free) — checkpoint writes are \
             PAUSED to protect the store; the live session continues in memory.",
            available / (1024 * 1024)
        ),
    }
}

/// One latch slot per [`Fault`] kind.
const FAULT_KINDS: usize = Fault::ALL.len();

/// Which host-produced NFR-024 faults have ALREADY been reported for the incident currently
/// in progress.
///
/// Every fault signal this host owns is a **level**, not an event: "the last present attempt
/// on the audience surface failed" and "the storage guard's verdict is below the floor" both
/// stay true for as long as the trouble lasts. The frame loop samples them ~60 times a
/// second. Reporting the level each time it is seen would drive `output_health.holds` up by
/// sixty every second — an unbounded, meaningless counter, and a live lie to the operator
/// about how many times the audience output was actually held. This latch turns each level
/// into an **edge**: the first frame of an incident reports, the rest do not, and the latch
/// clears when the condition clears so the *next* incident reports again.
///
/// Deliberately ONE `bool` per kind — never a queue, a log, a map, or a `Vec<FaultEvent>`.
/// A per-event container is exactly the unbounded growth `CLAUDE.md` forbids, and it would
/// grow fastest precisely when the host is in trouble. Boundedness here is a property of the
/// TYPE, so there is no cap for a later edit to raise.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
struct FaultLatch {
    reported: [bool; FAULT_KINDS],
}

/// The premises the latch rests on, pinned at COMPILE time so neither can be quietly
/// falsified — a runtime test cannot catch a change that makes itself vacuous.
///
/// Adding a `Fault` variant grows the array here *and* breaks [`fault_slot`]'s exhaustive
/// match, so latch coverage can never silently shrink to a subset of the kinds. Swapping the
/// array for any heap collection (the fault-log mistake above) adds at least a pointer plus a
/// length and breaks the size bound before a test ever runs.
const _: () = assert!(FAULT_KINDS == 4);
const _: () = assert!(std::mem::size_of::<FaultLatch>() <= 8);

/// The latch slot for a fault kind. Exhaustive on purpose: a new [`Fault`] variant must fail
/// to compile here rather than quietly share another kind's slot, which would let one
/// incident mute a different, unrelated one.
const fn fault_slot(fault: Fault) -> usize {
    match fault {
        Fault::GpuDeviceLost => 0,
        Fault::DecoderFault => 1,
        Fault::IpcStall => 2,
        Fault::DiskFull => 3,
    }
}

impl FaultLatch {
    /// Claim the right to report `fault`. Returns `true` exactly ONCE per incident: on the
    /// first call after the latch was clear, and never again until [`FaultLatch::clear`].
    fn claim(&mut self, fault: Fault) -> bool {
        let slot = &mut self.reported[fault_slot(fault)];
        !std::mem::replace(slot, true)
    }

    /// The condition ended — the next [`FaultLatch::claim`] for this kind reports again.
    fn clear(&mut self, fault: Fault) {
        self.reported[fault_slot(fault)] = false;
    }
}

/// Report `fault` to the shared controller on the EDGE into `active` — at most once per
/// incident (NFR-024; the host half of the never-blank seam).
///
/// `active` is the CURRENT level of the real condition, sampled by the caller every frame
/// ([`surface_fault_active`], [`disk_fault_active`]). Returns whether this call actually
/// reported, so a caller — and a test — can tell "reported now" from "already reported".
///
/// The controller lock is taken ONLY on the reporting edge, so a fault that lasts a whole
/// service costs one lock, not one per frame. A poisoned lock drops the report exactly the
/// way every other host path does (see [`drive`]), and the latch deliberately stays claimed
/// so the frame loop does not hammer a lock that is not going to recover.
fn report_fault_edge(
    latch: &mut FaultLatch,
    controller: &Mutex<LiveController>,
    fault: Fault,
    active: bool,
) -> bool {
    if !active {
        latch.clear(fault);
        return false;
    }
    if !latch.claim(fault) {
        return false;
    }
    match controller.lock() {
        Ok(mut c) => {
            c.report_fault(fault);
            true
        }
        Err(_) => false,
    }
}

/// Whether the AUDIENCE surface is currently in the wgpu-surface-loss fault (NFR-024).
///
/// True when the `main` window's last present ATTEMPT failed — `get_current_texture()`
/// returned a lost/outdated (or otherwise unusable) swapchain, so the audience could not be
/// given the frame the compositor produced. NFR-024 is a guarantee about the audience
/// output, so the stage/confidence monitor is deliberately not consulted: a held speaker
/// view is not a broadcast fault.
///
/// Two things that look like failures are not:
/// - an intentional frame-rate SKIP, which returns early from `present_output` *without*
///   recording, so `last_present_ok` keeps its previous value; and
/// - no `main` window at all (the screen is disabled), where nothing was attempted.
fn surface_fault_active(main: Option<&OutputTelemetry>) -> bool {
    main.is_some_and(|t| !t.last_present_ok)
}

/// Whether the storage guard's cached verdict is the full-disk fault (NFR-024).
///
/// Only [`guard::DiskStatus::Critical`] qualifies. A `Low` warning deliberately does NOT:
/// it means "free space soon", checkpoint writes continue, and reporting it would put
/// "OUTPUT HELD — disk full" on the console of every service whose drive is merely filling
/// up. `None` does not qualify either — a platform that cannot report free space has not
/// told us the disk is full, and calling that a fault is the same fabrication as
/// [`storage_tag`] mapping `None` onto `"ok"`, just in the alarming direction.
fn disk_fault_active(status: Option<guard::DiskStatus>) -> bool {
    matches!(status, Some(guard::DiskStatus::Critical { .. }))
}

/// The demo service plan used on a first run (no persisted session yet).
fn demo_plan() -> ServicePlan {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    plan.add_item(ItemKind::Song, "Closing Song");
    plan
}

/// Platform data directory for the session store (created if missing). Every
/// failure path reports itself — storage degradation must never be silent.
fn data_dir() -> Option<std::path::PathBuf> {
    // Windows resolves via APPDATA below and never reads HOME.
    #[cfg(not(target_os = "windows"))]
    let home = std::env::var_os("HOME").map(std::path::PathBuf::from);
    #[cfg(target_os = "macos")]
    let dir = home.map(|h| h.join("Library/Application Support/SelahCue"));
    #[cfg(target_os = "linux")]
    let dir = std::env::var_os("XDG_DATA_HOME")
        .map(std::path::PathBuf::from)
        // Per the XDG spec, an empty or relative XDG_DATA_HOME is treated as unset.
        .filter(|p| p.is_absolute())
        .or(home.map(|h| h.join(".local/share")))
        .map(|d| d.join("selahcue"));
    #[cfg(target_os = "windows")]
    let dir = std::env::var_os("APPDATA")
        .map(std::path::PathBuf::from)
        .map(|d| d.join("SelahCue"));
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    let dir: Option<std::path::PathBuf> = home.map(|h| h.join(".selahcue"));
    let Some(dir) = dir else {
        eprintln!("SelahCue: no data directory (HOME/APPDATA unset); running in-memory.");
        return None;
    };
    if let Err(e) = std::fs::create_dir_all(&dir) {
        eprintln!(
            "SelahCue: cannot create {} ({e}); running in-memory.",
            dir.display()
        );
        return None;
    }
    Some(dir)
}

/// Adapts `selahcue_data::transcript_repo` to `selahcue_app::TranscriptStoreWriter`
/// (86akcfftu). `selahcue-app` must not depend on `selahcue-data` (see `transcript_sink`'s
/// module docs there), so this binary — which already depends on both — is where the two
/// meet. Owns its own `Database` connection; see [`SessionStore::open_transcript_sink`] for
/// why that needs no lock shared with `SessionStore`'s own connection.
struct RealTranscriptStore {
    db: Database,
}

impl selahcue_app::TranscriptStoreWriter for RealTranscriptStore {
    fn open_transcript(
        &mut self,
        label: &str,
        provider: &str,
        started_at_ms: i64,
    ) -> Result<i64, String> {
        transcript_repo::create(
            &self.db,
            &transcript_repo::NewTranscript {
                label: label.to_string(),
                provider: provider.to_string(),
                plan_id: None,
                started_at_ms,
            },
        )
        .map_err(|e| e.to_string())
    }

    fn append_segment(
        &mut self,
        transcript_id: i64,
        start_ms: u64,
        end_ms: u64,
        text: &str,
    ) -> Result<i64, String> {
        transcript_repo::append_segment(&self.db, transcript_id, start_ms, end_ms, text)
            .map_err(|e| e.to_string())
    }

    fn end_transcript(&mut self, transcript_id: i64, ended_at_ms: i64) -> Result<(), String> {
        transcript_repo::end(&self.db, transcript_id, ended_at_ms).map_err(|e| e.to_string())
    }
}

/// Adapts `selahcue_data::sermon_note_repo` + `transcript_repo::most_recent_id` to
/// `selahcue_app::SermonNoteStore` (86akgqdv0; PR #33 review, Sana F1 remediation) — the exact
/// sibling of [`RealTranscriptStore`] just above, for the identical reason: `selahcue-app` must
/// not depend on `selahcue-data`, so this binary (which already depends on both) is where the
/// two meet. Owns its own `Database` connection, opened the SAME way `RealTranscriptStore`'s is
/// (see [`SessionStore::open_sermon_note_store`]).
struct RealSermonNoteStore {
    db: Database,
}

impl selahcue_app::SermonNoteStore for RealSermonNoteStore {
    fn active_transcript_id(&mut self) -> Result<Option<i64>, String> {
        transcript_repo::most_recent_id(&self.db).map_err(|e| e.to_string())
    }

    fn save_draft(
        &mut self,
        transcript_id: i64,
        draft: &selahcue_lan::protocol::SermonNoteDraftInput,
    ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
        let note = sermon_note_repo::NewSermonNote {
            transcript_id,
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            created_at_ms: now_ms(),
        };
        sermon_note_repo::create(&self.db, &note).map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or_else(|| "draft vanished immediately after create".to_string())?;
        Ok(sermon_note_view_of(&record))
    }

    fn load_draft(
        &mut self,
        transcript_id: i64,
    ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
        sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map(|opt| opt.map(|r| sermon_note_view_of(&r)))
            .map_err(|e| e.to_string())
    }

    fn update_draft(
        &mut self,
        transcript_id: i64,
        edit: &selahcue_lan::protocol::SermonNoteEditInput,
    ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
        let db_edit = sermon_note_repo::DraftEdit {
            title: edit.title.clone(),
            summary: edit.summary.clone(),
            sections_json: edit.sections_json.clone(),
            scriptures_json: edit.scriptures_json.clone(),
        };
        sermon_note_repo::update(&self.db, transcript_id, &db_edit, now_ms())
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or_else(|| "draft vanished immediately after update".to_string())?;
        Ok(sermon_note_view_of(&record))
    }

    /// Stage a freshly (re)generated draft against `transcript_id` WITHOUT replacing the
    /// currently-accepted draft (FR-129, 86akgqdx8). `Err` if no accepted draft exists yet.
    fn stage_regeneration(
        &mut self,
        transcript_id: i64,
        draft: &selahcue_lan::protocol::SermonNoteDraftInput,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        let pending = sermon_note_repo::PendingRegeneration {
            title: draft.title.clone(),
            summary: draft.summary.clone(),
            sections_json: draft.sections_json.clone(),
            scriptures_json: draft.scriptures_json.clone(),
            ai_generated: draft.ai_generated,
            disclosure: draft.disclosure.clone(),
            provider: draft.provider.clone(),
            model: draft.model.clone(),
            generated_at_ms: now_ms(),
        };
        sermon_note_repo::stage_regeneration(&self.db, transcript_id, &pending)
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?
            .ok_or_else(|| "draft vanished immediately after stage".to_string())?;
        Ok(regeneration_slot_of(&record))
    }

    /// Accept the pending regeneration for `transcript_id` (FR-129), replacing the accepted
    /// draft with it. `Err` if nothing is currently pending, or accepting would silently
    /// strip the FR-123 AI-generated label (`sermon_note_repo::confirm_regeneration`'s own
    /// "once AI-generated, always AI-generated" guard).
    fn confirm_regeneration(
        &mut self,
        transcript_id: i64,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        let record = sermon_note_repo::confirm_regeneration(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        Ok(regeneration_slot_of(&record))
    }

    /// Discard the pending regeneration for `transcript_id` (FR-129), leaving the accepted
    /// draft unchanged. Idempotent — never errors for "nothing was pending", INCLUDING the
    /// edge case of no `sermon_note` row at all for this transcript (86akgqdx8 review, Cody
    /// — Minor): `sermon_note_repo::discard_regeneration`'s own `UPDATE` is already a no-op
    /// with zero rows affected in that case, so reading back `None` here is not "the draft
    /// vanished", it is "there was never one" — an honest `RegenerationSlot::default()`
    /// (`current: None, pending: None`), not an error the caller has to interpret as a
    /// refusal.
    fn discard_regeneration(
        &mut self,
        transcript_id: i64,
    ) -> Result<selahcue_app::RegenerationSlot, String> {
        sermon_note_repo::discard_regeneration(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
            .map_err(|e| e.to_string())?;
        Ok(match record {
            Some(record) => regeneration_slot_of(&record),
            None => selahcue_app::RegenerationSlot::default(),
        })
    }
}

/// `SessionState` -> [`ControllerSnapshot`] — the read-side counterpart of
/// [`SessionStore::state_of`], shared by [`SessionStore::load_session`] and
/// [`RealAutosaveStore::load_slot`] so a persisted row decodes into the SAME snapshot shape no
/// matter which table it came from (the singleton `session_state` row or an `autosave_slot`
/// row — `autosave_repo::AutosaveSlot::state` is the same `SessionState` type).
fn state_to_snapshot(state: &SessionState) -> ControllerSnapshot {
    ControllerSnapshot {
        live_idx: state.live_idx,
        staged_idx: state.staged_idx,
        plan_cursor: state.plan_cursor,
        blackout: state.blackout,
        timer_total_secs: state.timer_total_secs,
        timer_elapsed_secs: state.timer_elapsed_secs,
        timer_running: state.timer_running,
        live_scripture: state.live_scripture.clone(),
        live_free_text: state.live_free_text.clone(),
        live_free_body: state.live_free_body.clone(),
        staged_scripture: state.staged_scripture.clone(),
        live_slide: state.live_slide,
        staged_slide: state.staged_slide,
        cursor_slide: state.cursor_slide,
        theme: state.theme.clone(),
        custom_theme: state.custom_theme.clone(),
    }
}

/// Adapts `selahcue_data::autosave_repo` to `selahcue_app::AutosaveStore` (FR-005 "last-3";
/// 86ajy0hxg) — the exact sibling of [`RealSermonNoteStore`] just above, for the identical
/// reason: `selahcue-app` must not depend on `selahcue-data`. Owns its own `Database`
/// connection, opened the same way (see [`SessionStore::open_autosave_store`]).
struct RealAutosaveStore {
    db: Database,
}

impl selahcue_app::AutosaveStore for RealAutosaveStore {
    fn list_slots(&mut self) -> Result<Vec<selahcue_app::AutosaveSlotSummary>, String> {
        autosave_repo::list(&self.db)
            .map(|rows| {
                rows.into_iter()
                    .map(|s| selahcue_app::AutosaveSlotSummary {
                        slot: s.id,
                        saved_at_ms: s.saved_at_ms,
                        label: s.label,
                    })
                    .collect()
            })
            .map_err(|e| e.to_string())
    }
}

/// A deterministic snapshot of a plan's item CONTENT (86ajy0hxg; Cody, PR #102 code review —
/// Blocking-1). `autosave_slot` rows store a `plan_id` POINTER, not an independent copy of the
/// plan's content, and `plan_repo::update` mutates a plan's rows IN PLACE on every edit — so
/// without something to compare, restoring an older slot silently reapplied its indices onto
/// whatever the CURRENT (possibly since-edited) content happens to be. Reproduced live: remove
/// a plan item, `RestoreAutosave` a slot captured before the removal, and the WRONG item went
/// LIVE with no error at all. [`resolve_autosave_slot`] compares this against the value stored
/// at capture time and REFUSES the restore (an honest `Err`) on any mismatch.
///
/// Debug-formats the item list rather than hashing: no hash-collision risk to reason about, and
/// `PlanItem`/`Stanza`/`ItemContent` are all `Vec`/`Option`/primitive-based (no unordered
/// collection whose iteration order could vary between two calls over identical content), so
/// the format is stable. This intentionally narrows what `RestoreAutosave` can do: it is
/// reliable for the "failed open" / crash-restart case (nothing edited the plan between capture
/// and restore), but NOT a general plan-version-history feature — undoing a live edit made
/// AFTER a slot was captured invalidates that slot's fingerprint by definition, so restoring it
/// is refused rather than replaying stale indices onto edited content. Real plan-content
/// versioning (independent snapshots, not a pointer) would need its own, larger feature — out
/// of scope for this ticket's additive wire slice.
fn plan_fingerprint(plan: &ServicePlan) -> String {
    format!("{:?}", plan.items())
}

/// Resolve one autosave slot to `(plan_id, plan, snapshot)`, integrity-checked (FR-079) and
/// fingerprint-guarded (see [`plan_fingerprint`]) — the shared logic behind
/// [`SessionStore::load_autosave_slot`]. A free function over `&Database` (not a method on any
/// store type) because it is called from the HOST tick ([`App::handle_pending_restore`]),
/// deliberately OUTSIDE any `Mutex<LiveController>` lock: PR #102's performance review (Vera)
/// found that running this — an `integrity_check` over the WHOLE store, potentially hundreds of
/// milliseconds — inline inside `LiveController::apply()` (the earlier shape, via an
/// `AutosaveStore::load_slot` trait method) held that lock for the same duration, stalling the
/// render/present loop that locks it every frame. `RestoreAutosave` no longer resolves inline;
/// see `autosave_store.rs`'s module doc. Returns the resolved plan's OWN row id alongside its
/// content — a caller with `plan_id` bookkeeping of its own (see
/// [`SessionStore::load_autosave_slot`]) needs it, and `ServicePlan` itself carries no
/// persisted identity to re-derive it from.
fn resolve_autosave_slot(
    db: &Database,
    slot: i64,
) -> Result<Option<(i64, ServicePlan, ControllerSnapshot)>, String> {
    // FR-079: never trust a read from a store that has gone corrupt — check BEFORE resolving
    // the row, so a corrupt store refuses the whole restore rather than handing back a
    // plausible-looking but unreliable snapshot.
    db.integrity_check().map_err(|e| e.to_string())?;
    let Some(row) = autosave_repo::load(db, slot).map_err(|e| e.to_string())? else {
        return Ok(None);
    };
    let Some(plan_id) = row.state.plan_id else {
        return Err("autosave slot has no associated plan".to_string());
    };
    let plan = plan_repo::load(db, plan_id).map_err(|e| e.to_string())?;
    // The plan-content guard (Blocking-1): refuse rather than silently reapply stale indices
    // onto content that has changed since this slot was captured.
    let current_fingerprint = plan_fingerprint(&plan);
    if row.plan_fingerprint.as_deref() != Some(current_fingerprint.as_str()) {
        return Err(format!(
            "plan {plan_id} has changed since autosave slot {slot} was captured; refusing to \
             restore stale indices onto different content"
        ));
    }
    Ok(Some((plan_id, plan, state_to_snapshot(&row.state))))
}

/// `sermon_note_repo::SermonNoteRecord` -> the LAN wire "slot" shape
/// ([`selahcue_app::RegenerationSlot`]) — the regenerate-with-retention sibling of
/// [`sermon_note_view_of`] just above, additionally surfacing the `pending` regeneration
/// (if any) as its own [`selahcue_lan::protocol::SermonNoteDraftView`] (FR-129, 86akgqdx8).
fn regeneration_slot_of(r: &sermon_note_repo::SermonNoteRecord) -> selahcue_app::RegenerationSlot {
    selahcue_app::RegenerationSlot {
        current: Some(sermon_note_view_of(r)),
        pending: r.pending.as_ref().map(|p| {
            selahcue_lan::protocol::SermonNoteDraftView {
                title: p.title.clone(),
                summary: p.summary.clone(),
                sections_json: p.sections_json.clone(),
                scriptures_json: p.scriptures_json.clone(),
                ai_generated: p.ai_generated,
                disclosure: p.disclosure.clone(),
                provider: p.provider.clone(),
                model: p.model.clone(),
                // A pending regeneration has no separate edit history yet — both
                // timestamps read as its generation time, mirroring how a freshly
                // `create`d draft's own `created_at`/`edited_at` start out equal.
                created_at_ms: p.generated_at_ms,
                edited_at_ms: p.generated_at_ms,
            }
        }),
    }
}

/// Wall-clock epoch milliseconds for `sermon_note.created_at`/`edited_at` — this binary's own
/// clock read, mirroring every other desktop-stamped timestamp (e.g. `NewTranscript::started_at_ms`
/// at the call sites that construct it from `SystemTime::now()`).
fn now_ms() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// `sermon_note_repo::SermonNoteRecord` -> the LAN wire view. `transcript_id` is dropped — the
/// caller already knows it (it is the key both sides used to ask for/save this row) and every
/// [`selahcue_lan::protocol::ServerMessage::SermonNoteDraft`] carries it as a separate top-level
/// field, never duplicated inside the draft payload itself.
fn sermon_note_view_of(
    r: &sermon_note_repo::SermonNoteRecord,
) -> selahcue_lan::protocol::SermonNoteDraftView {
    selahcue_lan::protocol::SermonNoteDraftView {
        title: r.title.clone(),
        summary: r.summary.clone(),
        sections_json: r.sections_json.clone(),
        scriptures_json: r.scriptures_json.clone(),
        ai_generated: r.ai_generated,
        disclosure: r.disclosure.clone(),
        provider: r.provider.clone(),
        model: r.model.clone(),
        created_at_ms: r.created_at_ms,
        edited_at_ms: r.edited_at_ms,
    }
}

/// 86akcfftu crash-recovery sweep: close any transcript left with `ended_at IS NULL` by a
/// previous run that never called `end()` — an app-close or crash mid-service, which the
/// normal Stop-Listening path (`selahcue-operator::listening`) cannot reach because the
/// process that would have sent it is the one that died. Runs once at startup, before any
/// new session can open one. Best-effort per row: one unreadable/unwritable row is logged
/// and skipped (retried on the next launch), never a hard failure that blocks startup.
///
/// The backfill timestamp is the transcript's last known segment `end_ms` (segment timings
/// are session-relative offsets from `started_at_ms`, per `transcript_repo`'s schema) added
/// onto `started_at_ms`, or `started_at_ms` itself for a session that crashed before its
/// first segment landed — the best available evidence of when it was last known to be alive,
/// never a fabricated "now".
fn sweep_orphaned_transcripts(db: &Database) {
    let Ok(summaries) = transcript_repo::list(db) else {
        return;
    };
    for t in summaries.into_iter().filter(|t| t.ended_at_ms.is_none()) {
        let backfill_ms = transcript_repo::load(db, t.id)
            .ok()
            .and_then(|detail| detail.segments.iter().map(|s| s.end_ms).max())
            .map(|last_end_ms| t.started_at_ms.saturating_add(last_end_ms as i64))
            .unwrap_or(t.started_at_ms);
        if let Err(e) = transcript_repo::end(db, t.id, backfill_ms) {
            eprintln!(
                "SelahCue: could not close orphaned transcript {} left open by a previous \
                 run ({e}); it will be retried on the next launch.",
                t.id
            );
        }
    }
}

/// The desktop's session store: the SQLite database + the persisted plan's row id.
/// A storage failure degrades to in-memory (never blocks a service) with a message.
struct SessionStore {
    db: Option<Database>,
    plan_id: Option<i64>,
    /// The most recent autosave failure, retained so the OPERATOR can see it.
    ///
    /// It previously reached stderr only, which means nobody running a service ever saw it —
    /// autosave could be failing for the whole meeting with the console showing nothing wrong.
    /// Bounded: exactly one, replaced each attempt and cleared on success, so a recovered
    /// autosave never keeps displaying an old failure.
    last_save_error: Option<String>,
}

impl SessionStore {
    fn open() -> Self {
        let db = data_dir()
            .map(|dir| (dir.join("selahcue.db3"), dir))
            .and_then(|(path, dir)| match Self::open_db(&path, &dir) {
                Ok(db) => Some(db),
                Err(e) => {
                    eprintln!("SelahCue: session store unavailable ({e}); running in-memory.");
                    None
                }
            });
        SessionStore {
            db,
            plan_id: None,
            last_save_error: None,
        }
    }

    /// Open the store (FR-154/86ajp5vp6). The decision is keyed on what is
    /// ACTUALLY on disk — the file header discriminates a plaintext store from
    /// an encrypted one — so a key hiccup can never mint a plaintext store next
    /// to real data, silently kill persistence, or masquerade as corruption:
    ///
    /// | on disk        | key acquired | action                                    |
    /// |----------------|--------------|-------------------------------------------|
    /// | nothing        | yes          | create ENCRYPTED                          |
    /// | nothing        | no           | create plaintext + loud warning (documented best-effort) |
    /// | plaintext      | either       | open PLAIN + warning (encryption pending a migration tool — never keyed-open a plain file) |
    /// | encrypted      | yes          | open ENCRYPTED; a key mismatch HARD-STOPS persistence with an honest message (file untouched) |
    /// | encrypted      | no           | HARD-STOP persistence: "fix the key source" (no unencrypted attempt) |
    #[cfg(feature = "encryption")]
    fn open_db(path: &std::path::Path, data_dir: &std::path::Path) -> Result<Database, DataError> {
        let acquired = keys::acquire(data_dir);
        Self::open_store(path, acquired)
    }

    /// The testable state machine behind [`open_db`] (encryption builds).
    #[cfg(feature = "encryption")]
    fn open_store(
        path: &std::path::Path,
        acquired: Option<(selahcue_data::EncryptionKey, keys::KeySource)>,
    ) -> Result<Database, DataError> {
        const SQLITE_MAGIC: &[u8; 16] = b"SQLite format 3\0";
        let on_disk: Option<bool /* plaintext */> = match std::fs::read(path) {
            Ok(bytes) if bytes.len() >= 16 => Some(&bytes[..16] == SQLITE_MAGIC),
            Ok(_) => None, // zero/short file: treat as absent
            Err(_) => None,
        };
        match (on_disk, acquired) {
            (None, Some((key, source))) => {
                println!("  Store encryption: SQLCipher (key via {source:?}).");
                Database::open_encrypted(path, &key)
            }
            (None, None) => {
                eprintln!(
                    "SelahCue: NO ENCRYPTION KEY available — creating the store \
                     UNENCRYPTED (best-effort per FR-154; set SELAHCUE_PASSPHRASE \
                     or fix the OS keychain, then migrate)."
                );
                Database::open(path)
            }
            (Some(true), key) => {
                if key.is_some() {
                    eprintln!(
                        "SelahCue: the existing store is UNENCRYPTED; opening it as-is \
                         (in-place encryption migration is a pending tool — the key was \
                         acquired and will be used once migrated)."
                    );
                }
                Database::open(path)
            }
            (Some(false), Some((key, source))) => match Database::open_encrypted(path, &key) {
                Ok(db) => {
                    println!("  Store encryption: SQLCipher (key via {source:?}).");
                    Ok(db)
                }
                Err(e) => {
                    eprintln!(
                        "SelahCue: the store is ENCRYPTED but the acquired key (via \
                         {source:?}) does not open it — a changed passphrase, a missing \
                         key.salt from a partial backup restore, or a switched key \
                         source. The file is UNTOUCHED; persistence is off until the \
                         right key is back. ({e})"
                    );
                    Err(e)
                }
            },
            (Some(false), None) => {
                eprintln!(
                    "SelahCue: the store is ENCRYPTED and no key is available — \
                     persistence is off until the keychain/passphrase is back. \
                     The file is untouched; do NOT delete it."
                );
                Err(DataError::Corrupt(
                    "encrypted store, key unavailable".into(),
                ))
            }
        }
    }

    #[cfg(not(feature = "encryption"))]
    fn open_db(path: &std::path::Path, _data_dir: &std::path::Path) -> Result<Database, DataError> {
        Database::open(path)
    }

    /// Best-effort: open the durable transcript side-channel (86akcfftu), sweeping any
    /// crash-orphaned transcript first. A SECOND, independent connection to the SAME on-disk
    /// store this `SessionStore` uses — opened via the identical [`Self::open_db`] decision
    /// (plaintext vs SQLCipher, same key resolution), so it reads/writes the same file. Two
    /// connections need no shared Rust-level lock between them: `selahcue-data`'s persistence
    /// is WAL throughout (`ARCHITECTURE.md`), which is precisely the mode built for multiple
    /// connections to one file, and the RETURNED sink lives inside `LiveController`, so every
    /// call to it is already serialized by that controller's own `Arc<Mutex<_>>` — the same
    /// reasoning that makes `self.db` need no lock either (single owner per connection).
    ///
    /// Returns `None` on any failure (no data dir, can't open a second connection) — a
    /// side-channel failure must never block the service starting; the caller keeps the
    /// default no-op `NullTranscriptSink`, exactly like any other storage degradation here.
    fn open_transcript_sink() -> Option<Box<dyn selahcue_app::TranscriptSink>> {
        let dir = data_dir()?;
        let path = dir.join("selahcue.db3");
        let db = Self::open_db(&path, &dir).ok()?;
        sweep_orphaned_transcripts(&db);
        Some(Box::new(selahcue_app::BatchingTranscriptWriter::new(
            RealTranscriptStore { db },
        )))
    }

    /// Best-effort: open the durable sermon-note-draft store (86akgqdv0; PR #33 review, Sana F1
    /// remediation) — the exact sibling of [`open_transcript_sink`](Self::open_transcript_sink)
    /// just above, for the identical reason. A THIRD independent connection to the SAME on-disk
    /// store (`self.db`/`open_transcript_sink`'s own connection are the other two) — safe for
    /// the same reason those two are: WAL throughout, and every call into the returned store is
    /// already serialized by `LiveController`'s own `Arc<Mutex<_>>`.
    ///
    /// This is the fix for the bug PR #33's review found: the operator previously opened its
    /// OWN, differently-located file for this feature (Tauri `app_data_dir()`, never this
    /// process's `data_dir()`), so in a real launch it could never see a real `transcript` row.
    /// The operator no longer opens any file for this feature at all — it sends LAN commands
    /// that land here, against the store this process actually owns.
    ///
    /// Returns `None` on any failure (no data dir, can't open a second connection) — a
    /// side-channel failure must never block the service starting; the caller keeps the
    /// default no-op `NullSermonNoteStore`, exactly like `open_transcript_sink`'s own
    /// degradation.
    fn open_sermon_note_store() -> Option<Box<dyn selahcue_app::SermonNoteStore>> {
        let dir = data_dir()?;
        let path = dir.join("selahcue.db3");
        let db = Self::open_db(&path, &dir).ok()?;
        Some(Box::new(RealSermonNoteStore { db }))
    }

    /// Load the persisted session: the plan + the live-state snapshot. `None` on a
    /// first run (or unusable store) — the caller seeds the demo plan.
    fn load_session(&mut self) -> Option<(ServicePlan, ControllerSnapshot)> {
        let db = self.db.as_ref()?;
        let state = match session_repo::load(db) {
            Ok(state) => state?,
            Err(e) => {
                // A corrupt snapshot is diagnosable evidence — say so before the
                // fresh start (the next autosave will overwrite the row).
                eprintln!("SelahCue: persisted session unreadable ({e}); starting fresh.");
                return None;
            }
        };
        let plan_id = state.plan_id?;
        let plan = match plan_repo::load(db, plan_id) {
            Ok(plan) => plan,
            Err(e) => {
                eprintln!("SelahCue: persisted plan unreadable ({e}); starting fresh.");
                return None;
            }
        };
        self.plan_id = Some(plan_id);
        Some((plan, state_to_snapshot(&state)))
    }

    /// Whether a preserved session row exists on disk, WITHOUT the side effects
    /// [`load_session`](Self::load_session) has (it sets `self.plan_id`, which must stay unset
    /// until a real resume actually happens — see the crash-loop `resumable` computation in
    /// [`App::new`], 86ajy0hxg). A read-only peek: `Ok(Some(_))` from `session_repo::load`, and
    /// nothing else — deliberately NOT "and its plan still loads", because that would require
    /// the same plan-load side effects this exists to avoid; a session row whose plan later
    /// fails to load is still surfaced honestly as "nothing to resume" by `Command::Resume`'s
    /// own handling at that point, not here.
    fn has_preserved_session(&self) -> bool {
        self.db
            .as_ref()
            .is_some_and(|db| matches!(session_repo::load(db), Ok(Some(_))))
    }

    /// Ensure the (demo) plan exists in the store; called before the first save.
    fn ensure_plan(&mut self, plan: &ServicePlan) {
        if self.plan_id.is_some() {
            return;
        }
        if let Some(db) = self.db.as_ref() {
            match plan_repo::insert(db, plan) {
                Ok(id) => self.plan_id = Some(id),
                Err(e) => eprintln!("SelahCue: could not persist the plan ({e})."),
            }
        }
    }

    /// Persisted output→display assignments (`(role, display_key)`), if any.
    fn load_output_assignments(&self) -> Vec<(String, String)> {
        self.db
            .as_ref()
            .and_then(|db| match output_repo::load_assignments(db) {
                Ok(rows) => Some(rows),
                Err(e) => {
                    eprintln!("SelahCue: could not read output assignments ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist one output→display assignment (reported, never fatal).
    fn save_output_assignment(&self, role: &str, display_key: &str) {
        if let Some(db) = self.db.as_ref() {
            if let Err(e) = output_repo::save_assignment(db, role, display_key) {
                eprintln!("SelahCue: could not persist the {role} output assignment ({e}).");
            }
        }
    }

    /// The persisted saved-theme library (`(name, theme_json)`), if any (86ajq4xmy).
    fn load_saved_themes(&self) -> Vec<(String, String)> {
        self.db
            .as_ref()
            .and_then(|db| match saved_theme_repo::load_all(db) {
                Ok(rows) => Some(rows),
                Err(e) => {
                    eprintln!("SelahCue: could not read the saved-theme library ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist the whole saved-theme library (reported, never fatal). Returns whether
    /// the write succeeded so the caller can re-arm the dirty flag on failure.
    fn save_saved_themes(&self, themes: &[(String, String)]) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        match saved_theme_repo::save_all(db, themes) {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the saved-theme library ({e}).");
                false
            }
        }
    }

    /// The persisted per-screen theme map (`(screen, theme_name)`), if any (86ajq321k).
    fn load_screen_themes(&self) -> Vec<(String, String)> {
        self.db
            .as_ref()
            .and_then(|db| match screen_theme_repo::load_all(db) {
                Ok(rows) => Some(rows),
                Err(e) => {
                    eprintln!("SelahCue: could not read the per-screen theme map ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist the whole per-screen theme map (reported, never fatal). Returns whether
    /// the write succeeded so the caller can re-arm the dirty flag on failure.
    fn save_screen_themes(&self, themes: &[(String, String)]) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        match screen_theme_repo::save_all(db, themes) {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the per-screen theme map ({e}).");
                false
            }
        }
    }

    /// The persisted screen registry (`(screen, role, enabled, deletable)`), if any
    /// (Screens page — dynamic registry). The controller recovers to the built-in default
    /// when this is empty/corrupt.
    fn load_screens(&self) -> Vec<(String, String, bool, bool)> {
        self.db
            .as_ref()
            .and_then(|db| match screen_repo::load_all(db) {
                Ok(rows) => Some(rows),
                Err(e) => {
                    eprintln!("SelahCue: could not read the screen registry ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist the whole screen registry (reported, never fatal). Returns whether the
    /// write succeeded so the caller can re-arm the dirty flag on failure.
    fn save_screens(&self, screens: &[(String, String, bool, bool)]) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        match screen_repo::save_all(db, screens) {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the screen registry ({e}).");
                false
            }
        }
    }

    /// The persisted per-screen OUTPUT CONFIG (Screens page inspector), decoded to
    /// `(screen, OutputConfigView)`. The controller drops any unknown/default entry on load.
    fn load_screen_configs(&self) -> Vec<(String, OutputConfigView)> {
        self.db
            .as_ref()
            .and_then(|db| match screen_config_repo::load_all(db) {
                Ok(rows) => Some(rows.into_iter().map(row_to_config).collect()),
                Err(e) => {
                    eprintln!("SelahCue: could not read the per-screen output config ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist the whole per-screen output-config set (reported, never fatal). Returns whether
    /// the write succeeded so the caller can re-arm the dirty flag on failure.
    fn save_screen_configs(&self, configs: &[(String, OutputConfigView)]) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        let rows: Vec<_> = configs.iter().map(|(s, c)| config_to_row(s, c)).collect();
        match screen_config_repo::save_all(db, &rows) {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the per-screen output config ({e}).");
                false
            }
        }
    }

    /// Persist the (edited) plan: update in place, or insert on the first save.
    /// Returns whether the write succeeded (the caller re-arms the retry).
    fn save_plan(&mut self, plan: &ServicePlan) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        let result = match self.plan_id {
            Some(id) => plan_repo::update(db, id, plan),
            None => plan_repo::insert(db, plan).map(|id| {
                self.plan_id = Some(id);
            }),
        };
        match result {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the plan edit ({e}).");
                false
            }
        }
    }

    /// The most recent autosave failure, if the last attempt failed.
    ///
    /// `None` once a save succeeds, so a recovered autosave never keeps displaying the failure
    /// it recovered from — the same discipline the output-health record uses for its fault
    /// reason.
    fn last_save_error(&self) -> Option<&str> {
        self.last_save_error.as_deref()
    }

    /// Build the persistence-layer [`SessionState`] for `snap`, stamped with this store's
    /// current `plan_id` — the single conversion both [`save_session`](Self::save_session) and
    /// [`push_autosave_slot`](Self::push_autosave_slot) use, so the two persisted shapes (the
    /// singleton row and a slot-ring row) can never drift apart field-by-field.
    fn state_of(&self, snap: &ControllerSnapshot) -> SessionState {
        SessionState {
            plan_id: self.plan_id,
            live_idx: snap.live_idx,
            staged_idx: snap.staged_idx,
            plan_cursor: snap.plan_cursor,
            blackout: snap.blackout,
            timer_total_secs: snap.timer_total_secs,
            timer_elapsed_secs: snap.timer_elapsed_secs,
            timer_running: snap.timer_running,
            live_scripture: snap.live_scripture.clone(),
            live_free_text: snap.live_free_text.clone(),
            live_free_body: snap.live_free_body.clone(),
            staged_scripture: snap.staged_scripture.clone(),
            live_slide: snap.live_slide,
            staged_slide: snap.staged_slide,
            cursor_slide: snap.cursor_slide,
            theme: snap.theme.clone(),
            custom_theme: snap.custom_theme.clone(),
        }
    }

    /// Persist the live-state snapshot. Returns whether the write succeeded (an
    /// error is reported, never fatal mid-service; the caller re-arms the retry).
    fn save_session(&mut self, snap: &ControllerSnapshot) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        let state = self.state_of(snap);
        match session_repo::save(db, &state) {
            Ok(()) => {
                self.last_save_error = None;
                true
            }
            Err(e) => {
                eprintln!("SelahCue: autosave failed ({e}).");
                self.last_save_error = Some(e.to_string());
                false
            }
        }
    }

    /// Capture a new autosave-slot restore point (FR-005 "last-3"; 86ajy0hxg). Best-effort and
    /// never fatal — a failure here does not touch [`last_save_error`](Self::last_save_error)
    /// (that field is specifically the SINGLETON crash-recovery row's health, which the
    /// operator-facing `autosave_error` health field reports; the slot ring is a secondary,
    /// lower-stakes convenience feature and logging its own failure is enough).
    fn push_autosave_slot(&self, plan: &ServicePlan, snap: &ControllerSnapshot, saved_at_ms: i64) {
        let Some(db) = self.db.as_ref() else {
            return;
        };
        let state = self.state_of(snap);
        // Captured alongside the state, from the SAME plan the snapshot's indices point into —
        // see `plan_fingerprint`'s doc for why this exists (Blocking-1).
        let fingerprint = plan_fingerprint(plan);
        if let Err(e) = autosave_repo::push(db, &state, saved_at_ms, None, Some(&fingerprint)) {
            eprintln!("SelahCue: could not capture an autosave restore point ({e}).");
        }
    }

    /// Best-effort: open the durable autosave-slot store (FR-005 "last-3"; 86ajy0hxg) — the
    /// exact sibling of [`open_sermon_note_store`](Self::open_sermon_note_store) just above,
    /// for the identical reason (`selahcue-app` must not depend on `selahcue-data`). `None` on
    /// any failure — the caller keeps the default no-op `NullAutosaveStore`.
    fn open_autosave_store() -> Option<Box<dyn selahcue_app::AutosaveStore>> {
        let dir = data_dir()?;
        let path = dir.join("selahcue.db3");
        let db = Self::open_db(&path, &dir).ok()?;
        Some(Box::new(RealAutosaveStore { db }))
    }

    /// Resolve a `Command::RestoreAutosave` slot (FR-005/FR-079; 86ajy0hxg) — called from
    /// [`App::handle_pending_restore`], on THIS store's own already-open connection, OUTSIDE any
    /// `Mutex<LiveController>` lock (see [`resolve_autosave_slot`]'s doc for why that matters).
    ///
    /// On success, ALSO updates `self.plan_id` to the resolved slot's plan — unlike the earlier
    /// shape (Sana, PR #102 security review — S-5), this runs on the SAME `SessionStore` whose
    /// `plan_id` governs where normal autosave writes go, so a cross-plan restore (a slot
    /// captured before a `NewPlan`/`ImportPlan`) immediately re-points subsequent saves at the
    /// restored plan's row — not "eventually, on the next edit," which was never actually true
    /// (`save_plan` only re-derives `plan_id` when it is `None`, never overwrites an existing
    /// one).
    fn load_autosave_slot(
        &mut self,
        slot: i64,
    ) -> Result<Option<(ServicePlan, ControllerSnapshot)>, String> {
        let Some(db) = self.db.as_ref() else {
            return Ok(None);
        };
        let Some((plan_id, plan, snap)) = resolve_autosave_slot(db, slot)? else {
            return Ok(None);
        };
        self.plan_id = Some(plan_id);
        Ok(Some((plan, snap)))
    }
}

/// Honest per-output present telemetry (Screens page signal-health footer). Every field is
/// MEASURED by the present loop — never fabricated. `fps` is an EWMA of real present
/// intervals; `dropped_frames` counts deferred presents (a lost/outdated swapchain); `signal`
/// reflects whether a monitor is attached and the last present succeeded. A virtual screen
/// with no physical window has no `Renderer`, so it honestly reports no telemetry (dash).
#[derive(Debug, Clone, Copy)]
struct OutputTelemetry {
    /// Frames actually presented to the surface.
    frames_presented: u64,
    /// Frames the host deferred (swapchain lost/outdated) — the honest dropped count.
    dropped_frames: u64,
    /// EWMA of the instantaneous present rate (fps). `0.0` until the second present.
    fps_ewma: f32,
    /// When the last present succeeded (drives the fps interval + the frame-rate gate).
    last_present: Option<Instant>,
    /// Whether the last present attempt succeeded (a deferred present degrades the signal).
    last_present_ok: bool,
}

impl OutputTelemetry {
    fn new() -> Self {
        OutputTelemetry {
            frames_presented: 0,
            dropped_frames: 0,
            fps_ewma: 0.0,
            last_present: None,
            last_present_ok: true,
        }
    }

    /// The measured fps as a whole number (rounded EWMA). `0` before the second present.
    fn fps(&self) -> u16 {
        self.fps_ewma.round().clamp(0.0, u16::MAX as f32) as u16
    }

    /// Honest signal-health label for the given (freshly sampled) monitor attachment: no
    /// monitor → `no_signal`; a recently-deferred present → `degraded`; otherwise `healthy`.
    /// `monitor_attached` is sampled by the caller at the low Moved/Resized cadence, not per
    /// frame.
    fn signal_label(&self, monitor_attached: bool) -> &'static str {
        if !monitor_attached {
            "no_signal"
        } else if !self.last_present_ok {
            "degraded"
        } else {
            "healthy"
        }
    }

    /// Record the outcome of a present ATTEMPT (not a frame-rate skip): update the EWMA fps
    /// from the real interval, and the dropped-frame count on a deferred present. Does NOT
    /// query the windowing system for monitor attachment — that is sampled at the far lower
    /// Moved/Resized cadence in `publish_output_status`, so the hot present path stays cheap.
    fn record(&mut self, now: Instant, presented: bool) {
        if presented {
            if let Some(prev) = self.last_present {
                let dt = now.duration_since(prev).as_secs_f32();
                if dt > 0.0 {
                    let inst = 1.0 / dt;
                    // Seed on the first interval, then a light EWMA to smooth jitter.
                    self.fps_ewma = if self.fps_ewma == 0.0 {
                        inst
                    } else {
                        0.9 * self.fps_ewma + 0.1 * inst
                    };
                }
            }
            self.last_present = Some(now);
            self.last_present_ok = true;
            self.frames_presented = self.frames_presented.saturating_add(1);
        } else {
            self.last_present_ok = false;
            self.dropped_frames = self.dropped_frames.saturating_add(1);
        }
    }
}

/// Apply a screen's per-output GEOMETRIC config to its composed frame, targeting the
/// `win_w × win_h` output surface: rotate (orientation) → mirror → fit (scaling). Returns
/// `None` when the config is geometrically default (orientation 0, no mirror, `Fill`) so the
/// caller blits the original buffer UNCHANGED — the common case pays ZERO transform cost and
/// default rendering is byte-identical (no regression / pinned smoke test safe). Pure integer
/// transforms (NFR-014). This drives the on-screen blit ONLY; the operator preview
/// (`render_screen` → `compose_screen`) is a separate path that does not apply these
/// geometric transforms (per-screen THEME + LAYER visibility do reach the preview, geometry
/// does not — a documented asymmetry).
///
/// Each stage is skipped when it would be an IDENTITY on this buffer, so a mirror-only (or
/// Fill-at-native-size) config never pays for a wasteful full-frame `rotated(0)` clone or a
/// no-op `fitted()` resample+crop on the audience-critical present path.
fn apply_output_config(
    base: &FrameBuffer,
    cfg: &OutputConfigView,
    win_w: u32,
    win_h: u32,
) -> Option<FrameBuffer> {
    let geometry_default =
        cfg.orientation.is_multiple_of(4) && !cfg.mirror && matches!(cfg.scale_fit, ScaleFit::Fill);
    if geometry_default {
        return None;
    }
    let (win_w, win_h) = (win_w.max(1), win_h.max(1));
    // Rotate only when it is not a full turn (rotated(0) is a wasteful identity clone).
    let rotated = (!cfg.orientation.is_multiple_of(4)).then(|| base.rotated(cfg.orientation));
    // Mirror the current buffer (borrow `base` when no rotate happened) only when requested.
    let mirrored = cfg
        .mirror
        .then(|| rotated.as_ref().unwrap_or(base).mirrored_horizontal());
    // The buffer after rotate+mirror, borrowing whichever we actually produced.
    let cur = mirrored.as_ref().or(rotated.as_ref()).unwrap_or(base);
    // Fit only when it would change the buffer: `Fill` that already matches the surface is a
    // no-op (skip the resample+crop clone chain).
    let fill_matches =
        matches!(cfg.scale_fit, ScaleFit::Fill) && cur.width() == win_w && cur.height() == win_h;
    if !fill_matches {
        let fit = match cfg.scale_fit {
            ScaleFit::Fill => Fit::Fill,
            ScaleFit::Fit => Fit::Fit,
            ScaleFit::Stretch => Fit::Stretch,
        };
        return Some(cur.fitted(win_w, win_h, fit));
    }
    // No fit needed — return the rotated/mirrored buffer (non-default guarantees one exists).
    mirrored.or(rotated)
}

/// The measured telemetry for an output window (`None` for an absent/virtual output).
fn telemetry_of(r: &Option<Renderer>) -> Option<&OutputTelemetry> {
    r.as_ref().map(|r| &r.telemetry)
}

/// The stable persist tag for a scaling/fit mode.
fn scale_fit_tag(fit: ScaleFit) -> &'static str {
    match fit {
        ScaleFit::Fill => "fill",
        ScaleFit::Fit => "fit",
        ScaleFit::Stretch => "stretch",
    }
}

/// Encode an [`OutputConfigView`] as a persist row (Store ↔ `screen_config_repo`).
fn config_to_row(screen: &str, c: &OutputConfigView) -> screen_config_repo::ScreenConfigRow {
    screen_config_repo::ScreenConfigRow {
        screen: screen.to_string(),
        orientation: c.orientation,
        scale_fit: scale_fit_tag(c.scale_fit).to_string(),
        mirror: c.mirror,
        delay_ms: c.delay_ms,
        frame_rate: c.frame_rate,
        layer_background: c.layers.background,
        layer_text: c.layers.text,
        layer_lower_third: c.layers.lower_third,
        layer_logo: c.layers.logo,
        layer_timer: c.layers.timer,
        safe_area: c.safe_area_guides,
        ndi_enabled: c.ndi_enabled,
        ndi_name: c.ndi_name.clone(),
    }
}

/// Decode a persist row into `(screen, OutputConfigView)`. An unknown `scale_fit` tag decodes
/// to the identity default (`Fill`) — robust recovery from a tampered/forward-compat store.
fn row_to_config(row: screen_config_repo::ScreenConfigRow) -> (String, OutputConfigView) {
    let scale_fit = match row.scale_fit.as_str() {
        "fit" => ScaleFit::Fit,
        "stretch" => ScaleFit::Stretch,
        _ => ScaleFit::Fill,
    };
    (
        row.screen,
        OutputConfigView {
            orientation: row.orientation,
            scale_fit,
            mirror: row.mirror,
            delay_ms: row.delay_ms,
            frame_rate: row.frame_rate,
            safe_area_guides: row.safe_area,
            layers: LayerVisibility {
                background: row.layer_background,
                text: row.layer_text,
                lower_third: row.layer_lower_third,
                logo: row.layer_logo,
                timer: row.layer_timer,
            },
            ndi_enabled: row.ndi_enabled,
            ndi_name: row.ndi_name,
        },
    )
}

struct Renderer {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    bind_group_layout: wgpu::BindGroupLayout,
    sampler: wgpu::Sampler,
    frame_texture: Option<(wgpu::Texture, u32, u32)>,
    /// Measured present telemetry (Screens page signal-health).
    telemetry: OutputTelemetry,
}

impl Renderer {
    /// Build the GPU renderer for a window. FALLIBLE by design: a screen can now be
    /// re-opened mid-service (the Screens toggle), and a GPU hiccup on that re-open must
    /// not panic the process — that would take down the *other* window, the LAN server and
    /// the live state with it. The caller logs and leaves the screen closed instead.
    fn new(window: Arc<Window>) -> Result<Self, String> {
        let size = window.inner_size();
        let instance = wgpu::Instance::default();
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| format!("create surface: {e}"))?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .ok_or_else(|| "no compatible GPU adapter".to_string())?;
        let (device, queue) =
            pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default(), None))
                .map_err(|e| format!("request device: {e}"))?;

        let caps = surface.get_capabilities(&adapter);
        let format = caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .or_else(|| caps.formats.first().copied())
            .ok_or_else(|| "surface offers no texture format".to_string())?;
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("blit"),
            source: wgpu::ShaderSource::Wgsl(include_str!("blit.wgsl").into()),
        });
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("blit"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("blit"),
            bind_group_layouts: &[&bind_group_layout],
            push_constant_ranges: &[],
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("blit"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: "vs",
                buffers: &[],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: "fs",
                targets: &[Some(config.format.into())],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor::default());

        Ok(Renderer {
            window,
            surface,
            device,
            queue,
            config,
            pipeline,
            bind_group_layout,
            sampler,
            frame_texture: None,
            telemetry: OutputTelemetry::new(),
        })
    }

    fn resize(&mut self, width: u32, height: u32) {
        self.config.width = width.max(1);
        self.config.height = height.max(1);
        self.surface.configure(&self.device, &self.config);
    }

    /// Composite `frame` onto this window's surface. Returns `true` when a frame
    /// was actually presented (false when the swapchain was lost/outdated and the
    /// paint is deferred to the next tick) — the smoke mode uses this to know the
    /// window really produced a visible frame before exiting.
    fn render(&mut self, frame: &FrameBuffer) -> bool {
        let (fw, fh) = (frame.width(), frame.height());
        if self.frame_texture.as_ref().map(|(_, w, h)| (*w, *h)) != Some((fw, fh)) {
            let texture = self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("frame"),
                size: wgpu::Extent3d {
                    width: fw,
                    height: fh,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Rgba8UnormSrgb,
                usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                view_formats: &[],
            });
            self.frame_texture = Some((texture, fw, fh));
        }
        let Some((texture, _, _)) = self.frame_texture.as_ref() else {
            return false;
        };
        self.queue.write_texture(
            wgpu::ImageCopyTexture {
                texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            frame.bytes(),
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(fw * 4),
                rows_per_image: Some(fh),
            },
            wgpu::Extent3d {
                width: fw,
                height: fh,
                depth_or_array_layers: 1,
            },
        );
        let tex_view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("blit"),
            layout: &self.bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&tex_view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.sampler),
                },
            ],
        });

        let surface_frame = match self.surface.get_current_texture() {
            Ok(frame) => frame,
            Err(err) => {
                // A stale/lost swapchain (sleep, display re-negotiation) needs
                // reconfiguring. The paced frame loop (`new_events`) re-requests a paint
                // next frame, so we do NOT request one here — doing so would busy-spin
                // while the surface can't present.
                if matches!(err, wgpu::SurfaceError::Outdated | wgpu::SurfaceError::Lost) {
                    self.surface.configure(&self.device, &self.config);
                }
                return false;
            }
        };
        let target = surface_frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("blit"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &target,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.draw(0..3, 0..1);
        }
        self.queue.submit(Some(encoder.finish()));
        surface_frame.present();
        true
    }

    /// Present `base` under this output's per-screen `cfg` (Screens page): honor the
    /// frame-rate cap, apply the geometric transform (orientation/mirror/fit), blit, and
    /// record telemetry. Returns whether a frame was actually presented. A frame-rate SKIP
    /// (the configured interval has not elapsed) is intentional — it returns `false` but is
    /// NOT counted as a dropped frame.
    fn present_output(&mut self, base: &FrameBuffer, cfg: &OutputConfigView, now: Instant) -> bool {
        // Frame-rate gate. Default 60fps at the 60 Hz loop never gates (5% slack); only an
        // explicitly LOWER target skips presents.
        let target = cfg.frame_rate.max(1) as f32;
        if let Some(prev) = self.telemetry.last_present {
            let min_dt = (1.0 / target) * 0.95;
            if now.duration_since(prev).as_secs_f32() < min_dt {
                return false; // intentional frame-rate skip — not a drop
            }
        }
        let (win_w, win_h) = {
            let s = self.window.inner_size();
            (s.width.max(1), s.height.max(1))
        };
        let transformed = apply_output_config(base, cfg, win_w, win_h);
        let frame = transformed.as_ref().unwrap_or(base);
        let presented = self.render(frame);
        self.telemetry.record(now, presented);
        presented
    }
}

/// State shared between the winit thread and the control-server thread.
struct RemoteShared {
    registry: Arc<AsyncMutex<SessionRegistry>>,
    /// `(bound port, certificate pin hex)` — filled once the server is listening.
    lan: OnceLock<(u16, String)>,
    /// The currently offered pairing code, so cancelling pairing can withdraw it
    /// from the registry (a cancelled code must actually die, not linger to TTL).
    active_code: Mutex<Option<String>>,
}

struct App {
    /// The main audience/program output window. `None` means the `main` screen is
    /// DISABLED — for a built-in screen, `enabled` means "the OS window exists".
    main: Option<Renderer>,
    /// The stage/confidence monitor window — the same live state composed as a speaker
    /// view (current + next line + timer + clock), FR-037. `None` when disabled.
    stage: Option<Renderer>,
    /// Shared with the control-server thread: the remote controller and the local
    /// keyboard drive the *same* live state, shown on both windows.
    controller: Arc<Mutex<LiveController>>,
    /// Pairing/registry state shared with the control-server thread.
    remote: Arc<RemoteShared>,
    /// The next frame deadline (a *fixed* schedule, advanced only when a frame fires), so
    /// continuous input can't keep pushing it forward and starve the redraw/tick loop.
    next_frame: Option<Instant>,
    /// The canonical keybinding state machine (UX-CANONICAL §1).
    keymap: Keymap,
    /// Attached physical displays, refreshed when windows are (re)created.
    displays: Vec<DisplayView>,
    /// Persisted role→display assignments (cache of the output_config table).
    assignments: Vec<(String, String)>,
    /// Launch-stability journal (crash-loop breaker, FR-169).
    launch_guard: Option<guard::LaunchGuard>,
    /// When this launch started (drives the stability mark).
    launched_at: Instant,
    /// Whether stability has been marked for this launch.
    stable_marked: bool,
    /// Last periodic disk-headroom check.
    last_disk_check: Instant,
    /// Whether checkpoint writes are currently halted (disk below the floor).
    disk_critical: bool,
    /// The most recent storage verdict, cached so every health publish reports the real one
    /// rather than re-reading the filesystem each frame. `None` = the platform could not tell
    /// us, which is reported as `"unknown"` — never silently as healthy.
    last_disk_status: Option<guard::DiskStatus>,
    /// Whether a persisted session was restored at launch.
    session_restored: bool,
    /// Unstable launches counted when the crash-loop breaker tripped.
    crash_rapid_launches: Option<u32>,
    /// Breaker-tripped clean run: checkpointing fully disabled so the
    /// preserved on-disk session is never touched (review 7ad-A).
    clean_mode: bool,
    /// Whether a preserved session exists to resume from while `clean_mode` is true
    /// (86ajy0hxg `SessionHealthView::resumable`) — cleared once `Command::Resume`/
    /// `Command::StartClean` is handled (see [`App::handle_crash_decision`]), since at that
    /// point there is no longer a pending decision to offer.
    crash_resumable: bool,
    /// Cached identify frames (main = 1, stage = 2) while the overlay is active. Each side
    /// is `None` when that screen currently has no window (disabled), so identify still
    /// works for whichever outputs ARE open. Invalidated whenever a window opens/closes.
    identify_frames: Option<(Option<FrameBuffer>, Option<FrameBuffer>)>,
    /// Live modifier state (winit reports modifiers separately from key presses) — the
    /// explicit Cmd-Q / Ctrl-Q quit chord needs it, since closing a window no longer quits.
    modifiers: winit::keyboard::ModifiersState,
    /// The session store (SQLite) for autosave + crash recovery.
    store: SessionStore,
    last_autosave: Instant,
    /// Last time an autosave-SLOT restore point was captured (FR-005 "last-3"; 86ajy0hxg) —
    /// gates [`AUTOSAVE_SLOT_INTERVAL`], separate from [`Self::last_autosave`] (the singleton
    /// row's own, much tighter, throttle).
    last_slot_push: Instant,
    /// GUI-launch smoke mode (story 86ajpevzp): present the first frame, report
    /// the time-to-first-frame (from App init — an informational figure, NOT the
    /// ≤3s cold-start NFR, which `make nfr` measures), then exit 0.
    smoke: bool,
    /// Whether the smoke exit has already fired (present can tick more than once).
    smoke_done: bool,
    /// Live NDI OUTPUT senders, keyed by registry screen id. Reconciled against the registry
    /// each frame: a sender is created for an enabled, NDI-configured audience screen and
    /// dropped (RAII closes the NDI source) when the screen is disabled / deleted / renamed —
    /// so the map stays bounded by the registry (`MAX_SCREENS`, no-leak). Empty in the default
    /// build (NDI delivery needs `--features ndi`); the config is stored + surfaced regardless.
    ndi_outputs: std::collections::HashMap<String, video_sink::NdiOutput>,
    /// Per-screen "do not retry NDI sender construction before this instant" backoff. When a
    /// sender fails to construct (feature-on: runtime not loadable, a network name collision, a
    /// resource limit), retrying every frame would be a ~60 Hz native re-init storm; this backs
    /// each failing screen off to [`NDI_RETRY_BACKOFF`]. Cleared when the screen's config changes
    /// or it succeeds. Bounded by the registry (entries pruned with the sender map).
    ndi_backoff: std::collections::HashMap<String, Instant>,
    /// Screen ids we've already warned about wanting NDI transmission on a build that can't do
    /// it (the `ndi` feature is off — [`video_sink::TRANSMIT_AVAILABLE`] is false). Logged once
    /// per screen so an operator who enables NDI on a non-NDI build learns why nothing shows up
    /// (e.g. in OBS) instead of silently believing it's on air. Bounded/pruned with the registry.
    ndi_warned: std::collections::HashSet<String>,
    /// Per-screen cached NDI frame + send pacing ([`NdiFrameCache`]): the dirty-gate that
    /// keeps the per-tick reconcile from re-rasterizing an unchanged output. Entries live
    /// only while their screen has live NDI delivery — pruned by [`reconcile_ndi`] with the
    /// sender set, so the map stays bounded by the registry (`MAX_SCREENS`).
    ndi_frames: std::collections::HashMap<String, NdiFrameCache>,
    /// Built-in windows whose creation FAILED this run — in-memory only, never persisted.
    /// See [`OpenFailures`] and [`record_open_outcome`].
    open_failures: OpenFailures,
    /// Which host-produced NFR-024 faults have already been reported for the incident in
    /// progress. See [`FaultLatch`]: one `bool` per fault kind, reported on the EDGE into the
    /// condition so a fault that lasts a whole service counts as one hold, not as one per
    /// frame.
    output_faults: FaultLatch,
}

/// Apply one command to the shared controller (a poisoned lock just drops the input
/// rather than panicking the UI thread).
fn drive(controller: &Mutex<LiveController>, command: &Command) {
    if let Ok(mut c) = controller.lock() {
        let _ = c.apply(command);
    }
}

/// Record the outcome of a window-creation attempt for a built-in screen.
///
/// The whole point of this function is what it does NOT do on failure: it does not touch
/// `controller`. Marking the screen disabled would go through `Command::SetScreenEnabled`,
/// which sets the registry dirty and lets the autosave WRITE it — so a transient GPU or
/// window-server failure at launch would be persisted as a durable "the operator turned this
/// screen off", and the next launch would open no window at all, present nothing, and fail
/// the smoke gate. The failure is instead held in `failures`, which lives and dies with the
/// process, and which also suppresses the retry storm without depending on a registry write
/// that can be rejected or silently dropped.
///
/// A success clears the flag, so a screen that recovers is never suppressed by an old failure.
fn record_open_outcome(
    controller: &Mutex<LiveController>,
    failures: &mut OpenFailures,
    role: WindowRole,
    outcome: Result<(), String>,
) {
    match outcome {
        Ok(()) => {
            failures.set(role, false);
            set_screen_enabled(controller, role, true);
        }
        Err(e) => {
            eprintln!(
                "SelahCue: could not open the {} output window ({e}); that screen has no window \
                 for now. It stays ENABLED — this is a transient failure, not a setting, so it is \
                 NOT saved. Switch the screen off and on again from the operator's Screens page \
                 to retry.",
                role.screen_id()
            );
            failures.set(role, true);
        }
    }
}

/// Flip a screen's `enabled` flag from THIS process, without a LAN round-trip. It goes
/// through the same [`Command::SetScreenEnabled`] dispatch a remote operator uses, so
/// there is exactly one place that mutates the registry (and the LAN `authorize()`
/// choke point is untouched — it still guards every remote caller). Skipped when the
/// flag already has the wanted value, so a reconcile can't dirty the registry for a
/// pointless persist write.
fn set_screen_enabled(controller: &Mutex<LiveController>, role: WindowRole, enabled: bool) {
    // A poisoned lock is read as "nothing to do": neither the read nor the write below can
    // succeed through it, so dispatching anyway would only be a command that silently
    // no-ops. Nothing depends on this write landing — window lifecycle is decided from the
    // registry plus [`OpenFailures`], never from whether this call took effect.
    let already = controller
        .lock()
        .map(|c| c.is_screen_enabled(role.screen_id()) == enabled)
        .unwrap_or(true);
    if already {
        return;
    }
    drive(
        controller,
        &Command::SetScreenEnabled {
            screen: role.screen_id().to_string(),
            enabled,
        },
    );
}

/// One screen's cached NDI frame + send-pacing state (the NDI dirty-gate). The frame is the
/// last composed output for the screen, re-sent while the controller's live generation holds
/// still — a memcpy send is ~1000x cheaper than the full-raster recompose that previously ran
/// every 16ms tick and pegged a core. One entry per LIVE sender (pruned with the sender set),
/// so the map is bounded by the registry (`MAX_SCREENS`).
/// Hard cap on the NDI frame cache's entry count (no-leak, published for the bounded-memory
/// test per the bounded-cache convention): at most ONE cached frame per registry screen, so
/// the cache tops out at `MAX_SCREENS` × one output-sized frame (~8.3MB each at 1080p). The
/// bound is enforced by [`reconcile_ndi`], which prunes entries to the live screen set every
/// tick and keys inserts by registry screen id.
pub const NDI_FRAME_CACHE_MAX_ENTRIES: usize = selahcue_app::MAX_SCREENS;

struct NdiFrameCache {
    /// The controller live generation this frame was composed at.
    generation: u64,
    /// The composed frame last put on the wire (~8.3MB at 1080p — hence the strict bound).
    frame: FrameBuffer,
    /// When the next frame is due on the wire (paces sends to the screen's `frame_rate`).
    next_send: Instant,
}

/// Decide-and-deliver ONE screen's NDI frame at `now`: recompose only when `generation`
/// differs from the cached frame's (fix 1), and put a frame on the wire only when the
/// screen's `frame_rate` says one is due (fix 2) — `now` is injected, never read here.
/// `compose`/`send` are seams so the default (no-NDI) build tests this exact logic.
fn ndi_deliver(
    frames: &mut std::collections::HashMap<String, NdiFrameCache>,
    screen: &str,
    generation: u64,
    frame_rate: u16,
    now: Instant,
    compose: impl FnOnce() -> Option<FrameBuffer>,
    send: impl FnOnce(&FrameBuffer),
) {
    // Pacing gate (fix 2): a frame goes on the wire at the screen's configured rate, not
    // at the ~60 Hz reconcile tick. `now` is injected by the caller — never read here.
    if frames.get(screen).is_some_and(|e| now < e.next_send) {
        return;
    }
    // Recompose ONLY when the controller's live generation moved past the cached frame's
    // (or nothing is cached yet) — an unchanged generation guarantees an unchanged compose.
    if frames
        .get(screen)
        .is_none_or(|e| e.generation != generation)
    {
        match compose() {
            Some(frame) => {
                frames.insert(
                    // Keyed by the SCREEN alone — every lookup here uses `screen`, and a
                    // key carrying the generation would both miss those lookups (nothing
                    // ever sent, recompose every tick) and grow one entry per generation,
                    // which is precisely the unbounded growth the bound below forbids.
                    screen.to_string(),
                    NdiFrameCache {
                        generation,
                        frame,
                        next_send: now,
                    },
                );
            }
            // The screen stopped composing (removed / role changed mid-flight): drop the
            // stale cache and send nothing — never re-send a frame for a gone screen.
            None => {
                frames.remove(screen);
                return;
            }
        }
    }
    if let Some(e) = frames.get_mut(screen) {
        send(&e.frame);
        // Clamp into the documented config range (the command path's own bound), so a
        // corrupt persisted rate (0 / nonsense) can neither divide by zero nor stall.
        let fps = frame_rate.clamp(MIN_FRAME_RATE, MAX_FRAME_RATE);
        let period = Duration::from_millis(1000 / u64::from(fps));
        // Anchor the cadence to the schedule (so the average rate holds despite the 16ms
        // tick grid), but never leave the deadline in the past after a stall — that would
        // burst-drain at tick rate instead of resuming the configured pace.
        e.next_send = std::cmp::max(e.next_send + period, now);
    }
}

/// Reconcile the NDI OUTPUT senders against the registry + per-screen config, then feed each
/// live sender its composed frame THROUGH [`ndi_deliver`] — recomposing only when the
/// controller's [`LiveController::live_generation`] moved (dirty-gate) and sending only at the
/// screen's configured `frame_rate` (pacer), so an idle live output costs a paced memcpy, not
/// a full 1080p re-raster every 16ms tick. Bounded by the registry (`MAX_SCREENS`) and
/// leak-free — a sender AND its ~8.3MB cached frame are dropped (RAII closes the NDI source)
/// when its screen is removed, disabled, has NDI turned off, or is renamed. Cheap no-op in the
/// DEFAULT build: without the `ndi` feature `NdiOutput::new` returns `None`, so no sender
/// exists and no per-screen frame is composed or cached.
fn reconcile_ndi(
    c: &LiveController,
    senders: &mut std::collections::HashMap<String, video_sink::NdiOutput>,
    backoff: &mut std::collections::HashMap<String, Instant>,
    warned: &mut std::collections::HashSet<String>,
    frames: &mut std::collections::HashMap<String, NdiFrameCache>,
    now: Instant,
) {
    // Drop any sender / backoff whose screen no longer exists in the registry (deleted feed).
    let live: std::collections::HashSet<&str> =
        c.screen_registry().iter().map(|s| s.id.as_str()).collect();
    senders.retain(|id, _| live.contains(id.as_str()));
    backoff.retain(|id, _| live.contains(id.as_str()));
    warned.retain(|id| live.contains(id.as_str()));
    // The frame cache holds ~8.3MB per entry at 1080p — bounded the same way (no-leak).
    frames.retain(|id, _| live.contains(id.as_str()));

    // The output resolution (used to construct a sender without a per-screen compose).
    let (out_w, out_h) = {
        let fb = c.presenter().live_output();
        (fb.width(), fb.height())
    };
    for s in c.screen_registry().iter() {
        let cfg = c.output_config(&s.id);
        let want = s.enabled && cfg.ndi_enabled && !cfg.ndi_name.is_empty();
        // If the operator has asked for NDI but this build can't transmit, say so once per
        // screen — the config is honoured (persisted + surfaced) but no source reaches the
        // network, which otherwise looks like a silent failure (nothing shows up in OBS).
        if want && !video_sink::TRANSMIT_AVAILABLE && warned.insert(s.id.clone()) {
            eprintln!(
                "[ndi] screen '{}' is set to broadcast as NDI source \"{}\", but this build has \
                 no NDI transmission compiled in — no source will appear on the network (e.g. in \
                 OBS). Run the NDI build to broadcast: `make output-ndi`.",
                s.id, cfg.ndi_name
            );
        }
        // Drop a stale sender (screen disabled / NDI off / renamed) so RAII closes its source;
        // clear any backoff so a re-enable / rename retries construction immediately.
        if senders
            .get(&s.id)
            .is_some_and(|o| !want || o.name() != cfg.ndi_name)
        {
            senders.remove(&s.id);
            backoff.remove(&s.id);
            frames.remove(&s.id);
        }
        if !want {
            backoff.remove(&s.id);
            warned.remove(&s.id);
            // No NDI delivery for this screen: hold no ~8.3MB frame for it either.
            frames.remove(&s.id);
            continue;
        }
        // Create the sender lazily (using the output dims — no per-screen compose to construct),
        // but not while backing off from a recent construction failure (avoids a per-frame
        // native re-init storm when the NDI runtime / name is persistently unavailable).
        if !senders.contains_key(&s.id) && backoff.get(&s.id).is_none_or(|&t| now >= t) {
            match video_sink::NdiOutput::new(&cfg.ndi_name, out_w, out_h, cfg.frame_rate) {
                Some(out) => {
                    senders.insert(s.id.clone(), out);
                    backoff.remove(&s.id);
                }
                None => {
                    backoff.insert(s.id.clone(), now + NDI_RETRY_BACKOFF);
                }
            }
        }
        // Compose + send ONLY when a real sink exists (feature on) — the default build (no
        // sink created) composes nothing here, so there is zero per-frame NDI cost. Delivery
        // goes through the dirty-gate + pacer: recompose only when the controller's live
        // generation moved past the cached frame, and only when `frame_rate` says a frame
        // is due — otherwise the cached frame is re-sent (NDI keeps receiving frames).
        if let Some(out) = senders.get_mut(&s.id) {
            ndi_deliver(
                frames,
                &s.id,
                c.live_generation(),
                cfg.frame_rate,
                now,
                || c.compose_screen(&s.id),
                |fb| out.send(fb),
            );
        }
    }
}

impl App {
    fn new() -> Self {
        // Open (or create) the session store; a storage failure degrades to an
        // in-memory session (the show must go on) with a clear message.
        let mut store = SessionStore::open();

        // Crash-loop breaker (FR-169): three rapid unstable launches mean
        // RECOVERY ITSELF is the failure — start clean, keep the session rows.
        let launch_guard = data_dir().map(|d| guard::LaunchGuard::new(&d));
        let launch_verdict = launch_guard.as_ref().map(guard::LaunchGuard::record_launch);
        // Keep the COUNT, not just the boolean: "started clean after 3 rapid restarts" is a
        // different message from "started clean", and the operator needs the number to judge
        // whether to investigate before the service starts.
        let crash_rapid_launches = match launch_verdict {
            Some(guard::LaunchVerdict::CrashLoop { rapid_launches }) => Some(rapid_launches as u32),
            _ => None,
        };
        let crash_loop = match launch_verdict {
            Some(guard::LaunchVerdict::CrashLoop { rapid_launches }) => {
                eprintln!(
                    "SelahCue: CRASH LOOP DETECTED ({rapid_launches} rapid restarts) — \
                     starting CLEAN with checkpointing DISABLED for this run, so the \
                     previous session stays untouched on disk. Once this run is stable, \
                     simply relaunch to resume the preserved session."
                );
                true
            }
            _ => false,
        };

        // Storage guard: checkpoint headroom is checked up front (and again
        // periodically in the autosave loop) — degradation is never silent, and
        // a critical startup status halts writes IMMEDIATELY (review 7ad-B).
        let startup_disk = data_dir().as_deref().and_then(guard::disk_status);
        if let Some(status) = startup_disk {
            report_disk(status);
        }
        let disk_critical = matches!(startup_disk, Some(guard::DiskStatus::Critical { .. }));

        let (plan, restored) = if crash_loop {
            (demo_plan(), None)
        } else {
            match store.load_session() {
                Some((plan, snap)) => (plan, Some(snap)),
                None => (demo_plan(), None),
            }
        };
        // Crash-loop "resumable" (86ajy0hxg): a read-only existence peek, deliberately NOT
        // `store.load_session()` (which sets `self.plan_id` as a side effect — see
        // `has_preserved_session`'s own doc) — this process must not point its OWN saves at the
        // preserved row until `Command::Resume` actually asks for it. Only meaningful when
        // `crash_loop` is true; the non-crash-loop path already resumed automatically above, so
        // there is nothing left pending to offer.
        let crash_resumable = crash_loop && store.has_preserved_session();
        // Make sure the plan rows exist before the first snapshot references them —
        // except in clean mode (the preserved session must stay untouched, and no
        // orphan demo rows may accumulate across breaker trips) or on a critical
        // disk (no writes at all below the floor).
        if !crash_loop && !disk_critical {
            store.ensure_plan(&plan);
        }
        let first_run = restored.is_none() && !crash_loop;

        let controller = Arc::new(Mutex::new(LiveController::new(
            plan,
            OUTPUT_W,
            OUTPUT_H,
            Theme::dark(),
        )));

        if let Ok(mut c) = controller.lock() {
            // Durable transcript side-channel (86akcfftu): best-effort, degrades to the
            // controller's default no-op sink on any failure (no data dir, storage
            // unavailable) — exactly like every other storage degradation in this file.
            if let Some(sink) = SessionStore::open_transcript_sink() {
                c.set_transcript_sink(sink);
            }
            // Durable sermon-note-draft store (86akgqdv0; PR #33 review, Sana F1
            // remediation): same best-effort degradation as the transcript sink above — a
            // sibling seam, not a dependency of it.
            if let Some(store) = SessionStore::open_sermon_note_store() {
                c.set_sermon_note_store(store);
            }
            // Autosave-slot store (FR-005 "last-3"; 86ajy0hxg): same best-effort degradation.
            if let Some(store) = SessionStore::open_autosave_store() {
                c.set_autosave_store(store);
            }
        }
        if let Ok(mut c) = controller.lock() {
            // Publish health from the FIRST frame, so the very first operator view already
            // carries it. Waiting for the first autosave tick would leave a window in which the
            // console has no health at all — and "no health yet" is indistinguishable to a
            // client from "this host does not report health".
            let (disk_tag, disk_available) = storage_tag(startup_disk);
            c.set_storage_health(disk_tag, disk_available, disk_critical || crash_loop);
            c.set_session_health(
                restored.is_some(),
                crash_loop,
                crash_rapid_launches,
                store.last_save_error(),
                crash_resumable,
            );
            // CON-158: a build fact, never a runtime condition, so it is set once here and
            // never revisited (unlike storage/session health, which the host re-reports as
            // conditions change).
            c.set_ndi_available(video_sink::TRANSMIT_AVAILABLE);
            // Load the user config (the saved-theme library + the per-screen theme map)
            // BEFORE restoring the session, so a per-item / per-screen override that
            // references a SAVED theme resolves as content is re-staged (86ajq69ft). The
            // library loads first (a per-screen name may reference it); the per-screen map
            // applies `main` (a no-op recompose while nothing is staged) so `restore()`
            // then composes the restored content with every override in place.
            c.load_saved_themes(store.load_saved_themes());
            // The screen registry loads BEFORE the per-screen theme map, so a virtual
            // screen's theme survives (`load_screen_themes` keeps only themes for a screen
            // in the registry). An empty/corrupt registry recovers to the built-ins.
            c.load_screen_registry(store.load_screens());
            c.load_screen_themes(store.load_screen_themes());
            // Per-output config loads AFTER the registry (it keeps only configs for a screen
            // in the registry) so a deleted screen's stale config is discarded, never crashes.
            c.load_output_configs(store.load_screen_configs());
            match &restored {
                Some(snap) => {
                    // Crash/restart recovery: rebuild the exact live state.
                    c.restore(snap);
                    println!("  Session restored (crash/restart recovery).");
                }
                None => {
                    // First run: show the first item so the window isn't blank.
                    let _ = c.apply(&Command::Next);
                    let _ = c.apply(&Command::GoLive);
                }
            }
        }

        // First run: write the initial session row NOW so the seeded plan is
        // referenced immediately (a run that dies early must not orphan plan rows).
        // Skipped in clean mode / on a critical disk — no writes in either state.
        if first_run && !disk_critical {
            if let Ok(c) = controller.lock() {
                store.save_session(&c.snapshot(Instant::now()));
            }
        }

        // Start the LAN control server so remote controllers can drive this window.
        let remote = Arc::new(RemoteShared {
            registry: Arc::new(AsyncMutex::new(SessionRegistry::new())),
            lan: OnceLock::new(),
            active_code: Mutex::new(None),
        });
        start_remote_control(controller.clone(), remote.clone());

        App {
            main: None,
            stage: None,
            controller,
            remote,
            next_frame: None,
            keymap: Keymap::new(),
            displays: Vec::new(),
            assignments: Vec::new(),
            launch_guard,
            launched_at: Instant::now(),
            stable_marked: false,
            last_disk_check: Instant::now(),
            disk_critical,
            last_disk_status: startup_disk,
            session_restored: restored.is_some(),
            crash_rapid_launches,
            clean_mode: crash_loop,
            crash_resumable,
            identify_frames: None,
            modifiers: winit::keyboard::ModifiersState::empty(),
            store,
            last_autosave: Instant::now(),
            last_slot_push: Instant::now(),
            smoke: smoke_mode_requested(
                std::env::args(),
                std::env::var_os("SELAHCUE_SMOKE").is_some(),
            ),
            smoke_done: false,
            ndi_outputs: std::collections::HashMap::new(),
            ndi_backoff: std::collections::HashMap::new(),
            ndi_warned: std::collections::HashSet::new(),
            ndi_frames: std::collections::HashMap::new(),
            open_failures: OpenFailures::default(),
            output_faults: FaultLatch::default(),
        }
    }

    /// Report the outputs (role → window/display) + attached displays to the
    /// controller so every operator surface can render the OUTPUTS panel.
    /// Re-run on window Moved/Resized: fullscreen transitions land async, so
    /// the truth arrives with those events, not with the assignment call.
    fn publish_output_status(&self) {
        let assignments = &self.assignments;
        let assigned = |role: &str| assignments.iter().any(|(r, _)| r == role);
        let assigned_key = |role: &str| {
            assignments
                .iter()
                .find(|(r, _)| r == role)
                .map(|(_, k)| k.clone())
        };
        let display_of = |renderer: &Option<Renderer>| {
            renderer
                .as_ref()
                .and_then(|r| r.window.current_monitor())
                .and_then(|m| m.name())
        };
        // Sample monitor attachment HERE (this runs on Moved/Resized, not per frame) so the
        // telemetry signal-health is honest without a per-present windowing query.
        let monitor_attached = |renderer: &Option<Renderer>| {
            renderer
                .as_ref()
                .is_some_and(|r| r.window.current_monitor().is_some())
        };
        let size_of = |renderer: &Option<Renderer>| {
            renderer
                .as_ref()
                .map(|r| {
                    let s = r.window.inner_size();
                    (s.width, s.height)
                })
                .unwrap_or((OUTPUT_W, OUTPUT_H))
        };
        let (mw, mh) = size_of(&self.main);
        let (sw, sh) = size_of(&self.stage);
        let outputs = vec![
            OutputStatusView {
                role: "main".into(),
                display: display_of(&self.main),
                width: mw,
                height: mh,
                assigned: assigned("main"),
                assigned_key: assigned_key("main"),
                fps: telemetry_of(&self.main).map(|t| t.fps()),
                dropped_frames: telemetry_of(&self.main).map(|t| t.dropped_frames),
                signal: telemetry_of(&self.main)
                    .map(|t| t.signal_label(monitor_attached(&self.main)).to_string()),
            },
            OutputStatusView {
                role: "stage".into(),
                display: display_of(&self.stage),
                width: sw,
                height: sh,
                assigned: assigned("stage"),
                assigned_key: assigned_key("stage"),
                fps: telemetry_of(&self.stage).map(|t| t.fps()),
                dropped_frames: telemetry_of(&self.stage).map(|t| t.dropped_frames),
                signal: telemetry_of(&self.stage)
                    .map(|t| t.signal_label(monitor_attached(&self.stage)).to_string()),
            },
        ];
        if let Ok(mut c) = self.controller.lock() {
            c.set_output_status(outputs, self.displays.clone());
        }
    }

    /// Apply any remotely requested display assignments. The display must exist
    /// RIGHT NOW to be accepted: a stale key is dropped without persisting and —
    /// critically — without touching the (possibly live, fullscreen) window.
    ///
    /// The monitor list comes from the event loop, not from a window, so a screen that is
    /// currently CLOSED (disabled) can still be assigned a display: the assignment persists
    /// and [`open_screen`](Self::open_screen) honours it when the screen is switched back
    /// on. Only the immediate fullscreen move needs a live window.
    fn apply_pending_assignments(&mut self, event_loop: &ActiveEventLoop) {
        let pending = match self.controller.lock() {
            Ok(mut c) => c.take_pending_assignments(),
            Err(_) => return,
        };
        if pending.is_empty() {
            return;
        }
        let monitors: Vec<winit::monitor::MonitorHandle> =
            event_loop.available_monitors().collect();
        let facts: Vec<MonitorFacts> = monitors.iter().map(monitor_facts).collect();
        let keyed = display_keys(&facts);
        for (role, key) in &pending {
            let renderer = match role.as_str() {
                "main" => self.main.as_ref(),
                _ => self.stage.as_ref(),
            };
            let target = monitors
                .iter()
                .zip(keyed.iter())
                .find(|(_, (_, k))| k == key)
                .map(|(m, _)| m.clone());
            match target {
                Some(monitor) => {
                    // Persist only what verifiably exists (a bad key must never
                    // overwrite a working venue profile).
                    self.store.save_output_assignment(role, key);
                    self.assignments.retain(|(r2, _)| r2 != role);
                    self.assignments.push((role.clone(), key.clone()));
                    if let Some(r) = renderer {
                        r.window
                            .set_fullscreen(Some(winit::window::Fullscreen::Borderless(Some(
                                monitor,
                            ))));
                    }
                }
                None => {
                    eprintln!(
                        "SelahCue: display '{key}' for the {role} output is not attached; \
                         assignment ignored (window and saved profile unchanged)."
                    );
                }
            }
        }
        self.publish_output_status();
    }

    /// Drain and act on a pending crash-loop `Resume`/`StartClean` decision (FR-169,
    /// FR-074/075; 86ajy0hxg). This is the ONE place that performs the host-side I/O the
    /// controller cannot reach itself (`SessionStore`/`LaunchGuard`) — the controller only ever
    /// records the operator's intent (see `LiveController::take_pending_crash_decision`).
    ///
    /// `Resume` re-reads the preserved session (untouched on disk because `clean_mode` paused
    /// checkpointing) and swaps it into the already-running controller; `StartClean` leaves the
    /// already-running clean session exactly as booted and persists it going forward. Both
    /// re-enable checkpointing and forgive the launch-stability journal (`mark_stable`) so a
    /// resolved trip does not compound into the next launch's count.
    fn handle_crash_decision(&mut self, now: Instant) {
        let decision = self
            .controller
            .lock()
            .ok()
            .and_then(|mut c| c.take_pending_crash_decision());
        let Some(decision) = decision else {
            return;
        };
        match decision {
            CrashDecision::Resume => {
                // Re-derive the preserved session the same way boot would have — `clean_mode`
                // guaranteed nothing wrote over it since. `load_session` (unlike the read-only
                // `has_preserved_session` peek used at boot) correctly sets `self.plan_id` to
                // the preserved plan's row, which is exactly right now: going forward, normal
                // autosave writes should target THAT row, because this IS the resumed session.
                match self.store.load_session() {
                    Some((plan, snap)) => {
                        if let Ok(mut c) = self.controller.lock() {
                            c.resume_preserved(plan, &snap);
                        }
                        self.session_restored = true;
                        println!("  Session resumed (crash-loop recovery, operator confirmed).");
                    }
                    None => {
                        eprintln!(
                            "SelahCue: Resume requested but no preserved session was found; \
                             continuing on the already-running clean session."
                        );
                    }
                }
            }
            CrashDecision::StartClean => {
                // Nothing to swap — the already-running session IS the clean start. Persist its
                // plan now (skipped at boot specifically because clean_mode was in effect), so
                // the row exists before checkpointing resumes below.
                if let Ok(c) = self.controller.lock() {
                    self.store.ensure_plan(c.plan());
                }
                println!("  Starting clean confirmed (crash-loop recovery, operator confirmed).");
            }
        }
        self.clean_mode = false;
        self.crash_resumable = false;
        if let Some(g) = self.launch_guard.as_ref() {
            g.mark_stable();
        }
        self.last_autosave = now;
    }

    /// Drain and act on a pending `Command::RestoreAutosave` slot (FR-005/FR-079; 86ajy0hxg).
    /// Mirrors [`handle_crash_decision`](Self::handle_crash_decision) exactly, and for the same
    /// reason PLUS one more (Vera, PR #102 performance review — B-1): resolving a slot means an
    /// `integrity_check` over the WHOLE store, which can run into the hundreds of milliseconds
    /// on a realistic install. The earlier shape ran that check INSIDE `LiveController::apply()`,
    /// which held the same `Mutex<LiveController>` the render/present loop locks every frame,
    /// stalling audience output for the full duration. This drains the controller's recorded
    /// INTENT with a brief lock, resolves the slot on `self.store`'s own connection with NO lock
    /// held, and takes the lock again only to apply the already-decoded result (a fast,
    /// in-memory `resume_preserved` call) — never both at once.
    fn handle_pending_restore(&mut self) {
        let slot = self
            .controller
            .lock()
            .ok()
            .and_then(|mut c| c.take_pending_restore_slot());
        let Some(slot) = slot else {
            return;
        };
        match self.store.load_autosave_slot(slot) {
            Ok(Some((plan, snap))) => {
                if let Ok(mut c) = self.controller.lock() {
                    c.resume_preserved(plan, &snap);
                }
                println!("  Autosave slot {slot} restored.");
            }
            Ok(None) => {
                eprintln!(
                    "SelahCue: RestoreAutosave requested slot {slot}, which no longer exists \
                     (already pruned, or never existed); nothing was restored."
                );
            }
            Err(e) => {
                eprintln!("SelahCue: could not restore autosave slot {slot} ({e}).");
            }
        }
    }

    /// Push the host's storage + session health into the operator view.
    ///
    /// These were previously reported by `eprintln!` only, so nobody actually running a service
    /// ever saw them: autosave could be failing for an entire meeting, or checkpointing halted
    /// on a full disk, with the console showing nothing wrong.
    ///
    /// Takes the controller lock briefly and drops it, so it is safe to call from paths that do
    /// not already hold it. Callers that DO hold the lock must use the setters directly.
    fn publish_health(&mut self) {
        let (status, available) = storage_tag(self.last_disk_status);
        let restored = self.session_restored;
        let crash_loop = self.clean_mode;
        let rapid = self.crash_rapid_launches;
        let autosave_error = self.store.last_save_error().map(str::to_string);
        if let Ok(mut c) = self.controller.lock() {
            c.set_storage_health(
                status,
                available,
                // Checkpoints are halted below the floor AND in breaker-tripped clean mode,
                // where the preserved session must stay untouched. Both are "not persisting",
                // which is what the operator needs to know.
                self.disk_critical || self.clean_mode,
            );
            c.set_session_health(
                restored,
                crash_loop,
                rapid,
                autosave_error.as_deref(),
                self.crash_resumable,
            );
        }
    }

    /// Autosave: persist the session when state changed (throttled to ~1/s) and
    /// periodically while a countdown runs (so its elapsed stays fresh on disk).
    fn autosave(&mut self, now: Instant) {
        // Drain any pending crash-loop decision FIRST, so a Resume/StartClean made this tick is
        // already reflected in this SAME tick's health publish immediately below (86ajy0hxg).
        self.handle_crash_decision(now);
        // Drain any pending RestoreAutosave slot — see `handle_pending_restore`'s own doc for
        // why this must never run inline inside `LiveController::apply()`.
        self.handle_pending_restore();
        // Publish health FIRST, before any early return below.
        //
        // A halted-checkpoint state is precisely when the operator most needs to be told, and
        // this function returns early in exactly that case. Ordering the publish first makes
        // that impossible to get wrong, rather than correct-until-someone-adds-another-return:
        // there is no branch between here and the top. The cost is that a disk verdict is at
        // most one frame stale, which is nothing against a once-a-minute check.
        self.publish_health();
        // Crash-loop breaker: surviving to STABLE_AFTER forgives this launch.
        if !self.stable_marked && now.duration_since(self.launched_at) >= guard::STABLE_AFTER {
            self.stable_marked = true;
            if let Some(g) = self.launch_guard.as_ref() {
                g.mark_stable();
            }
        }
        // Storage guard: re-check headroom once a minute; halting/resuming
        // checkpoint writes is always reported.
        if now.duration_since(self.last_disk_check) >= Duration::from_secs(60) {
            self.last_disk_check = now;
            match data_dir().as_deref().and_then(guard::disk_status) {
                Some(status) => {
                    let critical = matches!(status, guard::DiskStatus::Critical { .. });
                    if critical != self.disk_critical
                        || !matches!(status, guard::DiskStatus::Ok { .. })
                    {
                        report_disk(status);
                    }
                    if self.disk_critical && !critical {
                        eprintln!("SelahCue: disk headroom recovered — checkpoints resumed.");
                    }
                    self.disk_critical = critical;
                    self.last_disk_status = Some(status);
                }
                None if self.disk_critical => {
                    self.last_disk_status = None;
                    // Free space unknowable while halted: stay safe, keep saying so.
                    eprintln!(
                        "SelahCue: cannot determine free disk space — checkpoint \
                         writes remain paused."
                    );
                }
                None => {
                    self.last_disk_status = None;
                }
            }
        }
        // NFR-024 host fault producers. `Presenter::inject_fault` / `LiveController::report_fault`
        // are the seam that makes a held audience output visible to the operator; these two
        // calls are the only things in the shipped host that fire it, so without them
        // `output_health` is permanently `{"held":false}` however badly the host is doing.
        //
        // Both signals are LEVELS and this function runs every frame (~60 Hz), so both go
        // through `report_fault_edge`, which reports the transition INTO the fault and nothing
        // afterwards — see `FaultLatch`. Placed after the storage check above so the disk
        // verdict is this frame's, and before the halted-checkpoint early return below, which
        // triggers in exactly the full-disk case being reported. The surface telemetry is one
        // frame old (redraws are requested after this call), which at 16 ms is immaterial.
        report_fault_edge(
            &mut self.output_faults,
            &self.controller,
            Fault::GpuDeviceLost,
            surface_fault_active(telemetry_of(&self.main)),
        );
        report_fault_edge(
            &mut self.output_faults,
            &self.controller,
            Fault::DiskFull,
            disk_fault_active(self.last_disk_status),
        );
        if self.disk_critical || self.clean_mode {
            // Critical disk: never risk corrupting a full store. Clean mode:
            // the preserved session must stay untouched. State stays in memory.
            return;
        }
        let Ok(mut c) = self.controller.lock() else {
            return;
        };
        // The saved-theme library (86ajq4xmy) persists immediately on any change
        // (rare, operator-driven Save/Delete) — it is user config, independent of the
        // session snapshot, so it saves outside the plan/state throttle below.
        if c.take_saved_themes_dirty() {
            let themes: Vec<(String, String)> = c
                .saved_themes()
                .iter()
                .map(|(n, j)| (n.clone(), j.clone()))
                .collect();
            if !self.store.save_saved_themes(&themes) {
                c.mark_saved_themes_dirty(); // failed write: retry next frame
            }
        }
        // The per-screen theme map (86ajq321k) persists immediately on any change too.
        if c.take_screen_themes_dirty() {
            let themes: Vec<(String, String)> = c
                .screen_themes()
                .iter()
                .map(|(s, t)| (s.clone(), t.clone()))
                .collect();
            if !self.store.save_screen_themes(&themes) {
                c.mark_screen_themes_dirty(); // failed write: retry next frame
            }
        }
        // The screen registry (Screens page — dynamic registry) persists on any
        // enable/add/delete, so the operator's screen set survives a restart.
        if c.take_screen_registry_dirty() {
            let screens: Vec<(String, String, bool, bool)> = c
                .screen_registry()
                .iter()
                .map(|s| {
                    (
                        s.id.clone(),
                        s.role.as_tag().to_string(),
                        s.enabled,
                        s.deletable,
                    )
                })
                .collect();
            if !self.store.save_screens(&screens) {
                c.mark_screen_registry_dirty(); // failed write: retry next frame
            }
        }
        // The per-screen OUTPUT CONFIG (Screens page inspector) persists on any change, so
        // orientation / scaling / mirror / delay / frame-rate / safe-area / layer visibility
        // survive a restart (venue output config, like the display assignment).
        if c.take_output_configs_dirty() {
            let configs: Vec<(String, OutputConfigView)> = c
                .output_configs()
                .iter()
                .map(|(s, cfg)| (s.clone(), cfg.clone()))
                .collect();
            if !self.store.save_screen_configs(&configs) {
                c.mark_output_configs_dirty(); // failed write: retry next frame
            }
        }
        // Plan edits persist immediately (rare, operator-driven actions) — and the
        // session snapshot goes with them, bypassing the throttle: the on-disk pair
        // (plan, indices) must never be split across a crash window.
        if c.take_plan_dirty() {
            if !self.store.save_plan(c.plan()) {
                c.mark_plan_dirty(); // failed write: retry next frame
            }
            c.take_state_dirty(); // superseded by the immediate joint save below
            let snap = c.snapshot(now);
            if self.store.save_session(&snap) {
                self.last_autosave = now;
                // Autosave-slot capture (FR-005 "last-3"; 86ajy0hxg), gated by
                // AUTOSAVE_SLOT_INTERVAL so the bounded 3-slot ring holds distinct instants
                // rather than near-duplicates. Inlined (not a `&mut self` helper): `c` already
                // borrows `self.controller`, and only field-disjoint access compiles here.
                if now.duration_since(self.last_slot_push) >= AUTOSAVE_SLOT_INTERVAL {
                    self.last_slot_push = now;
                    self.store.push_autosave_slot(c.plan(), &snap, now_ms());
                }
            } else {
                c.mark_state_dirty();
            }
            return;
        }
        let dirty = c.take_state_dirty();
        let periodic =
            c.timer_active() && now.duration_since(self.last_autosave) >= TIMER_AUTOSAVE_INTERVAL;
        if (dirty || periodic) && now.duration_since(self.last_autosave) >= AUTOSAVE_MIN_INTERVAL {
            let snap = c.snapshot(now);
            if self.store.save_session(&snap) {
                self.last_autosave = now;
                if now.duration_since(self.last_slot_push) >= AUTOSAVE_SLOT_INTERVAL {
                    self.last_slot_push = now;
                    self.store.push_autosave_slot(c.plan(), &snap, now_ms());
                }
            } else if dirty {
                // The write failed: the change is still unpersisted — retry next frame.
                c.mark_state_dirty();
            }
        } else if dirty {
            // Too soon after the last write: keep the flag so the next frame saves.
            c.mark_state_dirty();
        }
    }

    /// `P`: toggle pairing mode — offer a fresh single-use code (2-minute TTL) and
    /// show the invite QR on the stage output + as ASCII in the terminal. Toggling
    /// off **withdraws** the code from the registry (a cancelled code must die
    /// immediately, e.g. when the operator suspects the QR was photographed).
    fn toggle_pairing(&self) {
        let Ok(mut c) = self.controller.lock() else {
            return;
        };
        if c.pairing_qr_active() {
            c.clear_pairing_qr();
            self.withdraw_active_code();
            println!("  Pairing mode off — the code is no longer redeemable.");
            return;
        }
        let Some((port, pin_hex)) = self.remote.lan.get().cloned() else {
            eprintln!("  Pairing unavailable: the control server is not running.");
            return;
        };
        let code = generate_pairing_code();
        if code.is_empty() {
            eprintln!("  Pairing unavailable: could not generate a code.");
            return;
        }
        let now = Instant::now();
        {
            let mut reg = self.remote.registry.blocking_lock();
            // Housekeeping: reclaim any expired offers + idle sessions so both maps stay
            // bounded (audit #8: an idle session self-reclaims after SESSION_IDLE_TTL).
            reg.prune_expired(now);
            reg.prune_idle(now, selahcue_lan::session::SESSION_IDLE_TTL);
            reg.offer_pairing(code.clone(), Role::Producer, now, PAIRING_TTL);
        }
        if let Ok(mut slot) = self.remote.active_code.lock() {
            *slot = Some(code.clone());
        }
        let host = lan_ip();
        if host.is_loopback() {
            eprintln!(
                "  WARNING: no LAN-facing interface found — the invite uses 127.0.0.1, \
                 so only clients on THIS machine can pair."
            );
        }
        let invite = PairingInvite {
            host: host.to_string(),
            port,
            pin_hex,
            code: code.clone(),
        };
        match invite.to_uri() {
            Some(uri) => {
                print_pairing_block(&uri, &code);
                c.show_pairing_qr(uri, now + PAIRING_TTL);
            }
            None => eprintln!("  Pairing unavailable: could not encode the invite."),
        }
    }

    /// Remove the currently offered code (if any) from the registry.
    fn withdraw_active_code(&self) {
        let code = self
            .remote
            .active_code
            .lock()
            .ok()
            .and_then(|mut g| g.take());
        if let Some(code) = code {
            self.remote.registry.blocking_lock().withdraw(&code);
        }
    }

    /// The renderer whose window matches `id`, if any.
    fn renderer_for(&mut self, id: WindowId) -> Option<&mut Renderer> {
        if self.main.as_ref().is_some_and(|r| r.window.id() == id) {
            self.main.as_mut()
        } else if self.stage.as_ref().is_some_and(|r| r.window.id() == id) {
            self.stage.as_mut()
        } else {
            None
        }
    }

    /// Which built-in screen owns the window `id`, if any.
    fn window_role_of(&self, id: WindowId) -> Option<WindowRole> {
        if self.main.as_ref().is_some_and(|r| r.window.id() == id) {
            Some(WindowRole::Main)
        } else if self.stage.as_ref().is_some_and(|r| r.window.id() == id) {
            Some(WindowRole::Stage)
        } else {
            None
        }
    }

    /// Whether this role's window currently exists.
    fn is_window_open(&self, role: WindowRole) -> bool {
        match role {
            WindowRole::Main => self.main.is_some(),
            WindowRole::Stage => self.stage.is_some(),
        }
    }

    /// The monitor this role is assigned to, if that display is attached RIGHT NOW.
    /// Re-resolved per open (monitors come and go between opens), same keying as
    /// [`apply_pending_assignments`](Self::apply_pending_assignments).
    fn assigned_monitor(
        &self,
        event_loop: &ActiveEventLoop,
        role: WindowRole,
    ) -> Option<winit::monitor::MonitorHandle> {
        let key = self
            .assignments
            .iter()
            .find(|(r, _)| r == role.screen_id())
            .map(|(_, k)| k.clone())?;
        let monitors: Vec<winit::monitor::MonitorHandle> =
            event_loop.available_monitors().collect();
        let facts: Vec<MonitorFacts> = monitors.iter().map(monitor_facts).collect();
        let keyed = display_keys(&facts);
        monitors
            .iter()
            .zip(keyed.iter())
            .find(|(_, (_, k))| *k == key)
            .map(|(m, _)| m.clone())
    }

    /// Open a built-in screen's OS window: create it (honouring the persisted per-role
    /// display assignment as borderless fullscreen), mark the screen enabled, and publish
    /// truthful status.
    ///
    /// A creation failure is logged and recorded IN MEMORY by [`record_open_outcome`] — the
    /// screen stays enabled in the registry (a transient GPU hiccup is not an operator
    /// setting and must never be saved as one), and the in-memory flag is what stops the
    /// reconcile retrying ~60x/s. The process keeps serving the other window rather than
    /// dying.
    fn open_screen(&mut self, event_loop: &ActiveEventLoop, role: WindowRole) {
        if self.is_window_open(role) {
            return;
        }
        let mut attrs = Window::default_attributes().with_title(role.title());
        if let Some(monitor) = self.assigned_monitor(event_loop, role) {
            // Borderless fullscreen on the assigned display (spike-S4 path);
            // unassigned keeps the windowed default.
            attrs =
                attrs.with_fullscreen(Some(winit::window::Fullscreen::Borderless(Some(monitor))));
        }
        let renderer = match event_loop.create_window(attrs) {
            Ok(w) => Renderer::new(Arc::new(w)),
            Err(e) => Err(format!("create window: {e}")),
        };
        let outcome = match renderer {
            Ok(r) => {
                match role {
                    WindowRole::Main => self.main = Some(r),
                    WindowRole::Stage => self.stage = Some(r),
                }
                Ok(())
            }
            Err(e) => Err(e),
        };
        record_open_outcome(&self.controller, &mut self.open_failures, role, outcome);
        // A window set change invalidates the cached identify overlay.
        self.identify_frames = None;
        self.publish_output_status();
    }

    /// Close a built-in screen's OS window. Dropping the [`Renderer`] drops the last
    /// `Arc<Window>` — which IS the OS window closing — then the screen is marked disabled
    /// and status is republished so the operator's pill stays truthful.
    ///
    /// This is the single code path shared by the Screens toggle and the window's own close
    /// button, so the two can never drift. The process stays alive: it still owns the other
    /// window, the LAN server, and the presentation state paired controllers depend on.
    fn close_screen(&mut self, role: WindowRole) {
        match role {
            WindowRole::Main => self.main = None,
            WindowRole::Stage => self.stage = None,
        }
        set_screen_enabled(&self.controller, role, false);
        // Switching a screen off clears any recorded open failure for it, so switching it
        // back on always gets a fresh attempt.
        self.open_failures.set(role, false);
        self.identify_frames = None;
        self.publish_output_status();
    }

    /// Make the OS windows match the screen registry. `resumed()` runs only once, so THIS
    /// is what makes "toggle a screen back on" relaunch its window. The decision itself is
    /// the pure [`reconcile_windows`]; this only performs it.
    fn reconcile_screen_windows(&mut self, event_loop: &ActiveEventLoop) {
        // The Arc is cloned so the registry read and the `open_failures` update are not two
        // borrows of `self` at once; the lock is still held for exactly the decision.
        let controller = self.controller.clone();
        let actions = {
            let Ok(c) = controller.lock() else {
                return;
            };
            reconcile_windows(
                c.screen_registry()
                    .iter()
                    .map(|s| (s.id.as_str(), s.enabled)),
                self.main.is_some(),
                self.stage.is_some(),
                &mut self.open_failures,
            )
        };
        for action in actions {
            match action {
                WindowAction::Open(role) => self.open_screen(event_loop, role),
                WindowAction::Close(role) => self.close_screen(role),
            }
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        // Physical displays (FR-040): a stable, collision-free key per monitor.
        let monitors: Vec<winit::monitor::MonitorHandle> =
            event_loop.available_monitors().collect();
        let facts: Vec<MonitorFacts> = monitors.iter().map(monitor_facts).collect();
        let keyed = display_keys(&facts);
        self.displays = monitors
            .iter()
            .zip(keyed.iter())
            .map(|(m, (name, key))| {
                let size = m.size();
                DisplayView {
                    key: key.clone(),
                    name: name.clone(),
                    width: size.width,
                    height: size.height,
                }
            })
            .collect();
        self.assignments = self.store.load_output_assignments();
        // Create a window only for a screen that is currently ENABLED, via the same
        // reconcile the Screens toggle and the close button use — one code path, so a
        // screen the operator left off last service does not come back on relaunch.
        self.reconcile_screen_windows(event_loop);
        self.publish_output_status();
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        match event {
            // Closing a window while ANOTHER remains open closes just THAT SCREEN — it is the
            // Screens toggle by another name, so it runs the same `close_screen`, and the
            // process stays up because it owns the other window, the LAN server and the
            // presentation state that paired mobile controllers depend on.
            //
            // Closing the LAST window quits. The Cmd-Q / Ctrl-Q chord arrives through this
            // very handler, so it only ever reaches a focused window (see
            // `quit_chord_reachable`): a windowless process could not be quit at all, and an
            // operator who clicks both close buttons — the gesture that quit before this
            // lifecycle existed — would have to kill it. That last close is a QUIT gesture,
            // not a screen edit, so it deliberately does NOT run `close_screen`: writing
            // `enabled = false` on the way out would leave the next launch with no window to
            // open, presenting nothing.
            WindowEvent::CloseRequested => {
                if let Some(role) = self.window_role_of(id) {
                    match close_button_outcome(self.main.is_some(), self.stage.is_some(), role) {
                        CloseOutcome::CloseScreen => self.close_screen(role),
                        CloseOutcome::Quit => event_loop.exit(),
                    }
                }
            }
            WindowEvent::ModifiersChanged(m) => self.modifiers = m.state(),
            WindowEvent::Resized(size) => {
                if let Some(renderer) = self.renderer_for(id) {
                    renderer.resize(size.width, size.height);
                    renderer.window.request_redraw();
                }
                // Fullscreen moves land async: the truthful monitor/size arrive
                // here. Stale identify frames would render at the old size.
                self.identify_frames = None;
                self.publish_output_status();
            }
            WindowEvent::Moved(_) => {
                self.publish_output_status();
            }
            WindowEvent::RedrawRequested => {
                // Identify (FR-040): while active, each window blits its number
                // INSTEAD of its scene — presentation state is untouched, so the
                // outputs resume by themselves when the overlay expires.
                let identify_active = self
                    .controller
                    .lock()
                    .ok()
                    .and_then(|c| c.identify_until())
                    .is_some_and(|t| Instant::now() < t);
                if identify_active {
                    if self.identify_frames.is_none() {
                        let theme = selahcue_present::StageTheme::dark();
                        let compose = |n: u32, r: &Renderer| {
                            let size = r.window.inner_size();
                            selahcue_engine::raster::render(&selahcue_present::compose_identify(
                                n,
                                theme.identify_bg,
                                theme.identify_marker,
                                size.width.max(1),
                                size.height.max(1),
                            ))
                        };
                        // Compose per EXISTING window: a disabled screen has none, and
                        // identify must still work for the outputs that are open.
                        self.identify_frames = Some((
                            self.main.as_ref().map(|m| compose(1, m)),
                            self.stage.as_ref().map(|st| compose(2, st)),
                        ));
                    }
                    let role = self.window_role_of(id);
                    if let Some((main_frame, stage_frame)) = self.identify_frames.as_ref() {
                        match role {
                            Some(WindowRole::Main) => {
                                if let (Some(frame), Some(r)) = (main_frame, self.main.as_mut()) {
                                    r.render(frame);
                                }
                            }
                            Some(WindowRole::Stage) => {
                                if let (Some(frame), Some(r)) = (stage_frame, self.stage.as_mut()) {
                                    r.render(frame);
                                }
                            }
                            // A redraw for a window we just closed: nothing to draw.
                            None => {}
                        }
                        return;
                    }
                } else {
                    self.identify_frames = None;
                }
                let Ok(c) = self.controller.lock() else {
                    return;
                };
                // Each window presents its own surface from the same shared live state.
                // A DISABLED built-in screen has NO window at all (see `close_screen`), so
                // there is nothing to mute here — a redraw only ever arrives for a window
                // that exists. Killing the picture while KEEPING the window is Blackout.
                let now = Instant::now();
                // Match on the window that raised this redraw. A stale event for a window
                // closed a moment ago matches neither and is dropped — it must never present
                // one screen's composition on the other's surface.
                match self.window_role_of(id) {
                    Some(WindowRole::Main) => {
                        let live = c.presenter().live_output();
                        let cfg = c.output_config("main");
                        let presented = self
                            .main
                            .as_mut()
                            .map(|r| r.present_output(live, &cfg, now))
                            .unwrap_or(false);
                        // Smoke mode (86ajpevzp): the main window produced a real frame —
                        // report time-to-first-frame (from App init) and exit cleanly (0).
                        if self.smoke && presented && !self.smoke_done {
                            self.smoke_done = true;
                            let ms = self.launched_at.elapsed().as_millis();
                            println!(
                                "SMOKE OK: main output window presented its first frame in {ms} ms (from App init)"
                            );
                            event_loop.exit();
                        }
                    }
                    Some(WindowRole::Stage) => {
                        let stage_live = c.stage_output();
                        let cfg = c.output_config("stage");
                        if let Some(r) = self.stage.as_mut() {
                            r.present_output(stage_live, &cfg, now);
                        }
                    }
                    None => {}
                }
            }
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key,
                        state: ElementState::Pressed,
                        repeat,
                        ..
                    },
                ..
            } => {
                // OS auto-repeat is never a deliberate action: a held Esc must
                // not complete the double-tap, a held B must not strobe.
                if repeat {
                    return;
                }
                // QUIT (Cmd-Q on macOS, Ctrl-Q elsewhere). Closing a window now closes just
                // that screen, so this chord is the deliberate way to stop the output
                // process — checked before everything else and never mapped to an action.
                let character = match &logical_key {
                    Key::Character(c) => Some(c.as_str()),
                    _ => None,
                };
                if is_quit_chord(
                    character,
                    self.modifiers.super_key(),
                    self.modifiers.control_key(),
                    cfg!(target_os = "macos"),
                ) {
                    event_loop.exit();
                    return;
                }
                // Host-local pairing keys first (not canonical live actions).
                // They still disarm a pending double-Esc — the keymap contract
                // is that ANY intervening key does (Esc, Y, Esc must never clear).
                match &logical_key {
                    Key::Character(c) if c.eq_ignore_ascii_case("p") => {
                        self.keymap.disarm();
                        self.toggle_pairing();
                        return;
                    }
                    Key::Character(c) if c.eq_ignore_ascii_case("i") => {
                        self.keymap.disarm();
                        if let Ok(mut ctl) = self.controller.lock() {
                            ctl.trigger_identify();
                        }
                        return;
                    }
                    _ => {}
                }
                // Canonical map (UX-CANONICAL §1). NOTE: `Esc` no longer quits —
                // double-`Esc` is Clear-all; quit with Cmd-Q / Ctrl-Q (above).
                let key = match logical_key {
                    Key::Named(NamedKey::Escape) => Some(KeyPress::Escape),
                    Key::Named(NamedKey::Space) => Some(KeyPress::Space),
                    Key::Named(NamedKey::Enter) => Some(KeyPress::Enter),
                    Key::Named(NamedKey::Backspace) => Some(KeyPress::Backspace),
                    Key::Named(NamedKey::ArrowLeft) => Some(KeyPress::ArrowLeft),
                    Key::Named(NamedKey::ArrowRight) => Some(KeyPress::ArrowRight),
                    Key::Character(c) => c.chars().next().map(KeyPress::Char),
                    _ => None,
                };
                let action = key.and_then(|k| self.keymap.press(k, Instant::now()));
                match action {
                    Some(CanonicalAction::Next) => drive(&self.controller, &Command::Next),
                    Some(CanonicalAction::Previous) => drive(&self.controller, &Command::Previous),
                    Some(CanonicalAction::GoLive) => drive(&self.controller, &Command::GoLive),
                    Some(CanonicalAction::ClearAll) => drive(&self.controller, &Command::Clear),
                    Some(CanonicalAction::BlackoutToggle) => {
                        let on = self
                            .controller
                            .lock()
                            .map(|g| !g.is_blackout())
                            .unwrap_or(true);
                        drive(&self.controller, &Command::Blackout { on });
                    }
                    Some(CanonicalAction::ClearLayer) => {
                        // Single-layer live output today: clearing the current
                        // layer IS the full clear (per-layer arrives with 86ajpy59e).
                        drive(&self.controller, &Command::Clear)
                    }
                    None => {}
                }
            }
            _ => {}
        }
    }

    fn new_events(&mut self, event_loop: &ActiveEventLoop, cause: StartCause) {
        // Fire a frame when the fixed deadline is reached (or at startup): advance the
        // shared state (the countdown + confidence monitor) and repaint BOTH windows — so
        // a change made by the remote controller, which is not a winit event, appears
        // within a frame. Checking a *fixed* deadline (not now+FRAME) means continuous
        // input (repeated `WaitCancelled`) can't push it forward and starve the loop.
        let now = Instant::now();
        let due = match cause {
            StartCause::Init | StartCause::ResumeTimeReached { .. } => true,
            _ => self.next_frame.is_none_or(|deadline| now >= deadline),
        };
        if due {
            self.next_frame = Some(now + FRAME);
            if let Ok(mut c) = self.controller.lock() {
                // Feed the confidence monitor its local wall clock (Timer-only chrome, Figma
                // 374-151) BEFORE ticking, so a minute rollover re-composes the stage in this
                // same frame. `set_wall_clock` de-dupes internally — no busy redraw.
                let local = chrono::Local::now();
                c.set_wall_clock(
                    &local.format("%A · %B %-d, %Y").to_string(),
                    &local.format("%-I:%M %p").to_string(),
                );
                c.tick(now);
                // Reconcile + feed the NDI OUTPUT senders from the same live state (holding the
                // lock once). No-op in the default build (no `ndi` feature → no sinks created).
                reconcile_ndi(
                    &c,
                    &mut self.ndi_outputs,
                    &mut self.ndi_backoff,
                    &mut self.ndi_warned,
                    &mut self.ndi_frames,
                    now,
                );
            }
            self.autosave(now);
            self.apply_pending_assignments(event_loop);
            if let Some(r) = self.main.as_ref() {
                r.window.request_redraw();
            }
            if let Some(r) = self.stage.as_ref() {
                r.window.request_redraw();
            }
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        // Smoke watchdog (86ajpevzp): a launch that never presents must FAIL, not
        // hang the CI job. If the window hasn't produced a frame within the budget,
        // exit non-zero with a clear message.
        if self.smoke && !self.smoke_done && self.launched_at.elapsed() > SMOKE_TIMEOUT {
            eprintln!(
                "SMOKE FAIL: no frame presented within {}s of launch (the `main` screen is {})",
                SMOKE_TIMEOUT.as_secs(),
                // An open failure is reported as itself: it is in-memory state, so the
                // registry still says "enabled" and would otherwise send the reader hunting
                // for a setting that was never changed.
                if self.open_failures.get(WindowRole::Main) {
                    "enabled, but its window FAILED TO OPEN this run — see the error above"
                } else {
                    match self.controller.lock() {
                        Ok(c) if c.is_screen_enabled("main") => "enabled",
                        Ok(_) => "DISABLED — it has no window to present",
                        Err(_) => "unknown (controller lock poisoned)",
                    }
                }
            );
            std::process::exit(1);
        }
        // Reconcile the OS windows against the screen registry: this is what makes a
        // Screens-page toggle open or close a window, since `resumed()` runs only once.
        // No-op (and no allocation) when reality already matches.
        self.reconcile_screen_windows(event_loop);
        // Wake at the *fixed* next-frame deadline. The repaint is requested in
        // `new_events` (not here), so the loop idles until the deadline instead of
        // spinning on a self-posted redraw — a window that can't present never pegs a CPU
        // core, and the fixed deadline still fires under a stream of input events.
        let deadline = self.next_frame.unwrap_or_else(|| Instant::now() + FRAME);
        event_loop.set_control_flow(ControlFlow::WaitUntil(deadline));
    }
}

/// Spawn the pinned-TLS control server on a background thread with its own Tokio
/// runtime, driving the shared `controller`. If it can't start, the window still runs
/// under local keyboard control.
fn start_remote_control(controller: Arc<Mutex<LiveController>>, remote: Arc<RemoteShared>) {
    std::thread::spawn(move || {
        let runtime = match tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
        {
            Ok(rt) => rt,
            Err(e) => {
                eprintln!("SelahCue: remote control disabled (runtime: {e})");
                return;
            }
        };
        if let Err(e) = runtime.block_on(run_server(controller, remote)) {
            eprintln!("SelahCue: remote control stopped: {e}");
        }
    });
}

async fn run_server(
    controller: Arc<Mutex<LiveController>>,
    remote: Arc<RemoteShared>,
) -> Result<(), Box<dyn std::error::Error>> {
    let identity = SelfSigned::generate(vec!["localhost".into()])
        .map_err(|e| format!("tls identity: {e:?}"))?;
    let pin = identity.pin;

    // A host-local operator session (for the operator shell on this machine): a fresh
    // random token per run — never a fixed value, since we bind beyond loopback now.
    let device = "operator-shell";
    let token = generate_token();
    if token.is_empty() {
        return Err("could not generate an operator token".into());
    }
    {
        let now = Instant::now();
        let mut reg = remote.registry.lock().await;
        reg.offer_pairing("host-local", Role::Operator, now, Duration::from_secs(60));
        reg.redeem(
            "host-local",
            DeviceId(device.to_string()),
            SessionToken::new(token.clone()),
            now,
        )
        .map_err(|e| format!("pairing: {e:?}"))?;
        // Pin the host-local operator credential so the idle-TTL (audit #8) never reclaims it:
        // it is held over one long-lived loopback connection (never re-authenticated, so `touch`
        // does not refresh it) and reuses the fixed endpoint token with no re-pair path.
        reg.pin(&DeviceId(device.to_string()));
    }

    // Bind the LAN so a phone can reach us: joining is gated by pairing (single-use
    // TTL code + host confirmation) behind pinned TLS, so an open port grants nothing.
    let listener = TcpListener::bind("0.0.0.0:0").await?;
    let port = listener.local_addr()?.port();
    let _ = remote.lan.set((port, pin.to_hex()));

    // Operator-paced pairing (86ajxer8n): a device that scans the QR and connects parks as a
    // pending request; the operator approves it (assigning a role) or denies it from the Remote
    // Control console. The output window no longer prompts for Y/N host confirmation.
    // The endpoint (LAN IP + bound port + raw cert pin) lets the operator's "New code" mint a
    // real, scannable `selahcue://pair?…` QR — the same invite this window shows on-screen.
    let server = Arc::new(
        ControlServer::new(&identity, remote.registry.clone(), handler_for(controller))
            .map_err(|e| format!("server: {e:?}"))?
            .with_pairing_requests()
            .with_pairing_endpoint(lan_ip().to_string(), port, pin.to_hex()),
    );
    // Advertise on mDNS so the phone can FIND us without typing an address
    // (86ajp0b0t). The TXT carries the cert pin — public data (it is printed in
    // every QR invite); joining still requires the TTL pairing code + host
    // approval, so discovery discloses presence, never access.
    let _mdns = advertise_mdns(port, device, &pin.to_hex());
    // Local clients (operator shell / CLI) connect via loopback.
    let local: SocketAddr = ([127, 0, 0, 1], port).into();
    let endpoint = write_endpoint(local, &pin.to_hex(), device, &token);
    print_connect_banner(local, &pin.to_hex(), device, &token, endpoint.as_deref());
    server
        .run(listener)
        .await
        .map_err(|e| format!("server run: {e:?}"))?;
    Ok(())
}

/// Advertise the control endpoint as `_selahcue._tcp.local.` while the server
/// runs (the returned daemon unregisters on drop). Best-effort: an mDNS-hostile
/// network only loses discovery — the QR/manual paths are unaffected.
fn advertise_mdns(port: u16, device: &str, pin_hex: &str) -> Option<mdns_sd::ServiceDaemon> {
    let daemon = match mdns_sd::ServiceDaemon::new() {
        Ok(d) => d,
        Err(e) => {
            eprintln!("SelahCue: mDNS advertising unavailable ({e}).");
            return None;
        }
    };
    // A per-run unique instance name so two hosts never collide in the phone's
    // list; the friendly name (with the pin fingerprint) rides in TXT so the
    // operator recognises the right host at a glance.
    let instance = format!("{device}-{port}");
    let friendly = format!("SelahCue {}", pin_fingerprint(pin_hex));
    let props = [("pin", pin_hex), ("name", friendly.as_str())];
    let info = mdns_sd::ServiceInfo::new(
        "_selahcue._tcp.local.",
        &instance,
        &format!("{instance}.local."),
        // Empty IP + auto-detect: mdns-sd fills in every up interface address,
        // so a multi-NIC host advertises the right one (not a single guess).
        "",
        port,
        &props[..],
    )
    .ok()?
    .enable_addr_auto();
    match daemon.register(info) {
        Ok(()) => {
            println!("  Discovery: advertising _selahcue._tcp on mDNS.");
            Some(daemon)
        }
        Err(e) => {
            eprintln!("SelahCue: mDNS registration failed ({e}).");
            None
        }
    }
}

/// This machine's LAN-facing IP (for the QR invite): a UDP "connect" selects the
/// outbound interface without sending a packet. Falls back to loopback.
fn lan_ip() -> std::net::IpAddr {
    std::net::UdpSocket::bind("0.0.0.0:0")
        .and_then(|s| {
            s.connect("8.8.8.8:80")?;
            s.local_addr()
        })
        .map(|a| a.ip())
        .unwrap_or_else(|_| std::net::IpAddr::from([127, 0, 0, 1]))
}

/// A short, human-comparable fingerprint of the certificate pin — the first 12
/// hex chars grouped in 4s (e.g. `AB12-CD34-EF56`). Shown on BOTH the host and
/// the phone so the operator can confirm a discovered host is the real one
/// before disclosing the pairing code (defeats a rogue-mDNS phish; the phone
/// mirrors this exact format). Not a secret — it derives from the public pin.
pub fn pin_fingerprint(pin_hex: &str) -> String {
    let head: String = pin_hex.chars().take(12).collect::<String>().to_uppercase();
    head.as_bytes()
        .chunks(4)
        .map(|c| std::str::from_utf8(c).unwrap_or(""))
        .collect::<Vec<_>>()
        .join("-")
}

/// Print the pairing invite: the URI, the hand-typable code, and an ASCII QR.
fn print_pairing_block(uri: &str, code: &str) {
    println!();
    println!("  PAIRING MODE (2 minutes) — scan from the SelahCue mobile app:");
    println!("  {uri}");
    println!("  or enter code: {code}");
    if let Some(pin) = uri.split("pin=").nth(1).and_then(|s| s.split('&').next()) {
        println!("  host fingerprint: {}", pin_fingerprint(pin));
        println!("  (if pairing from 'Nearby hosts', confirm the phone shows THIS fingerprint)");
    }
    if let Some((side, modules)) = qr_modules(uri) {
        println!();
        let quiet = 2usize;
        for y in 0..side + 2 * quiet {
            let mut line = String::with_capacity((side + 2 * quiet) * 2 + 2);
            line.push_str("  ");
            for x in 0..side + 2 * quiet {
                let dark = x >= quiet
                    && y >= quiet
                    && x < side + quiet
                    && y < side + quiet
                    && modules[(y - quiet) * side + (x - quiet)];
                line.push_str(if dark { "██" } else { "  " });
            }
            println!("{line}");
        }
    }
    println!("  (the QR is also on the stage/confidence window; press P again to cancel)");
    println!();
}

/// Write a local endpoint descriptor so the operator shell on this machine can
/// auto-discover + connect (a loopback-only convenience; real pairing is QR + host
/// confirmation). Values are simple ASCII (addr/hex/ids), so a hand-built JSON string is
/// safe. Returns the path written, if any.
fn endpoint_path() -> std::path::PathBuf {
    std::env::temp_dir().join("selahcue-operator-endpoint.json")
}

fn write_endpoint(
    addr: SocketAddr,
    pin_hex: &str,
    device: &str,
    token: &str,
) -> Option<std::path::PathBuf> {
    let json = format!(
        "{{\"addr\":\"{addr}\",\"pin\":\"{pin_hex}\",\"device\":\"{device}\",\"token\":\"{token}\"}}"
    );
    let path = endpoint_path();
    if let Err(e) = std::fs::write(&path, json) {
        eprintln!("SelahCue: could not write operator endpoint file: {e}");
        return None;
    }
    // The descriptor carries a bearer token. On macOS `temp_dir()` is already a per-user
    // private dir, but on Linux it is world-readable `/tmp`, so restrict to owner-only.
    // (This is a loopback-only demo convenience; real pairing is QR + host confirmation
    // and persists no token.)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600));
    }
    Some(path)
}

fn print_connect_banner(
    addr: SocketAddr,
    pin_hex: &str,
    device: &str,
    token: &str,
    endpoint: Option<&std::path::Path>,
) {
    println!();
    println!("  SelahCue — remote control ready");
    println!("  ------------------------------------------------------------");
    println!("  The output window is driven by the LAN control server.");
    println!("  address : {addr}");
    println!("  pin     : {pin_hex}");
    println!(
        "  device  : {device}   role : Operator (host shell); token: in the endpoint file (0600)"
    );
    if let Some(path) = endpoint {
        println!(
            "  endpoint: {}  (the operator shell auto-discovers this)",
            path.display()
        );
    }
    println!();
    println!("  Drive the window with the operator shell (auto-connects on this machine):");
    println!("    cargo run   # from crates/selahcue-operator");
    println!("  or from another terminal with the remote CLI:");
    println!("    cargo run -p selahcue-lan --example remote --features server -- \\");
    println!("      {addr} {pin_hex} {device} {token} next");
    println!(
        "    (commands: next · previous · go-live · blackout-on · blackout-off · clear · state)"
    );
    println!();
    println!("  Local keys: Space/\u{2192}=next  \u{2190}=prev  Enter=Go Live  B=blackout  Esc Esc=clear all  Backspace=clear staged");
    println!("  Pairing:    P=show a QR invite (approve/deny devices from the operator console)");
    // Closing a window closes only THAT screen while another output window is still open,
    // so both ways out have to be stated explicitly — and the chord only works while an
    // output window has focus, which is exactly why the last close quits.
    println!(
        "  Windows:    while more than one output window is open, a window's close button \
         switches OFF that screen (toggle it back on from the operator's Screens page)"
    );
    println!(
        "  Quit:       {} with an output window focused, or close the LAST open output window",
        if cfg!(target_os = "macos") {
            "Cmd-Q"
        } else {
            "Ctrl-Q"
        }
    );
    println!();
}

fn main() {
    let event_loop = EventLoop::new().expect("event loop");
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App::new();
    event_loop.run_app(&mut app).expect("run app");
    // A clean exit is by definition a stable launch.
    if let Some(g) = app.launch_guard.as_ref() {
        g.mark_stable();
    }
    // Final save on clean exit (the autosave loop already covered crash paths) —
    // including a plan edit acked in the last instants before the loop exited.
    // Honours the same halts as autosave: no writes on a critical disk, and a
    // clean-mode run never touches the preserved session. A `--smoke` launch is a
    // throwaway probe — it must not persist anything (no session mutation).
    if !app.disk_critical && !app.clean_mode && !app.smoke {
        if let Ok(mut c) = app.controller.lock() {
            // 86akcfftu (Sana, PR #31 F2): a clean exit while a transcript session is open
            // must close it here too, not just on an explicit Stop Listening — otherwise
            // quitting mid-service left `ended_at` unset until the next startup's
            // crash-recovery sweep, and dropped whatever was still buffered unflushed. A
            // no-op (via `close_current`'s early return) when no session is open.
            c.end_transcript_session();
            if c.take_plan_dirty() {
                app.store.save_plan(c.plan());
            }
            if c.take_saved_themes_dirty() {
                let themes: Vec<(String, String)> = c
                    .saved_themes()
                    .iter()
                    .map(|(n, j)| (n.clone(), j.clone()))
                    .collect();
                app.store.save_saved_themes(&themes);
            }
            if c.take_screen_themes_dirty() {
                let themes: Vec<(String, String)> = c
                    .screen_themes()
                    .iter()
                    .map(|(s, t)| (s.clone(), t.clone()))
                    .collect();
                app.store.save_screen_themes(&themes);
            }
            if c.take_screen_registry_dirty() {
                let screens: Vec<(String, String, bool, bool)> = c
                    .screen_registry()
                    .iter()
                    .map(|s| {
                        (
                            s.id.clone(),
                            s.role.as_tag().to_string(),
                            s.enabled,
                            s.deletable,
                        )
                    })
                    .collect();
                app.store.save_screens(&screens);
            }
            if c.take_output_configs_dirty() {
                let configs: Vec<(String, OutputConfigView)> = c
                    .output_configs()
                    .iter()
                    .map(|(s, cfg)| (s.clone(), cfg.clone()))
                    .collect();
                app.store.save_screen_configs(&configs);
            }
            app.store.save_session(&c.snapshot(Instant::now()));
        }
    }
    // Best-effort: don't leave a stale endpoint (with a now-dead token/port) behind on a
    // clean exit, so a later operator shell doesn't try to attach to a defunct window.
    let _ = std::fs::remove_file(endpoint_path());
}

/// The window-lifecycle decision (the pure half of the toggle / close-button path).
/// Real windowing is not testable in CI, so the DECISION is tested here and the winit
/// half only performs what these tests pin.
#[cfg(test)]
mod window_lifecycle_tests {
    use super::{
        close_button_outcome, demo_plan, is_quit_chord, quit_chord_reachable, reconcile_windows,
        record_open_outcome, window_role_for_screen, CloseOutcome, LiveController, OpenFailures,
        Theme, WindowAction, WindowRole, OUTPUT_H, OUTPUT_W,
    };
    use std::sync::Mutex;

    /// The default registry: the two built-ins, both enabled.
    fn builtins(main: bool, stage: bool) -> Vec<(&'static str, bool)> {
        vec![("main", main), ("stage", stage)]
    }

    /// The reconcile with a clean failure record — the ordinary case, where no window has
    /// failed to open. Tests that care about failures thread their own `OpenFailures`.
    fn decide(
        screens: Vec<(&'static str, bool)>,
        main_open: bool,
        stage_open: bool,
    ) -> Vec<WindowAction> {
        reconcile_windows(screens, main_open, stage_open, &mut OpenFailures::default())
    }

    /// A real controller with the default registry (both built-ins enabled), so the registry
    /// assertions below run against the same type and dirty flag the autosave persists from.
    fn controller() -> Mutex<LiveController> {
        Mutex::new(LiveController::new(
            demo_plan(),
            OUTPUT_W,
            OUTPUT_H,
            Theme::dark(),
        ))
    }

    #[test]
    fn nothing_to_do_when_reality_already_matches() {
        // Both enabled and both open: idempotent, no churn on the ~60 Hz reconcile.
        assert_eq!(decide(builtins(true, true), true, true), []);
        // Both disabled and both already closed: equally a fixed point.
        assert_eq!(decide(builtins(false, false), false, false), []);
    }

    #[test]
    fn disabling_a_screen_closes_its_window() {
        assert_eq!(
            decide(builtins(false, true), true, true),
            [WindowAction::Close(WindowRole::Main)]
        );
        assert_eq!(
            decide(builtins(true, false), true, true),
            [WindowAction::Close(WindowRole::Stage)]
        );
        // Both off at once closes both — the process still lives (it owns the LAN server).
        assert_eq!(
            decide(builtins(false, false), true, true),
            [
                WindowAction::Close(WindowRole::Main),
                WindowAction::Close(WindowRole::Stage)
            ]
        );
    }

    #[test]
    fn re_enabling_a_screen_relaunches_its_window() {
        // The reason the reconcile exists: `resumed()` runs once, so this is what makes
        // "toggle back on" bring the window back.
        assert_eq!(
            decide(builtins(true, false), false, false),
            [WindowAction::Open(WindowRole::Main)]
        );
        assert_eq!(
            decide(builtins(false, true), false, false),
            [WindowAction::Open(WindowRole::Stage)]
        );
        // A cold start with both enabled and no windows yet: `resumed()`'s case.
        assert_eq!(
            decide(builtins(true, true), false, false),
            [
                WindowAction::Open(WindowRole::Main),
                WindowAction::Open(WindowRole::Stage)
            ]
        );
    }

    #[test]
    fn opens_and_closes_can_be_decided_in_the_same_pass() {
        // main toggled off while stage was toggled on — one pass settles both.
        assert_eq!(
            decide(builtins(false, true), true, false),
            [
                WindowAction::Close(WindowRole::Main),
                WindowAction::Open(WindowRole::Stage)
            ]
        );
    }

    #[test]
    fn applying_the_actions_reaches_a_fixed_point() {
        // Idempotence as a property: performing the decision and re-running the reconcile
        // must decide nothing further, whatever the starting state.
        for main_enabled in [false, true] {
            for stage_enabled in [false, true] {
                for main_open in [false, true] {
                    for stage_open in [false, true] {
                        let actions =
                            decide(builtins(main_enabled, stage_enabled), main_open, stage_open);
                        // Perform them (the winit half does exactly this).
                        let mut m = main_open;
                        let mut s = stage_open;
                        for a in &actions {
                            match a {
                                WindowAction::Open(WindowRole::Main) => m = true,
                                WindowAction::Close(WindowRole::Main) => m = false,
                                WindowAction::Open(WindowRole::Stage) => s = true,
                                WindowAction::Close(WindowRole::Stage) => s = false,
                            }
                        }
                        assert_eq!(m, main_enabled, "main window matches the registry");
                        assert_eq!(s, stage_enabled, "stage window matches the registry");
                        assert_eq!(
                            decide(builtins(main_enabled, stage_enabled), m, s),
                            [],
                            "a second pass decides nothing"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn the_close_button_converges_on_the_same_decision() {
        // Clicking a window's close button runs `close_screen(role)`, which drops the
        // renderer AND sets that screen disabled. Feeding that resulting state back through
        // the reconcile must produce NO action — the button and the toggle are one path, so
        // a closed window is never re-opened behind the operator's back...
        assert_eq!(
            decide(builtins(false, true), false, true),
            [],
            "after the close button, the reconcile agrees"
        );
        // ...and the state the button lands in is exactly the state the TOGGLE lands in:
        // disabling main from the Screens page decides Close(Main), and performing that
        // close gives the same (enabled=false, window absent) pair.
        assert_eq!(
            decide(builtins(false, true), true, true),
            [WindowAction::Close(WindowRole::Main)]
        );
    }

    #[test]
    fn virtual_screens_never_produce_a_window_action() {
        // Lower-third / stream feeds have NO window: their `enabled` flag gates NDI only.
        // Whatever they are set to, the reconcile must stay silent about windows.
        assert!(window_role_for_screen("lower-third").is_none());
        assert!(window_role_for_screen("stream").is_none());
        assert!(window_role_for_screen("stream-2").is_none());
        let mixed = vec![
            ("main", true),
            ("stage", true),
            ("lower-third", false),
            ("stream", true),
            ("stream-2", false),
        ];
        assert_eq!(
            decide(mixed, true, true),
            [],
            "virtual screens are invisible to the window reconcile"
        );
        // Even a registry of ONLY virtual screens (no built-ins) decides nothing — and, in
        // particular, never closes a physical window that is open.
        assert_eq!(
            decide(vec![("lower-third", false), ("stream", false)], true, true),
            []
        );
    }

    #[test]
    fn quit_is_the_platform_chord_and_nothing_else() {
        // macOS: Cmd-Q quits, Ctrl-Q does not.
        assert!(is_quit_chord(Some("q"), true, false, true));
        assert!(is_quit_chord(Some("Q"), true, false, true));
        assert!(!is_quit_chord(Some("q"), false, true, true));
        // Elsewhere: Ctrl-Q quits, Cmd/Super-Q does not.
        assert!(is_quit_chord(Some("q"), false, true, false));
        assert!(!is_quit_chord(Some("q"), true, false, false));
        // A bare `q` is never a quit (it must not shadow a canonical key), and neither is
        // the modifier on some other key.
        assert!(!is_quit_chord(Some("q"), false, false, true));
        assert!(!is_quit_chord(Some("q"), false, false, false));
        assert!(!is_quit_chord(Some("b"), true, true, true));
        assert!(!is_quit_chord(None, true, true, true));
    }

    // --- What the process can still DO after the reconcile has been performed. The tests
    // above model the window DECISIONS; these model the state those decisions leave behind,
    // which is where the two shipped defects lived. ---

    #[test]
    fn the_process_is_never_left_running_with_no_way_to_quit_it() {
        // THE invariant. The quit chord is delivered by `window_event`, so it only reaches a
        // FOCUSED WINDOW — a running process with no window cannot be quit from the keyboard
        // at all, and the connect banner promises a chord nothing can deliver. Exhaustively:
        // from every window state, every close button that actually exists must either quit
        // the process or leave a window behind that can still receive the chord.
        for main_open in [false, true] {
            for stage_open in [false, true] {
                for closing in [WindowRole::Main, WindowRole::Stage] {
                    let exists = match closing {
                        WindowRole::Main => main_open,
                        WindowRole::Stage => stage_open,
                    };
                    // No window, no close button to press.
                    if !exists {
                        continue;
                    }
                    let (main_after, stage_after) = match closing {
                        WindowRole::Main => (false, stage_open),
                        WindowRole::Stage => (main_open, false),
                    };
                    let outcome = close_button_outcome(main_open, stage_open, closing);
                    let still_reachable = quit_chord_reachable(main_after, stage_after);
                    assert_eq!(
                        outcome == CloseOutcome::Quit,
                        !still_reachable,
                        "closing {closing:?} from (main_open={main_open}, \
                         stage_open={stage_open}): the process must quit exactly when no \
                         window would be left to receive the quit chord"
                    );
                }
            }
        }
        // And the fact the rule rests on, stated on its own so it cannot be quietly widened:
        // a windowless process has no keyboard route out.
        assert!(!quit_chord_reachable(false, false));
        assert!(quit_chord_reachable(true, false));
        assert!(quit_chord_reachable(false, true));
    }

    #[test]
    fn closing_the_last_window_is_a_quit_gesture() {
        // Both windows up: closing either is a screen edit, not a quit. This is the part of
        // the shipped behaviour that must be PRESERVED — the process hosts the LAN server and
        // the presentation state paired mobile controllers depend on.
        assert_eq!(
            close_button_outcome(true, true, WindowRole::Main),
            CloseOutcome::CloseScreen
        );
        assert_eq!(
            close_button_outcome(true, true, WindowRole::Stage),
            CloseOutcome::CloseScreen
        );
        // The last window, either way round: quit. Before this, an operator who closed both
        // (the gesture that quit the app before this lifecycle existed) had to kill the
        // process — the banner told them to press Cmd-Q, and nothing was left to hear it.
        assert_eq!(
            close_button_outcome(true, false, WindowRole::Main),
            CloseOutcome::Quit
        );
        assert_eq!(
            close_button_outcome(false, true, WindowRole::Stage),
            CloseOutcome::Quit
        );
    }

    #[test]
    fn a_failed_open_never_reaches_the_persisted_registry() {
        // A window that fails to open is a transient environment failure (GPU, window
        // server), not an operator setting. Recording it as `enabled = false` would mark the
        // registry dirty, the autosave would WRITE it, and the operator's main audience
        // output would be off in the saved registry for every future launch — recoverable
        // only from a paired operator console.
        let c = controller();
        let mut failures = OpenFailures::default();
        // Whatever the autosave would have carried over from startup is already taken.
        let _ = c.lock().expect("controller").take_screen_registry_dirty();

        record_open_outcome(
            &c,
            &mut failures,
            WindowRole::Main,
            Err("create surface: no adapter".into()),
        );

        let mut guard = c.lock().expect("controller");
        assert!(
            guard.is_screen_enabled("main"),
            "the screen must still be ENABLED — the failure is not a setting"
        );
        assert!(
            !guard.take_screen_registry_dirty(),
            "the registry must not be marked dirty: that flag is what the autosave persists, \
             so a one-off GPU hiccup would become a durable 'screen disabled'"
        );
        drop(guard);
        // The suppression lives here instead, where it dies with the process.
        assert!(failures.get(WindowRole::Main));
        assert!(!failures.get(WindowRole::Stage), "only the failing role");

        // A later success clears it, and still leaves the registry alone (it already says
        // enabled, so there is nothing to write).
        record_open_outcome(&c, &mut failures, WindowRole::Main, Ok(()));
        assert!(!failures.get(WindowRole::Main));
        assert!(
            !c.lock().expect("controller").take_screen_registry_dirty(),
            "an open that succeeds on an already-enabled screen writes nothing either"
        );
    }

    #[test]
    fn a_failed_open_is_attempted_once_not_once_per_frame() {
        // The reconcile runs in `about_to_wait`, i.e. ~60x a second. The premise here is that
        // the registry still reports the screen ENABLED after the failure — which is exactly
        // what the fix guarantees, and also what a `SetScreenEnabled` that was rejected or
        // dropped on a poisoned lock would leave behind. Suppression must therefore hold
        // WITHOUT any registry write.
        let mut failures = OpenFailures::default();
        let mut attempts = 0usize;
        // `stage` is open and stays open; `main` is enabled but its window keeps failing.
        for _ in 0..10_000 {
            for action in reconcile_windows(builtins(true, true), false, true, &mut failures) {
                if let WindowAction::Open(role) = action {
                    attempts += 1;
                    // Window creation fails, every single time.
                    failures.set(role, true);
                }
            }
        }
        assert_eq!(
            attempts, 1,
            "a failing open costs ONE window-creation attempt, not one per frame"
        );

        // Recovery is the operator's gesture, not a loop: switching the screen off clears the
        // record, and switching it back on buys exactly one more attempt.
        let cleared = reconcile_windows(builtins(false, true), false, true, &mut failures);
        assert_eq!(cleared, [], "already closed: nothing to do");
        assert!(
            !failures.get(WindowRole::Main),
            "switching the screen off forgets the failure"
        );
        for _ in 0..10_000 {
            for action in reconcile_windows(builtins(true, true), false, true, &mut failures) {
                if let WindowAction::Open(role) = action {
                    attempts += 1;
                    failures.set(role, true);
                }
            }
        }
        assert_eq!(attempts, 2, "one further attempt per deliberate re-enable");
    }

    #[test]
    fn a_suppressed_role_does_not_freeze_the_other_window() {
        // A failure on one screen must not stop the other from being opened or closed: a
        // stage window that will not create cannot be allowed to take the audience output
        // with it.
        let mut failures = OpenFailures::default();
        failures.set(WindowRole::Stage, true);
        assert_eq!(
            reconcile_windows(builtins(true, true), false, false, &mut failures),
            [WindowAction::Open(WindowRole::Main)],
            "main still opens while stage is suppressed"
        );
        assert_eq!(
            reconcile_windows(builtins(false, true), true, false, &mut failures),
            [WindowAction::Close(WindowRole::Main)],
            "main still closes while stage is suppressed"
        );
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod transcript_durability_tests {
    use selahcue_data::{transcript_repo, Database};

    /// `RealTranscriptStore` (86akcfftu) is a thin, faithful adapter over
    /// `selahcue_data::transcript_repo` — a full create → append → end round-trip, read back
    /// through the repo's own `load`, must show exactly what was written.
    #[test]
    fn real_transcript_store_round_trips_through_transcript_repo() {
        use selahcue_app::TranscriptStoreWriter;

        let mut store = super::RealTranscriptStore {
            db: Database::open_in_memory().unwrap(),
        };
        let id = store
            .open_transcript("Sunday Service", "on-device-whisper", 1_000)
            .unwrap();
        store.append_segment(id, 0, 500, "grace and peace").unwrap();
        store.append_segment(id, 500, 1_200, "to you").unwrap();
        store.end_transcript(id, 5_000).unwrap();

        let detail = transcript_repo::load(&store.db, id).unwrap();
        assert_eq!(detail.label, "Sunday Service");
        assert_eq!(detail.provider, "on-device-whisper");
        assert_eq!(detail.started_at_ms, 1_000);
        assert_eq!(detail.ended_at_ms, Some(5_000));
        assert_eq!(detail.segments.len(), 2);
        assert_eq!(detail.segments[0].text, "grace and peace");
        assert_eq!(detail.segments[1].text, "to you");
    }

    /// The 86akcfftu crash-recovery sweep: an orphaned transcript (no normal Stop Listening
    /// ever ran) gets `ended_at` backfilled from its last segment's `end_ms` on the next
    /// startup — never left null forever.
    #[test]
    fn sweep_closes_an_orphaned_transcript_using_its_last_segment_end() {
        let db = Database::open_in_memory().unwrap();
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".into(),
                provider: "on-device-whisper".into(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .unwrap();
        transcript_repo::append_segment(&db, id, 0, 500, "first").unwrap();
        transcript_repo::append_segment(&db, id, 500, 12_000, "last before the crash").unwrap();
        // Never end()ed — simulates a crash mid-service.

        super::sweep_orphaned_transcripts(&db);

        let detail = transcript_repo::load(&db, id).unwrap();
        assert_eq!(
            detail.ended_at_ms,
            Some(1_000 + 12_000),
            "ended_at must be backfilled from started_at + the last segment's end_ms, not left \
             null and not a fabricated 'now'"
        );
    }

    /// POSITIVE CONTROL for the sweep above: a transcript that crashed before its first
    /// segment ever landed still gets closed (using `started_at`, its only evidence) — the
    /// sweep must not silently skip a session with zero segments.
    #[test]
    fn sweep_closes_an_orphan_with_no_segments_using_started_at() {
        let db = Database::open_in_memory().unwrap();
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".into(),
                provider: "on-device-whisper".into(),
                plan_id: None,
                started_at_ms: 42_000,
            },
        )
        .unwrap();

        super::sweep_orphaned_transcripts(&db);

        let detail = transcript_repo::load(&db, id).unwrap();
        assert_eq!(detail.ended_at_ms, Some(42_000));
    }

    /// POSITIVE CONTROL: a transcript that already ended normally (a healthy prior run) must
    /// be left completely untouched by the sweep — otherwise "the sweep ran" would be
    /// indistinguishable from "the sweep clobbers everything it sees".
    #[test]
    fn sweep_never_touches_a_transcript_that_already_ended() {
        let db = Database::open_in_memory().unwrap();
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".into(),
                provider: "on-device-whisper".into(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .unwrap();
        transcript_repo::end(&db, id, 9_999).unwrap();

        super::sweep_orphaned_transcripts(&db);

        let detail = transcript_repo::load(&db, id).unwrap();
        assert_eq!(
            detail.ended_at_ms,
            Some(9_999),
            "a normally-ended transcript's ended_at must be left exactly as it was"
        );
    }
}

/// `resolve_autosave_slot`/`SessionStore::load_autosave_slot` (FR-005/FR-079; 86ajy0hxg) —
/// closes a gap Sana's PR #102 security review found (S-1): every `RestoreAutosave` test
/// elsewhere in this ticket goes through `FakeAutosaveStore`
/// (`selahcue-app/tests/test_service_plan_resilience.rs`), which never runs a real
/// `PRAGMA integrity_check` — its `fail_integrity` flag just returns a hardcoded string.
/// Deleting the real `integrity_check()` call, or reordering it after the row read, left every
/// test in this ticket green. These tests exercise the REAL `selahcue-data`-backed path,
/// against a real on-disk SQLite store, including a genuinely corrupted one AND the
/// plan-content fingerprint guard (Cody, PR #102 code review — Blocking-1).
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod autosave_restore_tests {
    use selahcue_core::plan::{ItemContent, ItemKind, ServicePlan};
    use selahcue_data::session_repo::SessionState;
    use selahcue_data::{autosave_repo, plan_repo, Database};

    fn seeded_db() -> (Database, i64, ServicePlan) {
        let db = Database::open_in_memory().unwrap();
        let mut plan = ServicePlan::new("Sunday");
        plan.add_item(ItemKind::Song, "Doxology");
        plan.add_item(ItemKind::Scripture, "Romans 8:28");
        let plan_id = plan_repo::insert(&db, &plan).unwrap();
        (db, plan_id, plan)
    }

    /// Push a slot for `plan` as it exists RIGHT NOW — mirrors
    /// `SessionStore::push_autosave_slot`'s real call, so the fingerprint captured always
    /// matches the plan at push time (tests that want a MISMATCH mutate the plan afterward).
    fn push(
        db: &Database,
        plan: &ServicePlan,
        plan_id: i64,
        live_idx: Option<u32>,
        saved_at_ms: i64,
    ) {
        let state = SessionState {
            plan_id: Some(plan_id),
            live_idx,
            ..Default::default()
        };
        let fp = super::plan_fingerprint(plan);
        autosave_repo::push(db, &state, saved_at_ms, None, Some(&fp)).unwrap();
    }

    #[test]
    fn resolves_a_healthy_slot_end_to_end() {
        let (db, plan_id, plan) = seeded_db();
        push(&db, &plan, plan_id, Some(0), 1_000);
        let slot = autosave_repo::list(&db).unwrap()[0].id;

        let (resolved_plan_id, resolved_plan, snap) = super::resolve_autosave_slot(&db, slot)
            .unwrap()
            .expect("a real, healthy slot must resolve");
        assert_eq!(resolved_plan_id, plan_id);
        assert_eq!(resolved_plan.len(), 2);
        assert_eq!(snap.live_idx, Some(0));
    }

    #[test]
    fn refuses_an_unknown_slot_without_touching_integrity() {
        let (db, _, _) = seeded_db();
        assert!(super::resolve_autosave_slot(&db, 999).unwrap().is_none());
    }

    /// FR-079's whole point: a slot with no associated plan (a corrupt/incomplete row) must be
    /// REFUSED, never silently resolved with a missing or default plan.
    #[test]
    fn refuses_a_slot_with_no_associated_plan() {
        let db = Database::open_in_memory().unwrap();
        let state = SessionState {
            plan_id: None,
            live_idx: Some(0),
            ..Default::default()
        };
        autosave_repo::push(&db, &state, 1_000, None, None).unwrap();
        let slot = autosave_repo::list(&db).unwrap()[0].id;
        assert!(
            super::resolve_autosave_slot(&db, slot).is_err(),
            "a slot with plan_id = NULL must be refused, not silently restored"
        );
    }

    /// FR-079, proven against REAL SQLite corruption (not a mocked flag): two tables sharing
    /// one b-tree root page is a genuine, `PRAGMA integrity_check`-detectable corruption
    /// (`sqlite_master.rootpage` edited via `writable_schema`, the standard technique for
    /// exercising this without fragile raw byte surgery on the file). Proves `resolve_autosave_slot`
    /// refuses to resolve the row when the store itself is unhealthy — the row read never
    /// happens; only `Err` comes back, never a plausible-looking but unreliable snapshot.
    #[test]
    fn refuses_to_resolve_from_a_genuinely_corrupt_store() {
        let (db, plan_id, plan) = seeded_db();
        push(&db, &plan, plan_id, Some(0), 1_000);
        let slot = autosave_repo::list(&db).unwrap()[0].id;
        // Positive control: before corruption, this exact slot resolves cleanly.
        assert!(
            super::resolve_autosave_slot(&db, slot).unwrap().is_some(),
            "positive control: the slot must resolve BEFORE corruption for the refusal below \
             to mean anything"
        );

        let other_root: i64 = db
            .conn()
            .query_row(
                "SELECT rootpage FROM sqlite_master WHERE type='table' AND name='service_plan'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        db.conn()
            .execute_batch(&format!(
                "PRAGMA writable_schema = ON;
                 UPDATE sqlite_master SET rootpage = {other_root}
                    WHERE type = 'table' AND name = 'autosave_slot';
                 PRAGMA writable_schema = OFF;
                 PRAGMA schema_version = 999999999;"
            ))
            .unwrap();

        let result = super::resolve_autosave_slot(&db, slot);
        assert!(
            result.is_err(),
            "a corrupt store must be refused, got {result:?}"
        );
    }

    /// THE Blocking-1 regression (Cody, PR #102 code review), reproduced against the real repo
    /// layer: capture a slot, then edit the SAME plan (same `plan_id` — the case the earlier
    /// doc comment called "unaffected" and which Cody proved wasn't), then attempt to restore
    /// the pre-edit slot. Before the fingerprint guard, this silently returned the pre-edit
    /// INDICES paired with the post-edit CONTENT — a removed item's slot could resolve to
    /// whatever item now sits at that index, with no error. The guard must refuse instead.
    #[test]
    fn refuses_to_restore_a_slot_whose_plan_content_changed_since_capture() {
        let (db, plan_id, plan) = seeded_db();
        // Capture live on the Scripture item (index 1) — Cody's exact repro shape.
        push(&db, &plan, plan_id, Some(1), 1_000);
        let slot = autosave_repo::list(&db).unwrap()[0].id;
        // Positive control: before the edit, this exact slot resolves cleanly.
        assert!(
            super::resolve_autosave_slot(&db, slot).unwrap().is_some(),
            "positive control: the slot must resolve BEFORE the edit for the refusal below to \
             mean anything"
        );

        // The operator removes the Scripture item — an ordinary, everyday plan edit, not a
        // NewPlan/ImportPlan replacement. `plan_repo::update` mutates the SAME `plan_id` row
        // in place, exactly like the real desktop's `App::save_plan` does on every `plan_dirty`
        // tick.
        let mut edited = plan.clone();
        let scripture_id = edited.items()[1].id;
        edited.remove(scripture_id).unwrap();
        assert_eq!(
            edited.len(),
            1,
            "positive control: the edit really removed an item"
        );
        plan_repo::update(&db, plan_id, &edited).unwrap();

        let result = super::resolve_autosave_slot(&db, slot);
        assert!(
            result.is_err(),
            "a slot captured before a since-applied plan edit must be REFUSED, not resolved \
             onto the edited content — got {result:?}"
        );
    }

    /// Positive control for the guard above, the other direction: a slot's OWN content link
    /// changing (not just add/remove) must also be caught — proves the fingerprint compares
    /// real item content, not just item COUNT (which an add/remove-only test could pass with a
    /// mutation that only checked `.len()`).
    #[test]
    fn refuses_when_only_an_items_content_link_changed_not_the_count() {
        let (db, plan_id, plan) = seeded_db();
        push(&db, &plan, plan_id, Some(0), 1_000);
        let slot = autosave_repo::list(&db).unwrap()[0].id;

        let mut edited = plan.clone();
        let scripture_item_id = edited.items()[1].id;
        edited
            .set_item_content(
                scripture_item_id,
                Some(ItemContent::Scripture {
                    reference: "John 3:16".to_string(),
                    translation: None,
                    verses_per_slide: None,
                    verse_numbers: None,
                }),
            )
            .unwrap();
        assert_eq!(
            edited.len(),
            plan.len(),
            "positive control: the item count is UNCHANGED — only content differs"
        );
        plan_repo::update(&db, plan_id, &edited).unwrap();

        assert!(
            super::resolve_autosave_slot(&db, slot).is_err(),
            "a content-only edit (same item count) must still invalidate the slot"
        );
    }
}

#[cfg(test)]
mod tests {

    /// The storage guard's verdict must reach the operator as FOUR outcomes, not three.
    ///
    /// A platform that cannot report free space is neither healthy nor critical. Mapping that
    /// `None` onto `"ok"` would tell the operator their disk is fine when nothing checked it —
    /// the same class of fabrication as rendering absent telemetry as a hard fault, just in the
    /// flattering direction.
    #[test]
    fn an_unreadable_disk_is_reported_as_unknown_never_as_ok() {
        assert_eq!(super::storage_tag(None), ("unknown", None));

        let (tag, bytes) =
            super::storage_tag(Some(super::guard::DiskStatus::Ok { available: 900 }));
        assert_eq!((tag, bytes), ("ok", Some(900)));

        let (tag, bytes) =
            super::storage_tag(Some(super::guard::DiskStatus::Low { available: 50 }));
        assert_eq!((tag, bytes), ("low", Some(50)));

        let (tag, bytes) =
            super::storage_tag(Some(super::guard::DiskStatus::Critical { available: 1 }));
        assert_eq!((tag, bytes), ("critical", Some(1)));
    }

    /// Every verdict needs its own tag, and every KNOWN verdict must carry its figure — a bare
    /// "ok" hides a slow slide toward the warning threshold until it crosses.
    #[test]
    fn every_storage_verdict_is_distinct_and_known_ones_carry_the_figure() {
        let cases = [
            None,
            Some(super::guard::DiskStatus::Ok { available: 900 }),
            Some(super::guard::DiskStatus::Low { available: 50 }),
            Some(super::guard::DiskStatus::Critical { available: 1 }),
        ];
        let mut tags: Vec<&str> = cases.iter().map(|c| super::storage_tag(*c).0).collect();
        let n = tags.len();
        tags.sort_unstable();
        tags.dedup();
        assert_eq!(tags.len(), n, "each verdict needs its own tag");

        for case in cases.into_iter().flatten() {
            assert!(
                super::storage_tag(Some(case)).1.is_some(),
                "a KNOWN verdict must report its free-space figure: {case:?}"
            );
        }
    }
    use super::{display_keys, smoke_mode_requested, MonitorFacts};

    #[test]
    fn smoke_mode_is_detected_from_arg_or_env() {
        // Neither the flag nor the env var: normal launch.
        assert!(!smoke_mode_requested(
            ["selahcue-output".to_string()].into_iter(),
            false
        ));
        // The `--smoke` argument enables it.
        assert!(smoke_mode_requested(
            ["selahcue-output".to_string(), "--smoke".to_string()].into_iter(),
            false
        ));
        // The env var enables it even without the argument.
        assert!(smoke_mode_requested(
            ["selahcue-output".to_string()].into_iter(),
            true
        ));
        // An unrelated flag does NOT enable it.
        assert!(!smoke_mode_requested(
            ["selahcue-output".to_string(), "--verbose".to_string()].into_iter(),
            false
        ));
    }

    fn m(name: Option<&str>, w: u32, h: u32, x: i32) -> MonitorFacts {
        MonitorFacts {
            name: name.map(String::from),
            width: w,
            height: h,
            x,
            y: 0,
        }
    }

    #[test]
    fn identical_monitors_get_distinct_position_ordered_keys() {
        // The two-identical-projectors venue: same name, same size. Keys must
        // differ, ordered by desktop position regardless of enumeration order.
        let keys = display_keys(&[
            m(Some("EPSON PJ"), 1920, 1080, 1920), // enumerated first, but RIGHT
            m(Some("EPSON PJ"), 1920, 1080, 0),    // LEFT
        ]);
        assert_eq!(keys[0].1, "EPSON PJ|1920x1080#2");
        assert_eq!(keys[1].1, "EPSON PJ|1920x1080#1");
        assert_eq!(keys[0].0, "EPSON PJ #2");
        // Re-enumeration in the other order yields the SAME key per position.
        let swapped = display_keys(&[
            m(Some("EPSON PJ"), 1920, 1080, 0),
            m(Some("EPSON PJ"), 1920, 1080, 1920),
        ]);
        assert_eq!(swapped[0].1, "EPSON PJ|1920x1080#1");
        assert_eq!(swapped[1].1, "EPSON PJ|1920x1080#2");
    }

    #[test]
    fn distinct_monitors_keep_plain_keys() {
        let keys = display_keys(&[
            m(Some("Color LCD"), 2560, 1600, 0),
            m(Some("EPSON PJ"), 1920, 1080, 2560),
            m(None, 1024, 768, 5000),
        ]);
        assert_eq!(keys[0].1, "Color LCD|2560x1600");
        assert_eq!(keys[1].1, "EPSON PJ|1920x1080");
        assert_eq!(keys[2].1, "Display 3|1024x768");
        assert_eq!(keys[2].0, "Display 3");
    }
}

#[cfg(all(test, feature = "encryption"))]
#[allow(clippy::unwrap_used)]
mod encryption_tests {
    use super::*;
    use selahcue_data::EncryptionKey;

    fn tmp(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "selahcue-openstore-{}-{}",
            name,
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir.join("selahcue.db3")
    }

    #[test]
    fn fresh_store_with_a_key_is_encrypted_and_reopens() {
        let path = tmp("fresh");
        let key = EncryptionKey::from_raw([7u8; 32]);
        let db = SessionStore::open_store(&path, Some((key, keys::KeySource::SecretStore)));
        assert!(db.is_ok());
        drop(db);
        // On disk it must NOT carry the plaintext SQLite magic.
        let head = std::fs::read(&path).unwrap();
        assert_ne!(&head[..16], b"SQLite format 3\0", "file is encrypted");
        // The right key reopens it; a wrong key hard-stops WITHOUT touching it.
        let again = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        );
        assert!(again.is_ok());
        drop(again);
        let before = std::fs::read(&path).unwrap();
        let wrong = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([9u8; 32]),
                keys::KeySource::Passphrase,
            )),
        );
        assert!(
            wrong.is_err(),
            "wrong key never opens (and never falls back)"
        );
        assert_eq!(std::fs::read(&path).unwrap(), before, "file untouched");
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn plaintext_store_is_opened_plain_never_keyed() {
        let path = tmp("plain");
        // Mint a plaintext store (the documented no-key first-run fallback).
        let db = SessionStore::open_store(&path, None);
        assert!(db.is_ok());
        drop(db);
        let head = std::fs::read(&path).unwrap();
        assert_eq!(&head[..16], b"SQLite format 3\0", "plaintext store");
        // A later run WITH a key must keep opening it plain (no keyed open of a
        // plain file, no wedge) — the review's first-run-hiccup scenario.
        let with_key = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        );
        assert!(
            with_key.is_ok(),
            "plaintext store keeps working with a key present"
        );
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn encrypted_store_without_a_key_hard_stops() {
        let path = tmp("nokey");
        drop(SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        ));
        let before = std::fs::read(&path).unwrap();
        let none = SessionStore::open_store(&path, None);
        assert!(
            none.is_err(),
            "no unencrypted attempt on an encrypted store"
        );
        assert_eq!(std::fs::read(&path).unwrap(), before, "file untouched");
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod fingerprint_tests {
    use super::pin_fingerprint;

    #[test]
    fn fingerprint_is_the_grouped_uppercase_pin_head() {
        // Mirrored byte-for-byte by the Dart pinFingerprint (see
        // mobile test/models/discovery_test.dart) — change together.
        assert_eq!(
            pin_fingerprint("ab12cd34ef56aa99bbccddee"),
            "AB12-CD34-EF56"
        );
        // Short pins group what they have without panicking.
        assert_eq!(pin_fingerprint("abcd"), "ABCD");
        assert_eq!(pin_fingerprint(""), "");
    }
}

#[cfg(test)]
mod ndi_tests {
    use super::{demo_plan, ndi_deliver, LiveController, NdiFrameCache, Theme};
    use std::cell::Cell;
    use std::collections::HashMap;
    use std::time::{Duration, Instant};

    /// A small controller (fast composes) with the default registry — `main` is an
    /// enabled Audience-class screen, so `compose_screen("main")` yields a frame.
    fn controller() -> LiveController {
        LiveController::new(demo_plan(), 320, 180, Theme::dark())
    }

    /// The dirty-gate itself (fix 1): while the controller's live generation holds still,
    /// repeated due ticks must RE-SEND the cached frame (NDI keeps receiving frames) but
    /// must NOT recompose — the ~69%-of-a-core full-raster recompose is the regression.
    #[test]
    fn unchanged_generation_re_sends_the_cached_frame_without_recomposing() {
        let c = controller();
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        let composes = Cell::new(0u32);
        let sends = Cell::new(0u32);
        let t0 = Instant::now();
        let generation = c.live_generation();
        for i in 0..3u64 {
            ndi_deliver(
                &mut frames,
                "main",
                generation,
                60,
                t0 + Duration::from_millis(100 * i), // 100ms apart: every tick is send-due
                || {
                    composes.set(composes.get() + 1);
                    c.compose_screen("main")
                },
                |_| sends.set(sends.get() + 1),
            );
        }
        assert_eq!(
            composes.get(),
            1,
            "an unchanged generation must compose once and then serve the cache"
        );
        assert_eq!(
            sends.get(),
            3,
            "every due tick must still put a frame on the wire (NDI stays alive)"
        );
    }

    /// The correctness half of the dirty-gate (fix 1c): a mutation that changes composed
    /// output must put the NEW frame on the wire — re-sending the stale cache here would be
    /// a worse bug than the recompose-per-tick it replaces.
    #[test]
    fn a_mutation_puts_the_new_frame_on_the_wire_not_the_cache() {
        use selahcue_lan::protocol::Command;
        let mut c = controller();
        c.apply(&Command::Next);
        c.apply(&Command::GoLive); // lit content on Live
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        let sent_luma = Cell::new(-1.0f64);
        let t0 = Instant::now();

        let g = c.live_generation();
        ndi_deliver(
            &mut frames,
            "main",
            g,
            60,
            t0,
            || c.compose_screen("main"),
            |fb| sent_luma.set(fb.average_luminance()),
        );
        assert!(
            sent_luma.get() > 1e-6,
            "sanity: the live item composes a lit frame (luma={})",
            sent_luma.get()
        );

        // An output-changing mutation via the public API — blackout blacks every screen.
        c.apply(&Command::Blackout { on: true });
        ndi_deliver(
            &mut frames,
            "main",
            c.live_generation(),
            60,
            t0 + Duration::from_millis(100),
            || c.compose_screen("main"),
            |fb| sent_luma.set(fb.average_luminance()),
        );
        assert!(
            sent_luma.get() < 1e-6,
            "after blackout the frame ON THE WIRE must be the new (black) compose, not the \
             cached lit frame (luma={})",
            sent_luma.get()
        );
    }

    /// Fix 2: `cfg.frame_rate` must PACE the wire, not just ride along as NDI metadata.
    /// At 30fps the ~16ms reconcile tick is not send-due; the next send comes at the
    /// configured period (1000/30 = 33ms). Time is injected — no wall-clock reads.
    #[test]
    fn frame_rate_paces_sends_to_the_configured_rate() {
        let c = controller();
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        let sends = Cell::new(0u32);
        let t0 = Instant::now();
        let g = c.live_generation();
        let deliver = |frames: &mut HashMap<String, NdiFrameCache>, at_ms: u64| {
            ndi_deliver(
                frames,
                "main",
                g,
                30,
                t0 + Duration::from_millis(at_ms),
                || c.compose_screen("main"),
                |_| sends.set(sends.get() + 1),
            );
        };
        deliver(&mut frames, 0);
        assert_eq!(sends.get(), 1, "the first frame goes out immediately");
        deliver(&mut frames, 16);
        assert_eq!(
            sends.get(),
            1,
            "16ms after a send, a 30fps screen is NOT due — the 60Hz loop tick must not \
             drive the wire"
        );
        deliver(&mut frames, 33);
        assert_eq!(
            sends.get(),
            2,
            "33ms (one 30fps period) after t0, exactly one more send"
        );
        deliver(&mut frames, 48);
        assert_eq!(
            sends.get(),
            2,
            "15ms later still inside the period — no send"
        );
    }

    /// A nonsense `frame_rate` (0 from a corrupt store, or an absurd 65535) must neither
    /// divide by zero nor stall the wire: the rate clamps into the documented config range
    /// `[MIN_FRAME_RATE, MAX_FRAME_RATE]` — exactly the bound the command path enforces.
    #[test]
    fn nonsense_frame_rate_clamps_instead_of_panicking_or_stalling() {
        let c = controller();
        let g = c.live_generation();
        let sends = Cell::new(0u32);
        let t0 = Instant::now();
        let deliver = |frames: &mut HashMap<String, NdiFrameCache>, fps: u16, at_ms: u64| {
            ndi_deliver(
                frames,
                "main",
                g,
                fps,
                t0 + Duration::from_millis(at_ms),
                || c.compose_screen("main"),
                |_| sends.set(sends.get() + 1),
            );
        };

        // fps = 0: clamps to MIN_FRAME_RATE (24fps, ~41ms period) — never a stall.
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        deliver(&mut frames, 0, 0);
        assert_eq!(
            sends.get(),
            1,
            "fps=0 must still put the first frame on the wire"
        );
        deliver(&mut frames, 0, 16);
        assert_eq!(sends.get(), 1, "inside the clamped 24fps period — not due");
        deliver(&mut frames, 0, 42);
        assert_eq!(
            sends.get(),
            2,
            "one 24fps period on, the wire must move again"
        );

        // fps = 65535: clamps to MAX_FRAME_RATE (60fps, ~16ms period), not a send storm.
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        sends.set(0);
        deliver(&mut frames, u16::MAX, 0);
        deliver(&mut frames, u16::MAX, 8);
        assert_eq!(sends.get(), 1, "8ms after a send even 60fps is not due");
        deliver(&mut frames, u16::MAX, 16);
        assert_eq!(sends.get(), 2, "a 60fps period on, due again");
    }

    /// Bounded-memory rule (CLAUDE.md): each cached frame is ~8.3MB at 1080p, so the cache
    /// must be bounded by the LIVE screen set — an entry for a deleted screen, or for a
    /// screen whose NDI delivery is off, must be dropped by the same reconcile that prunes
    /// the sender/backoff/warned maps.
    #[test]
    fn reconcile_prunes_the_frame_cache_with_the_screen_set() {
        use std::collections::HashSet;
        let c = controller();
        let now = Instant::now();
        let Some(frame_a) = c.compose_screen("main") else {
            panic!("main composes in the default registry");
        };
        let Some(frame_b) = c.compose_screen("main") else {
            panic!("main composes in the default registry");
        };
        let mut senders: HashMap<String, super::video_sink::NdiOutput> = HashMap::new();
        let mut backoff: HashMap<String, Instant> = HashMap::new();
        let mut warned: HashSet<String> = HashSet::new();
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        // A cache entry for a screen that no longer exists in the registry…
        frames.insert(
            "deleted-screen".to_string(),
            NdiFrameCache {
                generation: 0,
                frame: frame_a,
                next_send: now,
            },
        );
        // …and one for a live screen with NO NDI delivery configured (want = false).
        frames.insert(
            "main".to_string(),
            NdiFrameCache {
                generation: 0,
                frame: frame_b,
                next_send: now,
            },
        );
        super::reconcile_ndi(
            &c,
            &mut senders,
            &mut backoff,
            &mut warned,
            &mut frames,
            now,
        );
        assert!(
            frames.is_empty(),
            "the frame cache must be pruned with the screen set (still holds: {:?})",
            frames.keys().collect::<Vec<_>>()
        );
    }

    /// The other half of the bound: many ticks and generation churn never GROW the cache —
    /// one live screen means exactly one entry, no matter how long the loop runs.
    #[test]
    fn frame_cache_never_grows_past_one_entry_per_screen() {
        let c = controller();
        let mut frames: HashMap<String, NdiFrameCache> = HashMap::new();
        let t0 = Instant::now();
        for i in 0..500u64 {
            ndi_deliver(
                &mut frames,
                "main",
                i, // a NEW generation every tick — worst-case churn
                60,
                t0 + Duration::from_millis(i * 100),
                || c.compose_screen("main"),
                |_| (),
            );
        }
        assert_eq!(
            frames.len(),
            1,
            "500 ticks with 500 generations must still hold exactly one cache entry"
        );
        assert!(
            frames.len() <= super::NDI_FRAME_CACHE_MAX_ENTRIES,
            "the cache must respect its published cap"
        );
        assert_eq!(
            super::NDI_FRAME_CACHE_MAX_ENTRIES,
            selahcue_app::MAX_SCREENS,
            "the cache is bounded by the screen registry: one entry per screen at most"
        );
        // Assert the ACTUAL resident bytes, not a proxy: exactly one 320x180 RGBA frame
        // (230_400 bytes) may remain resident — churn must not retain hidden buffers.
        let resident: usize = frames.values().map(|e| e.frame.bytes().len()).sum();
        assert_eq!(
            resident,
            320 * 180 * 4,
            "resident cache bytes must be exactly one composed frame after 500 generations"
        );
    }
}

/// The host's NFR-024 fault PRODUCERS.
///
/// `Presenter::inject_fault` and `LiveController::report_fault` were complete, tested and
/// called by nothing outside `tests/` — so on the shipped host `output_health` was
/// permanently `{"held":false}` and the operator console's held-frame and recovery states
/// could never appear. These tests drive the real host producers
/// ([`report_fault_edge`] plus the two level functions that feed it) and read the result back
/// out of `operator_view()`, so a producer that stops firing, or fires too often, fails here.
///
/// The GPU and filesystem halves themselves are not runnable in CI, so — following the
/// `window_lifecycle_tests` precedent in this file — the DECISIONS are tested here and the
/// winit/wgpu half only performs what these tests pin.
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod output_fault_tests {
    use super::{
        demo_plan, disk_fault_active, fault_slot, report_fault_edge, surface_fault_active,
        telemetry_of, Command, Fault, FaultLatch, LiveController, OutputTelemetry, Theme,
        FAULT_KINDS,
    };
    use std::sync::Mutex;
    use std::time::{Duration, Instant};

    /// Four seconds of a ~60 Hz frame loop. Every "sustained fault" test drives at least this
    /// many frames, because that is the number the bug produces: an unlatched producer would
    /// report `SUSTAINED_FRAMES` holds where the operator saw ONE.
    const SUSTAINED_FRAMES: usize = 240;
    /// Pinned at compile time: a single-frame loop would make every anti-inflation assertion
    /// below vacuously true, and nothing at runtime could notice.
    const _: () = assert!(SUSTAINED_FRAMES > 1);

    /// A small controller (fast composes) with real content on Live, so a hold has a good
    /// frame to hold ONTO and `holds` / `recoveries` mean something.
    fn controller() -> Mutex<LiveController> {
        let mut c = LiveController::new(demo_plan(), 320, 180, Theme::dark());
        let first = c.plan().items()[0].id.0;
        c.apply(&Command::SelectItem { item_id: first });
        c.apply(&Command::GoLive);
        assert!(
            !c.operator_view().output_health.unwrap().held,
            "test setup: a fresh host must start healthy, or a hold assertion proves nothing"
        );
        Mutex::new(c)
    }

    /// `(held, fault tag, holds, recoveries)` as the operator console actually receives them.
    fn health(c: &Mutex<LiveController>) -> (bool, Option<String>, u64, u64) {
        let v = c
            .lock()
            .unwrap()
            .operator_view()
            .output_health
            .expect("a host that owns a compositor must always report health, even good news");
        (v.held, v.fault, v.holds, v.recoveries)
    }

    /// Drive a successful compose — the only way an output recovers. There is no "recover"
    /// call for the host to make; the engine clears the hold on the next good frame.
    fn compose_a_good_frame(c: &Mutex<LiveController>) {
        let mut g = c.lock().unwrap();
        let last = g.plan().items()[3].id.0;
        g.apply(&Command::SelectItem { item_id: last });
        g.apply(&Command::GoLive);
    }

    /// End to end: the host producer must reach `output_health` and NAME the fault. A hold
    /// the operator cannot name is barely better than no hold at all — "something is wrong"
    /// is not an instruction.
    #[test]
    fn a_fault_reported_by_the_host_producer_reaches_output_health_as_a_named_hold() {
        let c = controller();
        let mut latch = FaultLatch::default();

        let reported = report_fault_edge(&mut latch, &c, Fault::GpuDeviceLost, true);

        assert!(
            reported,
            "the producer must report the first frame of an incident — if it reported \
             nothing, every assertion below is about a mechanism that never ran"
        );
        let (held, fault, holds, recoveries) = health(&c);
        assert!(held, "the operator view must report the output HELD");
        assert_eq!(
            fault.as_deref(),
            Some("gpu_device_lost"),
            "and must name the reason the operator has to act on"
        );
        assert_eq!(holds, 1, "the hold must be counted exactly once");
        assert_eq!(recoveries, 0, "nothing has recovered yet");
    }

    /// **The anti-inflation control.** `autosave` runs every frame (~60 Hz) and both fault
    /// signals are LEVELS that stay true for as long as the trouble lasts. A producer that
    /// reported the level rather than the edge would add sixty holds a second: an unbounded
    /// counter, and a live lie about how many times the audience output was held. The count
    /// asserted here is exact for that reason — `> 0` would pass the very bug it exists for.
    #[test]
    fn a_fault_sustained_across_many_frames_is_counted_exactly_once() {
        const _: () = assert!(SUSTAINED_FRAMES > 1);
        let c = controller();
        let mut latch = FaultLatch::default();

        let mut reports = 0usize;
        for _ in 0..SUSTAINED_FRAMES {
            if report_fault_edge(&mut latch, &c, Fault::DiskFull, true) {
                reports += 1;
            }
        }

        assert_eq!(
            reports, 1,
            "the producer must fire on the TRANSITION into a fault: {SUSTAINED_FRAMES} \
             frames of one full disk is ONE incident, not {SUSTAINED_FRAMES}"
        );
        let (held, fault, holds, recoveries) = health(&c);
        assert!(held, "and the output must still be held throughout");
        assert_eq!(fault.as_deref(), Some("disk_full"));
        assert_eq!(
            holds, 1,
            "`holds` counts INCIDENTS, not frames — a per-frame report would read {SUSTAINED_FRAMES}"
        );
        assert_eq!(recoveries, 0);
    }

    /// The positive control. "Reported nothing" and "the producer is dead" are the same
    /// observation unless the benign path is also exercised, so this drives a long healthy
    /// stretch through the SAME call and then proves a real fault still gets through.
    #[test]
    fn a_healthy_stretch_reports_nothing_and_leaves_the_producer_live() {
        const _: () = assert!(SUSTAINED_FRAMES > 1);
        let c = controller();
        let mut latch = FaultLatch::default();

        let mut reports = 0usize;
        for _ in 0..SUSTAINED_FRAMES {
            if report_fault_edge(&mut latch, &c, Fault::GpuDeviceLost, false) {
                reports += 1;
            }
        }
        assert_eq!(reports, 0, "a healthy surface must never report a fault");
        assert_eq!(
            health(&c).2,
            0,
            "and must never move the hold counter the operator reads"
        );

        assert!(
            report_fault_edge(&mut latch, &c, Fault::GpuDeviceLost, true),
            "after {SUSTAINED_FRAMES} healthy frames a REAL fault must still be reported — \
             without this, 'reported nothing' above is equally consistent with a producer \
             that can no longer report anything at all"
        );
        assert_eq!(health(&c).2, 1, "and it must reach the operator view");
    }

    /// Recovery: implicit, and it must clear both the hold and the reason.
    #[test]
    fn a_good_frame_after_a_reported_fault_clears_the_hold_and_counts_the_recovery() {
        let c = controller();
        let mut latch = FaultLatch::default();
        assert!(
            report_fault_edge(&mut latch, &c, Fault::GpuDeviceLost, true),
            "premise: the producer reported, or there is no hold to recover from"
        );
        assert!(health(&c).0, "premise: the output is held");

        compose_a_good_frame(&c);

        let (held, fault, holds, recoveries) = health(&c);
        assert!(!held, "a good frame must clear the hold");
        assert_eq!(
            fault, None,
            "a recovered output must name NO fault — a stale reason beside a healthy output \
             is exactly the lie this seam exists to prevent"
        );
        assert_eq!(holds, 1);
        assert_eq!(recoveries, 1, "and the recovery must be counted");
    }

    /// The latch must be a gate, not a mute. A second, genuinely separate incident has to be
    /// counted separately — otherwise the fix for per-frame inflation would silently become
    /// "report the first fault of the service and nothing ever again", which is the same
    /// blindness in the other direction. Bounded-memory control too: 500 incidents accumulate
    /// nothing but counters.
    #[test]
    fn each_new_incident_is_counted_again_and_nothing_accumulates() {
        const INCIDENTS: usize = 500;
        const FRAMES_PER_INCIDENT: usize = 10;
        const _: () = assert!(INCIDENTS > 1 && FRAMES_PER_INCIDENT > 1);
        let c = controller();
        let mut latch = FaultLatch::default();

        let mut reports = 0usize;
        for _ in 0..INCIDENTS {
            for _ in 0..FRAMES_PER_INCIDENT {
                if report_fault_edge(&mut latch, &c, Fault::DiskFull, true) {
                    reports += 1;
                }
            }
            // The disk drops back below the floor's threshold: the incident is over.
            report_fault_edge(&mut latch, &c, Fault::DiskFull, false);
        }

        assert_eq!(
            reports, INCIDENTS,
            "each of {INCIDENTS} separate incidents must report exactly once — no more \
             (per-frame inflation) and no fewer (a latch that never reopens)"
        );
        assert_eq!(health(&c).2, INCIDENTS as u64);
        assert_eq!(
            std::mem::size_of_val(&latch),
            FAULT_KINDS,
            "the latch must still be one bool per fault kind after {INCIDENTS} incidents — \
             an event log or a per-incident collection would have grown here"
        );
    }

    /// Fault kinds must not share a latch slot: a full disk that muted a lost GPU (or the
    /// reverse) would hide the more serious of the two behind the one that happened first.
    #[test]
    fn each_fault_kind_latches_independently() {
        const _: () = assert!(FAULT_KINDS == 4);
        assert_eq!(
            Fault::ALL.len(),
            FAULT_KINDS,
            "premise: one latch slot per fault kind"
        );
        let mut seen = [false; FAULT_KINDS];
        for f in Fault::ALL {
            let slot = fault_slot(f);
            assert!(
                !seen[slot],
                "two fault kinds share latch slot {slot} — one would mute the other"
            );
            seen[slot] = true;
        }

        let c = controller();
        let mut latch = FaultLatch::default();
        assert!(report_fault_edge(&mut latch, &c, Fault::DiskFull, true));
        assert!(
            report_fault_edge(&mut latch, &c, Fault::GpuDeviceLost, true),
            "a full disk must not suppress a lost surface — they are different incidents"
        );
        assert_eq!(health(&c).2, 2, "both must reach the operator view");
    }

    /// The wgpu half of the producer: which telemetry state actually means "the audience
    /// could not be given the frame".
    #[test]
    fn a_deferred_present_is_the_surface_fault_and_a_lifetime_drop_count_is_not() {
        let now = Instant::now();
        assert!(
            !surface_fault_active(None),
            "no main window at all means nothing was attempted, so nothing failed"
        );
        assert!(
            !surface_fault_active(telemetry_of(&None)),
            "and the host's own accessor for an absent output must agree"
        );

        let mut t = OutputTelemetry::new();
        assert!(
            !surface_fault_active(Some(&t)),
            "a fresh output has not failed a present"
        );
        t.record(now, true);
        assert!(
            !surface_fault_active(Some(&t)),
            "a successful present is not a fault"
        );

        t.record(now + Duration::from_millis(16), false);
        assert!(
            surface_fault_active(Some(&t)),
            "a deferred present — a lost/outdated swapchain — IS the surface fault"
        );
        assert_eq!(
            t.dropped_frames, 1,
            "premise: the deferred present was counted, so the next assertion is about a \
             non-zero lifetime drop count"
        );

        t.record(now + Duration::from_millis(32), true);
        assert!(
            !surface_fault_active(Some(&t)),
            "a good present clears the fault: the level is the LAST attempt's outcome, not \
             the lifetime `dropped_frames` count, which never comes back down and would \
             pin the output held for the rest of the service"
        );
    }

    /// The storage half: only the verdict that actually halts writes is a fault.
    #[test]
    fn only_a_critical_disk_is_the_full_disk_fault() {
        use super::guard::{disk_status_from, DiskStatus, DISK_CRITICAL, DISK_LOW};
        const _: () = assert!(DISK_CRITICAL < DISK_LOW);

        assert!(
            !disk_fault_active(None),
            "a platform that cannot report free space has not told us the disk is full"
        );
        assert!(!disk_fault_active(Some(disk_status_from(u64::MAX))));

        // Pin each premise through the guard's OWN mapping, so changing a threshold cannot
        // leave this test asserting about a status the guard no longer produces there.
        let low = disk_status_from(DISK_LOW - 1);
        assert!(
            matches!(low, DiskStatus::Low { .. }),
            "premise: just below DISK_LOW is the Low verdict"
        );
        assert!(
            !disk_fault_active(Some(low)),
            "a LOW-headroom warning must not hold the audience output: checkpoint writes \
             continue, and every service on a filling drive would be told its output is held"
        );

        let critical = disk_status_from(DISK_CRITICAL - 1);
        assert!(
            matches!(critical, DiskStatus::Critical { .. }),
            "premise: below the floor is the Critical verdict"
        );
        assert!(
            disk_fault_active(Some(critical)),
            "the full-disk verdict IS the fault (present.rs names this mapping verbatim)"
        );
    }
}
