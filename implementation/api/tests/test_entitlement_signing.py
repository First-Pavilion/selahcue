"""Ed25519 envelope signing — pure crypto, no database.

The load-bearing test here is `tampered_payload_fails_verification`: without it every
other assertion would still pass against a no-op signer.
"""

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from selahcue_api.apps.entitlements.signing import (
    ALGORITHM,
    ENVELOPE_VERSION,
    InvalidEnvelope,
    SigningKeyUnavailable,
    derive_key_id,
    load_signing_key,
    sign_envelope,
    verify_envelope,
)

# A fixed seed so signatures are byte-reproducible across runs. Test-only.
TEST_SEED = bytes(range(32))
TEST_SEED_B64 = base64.b64encode(TEST_SEED).decode("ascii")

PAYLOAD = {"device_public_id": "dev-1", "feature_scope": "pro", "instances_used": 2}


def _key() -> Ed25519PrivateKey:
    return load_signing_key(TEST_SEED_B64)


def test_load_signing_key_accepts_a_valid_seed():
    assert isinstance(_key(), Ed25519PrivateKey)


def test_load_signing_key_rejects_absent_key():
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key("")


def test_load_signing_key_rejects_non_base64():
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key("not!valid!base64!")


def test_load_signing_key_rejects_wrong_length_seed():
    short = base64.b64encode(b"too-short").decode("ascii")
    with pytest.raises(SigningKeyUnavailable):
        load_signing_key(short)


def test_key_id_is_derived_and_stable():
    first = derive_key_id(_key().public_key())
    second = derive_key_id(_key().public_key())
    assert first == second
    assert len(first) == 8
    assert all(c in "0123456789abcdef" for c in first)


def test_key_id_differs_for_a_different_key():
    other = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    assert derive_key_id(_key().public_key()) != derive_key_id(other.public_key())


def test_envelope_has_the_declared_shape():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    assert envelope["envelope_version"] == ENVELOPE_VERSION
    assert envelope["alg"] == ALGORITHM
    assert envelope["key_id"] == derive_key_id(_key().public_key())
    assert isinstance(envelope["payload"], str)
    assert isinstance(envelope["signature"], str)


def test_roundtrip_returns_the_original_payload():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    assert verify_envelope(envelope, public_key=_key().public_key()) == PAYLOAD


def test_signing_is_deterministic_for_a_fixed_seed():
    # Ed25519 is deterministic — the same key and message always yield the same signature.
    a = sign_envelope(PAYLOAD, private_key=_key())
    b = sign_envelope(PAYLOAD, private_key=_key())
    assert a == b


def test_tampered_payload_fails_verification():
    """THE test. Flip one byte of the payload; verification must reject it."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    raw = envelope["payload"]
    flipped = "A" if raw[5] != "A" else "B"
    envelope["payload"] = raw[:5] + flipped + raw[6:]
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_signature_from_a_different_key_is_rejected():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    attacker = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=attacker.public_key())


def test_unexpected_alg_is_rejected_before_any_verification():
    """Algorithm confusion: a verifier must allow-list, not dispatch on the field."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    envelope["alg"] = "HS256"
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_unexpected_envelope_version_is_rejected():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    envelope["envelope_version"] = ENVELOPE_VERSION + 1
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_signature_covers_the_encoded_string_not_a_reserialization():
    """Re-encoding the decoded payload with different JSON formatting must NOT verify —
    proof that the signature is over the transmitted bytes, which is what lets the Rust
    verifier agree without matching Python's JSON formatting."""
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    decoded = verify_envelope(envelope, public_key=_key().public_key())
    padded = json.dumps(decoded, sort_keys=True, indent=2)  # different whitespace
    envelope["payload"] = (
        base64.urlsafe_b64encode(padded.encode("utf-8")).decode("ascii").rstrip("=")
    )
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())


def test_non_string_payload_or_signature_is_rejected():
    envelope = sign_envelope(PAYLOAD, private_key=_key())
    envelope["signature"] = 12345
    with pytest.raises(InvalidEnvelope):
        verify_envelope(envelope, public_key=_key().public_key())
