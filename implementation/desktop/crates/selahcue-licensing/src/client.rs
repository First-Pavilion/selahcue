//! The licensing client: sign-in, and both shipped activation paths.
//!
//! Everything here runs over the injected [`HttpTransport`], so the tests drive the whole
//! surface — including every failure mode — with no network, and the shell swaps in the
//! real `ReqwestTransport` without a code change.
//!
//! # Both paths, permanently
//!
//! - [`LicensingClient::sign_in`] then [`LicensingClient::activate_with_session`] is the
//!   **primary** path (DEC-005/007, DEC-011 pt 3). It is implemented and contract-tested,
//!   but **blocked against the deployed API by CSRF on `/graphql/account` (86ak5t1gw)** —
//!   see the crate docs. Treat it as not yet reachable in production.
//! - [`LicensingClient::activate_with_enrollment_key`] is the **delegation** path, and is
//!   not legacy. It exists for the case DEC-011 records: a volunteer setting up machines
//!   in the sound booth, who would otherwise need the administrator's account password on
//!   every device. An enrolment key is the credential that does exactly one thing.
//!
//! Removing either path was considered and rejected by the owner. Both stay.
//!
//! # Nothing here gates anything
//!
//! There is no `check`, `enforce` or `is_allowed` in this crate. It obtains credentials
//! and reports what happened. Enforcement is 86ak5mn1t and is ladder-shaped by design
//! (FR-520). A failure of any kind returns an [`ActivationFailure`], every variant of
//! which permits presentation.

use crate::contract::{
    ActivateDeviceInput, ActivateDevicePayload, ActivateWithSessionData, ActivationRequest,
    ActivationResponse, ApiErrorEnvelope, ErrorCode, GraphQlRequest, GraphQlResponse,
    InputVariables, LicenseDto, LoginData, LoginInput, LoginPayload, TokenMetaDto,
    ACCOUNT_GRAPHQL_PATH, ACTIVATE_WITH_SESSION_MUTATION, ACTIVATIONS_PATH, LOGIN_MUTATION,
};
use crate::custody::DeviceCredentials;
use crate::device::{DeviceIdentity, IdempotencyKey};
use crate::error::ActivationFailure;
use selahcue_cloud::{HttpResponse, HttpTransport, SecretError, SecretStore, Token};
use serde::de::DeserializeOwned;

/// Which path produced an activation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ActivationPath {
    /// Account sign-in (GraphQL `activateDeviceWithSession`) — the primary path.
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

/// A successful activation, normalised across the two paths.
///
/// Fields the GraphQL payload does not carry are `None` rather than defaulted — the
/// session path returns only `fullToken`, `created`, `devicePublicId` and `platform`
/// (`account_schema.py:122-128`), so inventing a `reminted: false` or an empty licence
/// block for it would be a fabricated value that later code could not tell from a real
/// one.
#[derive(Debug, Clone)]
pub struct Activation {
    /// Which path was used.
    pub path: ActivationPath,
    /// The show-once token, when one was issued.
    pub token: Option<Token>,
    /// True on a first activation.
    pub created: bool,
    /// True when a replacement token was minted for an existing device. **REST path
    /// only**; `None` on the session path, which does not report it.
    pub reminted: Option<bool>,
    pub device_public_id: String,
    pub platform: String,
    /// Non-secret token metadata. REST path only.
    pub token_meta: Option<TokenMetaDto>,
    /// The backing licence. REST path only.
    pub license: Option<LicenseDto>,
}

impl Activation {
    /// What to do with the device token.
    pub fn disposition(&self) -> TokenDisposition {
        match &self.token {
            Some(token) => TokenDisposition::Store(token.clone()),
            None => TokenDisposition::KeepExisting,
        }
    }

    /// Whether the server **told us** this activation replaced a previously-issued token.
    ///
    /// Named for what it actually answers. `reminted` is `None` for *every* session
    /// activation — the payload simply does not carry the field — and a session activation
    /// genuinely can be a re-mint, because that path delegates into the same
    /// `_activate_device_for_key`. So `false` here means "not known to be a re-mint", not
    /// "not a re-mint", and the old name `is_remint` quietly asserted the stronger claim.
    ///
    /// Nothing depends on this for correctness: [`Activation::persist`] decides from the
    /// presence of a token, which is reported on both paths. Read
    /// [`Activation::reminted`] directly when the difference between `false` and unknown
    /// matters.
    pub fn is_known_remint(&self) -> bool {
        self.reminted.unwrap_or(false)
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

/// A client for the Platform API's licensing surfaces.
pub struct LicensingClient<T: HttpTransport> {
    transport: T,
    base_url: String,
}

impl<T: HttpTransport> LicensingClient<T> {
    /// A client against `base_url`, e.g. `https://api.selahcue.example`.
    pub fn new(transport: T, base_url: impl Into<String>) -> Self {
        LicensingClient {
            transport,
            base_url: base_url.into(),
        }
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
    /// The password is used once, here, and is never stored: only the returned session
    /// token is persisted, and only in the OS secret store.
    pub fn sign_in(
        &self,
        email: &str,
        password: &Token,
    ) -> Result<AccountSession, ActivationFailure> {
        let request = GraphQlRequest {
            query: LOGIN_MUTATION,
            variables: InputVariables {
                input: LoginInput {
                    email: email.to_string(),
                    password: password.expose().to_string(),
                },
            },
        };
        let payload: LoginPayload = self
            .graphql::<_, LoginData>(&request, None, ActivationPath::AccountSession)
            .map(|data| data.login)?;

        Ok(AccountSession {
            token: payload.session_token,
            expires_at: payload.expires_at,
            role: payload.role,
            org_id: payload.org_id,
        })
    }

    /// Activate this device against a signed-in account session — the **primary**
    /// activation path.
    ///
    /// The caller's org is resolved server-side from the session, so no key and no org id
    /// are sent. The server requires the session's role to be ADMIN.
    pub fn activate_with_session(
        &self,
        session: &Token,
        identity: &DeviceIdentity,
        idempotency_key: &IdempotencyKey,
    ) -> Result<Activation, ActivationFailure> {
        let request = GraphQlRequest {
            query: ACTIVATE_WITH_SESSION_MUTATION,
            variables: InputVariables {
                input: ActivateDeviceInput {
                    idempotency_key: idempotency_key.as_str().to_string(),
                    device_fingerprint: identity.fingerprint.clone(),
                    platform: identity.platform.clone(),
                    app_version: identity.app_version.clone(),
                    display_name: identity.display_name.clone(),
                },
            },
        };

        let payload: ActivateDevicePayload = self
            .graphql::<_, ActivateWithSessionData>(
                &request,
                Some(session),
                ActivationPath::AccountSession,
            )
            .map(|data| data.activate_device_with_session)?;

        Ok(Activation {
            path: ActivationPath::AccountSession,
            token: payload.full_token,
            created: payload.created,
            // Not reported on this path — see `Activation::reminted`.
            reminted: None,
            device_public_id: payload.device_public_id,
            platform: payload.platform,
            token_meta: None,
            license: None,
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
        let body = serde_json::to_string(&request)
            .map_err(|e| ActivationFailure::Malformed(e.to_string()))?;

        let response = self
            .transport
            .post_json(&self.url(ACTIVATIONS_PATH), &body, None)
            .map_err(|e| ActivationFailure::Unreachable(e.to_string()))?;

        let parsed: ActivationResponse =
            Self::decode_rest(response, ActivationPath::EnrollmentKey)?;

        Ok(Activation {
            path: ActivationPath::EnrollmentKey,
            token: parsed.activation_token,
            created: parsed.created,
            reminted: Some(parsed.reminted),
            device_public_id: parsed.device.device_public_id,
            platform: parsed.device.platform,
            token_meta: Some(parsed.token),
            license: Some(parsed.license),
        })
    }

    // -----------------------------------------------------------------------
    // Transport plumbing
    // -----------------------------------------------------------------------

    /// Issue a GraphQL request and unwrap `data`, mapping `errors` onto coded failures.
    ///
    /// A GraphQL refusal arrives as HTTP 200 with an `errors` array, so errors are checked
    /// **before** `data` — a body carrying both must be treated as the failure it is.
    fn graphql<V: serde::Serialize, D: DeserializeOwned>(
        &self,
        request: &GraphQlRequest<V>,
        bearer: Option<&Token>,
        path: ActivationPath,
    ) -> Result<D, ActivationFailure> {
        let body = serde_json::to_string(request)
            .map_err(|e| ActivationFailure::Malformed(e.to_string()))?;

        let response = self
            .transport
            .post_json(
                &self.url(ACCOUNT_GRAPHQL_PATH),
                &body,
                bearer.map(Token::expose),
            )
            .map_err(|e| ActivationFailure::Unreachable(e.to_string()))?;

        // The body is parsed BEFORE the status is consulted, and that ordering is the whole
        // point. This surface reports a refusal in the body with HTTP 200 in the ordinary
        // case, but when the view itself rejects the request it answers a non-2xx whose
        // body is *still* the GraphQL error shape — `safe_error_payload` builds
        // `{"errors": [{"message", "extensions": {"code"}}]}`, not the REST
        // `{"error": {...}}` envelope (`graphql/views.py:52-54`). Classifying a non-2xx by
        // status first would therefore throw away a perfectly good coded error and report
        // contract drift instead.
        match serde_json::from_str::<GraphQlResponse<D>>(&response.body) {
            Ok(parsed) => {
                if let Some(errors) = parsed.errors.filter(|e| !e.is_empty()) {
                    let code = errors
                        .iter()
                        .find_map(|e| e.code())
                        .unwrap_or(ErrorCode::Unknown("GRAPHQL_ERROR".to_string()));
                    return Err(ActivationFailure::from_code(code, path));
                }
                parsed.data.ok_or_else(|| {
                    ActivationFailure::Malformed(
                        "GraphQL response carried neither data nor errors".into(),
                    )
                })
            }
            // Not a GraphQL body at all — a proxy error page, or a 405 from the wrong
            // method. Fall back to classifying by status.
            Err(e) => {
                if !(200..300).contains(&response.status) {
                    Err(Self::rest_error(&response, path))
                } else {
                    Err(ActivationFailure::Malformed(e.to_string()))
                }
            }
        }
    }

    /// Decode a REST response, mapping non-2xx onto coded failures.
    fn decode_rest<D: DeserializeOwned>(
        response: HttpResponse,
        path: ActivationPath,
    ) -> Result<D, ActivationFailure> {
        if !(200..300).contains(&response.status) {
            return Err(Self::rest_error(&response, path));
        }
        serde_json::from_str(&response.body)
            .map_err(|e| ActivationFailure::Malformed(e.to_string()))
    }

    /// Classify a non-2xx response.
    ///
    /// The coded body is authoritative when present. It is not always present: a wrong
    /// HTTP method yields a bare Django 405 with an HTML body, so an unparseable error is
    /// classified by status rather than being reported as contract drift.
    fn rest_error(response: &HttpResponse, path: ActivationPath) -> ActivationFailure {
        match serde_json::from_str::<ApiErrorEnvelope>(&response.body) {
            Ok(envelope) => {
                ActivationFailure::from_code(ErrorCode::parse(&envelope.error.code), path)
            }
            // Not a coded body. A 5xx is the server failing; anything else at a non-2xx is
            // something in FRONT of the application answering — a proxy page, a Django
            // middleware rejection, a wrong-method 405. Neither is contract drift, and
            // calling them `Malformed` sent the reader hunting for a schema change that
            // does not exist.
            Err(_) => {
                if (500..600).contains(&response.status) {
                    ActivationFailure::Server(response.status)
                } else {
                    ActivationFailure::UnexpectedStatus(response.status)
                }
            }
        }
    }
}
