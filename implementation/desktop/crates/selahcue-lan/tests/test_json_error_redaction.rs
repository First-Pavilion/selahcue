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
    client_config, server_config, CertPin, ControlClient, ControlServer, SelfSigned, TransportError,
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

fn assert_no_secret(what: &str, err: &TransportError) {
    for (how, text) in renderings(err) {
        assert!(
            !text.contains(SECRET) && !text.contains("SECRET"),
            "{what}: the {how} of the error quotes the frame: {text}"
        );
    }
}

/// The error still says what it is and where: a JSON failure at serde's own line and column.
fn assert_names_a_json_failure_and_its_position(
    what: &str,
    err: &TransportError,
    raw: &serde_json::Error,
) {
    let shown = err.to_string();
    assert!(
        shown.starts_with("json error: "),
        "{what}: the error should still say it is a JSON failure: {shown}"
    );
    let position = format!("line {} column {}", raw.line(), raw.column());
    assert!(
        shown.contains(&position),
        "{what}: the error should still say where (`{position}`): {shown}"
    );
}

/// One inbound frame shape with a planted secret in a field of the wrong type (or in a variant
/// name that does not exist), and a function that parses it as the type the transport expects.
struct Case {
    name: &'static str,
    frame: String,
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
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::OperatorState, a transcript segment's start_ms is a string",
            frame: format!(
                r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{{"id":1,"start_ms":"{SECRET}","end_ms":2,"text":"hello"}}]}}}}"#
            ),
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::State, live_item is a string",
            frame: format!(r#"{{"event":"state","live_item":"{SECRET}","blackout":false}}"#),
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::Ack, request_id is a string",
            frame: format!(r#"{{"event":"ack","request_id":"{SECRET}"}}"#),
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage::Denied, reason is an unknown variant",
            frame: format!(r#"{{"event":"denied","request_id":1,"reason":"{SECRET}"}}"#),
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "ServerMessage, the event tag is an unknown variant",
            frame: format!(r#"{{"event":"{SECRET}"}}"#),
            parse: parse_as::<ServerMessage>,
        },
        Case {
            name: "AuthResponse::Granted, role is an unknown variant",
            frame: format!(r#"{{"auth":"granted","role":"{SECRET}"}}"#),
            parse: parse_as::<AuthResponse>,
        },
        Case {
            name: "PairResponse::Granted, role is an unknown variant",
            frame: format!(r#"{{"pair":"granted","device_id":"d","token":"t","role":"{SECRET}"}}"#),
            parse: parse_as::<PairResponse>,
        },
        Case {
            name: "PairResponse::Rejected, reason is an unknown variant",
            frame: format!(r#"{{"pair":"rejected","reason":"{SECRET}"}}"#),
            parse: parse_as::<PairResponse>,
        },
        Case {
            name: "Hello::Auth, v is a string",
            frame: format!(r#"{{"hello":"auth","v":"{SECRET}","device_id":"d","token":"t"}}"#),
            parse: parse_as::<Hello>,
        },
        Case {
            name: "Hello, the hello tag is an unknown variant",
            frame: format!(r#"{{"hello":"{SECRET}"}}"#),
            parse: parse_as::<Hello>,
        },
        Case {
            name: "Request, request_id is a string",
            frame: format!(r#"{{"v":2,"request_id":"{SECRET}","command":{{"cmd":"get_state"}}}}"#),
            parse: parse_as::<Request>,
        },
        Case {
            name: "Command, the cmd tag is an unknown variant",
            frame: format!(r#"{{"cmd":"{SECRET}"}}"#),
            parse: parse_as::<Command>,
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
    from_json::<Request>(r#"{"v":2,"request_id":1,"command":{"cmd":"get_state"}}"#).unwrap();
    from_json::<ServerMessage>(
        r#"{"event":"operator_state","view":{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":[{"id":1,"start_ms":0,"end_ms":2,"text":"hello"}]}}"#,
    )
    .unwrap();
}

#[test]
fn a_mistyped_field_of_every_inbound_frame_shape_never_reaches_the_transport_error() {
    for case in cases() {
        let raw = (case.parse)(&case.frame)
            .expect_err(&format!("{}: the fixture should be malformed", case.name));

        // PREMISE: serde itself quotes the secret, in both renderings. If it stops doing so for
        // this frame the fixture is no longer exercising the leak and the checks below prove
        // nothing.
        assert!(
            raw.to_string().contains(SECRET) && format!("{raw:?}").contains(SECRET),
            "{}: premise broken, serde no longer quotes the value: {raw}",
            case.name
        );

        // This is exactly what `recv_json` does with the parse failure.
        let err = TransportError::from(raw);
        let raw_again = (case.parse)(&case.frame).unwrap_err();
        assert_no_secret(case.name, &err);
        assert_names_a_json_failure_and_its_position(case.name, &err, &raw_again);
    }
}

#[test]
fn a_syntax_failure_and_a_truncated_frame_keep_their_category_and_position() {
    // Not every failure quotes a value; these must stay as useful as they were.
    let cut = r#"{"event":"state","live_item":"#;
    let raw = from_json::<ServerMessage>(cut).unwrap_err();
    let (line, column) = (raw.line(), raw.column());
    let err = TransportError::from(raw);
    let shown = err.to_string();
    assert!(
        shown.starts_with("json error: ")
            && shown.contains(&format!("line {line} column {column}")),
        "a truncated frame: {shown}"
    );

    let broken = r#"{"event": state}"#;
    let raw = from_json::<ServerMessage>(broken).unwrap_err();
    let (line, column) = (raw.line(), raw.column());
    let shown = TransportError::from(raw).to_string();
    assert!(
        shown.contains(&format!("line {line} column {column}")),
        "a syntax error: {shown}"
    );

    // The category is stated, in words of our own, and the two differ.
    let truncated = TransportError::from(from_json::<ServerMessage>(cut).unwrap_err()).to_string();
    let syntax = TransportError::from(from_json::<ServerMessage>(broken).unwrap_err()).to_string();
    let data = TransportError::from(
        from_json::<ServerMessage>(r#"{"event":"ack","request_id":"x"}"#).unwrap_err(),
    )
    .to_string();
    assert_ne!(truncated, syntax);
    assert_ne!(syntax, data);
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

fn secret_in(frame: &str, err: &TransportError) {
    // PREMISE of each end-to-end case: the frame the host sent really does carry the secret.
    assert!(frame.contains(SECRET));
    assert_no_secret("real transport", err);
}

#[tokio::test]
async fn a_hostile_auth_reply_does_not_reach_the_error_connect_returns() {
    let frame = format!(r#"{{"auth":"granted","role":"{SECRET}"}}"#);
    let (addr, pin) = hostile_host(vec![frame.clone()]).await;

    let err = match ControlClient::connect(addr, "localhost", pin, "dev", "tok").await {
        Err(e) => e,
        Ok(_) => panic!("a malformed auth reply must not authenticate"),
    };

    secret_in(&frame, &err);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
    assert!(err.to_string().starts_with("json error: "), "{err}");
}

#[tokio::test]
async fn a_hostile_pairing_reply_does_not_reach_the_error_pair_returns() {
    let frame = format!(r#"{{"pair":"granted","device_id":"d","token":"t","role":"{SECRET}"}}"#);
    let (addr, pin) = hostile_host(vec![frame.clone()]).await;

    let err = match ControlClient::pair(addr, "localhost", pin, "code", "phone", "android").await {
        Err(e) => e,
        Ok(_) => panic!("a malformed pairing reply must not pair"),
    };

    secret_in(&frame, &err);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
}

#[tokio::test]
async fn a_hostile_command_reply_does_not_reach_the_error_command_returns() {
    // The ticket's own scenario: an operator-state frame whose transcript is a string.
    let frame = format!(
        r#"{{"event":"operator_state","view":{{"plan_name":"Sunday","items":[],"live_index":null,"staged_index":null,"blackout":false,"timer":null,"transcript":"{SECRET}"}}}}"#
    );
    let (addr, pin) = hostile_host(vec![
        r#"{"auth":"granted","role":"producer"}"#.to_string(),
        frame.clone(),
    ])
    .await;
    let mut client = ControlClient::connect(addr, "localhost", pin, "dev", "tok")
        .await
        .expect("a well-formed auth reply connects");

    let err = client
        .command(Command::GetOperatorState)
        .await
        .expect_err("a malformed state frame is an error");

    secret_in(&frame, &err);
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

    let frame = format!(r#"{{"hello":"auth","v":"{SECRET}","device_id":"d","token":"t"}}"#);
    let tcp = TcpStream::connect(addr).await.unwrap();
    let connector = TlsConnector::from(Arc::new(client_config(pin).unwrap()));
    let dns = rustls::pki_types::ServerName::try_from("localhost".to_string()).unwrap();
    let tls = connector.connect(dns, tcp).await.unwrap();
    let (mut ws, _) = tokio_tungstenite::client_async("wss://localhost/", tls)
        .await
        .unwrap();
    ws.send(Message::text(frame.clone())).await.unwrap();

    let err = tokio::time::timeout(Duration::from_secs(10), serving)
        .await
        .expect("the server should give up on a malformed hello")
        .unwrap()
        .expect_err("a malformed hello is an error");

    secret_in(&frame, &err);
    assert!(matches!(err, TransportError::Json(_)), "{err:?}");
}
