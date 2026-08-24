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
use selahcue_core::detector::{detector_state, DetectorSignals, DetectorState};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_lan::protocol::{ContentLinkView, ScaleFit};
use selahcue_lan::CertPin;
use selahcue_present::{FrameBuffer, Theme};
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use tauri::{Emitter, Manager, State};

/// Bring-up of the bundled native output window that sits beside the operator in a packaged
/// install (ADR-0002/0003: the audience compositor is a separate process, never the WebView).
mod autolaunch;

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
use selahcue_present::{DeckId, SlideId};

/// The app-owned media store (ADR-0024 decision 4): `<app_data>/media/`, per-import staging with
/// atomic commit, and the `media_repo` wiring that lets imported media survive a restart.
///
/// Declared here so it compiles and its tests run under the operator's `cargo test`. The import
/// COMMANDS that drive it are not written yet — see the handoff note in the build report — but
/// leaving the module undeclared would have meant shipping it uncompiled and unverified, which
/// is strictly worse than shipping it unused.
mod media_store;

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

    // --- Remote Control device management (86ajxer8n). Only a Remote backend has a host session
    //     registry; the stand-alone/demo Local backend has no controllers to manage. ---
    async fn remote_devices(&self) -> Result<RemoteDevicesReply, String> {
        match self {
            Backend::Remote(m) => {
                let (devices, pending) = m
                    .lock()
                    .await
                    .remote_devices()
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(RemoteDevicesReply { devices, pending })
            }
            Backend::Local(_) => Ok(RemoteDevicesReply::default()),
        }
    }
    async fn approve_pairing(
        &self,
        device_id: String,
        role: String,
    ) -> Result<RemoteDevicesReply, String> {
        match self {
            Backend::Remote(m) => {
                let (devices, pending) = m
                    .lock()
                    .await
                    .approve_pairing(&device_id, parse_role(&role)?)
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(RemoteDevicesReply { devices, pending })
            }
            Backend::Local(_) => Err(NO_HOST.into()),
        }
    }
    async fn deny_pairing(&self, device_id: String) -> Result<RemoteDevicesReply, String> {
        match self {
            Backend::Remote(m) => {
                let (devices, pending) = m
                    .lock()
                    .await
                    .deny_pairing(&device_id)
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(RemoteDevicesReply { devices, pending })
            }
            Backend::Local(_) => Err(NO_HOST.into()),
        }
    }
    async fn revoke_session(&self, device_id: String) -> Result<RemoteDevicesReply, String> {
        match self {
            Backend::Remote(m) => {
                let (devices, pending) = m
                    .lock()
                    .await
                    .revoke_session(&device_id)
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(RemoteDevicesReply { devices, pending })
            }
            Backend::Local(_) => Err(NO_HOST.into()),
        }
    }
    async fn set_session_role(
        &self,
        device_id: String,
        role: String,
    ) -> Result<RemoteDevicesReply, String> {
        match self {
            Backend::Remote(m) => {
                let (devices, pending) = m
                    .lock()
                    .await
                    .set_session_role(&device_id, parse_role(&role)?)
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(RemoteDevicesReply { devices, pending })
            }
            Backend::Local(_) => Err(NO_HOST.into()),
        }
    }
    async fn new_pairing_code(&self) -> Result<PairingCodeReply, String> {
        match self {
            Backend::Remote(m) => {
                let (code, fingerprint, expires_in_secs, uri) = m
                    .lock()
                    .await
                    .new_pairing_code()
                    .await
                    .map_err(|e| e.to_string())?;
                Ok(PairingCodeReply::new(
                    code,
                    fingerprint,
                    expires_in_secs,
                    uri,
                ))
            }
            Backend::Local(_) => Err(NO_HOST.into()),
        }
    }
    /// Present a Design 2.0 authored deck slide on the audience output (the deck editor's
    /// "Present"). `slide_json`/`theme_json` are the serialized `AuthoredSlide` + `Theme` the
    /// canvas preview composed; the host composes them with the same compositor as plan content.
    async fn present_authored_slide(
        &self,
        slide_json: String,
        theme_json: String,
        next_slide_json: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .present_authored_slide(slide_json, theme_json, next_slide_json)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => {
                Ok(s.present_authored_slide(&slide_json, &theme_json, next_slide_json.as_deref()))
            }
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
    async fn set_item_content(
        &self,
        item_id: u64,
        link: Option<ContentLinkView>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_item_content(item_id, link)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_item_content(item_id, link)),
        }
    }
    async fn set_item_owner(
        &self,
        item_id: u64,
        owner: Option<String>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_item_owner(item_id, owner)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_item_owner(item_id, owner)),
        }
    }
    async fn set_item_duration(
        &self,
        item_id: u64,
        secs: Option<u32>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .set_item_duration(item_id, secs)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.set_item_duration(item_id, secs)),
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
    async fn select_slide(&self, item_id: u64, slide_index: u32) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .select_slide(item_id, slide_index)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.select_slide(item_id, slide_index)),
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
    async fn plan_undo(&self) -> Result<OperatorView, String> {
        match self {
            // The host owns its own plan history; client-side plan undo is not carried over the
            // wire, so a Remote backend is a safe no-op that returns the current view.
            Backend::Remote(m) => m.lock().await.view().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.plan_undo()),
        }
    }
    async fn plan_redo(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m.lock().await.view().await.map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.plan_redo()),
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
    /// Providers & Privacy settings + consent (node 338:124). Offline-first defaults; the pure core
    /// owns the egress gate, so nothing here can silently enable cloud egress.
    providers: Mutex<selahcue_core::providers::ProvidersConfig>,
    /// Best-effort persistence connection for the providers config (`None` → in-memory only, like
    /// the deck library's fallback). A second connection to the same WAL DB is safe.
    providers_db: Option<Mutex<selahcue_data::Database>>,
    /// The SelahCue account/session token store (FR-134): OS keychain in a `cloud-live` build,
    /// in-memory otherwise. Never a user-pasted third-party key.
    secrets: Box<dyn selahcue_cloud::SecretStore + Send + Sync>,
}

/// Reply to the Remote Control device commands: the host's paired devices + pending requests.
#[derive(serde::Serialize, Default)]
struct RemoteDevicesReply {
    devices: Vec<selahcue_lan::protocol::RemoteDeviceView>,
    pending: Vec<selahcue_lan::protocol::RemotePendingView>,
}

/// Reply to `remote_new_code`: a fresh single-use pairing code + fingerprint, plus the REAL
/// scannable QR the webview paints (the `selahcue://pair?…` invite encoded with the same tested
/// encoder the native output window uses).
#[derive(serde::Serialize)]
struct PairingCodeReply {
    code: String,
    fingerprint: String,
    expires_in_secs: u64,
    /// The full `selahcue://pair?host=…&port=…&pin=…&code=…` invite (`None` if the host didn't
    /// supply its LAN endpoint — an older host, or one bound only to loopback).
    uri: Option<String>,
    /// The invite encoded as a QR module grid for the webview to paint (`None` when there is no
    /// `uri` to encode, or the invite is too long for a QR).
    qr: Option<QrModules>,
}

/// A QR code as a row-major `side × side` grid of dark-module flags — what the webview paints.
/// No quiet zone (the webview adds it). Produced by [`selahcue_present::qr_modules`].
#[derive(serde::Serialize)]
struct QrModules {
    side: usize,
    modules: Vec<bool>,
}

impl PairingCodeReply {
    /// Assemble the reply from the wire tuple, encoding the invite URI (if any) into QR modules.
    fn new(code: String, fingerprint: String, expires_in_secs: u64, uri: Option<String>) -> Self {
        let qr = uri
            .as_deref()
            .and_then(selahcue_present::qr_modules)
            .map(|(side, modules)| QrModules { side, modules });
        PairingCodeReply {
            code,
            fingerprint,
            expires_in_secs,
            uri,
            qr,
        }
    }
}

/// Shown when a device command is issued in stand-alone/demo mode (no host connected).
const NO_HOST: &str = "device management needs a connected output window";

/// Parse a wire role string (as the operator UI sends) into a [`selahcue_lan::Role`].
fn parse_role(s: &str) -> Result<selahcue_lan::Role, String> {
    match s {
        "operator" => Ok(selahcue_lan::Role::Operator),
        "producer" => Ok(selahcue_lan::Role::Producer),
        "assistant" => Ok(selahcue_lan::Role::Assistant),
        "viewer" => Ok(selahcue_lan::Role::Viewer),
        other => Err(format!("unknown role: {other}")),
    }
}

#[tauri::command]
async fn remote_snapshot(state: State<'_, AppState>) -> Result<RemoteDevicesReply, String> {
    state.backend.remote_devices().await
}
#[tauri::command]
async fn remote_approve(
    device_id: String,
    role: String,
    state: State<'_, AppState>,
) -> Result<RemoteDevicesReply, String> {
    state.backend.approve_pairing(device_id, role).await
}
#[tauri::command]
async fn remote_deny(
    device_id: String,
    state: State<'_, AppState>,
) -> Result<RemoteDevicesReply, String> {
    state.backend.deny_pairing(device_id).await
}
#[tauri::command]
async fn remote_revoke(
    device_id: String,
    state: State<'_, AppState>,
) -> Result<RemoteDevicesReply, String> {
    state.backend.revoke_session(device_id).await
}
#[tauri::command]
async fn remote_set_role(
    device_id: String,
    role: String,
    state: State<'_, AppState>,
) -> Result<RemoteDevicesReply, String> {
    state.backend.set_session_role(device_id, role).await
}
#[tauri::command]
async fn remote_new_code(state: State<'_, AppState>) -> Result<PairingCodeReply, String> {
    state.backend.new_pairing_code().await
}

/// Whether the operator is driving a REAL output window (the `Remote` backend) rather than the
/// stand-alone in-process demo (`Local`). The Pre-service Check reads this so it never reports
/// readiness — or a fabricated "network up" — when no output window is actually connected.
#[tauri::command]
fn host_connected(state: State<'_, AppState>) -> bool {
    state.backend.is_remote()
}

/// Reply to `disk_free`: free + total bytes on the volume backing the operator's **data dir** (the
/// same `<app_data_dir>` where the deck DB / autosave live — see `open_deck_db`), for the
/// Pre-service Check storage readiness. `available == 0` (the platform could not report) leaves the
/// UI to show an honest "couldn't read disk" state rather than a fabricated figure.
#[derive(serde::Serialize, Default)]
struct DiskFreeReply {
    available_bytes: u64,
    total_bytes: u64,
}

#[tauri::command]
fn disk_free(app: tauri::AppHandle) -> DiskFreeReply {
    use tauri::Manager;
    // Best-effort, read-only: measure the volume backing the data dir the deck DB uses, falling
    // back to the working dir if it isn't resolvable/created yet. `fs4` errors on platforms that
    // cannot report, surfaced as zeros (never a guessed value).
    let path = app
        .path()
        .app_data_dir()
        .ok()
        .filter(|p| p.exists())
        .or_else(|| std::env::current_dir().ok())
        .unwrap_or_else(|| std::path::PathBuf::from("."));
    DiskFreeReply {
        available_bytes: fs4::available_space(&path).unwrap_or(0),
        total_bytes: fs4::total_space(&path).unwrap_or(0),
    }
}

/// Reply to `stt_ready`: whether the on-device transcription model is present (ready to load) for
/// the Pre-service Check. A cheap presence+size probe (safe to poll); the full SHA-256 integrity
/// gate still runs when the model is actually loaded (FR-156 / ADR-0012).
#[derive(serde::Serialize, Default)]
struct SttReadyReply {
    ready: bool,
    /// `"ready"` | `"not_downloaded"` | `"size_mismatch"` | `"not_in_build"`.
    state: String,
    /// The selected model variant label (empty when STT is not compiled into this build).
    model: String,
    detail: String,
}

/// Report on-device STT readiness WITHOUT loading the native whisper context or opening audio:
/// resolve the SAME model + path the worker would use and check the file is present at the pinned
/// size. An explicit `SELAHCUE_STT_MODEL` override wins (mirrors `listening.rs`).
#[cfg(feature = "stt")]
#[tauri::command]
fn stt_ready() -> SttReadyReply {
    let selection = selahcue_stt::HardwareProbe::detect().select_model();
    let asset = selection.model.asset();
    let path = std::env::var_os("SELAHCUE_STT_MODEL")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| selahcue_stt::default_cache_dir().join(asset.file_name));
    let model = format!("{:?}", selection.model);
    match selahcue_stt::model_readiness(&path, asset.size_bytes) {
        selahcue_stt::ModelReadiness::Present => SttReadyReply {
            ready: true,
            state: "ready".into(),
            model,
            detail: format!("On-device model ready ({})", asset.file_name),
        },
        selahcue_stt::ModelReadiness::NotDownloaded => SttReadyReply {
            ready: false,
            state: "not_downloaded".into(),
            model,
            detail: "On-device model not downloaded yet".into(),
        },
        selahcue_stt::ModelReadiness::SizeMismatch => SttReadyReply {
            ready: false,
            state: "size_mismatch".into(),
            model,
            detail: "On-device model incomplete — it will re-download".into(),
        },
    }
}

/// STT is not compiled into this build — report an honest "not in this build" (never a guess),
/// which the Pre-service Check renders as a neutral "not checked" state.
#[cfg(not(feature = "stt"))]
#[tauri::command]
fn stt_ready() -> SttReadyReply {
    SttReadyReply {
        ready: false,
        state: "not_in_build".into(),
        model: String::new(),
        detail: "On-device transcription is not enabled in this build".into(),
    }
}

/// Reply to `audio_input`: the default microphone the on-device STT would capture from, for the
/// Pre-service Check AUDIO section. Queried WITHOUT opening a capture stream. Live signal levels
/// need a running capture (the `stt://level` event while listening), so this reports device
/// presence only — never a fabricated level.
#[derive(serde::Serialize, Default)]
struct AudioInputReply {
    /// An input device is present (and STT/capture is compiled into this build).
    available: bool,
    /// `"ok"` | `"no_device"` | `"not_in_build"`.
    state: String,
    /// Device name (empty when no device / not in this build).
    name: String,
    channels: Option<u16>,
    detail: String,
}

#[cfg(feature = "stt")]
#[tauri::command]
async fn audio_input() -> AudioInputReply {
    // `async` so Tauri runs the (blocking) cpal audio-HAL enumeration on its async runtime rather
    // than the UI/main thread — a slow HAL query never stalls the operator console.
    match selahcue_stt::audio::default_input_info() {
        Some(info) => {
            let ch = info
                .channels
                .map(|c| format!(" · {c} ch"))
                .unwrap_or_default();
            AudioInputReply {
                available: true,
                state: "ok".into(),
                detail: format!("{}{}", info.name, ch),
                name: info.name,
                channels: info.channels,
            }
        }
        None => AudioInputReply {
            available: false,
            state: "no_device".into(),
            name: String::new(),
            channels: None,
            detail: "No microphone / input device detected".into(),
        },
    }
}

/// STT/capture is not compiled into this build — report an honest "not in this build".
#[cfg(not(feature = "stt"))]
#[tauri::command]
async fn audio_input() -> AudioInputReply {
    AudioInputReply {
        available: false,
        state: "not_in_build".into(),
        name: String::new(),
        channels: None,
        detail: "Audio input check is not enabled in this build".into(),
    }
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
async fn set_item_content(
    item_id: u64,
    link: Option<ContentLinkView>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_item_content(item_id, link).await
}
#[tauri::command]
async fn set_item_owner(
    item_id: u64,
    owner: Option<String>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_item_owner(item_id, owner).await
}
#[tauri::command]
async fn set_item_duration(
    item_id: u64,
    secs: Option<u32>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.set_item_duration(item_id, secs).await
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
    // What an undo could actually put back. The trash is bounded, so this shrinks as deletes
    // age out — the UI must offer "Undo delete" from THIS list rather than assuming the last
    // delete is always restorable, or it will offer an undo that cannot work.
    let restorable: Vec<u64> = lib.restorable().into_iter().map(|id| id.0).collect();
    serde_json::json!({
        "decks": decks,
        "open": open_id.0,
        "persistent": lib.is_persistent(),
        "restorable": restorable,
    })
}

/// The Presentations Library list (id · name · slide count · which is open · persistence state).
#[tauri::command]
async fn deck_list(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| library_view(lib, ws.open_deck().id()))
}

/// Global presentation search (⌘/Ctrl+S): match `query` against deck NAMES and slide TEXT across
/// the whole library, returning at most 50 bounded hits — name matches before per-slide content
/// matches (see [`DeckLibrary::search`]). Reads the library only (never the open editor).
#[tauri::command]
async fn deck_search(
    query: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    with_deck_and_library(
        &state,
        |_ws, lib| serde_json::json!({ "hits": lib.search(&query, 50) }),
    )
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

/// Undo a presentation delete → returns the `LibraryView`.
///
/// Restores the deck's **real** content — slides, elements, theme, notes and transitions — from
/// the library's bounded in-memory trash. A client cannot do this itself: at delete time the
/// deck leaves the library and its persisted row is removed, so the most a client-side undo
/// could recreate is an empty deck of the same name, which misrepresents what was restored.
///
/// Rejected when the deck is no longer restorable — the trash is bounded, so an old delete may
/// have been evicted, and an unusually large deck may never have been retained at all. The
/// error is returned rather than silently no-op'ing so the UI can say why nothing happened.
///
/// The restored name is included because it can differ from the original: if the name was taken
/// while the deck sat in the trash it is uniquified, and the operator needs to know what their
/// presentation is now called.
#[tauri::command]
async fn deck_restore(id: u64, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    // `None` = the deck was not restorable, so nothing was touched. Decided by asking the
    // library BEFORE mutating, rather than inferring a refusal from the shape of the result.
    let outcome = with_deck_and_library(&state, |ws, lib| {
        if !lib.can_restore(DeckId(id)) {
            return serde_json::Value::Null;
        }
        match lib.restore(DeckId(id)) {
            Some(name) => {
                let mut view = library_view(lib, ws.open_deck().id());
                if let Some(obj) = view.as_object_mut() {
                    // The name can differ from the original if it was taken while the deck sat
                    // in the trash; the operator needs to be told what it is now called.
                    obj.insert("restored_name".into(), serde_json::Value::String(name));
                }
                view
            }
            None => serde_json::Value::Null,
        }
    })?;
    if outcome.is_null() {
        return Err("That presentation can no longer be restored.".to_string());
    }
    Ok(outcome)
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
    if let Some((slide_json, theme_json, next_slide_json)) = payload {
        state
            .backend
            .present_authored_slide(slide_json, theme_json, next_slide_json)
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
    if let Some((slide_json, theme_json, next_slide_json)) = payload {
        state
            .backend
            .present_authored_slide(slide_json, theme_json, next_slide_json)
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

/// List a plan-linked SAVED deck's slides for the Live Console slide picker (read-only bridge,
/// `LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §6). `available:false` when the deck id is unknown
/// (the linked deck was removed), so the picker shows its "presentation missing" state (FR-007).
/// Reads the deck library only — the open editor workspace is never touched.
#[tauri::command]
async fn plan_deck_slides(
    deck_id: u64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let lib = state
        .library
        .lock()
        .map_err(|e| format!("library lock: {e}"))?;
    match lib.slide_list(DeckId(deck_id)) {
        Some(slides) => Ok(serde_json::json!({
            "available": true,
            "slides": slides
                .iter()
                .map(|s| serde_json::json!({
                    "slide_id": s.id.0,
                    "label": s.label,
                    "has_notes": s.has_notes,
                }))
                .collect::<Vec<_>>(),
        })),
        None => Ok(serde_json::json!({ "available": false })),
    }
}

/// Render ONE slide of a plan-linked SAVED deck to bounded RGBA for the picker/preview (read-only;
/// the SAME compositor + `Theme::dark` preview the editor canvas uses, so a thumbnail matches).
/// `available:false` when the deck OR slide id is unknown. Off the editor workspace — it is never
/// loaded or mutated. Routing these pixels to the physical audience output is a separate seam
/// (Dep 2, ADR ~0022); this is Preview/thumbnail composition only.
#[tauri::command]
async fn render_plan_deck_slide(
    deck_id: u64,
    slide_id: u64,
    max_w: u32,
    max_h: u32,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    use base64::Engine;
    let lib = state
        .library
        .lock()
        .map_err(|e| format!("library lock: {e}"))?;
    match lib.render_slide(DeckId(deck_id), SlideId(slide_id), max_w, max_h) {
        Some(fb) => Ok(serde_json::json!({
            "available": true,
            "frame": {
                "w": fb.width(),
                "h": fb.height(),
                "rgba": base64::engine::general_purpose::STANDARD.encode(fb.bytes()),
            }
        })),
        None => Ok(serde_json::json!({ "available": false, "frame": serde_json::Value::Null })),
    }
}

/// Route ONE slide of a plan-linked SAVED deck to the LIVE audience output — the SAME authored-slide
/// present path the deck editor's `deck_go_live` uses, but for a plan-linked deck (the Live Console
/// slide picker's Go Live). Composes the slide operator-side (`present_payload`) and hands it to the
/// presenter via `present_authored_slide`; `render_console` then shows the real slide on the Live
/// panel + the physical audience output. `Err` when the deck/slide id is unknown. Returns the updated
/// OperatorView (its `live_authored_id` is the presented slide, driving the filmstrip LIVE marker).
#[tauri::command]
async fn present_plan_deck_slide(
    deck_id: u64,
    slide_id: u64,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    let payload = {
        let lib = state
            .library
            .lock()
            .map_err(|e| format!("library lock: {e}"))?;
        lib.present_payload(DeckId(deck_id), SlideId(slide_id))
    };
    match payload {
        Some((slide_json, theme_json, next_slide_json)) => {
            state
                .backend
                .present_authored_slide(slide_json, theme_json, next_slide_json)
                .await
        }
        None => Err("plan deck slide not found".into()),
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
/// Stage a specific within-item slide of a plan item in Preview — the Live Console slide picker
/// (`LIVE-CONSOLE-PRESENTATION-PLAYBACK-spec.md` §6). Preview only; Live is untouched (FR-012).
#[tauri::command]
async fn select_slide(
    item_id: u64,
    slide_index: u32,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.select_slide(item_id, slide_index).await
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
async fn plan_undo(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.plan_undo().await
}
#[tauri::command]
async fn plan_redo(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.plan_redo().await
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

/// Abort an in-flight model download (sets a flag the fetch loop polls; the partial `.part` file is
/// discarded, nothing is installed). Safe no-op when nothing is downloading.
#[cfg(feature = "stt")]
#[tauri::command]
async fn cancel_download() -> Result<(), String> {
    listening::cancel_download();
    Ok(())
}
#[cfg(not(feature = "stt"))]
#[tauri::command]
async fn cancel_download() -> Result<(), String> {
    Ok(())
}

/// What this build can observe about the detector.
///
/// The two arms are the entire build-configuration dependency; everything downstream of here
/// is the pure rule in `selahcue_core::detector`, which is compiled and tested unconditionally.
/// Splitting it this way is deliberate: this crate is excluded from the workspace AND its
/// `stt` feature is off in CI, so any judgement made here would be verified by nothing.
#[cfg(feature = "stt")]
fn detector_observations() -> (bool, Option<String>, Option<String>) {
    (
        listening::is_listening(),
        listening::last_failure(),
        listening::provider_label(),
    )
}

/// Without the `stt` feature there is no detector in this binary at all — so it is not idle,
/// not failed, and cannot be retried. Reporting anything else would be a fabrication.
#[cfg(not(feature = "stt"))]
fn detector_observations() -> (bool, Option<String>, Option<String>) {
    (false, None, None)
}

/// Whether a detector is compiled into this binary. A build constant, not a runtime condition.
const DETECTOR_COMPILED: bool = cfg!(feature = "stt");

/// The detector's current state, derived by the pure core rule.
fn current_detector_state() -> DetectorState {
    let (worker_running, last_failure, _) = detector_observations();
    detector_state(DetectorSignals {
        compiled: DETECTOR_COMPILED,
        worker_running,
        last_failure: last_failure.as_deref(),
    })
}

/// Reply to `detection_health`: enough for the console to tell a dead detector from a silent
/// room, and to know whether offering a retry would be honest.
#[derive(serde::Serialize)]
struct DetectionHealthReply {
    /// `"unsupported"` | `"idle"` | `"listening"` | `"unavailable"`.
    state: &'static str,
    /// The engine producing the transcript (FR-120 honest disclosure). `None` when nothing
    /// is listening — never a guessed or flattering name.
    provider: Option<String>,
    /// The retained terminal failure, when the detector is down. `None` otherwise.
    error: Option<String>,
    /// Whether a retry could actually change anything. Derived from the state's own
    /// permission rule, never set by hand, so it cannot disagree with `retry_detection`.
    can_retry: bool,
}

fn detection_health_reply() -> DetectionHealthReply {
    let state = current_detector_state();
    let (_, last_failure, provider) = detector_observations();
    DetectionHealthReply {
        state: state.tag(),
        provider,
        error: last_failure,
        can_retry: state.retry_request().is_some(),
    }
}

/// Detector liveness for the console's health UI.
///
/// This is what makes "a dead scripture detector and a silent room" render differently:
/// `listening` with no transcript is a quiet room, `unavailable` is a detector that died.
/// Silence alone is evidence of neither.
#[tauri::command]
fn detection_health() -> DetectionHealthReply {
    detection_health_reply()
}

/// Restart the detector after a failure.
///
/// Refused unless the current state can mint a `RetryRequest` — so in a build with no
/// detector the retry path is *unreachable*, not merely disabled. A control that cannot
/// possibly work is a fabrication of exactly the kind this work removes.
#[tauri::command]
async fn retry_detection(app: tauri::AppHandle) -> Result<DetectionHealthReply, String> {
    let state = current_detector_state();
    let Some(permit) = state.retry_request() else {
        return Err(match state {
            DetectorState::Unsupported => "This build does not include on-device \
                 speech-to-text, so there is nothing to retry."
                .to_string(),
            other => format!("Retry does not apply while detection is '{}'.", other.tag()),
        });
    };
    perform_retry(app, permit).await?;
    Ok(detection_health_reply())
}

/// The retry itself. Takes the permit so it cannot be called from a state that forbids it.
#[cfg(feature = "stt")]
async fn perform_retry(
    app: tauri::AppHandle,
    _permit: selahcue_core::detector::RetryRequest,
) -> Result<(), String> {
    // Tear down any half-dead worker first, so a retry is a clean restart rather than a
    // no-op against a wedged one.
    listening::stop();
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

/// Unreachable in this build: `RetryRequest` cannot be minted from `Unsupported`, which is
/// the only state a detector-less build can be in. Kept total rather than a panic so that a
/// future configuration change degrades to an honest refusal instead of crashing.
#[cfg(not(feature = "stt"))]
async fn perform_retry(
    _app: tauri::AppHandle,
    _permit: selahcue_core::detector::RetryRequest,
) -> Result<(), String> {
    Err("This build does not include on-device speech-to-text.".to_string())
}

/// Every translation the app knows, with availability — bundled ones are always available; a
/// downloadable one (e.g. YLT) is available only once its asset has been fetched. Feeds a future
/// translation-manager UI; the offline-download modal drives the actual fetch via `download_translation`.
#[tauri::command]
async fn list_translations() -> Result<serde_json::Value, String> {
    let items: Vec<serde_json::Value> = selahcue_scripture::Translation::ALL
        .iter()
        .map(|t| {
            serde_json::json!({
                "code": t.code(),
                "name": t.name(),
                "downloadable": t.is_downloadable(),
                "available": selahcue_scripture::is_available(*t),
            })
        })
        .collect();
    Ok(serde_json::json!({ "translations": items }))
}

/// Download a translation asset (by catalog id) on a worker thread, streaming `bible://phase`
/// events the offline-download modal renders (the SAME dialog the speech model uses). The catalog
/// URL/sha are owner-supplied; with the placeholder catalog this surfaces the honest failure states.
#[tauri::command]
async fn download_translation(id: String, app: tauri::AppHandle) -> Result<(), String> {
    use selahcue_scripture::download::{self, TranslationFetchError};
    let asset = download::catalog()
        .into_iter()
        .find(|a| a.id == id)
        .ok_or_else(|| format!("unknown translation '{id}'"))?;
    let name = asset.name.clone();
    let cache = download::default_cache_dir();
    tauri::async_runtime::spawn_blocking(move || {
        let res = download::fetch_translation(&asset, &cache, |done, total| {
            let pct = done.saturating_mul(100).checked_div(total).unwrap_or(0) as u8;
            let _ = app.emit(
                "bible://phase",
                serde_json::json!({"phase":"downloading","done":done,"total":total,"pct":pct,"name":name.clone(),"id":id.clone()}),
            );
        });
        let ev = match res {
            Ok(_) => serde_json::json!({"phase":"ready","name":name,"id":id}),
            Err(TranslationFetchError::Verify { .. })
            | Err(TranslationFetchError::BadExpectedHash) => {
                serde_json::json!({"phase":"failed","reason":"verify","message":"integrity check failed","resumable":false,"bytes_kept":0,"name":name,"id":id})
            }
            Err(TranslationFetchError::Network(m)) => {
                serde_json::json!({"phase":"failed","reason":"connect","message":m,"resumable":false,"bytes_kept":0,"name":name,"id":id})
            }
            Err(e @ TranslationFetchError::TooLarge { .. }) => {
                serde_json::json!({"phase":"failed","reason":"other","message":e.to_string(),"resumable":false,"bytes_kept":0,"name":name,"id":id})
            }
            Err(TranslationFetchError::Io(e)) => {
                serde_json::json!({"phase":"failed","reason":"other","message":e.to_string(),"resumable":false,"bytes_kept":0,"name":name,"id":id})
            }
        };
        let _ = app.emit("bible://phase", ev);
    });
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

/// The loopback endpoint descriptor path shared with the output window (both processes agree on
/// `temp_dir()/selahcue-operator-endpoint.json`).
fn endpoint_file_path() -> std::path::PathBuf {
    std::env::temp_dir().join("selahcue-operator-endpoint.json")
}

fn read_endpoint() -> Option<Endpoint> {
    let data = std::fs::read_to_string(endpoint_file_path()).ok()?;
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

// --- Providers & Privacy (Settings, Design 2.0 node 338:124) ---------------------------------
//
// Where transcription + AI sermon-notes run, and what (if anything) leaves the device
// (FR-131/132/134/135/137, NFR-018, CON-5). The desktop operator console IS the administrator
// surface — mobile controllers are role-gated separately via LAN RBAC — so consent changes made
// here are inherently admin-side (FR-137). The pure core owns the egress gate and the (key,value)
// mapping; this layer only persists best-effort and renders. Operator-local JSON replies only, so
// the pinned cross-language LAN wire fixtures stay untouched. All commands are `async` with
// synchronous, await-free bodies that hold the std `Mutex` briefly (same rule as the deck commands).

/// The keychain/secret-store credential name for the SelahCue account/session token (FR-134).
const ACCOUNT_TOKEN_NAME: &str = "account_token";

#[derive(serde::Serialize)]
struct TemplateOption {
    value: String,
    label: String,
}

#[derive(serde::Serialize)]
struct TranslationOption {
    code: String,
    name: String,
}

#[derive(serde::Serialize)]
struct IncludeView {
    prayer_points: bool,
    scripture_extraction: bool,
    social_excerpts: bool,
    chapter_markers: bool,
    notable_quotations: bool,
    short_summary: bool,
}

#[derive(serde::Serialize)]
struct QuotaView {
    used: u32,
    limit: u32,
    remaining: u32,
    resets_label: String,
}

/// The full Providers & Privacy panel state (node 338:124). `quota` is `None` until a live cloud
/// fetch returns one — never a fabricated figure (the server owns the count, and it does not exist
/// yet), matching the console's "no guessed numbers" convention.
#[derive(serde::Serialize)]
struct ProvidersView {
    transcription_mode: String,
    on_device: SttReadyReply,
    cloud_transcription_consent: bool,
    cloud_notes_consent: bool,
    offline_by_default: bool,
    any_cloud_enabled: bool,
    notes_template: String,
    notes_templates: Vec<TemplateOption>,
    preferred_translation: String,
    translations: Vec<TranslationOption>,
    include: IncludeView,
    /// `"available"` when a base URL + token are present, else `"not_configured"`.
    cloud_status: String,
    cloud_connected: bool,
    account_token_set: bool,
    quota: Option<QuotaView>,
}

fn providers_templates() -> Vec<TemplateOption> {
    selahcue_core::providers::NotesTemplate::ALL
        .iter()
        .map(|t| TemplateOption {
            value: t.as_str().to_string(),
            label: t.label().to_string(),
        })
        .collect()
}

fn providers_translations() -> Vec<TranslationOption> {
    selahcue_scripture::Translation::ALL
        .iter()
        .map(|t| TranslationOption {
            code: t.code().to_string(),
            name: t.name().to_string(),
        })
        .collect()
}

/// The configured SelahCue cloud base URL, or `None` (the honest default — the live service does
/// not exist). Read from the environment only in a `cloud-live` build.
#[cfg(feature = "cloud-live")]
fn cloud_base_url() -> Option<String> {
    std::env::var("SELAHCUE_CLOUD_URL")
        .ok()
        .filter(|s| !s.is_empty())
}
#[cfg(not(feature = "cloud-live"))]
fn cloud_base_url() -> Option<String> {
    None
}

fn providers_view_of(
    cfg: &selahcue_core::providers::ProvidersConfig,
    account_token_set: bool,
) -> ProvidersView {
    let cloud_connected = cloud_base_url().is_some() && account_token_set;
    let inc = cfg.settings.include;
    ProvidersView {
        transcription_mode: cfg.settings.transcription_mode.as_str().to_string(),
        on_device: stt_ready(),
        cloud_transcription_consent: cfg.consent.cloud_transcription,
        cloud_notes_consent: cfg.consent.cloud_notes,
        offline_by_default: true,
        any_cloud_enabled: cfg.consent.any_cloud_enabled(),
        notes_template: cfg.settings.notes_template.as_str().to_string(),
        notes_templates: providers_templates(),
        preferred_translation: cfg.settings.preferred_translation.clone(),
        translations: providers_translations(),
        include: IncludeView {
            prayer_points: inc.prayer_points,
            scripture_extraction: inc.scripture_extraction,
            social_excerpts: inc.social_excerpts,
            chapter_markers: inc.chapter_markers,
            notable_quotations: inc.notable_quotations,
            short_summary: inc.short_summary,
        },
        cloud_status: if cloud_connected {
            "available".to_string()
        } else {
            "not_configured".to_string()
        },
        cloud_connected,
        account_token_set,
        quota: None,
    }
}

fn account_token_is_set(state: &State<'_, AppState>) -> bool {
    state
        .secrets
        .get(ACCOUNT_TOKEN_NAME)
        .ok()
        .flatten()
        .map(|t| !t.is_empty())
        .unwrap_or(false)
}

/// Lock the providers config, apply an edit, persist best-effort, and return the fresh view.
/// Persistence failure never blocks the edit (mirrors the deck autosave).
fn with_providers(
    state: &State<'_, AppState>,
    f: impl FnOnce(&mut selahcue_core::providers::ProvidersConfig),
) -> Result<ProvidersView, String> {
    let mut cfg = state
        .providers
        .lock()
        .map_err(|e| format!("providers lock: {e}"))?;
    let before = cfg.clone();
    f(&mut cfg);
    // Persist only when the config actually changed — a read-only `providers_view` (fired on every
    // Settings open / resync) and the token commands (which mutate the keychain, not `cfg`) leave it
    // unchanged, so they no longer trigger a full DELETE+INSERT to the WAL DB on every call.
    if *cfg != before {
        if let Some(db) = &state.providers_db {
            if let Ok(db) = db.lock() {
                let _ = selahcue_data::providers_repo::save(&db, &cfg);
            }
        }
    }
    let token_set = account_token_is_set(state);
    Ok(providers_view_of(&cfg, token_set))
}

#[tauri::command]
async fn providers_view(state: State<'_, AppState>) -> Result<ProvidersView, String> {
    with_providers(&state, |_| {})
}

#[tauri::command]
async fn set_transcription_mode(
    mode: String,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    with_providers(&state, |cfg| {
        cfg.settings.transcription_mode = selahcue_core::providers::TranscriptionMode::parse(&mode)
    })
}

/// Set a per-provider cloud opt-in (`kind` = `"transcription"` | `"notes"`). This is the only path
/// that ungates cloud egress — it is the Administrator (desktop) surface (FR-132/137).
#[tauri::command]
async fn set_cloud_consent(
    kind: String,
    enabled: bool,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    with_providers(&state, |cfg| match kind.as_str() {
        "transcription" => cfg.consent.cloud_transcription = enabled,
        "notes" => cfg.consent.cloud_notes = enabled,
        _ => {}
    })
}

#[tauri::command]
async fn set_notes_template(
    template: String,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    with_providers(&state, |cfg| {
        cfg.settings.notes_template = selahcue_core::providers::NotesTemplate::parse(&template)
    })
}

/// Set the preferred Bible translation — validated against the INSTALLED set; an unknown code is
/// ignored (keeps the current value) rather than persisting a dangling choice.
#[tauri::command]
async fn set_preferred_translation(
    code: String,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    with_providers(&state, |cfg| {
        if selahcue_scripture::Translation::from_code(&code).is_some() {
            cfg.settings.preferred_translation = code.clone();
        }
    })
}

#[tauri::command]
async fn set_include_flag(
    name: String,
    enabled: bool,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    with_providers(&state, |cfg| {
        let i = &mut cfg.settings.include;
        match name.as_str() {
            "prayer_points" => i.prayer_points = enabled,
            "scripture_extraction" => i.scripture_extraction = enabled,
            "social_excerpts" => i.social_excerpts = enabled,
            "chapter_markers" => i.chapter_markers = enabled,
            "notable_quotations" => i.notable_quotations = enabled,
            "short_summary" => i.short_summary = enabled,
            _ => {}
        }
    })
}

/// Store the SelahCue account/session token in the OS secret store (FR-134). The token value is
/// never logged; only whether one is set is ever surfaced.
#[tauri::command]
async fn set_account_token(
    token: String,
    state: State<'_, AppState>,
) -> Result<ProvidersView, String> {
    let token = selahcue_cloud::Token::new(token);
    // An empty token means "no account" — purge rather than storing a blank entry that
    // `account_token_is_set` would then report as unset anyway.
    if token.is_empty() {
        state
            .secrets
            .remove(ACCOUNT_TOKEN_NAME)
            .map_err(|e| e.to_string())?;
    } else {
        state
            .secrets
            .set(ACCOUNT_TOKEN_NAME, &token)
            .map_err(|e| e.to_string())?;
    }
    with_providers(&state, |_| {})
}

/// Purge the stored account token ("remove key" — FR-134).
#[tauri::command]
async fn clear_account_token(state: State<'_, AppState>) -> Result<ProvidersView, String> {
    state
        .secrets
        .remove(ACCOUNT_TOKEN_NAME)
        .map_err(|e| e.to_string())?;
    with_providers(&state, |_| {})
}

/// Map a [`selahcue_core::providers::NoteError`] to a stable, secret-free error code for the UI.
fn note_error_code(e: &selahcue_core::providers::NoteError) -> &'static str {
    use selahcue_core::providers::NoteError::*;
    match e {
        ConsentRequired => "consent_required",
        NotConfigured => "not_configured",
        QuotaExceeded => "quota_exceeded",
        Transport(_) => "transport",
        Malformed(_) => "malformed",
    }
}

fn draft_json(d: &selahcue_core::providers::NoteDraft) -> serde_json::Value {
    serde_json::json!({
        "title": d.title,
        "summary": d.summary,
        "sections": d.sections.iter().map(|s| serde_json::json!({
            "heading": s.heading, "items": s.items,
        })).collect::<Vec<_>>(),
        "scriptures": d.scriptures,
    })
}

/// Run note generation with consent gating + graceful fallback. In a `cloud-live` build with a
/// configured base URL + stored token it calls the real SelahCue service; otherwise it still
/// honours the consent gate and then reports the honest "not configured" state (no live transport).
#[cfg(feature = "cloud-live")]
async fn run_note_generation(
    cfg: selahcue_core::providers::ProvidersConfig,
    transcript: String,
    state: &State<'_, AppState>,
) -> Result<selahcue_cloud::GenerationOutcome, selahcue_core::providers::NoteError> {
    let base = cloud_base_url();
    let token = state.secrets.get(ACCOUNT_TOKEN_NAME).ok().flatten();
    // Offload the BLOCKING reqwest call onto a blocking thread so a slow/unreachable endpoint
    // (up to the 30s transport timeout) never stalls a Tokio worker and starves other async
    // Tauri commands (honours the offload contract in selahcue-cloud/src/transport.rs).
    tauri::async_runtime::spawn_blocking(move || {
        let local = selahcue_cloud::LocalNoteProvider::new();
        match (base, token) {
            (Some(b), Some(t)) if !t.is_empty() => {
                let transport = selahcue_cloud::transport::ReqwestTransport::new()
                    .map_err(|e| selahcue_core::providers::NoteError::Transport(e.to_string()))?;
                let client = selahcue_cloud::SelahCueCloudClient::new(transport, b, t);
                selahcue_cloud::generate_sermon_notes(&cfg, &transcript, true, &client, &local)
            }
            _ => {
                // No account/endpoint yet — honour the gate first (ConsentRequired if not opted in),
                // then report NotConfigured.
                cfg.build_note_request(&transcript, true)?;
                Err(selahcue_core::providers::NoteError::NotConfigured)
            }
        }
    })
    .await
    .map_err(|e| {
        selahcue_core::providers::NoteError::Transport(format!("worker join error: {e}"))
    })?
}

#[cfg(not(feature = "cloud-live"))]
async fn run_note_generation(
    cfg: selahcue_core::providers::ProvidersConfig,
    transcript: String,
    _state: &State<'_, AppState>,
) -> Result<selahcue_cloud::GenerationOutcome, selahcue_core::providers::NoteError> {
    // Offline build: honour the consent gate (so the UI still gets ConsentRequired vs
    // NotConfigured correctly), then report the honest "not configured" state — the live
    // SelahCue service is not compiled in.
    cfg.build_note_request(&transcript, true)?;
    Err(selahcue_core::providers::NoteError::NotConfigured)
}

/// Generate AI sermon notes from a COMPLETED transcript. Consent-gated end-to-end: with cloud-notes
/// consent off, nothing is sent (returns `consent_required`). The result is operator-local JSON.
#[tauri::command]
async fn generate_sermon_notes(
    transcript: String,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    // Snapshot the config under the lock, then generate without holding it.
    let cfg = {
        state
            .providers
            .lock()
            .map_err(|e| format!("providers lock: {e}"))?
            .clone()
    };
    match run_note_generation(cfg, transcript, &state).await {
        Ok(outcome) => Ok(serde_json::json!({
            "ok": true,
            "degraded": outcome.degraded,
            "provider": outcome.provider_label,
            "draft": draft_json(&outcome.draft),
            "quota": outcome.quota.map(|q| serde_json::json!({
                "used": q.used, "limit": q.limit, "remaining": q.remaining(), "resets_label": q.resets_label,
            })),
        })),
        Err(e) => Ok(serde_json::json!({
            "ok": false,
            "error": note_error_code(&e),
            "message": e.to_string(),
        })),
    }
}

/// The account-token secret store: OS keychain in a `cloud-live` build (FR-134/NFR-017), an
/// in-memory store otherwise (nothing to persist until the live service exists).
#[cfg(feature = "cloud-live")]
fn make_secret_store() -> Box<dyn selahcue_cloud::SecretStore + Send + Sync> {
    Box::new(selahcue_cloud::secret::KeyringSecretStore::new("SelahCue"))
}
#[cfg(not(feature = "cloud-live"))]
fn make_secret_store() -> Box<dyn selahcue_cloud::SecretStore + Send + Sync> {
    Box::new(selahcue_cloud::InMemorySecretStore::new())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            // Packaged install: bring up the bundled output window (a sibling binary) BEFORE we
            // build the backend, so `build_backend()` finds its fresh loopback endpoint and
            // connects instead of falling back to the demo. In a dev run the sibling is absent,
            // so this is a no-op and today's behaviour is unchanged (ADR-0002/0003: separate
            // native compositor process, never rendered in the WebView).
            let output = std::env::current_exe()
                .ok()
                .and_then(|exe| autolaunch::spawn_output_window(&exe, &endpoint_file_path()))
                .map(Arc::new);
            if let Some(output) = &output {
                // Terminate the bundled output window when the operator window is destroyed, so
                // quitting the console does not orphan the audience-output process.
                if let Some(win) = app.get_webview_window("main") {
                    let output = Arc::clone(output);
                    win.on_window_event(move |event| {
                        if matches!(event, tauri::WindowEvent::Destroyed) {
                            output.kill();
                        }
                    });
                }
            }
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
            // Providers & Privacy: open a best-effort connection to the same DB and load the saved
            // config (empty/absent → the core's offline-first defaults). Persistence failure only
            // means settings live in memory for the session (never blocks the console).
            let providers_db = open_deck_db(app);
            let providers = providers_db
                .as_ref()
                .and_then(|db| selahcue_data::providers_repo::load(db).ok())
                .unwrap_or_default();
            app.manage(AppState {
                backend,
                deck: Mutex::new(ws),
                library: Mutex::new(library),
                providers: Mutex::new(providers),
                providers_db: providers_db.map(Mutex::new),
                secrets: make_secret_store(),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            remote_snapshot,
            remote_approve,
            remote_deny,
            remote_revoke,
            remote_set_role,
            remote_new_code,
            host_connected,
            disk_free,
            stt_ready,
            audio_input,
            view,
            next,
            previous,
            go_live,
            clear,
            blackout,
            select,
            select_slide,
            start_timer,
            stop_timer,
            adjust_timer,
            pause_timer,
            resume_timer,
            add_item,
            remove_item,
            move_item,
            plan_undo,
            plan_redo,
            rename_item,
            stage_scripture,
            follow_scripture,
            scripture_search,
            get_chapter,
            ingest_transcript,
            detection_health,
            retry_detection,
            approve_detection,
            dismiss_detection,
            start_listening,
            stop_listening,
            cancel_download,
            list_translations,
            download_translation,
            identify_outputs,
            assign_output,
            set_theme,
            set_custom_theme,
            set_item_theme,
            set_item_content,
            set_item_owner,
            set_item_duration,
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
            deck_search,
            deck_new,
            deck_open,
            deck_rename,
            deck_duplicate,
            deck_delete,
            deck_restore,
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
            plan_deck_slides,
            render_plan_deck_slide,
            present_plan_deck_slide,
            output_connected,
            providers_view,
            set_transcription_mode,
            set_cloud_consent,
            set_notes_template,
            set_preferred_translation,
            set_include_flag,
            set_account_token,
            clear_account_token,
            generate_sermon_notes
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
