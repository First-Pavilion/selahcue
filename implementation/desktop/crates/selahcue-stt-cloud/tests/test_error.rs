//! Error classification: a rejected credential and a network failure must lead an operator to
//! completely different actions, and only one of them is worth retrying.

#![allow(clippy::unwrap_used)]

use selahcue_stt_cloud::error::MalformedCredential;
use selahcue_stt_cloud::{Credential, DeepgramError, OperatorAction, DEEPGRAM_API_KEY_VAR};

const TEST_SECRET: &str = "dgkeyAAAABBBBCCCCDDDDEEEEFFFF0000111122223333";

fn credential() -> Credential {
    Credential::developer_key(TEST_SECRET).expect("a valid fixture key")
}

#[test]
fn a_rejected_credential_and_a_network_failure_prescribe_different_actions() {
    // This is the acceptance criterion: "the operator's next action differs completely
    // between the two". Asserting the variants differ would not establish that — two
    // differently-named variants can still leave a console showing the same message.
    let rejected = DeepgramError::CredentialRejected { status: 401 };
    let network = DeepgramError::transport("dns error: no such host", Some(&credential()));

    assert_eq!(
        rejected.operator_action(),
        OperatorAction::ReplaceCredential
    );
    assert_eq!(network.operator_action(), OperatorAction::CheckNetwork);
    assert_ne!(
        rejected.operator_action(),
        network.operator_action(),
        "a rejected key and a dead network prescribe the same action, so the console cannot \
         tell an operator which of the two things to go and fix"
    );

    assert!(
        rejected.to_string().contains("401"),
        "the rejection message hides the status the operator would quote in a support \
         request: {rejected}"
    );
    assert!(
        network.to_string().contains("dns error"),
        "the transport message discarded the underlying cause: {network}"
    );
}

#[test]
fn only_a_transport_failure_is_retried() {
    // Retrying a key Deepgram has already refused cannot succeed. It hammers the service and
    // hides the one message the operator needs behind a reconnect spinner.
    assert!(
        DeepgramError::transport("connection reset", Some(&credential())).is_retryable(),
        "a network failure is not retried, so a momentary Wi-Fi drop would end transcription \
         for the service"
    );

    for terminal in [
        DeepgramError::CredentialRejected { status: 401 },
        DeepgramError::CredentialRejected { status: 403 },
        DeepgramError::MissingCredential {
            variable: DEEPGRAM_API_KEY_VAR,
        },
        DeepgramError::MalformedCredential(MalformedCredential::TooShort),
        DeepgramError::ConsentRequired,
        DeepgramError::InsecureEndpoint {
            url: "ws://example.com".to_string(),
        },
        DeepgramError::Protocol {
            detail: "bad frame".to_string(),
        },
        DeepgramError::GaveUp { attempts: 5 },
    ] {
        assert!(
            !terminal.is_retryable(),
            "{terminal:?} would be retried, but no number of reconnections can fix it"
        );
    }
}

#[test]
fn every_variant_maps_to_exactly_one_action_and_the_actions_are_not_all_the_same() {
    // A classification where everything maps to one action is a classification that does not
    // classify. This asserts the mapping is actually discriminating.
    let mapped = [
        DeepgramError::MissingCredential {
            variable: DEEPGRAM_API_KEY_VAR,
        }
        .operator_action(),
        DeepgramError::CredentialRejected { status: 401 }.operator_action(),
        DeepgramError::ConsentRequired.operator_action(),
        DeepgramError::Transport {
            detail: "x".to_string(),
        }
        .operator_action(),
        DeepgramError::Protocol {
            detail: "x".to_string(),
        }
        .operator_action(),
    ];
    assert_eq!(
        mapped,
        [
            OperatorAction::SupplyCredential,
            OperatorAction::ReplaceCredential,
            OperatorAction::GrantConsent,
            OperatorAction::CheckNetwork,
            OperatorAction::ReportDefect,
        ],
        "the error-to-action mapping changed; the console's guidance changes with it"
    );

    let mut distinct = mapped.to_vec();
    distinct.sort_by_key(|a| format!("{a:?}"));
    distinct.dedup();
    assert_eq!(
        distinct.len(),
        5,
        "several errors collapsed onto one action, so the classification is not classifying"
    );
}

#[test]
fn giving_up_says_it_has_stopped_rather_than_implying_it_is_still_trying() {
    let gave_up = DeepgramError::GaveUp { attempts: 5 };
    let message = gave_up.to_string();
    assert!(
        message.contains("gave up"),
        "the give-up message does not say it gave up: {message}"
    );
    assert!(
        message.contains("stopped"),
        "the give-up message does not say transcription has stopped, so an operator would \
         keep waiting for it to come back: {message}"
    );
    assert!(message.contains('5'), "the attempt count is missing");
}

#[test]
fn transport_details_are_scrubbed_of_the_secret_without_losing_the_diagnostic() {
    // Transport stacks quote request context into their error strings, which makes an error
    // built from one a real escape route.
    let leaky = format!("handshake failed sending `Authorization: Token {TEST_SECRET}` to host");
    let scrubbed = DeepgramError::transport(&leaky, Some(&credential()));

    match &scrubbed {
        DeepgramError::Transport { detail } => {
            assert!(
                !detail.contains(TEST_SECRET),
                "the secret survived scrubbing: {detail}"
            );
            assert!(
                detail.contains("handshake failed"),
                "scrubbing discarded the diagnostic as well as the secret: {detail}"
            );
            assert!(
                detail.contains("<redacted>"),
                "the scrubbed detail does not mark where the secret was: {detail}"
            );
        }
        other => panic!("expected a transport error, got {other:?}"),
    }

    // Without a credential in scope there is nothing to scrub, and the detail passes through
    // intact — the positive control that scrubbing is targeted rather than blanket.
    let unscrubbed = DeepgramError::transport("plain failure", None);
    assert_eq!(
        unscrubbed,
        DeepgramError::Transport {
            detail: "plain failure".to_string()
        }
    );
}

#[test]
fn the_error_type_is_a_std_error() {
    // So a caller can put it in a `Box<dyn Error>` or a `?` chain without a wrapper.
    fn takes_error(_: &dyn std::error::Error) {}
    takes_error(&DeepgramError::ConsentRequired);
}
