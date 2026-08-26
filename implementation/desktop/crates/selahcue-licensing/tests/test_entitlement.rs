//! The two client-side entitlement rules the server cannot enforce for us.
//!
//! Both come from Sana's review of the catalogue branch, and both share a shape: the server
//! does its half correctly, and the protection only holds if the client does its half.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::entitlement::{
    decide_cache_replacement, Allowance, CacheDecision, GrantScalar, Grants, KeepReason,
    SignedFacts, DEGRADED_MANIFEST_TTL_SECONDS,
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

/// The cached artefact: issued at T0, valid two years.
fn cached() -> SignedFacts {
    SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY, T0, None)
}

/// A degraded artefact: issued later, but clamped to the 900s TTL.
fn degraded_refresh(degraded: Option<bool>) -> SignedFacts {
    SignedFacts::from_verified_payload(
        T0 + 3600 + DEGRADED_MANIFEST_TTL_SECONDS,
        T0 + 3600,
        degraded,
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

    assert_eq!(
        decide_cache_replacement(Some(cached()), incoming),
        CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
            cached_expires_at_unix: CACHED_LONG_EXPIRY,
            incoming_expires_at_unix: incoming.expires_at_unix(),
        })
    );
}

#[test]
fn the_flag_being_absent_is_treated_as_degraded_because_the_server_does_not_publish_it() {
    // Today `degraded` reaches the audit record and a log line but NOT the signed payload,
    // so the client always sees `None`. Guessing "not degraded" would cost a church its
    // offline window over a server blip; guessing "degraded" defers an honest downgrade to
    // the next refresh, which the issued_at rule bounds.
    assert_eq!(
        decide_cache_replacement(Some(cached()), degraded_refresh(None)),
        decide_cache_replacement(Some(cached()), degraded_refresh(Some(true))),
        "an unstated flag must behave exactly as a stated `degraded`"
    );
}

#[test]
fn an_explicit_not_degraded_may_shorten_because_that_is_a_real_licence_change() {
    // The narrowing this API is shaped for: once the server publishes the flag inside the
    // signature, a genuine downgrade gets through with no change here.
    let downgrade =
        SignedFacts::from_verified_payload(T0 + 30 * 24 * 60 * 60, T0 + 3600, Some(false));
    assert_eq!(
        decide_cache_replacement(Some(cached()), downgrade),
        CacheDecision::Replace
    );
}

#[test]
fn a_longer_or_equal_manifest_always_replaces() {
    // Positive control for the rule as a whole: it must not be a blanket refusal to cache.
    let longer = SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY + YEAR, T0 + 3600, None);
    let equal = SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY, T0 + 3600, None);
    assert_eq!(
        decide_cache_replacement(Some(cached()), longer),
        CacheDecision::Replace
    );
    assert_eq!(
        decide_cache_replacement(Some(cached()), equal),
        CacheDecision::Replace,
        "an equal window is a refresh, not a shortening"
    );
    let longer_but_degraded =
        SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY + YEAR, T0 + 3600, Some(true));
    assert_eq!(
        decide_cache_replacement(Some(cached()), longer_but_degraded),
        CacheDecision::Replace,
        "even a degraded manifest may replace when it does not shorten"
    );
}

// --- (b2) issued_at monotonicity: an older manifest never wins -------------------------

#[test]
fn a_manifest_issued_earlier_than_the_cached_one_is_refused_as_a_replay() {
    // A correctly-signed manifest is still replayable: capture one, serve it later. Without
    // this the newest artefact does not necessarily win, and whoever answers the refresh
    // chooses which past entitlement the client holds.
    let replayed = SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY + YEAR, T0 - 1, None);

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
    let old_but_not_degraded = SignedFacts::from_verified_payload(T0 + 60, T0 - 5000, Some(false));
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
    let same_instant = SignedFacts::from_verified_payload(CACHED_LONG_EXPIRY + YEAR, T0, None);
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
