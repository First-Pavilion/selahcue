"""The database action survives migration forward/reverse on PostgreSQL and SQLite."""
import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from selahcue_api.apps.devices.models import DeviceActivationOperation, DeviceToken
from test_bound_activation import KEY, body, post
from test_device_token_remint import _seed_license_key

pytestmark = pytest.mark.django_db(transaction=True)
APP = "selahcue_devices"
BEFORE = (APP, "0003_deviceactivationoperation")
AFTER = (APP, "0004_receipt_database_set_null")


def action():
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_key_list(selahcue_devices_deviceactivationoperation)")
            return next(row[6] for row in cursor.fetchall() if row[3] == "result_token_id")
        if connection.vendor == "postgresql":
            cursor.execute("""SELECT c.confdeltype FROM pg_constraint c
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                WHERE c.conrelid = %s::regclass AND c.contype = 'f' AND a.attname = 'result_token_id'
            """, [DeviceActivationOperation._meta.db_table])
            return {"a": "NO ACTION", "n": "SET NULL"}[cursor.fetchone()[0]]
        pytest.skip("constraint inspection targets supported PostgreSQL and SQLite")


def test_receipt_migration_reversal_and_reapply_preserve_rows_and_database_action(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)
    _, key = _seed_license_key(tag="receipt-migration", device_limit=1)
    assert post(Client(), KEY, body(license_key=key)).status_code == 200
    before = list(DeviceActivationOperation.objects.values())
    token_pk = DeviceToken.objects.get().pk
    assert action() == "SET NULL"
    executor = MigrationExecutor(connection)
    frontier = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([BEFORE])
        assert action() == "NO ACTION"
        assert list(DeviceActivationOperation.objects.values()) == before
        MigrationExecutor(connection).migrate([AFTER])
        assert action() == "SET NULL"
        assert list(DeviceActivationOperation.objects.values()) == before
    finally:
        MigrationExecutor(connection).migrate(frontier)
    assert action() == "SET NULL"
    assert list(DeviceActivationOperation.objects.values()) == before
    DeviceToken.objects.get(pk=token_pk).delete()
    receipt = DeviceActivationOperation.objects.get()
    assert receipt.result_token_id is None
    assert receipt.issued_token_pk == token_pk
