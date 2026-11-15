"""Finite quota-query allowance; this is not a general SQL read-only parser."""
from contextlib import nullcontext
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID

import pytest

from selahcue_api.apps.usage import readiness

# Independently pinned from the reviewed read-only PostgreSQL query at 57d586ec.
# Do not derive this allowance from live production SQL: a changed CTE needs review.
_POSTGRES_READINESS_SHA256 = "ecc5841285739a051250dce9a33b6d635ed9fe435865ddc542bc40db9f4b722c"


def quota_read_only_query(execute, sql, params, many, context):
    """Check parameterized SQL, without exposing statement values in failures."""
    __tracebackhide__ = True
    upper = " ".join(sql.upper().split())
    shape = "SELECT" if upper.startswith("SELECT") else "WITH" if upper.startswith("WITH") else "OTHER"
    locked = any(clause in upper for clause in (
        "FOR UPDATE", "FOR NO KEY UPDATE", "FOR SHARE", "FOR KEY SHARE",
    ))
    fingerprint = sha256(sql.encode()).hexdigest()
    if locked or (shape != "SELECT" and fingerprint != _POSTGRES_READINESS_SHA256):
        raise AssertionError(
            f"Unexpected quota SQL: shape={shape}, locking={locked}, sha256={fingerprint}"
        )
    return execute(sql, params, many, context)


def test_quota_guard_accepts_production_postgresql_readiness_statement(monkeypatch):
    """Exercise the real reader's emitted SQL with an inert cursor, not a PG service."""
    calls = []
    mapping_id = UUID(int=1)

    def execute(sql, params):
        def record(*args):
            calls.append(args)
        return quota_read_only_query(record, sql, params, False, {})

    cursor = SimpleNamespace(execute=execute, fetchone=lambda: (None, None, None, "coverage_missing"))
    monkeypatch.setattr(readiness, "connection", SimpleNamespace(
        vendor="postgresql", cursor=lambda: nullcontext(cursor),
        ops=SimpleNamespace(adapt_unknown_value=lambda value: value),
    ))
    result = readiness.read_stt_readiness(
        org_id=1, mapping_id=mapping_id, at=datetime(2026, 11, 15, 12, tzinfo=UTC),
    )
    assert result.status == "not_initialized"
    assert len(calls) == 1
    assert calls[0][1][0] == "deepgram"
    assert calls[0][1][2:] == [1, mapping_id]


def test_quota_guard_preserves_select_execution_and_parameters():
    params, context, result = ["synthetic-private-value"], {}, object()
    calls = []

    def execute(*args):
        calls.append(args)
        return result

    assert quota_read_only_query(execute, "SELECT %s", params, False, context) is result
    assert calls == [("SELECT %s", params, False, context)]


@pytest.mark.parametrize("sql", [
    "WITH removed AS (DELETE FROM quota_history RETURNING id) SELECT id FROM removed",
    "WITH ids AS (SELECT 1) UPDATE quota_history SET units = 0",
    "WITH unexpected AS (SELECT 1) SELECT * FROM unexpected",
    "SELECT id FROM quota_history FOR UPDATE",
    "SELECT id FROM quota_history FOR NO KEY UPDATE",
    "SELECT id FROM quota_history FOR SHARE",
    "SELECT id FROM quota_history FOR KEY SHARE",
], ids=["dml-cte", "dml-after-cte", "unknown-read-cte", "update-lock", "no-key-lock", "share-lock", "key-share-lock"])
def test_quota_guard_refuses_unapproved_ctes_and_locks_before_execution(sql):
    def unexpected_execution(*args):
        pytest.fail("Rejected query reached execution")

    with pytest.raises(AssertionError, match="Unexpected quota SQL: shape="):
        quota_read_only_query(unexpected_execution, sql, [], False, {})


def test_quota_guard_diagnostic_omits_query_text_and_parameters():
    marker = "synthetic-private-value"
    sql = f"WITH rejected AS (SELECT '{marker}') SELECT * FROM rejected"
    with pytest.raises(AssertionError) as caught:
        quota_read_only_query(None, sql, [marker], False, {})
    message = str(caught.value)
    assert marker not in message and sql not in message
    assert message == f"Unexpected quota SQL: shape=WITH, locking=False, sha256={sha256(sql.encode()).hexdigest()}"


@pytest.mark.django_db
def test_quota_guard_intercepts_database_execution():
    from django.db import connection

    with connection.execute_wrapper(quota_read_only_query), connection.cursor() as cursor:
        cursor.execute("SELECT %s", [17])
        assert cursor.fetchone() == (17,)
        # This valid read-only query would succeed on either supported backend;
        # refusal proves the wrapper, rather than the driver, enforces the pin.
        with pytest.raises(AssertionError, match="shape=WITH"):
            cursor.execute("WITH unexpected AS (SELECT 1) SELECT * FROM unexpected")
