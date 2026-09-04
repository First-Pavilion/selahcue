//! What gets sent to open a stream: the consent proof, the endpoint, the wire parameters, and
//! the request specification that combines them.
//!
//! Everything here is pure. Building a request is fully decided without a socket, so the wire
//! contract is pinned by tests in the default build rather than discovered against a paid
//! third party.

use selahcue_core::providers::ProvidersConfig;

use crate::credential::{Credential, REDACTED};
use crate::error::DeepgramError;

/// Proof that the operator's persisted settings permit streaming live microphone audio to a
/// cloud speech service.
///
/// The **only** way to obtain one is [`StreamAuthorization::from_config`], and it has no
/// public fields, no `Default`, and no other constructor — so a streaming request that was
/// never authorised is not merely discouraged, it cannot be expressed.
///
/// Note what this deliberately does **not** do: it does not re-derive "Cloud mode and
/// consent". It consumes [`ProvidersConfig::may_stream_cloud_audio`], the core's single
/// choke point, so a change there changes this. A control that re-assembles a conjunction
/// from parts is asserting something about a copy of the predicate and survives mutation of
/// the real one — this repository has been bitten by exactly that (86ak643rc).
#[derive(Debug, Clone)]
pub struct StreamAuthorization(());

impl StreamAuthorization {
    /// Consent proof, or [`DeepgramError::ConsentRequired`].
    ///
    /// Requires **both** the Cloud transcription mode and the cloud-transcription opt-in,
    /// because that is what `may_stream_cloud_audio()` requires; the default configuration
    /// (on-device, no consent) can never produce one.
    pub fn from_config(config: &ProvidersConfig) -> Result<Self, DeepgramError> {
        if config.may_stream_cloud_audio() {
            Ok(StreamAuthorization(()))
        } else {
            Err(DeepgramError::ConsentRequired)
        }
    }
}

/// The audio encoding declared to Deepgram. Signed 16-bit little-endian PCM is what
/// [`crate::AudioChunk`] produces and what the on-device pipeline already resamples to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Encoding {
    /// `linear16` — signed 16-bit little-endian PCM.
    #[default]
    Linear16,
}

impl Encoding {
    pub fn as_str(self) -> &'static str {
        match self {
            Encoding::Linear16 => "linear16",
        }
    }
}

/// The Deepgram streaming endpoint.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeepgramEndpoint {
    url: String,
}

/// Deepgram's live streaming endpoint.
pub const DEEPGRAM_LISTEN_URL: &str = "wss://api.deepgram.com/v1/listen";

impl Default for DeepgramEndpoint {
    fn default() -> Self {
        DeepgramEndpoint {
            url: DEEPGRAM_LISTEN_URL.to_string(),
        }
    }
}

impl DeepgramEndpoint {
    /// A different endpoint — **the stub socket the tests run against**, or a self-hosted
    /// Deepgram deployment.
    ///
    /// A plain-text `ws://` URL is accepted here but refused at
    /// [`RequestSpec::build`] unless its host is loopback, so pointing production at a
    /// cleartext endpoint cannot leak a credential onto a network.
    pub fn custom(url: impl Into<String>) -> Self {
        DeepgramEndpoint { url: url.into() }
    }

    /// The endpoint URL, without query parameters.
    pub fn url(&self) -> &str {
        &self.url
    }

    /// Whether sending a credential to this endpoint keeps it confidential: either the
    /// transport is TLS, or the peer is this machine.
    pub fn is_confidential(&self) -> bool {
        if let Some(rest) = self.url.strip_prefix("wss://") {
            return !rest.is_empty();
        }
        match self.url.strip_prefix("ws://") {
            Some(rest) => is_loopback_authority(rest),
            None => false,
        }
    }
}

/// Whether the authority at the start of `rest` (`host[:port][/path]`) is this machine.
fn is_loopback_authority(rest: &str) -> bool {
    let authority = rest.split('/').next().unwrap_or(rest);
    // Userinfo is refused outright rather than parsed. In `ws://127.0.0.1:80@evil.com/` the
    // real host is `evil.com` — everything before the `@` is userinfo — but a scan that splits
    // on `:` first sees `127.0.0.1` and calls it loopback, sending the credential in clear text
    // to an attacker-chosen host. This client never has a reason to send userinfo, so the safe
    // reading of an authority containing `@` is "not loopback", not "parse it more carefully".
    if authority.contains('@') {
        return false;
    }
    // `[::1]:9999` — an IPv6 literal keeps its brackets, so split the port off after them.
    let host = match authority.strip_prefix('[') {
        Some(after) => match after.split_once(']') {
            Some((h, _port)) => h,
            None => return false,
        },
        None => authority.split(':').next().unwrap_or(authority),
    };
    matches!(host, "127.0.0.1" | "localhost" | "::1")
        || host.strip_prefix("127.").is_some_and(|_| {
            host.split('.').count() == 4 && host.split('.').all(|o| o.parse::<u8>().is_ok())
        })
}

/// The Deepgram streaming query parameters.
///
/// [`StreamParams::default`] is the **recorded working set** for Phase 1: the exact
/// parameters used to measure the service. Every field is public and configurable — none of
/// these is a decision this client should be making silently on a church's behalf.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StreamParams {
    /// Deepgram model. `nova-3` is the current recommended model and is verified working on
    /// this account.
    pub model: String,
    /// BCP-47 language tag.
    pub language: String,
    /// Audio encoding declared to the service; must match what [`crate::AudioChunk`] carries.
    pub encoding: Encoding,
    /// Sample rate in Hz. 16 kHz matches `selahcue-stt`'s `TARGET_SAMPLE_RATE`, so one
    /// capture pipeline feeds either engine.
    pub sample_rate_hz: u32,
    /// Channel count. Mono; a sermon is one speaker on one microphone.
    pub channels: u16,
    /// Ask for interim hypotheses as well as finals. **Required** for the provisional-versus-
    /// settled distinction the console needs (FR-103) — with this off, Deepgram sends finals
    /// only and the distinction cannot be recovered downstream.
    pub interim_results: bool,
    /// Punctuate and capitalise. On: an unpunctuated wall of text is unreadable in the panel.
    pub punctuate: bool,
    /// Deepgram's "smart formatting": punctuation **plus** rewriting of numbers, dates,
    /// currency and similar into digit form.
    ///
    /// **Off by default, deliberately, and this is a product decision worth knowing about.**
    /// Smart formatting rewrites spoken numbers as digits — a live check against the service
    /// turned "John chapter three verse sixteen" into "John chapter three verse 16". The R4
    /// scripture detector (FR-112) was specified against *spoken* numbers and carries its own
    /// spoken-number normalisation, so smart formatting changes what that detector receives.
    /// It might help it (digits are easier to parse) or hurt it (inconsistent normalisation,
    /// and the detector's spoken-number path stops being exercised by real input). That is
    /// not a call to make silently inside a transport client, so the default preserves what
    /// the detector was built for and the flag is left explicit. Tracked for the R4 pipeline.
    pub smart_format: bool,
    /// Milliseconds of silence before Deepgram finalises an utterance. Deepgram's own default
    /// is 10 ms, which finalises mid-sentence on natural speech; 300 ms suits preaching.
    pub endpointing_ms: u32,
    /// Milliseconds of silence before Deepgram emits an `UtteranceEnd` message. Only
    /// meaningful with [`StreamParams::interim_results`] on, and omitted from the query when
    /// it is off.
    pub utterance_end_ms: Option<u32>,
    /// Emit `SpeechStarted` voice-activity events.
    pub vad_events: bool,
}

impl Default for StreamParams {
    fn default() -> Self {
        StreamParams {
            model: "nova-3".to_string(),
            language: "en-US".to_string(),
            encoding: Encoding::Linear16,
            sample_rate_hz: 16_000,
            channels: 1,
            interim_results: true,
            punctuate: true,
            smart_format: false,
            endpointing_ms: 300,
            utterance_end_ms: Some(1_000),
            vad_events: false,
        }
    }
}

impl StreamParams {
    /// The query string, in a fixed order so it is byte-for-byte reproducible — the wire
    /// contract is pinned by a test rather than described in prose that drifts.
    ///
    /// `utterance_end_ms` is omitted when `interim_results` is off, because Deepgram only
    /// honours it alongside interim results.
    pub fn to_query(&self) -> String {
        let mut parts: Vec<String> = vec![
            format!("model={}", self.model),
            format!("language={}", self.language),
            format!("encoding={}", self.encoding.as_str()),
            format!("sample_rate={}", self.sample_rate_hz),
            format!("channels={}", self.channels),
            format!("interim_results={}", self.interim_results),
            format!("punctuate={}", self.punctuate),
            format!("smart_format={}", self.smart_format),
            format!("endpointing={}", self.endpointing_ms),
        ];
        if let (true, Some(ms)) = (self.interim_results, self.utterance_end_ms) {
            parts.push(format!("utterance_end_ms={ms}"));
        }
        parts.push(format!("vad_events={}", self.vad_events));
        parts.join("&")
    }
}

/// Everything needed to open one Deepgram stream: where to connect and what to authenticate
/// with.
///
/// `Debug` is hand-written; deriving it would print the credential.
#[derive(Clone)]
pub struct RequestSpec {
    url: String,
    credential: Credential,
}

impl RequestSpec {
    /// Build a request, or explain why not.
    ///
    /// Takes the [`StreamAuthorization`] by reference so a request cannot be assembled
    /// without consent, and refuses an endpoint that would carry the credential in clear
    /// text off this machine.
    pub fn build(
        _authorization: &StreamAuthorization,
        endpoint: &DeepgramEndpoint,
        params: &StreamParams,
        credential: Credential,
    ) -> Result<Self, DeepgramError> {
        if !endpoint.is_confidential() {
            return Err(DeepgramError::InsecureEndpoint {
                url: endpoint.url().to_string(),
            });
        }
        Ok(RequestSpec {
            url: format!("{}?{}", endpoint.url(), params.to_query()),
            credential: credential.clone(),
        })
    }

    /// The full URL including query parameters. Carries **no** credential — Deepgram
    /// authenticates by header, and a key in a URL ends up in proxy logs.
    pub fn url(&self) -> &str {
        &self.url
    }

    /// The `Authorization` header value. The one deliberate exit for the secret; do not log
    /// the result.
    pub fn authorization_header_value(&self) -> String {
        self.credential.authorization_header_value()
    }

    /// The credential, for scrubbing errors raised while using this request.
    pub fn credential(&self) -> &Credential {
        &self.credential
    }
}

impl std::fmt::Debug for RequestSpec {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("RequestSpec")
            .field("url", &self.url)
            .field("credential", &REDACTED)
            .finish()
    }
}

// Tests live in `tests/test_session.rs` (public-API integration tests).
