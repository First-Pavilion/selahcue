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
use selahcue_lan::protocol::{ContentLinkView, ImportItemView, ScaleFit};
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

/// The bounded capture→consumer audio hand-off shared by the on-device and Cloud transcription
/// routes (86akby7th) — lives in its own module so neither route reaches into the other's file
/// for it. Depends on `selahcue_stt::audio::AudioChunk`, so it follows `listening.rs`'s own
/// `stt` gate (there is nothing for it to hand audio off to without that feature).
#[cfg(feature = "stt")]
mod capture_handoff;

/// Where live transcription should run (Cloud vs. on-device) — pure, and consumed only by
/// `listening.rs` (`stt`-gated), so the module itself follows the same gate for production
/// builds. `cfg(test)` widens that for `cargo test`/`cargo clippy --all-targets` specifically:
/// the routing decision is exercised by its own test module with **no feature flags at all**
/// (86akby7th) — the point being that `TranscriptionRoute::decide` is pure enough not to need
/// `stt`'s native toolchain to verify, even though nothing calls it in a build without `stt`.
#[cfg(any(test, feature = "stt"))]
mod transcription_route;

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

/// Safe, hardened validation of a user-picked file before it becomes a `MediaRef` or a library
/// asset (FR-138, 86ak0qmzv) — canonicalisation, a regular-file check, a size cap and a
/// magic-byte type allowlist, ahead of and separate from `selahcue_engine`'s own decode hardening.
mod safe_import;

/// Developer AI provider keys from the repo-root `.env` (feature `dev-keys`; OFF by default, and
/// the file read is not compiled in without it). Temporary scaffolding for the developer-key
/// phase — the module's own docs name what replaces it.
mod dev_env;

/// The single lock guarding **all** process-environment mutation in this test binary.
///
/// `std::env::set_var`/`remove_var` are process-global while `cargo test` runs tests as threads,
/// so two tests touching the same variable race. `dev_env::tests` had its own private lock; the
/// model-override tests in `providers_view_tests` mutate the same names
/// (`OPENAI_API_KEY`, `SELAHCUE_OPENAI_MODEL`), so a second private lock would guard nothing
/// against the first.
///
/// Today the two never compile together — `make ci` runs `--features dev-keys` and
/// `--features openai-notes` as separate invocations — so the race is latent rather than live.
/// It becomes real the moment anyone runs `--features dev-keys,openai-notes`, and a flake that
/// only appears under a feature combination nobody routinely builds is the worst kind to leave
/// armed. One lock, hoisted here where both modules can reach it.
#[cfg(test)]
pub(crate) static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

/// Acquire [`ENV_LOCK`], recovering from a poisoned mutex so one failing test does not cascade.
#[cfg(test)]
pub(crate) fn env_locked() -> std::sync::MutexGuard<'static, ()> {
    ENV_LOCK
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

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

    /// Swap in a freshly (re)connected client after the old one dropped. A no-op on `Local`:
    /// the demo backend has no link to replace. `Remote`'s client sits behind a `Mutex` that
    /// already exists for every other command, so replacing its contents needs no change to
    /// `AppState.backend`'s own type — only the reconnect loop in [`view`] calls this.
    async fn replace_remote(&self, fresh: RemoteOperator) {
        if let Backend::Remote(m) = self {
            *m.lock().await = fresh;
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
    // --- Plan publish / hand-off (FR-006) and the plan lifecycle actions (FR-005) ---
    async fn publish_plan(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .publish_plan()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.publish_plan()),
        }
    }
    async fn new_plan(&self, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .new_plan(&name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.new_plan(&name)),
        }
    }
    async fn template_plan(&self, template: String, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .template_plan(&template, &name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.template_plan(&template, &name)),
        }
    }
    async fn duplicate_plan(&self, name: String) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .duplicate_plan(&name)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.duplicate_plan(&name)),
        }
    }
    async fn import_plan(
        &self,
        name: String,
        items: Vec<ImportItemView>,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .import_plan(&name, items)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.import_plan(&name, items)),
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
    /// Resolve the transcript id new AI-derived content (a sermon-note draft) should attach to
    /// right now (86akgqdv0; PR #33 review, Sana F1 remediation). Same dispatch shape as
    /// `ingest_transcript` above — NOT `stt`-gated, because `generate_sermon_notes` (its only
    /// caller today) is not either: a transcript can be pasted in manually without live STT.
    async fn active_transcript_id(&self) -> Result<Option<i64>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .active_transcript_id()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.active_transcript_id()),
        }
    }
    /// Load the persisted sermon-note draft for `transcript_id`, if any (86akgqdv0).
    async fn load_sermon_note_draft(
        &self,
        transcript_id: i64,
    ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .load_sermon_note_draft(transcript_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.load_sermon_note_draft(transcript_id)),
        }
    }
    /// Persist (upsert) a freshly generated draft against `transcript_id` on the host
    /// (86akgqdv0) — `generate_sermon_notes`'s persist-on-success path. `Ok(None)` when the
    /// host refuses it (an oversized field, or no store configured) — never a hard error, so a
    /// persistence failure never blocks the draft from still being shown to the operator.
    async fn save_sermon_note_draft(
        &self,
        transcript_id: i64,
        draft: selahcue_lan::protocol::SermonNoteDraftInput,
    ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .save_sermon_note_draft(transcript_id, draft)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.save_sermon_note_draft(transcript_id, draft)),
        }
    }
    /// Apply an operator edit to the persisted draft's text for `transcript_id` (86akgqdv0).
    /// `Ok(None)` when the host refuses it (no draft exists yet, an oversized field).
    async fn update_sermon_note_draft(
        &self,
        transcript_id: i64,
        edit: selahcue_lan::protocol::SermonNoteEditInput,
    ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .update_sermon_note_draft(transcript_id, edit)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.update_sermon_note_draft(transcript_id, edit)),
        }
    }
    /// Stage a freshly (re)generated draft against `transcript_id` on the host WITHOUT
    /// replacing the currently-accepted draft (FR-129, 86akgqdx8). `Ok(None)` when the host
    /// refuses it (no accepted draft exists yet, an oversized field, or the frame would
    /// exceed the control link's cap on a Remote backend).
    async fn stage_sermon_note_regeneration(
        &self,
        transcript_id: i64,
        draft: selahcue_lan::protocol::SermonNoteDraftInput,
    ) -> Result<Option<selahcue_app::RegenerationSlot>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .stage_sermon_note_regeneration(transcript_id, draft)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.stage_sermon_note_regeneration(transcript_id, draft)),
        }
    }
    /// Accept the pending regeneration for `transcript_id` on the host (FR-129), replacing
    /// the accepted draft with it. `Ok(None)` when the host refuses it (nothing pending, or
    /// accepting would strip the FR-123 AI-generated label from an already-labelled draft).
    async fn confirm_sermon_note_regeneration(
        &self,
        transcript_id: i64,
    ) -> Result<Option<selahcue_app::RegenerationSlot>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .confirm_sermon_note_regeneration(transcript_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.confirm_sermon_note_regeneration(transcript_id)),
        }
    }
    /// Discard the pending regeneration for `transcript_id` on the host (FR-129), leaving
    /// the accepted draft unchanged.
    async fn discard_sermon_note_regeneration(
        &self,
        transcript_id: i64,
    ) -> Result<Option<selahcue_app::RegenerationSlot>, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .discard_sermon_note_regeneration(transcript_id)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.discard_sermon_note_regeneration(transcript_id)),
        }
    }
    /// Open a durable transcript session (86akcfftu) — the session-boundary sibling of
    /// [`ingest_transcript`](Self::ingest_transcript), same dispatch shape. Only called from
    /// the `stt`-gated `listening` module today (there is no webview affordance to open a
    /// session manually — out of scope, no UI change), hence the matching `cfg`.
    #[cfg(feature = "stt")]
    async fn start_transcript(
        &self,
        label: String,
        provider: String,
    ) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .start_transcript(&label, &provider)
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.start_transcript(&label, &provider)),
        }
    }
    /// Close the current durable transcript session, if one is open. Same `cfg` as
    /// [`start_transcript`](Self::start_transcript), for the same reason.
    #[cfg(feature = "stt")]
    async fn end_transcript(&self) -> Result<OperatorView, String> {
        match self {
            Backend::Remote(m) => m
                .lock()
                .await
                .end_transcript()
                .await
                .map_err(|e| e.to_string()),
            Backend::Local(s) => Ok(s.end_transcript()),
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
    /// Best-effort READ connection to the shared transcript store `selahcue-desktop` writes via
    /// its durable write path (86akcfftu) — see [`open_transcript_db`]'s doc comment for why this
    /// is a SEPARATE connection/path from `providers_db` above, never the same file. `None` → the
    /// Transcripts page (86akcffvt) reports "transcript store unavailable"; this shell never
    /// creates or writes to this store — structurally, via `open_existing_readonly` (SQLite's own
    /// `SQLITE_OPEN_READ_ONLY`, no `CREATE`, migrations never run), not merely by doc-comment
    /// claim (86akcffvt review, Sana F1 / Cody Blocker).
    transcript_db: Option<Mutex<selahcue_data::Database>>,
    /// The SelahCue account/session token store (FR-134): OS keychain in a `cloud-live` build,
    /// in-memory otherwise. Never a user-pasted third-party key.
    secrets: Box<dyn selahcue_cloud::SecretStore + Send + Sync>,
    /// The control link's real state (Tier 2a): the pure backoff/attempt-count state machine
    /// from `selahcue_lan::link`, driven by actual connect attempts made from [`view`]. A
    /// `Local` backend never leaves [`selahcue_lan::LinkState::Local`] — `LinkStatus`'s own
    /// `observe_*` methods no-op there, so this cannot drift into claiming a link that was
    /// never wanted.
    link_status: Mutex<selahcue_lan::LinkStatus>,
    /// Wall-clock deadline for the next automatic reconnect attempt, or `None` when none is
    /// scheduled (nothing to reconnect, or the breaker in `link_status` has given up).
    ///
    /// Lives here rather than in `selahcue_lan::link` because "when" is real-clock IO the
    /// pure crate deliberately does not own (its own doc: dialling belongs to the shell) —
    /// mirrors `selahcue-desktop`'s manual window-retry gesture, which is also real-clock
    /// state kept in the shell around a decision made elsewhere.
    link_next_attempt: Mutex<Option<std::time::Instant>>,
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
    view_body(&state, read_endpoint).await
}

/// `view`'s real body, against a bare `&AppState`. Split out so a test can drive the EXACT
/// sequence production uses — reconnect call included — instead of a hand-reconstructed copy.
/// The endpoint lookup is injected for the same reason [`maybe_reconnect_from`] takes one: a
/// test proving the real reconnect fires must not depend on the shared OS-temp-dir file every
/// other process on the machine also reads/writes (`endpoint_file_path`'s own doc). Production
/// calls the one-line wrapper above with the real `read_endpoint`.
///
/// An earlier version of this function was itself the bug: it called `record_link_outcome` then
/// immediately `maybe_reconnect`, and the test that was supposed to guard it called
/// `record_link_outcome` and `maybe_reconnect_from` directly rather than through this shared
/// body — so it passed even with the real call sequence broken (independently found and proven
/// by all four reviewers on 86ak4xxwm's review round: Cody, Vera P-2, Sana S-2). Any future
/// change here is covered by `link_reconnect_tests::a_dropped_link_really_reconnects_and_the_view_really_changes`,
/// which now calls exactly this function in a loop, the same way the webview's 1 Hz poll does.
async fn view_body(
    state: &AppState,
    endpoint_source: impl Fn() -> Option<Endpoint>,
) -> Result<OperatorView, String> {
    // The 1 Hz view poll is the console's only regular traffic over the control link, so it is
    // also the only place the link's liveness is observable — and, since Tier 2a, the only place
    // a real reconnect attempt gets a chance to run. Record the outcome so `link_status` reports
    // what actually happened, then (Remote only) drive the real backoff-paced re-dial loop.
    let r = state.backend.view().await;
    if state.backend.is_remote() {
        record_poll_outcome(state, r.as_ref().err());
        maybe_reconnect_from(state, endpoint_source).await;
    }
    r
}

/// Feed one POLL's outcome into the real `LinkStatus` state machine.
///
/// A poll failure only ever STARTS the backoff sequence (`Connected`/`Local` → `Reconnecting`,
/// exactly once) — it must never touch an ALREADY-scheduled deadline. The first version of this
/// function unconditionally rewrote `link_next_attempt` on every call, including a routine poll
/// against a link already known to be down. Since `view_body` calls `record_poll_outcome` then
/// `maybe_reconnect` back to back on every tick, that meant the deadline this tick just set was
/// always checked microseconds after being set — never due — and the NEXT tick's poll failure
/// overwrote it again before it could ever age past its own backoff. The reconnect path could
/// not fire, ever (proven independently by all four reviewers on 86ak4xxwm's review round, each
/// replaying the real sequence against the real `LinkStatus`: 0 re-dials over dozens of
/// simulated 1 Hz polls). Once genuinely reconnecting, only a REAL dial attempt
/// (`maybe_reconnect_from`'s own `connect_remote` call, via `record_dial_failure` below) is
/// allowed to advance `attempts`/the schedule — which is also what makes `attempts` count actual
/// re-dials instead of every failing poll (Sana S-4: the poll-driven version reported `attempts`
/// climbing past `MAX_RECONNECT_ATTEMPTS` with zero real dials made).
fn record_poll_outcome(state: &AppState, err: Option<&String>) {
    let Ok(mut status) = state.link_status.lock() else {
        return;
    };
    match err {
        None => {
            status.observe_success();
            drop(status);
            if let Ok(mut slot) = state.link_next_attempt.lock() {
                *slot = None;
            }
        }
        Some(e) => {
            if !matches!(
                status.state(),
                selahcue_lan::LinkState::Connected | selahcue_lan::LinkState::Local
            ) {
                // Already reconnecting, or the breaker has given up: this poll is confirming
                // what is already known, not a new attempt. Leave whatever schedule is already
                // pending untouched — this is the fix for the bug the doc comment above
                // describes.
                return;
            }
            status.observe_failure(e);
            schedule_next_attempt(state, &status);
        }
    }
}

/// Record a REAL dial attempt's failure (`maybe_reconnect_from`'s own `connect_remote` call) —
/// distinct from [`record_poll_outcome`]: unlike a routine poll, this must always advance
/// `attempts` and reschedule, even though the state is already `Reconnecting` (which is exactly
/// the state `record_poll_outcome` refuses to touch further). This poll-vs-dial split is what
/// bounds `attempts` at `MAX_RECONNECT_ATTEMPTS` regardless of how long the outage lasts, rather
/// than climbing forever with every failing poll (Sana S-4).
///
/// **Precise count (security review, Sana S-4/P-7 doc nit):** `attempts` is not purely "real
/// re-dials made" — the FIRST increment happens in `record_poll_outcome`, on the poll that
/// *detects* the drop, before any dial has been attempted. So `MAX_RECONNECT_ATTEMPTS = 5`
/// permits **4** real re-dials per outage, not 5, and `LinkStatus::next_backoff`'s first table
/// slot (250ms) is consequently never read — the first dial always waits the SECOND slot
/// (500ms). Both are intentional (the detecting poll genuinely is the first "we tried and it
/// didn't work" event), documented here so a future "attempt N of 5" surface does not
/// fabricate a dial that has not happened, which is the exact class of statement this ticket
/// exists to remove.
fn record_dial_failure(state: &AppState, err: &str) {
    let Ok(mut status) = state.link_status.lock() else {
        return;
    };
    status.observe_failure(err);
    schedule_next_attempt(state, &status);
}

/// Sets `link_next_attempt` from `status`'s own backoff table. The only two call sites allowed
/// to move the schedule forward: the first poll failure ([`record_poll_outcome`]) and a failed
/// dial attempt ([`record_dial_failure`]) — never a routine poll against an already-known-down
/// link.
fn schedule_next_attempt(state: &AppState, status: &selahcue_lan::LinkStatus) {
    let next = status.next_backoff();
    if let Ok(mut slot) = state.link_next_attempt.lock() {
        *slot = next.map(|d| std::time::Instant::now() + d);
    }
}

/// Attempt one real re-dial if the pure state machine's own backoff says it is due. This is
/// what makes `LinkState::Reconnecting` true only when an attempt genuinely is scheduled — the
/// exact biconditional the fabricated "Reconnecting…" label used to violate — and it is what
/// actually recovers the link without an operator restarting the console, up to the state
/// machine's own `MAX_RECONNECT_ATTEMPTS` bound (after which it reports `Disconnected` and this
/// function has nothing left to schedule).
///
/// `endpoint_source` is injected rather than hard-coded to `read_endpoint` for the same reason
/// [`view_body`] injects it: a test proving a real re-dial fires must not depend on the shared
/// OS-temp-dir file every other process on the machine also reads/writes. Production always
/// calls this via `view_body(&state, read_endpoint)`.
async fn maybe_reconnect_from(state: &AppState, endpoint_source: impl Fn() -> Option<Endpoint>) {
    let due = {
        let Ok(mut slot) = state.link_next_attempt.lock() else {
            return;
        };
        match *slot {
            Some(at) if std::time::Instant::now() >= at => {
                // Clear the schedule before attempting: a slow connect must not leave a stale
                // deadline that a later poll reads as "still due" and fires again concurrently.
                *slot = None;
                true
            }
            _ => false,
        }
    };
    if !due {
        return;
    }
    let Some(ep) = endpoint_source() else {
        // No endpoint file at all — the output window is gone, not merely unreachable. This
        // still counts as a failed dial attempt (not a free pass): without that, once the first
        // poll failure schedules the one and only deadline `record_poll_outcome` will ever set,
        // nothing would ever reschedule another attempt, and the console would sit in
        // "Reconnecting…" forever with no dial ever tried again and no honest give-up either.
        record_dial_failure(state, "no output window endpoint found");
        return;
    };
    match connect_remote(&ep).await {
        Ok(fresh) => {
            state.backend.replace_remote(fresh).await;
            if let Ok(mut status) = state.link_status.lock() {
                status.observe_success();
            }
        }
        Err(e) => {
            record_dial_failure(state, &e);
        }
    }
}

/// Tier 2a end to end: a real dropped socket is really reconnected, driven by the real
/// `selahcue_lan::link::LinkStatus` backoff state machine — not a copy of its logic re-asserted
/// here (that trap is called out in `implementation/desktop/CLAUDE.md`'s bounded-memory-test
/// section: a control that re-derives the predicate instead of consuming the real one survives
/// mutation of the real one). Every assertion below reads `link_status()`/`state.backend.view()`,
/// the exact producer→view path the console's poll uses.
#[cfg(test)]
mod link_reconnect_tests {
    use super::*;
    use selahcue_app::{handler_for, LiveController};
    use selahcue_core::plan::{ItemKind, ServicePlan};
    use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
    use selahcue_lan::{ControlServer, Role, SelfSigned};
    use selahcue_present::Theme;
    use std::time::{Duration, Instant as StdInstant};
    use tokio::net::TcpListener;
    use tokio::sync::Mutex as AsyncMutex;

    /// Stand up one real, pinned-TLS `ControlServer` on loopback with a single pre-paired
    /// Producer session, backed by a `LiveController` over `plan_name`. Returns the listening
    /// address, the pin, and the dedicated [`tokio::runtime::Runtime`] it runs on.
    ///
    /// It gets its OWN runtime, not a `tokio::spawn` on the test's runtime: `ControlServer::run`
    /// spawns one further detached task per accepted connection (`server.rs`), so aborting only
    /// the outer accept-loop `JoinHandle` leaves an already-established connection's handler
    /// running — the socket stays alive and the test cannot produce the real drop it needs.
    /// `Runtime::shutdown_background` drops every task the runtime owns, accepted connections
    /// included, which is what an actual crashed/killed output-window process looks like from
    /// the operator's side.
    ///
    /// Built with NO calls into an ambient async runtime (`block_on` on a fresh `Runtime`
    /// panics — "cannot start a runtime from within a runtime" — when called from this test's
    /// own `#[tokio::test]` task): every setup step here is synchronous, and only the accept
    /// loop itself is handed to the new runtime via `Runtime::spawn`, which merely schedules a
    /// task and needs no entered context on the calling thread.
    fn spawn_server(plan_name: &str) -> (SocketAddr, CertPin, tokio::runtime::Runtime) {
        let identity = SelfSigned::generate(vec!["localhost".into()]).expect("self-signed cert");
        let pin = identity.pin;
        let mut plan = ServicePlan::new(plan_name);
        plan.add_item(ItemKind::Song, "Opening Song");
        let controller = Arc::new(std::sync::Mutex::new(LiveController::new(
            plan,
            320,
            180,
            Theme::dark(),
        )));

        let mut registry_inner = SessionRegistry::new();
        let now = StdInstant::now();
        registry_inner.offer_pairing("p", Role::Producer, now, Duration::from_secs(300));
        registry_inner
            .redeem(
                "p",
                DeviceId("producer".into()),
                SessionToken::new("tok-prod"),
                now,
            )
            .expect("redeem test pairing code");
        let registry = Arc::new(AsyncMutex::new(registry_inner));

        let server = Arc::new(
            ControlServer::new(&identity, registry, handler_for(controller.clone()))
                .expect("build control server"),
        );

        let std_listener = std::net::TcpListener::bind("127.0.0.1:0").expect("bind loopback");
        std_listener
            .set_nonblocking(true)
            .expect("set listener nonblocking for tokio");
        let addr = std_listener.local_addr().expect("local addr");

        let rt = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .expect("build dedicated server runtime");
        rt.spawn(async move {
            let listener = TcpListener::from_std(std_listener).expect("tokio listener from std");
            let _ = server.run(listener).await;
        });
        (addr, pin, rt)
    }

    fn state_with_remote(remote: RemoteOperator) -> AppState {
        AppState {
            backend: Backend::Remote(Box::new(tokio::sync::Mutex::new(remote))),
            deck: Mutex::new(crate::DeckWorkspace::demo()),
            library: Mutex::new(crate::DeckLibrary::load(None)),
            providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
            providers_db: None,
            transcript_db: None,
            secrets: make_secret_store(),
            link_status: Mutex::new(selahcue_lan::LinkStatus::connected()),
            link_next_attempt: Mutex::new(None),
        }
    }

    /// The whole point of Tier 2a: after the host really disappears, `link_status()` really
    /// reports `reconnecting` (never a static "disconnected" the console cannot recover from
    /// without a restart), and once the backoff elapses and a real host comes back — on a
    /// DIFFERENT address, exactly as a restarted output window would advertise — the operator's
    /// own `view()` really reflects the new host's state.
    ///
    /// Drives the REAL `view_body` — the exact function `view` delegates to — in a loop, the
    /// same call pattern the webview's 1 Hz poll uses. An earlier version of this test called
    /// `record_link_outcome`/`maybe_reconnect_from` directly instead, and PASSED even after the
    /// real call site inside `view`/`view_body` was deleted entirely (independently reproduced
    /// by all four reviewers on 86ak4xxwm's review round — Cody, Vera P-2, Sana S-2). That gap,
    /// not only the scheduling bug it was hiding (Vera P-1 / Sana S-1 / Cody, also independently
    /// reproduced: the previous version of `record_link_outcome` rewrote `link_next_attempt` on
    /// every poll, so a deadline set this tick was always checked microseconds later — never
    /// due — is what this rewrite closes. No fixed-duration sleep gates an assertion here
    /// either (the previous version's `sleep(50ms)` after `shutdown_background()` — which
    /// explicitly does not wait for tasks to stop — was a flake risk under CI load, per Vera's
    /// and Sana's review); both waits below are bounded polls for the real condition.
    #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
    async fn a_dropped_link_really_reconnects_and_the_view_really_changes() {
        let (addr1, pin1, server1) = spawn_server("Original Service");
        let remote = RemoteOperator::connect(addr1, "localhost", pin1, "producer", "tok-prod")
            .await
            .expect("connect to first server");
        let state = state_with_remote(remote);
        // Never actually consulted while nothing is due (see the `view_body`/`maybe_reconnect_from`
        // doc comments) — used for the phases below that must not touch the shared endpoint file.
        let no_endpoint = || None;

        // 1. Healthy: the real poll succeeds and link_status says so.
        let v1 = view_body(&state, no_endpoint)
            .await
            .expect("first view succeeds");
        assert_eq!(v1.plan_name, "Original Service");
        assert_eq!(link_status_reply(&state).state, "connected");

        // 2. Kill the real server — a genuine dropped socket (every task the server's runtime
        //    owns, including the already-accepted connection's handler, is dropped), not a
        //    simulated error. Bounded wait-for-condition: poll the real `view_body` until it
        //    genuinely observes the drop, rather than betting on a fixed sleep duration.
        server1.shutdown_background();
        let mut saw_failure = false;
        for _ in 0..100 {
            if view_body(&state, no_endpoint).await.is_err() {
                saw_failure = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        assert!(
            saw_failure,
            "poll against a dead socket must eventually fail (waited 5s)"
        );

        // 3. link_status must say `reconnecting` — not a static `disconnected` — because an
        //    automatic attempt really is now scheduled. `attempts == 1`: exactly one POLL
        //    detected the drop; no DIAL has been attempted yet (Sana S-4 — `attempts` must count
        //    real re-dials, not every poll against a link already known to be down).
        let status = link_status_reply(&state);
        assert_eq!(
            status.state, "reconnecting",
            "a dropped link with attempts remaining must report reconnecting, not a dead end"
        );
        assert_eq!(
            status.attempts, 1,
            "one poll observed the drop; no dial has been attempted yet"
        );

        // 4. Stand up a SECOND real server on a DIFFERENT address with DIFFERENT content — the
        //    honest shape of "the output window restarted".
        let (addr2, pin2, server2) = spawn_server("Recovered Service");
        let second_server = move || {
            Some(Endpoint {
                addr: addr2.to_string(),
                pin: pin2.to_hex(),
                device: "producer".into(),
                token: "tok-prod".into(),
            })
        };

        // 5. Drive the REAL `view_body` sequence in a loop until the real backoff elapses and a
        //    re-dial actually fires and succeeds. Bounded well past the state machine's own
        //    `MAX_RECONNECT_ATTEMPTS` give-up point, so a regression fails the assertion below
        //    rather than hanging.
        let mut reconnected = false;
        for _ in 0..100 {
            let _ = view_body(&state, second_server).await;
            if link_status_reply(&state).state == "connected" {
                reconnected = true;
                break;
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        assert!(
            reconnected,
            "the real view_body sequence never reconnected within 10s — last_error = {:?}",
            link_status_reply(&state).last_error
        );

        // 6. The reconnect must be REAL: a fresh view() call returns the SECOND server's own
        //    data — proving the swap actually happened, not merely that the state label changed.
        let v2 = view_body(&state, second_server)
            .await
            .expect("view after reconnect");
        assert_eq!(v2.plan_name, "Recovered Service");

        // A `Runtime` cannot drop itself from inside an async context (it needs to block the
        // dropping thread), so shut both down explicitly rather than letting the test fn's end
        // do it implicitly.
        server2.shutdown_background();
    }
}

/// Reply to `link_status` — the operator↔host control-link state (Tier 2).
///
/// The `state` strings come from [`LinkState::tag`], so this cannot drift from the state machine
/// in `selahcue-lan::link` that defines the vocabulary.
#[derive(serde::Serialize)]
struct LinkStatusReply {
    state: &'static str,
    epoch: u64,
    attempts: u32,
    last_error: Option<String>,
}

/// The control-link state, replacing four fabrications at once: a permanent green "Connected"
/// in the stand-alone build, an untrue "Reconnecting…", absent telemetry rendered as a fault, and
/// (Tier 2a) a `Reconnecting` that used to be unreachable because nothing actually retried.
///
/// The `view` command now drives a real backoff-paced re-dial loop (see `maybe_reconnect`), so
/// this is a thin, honest READ of the state that loop maintains — it never itself dials or
/// mutates `link_status`. The biconditional the pure `selahcue_lan::link` module documents still
/// holds: `Reconnecting` is true here exactly when [`AppState::link_next_attempt`] genuinely has
/// a scheduled attempt behind it.
#[tauri::command]
fn link_status(state: State<'_, AppState>) -> LinkStatusReply {
    link_status_reply(&state)
}

/// [`link_status`]'s body, taking a bare `&AppState` so tests can call it directly without
/// standing up a `tauri::State` wrapper around a throwaway app handle.
fn link_status_reply(state: &AppState) -> LinkStatusReply {
    // A poisoned lock must not manufacture EITHER a disconnection or a false "connected" — a
    // mutex poison here says nothing about the link, it says another thread panicked while
    // holding it. Reporting a static "connected" (the original version of this fallback) is a
    // fabrication in exactly the sense this ticket exists to remove: a green pill asserted from
    // no evidence at all (security review, Sana S-5). `"unknown"` is deliberately NOT one of
    // `LinkState::tag()`'s four values — the webview's `paintConnPill`/`currentLinkState`
    // already treat any unrecognised state string as unknown ("Checking…"), the exact honest
    // fallback an older/newer version skew would also hit, so this reuses that path rather than
    // inventing a new one.
    let Ok(status) = state.link_status.lock() else {
        return LinkStatusReply {
            state: "unknown",
            epoch: 0,
            attempts: 0,
            last_error: None,
        };
    };
    LinkStatusReply {
        state: status.state().tag(),
        epoch: status.epoch(),
        attempts: status.attempts(),
        last_error: status.last_error().map(str::to_string),
    }
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
/// The three things a picker command can hand back: a validated path, "the user cancelled the
/// dialog", or "a file was picked but FR-138's [`safe_import::validate_picked_image`] refused
/// it". Deliberately NOT a Tauri command `Result`/`Err`: both `pick_image` call sites in
/// `dist/app.js` already treat a thrown command error as "no native picker available, fall back
/// to the manual path field" — conflating that with a validation refusal would silently swallow
/// the refusal's own reason and point the operator at the very field with no validation on it at
/// all. Serialised with a `outcome` tag so the frontend can distinguish the three cases without
/// re-deriving them from shape.
#[derive(serde::Serialize)]
#[serde(tag = "outcome", rename_all = "snake_case")]
enum PickImageOutcome {
    Picked { path: String },
    Cancelled,
    Rejected { reason: String },
}

/// Open the native OS file picker for a PNG image and return the chosen path, validated
/// (86ajq6j4p / 86ajq6j49 frontend; FR-138 / 86ak0qmzv). Host-local + user-initiated; the
/// returned path becomes an `Element::Image` source. **Must be `async`** so Tauri spawns it OFF
/// the main thread: `blocking_pick_file` enqueues the dialog onto the main event loop and waits
/// on it, so running it ON the main thread would deadlock/freeze the whole operator (the plugin
/// documents this footgun).
#[tauri::command]
async fn pick_image(app: tauri::AppHandle) -> PickImageOutcome {
    use tauri_plugin_dialog::DialogExt;
    let Some(picked) = app
        .dialog()
        .file()
        .add_filter("Images (PNG)", &["png"])
        .blocking_pick_file()
        .and_then(|fp| fp.into_path().ok())
    else {
        return PickImageOutcome::Cancelled;
    };
    // Offload validation (canonicalize + a bounded read) onto a blocking thread, mirroring the
    // same offload contract `run_note_generation` already uses for its blocking `reqwest` call
    // (main.rs, "Offload the BLOCKING ... call onto a blocking thread"): a slow/network/cloud-
    // placeholder path here must not stall a Tokio worker other async Tauri commands depend on.
    match tauri::async_runtime::spawn_blocking(move || safe_import::validate_picked_image(&picked))
        .await
    {
        Ok(Ok(canonical)) => PickImageOutcome::Picked {
            path: canonical.to_string_lossy().into_owned(),
        },
        Ok(Err(e)) => PickImageOutcome::Rejected {
            reason: e.to_string(),
        },
        Err(join_err) => PickImageOutcome::Rejected {
            reason: format!("internal error validating that file: {join_err}"),
        },
    }
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

/// The platform data directory `selahcue-desktop` (the desktop-authoritative process that owns
/// the real `Database`, ADR-0002/0003) actually writes transcripts into via its durable write
/// path (86akcfftu) — mirrors `selahcue-desktop/src/main.rs`'s own `data_dir()` exactly, same
/// per-OS branches, so both processes agree on the one file.
///
/// This is deliberately NOT `open_deck_db`'s `<app_data_dir>/selahcue.db3`: that path is keyed
/// on THIS shell's own Tauri bundle identifier (`com.selahcue.operator`), which resolves to a
/// DIFFERENT directory than `selahcue-desktop`'s (e.g. macOS: `~/Library/Application
/// Support/com.selahcue.operator` vs. `~/Library/Application Support/SelahCue`) — `open_deck_db`'s
/// own doc comment already names this exact gap as a documented follow-up ("aligning this path
/// with the desktop bin's data_dir() for a single shared DB"). Transcripts are the one thing this
/// shell reads that it never writes (86akcfftu's sink lives in `selahcue-desktop`, not here), so
/// reusing the operator-local path here would make the Transcripts page (86akcffvt) silently
/// empty against a real packaged app — the ticket's whole goal would go unmet. Scoped to
/// transcripts only: the deck/providers path stays its own separate follow-up, out of this
/// ticket's file footprint.
fn transcript_data_dir() -> Option<std::path::PathBuf> {
    // Windows resolves via APPDATA below and never reads HOME.
    #[cfg(not(target_os = "windows"))]
    let home = std::env::var_os("HOME").map(std::path::PathBuf::from);
    #[cfg(target_os = "macos")]
    let dir = home.map(|h| h.join("Library/Application Support/SelahCue"));
    #[cfg(target_os = "linux")]
    let dir = std::env::var_os("XDG_DATA_HOME")
        .map(std::path::PathBuf::from)
        // Per the XDG spec, an empty or relative XDG_DATA_HOME is treated as unset.
        .filter(|p| p.is_absolute())
        .or(home.map(|h| h.join(".local/share")))
        .map(|d| d.join("selahcue"));
    #[cfg(target_os = "windows")]
    let dir = std::env::var_os("APPDATA")
        .map(std::path::PathBuf::from)
        .map(|d| d.join("SelahCue"));
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    let dir: Option<std::path::PathBuf> = home.map(|h| h.join(".selahcue"));
    dir
}

/// Open a best-effort READ connection to the shared transcript store at
/// `<transcript_data_dir>/selahcue.db3`. `None` on any failure (no HOME/APPDATA, no service ever
/// recorded yet so the directory doesn't exist, the file present but not yet a real store, or an
/// at-rest-encrypted store this default (non-`encryption`) build can't open) — the caller reports
/// an honest "transcript store unavailable" rather than panicking.
///
/// Structurally, not just documentarily, never creates or writes anything: this calls
/// [`selahcue_data::Database::open_existing_readonly`] (86akcffvt review, Sana F1 / Cody
/// Blocker), never plain `open`. Plain `open` opens with SQLite's default CREATE flag and runs
/// migrations on demand — so a folder that exists but whose store doesn't yet (a real, ordinary
/// sequence: `make operator` run standalone before `selahcue-desktop` ever has, or a store
/// deleted by hand to reset transcript history) would have silently minted a fully-migrated
/// PLAINTEXT store from this "read-only" page. `selahcue-desktop`'s own `SessionStore::open_store`
/// decides plaintext-vs-encrypted for what it thinks is a brand-new store by reading what's
/// already on disk — it would see that operator-created file, find a plaintext header, and open
/// plain forever, permanently defeating FR-154 for that install the day desktop encryption
/// ships. `selahcue-desktop` alone owns creating, migrating, and writing this store; this shell
/// only ever reads it.
fn open_transcript_db() -> Option<selahcue_data::Database> {
    open_transcript_db_at(&transcript_data_dir()?)
}

/// As [`open_transcript_db`], but takes the directory explicitly rather than resolving the real
/// per-OS `transcript_data_dir()` — split out purely so a test can point this at a temp directory
/// it owns and can inspect afterward (86akcffvt review, Sana F1's required verification: "folder
/// present, no store → None and no file created" only means something against a directory the
/// test controls). Not a change of behaviour, just of testability.
fn open_transcript_db_at(dir: &std::path::Path) -> Option<selahcue_data::Database> {
    selahcue_data::Database::open_existing_readonly(dir.join("selahcue.db3")).ok()
}

// ---------------------------------------------------------------------------------------------
// Transcripts (86akcffvt / FR-130 core slice): list + read-only full-text viewer. Read-only —
// wired straight to 86ajtxzrn's `transcript_repo`, no new persistence/migration. Generating notes
// from a selected transcript is 86akcffy0's territory (depends on this one). The detected-
// scripture list and the saved sermon-note draft's actual content — both explicitly deferred by
// this ticket's own non-goals — are 86akgqdxr's territory: see `TranscriptDetailView`'s
// `detections`/`corrections`/`draft` fields and `transcript_get` below. Building a NEW write path
// for the correction layer is still out of scope (86akgqdxr's own non-goals) — `corrections` is
// forwarded read-only; nothing here opens `transcript_db` for a write.
// ---------------------------------------------------------------------------------------------

/// One row of the Transcripts list: label, date, duration, segment count — enough to render the
/// list without a second read per row (mirrors `transcript_repo::TranscriptSummary` field for
/// field; the JS side computes date/duration display strings from the raw `_ms` fields, the same
/// convention `OperatorView`'s other timing fields already use).
#[derive(serde::Serialize)]
struct TranscriptSummaryView {
    id: i64,
    label: String,
    provider: String,
    started_at_ms: i64,
    ended_at_ms: Option<i64>,
    segment_count: i64,
}

impl From<selahcue_data::transcript_repo::TranscriptSummary> for TranscriptSummaryView {
    fn from(t: selahcue_data::transcript_repo::TranscriptSummary) -> Self {
        TranscriptSummaryView {
            id: t.id,
            label: t.label,
            provider: t.provider,
            started_at_ms: t.started_at_ms,
            ended_at_ms: t.ended_at_ms,
            segment_count: t.segment_count,
        }
    }
}

/// One segment of a transcript's full stored text. `TranscriptSegment` itself derives no
/// `Serialize` (it is a pure domain type, `selahcue-core`), so this is the wire view.
#[derive(serde::Serialize)]
struct TranscriptSegmentView {
    id: u64,
    start_ms: u64,
    end_ms: u64,
    text: String,
}

impl From<&selahcue_core::transcript::TranscriptSegment> for TranscriptSegmentView {
    fn from(s: &selahcue_core::transcript::TranscriptSegment) -> Self {
        TranscriptSegmentView {
            id: s.id,
            start_ms: s.start_ms,
            end_ms: s.end_ms,
            text: s.text.clone(),
        }
    }
}

/// One scripture reference detected during a transcript's service (86akgqdxr; FR-130). Mirrors
/// `selahcue_core::detection::DetectedReference` field for field — that type derives no
/// `Serialize` (pure core, no wire concerns), same reason `TranscriptSegmentView` exists above.
/// `source_segment` is the "approximate transcript position" the ticket's scope asks for:
/// `transcripts.js` resolves it against the SAME response's `segments` array (by `id`) to derive
/// a human position, rather than this view duplicating segment ordinal/offset data it can already
/// reach. `0` is `transcript_repo::load`'s documented sentinel for "no known source segment" —
/// carried through unchanged, not reinterpreted here.
#[derive(serde::Serialize)]
struct DetectedReferenceView {
    id: u64,
    reference: String,
    source_segment: u64,
    confidence: u8,
}

impl From<&selahcue_core::detection::DetectedReference> for DetectedReferenceView {
    fn from(d: &selahcue_core::detection::DetectedReference) -> Self {
        DetectedReferenceView {
            id: d.id,
            reference: d.reference.clone(),
            source_segment: d.source_segment,
            confidence: d.confidence,
        }
    }
}

/// One segment's correction (86akgqdxr; the "editable correction layer" 86ajtxzrn's schema
/// reserved). READ-ONLY on this wire view — this ticket surfaces whatever corrections already
/// exist so the correction layer is reachable from this screen, but does not add a new command to
/// WRITE one: `transcript_repo::correct_segment` exists in `selahcue-data` but is reachable only
/// from a writable connection, which this operator shell structurally does not hold for the
/// transcript store (see `transcript_db`'s doc comment). Building that write path is this ticket's
/// own named non-goal, deferred to a follow-up.
#[derive(serde::Serialize)]
struct SegmentCorrectionView {
    segment_id: i64,
    corrected_text: String,
    corrected_at_ms: i64,
}

impl From<&selahcue_data::transcript_repo::SegmentCorrection> for SegmentCorrectionView {
    fn from(c: &selahcue_data::transcript_repo::SegmentCorrection) -> Self {
        SegmentCorrectionView {
            segment_id: c.segment_id,
            corrected_text: c.corrected_text.clone(),
            corrected_at_ms: c.corrected_at_ms,
        }
    }
}

/// A transcript read back in full: every stored segment, in order — never a tail or a sample
/// (86akcffvt AC2). `transcripts.js` owns bounded/windowed DOM rendering of however many segments
/// come back; this command does no pagination of its own (the ticket's scope is "get one
/// transcript in full").
///
/// `notes_generated` is real as of 86akcffy0: `sermon_note_repo::find_by_transcript` on the
/// SAME read-only connection this command already holds — a plain `SELECT`, so it costs nothing
/// this command didn't already pay for opening the store. Before this ticket it was hardcoded
/// `false` (there was no notes table); this is the "future ticket only has to change this ONE
/// value" the field's original comment named.
///
/// `detections`/`corrections` (86akgqdxr) were loaded by `transcript_repo::load` all along and
/// simply dropped on the way to this view — forwarding them costs no new query. `draft` and its
/// siblings (86akgqdxr) are the ACTUAL saved sermon-note content, not just `notes_generated`'s
/// boolean: fetched via `state.backend.load_sermon_note_draft(id)`, the SAME transcript-id-
/// generic path `update_sermon_note_draft` already uses to edit it — a second, independent read
/// from `notes_generated_for`'s (see `transcript_get`), kept deliberately separate so neither's
/// existing fault-isolation behaviour couples to the other's. All `Option` fields always
/// serialize (present as `null` when absent, matching `ended_at_ms`'s existing convention) so the
/// frontend contract's key set never depends on whether a draft happens to exist.
#[derive(serde::Serialize)]
struct TranscriptDetailView {
    id: i64,
    label: String,
    provider: String,
    started_at_ms: i64,
    ended_at_ms: Option<i64>,
    segments: Vec<TranscriptSegmentView>,
    notes_generated: bool,
    detections: Vec<DetectedReferenceView>,
    corrections: Vec<SegmentCorrectionView>,
    draft: Option<serde_json::Value>,
    scripture_verification_note: Option<&'static str>,
    ai_generated: Option<bool>,
    ai_label: Option<&'static str>,
    disclosure: Option<String>,
    notes_provider: Option<String>,
}

/// Pure mapping from a loaded `TranscriptDetail` (+ the two independently-fetched notes signals)
/// to the wire view — split out from `transcript_get` so the mapping is unit-testable without a
/// full `AppState`/Tauri context or an async runtime (86akgqdxr).
fn build_transcript_detail_view(
    t: selahcue_data::transcript_repo::TranscriptDetail,
    notes_generated: bool,
    draft_view: Option<&selahcue_lan::protocol::SermonNoteDraftView>,
) -> TranscriptDetailView {
    let (draft, scripture_verification_note, ai_generated, ai_label, disclosure, notes_provider) =
        match draft_view {
            Some(view) => {
                // `&t.segments` (86akgqdw0): this transcript's own real segments, already
                // loaded — the borrow ends with this call, well before `t.segments` (or any
                // other field of `t`) is read again below.
                let (draft_json, note) = sermon_note_draft_json(view, &t.segments);
                (
                    Some(draft_json),
                    note,
                    Some(view.ai_generated),
                    Some(selahcue_core::providers::AI_GENERATED_LABEL),
                    view.disclosure.clone(),
                    Some(view.provider.clone()),
                )
            }
            None => (None, None, None, None, None, None),
        };
    TranscriptDetailView {
        id: t.id,
        label: t.label,
        provider: t.provider,
        started_at_ms: t.started_at_ms,
        ended_at_ms: t.ended_at_ms,
        segments: t.segments.iter().map(TranscriptSegmentView::from).collect(),
        notes_generated,
        detections: t
            .detections
            .iter()
            .map(DetectedReferenceView::from)
            .collect(),
        corrections: t
            .corrections
            .iter()
            .map(SegmentCorrectionView::from)
            .collect(),
        draft,
        scripture_verification_note,
        ai_generated,
        ai_label,
        disclosure,
        notes_provider,
    }
}

/// Lock the shared transcript store for one read, or fail with a stable message the UI can tell
/// apart from "zero transcripts" (`transcripts.js`'s error state vs. its empty state). Same
/// lock-error shape as `with_providers`/`with_deck` — never panics on a poisoned lock, surfaces it
/// as an `Err` instead.
fn with_transcript_db<T>(
    state: &State<'_, AppState>,
    f: impl FnOnce(&selahcue_data::Database) -> selahcue_data::Result<T>,
) -> Result<T, String> {
    let guard = state
        .transcript_db
        .as_ref()
        .ok_or_else(|| "transcript store unavailable".to_string())?;
    let db = guard.lock().map_err(|e| format!("transcript lock: {e}"))?;
    f(&db).map_err(|e| e.to_string())
}

/// List every persisted transcript, most recent first (86akcffvt AC1).
#[tauri::command]
async fn transcript_list(state: State<'_, AppState>) -> Result<Vec<TranscriptSummaryView>, String> {
    with_transcript_db(&state, selahcue_data::transcript_repo::list)
        .map(|rows| rows.into_iter().map(TranscriptSummaryView::from).collect())
}

/// Whether transcript `id` has a persisted sermon-note draft — fault-isolated (86akcffy0, Sana
/// security review F4): a query error here (most plausibly "no such table: sermon_note" on a
/// store from a build older than the v21 migration that added it, since
/// `Database::open_existing_readonly` never migrates) degrades to the honest, pre-this-ticket
/// default (`false`) instead of propagating — `notes_generated` is a nice-to-have annotation on
/// an otherwise successful transcript read; it must never be the reason reading a transcript
/// stops working entirely.
fn notes_generated_for(db: &selahcue_data::Database, id: i64) -> bool {
    selahcue_data::sermon_note_repo::find_by_transcript(db, id)
        .unwrap_or_else(|e| {
            eprintln!(
                "selahcue-operator: could not check for a persisted sermon-note draft \
                 (transcript {id}), treating as not generated: {e}"
            );
            None
        })
        .is_some()
}

/// Read one transcript back in full (86akcffvt AC2). `NotFound` (a stale/deleted id) surfaces as
/// the repo's own stable, speech-free message ("row not found" — see `transcript_repo`'s FR-082
/// guarantee), never a fabricated one.
#[tauri::command]
async fn transcript_get(
    id: i64,
    state: State<'_, AppState>,
) -> Result<TranscriptDetailView, String> {
    let (t, notes_generated) = with_transcript_db(&state, |db| {
        let t = selahcue_data::transcript_repo::load(db, id)?;
        let notes_generated = notes_generated_for(db, id);
        Ok((t, notes_generated))
    })?;
    // Fault-isolated exactly like `notes_generated_for` above (86akgqdxr): a failure reading the
    // draft's actual content must never block the transcript/detections from being shown — it
    // degrades to "no draft", the same honest floor `notes_generated_for` already established for
    // its own boolean.
    //
    // The error is deliberately NOT interpolated (Sana, PR #50 F1): `Backend::load_sermon_note_
    // draft`'s `Remote` path stringifies whatever `TransportError` `RemoteOperator::
    // load_sermon_note_draft` returns, and its non-conforming-reply branch
    // (`selahcue-app/src/operator.rs`) builds that via `TransportError::Protocol(format!("expected
    // sermon_note_draft, got: {other:?}"))` — a `Debug` dump of the ENTIRE unexpected
    // `ServerMessage`, which can be `OperatorState` carrying live `transcript`/`partial_transcript`/
    // `detections` text verbatim. Reaching this needs a non-conforming host reply (version skew, a
    // host bug, or a request/response desync — `ControlClient::command` does not correlate
    // `request_id`), but FR-082 (no transcript/detection text reaches a diagnostic verbatim) covers
    // that text the same as draft text, so this path drops the error entirely rather than assume
    // any given `TransportError` variant is safe to print.
    let draft_view = match state.backend.load_sermon_note_draft(id).await {
        Ok(view) => view,
        Err(_) => {
            eprintln!(
                "selahcue-operator: could not load the sermon-note draft for transcript {id}, \
                 showing the transcript without it"
            );
            None
        }
    };
    Ok(build_transcript_detail_view(
        t,
        notes_generated,
        draft_view.as_ref(),
    ))
}

#[cfg(test)]
mod transcript_view_tests {
    use super::*;
    use selahcue_data::{transcript_repo, Database};

    fn fixture_db() -> Database {
        let db = Database::open_in_memory().expect("in-memory db opens");
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service — Aug 4".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .expect("create transcript");
        transcript_repo::append_segment(&db, id, 0, 4_000, "Good morning, church.")
            .expect("append segment");
        transcript_repo::append_segment(&db, id, 4_000, 9_000, "Turn with me to Romans eight.")
            .expect("append segment");
        transcript_repo::end(&db, id, 9_000).expect("end transcript");
        db
    }

    /// The frontend contract field names, pinned the same way `providers_view_tests` pins
    /// `ProvidersView` — `transcripts.js` reads these names verbatim, so a rename here must ship
    /// in the SAME merge request as the JS that reads it.
    #[test]
    fn the_summary_view_field_names_are_pinned() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let view: TranscriptSummaryView = rows.into_iter().next().expect("one row").into();
        let v = serde_json::to_value(&view).expect("view serialises");
        let obj = v.as_object().expect("object");
        let mut got: Vec<&str> = obj.keys().map(String::as_str).collect();
        got.sort_unstable();
        let mut expected = vec![
            "id",
            "label",
            "provider",
            "started_at_ms",
            "ended_at_ms",
            "segment_count",
        ];
        expected.sort_unstable();
        assert_eq!(got, expected, "the summary view contract changed; transcripts.js must change in the SAME merge request");
    }

    #[test]
    fn the_detail_view_field_names_are_pinned() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let id = rows[0].id;
        let t = transcript_repo::load(&db, id).expect("load");
        // Built through the SAME `build_transcript_detail_view` `transcript_get` itself calls
        // (86akgqdxr) — this pinned test can no longer drift from the real construction path the
        // way a hand-copied struct literal could.
        let view = build_transcript_detail_view(t, false, None);
        let v = serde_json::to_value(&view).expect("view serialises");
        let obj = v.as_object().expect("object");
        let mut got: Vec<&str> = obj.keys().map(String::as_str).collect();
        got.sort_unstable();
        let mut expected = vec![
            "id",
            "label",
            "provider",
            "started_at_ms",
            "ended_at_ms",
            "segments",
            "notes_generated",
            "detections",
            "corrections",
            "draft",
            "scripture_verification_note",
            "ai_generated",
            "ai_label",
            "disclosure",
            "notes_provider",
        ];
        expected.sort_unstable();
        assert_eq!(got, expected, "the detail view contract changed; transcripts.js must change in the SAME merge request");

        let seg_obj = v["segments"][0].as_object().expect("segment is an object");
        let mut seg_got: Vec<&str> = seg_obj.keys().map(String::as_str).collect();
        seg_got.sort_unstable();
        let mut seg_expected = vec!["id", "start_ms", "end_ms", "text"];
        seg_expected.sort_unstable();
        assert_eq!(seg_got, seg_expected, "the segment view contract changed; transcripts.js must change in the SAME merge request");

        // No detections/corrections seeded by `fixture_db` — the arrays must still be present as
        // `[]`, never omitted, so `transcripts.js` can rely on the key existing either way.
        assert_eq!(v["detections"], serde_json::json!([]));
        assert_eq!(v["corrections"], serde_json::json!([]));
        assert_eq!(
            v["draft"],
            serde_json::Value::Null,
            "no draft was passed in"
        );
    }

    /// The load-bearing behaviour: full text back, in order, none dropped — not a tail, not a
    /// sample (86akcffvt AC2). A regression that truncated/paginated at the Rust layer would
    /// still pass a naive "some segments came back" check; this pins the EXACT count and order.
    #[test]
    fn transcript_get_returns_every_segment_in_order_not_a_tail() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let id = rows[0].id;
        let t = transcript_repo::load(&db, id).expect("load");
        let view = build_transcript_detail_view(t, false, None);
        assert_eq!(
            view.segments.len(),
            2,
            "both segments came back, not a tail"
        );
        assert_eq!(view.segments[0].text, "Good morning, church.");
        assert_eq!(
            view.segments[1].text, "Turn with me to Romans eight.",
            "segment order is preserved end to end"
        );
    }

    #[test]
    fn a_missing_transcript_reports_not_found_not_a_panic() {
        let db = Database::open_in_memory().expect("in-memory db opens");
        let err = transcript_repo::load(&db, 999)
            .expect_err("a missing transcript id is NotFound, not Ok");
        assert_eq!(err.to_string(), "row not found");
    }

    // --- 86akgqdxr: detections + corrections + saved-draft content on `TranscriptDetailView` ---

    /// A fixture transcript that ALSO carries two detections (one with a known source segment,
    /// one with none — the documented `0` sentinel) and one correction, on top of `fixture_db`'s
    /// two segments.
    fn fixture_db_with_detections_and_correction() -> (Database, i64) {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let id = rows[0].id;
        let t = transcript_repo::load(&db, id).expect("load");
        let first_segment_id = t.segments[0].id as i64;
        transcript_repo::append_detection(&db, id, Some(first_segment_id), "Romans 8:28", 95)
            .expect("append detection with a known segment");
        transcript_repo::append_detection(&db, id, None, "John 3:16", 70)
            .expect("append detection with no known segment");
        transcript_repo::correct_segment(&db, first_segment_id, "Good morning, everyone.", 5_000)
            .expect("correct a segment");
        (db, id)
    }

    /// Every detection persisted against the transcript comes back — reference, confidence, and
    /// the segment it was traced to (86akgqdxr AC1). This is the load-bearing behaviour the whole
    /// ticket exists to add: before this change, `transcript_repo::load` already read these rows
    /// and `TranscriptDetailView` silently dropped them.
    #[test]
    fn every_persisted_detection_is_forwarded_to_the_wire_view() {
        let (db, id) = fixture_db_with_detections_and_correction();
        let t = transcript_repo::load(&db, id).expect("load");
        let view = build_transcript_detail_view(t, false, None);
        assert_eq!(view.detections.len(), 2, "both detections came back");
        assert_eq!(view.detections[0].reference, "Romans 8:28");
        assert_eq!(view.detections[0].confidence, 95);
        assert_ne!(
            view.detections[0].source_segment, 0,
            "a detection with a known segment must not read back as the 'unknown' sentinel"
        );
        assert_eq!(view.detections[1].reference, "John 3:16");
        assert_eq!(
            view.detections[1].source_segment, 0,
            "a detection with no known segment reads back as the documented 0 sentinel, \
             carried through unchanged rather than reinterpreted at this layer"
        );
    }

    /// A transcript with no detections shows an empty array, never a missing key or `null` —
    /// `transcripts.js` renders its empty state off `detections.length === 0`, not off the key's
    /// presence (86akgqdxr AC3, empty state is not "blank" but is also not absent from the wire).
    #[test]
    fn no_detections_forwards_an_empty_array_not_a_missing_field() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let t = transcript_repo::load(&db, rows[0].id).expect("load");
        let view = build_transcript_detail_view(t, false, None);
        assert!(view.detections.is_empty(), "fixture_db seeds no detections");
        let v = serde_json::to_value(&view).expect("view serialises");
        assert_eq!(
            v["detections"],
            serde_json::json!([]),
            "an empty Vec must serialise as [], not be omitted"
        );
    }

    /// Any existing correction is forwarded read-only (86akgqdxr: "the correction layer...
    /// reachable from one screen") — this ticket does not add a way to WRITE one (see
    /// `SegmentCorrectionView`'s doc comment), only to display what already exists.
    #[test]
    fn an_existing_correction_is_forwarded_read_only() {
        let (db, id) = fixture_db_with_detections_and_correction();
        let t = transcript_repo::load(&db, id).expect("load");
        let view = build_transcript_detail_view(t, false, None);
        assert_eq!(view.corrections.len(), 1);
        assert_eq!(
            view.corrections[0].corrected_text,
            "Good morning, everyone."
        );
    }

    fn fixture_draft_view() -> selahcue_lan::protocol::SermonNoteDraftView {
        selahcue_lan::protocol::SermonNoteDraftView {
            title: "Sunday Service Notes".to_string(),
            summary: Some("A short summary.".to_string()),
            sections_json: serde_json::json!([
                {"heading": "Main points", "items": ["Faith", "Hope"], "points": []}
            ])
            .to_string(),
            scriptures_json: serde_json::json!(["Romans 8:28"]).to_string(),
            ai_generated: true,
            disclosure: Some("AI-generated. Verify before use.".to_string()),
            provider: "OpenAI".to_string(),
            model: Some("gpt-test".to_string()),
            created_at_ms: 1_000,
            edited_at_ms: 2_000,
        }
    }

    /// When a draft exists, its ACTUAL content reaches the wire — title, summary, sections,
    /// scriptures — not merely `notes_generated: true` (86akgqdxr AC2, the whole point of this
    /// ticket's notes half). Reuses `sermon_note_draft_json` unchanged, so the caveat/
    /// scripture-verdict vocabulary is byte-identical to Settings' own persisted-draft view.
    #[test]
    fn a_saved_draft_forwards_its_real_content_not_just_the_generated_flag() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let t = transcript_repo::load(&db, rows[0].id).expect("load");
        let draft_view = fixture_draft_view();
        let view = build_transcript_detail_view(t, true, Some(&draft_view));
        assert!(view.notes_generated);
        let draft = view.draft.expect("a draft was passed in");
        assert_eq!(draft["title"], "Sunday Service Notes");
        assert_eq!(draft["summary"], "A short summary.");
        assert_eq!(draft["scriptures"], serde_json::json!(["Romans 8:28"]));
        assert_eq!(view.ai_generated, Some(true));
        assert_eq!(
            view.disclosure.as_deref(),
            Some("AI-generated. Verify before use.")
        );
        assert_eq!(view.notes_provider.as_deref(), Some("OpenAI"));
    }

    /// No saved draft: every draft-content field is `None`/`null`, independent of whatever
    /// `notes_generated` happens to say (they are two separate reads, deliberately — see
    /// `build_transcript_detail_view`'s doc comment).
    #[test]
    fn no_saved_draft_leaves_every_draft_field_none() {
        let db = fixture_db();
        let rows = transcript_repo::list(&db).expect("list");
        let t = transcript_repo::load(&db, rows[0].id).expect("load");
        let view = build_transcript_detail_view(t, false, None);
        assert!(view.draft.is_none());
        assert!(view.scripture_verification_note.is_none());
        assert!(view.ai_generated.is_none());
        assert!(view.ai_label.is_none());
        assert!(view.disclosure.is_none());
        assert!(view.notes_provider.is_none());
    }
}

// ---------------------------------------------------------------------------------------------
// `open_transcript_db_at` (86akcffvt review, Sana F1 / Cody Blocker): this shell must never
// create, write to, or migrate the shared transcript store it only reads. These tests exercise
// the FULL operator-level path (directory resolution + open), not just the crate-level
// constructor `selahcue-data`'s own tests already cover — the two layers can regress
// independently (e.g. a future edit could re-introduce `create_dir_all` here, or swap the call
// back to plain `open`), so both are tested. Mutation-verified: swapping the
// `open_existing_readonly` call in `open_transcript_db_at` back to plain `Database::open` turns
// (a) and (b) red together (see the ticket's evidence for the recorded run).
// ---------------------------------------------------------------------------------------------
#[cfg(test)]
mod transcript_db_open_tests {
    use super::*;
    use selahcue_data::{transcript_repo, Database};

    #[test]
    fn a_folder_present_but_no_store_yet_yields_none_and_creates_no_file() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store_path = dir.path().join("selahcue.db3");
        assert!(!store_path.exists(), "premise: no store in the folder yet");

        let result = open_transcript_db_at(dir.path());

        assert!(
            result.is_none(),
            "a folder with no store yet must report unavailable, not open one"
        );
        assert!(
            !store_path.exists(),
            "the 'read-only' open must not have created a store where none existed \
             (this is the exact FR-154 plaintext-lock-in shape: make operator run standalone \
             before selahcue-desktop ever has, or a store deleted by hand to reset history)"
        );
    }

    #[test]
    fn a_zero_byte_placeholder_yields_none_and_stays_zero_bytes() {
        let dir = tempfile::tempdir().expect("temp dir");
        let store_path = dir.path().join("selahcue.db3");
        std::fs::write(&store_path, []).expect("write empty placeholder");

        let result = open_transcript_db_at(dir.path());

        assert!(
            result.is_none(),
            "a zero-byte placeholder is not a real store and must report unavailable"
        );
        assert_eq!(
            store_path.metadata().expect("metadata").len(),
            0,
            "the refused open must not have written a schema into the placeholder"
        );
    }

    #[test]
    fn a_real_existing_store_opens_and_lists_its_transcript_positive_control() {
        // Positive control: the two refusal tests above prove nothing without proof this same
        // function still does its one real job against an ordinary, real store.
        let dir = tempfile::tempdir().expect("temp dir");
        let store_path = dir.path().join("selahcue.db3");
        {
            let db = Database::open(&store_path).expect("create the real store");
            transcript_repo::create(
                &db,
                &transcript_repo::NewTranscript {
                    label: "Sunday Service".to_string(),
                    provider: "manual".to_string(),
                    plan_id: None,
                    started_at_ms: 1_722_760_800_000,
                },
            )
            .expect("seed one transcript");
        }

        let db = open_transcript_db_at(dir.path())
            .expect("a real, ordinary store at this path must open");

        let rows = transcript_repo::list(&db).expect("list succeeds");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].label, "Sunday Service");
    }

    #[test]
    fn a_store_from_a_newer_build_still_opens_and_reads_correctly() {
        // What "the newer-schema-version case" resolves to for THIS constructor (see
        // `Database::open_existing_readonly`'s own doc comment for the full reasoning): every
        // migration to date is purely additive, and this path never migrates in either
        // direction, so refusing a newer-but-otherwise-normal store would only break the
        // reverse case this repo's shared checkouts hit in practice (an older read-only build
        // pointed at a store a newer sibling build already migrated forward) while protecting
        // nothing (there is no write to protect here). The one invariant under test is that the
        // version on disk is left exactly as found.
        let dir = tempfile::tempdir().expect("temp dir");
        let store_path = dir.path().join("selahcue.db3");
        {
            let db = Database::open(&store_path).expect("create the real store");
            transcript_repo::create(
                &db,
                &transcript_repo::NewTranscript {
                    label: "Sunday Service".to_string(),
                    provider: "manual".to_string(),
                    plan_id: None,
                    started_at_ms: 1_722_760_800_000,
                },
            )
            .expect("seed one transcript");
            let future = selahcue_data::migrations::target_version() + 1;
            db.conn()
                .execute_batch(&format!("PRAGMA user_version = {future};"))
                .expect("simulate a sibling build's future migration");
        }

        let db = open_transcript_db_at(dir.path()).expect("a newer-schema store still opens");

        assert_eq!(
            db.schema_version().expect("read version"),
            selahcue_data::migrations::target_version() + 1,
            "the version on disk must be left exactly as found — never migrated"
        );
        let rows = transcript_repo::list(&db).expect("list still succeeds");
        assert_eq!(rows.len(), 1);
    }
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
///
/// The response also carries the copy's own id as `new_id` (present only when `id` resolved to a
/// real deck), the same additive pattern `deck_restore` already uses for `restored_name`: the copy
/// is minted a FRESH id (`DeckLibrary::duplicate`), so a caller that wants to act on the new deck
/// specifically (PME-053's "New presentation → Start from → Duplicate…", which renames the copy to
/// whatever the operator typed and opens it) cannot infer it from `id` and has no other way to learn
/// it from this response.
#[tauri::command]
async fn deck_duplicate(id: u64, state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    with_deck_and_library(&state, |ws, lib| {
        let new_id = lib.duplicate(DeckId(id)).map(|d| d.id().0);
        let mut view = library_view(lib, ws.open_deck().id());
        if let (Some(new_id), Some(obj)) = (new_id, view.as_object_mut()) {
            obj.insert("new_id".into(), serde_json::Value::from(new_id));
        }
        view
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

/// Import an image into the media library via the native file picker, validated (FR-138 /
/// 86ak0qmzv) before it is staged, recording its real byte size. Video/audio disk import (and
/// on-output playback) is a deferred affordance (ADR-0020).
///
/// A cancelled dialog or a validation refusal are both `Ok` with the plan unchanged — matching
/// `pick_image`'s own "a refusal is not a transport failure" choice, but expressed differently
/// here because `deck_import_image` already had a real `Result` error channel and its one JS
/// caller already routes a thrown error through `pmShowErrorRaw` (see `dist/app.js`'s `pm-import`
/// handler), so a refusal surfaces to the operator as the command's own `Err`.
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
    let Some(picked) = picked else {
        return with_deck(&state, |_| ()); // the user cancelled — no-op, current view back
    };
    // Same offload as `pick_image`: validation does a bounded read of a user-chosen file and
    // must not run on the shared Tokio worker pool.
    let path =
        tauri::async_runtime::spawn_blocking(move || safe_import::validate_picked_image(&picked))
            .await
            .map_err(|join_err| format!("internal error validating that file: {join_err}"))?
            .map_err(|e| e.to_string())?;
    with_deck(&state, |w| {
        let size = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
        w.import_media(
            path.to_string_lossy().into_owned(),
            "image",
            size,
            None,
            None,
            None,
        );
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
// --- Plan publish / hand-off (FR-006) + the plan lifecycle actions (FR-005). Each returns the
//     fresh view, like every other action, so the console re-renders from host truth in one
//     round trip. Whether the surface OFFERS them is the shell's decision, driven by
//     `view.viewer.can_edit`; the host refuses them regardless if the role does not hold
//     `EditPlan`, so hiding a control is never what protects the plan. ---
#[tauri::command]
async fn publish_plan(state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.publish_plan().await
}
#[tauri::command]
async fn new_plan(name: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.new_plan(name).await
}
#[tauri::command]
async fn template_plan(
    template: String,
    name: String,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.template_plan(template, name).await
}
#[tauri::command]
async fn duplicate_plan(name: String, state: State<'_, AppState>) -> Result<OperatorView, String> {
    state.backend.duplicate_plan(name).await
}
#[tauri::command]
async fn import_plan(
    name: String,
    items: Vec<ImportItemView>,
    state: State<'_, AppState>,
) -> Result<OperatorView, String> {
    state.backend.import_plan(name, items).await
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
fn detector_observations() -> (bool, Option<String>, Option<String>, Option<String>) {
    (
        listening::is_listening(),
        listening::last_failure(),
        listening::provider_label(),
        listening::engine_note(),
    )
}

/// Without the `stt` feature there is no detector in this binary at all — so it is not idle,
/// not failed, and cannot be retried. Reporting anything else would be a fabrication.
#[cfg(not(feature = "stt"))]
fn detector_observations() -> (bool, Option<String>, Option<String>, Option<String>) {
    (false, None, None, None)
}

/// Whether a detector is compiled into this binary. A build constant, not a runtime condition.
const DETECTOR_COMPILED: bool = cfg!(feature = "stt");

/// The detector's current state, derived by the pure core rule.
fn current_detector_state() -> DetectorState {
    let (worker_running, last_failure, _, _) = detector_observations();
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
    /// Why `provider` is not what Settings' `transcription_mode` says, or that it changed
    /// mid-service (86akby7th) — e.g. Cloud selected without consent, or a live Cloud session
    /// that failed over to on-device. `None` when there is nothing to explain.
    note: Option<String>,
}

fn detection_health_reply() -> DetectionHealthReply {
    let state = current_detector_state();
    let (_, last_failure, provider, note) = detector_observations();
    DetectionHealthReply {
        state: state.tag(),
        provider,
        error: last_failure,
        can_retry: state.retry_request().is_some(),
        note,
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

/// Longest the endpoint descriptor file is trusted to be. It is four short strings of JSON —
/// real ones are under 300 bytes — so this is generous headroom, not a working limit; its job
/// is bounding `read_to_string` against a file an unprivileged local writer controls (security
/// review, Sana S-3: "cap the read... no size limit on a file an attacker controls").
const MAX_ENDPOINT_FILE_LEN: u64 = 4096;

/// Read and validate the endpoint descriptor file, applying the checks pinned TLS itself cannot
/// (security review, Sana S-3):
///
/// - **Mode `0600` (Unix only).** Before Tier 2a, this file was read exactly once, at process
///   startup — a narrow window. The reconnect loop re-reads it for the whole life of the
///   session, turning a locally-writable path into a standing target: on a multi-user machine
///   `temp_dir()` (e.g. `/tmp`) is typically world-writable, so another local account could
///   pre-create the file while no real host is running. `selahcue-desktop`'s own writer already
///   sets `0600` (`write_endpoint`, matching this exact `set_permissions`/`Permissions::from_mode`
///   pattern) — refusing anything else here is the read-side half of that same contract. This
///   alone is the actual boundary: the OS already refuses `read_to_string` on a `0600` file this
///   process does not own (a differently-owned `0600` planted file is unreadable to us
///   regardless of any check we add), so the exposure this closes is specifically a file some
///   other local account made WORLD- or GROUP-readable so our process even could read it.
/// - **Bounded read.** `MAX_ENDPOINT_FILE_LEN` caps the read itself, not just the parsed result.
///
/// **Not implemented: pin continuity across reconnects.** An earlier draft of this fix required
/// a reconnect's pin to match the one the console originally attached to. That is unsound here:
/// `selahcue-desktop::run_server` generates a FRESH `SelfSigned` identity (and a fresh random
/// token) on every process start — nothing about this system persists a stable identity across
/// a restart, by design. A pin-continuity check would therefore refuse the exact scenario this
/// feature exists to recover — the output window crashing and restarting — indistinguishably
/// from an actual attack, defeating Tier 2a entirely. The mode check above is the fix that
/// matches the real trust boundary (same local user), without that self-defeat.
fn read_endpoint() -> Option<Endpoint> {
    read_endpoint_at(&endpoint_file_path())
}

/// [`read_endpoint`]'s real body, against an injected path — tests use a private `tempfile`
/// path instead of the shared, machine-wide `endpoint_file_path()` (touching that file races
/// every other process on the machine that reads/writes it by convention).
///
/// **Check-then-use, closed (security review, Sana S-3a).** An earlier version of this function
/// checked the path's metadata (`std::fs::metadata`) and then read it (`std::fs::read_to_string`)
/// as two independent path resolutions — in the threat this guards against, the planted file is
/// owned by a DIFFERENT local account, which can change its mode between those two syscalls.
/// Sana reproduced this live: replaying the exact shape (an attacker thread flipping the mode
/// between `0o600` and `0o644` while this function's shape ran in a loop) let ~9.4% of attempts
/// pass the mode gate and then read bytes the gate would have rejected. Opening the file ONCE
/// and taking every check (size, mode) from `File::metadata()` — an `fstat` on the SAME open
/// file descriptor, not a fresh path lookup — makes the check and the read describe the same
/// bytes by construction: there is no window between them for the file to be swapped or
/// re-permissioned. `Read::take` bounds the read itself (not just re-checking `meta.len()`,
/// which reads as 0 for non-regular files like a FIFO and would otherwise be advisory only).
fn read_endpoint_at(path: &std::path::Path) -> Option<Endpoint> {
    use std::io::Read;
    let file = std::fs::File::open(path).ok()?;
    let meta = file.metadata().ok()?;
    if meta.len() > MAX_ENDPOINT_FILE_LEN {
        eprintln!(
            "SelahCue operator: endpoint descriptor at {} exceeds {MAX_ENDPOINT_FILE_LEN} bytes — refusing to read it.",
            path.display()
        );
        return None;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = meta.permissions().mode() & 0o777;
        if mode != 0o600 {
            eprintln!(
                "SelahCue operator: endpoint descriptor at {} is not mode 0600 (found {:o}) — refusing to trust it.",
                path.display(),
                mode
            );
            return None;
        }
    }
    let mut data = String::new();
    file.take(MAX_ENDPOINT_FILE_LEN)
        .read_to_string(&mut data)
        .ok()?;
    serde_json::from_str(&data).ok()
}

/// Parse, validate and dial an [`Endpoint`]. Enforces loopback-only — this descriptor is a
/// same-machine convenience file, not a remote pairing credential, and nothing upstream
/// otherwise restricts `ep.addr` to loopback, so a substituted descriptor could point the
/// console at an off-box service (security review, Sana S-3).
async fn connect_remote(ep: &Endpoint) -> Result<RemoteOperator, String> {
    let addr: SocketAddr = ep
        .addr
        .parse()
        .map_err(|_| format!("bad addr: {}", ep.addr))?;
    if !addr.ip().is_loopback() {
        return Err("endpoint address is not loopback — refusing to dial".to_string());
    }
    let pin = CertPin::from_hex(&ep.pin).ok_or_else(|| "bad pin".to_string())?;
    RemoteOperator::connect(addr, "localhost", pin, &ep.device, &ep.token)
        .await
        .map_err(|e| e.to_string())
}

/// The two checks `connect_remote`/`read_endpoint_at` added for Sana's S-3 review had no test —
/// "a control nothing consumes" is the exact defect class this repo's own bounded-memory-test
/// discipline warns about applied to a security control instead of a memory bound. Both would
/// previously have been deletable with no assertion firing; these two close that.
#[cfg(test)]
mod endpoint_guard_tests {
    use super::*;
    // Both imports are used only by the `#[cfg(unix)]` tests below (`write!` into a `File`,
    // and `Permissions::from_mode`) — gating them the same way avoids an `unused_imports` /
    // `-D warnings` failure on non-Unix CI (this exact mistake broke Windows CI once already
    // on this branch: the FIRST cut gated only `PermissionsExt`, leaving `Write` unused there).
    #[cfg(unix)]
    use std::io::Write;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;

    /// A non-loopback address must be refused before any network attempt — proven by using an
    /// address (`203.0.113.1`, TEST-NET-3, RFC 5737: guaranteed never routable) that would hang
    /// or fail for an unrelated reason if this check were not the thing that rejected it.
    #[tokio::test]
    async fn a_non_loopback_endpoint_is_refused_before_dialling() {
        let ep = Endpoint {
            addr: "203.0.113.1:9".into(),
            pin: "00".repeat(32),
            device: "producer".into(),
            token: "tok".into(),
        };
        let err = connect_remote(&ep)
            .await
            .err()
            .expect("a non-loopback endpoint must never be dialled");
        assert!(
            err.contains("not loopback"),
            "refusal must name the real reason, not surface as e.g. a connect timeout: {err}"
        );
    }

    /// A loopback address passes the check this test targets (it may still fail to connect,
    /// which is a DIFFERENT, expected error — nothing is listening) — proving the loopback
    /// branch is a real gate, not one that rejects everything regardless of the address.
    #[tokio::test]
    async fn a_loopback_endpoint_clears_the_address_check() {
        let ep = Endpoint {
            addr: "127.0.0.1:1".into(), // nothing listens on port 1; connect itself must fail
            pin: "00".repeat(32),
            device: "producer".into(),
            token: "tok".into(),
        };
        let err = connect_remote(&ep)
            .await
            .err()
            .expect("nothing listens on 127.0.0.1:1, so this must still fail");
        assert!(
            !err.contains("not loopback"),
            "a loopback address must clear the loopback check — got: {err}"
        );
    }

    /// A `0644` descriptor (world/group-readable) is exactly the exposure the mode check exists
    /// to close (security review, Sana S-3) — refused, not silently trusted. Unix-only: the mode
    /// check itself (`read_endpoint_at`) is `#[cfg(unix)]` — there is no POSIX-style mode bit on
    /// Windows for it to check.
    #[cfg(unix)]
    #[test]
    fn a_world_readable_descriptor_is_refused() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("endpoint.json");
        std::fs::write(
            &path,
            br#"{"addr":"127.0.0.1:1","pin":"00","device":"d","token":"t"}"#,
        )
        .expect("write descriptor");
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o644))
            .expect("chmod 0644");
        assert!(
            read_endpoint_at(&path).is_none(),
            "a 0644 (world-readable) descriptor must be refused, not trusted"
        );
    }

    /// Positive control for the mode check: the SAME descriptor, `0600`, is accepted — proving
    /// the refusal above is a real branch (a mode check, not something that rejects every file
    /// regardless of its permissions). Unix-only, same reason as the test above.
    #[cfg(unix)]
    #[test]
    fn a_0600_descriptor_is_accepted() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("endpoint.json");
        std::fs::write(
            &path,
            br#"{"addr":"127.0.0.1:1","pin":"00","device":"d","token":"t"}"#,
        )
        .expect("write descriptor");
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600))
            .expect("chmod 0600");
        let ep = read_endpoint_at(&path).expect("a 0600 descriptor must be accepted");
        assert_eq!(ep.addr, "127.0.0.1:1");
    }

    /// A regular file over `MAX_ENDPOINT_FILE_LEN` is refused — for a regular file this is
    /// caught by the `fstat`-derived size check. `Read::take` is the SEPARATE, defense-in-depth
    /// bound for a non-regular file (e.g. a FIFO, where `stat` reports `len() == 0` and the size
    /// check alone would be fooled); that path needs a real FIFO to exercise and is not covered
    /// by this test, which asserts the ordinary case: a big honest file is still refused.
    /// Unix-only only because `set_permissions`/`from_mode` are — the size check itself runs
    /// unconditionally in `read_endpoint_at`; the chmod here exists only so the file additionally
    /// clears the (also-tested) mode check and this test isolates the size check alone.
    #[cfg(unix)]
    #[test]
    fn an_oversized_descriptor_is_refused() {
        // A control that guards another control can be dead in a way a careless test misses
        // (`implementation/desktop/CLAUDE.md`'s bounded-memory-test section): a first version
        // of this test padded INSIDE the JSON value out past the cap, so `Read::take` alone
        // truncated it into invalid JSON and the size check was never actually exercised —
        // found by mutation (security review round 3, Sana S-9): neutering the size check left
        // this test green. Fixed by making the JSON object itself COMPLETE AND VALID at exactly
        // `MAX_ENDPOINT_FILE_LEN` bytes, with only WHITESPACE — which `serde_json` tolerates
        // trailing — appended afterward to push the file past the cap. A truncated (first
        // `MAX_ENDPOINT_FILE_LEN` bytes) read of THIS file parses cleanly, so only the size
        // check (not truncation) can be what refuses it.
        let prefix = r#"{"addr":"127.0.0.1:1","pin":"00","device":"d"#;
        let suffix = r#"","token":"t"}"#;
        let target_len = MAX_ENDPOINT_FILE_LEN as usize;
        let pad_len = target_len
            .checked_sub(prefix.len() + suffix.len())
            .expect("MAX_ENDPOINT_FILE_LEN must be large enough to hold the fixed JSON shape");
        let json = format!("{prefix}{}{suffix}", "x".repeat(pad_len));
        assert_eq!(
            json.len(),
            target_len,
            "premise: the JSON object itself must be exactly MAX_ENDPOINT_FILE_LEN bytes, or \
             this proves nothing about the size check specifically"
        );

        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("endpoint.json");
        let mut f = std::fs::File::create(&path).expect("create");
        write!(f, "{json}").expect("write the complete, valid, exactly-sized JSON object");
        // Trailing WHITESPACE ONLY, after the closing brace — grows the file past the cap
        // without changing what a first-N-bytes truncated read would see.
        write!(f, "{}", " ".repeat(1024)).expect("write trailing whitespace past the cap");
        drop(f);
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600))
            .expect("chmod 0600");

        assert!(
            read_endpoint_at(&path).is_none(),
            "a descriptor over MAX_ENDPOINT_FILE_LEN must be refused by the SIZE check, even \
             when its first MAX_ENDPOINT_FILE_LEN bytes alone would parse cleanly"
        );
    }
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
    podcast_show_notes: bool,
    short_description: bool,
}

#[derive(serde::Serialize)]
struct QuotaView {
    used: u32,
    limit: u32,
    remaining: u32,
    resets_label: String,
}

/// Who is generating the sermon notes, for the panel's FR-132 disclosure.
///
/// `Some` exactly when notes can actually be generated, `None` exactly when they cannot. That tie
/// is the point: there is no way to report the feature as available without naming the provider
/// behind it, and no way to name a provider while reporting the feature unavailable. It is asserted
/// in both directions by `notes_provider_matches_availability_in_both_directions`.
#[derive(serde::Serialize)]
struct NotesProviderView {
    /// Machine-readable: `"openai"` | `"selahcue_hosted"`. Branch on this, not on the display name.
    kind: String,
    /// Human-readable provider name — this is the string the disclosure renders (FR-132).
    name: String,
    /// The model actually called. Empty for the hosted service, which owns its own model choice.
    model: String,
    /// True when the credential is a developer key on this machine rather than an account with the
    /// hosted service. Surfaced so the panel can say the throwaway posture out loud instead of
    /// implying a shipped, supported configuration.
    developer_key: bool,
}

/// Who serves Cloud transcription, for the transcription card's honest-readiness disclosure
/// (86akby7th) — the same shape as [`NotesProviderView`], for the same reason: `Some` exactly
/// when `transcription_available` is true, never a provider named while unavailable and never
/// availability claimed with no provider to name.
#[derive(serde::Serialize)]
struct TranscriptionProviderView {
    /// Machine-readable: `"deepgram"`. Branch on this, not on the display name.
    kind: String,
    /// Human-readable provider name — the string the card's disclosure renders (FR-120/FR-132).
    name: String,
    /// The model actually requested (e.g. `"nova-3"`).
    model: String,
    /// True while this is the Phase 1 developer-key path rather than a server-minted grant
    /// token (Phase 2 sets it false) — mirrors `NotesProviderView::developer_key`.
    developer_key: bool,
}

/// Availability + named provider for Cloud transcription, from an **already-resolved**
/// [`selahcue_stt_cloud::readiness::CloudSttStatus`].
///
/// Split from [`transcription_status`] for the same reason [`notes_status_from`] is split from
/// [`notes_status`], after the same mistake: `transcription_status()` resolves from real build
/// `cfg!` + the process environment, so a test calling it directly can only ever observe the
/// ONE state this compilation and this environment happen to be in — which can never be the
/// state where `transcription_available` must be **true**, the one place a hardcoded `false`
/// would be caught. Taking the resolved status as a parameter — built from
/// `CloudSttReadiness::{NotInBuild,KeyMissing,Ready}.status()`, all three constructible in a
/// test regardless of feature flags — makes every state reachable.
fn transcription_status_from(
    status: selahcue_stt_cloud::readiness::CloudSttStatus,
) -> (bool, Option<TranscriptionProviderView>) {
    let provider = status.provider.map(|p| TranscriptionProviderView {
        kind: p.kind.to_string(),
        name: p.name.to_string(),
        model: p.model.to_string(),
        developer_key: p.developer_key,
    });
    (status.ready, provider)
}

/// This build's and this environment's real Cloud-transcription readiness. Always callable:
/// `selahcue-stt-cloud` is an unconditional dependency, so this build can report honestly
/// (`not_in_build`) even when `cloud-stt` is off, exactly the way `stt_ready()` reports
/// `not_in_build` for on-device when `stt` is off.
fn transcription_status() -> (bool, Option<TranscriptionProviderView>) {
    transcription_status_from(selahcue_stt_cloud::readiness::readiness().status())
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
    /// How notes are served right now. Four honest states:
    ///
    /// - `"not_configured"` — no direct-provider path is compiled in and no hosted service is
    ///   configured. A stock build. Nothing can generate notes.
    /// - `"key_missing"` — a direct-provider path IS compiled in, but no developer key is present.
    ///   Distinct from the above on purpose: "you have not supplied a key" is actionable where
    ///   "unavailable" is not, and collapsing the two is the same under-reporting bug one level down.
    /// - `"direct_provider"` — a third-party provider is configured on this machine via a developer
    ///   key (Phase 1, OpenAI).
    /// - `"hosted"` — the SelahCue hosted service is configured (base URL + account token). Phase 2.
    ///
    /// This replaces the old two-state `"available"` / `"not_configured"`, which could only describe
    /// the hosted service. See `notes_available` for why that mattered.
    cloud_status: String,
    /// **Renamed from `cloud_connected`, and the rename is the point.**
    ///
    /// The old field meant "the SelahCue hosted service is reachable" and was derived from
    /// `cloud_base_url().is_some() && account_token_set` — both properties of a service this phase
    /// does not build. With GPT wired directly it stayed `false` while generation actually worked,
    /// so the panel rendered "coming soon" over a working feature: the screen denying a feature
    /// while producing its output, on the one screen whose entire job is trust.
    ///
    /// The field now means **note generation can run right now** — true for `"direct_provider"` and
    /// `"hosted"`, false for the other two. Keeping the old name would have left a field called
    /// `cloud_connected` reading `true` for a local developer key with nothing connected to any
    /// cloud, which is a fresh instance of exactly the representation-vs-reality drift this change
    /// exists to remove. `cloud_status == "hosted"` is what now carries hosted connectivity.
    notes_available: bool,
    /// Who serves the notes. `Some` iff `notes_available`.
    notes_provider: Option<NotesProviderView>,
    account_token_set: bool,
    quota: Option<QuotaView>,
    /// Whether Cloud (Deepgram) transcription can actually run right now — mirrors
    /// `notes_available`/`notes_provider` exactly, and for the same reason: the card must
    /// never claim availability with no provider to name, and never name a provider while
    /// reporting unavailable (86akby7th). See `transcription_status_from`.
    transcription_available: bool,
    /// Who serves Cloud transcription. `Some` iff `transcription_available`.
    transcription_provider: Option<TranscriptionProviderView>,
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

/// Whether a direct third-party note provider is compiled into this build at all.
#[cfg(feature = "openai-notes")]
const DIRECT_NOTES_COMPILED: bool = true;
#[cfg(not(feature = "openai-notes"))]
const DIRECT_NOTES_COMPILED: bool = false;

/// The direct-provider descriptor, or `None` when no usable developer key is present.
///
/// Reads `OPENAI_API_KEY` as a plain environment variable. An absent variable and an empty one are
/// treated identically, so it does not matter whether the `.env` loader (86akby6yy) unsets a blank
/// value or exports it empty. Nothing here touches the key beyond asking whether it exists.
/// Decide the direct provider from a key value, without reading the environment.
///
/// Split out because the env read made the key check unassertable: `present.then(..)` mutated to
/// `true.then(..)` — which is the **over-reporting inversion the scope amendment names in terms**,
/// claiming a provider when no key exists — passed 74/74. A test cannot vary the process
/// environment safely under a parallel test runner, so the decision takes the value instead.
///
/// Absent and blank are treated identically, so it does not matter whether the `.env` loader
/// unsets an empty value or exports it empty.
#[cfg(feature = "openai-notes")]
fn direct_provider_from_key(key: Option<&str>, model: &str) -> Direct {
    let present = key.is_some_and(|k| !k.trim().is_empty());
    Direct(present.then(|| NotesProviderView {
        kind: selahcue_cloud::openai::PROVIDER_KIND.to_string(),
        name: selahcue_cloud::openai::PROVIDER_LABEL.to_string(),
        // The model ACTUALLY in use, not the compiled default. QA switches model via `.env` and
        // reads this off the panel to confirm the switch took — so if it reported the constant, an
        // operator who set luna would see terra and be unable to tell a failed override from a
        // stale display. That makes the feature unfalsifiable from outside, which is worse than
        // not having it.
        model: model.to_string(),
        developer_key: true,
    }))
}

/// **Also refuses in a release profile**, via `selahcue_cloud::openai::direct_key_permitted` —
/// the same predicate that gates `OpenAiNoteProvider::from_env`, the function that actually
/// performs generation (86akcmzyq, Cody's High finding on PR #24). Before this, this status
/// function had no profile check at all: a release build could report `"direct_provider"` from
/// whatever `OPENAI_API_KEY` happened to be exported, even once `from_env` itself refused to use
/// it — a panel claiming a working provider that generation would then fail to produce. The key
/// is not read at all when the profile refuses, matching `from_env`'s own behaviour so the panel
/// and the actual generation path never disagree.
#[cfg(feature = "openai-notes")]
fn direct_notes_provider() -> Direct {
    let key = selahcue_cloud::openai::direct_key_permitted(cfg!(debug_assertions))
        .then(|| std::env::var(selahcue_cloud::openai::API_KEY_ENV).ok())
        .flatten();
    direct_provider_from_key(key.as_deref(), &selahcue_cloud::openai::model_from_env())
}

#[cfg(not(feature = "openai-notes"))]
fn direct_notes_provider() -> Direct {
    Direct(None)
}

/// The hosted-service descriptor, or `None` when it is not configured.
///
/// **A known gap, left for Phase 2 rather than built now.** This requires a base URL *and* an
/// account token, and returns `None` if either is absent — so a build with a base URL but no token
/// collapses into the generic unconfigured state, which is the same lossy collapse that
/// `"key_missing"` exists to fix on the direct side. The symmetric state is `"token_missing"`, and
/// the derivation below is a plain match precisely so adding it is one arm and not a refactor. It
/// is not built here because Phase 1 has no hosted service to be half-configured against.
fn hosted_notes_provider(account_token_set: bool) -> Hosted {
    let Some(_base) = cloud_base_url() else {
        return Hosted(None);
    };
    Hosted(account_token_set.then(|| NotesProviderView {
        kind: "selahcue_hosted".to_string(),
        name: selahcue_cloud::client::CLOUD_PROVIDER_LABEL.to_string(),
        model: String::new(),
        developer_key: false,
    }))
}

/// Resolve the four-state status from **already-resolved inputs**. The hosted service wins when
/// configured: it is the shipping path, and the direct developer key is the stand-in for its absence.
///
/// # Why this is separated from the lookups
///
/// `notes_status` below reads `cloud_base_url()` and the environment, and in any one build those are
/// effectively constants — without `cloud-live` the base URL is a literal `None`, and without
/// `openai-notes` the direct provider is a literal `None`. So `notes_status` can only ever return
/// **one** of the four states in a given compilation, and a test calling it cannot reach the other
/// three however many arguments it varies.
///
/// That is not hypothetical: the first version of the invariant test looped over `account_token_set`
/// believing it was covering the state space, and reached exactly one state. Both the `hosted` and
/// `direct_provider` arms could be made to violate the invariant outright and the test stayed green —
/// a dead control inside the very test meant to prevent the trust bug this change exists to fix.
///
/// Taking the resolved inputs as parameters makes all four states reachable by a test, so the
/// control asserts something. `notes_status` is then the thin wrapper that supplies the real ones.
///
/// # Why [`Hosted`] and [`Direct`] are newtypes
///
/// Extracting this function fixed the logic and moved the untested thing one layer up: with two
/// bare `Option<NotesProviderView>` parameters, **swapping them at the call site still compiled**,
/// and every test passed — because in a Phase 1 build both are `None`, so the swap is invisible
/// until the Phase 2 build where both can be `Some` and precedence inverts. The newtypes make that
/// swap a type error rather than a test we would have to remember to write, which is the same move
/// as `NoteSection::flat`/`outline`: prefer an illegal state that cannot be built over one that is
/// merely asserted against.
///
/// **The producers return these types; the call site does not wrap.** Wrapping at the call site
/// was tried first and did not work — `Hosted(direct_notes_provider())` still typechecks, because
/// both producers returned a bare `Option<NotesProviderView>` and the newtype was applied to
/// whichever value was handed to it. The identity has to travel from where the value is *made*,
/// or the constructor is just a label the caller can misapply. Verified by swapping the two
/// producer calls and confirming it fails to compile.
/// The hosted-service provider, if configured. A newtype, not a bare `Option`, so it cannot
/// be passed where [`Direct`] is expected — see [`notes_status_from`].
struct Hosted(Option<NotesProviderView>);
/// The direct developer-key provider, if configured.
struct Direct(Option<NotesProviderView>);

fn notes_status_from(
    hosted: Hosted,
    direct: Direct,
    direct_compiled: bool,
) -> (String, Option<NotesProviderView>) {
    let (hosted, direct) = (hosted.0, direct.0);
    if let Some(hosted) = hosted {
        return ("hosted".to_string(), Some(hosted));
    }
    if let Some(direct) = direct {
        return ("direct_provider".to_string(), Some(direct));
    }
    if direct_compiled {
        // The feature is in, the key is not. Say which — "unavailable" would send someone
        // looking for a missing build rather than a missing line in `.env`.
        return ("key_missing".to_string(), None);
    }
    ("not_configured".to_string(), None)
}

/// The four-state status for this build, from the real lookups.
fn notes_status(account_token_set: bool) -> (String, Option<NotesProviderView>) {
    notes_status_from(
        hosted_notes_provider(account_token_set),
        direct_notes_provider(),
        DIRECT_NOTES_COMPILED,
    )
}

/// Build the view from an **already-resolved** status.
///
/// Split from [`providers_view_of`] for the same reason [`notes_status_from`] is split from
/// [`notes_status`], and after the same mistake: the wrapper resolves its status from build-time
/// constants, so in a test build `notes_provider` is always `None` and `notes_available` always
/// `false`. Hardcoding `notes_available = false` — **which is the trust bug this whole change
/// exists to fix** — passed 74/74 in both feature configurations, because the invariant was
/// asserted three times and not one of those assertions consumed *this* expression: the four-state
/// test drives `notes_status_from` directly, the default-build test asserts an all-false state
/// that a hardcoded `false` satisfies, and the headless stub re-derives the rule in JavaScript.
/// Three controls, all reading a copy.
///
/// Taking the resolved pair as parameters lets a test reach the state where `notes_available`
/// must be **true**, which is the only place the expression can be caught being wrong.
fn providers_view_from(
    cfg: &selahcue_core::providers::ProvidersConfig,
    account_token_set: bool,
    cloud_status: String,
    notes_provider: Option<NotesProviderView>,
    transcription_available: bool,
    transcription_provider: Option<TranscriptionProviderView>,
) -> ProvidersView {
    // Derived from the provider rather than computed alongside it, so the two cannot disagree.
    //
    // That sentence used to sit here on its own, one line above this expression, asserting a
    // guarantee that **nothing enforced**: hardcoding `notes_available = false` — which is exactly
    // the trust bug this change exists to fix — left 74/74 green in both feature configurations.
    // The invariant was asserted three times and every one of those controls read a copy rather
    // than this expression.
    //
    // What enforces it now: `notes_available_is_true_in_the_view_when_a_provider_is_named` drives
    // this function with a resolved provider present, which is the only state where this line can
    // be caught being wrong. Mutating it to a constant `false` or `true` goes RED in both configs.
    // If you change this derivation, that test is the one that should fail.
    let notes_available = notes_provider.is_some();
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
            podcast_show_notes: inc.podcast_show_notes,
            short_description: inc.short_description,
        },
        cloud_status,
        notes_available,
        notes_provider,
        account_token_set,
        // Stays None. There is no metering in this phase, so there is no number to show, and the
        // panel's honest placeholder is the correct output. A generation counter or session tally
        // would be a fabricated meter — the exact thing settings.js refuses to render.
        quota: None,
        transcription_available,
        transcription_provider,
    }
}

/// Providers & Privacy view contract (86akby7d8).
///
/// `dist/settings.js` reads these field names. They are pinned here so a rename is a failing test
/// and a deliberate two-sided change, rather than something the frontend discovers at runtime by
/// rendering `undefined`.
#[cfg(test)]
mod providers_view_tests {
    use super::*;

    fn view() -> serde_json::Value {
        let cfg = selahcue_core::providers::ProvidersConfig::default();
        serde_json::to_value(providers_view_of(&cfg, false)).expect("view serialises")
    }

    #[test]
    fn the_frontend_contract_field_names_are_pinned() {
        let v = view();
        let obj = v.as_object().expect("the view is a JSON object");
        let mut got: Vec<&str> = obj.keys().map(String::as_str).collect();
        got.sort_unstable();

        let mut expected = vec![
            "transcription_mode",
            "on_device",
            "cloud_transcription_consent",
            "cloud_notes_consent",
            "offline_by_default",
            "any_cloud_enabled",
            "notes_template",
            "notes_templates",
            "preferred_translation",
            "translations",
            "include",
            "cloud_status",
            "notes_available",
            "notes_provider",
            "account_token_set",
            "quota",
            "transcription_available",
            "transcription_provider",
        ];
        expected.sort_unstable();
        assert_eq!(
            got, expected,
            "the providers view surface changed; settings.js reads these names and must be \
             updated in the SAME merge request"
        );

        // The six include-flags are part of the same contract.
        let mut inc: Vec<&str> = v["include"]
            .as_object()
            .expect("`include` is an object in the view contract")
            .keys()
            .map(String::as_str)
            .collect();
        inc.sort_unstable();
        assert_eq!(
            inc,
            vec![
                "chapter_markers",
                "notable_quotations",
                "podcast_show_notes",
                "prayer_points",
                "scripture_extraction",
                "short_description",
                "short_summary",
                "social_excerpts",
            ]
        );
    }

    fn a_provider(kind: &str, developer_key: bool) -> NotesProviderView {
        NotesProviderView {
            kind: kind.to_string(),
            name: "Test Provider".to_string(),
            model: "test-model".to_string(),
            developer_key,
        }
    }

    /// Every input combination, and the state each must produce. Drives
    /// `notes_status_from` directly: `notes_status` reads build-time constants, so in any
    /// one compilation it can only ever return ONE of these four and a test calling it
    /// reaches nothing else.
    fn all_four_states() -> Vec<(&'static str, Hosted, Direct, bool)> {
        vec![
            ("not_configured", Hosted(None), Direct(None), false),
            ("key_missing", Hosted(None), Direct(None), true),
            (
                "direct_provider",
                Hosted(None),
                Direct(Some(a_provider("openai", true))),
                true,
            ),
            (
                "hosted",
                Hosted(Some(a_provider("selahcue_hosted", false))),
                Direct(None),
                false,
            ),
        ]
    }

    #[test]
    fn notes_provider_matches_availability_in_both_directions_in_all_four_states() {
        // The control that would catch a regression of the trust bug: the panel can never claim
        // notes are available without naming who provides them, and can never name a provider
        // while reporting notes unavailable.
        //
        // The earlier version of this test looped over `account_token_set` and reached exactly
        // ONE state, so both the hosted and direct arms could be made to violate the invariant
        // outright while it stayed green.
        let mut seen: Vec<&str> = Vec::new();
        for (expected, hosted, direct, compiled) in all_four_states() {
            let (status, provider) = notes_status_from(hosted, direct, compiled);
            assert_eq!(status, expected, "wrong state for this input combination");

            let available = provider.is_some();
            assert_eq!(
                available,
                status == "direct_provider" || status == "hosted",
                "status {status:?} disagrees with whether a provider was named"
            );
            seen.push(expected);
        }
        // POSITIVE CONTROL: all four states were actually produced. Without this the loop
        // could pass having exercised one row, which is exactly how it failed before.
        assert_eq!(
            seen,
            vec!["not_configured", "key_missing", "direct_provider", "hosted"],
            "the invariant must be exercised in ALL four states"
        );
    }

    #[test]
    fn hosted_wins_over_a_direct_provider_when_both_are_configured() {
        // Precedence has to be asserted, not assumed: it is what keeps the panel's report and
        // `run_note_generation`'s actual choice in agreement.
        let (status, provider) = notes_status_from(
            Hosted(Some(a_provider("selahcue_hosted", false))),
            Direct(Some(a_provider("openai", true))),
            true,
        );
        assert_eq!(status, "hosted");
        assert_eq!(
            provider.expect("a provider is named").kind,
            "selahcue_hosted",
            "the hosted service is the shipping path and must win"
        );
    }

    #[test]
    fn the_status_is_always_one_of_the_four_defined_states() {
        for (expected, hosted, direct, compiled) in all_four_states() {
            let (status, _) = notes_status_from(hosted, direct, compiled);
            assert!(
                ["not_configured", "key_missing", "direct_provider", "hosted"]
                    .contains(&status.as_str()),
                "unknown cloud_status {status:?}; settings.js branches on this set"
            );
            assert_eq!(status, expected);
        }
        // And the real build-time derivation also lands in the set.
        for token_set in [false, true] {
            let (status, _) = notes_status(token_set);
            assert!(
                ["not_configured", "key_missing", "direct_provider", "hosted"]
                    .contains(&status.as_str())
            );
        }
    }

    #[test]
    fn notes_available_is_true_in_the_view_when_a_provider_is_named() {
        // The control the three existing invariant assertions could not provide. They all run in a
        // build where `notes_status` can only produce `None`, so hardcoding
        // `notes_available = false` — the trust bug itself — satisfied every one of them.
        // Driving the resolved pair reaches the state where it must be TRUE.
        let cfg = selahcue_core::providers::ProvidersConfig::default();

        for (status, provider) in [
            ("direct_provider", a_provider("openai", true)),
            ("hosted", a_provider("selahcue_hosted", false)),
        ] {
            let v = serde_json::to_value(providers_view_from(
                &cfg,
                false,
                status.to_string(),
                Some(provider),
                false,
                None,
            ))
            .expect("the view serialises");

            assert_eq!(
                v["notes_available"],
                serde_json::json!(true),
                "a named provider must make notes_available TRUE in {status:?} — reporting false \
                 here is precisely the bug this change exists to fix: the panel would render \
                 'coming soon' over a working feature"
            );
            assert!(!v["notes_provider"].is_null());
            assert_eq!(v["cloud_status"], status);
        }

        // And the other direction, through the same function, so one expression is pinned both ways.
        for status in ["not_configured", "key_missing"] {
            let v = serde_json::to_value(providers_view_from(
                &cfg,
                false,
                status.to_string(),
                None,
                false,
                None,
            ))
            .expect("the view serialises");
            assert_eq!(
                v["notes_available"],
                serde_json::json!(false),
                "no provider must mean notes_available FALSE in {status:?} — the fix must not \
                 invert into over-reporting"
            );
            assert!(v["notes_provider"].is_null());
        }
    }

    /// `transcription_available`'s own version of `notes_available_is_true_in_the_view_when_a_provider_is_named`
    /// — same trust bug shape, same fix shape. Drives `transcription_status_from` with a
    /// **constructed** `CloudSttReadiness`, which is what makes the `Ready` state reachable
    /// from a test regardless of whether this compilation has `cloud-stt` on: a call to
    /// `transcription_status()` itself could only ever observe ONE build's real readiness, so a
    /// hardcoded `transcription_available = false` would satisfy every test that called it
    /// directly — exactly the `notes_available` postmortem repeated one field over.
    #[test]
    fn transcription_available_is_true_in_the_view_when_a_provider_is_named() {
        use selahcue_stt_cloud::readiness::CloudSttReadiness;

        let cfg = selahcue_core::providers::ProvidersConfig::default();

        // POSITIVE: Ready names a provider, and that must flip transcription_available TRUE.
        let (available, provider) = transcription_status_from(CloudSttReadiness::Ready.status());
        let v = serde_json::to_value(providers_view_from(
            &cfg,
            false,
            "not_configured".to_string(),
            None,
            available,
            provider,
        ))
        .expect("the view serialises");
        assert_eq!(
            v["transcription_available"],
            serde_json::json!(true),
            "a named provider (readiness == Ready) must make transcription_available TRUE — \
             reporting false here is the exact bug 86akby7th exists to fix: the card would deny \
             a feature that is actually configured"
        );
        assert!(!v["transcription_provider"].is_null());
        assert_eq!(v["transcription_provider"]["kind"], "deepgram");

        // NEGATIVE, both ineligible states, through the SAME function so one expression is
        // pinned in both directions.
        for readiness in [CloudSttReadiness::NotInBuild, CloudSttReadiness::KeyMissing] {
            let (available, provider) = transcription_status_from(readiness.status());
            let v = serde_json::to_value(providers_view_from(
                &cfg,
                false,
                "not_configured".to_string(),
                None,
                available,
                provider,
            ))
            .expect("the view serialises");
            assert_eq!(
                v["transcription_available"],
                serde_json::json!(false),
                "no provider must mean transcription_available FALSE for {readiness:?} — the \
                 fix must not invert into over-reporting (claiming Cloud is ready when it is not \
                 is the worse of the two directions: it lets an operator opt in to silence)"
            );
            assert!(v["transcription_provider"].is_null());
        }
    }

    #[test]
    fn the_transcription_provider_object_keys_are_pinned() {
        // settings.js reads these, and `name` is the FR-120/FR-132 disclosure string — the one
        // the card renders to say which engine is producing the transcript.
        use selahcue_stt_cloud::readiness::CloudSttReadiness;
        let (_, provider) = transcription_status_from(CloudSttReadiness::Ready.status());
        let provider = provider.expect("Ready must name a provider");
        let v = serde_json::to_value(provider).expect("serialises");
        let mut got: Vec<&str> = v
            .as_object()
            .expect("transcription_provider is an object")
            .keys()
            .map(String::as_str)
            .collect();
        got.sort_unstable();
        assert_eq!(
            got,
            vec!["developer_key", "kind", "model", "name"],
            "the transcription_provider surface changed; settings.js must be updated in the \
             SAME merge request"
        );
    }

    /// The key check, driven by value rather than by the process environment.
    #[cfg(feature = "openai-notes")]
    #[test]
    fn a_missing_or_blank_key_names_no_direct_provider() {
        for absent in [None, Some(""), Some("   "), Some("\t\n")] {
            assert!(
                direct_provider_from_key(absent, selahcue_cloud::openai::DEFAULT_MODEL)
                    .0
                    .is_none(),
                "key {absent:?} must NOT produce a provider — claiming one without a key is the \
                 over-reporting inversion the scope amendment forbids"
            );
        }
        // POSITIVE CONTROL: a real key does produce one, so the assertions above are not
        // satisfied by a function that always returns None.
        let present = direct_provider_from_key(
            Some("sk-proj-anything"),
            selahcue_cloud::openai::DEFAULT_MODEL,
        )
        .0;
        let present = present.expect("a non-empty key must name a provider");
        assert_eq!(present.kind, selahcue_cloud::openai::PROVIDER_KIND);
        assert_eq!(present.name, selahcue_cloud::openai::PROVIDER_LABEL);
        assert_eq!(present.model, selahcue_cloud::openai::DEFAULT_MODEL);
        assert!(present.developer_key, "a .env key is a developer key");
    }

    /// QA sets a model in `.env` and reads it off the panel to confirm the switch took. If the
    /// view showed the compiled default, the feature would be unfalsifiable from the outside.
    #[cfg(feature = "openai-notes")]
    #[test]
    fn the_view_reports_the_model_actually_in_use_not_the_compiled_default() {
        let cfg = selahcue_core::providers::ProvidersConfig::default();

        // Both real tiers, driven through the FULL view — not just the provider — because the
        // panel is what QA reads.
        for model in ["gpt-5.6-luna", "gpt-5.6-terra"] {
            let direct = direct_provider_from_key(Some("sk-proj-test"), model);
            let (status, provider) = notes_status_from(Hosted(None), direct, true);
            assert_eq!(status, "direct_provider");
            let v = serde_json::to_value(providers_view_from(
                &cfg, false, status, provider, false, None,
            ))
            .expect("the view serialises");
            assert_eq!(
                v["notes_provider"]["model"], model,
                "the panel must show the model actually configured; showing the default would \
                 leave QA unable to tell a failed override from a stale display"
            );
        }

        // PREMISE: at least one driven value is NOT the default, or the loop above could pass
        // against an implementation that always reports the constant.
        assert_ne!("gpt-5.6-luna", selahcue_cloud::openai::DEFAULT_MODEL);
    }

    /// The complement of Sana's F-4, on the other side of the seam.
    ///
    /// F-4 pinned `environment -> model_from_env` in the cloud crate. This pins
    /// `environment -> direct_notes_provider -> the view`. Both were unpinned for the same reason:
    /// the tests either side drive the value **by argument**, which is the copy, so the wiring
    /// expression that reads the environment was asserted by nothing.
    ///
    /// Verified before writing this: mutating `direct_notes_provider` to pass `DEFAULT_MODEL`
    /// instead of `model_from_env()` left the operator suite fully green. Under that mutation QA
    /// sets luna, the REQUEST correctly uses luna, and the PANEL says terra — so the one surface
    /// QA reads to confirm the switch is the one that lies. That is precisely the
    /// "unfalsifiable from outside" failure the model field exists to prevent.
    ///
    /// Extended for 86akcmzyq (Cody's High finding): `direct_notes_provider` now also refuses in
    /// a release profile, mirroring `OpenAiNoteProvider::from_env`. `cfg!(debug_assertions)` is
    /// fixed for the life of one compiled test binary, so this asserts whichever branch THIS
    /// profile actually compiled — `cargo test` (debug) takes the `if`, `cargo test --release`
    /// (added to `make ci`/CI alongside this fix) takes the `else`. One test, both arms proven by
    /// running it in both profiles, the same shape as `selahcue-licensing`'s
    /// `..._iff_it_is_a_debug_build`.
    #[cfg(feature = "openai-notes")]
    #[test]
    fn the_environment_reaches_the_view_not_only_the_request() {
        let _guard = crate::env_locked();
        let cfg = selahcue_core::providers::ProvidersConfig::default();

        std::env::set_var(selahcue_cloud::openai::API_KEY_ENV, "sk-proj-test-key");
        std::env::set_var(selahcue_cloud::openai::MODEL_ENV, "sentinel-model-from-env");
        let direct = direct_notes_provider();
        std::env::remove_var(selahcue_cloud::openai::MODEL_ENV);
        std::env::remove_var(selahcue_cloud::openai::API_KEY_ENV);

        let (status, provider) = notes_status_from(Hosted(None), direct, true);

        if cfg!(debug_assertions) {
            assert_eq!(
                status, "direct_provider",
                "premise: an exported key must name a provider in a debug build, or the model \
                 assertion below cannot run"
            );
            let v = serde_json::to_value(providers_view_from(
                &cfg, false, status, provider, false, None,
            ))
            .expect("the view serialises");
            assert_eq!(
                v["notes_provider"]["model"], "sentinel-model-from-env",
                "the panel reported a model other than the one exported — QA cannot tell a \
                 failed override from a stale display, which makes the whole switch unverifiable"
            );
        } else {
            // The release half of 86akcmzyq's Cody finding: a RELEASE build must not construct a
            // working direct provider from an exported OPENAI_API_KEY, even with openai-notes
            // compiled in — matching the layer-2 guard dev_env::load() already has for dev-keys.
            // If this goes back to "direct_provider", direct_key_permitted stopped being wired
            // into direct_notes_provider (inverted, hardcoded, or the gate was removed).
            assert_eq!(
                status, "key_missing",
                "a RELEASE build reported a working direct provider from an exported \
                 OPENAI_API_KEY — see selahcue_cloud::openai::direct_key_permitted"
            );
            assert!(
                provider.is_none(),
                "key_missing must carry no provider view"
            );
        }
        assert_ne!(
            "sentinel-model-from-env",
            selahcue_cloud::openai::DEFAULT_MODEL,
            "premise: the sentinel must differ from the default"
        );
    }

    #[test]
    fn the_notes_provider_object_keys_are_pinned() {
        // settings.js reads these, and `name` is the FR-132 disclosure string — the one the
        // panel renders to say who generated the notes. The headless stub is a hand-written
        // mirror, so it would not catch a rename here either; this is the only guard.
        let v = serde_json::to_value(a_provider("openai", true)).expect("serialises");
        let mut got: Vec<&str> = v
            .as_object()
            .expect("notes_provider is an object")
            .keys()
            .map(String::as_str)
            .collect();
        got.sort_unstable();
        assert_eq!(
            got,
            vec!["developer_key", "kind", "model", "name"],
            "the notes_provider surface changed; settings.js and scripts/operator_headless.py \
             read these names and must be updated in the SAME merge request"
        );
    }

    /// A stock build — no direct-provider path compiled in — must report notes as genuinely
    /// unavailable. The fix for the trust bug must not invert into OVER-reporting.
    #[cfg(not(feature = "openai-notes"))]
    #[test]
    fn a_default_build_reports_notes_unavailable_and_names_no_provider() {
        let v = view();
        assert_eq!(v["cloud_status"], "not_configured");
        assert_eq!(v["notes_available"], serde_json::json!(false));
        assert!(v["notes_provider"].is_null());
    }

    /// With the direct path compiled in, the status must never collapse back to the stock
    /// `"not_configured"` — that is the distinction the whole four-state design exists to keep.
    /// Which of the two feature-on states applies depends on whether a key happens to be exported
    /// in the test environment, so both are accepted; what is asserted is that the two builds are
    /// distinguishable at all.
    #[cfg(feature = "openai-notes")]
    #[test]
    fn a_build_with_the_direct_path_never_reports_the_stock_not_configured_state() {
        let (status, provider) = notes_status(false);
        assert_ne!(
            status, "not_configured",
            "a build that CAN reach a provider must not report the state of one that cannot"
        );
        assert!(
            status == "key_missing" || status == "direct_provider",
            "unexpected status {status:?}"
        );
        assert_eq!(provider.is_some(), status == "direct_provider");
    }

    #[test]
    fn quota_is_null_and_no_meter_is_fabricated() {
        // A negative requirement, tested because a well-meaning implementation invents one: a
        // generation counter, a session tally, anything. There is no metering in this phase, so
        // the honest placeholder is the correct output.
        assert!(view()["quota"].is_null(), "quota must stay null in Phase 1");
    }

    #[test]
    fn a_draft_carries_its_sub_points_through_to_the_frontend() {
        use selahcue_core::providers::{NoteDraft, NotePoint, NoteSection};
        let draft = NoteDraft {
            title: "t".into(),
            summary: None,
            sections: vec![NoteSection::outline(
                "Main points",
                vec![NotePoint {
                    text: "parent".into(),
                    sub_points: vec!["child".into()],
                }],
            )],
            scriptures: Vec::new(),
            caveats: Vec::new(),
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        };
        let j = draft_json(&draft);
        assert_eq!(j["sections"][0]["points"][0]["text"], "parent");
        assert_eq!(j["sections"][0]["points"][0]["sub_points"][0], "child");
        assert!(
            j["sections"][0]["items"]
                .as_array()
                .expect("items is an array")
                .is_empty(),
            "sub-points must NOT also be flattened into items"
        );
    }

    #[test]
    fn draft_json_marks_a_caveated_section_empty_requested_and_others_not() {
        // 86akc0tua: `draft_json` computes `empty_requested` per section, once, so
        // `settings.js` never has to cross-reference headings against `caveats` itself.
        use selahcue_core::providers::{DraftCaveat, NoteDraft, NoteSection};
        let draft = NoteDraft {
            title: "t".into(),
            summary: None,
            sections: vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            scriptures: Vec::new(),
            caveats: vec![DraftCaveat::SectionRequestedEmpty {
                heading: "Chapter markers".to_string(),
            }],
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        };
        let j = draft_json(&draft);
        assert_eq!(j["sections"][0]["heading"], "Illustrations");
        assert_eq!(
            j["sections"][0]["empty_requested"], false,
            "a populated section must never be marked empty_requested"
        );
        assert_eq!(j["sections"][1]["heading"], "Chapter markers");
        assert_eq!(j["sections"][1]["empty_requested"], true);
        assert_eq!(
            j["caveats"],
            serde_json::json!([{"kind": "section_empty", "heading": "Chapter markers"}])
        );
    }

    #[test]
    fn draft_json_reports_no_caveats_when_the_draft_has_none() {
        use selahcue_core::providers::{NoteDraft, NoteSection};
        let draft = NoteDraft {
            title: "t".into(),
            summary: None,
            sections: vec![NoteSection::flat("Illustrations", vec!["a lantern".into()])],
            scriptures: Vec::new(),
            caveats: Vec::new(),
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        };
        let j = draft_json(&draft);
        assert_eq!(j["sections"][0]["empty_requested"], false);
        assert_eq!(
            j["caveats"].as_array().expect("caveats is an array").len(),
            0
        );
    }
}

/// End-to-end verification against the REAL bundled Bible text (86akby820; FR-125/FR-128).
///
/// `selahcue-core`'s own tests (`test_scripture_verify.rs`) drive `verify_scriptures` with
/// a stub oracle, because that crate cannot depend on `selahcue-scripture` (the dependency
/// runs the other way). This crate depends on both, so this is where the real
/// `selahcue_scripture::verses` oracle is actually wired in and where the exact
/// looks-plausible-but-isn't table from the ticket is proven against the real text, not a
/// fake one.
#[cfg(test)]
mod scripture_verification_tests {
    use super::draft_json;
    use selahcue_core::providers::{verify_scriptures, DraftCaveat, NotePoint, NoteSection};

    fn real_oracle() -> impl FnMut(&selahcue_core::scripture::Reference) -> bool {
        |r: &selahcue_core::scripture::Reference| !selahcue_scripture::verses(r).is_empty()
    }

    #[test]
    fn a_real_valid_reference_verifies_against_the_bundled_text() {
        let (verdicts, truncated) =
            verify_scriptures(&["John 3:16".to_string()], &[], real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert!(verdicts[0].verified, "John 3:16 is a real verse");
        assert!(!truncated, "one reference is nowhere near either budget");
    }

    #[test]
    fn a_reference_naming_no_real_book_is_unverified() {
        let (verdicts, _) = verify_scriptures(&["Frobnicate 1:1".to_string()], &[], real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert!(!verdicts[0].verified);
        assert_eq!(verdicts[0].reference, "Frobnicate 1:1");
    }

    #[test]
    fn a_chapter_past_a_real_short_books_end_is_unverified() {
        // Obadiah has one chapter. Chapter 2 does not exist.
        let (verdicts, _) = verify_scriptures(&["Obadiah 2:1".to_string()], &[], real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert!(!verdicts[0].verified);
    }

    #[test]
    fn a_verse_past_a_real_chapters_end_is_unverified() {
        // John 3 has 36 verses.
        let (verdicts, _) = verify_scriptures(&["John 3:99".to_string()], &[], real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert!(!verdicts[0].verified);
    }

    #[test]
    fn unparseable_text_in_the_list_is_unverified_and_still_shown() {
        let (verdicts, _) = verify_scriptures(
            &["definitely not a scripture reference".to_string()],
            &[],
            real_oracle(),
        );
        assert_eq!(
            verdicts,
            vec![selahcue_core::providers::ScriptureVerdict {
                reference: "definitely not a scripture reference".to_string(),
                verified: false,
            }]
        );
    }

    /// The ticket's own bar: "a test suite of obviously-broken inputs would not prove the
    /// check works on the realistic case." These four are real books, syntactically
    /// well-formed, that read as entirely plausible sermon citations — and every one
    /// names a chapter beyond that book's real (single-chapter) length. A checker that
    /// only validates syntax would pass all four; this one must not.
    #[test]
    fn four_plausible_but_nonexistent_references_are_all_caught() {
        let candidates = ["Obadiah 2:1", "3 John 4:12", "Jude 2:1", "Philemon 2:3"];
        let (verdicts, _) = verify_scriptures(
            &candidates.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
            &[],
            real_oracle(),
        );
        assert_eq!(verdicts.len(), 4);
        for v in &verdicts {
            assert!(
                !v.verified,
                "{} looks plausible (real book, well-formed syntax) but its chapter does \
                 not exist — a verifier that only parses would wrongly pass it: {v:?}",
                v.reference
            );
        }
    }

    #[test]
    fn a_fabricated_reference_embedded_in_a_sermon_point_is_caught_against_the_real_text() {
        let sections = vec![NoteSection::outline(
            "Main points",
            vec![NotePoint {
                text: "This is affirmed in 3 John 4:12, among other places.".to_string(),
                sub_points: vec![],
            }],
        )];
        let (verdicts, _) = verify_scriptures(&[], &sections, real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert_eq!(verdicts[0].reference, "3 John 4:12");
        assert!(!verdicts[0].verified);
    }

    #[test]
    fn a_real_reference_embedded_in_a_flat_item_verifies_against_the_real_text() {
        let sections = vec![NoteSection::flat(
            "Illustrations",
            vec!["As it says in Isaiah 55:1, come.".to_string()],
        )];
        let (verdicts, _) = verify_scriptures(&[], &sections, real_oracle());
        assert_eq!(verdicts.len(), 1);
        assert_eq!(verdicts[0].reference, "Isaiah 55:1");
        assert!(verdicts[0].verified);
    }

    #[test]
    fn draft_json_carries_scripture_verdicts_and_the_matching_caveats() {
        // Pins the shape the frontend actually reads: `scripture_verdicts` carries every
        // reference with its verdict, and an unverified one is ALSO present in `caveats`
        // as a `ScriptureUnverified` entry — the same "one shared vocabulary" mechanism
        // 86akc0tua established for requested-but-empty sections.
        use selahcue_core::providers::NoteDraft;
        let (verdicts, _) = verify_scriptures(
            &["John 3:16".to_string(), "3 John 4:12".to_string()],
            &[],
            real_oracle(),
        );
        let mut draft = NoteDraft {
            title: "t".into(),
            summary: None,
            sections: Vec::new(),
            scriptures: vec!["John 3:16".to_string(), "3 John 4:12".to_string()],
            caveats: Vec::new(),
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        };
        draft
            .caveats
            .extend(verdicts.iter().filter(|v| !v.verified).map(|v| {
                DraftCaveat::ScriptureUnverified {
                    reference: v.reference.clone(),
                }
            }));
        draft.scripture_verdicts = verdicts;

        let j = draft_json(&draft);
        let sv = j["scripture_verdicts"].as_array().expect("array");
        assert_eq!(sv.len(), 2);
        assert_eq!(sv[0]["reference"], "John 3:16");
        assert_eq!(sv[0]["verified"], true);
        assert_eq!(sv[1]["reference"], "3 John 4:12");
        assert_eq!(sv[1]["verified"], false);

        let caveats = j["caveats"].as_array().expect("array");
        assert_eq!(
            *caveats,
            vec![serde_json::json!({"kind": "scripture_unverified", "reference": "3 John 4:12"})]
        );
    }

    #[test]
    fn draft_json_renders_the_scripture_verification_incomplete_caveat() {
        // 86akgqdwc (Sana F2 on PR #48): pins the wire shape for the new draft-wide
        // caveat — no `heading`, no `reference`, just its `kind` — and confirms it
        // survives `draft_json` alongside an ordinary section, unlike
        // `SectionRequestedEmpty` it must never mark any section `empty_requested`.
        use selahcue_core::providers::NoteDraft;
        let draft = NoteDraft {
            title: "t".into(),
            summary: None,
            sections: vec![NoteSection::flat("Podcast show notes", vec!["ok".into()])],
            scriptures: Vec::new(),
            caveats: vec![DraftCaveat::ScriptureVerificationIncomplete],
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        };
        let j = draft_json(&draft);
        assert_eq!(
            j["caveats"],
            serde_json::json!([{"kind": "scripture_verification_incomplete"}])
        );
        assert_eq!(
            j["sections"][0]["empty_requested"], false,
            "a draft-wide caveat must never mark an unrelated, populated section empty"
        );
    }
}

fn providers_view_of(
    cfg: &selahcue_core::providers::ProvidersConfig,
    account_token_set: bool,
) -> ProvidersView {
    let (cloud_status, notes_provider) = notes_status(account_token_set);
    let (transcription_available, transcription_provider) = transcription_status();
    providers_view_from(
        cfg,
        account_token_set,
        cloud_status,
        notes_provider,
        transcription_available,
        transcription_provider,
    )
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
            "podcast_show_notes" => i.podcast_show_notes = enabled,
            "short_description" => i.short_description = enabled,
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
    use selahcue_core::providers::DraftCaveat;

    // Two purposes, one shared enum (86akc0tua + 86akby820): which section HEADINGS are
    // requested-but-empty (drives the per-section `empty_requested` flag and the
    // Summary/Scripture-references empty checks) is a different question from which
    // scripture REFERENCES are unverified (drives the scripture rendering below). A
    // `match`, not an irrefutable destructure, so a future third variant fails this to
    // compile until it is deliberately taught how to render the new kind.
    let mut empty_headings: Vec<&str> = Vec::new();
    for c in &d.caveats {
        match c {
            DraftCaveat::SectionRequestedEmpty { heading } => empty_headings.push(heading.as_str()),
            DraftCaveat::ScriptureUnverified { .. } => {}
            // Draft-wide; names no section heading (86akgqdwc, Sana F2).
            DraftCaveat::ScriptureVerificationIncomplete => {}
        }
    }
    let caveats_json: Vec<serde_json::Value> = d
        .caveats
        .iter()
        .map(|c| match c {
            DraftCaveat::SectionRequestedEmpty { heading } => {
                serde_json::json!({"kind": "section_empty", "heading": heading})
            }
            DraftCaveat::ScriptureUnverified { reference } => {
                serde_json::json!({"kind": "scripture_unverified", "reference": reference})
            }
            DraftCaveat::ScriptureVerificationIncomplete => {
                serde_json::json!({"kind": "scripture_verification_incomplete"})
            }
        })
        .collect();

    serde_json::json!({
        "title": d.title,
        "summary": d.summary,
        "sections": d.sections.iter().map(|s| serde_json::json!({
            "heading": s.heading,
            "items": s.items(),
            // FR-122 points/sub-points. Emitted as a nested structure, NOT flattened into
            // `items` with an indent prefix: subordination has to survive the wire as a fact
            // the renderer can read, or the hierarchy is a typographic convention and nothing
            // downstream can tell a sub-point from a point.
            "points": s.points().iter().map(|p| serde_json::json!({
                "text": p.text, "sub_points": p.sub_points,
            })).collect::<Vec<_>>(),
            // 86akc0tua: true when this section was requested (an enabled `IncludeInNotes`
            // flag, or one of the handful FR-122 always includes) and came back with
            // nothing at all — distinct from a section the operator left off, which never
            // reaches `sections` in the first place. Computed here, once, so `settings.js`
            // never has to re-derive it by cross-referencing headings itself.
            "empty_requested": empty_headings.iter().any(|h| *h == s.heading),
        })).collect::<Vec<_>>(),
        // Unchanged shape (a flat string array) — this is a PINNED cross-path contract
        // with `sermon_note_draft_json` (the persisted-draft-reload path), which reads the
        // same stored column back into the same shape. 86akby820's per-reference verified
        // verdicts travel in the NEW `scripture_verdicts` field below instead of changing
        // this one's shape.
        "scriptures": d.scriptures,
        // 86akby820 (FR-125/FR-128): every reference found anywhere in the draft — the
        // list above AND ones embedded only in a section's body text — with its verdict.
        // settings.js cross-references by exact string against `scriptures` to mark the
        // list inline, and renders anything left over (embedded-only) separately.
        "scripture_verdicts": d.scripture_verdicts.iter().map(|v| serde_json::json!({
            "reference": v.reference, "verified": v.verified,
        })).collect::<Vec<_>>(),
        "caveats": caveats_json,
        // 86akgqdw0 (FR-124): a transcript-derived timestamp for a chapter marker or
        // (best-effort) outline point, joined to its item by VALUE (`heading` + `text`) —
        // exactly like `scripture_verdicts` above — never by position. Empty whenever
        // `link_timestamps` was never run against real segments (the live-tail generation
        // path, or a draft generated with chapter markers off) — the console must already
        // tolerate that, the same way it tolerates an empty `scripture_verdicts`.
        "timestamps": d.timestamps.iter().map(|t| serde_json::json!({
            "heading": t.heading, "text": t.text, "offset_ms": t.offset_ms,
        })).collect::<Vec<_>>(),
    })
}

/// Attach transcript-derived timestamps to `draft`'s chapter markers (and, best-effort, its
/// outline points) — the ONE call site both `generate_sermon_notes` and
/// `transcript_generate_notes` route through (86akgqdw0), so the linking behaviour cannot
/// drift between the two entrypoints. `segments` is empty for the live-tail path (the
/// operator holds no live segment structure there — see this ticket's Goal Contract for the
/// documented scope boundary), which `link_timestamps` already handles gracefully (an empty
/// `timestamps` result, never a panic).
fn link_note_timestamps(
    draft: &mut selahcue_core::providers::NoteDraft,
    segments: &[selahcue_core::transcript::TranscriptSegment],
) {
    draft.timestamps = selahcue_core::providers::link_timestamps(&draft.sections, segments);
}

/// Best-effort read of transcript `id`'s segments, for re-linking timestamps on a
/// persisted-draft reload/edit-save (`sermon_note_draft_json`'s `timestamps` field,
/// 86akgqdw0). Any failure (no transcript store configured, no such transcript, a lock
/// error) degrades to an empty slice — mirroring `notes_generated_for`'s existing "must
/// never be the reason an otherwise-successful read fails" contract: a persisted draft
/// still loads and displays correctly with no timestamps at all, which the console already
/// has to tolerate (a draft generated with chapter markers off, or from the live-tail path,
/// carries none either).
fn transcript_segments_for(
    state: &State<'_, AppState>,
    transcript_id: i64,
) -> Vec<selahcue_core::transcript::TranscriptSegment> {
    with_transcript_db(state, |db| {
        selahcue_data::transcript_repo::load(db, transcript_id)
    })
    .map(|t| t.segments)
    .unwrap_or_default()
}

// ---------------------------------------------------------------------------------
// Sermon-note draft persistence (86akgqdv0; FR-123 "editable" half).
//
// `selahcue-core` and `selahcue-data` stay dependency-free / dumb-store respectively
// (see the v20->v21 migration comment in `selahcue-data/src/migrations.rs`), so the
// JSON codec for `NoteSection`'s items-XOR-points shape (FR-122) lives here — the
// operator already depends on `serde_json` for the wire to the JS UI.
// ---------------------------------------------------------------------------------

/// The sections to persist for a draft (86akc0tua remediation — Cody's blocking finding
/// on PR #46).
///
/// `caveats`/`empty_requested` are computed only for the LIVE `draft_json` response and
/// are not carried by the persisted wire shape (`SermonNoteDraftView` has no such field —
/// deliberately out of this ticket's footprint, see the Goal Contract's non-goals). Left
/// unaddressed, persisting a caveated-empty `NoteSection` verbatim — which this ticket
/// newly started pushing instead of omitting — would reappear after a reload or the next
/// edit-save as a bare heading over a silently empty list, with NONE of the explanation
/// the live view showed: worse than this ticket's OWN pre-fix behaviour (fully silent),
/// not merely as good.
///
/// So a section this call generated purely to hold a `SectionRequestedEmpty` caveat's
/// place (see `openai.rs::parse_draft`) is filtered out before it reaches the persisted
/// columns, restoring the exact pre-86akc0tua persisted shape for exactly those sections.
/// This is a narrower, more conservative fix than threading caveats through the wire
/// protocol (a cross-language contract change — see CLAUDE.md), and it trades "the
/// improvement doesn't survive a reload" (already an accepted, disclosed limitation) for
/// "a reload never shows a worse, unexplained state than before this ticket existed."
///
/// Deliberately NOT a blanket "drop every empty section": `local.rs`'s offline scaffold
/// pushes intentionally empty placeholder headings (`NoteSection::flat("Prayer points",
/// Vec::new())`) as honest, empty-for-the-operator-to-fill sections — those are NOT
/// caveated (local.rs never populates `caveats`) and must keep persisting exactly as they
/// did before this ticket.
fn sections_to_persist(
    draft: &selahcue_core::providers::NoteDraft,
) -> Vec<selahcue_core::providers::NoteSection> {
    // `.filter_map`, as the comment this replaced predicted: 86akby820 added a second
    // `DraftCaveat` variant, `ScriptureUnverified`, which is about a single reference, not
    // a whole section — it names nothing that ever matches a `NoteSection::heading`, so it
    // has no heading to contribute here and is skipped rather than persisted-out-of-
    // existence. Only `SectionRequestedEmpty` still identifies a section to drop.
    let empty_caveated_headings: Vec<&str> = draft
        .caveats
        .iter()
        .filter_map(|c| match c {
            selahcue_core::providers::DraftCaveat::SectionRequestedEmpty { heading } => {
                Some(heading.as_str())
            }
            selahcue_core::providers::DraftCaveat::ScriptureUnverified { .. } => None,
            // Draft-wide (86akgqdwc); names no section either.
            selahcue_core::providers::DraftCaveat::ScriptureVerificationIncomplete => None,
        })
        .collect();
    draft
        .sections
        .iter()
        .filter(|s| !empty_caveated_headings.contains(&s.heading.as_str()))
        .cloned()
        .collect()
}

#[cfg(test)]
mod sections_to_persist_tests {
    use super::sections_to_persist;
    use selahcue_core::providers::{DraftCaveat, NoteDraft, NoteSection};

    fn draft(sections: Vec<NoteSection>, caveats: Vec<DraftCaveat>) -> NoteDraft {
        NoteDraft {
            title: "t".into(),
            summary: None,
            sections,
            scriptures: Vec::new(),
            caveats,
            scripture_verdicts: Vec::new(),
            timestamps: Vec::new(),
        }
    }

    #[test]
    fn a_caveated_empty_section_is_dropped_before_persisting() {
        // Cody's blocking finding on PR #46: persisting this section verbatim would
        // reappear after a reload as a bare heading over an empty list with NO
        // explanation — worse than the pre-86akc0tua silent omission. Dropping it here
        // restores that exact pre-fix persisted shape for exactly this section.
        let d = draft(
            vec![
                NoteSection::flat("Illustrations", vec!["a lantern".into()]),
                NoteSection::flat("Chapter markers", Vec::new()),
            ],
            vec![DraftCaveat::SectionRequestedEmpty {
                heading: "Chapter markers".to_string(),
            }],
        );
        let persisted = sections_to_persist(&d);
        assert_eq!(persisted.len(), 1);
        assert_eq!(persisted[0].heading, "Illustrations");
    }

    #[test]
    fn an_uncaveated_empty_section_such_as_locals_honest_placeholder_still_persists() {
        // The narrower-than-a-blanket-filter requirement: `local.rs`'s deliberately
        // empty "fill this in yourself" placeholders (never caveated) must NOT be
        // caught by this filter — dropping them would be a NEW, unrelated regression.
        let d = draft(
            vec![NoteSection::flat("Prayer points", Vec::new())],
            Vec::new(),
        );
        let persisted = sections_to_persist(&d);
        assert_eq!(
            persisted.len(),
            1,
            "an empty section with NO caveat must still persist — only a CAVEATED \
             empty section is filtered"
        );
    }

    #[test]
    fn a_scripture_unverified_caveat_drops_nothing_it_names_no_section_at_all() {
        // 86akby820 added `DraftCaveat::ScriptureUnverified`, which this function's
        // `filter_map` must skip (it has no `heading` field to compare against — it
        // names a reference, not a section). Without this arm the match would not
        // compile at all (the compile error this test guards against); with a `_ => None`
        // wildcard instead of an explicit arm, a THIRD future caveat variant could
        // silently fall through unnoticed — this exhaustive match is what forces that
        // to be revisited too. A section sharing NO heading with any caveat must survive.
        let d = draft(
            vec![NoteSection::flat("Illustrations", vec!["a lantern".into()])],
            vec![DraftCaveat::ScriptureUnverified {
                reference: "3 John 4:12".to_string(),
            }],
        );
        let persisted = sections_to_persist(&d);
        assert_eq!(
            persisted.len(),
            1,
            "a ScriptureUnverified caveat must never cause an unrelated section to be \
             dropped — it names a reference, not a heading"
        );
    }

    #[test]
    fn a_scripture_verification_incomplete_caveat_drops_nothing_either() {
        // 86akgqdwc added `DraftCaveat::ScriptureVerificationIncomplete` (Sana F2 on PR
        // #48) — draft-wide, names no section and no reference. Same exhaustive-match
        // discipline as the `ScriptureUnverified` test above: without this arm the match
        // in `sections_to_persist` would not compile.
        let d = draft(
            vec![NoteSection::flat("Illustrations", vec!["a lantern".into()])],
            vec![DraftCaveat::ScriptureVerificationIncomplete],
        );
        let persisted = sections_to_persist(&d);
        assert_eq!(
            persisted.len(),
            1,
            "a ScriptureVerificationIncomplete caveat must never cause an unrelated \
             section to be dropped — it names nothing"
        );
    }

    #[test]
    fn a_populated_section_is_never_filtered_even_if_its_heading_matches_a_caveat() {
        // Defensive: the filter matches by heading text, so a populated section must
        // never accidentally collide with a stale/unrelated caveat heading. (In
        // practice `parse_draft` never emits both for the same heading, but the filter
        // itself should not rely on that invariant holding elsewhere.)
        let d = draft(
            vec![NoteSection::flat(
                "Chapter markers",
                vec!["Opening prayer".into()],
            )],
            vec![DraftCaveat::SectionRequestedEmpty {
                heading: "Chapter markers".to_string(),
            }],
        );
        let persisted = sections_to_persist(&d);
        assert_eq!(
            persisted.len(),
            0,
            "documenting actual behaviour: the filter is heading-keyed and does not \
             also check emptiness — this is safe ONLY because parse_draft never \
             produces this combination for real; see the caveat above"
        );
    }
}

fn sections_to_json(sections: &[selahcue_core::providers::NoteSection]) -> String {
    let v: Vec<serde_json::Value> = sections
        .iter()
        .map(|s| {
            serde_json::json!({
                "heading": s.heading,
                "items": s.items(),
                "points": s.points().iter().map(|p| serde_json::json!({
                    "text": p.text, "sub_points": p.sub_points,
                })).collect::<Vec<_>>(),
            })
        })
        .collect();
    serde_json::to_string(&v).unwrap_or_else(|_| "[]".to_string())
}

fn scriptures_to_json(scriptures: &[String]) -> String {
    serde_json::to_string(scriptures).unwrap_or_else(|_| "[]".to_string())
}

/// One outline point as submitted by the edit surface — mirrors
/// `selahcue_core::providers::NotePoint` field-for-field so deserialization doubles
/// as the shape check (a malformed edit fails HERE, at the Tauri IPC boundary,
/// before ever reaching `sermon_note_repo::update`).
#[derive(serde::Deserialize)]
struct NotePointInput {
    text: String,
    #[serde(default)]
    sub_points: Vec<String>,
}

/// One section as submitted by the edit surface. `items`/`points` are not mutually
/// exclusive at the wire level (unlike `NoteSection`'s private-fields invariant) —
/// [`sections_from_input`] resolves that: a section with any `points` is treated as
/// an outline (its `items` are ignored), matching `NoteSection::is_outline`'s own
/// "points present" test, so a round-tripped section can never silently flip shape.
#[derive(serde::Deserialize)]
struct NoteSectionInput {
    heading: String,
    #[serde(default)]
    items: Vec<String>,
    #[serde(default)]
    points: Vec<NotePointInput>,
}

fn sections_from_input(input: Vec<NoteSectionInput>) -> Vec<selahcue_core::providers::NoteSection> {
    use selahcue_core::providers::{NotePoint, NoteSection};
    input
        .into_iter()
        .map(|s| {
            if s.points.is_empty() {
                NoteSection::flat(s.heading, s.items)
            } else {
                NoteSection::outline(
                    s.heading,
                    s.points
                        .into_iter()
                        .map(|p| NotePoint {
                            text: p.text,
                            sub_points: p.sub_points,
                        })
                        .collect(),
                )
            }
        })
        .collect()
}

/// Build the wire JSON for a persisted draft, in the same shape `generate_sermon_notes`
/// already returns under `"draft"` — so the JS render path is identical whether the
/// draft just arrived from a live generation or was loaded back from disk on panel
/// activation.
///
/// Takes the LAN wire view (`selahcue_lan::protocol::SermonNoteDraftView`), not a
/// `selahcue-data` type: as of PR #33's review remediation (Sana F1 — High), this
/// operator process no longer opens `selahcue-data`'s file for the sermon-note feature
/// at all — see `generate_sermon_notes`/`load_sermon_note_draft`/
/// `update_sermon_note_draft`'s doc comments for why (the operator's OWN copy of that
/// file, at a DIFFERENT path than the desktop's, could never see a real `transcript`
/// row in a real launch; persistence now goes through `Backend`'s LAN commands, which
/// execute against the desktop's authoritative store).
///
/// 86akby820 (Sana F4 on PR #47): scripture verdicts are NOT persisted (same non-goal as
/// 86akc0tua's caveats, and for the same cross-language-wire-contract reason), but unlike
/// that ticket's empty-section caveats — which are deliberately never written to storage
/// at all (`sections_to_persist`) — the raw material this check needs (`scriptures`,
/// `sections`) IS still here on every load. `verify_scriptures` is pure and offline, so
/// re-running it fresh on every load/edit-save costs nothing a live generation didn't
/// already pay, and it closes the exact "the safety check doesn't survive a reload" gap
/// Cody blocked 86akc0tua on — for the harm this ticket's own PRD cites (a pastor reading
/// from a RELOADED Sunday-morning draft), not only the just-generated one.
/// Returns the draft JSON (in `draft_json`'s own shape) alongside the address-only
/// verification-scope note, gated exactly like `generate_sermon_notes`'s own response:
/// present only when at least one reference was actually (re-)checked. One return value,
/// not two separate re-computations, since both come from the same `verify_scriptures`
/// call — see the doc comment above for why this re-verifies on every load/edit-save.
///
/// `segments` (86akgqdw0) is re-linked through [`link_note_timestamps`] on every call, the
/// same "recompute fresh, never persist" treatment `scripture_verdicts` already gets above
/// and for the identical reason: the raw material (`sections`) survives every reload, so
/// there is nothing to gain from persisting a derived value that can be recomputed exactly.
/// Callers that have no segments to offer (none loaded, or the transcript store is
/// unavailable) pass an empty slice — `link_timestamps` degrades to an empty `timestamps`
/// result, never a panic.
fn sermon_note_draft_json(
    v: &selahcue_lan::protocol::SermonNoteDraftView,
    segments: &[selahcue_core::transcript::TranscriptSegment],
) -> (serde_json::Value, Option<&'static str>) {
    let sections: Vec<NoteSectionInput> =
        serde_json::from_str(&v.sections_json).unwrap_or_default();
    let sections = sections_from_input(sections);
    let scriptures: Vec<String> = serde_json::from_str(&v.scriptures_json).unwrap_or_default();

    let (verdicts, embedded_scan_truncated) =
        selahcue_core::providers::verify_scriptures(&scriptures, &sections, |r| {
            !selahcue_scripture::verses(r).is_empty()
        });
    let note =
        (!verdicts.is_empty()).then_some(selahcue_core::providers::SCRIPTURE_VERIFICATION_WORDING);
    let mut caveats: Vec<selahcue_core::providers::DraftCaveat> = verdicts
        .iter()
        .filter(|v| !v.verified)
        .map(
            |v| selahcue_core::providers::DraftCaveat::ScriptureUnverified {
                reference: v.reference.clone(),
            },
        )
        .collect();
    // 86akgqdwc (Sana F2 on PR #48): a reload must carry the same "some references were
    // never checked at all" signal a fresh generation does — re-verification runs fresh
    // here (see this function's own doc comment above) and can hit the same budget.
    if embedded_scan_truncated {
        caveats.push(selahcue_core::providers::DraftCaveat::ScriptureVerificationIncomplete);
    }

    // Reuses `draft_json` rather than a second, slightly-different JSON builder — one
    // place knows the wire contract, whether the draft just arrived from a live
    // generation or was reconstructed here from persisted columns.
    let mut draft = selahcue_core::providers::NoteDraft {
        title: v.title.clone(),
        summary: v.summary.clone(),
        sections,
        scriptures,
        caveats,
        scripture_verdicts: verdicts,
        // Overwritten immediately below by `link_note_timestamps` — listed here (rather
        // than `..Default::default()`) so every field of a fresh `NoteDraft` stays visible
        // at this construction site, matching this function's own existing style.
        timestamps: Vec::new(),
    };
    link_note_timestamps(&mut draft, segments);
    let json = draft_json(&draft);
    (json, note)
}

#[cfg(test)]
mod sermon_note_codec_tests {
    use super::*;
    use selahcue_core::providers::{NotePoint, NoteSection};

    #[test]
    fn sections_to_json_round_trips_through_sections_from_input() {
        // FR-122: both shapes in the same round trip — a flat section and an outline section
        // with a sub-point — so neither path is only exercised on its own.
        let original = vec![
            NoteSection::flat("Prayer points", vec!["Thank God".to_string()]),
            NoteSection::outline(
                "Main points",
                vec![NotePoint {
                    text: "Be faithful".to_string(),
                    sub_points: vec!["In little".to_string(), "In much".to_string()],
                }],
            ),
        ];
        let json = sections_to_json(&original);

        // Round-trip through the SAME deserialization the Tauri IPC boundary uses for an edit
        // submission (`NoteSectionInput`), proving `sections_to_json`'s output is exactly what
        // `sections_from_input` (fed from JS) can read back.
        let input: Vec<NoteSectionInput> =
            serde_json::from_str(&json).expect("sections_to_json must produce valid JSON");
        let rebuilt = sections_from_input(input);

        assert_eq!(rebuilt.len(), 2);
        assert_eq!(rebuilt[0].heading, "Prayer points");
        assert_eq!(rebuilt[0].items(), ["Thank God".to_string()]);
        assert!(rebuilt[0].points().is_empty());
        assert_eq!(rebuilt[1].heading, "Main points");
        assert!(rebuilt[1].items().is_empty());
        assert_eq!(rebuilt[1].points()[0].text, "Be faithful");
        assert_eq!(
            rebuilt[1].points()[0].sub_points,
            vec!["In little".to_string(), "In much".to_string()]
        );
    }

    #[test]
    fn sections_from_input_treats_any_points_as_outline_even_with_items_present() {
        // A section with BOTH `items` and `points` populated is a shape `NoteSection`'s own
        // constructors cannot express (see its "exactly one of these is populated" invariant) —
        // this pins which one wins when a caller (a hand-crafted or buggy JS payload) sends both:
        // points wins, items are dropped, mirroring `NoteSection::is_outline`'s own "points
        // present" test, so a round-tripped section can never silently flip shape.
        let input = vec![NoteSectionInput {
            heading: "Mixed".to_string(),
            items: vec!["should be ignored".to_string()],
            points: vec![NotePointInput {
                text: "wins".to_string(),
                sub_points: vec![],
            }],
        }];
        let sections = sections_from_input(input);
        assert!(sections[0].is_outline());
        assert_eq!(sections[0].points()[0].text, "wins");
        assert!(sections[0].items().is_empty());
    }

    #[test]
    fn scriptures_to_json_round_trips() {
        let refs = vec!["John 3:16".to_string(), "Luke 16:10".to_string()];
        let json = scriptures_to_json(&refs);
        let back: Vec<String> =
            serde_json::from_str(&json).expect("scriptures_to_json must produce valid JSON");
        assert_eq!(back, refs);
    }

    #[test]
    fn corrupt_stored_sections_or_scriptures_degrade_to_empty_not_a_panic() {
        // A `sections`/`scriptures` column is written exclusively by this module's own
        // encoders — a parse failure here means the stored value is corrupt. This must
        // degrade the ONE field, not fail (or panic) the whole draft load.
        let view = selahcue_lan::protocol::SermonNoteDraftView {
            title: "A Title".to_string(),
            summary: None,
            sections_json: "{not valid json".to_string(),
            scriptures_json: "{not valid json".to_string(),
            ai_generated: false,
            disclosure: None,
            provider: "Local (offline)".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 2,
        };
        let (json, note) = sermon_note_draft_json(&view, &[]);
        assert_eq!(json["sections"], serde_json::json!([]));
        assert_eq!(json["scriptures"], serde_json::json!([]));
        assert!(note.is_none(), "nothing to verify, so no note either");
    }

    #[test]
    fn sermon_note_draft_json_reads_the_wire_view_back_into_the_ui_shape() {
        // PR #33 review, Sana F1: this now takes the LAN wire view
        // (`selahcue_lan::protocol::SermonNoteDraftView`), not a `selahcue-data` row — the
        // operator no longer opens that crate's database file for this feature at all.
        let view = selahcue_lan::protocol::SermonNoteDraftView {
            title: "A Title".to_string(),
            summary: Some("A summary".to_string()),
            sections_json: r#"[{"heading":"H","items":["i"],"points":[]}]"#.to_string(),
            scriptures_json: r#"["Gen 1:1"]"#.to_string(),
            ai_generated: true,
            disclosure: Some("disc".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 2,
        };
        let (json, note) = sermon_note_draft_json(&view, &[]);
        assert_eq!(json["title"], "A Title");
        assert_eq!(json["summary"], "A summary");
        assert_eq!(json["sections"][0]["heading"], "H");
        assert_eq!(json["scriptures"][0], "Gen 1:1");
        // 86akby820 (Sana F4): re-verified fresh from the persisted columns — "Gen 1:1" is
        // a real verse, so it comes back verified even though nothing was persisted
        // ABOUT its verdict, only the raw reference text.
        assert_eq!(json["scripture_verdicts"][0]["reference"], "Gen 1:1");
        assert_eq!(json["scripture_verdicts"][0]["verified"], true);
        assert!(
            note.is_some(),
            "the verification-scope note must accompany a reloaded draft too, not only a \
             freshly-generated one"
        );
    }

    #[test]
    fn sermon_note_draft_json_re_verifies_and_catches_an_unverified_reference_on_reload() {
        // The actual harm this fix closes (Sana F4): a fabricated reference must still be
        // marked unverified after a reload/edit-save, not just on the live generation.
        let view = selahcue_lan::protocol::SermonNoteDraftView {
            title: "A Title".to_string(),
            summary: None,
            sections_json: "[]".to_string(),
            scriptures_json: r#"["3 John 4:12"]"#.to_string(),
            ai_generated: true,
            disclosure: Some("disc".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 2,
        };
        let (json, _note) = sermon_note_draft_json(&view, &[]);
        assert_eq!(json["scripture_verdicts"][0]["reference"], "3 John 4:12");
        assert_eq!(json["scripture_verdicts"][0]["verified"], false);
        assert_eq!(
            json["caveats"],
            serde_json::json!([{"kind": "scripture_unverified", "reference": "3 John 4:12"}])
        );
    }

    #[test]
    fn sermon_note_draft_json_re_links_timestamps_fresh_from_the_passed_segments() {
        // 86akgqdw0: timestamps are never persisted (same treatment as `scripture_verdicts`
        // above) — this proves the reload path actually recomputes them from whatever
        // segments the caller passes, not just that the field exists on the wire.
        let view = selahcue_lan::protocol::SermonNoteDraftView {
            title: "A Title".to_string(),
            summary: None,
            sections_json:
                r#"[{"heading":"Chapter markers","items":["Opening prayer"],"points":[]}]"#
                    .to_string(),
            scriptures_json: "[]".to_string(),
            ai_generated: true,
            disclosure: Some("disc".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 2,
        };
        let segments = [selahcue_core::transcript::TranscriptSegment {
            id: 0,
            start_ms: 4_200,
            end_ms: 9_000,
            text: "Let us open this morning in a word of prayer.".to_string(),
        }];
        let (json, _note) = sermon_note_draft_json(&view, &segments);
        assert_eq!(
            json["timestamps"],
            serde_json::json!([{"heading": "Chapter markers", "text": "Opening prayer", "offset_ms": 4_200}])
        );
    }

    #[test]
    fn sermon_note_draft_json_with_no_segments_carries_no_timestamps() {
        let view = selahcue_lan::protocol::SermonNoteDraftView {
            title: "A Title".to_string(),
            summary: None,
            sections_json:
                r#"[{"heading":"Chapter markers","items":["Opening prayer"],"points":[]}]"#
                    .to_string(),
            scriptures_json: "[]".to_string(),
            ai_generated: true,
            disclosure: Some("disc".to_string()),
            provider: "SelahCue AI".to_string(),
            model: None,
            created_at_ms: 1,
            edited_at_ms: 2,
        };
        let (json, _note) = sermon_note_draft_json(&view, &[]);
        assert_eq!(
            json["timestamps"],
            serde_json::json!([]),
            "no segments to link against must degrade to no timestamps, never a panic"
        );
    }
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
    // (up to the 60s transport timeout) never stalls a Tokio worker and starves other async
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
                // No hosted account/endpoint. Try the direct developer-key provider when it is
                // compiled in — this mirrors `notes_status`, where hosted wins and direct is the
                // stand-in for its absence, so what the panel reports and what actually runs are
                // decided by the same precedence.
                #[cfg(feature = "openai-notes")]
                {
                    let transport =
                        selahcue_cloud::transport::ReqwestTransport::new().map_err(|e| {
                            selahcue_core::providers::NoteError::Transport(e.to_string())
                        })?;
                    if let Some(client) = selahcue_cloud::OpenAiNoteProvider::from_env(transport) {
                        return selahcue_cloud::generate_sermon_notes(
                            &cfg,
                            &transcript,
                            true,
                            &client,
                            &local,
                        );
                    }
                }
                // Honour the gate first (ConsentRequired if not opted in), then report the honest
                // NotConfigured state.
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

/// Direct OpenAI GPT generation with a developer key (Phase 1, `openai-notes`).
///
/// **Deliberately throwaway** — the shipping path proxies notes through the SelahCue platform API,
/// and this whole function goes when that lands. It is a sibling of the `cloud-live` path above,
/// not a replacement: when both are compiled the hosted service wins, matching `notes_status`.
///
/// The consent gate is untouched. `generate_sermon_notes` calls `build_note_request` first, so
/// nothing is sent without cloud-notes consent and an explicit Generate, and the request carries
/// the completed transcript only.
#[cfg(feature = "openai-notes")]
async fn run_openai_note_generation(
    cfg: selahcue_core::providers::ProvidersConfig,
    transcript: String,
) -> Result<selahcue_cloud::GenerationOutcome, selahcue_core::providers::NoteError> {
    // Offload the BLOCKING request so a slow provider (up to the transport timeout) never stalls a
    // Tokio worker and starves other async Tauri commands.
    tauri::async_runtime::spawn_blocking(move || {
        let local = selahcue_cloud::LocalNoteProvider::new();
        let transport = selahcue_cloud::transport::ReqwestTransport::new()
            .map_err(|e| selahcue_core::providers::NoteError::Transport(e.to_string()))?;
        match selahcue_cloud::OpenAiNoteProvider::from_env(transport) {
            Some(client) => {
                selahcue_cloud::generate_sermon_notes(&cfg, &transcript, true, &client, &local)
            }
            None => {
                // No developer key. Honour the gate first so the UI still distinguishes
                // ConsentRequired from NotConfigured, then report the honest state.
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

#[cfg(all(not(feature = "cloud-live"), feature = "openai-notes"))]
async fn run_note_generation(
    cfg: selahcue_core::providers::ProvidersConfig,
    transcript: String,
    _state: &State<'_, AppState>,
) -> Result<selahcue_cloud::GenerationOutcome, selahcue_core::providers::NoteError> {
    run_openai_note_generation(cfg, transcript).await
}

#[cfg(all(not(feature = "cloud-live"), not(feature = "openai-notes")))]
async fn run_note_generation(
    cfg: selahcue_core::providers::ProvidersConfig,
    transcript: String,
    _state: &State<'_, AppState>,
) -> Result<selahcue_cloud::GenerationOutcome, selahcue_core::providers::NoteError> {
    // Offline build: honour the consent gate (so the UI still gets ConsentRequired vs
    // NotConfigured correctly), then report the honest "not configured" state — neither the live
    // SelahCue service nor a direct provider is compiled in.
    cfg.build_note_request(&transcript, true)?;
    Err(selahcue_core::providers::NoteError::NotConfigured)
}

/// Generate AI sermon notes from a COMPLETED transcript. Consent-gated end-to-end: with cloud-notes
/// consent off, nothing is sent (returns `consent_required`). The result is operator-local JSON.
///
/// Save-on-generate persistence (86akgqdv0; FR-123 "editable" half) goes through `Backend`'s LAN
/// commands, never a `selahcue-data` connection this process opens itself — PR #33's review
/// (Sana F1 — High) found the operator's own connection was to a DIFFERENT file than the
/// desktop's authoritative store, so the feature was inert outside a test harness. See
/// `Backend::active_transcript_id`/`save_sermon_note_draft`'s doc comments.
///
/// **Regenerate-with-retention (FR-129, 86akgqdx8)** lives here, shared by both
/// `generate_sermon_notes` (below) and `transcript_generate_notes` (the from-history
/// sibling further down): a transcript with NO existing accepted draft is persisted exactly
/// as before this ticket (an immediate save — true first-time generation is unaffected).
/// A transcript that ALREADY has an accepted draft gets the new draft STAGED instead —
/// the accepted draft is never touched by this call, and the operator must explicitly
/// confirm or discard it via the two new commands below. See [`PersistOutcome`].
struct PersistOutcome {
    /// The transcript id persistence was attempted against, when resolvable AND the
    /// attempt succeeded (either an immediate save or a stage) — `None` on any failure
    /// (unresolvable id, host refusal, transport error), mirroring the pre-86akgqdx8
    /// `persisted_transcript_id` contract exactly.
    transcript_id: Option<i64>,
    /// True when an existing accepted draft was found and the new draft was staged
    /// (pending operator confirm/discard) rather than saved immediately.
    pending_confirmation: bool,
    /// The JSON view of the untouched accepted draft (via [`sermon_note_draft_json`]),
    /// present ONLY when `pending_confirmation` is true — so the operator console can
    /// show/compare it alongside the freshly generated one.
    previous_draft: Option<serde_json::Value>,
}

/// Persist a freshly generated draft against `transcript_id`, applying the FR-129 rule
/// described on [`PersistOutcome`]. Best-effort, mirroring the pre-86akgqdx8 behaviour this
/// replaces: persistence failing never blocks the draft from being generated and shown —
/// only the persisted/pending state is affected.
async fn persist_generated_draft(
    state: &State<'_, AppState>,
    transcript_id: i64,
    draft: selahcue_lan::protocol::SermonNoteDraftInput,
) -> PersistOutcome {
    let existing = state
        .backend
        .load_sermon_note_draft(transcript_id)
        .await
        .ok()
        .flatten();
    match existing {
        // An accepted draft already exists: STAGE, never upsert-replace directly — the
        // whole point of FR-129 is that this call must not be able to destroy it.
        Some(existing_view) => {
            match state
                .backend
                .stage_sermon_note_regeneration(transcript_id, draft)
                .await
            {
                Ok(Some(_)) => {
                    // Best-effort (86akgqdw0), same as every other reload path — see
                    // `transcript_segments_for`'s own doc comment.
                    let segments = transcript_segments_for(state, transcript_id);
                    PersistOutcome {
                        transcript_id: Some(transcript_id),
                        pending_confirmation: true,
                        previous_draft: Some(sermon_note_draft_json(&existing_view, &segments).0),
                    }
                }
                Ok(None) => {
                    eprintln!(
                        "selahcue-operator: the host refused to stage the sermon-note regeneration"
                    );
                    PersistOutcome {
                        transcript_id: None,
                        pending_confirmation: false,
                        previous_draft: None,
                    }
                }
                Err(_) => {
                    // Deliberately NOT interpolated — the same TransportError::Protocol
                    // Debug-dump-of-a-whole-ServerMessage risk Sana's F1 fixed elsewhere in
                    // this file; see `transcript_get`'s doc comment for the full call chain.
                    eprintln!("selahcue-operator: failed to stage sermon-note regeneration");
                    PersistOutcome {
                        transcript_id: None,
                        pending_confirmation: false,
                        previous_draft: None,
                    }
                }
            }
        }
        // No accepted draft yet: the ORIGINAL, unchanged immediate-save path.
        None => match state
            .backend
            .save_sermon_note_draft(transcript_id, draft)
            .await
        {
            Ok(Some(_)) => PersistOutcome {
                transcript_id: Some(transcript_id),
                pending_confirmation: false,
                previous_draft: None,
            },
            Ok(None) => {
                eprintln!("selahcue-operator: the host refused to persist the sermon-note draft");
                PersistOutcome {
                    transcript_id: None,
                    pending_confirmation: false,
                    previous_draft: None,
                }
            }
            Err(_) => {
                eprintln!("selahcue-operator: failed to persist sermon-note draft");
                PersistOutcome {
                    transcript_id: None,
                    pending_confirmation: false,
                    previous_draft: None,
                }
            }
        },
    }
}

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
    // Captured before `cfg` moves into `run_note_generation` below (86akby820).
    let scripture_extraction_on = cfg.settings.include.scripture_extraction;
    match run_note_generation(cfg, transcript, &state).await {
        Ok(mut outcome) => {
            // 86akby820 (FR-125/FR-128): every scripture reference this draft carries —
            // in the extracted list AND embedded in a section's body text — is checked
            // against the bundled Bible text, offline, only when the operator turned
            // extraction on. Runs regardless of `degraded`: a reference the preacher
            // genuinely spoke, echoed into the offline scaffold from the real transcript,
            // is exactly as worth confirming as one a cloud model proposed.
            if scripture_extraction_on {
                let (verdicts, embedded_scan_truncated) =
                    selahcue_core::providers::verify_scriptures(
                        &outcome.draft.scriptures,
                        &outcome.draft.sections,
                        |r| !selahcue_scripture::verses(r).is_empty(),
                    );
                outcome
                    .draft
                    .caveats
                    .extend(verdicts.iter().filter(|v| !v.verified).map(|v| {
                        selahcue_core::providers::DraftCaveat::ScriptureUnverified {
                            reference: v.reference.clone(),
                        }
                    }));
                // 86akgqdwc (Sana F2 on PR #48): the embedded-reference scan can hit
                // MAX_EMBEDDED_REFERENCES before every section is considered — a reference
                // past that budget gets no verdict at all, not even `Unverified`. Say so,
                // rather than let the absence of a caveat read as "everything was checked".
                if embedded_scan_truncated {
                    outcome.draft.caveats.push(
                        selahcue_core::providers::DraftCaveat::ScriptureVerificationIncomplete,
                    );
                }
                outcome.draft.scripture_verdicts = verdicts;
            }
            // 86akgqdw0 (FR-124): the live-tail path has no segment structure to link
            // against at all — the operator holds no live `TranscriptLog`/segment array in
            // Rust (the frontend hands this command a pre-flattened `String`). Called with
            // an empty slice anyway, explicitly, so this scope boundary is visible here
            // rather than only in a doc comment: `link_timestamps` degrades an empty
            // `segments` input to an empty `timestamps` result, never a panic. A draft
            // generated live still gains real timestamps once/if it is later reloaded from
            // its (by-then-persisted) transcript, via `sermon_note_draft_json`'s fresh
            // recomputation.
            link_note_timestamps(&mut outcome.draft, &[]);
            // Best-effort, mirroring `with_providers`'s "persistence failure never blocks the
            // edit" contract: resolve the real transcript id from the HOST (never fabricated),
            // then persist against it. Either step failing (no store configured, host refusal,
            // transport error) leaves `transcript_id: null` — the draft is still returned and
            // shown; only the edit surface stays hidden, exactly the pre-86akgqdv0 behaviour
            // for "no persistence available".
            let transcript_id = match state.backend.active_transcript_id().await {
                Ok(id) => id,
                Err(_) => {
                    // Deliberately NOT interpolated (Quinn, PR #50, 86akgqdxr four-reviewer-gate
                    // remediation): the same TransportError::Protocol Debug-dump-of-a-whole-
                    // ServerMessage risk Sana's F1 fixed elsewhere in this file — see
                    // transcript_get's doc comment for the full call chain.
                    eprintln!("selahcue-operator: could not resolve the active transcript id");
                    None
                }
            };
            let persist = match transcript_id {
                Some(transcript_id) => {
                    let draft = selahcue_lan::protocol::SermonNoteDraftInput {
                        title: outcome.draft.title.clone(),
                        summary: outcome.draft.summary.clone(),
                        sections_json: sections_to_json(&sections_to_persist(&outcome.draft)),
                        scriptures_json: scriptures_to_json(&outcome.draft.scriptures),
                        ai_generated: outcome.ai_generated,
                        disclosure: outcome.disclosure.map(str::to_string),
                        provider: outcome.provider_label.clone(),
                        // No `NoteProvider` implementation exposes a model id through
                        // `GenerationOutcome` today — see the migration comment for why
                        // this is honestly `None`, not invented data.
                        model: None,
                    };
                    persist_generated_draft(&state, transcript_id, draft).await
                }
                None => PersistOutcome {
                    transcript_id: None,
                    pending_confirmation: false,
                    previous_draft: None,
                },
            };
            Ok(serde_json::json!({
                "ok": true,
                "degraded": outcome.degraded,
                "provider": outcome.provider_label,
                // FR-123 / FR-128. `ai_generated` comes from the provider that actually SERVED the
                // draft, so a degraded outcome from the offline scaffold is not mislabelled as model
                // output; `disclosure` is Some exactly when `ai_generated`, so the warning cannot be
                // separated from the thing it warns about.
                "ai_generated": outcome.ai_generated,
                "ai_label": selahcue_core::providers::AI_GENERATED_LABEL,
                "disclosure": outcome.disclosure,
                // FR-135. A degraded outcome carries its OWN notice. The fabrication disclosure does
                // not apply to the offline scaffold — it invents nothing — but the operator asked for
                // AI notes and did not get them, and a scaffold shown in silence reads as though it
                // were the notes they asked for. `degraded_notice` is Some exactly when `degraded`.
                "degraded_notice": outcome.degraded
                    .then_some(selahcue_core::providers::DEGRADED_FALLBACK_NOTICE),
                // 86akby820 (FR-125): the address-only scope of scripture verification,
                // stated once here rather than left to the console to phrase — shown
                // exactly when at least one reference was actually checked, so it never
                // appears over an empty "Scriptures" line with nothing to caveat.
                "scripture_verification_note": (!outcome.draft.scripture_verdicts.is_empty())
                    .then_some(selahcue_core::providers::SCRIPTURE_VERIFICATION_WORDING),
                "draft": draft_json(&outcome.draft),
                // `null` when persistence was unavailable/failed — the edit surface stays
                // hidden in that case (nothing to key an edit off) but the draft itself is
                // still shown, exactly like the pre-86akgqdv0 behaviour.
                "transcript_id": persist.transcript_id,
                // FR-129 (86akgqdx8): true when an accepted draft already existed and this
                // fresh draft was STAGED (not saved) — the operator must Confirm or Discard
                // it via `confirm_sermon_note_regeneration`/`discard_sermon_note_regeneration`,
                // both keyed on `transcript_id` above. `previous_draft` is the untouched,
                // still-accepted draft the operator can compare against or keep.
                "pending_confirmation": persist.pending_confirmation,
                "previous_draft": persist.previous_draft,
                "quota": outcome.quota.map(|q| serde_json::json!({
                    "used": q.used, "limit": q.limit, "remaining": q.remaining(), "resets_label": q.resets_label,
                })),
            }))
        }
        Err(e) => Ok(serde_json::json!({
            "ok": false,
            "error": note_error_code(&e),
            "message": e.to_string(),
        })),
    }
}

// ---------------------------------------------------------------------------------------------
// Generate sermon notes from a STORED transcript (86akcffy0; FR-122/130) — the from-history
// sibling of `generate_sermon_notes` above, reachable from a transcript the operator selected in
// the Transcripts list (86akcffvt), not the console currently listening. Same consent gate, same
// provider machinery (`run_note_generation`, untouched), same persist-on-success shape. What
// differs:
//   - The transcript text is a FRESH read of the shared read-only store
//     (`transcript_repo::load` + `transcript_full_text`), never `window.scCompletedTranscript`'s
//     bounded, polled live tail (`OPERATOR_TRANSCRIPT_TAIL = 60`, `selahcue-app/src/
//     controller.rs`).
//   - The draft persists directly against the CALLER-SUPPLIED `id` via
//     `state.backend.save_sermon_note_draft(id, draft)` — never through `active_transcript_id()`,
//     which resolves the LIVE session's transcript and has no relationship to a transcript the
//     operator explicitly opened from history (that call already accepts an explicit id with no
//     "must be active" restriction; see its doc comment).
//   - A stored transcript can be many times larger than the live tail, so the 400,000-character
//     clamp (`selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS`) is realistically
//     reachable here. The decided strategy (86akcffy0 AC2) is: truncate to the head — the same
//     behaviour `bounded_transcript` already applies at send time — but SURFACE it, both to the
//     preview step before Confirm (`note_generation_limits` reports the clamp so the frontend
//     never hardcodes it) and echoed back in this command's own result (`clamp`), rather than
//     letting it happen invisibly.
// ---------------------------------------------------------------------------------------------

/// Join a transcript's segments into one string exactly the way `app.js`'s `syncTranscript`
/// joins the live tail (`\n`-joined segment texts) — so a from-history request is built from the
/// SAME shape of text the live-tail flow always sent, just the complete stored transcript rather
/// than a bounded, polled tail.
fn transcript_full_text(segments: &[selahcue_core::transcript::TranscriptSegment]) -> String {
    segments
        .iter()
        .map(|s| s.text.as_str())
        .collect::<Vec<_>>()
        .join("\n")
}

/// What the from-history transcript-length clamp will do to `transcript`, for an HONEST preview
/// (86akcffy0 AC2) — `None` when it fits under
/// [`selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS`] untouched, `Some` with exactly how
/// much will be left out otherwise. Never changes what is actually sent — `bounded_transcript`
/// still applies the real clamp downstream in the OpenAI transport; this only reports it.
#[derive(serde::Serialize, Debug, Clone, PartialEq, Eq)]
struct TranscriptClampNotice {
    /// The full transcript's length, in characters, before any clamping.
    total_chars: usize,
    /// How many trailing characters will be left out of the request.
    dropped_chars: usize,
    /// The clamp itself, mirrored here (not just in [`note_generation_limits`]) so a result the
    /// frontend already has in hand is self-describing.
    max_chars: usize,
}

/// Whether `t` may be used for the from-history Generate flow — `false` while it is still
/// recording (`ended_at_ms` is `None`). See [`transcript_generate_notes`]'s doc comment for why
/// this must be a hard refusal, not a race-narrowing check.
fn transcript_is_eligible_for_generate(
    t: &selahcue_data::transcript_repo::TranscriptDetail,
) -> bool {
    t.ended_at_ms.is_some()
}

fn transcript_clamp_notice(transcript: &str) -> Option<TranscriptClampNotice> {
    let (_, dropped) = selahcue_cloud::transcript_bounds::bounded_transcript(transcript);
    dropped.map(|dropped_chars| TranscriptClampNotice {
        total_chars: transcript.chars().count(),
        dropped_chars,
        max_chars: selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS,
    })
}

/// The canonical note-generation transcript-length clamp, for the frontend's preview step —
/// reachable in EVERY build configuration (`selahcue_cloud::transcript_bounds` is unconditionally
/// compiled, 86akcffy0), so `transcripts.js` never hardcodes/duplicates the number.
#[tauri::command]
fn note_generation_limits() -> serde_json::Value {
    serde_json::json!({ "max_transcript_chars": selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS })
}

/// Generate AI sermon notes from the FULL stored text of transcript `id` (86akcffy0). See the
/// section comment above for how this differs from `generate_sermon_notes`; everything else —
/// the consent gate, the provider fallback ladder, the response shape — is that same function's
/// machinery, reused unchanged via [`run_note_generation`].
///
/// Refuses (honestly, `error: "transcript_not_ended"`, no network call) when `id`'s transcript
/// is still recording (`ended_at_ms` is `None`) — Sana's security review (86akcffy0): this
/// path's whole design leans on a stored transcript being STATIC between the preview the
/// operator reviewed and the request this command actually reads/sends. That is true once
/// [`selahcue_data::transcript_repo::end`] has been called (nothing in this codebase appends a
/// segment to an ended transcript again — a new session starts a NEW row) and false before it:
/// `transcript_list` orders by `started_at DESC` with no `ended_at` filter, so an in-progress
/// service can be the very first, most-clickable card, its writer still appending segments the
/// preview never showed and the "complete transcript... every recorded segment" disclosure copy
/// would then be lying about. Refusing outright — rather than re-checking the segment set for
/// growth — is both simpler and strictly stronger: it removes the race window entirely instead
/// of narrowing it.
#[tauri::command]
async fn transcript_generate_notes(
    id: i64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let before = with_transcript_db(&state, |db| selahcue_data::transcript_repo::load(db, id))?;
    if !transcript_is_eligible_for_generate(&before) {
        return Ok(serde_json::json!({
            "ok": false,
            "error": "transcript_not_ended",
            "message": "This service is still being recorded. Generate sermon notes once it ends.",
        }));
    }
    let transcript = transcript_full_text(&before.segments);
    let clamp = transcript_clamp_notice(&transcript);

    // Snapshot the config under the lock, then generate without holding it — same discipline as
    // `generate_sermon_notes` above.
    let cfg = {
        state
            .providers
            .lock()
            .map_err(|e| format!("providers lock: {e}"))?
            .clone()
    };

    match run_note_generation(cfg, transcript, &state).await {
        Ok(mut outcome) => {
            // FR-123's "the source transcript is unchanged" invariant, RE-VERIFIED rather than
            // assumed from `transcript_db` being a read-only connection: a from-history generate
            // must never persist a draft against a record that no longer matches what was
            // actually sent. See `source_transcript_is_unchanged_by_generation` for the direct
            // test of the comparison this leans on.
            let after =
                with_transcript_db(&state, |db| selahcue_data::transcript_repo::load(db, id))?;
            if after.segments != before.segments {
                return Err(
                    "the source transcript changed while generating notes; refusing to persist \
                     a draft against a record that may no longer match what was sent"
                        .to_string(),
                );
            }
            // 86akgqdw0 (FR-124): the ONE entrypoint with real, full-fidelity segment data —
            // linked against the just-confirmed-unchanged `after.segments`, never `before`'s
            // (identical content, but `after` is the copy the unchanged-source check just
            // vouched for). This is the shared `link_note_timestamps` helper
            // `generate_sermon_notes` also routes through, so the linking behaviour cannot
            // drift between the two entrypoints.
            link_note_timestamps(&mut outcome.draft, &after.segments);

            let draft = selahcue_lan::protocol::SermonNoteDraftInput {
                title: outcome.draft.title.clone(),
                summary: outcome.draft.summary.clone(),
                sections_json: sections_to_json(&outcome.draft.sections),
                scriptures_json: scriptures_to_json(&outcome.draft.scriptures),
                ai_generated: outcome.ai_generated,
                disclosure: outcome.disclosure.map(str::to_string),
                provider: outcome.provider_label.clone(),
                // See `generate_sermon_notes`'s identical field: no `NoteProvider` exposes a
                // model id through `GenerationOutcome` today.
                model: None,
            };
            let persist = persist_generated_draft(&state, id, draft).await;

            Ok(serde_json::json!({
                "ok": true,
                "degraded": outcome.degraded,
                "provider": outcome.provider_label,
                "ai_generated": outcome.ai_generated,
                "ai_label": selahcue_core::providers::AI_GENERATED_LABEL,
                "disclosure": outcome.disclosure,
                "degraded_notice": outcome.degraded
                    .then_some(selahcue_core::providers::DEGRADED_FALLBACK_NOTICE),
                "draft": draft_json(&outcome.draft),
                "transcript_id": persist.transcript_id,
                // FR-129 (86akgqdx8) — see `generate_sermon_notes`'s identical fields.
                "pending_confirmation": persist.pending_confirmation,
                "previous_draft": persist.previous_draft,
                "quota": outcome.quota.map(|q| serde_json::json!({
                    "used": q.used, "limit": q.limit, "remaining": q.remaining(), "resets_label": q.resets_label,
                })),
                "clamp": clamp,
            }))
        }
        Err(e) => Ok(serde_json::json!({
            "ok": false,
            "error": note_error_code(&e),
            "message": e.to_string(),
            "clamp": clamp,
        })),
    }
}

#[cfg(test)]
mod transcript_generate_notes_tests {
    use super::*;
    use selahcue_data::{sermon_note_repo, transcript_repo, Database};

    fn fixture_db_with_segments(texts: &[&str]) -> (Database, i64) {
        let db = Database::open_in_memory().expect("in-memory db opens");
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .expect("create transcript");
        let mut t_ms = 0u64;
        for text in texts {
            transcript_repo::append_segment(&db, id, t_ms, t_ms + 1_000, text)
                .expect("append segment");
            t_ms += 1_000;
        }
        transcript_repo::end(&db, id, t_ms as i64).expect("end transcript");
        (db, id)
    }

    /// As [`fixture_db_with_segments`], but never calls `transcript_repo::end` — a service still
    /// being recorded (86akcffy0, Sana review).
    fn fixture_db_in_progress(texts: &[&str]) -> (Database, i64) {
        let db = Database::open_in_memory().expect("in-memory db opens");
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .expect("create transcript");
        let mut t_ms = 0u64;
        for text in texts {
            transcript_repo::append_segment(&db, id, t_ms, t_ms + 1_000, text)
                .expect("append segment");
            t_ms += 1_000;
        }
        (db, id)
    }

    /// Sana's High finding (86akcffy0): a transcript still recording must never be eligible for
    /// from-history Generate — nothing else in this flow (the preview snapshot, the disclosure
    /// copy's "complete transcript" claim, the before/after unchanged check) holds once the
    /// writer can still append segments underneath it.
    #[test]
    fn an_in_progress_transcript_is_not_eligible_for_generate() {
        let (db, id) = fixture_db_in_progress(&["still recording"]);
        let t = transcript_repo::load(&db, id).expect("load");
        assert_eq!(
            t.ended_at_ms, None,
            "premise: this transcript has not ended"
        );
        assert!(!transcript_is_eligible_for_generate(&t));
    }

    /// Positive control for the check above: an ordinary ENDED transcript remains eligible —
    /// otherwise "refused" would be indistinguishable from a check that always refuses.
    #[test]
    fn an_ended_transcript_is_eligible_for_generate() {
        let (db, id) = fixture_db_with_segments(&["a normal, finished service"]);
        let t = transcript_repo::load(&db, id).expect("load");
        assert!(
            t.ended_at_ms.is_some(),
            "premise: this transcript has ended"
        );
        assert!(transcript_is_eligible_for_generate(&t));
    }

    /// The load-bearing behaviour this whole ticket exists for: the from-history request is
    /// built from EVERY stored segment, not a 60-segment tail. `OPERATOR_TRANSCRIPT_TAIL` (60,
    /// `selahcue-app::controller`) would drop segment 0 from a 70-segment transcript; this
    /// asserts segment 0's text is still present in the joined string.
    #[test]
    fn the_full_text_includes_segments_far_past_the_live_tail_bound() {
        let texts: Vec<String> = (0..70).map(|i| format!("segment-{i}")).collect();
        let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
        let (db, id) = fixture_db_with_segments(&refs);
        let t = transcript_repo::load(&db, id).expect("load");
        assert_eq!(
            t.segments.len(),
            70,
            "premise: more than OPERATOR_TRANSCRIPT_TAIL (60)"
        );
        let joined = transcript_full_text(&t.segments);
        assert!(
            joined.contains("segment-0"),
            "the first segment must survive — a 60-tail would have dropped it"
        );
        assert!(joined.contains("segment-69"));
    }

    /// Matches `app.js`'s `syncTranscript` bridge (`segs.map(s => s.text).join("\n")`) exactly —
    /// this is the wire contract the from-history flow now shares with the live-tail one.
    #[test]
    fn segments_are_joined_with_newlines_matching_the_live_tail_bridge() {
        let (db, id) =
            fixture_db_with_segments(&["Good morning, church.", "Turn to Romans eight."]);
        let t = transcript_repo::load(&db, id).expect("load");
        assert_eq!(
            transcript_full_text(&t.segments),
            "Good morning, church.\nTurn to Romans eight."
        );
    }

    #[test]
    fn a_transcript_under_the_clamp_gets_no_notice() {
        let (db, id) = fixture_db_with_segments(&["short and unremarkable"]);
        let t = transcript_repo::load(&db, id).expect("load");
        let joined = transcript_full_text(&t.segments);
        assert_eq!(transcript_clamp_notice(&joined), None);
    }

    /// AC2: a transcript at/near the clamp gets a VISIBLE notice, not a silent cut. This is the
    /// exact information `transcripts.js`'s preview step renders before Confirm.
    #[test]
    fn a_transcript_over_the_clamp_reports_the_real_drop_count() {
        let huge = "a".repeat(selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS + 123);
        let notice = transcript_clamp_notice(&huge).expect("over the clamp must produce a notice");
        assert_eq!(notice.dropped_chars, 123);
        assert_eq!(
            notice.total_chars,
            selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS + 123
        );
        assert_eq!(
            notice.max_chars,
            selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS
        );
    }

    /// `note_generation_limits` is what lets the frontend compute the SAME notice above without
    /// hardcoding `400_000` — pin the field name/value so `transcripts.js` and this command
    /// cannot silently drift apart.
    #[test]
    fn note_generation_limits_reports_the_real_clamp() {
        let v = note_generation_limits();
        assert_eq!(
            v["max_transcript_chars"],
            serde_json::json!(selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS)
        );
    }

    /// FR-123's "the source transcript is unchanged" invariant, at the layer
    /// `transcript_generate_notes` actually relies on: two consecutive reads of a store nothing
    /// wrote to in between must agree exactly. This is the premise the command's own
    /// before/after equality check leans on — see its doc comment.
    #[test]
    fn source_transcript_is_unchanged_by_generation() {
        let (db, id) =
            fixture_db_with_segments(&["Good morning, church.", "Turn to Romans eight."]);
        let before = transcript_repo::load(&db, id).expect("load before");
        // Nothing runs between these two reads — `transcript_generate_notes` does real
        // generation work here instead; this test isolates the invariant it depends on.
        let after = transcript_repo::load(&db, id).expect("load after");
        assert_eq!(
            before.segments, after.segments,
            "reading the same read-only store twice must yield identical segments"
        );
    }

    /// The consent gate the from-history path relies on is `ProvidersConfig::
    /// build_note_request` — the SAME egress choke point `generate_sermon_notes`'s existing
    /// crate-level test already proves refuses with zero network calls
    /// (`selahcue-cloud/tests/test_openai.rs::
    /// with_consent_off_generate_makes_no_network_call_and_says_consent_is_required`). This test
    /// proves specifically that the TEXT OUR NEW PATH BUILDS — a full multi-segment transcript
    /// joined by `transcript_full_text`, not a short live-tail string — does not somehow bypass
    /// that gate: build_note_request must still refuse it.
    #[test]
    fn consent_off_refuses_the_from_history_text_before_any_provider_is_touched() {
        let texts: Vec<String> = (0..70).map(|i| format!("segment-{i}")).collect();
        let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
        let (db, id) = fixture_db_with_segments(&refs);
        let t = transcript_repo::load(&db, id).expect("load");
        let transcript = transcript_full_text(&t.segments);

        let cfg = selahcue_core::providers::ProvidersConfig::default();
        assert!(!cfg.consent.cloud_notes, "premise: consent defaults to OFF");
        let err = cfg
            .build_note_request(&transcript, true)
            .expect_err("consent is off; the request must be refused");
        assert_eq!(err, selahcue_core::providers::NoteError::ConsentRequired);
    }

    /// `notes_generated` (`transcript_get`'s field, 86akcffy0) must become `true` once a draft
    /// has actually been persisted against a transcript, and stay `false` until then — the exact
    /// value a future ticket's comment asked this ticket to make real.
    #[test]
    fn notes_generated_reflects_a_persisted_draft() {
        let (db, id) = fixture_db_with_segments(&["Good morning, church."]);
        assert_eq!(
            sermon_note_repo::find_by_transcript(&db, id).expect("query"),
            None,
            "no draft has been persisted yet"
        );

        sermon_note_repo::create(
            &db,
            &sermon_note_repo::NewSermonNote {
                transcript_id: id,
                title: "A Title".to_string(),
                summary: None,
                sections_json: "[]".to_string(),
                scriptures_json: "[]".to_string(),
                ai_generated: true,
                disclosure: Some("disc".to_string()),
                provider: "OpenAI".to_string(),
                model: None,
                created_at_ms: 1,
            },
        )
        .expect("create draft");

        assert!(
            sermon_note_repo::find_by_transcript(&db, id)
                .expect("query")
                .is_some(),
            "notes_generated must be true once a draft exists for this transcript"
        );
    }

    /// Sana's F4 (86akcffy0): on a store from a build older than the v21 migration that added
    /// `sermon_note` (`open_existing_readonly` never migrates), `find_by_transcript` errors —
    /// `notes_generated_for` must degrade to `false`, never propagate and break the whole
    /// transcript read. Simulated directly rather than constructing a real pre-v21 fixture: drop
    /// the table `find_by_transcript`'s own query names, on an otherwise normal database.
    #[test]
    fn notes_generated_for_degrades_to_false_when_the_sermon_note_table_is_missing() {
        let (db, id) = fixture_db_with_segments(&["Good morning, church."]);
        db.conn()
            .execute("DROP TABLE sermon_note", [])
            .expect("drop table for the test fixture");

        assert!(
            sermon_note_repo::find_by_transcript(&db, id).is_err(),
            "premise: the query against the dropped table must actually fail"
        );
        assert!(
            !notes_generated_for(&db, id),
            "a query failure must degrade to false, not propagate and break transcript_get"
        );
    }

    /// Positive control for the fault-isolation above: on a normal store, `notes_generated_for`
    /// still reports the real answer — otherwise "degrades to false" would be indistinguishable
    /// from "always returns false".
    #[test]
    fn notes_generated_for_reports_true_on_a_normal_store_with_a_draft() {
        let (db, id) = fixture_db_with_segments(&["Good morning, church."]);
        assert!(!notes_generated_for(&db, id), "no draft persisted yet");

        sermon_note_repo::create(
            &db,
            &sermon_note_repo::NewSermonNote {
                transcript_id: id,
                title: "A Title".to_string(),
                summary: None,
                sections_json: "[]".to_string(),
                scriptures_json: "[]".to_string(),
                ai_generated: true,
                disclosure: Some("disc".to_string()),
                provider: "OpenAI".to_string(),
                model: None,
                created_at_ms: 1,
            },
        )
        .expect("create draft");

        assert!(notes_generated_for(&db, id));
    }
}

/// Build the `{"ok": true, ...}` JSON body shared by `load_sermon_note_draft`,
/// `update_sermon_note_draft`, and the FR-129 (86akgqdx8) `confirm_sermon_note_regeneration`/
/// `discard_sermon_note_regeneration` below — "here is the CURRENT accepted draft", the same
/// shape every one of those commands returns on success.
///
/// `segments` (86akgqdw0) is passed straight through to [`sermon_note_draft_json`] for its own
/// fresh-recompute-on-every-read timestamp linking — every caller resolves it the same
/// best-effort way, via [`transcript_segments_for`].
fn sermon_note_view_ok_json(
    transcript_id: i64,
    view: &selahcue_lan::protocol::SermonNoteDraftView,
    segments: &[selahcue_core::transcript::TranscriptSegment],
) -> serde_json::Value {
    let (draft, scripture_verification_note) = sermon_note_draft_json(view, segments);
    serde_json::json!({
        "ok": true,
        "transcript_id": transcript_id,
        "ai_generated": view.ai_generated,
        "ai_label": selahcue_core::providers::AI_GENERATED_LABEL,
        "disclosure": view.disclosure,
        "provider": view.provider,
        "scripture_verification_note": scripture_verification_note,
        "draft": draft,
    })
}

/// Load the persisted sermon-note draft for the currently active transcript, if any
/// (86akgqdv0). Called on Settings panel activation so a draft generated in a prior
/// session — or edited and left unread — reappears after a restart. `{"ok": false}`
/// (not an error) when there is no host connection, no transcript yet, or no draft —
/// an absent draft is a normal, common state, not a failure.
///
/// Goes through `Backend`'s LAN commands — see `generate_sermon_notes`'s doc comment
/// for why (PR #33 review, Sana F1).
#[tauri::command]
async fn load_sermon_note_draft(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let Ok(Some(transcript_id)) = state.backend.active_transcript_id().await else {
        return Ok(serde_json::json!({ "ok": false }));
    };
    match state.backend.load_sermon_note_draft(transcript_id).await {
        Ok(Some(view)) => {
            // Best-effort (86akgqdw0): a segments-read failure here must never block loading
            // the draft itself — see `transcript_segments_for`'s own doc comment.
            let segments = transcript_segments_for(&state, transcript_id);
            let (draft, scripture_verification_note) = sermon_note_draft_json(&view, &segments);
            Ok(serde_json::json!({
                "ok": true,
                "transcript_id": transcript_id,
                "ai_generated": view.ai_generated,
                "ai_label": selahcue_core::providers::AI_GENERATED_LABEL,
                // FR-123/FR-128: the label and disclosure travel with the draft through a
                // restart exactly as they did through an edit — read back verbatim from
                // what the host persisted, never re-derived here.
                "disclosure": view.disclosure,
                "provider": view.provider,
                // 86akby820 (Sana F4): re-verified fresh on every load — see
                // `sermon_note_draft_json`'s doc comment for why this is safe and cheap.
                "scripture_verification_note": scripture_verification_note,
                "draft": draft,
            }))
        }
        Ok(None) => Ok(serde_json::json!({ "ok": false })),
        Err(_) => {
            // Deliberately NOT interpolated (Sana, PR #50 F1, mirrored from `transcript_get`'s
            // identical fix): this error can carry a `Debug`-dumped `ServerMessage::OperatorState`
            // with live transcript/detection text (FR-082) — see `transcript_get`'s doc comment
            // for the full call chain.
            eprintln!("selahcue-operator: failed to load sermon-note draft");
            Ok(serde_json::json!({ "ok": false }))
        }
    }
}

/// Apply an operator edit to the persisted draft's title/summary/sections/scriptures
/// (86akgqdv0). `transcript_id` is the id returned by a prior `generate_sermon_notes`
/// or `load_sermon_note_draft` call. Touches ONLY the editable columns — the wire type
/// (`SermonNoteEditInput`) structurally cannot carry `ai_generated`/`disclosure`/
/// `provider`, so an edit can never silently drop the FR-123 label or FR-128
/// disclosure; this command's own response echoes them back unchanged (re-read from
/// the host) so the UI never has to assume that rather than see it.
///
/// A malformed `sections`/`points` shape (wrong JSON types) is rejected by Tauri's
/// own IPC deserialization before this function body ever runs. Goes through
/// `Backend`'s LAN commands — see `generate_sermon_notes`'s doc comment for why (PR #33
/// review, Sana F1). The host's specific refusal reason (no draft yet vs. an oversized
/// field) does not currently cross the wire as distinct codes — `DenyReason` is a
/// small, shared enum with no per-command message field — so both surface here as one
/// honest `"refused"`, not a silent failure or a fabricated distinction.
#[tauri::command]
async fn update_sermon_note_draft(
    transcript_id: i64,
    title: String,
    summary: Option<String>,
    sections: Vec<NoteSectionInput>,
    scriptures: Vec<String>,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    let sections = sections_from_input(sections);
    let edit = selahcue_lan::protocol::SermonNoteEditInput {
        title,
        summary,
        sections_json: sections_to_json(&sections),
        scriptures_json: scriptures_to_json(&scriptures),
    };
    match state
        .backend
        .update_sermon_note_draft(transcript_id, edit)
        .await
    {
        Ok(Some(view)) => {
            // Best-effort (86akgqdw0): a segments-read failure here must never block the
            // edit response itself — see `transcript_segments_for`'s own doc comment.
            let segments = transcript_segments_for(&state, transcript_id);
            let (draft, scripture_verification_note) = sermon_note_draft_json(&view, &segments);
            Ok(serde_json::json!({
                "ok": true,
                "transcript_id": transcript_id,
                "ai_generated": view.ai_generated,
                "ai_label": selahcue_core::providers::AI_GENERATED_LABEL,
                "disclosure": view.disclosure,
                "provider": view.provider,
                // 86akby820 (Sana F4): re-verified fresh against what was just saved.
                "scripture_verification_note": scripture_verification_note,
                "draft": draft,
            }))
        }
        Ok(None) => Ok(serde_json::json!({
            "ok": false, "error": "refused",
            "message": "The host refused this edit: no saved draft exists for this \
                transcript, or a field was too large.",
        })),
        Err(_) => Ok(serde_json::json!({
            // Deliberately NOT the raw error string (Quinn, PR #50, 86akgqdxr four-reviewer-gate
            // remediation — the same F1-class risk Sana found elsewhere in this file, but WORSE
            // here: this "message" is rendered directly on the operator's own screen via
            // showGenError/saveDraftEdit (role="alert"), not merely logged. See transcript_get's
            // doc comment for the full TransportError::Protocol Debug-dump call chain.
            "ok": false, "error": "storage_error",
            "message": "The host reported a connection or protocol problem while saving this \
                edit. Check the connection and try again.",
        })),
    }
}

/// Accept the pending regeneration for `transcript_id` (FR-129, 86akgqdx8), replacing the
/// accepted draft with it — the "Use this draft" action on the regenerate-confirmation
/// banner. `transcript_id` is the id `generate_sermon_notes`/`transcript_generate_notes`
/// returned alongside `pending_confirmation: true`.
///
/// `{"ok": false, "error": "refused", ...}` when the host refuses: nothing is currently
/// pending for this transcript, OR accepting would strip the FR-123 AI-generated label from
/// an already AI-generated draft (`sermon_note_repo::confirm_regeneration`'s "once
/// AI-generated, always AI-generated" guard — the case a degraded/local-fallback regenerate
/// produces). Either way the pending draft is left exactly as it was, still available to
/// discard.
#[tauri::command]
async fn confirm_sermon_note_regeneration(
    transcript_id: i64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    match state
        .backend
        .confirm_sermon_note_regeneration(transcript_id)
        .await
    {
        Ok(Some(slot)) => match slot.current {
            // Best-effort (86akgqdw0), same as every other reload path — see
            // `transcript_segments_for`'s own doc comment.
            Some(view) => {
                let segments = transcript_segments_for(&state, transcript_id);
                Ok(sermon_note_view_ok_json(transcript_id, &view, &segments))
            }
            None => Ok(serde_json::json!({
                "ok": false, "error": "refused",
                "message": "The host has no accepted draft for this transcript.",
            })),
        },
        Ok(None) => Ok(serde_json::json!({
            "ok": false, "error": "refused",
            "message": "The host refused to confirm this regeneration: nothing is pending, \
                or accepting it would remove the AI-generated label from an already \
                AI-generated draft.",
        })),
        Err(_) => Ok(serde_json::json!({
            // Same Debug-dump-avoidance discipline as `update_sermon_note_draft` above.
            "ok": false, "error": "storage_error",
            "message": "The host reported a connection or protocol problem while confirming \
                this regeneration. Check the connection and try again.",
        })),
    }
}

/// Discard the pending regeneration for `transcript_id` (FR-129, 86akgqdx8), leaving the
/// accepted draft completely unchanged — the "Keep my current notes" action on the
/// regenerate-confirmation banner. A harmless success even if nothing was pending.
#[tauri::command]
async fn discard_sermon_note_regeneration(
    transcript_id: i64,
    state: State<'_, AppState>,
) -> Result<serde_json::Value, String> {
    match state
        .backend
        .discard_sermon_note_regeneration(transcript_id)
        .await
    {
        Ok(Some(slot)) => match slot.current {
            // Best-effort (86akgqdw0), same as every other reload path — see
            // `transcript_segments_for`'s own doc comment.
            Some(view) => {
                let segments = transcript_segments_for(&state, transcript_id);
                Ok(sermon_note_view_ok_json(transcript_id, &view, &segments))
            }
            // No accepted draft at all is an odd state to discard against, but honest rather
            // than fabricated — mirrors `save_sermon_note_draft`'s own "no store configured"
            // shape for an unavailable store.
            None => Ok(serde_json::json!({ "ok": false })),
        },
        Ok(None) => Ok(serde_json::json!({ "ok": false })),
        Err(_) => Ok(serde_json::json!({
            "ok": false, "error": "storage_error",
            "message": "The host reported a connection or protocol problem while discarding \
                this regeneration. Check the connection and try again.",
        })),
    }
}

/// FR-129 (86akgqdx8) operator-layer tests for the regenerate-with-retention flow.
/// `selahcue-data`/`selahcue-app` already prove the retention model itself exhaustively (stage/
/// confirm/discard semantics, the single-pending-slot rule, the "once AI-generated, always
/// AI-generated" guard) — what is unique to THIS crate, and untested anywhere else, is
/// `persist_generated_draft`'s own branch (does an existing draft cause a STAGE rather than an
/// upsert) and the two new Tauri commands' own JSON shape end to end through a real backend.
///
/// `run_note_generation`'s real provider paths (`cloud-live`/`openai-notes`) need a live network
/// call or a developer key this suite must never touch (the repo's own constraint: "Test against
/// a stub transport; never live OpenAI") — with neither feature enabled (the default build this
/// crate's `cargo test` runs under), generation itself always ends in `NotConfigured`/
/// `ConsentRequired`, never `Ok`. So `persist_generated_draft` is exercised directly with a
/// hand-built `SermonNoteDraftInput`, exactly as if a real generation had just produced it,
/// rather than by driving `generate_sermon_notes` all the way to a successful outcome.
#[cfg(test)]
mod regenerate_with_retention_tests {
    use super::*;
    use selahcue_app::{RegenerationSlot, SermonNoteStore};
    use selahcue_data::{sermon_note_repo, transcript_repo, Database};

    /// The same `selahcue_data::sermon_note_repo` adapter `selahcue-desktop::RealSermonNoteStore`
    /// runs in production, rebuilt here so this crate's own tests can drive
    /// `persist_generated_draft`/the two new commands against a REAL retention-capable store —
    /// `NullSermonNoteStore` refuses every one of these calls by design and would prove nothing.
    struct DbStore {
        db: Database,
    }

    impl SermonNoteStore for DbStore {
        fn active_transcript_id(&mut self) -> Result<Option<i64>, String> {
            transcript_repo::most_recent_id(&self.db).map_err(|e| e.to_string())
        }
        fn save_draft(
            &mut self,
            transcript_id: i64,
            draft: &selahcue_lan::protocol::SermonNoteDraftInput,
        ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
            let note = sermon_note_repo::NewSermonNote {
                transcript_id,
                title: draft.title.clone(),
                summary: draft.summary.clone(),
                sections_json: draft.sections_json.clone(),
                scriptures_json: draft.scriptures_json.clone(),
                ai_generated: draft.ai_generated,
                disclosure: draft.disclosure.clone(),
                provider: draft.provider.clone(),
                model: draft.model.clone(),
                created_at_ms: 1_000,
            };
            sermon_note_repo::create(&self.db, &note).map_err(|e| e.to_string())?;
            let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
                .map_err(|e| e.to_string())?
                .expect("draft vanished immediately after create");
            Ok(view_of(&record))
        }
        fn load_draft(
            &mut self,
            transcript_id: i64,
        ) -> Result<Option<selahcue_lan::protocol::SermonNoteDraftView>, String> {
            sermon_note_repo::find_by_transcript(&self.db, transcript_id)
                .map(|opt| opt.map(|r| view_of(&r)))
                .map_err(|e| e.to_string())
        }
        fn update_draft(
            &mut self,
            _transcript_id: i64,
            _edit: &selahcue_lan::protocol::SermonNoteEditInput,
        ) -> Result<selahcue_lan::protocol::SermonNoteDraftView, String> {
            Err("not exercised by this suite".into())
        }
        fn stage_regeneration(
            &mut self,
            transcript_id: i64,
            draft: &selahcue_lan::protocol::SermonNoteDraftInput,
        ) -> Result<RegenerationSlot, String> {
            let pending = sermon_note_repo::PendingRegeneration {
                title: draft.title.clone(),
                summary: draft.summary.clone(),
                sections_json: draft.sections_json.clone(),
                scriptures_json: draft.scriptures_json.clone(),
                ai_generated: draft.ai_generated,
                disclosure: draft.disclosure.clone(),
                provider: draft.provider.clone(),
                model: draft.model.clone(),
                generated_at_ms: 2_000,
            };
            sermon_note_repo::stage_regeneration(&self.db, transcript_id, &pending)
                .map_err(|e| e.to_string())?;
            let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
                .map_err(|e| e.to_string())?
                .expect("draft vanished immediately after stage");
            Ok(slot_of(&record))
        }
        fn confirm_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String> {
            let record = sermon_note_repo::confirm_regeneration(&self.db, transcript_id)
                .map_err(|e| e.to_string())?;
            Ok(slot_of(&record))
        }
        fn discard_regeneration(&mut self, transcript_id: i64) -> Result<RegenerationSlot, String> {
            sermon_note_repo::discard_regeneration(&self.db, transcript_id)
                .map_err(|e| e.to_string())?;
            let record = sermon_note_repo::find_by_transcript(&self.db, transcript_id)
                .map_err(|e| e.to_string())?
                .expect("draft vanished immediately after discard");
            Ok(slot_of(&record))
        }
    }

    fn view_of(
        r: &sermon_note_repo::SermonNoteRecord,
    ) -> selahcue_lan::protocol::SermonNoteDraftView {
        selahcue_lan::protocol::SermonNoteDraftView {
            title: r.title.clone(),
            summary: r.summary.clone(),
            sections_json: r.sections_json.clone(),
            scriptures_json: r.scriptures_json.clone(),
            ai_generated: r.ai_generated,
            disclosure: r.disclosure.clone(),
            provider: r.provider.clone(),
            model: r.model.clone(),
            created_at_ms: r.created_at_ms,
            edited_at_ms: r.edited_at_ms,
        }
    }

    fn slot_of(r: &sermon_note_repo::SermonNoteRecord) -> RegenerationSlot {
        RegenerationSlot {
            current: Some(view_of(r)),
            pending: r
                .pending
                .as_ref()
                .map(|p| selahcue_lan::protocol::SermonNoteDraftView {
                    title: p.title.clone(),
                    summary: p.summary.clone(),
                    sections_json: p.sections_json.clone(),
                    scriptures_json: p.scriptures_json.clone(),
                    ai_generated: p.ai_generated,
                    disclosure: p.disclosure.clone(),
                    provider: p.provider.clone(),
                    model: p.model.clone(),
                    created_at_ms: p.generated_at_ms,
                    edited_at_ms: p.generated_at_ms,
                }),
        }
    }

    /// A ready-to-run `AppState` wired to a REAL, DB-backed sermon-note store (via a
    /// `LiveController` in `Backend::Local`) with one ended transcript already in it —
    /// `listening.rs`'s `tauri::test::mock_app()` pattern is the established way this crate
    /// builds a full Tauri `State` in a unit test without a running window; reused verbatim.
    fn state_with_transcript(
        consent_cloud_notes: bool,
    ) -> (tauri::App<tauri::test::MockRuntime>, i64) {
        let db = Database::open_in_memory().expect("in-memory db opens");
        let id = transcript_repo::create(
            &db,
            &transcript_repo::NewTranscript {
                label: "Sunday Service".to_string(),
                provider: "manual".to_string(),
                plan_id: None,
                started_at_ms: 1_000,
            },
        )
        .expect("create transcript");
        transcript_repo::append_segment(&db, id, 0, 1_000, "Good morning, church.")
            .expect("append segment");
        transcript_repo::end(&db, id, 1_000).expect("end transcript");

        let mut plan = ServicePlan::new("Test Service");
        plan.add_item(ItemKind::Section, "Sermon");
        let controller = Arc::new(Mutex::new(LiveController::new(
            plan,
            320,
            180,
            Theme::dark(),
        )));
        controller
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .set_sermon_note_store(Box::new(DbStore { db }));
        let shell = OperatorShell::new(controller);

        let mut providers = selahcue_core::providers::ProvidersConfig::default();
        providers.consent.cloud_notes = consent_cloud_notes;

        let app = tauri::test::mock_app();
        app.handle().manage(AppState {
            backend: Backend::Local(shell),
            deck: Mutex::new(crate::DeckWorkspace::demo()),
            library: Mutex::new(crate::DeckLibrary::load(None)),
            providers: Mutex::new(providers),
            providers_db: None,
            transcript_db: None,
            secrets: make_secret_store(),
            link_status: Mutex::new(selahcue_lan::LinkStatus::local()),
            link_next_attempt: Mutex::new(None),
        });
        (app, id)
    }

    fn sample_draft(
        title: &str,
        ai_generated: bool,
    ) -> selahcue_lan::protocol::SermonNoteDraftInput {
        selahcue_lan::protocol::SermonNoteDraftInput {
            title: title.to_string(),
            summary: None,
            sections_json: "[]".to_string(),
            scriptures_json: "[]".to_string(),
            ai_generated,
            disclosure: ai_generated.then(|| "AI-generated; verify before use.".to_string()),
            provider: "Local (offline)".to_string(),
            model: None,
        }
    }

    /// C-007 (first half): no accepted draft exists yet — `persist_generated_draft` takes the
    /// ORIGINAL, unchanged immediate-save path, exactly like pre-86akgqdx8 behaviour.
    #[tokio::test]
    async fn persist_with_no_existing_draft_saves_immediately_not_staged() {
        let (app, id) = state_with_transcript(true);
        let state = app.state::<AppState>();
        let outcome = persist_generated_draft(&state, id, sample_draft("First draft", true)).await;
        assert_eq!(outcome.transcript_id, Some(id));
        assert!(
            !outcome.pending_confirmation,
            "no draft existed yet — this must be a save, not a stage"
        );
        assert!(outcome.previous_draft.is_none());

        let saved = state
            .backend
            .load_sermon_note_draft(id)
            .await
            .expect("load_sermon_note_draft against a real store succeeds")
            .expect("saved");
        assert_eq!(saved.title, "First draft");
    }

    /// C-007 (second half): an accepted draft already exists — the fresh draft is STAGED, and
    /// the accepted draft already on record is retrievable and unchanged, exactly what makes
    /// "the prior draft is retained until confirmed" true at this call site.
    #[tokio::test]
    async fn persist_with_an_existing_draft_stages_and_leaves_it_untouched() {
        let (app, id) = state_with_transcript(true);
        let state = app.state::<AppState>();
        // Seed an accepted draft the way a true first-time generate would.
        persist_generated_draft(&state, id, sample_draft("Original notes", true)).await;

        let outcome =
            persist_generated_draft(&state, id, sample_draft("Regenerated notes", true)).await;
        assert_eq!(outcome.transcript_id, Some(id));
        assert!(
            outcome.pending_confirmation,
            "an accepted draft already existed — this must stage, not upsert"
        );
        let previous = outcome.previous_draft.expect("previous draft echoed back");
        assert_eq!(previous["title"], serde_json::json!("Original notes"));

        // The accepted draft on record is STILL the original — never touched by staging.
        let still_accepted = state
            .backend
            .load_sermon_note_draft(id)
            .await
            .expect("load_sermon_note_draft against a real store succeeds")
            .expect("accepted draft");
        assert_eq!(
            still_accepted.title, "Original notes",
            "staging a regeneration must never replace the accepted draft"
        );
    }

    /// C-009 (operator layer, reinforcing the `selahcue-app`-level test of the same shape): the
    /// host refusing to stage (here, an oversized field the repo's own bounds reject) must never
    /// leave the accepted draft touched or a pending row behind.
    #[tokio::test]
    async fn a_refused_stage_never_touches_the_accepted_draft_or_leaves_a_pending_row() {
        let (app, id) = state_with_transcript(true);
        let state = app.state::<AppState>();
        persist_generated_draft(&state, id, sample_draft("Original notes", true)).await;

        let mut oversized = sample_draft("Regenerated notes", true);
        oversized.title = "x".repeat(10_000); // past sermon_note_repo::MAX_TITLE_CHARS (300)
        let outcome = persist_generated_draft(&state, id, oversized).await;
        assert_eq!(
            outcome.transcript_id, None,
            "a refused stage must not be reported as persisted"
        );
        assert!(!outcome.pending_confirmation);

        let still_accepted = state
            .backend
            .load_sermon_note_draft(id)
            .await
            .expect("load_sermon_note_draft against a real store succeeds")
            .expect("accepted draft");
        assert_eq!(still_accepted.title, "Original notes");
        // `discard` is a harmless no-op when nothing is pending — using it here to observe
        // `pending` is `None` proves the refused stage left no partial row behind.
        let slot = state
            .backend
            .discard_sermon_note_regeneration(id)
            .await
            .expect("discard_sermon_note_regeneration against a real store succeeds")
            .expect("slot");
        assert!(
            slot.pending.is_none(),
            "the refused stage must not have left a pending row"
        );
    }

    /// C-008: the consent gate is unchanged, shared code for Generate and Regenerate alike — this
    /// proves it specifically for a transcript that ALREADY has an accepted draft (the Regenerate
    /// scenario), not just the first-time-Generate case the existing crate-level tests already
    /// cover. With consent off, `generate_sermon_notes` must refuse before ever reaching
    /// `persist_generated_draft` — the accepted draft stays exactly as it was and no pending row
    /// is created.
    #[tokio::test]
    async fn consent_off_refuses_regenerate_before_touching_the_accepted_draft() {
        let (app, id) = state_with_transcript(false);
        let state = app.state::<AppState>();
        // Seed an accepted draft directly against the store (bypassing the command, which would
        // itself refuse with consent off) so this transcript is genuinely in the "already has a
        // draft" state the Regenerate affordance targets.
        persist_generated_draft(&state, id, sample_draft("Original notes", true)).await;

        let result = generate_sermon_notes("a fresh transcript".to_string(), state.clone())
            .await
            .expect("command returns Ok(json) even on refusal");
        assert_eq!(result["ok"], serde_json::json!(false));
        assert_eq!(result["error"], serde_json::json!("consent_required"));

        let still_accepted = state
            .backend
            .load_sermon_note_draft(id)
            .await
            .expect("load_sermon_note_draft against a real store succeeds")
            .expect("accepted draft");
        assert_eq!(
            still_accepted.title, "Original notes",
            "a consent-off refusal must never reach persistence"
        );
        let slot = state
            .backend
            .discard_sermon_note_regeneration(id)
            .await
            .expect("discard_sermon_note_regeneration against a real store succeeds")
            .expect("slot");
        assert!(
            slot.pending.is_none(),
            "a consent-off refusal must never stage a pending regeneration"
        );
    }

    /// C-010 (operator layer): a degraded (local-fallback) regeneration — `ai_generated: false`,
    /// no disclosure, exactly what a local fallback produces — still goes through the SAME
    /// stage/confirm gate as an AI-generated one when an existing draft is present, and the
    /// label survives confirm unchanged (the "once AI-generated, always AI-generated" rule is
    /// `selahcue-data`'s; this proves the operator's own stage/confirm call sites carry
    /// `ai_generated: false` through faithfully rather than defaulting it).
    #[tokio::test]
    async fn a_degraded_regenerate_over_a_never_ai_generated_draft_still_requires_confirm() {
        let (app, id) = state_with_transcript(true);
        let state = app.state::<AppState>();
        // The existing accepted draft was itself never AI-generated (a human-authored draft, or
        // an earlier degraded one) — `selahcue-data`'s own positive control already proves
        // confirming a degraded regeneration over such a draft is ALLOWED.
        persist_generated_draft(&state, id, sample_draft("Human notes", false)).await;

        let outcome = persist_generated_draft(
            &state,
            id,
            sample_draft("Degraded regenerated notes", false),
        )
        .await;
        assert!(
            outcome.pending_confirmation,
            "even a degraded regenerate must be staged, not auto-applied"
        );

        let confirmed = state
            .backend
            .confirm_sermon_note_regeneration(id)
            .await
            .expect("confirm_sermon_note_regeneration against a real store succeeds")
            .expect("confirm succeeds");
        let current = confirmed.current.expect("confirmed draft");
        assert_eq!(current.title, "Degraded regenerated notes");
        assert!(
            !current.ai_generated,
            "a degraded regenerate's ai_generated:false must survive confirm unchanged"
        );
        assert!(current.disclosure.is_none());
    }

    /// The two new Tauri commands' own JSON shape, end to end through a real backend — nothing
    /// else in this suite calls them as commands (only via `Backend` directly), so this is the
    /// only place a rename/shape drift in `confirm_sermon_note_regeneration`/
    /// `discard_sermon_note_regeneration` themselves would be caught.
    #[tokio::test]
    async fn confirm_and_discard_commands_round_trip_through_a_real_backend() {
        let (app, id) = state_with_transcript(true);
        let state = app.state::<AppState>();
        persist_generated_draft(&state, id, sample_draft("Original notes", true)).await;
        persist_generated_draft(&state, id, sample_draft("Regenerated notes", true)).await;

        // Discard first: the accepted draft must come back unchanged.
        let discarded = discard_sermon_note_regeneration(id, state.clone())
            .await
            .expect("discard_sermon_note_regeneration command succeeds");
        assert_eq!(discarded["ok"], serde_json::json!(true));
        assert_eq!(
            discarded["draft"]["title"],
            serde_json::json!("Original notes")
        );

        // Stage again, then confirm: the accepted draft must now be the regenerated one.
        persist_generated_draft(&state, id, sample_draft("Regenerated notes 2", true)).await;
        let confirmed = confirm_sermon_note_regeneration(id, state.clone())
            .await
            .expect("confirm_sermon_note_regeneration command succeeds");
        assert_eq!(confirmed["ok"], serde_json::json!(true));
        assert_eq!(
            confirmed["draft"]["title"],
            serde_json::json!("Regenerated notes 2")
        );

        // Confirming again with nothing pending is refused, not fabricated.
        let refused = confirm_sermon_note_regeneration(id, state.clone())
            .await
            .expect("confirm_sermon_note_regeneration command succeeds");
        assert_eq!(refused["ok"], serde_json::json!(false));
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
    // FIRST, before any thread exists: export the developer AI provider keys from the repo-root
    // `.env`. A no-op — and no file read at all — in a build without the `dev-keys` feature.
    dev_env::load();
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
            // Transcripts (86akcffvt): a best-effort READ-ONLY connection to the store
            // `selahcue-desktop` actually writes to (see `open_transcript_db`'s doc comment for
            // why this is a DIFFERENT path from `providers_db` above). Failing to open it is not
            // fatal to boot — the Transcripts page degrades to an honest "unavailable" state.
            let transcript_db = open_transcript_db();
            // `build_backend` only ever produces `Remote` when `connect_remote` actually
            // established the link, so a fresh `LinkStatus::connected()` here is honest at boot
            // — never a claim ahead of the evidence.
            let link_status = if backend.is_remote() {
                selahcue_lan::LinkStatus::connected()
            } else {
                selahcue_lan::LinkStatus::local()
            };
            app.manage(AppState {
                backend,
                deck: Mutex::new(ws),
                library: Mutex::new(library),
                providers: Mutex::new(providers),
                providers_db: providers_db.map(Mutex::new),
                transcript_db: transcript_db.map(Mutex::new),
                secrets: make_secret_store(),
                link_status: Mutex::new(link_status),
                link_next_attempt: Mutex::new(None),
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
            link_status,
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
            publish_plan,
            new_plan,
            template_plan,
            duplicate_plan,
            import_plan,
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
            generate_sermon_notes,
            load_sermon_note_draft,
            update_sermon_note_draft,
            confirm_sermon_note_regeneration,
            discard_sermon_note_regeneration,
            transcript_list,
            transcript_get,
            transcript_generate_notes,
            note_generation_limits
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
