use std::{path::PathBuf, sync::Arc};

use selahcue_cloud::{secret::KeyringSecretStore, transport::ReqwestTransport};
use selahcue_licensing::{
    client::MAX_RESPONSE_BODY_BYTES, LicensingClient, Token, TrustedKeys, KEYRING_SERVICE,
};
use tauri::{AppHandle, Emitter, Manager, Runtime, State};

use super::{
    controller::{system_time, AccountController, Command, Worker, API_ORIGIN},
    links::{AccountUiError, AccountWebDestination},
    state::CredentialPresence,
    AccountErrorCode, AccountView, DeviceState,
};

type NativeWorker = Worker<ReqwestTransport, KeyringSecretStore>;

const STATE_CHANGED: &str = "account-state-changed";

pub(crate) fn initialize<R: Runtime>(app: &AppHandle<R>, directory: Option<PathBuf>) {
    // Construct reqwest and perform all OS-store or disk reads off the UI thread.
    // State is registered synchronously so commands can return during initialization.
    let account = app.manage(ManagedAccount::default());
    if !account {
        return;
    }
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let worker = ReqwestTransport::new_with_response_limit(MAX_RESPONSE_BODY_BYTES)
            .and_then(|transport| LicensingClient::new(transport, API_ORIGIN))
            .ok()
            .map(|client| {
                Worker::new(AccountController::new(
                    directory,
                    client,
                    KeyringSecretStore::new(KEYRING_SERVICE),
                    TrustedKeys::bundled(),
                    system_time,
                ))
            });
        let startup = worker.as_ref().and_then(|worker| worker.admit().ok());
        let state = app.state::<ManagedAccount>();
        let _ = state.inner.set(worker);
        let view = if let Some(startup) = startup {
            startup.run(Command::Startup)
        } else {
            state.view()
        };
        let can_refresh = matches!(view.device_state, DeviceState::CredentialPresent)
            && matches!(view.setup_state, super::SetupState::Completed);
        let _ = app.emit_to("main", STATE_CHANGED, view);
        // Initial focus can arrive before the worker is registered. A configured
        // install has already restored and verified its disk snapshot at this point.
        if can_refresh {
            foreground(&app);
        }
    });
}

#[derive(Default)]
pub(crate) struct ManagedAccount {
    inner: std::sync::OnceLock<Option<Arc<NativeWorker>>>,
}

impl ManagedAccount {
    fn worker(&self) -> Option<&Arc<NativeWorker>> {
        self.inner.get()?.as_ref()
    }

    fn view(&self) -> AccountView {
        if let Some(worker) = self.worker() {
            return worker.view();
        }
        let mut view = AccountView::local(0, None, CredentialPresence::Unavailable);
        if self.inner.get().is_some() {
            view.revision = 1;
            view.error_code = Some(AccountErrorCode::WorkerUnavailable);
        } else {
            view.operation_state = super::OperationState::Busy;
        }
        view
    }
}

pub(crate) fn foreground<R: Runtime>(app: &AppHandle<R>) {
    let Some(state) = app.try_state::<ManagedAccount>() else {
        return;
    };
    let Some(worker) = state.worker() else { return };
    let Ok(work) = worker.admit() else { return };
    let app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let view = work.run(Command::Refresh { explicit: false });
        let _ = app.emit_to("main", STATE_CHANGED, view);
    });
}

async fn submit(state: &ManagedAccount, command: Command) -> AccountView {
    let Some(worker) = state.worker() else {
        return state.view();
    };
    let work = match worker.admit() {
        Ok(work) => work,
        Err(view) => return *view,
    };
    match tauri::async_runtime::spawn_blocking(move || work.run(command)).await {
        Ok(view) => view,
        Err(_) => state.view(),
    }
}

#[tauri::command]
pub(crate) async fn account_open_web(
    destination: AccountWebDestination,
) -> Result<(), AccountUiError> {
    tauri::async_runtime::spawn_blocking(move || {
        destination.open_with(|url| tauri_plugin_opener::open_url(url, None::<&str>))
    })
    .await
    .map_err(|_| AccountUiError::BrowserOpenFailed)?
}

#[tauri::command]
pub(crate) async fn account_view(state: State<'_, ManagedAccount>) -> Result<AccountView, ()> {
    Ok(state.view())
}

#[tauri::command]
pub(crate) async fn account_skip_setup(
    state: State<'_, ManagedAccount>,
) -> Result<AccountView, AccountErrorCode> {
    let worker = state
        .worker()
        .cloned()
        .ok_or(AccountErrorCode::WorkerUnavailable)?;
    tauri::async_runtime::spawn_blocking(move || worker.skip_setup())
        .await
        .map_err(|_| AccountErrorCode::WorkerUnavailable)?
}

#[tauri::command]
pub(crate) async fn account_sign_in_and_activate(
    state: State<'_, ManagedAccount>,
    email: String,
    password: String,
    display_name: String,
) -> Result<AccountView, ()> {
    Ok(submit(
        &state,
        Command::SignIn {
            email,
            password: Token::new(password),
            display_name,
        },
    )
    .await)
}

#[tauri::command]
pub(crate) async fn account_activate_with_enrollment(
    state: State<'_, ManagedAccount>,
    enrollment_key: String,
    display_name: String,
) -> Result<AccountView, ()> {
    Ok(submit(
        &state,
        Command::Enroll {
            key: Token::new(enrollment_key),
            display_name,
        },
    )
    .await)
}

#[tauri::command]
pub(crate) async fn account_retry_activation(
    state: State<'_, ManagedAccount>,
) -> Result<AccountView, ()> {
    Ok(submit(&state, Command::RetryActivation).await)
}

#[tauri::command]
pub(crate) async fn account_refresh(
    state: State<'_, ManagedAccount>,
    explicit: Option<bool>,
) -> Result<AccountView, ()> {
    Ok(submit(
        &state,
        Command::Refresh {
            explicit: explicit.unwrap_or(true),
        },
    )
    .await)
}

#[tauri::command]
pub(crate) async fn account_retry_session_cleanup(
    state: State<'_, ManagedAccount>,
) -> Result<AccountView, ()> {
    Ok(submit(&state, Command::RetryCleanup).await)
}
