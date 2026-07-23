//! The operator's TLS-pinned WebSocket control server (ADR-0009).
//!
//! Each accepted connection is served on its own task: TLS handshake → WebSocket
//! handshake → an [`AuthRequest`] authenticated against the shared
//! [`SessionRegistry`] → a request loop that enforces RBAC ([`authorize`]) on every
//! command before invoking the application [`Handler`]. Per-connection state is
//! dropped when the task ends, so the server holds no growing per-connection state
//! (see `active_connection_count`).

use crate::protocol::{self, AuthRequest, AuthResponse, Command, DenyReason, Request, ServerMessage};
use crate::rbac::{authorize, Role};
use crate::session::{DeviceId, SessionRegistry};
use crate::tls::{server_config, SelfSigned, TransportError};
use crate::wire::{recv_json, send_json};
use futures_util::StreamExt;
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
        })
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

    /// Serve one connection to completion. The pre-auth phase (TLS + WS handshake +
    /// first auth frame) is time-boxed so a stalled/half-open peer is dropped
    /// promptly (releasing its task, socket, and connection slot) instead of
    /// parking forever.
    pub async fn serve_connection(&self, tcp: TcpStream) -> Result<(), TransportError> {
        let _guard = ConnGuard::new(Arc::clone(&self.active_connections));
        let (mut ws, role) = tokio::time::timeout(self.handshake_timeout, self.handshake(tcp))
            .await
            .map_err(|_| TransportError::Protocol("handshake/auth timed out".into()))??;
        self.request_loop(&mut ws, role).await
    }

    /// The pre-auth phase: TLS handshake, WebSocket handshake (with a bounded
    /// message size), and authentication.
    async fn handshake(
        &self,
        tcp: TcpStream,
    ) -> Result<(WebSocketStream<TlsStream<TcpStream>>, Role), TransportError> {
        let tls = self.acceptor.accept(tcp).await?;
        let ws_config = WebSocketConfig {
            max_message_size: Some(MAX_MESSAGE_BYTES),
            max_frame_size: Some(MAX_MESSAGE_BYTES),
            ..Default::default()
        };
        let mut ws = tokio_tungstenite::accept_async_with_config(tls, Some(ws_config)).await?;
        let role = self.authenticate(&mut ws).await?;
        Ok((ws, role))
    }

    async fn authenticate<S>(&self, ws: &mut WebSocketStream<S>) -> Result<Role, TransportError>
    where
        S: AsyncRead + AsyncWrite + Unpin,
    {
        let auth: AuthRequest = recv_json(ws).await?;
        if !auth.version_supported() {
            send_json(ws, &AuthResponse::Rejected { reason: DenyReason::BadRequest }).await?;
            return Err(TransportError::Protocol("unsupported protocol version".into()));
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
                send_json(ws, &AuthResponse::Rejected { reason: DenyReason::Unauthenticated })
                    .await?;
                Err(TransportError::Protocol("authentication rejected".into()))
            }
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
                            send_json(ws, &ServerMessage::Error { message: "malformed request".into() })
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
                            Reply::Ack => ServerMessage::Ack { request_id: req.request_id },
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
