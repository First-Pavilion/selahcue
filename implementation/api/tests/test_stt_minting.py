import base64
import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.django_db

AT = datetime(2026, 11, 15, 10, tzinfo=UTC)


def _segment(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


def _parse(status, body):
    try:
        module = importlib.import_module("selahcue_api.apps.providers.adapters.deepgram_grants")
    except ModuleNotFoundError:
        pytest.fail("The bounded Deepgram parser is absent")
    return module.parse_grant(status, body, request_started_at=AT, response_received_at=AT + timedelta(seconds=1))


@pytest.mark.parametrize("status", [301, 400, 403, 429, 500])
def test_non_200_cannot_prove_nonissuance(status):
    result = _parse(status, b'{}')
    assert result.code == "provider_outcome_unproven"


@pytest.mark.parametrize(("claims", "lifetime"), [
    ({}, "30"), ({"exp": True}, "30"), ({"exp": 253402300799}, "30"),
    ({"exp": int(AT.timestamp()) + 30}, "true"), ({"exp": int(AT.timestamp()) + 30}, '"30"'),
    ({"exp": int(AT.timestamp()) + 30}, "30.01"), ({"exp": int(AT.timestamp()) + 30}, "NaN"),
])
def test_bad_exp_or_optional_lifetime_holds_uncertain(claims, lifetime):
    token = f"{_segment({'alg': 'HS256'})}.{_segment(claims)}.c2ln"
    result = _parse(200, f'{{"access_token":"{token}","expires_in":{lifetime}}}'.encode())
    assert result.code == "invalid_provider_response"
    assert token not in repr(result)


def test_grant_uses_exp_as_absolute_expiry():
    token = f"{_segment({'alg': 'HS256'})}.{_segment({'exp': int(AT.timestamp()) + 27})}.c2ln"
    result = _parse(200, json.dumps({"access_token": token, "expires_in": 30}).encode())
    assert result.grant.expires_at == AT + timedelta(seconds=27)
    assert result.grant.secret.value == token.encode()
    assert token not in repr(result) + repr(result.grant)


def test_circuit_has_five_eligible_failures_one_probe_and_generation_fencing():
    from selahcue_api.apps.providers.contracts import DefiniteFailure, Granted, MintFailureCode as Code, OutcomeUnknown
    from selahcue_api.apps.providers.stt_circuit import SttCircuit

    now = 1.0
    circuit = SttCircuit(clock=lambda: now)
    old = circuit.admit()
    for _ in range(4):
        circuit.finish(circuit.admit(), OutcomeUnknown(Code.TRANSPORT_ERROR))
        circuit.finish(circuit.admit(), DefiniteFailure(Code.REQUEST_REJECTED_LOCALLY))
        assert circuit.available()
    circuit.finish(circuit.admit(), OutcomeUnknown(Code.TRANSPORT_TIMEOUT))
    assert not circuit.available() and circuit.admit() is None
    circuit.finish(old, Granted(None))
    assert not circuit.available()
    now += 30
    probe = circuit.admit()
    assert probe is not None and circuit.admit() is None
    circuit.finish(probe, None)
    second = circuit.admit()
    assert second != probe
    circuit.finish(probe, Granted(None))
    assert circuit.admit() is None
    circuit.finish(second, Granted(None))
    assert circuit.available()
