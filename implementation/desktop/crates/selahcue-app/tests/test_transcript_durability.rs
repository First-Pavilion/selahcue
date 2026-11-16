//! 86akcfftu: the durable transcript side-channel, exercised end-to-end through
//! `LiveController` — the live ring's behaviour is unchanged (regression) while a durable
//! sink independently retains everything the ring would otherwise evict, regardless of which
//! `TranscriptProvider` produced a segment, and `ControllerSnapshot` stays untouched.

#![allow(clippy::unwrap_used)]

use selahcue_app::{pump_transcript, LiveController, TranscriptSink};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_core::transcript::{
    ManualProvider, ProviderSegment, TranscriptProvider, MAX_SEGMENT_TEXT_LEN,
    MAX_TRANSCRIPT_SEGMENTS,
};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};
use std::time::Instant;

fn controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Section, "Sermon");
    LiveController::new(plan, 320, 180, Theme::dark())
}

/// A recording spy `TranscriptSink`: keeps everything it was told, in call order, so a test
/// can assert the EXACT entity persisted (per CLAUDE.md's bounded-memory-test standard: never
/// a proxy like a count alone when the actual content is what matters here).
#[derive(Clone, Default)]
struct SpySink(Arc<Mutex<SpyState>>);

#[derive(Default)]
struct SpyState {
    started: Vec<(String, String)>,
    segments: Vec<(u64, u64, String)>,
    ended: u32,
}

impl SpySink {
    fn new() -> Self {
        Self::default()
    }
    fn segments(&self) -> Vec<(u64, u64, String)> {
        self.0.lock().unwrap().segments.clone()
    }
    fn started(&self) -> Vec<(String, String)> {
        self.0.lock().unwrap().started.clone()
    }
    fn ended_count(&self) -> u32 {
        self.0.lock().unwrap().ended
    }
}

impl TranscriptSink for SpySink {
    fn start(&mut self, label: &str, provider: &str) {
        self.0
            .lock()
            .unwrap()
            .started
            .push((label.to_string(), provider.to_string()));
    }
    fn ingest(&mut self, start_ms: u64, end_ms: u64, text: &str) {
        self.0
            .lock()
            .unwrap()
            .segments
            .push((start_ms, end_ms, text.to_string()));
    }
    fn end(&mut self) {
        self.0.lock().unwrap().ended += 1;
    }
}

/// A second, independent fake `TranscriptProvider` — deliberately NOT `ManualProvider` — so the
/// provider-agnostic assertions below cannot pass merely because the controller happens to
/// special-case the one concrete type every other test in this crate already uses.
struct SecondFakeProvider {
    queued: Vec<ProviderSegment>,
}
impl SecondFakeProvider {
    fn new() -> Self {
        Self { queued: Vec::new() }
    }
    fn queue_final(&mut self, text: &str, start_ms: u64, end_ms: u64) {
        self.queued
            .push(ProviderSegment::final_text(text, start_ms, end_ms));
    }
}
impl TranscriptProvider for SecondFakeProvider {
    fn label(&self) -> &str {
        "second-fake-provider"
    }
    fn poll(&mut self) -> Vec<ProviderSegment> {
        std::mem::take(&mut self.queued)
    }
}

// ---------------------------------------------------------------------------------------
// AC: every segment durably persisted, in order, before the ring's 240-segment eviction
// would have dropped it — verified by reading the durable copy back AFTER the ring has
// evicted those same segments from its own view.
// ---------------------------------------------------------------------------------------
#[test]
fn a_long_service_keeps_its_opening_in_the_durable_copy_after_the_ring_evicts_it() {
    let mut c = controller();
    let sink = SpySink::new();
    c.set_transcript_sink(Box::new(sink.clone()));
    c.start_transcript_session("Sunday Service", "on-device-whisper");

    const TOTAL: usize = MAX_TRANSCRIPT_SEGMENTS + 60; // comfortably past the ring's cap
    for i in 0..TOTAL {
        c.ingest_transcript(
            &format!("segment {i}"),
            i as u64 * 10,
            i as u64 * 10 + 5,
            true,
        );
    }

    // The ring is UNCHANGED (regression): still capped at MAX_TRANSCRIPT_SEGMENTS, and its
    // oldest retained segment is no longer "segment 0" — eviction genuinely happened, exactly
    // as it does today.
    let ring: Vec<_> = c.transcript_engine().transcript().segments().collect();
    assert_eq!(
        ring.len(),
        MAX_TRANSCRIPT_SEGMENTS,
        "the live ring's cap must be unchanged by adding a durable side-channel"
    );
    assert_eq!(
        ring.first().unwrap().text,
        format!("segment {}", TOTAL - MAX_TRANSCRIPT_SEGMENTS),
        "the ring must have evicted its opening exactly as it does today"
    );
    assert!(
        !ring.iter().any(|s| s.text == "segment 0"),
        "positive control: the ring must NOT still hold the opening segment — otherwise this \
         test would not be exercising eviction at all"
    );

    // The DURABLE copy has everything, including what the ring just evicted.
    let durable = sink.segments();
    assert_eq!(
        durable.len(),
        TOTAL,
        "the durable sink must have received every segment produced, not just the ring's tail"
    );
    assert_eq!(
        durable[0].2, "segment 0",
        "the transcript's opening must survive in the durable copy after the ring evicted it \
         — this is the ticket's core acceptance criterion"
    );
    for (i, (start, end, text)) in durable.iter().enumerate() {
        assert_eq!(*start, i as u64 * 10);
        assert_eq!(*end, i as u64 * 10 + 5);
        assert_eq!(text, &format!("segment {i}"));
    }
}

// ---------------------------------------------------------------------------------------
// Regression: the live ring's per-segment 2,000-char cap is unchanged — but the durable
// copy does NOT inherit it (the whole point of a side-channel that doesn't share the live
// view's bounds).
// ---------------------------------------------------------------------------------------
#[test]
fn the_rings_per_segment_text_cap_is_unchanged_while_the_durable_copy_keeps_the_full_text() {
    let mut c = controller();
    let sink = SpySink::new();
    c.set_transcript_sink(Box::new(sink.clone()));
    c.start_transcript_session("Sunday Service", "on-device-whisper");

    let long_text = "a".repeat(MAX_SEGMENT_TEXT_LEN + 3_000);
    c.ingest_transcript(&long_text, 0, 1_000, true);

    let ring: Vec<_> = c.transcript_engine().transcript().segments().collect();
    assert_eq!(ring.len(), 1);
    assert_eq!(
        ring[0].text.len(),
        MAX_SEGMENT_TEXT_LEN,
        "regression: the ring's per-segment cap (MAX_SEGMENT_TEXT_LEN) must be unchanged"
    );

    let durable = sink.segments();
    assert_eq!(durable.len(), 1);
    assert_eq!(
        durable[0].2.len(),
        long_text.len(),
        "the durable copy must not be truncated to the ring's live-view cap"
    );
}

// ---------------------------------------------------------------------------------------
// Regression: a streaming INTERIM segment reaches neither the ring nor the durable sink —
// unchanged behaviour, now proven for the sink too.
// ---------------------------------------------------------------------------------------
#[test]
fn an_interim_segment_reaches_neither_the_ring_nor_the_durable_sink() {
    let mut c = controller();
    let sink = SpySink::new();
    c.set_transcript_sink(Box::new(sink.clone()));
    c.start_transcript_session("Sunday Service", "on-device-whisper");

    c.ingest_transcript("still speaking", 0, 500, false);

    assert_eq!(c.transcript_engine().transcript().len(), 0);
    assert!(sink.segments().is_empty());
}

// ---------------------------------------------------------------------------------------
// AC: the capture path does not care which TranscriptProvider produced a segment — proven
// with a SECOND, independent fake provider (not just ManualProvider, which every other test
// in this crate already special-cases).
// ---------------------------------------------------------------------------------------
#[test]
fn the_durable_sink_is_fed_identically_regardless_of_which_provider_produced_the_segment() {
    let mut c_manual = controller();
    let sink_manual = SpySink::new();
    c_manual.set_transcript_sink(Box::new(sink_manual.clone()));
    let mut manual = ManualProvider::new();
    manual.submit("grace and peace to you", 0, 2_000);
    let n_manual = pump_transcript(&mut c_manual, &mut manual);

    let mut c_second = controller();
    let sink_second = SpySink::new();
    c_second.set_transcript_sink(Box::new(sink_second.clone()));
    let mut second = SecondFakeProvider::new();
    second.queue_final("grace and peace to you", 0, 2_000);
    let n_second = pump_transcript(&mut c_second, &mut second);

    assert_eq!(
        n_manual, n_second,
        "both providers must ingest the same number of segments"
    );
    assert_eq!(
        sink_manual.segments(),
        sink_second.segments(),
        "the durable sink must receive an identically-shaped segment regardless of which \
         TranscriptProvider produced it — ingest_transcript never sees provider identity"
    );
}

// ---------------------------------------------------------------------------------------
// The wire command dispatch (`apply`) reaches the sink too, not just the direct method —
// this is the real production path for a remote/host-authoritative controller.
// ---------------------------------------------------------------------------------------
#[test]
fn start_and_end_transcript_commands_reach_the_sink_through_apply() {
    use selahcue_lan::protocol::Command;

    let mut c = controller();
    let sink = SpySink::new();
    c.set_transcript_sink(Box::new(sink.clone()));

    let reply = c.apply(&Command::StartTranscript {
        label: "Sunday Service".into(),
        provider: "deepgram".into(),
    });
    assert!(matches!(reply, selahcue_app::ControllerReply::Ack));
    assert_eq!(
        sink.started(),
        vec![("Sunday Service".to_string(), "deepgram".to_string())]
    );

    let reply = c.apply(&Command::IngestTranscript {
        text: "hello church".into(),
        start_ms: Some(0),
        end_ms: Some(1_000),
        is_final: true,
    });
    assert!(matches!(reply, selahcue_app::ControllerReply::Ack));
    assert_eq!(sink.segments().len(), 1);

    let reply = c.apply(&Command::EndTranscript);
    assert!(matches!(reply, selahcue_app::ControllerReply::Ack));
    assert_eq!(sink.ended_count(), 1);
}

// ---------------------------------------------------------------------------------------
// Regression + positive control: ControllerSnapshot must stay untouched by transcript
// activity (ADR-0019) — but the operator view's transcript tail DOES change, proving the
// test harness would actually detect a real snapshot change if one occurred (an equality
// check alone, with nothing else moving, would be indistinguishable from a broken test).
// ---------------------------------------------------------------------------------------
#[test]
fn controller_snapshot_stays_untouched_by_transcript_activity() {
    let mut c = controller();
    let sink = SpySink::new();
    c.set_transcript_sink(Box::new(sink));
    c.start_transcript_session("Sunday Service", "on-device-whisper");

    let now = Instant::now();
    let before_snapshot = c.snapshot(now);
    let before_view_len = c.operator_view().transcript.len();

    for i in 0..5 {
        c.ingest_transcript(
            &format!("segment {i}"),
            i as u64 * 100,
            i as u64 * 100 + 50,
            true,
        );
    }
    c.end_transcript_session();

    let after_snapshot = c.snapshot(now);
    let after_view_len = c.operator_view().transcript.len();

    assert_eq!(
        before_snapshot, after_snapshot,
        "ControllerSnapshot must be completely unaffected by transcript ingestion/session \
         boundaries (ADR-0019: the transcript + detection queue stay out of crash recovery)"
    );
    assert_ne!(
        before_view_len, after_view_len,
        "positive control: the operator view's transcript tail DID grow, proving ingestion \
         really happened and the snapshot equality above is not vacuously true"
    );
}

// ---------------------------------------------------------------------------------------
// The default sink (no `set_transcript_sink` call) behaves exactly like today: a no-op,
// so a controller that never wires a durable store is unaffected by this ticket.
// ---------------------------------------------------------------------------------------
#[test]
fn a_controller_with_no_sink_wired_behaves_exactly_as_before() {
    let mut c = controller();
    // No `set_transcript_sink` call — exercises the NullTranscriptSink default.
    c.start_transcript_session("Sunday Service", "on-device-whisper");
    let n = c.ingest_transcript("good morning church", 0, 1_000, true);
    c.end_transcript_session();
    assert_eq!(c.transcript_engine().transcript().len(), 1);
    let _ = n; // detection count is exercised elsewhere; this test only cares that nothing panics
}

// Removing the host health projection must not let unwired storage appear safe.
#[test]
fn unwired_storage_is_explicitly_unavailable_in_the_real_host_view() {
    let mut c = controller();
    c.start_transcript_session("Sermon", "manual");
    c.ingest_transcript("words", 0, 1, true);
    let view = serde_json::to_value(c.operator_view()).unwrap();
    assert_eq!(view["transcript_storage_health"]["available"], false);
}

use selahcue_app::{BackgroundTranscriptWriter as DurableWorker, TranscriptStoreWriter};
use selahcue_lan::protocol::Command;
use std::sync::mpsc;
use std::time::Duration;

// The gate lives INSIDE the storage call, never under the observation lock.
struct GateStore {
    phase: &'static str,
    entered: mpsc::Sender<()>,
    release: mpsc::Receiver<()>,
}
impl GateStore {
    fn gate(&self, phase: &str) {
        if self.phase == phase {
            self.entered.send(()).unwrap();
            self.release.recv().unwrap();
        }
    }
}
impl TranscriptStoreWriter for GateStore {
    fn open_transcript(&mut self, _: &str, _: &str, _: i64) -> Result<i64, String> {
        self.gate("open");
        Ok(1)
    }
    fn append_segment(&mut self, _: i64, _: u64, _: u64, _: &str) -> Result<i64, String> {
        self.gate("append");
        Ok(1)
    }
    fn end_transcript(&mut self, _: i64, _: i64) -> Result<(), String> {
        self.gate("end");
        Ok(())
    }
}

#[test]
fn stalled_store_calls_leave_shared_controller_timer_manual_and_frames_responsive() {
    for phase in ["open", "append", "end"] {
        let (entered_tx, entered_rx) = mpsc::channel();
        let (release_tx, release_rx) = mpsc::channel();
        let mut c = controller();
        c.set_transcript_sink(Box::new(DurableWorker::new(GateStore {
            phase,
            entered: entered_tx,
            release: release_rx,
        })));
        let shared = Arc::new(Mutex::new(c));
        let producer = shared.clone();
        let producer = std::thread::spawn(move || {
            let mut c = producer.lock().unwrap();
            c.apply(&Command::StartTranscript {
                label: "Sermon".into(),
                provider: "manual".into(),
            });
            if phase == "append" {
                for _ in 0..8 {
                    c.ingest_transcript("speech", 0, 1, true);
                }
            }
            if phase == "end" {
                c.apply(&Command::EndTranscript);
            }
        });
        entered_rx.recv_timeout(Duration::from_secs(10)).unwrap();
        let (done_tx, done_rx) = mpsc::channel();
        let control = shared.clone();
        let control = std::thread::spawn(move || {
            #[cfg(feature = "server")]
            {
                let handler = selahcue_app::handler_for(control.clone());
                let reply = handler(selahcue_lan::Role::Operator, &Command::GetOperatorState);
                assert!(matches!(reply, selahcue_lan::server::Reply::Message(_)));
                assert!(matches!(
                    handler(selahcue_lan::Role::Operator, &Command::Next),
                    selahcue_lan::server::Reply::Ack
                ));
                assert!(matches!(
                    handler(selahcue_lan::Role::Operator, &Command::GoLive),
                    selahcue_lan::server::Reply::Ack
                ));
            }
            let mut c = control.lock().unwrap();
            let now = Instant::now();
            c.apply(&Command::StartTimer { seconds: 1 });
            c.tick(now);
            assert_eq!(
                c.apply(&Command::PauseTimer),
                selahcue_app::ControllerReply::Ack
            );
            c.tick(now);
            c.tick(now + Duration::from_secs(20));
            assert_eq!(c.operator_view().timer.unwrap().remaining_secs, Some(1));
            assert_eq!(
                c.apply(&Command::ResumeTimer),
                selahcue_app::ControllerReply::Ack
            );
            c.tick(now + Duration::from_secs(20));
            c.tick(now + Duration::from_secs(22));
            assert!(c.operator_view().timer.unwrap().time_up);
            c.apply(&Command::Next);
            assert_eq!(
                c.apply(&Command::GoLive),
                selahcue_app::ControllerReply::Ack
            );
            assert_eq!(c.live_index(), Some(0));
            assert!(!c.presenter().live_output().bytes().is_empty());
            assert!(!c.stage_output().bytes().is_empty());
            done_tx.send(()).unwrap();
        });
        let responsive = done_rx.recv_timeout(Duration::from_secs(3)).is_ok();
        // Always release before asserting/joining, including the red synchronous baseline.
        for _ in 0..16 {
            let _ = release_tx.send(());
        }
        producer.join().unwrap();
        control.join().unwrap();
        assert!(responsive, "{phase} blocked the live controller");
    }
}

#[derive(Clone)]
struct Clock(Arc<Mutex<Instant>>);
impl selahcue_app::MonotonicClock for Clock {
    fn now(&self) -> Instant {
        *self.0.lock().unwrap()
    }
}
#[derive(Clone)]
struct Epoch(Arc<std::sync::atomic::AtomicI64>);
impl selahcue_app::EpochClock for Epoch {
    fn now_ms(&self) -> i64 {
        self.0.load(std::sync::atomic::Ordering::SeqCst)
    }
}
#[derive(Default)]
struct Records {
    events: Vec<String>,
    texts: Vec<(i64, String)>,
    next: i64,
    fails: usize,
    open_fails: usize,
}
struct RecordingStore {
    records: Arc<Mutex<Records>>,
    gate: Option<GateStore>,
    attempts: mpsc::Sender<()>,
}
impl TranscriptStoreWriter for RecordingStore {
    fn open_transcript(&mut self, label: &str, _: &str, at: i64) -> Result<i64, String> {
        if let Some(g) = &self.gate {
            g.gate("open");
        }
        let mut r = self.records.lock().unwrap();
        if r.open_fails > 0 {
            r.open_fails -= 1;
            return Err("private error".into());
        }
        r.next += 1;
        let id = r.next;
        r.events.push(format!("open {id} {label} {at}"));
        Ok(id)
    }
    fn append_segment(&mut self, id: i64, _: u64, _: u64, text: &str) -> Result<i64, String> {
        if let Some(g) = &self.gate {
            g.gate("append");
        }
        let mut r = self.records.lock().unwrap();
        r.events.push(format!("append {id}"));
        let result = if r.fails > 0 {
            r.fails -= 1;
            Err("private error".into())
        } else {
            r.texts.push((id, text.to_owned()));
            Ok(1)
        };
        let _ = self.attempts.send(());
        result
    }
    fn end_transcript(&mut self, id: i64, at: i64) -> Result<(), String> {
        if let Some(g) = &self.gate {
            g.gate("end");
        }
        self.records
            .lock()
            .unwrap()
            .events
            .push(format!("end {id} {at}"));
        Ok(())
    }
}
fn recording_worker(
    phase: &'static str,
) -> (
    DurableWorker,
    Arc<Mutex<Records>>,
    mpsc::Receiver<()>,
    mpsc::Sender<()>,
) {
    let records = Arc::new(Mutex::new(Records::default()));
    let (entered, observe) = mpsc::channel();
    let (release, released) = mpsc::channel();
    let (attempts, _) = mpsc::channel();
    let worker = DurableWorker::new(RecordingStore {
        records: records.clone(),
        attempts,
        gate: Some(GateStore {
            phase,
            entered,
            release: released,
        }),
    });
    (worker, records, observe, release)
}
const WATCHDOG: Duration = Duration::from_secs(10);

#[test]
fn total_budget_includes_inflight_and_evicts_only_the_oldest_evictable_text() {
    for phase in ["open", "append"] {
        let (mut sink, records, entered, release) = recording_worker(phase);
        let completion = sink.completion();
        sink.start("A", "manual");
        if phase == "append" {
            for i in 0..8 {
                sink.ingest(0, 1, &format!("s{i}"));
            }
        }
        entered.recv_timeout(WATCHDOG).unwrap();
        for i in if phase == "append" { 8 } else { 0 }..65 {
            sink.ingest(0, 1, &format!("s{i}"));
        }
        let health = sink.health();
        // Release even when a budget assertion would fail.
        sink.end();
        for _ in 0..70 {
            let _ = release.send(());
        }
        assert_eq!(health.pending_segments, 64);
        assert_eq!(health.dropped_segments, 1);
        assert!(!health.available);
        assert!(completion.wait_closed(1, WATCHDOG));
        let texts: Vec<_> = records
            .lock()
            .unwrap()
            .texts
            .iter()
            .map(|(_, s)| s.clone())
            .collect();
        let expected: Vec<_> = (0..65)
            .filter(|i| *i != if phase == "append" { 1 } else { 0 })
            .map(|i| format!("s{i}"))
            .collect();
        assert_eq!(texts, expected);
        assert_eq!(sink.health().dropped_segments, 1);
        assert!(!sink.health().available);
        sink.start("B", "manual");
        sink.ingest(0, 1, "new speech");
        sink.end();
        for _ in 0..70 {
            let _ = release.send(());
        }
        assert!(completion.wait_closed(2, WATCHDOG));
        assert_eq!(
            records.lock().unwrap().texts.last().unwrap(),
            &(2, "new speech".into())
        );
        assert_eq!(sink.health().dropped_segments, 1);
        assert!(!sink.health().available);
    }
}

#[test]
fn session_fifo_is_bounded_and_rejected_starts_cannot_misattribute_speech() {
    let (mut sink, records, entered, release) = recording_worker("open");
    let done = sink.completion();
    sink.start("session-0", "manual");
    entered.recv_timeout(WATCHDOG).unwrap();
    sink.ingest(0, 1, "first");
    for i in 1..64 {
        sink.start(&format!("session-{i}"), "manual");
        sink.end();
    }
    sink.start("refused", "manual");
    sink.ingest(0, 1, "must not belong to session-63");
    sink.end();
    let status = sink.session_status();
    for _ in 0..66 {
        let _ = release.send(());
    }
    assert_eq!(status.confirmed_id, None);
    assert!(done.wait_closed(65, WATCHDOG));
    let r = records.lock().unwrap();
    assert_eq!(r.next, 64);
    assert_eq!(r.texts, vec![(1, "first".into())]);
    assert_eq!(
        r.events.iter().filter(|v| v.starts_with("end ")).count(),
        64
    );
    assert!(r.events[0].starts_with("open 1 session-0 "));
    assert!(r.events[2].starts_with("end 1 "));
    assert!(r.events[3].starts_with("open 2 session-1 "));
    drop(r);
    sink.start(&"é".repeat(513), "manual");
    sink.ingest(0, 1, "oversize metadata refused");
    assert_eq!(sink.health().dropped_segments, 2);
    sink.start("recovered", "manual");
    sink.ingest(0, 1, "correct attribution");
    sink.end();
    assert!(done.wait_closed(67, WATCHDOG));
    assert_eq!(
        records.lock().unwrap().texts.last().unwrap(),
        &(65, "correct attribution".into())
    );
}

#[test]
fn quiet_interval_count_end_and_retry_use_bounded_wakes_and_preserve_utf8() {
    let records = Arc::new(Mutex::new(Records::default()));
    let clock = Clock(Arc::new(Mutex::new(Instant::now())));
    let epoch = Epoch(Arc::new(std::sync::atomic::AtomicI64::new(100)));
    let (attempts, observed) = mpsc::channel();
    let store = RecordingStore {
        records: records.clone(),
        gate: None,
        attempts,
    };
    let mut sink = DurableWorker::with_clocks(move || Ok(store), clock.clone(), epoch.clone());
    let done = sink.completion();
    sink.start("A", "manual");
    assert!(done.wait_idle(WATCHDOG));
    for i in 0..7 {
        sink.ingest(0, 1, &format!("s{i}"));
    }
    assert!(records.lock().unwrap().texts.is_empty());
    sink.ingest(0, 1, "eighth");
    assert!(done.wait_idle(WATCHDOG));
    assert_eq!(records.lock().unwrap().texts.len(), 8);
    for _ in 0..8 {
        observed.recv_timeout(WATCHDOG).unwrap();
    }
    sink.ingest(0, 1, "quiet speech");
    *clock.0.lock().unwrap() += Duration::from_secs(5);
    done.wake();
    assert!(done.wait_idle(WATCHDOG));
    assert_eq!(records.lock().unwrap().texts.len(), 9);
    observed.recv_timeout(WATCHDOG).unwrap();
    records.lock().unwrap().fails = 1;
    for _ in 0..8 {
        sink.ingest(0, 1, "retry speech");
    }
    observed.recv_timeout(WATCHDOG).unwrap();
    // Barrier through the health lock ensures failed result has reconciled before advancing.
    let deadline = Instant::now() + WATCHDOG;
    while sink.health().available && Instant::now() < deadline {
        std::thread::yield_now();
    }
    assert!(!sink.health().available);
    assert_eq!(sink.health().pending_segments, 8);
    for _ in 0..100 {
        done.wake();
    }
    assert!(observed.try_recv().is_err());
    *clock.0.lock().unwrap() += Duration::from_secs(5);
    done.wake();
    assert!(done.wait_idle(WATCHDOG));
    assert!(sink.health().available);
    sink.ingest(0, 1, &"ọ".repeat(12_000));
    epoch.0.store(200, std::sync::atomic::Ordering::SeqCst);
    sink.end();
    assert!(done.wait_closed(1, WATCHDOG));
    assert_eq!(sink.health().truncated_segments, 1);
    assert!(!sink.health().available);
    let r = records.lock().unwrap();
    assert_eq!(r.texts.last().unwrap().1, "ọ".repeat(10_922));
    assert_eq!(r.events.first().unwrap(), "open 1 A 100");
    assert_eq!(r.events.last().unwrap(), "end 1 200");
}

#[test]
fn failed_open_and_final_failed_flush_count_loss_and_allow_later_sessions() {
    let records = Arc::new(Mutex::new(Records {
        open_fails: 1,
        ..Records::default()
    }));
    let (attempts, _) = mpsc::channel();
    let mut sink = DurableWorker::new(RecordingStore {
        records: records.clone(),
        gate: None,
        attempts,
    });
    let done = sink.completion();
    sink.start("failed", "manual");
    sink.ingest(0, 1, "lost on open");
    sink.end();
    assert!(done.wait_closed(1, WATCHDOG));
    assert_eq!(sink.health().dropped_segments, 1);
    assert!(!sink.health().available);
    records.lock().unwrap().fails = 1;
    sink.start("failed flush", "manual");
    sink.ingest(0, 1, "lost at end");
    sink.end();
    assert!(done.wait_closed(2, WATCHDOG));
    assert_eq!(sink.health().dropped_segments, 2);
    sink.start("healthy", "manual");
    sink.ingest(0, 1, "saved");
    sink.end();
    assert!(done.wait_closed(3, WATCHDOG));
    assert_eq!(sink.health().dropped_segments, 2);
    assert_eq!(records.lock().unwrap().texts, vec![(2, "saved".into())]);
}

#[test]
fn drop_queues_close_without_joining_stalled_storage() {
    let (mut sink, _, entered, release) = recording_worker("open");
    let done = sink.completion();
    sink.start("A", "manual");
    entered.recv_timeout(WATCHDOG).unwrap();
    let (tx, rx) = mpsc::channel();
    let dropping = std::thread::spawn(move || {
        drop(sink);
        tx.send(()).unwrap();
    });
    let dropped = rx.recv_timeout(Duration::from_secs(3)).is_ok();
    let _ = release.send(());
    dropping.join().unwrap();
    assert!(dropped);
    assert!(done.wait_closed(1, WATCHDOG));
}

struct SqliteStore(selahcue_data::Database);
impl TranscriptStoreWriter for SqliteStore {
    fn open_transcript(
        &mut self,
        label: &str,
        provider: &str,
        started_at_ms: i64,
    ) -> Result<i64, String> {
        selahcue_data::transcript_repo::create(
            &self.0,
            &selahcue_data::transcript_repo::NewTranscript {
                label: label.into(),
                provider: provider.into(),
                started_at_ms,
                plan_id: None,
            },
        )
        .map_err(|_| "store unavailable".into())
    }
    fn append_segment(&mut self, id: i64, start: u64, end: u64, text: &str) -> Result<i64, String> {
        selahcue_data::transcript_repo::append_segment(&self.0, id, start, end, text)
            .map_err(|_| "store unavailable".into())
    }
    fn end_transcript(&mut self, id: i64, end: i64) -> Result<(), String> {
        selahcue_data::transcript_repo::end(&self.0, id, end)
            .map_err(|_| "store unavailable".into())
    }
}
#[test]
fn real_producer_worker_completion_and_database_reopen_retain_over_240_finals() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("transcripts.db3");
    let db = selahcue_data::Database::open(&path).unwrap();
    let sink = DurableWorker::new(SqliteStore(db));
    let done = sink.completion();
    let mut c = controller();
    c.set_transcript_sink(Box::new(sink));
    c.start_transcript_session("Sunday", "manual");
    let mut producer = ManualProvider::new();
    for batch in 0..38 {
        for i in batch * 8..batch * 8 + 8 {
            producer.submit(format!("ọ̀rọ̀ {i}"), i * 10, i * 10 + 5);
        }
        pump_transcript(&mut c, &mut producer);
        c.ingest_transcript("interim must not persist", 0, 1, false);
        assert!(done.wait_idle(WATCHDOG));
    }
    c.end_transcript_session();
    assert!(done.wait_closed(1, WATCHDOG));
    let h = c.operator_view().transcript_storage_health.unwrap();
    assert!(h.available);
    assert_eq!(h.pending_segments, 0);
    assert_eq!(c.transcript_engine().transcript().len(), 240);
    drop(c);
    let reopened = selahcue_data::Database::open(&path).unwrap();
    let rows = selahcue_data::transcript_repo::list(&reopened).unwrap();
    assert_eq!(rows.len(), 1);
    assert!(rows[0].ended_at_ms.is_some());
    let detail = selahcue_data::transcript_repo::load(&reopened, rows[0].id).unwrap();
    assert_eq!(detail.segments.len(), 304);
    for (i, segment) in detail.segments.iter().enumerate() {
        assert_eq!(segment.text, format!("ọ̀rọ̀ {i}"));
    }
}

#[test]
fn queued_end_does_not_make_stored_history_eligible_before_final_append_completes() {
    struct GatedSqlite {
        db: SqliteStore,
        gate: GateStore,
    }
    impl TranscriptStoreWriter for GatedSqlite {
        fn open_transcript(&mut self, label: &str, provider: &str, at: i64) -> Result<i64, String> {
            self.db.open_transcript(label, provider, at)
        }
        fn append_segment(
            &mut self,
            id: i64,
            start: u64,
            end: u64,
            text: &str,
        ) -> Result<i64, String> {
            self.gate.gate("append");
            self.db.append_segment(id, start, end, text)
        }
        fn end_transcript(&mut self, id: i64, at: i64) -> Result<(), String> {
            self.db.end_transcript(id, at)
        }
    }
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("notes.db3");
    let db = selahcue_data::Database::open(&path).unwrap();
    let read = selahcue_data::Database::open(&path).unwrap();
    let (entered, observed) = mpsc::channel();
    let (release, released) = mpsc::channel();
    let sink = DurableWorker::new(GatedSqlite {
        db: SqliteStore(db),
        gate: GateStore {
            phase: "append",
            entered,
            release: released,
        },
    });
    let done = sink.completion();
    let mut c = controller();
    c.set_transcript_sink(Box::new(sink));
    c.start_transcript_session("A", "manual");
    for i in 0..8 {
        c.ingest_transcript(&format!("final {i}"), 0, 1, true);
    }
    observed.recv_timeout(WATCHDOG).unwrap();
    // The first append is in flight; fill the SAME budget through the actual command wrapper.
    for i in 8..65 {
        c.apply(&Command::IngestTranscript {
            text: format!("final {i}"),
            start_ms: Some(0),
            end_ms: Some(1),
            is_final: true,
        });
    }
    let health = c.operator_view().transcript_storage_health.unwrap();
    let ack = c.apply(&Command::EndTranscript);
    let active = c.apply(&Command::GetActiveTranscriptId);
    // Stop is an admission acknowledgement: live controls remain independent of drain.
    let now = Instant::now();
    assert_eq!(
        c.apply(&Command::StartTimer { seconds: 1 }),
        selahcue_app::ControllerReply::Ack
    );
    c.tick(now);
    c.tick(now + Duration::from_secs(2));
    assert!(c.operator_view().timer.unwrap().time_up);
    assert_eq!(c.apply(&Command::Next), selahcue_app::ControllerReply::Ack);
    assert_eq!(
        c.apply(&Command::GoLive),
        selahcue_app::ControllerReply::Ack
    );
    assert_eq!(
        c.apply(&Command::Blackout { on: true }),
        selahcue_app::ControllerReply::Ack
    );
    assert_eq!(
        c.apply(&Command::Blackout { on: false }),
        selahcue_app::ControllerReply::Ack
    );
    let rows = selahcue_data::transcript_repo::list(&read).unwrap();
    let before = selahcue_data::transcript_repo::load(&read, rows[0].id).unwrap();
    for _ in 0..64 {
        release.send(()).unwrap();
    }
    assert_eq!(
        health.pending_segments, 64,
        "in-flight append is inside the cap"
    );
    assert_eq!(health.dropped_segments, 1);
    assert_eq!(
        active,
        selahcue_app::ControllerReply::Message(
            selahcue_lan::protocol::ServerMessage::ActiveTranscriptId {
                transcript_id: Some(rows[0].id)
            }
        )
    );
    assert_eq!(ack, selahcue_app::ControllerReply::Ack);
    assert!(
        before.ended_at_ms.is_none(),
        "history generation must still refuse an open transcript"
    );
    assert!(
        before.segments.is_empty(),
        "append really was held inside the store"
    );
    assert!(done.wait_closed(1, WATCHDOG));
    drop(c);
    drop(read);
    let reopened = selahcue_data::Database::open(&path).unwrap();
    let after = selahcue_data::transcript_repo::load(&reopened, rows[0].id).unwrap();
    assert!(after.ended_at_ms.is_some());
    let texts: Vec<_> = after.segments.iter().map(|s| s.text.clone()).collect();
    assert_eq!(
        texts,
        (0..65)
            .filter(|i| *i != 1)
            .map(|i| format!("final {i}"))
            .collect::<Vec<_>>()
    );
}

#[test]
fn queued_close_cannot_report_saved_until_the_store_finishes_ending() {
    let (mut sink, _, entered, release) = recording_worker("end");
    let done = sink.completion();
    sink.start("A", "manual");
    assert!(done.wait_idle(WATCHDOG));
    sink.end();
    entered.recv_timeout(WATCHDOG).unwrap();
    let health = sink.health();
    release.send(()).unwrap();
    assert!(
        !health.available,
        "an unconfirmed close must not report saved"
    );
    assert!(done.wait_closed(1, WATCHDOG));
    assert!(sink.health().available);
}

#[test]
fn factory_failure_and_worker_panic_are_unavailable_and_account_for_pending_speech() {
    let mut failed = DurableWorker::from_factory(|| -> Result<SqliteStore, String> {
        Err("private path".into())
    });
    let done = failed.completion();
    failed.start("A", "manual");
    failed.ingest(0, 1, "lost");
    failed.end();
    assert!(done.wait_closed(1, WATCHDOG));
    assert!(!failed.health().available);
    assert_eq!(failed.health().dropped_segments, 1);
    struct Panics;
    impl TranscriptStoreWriter for Panics {
        fn open_transcript(&mut self, _: &str, _: &str, _: i64) -> Result<i64, String> {
            Ok(1)
        }
        fn append_segment(&mut self, _: i64, _: u64, _: u64, _: &str) -> Result<i64, String> {
            panic!("injected store panic")
        }
        fn end_transcript(&mut self, _: i64, _: i64) -> Result<(), String> {
            Ok(())
        }
    }
    let mut sink = DurableWorker::new(Panics);
    let done = sink.completion();
    sink.start("B", "manual");
    for _ in 0..8 {
        sink.ingest(0, 1, "pending");
    }
    assert!(done.wait_closed(1, WATCHDOG));
    assert!(!sink.health().available);
    assert_eq!(sink.health().pending_segments, 0);
    assert_eq!(sink.health().dropped_segments, 8);
}

#[test]
fn delayed_store_uses_captured_boundaries_and_fifo_session_attribution() {
    let records = Arc::new(Mutex::new(Records::default()));
    let clock = Clock(Arc::new(Mutex::new(Instant::now())));
    let epoch = Epoch(Arc::new(std::sync::atomic::AtomicI64::new(100)));
    let (entered, observed) = mpsc::channel();
    let (release, released) = mpsc::channel();
    let (attempts, _) = mpsc::channel();
    let store = RecordingStore {
        records: records.clone(),
        attempts,
        gate: Some(GateStore {
            phase: "open",
            entered,
            release: released,
        }),
    };
    let mut sink = DurableWorker::with_clocks(move || Ok(store), clock, epoch.clone());
    let done = sink.completion();
    sink.start("A", "manual");
    observed.recv_timeout(WATCHDOG).unwrap();
    sink.ingest(0, 1, "A speech");
    epoch.0.store(200, std::sync::atomic::Ordering::SeqCst);
    sink.end();
    epoch.0.store(300, std::sync::atomic::Ordering::SeqCst);
    sink.start("B", "manual");
    sink.ingest(0, 1, "B speech");
    epoch.0.store(400, std::sync::atomic::Ordering::SeqCst);
    sink.end();
    epoch.0.store(900, std::sync::atomic::Ordering::SeqCst);
    release.send(()).unwrap();
    observed.recv_timeout(WATCHDOG).unwrap();
    let a_finished_without_b = done.wait_closed(1, Duration::ZERO);
    release.send(()).unwrap();
    assert!(done.wait_closed(2, WATCHDOG));
    assert!(
        a_finished_without_b,
        "A completion must not wait for B's stalled open"
    );
    assert_eq!(
        records.lock().unwrap().events,
        vec![
            "open 1 A 100",
            "append 1",
            "end 1 200",
            "open 2 B 300",
            "append 2",
            "end 2 400"
        ]
    );
    assert_eq!(
        records.lock().unwrap().texts,
        vec![(1, "A speech".into()), (2, "B speech".into())]
    );
    assert_eq!(sink.session_status().confirmed_id, Some(2));
}

#[test]
fn actual_host_state_projects_sticky_loss_before_and_after_storage_recovers() {
    let (sink, _, entered, release) = recording_worker("open");
    let done = sink.completion();
    let mut c = controller();
    c.set_transcript_sink(Box::new(sink));
    c.start_transcript_session("A", "manual");
    entered.recv_timeout(WATCHDOG).unwrap();
    for i in 0..65 {
        c.ingest_transcript(&format!("speech {i}"), 0, 1, true);
    }
    let before = c.apply(&Command::GetOperatorState);
    c.end_transcript_session();
    release.send(()).unwrap();
    assert!(done.wait_closed(1, WATCHDOG));
    let after = c.apply(&Command::GetOperatorState);
    for (reply, pending) in [(before, 64), (after, 0)] {
        let selahcue_app::ControllerReply::Message(
            selahcue_lan::protocol::ServerMessage::OperatorState { view },
        ) = reply
        else {
            panic!("expected actual host state")
        };
        let health = serde_json::to_value(view).unwrap()["transcript_storage_health"].clone();
        assert_eq!(
            health,
            serde_json::json!({"available":false,"pending_segments":pending,"dropped_segments":1,"truncated_segments":0})
        );
    }
}
