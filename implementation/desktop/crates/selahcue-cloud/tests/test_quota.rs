//! C-006: the monthly quota is parsed from the provider and its remaining count is
//! derived (never trusted from the wire). The quota probe is itself consent-gated —
//! it must not phone home before opt-in.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{MockTransport, SelahCueCloudClient};
use selahcue_core::providers::{ConsentState, NoteError};

fn consented() -> ConsentState {
    ConsentState {
        cloud_transcription: false,
        cloud_notes: true,
    }
}

#[test]
fn fetch_quota_parses_and_derives_remaining() {
    let body = serde_json::json!({ "used": 12, "limit": 40, "resets_label": "Sep 1" }).to_string();
    let transport = MockTransport::responding(200, body);
    let client = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());

    let quota = client.fetch_quota(&consented()).unwrap();
    assert_eq!(quota.used, 12);
    assert_eq!(quota.limit, 40);
    assert_eq!(quota.resets_label, "Sep 1");
    assert_eq!(quota.remaining(), 28); // derived, matches the design "28 remaining"
    assert!(!quota.is_exhausted());
}

#[test]
fn fetch_quota_is_refused_and_sends_nothing_without_consent() {
    use std::sync::Arc;
    let transport = Arc::new(MockTransport::responding(
        200,
        serde_json::json!({ "used": 1, "limit": 40, "resets_label": "Sep 1" }).to_string(),
    ));
    let client =
        SelahCueCloudClient::new(ArcTransport(transport.clone()), "https://api.x", token());

    // No cloud-notes consent → the quota probe must refuse and issue ZERO requests.
    let err = client.fetch_quota(&ConsentState::default()).unwrap_err();
    assert_eq!(err, NoteError::ConsentRequired);
    assert_eq!(transport.request_count(), 0, "no egress without consent");
}

#[test]
fn fetch_quota_on_unconfigured_client_is_not_configured() {
    let transport = MockTransport::responding(200, "{}");
    let client = SelahCueCloudClient::unconfigured(transport);
    let err = client.fetch_quota(&consented()).unwrap_err();
    assert_eq!(err, NoteError::NotConfigured);
}

fn token() -> selahcue_cloud::Token {
    selahcue_cloud::Token::new("acct-session-token")
}

/// A transport wrapper so the test can keep an `Arc` handle to assert 0 requests.
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
