//! Throwaway measurement harness for ClickUp 86akcgmuh (10 s force-close repetition loops).
//! NOT part of the repo; nothing here is proposed for merge.
//!
//! Modes:
//!   extract <audio_manifest.json> <out_windows.json>
//!       Run the REAL `SttEngine` (EnergyVad, default EngineConfig: 300 ms hangover, 10 s
//!       force-close) over each recording with a capturing recognizer, and emit every FINAL the
//!       engine would decode, flagging the force-closed ones (len == max_utterance_samples).
//!   decode <slices.json> <out.jsonl> <cfg[,cfg...]> [config-major|slice-major]
//!       Decode each slice with each config against the real large-v3-turbo model.
//!
//! Config spec: '+'-joined modifiers on top of the production params
//! (Greedy best_of 1, audio_ctx 512, single_segment true, whisper.cpp defaults otherwise):
//!   prod | ss0 | unc | ctxN | nofb | entNN (entropy_thold NN/10) | lpNN (logprob_thold -NN/10)
//!   | beamN | bestN | nots | ngramN (no-repeat text-token n-gram ban) | padN (append N ms of
//!   silence) | cutqN (cut at the quietest 20 ms frame within the last N ms) | maxtokN | inst
//!   (install the counting-only logits callback)

use serde_json::{json, Value};
use std::collections::HashMap;
use std::ffi::{c_int, c_void};
use std::io::{Read, Write};
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::Instant;

use selahcue_stt::model::{verify_model, HardwareProbe, WhisperModel};
use selahcue_stt::{
    AudioChunk, EnergyVad, EngineConfig, FeedbackGuard, RecognizedSegment, Recognizer, SttEngine,
};
use whisper_rs::{WhisperSysContext, WhisperSysState, WhisperTokenData};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

const SR: usize = 16_000;

fn read_wav(path: &Path) -> Vec<f32> {
    let mut bytes = Vec::new();
    std::fs::File::open(path)
        .and_then(|mut f| f.read_to_end(&mut bytes))
        .unwrap_or_else(|e| panic!("read {path:?}: {e}"));
    assert_eq!(&bytes[0..4], b"RIFF");
    assert_eq!(&bytes[8..12], b"WAVE");
    let mut i = 12usize;
    while i + 8 <= bytes.len() {
        let id = &bytes[i..i + 4];
        let size =
            u32::from_le_bytes([bytes[i + 4], bytes[i + 5], bytes[i + 6], bytes[i + 7]]) as usize;
        let body = i + 8;
        if id == b"data" {
            let end = (body + size).min(bytes.len());
            let mut out = Vec::with_capacity(size / 2);
            let mut j = body;
            while j + 1 < end {
                out.push(i16::from_le_bytes([bytes[j], bytes[j + 1]]) as f32 / i16::MAX as f32);
                j += 2;
            }
            return out;
        }
        i = body + size + (size % 2);
    }
    panic!("no data chunk in {path:?}");
}

// ---------------------------------------------------------------- extract mode

#[derive(Clone)]
struct Capture(Arc<Mutex<Vec<(u64, u64, usize)>>>);

impl Recognizer for Capture {
    fn label(&self) -> &str {
        "capture"
    }
    fn transcribe(&mut self, samples: &[f32], s: u64, e: u64) -> Vec<RecognizedSegment> {
        self.0.lock().unwrap().push((s, e, samples.len()));
        Vec::new()
    }
}

fn extract(manifest: &str, out: &str) {
    let recs: Vec<Value> = serde_json::from_str(&std::fs::read_to_string(manifest).unwrap()).unwrap();
    let max = EngineConfig::default().max_utterance_samples;
    let mut windows = Vec::new();
    let (mut n_final, mut n_forced) = (0, 0);
    for r in &recs {
        let wav = r["wav"].as_str().unwrap();
        let samples = read_wav(Path::new(wav));
        let cap = Capture(Arc::new(Mutex::new(Vec::new())));
        let (mut engine, _provider) = SttEngine::build(
            EngineConfig::default(),
            Box::new(EnergyVad::new()),
            Box::new(cap.clone()),
            FeedbackGuard::new(),
        );
        for chunk in samples.chunks(SR / 10) {
            engine.process(&AudioChunk::new(chunk.to_vec(), SR as u32, 1));
        }
        engine.flush();
        for &(s, _e, len) in cap.0.lock().unwrap().iter() {
            n_final += 1;
            let forced = len >= max;
            if forced {
                n_forced += 1;
            }
            let start = (s as usize) * SR / 1000;
            windows.push(json!({
                "id": format!("{}@{}", r["id"].as_str().unwrap(), start),
                "rec": r["id"], "wav": wav, "start": start, "len": len, "forced": forced,
            }));
        }
    }
    eprintln!("finals: {n_final}, force-closed: {n_forced}");
    std::fs::write(out, serde_json::to_string_pretty(&windows).unwrap()).unwrap();
}

// ---------------------------------------------------------------- decode mode

#[derive(Debug, Clone)]
struct Cfg {
    name: String,
    ss: bool,
    audio_ctx: Option<i32>,
    temp_inc: Option<f32>,
    entropy: Option<f32>,
    logprob: Option<f32>,
    beam: Option<i32>,
    best_of: i32,
    no_ts: bool,
    ngram: usize,
    pad_ms: usize,
    cutq_ms: usize,
    max_tokens: Option<i32>,
    instrument: bool,
}

fn num(s: &str, prefix: &str) -> Option<f32> {
    s.strip_prefix(prefix).and_then(|r| r.parse::<f32>().ok())
}

fn parse_cfg(spec: &str) -> Cfg {
    let mut c = Cfg {
        name: spec.to_string(),
        ss: true,
        audio_ctx: Some(512),
        temp_inc: None,
        entropy: None,
        logprob: None,
        beam: None,
        best_of: 1,
        no_ts: false,
        ngram: 0,
        pad_ms: 0,
        cutq_ms: 0,
        max_tokens: None,
        instrument: false,
    };
    for m in spec.split('+') {
        match m {
            "prod" => {}
            "ss0" => c.ss = false,
            "unc" => c.audio_ctx = None,
            "nofb" => c.temp_inc = Some(0.0),
            "nots" => c.no_ts = true,
            "inst" => c.instrument = true,
            _ if m.starts_with("ctx") => c.audio_ctx = Some(num(m, "ctx").unwrap() as i32),
            _ if m.starts_with("ent") => c.entropy = Some(num(m, "ent").unwrap() / 10.0),
            _ if m.starts_with("lp") => c.logprob = Some(-num(m, "lp").unwrap() / 10.0),
            _ if m.starts_with("beam") => c.beam = Some(num(m, "beam").unwrap() as i32),
            _ if m.starts_with("best") => c.best_of = num(m, "best").unwrap() as i32,
            _ if m.starts_with("ngram") => {
                c.ngram = num(m, "ngram").unwrap() as usize;
                c.instrument = true;
            }
            _ if m.starts_with("pad") => c.pad_ms = num(m, "pad").unwrap() as usize,
            _ if m.starts_with("cutq") => c.cutq_ms = num(m, "cutq").unwrap() as usize,
            _ if m.starts_with("maxtok") => c.max_tokens = Some(num(m, "maxtok").unwrap() as i32),
            _ => panic!("unknown modifier {m:?} in {spec:?}"),
        }
    }
    c
}

/// Per-call state for the logits callback: counts decode passes (a call with zero tokens so far
/// is the start of a new temperature pass) and optionally bans repeated text-token n-grams.
struct FilterState {
    eot: i32,
    ngram: usize,
    passes: u32,
    bans: u32,
}

unsafe extern "C" fn filter_cb(
    _ctx: *mut WhisperSysContext,
    _state: *mut WhisperSysState,
    tokens: *const WhisperTokenData,
    n_tokens: c_int,
    logits: *mut f32,
    user_data: *mut c_void,
) {
    let fs = &mut *(user_data as *mut FilterState);
    if n_tokens == 0 {
        fs.passes += 1;
        return;
    }
    let n = fs.ngram;
    if n < 2 {
        return;
    }
    let toks = std::slice::from_raw_parts(tokens, n_tokens as usize);
    let text: Vec<i32> = toks.iter().map(|t| t.id).filter(|&id| id < fs.eot).collect();
    if text.len() < n - 1 {
        return;
    }
    let ctx_start = text.len() - (n - 1);
    let ctxw = &text[ctx_start..];
    let mut banned = false;
    for i in 0..ctx_start {
        if &text[i..i + n - 1] == ctxw {
            *logits.add(text[i + n - 1] as usize) = f32::NEG_INFINITY;
            banned = true;
        }
    }
    if banned {
        fs.bans += 1;
    }
}

/// Index (in samples) to cut at: the start of the quietest 20 ms frame within the last
/// `within_ms` of the window (RMS energy). Returns the full length if within_ms == 0.
fn quiet_cut(samples: &[f32], within_ms: usize) -> usize {
    if within_ms == 0 {
        return samples.len();
    }
    let frame = SR / 50;
    let lo = samples.len().saturating_sub(within_ms * SR / 1000);
    let mut best = (f32::INFINITY, samples.len());
    let mut i = lo / frame * frame;
    while i + frame <= samples.len() {
        let e: f32 = samples[i..i + frame].iter().map(|x| x * x).sum::<f32>() / frame as f32;
        if e < best.0 {
            best = (e, i);
        }
        i += frame;
    }
    best.1.max(SR) // never below 1 s
}

struct DecodeOut {
    text: String,
    ids: Vec<i32>,
    plogs: Vec<f32>,
    ms: f64,
    passes: u32,
    bans: u32,
    used_len: usize,
}

fn decode(ctx: &WhisperContext, cfg: &Cfg, window: &[f32], threads: i32, eot: i32) -> DecodeOut {
    let cut = quiet_cut(window, cfg.cutq_ms);
    let mut samples: Vec<f32> = window[..cut].to_vec();
    samples.extend(std::iter::repeat(0.0f32).take(cfg.pad_ms * SR / 1000));
    let used_len = samples.len();

    let started = Instant::now();
    let mut state = ctx.create_state().expect("state");
    let strategy = match cfg.beam {
        Some(b) => SamplingStrategy::BeamSearch { beam_size: b, patience: -1.0 },
        None => SamplingStrategy::Greedy { best_of: cfg.best_of },
    };
    let mut params = FullParams::new(strategy);
    params.set_n_threads(threads);
    params.set_translate(false);
    params.set_print_special(false);
    params.set_print_progress(false);
    params.set_print_realtime(false);
    params.set_print_timestamps(false);
    if let Some(a) = cfg.audio_ctx {
        params.set_audio_ctx(a);
    }
    params.set_single_segment(cfg.ss);
    if let Some(t) = cfg.temp_inc {
        params.set_temperature_inc(t);
    }
    if let Some(e) = cfg.entropy {
        params.set_entropy_thold(e);
    }
    if let Some(l) = cfg.logprob {
        params.set_logprob_thold(l);
    }
    if cfg.no_ts {
        params.set_no_timestamps(true);
    }
    if let Some(m) = cfg.max_tokens {
        params.set_max_tokens(m);
    }
    let mut fs = FilterState { eot, ngram: cfg.ngram, passes: 0, bans: 0 };
    if cfg.instrument {
        unsafe {
            params.set_filter_logits_callback(Some(filter_cb));
            params.set_filter_logits_callback_user_data(&mut fs as *mut FilterState as *mut c_void);
        }
    }
    state.full(params, &samples).expect("full");
    let n = state.full_n_segments().unwrap_or(0);
    let mut text = String::new();
    let (mut ids, mut plogs) = (Vec::new(), Vec::new());
    for s in 0..n {
        if let Ok(t) = state.full_get_segment_text(s) {
            let t = t.trim();
            if !t.is_empty() {
                if !text.is_empty() {
                    text.push(' ');
                }
                text.push_str(t);
            }
        }
        let nt = state.full_n_tokens(s).unwrap_or(0);
        for k in 0..nt {
            if let Ok(d) = state.full_get_token_data(s, k) {
                ids.push(d.id);
                plogs.push(d.plog);
            }
        }
    }
    let ms = started.elapsed().as_secs_f64() * 1000.0;
    DecodeOut { text, ids, plogs, ms, passes: fs.passes, bans: fs.bans, used_len }
}

fn run_decode(slices_path: &str, out_path: &str, cfgs: &str, order: &str) {
    let slices: Vec<Value> =
        serde_json::from_str(&std::fs::read_to_string(slices_path).unwrap()).unwrap();
    let cfgs: Vec<Cfg> = cfgs.split(',').map(parse_cfg).collect();

    let asset = WhisperModel::LargeV3Turbo.asset();
    let home = std::env::var("HOME").unwrap();
    let model = Path::new(&home).join("Library/Caches/selahcue/models").join(asset.file_name);
    if std::env::var("SPIKE_SKIP_VERIFY").is_err() {
        verify_model(&model, asset.sha256).expect("model must match the pinned SHA-256");
    }
    let ctx = WhisperContext::new_with_params(model.to_str().unwrap(), WhisperContextParameters::default())
        .expect("load");
    let eot = ctx.token_eot();
    // Same thread count production uses (model.rs production selection: probe - 1, min 1).
    let threads = HardwareProbe::detect().threads.saturating_sub(1).max(1) as i32;
    eprintln!("threads={threads} eot={eot} slices={} cfgs={}", slices.len(), cfgs.len());

    let mut audio: HashMap<String, Vec<f32>> = HashMap::new();
    let mut get = |wav: &str| -> Vec<f32> {
        audio.entry(wav.to_string()).or_insert_with(|| read_wav(Path::new(wav))).clone()
    };
    let window_of = |s: &Value, get: &mut dyn FnMut(&str) -> Vec<f32>| -> Vec<f32> {
        let all = get(s["wav"].as_str().unwrap());
        let start = s["start"].as_u64().unwrap() as usize;
        let len = s["len"].as_u64().unwrap() as usize;
        all[start..(start + len).min(all.len())].to_vec()
    };

    let mut out = std::fs::File::create(out_path).unwrap();
    let mut emit = |s: &Value, cfg: &Cfg, d: &DecodeOut, out: &mut std::fs::File| {
        let line = json!({
            "slice": s["id"], "cfg": cfg.name, "text": d.text, "ids": d.ids, "plogs": d.plogs,
            "ms": d.ms, "passes": d.passes, "bans": d.bans, "used_len": d.used_len,
            "len": s["len"],
        });
        writeln!(out, "{line}").unwrap();
    };

    let warm = |cfg: &Cfg, get: &mut dyn FnMut(&str) -> Vec<f32>| {
        let w = window_of(&slices[0], get);
        for _ in 0..2 {
            let _ = decode(&ctx, cfg, &w, threads, eot);
        }
    };

    if order == "slice-major" {
        for cfg in &cfgs {
            warm(cfg, &mut get);
        }
        for (i, s) in slices.iter().enumerate() {
            let w = window_of(s, &mut get);
            for cfg in &cfgs {
                let d = decode(&ctx, cfg, &w, threads, eot);
                emit(s, cfg, &d, &mut out);
            }
            if i % 20 == 0 {
                eprintln!("slice {i}/{}", slices.len());
            }
        }
    } else {
        for cfg in &cfgs {
            warm(cfg, &mut get);
            let t0 = Instant::now();
            for s in slices.iter() {
                let w = window_of(s, &mut get);
                let d = decode(&ctx, cfg, &w, threads, eot);
                emit(s, cfg, &d, &mut out);
            }
            eprintln!("cfg {} done in {:.1}s", cfg.name, t0.elapsed().as_secs_f64());
        }
    }
}

// ---------------------------------------------------------------- paced mode
//
// A real-time-paced end-to-end run, shaped like production's listening.rs: a producer thread
// pushes 20 ms of audio every 20 ms of wall time into a BOUNDED hand-off (5 s, the Phase 2
// handoff_capacity for this mono 16 kHz stream; overflow is dropped and counted), and the engine
// thread (production EngineConfig: 800 ms interims over a 6 s window, 10 s force-close) drains
// it, decoding through the REAL model. Every emitted segment's lag = wall time it was emitted
// minus the wall time its last audio sample was produced.
//
// The recognizer picks a config per call: `final_cfg` for a FORCE-CLOSED final (len >= 10 s,
// which no interim can reach since interims are capped at 6 s), `interim_cfg` otherwise. That
// is the seam an engine.rs "treat force-closed finals differently" change would provide.

struct SpikeRecognizer {
    ctx: Arc<WhisperContext>,
    interim: Cfg,
    final_cfg: Cfg,
    threads: i32,
    eot: i32,
    calls: Arc<Mutex<Vec<Value>>>,
}

impl Recognizer for SpikeRecognizer {
    fn label(&self) -> &str {
        "spike"
    }
    fn transcribe(&mut self, samples: &[f32], s: u64, e: u64) -> Vec<RecognizedSegment> {
        let forced = samples.len() >= 10 * SR;
        let cfg = if forced { &self.final_cfg } else { &self.interim };
        let d = decode(&self.ctx, cfg, samples, self.threads, self.eot);
        self.calls.lock().unwrap().push(json!({
            "len": samples.len(), "ms": d.ms, "cfg": cfg.name, "forced": forced,
            "passes": d.passes, "text": d.text,
        }));
        if d.text.trim().is_empty() {
            return Vec::new();
        }
        vec![RecognizedSegment::final_text(d.text.trim(), s, e)]
    }
}

fn load_ctx() -> WhisperContext {
    let asset = WhisperModel::LargeV3Turbo.asset();
    let home = std::env::var("HOME").unwrap();
    let model = Path::new(&home).join("Library/Caches/selahcue/models").join(asset.file_name);
    if std::env::var("SPIKE_SKIP_VERIFY").is_err() {
        verify_model(&model, asset.sha256).expect("model must match the pinned SHA-256");
    }
    WhisperContext::new_with_params(model.to_str().unwrap(), WhisperContextParameters::default())
        .expect("load")
}

fn paced(wavs: &str, out_path: &str, interim_spec: &str, final_spec: &str, noise_rms: f32) {
    use selahcue_core::transcript::TranscriptProvider;
    use std::collections::VecDeque;
    use std::time::Duration;

    let mut stream: Vec<f32> = Vec::new();
    for w in wavs.split(',') {
        stream.extend(read_wav(Path::new(w)));
        stream.extend(std::iter::repeat(0.0f32).take(SR * 4 / 10));
    }
    if noise_rms > 0.0 {
        // Deterministic uniform noise (LCG), scaled to the requested RMS: a "room that never
        // goes quiet" so the 300 ms hangover never fires and force-close is the close path.
        let mut x: u64 = 0x86ac_c9ed;
        let amp = noise_rms * 3f32.sqrt();
        for s in stream.iter_mut() {
            x = x.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            let u = ((x >> 33) as f32 / (1u64 << 31) as f32) * 2.0 - 1.0;
            *s += u * amp;
        }
    }
    let total_s = stream.len() as f64 / SR as f64;

    let ctx = Arc::new(load_ctx());
    let eot = ctx.token_eot();
    let threads = HardwareProbe::detect().threads.saturating_sub(1).max(1) as i32;
    let calls = Arc::new(Mutex::new(Vec::new()));
    let rec = SpikeRecognizer {
        ctx: Arc::clone(&ctx),
        interim: parse_cfg(interim_spec),
        final_cfg: parse_cfg(final_spec),
        threads,
        eot,
        calls: Arc::clone(&calls),
    };
    // Warm both shapes before the clock starts (a real session pays this once at start-up).
    {
        let w = &stream[..10 * SR];
        let _ = decode(&ctx, &rec.interim, &w[..6 * SR], threads, eot);
        let _ = decode(&ctx, &rec.final_cfg, w, threads, eot);
        let _ = decode(&ctx, &rec.interim, &w[..6 * SR], threads, eot);
    }
    let (mut engine, mut provider) = SttEngine::build(
        EngineConfig {
            interim_interval: std::time::Duration::from_millis(800),
            interim_max_samples: 6 * SR,
            ..EngineConfig::default()
        },
        Box::new(EnergyVad::new()),
        Box::new(rec),
        FeedbackGuard::new(),
    );

    const CAP: usize = 5 * SR;
    let buf: Arc<Mutex<(VecDeque<f32>, usize, bool)>> =
        Arc::new(Mutex::new((VecDeque::with_capacity(CAP), 0, false)));
    let t0 = Instant::now();
    let producer = {
        let buf = Arc::clone(&buf);
        let stream = stream.clone();
        std::thread::spawn(move || {
            let chunk = SR / 50;
            let mut i = 0;
            let mut k: u32 = 0;
            while i < stream.len() {
                let deadline = t0 + Duration::from_millis(20 * k as u64);
                let now = Instant::now();
                if deadline > now {
                    std::thread::sleep(deadline - now);
                }
                let end = (i + chunk).min(stream.len());
                let mut g = buf.lock().unwrap();
                if g.0.len() + (end - i) > CAP {
                    g.1 += end - i; // dropped, like the production hand-off overflow
                } else {
                    g.0.extend(&stream[i..end]);
                }
                drop(g);
                i = end;
                k += 1;
            }
            buf.lock().unwrap().2 = true;
        })
    };

    let mut segs: Vec<Value> = Vec::new();
    let mut max_fill = 0usize;
    loop {
        let (chunk, done) = {
            let mut g = buf.lock().unwrap();
            max_fill = max_fill.max(g.0.len());
            let c: Vec<f32> = g.0.drain(..).collect();
            (c, g.2)
        };
        let had_audio = !chunk.is_empty();
        if had_audio {
            engine.process(&AudioChunk::new(chunk, SR as u32, 1));
        } else if done {
            engine.flush();
        } else {
            std::thread::sleep(Duration::from_millis(5));
        }
        let now = t0.elapsed().as_secs_f64();
        for s in provider.poll() {
            let audio_end = s.end_ms as f64 / 1000.0;
            segs.push(json!({
                "text": s.text, "start_ms": s.start_ms, "end_ms": s.end_ms, "final": s.is_final,
                "emit_s": now, "lag_s": now - audio_end,
            }));
        }
        if done && !had_audio {
            let g = buf.lock().unwrap();
            if g.0.is_empty() {
                break;
            }
        }
    }
    producer.join().unwrap();
    let dropped = buf.lock().unwrap().1;

    let lags = |fin: bool| -> Vec<f64> {
        let mut v: Vec<f64> = segs
            .iter()
            .filter(|s| s["final"].as_bool() == Some(fin))
            .map(|s| s["lag_s"].as_f64().unwrap())
            .collect();
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        v
    };
    let stat = |v: &[f64]| -> (f64, f64, f64) {
        if v.is_empty() {
            return (0.0, 0.0, 0.0);
        }
        let mean = v.iter().sum::<f64>() / v.len() as f64;
        (mean, v[((v.len() as f64) * 0.95) as usize].min(v[v.len() - 1]), v[v.len() - 1])
    };
    let (im, ip95, imax) = stat(&lags(false));
    let (fm, fp95, fmax) = stat(&lags(true));
    let calls = calls.lock().unwrap().clone();
    let forced_ms: Vec<f64> = calls
        .iter()
        .filter(|c| c["forced"].as_bool() == Some(true))
        .map(|c| c["ms"].as_f64().unwrap())
        .collect();
    let summary = json!({
        "interim_cfg": interim_spec, "final_cfg": final_spec, "noise_rms": noise_rms,
        "audio_s": total_s, "wall_s": t0.elapsed().as_secs_f64(),
        "interims": lags(false).len(), "finals": lags(true).len(),
        "interim_lag_mean": im, "interim_lag_p95": ip95, "interim_lag_max": imax,
        "final_lag_mean": fm, "final_lag_p95": fp95, "final_lag_max": fmax,
        "dropped_samples": dropped, "handoff_peak_frac": max_fill as f64 / CAP as f64,
        "forced_finals": forced_ms.len(),
        "forced_final_ms_mean": if forced_ms.is_empty() { 0.0 } else { forced_ms.iter().sum::<f64>() / forced_ms.len() as f64 },
    });
    eprintln!("{summary}");
    let mut out = std::fs::File::create(out_path).unwrap();
    writeln!(out, "{}", json!({"summary": summary, "segments": segs, "calls": calls})).unwrap();
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("paced") => paced(
            &args[2],
            &args[3],
            &args[4],
            &args[5],
            args.get(6).map(|s| s.parse().unwrap()).unwrap_or(0.0),
        ),
        Some("extract") => extract(&args[2], &args[3]),
        Some("decode") => run_decode(
            &args[2],
            &args[3],
            &args[4],
            args.get(5).map(String::as_str).unwrap_or("config-major"),
        ),
        _ => eprintln!("usage: see module docs"),
    }
}
