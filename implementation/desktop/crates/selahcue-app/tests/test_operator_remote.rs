//! End-to-end: a remote operator (as the Tauri operator shell will) drives the HOST's
//! authoritative controller over the pinned-TLS link and renders from the host's
//! operator view. This is the operator↔output-window loop, verified headlessly (the
//! host controller here stands in for the one the output window renders).

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use futures_util::FutureExt;
use selahcue_app::{handler_for, LiveController, RemoteOperator};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlServer, Role, SelfSigned};
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

async fn setup() -> (SocketAddr, CertPin, Arc<Mutex<LiveController>>) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;

    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
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
        reg.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        reg.redeem(
            "p",
            DeviceId("producer".into()),
            SessionToken::new("tok-prod"),
            now,
        )
        .unwrap();
        reg.offer_pairing("a", Role::Assistant, now, Duration::from_secs(300));
        reg.redeem(
            "a",
            DeviceId("assistant".into()),
            SessionToken::new("tok-asst"),
            now,
        )
        .unwrap();
    }

    let server =
        Arc::new(ControlServer::new(&identity, registry, handler_for(controller.clone())).unwrap());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });
    (addr, pin, controller)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_operator_drives_the_host_and_sees_authoritative_state() {
    let (addr, pin, controller) = setup().await;
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();

    // Initial view mirrors the host plan.
    let v = op.view().await.unwrap();
    assert_eq!(v.plan_name, "Sunday");
    assert_eq!(v.items.len(), 3);
    assert_eq!(v.live_index, None);

    // Next stages Preview on the HOST — Live untouched (FR-012).
    let v = op.next().await.unwrap();
    assert_eq!(v.staged_index, Some(0));
    assert!(v.items[0].is_staged);
    assert_eq!(v.live_index, None);
    assert_eq!(
        controller.lock().unwrap().live_index(),
        None,
        "host Live unchanged by Next"
    );

    // Go Live commits on the host — the host controller reflects it.
    let v = op.go_live().await.unwrap();
    assert_eq!(v.live_index, Some(0));
    assert!(v.items[0].is_live);
    assert_eq!(
        controller.lock().unwrap().live_index(),
        Some(0),
        "host controller is now live"
    );

    // Select the 3rd item (Sermon) by id stages it in Preview.
    let id = v.items[2].id;
    let v = op.select(id).await.unwrap();
    assert_eq!(v.staged_index, Some(2));

    // Blackout is reflected on the host.
    let v = op.blackout(true).await.unwrap();
    assert!(v.blackout);
    assert!(controller.lock().unwrap().is_blackout());

    // Clear returns Live to idle on the host.
    let v = op.clear().await.unwrap();
    assert_eq!(v.live_index, None);
    assert_eq!(controller.lock().unwrap().live_index(), None);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_start_timer_is_reflected_after_a_host_tick() {
    let (addr, pin, controller) = setup().await;
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();

    // StartTimer is accepted; the overlay/snapshot appears once the host ticks (the
    // output window ticks every frame — here we drive one tick explicitly).
    op.start_timer(120).await.unwrap();
    controller.lock().unwrap().tick(Instant::now());

    let t = op
        .view()
        .await
        .unwrap()
        .timer
        .expect("timer visible after a host tick");
    assert_eq!(t.remaining_secs, Some(120));
    assert!(t.running && !t.time_up);

    // Stop clears it immediately (no tick needed).
    assert!(op.stop_timer().await.unwrap().timer.is_none());
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn a_denied_command_is_not_an_error_and_the_view_reflects_unchanged_state() {
    let (addr, pin, controller) = setup().await;
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "assistant", "tok-asst")
        .await
        .unwrap();

    // An Assistant may navigate (stage Preview).
    let v = op.next().await.unwrap();
    assert_eq!(v.staged_index, Some(0));

    // ...but GoLive is denied by RBAC. The remote operator does NOT surface an error —
    // it returns the fresh view, which shows Live still empty.
    let v = op.go_live().await.unwrap();
    assert_eq!(v.live_index, None, "denied GoLive left Live empty");
    assert_eq!(controller.lock().unwrap().live_index(), None);
}

/// The full demo-script chain as ONE wire flow: redeem a pairing code over the wire
/// (as a QR-scanning phone would), then — on the same paired connection — advance and
/// go live, asserting the HOST controller's state actually changed. (The pairing E2E
/// in selahcue-lan runs against a stub handler; this closes the pair→advance gap.)
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn wire_paired_device_advances_the_live_output() {
    use selahcue_lan::PairingApproval;

    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        320,
        180,
        Theme::dark(),
    )));

    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    registry.lock().await.offer_pairing(
        "QRCODE23",
        selahcue_lan::Role::Producer,
        Instant::now(),
        Duration::from_secs(300),
    );
    let approve: PairingApproval = Arc::new(|_name| async { true }.boxed());
    let server = Arc::new(
        ControlServer::new(&identity, registry, handler_for(controller.clone()))
            .unwrap()
            .with_pairing_approval(approve),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });

    // Pair over the wire (the invite's code), then drive the REAL controller.
    let (mut client, _creds) =
        selahcue_lan::ControlClient::pair(addr, "localhost", pin, "QRCODE23", "Demo Phone")
            .await
            .unwrap();
    assert!(matches!(
        client.command(Command::Next).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    assert_eq!(
        controller.lock().unwrap().live_index(),
        None,
        "Next staged Preview only"
    );
    assert!(matches!(
        client.command(Command::GoLive).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    assert_eq!(
        controller.lock().unwrap().live_index(),
        Some(0),
        "a wire-paired device changed the host's live output"
    );
    client.close().await.ok();
}
