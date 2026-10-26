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
        # Traditional email/password auth (DEC-007 / ADR-0023). Customer credentials must
        # never appear in an API payload, audit `after`, or log. The only permitted one-time
        # secret is the direct show-once login/refresh session-token response.
        "password",
        "password_hash",
        "new_password",
        "current_password",
    }
)


def is_restricted_payload_field(key: object) -> bool:
    normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
    return any(
        normalized == "".join(ch for ch in restricted.lower() if ch.isalnum())
        for restricted in RESTRICTED_PAYLOAD_FIELDS
    )


# How deeply a payload may nest before it is refused. Audit and API payloads in this codebase
# are flat or one object deep (a status, a date, an id, the device the licence was activated
# by); a bound of 8 leaves generous room and is still nowhere near CPython's recursion limit.
#
# Why a bound at all (86ak1090r, AC 9): the two walkers below used to recurse without one, so
# a deeply nested `extra_before` / `extra_after` raised `RecursionError` from inside the
# licence state machine's row lock. On the success path that rolls back and is safe; on the
# refusal path it destroys the DENIED audit row, the compliance record NFR-506 exists to
# keep. Refusing at the boundary, with a coded error, happens before any lock is taken.
MAX_PAYLOAD_DEPTH = 8

# A second, independent bound: how many containers one payload may hold. Depth alone does not
# stop SHARED sub-structure (the same mapping referenced from many keys at every level, which
# costs a few objects in memory) from taking `width ** MAX_PAYLOAD_DEPTH` steps to walk. Real
# payloads hold a handful of containers.
MAX_PAYLOAD_CONTAINERS = 2000


def _is_container(value: Any) -> bool:
    return isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    )


def _too_deep() -> SafeAPIError:
    return SafeAPIError(
        ErrorCode.VALIDATION_FAILED,
        f"Payload is nested more than {MAX_PAYLOAD_DEPTH} levels deep or holds more than "
        f"{MAX_PAYLOAD_CONTAINERS} containers.",
    )


def ensure_payload_depth(value: Any) -> None:
    """Refuse (VALIDATION_FAILED) a payload nested deeper than `MAX_PAYLOAD_DEPTH` or holding
    more than `MAX_PAYLOAD_CONTAINERS` containers.

    Iterative on purpose: the check that protects against deep recursion must not itself
    recurse. Strings and bytes are leaves (a `str` is a `Sequence`, and walking one would
    descend a character at a time). A cycle is refused by the same bound as any other
    over-deep structure, because following it only ever increases the depth.
    """
    stack: list[tuple[Any, int]] = [(value, 1)]
    seen = 0
    while stack:
        current, depth = stack.pop()
        if not _is_container(current):
            continue
        seen += 1
        if depth > MAX_PAYLOAD_DEPTH or seen > MAX_PAYLOAD_CONTAINERS:
            raise _too_deep()
        children = current.values() if isinstance(current, Mapping) else current
        stack.extend((child, depth + 1) for child in children if _is_container(child))


def redact_public_payload(value: Any) -> Any:
    ensure_payload_depth(value)
    return _redact(value)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: "[redacted]" if is_restricted_payload_field(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    return value


def assert_no_restricted_payload_fields(value: Any) -> None:
    ensure_payload_depth(value)
    _assert_no_restricted(value)


def _assert_no_restricted(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if is_restricted_payload_field(key) and item != "[redacted]":
                raise SafeAPIError(
                    ErrorCode.VALIDATION_FAILED,
                    f"Restricted field '{key}' cannot be included in public API payloads.",
                )
            _assert_no_restricted(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _assert_no_restricted(item)
