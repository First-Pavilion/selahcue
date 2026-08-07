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

use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

use selahcue_core::transcript::ProviderSegment;
use selahcue_stt::audio::{AudioChunk, AudioSource, CpalSource};
use selahcue_stt::recognizer::{WhisperContext, WhisperRecognizer};
use selahcue_stt::{pump, EnergyVad, EngineConfig, FeedbackGuard, HardwareProbe, SttEngine};
use tauri::{AppHandle, Emitter, Manager};

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
const HANDOFF_MAX_SAMPLES: usize = 48_000 * 2 * 5;

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

/// A bounded hand-off of captured audio from the SOURCE thread (which owns the `!Send` cpal
/// stream) to the RECOGNITION thread. When the recognizer falls behind (a long decode), the
/// OLDEST buffered audio is dropped so the source thread never blocks and the recognizer stays
/// near the live edge — bounded to [`HANDOFF_MAX_SAMPLES`] (no-leak).
struct AudioHandoff {
    inner: Mutex<VecDeque<AudioChunk>>,
    max_samples: usize,
}

impl AudioHandoff {
    fn new(max_samples: usize) -> Self {
        AudioHandoff {
            inner: Mutex::new(VecDeque::new()),
            max_samples: max_samples.max(1),
        }
    }

    /// Append a chunk, evicting the oldest until the buffered sample count is within budget.
    fn push(&self, chunk: AudioChunk) {
        let mut q = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        q.push_back(chunk);
        let mut total: usize = q.iter().map(|c| c.samples.len()).sum();
        while total > self.max_samples && q.len() > 1 {
            if let Some(old) = q.pop_front() {
                total -= old.samples.len();
            }
        }
    }

    /// Take everything buffered (in order), leaving the hand-off empty.
    fn drain(&self) -> Vec<AudioChunk> {
        let mut q = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        q.drain(..).collect()
    }

    fn is_empty(&self) -> bool {
        self.inner
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .is_empty()
    }
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
            let path = selahcue_stt::fetch_model(&asset, &cache, |done, total| {
                if total > 0 {
                    let pct = (done.saturating_mul(100) / total) as u8;
                    // Advisory progress for the operator UI; ignore send errors (no window yet).
                    let _ = app.emit(PROGRESS_EVENT, DownloadProgress { done, total, pct });
                    eprintln!("SelahCue STT: downloading {} … {}%", asset.file_name, pct);
                }
            })?;
            // `fetch_model` already SHA-256-verified the file (cache hit OR post-download), so we
            // load WITHOUT re-hashing the multi-hundred-MB/GB file — that redundant hash was the
            // slow wait before the mic opened.
            WhisperRecognizer::load_unverified(&path, &selection)?
        }
    };
    cache_context(model_path, recognizer.context());
    Ok(recognizer)
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
        // Slow, fallible setup on the worker thread (not the executor): mic + model. Report the
        // outcome so the caller can surface it before we claim to be listening.
        //
        // Open the mic FIRST so the OS microphone-permission prompt appears immediately — before
        // the (first-run) model download/load, not after several seconds of it. The capture ring
        // is bounded (drops oldest), so audio buffered while the model loads is safely discarded;
        // draining begins on fresh audio once the recognizer is ready.
        let mut source = match CpalSource::new() {
            Ok(s) => s,
            Err(e) => {
                let _ = ready_tx.send(Err(format!("microphone unavailable: {e}")));
                return;
            }
        };
        let recognizer = match load_recognizer(&app_worker) {
            Ok(r) => r,
            Err(e) => {
                let _ = ready_tx.send(Err(e));
                return;
            }
        };
        eprintln!(
            "SelahCue STT: capturing from {} — listening.",
            source.label()
        );
        let _ = ready_tx.send(Ok(()));

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
        while !stop_worker.load(Ordering::Relaxed) {
            while let Some(chunk) = source.next_chunk() {
                handoff.push(chunk);
            }
            // A live mic level so "waiting for speech…" can show whether audio is arriving (peak 0
            // for seconds while speaking ⇒ mic/permission, not the UI).
            let pct = (source.peak_level() * 100.0).round().clamp(0.0, 100.0) as u8;
            let _ = app_worker.emit(LEVEL_EVENT, MicLevel { pct });
            std::thread::sleep(CAPTURE_INTERVAL);
        }
        // Stop requested: let the recognition thread drain the tail + flush, then join it. The mic
        // stream (`source`) is dropped when this thread returns, stopping capture.
        let _ = recog.join();
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

#[cfg(test)]
mod tests {
    use super::*;

    fn chunk(samples: usize) -> AudioChunk {
        AudioChunk::new(vec![0.0; samples], 48_000, 2)
    }

    fn buffered(h: &AudioHandoff) -> usize {
        h.inner
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .iter()
            .map(|c| c.samples.len())
            .sum()
    }

    #[test]
    fn audio_handoff_is_bounded_drop_oldest() {
        // No-leak: pushing far past the budget keeps the buffered sample count bounded by dropping
        // the OLDEST chunks — the recognizer always works from the most-recent audio (live edge).
        let max = 10_000;
        let h = AudioHandoff::new(max);
        for _ in 0..1_000 {
            h.push(chunk(1_000)); // 1,000,000 samples pushed into a 10,000-sample budget
        }
        assert!(
            buffered(&h) <= max,
            "buffered {} exceeds the bound {max}",
            buffered(&h)
        );
        assert!(!h.is_empty(), "keeps the most recent audio");
        assert!(!h.drain().is_empty());
        assert!(h.is_empty(), "drain empties the hand-off");
    }
}
