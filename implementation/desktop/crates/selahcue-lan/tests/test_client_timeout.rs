//! `ControlClient::command`'s timeout must not desynchronize the reply stream.
//!
//! Before this fix, a timed-out `command` abandoned its in-flight reply with no `request_id`
//! correlation on the read side (`recv_json` returns the next frame off the socket, whatever it
//! is). If that abandoned reply arrived after the timeout, the NEXT `command` call on the same
//! connection silently consumed it and reported success for a request that was never actually
//! answered — proven live against the real transport by a security review (Sana S-8, PR #101,
//! ClickUp 86ak4xxwm) with exactly the scenario this test reproduces: a host that stalls once,
//! then recovers. For 86ak4xxwm's Tier 2a control-link reconnect specifically, this was fatal —
//! a poll that happened to land on a stale-but-successful reply would call `observe_success()`,
//! silently cancelling an already-scheduled reconnect and pinning the console at a fabricated
//! "Connected" for the rest of the session.
//!
//! The fix: a connection that has ever timed out is permanently refused further commands
//! (`ControlClient.poisoned`). This test proves that refusal is real, not merely documented.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlClient, ControlServer, Role, SelfSigned};
use std::net::SocketAddr;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex as AsyncMutex;

/// Stand up a real pinned-TLS `ControlServer` whose handler answers `GetState` with a
/// per-call sequence number (`live_item: Some(n)`, `n` starting at 0) and BLOCKS for `stall`
/// on the FIRST call only, then answers immediately from then on.
///
/// Runs on its OWN dedicated runtime, not `tokio::spawn` on the test's runtime: [`Handler`] is
/// a **synchronous** closure (`Arc<dyn Fn(Role, &Command) -> Reply + Send + Sync>`), so
/// simulating a slow host means genuinely blocking the thread that runs it
/// (`std::thread::sleep`). On a runtime shared with the client, that risks stalling the
/// client's own timeout timer too — indistinguishable from "the whole process hiccuped" rather
/// than "the client's `COMMAND_TIMEOUT` fired for real". A dedicated runtime keeps the stall
/// confined to the host side, which is what the scenario is actually testing.
fn spawn_server(stall: Duration) -> (SocketAddr, CertPin, tokio::runtime::Runtime) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).expect("self-signed cert");
    let pin = identity.pin;

    let mut registry_inner = SessionRegistry::new();
    let now = Instant::now();
    registry_inner.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
    registry_inner
        .redeem(
            "p",
            DeviceId("producer".into()),
            SessionToken::new("tok-prod"),
            now,
        )
        .expect("redeem test pairing code");
    let registry = Arc::new(AsyncMutex::new(registry_inner));

    let seq = Arc::new(AtomicU32::new(0));
    let first_call = Arc::new(AtomicBool::new(true));
    let handler: Handler = Arc::new(move |_role, cmd| match cmd {
        Command::GetState => {
            if first_call.swap(false, Ordering::SeqCst) {
                std::thread::sleep(stall);
            }
            let n = seq.fetch_add(1, Ordering::SeqCst);
            Reply::Message(Box::new(ServerMessage::State {
                live_item: Some(n as u64),
                blackout: false,
            }))
        }
        _ => Reply::Ack,
    });

    let server =
        Arc::new(ControlServer::new(&identity, registry, handler).expect("build control server"));

    let std_listener = std::net::TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    std_listener
        .set_nonblocking(true)
        .expect("set listener nonblocking for tokio");
    let addr = std_listener.local_addr().expect("local addr");

    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .expect("build dedicated server runtime");
    rt.spawn(async move {
        let listener =
            tokio::net::TcpListener::from_std(std_listener).expect("tokio listener from std");
        let _ = server.run(listener).await;
    });
    (addr, pin, rt)
}

/// The proof: a host that stalls past `COMMAND_TIMEOUT` once must not leave the connection
/// silently readable-but-wrong afterward.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_timed_out_command_poisons_the_connection_instead_of_returning_a_stale_reply() {
    // Stall the FIRST GetState for longer than COMMAND_TIMEOUT (2s, client.rs), on a server
    // with its own runtime so the stall cannot bleed into this test's own timer.
    let (addr, pin, server) = spawn_server(Duration::from_secs(3));
    let mut client = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .expect("connect to the (not-yet-stalling) auth phase");

    let first = client.command(Command::GetState).await;
    assert!(
        first.is_err(),
        "the stalled first command must time out, not succeed: {first:?}"
    );

    // THE control assertion. Before the fix, `recv_json` has no `request_id` correlation, so
    // this call would read the (by-now-arrived, at ~3s) reply to the TIMED-OUT first request —
    // `Ok(State { live_item: Some(0) })` — and report success for a request it never actually
    // sent an answer to. With the fix, the connection is poisoned and this returns immediately
    // without touching the network at all.
    let second = client.command(Command::GetState).await;
    assert!(
        second.is_err(),
        "a connection must refuse further commands after a timeout, not silently resync onto \
         an abandoned reply: {second:?}"
    );

    server.shutdown_background();
}
