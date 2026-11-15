"""Bounded keyring inputs, authenticated custody and recoverable rotation."""
from pathlib import Path
from uuid import uuid4

import pytest
from django.db import transaction

from provider_helpers import (
    SECRET, audit, cold_provider_cache, identity, keyring, provider_mounts,
    provisioner_runtime, write_mount,
)

from selahcue_api.apps.providers.configuration import _read_keyring, load_provider_configuration
from selahcue_api.apps.providers.contracts import (
    ProviderConfigurationError, ProviderCustodyError, ProviderRegistryError, RegistryReason,
)
from selahcue_api.apps.providers.custody import open_secret
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.providers.registry import (
    import_existing_mapping, retire_mapping, rotate_wrapping_key_batch,
)

from test_effective_org_plan import NOW, church

pytestmark = pytest.mark.django_db


def test_missing_active_key_is_a_safe_configuration_error(settings, tmp_path):
    path = tmp_path / "synthetic-private-filename"
    path.write_text('{"schema_version":1,"active_key_id":"missing","keys":{"present":"' + "A" * 43 + '"}}')
    path.chmod(0o400)
    settings.SELAHCUE_PROVIDER_KEYRING_FILE = str(path)
    with pytest.raises(ProviderConfigurationError, match="PCFG_KEY_MISSING") as error:
        _read_keyring()
    assert "synthetic-private-filename" not in str(error.value)


@pytest.mark.parametrize(("raw", "code"), [
    (b" " * 65537, "PCFG_FILE_TOO_LARGE"),
    (b"\xff", "PCFG_ENCODING_INVALID"),
    (b"\xef\xbb\xbf{}", "PCFG_ENCODING_INVALID"),
    (b'{"schema_version":1,"schema_version":1}', "PCFG_JSON_INVALID"),
    (b'{"keys":{"old":"synthetic-secret", "old":"other"}}', "PCFG_JSON_INVALID"),
    (b'{"schema_version":NaN}', "PCFG_JSON_INVALID"),
    (b'{"schema_version":1.0}', "PCFG_JSON_INVALID"),
    (b'{"schema_version":true}', "PCFG_SCHEMA_INVALID"),
    (b'{"schema_version":1,"active_key_id":"old","keys":{"old":"' + b"A" * 42 + b'B"}}',
     "PCFG_KEY_INVALID"),
])
def test_keyring_parser_rejects_unsafe_inputs_without_echo(raw, code, settings, tmp_path, provider_mounts):
    provider_mounts("provisioner")
    settings.SELAHCUE_PROVIDER_KEYRING_FILE = write_mount(tmp_path, "synthetic-do-not-echo-path", raw)
    with pytest.raises(ProviderConfigurationError, match=code) as error:
        load_provider_configuration("provisioner")
    assert "synthetic-secret" not in str(error.value)
    assert "synthetic-do-not-echo-path" not in str(error.value)


@pytest.mark.parametrize("mode", [0o644, 0o440, 0o401, 0o1400, 0o200])
def test_keyring_owner_only_regular_file(mode, settings, provider_mounts):
    provider_mounts("provisioner")
    Path(settings.SELAHCUE_PROVIDER_KEYRING_FILE).chmod(mode)
    with pytest.raises(ProviderConfigurationError, match="PCFG_FILE_(UNSAFE|UNREADABLE)"):
        load_provider_configuration("provisioner")


def test_keyring_does_not_follow_final_symlink(settings, tmp_path, provider_mounts):
    provider_mounts("provisioner")
    target = tmp_path / "symlink"
    target.symlink_to(settings.SELAHCUE_PROVIDER_KEYRING_FILE)
    settings.SELAHCUE_PROVIDER_KEYRING_FILE = str(target)
    with pytest.raises(ProviderConfigurationError, match="PCFG_FILE_UNSAFE"):
        load_provider_configuration("provisioner")


def imported(org):
    mapping = import_existing_mapping(
        mapping_id=uuid4(), org_id=org.pk, identity=identity(), secret=SECRET,
        now=NOW, audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
    )
    return ProviderCredential.objects.get(pk=mapping.mapping_id)


def test_ciphertext_cannot_be_used_for_another_org_or_identity(provisioner_runtime, caplog):
    left, right = imported(church()), imported(church())
    for field in ["secret_version", "wrapping_key_id", "secret_nonce", "secret_ciphertext"]:
        setattr(right, field, getattr(left, field))
    assert open_secret(left) == SECRET
    # Independently vary each AAD component while leaving all the other inputs intact.
    original_org, original_key, original_pk = left.org_id, left.external_api_key_id, left.pk
    for field, changed, original in (
        ("org_id", right.org_id, original_org),
        ("external_api_key_id", right.external_api_key_id, original_key),
        ("pk", right.pk, original_pk),
    ):
        setattr(left, field, changed)
        with pytest.raises(ProviderCustodyError, match="PCUST_AUTHENTICATION_FAILED"):
            open_secret(left)
        setattr(left, field, original)
    with pytest.raises(ProviderCustodyError, match="PCUST_AUTHENTICATION_FAILED"):
        open_secret(right)
    assert "synthetic-reusable-secret" not in caplog.text + repr(SECRET) + repr(left)


@pytest.mark.django_db(transaction=True)
def test_bounded_rotation_keeps_historical_ciphertext_readable_under_rollback(provisioner_runtime):
    active, retired = imported(church()), imported(church())
    old_nonce = active.secret_nonce
    retire_mapping(mapping_id=retired.pk, expected_revision=retired.revision, now=NOW,
                   audit=audit(RegistryReason.RETIRE))
    provisioner_runtime(ring=keyring("new", new=True))
    result = rotate_wrapping_key_batch(after=None, limit=1, now=NOW, audit=audit(RegistryReason.REWRAP))
    assert (result.scanned, result.rewrapped, result.failures, result.exhausted) == (1, (active.pk,), (), False)
    tail = rotate_wrapping_key_batch(after=result.next_cursor, limit=1, now=NOW, audit=audit(RegistryReason.REWRAP))
    assert (tail.scanned, tail.rewrapped, tail.failures, tail.exhausted) == (1, (retired.pk,), (), True)
    active.refresh_from_db()
    retired.refresh_from_db()
    assert active.secret_nonce != old_nonce
    assert active.wrapping_key_id == retired.wrapping_key_id == "new"
    assert retired.state == "RETIRED"
    provisioner_runtime(ring=keyring("old", new=True))
    assert open_secret(active) == SECRET
    with pytest.raises(ProviderCustodyError, match="PCUST_STATE_INVALID"):
        open_secret(retired)


@pytest.mark.django_db(transaction=True)
def test_missing_historical_wrapping_key_leaves_old_envelope_untouched(provisioner_runtime):
    row = imported(church())
    old = bytes(row.secret_ciphertext)
    provisioner_runtime(ring=keyring("new", old=False, new=True))
    result = rotate_wrapping_key_batch(after=None, limit=100, now=NOW, audit=audit(RegistryReason.REWRAP))
    assert result.exhausted
    assert not result.rewrapped
    assert [(f.mapping_id, f.code.value) for f in result.failures] == [(row.pk, "PCUST_KEY_UNAVAILABLE")]
    row.refresh_from_db()
    assert bytes(row.secret_ciphertext) == old and row.wrapping_key_id == "old"
    provisioner_runtime()
    assert open_secret(row) == SECRET


@pytest.mark.django_db(transaction=True)
def test_rotation_refuses_an_outer_transaction_that_would_retain_all_row_locks(provisioner_runtime):
    with transaction.atomic(), pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        rotate_wrapping_key_batch(after=None, limit=1, now=NOW, audit=audit(RegistryReason.REWRAP))
