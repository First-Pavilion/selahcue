//! C-005: the account/session token store (FR-134, NFR-017). Round-trips get/set/
//! remove; the token redacts itself in Debug/Display so it can never be logged.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{InMemorySecretStore, SecretStore, Token};

const NAME: &str = "account_token";

#[test]
fn get_set_remove_round_trips() {
    let store = InMemorySecretStore::new();
    assert!(store.get(NAME).unwrap().is_none(), "starts empty");

    store.set(NAME, &Token::new("s3cr3t-session")).unwrap();
    let got = store.get(NAME).unwrap().unwrap();
    assert_eq!(got.expose(), "s3cr3t-session");

    store.remove(NAME).unwrap();
    assert!(store.get(NAME).unwrap().is_none(), "purged after remove");
}

#[test]
fn remove_is_idempotent() {
    let store = InMemorySecretStore::new();
    // Removing an absent token is a success, not an error.
    store.remove(NAME).unwrap();
}

#[test]
fn token_debug_and_display_are_redacted() {
    let token = Token::new("super-secret-value");
    let dbg = format!("{token:?}");
    let disp = format!("{token}");
    assert!(!dbg.contains("super-secret-value"), "Debug leaked: {dbg}");
    assert!(
        !disp.contains("super-secret-value"),
        "Display leaked: {disp}"
    );
    assert!(dbg.contains("redacted"));
    // An empty token is reported as empty rather than as a hidden secret: emptiness is not
    // secret material, and a sweep that cannot tell the two apart passes on fixtures that
    // carry nothing.
    assert_eq!(format!("{:?}", Token::new("")), "Token(<empty>)");
    // The value is still reachable explicitly where actually needed.
    assert_eq!(token.expose(), "super-secret-value");
}

#[test]
fn empty_token_is_reported_empty() {
    assert!(Token::new("").is_empty());
    assert!(!Token::new("x").is_empty());
}

#[test]
fn a_blank_token_is_empty_or_only_whitespace_and_nothing_else() {
    for blank in ["", " ", "   ", "\t", "\n", " \r\n\t "] {
        assert!(
            Token::new(blank).is_blank(),
            "{blank:?} is not a credential"
        );
    }
    // Positive controls: padding around a real value, and a lone real character, are not blank.
    for real in ["x", " x ", "sess-1", "a b"] {
        assert!(!Token::new(real).is_blank(), "{real:?} is a value");
    }
}

#[test]
fn control_characters_are_detected_including_cr_and_lf() {
    for bad in [
        "sess\r\nX-Injected: 1",
        "sess\n",
        "sess\r",
        "se\0ss",
        "se\tss",
        "\u{7f}",
    ] {
        assert!(Token::new(bad).has_control_characters(), "{bad:?}");
    }
    for fine in [
        "",
        "sess-1112222",
        "sess with space",
        "d\u{e9}j\u{e0}",
        "\u{4e2d}\u{6587}",
    ] {
        assert!(!Token::new(fine).has_control_characters(), "{fine:?}");
    }
}
