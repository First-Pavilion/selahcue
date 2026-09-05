//! One place to turn "how much captured audio to retain" into a sample count — pure arithmetic
//! over the device's own reported configuration, so no consumer has to re-derive it and risk
//! baking in an assumption about that configuration.
//!
//! # Why this exists (86akby7th)
//!
//! A capture→consumer hand-off that retains raw device audio needs a cap in **samples**, and
//! that requires knowing the device's sample rate and channel count. Writing that arithmetic at
//! each call site — `sample_rate * channels * seconds` — looks harmless because it is *correct
//! arithmetic*; the risk is not the multiplication, it is what gets multiplied. A literal like
//! `48_000 * 2 * 5` bakes in an ASSUMPTION (stereo, in that case) rather than reading the
//! device's actual configuration, and on hardware that does not match the assumption (a mono
//! microphone), the cap silently becomes double what was intended — with no error, no warning,
//! just twice as much retained (and therefore twice as much *stale*) audio.
//!
//! [`handoff_capacity`] takes the real values as parameters. It cannot itself prevent a caller
//! from passing a wrong literal instead of a real `cpal::SupportedStreamConfig`'s fields — no
//! pure function can enforce that — but it gives every consumer *one place* to get the
//! multiplication right, so a fix here reaches everyone who calls it, and there is exactly one
//! definition to review, test, and mutation-verify rather than one per caller.
//!
//! # A real `Duration`, not a seconds scalar
//!
//! A caller passing a bare `5` meaning milliseconds is the same class of mistake as `× 2`
//! meaning stereo — a literal with an assumed, unstated unit. [`std::time::Duration`] removes
//! the ambiguity at the type rather than relying on a parameter name to carry it.
//!
//! The arithmetic below works in **milliseconds** (`Duration::as_millis`), not
//! `Duration::as_secs`, and that choice is deliberate rather than cosmetic: an integer
//! `as_secs()` truncates any sub-second duration to `0` before this function's own logic ever
//! runs, which — for a sub-second window — would return `None` for the *right* answer via the
//! *wrong* mechanism (silent truncation upstream, not a reasoned refusal). This function has
//! nothing sub-second to worry about *today* (every real caller passes whole seconds), but
//! failing safe by accident is not the same as being correct, and the accident stops covering
//! anyone the day a caller changes. Working in milliseconds throughout, dividing by `1_000`
//! only once at the end, represents a sub-second duration faithfully all the way through.
//!
//! # `Option<NonZeroUsize>`, not a clamped `usize`
//!
//! A device reporting `channels == 0` (or `sample_rate_hz == 0`, or a zero-length `duration`)
//! is not "assume mono and carry on": **clamping is the same bug in a less detectable form.**
//! If the device is actually stereo and merely misreported its channel count as zero, a clamp
//! to 1 silently returns a capacity HALF of what it should be — a plausible-looking number with
//! no signal attached, indistinguishable from a correct one to every caller downstream. A
//! zero-capacity ring at least fails *totally and immediately* (nothing survives a moment in
//! it); a wrongly-sized one just loses audio at a rate nobody can attribute. So this function
//! refuses rather than invents: any input that cannot produce a genuine, correctly-derived
//! positive capacity returns `None`, and the caller — which knows whether starting a capture
//! session that can only fail is the right response, or whether some other honest fallback is —
//! decides what `None` means. That decision does not belong in a crate with no I/O.
//!
//! The success case is [`std::num::NonZeroUsize`], not a plain `usize`, for a boundary reason
//! rather than a cosmetic one: `Option<usize>` still lets `Some(0)` exist, so a later edit to
//! this function — or a caller doing its own arithmetic instead of calling it — could
//! reintroduce a zero-capacity ring straight past this guard. `NonZeroUsize` makes that
//! unrepresentable in the type rather than merely absent from today's code paths, at zero cost
//! to callers already handling an `Option`.
//!
//! # Why `selahcue-core`
//!
//! This crate has no dependencies (`Cargo.toml`'s `[dependencies]` is empty) and is the one
//! crate every audio-capturing consumer already reaches by path — `selahcue-stt` (the on-device
//! engine) and `selahcue-stt-cloud` (the Deepgram streaming client) both depend on
//! `selahcue-core` already, for the `TranscriptProvider` seam their `poll()` implementations
//! satisfy. It is also the one candidate actually covered by a gate: `selahcue-core` is a
//! workspace member the `rust` CI job builds and tests across the OS matrix, where
//! `selahcue-stt` is excluded from the workspace and referenced by no CI job at all (its own
//! lint policy is unenforced, tracked as 86ak5rjh7). Putting shared, pure arithmetic at the
//! floor a CI gate actually reaches — rather than in either consumer — means a break here fails
//! loudly instead of silently, and costs nothing against the "no I/O, deterministic" contract
//! that makes this crate exhaustively unit-testable.

use std::num::NonZeroUsize;
use std::time::Duration;

/// How many samples to retain for `duration` of audio at `sample_rate_hz` and `channels`, or
/// `None` if the inputs cannot produce a genuine positive capacity — a zero channel count, a
/// zero sample rate, a zero-length duration, or a product too large to represent. See the
/// module doc for why this refuses rather than clamping or inventing a fallback value.
///
/// No `unwrap`, `expect`, or panicking arithmetic anywhere in this function — this crate's
/// workspace-wide `unwrap_used = "warn"` lint exists specifically to keep the domain core
/// panic-free on untrusted input (a device's reported configuration is exactly that: untrusted
/// input this crate did not produce and cannot verify).
pub fn handoff_capacity(
    sample_rate_hz: u32,
    channels: u16,
    duration: Duration,
) -> Option<NonZeroUsize> {
    if sample_rate_hz == 0 || channels == 0 {
        return None;
    }
    // Milliseconds throughout (see the module doc for why not `as_secs()`); `checked_mul` at
    // every step so a pathological input refuses rather than wraps. The largest realistic
    // product here is far below `u128::MAX`, so these calls are defence-in-depth rather than a
    // path this workspace's own inputs can actually reach — but "realistic" is not a promise a
    // device's reported config makes.
    let per_ms = (sample_rate_hz as u128).checked_mul(channels as u128)?;
    let total_ms = per_ms.checked_mul(duration.as_millis())?;
    let samples = total_ms / 1_000; // divisor is a nonzero literal; never fails
    if samples == 0 || samples > usize::MAX as u128 {
        return None;
    }
    NonZeroUsize::new(samples as usize)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_the_intended_arithmetic_for_realistic_inputs() {
        // The exact case this module exists to get right: a MONO microphone must retain HALF
        // what a stereo one would for the same window — never a hidden factor of two either way.
        let mono_48k_5s = handoff_capacity(48_000, 1, Duration::from_secs(5))
            .expect("realistic input must succeed");
        let stereo_48k_5s = handoff_capacity(48_000, 2, Duration::from_secs(5))
            .expect("realistic input must succeed");
        assert_eq!(
            mono_48k_5s.get(),
            48_000 * 5,
            "mono: rate × 1 × seconds, not doubled"
        );
        assert_eq!(stereo_48k_5s.get(), 48_000 * 2 * 5);
        assert_eq!(
            stereo_48k_5s.get(),
            mono_48k_5s.get() * 2,
            "stereo must be exactly double mono for the same rate and window — this is the \
             relationship a hardcoded '× 2' silently assumed for every device"
        );
    }

    // --- POSITIVE CONTROL: a benign, realistic config must succeed and exercise the real path -

    #[test]
    fn a_benign_realistic_config_returns_some_and_is_not_dead_code() {
        // Without this, every "returns None for X" test below could be satisfied by a function
        // that always returns None — "refused" would be indistinguishable from "broken".
        let cap = handoff_capacity(16_000, 1, Duration::from_secs(5));
        assert!(
            cap.is_some(),
            "a realistic mono 16 kHz config must produce a capacity"
        );
        assert_eq!(cap.unwrap().get(), 80_000);
    }

    // --- Each zero input refuses on its own — not just in combination -----------------------

    #[test]
    fn zero_channels_refuses_rather_than_assuming_mono() {
        assert_eq!(
            handoff_capacity(48_000, 0, Duration::from_secs(5)),
            None,
            "a zero channel count must be REFUSED, not clamped to 1 — a clamp would silently \
             halve the true capacity if the device is actually stereo and merely misreported"
        );
    }

    #[test]
    fn zero_sample_rate_refuses() {
        assert_eq!(handoff_capacity(0, 2, Duration::from_secs(5)), None);
    }

    #[test]
    fn zero_duration_refuses() {
        assert_eq!(handoff_capacity(48_000, 2, Duration::ZERO), None);
    }

    // --- The Duration-not-scalar choice, proven rather than merely asserted in prose --------

    #[test]
    fn a_sub_second_duration_is_represented_faithfully_not_truncated_to_zero() {
        // POSITIVE CONTROL for `as_millis()` over `as_secs()`: 500ms at 16kHz mono must read as
        // HALF of one second's capacity, not as zero. If this function computed on
        // `duration.as_secs()` instead, 500ms would truncate to `0` BEFORE the zero-guard ever
        // ran, and this test would fail (capacity absent) even though the input is genuinely
        // valid — the "failing safe by accident" case the module doc names.
        let one_sec =
            handoff_capacity(16_000, 1, Duration::from_secs(1)).expect("one second must succeed");
        let half_sec = handoff_capacity(16_000, 1, Duration::from_millis(500))
            .expect("half a second is a genuinely valid, non-zero duration");
        assert_eq!(one_sec.get(), 16_000);
        assert_eq!(
            half_sec.get(),
            8_000,
            "500ms must read as half a second, not truncate to 0"
        );
    }

    #[test]
    fn a_pathological_product_refuses_rather_than_wrapping() {
        // A product that cannot fit in `usize` must come back `None`, never a wrapped/truncated
        // small value that would silently under-size the buffer.
        assert_eq!(
            handoff_capacity(u32::MAX, u16::MAX, Duration::from_secs(u64::MAX)),
            None,
            "an unrepresentable product must be refused, never silently wrapped"
        );
    }

    #[test]
    fn zero_capacity_is_unrepresentable_in_the_success_case_by_construction() {
        // Documents the NonZeroUsize property directly: even if every zero-guard above were
        // deleted, `NonZeroUsize::new(0)` itself returns `None` — the type, not just this
        // function's own logic, refuses to name a zero capacity a success.
        assert_eq!(NonZeroUsize::new(0), None);
    }
}
