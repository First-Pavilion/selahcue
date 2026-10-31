//! Single source selection for provider readiness and actual request construction.
//! Pilot always takes precedence, including when unavailable; it never falls back
//! to developer environment. Configuration and credential types never cross IPC.
#[cfg(feature = "pilot-credentials")]
fn pilot() -> Option<selahcue_cloud::pilot::PilotConfig> {
    selahcue_cloud::pilot::PilotConfig::parse(
        Some(include_str!(concat!(env!("OUT_DIR"), "/pilot-config.json"))),
        now()?,
    )
}
#[cfg(feature = "pilot-credentials")]
fn now() -> Option<u64> {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .ok()
        .map(|d| d.as_secs())
}

pub fn notes_model() -> Option<(String, bool)> {
    #[cfg(feature = "pilot-credentials")]
    {
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
