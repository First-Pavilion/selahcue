//! Optional admission gate for generated mutations. No protocol change: after
//! start_send the ordinary bounded exchange is allowed to finish. Readiness waits
//! remain cancellable before that admission point, without poisoning the socket.
use crate::TransportError;
use futures_util::{Sink, SinkExt};
use std::pin::Pin;
use tokio_tungstenite::tungstenite::{Error, Message};

pub async fn send_when_admitted<S>(
    sink: &mut S,
    message: Message,
    admit: impl Fn() -> bool + Send + Sync,
) -> Result<(), TransportError>
where
    S: Sink<Message, Error = Error> + Unpin,
{
    {
        let ready = futures_util::future::poll_fn(|cx| Pin::new(&mut *sink).poll_ready(cx));
        tokio::pin!(ready);
        loop {
            if !admit() {
                return Err(TransportError::Protocol(
                    "generated mutation admission refused".into(),
                ));
            }
            tokio::select! {
                biased;
                _=tokio::time::sleep(std::time::Duration::from_millis(20))=>{},
                result=&mut ready=>{result?;break;}
            }
        }
    }
    // Re-prove admission at actual enqueue, after releasing the readiness borrow.
    if !admit() {
        return Err(TransportError::Protocol(
            "generated mutation admission refused".into(),
        ));
    }
    Pin::new(&mut *sink).start_send(message)?;
    sink.flush().await?;
    Ok(())
}
