//! The transport-level response cap (86akby7d8, review round 2 / R2).
//!
//! `read_capped` is the bound that actually holds: a cap applied *after* the body is in
//! hand bounds parsing, not memory, because by then an unbounded read has already
//! allocated whatever the peer chose to send.
//!
//! **This file is deliberately not feature-gated.** The previous version of this bound
//! took a `reqwest::blocking::Response`, so it existed only under the `http` feature —
//! which the cloud gate never compiles and no gate ever *ran*. It was linted into
//! existence and executed by nothing. Taking `impl Read` puts it in the default build,
//! where `cargo test --workspace` covers it.
#![allow(clippy::unwrap_used)]

use selahcue_cloud::transport::read_capped;
// Only the cross-cap comparison at the bottom needs the shipped constant, and that assertion
// is `openai`-gated, so the import is too.
#[cfg(feature = "openai")]
use selahcue_cloud::transport::MAX_TRANSPORT_RESPONSE_BYTES;

const CAP: usize = 1_000;

#[test]
fn a_body_exactly_at_the_cap_is_accepted_whole() {
    // The `cap + 1` read exists for this case. Reading exactly `cap` and stopping would
    // silently truncate a legitimately cap-sized body, and a truncated JSON body surfaces
    // as a confusing parse error rather than as the size problem it is.
    let body = vec![b'x'; CAP];
    let got = read_capped(std::io::Cursor::new(body.clone()), CAP)
        .expect("a body exactly at the cap must be accepted, not refused");
    assert_eq!(got.len(), CAP);
    assert_eq!(got, body, "and it must arrive intact, not truncated");
}

#[test]
fn one_byte_over_the_cap_is_refused() {
    let body = vec![b'x'; CAP + 1];
    let err = read_capped(std::io::Cursor::new(body), CAP)
        .expect_err("a body over the cap must be refused");

    // Off-by-one guard: this pair is the whole point of reading `cap + 1`. If the
    // implementation read exactly `cap`, the test above would truncate silently and this
    // one would never fire.
    assert!(
        err.to_string().contains(&CAP.to_string()),
        "the error should name the cap: {err}"
    );
}

#[test]
fn a_refusal_leaks_nothing_from_the_body() {
    // Response bodies are attacker-influenced, and on at least one real provider (OpenAI's
    // 401) they contain key material. The size error must never quote them.
    let secret = "sk-proj-SECRETKEYMATERIAL";
    let mut body = secret.as_bytes().to_vec();
    body.resize(CAP + 500, b'x');
    let err = read_capped(std::io::Cursor::new(body), CAP).unwrap_err();
    let rendered = format!("{err}  {err:?}");
    assert!(
        !rendered.contains(secret) && !rendered.contains("sk-proj-"),
        "body content reached the transport error: {rendered}"
    );
}

/// A reader that yields some bytes and then fails — a connection dropped mid-body.
struct FailsMidStream {
    sent: usize,
}

impl std::io::Read for FailsMidStream {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.sent >= 16 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::ConnectionReset,
                "peer went away",
            ));
        }
        let n = buf.len().min(16);
        for b in buf.iter_mut().take(n) {
            *b = b'y';
        }
        self.sent += n;
        Ok(n)
    }
}

#[test]
fn a_stream_that_fails_partway_is_an_error_not_a_short_body() {
    // Returning the partial bytes would hand the parser a truncated body, which surfaces as
    // `Malformed` — a terminal state the operator sees — instead of `Transport`, which is
    // the one that correctly serves the degraded local draft. Getting this wrong routes a
    // dropped connection to the wrong recovery path.
    let err = read_capped(FailsMidStream { sent: 0 }, CAP)
        .expect_err("a mid-stream failure must be an error");
    assert!(err.to_string().contains("peer went away"), "{err}");
}

#[test]
fn a_small_body_passes_through_untouched() {
    // POSITIVE CONTROL. Without it, every assertion above is satisfied by an implementation
    // that refuses everything.
    let got = read_capped(std::io::Cursor::new(b"{\"ok\":true}".to_vec()), CAP).unwrap();
    assert_eq!(got, b"{\"ok\":true}");
}

// The two bounds are deliberately different sizes and deliberately differently named. A body
// between them is READ and then refused by the parser with a precise error, which is a better
// diagnostic than a truncated read — so the socket ceiling must sit ABOVE the parse ceiling, or
// a legitimately-sized body would be cut off before the parser could explain why.
//
// Pinned at COMPILE time rather than as a test: both sides are constants, so a runtime assertion
// could only ever restate what the compiler already knows. Needs the `openai` feature because
// that is where the parse-side cap lives; everything above it is deliberately ungated, which is
// the whole reason `read_capped` takes `impl Read` rather than a `reqwest::Response`.
#[cfg(feature = "openai")]
const _: () = assert!(
    MAX_TRANSPORT_RESPONSE_BYTES > selahcue_cloud::openai::MAX_PARSED_RESPONSE_BYTES,
    "the socket ceiling must sit above the parse ceiling"
);
