//! The two client-side entitlement rules the server cannot enforce for us.
//!
//! Both come from Sana's review of the catalogue branch, and both share a shape: the server
//! does its half correctly, and the protection only holds if the client does its half.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::entitlement::{
    decide_cache_replacement, Allowance, CacheDecision, GrantScalar, Grants, KeepReason,
    DEGRADED_MANIFEST_TTL_SECONDS,
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
const CACHED_LONG: i64 = 1_800_000_000 + 2 * YEAR;

#[test]
fn nothing_cached_means_anything_verified_is_an_improvement() {
    assert_eq!(
        decide_cache_replacement(None, 1_800_000_000 + DEGRADED_MANIFEST_TTL_SECONDS, None),
        CacheDecision::Replace
    );
}

#[test]
fn a_degraded_manifest_never_evicts_a_longer_cached_entitlement() {
    // THE rule. The server clamps a degraded manifest to 900s so a transient fault cannot
    // be frozen into a multi-year credential. That protection is only half the mechanism:
    // if the client caches the 900s artefact over a multi-year one, a brief server blip
    // collapses a church's offline entitlement to fifteen minutes, mid-service.
    let incoming = 1_800_000_000 + DEGRADED_MANIFEST_TTL_SECONDS;

    // Positive control: this really is a shortening, or the assertion below is vacuous.
    assert!(
        incoming < CACHED_LONG,
        "fixture must actually shorten the window"
    );

    for flag in [Some(true), None] {
        assert_eq!(
            decide_cache_replacement(Some(CACHED_LONG), incoming, flag),
            CacheDecision::KeepCached(KeepReason::WouldShortenEntitlement {
                cached_expires_at_unix: CACHED_LONG,
                incoming_expires_at_unix: incoming,
            }),
            "a shortening manifest with degraded={flag:?} must not evict the cache"
        );
    }
}

#[test]
fn the_flag_being_absent_is_treated_as_degraded_because_the_server_does_not_publish_it() {
    // Today `degraded` reaches the audit record and a log line but NOT the signed payload,
    // so the client always sees `None`. Guessing "not degraded" would cost a church its
    // offline window over a server blip; guessing "degraded" costs a delayed legitimate
    // shortening, which the next successful refresh corrects.
    let incoming = 1_800_000_000 + DEGRADED_MANIFEST_TTL_SECONDS;
    assert_eq!(
        decide_cache_replacement(Some(CACHED_LONG), incoming, None),
        decide_cache_replacement(Some(CACHED_LONG), incoming, Some(true)),
        "an unstated flag must behave exactly as a stated `degraded`"
    );
}

#[test]
fn an_explicit_not_degraded_may_shorten_because_that_is_a_real_licence_change() {
    // The narrowing this API is shaped for: once the server publishes the flag, a genuine
    // downgrade gets through without any change here.
    let incoming = 1_800_000_000 + 30 * 24 * 60 * 60;
    assert_eq!(
        decide_cache_replacement(Some(CACHED_LONG), incoming, Some(false)),
        CacheDecision::Replace,
        "a deliberate, server-declared shortening is a real licence change"
    );
}

#[test]
fn a_longer_or_equal_manifest_always_replaces() {
    // Positive control for the rule as a whole: it must not be a blanket refusal to cache.
    let longer = CACHED_LONG + YEAR;
    assert_eq!(
        decide_cache_replacement(Some(CACHED_LONG), longer, None),
        CacheDecision::Replace
    );
    assert_eq!(
        decide_cache_replacement(Some(CACHED_LONG), CACHED_LONG, None),
        CacheDecision::Replace,
        "an equal window is a refresh, not a shortening"
    );
    assert_eq!(
        decide_cache_replacement(Some(CACHED_LONG), longer, Some(true)),
        CacheDecision::Replace,
        "even a degraded manifest may replace when it does not shorten"
    );
}
