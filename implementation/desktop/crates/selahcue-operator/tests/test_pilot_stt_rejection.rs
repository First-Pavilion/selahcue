#![cfg(feature = "pilot-credentials")]
#![allow(clippy::unwrap_used)]
#[allow(dead_code)]
#[path = "../src/provider_source.rs"]
mod source;
#[test]
fn observed_transcription_rejection_does_not_disable_notes() {
    use source::PilotState;
    if std::env::var("PILOT_TEST_EXPECT_READY").as_deref() != Ok("1") {
        assert_ne!(
            source::access_status().unwrap().transcription_state,
            PilotState::Available
        );
        return;
    }
    assert!(source::deepgram().is_ok());
    source::mark_transcription_rejected();
    let status = source::access_status().unwrap();
    assert_eq!(status.transcription_state, PilotState::Rejected);
    assert_eq!(status.notes_state, PilotState::Available);
    assert!(source::deepgram().is_err());
    assert!(source::notes_model().is_some());
    assert!(source::openai(selahcue_cloud::MockTransport::failing()).is_some());
}
