//! Private, paced file replay through the production engine and Recognizer boundary.
//! No downloads, microphone, providers, model retuning or acceptance claims.
use selahcue_stt::engine::production_engine_config;
use selahcue_stt::HardwareProbe;
use sha2::{Digest, Sha256};
#[cfg(any(feature = "whisper", test))]
use std::io::{self, Write};

fn json_string(value: &str) -> String {
    let mut out = String::from("\"");
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            ch if ch <= '\u{1f}' => out.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => out.push(ch),
        }
    }
    out.push('"');
    out
}

fn digest(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn configuration() -> String {
    // Every value comes from the actual producer factory/default/selector. Decoder settings
    // are not emulated here: the engine hash covers the real recognizer source and lockfile.
    format!("{:?};vad={:?};selection={:?};os={};arch={};whisper={};metal={};cuda={};vulkan={};input=16000Hz-mono-f32le;replay_pacing=20ms",
        production_engine_config(), selahcue_stt::VadConfig::default(),
        HardwareProbe::detect().select_model(), std::env::consts::OS, std::env::consts::ARCH,
        cfg!(feature = "whisper"), cfg!(feature = "metal"), cfg!(feature = "cuda"), cfg!(feature = "vulkan"))
}

fn engine_hash() -> String {
    // This is a source/lock identity, not an installed operator binary attestation.
    let mut hasher = Sha256::new();
    for source in [
        include_bytes!("../src/engine.rs").as_slice(),
        include_bytes!("../src/recognizer.rs").as_slice(),
        include_bytes!("../src/model.rs").as_slice(),
        include_bytes!("../src/vad.rs").as_slice(),
        include_bytes!("../src/audio.rs").as_slice(),
        include_bytes!("../src/resample.rs").as_slice(),
        include_bytes!("../src/guard.rs").as_slice(),
        include_bytes!("../src/repetition.rs").as_slice(),
        include_bytes!("../src/provider.rs").as_slice(),
        include_bytes!("../Cargo.toml").as_slice(),
        include_bytes!("../Cargo.lock").as_slice(),
    ] {
        hasher.update((source.len() as u64).to_le_bytes());
        hasher.update(source);
    }
    hasher
        .finalize()
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn describe() {
    let selection = HardwareProbe::detect().select_model();
    println!("{{\"id\":\"production-baseline\",\"role\":\"production_baseline\",\"engine_sha256\":{},\"model_sha256\":{},\"config_sha256\":{},\"languages\":[\"English\",\"Yoruba\",\"Hausa\"],\"rights_source\":\"Stock Whisper MIT; verify exact asset notices before evaluation\",\"configuration\":{{\"description\":{},\"model_verified\":false,\"measurement_kind\":\"file replay; not installed capture\"}}}}",
        json_string(&engine_hash()), json_string(selection.model.asset().sha256),
        json_string(&digest(configuration().as_bytes())), json_string(&configuration()));
}

#[cfg(any(feature = "whisper", test))]
fn replay(
    input: &mut impl io::Read,
    output: &mut impl Write,
    recognizer: Box<dyn selahcue_stt::Recognizer + Send>,
    paced: bool,
) -> io::Result<()> {
    use selahcue_core::transcript::TranscriptProvider;
    use selahcue_stt::{AudioChunk, EnergyVad, FeedbackGuard, SttEngine};
    let (mut engine, mut provider) = SttEngine::build(
        production_engine_config(),
        Box::new(EnergyVad::new()),
        recognizer,
        FeedbackGuard::new(),
    );
    let start = std::time::Instant::now();
    let mut samples_read = 0_u64;
    let mut first = true;
    let mut emit = |provider: &mut selahcue_stt::SttProvider| -> io::Result<()> {
        for segment in provider.poll() {
            if !first {
                write!(output, ",")?;
            }
            first = false;
            write!(
                output,
                "{{\"text\":{},\"start_ms\":{},\"end_ms\":{},\"is_final\":{}}}",
                json_string(&segment.text),
                segment.start_ms,
                segment.end_ms,
                segment.is_final
            )?;
        }
        Ok(())
    };
    loop {
        // One 20ms frame: bounded I/O and output queue even for long authorized recordings.
        let mut bytes = [0_u8; 320 * 4];
        let mut used = 0;
        while used < bytes.len() {
            let read = input.read(&mut bytes[used..])?;
            if read == 0 {
                break;
            }
            used += read;
        }
        if used == 0 {
            break;
        }
        if used % 4 != 0 {
            return Err(io::Error::other("partial f32 PCM sample"));
        }
        let mut samples = Vec::with_capacity(320);
        for bytes in bytes[..used].chunks_exact(4) {
            let value = f32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
            if !value.is_finite() || !(-1.0..=1.0).contains(&value) {
                return Err(io::Error::other("PCM must be finite normalized f32"));
            }
            samples.push(value);
        }
        samples_read += samples.len() as u64;
        if paced {
            // This is file replay, not microphone capture: delays never claim physical drops.
            let due = std::time::Duration::from_secs_f64(samples_read as f64 / 16_000.0);
            std::thread::sleep(due.saturating_sub(start.elapsed()));
        }
        engine.process(&AudioChunk::new(samples, 16_000, 1));
        emit(&mut provider)?;
    }
    engine.flush();
    emit(&mut provider)
}

#[cfg(feature = "whisper")]
fn run(args: &[String]) -> Result<(), Box<dyn std::error::Error>> {
    use selahcue_stt::model::sha256_file;
    use selahcue_stt::recognizer::WhisperRecognizer;
    use std::fs::{File, OpenOptions};
    use std::path::Path;
    if args.len() != 6 {
        return Err("usage: sermon_pilot_eval CORPUS_ID PROFILE_ID PCM_F32LE MODEL OUTPUT_JSON (or --describe)".into());
    }
    let selection = HardwareProbe::detect().select_model();
    // Exactly the current production selector's pinned model; no unmeasured substitution.
    let recognizer = WhisperRecognizer::load(
        Path::new(&args[4]),
        selection.model.asset().sha256,
        &selection,
    )?;
    let audio_hash = sha256_file(Path::new(&args[3]))?;
    let mut input = File::open(&args[3])?;
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let file = options.open(&args[5])?;
    let result = (|| -> io::Result<()> {
        let mut output = io::BufWriter::new(file);
        write!(output, "[{{\"corpus_id\":{},\"profile_id\":{},\"audio_sha256\":{},\"engine_sha256\":{},\"model_sha256\":{},\"config_sha256\":{},\"run_kind\":\"production_pipeline_file_replay\",\"configuration\":{},\"segments\":[",
            json_string(&args[1]), json_string(&args[2]), json_string(&audio_hash),
            json_string(&engine_hash()), json_string(selection.model.asset().sha256),
            json_string(&digest(configuration().as_bytes())), json_string(&configuration()))?;
        replay(&mut input, &mut output, Box::new(recognizer), true)?;
        // These need external observation or annotation, never invented zeros.
        writeln!(output, "],\"omission_count\":null,\"error_count\":null,\"latency_ms\":null,\"peak_process_tree_memory_bytes\":null,\"dropped_audio_count\":null,\"switch_recovery_ms\":null,\"retrieval\":null}}]")?;
        output.flush()
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&args[5]);
    }
    result?;
    Ok(())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--describe" {
        describe();
        return;
    }
    #[cfg(feature = "whisper")]
    let result = run(&args);
    #[cfg(not(feature = "whisper"))]
    let result: Result<(), Box<dyn std::error::Error>> = Err("replay requires --features whisper and the existing selector's pinned local model; nothing is downloaded".into());
    if result.is_err() {
        // Do not echo private corpus IDs, paths or model-library errors into shared logs.
        eprintln!("Replay failed: check local assets, features and documented arguments; no acceptance result.");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_string_round_trips_with_independent_python_parser() {
        let original = "\"quoted\"\\path\n\r\t\u{0}\u{1f} Yorùbá Ìgbò Hausa ƙ";
        let encoded = json_string(original);
        let output = std::process::Command::new("python3")
            .args([
                "-c",
                "import json,sys; print(json.loads(sys.argv[1]), end='')",
                &encoded,
            ])
            .output()
            .expect("independent JSON parser");
        assert!(output.status.success());
        assert_eq!(String::from_utf8(output.stdout).expect("UTF-8"), original);
    }

    #[test]
    fn replay_uses_actual_recognizer_boundary_and_preserves_saved_words() {
        let recognizer = Box::new(selahcue_stt::FakeRecognizer::with_script([
            "Àlàáfíà Ìgbò ƙ",
        ]));
        let mut input = std::io::Cursor::new(
            vec![0.2_f32, -0.2]
                .repeat(1600)
                .into_iter()
                .flat_map(f32::to_le_bytes)
                .collect::<Vec<_>>(),
        );
        let mut output = Vec::new();
        replay(&mut input, &mut output, recognizer, false).expect("synthetic replay");
        let output = String::from_utf8(output).expect("UTF-8");
        let parsed = std::process::Command::new("python3")
            .args(["-c", "import json,sys; r=json.loads('['+sys.argv[1]+']'); assert len(r)==1; print(r[0]['text'],end='')", &output])
            .output().expect("independent parser");
        assert!(parsed.status.success());
        assert_eq!(
            String::from_utf8(parsed.stdout).expect("UTF-8"),
            "Àlàáfíà Ìgbò ƙ"
        );
    }

    #[test]
    fn replay_producer_uses_shared_six_second_interim_configuration() {
        use std::io::Read;
        use std::sync::{Arc, Mutex};
        struct PausedInput {
            inner: std::io::Cursor<Vec<u8>>,
            paused: bool,
        }
        impl Read for PausedInput {
            fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
                if !self.paused && self.inner.position() >= 112_000 * 4 {
                    self.paused = true;
                    // Open the real existing wall-clock gate, not a performance assertion.
                    std::thread::sleep(std::time::Duration::from_millis(1_200));
                }
                self.inner.read(bytes)
            }
        }
        struct RecordingRecognizer(Arc<Mutex<Vec<usize>>>);
        impl selahcue_stt::Recognizer for RecordingRecognizer {
            fn label(&self) -> &str {
                "synthetic-replay-config-parity"
            }
            fn transcribe(
                &mut self,
                samples: &[f32],
                start: u64,
                end: u64,
            ) -> Vec<selahcue_stt::RecognizedSegment> {
                self.0.lock().expect("observed samples").push(samples.len());
                vec![selahcue_stt::RecognizedSegment::final_text(
                    "synthetic",
                    start,
                    end,
                )]
            }
        }
        let observed = Arc::new(Mutex::new(Vec::new()));
        let bytes = vec![0.2_f32, -0.2]
            .repeat(56_160)
            .into_iter()
            .flat_map(f32::to_le_bytes)
            .collect();
        let mut input = PausedInput {
            inner: std::io::Cursor::new(bytes),
            paused: false,
        };
        replay(
            &mut input,
            &mut Vec::new(),
            Box::new(RecordingRecognizer(Arc::clone(&observed))),
            false,
        )
        .expect("synthetic paced-boundary replay");
        assert_eq!(
            *observed.lock().expect("observed samples"),
            vec![96_000, 112_320],
            "replay producer must decode a bounded interim then the whole final"
        );
    }

    #[test]
    fn replay_rejects_partial_or_nonfinite_pcm() {
        for bytes in [vec![0], f32::NAN.to_le_bytes().to_vec()] {
            let mut input = std::io::Cursor::new(bytes);
            assert!(replay(
                &mut input,
                &mut Vec::new(),
                Box::new(selahcue_stt::FakeRecognizer::new()),
                false
            )
            .is_err());
        }
    }
}
