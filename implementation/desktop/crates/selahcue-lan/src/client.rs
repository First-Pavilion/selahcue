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
            match recv_json::<_, PairResponse>(&mut ws).await? {
                PairResponse::Granted {
                    device_id,
                    token,
                    role,
                } => Ok((
                    Self {
                        ws,
                        role,
                        next_id: 1,
                    },
                    PairingCredentials { device_id, token },
                )),
                PairResponse::Rejected { reason } => Err(TransportError::Protocol(format!(
                    "pairing rejected: {reason:?}"
                ))),
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

    /// Send a command and await the operator's reply.
    pub async fn command(&mut self, command: Command) -> Result<ServerMessage, TransportError> {
        let id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1);
        send_json(&mut self.ws, &Request::new(id, command)).await?;
        recv_json(&mut self.ws).await
    }

    /// Close the connection cleanly.
    pub async fn close(mut self) -> Result<(), TransportError> {
        self.ws.close(None).await?;
        Ok(())
    }
}
