"""Revocation cascade + expiry sweeps.

Closes R6 from the entitlement-manifest spec: the issuance gate stops re-issue, this
stops the already-issued token. Together they make revocation effective without a
revocation list.

Both jobs run from Celery beat under `CELERY_TASK_ACKS_LATE`, so a crashed worker
redelivers them — every assertion about idempotency here is load-bearing, not decorative.
"""

import json
import subprocess
import sys
from datetime import timedelta

import pytest
from django.utils import timezone

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices.models import Device, DeviceToken, DeviceTokenStatus
from selahcue_api.apps.devices.tasks import cascade_license_revocations
from selahcue_api.apps.license_keys.models import LicenseKeyStatus

pytestmark = pytest.mark.django_db


# Module-local seeding helpers, copied from tests/test_entitlement_manifest_slice.py. The
# shipped slices each build their own rather than sharing a conftest.py — follow that.
def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    """Returns (AppLicenseKey, full_key)."""
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Cascade Church {tag}",
        slug=f"cascade-church-{tag}",
        primary_contact_email=f"ops+{tag}@cascade.example",
        country="NG",
        timezone="Africa/Lagos",
        plan="TRIAL",
        seat_limit=5,
        device_limit=device_limit,
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"customer-org-{tag}",
    )
    now = timezone.now().replace(microsecond=0)
    actor = ActorContext(
        kind=ActorKind.STAFF,
        actor_id="staff_ops_1",
        staff_permissions=frozenset({StaffPermission.GENERATE_LICENSE_KEY}),
    )
    result = generate_license_key(
        actor,
        GenerateLicenseKeyData(
            idempotency_key=f"license-key-{tag}",
            customer_id=str(customer.id),
            key_type="TRIAL",
            feature_scope="CHURCH",
            plan_code="LEGACY",
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for revocation-cascade tests.",
        ),
    )
    return result.license_key, result.full_key


def _activate(client, *, full_key, tag):
    """Activate over HTTP, as the manifest slice does. Returns (device_token, device_public_id)."""
    body = {
        "idempotency_key": f"cascade-act-{tag}",
        "license_key": full_key,
        "device_fingerprint": f"fp-cascade-{tag}",
        "platform": "macos",
    }
    resp = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    return payload["activation_token"], payload["device"]["device_public_id"]


@pytest.fixture(autouse=True)
def _fresh_throttle_budget():
    """`/v1` is rate limited per (endpoint, client IP), and the default LocMemCache lives for
    the whole pytest process — so budget spent by an earlier test would otherwise leak into
    this one and 429 it. Reset the window instead of loosening the limits."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def activated(client):
    """An activated device on a live licence. Returns (Device, device_token, AppLicenseKey)."""
    key, full_key = _seed_license_key(tag="c1")
    token, device_public_id = _activate(client, full_key=full_key, tag="c1")
    device = Device.objects.get(device_public_id=device_public_id)
    # First activation flips the key ISSUED -> ACTIVATED (devices/services.py), so the
    # in-memory object returned at creation is stale. Refresh, or assertions compare
    # against a status the database no longer holds.
    key.refresh_from_db()
    return device, token, key


# --- Revocation cascade ---------------------------------------------------------------


def test_revoked_licence_revokes_its_device_tokens(activated):
    device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])

    changed = cascade_license_revocations()

    assert changed == 1
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.REVOKED


def test_active_licence_is_left_alone(activated):
    device, _token, _key = activated
    assert cascade_license_revocations() == 0
    assert DeviceToken.objects.get(device=device).status == DeviceTokenStatus.ACTIVE


def test_cascade_is_idempotent(activated):
    """acks_late means a crashed worker redelivers this job. The second run must be a
    no-op, not a second revocation and a second audit row."""
    _device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])

    assert cascade_license_revocations() == 1
    assert cascade_license_revocations() == 0  # nothing left to do
    assert AuditEvent.objects.filter(action="device_token.revoked_by_cascade").count() == 1


def test_cascade_is_audited(activated):
    _device, _token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])
    cascade_license_revocations()
    assert AuditEvent.objects.filter(action="device_token.revoked_by_cascade").count() == 1


def test_cascade_records_no_token_material(activated):
    """The audit row names the token by id only. A revocation record is not a place to
    leave the credential it revoked."""
    _device, token, key = activated
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])
    cascade_license_revocations()
    event = AuditEvent.objects.get(action="device_token.revoked_by_cascade")
    assert token not in json.dumps({"reason": event.reason, "after": event.after})
    assert event.target_type == "device_token"


def test_cascade_is_bounded_by_batch_size(client):
    """Standing repo rule: no unbounded queries. Two stale tokens with batch_size=1 must
    take two runs, proving the slice is applied rather than decorative."""
    key, full_key = _seed_license_key(tag="c2", device_limit=2)
    _activate(client, full_key=full_key, tag="c2a")
    _activate(client, full_key=full_key, tag="c2b")
    key.refresh_from_db()
    key.status = LicenseKeyStatus.REVOKED
    key.save(update_fields=["status", "updated_at"])

    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 2
    assert cascade_license_revocations(batch_size=1) == 1
    assert DeviceToken.objects.filter(status=DeviceTokenStatus.ACTIVE).count() == 1
    assert cascade_license_revocations(batch_size=1) == 1
    assert cascade_license_revocations(batch_size=1) == 0


# --- Expiry sweeps --------------------------------------------------------------------


def _seed_customer_user(*, tag):
    from selahcue_api.apps.accounts.models import CustomerOrg, CustomerUser

    customer = CustomerOrg.objects.create(
        name=f"Sweep Church {tag}",
        slug=f"sweep-church-{tag}",
        primary_contact_email=f"ops+{tag}@sweep.example",
        country="NG",
        created_by_actor_id="staff_ops_1",
        idempotency_key=f"sweep-org-{tag}",
    )
    return CustomerUser.objects.create(
        customer=customer,
        email=f"user+{tag}@sweep.example",
        email_fingerprint=f"fp-user-{tag}",
        password_hash="not-a-real-hash",
        created_by_actor_id="self_signup",
        idempotency_key=f"sweep-user-{tag}",
    )


def _seed_session(user, *, tag, expires_at):
    from selahcue_api.apps.accounts.models import CustomerSession

    return CustomerSession.objects.create(
        customer_user=user,
        token_prefix=f"sess_{tag}",
        token_suffix=tag,
        masked_token=f"sess_{tag}...{tag}",
        token_hash=f"hash-{tag}",
        token_fingerprint=f"sessfp-{tag}",
        # The model has a CHECK constraint expires_at > issued_at, so issue well before.
        issued_at=expires_at - timedelta(days=1),
        expires_at=expires_at,
    )


def _seed_credential_token(user, *, tag, expires_at):
    from selahcue_api.apps.accounts.models import CredentialToken, CredentialTokenPurpose

    return CredentialToken.objects.create(
        customer_user=user,
        purpose=CredentialTokenPurpose.EMAIL_VERIFY,
        token_hash=f"hash-{tag}",
        token_fingerprint=f"credfp-{tag}",
        masked_token=f"cred_{tag}...{tag}",
        expires_at=expires_at,
    )


def test_sweep_deletes_expired_credential_tokens_only():
    """Seeded both sides deliberately: an assertion that only counts what survives would
    also pass against a sweep that deletes nothing, or one that deletes everything."""
    from selahcue_api.apps.accounts.maintenance import sweep_expired_credentials
    from selahcue_api.apps.accounts.models import CredentialToken, CustomerSession

    user = _seed_customer_user(tag="s1")
    now = timezone.now()
    dead_session = _seed_session(user, tag="dead", expires_at=now - timedelta(hours=1))
    live_session = _seed_session(user, tag="live", expires_at=now + timedelta(hours=1))
    dead_cred = _seed_credential_token(user, tag="dead", expires_at=now - timedelta(hours=1))
    live_cred = _seed_credential_token(user, tag="live", expires_at=now + timedelta(hours=1))

    result = sweep_expired_credentials()

    # Exact counts: ">= 0" would be satisfied by a sweep that does nothing at all.
    assert result == {"sessions": 1, "credential_tokens": 1}
    assert not CustomerSession.objects.filter(pk=dead_session.pk).exists()
    assert not CredentialToken.objects.filter(pk=dead_cred.pk).exists()
    # The "only" half of the name: unexpired rows are untouched.
    assert CustomerSession.objects.filter(pk=live_session.pk).exists()
    assert CredentialToken.objects.filter(pk=live_cred.pk).exists()


def test_sweep_is_idempotent():
    """acks_late redelivery: the second run finds nothing and must report nothing."""
    from selahcue_api.apps.accounts.maintenance import sweep_expired_credentials

    user = _seed_customer_user(tag="s2")
    now = timezone.now()
    _seed_session(user, tag="d2", expires_at=now - timedelta(hours=1))
    _seed_credential_token(user, tag="d2", expires_at=now - timedelta(hours=1))

    assert sweep_expired_credentials() == {"sessions": 1, "credential_tokens": 1}
    assert sweep_expired_credentials() == {"sessions": 0, "credential_tokens": 0}


def test_sweep_is_bounded_by_batch_size():
    """Standing repo rule: no unbounded deletes. Three expired sessions with batch_size=2
    must take two runs."""
    from selahcue_api.apps.accounts.maintenance import sweep_expired_credentials

    user = _seed_customer_user(tag="s3")
    now = timezone.now()
    for n in range(3):
        _seed_session(user, tag=f"b{n}", expires_at=now - timedelta(hours=1))

    assert sweep_expired_credentials(batch_size=2)["sessions"] == 2
    assert sweep_expired_credentials(batch_size=2)["sessions"] == 1
    assert sweep_expired_credentials(batch_size=2)["sessions"] == 0


# --- Beat/worker contract -------------------------------------------------------------

_REGISTRATION_PROBE = """
import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")
django.setup()

from django.conf import settings
from selahcue_api import celery_app

# Exactly what `celery -A selahcue_api worker` does at startup, and the ONLY thing that
# registers a task module the rest of the app never imports.
celery_app.loader.import_default_modules()

scheduled = sorted(entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values())
missing = [name for name in scheduled if name not in celery_app.tasks]
print("SCHEDULED=" + ",".join(scheduled))
print("MISSING=" + ",".join(missing))
"""


def test_every_beat_scheduled_task_is_registered_in_a_worker_process():
    """Beat schedules tasks by NAME. If the worker never imports the module that defines
    the name, beat dispatches happily and every run dies with NotRegistered — silently,
    nightly, in production.

    Run in a subprocess on purpose: this module imports `devices.tasks` directly at the
    top, which would register the task and make an in-process assertion pass for the wrong
    reason. A clean interpreter that only runs Celery's own autodiscovery is the real test,
    and it is what catches a task parked in a module `autodiscover_tasks()` never looks at
    (e.g. `maintenance.py` instead of `tasks.py`).
    """
    completed = subprocess.run(
        [sys.executable, "-c", _REGISTRATION_PROBE],
        capture_output=True,
        text=True,
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    scheduled = next(
        line[len("SCHEDULED=") :] for line in output.splitlines() if line.startswith("SCHEDULED=")
    ).split(",")
    missing = [
        part
        for line in output.splitlines()
        if line.startswith("MISSING=")
        for part in line[len("MISSING=") :].split(",")
        if part
    ]

    assert missing == [], f"beat schedules tasks no worker registers: {missing}"
    assert "devices.cascade_license_revocations" in scheduled
    assert "accounts.sweep_expired_credentials" in scheduled
