//! On-device speech-to-text **source** for the live transcript (feature `stt`).
//!
//! When the operator presses "Start listening", [`start`] spins up a background worker that
//! captures the microphone (`cpal`), transcribes on-device (`whisper.cpp`), and pumps each
//! recognised segment into the shared controller via [`OperatorShell::ingest_transcript`] —
//! the exact path that runs exact + fuzzy scripture detection and populates the transcript /
//! detection panels. The worker is out-of-band from render (its own thread); the audience
//! output never waits on it.
//!
//! Compiled only under `stt`, which pulls the native whisper/cpal toolchain — so the default
//! operator build (and CI's compile-check) needs neither. The model is resolved from the
//! environment and **integrity-verified before load** (FR-156 / ADR-0012); no model ships in
//! the binary (ADR-0012 defers delivery). Real accuracy/latency are spike-gated (S8/S11).

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use selahcue_app::OperatorShell;
// `CpalSource`/`WhisperRecognizer` are re-exported into their (feature-gated) modules, not at
// the crate root — import them by their module paths.
use selahcue_stt::audio::CpalSource;
use selahcue_stt::recognizer::WhisperRecognizer;
use selahcue_stt::{pump, EnergyVad, EngineConfig, FeedbackGuard, HardwareProbe, SttEngine};

/// Poll cadence for draining captured audio → recognition → ingest. Out-of-band from render.
const PUMP_INTERVAL: Duration = Duration::from_millis(200);

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

/// Start on-device transcription into `shell`. Idempotent (a second call while listening is a
/// no-op). Configuration failures (missing / mismatched model) and microphone-open failures
/// both surface as an error **before** we claim to be listening — the UI never shows a
/// phantom "listening" state or a fabricated transcript.
pub fn start(shell: OperatorShell) -> Result<(), String> {
    if is_listening() {
        return Ok(());
    }

    // Resolve + integrity-verify + load the model BEFORE taking the worker lock: the
    // multi-hundred-MB SHA-256 + whisper.cpp load is slow and must not block
    // `is_listening()` / `stop()`. No model is bundled (ADR-0012).
    let model_path = std::env::var("SELAHCUE_STT_MODEL").map_err(|_| {
        "on-device STT needs a model: set SELAHCUE_STT_MODEL to the whisper model file path"
            .to_string()
    })?;
    let expected_sha = std::env::var("SELAHCUE_STT_MODEL_SHA256").map_err(|_| {
        "set SELAHCUE_STT_MODEL_SHA256 to the model's pinned SHA-256 (integrity gate, FR-156)"
            .to_string()
    })?;
    let selection = HardwareProbe::detect().select_model();
    // Verifies before load; a hash mismatch refuses to load.
    let recognizer = WhisperRecognizer::load(Path::new(&model_path), &expected_sha, &selection)?;

    let mut guard = worker_lock();
    if guard.is_some() {
        return Ok(()); // raced with another start
    }

    // The cpal input stream is opened on the worker thread (its handle is not `Send` on
    // CoreAudio/WASAPI). The worker reports whether the mic opened, so a capture failure
    // surfaces here rather than as a phantom "listening" state.
    let (ready_tx, ready_rx) = std::sync::mpsc::channel::<Result<(), String>>();
    let stop = Arc::new(AtomicBool::new(false));
    let stop_worker = Arc::clone(&stop);
    let handle = std::thread::spawn(move || {
        let mut source = match CpalSource::new() {
            Ok(s) => {
                let _ = ready_tx.send(Ok(()));
                s
            }
            Err(e) => {
                let _ = ready_tx.send(Err(format!("microphone unavailable: {e}")));
                return;
            }
        };
        let (mut engine, mut provider) = SttEngine::build(
            EngineConfig::default(),
            Box::new(EnergyVad::new()),
            Box::new(recognizer),
            FeedbackGuard::new(),
        );
        while !stop_worker.load(Ordering::Relaxed) {
            engine.drain_source(&mut source);
            pump(&mut provider, |seg| {
                shell.ingest_transcript(&seg.text, seg.start_ms, seg.end_ms);
            });
            std::thread::sleep(PUMP_INTERVAL);
        }
        // Flush any tail utterance on stop, then drain it.
        engine.flush();
        pump(&mut provider, |seg| {
            shell.ingest_transcript(&seg.text, seg.start_ms, seg.end_ms);
        });
    });

    // Wait for the mic to open (fast) before recording the worker as "listening".
    match ready_rx.recv() {
        Ok(Ok(())) => {
            *guard = Some(Worker {
                stop,
                handle: Some(handle),
            });
            Ok(())
        }
        Ok(Err(e)) => {
            let _ = handle.join();
            Err(e)
        }
        Err(_) => {
            let _ = handle.join();
            Err("STT capture worker failed to start".to_string())
        }
    }
}

/// Stop the capture worker (idempotent). Takes the worker out of the slot BEFORE joining, so
/// the worker lock is never held across the join; the worker thread only locks the controller
/// (via `ingest_transcript`), never this slot — no lock-ordering cycle.
pub fn stop() {
    let worker = worker_lock().take();
    if let Some(mut w) = worker {
        w.stop.store(true, Ordering::Relaxed);
        if let Some(handle) = w.handle.take() {
            let _ = handle.join();
        }
    }
}
