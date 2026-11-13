//! C-004: graceful local fallback (FR-135). A failing/unreachable cloud transport
//! must yield a degraded outcome served by the local provider — no panic, output
//! never blocked.

#![allow(clippy::unwrap_used)]

use selahcue_cloud::{
    generate_sermon_notes, generate_sermon_notes_with_factory, CloudNoteProvider,
    DegradedNoteReason, LocalNoteProvider, MockTransport, SelahCueCloudClient,
};
use selahcue_core::providers::{
    NoteDraft, NoteError, NoteProvider, NoteRequest, ProvidersConfig, Quota,
};
use std::cell::{Cell, RefCell};

/// 86akcffy0 (Cody review, High): `generate_sermon_notes` clamps the transcript at its own
/// egress choke point, BEFORE calling any `CloudNoteProvider` — so a hosted `SelahCueCloudClient`
/// (the actual shipping path, DEC-004) is bound by the SAME 400,000-character limit as the
/// OpenAI direct-key provider, even though the client itself never calls `bounded_transcript`.
/// Before this fix, only `openai::build_body` clamped; a from-history transcript past the cap
/// would have gone out to the hosted service in full the moment `cloud-live` becomes real, making
/// the from-history preview's "the final N characters will be left out" disclosure false for
/// that path. Asserted against the REAL wire body a `SelahCueCloudClient` sends (via
/// `MockTransport`'s request recording), not against an internal function in isolation.
#[test]
fn the_hosted_client_never_sends_an_unclamped_transcript() {
    // Distinct HEAD / TAIL markers (QA D5): the wire body must carry the head and not the tail.
    let filler = selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS + 5_000 - 8;
    let huge = format!("HEAD{}TAIL", "a".repeat(filler));

    let transport = MockTransport::responding(
        200,
        r#"{"draft":{"title":"t","summary":null,"introduction":[],"illustrations":[],
             "quotes":[],"prayer_points":[],"calls_to_action":[],"key_lessons":[],
             "chapter_markers":[],"social_excerpts":[],"points":[]},
           "quota":{"used":0,"limit":10,"resets_label":"in 30 days"}}"#,
    );
    // Taken BEFORE `transport` is moved by value into the client below — see
    // `MockTransport::requests_handle`'s doc comment.
    let requests = transport.requests_handle();
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let outcome = generate_sermon_notes(&cfg, &huge, true, &cloud, &local);
    assert!(
        outcome.is_ok(),
        "premise: the mocked hosted response must actually succeed, or this test proves nothing: {outcome:?}"
    );

    let recorded = requests
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    assert_eq!(
        recorded.len(),
        1,
        "premise: exactly one request must have left the device"
    );
    let sent: serde_json::Value =
        serde_json::from_str(&recorded[0].body).expect("the recorded body is valid JSON");
    let sent_transcript = sent["transcript"]
        .as_str()
        .expect("the wire request carries a transcript field");

    assert!(
        sent_transcript.chars().count() <= selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS,
        "the hosted client sent {} characters — the shared clamp did not reach this provider",
        sent_transcript.chars().count()
    );
    assert!(
        sent_transcript.chars().count() < huge.chars().count(),
        "positive control: the sent transcript must genuinely be smaller than the oversized input, \
         not merely 'at or under the cap' by coincidence of a provider that always truncates"
    );
    assert!(
        sent_transcript.starts_with("HEAD") && !sent_transcript.contains("TAIL"),
        "the clamp must keep the START of the transcript and drop the END"
    );
}

#[test]
fn transport_failure_falls_back_to_local_and_marks_degraded() {
    let transport = MockTransport::failing();
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let outcome = generate_sermon_notes(
        &cfg,
        "First point. Second point. Third point.",
        true,
        &cloud,
        &local,
    )
    .unwrap();

    assert!(outcome.degraded, "cloud failed → degraded");
    assert_eq!(outcome.provider_label, "Local (offline)");
    assert!(outcome.quota.is_none());
    // The fallback draft is never blank.
    assert!(!outcome.draft.title.is_empty());
    assert!(!outcome.draft.sections.is_empty());
}

#[test]
fn quota_exceeded_is_not_masked_by_fallback() {
    // 402 → QuotaExceeded is an honest terminal state, not a network blip; it must
    // surface, not silently fall back.
    let transport = MockTransport::responding(402, "{}");
    let cloud = SelahCueCloudClient::new(transport, "https://api.selahcue.example", token());
    let local = LocalNoteProvider::new();

    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;

    let err = generate_sermon_notes(&cfg, "transcript", true, &cloud, &local).unwrap_err();
    assert_eq!(err, selahcue_core::providers::NoteError::QuotaExceeded);
}

fn token() -> selahcue_cloud::Token {
    selahcue_cloud::Token::new("acct-session-token")
}

#[derive(Default)]
struct RecordingLocal(RefCell<Vec<NoteRequest>>);

impl NoteProvider for RecordingLocal {
    fn label(&self) -> &str {
        "Local (offline)"
    }

    fn generate(&self, req: &NoteRequest) -> Result<NoteDraft, NoteError> {
        self.0.borrow_mut().push(req.clone());
        LocalNoteProvider::new().generate(req)
    }

    fn is_generative(&self) -> bool {
        false
    }
}

struct RecordingCloud<'a> {
    requests: &'a RefCell<Vec<NoteRequest>>,
    error: Option<NoteError>,
}

impl NoteProvider for RecordingCloud<'_> {
    fn label(&self) -> &str {
        "Cloud fixture"
    }

    fn generate(&self, req: &NoteRequest) -> Result<NoteDraft, NoteError> {
        self.generate_with_quota(req).map(|(draft, _)| draft)
    }
}

impl CloudNoteProvider for RecordingCloud<'_> {
    fn generate_with_quota(
        &self,
        req: &NoteRequest,
    ) -> Result<(NoteDraft, Option<Quota>), NoteError> {
        self.requests.borrow_mut().push(req.clone());
        match &self.error {
            Some(error) => Err(error.clone()),
            None => Ok((
                LocalNoteProvider::new().generate(req)?,
                Some(Quota::default()),
            )),
        }
    }
}

fn consented() -> ProvidersConfig {
    let mut cfg = ProvidersConfig::default();
    cfg.consent.cloud_notes = true;
    cfg
}

#[test]
fn factory_transport_failure_degrades() {
    let calls = Cell::new(0);
    let transport = MockTransport::failing();
    let requests = transport.requests_handle();
    let local = RecordingLocal::default();

    let outcome = generate_sermon_notes_with_factory(
        &consented(),
        "Opening point. Closing point.",
        true,
        || {
            calls.set(calls.get() + 1);
            drop(transport);
            Err::<SelahCueCloudClient<MockTransport>, _>(NoteError::Transport(
                "cloud HTTP client setup failed".into(),
            ))
        },
        &local,
    )
    .unwrap();

    assert_eq!(calls.get(), 1);
    assert!(requests.lock().unwrap().is_empty());
    assert_eq!(local.0.borrow().len(), 1);
    assert!(outcome.degraded);
    assert_eq!(
        outcome.degraded_reason,
        Some(DegradedNoteReason::ClientSetupFailed)
    );
    assert_eq!(outcome.draft.title, "Opening point");
    assert_eq!(outcome.provider_label, "Local (offline)");
    assert_eq!(outcome.quota, None);
    assert!(!outcome.ai_generated);
    assert_eq!(outcome.disclosure, None);
}

#[test]
fn factory_terminal_errors_propagate() {
    for error in [
        NoteError::ConsentRequired,
        NoteError::NotConfigured,
        NoteError::QuotaExceeded,
        NoteError::Malformed("fixture returned an invalid draft".into()),
    ] {
        let calls = Cell::new(0);
        let requests = RefCell::new(Vec::new());
        let local = RecordingLocal::default();
        let cfg = consented();

        let construction = generate_sermon_notes_with_factory(
            &cfg,
            "Transcript.",
            true,
            || {
                calls.set(calls.get() + 1);
                Err::<RecordingCloud<'_>, _>(error.clone())
            },
            &local,
        );
        assert_eq!(construction.unwrap_err(), error);
        assert_eq!(calls.get(), 1);
        assert!(requests.borrow().is_empty());

        let cloud = || RecordingCloud {
            requests: &requests,
            error: Some(error.clone()),
        };
        let request =
            generate_sermon_notes_with_factory(&cfg, "Transcript.", true, || Ok(cloud()), &local);
        let borrowed = generate_sermon_notes(&cfg, "Transcript.", true, &cloud(), &local);
        assert_eq!(request.unwrap_err(), error);
        assert_eq!(borrowed.unwrap_err(), error);
        assert_eq!(requests.borrow().len(), 2);
        assert!(local.0.borrow().is_empty());
    }
}

fn assert_unadmitted(cfg: &ProvidersConfig, pressed: bool) {
    let local = RecordingLocal::default();
    let result = generate_sermon_notes_with_factory::<RecordingCloud<'_>, _, _>(
        cfg,
        "Transcript.",
        pressed,
        || panic!("unadmitted generation must not construct the cloud provider"),
        &local,
    );
    assert_eq!(result.unwrap_err(), NoteError::ConsentRequired);
    assert!(local.0.borrow().is_empty());
}

#[test]
fn denied_consent_never_calls_factory() {
    assert_unadmitted(&ProvidersConfig::default(), true);
}

#[test]
fn generate_not_pressed_never_calls_factory() {
    assert_unadmitted(&consented(), false);
}

#[test]
fn factory_and_borrowed_paths_share_request_bound() {
    let cap = selahcue_cloud::transcript_bounds::MAX_TRANSCRIPT_CHARS;
    let kept = format!("HEAD. {}", "é".repeat(cap - 6));
    let transcript = format!("{kept}TAIL");
    let cfg = consented();
    let requests = RefCell::new(Vec::new());
    let local = RecordingLocal::default();
    let cloud = || RecordingCloud {
        requests: &requests,
        error: Some(NoteError::Transport(
            "cloud TLS certificate rejected".into(),
        )),
    };
    let borrowed = generate_sermon_notes(&cfg, &transcript, true, &cloud(), &local).unwrap();
    let request =
        generate_sermon_notes_with_factory(&cfg, &transcript, true, || Ok(cloud()), &local)
            .unwrap();
    let construction = generate_sermon_notes_with_factory::<RecordingCloud<'_>, _, _>(
        &cfg,
        &transcript,
        true,
        || {
            Err(NoteError::Transport(
                "cloud TLS certificate rejected".into(),
            ))
        },
        &local,
    )
    .unwrap();
    assert_eq!(request, borrowed);
    assert_eq!(construction, request);
    assert_eq!(
        request.degraded_reason,
        Some(DegradedNoteReason::CertificateRejected)
    );
    assert_eq!(requests.borrow().len(), 2);
    assert_eq!(local.0.borrow().len(), 3);
    for req in requests.borrow().iter().chain(local.0.borrow().iter()) {
        assert_eq!(req.transcript, kept);
    }

    let cloud_success = generate_sermon_notes_with_factory(
        &cfg,
        "Transcript.",
        true,
        || {
            Ok(RecordingCloud {
                requests: &requests,
                error: None,
            })
        },
        &local,
    )
    .unwrap();
    assert!(!cloud_success.degraded);
    assert_eq!(cloud_success.degraded_reason, None);
    assert_eq!(cloud_success.provider_label, "Cloud fixture");
    assert_eq!(cloud_success.quota, Some(Quota::default()));
    assert!(cloud_success.ai_generated);
    assert_eq!(
        cloud_success.disclosure,
        Some(selahcue_core::providers::FABRICATION_DISCLOSURE),
    );
    assert_eq!(local.0.borrow().len(), 3);
}
