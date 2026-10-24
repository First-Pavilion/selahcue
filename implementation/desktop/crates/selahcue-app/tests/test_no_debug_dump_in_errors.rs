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
//!
//! Known limit, by design: a `Debug` dump routed through an INTERMEDIATE VARIABLE
//! (`let d = format!("{m:?}"); TransportError::Protocol(d)`) is out of this scan's reach. That
//! shape is caught only by the behavioural tests, which send every reply variant with a planted
//! secret through every `RemoteOperator` method and assert the error contains none of it.

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

/// Whether `text` contains a format placeholder with a `Debug` trait: ANY placeholder whose spec
/// ends in `?`, whatever precedes it (`{:?}`, `{x:?}`, `{x:#?}`, `{x:x?}`, `{x:.9999?}`,
/// `{x:>1?}`, `{0:1?}`, `{x:w$?}`). `{{` is an escaped brace, not a placeholder. Deliberately
/// scans the whole argument text, not just string literals: over-flagging fails loudly, a miss
/// (a raw string, say) would not.
fn has_debug_placeholder(text: &str) -> bool {
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'{' {
            if bytes.get(i + 1) == Some(&b'{') {
                i += 2;
                continue;
            }
            if let Some(len) = text[i + 1..].find('}') {
                let body = &text[i + 1..i + 1 + len];
                if body.contains(':') && body.ends_with('?') {
                    return true;
                }
                i += len + 2;
                continue;
            }
        }
        i += 1;
    }
    false
}

/// Every `Protocol(...)` construction whose argument list uses `Debug` formatting (see
/// [`has_debug_placeholder`]). Returns the offending argument text.
fn debug_formatted_protocol_errors(src: &str) -> Vec<String> {
    let code = strip_line_comments(src);
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(rel) = code[from..].find("Protocol(") {
        let open = from + rel + "Protocol".len();
        let args = balanced_args(&code, open);
        if has_debug_placeholder(args) {
            out.push(args.to_string());
        }
        from = open + 1;
    }
    out
}

/// Whether `ident` appears in `text` as a whole identifier (not as a substring of another word).
fn mentions_ident(text: &str, ident: &str) -> bool {
    text.split(|c: char| !(c.is_alphanumeric() || c == '_'))
        .any(|word| word == ident)
}

/// Every `.command(` call (a host round trip) that is NOT consumed by a `reply::expect_*`
/// function: either directly (`reply::expect_x(self.client.command(c).await?)`) or through one
/// immediately following binding (`let r = self.client.command(c).await?; reply::expect_x(r)`).
/// Returns the statement text leading up to the offending call.
fn command_calls_outside_the_redacting_parsers(src: &str) -> Vec<String> {
    let code = strip_line_comments(src);
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(rel) = code[from..].find(".command(") {
        let at = from + rel;
        from = at + 1;
        let stmt_start = code[..at].rfind([';', '{', '}']).map_or(0, |i| i + 1);
        let stmt = &code[stmt_start..at];
        if stmt.contains("reply::expect_") {
            continue;
        }
        // `let [mut] name = <...>.command(` followed by a statement that feeds `name` to a parser.
        if let Some(binding) = stmt.trim_start().strip_prefix("let ") {
            let name: String = binding
                .trim_start()
                .trim_start_matches("mut ")
                .chars()
                .take_while(|c| c.is_alphanumeric() || *c == '_')
                .collect();
            let stmt_end = code[at..].find(';').map_or(code.len(), |i| at + i + 1);
            let next = code[stmt_end..].split(';').next().unwrap_or("");
            if !name.is_empty() && next.contains("reply::expect_") && mentions_ident(next, &name) {
                continue;
            }
        }
        out.push(stmt.trim().to_string());
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

/// `Protocol(...)` sites the Debug scan flags but that are known-safe: they format a
/// FIELDLESS enum (`DenyReason`), whose `Debug` is just its variant name. Matched by file suffix
/// and a fragment of the argument text. An entry that stops matching fails the test, so this list
/// cannot silently outlive the code it excuses.
const ALLOWED_DEBUG_SITES: &[(&str, &str)] = &[
    (
        "selahcue-lan/src/client.rs",
        "authentication rejected: {reason:?}",
    ),
    ("selahcue-lan/src/client.rs", "pairing rejected: {reason:?}"),
];

#[test]
fn no_protocol_error_in_the_operator_process_is_debug_formatted() {
    let roots = [
        manifest_dir().join("src"),
        manifest_dir().join("../selahcue-operator/src"),
    ];
    // The LAN client builds `Protocol` errors on the operator's connect path too.
    let extra_files = [manifest_dir().join("../selahcue-lan/src/client.rs")];
    let mut files: Vec<PathBuf> = roots.iter().flat_map(|r| rust_files_under(r)).collect();
    files.extend(extra_files);
    // A scan that found no files would pass vacuously (e.g. a moved crate): the real number today
    // is 21 (9 in selahcue-app/src + 11 in selahcue-operator/src + client.rs).
    assert!(
        files.len() >= 21,
        "scanned only {} files - did a crate move?",
        files.len()
    );

    let mut offenders = Vec::new();
    let mut allowed_used = vec![0usize; ALLOWED_DEBUG_SITES.len()];
    for file in &files {
        let src = std::fs::read_to_string(file).unwrap();
        let path = file.to_string_lossy().replace('\\', "/");
        for args in debug_formatted_protocol_errors(&src) {
            let allowed = ALLOWED_DEBUG_SITES
                .iter()
                .position(|(suffix, fragment)| path.ends_with(suffix) && args.contains(fragment));
            match allowed {
                Some(i) => allowed_used[i] += 1,
                None => offenders.push(format!("{}: Protocol{args}", file.display())),
            }
        }
    }
    assert!(
        offenders.is_empty(),
        "TransportError::Protocol built with Debug formatting (FR-082: a ServerMessage can carry \
         live transcript/detection/note text). Use operator_reply::unexpected_reply, which names \
         the variant only:\n{}",
        offenders.join("\n")
    );
    assert_eq!(
        allowed_used,
        vec![1; ALLOWED_DEBUG_SITES.len()],
        "every allow-list entry must match exactly one real site (a stale entry excuses nothing)"
    );
}

/// The allow-listed sites are only safe while `DenyReason` is a fieldless enum; if a variant ever
/// gains a payload this stops compiling (the `match` patterns name no fields) or the Debug check
/// below fails.
#[test]
fn the_allow_listed_debug_sites_format_a_fieldless_enum() {
    use selahcue_lan::protocol::DenyReason;
    fn exhaustive(r: DenyReason) -> DenyReason {
        match r {
            DenyReason::Forbidden => r,
            DenyReason::Unauthenticated => r,
            DenyReason::BadRequest => r,
        }
    }
    for r in [
        DenyReason::Forbidden,
        DenyReason::Unauthenticated,
        DenyReason::BadRequest,
    ] {
        let shown = format!("{:?}", exhaustive(r));
        assert!(
            shown.chars().all(|c| c.is_ascii_alphabetic()),
            "{shown} is not a bare variant name"
        );
    }
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
    // a smaller count would mean the pattern stopped matching and the check above is vacuous).
    assert!(
        src.matches(".command(").count() >= 15,
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
        // Debug with a format spec: every one of these printed the full payload of a real
        // `ServerMessage` and used to slip past a `:?}` / `:#?}` substring check.
        r#"Err(TransportError::Protocol(format!("got {other:x?}")))"#,
        r#"Err(TransportError::Protocol(format!("got {other:.9999?}")))"#,
        r#"Err(TransportError::Protocol(format!("got {other:>1?}")))"#,
        r#"Err(TransportError::Protocol(format!("got {0:1?}", other)))"#,
        r#"Err(TransportError::Protocol(format!("got {other:w$?}", w = 3)))"#,
        r#"Err(TransportError::Protocol(format!("got {other:#X?}")))"#,
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
        // A `Debug` outside any Protocol error is not this guard's business (the documented
        // limit: a dump through an intermediate variable is caught by the behavioural tests).
        r#"let s = format!("{other:?}"); TransportError::Protocol(s)"#,
        // Escaped braces and a question mark in prose are not placeholders.
        r#"TransportError::Protocol(format!("literal {{what?}} braces, and why? {x}"))"#,
        r#"TransportError::Protocol(format!("a {{:?}} escaped"))"#,
        // Display with a spec is fine.
        r#"TransportError::Protocol(format!("{x:>8} {y:.3}"))"#,
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
    // A binding that is handed straight to a parser is fine ...
    let bound = r#"
        pub async fn fresh_method(&mut self) -> Result<u8, TransportError> {
            let r = self.client.command(Command::Fresh).await?;
            reply::expect_fresh(r)
        }
    "#;
    assert!(command_calls_outside_the_redacting_parsers(bound).is_empty());
    // ... one that is bound and then matched by hand is not ...
    let bound_then_matched = r#"
        pub async fn fresh_method(&mut self) -> Result<u8, TransportError> {
            let r = self.client.command(Command::Fresh).await?;
            match r { ServerMessage::Fresh { n } => Ok(n), other => Err(oops(other)) }
        }
    "#;
    assert_eq!(
        command_calls_outside_the_redacting_parsers(bound_then_matched).len(),
        1
    );
    // ... and neither is a parser call that does not take the bound name.
    let bound_wrong_name = r#"
        pub async fn fresh_method(&mut self) -> Result<u8, TransportError> {
            let r = self.client.command(Command::Fresh).await?;
            reply::expect_fresh(something_else)
        }
    "#;
    assert_eq!(
        command_calls_outside_the_redacting_parsers(bound_wrong_name).len(),
        1
    );
    // Comments that mention `.command(` are not calls.
    assert!(command_calls_outside_the_redacting_parsers("// self.client.command(x)").is_empty());
}
