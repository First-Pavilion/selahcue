//! Custody of the two credentials an activated install holds (FR-517, NFR-017).
//!
//! Both live in the OS secret store — Keychain / Credential Manager / Secret Service —
//! reached through [`SecretStore`], which the application shell injects. Neither is ever
//! written to a file, to the app database, or to a log: the values are carried in
//! [`Token`], whose `Debug` and `Display` are redacted, so the ordinary ways a secret
//! escapes (a `{:?}` in a log line, an error message, a panic payload) cannot leak them.
//!
//! # The two credentials are not the same thing, and that is the point
//!
//! | Credential | What it is | Cleared by sign-out? |
//! |---|---|---|
//! | **Device token** | Proof *this machine* is an activated instance. Show-once. | **No** |
//! | **Account session token** | Proof *a person* is signed in. 30-day TTL. | Yes |
//!
//! [`DeviceCredentials::sign_out`] clears the session and deliberately leaves the device
//! token in place. That is DEC-007's recorded invariant, restated by FR-542 — "session
//! expiry/logout never revokes device tokens or affects live output" — and it is the
//! difference between a volunteer signing out of the booth machine after setup and that
//! machine losing its entitlement mid-Sunday. It is tested explicitly
//! (`test_custody.rs::sign_out_leaves_the_device_token_intact`) because it reads like a
//! bug to anyone who has not seen the decision, and is exactly the kind of thing a
//! well-meaning tidy-up deletes.

use selahcue_cloud::{SecretError, SecretStore, Token};

/// Secret-store entry name for the device token.
///
/// Named `device_token` **locally**, which is safe and clear: the server's audit
/// redaction denylist is a server-side guard on payloads it emits, and has no say over
/// what an OS keychain entry is called. (On the wire the same value is
/// `activation_token`, for the reason spelled out in [`crate::contract`].)
pub const DEVICE_TOKEN_NAME: &str = "device_token";

/// Secret-store entry name for the account session token.
pub const ACCOUNT_SESSION_NAME: &str = "account_session_token";

/// The keyring *service* name both entries live under.
pub const KEYRING_SERVICE: &str = "SelahCue";

/// Reads and writes the licensing credentials, and nothing else.
///
/// Generic over the store so tests use `InMemorySecretStore` and the shell uses
/// `KeyringSecretStore` with no branch in this code.
pub struct DeviceCredentials<S: SecretStore> {
    store: S,
}

impl<S: SecretStore> DeviceCredentials<S> {
    /// Wrap a secret store.
    pub fn new(store: S) -> Self {
        DeviceCredentials { store }
    }

    /// The device token, or `None` when this install has never activated.
    ///
    /// `None` is an ordinary, expected answer — a fresh install, or one whose operator
    /// chose "Skip — set up later". It is not an error and must never be treated as one.
    pub fn device_token(&self) -> Result<Option<Token>, SecretError> {
        self.store.get(DEVICE_TOKEN_NAME)
    }

    /// Persist (or replace) the device token.
    ///
    /// Called on a fresh activation and on a re-mint. On a re-mint the previous token has
    /// already been revoked server-side, so overwriting is mandatory, not optional.
    pub fn store_device_token(&self, token: &Token) -> Result<(), SecretError> {
        self.store.set(DEVICE_TOKEN_NAME, token)
    }

    /// Whether this install holds a **usable** device token.
    ///
    /// An empty string is not a token. The distinction is not hypothetical: a keychain
    /// entry can be present and empty after a partial write or a manual edit, and
    /// `is_some()` alone would report such an install activated — then every call made with
    /// that "token" would 401, with the install insisting it was fine.
    pub fn is_activated(&self) -> Result<bool, SecretError> {
        Ok(self.device_token()?.is_some_and(|t| !t.is_empty()))
    }

    /// The account session token, or `None` when nobody is signed in.
    pub fn account_session(&self) -> Result<Option<Token>, SecretError> {
        self.store.get(ACCOUNT_SESSION_NAME)
    }

    /// Persist (or replace) the account session token.
    pub fn store_account_session(&self, token: &Token) -> Result<(), SecretError> {
        self.store.set(ACCOUNT_SESSION_NAME, token)
    }

    /// Sign the person out: clears the account session, **keeps the device token**.
    ///
    /// See the module docs. This asymmetry is the DEC-007 invariant, not an oversight.
    pub fn sign_out(&self) -> Result<(), SecretError> {
        self.store.remove(ACCOUNT_SESSION_NAME)
    }

    /// Deactivate this install: purge **both** credentials.
    ///
    /// This is the A9 destructive-confirm path — the operator explicitly giving up the
    /// device's slot — and the only path in this crate that removes a device token.
    /// Losing the token stops cloud features; it does not stop slides, scripture, media
    /// or timers, which never depended on it.
    pub fn forget_all(&self) -> Result<(), SecretError> {
        self.store.remove(DEVICE_TOKEN_NAME)?;
        self.store.remove(ACCOUNT_SESSION_NAME)
    }
}
