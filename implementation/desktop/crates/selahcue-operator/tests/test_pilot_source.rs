//! Compiles the actual operator selector; no Tauri state or provider network needed.
#![cfg(feature = "pilot-credentials")]
#![allow(clippy::unwrap_used)]
// Import the real selector; app-only entry points are exercised by bin tests.
#[allow(dead_code)]
#[path = "../src/provider_source.rs"]
mod provider_source;
use selahcue_cloud::transport::{HttpResponse, HttpTransport, TransportError};
use selahcue_cloud::{generate_sermon_notes, LocalNoteProvider};
use selahcue_core::providers::{NoteError, ProvidersConfig};

static REQUESTS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
struct InspectTransport;
impl HttpTransport for InspectTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<HttpResponse, TransportError> {
        REQUESTS.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        assert_eq!(url, "https://api.openai.com/v1/responses");
        assert!(
            bearer == Some("synthetic-openai-fixture-only"),
            "request must use the synthetic package credential"
        );
        let body: serde_json::Value = serde_json::from_str(body).unwrap();
        assert_eq!(body["model"], "approved-fixture-model");
        Ok(HttpResponse {
            status: 401,
            body: "{}".into(),
        })
    }
    fn get(&self, _: &str, _: Option<&str>) -> Result<HttpResponse, TransportError> {
        panic!("unexpected GET")
    }
}

#[test]
fn selected_source_drives_both_readiness_and_real_authorization() {
    // Test runner sets this only for the synthetic valid build, never production.
    let ready = std::env::var("PILOT_TEST_EXPECT_READY").as_deref() == Ok("1");
    assert_eq!(provider_source::notes_model().is_some(), ready);
    assert_eq!(provider_source::transcription_readiness().is_ready(), ready);
    if let Ok(expected) = std::env::var("PILOT_TEST_EXPECT_EXPIRY") {
        let expected = if expected == "none" {
            None
        } else {
            Some(expected.parse::<u64>().expect("integer expiry expectation"))
        };
        assert_eq!(
            provider_source::access_status()
                .expect("pilot access status")
                .effective_expiry_unix_seconds,
            expected
        );
    }
    let status = provider_source::transcription_status();
    assert_eq!(status.ready, ready);
    assert_eq!(status.provider.is_some(), ready);
    assert!(!status.detail.contains(".env"));
    let client = provider_source::openai(InspectTransport);
    assert_eq!(client.is_some(), ready);
    let credential = provider_source::deepgram();
    assert_eq!(credential.is_ok(), ready);
    if !ready {
        let error = provider_source::deepgram().unwrap_err();
        assert!(
            !error.contains(".env"),
            "a pilot package cannot be repaired using developer environment"
        );
    }
    if ready {
        assert_eq!(
            provider_source::notes_model(),
            Some(("approved-fixture-model".into(), false))
        );
        let credential = credential.unwrap();
        assert!(
            credential.authorization_header_value() == "Token synthetic-deepgram-fixture-only",
            "credential must use synthetic package token authorization"
        );
        assert!(!format!("{credential:?}").contains("synthetic-deepgram"));
        assert!(!status.provider.unwrap().developer_key);
        use selahcue_stt_cloud::{
            DeepgramEndpoint, RequestSpec, StreamAuthorization, StreamParams,
        };
        let mut audio_config = ProvidersConfig::default();
        audio_config.settings.transcription_mode =
            selahcue_core::providers::TranscriptionMode::Cloud;
        assert!(
            StreamAuthorization::from_config(&audio_config).is_err(),
            "pilot credential cannot confer consent"
        );
        audio_config.consent.cloud_transcription = true;
        let authorization = StreamAuthorization::from_config(&audio_config).unwrap();
        let request = RequestSpec::build(
            &authorization,
            &DeepgramEndpoint::default(),
            &StreamParams::default(),
            credential,
        )
        .unwrap();
        assert!(request
            .url()
            .starts_with("wss://api.deepgram.com/v1/listen?"));
        assert!(request.url().contains("model=nova-3"));
        assert!(
            request.authorization_header_value() == "Token synthetic-deepgram-fixture-only",
            "request must use synthetic package token authorization"
        );
        assert!(!format!("{request:?}").contains("synthetic-deepgram"));
        let mut config = ProvidersConfig::default();
        config.consent.cloud_notes = true;
        // InspectTransport is only reached through the real provider request builder.
        let _ = generate_sermon_notes(
            &config,
            "synthetic completed transcript",
            true,
            &client.unwrap(),
            &LocalNoteProvider::new(),
        );
        assert_eq!(
            REQUESTS.load(std::sync::atomic::Ordering::SeqCst),
            1,
            "the authorization assertion must actually run"
        );
    }
}
#[test]
fn consent_and_explicit_generate_prevent_egress_with_valid_pilot_source() {
    struct Forbidden;
    impl HttpTransport for Forbidden {
        fn post_json(
            &self,
            _: &str,
            _: &str,
            _: Option<&str>,
        ) -> Result<HttpResponse, TransportError> {
            panic!("egress without consent")
        }
        fn get(&self, _: &str, _: Option<&str>) -> Result<HttpResponse, TransportError> {
            panic!("egress without consent")
        }
    }
    if std::env::var("PILOT_TEST_EXPECT_READY").as_deref() != Ok("1") {
        return;
    }
    let client = provider_source::openai(Forbidden).expect("valid fixture must reach gate");
    let mut config = ProvidersConfig::default();
    assert!(matches!(
        generate_sermon_notes(
            &config,
            "completed transcript",
            true,
            &client,
            &LocalNoteProvider::new()
        ),
        Err(NoteError::ConsentRequired)
    ));
    config.consent.cloud_notes = true;
    assert!(generate_sermon_notes(
        &config,
        "completed transcript",
        false,
        &client,
        &LocalNoteProvider::new()
    )
    .is_err());
}
#[test]
fn developer_environment_is_still_refused_in_release() {
    if cfg!(debug_assertions) {
        return;
    }
    assert!(selahcue_cloud::OpenAiNoteProvider::from_env(InspectTransport).is_none());
    assert!(selahcue_stt_cloud::developer_credential_from_env().is_err());
}

#[test]
fn release_executable_does_not_contain_the_test_clock_override() {
    use std::io::Read;
    let marker = b"SELAHCUE_PILOT_TEST_EPOCH";
    let mut binary = std::fs::File::open(env!("CARGO_BIN_EXE_selahcue-operator"))
        .expect("production executable");
    let mut tail = Vec::new();
    let mut chunk = [0u8; 16 * 1024];
    loop {
        let n = binary.read(&mut chunk).expect("read executable bytes");
        if n == 0 {
            break;
        }
        tail.extend_from_slice(&chunk[..n]);
        assert!(
            !tail.windows(marker.len()).any(|w| w == marker),
            "production executable must exclude test-clock environment lookup"
        );
        let retain = marker.len() - 1;
        if tail.len() > retain {
            tail.drain(..tail.len() - retain);
        }
    }
}
