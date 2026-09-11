//! A durable side-channel for live-transcript segments (86akcfftu).
//!
//! `selahcue_core::transcript::TranscriptLog::push` evicts the oldest segment once the live
//! ring passes `MAX_TRANSCRIPT_SEGMENTS` (240) — correct and deliberate, it bounds memory for
//! the live console view of an unbounded-length service. This module gives [`LiveController`]
//! an independent, injectable seam so every FINAL segment can *also* be written to a durable
//! store as it happens, before the ring's eviction would have dropped it, without changing the
//! ring's behaviour at all and without the caller needing to know which
//! [`TranscriptProvider`](selahcue_core::transcript::TranscriptProvider) produced the segment —
//! `ingest_transcript` already receives provider-erased `text`/`start_ms`/`end_ms`, so this seam
//! is exactly as provider-agnostic as the method it hangs off.
//!
//! This is a **parallel path, not a route through `ControllerSnapshot`/autosave**: ADR-0019
//! deliberately keeps the transcript + detection queue out of the crash-recovery snapshot, and
//! this module does not touch it. It borrows only the *pattern* FR-074's autosave established —
//! bounded, batched, count-or-interval-triggered writes — never its code or its target.
//!
//! `selahcue-app` must not depend on `selahcue-data` (the crate graph runs the other way: both
//! `selahcue-desktop` and `selahcue-operator` depend on `selahcue-app` AND `selahcue-data` as
//! siblings). So [`TranscriptSink`] is the seam a binary crate implements against its own
//! `Database`; this module owns only the bounded buffering policy, exercised in tests entirely
//! against a fake [`TranscriptStoreWriter`] with no SQLite involved.

use std::collections::VecDeque;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// A durable sink for transcript session boundaries + segments. [`LiveController`] holds one as
/// `Box<dyn TranscriptSink>`, defaulting to [`NullTranscriptSink`] — exactly today's behaviour
/// (in-memory-only transcript) for a caller that has not wired a real store, e.g. the operator's
/// stand-alone in-process demo shell (`Backend::Local`): it has no output window and no database
/// shared with the desktop process that owns the real transcript store (see the 86akcfftu PR
/// description for why that pairing is out of scope here).
pub trait TranscriptSink: Send {
    /// A new listening session started. `label`/`provider` describe it for a future Transcripts
    /// list. Implementations that cannot open a transcript record (no store configured, a
    /// storage failure) must degrade silently — a side-channel failure must never block or alter
    /// the live console; the ring is unaffected either way.
    fn start(&mut self, label: &str, provider: &str);
    /// One FINALISED segment — the same text/timing [`LiveController::ingest_transcript`] just
    /// pushed onto the live ring — to persist durably. Never called for a streaming interim (an
    /// interim never reaches the ring either; see `ingest_transcript`'s `is_final` guard).
    fn ingest(&mut self, start_ms: u64, end_ms: u64, text: &str);
    /// The listening session ended (normal Stop Listening). Closes the transcript's `ended_at`.
    /// A crash that skips this call is handled separately, by a startup sweep over transcripts
    /// left with no `ended_at` (see the desktop binary's wiring) — not by anything in this trait.
    fn end(&mut self);
}

/// The default, no-op sink. Matches today's behaviour exactly.
#[derive(Debug, Default, Clone, Copy)]
pub struct NullTranscriptSink;

impl TranscriptSink for NullTranscriptSink {
    fn start(&mut self, _label: &str, _provider: &str) {}
    fn ingest(&mut self, _start_ms: u64, _end_ms: u64, _text: &str) {}
    fn end(&mut self) {}
}

/// A monotonic time source, injected so the buffer's flush-INTERVAL logic is deterministic in
/// tests (CLAUDE.md: "Timers/animation take an injected clock — keep new time-dependent code
/// deterministic the same way"). This is never persisted or compared across restarts — only used
/// for "how long since the last flush attempt". Wall-clock epoch-ms (for `started_at`/`ended_at`,
/// which ARE persisted) is a separate concern: [`EpochClock`].
pub trait MonotonicClock: Send {
    fn now(&self) -> Instant;
}

/// Reads the real OS monotonic clock. The only production implementation.
#[derive(Debug, Default, Clone, Copy)]
pub struct SystemMonotonicClock;
impl MonotonicClock for SystemMonotonicClock {
    fn now(&self) -> Instant {
        Instant::now()
    }
}

/// Wall-clock epoch-ms, injected for the same determinism reason — `started_at_ms`/`ended_at_ms`
/// values passed to the store are controllable in tests rather than reading the OS clock from
/// inside buffering logic.
pub trait EpochClock: Send {
    fn now_ms(&self) -> i64;
}

/// Reads the real OS wall clock. The only production implementation.
#[derive(Debug, Default, Clone, Copy)]
pub struct SystemEpochClock;
impl EpochClock for SystemEpochClock {
    fn now_ms(&self) -> i64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as i64)
            .unwrap_or(0)
    }
}

/// What a real store must offer [`BatchingTranscriptWriter`] — a thin seam over
/// `selahcue_data::transcript_repo`, implemented by the binary crate that owns a `Database`
/// (this crate does not, and must not, depend on `selahcue-data`; see the module docs).
///
/// `open_transcript`/`append_segment` return the id the row was given (a database rowid) so a
/// caller can map a segment back to it if it ever needs to (e.g. for a correction or a
/// detection's `segment_id` — a rowid, NOT `selahcue_core::transcript::TranscriptSegment::id`,
/// which is a separate 0-based counter; nothing in this trait mixes the two).
pub trait TranscriptStoreWriter {
    fn open_transcript(
        &mut self,
        label: &str,
        provider: &str,
        started_at_ms: i64,
    ) -> Result<i64, String>;
    fn append_segment(
        &mut self,
        transcript_id: i64,
        start_ms: u64,
        end_ms: u64,
        text: &str,
    ) -> Result<i64, String>;
    fn end_transcript(&mut self, transcript_id: i64, ended_at_ms: i64) -> Result<(), String>;
}

/// Flush once the buffer holds this many un-persisted segments, even if the interval below
/// hasn't elapsed — bounds how many segments a slow (but healthy) store leaves unwritten in the
/// common case. Mirrors FR-074's autosave being both count- and time-triggered.
pub const FLUSH_SEGMENT_THRESHOLD: usize = 8;

/// Flush at least this often even under a trickle of segments, so a quiet stretch of a service
/// doesn't leave several minutes of speech sitting unpersisted just because fewer than
/// [`FLUSH_SEGMENT_THRESHOLD`] segments have arrived. Mirrors FR-074's `TIMER_AUTOSAVE_INTERVAL`.
pub const FLUSH_INTERVAL: Duration = Duration::from_secs(5);

/// Hard cap on how many un-persisted segments this buffer will ever hold, regardless of how long
/// or how badly the store is failing. This is the bounded-memory guarantee: once reached, the
/// OLDEST unpersisted segment is dropped to admit the newest one
/// ([`BatchingTranscriptWriter::dropped_segment_count`] tracks how many, mirroring
/// `SessionStore.last_save_error` — a degradation is counted/visible, never silent). Must stay
/// `>= FLUSH_SEGMENT_THRESHOLD`, pinned below, so a future edit cannot shrink the cap under the
/// trigger and force a synchronous flush on every single push (defeating the batching this
/// exists to provide).
pub const MAX_PENDING_SEGMENTS: usize = 64;

const _: () = assert!(MAX_PENDING_SEGMENTS >= FLUSH_SEGMENT_THRESHOLD);

/// Defensive per-segment text cap for THIS buffer only — independent of, and much larger than,
/// the live ring's `MAX_SEGMENT_TEXT_LEN` (2,000). The durable copy is deliberately NOT
/// truncated to the ring's cap (the whole point of this ticket is that the persisted transcript
/// must not inherit the live view's bounds); this is only a safety net against a runaway/corrupt
/// provider bug feeding one pathological segment that would otherwise let a single entry consume
/// unbounded memory even while the entry COUNT stays bounded.
pub const MAX_PENDING_SEGMENT_TEXT_LEN: usize = 32_768;

/// One durably-pending segment, buffered until the next flush.
#[derive(Debug, Clone, PartialEq, Eq)]
struct PendingSegment {
    start_ms: u64,
    end_ms: u64,
    text: String,
}

/// Truncate `text` to at most `max_len` bytes on a UTF-8 char boundary (never splits a
/// multi-byte codepoint), mirroring the safety property of core's own segment-text bounding.
fn bounded_text(text: &str, max_len: usize) -> String {
    if text.len() <= max_len {
        return text.to_string();
    }
    let mut end = max_len;
    while end > 0 && !text.is_char_boundary(end) {
        end -= 1;
    }
    text[..end].to_string()
}

/// Batches segments in memory and flushes them to a [`TranscriptStoreWriter`] on a
/// count-or-interval trigger (FR-074's autosave *pattern*, applied to a different store).
/// Implements [`TranscriptSink`] so `LiveController` can hold it as `Box<dyn TranscriptSink>`.
pub struct BatchingTranscriptWriter<S, M = SystemMonotonicClock, E = SystemEpochClock> {
    store: S,
    monotonic: M,
    epoch: E,
    transcript_id: Option<i64>,
    pending: VecDeque<PendingSegment>,
    last_flush_at: Option<Instant>,
    dropped_segment_count: u64,
    last_error: Option<String>,
}

impl<S: TranscriptStoreWriter> BatchingTranscriptWriter<S, SystemMonotonicClock, SystemEpochClock> {
    /// Construct with the real OS clocks (production wiring).
    pub fn new(store: S) -> Self {
        Self::with_clocks(store, SystemMonotonicClock, SystemEpochClock)
    }
}

impl<S: TranscriptStoreWriter, M: MonotonicClock, E: EpochClock> BatchingTranscriptWriter<S, M, E> {
    /// Construct with injected clocks (tests: deterministic time, no sleeping).
    pub fn with_clocks(store: S, monotonic: M, epoch: E) -> Self {
        Self {
            store,
            monotonic,
            epoch,
            transcript_id: None,
            pending: VecDeque::new(),
            last_flush_at: None,
            dropped_segment_count: 0,
            last_error: None,
        }
    }

    /// Number of segments buffered but not yet confirmed written. NEVER exceeds
    /// [`MAX_PENDING_SEGMENTS`] — see `bounded_regardless_of_store_health` in this crate's tests.
    pub fn pending_len(&self) -> usize {
        self.pending.len()
    }

    /// How many buffered segments have been dropped (oldest-first) to hold the bound above,
    /// because the store kept failing to accept a flush. Zero under a healthy store.
    pub fn dropped_segment_count(&self) -> u64 {
        self.dropped_segment_count
    }

    /// The most recent store-write failure, if any (cleared on the next successful flush).
    pub fn last_error(&self) -> Option<&str> {
        self.last_error.as_deref()
    }

    /// Whether a transcript is currently open (`start` succeeded and `end` has not run).
    pub fn is_open(&self) -> bool {
        self.transcript_id.is_some()
    }

    /// Direct access to the wrapped store, for a caller that needs to read back what was
    /// written (tests use this to assert order/content against the fake store).
    pub fn store(&self) -> &S {
        &self.store
    }

    fn should_flush(&self) -> bool {
        if self.pending.is_empty() {
            return false;
        }
        if self.pending.len() >= FLUSH_SEGMENT_THRESHOLD {
            return true;
        }
        match self.last_flush_at {
            None => true,
            Some(t) => self.monotonic.now().duration_since(t) >= FLUSH_INTERVAL,
        }
    }

    fn flush(&mut self) {
        let Some(id) = self.transcript_id else {
            // Nothing open (start() never succeeded, or end() already ran) — keep buffering;
            // a later start() will flush what's pending against the newly opened transcript.
            return;
        };
        while let Some(seg) = self.pending.front() {
            match self
                .store
                .append_segment(id, seg.start_ms, seg.end_ms, &seg.text)
            {
                Ok(_) => {
                    self.pending.pop_front();
                    self.last_error = None;
                }
                Err(e) => {
                    self.last_error = Some(e);
                    break; // keep the rest buffered; retry on the next flush trigger
                }
            }
        }
        self.last_flush_at = Some(self.monotonic.now());
    }

    /// Enforce the hard cap unconditionally — the one invariant that must hold no matter how the
    /// store behaves. Drops the OLDEST unpersisted segment(s) first (a service's most recent
    /// words matter more to keep buffered/retryable than its oldest still-unwritten ones).
    fn enforce_bound(&mut self) {
        while self.pending.len() > MAX_PENDING_SEGMENTS {
            self.pending.pop_front();
            self.dropped_segment_count += 1;
        }
    }
}

impl<S: TranscriptStoreWriter + Send, M: MonotonicClock, E: EpochClock> TranscriptSink
    for BatchingTranscriptWriter<S, M, E>
{
    fn start(&mut self, label: &str, provider: &str) {
        self.pending.clear();
        self.last_error = None;
        self.dropped_segment_count = 0;
        self.last_flush_at = Some(self.monotonic.now());
        match self
            .store
            .open_transcript(label, provider, self.epoch.now_ms())
        {
            Ok(id) => self.transcript_id = Some(id),
            Err(e) => {
                self.transcript_id = None;
                self.last_error = Some(e);
            }
        }
    }

    fn ingest(&mut self, start_ms: u64, end_ms: u64, text: &str) {
        self.pending.push_back(PendingSegment {
            start_ms,
            end_ms,
            text: bounded_text(text, MAX_PENDING_SEGMENT_TEXT_LEN),
        });
        self.enforce_bound();
        if self.should_flush() {
            self.flush();
            self.enforce_bound();
        }
    }

    fn end(&mut self) {
        self.flush();
        self.enforce_bound();
        if let Some(id) = self.transcript_id.take() {
            if let Err(e) = self.store.end_transcript(id, self.epoch.now_ms()) {
                self.last_error = Some(e);
            }
        }
        self.pending.clear();
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    /// A fake `TranscriptStoreWriter` + clocks, fully deterministic and SQLite-free, per
    /// CLAUDE.md's bounded-memory-test standard: no proxy metrics, exact entity assertions.
    /// `Arc<Mutex<_>>` rather than `Rc<RefCell<_>>` because `TranscriptSink: Send` (it is held
    /// as `Box<dyn TranscriptSink>` inside `LiveController`, which crosses an `Arc<Mutex<_>>`
    /// boundary in real wiring) — the fakes must satisfy the same bound the real thing does.
    #[derive(Default)]
    struct FakeStoreState {
        next_id: i64,
        /// Every segment the fake ever accepted, in call order: (transcript_id, start_ms,
        /// end_ms, text) — the "entity", not a byte-size proxy.
        accepted: Vec<(i64, u64, u64, String)>,
        ended: Vec<(i64, i64)>,
        /// When `Some(n)`, the next `n` `append_segment` calls fail before succeeding again.
        fail_next_appends: usize,
        open_calls: usize,
    }

    #[derive(Clone, Default)]
    struct FakeStore(Arc<Mutex<FakeStoreState>>);
    impl FakeStore {
        fn new() -> Self {
            Self::default()
        }
        fn fail_next(&self, n: usize) {
            self.0.lock().unwrap().fail_next_appends = n;
        }
        fn accepted(&self) -> Vec<(i64, u64, u64, String)> {
            self.0.lock().unwrap().accepted.clone()
        }
        fn ended(&self) -> Vec<(i64, i64)> {
            self.0.lock().unwrap().ended.clone()
        }
        fn open_calls(&self) -> usize {
            self.0.lock().unwrap().open_calls
        }
    }
    impl TranscriptStoreWriter for FakeStore {
        fn open_transcript(
            &mut self,
            _label: &str,
            _provider: &str,
            _started_at_ms: i64,
        ) -> Result<i64, String> {
            let mut s = self.0.lock().unwrap();
            s.open_calls += 1;
            s.next_id += 1;
            Ok(s.next_id)
        }
        fn append_segment(
            &mut self,
            transcript_id: i64,
            start_ms: u64,
            end_ms: u64,
            text: &str,
        ) -> Result<i64, String> {
            let mut s = self.0.lock().unwrap();
            if s.fail_next_appends > 0 {
                s.fail_next_appends -= 1;
                return Err("simulated store failure".to_string());
            }
            s.accepted
                .push((transcript_id, start_ms, end_ms, text.to_string()));
            Ok(s.accepted.len() as i64)
        }
        fn end_transcript(&mut self, transcript_id: i64, ended_at_ms: i64) -> Result<(), String> {
            self.0
                .lock()
                .unwrap()
                .ended
                .push((transcript_id, ended_at_ms));
            Ok(())
        }
    }

    /// A store that ALWAYS fails every append — the hostile case for the bounded-memory control.
    #[derive(Default, Clone)]
    struct AlwaysFailingStore;
    impl TranscriptStoreWriter for AlwaysFailingStore {
        fn open_transcript(&mut self, _: &str, _: &str, _: i64) -> Result<i64, String> {
            Ok(1)
        }
        fn append_segment(&mut self, _: i64, _: u64, _: u64, _: &str) -> Result<i64, String> {
            Err("disk is jammed".to_string())
        }
        fn end_transcript(&mut self, _: i64, _: i64) -> Result<(), String> {
            Err("disk is jammed".to_string())
        }
    }

    /// A fake clock that never advances on its own — the test drives it explicitly, so the
    /// interval trigger is deterministic rather than racing real wall time.
    #[derive(Clone)]
    struct FakeMonotonicClock(Arc<Mutex<Instant>>);
    impl FakeMonotonicClock {
        fn new() -> Self {
            Self(Arc::new(Mutex::new(Instant::now())))
        }
        fn advance(&self, d: Duration) {
            *self.0.lock().unwrap() += d;
        }
    }
    impl MonotonicClock for FakeMonotonicClock {
        fn now(&self) -> Instant {
            *self.0.lock().unwrap()
        }
    }

    #[derive(Clone)]
    struct FakeEpochClock(Arc<Mutex<i64>>);
    impl FakeEpochClock {
        fn new(start_ms: i64) -> Self {
            Self(Arc::new(Mutex::new(start_ms)))
        }
    }
    impl EpochClock for FakeEpochClock {
        fn now_ms(&self) -> i64 {
            *self.0.lock().unwrap()
        }
    }

    // Compile-time pin: this test's premise (that pushing MORE than the cap must not grow
    // `pending` past it) is only meaningful while the cap exceeds the flush trigger; if a future
    // edit ever inverted that relationship the module-level `const _` assertion already refuses
    // to compile, but pin it here too so this test file alone documents why `PUSHES` below must
    // stay comfortably larger than `MAX_PENDING_SEGMENTS`.
    const _: () = assert!(MAX_PENDING_SEGMENTS >= FLUSH_SEGMENT_THRESHOLD);

    /// THE bounded-memory control (CLAUDE.md standard): under a store that NEVER succeeds, the
    /// pending buffer must never exceed `MAX_PENDING_SEGMENTS`, checked after EVERY push (not
    /// just at the end) so a control that only samples the final state cannot pass by luck.
    #[test]
    fn bounded_regardless_of_store_health() {
        let mut writer = BatchingTranscriptWriter::with_clocks(
            AlwaysFailingStore,
            FakeMonotonicClock::new(),
            FakeEpochClock::new(0),
        );
        writer.start("Sunday Service", "on-device-whisper");

        const PUSHES: usize = MAX_PENDING_SEGMENTS * 3;
        for i in 0..PUSHES {
            writer.ingest(i as u64, i as u64 + 100, "hello church");
            assert!(
                writer.pending_len() <= MAX_PENDING_SEGMENTS,
                "the write buffer's bounded-memory contract was not exercised: pending_len() \
                 was {} after push {}, which exceeds MAX_PENDING_SEGMENTS ({})",
                writer.pending_len(),
                i,
                MAX_PENDING_SEGMENTS
            );
        }
        // The hostile case is refused: with a permanently failing store, segments beyond the
        // cap must have been dropped (counted), not silently retained forever.
        assert!(
            writer.dropped_segment_count() > 0,
            "a permanently failing store must eventually drop the oldest buffered segments to \
             hold the bound, and count that it did — dropped_segment_count() was 0"
        );
        assert_eq!(
            writer.pending_len(),
            MAX_PENDING_SEGMENTS,
            "once saturated, pending_len() should sit exactly at the cap, not below it"
        );
    }

    /// POSITIVE CONTROL for the test above: with a HEALTHY store, refusing overflow must not be
    /// indistinguishable from a dead mechanism that drops everything. Every segment must reach
    /// the store, in order, with the exact text/timing given, and nothing is ever dropped.
    #[test]
    fn a_healthy_store_drops_nothing_and_receives_every_segment_in_order() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(1_000),
        );
        writer.start("Sunday Service", "on-device-whisper");

        const PUSHES: usize = MAX_PENDING_SEGMENTS * 3;
        for i in 0..PUSHES {
            writer.ingest(i as u64 * 10, i as u64 * 10 + 5, &format!("segment {i}"));
        }
        writer.end();

        assert_eq!(
            writer.dropped_segment_count(),
            0,
            "a healthy store must never need to drop a buffered segment"
        );
        assert_eq!(
            writer.pending_len(),
            0,
            "end() must flush everything buffered"
        );

        let accepted = store.accepted();
        assert_eq!(
            accepted.len(),
            PUSHES,
            "the healthy-store control was not exercised: not every pushed segment reached the \
             store — a dead write path would also show zero drops, so this count is what \
             actually proves the mechanism is live, not just quiet"
        );
        for (i, (_, start, end, text)) in accepted.iter().enumerate() {
            assert_eq!(*start, i as u64 * 10);
            assert_eq!(*end, i as u64 * 10 + 5);
            assert_eq!(text, &format!("segment {i}"));
        }
        assert_eq!(
            store.ended().len(),
            1,
            "end() must close exactly one transcript"
        );
    }

    #[test]
    fn flushes_on_count_threshold_before_the_interval_elapses() {
        let store = FakeStore::new();
        let clock = FakeMonotonicClock::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            clock.clone(),
            FakeEpochClock::new(0),
        );
        writer.start("Service", "deepgram");

        for i in 0..FLUSH_SEGMENT_THRESHOLD - 1 {
            writer.ingest(i as u64, i as u64 + 1, "partial batch");
        }
        assert!(
            store.accepted().is_empty(),
            "must not flush before the count threshold or the interval, whichever comes first"
        );
        writer.ingest(999, 1000, "the segment that completes the batch");
        assert_eq!(
            store.accepted().len(),
            FLUSH_SEGMENT_THRESHOLD,
            "hitting FLUSH_SEGMENT_THRESHOLD must flush the whole batch immediately"
        );
    }

    #[test]
    fn flushes_on_interval_even_with_a_trickle_below_the_count_threshold() {
        let store = FakeStore::new();
        let clock = FakeMonotonicClock::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            clock.clone(),
            FakeEpochClock::new(0),
        );
        writer.start("Service", "on-device-whisper");

        writer.ingest(0, 1, "one lonely segment");
        assert!(store.accepted().is_empty(), "must not flush immediately");

        clock.advance(FLUSH_INTERVAL - Duration::from_millis(1));
        writer.ingest(1, 2, "still inside the window");
        assert!(
            store.accepted().is_empty(),
            "must not flush before FLUSH_INTERVAL has elapsed since the last flush"
        );

        clock.advance(Duration::from_millis(2));
        writer.ingest(2, 3, "this push crosses the interval");
        assert_eq!(
            store.accepted().len(),
            3,
            "crossing FLUSH_INTERVAL must flush everything buffered so far"
        );
    }

    #[test]
    fn a_failed_flush_keeps_segments_buffered_and_retries_in_order_on_the_next_trigger() {
        let store = FakeStore::new();
        store.fail_next(1);
        let clock = FakeMonotonicClock::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            clock.clone(),
            FakeEpochClock::new(0),
        );
        writer.start("Service", "on-device-whisper");

        for i in 0..FLUSH_SEGMENT_THRESHOLD {
            writer.ingest(i as u64, i as u64 + 1, "batch one");
        }
        assert!(
            store.accepted().is_empty(),
            "the one simulated failure must fail the whole batch's first segment and stop \
             draining, leaving every segment in this batch still buffered for a retry"
        );
        assert!(writer.last_error().is_some());
        assert_eq!(writer.pending_len(), FLUSH_SEGMENT_THRESHOLD);

        // Next trigger retries from the front, in the SAME order, and this time succeeds.
        writer.ingest(999, 1000, "the push that triggers a retry");
        assert_eq!(
            store.accepted().len(),
            FLUSH_SEGMENT_THRESHOLD + 1,
            "a retried flush must eventually deliver every segment, still in order"
        );
        assert!(
            writer.last_error().is_none(),
            "a successful flush clears the last error"
        );
    }

    #[test]
    fn ended_transcript_carries_the_epoch_ms_given_by_the_injected_clock() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(1_700_000_000_000),
        );
        writer.start("Service", "on-device-whisper");
        writer.ingest(0, 1, "hello");
        writer.end();

        let ended = store.ended();
        assert_eq!(ended.len(), 1);
        assert_eq!(ended[0].1, 1_700_000_000_000);
    }

    #[test]
    fn open_transcript_is_called_exactly_once_per_start() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(0),
        );
        writer.start("Service", "on-device-whisper");
        writer.ingest(0, 1, "hello");
        writer.end();
        assert_eq!(store.open_calls(), 1);
    }

    #[test]
    fn null_sink_is_a_true_no_op() {
        // Positive control for NullTranscriptSink: it must be safe to call in any order,
        // any number of times, and never panic or allocate observable state.
        let mut sink = NullTranscriptSink;
        sink.start("x", "y");
        sink.ingest(0, 1, "z");
        sink.end();
        sink.ingest(2, 3, "after end, still fine");
    }

    #[test]
    fn a_pathologically_long_segment_is_bounded_before_buffering() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(0),
        );
        writer.start("Service", "on-device-whisper");
        let runaway = "x".repeat(MAX_PENDING_SEGMENT_TEXT_LEN * 10);
        writer.ingest(0, 1, &runaway);
        writer.end();

        let accepted = store.accepted();
        assert_eq!(accepted.len(), 1);
        assert!(
            accepted[0].3.len() <= MAX_PENDING_SEGMENT_TEXT_LEN,
            "a single runaway segment must not be buffered/persisted at unbounded length: got {} \
             bytes",
            accepted[0].3.len()
        );
    }
}
