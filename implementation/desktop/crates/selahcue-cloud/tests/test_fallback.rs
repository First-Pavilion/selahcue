//! C-004: graceful local fallback (FR-135). A failing/unreachable cloud transport
//! must yield a degraded outcome served by the local provider — no panic, output
//! never blocked.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{
    generate_sermon_notes, LocalNoteProvider, MockTransport, SelahCueCloudClient,
};
use selahcue_core::providers::ProvidersConfig;

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
