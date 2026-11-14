//! Isolated state for native Account Setup.
pub(crate) mod state;

use std::{path::PathBuf, sync::Mutex};

use serde::Serialize;

use state::{AccountMetadata, AccountMetadataStore, AccountStorageError, CredentialPresence};

/// The only account state sent to the WebView. Fields that need verified
/// entitlement or runtime evidence are absent until the worker observes it.
#[derive(Clone, Debug, Serialize)]
pub(crate) struct AccountView {
    pub(crate) revision: u64,
    pub(crate) setup_state: SetupState,
    pub(crate) device_state: DeviceState,
    pub(crate) entitlement_state: EntitlementState,
    pub(crate) operation_state: OperationState,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) display_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) platform: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) app_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) plan_label: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) instances_used: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) instance_limit: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) license_expires_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) last_checked_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) error_code: Option<AccountErrorCode>,
    pub(crate) pending_cleanup: bool,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum SetupState {
    Unknown,
    Needed,
    Skipped,
    Completed,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum DeviceState {
    Unknown,
    Unregistered,
    CredentialMissing,
    CredentialPresent,
    CustodyUnavailable,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum EntitlementState {
    Unavailable,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum OperationState {
    Idle,
    RetryPending,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub(crate) enum AccountErrorCode {
    IdentityRecoveryRequired,
    CredentialPresenceUnavailable,
    MetadataUnavailable,
    MetadataChanged,
    InvalidIdentity,
    PendingActivationPath,
}

impl From<AccountStorageError> for AccountErrorCode {
    fn from(error: AccountStorageError) -> Self {
        match error {
            AccountStorageError::IdentityRecoveryRequired => Self::IdentityRecoveryRequired,
            AccountStorageError::CredentialPresenceUnavailable => {
                Self::CredentialPresenceUnavailable
            }
            AccountStorageError::Changed => Self::MetadataChanged,
            AccountStorageError::InvalidIdentity => Self::InvalidIdentity,
            AccountStorageError::PendingActivationPath => Self::PendingActivationPath,
            AccountStorageError::Io(_)
            | AccountStorageError::UnsafePath
            | AccountStorageError::Oversize
            | AccountStorageError::Malformed
            | AccountStorageError::EntropyUnavailable => Self::MetadataUnavailable,
        }
    }
}

impl AccountView {
    pub(crate) fn local(
        revision: u64,
        metadata: Option<&AccountMetadata>,
        presence: CredentialPresence,
    ) -> Self {
        let mut view = Self {
            revision,
            setup_state: SetupState::Unknown,
            device_state: DeviceState::Unknown,
            entitlement_state: EntitlementState::Unavailable,
            operation_state: OperationState::Idle,
            display_name: None,
            platform: None,
            app_version: None,
            plan_label: None,
            instances_used: None,
            instance_limit: None,
            license_expires_at: None,
            last_checked_at: None,
            error_code: None,
            pending_cleanup: false,
        };
        let Some(metadata) = metadata else {
            return view;
        };

        let registered = metadata.activated_public_id.is_some();
        view.setup_state = match (registered, presence, metadata.skipped_setup) {
            (true, CredentialPresence::Present, _) => SetupState::Completed,
            (_, _, true) => SetupState::Skipped,
            _ => SetupState::Needed,
        };
        view.device_state = match (registered, presence) {
            (true, CredentialPresence::Missing) => DeviceState::CredentialMissing,
            (false, CredentialPresence::Missing) => DeviceState::Unregistered,
            (_, CredentialPresence::Unavailable) => DeviceState::CustodyUnavailable,
            (_, CredentialPresence::Present) => DeviceState::CredentialPresent,
        };
        if metadata.pending_activation().is_some() {
            view.operation_state = OperationState::RetryPending;
        }

        let (display_name, platform, version) = metadata.display_fields();
        view.display_name = nonempty(display_name);
        view.platform = nonempty(platform);
        view.app_version = nonempty(version);
        view
    }
}

fn nonempty(value: &str) -> Option<String> {
    if value.is_empty() {
        None
    } else {
        Some(value.to_owned())
    }
}

/// Tauri state independent of the live presentation state. Construction
/// stores the configured location and an empty projection without I/O.
pub(crate) struct AccountState {
    pub(crate) metadata_store: Option<AccountMetadataStore>,
    pub(crate) view: Mutex<AccountView>,
}

impl AccountState {
    pub(crate) fn new(directory: Option<PathBuf>) -> Self {
        Self {
            metadata_store: directory.map(AccountMetadataStore::new),
            view: Mutex::new(AccountView::local(0, None, CredentialPresence::Unavailable)),
        }
    }
}

#[cfg(test)]
mod tests;
