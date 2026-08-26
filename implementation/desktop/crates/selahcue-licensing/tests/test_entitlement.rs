//! The two client-side entitlement rules the server cannot enforce for us.
//!
//! Both come from Sana's review of the catalogue branch, and both share a shape: the server
//! does its half correctly, and the protection only holds if the client does its half.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::entitlement::{
    decide_cache_replacement, Allowance, CacheDecision, GrantScalar, Grants, KeepReason,
    SignedFacts, DEGRADED_MANIFEST_TTL_SECONDS, MAX_GRANT_DIMENSIONS,
};

// The server's clamp, pinned. If it ever grew to something near a licence window, the
// premise of the cache rule below — that a degraded manifest is dramatically shorter —
// would quietly stop holding.
const _: () = assert!(
    DEGRADED_MANIFEST_TTL_SECONDS > 0 && DEGRADED_MANIFEST_TTL_SECONDS < 86_400,
    "a degraded manifest must outlive the incident but never approach a licence window"
);

fn grants() -> Grants {
    Grants::from_pairs([
        ("stage_display".to_string(), Some(GrantScalar::Flag(true))),
        ("cloud_notes".to_string(), Some(GrantScalar::Flag(false))),
        ("saved_themes".to_string(), Some(GrantScalar::Count(25))),
        ("media_library_gb".to_string(), None), // explicit null => unlimited
    ])
}

// --- (a) absent must fail restrictive ---------------------------------------------------

#[test]
fn an_absent_grant_is_denied_and_never_unlimited() {
    // THE control. Server-side, stripping a key breaks the signature — but once the client
    // falls back to a default, the default IS the control. If any dimension defaulted to
    // unlimited, an attacker would gain a capability by DELETING signed data rather than
    // forging it, and deleting is free.
    let g = grants();

    // Positive control first: the map really is populated, so the Denied below is about
    // absence and not about an empty fixture.
    assert_eq!(
        g.len(),
        4,
        "fixture must carry grants or this proves nothing"
    );
    assert!(g.mentions("stage_display"));

    for absent in [
        "a_dimension_that_does_not_exist",
        "device_instances",
        "",
        "STAGE_DISPLAY", // case matters: a near-miss is still absent
    ] {
        assert!(!g.mentions(absent));
        assert_eq!(
            g.allowance(absent),
            Allowance::Denied,
            "absent key {absent:?} must be Denied, never Unlimited"
        );
        assert!(
            !g.allowance(absent).permits_any(),
            "absent key {absent:?} must permit nothing"
        );
        assert_eq!(
            g.allowance(absent).ceiling(),
            Some(0),
            "absent key {absent:?} must read as a zero ceiling, never as 'no limit'"
        );
    }
}

#[test]
fn an_empty_manifest_grants_nothing_at_all() {
    // The shape a degraded issuance has: `resolve_entitlement` returns `values={}` when the
    // catalogue read fails. Every dimension must read Denied — this is the case where a
    // permissive default would hand out the whole product during a server incident.
    let g = Grants::default();
    assert!(g.is_empty());
    for key in [
        "stage_display",
        "cloud_notes",
        "saved_themes",
        "media_library_gb",
    ] {
        assert_eq!(g.allowance(key), Allowance::Denied);
        assert!(!g.allowance(key).permits_any());
    }
}

#[test]
fn the_three_wire_states_stay_distinct() {
    // absent / null / value are three different things and collapsing any pair is a bug.
    let g = grants();
    assert_eq!(g.allowance("media_library_gb"), Allowance::Unlimited);
    assert_eq!(g.allowance("saved_themes"), Allowance::Count(25));
    assert_eq!(g.allowance("stage_display"), Allowance::Flag(true));
    assert_eq!(g.allowance("cloud_notes"), Allowance::Flag(false));
    assert_eq!(g.allowance("nope"), Allowance::Denied);

    // The two that must never be confused: explicit-unlimited and absent.
    assert_ne!(
        g.allowance("media_library_gb"),
        g.allowance("nope"),
        "an explicit `unlimited` and an absent key must never be the same value"
    );
    assert_eq!(g.allowance("media_library_gb").ceiling(), None);
    assert_eq!(g.allowance("nope").ceiling(), Some(0));
}

#[test]
fn an_explicit_false_denies_just_as_firmly_as_absence() {
    let g = grants();
    assert!(!g.allowance("cloud_notes").permits_any());
    assert_eq!(g.allowance("cloud_notes").ceiling(), Some(0));
    // ...but it is still a DIFFERENT state, because the server had an opinion.
    assert!(g.mentions("cloud_notes"));
    assert!(!g.mentions("nope"));
}

#[test]
fn grants_parse_from_the_wire_shape() {
    // `dict(entitlement.published_values)` — bool, int, or null.
    let json = r#"{"stage_display": true, "cloud_notes": false,
                   "saved_themes": 25, "media_library_gb": null}"#;
    let g: Grants = serde_json::from_str(json).unwrap();
    assert_eq!(g.allowance("stage_display"), Allowance::Flag(true));
    assert_eq!(g.allowance("cloud_notes"), Allowance::Flag(false));
    assert_eq!(g.allowance("saved_themes"), Allowance::Count(25));
    assert_eq!(
        g.allowance("media_library_gb"),
        Allowance::Unlimited,
        "wire null is the operator's explicit `unlimited`"
    );
    assert_eq!(
        g.keys(),
        vec![
            "cloud_notes",
            "media_library_gb",
            "saved_themes",
            "stage_display"
        ]
    );
}

#[test]
fn a_dimension_this_build_has_never_heard_of_is_denied_not_assumed() {
    // Grant keys come from catalogue rows, so a new dimension reaches this client with no
    // code change. It must be met exactly as an absent one is.
    let json = r#"{"some_future_dimension": 7}"#;
    let g: Grants = serde_json::from_str(json).unwrap();
    assert_eq!(g.allowance("some_future_dimension"), Allowance::Count(7));
    assert_eq!(g.allowance("another_future_one"), Allowance::Denied);
}

// --- (b) a valid degraded manifest must not evict a longer cached one -------------------

const YEAR: i64 = 365 * 24 * 60 * 60;
const T0: i64 = 1_800_000_000;
const CACHED_LONG_EXPIRY: i64 = T0 + 2 * YEAR;

/// The cached artefact: issued at T0, valid two years, artefact == licence (not degraded).
fn cached() -> SignedFacts {
    SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY, CACHED_LONG_EXPIRY, T0, None, 4)
}

/// A GENUINE shortening: the licence itself now ends sooner and the artefact matches it.
/// Nothing was clamped, so this is not a degraded issuance.
fn genuine_shortening(expiry: i64) -> SignedFacts {
    SignedFacts::from_verified_payload(expiry, expiry, T0 + 3600, None, 4)
}

/// A degraded artefact: issued later, but clamped to the 900s TTL.
fn degraded_refresh(degraded: Option<bool>) -> SignedFacts {
    // The licence still runs two years; only the ARTEFACT is clamped. That pair —
    // `expires_at < license_expires_at` — is the degraded signature.
    // Degraded issuances carry ZERO grants (`resolve_entitlement` returns `values={}`).
    SignedFacts::from_verified_payload(
        T0 + 3600 + DEGRADED_MANIFEST_TTL_SECONDS,
        CACHED_LONG_EXPIRY,
        T0 + 3600,
        degraded,
        0,
    )
}

#[test]
fn nothing_cached_means_anything_verified_is_an_improvement() {
    assert_eq!(
        decide_cache_replacement(None, degraded_refresh(None)),
        CacheDecision::Replace
    );
}

#[test]
fn a_degraded_manifest_never_evicts_a_longer_cached_entitlement() {
    // THE rule. The server clamps a degraded manifest to 900s so a transient fault cannot be
    // frozen into a multi-year credential. That is only half the mechanism: if the client
    // caches the 900s artefact over a multi-year one, a brief server blip collapses a
    // church's offline entitlement to fifteen minutes, mid-service.
    let incoming = degraded_refresh(Some(true));

    // Positive controls: this really is a shortening, and it is NOT a replay — so the
    // refusal below is rule 2 doing the work, not rule 1.
    assert!(incoming.expires_at_unix() < cached().expires_at_unix());
    assert!(incoming.issued_at_unix() > cached().issued_at_unix());

    // The grant rule now fires first, and should: losing every dimension is the worse harm.
    assert_eq!(
        decide_cache_replacement(Some(cached()), incoming),
        CacheDecision::KeepCached(KeepReason::DegradedWouldDropGrants {
            cached_grant_count: 4,
        })
    );

    // With a GRANTLESS cache there are no grants to protect, so the shortening rule is what
    // refuses it — proving that branch is still reachable rather than shadowed for good.
    let grantless_cache =
        SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY, CACHED_LONG_EXPIRY, T0, None, 0);
    assert_eq!(
        decide_cache_replacement(Some(grantless_cache), incoming),
        CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
            cached_expires_at_unix: CACHED_LONG_EXPIRY,
            incoming_expires_at_unix: incoming.expires_at_unix(),
        })
    );
}

#[test]
fn degradation_is_derived_from_the_two_signed_expiries_when_no_flag_is_published() {
    // The premise an earlier version of this module denied. `expires_at` is narrowed below
    // `license_expires_at` ONLY in the degraded branch, so the pair is the signal — no API
    // change and no guessing required.
    assert!(
        degraded_refresh(None).is_degraded(),
        "a clamped artefact under a longer licence IS the degraded signature"
    );
    assert!(
        !cached().is_degraded(),
        "artefact expiry == licence expiry is a normal issuance"
    );
    assert!(
        !genuine_shortening(T0 + 30 * 24 * 60 * 60).is_degraded(),
        "a licence that genuinely ends sooner is not a degraded issuance"
    );

    // An explicit signed flag still wins, so publishing it later changes nothing here.
    let clamped_but_declared_fine = SignedFacts::from_verified_payload(
        T0 + 3600 + DEGRADED_MANIFEST_TTL_SECONDS,
        CACHED_LONG_EXPIRY,
        T0 + 3600,
        Some(false),
        4,
    );
    assert!(!clamped_but_declared_fine.is_degraded());
}

#[test]
fn a_genuine_expiry_shortening_lands_instead_of_pinning_the_entitlement_for_good() {
    // THE bug the blunt rule caused. A shorter-term renewal, a plan term change or an expiry
    // correction was refused PERMANENTLY — no retry, reactivation or operator action would
    // land it — and because the whole manifest was refused, the older and more GENEROUS
    // grants persisted with it. It did not defer an expiry change; it pinned the entitlement.
    let renewal = genuine_shortening(T0 + 30 * 24 * 60 * 60);

    // Positive controls: this really shortens, really is newer, and really is not degraded.
    assert!(renewal.expires_at_unix() < cached().expires_at_unix());
    assert!(renewal.issued_at_unix() > cached().issued_at_unix());
    assert!(!renewal.is_degraded());

    assert_eq!(
        decide_cache_replacement(Some(cached()), renewal),
        CacheDecision::Replace,
        "a genuine licence change must land, or the entitlement is pinned with no way back"
    );
}

#[test]
fn an_explicit_not_degraded_may_shorten_because_that_is_a_real_licence_change() {
    // The narrowing this API is shaped for: once the server publishes the flag inside the
    // signature, a genuine downgrade gets through with no change here.
    let downgrade = SignedFacts::from_verified_payload(
        T0 + 30 * 24 * 60 * 60,
        T0 + 30 * 24 * 60 * 60,
        T0 + 3600,
        Some(false),
        4,
    );
    assert_eq!(
        decide_cache_replacement(Some(cached()), downgrade),
        CacheDecision::Replace
    );
}

#[test]
fn a_longer_or_equal_manifest_always_replaces() {
    // Positive control for the rule as a whole: it must not be a blanket refusal to cache.
    let longer = SignedFacts::from_verified_payload(
        CACHED_LONG_EXPIRY + YEAR,
        CACHED_LONG_EXPIRY + YEAR,
        T0 + 3600,
        None,
        4,
    );
    let equal = SignedFacts::from_verified_payload(
        CACHED_LONG_EXPIRY,
        CACHED_LONG_EXPIRY,
        T0 + 3600,
        None,
        4,
    );
    assert_eq!(
        decide_cache_replacement(Some(cached()), longer),
        CacheDecision::Replace
    );
    assert_eq!(
        decide_cache_replacement(Some(cached()), equal),
        CacheDecision::Replace,
        "an equal window is a refresh, not a shortening"
    );
    // This case previously asserted "even a degraded manifest may replace when it does not
    // shorten" — which encoded the very gap this rule closes. A degraded issuance carries no
    // grants, so replacing a grant-bearing cache with one denies every dimension no matter
    // how far out it expires.
    let longer_but_degraded = SignedFacts::from_verified_payload(
        CACHED_LONG_EXPIRY + YEAR,
        CACHED_LONG_EXPIRY + YEAR + YEAR,
        T0 + 3600,
        None,
        0,
    );
    assert!(longer_but_degraded.is_degraded());
    assert!(longer_but_degraded.expires_at_unix() > cached().expires_at_unix());
    assert_eq!(
        decide_cache_replacement(Some(cached()), longer_but_degraded),
        CacheDecision::KeepCached(KeepReason::DegradedWouldDropGrants {
            cached_grant_count: 4,
        }),
        "a longer window does not license dropping every grant"
    );

    // ...but with nothing to protect, a degraded manifest replaces normally.
    let grantless_cache =
        SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY, CACHED_LONG_EXPIRY, T0, None, 0);
    assert_eq!(
        decide_cache_replacement(Some(grantless_cache), longer_but_degraded),
        CacheDecision::Replace
    );
}

#[test]
fn a_nearly_expired_grant_bearing_cache_is_not_wiped_by_a_degraded_refresh() {
    // The exact probe from review: whenever the cache has less time left than the degraded
    // artefact's TTL, the "does not shorten" branch used to return Replace before degradation
    // was consulted — landing a zero-grant manifest that denied every dimension for up to 900
    // seconds. Bounded, and still the shape this policy exists to prevent.
    let nearly_expired = SignedFacts::from_verified_payload(T0 + 60, T0 + 60, T0 - 100, None, 4);
    let degraded = degraded_refresh(None);

    // Positive controls: the refresh really is longer AND really is degraded, so this is the
    // branch that used to return Replace.
    assert!(degraded.expires_at_unix() > nearly_expired.expires_at_unix());
    assert!(degraded.is_degraded());
    assert!(nearly_expired.carries_grants());

    assert_eq!(
        decide_cache_replacement(Some(nearly_expired), degraded),
        CacheDecision::KeepCached(KeepReason::DegradedWouldDropGrants {
            cached_grant_count: 4,
        }),
        "a degraded refresh must not wipe grants just because the cache is nearly expired"
    );
}

#[test]
fn a_licence_ending_inside_the_ttl_window_reads_as_healthy_and_that_edge_is_pinned() {
    // The edge the module docs describe in prose and nothing tested. When the licence ends
    // inside the 900s window, `min()` picks the LICENCE expiry, so the two signed expiries
    // come out equal and a genuinely degraded issuance reports `is_degraded() == false`.
    //
    // It is benign — shortening to the licence's own end is correct, and the grant rule is
    // what still protects the dimensions — but it is real, reachable, and now pinned so it
    // cannot be discovered as a surprise.
    let licence_ends_soon = T0 + 300; // inside DEGRADED_MANIFEST_TTL_SECONDS
    assert!(licence_ends_soon - T0 < DEGRADED_MANIFEST_TTL_SECONDS);

    let clamped_to_licence =
        SignedFacts::from_verified_payload(licence_ends_soon, licence_ends_soon, T0, None, 0);
    assert!(
        !clamped_to_licence.is_degraded(),
        "equal expiries read as healthy — this is the documented incompleteness of deriving \
         degradation from the expiry pair"
    );

    // And it is safe: the grant rule still refuses to drop a grant-bearing cache.
    assert_eq!(
        decide_cache_replacement(Some(cached()), clamped_to_licence),
        CacheDecision::Replace,
        "a zero-grant but HEALTHY manifest is a real licence state, not a degraded one"
    );
}

// --- (b2) issued_at monotonicity: an older manifest never wins -------------------------

#[test]
fn a_manifest_issued_earlier_than_the_cached_one_is_refused_as_a_replay() {
    // A correctly-signed manifest is still replayable: capture one, serve it later. Without
    // this the newest artefact does not necessarily win, and whoever answers the refresh
    // chooses which past entitlement the client holds.
    let replayed = SignedFacts::from_verified_payload(
        CACHED_LONG_EXPIRY + YEAR,
        CACHED_LONG_EXPIRY + YEAR,
        T0 - 1,
        None,
        4,
    );

    // Positive control: it is LONGER, so rule 2 would happily accept it. Only rule 1 refuses.
    assert!(replayed.expires_at_unix() > cached().expires_at_unix());

    assert_eq!(
        decide_cache_replacement(Some(cached()), replayed),
        CacheDecision::KeepCached(KeepReason::StaleIssuance {
            cached_issued_at_unix: T0,
            incoming_issued_at_unix: T0 - 1,
        }),
        "an older issuance must be refused even when it offers a longer window"
    );
}

#[test]
fn a_replay_cannot_talk_its_way_past_the_shortening_rule_with_a_signed_not_degraded() {
    // Why rule 1 is checked FIRST. `degraded` is inside the signature, so it cannot be
    // forged — but a genuine old manifest that legitimately carried `degraded: false` can be
    // replayed. If the shortening rule ran first, that replay would be accepted.
    let old_but_not_degraded =
        SignedFacts::from_verified_payload(T0 + 60, T0 + 60, T0 - 5000, Some(false), 4);
    assert_eq!(
        decide_cache_replacement(Some(cached()), old_but_not_degraded),
        CacheDecision::KeepCached(KeepReason::StaleIssuance {
            cached_issued_at_unix: T0,
            incoming_issued_at_unix: T0 - 5000,
        }),
        "replay defence must run before anything the incoming manifest asserts"
    );
}

#[test]
fn a_manifest_re_issued_at_the_same_instant_is_still_accepted() {
    // Equal issuance is a re-issue, not a replay — refusing it would wedge a client whose
    // server re-signs within the same second.
    let same_instant = SignedFacts::from_verified_payload(
        CACHED_LONG_EXPIRY + YEAR,
        CACHED_LONG_EXPIRY + YEAR,
        T0,
        None,
        4,
    );
    assert_eq!(
        decide_cache_replacement(Some(cached()), same_instant),
        CacheDecision::Replace
    );
}

#[test]
fn the_artefact_expiry_is_what_the_rule_reads_not_the_licence_expiry() {
    // The payload carries `expires_at` (clamped) AND `license_expires_at` (not). Feeding the
    // licence expiry in would make a degraded manifest look multi-year and defeat the rule
    // entirely — so the accessor is named for the artefact and documented as such.
    let degraded = degraded_refresh(Some(true));
    assert_eq!(
        degraded.expires_at_unix(),
        T0 + 3600 + DEGRADED_MANIFEST_TTL_SECONDS,
        "the clamped artefact expiry is what this policy reads"
    );
    assert!(
        degraded.expires_at_unix() - degraded.issued_at_unix() <= DEGRADED_MANIFEST_TTL_SECONDS,
        "a degraded artefact must live no longer than the server's clamp"
    );
}

// --- traps for the enforcement ticket, pinned so they cannot be discovered the hard way ---

#[test]
fn a_negative_ceiling_survives_intact_so_enforcement_must_compare_not_subtract() {
    // An operator can type -3 into the catalogue. `Some(-3)` is the honest reading, and it is
    // pinned here because the dangerous alternative is silent: `remaining = ceiling - used`
    // yields a negative, and an unsigned cast turns that into a very large allowance.
    let g = Grants::from_pairs([("saved_themes".to_string(), Some(GrantScalar::Count(-3)))]);
    assert_eq!(g.allowance("saved_themes"), Allowance::Count(-3));
    assert_eq!(g.allowance("saved_themes").ceiling(), Some(-3));
    assert!(
        !g.allowance("saved_themes").permits_any(),
        "a negative ceiling must not read as permitting anything"
    );
}

#[test]
fn a_true_flag_has_no_ceiling_which_numeric_enforcement_must_not_read_as_unlimited() {
    // `Flag(true).ceiling()` is None — the same value `Unlimited` gives. A numeric check
    // meeting a bool-typed dimension therefore cannot distinguish them by ceiling alone and
    // must consult the variant.
    let g = Grants::from_pairs([("stage_display".to_string(), Some(GrantScalar::Flag(true)))]);
    assert_eq!(g.allowance("stage_display").ceiling(), None);
    assert_eq!(Allowance::Unlimited.ceiling(), None);
    assert_ne!(
        g.allowance("stage_display"),
        Allowance::Unlimited,
        "the variants stay distinguishable even though their ceilings collide"
    );
}

// --- the grant map is bounded, like its sibling trust store -----------------------------

const _: () = assert!(MAX_GRANT_DIMENSIONS >= 8 && MAX_GRANT_DIMENSIONS <= 1024);

#[test]
fn the_grant_map_is_bounded_and_an_over_cap_manifest_is_refused() {
    // `Grants` is fed straight from the payload and, in 86ak5mn1d, decoded BEFORE the
    // signature is checked — so for that window its size is an attacker's choice. Its
    // sibling `TrustedKeys` has been cap-pinned since it was written; this had no bound.
    let within: String = (0..MAX_GRANT_DIMENSIONS)
        .map(|i| format!("\"d{i}\": true"))
        .collect::<Vec<_>>()
        .join(",");
    let at_cap: Grants = serde_json::from_str(&format!("{{{within}}}")).unwrap();

    // Positive control FIRST: exactly at the cap parses and every key is retrievable, so the
    // refusal below is a boundary and not a blanket rejection.
    assert_eq!(at_cap.len(), MAX_GRANT_DIMENSIONS);
    assert_eq!(at_cap.allowance("d0"), Allowance::Flag(true));
    assert_eq!(
        at_cap.allowance(&format!("d{}", MAX_GRANT_DIMENSIONS - 1)),
        Allowance::Flag(true)
    );

    let over: String = (0..MAX_GRANT_DIMENSIONS + 1)
        .map(|i| format!("\"d{i}\": true"))
        .collect::<Vec<_>>()
        .join(",");
    let refused = serde_json::from_str::<Grants>(&format!("{{{over}}}"));
    assert!(
        refused.is_err(),
        "a manifest carrying more than {MAX_GRANT_DIMENSIONS} dimensions must be refused"
    );
    assert!(
        refused.unwrap_err().to_string().contains("grant"),
        "the refusal should say what was refused"
    );
}

#[test]
fn the_cap_is_cross_pinned_to_the_servers_own_bound() {
    // The server asserts MAX_GRANT_DIMENSIONS = 64 (apps/catalogue/models.py:90 on
    // origin/feat/86ak10abc-product-catalogue). A client cap BELOW it would refuse manifests
    // the server considers valid.
    assert_eq!(
        MAX_GRANT_DIMENSIONS, 64,
        "cross-pinned to the server's MAX_GRANT_DIMENSIONS; change both together"
    );
}
