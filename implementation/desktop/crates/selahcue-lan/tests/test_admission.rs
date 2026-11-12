#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]
use futures_util::Sink;
use std::{
    pin::Pin,
    sync::{
        atomic::{AtomicBool, AtomicUsize, Ordering},
        Arc,
    },
    task::{Context, Poll},
};
use tokio_tungstenite::tungstenite::{Error, Message};
struct HeldSink {
    ready: Arc<AtomicBool>,
    sent: Arc<AtomicUsize>,
}
impl Sink<Message> for HeldSink {
    type Error = Error;
    fn poll_ready(self: Pin<&mut Self>, _: &mut Context<'_>) -> Poll<Result<(), Error>> {
        if self.ready.load(Ordering::SeqCst) {
            Poll::Ready(Ok(()))
        } else {
            Poll::Pending
        }
    }
    fn start_send(self: Pin<&mut Self>, _: Message) -> Result<(), Error> {
        self.sent.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }
    fn poll_flush(self: Pin<&mut Self>, _: &mut Context<'_>) -> Poll<Result<(), Error>> {
        Poll::Ready(Ok(()))
    }
    fn poll_close(self: Pin<&mut Self>, _: &mut Context<'_>) -> Poll<Result<(), Error>> {
        Poll::Ready(Ok(()))
    }
}
#[tokio::test]
async fn expiry_during_sink_readiness_never_dispatches_a_new_mutation() {
    use selahcue_lan::admission::send_when_admitted;
    let ready = Arc::new(AtomicBool::new(false));
    let allowed = Arc::new(AtomicBool::new(true));
    let sent = Arc::new(AtomicUsize::new(0));
    let r = ready.clone();
    let a = allowed.clone();
    tokio::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_millis(30)).await;
        a.store(false, Ordering::SeqCst);
        r.store(true, Ordering::SeqCst);
    });
    let mut sink = HeldSink {
        ready: ready.clone(),
        sent: sent.clone(),
    };
    assert!(send_when_admitted(
        &mut sink,
        Message::Text("synthetic mutation".into()),
        || allowed.load(Ordering::SeqCst)
    )
    .await
    .is_err());
    assert_eq!(
        sent.load(Ordering::SeqCst),
        0,
        "expired queued mutation must never reach start_send"
    );
    allowed.store(true, Ordering::SeqCst);
    send_when_admitted(
        &mut sink,
        Message::Text("synthetic mutation".into()),
        || allowed.load(Ordering::SeqCst),
    )
    .await
    .unwrap();
    assert_eq!(sent.load(Ordering::SeqCst), 1, "positive dispatch control");
}
