#![allow(clippy::unwrap_used)]
use super::*;
#[test]
fn configured_hosted_route_is_captured_without_pilot_restrictions() {
    let _env = crate::ENV_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    struct Restore(Option<std::ffi::OsString>);
    impl Drop for Restore {
        fn drop(&mut self) {
            match self.0.take() {
                Some(v) => std::env::set_var("SELAHCUE_CLOUD_URL", v),
                None => std::env::remove_var("SELAHCUE_CLOUD_URL"),
            }
        }
    }
    let _restore = Restore(std::env::var_os("SELAHCUE_CLOUD_URL"));
    std::env::set_var("SELAHCUE_CLOUD_URL", "https://127.0.0.1:1/fixture-only");
    let app = tauri::test::mock_app();
    let secrets = selahcue_cloud::InMemorySecretStore::new();
    selahcue_cloud::SecretStore::set(
        &secrets,
        ACCOUNT_TOKEN_NAME,
        &selahcue_cloud::Token::new("synthetic-hosted-account-fixture"),
    )
    .unwrap();
    app.handle().manage(AppState {
        backend: Backend::Local(OperatorShell::new(Arc::new(Mutex::new(
            LiveController::new(ServicePlan::new("fixture"), 320, 180, Theme::dark()),
        )))),
        deck: Mutex::new(crate::DeckWorkspace::demo()),
        library: Mutex::new(crate::DeckLibrary::load(None)),
        providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
        providers_db: None,
        transcript_db: None,
        secrets: Box::new(secrets),
        link_status: Mutex::new(selahcue_lan::LinkStatus::local()),
        link_next_attempt: Mutex::new(None),
        media_store: None,
    });
    let state = app.state::<AppState>();
    let captured = selected_notes_route(&state);
    assert!(!captured.uses_pilot());
    let admitted = GeneratedAdmission::for_route(captured.uses_pilot());
    assert!(admitted.ensure().is_ok());
    let status = pilot_access_status(state.clone()).unwrap();
    assert!(!status.notes_uses_pilot);
    assert_eq!(status.notes_state, provider_source::PilotState::Available);
    // This test invocation supplies the committed expired synthetic build config.
    let expect_expired = std::env::var("PILOT_MIXED_EXPECT_EXPIRED").as_deref() == Ok("1");
    if std::env::var("PILOT_TEST_EXPECT_READY").as_deref() == Ok("1") {
        assert_eq!(
            status.transcription_state,
            provider_source::PilotState::Available
        );
    }
    if expect_expired {
        assert_eq!(
            status.transcription_state,
            provider_source::PilotState::Expired
        );
    }
    let view = with_providers(&state, |_| {}).unwrap();
    assert!(!view.pilot_access.unwrap().notes_uses_pilot);
    assert_eq!(view.cloud_status, "hosted");
    assert!(view.notes_available);
    state.secrets.remove(ACCOUNT_TOKEN_NAME).unwrap();
    assert!(selected_notes_route(&state).uses_pilot());
    assert!(!captured.uses_pilot());
    assert!(
        admitted.ensure().is_ok(),
        "captured hosted work must never be retargeted to pilot guards"
    );
    if expect_expired {
        let direct = GeneratedAdmission::for_route(true);
        assert_eq!(direct.ensure(), Err(provider_source::PilotFault::Expired));
    }
}
