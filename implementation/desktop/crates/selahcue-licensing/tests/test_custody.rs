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
    AccountSession, DeviceCredentials, DeviceIdentity, IdempotencyKey, InMemorySecretStore,
    LicensingClient, ScriptedTransport, SecretStore, Token, ACCOUNT_SESSION_NAME,
    DEVICE_TOKEN_NAME,
};
use std::path::PathBuf;

/// Number of `.rs` modules in `src/`. Pinned so a sweep cannot silently cover less.
const EXPECTED_SRC_MODULES: usize = 9;

/// Number of formatted renderings the credential sweep covers. Pinned so an entry cannot
/// quietly disappear from it.
const SWEPT_RENDERINGS: usize = 14;

/// Number of sanctioned `Token::expose()` call sites in `src/`.
///
/// Each one hands out a raw credential. All three are "attach this to an outbound request",
/// and none may be a formatter:
///
/// - `client.rs` — the password into the sign-in mutation's variables
/// - `client.rs` — the enrollment key into the activation request body
/// - `client.rs` — `bearer.map(Token::expose)`, the session token into the Authorization
///   header. This one is a **path call**, which is exactly the form the guard used to miss.
///
/// Pinned so adding one is a decision made here, in the open.
const SANCTIONED_EXPOSE_SITES: usize = 3;

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
fn an_empty_token_does_not_count_as_activated() {
    // F11: `is_activated` used `is_some_and(|t| !t.is_empty())`, and replacing that with a
    // bare `is_some()` survived every test — nothing pinned the emptiness check. A keychain
    // entry can be present and empty after a partial write or a manual edit, and an install
    // in that state would report itself activated while every call it made 401'd.
    let creds = credentials();
    creds.store_device_token(&Token::new("")).unwrap();

    // Positive control: the entry really is present, so the `false` below is about
    // emptiness and not about an absent token.
    assert!(
        creds.device_token().unwrap().is_some(),
        "the empty entry must be present, or this test proves nothing about emptiness"
    );
    assert!(
        !creds.is_activated().unwrap(),
        "an empty string is not a usable device token"
    );

    // ...and a real token still reads as activated, so this is not a blanket refusal.
    creds.store_device_token(&Token::new(DEVICE_TOKEN)).unwrap();
    assert!(creds.is_activated().unwrap());
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

    // --- the test-support transport ----------------------------------------------------
    // `ScriptedTransport` records request bodies verbatim, and those bodies carry the
    // password on sign-in and the enrollment key on activation. Its own comment said a test
    // fixture is exactly where a credential gets copied into a log and then into a bug
    // report — while it printed one. Swept here so that stays fixed.
    let transport = ScriptedTransport::new();
    // Queue REAL responses carrying a device token, so both halves of the transport's
    // redaction claim are exercised. The fixture previously used a bare `new()` and never
    // queued a step, which left "queued responses carry show-once device tokens" — half of
    // what its `Debug` claims to protect — completely untested.
    transport.push_response(
        200,
        format!(
            r#"{{"data":{{"login":{{"sessionToken":"{SESSION_TOKEN}","expiresAt":"x",
            "role":"ADMIN","orgId":"o"}}}}}}"#
        ),
    );
    transport.push_response(
        200,
        format!(
            r#"{{"created":true,"reminted":false,"activation_token":"{DEVICE_TOKEN}",
            "device":{{"device_public_id":"dev_1","status":"ACTIVE","platform":"macos"}},
            "token":{{}},"license":{{"status":"ACTIVATED","expires_at":"x"}}}}"#
        ),
    );
    // ...and one left UNCONSUMED, so the queued-steps side is non-empty when Debug runs.
    transport.push_response(200, format!(r#"{{"activation_token":"{DEVICE_TOKEN}"}}"#));
    let client = LicensingClient::new(transport, "https://api.selahcue.example");
    let _ = client.sign_in("admin@example.test", &Token::new(PASSWORD));
    let _ = client.activate_with_enrollment_key(
        &Token::new(ENROLLMENT_KEY),
        &DeviceIdentity::new("fp-1", "macos", "1.0.0", "Booth").unwrap(),
        &IdempotencyKey::new("idem-0123456789ab").unwrap(),
    );
    // Positive controls for BOTH halves of what this transport's Debug redacts.
    assert!(
        client.transport().request_count() >= 2,
        "both credential-bearing calls must have been recorded, or this entry sweeps nothing"
    );
    assert!(
        format!("{:?}", client.transport()).contains("queued_steps: 1"),
        "a queued response must remain unconsumed, or the queued-payload half of the \
         transport's redaction claim is never exercised"
    );
    formatted.push((
        "RecordedRequest/Debug",
        format!("{:?}", client.transport().recorded()),
    ));
    formatted.push((
        "ScriptedTransport/Debug",
        format!("{:?}", client.transport()),
    ));

    // Positive control: the sweep must be looking at real, non-empty renderings. Without
    // this, a formatter that returned "" would pass every assertion below.
    // --- G4: the sweep list is pinned -------------------------------------------------
    // Deleting an entry is otherwise invisible. Less serious now the fields are `Token`-
    // typed and the source backstop below catches new ones, but it is free to close.
    assert_eq!(
        formatted.len(),
        SWEPT_RENDERINGS,
        "the sweep list changed size; update SWEPT_RENDERINGS deliberately rather than \
         letting an entry disappear"
    );

    // --- G3: PER-ENTRY positive controls ----------------------------------------------
    // Not merely "non-empty". Each entry must visibly carry a REDACTED secret, which is
    // what proves this particular type was exercised with a real credential in it.
    //
    // Without this the sweep passes by coincidence: neutering any fixture — setting
    // `activation_token: None`, `full_token: None`, or `session_token: Token::new("")` —
    // leaves the entry present and non-empty while it exercises nothing at all. All three
    // were demonstrated to survive before this control existed.
    for (name, rendered) in &formatted {
        assert!(
            !rendered.is_empty(),
            "{name} rendered empty, so the leak sweep below exercises nothing"
        );
        assert!(
            rendered.contains("***redacted***"),
            "{name} shows no redaction marker, so either its fixture carries no secret or \
             its secret is not redacted at all — either way this entry proves nothing. \
             Rendered: {rendered}"
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
fn every_secret_bearing_public_field_is_token_typed_so_the_sweep_cannot_fall_behind() {
    // The sweep above enumerates types by hand, and a hand-written list falls behind. This
    // reads the SOURCE instead, so a new secret-bearing field cannot be added without it
    // being noticed — including in a type nobody adds to the sweep.
    //
    // Four limits found by review, each demonstrated rather than theorised:
    //
    // - The vocabulary was `token|password|secret`, so `bearer`, `credential` and `api_key`
    //   slipped through. `key` is the sharp one: this product's other credential is an
    //   **enrollment key / license key**, so `key` is the word a future leak is spelled with.
    // - It read only `contract.rs`, while the rule in `lib.rs` has no file qualifier.
    // - It filtered on `starts_with("pub ")`, so `pub(crate) recovery_token: String` was
    //   invisible — yet a `pub(crate)` field is printed verbatim by its struct's derived
    //   `Debug` just the same.
    // - It tested `contains("Token")` against the WHOLE LINE, so
    //   `pub refresh_key: String, // TODO: wrap in Token` satisfied the guard with a
    //   promise instead of a type.
    let src = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");

    // Words that mark a field as credential-bearing. Deliberately broad: a false positive
    // costs one line in ALLOWED with a reason, a false negative costs a leaked secret.
    const SECRET_WORDS: &[&str] = &["token", "key", "cred", "bearer", "auth", "pass", "secret"];

    // `pub` item forms that are not fields.
    const NOT_FIELDS: &[&str] = &[
        "fn ", "mod ", "use ", "struct ", "enum ", "type ", "const ", "static ", "trait ", "impl ",
    ];

    // Fields that legitimately are NOT `Token`, each with the reason it is safe. Meant to
    // read as a COMPLETE inventory of exceptions.
    const ALLOWED: &[(&str, &str)] = &[
        (
            "token: TokenMetaDto",
            "metadata only (masked/prefix/suffix/fingerprint); no secret",
        ),
        (
            "password: String",
            "must be String to serialize; hand-redacted Debug on LoginInput",
        ),
        (
            "license_key: String",
            "must be String to serialize; hand-redacted Debug on ActivationRequest",
        ),
        (
            "idempotency_key: String",
            "a client-chosen correlation id, deliberately visible in logs",
        ),
        ("key_id: String", "names a PUBLIC key; not secret"),
        (
            "token_meta: Option<TokenMetaDto>",
            "metadata only; no secret",
        ),
        (
            "had_bearer: bool",
            "a flag recording THAT a bearer was sent, never its value",
        ),
    ];

    let mut checked = 0usize;
    let mut token_typed = 0usize;
    let mut scanned_files = 0usize;

    let mut paths: Vec<_> = std::fs::read_dir(&src)
        .unwrap()
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|e| e == "rs"))
        .collect();
    paths.sort();

    for path in &paths {
        scanned_files += 1;
        let body = std::fs::read_to_string(path).unwrap();
        for (lineno, line) in body.lines().enumerate() {
            // Strip any trailing line comment BEFORE looking at the declaration, so a
            // comment can never stand in for a type.
            let code = line.split("//").next().unwrap_or("").trim();
            if !(code.starts_with("pub ") || code.starts_with("pub(")) {
                continue;
            }
            // Everything after the visibility marker, including `pub(crate)` / `pub(in ...)`.
            let declaration = if code.starts_with("pub(") {
                match code.find(')') {
                    Some(paren) => code[paren + 1..].trim(),
                    None => continue,
                }
            } else {
                code.trim_start_matches("pub ").trim()
            };
            if NOT_FIELDS.iter().any(|kw| declaration.starts_with(kw)) {
                continue;
            }
            // A field declaration has a type and no initialiser.
            let Some((name, ty)) = declaration.split_once(':') else {
                continue;
            };
            if declaration.contains('=') {
                continue;
            }
            let (name, ty) = (name.trim(), ty.trim().trim_end_matches(','));
            if !SECRET_WORDS.iter().any(|w| name.to_lowercase().contains(w)) {
                continue;
            }
            checked += 1;
            if ALLOWED
                .iter()
                .any(|(pattern, _)| format!("{name}: {ty}").starts_with(pattern))
            {
                continue;
            }
            // The TYPE must be Token — not the line, not a comment on it.
            assert!(
                ty.contains("Token"),
                "{}:{} declares a credential-named field whose TYPE is not `Token`, so a \
                 `{{:?}}` on its struct would print the secret verbatim:\n  {code}\n\
                 Type it as `Token`, or add it to ALLOWED with the reason it is safe.",
                path.display(),
                lineno + 1
            );
            token_typed += 1;
        }
    }

    // Positive controls. Without these the loop could match nothing — a renamed field, a
    // moved directory, a broken parse — and pass having checked zero fields.
    assert_eq!(
        scanned_files, EXPECTED_SRC_MODULES,
        "expected to scan {EXPECTED_SRC_MODULES} modules, scanned {scanned_files}"
    );
    assert!(
        checked >= 8,
        "expected several credential-named fields across the crate, found {checked}; the \
         guard is no longer looking at the right thing"
    );
    assert!(
        token_typed >= 3,
        "expected at least the three show-once token fields to be Token-typed, found \
         {token_typed}"
    );
}

#[test]
fn the_raw_token_is_never_handed_to_a_formatter() {
    // `Token::expose()` is the one sanctioned way out of the redaction, and nothing stopped
    // `println!("{}", t.expose())` from undoing every other control in this file. The
    // legitimate uses are all "attach this to an outbound request"; none is a formatter.
    //
    // Same spirit as the filesystem-primitive sweep below: make the dangerous shape
    // unwritable rather than merely discouraged.
    let src = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");
    const FORMATTERS: &[&str] = &[
        "println!",
        "eprintln!",
        "print!",
        "eprint!",
        "format!",
        "write!",
        "writeln!",
        "dbg!",
        "panic!",
        "todo!",
        "unimplemented!",
        "log::",
        "tracing::",
    ];

    let mut expose_sites = 0usize;
    let mut scanned = 0usize;
    let mut paths: Vec<_> = std::fs::read_dir(&src)
        .unwrap()
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|e| e == "rs"))
        .collect();
    paths.sort();

    for path in &paths {
        scanned += 1;
        let body = std::fs::read_to_string(path).unwrap();
        for (lineno, line) in body.lines().enumerate() {
            let code = line.split("//").next().unwrap_or("");
            // `expose`, not `expose()`. Matching the method-call spelling with literal
            // empty parens missed the path-call form entirely —
            // `Token::expose(password)` inside an `eprintln!` put a raw password on stderr
            // while this test reported ok. Same mistake as the manifest guard that matched
            // a TOML key instead of the resolved package: pinning a spelling, not a class.
            //
            // The tell was already here. SANCTIONED_EXPOSE_SITES said 2 while `src/` held
            // 3 — `bearer.map(Token::expose)` is invisible to the same substring — so the
            // pin was one short of the inventory it claims to fix, and the number said so.
            if !code.contains("expose") {
                continue;
            }
            expose_sites += 1;
            for formatter in FORMATTERS {
                assert!(
                    !code.contains(formatter),
                    "{}:{} passes an exposed token to {formatter} — the raw secret must \
                     never reach a formatter:\n  {}",
                    path.display(),
                    lineno + 1,
                    code.trim()
                );
            }
        }
    }

    assert_eq!(
        scanned, EXPECTED_SRC_MODULES,
        "expected to scan {EXPECTED_SRC_MODULES} modules, scanned {scanned}"
    );
    // Pinned so a NEW call site is a deliberate decision someone has to make here, not an
    // edit that slips by. Raising this number should always come with a reason.
    assert_eq!(
        expose_sites, SANCTIONED_EXPOSE_SITES,
        "the number of `expose()` call sites changed ({expose_sites} vs \
         {SANCTIONED_EXPOSE_SITES}). Every one hands out a raw credential — confirm the new \
         site attaches it to a request and nothing else, then update this pin."
    );
}

// --- structural sweeps ----------------------------------------------------------------

fn crate_src_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

#[test]
fn no_filesystem_primitive_is_reachable_from_this_crate() {
    // A lexical scan of THIS crate's own `src/` for an enumerated set of spellings, in the
    // spirit of `scripts/import_guards.sh` §14. Worth having: it catches the plain forms,
    // and inspecting a running install would only ever prove the token was absent on the day
    // the test ran.
    //
    // What it does NOT do — stated here because an earlier version of this comment claimed
    // it "proves the code has no way to put it there", and the same false claim in
    // `trust.rs` was a review finding. Security review demonstrated three compiling loaders
    // that pass this guard green: `use std::{env as source};` (the brace breaks the
    // substring), `std :: env :: var(..)` (whitespace does the same), and a helper placed in
    // the path dependency `selahcue-cloud` and called from here, which names no forbidden
    // token in this crate's `src/` at all. No name-scan can close that: reachability is
    // transitive through the dependency graph and the spellings are unbounded. Widening the
    // list moves the boundary; it never closes it.
    //
    // The test's NAME overstates for the same reason — "reachable" implies transitivity this
    // cannot see. It is kept as-is deliberately, so the review trail that cites it stays
    // legible; renaming it to something like `..._is_named_in_this_crates_own_source` is
    // worth doing in the ticket that next touches this file.
    //
    // The effect-level control is the byte scan of the shipped release artefact —
    // `scripts/dev_key_not_in_release.sh`, which ships and RUNS TODAY in `make ci` and CI.
    // An earlier version of this comment called it an obligation deferred onto 86ak5mn1d /
    // 86ak5mn1t; it has not been one for some time, and `TrustedKeys::bundled` says so.
    //
    // It is NOT a superset of this guard and must not be cited as one. It searches the
    // release rlib for the LITERAL key bytes, so it closes "the dev key is COMPILED INTO
    // release" and is blind to "a release binary OBTAINS the key at runtime" — which is
    // precisely the threat this guard names above and also cannot catch. Handing that threat
    // on to the byte scan as "the real guarantee" is what turned two honest admissions into
    // a false claim: QA built the loader that BOTH of them miss (key derived from the seed
    // file's own decimal form, env read placed in `selahcue-cloud`, behind a runtime trigger)
    // and every control in the repository passed it green. The three env-spelling
    // counterexamples named above are security review's — two separate demonstrations, kept
    // apart so the review trail stays traceable.
    //
    // What actually holds this line is the review rule in `TrustedKeys::insert`: no config
    // loader in this crate. That is enforced by a reviewer, deliberately — writing one is a
    // considered act, not a slip, and no name-scan or byte-scan is going to catch it.
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
        // Environment access, added after review found `trust.rs` CLAIMING this guard
        // covered it when it did not. The claim was not idle: an env-var trusted-key loader
        // would defeat the release exclusion **at runtime, inside a release binary, with no
        // `cfg` involved at all** — the `#[cfg(debug_assertions)]` gates would be perfectly
        // intact and perfectly irrelevant. A no-op today because `src/` is otherwise
        // env-free, which is exactly when it is cheapest to close.
        "std::env",
        "env::var",
        "env!(",
        "option_env!(",
    ];

    let mut sources = Vec::new();
    for entry in std::fs::read_dir(crate_src_dir()).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_some_and(|e| e == "rs") {
            sources.push((path.clone(), std::fs::read_to_string(&path).unwrap()));
        }
    }

    // Positive control: the sweep found the sources it is meant to scan.
    // Exact, not `>=`: a floor lets modules disappear from the scan unnoticed.
    assert_eq!(
        sources.len(),
        EXPECTED_SRC_MODULES,
        "expected exactly {EXPECTED_SRC_MODULES} modules, found {} — add or remove the pin \
         deliberately rather than letting the sweep cover less",
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
