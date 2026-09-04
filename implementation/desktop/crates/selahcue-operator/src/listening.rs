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
fn emit_phase(app: &AppHandle, phase: selahcue_stt::DownloadPhase) {
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
fn load_recognizer(app: &AppHandle) -> Result<WhisperRecognizer, String> {
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
/// audio is actually arriving, regardless of which engine is consuming it.
fn emit_level(app: &AppHandle, source: &mut CpalSource) {
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
                    run_cloud(
                        app_worker,
                        source,
                        stop_worker,
                        seg_tx,
                        ready_tx,
                        providers_snapshot,
                    );
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
                run_on_device(app_worker, source, stop_worker, seg_tx, Some(ready_tx));
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

/// Run on-device (Whisper) transcription until stopped. The single on-device path: the initial
/// choice when on-device was actually selected, the immediate fallback when Cloud was selected
/// but is not usable, AND the mid-service fallback when a running Cloud session fails — all
/// three call this same function rather than three separate copies of it.
///
/// `ready_tx` is `Some` and consumed exactly once when this is the FIRST engine this capture
/// session tries (on-device chosen outright, or an immediate pre-stream Cloud fallback);
/// `None` when this is a mid-service handoff from an already-`Ok`-acknowledged Cloud session
/// (the caller already resolved the oneshot channel, which can only be sent once).
fn run_on_device(
    app_worker: AppHandle,
    mut source: CpalSource,
    stop_worker: Arc<AtomicBool>,
    seg_tx: tokio::sync::mpsc::Sender<ProviderSegment>,
    ready_tx: Option<tokio::sync::oneshot::Sender<Result<(), String>>>,
) {
    let recognizer = match load_recognizer(&app_worker) {
        Ok(r) => r,
        Err(e) => {
            record_failure(e.clone());
            if let Some(tx) = ready_tx {
                let _ = tx.send(Err(e));
            }
            return;
        }
    };
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
            *status_lock(&ENGINE_NOTE) = Some(ON_DEVICE_AUDIO_DROPPED_NOTICE.to_string());
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

/// Run Cloud (Deepgram) transcription until it fails, is stopped, or the running session is
/// terminal, falling back to `run_on_device` in every case that is not a clean operator-driven
/// stop. Behind `cloud-stt`: everything it touches from `selahcue-stt-cloud` beyond `readiness`
/// requires the `deepgram` feature.
///
/// This function never blocks the caller waiting on the network: `CloudSttSession::start`
/// returns before the socket is open (it runs on its own thread), and every iteration of the
/// loop below is bounded local work — draining the mic, pushing into the bounded `AudioRing`,
/// draining the bounded `SegmentQueue`, and one non-blocking status read.
#[cfg(feature = "cloud-stt")]
fn run_cloud(
    app_worker: AppHandle,
    mut source: CpalSource,
    stop_worker: Arc<AtomicBool>,
    seg_tx: tokio::sync::mpsc::Sender<ProviderSegment>,
    ready_tx: tokio::sync::oneshot::Sender<Result<(), String>>,
    providers_snapshot: selahcue_core::providers::ProvidersConfig,
) {
    use selahcue_stt_cloud::session::{StreamAuthorization, StreamParams};
    use selahcue_stt_cloud::transport::{CloudSttSession, SessionConfig};
    use selahcue_stt_cloud::{
        developer_credential_from_env, AudioChunk as CloudAudioChunk, AudioRing,
        CloudTranscriptProvider, SegmentQueue, SessionStatus, DEGRADED_FALLBACK_NOTICE,
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

    // `TranscriptionRoute::decide` already checked `may_stream_cloud_audio()` a moment ago, but
    // config can change between that decision and here (the operator flips a toggle mid-start)
    // — re-proving it at the point audio would actually stream, rather than trusting a decision
    // made a few lines of code earlier, is what makes "streaming is unreachable without
    // consent" hold at the point that matters (mirrors `selahcue-stt-cloud`'s own
    // `StreamAuthorization` invariant).
    let authorization = match StreamAuthorization::from_config(&providers_snapshot) {
        Ok(a) => a,
        Err(e) => {
            record_failure(format!("cloud transcription not authorized: {e}"));
            run_on_device(app_worker, source, stop_worker, seg_tx, Some(ready_tx));
            return;
        }
    };
    let credential = match developer_credential_from_env() {
        Ok(c) => c,
        Err(e) => {
            record_failure(format!("cloud transcription credential unavailable: {e}"));
            run_on_device(app_worker, source, stop_worker, seg_tx, Some(ready_tx));
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
    // guard is what stands between this branch and an unbounded reconnect loop (V-2).
    let config = SessionConfig::default();

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
            run_on_device(app_worker, source, stop_worker, seg_tx, Some(ready_tx));
            return;
        }
    };

    let mut provider = CloudTranscriptProvider::new(queue.clone(), &params);
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

    // Both `handoff` (shared capture→consumer type; drops the OLDEST raw audio if this loop
    // ever fell behind draining the mic — it does not in practice, since nothing here blocks)
    // and `audio_ring` (Deepgram-specific, downstream of resampling; drops OLDEST if the socket
    // falls behind) have their own drop-oldest capacity bound. Both are honest capacity
    // management, not bugs, but both are SILENT ones otherwise — tracked so the console can say
    // so rather than presenting a transcript that looks complete while it is not (the same
    // honesty rule this ticket already applies to which engine is running). Sticky for the rest
    // of THIS session once true — a flicker back to "no drops yet" the moment either buffer
    // catches up would be easy to miss and would read as reassurance about audio already lost.
    let mut audio_dropped_ever = false;

    loop {
        if stop_worker.load(Ordering::Relaxed) {
            // Clean operator-driven stop. `stop()` asks Deepgram to flush first (bounded —
            // `SHUTDOWN_GRACE`) so the last sentence of a sermon is not lost.
            session.stop();
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
        emit_level(&app_worker, &mut source);

        if should_note_audio_drop(
            handoff.dropped() + audio_ring.dropped_for_bound(),
            audio_dropped_ever,
        ) {
            audio_dropped_ever = true;
            eprintln!(
                "SelahCue STT: audio was dropped before reaching Deepgram (capture hand-off: {} \
                 samples dropped, {} currently retained; Deepgram ring: {} bytes dropped) — the \
                 pipeline is not keeping up.",
                handoff.dropped(),
                handoff.retained_samples(),
                audio_ring.dropped_for_bound()
            );
            *status_lock(&ENGINE_NOTE) = Some(AUDIO_DROPPED_NOTICE.to_string());
        }

        // Drain whatever the socket has queued so far — never blocks (see `CloudTranscriptProvider::poll`).
        pump(&mut provider, |seg| {
            let _ = seg_tx.try_send(seg);
        });

        if status.get().is_terminal() {
            // The session gave up (bad credential, exhausted retries, or a defect) rather than
            // being asked to stop. Hand off to on-device with the SAME open mic — no re-prompt,
            // no gap while a new stream opens — and say so on the console (FR-135 / FR-120).
            record_failure(format!("cloud transcription stopped: {:?}", status.get()));
            *status_lock(&ENGINE_NOTE) = Some(DEGRADED_FALLBACK_NOTICE.to_string());
            run_on_device(app_worker, source, stop_worker, seg_tx, None);
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

    // `AudioHandoff`'s own bounded-memory tests (retained-sample bound, exact drop count, a
    // benign positive control) now live with the type, in `capture_handoff.rs` — shared with
    // the Cloud route rather than duplicated here.

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

    #[cfg(feature = "cloud-stt")]
    mod cloud_stt {
        use super::super::pcm_i16_from_f32;

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
    }
}
