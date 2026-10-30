"""Account audit token-material boundary, including working search controls (17tnw2b9dp2)."""

import json
import logging
from types import SimpleNamespace
from uuid import UUID

import pytest
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import TestCase

from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.models import CredentialToken, CustomerSession, CustomerUser
from selahcue_api.apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db
PASSWORD = "original-audit-passphrase"
NEW_PASSWORD = "replacement-audit-passphrase"
EMAIL = "audit-member@example.test"
ATTEMPT = UUID("8e18f256-4e39-44f6-899c-1a05a674ef27")
ACTIONS = (
    "email_verified", "verification_resent", "logged_in", "session_refreshed",
    "logged_out", "password_reset_requested", "password_reset_completed",
)


class CapturingSender(services.EmailSender):
    def __init__(self):
        self.verify_tokens = []
        self.reset_tokens = []

    def send_email_verification(self, user, raw_token):
        self.verify_tokens.append(raw_token)

    def send_password_reset(self, user, raw_token):
        self.reset_tokens.append(raw_token)


@pytest.fixture
def account(settings):
    cache.clear()
    services._reset_trace_reporting()
    settings.ACCOUNT_RESET_REQUEST_MIN_SECONDS = 0
    sender = CapturingSender()
    services.set_email_sender(sender)
    with TestCase.captureOnCommitCallbacks(execute=True):
        services.register_customer_user(services.RegisterCustomerUserData(
            idempotency_key="token-audit-signup-0001", email=EMAIL, password=PASSWORD,
            org_name="Audit Chapel", country="NG",
        ))
    yield sender, CustomerUser.objects.get(email=EMAIL)
    services.set_email_sender(services.EmailSender())
    cache.clear()
    services._reset_trace_reporting()


def post(client, query, variables=None, bearer=None):
    extra = {"HTTP_AUTHORIZATION": f"Bearer {bearer}"} if bearer else {}
    with TestCase.captureOnCommitCallbacks(execute=True):
        response = client.post(
            "/graphql/account", data=json.dumps({"query": query, "variables": variables or {}}),
            content_type="application/json", REMOTE_ADDR="203.0.113.31", **extra,
        )
    assert response.status_code == 200
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]


def audit_text(rows):
    # No enumerated audit columns: new columns automatically join the search.
    return json.dumps(list(rows.values()), default=str, sort_keys=True)


def matches(text, needles):
    return {needle for needle in needles if needle in text}


def token_needles(raw_tokens, user):
    whole = {PASSWORD, NEW_PASSWORD, user.password_hash}
    for raw in raw_tokens:
        whole.update((raw, services._fingerprint(raw), services._credential_token_hash(raw), services._mask(raw)[2]))
    for model in (CredentialToken, CustomerSession):
        for row in model.objects.filter(customer_user=user):
            whole.update((row.token_fingerprint, row.token_hash, row.masked_token))
    # Same12-character fragment boundary as the shipped failed-confirm scan. Include
    # full masks as well;4-character suffixes alone cause incidental matches in UUIDs.
    needles = set(whole)
    for value in whole:
        needles.update(value[i:i + 12] for i in range(max(len(value) - 11, 1)))
    needles.update((PASSWORD[:6], NEW_PASSWORD[:6]))
    assert len(needles) > 100, "the search lost its token forms/fragment coverage"
    return needles


@pytest.mark.parametrize("action", ACTIONS)
def test_successful_account_flow_has_independent_attempt_id_and_no_audit_or_log_token_material(
    action, account, client, monkeypatch, caplog
):
    sender, user = account
    sessions = []
    if action not in {"email_verified", "verification_resent"}:
        services.verify_email(sender.verify_tokens[-1], client_ip="203.0.113.31")
    if action in {"session_refreshed", "logged_out", "password_reset_completed"}:
        sessions.append(services.login(services.LoginData(EMAIL, PASSWORD)).session_token)
    if action == "password_reset_completed":
        # The reset still has to revoke every active session, not just one.
        sessions.append(services.login(services.LoginData(EMAIL, PASSWORD)).session_token)
        with TestCase.captureOnCommitCallbacks(execute=True):
            services.request_password_reset(EMAIL, client_ip="203.0.113.31")

    historical = AuditEvent.objects.create(
        actor_kind="CUSTOMER_USER", actor_id=str(user.id), action="historical.account_evidence",
        target_type="customer_user", target_id=str(user.id),
        request_id=services._fingerprint(sender.verify_tokens[-1]),
        after={"masked_token": services._mask(sender.verify_tokens[-1])[2]},
    )
    historical_before = AuditEvent.objects.filter(pk=historical.pk).values().get()
    existing = set(AuditEvent.objects.values_list("pk", flat=True))
    # Replace only the services module's UUID namespace; model UUID defaults remain real.
    attempts = []
    def next_attempt():
        attempts.append(ATTEMPT)
        return ATTEMPT
    monkeypatch.setattr(services, "uuid", SimpleNamespace(uuid4=next_attempt))
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        if action == "email_verified":
            data = post(client, 'mutation($t:String!){verifyEmail(token:$t){verified}}', {"t": sender.verify_tokens[-1]})
            assert data["verifyEmail"]["verified"] is True
        elif action == "verification_resent":
            data = post(client, 'mutation($e:String!){resendVerificationEmail(email:$e){accepted}}', {"e": EMAIL})
            assert data["resendVerificationEmail"]["accepted"] is True
            assert len(sender.verify_tokens) == 2
        elif action == "logged_in":
            data = post(client, 'mutation($input:LoginInput!){login(input:$input){sessionToken expiresAt}}', {"input": {"email": EMAIL, "password": PASSWORD}})
            sessions.append(data["login"]["sessionToken"])
            assert services.authenticate_session(sessions[-1])[1].pk == user.pk
        elif action == "session_refreshed":
            data = post(client, 'mutation{refreshSession{sessionToken expiresAt}}', bearer=sessions[-1])
            sessions.append(data["refreshSession"]["sessionToken"])
            assert sessions[0] != sessions[1]
            assert services.authenticate_session(sessions[-1])[1].pk == user.pk
            assert CustomerSession.objects.get(token_fingerprint=services._fingerprint(sessions[0])).status == "REVOKED"
        elif action == "logged_out":
            data = post(client, 'mutation{logout{revoked}}', bearer=sessions[-1])
            assert data["logout"]["revoked"] is True
            assert CustomerSession.objects.get(token_fingerprint=services._fingerprint(sessions[-1])).status == "REVOKED"
        elif action == "password_reset_requested":
            data = post(client, 'mutation($e:String!){requestPasswordReset(email:$e){accepted}}', {"e": EMAIL})
            assert data["requestPasswordReset"]["accepted"] is True
            assert len(sender.reset_tokens) == 1
        else:
            data = post(client, 'mutation($input:ConfirmPasswordResetInput!){confirmPasswordReset(input:$input){reset}}', {"input": {"token": sender.reset_tokens[-1], "newPassword": NEW_PASSWORD}})
            assert data["confirmPasswordReset"]["reset"] is True
            user.refresh_from_db()
            assert check_password(NEW_PASSWORD, user.password_hash)
            assert not CustomerSession.objects.filter(customer_user=user, status="ACTIVE").exists()
            assert CredentialToken.objects.get(token_fingerprint=services._fingerprint(sender.reset_tokens[-1])).consumed_at is not None
    user.refresh_from_db()
    rows = AuditEvent.objects.exclude(pk__in=existing)
    assert rows.count() == 1, "the real successful flow must write exactly its success audit row"
    row = rows.get()
    assert row.action == f"customer_user.{action}"
    assert row.actor_id == str(user.id) and row.result == "SUCCESS"
    assert row.target_type == ("customer_session" if action in {"logged_in", "session_refreshed"} else "customer_user")
    assert row.source_surface == services.ACCOUNT_AUDIT_SURFACE
    needles = token_needles(sender.verify_tokens + sender.reset_tokens + sessions, user)
    assert matches(audit_text(rows), needles) == set(), "token derivative reached an audit column"
    assert matches(caplog.text, needles) == set(), "token derivative reached a flow log"
    assert row.request_id == ATTEMPT.hex
    assert UUID(hex=row.request_id).version == 4
    assert attempts == [ATTEMPT]
    assert AuditEvent.objects.filter(pk=historical.pk).values().get() == historical_before
    if action in {"logged_in", "session_refreshed"}:
        session = CustomerSession.objects.get(pk=row.target_id)
        assert row.after == {"expires_at": session.expires_at.isoformat()}
    if action == "email_verified":
        assert user.email_verified_at is not None and user.status == "ACTIVE"
        assert row.after == {"status": "ACTIVE"}


AUDIT_TEXT_COLUMNS = (
    "actor_kind", "actor_id", "action", "target_type", "target_id", "reason", "result",
    "request_id", "source_surface", "before", "after",
)


@pytest.mark.parametrize("column", AUDIT_TEXT_COLUMNS)
def test_all_column_search_detects_planted_token_fragment(column):
    raw = "SC-PRS-planted-secret-material-which-must-be-detected"
    needles = {services._fingerprint(raw)[17:37]}
    row = AuditEvent.objects.create(
        actor_kind="ANONYMOUS", actor_id="source", action="test.scanner",
        target_type="customer_user", target_id="unresolved", request_id="independent-attempt",
    )
    rows = AuditEvent.objects.filter(pk=row.pk)
    assert matches(audit_text(rows), needles) == set()
    fragment = next(iter(needles))
    value = {"nested": [fragment]} if column in {"before", "after"} else fragment
    rows.update(**{column: value})
    assert matches(audit_text(rows), needles) == needles, f"scanner cannot see {column}"


def test_log_capture_and_fragment_search_detect_planted_material(caplog):
    raw = "SC-PRS-planted-secret-material-which-must-be-detected"
    fingerprint = services._fingerprint(raw)
    masked = services._mask(raw)[2]
    needles = {fingerprint[17:37], masked, PASSWORD[:6]}
    with caplog.at_level(logging.DEBUG):
        logging.getLogger(services.__name__).warning("planted %s %s %s", fingerprint[17:37], masked, PASSWORD[:6])
    assert matches(caplog.text, needles) == needles


def test_repeated_real_logins_use_distinct_random_attempt_ids(account, monkeypatch):
    sender, user = account
    services.verify_email(sender.verify_tokens[-1], client_ip="203.0.113.31")
    expected = [ATTEMPT, UUID("9010a489-603a-48a2-9d4a-ed329d8d25c1")]
    generated = iter(expected)
    monkeypatch.setattr(services, "uuid", SimpleNamespace(uuid4=lambda: next(generated)))
    results = [services.login(services.LoginData(EMAIL, PASSWORD)) for _ in expected]
    rows = list(AuditEvent.objects.filter(action="customer_user.logged_in").order_by("pk"))
    assert len(rows) == 2
    assert [r.request_id for r in rows] == [value.hex for value in expected]
    assert len({r.request_id for r in rows}) == 2
    assert all(UUID(hex=r.request_id).version == 4 for r in rows)
    assert all(services.authenticate_session(r.session_token)[1].pk == user.pk for r in results)
