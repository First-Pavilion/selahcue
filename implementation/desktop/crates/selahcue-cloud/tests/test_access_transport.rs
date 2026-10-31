#![cfg(feature = "http")]
#![allow(clippy::unwrap_used)]
use selahcue_cloud::deadline_transport::DeadlineTransport;
use selahcue_cloud::transport::HttpTransport;
use selahcue_core::deadline::{AccessDeadline, Clock, ClockReading};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
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
#[test]
fn delayed_head_and_slow_body_really_close_the_client_at_one_deadline() {
    for head in [false, true] {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/fixture", listener.local_addr().unwrap());
        let (closed_tx, closed_rx) = std::sync::mpsc::channel();
        let server = std::thread::spawn(move || {
            let (mut s, _) = listener.accept().unwrap();
            s.set_read_timeout(Some(Duration::from_secs(2))).unwrap();
            let mut buf = [0; 4096];
            let _ = s.read(&mut buf).unwrap();
            if head {
                std::thread::sleep(Duration::from_millis(60));
                s.write_all(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\nConnection: close\r\n\r\nx",
                )
                .unwrap();
            }
            // Reading EOF observes an actual connection close, not an outer task timeout.
            loop {
                match s.read(&mut buf) {
                    Ok(0) => break,
                    Ok(_) => {}
                    Err(e) => panic!("client did not close: {e}"),
                }
            }
            closed_tx.send(Instant::now()).unwrap();
        });
        let started = Instant::now();
        let t =
            DeadlineTransport::new_for_loopback_tests(lease(120), Arc::new(AtomicBool::new(false)))
                .unwrap();
        let result = t.post_json(&url, "{}", Some("synthetic-native-fixture"));
        assert!(result.is_err());
        let closed = closed_rx
            .recv_timeout(Duration::from_millis(500))
            .expect("actual HTTP socket close");
        assert!(closed.duration_since(started) < Duration::from_millis(620));
        server.join().unwrap();
    }
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
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}/", listener.local_addr().unwrap());
    let advance = Arc::new(AtomicU64::new(0));
    let jump = advance.clone();
    let server = std::thread::spawn(move || {
        let (mut s, _) = listener.accept().unwrap();
        s.set_read_timeout(Some(Duration::from_millis(500)))
            .unwrap();
        let mut b = [0; 4096];
        assert!(s.read(&mut b).unwrap() > 0);
        jump.store(60_000, Ordering::SeqCst);
        loop {
            match s.read(&mut b) {
                Ok(0) => break,
                Ok(_) => {}
                Err(e) => panic!("inflight client failed to close after wall jump: {e}"),
            }
        }
    });
    let deadline = AccessDeadline::admit(
        SystemTime::now() + Duration::from_secs(30),
        Arc::new(JumpClock(advance)),
    )
    .unwrap();
    let transport =
        DeadlineTransport::new_for_loopback_tests(deadline, Arc::new(AtomicBool::new(false)))
            .unwrap();
    assert!(transport.post_json(&url, "{}", None).is_err());
    server.join().unwrap();
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
