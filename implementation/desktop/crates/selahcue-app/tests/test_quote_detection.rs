//! Fuzzy quote/paraphrase detection wired end-to-end through the app (R4 fuzzy rung):
//! `ingest_transcript` runs exact + fuzzy detection, and `pump_transcript` drives any
//! `TranscriptProvider` (e.g. the on-device STT provider, here a `ManualProvider`) into it.

#![allow(clippy::unwrap_used)]

use selahcue_app::{pump_transcript, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_core::transcript::ManualProvider;
use selahcue_present::Theme;

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
    c.ingest_transcript("please turn to John chapter 3 verse 16", 0, 2_000);
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
