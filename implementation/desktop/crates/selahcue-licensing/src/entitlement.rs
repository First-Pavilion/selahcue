//! Entitlement **policy** — the two client-side rules the server cannot enforce for us.
//!
//! This module deliberately contains no fetching, no signature verification and no cache.
//! Those are 86ak5mn1d. What lives here is the pair of decisions that ticket must not be
//! free to get wrong, landed in the same spirit as the trusted-key *set*: cheap now,
//! expensive to retrofit, and dangerous if guessed.
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

/// What to do with a freshly verified manifest, given what is already cached.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CacheDecision {
    /// Store it: nothing cached, or it does not shorten the entitlement.
    Replace,
    /// Keep the cached entitlement and retry later.
    KeepCached(KeepReason),
}

/// Why a verified manifest was not allowed to replace the cache.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum KeepReason {
    /// The incoming manifest expires sooner than the cached one, and the server did not say
    /// it was a deliberate shortening. Accepting it would let a transient server fault
    /// collapse a customer's offline window.
    WouldShortenEntitlement {
        cached_expires_at_unix: i64,
        incoming_expires_at_unix: i64,
    },
}

/// Decide whether a verified manifest may replace the cached one.
///
/// Pure, and takes instants rather than parsing timestamps: time-dependent behaviour in
/// this workspace is driven by injected values, and parsing the payload belongs to the
/// ticket that decodes it (86ak5mn1d).
///
/// `incoming_degraded` is the server's own word for it:
///
/// - `Some(true)` — degraded: never allowed to shorten the cache.
/// - `Some(false)` — a genuine, deliberate change: allowed to shorten.
/// - `None` — **the server did not say**, which is the situation today because the flag is
///   not in the signed payload. Treated as `Some(true)`, because guessing wrong in the
///   other direction costs a church its offline window mid-service.
pub fn decide_cache_replacement(
    cached_expires_at_unix: Option<i64>,
    incoming_expires_at_unix: i64,
    incoming_degraded: Option<bool>,
) -> CacheDecision {
    let Some(cached) = cached_expires_at_unix else {
        // Nothing cached: anything verified is an improvement on nothing.
        return CacheDecision::Replace;
    };

    if incoming_expires_at_unix >= cached {
        return CacheDecision::Replace;
    }

    // It shortens. Only an explicit "not degraded" from the server permits that.
    if incoming_degraded == Some(false) {
        return CacheDecision::Replace;
    }

    CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
        cached_expires_at_unix: cached,
        incoming_expires_at_unix,
    })
}
