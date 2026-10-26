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
    ActivationRequest, ActivationResponse, ApiErrorEnvelope, ErrorCode, LicenseDto,
    SessionActivationRequest, SessionRequest, SessionResponse, TokenMetaDto, ACTIVATIONS_PATH,
    ACTIVATIONS_WITH_SESSION_PATH, SESSIONS_PATH,
};
use crate::custody::DeviceCredentials;
use crate::device::{DeviceIdentity, IdempotencyKey};
use crate::error::ActivationFailure;
use selahcue_cloud::{HttpResponse, HttpTransport, SecretError, SecretStore, Token};
use serde::de::DeserializeOwned;

/// The most response body this client will parse.
///
/// Every success body here is a few hundred bytes and every coded error is under 200, so
/// 64 KiB is two orders of magnitude of headroom. The transport already refuses to *read*
/// more than `MAX_TRANSPORT_RESPONSE_BYTES` (4 MiB) off the socket; this is the second,
/// tighter bound for what is handed to a parser, and it holds for any transport, including
/// a test double. A body over it is refused unparsed and is never quoted.
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

/// A client for the Platform API's licensing surfaces.
pub struct LicensingClient<T: HttpTransport> {
    transport: T,
    base_url: String,
}

impl<T: HttpTransport> LicensingClient<T> {
    /// A client against `base_url`, e.g. `https://api.selahcue.example`.
    ///
    /// **The scheme is not validated here, and the wiring must require `https://`.** Every
    /// call this client makes carries a credential — the password on sign-in, the enrollment
    /// key on activation, the session token as a bearer — so an `http://` base URL puts all
    /// three on the wire in clear. The check belongs at the configuration boundary, where a
    /// bad value can be refused with something an operator can act on, rather than here
    /// where it would be a panic or a silent rewrite deep in a call stack.
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

    // -----------------------------------------------------------------------
    // Transport plumbing
    // -----------------------------------------------------------------------

    /// The one place a request leaves this crate: a JSON `POST`, with the session token as
    /// the only credential header there can be. This crate sets no cookie, CSRF, `Origin` or
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
            return Err(Self::error(&response, classify));
        }
        serde_json::from_str(&response.body).map_err(|e| Self::malformed(&e))
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
