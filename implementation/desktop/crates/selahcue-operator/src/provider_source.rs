//! Single source selection for provider readiness and actual request construction.
//! Pilot always takes precedence, including when unavailable; it never falls back
//! to developer environment. Configuration and credential types never cross IPC.
use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
#[cfg_attr(not(any(test, feature = "pilot-credentials")), allow(dead_code))]
pub enum PilotState {
    Available,
    Expired,
    Rejected,
    Unavailable,
}
#[derive(Debug, Clone, Serialize)]
pub struct PilotAccessView {
    pub notes_uses_pilot: bool,
    pub state: PilotState,
    pub notes_state: PilotState,
    pub transcription_state: PilotState,
    pub effective_expiry_unix_seconds: Option<u64>,
    pub replacement_required: bool,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PilotFault {
    Expired,
    Rejected,
    Unavailable,
}
impl PilotFault {
    pub fn code(self) -> &'static str {
        match self {
            Self::Expired => "pilot_expired",
            Self::Rejected => "pilot_access_rejected",
            Self::Unavailable => "pilot_unavailable",
        }
    }
    pub fn message(self) -> &'static str {
        match self {
        Self::Expired=>"Pilot AI access expired. Install a current pilot build. Live presentation and available on-device transcription still work.",
        Self::Rejected=>"Pilot AI access was rejected. Contact the pilot coordinator for a replacement build.",
        Self::Unavailable=>"Pilot AI access is unavailable. Contact the pilot coordinator for a current build. Live presentation and available on-device transcription still work.",
    }
    }
}
fn fault(state: PilotState) -> Option<PilotFault> {
    match state {
        PilotState::Available => None,
        PilotState::Expired => Some(PilotFault::Expired),
        PilotState::Rejected => Some(PilotFault::Rejected),
        PilotState::Unavailable => Some(PilotFault::Unavailable),
    }
}
pub fn notes_fault() -> Option<PilotFault> {
    access_status().and_then(|s| fault(s.notes_state))
}
#[cfg(any(feature = "pilot-credentials", feature = "cloud-stt"))]
pub fn transcription_fault() -> Option<PilotFault> {
    access_status().and_then(|s| fault(s.transcription_state))
}

#[cfg(feature = "pilot-credentials")]
#[allow(dead_code)] // The encoder is consumed by build generation, not the operator.
#[path = "provider_source/payload.rs"]
mod payload;

#[cfg(feature = "pilot-credentials")]
#[used]
static PILOT_PAYLOAD: [u8; include_bytes!(concat!(env!("OUT_DIR"), "/pilot-config.bin")).len()] =
    *include_bytes!(concat!(env!("OUT_DIR"), "/pilot-config.bin"));

#[cfg(feature = "pilot-credentials")]
fn payload_json() -> Option<&'static str> {
    payload::json_from_frame(&PILOT_PAYLOAD)
}

#[cfg(feature = "pilot-credentials")]
fn configuration() -> Option<&'static selahcue_cloud::pilot::PilotConfig> {
    static CONFIG: std::sync::OnceLock<Option<selahcue_cloud::pilot::PilotConfig>> =
        std::sync::OnceLock::new();
    CONFIG
        .get_or_init(|| selahcue_cloud::pilot::PilotConfig::inspect(payload_json()))
        .as_ref()
}
#[cfg(feature = "pilot-credentials")]
struct NativeClock;
#[cfg(feature = "pilot-credentials")]
impl selahcue_core::deadline::Clock for NativeClock {
    fn now(&self) -> selahcue_core::deadline::ClockReading {
        native_reading()
    }
}
#[cfg(feature = "pilot-credentials")]
fn native_reading() -> selahcue_core::deadline::ClockReading {
    use std::time::{Instant, SystemTime};
    #[cfg(test)]
    if let Some(epoch) = std::env::var_os("SELAHCUE_PILOT_TEST_EPOCH") {
        // Runtime-only fixture clock: never compiled into a production executable.
        // Anchor once to real monotonic elapsed time, not once per read/retry.
        static ANCHOR: std::sync::OnceLock<Option<(SystemTime, Instant)>> =
            std::sync::OnceLock::new();
        let anchor = ANCHOR.get_or_init(|| {
            let seconds = epoch.to_str()?.parse::<u64>().ok()?;
            Some((
                std::time::UNIX_EPOCH.checked_add(std::time::Duration::from_secs(seconds))?,
                Instant::now(),
            ))
        });
        return selahcue_core::deadline::ClockReading {
            wall: anchor.and_then(|(wall, start)| wall.checked_add(start.elapsed())),
            monotonic: Instant::now(),
        };
    }
    selahcue_core::deadline::ClockReading {
        wall: Some(SystemTime::now()),
        monotonic: Instant::now(),
    }
}
#[cfg(feature = "pilot-credentials")]
fn deadline(
) -> Result<selahcue_core::deadline::AccessDeadline, selahcue_core::deadline::DeadlineError> {
    use selahcue_core::deadline::{AccessDeadline, DeadlineError};
    static LEASE: std::sync::OnceLock<Result<AccessDeadline, DeadlineError>> =
        std::sync::OnceLock::new();
    LEASE
        .get_or_init(|| {
            let expiry = configuration()
                .ok_or(DeadlineError::Unavailable)?
                .effective_expiry();
            AccessDeadline::admit(
                std::time::UNIX_EPOCH + std::time::Duration::from_secs(expiry),
                std::sync::Arc::new(NativeClock),
            )
        })
        .clone()
}
#[cfg(feature = "pilot-credentials")]
fn notes_rejected() -> std::sync::Arc<std::sync::atomic::AtomicBool> {
    static REJECTED: std::sync::OnceLock<std::sync::Arc<std::sync::atomic::AtomicBool>> =
        std::sync::OnceLock::new();
    REJECTED
        .get_or_init(|| std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)))
        .clone()
}
#[cfg(feature = "pilot-credentials")]
fn transcription_rejected() -> std::sync::Arc<std::sync::atomic::AtomicBool> {
    static REJECTED: std::sync::OnceLock<std::sync::Arc<std::sync::atomic::AtomicBool>> =
        std::sync::OnceLock::new();
    REJECTED
        .get_or_init(|| std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false)))
        .clone()
}
/// Bind the actual worker's rejection publication to the same sticky source lane.
#[cfg(any(feature = "pilot-credentials", feature = "cloud-stt"))]
pub fn transcription_session_status() -> selahcue_stt_cloud::SessionStatus {
    #[cfg(feature = "pilot-credentials")]
    {
        selahcue_stt_cloud::SessionStatus::with_rejection_latch(transcription_rejected())
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        selahcue_stt_cloud::SessionStatus::new()
    }
}
#[cfg(any(test, feature = "pilot-credentials"))]
fn status_from(
    base: PilotState,
    expiry: Option<u64>,
    notes_rejected: bool,
    transcription_rejected: bool,
) -> PilotAccessView {
    let lane = |rejected| {
        if base == PilotState::Expired {
            PilotState::Expired
        } else if rejected {
            PilotState::Rejected
        } else {
            base
        }
    };
    let notes_state = lane(notes_rejected);
    let transcription_state = lane(transcription_rejected);
    let state = [
        PilotState::Expired,
        PilotState::Rejected,
        PilotState::Unavailable,
        PilotState::Available,
    ]
    .into_iter()
    .find(|s| *s == notes_state || *s == transcription_state)
    .unwrap_or(PilotState::Unavailable);
    PilotAccessView {
        notes_uses_pilot: true,
        state,
        notes_state,
        transcription_state,
        effective_expiry_unix_seconds: expiry,
        replacement_required: notes_state != PilotState::Available
            || transcription_state != PilotState::Available,
    }
}
pub fn access_status() -> Option<PilotAccessView> {
    #[cfg(feature = "pilot-credentials")]
    {
        use selahcue_core::deadline::DeadlineError;
        let base = match deadline().and_then(|d| d.remaining()) {
            Ok(_) => PilotState::Available,
            Err(DeadlineError::Expired) => PilotState::Expired,
            Err(DeadlineError::Unavailable) => PilotState::Unavailable,
        };
        Some(status_from(
            base,
            configuration().map(|c| c.effective_expiry()),
            notes_rejected().load(std::sync::atomic::Ordering::SeqCst),
            transcription_rejected().load(std::sync::atomic::Ordering::SeqCst),
        ))
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        None
    }
}
#[cfg(feature = "pilot-credentials")]
fn pilot() -> Option<&'static selahcue_cloud::pilot::PilotConfig> {
    deadline().ok()?.remaining().ok()?;
    configuration()
}
#[cfg(feature = "pilot-credentials")]
fn now() -> Option<u64> {
    native_reading()
        .wall?
        .duration_since(std::time::UNIX_EPOCH)
        .ok()
        .map(|d| d.as_secs())
}
#[cfg(any(feature = "pilot-credentials", feature = "cloud-stt"))]
pub fn transcription_deadline(
) -> Result<Option<selahcue_core::deadline::AccessDeadline>, PilotFault> {
    if let Some(f) = transcription_fault() {
        return Err(f);
    }
    #[cfg(feature = "pilot-credentials")]
    {
        deadline().map(Some).map_err(|_| PilotFault::Unavailable)
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        Ok(None)
    }
}

pub fn notes_model() -> Option<(String, bool)> {
    #[cfg(feature = "pilot-credentials")]
    {
        if notes_fault().is_some() {
            return None;
        }
        pilot().map(|p| (p.openai_model().to_owned(), false))
    }
    #[cfg(all(not(feature = "pilot-credentials"), feature = "openai-notes"))]
    {
        if !selahcue_cloud::openai::direct_key_permitted(cfg!(debug_assertions)) {
            return None;
        }
        let key = std::env::var(selahcue_cloud::openai::API_KEY_ENV).ok();
        notes_model_from_key(key.as_deref(), &selahcue_cloud::openai::model_from_env())
    }
    #[cfg(not(any(feature = "pilot-credentials", feature = "openai-notes")))]
    {
        None
    }
}

#[cfg(feature = "openai-notes")]
pub fn notes_model_from_key(key: Option<&str>, model: &str) -> Option<(String, bool)> {
    key.filter(|k| !k.trim().is_empty())
        .map(|_| (model.to_owned(), true))
}

#[cfg(any(feature = "pilot-credentials", feature = "openai-notes"))]
pub fn openai<T: selahcue_cloud::transport::HttpTransport>(
    transport: T,
) -> Option<selahcue_cloud::OpenAiNoteProvider<T>> {
    #[cfg(feature = "pilot-credentials")]
    {
        if notes_fault().is_some() {
            return None;
        }
        pilot()?.openai(transport, now()?)
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        selahcue_cloud::OpenAiNoteProvider::from_env(transport)
    }
}

#[cfg(any(feature = "pilot-credentials", feature = "cloud-stt"))]
pub fn deepgram() -> Result<selahcue_stt_cloud::Credential, String> {
    #[cfg(feature = "pilot-credentials")]
    {
        // Do not reuse MissingCredential: its developer error explicitly tells the
        // operator to edit .env, which cannot repair a pilot package.
        if let Some(f) = transcription_fault() {
            return Err(f.message().to_owned());
        }
        let unavailable = "pilot package configuration is missing, invalid or expired";
        let key = pilot()
            .and_then(|p| p.deepgram_key(now()?))
            .ok_or_else(|| unavailable.to_owned())?;
        selahcue_stt_cloud::Credential::pilot_key(key.expose()).map_err(|_| unavailable.to_owned())
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        selahcue_stt_cloud::developer_credential_from_env().map_err(|e| e.to_string())
    }
}

pub fn transcription_readiness() -> selahcue_stt_cloud::CloudSttReadiness {
    #[cfg(feature = "pilot-credentials")]
    {
        selahcue_stt_cloud::readiness_from(
            selahcue_stt_cloud::transport_in_build(),
            selahcue_stt_cloud::CredentialPresent::for_credential(deepgram().ok().as_ref()),
        )
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        selahcue_stt_cloud::readiness()
    }
}

pub fn transcription_status() -> selahcue_stt_cloud::CloudSttStatus {
    #[allow(unused_mut)]
    let mut status = transcription_readiness().status();
    #[cfg(feature = "pilot-credentials")]
    {
        status.key_variable = "";
        status.detail = if status.ready {
            "Cloud transcription uses the restricted pilot package configuration"
        } else {
            "Pilot cloud transcription is unavailable: package configuration is missing, invalid or expired"
        };
        if let Some(ref mut provider) = status.provider {
            provider.developer_key = false;
        }
    }
    status
}

#[cfg(any(feature = "pilot-credentials", feature = "openai-notes"))]
pub enum NotesTransport {
    #[cfg(feature = "pilot-credentials")]
    Pilot(selahcue_cloud::deadline_transport::DeadlineTransport),
    #[cfg(not(feature = "pilot-credentials"))]
    Ordinary(selahcue_cloud::transport::ReqwestTransport),
}
#[cfg(any(feature = "pilot-credentials", feature = "openai-notes"))]
impl selahcue_cloud::transport::HttpTransport for NotesTransport {
    fn post_json(
        &self,
        url: &str,
        body: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_cloud::transport::TransportError>
    {
        match self {
            #[cfg(feature = "pilot-credentials")]
            Self::Pilot(t) => t.post_json(url, body, bearer),
            #[cfg(not(feature = "pilot-credentials"))]
            Self::Ordinary(t) => t.post_json(url, body, bearer),
        }
    }
    fn get(
        &self,
        url: &str,
        bearer: Option<&str>,
    ) -> Result<selahcue_cloud::transport::HttpResponse, selahcue_cloud::transport::TransportError>
    {
        match self {
            #[cfg(feature = "pilot-credentials")]
            Self::Pilot(t) => t.get(url, bearer),
            #[cfg(not(feature = "pilot-credentials"))]
            Self::Ordinary(t) => t.get(url, bearer),
        }
    }
}
#[cfg(any(feature = "pilot-credentials", feature = "openai-notes"))]
pub fn notes_transport() -> Result<NotesTransport, selahcue_core::providers::NoteError> {
    #[cfg(not(feature = "pilot-credentials"))]
    use selahcue_core::providers::NoteError;
    #[cfg(feature = "pilot-credentials")]
    {
        pilot_notes_transport_with(selahcue_cloud::deadline_transport::DeadlineTransport::new)
            .map(NotesTransport::Pilot)
    }
    #[cfg(not(feature = "pilot-credentials"))]
    {
        selahcue_cloud::transport::ReqwestTransport::new()
            .map(NotesTransport::Ordinary)
            .map_err(|e| NoteError::Transport(e.to_string()))
    }
}

/// Applicability is supplied only by the actual native route selector, never UI
/// inference. Hosted notes keep their ordinary readiness/errors and are not gated.
#[cfg(feature = "pilot-credentials")]
pub fn access_status_for_route(notes_uses_pilot: bool) -> Option<PilotAccessView> {
    access_status().map(|mut view| {
        view.notes_uses_pilot = notes_uses_pilot;
        if !notes_uses_pilot {
            view.notes_state = PilotState::Available;
            view.state = view.transcription_state;
            view.replacement_required = view.transcription_state != PilotState::Available;
        }
        view
    })
}

/// Constructor injection shares the actual source/observer/admission policy; the
/// application supplies the production HTTPS transport, fixtures use loopback.
#[cfg(feature = "pilot-credentials")]
pub(crate) fn pilot_notes_transport_with<T>(
    build: impl FnOnce(
        selahcue_core::deadline::AccessDeadline,
        std::sync::Arc<std::sync::atomic::AtomicBool>,
    ) -> Result<T, selahcue_cloud::transport::TransportError>,
) -> Result<T, selahcue_core::providers::NoteError> {
    use selahcue_core::providers::NoteError;
    if notes_fault().is_some() {
        return Err(NoteError::NotConfigured);
    }
    let admitted = deadline().map_err(|_| NoteError::NotConfigured)?;
    build(admitted, notes_rejected())
        .map_err(|_| NoteError::Transport("could not initialize pilot HTTP transport".into()))
}

#[cfg(test)]
mod access_tests {
    use super::*;
    #[test]
    fn pilot_rejection_is_lane_specific_and_shared_expiry_overrides_both() {
        let s = status_from(PilotState::Available, Some(1_809_129_599), true, false);
        assert_eq!(s.state, PilotState::Rejected);
        assert_eq!(s.notes_state, PilotState::Rejected);
        assert_eq!(s.transcription_state, PilotState::Available);
        assert!(s.replacement_required);
        let s = status_from(PilotState::Available, Some(1_809_129_599), false, true);
        assert_eq!(s.notes_state, PilotState::Available);
        assert_eq!(s.transcription_state, PilotState::Rejected);
        let s = status_from(PilotState::Expired, Some(1_809_129_599), true, false);
        assert_eq!(s.notes_state, PilotState::Expired);
        assert_eq!(s.transcription_state, PilotState::Expired);
        let value = serde_json::to_value(s).expect("safe status");
        assert_eq!(value.as_object().expect("status").len(), 6);
        assert_eq!(value["effective_expiry_unix_seconds"], 1_809_129_599u64);
    }
}
