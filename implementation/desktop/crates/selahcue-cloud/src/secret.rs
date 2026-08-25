//! The SelahCue account/session token and its secret store (FR-134, NFR-017).
//!
//! The hosted model authenticates with a SelahCue account/session token — **never a
//! user-pasted third-party API key**. The token is held in [`Token`], which redacts
//! itself in `Debug`/`Display` so it can never be logged by accident, and is persisted
//! only via a [`SecretStore`] (the OS Keychain / Credential Manager / Secret Service
//! behind the `keyring` feature; an in-memory store for tests). `remove` purges it.

use std::sync::Mutex;

/// A SelahCue account/session token. Its `Debug`/`Display` are **redacted** — the
/// secret is reachable only through [`Token::expose`], which the code calls exactly
/// once at the point of use (the `Authorization` header) and never logs.
///
/// # `Deserialize` but deliberately not `Serialize`
///
/// A token arrives from the wire, so wire types can name this type directly for their
/// secret-bearing fields and inherit the redaction structurally — rather than relying on
/// a hand-written `Debug` that the next field added to the struct would slip straight
/// past. That is worth more than it looks: it is the difference between "we remembered"
/// and "it cannot happen".
///
/// The reverse direction is omitted on purpose. Nothing in this codebase should ever
/// serialize a token back out into JSON, and leaving `Serialize` off means that is a
/// compile error rather than a code-review question.
#[derive(Clone, Eq, serde::Deserialize)]
pub struct Token(String);

/// Constant-time equality.
///
/// The derived `PartialEq` short-circuits on the first differing byte, which over a
/// credential is a timing side channel: an attacker who can submit candidate tokens and
/// measure the comparison learns the secret one byte at a time. Nothing compares two
/// `Token`s outside tests today — but this type now carries **device tokens** on the
/// response path, and "does the presented token match the stored one" is the obvious next
/// thing someone writes. Making it timing-invariant now costs nothing and removes the
/// chance that the obvious code is quietly wrong.
///
/// Lengths are compared first and non-constant-time, which is standard and accepted: token
/// length is not the secret.
impl PartialEq for Token {
    fn eq(&self, other: &Self) -> bool {
        let a = self.0.as_bytes();
        let b = other.0.as_bytes();
        if a.len() != b.len() {
            return false;
        }
        // Fold every byte pair into an accumulator; no early exit, so the work done does
        // not depend on WHERE the values differ.
        let mut diff = 0u8;
        for (x, y) in a.iter().zip(b.iter()) {
            diff |= x ^ y;
        }
        diff == 0
    }
}

impl Token {
    pub fn new(value: impl Into<String>) -> Self {
        Token(value.into())
    }

    /// The raw token — call only where the secret is actually needed (the bearer
    /// header). Never pass the result to a logger/formatter.
    pub fn expose(&self) -> &str {
        &self.0
    }

    /// Whether the token is empty (treated as "no token configured").
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

// Redacting formatters: printing a Token never reveals its value.
impl core::fmt::Debug for Token {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        // An EMPTY token renders distinguishably. Whether a credential is empty is not
        // secret material — an empty token is not a credential at all — and hiding the
        // difference costs twice over:
        //
        //   * diagnostically, an empty entry rendering as "redacted" disguises exactly the
        //     bug `is_activated` exists to catch, where a present-but-empty keychain entry
        //     makes an install insist it is activated while every call 401s;
        //   * for testing, a redaction sweep cannot otherwise tell "this fixture carries a
        //     real secret and hid it" from "this fixture was empty and hid nothing" — so a
        //     neutered fixture passes while exercising nothing.
        //
        // Same reasoning as comparing lengths in the constant-time `PartialEq` above:
        // presence and size are not the secret; the bytes are.
        if self.0.is_empty() {
            f.write_str("Token(<empty>)")
        } else {
            f.write_str("Token(***redacted***)")
        }
    }
}

impl core::fmt::Display for Token {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str("***redacted***")
    }
}

/// A secret-store failure. Its message never contains the secret value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SecretError(pub String);

impl core::fmt::Display for SecretError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for SecretError {}

/// A named-secret store. Backed by the OS secret store in production and by an
/// in-memory map in tests. `name` is a stable credential name (e.g. `"account_token"`).
pub trait SecretStore {
    /// Fetch a token, or `None` if unset. Returns `Err` only on a store failure.
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError>;
    /// Store (or replace) a token.
    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError>;
    /// Purge a token. Removing an absent token is a success (idempotent).
    fn remove(&self, name: &str) -> Result<(), SecretError>;
}

/// An in-memory [`SecretStore`] for tests and headless dev — no OS keychain needed.
#[derive(Debug, Default)]
pub struct InMemorySecretStore {
    map: Mutex<std::collections::HashMap<String, String>>,
}

impl InMemorySecretStore {
    pub fn new() -> Self {
        Self::default()
    }
}

impl SecretStore for InMemorySecretStore {
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
        let map = self.map.lock().map_err(|e| SecretError(e.to_string()))?;
        Ok(map.get(name).map(|v| Token::new(v.clone())))
    }

    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
        let mut map = self.map.lock().map_err(|e| SecretError(e.to_string()))?;
        map.insert(name.to_string(), token.expose().to_string());
        Ok(())
    }

    fn remove(&self, name: &str) -> Result<(), SecretError> {
        let mut map = self.map.lock().map_err(|e| SecretError(e.to_string()))?;
        map.remove(name);
        Ok(())
    }
}

/// An OS-secret-store-backed [`SecretStore`] (Keychain / Credential Manager / Secret
/// Service) via the same `keyring` crate the DB key uses (`keys.rs` idiom). Compiled
/// only with the `keyring` feature so tests need no OS keychain.
#[cfg(feature = "keyring")]
pub struct KeyringSecretStore {
    service: String,
}

#[cfg(feature = "keyring")]
impl KeyringSecretStore {
    /// A store under the given keyring *service* name (e.g. `"SelahCue"`). Each secret
    /// is a `(service, name)` entry.
    pub fn new(service: impl Into<String>) -> Self {
        KeyringSecretStore {
            service: service.into(),
        }
    }

    fn entry(&self, name: &str) -> Result<keyring::Entry, SecretError> {
        keyring::Entry::new(&self.service, name).map_err(|e| SecretError(e.to_string()))
    }
}

#[cfg(feature = "keyring")]
impl SecretStore for KeyringSecretStore {
    fn get(&self, name: &str) -> Result<Option<Token>, SecretError> {
        match self.entry(name)?.get_password() {
            Ok(v) => Ok(Some(Token::new(v))),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(SecretError(e.to_string())),
        }
    }

    fn set(&self, name: &str, token: &Token) -> Result<(), SecretError> {
        self.entry(name)?
            .set_password(token.expose())
            .map_err(|e| SecretError(e.to_string()))
    }

    fn remove(&self, name: &str) -> Result<(), SecretError> {
        match self.entry(name)?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(SecretError(e.to_string())),
        }
    }
}
