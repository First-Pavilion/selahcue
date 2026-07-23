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
    /// A message could not be (de)serialized.
    Json(serde_json::Error),
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
    fn from(e: serde_json::Error) -> Self {
        TransportError::Json(e)
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
            certified.key_pair.serialize_der(),
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
        .with_single_cert(vec![identity.cert_der.clone()], identity.key_der.clone_key())?;
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
