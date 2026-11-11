#[allow(dead_code)] // The decoder is consumed by the operator, not build generation.
#[path = "src/provider_source/payload.rs"]
mod payload;

fn main() {
    // macOS microphone access (TCC): the on-device STT worker opens the mic via cpal. A
    // *bundled* .app gets its usage description from the bundle's Info.plist, but the dev
    // workflow runs the raw `cargo run` binary — which, with no embedded Info.plist, can't
    // request the mic at all (macOS never prompts and it never appears in System Settings →
    // Microphone; capture just returns silence). Embed an Info.plist carrying
    // NSMicrophoneUsageDescription directly into the Mach-O `__TEXT,__info_plist` section so
    // the raw binary can request access. Link-time only — `cargo check` (CI) is unaffected;
    // gated on the macOS *target* so other platforms are untouched.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("macos") {
        let plist = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("Info.plist");
        println!("cargo:rerun-if-changed=Info.plist");
        println!(
            "cargo:rustc-link-arg=-Wl,-sectcreate,__TEXT,__info_plist,{}",
            plist.display()
        );
    }
    pilot_config();
    tauri_build::build()
}

/// CI supplies a generated file through an explicit build-only path. No dotenv, no
/// runtime environment lookup, and no values in Cargo diagnostics. Absent config
/// produces an unavailable source, including when the feature is explicitly selected.
fn pilot_config() {
    use std::{env, fs, io::Read, path::PathBuf};
    println!("cargo:rerun-if-env-changed=SELAHCUE_PILOT_CONFIG_PATH");
    let mut bytes = Vec::new();
    if env::var_os("CARGO_FEATURE_PILOT_CREDENTIALS").is_some() {
        if let Some(path) = env::var_os("SELAHCUE_PILOT_CONFIG_PATH") {
            // Track rotation without printing the secret-bearing file contents.
            println!("cargo:rerun-if-changed={}", PathBuf::from(&path).display());
            if let Ok(file) = fs::File::open(path) {
                if file
                    .take((payload::MAX_PAYLOAD + 1) as u64)
                    .read_to_end(&mut bytes)
                    .is_err()
                    || bytes.len() > payload::MAX_PAYLOAD
                    || std::str::from_utf8(&bytes).is_err()
                {
                    bytes.clear();
                }
            }
        }
    }
    let out = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo OUT_DIR"));
    fs::write(
        out.join("pilot-config.bin"),
        payload::frame_json(&bytes).unwrap_or_default(),
    )
    .expect("write native pilot configuration");
}
