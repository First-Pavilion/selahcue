import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.core import signing
from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.utils import timezone

from selahcue_api.apps.pilot_downloads.models import PilotRegistrationRecord, PilotSheetDestination
from selahcue_api.apps.pilot_downloads.services import (
    PilotRegistrationError, confirm_registration, reserve_registration,
    verify_registration_receipt,
)
from selahcue_api.graphql.route_contracts import desktop_command_contracts, pilot_registration_contracts


pytestmark = pytest.mark.django_db


@pytest.fixture
def pilot_policy(settings):
    value = {
        "enabled": True, "n8n_token": "t" * 48,
        "signing_key": "s" * 48, "fingerprint_key": "f" * 48,
        "spreadsheet_id": "sandbox-sheet-123", "sheet_tab": "Registrations",
        "capacity": 4, "notice_versions": ["test-notice-v1"],
        "collection_owner": "sandbox-test-owner", "retention_days": 30,
        "layout_protected": True, "receipt_ttl_seconds": 300,
        "pilot_expires_at": (timezone.now() + timedelta(days=60)).isoformat(),
    }
    settings.SELAHCUE_PILOT_REGISTRATION = value
    return value


def payload(**changes):
    value = {
        "schema_version": 1, "registration_id": str(uuid4()),
        "full_name": "Test Operator", "email": "operator@example.invalid",
        "phone": "", "church_name": "Test Church", "church_role": "Operator",
        "church_city": "Lagos", "church_country": "Nigeria",
        "platform": "Ubuntu", "notice_version": "test-notice-v1",
    }
    value.update(changes)
    return value


def ack(reservation, **changes):
    write = reservation["sheet_write"]
    value = {
        "spreadsheetId": write["spreadsheet_id"], "updatedRange": write["range"],
        "updatedRows": 1, "updatedColumns": 13, "updatedCells": 13,
    }
    value.update(changes)
    return {"registration_id": reservation["registration_id"], "sheet_ack": value}


def test_reserve_binds_one_row_and_never_stores_contact_values(pilot_policy):
    data = payload()
    first = reserve_registration(data)
    repeated = reserve_registration(dict(data))
    assert first == repeated
    assert first["state"] == "pending"
    assert "receipt" not in first
    assert first["sheet_write"]["range"] == "'Registrations'!A2:M2"
    assert first["sheet_write"]["valueInputOption"] == "RAW"
    assert first["sheet_write"]["values"][0][0] == data["registration_id"]
    record = PilotRegistrationRecord.objects.get()
    assert record.confirmed_at is None
    assert record.sheet_row == 2
    assert data["email"] not in repr(record.__dict__)
    assert data["church_name"] not in repr(record.__dict__)
    assert PilotSheetDestination.objects.get().next_row == 3


def test_same_identity_cannot_change_payload_or_destination(pilot_policy):
    data = payload()
    reserve_registration(data)
    for modified in (dict(data, email="other@example.invalid"), dict(data, platform="Windows")):
        with pytest.raises(PilotRegistrationError, match="identity_conflict"):
            reserve_registration(modified)
    pilot_policy["spreadsheet_id"] = "other-sandbox-sheet"
    with pytest.raises(PilotRegistrationError, match="identity_conflict"):
        reserve_registration(data)
    assert PilotRegistrationRecord.objects.count() == 1


def test_ambiguous_sheet_timeout_reuses_range_then_confirm_issues_bound_receipt(pilot_policy):
    data = payload()
    reservation = reserve_registration(data)
    # Simulate remote write possibly succeeding but its ACK being lost. Do not confirm.
    retry = reserve_registration(data)
    assert retry["sheet_write"] == reservation["sheet_write"]
    saved = confirm_registration(ack(retry))
    assert saved["state"] == "confirmed"
    assert "sheet_write" not in reserve_registration(data)
    claims = verify_registration_receipt(saved["receipt"])
    assert claims["registration_id"] == data["registration_id"]
    assert claims["platform"] == "Ubuntu"
    assert claims["channel"] == "pilot"
    assert "email" not in json.dumps(claims)
    assert "download_url" not in saved
    expiry = saved["expires_at"]
    assert confirm_registration(ack(retry))["expires_at"] == expiry


@pytest.mark.parametrize("field,value", [
    ("spreadsheetId", "foreign-sheet"), ("updatedRange", "'Registrations'!A3:M3"),
    ("updatedRows", True), ("updatedRows", 2), ("updatedColumns", 12),
    ("updatedCells", 12), ("updatedRange", []), ("updatedRange", None),
])
def test_mismatching_sheet_ack_cannot_confirm(pilot_policy, field, value):
    reserved = reserve_registration(payload())
    with pytest.raises(PilotRegistrationError, match="sheet_ack_invalid"):
        confirm_registration(ack(reserved, **{field: value}))
    assert PilotRegistrationRecord.objects.get().confirmed_at is None


def test_capacity_is_bounded_and_allocations_are_not_reused(pilot_policy):
    for _ in range(3):
        reserve_registration(payload())
    with pytest.raises(PilotRegistrationError, match="sheet_capacity_exhausted"):
        reserve_registration(payload())
    assert PilotRegistrationRecord.objects.count() == 3
    assert PilotSheetDestination.objects.get().next_row == 5
    with pytest.raises(ProtectedError):
        PilotSheetDestination.objects.get().delete()


@pytest.mark.parametrize("missing", [
    "collection_owner", "retention_days", "notice_versions", "n8n_token",
    "fingerprint_key", "signing_key", "spreadsheet_id", "sheet_tab",
    "receipt_ttl_seconds", "capacity", "pilot_expires_at",
])
def test_policy_must_be_complete_before_collection(pilot_policy, missing):
    pilot_policy.pop(missing)
    with pytest.raises(PilotRegistrationError, match="configuration_required"):
        reserve_registration(payload())
    assert PilotRegistrationRecord.objects.count() == 0


def test_protection_disabled_or_unknown_notice_blocks_collection(pilot_policy):
    pilot_policy["layout_protected"] = False
    with pytest.raises(PilotRegistrationError, match="configuration_required"):
        reserve_registration(payload())
    pilot_policy["layout_protected"] = True
    with pytest.raises(PilotRegistrationError, match="notice_not_approved"):
        reserve_registration(payload(notice_version="unapproved-v1"))


def test_expiry_retention_and_tampering_fail_closed(pilot_policy, monkeypatch):
    now = timezone.now().replace(microsecond=0)
    monkeypatch.setattr("selahcue_api.apps.pilot_downloads.services.timezone.now", lambda: now)
    reserved = reserve_registration(payload())
    receipt = confirm_registration(ack(reserved))["receipt"]
    with pytest.raises(PilotRegistrationError, match="receipt_invalid"):
        verify_registration_receipt(receipt + "tampered")
    later = now + timedelta(seconds=301)
    monkeypatch.setattr("selahcue_api.apps.pilot_downloads.services.timezone.now", lambda: later)
    with pytest.raises(PilotRegistrationError, match="receipt_expired"):
        verify_registration_receipt(receipt)
    with pytest.raises(PilotRegistrationError, match="receipt_expired"):
        confirm_registration(ack(reserved))


def test_noncanonical_google_range_is_accepted_only_for_same_fixed_row(pilot_policy):
    reserved = reserve_registration(payload())
    assert confirm_registration(ack(reserved, updatedRange="Registrations!A2:M2"))["state"] == "confirmed"


def test_endpoints_require_enabled_config_and_server_auth(client, settings, pilot_policy):
    url = "/v1/pilot/registrations:reserve"
    settings.SELAHCUE_PILOT_REGISTRATION = {"enabled": False}
    assert client.post(url, payload(), content_type="application/json").status_code == 404
    settings.SELAHCUE_PILOT_REGISTRATION = pilot_policy
    assert client.post(url, payload(), content_type="application/json").status_code == 403
    headers = {"HTTP_AUTHORIZATION": "Bearer " + pilot_policy["n8n_token"]}
    assert client.post(url, payload(), content_type="application/json", **headers).status_code == 200
    assert client.post(url, {"registered": True}, content_type="application/json", **headers).status_code == 400
    assert client.post(url, "x" * 33000, content_type="application/json", **headers).status_code == 413
    method_error = client.get(url, **headers)
    assert method_error.status_code == 405
    assert method_error["Allow"] == "POST"
    assert client.post(url, "not-json", content_type="text/plain", **headers).status_code == 415
    assert PilotRegistrationRecord.objects.count() == 1


def test_callback_ack_is_not_a_browser_registration_assertion(client, pilot_policy, caplog):
    headers = {"HTTP_AUTHORIZATION": "Bearer " + pilot_policy["n8n_token"]}
    data = payload()
    reserved = client.post("/v1/pilot/registrations:reserve", data, content_type="application/json", **headers).json()
    url = "/v1/pilot/registrations:confirm"
    assert client.post(url, ack(reserved), content_type="application/json").status_code == 403
    failed = client.post(url, {"registration_id": data["registration_id"], "registered": True}, content_type="application/json", **headers)
    assert failed.status_code == 400
    assert PilotRegistrationRecord.objects.get().confirmed_at is None
    confirmed = client.post(url, ack(reserved), content_type="application/json", **headers)
    assert confirmed.status_code == 200
    assert confirmed["Cache-Control"] == "no-store"
    assert "download_url" not in confirmed.json()
    assert data["email"] not in caplog.text
    assert pilot_policy["n8n_token"] not in caplog.text


def test_server_callbacks_keep_device_and_cookie_auth_separate(client, pilot_policy):
    contracts = pilot_registration_contracts()
    assert len(contracts) == 2
    assert all(value.auth_context == "n8n_server_bearer_no_cookie" for value in contracts)
    assert not ({value.path for value in contracts} & {value.path for value in desktop_command_contracts()})
    client.cookies["selahcue_account_session"] = "pretend-customer-session"
    for value in contracts:
        response = client.post("/" + value.path, payload(), content_type="application/json", HTTP_AUTHORIZATION="Bearer pretend-device-token")
        assert response.status_code == 403
        assert response.json() == {"error": {"code": "server_auth_required"}}
        assert not response.cookies
    assert PilotRegistrationRecord.objects.count() == 0


def test_server_auth_works_without_csrf_cookie_but_still_requires_its_own_budget(settings, pilot_policy):
    client = Client(enforce_csrf_checks=True)
    headers = {"HTTP_AUTHORIZATION": "Bearer " + pilot_policy["n8n_token"]}
    url = "/v1/pilot/registrations:reserve"
    settings.SELAHCUE_THROTTLE_PILOT_REGISTRATION = (1, 60)
    cache.clear()
    try:
        assert client.post(url, payload(), content_type="application/json").status_code == 403
        valid = client.post(url, payload(), content_type="application/json", **headers)
        assert valid.status_code == 200
        assert not valid.cookies
        limited = client.post(url, payload(), content_type="application/json", **headers)
        assert limited.status_code == 429
        assert limited.json() == {"error": {"code": "registration_rate_limited"}}
        assert limited["Cache-Control"] == "no-store"
        assert "Retry-After" in limited
        assert PilotRegistrationRecord.objects.count() == 1
    finally:
        cache.clear()


def test_receipt_is_purpose_bound_and_missing_ledger_state_cannot_authorize(pilot_policy):
    reserved = reserve_registration(payload())
    saved = confirm_registration(ack(reserved))
    claims = verify_registration_receipt(saved["receipt"])
    wrong_purpose = signing.dumps(claims, key=pilot_policy["signing_key"], salt="different-purpose")
    with pytest.raises(PilotRegistrationError, match="receipt_invalid"):
        verify_registration_receipt(wrong_purpose)
    PilotRegistrationRecord.objects.all().delete()
    with pytest.raises(PilotRegistrationError, match="receipt_invalid"):
        verify_registration_receipt(saved["receipt"])


def test_retention_and_pilot_end_block_resumption(pilot_policy, monkeypatch):
    now = timezone.now()
    data = payload()
    reserve_registration(data)
    monkeypatch.setattr("selahcue_api.apps.pilot_downloads.services.timezone.now", lambda: now + timedelta(days=31))
    with pytest.raises(PilotRegistrationError, match="registration_retired"):
        reserve_registration(data)
    monkeypatch.setattr("selahcue_api.apps.pilot_downloads.services.timezone.now", lambda: now + timedelta(days=61))
    with pytest.raises(PilotRegistrationError, match="pilot_expired"):
        reserve_registration(data)
