//! Fuzzy quote/paraphrase detection wired end-to-end through the app (R4 fuzzy rung):
//! `ingest_transcript` runs exact + fuzzy detection, and `pump_transcript` drives any
//! `TranscriptProvider` (e.g. the on-device STT provider, here a `ManualProvider`) into it.

#![allow(clippy::unwrap_used)]

use selahcue_app::{pump_transcript, ControllerReply, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_core::transcript::ManualProvider;
use selahcue_lan::protocol::{Command, DenyReason};
use selahcue_present::Theme;
use std::time::{Duration, Instant};

fn controller() -> LiveController {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Section, "Sermon");
    LiveController::new(plan, 320, 180, Theme::dark())
}

fn pending_refs(c: &LiveController) -> Vec<String> {
    c.transcript_engine()
        .detections()
        .pending()
        .map(|d| d.reference.clone())
        .collect()
}

#[test]
fn ingest_transcript_detects_a_spoken_quote_without_a_named_reference() {
    let mut c = controller();
    // A quotation of John 3:16 — the reference is NOT spoken.
    let n = c.ingest_transcript(
        "for God so loved the world that he gave his only begotten Son, \
         that whosoever believeth in him should not perish but have everlasting life",
        0,
        3_000,
        true,
    );
    assert_eq!(n, 1, "the quote should surface one detection");
    assert!(
        pending_refs(&c).contains(&"John 3:16".to_string()),
        "expected John 3:16 from the quote, got {:?}",
        pending_refs(&c)
    );
}

#[test]
fn ingest_transcript_still_detects_a_named_reference() {
    // Regression: the exact detector is unchanged.
    let mut c = controller();
    c.ingest_transcript("please turn to John chapter 3 verse 16", 0, 2_000, true);
    assert!(pending_refs(&c).contains(&"John 3:16".to_string()));
}

#[test]
fn ingest_transcript_ignores_ordinary_speech() {
    // Precision: neither the exact detector nor the quote matcher fires on ordinary speech.
    let mut c = controller();
    let n = c.ingest_transcript(
        "good morning everyone and welcome to church this morning",
        0,
        2_000,
        true,
    );
    assert_eq!(n, 0);
    assert!(pending_refs(&c).is_empty());
}

#[test]
fn pump_transcript_drives_a_provider_into_detection() {
    // The STT↔detection wiring: a TranscriptProvider's segments flow into detection.
    let mut c = controller();
    let mut provider = ManualProvider::new();
    provider.submit(
        "for God so loved the world that he gave his only begotten Son, \
         that whosoever believeth in him should not perish but have everlasting life",
        0,
        3_000,
    );
    let n = pump_transcript(&mut c, &mut provider);
    assert_eq!(n, 1, "one segment pumped");
    assert!(
        pending_refs(&c).contains(&"John 3:16".to_string()),
        "the pumped quote should be detected, got {:?}",
        pending_refs(&c)
    );
}

#[test]
fn pump_transcript_forwards_nothing_from_an_empty_provider() {
    let mut c = controller();
    let mut provider = ManualProvider::new();
    assert_eq!(pump_transcript(&mut c, &mut provider), 0);
    assert!(pending_refs(&c).is_empty());
}

// Exercise the real dispatcher, including action-side marking and dedup expiry.
fn actioned_reference_expires(approve: bool, churn: bool, quoted: bool) {
    let mut c = controller();
    // Hold the B1 writer INSIDE its append call while reusing all B5 deadline/action assertions.
    struct StalledStore(std::sync::mpsc::Sender<()>, std::sync::mpsc::Receiver<()>);
    impl selahcue_app::TranscriptStoreWriter for StalledStore {
        fn open_transcript(&mut self, _: &str, _: &str, _: i64) -> Result<i64, String> {
            Ok(1)
        }
        fn append_segment(&mut self, _: i64, _: u64, _: u64, _: &str) -> Result<i64, String> {
            self.0.send(()).unwrap();
            self.1.recv().unwrap();
            Ok(1)
        }
        fn end_transcript(&mut self, _: i64, _: i64) -> Result<(), String> {
            Ok(())
        }
    }
    let (entered, observed) = std::sync::mpsc::channel();
    let (release, released) = std::sync::mpsc::channel();
    let sink = selahcue_app::BackgroundTranscriptWriter::new(StalledStore(entered, released));
    let completion = sink.completion();
    c.set_transcript_sink(Box::new(sink));
    c.apply(&Command::StartTranscript {
        label: "B1+B5 synthetic".into(),
        provider: "manual".into(),
    });
    for i in 0..8 {
        c.ingest_transcript(&format!("ordinary speech {i}"), 0, 1, true);
    }
    observed.recv_timeout(Duration::from_secs(10)).unwrap();
    let now = Instant::now();
    c.apply(&Command::StartTimer { seconds: 1 });
    c.tick(now);
    c.tick(now + Duration::from_secs(2));
    assert!(c.operator_view().timer.unwrap().time_up);
    assert_eq!(c.apply(&Command::Next), ControllerReply::Ack);
    assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
    assert_eq!(
        c.apply(&Command::Blackout { on: true }),
        ControllerReply::Ack
    );
    assert_eq!(
        c.apply(&Command::Blackout { on: false }),
        ControllerReply::Ack
    );
    let text = if quoted {
        "for God so loved the world that he gave his only begotten Son, that whosoever believeth in him should not perish but have everlasting life"
    } else {
        "John 3:16"
    };
    c.ingest_transcript_at(text, 0, 1_000, true, now);
    let id = c.operator_view().detections[0].id;
    let command = if approve {
        Command::ApproveDetection { detection_id: id }
    } else {
        Command::DismissDetection { detection_id: id }
    };
    // Cooldown starts at the action, not at the earlier detection or last tick.
    let action_time = now + Duration::from_secs(10);
    assert_eq!(c.apply_at(&command, action_time), ControllerReply::Ack);
    if approve {
        assert_eq!(c.apply(&Command::GoLive), ControllerReply::Ack);
        assert_eq!(
            c.apply(&Command::FollowScripture {
                reference: "John 3:17".into(),
                translation: None
            }),
            ControllerReply::Ack
        );
        assert_eq!(
            c.operator_view().live_scripture.as_deref(),
            Some("John 3:17")
        );
    }
    let staged = c.operator_view().staged_scripture;
    let live = c.operator_view().live_scripture;
    let generation = c.live_generation();
    if churn {
        // Expel John from the old 16-entry dedup ring without actioning it again.
        for chapter in 1..=17 {
            c.ingest_transcript_at(&format!("Psalms {chapter}"), 0, 1_000, true, action_time);
        }
    }
    // Deliberately no tick: detection time cannot depend on render progress.
    // Transcript timestamps are unrelated to host monotonic cooldown time.
    c.ingest_transcript_at(
        text,
        90_000,
        91_000,
        true,
        action_time + Duration::from_secs(19),
    );
    assert!(
        !pending_refs(&c).contains(&"John 3:16".to_string()),
        "19s must suppress the actioned reference even after dedup-ring churn"
    );
    c.ingest_transcript_at(
        "Romans 8:28",
        0,
        1_000,
        true,
        action_time + Duration::from_secs(19),
    );
    assert!(
        pending_refs(&c).contains(&"Romans 8:28".to_string()),
        "different references remain eligible"
    );
    assert_eq!(c.operator_view().staged_scripture, staged);
    assert_eq!(c.operator_view().live_scripture, live);
    assert_eq!(
        c.live_generation(),
        generation,
        "repetition must not reset the displayed passage"
    );

    assert_eq!(
        c.apply_at(&command, action_time + Duration::from_secs(19)),
        ControllerReply::Deny(DenyReason::BadRequest),
        "a stale action must not restart cooldown"
    );
    // Denied approve may conservatively increment the host's dirty generation.
    let generation = c.live_generation();
    assert_eq!(
        c.apply_at(
            &Command::IngestTranscript {
                text: text.into(),
                start_ms: None,
                end_ms: None,
                is_final: true
            },
            action_time + Duration::from_secs(20)
        ),
        ControllerReply::Ack
    );
    assert!(
        pending_refs(&c).contains(&"John 3:16".to_string()),
        "exactly 20s re-enables the reference without a dedup-ring wait"
    );
    assert_eq!(c.operator_view().staged_scripture, staged);
    assert_eq!(c.operator_view().live_scripture, live);
    assert_eq!(c.live_generation(), generation);
    assert!(
        c.operator_view()
            .transcript_storage_health
            .unwrap()
            .pending_segments
            > 0
    );
    c.apply(&Command::EndTranscript);
    for _ in 0..64 {
        let _ = release.send(());
    }
    assert!(completion.wait_closed(1, Duration::from_secs(10)));
}

#[test]
fn approved_reference_cooldown_expires_at_twenty_seconds() {
    actioned_reference_expires(true, false, false);
}

#[test]
fn dismissed_reference_cooldown_expires_at_twenty_seconds() {
    actioned_reference_expires(false, false, false);
}

#[test]
fn approved_reference_stays_suppressed_after_dedup_ring_churn() {
    actioned_reference_expires(true, true, false);
}

#[test]
fn dismissed_reference_stays_suppressed_after_dedup_ring_churn() {
    actioned_reference_expires(false, true, false);
}

#[test]
fn new_transcript_session_clears_actioned_and_pending_references() {
    let mut c = controller();
    c.tick(Instant::now());
    c.ingest_transcript("John 3:16", 0, 1_000, true);
    let id = c.operator_view().detections[0].id;
    assert_eq!(
        c.apply(&Command::DismissDetection { detection_id: id }),
        ControllerReply::Ack
    );
    c.ingest_transcript("Romans 8:28", 0, 1_000, true);
    assert_eq!(
        c.apply(&Command::StartTranscript {
            label: "New sermon".into(),
            provider: "manual".into()
        }),
        ControllerReply::Ack
    );
    assert!(
        pending_refs(&c).is_empty(),
        "a new session clears the old queue"
    );
    c.ingest_transcript("John 3:16", 0, 1_000, true);
    assert!(
        pending_refs(&c).contains(&"John 3:16".to_string()),
        "a new session does not inherit cooldown"
    );
}

#[test]
fn approved_quote_cooldown_expires_at_twenty_seconds() {
    actioned_reference_expires(true, false, true);
}

#[test]
fn dismissed_quote_cooldown_expires_at_twenty_seconds() {
    actioned_reference_expires(false, false, true);
}
