"""Translate the bounded Deepgram grant reply into finite issuance evidence."""
import base64
import binascii
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException
import re

from selahcue_api.apps.providers.contracts import (
    EphemeralGrant, Granted, MintFailureCode as Code, MintOutcome, OutcomeUnknown, SecretBytes,
)
from selahcue_api.apps.providers.stt_policy import STT_MINT_POLICY
from selahcue_api.apps.usage.weeks import utc_instant

from .grants_child import MAX_RESPONSE, strict_object

_MAX_ACCESS_TOKEN = 12288


def _segment(segment, maximum):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", segment):
        raise ValueError("Invalid JWT segment")
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except binascii.Error:
        raise ValueError("Invalid JWT segment") from None
    if len(raw) > maximum or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != segment:
        raise ValueError("Invalid JWT segment")
    return raw


def parse_grant(status: int, body: bytes, *, request_started_at: datetime,
                response_received_at: datetime) -> MintOutcome:
    if status != 200:
        return OutcomeUnknown(Code.PROVIDER_OUTCOME_UNPROVEN)
    try:
        if len(body) > MAX_RESPONSE:
            raise ValueError("Oversized grant")
        payload = strict_object(body, parse_float=Decimal)
        if not {"access_token"} <= payload.keys() <= {"access_token", "expires_in"}:
            raise ValueError("Invalid grant keys")
        if "expires_in" in payload:
            lifetime = payload["expires_in"]
            if type(lifetime) not in (int, Decimal) or not 0 < lifetime <= 30:
                raise ValueError("Invalid credential lifetime")
        token = payload["access_token"]
        if type(token) is not str or not 0 < len(token) <= _MAX_ACCESS_TOKEN or not token.isascii():
            raise ValueError("Invalid access token")
        header, claims, signature = token.split(".")
        algorithm = strict_object(_segment(header, 1024), parse_float=Decimal).get("alg")
        if type(algorithm) is not str or not algorithm or algorithm.lower() == "none":
            raise ValueError("Invalid JWT algorithm")
        expiration = strict_object(_segment(claims, 8192), parse_float=Decimal).get("exp")
        _segment(signature, _MAX_ACCESS_TOKEN)
        if type(expiration) is not int or not 0 <= expiration <= 253402300799:
            raise ValueError("Invalid JWT expiration")
        expires_at = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=expiration)
        if not utc_instant(response_received_at) < expires_at <= utc_instant(request_started_at) + timedelta(seconds=34):
            raise ValueError("Invalid credential lifetime")
    except (ValueError, TypeError, RecursionError, OverflowError, DecimalException):
        return OutcomeUnknown(Code.INVALID_PROVIDER_RESPONSE)
    return Granted(EphemeralGrant(SecretBytes(token.encode("ascii")), STT_MINT_POLICY.endpoint, expires_at, "deepgram"))
