"""Ed25519 signing of the offline entitlement envelope (DEC-004).

Bytes in, envelope out. This module knows nothing about licensing, devices or HTTP —
it is the only place that touches key material.

**The signature covers the base64url payload string exactly as transmitted**, not a
re-serialization of the decoded JSON. Signing a canonical serialization would require
Python and Rust to agree byte-for-byte on key ordering, separators, unicode escaping
and float formatting; every one of those is a place a signature silently fails to
verify. Signing the transmitted encoding removes the entire class of problem: there is
exactly one byte string, and both sides see it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.conf import settings

ENVELOPE_VERSION = 1
ALGORITHM = "Ed25519"
_SEED_BYTES = 32


class SigningKeyUnavailable(RuntimeError):
    """The signing key is absent or malformed. Never degrade to unsigned output."""


class InvalidEnvelope(ValueError):
    """The envelope is malformed, uses an unexpected algorithm, or fails verification."""


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_signing_key(seed_b64: str | None = None) -> Ed25519PrivateKey:
    """Load the Ed25519 private key from a base64 seed.

    `seed_b64` is for tests; production passes nothing and reads settings. Raises rather
    than returning a fallback key — an unsigned or dev-signed manifest would void the
    offline entitlement model entirely.
    """
    raw = settings.ENTITLEMENT_SIGNING_KEY if seed_b64 is None else seed_b64
    if not raw:
        raise SigningKeyUnavailable("SELAHCUE_ENTITLEMENT_SIGNING_KEY is not set")
    try:
        seed = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as error:
        raise SigningKeyUnavailable("signing key is not valid base64") from error
    if len(seed) != _SEED_BYTES:
        raise SigningKeyUnavailable(
            f"signing key must decode to {_SEED_BYTES} bytes, got {len(seed)}"
        )
    return Ed25519PrivateKey.from_private_bytes(seed)


def derive_key_id(public_key: Ed25519PublicKey) -> str:
    """First 8 hex characters of SHA-256 over the raw public key.

    Derived rather than configured, so a key and its id cannot drift apart and rotation
    needs no registry: the client trusts a set of public keys and selects by this id.
    """
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:8]


def sign_envelope(payload: dict[str, Any], *, private_key: Ed25519PrivateKey) -> dict[str, Any]:
    encoded = _b64u_encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    signature = private_key.sign(encoded.encode("ascii"))
    return {
        "envelope_version": ENVELOPE_VERSION,
        "alg": ALGORITHM,
        "key_id": derive_key_id(private_key.public_key()),
        "payload": encoded,
        "signature": _b64u_encode(signature),
    }


def verify_envelope(envelope: dict[str, Any], *, public_key: Ed25519PublicKey) -> dict[str, Any]:
    """Verify and decode. The reference implementation the Rust verifier mirrors.

    `alg` is checked against a one-element allow-list before any key material is used —
    dispatching on a caller-supplied algorithm field is how confusion attacks work.
    """
    if envelope.get("alg") != ALGORITHM:
        raise InvalidEnvelope(f"unsupported alg: {envelope.get('alg')!r}")
    if envelope.get("envelope_version") != ENVELOPE_VERSION:
        raise InvalidEnvelope(
            f"unsupported envelope_version: {envelope.get('envelope_version')!r}"
        )
    encoded = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(encoded, str) or not isinstance(signature, str):
        raise InvalidEnvelope("payload and signature must both be strings")
    try:
        public_key.verify(_b64u_decode(signature), encoded.encode("ascii"))
    except (InvalidSignature, binascii.Error, ValueError) as error:
        raise InvalidEnvelope("signature verification failed") from error
    try:
        return json.loads(_b64u_decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidEnvelope("payload is not valid JSON") from error
