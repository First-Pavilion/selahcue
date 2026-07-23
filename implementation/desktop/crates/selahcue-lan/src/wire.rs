//! JSON-over-WebSocket framing shared by the server and client.

use crate::protocol;
use crate::tls::TransportError;
use futures_util::{SinkExt, StreamExt};
use serde::de::DeserializeOwned;
use serde::Serialize;
use tokio::io::{AsyncRead, AsyncWrite};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::WebSocketStream;

/// Serialize `msg` to JSON and send it as a WebSocket text frame.
pub(crate) async fn send_json<S>(
    ws: &mut WebSocketStream<S>,
    msg: &impl Serialize,
) -> Result<(), TransportError>
where
    S: AsyncRead + AsyncWrite + Unpin,
{
    ws.send(Message::text(protocol::to_json(msg)?)).await?;
    Ok(())
}

/// Receive the next text frame and deserialize it, skipping ping/pong/binary
/// frames. Errors `Closed` if the peer closes first.
pub(crate) async fn recv_json<S, T>(ws: &mut WebSocketStream<S>) -> Result<T, TransportError>
where
    S: AsyncRead + AsyncWrite + Unpin,
    T: DeserializeOwned,
{
    loop {
        match ws.next().await.ok_or(TransportError::Closed)?? {
            Message::Text(t) => return protocol::from_json(t.as_str()).map_err(TransportError::from),
            Message::Close(_) => return Err(TransportError::Closed),
            _ => continue,
        }
    }
}
