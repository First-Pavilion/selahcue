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
    let got = read_capped(std::io::Cursor::new(body.clone()), CAP, None)
        .expect("a body exactly at the cap must be accepted, not refused");
    assert_eq!(got.len(), CAP);
    assert_eq!(got, body, "and it must arrive intact, not truncated");
}

#[test]
fn one_byte_over_the_cap_is_refused() {
    let body = vec![b'x'; CAP + 1];
    let err = read_capped(std::io::Cursor::new(body), CAP, None)
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
    let err = read_capped(std::io::Cursor::new(body), CAP, None).unwrap_err();
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
    let err = read_capped(FailsMidStream { sent: 0 }, CAP, None)
        .expect_err("a mid-stream failure must be an error");
    assert!(err.to_string().contains("peer went away"), "{err}");
}

/// Counts the bytes actually pulled from the underlying stream, and refuses to serve an
/// unbounded amount so a broken bound cannot hang the suite.
struct CountingReader {
    remaining: usize,
    pulled: std::sync::Arc<std::sync::atomic::AtomicUsize>,
}

impl std::io::Read for CountingReader {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.remaining == 0 {
            return Ok(0);
        }
        let n = buf.len().min(self.remaining).min(64 * 1024);
        for b in buf.iter_mut().take(n) {
            *b = b'z';
        }
        self.remaining -= n;
        self.pulled
            .fetch_add(n, std::sync::atomic::Ordering::SeqCst);
        Ok(n)
    }
}

#[test]
fn the_cap_bounds_what_is_read_off_the_wire_not_merely_what_is_returned() {
    // THE control for this module, and the one the outcome assertions do not provide.
    //
    // Every other test here checks what `read_capped` RETURNS, and a post-hoc length check on a
    // fully-buffered body returns exactly the same things — so deleting `.take(cap + 1)` and
    // leaving an unbounded `read_to_end` passes all of them, green, exit 0. That mutation is the
    // entire bug the function exists to prevent: memory is allocated before any check runs.
    //
    // So assert the ENTITY — how many bytes were pulled from the stream — rather than the
    // outcome. A hostile peer offering far more than the cap must cost us the cap, not the offer.
    let pulled = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let offered = 8 * 1024 * 1024; // what a hostile peer is willing to send
    let reader = CountingReader {
        remaining: offered,
        pulled: pulled.clone(),
    };

    let err = read_capped(reader, CAP, None).expect_err("8 MB against a 1 KB cap must be refused");
    let n = pulled.load(std::sync::atomic::Ordering::SeqCst);

    assert!(
        n <= CAP + 1,
        "read_capped pulled {n} bytes off a stream offering {offered} against a {CAP}-byte cap; \
         the bound must limit the READ, not just the returned value — an unbounded read_to_end \
         followed by a length check produces an identical error while allocating everything"
    );
    assert!(err.to_string().contains(&CAP.to_string()));

    // POSITIVE CONTROL: a stream inside the cap is read to completion, so the assertion above
    // is not satisfied by a function that reads nothing.
    let pulled2 = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let got = read_capped(
        CountingReader {
            remaining: 500,
            pulled: pulled2.clone(),
        },
        CAP,
        None,
    )
    .expect("a body under the cap must be accepted");
    assert_eq!(got.len(), 500);
    assert_eq!(pulled2.load(std::sync::atomic::Ordering::SeqCst), 500);
}

#[test]
fn a_small_body_passes_through_untouched() {
    // POSITIVE CONTROL. Without it, every assertion above is satisfied by an implementation
    // that refuses everything.
    let got = read_capped(std::io::Cursor::new(b"{\"ok\":true}".to_vec()), CAP, None).unwrap();
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

/// Always has one more byte, and never finishes. Models the peer that sends headers and then
/// drips — the shape that evaded the client timeout entirely.
struct DrippingReader;

impl std::io::Read for DrippingReader {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if buf.is_empty() {
            return Ok(0);
        }
        buf[0] = b'.';
        Ok(1)
    }
}

#[test]
fn a_peer_that_drips_bytes_forever_is_cut_off_at_the_deadline() {
    // PERF-2. This is the case every earlier probe missed: they all tested a peer that goes
    // SILENT, and silence was the one shape reqwest's per-read timeout already handled. A peer
    // that keeps sending — one byte at a time — resets that clock on every read and was measured
    // still being read 172 seconds past a 60-second deadline.
    //
    // Deterministic and offline: no sleeping, no sockets, no wall-clock flakiness. An infinite
    // reader against an already-expired deadline must refuse rather than run forever, and this
    // test cannot pass by hanging — it would never finish.
    let already_past = std::time::Instant::now() - std::time::Duration::from_secs(1);
    let err = read_capped(DrippingReader, usize::MAX, Some(already_past))
        .expect_err("an expired deadline must refuse a dripping peer");
    assert!(
        err.to_string().contains("timed out"),
        "the refusal must name the deadline, not the cap: {err}"
    );

    // And with a live-but-short deadline it still terminates, rather than only handling the
    // already-expired special case.
    let soon = std::time::Instant::now() + std::time::Duration::from_millis(50);
    let t0 = std::time::Instant::now();
    let err = read_capped(DrippingReader, usize::MAX, Some(soon))
        .expect_err("a dripping peer must be cut off");
    let elapsed = t0.elapsed();
    assert!(err.to_string().contains("timed out"), "{err}");
    assert!(
        elapsed < std::time::Duration::from_secs(5),
        "the deadline must actually bound elapsed time; took {elapsed:?}"
    );

    // POSITIVE CONTROL: a generous deadline does not interfere with a normal body, so the
    // assertions above are not satisfied by a function that refuses everything.
    let far = std::time::Instant::now() + std::time::Duration::from_secs(60);
    let got = read_capped(
        std::io::Cursor::new(b"{\"ok\":true}".to_vec()),
        CAP,
        Some(far),
    )
    .expect("a normal body must still be read under a live deadline");
    assert_eq!(got, b"{\"ok\":true}");
}

#[test]
fn the_cap_still_bites_while_a_deadline_is_live() {
    // The two bounds must not shadow each other: an over-cap body under a generous deadline is
    // still a cap refusal, not a timeout.
    let far = std::time::Instant::now() + std::time::Duration::from_secs(60);
    let err = read_capped(DrippingReader, CAP, Some(far))
        .expect_err("an infinite stream must hit the cap");
    assert!(
        err.to_string().contains(&CAP.to_string()) && !err.to_string().contains("timed out"),
        "an over-cap body under a live deadline must be refused for SIZE: {err}"
    );
}

/// Drips key-shaped marker bytes forever, so a timeout fires with attacker-influenced content
/// sitting in the buffer — the state in which an echo would leak. Counts what it emitted so the
/// test can prove that state was actually reached.
struct MarkerDrip {
    emitted: std::sync::Arc<std::sync::atomic::AtomicUsize>,
}

impl std::io::Read for MarkerDrip {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        let m = b"sk-proj-TIMEOUT-MARKER-";
        let n = m.len().min(buf.len());
        buf[..n].copy_from_slice(&m[..n]);
        self.emitted
            .fetch_add(n, std::sync::atomic::Ordering::SeqCst);
        Ok(n)
    }
}

#[test]
fn a_timeout_refusal_leaks_nothing_from_the_body() {
    // Sana F-3. The two timeout branches were born unpinned for the no-echo property: adding a
    // body-prefix echo to both of them passed the entire suite, exit 0. The drip tests assert the
    // error SAYS "timed out" and never that it does not say anything else, and the size-refusal
    // leak test only covers the cap branch.
    //
    // A **live-short** deadline, not an already-expired one: the buffer has to accumulate
    // attacker-controlled content BEFORE expiry, or the assertion fires on an empty buffer and
    // proves nothing about echoing. That is the same trap as a test whose setup makes its own
    // assertion unreachable.
    let emitted = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let soon = std::time::Instant::now() + std::time::Duration::from_millis(20);
    let err = read_capped(
        MarkerDrip {
            emitted: emitted.clone(),
        },
        usize::MAX,
        Some(soon),
    )
    .expect_err("must time out");

    // PREMISE, pinned rather than assumed. "Live-short" is a timing argument, and on a loaded
    // machine the deadline could elapse before the first read returns — leaving an empty buffer
    // and a vacuously-passing test. Assert the leak-able state was actually reached.
    let n = emitted.load(std::sync::atomic::Ordering::SeqCst);
    assert!(
        n > 0,
        "no bytes were ever emitted, so the timeout fired on an empty buffer and this test \
         proves nothing about echoing"
    );

    assert!(
        err.to_string().contains("timed out"),
        "positive control — the DEADLINE branch fired, not the cap branch: {err}"
    );
    let rendered = format!("{err}  {err:?}");
    assert!(
        !rendered.contains("sk-proj-"),
        "the timeout error echoed body content: {rendered}"
    );
    assert!(
        !rendered.contains("MARKER"),
        "the timeout error echoed body content: {rendered}"
    );
}
