//! The real socket, driven against a **local stub Deepgram** rather than the live service.
//!
//! A suite that needs a paid third party and a network is a suite that gets skipped, so the
//! stub speaks Deepgram's wire format on loopback. What the live service is used for instead
//! is recording the latency and confirming the parameters — evidence on the ticket, not a
//! test that has to pass on someone else's uptime.
//!
//! These tests only exist in a `--features deepgram` build.
//!
//! # Why every test here is `multi_thread`
//!
//! Not a performance choice. The session's handle joins its worker thread on drop — it must,
//! or a session could outlive the handle and keep streaming a church's audio after the
//! operator believed it stopped. That join blocks the calling thread. On a single-threaded
//! runtime, with the stub server running as a task on that same runtime, the block starves
//! the server: it can never answer the handshake the worker is waiting on, the worker never
//! returns, and the join never completes. Found the hard way — a mutation run wedged for an
//! hour on exactly this. It is a property of the test harness, not of the client, but it is
//! the kind of hang that looks like a slow test until you sample the process.

#![cfg(feature = "deepgram")]
#![allow(clippy::unwrap_used)]
// The handshake-callback signature is tungstenite's, not ours: it returns
// `Result<Response, ErrorResponse>` and both variants are HTTP responses. Nothing here can
// shrink the error variant, and boxing a stub server's refusal would obscure the test.
#![allow(clippy::result_large_err)]

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpListener;
use tokio_tungstenite::tungstenite::handshake::server::{ErrorResponse, Request, Response};
use tokio_tungstenite::tungstenite::http::StatusCode;
use tokio_tungstenite::tungstenite::Message;

use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
use selahcue_stt_cloud::transport::{CloudSttSession, SessionConfig};
use selahcue_stt_cloud::{
    AudioChunk, AudioRing, Credential, DeepgramEndpoint, OperatorAction, RetryPolicy, SegmentQueue,
    SessionState, SessionStatus, StreamAuthorization, StreamParams,
};

const TEST_SECRET: &str = "dgkeyAAAABBBBCCCCDDDDEEEEFFFF0000111122223333";

/// What the stub saw on the upgrade request.
#[derive(Debug, Default, Clone)]
struct Handshake {
    authorization: String,
    uri: String,
}

fn authorised() -> StreamAuthorization {
    let mut config = ProvidersConfig::default();
    config.settings.transcription_mode = TranscriptionMode::Cloud;
    config.consent.cloud_transcription = true;
    StreamAuthorization::from_config(&config).expect("cloud + consent is authorised")
}

fn results(transcript: &str, is_final: bool) -> String {
    format!(
        r#"{{"type":"Results","start":0.5,"duration":1.0,"is_final":{is_final},
             "speech_final":false,
             "channel":{{"alternatives":[{{"transcript":"{transcript}"}}]}}}}"#
    )
}

/// A retry policy that gives up in well under a test timeout, so "it gives up" is observable
/// here rather than only in the pure policy suite.
fn brisk_retry() -> RetryPolicy {
    RetryPolicy {
        max_attempts: 2,
        initial_backoff: Duration::from_millis(20),
        max_backoff: Duration::from_millis(40),
    }
}

fn config_for(endpoint: DeepgramEndpoint, retry: RetryPolicy) -> SessionConfig {
    SessionConfig {
        endpoint,
        params: StreamParams::default(),
        retry,
        audio_poll_interval: Duration::from_millis(5),
        keep_alive_after: Duration::from_millis(50),
        connect_timeout: Duration::from_secs(5),
        stall_timeout: Duration::from_secs(30),
        reset_backoff_after: Duration::from_secs(30),
    }
}

/// Wait, bounded, for `check` to hold. Returns whether it ever did, so callers assert with a
/// message rather than hanging a CI run.
async fn within(limit: Duration, mut check: impl FnMut() -> bool) -> bool {
    let deadline = Instant::now() + limit;
    while Instant::now() < deadline {
        if check() {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
    check()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_stream_authenticates_by_header_and_delivers_interim_then_final_segments() {
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let seen = Arc::new(Mutex::new(Handshake::default()));
    let audio_bytes = Arc::new(AtomicUsize::new(0));

    let server_seen = Arc::clone(&seen);
    let server_audio = Arc::clone(&audio_bytes);
    let server = tokio::spawn(async move {
        let (stream, _) = listener.accept().await.expect("a client connects");
        let capture = Arc::clone(&server_seen);
        let callback = move |request: &Request, response: Response| {
            let mut recorded = capture.lock().unwrap_or_else(|e| e.into_inner());
            recorded.authorization = request
                .headers()
                .get("authorization")
                .and_then(|v| v.to_str().ok())
                .unwrap_or_default()
                .to_string();
            recorded.uri = request.uri().to_string();
            Ok(response)
        };
        let mut socket = tokio_tungstenite::accept_hdr_async(stream, callback)
            .await
            .expect("the upgrade succeeds");

        socket
            .send(Message::Text(results("turn with me to", false)))
            .await
            .expect("send interim");
        socket
            .send(Message::Text(results("Turn with me to John three.", true)))
            .await
            .expect("send final");
        // Deepgram sends empty interims during silence; the queue must refuse them.
        socket
            .send(Message::Text(results("", false)))
            .await
            .expect("send empty interim");

        while let Some(Ok(message)) = socket.next().await {
            if let Message::Binary(bytes) = message {
                server_audio.fetch_add(bytes.len(), Ordering::SeqCst);
            }
        }
    });

    let queue = SegmentQueue::new();
    let ring = AudioRing::new();
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config_for(
            DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
            RetryPolicy::default(),
        ),
        ring.clone(),
        queue.clone(),
        status.clone(),
    )
    .expect("an authorised loopback session starts");

    assert!(
        within(Duration::from_secs(10), || queue.len() >= 2).await,
        "the stub's two transcripts never reached the queue (queue holds {}, session is {:?})",
        queue.len(),
        status.get()
    );

    ring.push(AudioChunk::from_pcm_i16(&[1, 2, 3, 4]));
    assert!(
        within(Duration::from_secs(10), || audio_bytes
            .load(Ordering::SeqCst)
            >= 8)
        .await,
        "audio pushed into the ring never reached the socket; the stream is receive-only"
    );

    let segments = queue.drain();
    assert_eq!(
        segments.len(),
        2,
        "the empty interim was queued as well; a silent passage would evict real text"
    );
    assert_eq!(segments[0].text, "turn with me to");
    assert!(
        !segments[0].is_final,
        "the interim result arrived marked as settled, so the console could not style it as \
         provisional"
    );
    assert_eq!(segments[1].text, "Turn with me to John three.");
    assert!(
        segments[1].is_final,
        "the final result arrived marked as provisional, so nothing would ever settle"
    );
    assert_eq!(segments[0].start_ms, 500);
    assert_eq!(segments[0].end_ms, 1_500);

    let handshake = seen.lock().unwrap_or_else(|e| e.into_inner()).clone();
    assert_eq!(
        handshake.authorization,
        format!("Token {TEST_SECRET}"),
        "the raw API key was not sent with Deepgram's Token spelling"
    );
    assert!(
        handshake.uri.contains("model=nova-3") && handshake.uri.contains("interim_results=true"),
        "the wire parameters did not reach the request line: {}",
        handshake.uri
    );
    assert!(
        !handshake.uri.contains(TEST_SECRET),
        "the credential was sent in the URL, where proxies log it: {}",
        handshake.uri
    );

    session.stop();
    let _ = server.await;
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_rejected_credential_stops_immediately_rather_than_retrying() {
    // Retrying a key the service has already refused cannot succeed. The observable claim is
    // that the session reaches a terminal Failed state, with the credential action, in far
    // less time than even this brisk retry policy would take to exhaust itself.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let attempts = Arc::new(AtomicUsize::new(0));

    let server_attempts = Arc::clone(&attempts);
    let server = tokio::spawn(async move {
        loop {
            let Ok((stream, _)) = listener.accept().await else {
                return;
            };
            server_attempts.fetch_add(1, Ordering::SeqCst);
            let callback =
                |_request: &Request, _response: Response| -> Result<Response, ErrorResponse> {
                    let mut refusal = ErrorResponse::new(None);
                    *refusal.status_mut() = StatusCode::UNAUTHORIZED;
                    Err(refusal)
                };
            let _ = tokio_tungstenite::accept_hdr_async(stream, callback).await;
        }
    });

    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config_for(
            DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
            RetryPolicy {
                max_attempts: 50,
                initial_backoff: Duration::from_secs(30),
                max_backoff: Duration::from_secs(30),
            },
        ),
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts; the rejection is discovered on connect");

    assert!(
        within(Duration::from_secs(10), || status.get().is_terminal()).await,
        "the session never reached a terminal state after a 401 (it is {:?}); with a 30-second \
         backoff and 50 attempts, retrying would leave the operator watching a spinner for \
         twenty-five minutes",
        status.get()
    );

    match status.get() {
        SessionState::Failed { action, message } => {
            assert_eq!(
                action,
                OperatorAction::ReplaceCredential,
                "a rejected credential did not prescribe replacing the credential"
            );
            assert!(
                message.contains("401"),
                "the failure message hides the status: {message}"
            );
            assert!(
                !message.contains(TEST_SECRET),
                "the credential reached the failure message the console displays: {message}"
            );
        }
        other => panic!("a 401 produced {other:?} rather than a credential failure"),
    }
    assert_eq!(
        attempts.load(Ordering::SeqCst),
        1,
        "the client reconnected after a 401; a revoked key would be retried indefinitely"
    );

    session.stop();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_dropped_socket_retries_a_bounded_number_of_times_and_then_gives_up_cleanly() {
    // The stub accepts and immediately closes, so every attempt fails the same way. The claim
    // is that this ends — bounded attempts, then a terminal state — rather than reconnecting
    // for the rest of the service.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let accepted = Arc::new(AtomicUsize::new(0));

    let server_accepted = Arc::clone(&accepted);
    let server = tokio::spawn(async move {
        loop {
            let Ok((stream, _)) = listener.accept().await else {
                return;
            };
            server_accepted.fetch_add(1, Ordering::SeqCst);
            if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
                let _ = socket.close(None).await;
            }
        }
    });

    let retry = brisk_retry();
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config_for(
            DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
            retry.clone(),
        ),
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts");

    assert!(
        within(Duration::from_secs(15), || status.get().is_terminal()).await,
        "the session never gave up (it is {:?}); a dropped connection would retry forever and \
         no actionable message would ever reach the operator",
        status.get()
    );

    match status.get() {
        SessionState::Failed { action, message } => {
            assert_eq!(action, OperatorAction::CheckNetwork);
            assert!(
                message.contains("gave up"),
                "the terminal message does not say it gave up: {message}"
            );
        }
        other => panic!("expected a give-up failure, got {other:?}"),
    }

    // Exercised before contract: it really did retry, and it really did stop. Without the
    // lower bound this test would pass on a client that never retried at all.
    let tries = accepted.load(Ordering::SeqCst);
    assert!(
        tries >= 2,
        "the client only connected {tries} time(s), so the retry path went unexercised and the \
         bound below proves nothing"
    );
    assert!(
        tries <= retry.max_attempts as usize + 1,
        "the client connected {tries} times against a bound of {} attempts plus the first try",
        retry.max_attempts
    );

    session.stop();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn dropping_the_session_handle_stops_the_stream() {
    // A session that outlived its handle would keep streaming a church's audio after the
    // operator believed it stopped.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();

    let server = tokio::spawn(async move {
        let Ok((stream, _)) = listener.accept().await else {
            return;
        };
        if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
            while socket.next().await.is_some() {}
        }
    });

    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config_for(
            DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
            brisk_retry(),
        ),
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts");

    assert!(
        within(Duration::from_secs(10), || status.get().is_streaming()).await,
        "the session never began streaming (it is {:?}), so dropping it below proves nothing",
        status.get()
    );

    drop(session);

    assert_eq!(
        status.get(),
        SessionState::Stopped,
        "dropping the handle left the session running"
    );
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_session_to_a_cleartext_non_loopback_endpoint_never_opens_a_socket() {
    let outcome = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config_for(
            DeepgramEndpoint::custom("ws://api.deepgram.com/v1/listen"),
            brisk_retry(),
        ),
        AudioRing::new(),
        SegmentQueue::new(),
        SessionStatus::new(),
    );
    assert!(
        matches!(
            outcome,
            Err(selahcue_stt_cloud::DeepgramError::InsecureEndpoint { .. })
        ),
        "a cleartext endpoint was allowed to start a session, so the credential would go out \
         in the clear before anything could stop it"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_peer_that_accepts_but_never_answers_times_out_instead_of_hanging_forever() {
    // The failure a bounded retry policy cannot save you from on its own: nothing ever fails,
    // so nothing is ever retried, so the bound never engages. A peer that completes the TCP
    // handshake and then says nothing holds the session open indefinitely — the operator sees
    // "connecting…" for the rest of the service and is never told anything is wrong.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let accepted = Arc::new(AtomicUsize::new(0));

    let server_accepted = Arc::clone(&accepted);
    let server = tokio::spawn(async move {
        let mut held = Vec::new();
        loop {
            let Ok((stream, _)) = listener.accept().await else {
                return;
            };
            server_accepted.fetch_add(1, Ordering::SeqCst);
            // Hold the connection open and answer nothing at all.
            held.push(stream);
        }
    });

    let mut config = config_for(
        DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
        RetryPolicy {
            max_attempts: 1,
            initial_backoff: Duration::from_millis(20),
            max_backoff: Duration::from_millis(20),
        },
    );
    config.connect_timeout = Duration::from_millis(200);

    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config,
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts");

    assert!(
        within(Duration::from_secs(10), || status.get().is_terminal()).await,
        "the session never reached a terminal state against a peer that accepts and says \
         nothing (it is {:?}) — it is hanging, and a hang is not a slow success",
        status.get()
    );

    // Exercised before contract: the stub really did accept, so the timeout fired on a live
    // connection rather than on a refused one, which is a different code path entirely.
    assert!(
        accepted.load(Ordering::SeqCst) >= 1,
        "the stub never accepted a connection, so this test exercised connection refusal, not \
         the connect timeout"
    );

    match status.get() {
        SessionState::Failed { action, message } => {
            assert_eq!(action, OperatorAction::CheckNetwork);
            assert!(
                !message.contains(TEST_SECRET),
                "the credential reached the failure message: {message}"
            );
        }
        other => panic!("expected a terminal network failure, got {other:?}"),
    }

    session.stop();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_stream_that_goes_quiet_mid_sermon_is_noticed_rather_than_waited_on_forever() {
    // The same class as the connect timeout, one stage later — and this is the one that bites
    // DURING a service rather than before it. Deepgram completes the handshake, accepts every
    // byte of audio, and never answers. A bounded retry policy cannot help: the bound only
    // engages once something fails, and a peer that is merely quiet never does. Without a
    // stall timeout the operator watches a transcript panel that has silently stopped filling
    // and is told nothing, which is the one unacceptable failure mode.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let audio_bytes = Arc::new(AtomicUsize::new(0));

    let server_audio = Arc::clone(&audio_bytes);
    let server = tokio::spawn(async move {
        let Ok((stream, _)) = listener.accept().await else {
            return;
        };
        // Handshake normally, then swallow audio and answer nothing at all.
        if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
            while let Some(Ok(message)) = socket.next().await {
                if let Message::Binary(bytes) = message {
                    server_audio.fetch_add(bytes.len(), Ordering::SeqCst);
                }
            }
        }
    });

    let mut config = config_for(
        DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
        RetryPolicy {
            max_attempts: 1,
            initial_backoff: Duration::from_millis(20),
            max_backoff: Duration::from_millis(20),
        },
    );
    config.stall_timeout = Duration::from_millis(300);

    let ring = AudioRing::new();
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config,
        ring.clone(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts");

    // Exercised before contract, part one: the socket really did open. Otherwise this test
    // would be re-testing the connect timeout under a different name.
    assert!(
        within(Duration::from_secs(10), || status.get().is_streaming()
            || status.get().is_terminal())
        .await,
        "the session never got past connecting (it is {:?})",
        status.get()
    );

    // Keep audio flowing, because the stall bound is deliberately conditioned on our having
    // given the peer something to answer.
    let feeder_ring = ring.clone();
    let feeder = tokio::spawn(async move {
        for _ in 0..200 {
            feeder_ring.push(AudioChunk::from_pcm_i16(&[0; 160]));
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    });

    assert!(
        within(Duration::from_secs(15), || status.get().is_terminal()).await,
        "an established stream that answered nothing was waited on indefinitely (it is {:?}) \
         — mid-sermon the panel would stop filling and say nothing about it",
        status.get()
    );

    // Exercised before contract, part two: the peer actually received audio, so the stall was
    // detected while we were giving it something to answer rather than on an idle link.
    assert!(
        audio_bytes.load(Ordering::SeqCst) > 0,
        "the stub never received any audio, so the stall bound fired on an idle stream — which \
         is the false alarm this bound is specifically conditioned to avoid"
    );

    match status.get() {
        SessionState::Failed { action, message } => {
            assert_eq!(action, OperatorAction::CheckNetwork);
            assert!(
                !message.contains(TEST_SECRET),
                "the credential reached the failure message: {message}"
            );
        }
        other => panic!("expected a terminal network failure, got {other:?}"),
    }

    session.stop();
    feeder.abort();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn an_idle_stream_with_no_audio_is_not_torn_down_as_a_stall() {
    // The positive control for the bound above. A service between items sends no audio and
    // hears nothing back, and that is entirely normal — a stall bound that fired on it would
    // drop cloud transcription every time the preacher paused between sessions.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();

    let server = tokio::spawn(async move {
        let Ok((stream, _)) = listener.accept().await else {
            return;
        };
        if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
            while socket.next().await.is_some() {}
        }
    });

    let mut config = config_for(
        DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
        brisk_retry(),
    );
    config.stall_timeout = Duration::from_millis(100);

    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config,
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts");

    assert!(
        within(Duration::from_secs(10), || status.get().is_streaming()).await,
        "the session never began streaming, so this control proves nothing"
    );

    // Well past the stall timeout, with no audio sent.
    tokio::time::sleep(Duration::from_millis(600)).await;

    assert!(
        status.get().is_streaming(),
        "an idle stream with no audio in flight was torn down as a stall (it is {:?}) — cloud \
         transcription would drop every time the room went quiet",
        status.get()
    );

    session.stop();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_panic_inside_the_worker_becomes_a_terminal_state_not_an_eternal_connecting() {
    // Found the hard way. rustls 0.23 refuses to pick a crypto backend for itself, and the
    // first real TLS connection panicked on the worker thread — where a panic is invisible.
    // The session did not fail; it simply never left `Connecting`, forever. Nothing in this
    // file could have caught it, because every other test here connects over loopback `ws://`
    // and never builds a TLS session at all.
    //
    // `ensure_crypto_provider` removes that particular panic. This asserts the containment
    // behind it: whatever panics, the operator is told, rather than left watching a spinner.
    //
    // A zero audio-poll interval is a real panic reachable through the public API —
    // `tokio::time::interval` rejects a zero period — so this exercises the containment
    // without a test-only injection hook.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();

    let server = tokio::spawn(async move {
        let Ok((stream, _)) = listener.accept().await else {
            return;
        };
        if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
            while socket.next().await.is_some() {}
        }
    });

    let mut config = config_for(
        DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
        brisk_retry(),
    );
    config.audio_poll_interval = Duration::ZERO;

    // The worker's panic is expected and its backtrace is noise; keep the test output honest
    // about what it is doing rather than letting a stray panic message look like a failure.
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(|_| {}));

    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config,
        AudioRing::new(),
        SegmentQueue::new(),
        status.clone(),
    )
    .expect("the session starts; the panic happens on the worker");

    let reached = within(Duration::from_secs(10), || status.get().is_terminal()).await;
    std::panic::set_hook(previous);

    assert!(
        reached,
        "a worker panic left the session at {:?} — the console would show that state for the \
         rest of the service and never resolve it",
        status.get()
    );
    match status.get() {
        SessionState::Failed { action, message } => {
            assert_eq!(
                action,
                OperatorAction::ReportDefect,
                "a defect in our own code was reported as something the operator could fix"
            );
            assert!(
                message.contains("on-device"),
                "the message does not tell the operator that on-device transcription still \
                 works: {message}"
            );
        }
        other => panic!("expected a terminal defect state, got {other:?}"),
    }

    session.stop();
    server.abort();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn a_slow_but_steady_peer_is_healthy_rather_than_stalled() {
    // The COMPLEMENT of the stall test, and the one that matters more in a church. Two
    // verifications of a bound agree for nothing if both drive the same shape of failure:
    // "stops sending" and "keeps sending slowly" are different peers, and only the first is
    // conspicuous. A preacher pauses; a hymn plays; Deepgram answers less often. If the bound
    // read a slow peer as a dead one it would drop cloud transcription during the quiet parts
    // of a service — the parts where a stall is most likely and least warranted.
    //
    // This asserts the liveness clock resets on ANY frame, so a drip well inside the bound is
    // health rather than a countdown that merely restarts late.
    let listener = TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind loopback");
    let port = listener.local_addr().expect("local addr").port();
    let frames_sent = Arc::new(AtomicUsize::new(0));

    let server_frames = Arc::clone(&frames_sent);
    let server = tokio::spawn(async move {
        let Ok((stream, _)) = listener.accept().await else {
            return;
        };
        if let Ok(mut socket) = tokio_tungstenite::accept_async(stream).await {
            // A drip: one frame every 120 ms against a 400 ms bound. Slow, never silent.
            for i in 0..12 {
                tokio::time::sleep(Duration::from_millis(120)).await;
                if socket
                    .send(Message::Text(results(&format!("word {i}"), false)))
                    .await
                    .is_err()
                {
                    return;
                }
                server_frames.fetch_add(1, Ordering::SeqCst);
            }
            while socket.next().await.is_some() {}
        }
    });

    let mut config = config_for(
        DeepgramEndpoint::custom(format!("ws://127.0.0.1:{port}/v1/listen")),
        brisk_retry(),
    );
    config.stall_timeout = Duration::from_millis(400);

    let ring = AudioRing::new();
    let queue = SegmentQueue::new();
    let status = SessionStatus::new();
    let session = CloudSttSession::start(
        &authorised(),
        Credential::developer_key(TEST_SECRET).expect("fixture key"),
        config,
        ring.clone(),
        queue.clone(),
        status.clone(),
    )
    .expect("the session starts");

    assert!(
        within(Duration::from_secs(10), || status.get().is_streaming()).await,
        "the session never began streaming, so this control proves nothing"
    );

    // Audio flowing throughout, so the stall bound is armed rather than dormant — otherwise
    // this test would pass simply because the bound was never eligible to fire.
    let feeder_ring = ring.clone();
    let feeder = tokio::spawn(async move {
        for _ in 0..200 {
            feeder_ring.push(AudioChunk::from_pcm_i16(&[0; 160]));
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    });

    // Well past the bound in total elapsed time, but never a gap that reaches it.
    tokio::time::sleep(Duration::from_millis(1_400)).await;

    // Exercised before contract: the drip really happened and really spanned more than the
    // bound, so "still streaming" is a statement about a slow peer and not about a quiet test.
    let sent = frames_sent.load(Ordering::SeqCst);
    assert!(
        sent >= 4,
        "the stub only managed {sent} frames, so the drip did not span the stall bound and \
         this test did not exercise it"
    );

    assert!(
        status.get().is_streaming(),
        "a slow but steady peer was torn down as a stall (it is {:?}) — cloud transcription \
         would drop during exactly the quiet stretches of a service where Deepgram legitimately \
         answers less often",
        status.get()
    );

    session.stop();
    feeder.abort();
    server.abort();
}
