"""Joint G1 wire test with the operator controller and the real local Platform API.

Build the pinned operator tests first. Set SELAHCUE_G1_OPERATOR_TEST_BIN to the resulting
operator unit-test executable, then run this file with the normal API test settings.
No production tenant, network destination, signing material or OS keychain is needed.
"""

import json
import os
import queue
import re
import runpy
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.cache import cache
from django.utils import timezone

from test_bound_activation import another_license
from test_device_token_remint import TEST_SEED_B64, _expire_tokens, _renew, _seed_license_key
from test_free_license_lifecycle import self_service_org
from test_license_revoke_extend import _extend
from test_native_account_surface import seed_user
from selahcue_api.apps.accounts.models import CustomerSession
from selahcue_api.apps.audit.models import AuditEvent, AuditResult
from selahcue_api.apps.catalogue.models import LicensePlanAssignment
from selahcue_api.apps.devices.models import Device, DeviceActivationOperation, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys.models import AppLicenseKey, FreeLicenseLifecycle, LicenseKeyStatus

OPERATOR_TEST = "account::tests::controller::django_g1_real_api"
RUST_BIN = os.environ.get("SELAHCUE_G1_OPERATOR_TEST_BIN")
REQUIRE_G1 = os.environ.get("SELAHCUE_G1_REQUIRE") == "1"


def test_required_g1_missing_binary_fails(tmp_path):
    """Required coverage may never turn an absent executable into a successful skip."""
    module = Path(__file__).resolve()
    joint_test = "test_native_account_controller_against_local_platform_api"
    junit = tmp_path / "missing-binary.xml"
    # Select only the joint cases (never this probe). Even if a case reaches its
    # fixtures, it gets temporary SQLite and process-local cache and broker,
    # independently of the parent runner's PostgreSQL/Redis configuration.
    test_db = tmp_path / "test-child.sqlite3"
    (tmp_path / "g1_missing_binary_settings.py").write_text(
        "from selahcue_api.settings import *\n"
        f"DATABASES['default']['TEST'] = {{'NAME': {str(test_db)!r}}}\n",
        encoding="utf-8",
    )
    env = {
        name: os.environ[name]
        for name in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR")
        if name in os.environ
    }
    env.update(
        DJANGO_SETTINGS_MODULE="g1_missing_binary_settings",
        PYTHONPATH=str(tmp_path),
        SQL_ENGINE="django.db.backends.sqlite3",
        SQL_DATABASE=str(tmp_path / "child.sqlite3"),
        CELERY_BROKER_URL="memory://",
        CELERY_RESULT_BACKEND="cache+memory://",
        SELAHCUE_G1_REQUIRE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-p", "pytest_django.plugin",
            "-p", "no:cacheprovider", "-q", "-rs",
            "--junitxml", str(junit), f"tests/{module.name}::{joint_test}",
        ],
        cwd=module.parents[1], env=env, capture_output=True, text=True, timeout=90,
    )
    diagnostics = f"Required G1 child exited {result.returncode}:\n{result.stdout}{result.stderr}"
    assert result.returncode == pytest.ExitCode.TESTS_FAILED, diagnostics
    cases = ET.parse(junit).findall(".//testcase")
    names = {case.attrib["name"] for case in cases}
    expected = {
        "expired", "cascade", "missing", "missing-local", "live", "initial-restart",
        "lost-initial", "managed-free-lost-initial", "race-loss", "race-replay",
        "staff-extension", "staff-extension-response-lost", "staff-extension-store-failed",
        "staff-extension-restart", "staff-extension-managed-free",
    }
    assert {f"{joint_test}[{scenario}]" for scenario in expected} <= names, diagnostics
    assert len(cases) == len(names), diagnostics
    for case in cases:
        assert case.find("skipped") is None and case.find("error") is None, diagnostics
        failure = case.find("failure")
        assert failure is not None, diagnostics
        assert "SELAHCUE_G1_OPERATOR_TEST_BIN" in failure.get("message", ""), diagnostics


def test_required_g1_workflow_keeps_api_reachable_and_requires_same_source_artifact():
    """A job failure or skip must not hide ordinary API tests or bypass the joint proof."""
    repo = Path(__file__).resolve().parents[3]
    # Reuse the stdlib workflow inspection behind the API parity self-test.
    # The contract test runs in pytest, after that self-test and system checks.
    inspection = runpy.run_path(str(repo / "scripts" / "check_api_gate.py"))
    workflow = inspection["CI_YML"].read_text()
    job_lines = inspection["workflow_job_lines"]
    api = "\n".join(job_lines(workflow, "api"))
    operator = "\n".join(job_lines(workflow, "operator"))
    changes = "\n".join(job_lines(workflow, "changes"))

    needs = re.search(r"^    needs:.*$", api, re.MULTILINE)
    assert needs is not None and {"changes", "operator"} <= set(re.findall(r"\w+", needs[0])), (
        "The API job must depend on operator for the required same-run G1 artifact"
    )

    def condition(block, indent):
        value = next((line.strip()[3:].strip() for line in block.splitlines()
                      if line.startswith(" " * indent + "if:")), "")
        return value.removeprefix("${{").removesuffix("}}").strip()

    joint = "needs.changes.outputs.native_account_joint == 'true'"
    api_area = f"needs.changes.outputs.api == 'true' || {joint}"
    assert condition(api, 4) == f"always() && !cancelled() && ({api_area})", (
        "The API job must remain reachable when the operator dependency fails or is skipped"
    )
    assert condition(operator, 4) == f"needs.changes.outputs.desktop == 'true' || {joint}"
    assert "steps.filter.outputs.native_account_joint" in changes

    def steps(job_text):
        return re.split(r"^      - ", job_text, flags=re.MULTILINE)[1:]

    stage = next((step for step in steps(operator) if "g1_operator_artifact.py stage" in step), "")
    assert "git rev-parse HEAD" in stage and "--source-sha" in stage

    def joint_artifact_steps(job_text, action):
        artifact_name = "g1-operator-linux-${{ github.sha }}"
        return [step for step in steps(job_text)
                if f"uses: actions/{action}-artifact@" in step
                and f"          name: {artifact_name}" in step.splitlines()]

    uploads = joint_artifact_steps(operator, "upload")
    assert len(uploads) == 1 and "runner.os == 'Linux'" in condition(uploads[0], 8)
    downloads = joint_artifact_steps(api, "download")
    assert len(downloads) == 1 and joint in condition(downloads[0], 8)
    assert not re.search(r"^\s*(run-id|repository|github-token):", downloads[0], re.MULTILINE)
    verify = next((step for step in steps(api) if "g1_operator_artifact.py verify " in step), "")
    assert "git rev-parse HEAD" in verify and "--expected-source-sha" in verify

    errors = inspection["joint_test_step_errors"](workflow)
    assert not errors, "\n".join(errors)


def _staff_extension_case(scenario, customer, receive, advance):
    key = AppLicenseKey.objects.get(customer=customer)
    device = Device.objects.get(license_key=key)
    original = DeviceToken.objects.get(device=device)
    receipt = DeviceActivationOperation.objects.values().get(device=device)
    assert receipt["issued_token_pk"] == receipt["result_token_id"] == original.pk
    assert original.status == DeviceTokenStatus.ACTIVE and original.expires_at > timezone.now()
    assert original.staff_extension_generation == key.staff_extension_generation
    managed = scenario == "staff-extension-managed-free"
    if managed:
        marker = FreeLicenseLifecycle.objects.values().get(customer=customer, license_key=key)
        grant = LicensePlanAssignment.objects.values().get(license_key=key, plan__is_fallback=True)
        assert marker["renewal_enabled"]
        assert AuditEvent.objects.filter(
            action="customer_org.free_activated", target_id=str(customer.pk), result=AuditResult.SUCCESS,
        ).count() == 1

    expiry = key.expires_at + timedelta(days=30)
    result = _extend(key, expiry, idem=f"g1-{scenario}")
    key.refresh_from_db()
    assert result.changed and key.expires_at == expiry
    assert key.staff_extension_generation == original.staff_extension_generation + 1
    extension = AuditEvent.objects.get(
        action="license_key.extended", target_id=str(key.pk), result=AuditResult.SUCCESS,
    )
    assert result.audit_event.pk == extension.pk
    assert (extension.actor_kind, extension.actor_id, extension.request_id) == ("staff", "staff_ops_7", f"g1-{scenario}")
    assert extension.before["staff_extension_generation"] == original.staff_extension_generation
    assert extension.after["staff_extension_generation"] == key.staff_extension_generation
    original.refresh_from_db()
    assert original.status == DeviceTokenStatus.ACTIVE
    assert original.staff_extension_generation == key.staff_extension_generation - 1

    def assert_rotated():
        original.refresh_from_db()
        assert original.status == DeviceTokenStatus.REVOKED
        tokens = DeviceToken.objects.filter(device=device)
        assert tokens.count() == 2
        replacement = tokens.get(status=DeviceTokenStatus.ACTIVE)
        assert replacement.pk != original.pk
        assert replacement.expires_at == expiry
        assert replacement.staff_extension_generation == key.staff_extension_generation
        assert Device.objects.filter(customer=customer).count() == 1
        persisted = Device.objects.get(pk=device.pk)
        assert persisted.device_public_id == device.device_public_id
        assert persisted.device_fingerprint == device.device_fingerprint
        assert persisted.license_key_id == key.pk
        assert DeviceActivationOperation.objects.values().get(pk=receipt["id"]) == receipt
        assert AuditEvent.objects.filter(
            action="device_token.reminted", after__device_public_id=device.device_public_id,
            result=AuditResult.SUCCESS,
        ).count() == 1

    advance()
    receive("staff refresh returned")
    # Record database evidence even when the native behavioral assertion below
    # fails on a status-only legacy response. Keep identifiers and secrets out
    # of pytest output. The child is paused after its real HTTP call.
    original.refresh_from_db()
    live_generations = list(DeviceToken.objects.filter(
        device=device, status=DeviceTokenStatus.ACTIVE,
    ).values_list("staff_extension_generation", flat=True))
    print(f"{scenario}: licence generation={key.staff_extension_generation}, "
          f"original status={original.status}, active token generations={live_generations}")
    assert DeviceActivationOperation.objects.values().get(pk=receipt["id"]) == receipt
    advance()
    if scenario in {"staff-extension-response-lost", "staff-extension-store-failed"}:
        # Child emits this only after it observes the real dropped response or
        # the denied device write. On a legacy status-only response it exits
        # with the specific behavioral assertion, which receive() reports.
        receive("replacement unavailable locally")
        assert_rotated()
        assert DeviceActivationOperation.objects.filter(device=device).count() == 1
        advance()
    receive("staff extension checked")
    assert_rotated()
    if scenario != "staff-extension-response-lost":
        assert DeviceActivationOperation.objects.filter(device=device).count() == 1
    if managed:
        assert FreeLicenseLifecycle.objects.values().get(customer=customer) == marker
        assert LicensePlanAssignment.objects.values().get(license_key=key) == grant
        assert not AuditEvent.objects.filter(action="license_key.free_renewed").exists()


@pytest.mark.skipif(not RUST_BIN and not REQUIRE_G1, reason="requires staged Rust operator integration test binary")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("scenario", [
    "expired", "cascade", "missing", "missing-local", "live", "initial-restart",
    "lost-initial", "managed-free-lost-initial", "race-loss", "race-replay",
    "staff-extension", "staff-extension-response-lost", "staff-extension-store-failed",
    "staff-extension-restart", "staff-extension-managed-free",
])
def test_native_account_controller_against_local_platform_api(scenario, settings, live_server):
    assert RUST_BIN, "SELAHCUE_G1_OPERATOR_TEST_BIN is required when SELAHCUE_G1_REQUIRE=1"
    rust_bin = Path(RUST_BIN)
    assert rust_bin.is_file() and os.access(rust_bin, os.X_OK), (
        "SELAHCUE_G1_OPERATOR_TEST_BIN must point to an executable file"
    )
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    cache.clear()
    now = timezone.now().replace(microsecond=0)
    legacy_free_loss = scenario == "managed-free-lost-initial"
    starts_with_free = legacy_free_loss or scenario == "staff-extension-managed-free"
    if starts_with_free:
        customer = self_service_org()
        enrollment_key = None
    else:
        key, enrollment_key = _seed_license_key(tag=scenario, device_limit=1, starts_at=now - timedelta(days=40))
        assert key.device_limit == 1
        customer = key.customer
    email = f"admin-{scenario}@fixture.test"
    password = "Synthetic-loopback-fixture-only-548!"
    if starts_with_free or scenario in {
        "cascade", "initial-restart", "lost-initial", "staff-extension-response-lost",
    }:
        seed_user(customer, email=email, password=password)

    env = os.environ.copy()
    env["SELAHCUE_G1_FIXTURE_URL"] = live_server.url
    env["SELAHCUE_G1_SCENARIO"] = "lost-initial" if legacy_free_loss else scenario
    env["NO_PROXY"] = "127.0.0.1,localhost"
    try:
        process = subprocess.Popen(
            [str(rust_bin.resolve(strict=True)), OPERATOR_TEST, "--exact", "--ignored", "--nocapture"],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except OSError as error:
        pytest.fail(f"SELAHCUE_G1_OPERATOR_TEST_BIN could not be executed: {error.strerror}", pytrace=False)
    with process as child:
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
            if legacy_free_loss or scenario == "lost-initial":
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
            if scenario.startswith("staff-extension"):
                _staff_extension_case(scenario, customer, receive, advance)
                assert child.wait(timeout=30) == 0
                return
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
