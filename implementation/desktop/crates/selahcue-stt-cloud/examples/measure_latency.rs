//! Measure first-token and interim-to-final latency against the **live** Deepgram service.
//!
//! This is evidence-gathering, not a test. It is deliberately an example rather than a
//! `#[test]`: it needs a real key, a network and a paid third party, and a suite with those
//! dependencies is a suite that gets skipped. The automated suite talks only to a local stub
//! socket. This is how the ticket's latency and wire-parameter criteria get their numbers, and
//! it is checked in so those numbers can be reproduced rather than taken on trust.
//!
//! ```text
//! # 16 kHz mono signed-16-bit little-endian PCM, headerless:
//! say -o /tmp/sermon.aiff "Turn with me to John chapter three verse sixteen."
//! afconvert -f WAVE -d LEI16@16000 -c 1 /tmp/sermon.aiff /tmp/sermon.wav
//! tail -c +45 /tmp/sermon.wav > /tmp/sermon.pcm
//!
//! cargo run -p selahcue-stt-cloud --features deepgram \
//!     --example measure_latency -- /tmp/sermon.pcm 4
//! ```
//!
//! Audio is paced at **real time**, because sending a whole utterance in one burst measures
//! how fast Deepgram drains a buffer rather than how quickly words reach an operator.
//!
//! Reads `DEEPGRAM_API_KEY` from the environment. It never prints it.

use std::time::{Duration, Instant};

use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
use selahcue_stt_cloud::transport::{CloudSttSession, SessionConfig};
use selahcue_stt_cloud::{
    developer_credential_from_env, AudioChunk, AudioRing, SegmentQueue, SessionStatus, StreamParams,
};

/// 20 ms of 16 kHz mono 16-bit audio — the cadence a capture callback would deliver.
const FRAME_SAMPLES: usize = 320;
const FRAME_INTERVAL: Duration = Duration::from_millis(20);

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = std::env::args().skip(1);
    let pcm_path = args
        .next()
        .ok_or("usage: measure_latency <pcm-file> [runs]")?;
    let runs: usize = args.next().unwrap_or_else(|| "4".into()).parse()?;

    let pcm = std::fs::read(&pcm_path)?;
    let samples: Vec<i16> = pcm
        .as_chunks::<2>()
        .0
        .iter()
        .map(|b| i16::from_le_bytes(*b))
        .collect();
    let params = StreamParams::default();
    println!(
        "audio      : {pcm_path} ({} samples, {:.1}s at 16 kHz)",
        samples.len(),
        samples.len() as f64 / 16_000.0
    );
    println!("parameters : {}", params.to_query());
    println!("runs       : {runs}\n");

    // The consent gate is authoritative even here: there is no way to build a streaming
    // session without it, and this example is not a place to make an exception.
    let mut config = ProvidersConfig::default();
    config.settings.transcription_mode = TranscriptionMode::Cloud;
    config.consent.cloud_transcription = true;
    let authorisation = selahcue_stt_cloud::StreamAuthorization::from_config(&config)?;

    let mut first_tokens = Vec::new();
    let mut interim_to_finals = Vec::new();

    for run in 1..=runs {
        let credential = developer_credential_from_env()?;
        let queue = SegmentQueue::new();
        let ring = AudioRing::new();
        let status = SessionStatus::new();
        let session = CloudSttSession::start(
            &authorisation,
            credential,
            SessionConfig {
                params: params.clone(),
                ..SessionConfig::default()
            },
            ring.clone(),
            queue.clone(),
            status.clone(),
        )?;

        // Wait for the socket before starting the clock, so connection setup is not counted as
        // transcription latency — they are different numbers and conflating them flatters us.
        let connect_started = Instant::now();
        while !status.get().is_streaming() && connect_started.elapsed() < Duration::from_secs(15) {
            std::thread::sleep(Duration::from_millis(5));
        }
        if !status.get().is_streaming() {
            println!("run {run}: never connected — {:?}", status.get());
            continue;
        }
        let connect_ms = connect_started.elapsed().as_millis();

        let audio_started = Instant::now();
        let mut first_segment: Option<(Duration, bool)> = None;
        let mut first_interim: Option<Duration> = None;
        let mut first_final: Option<Duration> = None;
        let mut transcript = String::new();

        for frame in samples.chunks(FRAME_SAMPLES) {
            let due = audio_started + FRAME_INTERVAL * (ring.admitted() as u32 + 1);
            ring.push(AudioChunk::from_pcm_i16(frame));
            drain(
                &queue,
                &audio_started,
                &mut first_segment,
                &mut first_interim,
                &mut first_final,
                &mut transcript,
            );
            let now = Instant::now();
            if due > now {
                std::thread::sleep(due - now);
            }
        }

        // Let the tail of the utterance settle.
        let settling = Instant::now();
        while first_final.is_none() && settling.elapsed() < Duration::from_secs(10) {
            drain(
                &queue,
                &audio_started,
                &mut first_segment,
                &mut first_interim,
                &mut first_final,
                &mut transcript,
            );
            std::thread::sleep(Duration::from_millis(5));
        }
        drain(
            &queue,
            &audio_started,
            &mut first_segment,
            &mut first_interim,
            &mut first_final,
            &mut transcript,
        );

        print!("run {run}: connect {connect_ms} ms");
        match first_segment {
            Some((at, is_final)) => {
                first_tokens.push(at);
                print!(
                    " | first token {} ms ({})",
                    at.as_millis(),
                    if is_final { "final" } else { "interim" }
                );
            }
            None => print!(" | first token NONE"),
        }
        if let (Some(i), Some(f)) = (first_interim, first_final) {
            let delta = f.saturating_sub(i);
            interim_to_finals.push(delta);
            print!(" | interim→final {} ms", delta.as_millis());
        }
        println!("\n        transcript: {transcript:?}");

        session.stop();
        std::thread::sleep(Duration::from_millis(250));
    }

    summarise("first token", &first_tokens);
    summarise("interim→final", &interim_to_finals);
    Ok(())
}

fn drain(
    queue: &SegmentQueue,
    started: &Instant,
    first_segment: &mut Option<(Duration, bool)>,
    first_interim: &mut Option<Duration>,
    first_final: &mut Option<Duration>,
    transcript: &mut String,
) {
    for segment in queue.drain() {
        let at = started.elapsed();
        if first_segment.is_none() {
            *first_segment = Some((at, segment.is_final));
        }
        if segment.is_final {
            if first_final.is_none() {
                *first_final = Some(at);
            }
            if !transcript.is_empty() {
                transcript.push(' ');
            }
            transcript.push_str(&segment.text);
        } else if first_interim.is_none() {
            *first_interim = Some(at);
        }
    }
}

/// Report the spread, not just an average. A single run is a hypothesis; four runs with their
/// range is a measurement, and quoting one number hides which it was.
fn summarise(label: &str, samples: &[Duration]) {
    if samples.is_empty() {
        println!("\n{label}: no samples");
        return;
    }
    let mut ms: Vec<u128> = samples.iter().map(|d| d.as_millis()).collect();
    ms.sort_unstable();
    let total: u128 = ms.iter().sum();
    println!(
        "\n{label}: n={} min={} median={} max={} mean={}",
        ms.len(),
        ms[0],
        ms[ms.len() / 2],
        ms[ms.len() - 1],
        total / ms.len() as u128
    );
}
