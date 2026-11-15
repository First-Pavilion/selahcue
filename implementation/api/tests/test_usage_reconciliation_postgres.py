"""PostgreSQL authority and real broker/process coverage for Task 6."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
import subprocess
import sys
from threading import Barrier
import time
from uuid import uuid4

import pytest
from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from provider_helpers import DEEPGRAM, cold_provider_cache, identity, provider_mounts
from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.providers import sessions
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.models import ProviderCredential, SttMintAttempt
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.health import read_provider_usage_health
from selahcue_api.apps.usage.models import (
    ProviderUsageHealthState, ProviderUsageRecord, ScopeUsageHealth, UsageObservedInterval,
    UsageOutbox, UsageReservation, UsageWeek, UsageWork,
)
from selahcue_api.apps.usage.observation_contracts import ScanPurpose
from selahcue_api.apps.usage.observations import ingest_observations
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.reconciliation import reconcile_org
from selahcue_api.apps.usage.usage_tasks import bounded_transaction, ensure_work, publish_work

from test_cloud_grant_postgres import command, deps, token_for
from test_effective_org_plan import church, device, licence
from test_provider_observations import (
    COVERAGE, NOW, begin_scan, clock, complete, dg_data, page_claim, parse_dg, request, task_for, usage_runtime,
)
from test_provider_reservation_binding import active_mapping, retire
from test_usage_reconciliation import MONDAY, observed, reserve_stt

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def postgres():
    if connection.vendor != "postgresql":
        assert "postgres" not in os.getenv("SQL_ENGINE", ""), "PostgreSQL runner silently used the wrong engine"
        pytest.skip("Requires PostgreSQL row locks, constraints, and actual process connections")


@pytest.mark.parametrize("only_partial", (False, True))
@pytest.mark.parametrize("duration", (60, None))
def test_reordered_health_evaluations_cannot_retreat(usage_runtime, clock, only_partial, duration):
    usage_runtime()
    g1 = begin_scan(DEEPGRAM, purpose=ScanPurpose.HEALTH)
    older = task_for(g1, NOW)
    ingest_observations(parse_dg(dg_data()), g1.pk, claim=page_claim(older, NOW))

    newer_at = NOW + timedelta(minutes=1)
    clock.value = newer_at
    interval = UTCInterval(newer_at - timedelta(days=1), newer_at)
    g2 = begin_scan(DEEPGRAM, interval=interval, start=newer_at, purpose=ScanPurpose.HEALTH)
    newer = task_for(g2, newer_at)
    entry = request("newer-health-fact", completed=False, duration=duration, created=NOW + timedelta(seconds=30))
    page = parse_dg(dg_data([entry] * (100 if only_partial else 1)), interval=interval)
    going = Barrier(2, timeout=5)

    def publish_newer():
        close_old_connections()
        try:
            going.wait()
            ingest_observations(page, g2.pk, claim=page_claim(newer, newer_at))
            if not only_partial:
                complete(g2, DEEPGRAM, newer_at)
        finally:
            connections.close_all()

    # The two scans use different connections and durable generations. Force
    # the older completion to apply after the newer relevant page or scan.
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(publish_newer)
        going.wait()
        work.result(timeout=10)
    expected = ScopeUsageHealth.objects.values().get(scope_id=g1.scope_id)
    clock.value = NOW + timedelta(minutes=2)
    complete(g1, DEEPGRAM, clock())
    actual = ScopeUsageHealth.objects.values().get(scope_id=g1.scope_id)
    for field in ("complete_scan_id", "selected_generation", "selected_window_end", "applied_facts_revision", "valid_until", "state"):
        assert actual[field] == expected[field]
    assert (actual["clear_min_generation"], actual["clear_min_window_end"]) == (g2.generation, newer_at)
    health = read_provider_usage_health("deepgram", clock())
    want = "BLOCKED" if duration is not None and not only_partial else "UNRESOLVED"
    assert health.status == want


def test_empty_observed_initial_window_reaches_first_real_admission(usage_runtime, clock, provider_mounts):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    token, _ = token_for(install)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), org=org, mapping=mapping.mapping_id)
    observed(scan, [], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    provider_mounts("web", stt=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    result, http = sessions._issue_stt_session(
        token, command(), deps(clock=clock, readiness_reader=read_stt_readiness),
    )
    assert http.status_code == 200
    assert result.decision.state == "ISSUED"
    assert UsageReservation.objects.get(pk=result.decision.reservation_id).week.stt_seconds_settled == 0


def test_ingest_while_org_is_locked_then_reserve_and_reconcile_serialize(usage_runtime, clock):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="concurrent-meter"))
    usage_runtime()
    interval = UTCInterval(MONDAY, NOW)
    scan = begin_scan(DEEPGRAM, interval=interval, org=org, mapping=mapping.mapping_id)
    work = task_for(scan, NOW)
    claim = page_claim(work, NOW)
    page = parse_dg(dg_data([request("correction", key="concurrent-meter", duration=600)]), interval=interval)
    started = Barrier(2, timeout=5)

    def ingest():
        close_old_connections()
        try:
            started.wait()
            return ingest_observations(page, scan.pk, claim=claim)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            CustomerOrg.objects.select_for_update(no_key=True).get(pk=org.pk)
            concurrent = pool.submit(ingest)
            started.wait()
            assert concurrent.result(timeout=5).inserted == 1
    complete(scan, DEEPGRAM)

    lock_order = Barrier(3, timeout=5)

    def run(operation):
        close_old_connections()
        try:
            lock_order.wait()
            return operation()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reserved = pool.submit(run, lambda: reserve_stt(install, mapping.mapping_id, NOW))
        reconciled = pool.submit(run, lambda: reconcile_org(org.pk, NOW, clock=clock))
        lock_order.wait()
        assert reserved.result(timeout=10).state == "RESERVED"
        assert reconciled.result(timeout=10).blocked_reason is None
    week = UsageWeek.objects.get(org=org)
    assert (week.stt_seconds_settled, week.reservations.count()) == (600, 1)


def test_postgres_observation_guard_protects_clearing_and_append_only_facts(usage_runtime, clock):
    usage_runtime()
    scan = begin_scan(DEEPGRAM)
    observed(scan, [request(completed=False, duration=60)], NOW)
    health = ScopeUsageHealth.objects.get(scope_id=scan.scope_id)
    assert health.clear_min_generation > 0
    with pytest.raises(IntegrityError), transaction.atomic():
        ScopeUsageHealth.objects.filter(pk=health.pk).update(clear_min_window_end=NOW-timedelta(seconds=1))
    with pytest.raises(IntegrityError), transaction.atomic():
        ProviderUsageRecord.objects.all().update(event_at=NOW)
    with pytest.raises(IntegrityError), transaction.atomic():
        UsageObservedInterval.objects.filter(scan=scan).update(scan_started_at=NOW+timedelta(seconds=1))


def test_task6_additive_migration_preserves_promoted_schema_and_restores_every_leaf(usage_runtime, clock):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    reserved = reserve_stt(install, mapping.mapping_id, NOW)
    from test_effective_org_plan import context
    from selahcue_api.apps.usage.services import reserve
    from test_usage_weeks import start

    unbound = reserve(context(install, "stt", NOW), start(), NOW)
    retire(mapping)
    frontier = MigrationExecutor(connection).loader.graph.leaf_nodes()
    before_usage = ("selahcue_usage", "0002_provider_binding")
    prior = [node for node in frontier if node[0] != "selahcue_usage"] + [before_usage]
    try:
        executor = MigrationExecutor(connection)
        assert executor.loader.graph.nodes[("selahcue_usage", "0003_provider_observations")].dependencies == [
            ("selahcue_accounts", "0004_remove_customerorg_device_limit"),
            ("selahcue_audit", "0001_initial"),
            ("selahcue_providers", "0002_provisioning_attempts"),
            before_usage,
        ]
        executor.migrate(prior)
        historic = executor.loader.project_state(prior).apps.get_model("selahcue_usage", "UsageReservation")
        assert historic.objects.get(pk=reserved.pk).provider_mapping_id == mapping.mapping_id
        assert historic.objects.get(pk=unbound.reservation_id).provider_mapping_id is None
    finally:
        MigrationExecutor(connection).migrate(frontier)
    assert set(MigrationExecutor(connection).loader.graph.leaf_nodes()) == set(frontier)
    assert ProviderUsageHealthState.objects.filter(state="UNRESOLVED").count() == 2
    assert ProviderCredential.objects.get(pk=mapping.mapping_id).state == "RETIRED"
    assert SttMintAttempt.objects.count() == 0


def _worker_environment(prefix):
    db = connection.settings_dict
    environ = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "ENVIRONMENT": "dev", "DJANGO_SETTINGS_MODULE": "selahcue_api.settings",
        "SQL_ENGINE": db["ENGINE"], "SQL_DATABASE": db["NAME"], "SQL_USER": db["USER"],
        "SQL_PASSWORD": db["PASSWORD"], "SQL_HOST": db["HOST"], "SQL_PORT": str(db["PORT"]),
        "CELERY_BROKER_URL": os.environ["CELERY_BROKER_URL"],
        "SELAHCUE_PROVIDER_PROCESS_ROLE": "usage",
        "SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE": settings.SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE,
        "SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE": settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE,
        "SELAHCUE_TEST_USAGE_PREFIX": prefix, "PYTHONDONTWRITEBYTECODE": "1",
    }
    return environ


def test_real_redis_publish_and_worker_ack_preserve_terminal_usage_work(usage_runtime, tmp_path):
    from celery import Celery

    broker = os.getenv("CELERY_BROKER_URL")
    if not broker or not broker.startswith(("redis://", "rediss://")):
        pytest.skip("Requires the configured disposable Redis broker")
    usage_runtime()
    code = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'selahcue_api.settings')
django.setup()
from selahcue_api.celery import app
app.conf.broker_transport_options = {
    **app.conf.broker_transport_options, 'global_keyprefix': os.environ['SELAHCUE_TEST_USAGE_PREFIX'],
}
app.worker_main(['worker', '-P', 'solo', '-Q', 'provider_usage', '--without-gossip',
                 '--without-mingle', '--without-heartbeat', '--loglevel=INFO'])
"""
    prefix = f"task6-{uuid4().hex}:"
    broker_app = Celery("task6-test", broker=broker)
    broker_app.conf.broker_transport_options = {
        **settings.CELERY_BROKER_TRANSPORT_OPTIONS, "global_keyprefix": prefix,
    }
    with bounded_transaction():
        attempt = uuid4()
        work = ensure_work("MINT_RECOVERY", str(attempt), NOW, attempt_id=attempt)
    env = _worker_environment(prefix)
    with (tmp_path / "worker.log").open("w+") as output:
        process = subprocess.Popen(
            [sys.executable, "-c", code], stdout=output, stderr=subprocess.STDOUT, env=env,
        )
        try:
            publish_work(work.pk, app=broker_app)
            expires = time.monotonic() + 15
            while time.monotonic() < expires and process.poll() is None:
                if UsageWork.objects.filter(pk=work.pk, state="COMPLETE").exists():
                    break
                time.sleep(0.03)
            output.seek(0)
            log = output.read()
            assert "usage.recover_mint" in log
            assert UsageWork.objects.get(pk=work.pk).state == "COMPLETE", log[-2500:]
            assert UsageOutbox.objects.get(work=work).state == "ACKED"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_dispatched_mint_recovery_preserves_original_metadata_and_audits_once(usage_runtime, clock):
    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.providers.stt_recovery import recover_abandoned_stt_mint

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    reservation = reserve_stt(install, mapping.mapping_id, NOW)
    attempt = SttMintAttempt.objects.create(
        reservation=reservation, owner_nonce=uuid4(), request_receipt_id=uuid4(), trigger_token_pk=1,
        mapping_revision=2, state="PREPARED", prepared_at=NOW, dispatch_not_after=NOW + timedelta(seconds=3),
    )
    attempt.state, attempt.dispatched_at = "DISPATCHED", NOW + timedelta(seconds=1)
    attempt.save(update_fields=("state", "dispatched_at"))
    usage_runtime()
    cutoff = attempt.dispatch_not_after + timedelta(seconds=4)
    clock.value = cutoff - timedelta(microseconds=1)
    assert not recover_abandoned_stt_mint(attempt.pk, clock=clock).changed
    clock.value = cutoff
    assert recover_abandoned_stt_mint(attempt.pk, clock=clock).state == "recovered_unknown"
    assert not recover_abandoned_stt_mint(attempt.pk, clock=clock).changed
    attempt.refresh_from_db()
    reservation.refresh_from_db()
    assert attempt.owner_nonce and attempt.audit_event_id is None
    assert attempt.state == "UNKNOWN"
    assert attempt.failure_code == "provider_outcome_unproven"
    assert (reservation.state, reservation.last_minted_at) == ("RESERVED", None)
    assert AuditEvent.objects.filter(action="cloud.stt.mint_recovery", actor_kind="service").count() == 1


def test_concurrent_history_sweeps_share_older_and_retained_windows(usage_runtime, clock):
    from selahcue_api.apps.usage.models import UsageScan
    from selahcue_api.apps.usage.usage_tasks import _schedule_periodic
    from test_usage_reconciliation import seed_old_unresolved_days

    usage_runtime()
    scope, (first_day, _) = seed_old_unresolved_days(clock)
    barrier = Barrier(3, timeout=5)

    def schedule():
        close_old_connections()
        try:
            barrier.wait()
            _schedule_periodic(scope, "HISTORY_SCOPE", clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        contenders = [pool.submit(schedule) for _ in range(2)]
        barrier.wait()
        for contender in contenders:
            contender.result(timeout=10)

    pending = UsageScan.objects.filter(scope=scope, purpose="HISTORY", state="PARTIAL")
    retained_day = (NOW - timedelta(weeks=104)).replace(hour=0)
    assert sorted(pending.values_list("requested_start", flat=True)) == [first_day, retained_day]
    assert UsageWork.objects.filter(kind="SCAN", scan__in=pending, state="PENDING").count() == 2
    scope.refresh_from_db()
    assert scope.history_recovery_pending == first_day
    assert scope.history_recovery_after is None
