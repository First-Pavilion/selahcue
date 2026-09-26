//! A Rust control client for the pinned WebSocket transport — used by the transport
//! tests and available for a native (desktop) controller. The mobile controller is a
//! separate Flutter client speaking the same protocol.

use crate::pinning::CertPin;
use crate::protocol::{
    self, AuthRequest, AuthResponse, Command, Hello, PairRequest, PairResponse, Request,
    ServerMessage,
};
use crate::rbac::Role;
use crate::tls::{client_config, TransportError};
use crate::wire::{recv_json, send_json};
use rustls::pki_types::ServerName;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use tokio::net::TcpStream;
use tokio_rustls::client::TlsStream;
use tokio_rustls::TlsConnector;
use tokio_tungstenite::WebSocketStream;

/// An authenticated control connection to the operator.
pub struct ControlClient {
    ws: WebSocketStream<TlsStream<TcpStream>>,
    role: Role,
    next_id: u64,
    /// Set once a [`command`](Self::command) times out. See that method's doc for why a timed
    /// out connection can never safely be reused (security review, Sana S-8).
    poisoned: bool,
}

/// Credentials issued at pairing time — store these (securely) for reconnects.
/// `Debug` redacts the token.
#[derive(Clone, PartialEq, Eq)]
pub struct PairingCredentials {
    pub device_id: String,
    pub token: String,
}

impl std::fmt::Debug for PairingCredentials {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PairingCredentials")
            .field("device_id", &self.device_id)
            .field("token", &"<redacted>")
            .finish()
    }
}

impl ControlClient {
    /// Total time budget for establishing a session (TCP + TLS + WebSocket + auth).
    /// Mirrors the server's handshake timeout so a peer that accepts TCP but then stalls
    /// the TLS/WebSocket handshake degrades to an error instead of hanging the caller
    /// forever (e.g. a stale endpoint pointing at a now-reused loopback port).
    const CONNECT_TIMEOUT: Duration = Duration::from_secs(10);

    /// How long a pairing attempt waits for the grant — the transport phase plus the server's
    /// operator-approval park window. MUST exceed the server's `PAIRING_PARK_TIMEOUT` (120s) so
    /// the device never hangs up before the operator has decided (else it would burn the code).
    const PAIR_TIMEOUT: Duration = Duration::from_secs(150);

    /// How long [`command`](Self::command) waits for a reply once the connection is already
    /// established.
    ///
    /// Unlike [`CONNECT_TIMEOUT`](Self::CONNECT_TIMEOUT), this bounds a REQUEST over an
    /// already-open socket, not the dial itself — and until this constant existed, nothing did:
    /// `recv_json` had no deadline at all. A half-open connection (Wi-Fi drops, the host machine
    /// sleeps, a switch reboots) is TCP-silent — no RST, no FIN — so a caller waiting on this
    /// reply would hang for however long the OS takes to notice (minutes, on macOS/Linux
    /// defaults). That is precisely the outage shape a reconnect loop exists to recover from
    /// (86ak4xxwm Tier 2a review, Vera P-3): every poll blocked meant the poll never returned,
    /// so the link's own liveness check — the poll failing — could never fire, and the
    /// reconnect path was never even reached. Two seconds is generous for a LAN request/response
    /// (this repo's own handshake timeout budgets far less per phase).
    ///
    /// **Correction (performance review, Vera P-6 / security review, Sana):** an earlier version
    /// of this comment claimed the value "must stay short enough... to get an answer well inside
    /// one tick" of the operator console's 1 Hz `view` poll. That is false as written — 2s is
    /// LONGER than the 1s tick it was claimed to fit inside, so a stall near the bound can still
    /// overrun a poll interval. This is a real, currently-open residual (a caller on a fixed
    /// `setInterval` without backpressure can queue overlapping in-flight calls during a stall),
    /// but it is the WEBVIEW POLL LOOP's property to fix (`dist/app.js`'s `setInterval`, not
    /// this client), and it is strictly better than the un-bounded hang this constant replaced.
    /// Left here rather than silently corrected, so the next reader does not inherit the
    /// original, disproven claim.
    const COMMAND_TIMEOUT: Duration = Duration::from_secs(2);

    /// Establish the pinned-TLS WebSocket transport (no authentication yet).
    async fn establish(
        addr: SocketAddr,
        server_name: &str,
        pin: CertPin,
    ) -> Result<WebSocketStream<TlsStream<TcpStream>>, TransportError> {
        let tcp = TcpStream::connect(addr).await?;
        let connector = TlsConnector::from(Arc::new(client_config(pin)?));
        let dns = ServerName::try_from(server_name.to_string())
            .map_err(|_| TransportError::Protocol("invalid server name".into()))?;
        let tls = connector.connect(dns, tcp).await?;
        let (ws, _resp) =
            tokio_tungstenite::client_async(format!("wss://{server_name}/"), tls).await?;
        Ok(ws)
    }

    /// Connect to `addr`, trusting the server **only** if its certificate matches
    /// `pin`, then authenticate as `device_id` with `token`. Returns the granted
    /// role on success. Fails with a timeout rather than hanging if the peer stalls.
    pub async fn connect(
        addr: SocketAddr,
        server_name: &str,
        pin: CertPin,
        device_id: &str,
        token: &str,
    ) -> Result<Self, TransportError> {
        let attempt = async {
            let mut ws = Self::establish(addr, server_name, pin).await?;
            send_json(
                &mut ws,
                &Hello::Auth(AuthRequest {
                    v: protocol::VERSION,
                    device_id: device_id.to_string(),
                    token: token.to_string(),
                }),
            )
            .await?;
            let role = match recv_json::<_, AuthResponse>(&mut ws).await? {
                AuthResponse::Granted { role } => role,
                AuthResponse::Rejected { reason } => {
                    return Err(TransportError::Protocol(format!(
                        "authentication rejected: {reason:?}"
                    )))
                }
            };
            Ok(Self {
                ws,
                role,
                next_id: 1,
                poisoned: false,
            })
        };

        match tokio::time::timeout(Self::CONNECT_TIMEOUT, attempt).await {
            Ok(result) => result,
            Err(_) => Err(TransportError::Protocol("connection timed out".into())),
        }
    }

    /// Pair with the operator by redeeming the single-use `code` from a
    /// [`PairingInvite`](crate::protocol::PairingInvite): connect pinned, send a
    /// `Pair` hello, and await the grant (which includes the operator's confirmation
    /// window). On success the connection is **already authenticated**; the returned
    /// [`PairingCredentials`] are for storage + later reconnects.
    pub async fn pair(
        addr: SocketAddr,
        server_name: &str,
        pin: CertPin,
        code: &str,
        device_name: &str,
        platform: &str,
    ) -> Result<(Self, PairingCredentials), TransportError> {
        let attempt = async {
            let mut ws = Self::establish(addr, server_name, pin).await?;
            send_json(
                &mut ws,
                &Hello::Pair(PairRequest {
                    v: protocol::VERSION,
                    code: code.to_string(),
                    device_name: device_name.to_string(),
                    platform: platform.to_string(),
                }),
            )
            .await?;
            loop {
                match recv_json::<_, PairResponse>(&mut ws).await? {
                    // Interim: the host parked our request and is awaiting the operator (86ajxhv0q).
                    // Keep waiting for the terminal reply (a UI shows "waiting" meanwhile).
                    PairResponse::Parked => continue,
                    PairResponse::Granted {
                        device_id,
                        token,
                        role,
                    } => {
                        break Ok((
                            Self {
                                ws,
                                role,
                                next_id: 1,
                                poisoned: false,
                            },
                            PairingCredentials { device_id, token },
                        ))
                    }
                    PairResponse::Rejected { reason } => {
                        break Err(TransportError::Protocol(format!(
                            "pairing rejected: {reason:?}"
                        )))
                    }
                }
            }
        };
        match tokio::time::timeout(Self::PAIR_TIMEOUT, attempt).await {
            Ok(result) => result,
            Err(_) => Err(TransportError::Protocol("pairing timed out".into())),
        }
    }

    /// The role granted to this connection.
    pub fn role(&self) -> Role {
        self.role
    }

    /// Send a command and await the operator's reply. Bounded by [`COMMAND_TIMEOUT`](Self::COMMAND_TIMEOUT)
    /// so a half-open connection (the peer vanished without closing the socket) surfaces as an
    /// error a caller can act on — e.g. retry — instead of hanging indefinitely.
    ///
    /// **A connection that has ever timed out here is permanently refused further commands**
    /// (security/correctness review, Sana S-8). `recv_json` reads the next frame off the socket
    /// with no `request_id` correlation, so when a timeout fires there is no way to know whether
    /// the abandoned reply is still in flight. If it is, and this method were simply called
    /// again, the NEXT command would silently receive THIS one's reply — deserializing fine,
    /// since every reply shares one `ServerMessage` shape, and reporting success for a request
    /// that was never actually answered. Measured live: a single >2s host stall left every
    /// subsequent reply permanently one behind, each returned as `Ok`. For this ticket's own
    /// Tier 2a specifically, that is fatal: a poll that happens to land on a stale-but-successful
    /// reply calls `observe_success()`, silently cancelling a reconnect that was already
    /// scheduled and pinning the console at a fabricated "Connected" for the rest of the
    /// session — the exact class of lie this ticket exists to remove. Poisoning trades a
    /// resumable connection for a correct one: every caller here already has a real reconnect
    /// path (`maybe_reconnect_from` replaces the whole `RemoteOperator`/`ControlClient` on the
    /// next failure), so refusing to reuse a connection whose reply stream may be desynchronized
    /// costs one extra dial, never a wrong answer.
    pub async fn command(&mut self, command: Command) -> Result<ServerMessage, TransportError> {
        if self.poisoned {
            return Err(TransportError::Protocol(
                "connection desynchronized after a previous command timed out — reconnect required"
                    .into(),
            ));
        }
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        let exchange = async {
            send_json(&mut self.ws, &Request::new(id, command)).await?;
            recv_json(&mut self.ws).await
        };
        match tokio::time::timeout(Self::COMMAND_TIMEOUT, exchange).await {
            Ok(result) => result,
            Err(_) => {
                self.poisoned = true;
                Err(TransportError::Protocol("command timed out".into()))
            }
        }
    }

    /// Close the connection cleanly.
    pub async fn close(mut self) -> Result<(), TransportError> {
        self.ws.close(None).await?;
        Ok(())
    }
}
