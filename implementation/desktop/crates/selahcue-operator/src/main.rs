//! SelahCue operator shell (Tauri desktop UI).
//!
//! The webview renders the service plan and control buttons; each button calls a
//! `#[tauri::command]` that drives a [`Backend`] and returns the fresh [`OperatorView`]
//! so the UI re-renders from one round trip (ADR-0003).
//!
//! The backend is chosen at startup:
//! - **Remote** — if a running SelahCue output window advertised a local endpoint, the
//!   shell connects to it over the pinned-TLS control link and drives the **on-screen
//!   audience output** (a `RemoteOperator`, the same path the mobile client will use).
//! - **Local** — otherwise it drives an in-process demo controller so the UI is still
//!   useful stand-alone.
//!
//! Run on a desktop with the Tauri toolchain: `cargo run` (from this crate). Start the
//! output window first (`cargo run -p selahcue-desktop`) to drive the real output.

#![forbid(unsafe_code)]
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use selahcue_app::{LiveController, OperatorShell, OperatorView, RemoteOperator};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::CertPin;
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tauri::{Manager, State};

/// Where the operator commands are dispatched: a remote host output window, or an
/// in-process demo controller.
enum Backend {
    // Boxed: a RemoteOperator (TLS WebSocket client + buffers) is much larger than the
    // Arc-sized local shell, so box it to keep the enum small.
    Remote(Box<tokio::sync::Mutex<RemoteOperator>>),
    Local(OperatorShell),
}

impl Backend {
    async fn view(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.view().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.view()),
        }
    }
    async fn next(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.next().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.next()),
        }
    }
    async fn previous(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.previous().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.previous()),
        }
    }
    async fn go_live(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.go_live().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.go_live()),
        }
    }
    async fn clear(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.clear().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.clear()),
        }
    }
    async fn blackout(&self, on: bool) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.blackout(on).await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.blackout(on)),
        }
    }
    async fn select(&self, item_id: u64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.select(item_id).await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.select(item_id)),
        }
    }
    async fn start_timer(&self, seconds: u32) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.start_timer(seconds).await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.start_timer(seconds)),
        }
    }
    async fn stop_timer(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.stop_timer().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.stop_timer()),
        }
    }
}

struct AppState {
    backend: Backend,
}

#[tauri::command]
async fn view(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.view().await
}
#[tauri::command]
async fn next(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.next().await
}
#[tauri::command]
async fn previous(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.previous().await
}
#[tauri::command]
async fn go_live(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.go_live().await
}
#[tauri::command]
async fn clear(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.clear().await
}
#[tauri::command]
async fn blackout(on: bool, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.blackout(on).await
}
#[tauri::command]
async fn select(item_id: u64, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.select(item_id).await
}
#[tauri::command]
async fn start_timer(seconds: u32, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.start_timer(seconds).await
}
#[tauri::command]
async fn stop_timer(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.stop_timer().await
}

/// The local endpoint descriptor an output window writes so its operator shell can
/// auto-discover it (loopback-only convenience; real pairing is QR + host confirmation).
#[derive(serde::Deserialize)]
struct Endpoint {
    addr: String,
    pin: String,
    device: String,
    token: String,
}

fn read_endpoint() -> Option<Endpoint> {
    let path = std::env::temp_dir().join("selahcue-operator-endpoint.json");
    let data = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&data).ok()
}

async fn connect_remote(ep: &Endpoint) -> Result<RemoteOperator, String> {
    let addr: SocketAddr = ep.addr.parse().map_err(|_| format!("bad addr: {}", ep.addr))?;
    let pin = CertPin::from_hex(&ep.pin).ok_or_else(|| "bad pin".to_string())?;
    RemoteOperator::connect(addr, "localhost", pin, &ep.device, &ep.token)
        .await
        .map_err(|e| e.to_string())
}

/// Try to attach to a running output window; fall back to a stand-alone demo controller.
async fn build_backend() -> Backend {
    match read_endpoint() {
        Some(ep) => match connect_remote(&ep).await {
            Ok(remote) => {
                eprintln!("SelahCue operator: connected to output window at {}", ep.addr);
                Backend::Remote(Box::new(tokio::sync::Mutex::new(remote)))
            }
            Err(e) => {
                eprintln!("SelahCue operator: could not connect to output window ({e}); running the stand-alone demo.");
                Backend::Local(demo_shell())
            }
        },
        None => {
            eprintln!("SelahCue operator: no running output window found; running the stand-alone demo. Start `cargo run -p selahcue-desktop` first to drive the real output.");
            Backend::Local(demo_shell())
        }
    }
}

/// A demo service plan for the stand-alone (no output window) case.
fn demo_shell() -> OperatorShell {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    plan.add_item(ItemKind::Song, "Closing Song");
    let controller = Arc::new(Mutex::new(LiveController::new(plan, 1920, 1080, Theme::dark())));
    OperatorShell::new(controller)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Connect on the Tauri runtime so the client is bound to the same reactor the
            // async commands run on.
            let backend = tauri::async_runtime::block_on(build_backend());
            app.manage(AppState { backend });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            view, next, previous, go_live, clear, blackout, select, start_timer, stop_timer
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
