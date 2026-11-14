# Audio capacity test synchronization implementation plan

Use the subagent-driven development workflow for Task 1. The [design](../specs/2026-11-14-audio-capacity-test-synchronization.md) describes the scheduler dependency and required evidence.

## Task 1. Synchronize the real-path capacity test

The Rust change is limited to the test module in `implementation/desktop/crates/selahcue-operator/src/listening.rs`. Record results in `docs/delivery/evidence/public-release-windows-capacity-test-20261114.md`.

- [x] Read the diagnosis, test and owning capture seams. Define the readiness, primer, recognition entry, flood consumption and cleanup sequence.
- [x] Use test-only channel synchronization on the existing `Recognizer` and `AudioSource` seams. Keep the named capacity test, both 48 kHz device configurations, the 350,000-sample flood and the existing notice assertions. Stop, release and join the worker on fixture timeout and success.
- [x] Verify that the capacity test rejects the historical `HANDOFF_MAX_SAMPLES.max(handoff_capacity)` widening and a forced mono cap for stereo. Restore both temporary mutations.
- [x] Run the capacity test and the neighboring post-ready overload test with `stt,cloud-stt`. Verify formatting and run Clippy with the same features and `-D warnings`. Record the host, commands and results.
- [x] Commit the test, evidence, design and plan.
- [ ] Review the change in PR #400 and verify the hosted Windows native STT result before release acceptance.
