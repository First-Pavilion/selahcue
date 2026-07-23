//! A Rust control client for the pinned WebSocket transport — used by the transport
//! tests and available for a native (desktop) controller. The mobile controller is a
//! separate Flutter client speaking the same protocol.

use crate::pinning::CertPin;
use crate::protocol::{self, AuthRequest, AuthResponse, Command, Request, ServerMessage};
use crate::rbac::Role;
use crate::tls::{client_config, TransportError};
use crate::wire::{recv_json, send_json};
use rustls::pki_types::ServerName;
use std::net::SocketAddr;
use std::sync::Arc;
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

impl ControlClient {
    /// Connect to `addr`, trusting the server **only** if its certificate matches
    /// `pin`, then authenticate as `device_id` with `token`. Returns the granted
    /// role on success.
    pub async fn connect(
        addr: SocketAddr,
        server_name: &str,
        pin: CertPin,
        device_id: &str,
        token: &str,
    ) -> Result<Self, TransportError> {
        let tcp = TcpStream::connect(addr).await?;
        let connector = TlsConnector::from(Arc::new(client_config(pin)?));
        let dns = ServerName::try_from(server_name.to_string())
            .map_err(|_| TransportError::Protocol("invalid server name".into()))?;
        let tls = connector.connect(dns, tcp).await?;
        let (mut ws, _resp) =
            tokio_tungstenite::client_async(format!("wss://{server_name}/"), tls).await?;

        send_json(
            &mut ws,
            &AuthRequest {
                v: protocol::VERSION,
                device_id: device_id.to_string(),
                token: token.to_string(),
            },
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
