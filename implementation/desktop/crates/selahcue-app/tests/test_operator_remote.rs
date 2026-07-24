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

/// Plan editing over the wire is Operator-only: the host shell's Operator session
/// edits (and the host plan changes); a Producer's edit is RBAC-denied.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn plan_editing_is_operator_only_over_the_wire() {
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
        reg.offer_pairing("o", Role::Operator, now, Duration::from_secs(300));
        reg.redeem("o", DeviceId("op".into()), SessionToken::new("tok-op"), now)
            .unwrap();
        reg.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        reg.redeem(
            "p",
            DeviceId("prod".into()),
            SessionToken::new("tok-prod"),
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

    // The Operator adds + renames + moves over the wire; the host plan reflects it.
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "op", "tok-op")
        .await
        .unwrap();
    let view = op.add_item("song", "Closing Song").await.unwrap();
    assert_eq!(view.items.len(), 2);
    let new_id = view.items[1].id;
    let view = op.rename_item(new_id, "Benediction").await.unwrap();
    assert_eq!(view.items[1].title, "Benediction");
    let view = op.move_item(new_id, 0).await.unwrap();
    assert_eq!(view.items[0].title, "Benediction");
    assert_eq!(
        controller.lock().unwrap().plan().len(),
        2,
        "host plan edited"
    );
    assert!(
        controller.lock().unwrap().take_plan_dirty(),
        "persist signal raised"
    );

    // A Producer's edit is DENIED and changes nothing (view shows unchanged plan).
    let mut prod = RemoteOperator::connect(addr, "localhost", pin, "prod", "tok-prod")
        .await
        .unwrap();
    let view = prod.add_item("song", "Sneaky").await.unwrap();
    assert_eq!(view.items.len(), 2, "Producer edit denied — plan unchanged");
}

/// Story 86ajpew05 acceptance, over the wire: a remote client searches
/// scripture, stages the hit, goes live — and the HOST's audience output shows
/// the verse text from the bundled translation.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn wire_scripture_search_stage_golive_shows_verse_text() {
    let (addr, pin, controller) = setup().await;
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();

    // Keyword search (not a reference) finds the verse in the bundled WEB text.
    let hits = op
        .scripture_search("work together for good", None)
        .await
        .unwrap();
    assert!(
        hits.iter().any(|h| h.reference == "Romans 8:28"),
        "keyword search over the wire: {hits:?}"
    );
    // The hit carries its verse text (the operator sees WHY it matched).
    assert!(
        hits[0].text.contains("work together for good"),
        "hit snippet present: {}",
        hits[0].text
    );

    // Stage the hit: Preview holds the scripture (not a plan index) and the
    // operator view says so.
    let view = op.stage_scripture(&hits[0].reference, None).await.unwrap();
    assert_eq!(view.staged_index, None);
    assert_eq!(view.staged_scripture.as_deref(), Some("Romans 8:28"));

    // Go Live: the host's audience output now carries the VERSE TEXT.
    let view = op.go_live().await.unwrap();
    assert_eq!(view.live_scripture.as_deref(), Some("Romans 8:28"));
    let c = controller.lock().unwrap();
    let live = c.presenter().live_slide().expect("live slide");
    assert!(
        live.title.contains("Romans 8:28 (KJV)"),
        "default translation is KJV"
    );
    let body = live.body.join(" ");
    assert!(
        body.contains("all things work together for good"),
        "audience output shows the KJV verse text, got: {body}"
    );
}

/// Output configuration is Operator-only over the wire: the Operator identifies
/// and assigns; a Producer's attempts are RBAC-denied; the injected output
/// status travels the wire into the remote operator view.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn output_configuration_is_operator_only_and_status_travels_the_wire() {
    use selahcue_lan::protocol::{DisplayView, OutputStatusView};

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
    controller.lock().unwrap().set_output_status(
        vec![OutputStatusView {
            role: "main".into(),
            display: Some("Projector".into()),
            width: 1920,
            height: 1080,
            assigned: true,
            assigned_key: Some("Projector|1920x1080".into()),
        }],
        vec![DisplayView {
            key: "Projector|1920x1080".into(),
            name: "Projector".into(),
            width: 1920,
            height: 1080,
        }],
    );

    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("o", Role::Operator, now, Duration::from_secs(300));
        reg.redeem("o", DeviceId("op".into()), SessionToken::new("tok-op"), now)
            .unwrap();
        reg.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        reg.redeem(
            "p",
            DeviceId("prod".into()),
            SessionToken::new("tok-prod"),
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

    // The Operator sees the outputs, identifies, and assigns.
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "op", "tok-op")
        .await
        .unwrap();
    let view = op.view().await.unwrap();
    assert_eq!(view.outputs.len(), 1);
    assert_eq!(view.outputs[0].display.as_deref(), Some("Projector"));
    assert_eq!(view.displays.len(), 1);
    op.identify_outputs().await.unwrap();
    controller.lock().unwrap().tick(Instant::now());
    assert!(controller.lock().unwrap().identify_until().is_some());
    op.assign_output("stage", "Projector|1920x1080")
        .await
        .unwrap();
    assert_eq!(
        controller.lock().unwrap().take_pending_assignments(),
        vec![("stage".to_string(), "Projector|1920x1080".to_string())]
    );

    // A Producer's identify/assign are DENIED (no pending change appears).
    let mut prod = RemoteOperator::connect(addr, "localhost", pin, "prod", "tok-prod")
        .await
        .unwrap();
    prod.identify_outputs().await.unwrap();
    prod.assign_output("main", "Projector|1920x1080")
        .await
        .unwrap();
    assert!(
        controller
            .lock()
            .unwrap()
            .take_pending_assignments()
            .is_empty(),
        "Producer assignment denied"
    );
}

/// Timer live-adjust over the wire (owner story 86ajphu98): +1:00 on a running
/// countdown extends the host's readout; RBAC = the Timer permission.
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn remote_adjust_timer_extends_the_running_countdown() {
    let (addr, pin, controller) = setup().await;
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();
    op.start_timer(300).await.unwrap();
    controller.lock().unwrap().tick(Instant::now());

    op.adjust_timer(60).await.unwrap();
    controller.lock().unwrap().tick(Instant::now());
    let t = op.view().await.unwrap().timer.expect("timer");
    assert!(
        t.remaining_secs.is_some_and(|r| r > 300 && r <= 360),
        "extended past the original 5:00: {:?}",
        t.remaining_secs
    );
}
