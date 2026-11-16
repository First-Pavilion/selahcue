"""The fixed direct-STT policy and its read-only client metadata."""
from selahcue_api.platform.cloud_contracts import MeterPolicyVersions

from .configuration import get_provider_configuration
from .contracts import MintPolicy, ProviderConfigurationError

STT_VERSIONS = MeterPolicyVersions("stt-direct-v1", "stt-direct-audio-v1")
STT_MINT_POLICY = MintPolicy("deepgram", 30, 2, 2, 4, "wss://api.deepgram.com/v1/listen")


def stt_configuration():
    try:
        config = get_provider_configuration(required_role="web")
        if (
            "deepgram" in config.requested_public_providers and config.keyring is not None
            and config.policy is not None and any(
                row.scope.provider == "deepgram" for row in config.policy.scopes
            )
        ):
            config.keyring.active()
            return config
    except ProviderConfigurationError:
        return None
    return None


def get_stt_policy_versions() -> MeterPolicyVersions | None:
    return STT_VERSIONS if stt_configuration() is not None else None
