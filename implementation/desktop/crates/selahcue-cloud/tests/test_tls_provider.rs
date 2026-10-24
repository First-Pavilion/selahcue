//! The rustls crypto provider is installed before the first request is built (DEC-019).
//!
//! reqwest 0.13 with `rustls-no-provider` builds no provider of its own and **panics at `Client`
//! construction** when none is installed. The transport therefore installs `ring` itself, once. This
//! file is its own test binary, i.e. its own PROCESS, with exactly one test, because the thing under
//! test is process-global state that has a first use: a second test in this file, or another
//! binary's test, could install a provider first and turn "we installed it" into "someone did".
//! `test_tls_provider_preinstalled.rs` covers the opposite order.
//!
//! The same shape as `selahcue-stt-cloud`'s `the_rustls_crypto_provider_is_actually_installed`
//! (86akby4yz): without an observable, deleting the install left the whole suite green, because no
//! test made a TLS connection and nothing else notices a missing provider until production.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use rustls::crypto::CryptoProvider;
use selahcue_cloud::transport::{ensure_crypto_provider, CryptoProviderInstall, ReqwestTransport};
use std::sync::{Arc, Barrier};

/// Whether the process-wide default is still exactly the provider object we hold (not merely an
/// equal one): a replaced provider is a different allocation.
fn is_same_provider(held: &Arc<CryptoProvider>) -> bool {
    let now = CryptoProvider::get_default().expect("a provider is installed");
    Arc::ptr_eq(held, now)
}

#[test]
fn the_first_use_installs_ring_once_and_every_later_use_agrees() {
    // The premise, asserted so the test cannot silently become vacuous: nothing has installed a
    // provider in this process yet.
    assert!(
        CryptoProvider::get_default().is_none(),
        "a crypto provider was already installed before the transport ran, so this file no longer \
         tests the first-use path"
    );

    // 16 threads race the very first call. Exactly one may install; the others must wait for it
    // and report the same outcome, not a probe of the state they happened to see.
    const THREADS: usize = 16;
    let gate = Arc::new(Barrier::new(THREADS));
    let handles: Vec<_> = (0..THREADS)
        .map(|_| {
            let gate = Arc::clone(&gate);
            std::thread::spawn(move || {
                gate.wait();
                ensure_crypto_provider()
            })
        })
        .collect();
    let outcomes: Vec<CryptoProviderInstall> = handles
        .into_iter()
        .map(|h| h.join().expect("no thread may panic"))
        .collect();
    assert!(
        outcomes
            .iter()
            .all(|o| *o == CryptoProviderInstall::InstalledRing),
        "every racing caller must see the one install: {outcomes:?}"
    );

    // The provider is now really installed (the observable the stt-cloud test added).
    let installed = CryptoProvider::get_default()
        .expect("after ensure_crypto_provider() a default provider must exist")
        .clone();

    // Asking again changes nothing: same answer, and the installed provider is the same object,
    // neither replaced nor re-installed.
    assert_eq!(
        ensure_crypto_provider(),
        CryptoProviderInstall::InstalledRing
    );
    assert!(
        is_same_provider(&installed),
        "a later call replaced the process-wide provider"
    );

    // A transport can now be built, twice, in the same process: the second `new()` must neither
    // panic nor reinstall.
    let first = ReqwestTransport::new().expect("first transport");
    let second = ReqwestTransport::new().expect("second transport");
    drop((first, second));
    assert!(
        is_same_provider(&installed),
        "building a transport replaced the process-wide provider"
    );
}
