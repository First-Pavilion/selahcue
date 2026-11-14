//! The licensing client: sign-in, and both shipped activation paths.
//!
//! Everything here runs over the injected [`HttpTransport`], so the tests drive the whole
//! surface — including every failure mode — with no network, and the shell swaps in the
//! real `ReqwestTransport` without a code change.
//!
//! # Both paths, permanently
//!
//! - [`LicensingClient::sign_in`] then [`LicensingClient::activate_with_session`] is the
//!   **primary** path (DEC-005/007, DEC-011 pt 3): `POST /v1/sessions`, then
//!   `POST /v1/activations:with-session` with the session as a bearer. These are the
//!   server's native-client routes (86ak5t1gw, ADR-0029). They need no cookie and no CSRF
//!   token, and this client sends neither: the transport seam can carry a bearer and
//!   nothing else, and `tests/test_client.rs` pins that nothing here names a cookie, a CSRF
//!   header or the browser's `/graphql/account` route.
//!   A valid activation is followed by one `/v1/sessions:revoke` attempt; its
//!   separate cleanup result never masks the activated device.
//! - [`LicensingClient::activate_with_enrollment_key`] is the **delegation** path, and is
//!   not legacy. It exists for the case DEC-011 records: a volunteer setting up machines
//!   in the sound booth, who would otherwise need the administrator's account password on
//!   every device. An enrolment key is the credential that does exactly one thing.
//!
//! Removing either path was considered and rejected by the owner. Both stay.
//!
//! # What a response is allowed to become
//!
//! A response body is untrusted text: the API's, but equally a proxy's, a WAF's or Django's
//! CSRF page. It is read by the transport under a hard byte cap, refused here above
//! [`MAX_RESPONSE_BODY_BYTES`] without being parsed, and never copied into a failure — see
//! [`crate::error`]. A body that is not the API's coded envelope is classified by its
//! HTTP status alone.
//!
//! # Nothing here gates anything
//!
//! There is no `check`, `enforce` or `is_allowed` in this crate. It obtains credentials
//! and reports what happened. Enforcement is 86ak5mn1t and is ladder-shaped by design
//! (FR-520). A failure of any kind returns an [`ActivationFailure`], every variant of
//! which permits presentation.

use crate::contract::{
    ActivationRequest, ActivationResponse, ApiErrorEnvelope, BoundActivationError,
    BoundActivationRequest, BoundActivationResponse, BoundOperationState, EntitlementEnvelope,
    ErrorCode, LicenseDto, SessionActivationRequest, SessionRequest, SessionResponse,
    SessionRevokeResponse, TokenMetaDto, ACTIVATIONS_PATH, ACTIVATIONS_WITH_SESSION_PATH,
    ENTITLEMENT_MANIFEST_PATH, SESSIONS_PATH, SESSION_REVOKE_PATH,
};
use crate::custody::DeviceCredentials;
use crate::device::{DeviceIdentity, IdempotencyKey};
use crate::error::ActivationFailure;
use selahcue_cloud::transport::{require_https_base_url, require_loopback_test_url};
use selahcue_cloud::{
    HttpResponse, HttpTransport, SecretError, SecretStore, Token, TransportError,
};
use serde::{de::DeserializeOwned, Deserialize};

/// The most response body this client will parse.
///
/// Every success body here is a few hundred bytes and every coded error is under 200, so
/// 64 KiB is two orders of magnitude of headroom. The transport already refuses to *read*
/// more than its configured limit off the socket. Configure the native account transport
/// with this cap. The parsing bound here also applies to any injected transport. A body
/// over it is refused unparsed and is never quoted.
pub const MAX_RESPONSE_BODY_BYTES: usize = 64 * 1024;

/// Which path produced an activation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivationPath {
    /// Account sign-in (`POST /v1/activations:with-session`) — the primary path.
    AccountSession,
    /// Enrollment key (`POST /v1/activations`) — the delegation path.
    EnrollmentKey,
}

/// A signed-in account session.
#[derive(Debug, Clone)]
pub struct AccountSession {
    /// The session token. Redacted in `Debug`; hand it straight to
    /// [`LicensingClient::activate_with_session`] or to custody.
    pub token: Token,
    pub expires_at: String,
    pub role: String,
    pub org_id: String,
}

/// What the server said about this device's token.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TokenDisposition {
    /// A token was issued — store it, replacing anything cached.
    Store(Token),
    /// The device already holds a live token and the server will not re-show it
    /// (show-once). Keep what is cached.
    KeepExisting,
}

/// The result of persisting an activation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PersistOutcome {
    /// A new or replacement token was written to the secret store.
    Stored,
    /// The server replayed and this install already holds its token. Nothing to do.
    KeptExisting,
    /// **The awkward one.** The server replayed — so it will not re-show the token — but
    /// this install has no token cached. That happens if the keychain entry was deleted
    /// or the machine was re-imaged while the server-side device row stayed live.
    ///
    /// It cannot be resolved by retrying: show-once means the server will keep replaying.
    /// Recovery is to deactivate the device server-side (freeing its slot) and activate
    /// again. Reported rather than hidden, because a silent "success" that leaves the
    /// install with no credential is worse than a state the operator can act on — and
    /// because, per CON-P1, this still stops nothing: the app presents regardless.
    MissingLocally,
}

/// The bootstrap account session's cleanup, independent of device activation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SessionCleanup {
    /// The server positively acknowledged revoking the presented session.
    Revoked,
    /// One cleanup attempt was not confirmed. Retain custody for an explicit retry;
    /// never erase a device credential or turn the valid activation into a failure.
    RetryRequired(ActivationFailure),
}

/// Device persistence and local account cleanup have separate outcomes.
#[derive(Debug, Clone)]
pub struct PersistedActivation {
    pub activation: Activation,
    pub device_persistence: Result<PersistOutcome, SecretError>,
    /// False when remote cleanup was unconfirmed or another session is stored.
    /// A keychain error is reported separately from the successfully activated device.
    pub account_session_cleared: Result<bool, SecretError>,
}

/// A successful activation. Both paths answer with the same body, so every field is
/// present whichever way the device was activated.
#[derive(Debug, Clone)]
pub struct Activation {
    /// Which path was used.
    pub path: ActivationPath,
    /// The show-once token, when one was issued.
    pub token: Option<Token>,
    /// True on a first activation.
    pub created: bool,
    /// True when a replacement token was minted for an existing device because its own was
    /// expired or revoked. A `true` here means the previously cached token is now revoked.
    pub reminted: bool,
    pub device_public_id: String,
    pub platform: String,
    /// Non-secret token metadata.
    pub token_meta: TokenMetaDto,
    /// The backing licence.
    pub license: LicenseDto,
    /// Account activations attempt one immediate native cleanup; enrollment activation is None.
    pub session_cleanup: Option<SessionCleanup>,
}

impl Activation {
    /// What to do with the device token.
    pub fn disposition(&self) -> TokenDisposition {
        match &self.token {
            Some(token) => TokenDisposition::Store(token.clone()),
            None => TokenDisposition::KeepExisting,
        }
    }

    /// The licensing status this activation establishes.
    ///
    /// Both paths report the server-side instance id, so this is the one field that is
    /// meaningful whichever way the device was activated. Persisting it for display across
    /// restarts is the console's business (86ajy7anx) — it is not a secret, and it is
    /// deliberately not put in the secret store alongside the token.
    pub fn status(&self) -> crate::LicensingStatus {
        crate::LicensingStatus::Activated {
            device_public_id: self.device_public_id.clone(),
        }
    }

    /// Persist the outcome into the OS secret store, doing the right thing for each of
    /// the three server outcomes.
    ///
    /// Provided so a caller cannot get the re-mint case wrong: when `reminted` is true the
    /// previously cached token has already been revoked server-side and will 401 on its
    /// next use, so overwriting is mandatory rather than an optimisation.
    pub fn persist<S: SecretStore>(
        &self,
        credentials: &DeviceCredentials<S>,
    ) -> Result<PersistOutcome, SecretError> {
        match self.disposition() {
            TokenDisposition::Store(token) => {
                credentials.store_device_token(&token)?;
                Ok(PersistOutcome::Stored)
            }
            TokenDisposition::KeepExisting => {
                if credentials.is_activated()? {
                    Ok(PersistOutcome::KeptExisting)
                } else {
                    Ok(PersistOutcome::MissingLocally)
                }
            }
        }
    }
}

/// Online status for the bound device as last reported by the Platform API.
/// Offline state and feature grants come from a verified signed entitlement.
#[derive(Clone, PartialEq, Eq)]
pub struct LicenseRefresh {
    pub device_public_id: String,
    pub device_status: String,
    pub license_status: String,
    pub license_starts_at: String,
    pub license_expires_at: String,
    pub license_valid_now: bool,
    pub instances_used: u32,
    pub instances_limit: u32,
    pub token_expires_at: String,
}

impl core::fmt::Debug for LicenseRefresh {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("LicenseRefresh").finish_non_exhaustive()
    }
}

#[derive(Deserialize)]
struct LicenseRefreshResponse {
    device: RefreshDevice,
    license: RefreshLicense,
    instances: RefreshInstances,
    token: RefreshToken,
}

#[derive(Deserialize)]
struct RefreshDevice {
    device_public_id: String,
    status: String,
}

#[derive(Deserialize)]
struct RefreshLicense {
    status: String,
    starts_at: String,
    expires_at: String,
    valid_now: bool,
}

#[derive(Deserialize)]
struct RefreshInstances {
    used: u32,
    limit: u32,
}

#[derive(Deserialize)]
struct RefreshToken {
    expires_at: String,
}

/// A client for the Platform API's licensing surfaces.
pub struct LicensingClient<T: HttpTransport> {
    transport: T,
    base_url: String,
}

impl<T: HttpTransport> LicensingClient<T> {
    /// A client against an HTTPS base, e.g. `https://api.selahcue.example`.
    ///
    /// Invalid/non-HTTPS configuration is refused before any call can carry a password,
    /// enrollment key or bearer. The error contains no URL, query, userinfo or parser text.
    pub fn new(transport: T, base_url: impl Into<String>) -> Result<Self, TransportError> {
        let base_url = base_url.into();
        require_https_base_url(&base_url)?;
        Ok(LicensingClient {
            transport,
            base_url,
        })
    }

    /// Explicit local HTTP fixture constructor, never the normal application constructor.
    /// Accepts HTTPS or HTTP with a parsed loopback host only. A real HTTP fixture must also
    /// explicitly use `ReqwestTransport::new_for_loopback_tests`.
    pub fn new_for_loopback_tests(
        transport: T,
        base_url: impl Into<String>,
    ) -> Result<Self, TransportError> {
        let base_url = base_url.into();
        require_loopback_test_url(&base_url)?;
        Ok(LicensingClient {
            transport,
            base_url,
        })
    }

    /// The transport, for tests that assert what left the device.
    pub fn transport(&self) -> &T {
        &self.transport
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url.trim_end_matches('/'), path)
    }

    // -----------------------------------------------------------------------
    // Primary path: account sign-in, then session-authenticated activation
    // -----------------------------------------------------------------------

    /// Sign in with email and password, returning an account session.
    ///
    /// `POST /v1/sessions`. The password is used once, here, and is never stored: only the
    /// returned session token is persisted, and only in the OS secret store.
    ///
    /// A refusal is classified by [`ActivationFailure::from_sign_in_code`], not by
    /// `from_code`: a wrong password is [`ActivationFailure::InvalidCredentials`], not "the
    /// session is not valid".
    pub fn sign_in(
        &self,
        email: &str,
        password: &Token,
    ) -> Result<AccountSession, ActivationFailure> {
        let request = SessionRequest {
            email: email.to_string(),
            password: password.expose().to_string(),
        };
        let body = Self::encode(&request)?;
        let response = self.post(SESSIONS_PATH, &body, None)?;
        let parsed: SessionResponse = Self::decode(response, ActivationFailure::from_sign_in_code)?;
        if Self::unusable_bearer(&parsed.session_token) {
            // The server never issues one. Accepting it would store a blank (or header-
            // splitting) credential and send it as the bearer on the next call, which fails as
            // an unexplained 401. Nothing about the value is repeated.
            return Err(ActivationFailure::Malformed(
                "the response carried an unusable session token".into(),
            ));
        }

        Ok(AccountSession {
            token: parsed.session_token,
            expires_at: parsed.expires_at,
            role: parsed.role,
            org_id: parsed.org_id,
        })
    }

    /// Activate this device against a signed-in account session — the **primary**
    /// activation path.
    ///
    /// `POST /v1/activations:with-session` with the session as the bearer. The caller's org
    /// is resolved server-side from the session, so no key and no org id are sent. The
    /// server requires the session's role to be ADMIN (a MEMBER is
    /// [`ActivationFailure::PermissionDenied`]).
    pub fn activate_with_session(
        &self,
        session: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
    ) -> Result<Activation, ActivationFailure> {
        let mut activation = self.begin_session_activation(session, identity, idempotency_key)?;
        self.cleanup_session(session, &mut activation);
        Ok(activation)
    }

    /// Request a validated activation and leave session cleanup to the caller.
    ///
    /// An operator with durable install metadata should save the public device ID,
    /// persist the show-once token, and then revoke the session. Use the same frozen
    /// request and authorization on an ambiguous failure.
    pub fn begin_session_activation(
        &self,
        session: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
    ) -> Result<Activation, ActivationFailure> {
        if Self::unusable_bearer(session) {
            // Nothing sensible can be sent: the server would answer 401 to a blank bearer, and
            // a control character cannot be put in a header at all. Say so without a request.
            return Err(ActivationFailure::Unauthenticated);
        }
        let request = SessionActivationRequest {
            idempotency_key: idempotency_key.as_str().to_string(),
            device_fingerprint: identity.fingerprint.clone(),
            platform: identity.platform.clone(),
            app_version: identity.app_version.clone(),
            display_name: identity.display_name.clone(),
        };
        let body = Self::encode(&request)?;
        let response = self.post(ACTIVATIONS_WITH_SESSION_PATH, &body, Some(session))?;
        let parsed: ActivationResponse = Self::decode(response, |code| {
            ActivationFailure::from_code(code, ActivationPath::AccountSession)
        })?;

        Self::activation(ActivationPath::AccountSession, parsed)
    }

    fn cleanup_session(&self, session: &Token, activation: &mut Activation) {
        activation.session_cleanup = Some(match self.revoke_session(session) {
            Ok(()) => SessionCleanup::Revoked,
            Err(failure) => SessionCleanup::RetryRequired(failure),
        });
    }

    /// End this account session without cookies or CSRF. One request, no implicit retries.
    /// This is also the explicit cancellation/retry operation; it never touches device custody.
    pub fn revoke_session(&self, session: &Token) -> Result<(), ActivationFailure> {
        if Self::unusable_bearer(session) {
            return Err(ActivationFailure::Unauthenticated);
        }
        let response = self.post(SESSION_REVOKE_PATH, "{}", Some(session))?;
        let parsed: SessionRevokeResponse = Self::decode(response, |code| match code {
            // NOT_FOUND here does not mean the device's license has lapsed.
            ErrorCode::NotFound => ActivationFailure::Coded(ErrorCode::NotFound),
            other => ActivationFailure::from_code(other, ActivationPath::AccountSession),
        })?;
        if !parsed.revoked {
            return Err(ActivationFailure::Malformed(
                "session cleanup was not acknowledged".into(),
            ));
        }
        Ok(())
    }

    /// Complete the existing activation path and persist its device credential, while
    /// clearing only the matching account entry after confirmed remote cleanup.
    ///
    /// The caller owns/serializes this credential lifecycle. Neither cleanup nor keychain
    /// failure masks a valid activation: separate outcomes preserve the device token and
    /// allow explicit recovery. An unsuccessful/ambiguous activation retains its session
    /// for retrying the same idempotency key; no cleanup request is sent in that case.
    pub fn activate_and_persist_with_session<S: SecretStore>(
        &self,
        session: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
        credentials: &DeviceCredentials<S>,
    ) -> Result<PersistedActivation, ActivationFailure> {
        let mut activation = self.begin_session_activation(session, identity, idempotency_key)?;
        // Preserve the show-once device token before waiting on a second remote operation.
        let device_persistence = activation.persist(credentials);
        self.cleanup_session(session, &mut activation);
        let account_session_cleared = if activation.session_cleanup == Some(SessionCleanup::Revoked)
        {
            credentials.clear_account_session_if_matches(session)
        } else {
            Ok(false)
        };
        Ok(PersistedActivation {
            activation,
            device_persistence,
            account_session_cleared,
        })
    }

    // -----------------------------------------------------------------------
    // Delegation path: enrollment key
    // -----------------------------------------------------------------------

    /// Activate this device with an org enrollment key — the **delegation** path.
    ///
    /// Retained permanently (DEC-011 pt 3). The key travels in the request body; this
    /// endpoint takes no `Authorization` header, because the presented key *is* the
    /// credential and the device is its own actor.
    pub fn activate_with_enrollment_key(
        &self,
        enrollment_key: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
    ) -> Result<Activation, ActivationFailure> {
        let request = ActivationRequest {
            idempotency_key: idempotency_key.as_str().to_string(),
            license_key: enrollment_key.expose().to_string(),
            device_fingerprint: identity.fingerprint.clone(),
            platform: identity.platform.clone(),
            app_version: identity.app_version.clone(),
            display_name: identity.display_name.clone(),
        };
        let body = Self::encode(&request)?;
        let response = self.post(ACTIVATIONS_PATH, &body, None)?;
        let parsed: ActivationResponse = Self::decode(response, |code| {
            ActivationFailure::from_code(code, ActivationPath::EnrollmentKey)
        })?;

        Self::activation(ActivationPath::EnrollmentKey, parsed)
    }

    /// Send the frozen native operation using its dedicated path. These paths
    /// intentionally never fall back to the legacy allocating endpoints.
    pub fn activate_bound(
        &self,
        path: ActivationPath,
        credential: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
        expected_device_public_id: Option<&str>,
    ) -> Result<Activation, ActivationFailure> {
        let (route, bearer, key) = match path {
            ActivationPath::EnrollmentKey => {
                ("/v1/activations:bound", None, Some(credential.expose()))
            }
            ActivationPath::AccountSession => {
                if Self::unusable_bearer(credential) {
                    return Err(ActivationFailure::Unauthenticated);
                }
                ("/v1/activations:bound-with-session", Some(credential), None)
            }
        };
        let request = BoundActivationRequest {
            operation_version: 1,
            mode: if expected_device_public_id.is_some() {
                "recover"
            } else {
                "initial"
            },
            idempotency_key: idempotency_key.as_str(),
            expected_device_public_id,
            device_fingerprint: &identity.fingerprint,
            platform: &identity.platform,
            app_version: &identity.app_version,
            display_name: &identity.display_name,
            license_key: key,
        };
        let body = Self::encode(&request)?;
        let response = self.post(route, &body, bearer)?;
        let status = response.status;
        if status == 405 {
            return Err(ActivationFailure::BoundActivationUnsupported);
        }
        if !(200..300).contains(&status) {
            if status == 429 || status >= 500 {
                return Err(Self::status_failure(status, &|code| {
                    ActivationFailure::from_code(code, path)
                }));
            }
            let parsed: BoundActivationError = (response.body.len() <= MAX_RESPONSE_BODY_BYTES)
                .then(|| serde_json::from_str(&response.body).ok())
                .flatten()
                .filter(|envelope: &BoundActivationError| envelope.operation_version == 1)
                .ok_or(ActivationFailure::BoundActivationUnsupported)?;
            let code = ErrorCode::parse(&parsed.error.code);
            if matches!(code, ErrorCode::Unknown(_)) {
                return Err(ActivationFailure::BoundActivationUnsupported);
            }
            if code == ErrorCode::ActivationOperationCompleted {
                if let Some(proof) = parsed.completed_activation {
                    if status != 409
                        || proof.idempotency_key != request.idempotency_key
                        || proof.platform != identity.platform
                        || !Self::valid_bound_device_id(&proof.device_public_id)
                        || expected_device_public_id.is_some_and(|id| id != proof.device_public_id)
                    {
                        return Err(ActivationFailure::ActivationOperationConflict);
                    }
                    return Err(ActivationFailure::ActivationOperationCompleted {
                        device_public_id: Some(proof.device_public_id),
                    });
                }
            }
            return Err(ActivationFailure::from_code(code, path));
        }
        let parsed: BoundActivationResponse =
            Self::decode(response, |code| ActivationFailure::from_code(code, path))
                .map_err(|_| ActivationFailure::BoundActivationUnsupported)?;
        if parsed.operation_version != 1 {
            return Err(ActivationFailure::BoundActivationUnsupported);
        }
        if parsed.idempotency_key != request.idempotency_key
            || !Self::valid_bound_device_id(&parsed.activation.device.device_public_id)
            || parsed.activation.device.status != "ACTIVE"
            || (parsed.operation_state == BoundOperationState::Replay
                && (parsed.activation.activation_token.is_some()
                    || parsed.activation.created
                    || parsed.activation.reminted))
            || parsed.activation.device.platform != identity.platform
            || expected_device_public_id
                .is_some_and(|id| parsed.activation.device.device_public_id != id)
        {
            return Err(ActivationFailure::ActivationOperationConflict);
        }
        Self::activation(path, parsed.activation)
    }

    fn valid_bound_device_id(value: &str) -> bool {
        value.strip_prefix("dev_").is_some_and(|id| {
            id.len() == 32
                && id
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
        })
    }

    /// Fetch an unverified manifest envelope for later verification against trusted keys
    /// and this install's identity. Keeps the response bytes for the verifier and cache.
    pub fn fetch_entitlement(&self, device_token: &Token) -> Result<Vec<u8>, ActivationFailure> {
        let bearer = Self::device_bearer(device_token)?;
        let response = self
            .transport
            .get(&self.url(ENTITLEMENT_MANIFEST_PATH), Some(bearer))
            .map_err(|_| Self::device_transport_failure())?;
        Self::check_device_response(&response)?;
        // Check the outer wire shape. Payload decoding and signature verification belong
        // to verify_entitlement, which receives the unmodified envelope.
        serde_json::from_str::<EntitlementEnvelope>(&response.body)
            .map_err(|e| Self::malformed(&e))?;
        Ok(response.body.into_bytes())
    }

    /// Read current online licence status. A live device token can report an expired
    /// licence. The caller supplies the public ID saved at activation.
    pub fn refresh_license(
        &self,
        device_token: &Token,
        expected_device_public_id: &str,
    ) -> Result<LicenseRefresh, ActivationFailure> {
        let bearer = Self::device_bearer(device_token)?;
        let response = self
            .transport
            .post_json(&self.url("/v1/license:refresh"), "{}", Some(bearer))
            .map_err(|_| Self::device_transport_failure())?;
        Self::check_device_response(&response)?;
        let parsed: LicenseRefreshResponse =
            serde_json::from_str(&response.body).map_err(|e| Self::malformed(&e))?;
        if expected_device_public_id.is_empty()
            || parsed.device.device_public_id != expected_device_public_id
        {
            return Err(ActivationFailure::Malformed(
                "the refresh response was for a different device".into(),
            ));
        }
        let status_is_bounded = |status: &str, max_len| {
            !status.is_empty()
                && status.len() <= max_len
                && status.bytes().all(|b| b.is_ascii_uppercase() || b == b'_')
        };
        if parsed.device.device_public_id.len() > 64
            || !status_is_bounded(&parsed.device.status, 16)
            || !status_is_bounded(&parsed.license.status, 32)
            || [
                &parsed.license.starts_at,
                &parsed.license.expires_at,
                &parsed.token.expires_at,
            ]
            .iter()
            .any(|date| date.len() > 64 || chrono::DateTime::parse_from_rfc3339(date).is_err())
        {
            return Err(ActivationFailure::Malformed(
                "the refresh response carried invalid status details".into(),
            ));
        }
        Ok(LicenseRefresh {
            device_public_id: parsed.device.device_public_id,
            device_status: parsed.device.status,
            license_status: parsed.license.status,
            license_starts_at: parsed.license.starts_at,
            license_expires_at: parsed.license.expires_at,
            license_valid_now: parsed.license.valid_now,
            instances_used: parsed.instances.used,
            instances_limit: parsed.instances.limit,
            token_expires_at: parsed.token.expires_at,
        })
    }

    fn device_bearer(token: &Token) -> Result<&str, ActivationFailure> {
        if Self::unusable_bearer(token) {
            return Err(ActivationFailure::Unauthenticated);
        }
        Ok(token.expose())
    }

    fn device_transport_failure() -> ActivationFailure {
        ActivationFailure::Unreachable("the device request did not complete".into())
    }

    fn check_device_response(response: &HttpResponse) -> Result<(), ActivationFailure> {
        // A device credential rejection remains distinguishable if a proxy stripped the
        // application error envelope. A redirect never becomes a successful device read.
        match response.status {
            401 => return Err(ActivationFailure::Unauthenticated),
            300..=399 => return Err(ActivationFailure::UnexpectedStatus(response.status)),
            _ => {}
        }
        Self::check_response(response, |code| match code {
            ErrorCode::NotFound => ActivationFailure::Coded(ErrorCode::NotFound),
            ErrorCode::Unknown(_) => ActivationFailure::UnexpectedStatus(response.status),
            known => ActivationFailure::from_code(known, ActivationPath::AccountSession),
        })
    }

    // -----------------------------------------------------------------------
    // Transport plumbing
    // -----------------------------------------------------------------------

    /// Send an activation or account-session JSON `POST`. This crate sets no cookie, CSRF, `Origin` or
    /// `Referer` header, and the transport seam (`post_json(url, body, bearer)`) gives it no way
    /// to; that is the property the native routes' CSRF exemption rests on.
    ///
    /// What the production transport really puts on the wire is pinned by
    /// `selahcue-cloud/tests/test_wire.rs`. The production transport never follows a redirect
    /// (ClickUp 17tnw2b9aaz), so a 3xx comes back as a status and is classified below like any
    /// other non-2xx response (a coded error envelope in its body gives that code's failure,
    /// otherwise [`ActivationFailure::UnexpectedStatus`]): the password and the enrollment key
    /// are never replayed to another host, and `reqwest` never adds the `Referer` it sets on a
    /// followed redirect. The policy is the transport's to set, not this crate's.
    fn post(
        &self,
        path: &str,
        body: &str,
        bearer: Option<&Token>,
    ) -> Result<HttpResponse, ActivationFailure> {
        self.transport
            .post_json(&self.url(path), body, bearer.map(Token::expose))
            .map_err(|e| ActivationFailure::Unreachable(e.to_string()))
    }

    fn encode<R: serde::Serialize>(request: &R) -> Result<String, ActivationFailure> {
        // A request of plain strings cannot fail to encode; if it somehow does, the
        // serializer's message is not forwarded, since it is written against our own value.
        serde_json::to_string(request)
            .map_err(|_| ActivationFailure::Malformed("the request could not be encoded".into()))
    }

    fn activation(
        path: ActivationPath,
        response: ActivationResponse,
    ) -> Result<Activation, ActivationFailure> {
        // `Some("")` is not a replay (that is `null`): persisting it would overwrite a working
        // device token with a blank one and report `Stored`.
        if response
            .activation_token
            .as_ref()
            .is_some_and(Self::unusable_bearer)
        {
            return Err(ActivationFailure::Malformed(
                "the response carried an unusable device token".into(),
            ));
        }
        Ok(Activation {
            path,
            token: response.activation_token,
            created: response.created,
            reminted: response.reminted,
            device_public_id: response.device.device_public_id,
            platform: response.device.platform,
            token_meta: response.token,
            license: response.license,
            session_cleanup: None,
        })
    }

    /// A token that cannot serve as a bearer: blank, or holding a control character. Asked of
    /// [`Token`] itself so no new `expose()` site is needed.
    fn unusable_bearer(token: &Token) -> bool {
        token.is_blank() || token.has_control_characters()
    }

    /// Decode a response, mapping non-2xx onto coded failures with `classify`.
    ///
    /// Nothing in the body reaches the returned failure except a code that has passed
    /// [`ErrorCode::parse`]'s shape check; see the module docs.
    fn decode<D: DeserializeOwned>(
        response: HttpResponse,
        classify: impl Fn(ErrorCode) -> ActivationFailure,
    ) -> Result<D, ActivationFailure> {
        Self::check_response(&response, classify)?;
        serde_json::from_str(&response.body).map_err(|e| Self::malformed(&e))
    }

    fn check_response(
        response: &HttpResponse,
        classify: impl Fn(ErrorCode) -> ActivationFailure,
    ) -> Result<(), ActivationFailure> {
        let ok = (200..300).contains(&response.status);
        if response.body.len() > MAX_RESPONSE_BODY_BYTES {
            // Refused unparsed: no allocation proportional to the body, and no echo of it.
            return Err(if ok {
                ActivationFailure::Malformed(format!(
                    "the response was larger than the {MAX_RESPONSE_BODY_BYTES}-byte limit"
                ))
            } else {
                Self::status_failure(response.status, &classify)
            });
        }
        if !ok {
            return Err(Self::error(response, classify));
        }
        Ok(())
    }

    /// Classify a non-2xx response.
    ///
    /// The coded body is authoritative when present. It is not always present: a wrong
    /// HTTP method yields a bare Django 405 with an HTML body, and a proxy or WAF answers
    /// with its own page, so an unparseable error is classified by status rather than
    /// being reported as contract drift.
    fn error(
        response: &HttpResponse,
        classify: impl Fn(ErrorCode) -> ActivationFailure,
    ) -> ActivationFailure {
        match serde_json::from_str::<ApiErrorEnvelope>(&response.body) {
            Ok(envelope) => match classify(ErrorCode::parse(&envelope.error.code)) {
                // `INTERNAL` carries no status of its own; keep the real 5xx the server sent
                // rather than flattening 502/503/504 to 500.
                ActivationFailure::Server(_) if (500..600).contains(&response.status) => {
                    ActivationFailure::Server(response.status)
                }
                other => other,
            },
            Err(_) => Self::status_failure(response.status, &classify),
        }
    }

    /// A 5xx is the server failing; a bare 429 is rate limiting whoever said it (a proxy's page
    /// is as good a signal as the API's envelope, and "try again shortly" is true of both);
    /// anything else at a non-2xx is something in FRONT of the application answering — a proxy
    /// page, a Django middleware rejection, a wrong-method 405. None of these is contract
    /// drift, and calling them `Malformed` sent the reader hunting for a schema change that
    /// does not exist.
    fn status_failure(
        status: u16,
        classify: &impl Fn(ErrorCode) -> ActivationFailure,
    ) -> ActivationFailure {
        if status == 429 {
            classify(ErrorCode::RateLimited)
        } else if (500..600).contains(&status) {
            ActivationFailure::Server(status)
        } else {
            ActivationFailure::UnexpectedStatus(status)
        }
    }

    /// Describe a parse failure WITHOUT quoting the body.
    ///
    /// `serde_json::Error`'s own message is not safe to forward: for a type mismatch it
    /// quotes the offending value (`invalid type: string "SC-DEV-...", expected a boolean`),
    /// so a body that put a credential-shaped string in the wrong field would carry it into
    /// an error message and from there into a log. This keeps the error's category and
    /// position, plus the name of a missing field (which comes from this crate's own struct
    /// definitions, not from the body).
    fn malformed(error: &serde_json::Error) -> ActivationFailure {
        use serde_json::error::Category;
        let what = match error.classify() {
            Category::Syntax => "was not valid JSON",
            Category::Data => "did not have the shape the contract defines",
            Category::Eof => "ended early",
            Category::Io => "could not be read",
        };
        let field = missing_field(&error.to_string())
            .map(|name| format!(", missing field `{name}`"))
            .unwrap_or_default();
        ActivationFailure::Malformed(format!(
            "the response body {what} (line {}, column {}{field})",
            error.line(),
            error.column()
        ))
    }
}

/// The field name in a serde `missing field `name`` message, when it is one and the name is
/// plainly an identifier. Anything else yields `None`, so no free text from a message is
/// ever forwarded.
///
/// `pub` and hidden only so that `tests/` can drive it with messages serde would never
/// produce from this crate's own structs: with real parse errors the identifier check can
/// never fire, which would leave it untested.
#[doc(hidden)]
pub fn missing_field(message: &str) -> Option<&str> {
    let rest = message.strip_prefix("missing field `")?;
    let name = &rest[..rest.find('`')?];
    let identifier = !name.is_empty()
        && name.len() <= 40
        && name.bytes().all(|b| b.is_ascii_lowercase() || b == b'_');
    identifier.then_some(name)
}
