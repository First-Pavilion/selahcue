"""Sustained-denial alerting in `apps.throttling.guards` (86akcn92k, F3).

DEC-013's wording was "the oracle repeats indefinitely and alerts no one." 86akcmfd4 fixed the
first clause only — `enforce_budget` raised `RATE_LIMITED` with zero logging. A sustained run of
denials on a reset scope is the highest-signal indicator that someone is doing exactly what
DEC-013 feared, so `spend_budget` (the one place every caller — `within_budget`,
`enforce_budget`, `enforce_budget_reporting_outage` — routes through) now reports it, at most
once per scope per suppression interval, mirroring `apps.throttling.services`'s own
`_STORE_ERROR_LOG_INTERVAL_SECONDS` pattern (same file already forbids unbounded logging).

Unit-level, no DB: `spend_budget` needs only Django's cache, not a request or the ORM.
"""

import logging

import pytest
from django.core.cache import cache

from selahcue_api.apps.throttling import guards


@pytest.fixture(autouse=True)
def _fresh_state():
    cache.clear()
    guards._reset_denial_log_suppression()


def test_a_sustained_denial_run_logs_exactly_one_warning(caplog):
    """THE positive control: many denials in a row against ONE scope must produce exactly ONE
    log line, not one per denial (which would be the unbounded-log problem this repo forbids)
    and not zero (which was the pre-fix behaviour — DEC-013's unmet half)."""
    with caplog.at_level(logging.WARNING, logger=guards.logger.name):
        # Exhaust the budget, then keep hammering it well past the limit.
        for _ in range(50):
            guards.spend_budget("verify_email_ip", "203.0.113.9", "SOME_SETTING_NAME", (1, 3600))

    records = [r for r in caplog.records if "is refusing requests" in r.getMessage()]
    assert len(records) == 1, f"expected one suppressed report, got {len(records)}"
    assert records[0].levelno == logging.WARNING
    assert "verify_email_ip" in records[0].getMessage()


def test_calls_within_budget_never_log_a_denial_warning(caplog):
    """The benign case must stay silent — a warning on every ALLOWED spend would defeat the
    "sustained denial is the signal" framing and just be noise."""
    with caplog.at_level(logging.WARNING, logger=guards.logger.name):
        for _ in range(5):
            guards.spend_budget("verify_email_ip", "198.51.100.7", "SOME_SETTING_NAME", (10, 3600))

    records = [r for r in caplog.records if "is refusing requests" in r.getMessage()]
    assert records == [], "no denial occurred, so no denial warning should have been logged"


def test_denial_warnings_are_independent_per_scope():
    """Two DIFFERENT scopes being hammered at once must each get their own report — a single
    shared suppression flag would silence the second scope's first, actionable report."""
    logged = []

    class _Recorder(logging.Handler):
        def emit(self, record):
            if "is refusing requests" in record.getMessage():
                logged.append(record.getMessage())

    handler = _Recorder()
    guards.logger.addHandler(handler)
    guards.logger.setLevel(logging.WARNING)
    try:
        guards.spend_budget("scope_a", "id", "SOME_SETTING_NAME", (0, 3600))
        guards.spend_budget("scope_b", "id", "SOME_SETTING_NAME", (0, 3600))
    finally:
        guards.logger.removeHandler(handler)

    assert any("scope_a" in m for m in logged)
    assert any("scope_b" in m for m in logged)
    assert len(logged) == 2, f"expected one report per scope, got {logged}"


def test_a_denied_call_still_returns_denied_after_logging():
    """The alerting must be a side effect, not a behaviour change: `spend_budget`'s return
    value is unaffected by whether it logged."""
    from selahcue_api.apps.throttling.services import BudgetOutcome

    outcome = guards.spend_budget("verify_email_ip", "203.0.113.9", "SOME_SETTING_NAME", (0, 3600))
    assert outcome is BudgetOutcome.DENIED
