#![cfg(feature = "openai")]
#![allow(clippy::unwrap_used)]
use selahcue_cloud::pilot::PilotConfig;
// Independently checked UTC timestamp; changing the production cutoff must fail admission.
const APPROVED_CUTOFF: u64 = 1_809_129_599;

fn fixture() -> serde_json::Value {
    serde_json::json!({"schema":1,"cohort":"field-test-2026-10", "cutoff":APPROVED_CUTOFF,
        "openai":{"key":"synthetic-openai-fixture-only", "expires_at":APPROVED_CUTOFF,"model":"approved-fixture-model"},
        "deepgram":{"key":"synthetic-deepgram-fixture-only", "expires_at":APPROVED_CUTOFF-100,"model":"nova-3"}})
}
#[test]
fn rejects_absent_malformed_unknown_and_expired_config() {
    assert!(PilotConfig::parse(None, 1).is_none());
    assert!(PilotConfig::parse(Some("{synthetic-sensitive-invalid"), 1).is_none());
    let mut v = fixture();
    v["schema"] = 2.into();
    assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    let v = fixture();
    assert!(PilotConfig::parse(Some(&v.to_string()), APPROVED_CUTOFF - 100).is_none());
}
#[test]
fn earliest_expiry_wins_and_is_rechecked_at_construction() {
    let v = fixture().to_string();
    let c = PilotConfig::parse(Some(&v), 1).expect("valid synthetic config");
    assert!(c
        .openai(
            selahcue_cloud::MockTransport::failing(),
            APPROVED_CUTOFF - 101
        )
        .is_some());
    assert!(c
        .openai(
            selahcue_cloud::MockTransport::failing(),
            APPROVED_CUTOFF - 100
        )
        .is_none());
    assert!(c.deepgram_key(APPROVED_CUTOFF - 101).is_some());
    assert!(c.deepgram_key(APPROVED_CUTOFF - 100).is_none());
    assert_eq!(c.openai_model(), "approved-fixture-model");
}
#[test]
fn rejects_unsafe_fields_and_expiry_extension() {
    for (provider, field, value) in [
        ("openai", "key", "synthetic-secret\r\ninjection"),
        ("deepgram", "key", "synthetic key with spaces"),
        ("openai", "model", "bad/model?key=secret"),
        ("deepgram", "model", "unapproved-model"),
    ] {
        let mut v = fixture();
        v[provider][field] = value.into();
        assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    }
    let mut v = fixture();
    v["openai"]["expires_at"] = (APPROVED_CUTOFF + 1).into();
    assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    let mut v = fixture();
    v["cutoff"] = (APPROVED_CUTOFF + 1).into();
    assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
}

#[test]
fn fixed_deadline_and_both_provider_expiries_are_strict() {
    let mut v = fixture();
    v["deepgram"]["expires_at"] = APPROVED_CUTOFF.into();
    let text = v.to_string();
    assert!(PilotConfig::parse(Some(&text), APPROVED_CUTOFF - 1).is_some());
    assert!(PilotConfig::parse(Some(&text), APPROVED_CUTOFF).is_none());
    assert!(PilotConfig::parse(Some(&text), APPROVED_CUTOFF + 1).is_none());
    v["openai"]["expires_at"] = (APPROVED_CUTOFF - 200).into();
    assert!(PilotConfig::parse(Some(&v.to_string()), APPROVED_CUTOFF - 200).is_none());
    assert!(PilotConfig::parse(Some(&v.to_string()), APPROVED_CUTOFF - 201).is_some());
}
#[test]
fn required_fields_unknown_fields_and_bounds_fail_closed() {
    for field in ["schema", "cohort", "cutoff", "openai", "deepgram"] {
        let mut v = fixture();
        v.as_object_mut().unwrap().remove(field);
        assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    }
    for field in ["key", "expires_at", "model"] {
        for provider in ["openai", "deepgram"] {
            let mut v = fixture();
            v[provider].as_object_mut().unwrap().remove(field);
            assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
        }
    }
    let mut v = fixture();
    v["extra"] = "synthetic-sensitive-field".into();
    assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    let mut v = fixture();
    v["cohort"] = "".into();
    assert!(PilotConfig::parse(Some(&v.to_string()), 1).is_none());
    // Valid JSON plus trailing whitespace: removing the cap must make admission
    // succeed, rather than letting a JSON parse error masquerade as bounded input.
    let oversized = format!(
        "{}{}",
        fixture(),
        " ".repeat(selahcue_cloud::pilot::MAX_CONFIG_BYTES)
    );
    assert!(PilotConfig::parse(Some(&oversized), 1).is_none());
}

#[test]
fn inspection_retains_only_safe_expiry_metadata_after_expiry_without_admitting_credentials() {
    let text = fixture().to_string();
    let c = PilotConfig::inspect(Some(&text)).expect("synthetic config metadata");
    assert_eq!(c.effective_expiry(), APPROVED_CUTOFF - 100);
    assert!(c.deepgram_key(APPROVED_CUTOFF).is_none());
    assert!(c
        .openai(selahcue_cloud::MockTransport::failing(), APPROVED_CUTOFF)
        .is_none());
    assert!(PilotConfig::parse(Some(&text), APPROVED_CUTOFF).is_none());
}
