"""Bounded representative Task 6 qualification on the existing hosted PostgreSQL runner."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from threading import Barrier, Timer
import time
from uuid import UUID

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from provider_helpers import DEEPGRAM, cold_provider_cache, identity, policy_rows, provider_mounts, write_mount
from selahcue_api.apps.providers.adapters import deepgram_usage
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningAuditContext
from selahcue_api.apps.providers.models import ProviderCapacityPool, ScopePolicyEpoch
from selahcue_api.apps.providers.policy_publication import canonical, digest, publish_provider_policy
from selahcue_api.apps.usage import health
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.models import (
    ProviderUsageRecord, ProviderUsageVersion, ScopeUsageHealth, SttScopeReadiness,
    UsageObservedInterval, UsageOutbox, UsagePageClaim, UsageRecentPlan, UsageReservation, UsageScan, UsageWeek, UsageWork,
)
from selahcue_api.apps.usage.observation_contracts import ObservedCoverage, RetentionKind
from selahcue_api.apps.usage.observations import attribute_scope_batch, ingest_observations, safe_digest
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.reconciliation import _weekly_totals, reconcile_org
from selahcue_api.apps.usage.retention import DETAIL_AGE, _candidates
from selahcue_api.apps.usage.recent import _mapping_batch
from selahcue_api.apps.usage.scans import enroll_scope, finish_scan
from selahcue_api.apps.usage.usage_tasks import _schedule_periodic, bounded_transaction
from test_cloud_grant_postgres import token_for
from test_effective_org_plan import church, device, licence
from test_provider_observations import NOW, begin_scan, clock, dg_data, page_claim, task_for
from test_provider_reservation_binding import active_mapping
from test_usage_reconciliation import MONDAY

pytestmark = pytest.mark.django_db(transaction=True)
SEED = "task6-retained-64-8-104x8-plus-32-history-250-hot-v1"


def _runtime(role, provider_mounts, settings, tmp_path, scopes):
    provider_mounts(role, capable=True)
    policy = policy_rows(capable=True)
    original = policy["deepgram"][0]
    policy["deepgram"] = [{**original, "project_id": scope.parent_scope_id} for scope in scopes]
    settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "load-policy", policy)
    settings.SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE = write_mount(tmp_path, "load-usage", {
        "schema_version": 1,
        "deepgram": [{"project_id": scope.parent_scope_id, "api_key": "synthetic-load"} for scope in scopes],
        "openai": [{"organization_id": "synthetic-organization", "admin_api_key": "synthetic-openai-load"}],
    })
    settings.SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE = write_mount(tmp_path, "load-provisioner", {
        "schema_version": 1,
        "deepgram": [{"project_id": scope.parent_scope_id, "keys_write_api_key": "synthetic-provisioner"} for scope in scopes],
        "openai": [{"organization_id": "synthetic-organization", "admin_api_key": "synthetic-openai-provisioner"}],
    })
    initialize_provider_runtime(entrypoint="operator" if role == "provisioner" else "celery_worker")


def _complete_scope(scope, start, end, capture, *, health_input=False):
    now = capture
    pool = ProviderCapacityPool.objects.get(provider="deepgram", parent_scope_id=scope.parent_scope_id)
    with bounded_transaction():
        _provider, row, evaluation = enroll_scope("deepgram", scope.parent_scope_id, now)
        generation = row.next_scan_generation
        row.next_scan_generation += 1
        row.save(update_fields=("next_scan_generation",))
        scan = UsageScan.objects.create(
            scope=row, purpose="RECENT" if health_input else "HISTORY", profile="DG_LISTEN_V1",
            generation=generation, requested_start=start, requested_end=end, started_at=capture, finished_at=capture,
            created_at=now, updated_at=now, state="COMPLETE", page_ordinal=1, terminal_page_seen=True,
            policy_epoch=pool.current_epoch, policy_digest=pool.current_epoch.digest,
        )
        page = UsagePageClaim.objects.create(
            scan=scan, ordinal=0, attempts=1, state="APPLIED", terminal=True, dispatched_at=capture,
            completed_at=capture, first_receipt_at=capture, response_digest="1" * 64, created_at=now, updated_at=now,
        )
        UsageObservedInterval.objects.create(
            scan=scan, scope=row, start=start, end=end, profile=scan.profile,
            scan_started_at=capture, scan_finished_at=capture, created_at=now,
        )
        if health_input:
            ScopeUsageHealth.objects.filter(pk=evaluation.pk).update(
                state="CURRENT", reason=None, applied_facts_revision=evaluation.facts_revision,
                policy_epoch=pool.current_epoch, policy_digest=pool.current_epoch.digest, complete_scan=scan,
                window_start=end - timedelta(days=1), window_end=end, scan_started_at=capture,
                valid_until=capture + timedelta(seconds=300), observed_total=Decimal(0),
                selected_generation=generation, selected_window_end=end,
            )
            SttScopeReadiness.objects.create(
                scope=row, latest_complete_scan=scan, scan_started_at=capture, scan_finished_at=capture,
                observed_through=end, valid_until=capture + timedelta(seconds=300), created_at=now, updated_at=now,
            )
        else:
            work = UsageWork.objects.create(
                kind="SCAN", scope=row, scan=scan, subject_key=str(scan.pk), state="COMPLETE", due_at=now,
                started_at=now, finished_at=now, created_at=now, updated_at=now,
            )
            UsageOutbox.objects.create(
                work=work, generation=1, state="ACKED", publish_attempts=1, available_at=now,
                acked_at=now, sent_at=now, created_at=now, updated_at=now,
            )
    return scan, page


def _historical_parent(template, label):
    pool = ProviderCapacityPool.objects.create(
        provider="deepgram", parent_scope_id=label, budget=template.budget, created_at=NOW, updated_at=NOW,
    )
    policy = {**template.current_epoch.policy, "parent_scope_id": label}
    policy_digest = digest(canonical(policy))
    pool.current_epoch = ScopePolicyEpoch.objects.create(
        pool=pool, policy=policy, digest=policy_digest, publication_digest=policy_digest,
        cleanup_authorized=False, published_by="load-fixture", request_id=UUID(int=999), evidence_ref="load-fixture",
        created_at=NOW,
    )
    pool.save(update_fields=("current_epoch",))
    return ProviderScope("deepgram", label)


def _seed_org(org, mapping, fresh, expired, serial):
    rows = UsageWeek.objects.bulk_create([
        UsageWeek(
            org=org, tz_name="UTC", week_start_local=(MONDAY - timedelta(weeks=offset)).date(),
            starts_at=MONDAY - timedelta(weeks=offset), ends_at=MONDAY - timedelta(weeks=offset - 1),
            admissions_start_at=MONDAY - timedelta(weeks=offset), counted_from=MONDAY - timedelta(weeks=offset),
            high_water_rank=1, opening_stt_seconds_limit=1200, opening_notes_limit=1,
            high_water_stt_seconds_limit=1200, high_water_notes_limit=1, stt_seconds_settled=1,
        ) for offset in range(104)
    ])
    facts, attributes = [], []
    for week in rows:
        scan, page = fresh if week.starts_at == MONDAY else expired
        for ordinal in range(8):
            event = week.starts_at + timedelta(days=2, seconds=ordinal)
            identifier = f"load-{serial}-{week.week_start_local.isoformat()}-{ordinal}"
            identity_key = {"request_id": identifier, "provider": "deepgram"}
            natural = {
                "request_id": identifier, "project_id": scan.scope.parent_scope_id,
                "api_key_id": f"load-key-{serial}",
                "created_at": event.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            }
            facts.append(ProviderUsageRecord(
                scope_id=scan.scope_id, provider="deepgram", kind="DG_REQUEST", identity_key=safe_digest("usage-identity-v1", identity_key),
                natural_identity=natural, first_seen_at=scan.started_at, event_at=event, retention_at=event,
                mapping_id=mapping.mapping_id, attribution="EXACT_KEY", placed_week=week, request_id=identifier,
                returned_project_id=scan.scope.parent_scope_id, returned_api_key_id=f"load-key-{serial}",
                accepted_generation=scan.generation, created_at=scan.started_at, updated_at=scan.started_at,
            ))
            attributes.append((scan, page))
    ProviderUsageRecord.objects.bulk_create(facts, batch_size=500)
    versions = []
    for fact, (scan, page) in zip(facts, attributes, strict=True):
        for revision, amount in ((1, "0.1"), (2, "0.125")):
            dto = {
                "request_id": fact.request_id, "project_id": fact.returned_project_id,
                "api_key_id": fact.returned_api_key_id, "created_at": fact.natural_identity["created_at"],
                "completion": "COMPLETE",
                "completed_at": (fact.event_at + timedelta(seconds=1)).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                "duration_seconds": amount, "response_code": 200,
            }
            versions.append(ProviderUsageVersion(
                record=fact, revision=revision, normalized_digest=safe_digest("usage-normalization-v1", dto),
                safe_facts=dto, source_scan=scan, source_page=page, source_generation=scan.generation,
                created_at=scan.started_at, first_receipt_at=scan.started_at, source_scope_id=scan.scope_id,
                source_interval_start=scan.requested_start, source_interval_end=scan.requested_end,
                source_scan_started_at=scan.started_at, completion="COMPLETE",
                completed_at=fact.event_at + timedelta(seconds=1), duration_seconds=Decimal(amount), response_code=200,
            ))
    ProviderUsageVersion.objects.bulk_create(versions, batch_size=500)
    for row, version in zip(facts, versions[1::2], strict=True):
        row.current_version = version
    ProviderUsageRecord.objects.bulk_update(facts, ("current_version",), batch_size=500)


def _plans(call):
    queries = []

    def capture(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith(("SELECT", "WITH")):
            queries.append((sql, params))
        return execute(sql, params, many, context)

    with connection.execute_wrapper(capture):
        result = call()
    plans = []
    for sql, params in queries:
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
            plans.append(cursor.fetchone()[0])
    return result, plans


def _latencies(kind, samples, outcomes, locks=(), queries=0):
    ordered = sorted(samples)
    return {
        "kind": kind, "count": len(samples), "outcomes": outcomes, "locks": locks, "queries": queries,
        "p50_ms": ordered[len(ordered)//2], "p95_ms": ordered[int(0.95 * (len(ordered)-1))],
        "max_ms": ordered[-1],
    }


LOCAL_PARTICIPANTS = (
    (0, "reader"), (1, "reader"), (2, "reader"), (3, "reader"),
    (6, "reconcile"), (7, "ingest"),
)


@contextmanager
def _capture_operation_queries():
    """Capture one nonoverlapping operation on this participant's connection."""
    queries_log = connection.queries_log
    queries_log.clear()
    with CaptureQueriesContext(connection) as statements:
        yield statements
    # At capacity we cannot distinguish an exact count from overwritten entries.
    if len(queries_log) == queries_log.maxlen:
        raise AssertionError(f"SQL measurement reached the query log capacity ({queries_log.maxlen})")


def _sample_admissions(submit_once, until, *, monotonic=time.monotonic, sleep=time.sleep, granted=None):
    samples, outcomes, query_count = [], {}, 0
    while monotonic() < until and len(samples) < 500:
        start = monotonic()
        with _capture_operation_queries() as statements:
            result = submit_once()
        query_count += len(statements)
        name = result if isinstance(result, str) else "GRANTED"
        outcomes[name] = outcomes.get(name, 0) + 1
        if name == "GRANTED" and granted is not None:
            granted()
        samples.append(round((monotonic() - start) * 1000, 3))
        sleep(0.05)
    return _latencies("admit", samples, outcomes, queries=query_count)


def _collect_locals(operation, release, *, timeout):
    barrier = Barrier(len(LOCAL_PARTICIPANTS), timeout=timeout)

    def participant(index, role):
        barrier.wait()
        result = operation(index, role)
        assert result["kind"] == role and result["count"] > 0
        return result

    with ThreadPoolExecutor(max_workers=len(LOCAL_PARTICIPANTS)) as executor:
        measurements = [executor.submit(participant, index, role) for index, role in LOCAL_PARTICIPANTS]
        release()
        return [f.result(timeout=timeout) for f in measurements]


def run_web_admissions():
    """Separate initialized web runtime for two real admission connections."""
    from selahcue_api.apps.devices.models import DeviceToken
    from test_cloud_grant_postgres import command, deps, submit

    cfg = json.loads(Path(os.environ["TASK6_LOAD_CONTROL"]).read_text())
    initialize_provider_runtime(entrypoint="wsgi")
    ready, go = Path(cfg["ready"]), Path(cfg["go"])
    ready.touch()
    start_limit = time.monotonic() + 15
    while not go.exists():
        if time.monotonic() >= start_limit:
            raise TimeoutError("No synchronized load start")
        time.sleep(0.01)
    at = datetime.fromisoformat(cfg["at"])

    def admit(token_id):
        _cap_connection()
        token = DeviceToken.objects.get(pk=token_id)
        try:
            return _sample_admissions(
                lambda: submit(token, command(), deps(clock=lambda: at, readiness_reader=read_stt_readiness)),
                time.monotonic() + cfg["duration"], granted=Path(cfg["grant"]).touch,
            )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(admit, cfg["tokens"]))
    Path(cfg["result"]).write_text(json.dumps(result))


def _cap_connection():
    with connection.cursor() as cursor:
        cursor.execute("SET statement_timeout = '10s'; SET lock_timeout = '2s'")


def _web_load(at, duration, tokens, tmp_path, settings):
    db = connection.settings_dict
    path = tmp_path / ("web-" + str(at.second))
    path.mkdir()
    controls = path / "controls.json"
    fields = {
        "at": at.isoformat(), "duration": duration, "tokens": tokens,
        "ready": str(path / "ready"), "go": str(path / "go"), "result": str(path / "result"), "grant": str(path / "grant"),
    }
    controls.write_text(json.dumps(fields))
    env = {
        "PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(__file__).parent.absolute()), "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "dev", "DJANGO_SETTINGS_MODULE": "selahcue_api.settings", "SQL_ENGINE": db["ENGINE"],
        "SQL_DATABASE": db["NAME"], "SQL_USER": db["USER"], "SQL_PASSWORD": db["PASSWORD"],
        "SQL_HOST": db["HOST"], "SQL_PORT": str(db["PORT"]), "SELAHCUE_PROVIDER_PROCESS_ROLE": "web",
        "PGCONNECT_TIMEOUT": "5", "PGOPTIONS": "-c statement_timeout=10000 -c lock_timeout=2000",
        "SELAHCUE_CLOUD_STT_ENABLED": "1",
        "SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE": settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE,
        "SELAHCUE_PROVIDER_KEYRING_FILE": settings.SELAHCUE_PROVIDER_KEYRING_FILE,
        "TASK6_LOAD_CONTROL": str(controls),
    }
    return env, fields, path / "web.log"


def _mixed_round(orgs, mapping_rows, tokens, at, duration, tmp_path, settings, clock):
    """Eight separate connections with bounded measurements and deterministic roles."""
    clock.value = at
    interval = UTCInterval(MONDAY, at)
    secondary = ProviderScope("deepgram", "load-active-6")
    env, controls, logfile = _web_load(at, duration, tokens, tmp_path, settings)
    first_grant = Path(controls["grant"])
    connections.close_all()

    def operation(index, kind):
        close_old_connections()
        org, mapping = orgs[index % 8], mapping_rows[index % 8]
        samples, outcomes, locks = [], {}, []
        queries = writes = 0
        try:
            _cap_connection()
            deadline = time.monotonic() + duration
            if kind == "ingest":
                allow_first_grant = time.monotonic() + min(2, duration / 2)
                while not first_grant.exists() and time.monotonic() < allow_first_grant:
                    time.sleep(0.01)
            while time.monotonic() < deadline:
                started = time.monotonic()
                with _capture_operation_queries() as statements:
                    if kind == "reader" or kind == "ingest" and writes >= 5:
                        result = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=at)
                        outcome = result.status
                    elif kind == "reconcile":
                        result = reconcile_org(org.pk, at, clock=lambda: at)
                        outcome = "CORRECTED" if result.blocked_reason is None else result.blocked_reason.value
                    else:
                        # Repeated bounded writer operations on both a shared parent
                        # and the reconciler's other parent. All provider pages are inert.
                        parent = DEEPGRAM if writes % 2 == 0 else secondary
                        scan = begin_scan(parent, interval=interval, start=at)
                        work = task_for(scan, at)
                        page = deepgram_usage._parse_page(dg_data(), parent, interval, None)
                        ingest_observations(page, scan.pk, claim=page_claim(work, at))
                        finish_scan(scan.pk, ObservedCoverage(scan.pk, parent, interval, at, at, True))
                        attribute_scope_batch(scan.scope_id, after=None, limit=20, clock=lambda: at)
                        writes += 1
                        outcome = "APPLIED"
                queries += len(statements)
                samples.append(round((time.monotonic() - started) * 1000, 3))
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
                if index == 0 and len(samples) % 50 == 1:
                    with connection.cursor() as cursor:
                        cursor.execute("""SELECT count(*), count(*) FILTER (WHERE cardinality(pg_blocking_pids(pid)) > 0)
                            FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend'""")
                        locks.append(cursor.fetchone())
                if len(samples) >= 1000:
                    time.sleep(max(0, deadline - time.monotonic()))
                    break
                time.sleep(0.02)
            return _latencies(kind, samples, outcomes, locks, queries)
        finally:
            connections.close_all()

    with logfile.open("w+") as logs:
        web = subprocess.Popen(
            [sys.executable, "-c",
             "import django; django.setup(); from test_usage_retained_history_load import run_web_admissions; run_web_admissions()"],
            env=env, stdout=logs, stderr=subprocess.STDOUT,
        )
        try:
            client_ready = time.monotonic() + 8
            while not Path(controls["ready"]).exists() and web.poll() is None and time.monotonic() < client_ready:
                time.sleep(0.02)
            if not Path(controls["ready"]).exists():
                logs.seek(0)
                pytest.fail(logs.read()[-3000:])
            result = _collect_locals(operation, Path(controls["go"]).touch, timeout=duration + 25)
            if web.wait(timeout=20) != 0:
                logs.seek(0)
                pytest.fail(logs.read()[-3000:])
            return result + json.loads(Path(controls["result"]).read_text())
        finally:
            if web.poll() is None:
                web.kill()
                web.wait(timeout=5)



def _emit(capsys, stage, values):
    with capsys.disabled():
        print("TASK6_RETAINED_HISTORY", stage, json.dumps(values, default=str), flush=True)


@pytest.fixture
def load_watchdog(capsys):
    if connection.vendor != "postgresql":
        pytest.skip("Requires the existing PostgreSQL retained-history runner")
    started = time.monotonic()

    def expired():
        os.write(2, b"TASK6_RETAINED_HISTORY hard-timeout 600s: aborting disposable test runner\n")
        os._exit(124)

    timer = Timer(600, expired)
    timer.daemon = True
    timer.start()
    try:
        _cap_connection()
        yield started
    finally:
        timer.cancel()
        connections.close_all()


def test_task6_bounded_retained_history_explain_and_concurrent_work(
    provider_mounts, settings, tmp_path, clock, capsys, load_watchdog,
):
    started = load_watchdog
    _emit(capsys, "start", {
        "seed": SEED, "seed_sha256": sha256(SEED.encode()).hexdigest(),
        "runtime": sys.version.split()[0], "postgres_version_num": connection.pg_version,
        "connection_roles": [role for _, role in LOCAL_PARTICIPANTS] + ["admit", "admit"],
    })
    scopes = [DEEPGRAM, *[ProviderScope("deepgram", f"load-active-{index}") for index in range(1, 8)]]
    hot = ProviderScope("deepgram", "load-hot-parent")
    _runtime("provisioner", provider_mounts, settings, tmp_path, (*scopes, hot))
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("load-fixture", UUID(int=920), "retained-history"),
        clock=lambda: NOW - timedelta(hours=2),
    )
    orgs = [church() for _ in range(64)]
    mapping_rows = [
        active_mapping(org, identity(scopes[index % 8], key=f"load-key-{index}"))
        for index, org in enumerate(orgs)
    ]
    tokens = [token_for(device(licence(orgs[index])))[0].pk for index in range(6)]
    template = ProviderCapacityPool.objects.get(provider="deepgram", parent_scope_id=DEEPGRAM.parent_scope_id)
    historical = [_historical_parent(template, f"load-history-{i}") for i in range(32)]
    hot_orgs = [church() for _ in range(250)]
    for index, org in enumerate(hot_orgs):
        active_mapping(org, identity(hot, key=f"hot-key-{index}"))
    _runtime("usage", provider_mounts, settings, tmp_path, (*scopes, hot))

    seeds = []
    for scope in scopes:
        expired = _complete_scope(scope, MONDAY - timedelta(weeks=103), MONDAY, MONDAY)
        fresh = _complete_scope(scope, MONDAY, NOW, NOW, health_input=True)
        seeds.append((fresh, expired))
    for scope in [*historical, hot]:
        _complete_scope(scope, MONDAY, NOW, NOW, health_input=True)
    for index, (org, mapping) in enumerate(zip(orgs, mapping_rows, strict=True)):
        assert time.monotonic() - started < 480
        _seed_org(org, mapping, *seeds[index % 8], index)
    from selahcue_api.apps.usage.models import UsageScope
    from test_provider_observations import request
    from test_usage_reconciliation import observed

    ancient = NOW - timedelta(weeks=105)
    old = begin_scan(DEEPGRAM, interval=UTCInterval(ancient - timedelta(days=1), ancient + timedelta(days=1)))
    observed(old, [
        request(f"load-ancient-{index}", completed=False, duration=None, created=ancient+timedelta(seconds=index))
        for index in range(2)
    ], NOW)
    assert UsageScope.objects.filter(provider="deepgram").count() == 41
    assert ProviderUsageRecord.objects.filter(issue="ANCIENT_FACT").count() == 2
    assert ProviderUsageRecord.objects.count() == 53250
    assert ProviderUsageVersion.objects.count() == 106498
    _emit(capsys, "seeded", {
        "orgs": 64, "weeks": 64 * 104, "records": 53250, "versions": 106498, "scopes": 41,
        "hot_orgs": len(hot_orgs), "ancient_unresolved": 2, "elapsed_s": time.monotonic() - started,
    })
    for org in orgs[:8]:
        assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    readiness, stt_plan = _plans(lambda: read_stt_readiness(org_id=orgs[0].pk, mapping_id=mapping_rows[0].mapping_id, at=NOW))
    provider, health_plan = _plans(lambda: health.read_provider_usage_health("deepgram", NOW))
    assert readiness.status == "current_observed" and provider.status == "CURRENT"
    assert len(stt_plan) == len(health_plan) == 1
    _emit(capsys, "reader_plans", {"stt": stt_plan, "health": health_plan})
    _, totals_plan = _plans(lambda: _weekly_totals(ProviderUsageRecord.objects.filter(mapping_id=mapping_rows[0].mapping_id)))
    _, population_plan = _plans(lambda: health._population(seeds[0][0][0].scope, NOW - timedelta(days=1), NOW))
    hot_scope = UsageScope.objects.get(provider="deepgram", parent_scope_id=hot.parent_scope_id)
    planning = UsageRecentPlan(scope=hot_scope, captured_at=NOW, cutoff=NOW)
    _, recent_plan = _plans(lambda: _mapping_batch(planning, 100))
    retention = {
        kind.value: _plans(lambda: list(_candidates(
            kind, NOW - (DETAIL_AGE if kind.value in ("PAGE_DETAIL", "SUPERSEDED_VERSION", "TERMINAL_SCAN_WORK")
                         else timedelta(weeks=104)),
        ).order_by("pk").values_list("pk", flat=True)[:100]))[1]
        for kind in RetentionKind
    }
    _emit(capsys, "writer_plans", {
        "health_window": population_plan, "totals": totals_plan, "recent": recent_plan, "retention": retention,
    })
    for index, elapsed in enumerate((5, 30, 30)):
        at = NOW + timedelta(seconds=index + 1)
        clock.value = at
        for org in orgs[:8]:
            assert reconcile_org(org.pk, at, clock=clock).blocked_reason is None
        batch = _mixed_round(orgs, mapping_rows, tokens[2*index:2*index+2], at, elapsed, tmp_path, settings, clock)
        _emit(capsys, f"samples-{index}", {
            "operations": batch, "parent_test_process_rss_os_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "database_connection_counts_are_samples": True, "elapsed_s": time.monotonic() - started,
        })
        assert all(item["count"] > 0 for item in batch)
        assert sum(row["outcomes"].get("GRANTED", 0) for row in batch if row["kind"] == "admit") > 0
        assert sum(row["outcomes"].get("current_observed", 0) for row in batch if row["kind"] == "reader") > 0
        assert sum(row["outcomes"].get("CORRECTED", 0) for row in batch if row["kind"] == "reconcile") > 0
        assert all(active <= 8 for item in batch for active, _ in item["locks"])
        _cap_connection()
    assert UsageReservation.objects.filter(state__in=("RESERVED", "ISSUED")).count() <= 24
    assert UsageWeek.objects.filter(org_id__in=[org.pk for org in orgs], stt_seconds_settled=1).count() == 64 * 104
    _emit(capsys, "complete", {"elapsed_s": time.monotonic() - started})


def test_local_load_roles_all_start_and_finish_before_seeding():
    from threading import Lock

    started, finished = [], []
    lock = Lock()

    def operation(org_index, role):
        with lock:
            started.append((org_index, role))
        result = {"kind": role, "count": 1}
        with lock:
            finished.append((org_index, role))
        return result

    results = _collect_locals(operation, lambda: None, timeout=2)
    intended = [(0, "reader"), (1, "reader"), (2, "reader"), (3, "reader"), (6, "reconcile"), (7, "ingest")]
    assert sorted(started) == sorted(finished) == intended
    assert [row["kind"] for row in results] == [role for _, role in intended]


def test_admission_measurement_counts_a_real_query_in_one_sample():
    ticks = iter((0, 0, 0.01, 1))

    def submit_once():
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
        return object()

    result = _sample_admissions(submit_once, .5, monotonic=lambda: next(ticks), sleep=lambda _: None)
    assert (result["count"], result["queries"], result["outcomes"]) == (1, 1, {"GRANTED": 1})


def test_admission_measurement_counts_transactions_past_the_cumulative_log_limit():
    ticks = iter((0,) * 300 + (1,))
    attempts = 0

    def submit_once():
        nonlocal attempts
        attempts += 1
        with transaction.atomic():
            with connection.cursor() as cursor:
                for _ in range(90):
                    cursor.execute("SELECT 1")
            if attempts % 2 == 0:
                transaction.set_rollback(True)
        return object()

    result = _sample_admissions(submit_once, .5, monotonic=lambda: next(ticks), sleep=lambda _: None)
    # Each of 100 attempts logs BEGIN, 90 selects, and either COMMIT or ROLLBACK.
    assert (result["count"], result["queries"], result["outcomes"]) == (100, 9200, {"GRANTED": 100}), result


@pytest.mark.parametrize("statement_count", [4, 5])
def test_admission_measurement_rejects_a_full_operation_log(monkeypatch, statement_count):
    connection.ensure_connection()
    monkeypatch.setattr(connection, "queries_log", deque(maxlen=4))
    monkeypatch.setattr(connection, "force_debug_cursor", False)
    ticks = iter((0, 0, .01, 1))

    def submit_once():
        with connection.cursor() as cursor:
            for _ in range(statement_count):
                cursor.execute("SELECT 1")

    with pytest.raises(AssertionError, match="SQL measurement reached the query log capacity"):
        _sample_admissions(submit_once, .5, monotonic=lambda: next(ticks), sleep=lambda _: None)
    assert connection.force_debug_cursor is False


def test_admission_measurement_preserves_operation_error_and_restores_debug_cursor(monkeypatch):
    connection.ensure_connection()
    monkeypatch.setattr(connection, "queries_log", deque(maxlen=4))
    monkeypatch.setattr(connection, "force_debug_cursor", False)
    failure = RuntimeError("original measured operation error")

    def submit_once():
        with connection.cursor() as cursor:
            for _ in range(5):
                cursor.execute("SELECT 1")
        raise failure

    with pytest.raises(RuntimeError) as caught:
        _sample_admissions(submit_once, .5, monotonic=lambda: 0, sleep=lambda _: None)
    assert caught.value is failure
    assert connection.force_debug_cursor is False
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
