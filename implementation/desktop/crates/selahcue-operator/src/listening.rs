//! On-device speech-to-text **source** for the live transcript (feature `stt`).
//!
//! When the operator presses "Start listening", [`start`] spins up a background worker that
//! captures the microphone (`cpal`), transcribes on-device (`whisper.cpp`), and feeds each
//! recognised segment into the controller — running exact + fuzzy scripture detection and
//! populating the transcript / detection panels.
//!
//! It works whether or not an output window is open: segments are ingested through the
//! backend's own dual path (`Backend::ingest_transcript`), which drives the local in-process
//! controller **or** forwards over the pinned-TLS wire to a connected output-window host. The
//! ingest runs on the Tauri async runtime (a drain task), so the remote wire I/O uses the
//! runtime its socket lives on; the audio worker stays on its own thread, out-of-band from
//! render (the audience output never waits on it).
//!
//! Compiled only under `stt`, which pulls the native whisper/cpal toolchain — so the default
//! operator build (and CI's compile-check) needs neither. The model is resolved from a cache
//! or downloaded on demand, and **integrity-verified before load** (FR-156 / ADR-0012). Real
//! accuracy/latency are spike-gated (S8/S11).
//!
//! # Cloud routing (86akby7th)
//!
//! `start()` decides once, via `crate::transcription_route::TranscriptionRoute::decide`,
//! whether this capture session streams to Deepgram or runs on-device — the decision consumes
//! the persisted `TranscriptionMode`, the core's `may_stream_cloud_audio()` consent gate, and
//! `selahcue_stt_cloud::readiness()` (built vs. not, key present vs. not). Selecting Cloud
//! without consent, without a key, or in a build without the `cloud-stt` feature falls back to
//! on-device **before ever attempting to stream** — never silently, always with a note the
//! console can show (`engine_note()`). A Cloud session that fails or stalls **mid-service**
//! falls back the same way, reusing the already-open microphone so the operator is never
//! re-prompted and the transcript never goes blank while the switch happens (FR-135,
//! NFR-024) — see `run_cloud` (behind `cloud-stt`) and `run_on_device`, the single on-device
//! path both the initial choice and every fallback route through.

use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use selahcue_core::transcript::{ProviderSegment, TranscriptProvider};
use selahcue_stt::audio::{AudioSource, CpalSource};
use selahcue_stt::recognizer::{WhisperContext, WhisperRecognizer};
use selahcue_stt::{pump, EnergyVad, EngineConfig, FeedbackGuard, HardwareProbe, SttEngine};
use tauri::{AppHandle, Emitter, Manager};

use crate::capture_handoff::AudioHandoff;
use crate::transcription_route::TranscriptionRoute;

/// What `run_on_device` (and, via `emit_level`, `run_cloud_stream_loop`) need from a capture
/// source beyond [`AudioSource`] itself (`next_chunk`/`label`) — kept to exactly the one extra
/// operation those call (`emit_level`'s peak reading), so both can be generic and exercised in
/// tests against a `FakeAudioSource`-backed stand-in with no real microphone, while
/// [`CpalSource`] satisfies it unchanged for the real capture path (86akby7th PR #22 review,
/// Quinn's "zero coverage" — see `run_cloud_stream_loop`).
trait CaptureSource: AudioSource {
    /// Peak input amplitude (`0..=1`) since the previous call. See [`CpalSource::peak_level`].
    fn peak_level(&self) -> f32;
}

impl CaptureSource for CpalSource {
    fn peak_level(&self) -> f32 {
        CpalSource::peak_level(self)
    }
}

/// What `run_cloud` additionally needs, beyond [`CaptureSource`], to size the capture hand-off
/// from the device's REAL configuration rather than a literal (`sample_rate`/`channels` feed
/// `selahcue_core::audio_capacity::handoff_capacity`). A separate trait, rather than folding
/// these into `CaptureSource` itself, so an `stt`-only build (no `cloud-stt`) — which never
/// calls `run_cloud` at all — does not carry two methods nothing in that build can reach
/// (`-D warnings` would otherwise flag them `dead_code`). Extended in the PR #22 remediation
/// round 2 so `run_cloud` ITSELF, not only its inner loop, can be driven by a test — see
/// `cloud_session_config`.
#[cfg(feature = "cloud-stt")]
trait CloudCaptureSource: CaptureSource {
    /// The device's sample rate, Hz. See [`CpalSource::sample_rate`].
    fn sample_rate(&self) -> u32;
    /// The device's channel count. See [`CpalSource::channels`].
    fn channels(&self) -> u16;
}

#[cfg(feature = "cloud-stt")]
impl CloudCaptureSource for CpalSource {
    fn sample_rate(&self) -> u32 {
        CpalSource::sample_rate(self)
    }
    fn channels(&self) -> u16 {
        CpalSource::channels(self)
    }
}

/// How often the SOURCE thread drains the mic ring into the hand-off + emits the live level.
/// Short so the meter stays smooth and the capture ring never overflows (independent of decode).
const CAPTURE_INTERVAL: Duration = Duration::from_millis(50);

/// How often the RECOGNITION thread polls the hand-off for new audio to transcribe.
const RECOG_INTERVAL: Duration = Duration::from_millis(30);

/// Sliding-window bound (16 kHz mono samples) for an INTERIM decode — each interim re-decodes at
/// most the last ~6 s, so the live line stays near real time no matter how long the speaker talks
/// (the final on close still decodes the whole utterance for accuracy).
const INTERIM_WINDOW_SAMPLES: usize = 6 * 16_000;

/// Bound on device audio buffered in the source→recognition hand-off (~5 s at 48 kHz stereo). The
/// hand-off drops OLDEST beyond this if the recognizer falls behind, keeping it near the live edge
/// (bounded memory — no-leak).
///
/// **Known issue, not touched by 86akby7th**: this literal assumes stereo (`× 2`); on a mono
/// microphone the real window is double what is intended. Tracked and being fixed separately —
/// the value is unchanged here on purpose. Only the TYPE changed, to `NonZeroUsize`, because
/// `AudioHandoff::new` (now shared with the Cloud route, `capture_handoff.rs`) requires one; the
/// fix for the VALUE itself is to call `selahcue_core::audio_capacity::handoff_capacity` with
/// this device's real sample rate and channel count instead of this literal.
const HANDOFF_MAX_SAMPLES: NonZeroUsize = match NonZeroUsize::new(48_000 * 2 * 5) {
    Some(n) => n,
    None => panic!("HANDOFF_MAX_SAMPLES literal must be nonzero"),
};

// Pins the domain relationship the startup-backlog tests' NARRATIVE relies on (Quinn, 86akd1jcc
// review): `PcmRing`'s own worst-case retention (`selahcue_stt::audio::MAX_PCM_SAMPLES`) is
// meant to exceed this hand-off's cap — `PcmRing` exists specifically to buffer MORE audio,
// for longer, than `AudioHandoff` would ever want to retain (see `flush_pending_backlog`'s doc
// comment). If a future edit ever made `MAX_PCM_SAMPLES` smaller than `HANDOFF_MAX_SAMPLES`,
// every place in this file that calls a `MAX_PCM_SAMPLES`-sized backlog "the worst case" would
// be describing a number smaller than the thing it is supposed to be worse than.
//
// **This does NOT, by itself, make `a_real_cold_start_backlog_no_longer_trips_the_notice`
// sensitive to either constant's value** — that test's own doc comment says so plainly. Quinn
// proved this by shrinking `MAX_PCM_SAMPLES` to 100 (a 288,000× reduction) and watching that
// test stay green: `flush_pending_backlog`'s effect on the disclosure is the boolean `flushed >
// 0`, not a magnitude comparison against either constant, so ANY nonzero backlog produces the
// identical outcome. What this assertion protects is narrower and honest about it: the
// RELATIONSHIP the test's prose claims (a `MAX_PCM_SAMPLES`-sized backlog stands in for "the
// worst case a real mic's ring could hand over") stays true, even though nothing here can make
// the note-firing behavior itself depend on it. Restated as a runtime `assert!` inside that
// test too — see there.
const _: () = assert!(
    selahcue_stt::audio::MAX_PCM_SAMPLES > HANDOFF_MAX_SAMPLES.get(),
    "MAX_PCM_SAMPLES must exceed HANDOFF_MAX_SAMPLES, or a MAX_PCM_SAMPLES-sized backlog is no \
     longer an honest stand-in for PcmRing's worst case relative to this hand-off's cap"
);

/// The Tauri event the operator webview listens on for first-run model-download progress, so
/// the "Start listening" control can show "Downloading model… N%" instead of a dead button
/// while the ~1.6 GB model is fetched. Purely advisory — readiness is still the command's
/// return value; the UI works without these events (it just shows a generic "Preparing…").
const PROGRESS_EVENT: &str = "stt://progress";

/// Payload for [`PROGRESS_EVENT`]: bytes fetched so far, the total, and a whole-percent.
#[derive(Clone, serde::Serialize)]
struct DownloadProgress {
    done: u64,
    total: u64,
    pct: u8,
}

/// The Tauri event carrying the FULL download lifecycle, so the operator's "Offline Download
/// Modal" (Figma node 396-124) can render a distinct state per phase: downloading (bytes + %),
/// verifying (SHA-256), ready, or a classified failure. The legacy [`PROGRESS_EVENT`] is still
/// emitted during downloading, so anything already listening on `stt://progress` keeps working.
const PHASE_EVENT: &str = "stt://phase";

/// Serializable payload for [`PHASE_EVENT`] — an internally-tagged mirror of
/// [`selahcue_stt::DownloadPhase`] (that domain enum is serde-free, so the operator maps it here).
/// The `phase` tag lets the webview switch on the state; the JSON shapes are:
/// - `{"phase":"downloading","done":N,"total":N,"pct":P}`
/// - `{"phase":"verifying"}`
/// - `{"phase":"ready"}`
/// - `{"phase":"failed","reason":"connect|offline|verify|other","message":"…","resumable":bool,"bytes_kept":N}`
#[derive(Clone, serde::Serialize)]
#[serde(tag = "phase", rename_all = "snake_case")]
enum PhaseEvent {
    Downloading {
        done: u64,
        total: u64,
        pct: u8,
    },
    Verifying,
    Ready,
    Failed {
        reason: FailReasonPayload,
        message: String,
        resumable: bool,
        bytes_kept: u64,
    },
}

/// Why a download failed, mirrored from [`selahcue_stt::FailReason`] onto the wire (snake_case):
/// `connect` (couldn't reach/read the server), `offline` (DNS/no connection), `verify` (integrity
/// check failed → discarded), `other` (filesystem/config).
#[derive(Clone, Copy, serde::Serialize)]
#[serde(rename_all = "snake_case")]
enum FailReasonPayload {
    Connect,
    Offline,
    Verify,
    Other,
}

/// Map a domain [`selahcue_stt::DownloadPhase`] onto the webview events: always emit the rich
/// [`PHASE_EVENT`]; during downloading ALSO emit the legacy [`PROGRESS_EVENT`] so nothing that
/// listens on `stt://progress` breaks. Advisory — send errors (no window yet) are ignored, and a
/// short log line aids first-run debugging.
fn emit_phase<R: tauri::Runtime>(app: &AppHandle<R>, phase: selahcue_stt::DownloadPhase) {
    use selahcue_stt::{DownloadPhase as P, FailReason as R};
    let event = match phase {
        P::Downloading { done, total } => {
            // Pre-existing pattern rewritten only to satisfy `clippy::manual_checked_ops`
            // (86akby7th sweeps `listening.rs` through `-D warnings` clippy for the first time
            // via the new `cloud-stt` gate below — `stt` itself was never linted in CI before
            // this ticket, the same "compiled by nothing" shape `CLAUDE.md` already tracks for
            // `selahcue-stt` under 86ak5rjh7). Same behaviour: `total == 0` still yields `0`.
            let pct = done.saturating_mul(100).checked_div(total).unwrap_or(0) as u8;
            // Keep the original byte-progress event working for existing listeners.
            let _ = app.emit(PROGRESS_EVENT, DownloadProgress { done, total, pct });
            eprintln!("SelahCue STT: downloading model … {pct}%");
            PhaseEvent::Downloading { done, total, pct }
        }
        P::Verifying => {
            eprintln!("SelahCue STT: verifying model integrity (SHA-256)…");
            PhaseEvent::Verifying
        }
        P::Ready => {
            eprintln!("SelahCue STT: model ready.");
            // The detector is healthy again — drop any earlier verdict.
            clear_failure();
            PhaseEvent::Ready
        }
        P::Failed {
            reason,
            message,
            resumable,
            bytes_kept,
        } => {
            eprintln!("SelahCue STT: download failed ({reason:?}): {message}");
            // Retain it: the event alone is fire-and-forget and would otherwise be lost,
            // leaving a dead detector indistinguishable from an idle one.
            record_failure(message.clone());
            PhaseEvent::Failed {
                reason: match reason {
                    R::Connect => FailReasonPayload::Connect,
                    R::Offline => FailReasonPayload::Offline,
                    R::Verify => FailReasonPayload::Verify,
                    R::Other => FailReasonPayload::Other,
                },
                message,
                resumable,
                bytes_kept,
            }
        }
    };
    let _ = app.emit(PHASE_EVENT, event);
}

/// The Tauri event carrying a live microphone level (peak percent) while listening, so the
/// "waiting for speech…" status can show whether audio is actually arriving — a peak stuck at
/// 0 while the operator speaks points at mic/permission, not the transcript UI.
const LEVEL_EVENT: &str = "stt://level";

/// Payload for [`LEVEL_EVENT`]: peak input amplitude as a whole percent (`0..=100`).
#[derive(Clone, serde::Serialize)]
struct MicLevel {
    pct: u8,
}

/// Bound on segments buffered between the audio worker and the ingest drain task (no-leak).
const SEGMENT_QUEUE: usize = 256;

/// A running capture/transcription worker.
struct Worker {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

/// The single active worker (at most one — "listening" is a global capture state).
static WORKER: Mutex<Option<Worker>> = Mutex::new(None);

/// Process-wide CANCEL flag for an in-flight first-run model download. Reset to `false` at the
/// start of every download attempt (in [`load_recognizer`]) and set to `true` by
/// [`cancel_download`] (and by [`stop`], so "Stop listening" also aborts a download in progress).
/// The fetch loop polls it once per streamed chunk; on cancel it removes the partial `.part` file
/// and returns a terminal `Failed{…"cancelled"}` phase. It is a plain flag — reading/writing it
/// never takes the worker lock, so cancelling can never deadlock against the worker thread, and it
/// is a no-op when no download is running (the next download simply resets it before fetching).
static DOWNLOAD_CANCEL: AtomicBool = AtomicBool::new(false);

/// Lock the worker slot, recovering from a poisoned lock (a prior panic must not make the
/// worker permanently unstoppable — recover the guard and continue).
fn worker_lock() -> std::sync::MutexGuard<'static, Option<Worker>> {
    WORKER.lock().unwrap_or_else(|e| e.into_inner())
}

/// Whether a capture worker is currently running.
pub fn is_listening() -> bool {
    worker_lock().is_some()
}

/// The last TERMINAL failure the detector reported, retained until the next attempt.
///
/// `stt://phase` is fire-and-forget: a `Failed` phase that nothing happened to be listening
/// for is simply lost, which leaves a DEAD detector looking exactly like an idle one — the
/// confusion the acceptance bar names. Retaining it here is what lets
/// `selahcue_core::detector::detector_state` tell those two apart. Bounded: exactly one
/// `Option<String>`, replaced rather than accumulated, so it can never grow.
static LAST_FAILURE: Mutex<Option<String>> = Mutex::new(None);

/// The transcript provider's honest label (FR-120 — the UI states which engine produced the
/// transcript, and never claims a perfect one). Set when a worker starts, cleared when it
/// stops. Bounded: one `Option<String>`.
static PROVIDER_LABEL: Mutex<Option<String>> = Mutex::new(None);

/// A note explaining WHY the running engine is not what Settings says, or that it changed
/// mid-service — `None` when there is nothing to explain (on-device chosen outright, or Cloud
/// selected and streaming normally). Distinct from [`LAST_FAILURE`]: a note here is not
/// necessarily a failure (e.g. consent not yet granted), and a failure does not always need a
/// note (an on-device model-load error has nowhere else to fall back to). Set at capture start
/// from `TranscriptionRoute::fallback_reason()`, or by `run_cloud` on a mid-service handoff.
/// Bounded: one `Option<String>`, replaced rather than accumulated.
static ENGINE_NOTE: Mutex<Option<String>> = Mutex::new(None);

fn status_lock<T>(m: &'static Mutex<Option<T>>) -> std::sync::MutexGuard<'static, Option<T>> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Record a terminal failure — the detector is down until something clears this.
fn record_failure(message: impl Into<String>) {
    *status_lock(&LAST_FAILURE) = Some(message.into());
}

/// Clear the retained failure: a fresh attempt supersedes an old verdict, so a recovered
/// detector is never still reported dead.
fn clear_failure() {
    *status_lock(&LAST_FAILURE) = None;
}

/// Set the audio-dropped notice WITHOUT erasing a distinct note already there — appending
/// rather than replacing.
///
/// `ENGINE_NOTE` is a single slot, and a mid-service engine-change disclosure (e.g.
/// [`selahcue_stt_cloud::DEGRADED_FALLBACK_NOTICE`]) and a LATER audio-dropped notice
/// ([`ON_DEVICE_AUDIO_DROPPED_NOTICE`] / [`AUDIO_DROPPED_NOTICE`]) can both be true about the
/// same session — a fallback happened, AND the fallback engine later fell behind. Writing the
/// drop notice straight into the slot (the previous behaviour) silently erased the disclosure
/// that explained why the engine changed in the first place, which is exactly the kind of
/// stale-looking honesty gap this ticket's other fixes remove elsewhere (86akby7th PR #22
/// review, LOW: "do not let a drop note erase an engine-change note"). Idempotent: calling it
/// twice with the same `addition` does not duplicate the suffix.
///
/// **Not bounded by this function.** The idempotence check above only stops the SAME `addition`
/// from being appended twice in a row (suffix match) — it does not cap how many DISTINCT
/// fragments accumulate. Boundedness today is a property of the two call sites (each session
/// appends at most one engine-change note and one drop note), not of `append_engine_note`
/// itself; a future third caller alternating between two different additions would grow this
/// slot without limit (86akby7th PR #22 remediation round 2, Vera LOW).
fn append_engine_note(addition: &str) {
    let mut slot = status_lock(&ENGINE_NOTE);
    let next = match slot.take() {
        // Already there (a prior call already appended it, or it IS the whole note): keep it —
        // re-appending on every poll while the sticky drop condition holds would otherwise
        // compound into a note that keeps growing.
        Some(existing) if !existing.is_empty() && existing.ends_with(addition) => existing,
        Some(existing) if !existing.is_empty() => format!("{existing} {addition}"),
        _ => addition.to_string(),
    };
    *slot = Some(next);
}

/// The live `ProvidersConfig`, read fresh from shared app state — never a snapshot taken
/// earlier in this capture session.
///
/// Used two ways in `run_cloud` (86akby7th PR #22 review):
/// - to (re-)prove Cloud eligibility immediately before minting a `StreamAuthorization`, rather
///   than trusting the snapshot `start()` decided the route from a moment ago — `CpalSource::new()`
///   can block for as long as the OS mic-permission dialog is up, and the operator can revoke
///   consent or leave Cloud mode during that wait (Cody, High: the old code re-derived
///   `StreamAuthorization::from_config(&providers_snapshot)` from that same frozen clone, so it
///   structurally could not see a change — the comment claiming otherwise was wrong, not just the
///   behaviour);
/// - polled every iteration of the streaming loop so a mid-service revocation (or leaving Cloud
///   mode) is caught within one `CAPTURE_INTERVAL`, not only at the moment streaming started
///   (Sana, High).
#[cfg(feature = "cloud-stt")]
fn live_providers_config<R: tauri::Runtime>(
    app: &AppHandle<R>,
) -> selahcue_core::providers::ProvidersConfig {
    let state = app.state::<crate::AppState>();
    let guard = state.providers.lock().unwrap_or_else(|e| e.into_inner());
    guard.clone()
}

/// A [`selahcue_stt_cloud::transport::CloudSttSession`] shared between `run_cloud`'s
/// `on_clean_stop` and `on_fallback` closures, so WHICHEVER one actually fires can take sole
/// ownership and stop it. `CloudSttSession` is not `Clone` (deliberately: two handles to one
/// worker thread would double-join it), and exactly one of `run_cloud_stream_loop`'s three
/// exits ever runs — so a plain `move` into one closure would leave the OTHER with no way to
/// reach the session at all. `Option` because [`close_cloud_session`] takes it out; a second
/// call (there is at most one today, but the type does not rely on that) is then a no-op
/// rather than a double-stop.
#[cfg(feature = "cloud-stt")]
type SharedCloudSession = Arc<Mutex<Option<selahcue_stt_cloud::transport::CloudSttSession>>>;

/// Take the session out of `slot`, if still present, and stop it.
///
/// **Must run before `run_cloud`'s fallback continues into `run_on_device`.** `run_on_device`
/// blocks for the rest of the capture session (it returns only when the operator stops
/// listening), so anything that has not already severed the Deepgram connection by the time it
/// is called stays open behind that block — for hours, not moments.
///
/// This is the fix for a defect that shipped in this ticket's first remediation round: the old
/// `on_fallback` never touched `session` at all, so on a mid-service consent revocation (or a
/// terminal session failure) the authenticated WebSocket stayed open, `pump()` kept sending
/// `KeepAlive` frames and flushing residual ring content, and any socket drop reconnected and
/// re-presented the developer API key — directly contradicting
/// [`CONSENT_REVOKED_NOTICE`]'s own text. The equivalent gap on the CLEAN-STOP path was already
/// closed (that branch calls `session.stop()` itself); this closes it for every exit, through
/// one call site, so the fallback branch cannot regress back to silently skipping it (86akby7th
/// PR #22 remediation round 2, Cody High / Vera High).
///
/// `CloudSttSession::stop` is bounded by
/// [`selahcue_stt_cloud::transport::SHUTDOWN_GRACE`] and sends Deepgram the courtesy close, so
/// this cannot itself hang the capture worker thread — but it can still hang a THIRD locker of
/// `slot` behind it for that same bound, up to [`selahcue_stt_cloud::transport::SHUTDOWN_GRACE`]
/// (5 s), if `session.stop()` runs while the lock is still held. `slot.lock().take()` is taken
/// as its own statement, ending the borrow there, rather than as the scrutinee of the `if let`
/// (which would extend the guard's lifetime across the whole block) — so `stop()` below runs
/// with `slot` already unlocked (86akby7th PR #22 remediation round 2, Vera LOW). Harmless
/// today: only `run_cloud`'s two `FnOnce` closures ever call this, and exactly one of them runs
/// per session — but a future third locker (e.g. a UI force-disconnect command) would otherwise
/// block behind a lock this function no longer needs to hold.
#[cfg(feature = "cloud-stt")]
fn close_cloud_session(slot: &SharedCloudSession) {
    let session = slot.lock().unwrap_or_else(|e| e.into_inner()).take();
    if let Some(session) = session {
        session.stop();
    }
}

/// Context for a mid-service fallback into [`run_on_device`], carrying WHY the previous engine
/// stopped.
///
/// Applied only once on-device is confirmed to actually be producing (`run_on_device`'s success
/// path), never proactively before the attempt — so the console never shows a disclosure
/// claiming "coming from on-device instead" while on-device itself is still loading (a first-run
/// model download can take a while) or has failed to start (86akby7th PR #22 review, LOW: "the
/// fallback note/label should be set when the on-device engine actually produces, not before").
/// If on-device ALSO fails, `prior_failure` is folded into the on-device error instead, so the
/// operator learns both facts rather than only the newest one.
struct FallbackContext {
    /// What happened to the engine this session is falling back FROM — used only if on-device
    /// also fails to start.
    prior_failure: String,
    /// The disclosure to show once on-device is confirmed running.
    note: &'static str,
}

/// `run_on_device`'s failure branch, extracted so this exact wiring is what a test drives —
/// rather than a real `CpalSource` (a live microphone) or a loaded whisper model, neither of
/// which this failure path actually touches.
///
/// Folds in WHY a previous engine stopped, if `fallback` is `Some` (a mid-service handoff),
/// then tears the worker slot down FROM INSIDE ITSELF (Quinn, PR #22 review, "zombie worker"):
/// this may be a mid-service fallback (`run_on_device`'s `ready_tx: None` case) with no caller
/// left watching a result to notice the failure and call the real `stop()` — the two callers
/// that DO get an `Err` from `run_on_device` (`start_listening`, `perform_retry`) already call
/// `stop()` themselves, so clearing the slot here too is a harmless, idempotent no-op for them.
/// Calling the real `stop()` from here would deadlock: it joins the worker thread, and a thread
/// cannot join itself. This is that same cleanup minus the join, safe because this thread is
/// returning right after anyway — so `is_listening()` goes false and `detector_state` reports
/// `Unavailable` with the real error, instead of a worker slot that outlives the thread it names
/// and keeps reporting `Listening` forever. Returns the (possibly folded) message, so the caller
/// can also send it down `ready_tx` when one is waiting.
fn abandon_worker_after_on_device_failure(
    fallback: &Option<FallbackContext>,
    on_device_error: String,
) -> String {
    let message = match fallback {
        Some(fb) => format!(
            "{}; on-device fallback also failed: {on_device_error}",
            fb.prior_failure
        ),
        None => on_device_error,
    };
    record_failure(message.clone());
    *status_lock(&PROVIDER_LABEL) = None;
    *status_lock(&ENGINE_NOTE) = None;
    let _ = worker_lock().take();
    message
}

/// The retained terminal failure, if the detector is currently down.
pub fn last_failure() -> Option<String> {
    status_lock(&LAST_FAILURE).clone()
}

/// The running transcript provider's label (FR-120), or `None` when nothing is listening.
pub fn provider_label() -> Option<String> {
    status_lock(&PROVIDER_LABEL).clone()
}

/// Why the running engine differs from — or changed away from — what Settings says, or `None`
/// when there is nothing to explain. See [`ENGINE_NOTE`].
pub fn engine_note() -> Option<String> {
    status_lock(&ENGINE_NOTE).clone()
}

/// A loaded model context, cached across capture sessions so a stop→start reuses the resident
/// model instead of re-verifying (~1.6 GB SHA-256) and reloading it — the "one-time" cost the
/// operator expects. Bounded (FR-101): at most ONE entry (the current model path), and the model
/// already fits the ≤2 GB resident budget, so the cache never grows.
static MODEL_CACHE: Mutex<Option<(PathBuf, Arc<WhisperContext>)>> = Mutex::new(None);

fn model_cache_lock() -> std::sync::MutexGuard<'static, Option<(PathBuf, Arc<WhisperContext>)>> {
    MODEL_CACHE.lock().unwrap_or_else(|e| e.into_inner())
}

/// The resident context for `path`, if one is already loaded (reused across start/stop).
fn cached_context(path: &Path) -> Option<Arc<WhisperContext>> {
    let cache = model_cache_lock();
    cache
        .as_ref()
        .and_then(|(p, ctx)| (p == path).then(|| Arc::clone(ctx)))
}

/// Remember `ctx` as the resident model for `path` (replaces any prior entry — bounded to one).
fn cache_context(path: PathBuf, ctx: Arc<WhisperContext>) {
    *model_cache_lock() = Some((path, ctx));
}

/// Resolve the model (cache/download, integrity-verified) and load the recognizer. Runs on
/// the worker thread (it can be slow: a large SHA-256 + whisper.cpp load, or a first-run
/// download). An explicit `SELAHCUE_STT_MODEL` path overrides the download.
fn load_recognizer<R: tauri::Runtime>(app: &AppHandle<R>) -> Result<WhisperRecognizer, String> {
    let selection = HardwareProbe::detect().select_model();
    // Resolve the intended model path WITHOUT downloading or hashing yet, so a warm cache hit
    // (a prior start this session) skips fetch + verify + reload and reuses the resident context.
    // An explicit `SELAHCUE_STT_MODEL` overrides the download and must be integrity-gated here
    // (it is not fetch-verified); the download path is verified once by `fetch_model` itself.
    let (model_path, env_sha) = match std::env::var("SELAHCUE_STT_MODEL") {
        Ok(path) => {
            let sha = std::env::var("SELAHCUE_STT_MODEL_SHA256").map_err(|_| {
                "SELAHCUE_STT_MODEL is set — also set SELAHCUE_STT_MODEL_SHA256 (integrity gate, FR-156)"
                    .to_string()
            })?;
            (PathBuf::from(path), Some(sha))
        }
        Err(_) => {
            let asset = selection.model.asset();
            // `fetch_model` installs at exactly this path — compute it up front for the cache key.
            (
                selahcue_stt::default_cache_dir().join(asset.file_name),
                None,
            )
        }
    };

    // Reuse a resident model loaded earlier this session — no fetch, no SHA-256, no reload.
    if let Some(ctx) = cached_context(&model_path) {
        eprintln!("SelahCue STT: reusing the resident model ({model_path:?}).");
        return Ok(WhisperRecognizer::from_context(ctx, &selection));
    }

    // Cache miss (first start this session): ensure the file is present + integrity-verified
    // ONCE, load it, and cache the context for the next start.
    let recognizer = match env_sha {
        Some(sha) => WhisperRecognizer::load(&model_path, &sha, &selection)?,
        None => {
            let asset = selection.model.asset();
            let cache = selahcue_stt::default_cache_dir();
            eprintln!(
                "SelahCue STT: resolving model {} (~{} MB) in {}…",
                asset.file_name,
                asset.size_bytes / 1_000_000,
                cache.display()
            );
            // Fresh attempt: clear any cancel request left over from a previous download before we
            // start polling, so a stale `true` can't abort this one.
            DOWNLOAD_CANCEL.store(false, Ordering::SeqCst);
            let path = selahcue_stt::fetch_model_phased(
                &asset,
                &cache,
                |phase| {
                    // Drive the phase-aware modal (downloading/verifying/ready/failed) and the
                    // legacy byte-progress event. Advisory — send errors (no window yet) are
                    // ignored. On cancel the fetch emits Failed{…"cancelled"} through here so the
                    // modal can show a cancelled/dismissed state.
                    emit_phase(app, phase);
                },
                // Cooperative cancel: the fetch loop polls this once per chunk. Set by
                // `cancel_download()` (the modal's Cancel) or `stop()` (Stop listening).
                || DOWNLOAD_CANCEL.load(Ordering::SeqCst),
            )?;
            // `fetch_model` already SHA-256-verified the file (cache hit OR post-download), so we
            // load WITHOUT re-hashing the multi-hundred-MB/GB file — that redundant hash was the
            // slow wait before the mic opened.
            WhisperRecognizer::load_unverified(&path, &selection)?
        }
    };
    cache_context(model_path, recognizer.context());
    Ok(recognizer)
}

/// Emit a live mic-level reading (peak percent) so "waiting for speech…" can show whether
/// audio is actually arriving, regardless of which engine is consuming it. Generic over
/// [`CaptureSource`] (not just [`CpalSource`]) so `run_cloud_stream_loop` can call it — in
/// production always monomorphized to `CpalSource`, so this is not a behaviour change.
fn emit_level<S: CaptureSource, R: tauri::Runtime>(app: &AppHandle<R>, source: &mut S) {
    let pct = (source.peak_level() * 100.0).round().clamp(0.0, 100.0) as u8;
    let _ = app.emit(LEVEL_EVENT, MicLevel { pct });
}

/// Start live transcription into `app`'s controller (local or wire-connected host), routed
/// between Cloud (Deepgram) and on-device (Whisper) per `TranscriptionRoute::decide` — see the
/// module doc for the fallback rules. Returns a receiver that resolves once the worker has
/// opened the mic and either engine is ready (`Ok`) or setup failed (`Err`) — so the caller can
/// surface configuration / download / microphone failures without blocking, and without a
/// phantom "listening" state.
pub fn start(app: AppHandle) -> tokio::sync::oneshot::Receiver<Result<(), String>> {
    let (ready_tx, ready_rx) = tokio::sync::oneshot::channel::<Result<(), String>>();
    {
        let guard = worker_lock();
        if guard.is_some() {
            let _ = ready_tx.send(Ok(())); // already listening — idempotent
            return ready_rx;
        }
    }

    // The routing decision is made ONCE, here, from the config as it stands right now — not
    // re-evaluated for the life of the session (a mid-service Cloud *failure* is a separate,
    // runtime fallback; see `run_cloud`). `readiness()` reads real env + build cfg and is
    // always callable: `selahcue-stt-cloud` is an unconditional dependency, so this build can
    // always tell the console the truth about cloud transcription even when `cloud-stt` is off.
    let providers_snapshot = {
        let state = app.state::<crate::AppState>();
        let guard = state.providers.lock().unwrap_or_else(|e| e.into_inner());
        guard.clone()
    };
    let readiness = selahcue_stt_cloud::readiness::readiness();
    let route = TranscriptionRoute::decide(&providers_snapshot, readiness);
    // Honest from the first frame: if Cloud was selected but is not usable, say so before a
    // single sample is captured — never let the console imply cloud streaming that never
    // happened.
    *status_lock(&ENGINE_NOTE) = route.fallback_reason().map(|r| r.detail().to_string());

    // Recognised segments flow worker(sync) → drain task(async) → backend ingest. Bounded.
    let (seg_tx, mut seg_rx) = tokio::sync::mpsc::channel::<ProviderSegment>(SEGMENT_QUEUE);

    // Drain task on the Tauri runtime: ingest each segment through the backend's dual path
    // (local controller OR the wire to a connected output-window host). Ends when the worker
    // stops and drops `seg_tx`.
    let app_task = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(seg) = seg_rx.recv().await {
            let state = app_task.state::<crate::AppState>();
            let _ = state
                .backend
                .ingest_transcript(seg.text, seg.start_ms, seg.end_ms, seg.is_final)
                .await;
        }
    });

    let stop = Arc::new(AtomicBool::new(false));
    let stop_worker = Arc::clone(&stop);
    // A handle for the worker thread to emit first-run download progress to the webview.
    let app_worker = app.clone();
    let handle = std::thread::spawn(move || {
        // Slow, fallible setup on the worker thread (not the executor): open the mic before
        // EITHER engine, so the OS microphone-permission prompt appears immediately regardless
        // of route, and so a mid-service Cloud→on-device handoff reuses the same open stream
        // instead of re-prompting. The on-device capture ring is bounded (drops oldest), so
        // audio buffered while a model loads is safely discarded.
        let source = match CpalSource::new() {
            Ok(s) => s,
            Err(e) => {
                record_failure(format!("microphone unavailable: {e}"));
                let _ = ready_tx.send(Err(format!("microphone unavailable: {e}")));
                return;
            }
        };

        match route {
            TranscriptionRoute::Cloud => {
                #[cfg(feature = "cloud-stt")]
                {
                    // `providers_snapshot` (captured above for the route DECISION only) is
                    // deliberately NOT threaded through to `run_cloud`: it re-fetches the LIVE
                    // config itself (`live_providers_config`) at the moment it matters, rather
                    // than trusting a clone taken here that could already be stale by the time
                    // `CpalSource::new()` above returns (86akby7th PR #22 review, Cody High).
                    run_cloud(app_worker, source, stop_worker, seg_tx, ready_tx);
                }
                #[cfg(not(feature = "cloud-stt"))]
                {
                    // Unreachable in practice: `readiness()` can only report `Ready` — the one
                    // input that makes `decide()` return `Cloud` — when this build was compiled
                    // with `cloud-stt` (see its doc comment: the fact has a single origin, this
                    // crate's own `cfg!(feature = "deepgram")`). Kept as a safe, honest failure
                    // rather than `unreachable!()`, in case that invariant is ever loosened.
                    let _ = app_worker;
                    record_failure(
                        "internal error: routed to Cloud transcription in a build without \
                         cloud-stt"
                            .to_string(),
                    );
                    let _ = ready_tx.send(Err(
                        "cloud transcription is not available in this build".to_string(),
                    ));
                }
            }
            TranscriptionRoute::OnDevice { reason } => {
                if let Some(reason) = reason {
                    eprintln!(
                        "SelahCue STT: Cloud transcription selected but not available \
                         ({reason:?}); using on-device transcription instead."
                    );
                }
                run_on_device(
                    app_worker,
                    source,
                    stop_worker,
                    seg_tx,
                    Some(ready_tx),
                    None,
                );
            }
        }
    });

    *worker_lock() = Some(Worker {
        stop,
        handle: Some(handle),
    });
    ready_rx
}

/// Shown once the on-device capture hand-off has had to drop raw audio because the recognition
/// thread could not keep up. Distinct wording from Cloud's [`AUDIO_DROPPED_NOTICE`] (no
/// "connection" or "Deepgram" — nothing here has a socket to fall behind on; it is CPU decode
/// falling behind capture instead), same mechanism: [`should_note_audio_drop`] over
/// `AudioHandoff::dropped()`, the shared type both routes use (`capture_handoff.rs`).
const ON_DEVICE_AUDIO_DROPPED_NOTICE: &str = "On-device transcription is running, but audio is \
     being captured faster than it can be processed — some audio may not have reached the \
     transcript.";

/// Appended (via [`append_engine_note`], never overwriting a route note already there) when
/// this capture session's FIRST engine attempt — on-device chosen outright, or an immediate
/// pre-stream Cloud fallback — had to discard audio that piled up in `source` while
/// `load_recognizer` was loading or downloading the model. See [`flush_pending_backlog`].
///
/// **Deliberately NOT silence, and deliberately NOT sticky.** An earlier version of this fix
/// discarded this backlog with no operator-facing disclosure at all — reasoned as harmless
/// because the operator was already shown "Preparing on-device transcription…" for this exact
/// window. Cody's review (86akd1jcc, HIGH-1) is why that reasoning does not hold: the owner's
/// original complaint was that [`ON_DEVICE_AUDIO_DROPPED_NOTICE`] was WRONGLY WORDED (claiming
/// an ongoing rate problem that a one-time startup artifact does not support), not that a
/// notice existed at all — replacing "wrong notice" with "no notice" regresses the FR-120
/// honest-disclosure property this file otherwise keeps everywhere else. So this exists to
/// disclose the SAME fact accurately instead: audio was lost, once, during preparation — never
/// re-checked or re-fired afterward (unlike [`ON_DEVICE_AUDIO_DROPPED_NOTICE`]'s stickiness,
/// which exists for a different reason — a REPEATED, ongoing condition — see its own doc
/// comment; a one-time event does not need or want that behaviour).
///
/// Only ever appended when `run_on_device`'s `fallback` parameter is `None`. See
/// [`AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE`] for the mid-service case, which needs different
/// wording because the operator's on-screen state at that moment is different (a transcript
/// already appears to be live, not "Preparing…").
///
/// **Wording constraint (coordinator, 86akd1jcc remediation): state only what is true, nothing
/// more.** The bug this whole fix responds to was the app telling the operator something
/// UNTRUE about their own service (a claimed ongoing rate problem that was really a one-time
/// artifact) — replacing that with a different, quieter untruth, or with a plausible-sounding
/// mechanism this code does not actually know, would not fix the underlying problem, only move
/// it. So this states exactly two facts and nothing else: the microphone was live during
/// preparation, and audio from that window is not in the transcript. No claim about WHY
/// (loading, downloading, hashing — the operator does not need the mechanism to act on this),
/// and no claim about how much.
const AUDIO_LOST_DURING_STARTUP_NOTICE: &str =
    "Audio captured while on-device transcription was preparing was not transcribed.";

/// Appended (via [`append_engine_note`], never erasing the engine-change disclosure it
/// accompanies) when a MID-SERVICE fallback into on-device (`run_on_device`'s `fallback:
/// Some(_)` case — a running Cloud session failed, or consent was revoked, while audio kept
/// arriving) also had to discard audio that accumulated while the new engine's model was
/// loading. See [`flush_pending_backlog`].
///
/// Distinct wording from [`AUDIO_LOST_DURING_STARTUP_NOTICE`] on purpose (Sana, 86akd1jcc
/// review M-1): unlike the startup case, this audio was part of an ALREADY-FLOWING transcript
/// the operator believes is live — the console keeps reading "Listening — transcribing"
/// throughout a fallback, it never shows a "Preparing…" state for it — so the disclosure names
/// the engine switch specifically rather than reusing startup language that would not match
/// what the operator was actually seeing at the time.
///
/// Only ever appended when `fallback` is `Some(_)` — never on the first two call sites (see
/// [`AUDIO_LOST_DURING_STARTUP_NOTICE`]).
const AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE: &str =
    "Audio captured while transcription was switching engines was not transcribed.";

/// Discard whatever `source` has already buffered, returning the number of samples thrown away.
///
/// **Why this exists (owner report, 2026-09-05): the sticky drop notice was firing from a
/// one-time startup artifact, not a real processing shortfall.** `load_recognizer` can take
/// anywhere from ~5s (a warm disk cache still pays a SHA-256 verify + whisper.cpp load — see
/// 86akcfpcc) to over a minute (a first-run ~1.6 GB download) before returning, and for that
/// whole window nothing calls [`AudioSource::next_chunk`] — the mic keeps capturing regardless
/// (via `CpalSource`'s own internal ring, `PcmRing`), but into a buffer this module cannot see
/// or count, because [`AudioHandoff`] does not exist yet. The FIRST call to `next_chunk` once
/// `load_recognizer` returns hands back that WHOLE backlog in one [`AudioChunk`] (`CpalSource`
/// always drains its ring to completion); pushed into a brand-new, empty hand-off it is
/// retained WHOLE (see `capture_handoff.rs`'s `retained_samples` doc comment), and then the
/// very NEXT ordinary live chunk evicts it entirely in one shot — before the recognition
/// thread has had any chance to decode a single frame. `should_note_audio_drop` cannot tell
/// that apart from a genuine, ongoing "capture is outpacing decode" — it just sees a nonzero
/// drop count — so the operator was shown a claim about ONGOING throughput
/// ([`ON_DEVICE_AUDIO_DROPPED_NOTICE`]) that this one-time, pre-ready backlog does not support,
/// and the notice's own deliberate stickiness (a real design choice, not a bug — see its doc
/// comment) then carried that false impression for the rest of the session.
///
/// The fix is to never let that backlog reach the hand-off at all — the discarded count is
/// disclosed instead through [`AUDIO_LOST_DURING_STARTUP_NOTICE`] or
/// [`AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE`] (see `run_on_device`), not silence: an earlier
/// version of this fix discarded with no disclosure at all, which Cody's review (86akd1jcc,
/// HIGH-1) correctly rejected — see [`AUDIO_LOST_DURING_STARTUP_NOTICE`]'s doc comment for why.
///
/// **Ordering guarantee, exact (Cody, 86akd1jcc review, item 3 — a prior version of this
/// comment overstated it):** this is called as the FIRST thing `run_on_device` does after
/// `load_recognizer` returns `Ok` — strictly before the ready signal is sent, before
/// `SttEngine::build`, before `AudioHandoff::new`. Placing it before the ready signal
/// specifically (rather than merely before the hand-off, which an earlier version of this
/// comment implied was already the whole guarantee) closes a real gap Cody and Sana both found
/// independently (Cody's Q1/Q2, Sana's L-1): with the flush AFTER the ready send, anything
/// captured in the few, cheap, synchronous instructions between "ready" being signalled and the
/// flush actually running — `SttEngine::build`, a couple of mutex-guarded assignments — could
/// be swept into the discard despite being, technically, "audio captured after readiness". That
/// window was always sub-millisecond in practice (no I/O, no lock held across it), but it was
/// real, not hypothetical, and closing it costs nothing: nothing between `load_recognizer`
/// returning and this call needs to run first.
///
/// **Termination premise (Cody, 86akd1jcc review, item 4):** the loop below assumes
/// `source.next_chunk()` eventually returns `None`. That holds for every `CaptureSource` this
/// crate actually constructs — `CpalSource` is bounded by real hardware capture (a finite
/// callback rate), `FakeAudioSource` by a finite pre-loaded queue — but it is not guaranteed by
/// the [`AudioSource`] trait's contract itself. A hypothetical implementation that always
/// returns `Some` would make this loop spin forever. Unlike the arithmetic constants elsewhere
/// in this file, that is not something a `const _: () = assert!(…)` can pin at compile time —
/// it is a runtime behavioural property of the implementation, not a checkable value — so it is
/// stated here, in prose, instead: if you add a `CaptureSource` whose `next_chunk` can be
/// permanently, unboundedly `Some`, this function is not safe to call on it.
fn flush_pending_backlog<S: CaptureSource>(source: &mut S) -> usize {
    let mut discarded = 0usize;
    // See this function's doc comment: relies on `next_chunk` eventually returning `None`.
    while let Some(chunk) = source.next_chunk() {
        discarded += chunk.samples.len();
    }
    discarded
}

/// Run on-device (Whisper) transcription until stopped. The single on-device path: the initial
/// choice when on-device was actually selected, the immediate fallback when Cloud was selected
/// but is not usable, AND the mid-service fallback when a running Cloud session fails — all
/// three call this same function rather than three separate copies of it.
///
/// `ready_tx` is `Some` and consumed exactly once when this is the FIRST engine this capture
/// session tries (on-device chosen outright, or an immediate pre-stream Cloud fallback);
/// `None` when this is a mid-service handoff from an already-`Ok`-acknowledged Cloud session
/// (the caller already resolved the oneshot channel, which can only be sent once).
///
/// `fallback` carries WHY a previous engine stopped, when this is that kind of handoff — `None`
/// for the two call sites where on-device is the FIRST thing this session tries (nothing to
/// explain). See [`FallbackContext`]: its `note` is applied only in the success branch below,
/// never before, and its `prior_failure` is folded into the error only if on-device ALSO fails.
///
/// Before anything else — including before the ready signal is sent — [`flush_pending_backlog`]
/// discards whatever `source` accumulated while `load_recognizer` was blocked, and the count is
/// disclosed once (never silently, never stickily) as [`AUDIO_LOST_DURING_STARTUP_NOTICE`] or
/// [`AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE`] depending on whether `fallback` is `None` — see
/// `flush_pending_backlog`'s doc comment for the full reasoning.
fn run_on_device<S: CaptureSource, R: tauri::Runtime>(
    app_worker: AppHandle<R>,
    mut source: S,
    stop_worker: Arc<AtomicBool>,
    seg_tx: tokio::sync::mpsc::Sender<ProviderSegment>,
    ready_tx: Option<tokio::sync::oneshot::Sender<Result<(), String>>>,
    fallback: Option<FallbackContext>,
) {
    let recognizer = match load_recognizer(&app_worker) {
        Ok(r) => r,
        Err(e) => {
            let message = abandon_worker_after_on_device_failure(&fallback, e);
            if let Some(tx) = ready_tx {
                let _ = tx.send(Err(message));
            }
            return;
        }
    };

    // FIRST thing after a successful load — strictly before the ready signal below. See
    // `flush_pending_backlog`'s "Ordering guarantee" doc comment for exactly why this position
    // (not merely "before the hand-off") is the actual fix, not just a nearby one.
    let flushed = flush_pending_backlog(&mut source);
    if flushed > 0 {
        eprintln!(
            "SelahCue STT: discarded {flushed} samples captured before the on-device engine \
             started consuming (model load/download) — not counted as a drop; see the engine \
             note for the operator-facing disclosure."
        );
    }

    eprintln!(
        "SelahCue STT: capturing from {} — listening on-device.",
        source.label()
    );
    // Capture is live: supersede any earlier failure verdict.
    clear_failure();
    if let Some(tx) = ready_tx {
        let _ = tx.send(Ok(()));
    }

    let (mut engine, mut provider) = SttEngine::build(
        // Stream interims (~0.8 s cadence) so recognised words appear live; bound each interim
        // to a sliding window so its cost stays fixed as the utterance grows (the final on
        // close still decodes the whole utterance). Interims run on the recognition thread.
        EngineConfig {
            interim_interval_frames: 40,
            interim_max_samples: INTERIM_WINDOW_SAMPLES,
            ..EngineConfig::default()
        },
        Box::new(EnergyVad::new()),
        Box::new(recognizer),
        FeedbackGuard::new(),
    );
    // FR-120 honest disclosure: retain WHICH engine is producing this transcript, so the
    // console can name it instead of implying a perfect, anonymous recogniser.
    *status_lock(&PROVIDER_LABEL) = Some(provider.label().to_string());
    // Apply the deferred fallback disclosure now that on-device is CONFIRMED producing — never
    // before (see the doc comment above and `FallbackContext`) — and, on that same branch,
    // disclose a startup backlog that was discarded above using the wording appropriate to
    // WHICH kind of call this is (86akd1jcc review, Cody HIGH-1 / Sana M-1 & L-2: silence was
    // rejected, and the two cases need different wording — see the two notice constants' doc
    // comments for why). `append_engine_note` never clobbers, so an engine-change note and an
    // audio-loss note can both be true about the same session.
    match &fallback {
        Some(fb) => {
            append_engine_note(fb.note);
            if flushed > 0 {
                append_engine_note(AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE);
            }
        }
        None => {
            if flushed > 0 {
                append_engine_note(AUDIO_LOST_DURING_STARTUP_NOTICE);
            }
        }
    }

    // Decouple recognition from capture so a (potentially slow) decode never freezes the mic
    // or the level meter. The cpal stream is `!Send`, so the SOURCE stays on THIS thread and a
    // separate RECOGNITION thread owns the engine, fed by a bounded drop-oldest hand-off.
    let handoff = Arc::new(AudioHandoff::new(HANDOFF_MAX_SAMPLES));
    let recog_handoff = Arc::clone(&handoff);
    let recog_stop = Arc::clone(&stop_worker);
    let recog = std::thread::spawn(move || {
        // Recognition loop: transcribe buffered audio → segments → ingest. A long decode here
        // never stalls capture. When stopping, drain the tail then flush the open utterance.
        loop {
            for chunk in recog_handoff.drain() {
                engine.process(&chunk);
            }
            pump(&mut provider, |seg| {
                let _ = seg_tx.try_send(seg); // bounded; drop under backpressure, never block
            });
            if recog_stop.load(Ordering::Relaxed) && recog_handoff.is_empty() {
                break;
            }
            std::thread::sleep(RECOG_INTERVAL);
        }
        engine.flush();
        pump(&mut provider, |seg| {
            let _ = seg_tx.try_send(seg);
        });
        // `seg_tx` drops here → the drain task ends.
    });

    // Source loop (this thread): drain the mic ring into the hand-off + emit the live level.
    // It never touches the recognizer, so the meter + capture stay real time during a decode.
    // `audio_dropped_ever`: same sticky-notice pattern `run_cloud` uses over the same
    // `AudioHandoff` type — see `should_note_audio_drop` and `ON_DEVICE_AUDIO_DROPPED_NOTICE`.
    let mut audio_dropped_ever = false;
    while !stop_worker.load(Ordering::Relaxed) {
        while let Some(chunk) = source.next_chunk() {
            handoff.push(chunk);
        }
        emit_level(&app_worker, &mut source);
        if should_note_audio_drop(handoff.dropped(), audio_dropped_ever) {
            audio_dropped_ever = true;
            eprintln!(
                "SelahCue STT: the on-device capture hand-off dropped {} samples ({} currently \
                 retained) — recognition is not keeping up with capture.",
                handoff.dropped(),
                handoff.retained_samples()
            );
            append_engine_note(ON_DEVICE_AUDIO_DROPPED_NOTICE);
        }
        std::thread::sleep(CAPTURE_INTERVAL);
    }
    // Stop requested: let the recognition thread drain the tail + flush, then join it. The mic
    // stream (`source`) is dropped when this thread returns, stopping capture.
    let _ = recog.join();
}

/// The retention window this route's capture hand-off is sized to — the same 5 seconds
/// [`HANDOFF_MAX_SAMPLES`]'s literal means for on-device, but derived through
/// [`selahcue_core::audio_capacity::handoff_capacity`] against THIS device's real
/// configuration rather than baked into a fixed sample count. `HANDOFF_MAX_SAMPLES` itself is
/// not switched to consume this constant here — that literal's value is a separate, known
/// issue (see its own doc comment) that this ticket does not touch.
#[cfg(feature = "cloud-stt")]
const CAPTURE_WINDOW: Duration = Duration::from_secs(5);

/// Shown once EITHER of this session's bounded buffers has had to drop captured audio because a
/// downstream consumer could not keep up — the shared capture→consumer `AudioHandoff` (the same
/// type and drop counter the on-device route uses), or the Deepgram-specific `AudioRing` further
/// downstream (network egress; no on-device equivalent, since on-device has no socket to back up
/// against). Both are honest capacity management, not bugs, but both are SILENT ones otherwise:
/// a healthy-looking `SessionState::Streaming` does not by itself say whether every captured
/// sample reached the service. Named separately from
/// [`selahcue_stt_cloud::DEGRADED_FALLBACK_NOTICE`] because the two are different claims: that
/// one says the engine changed; this one says the still-running Cloud engine's transcript may
/// have a gap.
#[cfg(feature = "cloud-stt")]
const AUDIO_DROPPED_NOTICE: &str = "Cloud transcription is running, but the connection is \
     falling behind — some audio may not have reached the transcript.";

/// Shown when a running Cloud session is torn down because consent was revoked, or Cloud mode
/// was left, WHILE it was actively streaming — distinct from [`selahcue_stt_cloud::DEGRADED_FALLBACK_NOTICE`]
/// (that one means the session itself gave up; this one means the operator withdrew permission
/// for it to keep running). Both land the operator in the same place — on-device, with an
/// honest reason — but conflating "it broke" with "you turned it off" would misreport an
/// intentional privacy action as a fault (86akby7th PR #22 review, Sana High / Cody High).
#[cfg(feature = "cloud-stt")]
const CONSENT_REVOKED_NOTICE: &str = "Cloud transcription was turned off (consent revoked, or \
     On-device was selected) while a session was active. The transcript below is coming from \
     the on-device engine instead.";

/// The `CloudSttSession`'s wire configuration — real Deepgram in production, and in a TEST
/// build only, an optional override so a test can point `run_cloud` at a local stub instead
/// (`SELAHCUE_STT_CLOUD_TEST_ENDPOINT`, e.g. `ws://127.0.0.1:PORT/v1/listen`).
///
/// This is a **compiled-away** seam, not a runtime branch: the `#[cfg(test)]` / `#[cfg(not(test))]`
/// pair below means a release binary contains only the second definition and never reads this
/// (or any) environment variable to decide where Deepgram audio goes — an always-on override
/// would be a way to redirect a church's audio to an attacker-controlled endpoint via the
/// process environment, which this codebase's existing endpoint-confidentiality checks
/// (`DeepgramEndpoint::is_confidential`, `RequestSpec::build`'s loopback-only cleartext rule)
/// are precisely trying to close off. Exists so `run_cloud`'s own composition — not just the
/// generic, closure-driven `run_cloud_stream_loop` — can be driven end to end in a test against
/// a real `CloudSttSession` and a local stub server (86akby7th PR #22 remediation round 2,
/// Sana: "the composition is untested, not untestable").
#[cfg(all(feature = "cloud-stt", not(test)))]
fn cloud_session_config() -> selahcue_stt_cloud::transport::SessionConfig {
    selahcue_stt_cloud::transport::SessionConfig::default()
}

#[cfg(all(feature = "cloud-stt", test))]
fn cloud_session_config() -> selahcue_stt_cloud::transport::SessionConfig {
    use selahcue_stt_cloud::transport::SessionConfig;
    match std::env::var("SELAHCUE_STT_CLOUD_TEST_ENDPOINT") {
        Ok(url) => SessionConfig {
            endpoint: selahcue_stt_cloud::DeepgramEndpoint::custom(url),
            ..SessionConfig::default()
        },
        Err(_) => SessionConfig::default(),
    }
}

/// Run Cloud (Deepgram) transcription until it fails, is stopped, or the running session is
/// terminal, falling back to `run_on_device` in every case that is not a clean operator-driven
/// stop. Behind `cloud-stt`: everything it touches from `selahcue-stt-cloud` beyond `readiness`
/// requires the `deepgram` feature.
///
/// This function never blocks the caller waiting on the network: `CloudSttSession::start`
/// returns before the socket is open (it runs on its own thread), and every iteration of
/// [`run_cloud_stream_loop`]'s loop is bounded local work — draining the mic, pushing into the
/// bounded `AudioRing`, draining the bounded `SegmentQueue`, and one non-blocking status read.
#[cfg(feature = "cloud-stt")]
fn run_cloud<S: CloudCaptureSource, R: tauri::Runtime>(
    app_worker: AppHandle<R>,
    source: S,
    stop_worker: Arc<AtomicBool>,
    seg_tx: tokio::sync::mpsc::Sender<ProviderSegment>,
    ready_tx: tokio::sync::oneshot::Sender<Result<(), String>>,
) {
    use selahcue_stt_cloud::session::{StreamAuthorization, StreamParams};
    use selahcue_stt_cloud::transport::CloudSttSession;
    use selahcue_stt_cloud::{
        developer_credential_from_env, AudioRing, CloudTranscriptProvider, SegmentQueue,
        SessionStatus,
    };

    // Size the shared capture hand-off from THIS device's real configuration — never a literal
    // (see `capture_handoff.rs` / `selahcue_core::audio_capacity`). `None` means the device
    // reported something this app cannot safely turn into a retention window (zero channels,
    // zero sample rate, or an unrepresentable product): a capture session started anyway could
    // only ever silently mis-size its buffer, so this refuses to start at all and says why —
    // the same "surface a device-configuration error rather than start a capture that can only
    // fail" decision applies whichever engine was about to run, but Cloud reaches it first here
    // because on-device's own call site is a separate, already-in-flight change.
    let handoff_capacity = match selahcue_core::audio_capacity::handoff_capacity(
        source.sample_rate(),
        source.channels(),
        CAPTURE_WINDOW,
    ) {
        Some(cap) => cap,
        None => {
            let msg = format!(
                "microphone reported an unusable configuration (sample_rate={}, channels={}); \
                 cannot size the capture buffer safely",
                source.sample_rate(),
                source.channels()
            );
            record_failure(msg.clone());
            let _ = ready_tx.send(Err(msg));
            return;
        }
    };
    let handoff = AudioHandoff::new(handoff_capacity);

    // Re-fetch the LIVE config right here, rather than trusting `start()`'s snapshot from a
    // moment ago (86akby7th PR #22 review, Cody High). `TranscriptionRoute::decide` already
    // checked `may_stream_cloud_audio()` once, but `CpalSource::new()` above can block for as
    // long as the OS mic-permission dialog is up — the operator can revoke consent or leave
    // Cloud mode during that wait, and a frozen snapshot cannot see it. Re-proving eligibility
    // at the point audio would actually stream, against the config as it stands NOW, is what
    // makes "streaming is unreachable without consent" hold at the point that matters (mirrors
    // `selahcue-stt-cloud`'s own `StreamAuthorization` invariant).
    let authorization = match StreamAuthorization::from_config(&live_providers_config(&app_worker))
    {
        Ok(a) => a,
        Err(e) => {
            record_failure(format!("cloud transcription not authorized: {e}"));
            run_on_device(
                app_worker,
                source,
                stop_worker,
                seg_tx,
                Some(ready_tx),
                None,
            );
            return;
        }
    };
    let credential = match developer_credential_from_env() {
        Ok(c) => c,
        Err(e) => {
            record_failure(format!("cloud transcription credential unavailable: {e}"));
            run_on_device(
                app_worker,
                source,
                stop_worker,
                seg_tx,
                Some(ready_tx),
                None,
            );
            return;
        }
    };

    let params = StreamParams::default();
    let audio_ring = AudioRing::new();
    let queue = SegmentQueue::new();
    let status = SessionStatus::new();
    // `SessionConfig::default()` is the crate's own validated baseline (it is a compile-time-
    // pinned invariant of that crate that its defaults satisfy `SessionConfig::validate`) —
    // built through the validated path rather than hand-rolled, per the review note that this
    // guard is what stands between this branch and an unbounded reconnect loop (V-2). See
    // `cloud_session_config` for why a TEST build can reach a different endpoint here.
    let config = cloud_session_config();

    let session = match CloudSttSession::start(
        &authorization,
        credential,
        config,
        audio_ring.clone(),
        queue.clone(),
        status.clone(),
    ) {
        Ok(s) => s,
        Err(e) => {
            record_failure(format!("cloud transcription failed to start: {e}"));
            run_on_device(
                app_worker,
                source,
                stop_worker,
                seg_tx,
                Some(ready_tx),
                None,
            );
            return;
        }
    };

    let provider = CloudTranscriptProvider::new(queue.clone(), &params);
    // FR-120 honest disclosure: name Deepgram specifically, distinguishable from the on-device
    // label, so a fallback later is visibly a DIFFERENT engine, not the same string re-shown.
    *status_lock(&PROVIDER_LABEL) = Some(provider.label().to_string());
    clear_failure();
    *status_lock(&ENGINE_NOTE) = None; // streaming normally — nothing to explain (yet)
    let _ = ready_tx.send(Ok(()));
    eprintln!(
        "SelahCue STT: capturing from {} — streaming to Deepgram.",
        source.label()
    );

    // Shared between BOTH exits below so whichever one fires can stop the session — see
    // `SharedCloudSession` / `close_cloud_session`. Neither closure may simply `move session`
    // into itself: only one of them ever runs, and the other would then have no way to reach it
    // at all (exactly the shape of the bug this replaces).
    let session_slot: SharedCloudSession = Arc::new(Mutex::new(Some(session)));
    let session_for_clean_stop = Arc::clone(&session_slot);
    let session_for_fallback = Arc::clone(&session_slot);

    // The loop itself is a separate, generic function (`run_cloud_stream_loop`) so it is
    // exercised in tests against a fake capture source and injected fallback/consent-check
    // closures — no real microphone, network, or whisper model — rather than only by 104 tests
    // that never touch this code path at all (Quinn, PR #22 review: deleting the terminal-
    // handoff block here previously left the whole suite green).
    let app_for_level = app_worker.clone();
    let app_for_check = app_worker.clone();
    run_cloud_stream_loop(
        source,
        stop_worker,
        seg_tx,
        &handoff,
        &audio_ring,
        provider,
        &status,
        move |s: &mut S| emit_level(&app_for_level, s),
        // Polled every iteration (86akby7th PR #22 review, Sana High): a mid-service consent
        // revocation or a move away from Cloud mode must terminate cloud egress within one
        // `CAPTURE_INTERVAL`, not only be noticed the next time "Start listening" is pressed.
        move || live_providers_config(&app_for_check).may_stream_cloud_audio(),
        move || {
            // Clean operator-driven stop. `stop()` asks Deepgram to flush first (bounded —
            // `SHUTDOWN_GRACE`) so the last sentence of a sermon is not lost.
            close_cloud_session(&session_for_clean_stop);
        },
        move |source, stop_worker, seg_tx, prior_failure, note| {
            // Sever the Deepgram connection BEFORE falling back. `run_on_device` below blocks
            // for the rest of the capture session — anything not already stopped by the time it
            // is called would stay open behind that block, reconnecting and re-presenting the
            // developer credential for as long as capture runs (86akby7th PR #22 remediation
            // round 2, Cody High / Vera High: the previous `on_fallback` never touched `session`
            // at all). See `close_cloud_session`.
            close_cloud_session(&session_for_fallback);
            run_on_device(
                app_worker,
                source,
                stop_worker,
                seg_tx,
                None,
                Some(FallbackContext {
                    prior_failure,
                    note,
                }),
            );
        },
    );
}

/// The Cloud streaming loop itself: drains the mic, forwards audio to Deepgram, drains
/// recognised segments, and watches two independent reasons to hand off to on-device — until
/// told to stop cleanly.
///
/// Generic over [`CaptureSource`] and takes its side effects (`emit_level`, the live consent
/// re-check, the clean-stop action, and the fallback handoff itself) as injected closures
/// rather than calling `run_on_device`/`AppHandle::emit` directly, so this exact function — not
/// a copy of its logic — is what a test drives with a `SessionStatus` set to terminal or a
/// consent check that flips to `false`, with no real microphone, network socket, or whisper
/// model anywhere nearby. Production (`run_cloud`, above) wires the closures to the real thing;
/// removing or mis-wiring either exit path is a test failure here, not a silent no-op the way
/// deleting the equivalent inline `if` block used to be (Quinn, PR #22 review).
///
/// Returns when `stop_worker` is set (`on_clean_stop` runs, no fallback), when `may_stream_now`
/// reports the operator withdrew permission (`on_fallback` runs with [`CONSENT_REVOKED_NOTICE`]),
/// or when `status` goes terminal (`on_fallback` runs with
/// [`selahcue_stt_cloud::DEGRADED_FALLBACK_NOTICE`]) — never loops forever once any of the three
/// fires.
#[cfg(feature = "cloud-stt")]
#[allow(clippy::too_many_arguments)]
fn run_cloud_stream_loop<S: CaptureSource>(
    mut source: S,
    stop_worker: Arc<AtomicBool>,
    seg_tx: tokio::sync::mpsc::Sender<ProviderSegment>,
    handoff: &AudioHandoff,
    audio_ring: &selahcue_stt_cloud::AudioRing,
    mut provider: selahcue_stt_cloud::CloudTranscriptProvider,
    status: &selahcue_stt_cloud::SessionStatus,
    mut emit_level_cb: impl FnMut(&mut S),
    mut may_stream_now: impl FnMut() -> bool,
    on_clean_stop: impl FnOnce(),
    on_fallback: impl FnOnce(
        S,
        Arc<AtomicBool>,
        tokio::sync::mpsc::Sender<ProviderSegment>,
        String,
        &'static str,
    ),
) {
    use selahcue_stt_cloud::{AudioChunk as CloudAudioChunk, DEGRADED_FALLBACK_NOTICE};

    // Both `handoff` (shared capture→consumer type; drops the OLDEST raw audio if this loop
    // ever fell behind draining the mic — it does not in practice, since nothing here blocks)
    // and `audio_ring` (Deepgram-specific, downstream of resampling; drops OLDEST if the socket
    // falls behind, and REFUSES a single chunk larger than its own per-chunk cap) have their own
    // capacity bound. All three are honest capacity management, not bugs, but all three are
    // SILENT ones otherwise — tracked so the console can say so rather than presenting a
    // transcript that looks complete while it is not (the same honesty rule this ticket already
    // applies to which engine is running). Sticky for the rest of THIS session once true — a
    // flicker back to "no drops yet" the moment a buffer catches up would be easy to miss and
    // would read as reassurance about audio already lost.
    let mut audio_dropped_ever = false;

    loop {
        if stop_worker.load(Ordering::Relaxed) {
            on_clean_stop();
            return;
        }

        // Checked BEFORE this iteration touches the egress ring (86akby7th PR #22 remediation
        // round 2, Sana LOW). Checking it after the mic-drain/push below (the original order)
        // meant a revoked-consent iteration still forwarded one further `CAPTURE_INTERVAL` of
        // audio to Deepgram before the loop noticed — a small but real leak past the point
        // consent was withdrawn. The mic ring is not lost by skipping this: the samples simply
        // stay in `source`/the hand-off for whoever runs next (on-device, via the same open
        // mic), rather than being pushed to the ring this route is about to stop feeding.
        if !may_stream_now() {
            // The operator withdrew permission (revoked consent, or left Cloud mode) WHILE this
            // session was actively streaming. Distinct from the terminal branch below: nothing
            // here failed.
            on_fallback(
                source,
                stop_worker,
                seg_tx,
                "cloud transcription consent was revoked, or Cloud mode was left, mid-service"
                    .to_string(),
                CONSENT_REVOKED_NOTICE,
            );
            return;
        }

        // Drain the mic into the SHARED hand-off (same type, same sizing rule, same drop
        // counter the on-device route uses — see `capture_handoff.rs`), then drain the
        // hand-off and resample each chunk to what Deepgram was told to expect (16 kHz mono,
        // matching `selahcue-stt`'s own target rate — "one capture pipeline feeds either
        // engine") before offering it to the Deepgram-specific `AudioRing` the session's own
        // thread drains. Neither `push` blocks beyond its own lock, so this loop is never held
        // up by the network.
        while let Some(chunk) = source.next_chunk() {
            handoff.push(chunk);
        }
        for chunk in handoff.drain() {
            let mono = selahcue_stt::resample_to_16k_mono(
                &chunk.samples,
                chunk.sample_rate,
                chunk.channels,
            );
            audio_ring.push(CloudAudioChunk::from_pcm_i16(&pcm_i16_from_f32(&mono)));
        }
        emit_level_cb(&mut source);

        // `refused_oversize()` is now part of the sum (86akby7th PR #22 review, Vera Medium): a
        // stall long enough to make the whole backlog one oversized chunk is refused whole by
        // `AudioRing::push`, counted ONLY here — omitting it let a 30 s backlog vanish with the
        // drop notice never firing, because `dropped_for_bound()` alone stayed at zero.
        if should_note_audio_drop(
            handoff.dropped() + audio_ring.dropped_for_bound() + audio_ring.refused_oversize(),
            audio_dropped_ever,
        ) {
            audio_dropped_ever = true;
            eprintln!(
                "SelahCue STT: audio was dropped before reaching Deepgram (capture hand-off: {} \
                 samples dropped, {} currently retained; Deepgram ring: {} chunks dropped, {} \
                 chunks refused oversize) — the pipeline is not keeping up.",
                handoff.dropped(),
                handoff.retained_samples(),
                audio_ring.dropped_for_bound(),
                audio_ring.refused_oversize()
            );
            // Append, never overwrite (86akby7th PR #22 review, LOW): a consent-revoked or
            // degraded-fallback disclosure may already be in this slot from an EARLIER iteration
            // of this same loop, and a drop notice must not silently erase it.
            append_engine_note(AUDIO_DROPPED_NOTICE);
        }

        // Drain whatever the socket has queued so far — never blocks (see `CloudTranscriptProvider::poll`).
        pump(&mut provider, |seg| {
            let _ = seg_tx.try_send(seg);
        });

        if status.get().is_terminal() {
            // The session gave up (bad credential, exhausted retries, or a defect) rather than
            // being asked to stop, and the operator did not withdraw permission — hand off to
            // on-device with the SAME open mic (no re-prompt, no gap while a new stream opens).
            let terminal_status = status.get();
            on_fallback(
                source,
                stop_worker,
                seg_tx,
                format!("cloud transcription stopped: {terminal_status:?}"),
                DEGRADED_FALLBACK_NOTICE,
            );
            return;
        }

        std::thread::sleep(CAPTURE_INTERVAL);
    }
}

/// Convert resampled `f32` samples in `[-1.0, 1.0]` to signed 16-bit PCM, the encoding Deepgram
/// is told to expect ([`selahcue_stt_cloud::session::Encoding::Linear16`]). Out-of-range input
/// (should not occur post-resample, but a capture glitch is not impossible) is clamped rather
/// than wrapped, so a bad sample is a loud click, never noise that reads as speech.
#[cfg(feature = "cloud-stt")]
fn pcm_i16_from_f32(samples: &[f32]) -> Vec<i16> {
    samples
        .iter()
        .map(|s| (s.clamp(-1.0, 1.0) * i16::MAX as f32).round() as i16)
        .collect()
}

/// Whether observing a dropped-sample/byte count should (re)set the sticky "some audio was
/// dropped" notice — shared by both routes (86akby7th: "one shared counter, not one per
/// route"). Pure and extracted so the decision is unit-testable without a real buffer or a
/// thread. Sticky: once `already_noted`, stays `false` here (nothing to re-set) for the rest of
/// the session — a persistent notice beats a flickering one that could read as reassurance
/// about audio already lost.
fn should_note_audio_drop(dropped_count: u64, already_noted: bool) -> bool {
    !already_noted && dropped_count > 0
}

/// Request cancellation of an in-flight first-run model download (idempotent; safe when nothing is
/// downloading). Sets the process-wide [`DOWNLOAD_CANCEL`] flag; the fetch loop polls it once per
/// chunk, removes its partial `.part` file, and reports a terminal `Failed{…"cancelled"}` phase on
/// `stt://phase` — which lets the "Offline Download Modal" show a cancelled/dismissed state. It does
/// NOT take the worker lock (no deadlock against the worker thread), and if no download is running
/// it is a harmless no-op: the flag is reset at the start of the next download before any polling.
/// Exposed so `main.rs` can register a Tauri command that the modal's Cancel button invokes.
pub fn cancel_download() {
    DOWNLOAD_CANCEL.store(true, Ordering::SeqCst);
}

/// Stop the capture worker (idempotent). Takes the worker out of the slot BEFORE joining, so
/// the worker lock is never held across the join; the worker thread only touches the segment
/// channel and the controller, never this slot — no lock-ordering cycle. Joining the worker
/// drops its `seg_tx`, which ends the drain task.
pub fn stop() {
    // Also abort any in-flight first-run download: during the download the worker is parked inside
    // `load_recognizer`, not yet in the capture loop, so `w.stop` alone would leave `join()` waiting
    // for the whole (~1.6 GB) transfer. Cancelling makes the fetch return promptly so stop is snappy.
    DOWNLOAD_CANCEL.store(true, Ordering::SeqCst);
    // Nothing is producing a transcript once the worker is gone — do not keep naming an
    // engine that is no longer running, or explaining a routing decision that no longer applies.
    *status_lock(&PROVIDER_LABEL) = None;
    *status_lock(&ENGINE_NOTE) = None;
    let worker = worker_lock().take();
    if let Some(mut w) = worker {
        w.stop.store(true, Ordering::Relaxed);
        if let Some(handle) = w.handle.take() {
            let _ = handle.join();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use selahcue_stt::audio::AudioChunk;

    // `AudioHandoff`'s own bounded-memory tests (retained-sample bound, exact drop count, a
    // benign positive control) now live with the type, in `capture_handoff.rs` — shared with
    // the Cloud route rather than duplicated here.

    /// Serializes tests in this module (and `cloud_stt`, below) that touch the process-wide
    /// `ENGINE_NOTE` / `LAST_FAILURE` / `PROVIDER_LABEL` / `WORKER` statics — the same pattern
    /// `main.rs`'s `ENV_LOCK` uses for its own process-global test state. `cargo test` runs
    /// tests in this binary on multiple threads by default, and without this two such tests
    /// would race each other's writes to the same statics.
    static STATE_LOCK: Mutex<()> = Mutex::new(());
    fn state_locked() -> std::sync::MutexGuard<'static, ()> {
        STATE_LOCK.lock().unwrap_or_else(|e| e.into_inner())
    }

    #[test]
    fn should_note_audio_drop_is_sticky_and_needs_a_real_drop() {
        // The shared (86akby7th: "one shared counter") sticky-notice decision both routes call.
        // POSITIVE CONTROL first — a real drop with no prior note must fire.
        assert!(
            should_note_audio_drop(1, false),
            "a genuine drop with no prior note must fire"
        );
        // A zero count must never fire, noted or not.
        assert!(
            !should_note_audio_drop(0, false),
            "zero drops must never set the notice"
        );
        assert!(
            !should_note_audio_drop(0, true),
            "zero drops must never set the notice"
        );
        // Sticky: once already noted, a FURTHER drop must not re-fire (the caller's job is to
        // set the note once and leave it, not flicker on every poll).
        assert!(
            !should_note_audio_drop(50, true),
            "already-noted must stay sticky even as the drop count keeps climbing"
        );
    }

    /// Reproduces, deterministically and with no thread/model/microphone involved, the EXACT
    /// sequence `run_on_device`'s source loop produces when `load_recognizer` (a first-run
    /// download, or — per 86akcfpcc — the ~5s SHA-256 verify+load that happens on EVERY fresh
    /// session even with a warm cache) has taken long enough for real audio to pile up
    /// somewhere `AudioHandoff` cannot see or count: `AudioHandoff` is constructed AFTER
    /// `load_recognizer` returns (see `run_on_device`), so anything captured before that point
    /// lives only in `CpalSource`'s OWN ring (`PcmRing`, capacity `MAX_PCM_SAMPLES` = 30s), a
    /// buffer this module never reads a drop count from.
    ///
    /// `CpalSource::next_chunk` always drains its ring to completion in ONE `AudioChunk` — so
    /// the FIRST chunk the fresh `AudioHandoff` ever sees after a slow load is that whole
    /// backlog, retained WHOLE because it is the only chunk present (`capture_handoff.rs`'s own
    /// `a_single_chunk_larger_than_the_cap_is_retained_whole_not_evicted_to_empty`). This test's
    /// point is what happens next: the VERY NEXT ordinary live chunk — silence or speech, it
    /// makes no difference — evicts that entire backlog in one shot, and does so before the
    /// recognition thread has had any chance to decode a single frame. `should_note_audio_drop`
    /// cannot tell that story from a bare drop count, which is exactly why the wording this
    /// fires (`ON_DEVICE_AUDIO_DROPPED_NOTICE`, "audio is being captured faster than it can be
    /// processed") is a claim about ONGOING throughput that this sequence does not support.
    #[test]
    fn a_startup_backlog_dump_can_trip_the_notice_before_any_decode_happens() {
        let handoff = AudioHandoff::new(HANDOFF_MAX_SAMPLES);

        // The backlog: comfortably bigger than the hand-off's own cap, standing in for what a
        // real mic accumulates in `PcmRing` while `load_recognizer` blocks (bounded at
        // `PcmRing`'s own 30s cap in the worst case — see `selahcue_stt::audio::MAX_PCM_SAMPLES`).
        let backlog_samples = HANDOFF_MAX_SAMPLES.get() * 3;
        handoff.push(AudioChunk::new(vec![0.0; backlog_samples], 48_000, 1));

        // PREMISE, asserted before the real claim: a lone oversized chunk is retained whole,
        // not evicted down to empty — if this ever regresses, the rest of this test would prove
        // nothing about a "dump then evict" sequence, because there would be nothing left to
        // dump. Named so a failure here points at the right place, not the assertion below it.
        assert_eq!(
            handoff.dropped(),
            0,
            "premise: a lone oversized chunk must be retained whole (see capture_handoff.rs), \
             not partially evicted — otherwise this test does not exercise the sequence it \
             claims to"
        );
        assert!(
            !should_note_audio_drop(handoff.dropped(), false),
            "the notice must not fire before anything has actually been evicted"
        );

        // Ordinary live capture continuing — ~10ms of audio, the size of one real cpal
        // callback's worth, at whatever peak level (silence here; the level is irrelevant to
        // eviction). The recognition thread has done NOTHING in this test: no `drain()`, no
        // `engine.process` call — zero decode work performed, by construction, since this test
        // never creates a recognizer or a recognition thread at all.
        handoff.push(AudioChunk::new(vec![0.0; 480], 48_000, 1));

        assert!(
            handoff.dropped() >= backlog_samples as u64,
            "the whole backlog must be evicted once any further audio arrives — got {} dropped",
            handoff.dropped()
        );
        assert!(
            should_note_audio_drop(handoff.dropped(), false),
            "REMOVING the backlog-then-one-more-push sequence's eviction must fail this test: \
             this is exactly the sequence that fires ON_DEVICE_AUDIO_DROPPED_NOTICE in \
             production before the recognizer has processed anything at all — see \
             run_on_device's source loop and its call to AudioHandoff::new AFTER \
             load_recognizer returns"
        );
    }

    /// A source with nothing buffered: `flush_pending_backlog` must be a true no-op, never
    /// panicking and never fabricating samples to discard. POSITIVE CONTROL for the eviction
    /// test below — without this, "discards everything queued" could be satisfied by a function
    /// that also discards things that were never there.
    #[test]
    fn flush_pending_backlog_on_an_empty_source_discards_nothing() {
        struct EmptySource(selahcue_stt::audio::FakeAudioSource);
        impl AudioSource for EmptySource {
            fn label(&self) -> &str {
                "empty"
            }
            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.0.next_chunk()
            }
        }
        impl CaptureSource for EmptySource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }
        let mut source = EmptySource(selahcue_stt::audio::FakeAudioSource::new());
        assert_eq!(flush_pending_backlog(&mut source), 0);
    }

    /// The mechanism `run_on_device` relies on: everything currently queued on `source` is
    /// discarded and counted, in one call, with nothing left behind for the caller's own
    /// `next_chunk` loop to pick up afterward (the second assertion is what makes this a fix for
    /// the bug — a flush that left even one chunk behind would still hand that chunk to a fresh
    /// `AudioHandoff` next).
    #[test]
    fn flush_pending_backlog_discards_everything_queued_and_reports_the_exact_count() {
        struct QueuedSource(selahcue_stt::audio::FakeAudioSource);
        impl AudioSource for QueuedSource {
            fn label(&self) -> &str {
                "queued"
            }
            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.0.next_chunk()
            }
        }
        impl CaptureSource for QueuedSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }
        let mut inner = selahcue_stt::audio::FakeAudioSource::new();
        inner.push_chunk(AudioChunk::new(vec![0.0; 300_000], 48_000, 1));
        inner.push_chunk(AudioChunk::new(vec![0.0; 1], 48_000, 1));
        inner.push_chunk(AudioChunk::new(vec![0.0; 42], 48_000, 1));
        let mut source = QueuedSource(inner);

        assert_eq!(
            flush_pending_backlog(&mut source),
            300_000 + 1 + 42,
            "must report the EXACT total across every queued chunk, not just whether any \
             existed"
        );
        assert!(
            source.next_chunk().is_none(),
            "REMOVING the drain loop (leaving one chunk un-flushed) must fail this test: a \
             chunk left behind here is a chunk `run_on_device` would still hand to a fresh \
             AudioHandoff next"
        );
    }

    #[test]
    fn append_engine_note_never_erases_a_distinct_existing_note() {
        let _guard = state_locked();

        // Baseline: nothing set yet — appending sets it plainly, no leading artifact.
        *status_lock(&ENGINE_NOTE) = None;
        append_engine_note("first note");
        assert_eq!(engine_note().as_deref(), Some("first note"));

        // POSITIVE CONTROL for the fix (86akby7th PR #22 review, LOW): a distinct note already
        // in the slot (e.g. an engine-change disclosure) must survive a LATER drop notice — the
        // bug this replaces was a plain `*status_lock(&ENGINE_NOTE) = Some(addition)`, which
        // erased whatever was there.
        *status_lock(&ENGINE_NOTE) = Some("engine changed".to_string());
        append_engine_note("audio dropped");
        assert_eq!(
            engine_note().as_deref(),
            Some("engine changed audio dropped"),
            "a later append must not erase the note already there"
        );

        // Idempotent: appending the SAME text again must not duplicate the suffix.
        append_engine_note("audio dropped");
        assert_eq!(
            engine_note().as_deref(),
            Some("engine changed audio dropped"),
            "appending the same text twice must not duplicate it"
        );

        *status_lock(&ENGINE_NOTE) = None; // leave the slot clean for other tests
    }

    #[test]
    fn on_device_failure_tears_the_worker_slot_down_and_reports_both_facts() {
        let _guard = state_locked();

        // Arrange the EXACT shape of Quinn's PR #22 "zombie worker" finding: a worker slot left
        // occupied by `start()`, a stale Cloud provider label, and a stale "coming from
        // on-device instead" note — all three left over from BEFORE a mid-service fallback's
        // `load_recognizer()` call fails.
        *worker_lock() = Some(Worker {
            stop: Arc::new(AtomicBool::new(false)),
            handle: None,
        });
        *status_lock(&PROVIDER_LABEL) = Some("deepgram-nova-3".to_string());
        *status_lock(&ENGINE_NOTE) = Some("stale: coming from on-device instead".to_string());
        clear_failure();
        assert!(is_listening(), "premise: the worker slot starts occupied");

        let message = abandon_worker_after_on_device_failure(
            &Some(FallbackContext {
                prior_failure: "cloud transcription stopped: Failed".to_string(),
                note: "unused on the failure path",
            }),
            "model file not found".to_string(),
        );

        assert!(
            !is_listening(),
            "REMOVING this teardown must fail this test: a worker slot that outlives the \
             thread it names is what made `detector_state` report Listening forever instead of \
             Unavailable (Quinn, PR #22 review)"
        );
        assert_eq!(
            provider_label(),
            None,
            "no engine is producing a transcript any more — the stale Deepgram label must not \
             survive on-device also failing"
        );
        assert_eq!(
            engine_note(),
            None,
            "a note claiming on-device is running must not survive on-device actually failing"
        );
        assert!(
            message.contains("cloud transcription stopped: Failed")
                && message.contains("on-device fallback also failed: model file not found"),
            "the reported message must carry BOTH facts (why cloud stopped AND why the \
             fallback also failed), got {message:?}"
        );
        assert_eq!(
            last_failure().as_deref(),
            Some(message.as_str()),
            "the folded message must be what's retained as the terminal failure"
        );

        *worker_lock() = None; // leave the slot clean for other tests
        clear_failure();
    }

    #[test]
    fn on_device_failure_with_no_prior_engine_reports_the_bare_error() {
        let _guard = state_locked();
        *worker_lock() = Some(Worker {
            stop: Arc::new(AtomicBool::new(false)),
            handle: None,
        });

        let message =
            abandon_worker_after_on_device_failure(&None, "no default input device".to_string());

        assert_eq!(
            message, "no default input device",
            "with no prior engine to fold in (on-device chosen outright, or an immediate \
             pre-stream Cloud fallback), the message is exactly the bare on-device error"
        );
        assert!(!is_listening());

        *worker_lock() = None;
        clear_failure();
    }

    #[cfg(feature = "cloud-stt")]
    mod cloud_stt {
        use super::super::*;
        use selahcue_stt::audio::{AudioChunk, AudioSource, FakeAudioSource};
        use selahcue_stt_cloud::error::OperatorAction;
        use selahcue_stt_cloud::session::StreamParams;
        use selahcue_stt_cloud::{
            AudioRing, CloudTranscriptProvider, SegmentQueue, SessionState, SessionStatus,
            DEGRADED_FALLBACK_NOTICE,
        };
        use std::time::Instant;

        #[test]
        fn round_trips_silence_and_full_scale() {
            // Positive control: known values map to known PCM, so a mutation of the formula
            // (e.g. dropping the `* i16::MAX` scale, or using `i16::MIN` for the positive peak)
            // is caught rather than only exercising the clamp below.
            assert_eq!(pcm_i16_from_f32(&[0.0]), vec![0i16]);
            assert_eq!(pcm_i16_from_f32(&[1.0]), vec![i16::MAX]);
            // -1.0 * i16::MAX rounds to -32767, one shy of i16::MIN — expected: PCM is not
            // symmetric around 0 at i16::MAX, and clamping the INPUT (not the output) is what
            // `out_of_range_input_is_clamped_not_wrapped` below actually exercises.
            assert_eq!(pcm_i16_from_f32(&[-1.0]), vec![-i16::MAX]);
        }

        #[test]
        fn out_of_range_input_is_clamped_not_wrapped() {
            // A capture glitch above 1.0 must clamp to the same value 1.0 produces, never wrap
            // around to a negative sample that would read as a loud click of the wrong sign.
            assert_eq!(pcm_i16_from_f32(&[2.5]), pcm_i16_from_f32(&[1.0]));
            assert_eq!(pcm_i16_from_f32(&[-2.5]), pcm_i16_from_f32(&[-1.0]));
        }

        // --- `run_cloud_stream_loop` (Quinn, PR #22 review: "zero coverage" — deleting the
        // entire terminal-handoff block left 104/104 tests passing) --------------------------
        //
        // A [`CaptureSource`] backed by [`FakeAudioSource`] — no real microphone, deterministic
        // — so the loop can be driven end to end with no hardware, no network socket, and no
        // whisper model anywhere nearby: `SessionStatus`, `AudioRing`, `SegmentQueue` and
        // `CloudTranscriptProvider` are all constructible without the `deepgram` transport
        // (see `selahcue-stt-cloud`'s own lib doc — "everything decidable without a socket
        // already has been, in the default build").

        struct TestSource {
            inner: FakeAudioSource,
        }

        impl TestSource {
            fn empty() -> Self {
                TestSource {
                    inner: FakeAudioSource::new(),
                }
            }

            fn with_one_chunk(chunk: AudioChunk) -> Self {
                TestSource {
                    inner: FakeAudioSource::with_chunks([chunk]),
                }
            }
        }

        impl AudioSource for TestSource {
            fn label(&self) -> &str {
                "test"
            }

            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.inner.next_chunk()
            }
        }

        impl CaptureSource for TestSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }

        impl CloudCaptureSource for TestSource {
            fn sample_rate(&self) -> u32 {
                // A representative, safely-sizeable value — `run_cloud`'s handoff-capacity
                // sizing (`selahcue_core::audio_capacity::handoff_capacity`) only needs a
                // nonzero rate/channel pair that multiplies without overflow; the tests below
                // that reach `run_cloud` itself do not assert on the resulting capacity.
                16_000
            }
            fn channels(&self) -> u16 {
                1
            }
        }

        /// Generous enough that no test below trips the hand-off's OWN drop-oldest bound by
        /// accident — each test isolates ONE specific exit path or drop/refusal source.
        fn generous_handoff() -> AudioHandoff {
            AudioHandoff::new(NonZeroUsize::new(10_000_000).expect("nonzero"))
        }

        fn empty_provider() -> CloudTranscriptProvider {
            CloudTranscriptProvider::new(SegmentQueue::new(), &StreamParams::default())
        }

        /// How long [`run_cloud_stream_loop`] gets to return in the three tests below before
        /// the test itself fails it — generous for a loop that does no real I/O and normally
        /// returns in well under a millisecond, nowhere near the `operator` CI job's full
        /// 25-minute timeout.
        const LOOP_RETURN_BOUND: Duration = Duration::from_secs(2);

        /// Run `f` (expected to call [`run_cloud_stream_loop`] exactly once) on its own thread
        /// and fail with a clear message if it has not returned within [`LOOP_RETURN_BOUND`],
        /// rather than hanging.
        ///
        /// The three exit-path tests below (`a_clean_stop_…`, `a_terminal_cloud_session_…`,
        /// `a_consent_revocation_…`) each remove every reason to exit the loop EXCEPT the one
        /// under test — that is what makes them a real regression test for that branch. It also
        /// means a future edit that breaks the SAME branch (e.g. an early `return` added above
        /// the check, or a condition inverted) leaves the loop with no live exit at all, and it
        /// spins forever. Before this helper, that read as a stuck test name burning the whole
        /// CI job's 25-minute timeout with no indication of which of the three branches was at
        /// fault (86akby7th PR #22 remediation round 2, Cody Medium). Mirrors the bounded-wait
        /// idiom already proven one file away —
        /// [`selahcue_stt_cloud::transport::CloudSttSession::shutdown`]'s own
        /// `finished.recv_timeout(SHUTDOWN_GRACE)` — rather than an unbounded join, which would
        /// defeat the entire point.
        ///
        /// Deliberately does NOT join a thread that overran: an overrun means something is
        /// wedged with no bounded exit of its own, and joining it here would just relocate the
        /// hang from "a stuck test" to "a stuck cleanup step". The orphaned thread is reclaimed
        /// when the test process exits, the same trade-off `CloudSttSession::shutdown` itself
        /// makes on its own timeout path.
        fn assert_loop_returns_within(f: impl FnOnce() + Send + 'static) {
            let handle = std::thread::spawn(f);
            let start = Instant::now();
            loop {
                if handle.is_finished() {
                    if let Err(panic) = handle.join() {
                        std::panic::resume_unwind(panic);
                    }
                    return;
                }
                assert!(
                    start.elapsed() < LOOP_RETURN_BOUND,
                    "run_cloud_stream_loop did not return within {LOOP_RETURN_BOUND:?} — this \
                     scenario removed every exit path except the one under test, so it has no \
                     way to return; a live regression here would otherwise hang for the whole \
                     `operator` CI job's 25-minute timeout instead of failing (86akby7th PR #22 \
                     remediation round 2, Cody Medium)"
                );
                std::thread::sleep(Duration::from_millis(5));
            }
        }

        #[test]
        fn a_clean_stop_takes_the_stop_branch_and_never_calls_the_fallback() {
            let stop_worker = Arc::new(AtomicBool::new(true)); // ALREADY asked to stop
            let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);
            let handoff = generous_handoff();
            let audio_ring = AudioRing::new();
            let status = SessionStatus::new(); // Idle — non-terminal; must not matter here

            let clean_stop_called = Arc::new(AtomicBool::new(false));
            let clean_stop_called2 = Arc::clone(&clean_stop_called);
            let fallback_called = Arc::new(AtomicBool::new(false));
            let fallback_called2 = Arc::clone(&fallback_called);

            assert_loop_returns_within(move || {
                run_cloud_stream_loop(
                    TestSource::empty(),
                    stop_worker,
                    seg_tx,
                    &handoff,
                    &audio_ring,
                    empty_provider(),
                    &status,
                    |_s: &mut TestSource| {},
                    || true, // consent stays granted throughout
                    move || clean_stop_called2.store(true, Ordering::SeqCst),
                    move |_s, _sw, _tx, _prior, _note| {
                        fallback_called2.store(true, Ordering::SeqCst)
                    },
                );
            });

            assert!(
                clean_stop_called.load(Ordering::SeqCst),
                "an already-stopped worker must take the clean-stop branch"
            );
            assert!(
                !fallback_called.load(Ordering::SeqCst),
                "a clean, operator-driven stop must never fall back to on-device"
            );
        }

        #[test]
        fn a_terminal_cloud_session_hands_off_with_the_degraded_fallback_note() {
            let stop_worker = Arc::new(AtomicBool::new(false));
            let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);
            let handoff = generous_handoff();
            let audio_ring = AudioRing::new();
            let status = SessionStatus::new();
            status.set(SessionState::Failed {
                action: OperatorAction::ReportDefect,
                message: "boom".to_string(),
            });

            let captured: Arc<Mutex<Option<(String, &'static str)>>> = Arc::new(Mutex::new(None));
            let captured2 = Arc::clone(&captured);
            let clean_stop_called = Arc::new(AtomicBool::new(false));
            let clean_stop_called2 = Arc::clone(&clean_stop_called);

            assert_loop_returns_within(move || {
                run_cloud_stream_loop(
                    TestSource::empty(),
                    stop_worker,
                    seg_tx,
                    &handoff,
                    &audio_ring,
                    empty_provider(),
                    &status,
                    |_s: &mut TestSource| {},
                    || true, // consent stays granted — isolates the TERMINAL branch specifically
                    move || clean_stop_called2.store(true, Ordering::SeqCst),
                    move |_s, _sw, _tx, prior_failure, note| {
                        *captured2.lock().unwrap_or_else(|e| e.into_inner()) =
                            Some((prior_failure, note));
                    },
                );
            });

            assert!(
                !clean_stop_called.load(Ordering::SeqCst),
                "a terminal session must not take the clean-stop branch"
            );
            let (prior_failure, note) = captured
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .clone()
                .expect(
                    "REMOVING the terminal-session handoff (or never calling the fallback) must \
                 fail this test — Quinn's PR #22 finding was that deleting this exact block \
                 left 104/104 tests passing",
                );
            assert!(
                prior_failure.contains("cloud transcription stopped"),
                "got {prior_failure:?}"
            );
            assert_eq!(
                note, DEGRADED_FALLBACK_NOTICE,
                "a genuine session failure must carry the DEGRADED note, not the consent one"
            );
        }

        #[test]
        fn a_consent_revocation_hands_off_with_the_consent_revoked_note() {
            let stop_worker = Arc::new(AtomicBool::new(false));
            let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);
            let handoff = generous_handoff();
            let audio_ring = AudioRing::new();
            // Stays Idle (non-terminal) throughout — isolates the CONSENT branch from the
            // terminal-session branch above.
            let status = SessionStatus::new();

            let captured: Arc<Mutex<Option<(String, &'static str)>>> = Arc::new(Mutex::new(None));
            let captured2 = Arc::clone(&captured);

            assert_loop_returns_within(move || {
                run_cloud_stream_loop(
                    TestSource::empty(),
                    stop_worker,
                    seg_tx,
                    &handoff,
                    &audio_ring,
                    empty_provider(),
                    &status,
                    |_s: &mut TestSource| {},
                    || false, // consent withdrawn from the very first check (Sana/Cody, PR #22 High)
                    || panic!("a consent revocation must not take the clean-stop branch"),
                    move |_s, _sw, _tx, prior_failure, note| {
                        *captured2.lock().unwrap_or_else(|e| e.into_inner()) =
                            Some((prior_failure, note));
                    },
                );
            });

            let (prior_failure, note) = captured
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .clone()
                .expect(
                    "a withdrawn `may_stream_now()` must trigger the fallback — this is the exact \
                 mid-service consent-revocation path Sana's and Cody's PR #22 findings required",
                );
            assert!(prior_failure.contains("consent"), "got {prior_failure:?}");
            assert_eq!(
                note, CONSENT_REVOKED_NOTICE,
                "a withdrawn consent must carry the CONSENT note, not the degraded-session one"
            );
        }

        #[test]
        fn a_lone_oversized_chunk_is_refused_and_still_sets_the_drop_notice() {
            let _guard = super::state_locked(); // this test touches ENGINE_NOTE via append_engine_note
            *status_lock(&ENGINE_NOTE) = None;

            // One chunk, already 16 kHz mono so resample is a no-op passthrough, comfortably
            // bigger than `MAX_AUDIO_CHUNK_BYTES` (64 KiB = 32,768 i16 samples) once PCM-encoded
            // — reproduces Vera's PR #22 finding: a stall long enough that the whole backlog
            // becomes ONE oversized chunk, which `AudioRing::push` refuses WHOLE and counts
            // ONLY in `refused_oversize()` — never in `dropped_for_bound()`.
            let oversized = AudioChunk::new(vec![0.5f32; 40_000], 16_000, 1);

            let stop_worker = Arc::new(AtomicBool::new(false));
            let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);
            // This test, uniquely among the four `run_cloud_stream_loop` exit-path tests, reads
            // `handoff`/`audio_ring` state AFTER the loop returns — but `assert_loop_returns_within`
            // moves its closure onto another thread (86akby7th PR #22 remediation round 2, Quinn
            // HIGH: this test relies on `may_stream_now()` to terminate the loop exactly like the
            // other three, but was not wrapped, so a regression here hung the whole suite instead
            // of failing — see `assert_loop_returns_within`'s own doc comment). A plain `move`
            // would consume `handoff`/`audio_ring` and leave nothing to assert against below, so
            // each is shared instead: `AudioRing` is already an `Arc`-backed handle (`.clone()`
            // shares state, per its own doc comment); `AudioHandoff` is not, so it is wrapped in
            // an `Arc` here explicitly, for the same reason.
            let handoff = Arc::new(generous_handoff());
            let handoff_for_loop = Arc::clone(&handoff);
            let audio_ring = AudioRing::new();
            let audio_ring_for_loop = audio_ring.clone();
            let status = SessionStatus::new();

            // Consent is checked at the TOP of the loop now (86akby7th PR #22 remediation round
            // 2, Sana LOW), so a constant `|| false` would exit before the chunk was ever
            // touched and prove nothing about oversize refusal. Grant it for exactly the first
            // iteration — enough to let that iteration process the chunk and evaluate the
            // drop-notice condition — then withdraw it, exiting via the consent branch.
            let allow_one_iteration = std::cell::Cell::new(true);

            assert_loop_returns_within(move || {
                run_cloud_stream_loop(
                    TestSource::with_one_chunk(oversized),
                    stop_worker,
                    seg_tx,
                    &handoff_for_loop,
                    &audio_ring_for_loop,
                    empty_provider(),
                    &status,
                    |_s: &mut TestSource| {},
                    move || allow_one_iteration.replace(false),
                    || panic!("must not take the clean-stop branch"),
                    |_s, _sw, _tx, _prior, _note| {}, // the fallback itself is not under test here
                );
            });

            assert_eq!(
                audio_ring.refused_oversize(),
                1,
                "the oversized chunk must be refused exactly once"
            );
            assert_eq!(
                audio_ring.dropped_for_bound(),
                0,
                "premise: this is refusal, not the separate byte-bound eviction path"
            );
            assert_eq!(
                handoff.dropped(),
                0,
                "premise: the hand-off itself never evicted anything (a lone chunk is kept \
                 whole regardless of size — see capture_handoff.rs)"
            );
            assert_eq!(
                engine_note().as_deref(),
                Some(AUDIO_DROPPED_NOTICE),
                "REMOVING refused_oversize() from the drop-notice sum (86akby7th PR #22 \
                 review, Vera Medium) must fail this test: dropped_for_bound() alone stays 0 \
                 here, so the notice would never fire and a 30 s backlog would vanish silently"
            );

            *status_lock(&ENGINE_NOTE) = None; // leave the slot clean for other tests
        }
    }

    // --- `run_cloud` itself, end to end (86akby7th PR #22 remediation round 2) -------------
    //
    // `cloud_stt`'s tests above drive `run_cloud_stream_loop` with FAKE closures — they prove
    // that function's own exits fire correctly, but they cannot see whether `run_cloud`'s REAL
    // closures are wired correctly, because those tests never construct them. That gap is
    // exactly how the fallback branch shipped with no `session.stop()` call at all: every test
    // was green. Sana's PR #22 review rejected "untestable — no `AppHandle` harness" as the
    // reason that gap was allowed to stand: `tauri::test::mock_app()` mints a real
    // `App`/`AppHandle` (`MockRuntime`) with no window and no OS integration, which is enough
    // to call `run_cloud` for real, with managed `AppState`, and drive a REAL
    // `CloudSttSession` against a local stub server.
    //
    // **`#[cfg(unix)]`, in addition to `cloud-stt`, and deliberately so (86akby7th PR #22
    // remediation round, Cody / Sana / Quinn HIGH, found independently by all three).**
    // [`HeldOpenModelFile`] shells out to the `mkfifo` binary with no OS guard at all, and the
    // `operator` job's `Test (stt,cloud-stt)` step runs across `[ubuntu, macos, windows-latest]`
    // with no OS skip — so an unguarded build breaks CI on Windows, not just "doesn't work
    // there". Sana's finding is the sharper one: even where an MSYS `mkfifo` happens to be on
    // `PATH`, it creates a Cygwin-emulated FIFO that a native Rust `std::fs::File::open` does
    // NOT block on the way a POSIX FIFO does — so the held-open hold this test's whole ordering
    // argument depends on would silently not hold, and the `!worker.is_finished()` positive
    // control a few dozen lines down would fail instead of the intended assertion. Every path is
    // a red, none is a benign skip; gating the whole module is the honest fix, not a smaller
    // one inside it.
    //
    // This means **Windows has no behavioural cover for the `run_cloud` fallback composition
    // this module exists to test** — deliberately, and stated here rather than left to be
    // discovered by inspection. That gap is defensible because the code under test
    // (`run_cloud`'s closure composition, `close_cloud_session`, `SharedCloudSession`) is itself
    // entirely platform-neutral: nothing in the PRODUCTION path is `#[cfg(unix)]`, only this
    // ONE test's mechanism for forcing a deterministic hold is. A cross-platform replacement
    // (e.g. a channel-based rendezvous instead of a FIFO) would close this gap and is a
    // reasonable follow-up; it was not attempted here to keep this remediation round scoped to
    // the four reviewers' actual findings.
    #[cfg(all(feature = "cloud-stt", unix))]
    mod run_cloud_composition {
        use super::super::*;
        use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
        use selahcue_stt::audio::{AudioChunk, AudioSource, FakeAudioSource};
        use std::time::Instant;

        /// A capture source that produces silence forever — `run_cloud` only needs SOME
        /// `CloudCaptureSource`, and this test does not exercise the audio path at all.
        struct NullSource {
            inner: FakeAudioSource,
        }

        impl NullSource {
            fn new() -> Self {
                NullSource {
                    inner: FakeAudioSource::new(),
                }
            }
        }

        impl AudioSource for NullSource {
            fn label(&self) -> &str {
                "test"
            }

            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.inner.next_chunk()
            }
        }

        impl CaptureSource for NullSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }

        impl CloudCaptureSource for NullSource {
            fn sample_rate(&self) -> u32 {
                16_000
            }
            fn channels(&self) -> u16 {
                1
            }
        }

        /// Poll `check` until it holds or `limit` elapses. Returns whether it ever held, so a
        /// caller asserts with an honest message instead of the loop just falling through.
        fn within(limit: Duration, mut check: impl FnMut() -> bool) -> bool {
            let deadline = Instant::now() + limit;
            loop {
                if check() {
                    return true;
                }
                if Instant::now() >= deadline {
                    return check();
                }
                std::thread::sleep(Duration::from_millis(5));
            }
        }

        /// A POSIX FIFO whose read end this test controls, so `run_on_device`'s (real)
        /// `load_recognizer` can be held BLOCKED, deterministically, for as long as this test
        /// wants — no sleep-and-hope timing race against how fast a local file read happens to
        /// fail.
        ///
        /// Why this exists at all: `run_cloud`'s stack frame — and with it, any Cloud session
        /// that the buggy pre-fix `on_fallback` merely left captured in an unused local rather
        /// than explicitly stopping — does not actually drop until `run_cloud` RETURNS, and
        /// `Drop for CloudSttSession` closes the socket too. If `run_on_device`'s failure were
        /// allowed to return in microseconds (e.g. failing on a nonexistent path), a buggy
        /// build closes the socket via that implicit drop just as fast as a correct build closes
        /// it via the explicit `close_cloud_session` call — the two are indistinguishable by
        /// wall-clock timing, and a first attempt at this test proved exactly that: it passed
        /// unchanged with the fix's `close_cloud_session(&session_for_fallback);` call deleted.
        /// Holding `run_on_device` open on a blocked read turns "did it close before the NEXT
        /// step, or only when the whole call finally unwound" from a timing race into a state
        /// this test can just look at.
        struct HeldOpenModelFile {
            path: PathBuf,
        }

        impl HeldOpenModelFile {
            fn create() -> Self {
                let path = std::env::temp_dir().join(format!(
                    "selahcue-run-cloud-composition-test-{}-{:?}.fifo",
                    std::process::id(),
                    std::thread::current().id()
                ));
                let _ = std::fs::remove_file(&path); // stale FIFO from a killed prior run
                let status = std::process::Command::new("mkfifo")
                    .arg(&path)
                    .status()
                    .expect("run mkfifo");
                assert!(status.success(), "mkfifo failed for {path:?}");
                HeldOpenModelFile { path }
            }

            /// Open the write end, send a few bytes (guaranteed to fail the SHA-256 check — its
            /// content is irrelevant, this test wants on-device to fail either way), and close
            /// it — which is what lets the blocked reader on the other end finally see EOF.
            fn release(&self) {
                use std::io::Write;
                let mut writer = std::fs::OpenOptions::new()
                    .write(true)
                    .open(&self.path)
                    .expect("open the FIFO's write end");
                let _ = writer.write_all(b"not a real whisper model");
            }
        }

        impl Drop for HeldOpenModelFile {
            fn drop(&mut self) {
                let _ = std::fs::remove_file(&self.path);
            }
        }

        /// Sets the four environment variables this test's `run_cloud` composition depends on
        /// (`SELAHCUE_STT_MODEL`, `_SHA256`, `DEEPGRAM_API_KEY`,
        /// `SELAHCUE_STT_CLOUD_TEST_ENDPOINT`) and removes all four on drop, unconditionally —
        /// including when an assertion further down the test panics before reaching the code
        /// that used to clean them up (86akby7th PR #22 remediation round, Cody / Quinn MEDIUM).
        ///
        /// Before this, cleanup was four `std::env::remove_var` calls at the very end of the
        /// happy path — so ANY earlier `assert!` failing (there are several, deliberately, each
        /// checking one step of the fallback ordering) unwound past them and left all four set
        /// in the process environment for every test that runs afterward in this binary.
        /// `crate::env_locked()` (held for this test's whole body, see `_env_guard` below) only
        /// serialises WHICH test may read/write these names at a time — it does not reset their
        /// values, so a leak here would be read by whichever test acquires the lock next, not
        /// caught by the lock itself. The discipline already exists once in this same file, for
        /// the FIFO path — see [`HeldOpenModelFile`]'s own `Drop`; this is that same pattern
        /// applied to the env vars.
        struct TestEnvVars;

        impl TestEnvVars {
            fn set(model_path: &Path, cloud_endpoint: &str) -> Self {
                std::env::set_var("SELAHCUE_STT_MODEL", model_path);
                std::env::set_var("SELAHCUE_STT_MODEL_SHA256", "0".repeat(64));
                std::env::set_var("DEEPGRAM_API_KEY", "test-fixture-credential-000000");
                std::env::set_var("SELAHCUE_STT_CLOUD_TEST_ENDPOINT", cloud_endpoint);
                TestEnvVars
            }
        }

        impl Drop for TestEnvVars {
            fn drop(&mut self) {
                std::env::remove_var("SELAHCUE_STT_MODEL");
                std::env::remove_var("SELAHCUE_STT_MODEL_SHA256");
                std::env::remove_var("DEEPGRAM_API_KEY");
                std::env::remove_var("SELAHCUE_STT_CLOUD_TEST_ENDPOINT");
            }
        }

        /// Proves the property `TestEnvVars` exists for, directly and without the cost/flakiness
        /// of driving the full `run_cloud` composition: an assertion panicking BETWEEN
        /// `TestEnvVars::set` and the end of a test must not leave any of the four variables set
        /// for whatever test acquires `ENV_LOCK` next. `catch_unwind` here stands in for the test
        /// harness's own panic boundary — what matters is that `TestEnvVars`'s `Drop` runs during
        /// that unwind, same as it would in the real composition test above (86akby7th PR #22
        /// remediation round, Cody / Quinn MEDIUM). Not gated to real `run_cloud` machinery
        /// (mkfifo, tokio, a stub socket) — this test's premise is about `Drop`-during-unwind,
        /// which needs none of that, so it stays fast and independent of the `unix`-only gate
        /// above (moved out of `run_cloud_composition` would be equally valid; kept here because
        /// `TestEnvVars` is private to this module).
        #[test]
        fn test_env_vars_are_removed_on_drop_even_after_a_panic() {
            let _env_guard = crate::env_locked();
            // Baseline: none of these leak in from an unrelated test that ran earlier.
            for name in [
                "SELAHCUE_STT_MODEL",
                "SELAHCUE_STT_MODEL_SHA256",
                "DEEPGRAM_API_KEY",
                "SELAHCUE_STT_CLOUD_TEST_ENDPOINT",
            ] {
                std::env::remove_var(name);
            }

            let result = std::panic::catch_unwind(|| {
                let _guard = TestEnvVars::set(
                    Path::new("/does-not-need-to-exist"),
                    "ws://example.invalid/v1/listen",
                );
                assert_eq!(
                    std::env::var("SELAHCUE_STT_MODEL").as_deref(),
                    Ok("/does-not-need-to-exist"),
                    "premise: the guard actually set the variable"
                );
                panic!(
                    "simulated assertion failure partway through the real composition test, \
                     BEFORE any explicit cleanup would have run"
                );
            });
            assert!(
                result.is_err(),
                "premise: the simulated failure actually unwound"
            );

            assert!(
                std::env::var("SELAHCUE_STT_MODEL").is_err(),
                "REMOVING TestEnvVars's Drop impl (reverting to explicit remove_var calls only \
                 at the end of the happy path) must fail this test: a panic partway through must \
                 not leave SELAHCUE_STT_MODEL set for the next test to acquire ENV_LOCK"
            );
            assert!(std::env::var("SELAHCUE_STT_MODEL_SHA256").is_err());
            assert!(std::env::var("DEEPGRAM_API_KEY").is_err());
            assert!(std::env::var("SELAHCUE_STT_CLOUD_TEST_ENDPOINT").is_err());
        }

        #[test]
        fn run_cloud_closes_the_deepgram_session_before_falling_back_on_consent_revocation() {
            let _env_guard = crate::env_locked();
            let _state_guard = super::state_locked();

            // `run_cloud`'s `on_fallback` closure, if this test's fix is in place, calls the
            // REAL `run_on_device` — which must not attempt a ~1.6 GB model download. Pointing
            // `SELAHCUE_STT_MODEL` at this FIFO makes `load_recognizer`'s `verify_model` block
            // (a POSIX FIFO opened for reading blocks until a writer opens it) INSIDE
            // `run_on_device`, on the capture worker thread, for as long as this test wants —
            // see `HeldOpenModelFile`. No network either way: the write end sends a few garbage
            // bytes, which fails the SHA-256 check locally.
            let held_model = HeldOpenModelFile::create();

            // A tiny local stub that completes the WebSocket handshake — so the session this
            // test drives actually reaches `Streaming` against it, which is what makes "the
            // socket closes on revocation" a claim about a LIVE connection rather than one that
            // never opened — then just watches for the peer to close, recording when. Same
            // shape `selahcue-stt-cloud`'s own `tests/test_transport.rs`
            // (`dropping_the_session_handle_stops_the_stream`) already uses and already proves
            // works; reused rather than reinvented.
            let runtime = tokio::runtime::Runtime::new().expect("build a tokio runtime");
            let handshaken = Arc::new(AtomicBool::new(false));
            let handshaken_server = Arc::clone(&handshaken);
            let closed_at: Arc<Mutex<Option<Instant>>> = Arc::new(Mutex::new(None));
            let closed_at_server = Arc::clone(&closed_at);
            let port = runtime.block_on(async {
                let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
                    .await
                    .expect("bind loopback");
                let port = listener.local_addr().expect("local addr").port();
                tokio::spawn(async move {
                    let Ok((stream, _)) = listener.accept().await else {
                        return;
                    };
                    if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
                        handshaken_server.store(true, Ordering::SeqCst);
                        while futures_util::StreamExt::next(&mut socket).await.is_some() {}
                        *closed_at_server.lock().unwrap_or_else(|e| e.into_inner()) =
                            Some(Instant::now());
                    }
                });
                port
            });

            // Sets all four env vars this composition depends on; removed on drop, including on
            // an early panic from one of the several `assert!`s below — see `TestEnvVars`.
            let _env_vars = TestEnvVars::set(
                &held_model.path,
                &format!("ws://127.0.0.1:{port}/v1/listen"),
            );

            let mut providers = ProvidersConfig::default();
            providers.settings.transcription_mode = TranscriptionMode::Cloud;
            providers.consent.cloud_transcription = true;

            let app = tauri::test::mock_app();
            let handle = app.handle().clone();
            handle.manage(crate::AppState {
                backend: crate::Backend::Local(crate::demo_shell()),
                deck: Mutex::new(crate::DeckWorkspace::demo()),
                library: Mutex::new(crate::DeckLibrary::load(None)),
                providers: Mutex::new(providers),
                providers_db: None,
                secrets: crate::make_secret_store(),
                link_error: Mutex::new(None),
            });

            let stop_worker = Arc::new(AtomicBool::new(false));
            let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);
            let (ready_tx, ready_rx) = tokio::sync::oneshot::channel();

            let handle_for_worker = handle.clone();
            let worker = std::thread::spawn(move || {
                run_cloud(
                    handle_for_worker,
                    NullSource::new(),
                    stop_worker,
                    seg_tx,
                    ready_tx,
                );
            });

            assert!(
                within(Duration::from_secs(10), || handshaken
                    .load(Ordering::SeqCst)),
                "the stub server never completed the WebSocket handshake — the session never \
                 went live, so revoking consent below would prove nothing about tearing down a \
                 LIVE connection"
            );
            let ready = runtime
                .block_on(async { tokio::time::timeout(Duration::from_secs(5), ready_rx).await });
            assert!(
                matches!(ready, Ok(Ok(Ok(())))),
                "run_cloud must report ready once the session starts, got {ready:?}"
            );

            // Revoke consent WHILE the session is live — the exact mid-service withdrawal
            // `CONSENT_REVOKED_NOTICE` describes. `run_on_device`'s (real) `load_recognizer`
            // is about to block on `held_model`'s FIFO, deterministically, until this test
            // releases it below — so everything asserted before that release is a statement
            // about state DURING the fallback, not after `run_cloud` has already returned.
            let revoked_at = Instant::now();
            handle
                .state::<crate::AppState>()
                .providers
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .consent
                .cloud_transcription = false;

            // THE assertion this test exists for: the stub server's side of the socket actually
            // closed — and, thanks to `held_model`, closed WHILE `run_on_device` is still
            // blocked, not merely by the time `run_cloud` eventually returns. A build that
            // reverts to the pre-fix `on_fallback` (which never touched `session` at all)
            // leaves the session captured in a local that `run_cloud`'s own stack frame keeps
            // alive for as long as `run_on_device` blocks — i.e. for as long as this test is
            // willing to hold the FIFO — so `closed_at` would stay `None` here and this
            // `within` would time out.
            assert!(
                within(Duration::from_secs(5), || {
                    closed_at
                        .lock()
                        .unwrap_or_else(|e| e.into_inner())
                        .is_some()
                }),
                "REMOVING `close_cloud_session` from `run_cloud`'s `on_fallback` closure must \
                 fail this test: the stub server never saw the socket close WHILE the fallback \
                 was still blocked in `load_recognizer` — this is the exact composition gap the \
                 first remediation round shipped through (86akby7th PR #22 remediation round 2, \
                 Cody High / Vera High)"
            );

            // POSITIVE CONTROL: confirm the premise that made the assertion above meaningful —
            // `run_cloud` genuinely has not returned yet (still blocked on the FIFO). Without
            // this, a `closed_at` set only AFTER `run_cloud` already returned (the buggy,
            // Drop-at-unwind timing) could still race the check above and pass for the wrong
            // reason on a slow CI runner.
            assert!(
                !worker.is_finished(),
                "premise violated: run_cloud returned before this test released the FIFO, so \
                 the assertion above proves nothing about ordering"
            );
            let closed_at = closed_at
                .lock()
                .unwrap_or_else(|e| e.into_inner())
                .expect("checked Some by the `within` above");
            assert!(
                closed_at >= revoked_at,
                "the socket must not appear to close before consent was even revoked"
            );

            // Release the held FIFO so `load_recognizer` gets EOF, fails the SHA-256 check
            // (the bytes sent are not a real model), and `run_on_device` — and with it,
            // `run_cloud` — finally returns.
            held_model.release();
            assert!(
                within(Duration::from_secs(5), || worker.is_finished()),
                "run_cloud did not return after the held FIFO was released"
            );
            worker.join().expect("run_cloud must not panic");

            // `_env_vars` (and `held_model`) drop here, cleaning up unconditionally — no
            // explicit teardown needed on the happy path either, so there is exactly one place
            // that removes these, not two.
        }
    }

    /// End-to-end proof against the REAL stack (real whisper.cpp, real Metal load, the actual
    /// cached model — no download, no network) that a startup backlog no longer trips
    /// [`ON_DEVICE_AUDIO_DROPPED_NOTICE`]. Same category as `recognizer.rs`'s own real-model
    /// tests: slow (a genuine ~1.6 GB model load), hardware-dependent, and skipped cleanly when
    /// the model is not cached locally (not part of `make ci`'s gate, which needs no model) —
    /// but a real, reproducible RED→GREEN result, not a synthetic mutation:
    ///
    /// **Captured RED against this exact test, pre-fix, during this investigation
    /// (2026-09-05):** `real model load+ready took 60.967132833s` (this machine was under real
    /// contention from other sessions at the time — 86akcfpcc's clean measurement is ~5.3s),
    /// immediately followed by `the on-device capture hand-off dropped 3309120 samples (480000
    /// currently retained)` and `engine_note() = Some("On-device transcription is running, but
    /// audio is being captured faster than it can be processed — some audio may not have
    /// reached the transcript.")` — the exact notice from the owner's report, fired from a
    /// recognizer that had not yet decoded a single frame.
    ///
    /// **What this test does and does not prove (corrected after Quinn's review, 86akd1jcc):
    /// this is a WIRING test, not a size/boundary test.** An earlier version of this comment
    /// claimed the backlog size here "pins the boundary" against a race with the recognition
    /// thread. Quinn proved that false by shrinking `selahcue_stt::audio::MAX_PCM_SAMPLES` to
    /// 100 (a 288,000× reduction) and observing this test stay green regardless. The real
    /// reason: `flush_pending_backlog` now runs BEFORE the capture loop and before any thread
    /// is spawned, so it drains this `FakeAudioSource` down to nothing in one call, and the
    /// resulting disclosure is governed by the boolean `flushed > 0` — not by comparing the
    /// backlog's size against any cap. There is no eviction, and no race, left for this test to
    /// exercise; that mechanism (a REAL `AudioHandoff` eviction, pre-flush) is what
    /// `a_startup_backlog_dump_can_trip_the_notice_before_any_decode_happens` covers
    /// deterministically, and the EXACT discarded-count accounting is what
    /// `flush_pending_backlog_discards_everything_queued_and_reports_the_exact_count` covers.
    /// What THIS test uniquely proves is that the real call site, in the real function, against
    /// a real loaded model, actually produces the disclosure — wiring, not magnitude. The
    /// backlog is still sized to `MAX_PCM_SAMPLES` (kept, with its relationship to
    /// `HANDOFF_MAX_SAMPLES` pinned at compile time beside that constant, and restated here at
    /// runtime) purely so this test's own narrative stays an honest stand-in for "the most a
    /// real mic's ring could have accumulated" — not because the test's pass/fail depends on it.
    #[test]
    fn a_real_cold_start_backlog_no_longer_trips_the_notice() {
        let _env_guard = crate::env_locked();
        let _state_guard = state_locked();
        use std::time::Instant;

        let model_path = match std::env::var_os("HOME") {
            Some(home) => std::path::PathBuf::from(home)
                .join("Library/Caches/selahcue/models/ggml-large-v3-turbo.bin"),
            None => {
                eprintln!("skipping a_real_cold_start_backlog_no_longer_trips_the_notice: no HOME");
                return;
            }
        };
        if !model_path.exists() {
            eprintln!(
                "skipping a_real_cold_start_backlog_no_longer_trips_the_notice: no cached \
                 model at {model_path:?}"
            );
            return;
        }
        // The pinned SHA-256 for `ggml-large-v3-turbo.bin` (`model.rs`) — verified independently
        // against this exact file via `shasum -a 256` during this investigation.
        let sha = "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69";
        std::env::set_var("SELAHCUE_STT_MODEL", &model_path);
        std::env::set_var("SELAHCUE_STT_MODEL_SHA256", sha);

        *status_lock(&ENGINE_NOTE) = None;
        clear_failure();

        struct BacklogSource {
            inner: selahcue_stt::audio::FakeAudioSource,
        }
        impl AudioSource for BacklogSource {
            fn label(&self) -> &str {
                "investigation"
            }
            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.inner.next_chunk()
            }
        }
        impl CaptureSource for BacklogSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }

        // Backlog sized to `PcmRing`'s own worst-case cap (`MAX_PCM_SAMPLES`) — a stand-in for
        // the most a real mic's ring could ever hand `flush_pending_backlog` in one call. As the
        // doc comment above explains, this test's PASS/FAIL does not depend on this exact size
        // (any nonzero backlog produces the same disclosure) — this runtime `assert!` restates,
        // beside this specific test, the same relationship pinned at compile time next to
        // `HANDOFF_MAX_SAMPLES`'s own definition, so this test's narrative cannot silently drift
        // from that pinned invariant either (the `capture_handoff.rs` convention: state a
        // premise both at the constant and beside the test that leans on it).
        let backlog_samples = selahcue_stt::audio::MAX_PCM_SAMPLES;
        assert!(
            backlog_samples > HANDOFF_MAX_SAMPLES.get(),
            "premise: this test's backlog must exceed HANDOFF_MAX_SAMPLES to be an honest \
             stand-in for PcmRing's worst case — see the const _: () = assert!(...) beside \
             HANDOFF_MAX_SAMPLES's definition, which pins the same relationship for good"
        );
        let mut inner = selahcue_stt::audio::FakeAudioSource::new();
        inner.push_chunk(AudioChunk::new(vec![0.0; backlog_samples], 48_000, 1));
        let source = BacklogSource { inner };

        let app = tauri::test::mock_app();
        let handle = app.handle().clone();
        handle.manage(crate::AppState {
            backend: crate::Backend::Local(crate::demo_shell()),
            deck: Mutex::new(crate::DeckWorkspace::demo()),
            library: Mutex::new(crate::DeckLibrary::load(None)),
            providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
            providers_db: None,
            secrets: crate::make_secret_store(),
            link_error: Mutex::new(None),
        });

        let stop_worker = Arc::new(AtomicBool::new(false));
        let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(64);
        let (ready_tx, ready_rx) = tokio::sync::oneshot::channel();

        let started = Instant::now();
        let sw = Arc::clone(&stop_worker);
        let app_worker = handle.clone();
        let worker = std::thread::spawn(move || {
            run_on_device(app_worker, source, sw, seg_tx, Some(ready_tx), None);
        });

        let runtime = tokio::runtime::Runtime::new().expect("build a tokio runtime");
        // Generous: a real ~1.6 GB model load competing with other work on a shared machine
        // measured 61s during this investigation (a clean run is ~5.3s per 86akcfpcc). This is
        // not part of `make ci` and only ever runs opt-in, locally, with the model cached.
        let ready = runtime
            .block_on(async { tokio::time::timeout(Duration::from_secs(150), ready_rx).await });
        eprintln!(
            "a_real_cold_start_backlog_no_longer_trips_the_notice: real model load+ready took \
             {:?}, ready={:?}",
            started.elapsed(),
            ready
        );
        assert!(
            matches!(ready, Ok(Ok(Ok(())))),
            "on-device must become ready against the real cached model: {ready:?}"
        );

        // A bounded real window before a clean stop — mirrors `run_on_device`'s own shutdown
        // contract. `source` is fully drained by the flush above by this point (see the doc
        // comment), so this is exercising clean shutdown against an exhausted source, not any
        // further capture/recognition interleaving.
        std::thread::sleep(Duration::from_millis(1_500));
        stop_worker.store(true, Ordering::Relaxed);
        worker.join().expect("run_on_device must not panic");

        let note = engine_note();
        eprintln!(
            "a_real_cold_start_backlog_no_longer_trips_the_notice: engine_note() = {note:?}, \
             last_failure() = {:?}",
            last_failure()
        );

        std::env::remove_var("SELAHCUE_STT_MODEL");
        std::env::remove_var("SELAHCUE_STT_MODEL_SHA256");
        *status_lock(&ENGINE_NOTE) = None;
        *status_lock(&PROVIDER_LABEL) = None;
        clear_failure();

        // THE assertion this test exists for. Pre-fix, this exact scenario reproducibly set
        // `engine_note()` to `ON_DEVICE_AUDIO_DROPPED_NOTICE` (see the captured RED result in
        // this test's doc comment) despite the recognizer never having decoded a frame.
        // REMOVING `flush_pending_backlog`'s call site in `run_on_device` (or reordering it
        // after `AudioHandoff::new`) must fail this test.
        assert_ne!(
            note.as_deref(),
            Some(ON_DEVICE_AUDIO_DROPPED_NOTICE),
            "a cold-start backlog must not be reported as an ongoing processing shortfall — got \
             {note:?}"
        );
        // Silence was rejected on review (Cody, HIGH-1): going quiet instead of wrong regresses
        // FR-120. This backlog (well over `PcmRing`'s own worst-case cap) WAS real audio lost
        // during preparation, and this session's `fallback` is `None`, so it must be disclosed
        // honestly via `AUDIO_LOST_DURING_STARTUP_NOTICE` — not silently, not with the old
        // wrong wording.
        assert_eq!(
            note.as_deref(),
            Some(AUDIO_LOST_DURING_STARTUP_NOTICE),
            "a genuine startup backlog must be disclosed honestly, not silently discarded — \
             got {note:?}"
        );
    }

    /// The other direction of Sana's M-1 (86akd1jcc review): a MID-SERVICE fallback
    /// (`fallback: Some(_)`, `ready_tx: None`) that also has to discard a startup-style backlog
    /// must disclose it with [`AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE`] — wording distinct from
    /// the plain startup case, alongside (not instead of) the fallback's own engine-change note
    /// — because the operator's on-screen state during a fallback is "Listening —
    /// transcribing", never "Preparing…", so startup wording would misdescribe what they were
    /// actually seeing.
    ///
    /// Deterministic and fast despite needing a real, successful model load: `stop_worker` is
    /// pre-set `true`, so `run_on_device`'s capture loop body never runs even once — the note
    /// this test asserts on is set synchronously, before any thread is spawned, so there is
    /// nothing here for a recognition-thread race to affect (contrast the backlog-eviction
    /// tests above and below, which need real capture-loop iterations and therefore real time).
    #[test]
    fn a_mid_service_fallback_discloses_audio_lost_during_the_engine_switch() {
        let _env_guard = crate::env_locked();
        let _state_guard = state_locked();

        let model_path = match std::env::var_os("HOME") {
            Some(home) => std::path::PathBuf::from(home)
                .join("Library/Caches/selahcue/models/ggml-large-v3-turbo.bin"),
            None => {
                eprintln!(
                    "skipping a_mid_service_fallback_discloses_audio_lost_during_the_engine_switch: no HOME"
                );
                return;
            }
        };
        if !model_path.exists() {
            eprintln!(
                "skipping a_mid_service_fallback_discloses_audio_lost_during_the_engine_switch: \
                 no cached model at {model_path:?}"
            );
            return;
        }
        let sha = "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69";
        std::env::set_var("SELAHCUE_STT_MODEL", &model_path);
        std::env::set_var("SELAHCUE_STT_MODEL_SHA256", sha);

        *status_lock(&ENGINE_NOTE) = None;
        clear_failure();

        struct OneChunkSource {
            inner: selahcue_stt::audio::FakeAudioSource,
        }
        impl AudioSource for OneChunkSource {
            fn label(&self) -> &str {
                "fallback-with-backlog"
            }
            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.inner.next_chunk()
            }
        }
        impl CaptureSource for OneChunkSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }
        // Any nonzero backlog suffices — the note fires on `flushed > 0` directly, with no
        // eviction/threshold mechanics involved (see `flush_pending_backlog`'s call site).
        let source = OneChunkSource {
            inner: selahcue_stt::audio::FakeAudioSource::with_chunks([AudioChunk::new(
                vec![0.0; 4_800],
                48_000,
                1,
            )]),
        };

        let app = tauri::test::mock_app();
        let handle = app.handle().clone();
        handle.manage(crate::AppState {
            backend: crate::Backend::Local(crate::demo_shell()),
            deck: Mutex::new(crate::DeckWorkspace::demo()),
            library: Mutex::new(crate::DeckLibrary::load(None)),
            providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
            providers_db: None,
            secrets: crate::make_secret_store(),
            link_error: Mutex::new(None),
        });

        const TEST_FALLBACK_NOTE: &str = "test: engine changed for this fixture";
        // `stop_worker` starts `true`: `run_on_device`'s capture-loop body never executes, so
        // the function returns as soon as setup (including the flush + note-setting under
        // test) finishes and the recognition thread sees stop+empty on its first iteration.
        let stop_worker = Arc::new(AtomicBool::new(true));
        let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(8);

        run_on_device(
            handle,
            source,
            stop_worker,
            seg_tx,
            None, // mid-service: the oneshot was already resolved by the (simulated) prior engine
            Some(FallbackContext {
                prior_failure: "test: prior engine stopped".to_string(),
                note: TEST_FALLBACK_NOTE,
            }),
        );

        let note = engine_note();
        std::env::remove_var("SELAHCUE_STT_MODEL");
        std::env::remove_var("SELAHCUE_STT_MODEL_SHA256");
        *status_lock(&ENGINE_NOTE) = None;
        *status_lock(&PROVIDER_LABEL) = None;
        clear_failure();

        // Both facts must be true at once: WHY the engine changed, AND that the switch lost
        // some audio — `append_engine_note`'s whole reason for existing is that a mid-service
        // engine-change note and a later audio-loss note can both be true about one session.
        let note = note.expect("a fallback with a real discarded backlog must set a note");
        assert!(
            note.contains(TEST_FALLBACK_NOTE),
            "must still carry the engine-change reason — got {note:?}"
        );
        assert!(
            note.contains(AUDIO_LOST_DURING_ENGINE_SWITCH_NOTICE),
            "REMOVING the `flushed > 0` branch under `Some(fb)` in run_on_device must fail this \
             test: a mid-service fallback that discards live, already-being-transcribed audio \
             must disclose it — got {note:?}"
        );
        assert!(
            !note.contains(AUDIO_LOST_DURING_STARTUP_NOTICE),
            "a mid-service fallback must use the engine-switch wording, never the startup \
             wording — got {note:?}"
        );
    }

    /// Cody's MEDIUM-2 (86akd1jcc review): before this test, nothing exercised
    /// `run_on_device`'s real capture loop with a genuine POST-ready overload and asserted
    /// [`ON_DEVICE_AUDIO_DROPPED_NOTICE`] actually fires — so a regression that silently
    /// disabled the on-device drop notice entirely (e.g. an inverted condition, a mutated
    /// `should_note_audio_drop`, a hand-off that stopped evicting) would have passed this
    /// suite green: "correctly absent" and "mechanism dead" read identically to every OTHER
    /// test here, all of which assert absence. The Cloud route already had this positive
    /// control (`a_lone_oversized_chunk_is_refused_and_still_sets_the_drop_notice`, PR #22);
    /// this closes the same gap for on-device.
    ///
    /// The source here starts EMPTY (so `flush_pending_backlog` has nothing to discard — this
    /// is deliberately NOT a startup-backlog scenario) and only begins supplying audio, in a
    /// flood far exceeding any real-time decode rate, AFTER `ready_rx` resolves — i.e. strictly
    /// after the engine is confirmed live and consuming. Any drop this test observes is
    /// therefore unambiguously a genuine post-ready throughput problem.
    #[test]
    fn a_genuine_post_ready_overload_still_trips_the_notice() {
        let _env_guard = crate::env_locked();
        let _state_guard = state_locked();

        let model_path = match std::env::var_os("HOME") {
            Some(home) => std::path::PathBuf::from(home)
                .join("Library/Caches/selahcue/models/ggml-large-v3-turbo.bin"),
            None => {
                eprintln!("skipping a_genuine_post_ready_overload_still_trips_the_notice: no HOME");
                return;
            }
        };
        if !model_path.exists() {
            eprintln!(
                "skipping a_genuine_post_ready_overload_still_trips_the_notice: no cached \
                 model at {model_path:?}"
            );
            return;
        }
        let sha = "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69";
        std::env::set_var("SELAHCUE_STT_MODEL", &model_path);
        std::env::set_var("SELAHCUE_STT_MODEL_SHA256", sha);

        *status_lock(&ENGINE_NOTE) = None;
        clear_failure();

        // Starts empty; `push_more` is how the test hands it a flood of audio only AFTER
        // `run_on_device` reports ready, so nothing here can be mistaken for a startup backlog.
        struct EmptyThenFloodSource {
            inner: Arc<Mutex<selahcue_stt::audio::FakeAudioSource>>,
        }
        impl AudioSource for EmptyThenFloodSource {
            fn label(&self) -> &str {
                "post-ready-overload"
            }
            fn next_chunk(&mut self) -> Option<AudioChunk> {
                self.inner
                    .lock()
                    .unwrap_or_else(|e| e.into_inner())
                    .next_chunk()
            }
        }
        impl CaptureSource for EmptyThenFloodSource {
            fn peak_level(&self) -> f32 {
                0.0
            }
        }

        let queue = Arc::new(Mutex::new(selahcue_stt::audio::FakeAudioSource::new()));
        let source = EmptyThenFloodSource {
            inner: Arc::clone(&queue),
        };

        let app = tauri::test::mock_app();
        let handle = app.handle().clone();
        handle.manage(crate::AppState {
            backend: crate::Backend::Local(crate::demo_shell()),
            deck: Mutex::new(crate::DeckWorkspace::demo()),
            library: Mutex::new(crate::DeckLibrary::load(None)),
            providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
            providers_db: None,
            secrets: crate::make_secret_store(),
            link_error: Mutex::new(None),
        });

        let stop_worker = Arc::new(AtomicBool::new(false));
        let (seg_tx, _seg_rx) = tokio::sync::mpsc::channel(64);
        let (ready_tx, ready_rx) = tokio::sync::oneshot::channel();

        let sw = Arc::clone(&stop_worker);
        let app_worker = handle.clone();
        let worker = std::thread::spawn(move || {
            run_on_device(app_worker, source, sw, seg_tx, Some(ready_tx), None);
        });

        let runtime = tokio::runtime::Runtime::new().expect("build a tokio runtime");
        let ready = runtime
            .block_on(async { tokio::time::timeout(Duration::from_secs(150), ready_rx).await });
        assert!(
            matches!(ready, Ok(Ok(Ok(())))),
            "on-device must become ready against the real cached model: {ready:?}"
        );
        // PREMISE: nothing was ever queued before readiness, so `flush_pending_backlog` had
        // nothing to discard and `AUDIO_LOST_DURING_STARTUP_NOTICE` must not be present — if it
        // were, a drop this test observes below could be the startup path firing, not the
        // genuine post-ready path this test claims to isolate.
        assert_eq!(
            engine_note(),
            None,
            "premise: an empty pre-ready source must produce no disclosure at all yet"
        );

        // NOW flood it — thousands of ~100ms chunks (48,000 mono samples each — 100ms of audio
        // at 48kHz) delivered as fast as the source thread can call `next_chunk` (no real-time
        // pacing, unlike an actual microphone), far outrunning any real decode rate this engine
        // could sustain, however fast. This is what makes the drop this test observes
        // unambiguous: no plausible recognizer, on any hardware, keeps up with this.
        {
            let mut q = queue.lock().unwrap_or_else(|e| e.into_inner());
            for _ in 0..5_000 {
                q.push_chunk(AudioChunk::new(vec![0.0; 4_800], 48_000, 1));
            }
        }

        std::thread::sleep(Duration::from_millis(2_000));
        stop_worker.store(true, Ordering::Relaxed);
        worker.join().expect("run_on_device must not panic");

        let note = engine_note();
        eprintln!("a_genuine_post_ready_overload_still_trips_the_notice: engine_note() = {note:?}");

        std::env::remove_var("SELAHCUE_STT_MODEL");
        std::env::remove_var("SELAHCUE_STT_MODEL_SHA256");
        *status_lock(&ENGINE_NOTE) = None;
        *status_lock(&PROVIDER_LABEL) = None;
        clear_failure();

        // THE positive control this test exists for: a genuine, unambiguous post-ready overload
        // must still trip `ON_DEVICE_AUDIO_DROPPED_NOTICE`. Without this test, a regression that
        // silently disabled the whole on-device drop-notice mechanism (e.g. an inverted
        // condition in `should_note_audio_drop`, or a hand-off that stopped evicting) would
        // read as "correctly absent" and pass every other test in this file, all of which
        // assert absence.
        assert_eq!(
            note.as_deref(),
            Some(ON_DEVICE_AUDIO_DROPPED_NOTICE),
            "a genuine, post-ready, real-time-outrunning overload must still trip the drop \
             notice — got {note:?} (if this is None, the on-device drop-notice mechanism may be \
             dead, not merely quiet)"
        );
    }
}
