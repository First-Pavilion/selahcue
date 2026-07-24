//! SelahCue operator shell (Tauri desktop UI).
//!
//! The webview renders the service plan and control buttons; each button calls a
//! `#[tauri::command]` that drives the shared [`OperatorShell`] and returns the fresh
//! [`OperatorView`] so the UI re-renders from one round trip. The operator logic is
//! the same surface unit-tested in `selahcue-app` (`tests/test_operator.rs`); this
//! crate is the GUI veneer over it (ADR-0003).
//!
//! Run on a desktop with the Tauri toolchain:  `cargo run` (from this crate).

#![forbid(unsafe_code)]
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use selahcue_app::{LiveController, OperatorShell, OperatorView};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_present::Theme;
use std::sync::{Arc, Mutex};
use tauri::State;

/// Tauri-managed application state: the shared operator shell.
struct AppState {
    shell: OperatorShell,
}

#[tauri::command]
fn view(state: State<'_, AppState>) -> OperatorView {
    state.shell.view()
}

#[tauri::command]
fn next(state: State<'_, AppState>) -> OperatorView {
    state.shell.next()
}

#[tauri::command]
fn previous(state: State<'_, AppState>) -> OperatorView {
    state.shell.previous()
}

#[tauri::command]
fn go_live(state: State<'_, AppState>) -> OperatorView {
    state.shell.go_live()
}

#[tauri::command]
fn clear(state: State<'_, AppState>) -> OperatorView {
    state.shell.clear()
}

#[tauri::command]
fn blackout(on: bool, state: State<'_, AppState>) -> OperatorView {
    state.shell.blackout(on)
}

#[tauri::command]
fn select(item_id: u64, state: State<'_, AppState>) -> OperatorView {
    state.shell.select(item_id)
}

/// A demo service plan so the shell is useful to launch stand-alone. In the full app
/// the plan is loaded from the persistence layer.
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
        .manage(AppState {
            shell: demo_shell(),
        })
        .invoke_handler(tauri::generate_handler![
            view, next, previous, go_live, clear, blackout, select
        ])
        .run(tauri::generate_context!())
        .expect("run SelahCue operator shell");
}
