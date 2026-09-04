//! The request: wire parameters, endpoint confidentiality, and what the request specification
//! does and does not carry.
//!
//! The default query string is pinned **byte for byte**. That is the acceptance criterion
//! "the working connection parameters are recorded precisely enough to rebuild from", made
//! structural: prose in a ticket drifts, a pinned fixture does not.

#![allow(clippy::unwrap_used)]

use selahcue_stt_cloud::session::DEEPGRAM_LISTEN_URL;
use selahcue_stt_cloud::{
    Credential, DeepgramEndpoint, DeepgramError, Encoding, RequestSpec, StreamAuthorization,
    StreamParams,
};

const TEST_SECRET: &str = "0123456789abcdef0123456789abcdef01234567";

/// The consent gate has its own suite (`test_consent.rs`); this one needs a granted
/// authorisation to get past it.
fn authorised() -> StreamAuthorization {
    use selahcue_core::providers::{ProvidersConfig, TranscriptionMode};
    let mut config = ProvidersConfig::default();
    config.settings.transcription_mode = TranscriptionMode::Cloud;
    config.consent.cloud_transcription = true;
    StreamAuthorization::from_config(&config).expect("this fixture is meant to be authorised")
}

#[test]
fn the_default_query_string_is_pinned_byte_for_byte() {
    assert_eq!(
        StreamParams::default().to_query(),
        "model=nova-3\
         &language=en-US\
         &encoding=linear16\
         &sample_rate=16000\
         &channels=1\
         &interim_results=true\
         &punctuate=true\
         &smart_format=false\
         &endpointing=300\
         &utterance_end_ms=1000\
         &vad_events=false",
        "the Deepgram wire parameters changed. This string is the record of what was measured \
         against the live service; update the ticket's recorded parameters in the same change."
    );
}

#[test]
fn interim_results_is_on_because_the_console_cannot_recover_the_distinction_later() {
    // With interim_results off Deepgram sends finals only, and the provisional-versus-settled
    // styling FR-103 requires becomes unbuildable downstream.
    assert!(StreamParams::default().interim_results);
}

#[test]
fn smart_format_is_off_so_the_scripture_detector_still_receives_spoken_numbers() {
    // A live check against the service turned "John chapter three verse sixteen" into "John
    // chapter three verse 16". The R4 scripture detector (FR-112) was specified against spoken
    // numbers and carries its own spoken-number normalisation, so this is a product decision
    // and not a transport default to change casually. Flagged for the R4 pipeline.
    assert!(
        !StreamParams::default().smart_format,
        "smart_format was turned on by default; Deepgram would rewrite spoken numbers as \
         digits and change what the FR-112 scripture detector receives"
    );
    assert!(
        StreamParams::default().punctuate,
        "punctuation was turned off as well; the panel would show an unreadable wall of text"
    );
}

#[test]
fn utterance_end_ms_is_omitted_when_interim_results_is_off() {
    // Deepgram only honours it alongside interim results, so sending it otherwise is a
    // parameter that quietly does nothing.
    let params = StreamParams {
        interim_results: false,
        utterance_end_ms: Some(1_000),
        ..StreamParams::default()
    };
    let query = params.to_query();
    assert!(
        !query.contains("utterance_end_ms"),
        "utterance_end_ms was sent without interim_results: {query}"
    );
    // The positive control: it IS sent in the configuration that honours it.
    assert!(
        StreamParams::default()
            .to_query()
            .contains("utterance_end_ms=1000"),
        "utterance_end_ms is never sent at all, so the omission above proves nothing"
    );
}

#[test]
fn the_encoding_declared_matches_what_the_audio_ring_carries() {
    assert_eq!(Encoding::Linear16.as_str(), "linear16");
    assert_eq!(StreamParams::default().encoding, Encoding::Linear16);
    assert_eq!(
        StreamParams::default().sample_rate_hz,
        16_000,
        "the sample rate no longer matches selahcue-stt's TARGET_SAMPLE_RATE, so one capture \
         pipeline can no longer feed both engines"
    );
    assert_eq!(StreamParams::default().channels, 1);
}

#[test]
fn the_default_endpoint_is_deepgrams_tls_streaming_url() {
    assert_eq!(DeepgramEndpoint::default().url(), DEEPGRAM_LISTEN_URL);
    assert_eq!(DEEPGRAM_LISTEN_URL, "wss://api.deepgram.com/v1/listen");
}

#[test]
fn a_cleartext_endpoint_is_refused_unless_the_peer_is_this_machine() {
    // A credential must never cross a network in clear text. Loopback is allowed because that
    // is what the stub-socket tests connect to and the bytes never leave the machine.
    for confidential in [
        "wss://api.deepgram.com/v1/listen",
        "ws://127.0.0.1:9999/v1/listen",
        "ws://localhost:9999/v1/listen",
        "ws://[::1]:9999/v1/listen",
        "ws://127.0.0.1/v1/listen",
    ] {
        assert!(
            DeepgramEndpoint::custom(confidential).is_confidential(),
            "{confidential} was refused, but it keeps the credential confidential — the stub \
             socket suite and the real endpoint both depend on this being allowed"
        );
    }

    for exposed in [
        "ws://api.deepgram.com/v1/listen",
        "ws://192.168.1.10:9999/v1/listen",
        "ws://evil.example.com/v1/listen",
        "http://api.deepgram.com/v1/listen",
        "ws://127.0.0.1.evil.example.com/v1/listen",
        // Userinfo: the real host is `evil.com`. A scan that splits on `:` before
        // noticing the `@` sees `127.0.0.1` and calls it loopback.
        "ws://127.0.0.1:80@evil.com/v1/listen",
        "ws://127.0.0.1@evil.com/v1/listen",
        "ws://localhost:9999@evil.com/v1/listen",
    ] {
        assert!(
            !DeepgramEndpoint::custom(exposed).is_confidential(),
            "{exposed} would carry the credential in clear text off this machine and was \
             allowed"
        );
    }
}

#[test]
fn building_a_request_to_a_cleartext_endpoint_fails_before_connecting() {
    let credential = Credential::developer_key(TEST_SECRET).expect("fixture key");
    let endpoint = DeepgramEndpoint::custom("ws://api.deepgram.com/v1/listen");

    match RequestSpec::build(
        &authorised(),
        &endpoint,
        &StreamParams::default(),
        credential.clone(),
    ) {
        Err(DeepgramError::InsecureEndpoint { url }) => {
            assert_eq!(url, "ws://api.deepgram.com/v1/listen")
        }
        other => panic!("a cleartext endpoint was accepted: {other:?}"),
    }

    // The positive control: the same call over TLS succeeds, so the refusal above is about
    // the endpoint and not about a build path that never works.
    assert!(
        RequestSpec::build(
            &authorised(),
            &DeepgramEndpoint::default(),
            &StreamParams::default(),
            credential,
        )
        .is_ok(),
        "a TLS endpoint was refused too; the confidentiality guard is refusing everything"
    );
}

#[test]
fn the_url_carries_the_parameters_and_never_the_credential() {
    // A key in a query string ends up in proxy logs. Deepgram authenticates by header, and
    // this asserts we use it.
    let credential = Credential::developer_key(TEST_SECRET).expect("fixture key");
    let spec = RequestSpec::build(
        &authorised(),
        &DeepgramEndpoint::default(),
        &StreamParams::default(),
        credential,
    )
    .expect("a TLS endpoint with consent should build");

    assert!(spec.url().starts_with(DEEPGRAM_LISTEN_URL));
    assert!(spec.url().contains("model=nova-3"));
    assert!(
        !spec.url().contains(TEST_SECRET),
        "the credential is in the URL: {}",
        spec.url()
    );
    assert_eq!(
        spec.authorization_header_value(),
        format!("Token {TEST_SECRET}"),
        "the Authorization header is not the raw-API-key spelling Deepgram expects"
    );
}
