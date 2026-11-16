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
    app.handle().manage(fixture_state(Box::new(secrets)));
    let state = app.state::<AppState>();
    let captured = selected_notes_route(&state);
    assert!(!captured.uses_pilot());
    let admitted = GeneratedAdmission::for_route(captured.uses_pilot());
    assert!(admitted.ensure().is_ok());
    let status =
        tauri::async_runtime::block_on(pilot_access_status_for(app.handle().clone())).unwrap();
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
    let NotesRoute::Hosted { base, token } = captured else {
        panic!("the captured route must stay Hosted");
    };
    let transport = selahcue_cloud::MockTransport::responding(
        200,
        r#"{"draft":{"title":"Hosted fixture","summary":null,"introduction":[],"illustrations":[],
             "quotes":[],"prayer_points":[],"calls_to_action":[],"key_lessons":[],
             "chapter_markers":[],"social_excerpts":[],"points":[]},
           "quota":{"used":0,"limit":10,"resets_label":"in 30 days"}}"#,
    );
    let requests = transport.requests_handle();
    let mut config = selahcue_core::providers::ProvidersConfig::default();
    config.consent.cloud_notes = true;
    let outcome =
        generate_hosted_notes_with(&config, "Completed fixture sermon.", base, token, || {
            Ok(transport)
        })
        .unwrap();
    assert!(!outcome.degraded);
    assert_eq!(outcome.draft.title, "Hosted fixture");
    let recorded = requests.lock().unwrap();
    assert_eq!(recorded.len(), 1);
    assert!(recorded[0]
        .url
        .starts_with("https://127.0.0.1:1/fixture-only/"));
    assert!(recorded[0].had_bearer);
    if expect_expired {
        let direct = GeneratedAdmission::for_route(true);
        assert_eq!(direct.ensure(), Err(provider_source::PilotFault::Expired));
    }
}

fn fixture_state(secrets: Box<dyn selahcue_cloud::SecretStore + Send + Sync>) -> AppState {
    AppState {
        backend: Backend::Local(OperatorShell::new(Arc::new(Mutex::new(
            LiveController::new(ServicePlan::new("fixture"), 320, 180, Theme::dark()),
        )))),
        deck: Mutex::new(crate::DeckWorkspace::demo()),
        library: Mutex::new(crate::DeckLibrary::load(None)),
        providers: Mutex::new(selahcue_core::providers::ProvidersConfig::default()),
        providers_db: None,
        transcript_db: None,
        secrets,
        link_status: Mutex::new(selahcue_lan::LinkStatus::local()),
        link_next_attempt: Mutex::new(None),
        media_store: None,
    }
}

#[test]
fn pilot_status_lookup_keeps_the_event_loop_responsive_while_secret_store_is_held() {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{mpsc, Condvar};
    use std::time::{Duration, Instant};
    let _env = crate::env_locked();
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
    let entered = Arc::new(AtomicBool::new(false));
    let released = Arc::new((Mutex::new(false), Condvar::new()));
    struct HeldStore {
        entered: Arc<AtomicBool>,
        release: Arc<(Mutex<bool>, Condvar)>,
    }
    impl selahcue_cloud::SecretStore for HeldStore {
        fn get(
            &self,
            _: &str,
        ) -> Result<Option<selahcue_cloud::Token>, selahcue_cloud::SecretError> {
            let (lock, cv) = &*self.release;
            let mut released = lock.lock().unwrap();
            self.entered.store(true, Ordering::SeqCst);
            while !*released {
                released = cv.wait(released).unwrap();
            }
            Ok(Some(selahcue_cloud::Token::new(
                "synthetic-held-store-token",
            )))
        }
        fn set(
            &self,
            _: &str,
            _: &selahcue_cloud::Token,
        ) -> Result<(), selahcue_cloud::SecretError> {
            panic!("fixture never writes")
        }
        fn remove(&self, _: &str) -> Result<(), selahcue_cloud::SecretError> {
            panic!("fixture never removes")
        }
    }
    let app = tauri::test::mock_app();
    app.handle().manage(fixture_state(Box::new(HeldStore {
        entered: entered.clone(),
        release: released.clone(),
    })));
    let (responsive_tx, responsive_rx) = mpsc::channel();
    let release_control = released.clone();
    let seen_entered = entered.clone();
    let controller = std::thread::spawn(move || {
        let end = Instant::now() + Duration::from_secs(2);
        while !seen_entered.load(Ordering::SeqCst) && Instant::now() < end {
            std::thread::yield_now();
        }
        let responsive = matches!(
            responsive_rx.recv_timeout(Duration::from_millis(500)),
            Ok(true)
        );
        let (lock, cv) = &*release_control;
        *lock.lock().unwrap() = true;
        cv.notify_all();
        responsive
    });
    // A current-thread executor detects direct blocking AND spawn(async { get }).
    // The external watchdog releases the held fixture even on the RED path.
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    let status = runtime.block_on(async {
        let status = pilot_access_status_for(app.handle().clone());
        let lightweight = async {
            let end = Instant::now() + Duration::from_secs(2);
            while !entered.load(Ordering::SeqCst) {
                assert!(Instant::now() < end);
                tokio::task::yield_now().await;
            }
            view_body(&app.state::<AppState>(), || None).await.unwrap();
            let still_held = !*released.0.lock().unwrap();
            let _ = responsive_tx.send(still_held);
        };
        let (status, ()) = tokio::join!(status, lightweight);
        status.unwrap()
    });
    assert!(controller.join().unwrap(), "status lookup blocked unrelated event-loop work while the synthetic credential service was held");
    assert!(
        !status.notes_uses_pilot,
        "released token must select actual hosted lane"
    );
    assert_eq!(status.notes_state, provider_source::PilotState::Available);
}

#[test]
fn pilot_status_without_hosted_endpoint_never_reads_the_secret_store() {
    use std::sync::atomic::{AtomicUsize, Ordering};
    let _env = crate::env_locked();
    struct Restore(Option<std::ffi::OsString>);
    impl Drop for Restore {
        fn drop(&mut self) {
            if let Some(v) = self.0.take() {
                std::env::set_var("SELAHCUE_CLOUD_URL", v)
            }
        }
    }
    let _restore = Restore(std::env::var_os("SELAHCUE_CLOUD_URL"));
    std::env::remove_var("SELAHCUE_CLOUD_URL");
    let reads = Arc::new(AtomicUsize::new(0));
    struct CountReads(Arc<AtomicUsize>);
    impl selahcue_cloud::SecretStore for CountReads {
        fn get(
            &self,
            _: &str,
        ) -> Result<Option<selahcue_cloud::Token>, selahcue_cloud::SecretError> {
            self.0.fetch_add(1, Ordering::SeqCst);
            Ok(None)
        }
        fn set(
            &self,
            _: &str,
            _: &selahcue_cloud::Token,
        ) -> Result<(), selahcue_cloud::SecretError> {
            panic!("unused")
        }
        fn remove(&self, _: &str) -> Result<(), selahcue_cloud::SecretError> {
            panic!("unused")
        }
    }
    let app = tauri::test::mock_app();
    app.handle()
        .manage(fixture_state(Box::new(CountReads(reads.clone()))));
    let status =
        tauri::async_runtime::block_on(pilot_access_status_for(app.handle().clone())).unwrap();
    assert_eq!(
        reads.load(Ordering::SeqCst),
        0,
        "absent hosted endpoint must not query OS credentials"
    );
    assert!(status.notes_uses_pilot);
    assert_eq!(
        status.notes_state,
        provider_source::access_status().unwrap().notes_state
    );
}

#[test]
fn pilot_failed_status_dispatch_never_grants_a_hosted_exemption() {
    let status = unavailable_notes_access_status().expect("pilot schema");
    assert!(status.notes_uses_pilot);
    assert_eq!(status.notes_state, provider_source::PilotState::Unavailable);
    assert!(status.replacement_required);
    let json = serde_json::to_value(status).expect("safe fields");
    assert_eq!(json.as_object().expect("safe schema").len(), 6);
}
