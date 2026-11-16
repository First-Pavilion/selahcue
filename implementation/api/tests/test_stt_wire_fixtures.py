"""Check the canonical native contract files with the Python producer."""
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from django.test import RequestFactory

import pytest

from selahcue_api.apps.providers.contracts import EphemeralGrant, SecretBytes, SessionFailureCode, SessionResult
from selahcue_api.apps.usage.contracts import ReservationDecision, ReservationState
from selahcue_api.platform.cloud_views import _error, render_session_reply

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3] / "docs/contracts/native-cloud-v1"
COMMON = {"name", "valid", "expected"}
OPTIONAL = {"request", "raw_request_utf8", "response", "raw_response_utf8", "timing", "request_method", "request_headers"}
HEADER_KEYS = {"Cache-Control", "Retry-After", "Allow"}
TAGS = {"success_start", "success_renewal", "quota", "rejected_request", "rejected_response"} | {
    value.value for value in SessionFailureCode
}


def cases(filename):
    document = json.loads((ROOT / filename).read_text())
    assert set(document) == {"schema_version", "cases"} and document["schema_version"] == 1
    names = set()
    for case in document["cases"]:
        assert COMMON <= case.keys() <= COMMON | OPTIONAL
        assert type(case["valid"]) is bool and case["expected"] in TAGS
        assert type(case["name"]) is str and case["name"] not in names
        names.add(case["name"])
        assert len(case.keys() & {"request", "raw_request_utf8"}) == 1
        assert len(case.keys() & {"response", "raw_response_utf8"}) == 1
        reply = case.get("response") or case["raw_response_utf8"]
        assert set(reply["headers"]) <= HEADER_KEYS
        assert reply["headers"]["Cache-Control"] == "no-store"
        yield case


def test_session_examples_render_as_the_shared_native_fixture():
    for case in cases("cloud-session-v1.json"):
        if "raw_response_utf8" in case:
            assert not case["valid"] and "\\ud800" in case["raw_response_utf8"]["body_utf8"]
            continue
        body = case["response"]["body"]
        if "timing" in case:
            timing = case["timing"]
            delta = (
                datetime.fromisoformat(body["authorized_until"]) - datetime.fromisoformat(body["server_time"])
            ).total_seconds()
            t0, t1 = timing["t0_ns"], timing["t1_ns"]
            deadline = t0 + int(delta * 1_000_000_000)
            assert timing["expected_deadline_ns"] == (
                deadline if t0 <= t1 < deadline < 2**64 else None
            )
        if not case["valid"]:
            continue
        provider = body.get("provider")
        result = SessionResult(
            ReservationDecision(UUID(body["reservation_id"]), ReservationState.ISSUED, 300,
                                datetime.fromisoformat(body["authorized_from"]),
                                datetime.fromisoformat(body["authorized_until"]), 0),
            EphemeralGrant(SecretBytes(provider["credential"].encode()), provider["endpoint"],
                           datetime.fromisoformat(provider["credential_expires_at"]), provider["kind"]) if provider else None,
            datetime.fromisoformat(body["server_time"]), datetime.fromisoformat(body["issued_at"]),
            body["policy_version"],
        )
        reply = render_session_reply(result)
        assert json.loads(reply.content) == body
        assert reply["Cache-Control"] == "no-store"


def test_errors_and_raw_invalid_requests_match_wire_fixtures():
    from django.urls import resolve

    for case in cases("cloud-errors-v1.json"):
        expected = case["response"]
        operation = expected["body"]["operation"]
        path = "/v1/quota" if operation == "quota" else "/v1/stt/session"
        if "raw_request_utf8" in case or "request_method" in case:
            request = RequestFactory().generic(
                case.get("request_method", "POST"), path, case.get("raw_request_utf8", ""),
                content_type="application/json", headers=case.get("request_headers"),
            )
            reply = resolve(path).func(request)
        else:
            reply = _error(
                operation, SessionFailureCode(case["expected"]),
                retry=expected["headers"].get("Retry-After"),
            )
        assert reply.status_code == expected["status"], case["name"]
        assert json.loads(reply.content) == expected["body"]
        assert {key: reply[key] for key in expected["headers"]} == expected["headers"]


def test_quota_fixtures_keep_both_meters_and_policy_metadata():
    states = set()
    for case in cases("cloud-quota-v1.json"):
        body = case["response"]["body"]
        assert set(body) == {"stt", "notes", "policies"}
        states.add(body["stt"]["status"])
        assert body["notes"]["meter"] == "notes"
        assert body["policies"]["notes"] is None
        for meter in ("stt", "notes"):
            quota = body[meter]
            assert quota["meter"] == meter
            assert quota["remaining"] == max(0, quota["limit"] - quota["settled"] - quota["held"] - quota["carried_debt"])
            assert datetime.fromisoformat(quota["as_of"]) < datetime.fromisoformat(quota["resets_at"])
    assert states == {"current_observed", "stale", "not_initialized"}
