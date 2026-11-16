"""Authoritative PostgreSQL gates. SQLite deliberately cannot prove these locks/guards.

Task7 Notes admission/publication races require its eventual real consumers and are
not replaced here with invented models or ledger-only acceptance.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic, sleep

import pytest
from django.core.cache import cache
from django.db import DatabaseError, connection, connections, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext

from provider_helpers import cold_provider_cache, provider_mounts  # noqa: F401
from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices import deactivation
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle
from selahcue_api.apps.providers.models import SttMintAttempt
from selahcue_api.apps.usage.models import UsageReservation, UsageWeek
from selahcue_api.apps.usage.services import reserve_notes_job
from selahcue_api.graphql.errors import ErrorCode
from test_account_overview import assert_code, deactivate, principal, token
from test_bound_activation import KEY, body, post
from test_bound_activation_postgres import parallel
from test_cloud_grant_postgres import command, deps, granted, live_org, submit  # noqa: F401
from test_device_token_remint import _activate, _refresh, _seed_license_key
from test_effective_org_plan import NOW, context, device, licence
from test_usage_weeks import DIGEST

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='requires real PostgreSQL row locks and installed guards'),
]


@pytest.fixture(autouse=True)
def isolated_budgets_and_signing(settings):
    cache.clear()
    settings.ENTITLEMENT_SIGNING_KEY = base64.b64encode(bytes(range(32))).decode('ascii')
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    settings.SELAHCUE_THROTTLE_ACTIVATION = (100, 60)
    settings.SELAHCUE_THROTTLE_REFRESH = (100, 60)


def wait_for_block(pid):
    deadline = monotonic()+3
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute('SELECT cardinality(pg_blocking_pids(%s))', [pid])
            if cursor.fetchone()[0]:
                return
        sleep(0.005)
    pytest.fail('Owning worker did not encounter a real PostgreSQL lock wait')


def worker_call(call, pids=None):
    try:
        if pids is not None:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()')
                pids.put(cursor.fetchone()[0])
        return call()
    finally:
        connections.close_all()


def test_double_deactivation_has_one_committed_transition_and_service_audit():
    user, actor = principal()
    install = device(licence(user.customer))
    token(install)
    result = parallel(
        lambda: deactivate(actor, install.device_public_id),
        lambda: deactivate(actor, install.device_public_id, 'second-correlation-001'),
    )
    assert sorted(row.already_inactive for row in result) == [False, True]
    assert AuditEvent.objects.filter(action='device.deactivated').count() == 1
    assert DeviceToken.objects.get(device=install).status == 'REVOKED'


def test_real_lock_order_final_clock_and_ordered_nonrevoked_tokens(monkeypatch):
    user, actor = principal()
    install = device(licence(user.customer))
    token(install, expired=True)
    token(install)
    clock_reads = []
    with CaptureQueriesContext(connection) as queries:
        def final_clock():
            clock_reads.append(tuple(q['sql'] for q in queries))
            return NOW
        monkeypatch.setattr(deactivation.timezone, 'now', final_clock)
        assert not deactivate(actor, install.device_public_id).already_inactive
    locks = [sql for sql in clock_reads[0] if 'FOR ' in sql]
    assert len(locks) == 5
    assert 'selahcue_accounts_customerorg' in locks[0] and 'FOR NO KEY UPDATE' in locks[0]
    assert 'selahcue_accounts_customeruser' in locks[1]
    assert 'selahcue_license_keys_applicensekey' in locks[2]
    assert 'selahcue_devices_device"' in locks[3]
    assert 'selahcue_devices_devicetoken' in locks[4] and 'ORDER BY' in locks[4] and ' ASC' in locks[4]
    assert all('FOR UPDATE' in sql for sql in locks[1:])
    assert Device.objects.get(pk=install.pk).updated_at == NOW
    assert set(DeviceToken.objects.filter(device=install).values_list('updated_at', flat=True)) == {NOW}


def test_audit_failure_rolls_back_every_token_status_and_timestamp(monkeypatch):
    user, actor = principal()
    install = device(licence(user.customer))
    token(install)
    token(install, expired=True)
    before_device = Device.objects.get(pk=install.pk).__dict__.copy()
    before_tokens = list(DeviceToken.objects.filter(device=install).order_by('pk').values())
    def fail(*args, **kwargs):
        raise DatabaseError('synthetic audit failure')
    monkeypatch.setattr(deactivation, 'record_audit_event', fail)
    assert_code(lambda: deactivate(actor, install.device_public_id), ErrorCode.INTERNAL)
    current = Device.objects.get(pk=install.pk)
    assert current.status == before_device['status'] and current.updated_at == before_device['updated_at']
    assert list(DeviceToken.objects.filter(device=install).order_by('pk').values()) == before_tokens
    assert not AuditEvent.objects.filter(action='device.deactivated').exists()


def test_deactivation_preserves_usage_holds_licence_and_other_devices():
    from uuid import uuid4
    user, actor = principal()
    key = licence(user.customer)
    install, other = device(key), device(key)
    token(install)
    token(other)
    reserve_notes_job(context(install, 'notes'), uuid4(), DIGEST, NOW)
    before = (list(UsageReservation.objects.values()), list(UsageWeek.objects.values()),
              AppLicenseKey.objects.values().get(pk=key.pk), Device.objects.values().get(pk=other.pk),
              list(DeviceToken.objects.filter(device=other).values()))
    deactivate(actor, install.device_public_id)
    after = (list(UsageReservation.objects.values()), list(UsageWeek.objects.values()),
             AppLicenseKey.objects.values().get(pk=key.pk), Device.objects.values().get(pk=other.pk),
             list(DeviceToken.objects.filter(device=other).values()))
    assert after == before


def test_bound_old_receipt_and_legacy_fingerprint_stay_terminal_freed_slot_works():
    key, enrollment = _seed_license_key(tag='account-terminal', device_limit=1)
    _, actor = principal(key.customer)
    client = Client()
    initial = post(client, KEY, body(license_key=enrollment))
    assert initial.status_code == 200, initial.content
    public_id = initial.json()['device']['device_public_id']
    receipt_before = list(DeviceActivationOperation.objects.values())
    deactivate(actor, public_id)
    for payload in (body(license_key=enrollment),
                    body('2'*32, expected=public_id, license_key=enrollment),
                    body('3'*32, license_key=enrollment)):
        denied = post(client, KEY, payload)
        assert denied.status_code == 403, denied.content
    assert _activate(client, license_key=enrollment, fingerprint='native-booth').status_code == 403
    assert _refresh(client, initial.json()['activation_token']).status_code == 401
    assert list(DeviceActivationOperation.objects.values()) == receipt_before
    replacement = post(client, KEY, body('4'*32, license_key=enrollment, device_fingerprint='replacement-install'))
    assert replacement.status_code == 200, replacement.content
    assert replacement.json()['device']['device_public_id'] != public_id
    assert Device.objects.filter(license_key=key, status='ACTIVE').count() == 1
    assert DeviceToken.objects.filter(device__device_public_id=public_id, status='ACTIVE').count() == 0


def test_managed_refresh_waits_then_rechecks_deactivated_device():
    key, enrollment = _seed_license_key(tag='account-refresh-race', device_limit=1)
    user, actor = principal(key.customer)
    initial = post(Client(), KEY, body(license_key=enrollment))
    assert initial.status_code == 200, initial.content
    FreeLicenseLifecycle.objects.create(customer=user.customer, license_key=key, policy_version=1)
    pids = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            CustomerOrg.objects.select_for_update(no_key=True).get(pk=user.customer_id)
            job = pool.submit(worker_call, lambda: _refresh(Client(), initial.json()['activation_token']), pids)
            wait_for_block(pids.get(timeout=3))
            deactivate(actor, initial.json()['device']['device_public_id'])
        result = job.result(timeout=10)
    assert result.status_code == 401, result.content
    assert DeviceToken.objects.filter(status='ACTIVE').count() == 0
    assert not AuditEvent.objects.filter(action='license_key.free_renewed').exists()


def test_legacy_activation_serializes_on_exact_license_after_revocation():
    key, enrollment = _seed_license_key(tag='account-activation-race', device_limit=1)
    user, actor = principal(key.customer)
    first = _activate(Client(), license_key=enrollment, fingerprint='old-install')
    assert first.status_code == 200, first.content
    install = Device.objects.get(license_key=key)
    pids = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            # Deactivation retains its org/licence locks until this surrounding commit.
            deactivate(actor, install.device_public_id)
            job = pool.submit(worker_call, lambda: _activate(
                Client(), license_key=enrollment, fingerprint='replacement-install', idem='replacement-race-001',
            ), pids)
            wait_for_block(pids.get(timeout=3))
        result = job.result(timeout=10)
    assert result.status_code == 200, result.content
    assert Device.objects.filter(license_key=key, status='ACTIVE').count() == 1
    assert Device.objects.get(pk=install.pk).status == 'REVOKED'


def test_actual_task5_final_mint_recheck_discards_after_real_deactivation(live_org):
    org, _, original_token, _, _ = live_org()
    _, actor = principal(org)
    # This must run against the installed Task5 write guard, never a fake model.
    with connection.cursor() as cursor:
        cursor.execute("SELECT tgenabled FROM pg_trigger WHERE tgname = 'stt_mint_attempt_guard' AND NOT tgisinternal")
        assert cursor.fetchall() == [('O',)]
    mint_entered, release_mint = Event(), Event()
    request = command()
    def gated_mint(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        mint_entered.set()
        assert release_mint.wait(timeout=10)
        return receipt
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(worker_call, lambda: submit(original_token, request, deps(gated_mint)))
        try:
            assert mint_entered.wait(timeout=10)
            deactivate(actor, original_token.device.device_public_id)
        finally:
            release_mint.set()
        assert job.result(timeout=10) == 'UNAUTHENTICATED'
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == 'DISCARDED'
    assert attempt.audit_event.reason == 'UNAUTHENTICATED'
    assert attempt.reservation.state == 'RESERVED'
    assert DeviceToken.objects.get(pk=original_token.pk).status == 'REVOKED'
    assert AuditEvent.objects.filter(action='device.deactivated').count() == 1
