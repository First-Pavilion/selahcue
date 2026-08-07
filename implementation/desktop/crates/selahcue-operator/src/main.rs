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
use selahcue_lan::protocol::ScaleFit;
use selahcue_lan::CertPin;
use selahcue_present::{FrameBuffer, Theme};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tauri::{Manager, State};

/// On-device STT capture worker driving the live transcript (feature `stt`; OFF by default).
#[cfg(feature = "stt")]
mod listening;

/// The Presentation & Media editing workspace (Design 2.0, node 329:124) — the authored deck +
/// media library the console edits, behind the deck/media Tauri commands.
mod deck_workspace;
use deck_workspace::DeckWorkspace;

/// The persisted Presentations Library (design 86ajvpngr) — the set of saved decks + best-effort
/// SQLite persistence behind the deck_list/new/open/rename/duplicate/delete commands.
mod deck_library;
use deck_library::DeckLibrary;
use selahcue_present::DeckId;

/// Where the operator commands are dispatched: a remote host output window, or an
/// in-process demo controller.
enum Backend {
    // Boxed: a RemoteOperator (TLS WebSocket client + buffers) is much larger than the
    // Arc-sized local shell, so box it to keep the enum small.
    Remote(Box<tokio::sync::Mutex<RemoteOperator>>),
    Local(OperatorShell),
}

impl Backend {
    /// Whether a REAL audience output window is connected (a Remote backend), as opposed to the
    /// stand-alone/demo local backend where a present succeeds silently with no physical output.
    fn is_remote(&self) -> bool {
        matches!(self, Backend::Remote(_))
    }

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
    /// Present a Design 2.0 authored deck slide on the audience output (the deck editor's
    /// "Present"). `slide_json`/`theme_json` are the serialized `AuthoredSlide` + `Theme` the
    /// canvas preview composed; the host composes them with the same compositor as plan content.
    async fn present_authored_slide(
        &self,
        slide_json: String,
        theme_json: String,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .present_authored_slide(slide_json, theme_json)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.present_authored_slide(&slide_json, &theme_json)),
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
    async fn set_item_theme(
        &self,
        item_id: u64,
        theme: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_item_theme(item_id, theme)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_item_theme(item_id, theme)),
        }
    }
    async fn save_theme(&self, name: String, theme_json: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .save_theme(&name, &theme_json)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.save_theme(&name, &theme_json)),
        }
    }
    async fn delete_theme(&self, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .delete_theme(&name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.delete_theme(&name)),
        }
    }
    async fn set_screen_theme(&self, screen: String, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_screen_theme(&screen, &name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_screen_theme(&screen, &name)),
        }
    }
    async fn set_screen_enabled(
        &self,
        screen: String,
        enabled: bool,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_screen_enabled(&screen, enabled)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_screen_enabled(&screen, enabled)),
        }
    }
    async fn add_screen(&self, role: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .add_screen(&role)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.add_screen(&role)),
        }
    }
    async fn remove_screen(&self, screen: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .remove_screen(&screen)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.remove_screen(&screen)),
        }
    }
    async fn set_output_orientation(
        &self,
        screen: String,
        quarter_turns: u8,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_orientation(&screen, quarter_turns)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_orientation(&screen, quarter_turns)),
        }
    }
    async fn set_output_scale_fit(
        &self,
        screen: String,
        fit: ScaleFit,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_scale_fit(&screen, fit)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_scale_fit(&screen, fit)),
        }
    }
    async fn set_output_mirror(&self, screen: String, on: bool) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_mirror(&screen, on)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_mirror(&screen, on)),
        }
    }
    async fn set_output_delay(&self, screen: String, ms: u32) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_delay(&screen, ms)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_delay(&screen, ms)),
        }
    }
    async fn set_output_frame_rate(
        &self,
        screen: String,
        fps: u16,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_frame_rate(&screen, fps)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_frame_rate(&screen, fps)),
        }
    }
    async fn set_output_safe_area(&self, screen: String, on: bool) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_output_safe_area(&screen, on)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_output_safe_area(&screen, on)),
        }
    }
    async fn set_screen_layer_visible(
        &self,
        screen: String,
        layer: String,
        visible: bool,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_screen_layer_visible(&screen, &layer, visible)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_screen_layer_visible(&screen, &layer, visible)),
        }
    }
    async fn set_ndi_output(
        &self,
        screen: String,
        name: String,
        enabled: bool,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_ndi_output(&screen, &name, enabled)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_ndi_output(&screen, &name, enabled)),
        }
    }
    async fn set_stage_template(&self, template: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_stage_template(&template)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_stage_template(&template)),
        }
    }
    async fn set_stage_message(&self, text: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_stage_message(&text)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_stage_message(&text)),
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
    async fn pause_timer(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .pause_timer()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.pause_timer()),
        }
    }
    async fn resume_timer(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .resume_timer()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.resume_timer()),
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
    async fn follow_scripture(
        &self,
        reference: String,
        translation: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .follow_scripture(&reference, translation.as_deref())
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.follow_scripture(&reference, translation.as_deref())),
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
    async fn ingest_transcript(
        &self,
        text: String,
        start_ms: u64,
        end_ms: u64,
        is_final: bool,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .ingest_transcript(&text, start_ms, end_ms, is_final)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.ingest_transcript(&text, start_ms, end_ms, is_final)),
        }
    }
    async fn approve_detection(&self, detection_id: u64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .approve_detection(detection_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.approve_detection(detection_id)),
        }
    }
    async fn dismiss_detection(&self, detection_id: u64) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .dismiss_detection(detection_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.dismiss_detection(detection_id)),
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
    /// The Presentation & Media workspace (operator-local — its `DeckView` is separate from the
    /// LAN-shared `OperatorView`, so the pinned cross-language wire fixtures stay untouched).
    deck: Mutex<DeckWorkspace>,
    /// The persisted Presentations Library — the set of saved decks the `deck` workspace opens
    /// one of at a time. Locked AFTER `deck` wherever both are held (consistent order, no deadlock).
    library: Mutex<DeckLibrary>,
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
#[tauri::command]
async fn set_item_theme(
    item_id: u64,
    theme: Option<String>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_item_theme(item_id, theme).await
}
#[tauri::command]
async fn save_theme(
    name: String,
    theme_json: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.save_theme(name, theme_json).await
}
#[tauri::command]
async fn delete_theme(name: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.delete_theme(name).await
}
#[tauri::command]
async fn set_screen_theme(
    screen: String,
    name: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_screen_theme(screen, name).await
}
#[tauri::command]
async fn set_screen_enabled(
    screen: String,
    enabled: bool,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_screen_enabled(screen, enabled).await
}
#[tauri::command]
async fn add_screen(role: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.add_screen(role).await
}
#[tauri::command]
async fn remove_screen(screen: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.remove_screen(screen).await
}
#[tauri::command]
async fn set_output_orientation(
    screen: String,
    quarter_turns: u8,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state
        .backend
        .set_output_orientation(screen, quarter_turns)
        .await
}
#[tauri::command]
async fn set_output_scale_fit(
    screen: String,
    fit: ScaleFit,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_output_scale_fit(screen, fit).await
}
#[tauri::command]
async fn set_output_mirror(
    screen: String,
    on: bool,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_output_mirror(screen, on).await
}
#[tauri::command]
async fn set_output_delay(
    screen: String,
    ms: u32,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_output_delay(screen, ms).await
}
#[tauri::command]
async fn set_output_frame_rate(
    screen: String,
    fps: u16,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_output_frame_rate(screen, fps).await
}
#[tauri::command]
async fn set_output_safe_area(
    screen: String,
    on: bool,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_output_safe_area(screen, on).await
}
#[tauri::command]
async fn set_screen_layer_visible(
    screen: String,
    layer: String,
    visible: bool,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state
        .backend
        .set_screen_layer_visible(screen, layer, visible)
        .await
}
#[tauri::command]
async fn set_ndi_output(
    screen: String,
    name: String,
    enabled: bool,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_ndi_output(screen, name, enabled).await
}
#[tauri::command]
async fn set_stage_template(
    template: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_stage_template(template).await
}
#[tauri::command]
async fn set_stage_message(
    text: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_stage_message(text).await
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
/// The fonts installed on THIS machine (sorted, deduped, bounded) for the Theme Designer
/// font picker (86ajq6fxt). A pure, host-local enumeration (like `builtin_themes`); the
/// selected family rides in the theme JSON, so there is NO new wire command.
#[tauri::command]
fn system_fonts() -> Vec<String> {
    selahcue_present::system_font_families()
}
/// Open the native OS file picker for a PNG image and return the chosen absolute path
/// (86ajq6j4p / 86ajq6j49 frontend). Host-local + user-initiated; the path becomes an
/// `Element::Image` source (validated by `MediaRef` host-side). FR-138 import-path
/// canonicalization / media-root confinement remains the deferred hardening. `None` = the
/// user cancelled. **Must be `async`** so Tauri spawns it OFF the main thread: `blocking_pick_file`
/// enqueues the dialog onto the main event loop and waits on it, so running it ON the main
/// thread would deadlock/freeze the whole operator (the plugin documents this footgun).
#[tauri::command]
async fn pick_image(app: tauri::AppHandle) -> Option<String> {
    use tauri_plugin_dialog::DialogExt;
    app.dialog()
        .file()
        .add_filter("Images (PNG)", &["png"])
        .blocking_pick_file()
        .and_then(|fp| fp.into_path().ok())
        .map(|p| p.to_string_lossy().into_owned())
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

/// Render the CURRENT Preview + Live outputs to base64 RGBA8 thumbnails for the console
/// monitors (86ajtwq28) — the true composited pixels the audience preview and live show
/// (including blackout / timer / the live scene). A **read-only** readback: it drives no
/// command, so it never changes what is on air. `max_w`/`max_h` (the panel's pixel size)
/// are CLAMPED to a bounded ceiling so a hostile/huge size can't over-allocate or bloat the
/// IPC payload. A REMOTE host returns `{available:false}` (its pixels are not on the control
/// wire — a streaming seam), and the UI keeps its accessible text fallback.
///
/// **Async** (not sync) — matching every other command in this shell: a sync `#[tauri::command]`
/// that takes `State` ran on the WebView event thread and did not surface its result, so the
/// panels stayed on the text fallback (owner QA, refine #7-fix); an async command runs off that
/// thread and resolves normally. The body is still synchronous + read-only (`console_thumbnails`
/// returns owned frames — no lock is held across an await, because there is no await).
#[tauri::command]
async fn render_console(
    max_w: u32,
    max_h: u32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    // Bound the thumbnail (the true output is up to 1920×1080) so the IPC payload + the
    // allocation stay small regardless of the requested panel size — 480×270 matches the
    // Theme Designer preview and is ample for a console monitor.
    let max_w = max_w.clamp(1, 480);
    let max_h = max_h.clamp(1, 270);
    // A local FrameBuffer readback → the webview JSON shape.
    let fb_json = |fb: &FrameBuffer| {
        serde_json::json!({
            "w": fb.width(),
            "h": fb.height(),
            "rgba": base64::engine::general_purpose::STANDARD.encode(fb.bytes()),
        })
    };
    // A host ThumbView (already base64) → the same shape; `None` (no host frame) → JSON null.
    let thumb_json = |t: Option<selahcue_lan::protocol::ThumbView>| match t {
        Some(t) => serde_json::json!({ "w": t.w, "h": t.h, "rgba": t.rgba }),
        None => serde_json::Value::Null,
    };
    match &state.backend {
        // Standalone (demo) — the operator has the composited frames locally.
        Backend::Local(s) => {
            let (preview, live) = s.console_thumbnails(max_w, max_h);
            Ok(
                serde_json::json!({ "available": true, "preview": fb_json(&preview), "live": fb_json(&live) }),
            )
        }
        // Driving the output app over the loopback link (86ajtwq28): the composited pixels
        // live in the OUTPUT-APP process, so ask it for the Preview/Live thumbnails over the
        // same link (a read — never changes what is on air). A transport error (e.g. a
        // pre-feature host that can't parse the command) → `available:false` → text fallback.
        Backend::Remote(m) => match m.lock().await.console_thumbnails(max_w, max_h).await {
            Ok((preview, live)) => Ok(serde_json::json!({
                "available": true,
                "preview": thumb_json(preview),
                "live": thumb_json(live),
            })),
            Err(e) => Ok(serde_json::json!({ "available": false, "error": e.to_string() })),
        },
    }
}

/// Fetch one Audience `screen`'s LIVE content rendered under ITS per-screen theme, as a
/// downscaled thumbnail (86ajq321k) — for the operator Screens-page preview, so each screen's
/// design is visible (the secondaries have no physical output yet). Read-only, same shape +
/// off-thread handling as `render_console`. `available:false` on a transport error.
#[tauri::command]
async fn render_screen(
    screen: String,
    max_w: u32,
    max_h: u32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    let max_w = max_w.clamp(1, 480);
    let max_h = max_h.clamp(1, 270);
    let fb_json = |fb: &FrameBuffer| {
        serde_json::json!({
            "w": fb.width(),
            "h": fb.height(),
            "rgba": base64::engine::general_purpose::STANDARD.encode(fb.bytes()),
        })
    };
    match &state.backend {
        Backend::Local(s) => match s.screen_frame(&screen, max_w, max_h) {
            Some(fb) => Ok(serde_json::json!({ "available": true, "frame": fb_json(&fb) })),
            None => Ok(serde_json::json!({ "available": true, "frame": serde_json::Value::Null })),
        },
        Backend::Remote(m) => match m.lock().await.screen_frame(&screen, max_w, max_h).await {
            Ok(Some(t)) => Ok(serde_json::json!({
                "available": true,
                "frame": { "w": t.w, "h": t.h, "rgba": t.rgba },
            })),
            Ok(None) => {
                Ok(serde_json::json!({ "available": true, "frame": serde_json::Value::Null }))
            }
            Err(e) => Ok(serde_json::json!({ "available": false, "error": e.to_string() })),
        },
    }
}

// --- Presentation & Media (Design 2.0, node 329:124) --------------------------------------
//
// The deck/media commands drive the operator-local [`DeckWorkspace`] and return a `DeckView`
// JSON snapshot (NOT the LAN-shared `OperatorView`, so the pinned cross-language wire fixtures
// stay untouched). All are `async` — a sync `#[tauri::command]` that takes `State` runs on the
// WebView thread and does not surface its result (same reason as `render_console`); the body is
// synchronous + holds the std `Mutex` only within the (await-free) call, so the future is `Send`.

/// Lock the deck workspace, apply an edit, autosave the open deck into the library, and return the
/// fresh `DeckView`. The autosave is a best-effort single-row upsert (idempotent when unchanged);
/// a poisoned/absent library never blocks or fails the edit (persistence is best-effort). Lock
/// order is ALWAYS deck→library.
fn with_deck(
    state: &State<'_, AppState>,
    f: impl FnOnce(&mut DeckWorkspace),
) -> Result<serde_json::Value, String> {
    let mut ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
    f(&mut ws);
    if let Ok(mut lib) = state.library.lock() {
        lib.store(ws.open_deck());
    }
    Ok(ws.view())
}

/// Open the operator's best-effort deck DB at `<app_data_dir>/selahcue.db3`. Returns `None` on ANY
/// failure (missing dir, permissions, a DB the default build can't read — e.g. an encrypted file),
/// so the caller falls back to an in-memory library. (Aligning this path with the desktop bin's
/// `data_dir()` for a single shared DB is a documented follow-up.)
fn open_deck_db(app: &tauri::App) -> Option<selahcue_data::Database> {
    use tauri::Manager;
    let dir = app.path().app_data_dir().ok()?;
    std::fs::create_dir_all(&dir).ok()?;
    selahcue_data::Database::open(dir.join("selahcue.db3")).ok()
}

/// Lock the deck workspace AND the library (in that order — consistent, no deadlock) and run `f`,
/// returning its JSON. Used by the library commands that must coordinate the open editor with the
/// saved set (open/switch/rename/delete).
fn with_deck_and_library(
    state: &State<'_, AppState>,
    f: impl FnOnce(&mut DeckWorkspace, &mut DeckLibrary) -> serde_json::Value,
) -> Result<serde_json::Value, String> {
    let mut ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
    let mut lib = state
        .library
        .lock()
        .map_err(|e| format!("library lock: {e}"))?;
    Ok(f(&mut ws, &mut lib))
}

/// The `LibraryView` JSON the Presentations Library renders from: the decks (id · name · slide
/// count), which one is open, and whether edits are persisted (in-memory fallback → false).
fn library_view(lib: &DeckLibrary, open_id: DeckId) -> serde_json::Value {
    let decks: Vec<serde_json::Value> = lib
        .list()
        .into_iter()
        .map(|m| serde_json::json!({ "id": m.id.0, "name": m.name, "slides": m.slides }))
        .collect();
    serde_json::json!({ "decks": decks, "open": open_id.0, "persistent": lib.is_persistent() })
}

/// The Presentations Library list (id · name · slide count · which is open · persistence state).
#[tauri::command]
async fn deck_list(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| library_view(lib, ws.open_deck().id()))
}

/// Create a new blank presentation (unique id + name) and OPEN it in the editor → returns the
/// `DeckView` so the surface switches to the new deck.
#[tauri::command]
async fn deck_new(name: String, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        let deck = lib.create(&name);
        ws.load_deck(deck);
        ws.view()
    })
}

/// Open an existing presentation by id → saves the outgoing deck, loads the target, returns the
/// `DeckView`. A no-op (returns the current deck) if `id` is unknown.
#[tauri::command]
async fn deck_open(id: u64, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        if ws.open_deck().id() == DeckId(id) {
            return ws.view(); // already open — don't reset the editing session (undo/selection)
        }
        lib.store(ws.open_deck()); // persist the deck we are leaving
        if let Some(deck) = lib.get(DeckId(id)) {
            ws.load_deck(deck);
        }
        ws.view()
    })
}

/// Rename a presentation (unique-enforced) → returns the `LibraryView`. If the renamed deck is the
/// open one, the editor's name is updated in place too.
#[tauri::command]
async fn deck_rename(
    id: u64,
    name: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        if let Some(applied) = lib.rename(DeckId(id), &name) {
            if ws.open_deck().id() == DeckId(id) {
                ws.set_open_name(applied);
            }
        }
        library_view(lib, ws.open_deck().id())
    })
}

/// Duplicate a presentation into an independent "<name> copy" → returns the `LibraryView` (the copy
/// is added to the library; the editor stays on the current deck).
#[tauri::command]
async fn deck_duplicate(id: u64, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        lib.duplicate(DeckId(id));
        library_view(lib, ws.open_deck().id())
    })
}

/// Delete a presentation → returns the `LibraryView`. If the deleted deck was open, the editor
/// switches to another deck (or a fresh blank one if the library is now empty — never left with no
/// open deck).
#[tauri::command]
async fn deck_delete(id: u64, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        let was_open = ws.open_deck().id() == DeckId(id);
        lib.delete(DeckId(id));
        if was_open {
            let next = lib.list().first().and_then(|m| lib.get(m.id));
            let deck = next.unwrap_or_else(|| lib.create("Untitled presentation"));
            ws.load_deck(deck);
        }
        library_view(lib, ws.open_deck().id())
    })
}

#[tauri::command]
async fn deck_view(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    // Read-only — lock the deck and return its view WITHOUT the library autosave (a read must not
    // write). Mirrors `render_deck_slide`'s single-lock read path.
    let ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
    Ok(ws.view())
}
#[tauri::command]
async fn deck_add_slide(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.add_slide())
}
#[tauri::command]
async fn deck_remove_slide(
    id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.remove_slide(id))
}
#[tauri::command]
async fn deck_duplicate_slide(
    id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.duplicate_slide(id))
}
#[tauri::command]
async fn deck_reorder_slide(
    from: usize,
    to: usize,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.reorder_slide(from, to))
}
#[tauri::command]
async fn deck_select_slide(
    id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.select_slide(id))
}
#[tauri::command]
async fn deck_add_element(
    kind: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.add_element(&kind))
}
#[tauri::command]
async fn deck_add_image_element(
    media_id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.add_image_element(media_id))
}
#[tauri::command]
async fn deck_remove_element(
    index: usize,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.remove_element(index))
}
#[tauri::command]
async fn deck_select_element(
    index: Option<usize>,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.select_element(index))
}
#[tauri::command]
async fn deck_move_element(
    index: usize,
    x: u16,
    y: u16,
    w: u16,
    h: u16,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |ws| ws.move_element(index, x, y, w, h))
}
#[tauri::command]
async fn deck_set_element_z(
    index: usize,
    z: i16,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.set_element_z(index, z))
}
#[tauri::command]
async fn deck_reorder_elements(
    order: Vec<usize>,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.reorder_elements(order))
}
#[tauri::command]
async fn deck_toggle_element_visible(
    index: usize,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.toggle_element_visible(index))
}
#[tauri::command]
async fn deck_set_element_text(
    index: usize,
    text: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.set_element_text(index, text))
}
#[tauri::command]
async fn deck_update_element(
    index: usize,
    patch: serde_json::Value,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.update_element(index, patch))
}
#[tauri::command]
async fn deck_replace_element_image(
    index: usize,
    media_id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.replace_element_image(index, media_id))
}
#[tauri::command]
async fn deck_set_notes(
    notes: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.set_notes(notes))
}
#[tauri::command]
async fn deck_set_transition(
    transition: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.set_transition(&transition))
}
#[tauri::command]
async fn deck_set_auto_advance(
    secs: Option<u32>,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.set_auto_advance(secs))
}
#[tauri::command]
async fn deck_undo(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.undo())
}
#[tauri::command]
async fn deck_redo(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.redo())
}
/// **Present** the selected deck slide (Design 2.0). Marks it live in the editor (FR-012
/// Preview→Live annotation) AND routes the composed slide to the native audience output over the
/// LAN control link — the fix for "clicking Present does nothing on the output".
#[tauri::command]
async fn deck_go_live(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    // Capture the editor view + the (slide, theme) payload under the deck/library locks, then
    // drop them BEFORE the async backend call (they are std Mutexes).
    let (view, payload) = {
        let mut ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
        ws.go_live();
        if let Ok(mut lib) = state.library.lock() {
            lib.store(ws.open_deck());
        }
        (ws.view(), ws.present_payload())
    };
    // Route the composed slide to the audience output (same compositor as the canvas preview). A
    // transport failure surfaces as the command error so the operator learns the output wasn't
    // reached; the local live annotation already succeeded regardless.
    if let Some((slide_json, theme_json)) = payload {
        state
            .backend
            .present_authored_slide(slide_json, theme_json)
            .await?;
    }
    Ok(view)
}
/// Advance the LIVE deck slide by `delta` (−1 previous / +1 next), clamped to the deck ends, and
/// present it to the audience output — atomically, under a single deck-lock acquisition (no
/// select-then-present race). Drives the presentation grid's ◀ ▶ transport and live-mode arrows.
#[tauri::command]
async fn deck_go_live_delta(
    delta: i32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let (view, payload) = {
        let mut ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
        ws.go_live_delta(delta);
        if let Ok(mut lib) = state.library.lock() {
            lib.store(ws.open_deck());
        }
        (ws.view(), ws.present_payload())
    };
    if let Some((slide_json, theme_json)) = payload {
        state
            .backend
            .present_authored_slide(slide_json, theme_json)
            .await?;
    }
    Ok(view)
}
#[tauri::command]
async fn deck_remove_media(
    id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck(&state, |w| w.remove_media(id))
}

/// Import an image into the media library via the native file picker, recording its real byte
/// size. Video/audio disk import (and on-output playback) is a deferred affordance (ADR-0020).
#[tauri::command]
async fn deck_import_image(
    app: tauri::AppHandle,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    use tauri_plugin_dialog::DialogExt;
    let picked = app
        .dialog()
        .file()
        .add_filter("Images", &["png", "jpg", "jpeg"])
        .blocking_pick_file()
        .and_then(|fp| fp.into_path().ok());
    with_deck(&state, |w| {
        if let Some(path) = picked {
            let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
            w.import_media(
                path.to_string_lossy().into_owned(),
                "image",
                size,
                None,
                None,
                None,
            );
        }
    })
}

/// Compose the selected (or `id`) slide to base64 RGBA8 for the slide-canvas preview — the same
/// native compositor as the audience output (read-only; never changes what is on air). Bounded.
#[tauri::command]
async fn render_deck_slide(
    id: Option<u64>,
    max_w: u32,
    max_h: u32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    let ws = state.deck.lock().map_err(|e| format!("deck lock: {e}"))?;
    match ws.render_slide(id, max_w, max_h) {
        Some(fb) => Ok(serde_json::json!({
            "available": true,
            "frame": {
                "w": fb.width(),
                "h": fb.height(),
                "rgba": base64::engine::general_purpose::STANDARD.encode(fb.bytes()),
            }
        })),
        None => Ok(serde_json::json!({ "available": true, "frame": serde_json::Value::Null })),
    }
}

#[tauri::command]
async fn blackout(on: bool, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.blackout(on).await
}
/// Whether a real audience output window is connected. The presentation grid uses this to be
/// HONEST: with no output it shows "Preview only — no audience output" instead of a true LIVE ring.
#[tauri::command]
async fn output_connected(state: State<'_, AppState>) -> Result<bool, String> {
    Ok(state.backend.is_remote())
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
async fn pause_timer(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.pause_timer().await
}
#[tauri::command]
async fn resume_timer(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.resume_timer().await
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
/// Stage a verse in Preview and — only when a scripture is already live — advance Live to it
/// (86ajtwq2b, refine #8: scrolling verses follows the audience once a scripture is live).
#[tauri::command]
async fn follow_scripture(
    reference: String,
    translation: Option<String>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.follow_scripture(reference, translation).await
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
/// Feed one live-transcript segment (R3). The default STT provider is operator/host
/// injected text; this is the webview's inject channel and the same path a real
/// on-device engine would drive. Runs scripture detection and returns the fresh view.
#[tauri::command]
async fn ingest_transcript(
    text: String,
    start_ms: u64,
    end_ms: u64,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    // A directly-injected line is a finalised segment (interims come from the STT worker).
    state
        .backend
        .ingest_transcript(text, start_ms, end_ms, true)
        .await
}
/// Approve a queued scripture detection (R4): stage its verse in Preview.
#[tauri::command]
async fn approve_detection(
    detection_id: u64,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.approve_detection(detection_id).await
}
/// Dismiss a queued scripture detection without staging it.
#[tauri::command]
async fn dismiss_detection(
    detection_id: u64,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.dismiss_detection(detection_id).await
}

// --- Live-transcript source: on-device STT capture (feature `stt`) ------------------------
// "Start listening" drives real on-device transcription into the detection engine. It works
// whether or not an output window is open: the transcript is ingested through the backend's
// dual path (local in-process controller, or forwarded over the wire to a connected
// output-window host), so scripture detection populates the panels either way. Real audio
// runs only in a build with `--features stt` (native whisper toolchain + model); otherwise
// the commands still exist and return an honest "not in this build" error — the webview
// surfaces it and never shows a fabricated transcript.

/// Start on-device transcription into the live transcript.
#[cfg(feature = "stt")]
#[tauri::command]
async fn start_listening(app: tauri::AppHandle) -> Result<(), String> {
    // The worker (its own thread) loads the model + opens the mic and reports readiness; we
    // await that here without blocking the executor. On failure, tear the worker back down so
    // the UI is not left in a phantom "listening" state.
    match listening::start(app).await {
        Ok(Ok(())) => Ok(()),
        Ok(Err(e)) => {
            listening::stop();
            Err(e)
        }
        Err(_) => {
            listening::stop();
            Err("on-device STT worker aborted before it started".to_string())
        }
    }
}

/// Stop on-device transcription.
#[cfg(feature = "stt")]
#[tauri::command]
async fn stop_listening() -> Result<(), String> {
    listening::stop();
    Ok(())
}

/// Honest fallback when the operator was not built with on-device STT.
#[cfg(not(feature = "stt"))]
#[tauri::command]
async fn start_listening() -> Result<(), String> {
    Err(
        "This build does not include on-device speech-to-text. Rebuild the operator with \
         `--features stt` on a machine with the whisper toolchain and a model."
            .to_string(),
    )
}

#[cfg(not(feature = "stt"))]
#[tauri::command]
async fn stop_listening() -> Result<(), String> {
    Ok(())
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
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Connect on the Tauri runtime so the client is bound to the same reactor the
            // async commands run on.
            let backend = tauri::async_runtime::block_on(build_backend());
            // Best-effort deck persistence: open `<app_data_dir>/selahcue.db3`; on ANY failure the
            // library runs in memory (editing never blocked). Load the saved library and open a
            // deck: the most-recent saved deck, or — on first run — adopt the demo deck so the
            // editor still opens onto content and the library isn't empty.
            let library = DeckLibrary::load(open_deck_db(app));
            let mut ws = DeckWorkspace::demo();
            let mut library = library;
            if library.is_empty() {
                let seeded = library.adopt(ws.open_deck().clone());
                ws.load_deck(seeded);
            } else if let Some(first) = library.list().first().and_then(|m| library.get(m.id)) {
                ws.load_deck(first);
            }
            app.manage(AppState {
                backend,
                deck: Mutex::new(ws),
                library: Mutex::new(library),
            });
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
            pause_timer,
            resume_timer,
            add_item,
            remove_item,
            move_item,
            rename_item,
            stage_scripture,
            follow_scripture,
            scripture_search,
            get_chapter,
            ingest_transcript,
            approve_detection,
            dismiss_detection,
            start_listening,
            stop_listening,
            identify_outputs,
            assign_output,
            set_theme,
            set_custom_theme,
            set_item_theme,
            save_theme,
            delete_theme,
            set_screen_theme,
            set_screen_enabled,
            add_screen,
            remove_screen,
            set_output_orientation,
            set_output_scale_fit,
            set_output_mirror,
            set_output_delay,
            set_output_frame_rate,
            set_output_safe_area,
            set_screen_layer_visible,
            set_ndi_output,
            set_stage_template,
            set_stage_message,
            preview_theme,
            render_console,
            render_screen,
            builtin_themes,
            system_fonts,
            pick_image,
            deck_view,
            deck_list,
            deck_new,
            deck_open,
            deck_rename,
            deck_duplicate,
            deck_delete,
            deck_add_slide,
            deck_remove_slide,
            deck_duplicate_slide,
            deck_reorder_slide,
            deck_select_slide,
            deck_add_element,
            deck_add_image_element,
            deck_remove_element,
            deck_select_element,
            deck_move_element,
            deck_set_element_z,
            deck_reorder_elements,
            deck_toggle_element_visible,
            deck_set_element_text,
            deck_update_element,
            deck_replace_element_image,
            deck_set_notes,
            deck_set_transition,
            deck_set_auto_advance,
            deck_undo,
            deck_redo,
            deck_go_live,
            deck_go_live_delta,
            deck_remove_media,
            deck_import_image,
            render_deck_slide,
            output_connected
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
