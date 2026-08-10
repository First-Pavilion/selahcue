import json
from datetime import timedelta

import pytest
from django.utils import timezone


def _seed_license_key(*, tag, device_limit=3, starts_at=None, expires_at=None):
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.license_keys.services import (
        GenerateLicenseKeyData,
        generate_license_key,
    )
    from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission

    customer = CustomerOrg.objects.create(
        name=f"Refresh Church {tag}",
        slug=f"refresh-church-{tag}",
        primary_contact_email=f"ops+{tag}@refresh.example",
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
            starts_at=starts_at or now,
            expires_at=expires_at or (now + timedelta(days=30)),
            timezone="Africa/Lagos",
            seat_limit=5,
            device_limit=device_limit,
            territory="NG",
            reason="Pilot for license-refresh tests.",
        ),
    )
    return result.full_key


def _activate(client, *, license_key, fingerprint="fp-1", idem="refresh-act-0001", platform="macos"):
    body = {
        "idempotency_key": idem,
        "license_key": license_key,
        "device_fingerprint": fingerprint,
        "platform": platform,
    }
    resp = client.post("/v1/activations", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200, resp.content
    return resp.json()["activation_token"]


def _refresh(client, token=None, *, use_body=False):
    if token is None:
        return client.post("/v1/license:refresh", data=json.dumps({}), content_type="application/json")
    if use_body:
        return client.post(
            "/v1/license:refresh",
            data=json.dumps({"device_token": token}),
            content_type="application/json",
        )
    return client.post(
        "/v1/license:refresh",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


@pytest.mark.django_db
def test_refresh_returns_current_license_status_for_a_valid_token(client):
    full_key = _seed_license_key(tag="ok")
    token = _activate(client, license_key=full_key, fingerprint="mac-1")

    response = _refresh(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["device"]["status"] == "ACTIVE"
    assert body["license"]["status"] == "ACTIVATED"
    assert body["license"]["valid_now"] is True
    assert body["instances"]["used"] == 1
    assert body["instances"]["limit"] == 3
    assert body["token"]["expires_at"]
    assert body["entitlement"]["feature_scope"] == "CHURCH"
    # The presented token never echoes back in the status body.
    assert token not in json.dumps(body)


@pytest.mark.django_db
def test_refresh_accepts_the_token_in_the_body_too(client):
    full_key = _seed_license_key(tag="body")
    token = _activate(client, license_key=full_key, fingerprint="mac-body")
    response = _refresh(client, token, use_body=True)
    assert response.status_code == 200
    assert response.json()["license"]["valid_now"] is True


@pytest.mark.django_db
def test_refresh_rejects_unknown_missing_and_expired_tokens(client):
    # Unknown token.
    unknown = _refresh(client, "SC-DEV-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "UNAUTHENTICATED"

    # No token at all.
    missing = _refresh(client, None)
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "UNAUTHENTICATED"

    # Expired token.
    full_key = _seed_license_key(tag="expiredtok")
    token = _activate(client, license_key=full_key, fingerprint="mac-exp")
    from selahcue_api.apps.devices.models import DeviceToken

    # Move the whole window into the past (keeps the expires_at > issued_at check constraint).
    now = timezone.now()
    DeviceToken.objects.update(
        issued_at=now - timedelta(days=2), expires_at=now - timedelta(days=1)
    )
    expired = _refresh(client, token)
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_refresh_rejects_a_revoked_device(client):
    full_key = _seed_license_key(tag="revdev")
    token = _activate(client, license_key=full_key, fingerprint="mac-rev")
    from selahcue_api.apps.devices.models import Device, DeviceStatus

    Device.objects.update(status=DeviceStatus.REVOKED)
    response = _refresh(client, token)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_refresh_rejects_a_revoked_token(client):
    # Revoking the TOKEN (device still ACTIVE + time-valid) is the primary credential-revocation
    # path and must deny — the server-side kill switch for a leaked/rotated token.
    full_key = _seed_license_key(tag="revtok")
    token = _activate(client, license_key=full_key, fingerprint="mac-revtok")
    from selahcue_api.apps.devices.models import DeviceToken, DeviceTokenStatus

    DeviceToken.objects.update(status=DeviceTokenStatus.REVOKED)
    response = _refresh(client, token)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_natural_license_expiry_denies_via_token_expiry(client):
    # DESIGN CONTRACT (DEC-004): a device token's lifetime == the license validity window
    # (token.expires_at = license.expires_at at issuance). So when the calendar passes the license
    # window, the token is ALSO expired → 401 (the desktop treats a 401 on a previously-valid token
    # as "re-activate", not a hard error). Administrative early-EXPIRED/SUSPENDED with an open
    # window still reports truthfully via 200 (see test_expired_license_is_reported_truthfully).
    full_key = _seed_license_key(tag="natexp")
    token = _activate(client, license_key=full_key, fingerprint="mac-natexp")

    from selahcue_api.apps.devices.models import DeviceToken
    from selahcue_api.apps.license_keys.models import AppLicenseKey

    now = timezone.now()
    # Move both windows fully into the past (respecting each expires_at > start check constraint).
    AppLicenseKey.objects.update(
        starts_at=now - timedelta(days=40), expires_at=now - timedelta(days=1)
    )
    DeviceToken.objects.update(
        issued_at=now - timedelta(days=2), expires_at=now - timedelta(days=1)
    )
    response = _refresh(client, token)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.django_db
def test_expired_license_is_reported_truthfully_not_denied(client):
    # A valid *token* whose *license* is EXPIRED must still return 200 with an honest status
    # (valid_now False) so the client can act — only an invalid token denies.
    full_key = _seed_license_key(tag="explic")
    token = _activate(client, license_key=full_key, fingerprint="mac-explic")

    from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus

    # Mark the license EXPIRED but keep expires_at in the future so the token stays valid.
    AppLicenseKey.objects.update(status=LicenseKeyStatus.EXPIRED)

    response = _refresh(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["license"]["status"] == "EXPIRED"
    assert body["license"]["valid_now"] is False


@pytest.mark.django_db
def test_refresh_never_leaks_the_token_hash(client):
    full_key = _seed_license_key(tag="secrecy")
    token = _activate(client, license_key=full_key, fingerprint="mac-sec")
    response = _refresh(client, token)
    body_text = json.dumps(response.json())

    from selahcue_api.apps.devices.models import DeviceToken

    token_row = DeviceToken.objects.get()
    assert token not in body_text
    assert token_row.token_hash not in body_text
    assert token_row.token_fingerprint not in body_text
