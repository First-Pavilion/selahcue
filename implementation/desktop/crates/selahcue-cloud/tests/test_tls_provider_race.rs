//! Several threads building the FIRST transport at the same moment must all succeed.
//!
//! The danger is not two installs (that is harmless) but one thread reaching `Client::build` before
//! another thread's install has finished: reqwest 0.13's `rustls-no-provider` PANICS then, and in the
//! operator that is a panic on a `spawn_blocking` worker. Its own process with one test, so the
//! constructors really are the first thing to touch the provider.

#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::ReqwestTransport;
use std::sync::{Arc, Barrier};

#[test]
fn racing_first_constructors_all_succeed() {
    const THREADS: usize = 16;
    let gate = Arc::new(Barrier::new(THREADS));
    let handles: Vec<_> = (0..THREADS)
        .map(|_| {
            let gate = Arc::clone(&gate);
            std::thread::spawn(move || {
                gate.wait();
                ReqwestTransport::new().is_ok()
            })
        })
        .collect();
    for (i, h) in handles.into_iter().enumerate() {
        assert!(
            h.join()
                .expect("a constructor panicked: the provider was not installed in time"),
            "constructor {i} returned an error"
        );
    }
}
