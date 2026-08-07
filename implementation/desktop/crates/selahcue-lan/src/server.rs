//! The operator's TLS-pinned WebSocket control server (ADR-0009).
//!
//! Each accepted connection is served on its own task: TLS handshake → WebSocket
//! handshake → an [`AuthRequest`] authenticated against the shared
//! [`SessionRegistry`] → a request loop that enforces RBAC ([`authorize`]) on every
//! command before invoking the application [`Handler`]. Per-connection state is
//! dropped when the task ends, so the server holds no growing per-connection state
//! (see `active_connection_count`).

use crate::protocol::{
    self, AuthResponse, Command, DenyReason, Hello, PairRequest, PairResponse, RemoteDeviceView,
    RemotePendingView, Request, ServerMessage,
};
use crate::rbac::{authorize, Role};
use crate::session::{
    ApproveError, DeviceId, RequestError, SessionRegistry, SessionToken, SESSION_IDLE_TTL,
};
use crate::tls::{server_config, SelfSigned, TransportError};
use crate::wire::{recv_json, send_json};
use futures_util::{SinkExt, StreamExt};
use ring::rand::{SecureRandom, SystemRandom};
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::io::{AsyncRead, AsyncWrite};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{oneshot, Mutex, Semaphore};
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

/// How long a device's `Pair` connection parks awaiting the operator's approve/deny
/// decision. Applied *after* the network handshake completed (the pairing peer has
/// already sent its full frame), so waiting on the human does not extend the slowloris
/// window. The client's pair timeout MUST exceed this so the device never hangs up first.
const PAIRING_PARK_TIMEOUT: Duration = Duration::from_secs(120);

/// Cadence of keepalive pings sent to a parked pairing connection, so NAT/idle timeouts
/// do not silently drop the socket across the (up-to-[`PAIRING_PARK_TIMEOUT`]) human wait.
const PAIRING_PARK_PING_INTERVAL: Duration = Duration::from_secs(25);

/// Registry-side backstop TTL for pending requests, swept on each new pairing/auth. Set
/// above [`PAIRING_PARK_TIMEOUT`] so it only reclaims requests orphaned by a task that was
/// cancelled/aborted without running its inline cleanup (no-leak guarantee).
const PAIRING_STALE_REQUEST_TTL: Duration = Duration::from_secs(180);

/// Cap on the displayed device name (untrusted text shown to the operator).
const MAX_DEVICE_NAME: usize = 48;

/// Cap on the displayed device platform / OS string (untrusted text).
const MAX_PLATFORM: usize = 32;

/// The pairing model this server runs.
enum PairingMode {
    /// Reject every `Pair` hello — the secure default; a server must opt in to pairing.
    Disabled,
    /// Operator-paced (86ajxer8n): a `Pair` hello parks as a pending request until the operator
    /// approves it (with a role) or denies it over the Remote Control channel. The token is minted
    /// operator-side at approval and pushed back to the still-parked device socket.
    OperatorPaced,
}

/// The operator's decision, delivered from the (separate) operator connection to a parked
/// pairing connection over its private one-shot rendezvous. `Debug` redacts the token.
enum Approval {
    Granted { token: String, role: Role },
    Denied,
}

impl std::fmt::Debug for Approval {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Approval::Granted { role, .. } => f
                .debug_struct("Approval::Granted")
                .field("token", &"<redacted>")
                .field("role", role)
                .finish(),
            Approval::Denied => f.write_str("Approval::Denied"),
        }
    }
}

/// The per-device rendezvous channels for parked pairing connections, keyed by the
/// server-minted `device_id`. A [`oneshot::Sender`] is inserted while a device parks and
/// removed on every exit path; bounded by `MAX_PENDING_REQUESTS` (a waiter is only inserted
/// after `submit_request` succeeds), so it cannot grow without limit.
type Waiters = Arc<std::sync::Mutex<HashMap<DeviceId, oneshot::Sender<Approval>>>>;

/// The operator's response to an authorized command.
pub enum Reply {
    /// Accept and perform — the server returns `Ack{request_id}`.
    Ack,
    /// Refuse at the application level (e.g. an unknown item) — the server returns
    /// `Denied{request_id, reason}`. (RBAC denials are handled before the handler.)
    Deny(DenyReason),
    /// Return this specific message (e.g. `State`, `ScriptureResults`).
    /// Boxed: `ServerMessage` carries the full operator view (plan + outputs),
    /// far larger than the other variants.
    Message(Box<ServerMessage>),
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
    park_timeout: Duration,
    limiter: Arc<Semaphore>,
    /// The over-the-wire pairing model. [`PairingMode::Disabled`] (the secure default)
    /// rejects every `Pair` hello — a server must opt in with [`ControlServer::with_pairing_requests`].
    pairing: PairingMode,
    /// Rendezvous senders for parked pairing connections (see [`Waiters`]).
    waiters: Waiters,
}

/// Increments the live-connection counter on creation and decrements it on drop —
/// so the count is correct even if a connection task ends via error or panic.
struct ConnGuard(Arc<AtomicUsize>);

/// Removes a parked device's rendezvous sender on drop — a synchronous, panic/cancel-safe
/// backstop so a waiter never outlives its parked connection even if the task is aborted
/// without running its inline cleanup.
struct WaiterGuard {
    waiters: Waiters,
    device_id: DeviceId,
}

impl Drop for WaiterGuard {
    fn drop(&mut self) {
        if let Ok(mut w) = self.waiters.lock() {
            w.remove(&self.device_id);
        }
    }
}

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
            park_timeout: PAIRING_PARK_TIMEOUT,
            limiter: Arc::new(Semaphore::new(DEFAULT_MAX_CONNECTIONS)),
            pairing: PairingMode::Disabled,
            waiters: Arc::new(std::sync::Mutex::new(HashMap::new())),
        })
    }

    /// Enable operator-paced over-the-wire pairing (86ajxer8n): a `Pair` hello parks as a
    /// pending request until the operator approves it with a role (or denies it) over the
    /// Remote Control channel. Without this, `Pair` hellos are rejected (the secure default).
    pub fn with_pairing_requests(mut self) -> Self {
        self.pairing = PairingMode::OperatorPaced;
        self
    }

    /// Override the pre-auth handshake timeout (default 10s). Mainly for tests.
    pub fn with_handshake_timeout(mut self, timeout: Duration) -> Self {
        self.handshake_timeout = timeout;
        self
    }

    /// Override the operator-approval park window (default 120s). Mainly for tests.
    pub fn with_park_timeout(mut self, timeout: Duration) -> Self {
        self.park_timeout = timeout;
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
        let device_id = DeviceId(auth.device_id.clone());
        let role = {
            let mut reg = self.registry.lock().await;
            let r = reg.authenticate(&device_id, &auth.token);
            if r.is_some() {
                // The device just proved it is active — refresh its idle-TTL so housekeeping
                // does not reclaim it while it is connecting/reconnecting (audit #8).
                reg.touch(&device_id, std::time::Instant::now());
            }
            r
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

    /// Operator-paced pairing (86ajxer8n): validate + consume the single-use code, park the
    /// connection as a pending request (device-supplied name/platform), then await the operator's
    /// approve/deny decision delivered over a per-device one-shot rendezvous. On approval the
    /// operator-minted token is pushed to this still-open socket as `Granted` and the connection
    /// continues already authenticated; on deny/timeout/disconnect it is rejected and the pending
    /// request is dropped. Bounded by the pending-request cap + a park timeout (no-leak).
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
        match self.pairing {
            PairingMode::Disabled => {
                return reject(ws, DenyReason::Forbidden, "pairing not enabled").await;
            }
            PairingMode::OperatorPaced => {}
        }

        // Register the pending request + its rendezvous under ONE registry-lock critical section:
        // the waiter is inserted BEFORE the request is observable in `pending_requests`, and the
        // operator can only learn the `device_id` from that snapshot — so an approval can never
        // race ahead of the park (this structurally closes the lost-wakeup window).
        let now = std::time::Instant::now();
        let (device_id, mut rx) = {
            let mut reg = self.registry.lock().await;
            reg.prune_expired(now);
            reg.prune_idle(now, SESSION_IDLE_TTL);
            // Backstop: reclaim any pending request orphaned by a cancelled/aborted parked task.
            reg.prune_stale_requests(now, PAIRING_STALE_REQUEST_TTL);
            if !reg.code_valid(&pair.code, now) {
                drop(reg);
                return reject(ws, DenyReason::Unauthenticated, "unknown or expired code").await;
            }
            // Consume the code single-use NOW, detaching the park from the code's short TTL.
            reg.withdraw(&pair.code);
            // Mint a fresh, collision-free server-side device id (checked against active
            // sessions, pending requests, AND currently-parked waiters, all under this lock).
            let device_id = {
                let waiters = self.waiters.lock().expect("waiters mutex poisoned");
                let mut candidate = DeviceId(format!("dev-{}", random_hex(8)));
                while reg.is_known_device(&candidate) || waiters.contains_key(&candidate) {
                    candidate = DeviceId(format!("dev-{}", random_hex(8)));
                }
                candidate
            };
            let name = sanitize_device_name(&pair.device_name);
            let platform = sanitize_platform(&pair.platform);
            // NOTE: the fingerprint is the code-derived placeholder (see `pairing_fingerprint`);
            // real TLS-cert SHA-256 pinning is deferred to the Part B cert-pinning follow-on.
            let fingerprint = pairing_fingerprint(&pair.code);
            match reg.submit_request(device_id.clone(), name, platform, fingerprint, now) {
                Ok(()) => {}
                Err(RequestError::TooManyRequests) => {
                    drop(reg);
                    return reject(ws, DenyReason::Unauthenticated, "too many pending requests")
                        .await;
                }
            }
            let (tx, rx) = oneshot::channel::<Approval>();
            self.waiters
                .lock()
                .expect("waiters mutex poisoned")
                .insert(device_id.clone(), tx);
            (device_id, rx)
        };
        // Removes the waiter on EVERY exit — approve, deny, timeout, disconnect, or task abort.
        let _waiter_guard = WaiterGuard {
            waiters: Arc::clone(&self.waiters),
            device_id: device_id.clone(),
        };

        // Park: await the operator's decision, sending periodic keepalive pings so an idle
        // NAT/firewall does not silently drop the socket across the (up-to-120s) human wait.
        // We do not read here — the client sends nothing while parked, `recv_json` skips our
        // pings, and any buffered pong is ignored by the request loop once we proceed.
        enum ParkExit {
            Decision(Approval),
            Timeout,
            Gone,
        }
        let exit = {
            let deadline = tokio::time::sleep(self.park_timeout);
            tokio::pin!(deadline);
            // Ping often enough to notice a dead socket well within the park window (and to keep
            // NAT state warm), but never faster than the base cadence for a long human wait.
            let ping_interval = std::cmp::min(PAIRING_PARK_PING_INTERVAL, self.park_timeout / 4)
                .max(Duration::from_millis(50));
            let mut ping = tokio::time::interval(ping_interval);
            ping.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
            ping.tick().await; // consume the immediate first tick — first real ping is one interval in
            loop {
                tokio::select! {
                    biased;
                    res = &mut rx => break match res {
                        Ok(approval) => ParkExit::Decision(approval),
                        Err(_) => ParkExit::Gone, // sender dropped without a decision
                    },
                    _ = &mut deadline => break ParkExit::Timeout,
                    _ = ping.tick() => {
                        if ws.send(Message::Ping(Default::default())).await.is_err() {
                            break ParkExit::Gone; // socket is dead
                        }
                    }
                }
            }
        };

        match exit {
            // Approved: the session already exists (minted by `approve_request` on the operator
            // connection); push the token to this still-parked socket and continue authenticated.
            ParkExit::Decision(Approval::Granted { token, role }) => {
                send_json(
                    ws,
                    &PairResponse::Granted {
                        device_id: device_id.0,
                        token,
                        role,
                    },
                )
                .await?;
                Ok(role)
            }
            ParkExit::Decision(Approval::Denied) => {
                reject(ws, DenyReason::Forbidden, "operator denied the request").await
            }
            // Timed out or the socket went away. Close the zombie-session race UNDER the registry
            // lock: an approval may have landed in the very instant we stopped waiting (the
            // operator's `send` succeeded before our `WaiterGuard` dropped) — honor it; otherwise
            // drop the pending request so nothing lingers.
            ParkExit::Timeout | ParkExit::Gone => {
                let mut reg = self.registry.lock().await;
                match rx.try_recv() {
                    Ok(Approval::Granted { token, role }) => {
                        drop(reg);
                        send_json(
                            ws,
                            &PairResponse::Granted {
                                device_id: device_id.0,
                                token,
                                role,
                            },
                        )
                        .await?;
                        Ok(role)
                    }
                    _ => {
                        reg.deny_request(&device_id);
                        drop(reg);
                        reject(ws, DenyReason::Forbidden, "pairing not approved in time").await
                    }
                }
            }
        }
    }

    /// Handle a Remote Control device-management command against the [`SessionRegistry`] (the
    /// operator's device authority, 86ajxer8n). Returns `Some(reply)` for a device command — the
    /// caller has already `authorize`d it as `ManageDevices` — or `None` for any other command,
    /// which then falls through to the application handler. Every mutator replies with the fresh
    /// snapshot so the operator UI re-renders from a single source of truth.
    async fn handle_remote_command(&self, cmd: &Command) -> Option<ServerMessage> {
        let now = std::time::Instant::now();
        let mut reg = self.registry.lock().await;
        match cmd {
            Command::ListRemoteDevices => Some(remote_snapshot(&reg, now)),
            Command::RevokeSession { device_id } => {
                reg.revoke(&DeviceId(device_id.clone()));
                Some(remote_snapshot(&reg, now))
            }
            Command::SetSessionRole { device_id, role } => {
                reg.set_role(&DeviceId(device_id.clone()), *role);
                Some(remote_snapshot(&reg, now))
            }
            Command::DenyPairing { device_id } => {
                let did = DeviceId(device_id.clone());
                reg.deny_request(&did);
                // Wake a parked device with the denial (best-effort; it may already be gone).
                if let Some(tx) = self
                    .waiters
                    .lock()
                    .expect("waiters mutex poisoned")
                    .remove(&did)
                {
                    let _ = tx.send(Approval::Denied);
                }
                Some(remote_snapshot(&reg, now))
            }
            Command::ApprovePairing { device_id, role } => {
                let did = DeviceId(device_id.clone());
                // Fail-closed: a remotely-paired device may NEVER be granted Operator
                // (device-management) authority — the console stays the sole Operator. The request
                // is left pending so the operator can re-approve it with a valid role.
                if *role == Role::Operator {
                    return Some(remote_snapshot(&reg, now));
                }
                let token = random_hex(32);
                match reg.approve_request(&did, *role, SessionToken::new(token.clone()), now) {
                    Ok(granted_role) => {
                        // Wake the parked device with the SAME token, if it is still parked.
                        // No waiter (None) = an operator-management flow with no parked connection
                        // (e.g. a directly-seeded request): keep the session as-is. A present
                        // waiter whose receiver is gone (send Err) = the device left/timed out:
                        // compensate the just-minted zombie session.
                        let sender = self
                            .waiters
                            .lock()
                            .expect("waiters mutex poisoned")
                            .remove(&did);
                        if let Some(tx) = sender {
                            if tx
                                .send(Approval::Granted {
                                    token,
                                    role: granted_role,
                                })
                                .is_err()
                            {
                                reg.revoke(&did);
                            }
                        }
                    }
                    // NoSuchRequest (denied / timed out / never existed) or TooManySessions
                    // (retryable) — leave any waiter untouched and create no session.
                    Err(ApproveError::NoSuchRequest) | Err(ApproveError::TooManySessions) => {}
                }
                Some(remote_snapshot(&reg, now))
            }
            Command::NewPairingCode => {
                let code = random_hex(4); // 8 hex chars — short enough for a QR fallback readout
                let fingerprint = pairing_fingerprint(&code);
                let ttl = Duration::from_secs(120);
                // Least-privilege default: a scanning device redeems as Viewer, then the operator
                // approves/re-roles it. (The role-at-approval handshake is the Part B follow-on.)
                reg.offer_pairing(code.clone(), Role::Viewer, now, ttl);
                Some(ServerMessage::PairingCode {
                    code,
                    fingerprint,
                    expires_in_secs: ttl.as_secs(),
                })
            }
            _ => None,
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
                        // Remote Control device management is served here against the
                        // SessionRegistry (the server owns it); everything else falls through to
                        // the application handler (86ajxer8n).
                        if let Some(msg) = self.handle_remote_command(&req.command).await {
                            msg
                        } else {
                            match (self.handler)(role, &req.command) {
                                Reply::Ack => ServerMessage::Ack {
                                    request_id: req.request_id,
                                },
                                Reply::Deny(reason) => ServerMessage::Denied {
                                    request_id: req.request_id,
                                    reason,
                                },
                                Reply::Message(msg) => *msg,
                            }
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
/// Build the operator's Remote Control snapshot — paired devices + pending requests — as
/// JS-friendly wire views (seconds instead of `Duration`, and never a session token).
fn remote_snapshot(reg: &SessionRegistry, now: std::time::Instant) -> ServerMessage {
    ServerMessage::RemoteDevices {
        devices: reg
            .sessions(now)
            .into_iter()
            .map(|s| RemoteDeviceView {
                device_id: s.device_id.0,
                name: s.name,
                platform: s.platform,
                role: s.role,
                idle_secs: s.idle_for.as_secs(),
                pinned: s.pinned,
            })
            .collect(),
        pending: reg
            .pending_requests(now)
            .into_iter()
            .map(|p| RemotePendingView {
                device_id: p.device_id.0,
                name: p.name,
                platform: p.platform,
                fingerprint: p.fingerprint,
                waiting_secs: p.waiting_for.as_secs(),
            })
            .collect(),
    }
}

/// A short, human-readable fingerprint for the "Pair a device" QR, rendered as space-separated hex
/// pairs (e.g. `A1 · B2 · C3 · D4`). NOTE: derived from the pairing code as a placeholder — the
/// real TLS-cert SHA-256 pinning belongs to the pairing-handshake redesign (Part B).
fn pairing_fingerprint(code: &str) -> String {
    code.to_uppercase()
        .as_bytes()
        .chunks(2)
        .map(|c| String::from_utf8_lossy(c).into_owned())
        .collect::<Vec<_>>()
        .join(" · ")
}

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

/// Sanitize the untrusted device platform / OS string before it enters the registry and the
/// operator's snapshots: strip control characters and length-cap. Unlike the device name, an
/// empty platform is allowed (it is optional and omitted on the wire).
fn sanitize_platform(raw: &str) -> String {
    raw.chars()
        .filter(|c| !c.is_control())
        .take(MAX_PLATFORM)
        .collect::<String>()
        .trim()
        .to_string()
}
