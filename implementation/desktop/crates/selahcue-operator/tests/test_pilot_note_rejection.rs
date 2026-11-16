#![cfg(feature = "pilot-credentials")]
#![allow(clippy::unwrap_used)]
#[allow(dead_code)]
#[path = "../src/provider_source.rs"]
mod source;
use std::io::{Read, Write};
#[test]
fn real_notes_rejection_observer_latches_only_notes_and_exposes_no_raw_body() {
    use source::PilotState;
    if std::env::var("PILOT_TEST_EXPECT_READY").as_deref() != Ok("1") {
        assert_ne!(
            source::access_status().unwrap().notes_state,
            PilotState::Available
        );
        return;
    }
    assert_eq!(
        source::access_status().unwrap().notes_state,
        PilotState::Available
    );
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    let server = std::thread::spawn(move || {
        let (mut s, _) = listener.accept().unwrap();
        let mut bytes = [0; 4096];
        let _ = s.read(&mut bytes);
        let _=s.write_all(b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 99999\r\n\r\nSYNTHETIC_PRIVATE_ERROR_MARKER");
    });
    let transport = source::pilot_notes_transport_with(
        selahcue_cloud::deadline_transport::DeadlineTransport::new_for_loopback_tests,
    )
    .unwrap();
    let client = source::openai(transport).unwrap().with_base_url(base);
    let mut config = selahcue_core::providers::ProvidersConfig::default();
    config.consent.cloud_notes = true;
    let result = selahcue_cloud::generate_sermon_notes(
        &config,
        "synthetic completed transcript",
        true,
        &client,
        &selahcue_cloud::LocalNoteProvider::new(),
    );
    assert!(result.is_err());
    server.join().unwrap();
    let status = source::access_status().unwrap();
    assert_eq!(status.notes_state, PilotState::Rejected);
    assert_eq!(status.transcription_state, PilotState::Available);
    assert!(source::notes_model().is_none());
    assert!(
        source::deepgram().is_ok(),
        "healthy transcription remains usable"
    );
    assert!(!serde_json::to_string(&status)
        .unwrap()
        .contains("SYNTHETIC_PRIVATE_ERROR_MARKER"));
    assert_eq!(
        source::notes_fault().unwrap().code(),
        "pilot_access_rejected"
    );
}
