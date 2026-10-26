//! A malformed inbound frame never puts the value it choked on into a `TransportError`
//! (FR-082, ClickUp 17tnw2b9aec).
//!
//! serde quotes the offending VALUE in its message for a wrongly-typed field
//! (`invalid type: string "SECRET sermon words", expected a sequence`) and for an unknown enum
//! variant (``unknown variant `SECRET`, expected one of ...``). `TransportError::Json` used to
//! carry that `serde_json::Error` whole, so `Display` ("json error: ...") and the derived `Debug`
//! both printed it, and any caller that logs the error or returns it to the UI carried the quoted
//! text. The text can be a sermon transcript (a field of the operator's state frame), a device
//! token, or anything else a version-skewed, buggy or hostile peer put in the wrong field.
//!
//! The fix keeps only what is safe to repeat: the category (syntax, data, eof, io) and the line and
//! column, in a type that cannot hold the message. These tests pin that from two directions:
//!
//! - **Every inbound frame shape**, parsed with the same function the transport uses
//!   (`protocol::from_json`) and converted the same way (`TransportError::from`), with a planted
//!   secret in a mistyped field. `Display`, `Debug` and the whole `source()` chain must not
//!   contain it, and the error must still say it is a JSON failure and where.
//! - **The real transport**: a hostile host answering a real `ControlClient` (`connect`, `pair`,
//!   `command`), and a hostile controller sending a real `ControlServer` a bad `Hello`, so the
//!   claim is about what a caller of the public API receives, not only about a conversion.
//!
//! Every case has a premise check: serde's OWN error for the same frame does contain the secret,
//! in both `Display` and `Debug`. Without it a fixture that stopped being malformed in the way
//! it claims would make every assertion below pass for nothing.

#![cfg(feature = "server")]
#![allow(clippy::unwrap_used)]

use futures_util::{SinkExt, StreamExt};
use selahcue_lan::protocol::{
    from_json, AuthResponse, Command, Hello, PairResponse, Request, ServerMessage,
};
use selahcue_lan::server::{Handler, Reply};
use selahcue_lan::session::SessionRegistry;
use selahcue_lan::{
    client_config, server_config, CertPin, ControlClient, ControlServer, JsonFailureKind,
    SelfSigned, TransportError,
};
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Mutex;
use tokio_rustls::{TlsAcceptor, TlsConnector};
use tokio_tungstenite::tungstenite::Message;

/// Recognisable, and long enough that no fixed-wording message can contain it by accident.
const SECRET: &str = "SECRET-SERMON-WORDS-9f3a-do-not-log";

/// For the cases where the planted value is a NUMBER: serde quotes integers and floats too, in
/// backticks (``invalid value: integer `-4815162342`, expected u64``), so a number in the wrong
/// field is a leak of the same kind.
const NUMERIC_SECRET: &str = "4815162342";

/// Everything a `TransportError` can show a person or a log, plus its `source()` chain.
fn renderings(err: &TransportError) -> Vec<(&'static str, String)> {
    let mut out = vec![
        ("Display", err.to_string()),
        ("Debug", format!("{err:?}")),
        ("alternate Debug", format!("{err:#?}")),
    ];
    let mut source = std::error::Error::source(err);
    while let Some(cause) = source {
        out.push(("source Display", cause.to_string()));
        out.push(("source Debug", format!("{cause:?}")));
        source = cause.source();
    }
    out
}

/// The planted value and the shorter distinctive fragments of it that must not appear either. A
/// check for the whole value alone cannot see a leak of a PREFIX of the message (a mutant that
/// appended the first 22 characters of serde's text leaked `SECRE` of an unknown-variant value and
/// passed every whole-value assertion).
fn forbidden_fragments(secret: &str) -> Vec<&str> {
    let fragments: &[&str] = match secret {
        SECRET => &["SECR", "SERMON", "9f3a"],
        NUMERIC_SECRET => &["4815", "162342"],
        _ => &[],
    };
    for fragment in fragments {
        assert!(
            secret.contains(fragment),
            "`{fragment}` is not part of `{secret}`"
        );
    }
    let mut all = vec![secret];
    all.extend_from_slice(fragments);
    all
}

/// The first rendering of `err` that contains `secret` or a distinctive fragment of it, if any.
fn find_leak(what: &str, err: &TransportError, secret: &str) -> Option<String> {
    let forbidden = forbidden_fragments(secret);
    renderings(err).into_iter().find_map(|(how, text)| {
        forbidden
            .iter()
            .find(|piece| text.contains(**piece))
            .map(|piece| {
                format!("{what}: the {how} of the error quotes the frame (`{piece}`): {text}")
            })
    })
}

fn assert_no_secret(what: &str, err: &TransportError, secret: &str) {
    if let Some(leak) = find_leak(what, err, secret) {
        panic!("{leak}");
    }
}

/// What is wrong, if anything, with the error's diagnostic value: it should still say it is a
/// JSON failure, and say where when serde knows where.
///
/// serde reports line 0 and column 0 when it has no position, which is the case for a data error
/// inside an internally tagged enum (serde buffers the content first): `ServerMessage`,
/// `AuthResponse`, `PairResponse`, `Hello` and `Command` are all tagged, so most shape errors have
/// none. Such an error must say so, not print `line 0 column 0` as if it were a place.
fn diagnostic_problem(what: &str, err: &TransportError, raw: &serde_json::Error) -> Option<String> {
    let shown = err.to_string();
    if !shown.starts_with("json error: ") {
        return Some(format!(
            "{what}: the error should still say it is a JSON failure: {shown}"
        ));
    }
    if raw.line() == 0 {
        if !shown.contains("(no position)") || shown.contains("line 0") {
            return Some(format!(
                "{what}: serde has no position, so the error should say `(no position)` and not a line 0: {shown}"
            ));
        }
        return None;
    }
    let position = format!("at line {} column {}", raw.line(), raw.column());
    if !shown.contains(&position) {
        return Some(format!(
            "{what}: the error should still say where (`{position}`): {shown}"
        ));
    }
    None
}

/// One inbound frame shape with a planted secret in a field of the wrong type (or in a variant
/// name that does not exist), and a function that parses it as the type the transport expects.
struct Case {
    name: &'static str,
    frame: String,
    /// The planted value that no rendering of the error may contain.
    secret: &'static str,
    parse: fn(&str) -> Result<(), serde_json::Error>,
}

fn parse_as<T: serde::de::DeserializeOwned>(frame: &str) -> Result<(), serde_json::Error> {
    from_json::<T>(frame).map(|_| ())
}

fn cases() -> Vec<Case> {
    vec![
        // The ticket's own reproduction: the operator's state frame with a transcript that is a
        // string where a list of segments belongs.
        Case {
            name: "ServerMessage::OperatorState, transcript is a string",
            frame: format!(
                r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":"{SECRET}"}}}}"#
            ),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::OperatorState, a transcript segment's start_ms is a string",
            frame: format!(
                r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{{"id":1,"start_ms":"{SECRET}","end_ms":2,"text":"hello"}}]}}}}"#
            ),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::State, live_item is a string",
            frame: format!(r#"{{"event":"state","live_item":"{SECRET}","blackout":false}}"#),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::Ack, request_id is a string",
            frame: format!(r#"{{"event":"ack","request_id":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::Denied, reason is an unknown variant",
            frame: format!(r#"{{"event":"denied","request_id":1,"reason":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage, the event tag is an unknown variant",
            frame: format!(r#"{{"event":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "AuthResponse::Granted, role is an unknown variant",
            frame: format!(r#"{{"auth":"granted","role":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<AuthResponse>,
        },
        Case {
            name: "PairResponse::Granted, role is an unknown variant",
            frame: format!(r#"{{"pair":"granted","device_id":"d","token":"t","role":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<PairResponse>,
        },
        Case {
            name: "PairResponse::Rejected, reason is an unknown variant",
            frame: format!(r#"{{"pair":"rejected","reason":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<PairResponse>,
        },
        Case {
            name: "Hello::Auth, v is a string",
            frame: format!(r#"{{"hello":"auth","v":"{SECRET}","device_id":"d","token":"t"}}"#),
            secret: SECRET,
            parse: parse_as::<Hello>,
        },
        Case {
            name: "Hello, the hello tag is an unknown variant",
            frame: format!(r#"{{"hello":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<Hello>,
        },
        Case {
            name: "Request, request_id is a string",
            frame: format!(r#"{{"v":2,"request_id":"{SECRET}","command":{{"cmd":"get_state"}}}}"#),
            secret: SECRET,
            parse: parse_as::<Request>,
        },
        Case {
            name: "Command, the cmd tag is an unknown variant",
            frame: format!(r#"{{"cmd":"{SECRET}"}}"#),
            secret: SECRET,
            parse: parse_as::<Command>,
        },
        // The pairing hello: the code is a credential too (single-use, but live until redeemed).
        Case {
            name: "Hello::Pair, v is a string",
            frame: format!(
                r#"{{"hello":"pair","v":"{SECRET}","code":"c","device_name":"p","platform":"a"}}"#
            ),
            secret: SECRET,
            parse: parse_as::<Hello>,
        },
        Case {
            name: "Hello::Pair, code is a number",
            frame: format!(
                r#"{{"hello":"pair","v":2,"code":{NUMERIC_SECRET},"device_name":"p","platform":"a"}}"#
            ),
            secret: NUMERIC_SECRET,
            parse: parse_as::<Hello>,
        },
        // Numbers are quoted too, in backticks, in three different serde messages.
        Case {
            name: "ServerMessage::Ack, request_id is a negative integer",
            frame: format!(r#"{{"event":"ack","request_id":-{NUMERIC_SECRET}}}"#),
            secret: NUMERIC_SECRET,
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::Ack, request_id is a float",
            frame: format!(r#"{{"event":"ack","request_id":{NUMERIC_SECRET}.5}}"#),
            secret: NUMERIC_SECRET,
            parse: parse_as::<ServerMessage>,
        },
    ]
}

#[test]
fn a_valid_frame_of_each_shape_still_parses_so_the_cases_are_malformed_only_where_planted() {
    // The control for the table below: the same shapes, unbroken, are accepted.
    from_json::<ServerMessage>(r#"{"event":"state","live_item":3,"blackout":false}"#).unwrap();
    from_json::<ServerMessage>(r#"{"event":"ack","request_id":1}"#).unwrap();
    from_json::<AuthResponse>(r#"{"auth":"granted","role":"producer"}"#).unwrap();
    from_json::<PairResponse>(
        r#"{"pair":"granted","device_id":"d","token":"t","role":"producer"}"#,
    )
    .unwrap();
    from_json::<Hello>(r#"{"hello":"auth","v":2,"device_id":"d","token":"t"}"#).unwrap();
    from_json::<Hello>(r#"{"hello":"pair","v":2,"code":"c","device_name":"p","platform":"a"}"#)
        .unwrap();
    from_json::<Request>(r#"{"v":2,"request_id":1,"command":{"cmd":"get_state"}}"#).unwrap();
    from_json::<ServerMessage>(
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{"id":1,"start_ms":0,"end_ms":2,"text":"hello"}]}}"#,
    )
    .unwrap();
}

#[test]
fn a_mistyped_field_of_every_inbound_frame_shape_never_reaches_the_transport_error() {
    // Every case is checked and every failure is reported together, so a regression shows which
    // shapes it touches rather than only the first.
    let mut failures = Vec::new();
    let all = cases();
    assert!(all.len() >= 17, "the table has shrunk: {} cases", all.len());
    for case in all {
        let raw = (case.parse)(&case.frame)
            .expect_err(&format!("{}: the fixture should be malformed", case.name));

        // PREMISE: serde itself quotes the secret, in both renderings. If it stops doing so for
        // this frame the fixture is no longer exercising the leak and the checks below prove
        // nothing.
        assert!(
            raw.to_string().contains(case.secret) && format!("{raw:?}").contains(case.secret),
            "{}: premise broken, serde no longer quotes the value: {raw}",
            case.name
        );

        // This is exactly what `recv_json` does with the parse failure.
        let err = TransportError::from(raw);
        let raw_again = (case.parse)(&case.frame).unwrap_err();
        failures.extend(find_leak(case.name, &err, case.secret));
        failures.extend(diagnostic_problem(case.name, &err, &raw_again));
    }
    assert!(
        failures.is_empty(),
        "{} case(s) failed:\n{}",
        failures.len(),
        failures.join("\n")
    );
}

/// The `JsonFailure` inside the error the transport would return for `frame` parsed as `T`, and
/// the text a person would read.
fn failure_of<T: serde::de::DeserializeOwned>(frame: &str) -> (selahcue_lan::JsonFailure, String) {
    let Err(raw) = from_json::<T>(frame) else {
        panic!("`{frame}` should not parse");
    };
    let err = TransportError::from(raw);
    let text = err.to_string();
    match err {
        TransportError::Json(f) => (f, text),
        other => panic!("not a Json error: {other:?}"),
    }
}

#[test]
fn each_category_keeps_its_kind_its_wording_and_a_position_where_serde_has_one() {
    // The category is carried and stated, in words of our own. Asserted on the kind itself AND on
    // the exact wording, so a swapped mapping and a single sentence for every kind both fail.

    // A truncated frame: serde knows where.
    let (f, text) = failure_of::<ServerMessage>(r#"{"event":"state","live_item":"#);
    assert_eq!(f.kind(), JsonFailureKind::Eof);
    assert!(text.contains("ended early"), "{text}");
    assert!(f.line() >= 1 && f.column() >= 1, "{f:?}");
    assert!(
        text.contains(&format!("at line {} column {}", f.line(), f.column())),
        "{text}"
    );

    // Not JSON at all: serde knows where.
    let (f, text) = failure_of::<ServerMessage>(r#"{"event": state}"#);
    assert_eq!(f.kind(), JsonFailureKind::Syntax);
    assert!(text.contains("not valid JSON"), "{text}");
    assert!(f.line() >= 1 && f.column() >= 1, "{f:?}");
    assert!(
        text.contains(&format!("at line {} column {}", f.line(), f.column())),
        "{text}"
    );

    // A wrong shape in a plain struct: serde knows where.
    let (f, text) =
        failure_of::<Request>(r#"{"v":2,"request_id":"x","command":{"cmd":"get_state"}}"#);
    assert_eq!(f.kind(), JsonFailureKind::Data);
    assert!(text.contains("did not have the shape"), "{text}");
    assert!(f.line() >= 1 && f.column() >= 1, "{f:?}");
    assert!(
        text.contains(&format!("at line {} column {}", f.line(), f.column())),
        "{text}"
    );
}

#[test]
fn a_shape_error_inside_a_tagged_enum_says_it_has_no_position_instead_of_line_0() {
    // serde buffers the content of an internally tagged enum before it knows the variant, so a
    // data error inside one carries no position (line 0, column 0). The ticket's own frame is
    // such a case: an operator-state frame whose transcript is a string. 72% of the malformed
    // frames QA mutated were of this kind, so printing `line 0 column 0` would send a reader
    // looking for a place that does not exist.
    let frame = format!(
        r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":"{SECRET}"}}}}"#
    );
    let raw = from_json::<ServerMessage>(&frame).unwrap_err();
    // PREMISE: serde really has no position here. If a serde upgrade starts reporting one, this
    // test says so instead of passing on a case that no longer exercises the wording.
    assert_eq!((raw.line(), raw.column()), (0, 0), "{raw}");

    let (f, text) = failure_of::<ServerMessage>(&frame);
    assert_eq!(f.kind(), JsonFailureKind::Data);
    assert!(text.starts_with("json error: "), "{text}");
    assert!(text.contains("did not have the shape"), "{text}");
    assert!(text.contains("(no position)"), "{text}");
    assert!(
        !text.contains("line 0") && !text.contains("column 0"),
        "{text}"
    );
    // The numbers stay in the type for anyone who wants them.
    assert_eq!((f.line(), f.column()), (0, 0));
}

#[test]
fn an_io_failure_is_its_own_kind_and_quotes_nothing_from_the_reader() {
    // The `Io` category cannot come from parsing a string, but it can come from `serde_json`
    // reading a stream, and the mapping is total, so it is exercised here with a reader whose
    // error carries the secret. serde would print that error's text.
    struct Failing;
    impl std::io::Read for Failing {
        fn read(&mut self, _buf: &mut [u8]) -> std::io::Result<usize> {
            Err(std::io::Error::other(SECRET))
        }
    }
    let raw = serde_json::from_reader::<_, ServerMessage>(Failing).unwrap_err();
    assert!(
        raw.is_io() && raw.to_string().contains(SECRET),
        "premise: {raw}"
    );

    let err = TransportError::from(raw);
    assert_no_secret("an io failure", &err, SECRET);
    let TransportError::Json(f) = &err else {
        panic!("not a Json error: {err:?}");
    };
    assert_eq!(f.kind(), JsonFailureKind::Io);
    assert!(err.to_string().contains("could not be read"), "{err}");
}

// ---------------------------------------------------------------------------
// The real transport
// ---------------------------------------------------------------------------

/// A host that speaks TLS and WebSocket like the real one, but answers each incoming text frame
/// with the next scripted reply. Returns its address and the pin a client must trust.
async fn hostile_host(replies: Vec<String>) -> (SocketAddr, CertPin) {
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let acceptor = TlsAcceptor::from(Arc::new(server_config(&identity).unwrap()));
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        let Ok((tcp, _)) = listener.accept().await else {
            return;
        };
        let Ok(tls) = acceptor.accept(tcp).await else {
            return;
        };
        let Ok(mut ws) = tokio_tungstenite::accept_async(tls).await else {
            return;
        };
        for reply in replies {
            // Wait for the client's frame (its Hello or its Request), then answer it.
            match tokio::time::timeout(Duration::from_secs(5), ws.next()).await {
                Ok(Some(Ok(Message::Text(_)))) => {}
                _ => return,
            }
            if ws.send(Message::text(reply)).await.is_err() {
                return;
            }
        }
        // Hold the socket open long enough for the client to read the last reply.
        tokio::time::sleep(Duration::from_secs(5)).await;
    });
    (addr, pin)
}

/// Build the hostile frame for a real-transport case, after checking its premise: parsed as the
/// type the transport expects, it fails, and serde's own error quotes the secret in both
/// renderings. Checked BEFORE the transport is involved, so a fixture that stopped being
/// malformed fails here with the reason, not later as a confusing success.
fn hostile_frame<T: serde::de::DeserializeOwned>(frame: String) -> String {
    let Err(raw) = from_json::<T>(&frame) else {
        panic!("the hostile frame should not parse");
    };
    assert!(
        raw.to_string().contains(SECRET) && format!("{raw:?}").contains(SECRET),
        "premise broken, serde no longer quotes the value: {raw}"
    );
    frame
}

/// A bound on every client call in these tests: `ControlClient::pair` alone is capped only by its
/// 150 s pairing timeout, so a regression must fail quickly instead of hanging the suite.
async fn within_ten_seconds<F: std::future::Future>(what: &str, future: F) -> F::Output {
    tokio::time::timeout(Duration::from_secs(10), future)
        .await
        .unwrap_or_else(|_| panic!("{what} did not return within 10 s"))
}

#[tokio::test]
async fn a_hostile_auth_reply_does_not_reach_the_error_connect_returns() {
    let frame = hostile_frame::<AuthResponse>(format!(r#"{{"auth":"granted","role":"{SECRET}"}}"#));
    let (addr, pin) = hostile_host(vec![frame]).await;

    let err = match within_ten_seconds(
        "connect",
        ControlClient::connect(addr, "localhost", pin, "dev", "tok"),
    )
    .await
    {
        Err(e) => e,
        Ok(_) => panic!("a malformed auth reply must not authenticate"),
    };

    assert_no_secret("real transport", &err, SECRET);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
    assert!(err.to_string().starts_with("json error: "), "{err}");
}

#[tokio::test]
async fn a_hostile_pairing_reply_does_not_reach_the_error_pair_returns() {
    let frame = hostile_frame::<PairResponse>(format!(
        r#"{{"pair":"granted","device_id":"d","token":"t","role":"{SECRET}"}}"#
    ));
    let (addr, pin) = hostile_host(vec![frame]).await;

    let err = match within_ten_seconds(
        "pair",
        ControlClient::pair(addr, "localhost", pin, "code", "phone", "android"),
    )
    .await
    {
        Err(e) => e,
        Ok(_) => panic!("a malformed pairing reply must not pair"),
    };

    assert_no_secret("real transport", &err, SECRET);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
}

#[tokio::test]
async fn a_hostile_command_reply_does_not_reach_the_error_command_returns() {
    // The ticket's own scenario: an operator-state frame whose transcript is a string.
    let frame = hostile_frame::<ServerMessage>(format!(
        r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":"{SECRET}"}}}}"#
    ));
    let (addr, pin) = hostile_host(vec![
        r#"{"auth":"granted","role":"producer"}"#.to_string(),
        frame,
    ])
    .await;
    let mut client = within_ten_seconds(
        "connect",
        ControlClient::connect(addr, "localhost", pin, "dev", "tok"),
    )
    .await
    .expect("a well-formed auth reply connects");

    let err = within_ten_seconds("command", client.command(Command::GetOperatorState))
        .await
        .expect_err("a malformed state frame is an error");

    assert_no_secret("real transport", &err, SECRET);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
    assert!(err.to_string().starts_with("json error: "), "{err}");
}

#[tokio::test]
async fn a_hostile_hello_does_not_reach_the_error_the_server_returns() {
    // The host's side: an untrusted LAN peer sends the first frame. `serve_connection` returns
    // the error to whoever runs the accept loop, which logs it.
    let identity = SelfSigned::generate(vec!["localhost".into()]).unwrap();
    let pin = identity.pin;
    let handler: Handler = Arc::new(|_role, _cmd| Reply::Ack);
    let server = Arc::new(
        ControlServer::new(
            &identity,
            Arc::new(Mutex::new(SessionRegistry::new())),
            handler,
        )
        .unwrap()
        .with_handshake_timeout(Duration::from_secs(10)),
    );
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let serving = tokio::spawn({
        let server = Arc::clone(&server);
        async move {
            let (tcp, _) = listener.accept().await.unwrap();
            server.serve_connection(tcp).await
        }
    });

    let frame = hostile_frame::<Hello>(format!(
        r#"{{"hello":"auth","v":"{SECRET}","device_id":"d","token":"t"}}"#
    ));
    let tcp = TcpStream::connect(addr).await.unwrap();
    let connector = TlsConnector::from(Arc::new(client_config(pin).unwrap()));
    let dns = rustls::pki_types::ServerName::try_from("localhost".to_string()).unwrap();
    let tls = connector.connect(dns, tcp).await.unwrap();
    let (mut ws, _) = tokio_tungstenite::client_async("wss://localhost/", tls)
        .await
        .unwrap();
    ws.send(Message::text(frame)).await.unwrap();

    let err = tokio::time::timeout(Duration::from_secs(10), serving)
        .await
        .expect("the server should give up on a malformed hello")
        .unwrap()
        .expect_err("a malformed hello is an error");

    assert_no_secret("real transport", &err, SECRET);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
}
