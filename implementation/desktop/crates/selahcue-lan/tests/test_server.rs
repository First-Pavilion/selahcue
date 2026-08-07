//! End-to-end transport tests over a real loopback TLS WebSocket: certificate
//! pinning, device authentication, RBAC enforcement, and a connection-leak guard.
//! Compiled only with the `server` feature.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{Command, DenyReason, ServerMessage};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlClient, ControlServer, Role, SelfSigned};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex;

/// Start a server with a Producer and an Assistant pre-paired. Returns the bound
/// address, the cert pin to trust, and a handle to the running server.
async fn start_server() -> (
    SocketAddr,
    CertPin,
    Arc<ControlServer>,
    Arc<Mutex<SessionRegistry>>,
) {
    start_server_cfg(Duration::from_secs(10)).await
}

/// As [`start_server`] but with a configurable pre-auth handshake timeout.
async fn start_server_cfg(
    handshake_timeout: Duration,
) -> (
    SocketAddr,
    CertPin,
    Arc<ControlServer>,
    Arc<Mutex<SessionRegistry>>,
) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let registry = Arc::new(Mutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("prod-code", Role::Producer, now, Duration::from_secs(300));
        reg.redeem(
            "prod-code",
            DeviceId("producer".into()),
            SessionToken::new("tok-prod"),
            now,
        )
        .unwrap();
        reg.offer_pairing("asst-code", Role::Assistant, now, Duration::from_secs(300));
        reg.redeem(
            "asst-code",
            DeviceId("assistant".into()),
            SessionToken::new("tok-asst"),
            now,
        )
        .unwrap();
    }

    // Handler: GetState returns a State snapshot; everything else is Ack.
    let handler: Handler = Arc::new(|_role, cmd| match cmd {
        Command::GetState => Reply::Message(Box::new(ServerMessage::State {
            live_item: None,
            blackout: false,
        })),
        _ => Reply::Ack,
    });

    let server = Arc::new(
        ControlServer::new(&identity, registry.clone(), handler)
            .unwrap()
            .with_handshake_timeout(handshake_timeout),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });
    (addr, pin, server, registry)
}

async fn wait_until(mut cond: impl FnMut() -> bool, timeout: Duration) -> bool {
    let start = tokio::time::Instant::now();
    while start.elapsed() < timeout {
        if cond() {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    cond()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn pinned_authenticated_and_rbac_enforced_end_to_end() {
    let (addr, pin, _server, _registry) = start_server().await;

    // Producer: correct pin + token → Producer role; GoLive is allowed → Ack.
    let mut producer = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();
    assert_eq!(producer.role(), Role::Producer);
    assert!(matches!(
        producer.command(Command::GoLive).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    // GetState returns a State snapshot via the handler.
    assert!(matches!(
        producer.command(Command::GetState).await.unwrap(),
        ServerMessage::State {
            blackout: false,
            ..
        }
    ));

    // Assistant: GoLive is denied (RBAC), Next is allowed.
    let mut assistant = ControlClient::connect(addr, "localhost", pin, "assistant", "tok-asst")
        .await
        .unwrap();
    assert_eq!(assistant.role(), Role::Assistant);
    assert!(matches!(
        assistant.command(Command::GoLive).await.unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));
    assert!(matches!(
        assistant.command(Command::Next).await.unwrap(),
        ServerMessage::Ack { .. }
    ));

    producer.close().await.unwrap();
    assistant.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn wrong_certificate_pin_is_rejected() {
    let (addr, _pin, _server, _registry) = start_server().await;
    // A client trusting a different pin must fail the TLS handshake.
    let wrong_pin = CertPin::of_cert_der(b"not the operator's certificate");
    let result = ControlClient::connect(addr, "localhost", wrong_pin, "producer", "tok-prod").await;
    assert!(result.is_err(), "a mismatched pin must not connect");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn wrong_token_is_rejected_after_tls() {
    let (addr, pin, _server, _registry) = start_server().await;
    // Correct pin, wrong token → authentication rejected.
    let result = ControlClient::connect(addr, "localhost", pin, "producer", "WRONG-TOKEN").await;
    assert!(result.is_err(), "a wrong token must not authenticate");
    // Unknown device likewise.
    let result = ControlClient::connect(addr, "localhost", pin, "ghost", "tok-prod").await;
    assert!(result.is_err());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn stalled_half_open_connections_are_reaped() {
    // Slowloris: connect but never begin a TLS handshake. Without a handshake
    // timeout these would pin down tasks/fds/the counter forever.
    let (addr, _pin, server, _registry) = start_server_cfg(Duration::from_millis(400)).await;

    let mut stalled = Vec::new();
    for _ in 0..8 {
        // Hold the sockets open (send nothing) so the server awaits a ClientHello.
        stalled.push(tokio::net::TcpStream::connect(addr).await.unwrap());
    }
    // They register as live connections briefly...
    let rose = wait_until(
        || server.active_connection_count() > 0,
        Duration::from_secs(2),
    )
    .await;
    assert!(rose, "stalled connections never registered");

    // ...then the handshake timeout reaps every one — the counter returns to 0.
    let drained = wait_until(
        || server.active_connection_count() == 0,
        Duration::from_secs(5),
    )
    .await;
    assert!(
        drained,
        "half-open connections leaked: {} still live",
        server.active_connection_count()
    );
    drop(stalled);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn connections_do_not_leak_server_state() {
    let (addr, pin, server, registry) = start_server().await;

    // Churn many short-lived connections.
    for _ in 0..40 {
        let mut client = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
            .await
            .unwrap();
        let _ = client.command(Command::GetState).await.unwrap();
        client.close().await.unwrap();
    }

    // Every connection task must have torn down — the live-connection count returns
    // to zero (no per-connection handler leak).
    let drained = wait_until(
        || server.active_connection_count() == 0,
        Duration::from_secs(5),
    )
    .await;
    assert!(
        drained,
        "connection handlers leaked: {} still live",
        server.active_connection_count()
    );

    // And the shared registry never grew: still exactly the 2 pre-paired sessions,
    // no leftover pairing offers — connecting does not accumulate session state.
    let reg = registry.lock().await;
    assert_eq!(
        reg.active_count(),
        2,
        "session registry grew across connections"
    );
    assert_eq!(reg.pending_count(), 0);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn operator_manages_remote_devices_end_to_end() {
    let (addr, pin, _server, registry) = start_server().await;

    // Pre-seed an Operator session (the device-management authority) and one pending pairing
    // request for it to approve. (In production the request arrives over the pairing handshake;
    // here we inject it directly through the shared registry.)
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("op-code", Role::Operator, now, Duration::from_secs(300));
        reg.redeem(
            "op-code",
            DeviceId("operator".into()),
            SessionToken::new("tok-op"),
            now,
        )
        .unwrap();
        reg.submit_request(
            DeviceId("anna-iphone".into()),
            "Anna's iPhone",
            "iOS",
            "fp-anna",
            now,
        )
        .unwrap();
    }

    let mut operator = ControlClient::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap();
    assert_eq!(operator.role(), Role::Operator);

    // List: the pre-paired producer + assistant + this operator are all present, and the one
    // pending request is surfaced with its device-supplied metadata.
    let (devices, pending) = match operator.command(Command::ListRemoteDevices).await.unwrap() {
        ServerMessage::RemoteDevices { devices, pending } => (devices, pending),
        other => panic!("expected RemoteDevices, got {other:?}"),
    };
    assert!(devices
        .iter()
        .any(|d| d.device_id == "producer" && d.role == Role::Producer));
    assert_eq!(pending.len(), 1);
    assert_eq!(pending[0].device_id, "anna-iphone");
    assert_eq!(pending[0].name, "Anna's iPhone");

    // Approve the pending request AS an Assistant → it becomes a live session; pending clears.
    let (devices, pending) = match operator
        .command(Command::ApprovePairing {
            device_id: "anna-iphone".into(),
            role: Role::Assistant,
        })
        .await
        .unwrap()
    {
        ServerMessage::RemoteDevices { devices, pending } => (devices, pending),
        other => panic!("expected RemoteDevices, got {other:?}"),
    };
    assert!(
        pending.is_empty(),
        "approved request must clear from pending"
    );
    let anna = devices
        .iter()
        .find(|d| d.device_id == "anna-iphone")
        .expect("approved device now paired");
    assert_eq!(anna.role, Role::Assistant, "approved with the chosen role");

    // Re-role, then revoke.
    if let ServerMessage::RemoteDevices { devices, .. } = operator
        .command(Command::SetSessionRole {
            device_id: "anna-iphone".into(),
            role: Role::Producer,
        })
        .await
        .unwrap()
    {
        let anna = devices
            .iter()
            .find(|d| d.device_id == "anna-iphone")
            .unwrap();
        assert_eq!(anna.role, Role::Producer, "role updated in place");
    } else {
        panic!("expected RemoteDevices");
    }
    if let ServerMessage::RemoteDevices { devices, .. } = operator
        .command(Command::RevokeSession {
            device_id: "anna-iphone".into(),
        })
        .await
        .unwrap()
    {
        assert!(
            !devices.iter().any(|d| d.device_id == "anna-iphone"),
            "revoked device is gone"
        );
    } else {
        panic!("expected RemoteDevices");
    }

    // NewPairingCode mints a fresh single-use code + fingerprint for the "Pair a device" QR.
    match operator.command(Command::NewPairingCode).await.unwrap() {
        ServerMessage::PairingCode {
            code,
            fingerprint,
            expires_in_secs,
            uri: _,
        } => {
            assert_eq!(code.len(), 8, "8 hex chars");
            assert!(!fingerprint.is_empty());
            assert_eq!(expires_in_secs, 120);
        }
        other => panic!("expected PairingCode, got {other:?}"),
    }

    operator.close().await.unwrap();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn non_operator_cannot_manage_devices() {
    let (addr, pin, _server, _registry) = start_server().await;
    // A Producer holds no ManageDevices permission → every device command is Forbidden at the
    // single authorize() choke point, never reaching the registry.
    let mut producer = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();
    assert!(matches!(
        producer.command(Command::ListRemoteDevices).await.unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));
    assert!(matches!(
        producer
            .command(Command::RevokeSession {
                device_id: "assistant".into()
            })
            .await
            .unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));
    producer.close().await.unwrap();
}
