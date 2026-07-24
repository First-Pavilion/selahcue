//! Over-the-wire pairing (FR-086/174): QR-code redemption over pinned TLS, host
//! confirmation, single-use + TTL enforcement, and issued-credential reconnects.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use futures_util::FutureExt;
use selahcue_lan::protocol::{Command, PairingInvite, ServerMessage};
use selahcue_lan::session::SessionRegistry;
use selahcue_lan::{
    generate_pairing_code, CertPin, ControlClient, ControlServer, PairingApproval, Reply, Role,
    SelfSigned,
};
use std::net::SocketAddr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

fn approve_all() -> PairingApproval {
    Arc::new(|_name| async { true }.boxed())
}

fn decline_all() -> PairingApproval {
    Arc::new(|_name| async { false }.boxed())
}

/// An approval that records whether it was ever consulted.
fn tracking(consulted: Arc<AtomicBool>, verdict: bool) -> PairingApproval {
    Arc::new(move |_name| {
        consulted.store(true, Ordering::SeqCst);
        async move { verdict }.boxed()
    })
}

/// Attempt a pairing that must fail; returns the error text.
async fn pair_err(addr: SocketAddr, pin: CertPin, code: &str, name: &str) -> String {
    match ControlClient::pair(addr, "localhost", pin, code, name).await {
        Ok(_) => panic!("pairing unexpectedly succeeded"),
        Err(e) => format!("{e}"),
    }
}

async fn start_server(
    approval: Option<PairingApproval>,
    code: &str,
    ttl: Duration,
) -> (SocketAddr, CertPin) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    registry
        .lock()
        .await
        .offer_pairing(code, Role::Producer, Instant::now(), ttl);

    let handler = Arc::new(|_role: Role, _cmd: &Command| Reply::Ack);
    let mut server = ControlServer::new(&identity, registry, handler).unwrap();
    if let Some(approval) = approval {
        server = server.with_pairing_approval(approval);
    }
    let server = Arc::new(server);
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = server.run(listener).await;
    });
    (addr, pin)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn pair_over_the_wire_then_control_then_reconnect() {
    let (addr, pin) = start_server(Some(approve_all()), "CODE1234", Duration::from_secs(60)).await;

    // Redeem the code: the connection comes back already authenticated as Producer.
    let (mut client, creds) =
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "Dami's iPhone")
            .await
            .unwrap();
    assert_eq!(client.role(), Role::Producer);
    assert!(!creds.token.is_empty() && creds.device_id.starts_with("dev-"));

    // The paired connection can control immediately.
    assert!(matches!(
        client.command(Command::GoLive).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    client.close().await.ok();

    // The issued credentials work for a fresh reconnect (graceful-reconnect path).
    let again = ControlClient::connect(addr, "localhost", pin, &creds.device_id, &creds.token)
        .await
        .unwrap();
    assert_eq!(again.role(), Role::Producer);
    again.close().await.ok();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn host_decline_rejects_and_keeps_the_code_for_the_legit_device() {
    let (addr, pin) = start_server(Some(decline_all()), "CODE1234", Duration::from_secs(60)).await;
    let err = pair_err(addr, pin, "CODE1234", "intruder").await;
    assert!(err.contains("Forbidden"), "declined => Forbidden: {err}");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn unknown_code_is_rejected_without_consulting_the_host() {
    let consulted = Arc::new(AtomicBool::new(false));
    let (addr, pin) = start_server(
        Some(tracking(consulted.clone(), true)),
        "REALCODE",
        Duration::from_secs(60),
    )
    .await;
    let err = pair_err(addr, pin, "WRONGCODE", "x").await;
    assert!(err.contains("Unauthenticated"), "{err}");
    assert!(
        !consulted.load(Ordering::SeqCst),
        "a bad code must never raise a confirmation prompt"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn pairing_is_disabled_unless_opted_in() {
    let (addr, pin) = start_server(None, "CODE1234", Duration::from_secs(60)).await;
    let err = pair_err(addr, pin, "CODE1234", "x").await;
    assert!(err.contains("Forbidden"), "{err}");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_code_is_single_use() {
    let (addr, pin) = start_server(Some(approve_all()), "CODE1234", Duration::from_secs(60)).await;
    let (client, _creds) = ControlClient::pair(addr, "localhost", pin, "CODE1234", "first")
        .await
        .unwrap();
    client.close().await.ok();
    // The same code cannot be redeemed twice.
    let err = pair_err(addr, pin, "CODE1234", "replayer").await;
    assert!(err.contains("Unauthenticated"), "{err}");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn an_expired_code_is_rejected() {
    let (addr, pin) =
        start_server(Some(approve_all()), "CODE1234", Duration::from_millis(50)).await;
    tokio::time::sleep(Duration::from_millis(120)).await;
    let err = pair_err(addr, pin, "CODE1234", "late").await;
    assert!(err.contains("Unauthenticated"), "{err}");
}

#[test]
fn generated_codes_are_wellformed_and_vary() {
    let a = generate_pairing_code();
    let b = generate_pairing_code();
    assert_eq!(a.len(), 8);
    assert!(a.chars().all(|c| c.is_ascii_alphanumeric()));
    // No ambiguous glyphs in the hand-typable alphabet.
    assert!(!a.contains(['0', 'O', '1', 'I']));
    assert_ne!(a, b, "two draws should differ (2^-40 collision odds)");
}

#[test]
fn pairing_invite_uri_round_trips_and_rejects_garbage() {
    let invite = PairingInvite {
        host: "192.168.1.20".into(),
        port: 53621,
        pin_hex: "ab".repeat(32),
        code: "CODE1234".into(),
    };
    let uri = invite.to_uri().unwrap();
    assert!(uri.starts_with("selahcue://pair?"));
    assert_eq!(PairingInvite::parse_uri(&uri).unwrap(), invite);

    // Malformed inputs parse to None, never panic.
    for bad in [
        "",
        "selahcue://pair?",
        "selahcue://pair?host=&port=1&pin=ab&code=C",
        "selahcue://pair?host=h&port=notaport&pin=ab&code=C",
        "selahcue://pair?host=h&port=1&pin=ab", // missing code
        "http://evil/pair?host=h&port=1&pin=ab&code=C",
        "selahcue://pair?host=h&port=1&pin=ab&code=has space",
    ] {
        assert!(
            PairingInvite::parse_uri(bad).is_none(),
            "should reject: {bad}"
        );
    }

    // A field with URI-breaking characters refuses to encode.
    let evil = PairingInvite {
        host: "a&b".into(),
        port: 1,
        pin_hex: "ab".into(),
        code: "C".into(),
    };
    assert!(evil.to_uri().is_none());
}
