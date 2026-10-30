"""Real GraphQL regressions for bounded expected-refusal logging (17tnw2b1wve)."""

import json
import logging
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from graphql import GraphQLError

from selahcue_api.apps.accounts.models import CredentialToken
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.throttling import guards
from selahcue_api.graphql import account_schema
from selahcue_api.graphql.errors import ErrorCode, SafeAPIError

pytestmark = pytest.mark.django_db

REQUEST = 'mutation Reset($email: String!) { requestPasswordReset(email: $email) { accepted } }'
CONFIRM = '''mutation Reset($input: ConfirmPasswordResetInput!) {
  confirmPasswordReset(input: $input) { reset }
}'''
REQUEST_VARIABLES = {"email": "private-reset-target@example.test"}
CONFIRM_VARIABLES = {"input": {"token": "private-reset-token", "newPassword": "private-new-password"}}
BUDGETS = (
    ("SELAHCUE_THROTTLE_RESET_REQUEST_GLOBAL", "password_reset_request_global", REQUEST, REQUEST_VARIABLES),
    ("SELAHCUE_THROTTLE_RESET_REQUEST", "password_reset_request_ip", REQUEST, REQUEST_VARIABLES),
    ("SELAHCUE_THROTTLE_RESET_REQUEST_ADDRESS", "password_reset_request_addr", REQUEST, REQUEST_VARIABLES),
    ("SELAHCUE_THROTTLE_RESET_CONFIRM", "password_reset_confirm_ip", CONFIRM, CONFIRM_VARIABLES),
)


@pytest.fixture(autouse=True)
def fresh_budgets(settings):
    cache.clear()
    guards._reset_denial_log_suppression()
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    for setting_name, *_ in BUDGETS:
        setattr(settings, setting_name, (10_000, 3600))
    yield
    cache.clear()
    guards._reset_denial_log_suppression()


def post(client, query=REQUEST, variables=None):
    return client.post(
        "/graphql/account",
        data=json.dumps({"query": query, "variables": variables or REQUEST_VARIABLES}),
        content_type="application/json",
        REMOTE_ADDR="203.0.113.71",
    )


def framework_errors(caplog):
    return [r for r in caplog.records if r.name == "strawberry.execution" and r.levelno >= logging.ERROR]


@pytest.mark.parametrize("setting_name,scope,query,variables", BUDGETS, ids=[b[1] for b in BUDGETS])
def test_100_real_reset_refusals_log_one_line_without_framework_tracebacks(
    client, settings, monkeypatch, caplog, setting_name, scope, query, variables
):
    setattr(settings, setting_name, (0, 3600))
    # Replace only this module's clock reference; do not replace global time.monotonic.
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(guards, "time", SimpleNamespace(monotonic=lambda: clock.now))
    before = (CredentialToken.objects.count(), AuditEvent.objects.count())
    with caplog.at_level(logging.WARNING):
        for _ in range(100):
            response = post(client, query, variables)
            assert response.status_code == 200
            assert response.json()["errors"] == [{
                "message": "Too many requests.", "extensions": {"code": "RATE_LIMITED"}
            }]
        application = [r for r in caplog.records if r.name.startswith("selahcue_api.")]
        assert len(application) == 1
        assert f"scope={scope} " in application[0].getMessage()
        assert application[0].levelno == logging.WARNING
        assert application[0].exc_info is None
        assert "\n" not in application[0].getMessage()
        assert framework_errors(caplog) == [], "expected throttles flooded Strawberry ERROR logging"

        # Same minute remains suppressed; exactly the next boundary reports again.
        clock.now = 159.999
        assert post(client, query, variables).json()["errors"][0]["extensions"]["code"] == "RATE_LIMITED"
        assert len([r for r in caplog.records if r.name == guards.logger.name]) == 1
        clock.now = 160.0
        assert post(client, query, variables).json()["errors"][0]["extensions"]["code"] == "RATE_LIMITED"
        warnings = [r for r in caplog.records if r.name == guards.logger.name]
        assert len(warnings) == 2
        assert all(r.exc_info is None and "\n" not in r.getMessage() for r in warnings)
        assert framework_errors(caplog) == []
    assert (CredentialToken.objects.count(), AuditEvent.objects.count()) == before
    logged = "\n".join(r.getMessage() for r in caplog.records)
    for secret in ("private-reset-target", "private-reset-token", "private-new-password", "203.0.113.71"):
        assert secret not in logged


@pytest.mark.parametrize("failure", [
    RuntimeError("unexpected reset failure"),
    GraphQLError("unexpected coded failure", extensions={"code": "RATE_LIMITED"}),
    SafeAPIError(ErrorCode.INTERNAL),
], ids=["runtime-error", "unexpected-spoofed-code", "other-safe-code"])
def test_non_throttle_failures_keep_original_framework_tracebacks(client, monkeypatch, caplog, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(account_schema, "request_password_reset", fail)
    with caplog.at_level(logging.ERROR, logger="strawberry.execution"):
        response = post(client)
    assert response.status_code == 200
    assert "errors" in response.json()
    records = framework_errors(caplog)
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert records[0].exc_info[1] is failure
    assert records[0].exc_info[2] is not None


def test_legitimate_reset_request_remains_accepted_without_denial_warning(client, settings, caplog):
    settings.ACCOUNT_RESET_REQUEST_MIN_SECONDS = 0
    with caplog.at_level(logging.WARNING):
        response = post(client)
    assert response.status_code == 200
    assert response.json() == {"data": {"requestPasswordReset": {"accepted": True}}}
    assert not [r for r in caplog.records if r.name == guards.logger.name]
    assert framework_errors(caplog) == []
