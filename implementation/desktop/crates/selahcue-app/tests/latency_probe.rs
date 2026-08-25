//! Latency probe for the operator→output scripture path (owner defect: "select a
//! scripture … takes a couple of seconds to show in the output window").
//!
//! Measures each hop of the production path headlessly, at the HOST's real output
//! dimensions (1920×1080, matching selahcue-desktop's OUTPUT_W/H):
//!
//!   parse → bundle lookup (cold/warm) → compose+stage (LiveController::apply)
//!   → wire round trip (pinned-TLS loopback, real ControlServer)
//!   → GetOperatorState read-back → console-thumbnail read (GetConsoleThumbnails)
//!   → contention (a stage queued behind an in-flight thumbnail fetch).
//!
//! Run with timings printed:
//!   cargo test -p selahcue-app --features server --test latency_probe -- --nocapture
//!   cargo test -p selahcue-app --features server --release --test latency_probe -- --nocapture

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use selahcue_app::{handler_for, LiveController, RemoteOperator};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::Command;
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{CertPin, ControlServer, Role, SelfSigned};
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;

/// The host output surface (selahcue-desktop OUTPUT_W/OUTPUT_H).
const W: u32 = 1920;
const H: u32 = 1080;

fn ms(d: Duration) -> f64 {
    d.as_secs_f64() * 1e3
}

fn controller() -> Arc<Mutex<LiveController>> {
    let mut plan = ServicePlan::new("Sunday");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    Arc::new(Mutex::new(LiveController::new(plan, W, H, Theme::dark())))
}

async fn serve(c: Arc<Mutex<LiveController>>) -> (SocketAddr, CertPin) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        reg.redeem("p", DeviceId("op".into()), SessionToken::new("tok"), now)
            .unwrap();
    }
    let server = Arc::new(ControlServer::new(&identity, registry, handler_for(c)).unwrap());
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let _ = server.run(listener).await;
    });
    (addr, pin)
}

/// Hop 3+5 in isolation (no wire): parse, bundle lookup, and the synchronous
/// compose inside `LiveController::apply(StageScripture)` at 1920×1080.
#[test]
fn probe_in_process_breakdown() {
    // Hop 3a: reference parse.
    let t0 = Instant::now();
    let parsed = selahcue_core::scripture::parse_one("John 3:16").unwrap();
    let t_parse = t0.elapsed();

    // Hop 3b: bundle lookup — cold (first touch gunzips + indexes the translation).
    let t = selahcue_scripture::Translation::default();
    let t0 = Instant::now();
    let v = selahcue_scripture::verses_in(t, &parsed);
    let t_cold = t0.elapsed();
    assert!(!v.is_empty());

    // Hop 3b': warm lookup.
    let t0 = Instant::now();
    let v = selahcue_scripture::verses_in(t, &parsed);
    let t_warm = t0.elapsed();
    assert!(!v.is_empty());

    // Hop 5: apply(StageScripture) — lookup + synchronous 1920×1080 compose.
    let c = controller();
    let mut c = c.lock().unwrap();
    let refs = ["John 3:16", "Ps 23:1", "Rom 8:28", "Gen 1:1", "Isa 40:31"];
    let mut worst = Duration::ZERO;
    let mut total = Duration::ZERO;
    for (i, r) in refs.iter().cycle().take(20).enumerate() {
        let t0 = Instant::now();
        c.apply(&Command::StageScripture {
            reference: (*r).into(),
            translation: None,
        });
        let dt = t0.elapsed();
        total += dt;
        if dt > worst {
            worst = dt;
        }
        if i == 0 {
            println!("apply(StageScripture) first:      {:8.2} ms", ms(dt));
        }
    }
    let avg = total / 20;

    // Follow (stage + go-live = two composes) once a scripture is live.
    c.apply(&Command::StageScripture {
        reference: "John 3:16".into(),
        translation: None,
    });
    c.apply(&Command::GoLive);
    let t0 = Instant::now();
    c.apply(&Command::FollowScripture {
        reference: "John 3:17".into(),
        translation: None,
    });
    let t_follow = t0.elapsed();

    // The operator-view read-back that follows every command (act() → GetOperatorState).
    let t0 = Instant::now();
    let reply = c.apply(&Command::GetOperatorState);
    let t_view = t0.elapsed();
    let view_bytes = match reply {
        selahcue_app::ControllerReply::Message(m) => serde_json::to_vec(&m).unwrap().len(),
        _ => 0,
    };

    // The console-monitor read (webview render_console → GetConsoleThumbnails 480×270).
    let t0 = Instant::now();
    let reply = c.apply(&Command::GetConsoleThumbnails {
        max_w: 480,
        max_h: 270,
    });
    let t_thumb = t0.elapsed();
    let thumb_bytes = match reply {
        selahcue_app::ControllerReply::Message(m) => serde_json::to_vec(&m).unwrap().len(),
        _ => 0,
    };

    println!("parse_one:                        {:8.3} ms", ms(t_parse));
    println!("verses_in cold (bundle load):     {:8.2} ms", ms(t_cold));
    println!("verses_in warm:                   {:8.3} ms", ms(t_warm));
    println!("apply(StageScripture) avg of 20:  {:8.2} ms", ms(avg));
    println!("apply(StageScripture) worst:      {:8.2} ms", ms(worst));
    println!("apply(FollowScripture, 2 comps):  {:8.2} ms", ms(t_follow));
    println!(
        "apply(GetOperatorState):          {:8.2} ms  ({} bytes JSON)",
        ms(t_view),
        view_bytes
    );
    println!(
        "apply(GetConsoleThumbnails 480):  {:8.2} ms  ({} bytes JSON)",
        ms(t_thumb),
        thumb_bytes
    );
}

/// Hops 4+5 over the real pinned-TLS loopback: what the operator shell actually
/// waits on for one verse selection, plus the console-thumbnail read and the
/// contention case (a selection queued behind an in-flight thumbnail fetch).
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn probe_wire_breakdown() {
    let c = controller();
    let (addr, pin) = serve(c).await;

    let t0 = Instant::now();
    let mut op = RemoteOperator::connect(addr, "localhost", pin, "op", "tok")
        .await
        .unwrap();
    let t_connect = t0.elapsed();

    // Cold: first scripture command (host pays the bundle load inside apply).
    let t0 = Instant::now();
    op.stage_scripture("John 3:16", None).await.unwrap();
    let t_first = t0.elapsed();

    // Warm round trips (command + state read-back, exactly what the shell awaits).
    let refs = ["John 3:16", "Ps 23:1", "Rom 8:28", "Gen 1:1", "Isa 40:31"];
    let mut samples: Vec<Duration> = Vec::new();
    for r in refs.iter().cycle().take(20) {
        let t0 = Instant::now();
        op.stage_scripture(r, None).await.unwrap();
        samples.push(t0.elapsed());
    }
    samples.sort();
    let p50 = samples[samples.len() / 2];
    let max = *samples.last().unwrap();

    // The console-monitor fetch the webview issues after every state change.
    let t0 = Instant::now();
    let (pv, lv) = op.console_thumbnails(480, 270).await.unwrap();
    let t_thumb = t0.elapsed();
    assert!(pv.is_some() && lv.is_some());

    // Contention: a verse selection queued behind an in-flight thumbnail fetch on
    // the same connection (the webview's render_console vs the next click).
    let t0 = Instant::now();
    let _ = op.console_thumbnails(480, 270).await.unwrap();
    op.stage_scripture("Ps 23:1", None).await.unwrap();
    let t_contended = t0.elapsed();

    println!("connect (TCP+TLS+WS+auth):        {:8.2} ms", ms(t_connect));
    println!("stage_scripture first (cold):     {:8.2} ms", ms(t_first));
    println!("stage_scripture warm p50:         {:8.2} ms", ms(p50));
    println!("stage_scripture warm max:         {:8.2} ms", ms(max));
    println!("console_thumbnails 480×270:       {:8.2} ms", ms(t_thumb));
    println!(
        "thumb then stage (queued):        {:8.2} ms",
        ms(t_contended)
    );
}

/// The live-service condition: on-device STT feeds transcript FINALS through the same
/// path while the operator selects verses. Measures the ingest cost (fuzzy quote match
/// under the controller lock) and a stage_scripture issued mid-stream.
#[test]
fn probe_ingest_in_process() {
    let sermon = [
        "for god so loved the world that he gave his one and only son",
        "that whoever believes in him shall not perish but have eternal life",
        "and we know that in all things god works for the good of those who love him",
        "the lord is my shepherd i shall not want he makes me lie down in green pastures",
        "trust in the lord with all your heart and lean not on your own understanding",
        "come to me all you who are weary and burdened and i will give you rest",
    ];
    let c = controller();
    let mut c = c.lock().unwrap();

    // Cold: the first final builds the fuzzy matcher's inverted index.
    let t0 = Instant::now();
    c.apply(&Command::IngestTranscript {
        text: sermon[0].into(),
        start_ms: Some(0),
        end_ms: Some(4_000),
        is_final: true,
    });
    let t_cold = t0.elapsed();

    // Warm finals (each runs match_quote_scored over the 3-segment window).
    let mut worst = Duration::ZERO;
    let mut total = Duration::ZERO;
    for (i, s) in sermon.iter().cycle().take(20).enumerate() {
        let t0 = Instant::now();
        c.apply(&Command::IngestTranscript {
            text: (*s).into(),
            start_ms: Some((i as u64) * 4_000),
            end_ms: Some((i as u64 + 1) * 4_000),
            is_final: true,
        });
        let dt = t0.elapsed();
        total += dt;
        if dt > worst {
            worst = dt;
        }
    }

    // Interims are documented-cheap; confirm.
    let t0 = Instant::now();
    c.apply(&Command::IngestTranscript {
        text: "and we know that in all things".into(),
        start_ms: Some(0),
        end_ms: Some(1_000),
        is_final: false,
    });
    let t_interim = t0.elapsed();

    println!("ingest final cold (index build):  {:8.2} ms", ms(t_cold));
    println!(
        "ingest final warm avg of 20:      {:8.2} ms",
        ms(total / 20)
    );
    println!("ingest final warm worst:          {:8.2} ms", ms(worst));
    println!("ingest interim:                   {:8.3} ms", ms(t_interim));
}
