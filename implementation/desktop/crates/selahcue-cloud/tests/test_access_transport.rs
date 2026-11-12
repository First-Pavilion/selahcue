#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]
use selahcue_cloud::deadline_transport::DeadlineTransport;
use selahcue_cloud::transport::HttpTransport;
use selahcue_core::deadline::{AccessDeadline, Clock, ClockReading};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, Instant, SystemTime};
struct RealClock;
impl Clock for RealClock {
    fn now(&self) -> ClockReading {
        ClockReading {
            wall: Some(SystemTime::now()),
            monotonic: Instant::now(),
        }
    }
}
fn lease(ms: u64) -> AccessDeadline {
    AccessDeadline::admit(
        SystemTime::now() + Duration::from_millis(ms),
        Arc::new(RealClock),
    )
    .unwrap()
}
// Receipts contain fixed phase names and monotonic offsets only, never request data.
#[derive(Clone)]
struct Trace {
    started: Instant,
    events: Arc<Mutex<Vec<(&'static str, Duration)>>>,
}
impl Trace {
    fn new() -> Self {
        Self {
            started: Instant::now(),
            events: Arc::new(Mutex::new(Vec::with_capacity(24))),
        }
    }
    fn mark(&self, phase: &'static str) {
        let mut events = self.events.lock().unwrap();
        assert!(events.len() < 24, "bounded fixture receipt capacity");
        events.push((phase, self.started.elapsed()));
    }
    fn has(&self, phase: &str) -> bool {
        self.events.lock().unwrap().iter().any(|(p, _)| *p == phase)
    }
    fn report(&self, case: &str) {
        eprintln!(
            "HTTP deadline case={case} phases={:?}",
            self.events.lock().unwrap()
        );
    }
}
#[derive(Debug, PartialEq, Eq)]
struct FixtureFailure {
    phase: &'static str,
    kind: Option<std::io::ErrorKind>,
}
fn io_failure(phase: &'static str, error: std::io::Error) -> FixtureFailure {
    FixtureFailure {
        phase,
        kind: Some(error.kind()),
    }
}
fn fixture_failure(phase: &'static str) -> FixtureFailure {
    FixtureFailure { phase, kind: None }
}
// A complete, bounded request with the literal synthetic authorization is required
// before the fixture can classify a close as in-flight cancellation.
fn read_authenticated_request(stream: &mut TcpStream) -> Result<(), FixtureFailure> {
    let end = Instant::now() + Duration::from_secs(2);
    let mut bytes = Vec::with_capacity(4096);
    loop {
        if bytes.len() == 4096 || Instant::now() >= end {
            return Err(fixture_failure("request-bound"));
        }
        stream
            .set_read_timeout(Some(end.saturating_duration_since(Instant::now())))
            .map_err(|e| io_failure("request-timeout-setup", e))?;
        let mut buf = [0; 512];
        let limit = buf.len().min(4096 - bytes.len());
        let n = stream
            .read(&mut buf[..limit])
            .map_err(|e| io_failure("request-read", e))?;
        if n == 0 {
            return Err(fixture_failure("request-incomplete-eof"));
        }
        bytes.extend_from_slice(&buf[..n]);
        if let Some(header_end) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
            let header = std::str::from_utf8(&bytes[..header_end])
                .map_err(|_| fixture_failure("request-header"))?;
            let mut lines = header.split("\r\n");
            if !matches!(
                lines.next(),
                Some("POST /fixture HTTP/1.1" | "POST / HTTP/1.1")
            ) {
                return Err(fixture_failure("request-method"));
            }
            let fields: Vec<_> = lines.filter_map(|line| line.split_once(':')).collect();
            let exact_field = |name: &str, expected: &str| {
                let values: Vec<_> = fields
                    .iter()
                    .filter(|(key, _)| key.eq_ignore_ascii_case(name))
                    .collect();
                values.len() == 1 && values[0].1.trim() == expected
            };
            if !exact_field("authorization", "Bearer synthetic-native-fixture")
                || !exact_field("content-length", "2")
            {
                return Err(fixture_failure("request-auth-or-length"));
            }
            let body = &bytes[header_end + 4..];
            if body.len() >= 2 {
                return if body == b"{}" {
                    Ok(())
                } else {
                    Err(fixture_failure("request-body"))
                };
            }
        }
    }
}
struct CloseFixture {
    url: String,
    trace: Trace,
    stop: Arc<AtomicBool>,
    receipt: std::sync::mpsc::Receiver<Result<Instant, FixtureFailure>>,
    thread: Option<std::thread::JoinHandle<()>>,
}
impl CloseFixture {
    fn start(head: bool, jump: Option<Arc<std::sync::atomic::AtomicU64>>, trace: Trace) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let url = format!("http://{}/fixture", listener.local_addr().unwrap());
        trace.mark("listener-ready");
        let stop = Arc::new(AtomicBool::new(false));
        let stopped = stop.clone();
        let events = trace.clone();
        let (tx, receipt) = std::sync::mpsc::channel();
        // Preserve the forward-jump fixture's original 500 ms read bound.
        let eof_timeout = if jump.is_some() {
            Duration::from_millis(500)
        } else {
            Duration::from_secs(2)
        };
        let thread = std::thread::spawn(move || {
            let outcome = (|| {
                let accept_end = Instant::now() + Duration::from_secs(2);
                let mut stream = loop {
                    if stopped.load(Ordering::SeqCst) {
                        return Err(fixture_failure("accept-stopped"));
                    }
                    match listener.accept() {
                        Ok((stream, _)) => break stream,
                        Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                            if Instant::now() >= accept_end {
                                return Err(fixture_failure("accept-timeout"));
                            }
                            std::thread::sleep(Duration::from_millis(1));
                        }
                        Err(e) => return Err(io_failure("accept", e)),
                    }
                };
                events.mark("accepted");
                stream
                    .set_nonblocking(false)
                    .map_err(|e| io_failure("accepted-mode-setup", e))?;
                read_authenticated_request(&mut stream)?;
                events.mark("authenticated-request-complete");
                if let Some(jump) = jump {
                    jump.store(60_000, Ordering::SeqCst);
                }
                if head {
                    events.mark("delayed-head-wait");
                    std::thread::sleep(Duration::from_millis(60));
                    events.mark("head-body-write-entry");
                    stream
                        .set_write_timeout(Some(Duration::from_secs(2)))
                        .map_err(|e| io_failure("write-timeout-setup", e))?;
                    stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\nx")
                        .map_err(|e| io_failure("head-body-write", e))?;
                    events.mark("head-body-written");
                }
                events.mark("eof-observer-entry");
                stream
                    .set_read_timeout(Some(eof_timeout))
                    .map_err(|e| io_failure("eof-timeout-setup", e))?;
                let mut buf = [0; 512];
                match stream.read(&mut buf) {
                    Ok(0) => {
                        let eof = Instant::now();
                        events.mark("actual-eof");
                        Ok(eof)
                    }
                    Ok(_) => Err(fixture_failure("unexpected-extra-request-bytes")),
                    Err(e) => Err(io_failure("eof-read", e)),
                }
            })();
            if let Err(error) = &outcome {
                events.mark(error.phase);
            }
            events.mark("receipt-send");
            let _ = tx.send(outcome);
        });
        Self {
            url,
            trace,
            stop,
            receipt,
            thread: Some(thread),
        }
    }
    fn observe(
        &self,
    ) -> Result<Result<Instant, FixtureFailure>, std::sync::mpsc::RecvTimeoutError> {
        let result = self.receipt.recv_timeout(Duration::from_millis(500));
        self.trace.mark("receipt-received-or-watchdog");
        result
    }
    fn join(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(thread) = self.thread.take() {
            thread.join().unwrap();
            self.trace.mark("fixture-joined");
        }
    }
}
impl Drop for CloseFixture {
    fn drop(&mut self) {
        self.join();
    }
}
#[test]
fn delayed_head_and_slow_body_really_close_the_client_at_one_deadline() {
    for head in [false, true] {
        let trace = Trace::new();
        let mut fixture = CloseFixture::start(head, None, trace.clone());
        let started = Instant::now();
        trace.mark("admission-entry");
        let deadline = lease(120);
        trace.mark("admitted-build-entry");
        let t =
            DeadlineTransport::new_for_loopback_tests(deadline, Arc::new(AtomicBool::new(false)))
                .unwrap();
        trace.mark("build-return-request-entry");
        let result = t.post_json(&fixture.url, "{}", Some("synthetic-native-fixture"));
        trace.mark("request-return");
        let receipt = fixture.observe();
        fixture.join();
        trace.report(if head {
            "delayed-head-partial-body"
        } else {
            "stalled-head"
        });
        eprintln!("HTTP deadline close receipt={receipt:?}");
        assert!(result.is_err());
        assert!(
            trace.has("authenticated-request-complete"),
            "complete authenticated request required"
        );
        if head {
            assert!(
                trace.has("head-body-written"),
                "partial-body phase required"
            );
        }
        let closed = receipt
            .expect("actual HTTP socket close watchdog")
            .expect("actual HTTP socket EOF, not fixture error");
        assert!(closed.duration_since(started) < Duration::from_millis(620));
    }
}
#[test]
fn forced_setup_expiry_refuses_without_accepting_request_bytes() {
    let trace = Trace::new();
    let mut fixture = CloseFixture::start(false, None, trace.clone());
    trace.mark("admission-entry");
    let deadline = lease(120);
    trace.mark("admitted-forced-setup-delay");
    std::thread::sleep(Duration::from_millis(150));
    let transport =
        DeadlineTransport::new_for_loopback_tests(deadline, Arc::new(AtomicBool::new(false)))
            .unwrap();
    trace.mark("build-return-request-entry");
    let result = transport.post_json(&fixture.url, "{}", Some("synthetic-native-fixture"));
    trace.mark("request-return");
    let receipt = fixture.observe();
    fixture.join();
    trace.report("forced-setup-expiry");
    assert!(result.is_err());
    assert_eq!(
        receipt.unwrap_err(),
        std::sync::mpsc::RecvTimeoutError::Timeout
    );
    assert!(
        !trace.has("accepted"),
        "expired setup must open no socket or send bytes"
    );
    let terminal = fixture.receipt.recv().unwrap();
    eprintln!("HTTP deadline setup-expiry terminal={terminal:?}");
    assert_eq!(terminal.unwrap_err().phase, "accept-stopped");
}
#[test]
fn rejection_is_latched_without_waiting_for_or_returning_a_raw_body() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}/", listener.local_addr().unwrap());
    let server = std::thread::spawn(move || {
        let (mut s, _) = listener.accept().unwrap();
        let mut b = [0; 4096];
        let _ = s.read(&mut b);
        let _ = s.write_all(
            b"HTTP/1.1 403 Forbidden\r\nContent-Length: 99999\r\n\r\nsynthetic-secret-body",
        );
    });
    let rejected = Arc::new(AtomicBool::new(false));
    let t = DeadlineTransport::new_for_loopback_tests(lease(1000), rejected.clone()).unwrap();
    let response = t.post_json(&url, "{}", None).unwrap();
    assert_eq!(response.status, 403);
    assert!(response.body.is_empty());
    assert!(rejected.load(Ordering::SeqCst));
    server.join().unwrap();
}

#[test]
fn forward_clock_jump_cancels_real_inflight_http_and_expired_dispatch_sends_nothing() {
    use std::sync::atomic::AtomicU64;
    struct JumpClock(Arc<AtomicU64>);
    impl Clock for JumpClock {
        fn now(&self) -> ClockReading {
            ClockReading {
                wall: Some(
                    SystemTime::now() + Duration::from_millis(self.0.load(Ordering::SeqCst)),
                ),
                monotonic: Instant::now(),
            }
        }
    }
    let trace = Trace::new();
    let advance = Arc::new(AtomicU64::new(0));
    let mut fixture = CloseFixture::start(false, Some(advance.clone()), trace.clone());
    let deadline = AccessDeadline::admit(
        SystemTime::now() + Duration::from_secs(30),
        Arc::new(JumpClock(advance)),
    )
    .unwrap();
    let transport =
        DeadlineTransport::new_for_loopback_tests(deadline, Arc::new(AtomicBool::new(false)))
            .unwrap();
    trace.mark("request-entry");
    let result = transport.post_json(&fixture.url, "{}", Some("synthetic-native-fixture"));
    trace.mark("request-return");
    let receipt = fixture.observe();
    fixture.join();
    trace.report("forward-clock-jump");
    eprintln!("HTTP deadline close receipt={receipt:?}");
    assert!(result.is_err());
    assert!(trace.has("authenticated-request-complete"));
    receipt
        .expect("wall-jump socket close watchdog")
        .expect("wall-jump actual EOF");
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let url = format!("http://{}/", listener.local_addr().unwrap());
    let expired = lease(20);
    std::thread::sleep(Duration::from_millis(30));
    let transport =
        DeadlineTransport::new_for_loopback_tests(expired, Arc::new(AtomicBool::new(false)))
            .unwrap();
    assert!(transport.post_json(&url, "{}", None).is_err());
    assert_eq!(
        listener.accept().unwrap_err().kind(),
        std::io::ErrorKind::WouldBlock
    );
}
