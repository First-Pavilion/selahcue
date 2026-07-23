//! TLS certificate pinning for the LAN transport (ADR-0009).
//!
//! The operator presents a self-signed certificate; controllers trust it **only**
//! if its SHA-256 matches a pin they obtained out-of-band (e.g. from a QR code shown
//! on the operator screen) — no public CA is involved. The handshake signature is
//! still verified against the presented certificate's key, so an attacker who copies
//! the (public) pinned certificate but lacks its private key cannot complete the
//! handshake.

use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::crypto::{verify_tls12_signature, verify_tls13_signature, CryptoProvider};
use rustls::pki_types::{CertificateDer, ServerName, UnixTime};
use rustls::{DigitallySignedStruct, Error as TlsError, SignatureScheme};
use sha2::{Digest, Sha256};
use std::sync::Arc;

/// A SHA-256 pin of a server's end-entity certificate (DER).
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct CertPin([u8; 32]);

impl CertPin {
    /// Compute the pin of a certificate's DER bytes.
    pub fn of_cert_der(der: &[u8]) -> Self {
        let mut hasher = Sha256::new();
        hasher.update(der);
        let digest = hasher.finalize();
        let mut out = [0u8; 32];
        out.copy_from_slice(&digest);
        Self(out)
    }

    /// The 32 raw pin bytes.
    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Lowercase hex encoding (e.g. for a QR payload or display).
    pub fn to_hex(&self) -> String {
        use std::fmt::Write;
        let mut s = String::with_capacity(64);
        for b in &self.0 {
            let _ = write!(s, "{b:02x}");
        }
        s
    }
}

impl std::fmt::Debug for CertPin {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "CertPin({})", self.to_hex())
    }
}

/// A rustls verifier that accepts a server iff its end-entity certificate matches
/// [`CertPin`] — ignoring CA chains and hostnames, but still verifying the handshake
/// signature against the presented certificate.
#[derive(Debug)]
pub struct PinnedServerVerifier {
    pin: CertPin,
    provider: Arc<CryptoProvider>,
}

impl PinnedServerVerifier {
    pub fn new(pin: CertPin, provider: Arc<CryptoProvider>) -> Self {
        Self { pin, provider }
    }
}

impl ServerCertVerifier for PinnedServerVerifier {
    fn verify_server_cert(
        &self,
        end_entity: &CertificateDer<'_>,
        _intermediates: &[CertificateDer<'_>],
        _server_name: &ServerName<'_>,
        _ocsp_response: &[u8],
        _now: UnixTime,
    ) -> Result<ServerCertVerified, TlsError> {
        let presented = CertPin::of_cert_der(end_entity.as_ref());
        // The pin is a public value (a hash of the public cert), so a plain compare
        // is fine — there is no secret to protect against timing here.
        if presented == self.pin {
            Ok(ServerCertVerified::assertion())
        } else {
            Err(TlsError::General("certificate pin mismatch".into()))
        }
    }

    fn verify_tls12_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        verify_tls12_signature(
            message,
            cert,
            dss,
            &self.provider.signature_verification_algorithms,
        )
    }

    fn verify_tls13_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        verify_tls13_signature(
            message,
            cert,
            dss,
            &self.provider.signature_verification_algorithms,
        )
    }

    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        self.provider
            .signature_verification_algorithms
            .supported_schemes()
    }
}
