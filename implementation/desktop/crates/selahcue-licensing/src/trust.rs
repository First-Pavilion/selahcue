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
        let store = Self::new();

        // --- development entitlement key (debug builds ONLY) -----------------------------
        // `make launch` must not demand activation, and the owner will opt into QAing
        // enforcement deliberately. The mechanism is to MINT, not to bypass: a debug build
        // additionally trusts the development key below, `make` mints a manifest signed by
        // its (deliberately public) seed, and real verification runs — real signature
        // check, real expiry, real cache behaviour. There is no bypass branch, because a
        // branch that skips verification is the highest-value target in the product and
        // means the path we ship is not the path anyone develops against.
        //
        // THE EFFECT-LEVEL GATE IS `scripts/dev_key_not_in_release.sh`, which runs in
        // `make ci` and CI. It builds this crate in both profiles and fails if these 32 bytes
        // appear in the release rlib, with the debug rlib as a live positive control.
        //
        // It exists because everything else here is partial. The `cfg` gates can be removed
        // (caught by the source guard), a release profile can turn `debug_assertions` back on
        // (import_guards.sh catches the common spellings and misses several), and RUSTFLAGS
        // can do the same from the environment where nothing in-repo can see it. Asking what
        // is IN THE ARTEFACT closes all of those CONFIGURATION routes at once.
        //
        // It does NOT close a runtime loader, and this comment used to say it did. The scan
        // searches for the literal key bytes, so it settles "is the key compiled into
        // release" and is blind to "does a release binary obtain the key at runtime" — a
        // loader that derives the bytes leaves it nothing to find. The release `iff` test in
        // CI is what catches that one, so the two controls are COMPLEMENTARY and neither is
        // redundant; the route table is in `scripts/dev_key_not_in_release.sh`.
        //
        // It was deferred once on the belief that it needed something to link the crate
        // first. That was wrong -- `cargo build -p selahcue-licensing --release` emits an
        // rlib today -- and the deferral is recorded here because it cost several rounds of
        // enumerating spellings that a five-second scan made unnecessary.
        //
        // The `cfg` is the control. A release build must not trust this key: its seed is
        // committed in `dev-signing-key.NOT-A-SECRET`, so anyone at all can sign with it.
        // `the_development_key_is_gated_on_debug_assertions` fails if this gate is removed.
        // Shadowed rather than declared `mut` up front: in a release build the block below
        // is compiled out, so a `let mut` there is an unused-mut warning on every release
        // build. Silencing that with `#[allow(unused_mut)]` would have hidden a real signal —
        // the warning is the compiler saying "nothing mutates this here", which is exactly
        // the property the release profile is supposed to have.
        #[cfg(debug_assertions)]
        let store = {
            let mut store = store;
            if let Ok(id) = store.insert(DEV_PUBLIC_KEY) {
                debug_assert_eq!(id, Self::DEV_KEY_ID, "dev key_id drifted from its bytes");
            }
            store
        };

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
    /// **That rule is enforced by review, not by the build.** An earlier version of this
    /// paragraph claimed the opposite — that a config loader "cannot be written in this crate
    /// without tripping" `no_filesystem_primitive_is_reachable_from_this_crate`. It can.
    /// Security review demonstrated three compiling loaders that pass that guard green:
    /// `use std::{env as source};` (the brace puts `{` between `std::` and `env`, so the
    /// scanned substring never appears), `std :: env :: var(..)` (whitespace around `::`
    /// does the same), and — the one no amount of spelling-chasing reaches — a helper placed
    /// in the path dependency `selahcue-cloud` and called as `selahcue_cloud::read_env()`,
    /// which names no forbidden token in this crate's `src/` at all.
    ///
    /// What that guard actually is: a **lexical scan of this crate's own `src/` for an
    /// enumerated set of spellings**. It catches the plain forms, which is worth having and
    /// is why it stays. It cannot catch aliased or whitespace-separated paths, and it cannot
    /// see through the dependency graph — and no name-scan ever will, because reachability
    /// is transitive and the spellings are unbounded. Widening the list only moves the
    /// boundary; it never closes it.
    ///
    /// The effect-level control is the one [`TrustedKeys::bundled`] records twenty lines
    /// above: **byte-scan the shipped release artefact** for the dev key and fail if it is
    /// present — `scripts/dev_key_not_in_release.sh`. It **ships and runs today**, in
    /// `make ci` and in CI. This paragraph previously called it an obligation deferred onto
    /// 86ak5mn1d / 86ak5mn1t "because it needs something to actually link this crate first";
    /// that is the belief `bundled()` calls wrong, and the scan has run at every commit since.
    ///
    /// It is immune to spelling, to aliasing and to the dependency graph. It is **not** immune
    /// to a runtime loader, and this paragraph claimed it was. The scan searches the emitted
    /// rlib for the literal key bytes, so it settles *"is the key compiled into release"* and
    /// cannot see *"does a release binary obtain the key at runtime"*. A loader that derives
    /// the bytes — from the decimal form the seed file itself publishes, for instance —
    /// leaves it nothing to find. Security review built that loader, put the env read in the
    /// path dependency `selahcue-cloud` so the guard above is blind too, and every control in
    /// the repository passed it green.
    ///
    /// **No gate closes that, and none is being added.** Handing the runtime-loader threat on
    /// to the byte scan is what turned two honest admissions into a false guarantee, so it is
    /// not handed on: the rule at the top of this comment is enforced by REVIEW, deliberately.
    /// Writing a config loader here is a considered act rather than a slip, and the honest
    /// position is that this paragraph tells a reviewer what to look for instead of pretending
    /// a scan will catch it.
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
