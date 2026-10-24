//! A provider that someone else installed first is kept, not replaced, and reported as such.
//!
//! In the operator the LAN transport or the Deepgram transport may install `ring` before the cloud
//! client is first used. `install_default` then returns `Err`, which is success for us, but it must
//! be (a) not a panic, (b) not a replacement of the provider the other code is already using, and
//! (c) visible: the caller is told it was `AlreadyInstalled`, not `InstalledRing`.
//!
//! Its own process with one test, for the same reason as `test_tls_provider.rs`: the order of the
//! first two installs is the whole point.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use rustls::crypto::CryptoProvider;
use selahcue_cloud::transport::{ensure_crypto_provider, CryptoProviderInstall, ReqwestTransport};
use std::sync::Arc;

/// Whether the process-wide default is still exactly the provider object we hold (not merely an
/// equal one): a replaced provider is a different allocation.
fn is_same_provider(held: &Arc<CryptoProvider>) -> bool {
    let now = CryptoProvider::get_default().expect("a provider is installed");
    Arc::ptr_eq(held, now)
}

#[test]
fn a_provider_installed_by_someone_else_is_kept_and_reported() {
    // Someone else installs first, the way selahcue-stt-cloud's `ensure_crypto_provider` does.
    rustls::crypto::ring::default_provider()
        .install_default()
        .expect("this process had no provider yet");
    let theirs = CryptoProvider::get_default()
        .expect("the other party's provider")
        .clone();

    assert_eq!(
        ensure_crypto_provider(),
        CryptoProviderInstall::AlreadyInstalled,
        "an existing provider must be reported as already installed, not claimed as ours"
    );
    assert!(
        is_same_provider(&theirs),
        "the other party's provider was replaced"
    );

    // And the transport still builds against it, repeatedly.
    ReqwestTransport::new().expect("a transport built over a provider installed elsewhere");
    ReqwestTransport::new().expect("and a second one");
    assert_eq!(
        ensure_crypto_provider(),
        CryptoProviderInstall::AlreadyInstalled
    );
    assert!(
        is_same_provider(&theirs),
        "building transports replaced the other party's provider"
    );
}
