from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from selahcue_api.graphql.errors import ErrorCode, SafeAPIError


RESTRICTED_PAYLOAD_FIELDS = frozenset(
    {
        "license_key",
        "full_key",
        "secret",
        "provider_secret",
        "signing_key",
        "device_token",
        "bible_text",
        "content",
        # OIDC / customer-identity credentials (ADR-0022 security review, task 86ajy7aqw) — must
        # never appear in an API payload, audit `after`, or log. Added ahead of the OIDC RP so the
        # denylist is in place when those fields start flowing. NB: the exact names normalise to
        # distinct tokens (e.g. "authorization_code" != the error-envelope "code"), so existing
        # payloads are unaffected.
        "access_token",
        "refresh_token",
        "id_token",
        "code_verifier",
        "authorization_code",
        "client_secret",
    }
)


def is_restricted_payload_field(key: object) -> bool:
    normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
    return any(
        normalized == "".join(ch for ch in restricted.lower() if ch.isalnum())
        for restricted in RESTRICTED_PAYLOAD_FIELDS
    )


def redact_public_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: "[redacted]" if is_restricted_payload_field(key) else redact_public_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_public_payload(item) for item in value]
    return value


def assert_no_restricted_payload_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if is_restricted_payload_field(key) and item != "[redacted]":
                raise SafeAPIError(
                    ErrorCode.VALIDATION_FAILED,
                    f"Restricted field '{key}' cannot be included in public API payloads.",
                )
            assert_no_restricted_payload_fields(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            assert_no_restricted_payload_fields(item)
