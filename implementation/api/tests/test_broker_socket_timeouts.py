"""Real request -> on_commit -> production sender -> Kombu/redis-py tests.

A silent loopback broker reproduces the original indefinite read. A BaseException watchdog
cannot be swallowed by the sender's recovery path. Healthy Redis uses unique key prefixes,
never FLUSHDB. Connect blackholes are verified by client kwargs, not simulated on loopback.
"""

import base64
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager

import pytest
from celery import Celery
from celery.backends.redis import RedisBackend
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from redis import Redis

from selahcue_api import settings as project_settings
from selahcue_api.apps.accounts import email as email_module
from selahcue_api.apps.accounts import services
from selahcue_api.apps.accounts.email import CeleryEmailSender
from selahcue_api.apps.accounts.tasks import send_verification_email_task
from test_cache_socket_timeouts import StalledRedis, _watchdog, needs_sigalrm
from test_customer_auth_slice import REGISTER, REQUEST_RESET, register_input
from test_resend_verification import RESEND, _make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_publish_log(monkeypatch):
    monkeypatch.setattr(email_module, "_last_publish_failure_log", float("-inf"), raising=False)

TIMEOUT = 0.2


@contextmanager
def publisher(monkeypatch, url, *, prefix=None, result_backend="cache+memory://"):
    monkeypatch.setenv("CELERY_BROKER_URL", url)
    # Celery's environment backend takes precedence over the constructor argument too.
    # Make the memory siblings explicit, then exercise production-shaped Redis separately.
    monkeypatch.setenv("CELERY_RESULT_BACKEND", result_backend)
    app = Celery("broker_test", broker=url, backend=result_backend, set_as_current=False)
    app.conf.update(
        broker_transport_options={
            **getattr(project_settings, "CELERY_BROKER_TRANSPORT_OPTIONS", {}),
            "global_keyprefix": prefix or f"broker-test-{uuid.uuid4().hex}:",
        },
        task_default_queue="email-probe",
        task_always_eager=False,
    )
    previous_sender = services.get_email_sender()
    services.set_email_sender(CeleryEmailSender())
    # Real shared tasks, real app/connection and real task serialization; only substitute the
    # application's broker endpoint so no deployed/shared queue receives the synthetic tokens.
    tasks = app.tasks
    for attr in ("send_verification_email_task", "send_password_reset_task", "send_account_exists_task"):
        original = getattr(email_module, attr)
        monkeypatch.setattr(email_module, attr, tasks[original.name])
    try:
        yield app
    finally:
        services.set_email_sender(previous_sender)
        if isinstance(app.backend, RedisBackend):
            # PubSub.close and pool.disconnect close owned sockets without unsubscribing or
            # waiting for a server response, including after the BaseException watchdog fires.
            app.backend.result_consumer.stop()
            app.backend.client.close()
            app.backend.client.connection_pool.disconnect()
        app.close()


def test_broker_options_bound_both_sockets():
    options = project_settings.CELERY_BROKER_TRANSPORT_OPTIONS
    for name in ("socket_timeout", "socket_connect_timeout"):
        assert 0.05 <= options[name] <= 10


@pytest.mark.parametrize("name", ["CELERY_BROKER_SOCKET_TIMEOUT", "CELERY_BROKER_SOCKET_CONNECT_TIMEOUT"])
@pytest.mark.parametrize("value", ["0", "-1", "0.049", "10.01", "nan", "inf", "oops"])
def test_invalid_broker_timeout_refuses_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ImproperlyConfigured, match=name):
        project_settings._socket_timeout_seconds(name, "0.5")


def _request(client, path):
    cache.clear()  # LocMem only in this test module
    email = f"broker-{uuid.uuid4().hex}@example.test"
    if path.startswith("signup"):
        if path == "signup-existing":
            _make_user(email, tag=uuid.uuid4().hex)
        query, variables = REGISTER, register_input(idem=uuid.uuid4().hex, email=email)
        field = "registerCustomerUser"
    else:
        _make_user(email, tag=uuid.uuid4().hex)
        query, variables = (RESEND if path == "resend" else REQUEST_RESET), {"e": email}
        field = "resendVerificationEmail" if path == "resend" else "requestPasswordReset"
    # The caller tests use real commits: the on_commit publisher must finish before the
    # HTTP response returns, rather than executing a captured callback after the request.
    response = client.post("/graphql/account", data=json.dumps({"query": query, "variables": variables}), content_type="application/json")
    assert response.status_code == 200
    assert response.json() == {"data": {field: {"accepted": True}}}


@needs_sigalrm
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("path", ["signup", "signup-existing", "resend", "reset"])
def test_silent_broker_bounds_real_request(client, settings, monkeypatch, caplog, path):
    settings.CACHES = {"default": project_settings._cache_config("", TIMEOUT, TIMEOUT)}
    server = StalledRedis()
    try:
        budget = project_settings.CELERY_BROKER_SOCKET_TIMEOUT
        started = time.monotonic()
        with publisher(monkeypatch, server.url), caplog.at_level(logging.ERROR), _watchdog(budget + 5):
            _request(client, path)
        elapsed = time.monotonic() - started
        print(f"silent broker {path}: {elapsed:.3f}s; read timeout {budget}s")
        assert elapsed < budget + 3, "failure must cost one timeout plus request work/jitter"
        assert server.connections_after_settling(1) == 1, "hidden reconnect multiplies timeout"
        assert "email delivery unconfirmed" in caplog.text
        assert "TimeoutError" in caplog.text or "OperationalError" in caplog.text
    finally:
        server.close()


@pytest.mark.skipif(not os.getenv("CELERY_BROKER_URL"), reason="needs CI Redis broker")
@pytest.mark.parametrize("path", ["signup", "signup-existing", "resend", "reset"])
@pytest.mark.django_db(transaction=True)
def test_healthy_broker_gets_real_request_task(client, settings, monkeypatch, path):
    settings.CACHES = {"default": project_settings._cache_config("", TIMEOUT, TIMEOUT)}
    prefix = f"broker-test-{uuid.uuid4().hex}:"
    redis = Redis.from_url(os.environ["CELERY_BROKER_URL"], socket_timeout=1, socket_connect_timeout=1)
    try:
        with publisher(monkeypatch, os.environ["CELERY_BROKER_URL"], prefix=prefix):
            _request(client, path)
        payload = json.loads(redis.lpop(prefix + "email-probe"))
        expected = {
            "reset": "accounts.send_password_reset",
            "signup-existing": "accounts.send_account_exists",
        }.get(path, "accounts.send_verification_email")
        assert payload["headers"]["task"] == expected
        args, kwargs, _ = json.loads(base64.b64decode(payload["body"]))
        assert args[0].endswith("@example.test")
        assert (len(args) == 1) if path == "signup-existing" else (len(args) == 2 and args[1])
        assert payload["headers"]["argsrepr"] == "(<redacted>)"
    finally:
        # The prefix is owned by this test; do not clear anyone else's database.
        keys = list(redis.scan_iter(match=prefix + "*"))
        if keys:
            redis.delete(*keys)
        redis.close()


def test_publish_failure_logs_no_exception_message(monkeypatch, caplog):
    secret = "redis://user:private-password@broker/2 raw-token church@example.test"
    def fail(*args, **kwargs):
        raise RuntimeError(secret)
    monkeypatch.setattr(send_verification_email_task, "apply_async", fail)
    with caplog.at_level(logging.ERROR):
        CeleryEmailSender().send_email_verification(type("User", (), {"email": "church@example.test"})(), "raw-token")
    assert "email delivery unconfirmed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text
    assert not any(record.exc_info for record in caplog.records)


def test_publish_failure_logging_is_bounded(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("private")
    monkeypatch.setattr(send_verification_email_task, "apply_async", fail)
    now = [100.0]
    monkeypatch.setattr(email_module.time, "monotonic", lambda: now[0])
    sender = CeleryEmailSender()
    user = type("User", (), {"email": "church@example.test"})()
    with caplog.at_level(logging.ERROR):
        for _ in range(100):
            sender.send_email_verification(user, "raw-token")
        assert len(caplog.records) == 1
        now[0] += 60
        sender.send_email_verification(user, "raw-token")
        assert len(caplog.records) == 2


def test_actual_environment_controls_transport_options():
    env = {**os.environ, "CELERY_BROKER_SOCKET_CONNECT_TIMEOUT": "0.07", "CELERY_BROKER_SOCKET_TIMEOUT": "0.09"}
    result = subprocess.run(
        [sys.executable, "-c", "import json; from selahcue_api.settings import CELERY_BROKER_TRANSPORT_OPTIONS; print(json.dumps(CELERY_BROKER_TRANSPORT_OPTIONS))"],
        env=env, capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(result.stdout) == {"socket_connect_timeout": 0.07, "socket_timeout": 0.09, "retry_on_timeout": False}


@pytest.mark.parametrize("option", ["socket_timeout=86400", "socket_connect_timeout=0", "retry_on_timeout=True", "%73ocket_timeout=0.5"])
def test_kombu_broker_url_queries_cannot_override_timeouts(monkeypatch, option):
    # Unlike Django RedisCache's from_url, Kombu parses these as unsupported connection
    # constructor keywords. Check the installed parser, including decoded names, without I/O.
    with publisher(monkeypatch, "redis://127.0.0.1:1/2?" + option) as app:
        with pytest.raises(TypeError):
            app.connection_for_write()


@pytest.mark.skipif(not os.getenv("CELERY_BROKER_URL"), reason="needs CI Redis broker")
def test_socket_limits_reach_real_redis_connection(monkeypatch):
    with publisher(monkeypatch, os.environ["CELERY_BROKER_URL"]) as app:
        with app.connection_for_write(transport_options={"max_retries": 0}) as connection:
            channel = connection.channel()
            try:
                kwargs = channel.client.connection_pool.connection_kwargs
                assert kwargs["socket_timeout"] == project_settings.CELERY_BROKER_SOCKET_TIMEOUT
                assert kwargs["socket_connect_timeout"] == project_settings.CELERY_BROKER_SOCKET_CONNECT_TIMEOUT
                assert kwargs["retry_on_timeout"] is False
                redis_connection = channel.client.connection_pool.get_connection()
                try:
                    assert redis_connection.retry._retries == 0
                finally:
                    channel.client.connection_pool.release(redis_connection)
            finally:
                channel.close()


@pytest.mark.parametrize("name", ["CELERY_BROKER_SOCKET_TIMEOUT", "CELERY_BROKER_SOCKET_CONNECT_TIMEOUT"])
@pytest.mark.parametrize("value,expected", [("0.05", 0.05), ("10", 10.0), ("", 0.5), ("  ", 0.5)])
def test_valid_broker_timeout_bounds(monkeypatch, name, value, expected):
    monkeypatch.setenv(name, value)
    assert project_settings._socket_timeout_seconds(name, "0.5") == expected


@pytest.mark.parametrize("name", ["CELERY_BROKER_SOCKET_TIMEOUT", "CELERY_BROKER_SOCKET_CONNECT_TIMEOUT"])
def test_invalid_broker_timeout_does_not_echo_accidental_secrets(monkeypatch, name):
    secret = "redis://private-user:private-password@broker/2"
    monkeypatch.setenv(name, secret)
    with pytest.raises(ImproperlyConfigured) as error:
        project_settings._socket_timeout_seconds(name, "0.5")
    assert name in str(error.value)
    assert secret not in str(error.value)



def _assert_production_result_shape(app):
    """Keep the unsafe production result defaults in the regression, rather than replacing
    Redis with memory or shortening the result timeout to mask accidental subscriptions."""
    assert isinstance(app.backend, RedisBackend)
    assert app.backend.connparams["socket_timeout"] == 120.0
    assert app.backend.connparams["socket_connect_timeout"] is None
    assert app.conf.task_ignore_result is False
    for name in (
        "accounts.send_verification_email", "accounts.send_password_reset",
        "accounts.send_account_exists", "accounts.sweep_expired_credentials",
    ):
        assert app.tasks[name].ignore_result is False, "per-publish scope must not alter task policy"
    assert app.conf.task_publish_retry is True


@needs_sigalrm
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("path", ["signup", "signup-existing", "resend", "reset"])
def test_redis_result_subscription_cannot_bypass_email_broker_bound(
    client, settings, monkeypatch, caplog, path
):
    settings.CACHES = {"default": project_settings._cache_config("", TIMEOUT, TIMEOUT)}
    broker, results = StalledRedis(), StalledRedis()
    try:
        budget = project_settings.CELERY_BROKER_SOCKET_TIMEOUT
        with publisher(monkeypatch, broker.url, result_backend=results.url) as app:
            _assert_production_result_shape(app)
            started = time.monotonic()
            with caplog.at_level(logging.ERROR), _watchdog(budget + 5):
                _request(client, path)
            elapsed = time.monotonic() - started
            print(f"Redis results + silent broker {path}: {elapsed:.3f}s; read timeout {budget}s")
            assert elapsed < budget + 3
            assert results.connections_after_settling(0) == 0, "email must not subscribe for unused results"
            assert broker.connections_after_settling(1) == 1
            assert app.backend.result_consumer.subscribed_to == set()
            _assert_production_result_shape(app)
        assert "email delivery unconfirmed" in caplog.text
        assert "example.test" not in caplog.text
    finally:
        broker.close()
        results.close()
        assert not broker._thread.is_alive() and not results._thread.is_alive()


@needs_sigalrm
@pytest.mark.skipif(not os.getenv("CELERY_BROKER_URL"), reason="needs CI Redis broker")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("path", ["signup", "signup-existing", "resend", "reset"])
def test_healthy_email_publish_ignores_only_its_unused_redis_results(
    client, settings, monkeypatch, path
):
    settings.CACHES = {"default": project_settings._cache_config("", TIMEOUT, TIMEOUT)}
    prefix = f"email-result-probe-{uuid.uuid4().hex}:"
    url = os.environ["CELERY_BROKER_URL"]
    redis = Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    results = StalledRedis()
    try:
        with publisher(monkeypatch, url, prefix=prefix, result_backend=results.url) as app:
            _assert_production_result_shape(app)
            with _watchdog(project_settings.CELERY_BROKER_SOCKET_TIMEOUT + 5):
                _request(client, path)
            assert results.connections_after_settling(0) == 0
            assert app.backend.result_consumer.subscribed_to == set()
            _assert_production_result_shape(app)
        payload = json.loads(redis.lpop(prefix + "email-probe"))
        expected = {
            "reset": "accounts.send_password_reset",
            "signup-existing": "accounts.send_account_exists",
        }.get(path, "accounts.send_verification_email")
        assert payload["headers"]["task"] == expected
        assert payload["headers"]["ignore_result"] is True
        assert payload["headers"]["argsrepr"] == "(<redacted>)"
        assert payload["headers"]["kwargsrepr"] == "{}"
        args, kwargs, _ = json.loads(base64.b64decode(payload["body"]))
        assert args[0].endswith("@example.test")
        assert len(args) == (1 if path == "signup-existing" else 2)
        assert kwargs == {}
    finally:
        results.close()
        assert not results._thread.is_alive()
        keys = list(redis.scan_iter(match=prefix + "*"))
        if keys:
            redis.delete(*keys)
        redis.close()
