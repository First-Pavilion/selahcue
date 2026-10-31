//! 17tnw2b9cpm: exercise the real host's pairing action in a child process so
//! inherited stdout AND stderr are observable in actual debug/release builds.
//! No production test flag, profile override, GUI storage or live endpoint is used.

use super::host_test_support::{fresh_controller, fresh_remote, wait_for};
use super::{
    start_remote_control_in, toggle_pairing_in, BindFuture, PairingInvite, ServerEnv, ServerIo,
    TokenDisclosure,
};
use crate::endpoint::test_support::Scratch;
use crate::endpoint::{is_complete_descriptor, json_field};
use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::{CertPin, ControlClient, Role};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Command as ProcessCommand, Stdio};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;

const STREAM_CAP: usize = 128 * 1024;
const CHILD: &str = "pairing_output_tests::child_real_host_pairing_lifecycle";

/// Reintroducing an unconditional print, leaking only a code/link to stderr, or
/// suppressing the debug print must fail this real-stream/profile assertion.
#[test]
fn real_host_pairing_output_respects_actual_build_profile() {
    let scratch = Scratch::new("pairing-output-profile");
    let receipt = scratch.0.join("pairing-receipt.txt");
    let mut child = ProcessCommand::new(std::env::current_exe().expect("test executable"))
        .args(["--exact", CHILD, "--ignored", "--nocapture"])
        .env("SELAHCUE_PAIRING_TEST_RECEIPT", &receipt)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("start the real-host test process");
    let stdout = child.stdout.take().expect("piped stdout");
    let stderr = child.stderr.take().expect("piped stderr");
    let capture = |stream: Box<dyn Read + Send>| {
        std::thread::spawn(move || {
            let mut bytes = Vec::new();
            stream
                .take((STREAM_CAP + 1) as u64)
                .read_to_end(&mut bytes)
                .expect("read child stream");
            bytes
        })
    };
    let out_reader = capture(Box::new(stdout));
    let err_reader = capture(Box::new(stderr));
    let deadline = Instant::now() + Duration::from_secs(120);
    let status = loop {
        if let Some(status) = child.try_wait().expect("poll host child") {
            break status;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            panic!("real-host pairing child exceeded its 120-second bound");
        }
        std::thread::sleep(Duration::from_millis(10));
    };
    let stdout = out_reader.join().expect("stdout reader");
    let stderr = err_reader.join().expect("stderr reader");
    assert!(stdout.len() <= STREAM_CAP && stderr.len() <= STREAM_CAP);
    // Do not echo captured streams: the expected debug fixture carries actual
    // short-lived codes. The private receipt is removed with Scratch on unwind.
    assert!(
        status.success(),
        "real-host lifecycle child failed: {status}"
    );
    let stdout = String::from_utf8(stdout).expect("UTF-8 stdout");
    let stderr = String::from_utf8(stderr).expect("UTF-8 stderr");
    let receipt = std::fs::read_to_string(receipt).expect("private pairing receipt");
    assert!(receipt.len() < 4096);
    let fields: Vec<_> = receipt.lines().collect();
    assert_eq!(fields.len(), 5, "complete bounded lifecycle receipt");
    assert_eq!(
        fields[4],
        "host-started-qr-approval-single-use-withdrawal-ok"
    );
    let pairs = [(fields[0], fields[1]), (fields[2], fields[3])];
    println!(
        "CPM_STREAM_PREMISES debug={} codes_stdout={} invites_stdout={} codes_stderr={} invites_stderr={} lifecycle=true",
        cfg!(debug_assertions),
        pairs.iter().filter(|(code, _)| stdout.contains(*code)).count(),
        pairs.iter().filter(|(_, uri)| stdout.contains(*uri)).count(),
        pairs.iter().filter(|(code, _)| stderr.contains(*code)).count(),
        pairs.iter().filter(|(_, uri)| stderr.contains(*uri)).count(),
    );
    for (code, uri) in pairs {
        assert_eq!(code.len(), 8, "the code must be real, nonempty entropy");
        assert!(uri.starts_with("selahcue://pair?") && uri.contains("&code="));
        assert!(uri.ends_with(code), "the invite carries the offered code");
        assert!(!stderr.contains(code), "pairing code reached stderr");
        assert!(!stderr.contains(uri), "pairing invite reached stderr");
        if cfg!(debug_assertions) {
            assert!(stdout.contains(code), "debug lost the real developer code");
            assert!(stdout.contains(uri), "debug lost the real developer invite");
            assert!(stdout.contains("or enter code:"));
        } else {
            assert!(
                !stdout.contains(code),
                "release stdout exposed the real pairing code"
            );
            assert!(
                !stdout.contains(uri),
                "release stdout exposed the real pairing invite"
            );
            assert!(
                !stdout.contains("selahcue://pair?"),
                "release stdout exposed an invite link"
            );
            assert!(
                stdout.contains("PAIRING MODE"),
                "release lost pairing-on confirmation"
            );
            assert!(
                stdout.contains("QR") && stdout.contains("stage"),
                "release must point to the stage QR"
            );
        }
    }
    assert!(
        stdout.contains("CPM_HOST_LIFECYCLE_OK"),
        "the full child lifecycle ran"
    );
    println!(
        "CPM_PROFILE_CAPTURE_OK debug={} both_streams_checked=true real_host=true codes=2",
        cfg!(debug_assertions)
    );
}

/// Invoked only by the parent's fresh child process, including under --release.
/// It starts the actual host thread/TLS server and invokes the same pairing body
/// as App::toggle_pairing; the only seams are existing hermetic host I/O.
#[test]
#[ignore = "child of the real-host captured-profile test; run by its parent"]
fn child_real_host_pairing_lifecycle() {
    let receipt = PathBuf::from(
        std::env::var_os("SELAHCUE_PAIRING_TEST_RECEIPT").expect("run by the parent only"),
    );
    let scratch = Scratch::new("pairing-real-host");
    let endpoint = scratch.descriptor();
    let controller = fresh_controller();
    let remote = fresh_remote();
    start_remote_control_in(
        controller.clone(),
        remote.clone(),
        ServerEnv {
            warm: Box::new(|| {}),
            io: ServerIo {
                bind: Box::new(|| -> BindFuture { Box::pin(TcpListener::bind("127.0.0.1:0")) }),
                lan_ip: || std::net::IpAddr::from([127, 0, 0, 1]),
                advertise_mdns: false,
                endpoint_file: Some(crate::endpoint::EndpointFile::At(endpoint.clone())),
                banner: Box::new(std::io::stdout()),
                token_disclosure: TokenDisclosure::Redacted,
            },
        },
    );
    wait_for("real TLS listener and private host descriptor", || {
        remote.lan.get().is_some()
            && std::fs::read_to_string(&endpoint).is_ok_and(|text| is_complete_descriptor(&text))
    });
    let descriptor = std::fs::read_to_string(&endpoint).expect("host descriptor");
    let token = json_field(&descriptor, "token").expect("host operator token");
    let (port, pin_hex) = remote.lan.get().expect("real listener").clone();
    let pin = CertPin::from_hex(&pin_hex).expect("real TLS certificate pin");
    let addr = ([127, 0, 0, 1], port).into();
    let before = Instant::now();
    let stage_before = controller
        .lock()
        .expect("controller")
        .stage_output()
        .bytes()
        .to_vec();
    toggle_pairing_in(&controller, &remote);
    let offered_at = Instant::now();
    let code = remote
        .active_code
        .lock()
        .expect("code slot")
        .clone()
        .expect("real offered code");
    assert_eq!(code.len(), 8);
    {
        let mut c = controller.lock().expect("controller");
        assert!(
            c.pairing_qr_active(),
            "the actual toggle must show the stage QR"
        );
        c.tick(offered_at);
        assert_ne!(
            c.stage_output().bytes(),
            stage_before,
            "the stage renders the real QR"
        );
    }
    {
        let reg = remote.registry.blocking_lock();
        assert!(
            reg.code_valid(&code, before + Duration::from_secs(119)),
            "offer remains valid inside120s"
        );
        assert!(
            !reg.code_valid(&code, offered_at + Duration::from_secs(121)),
            "offer expires after120s"
        );
        assert_eq!(
            reg.active_count(),
            1,
            "only the host operator is authenticated"
        );
    }
    let uri = PairingInvite {
        host: super::lan_ip().to_string(),
        port,
        pin_hex: pin_hex.clone(),
        code: code.clone(),
    }
    .to_uri()
    .expect("actual invite fields encode");
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .expect("client runtime");
    runtime.block_on(async {
        let mut operator = ControlClient::connect(addr, "localhost", pin, "operator-shell", token)
            .await.expect("real authenticated host operator");
        let pair_code = code.clone();
        let phone = tokio::spawn(async move {
            ControlClient::pair(addr, "localhost", pin, &pair_code, "CPM test phone", "test")
                .await
        });
        let device = tokio::time::timeout(Duration::from_secs(10), async {
            loop {
                let pending = remote.registry.lock().await.pending_requests(Instant::now());
                if let Some(request) = pending.first() {
                    break request.device_id.0.clone();
                }
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
        }).await.expect("real phone parks pending operator approval");
        assert!(!phone.is_finished(), "a code alone cannot grant access");
        {
            let reg = remote.registry.lock().await;
            assert_eq!(reg.active_count(), 1, "no session before approval");
            assert!(!reg.code_valid(&code, Instant::now()), "first request consumed the single-use code");
        }
        let replay = ControlClient::pair(addr, "localhost", pin, &code, "replay", "test").await;
        assert!(matches!(replay, Err(selahcue_lan::TransportError::Protocol(ref message)) if message.contains("Unauthenticated")), "the consumed code cannot be replayed");
        assert!(matches!(operator.command(Command::ApprovePairing { device_id: device, role: Role::Producer }).await.expect("operator approves"), ServerMessage::RemoteDevices { .. }));
        let (phone, credentials) = tokio::time::timeout(Duration::from_secs(10), phone)
            .await.expect("approval reaches parked phone").expect("phone task").expect("pair approved");
        assert_eq!(phone.role(), Role::Producer);
        assert!(!credentials.token.is_empty());
        assert_eq!(remote.registry.lock().await.active_count(), 2);
        phone.close().await.expect("close phone");
        operator.close().await.expect("close operator");
    });
    // Cancel the first overlay, then offer a second real code and cancel it
    // BEFORE use. This proves withdrawal rather than just testing a spent code.
    toggle_pairing_in(&controller, &remote);
    assert!(!controller.lock().expect("controller").pairing_qr_active());
    toggle_pairing_in(&controller, &remote);
    let second = remote
        .active_code
        .lock()
        .expect("second slot")
        .clone()
        .expect("second actual code");
    assert_ne!(code, second, "fresh toggle offers new entropy");
    assert!(remote
        .registry
        .blocking_lock()
        .code_valid(&second, Instant::now()));
    let second_uri = PairingInvite {
        host: super::lan_ip().to_string(),
        port,
        pin_hex,
        code: second.clone(),
    }
    .to_uri()
    .expect("second invite encodes");
    toggle_pairing_in(&controller, &remote);
    assert!(!controller.lock().expect("controller").pairing_qr_active());
    assert!(remote.active_code.lock().expect("withdrawn slot").is_none());
    assert!(
        !remote
            .registry
            .blocking_lock()
            .code_valid(&second, Instant::now()),
        "cancelled unused code is withdrawn immediately"
    );
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut receipt = options.open(receipt).expect("private synthetic receipt");
    writeln!(
        receipt,
        "{code}\n{uri}\n{second}\n{second_uri}\nhost-started-qr-approval-single-use-withdrawal-ok"
    )
    .expect("write private synthetic receipt");
    println!("CPM_HOST_LIFECYCLE_OK startup=tls pairing=real stage=qr single_use=true approval=required withdrawal=true");
}
