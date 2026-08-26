//! Entitlement **policy** — the two client-side rules the server cannot enforce for us.
//!
//! This module deliberately contains no fetching, no signature verification and no cache.
//! Those are 86ak5mn1d. What lives here is the pair of decisions that ticket must not be
//! free to get wrong, landed in the same spirit as the trusted-key *set*: cheap now,
//! expensive to retrofit, and dangerous if guessed.
//!
//! # Bound the payload BEFORE decoding it
//!
//! [`Grants`] is an unbounded map read straight from the payload, and it is only safe once
//! the signature has been checked — a trusted signature is what makes its size the server's
//! problem rather than an attacker's. Whoever fetches the manifest (86ak5mn1d) must cap the
//! accepted response size **before** decode, not after. This pairs with the same gap on the
//! shared transport, which reads whole bodies with no byte cap.
//!
//! # (a) An absent grant fails restrictive, never permissive
//!
//! The catalogue treats **absent**, **null** and **a value** as three distinct states
//! (`apps/catalogue/services.py:86-92`):
//!
//! | On the wire | Means |
//! |---|---|
//! | key absent | no signed opinion — the client decides |
//! | key present, `null` | granted **without a ceiling** (an operator typed `unlimited`) |
//! | key present, value | that `bool` or `int` |
//!
//! Server-side this is safe: stripping a key breaks the signature. But the moment the
//! client falls back to a default, **the signature stops being the control and the default
//! becomes the control.** If any dimension defaulted to unlimited, an attacker would gain a
//! capability by *deleting* signed data rather than forging it — and deleting is free,
//! while forging needs the signing key.
//!
//! So [`Grants::allowance`] answers [`Allowance::Denied`] for an absent key, and **there is
//! no API here that yields [`Allowance::Unlimited`] for one**. That is the control: not a
//! default someone chose well, but a permissive default that cannot be written.
//!
//! # (b) A valid degraded manifest must not evict a longer cached one
//!
//! FR-518's keep-the-previous-cache rule covers manifests that fail *verification*. It does
//! not cover one that verifies perfectly and is simply **shorter**. The server issues such
//! a manifest by design: when the catalogue cannot be read it still signs one — refusing
//! would deny a live service over a server-side fault — but clamps it to
//! [`DEGRADED_MANIFEST_TTL_SECONDS`] so a transient failure cannot be frozen into a
//! multi-year offline credential (`apps/entitlements/services.py:122-133`).
//!
//! That protection has a matching client obligation. If a desktop holding a multi-year
//! cached entitlement replaces it with a valid 15-minute one, a brief server blip collapses
//! a church's offline entitlement to fifteen minutes — mid-service, on a product whose
//! central promise is offline-first (NFR-015, CON-2). [`decide_cache_replacement`] refuses
//! that: **a shorter window never evicts a longer cached one.** Keep serving the cached
//! grant and retry.
//!
//! ## The server does not currently tell us it was degraded — raised, not worked around
//!
//! `degraded` is real server-side, but it reaches only the **audit record** and a log line.
//! The signed payload carries `grants`, `expires_at` and fourteen other fields and **no
//! `degraded` flag** (`apps/entitlements/services.py:135-170`). So the client cannot
//! distinguish "short because the catalogue failed" from "short because the licence really
//! is short", and the rule here is correspondingly blunt: it refuses *any* shortening.
//!
//! The bluntness is the cost of the missing field, and it is deliberately visible rather
//! than hidden — [`decide_cache_replacement`] already takes the flag as
//! `Option<bool>`, so publishing it in the payload narrows this to exactly the intended
//! rule with no change here: `Some(true)` keeps the cache, `Some(false)` allows a genuine
//! licence shortening through, `None` (today) stays conservative.

use serde::Deserialize;
use std::collections::BTreeMap;

/// The server's clamp on a degraded manifest (`entitlements/services.py:83`). Mirrored for
/// documentation and tests; the client never assumes it, it reads `expires_at`.
pub const DEGRADED_MANIFEST_TTL_SECONDS: i64 = 900;

/// A grant value as it appears on the wire.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(untagged)]
pub enum GrantScalar {
    /// A capability switch.
    Flag(bool),
    /// A ceiling.
    Count(i64),
}

/// What this client may do for one dimension.
///
/// Note what is **not** here: any `Default`. Absence is answered by [`Grants::allowance`]
/// with [`Self::Denied`], and there is no other way to obtain an `Allowance` from a missing
/// key — so "unset means no limit" cannot be written by accident.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Allowance {
    /// The key was absent: no signed opinion, so nothing is granted.
    ///
    /// This is the whole of control (a). An attacker who strips a grant from a manifest
    /// they hold must end up with *less* capability, never more.
    Denied,
    /// Explicit `null` — granted with no ceiling. Only an operator typing `unlimited`
    /// produces this, and only over a valid signature.
    Unlimited,
    /// An explicit ceiling.
    Count(i64),
    /// An explicit capability switch.
    Flag(bool),
}

impl Allowance {
    /// Whether this permits anything at all. `Denied` and `Flag(false)` do not.
    pub fn permits_any(&self) -> bool {
        match self {
            Allowance::Denied => false,
            Allowance::Flag(on) => *on,
            Allowance::Count(n) => *n > 0,
            Allowance::Unlimited => true,
        }
    }

    /// A numeric ceiling, or `None` when unlimited.
    ///
    /// `Denied` is `Some(0)`, not `None` — reading "no opinion" as "no limit" is precisely
    /// the inversion this module exists to prevent.
    ///
    /// # Two traps for whoever writes enforcement (86ak5mn1t)
    ///
    /// **A ceiling can be negative.** An operator can type `-3` into the catalogue, so this
    /// returns `Some(-3)`. Enforcement must therefore **compare, never subtract**:
    /// `used < ceiling` is safe, `remaining = ceiling - used` yields a negative "remaining"
    /// that an unsigned cast turns into a very large allowance.
    ///
    /// **`Flag(true)` has no ceiling**, so this returns `None` for it — the same value
    /// `Unlimited` returns. Numeric enforcement meeting a dimension the catalogue happens to
    /// have typed as a bool must read that restrictively rather than as "no limit"; check
    /// [`Self::permits_any`] and the variant, not the ceiling alone.
    pub fn ceiling(&self) -> Option<i64> {
        match self {
            Allowance::Denied => Some(0),
            Allowance::Flag(false) => Some(0),
            Allowance::Flag(true) => None,
            Allowance::Count(n) => Some(*n),
            Allowance::Unlimited => None,
        }
    }
}

/// The `grants` map from a verified manifest payload.
///
/// Keys come from catalogue rows, so a new dimension appears without a client code change.
/// That is exactly why the *default* has to be safe: this client will routinely meet keys
/// it has never heard of, and must meet unknown ones the same way it meets absent ones.
#[derive(Debug, Clone, Default, PartialEq, Eq, Deserialize)]
#[serde(transparent)]
pub struct Grants(BTreeMap<String, Option<GrantScalar>>);

impl Grants {
    /// Build from decoded pairs. `None` is the wire's `null` — unlimited.
    pub fn from_pairs(pairs: impl IntoIterator<Item = (String, Option<GrantScalar>)>) -> Self {
        Grants(pairs.into_iter().collect())
    }

    /// What this manifest grants for `key`.
    ///
    /// **Absent is [`Allowance::Denied`].** There is deliberately no variant of this call
    /// that takes a caller-supplied fallback: a `grants.allowance_or(key, Unlimited)` would
    /// re-open the hole at every call site, one careless argument at a time.
    pub fn allowance(&self, key: &str) -> Allowance {
        match self.0.get(key) {
            None => Allowance::Denied,
            Some(None) => Allowance::Unlimited,
            Some(Some(GrantScalar::Flag(on))) => Allowance::Flag(*on),
            Some(Some(GrantScalar::Count(n))) => Allowance::Count(*n),
        }
    }

    /// Whether the manifest carried an opinion about `key` at all.
    pub fn mentions(&self, key: &str) -> bool {
        self.0.contains_key(key)
    }

    /// Every dimension the manifest spoke to, in deterministic order.
    pub fn keys(&self) -> Vec<&str> {
        self.0.keys().map(String::as_str).collect()
    }

    /// How many dimensions were carried.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether the manifest carried no grants at all — the shape a degraded issuance has,
    /// since a failed catalogue read yields `values={}`.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

/// Facts this policy needs, taken from a **verified** manifest payload.
///
/// # Every field here must come from inside the signature
///
/// This is the contract, and it is the difference between a control and a decoration.
/// `expires_at`, `issued_at` and `degraded` are all signed payload fields. **None of them
/// may ever be populated from transport metadata** — not an HTTP header, not a status code,
/// not a sibling field the view appends outside the envelope (`surface`/`operation` are
/// exactly that shape). A man-in-the-middle who replays a captured degraded manifest and
/// attaches a forged "not degraded" marker outside the signature would otherwise collapse a
/// customer's offline window on demand.
///
/// The fields are private and there is one constructor, named for the contract, so every
/// construction site reads `from_verified_payload` and a reviewer can grep for all of them.
/// The verifier that produces these values is 86ak5mn1d.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SignedFacts {
    expires_at_unix: i64,
    issued_at_unix: i64,
    degraded: Option<bool>,
}

impl SignedFacts {
    /// Build from values read out of a payload whose signature has been verified.
    ///
    /// `degraded` is `None` when the payload does not carry the field — which is every
    /// payload today, since the server publishes it only to the audit record.
    pub fn from_verified_payload(
        expires_at_unix: i64,
        issued_at_unix: i64,
        degraded: Option<bool>,
    ) -> Self {
        SignedFacts {
            expires_at_unix,
            issued_at_unix,
            degraded,
        }
    }

    /// The **artefact** expiry — the clamped `expires_at`, not `license_expires_at`.
    ///
    /// The payload carries both and only this one reflects the degraded clamp. Feeding the
    /// licence expiry here would defeat the whole rule: a degraded manifest would look
    /// multi-year and replace a good cache.
    pub fn expires_at_unix(&self) -> i64 {
        self.expires_at_unix
    }

    /// When the server issued this artefact.
    pub fn issued_at_unix(&self) -> i64 {
        self.issued_at_unix
    }

    /// The server's own word on whether this issuance was degraded, when it says.
    pub fn degraded(&self) -> Option<bool> {
        self.degraded
    }
}

/// What to do with a freshly verified manifest, given what is already cached.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CacheDecision {
    /// Store it: nothing cached, or it neither goes backwards nor shortens.
    Replace,
    /// Keep the cached entitlement and retry later.
    KeepCached(KeepReason),
}

/// Why a verified manifest was not allowed to replace the cache.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum KeepReason {
    /// The incoming manifest was **issued earlier** than the cached one.
    ///
    /// A correctly-signed manifest is still replayable: capture one, serve it later. Without
    /// this the newest artefact does not necessarily win, and an attacker who can answer the
    /// refresh gets to choose which past entitlement the client holds. It also bounds how
    /// long an honest downgrade can be deferred — to the refresh cadence — because the
    /// replacement carries a newer `issued_at`.
    StaleIssuance {
        cached_issued_at_unix: i64,
        incoming_issued_at_unix: i64,
    },
    /// The incoming manifest expires sooner than the cached one, and the server did not say
    /// the shortening was deliberate. Accepting it would let a transient server fault
    /// collapse a customer's offline window.
    WouldShortenEntitlement {
        cached_expires_at_unix: i64,
        incoming_expires_at_unix: i64,
    },
}

/// Decide whether a verified manifest may replace the cached one.
///
/// Pure, and takes instants rather than parsing timestamps: time-dependent behaviour in this
/// workspace is driven by injected values, and decoding the payload belongs to 86ak5mn1d.
///
/// Two rules, in order:
///
/// 1. **Never go backwards.** An older `issued_at` is refused outright — that is a replay,
///    whatever else it says, and it is checked first precisely so a replayed manifest cannot
///    talk its way past rule 2 with its own signed `degraded: false`.
/// 2. **Never shorten**, unless the server explicitly says the shortening is deliberate:
///    - `Some(true)` — degraded: never allowed to shorten.
///    - `Some(false)` — a genuine licence change: allowed.
///    - `None` — the server did not say, which is every payload today. Treated as
///      `Some(true)`, because guessing wrong the other way costs a church its offline window
///      mid-service, while guessing this way only defers an honest downgrade to the next
///      refresh.
///
/// A revoked or expired licence is **not** affected by rule 2: the server issues no manifest
/// at all for one (`POLICY_DENIED` on the issuance allow-list), so there is no shortened
/// artefact to refuse. Issuance is the enforcement point; there is no revocation list.
pub fn decide_cache_replacement(
    cached: Option<SignedFacts>,
    incoming: SignedFacts,
) -> CacheDecision {
    let Some(cached) = cached else {
        // Nothing cached: anything verified beats nothing.
        return CacheDecision::Replace;
    };

    // Rule 1 — replay defence, checked before anything the incoming manifest asserts.
    if incoming.issued_at_unix < cached.issued_at_unix {
        return CacheDecision::KeepCached(KeepReason::StaleIssuance {
            cached_issued_at_unix: cached.issued_at_unix,
            incoming_issued_at_unix: incoming.issued_at_unix,
        });
    }

    // Rule 2 — never shorten without the server saying so.
    if incoming.expires_at_unix >= cached.expires_at_unix {
        return CacheDecision::Replace;
    }
    if incoming.degraded == Some(false) {
        return CacheDecision::Replace;
    }

    CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
        cached_expires_at_unix: cached.expires_at_unix,
        incoming_expires_at_unix: incoming.expires_at_unix,
    })
}
