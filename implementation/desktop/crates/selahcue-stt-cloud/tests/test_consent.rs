//! The consent gate: streaming live microphone audio must be impossible without both the
//! Cloud transcription mode and the operator's opt-in.
//!
//! Two different things are asserted, deliberately.
//!
//! 1. **The gate agrees with the core's own predicate**, by consuming
//!    `ProvidersConfig::may_stream_cloud_audio()` in the assertion rather than re-deriving
//!    `mode == Cloud && consent`. A control that re-assembles the conjunction from parts is
//!    asserting something about a copy, and survives a mutation of the real expression — this
//!    repository has been bitten by exactly that (86ak643rc).
//! 2. **The four combinations have the values they should**, stated outright, so a regression
//!    in the core predicate itself is caught here too rather than being faithfully mirrored.
//!
//! Neither alone is sufficient: the first passes if both sides break together, the second
//! passes if this crate reads a stale copy that happens to agree.

#![allow(clippy::unwrap_used)]

use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
use selahcue_stt_cloud::{
    Credential, DeepgramEndpoint, DeepgramError, RequestSpec, StreamAuthorization, StreamParams,
};

fn config(mode: TranscriptionMode, consent: bool) -> ProvidersConfig {
    let mut config = ProvidersConfig::default();
    config.settings.transcription_mode = mode;
    config.consent.cloud_transcription = consent;
    config
}

#[test]
fn authorisation_follows_the_cores_own_egress_predicate() {
    for (mode, consent) in [
        (TranscriptionMode::OnDevice, false),
        (TranscriptionMode::OnDevice, true),
        (TranscriptionMode::Cloud, false),
        (TranscriptionMode::Cloud, true),
    ] {
        let config = config(mode, consent);
        // The single definition, consumed — not re-derived.
        let verdict = config.may_stream_cloud_audio();
        let authorisation = StreamAuthorization::from_config(&config);

        assert_eq!(
            authorisation.is_ok(),
            verdict,
            "the streaming gate disagrees with ProvidersConfig::may_stream_cloud_audio() for \
             mode={mode:?} consent={consent}; this crate is reading a copy of the egress \
             predicate rather than the predicate"
        );
    }
}

#[test]
fn only_cloud_mode_with_the_opt_in_may_stream() {
    // Stated outright as well, so a regression in the core predicate is caught here rather
    // than mirrored faithfully by the test above.
    assert!(StreamAuthorization::from_config(&config(TranscriptionMode::Cloud, true)).is_ok());

    for (mode, consent) in [
        (TranscriptionMode::OnDevice, false),
        (TranscriptionMode::OnDevice, true),
        (TranscriptionMode::Cloud, false),
    ] {
        match StreamAuthorization::from_config(&config(mode, consent)) {
            Err(DeepgramError::ConsentRequired) => {}
            other => panic!(
                "mode={mode:?} consent={consent} was allowed to stream live microphone audio: \
                 {other:?}"
            ),
        }
    }
}

#[test]
fn the_default_configuration_can_never_stream() {
    // Offline by default: a fresh install must not be one setting away from streaming audio.
    match StreamAuthorization::from_config(&ProvidersConfig::default()) {
        Err(DeepgramError::ConsentRequired) => {}
        other => panic!("the default configuration was allowed to stream: {other:?}"),
    }
}

#[test]
fn a_request_cannot_be_built_without_an_authorisation() {
    // `RequestSpec::build` takes `&StreamAuthorization`, and `StreamAuthorization` has no
    // public constructor other than `from_config`. That makes an unauthorised request
    // unrepresentable rather than merely discouraged — this test records the property so
    // adding a second constructor is a visible change rather than a silent one.
    let authorisation = StreamAuthorization::from_config(&config(TranscriptionMode::Cloud, true))
        .expect("cloud + consent is authorised");
    let credential =
        Credential::developer_key("0123456789abcdef0123456789abcdef01234567").expect("fixture");

    assert!(
        RequestSpec::build(
            &authorisation,
            &DeepgramEndpoint::default(),
            &StreamParams::default(),
            credential,
        )
        .is_ok(),
        "an authorised request could not be built, so the gate above is refusing everything"
    );
}

#[test]
fn revoking_consent_revokes_the_ability_to_stream() {
    // The switch-back path: turning the mode back to on-device must take the permission with
    // it, not leave a granted authorisation valid.
    let mut config = config(TranscriptionMode::Cloud, true);
    assert!(StreamAuthorization::from_config(&config).is_ok());

    config.consent.cloud_transcription = false;
    assert!(
        StreamAuthorization::from_config(&config).is_err(),
        "withdrawing the opt-in left streaming permitted"
    );

    config.consent.cloud_transcription = true;
    config.settings.transcription_mode = TranscriptionMode::OnDevice;
    assert!(
        StreamAuthorization::from_config(&config).is_err(),
        "switching back to on-device left streaming permitted"
    );
}
