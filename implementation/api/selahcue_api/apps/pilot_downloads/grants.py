"""Private pilot grant boundary, separate from licensed/device download APIs.

P10 supplies a real exact-object GET signer. Until then production returns503;
only tests inject synthetic signers. No Google write, external call under a lock,
new registration row, or mutable 'latest' artifact resolution occurs here.
"""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Protocol
from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.utils import timezone

from selahcue_api.apps.pilot_downloads.grant_manifest import COHORT_CUTOFF, SIGNING_STATES, identifier, load_manifest
from selahcue_api.apps.pilot_downloads.policy import PilotPolicy, PilotRegistrationError, load_policy
from selahcue_api.apps.pilot_downloads.services import verify_registration_receipt


@dataclass(frozen=True, repr=False)
class GrantPolicy:
    n8n_token: str
    storage_target: str
    download_origin: str
    manifest_path: str
    manifest_sha256: str
    max_ttl_seconds: int
    signed_query_keys: tuple[str, ...]
    signing_requirements: dict[str, str]
    cohort_id: str


@dataclass(frozen=True, repr=False)
class PrivateReadRequest:
    storage_target: str
    object_key: str
    sha256: str
    expires_at: int


@dataclass(frozen=True, repr=False)
class SignedRead:
    url: str
    expires_at: int


class PrivateReadSigner(Protocol):
    def sign_read(self, request: PrivateReadRequest) -> SignedRead:
        """Bounded exact-object GET only, no list/write/redirect or raw logging.

        The concrete P10 adapter must enforce its own connect/read/total timeout
        and verify object immutability; returning this type is not such proof.
        """
        ...


def configured_private_read_signer(policy: GrantPolicy) -> PrivateReadSigner | None:
    # No production adapter is configured until P10 fixes the provider and proves
    # anonymous-read refusal, immutable keys, minimal rights and bounded GETs.
    # Deliberately no synthetic/default/public URL implementation.
    return None


def load_grant_policy(registration_policy: PilotPolicy | None = None) -> GrantPolicy:
    raw = getattr(settings, "SELAHCUE_PILOT_DOWNLOAD_GRANTS", {})
    if not isinstance(raw, dict) or raw.get("enabled") is not True:
        raise PilotRegistrationError("downloads_disabled", 404)
    registration_policy = registration_policy or load_policy()
    try:
        token = raw["n8n_token"]
        if (not isinstance(token, str) or not 32 <= len(token) <= 256 or not token.isascii() or any(not 33 <= ord(c) <= 126 for c in token) or
                token in (registration_policy.n8n_token, registration_policy.signing_key, registration_policy.fingerprint_key)):
            raise ValueError
        target, cohort = raw["storage_target"], raw["cohort_id"]
        if not identifier(target) or not identifier(cohort):
            raise ValueError
        origin = raw["download_origin"]
        if not isinstance(origin, str) or len(origin) > 300 or not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", origin):
            raise ValueError
        path = raw["manifest_path"]
        if not isinstance(path, str) or len(path) > 4096 or not Path(path).is_absolute():
            raise ValueError
        digest = raw["manifest_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError
        ttl_raw = raw["max_ttl_seconds"]
        if type(ttl_raw) not in (str, int):
            raise ValueError
        ttl = int(ttl_raw)
        if not 1 <= ttl <= 300:
            raise ValueError
        query_keys = raw["signed_query_keys"]
        if (not isinstance(query_keys, (tuple, list)) or not 1 <= len(query_keys) <= 20 or
                any(not identifier(k, 64) for k in query_keys) or len(set(query_keys)) != len(query_keys)):
            raise ValueError
        forbidden = {"receipt", "registration_id", "email", "name", "full_name", "phone", "church_name", "openai_api_key", "deepgram_api_key", "redirect", "url", "response-content-disposition"}
        if any(k.lower() in forbidden for k in query_keys):
            raise ValueError
        signing = raw["signing_requirements"]
        if isinstance(signing, str):
            signing = json.loads(signing)
        if (not isinstance(signing, dict) or set(signing) != set(SIGNING_STATES) or
                any(not isinstance(signing[k], str) or signing[k] not in allowed for k, allowed in SIGNING_STATES.items())):
            raise ValueError
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
        raise PilotRegistrationError("download_configuration_required", 503) from None
    return GrantPolicy(token, target, origin, path, digest, ttl, tuple(query_keys), signing, cohort)


def _seconds(value: datetime) -> int:
    if timezone.is_naive(value):
        raise PilotRegistrationError("downloads_temporarily_unavailable", 503)
    return int(value.timestamp())


def grant_download(payload: object, *, signer: PrivateReadSigner | None = None,
                   policy: GrantPolicy | None = None, registration_policy: PilotPolicy | None = None) -> dict:
    registration_policy = registration_policy or load_policy()
    policy = policy or load_grant_policy(registration_policy)
    if (not isinstance(payload, dict) or set(payload) != {"schema_version", "receipt", "artifact_id"} or
            type(payload["schema_version"]) is not int or payload["schema_version"] != 1 or not identifier(payload["artifact_id"])):
        raise PilotRegistrationError("download_request_invalid", 400)
    # P13 owns authenticity, audience, pending/confirmed/retired ledger and anchored TTL.
    claims = verify_registration_receipt(payload["receipt"], policy=registration_policy)
    now = _seconds(timezone.now())
    manifest = load_manifest(policy, now)
    artifact = next((entry for entry in manifest.artifacts if entry.artifact_id == payload["artifact_id"]), None)
    if artifact is None or artifact.platform != claims["platform"]:
        raise PilotRegistrationError("download_selection_unavailable", 409)
    deadline = min(claims["expires_at"], COHORT_CUTOFF, _seconds(registration_policy.pilot_expires_at),
                   manifest.expires_at, artifact.credentials_expires_at, now + policy.max_ttl_seconds)
    if deadline <= now:
        raise PilotRegistrationError("download_expired", 410)
    signer = signer or configured_private_read_signer(policy)
    if signer is None:
        raise PilotRegistrationError("download_configuration_required", 503)
    request = PrivateReadRequest(policy.storage_target, artifact.object_key, artifact.sha256, deadline)
    try:
        result = signer.sign_read(request)
        if (not isinstance(result, SignedRead) or type(result.expires_at) is not int or
                not _seconds(timezone.now()) < result.expires_at <= deadline or
                not isinstance(result.url, str) or len(result.url) > 8192 or not result.url.isascii() or
                any(ord(c) < 33 or ord(c) > 126 for c in result.url)):
            raise ValueError
        parsed = urlsplit(result.url)
        if (parsed.scheme + "://" + parsed.netloc != policy.download_origin or
                parsed.path != "/" + artifact.object_key or parsed.fragment or parsed.username or parsed.password):
            raise ValueError
        query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=20)
        if not query or len({k for k, _ in query}) != len(query):
            raise ValueError
        forbidden_values = (payload["receipt"], claims["registration_id"], policy.n8n_token,
                            registration_policy.n8n_token, registration_policy.signing_key, registration_policy.fingerprint_key)
        if any(k not in policy.signed_query_keys or not v or len(v) > 2048 or
               any(secret in v for secret in forbidden_values) or any(ord(c) < 32 or ord(c) > 126 for c in v) for k, v in query):
            raise ValueError
    except Exception:
        # Provider errors/URL bodies may contain credentials; discard rather than
        # interpolate/log. Cancellation/process-control exceptions still propagate.
        raise PilotRegistrationError("download_signing_unavailable", 503) from None
    return {"schema_version": 1, "artifact_id": artifact.artifact_id, "release_id": manifest.release_id,
            "platform": artifact.platform, "architectures": list(artifact.architectures), "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes, "download_url": result.url, "expires_at": result.expires_at}
