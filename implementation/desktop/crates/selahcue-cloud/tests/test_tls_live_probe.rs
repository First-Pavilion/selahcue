//! A LIVE check that the production constructor trusts the operating-system store: a request to a
//! public HTTPS host through `ReqwestTransport::new()` must succeed.
//!
//! IGNORED BY DEFAULT: it needs the network and a public host. It exists because nothing else in the
//! suite can show, on macOS or Windows, that the OS store is consulted at all: the other TLS tests
//! hand a throwaway CA to a private constructor, and a client built to trust NOTHING from the OS
//! (for example `build()` always calling `tls_certs_only(extra_roots)`) passes all of them; only the
//! Linux test (via `SSL_CERT_FILE`) and this probe catch it. Run it by hand before a release and
//! after a reqwest or rustls-platform-verifier bump:
//!
//! ```text
//! cargo test -p selahcue-cloud --features http --test test_tls_live_probe -- --ignored
//! ```
//!
//! `SELAHCUE_LIVE_PROBE_URL` overrides the host (default `https://example.com`). A machine behind a
//! proxy needs `HTTPS_PROXY`/`HTTP_PROXY` set as usual.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};

#[test]
#[ignore = "needs the network; run by hand with --ignored (see the file header)"]
fn a_public_host_is_accepted_through_the_production_constructor() {
    let url = std::env::var("SELAHCUE_LIVE_PROBE_URL")
        .unwrap_or_else(|_| "https://example.com".to_string());
    let transport = ReqwestTransport::new().expect("the production transport");
    let resp = transport.get(&url, None).unwrap_or_else(|e| {
        panic!("a public certificate was refused or the host is unreachable: {e}")
    });
    assert!(
        (200..400).contains(&resp.status),
        "unexpected status {} from {url}",
        resp.status
    );
}
