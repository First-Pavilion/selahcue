//! SelahCue — end-to-end foundation demo (batches 7a–7e).
//!
//! Run:  cargo run -p selahcue-lan --example demo --features server
//!
//! Exercises the whole headless engine live: scripture parsing, the service-plan
//! model, the monotonic timer, persistence (save + reload + integrity), and a real
//! certificate-pinned TLS control session with device auth + RBAC enforcement.

#![allow(clippy::unwrap_used)]

use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_core::scripture;
use selahcue_core::timer::Timer;
use selahcue_data::Database;
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlClient, ControlServer, Role, SelfSigned};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex;

fn section(title: &str) {
    println!("\n\x1b[1;36m== {title} ==\x1b[0m");
}
fn ok(msg: impl AsRef<str>) {
    println!("  \x1b[32m✓\x1b[0m {}", msg.as_ref());
}
fn pretty(m: &ServerMessage) -> String {
    match m {
        ServerMessage::Ack { request_id } => format!("Ack(#{request_id})"),
        ServerMessage::Denied { reason, .. } => format!("Denied({reason:?})"),
        ServerMessage::State { blackout, .. } => format!("State(blackout={blackout})"),
        other => format!("{other:?}"),
    }
}

#[tokio::main]
async fn main() {
    println!("\x1b[1m╔══════════════════════════════════════════╗\x1b[0m");
    println!("\x1b[1m║   SelahCue — Foundation Demo (7a–7e)      ║\x1b[0m");
    println!("\x1b[1m╚══════════════════════════════════════════╝\x1b[0m");

    // 1) Scripture parsing (FR-027)
    section("Scripture reference parser");
    for input in ["Rom 8:28-30", "Ps 23", "John 3:16; 1 Cor 13:4", "Xyzzy 9:9"] {
        let refs = scripture::parse(input);
        if refs.is_empty() {
            ok(format!("{input:<24} → rejected cleanly (no panic)"));
        } else {
            let shown: Vec<String> = refs.iter().map(|r| r.to_string()).collect();
            ok(format!("{input:<24} → {}", shown.join(" | ")));
        }
    }

    // 2) Service plan (FR-001/002)
    section("Service plan");
    let mut plan = ServicePlan::new("Sunday Morning");
    plan.add_item(ItemKind::Announcement, "Welcome");
    let song = plan.add_item(ItemKind::Song, "Great Are You Lord");
    plan.add_item(ItemKind::Scripture, "Romans 8:28-30");
    plan.add_item(ItemKind::Section, "Sermon");
    plan.get_mut(song).unwrap().planned_secs = Some(300);
    ok(format!("plan '{}' — {} items:", plan.name, plan.len()));
    for (i, item) in plan.items().iter().enumerate() {
        println!(
            "      {}. [{:<12}] {}",
            i + 1,
            item.kind.as_tag(),
            item.title
        );
    }
    ok(format!("planned total: {}s", plan.planned_total_secs()));

    // 3) Timer (FR-054/065)
    section("Monotonic timer");
    let base = Instant::now();
    let mut timer = Timer::count_down(Duration::from_secs(300));
    timer.start(base);
    ok(format!(
        "5:00 countdown → at +60s remaining {:?}",
        timer.remaining(base + Duration::from_secs(60)).unwrap()
    ));
    ok(format!(
        "at +300s TIME UP = {} · at +315s overrun {:?}",
        timer.is_time_up(base + Duration::from_secs(300)),
        timer.overrun(base + Duration::from_secs(315))
    ));

    // 4) Persistence (FR-079)
    section("Persistence — save, reload, integrity");
    let db = Database::open_in_memory().unwrap();
    let id = selahcue_data::plan_repo::insert(&db, &plan).unwrap();
    db.integrity_check().unwrap();
    let reloaded = selahcue_data::plan_repo::load(&db, id).unwrap();
    ok(format!(
        "saved plan #{id} → reloaded '{}' ({} items) — round-trip {}",
        reloaded.name,
        reloaded.len(),
        if reloaded == plan {
            "OK ✓"
        } else {
            "MISMATCH ✗"
        }
    ));
    ok("integrity_check → ok");

    // 5) LAN control over pinned TLS (FR-118/119/120)
    section("LAN control over pinned TLS + RBAC");
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    println!("      operator cert pin (the QR payload a phone scans):");
    println!("      \x1b[33m{}\x1b[0m", pin.to_hex());

    let registry = Arc::new(Mutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("111", Role::Producer, now, Duration::from_secs(300));
        reg.redeem(
            "111",
            DeviceId("ipad-producer".into()),
            SessionToken::new("tok-prod"),
            now,
        )
        .unwrap();
        reg.offer_pairing("222", Role::Assistant, now, Duration::from_secs(300));
        reg.redeem(
            "222",
            DeviceId("phone-assistant".into()),
            SessionToken::new("tok-asst"),
            now,
        )
        .unwrap();
    }
    ok("paired 2 devices: ipad-producer (Producer), phone-assistant (Assistant)");

    let handler: Handler = Arc::new(|_role, cmd| match cmd {
        Command::GetState => Reply::Message(Box::new(ServerMessage::State {
            live_item: None,
            blackout: false,
        })),
        _ => Reply::Ack,
    });
    let server = Arc::new(ControlServer::new(&identity, registry.clone(), handler).unwrap());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let running = server.clone();
    tokio::spawn(async move {
        let _ = running.run(listener).await;
    });
    ok(format!("operator server listening on {addr}"));

    // An attacker who doesn't have the pinned cert is blocked at the TLS layer.
    let attacker_pin = CertPin::of_cert_der(b"an attacker's certificate");
    let blocked =
        ControlClient::connect(addr, "localhost", attacker_pin, "ipad-producer", "tok-prod")
            .await
            .is_err();
    ok(format!(
        "wrong-pin client blocked at TLS handshake: {blocked}"
    ));

    // Producer: full live control.
    let mut producer = ControlClient::connect(addr, "localhost", pin, "ipad-producer", "tok-prod")
        .await
        .unwrap();
    let r = producer.command(Command::GoLive).await.unwrap();
    ok(format!("Producer  GoLive → {}", pretty(&r)));

    // Assistant: prepares/searches but cannot push live — RBAC denies GoLive.
    let mut assistant =
        ControlClient::connect(addr, "localhost", pin, "phone-assistant", "tok-asst")
            .await
            .unwrap();
    let r = assistant.command(Command::GoLive).await.unwrap();
    ok(format!(
        "Assistant GoLive → {}   ← RBAC blocks live control",
        pretty(&r)
    ));
    let r = assistant.command(Command::Next).await.unwrap();
    ok(format!("Assistant Next   → {}", pretty(&r)));

    producer.close().await.ok();
    assistant.close().await.ok();

    println!("\n\x1b[1;32m✓ All foundation pieces ran end-to-end.\x1b[0m");
    println!(
        "  The visual UI (19 screens) lives in Figma: file SYQn5hFY8YVQKm3c6rw0eJ.\n\
         \x20 The on-screen operator app is the upcoming walking-skeleton batch."
    );
}
