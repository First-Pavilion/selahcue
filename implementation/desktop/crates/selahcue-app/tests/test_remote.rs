//! End-to-end: a remote controller drives the live output over the pinned-TLS
//! control link. Compiled only with the `server` feature.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::{handler_for, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{Command, DenyReason, ServerMessage};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlClient, ControlServer, Role, SelfSigned};
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
    let controller = Arc::new(Mutex::new(LiveController::new(plan, 320, 180, Theme::dark())));

    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        reg.redeem("p", DeviceId("producer".into()), SessionToken::new("tok-prod"), now)
            .unwrap();
        reg.offer_pairing("a", Role::Assistant, now, Duration::from_secs(300));
        reg.redeem("a", DeviceId("assistant".into()), SessionToken::new("tok-asst"), now)
            .unwrap();
    }

    let server = Arc::new(
        ControlServer::new(&identity, registry, handler_for(controller.clone())).unwrap(),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });
    (addr, pin, controller)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn producer_drives_the_live_output() {
    let (addr, pin, controller) = setup().await;
    let mut prod = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();

    // Next stages Preview — Live is untouched (FR-012).
    assert!(matches!(
        prod.command(Command::Next).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    assert_eq!(
        controller.lock().unwrap().live_index(),
        None,
        "Next must not change Live"
    );

    // Go Live commits the staged item to the audience output.
    assert!(matches!(
        prod.command(Command::GoLive).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    {
        let c = controller.lock().unwrap();
        assert_eq!(c.live_index(), Some(0));
        assert!(
            c.presenter().live_output().average_luminance() > 1e-6,
            "live output shows content after Go Live"
        );
    }

    // Blackout blacks the audience output.
    assert!(matches!(
        prod.command(Command::Blackout { on: true }).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    assert!(controller.lock().unwrap().presenter().live_output().average_luminance() < 1e-6);

    prod.close().await.ok();
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn rbac_and_application_denials_over_the_wire() {
    let (addr, pin, _controller) = setup().await;

    // Assistant lacks GoLive — the server denies (RBAC) before the handler runs.
    let mut asst = ControlClient::connect(addr, "localhost", pin, "assistant", "tok-asst")
        .await
        .unwrap();
    assert!(matches!(
        asst.command(Command::GoLive).await.unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));
    // ...but Assistant may navigate (stages Preview).
    assert!(matches!(
        asst.command(Command::Next).await.unwrap(),
        ServerMessage::Ack { .. }
    ));
    // ...and cannot wipe the live output (DEC-002 revised — Clear is Producer+).
    assert!(matches!(
        asst.command(Command::Clear).await.unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::Forbidden,
            ..
        }
    ));

    // Producer: an unknown item is an application-level denial (BadRequest).
    let mut prod = ControlClient::connect(addr, "localhost", pin, "producer", "tok-prod")
        .await
        .unwrap();
    assert!(matches!(
        prod.command(Command::SelectItem { item_id: 9999 }).await.unwrap(),
        ServerMessage::Denied {
            reason: DenyReason::BadRequest,
            ..
        }
    ));

    prod.close().await.ok();
    asst.close().await.ok();
}
