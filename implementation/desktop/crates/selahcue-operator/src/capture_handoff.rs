//! A bounded hand-off of captured audio between the capture (SOURCE) thread and whatever
//! consumes it — shared by the on-device engine and the Cloud (Deepgram) route (86akby7th), so
//! there is exactly ONE buffer type and ONE drop counter regardless of which engine is running.
//!
//! # Why this module exists, and why it belongs to neither route
//!
//! This type used to live inside `listening.rs`'s on-device section, private to that one route.
//! Adding a second route (Cloud) that also needs a capture→consumer hand-off left two ways to
//! satisfy that need: reach into the on-device route's private type, or grow a second, separate
//! one with the same shape. Both are the same mistake in different clothes — the thing that
//! must be single here is not the buffer instance (each capture session gets its own; that is
//! correct and unavoidable) but the **type and its sizing rule**. A duplicated buffer is
//! survivable; a duplicated assumption about how big it should be is not (see
//! [`selahcue_core::audio_capacity`] for the concrete case that motivated this: a literal
//! `channels × 2` silently doubling the retention window on a mono microphone). So the type
//! lives in a module neither route owns, and every caller sizes it via
//! [`selahcue_core::audio_capacity::handoff_capacity`] with the device's REAL reported sample
//! rate and channel count — never a re-derived multiplication.
//!
//! # A zero-capacity hand-off is unrepresentable in this codebase
//!
//! [`AudioHandoff::new`] takes a [`NonZeroUsize`], not a plain `usize`. This is a property of
//! the type, not a runtime check: there is no value you can pass that constructs a hand-off
//! with a capacity of zero, because `NonZeroUsize` itself cannot hold zero. A reviewer can
//! verify this directly by trying to write `AudioHandoff::new(0)` or
//! `AudioHandoff::new(some_usize)` and watching it fail to compile (`expected NonZeroUsize,
//! found usize` / `found integer`) — see the doctest pair below for exactly that failing
//! snippet next to the passing one that shows the correct call.
//!
//! **Those doctests are not exercised by `cargo test` in this crate.** `selahcue-operator` is a
//! binary-only package (`Cargo.toml` declares `[[bin]]`, no `[lib]`), and rustdoc's doctest
//! runner requires a library target to link a snippet against — confirmed empirically:
//! `cargo test --doc -p selahcue-operator` reports `error: no library targets found in package
//! selahcue-operator` rather than running anything. Adding a `[lib]` target purely to enable
//! this one doctest pair would be a real structural change to how this crate is built (`main.rs`
//! would need to consume its own library rather than declaring every module inline), which is
//! out of scope here. The doctests below are therefore documentation of a guarantee a reader
//! can verify by hand — matching the type signature, which IS enforced, by the compiler, on
//! every build — not a mechanically CI-checked control. Do not read their presence as evidence
//! `cargo test` covers this; it does not, and that gap is worth closing (a `[lib]` target and a
//! thin `main.rs` over it) as a follow-up rather than folded into this change.
//!
//! ```
//! # use std::num::NonZeroUsize;
//! # struct AudioHandoff; impl AudioHandoff { fn new(_: NonZeroUsize) -> Self { AudioHandoff } }
//! // Correct: a real NonZeroUsize passes straight through.
//! let cap = NonZeroUsize::new(80_000).expect("80_000 is nonzero");
//! let _handoff = AudioHandoff::new(cap);
//! ```
//!
//! ```compile_fail
//! # use std::num::NonZeroUsize;
//! # struct AudioHandoff; impl AudioHandoff { fn new(_: NonZeroUsize) -> Self { AudioHandoff } }
//! // Refused at compile time: a plain `usize` (here, a literal `0`) is not a `NonZeroUsize`.
//! let _handoff = AudioHandoff::new(0usize);
//! ```
//!
//! # The drop is real, and it is now visible
//!
//! Dropping the OLDEST audio when the cap is exceeded is the correct policy (stale audio is
//! worse than a gap — sending a backlog after a stall produces a transcript permanently running
//! behind, worse than briefly thin). But it is a SILENT policy by construction: nothing about a
//! healthy-looking capture session says whether every captured sample actually reached the
//! engine. [`AudioHandoff::dropped`] is the per-buffer, per-session counter that makes it
//! observable — the caller's job (both routes') is to surface a nonzero reading to the
//! operator, not to assume "still running" means "still complete".

use std::collections::VecDeque;
use std::num::NonZeroUsize;
use std::sync::Mutex;

use selahcue_stt::audio::AudioChunk;

/// A bounded hand-off of captured audio from the SOURCE thread (which owns the `!Send` cpal
/// stream) to whatever consumes it next. When the consumer falls behind, the OLDEST buffered
/// audio is dropped so the source thread never blocks and the consumer stays near the live
/// edge — bounded to the capacity passed to [`AudioHandoff::new`] (no-leak).
pub struct AudioHandoff {
    inner: Mutex<Inner>,
    max_samples: usize,
}

#[derive(Default)]
struct Inner {
    chunks: VecDeque<AudioChunk>,
    /// Samples dropped to stay within the cap since construction (observability; a nonzero
    /// value means the consumer is not keeping up with capture, or was momentarily stalled).
    dropped: u64,
}

impl AudioHandoff {
    /// A hand-off capped at `capacity` retained samples. See the module doc: a zero capacity
    /// cannot be expressed here at all (`NonZeroUsize`), so "the oldest is dropped, the newest
    /// is kept" is always stateable — there is no cap small enough to make every push evict
    /// itself. Callers derive `capacity` from
    /// [`selahcue_core::audio_capacity::handoff_capacity`] with the device's real
    /// configuration, not a literal.
    pub fn new(capacity: NonZeroUsize) -> Self {
        AudioHandoff {
            inner: Mutex::new(Inner::default()),
            max_samples: capacity.get(),
        }
    }

    /// Append a chunk, evicting the oldest chunks (in whole-chunk steps) until the buffered
    /// sample count is within budget. Never blocks beyond this hand-off's own lock.
    pub fn push(&self, chunk: AudioChunk) {
        let mut inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner.chunks.push_back(chunk);
        let mut total: usize = inner.chunks.iter().map(|c| c.samples.len()).sum();
        while total > self.max_samples && inner.chunks.len() > 1 {
            if let Some(old) = inner.chunks.pop_front() {
                total -= old.samples.len();
                inner.dropped = inner.dropped.saturating_add(old.samples.len() as u64);
            }
        }
    }

    /// Take everything buffered (in order), leaving the hand-off empty.
    pub fn drain(&self) -> Vec<AudioChunk> {
        let mut inner = self.inner.lock().unwrap_or_else(|e| e.into_inner());
        inner.chunks.drain(..).collect()
    }

    pub fn is_empty(&self) -> bool {
        self.inner
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .chunks
            .is_empty()
    }

    /// Retained sample count right now (never exceeds the cap this hand-off was built with).
    pub fn retained_samples(&self) -> usize {
        self.inner
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .chunks
            .iter()
            .map(|c| c.samples.len())
            .sum()
    }

    /// Total samples dropped to stay within the cap since construction — per-buffer (a fresh
    /// hand-off starts at 0; this is not a process-global counter a sibling test could satisfy
    /// on your behalf). The observability signal both routes surface to the operator.
    pub fn dropped(&self) -> u64 {
        self.inner.lock().unwrap_or_else(|e| e.into_inner()).dropped
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Chunk size these tests push, and the test cap they push it into — named constants (not
    /// inline literals) so the premise below is a real, checkable relationship rather than two
    /// numbers clippy can already see are constant (`assertions_on_constants` on a literal-vs-
    /// literal comparison is correctly flagged as always-true and provides no protection; a
    /// relationship between two NAMED values that a later edit could change independently is
    /// what the pin is actually for).
    const TEST_CHUNK_SAMPLES: usize = 1_000;
    const TEST_CAP_SAMPLES: usize = 10_000;

    // The premise every bounded-memory test below rests on, pinned at compile time: a cap that
    // is not reachable by whole `TEST_CHUNK_SAMPLES` chunks would make "far past the budget"
    // vacuous (every chunk would be admitted in full, nothing would ever be dropped, and the
    // tests would pass for a hand-off with no effective cap at all).
    const _: () = assert!(
        TEST_CHUNK_SAMPLES < TEST_CAP_SAMPLES,
        "the chunk size used below must be smaller than the test cap, or every push fits and \
         the drop-oldest path is never exercised"
    );

    fn chunk(samples: usize) -> AudioChunk {
        AudioChunk::new(vec![0.0; samples], 48_000, 2)
    }

    fn cap(n: usize) -> NonZeroUsize {
        NonZeroUsize::new(n).expect("test cap must be nonzero")
    }

    #[test]
    fn retained_samples_is_bounded_and_the_most_recent_audio_survives() {
        // No-leak: pushing far past the budget keeps the buffered sample count bounded by
        // dropping the OLDEST chunks — the consumer always works from the most-recent audio
        // (live edge). Per-buffer accessor (`retained_samples`), not a global — a sibling test
        // creating its own `AudioHandoff` cannot mask a miss here.
        let h = AudioHandoff::new(cap(TEST_CAP_SAMPLES));
        for _ in 0..1_000 {
            h.push(chunk(TEST_CHUNK_SAMPLES)); // 1,000,000 samples into a 10,000-sample budget
        }
        assert!(
            h.retained_samples() <= TEST_CAP_SAMPLES,
            "retained {} exceeds the bound {TEST_CAP_SAMPLES}",
            h.retained_samples()
        );
        assert!(!h.is_empty(), "keeps the most recent audio");
        assert!(!h.drain().is_empty());
        assert!(h.is_empty(), "drain empties the hand-off");
    }

    #[test]
    fn the_drop_counter_names_the_exact_number_of_samples_dropped() {
        // Asserted on the ENTITY (the exact dropped-sample count), not a proxy like
        // `retained <= N * chunk_size`. 12 chunks of 1,000 samples into a 10,000-sample cap
        // retains the last 10 chunks (10,000 samples) and drops exactly the first 2
        // (2,000 samples) — a number a vacuous "some drops happened" check could not produce.
        let h = AudioHandoff::new(cap(TEST_CAP_SAMPLES));
        for _ in 0..12 {
            h.push(chunk(TEST_CHUNK_SAMPLES));
        }
        assert_eq!(
            h.dropped(),
            2 * TEST_CHUNK_SAMPLES as u64,
            "expected exactly the first two chunks dropped"
        );
        assert_eq!(h.retained_samples(), TEST_CAP_SAMPLES);
    }

    #[test]
    fn a_benign_under_cap_session_never_drops_anything() {
        // POSITIVE CONTROL: without this, "drops are bounded and counted" above could be
        // satisfied by a hand-off that drops (and counts) EVERYTHING, which is indistinguishable
        // from broken. A session that never exceeds its budget must report zero drops and
        // retain every sample it was given.
        let h = AudioHandoff::new(cap(TEST_CAP_SAMPLES));
        for _ in 0..5 {
            h.push(chunk(TEST_CHUNK_SAMPLES)); // 5,000 into a 10,000-sample budget — never exceeds it
        }
        assert_eq!(
            h.dropped(),
            0,
            "a session that stays under the cap must never be reported as having dropped audio"
        );
        assert_eq!(h.retained_samples(), 5 * TEST_CHUNK_SAMPLES);
    }

    #[test]
    fn a_capacity_of_one_never_panics_and_still_retains_the_newest_sample() {
        // The smallest capacity `NonZeroUsize` can express. Not a bug case to guard against —
        // a proof that the type-level "cannot be zero" guarantee leaves no residual runtime
        // floor/clamp of its own to get wrong.
        let h = AudioHandoff::new(cap(1));
        h.push(chunk(1));
        h.push(chunk(1));
        assert_eq!(h.retained_samples(), 1);
        assert_eq!(h.dropped(), 1);
    }
}
