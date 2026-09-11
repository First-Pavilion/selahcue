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
