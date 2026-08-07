//! Over-the-wire operator-paced pairing (86ajxer8n — replaces the FR-086 output-window Y/N
//! host-confirmation). A device redeeming a QR code PARKS as a pending request until the operator
//! approves it (assigning a role) or denies it over the Remote Control channel; the operator-minted
//! token is then pushed to the still-parked socket. Covers: happy path + reconnect, deny, unknown/
//! expired/disabled/single-use codes, the fail-closed Operator-role clamp, platform threading, the
//! park timeout, disconnect cleanup, and approve idempotency — all over pinned loopback TLS.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_lan::protocol::{Command, PairingInvite, ServerMessage};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{
    generate_pairing_code, CertPin, ControlClient, ControlServer, Reply, Role, SelfSigned,
};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

type Registry = Arc<AsyncMutex<SessionRegistry>>;

/// Start a server. `enabled` opts into operator-paced pairing; `code`/`code_ttl` seed one admission
/// code; `park` is the parked-connection timeout. A pre-paired **Operator** session (device
/// `operator` / token `tok-op`) lets a second connection drive approve/deny.
async fn start_server_cfg(
    enabled: bool,
    code: &str,
    code_ttl: Duration,
    park: Duration,
) -> (SocketAddr, CertPin, Registry) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        // The admission code (its baked role is unused — the role is assigned at approval).
        reg.offer_pairing(code, Role::Producer, now, code_ttl);
        reg.offer_pairing("op-code", Role::Operator, now, Duration::from_secs(300));
        reg.redeem(
            "op-code",
            DeviceId("operator".into()),
            SessionToken::new("tok-op"),
            now,
        )
        .unwrap();
    }
    let handler = Arc::new(|_role: Role, _cmd: &Command| Reply::Ack);
    let mut server = ControlServer::new(&identity, registry.clone(), handler)
        .unwrap()
        .with_park_timeout(park);
    if enabled {
        server = server.with_pairing_requests();
    }
    let server = Arc::new(server);
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = server.run(listener).await;
    });
    (addr, pin, registry)
}

/// Convenience: pairing enabled, a generous park window.
async fn start_server(
    enabled: bool,
    code: &str,
    code_ttl: Duration,
) -> (SocketAddr, CertPin, Registry) {
    start_server_cfg(enabled, code, code_ttl, Duration::from_secs(60)).await
}

async fn operator(addr: SocketAddr, pin: CertPin) -> ControlClient {
    ControlClient::connect(addr, "localhost", pin, "operator", "tok-op")
        .await
        .unwrap()
}

/// Poll the operator's device list until a pending request appears; return `(device_id, platform)`.
async fn wait_for_pending(op: &mut ControlClient) -> (String, String) {
    for _ in 0..300 {
        if let ServerMessage::RemoteDevices { pending, .. } =
            op.command(Command::ListRemoteDevices).await.unwrap()
        {
            if let Some(p) = pending.first() {
                return (p.device_id.clone(), p.platform.clone());
            }
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    panic!("no pending pairing request appeared");
}

async fn pending_requests(reg: &Registry) -> usize {
    reg.lock().await.pending_request_count()
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn pair_parks_then_operator_approves_with_role_then_reconnect() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;

    // The device parks awaiting a decision.
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "Dami's iPhone", "iOS").await
    });

    // The operator sees the pending request (with the device's platform) and approves it Producer.
    let mut op = operator(addr, pin).await;
    let (device_id, platform) = wait_for_pending(&mut op).await;
    assert_eq!(
        platform, "iOS",
        "device platform threaded into the pending view"
    );
    assert!(matches!(
        op.command(Command::ApprovePairing {
            device_id: device_id.clone(),
            role: Role::Producer,
        })
        .await
        .unwrap(),
        ServerMessage::RemoteDevices { .. }
    ));

    // The parked device now receives Granted with the assigned role + issued credentials.
    let (mut client, creds) = device.await.unwrap().unwrap();
    assert_eq!(client.role(), Role::Producer);
    assert_eq!(creds.device_id, device_id);
    assert!(!creds.token.is_empty() && creds.device_id.starts_with("dev-"));
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
async fn operator_deny_rejects_the_parked_device_and_clears_it() {
    let (addr, pin, reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "intruder", "").await
    });
    let mut op = operator(addr, pin).await;
    let (device_id, _) = wait_for_pending(&mut op).await;
    op.command(Command::DenyPairing {
        device_id: device_id.clone(),
    })
    .await
    .unwrap();

    let err = format!("{}", device.await.unwrap().err().unwrap());
    assert!(err.contains("Forbidden"), "denied => Forbidden: {err}");
    assert_eq!(pending_requests(&reg).await, 0, "denied request is cleared");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn unknown_code_is_rejected_immediately_without_parking() {
    let (addr, pin, reg) = start_server(true, "REALCODE", Duration::from_secs(60)).await;
    let err = format!(
        "{}",
        ControlClient::pair(addr, "localhost", pin, "WRONGCODE", "x", "")
            .await
            .err()
            .unwrap()
    );
    assert!(err.contains("Unauthenticated"), "{err}");
    assert_eq!(pending_requests(&reg).await, 0, "a bad code never parks");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn pairing_is_disabled_unless_opted_in() {
    let (addr, pin, _reg) = start_server(false, "CODE1234", Duration::from_secs(60)).await;
    let err = format!(
        "{}",
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "x", "")
            .await
            .err()
            .unwrap()
    );
    assert!(err.contains("Forbidden"), "{err}");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_code_is_consumed_when_a_device_parks() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    // First device parks — consuming the single-use code.
    let d1 = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "first", "").await
    });
    let mut op = operator(addr, pin).await;
    let (id1, _) = wait_for_pending(&mut op).await;

    // A SECOND device presenting the same code is rejected — it was withdrawn at the first park.
    let err = format!(
        "{}",
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "replayer", "")
            .await
            .err()
            .unwrap()
    );
    assert!(
        err.contains("Unauthenticated"),
        "code reused after park: {err}"
    );

    op.command(Command::ApprovePairing {
        device_id: id1,
        role: Role::Viewer,
    })
    .await
    .unwrap();
    d1.await.unwrap().unwrap();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn an_expired_code_is_rejected() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_millis(50)).await;
    tokio::time::sleep(Duration::from_millis(120)).await;
    let err = format!(
        "{}",
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "late", "")
            .await
            .err()
            .unwrap()
    );
    assert!(err.contains("Unauthenticated"), "{err}");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn operator_role_cannot_be_granted_to_a_remote_device() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "greedy", "").await
    });
    let mut op = operator(addr, pin).await;
    let (device_id, _) = wait_for_pending(&mut op).await;

    // Fail-closed: approving as Operator creates NO session and leaves the request pending.
    if let ServerMessage::RemoteDevices { devices, pending } = op
        .command(Command::ApprovePairing {
            device_id: device_id.clone(),
            role: Role::Operator,
        })
        .await
        .unwrap()
    {
        assert!(
            !devices.iter().any(|d| d.device_id == device_id),
            "no session may be created for an Operator-role grant"
        );
        assert!(
            pending.iter().any(|p| p.device_id == device_id),
            "the request stays pending for re-approval with a valid role"
        );
    } else {
        panic!("expected RemoteDevices");
    }

    // Re-approving with a valid role succeeds.
    op.command(Command::ApprovePairing {
        device_id: device_id.clone(),
        role: Role::Assistant,
    })
    .await
    .unwrap();
    let (client, _creds) = device.await.unwrap().unwrap();
    assert_eq!(client.role(), Role::Assistant);
    client.close().await.ok();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_parked_device_times_out_and_is_cleaned_up() {
    // Short park window (real time) so the device times out promptly with no operator decision.
    let (addr, pin, reg) = start_server_cfg(
        true,
        "CODE1234",
        Duration::from_secs(60),
        Duration::from_millis(200),
    )
    .await;
    let err = format!(
        "{}",
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "ghost", "")
            .await
            .err()
            .unwrap()
    );
    assert!(err.contains("Forbidden"), "timeout => rejected: {err}");
    // Let the inline cleanup run, then assert nothing lingers.
    tokio::time::sleep(Duration::from_millis(80)).await;
    assert_eq!(
        pending_requests(&reg).await,
        0,
        "a timed-out park leaves no pending request"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_device_that_disconnects_while_parked_is_cleaned_up() {
    let (addr, pin, reg) = start_server_cfg(
        true,
        "CODE1234",
        Duration::from_secs(60),
        Duration::from_millis(300),
    )
    .await;
    let mut op = operator(addr, pin).await;
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "flaky", "").await
    });
    let _ = wait_for_pending(&mut op).await;

    // Drop the device while it is parked; the keepalive ping (or the park deadline) reaps it.
    device.abort();
    tokio::time::sleep(Duration::from_millis(400)).await;
    assert_eq!(
        pending_requests(&reg).await,
        0,
        "a disconnected park must not leak a pending request"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn re_approving_a_paired_device_does_not_grant_twice() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "steady", "").await
    });
    let mut op = operator(addr, pin).await;
    let (device_id, _) = wait_for_pending(&mut op).await;
    op.command(Command::ApprovePairing {
        device_id: device_id.clone(),
        role: Role::Producer,
    })
    .await
    .unwrap();
    let (client, _creds) = device.await.unwrap().unwrap();
    assert_eq!(client.role(), Role::Producer);

    // A second approve finds no pending request → no-op (no panic, snapshot still returned, the
    // existing session's role is untouched).
    if let ServerMessage::RemoteDevices { devices, .. } = op
        .command(Command::ApprovePairing {
            device_id: device_id.clone(),
            role: Role::Assistant,
        })
        .await
        .unwrap()
    {
        let dev = devices.iter().find(|d| d.device_id == device_id).unwrap();
        assert_eq!(
            dev.role,
            Role::Producer,
            "role unchanged by a stale re-approve"
        );
    } else {
        panic!("expected RemoteDevices");
    }
    client.close().await.ok();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn several_devices_park_concurrently_and_are_each_approved() {
    let (addr, pin, reg) = start_server(true, "SHARED00", Duration::from_secs(60)).await;
    // Each device needs its own code (single-use); offer two more.
    {
        let now = Instant::now();
        let mut r = reg.lock().await;
        r.offer_pairing("SHARED01", Role::Producer, now, Duration::from_secs(60));
        r.offer_pairing("SHARED02", Role::Producer, now, Duration::from_secs(60));
    }
    let mut devices = Vec::new();
    for code in ["SHARED00", "SHARED01", "SHARED02"] {
        devices.push(tokio::spawn(async move {
            ControlClient::pair(addr, "localhost", pin, code, "dev", "iOS").await
        }));
    }
    let mut op = operator(addr, pin).await;
    // Wait until all three have parked.
    let mut ids = Vec::new();
    for _ in 0..300 {
        if let ServerMessage::RemoteDevices { pending, .. } =
            op.command(Command::ListRemoteDevices).await.unwrap()
        {
            if pending.len() == 3 {
                ids = pending.iter().map(|p| p.device_id.clone()).collect();
                break;
            }
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    assert_eq!(ids.len(), 3, "all three devices parked");
    for id in ids {
        op.command(Command::ApprovePairing {
            device_id: id,
            role: Role::Assistant,
        })
        .await
        .unwrap();
    }
    for d in devices {
        let (client, _creds) = d.await.unwrap().unwrap();
        assert_eq!(client.role(), Role::Assistant);
        client.close().await.ok();
    }
    assert_eq!(pending_requests(&reg).await, 0, "all requests cleared");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn set_session_role_cannot_promote_a_device_to_operator() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    let device = tokio::spawn(async move {
        ControlClient::pair(addr, "localhost", pin, "CODE1234", "climber", "").await
    });
    let mut op = operator(addr, pin).await;
    let (device_id, _) = wait_for_pending(&mut op).await;
    op.command(Command::ApprovePairing {
        device_id: device_id.clone(),
        role: Role::Producer,
    })
    .await
    .unwrap();
    let (client, _creds) = device.await.unwrap().unwrap();
    assert_eq!(client.role(), Role::Producer);

    // Re-roling to Operator is refused (the same fail-closed clamp as ApprovePairing) — the
    // device stays Producer; a remote LAN peer can never gain device-management authority.
    if let ServerMessage::RemoteDevices { devices, .. } = op
        .command(Command::SetSessionRole {
            device_id: device_id.clone(),
            role: Role::Operator,
        })
        .await
        .unwrap()
    {
        let dev = devices.iter().find(|d| d.device_id == device_id).unwrap();
        assert_eq!(
            dev.role,
            Role::Producer,
            "a remote device must never be re-roled to Operator"
        );
    } else {
        panic!("expected RemoteDevices");
    }
    // A valid (non-Operator) re-role still works.
    if let ServerMessage::RemoteDevices { devices, .. } = op
        .command(Command::SetSessionRole {
            device_id: device_id.clone(),
            role: Role::Assistant,
        })
        .await
        .unwrap()
    {
        let dev = devices.iter().find(|d| d.device_id == device_id).unwrap();
        assert_eq!(dev.role, Role::Assistant);
    } else {
        panic!("expected RemoteDevices");
    }
    client.close().await.ok();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn untrusted_device_name_bidi_and_zero_width_chars_are_stripped() {
    let (addr, pin, _reg) = start_server(true, "CODE1234", Duration::from_secs(60)).await;
    // A name/platform carrying a right-to-left override + a zero-width space (spoofing vectors).
    let device = tokio::spawn(async move {
        ControlClient::pair(
            addr,
            "localhost",
            pin,
            "CODE1234",
            "ab\u{202E}cd\u{200B}",
            "i\u{202E}os",
        )
        .await
    });
    let mut op = operator(addr, pin).await;
    let _ = wait_for_pending(&mut op).await;
    if let ServerMessage::RemoteDevices { pending, .. } =
        op.command(Command::ListRemoteDevices).await.unwrap()
    {
        let p = pending.first().expect("one pending request");
        assert!(
            !p.name.contains('\u{202E}') && !p.name.contains('\u{200B}'),
            "bidi/zero-width chars stripped from name: {:?}",
            p.name
        );
        assert!(
            !p.platform.contains('\u{202E}'),
            "bidi chars stripped from platform: {:?}",
            p.platform
        );
        assert!(
            p.name.contains("abcd"),
            "visible name preserved: {:?}",
            p.name
        );
    } else {
        panic!("expected RemoteDevices");
    }
    device.abort();
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
