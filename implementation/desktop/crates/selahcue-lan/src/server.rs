//! The operator's TLS-pinned WebSocket control server (ADR-0009).
//!
//! Each accepted connection is served on its own task: TLS handshake → WebSocket
//! handshake → an [`AuthRequest`] authenticated against the shared
//! [`SessionRegistry`] → a request loop that enforces RBAC ([`authorize`]) on every
//! command before invoking the application [`Handler`]. Per-connection state is
//! dropped when the task ends, so the server holds no growing per-connection state
//! (see `active_connection_count`).

use crate::protocol::{
    self, AuthResponse, Command, DenyReason, Hello, PairRequest, PairResponse, Request,
    ServerMessage,
};
use crate::rbac::{authorize, Role};
use crate::session::{DeviceId, SessionRegistry, SessionToken};
use crate::tls::{server_config, SelfSigned, TransportError};
use crate::wire::{recv_json, send_json};
use futures_util::future::BoxFuture;
use futures_util::StreamExt;
use ring::rand::{SecureRandom, SystemRandom};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::io::{AsyncRead, AsyncWrite};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{Mutex, Semaphore};
use tokio_rustls::server::TlsStream;
use tokio_rustls::TlsAcceptor;
use tokio_tungstenite::tungstenite::protocol::WebSocketConfig;
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::WebSocketStream;

/// Time budget for the pre-auth phase (TLS + WebSocket handshake + first auth
/// frame). Stalled/half-open peers are dropped after this so they cannot pin down
/// tasks, sockets, and memory (slowloris defence).
const DEFAULT_HANDSHAKE_TIMEOUT: Duration = Duration::from_secs(10);

/// Maximum concurrent connections served at once — bounds file descriptors, tasks,
/// and per-connection memory regardless of how many peers connect.
const DEFAULT_MAX_CONNECTIONS: usize = 128;

/// Cap on a single control message. Control frames are tiny (a JSON command); this
/// stops a peer from forcing large pre-auth buffering.
const MAX_MESSAGE_BYTES: usize = 64 * 1024;

/// How long the operator has to confirm/decline a pairing request. Applied *after*
/// the network handshake completed (the pairing peer has already sent its full
/// frame), so waiting on the human does not extend the slowloris window.
const PAIRING_APPROVAL_TIMEOUT: Duration = Duration::from_secs(30);

/// Cap on the displayed device name (untrusted text shown to the operator).
const MAX_DEVICE_NAME: usize = 48;

/// Host-confirmation seam (FR-086): given the requesting device's (sanitized) display
/// name, resolve to whether the operator approves. Implementations typically prompt
/// the operator; tests inject closures. Approval is awaited with
/// [`PAIRING_APPROVAL_TIMEOUT`]; a timeout counts as declined.
pub type PairingApproval = Arc<dyn Fn(String) -> BoxFuture<'static, bool> + Send + Sync>;

/// The operator's response to an authorized command.
pub enum Reply {
    /// Accept and perform — the server returns `Ack{request_id}`.
    Ack,
    /// Refuse at the application level (e.g. an unknown item) — the server returns
    /// `Denied{request_id, reason}`. (RBAC denials are handled before the handler.)
    Deny(DenyReason),
    /// Return this specific message (e.g. `State`, `ScriptureResults`).
    Message(ServerMessage),
}

/// Application command handler: given the authenticated [`Role`] and an already
/// **authorized** [`Command`], produce a [`Reply`]. Must be cheap and non-blocking
/// (offload real work elsewhere) so it does not stall the connection task.
pub type Handler = Arc<dyn Fn(Role, &Command) -> Reply + Send + Sync>;

/// A TLS-pinned WebSocket control server bound to a [`SessionRegistry`].
pub struct ControlServer {
    acceptor: TlsAcceptor,
    registry: Arc<Mutex<SessionRegistry>>,
    handler: Handler,
    active_connections: Arc<AtomicUsize>,
    handshake_timeout: Duration,
    limiter: Arc<Semaphore>,
    /// Host-confirmation for over-the-wire pairing. `None` (the secure default)
    /// rejects every `Pair` hello — a server must opt in to wire pairing.
    pairing: Option<PairingApproval>,
}

/// Increments the live-connection counter on creation and decrements it on drop —
/// so the count is correct even if a connection task ends via error or panic.
struct ConnGuard(Arc<AtomicUsize>);

impl ConnGuard {
    fn new(counter: Arc<AtomicUsize>) -> Self {
        counter.fetch_add(1, Ordering::SeqCst);
        Self(counter)
    }
}

impl Drop for ConnGuard {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::SeqCst);
    }
}

impl ControlServer {
    /// Build a server from the operator's self-signed identity, a shared session
    /// registry, and an application command handler.
    pub fn new(
        identity: &SelfSigned,
        registry: Arc<Mutex<SessionRegistry>>,
        handler: Handler,
    ) -> Result<Self, TransportError> {
        let config = server_config(identity)?;
        Ok(Self {
            acceptor: TlsAcceptor::from(Arc::new(config)),
            registry,
            handler,
            active_connections: Arc::new(AtomicUsize::new(0)),
            handshake_timeout: DEFAULT_HANDSHAKE_TIMEOUT,
            limiter: Arc::new(Semaphore::new(DEFAULT_MAX_CONNECTIONS)),
            pairing: None,
        })
    }

    /// Enable over-the-wire pairing, gated by this host-confirmation callback
    /// (FR-086). Without this, `Pair` hellos are rejected.
    pub fn with_pairing_approval(mut self, approval: PairingApproval) -> Self {
        self.pairing = Some(approval);
        self
    }

    /// Override the pre-auth handshake timeout (default 10s). Mainly for tests.
    pub fn with_handshake_timeout(mut self, timeout: Duration) -> Self {
        self.handshake_timeout = timeout;
        self
    }

    /// Override the concurrent-connection cap (default 128).
    pub fn with_max_connections(mut self, max: usize) -> Self {
        self.limiter = Arc::new(Semaphore::new(max.max(1)));
        self
    }

    /// Connections currently being served. Returns to 0 after clients disconnect
    /// (or after the handshake timeout reaps a stalled peer) — a guard against
    /// connection-handler/state leaks.
    pub fn active_connection_count(&self) -> usize {
        self.active_connections.load(Ordering::SeqCst)
    }

    /// Accept connections, serving each on its own task, until this future is
    /// dropped or the limiter is closed.
    ///
    /// A per-accept error (e.g. file-descriptor exhaustion) is logged-and-skipped
    /// with a short backoff, never fatal — so a transient resource spike can't
    /// permanently stop the operator from accepting controllers. Concurrency is
    /// bounded by a semaphore, giving natural backpressure at the cap.
    pub async fn run(self: Arc<Self>, listener: TcpListener) -> Result<(), TransportError> {
        loop {
            // Acquire a slot before accepting — at the cap this awaits until a
            // connection frees, bounding fds/tasks/memory.
            let permit = match Arc::clone(&self.limiter).acquire_owned().await {
                Ok(permit) => permit,
                Err(_) => return Ok(()), // limiter closed → graceful shutdown
            };
            match listener.accept().await {
                Ok((tcp, _peer)) => {
                    let server = Arc::clone(&self);
                    tokio::spawn(async move {
                        // The permit is released (and the slot reclaimed) when this
                        // task ends, however it ends.
                        let _permit = permit;
                        let _ = server.serve_connection(tcp).await;
                    });
                }
                Err(_e) => {
                    // Do not let a transient accept error kill the loop; back off
                    // briefly so we don't busy-spin while descriptors are exhausted.
                    drop(permit);
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
        }
    }

    /// Serve one connection to completion. The pre-auth network phase (TLS + WS
    /// handshake + the first `Hello` frame) is time-boxed so a stalled/half-open peer
    /// is dropped promptly (slowloris defence). A pairing hello then gets its own
    /// bounded **approval** window — by that point the peer has already sent its full
    /// frame, so the human decision does not extend the network-attack surface.
    pub async fn serve_connection(&self, tcp: TcpStream) -> Result<(), TransportError> {
        let _guard = ConnGuard::new(Arc::clone(&self.active_connections));
        let (mut ws, hello) = tokio::time::timeout(self.handshake_timeout, self.handshake(tcp))
            .await
            .map_err(|_| TransportError::Protocol("handshake/auth timed out".into()))??;
        let role = match hello {
            Hello::Auth(auth) => self.authenticate(&mut ws, auth).await?,
            Hello::Pair(pair) => self.complete_pairing(&mut ws, pair).await?,
        };
        self.request_loop(&mut ws, role).await
    }

    /// The pre-auth network phase: TLS handshake, WebSocket handshake (with a bounded
    /// message size), and receipt of the first `Hello` frame.
    async fn handshake(
        &self,
        tcp: TcpStream,
    ) -> Result<(WebSocketStream<TlsStream<TcpStream>>, Hello), TransportError> {
        let tls = self.acceptor.accept(tcp).await?;
        let ws_config = WebSocketConfig {
            max_message_size: Some(MAX_MESSAGE_BYTES),
            max_frame_size: Some(MAX_MESSAGE_BYTES),
            ..Default::default()
        };
        let mut ws = tokio_tungstenite::accept_async_with_config(tls, Some(ws_config)).await?;
        let hello: Hello = recv_json(&mut ws).await?;
        Ok((ws, hello))
    }

    async fn authenticate<S>(
        &self,
        ws: &mut WebSocketStream<S>,
        auth: protocol::AuthRequest,
    ) -> Result<Role, TransportError>
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        if !auth.version_supported() {
            send_json(
                ws,
                &AuthResponse::Rejected {
                    reason: DenyReason::BadRequest,
                },
            )
            .await?;
            return Err(TransportError::Protocol(
                "unsupported protocol version".into(),
            ));
        }
        let role = {
            let reg = self.registry.lock().await;
            reg.authenticate(&DeviceId(auth.device_id.clone()), &auth.token)
        };
        match role {
            Some(role) => {
                send_json(ws, &AuthResponse::Granted { role }).await?;
                Ok(role)
            }
            None => {
                send_json(
                    ws,
                    &AuthResponse::Rejected {
                        reason: DenyReason::Unauthenticated,
                    },
                )
                .await?;
                Err(TransportError::Protocol("authentication rejected".into()))
            }
        }
    }

    /// Redeem a pairing code over the wire: version + code validity (non-consuming)
    /// → **host confirmation** → single-use redemption with server-generated
    /// credentials → `Granted`, continuing the connection already authenticated.
    async fn complete_pairing<S>(
        &self,
        ws: &mut WebSocketStream<S>,
        pair: PairRequest,
    ) -> Result<Role, TransportError>
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        async fn reject<S>(
            ws: &mut WebSocketStream<S>,
            reason: DenyReason,
            why: &str,
        ) -> Result<Role, TransportError>
        where
            S: AsyncRead + AsyncWrite + Unpin,
        {
            send_json(ws, &PairResponse::Rejected { reason }).await?;
            Err(TransportError::Protocol(format!("pairing rejected: {why}")))
        }

        if !pair.version_supported() {
            return reject(ws, DenyReason::BadRequest, "unsupported protocol version").await;
        }
        let Some(approval) = self.pairing.as_ref() else {
            return reject(ws, DenyReason::Forbidden, "pairing not enabled").await;
        };
        // Cheap pre-check (non-consuming) so an invalid/expired code never bothers
        // the operator with a confirmation prompt. Pruning here also keeps the
        // pending-offer map from accumulating expired entries (bounded memory).
        if !{
            let mut reg = self.registry.lock().await;
            let now = std::time::Instant::now();
            reg.prune_expired(now);
            reg.code_valid(&pair.code, now)
        } {
            return reject(ws, DenyReason::Unauthenticated, "unknown or expired code").await;
        }

        // Host confirmation (FR-086). The device name is untrusted display text —
        // sanitize before showing. A timeout counts as declined.
        let name = sanitize_device_name(&pair.device_name);
        let approved = tokio::time::timeout(PAIRING_APPROVAL_TIMEOUT, approval(name))
            .await
            .unwrap_or(false);
        if !approved {
            return reject(ws, DenyReason::Forbidden, "host declined").await;
        }

        // Redeem (single-use; re-checks expiry, closing the confirm-window race) with
        // server-generated credentials.
        let device_id = format!("dev-{}", random_hex(8));
        let token = random_hex(32);
        let redeemed = {
            let mut reg = self.registry.lock().await;
            reg.redeem(
                &pair.code,
                DeviceId(device_id.clone()),
                SessionToken::new(token.clone()),
                std::time::Instant::now(),
            )
        };
        match redeemed {
            Ok(role) => {
                send_json(
                    ws,
                    &PairResponse::Granted {
                        device_id,
                        token,
                        role,
                    },
                )
                .await?;
                Ok(role)
            }
            Err(_) => reject(ws, DenyReason::Unauthenticated, "code expired").await,
        }
    }

    async fn request_loop<S>(
        &self,
        ws: &mut WebSocketStream<S>,
        role: Role,
    ) -> Result<(), TransportError>
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        while let Some(frame) = ws.next().await {
            match frame? {
                Message::Text(text) => {
                    let req: Request = match protocol::from_json(text.as_str()) {
                        Ok(req) => req,
                        Err(_) => {
                            send_json(
                                ws,
                                &ServerMessage::Error {
                                    message: "malformed request".into(),
                                },
                            )
                            .await?;
                            continue;
                        }
                    };
                    if !req.version_supported() {
                        send_json(
                            ws,
                            &ServerMessage::Error {
                                message: "unsupported protocol version".into(),
                            },
                        )
                        .await?;
                        continue;
                    }
                    let reply = if authorize(role, &req.command) {
                        match (self.handler)(role, &req.command) {
                            Reply::Ack => ServerMessage::Ack {
                                request_id: req.request_id,
                            },
                            Reply::Deny(reason) => ServerMessage::Denied {
                                request_id: req.request_id,
                                reason,
                            },
                            Reply::Message(msg) => msg,
                        }
                    } else {
                        ServerMessage::Denied {
                            request_id: req.request_id,
                            reason: DenyReason::Forbidden,
                        }
                    };
                    send_json(ws, &reply).await?;
                }
                Message::Close(_) => break,
                _ => {}
            }
        }
        Ok(())
    }
}

/// `n` random bytes from the OS CSPRNG as lowercase hex (2n chars). Falls back to a
/// second draw attempt; a CSPRNG that cannot produce bytes is unrecoverable, so the
/// caller-facing contract stays simple (this is used for token/device-id issuance).
fn random_hex(n: usize) -> String {
    let rng = SystemRandom::new();
    let mut bytes = vec![0u8; n];
    if rng.fill(&mut bytes).is_err() {
        // One retry; if the OS RNG is truly broken, fail closed with an empty string,
        // which the registry rejects (empty tokens never authenticate).
        if rng.fill(&mut bytes).is_err() {
            return String::new();
        }
    }
    let mut s = String::with_capacity(n * 2);
    for b in bytes {
        use std::fmt::Write;
        let _ = write!(s, "{b:02x}");
    }
    s
}

/// A fresh 256-bit random bearer token (lowercase hex) — for issuing credentials
/// outside the wire-pairing path (e.g. a host-local session). Empty on CSPRNG
/// failure, which the registry rejects (fail closed).
pub fn generate_token() -> String {
    random_hex(32)
}

/// A short random pairing code (uppercase alphanumeric, unambiguous alphabet) the
/// operator offers via QR. 8 chars over a 32-symbol alphabet ≈ 40 bits — plenty for a
/// single-use code with a 2-minute TTL and host confirmation behind it.
pub fn generate_pairing_code() -> String {
    // No 0/O/1/I — the code may be typed by hand as a QR fallback.
    const ALPHABET: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    let rng = SystemRandom::new();
    let mut bytes = [0u8; 8];
    if rng.fill(&mut bytes).is_err() {
        return String::new(); // registry refuses empty codes (fail closed)
    }
    bytes
        .iter()
        .map(|b| ALPHABET[(*b as usize) % ALPHABET.len()] as char)
        .collect()
}

/// Sanitize an untrusted device name for operator display: keep printable
/// non-control characters, cap the length, and never yield an empty string.
fn sanitize_device_name(raw: &str) -> String {
    let cleaned: String = raw
        .chars()
        .filter(|c| !c.is_control())
        .take(MAX_DEVICE_NAME)
        .collect();
    let trimmed = cleaned.trim();
    if trimmed.is_empty() {
        "(unnamed device)".to_string()
    } else {
        trimmed.to_string()
    }
}
