#![cfg(feature = "pilot-credentials")]
#![allow(clippy::unwrap_used)]
#[allow(dead_code)]
#[path = "../src/provider_source.rs"]
mod source;
use std::io::{Read, Write};
use std::sync::mpsc;
use std::time::{Duration, Instant};

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
    // Each real worker gets a fresh process-wide source latch, never a test reset.
    let Ok(order) = std::env::var("P03_REJECTION_STOP_ORDER") else {
        let mut failed = Vec::new();
        for order in ["before-stop", "during-join"] {
            let child = std::process::Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "observed_transcription_rejection_does_not_disable_notes",
                    "--nocapture",
                ])
                .env("P03_REJECTION_STOP_ORDER", order)
                .output()
                .unwrap();
            if !child.status.success() {
                failed.push(format!(
                    "{order}: {}{}",
                    String::from_utf8_lossy(&child.stdout),
                    String::from_utf8_lossy(&child.stderr)
                ));
            }
        }
        assert!(failed.is_empty(), "{}", failed.join("\n"));
        return;
    };
    assert!(source::deepgram().is_ok());
    let status = source::transcription_session_status();
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let endpoint = selahcue_stt_cloud::DeepgramEndpoint::custom(format!(
        "ws://{}/",
        listener.local_addr().unwrap()
    ));
    let (connected_tx, connected_rx) = mpsc::channel();
    let (reject_tx, reject_rx) = mpsc::channel();
    let server = std::thread::spawn(move || {
        let (mut socket, _) = listener.accept().unwrap();
        socket
            .set_read_timeout(Some(Duration::from_secs(2)))
            .unwrap();
        let mut bytes = [0; 4096];
        assert!(
            socket.read(&mut bytes).unwrap() > 0,
            "real handshake is the premise"
        );
        connected_tx.send(()).unwrap();
        reject_rx.recv_timeout(Duration::from_secs(2)).unwrap();
        socket
            .write_all(
                b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            )
            .unwrap();
    });
    let mut config = selahcue_core::providers::ProvidersConfig::default();
    config.settings.transcription_mode = selahcue_core::providers::TranscriptionMode::Cloud;
    config.consent.cloud_transcription = true;
    let authorization = selahcue_stt_cloud::StreamAuthorization::from_config(&config).unwrap();
    let wire = selahcue_stt_cloud::transport::SessionConfig {
        endpoint,
        access_deadline: source::transcription_deadline().unwrap(),
        ..Default::default()
    };
    let worker = selahcue_stt_cloud::transport::CloudSttSession::start(
        &authorization,
        source::deepgram().unwrap(),
        wire,
        selahcue_stt_cloud::AudioRing::new(),
        selahcue_stt_cloud::SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    connected_rx.recv_timeout(Duration::from_secs(2)).unwrap();
    if order == "before-stop" {
        reject_tx.send(()).unwrap();
        let end = Instant::now() + Duration::from_secs(2);
        while status.get() != selahcue_stt_cloud::SessionState::CredentialRejected {
            assert!(Instant::now() < end, "real rejection not published");
            std::thread::yield_now();
        }
        // Stop is already pending before any capture-loop poll/fallback can observe it.
        worker.stop();
    } else {
        let (joining_tx, joining_rx) = mpsc::channel();
        let (joined_tx, joined_rx) = mpsc::channel();
        let closer = std::thread::spawn(move || {
            joining_tx.send(()).unwrap();
            worker.stop();
            joined_tx.send(()).unwrap();
        });
        joining_rx.recv_timeout(Duration::from_secs(2)).unwrap();
        assert!(
            matches!(
                joined_rx.recv_timeout(Duration::from_millis(30)),
                Err(mpsc::RecvTimeoutError::Timeout)
            ),
            "clean shutdown must still be held by the withheld provider handshake"
        );
        reject_tx.send(()).unwrap();
        joined_rx.recv_timeout(Duration::from_secs(2)).unwrap();
        closer.join().unwrap();
    }
    server.join().unwrap();
    let view = source::access_status().unwrap();
    assert_eq!(
        view.transcription_state,
        PilotState::Rejected,
        "{order}: worker rejection must survive capture stop"
    );
    assert_eq!(view.notes_state, PilotState::Available);
    assert!(
        source::deepgram().is_err(),
        "a subsequent start must refuse the rejected credential"
    );
    assert!(!source::transcription_readiness().is_ready());
    assert!(source::notes_model().is_some());
    assert!(source::openai(selahcue_cloud::MockTransport::failing()).is_some());
}
