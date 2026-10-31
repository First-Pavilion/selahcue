//! Real bounded credential recorder shared only by cloud/licensing/operator tests.
//! A successful client response means the complete request was recorded before reply.
use std::io::{Read, Write};
use std::net::TcpListener;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

pub struct Receiver {
    pub base: String,
    stop: Arc<AtomicBool>,
    worker: Option<JoinHandle<Vec<String>>>,
}

impl Receiver {
    pub fn start() -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind recorder");
        listener
            .set_nonblocking(true)
            .expect("nonblocking recorder");
        let base = format!(
            "http://{}",
            listener.local_addr().expect("recorder address")
        );
        let stop = Arc::new(AtomicBool::new(false));
        let stopping = Arc::clone(&stop);
        let worker = thread::spawn(move || {
            let mut seen = Vec::new();
            let deadline = Instant::now() + Duration::from_secs(10);
            while Instant::now() < deadline && seen.len() < 8 {
                let mut socket = match listener.accept() {
                    Ok((socket, _)) => socket,
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        if stopping.load(Ordering::SeqCst) {
                            break;
                        }
                        thread::sleep(Duration::from_millis(2));
                        continue;
                    }
                    Err(e) => panic!("recorder accept: {e}"),
                };
                socket
                    .set_read_timeout(Some(Duration::from_secs(2)))
                    .expect("read deadline");
                let mut bytes = Vec::new();
                let mut chunk = [0u8; 1024];
                while bytes.len() < 16 * 1024 {
                    let n = socket.read(&mut chunk).expect("read request");
                    if n == 0 {
                        break;
                    }
                    bytes.extend_from_slice(&chunk[..n]);
                    if let Some(end) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
                        let length = String::from_utf8_lossy(&bytes[..end])
                            .lines()
                            .find_map(|line| {
                                line.to_ascii_lowercase()
                                    .strip_prefix("content-length:")?
                                    .trim()
                                    .parse::<usize>()
                                    .ok()
                            })
                            .unwrap_or(0);
                        if bytes.len() >= end + 4 + length {
                            break;
                        }
                    }
                }
                seen.push(String::from_utf8(bytes).expect("UTF8 request"));
                socket.write_all(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}").expect("recorder reply");
            }
            seen
        });
        Self {
            base,
            stop,
            worker: Some(worker),
        }
    }
    pub fn finish(mut self) -> Vec<String> {
        self.stop.store(true, Ordering::SeqCst);
        self.worker
            .take()
            .expect("worker")
            .join()
            .expect("recorder thread")
    }
}
impl Drop for Receiver {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
