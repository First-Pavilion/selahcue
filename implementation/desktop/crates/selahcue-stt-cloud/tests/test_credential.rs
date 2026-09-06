//! The credential: validation, the two `Authorization` spellings, the single environment
//! read, and the property that matters most — **the secret does not escape**.

#![allow(clippy::unwrap_used)]

use std::sync::{Mutex, MutexGuard};

use selahcue_stt_cloud::credential::{developer_key_permitted, MIN_SECRET_LEN};
use selahcue_stt_cloud::error::MalformedCredential;
use selahcue_stt_cloud::{
    developer_credential_from_env, Credential, CredentialScheme, DeepgramError,
    DEEPGRAM_API_KEY_VAR,
};

/// A plausible Deepgram key shape. Distinctive enough that a substring search for it in
/// formatted output cannot match by accident.
const TEST_SECRET: &str = "dgkeyAAAABBBBCCCCDDDDEEEEFFFF0000111122223333";

/// The environment is process-global, so the two tests that manipulate it serialise here
/// rather than racing each other inside this test binary.
static ENV_LOCK: Mutex<()> = Mutex::new(());

fn env_guard() -> MutexGuard<'static, ()> {
    ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner())
}

#[test]
fn a_developer_key_uses_the_token_spelling_and_a_grant_token_uses_bearer() {
    // Deepgram accepts both, and which one is correct depends on what the credential is.
    // Phase 2 swaps a raw key for a minted JWT; this is the whole of the difference on the
    // wire, and getting it backwards is a 401 that looks like a bad key.
    let key = Credential::developer_key(TEST_SECRET).expect("a valid key");
    assert_eq!(key.scheme(), CredentialScheme::Token);
    assert_eq!(
        key.authorization_header_value(),
        format!("Token {TEST_SECRET}")
    );

    let token = Credential::grant_token(TEST_SECRET).expect("a valid token");
    assert_eq!(token.scheme(), CredentialScheme::Bearer);
    assert_eq!(
        token.authorization_header_value(),
        format!("Bearer {TEST_SECRET}")
    );
}

#[test]
fn an_absent_credential_names_the_variable_the_operator_has_to_set() {
    // "Cloud transcription unavailable" is not an actionable message. The variable name is.
    for blank in ["", "   ", "\t\n"] {
        match Credential::developer_key(blank) {
            Err(e @ DeepgramError::MissingCredential { variable }) => {
                assert_eq!(variable, DEEPGRAM_API_KEY_VAR);
                assert!(
                    e.to_string().contains("DEEPGRAM_API_KEY"),
                    "the message does not name the variable: {e}"
                );
                assert!(
                    e.to_string().contains(".env"),
                    "the message does not say where to set it: {e}"
                );
            }
            other => panic!("a blank credential {blank:?} was accepted: {other:?}"),
        }
    }
}

#[test]
fn a_credential_carrying_a_header_terminator_is_refused() {
    // A CR or LF in a header value is header injection on the upgrade request. Refusing is
    // the only safe answer; escaping it would still be sending an attacker-shaped header.
    for injected in [
        "dgkey\r\nX-Injected: yes0000111122223333",
        "dgkey\nX-Injected: yes00001111222233334",
        "dgkey\u{0}0000111122223333444455556666",
        "dgkéy0000111122223333444455556666777",
    ] {
        match Credential::developer_key(injected) {
            Err(DeepgramError::MalformedCredential(
                MalformedCredential::IllegalHeaderCharacter,
            )) => {}
            other => panic!("a credential containing {injected:?} was accepted: {other:?}"),
        }
    }
}

#[test]
fn a_credential_with_the_scheme_prefix_pasted_in_is_refused_with_a_message_that_says_so() {
    let error = Credential::developer_key(format!("Token {TEST_SECRET}"))
        .expect_err("a pasted scheme prefix should be refused");
    assert_eq!(
        error,
        DeepgramError::MalformedCredential(MalformedCredential::ContainsWhitespace)
    );
    assert!(
        error.to_string().contains("Token"),
        "the message does not tell the operator to drop the prefix: {error}"
    );
}

#[test]
fn a_truncated_paste_is_refused_and_a_full_length_key_is_still_accepted() {
    // `Credential` deliberately derives no `PartialEq` — comparing secrets is one of the ways
    // they end up in a test failure message — so the error is matched rather than compared.
    let short = "a".repeat(MIN_SECRET_LEN - 1);
    assert_eq!(
        Credential::developer_key(&short).err(),
        Some(DeepgramError::MalformedCredential(
            MalformedCredential::TooShort
        ))
    );
    // The positive control, in the same test: without it, "too short is refused" is
    // indistinguishable from "everything is refused".
    assert!(
        Credential::developer_key("a".repeat(MIN_SECRET_LEN)).is_ok(),
        "a key of exactly the minimum length was refused; the length guard is off by one or \
         refusing everything"
    );
}

#[test]
fn the_secret_never_appears_in_any_formatted_output() {
    // The three routes a secret usually escapes: a derived Debug, a Display, and an error
    // built from a transport failure that quoted the request.
    let credential = Credential::developer_key(TEST_SECRET).expect("a valid key");

    let renderings = [
        format!("{credential:?}"),
        format!("{credential:#?}"),
        format!("{:?}", Some(credential.clone())),
        format!("{:?}", vec![credential.clone()]),
    ];
    for rendering in &renderings {
        assert!(
            !rendering.contains(TEST_SECRET),
            "the credential leaked through a formatter: {rendering}"
        );
        assert!(
            rendering.contains("<redacted>"),
            "the credential formatted without the redaction marker, so a reader cannot tell \
             a redacted field from an absent one: {rendering}"
        );
    }

    // The positive control: the redaction is not achieved by formatting nothing at all.
    assert!(
        renderings[0].contains("Token"),
        "the Debug output carries no scheme either, so it is empty rather than redacted"
    );
}

#[test]
fn every_error_variant_renders_without_the_secret() {
    let credential = Credential::developer_key(TEST_SECRET).expect("a valid key");
    let quoted = format!("connection refused while sending Authorization: Token {TEST_SECRET}");

    let errors = vec![
        DeepgramError::MissingCredential {
            variable: DEEPGRAM_API_KEY_VAR,
        },
        DeepgramError::MalformedCredential(MalformedCredential::TooShort),
        DeepgramError::ConsentRequired,
        DeepgramError::InsecureEndpoint {
            url: "ws://example.com".to_string(),
        },
        DeepgramError::CredentialRejected { status: 401 },
        DeepgramError::transport(&quoted, Some(&credential)),
        DeepgramError::protocol(&quoted, Some(&credential)),
        DeepgramError::GaveUp { attempts: 5 },
    ];

    for error in &errors {
        assert!(
            !format!("{error}").contains(TEST_SECRET),
            "the secret reached an error message: {error}"
        );
        assert!(
            !format!("{error:?}").contains(TEST_SECRET),
            "the secret reached an error's Debug output: {error:?}"
        );
    }

    // The positive control: the scrubbed errors still carry the rest of their message, so
    // "no secret" is not achieved by discarding the whole detail.
    let scrubbed = format!("{}", errors[5]);
    assert!(
        scrubbed.contains("connection refused"),
        "scrubbing removed the diagnostic as well as the secret: {scrubbed}"
    );
    assert!(
        scrubbed.contains("<redacted>"),
        "the scrubbed message does not mark where the secret was: {scrubbed}"
    );
}

#[test]
fn reading_the_environment_when_nothing_is_set_names_the_variable() {
    let _guard = env_guard();
    let restore = std::env::var(DEEPGRAM_API_KEY_VAR).ok();
    std::env::remove_var(DEEPGRAM_API_KEY_VAR);

    let result = developer_credential_from_env();

    if let Some(previous) = restore {
        std::env::set_var(DEEPGRAM_API_KEY_VAR, previous);
    }

    match result {
        Err(DeepgramError::MissingCredential { variable }) => {
            assert_eq!(variable, DEEPGRAM_API_KEY_VAR)
        }
        other => panic!("an unset environment produced {other:?} rather than a named failure"),
    }
}

// 86akd10dq (Sana's High finding, Cody's Finding A, Quinn's High: the `cloud-stt` reachability
// PR): `developer_credential_from_env` read `DEEPGRAM_API_KEY_VAR` with no profile check at all,
// so making `cloud-stt` reachable from `make launch`'s default `STT ?= auto` meant `make launch
// RELEASE=1`/`make run-release` built a working direct-to-Deepgram release binary from whatever
// happened to be exported in the shell. `developer_key_permitted` closes that, the same shape as
// `selahcue_cloud::openai`'s `direct_key_permitted` pair plus its own wiring test — these four
// tests prove it (three here, one wiring test folded into the existing environment-read test
// below rather than duplicated, since it already sets up exactly the state the wiring test
// needs).

/// The pure predicate's release branch, tested directly since `cfg!(debug_assertions)` cannot be
/// varied within one compiled test binary.
#[test]
fn a_release_profile_input_refuses_the_developer_key() {
    assert!(
        !developer_key_permitted(false),
        "a release-profile (debug_assertions=false) input must refuse the developer key — this \
         is the guard standing between `--features cloud-stt --release` (or `make launch \
         RELEASE=1`/`make run-release`, which now reach `cloud-stt` by default) and a shipped \
         binary that reads DEEPGRAM_API_KEY from whatever happens to be exported"
    );
}

/// The positive control: an ordinary debug/test profile must still permit it, so "refuses" above
/// is the release branch actually firing rather than the predicate refusing unconditionally.
#[test]
fn a_debug_profile_input_still_permits_the_developer_key() {
    assert!(
        developer_key_permitted(true),
        "a debug-profile (debug_assertions=true) input was refused — cloud-stt would stop \
         working in ordinary `cargo run`/`cargo test`, not just in --release"
    );
}

/// The wiring test: proves `developer_credential_from_env` ITSELF takes the branch this profile
/// compiled, not just that the extracted predicate above is correct in isolation. Mirrors
/// `selahcue_cloud::openai::OpenAiNoteProvider::from_env`'s wiring test and
/// `selahcue-operator`'s `dev_env::load()` wiring test: one test, run once per profile by
/// `make ci`/CI (`cargo test -p selahcue-stt-cloud --features deepgram` and the `--release`
/// sibling added alongside this fix), asserting whichever branch that profile actually compiled.
/// Also doubles as the positive control for the environment read itself in a debug build —
/// without it, "missing is reported" would be indistinguishable from a function that always
/// fails.
#[test]
fn reading_the_environment_when_a_key_is_set_produces_a_credential_iff_this_is_a_debug_build() {
    let _guard = env_guard();
    let restore = std::env::var(DEEPGRAM_API_KEY_VAR).ok();
    std::env::set_var(DEEPGRAM_API_KEY_VAR, TEST_SECRET);

    let result = developer_credential_from_env();

    match restore {
        Some(previous) => std::env::set_var(DEEPGRAM_API_KEY_VAR, previous),
        None => std::env::remove_var(DEEPGRAM_API_KEY_VAR),
    }

    if cfg!(debug_assertions) {
        let credential = result.expect(
            "a debug build must produce a credential from an exported \
                            DEEPGRAM_API_KEY, or cloud-stt stops working in ordinary development",
        );
        assert_eq!(credential.scheme(), CredentialScheme::Token);
        assert_eq!(
            credential.authorization_header_value(),
            format!("Token {TEST_SECRET}")
        );
    } else {
        match result {
            Err(DeepgramError::MissingCredential { variable }) => {
                assert_eq!(variable, DEEPGRAM_API_KEY_VAR)
            }
            other => panic!(
                "a RELEASE build produced {other:?} from an exported DEEPGRAM_API_KEY — \
                 developer_key_permitted stopped being wired into developer_credential_from_env \
                 (inverted, hardcoded, or the early return was removed)"
            ),
        }
    }
}
