//! Account operations own their I/O independently of the presentation state.
use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, MutexGuard,
    },
    time::{Duration, Instant},
};

use selahcue_licensing::{
    Activation, ActivationFailure, DeviceCredentials, DeviceIdentity, EntitlementCache,
    HttpTransport, LicenseRefresh, LicensingClient, PersistOutcome, SecretStore, Token,
    TrustedKeys, VerifiedEntitlement,
};
use time::{format_description::well_known::Rfc3339, OffsetDateTime};

use super::{
    state::{
        AccountMetadata, AccountMetadataStore, ActivationPath, CredentialPresence,
        PendingActivation,
    },
    AccountErrorCode as Code, AccountView, DeviceState, EntitlementState, LicenseState,
    OperationState, SetupState,
};

pub(super) const API_ORIGIN: &str = "https://api.selahcueapp.com";
// Future lower boundaries alone get this allowance for minor workstation clock
// drift. Expiry is exclusive with no extension, and this status never gates outputs.
const LICENSE_CLOCK_SKEW: Duration = Duration::from_secs(120);
// Keep at most one show-once answer, scoped to a single saved activation.
const CREDENTIAL_SAVE_WINDOW: Duration = Duration::from_secs(600);

pub(super) type Time = (i64, u32);

pub(super) fn system_time() -> Time {
    let now = OffsetDateTime::now_utc();
    (now.unix_timestamp(), now.nanosecond())
}

fn rfc3339(at: Time) -> Option<String> {
    OffsetDateTime::from_unix_timestamp(at.0)
        .ok()?
        .replace_nanosecond(at.1)
        .ok()?
        .format(&Rfc3339)
        .ok()
}

pub(super) enum Command {
    Startup,
    Skip,
    SignIn {
        email: String,
        password: Token,
        display_name: String,
    },
    Enroll {
        key: Token,
        display_name: String,
    },
    RetryActivation,
    Refresh {
        explicit: bool,
    },
    RetryCleanup,
}

/// One admit slot and one immutable projection. Holding a secret-store prompt
/// open or waiting on a remote deadline never blocks reads or queues mutations.
pub(super) struct Worker<T: HttpTransport, S: SecretStore> {
    controller: Mutex<AccountController<T, S>>,
    working: AtomicBool,
    projection: Mutex<AccountView>,
}

impl<T: HttpTransport, S: SecretStore> Worker<T, S> {
    pub(super) fn new(controller: AccountController<T, S>) -> Arc<Self> {
        Arc::new(Self {
            controller: Mutex::new(controller),
            working: AtomicBool::new(false),
            projection: Mutex::new(AccountView::local(0, None, CredentialPresence::Unavailable)),
        })
    }

    pub(super) fn view(&self) -> AccountView {
        self.projection().clone()
    }

    fn projection(&self) -> MutexGuard<'_, AccountView> {
        self.projection
            .lock()
            .unwrap_or_else(|lock| lock.into_inner())
    }

    pub(super) fn admit(self: &Arc<Self>) -> Result<Work<T, S>, Box<AccountView>> {
        let mut view = self.projection();
        if self.working.swap(true, Ordering::AcqRel) {
            return Err(Box::new(view.clone()));
        }
        view.revision = view.revision.saturating_add(1);
        view.operation_state = OperationState::Busy;
        Ok(Work {
            worker: Arc::clone(self),
            finished: false,
        })
    }
}

pub(super) struct Work<T: HttpTransport, S: SecretStore> {
    worker: Arc<Worker<T, S>>,
    finished: bool,
}

impl<T: HttpTransport, S: SecretStore> Work<T, S> {
    pub(super) fn run(mut self, command: Command) -> AccountView {
        let mut result = match self.worker.controller.lock() {
            Ok(mut account) => account.execute(command),
            Err(_) => {
                let mut view = self.worker.view();
                view.error_code = Some(Code::WorkerUnavailable);
                view.operation_state = OperationState::Idle;
                view
            }
        };
        {
            let mut view = self.worker.projection();
            result.revision = view.revision.saturating_add(1);
            *view = result.clone();
            self.worker.working.store(false, Ordering::Release);
        }
        self.finished = true;
        result
    }
}

impl<T: HttpTransport, S: SecretStore> Drop for Work<T, S> {
    fn drop(&mut self) {
        if !self.finished {
            let mut view = self.worker.projection();
            view.revision = view.revision.saturating_add(1);
            view.operation_state = OperationState::Idle;
            view.error_code = Some(Code::WorkerUnavailable);
            self.worker.working.store(false, Ordering::Release);
        }
    }
}

pub(super) struct AccountController<T: HttpTransport, S: SecretStore> {
    storage: Option<AccountMetadataStore>,
    cache: Option<EntitlementCache>,
    client: LicensingClient<T>,
    credentials: DeviceCredentials<S>,
    trust: TrustedKeys,
    clock: fn() -> Time,
    retained: Option<RetainedActivation>,
    cleanup_ack: Option<Token>,
    cleanup_error: Option<Code>,
    device_rejected: bool,
    checked_at: Option<Time>,
    online_license: Option<LicenseState>,
}

struct RetainedActivation {
    answer: Activation,
    operation: PendingActivation,
    received: Instant,
    session: Option<Token>,
}

impl<T: HttpTransport, S: SecretStore> AccountController<T, S> {
    pub(super) fn new(
        directory: Option<PathBuf>,
        client: LicensingClient<T>,
        secrets: S,
        trust: TrustedKeys,
        clock: fn() -> Time,
    ) -> Self {
        Self {
            storage: directory.clone().map(AccountMetadataStore::new),
            cache: directory.map(EntitlementCache::new),
            client,
            credentials: DeviceCredentials::new(secrets),
            trust,
            clock,
            retained: None,
            cleanup_ack: None,
            cleanup_error: None,
            device_rejected: false,
            checked_at: None,
            online_license: None,
        }
    }

    #[cfg(test)]
    pub(super) fn client(&self) -> &LicensingClient<T> {
        &self.client
    }

    pub(super) fn execute(&mut self, command: Command) -> AccountView {
        if self
            .retained
            .as_ref()
            .is_some_and(|held| held.received.elapsed() >= CREDENTIAL_SAVE_WINDOW)
        {
            self.retained = None;
        }
        let (mut metadata, presence) = match self.load_metadata() {
            Ok(local) => local,
            Err(error) => {
                let mut view = AccountView::local(0, None, CredentialPresence::Unavailable);
                view.error_code = Some(error);
                return view;
            }
        };
        // Verify the on-disk snapshot before attempting to replace it. Project from
        // the disk again after edits, including failed or ambiguous disk writes.
        let cached = self.read_cache(&metadata);
        let startup = matches!(command, Command::Startup);
        let result = match command {
            Command::Startup => Ok(()),
            Command::Skip => self.skip(&mut metadata),
            Command::SignIn {
                email,
                password,
                display_name,
            } => self.sign_in(&mut metadata, &email, password, &display_name),
            Command::Enroll { key, display_name } => self.enroll(&mut metadata, key, &display_name),
            Command::RetryActivation => self.retry_activation(&mut metadata),
            Command::Refresh { explicit } => {
                let result = self.refresh(&metadata);
                if !explicit
                    && matches!(
                        result,
                        Err(Code::NetworkUnavailable | Code::ServiceUnavailable)
                    )
                    && cached
                        .as_ref()
                        .ok()
                        .and_then(Option::as_ref)
                        .is_some_and(|manifest| {
                            matches!(
                                entitlement_state(manifest, (self.clock)()),
                                EntitlementState::Current
                            )
                        })
                {
                    Ok(())
                } else {
                    result
                }
            }
            Command::RetryCleanup => self.retry_cleanup(&mut metadata),
        };
        if startup {
            self.project(&metadata, presence, cached, result)
        } else {
            let presence = CredentialPresence::from_check(self.credentials.is_activated());
            self.project(&metadata, presence, self.read_cache(&metadata), result)
        }
    }

    fn load_metadata(&self) -> Result<(AccountMetadata, CredentialPresence), Code> {
        let presence = CredentialPresence::from_check(self.credentials.is_activated());
        let metadata = self
            .storage
            .as_ref()
            .ok_or(Code::MetadataUnavailable)?
            .load_or_create(presence)?;
        Ok((metadata, presence))
    }

    fn save(&self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        *metadata = self
            .storage
            .as_ref()
            .ok_or(Code::MetadataUnavailable)?
            .save(metadata)?;
        Ok(())
    }

    fn skip(&self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        let mut candidate = metadata.clone();
        candidate.skipped_setup = true;
        self.save(&mut candidate)?;
        *metadata = candidate;
        Ok(())
    }

    fn prepare(
        &self,
        metadata: &mut AccountMetadata,
        path: ActivationPath,
        name: &str,
    ) -> Result<PendingActivation, Code> {
        let mut candidate = metadata.clone();
        let pending = candidate
            .begin_activation(path, std::env::consts::OS, env!("CARGO_PKG_VERSION"), name)?
            .clone();
        if candidate != *metadata {
            self.save(&mut candidate)?;
            *metadata = candidate;
        }
        Ok(pending)
    }

    fn complete_pending(&self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        let mut candidate = metadata.clone();
        candidate.clear_pending_activation();
        self.save(&mut candidate)?;
        *metadata = candidate;
        Ok(())
    }

    fn sign_in(
        &mut self,
        metadata: &mut AccountMetadata,
        email: &str,
        password: Token,
        name: &str,
    ) -> Result<(), Code> {
        if self.retained.is_some() {
            drop(password);
            return self.finish_retained(metadata);
        }
        if let Some(pending) = metadata.pending_activation() {
            if pending.path() != ActivationPath::AccountSession {
                return Err(Code::PendingActivationPath);
            }
        } else {
            DeviceIdentity::new(
                metadata.fingerprint(),
                std::env::consts::OS,
                env!("CARGO_PKG_VERSION"),
                name,
            )
            .map_err(|_| Code::InvalidIdentity)?;
        }
        let signed_in = self.client.sign_in(email, &password);
        drop(password);
        let session = signed_in.map_err(Code::from)?.token;
        let pending = match self.prepare(metadata, ActivationPath::AccountSession, name) {
            Ok(pending) => pending,
            Err(error) => {
                let _ = self.revoke_and_clear(&session);
                return Err(error);
            }
        };
        if self.credentials.store_account_session(&session).is_err() {
            // No activation can leave without saved retry authority. Preserve the
            // local failure alongside the independent unused-session cleanup result.
            let _ = self.revoke_and_clear(&session);
            return Err(Code::AccountSessionSaveFailed);
        }
        self.activate_session(metadata, &pending, &session)
    }

    fn enroll(
        &mut self,
        metadata: &mut AccountMetadata,
        key: Token,
        name: &str,
    ) -> Result<(), Code> {
        if self.retained.is_some() {
            drop(key);
            return self.finish_retained(metadata);
        }
        let pending = self.prepare(metadata, ActivationPath::EnrollmentKey, name)?;
        let result = self.client.activate_with_enrollment_key(
            &key,
            &pending.device_identity()?,
            &pending.retry_key()?,
        );
        drop(key);
        self.complete_response(metadata, &pending, result, None)
    }

    fn activate_session(
        &mut self,
        metadata: &mut AccountMetadata,
        pending: &PendingActivation,
        session: &Token,
    ) -> Result<(), Code> {
        let result = self.client.begin_session_activation(
            session,
            &pending.device_identity()?,
            &pending.retry_key()?,
        );
        self.complete_response(metadata, pending, result, Some(session))
    }

    fn complete_response(
        &mut self,
        metadata: &mut AccountMetadata,
        pending: &PendingActivation,
        response: Result<Activation, ActivationFailure>,
        session: Option<&Token>,
    ) -> Result<(), Code> {
        let answer = match response {
            Ok(answer) => answer,
            Err(error) => {
                // A definite policy or input refusal did not consume the operation.
                // A missing response or a malformed success leaves the outcome unknown.
                if matches!(
                    error,
                    ActivationFailure::NoActiveLicense
                        | ActivationFailure::UnknownKey
                        | ActivationFailure::PolicyDenied
                        | ActivationFailure::PermissionDenied
                        | ActivationFailure::ValidationFailed
                ) {
                    self.complete_pending(metadata)?;
                    if pending.path() == ActivationPath::AccountSession {
                        if let Some(session) = session {
                            let _ = self.revoke_and_clear(session);
                        }
                    }
                }
                return Err(error.into());
            }
        };
        if metadata
            .activated_public_id
            .as_ref()
            .is_some_and(|id| id != &answer.device_public_id)
            || answer.platform != pending.device_identity()?.platform
        {
            return Err(Code::DeviceBindingMismatch);
        }
        self.retained = Some(RetainedActivation {
            answer,
            operation: pending.clone(),
            received: Instant::now(),
            session: session.cloned(),
        });
        self.finish_retained(metadata)
    }

    fn finish_retained(&mut self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        let held = self
            .retained
            .as_ref()
            .ok_or(Code::ActivationCompletionPending)?;
        if metadata.pending_activation() != Some(&held.operation)
            || metadata
                .activated_public_id
                .as_ref()
                .is_some_and(|id| id != &held.answer.device_public_id)
        {
            return Err(Code::MetadataChanged);
        }
        if metadata.activated_public_id.is_none() || metadata.skipped_setup {
            let mut registered = metadata.clone();
            registered.activated_public_id = Some(held.answer.device_public_id.clone());
            registered.skipped_setup = false;
            self.save(&mut registered)?;
            *metadata = registered;
        }

        let session = held.session.clone();
        let persistence = held.answer.persist(&self.credentials);
        let replay_status = match persistence {
            Ok(PersistOutcome::Stored) => None,
            Ok(PersistOutcome::KeptExisting) => {
                // A pre-existing token could have been revoked by a remint whose
                // response was lost. Prove bearer custody for this exact device.
                let id = &held.answer.device_public_id;
                let token = self.device_token()?.ok_or(Code::DeviceRecoveryRequired)?;
                match self.client.refresh_license(&token, id) {
                    Ok(status) => Some(status),
                    Err(ActivationFailure::Unauthenticated) => {
                        self.device_rejected = true;
                        self.retained = None;
                        self.complete_pending(metadata)?;
                        if let Some(session) = &session {
                            let _ = self.revoke_and_clear(session);
                        }
                        return Err(Code::DeviceRecoveryRequired);
                    }
                    Err(error) => return Err(error.into()),
                }
            }
            Ok(PersistOutcome::MissingLocally) => {
                self.retained = None;
                self.complete_pending(metadata)?;
                if let Some(session) = &session {
                    let _ = self.revoke_and_clear(session);
                }
                return Err(Code::DeviceRecoveryRequired);
            }
            Err(_) => return Err(Code::CredentialSaveFailed),
        };
        self.complete_pending(metadata)?;
        self.retained = None;
        self.device_rejected = false;
        self.online_license = None;
        self.checked_at = None;

        if let Some(session) = &session {
            // Cleanup is independent of an already durable device. Its result has
            // its own field in the view, while refresh continues.
            let _ = self.revoke_and_clear(session);
        }
        if let Some(status) = replay_status {
            self.refresh_manifest(
                metadata,
                &self.device_token()?.ok_or(Code::DeviceRecoveryRequired)?,
                status,
            )
        } else {
            self.refresh(metadata)
        }
    }

    fn retry_activation(&mut self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        if self.retained.is_some() {
            return self.finish_retained(metadata);
        }
        let pending = match metadata.pending_activation().cloned() {
            Some(pending) => pending,
            None if self.device_rejected => {
                // An explicitly retried reauthorization may reuse existing account
                // custody. Normal successful activation removes that session.
                let session = self
                    .account_session()?
                    .ok_or(Code::ReauthenticationRequired)?;
                if self.cleanup_ack.is_some() {
                    return Err(Code::ReauthenticationRequired);
                }
                let display_name = metadata.display_fields().0.to_owned();
                let pending =
                    self.prepare(metadata, ActivationPath::AccountSession, &display_name)?;
                return self.activate_session(metadata, &pending, &session);
            }
            None => return self.refresh(metadata),
        };
        if pending.path() == ActivationPath::EnrollmentKey {
            return Err(Code::EnrollmentKeyRequired);
        }
        let session = self
            .account_session()?
            .ok_or(Code::ReauthenticationRequired)?;
        self.activate_session(metadata, &pending, &session)
    }

    fn account_session(&self) -> Result<Option<Token>, Code> {
        self.credentials
            .account_session()
            .map_err(|_| Code::CredentialPresenceUnavailable)
    }

    fn device_token(&self) -> Result<Option<Token>, Code> {
        self.credentials
            .device_token()
            .map(|token| token.filter(|token| !token.is_blank() && !token.has_control_characters()))
            .map_err(|_| Code::CredentialPresenceUnavailable)
    }

    fn retry_cleanup(&mut self, metadata: &mut AccountMetadata) -> Result<(), Code> {
        if self.retained.is_some() || metadata.pending_activation().is_some() {
            return Err(Code::ActivationCompletionPending);
        }
        if self.cleanup_ack.is_some() {
            return self.clear_acknowledged_cleanup();
        }
        let Some(session) = self.account_session().inspect_err(|_| {
            self.cleanup_error = Some(Code::SessionCleanupLocalFailure);
        })?
        else {
            self.cleanup_error = None;
            return Ok(());
        };
        self.revoke_and_clear(&session)
    }

    fn revoke_and_clear(&mut self, session: &Token) -> Result<(), Code> {
        if self.client.revoke_session(session).is_err() {
            self.cleanup_error = Some(Code::SessionCleanupUnconfirmed);
            return Err(Code::SessionCleanupUnconfirmed);
        }
        self.cleanup_ack = Some(session.clone());
        self.clear_acknowledged_cleanup()
    }

    fn clear_acknowledged_cleanup(&mut self) -> Result<(), Code> {
        if let Some(acknowledged) = self.cleanup_ack.as_ref() {
            match self
                .credentials
                .clear_account_session_if_matches(acknowledged)
            {
                Ok(_) => {
                    self.cleanup_ack = None;
                    self.cleanup_error = None;
                }
                Err(_) => {
                    self.cleanup_error = Some(Code::SessionCleanupLocalFailure);
                    return Err(Code::SessionCleanupLocalFailure);
                }
            }
        }
        Ok(())
    }

    fn refresh(&mut self, metadata: &AccountMetadata) -> Result<(), Code> {
        let Some(id) = metadata.activated_public_id.as_deref() else {
            return Ok(());
        };
        if self.retained.is_some() || metadata.pending_activation().is_some() {
            return Err(Code::ActivationCompletionPending);
        }
        let Some(token) = self.device_token()? else {
            return Err(Code::DeviceRecoveryRequired);
        };
        let status = self
            .client
            .refresh_license(&token, id)
            .map_err(|error| self.refresh_failure(error))?;
        self.refresh_manifest(metadata, &token, status)
    }

    fn refresh_failure(&mut self, error: ActivationFailure) -> Code {
        self.online_license = None;
        if matches!(error, ActivationFailure::Unauthenticated) {
            self.device_rejected = true;
        }
        error.into()
    }

    fn refresh_manifest(
        &mut self,
        metadata: &AccountMetadata,
        token: &Token,
        status: LicenseRefresh,
    ) -> Result<(), Code> {
        self.device_rejected = false;
        self.checked_at = Some((self.clock)());
        self.online_license = Some(
            if status.license_valid_now && status.device_status == "ACTIVE" {
                LicenseState::Active
            } else if status.license_status == "EXPIRED" {
                LicenseState::RenewalNeeded
            } else {
                LicenseState::Inactive
            },
        );
        if !status.license_valid_now || status.device_status != "ACTIVE" {
            return Err(Code::LicenseInactive);
        }
        let body = self
            .client
            .fetch_entitlement(token)
            .map_err(|error| self.refresh_failure(error))?;
        self.cache
            .as_ref()
            .ok_or(Code::ManifestUnavailable)?
            .replace(
                &body,
                &self.trust,
                &status.device_public_id,
                metadata.fingerprint(),
            )
            .map_err(|_| Code::ManifestUnavailable)?;
        Ok(())
    }

    fn read_cache(&self, metadata: &AccountMetadata) -> Result<Option<VerifiedEntitlement>, Code> {
        let Some(id) = metadata.activated_public_id.as_deref() else {
            return Ok(None);
        };
        self.cache
            .as_ref()
            .ok_or(Code::ManifestUnavailable)?
            .load(&self.trust, id, metadata.fingerprint())
            .map_err(|_| Code::ManifestUnavailable)
    }

    fn project(
        &self,
        metadata: &AccountMetadata,
        presence: CredentialPresence,
        cache: Result<Option<VerifiedEntitlement>, Code>,
        result: Result<(), Code>,
    ) -> AccountView {
        let mut view = AccountView::local(0, Some(metadata), presence);
        let pending = metadata.pending_activation().is_some();
        let account = self.account_session();
        view.pending_cleanup = self.cleanup_ack.is_some()
            || self.cleanup_error.is_some()
            || (!pending && account.as_ref().ok().is_some_and(Option::is_some));
        view.cleanup_error_code = self.cleanup_error;
        view.error_code = result.err().or_else(|| cache.as_ref().err().copied());
        if view.error_code.is_none() && matches!(presence, CredentialPresence::Unavailable) {
            view.error_code = Some(Code::CredentialPresenceUnavailable);
        }
        if self.retained.is_some() || (pending && matches!(presence, CredentialPresence::Present)) {
            view.device_state = if self
                .retained
                .as_ref()
                .is_some_and(|held| held.answer.token.is_some())
            {
                DeviceState::CredentialNotSaved
            } else {
                DeviceState::CredentialUnconfirmed
            };
            view.setup_state = if metadata.skipped_setup {
                SetupState::Skipped
            } else {
                SetupState::Needed
            };
            view.operation_state = OperationState::RetryPending;
        } else if self.device_rejected {
            view.device_state = DeviceState::ReauthenticationNeeded;
        }
        view.last_checked_at = self.checked_at.and_then(rfc3339);
        view.license_state = self.online_license;

        if let Ok(Some(manifest)) = cache {
            let now = (self.clock)();
            let facts = manifest.facts();
            view.entitlement_state = entitlement_state(&manifest, now);
            view.manifest_expires_at = rfc3339(facts.expires_at());
            view.license_expires_at = rfc3339(facts.license_expires_at());
            let display = manifest.display();
            view.plan_label = display.plan_display_label.clone();
            view.instances_used = display.instances_used;
            view.instance_limit = display.instances_limit;
            // An expired manifest alone cannot establish licence expiry. Use the
            // independent signed licence boundary only for local renewal guidance.
            if !matches!(view.entitlement_state, EntitlementState::FutureOrClockSkew) {
                view.license_state = match view.license_state {
                    Some(LicenseState::Inactive | LicenseState::RenewalNeeded) => {
                        view.license_state
                    }
                    None if now >= facts.license_expires_at() => Some(LicenseState::RenewalNeeded),
                    None if matches!(view.entitlement_state, EntitlementState::Current) => {
                        Some(LicenseState::Active)
                    }
                    _ => view.license_state,
                };
            }
        }
        view
    }
}

pub(super) fn temporal_state(
    issued: Time,
    not_before: Time,
    expiry: Time,
    now: Time,
) -> EntitlementState {
    let Some(latest) = now.0.checked_add(LICENSE_CLOCK_SKEW.as_secs() as i64) else {
        return EntitlementState::FutureOrClockSkew;
    };
    if issued.max(not_before) > (latest, now.1) {
        EntitlementState::FutureOrClockSkew
    } else if now >= expiry {
        EntitlementState::Expired
    } else {
        EntitlementState::Current
    }
}

fn entitlement_state(manifest: &VerifiedEntitlement, now: Time) -> EntitlementState {
    let facts = manifest.facts();
    temporal_state(
        facts.issued_at(),
        manifest.not_before(),
        facts.expires_at(),
        now,
    )
}

impl From<ActivationFailure> for Code {
    fn from(error: ActivationFailure) -> Self {
        match error {
            ActivationFailure::InvalidCredentials => Self::InvalidCredentials,
            ActivationFailure::AccountNotActive => Self::AccountNotActive,
            ActivationFailure::NoActiveLicense => Self::NoActiveLicense,
            ActivationFailure::UnknownKey => Self::UnknownKey,
            ActivationFailure::PolicyDenied => Self::PolicyDenied,
            ActivationFailure::PermissionDenied => Self::PermissionDenied,
            ActivationFailure::ValidationFailed | ActivationFailure::SignInInvalidInput => {
                Self::InvalidInput
            }
            ActivationFailure::RateLimited | ActivationFailure::SignInRateLimited => {
                Self::RateLimited
            }
            ActivationFailure::Unauthenticated => Self::ReauthenticationRequired,
            ActivationFailure::Unreachable(_) => Self::NetworkUnavailable,
            ActivationFailure::Server(_)
            | ActivationFailure::Malformed(_)
            | ActivationFailure::Coded(_)
            | ActivationFailure::UnexpectedStatus(_) => Self::ServiceUnavailable,
        }
    }
}
