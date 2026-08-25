//! Credential custody (FR-517, NFR-017) and the DEC-007 sign-out invariant.
//!
//! Three kinds of check live here, and the last two are the ones that bite:
//!
//! 1. The store round-trips, and sign-out keeps the device token.
//! 2. **A redaction sweep**: every type this crate can put in a log line is formatted and
//!    searched for real token material. The desktop equivalent of the server's audit
//!    redaction discipline.
//! 3. **Structural sweeps**: the crate's own source cannot name a file, and the app
//!    database schema has no column that could hold a token. These are what make "never in
//!    a plaintext file, never in the database" a property rather than a promise — a test
//!    that inspects a running install would only prove the token was not there *today*.

#![allow(clippy::unwrap_used)]

use selahcue_licensing::client::{Activation, ActivationPath};
use selahcue_licensing::contract::{
    ActivateDevicePayload, ActivateWithSessionData, ActivationRequest, ActivationResponse,
    DeviceDto, GraphQlResponse, LicenseDto, LoginData, LoginInput, LoginPayload, TokenMetaDto,
};
use selahcue_licensing::{
    AccountSession, DeviceCredentials, InMemorySecretStore, SecretStore, Token,
    ACCOUNT_SESSION_NAME, DEVICE_TOKEN_NAME,
};
use std::path::PathBuf;

/// A realistic device token: the server's format is `SC-DEV-` + 8 groups of 4.
const DEVICE_TOKEN: &str = "SC-DEV-A1B2-C3D4-E5F6-G7H8-J9K2-L3M4-N5P6-Q7R8";
const SESSION_TOKEN: &str = "sess-11112222333344445555666677778888";
const ENROLLMENT_KEY: &str = "SC-TRIAL-Z9Y8-X7W6-V5U4-T3S2-R1Q0-P9N8-M7L6-K5J4";
const PASSWORD: &str = "correct-horse-battery-staple";

fn credentials() -> DeviceCredentials<InMemorySecretStore> {
    DeviceCredentials::new(InMemorySecretStore::new())
}

#[test]
fn a_fresh_install_holds_no_credentials_and_that_is_not_an_error() {
    let creds = credentials();
    assert!(
        creds.device_token().unwrap().is_none(),
        "a fresh install has no device token"
    );
    assert!(!creds.is_activated().unwrap());
    assert!(creds.account_session().unwrap().is_none());
}

#[test]
fn the_device_token_round_trips_through_the_secret_store() {
    let creds = credentials();
    creds.store_device_token(&Token::new(DEVICE_TOKEN)).unwrap();

    assert!(creds.is_activated().unwrap());
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        DEVICE_TOKEN
    );
}

#[test]
fn sign_out_leaves_the_device_token_intact() {
    // THE DEC-007 INVARIANT (restated by FR-542). This reads like a bug to anyone who has
    // not seen the decision — signing out normally clears credentials — which is exactly
    // why it is pinned here by name. A volunteer signing out of the sound-booth machine
    // after setup must not take that machine's entitlement with them.
    let creds = credentials();
    creds.store_device_token(&Token::new(DEVICE_TOKEN)).unwrap();
    creds
        .store_account_session(&Token::new(SESSION_TOKEN))
        .unwrap();

    // Positive control first: both credentials really are present, so the assertions below
    // are about sign-out's behaviour and not about an empty store.
    assert!(
        creds.is_activated().unwrap() && creds.account_session().unwrap().is_some(),
        "both credentials must be present before sign-out, or this test proves nothing"
    );

    creds.sign_out().unwrap();

    assert!(
        creds.account_session().unwrap().is_none(),
        "sign-out must clear the account session"
    );
    assert!(
        creds.is_activated().unwrap(),
        "sign-out must NOT revoke the device token (DEC-007 / FR-542)"
    );
    assert_eq!(
        creds.device_token().unwrap().unwrap().expose(),
        DEVICE_TOKEN,
        "the device token must survive sign-out byte-for-byte"
    );
}

#[test]
fn deactivation_purges_both_credentials() {
    // The A9 destructive-confirm path — the only place in this crate that removes a device
    // token, and only because the operator explicitly gave up the slot.
    let creds = credentials();
    creds.store_device_token(&Token::new(DEVICE_TOKEN)).unwrap();
    creds
        .store_account_session(&Token::new(SESSION_TOKEN))
        .unwrap();

    creds.forget_all().unwrap();

    assert!(!creds.is_activated().unwrap());
    assert!(creds.account_session().unwrap().is_none());
}

#[test]
fn the_two_credentials_live_under_distinct_names() {
    // If both entries collided on one name, sign-out would silently destroy the device
    // token and `sign_out_leaves_the_device_token_intact` would be the only thing standing
    // between that and a Sunday morning.
    assert_ne!(DEVICE_TOKEN_NAME, ACCOUNT_SESSION_NAME);

    let store = InMemorySecretStore::new();
    let creds = DeviceCredentials::new(InMemorySecretStore::new());
    let _ = &creds;

    store
        .set(DEVICE_TOKEN_NAME, &Token::new(DEVICE_TOKEN))
        .unwrap();
    store
        .set(ACCOUNT_SESSION_NAME, &Token::new(SESSION_TOKEN))
        .unwrap();
    assert_eq!(
        store.get(DEVICE_TOKEN_NAME).unwrap().unwrap().expose(),
        DEVICE_TOKEN
    );
    assert_eq!(
        store.get(ACCOUNT_SESSION_NAME).unwrap().unwrap().expose(),
        SESSION_TOKEN
    );
}

// --- the redaction sweep --------------------------------------------------------------

#[test]
fn no_type_this_crate_exposes_leaks_credential_material_when_formatted() {
    // The server blocks `device_token`/`full_key`/`secret` from ever reaching an audit
    // payload. This is the desktop equivalent: the ordinary ways a secret escapes are a
    // `{:?}` in a log line, an error message, and a panic payload — all of which go through
    // these formatters.
    let mut formatted: Vec<(&str, String)> = Vec::new();

    let token = Token::new(DEVICE_TOKEN);
    formatted.push(("Token/Debug", format!("{token:?}")));
    formatted.push(("Token/Display", format!("{token}")));

    formatted.push((
        "AccountSession/Debug",
        format!(
            "{:?}",
            AccountSession {
                token: Token::new(SESSION_TOKEN),
                expires_at: "2026-09-24T10:11:12.123456+00:00".into(),
                role: "ADMIN".into(),
                org_id: "org_1".into(),
            }
        ),
    ));

    formatted.push((
        "Activation/Debug",
        format!(
            "{:?}",
            Activation {
                path: ActivationPath::EnrollmentKey,
                token: Some(Token::new(DEVICE_TOKEN)),
                created: true,
                reminted: Some(false),
                device_public_id: "dev_00000000000000000000000000000000".into(),
                platform: "macos".into(),
                token_meta: None,
                license: None,
            }
        ),
    ));

    // The wire types are the sharpest case: they must hold the raw secret to serialize it.
    formatted.push((
        "ActivationRequest/Debug",
        format!(
            "{:?}",
            ActivationRequest {
                idempotency_key: "idem-000000000001".into(),
                license_key: ENROLLMENT_KEY.into(),
                device_fingerprint: "fp-1".into(),
                platform: "macos".into(),
                app_version: "1.0.0".into(),
                display_name: "Booth".into(),
            }
        ),
    ));
    formatted.push((
        "LoginInput/Debug",
        format!(
            "{:?}",
            LoginInput {
                email: "admin@example.test".into(),
                password: PASSWORD.into(),
            }
        ),
    ));

    // --- the RESPONSE side ------------------------------------------------------------
    // The request types were the obvious half. These carry the same class of secret in the
    // other direction and were missed the first time round: the sweep named five types
    // while the crate exposed more, so removing a redaction here could never have gone
    // red. They are typed `Token` now, so the derived `Debug` redacts structurally — and
    // these entries are what pin that, rather than merely describing it.
    let activation_response = ActivationResponse {
        created: true,
        reminted: false,
        activation_token: Some(Token::new(DEVICE_TOKEN)),
        device: DeviceDto {
            device_public_id: "dev_1".into(),
            status: "ACTIVE".into(),
            platform: "macos".into(),
        },
        token: TokenMetaDto::default(),
        license: LicenseDto::default(),
    };
    formatted.push((
        "ActivationResponse/Debug",
        format!("{activation_response:?}"),
    ));

    let login_payload = LoginPayload {
        session_token: Token::new(SESSION_TOKEN),
        expires_at: "2026-09-24T10:11:12.123456+00:00".into(),
        role: "ADMIN".into(),
        org_id: "org_1".into(),
    };
    formatted.push(("LoginPayload/Debug", format!("{login_payload:?}")));

    let activate_payload = ActivateDevicePayload {
        full_token: Some(Token::new(DEVICE_TOKEN)),
        created: true,
        device_public_id: "dev_1".into(),
        platform: "macos".into(),
    };
    formatted.push((
        "ActivateDevicePayload/Debug",
        format!("{activate_payload:?}"),
    ));

    // ...and the wrappers that print them transitively. A leak-free leaf is worth nothing
    // if the envelope around it re-exposes the value.
    let login_data = LoginData {
        login: login_payload,
    };
    formatted.push(("LoginData/Debug", format!("{login_data:?}")));

    let activate_data = ActivateWithSessionData {
        activate_device_with_session: activate_payload,
    };
    formatted.push((
        "ActivateWithSessionData/Debug",
        format!("{activate_data:?}"),
    ));

    let graphql_envelope: GraphQlResponse<LoginData> = GraphQlResponse {
        data: Some(login_data),
        errors: None,
    };
    formatted.push((
        "GraphQlResponse<LoginData>/Debug",
        format!("{graphql_envelope:?}"),
    ));

    // Positive control: the sweep must be looking at real, non-empty renderings. Without
    // this, a formatter that returned "" would pass every assertion below.
    for (name, rendered) in &formatted {
        assert!(
            !rendered.is_empty(),
            "{name} rendered empty, so the leak sweep below exercises nothing"
        );
    }

    for (name, rendered) in &formatted {
        for secret in [DEVICE_TOKEN, SESSION_TOKEN, ENROLLMENT_KEY, PASSWORD] {
            assert!(
                !rendered.contains(secret),
                "{name} leaked credential material: {rendered}"
            );
        }
    }
}

#[test]
fn every_secret_bearing_wire_field_is_token_typed_so_the_sweep_cannot_fall_behind() {
    // The sweep above enumerates types by hand, and a hand-written list is exactly the
    // thing that falls behind: the first version of it named five types while the crate
    // exposed more, so removing a redaction on the response payloads could never have gone
    // red. Enumerating the FIELDS from the source closes that, because a new
    // secret-bearing field cannot be added without this noticing.
    //
    // The rule: any public wire field whose NAME says it holds a secret must be typed with
    // `Token`, which redacts itself. Exceptions must be listed here with a reason, so
    // adding one is a visible decision rather than an omission.
    let contract = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src/contract.rs");
    let body = std::fs::read_to_string(&contract).unwrap();

    // Fields that legitimately are NOT `Token`, each with the reason it is safe.
    let allowed: &[(&str, &str)] = &[
        // Non-secret metadata about a token: masked form, prefix, suffix, fingerprint,
        // expiry. Carries no secret by construction.
        ("pub token: TokenMetaDto", "metadata only, never the secret"),
        // Must be a plain String to serialize, and is protected by a hand-written
        // redacting Debug asserted in the sweep above.
        ("pub password: String", "hand-redacted Debug on LoginInput"),
    ];

    let mut checked = 0usize;
    let mut token_typed = 0usize;
    for (lineno, line) in body.lines().enumerate() {
        let code = line.trim();
        if !code.starts_with("pub ") || !code.contains(':') {
            continue;
        }
        let name = code
            .trim_start_matches("pub ")
            .split(':')
            .next()
            .unwrap_or("");
        let lowered = name.to_lowercase();
        if !(lowered.contains("token")
            || lowered.contains("password")
            || lowered.contains("secret"))
        {
            continue;
        }
        checked += 1;

        if allowed.iter().any(|(pattern, _)| code.starts_with(pattern)) {
            continue;
        }
        assert!(
            code.contains("Token"),
            "{}:{} declares a secret-bearing field that is not `Token`-typed, so a `{{:?}}` \
             on its struct would print the secret verbatim:\n  {code}\n\
             Type it as `Token`, or add it to `allowed` above with the reason it is safe.",
            contract.display(),
            lineno + 1
        );
        token_typed += 1;
    }

    // Positive controls. Without these the loop could match nothing — a renamed field, a
    // moved file, a broken parse — and the test would pass having checked zero fields.
    assert!(
        checked >= 4,
        "expected to find several secret-bearing wire fields, found {checked}; this guard \
         is no longer looking at the right thing"
    );
    assert!(
        token_typed >= 3,
        "expected at least the three show-once token fields to be Token-typed, found \
         {token_typed}"
    );
}

// --- structural sweeps ----------------------------------------------------------------

fn crate_src_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

#[test]
fn no_filesystem_primitive_is_reachable_from_this_crate() {
    // "Never in a plaintext file" is enforced by making a file unnameable from this crate's
    // own code, in the spirit of `scripts/import_guards.sh` §14. Inspecting a running
    // install would only ever prove the token was absent on the day the test ran; this
    // proves the code has no way to put it there.
    //
    // Comment lines are filtered out because the module docs deliberately NAME these
    // primitives to explain why they are absent, and a guard silenced by deleting a comment
    // would be measuring the wrong thing.
    let forbidden = [
        "std::fs",
        "File::open",
        "OpenOptions",
        "fs::write",
        "fs::read",
        "std::process",
        "Command::new",
    ];

    let mut sources = Vec::new();
    for entry in std::fs::read_dir(crate_src_dir()).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_some_and(|e| e == "rs") {
            sources.push((path.clone(), std::fs::read_to_string(&path).unwrap()));
        }
    }

    // Positive control: the sweep found the sources it is meant to scan.
    assert!(
        sources.len() >= 6,
        "expected to scan the crate's modules, found {} files — the sweep is looking in \
         the wrong place and would pass vacuously",
        sources.len()
    );

    for (path, body) in &sources {
        for (lineno, line) in body.lines().enumerate() {
            let code = line.trim_start();
            if code.starts_with("//") || code.starts_with("*") {
                continue;
            }
            for pattern in forbidden {
                assert!(
                    !code.contains(pattern),
                    "{}:{} names a filesystem/process primitive ({pattern}); the device \
                     token must never be writable to a plaintext file from this crate\n  {code}",
                    path.display(),
                    lineno + 1
                );
            }
        }
    }
}

#[test]
fn the_app_database_schema_has_no_column_that_could_hold_a_credential() {
    // "Never in the app database". The desktop's schema is a forward-only migration list;
    // this reads it and fails if a licensing credential ever acquires a column. Today the
    // schema has none, so the check is cheap — the point is that ADDING one turns it red
    // rather than passing unnoticed.
    let migrations = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../selahcue-data/src/migrations.rs")
        .canonicalize()
        .expect(
            "selahcue-data/src/migrations.rs must exist — if the schema moved, this sweep \
             needs repointing rather than deleting",
        );
    let body = std::fs::read_to_string(&migrations).unwrap().to_lowercase();

    // Positive control: we really did read the migration list, not an empty or moved file.
    assert!(
        body.contains("create table"),
        "{} does not look like the migration list; the sweep would pass vacuously",
        migrations.display()
    );

    for forbidden in [
        "device_token",
        "activation_token",
        "session_token",
        "enrollment_key",
        "license_key",
    ] {
        assert!(
            !body.contains(forbidden),
            "the app database schema mentions {forbidden:?} — licensing credentials belong \
             in the OS secret store, never in the database ({})",
            migrations.display()
        );
    }
}
