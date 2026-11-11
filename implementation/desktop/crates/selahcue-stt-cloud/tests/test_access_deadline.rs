#![cfg(feature = "deepgram")]
#![allow(clippy::unwrap_used)]
use futures_util::StreamExt;
use selahcue_core::deadline::{AccessDeadline, Clock, ClockReading};
use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
use selahcue_stt_cloud::transport::{CloudSttSession, SessionConfig};
use selahcue_stt_cloud::{
    AudioChunk, AudioRing, Credential, DeepgramEndpoint, SegmentQueue, SessionState, SessionStatus,
    StreamAuthorization,
};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime};
use tokio::io::AsyncReadExt;
struct RealClock;
impl Clock for RealClock {
    fn now(&self) -> ClockReading {
        ClockReading {
            wall: Some(SystemTime::now()),
            monotonic: Instant::now(),
        }
    }
}
fn lease(ms: u64) -> AccessDeadline {
    AccessDeadline::admit(
        SystemTime::now() + Duration::from_millis(ms),
        Arc::new(RealClock),
    )
    .unwrap()
}
fn authorization() -> StreamAuthorization {
    let mut c = ProvidersConfig::default();
    c.settings.transcription_mode = TranscriptionMode::Cloud;
    c.consent.cloud_transcription = true;
    StreamAuthorization::from_config(&c).unwrap()
}
fn credential() -> Credential {
    Credential::pilot_key("synthetic-deepgram-native-fixture").unwrap()
}
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn stalled_connect_is_closed_and_worker_joined_at_expiry() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let server = tokio::spawn(async move {
        let (mut socket, _) = listener.accept().await.unwrap();
        let mut b = [0; 4096];
        let n = socket.read(&mut b).await.unwrap();
        assert!(n > 0);
        loop {
            match socket.read(&mut b).await {
                Ok(0) => break,
                Ok(_) => {}
                Err(_) => break,
            }
        }
        Instant::now()
    });
    let start = Instant::now();
    let config = SessionConfig {
        endpoint,
        access_deadline: Some(lease(150)),
        ..SessionConfig::default()
    };
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorization(),
        credential(),
        config,
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    let closed = tokio::time::timeout(Duration::from_millis(650), server)
        .await
        .expect("actual TCP close at lease cutoff")
        .unwrap();
    assert!(closed.duration_since(start) < Duration::from_millis(650));
    assert!(
        session.stop_immediately(),
        "worker must really join, not detach"
    );
    assert_eq!(status.get(), SessionState::AccessExpired);
}
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn active_socket_expires_without_courtesy_flush_and_without_reconnect() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let server = tokio::spawn(async move {
        let (s, _) = listener.accept().await.unwrap();
        let mut ws = tokio_tungstenite::accept_async(s).await.unwrap();
        let mut binary = false;
        let mut courtesy = false;
        while let Some(frame) = ws.next().await {
            match frame {
                Ok(tokio_tungstenite::tungstenite::Message::Binary(_)) => binary = true,
                Ok(tokio_tungstenite::tungstenite::Message::Text(t)) => {
                    courtesy |= t.contains("CloseStream")
                }
                Err(_) => break,
                _ => {}
            }
        }
        assert!(binary, "stream must actually send before expiry");
        assert!(!courtesy, "expiry must not flush cloud audio");
        assert!(
            tokio::time::timeout(Duration::from_millis(80), listener.accept())
                .await
                .is_err(),
            "no credential replay after expiry"
        );
    });
    let audio = AudioRing::new();
    audio.push(AudioChunk::from_pcm_i16(&[1; 320]));
    let config = SessionConfig {
        endpoint,
        access_deadline: Some(lease(180)),
        ..SessionConfig::default()
    };
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorization(),
        credential(),
        config,
        audio.clone(),
        SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    tokio::time::timeout(Duration::from_millis(680), server)
        .await
        .expect("actual WebSocket close")
        .unwrap();
    assert!(session.stop_immediately());
    assert_eq!(status.get(), SessionState::AccessExpired);
    assert!(audio.drain().is_empty());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn expiry_during_retry_backoff_never_replays_the_credential() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let server = tokio::spawn(async move {
        let (s, _) = listener.accept().await.unwrap();
        let mut ws = tokio_tungstenite::accept_async(s).await.unwrap();
        ws.close(None).await.unwrap();
        assert!(
            tokio::time::timeout(Duration::from_millis(350), listener.accept())
                .await
                .is_err(),
            "retry must never replay after the admitted deadline"
        );
    });
    let config = SessionConfig {
        endpoint,
        access_deadline: Some(lease(120)),
        retry: selahcue_stt_cloud::RetryPolicy {
            max_attempts: 5,
            initial_backoff: Duration::from_millis(200),
            max_backoff: Duration::from_millis(200),
        },
        ..SessionConfig::default()
    };
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorization(),
        credential(),
        config,
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    tokio::time::timeout(Duration::from_millis(620), server)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(status.get(), SessionState::AccessExpired);
    assert!(session.stop_immediately());
}
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn expired_before_dispatch_never_opens_a_socket() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let deadline = lease(20);
    tokio::time::sleep(Duration::from_millis(30)).await;
    let result = CloudSttSession::start(
        &authorization(),
        credential(),
        SessionConfig {
            endpoint,
            access_deadline: Some(deadline),
            ..SessionConfig::default()
        },
        AudioRing::new(),
        SegmentQueue::new(),
        SessionStatus::new(),
    );
    assert!(result.is_err());
    assert!(
        tokio::time::timeout(Duration::from_millis(40), listener.accept())
            .await
            .is_err()
    );
}
#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn pilot_rejection_is_terminal_and_never_retains_the_response_body() {
    use tokio::io::AsyncWriteExt;
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let server = tokio::spawn(async move {
        let (mut s, _) = listener.accept().await.unwrap();
        let mut b = [0; 4096];
        let n = s.read(&mut b).await.unwrap();
        assert!(n > 0);
        s.write_all(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 30\r\nConnection: close\r\n\r\nSYNTHETIC_PRIVATE_ERROR_MARKER").await.unwrap();
    });
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorization(),
        credential(),
        SessionConfig {
            endpoint,
            access_deadline: Some(lease(1000)),
            ..SessionConfig::default()
        },
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    server.await.unwrap();
    tokio::time::timeout(Duration::from_millis(500), async {
        while !status.get().is_terminal() {
            tokio::time::sleep(Duration::from_millis(5)).await;
        }
    })
    .await
    .unwrap();
    assert_eq!(status.get(), SessionState::CredentialRejected);
    assert!(!format!("{:?}", status.get()).contains("SYNTHETIC_PRIVATE_ERROR_MARKER"));
    assert!(session.stop_immediately());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn hard_deadline_closes_under_sustained_audio_and_peer_backpressure() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let endpoint = DeepgramEndpoint::custom(format!("ws://{}/", listener.local_addr().unwrap()));
    let server = tokio::spawn(async move {
        let (s, _) = listener.accept().await.unwrap();
        let mut ws = tokio_tungstenite::accept_async(s).await.unwrap();
        // Keep the peer open and unread while the real client fills socket buffers.
        tokio::time::sleep(Duration::from_millis(700)).await;
        let mut count = 0;
        while let Some(frame) = ws.next().await {
            match frame {
                Ok(tokio_tungstenite::tungstenite::Message::Binary(_)) => count += 1,
                Err(_) => break,
                _ => {}
            }
        }
        assert!(
            count > 0,
            "audio must actually have crossed the socket before cutoff"
        );
    });
    let audio = AudioRing::new();
    let producer_ring = audio.clone();
    let producer = tokio::spawn(async move {
        loop {
            producer_ring.push(AudioChunk::from_pcm_i16(&vec![1; 32_000]));
            tokio::time::sleep(Duration::from_millis(1)).await;
        }
    });
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorization(),
        credential(),
        SessionConfig {
            endpoint,
            access_deadline: Some(lease(500)),
            audio_poll_interval: Duration::from_millis(1),
            write_timeout: Duration::from_secs(5),
            ..SessionConfig::default()
        },
        audio.clone(),
        SegmentQueue::new(),
        status.clone(),
    )
    .unwrap();
    let completed = tokio::time::timeout(Duration::from_millis(1000), server).await;
    producer.abort();
    let joined = session.stop_immediately();
    assert!(joined, "must join a real worker, not detach an I/O task");
    assert_eq!(status.get(), SessionState::AccessExpired);
    assert!(
        audio.dropped_for_bound() > 0,
        "bounded producer/consumer pressure must actually be exercised"
    );
    completed
        .expect("actual backpressured socket must close within 500ms after cutoff")
        .unwrap();
}
