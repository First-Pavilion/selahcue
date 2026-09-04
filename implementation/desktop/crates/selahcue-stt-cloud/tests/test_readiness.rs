//! Readiness: the crate API ticket 86akby7th renders.
//!
//! The point of these tests is that the three states stay **three**. A boolean would conflate
//! "this build has no cloud transcription" with "you have not put a key in `.env`", and only
//! one of those is something an operator can act on.

#![allow(clippy::unwrap_used)]

use selahcue_stt_cloud::readiness::DEFAULT_MODEL;
use selahcue_stt_cloud::{
    readiness, readiness_from, transport_in_build, CloudSttReadiness, CredentialPresent,
    TransportInBuild, DEEPGRAM_API_KEY_VAR,
};

fn compiled(yes: bool) -> TransportInBuild {
    TransportInBuild::observed(yes)
}

fn keyed(yes: bool) -> CredentialPresent {
    CredentialPresent::observed(yes)
}

#[test]
fn readiness_is_a_tri_state_over_the_two_things_that_can_be_missing() {
    assert_eq!(
        readiness_from(compiled(false), keyed(false)),
        CloudSttReadiness::NotInBuild,
        "a build without the transport must say so"
    );
    assert_eq!(
        readiness_from(compiled(false), keyed(true)),
        CloudSttReadiness::NotInBuild,
        "PRECEDENCE: a key present in a build that cannot stream must still report NotInBuild. \
         Reporting KeyMissing would send the operator to edit a .env file that cannot help \
         them, and would put the panel's report out of step with what the build can do"
    );
    assert_eq!(
        readiness_from(compiled(true), keyed(false)),
        CloudSttReadiness::KeyMissing,
        "the actionable middle state collapsed; this is the whole reason readiness is not a \
         boolean"
    );
    assert_eq!(
        readiness_from(compiled(true), keyed(true)),
        CloudSttReadiness::Ready
    );
}

#[test]
fn the_two_readiness_inputs_cannot_be_transposed() {
    // Both inputs are yes/no facts. As bare booleans a caller could swap them and the code
    // would still compile and still read correctly, while reporting NotInBuild for a build
    // that merely lacks a key. The types close that ONLY because the producers return them —
    // wrapping at the call site would be a label the caller could misapply.
    //
    // The real assertion here is a compile-time one and lives in the type signature; what this
    // test can check is that the producers really are the typed source, so the property is not
    // resting on a `TransportInBuild(...)` conversion someone added at a boundary.
    let from_producer: TransportInBuild = transport_in_build();
    assert_eq!(
        from_producer.get(),
        cfg!(feature = "deepgram"),
        "transport_in_build() does not report this build, so it is not the single source of \
         that fact and readiness() is reading it from somewhere else"
    );
    assert_eq!(
        readiness_from(from_producer, keyed(true)).is_ready(),
        cfg!(feature = "deepgram")
    );
}

#[test]
fn only_the_ready_state_reports_ready() {
    assert!(CloudSttReadiness::Ready.is_ready());
    assert!(!CloudSttReadiness::KeyMissing.is_ready());
    assert!(!CloudSttReadiness::NotInBuild.is_ready());
}

#[test]
fn the_provider_is_named_exactly_when_it_is_available() {
    // The invariant the sermon-notes lane pins on its own half of this panel:
    // `provider.is_some() == available`. Tested both directions — no claiming availability
    // without naming the provider, and no naming a provider while reporting unavailable.
    // Driven over the states THEMSELVES, not over environment- or cfg-derived values: a
    // control is dead when its inputs cannot vary in the build that runs it, however many
    // iterations its loop has.
    let mut exercised = Vec::new();
    for (transport, credential) in [(false, false), (true, false), (true, true)] {
        let state = readiness_from(compiled(transport), keyed(credential));
        let status = state.status();
        assert_eq!(
            status.provider.is_some(),
            status.ready,
            "{state:?} breaks provider.is_some() == ready — the one screen whose entire job \
             is trust would either claim availability it cannot back or name a provider it \
             says is unavailable"
        );
        exercised.push(state);
    }

    // The positive control. Without it the loop above is satisfied by three inputs that all
    // land in the same state, which is exactly how a two-way invariant test ends up asserting
    // nothing about two of its three arms.
    exercised.sort_by_key(|s| format!("{s:?}"));
    exercised.dedup();
    assert_eq!(
        exercised.len(),
        3,
        "the invariant loop reached only {:?} — it did not exercise all three readiness \
         states, so the arms it missed are untested",
        exercised
    );

    let ready = CloudSttReadiness::Ready.status();
    let provider = ready.provider.expect("the ready state names its provider");
    assert_eq!(provider.kind, "deepgram");
    assert_eq!(provider.name, "Deepgram");
    assert_eq!(provider.model, DEFAULT_MODEL);
    assert_eq!(provider.model, "nova-3");
    assert!(
        provider.developer_key,
        "Phase 1 runs on a developer key; reporting otherwise would hide that this machine \
         holds the credential"
    );
}

#[test]
fn the_state_strings_match_the_two_surfaces_that_consume_them() {
    // Left column mirrors the on-device readiness reply the Pre-service Check renders; right
    // column mirrors the sermon-notes lane's `cloud_status`. Both are contracts with code in
    // another crate, so they are pinned here rather than left to drift.
    assert_eq!(CloudSttReadiness::Ready.state(), "ready");
    assert_eq!(CloudSttReadiness::KeyMissing.state(), "key_missing");
    assert_eq!(CloudSttReadiness::NotInBuild.state(), "not_in_build");

    assert_eq!(
        CloudSttReadiness::Ready.provider_status(),
        "direct_provider"
    );
    assert_eq!(
        CloudSttReadiness::KeyMissing.provider_status(),
        "key_missing"
    );
    assert_eq!(
        CloudSttReadiness::NotInBuild.provider_status(),
        "not_configured"
    );
}

#[test]
fn the_unavailable_states_say_what_to_do_about_it() {
    let key_missing = CloudSttReadiness::KeyMissing.status();
    assert!(
        key_missing.detail.contains(DEEPGRAM_API_KEY_VAR),
        "the actionable state does not name the variable to set: {}",
        key_missing.detail
    );
    assert!(
        key_missing.detail.contains(".env"),
        "the actionable state does not say where to set it: {}",
        key_missing.detail
    );
    assert!(
        key_missing.detail.contains("Deepgram"),
        "the operator is asked to configure a provider that is never named: {}",
        key_missing.detail
    );
    assert_eq!(key_missing.key_variable, DEEPGRAM_API_KEY_VAR);

    let not_in_build = CloudSttReadiness::NotInBuild.status();
    assert!(
        !not_in_build.detail.contains(DEEPGRAM_API_KEY_VAR),
        "a build that cannot stream at all is telling the operator to go and set a key: {}",
        not_in_build.detail
    );
    assert!(
        not_in_build.detail.contains("on-device"),
        "the message does not reassure the operator that on-device transcription still \
         works: {}",
        not_in_build.detail
    );
}

#[test]
fn this_builds_readiness_agrees_with_whether_the_transport_is_compiled_in() {
    // `readiness()` reads a `cfg` and the process environment, so only one of its three
    // states is observable from any single test run. What can be asserted in both builds is
    // the relationship between the two.
    let observed = readiness();
    if transport_in_build().get() {
        assert_ne!(
            observed,
            CloudSttReadiness::NotInBuild,
            "the deepgram feature is compiled in but readiness reports NotInBuild"
        );
    } else {
        assert_eq!(
            observed,
            CloudSttReadiness::NotInBuild,
            "the deepgram feature is not compiled in but readiness claims otherwise; a build \
             with no socket would offer the operator cloud transcription"
        );
    }
    assert_eq!(
        observed.is_ready(),
        observed.status().ready,
        "the enum and the rendered status disagree about readiness"
    );
}
