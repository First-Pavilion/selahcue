"""Context-bound AES-256-GCM encryption of reusable provider keys."""
import os
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .configuration import get_provider_configuration, selected_role, valid_id
from .contracts import (
    CustodyErrorCode as Code,
    EncryptedSecret,
    ProviderConfigurationError,
    ProviderCustodyError,
    ProviderMappingState as State,
    ProviderScope,
    SecretBytes,
)
from .models import ProviderCredential

_DOMAIN = b"selahcue/provider-secret\x00"


def _keyring(mapping: ProviderCredential, *, roles: set[str]):
    try:
        role = selected_role()
        config = get_provider_configuration(required_role=role)
    except ProviderConfigurationError:
        raise ProviderCustodyError(Code.PCUST_ROLE_DENIED) from None
    scope = ProviderScope(mapping.provider, mapping.parent_scope_id)
    if (
        role not in roles or config.policy is None or config.keyring is None
        or (role == "web" and mapping.provider != "deepgram")
        or (role == "notes" and mapping.provider != "openai")
        or all(scope != entry.scope for entry in config.policy.scopes)
    ):
        raise ProviderCustodyError(Code.PCUST_ROLE_DENIED)
    return config.keyring


def _aad(mapping: ProviderCredential) -> bytes:
    if (
        not isinstance(mapping.pk, UUID) or type(mapping.org_id) is not int or mapping.org_id <= 0
        or not valid_id(mapping.parent_scope_id) or not valid_id(mapping.external_project_id)
        or not valid_id(mapping.external_api_key_id)
        or not (
            (mapping.provider == "deepgram" and mapping.external_project_id == mapping.parent_scope_id
             and mapping.external_service_account_id is None)
            or (mapping.provider == "openai" and valid_id(mapping.external_service_account_id))
        )
    ):
        raise ProviderCustodyError(Code.PCUST_IDENTITY_INCOMPLETE)
    fields = ("1", str(mapping.pk), str(mapping.org_id), mapping.provider,
              mapping.external_project_id, mapping.external_api_key_id)
    encoded = tuple(field.encode("ascii") for field in fields)
    return _DOMAIN + b"".join(len(field).to_bytes(4, "big") + field for field in encoded)


def _validate_secret(secret: bytes) -> None:
    if type(secret) is not bytes or not 1 <= len(secret) <= 4096:
        raise ProviderCustodyError(Code.PCUST_SECRET_INVALID)


def seal_secret(mapping: ProviderCredential, secret: bytes) -> EncryptedSecret:
    keyring = _keyring(mapping, roles={"provisioner"})
    _validate_secret(secret)
    aad = _aad(mapping)
    try:
        active = keyring.active()
        nonce = os.urandom(12)
        sealed = AESGCM(active.material.value).encrypt(nonce, secret, aad)
    except (ProviderConfigurationError, OSError, ValueError):
        raise ProviderCustodyError(Code.PCUST_KEY_UNAVAILABLE) from None
    return EncryptedSecret(1, active.key_id, nonce, sealed)


def _unseal(mapping: ProviderCredential, *, roles: set[str]) -> SecretBytes:
    keyring = _keyring(mapping, roles=roles)
    aad = _aad(mapping)
    nonce, sealed = mapping.secret_nonce, mapping.secret_ciphertext
    if (
        mapping.secret_version != 1 or not valid_id(mapping.wrapping_key_id)
        or not isinstance(nonce, (bytes, memoryview)) or len(nonce) != 12
        or not isinstance(sealed, (bytes, memoryview)) or not 17 <= len(sealed) <= 4112
    ):
        raise ProviderCustodyError(Code.PCUST_ENVELOPE_INVALID)
    try:
        cipher = AESGCM(keyring.lookup(mapping.wrapping_key_id).value)
    except (ProviderConfigurationError, ValueError):
        raise ProviderCustodyError(Code.PCUST_KEY_UNAVAILABLE) from None
    try:
        return SecretBytes(cipher.decrypt(bytes(nonce), bytes(sealed), aad))
    except (InvalidTag, ValueError):
        raise ProviderCustodyError(Code.PCUST_AUTHENTICATION_FAILED) from None


def open_secret(mapping: ProviderCredential) -> SecretBytes:
    if mapping.state != State.ACTIVE:
        raise ProviderCustodyError(Code.PCUST_STATE_INVALID)
    return _unseal(mapping, roles={"web", "notes", "provisioner"})


def _rewrap(mapping: ProviderCredential) -> EncryptedSecret:
    return seal_secret(mapping, _unseal(mapping, roles={"provisioner"}).value)
