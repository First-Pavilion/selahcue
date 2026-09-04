//! The real Deepgram WebSocket transport — the only part of this crate behind the
//! off-by-default `deepgram` feature.
//!
//! Everything that could be decided without a socket already has been, in the default build,
//! so what is left here is genuinely socket work: open the connection, forward audio, read
//! frames, reconnect, give up. Each of those consults a policy that is tested elsewhere
//! rather than deciding anything itself.
//!
//! # It runs on its own thread, with its own runtime
//!
//! [`CloudSttSession::start`] spawns a thread and builds a single-threaded Tokio runtime
//! inside it, so the caller needs no runtime of its own and the console's thread is never
//! borrowed by network work. This mirrors how the on-device engine's worker is run, and it is
//! what makes [`crate::CloudTranscriptProvider::poll`] able to promise it never blocks: the
//! poll and the socket share nothing but a mutex around a bounded queue.
//!
//! # Failure behaviour
//!
//! - A **transport** failure backs off and retries, bounded, then gives up cleanly.
//! - A **rejected credential** is not retried at all: no number of reconnections will make a
//!   revoked key work, and retrying hides the one message the operator needs behind a
//!   spinner.
//! - A frame this client cannot read is **dropped**, not fatal. Ending a service's
//!   transcription over one malformed frame is a worse failure than missing a sentence.
//! - Nothing here can blank or delay live output. It touches no presenter, no renderer and no
//!   control path — its only outputs are a bounded queue and a status cell.

use std::panic::AssertUnwindSafe;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Once};
use std::time::{Duration, Instant};

use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::header::AUTHORIZATION;
use tokio_tungstenite::tungstenite::http::HeaderValue;
use tokio_tungstenite::tungstenite::protocol::WebSocketConfig;
use tokio_tungstenite::tungstenite::{Error as WsError, Message};

use crate::audio::AudioRing;
use crate::credential::Credential;
use crate::error::{DeepgramError, OperatorAction};
use crate::protocol::{parse_frame, DeepgramFrame, CLOSE_STREAM, KEEP_ALIVE, MAX_FRAME_BYTES};
use crate::provider::{SessionState, SessionStatus};
use crate::queue::SegmentQueue;
use crate::retry::RetryPolicy;
use crate::session::{DeepgramEndpoint, RequestSpec, StreamAuthorization, StreamParams};

/// How the session behaves, separately from what it connects to.
#[derive(Debug, Clone)]
pub struct SessionConfig {
    /// Where to connect.
    pub endpoint: DeepgramEndpoint,
    /// The wire parameters.
    pub params: StreamParams,
    /// Reconnection policy.
    pub retry: RetryPolicy,
    /// How often the loop wakes to forward buffered audio.
    pub audio_poll_interval: Duration,
    /// How long without sending anything before a `KeepAlive` goes out. Deepgram closes an
    /// idle stream; a silent passage in a service is not the end of the sermon.
    pub keep_alive_after: Duration,
    /// How long an established stream may go without a single frame from Deepgram **while
    /// audio is being sent**, before it counts as a failure.
    ///
    /// [`SessionConfig::connect_timeout`] closes "present and silent at the handshake". This
    /// closes the same class one stage later — and that is the one that bites *during* a
    /// sermon rather than before it. If Deepgram accepts audio and simply stops answering,
    /// nothing in a bounded retry policy helps: the retry bound only engages once something
    /// fails, and a peer that is merely quiet never does. The operator would watch a transcript
    /// panel that has silently stopped filling and be told nothing.
    ///
    /// Deliberately conditioned on audio **actually having been sent** since the last frame. A
    /// session nobody is speaking into is legitimately quiet in both directions, and tearing
    /// that down would be a false alarm on a service that is merely between items. While audio
    /// is flowing, Deepgram answers continuously — including empty interim results during
    /// silence in the room — so silence from the peer *then* is genuinely anomalous.
    pub stall_timeout: Duration,
    /// How long to wait for the socket to open before calling it a transport failure.
    ///
    /// Without this, a peer that accepts the TCP connection but never completes the WebSocket
    /// handshake holds the session open indefinitely: the retry bound never engages, because
    /// nothing ever fails. A hang is not a slow success, and it is the one failure mode a
    /// bounded retry policy cannot save you from on its own.
    pub connect_timeout: Duration,
    /// How long a connection must survive before the backoff counter resets.
    ///
    /// Without this the retry bound is defeated by its own success: a socket that connects
    /// and immediately drops would reset the counter every cycle and reconnect forever, which
    /// is the exact behaviour [`RetryPolicy`] exists to prevent. A connection only "counts"
    /// once it has stayed up this long.
    pub reset_backoff_after: Duration,
}

impl Default for SessionConfig {
    fn default() -> Self {
        SessionConfig {
            endpoint: DeepgramEndpoint::default(),
            params: StreamParams::default(),
            retry: RetryPolicy::default(),
            audio_poll_interval: Duration::from_millis(20),
            keep_alive_after: Duration::from_secs(5),
            connect_timeout: Duration::from_secs(10),
            stall_timeout: Duration::from_secs(30),
            reset_backoff_after: Duration::from_secs(30),
        }
    }
}

/// Install rustls' crypto backend, once per process.
///
/// rustls 0.23 will not choose a provider for itself, and `tokio-tungstenite`'s TLS feature
/// enables neither backend — so without this the **first real TLS connection panics**, on the
/// worker thread, where the panic is invisible: the session simply never leaves `Connecting`.
///
/// Nothing in the stub-socket suite could catch this, because those tests connect over
/// loopback `ws://` and never build a TLS session at all. It was found by running against the
/// live service, which is the entire reason that measurement exists.
///
/// `install_default` returns `Err` if a provider is already installed — by the LAN transport,
/// say, in the same process. That is success for our purposes, not failure.
fn ensure_crypto_provider() {
    static ONCE: Once = Once::new();
    ONCE.call_once(|| {
        let _ = rustls::crypto::ring::default_provider().install_default();
    });
}

/// A running Deepgram streaming session.
///
/// Dropping it signals the worker to stop and waits for it, so a session cannot outlive the
/// handle and keep streaming a church's audio after the operator thinks it stopped.
#[derive(Debug)]
pub struct CloudSttSession {
    stop: Arc<AtomicBool>,
    join: Option<std::thread::JoinHandle<()>>,
}

impl CloudSttSession {
    /// Open a session.
    ///
    /// Takes the [`StreamAuthorization`] by reference, so this cannot be called without the
    /// consent gate having passed, and the [`Credential`] **by value as a parameter** — Phase
    /// 2 passes a server-minted grant token here instead of a developer key, and that is the
    /// whole of the change.
    ///
    /// Returns before the socket is open; watch `status` for progress. Failing fast here
    /// covers only what can be known without a network round trip: consent, the credential's
    /// shape, and endpoint confidentiality.
    pub fn start(
        authorization: &StreamAuthorization,
        credential: Credential,
        config: SessionConfig,
        audio: AudioRing,
        queue: SegmentQueue,
        status: SessionStatus,
    ) -> Result<Self, DeepgramError> {
        let spec = RequestSpec::build(
            authorization,
            &config.endpoint,
            &config.params,
            credential.clone(),
        )?;
        ensure_crypto_provider();
        let stop = Arc::new(AtomicBool::new(false));
        let worker_stop = Arc::clone(&stop);
        let join = std::thread::Builder::new()
            .name("selahcue-stt-cloud".to_string())
            .spawn(move || {
                let runtime = match tokio::runtime::Builder::new_current_thread()
                    .enable_all()
                    .build()
                {
                    Ok(runtime) => runtime,
                    Err(e) => {
                        let error = DeepgramError::transport(e, Some(&credential));
                        status.set(SessionState::Failed {
                            action: error.operator_action(),
                            message: error.to_string(),
                        });
                        return;
                    }
                };
                // A panic here would otherwise kill the worker thread silently, leaving the
                // console showing "connecting…" for the rest of the service with nothing ever
                // resolving it. Silence is the one unacceptable failure mode, so a panic is
                // converted into an honest terminal state. Defence in depth behind
                // `ensure_crypto_provider`, which removes the panic we actually hit.
                let outcome = std::panic::catch_unwind(AssertUnwindSafe(|| {
                    runtime.block_on(run(spec, config, audio, queue, status.clone(), worker_stop))
                }));
                if outcome.is_err() {
                    status.set(SessionState::Failed {
                        action: OperatorAction::ReportDefect,
                        message: "cloud transcription stopped unexpectedly; on-device \
                                  transcription is unaffected"
                            .to_string(),
                    });
                }
            })
            .map_err(|e| DeepgramError::transport(e, None))?;
        Ok(CloudSttSession {
            stop,
            join: Some(join),
        })
    }

    /// Ask the session to stop, and wait for it. Deepgram is told to flush first, so the last
    /// sentence of a sermon is not lost to an abrupt close.
    pub fn stop(mut self) {
        self.shutdown();
    }

    fn shutdown(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(join) = self.join.take() {
            let _ = join.join();
        }
    }
}

impl Drop for CloudSttSession {
    fn drop(&mut self) {
        self.shutdown();
    }
}

/// The connect → stream → back off → give up loop.
async fn run(
    spec: RequestSpec,
    config: SessionConfig,
    audio: AudioRing,
    queue: SegmentQueue,
    status: SessionStatus,
    stop: Arc<AtomicBool>,
) {
    let mut attempt: u32 = 0;
    loop {
        if stop.load(Ordering::SeqCst) {
            status.set(SessionState::Stopped);
            return;
        }
        status.set(if attempt == 0 {
            SessionState::Connecting
        } else {
            SessionState::Reconnecting {
                attempt,
                of: config.retry.max_attempts,
            }
        });

        let attempt_outcome =
            match tokio::time::timeout(config.connect_timeout, connect(&spec)).await {
                Ok(result) => result,
                Err(_) => Err(DeepgramError::transport(
                    format!(
                        "timed out after {:?} opening the Deepgram socket",
                        config.connect_timeout
                    ),
                    Some(spec.credential()),
                )),
            };

        let outcome = match attempt_outcome {
            Ok(socket) => {
                status.set(SessionState::Streaming);
                let opened_at = Instant::now();
                let result = pump(socket, &config, &audio, &queue, &spec, &stop).await;
                // A connection only earns a backoff reset by staying up. See
                // `SessionConfig::reset_backoff_after`.
                if opened_at.elapsed() >= config.reset_backoff_after {
                    attempt = 0;
                }
                match result {
                    Ok(()) => {
                        status.set(SessionState::Stopped);
                        return;
                    }
                    Err(e) => e,
                }
            }
            Err(e) => e,
        };

        if !outcome.is_retryable() {
            status.set(SessionState::Failed {
                action: outcome.operator_action(),
                message: outcome.to_string(),
            });
            return;
        }
        if stop.load(Ordering::SeqCst) {
            status.set(SessionState::Stopped);
            return;
        }
        match config.retry.backoff_for_attempt(attempt) {
            Some(wait) => {
                sleep_interruptible(wait, &stop).await;
                attempt = attempt.saturating_add(1);
            }
            None => {
                let gave_up = DeepgramError::GaveUp {
                    attempts: config.retry.max_attempts,
                };
                status.set(SessionState::Failed {
                    action: gave_up.operator_action(),
                    message: gave_up.to_string(),
                });
                return;
            }
        }
    }
}

type Socket =
    tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

/// Open the socket, authenticating by header.
///
/// The credential goes in the `Authorization` header, never the URL: a key in a query string
/// ends up in proxy logs and browser histories. An HTTP `401`/`403` on the upgrade is
/// reported as [`DeepgramError::CredentialRejected`] rather than as a transport failure,
/// because it is the one connection error retrying cannot fix.
async fn connect(spec: &RequestSpec) -> Result<Socket, DeepgramError> {
    let mut request = spec
        .url()
        .into_client_request()
        .map_err(|e| DeepgramError::transport(e, Some(spec.credential())))?;
    let header = HeaderValue::from_str(&spec.authorization_header_value())
        .map_err(|e| DeepgramError::transport(e, Some(spec.credential())))?;
    request.headers_mut().insert(AUTHORIZATION, header);

    // The same cap the parser enforces, applied one layer lower so an oversized frame is
    // refused before it is buffered rather than after.
    let ws_config = WebSocketConfig {
        max_message_size: Some(MAX_FRAME_BYTES),
        max_frame_size: Some(MAX_FRAME_BYTES),
        ..Default::default()
    };

    match tokio_tungstenite::connect_async_with_config(request, Some(ws_config), false).await {
        Ok((socket, _response)) => Ok(socket),
        Err(WsError::Http(response)) if is_credential_rejection(response.status().as_u16()) => {
            Err(DeepgramError::CredentialRejected {
                status: response.status().as_u16(),
            })
        }
        Err(e) => Err(DeepgramError::transport(e, Some(spec.credential()))),
    }
}

/// Which upgrade statuses mean "your credential is the problem" rather than "the network is".
fn is_credential_rejection(status: u16) -> bool {
    matches!(status, 401 | 403)
}

/// Forward audio, read transcripts, until the socket ends or a stop is requested.
async fn pump(
    mut socket: Socket,
    config: &SessionConfig,
    audio: &AudioRing,
    queue: &SegmentQueue,
    spec: &RequestSpec,
    stop: &AtomicBool,
) -> Result<(), DeepgramError> {
    let mut ticker = tokio::time::interval(config.audio_poll_interval);
    let mut last_sent = Instant::now();
    // Stall detection: when did the peer last say anything, and have we given it something to
    // answer since? Both are needed — see `SessionConfig::stall_timeout`.
    let mut last_heard = Instant::now();
    let mut audio_sent_since_heard = false;
    loop {
        tokio::select! {
            _ = ticker.tick() => {
                if stop.load(Ordering::SeqCst) {
                    // Ask Deepgram to flush before closing, so trailing words survive.
                    let _ = socket.send(Message::Text(CLOSE_STREAM.to_string())).await;
                    let _ = socket.close(None).await;
                    return Ok(());
                }
                let chunks = audio.drain();
                if chunks.is_empty() {
                    if last_sent.elapsed() >= config.keep_alive_after {
                        socket
                            .send(Message::Text(KEEP_ALIVE.to_string()))
                            .await
                            .map_err(|e| DeepgramError::transport(e, Some(spec.credential())))?;
                        last_sent = Instant::now();
                    }
                } else {
                    for chunk in chunks {
                        socket
                            .send(Message::Binary(chunk.as_bytes().to_vec()))
                            .await
                            .map_err(|e| DeepgramError::transport(e, Some(spec.credential())))?;
                    }
                    last_sent = Instant::now();
                    audio_sent_since_heard = true;
                }
                if audio_sent_since_heard && last_heard.elapsed() >= config.stall_timeout {
                    return Err(DeepgramError::transport(
                        format!(
                            "Deepgram accepted audio but sent nothing back for {:?}",
                            config.stall_timeout
                        ),
                        Some(spec.credential()),
                    ));
                }
            }
            incoming = socket.next() => {
                // Any frame at all is a sign of life, including a ping or a metadata message.
                last_heard = Instant::now();
                audio_sent_since_heard = false;
                match incoming {
                    Some(Ok(Message::Text(text))) => ingest(&text, queue),
                    Some(Ok(Message::Close(_))) | None => {
                        return Err(DeepgramError::transport(
                            "the Deepgram socket closed",
                            Some(spec.credential()),
                        ));
                    }
                    Some(Ok(_)) => {}
                    Some(Err(e)) => {
                        return Err(DeepgramError::transport(e, Some(spec.credential())));
                    }
                }
            }
        }
    }
}

/// Turn one text frame into a queued segment, if it is one.
///
/// A frame this client cannot read is dropped. That is deliberate: an unknown message type or
/// a malformed frame must not end a service's transcription, and the parser has already
/// refused anything oversized.
fn ingest(text: &str, queue: &SegmentQueue) {
    if let Ok(DeepgramFrame::Results(results)) = parse_frame(text) {
        // The queue itself refuses blank transcripts; pushing unconditionally keeps that
        // policy in one place rather than duplicating it here.
        queue.push(results.to_segment());
    }
}

/// Wait, but notice a stop request promptly rather than sleeping through eight seconds of it.
async fn sleep_interruptible(total: Duration, stop: &AtomicBool) {
    const SLICE: Duration = Duration::from_millis(50);
    let deadline = Instant::now() + total;
    while Instant::now() < deadline {
        if stop.load(Ordering::SeqCst) {
            return;
        }
        tokio::time::sleep(SLICE.min(deadline.saturating_duration_since(Instant::now()))).await;
    }
}

// Tests live in `tests/test_transport.rs` (feature-gated, against a local stub socket).
