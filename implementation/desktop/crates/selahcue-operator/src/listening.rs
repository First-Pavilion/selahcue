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

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use selahcue_core::transcript::ProviderSegment;
use selahcue_stt::audio::{AudioSource, CpalSource};
use selahcue_stt::recognizer::WhisperRecognizer;
use selahcue_stt::{pump, EnergyVad, EngineConfig, FeedbackGuard, HardwareProbe, SttEngine};
use tauri::{AppHandle, Emitter, Manager};

/// Poll cadence for draining captured audio → recognition → ingest. Out-of-band from render.
const PUMP_INTERVAL: Duration = Duration::from_millis(200);

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

/// Lock the worker slot, recovering from a poisoned lock (a prior panic must not make the
/// worker permanently unstoppable — recover the guard and continue).
fn worker_lock() -> std::sync::MutexGuard<'static, Option<Worker>> {
    WORKER.lock().unwrap_or_else(|e| e.into_inner())
}

/// Whether a capture worker is currently running.
pub fn is_listening() -> bool {
    worker_lock().is_some()
}

/// Resolve the model (cache/download, integrity-verified) and load the recognizer. Runs on
/// the worker thread (it can be slow: a large SHA-256 + whisper.cpp load, or a first-run
/// download). An explicit `SELAHCUE_STT_MODEL` path overrides the download.
fn load_recognizer(app: &AppHandle) -> Result<WhisperRecognizer, String> {
    let selection = HardwareProbe::detect().select_model();
    let (model_path, expected_sha) = match std::env::var("SELAHCUE_STT_MODEL") {
        Ok(path) => {
            let sha = std::env::var("SELAHCUE_STT_MODEL_SHA256").map_err(|_| {
                "SELAHCUE_STT_MODEL is set — also set SELAHCUE_STT_MODEL_SHA256 (integrity gate, FR-156)"
                    .to_string()
            })?;
            (PathBuf::from(path), sha)
        }
        Err(_) => {
            let asset = selection.model.asset();
            let cache = selahcue_stt::default_cache_dir();
            eprintln!(
                "SelahCue STT: resolving model {} (~{} MB) in {}…",
                asset.file_name,
                asset.size_bytes / 1_000_000,
                cache.display()
            );
            let path = selahcue_stt::fetch_model(&asset, &cache, |done, total| {
                if total > 0 {
                    let pct = (done.saturating_mul(100) / total) as u8;
                    // Advisory progress for the operator UI; ignore send errors (no window yet).
                    let _ = app.emit(PROGRESS_EVENT, DownloadProgress { done, total, pct });
                    eprintln!("SelahCue STT: downloading {} … {}%", asset.file_name, pct);
                }
            })?;
            (path, asset.sha256.to_string())
        }
    };
    WhisperRecognizer::load(&model_path, &expected_sha, &selection)
}

/// Start on-device transcription into `app`'s controller (local or wire-connected host).
/// Returns a receiver that resolves once the worker has loaded the model and opened the mic
/// (`Ok`) or failed (`Err`) — so the caller can surface configuration / download / microphone
/// failures without blocking, and without a phantom "listening" state.
pub fn start(app: AppHandle) -> tokio::sync::oneshot::Receiver<Result<(), String>> {
    let (ready_tx, ready_rx) = tokio::sync::oneshot::channel::<Result<(), String>>();
    {
        let guard = worker_lock();
        if guard.is_some() {
            let _ = ready_tx.send(Ok(())); // already listening — idempotent
            return ready_rx;
        }
    }

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
        // Slow, fallible setup on the worker thread (not the executor): model + mic. Report
        // the outcome so the caller can surface it before we claim to be listening.
        let recognizer = match load_recognizer(&app_worker) {
            Ok(r) => r,
            Err(e) => {
                let _ = ready_tx.send(Err(e));
                return;
            }
        };
        let mut source = match CpalSource::new() {
            Ok(s) => s,
            Err(e) => {
                let _ = ready_tx.send(Err(format!("microphone unavailable: {e}")));
                return;
            }
        };
        eprintln!(
            "SelahCue STT: capturing from {} — listening.",
            source.label()
        );
        let _ = ready_tx.send(Ok(()));

        let (mut engine, mut provider) = SttEngine::build(
            // Stream interims (~0.8 s cadence) so recognised words appear live in the operator's
            // transcript instead of only when the utterance closes. (Cost grows with the open
            // buffer; the 10 s force-close bounds it — a sliding-window pass is a perf follow-up.)
            EngineConfig {
                interim_interval_frames: 40,
                ..EngineConfig::default()
            },
            Box::new(EnergyVad::new()),
            Box::new(recognizer),
            FeedbackGuard::new(),
        );
        // Throttle the level readout to ~4/sec (every LEVEL_EVERY pump ticks); the callback
        // keeps the running peak between reads so nothing is missed.
        const LEVEL_EVERY: u32 = 1;
        let mut tick: u32 = 0;
        while !stop_worker.load(Ordering::Relaxed) {
            engine.drain_source(&mut source);
            pump(&mut provider, |seg| {
                let _ = seg_tx.try_send(seg); // bounded; drop under backpressure, never block
            });
            // Emit a live mic level so "waiting for speech…" can show whether audio is even
            // arriving (peak 0 for seconds while speaking ⇒ mic/permission, not the UI).
            tick = tick.wrapping_add(1);
            if tick % LEVEL_EVERY == 0 {
                let pct = (source.peak_level() * 100.0).round().clamp(0.0, 100.0) as u8;
                let _ = app_worker.emit(LEVEL_EVENT, MicLevel { pct });
            }
            std::thread::sleep(PUMP_INTERVAL);
        }
        engine.flush();
        pump(&mut provider, |seg| {
            let _ = seg_tx.try_send(seg);
        });
        // `seg_tx` drops here → the drain task ends.
    });

    *worker_lock() = Some(Worker {
        stop,
        handle: Some(handle),
    });
    ready_rx
}

/// Stop the capture worker (idempotent). Takes the worker out of the slot BEFORE joining, so
/// the worker lock is never held across the join; the worker thread only touches the segment
/// channel and the controller, never this slot — no lock-ordering cycle. Joining the worker
/// drops its `seg_tx`, which ends the drain task.
pub fn stop() {
    let worker = worker_lock().take();
    if let Some(mut w) = worker {
        w.stop.store(true, Ordering::Relaxed);
        if let Some(handle) = w.handle.take() {
            let _ = handle.join();
        }
    }
}
