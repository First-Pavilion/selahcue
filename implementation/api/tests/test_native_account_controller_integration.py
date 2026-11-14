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

from test_device_token_remint import TEST_SEED_B64, _expire_tokens, _renew, _seed_license_key
from test_native_account_surface import seed_user
from selahcue_api.apps.accounts.models import CustomerSession
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

OPERATOR_TEST = "account::tests::controller::django_g1_real_api"
RUST_BIN = os.environ.get("SELAHCUE_G1_OPERATOR_TEST_BIN")


@pytest.mark.skipif(not RUST_BIN, reason="requires staged Rust operator integration test binary")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("scenario", ["expired", "cascade", "missing", "missing-local", "live"])
def test_native_account_controller_against_local_platform_api(scenario, settings, live_server):
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    cache.clear()
    now = timezone.now().replace(microsecond=0)
    key, enrollment_key = _seed_license_key(tag=scenario, device_limit=1, starts_at=now - timedelta(days=40))
    assert key.device_limit == 1
    email = f"admin-{scenario}@fixture.test"
    password = "Synthetic-loopback-fixture-only-548!"
    if scenario == "cascade":
        seed_user(key.customer, email=email, password=password)

    env = os.environ.copy()
    env["SELAHCUE_G1_FIXTURE_URL"] = live_server.url
    env["SELAHCUE_G1_SCENARIO"] = scenario
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
            if scenario == "expired":
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
            assert Device.objects.get(pk=initial.pk).device_public_id == initial.device_public_id
            assert Device.objects.get(pk=initial.pk).device_fingerprint == initial.device_fingerprint
            live = DeviceToken.objects.get(device=initial, status=DeviceTokenStatus.ACTIVE)
            assert (live.pk == original.pk) == (scenario == "live")
            assert not CustomerSession.objects.filter(revoked_at__isnull=True).exists()
        finally:
            if child.poll() is None:
                child.kill()
            reader.join(timeout=2)
