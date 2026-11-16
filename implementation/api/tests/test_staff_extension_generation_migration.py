"""Generation migration contracts against the historical app state."""

import pytest
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from test_bound_activation import KEY, body, post
from test_native_account_surface import seed_license, seed_org
from test_license_revoke_extend import _seed_key

pytestmark = pytest.mark.django_db(transaction=True)
LICENSES = "selahcue_license_keys"
DEVICES = "selahcue_devices"
AUDIT = "selahcue_audit"
BEFORE = [
    (LICENSES, "0004_staff_extension_generation"),
    (DEVICES, "0004_receipt_database_set_null"),
    (AUDIT, "0001_initial"),
]


@pytest.fixture
def historical_generation_schema():
    executor = MigrationExecutor(connection)
    frontier = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(BEFORE)
        yield executor.loader.project_state(BEFORE).apps, frontier
    finally:
        MigrationExecutor(connection).migrate(frontier)


def _extension_event(target_id, **overrides):
    return {
        "actor_kind": "staff",
        "actor_id": "historical-operator",
        "action": "license_key.extended",
        "target_type": "app_license_key",
        "target_id": str(target_id),
        "request_id": "historical-extension",
        "result": "SUCCESS",
        **overrides,
    }


def test_generation_migration_preserves_expiry_audits_receipts(client):
    cache.clear()
    key, full_key = _seed_key("historical-extension")
    assert post(client, KEY, body(license_key=full_key)).status_code == 200
    executor = MigrationExecutor(connection)
    frontier = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(BEFORE)
        historical = executor.loader.project_state(BEFORE).apps
        license_key = historical.get_model(LICENSES, "AppLicenseKey")
        token = historical.get_model(DEVICES, "DeviceToken")
        receipt = historical.get_model(DEVICES, "DeviceActivationOperation")
        audit = historical.get_model(AUDIT, "AuditEvent")
        audit.objects.create(**_extension_event(key.pk))
        key_before = license_key.objects.values().get(pk=key.pk)
        token_before = token.objects.values().get(device__license_key_id=key.pk)
        receipt_before = receipt.objects.values().get(license_key_id=key.pk)
        audit_before = list(audit.objects.order_by("pk").values())
        assert key_before["staff_extension_generation"] == 0
        assert "staff_extension_generation" not in token_before

        migrated = MigrationExecutor(connection).migrate(frontier).apps
        assert migrated.get_model(LICENSES, "AppLicenseKey").objects.values().get(pk=key.pk) == {
            **key_before, "staff_extension_generation": 1,
        }
        assert migrated.get_model(DEVICES, "DeviceToken").objects.values().get(
            pk=token_before["id"],
        ) == {**token_before, "staff_extension_generation": 0}
        assert migrated.get_model(DEVICES, "DeviceActivationOperation").objects.values().get(
            license_key_id=key.pk,
        ) == receipt_before
        assert list(migrated.get_model(AUDIT, "AuditEvent").objects.order_by("pk").values()) == audit_before
    finally:
        MigrationExecutor(connection).migrate(frontier)


def test_generation_backfill_ignores_invalid_target_and_never_resets_nonzero(historical_generation_schema):
    historical, frontier = historical_generation_schema
    key = historical.get_model(LICENSES, "AppLicenseKey")
    audit = historical.get_model(AUDIT, "AuditEvent")
    # This fixture state already has the licence generation column.
    old = key.objects.get(pk=seed_license(seed_org(tag="historical-valid")).pk)
    nonzero = key.objects.get(pk=seed_license(seed_org(tag="historical-nonzero")).pk)
    untouched = key.objects.get(pk=seed_license(seed_org(tag="historical-invalid")).pk)
    key.objects.filter(pk=nonzero.pk).update(staff_extension_generation=9)

    invalid_targets = [
        "", "not-a-number", "-1", "0", f"0{untouched.pk}", f"+{untouched.pk}", f" {untouched.pk}",
        "٤", "9" * 90, str(2**63), str(2**63 - 1),
    ]
    # Place valid records past the first page to prove bounded iteration continues.
    audit.objects.bulk_create([audit(**_extension_event("invalid")) for _ in range(500)])
    audit.objects.bulk_create([audit(**_extension_event(target)) for target in invalid_targets])
    audit.objects.bulk_create([
        audit(**_extension_event(old.pk)),
        audit(**_extension_event(old.pk)),
        audit(**_extension_event(nonzero.pk)),
        audit(**_extension_event(untouched.pk, result="DENIED")),
        audit(**_extension_event(untouched.pk, target_type="other_resource")),
        audit(**_extension_event(untouched.pk, action="license_key.free_renewed")),
    ])
    before = list(audit.objects.order_by("pk").values())

    migrated = MigrationExecutor(connection).migrate(frontier).apps
    assert dict(migrated.get_model(LICENSES, "AppLicenseKey").objects.values_list(
        "pk", "staff_extension_generation",
    )) == {old.pk: 1, nonzero.pk: 9, untouched.pk: 0}
    assert list(migrated.get_model(AUDIT, "AuditEvent").objects.order_by("pk").values()) == before
