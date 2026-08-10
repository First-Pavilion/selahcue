//! C-003: end-to-end note generation is consent-gated and transcript-only.
//!
//! The privacy properties under test:
//! - with cloud-notes consent OFF, **no request is issued** (nothing leaves the device);
//! - with consent ON + Generate, the request body carries **only the completed
//!   transcript** (there is no audio field) and a draft comes back.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{
    generate_sermon_notes, LocalNoteProvider, MockTransport, SelahCueCloudClient,
};
use selahcue_core::providers::{NoteError, ProvidersConfig};

fn ok_response_body() -> String {
    serde_json::json!({
        "draft": {
            "title": "The Good Shepherd",
            "summary": "A study of John 10.",
            "sections": [{"heading": "Intro", "items": ["He calls his own by name"]}],
            "scriptures": ["John 10:11"]
        },
        "quota": { "used": 12, "limit": 40, "resets_label": "Sep 1" }
    })
    .to_string()
}

#[test]
fn consent_off_generates_nothing_and_issues_zero_requests() {
    use std::sync::Arc;
    // The headline privacy property, proven end-to-end: with cloud-notes consent OFF,
    // running the FULL orchestrator (gate → cloud → fallback) must refuse AND leave the
    // transport untouched (0 bytes leave the device). Asserted via an inspectable transport,
    // not by argument.
    let transport = Arc::new(MockTransport::responding(200, ok_response_body()));
    let cloud = SelahCueCloudClient::new(ArcTransport(transport.clone()), "https://api.x", token());
    let local = LocalNoteProvider::new();

    let cfg = ProvidersConfig::default(); // consent OFF
    let err =
        generate_sermon_notes(&cfg, "the completed transcript", true, &cloud, &local).unwrap_err();
    assert_eq!(err, NoteError::ConsentRequired);
    assert_eq!(
        transport.request_count(),
        0,
        "consent off ⇒ nothing leaves the device"
    );
}

#[test]
fn consented_generate_sends_only_the_completed_transcript_and_returns_a_draft() {
    use std::sync::Arc;
    // Share the transport so we can inspect what was sent after the call.
    let transport = Arc::new(MockTransport::responding(200, ok_response_body()));
    let cloud = SelahCueCloudClient::new(ArcTransport(transport.clone()), "https://api.x", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let outcome =
        generate_sermon_notes(&cfg, "God so loved the world", true, &cloud, &local).unwrap();

    assert!(!outcome.degraded);
    assert_eq!(outcome.provider_label, "SelahCue AI");
    assert_eq!(outcome.draft.title, "The Good Shepherd");
    assert_eq!(outcome.quota.unwrap().remaining(), 28);

    // Exactly one request; it carried the transcript and a bearer, and NO audio field.
    let recorded = transport.recorded();
    assert_eq!(recorded.len(), 1);
    let sent = &recorded[0];
    assert_eq!(sent.method, "POST");
    assert!(sent.had_bearer, "auth attached");
    assert!(sent.body.contains("God so loved the world"));
    assert!(
        !sent.body.contains("audio"),
        "request must never carry audio: {}",
        sent.body
    );
}

#[test]
fn unconfigured_client_reports_not_configured_without_sending() {
    use std::sync::Arc;
    let transport = Arc::new(MockTransport::responding(200, ok_response_body()));
    let cloud = SelahCueCloudClient::unconfigured(ArcTransport(transport.clone()));
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let err = generate_sermon_notes(&cfg, "transcript", true, &cloud, &local).unwrap_err();
    assert_eq!(err, NoteError::NotConfigured);
    assert_eq!(transport.request_count(), 0, "no egress when unconfigured");
}

// --- test helpers ---

fn token() -> selahcue_cloud::Token {
    selahcue_cloud::Token::new("acct-session-token")
}

/// A transport wrapper so tests can keep an `Arc` handle to inspect recordings while
/// the client owns a transport.
struct ArcTransport(std::sync::Arc<MockTransport>);

impl selahcue_cloud::HttpTransport for ArcTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::HttpResponse, selahcue_cloud::TransportError> {
        self.0.post_json(url, body, bearer)
    }
    fn get(
        &self,
        url: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::HttpResponse, selahcue_cloud::TransportError> {
        self.0.get(url, bearer)
    }
}
