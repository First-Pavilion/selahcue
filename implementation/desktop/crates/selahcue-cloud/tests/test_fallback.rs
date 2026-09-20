//! C-004: graceful local fallback (FR-135). A failing/unreachable cloud transport
//! must yield a degraded outcome served by the local provider — no panic, output
//! never blocked.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{
    generate_sermon_notes, LocalNoteProvider, MockTransport, SelahCueCloudClient,
};
use selahcue_core::providers::ProvidersConfig;

/// 86akcffy0 (Cody review, High): `generate_sermon_notes` clamps the transcript at its own
/// egress choke point, BEFORE calling any `CloudNoteProvider` — so a hosted `SelahCueCloudClient`
/// (the actual shipping path, DEC-004) is bound by the SAME 400,000-character limit as the
/// OpenAI direct-key provider, even though the client itself never calls `bounded_transcript`.
/// Before this fix, only `openai::build_body` clamped; a from-history transcript past the cap
/// would have gone out to the hosted service in full the moment `cloud-live` becomes real, making
/// the from-history preview's "the final N characters will be left out" disclosure false for
/// that path. Asserted against the REAL wire body a `SelahCueCloudClient` sends (via
/// `MockTransport`'s request recording), not against an internal function in isolation.
#[test]
fn the_hosted_client_never_sends_an_unclamped_transcript() {
    let huge = "a".repeat(selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS + 5_000);

    let transport = MockTransport::responding(
        200,
        r#"{"draft":{"title":"t","summary":null,"introduction":[],"illustrations":[],
             "quotes":[],"prayer_points":[],"calls_to_action":[],"key_lessons":[],
             "chapter_markers":[],"social_excerpts":[],"points":[]},
           "quota":{"used":0,"limit":10,"resets_label":"in 30 days"}}"#,
    );
    // Taken BEFORE `transport` is moved by value into the client below — see
    // `MockTransport::requests_handle`'s doc comment.
    let requests = transport.requests_handle();
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let outcome = generate_sermon_notes(&cfg, &huge, true, &cloud, &local);
    assert!(
        outcome.is_ok(),
        "premise: the mocked hosted response must actually succeed, or this test proves nothing: {outcome:?}"
    );

    let recorded = requests
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    assert_eq!(
        recorded.len(),
        1,
        "premise: exactly one request must have left the device"
    );
    let sent: serde_json::Value =
        serde_json::from_str(&recorded[0].body).expect("the recorded body is valid JSON");
    let sent_transcript = sent["transcript"]
        .as_str()
        .expect("the wire request carries a transcript field");

    assert!(
        sent_transcript.chars().count() <= selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS,
        "the hosted client sent {} characters — the shared clamp did not reach this provider",
        sent_transcript.chars().count()
    );
    assert!(
        sent_transcript.chars().count() < huge.chars().count(),
        "positive control: the sent transcript must genuinely be smaller than the oversized input, \
         not merely 'at or under the cap' by coincidence of a provider that always truncates"
    );
}

#[test]
fn transport_failure_falls_back_to_local_and_marks_degraded() {
    let transport = MockTransport::failing();
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let outcome = generate_sermon_notes(
        &cfg,
        "First point. Second point. Third point.",
        true,
        &cloud,
        &local,
    )
    .unwrap();

    assert!(outcome.degraded, "cloud failed → degraded");
    assert_eq!(outcome.provider_label, "Local (offline)");
    assert!(outcome.quota.is_none());
    // The fallback draft is never blank.
    assert!(!outcome.draft.title.is_empty());
    assert!(!outcome.draft.sections.is_empty());
}

#[test]
fn quota_exceeded_is_not_masked_by_fallback() {
    // 402 → QuotaExceeded is an honest terminal state, not a network blip; it must
    // surface, not silently fall back.
    let transport = MockTransport::responding(402, "{}");
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let err = generate_sermon_notes(&cfg, "transcript", true, &cloud, &local).unwrap_err();
    assert_eq!(err, selahcue_core::providers::NoteError::QuotaExceeded);
}

fn token() -> selahcue_cloud::Token {
    selahcue_cloud::Token::new("acct-session-token")
}
