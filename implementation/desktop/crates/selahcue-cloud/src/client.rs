//! The SelahCue-hosted cloud client — a [`NoteProvider`] over an injected
//! [`HttpTransport`] (R3; FR-131/134).
//!
//! Configuration is a base URL + an account/session [`Token`]. Missing either →
//! [`NoteError::NotConfigured`] (the honest state while the live service does not
//! exist), and **no** request is issued. HTTP error statuses map to stable
//! [`NoteError`]s (402/429 → quota; 5xx/other → malformed/transport); a transport
//! failure maps to [`NoteError::Transport`], which the orchestrator turns into the
//! local fallback (FR-135). The bearer token is attached only to the request and is
//! never logged.

use crate::contract::{
    GenerateNotesRequest, GenerateNotesResponse, QuotaDto, NOTES_GENERATE_PATH, QUOTA_PATH,
};
use crate::secret::Token;
use crate::transport::HttpTransport;
use crate::CloudNoteProvider;
use selahcue_core::providers::{
    ConsentState, NoteDraft, NoteError, NoteProvider, NoteRequest, Quota,
};

/// The provider label shown for honest disclosure (matches the design card).
pub const CLOUD_PROVIDER_LABEL: &str = "SelahCue AI";

/// A client for the SelahCue-hosted note-generation service.
pub struct SelahCueCloudClient<T: HttpTransport> {
    transport: T,
    /// Base URL of the SelahCue service, e.g. `https://api.selahcue.example`. `None`
    /// until the live service is configured.
    base_url: Option<String>,
    /// Account/session token. `None`/empty until the operator's account is connected.
    token: Option<Token>,
}

impl<T: HttpTransport> SelahCueCloudClient<T> {
    /// A fully-configured client.
    pub fn new(transport: T, base_url: impl Into<String>, token: Token) -> Self {
        SelahCueCloudClient {
            transport,
            base_url: Some(base_url.into()),
            token: Some(token),
        }
    }

    /// An **unconfigured** client (no base URL / token). Every `generate` returns
    /// [`NoteError::NotConfigured`] and issues no request — the honest default while
    /// the live SelahCue service does not exist.
    pub fn unconfigured(transport: T) -> Self {
        SelahCueCloudClient {
            transport,
            base_url: None,
            token: None,
        }
    }

    /// Whether a base URL and non-empty token are both present.
    pub fn is_configured(&self) -> bool {
        self.base_url.is_some() && self.token.as_ref().is_some_and(|t| !t.is_empty())
    }

    fn require_config(&self) -> Result<(&str, &str), NoteError> {
        match (self.base_url.as_deref(), self.token.as_ref()) {
            (Some(base), Some(token)) if !token.is_empty() => Ok((base, token.expose())),
            _ => Err(NoteError::NotConfigured),
        }
    }

    fn url(base: &str, path: &str) -> String {
        format!("{}{}", base.trim_end_matches('/'), path)
    }

    /// Map an HTTP status to the terminal [`NoteError`]s the UI must distinguish.
    fn status_error(status: u16, body: &str) -> NoteError {
        match status {
            402 | 429 => NoteError::QuotaExceeded,
            // 5xx is a server-side blip → treat as transport so the orchestrator falls
            // back locally rather than surfacing a dead end.
            500..=599 => NoteError::Transport(format!("server status {status}")),
            other => NoteError::Malformed(format!(
                "unexpected status {other}: {}",
                truncate(body, 200)
            )),
        }
    }

    /// Fetch the current quota (standalone probe, e.g. to render the meter on load).
    ///
    /// **Consent-gated egress** (FR-132): the quota probe sends the bearer token to the
    /// SelahCue servers, which reveals the account is online — so it is refused with
    /// [`NoteError::ConsentRequired`] (issuing NO request) unless cloud-notes consent is
    /// set, exactly like [`crate::generate_sermon_notes`]. This keeps the consent choke
    /// point covering *every* egress path, not just note generation, so a UI that renders
    /// the meter on load cannot phone home before the operator opts in.
    pub fn fetch_quota(&self, consent: &ConsentState) -> Result<Quota, NoteError> {
        if !consent.cloud_notes {
            return Err(NoteError::ConsentRequired);
        }
        let (base, token) = self.require_config()?;
        let url = Self::url(base, QUOTA_PATH);
        let resp = self
            .transport
            .get(&url, Some(token))
            .map_err(|e| NoteError::Transport(e.to_string()))?;
        if !(200..300).contains(&resp.status) {
            return Err(Self::status_error(resp.status, &resp.body));
        }
        let dto: QuotaDto =
            serde_json::from_str(&resp.body).map_err(|e| NoteError::Malformed(e.to_string()))?;
        Ok(dto.to_core())
    }
}

/// Truncate a body for an error message (never include a full/huge server response).
fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}…", &s[..end])
}

impl<T: HttpTransport> NoteProvider for SelahCueCloudClient<T> {
    fn label(&self) -> &str {
        CLOUD_PROVIDER_LABEL
    }

    fn generate(&self, req: &NoteRequest) -> Result<NoteDraft, NoteError> {
        self.generate_with_quota(req).map(|(draft, _)| draft)
    }
}

impl<T: HttpTransport> CloudNoteProvider for SelahCueCloudClient<T> {
    fn generate_with_quota(
        &self,
        req: &NoteRequest,
    ) -> Result<(NoteDraft, Option<Quota>), NoteError> {
        let (base, token) = self.require_config()?;
        let url = Self::url(base, NOTES_GENERATE_PATH);
        let wire = GenerateNotesRequest::from_core(req);
        let body = serde_json::to_string(&wire).map_err(|e| NoteError::Malformed(e.to_string()))?;

        let resp = self
            .transport
            .post_json(&url, &body, Some(token))
            .map_err(|e| NoteError::Transport(e.to_string()))?;

        if !(200..300).contains(&resp.status) {
            return Err(Self::status_error(resp.status, &resp.body));
        }

        let parsed: GenerateNotesResponse =
            serde_json::from_str(&resp.body).map_err(|e| NoteError::Malformed(e.to_string()))?;
        Ok((parsed.draft.to_core(), Some(parsed.quota.to_core())))
    }
}
