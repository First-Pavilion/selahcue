//! The SelahCue-hosted cloud client — a [`NoteProvider`] over an injected
//! [`HttpTransport`] (R3; FR-131/134).
//!
//! Configuration is a base URL + an account/session [`Token`]. Missing either →
//! [`NoteError::NotConfigured`] (the honest state while the live service does not
//! exist), and **no** request is issued. HTTP error statuses map to stable
//! [`NoteError`]s (402 and a terminal-exhaustion 429 -> quota; any other 429 and 5xx ->
//! transport; the rest -> malformed), and **no part of a response body is ever put in an
//! error** (86akbzxjg); a transport
//! failure maps to [`NoteError::Transport`], which the orchestrator turns into the
//! local fallback (FR-135). The bearer token is attached only to the request and is
//! never logged.

use crate::contract::{
    GenerateNotesRequest, GenerateNotesResponse, QuotaDto, NOTES_GENERATE_PATH, QUOTA_PATH,
};
use crate::provider_error::ErrorFields;
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

    /// Map a non-2xx HTTP status (and the allowlisted fields of its body) to a [`NoteError`].
    ///
    /// **No part of `body` is ever copied into the result.** A provider's error body is
    /// untrusted free text that has been observed to carry a clear-text fragment of the API
    /// key, and a hosted proxy that forwards an upstream body would forward it too. Only
    /// [`ErrorFields`] is read: a reason code from a closed list and a correlation handle of a
    /// fixed shape. Everything else in the message is this function's own wording.
    ///
    /// **429 is overloaded and is decided on the payload, not the status.** A terminal
    /// exhaustion code means the account is out of credit: [`NoteError::QuotaExceeded`], which
    /// [`crate::generate_sermon_notes`] propagates. Any other 429 is a rate-limit blip:
    /// [`NoteError::Transport`], so the operator still gets the degraded local draft. 402 is
    /// always terminal. The discrimination itself lives in [`ErrorFields`], shared with the
    /// OpenAI mapper.
    fn status_error(status: u16, body: &str) -> NoteError {
        if status == 402 {
            return NoteError::QuotaExceeded;
        }
        let fields = ErrorFields::parse(body);
        match status {
            429 if fields.is_terminal_exhaustion() => NoteError::QuotaExceeded,
            429 => NoteError::Transport(format!(
                "the service is rate limiting requests (status 429), try again shortly{}",
                fields.describe()
            )),
            // 5xx is a server-side blip -> treat as transport so the orchestrator falls
            // back locally rather than surfacing a dead end.
            500..=599 => {
                NoteError::Transport(format!("server status {status}{}", fields.describe()))
            }
            401 | 403 => NoteError::Malformed(format!(
                "the service rejected the account credentials (status {status}), \
                 reconnect the SelahCue account{}",
                fields.describe()
            )),
            other => {
                NoteError::Malformed(format!("unexpected status {other}{}", fields.describe()))
            }
        }
    }

    /// A body that arrived with a success status but does not fit the contract.
    ///
    /// serde_json's text for a type mismatch quotes the offending value
    /// (`invalid type: string "sk-...", expected u32`), so `e.to_string()` here would copy
    /// response text into the error exactly as the non-2xx path used to. Only the category and
    /// position, which are numbers and a fixed word, are kept.
    fn malformed_response(e: &serde_json::Error) -> NoteError {
        use serde_json::error::Category;
        let kind = match e.classify() {
            Category::Io => "read",
            Category::Syntax => "syntax",
            Category::Data => "type or shape",
            Category::Eof => "truncated",
        };
        NoteError::Malformed(format!(
            "the response did not match the SelahCue cloud contract ({kind} problem at line {} column {})",
            e.line(),
            e.column()
        ))
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
            serde_json::from_str(&resp.body).map_err(|e| Self::malformed_response(&e))?;
        Ok(dto.to_core())
    }
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
            serde_json::from_str(&resp.body).map_err(|e| Self::malformed_response(&e))?;
        Ok((parsed.draft.to_core(), Some(parsed.quota.to_core())))
    }
}
