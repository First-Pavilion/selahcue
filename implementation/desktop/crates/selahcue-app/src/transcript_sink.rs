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
    /// The listening session ended (normal Stop Listening). Production queues final flush/close;
    /// an ACK is not durable completion. Observe `TranscriptCompletion` outside control locks.
    /// A crash that skips this call is handled separately, by a startup sweep over transcripts
    /// left with no `ended_at` (see the desktop binary's wiring) — not by anything in this trait.
    fn end(&mut self);
    /// Memory-only status; unavailable is the safe default for custom/no-op sinks.
    fn health(&self) -> TranscriptStorageHealth {
        TranscriptStorageHealth::default()
    }
    fn session_status(&self) -> TranscriptSessionStatus {
        TranscriptSessionStatus::default()
    }
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
    truncated_segment_count: u64,
    session_status: TranscriptSessionStatus,
    last_error: Option<String>,
}

impl<S: TranscriptStoreWriter> BatchingTranscriptWriter<S, SystemMonotonicClock, SystemEpochClock> {
    /// Construct the synchronous policy helper with real OS clocks. Production uses the worker.
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
            truncated_segment_count: 0,
            session_status: TranscriptSessionStatus::default(),
            last_error: None,
        }
    }

    /// Number of segments buffered but not yet confirmed written. NEVER exceeds
    /// [`MAX_PENDING_SEGMENTS`] — see `bounded_regardless_of_store_health` in this crate's tests.
    pub fn pending_len(&self) -> usize {
        self.pending.len()
    }

    /// How many segments this writer has ever had to drop instead of persisting them — a
    /// LIFETIME count for this writer (never reset by `start()`), covering every way a
    /// segment can be lost: the bound above being held against a failing store
    /// (oldest-first), a segment ingested with no session open (nothing to attribute it to),
    /// and a segment still unflushed when its session closed. Zero under a healthy store used
    /// as documented (a `start()`/`ingest()`/`end()` sequence with no gaps).
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
            // Nothing open. `pending` should be empty here by construction — `ingest` (below)
            // refuses to buffer a segment with no open transcript in the first place, so there
            // is nothing to attribute a flush to and nothing this call needs to do.
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
                Err(_) => {
                    self.last_error = Some("transcript storage unavailable".into());
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
            self.dropped_segment_count = self.dropped_segment_count.saturating_add(1);
        }
    }
}

impl<S: TranscriptStoreWriter, M: MonotonicClock, E: EpochClock> BatchingTranscriptWriter<S, M, E> {
    /// Flush and end whatever transcript is currently open, if any — a no-op if none is.
    /// Shared by [`TranscriptSink::end`] and [`TranscriptSink::start`] so a `start()` that
    /// finds a session already open can never silently discard it (PR #31 review, Sana F1: a
    /// bare `start()` used to clear `pending` and drop the transcript id unconditionally,
    /// losing every unflushed segment of whatever was open — reachable both by a legitimate
    /// operator-process restart mid-service and, since RBAC does not track "is a session
    /// already open" state, by any two `StartTranscript` commands in a row from a paired
    /// Producer/Operator). This makes "close whatever's open" the ONE code path either
    /// caller goes through, so a future change to closing logic cannot fix one and miss
    /// the other.
    fn close_current(&mut self) {
        self.flush();
        self.enforce_bound();
        if let Some(id) = self.transcript_id.take() {
            if self.store.end_transcript(id, self.epoch.now_ms()).is_err() {
                self.last_error = Some("transcript storage unavailable".into());
            }
        }
        // Anything still buffered here means the store kept refusing it even through the
        // flush above (a persistently failing store) — count it as dropped, never silently
        // discard it, mirroring `enforce_bound`'s own count-on-drop discipline. Under a
        // healthy store this is always empty already.
        self.dropped_segment_count = self
            .dropped_segment_count
            .saturating_add(self.pending.len() as u64);
        self.pending.clear();
    }
}

impl<S: TranscriptStoreWriter + Send, M: MonotonicClock, E: EpochClock> TranscriptSink
    for BatchingTranscriptWriter<S, M, E>
{
    fn start(&mut self, label: &str, provider: &str) {
        // A `start()` while a transcript is ALREADY open must never silently discard it (Sana,
        // PR #31 F1) — close it out properly first: flush its pending segments, end it, and
        // count anything that still could not be flushed. See `close_current`'s own doc.
        self.close_current();
        self.session_status.generation = self.session_status.generation.saturating_add(1);
        self.session_status.confirmed_id = None;
        // Deliberately NOT clearing `last_error` or `dropped_segment_count`: `close_current()`
        // just above may have set/incremented either (the previous session's close failed to
        // flush or end cleanly), and that is exactly the moment a caller most needs to still
        // see it — both are lifetime counters/latches for this writer, not per-session ones,
        // cleared only by their own natural mechanism (a later successful flush clears
        // `last_error`; `dropped_segment_count` never auto-clears, same as e.g. this
        // codebase's other saturating lifetime counters).
        self.last_flush_at = Some(self.monotonic.now());
        match self
            .store
            .open_transcript(label, provider, self.epoch.now_ms())
        {
            Ok(id) => {
                self.transcript_id = Some(id);
                self.session_status.confirmed_id = Some(id);
            }
            Err(_) => {
                self.transcript_id = None;
                self.last_error = Some("transcript storage unavailable".into());
            }
        }
    }

    fn ingest(&mut self, start_ms: u64, end_ms: u64, text: &str) {
        if self.transcript_id.is_none() {
            // No session open — there is nothing to durably attribute this segment to.
            // Buffering it "for whichever session starts next" (the previous design) would
            // silently mis-attribute it to an unrelated future session, or vanish entirely if
            // that session's own `start()`/`close_current()` cleared the buffer first (Sana,
            // PR #31 F1, probe B). Counting it as dropped makes the loss honest and visible
            // instead of a queue nothing is actually consuming.
            self.dropped_segment_count = self.dropped_segment_count.saturating_add(1);
            return;
        }
        if text.len() > MAX_PENDING_SEGMENT_TEXT_LEN {
            self.truncated_segment_count = self.truncated_segment_count.saturating_add(1);
        }
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
        self.close_current();
    }
    fn health(&self) -> TranscriptStorageHealth {
        TranscriptStorageHealth {
            available: self.session_status.confirmed_id.is_some()
                && self.last_error.is_none()
                && self.dropped_segment_count == 0
                && self.truncated_segment_count == 0,
            pending_segments: self.pending.len(),
            dropped_segments: self.dropped_segment_count,
            truncated_segments: self.truncated_segment_count,
        }
    }
    fn session_status(&self) -> TranscriptSessionStatus {
        self.session_status
    }
}

/// Content-free, memory-only lifetime health. Pending includes the in-flight append.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct TranscriptStorageHealth {
    pub available: bool,
    pub pending_segments: usize,
    pub dropped_segments: u64,
    pub truncated_segments: u64,
}

/// The last requested generation, including an opening/failed (unconfirmed) session.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct TranscriptSessionStatus {
    pub generation: u64,
    pub confirmed_id: Option<i64>,
}

/// Bounded metadata per admitted session, independent of the global segment budget.
pub const MAX_PENDING_SESSIONS: usize = 64;
pub const MAX_SESSION_METADATA_BYTES: usize = 1024;

struct Session {
    generation: u64,
    label: String,
    provider: String,
    started_at: i64,
    ended_at: Option<i64>,
    opened: bool,
    id: Option<i64>,
    last_attempt: Instant,
    retry: bool,
    flushing: bool,
}

struct WorkerState {
    sessions: VecDeque<Session>,
    pending: VecDeque<(u64, PendingSegment)>,
    in_flight: bool,
    busy: bool,
    current: TranscriptSessionStatus,
    active: Option<u64>,
    io_available: bool,
    dropped: u64,
    truncated: u64,
    alive: bool,
    stop: bool,
    monotonic: Box<dyn MonotonicClock>,
    epoch: Box<dyn EpochClock>,
}
impl WorkerState {
    fn health(&self) -> TranscriptStorageHealth {
        TranscriptStorageHealth {
            available: self.alive
                && self.io_available
                && self.current.confirmed_id.is_some()
                && !self.sessions.iter().any(|session| {
                    session.generation == self.current.generation && session.ended_at.is_some()
                })
                && self.dropped == 0
                && self.truncated == 0,
            pending_segments: self.pending.len() + usize::from(self.in_flight),
            dropped_segments: self.dropped,
            truncated_segments: self.truncated,
        }
    }
    fn discard(&mut self, generation: u64) {
        let before = self.pending.len();
        self.pending.retain(|(g, _)| *g != generation);
        self.dropped = self
            .dropped
            .saturating_add((before - self.pending.len()) as u64);
    }
    fn end_active(&mut self) {
        if let Some(generation) = self.active.take() {
            let now = self.epoch.now_ms();
            if let Some(s) = self
                .sessions
                .iter_mut()
                .find(|s| s.generation == generation)
            {
                s.ended_at = Some(now);
            }
        }
    }
}
struct WorkerShared {
    state: std::sync::Mutex<WorkerState>,
    changed: std::sync::Condvar,
}
impl WorkerShared {
    fn lock(&self) -> std::sync::MutexGuard<'_, WorkerState> {
        self.state.lock().unwrap_or_else(|e| e.into_inner())
    }
}

/// Observation for clean shutdown/tests OUTSIDE the controller lock. An End ACK only queues
/// closure. A timeout is an observation, never cancellation or a claim of durable completion.
#[derive(Clone)]
pub struct TranscriptCompletion(std::sync::Arc<WorkerShared>);
impl TranscriptCompletion {
    pub fn wait_closed(&self, generation: u64, timeout: Duration) -> bool {
        self.wait(timeout, |s| {
            !s.sessions.iter().any(|v| v.generation <= generation)
        })
    }
    /// Wait for all admitted speech and opening work. Does not force a premature batch flush.
    pub fn wait_idle(&self, timeout: Duration) -> bool {
        self.wait(timeout, |s| {
            !s.busy && s.pending.is_empty() && s.sessions.iter().all(|v| v.opened)
        })
    }
    fn wait(&self, timeout: Duration, done: impl Fn(&WorkerState) -> bool) -> bool {
        let state = self.0.lock();
        let (state, _) = self
            .0
            .changed
            .wait_timeout_while(state, timeout, |s| s.alive && !done(s))
            .unwrap_or_else(|e| e.into_inner());
        done(&state)
    }
    /// Wake the deadline evaluator after an injected monotonic clock advances.
    pub fn wake(&self) {
        self.0.changed.notify_all();
    }
    pub fn health(&self) -> TranscriptStorageHealth {
        self.0.lock().health()
    }
}

/// One persistent store worker. The only transcript text queue is in `WorkerState`; moving a
/// segment into a store call retains its permit. No sink method/Drop waits for disk or joins.
pub struct BackgroundTranscriptWriter {
    shared: std::sync::Arc<WorkerShared>,
}
impl BackgroundTranscriptWriter {
    pub fn new<S: TranscriptStoreWriter + Send + 'static>(store: S) -> Self {
        Self::from_factory(move || Ok(store))
    }
    /// The factory (including connection open/orphan sweep) runs on the storage worker.
    pub fn from_factory<S, F>(factory: F) -> Self
    where
        S: TranscriptStoreWriter + Send + 'static,
        F: FnOnce() -> Result<S, String> + Send + 'static,
    {
        Self::with_clocks(factory, SystemMonotonicClock, SystemEpochClock)
    }
    pub fn with_clocks<S, F, M, E>(factory: F, monotonic: M, epoch: E) -> Self
    where
        S: TranscriptStoreWriter + Send + 'static,
        F: FnOnce() -> Result<S, String> + Send + 'static,
        M: MonotonicClock + 'static,
        E: EpochClock + 'static,
    {
        let shared = std::sync::Arc::new(WorkerShared {
            state: std::sync::Mutex::new(WorkerState {
                sessions: VecDeque::new(),
                pending: VecDeque::new(),
                in_flight: false,
                busy: false,
                current: TranscriptSessionStatus::default(),
                active: None,
                io_available: false,
                dropped: 0,
                truncated: 0,
                alive: true,
                stop: false,
                monotonic: Box::new(monotonic),
                epoch: Box::new(epoch),
            }),
            changed: std::sync::Condvar::new(),
        });
        let worker = shared.clone();
        let result = std::thread::Builder::new()
            .name("transcript-storage".into())
            .spawn(move || {
                // A panicking adapter must not leave a forever-healthy snapshot or hanging barrier.
                let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    if let Ok(mut store) = factory() {
                        run_transcript_worker(&worker, &mut store);
                    }
                }));
                let mut s = worker.lock();
                s.dropped = s
                    .dropped
                    .saturating_add(s.pending.len() as u64 + u64::from(s.in_flight));
                s.pending.clear();
                s.sessions.clear();
                s.in_flight = false;
                s.busy = false;
                s.alive = false;
                s.io_available = false;
                s.active = None;
                worker.changed.notify_all();
            });
        if result.is_err() {
            shared.lock().alive = false;
        }
        Self { shared }
    }
    pub fn completion(&self) -> TranscriptCompletion {
        TranscriptCompletion(self.shared.clone())
    }
}
impl TranscriptSink for BackgroundTranscriptWriter {
    fn start(&mut self, label: &str, provider: &str) {
        let mut s = self.shared.lock();
        s.end_active();
        s.current.confirmed_id = None;
        let next = s.current.generation.checked_add(1);
        if let Some(next) = next {
            s.current.generation = next;
        }
        if next.is_none()
            || !s.alive
            || s.stop
            || s.sessions.len() >= MAX_PENDING_SESSIONS
            || label.len() > MAX_SESSION_METADATA_BYTES
            || provider.len() > MAX_SESSION_METADATA_BYTES
        {
            s.io_available = false;
        } else {
            let generation = s.current.generation;
            let started_at = s.epoch.now_ms();
            let last_attempt = s.monotonic.now();
            s.sessions.push_back(Session {
                generation,
                label: label.to_owned(),
                provider: provider.to_owned(),
                started_at,
                ended_at: None,
                opened: false,
                id: None,
                last_attempt,
                retry: false,
                flushing: false,
            });
            s.active = Some(generation);
        }
        self.shared.changed.notify_all();
    }
    fn ingest(&mut self, start_ms: u64, end_ms: u64, text: &str) {
        let mut s = self.shared.lock();
        let generation = s
            .active
            .filter(|g| s.alive && s.sessions.iter().any(|v| v.generation == *g));
        let Some(generation) = generation else {
            s.dropped = s.dropped.saturating_add(1);
            return;
        };
        if s.pending.len() + usize::from(s.in_flight) >= MAX_PENDING_SEGMENTS {
            s.dropped = s.dropped.saturating_add(1);
            if s.pending.pop_front().is_none() {
                return;
            }
        }
        if text.len() > MAX_PENDING_SEGMENT_TEXT_LEN {
            s.truncated = s.truncated.saturating_add(1);
        }
        s.pending.push_back((
            generation,
            PendingSegment {
                start_ms,
                end_ms,
                text: bounded_text(text, MAX_PENDING_SEGMENT_TEXT_LEN),
            },
        ));
        self.shared.changed.notify_all();
    }
    fn end(&mut self) {
        self.shared.lock().end_active();
        self.shared.changed.notify_all();
    }
    fn health(&self) -> TranscriptStorageHealth {
        self.shared.lock().health()
    }
    fn session_status(&self) -> TranscriptSessionStatus {
        self.shared.lock().current
    }
}
impl Drop for BackgroundTranscriptWriter {
    fn drop(&mut self) {
        let mut s = self.shared.lock();
        s.end_active();
        s.stop = true;
        self.shared.changed.notify_all();
    }
}

enum StoreOperation {
    Open(u64, String, String, i64),
    Append(u64, i64, PendingSegment),
    End(u64, i64, i64),
}
fn run_transcript_worker(shared: &WorkerShared, store: &mut impl TranscriptStoreWriter) {
    loop {
        let op = {
            let mut s = shared.lock();
            loop {
                let now = s.monotonic.now();
                let mut wait = FLUSH_INTERVAL;
                if let Some(front) = s.sessions.front() {
                    let generation = front.generation;
                    if !front.opened {
                        let op = StoreOperation::Open(
                            generation,
                            front.label.clone(),
                            front.provider.clone(),
                            front.started_at,
                        );
                        if let Some(v) = s.sessions.front_mut() {
                            v.opened = true;
                        }
                        s.busy = true;
                        break op;
                    }
                    let count = s
                        .pending
                        .iter()
                        .take_while(|(g, _)| *g == generation)
                        .count();
                    let due = now.saturating_duration_since(front.last_attempt) >= FLUSH_INTERVAL;
                    let closing = front.ended_at.is_some();
                    let flush = closing
                        || due
                        || (!front.retry && (front.flushing || count >= FLUSH_SEGMENT_THRESHOLD));
                    if let Some(id) = front.id {
                        if count > 0 && flush {
                            let (_, segment) =
                                s.pending.pop_front().expect("counted pending segment");
                            s.in_flight = true;
                            s.busy = true;
                            if let Some(v) = s.sessions.front_mut() {
                                v.flushing = true;
                            }
                            break StoreOperation::Append(generation, id, segment);
                        }
                        if count == 0 && closing {
                            let end = front.ended_at.expect("closing session");
                            s.busy = true;
                            break StoreOperation::End(generation, id, end);
                        }
                    }
                    if count > 0 {
                        wait = FLUSH_INTERVAL
                            .saturating_sub(now.saturating_duration_since(front.last_attempt));
                    }
                } else if s.stop {
                    return;
                }
                s = shared
                    .changed
                    .wait_timeout(s, wait)
                    .unwrap_or_else(|e| e.into_inner())
                    .0;
            }
        };
        // Deliberately outside ALL shared locks, including factory, open, append and end.
        match op {
            StoreOperation::Open(generation, label, provider, start) => {
                let result = store.open_transcript(&label, &provider, start);
                let mut s = shared.lock();
                s.busy = false;
                match result {
                    Ok(id) => {
                        if let Some(front) = s.sessions.front_mut() {
                            front.id = Some(id);
                        }
                        if s.current.generation == generation {
                            s.current.confirmed_id = Some(id);
                        }
                        s.io_available = true;
                    }
                    Err(_) => {
                        s.io_available = false;
                        s.discard(generation);
                        s.sessions.pop_front();
                        if s.active == Some(generation) {
                            s.active = None;
                        }
                    }
                }
            }
            StoreOperation::Append(generation, id, segment) => {
                let result =
                    store.append_segment(id, segment.start_ms, segment.end_ms, &segment.text);
                let mut s = shared.lock();
                s.busy = false;
                s.in_flight = false;
                let now = s.monotonic.now();
                let closing = s.sessions.front().is_some_and(|v| v.ended_at.is_some());
                match result {
                    Ok(_) => {
                        s.io_available = true;
                    }
                    Err(_) => {
                        s.io_available = false;
                        if closing {
                            s.dropped = s.dropped.saturating_add(1);
                            s.discard(generation);
                        } else {
                            s.pending.push_front((generation, segment));
                        }
                    }
                }
                let remaining = s.pending.front().is_some_and(|(g, _)| *g == generation);
                let success = s.io_available;
                if let Some(front) = s.sessions.front_mut() {
                    front.last_attempt = now;
                    front.retry = !success;
                    front.flushing = success && remaining;
                }
            }
            StoreOperation::End(_generation, id, end) => {
                let result = store.end_transcript(id, end);
                let mut s = shared.lock();
                s.busy = false;
                // A successful end cannot erase a preceding failed append's I/O state.
                if result.is_err() {
                    s.io_available = false;
                }
                s.sessions.pop_front();
            }
        }
        shared.changed.notify_all();
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

    /// Regression for PR #31 review (Sana F1, probe A): `start()` while a transcript is
    /// ALREADY open must flush + end the previous one, never silently discard it.
    #[test]
    fn starting_a_new_session_while_one_is_open_flushes_and_ends_the_previous_one_first() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(1_000),
        );
        writer.start("Sunday AM", "on-device-whisper");
        // Below FLUSH_SEGMENT_THRESHOLD, so nothing has flushed yet — still buffered when the
        // second start() arrives.
        for i in 0..FLUSH_SEGMENT_THRESHOLD - 1 {
            writer.ingest(i as u64, i as u64 + 1, "grace and peace");
        }
        assert_eq!(
            store.accepted().len(),
            0,
            "nothing flushed yet — this is the setup"
        );

        writer.start("Sunday PM", "on-device-whisper");

        assert_eq!(
            store.accepted().len(),
            FLUSH_SEGMENT_THRESHOLD - 1,
            "the first session's buffered segments must have been flushed before the second \
             session opened, not discarded"
        );
        assert_eq!(
            store.ended().len(),
            1,
            "the first session must have been properly ended, not left dangling"
        );
        assert_eq!(
            writer.dropped_segment_count(),
            0,
            "a healthy store must lose nothing across a start-while-open"
        );
        assert_eq!(
            store.open_calls(),
            2,
            "and the second session must have genuinely opened"
        );
    }

    /// Regression for PR #31 review (Sana F1, probe B): a segment ingested with NO session
    /// open (e.g. after `end()`, before the next `start()`) must be counted as dropped, not
    /// silently buffered where a later `start()` would discard it unnoticed.
    #[test]
    fn a_segment_ingested_with_no_session_open_is_counted_as_dropped_not_silently_lost() {
        let store = FakeStore::new();
        let mut writer = BatchingTranscriptWriter::with_clocks(
            store.clone(),
            FakeMonotonicClock::new(),
            FakeEpochClock::new(1_000),
        );
        writer.start("Sunday AM", "on-device-whisper");
        writer.end();
        assert_eq!(writer.dropped_segment_count(), 0);

        // No session open here — these must not vanish into a buffer nothing will ever flush.
        for i in 0..74 {
            writer.ingest(i, i + 1, "orphaned tail audio");
        }
        assert_eq!(
            writer.dropped_segment_count(),
            74,
            "every orphaned ingest must be counted as dropped, immediately — not queued"
        );
        assert_eq!(
            writer.pending_len(),
            0,
            "nothing should be buffered with no session open"
        );

        writer.start("Sunday PM", "on-device-whisper");
        writer.ingest(0, 1, "a genuinely new segment");
        writer.end();

        let accepted = store.accepted();
        assert_eq!(
            accepted.len(),
            1,
            "the second session must contain only its OWN segment, not any orphaned ones"
        );
        assert_eq!(accepted[0].3, "a genuinely new segment");
        assert_eq!(
            writer.dropped_segment_count(),
            74,
            "the drop count must still show the earlier loss after a later, healthy session"
        );
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
