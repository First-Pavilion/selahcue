//! Source guard for FR-082 (17tnw2axppb): a `TransportError::Protocol` message in the operator
//! process must never be built with `Debug` formatting, and `RemoteOperator` must read every
//! host reply through the redacting `operator_reply::expect_*` functions.
//!
//! Why a source scan on top of the behavioural tests: `ServerMessage` derives `Debug`, and a
//! `{other:?}` in a `format!` compiles, passes every test that never sends that branch a
//! secret-bearing reply, and looks exactly like the pattern the other branches used for years.
//! The behavioural tests (`src/operator_reply.rs`, `test_operator_reply_redaction.rs`) prove the
//! CURRENT branches; this guard is what makes the NEXT branch fail the build rather than rely on
//! its author remembering. It is a tripwire, not a proof (it cannot see a `Debug` dump built
//! some other way), which is why it has positive controls below: a guard that cannot fail
//! guards nothing.

#![allow(clippy::unwrap_used)]

use std::path::{Path, PathBuf};

/// Remove whole-line `//`, `///` and `//!` comments: the stale-comment text that QUOTES the old
/// pattern (to explain it) is not code.
fn strip_line_comments(src: &str) -> String {
    src.lines()
        .filter(|l| !l.trim_start().starts_with("//"))
        .collect::<Vec<_>>()
        .join("\n")
}

/// The text of the balanced `( ... )` argument list opening at `open` (an index of a `(`),
/// skipping string literals so parentheses inside a format string do not unbalance it.
fn balanced_args(src: &str, open: usize) -> &str {
    let bytes = src.as_bytes();
    let mut depth = 0usize;
    let mut i = open;
    while i < bytes.len() {
        match bytes[i] {
            b'"' => {
                i += 1;
                while i < bytes.len() && bytes[i] != b'"' {
                    if bytes[i] == b'\\' {
                        i += 1;
                    }
                    i += 1;
                }
            }
            b'(' => depth += 1,
            b')' => {
                depth -= 1;
                if depth == 0 {
                    return &src[open..=i];
                }
            }
            _ => {}
        }
        i += 1;
    }
    &src[open..]
}

/// Every `Protocol(...)` construction whose argument list uses `Debug` formatting
/// (`{:?}`, `{x:?}`, `{x:#?}`, `{0:?}`). Returns the offending argument text.
fn debug_formatted_protocol_errors(src: &str) -> Vec<String> {
    let code = strip_line_comments(src);
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(rel) = code[from..].find("Protocol(") {
        let open = from + rel + "Protocol".len();
        let args = balanced_args(&code, open);
        if args.contains(":?}") || args.contains(":#?}") {
            out.push(args.to_string());
        }
        from = open + 1;
    }
    out
}

/// Every `.command(` call (a host round trip) that is NOT consumed directly by a
/// `reply::expect_*` function. Returns the statement text leading up to it.
fn command_calls_outside_the_redacting_parsers(src: &str) -> Vec<String> {
    let code = strip_line_comments(src);
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(rel) = code[from..].find(".command(") {
        let at = from + rel;
        let stmt_start = code[..at].rfind([';', '{', '}']).map_or(0, |i| i + 1);
        let stmt = &code[stmt_start..at];
        if !stmt.contains("reply::expect_") {
            out.push(stmt.trim().to_string());
        }
        from = at + 1;
    }
    out
}

fn rust_files_under(dir: &Path) -> Vec<PathBuf> {
    let mut found = Vec::new();
    let mut pending = vec![dir.to_path_buf()];
    while let Some(d) = pending.pop() {
        for entry in std::fs::read_dir(&d).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                pending.push(path);
            } else if path.extension().is_some_and(|e| e == "rs") {
                found.push(path);
            }
        }
    }
    found.sort();
    found
}

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

// ---- the guards, against the real sources ----

#[test]
fn no_protocol_error_in_the_operator_process_is_debug_formatted() {
    let roots = [
        manifest_dir().join("src"),
        manifest_dir().join("../selahcue-operator/src"),
    ];
    let mut scanned = 0;
    let mut offenders = Vec::new();
    for root in &roots {
        for file in rust_files_under(root) {
            scanned += 1;
            let src = std::fs::read_to_string(&file).unwrap();
            for args in debug_formatted_protocol_errors(&src) {
                offenders.push(format!("{}: Protocol{args}", file.display()));
            }
        }
    }
    // A scan that found no files would pass vacuously (e.g. a moved crate).
    assert!(
        scanned >= 15,
        "scanned only {scanned} files - did a crate move?"
    );
    assert!(
        offenders.is_empty(),
        "TransportError::Protocol built with Debug formatting (FR-082: a ServerMessage can carry \
         live transcript/detection/note text). Use operator_reply::unexpected_reply, which names \
         the variant only:\n{}",
        offenders.join("\n")
    );
}

#[test]
fn every_remote_operator_round_trip_goes_through_the_redacting_parsers() {
    let src = std::fs::read_to_string(manifest_dir().join("src/operator.rs")).unwrap();
    let outside = command_calls_outside_the_redacting_parsers(&src);
    assert!(
        outside.is_empty(),
        "RemoteOperator reads a host reply without operator_reply::expect_*: a hand-written \
         `other =>` arm can reintroduce the Debug dump (17tnw2axppb). Offending statements:\n{}",
        outside.join("\n---\n")
    );
    // Positive control on the real file: the scan does see the round trips (there are 15 today;
    // a count of zero would mean the pattern stopped matching and the check above is vacuous).
    assert!(
        src.matches(".command(").count() >= 10,
        "the scan no longer sees RemoteOperator's round trips"
    );
}

// ---- positive controls: the scanners CAN fail, and do not cry wolf ----

/// The pattern as it stood for years, in rustfmt's real multi-line shape.
const HISTORIC: &str = r#"
            other => Err(selahcue_lan::TransportError::Protocol(format!(
                "expected sermon_note_draft, got: {other:?}"
            ))),
"#;

#[test]
fn the_debug_scanner_flags_the_historic_pattern_and_its_variants() {
    assert_eq!(debug_formatted_protocol_errors(HISTORIC).len(), 1);
    for variant in [
        r#"Err(TransportError::Protocol(format!("got {:?}", other)))"#,
        r#"Err(TransportError::Protocol(format!("got {0:?}", other)))"#,
        r#"Err(TransportError::Protocol(format!("got {other:#?}")))"#,
        r#"Err(Protocol(format!("(weird) paren in the format string {m:?}")))"#,
    ] {
        assert_eq!(
            debug_formatted_protocol_errors(variant).len(),
            1,
            "not flagged: {variant}"
        );
    }
}

#[test]
fn the_debug_scanner_accepts_the_redacting_forms_and_ignores_comments() {
    for ok in [
        r#"TransportError::Protocol(format!("expected {expected}, got: {}", got.kind()))"#,
        r#"TransportError::Protocol("command timed out".into())"#,
        r#"TransportError::Protocol(format!("authentication rejected: {reason}"))"#,
        // The old pattern quoted in a comment (as main.rs and operator_reply.rs do) is prose.
        "// TransportError::Protocol(format!(\"got {other:?}\"))\n//! Protocol(format!(\"{x:?}\"))",
        // A `Debug` outside any Protocol error is not this guard's business.
        r#"let s = format!("{other:?}"); TransportError::Protocol(s)"#,
    ] {
        assert!(
            debug_formatted_protocol_errors(ok).is_empty(),
            "false positive: {ok}"
        );
    }
}

#[test]
fn the_round_trip_scanner_flags_a_hand_written_match_and_accepts_the_parsers() {
    let hand_written = r#"
        pub async fn fresh_method(&mut self) -> Result<u8, TransportError> {
            match self.client.command(Command::Fresh).await? {
                ServerMessage::Fresh { n } => Ok(n),
                other => Err(TransportError::Protocol(String::new())),
            }
        }
    "#;
    assert_eq!(
        command_calls_outside_the_redacting_parsers(hand_written).len(),
        1
    );
    let chained = r#"
        pub async fn fresh_method(&mut self) -> Result<u8, TransportError> {
            reply::expect_fresh(
                self.client
                    .command(Command::Fresh)
                    .await?,
            )
        }
    "#;
    assert!(command_calls_outside_the_redacting_parsers(chained).is_empty());
    // Comments that mention `.command(` are not calls.
    assert!(command_calls_outside_the_redacting_parsers("// self.client.command(x)").is_empty());
}
