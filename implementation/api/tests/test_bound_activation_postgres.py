"""Transaction-level native operation binding and token deletion on PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

import pytest
from django.db import connection, connections, transaction
from django.test import Client
from django.utils import timezone

from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from test_bound_activation import KEY, body, post
from test_device_token_remint import _expire_tokens, _seed_license_key

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="requires PostgreSQL row locks"),
]


def parallel(*calls):
    ready = Barrier(len(calls))
    def run(call):
        try:
            ready.wait(timeout=10)
            return call()
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        jobs = [pool.submit(run, call) for call in calls]
        return [job.result(timeout=20) for job in jobs]


def activation(payload):
    return post(Client(), KEY, payload)


def test_concurrent_global_nonce_cannot_leave_an_orphan_seat(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    _, a = _seed_license_key(tag="global-a", device_limit=1)
    _, b = _seed_license_key(tag="global-b", device_limit=1)
    results = parallel(
        lambda: activation(body(license_key=a)),
        lambda: activation(body(license_key=b)),
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    assert Device.objects.count() == DeviceToken.objects.count() == DeviceActivationOperation.objects.count() == 1
    assert DeviceToken.objects.get().status == DeviceTokenStatus.ACTIVE
    assert AppLicenseKey.objects.filter(status=LicenseKeyStatus.ACTIVATED).count() == 1


def test_concurrent_duplicate_remint_creates_one_token_and_one_receipt(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    license_key, key = _seed_license_key(tag="parallel-remint", device_limit=1)
    expected = activation(body(license_key=key)).json()["device"]["device_public_id"]
    _expire_tokens(license_key, at=timezone.now() - timedelta(hours=1))
    request = body("2" * 32, expected=expected, license_key=key)
    responses = parallel(lambda: activation(request), lambda: activation(request))
    assert [response.status_code for response in responses] == [200, 200]
    replies = [response.json() for response in responses]
    assert {reply["operation_state"] for reply in replies} == {"completed", "replay"}
    assert sum(reply["activation_token"] is not None for reply in replies) == 1
    assert Device.objects.count() == 1
    assert DeviceActivationOperation.objects.count() == DeviceToken.objects.count() == 2
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 1


def test_postgres_rechecks_committed_licence_status_after_waiting(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    license_key, key = _seed_license_key(tag="lock-suspend", device_limit=1)
    initial = activation(body(license_key=key)).json()
    expected = initial["device"]["device_public_id"]
    _expire_tokens(license_key, at=timezone.now() - timedelta(hours=1))

    from test_concurrency_postgres import _licence_row_waiters
    from time import monotonic, sleep

    def recover():
        try:
            return activation(body("2" * 32, expected=expected, license_key=key))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = AppLicenseKey.objects.select_for_update().get(pk=license_key.pk)
            job = pool.submit(recover)
            deadline = monotonic() + 8
            waiters = 0
            while not waiters and monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                waiters = _licence_row_waiters()
                if not waiters:
                    sleep(0.01)
            assert waiters == 1
            locked.prior_status = locked.status
            locked.status = LicenseKeyStatus.SUSPENDED
            locked.save(update_fields=["status", "prior_status"])
        reply = job.result(timeout=10)
    assert reply.status_code == 403
    assert Device.objects.count() == DeviceToken.objects.count() == DeviceActivationOperation.objects.count() == 1


def test_concurrent_original_token_deletion_and_replay_never_remints(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    _, key = _seed_license_key(tag="parallel-delete", device_limit=1)
    request = body(license_key=key)
    initial = activation(request)
    token_pk = DeviceToken.objects.get().pk
    replay, _ = parallel(
        lambda: activation(request),
        lambda: DeviceToken.objects.filter(pk=token_pk).delete(),
    )
    assert initial.status_code == 200
    assert replay.status_code in {200, 409}
    assert replay.json().get("activation_token") is None
    assert not DeviceToken.objects.exists()
    receipt = DeviceActivationOperation.objects.get()
    assert receipt.result_token_id is None and receipt.issued_token_pk == token_pk
    assert activation(request).json()["error"]["code"] == "ACTIVATION_OPERATION_COMPLETED"
    assert Device.objects.count() == 1


def test_postgres_rechecks_revoked_device_under_target_row_lock(settings):
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    license_key, key = _seed_license_key(tag="lock-device", device_limit=1)
    expected = activation(body(license_key=key)).json()["device"]["device_public_id"]
    _expire_tokens(license_key, at=timezone.now() - timedelta(hours=1))

    from time import monotonic, sleep
    from selahcue_api.apps.devices.models import DeviceStatus

    def recover():
        try:
            return activation(body("2" * 32, expected=expected, license_key=key))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            device = Device.objects.select_for_update().get(device_public_id=expected)
            job = pool.submit(recover)
            deadline = monotonic() + 8
            waiting = False
            while not waiting and monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                    cursor.execute(
                        """SELECT EXISTS (
                            SELECT 1 FROM pg_stat_activity
                            WHERE datname = current_database() AND pid <> pg_backend_pid()
                            AND wait_event_type = 'Lock' AND query ILIKE %s
                        )""", [f"SELECT%{Device._meta.db_table}%"],
                    )
                    waiting = cursor.fetchone()[0]
                if not waiting:
                    sleep(0.01)
            assert waiting
            device.status = DeviceStatus.REVOKED
            device.save(update_fields=["status"])
        assert job.result(timeout=10).status_code == 403
    assert DeviceActivationOperation.objects.count() == DeviceToken.objects.count() == Device.objects.count() == 1


def test_fresh_recovery_receipt_survives_concurrent_token_delete(settings, monkeypatch):
    from threading import Event
    from time import monotonic, sleep
    from selahcue_api.apps.devices import bound_activation

    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    _, key = _seed_license_key(tag="fresh-recovery-delete", device_limit=1)
    initial = activation(body(license_key=key)).json()
    token_pk = DeviceToken.objects.get().pk
    locked, release = Event(), Event()
    original = bound_activation._existing_device_result

    def pause_after_token_lock(*args, **kwargs):
        result = original(*args, **kwargs)
        locked.set()
        assert release.wait(10), "release recovery transaction"
        return result

    monkeypatch.setattr(bound_activation, "_existing_device_result", pause_after_token_lock)

    def run(call):
        try:
            return call()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        recovering = pool.submit(run, lambda: activation(body(
            "9" * 32, expected=initial["device"]["device_public_id"], license_key=key,
        )))
        assert locked.wait(10)
        deleting = pool.submit(run, lambda: DeviceToken.objects.filter(pk=token_pk).delete())
        try:
            deadline = monotonic() + 8
            waiting = False
            while not waiting and monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")
                    cursor.execute(
                        """SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                        WHERE datname = current_database() AND wait_event_type = 'Lock'
                        AND query ILIKE %s)""", [f"DELETE%{DeviceToken._meta.db_table}%"],
                    )
                    waiting = cursor.fetchone()[0]
                if not waiting:
                    sleep(0.01)
            assert waiting, "token DELETE reached the held live-token lock"
        finally:
            release.set()
        response = recovering.result(timeout=10)
        deleting.result(timeout=10)
    assert response.status_code == 200
    assert response.json()["activation_token"] is None
    assert not DeviceToken.objects.exists()
    receipts = list(DeviceActivationOperation.objects.order_by("pk"))
    assert len(receipts) == 2
    assert all(row.result_token_id is None and row.issued_token_pk == token_pk for row in receipts)
    assert Device.objects.count() == 1


def test_receipt_fk_has_database_set_null_and_identity_protection():
    from django.db.models import DO_NOTHING, PROTECT

    assert DeviceActivationOperation._meta.get_field("result_token").remote_field.on_delete is DO_NOTHING
    for name in ["device", "license_key", "organization"]:
        assert DeviceActivationOperation._meta.get_field(name).remote_field.on_delete is PROTECT
    with connection.cursor() as cursor:
        cursor.execute("""SELECT c.confdeltype FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            WHERE c.conrelid = %s::regclass AND c.contype = 'f' AND a.attname = 'result_token_id'
        """, [DeviceActivationOperation._meta.db_table])
        assert cursor.fetchall() == [("n",)]
