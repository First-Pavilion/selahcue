//! Happy-path (and boundary) proof, through the real pinned-TLS `ControlServer` and the public
//! `RemoteOperator` methods, of the call sites the FR-082 reply-redaction work (17tnw2axppb) moved
//! into `operator_reply.rs` but that no earlier test executed end to end: `new_pairing_code`,
//! the device-management family (`remote_devices`, `approve_pairing`, `deny_pairing`,
//! `revoke_session`, `set_session_role`) and `screen_frame`. The server answers the first two
//! groups itself (a hostile reply cannot be injected there), so this is the only wire-level
//! coverage they get.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::{handler_for, LiveController, RemoteOperator};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlServer, Role, SelfSigned};
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

struct Host {
    addr: SocketAddr,
    pin: CertPin,
    registry: Arc<AsyncMutex<SessionRegistry>>,
}

/// A host running the real controller handler. `operator` (Role::Operator) and `producer`
/// (Role::Producer) are paired; `viewer-1` is an additional active Viewer session; `pending-1`
/// and `pending-2` are outstanding pairing requests. `endpoint` enables the QR invite URI.
async fn host(endpoint: bool) -> Host {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    )));
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        for (id, role) in [
            ("operator", Role::Operator),
            ("producer", Role::Producer),
            ("viewer-1", Role::Viewer),
        ] {
            reg.offer_pairing(format!("c-{id}"), role, now, Duration::from_secs(300));
            reg.redeem(
                &format!("c-{id}"),
                DeviceId(id.into()),
                SessionToken::new(format!("tok-{id}")),
                now,
            )
            .unwrap();
        }
        for (id, name) in [("pending-1", "Anna's iPhone"), ("pending-2", "Booth iPad")] {
            reg.submit_request(DeviceId(id.into()), name, "iOS", "AA:BB:CC", now)
                .unwrap();
        }
    }
    let mut server =
        ControlServer::new(&identity, registry.clone(), handler_for(controller)).unwrap();
    if endpoint {
        server = server.with_pairing_endpoint("192.168.1.9".into(), 8443, identity.pin.to_hex());
    }
    let server = Arc::new(server);
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = server.run(listener).await;
    });
    Host {
        addr,
        pin,
        registry,
    }
}

async fn connect(h: &Host, id: &str) -> RemoteOperator {
    RemoteOperator::connect(h.addr, "localhost", h.pin, id, &format!("tok-{id}"))
        .await
        .unwrap()
}

fn role_of(devices: &[selahcue_lan::protocol::RemoteDeviceView], id: &str) -> Option<Role> {
    devices.iter().find(|d| d.device_id == id).map(|d| d.role)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn new_pairing_code_returns_a_fresh_single_use_code_and_the_invite() {
    let h = host(true).await;
    let mut op = connect(&h, "operator").await;
    let offers_before = h.registry.lock().await.pending_count();

    let (code, fingerprint, expires, uri) = op.new_pairing_code().await.unwrap();
    assert_eq!(code.len(), 8, "8 hex chars: {code}");
    assert!(code.chars().all(|c| c.is_ascii_hexdigit()), "{code}");
    assert_eq!(expires, 120);
    assert_eq!(
        fingerprint.replace(':', "").to_lowercase(),
        h.pin.to_hex(),
        "the fingerprint is the host cert pin, colon-grouped"
    );
    let uri = uri.expect("an endpoint was configured, so the invite URI is present");
    assert!(uri.starts_with("selahcue://pair?"), "{uri}");
    assert!(
        uri.contains(&format!("code={code}")),
        "the invite carries this code: {uri}"
    );
    assert_eq!(
        h.registry.lock().await.pending_count(),
        offers_before + 1,
        "the code is registered as a pairing offer"
    );

    // A second call mints a DIFFERENT code (never a replay of the first).
    let (code2, _, _, _) = op.new_pairing_code().await.unwrap();
    assert_ne!(code, code2);
    assert_eq!(h.registry.lock().await.pending_count(), offers_before + 2);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn new_pairing_code_without_an_endpoint_has_no_uri() {
    let h = host(false).await;
    let mut op = connect(&h, "operator").await;
    let (code, _fingerprint, _expires, uri) = op.new_pairing_code().await.unwrap();
    assert_eq!(code.len(), 8);
    assert_eq!(
        uri, None,
        "no LAN endpoint configured: show the code, no fake QR"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_devices_lists_paired_devices_and_pending_requests() {
    let h = host(false).await;
    let mut op = connect(&h, "operator").await;
    let (devices, pending) = op.remote_devices().await.unwrap();

    assert_eq!(role_of(&devices, "operator"), Some(Role::Operator));
    assert_eq!(role_of(&devices, "producer"), Some(Role::Producer));
    assert_eq!(role_of(&devices, "viewer-1"), Some(Role::Viewer));
    assert_eq!(devices.len(), 3);
    let ids: Vec<_> = pending.iter().map(|p| p.device_id.as_str()).collect();
    assert_eq!(ids, ["pending-1", "pending-2"], "sorted, none lost");
    let anna = &pending[0];
    assert_eq!(
        (anna.name.as_str(), anna.platform.as_str()),
        ("Anna's iPhone", "iOS")
    );
    assert_eq!(anna.fingerprint, "AA:BB:CC");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn approve_deny_revoke_and_re_role_update_the_host_and_return_the_fresh_snapshot() {
    let h = host(false).await;
    let mut op = connect(&h, "operator").await;

    // Approve pending-1 as a Producer: it leaves the pending list and becomes a session.
    let (devices, pending) = op
        .approve_pairing("pending-1", Role::Producer)
        .await
        .unwrap();
    assert_eq!(role_of(&devices, "pending-1"), Some(Role::Producer));
    assert_eq!(
        pending
            .iter()
            .map(|p| p.device_id.as_str())
            .collect::<Vec<_>>(),
        ["pending-2"]
    );

    // Deny pending-2: gone from pending, never a session.
    let (devices, pending) = op.deny_pairing("pending-2").await.unwrap();
    assert!(pending.is_empty());
    assert_eq!(role_of(&devices, "pending-2"), None);

    // Re-role viewer-1 to Assistant.
    let (devices, _) = op
        .set_session_role("viewer-1", Role::Assistant)
        .await
        .unwrap();
    assert_eq!(role_of(&devices, "viewer-1"), Some(Role::Assistant));

    // Revoke it: the session is gone.
    let (devices, _) = op.revoke_session("viewer-1").await.unwrap();
    assert_eq!(role_of(&devices, "viewer-1"), None);
    assert!(
        !h.registry
            .lock()
            .await
            .sessions(Instant::now())
            .iter()
            .any(|s| s.device_id.0 == "viewer-1"),
        "the host registry agrees with the reply"
    );
}

/// Boundaries: a remotely-paired device can never be made an Operator (approve or re-role), and
/// naming a device that does not exist changes nothing.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn the_operator_role_cannot_be_granted_remotely_and_unknown_devices_are_noops() {
    let h = host(false).await;
    let mut op = connect(&h, "operator").await;

    // Approve as Operator is refused fail-closed: the request stays pending.
    let (devices, pending) = op
        .approve_pairing("pending-1", Role::Operator)
        .await
        .unwrap();
    assert_eq!(role_of(&devices, "pending-1"), None);
    assert!(pending.iter().any(|p| p.device_id == "pending-1"));

    // Re-role to Operator is a no-op: the role is unchanged.
    let (devices, _) = op
        .set_session_role("viewer-1", Role::Operator)
        .await
        .unwrap();
    assert_eq!(role_of(&devices, "viewer-1"), Some(Role::Viewer));

    // Unknown ids: every mutator answers with the unchanged snapshot (3 devices, 2 pending).
    for (devices, pending) in [
        op.approve_pairing("ghost", Role::Viewer).await.unwrap(),
        op.deny_pairing("ghost").await.unwrap(),
        op.revoke_session("ghost").await.unwrap(),
        op.set_session_role("ghost", Role::Viewer).await.unwrap(),
    ] {
        assert_eq!((devices.len(), pending.len()), (3, 2));
    }
}

/// A device without the device-management permission gets the host's refusal, surfaced as a
/// short protocol error that names the reply variant (`denied`) - the redacting path, for real.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_non_operator_is_refused_device_management_with_a_short_named_error() {
    let h = host(false).await;
    let mut producer = connect(&h, "producer").await;
    let err = producer
        .remote_devices()
        .await
        .expect_err("a Producer lacks ManageDevices");
    assert_eq!(
        err.to_string(),
        "protocol error: expected remote_devices, got: denied"
    );
    let err = producer
        .new_pairing_code()
        .await
        .expect_err("a Producer lacks ManageDevices");
    assert_eq!(
        err.to_string(),
        "protocol error: expected pairing_code, got: denied"
    );
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn screen_frame_returns_a_clamped_thumbnail_for_a_live_screen_and_none_for_an_unknown_one() {
    let h = host(false).await;
    let mut op = connect(&h, "operator").await;
    op.next().await.unwrap();
    op.go_live().await.unwrap();

    let frame = op
        .screen_frame("main", 96, 54)
        .await
        .unwrap()
        .expect("main has live content");
    assert!(
        frame.w > 0 && frame.w <= 96 && frame.h > 0 && frame.h <= 54,
        "clamped to the request: {}x{}",
        frame.w,
        frame.h
    );
    assert!(!frame.rgba.is_empty());

    assert!(
        op.screen_frame("disco", 96, 54).await.unwrap().is_none(),
        "an unknown screen has no frame (Ok(None), not an error)"
    );
}
