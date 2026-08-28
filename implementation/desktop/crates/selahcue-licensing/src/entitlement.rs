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
//! # (b) A valid degraded manifest must not evict a longer cached one, nor strip its grants
//!
//! FR-518's keep-the-previous-cache rule covers manifests that fail *verification*. It does
//! not cover one that verifies perfectly and is simply **shorter**. The server issues such
//! a manifest by design: when the catalogue cannot be read it still signs one — refusing
//! would deny a live service over a server-side fault — but clamps it to
//! [`DEGRADED_MANIFEST_TTL_SECONDS`] so a transient failure cannot be frozen into a
//! multi-year offline credential (`apps/entitlements/services.py:122-133` **on
//! `origin/feat/86ak10abc-product-catalogue`** — on `main` that file is 101 lines and has
//! no grants, no `degraded` and no clamp).
//!
//! That protection has a matching client obligation. If a desktop holding a multi-year
//! cached entitlement replaces it with a valid 15-minute one, a brief server blip collapses
//! a church's offline entitlement to fifteen minutes — mid-service, on a product whose
//! central promise is offline-first (NFR-015, CON-2). [`decide_cache_replacement`] refuses
//! that: **a shorter window never evicts a longer cached one.** Keep serving the cached
//! grant and retry.
//!
//! ## The payload already tells us it was degraded — derived, not guessed
//!
//! An earlier version of this module said the client "cannot distinguish short-because-the-
//! catalogue-failed from short-because-the-licence-is-short", and refused **all** shortening
//! on that basis. That premise was wrong, and the rule built on it was harmful.
//!
//! The signed payload carries **two** expiries:
//!
//! - `license_expires_at` — the true licence expiry, **never clamped**
//! - `expires_at` — the artefact expiry, clamped **only** in the degraded branch
//!   (`min(..., now + DEGRADED_MANIFEST_TTL_SECONDS)`, guarded by `if entitlement.degraded:`)
//!
//! So **`expires_at < license_expires_at` implies degraded.** Sound — nothing else narrows
//! the artefact below the licence — and complete except when the licence itself ends inside
//! the TTL window, where the clamp picks the licence expiry and the pair comes out equal.
//!
//! **That blind spot is one-sided, and it is only harmless for one of the two rules.** A
//! derived `false` means *no evidence of degradation*, not *healthy*. For the shortening rule
//! it costs nothing: the only thing it lets through is shortening to the licence's own end,
//! which is correct anyway. For **grant loss** the same reasoning does not hold — a degraded,
//! zero-grant issuance inside the licence tail reads healthy and would wipe every dimension.
//! So the grant rule keys on the grant map itself rather than on this predicate; see
//! [`decide_cache_replacement`], including what that costs a genuine zero-grant licence while
//! no server publishes the explicit flag. Both fields are on `main`
//! (`apps/entitlements/services.py:71,78`, where they are equal because that revision has no
//! degradation path) and on `origin/feat/86ak10abc-product-catalogue` (`:144,:169`), so the
//! signal is stable and needs no API change.
//!
//! ### What refusing all shortening actually cost
//!
//! Not, as I first wrote, "a deferred downgrade". A **genuine** expiry shortening — a
//! shorter-term renewal, a plan term change, an expiry correction — was refused
//! **permanently and unrecoverably**: no retry, reactivation or operator action would land
//! it. And because the *whole manifest* was refused, the older and more **generous grants**
//! rode along and persisted with it. The rule did not defer an expiry change; it pinned the
//! entire entitlement.
//!
//! [`SignedFacts::is_degraded`] therefore derives the answer from the two signed timestamps,
//! and an explicit `degraded` field takes precedence if the server ever publishes one inside
//! the signature. Either way the input is **signed payload bytes only** — never a header, a
//! status code, or a field the view appends outside the envelope.

use serde::Deserialize;
use std::collections::BTreeMap;

/// The server's clamp on a degraded manifest (`entitlements/services.py:83` on
/// `origin/feat/86ak10abc-product-catalogue`; the clamp does not exist on `main` yet). Mirrored for
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
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Grants(BTreeMap<String, Option<GrantScalar>>);

/// The most grant dimensions this client will accept from one manifest.
///
/// Cross-pinned to the server's own bound (`apps/catalogue/models.py:90` on
/// `origin/feat/86ak10abc-product-catalogue`, `MAX_GRANT_DIMENSIONS = 64`). The sibling
/// [`crate::trust::TrustedKeys`] has carried a compile-pinned cap since it was written; this
/// map is the same class of unbounded, wire-fed collection and had none.
///
/// It matters most in the window this crate does not own yet: 86ak5mn1d decodes the payload
/// **before** the signature is checked, so for that moment the map's size is an attacker's
/// choice rather than the server's.
pub const MAX_GRANT_DIMENSIONS: usize = 64;

// Pinned at compile time so the cap cannot drift below the dimensions the product actually
// decides on, mirroring the server's own `assert MAX_GRANT_DIMENSIONS >= 8`.
const _: () = assert!(
    MAX_GRANT_DIMENSIONS >= 8,
    "MAX_GRANT_DIMENSIONS must leave room for the decided dimensions"
);

impl<'de> Deserialize<'de> for Grants {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct BoundedGrants;

        impl<'de> serde::de::Visitor<'de> for BoundedGrants {
            type Value = Grants;

            fn expecting(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
                write!(f, "at most {MAX_GRANT_DIMENSIONS} grant dimensions")
            }

            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut access: A,
            ) -> Result<Grants, A::Error> {
                let mut map = BTreeMap::new();
                // Counted as entries arrive and refused on the one that crosses the cap, so
                // an over-large document is abandoned mid-parse rather than allocated in
                // full and measured afterwards. Checking `len()` after collecting would
                // bound the value while leaving the *work* unbounded, which is the half that
                // matters against untrusted input.
                while let Some((key, value)) = access.next_entry::<String, Option<GrantScalar>>()? {
                    if map.len() >= MAX_GRANT_DIMENSIONS {
                        return Err(serde::de::Error::custom(format!(
                            "manifest carries more than {MAX_GRANT_DIMENSIONS} grant \
                             dimensions; refusing to decode the rest"
                        )));
                    }
                    map.insert(key, value);
                }
                Ok(Grants(map))
            }
        }

        deserializer.deserialize_map(BoundedGrants)
    }
}

impl Grants {
    /// Build from decoded pairs. `None` is the wire's `null` — unlimited.
    ///
    /// In-process constructor: the cap is enforced where untrusted bytes enter, in
    /// `Deserialize`. Callers building a map in memory are not the threat this bounds.
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
    license_expires_at_unix: i64,
    issued_at_unix: i64,
    degraded: Option<bool>,
    grant_count: usize,
}

impl SignedFacts {
    /// Build from values read out of a payload whose signature has been verified.
    ///
    /// `degraded` is `None` when the payload does not carry the field — which is every
    /// payload today, since the server publishes it only to the audit record.
    pub fn from_verified_payload(
        expires_at_unix: i64,
        license_expires_at_unix: i64,
        issued_at_unix: i64,
        degraded: Option<bool>,
        grant_count: usize,
    ) -> Self {
        SignedFacts {
            expires_at_unix,
            license_expires_at_unix,
            issued_at_unix,
            degraded,
            grant_count,
        }
    }

    /// How many grant dimensions the payload carried.
    ///
    /// A degraded issuance carries **zero**: `resolve_entitlement`'s failure path returns
    /// `values={}`. Combined with this crate's own rule that an absent grant is
    /// [`Allowance::Denied`], caching such a manifest denies every dimension.
    pub fn grant_count(&self) -> usize {
        self.grant_count
    }

    /// Whether the payload carried any grants at all.
    pub fn carries_grants(&self) -> bool {
        self.grant_count > 0
    }

    /// The **licence** expiry — never clamped, whatever happened server-side.
    pub fn license_expires_at_unix(&self) -> i64 {
        self.license_expires_at_unix
    }

    /// Whether this issuance was degraded.
    ///
    /// An explicit signed `degraded` wins when present. Otherwise it is **derived**: the
    /// artefact expiry is narrowed below the licence expiry only in the degraded branch, so
    /// `expires_at < license_expires_at` is exactly that condition. See the module docs for
    /// why this is sound, and for what the previous guess-nothing rule cost.
    pub fn is_degraded(&self) -> bool {
        self.degraded
            .unwrap_or(self.expires_at_unix < self.license_expires_at_unix)
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
    /// A newer-but-shorter honest manifest passes this rule and is judged by rule 2, so the
    /// bound this provides is on REPLAY specifically, not on honest deferral. (An earlier
    /// version of this comment claimed deferral was bounded "to the refresh cadence", which
    /// was wrong: before degradation was derived rather than assumed, a refused shortening
    /// persisted until the cached manifest expired.)
    StaleIssuance {
        cached_issued_at_unix: i64,
        incoming_issued_at_unix: i64,
    },
    /// The incoming manifest **carries no grants** while the cache does, and the server did
    /// not sign that the drop is deliberate.
    ///
    /// A degraded manifest carries none — `resolve_entitlement`'s failure path returns
    /// `values={}` — and this crate's own rule is that an absent grant is denied. So caching
    /// one over a grant-bearing manifest **denies every dimension** until it expires.
    ///
    /// Expiry alone did not catch this: whenever the cache had less time left than the
    /// degraded artefact's TTL, the "does not shorten" branch returned `Replace` before
    /// degradation was ever consulted. Bounded by the 900s clamp, but a customer losing every
    /// feature for a quarter of an hour because a server had a bad minute is precisely the
    /// shape this policy exists to prevent.
    ///
    /// **Nor did `is_degraded()` catch it**, which is why this rule keys on the empty grant
    /// map rather than on degradation. That predicate is one-sided — see
    /// [`decide_cache_replacement`] — and a degraded issuance inside the licence tail reads
    /// healthy through it. The grant map is the entity; degradation is only ever the reason
    /// one is empty.
    DegradedWouldDropGrants { cached_grant_count: usize },
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
/// 2. **A replacement never drops grants** unless the server signs that the drop is
///    deliberate. An empty grant map over a grant-bearing cache denies every dimension until
///    it expires, whatever the incoming expiry says.
/// 3. **A degraded issuance may not shorten.** A genuine licence change may, and must —
///    refusing it would pin the whole entitlement, generous grants included, with no way
///    back. Degradation is read from [`SignedFacts::is_degraded`], which derives it from the
///    two signed expiries when the server publishes no explicit flag.
///
/// # Why rule 2 reads the grant map and rule 3 reads degradation
///
/// [`SignedFacts::is_degraded`]'s derived form is **sound but incomplete**: `expires_at <
/// license_expires_at` implies degraded, but the converse fails whenever the licence ends
/// inside the TTL window, where the server's `min()` picks the licence expiry and the two
/// timestamps come out equal. `is_degraded() == false` therefore means *no evidence of
/// degradation*, never *known healthy*.
///
/// That is tolerable for rule 3, where the blind spot only ever permits shortening to the
/// licence's own end — correct anyway. It is **not** tolerable for rule 2, where the harm is
/// grant loss: a degraded, zero-grant issuance inside the licence tail reads healthy, and
/// keying rule 2 on that proxy let it through to rule 3 and deny every dimension. So rule 2
/// keys on the entity that is at stake and sits on the same struct —
/// [`SignedFacts::carries_grants`] — and spends only an explicit signed `degraded: false` as
/// permission to drop.
///
/// # The residual, with its actual cost
///
/// While no server publishes the `degraded` field, a *genuine* zero-grant licence is refused
/// too, because on the wire it is identical to a degraded issuance. An earlier version of
/// this paragraph said that "defers such a licence; it does not extend anything, since the
/// cached artefact keeps its own expiry". **That is only true when the offered manifest is no
/// longer than the cache**, and the test written to demonstrate it used equal expiries on
/// both sides — the one case where the claim holds. It is false in general.
///
/// Rule 2 runs *before* the expiry comparison, so a zero-grant **renewal that extends the
/// licence** is refused entirely and the client keeps the shorter window. QA measured a kept
/// window of 2 592 000s against an offered 63 072 000s: **700 days forgone**, with a valid
/// signed manifest refused. When the cache then expires the client has nothing.
///
/// **And the refusal does not clear on its own.** Every honest refresh carrying the same
/// zero-grant shape is refused the same way — QA measured 12 of 12 successive refreshes
/// refused — so the deferral is bounded by the cached artefact's own expiry, not by the
/// refresh cadence. No retry, reactivation or operator action lands such a manifest. That is
/// the same shape the module docs call harmful about the **previous** rule, which pinned the
/// entitlement over expiry; this rule has its own version of it over grants. The difference
/// is the direction of failure, not the presence of the trap.
///
/// This is a deliberate consequence of refusing drops without signed permission, and it is
/// fail-closed — the client keeps capability it was legitimately granted rather than losing
/// every dimension to a server's bad minute. It is recorded here rather than fixed here.
///
/// The clean fix is server-side: publish `degraded` inside the signature, which
/// [`SignedFacts::is_degraded`] already prefers over the derived signal. **No server does
/// today**, so the recovery path for everything above depends on a change that does not yet
/// exist.
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

    // Rule 2 — GRANT LOSS. Keyed on the entity that is actually at stake, and it sits right
    // here on the facts: would this replacement drop the grants the client is holding?
    // Checked before the expiry comparison because a degraded artefact can easily outlive a
    // nearly-expired cache, and the expiry branch would then accept it and silently drop
    // every grant.
    //
    // This deliberately does NOT key on `is_degraded()`, which is a PROXY for the harm and a
    // one-sided one. The derived form is SOUND but INCOMPLETE: `expires_at <
    // license_expires_at` implies degraded, but the converse does not hold, because a licence
    // ending inside the TTL window makes the server's `min()` pick the licence expiry and the
    // two signed timestamps come out equal. So `is_degraded() == false` means "no evidence of
    // degradation", NEVER "known healthy" — and it must not be spent as a licence to drop
    // grants. Keyed on the proxy, a genuinely degraded zero-grant issuance inside the licence
    // tail read healthy, fell through to rule 3, replaced the cache and denied every
    // dimension. The incompleteness was only ever reasoned about for rule 3, where shortening
    // to the licence's own end is correct anyway; for grant loss that reasoning does not hold.
    //
    // The escape hatch is the server's own signed word, not the derived signal: only an
    // explicit `degraded: false` INSIDE the signature sanctions dropping grants. What that
    // costs while no server publishes the field — including a longer zero-grant renewal being
    // refused outright, and the refusal not clearing on retry — is on this function's own doc
    // comment, under "The residual, with its actual cost".
    let would_drop_grants = cached.carries_grants() && !incoming.carries_grants();
    let server_signed_that_the_drop_is_genuine = incoming.degraded == Some(false);
    if would_drop_grants && !server_signed_that_the_drop_is_genuine {
        return CacheDecision::KeepCached(KeepReason::DegradedWouldDropGrants {
            cached_grant_count: cached.grant_count,
        });
    }

    // Rule 3 — never shorten without the server saying so.
    if incoming.expires_at_unix >= cached.expires_at_unix {
        return CacheDecision::Replace;
    }
    // It shortens. Only a DEGRADED issuance is refused; a genuine licence change must land,
    // or the entitlement is pinned for good — grants and all.
    if !incoming.is_degraded() {
        return CacheDecision::Replace;
    }

    CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
        cached_expires_at_unix: cached.expires_at_unix,
        incoming_expires_at_unix: incoming.expires_at_unix,
    })
}
