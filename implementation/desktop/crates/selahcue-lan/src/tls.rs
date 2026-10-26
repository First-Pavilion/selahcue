//! Self-signed certificate generation and pinned TLS configuration (ADR-0009).

use crate::pinning::{CertPin, PinnedServerVerifier};
use rustls::crypto::CryptoProvider;
use rustls::pki_types::{CertificateDer, PrivateKeyDer, PrivatePkcs8KeyDer};
use rustls::{ClientConfig, ServerConfig};
use std::sync::Arc;

/// Errors from the LAN transport.
#[derive(Debug)]
pub enum TransportError {
    /// TLS configuration or handshake error.
    Tls(rustls::Error),
    /// Certificate generation error.
    Cert(String),
    /// Underlying I/O error.
    Io(std::io::Error),
    /// WebSocket protocol error. Boxed because `tungstenite::Error` is large and
    /// would otherwise bloat every `Result<_, TransportError>`.
    Ws(Box<tokio_tungstenite::tungstenite::Error>),
    /// A message could not be (de)serialized. Carries only the failure's category and position,
    /// never serde's message: see [`JsonFailure`] (FR-082, 17tnw2b9aec).
    Json(JsonFailure),
    /// The peer violated the control protocol (e.g. wrong frame, bad version).
    Protocol(String),
    /// The connection closed before the exchange completed.
    Closed,
}

impl std::fmt::Display for TransportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TransportError::Tls(e) => write!(f, "tls error: {e}"),
            TransportError::Cert(e) => write!(f, "certificate error: {e}"),
            TransportError::Io(e) => write!(f, "io error: {e}"),
            TransportError::Ws(e) => write!(f, "websocket error: {e}"),
            TransportError::Json(e) => write!(f, "json error: {e}"),
            TransportError::Protocol(e) => write!(f, "protocol error: {e}"),
            TransportError::Closed => f.write_str("connection closed"),
        }
    }
}

impl std::error::Error for TransportError {}

impl From<rustls::Error> for TransportError {
    fn from(e: rustls::Error) -> Self {
        TransportError::Tls(e)
    }
}
impl From<std::io::Error> for TransportError {
    fn from(e: std::io::Error) -> Self {
        TransportError::Io(e)
    }
}
impl From<tokio_tungstenite::tungstenite::Error> for TransportError {
    fn from(e: tokio_tungstenite::tungstenite::Error) -> Self {
        TransportError::Ws(Box::new(e))
    }
}
impl From<serde_json::Error> for TransportError {
    /// The one conversion every (de)serialization failure on the wire goes through. It keeps the
    /// category and the position and drops the `serde_json::Error` itself, so nothing in the
    /// result can quote the frame (see [`JsonFailure`]).
    fn from(e: serde_json::Error) -> Self {
        TransportError::Json(JsonFailure::from(&e))
    }
}

/// What a failed JSON decode (or encode) is allowed to tell a person or a log: a category in
/// words of our own, and the line and column **when serde has them**. **Never serde's message.**
///
/// serde quotes the offending VALUE in its message: `invalid type: string "SECRET sermon words",
/// expected a sequence` for a wrongly-typed field, ``unknown variant `SECRET`, expected one of
/// ...`` for an unknown enum tag. The frame can be the operator's state (it carries the live
/// transcript), a pairing grant (it carries a device token) or whatever a version-skewed, buggy
/// or hostile peer put in the wrong place. `TransportError::Json` used to wrap the whole
/// `serde_json::Error`, so both `Display` and the derived `Debug` printed that text, and every
/// caller that logged the error or returned it to the UI carried it along (FR-082,
/// 17tnw2b9aec).
///
/// This type holds a [`JsonFailureKind`] and two numbers, so there is no text for a derived
/// `Debug` to leak and no `source()` to walk. It is the same approach as the cloud client's
/// error mapping (`selahcue-cloud`, 86akbzxjg: category and position only), not a redaction pass
/// over text: a filter can only remove what someone thought to describe.
///
/// **The position is not always there.** serde reports line 0 and column 0 when it has no
/// position, which is the case for a data error inside an internally tagged enum (serde buffers
/// the content before it knows the variant). Every wire message here (`ServerMessage`,
/// `AuthResponse`, `PairResponse`, `Hello`, `Command`) is such an enum, so most shape errors have
/// none. `Display` says `(no position)` for those rather than `at line 0 column 0`, as serde
/// itself omits the suffix; the numbers stay readable through [`JsonFailure::line`] and
/// [`JsonFailure::column`]. Where there is a position it says roughly how far into the frame the
/// failure was, never what was there.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct JsonFailure {
    kind: JsonFailureKind,
    line: usize,
    column: usize,
}

/// What kind of JSON failure it was, as `serde_json` classifies it.
///
/// `#[non_exhaustive]`: a new category in a future serde_json must not break a caller that
/// matches on this. Nothing in the workspace matches it exhaustively outside this crate.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum JsonFailureKind {
    /// The text is not valid JSON.
    Syntax,
    /// Valid JSON that does not have the shape the protocol defines (a missing field, a field of
    /// the wrong type, an unknown variant). The category serde quotes values in.
    Data,
    /// The text ended before the value did.
    Eof,
    /// Reading the text failed. **Unreachable from parsing a string** (`protocol::from_json` and
    /// every frame the transport receives): `serde_json` produces it only when it reads a stream.
    /// Kept so the mapping from `serde_json`'s categories is total.
    Io,
}

impl JsonFailure {
    /// The category of the failure.
    pub fn kind(&self) -> JsonFailureKind {
        self.kind
    }

    /// The 1-based line the failure was detected on (0 when serde has no position: see the type
    /// documentation).
    pub fn line(&self) -> usize {
        self.line
    }

    /// The 1-based column the failure was detected at (0 when serde has no position: see the type
    /// documentation).
    pub fn column(&self) -> usize {
        self.column
    }
}

impl From<&serde_json::Error> for JsonFailure {
    fn from(e: &serde_json::Error) -> Self {
        use serde_json::error::Category;
        JsonFailure {
            kind: match e.classify() {
                Category::Syntax => JsonFailureKind::Syntax,
                Category::Data => JsonFailureKind::Data,
                Category::Eof => JsonFailureKind::Eof,
                Category::Io => JsonFailureKind::Io,
            },
            line: e.line(),
            column: e.column(),
        }
    }
}

impl std::fmt::Display for JsonFailure {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let what = match self.kind {
            JsonFailureKind::Syntax => "the message was not valid JSON",
            JsonFailureKind::Data => "the message did not have the shape the protocol defines",
            JsonFailureKind::Eof => "the message ended early",
            JsonFailureKind::Io => "the message could not be read",
        };
        if self.line == 0 {
            // serde has no position (see the type documentation); do not invent one.
            write!(f, "{what} (no position)")
        } else {
            write!(f, "{what} at line {} column {}", self.line, self.column)
        }
    }
}

/// The pure-Rust crypto provider (ring) used everywhere in the transport.
pub fn crypto_provider() -> Arc<CryptoProvider> {
    Arc::new(rustls::crypto::ring::default_provider())
}

/// A freshly generated self-signed identity for the operator server, plus the
/// [`CertPin`] controllers must trust.
pub struct SelfSigned {
    pub cert_der: CertificateDer<'static>,
    pub key_der: PrivateKeyDer<'static>,
    /// The pin controllers verify against (share this out-of-band, e.g. via QR).
    pub pin: CertPin,
}

impl SelfSigned {
    /// Generate a new self-signed certificate/key for the given SAN names
    /// (e.g. `["localhost"]` or the operator's LAN hostname/IP).
    pub fn generate(sans: Vec<String>) -> Result<Self, TransportError> {
        let certified = rcgen::generate_simple_self_signed(sans)
            .map_err(|e| TransportError::Cert(e.to_string()))?;
        let cert_der = certified.cert.der().clone();
        let pin = CertPin::of_cert_der(cert_der.as_ref());
        let key_der = PrivateKeyDer::Pkcs8(PrivatePkcs8KeyDer::from(
            certified.signing_key.serialize_der(),
        ));
        Ok(Self {
            cert_der,
            key_der,
            pin,
        })
    }
}

/// Build the operator's TLS server configuration from its self-signed identity.
pub fn server_config(identity: &SelfSigned) -> Result<ServerConfig, TransportError> {
    let config = ServerConfig::builder_with_provider(crypto_provider())
        .with_safe_default_protocol_versions()?
        .with_no_client_auth()
        .with_single_cert(
            vec![identity.cert_der.clone()],
            identity.key_der.clone_key(),
        )?;
    Ok(config)
}

/// Build a controller's TLS client configuration that trusts **only** the server
/// whose certificate matches `pin`.
pub fn client_config(pin: CertPin) -> Result<ClientConfig, TransportError> {
    let provider = crypto_provider();
    let verifier = Arc::new(PinnedServerVerifier::new(pin, provider.clone()));
    let config = ClientConfig::builder_with_provider(provider)
        .with_safe_default_protocol_versions()?
        .dangerous()
        .with_custom_certificate_verifier(verifier)
        .with_no_client_auth();
    Ok(config)
}
