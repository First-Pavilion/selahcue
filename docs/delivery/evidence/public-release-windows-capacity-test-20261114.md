# Windows native STT hand-off capacity regression

The Windows native STT job at `448c93f40f24e294eba7b7f60059a3d4655c81a7` failed the mono notice assertion in `on_device_hand_off_capacity_is_mono_correct_not_stereo_doubled`. The test previously let recognition drain while capture was pushing the 350,000-sample flood. One drain after 175 of the 350 pushes would leave two 175,000-sample batches, both below the correct 240,000-sample mono cap. The log does not identify the failed run's interleaving. [Windows job 132535511051](https://github.com/First-Pavilion/selahcue/actions/runs/43623917349/job/132535511051)

The test now waits for a voiced primer with trailing silence to reach the injected recognizer and parks recognition through the measured flood. The next empty source read acknowledges that capture pushed the final chunk. A scope guard stops capture and disconnects the release channel before the scope joins the worker. Capture checks the cumulative drop counter before it exits, and the original assertions read the notice after the join. Both cases still exercise the production capture, hand-off sizing and notice path with 48 kHz audio and identical 350,000-sample floods.

## Local results

The local checks ran on macOS 26.3 (25D125), `aarch64-apple-darwin`, Rust 1.98.0. The Tauri build required an ignored empty `binaries/selahcue-output-aarch64-apple-darwin` placeholder and the local build-only override `TAURI_CONFIG='{"bundle":{"macOS":{"frameworks":[]}}}'` because the packaging dylib was absent. The tests exercised synthetic audio through the mock Tauri app and injected recognizer.

Run from `implementation/desktop/crates/selahcue-operator` with the override above for Cargo builds.

```sh
cargo test --offline --locked --features stt,cloud-stt --bin selahcue-operator \
  listening::tests::on_device_hand_off_capacity_is_mono_correct_not_stereo_doubled \
  -- --exact --nocapture
cargo test --offline --locked --features stt,cloud-stt --bin selahcue-operator \
  listening::tests::a_genuine_post_ready_overload_still_trips_the_notice \
  -- --exact --nocapture
cargo fmt --check
cargo clippy --offline --locked --features stt,cloud-stt --all-targets -- -D warnings
```

| Check | Result |
| --- | --- |
| Focused capacity regression, before and after the controls | Passed twice. Each run reported 110,000 dropped and 240,000 retained for mono and no stereo drop notice. |
| Temporary historical widening at the on-device call site with `HANDOFF_MAX_SAMPLES.max(handoff_capacity)` | Failed at the mono assertion with exit 101. The widened cap produced no mono drop notice. |
| Temporary clamp to the derived single-channel capacity | Failed at the stereo assertion with exit 101. The forced cap produced a drop notice in both cases. |
| Neighboring post-ready overload regression | Passed. The expected sticky drop notice was present. |
| Formatting and Clippy | Passed. |

The temporary controls were restored byte for byte before the final verification. The committed Rust diff starts inside the existing `#[cfg(test)]` module. Hosted Windows native acceptance remains pending on PR #400.
