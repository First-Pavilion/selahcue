//! Validated native pilot package configuration. No environment access, serialization,
//! Debug or Display: malformed input is discarded without quoting parser errors.
//! This is an extraction-prone embedded credential source, not a secret vault. Actual
//! provider-side restrictions/expiry and release admission remain external prerequisites.
use crate::{openai::OpenAiNoteProvider, secret::Token, transport::HttpTransport};
use serde::Deserialize;

/// Fixed owner-approved cohort deadline: 2027-04-30T23:59:59Z (Unix seconds).
pub const COHORT_CUTOFF: u64 = 1_809_129_599;
pub const MAX_CONFIG_BYTES: usize = 16_384;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Provider {
    key: Token,
    expires_at: u64,
    model: String,
}

/// Secret-bearing configuration. It deliberately implements no formatting traits.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ConfigInput {
    schema: u32,
    cohort: String,
    cutoff: u64,
    openai: Provider,
    deepgram: Provider,
}

impl ConfigInput {
    fn effective_expiry(&self) -> u64 {
        self.cutoff
            .min(self.openai.expires_at)
            .min(self.deepgram.expires_at)
    }
}

/// Admitted configuration. Only `parse` can construct this type; deserialization
/// cannot bypass schema, key, model and expiry validation.
pub struct PilotConfig {
    config: ConfigInput,
}

fn identifier(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 128
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'))
}
fn valid_key(key: &Token) -> bool {
    let s = key.expose();
    (16..=4096).contains(&s.len()) && s.bytes().all(|b| b.is_ascii_graphic())
}

impl PilotConfig {
    /// All-or-nothing source admission. Epoch seconds are UTC; missing/bad clocks fail
    /// closed at the caller. No provider can outlive the cohort or its partner's expiry.
    pub fn parse(input: Option<&str>, now: u64) -> Option<Self> {
        Self::inspect(input).filter(|config| config.available(now))
    }

    /// Validate configuration without admitting credentials, retaining safe expiry
    /// metadata for an expired/replacement UI. Credential exits still check time.
    pub fn inspect(input: Option<&str>) -> Option<Self> {
        let input = input.filter(|s| !s.is_empty() && s.len() <= MAX_CONFIG_BYTES)?;
        let config: ConfigInput = serde_json::from_str(input).ok()?;
        if config.schema != 1
            || !identifier(&config.cohort)
            || config.cutoff != COHORT_CUTOFF
            || !identifier(&config.openai.model)
            || config.deepgram.model != "nova-3"
            || !valid_key(&config.openai.key)
            || !valid_key(&config.deepgram.key)
            || config.openai.expires_at > config.cutoff
            || config.deepgram.expires_at > config.cutoff
            || config.openai.expires_at == 0
            || config.deepgram.expires_at == 0
        {
            return None;
        }
        Some(Self { config })
    }

    pub fn effective_expiry(&self) -> u64 {
        self.config.effective_expiry()
    }
    pub fn available(&self, now: u64) -> bool {
        now < self.effective_expiry()
    }
    pub fn openai_model(&self) -> &str {
        &self.config.openai.model
    }

    /// Recheck time for every new construction, including regeneration.
    pub fn openai<T: HttpTransport>(
        &self,
        transport: T,
        now: u64,
    ) -> Option<OpenAiNoteProvider<T>> {
        self.available(now).then(|| {
            OpenAiNoteProvider::new(
                transport,
                self.config.openai.key.clone(),
                self.config.openai.model.clone(),
            )
        })
    }
    /// Deliberate native-only exit to the Deepgram injected credential constructor.
    /// Never expose this token through IPC, logs or frontend state.
    pub fn deepgram_key(&self, now: u64) -> Option<Token> {
        self.available(now)
            .then(|| self.config.deepgram.key.clone())
    }
}
