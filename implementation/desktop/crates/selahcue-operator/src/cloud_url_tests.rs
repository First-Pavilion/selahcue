//! Actual env reads use a fresh child test process, never mutate parallel sibling env.
#![cfg(feature = "cloud-live")]
#[path = "../../selahcue-cloud/tests/support/credential_receiver.rs"]
mod credential_receiver;
use credential_receiver::Receiver;
use selahcue_cloud::transport::{HttpTransport, ReqwestTransport};

fn probe(base: Option<&str>, send: bool) -> std::process::Output {
    let mut command = std::process::Command::new(std::env::current_exe().expect("test exe"));
    command
        .args([
            "--exact",
            "cloud_url_tests::dnu_operator_env_probe",
            "--nocapture",
            "--test-threads=1",
        ])
        .env("DNU_CLOUD_URL_PROBE", if send { "send" } else { "inspect" });
    match base {
        Some(base) => {
            command.env("SELAHCUE_CLOUD_URL", base);
        }
        None => {
            command.env_remove("SELAHCUE_CLOUD_URL");
        }
    }
    let output = command.output().expect("child probe");
    assert!(
        output.status.success(),
        "probe failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        String::from_utf8_lossy(&output.stdout).contains("1 passed; 0 failed"),
        "probe did not execute"
    );
    output
}
#[test]
fn dnu_operator_env_probe() {
    let Ok(mode) = std::env::var("DNU_CLOUD_URL_PROBE") else {
        return;
    };
    let base = super::cloud_base_url();
    println!("DNU_CONFIG_SELECTED {}", u8::from(base.is_some()));
    assert_eq!(
        super::hosted_notes_provider(true).0.is_some(),
        base.is_some()
    );
    if mode == "send" {
        if let Some(base) = base {
            let _ = ReqwestTransport::new().expect("transport").post_json(
                &format!("{base}/v1/notes"),
                "DNU-TRANSCRIPT-SECRET",
                Some("DNU-ACCOUNT-SECRET"),
            );
        }
    }
}
#[test]
fn dnu_operator_http_env_refuses_before_transcript_or_bearer_send() {
    let receiver = Receiver::start();
    let output = probe(Some(&receiver.base), true);
    let seen = receiver.finish();
    assert!(
        seen.is_empty(),
        "operator selected insecure base and sent {} requests",
        seen.len()
    );
    assert!(String::from_utf8_lossy(&output.stdout).contains("DNU_CONFIG_SELECTED 0"));
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("SELAHCUE_CLOUD_URL must be an HTTPS URL")
    );
}
#[test]
fn dnu_operator_configuration_refusals_are_data_free() {
    for base in [
        "http://alice:URL-SECRET@127.0.0.1/?query=QUERY-SECRET",
        "ftp://example.test/?QUERY-SECRET",
        "//example.test/?QUERY-SECRET",
        "httpsnot://example.test/?QUERY-SECRET",
        "https://",
    ] {
        let output = probe(Some(base), false);
        assert!(String::from_utf8_lossy(&output.stdout).contains("DNU_CONFIG_SELECTED 0"));
        let stderr = String::from_utf8_lossy(&output.stderr);
        assert!(stderr.contains("SELAHCUE_CLOUD_URL must be an HTTPS URL"));
        for secret in ["URL-SECRET", "QUERY-SECRET", "alice"] {
            assert!(!stderr.contains(secret));
        }
    }
}
#[test]
fn dnu_operator_https_and_unconfigured_controls() {
    for base in [
        "https://api.selahcue.example",
        "HTTPS://api.selahcue.example/base/",
    ] {
        let output = probe(Some(base), false);
        assert!(String::from_utf8_lossy(&output.stdout).contains("DNU_CONFIG_SELECTED 1"));
    }
    for base in [None, Some("")] {
        let output = probe(base, false);
        assert!(String::from_utf8_lossy(&output.stdout).contains("DNU_CONFIG_SELECTED 0"));
        assert!(output.stderr.is_empty());
    }
}
