"""A STALLED cache store must degrade the throttle, not block the request (17tnw2b1wrx).

The throttle fails OPEN when its store is unreachable: `evaluate_budget` turns a store
exception into a permit. That covers a store that is DOWN — a refused connection raises at
once. It did not cover a store that is UP but WEDGED (a failing node, a network partition,
memory pressure): one that accepts the TCP connection and never answers. redis-py has no socket
timeout by default, so `recv()` blocked forever, no exception was ever raised, and fail-open
never got the chance to run. Every request that touches a throttle — native sign-in, activation,
licence refresh, the password-reset and verification mutations — then held a web worker for as
long as Redis stayed wedged (this repo configures no request timeout of its own), which can turn
a cache problem into a full API outage.

Nothing modelled a stall before this file: every other throttle test injects a store that RAISES
(`_BrokenStore`, `FakeStore(raise_on_use=True)`), which is the one failure mode that already
worked. Here the store is a real TCP listener that accepts and stays silent, in front of the real
`RedisCache` backend and the real redis-py client, so the timeout has to come from the shipped
`CACHES` configuration or the test blocks.

HOW A BLOCKED CALL IS REPORTED, NOT HUNG. A call that never returns would hang the whole suite,
so each stalled call runs under a SIGALRM watchdog. The watchdog raises `_Blocked`, a
BaseException on purpose: `evaluate_budget` catches `Exception`, so an `Exception` subclass
would be swallowed as "store down" and a limiter that blocked for the whole watchdog interval
would look like a fail-open that merely took a while.

WHAT IS NOT COVERED HERE. `socket_connect_timeout` (a SYN that is never answered) cannot be
modelled deterministically on loopback; it is asserted by configuration — that the value reaches
redis-py's connection kwargs — rather than by behaviour. The read timeout is the one the
reported hang exercised.
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from django.core.cache import cache, caches
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from selahcue_api import settings as project_settings
from selahcue_api.apps.accounts import services as account_services
from selahcue_api.apps.throttling import services as throttle_services
from selahcue_api.apps.throttling.guards import spend_budget
from selahcue_api.apps.throttling.services import BudgetOutcome

# Only the tests that run a stalled call under the SIGALRM watchdog need POSIX. The configuration
# and environment-variable tests below it are plain assertions and must run everywhere.
needs_sigalrm = pytest.mark.skipif(
    not hasattr(signal, "setitimer"), reason="the stall watchdog needs SIGALRM (POSIX only)"
)

API_ROOT = Path(__file__).resolve().parent.parent

# Short enough to keep the suite quick, long enough that a loaded CI runner is not mistaken for
# a stall. The assertions are relative to it, not to the shipped default.
TEST_TIMEOUT = 0.2
# Generous on purpose: this guards "does not block", not "is fast". A blocked call is infinite,
# so any finite bound separates the two; a tight one would only buy flakes on a busy machine.
JITTER_ALLOWANCE = 3.0
WATCHDOG_SECONDS = 20


# --- the stalled store ----------------------------------------------------------------------
class StalledRedis:
    """Completes the TCP handshake and then says nothing, ever.

    That is what a wedged Redis looks like from the client's side: `connect()` succeeds, the
    command is written, and the reply never comes. Bounded: it holds only the connections the
    test itself opens, and `close()` shuts every one of them, which also wakes any client still
    blocked in `recv()` (it sees EOF) so a failing test cannot leak a stuck thread.
    """

    def __init__(self):
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(0.1)
        self.url = f"redis://127.0.0.1:{self._listener.getsockname()[1]}/1"
        self._held = []
        self._lock = threading.Lock()
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                self._held.append(connection)

    @property
    def connections_accepted(self) -> int:
        with self._lock:
            return len(self._held)

    def connections_after_settling(self, expected: int, within: float = 2.0) -> int:
        """The accepted-connection count, read after the accept thread has had a chance to catch
        up. The client finishes `connect()` before this thread records it, so a bare read straight
        after a call can lag on a starved runner and read low with no real fault. Poll (up to
        `within` seconds) until `expected` have been recorded, then give a would-be EXTRA
        connection — a retry — a moment to be recorded too, so `== expected` still catches one."""
        deadline = time.monotonic() + within
        while self.connections_accepted < expected and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        return self.connections_accepted

    def close(self):
        self._stopping.set()
        self._thread.join(timeout=2)
        self._listener.close()
        with self._lock:
            for connection in self._held:
                try:
                    connection.close()
                except OSError:
                    pass
            self._held.clear()


@pytest.fixture
def stalled_redis():
    server = StalledRedis()
    try:
        yield server
    finally:
        server.close()


class _Blocked(BaseException):
    """Raised by the watchdog. A BaseException so `evaluate_budget`'s `except Exception` cannot
    swallow it and turn a blocked limiter into a slow fail-open."""


@contextmanager
def _watchdog(seconds: float = WATCHDOG_SECONDS):
    """Fail the test, rather than hang the suite, if the body is still blocked after `seconds`."""

    def _fire(signum, frame):
        raise _Blocked(f"still blocked after {seconds}s")

    previous = signal.signal(signal.SIGALRM, _fire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    except _Blocked:
        pytest.fail(
            f"the call was still blocked after {seconds}s: the stalled cache store was never "
            "given up on, so the throttle never got to fail open"
        )
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _point_cache_at(settings, server: StalledRedis, timeout: float = TEST_TIMEOUT):
    """Swap the default cache for the REAL Redis backend aimed at the stalled listener, built by
    the same function `settings.py` uses for `CACHES` — so removing the timeouts from the shipped
    configuration removes them here too. `settings.CACHES` assignment makes Django drop its
    cache-handler cache, so `django.core.cache.cache` picks the new backend up."""
    settings.CACHES = {"default": project_settings._cache_config(server.url, timeout, timeout)}


@pytest.fixture(autouse=True)
def _quiet_limiter_state(monkeypatch):
    """The outage warning is rate-limited via module state; forget it so each test sees the
    first one. Local-memory cache for everything that runs before a test points at the stall."""
    monkeypatch.setattr(throttle_services, "_last_store_error_log", float("-inf"))
    cache.clear()


# --- the configuration itself ---------------------------------------------------------------
def test_the_redis_cache_is_configured_with_bounded_socket_timeouts():
    config = project_settings._cache_config(
        "redis://example.invalid:6379/1",
        project_settings.CACHE_SOCKET_CONNECT_TIMEOUT,
        project_settings.CACHE_SOCKET_TIMEOUT,
    )
    options = config["OPTIONS"]
    assert config["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    # Both present and inside the documented range. Asserted against the range the validator
    # enforces, not a number of this test's own: this reads the runner's environment, and a
    # legitimate override (`CACHE_SOCKET_TIMEOUT=10`) must not fail it.
    low = project_settings._SOCKET_TIMEOUT_MIN_SECONDS
    high = project_settings._SOCKET_TIMEOUT_MAX_SECONDS
    for name in ("socket_connect_timeout", "socket_timeout"):
        assert low <= options[name] <= high, (
            f"{name} must lie in [{low}, {high}] seconds, got {options[name]!r}"
        )


def test_the_timeouts_reach_the_redis_client_not_just_the_settings_dict(settings):
    """A key that Django does not forward to `redis.ConnectionPool` would sit in `CACHES` doing
    nothing while looking configured. Inspect the pool the backend actually builds (no network:
    a pool connects lazily)."""
    settings.CACHES = {
        "default": project_settings._cache_config("redis://example.invalid:6379/1", 0.7, 0.9)
    }
    kwargs = caches["default"]._cache.get_client(write=True).connection_pool.connection_kwargs
    assert kwargs["socket_connect_timeout"] == 0.7
    assert kwargs["socket_timeout"] == 0.9


def test_without_a_cache_url_the_local_memory_cache_is_kept_and_needs_no_timeouts():
    config = project_settings._cache_config("", 0.5, 0.5)
    assert config["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
    assert "OPTIONS" not in config


# --- the environment variables ---------------------------------------------------------------
def _settings_in_subprocess(**env):
    """Import the REAL settings module in a clean interpreter with `env` applied — the only way
    to see the environment variables take effect, since `settings.py` reads them at import."""
    child_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CACHE_URL", "CACHE_SOCKET_TIMEOUT", "CACHE_SOCKET_CONNECT_TIMEOUT"}
    }
    child_env.update({"DJANGO_SETTINGS_MODULE": "selahcue_api.settings", "ENVIRONMENT": "dev"})
    child_env.update(env)
    code = (
        "import json; from django.conf import settings; "
        "print(json.dumps(settings.CACHES['default']))"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=API_ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_timeouts_default_to_a_short_bound_and_are_tunable_by_environment():
    default = _settings_in_subprocess(CACHE_URL="redis://example.invalid:6379/1")
    assert default.returncode == 0, default.stderr
    default_options = json.loads(default.stdout)["OPTIONS"]
    assert default_options == {"socket_connect_timeout": 0.5, "socket_timeout": 0.5}

    tuned = _settings_in_subprocess(
        CACHE_URL="redis://example.invalid:6379/1",
        CACHE_SOCKET_CONNECT_TIMEOUT="1.5",
        CACHE_SOCKET_TIMEOUT="2",
    )
    assert tuned.returncode == 0, tuned.stderr
    assert json.loads(tuned.stdout)["OPTIONS"] == {
        "socket_connect_timeout": 1.5,
        "socket_timeout": 2.0,
    }


@pytest.mark.parametrize("name", ["CACHE_SOCKET_TIMEOUT", "CACHE_SOCKET_CONNECT_TIMEOUT"])
def test_a_blank_timeout_means_the_default_not_zero(name):
    """Compose and Coolify both produce set-but-blank variables (`VAR=` or `${VAR:-}`); that
    must read as "not configured", never as a zero or a crash."""
    result = _settings_in_subprocess(CACHE_URL="redis://example.invalid:6379/1", **{name: "  "})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["OPTIONS"] == {
        "socket_connect_timeout": 0.5,
        "socket_timeout": 0.5,
    }


TIMEOUT_VARIABLES = ["CACHE_SOCKET_TIMEOUT", "CACHE_SOCKET_CONNECT_TIMEOUT"]

# Every one of these boots on a naive "positive and finite" check and then defeats the control,
# or is not a number at all. Each was reproduced against a healthy Redis before the range existed
# (PR #186 review round 1), in the three families below.
OUT_OF_RANGE_OR_NOT_A_NUMBER = [
    # Not a usable timeout at all.
    "0", "-1", "-inf", "nan", "inf", "1e400", "soon",
    # Too big: `1e10` / `1e308` make Python's socket layer raise OverflowError (not an OSError)
    # on every call, so the throttle fails open forever while the app boots fine; `86400` is a
    # 24-hour wait and `500` is milliseconds typed as seconds — the original bug again.
    "10.01", "500", "86400", "1e10", "1e308",
    # Too small: indistinguishable from `0` over a real network, where working calls time out.
    "0.049", "0.001", "1e-9",
]


@pytest.mark.parametrize("name", TIMEOUT_VARIABLES)
@pytest.mark.parametrize("bad", OUT_OF_RANGE_OR_NOT_A_NUMBER)
def test_a_timeout_that_would_switch_the_protection_off_is_refused(monkeypatch, name, bad):
    """A knob that can silently remove the protection — or break every cache call — has to fail
    at startup, naming the variable, where a deploy catches it, rather than under load. In-process
    (the validator is a pure function of the environment) so the whole list stays cheap."""
    monkeypatch.setenv(name, bad)
    with pytest.raises(ImproperlyConfigured, match=name):
        project_settings._socket_timeout_seconds(name, "0.5")


@pytest.mark.parametrize("name", TIMEOUT_VARIABLES)
@pytest.mark.parametrize(
    ("accepted", "expected"),
    [("0.05", 0.05), ("0.5", 0.5), (" 2 ", 2.0), ("10", 10.0)],
)
def test_the_range_boundaries_themselves_are_accepted(monkeypatch, name, accepted, expected):
    """Both ends are inclusive: the floor (`0.05`) and the ceiling (`10`) are legitimate values,
    and the pair just outside them (`0.049`, `10.01`) is in the refused list above."""
    monkeypatch.setenv(name, accepted)
    assert project_settings._socket_timeout_seconds(name, "0.5") == expected


@pytest.mark.parametrize("name", TIMEOUT_VARIABLES)
@pytest.mark.parametrize("bad", ["0", "1e10", "0.001", "500"])
def test_a_bad_timeout_stops_the_real_settings_module_from_loading(name, bad):
    """The same refusal through the real settings import, in a clean interpreter: what a deploy
    actually sees. With NO `CACHE_URL` — the variables are validated even when no Redis cache is
    configured, so a typo cannot hide until the day Redis is switched on."""
    result = _settings_in_subprocess(**{name: bad})
    assert result.returncode != 0, f"{name}={bad!r} was accepted: {result.stdout}"
    assert "ImproperlyConfigured" in result.stderr
    assert name in result.stderr


# --- the throttle against a store that accepts and never answers ----------------------------
@needs_sigalrm
def test_the_limiter_fails_open_after_about_the_timeout_when_the_store_stalls(
    settings, stalled_redis, caplog
):
    _point_cache_at(settings, stalled_redis)

    with caplog.at_level(logging.WARNING, logger=throttle_services.logger.name):
        with _watchdog():
            started = time.monotonic()
            outcome = spend_budget("stall_probe", "x", "SELAHCUE_THROTTLE_ACTIVATION", (10, 60))
            elapsed = time.monotonic() - started

    assert outcome is BudgetOutcome.STORE_UNAVAILABLE, "a stalled store must read as a down one"
    # Positive control: the stub really was in the path, and the call really waited on it. A
    # result that came back instantly would mean the cache never reached the stalled listener
    # and everything below proves nothing.
    assert elapsed >= TEST_TIMEOUT * 0.9, f"returned in {elapsed:.3f}s without waiting on the stall"
    assert elapsed < TEST_TIMEOUT + JITTER_ALLOWANCE, f"took {elapsed:.3f}s"
    # EXACTLY one connection: the stall costs one timeout, not a timeout per retry. redis-py 6.4
    # retries nothing by default; a later release that starts retrying would reconnect here, and
    # this is where that shows up (elapsed alone could not tell it from jitter).
    assert stalled_redis.connections_after_settling(1) == 1

    # The outage warning behaves as it does for a down store: one line, naming the cause.
    warnings = [r for r in caplog.records if "rate-limit store unavailable" in r.getMessage()]
    assert len(warnings) == 1
    assert "TimeoutError" in warnings[0].getMessage()


@needs_sigalrm
def test_repeated_stalled_calls_still_log_one_outage_warning_not_one_each(
    settings, stalled_redis, caplog
):
    """Each call now costs a timeout, so a stalled store at real traffic would otherwise turn
    into the unbounded log the repo forbids — the once-a-minute suppression must hold."""
    _point_cache_at(settings, stalled_redis)

    with caplog.at_level(logging.WARNING, logger=throttle_services.logger.name):
        with _watchdog():
            outcomes = [
                spend_budget("stall_probe", "x", "SELAHCUE_THROTTLE_ACTIVATION", (10, 60))
                for _ in range(4)
            ]

    assert outcomes == [BudgetOutcome.STORE_UNAVAILABLE] * 4
    assert len([r for r in caplog.records if "rate-limit store unavailable" in r.getMessage()]) == 1


ACTIVATION_BODY = json.dumps(
    {
        "idempotency_key": "stall-probe-1",
        "license_key": "nope",
        "device_fingerprint": "fp",
        "platform": "macos",
    }
)


@needs_sigalrm
@pytest.mark.django_db
def test_the_activation_throttle_permits_the_request_when_the_store_stalls(
    client, settings, stalled_redis
):
    """Through the real `/v1/activations` view and its `@throttle` decorator. With a working
    store a (2, 60) budget refuses the third call (`test_activation_returns_429_over_the_limit`);
    here the store cannot count at all, so every call must be PERMITTED — reaching the view and
    failing on the bogus key (404), never 429 and never a hang."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_THROTTLE_ACTIVATION = (2, 60)
    _point_cache_at(settings, stalled_redis)

    with _watchdog():
        timings = []
        statuses = []
        for _ in range(3):
            started = time.monotonic()
            response = client.post(
                "/v1/activations", data=ACTIVATION_BODY, content_type="application/json"
            )
            timings.append(time.monotonic() - started)
            statuses.append(response.status_code)

    assert statuses == [404, 404, 404], statuses
    assert all(TEST_TIMEOUT * 0.9 <= t < TEST_TIMEOUT + JITTER_ALLOWANCE for t in timings), timings
    # One budget per request, one connection per budget (a timed-out connection is dropped and
    # the next call reconnects), and nothing retried: exactly three.
    assert stalled_redis.connections_after_settling(3) == 3


REQUEST_RESET = "mutation Req($e: String!) { requestPasswordReset(email: $e) { accepted } }"


def _post_account(client, query, variables):
    # The reset email is dispatched from `transaction.on_commit`, which `django_db`'s rollback
    # never runs unless captured (same shape as tests/test_password_reset_throttle.py).
    with TestCase.captureOnCommitCallbacks(execute=True):
        return client.post(
            "/graphql/account",
            data=json.dumps({"query": query, "variables": variables}),
            content_type="application/json",
        )


def _post_each(client, query, emails):
    """One request per address, timed. Returns (responses, seconds-per-request)."""
    responses, timings = [], []
    for email in emails:
        started = time.monotonic()
        responses.append(_post_account(client, query, {"e": email}))
        timings.append(time.monotonic() - started)
    return responses, timings


def _assert_every_request_accepted(responses, field):
    """Every caller is told the same thing: no error, no outage-shaped answer, no oracle."""
    for response in responses:
        payload = json.loads(response.content)
        assert not payload.get("errors"), payload
        assert payload["data"][field]["accepted"] is True


def _assert_reported_once(caplog):
    """The degradation is reported exactly as it is for a down store: the shared limiter reports
    the store being unavailable once, and the send ceiling reports the skipped send once."""
    skipped = [r for r in caplog.records if "limiter unavailable" in r.getMessage()]
    assert len(skipped) == 1, "the degradation must be reported, once per interval"
    outage = [r for r in caplog.records if "rate-limit store unavailable" in r.getMessage()]
    assert len(outage) == 1


class _CapturingSender(account_services.EmailSender):
    def __init__(self):
        self.verify_tokens = []
        self.reset_tokens = []

    def send_email_verification(self, user, raw_token):
        self.verify_tokens.append(raw_token)

    def send_password_reset(self, user, raw_token):
        self.reset_tokens.append(raw_token)


def _account(sender, email, idem, *, verified):
    """A real customer account built through the signup service (not hand-rolled rows, so its
    email fingerprint is the one the code under test computes). Left unverified it is the shape
    `resendVerificationEmail` sends to; verified, the shape `requestPasswordReset` mints for."""
    with TestCase.captureOnCommitCallbacks(execute=True):
        account_services.register_customer_user(
            account_services.RegisterCustomerUserData(
                idempotency_key=idem,
                email=email,
                password="correct-horse-battery-1",
                org_name="Stall Chapel",
                country="NG",
            )
        )
    if verified:
        account_services.verify_email(sender.verify_tokens[-1])
    return email


@needs_sigalrm
@pytest.mark.django_db
def test_password_reset_degrades_to_its_outage_ceiling_when_the_store_stalls(
    client, settings, stalled_redis, caplog
):
    """The same property `test_a_limiter_outage_bounds_the_reset_send_without_denying_the_
    response` pins for a store that RAISES, now for one that STALLS: every request is answered
    (accepted:true, no error, no oracle), the mail volume is bounded by the degraded-send
    ceiling instead of being unmetered, and the skip is reported once."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_RESET_SEND_DEGRADED_CEILING = (1, 60)
    sender = _CapturingSender()
    account_services.set_email_sender(sender)
    account_services._reset_floor_overrun_reporting()
    account_services._reset_reset_send_degraded_window()
    try:
        # Accounts are built while the cache is still local memory: signup is not what is under
        # test, and it would otherwise pay for the stall too.
        emails = [
            _account(sender, f"stall{i}@budget.example", f"stall-reset-{i}", verified=True)
            for i in range(3)
        ]
        sender.reset_tokens.clear()
        _point_cache_at(settings, stalled_redis)

        with caplog.at_level(logging.WARNING):
            with _watchdog():
                responses, timings = _post_each(client, REQUEST_RESET, emails)

        _assert_every_request_accepted(responses, "requestPasswordReset")
        assert len(sender.reset_tokens) == 1, (
            "a stalled limiter store must bound the reset send with the degraded ceiling, "
            f"not hand out unmetered mail (sent {len(sender.reset_tokens)})"
        )
        _assert_reported_once(caplog)
        # THREE budgets are spent per request (global, per-IP, per-address), each failing open
        # after one timeout on its own fresh connection: 3 requests x 3 budgets = 9 connections,
        # and nothing retried. This is what pins the "about three timeouts" cost the deployment
        # docs quote for this mutation — one budget alone would satisfy a bare `>= timeout`.
        assert stalled_redis.connections_after_settling(9) == 9
        assert all(t >= 3 * 0.9 * TEST_TIMEOUT for t in timings), timings
        assert all(t < 3 * TEST_TIMEOUT + JITTER_ALLOWANCE + 2 for t in timings), timings
    finally:
        account_services.set_email_sender(account_services.EmailSender())


RESEND_VERIFICATION = (
    "mutation Resend($e: String!) { resendVerificationEmail(email: $e) { accepted } }"
)


@needs_sigalrm
@pytest.mark.django_db
def test_resend_verification_degrades_to_its_outage_ceiling_when_the_store_stalls(
    client, settings, stalled_redis, caplog
):
    """The resend mutation's own degraded-send ceiling (`_claim_degraded_send`, a different
    counter from the reset path's) behaves for a stalled store as for a down one: every response
    is accepted:true, only the ceiling's worth of mail leaves, and the skip is reported once."""
    settings.SELAHCUE_TRUSTED_PROXY_COUNT = 0
    settings.SELAHCUE_RESEND_DEGRADED_SEND_CEILING = (1, 60)
    # Measure the stall, not the constant-time padding that would otherwise absorb it.
    settings.ACCOUNT_RESEND_MIN_SECONDS = 0.0
    sender = _CapturingSender()
    account_services.set_email_sender(sender)
    account_services._reset_floor_overrun_reporting()
    account_services._reset_degraded_send_window()
    try:
        emails = [
            _account(sender, f"resend{i}@budget.example", f"stall-resend-{i}", verified=False)
            for i in range(3)
        ]
        sender.verify_tokens.clear()  # signup's own verification mail is not what is counted
        _point_cache_at(settings, stalled_redis)

        with caplog.at_level(logging.WARNING):
            with _watchdog():
                responses, timings = _post_each(client, RESEND_VERIFICATION, emails)

        _assert_every_request_accepted(responses, "resendVerificationEmail")
        assert len(sender.verify_tokens) == 1, (
            "a stalled limiter store must bound the resend with the degraded ceiling, "
            f"not hand out unmetered mail (sent {len(sender.verify_tokens)})"
        )
        _assert_reported_once(caplog)
        # Same shape as the reset mutation: three budgets per request, one connection each.
        assert stalled_redis.connections_after_settling(9) == 9
        assert all(t >= 3 * 0.9 * TEST_TIMEOUT for t in timings), timings
        assert all(t < 3 * TEST_TIMEOUT + JITTER_ALLOWANCE + 2 for t in timings), timings
    finally:
        account_services.set_email_sender(account_services.EmailSender())


# --- the shipped settings, end to end, in a clean interpreter ------------------------------
def test_the_shipped_settings_fail_open_against_a_stalled_store_from_the_environment(stalled_redis):
    """Environment variables -> `settings.CACHES` -> real redis-py -> a store that never
    replies -> the real `spend_budget`. This is the one test that does not go through the
    builder function: it boots the actual settings module the way production does, so a change
    that stops the module applying its own timeouts cannot hide behind the builder still being
    correct. A child that blocks is killed by `subprocess` and reported as a failure."""
    code = (
        "import django, time; django.setup(); "
        "from selahcue_api.apps.throttling.guards import spend_budget; "
        "t = time.monotonic(); "
        "outcome = spend_budget('stall_env', 'x', 'SELAHCUE_THROTTLE_ACTIVATION', (10, 60)); "
        "print(outcome.value, round(time.monotonic() - t, 3))"
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"CACHE_URL", "CACHE_SOCKET_TIMEOUT", "CACHE_SOCKET_CONNECT_TIMEOUT"}
    }
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "selahcue_api.settings",
            "ENVIRONMENT": "dev",
            "CACHE_URL": stalled_redis.url,
            "CACHE_SOCKET_TIMEOUT": str(TEST_TIMEOUT),
            "CACHE_SOCKET_CONNECT_TIMEOUT": str(TEST_TIMEOUT),
        }
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=API_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=WATCHDOG_SECONDS,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"the child was still blocked after {WATCHDOG_SECONDS}s: the shipped settings put "
            "no timeout on the cache connection"
        )
    assert result.returncode == 0, result.stderr
    outcome, elapsed = result.stdout.split()
    assert outcome == "STORE_UNAVAILABLE"
    assert float(elapsed) < TEST_TIMEOUT + JITTER_ALLOWANCE
    assert stalled_redis.connections_after_settling(1) == 1


# --- the other half of the contract: nothing changes while Redis is healthy ------------------
@pytest.mark.skipif(
    not os.getenv("CACHE_URL"),
    reason="needs a real Redis (CACHE_URL) — the `api` CI job provides one",
)
def test_a_healthy_redis_still_counts_and_denies_with_the_timeouts_configured(settings):
    """The timeouts are a ceiling on a WEDGED call, not a change to a working one. Against a real
    Redis, with the shipped timeouts, the limiter allows up to its limit and then denies — the
    same arithmetic `test_allows_up_to_the_limit_then_denies` pins on a fake store."""
    settings.CACHES = {
        "default": project_settings._cache_config(
            os.environ["CACHE_URL"],
            project_settings.CACHE_SOCKET_CONNECT_TIMEOUT,
            project_settings.CACHE_SOCKET_TIMEOUT,
        )
    }
    settings.SELAHCUE_THROTTLE_ACTIVATION = (3, 60)
    # Unique per run: no `cache.clear()` against a shared Redis just to isolate this.
    identity = f"healthy-{uuid.uuid4().hex}"
    outcomes = [
        spend_budget("healthy_probe", identity, "SELAHCUE_THROTTLE_ACTIVATION", (3, 60))
        for _ in range(5)
    ]
    assert outcomes == [
        BudgetOutcome.ALLOWED,
        BudgetOutcome.ALLOWED,
        BudgetOutcome.ALLOWED,
        BudgetOutcome.DENIED,
        BudgetOutcome.DENIED,
    ]
