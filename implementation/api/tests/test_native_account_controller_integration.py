"""Joint G1 wire test with the operator controller and the real local Platform API.

Build the pinned operator tests first. Set SELAHCUE_G1_OPERATOR_TEST_BIN to the resulting
operator unit-test executable, then run this file with the normal API test settings.
No production tenant, network destination, signing material or OS keychain is needed.
"""

import json
import os
import queue
import subprocess
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.cache import cache
from django.utils import timezone

from test_bound_activation import another_license
from test_device_token_remint import TEST_SEED_B64, _expire_tokens, _renew, _seed_license_key
from test_free_license_lifecycle import self_service_org
from test_native_account_surface import seed_user
from selahcue_api.apps.accounts.models import CustomerSession
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle, LicenseKeyStatus

OPERATOR_TEST = "account::tests::controller::django_g1_real_api"
RUST_BIN = os.environ.get("SELAHCUE_G1_OPERATOR_TEST_BIN")


@pytest.mark.skipif(not RUST_BIN, reason="requires staged Rust operator integration test binary")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("scenario", [
    "expired", "cascade", "missing", "missing-local", "live", "initial-restart",
    "lost-initial", "managed-free-lost-initial", "race-loss", "race-replay",
])
def test_native_account_controller_against_local_platform_api(scenario, settings, live_server):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    cache.clear()
    now = timezone.now().replace(microsecond=0)
    starts_with_free = scenario == "managed-free-lost-initial"
    if starts_with_free:
        customer = self_service_org()
        enrollment_key = None
    else:
        key, enrollment_key = _seed_license_key(tag=scenario, device_limit=1, starts_at=now - timedelta(days=40))
        assert key.device_limit == 1
        customer = key.customer
    email = f"admin-{scenario}@fixture.test"
    password = "Synthetic-loopback-fixture-only-548!"
    if starts_with_free or scenario in {"cascade", "initial-restart", "lost-initial"}:
        seed_user(customer, email=email, password=password)

    env = os.environ.copy()
    env["SELAHCUE_G1_FIXTURE_URL"] = live_server.url
    env["SELAHCUE_G1_SCENARIO"] = "lost-initial" if starts_with_free else scenario
    env["NO_PROXY"] = "127.0.0.1,localhost"
    with subprocess.Popen(
        [str(Path(RUST_BIN).resolve(strict=True)), OPERATOR_TEST, "--exact", "--ignored", "--nocapture"],
        env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    ) as child:
        output = queue.Queue()

        def collect():
            for line in child.stdout:
                output.put(line)
            output.put(None)

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        lines = []

        def receive(marker):
            while True:
                line = output.get(timeout=30)
                assert line is not None, "".join(lines)
                lines.append(line)
                if line.strip() == f"G1 {marker}":
                    return

        def advance():
            child.stdin.write("continue\n")
            child.stdin.flush()

        try:
            child.stdin.write(json.dumps({"email": email, "password": password, "enrollment_key": enrollment_key}) + "\n")
            child.stdin.flush()
            if scenario == "initial-restart":
                receive("initial unsaved")
                original = Device.objects.get(license_key=key)
                receipt = DeviceActivationOperation.objects.get()
                assert receipt.expected_device_public_id is None and receipt.mode == "initial"
                competitor, _ = another_license(key, "native-initial-competitor")
                advance()
                receive("initial replay")
                assert child.wait(timeout=30) == 0
                assert not Device.objects.filter(license_key=competitor).exists()
                assert DeviceToken.objects.filter(device=original).count() == 1
                assert DeviceActivationOperation.objects.count() == 1
                # A replay with no secret cannot retire a possibly in-flight
                # original response; restart retains the identical retry authority.
                assert CustomerSession.objects.filter(revoked_at__isnull=True).count() == 1
                return
            if starts_with_free or scenario == "lost-initial":
                receive("initial response lost")
                receipt = DeviceActivationOperation.objects.get()
                origin = receipt.device
                receipt.result_token.delete()
                competitor = None
                if starts_with_free:
                    key = receipt.license_key
                    assert FreeLicenseLifecycle.objects.get(customer=customer).license_key_id == key.pk
                    assert key.expires_at - key.starts_at == timedelta(days=365)
                    expired = now - timedelta(days=1)
                    AppLicenseKey.objects.filter(pk=key.pk).update(
                        starts_at=expired - timedelta(days=365), expires_at=expired,
                        status=LicenseKeyStatus.EXPIRED,
                    )
                else:
                    competitor, _ = another_license(key, "native-lost-competitor")
                advance()
                receive("completed receipt learned")
                if starts_with_free:
                    key.refresh_from_db()
                    assert key.expires_at == expired
                    assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()
                assert not DeviceToken.objects.exists()
                assert not AuditEvent.objects.filter(action="device_token.reminted").exists()
                assert DeviceActivationOperation.objects.count() == 1
                advance()
                receive("lost-initial recovered")
                assert child.wait(timeout=30) == 0
                if competitor is not None:
                    assert not Device.objects.filter(license_key=competitor).exists()
                if starts_with_free:
                    key.refresh_from_db()
                    assert key.status == LicenseKeyStatus.ACTIVATED
                    assert key.expires_at > now + timedelta(days=364)
                    assert AuditEvent.objects.filter(action="license_key.free_renewed").count() == 1
                    assert DeviceActivationOperation.objects.filter(license_key=key, device=origin).count() == 2
                assert DeviceToken.objects.filter(device=origin).count() == Device.objects.count() == 1
                old = DeviceActivationOperation.objects.get(pk=receipt.pk)
                assert old.result_token_id is None and old.issued_token_pk == receipt.issued_token_pk
                assert DeviceActivationOperation.objects.count() == 2
                assert AuditEvent.objects.filter(action="device_token.reminted").count() == 1
                return
            receive("activated")
            initial = Device.objects.get(license_key=key)
            original = DeviceToken.objects.get(device=initial)
            if scenario == "missing-local":
                advance()
                receive("recovery required")
                assert child.wait(timeout=30) == 0
                assert Device.objects.filter(license_key=key).count() == 1
                assert DeviceToken.objects.get(device=initial).pk == original.pk
                assert not AuditEvent.objects.filter(action="device_token.reminted").exists()
                return

            expired = now - timedelta(days=1)
            AppLicenseKey.objects.filter(pk=key.pk).update(expires_at=expired, status=LicenseKeyStatus.EXPIRED)
            if scenario in {"expired", "race-loss", "race-replay"}:
                _expire_tokens(key, at=expired)
            elif scenario == "cascade":
                assert cascade_license_revocations() == 1
                assert DeviceToken.objects.get(pk=original.pk).status == DeviceTokenStatus.REVOKED
            elif scenario == "missing":
                DeviceToken.objects.filter(pk=original.pk).delete()
            else:
                assert DeviceToken.objects.get(pk=original.pk).expires_at > timezone.now()

            advance()
            receive("lapsed")
            # The currently active licence points at the same device after renewal.
            _renew(key, expires_at=now + timedelta(days=90))
            competitor = None
            if scenario == "cascade":
                competitor, _ = another_license(key, "native-admin-competitor")
            advance()
            if scenario != "live":
                receive("dead_token")
                assert not AuditEvent.objects.filter(action="device_token.reminted").exists()
                assert DeviceToken.objects.filter(device=initial).count() == (scenario != "missing")
                advance()
                receive("unsaved")
                assert AuditEvent.objects.filter(action="device_token.reminted").count() == 1
                if scenario == "cascade":
                    assert CustomerSession.objects.filter(revoked_at__isnull=True).count() == 1
                advance()
            receive("recovered")
            assert child.wait(timeout=30) == 0
            assert Device.objects.filter(license_key=key).count() == 1
            if competitor is not None:
                assert not Device.objects.filter(license_key=competitor).exists()
            assert Device.objects.get(pk=initial.pk).device_public_id == initial.device_public_id
            assert Device.objects.get(pk=initial.pk).device_fingerprint == initial.device_fingerprint
            live = DeviceToken.objects.get(device=initial, status=DeviceTokenStatus.ACTIVE)
            assert (live.pk == original.pk) == (scenario == "live")
            assert not CustomerSession.objects.filter(revoked_at__isnull=True).exists()
        finally:
            if child.poll() is None:
                child.kill()
            reader.join(timeout=2)
