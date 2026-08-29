//! The invariants that outrank the feature: CON-P1 (never-blank) and CON-P2
//! (offline-first), plus NFR-501/502/504.
//!
//! A church runs disconnected for a week and must keep presenting. Nothing in this crate
//! may make that untrue, and "we were careful" is not a verification strategy. Three
//! different kinds of proof live here:
//!
//! - **Structural** — the render and live-control crates cannot even *reach* this code,
//!   asserted by reading their manifests. This is what "no licensing call sits on the
//!   render, go-live or live-control path — asserted, not assumed" means.
//! - **Exhaustive** — every failure state and every status answers "yes" to "may the app
//!   present?". The compiler forces the list to stay complete; these tests check the
//!   answers.
//! - **Behavioural** — an unreachable platform produces an ordinary, silent, retryable
//!   *unknown*, and a failed activation destroys nothing that was already working.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::{
    ActivationFailure, DeviceCredentials, DeviceIdentity, ErrorCode, IdempotencyKey,
    InMemorySecretStore, LicensingClient, LicensingStatus, ScriptedTransport, Token,
};
use std::path::PathBuf;

/// Number of `.rs` modules in `src/`. Pinned so a scan cannot silently cover less.
const EXPECTED_SRC_MODULES: usize = 9;

// ---------------------------------------------------------------------------
// Structural: licensing is not on the render / go-live / live-control path
// ---------------------------------------------------------------------------

/// The crates that make up the render, composition and live-control paths.
///
// --- where the closure guard actually lives ------------------------------------------
//
// A transitive-closure guard used to live HERE, hand-parsing each manifest. It has been
// removed rather than patched, because its claim was wider than its detection and that is
// worse than having no guard: two ordinary declaration forms walked straight past it while
// it reported success —
//
//     [dependencies.selahcue-licensing]                              # name is in the HEADER
//     licensing = { package = "selahcue-licensing", path = "..." }   # key renamed
//
// — both confirmed to link licensing into the `selahcue-output` process while the suite
// stayed green. Both matched on the TOML key rather than the resolved package, and adding
// two more spellings would have left the class open.
//
// The guard now asks cargo, in `scripts/import_guards.sh` (`make ci` runs it): `cargo tree
// -p selahcue-desktop -e normal` and the same for `selahcue-app`, with a positive control
// that the walk reached `selahcue-present`. That resolves real packages, so no spelling
// evades it. It lives in the script rather than in a test for the same reason the
// importer's B2 allowlist does — it shells out to cargo, which is not something to do from
// inside a `cargo test` run.
//
// What remains in this file is the behavioural half of never-blank, which needs no
// dependency graph: every failure and status permits presentation, an unreachable platform
// is a silent retryable unknown, and a failed activation destroys nothing.

#[test]
fn this_crate_exposes_no_enforcement_entry_point() {
    // Enforcement is 86ak5mn1t and is ladder-shaped by design (FR-520): licensing state
    // takes effect only at session boundaries and only on non-core surfaces. If a
    // `should_block`-shaped function ever appears *here*, that laddering has been bypassed
    // and some caller is one `if` away from gating live output.
    let src = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");
    // The trailing `(` matters: without it these match any function whose name merely
    // STARTS with one of them, and `is_allowed_key_char` — a character-class predicate with
    // nothing to do with gating — trips a guard about enforcement. A guard that cries wolf
    // gets loosened, and a loosened guard stops catching the thing it was written for.
    let forbidden = [
        "fn is_allowed(",
        "fn should_block(",
        "fn enforce(",
        "fn require_activation(",
        "fn gate(",
        "fn is_blocked(",
    ];

    let mut scanned = 0usize;
    for entry in std::fs::read_dir(&src).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_none_or(|e| e != "rs") {
            continue;
        }
        let body = std::fs::read_to_string(&path).unwrap();
        scanned += 1;
        for (lineno, line) in body.lines().enumerate() {
            let code = line.trim_start();
            if code.starts_with("//") {
                continue;
            }
            for pattern in forbidden {
                assert!(
                    !code.contains(pattern),
                    "{}:{} defines {pattern:?}. This crate obtains credentials and reports \
                     state; it does not gate. Enforcement belongs to 86ak5mn1t.\n  {code}",
                    path.display(),
                    lineno + 1
                );
            }
        }
    }
    // Exact, not `>=`. With a floor of 6 against 8 modules, two could be deleted and the
    // control would still pass while the scan silently covered less.
    assert_eq!(
        scanned, EXPECTED_SRC_MODULES,
        "expected to scan exactly {EXPECTED_SRC_MODULES} modules, scanned {scanned} — a \
         module was added or removed, so update this pin deliberately"
    );
}

// ---------------------------------------------------------------------------
// Exhaustive: every state permits presentation
// ---------------------------------------------------------------------------

/// Every [`ActivationFailure`] variant.
///
/// The exhaustive `match` below exists purely to break the build when a variant is added:
/// the compiler rejects it as non-exhaustive, so this list cannot quietly fall behind and
/// leave a new failure state unverified. That, plus the exhaustive match inside
/// `permits_presentation` itself, is what stops these tests going vacuous.
fn every_failure_variant() -> Vec<ActivationFailure> {
    let sample = ActivationFailure::UnknownKey;
    match sample {
        ActivationFailure::Unreachable(_) => {}
        ActivationFailure::NoActiveLicense => {}
        ActivationFailure::UnknownKey => {}
        ActivationFailure::PolicyDenied => {}
        ActivationFailure::Unauthenticated => {}
        ActivationFailure::PermissionDenied => {}
        ActivationFailure::ValidationFailed => {}
        ActivationFailure::RateLimited => {}
        ActivationFailure::Server(_) => {}
        ActivationFailure::Coded(_) => {}
        ActivationFailure::UnexpectedStatus(_) => {}
        ActivationFailure::Malformed(_) => {}
    }

    vec![
        ActivationFailure::Unreachable("dns failure".into()),
        ActivationFailure::NoActiveLicense,
        ActivationFailure::UnknownKey,
        ActivationFailure::PolicyDenied,
        ActivationFailure::Unauthenticated,
        ActivationFailure::PermissionDenied,
        ActivationFailure::ValidationFailed,
        ActivationFailure::RateLimited,
        ActivationFailure::Server(503),
        ActivationFailure::Coded(ErrorCode::Conflict),
        ActivationFailure::UnexpectedStatus(403),
        ActivationFailure::Malformed("bad json".into()),
    ]
}

#[test]
fn every_activation_failure_permits_presentation() {
    let variants = every_failure_variant();
    assert_eq!(
        variants.len(),
        12,
        "the variant list drifted from the exhaustive match above"
    );

    for failure in variants {
        assert!(
            failure.permits_presentation(),
            "{failure:?} does not permit presentation. No licensing state, transition, API \
             response or outage may block live output (CON-P1 / NFR-501)."
        );
    }
}

#[test]
fn every_licensing_status_permits_presentation() {
    let statuses = {
        let sample = LicensingStatus::Unknown;
        match sample {
            LicensingStatus::Unknown => {}
            LicensingStatus::Activated { .. } => {}
        }
        vec![
            LicensingStatus::Unknown,
            LicensingStatus::Activated {
                device_public_id: "dev_0123456789abcdef0123456789abcdef".into(),
            },
        ]
    };

    assert_eq!(statuses.len(), 2, "the status list drifted");
    for status in statuses {
        assert!(
            status.permits_presentation(),
            "{status:?} does not permit presentation (CON-P1 / NFR-501)"
        );
    }
}

#[test]
fn a_fresh_install_defaults_to_unknown_not_to_a_fault() {
    // "Absent or unreachable licensing renders as unknown, never as a fault and never as
    // a block." The default matters: it is what a fresh install, a skipped setup and an
    // air-gapped booth all evaluate to.
    let status = LicensingStatus::default();
    assert_eq!(status, LicensingStatus::Unknown);
    assert!(!status.is_activated());
    assert!(status.permits_presentation());
}

// ---------------------------------------------------------------------------
// Behavioural: an unreachable platform is silent, retryable and harmless
// ---------------------------------------------------------------------------

fn identity() -> DeviceIdentity {
    DeviceIdentity::new("fp-booth-mac-01", "macos", "1.0.0", "Booth").unwrap()
}

fn idem() -> IdempotencyKey {
    IdempotencyKey::new("idem-0123456789ab").unwrap()
}

#[test]
fn an_unreachable_platform_is_a_silent_retryable_unknown() {
    // NFR-504 and FR-523: "Airplane-mode refresh = silent retry, no operator-facing
    // warning". The church is offline on a Sunday; nothing about that is an error state.
    let client = LicensingClient::new(
        ScriptedTransport::failing("dns error: no such host"),
        "https://api.selahcue.example",
    );

    let failure = client
        .activate_with_enrollment_key(&Token::new("SC-TRIAL-KEY"), &identity(), &idem())
        .unwrap_err();

    match &failure {
        ActivationFailure::Unreachable(_) => {}
        other => panic!("an offline platform must classify as Unreachable, got {other:?}"),
    }
    assert!(
        failure.is_retryable(),
        "an unreachable platform must be retried silently, not surfaced as a refusal"
    );
    assert!(failure.permits_presentation());

    // And the state the app reports is the ordinary unknown — not a fault variant, because
    // there isn't one.
    assert_eq!(LicensingStatus::default(), LicensingStatus::Unknown);
}

#[test]
fn a_failed_activation_destroys_nothing_that_was_already_working() {
    // The install is already activated and presenting. A later activation attempt fails —
    // offline, refused, rate-limited, anything. It must not clear the device token, because
    // losing it is how a working booth stops being able to reach cloud features at all.
    let creds = DeviceCredentials::new(InMemorySecretStore::new());
    let existing = "SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8";
    creds.store_device_token(&Token::new(existing)).unwrap();

    for transport in [
        ScriptedTransport::failing("network unreachable"),
        ScriptedTransport::responding(
            403,
            r#"{"error":{"code":"POLICY_DENIED","message":"x"},"surface":"desktop","operation":"activation"}"#,
        ),
        ScriptedTransport::responding(500, "<html>boom</html>"),
    ] {
        let client = LicensingClient::new(transport, "https://api.selahcue.example");
        let result =
            client.activate_with_enrollment_key(&Token::new("SC-TRIAL-KEY"), &identity(), &idem());

        assert!(result.is_err(), "this fixture is meant to fail");
        assert!(
            creds.is_activated().unwrap(),
            "a failed activation must not clear an existing device token"
        );
        assert_eq!(
            creds.device_token().unwrap().unwrap().expose(),
            existing,
            "the existing token must survive a failed activation byte-for-byte"
        );
    }
}

#[test]
fn nothing_leaves_the_device_when_the_identity_is_rejected_locally() {
    // Local validation runs before any request. An install with an empty fingerprint
    // cannot even attempt activation, so it burns neither a round trip nor one of the ten
    // activation attempts per minute the endpoint allows.
    assert!(DeviceIdentity::new("", "macos", "1.0.0", "Booth").is_err());
    assert!(IdempotencyKey::new("short").is_err());

    // Proof that a client given no work issues no request.
    let client = LicensingClient::new(
        ScriptedTransport::failing("should never be called"),
        "https://api.selahcue.example",
    );
    assert_eq!(
        client.transport().request_count(),
        0,
        "constructing a client must not touch the network"
    );
}
