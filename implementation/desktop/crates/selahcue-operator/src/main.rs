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
    async fn set_theme(&self, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_theme(&name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_theme(&name)),
        }
    }
    async fn set_custom_theme(&self, theme_json: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_custom_theme(&theme_json)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_custom_theme(&theme_json)),
        }
    }
    async fn select(&self, item_id: u64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .select(item_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.select(item_id)),
        }
    }
    async fn start_timer(&self, seconds: u32) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .start_timer(seconds)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.start_timer(seconds)),
        }
    }
    async fn stop_timer(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.stop_timer().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.stop_timer()),
        }
    }
    async fn adjust_timer(&self, delta_secs: i64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .adjust_timer(delta_secs)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.adjust_timer(delta_secs)),
        }
    }
    async fn add_item(
        &self,
        kind: String,
        title: String,
        content: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .add_item(&kind, &title, content.as_deref())
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.add_item(&kind, &title, content.as_deref())),
        }
    }
    async fn remove_item(&self, item_id: u64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .remove_item(item_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.remove_item(item_id)),
        }
    }
    async fn move_item(&self, item_id: u64, to: u32) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .move_item(item_id, to)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.move_item(item_id, to)),
        }
    }
    async fn rename_item(&self, item_id: u64, title: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .rename_item(item_id, &title)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.rename_item(item_id, &title)),
        }
    }
    async fn stage_scripture(
        &self,
        reference: String,
        translation: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .stage_scripture(&reference, translation.as_deref())
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.stage_scripture(&reference, translation.as_deref())),
        }
    }
    async fn scripture_search(
        &self,
        query: String,
        translation: Option<String>,
    ) -> Result<Vec<selahcue_lan::protocol::ScriptureHitView>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .scripture_search(&query, translation.as_deref())
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.scripture_search(&query, translation.as_deref())),
        }
    }
    async fn identify_outputs(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .identify_outputs()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.identify_outputs()),
        }
    }
    async fn assign_output(
        &self,
        role: String,
        display_key: String,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .assign_output(&role, &display_key)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.assign_output(&role, &display_key)),
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
async fn set_theme(name: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.set_theme(name).await
}
#[tauri::command]
async fn set_custom_theme(
    theme_json: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_custom_theme(theme_json).await
}
/// The built-in themes as `[{ name, theme }]` (theme = the serialized `Theme`) so the
/// Theme Designer edits/previews the REAL built-ins from `theme.rs` — no hand-mirrored
/// JS copy to drift out of sync with the engine (e.g. the lower-third band).
#[tauri::command]
fn builtin_themes() -> Vec<serde_json::Value> {
    selahcue_present::Theme::BUILTIN_NAMES
        .iter()
        .filter_map(|name| {
            let theme = selahcue_present::Theme::builtin(name)?;
            Some(serde_json::json!({ "name": name, "theme": serde_json::to_value(theme).ok()? }))
        })
        .collect()
}
/// Render a Theme-Designer theme as a sample slide and return it as base64 RGBA8
/// (+ dimensions) — the webview draws it to a <canvas> via ImageData for an ACCURATE
/// preview (same compositor as the audience output). A pure function of the theme;
/// no host round-trip. Malformed theme JSON is reported as an error.
#[tauri::command]
fn preview_theme(theme_json: String) -> Result<serde_json::Value, String> {
    use base64::Engine;
    let theme: selahcue_present::Theme =
        serde_json::from_str(&theme_json).map_err(|e| format!("invalid theme: {e}"))?;
    let (w, h) = (480u32, 270u32);
    let fb = selahcue_present::render_sample(&theme, w, h);
    let rgba = base64::engine::general_purpose::STANDARD.encode(fb.bytes());
    Ok(serde_json::json!({ "w": w, "h": h, "rgba": rgba }))
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
#[tauri::command]
async fn adjust_timer(delta_secs: i64, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.adjust_timer(delta_secs).await
}
#[tauri::command]
async fn add_item(
    kind: String,
    title: String,
    content: Option<String>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.add_item(kind, title, content).await
}
#[tauri::command]
async fn remove_item(item_id: u64, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.remove_item(item_id).await
}
#[tauri::command]
async fn move_item(
    item_id: u64,
    to: u32,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.move_item(item_id, to).await
}
#[tauri::command]
async fn rename_item(
    item_id: u64,
    title: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.rename_item(item_id, title).await
}
#[tauri::command]
async fn stage_scripture(
    reference: String,
    translation: Option<String>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.stage_scripture(reference, translation).await
}

/// One chapter for the browser (local bundle — identical text on host and
/// shell). `translation` is a bundled code; omitted = the KJV default.
#[derive(serde::Serialize)]
struct ChapterView {
    book_name: String,
    chapter: u16,
    reference: String,
    translation: String,
    verses: Vec<(u16, String)>,
    prev: Option<String>,
    next: Option<String>,
    translations: Vec<String>,
    /// The verse selection parsed from the query ("gen 1 5" / "Gen 1:5" /
    /// "Gen 1:1-3") — the browser lands/stages from THIS, never from regex
    /// guessing on the raw string (owner bug: "2 cor 4 5" landed on v1).
    verse_start: Option<u16>,
    verse_end: Option<u16>,
}

#[tauri::command]
fn get_chapter(reference: String, translation: Option<String>) -> Result<ChapterView, String> {
    let t = match translation.as_deref() {
        None => selahcue_scripture::Translation::default(),
        Some(code) => selahcue_scripture::Translation::from_code(code)
            .ok_or_else(|| format!("unknown translation: {code}"))?,
    };
    let parsed = selahcue_core::scripture::parse_one(&reference)
        .map_err(|_| format!("not a reference: {reference}"))?;
    let ch = selahcue_scripture::chapter_in(t, &parsed)
        .ok_or_else(|| format!("no such chapter: {reference}"))?;
    Ok(ChapterView {
        reference: format!("{} {}", ch.book_name, ch.chapter),
        book_name: ch.book_name,
        chapter: ch.chapter,
        translation: t.code().to_string(),
        verses: ch.verses,
        prev: selahcue_scripture::adjacent_chapter_in(t, &parsed, false),
        next: selahcue_scripture::adjacent_chapter_in(t, &parsed, true),
        translations: selahcue_scripture::Translation::ALL
            .iter()
            .map(|t| t.code().to_string())
            .collect(),
        verse_start: parsed.verses.map(|r| r.start),
        verse_end: parsed.verses.map(|r| r.end),
    })
}
#[tauri::command]
async fn scripture_search(
    query: String,
    translation: Option<String>,
    state: State<'_, AppState>,
) -> Result<Vec<selahcue_lan::protocol::ScriptureHitView>, String> {
    state.backend.scripture_search(query, translation).await
}
#[tauri::command]
async fn identify_outputs(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.identify_outputs().await
}
#[tauri::command]
async fn assign_output(
    role: String,
    display_key: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.assign_output(role, display_key).await
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
    let addr: SocketAddr = ep
        .addr
        .parse()
        .map_err(|_| format!("bad addr: {}", ep.addr))?;
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
                eprintln!(
                    "SelahCue operator: connected to output window at {}",
                    ep.addr
                );
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
    let controller = Arc::new(Mutex::new(LiveController::new(
        plan,
        1920,
        1080,
        Theme::dark(),
    )));
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
            view,
            next,
            previous,
            go_live,
            clear,
            blackout,
            select,
            start_timer,
            stop_timer,
            adjust_timer,
            add_item,
            remove_item,
            move_item,
            rename_item,
            stage_scripture,
            scripture_search,
            get_chapter,
            identify_outputs,
            assign_output,
            set_theme,
            set_custom_theme,
            preview_theme,
            builtin_themes
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
