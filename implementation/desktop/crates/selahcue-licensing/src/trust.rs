//! The trusted entitlement-signing keys — a **set**, selected by `key_id` (FR-518).
//!
//! # Why this is a set in the foundation ticket and not later
//!
//! DEC-011 pt 2 calls this "not deferrable", and the reasoning is worth keeping next to
//! the code because it is not obvious from the shape of the type. The signing public key
//! is compiled into every installed desktop copy. If a client trusted exactly one key,
//! then the first time that key ever changed — a rotation, a leak, a lost secret — every
//! new entitlement would be rejected on every installed copy simultaneously, and shipping
//! an update would not fix it, because the machines that matter are church booths that are
//! deliberately offline. A set plus a `key_id` makes rotation a server-side operation
//! against clients already in the field: add the new key to the set, ship, wait for
//! adoption, start signing with the new key, retire the old one after the overlap.
//!
//! The cost is the one DEC-011 names — "an array instead of a constant, plus one field" —
//! and it is what makes deferring KMS custody a safe deferral rather than a trap.
//!
//! # What this module does and does not do
//!
//! It holds keys and selects one by `key_id`. It does **not** verify signatures: that,
//! with manifest caching, is 86ak5mn1d. Keeping the trust store here means that ticket
//! implements `verify()` against a store that is already a set, so single-key thinking
//! never gets a chance to be baked in.

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

/// Length of a raw Ed25519 public key.
pub const PUBLIC_KEY_BYTES: usize = 32;

/// Length of a `key_id`: the first 8 hex characters of SHA-256 over the raw public key
/// (`apps/entitlements/signing.py:72-79`).
pub const KEY_ID_HEX_CHARS: usize = 8;

// The derivation below emits two hex characters per byte, so it can only land on
// KEY_ID_HEX_CHARS exactly when that number is even. It is pinned rather than handled: an
// odd id length would be a change to a cross-language contract, not a local tweak, and it
// should stop the build here rather than be silently trimmed to fit.
const _: () = assert!(
    KEY_ID_HEX_CHARS.is_multiple_of(2),
    "KEY_ID_HEX_CHARS must be even: the derivation emits whole bytes as two hex chars each"
);

/// The most trusted keys this client will hold at once.
///
/// A bound, not a target. The rotation procedure needs two at a time (outgoing plus
/// incoming) and this leaves generous headroom, while keeping the store from growing
/// without limit should a future loader ever feed it from anywhere but the compiled-in
/// list — lookup cost and memory both stay bounded by construction.
pub const MAX_TRUSTED_KEYS: usize = 8;

// FR-518 pinned at compile time: the trust store must be able to hold more than one key.
// A cap of 1 is not a smaller set, it is a *single-key client* — the precise thing
// DEC-011 pt 2 forbids, and the thing that would make a future rotation unshippable to
// machines that are deliberately offline. Reducing this below 2 breaks the build on
// purpose, so the property cannot be lost to a tidy-up that reads it as an arbitrary
// number.
const _: () = assert!(
    MAX_TRUSTED_KEYS >= 2,
    "FR-518/DEC-011: the entitlement trust store must be a SET (>= 2 keys), never a single key"
);

/// The development entitlement signing key's PUBLIC half — **debug builds only**.
///
/// Derived from the deliberately-public seed in `dev-signing-key.NOT-A-SECRET`. Compiled
/// out of release builds entirely, so a release binary cannot trust it even by accident.
#[cfg(debug_assertions)]
const DEV_PUBLIC_KEY: [u8; PUBLIC_KEY_BYTES] = [
    122, 63, 108, 222, 26, 234, 144, 88, 16, 53, 82, 180, 127, 244, 213, 16, 86, 6, 76, 132, 249,
    209, 18, 122, 21, 96, 175, 100, 231, 174, 33, 129,
];

/// A raw Ed25519 public key together with its derived id.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TrustedKey {
    key_id: String,
    public_key: [u8; PUBLIC_KEY_BYTES],
}

impl TrustedKey {
    /// The `key_id` a manifest envelope names to select this key.
    pub fn key_id(&self) -> &str {
        &self.key_id
    }

    /// The raw 32-byte public key, for the verifier in 86ak5mn1d.
    pub fn public_key(&self) -> &[u8; PUBLIC_KEY_BYTES] {
        &self.public_key
    }
}

/// Derive a `key_id` exactly as the server does: SHA-256 over the raw public key, first
/// 8 lowercase hex characters.
///
/// Derived rather than configured, mirroring the server's rationale: a key and its id
/// cannot drift apart, and rotation needs no registry on either side.
pub fn derive_key_id(public_key: &[u8; PUBLIC_KEY_BYTES]) -> String {
    let digest = Sha256::digest(public_key);
    let mut out = String::with_capacity(KEY_ID_HEX_CHARS);
    for byte in digest.iter().take(KEY_ID_HEX_CHARS.div_ceil(2)) {
        use core::fmt::Write as _;
        // Infallible for a String sink.
        let _ = write!(out, "{byte:02x}");
    }
    out
}

/// A key could not be added to the trust store.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TrustError {
    /// The store already holds [`MAX_TRUSTED_KEYS`] distinct keys.
    Full { cap: usize },
    /// A **different** key derives an id the store already holds. Refused loudly rather
    /// than dropped silently — see [`TrustedKeys::insert`].
    Collision { key_id: String },
}

impl core::fmt::Display for TrustError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            TrustError::Full { cap } => {
                write!(f, "the trust store already holds its maximum of {cap} keys")
            }
            TrustError::Collision { key_id } => write!(
                f,
                "a different key already occupies key_id {key_id}; refusing to replace it silently"
            ),
        }
    }
}

impl std::error::Error for TrustError {}

/// The set of public keys whose entitlement signatures this build accepts.
///
/// Keyed by `key_id` so selection is a lookup, not a scan, and so a `BTreeMap` gives
/// deterministic ordering for tests and logs.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct TrustedKeys {
    keys: BTreeMap<String, TrustedKey>,
}

impl TrustedKeys {
    /// An empty store.
    pub fn new() -> Self {
        TrustedKeys {
            keys: BTreeMap::new(),
        }
    }

    /// `key_id` of the **development** entitlement signing key (`f5194d13`).
    ///
    /// Always compiled, in every profile, because it is a public identifier and the
    /// release-exclusion test has to be able to name the entity it asserts is absent.
    /// Compiling the id is not what makes a build trust the key — [`Self::bundled`] is.
    pub const DEV_KEY_ID: &'static str = "f5194d13";

    /// The keys compiled into this build.
    ///
    /// **Currently empty, and honestly so.** The production entitlement signing key is an
    /// env-var seed on the server (`SELAHCUE_ENTITLEMENT_SIGNING_KEY`, DEC-011 pt 1) and
    /// no public key has been issued for bundling yet. Populating this — and the
    /// fail-closed rule that an envelope naming an unknown `key_id` is refused while the
    /// previous valid cache is kept (FR-518) — belongs to 86ak5mn1d, which is where the
    /// verifier lands. Refusal keeps the prior cache and never degrades the running app;
    /// an empty store therefore fails closed on *verification* without ever failing
    /// closed on *presentation*.
    pub fn bundled() -> Self {
        let mut store = Self::new();

        // --- development entitlement key (debug builds ONLY) -----------------------------
        // `make launch` must not demand activation, and the owner will opt into QAing
        // enforcement deliberately. The mechanism is to MINT, not to bypass: a debug build
        // additionally trusts the development key below, `make` mints a manifest signed by
        // its (deliberately public) seed, and real verification runs — real signature
        // check, real expiry, real cache behaviour. There is no bypass branch, because a
        // branch that skips verification is the highest-value target in the product and
        // means the path we ship is not the path anyone develops against.
        //
        // OBLIGATION ON WHOEVER FIRST LINKS THIS CRATE (86ak5mn1d / 86ak5mn1t):
        // add a build step that scans the shipped RELEASE binary for these 32 bytes and
        // fails if they are present. That is the only complete control. Everything below is
        // partial: the `cfg` gates can be removed (caught by the source guard), a release
        // profile can turn `debug_assertions` back on (caught by scripts/import_guards.sh),
        // and `RUSTFLAGS=-C debug-assertions=on` can do the same from the environment
        // (caught by nothing in-repo). A byte scan of the artefact answers the question that
        // actually matters -- does the thing we ship contain this key -- and is immune to
        // all three, plus any future runtime loader.
        //
        // The `cfg` is the control. A release build must not trust this key: its seed is
        // committed in `dev-signing-key.NOT-A-SECRET`, so anyone at all can sign with it.
        // `the_development_key_is_gated_on_debug_assertions` fails if this gate is removed.
        #[cfg(debug_assertions)]
        {
            if let Ok(id) = store.insert(DEV_PUBLIC_KEY) {
                debug_assert_eq!(id, Self::DEV_KEY_ID, "dev key_id drifted from its bytes");
            }
        }

        store
    }

    /// Add a key, deriving its id. Returns the id.
    ///
    /// # The trusted set must never become loadable from configuration
    ///
    /// This is `pub` so the bundled set can be built and so tests can exercise the bounds.
    /// It must **not** grow a caller that reads keys from a file, an environment variable or
    /// a config value: a trust store an operator can append to is not a trust store, and it
    /// re-creates by the back door exactly the bypass that `bundled`'s `cfg` gate exists to
    /// prevent.
    ///
    /// That is structural rather than advisory here — `no_filesystem_primitive_is_reachable_from_this_crate`
    /// fails the build if anything in `src/` so much as names `std::fs`, `std::env` or
    /// `File::open`, so a config loader cannot be written in this crate without tripping it.
    ///
    /// Idempotent for the *same key material*: re-adding a key already present succeeds
    /// and consumes no extra slot, so a loader that runs twice cannot exhaust the cap.
    ///
    /// A **different** key deriving an id already in the store is refused with
    /// [`TrustError::Collision`]. `key_id` is only 32 bits, so a colliding pair is
    /// findable in about a second; treating "id already present" as success without
    /// comparing the bytes would silently keep the first key and drop the second. That is
    /// not a forgery vector — verification uses the stored full 32-byte key, so a
    /// collision makes a legitimate manifest fail, which is fail-closed — but it is a
    /// silent rotation denial-of-service on the exact mechanism DEC-011's accepted
    /// no-KMS risk rests on: the operator adds the incoming key, the call returns `Ok`,
    /// and the rotation then fails in the field as unexplained verification errors with
    /// nothing anywhere saying why.
    pub fn insert(&mut self, public_key: [u8; PUBLIC_KEY_BYTES]) -> Result<String, TrustError> {
        let key_id = derive_key_id(&public_key);
        if let Some(existing) = self.keys.get(&key_id) {
            if existing.public_key == public_key {
                return Ok(key_id);
            }
            return Err(TrustError::Collision { key_id });
        }
        if self.keys.len() >= MAX_TRUSTED_KEYS {
            return Err(TrustError::Full {
                cap: MAX_TRUSTED_KEYS,
            });
        }
        self.keys.insert(
            key_id.clone(),
            TrustedKey {
                key_id: key_id.clone(),
                public_key,
            },
        );
        Ok(key_id)
    }

    /// Select the key a manifest envelope names.
    ///
    /// `None` means the envelope names a key this build does not trust — which FR-518
    /// requires be treated as a refusal that keeps the previous valid cache, never as a
    /// reason to degrade anything the congregation can see.
    pub fn get(&self, key_id: &str) -> Option<&TrustedKey> {
        self.keys.get(key_id)
    }

    /// Whether this build trusts `key_id`.
    pub fn contains(&self, key_id: &str) -> bool {
        self.keys.contains_key(key_id)
    }

    /// How many distinct keys are held.
    pub fn len(&self) -> usize {
        self.keys.len()
    }

    /// Whether the store is empty.
    pub fn is_empty(&self) -> bool {
        self.keys.is_empty()
    }

    /// Every trusted `key_id`, in deterministic order.
    pub fn key_ids(&self) -> Vec<&str> {
        self.keys.keys().map(String::as_str).collect()
    }

    /// The cap this store enforces.
    pub const fn capacity() -> usize {
        MAX_TRUSTED_KEYS
    }
}
