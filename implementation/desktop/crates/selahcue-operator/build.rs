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
    tauri_build::build()
}
