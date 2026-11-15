import pytest as _pytest
pytestmark = _pytest.mark.django_db

from datetime import UTC, datetime
from uuid import UUID

from django.urls import resolve


def test_default_readiness_has_no_fabricated_coverage():
    import importlib

    try:
        reader = importlib.import_module("selahcue_api.apps.usage.readiness").read_stt_readiness
    except ModuleNotFoundError:
        reader = None
    assert callable(reader)
    at = datetime(2026, 11, 15, 12, tzinfo=UTC)
    mapping_id = UUID(int=1)
    result = reader(org_id=1, mapping_id=mapping_id, at=at)
    assert (result.org_id, result.mapping_id, result.status, result.checked_at) == (
        1, mapping_id, "not_initialized", at,
    )
    assert result.blocked_reason == "reader_missing"
    assert (result.observed_through, result.valid_until, result.publication_revision) == (None, None, None)


def test_session_route_accepts_only_header_authentication(client):
    reply = client.post(
        "/v1/stt/session?device_token=synthetic",
        {
            "idempotency_key": str(UUID(int=1)), "action": "start", "socket": "new",
            "consent_version": "stt-direct-audio-v1", "policy_version": "stt-direct-v1",
        },
        content_type="application/json",
    )
    assert reply.status_code == 401
    assert resolve("/v1/stt/session").url_name == "stt-session"
