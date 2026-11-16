from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from queue import Queue
from threading import Barrier
from time import monotonic, sleep

import pytest
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from selahcue_api.apps.usage.contracts import ReservationRejected
from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.usage.models import UsageReservation, UsageWeek
from selahcue_api.apps.usage.services import remaining, reserve

from test_effective_org_plan import NOW, church, context, device, licence
from test_usage_weeks import reserve_note, start


@pytest.mark.django_db(transaction=True)
def test_two_devices_racing_for_final_slice_admit_exactly_one():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks.")
    org = church()
    key = licence(org)
    left, right = device(key), device(key)
    for _ in range(3):
        reserve(context(left, "stt"), start(), NOW)
    contexts = [context(inst, "stt") for inst in (left, right)]
    barrier = Barrier(3, timeout=10)
    pids = Queue()

    def compete(ctx):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])
            barrier.wait()
            reserve(ctx, start(), NOW)
            return "reserved"
        except ReservationRejected as error:
            return error.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as workers:
        with transaction.atomic():
            CustomerOrg.objects.select_for_update(no_key=True).get(pk=org.pk)
            claims = [workers.submit(compete, ctx) for ctx in contexts]
            worker_pids = [pids.get(timeout=10) for _ in contexts]
            barrier.wait()
            deadline = monotonic() + 8
            while True:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT count(*) FROM unnest(%s::int[]) AS worker(pid) "
                        "WHERE cardinality(pg_blocking_pids(worker.pid)) > 0",
                        [worker_pids],
                    )
                    blocked = cursor.fetchone()[0]
                if blocked == 2:
                    break
                assert monotonic() < deadline, "Both reserve calls must contend for the org lock"
                sleep(0.01)
        results = [claim.result(timeout=10) for claim in claims]
    assert sorted(results) == ["QUOTA_EXHAUSTED", "reserved"]
    assert UsageReservation.objects.filter(org=org, meter="stt").count() == 4


@pytest.mark.django_db
@pytest.mark.parametrize("plan,stt_count,notes_count", [("FREE", 4, 1), ("PRO", 16, 10)])
def test_query_cost_includes_plan_resolution_without_read_locks(plan, stt_count, notes_count):
    org = church()
    inst = device(licence(org, plan))
    request_context = context(inst, "stt")
    for _ in range(stt_count - 1):
        reserve(request_context, start(), NOW)
    for _ in range(notes_count):
        reserve_note(inst)
    with CaptureQueriesContext(connection) as writes:
        reserve(request_context, start(), NOW)
    with CaptureQueriesContext(connection) as reads:
        snapshots = remaining(org, NOW)
    assert sum(row.remaining for row in snapshots) == 0
    assert UsageReservation.objects.filter(org=org).count() == stt_count + notes_count
    assert all(query["sql"].lstrip().upper().startswith("SELECT") for query in reads)
    lock_clauses = ("FOR UPDATE", "FOR NO KEY UPDATE", "FOR SHARE", "FOR KEY SHARE")
    assert not any(
        clause in query["sql"].upper()
        for query in reads
        for clause in lock_clauses
    )
    assert (len(reads), len(writes)) == (7, 15)


@pytest.mark.django_db
def test_unbound_foundation_explicitly_refuses_provider_mapping():
    from uuid import uuid4

    org = church()
    inst = device(licence(org))
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve(replace(context(inst, "stt"), provider_mapping_id=uuid4()), start(), NOW)
    assert not UsageReservation.objects.filter(org=org).exists()


@pytest.mark.django_db
def test_postgresql_excludes_overlapping_utc_bounds_per_org():
    from datetime import timedelta

    if connection.vendor != "postgresql":
        pytest.skip("Requires the PostgreSQL GiST exclusion constraint.")
    org = church()
    reserve_note(device(licence(org)))
    week = UsageWeek.objects.get(org=org)
    fields = {
        "week_start_local": week.week_start_local + timedelta(days=7),
        "tz_name": "Pacific/Kiritimati",
        "starts_at": week.starts_at + timedelta(days=6),
        "ends_at": week.ends_at + timedelta(days=6),
        "counted_from": week.starts_at + timedelta(days=6),
        "admissions_start_at": week.starts_at + timedelta(days=6),
        "high_water_rank": 1,
        "opening_stt_seconds_limit": 1200,
        "opening_notes_limit": 1,
        "high_water_stt_seconds_limit": 1200,
        "high_water_notes_limit": 1,
    }
    with pytest.raises(IntegrityError), transaction.atomic():
        UsageWeek.objects.create(org=org, **fields)
    UsageWeek.objects.create(org=church(pk=2**63 - 1), **fields)
