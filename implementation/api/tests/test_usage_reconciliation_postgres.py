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


def _publish_with_delivery_receipt(work, broker_app, *, clock=None):
    from unittest.mock import patch

    real_send = broker_app.send_task
    invocations, errors = [], []

    def send(name, **kwargs):
        invocations.append((name, kwargs.get("task_id"), kwargs.get("queue")))
        try:
            return real_send(name, **kwargs)
        except Exception as error:
            errors.append((type(error).__name__, type(error.__cause__).__name__))
            raise

    with patch.object(broker_app, "send_task", side_effect=send):
        if clock is None:
            publish_work(work.pk, app=broker_app)
        else:
            publish_work(work.pk, app=broker_app, clock=clock)
    delivery = UsageOutbox.objects.get(work=work, generation=work.execution_generation)
    state = {
        "delivery": str(delivery.pk), "generation": delivery.generation, "state": delivery.state,
        "publish_attempts": delivery.publish_attempts, "last_error": delivery.last_error,
        "available_at": delivery.available_at.isoformat(), "first_failure_at": delivery.first_failure_at,
        "invocations": invocations, "error_classes": errors,
    }
    assert len(invocations) == 1 and invocations[0][1:] == (str(delivery.pk), "provider_usage"), state
    assert delivery.publish_attempts == 1 and delivery.state in ("SENT", "ACKED"), state
    assert not errors, state
    return state


class _UsageDeliveryDiagnostic:
    """Finite fixture-only receipts; configuration alone is never a channel receipt.

    Copied into the spawned worker with inspect.getsource, so this class imports
    only its own dependencies and never imports the Django test module there.
    """

    marker = "TASK7_USAGE_DELIVERY "
    namespace_fields = {"app", "transport", "host", "port", "db", "broker_match",
                        "prefix_sha256", "prefix_match", "queue", "exchange", "routing_key"}
    identity_fields = {"task_name_match", "task_id_match", "work_id_match"}

    def __init__(self, broker, prefix, task_id, work_id, *, stream=None):
        import time
        from urllib.parse import urlsplit

        self.started = time.monotonic()
        self.events, self.stream = [], stream
        self.prefix, self.task_id, self.work_id = prefix, task_id, work_id
        self.broker = urlsplit(broker)
        self.publish_channel = self.publish_client = None

    @classmethod
    def valid(cls, row):
        import re

        if type(row) is not dict:
            return False
        stage = row.get("stage")
        if type(stage) is not str:
            return False
        fields = {"stage", "elapsed_ms", "overflow"}
        if stage == "publish_channel":
            fields |= cls.namespace_fields | cls.identity_fields
        elif stage == "consumer_channel":
            fields |= cls.namespace_fields
        elif stage == "received":
            fields |= cls.identity_fields | {"routing_key"}
        elif stage == "queue_counts":
            fields |= {"counts"}
        elif stage not in {"publish_unknown", "consumer_unknown", "received_unknown", "counts_unknown", "overflow"}:
            return False
        if set(row) != fields or type(row["elapsed_ms"]) is not int or not 0 <= row["elapsed_ms"] <= 3_600_000:
            return False
        for key in fields & {"overflow", "broker_match", "prefix_match", *cls.identity_fields}:
            if type(row[key]) is not bool:
                return False
        if row["overflow"] != (stage == "overflow"):
            return False
        enums = {"app": {"task6-test", "selahcue_api", "other"}, "transport": {"redis", "other"},
                 "host": {"expected-loopback", "other"},
                 "queue": {"expected", "other", "absent"}, "exchange": {"expected", "other", "absent"},
                 "routing_key": {"expected", "other", "absent"}}
        for key, allowed in enums.items():
            if key in fields and (type(row[key]) is not str or row[key] not in allowed):
                return False
        if "port" in fields:
            if type(row["port"]) is not int or not 1 <= row["port"] <= 65535:
                return False
            if type(row["db"]) is not int or not 0 <= row["db"] <= 15:
                return False
            if type(row["prefix_sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", row["prefix_sha256"]):
                return False
        if "counts" in fields:
            counts = row["counts"]
            if type(counts) is not list or len(counts) != 4 or any(type(n) is not int or not 0 <= n <= 2**31 - 1 for n in counts):
                return False
        return True

    def emit(self, stage, **fields):
        import json
        import time

        if len(self.events) >= 8:
            return
        if len(self.events) == 7:
            stage, fields = "overflow", {}
        row = {"stage": stage, "elapsed_ms": min(3_600_000, max(0, int((time.monotonic() - self.started) * 1000))),
               "overflow": stage == "overflow", **fields}
        if not self.valid(row):
            return
        line = self.marker + json.dumps(row, separators=(",", ":"))
        if len(line.encode("utf-8")) > 2048:
            return
        self.events.append(row)
        if self.stream is not None:
            print(line, file=self.stream, flush=True)

    def unknown(self, stage):
        try:
            self.emit(stage)
        except Exception:
            pass  # Broken diagnostic output cannot replace a native error.

    def observe(self, stage, reader):
        # No error text, task repr, arbitrary headers or configuration enters a marker.
        try:
            self.emit(stage, **reader())
        except Exception:
            self.unknown({"publish_channel": "publish_unknown", "consumer_channel": "consumer_unknown",
                          "received": "received_unknown", "queue_counts": "counts_unknown"}[stage])

    @staticmethod
    def selected(value):
        return "expected" if value == "provider_usage" else "absent" if value in (None, "") else "other"

    def namespace(self, channel, app, queue, exchange, routing_key, *, client=None):
        import hashlib
        from kombu.transport.redis import Channel

        # Channel.__init__ has already pinged this cached client. Do not resolve
        # the lazy property here or create/acquire any connection for observation.
        if not isinstance(channel, Channel):
            raise ValueError
        if client is None:
            client = channel.__dict__["client"]
        params = client.connection_pool.connection_kwargs
        prefix = getattr(client, "global_keyprefix", "")
        if type(prefix) is not str or len(prefix) > 128 or not prefix.isascii():
            raise ValueError
        host, port, db = params.get("host"), params.get("port"), params.get("db")
        loopback = host in ("localhost", "127.0.0.1", "::1")
        match = (loopback and host == self.broker.hostname and port == (self.broker.port or 6379)
                 and db == int(self.broker.path.strip("/") or "0"))
        return {"app": app if app in ("task6-test", "selahcue_api") else "other", "transport": "redis",
                "host": "expected-loopback" if loopback else "other", "port": port, "db": db,
                "broker_match": match, "prefix_sha256": hashlib.sha256(prefix.encode("ascii")).hexdigest(),
                "prefix_match": prefix == self.prefix, "queue": self.selected(queue),
                "exchange": self.selected(exchange), "routing_key": self.selected(routing_key)}

    def identity(self, name, task_id, kwargs):
        return {"task_name_match": name == "usage.recover_mint", "task_id_match": task_id == self.task_id,
                "work_id_match": type(kwargs) is dict and kwargs.get("work_id") == self.work_id}

    def publish(self, channel, message, exchange, routing_key, app, *, client=None):
        import json

        def read():
            body = message["body"]
            if (message.get("content-type") != "application/json" or message.get("content-encoding") != "utf-8"
                    or type(body) not in (str, bytes) or len(body) > 8192):
                raise ValueError
            decoded = json.loads(body)
            if type(decoded) is not list or len(decoded) != 3 or type(decoded[1]) is not dict:
                raise ValueError
            row = self.namespace(channel, app, routing_key, exchange, routing_key, client=client)
            row.update(self.identity(message["headers"].get("task"), message["headers"].get("id"), decoded[1]))
            if not self.valid({"stage": "publish_channel", "elapsed_ms": 0, "overflow": False, **row}):
                raise ValueError
            self.publish_channel = channel
            self.publish_client = client if client is not None else channel.__dict__["client"]
            return row
        self.observe("publish_channel", read)

    def publisher_hook(self, app):
        from contextlib import contextmanager
        from unittest.mock import patch
        from kombu.transport.redis import Channel

        native_publish, native_acquire = Channel.basic_publish, Channel.conn_or_acquire
        pending = [None]  # Only the currently executing native publication.

        @contextmanager
        def acquire(channel, *args, **kwargs):
            # _put acquires this synchronous client immediately before LPUSH.
            # The channel's cached client is asynchronous and is not that client.
            with native_acquire(channel, *args, **kwargs) as client:
                observation = pending[0]
                if observation is not None and observation[0] is channel:
                    _, message, exchange, routing_key = observation
                    try:
                        self.publish(channel, message, exchange, routing_key, app.main, client=client)
                    except Exception:
                        self.unknown("publish_unknown")
                yield client

        def forwarding(channel, *args, **kwargs):
            previous, before = pending[0], len(self.events)
            try:
                try:
                    message = args[0] if args else kwargs["message"]
                    # Preserve pre-base64 serialized identity without mutating the
                    # native message that basic_publish augments in place.
                    envelope = {key: message[key] for key in ("body", "headers", "content-type", "content-encoding")}
                    pending[0] = (channel, envelope, args[1] if len(args) > 1 else kwargs.get("exchange"),
                                  args[2] if len(args) > 2 else kwargs.get("routing_key"))
                except Exception:
                    pending[0] = None
                return native_publish(channel, *args, **kwargs)
            finally:
                pending[0] = previous
                if len(self.events) == before:
                    self.unknown("publish_unknown")

        @contextmanager
        def installed():
            with patch.object(Channel, "basic_publish", forwarding), patch.object(Channel, "conn_or_acquire", acquire):
                yield
        return installed()

    def ready(self, sender=None, **kwargs):
        def read():
            consumer = sender.task_consumer
            if len(consumer.queues) != 1:
                raise ValueError
            queue = consumer.queues[0]
            row = self.namespace(consumer.channel, sender.app.main, queue.name, queue.exchange.name, queue.routing_key)
            if not self.valid({"stage": "consumer_channel", "elapsed_ms": 0, "overflow": False, **row}):
                raise ValueError
            return row
        self.observe("consumer_channel", read)

    def received(self, request=None, **kwargs):
        self.observe("received", lambda: {**self.identity(request.name, request.id, request.kwargs),
                                          "routing_key": self.selected(request.delivery_info.get("routing_key"))})

    def worker_hooks(self):
        from contextlib import ExitStack
        from celery import signals

        stack = ExitStack()
        try:
            for signal, receiver in ((signals.worker_ready, self.ready), (signals.task_received, self.received)):
                signal.connect(receiver, weak=False)
                stack.callback(signal.disconnect, receiver=receiver)
        except Exception:
            stack.close()
            self.unknown("consumer_unknown")
        return stack

    @classmethod
    def collect(cls, log):
        import io
        import json

        rows = []
        # Bounded line reads also reject a huge non-marker or malformed JSON line.
        stream = io.StringIO(log)
        while len(rows) < 8:
            line = stream.readline(2049)
            if not line:
                break
            if not line.endswith("\n") and len(line) == 2049:
                while line and not line.endswith("\n"):
                    line = stream.readline(2049)
                continue
            if not line.startswith(cls.marker) or len(line.encode("utf-8", errors="replace")) > 2048:
                continue
            try:
                row = json.loads(line[len(cls.marker):])
                if cls.valid(row):
                    rows.append(row)
            except (ValueError, TypeError, RecursionError):
                pass
        return rows

    @classmethod
    def branch(cls, parent, worker):
        parent = [row for row in parent if cls.valid(row)]
        worker = [row for row in worker if cls.valid(row)]
        rows = [*parent, *worker]
        received = [row for row in worker if row["stage"] == "received"]
        if received:
            return "received" if all(all(row[k] for k in cls.identity_fields) and row["routing_key"] == "expected" for row in received) else "mismatch"
        channels = [row for row in rows if row["stage"] in ("publish_channel", "consumer_channel")]
        if any(not row["broker_match"] or not row["prefix_match"] or row["queue"] != "expected"
               or row["routing_key"] != "expected" or row["exchange"] == "other"
               or any(not row[k] for k in cls.identity_fields if k in row) for row in channels):
            return "mismatch"
        if (any(row["stage"] == "publish_channel" for row in parent)
                and any(row["stage"] == "consumer_channel" for row in worker)
                and not any(row["stage"].endswith("unknown") or row["overflow"] for row in rows)):
            return "matched_no_receive"
        return "unknown"

    def queue_counts(self, worker, *, failed_after_deadline):
        # Optional post-failure observation only. Never run on missing/mismatched
        # namespace/identity or reception; never change the original work verdict.
        import time

        deadline = time.monotonic() + 2
        if not failed_after_deadline or self.branch(self.events, worker) != "matched_no_receive":
            return

        def read():
            import json
            import os
            import re
            import subprocess
            import sys
            import redis

            channel = self.publish_channel
            client = self.publish_client
            params = client.connection_pool.connection_kwargs
            if (not re.fullmatch(r"task6-[0-9a-f]{32}:", self.prefix)
                    or channel.priority_steps != [0, 3, 6, 9]
                    or client.connection_pool.connection_class is not redis.Connection
                    or params.get("credential_provider") is not None):
                raise ValueError
            keys = [client.global_keyprefix + channel._q_for_pri("provider_usage", priority)
                    for priority in channel.priority_steps]
            expected = [self.prefix + "provider_usage" + suffix for suffix in ("", "\x06\x163", "\x06\x166", "\x06\x169")]
            if keys != expected:
                raise ValueError
            # No inherited environment/config or key material in argv/output.
            config = {key: params[key] for key in ("host", "port", "db", "username", "password") if key in params}
            payload = json.dumps([config, keys])
            if len(payload.encode("utf-8")) > 2048:
                raise ValueError
            source = """
import json, sys, redis
from redis.backoff import NoBackoff
from redis.retry import Retry
config, keys = json.load(sys.stdin)
client = redis.Redis(**config, socket_connect_timeout=0.15, socket_timeout=0.15,
                     retry=Retry(NoBackoff(), 0), retry_on_timeout=False)
try:
    with client.pipeline(transaction=False) as pipe:
        for key in keys:
            pipe.llen(key)
        print(json.dumps(pipe.execute()))
finally:
    client.close()
"""
            # Reserve cleanup/parse time from the single total two-second budget.
            timeout = min(1.5, deadline - time.monotonic() - 0.2)
            if timeout <= 0:
                raise ValueError
            result = subprocess.run([sys.executable, "-B", "-c", source], input=payload,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
                                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONDONTWRITEBYTECODE": "1"})
            if time.monotonic() >= deadline or result.returncode != 0 or len(result.stdout) > 128:
                raise ValueError
            counts = json.loads(result.stdout)
            if not self.valid({"stage": "queue_counts", "elapsed_ms": 0, "overflow": False, "counts": counts}):
                raise ValueError
            return {"counts": counts}
        self.observe("queue_counts", read)


def test_real_redis_publish_and_worker_ack_preserve_terminal_usage_work(usage_runtime, tmp_path):
    import inspect
    from celery import Celery

    broker = os.getenv("CELERY_BROKER_URL")
    if not broker or not broker.startswith(("redis://", "rediss://")):
        pytest.skip("Requires the configured disposable Redis broker")
    usage_runtime()
    code = inspect.getsource(_UsageDeliveryDiagnostic) + """
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'selahcue_api.settings')
django.setup()
from selahcue_api.celery import app
app.conf.broker_transport_options = {
    **app.conf.broker_transport_options, 'global_keyprefix': os.environ['SELAHCUE_TEST_USAGE_PREFIX'],
}
diagnostic = _UsageDeliveryDiagnostic(
    os.environ['CELERY_BROKER_URL'], os.environ['SELAHCUE_TEST_USAGE_PREFIX'],
    os.environ['SELAHCUE_TEST_USAGE_TASK_ID'], os.environ['SELAHCUE_TEST_USAGE_WORK_ID'], stream=sys.__stdout__,
)
with diagnostic.worker_hooks():
    app.worker_main(['worker', '-P', 'prefork', '--concurrency=1', '-Q', 'provider_usage', '--without-gossip',
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
    delivery = UsageOutbox.objects.get(work=work)
    env.update({"SELAHCUE_TEST_USAGE_TASK_ID": str(delivery.pk), "SELAHCUE_TEST_USAGE_WORK_ID": str(work.pk)})
    diagnostic = _UsageDeliveryDiagnostic(broker, prefix, str(delivery.pk), str(work.pk))
    with (tmp_path / "worker.log").open("w+") as output:
        process = subprocess.Popen(
            [sys.executable, "-c", code], stdout=output, stderr=subprocess.STDOUT, env=env,
        )
        try:
            with diagnostic.publisher_hook(broker_app):
                publication = _publish_with_delivery_receipt(work, broker_app)
            expires = time.monotonic() + 15
            while time.monotonic() < expires and process.poll() is None:
                if UsageWork.objects.filter(pk=work.pk, state="COMPLETE").exists():
                    break
                time.sleep(0.03)
            output.seek(0)
            log = output.read()
            assert "usage.recover_mint" in log
            final = UsageOutbox.objects.get(work=work)
            worker_events = diagnostic.collect(log)
            work_state = UsageWork.objects.get(pk=work.pk).state
            diagnostic.queue_counts(worker_events, failed_after_deadline=(work_state != "COMPLETE" and time.monotonic() >= expires))
            # Freeze the original verdict before the optional diagnostic allowance.
            assert work_state == "COMPLETE", {
                "publication": publication, "final_delivery_state": final.state, "worker": log[-2500:],
                "delivery_boundary": diagnostic.branch(diagnostic.events, worker_events),
                "producer_events": diagnostic.events, "worker_events": worker_events,
            }
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


def test_retired_binding_dirties_running_work_after_reconcile_commit_without_health_bump(
    usage_runtime, clock, provider_mounts,
):
    from selahcue_api.apps.usage.models import UsageOrgState
    from selahcue_api.apps.usage.observations import dirty_orgs
    from selahcue_api.apps.usage.usage_tasks import _claim_publication, claim_work, finish_work

    org = church()
    mapping = active_mapping(org, identity(key="retired-handoff"))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [], NOW)
    with bounded_transaction():
        dirty_orgs((org.pk,), NOW)
    work = UsageWork.objects.get(kind="RECONCILE", org=org)
    delivery = _claim_publication(work.pk, False, clock)
    claimed = claim_work(work.pk, delivery[1], "RECONCILE", "provider_usage", clock=clock)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    retire(mapping)
    usage_runtime()
    clock.value = NOW + timedelta(seconds=1)
    interval = UTCInterval(MONDAY, clock())
    late = begin_scan(DEEPGRAM, interval=interval, start=clock())
    late_work = task_for(late, clock())
    page = parse_dg(dg_data([request("retired-later", key="retired-handoff", duration=8)]), interval=interval)
    page_authority = page_claim(late_work, clock())
    before = ProviderUsageHealthState.objects.get(pk="deepgram").revision
    barrier = Barrier(2, timeout=5)

    def writer():
        close_old_connections()
        try:
            barrier.wait()
            ingest_observations(page, late.pk, claim=page_authority)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        barrier.wait()
        future.result(timeout=10)
    assert ProviderUsageHealthState.objects.get(pk="deepgram").revision == before
    finish_work(claimed.pk, claimed.lease_id, clock=clock)
    state = UsageOrgState.objects.get(org=org)
    claimed.refresh_from_db()
    assert state.dirty_revision == state.applied_revision + 1
    assert claimed.state == "PENDING" and claimed.execution_generation == 2
    assert UsageOutbox.objects.filter(work=claimed, generation=2, state="PENDING").exists()
    reconcile_org(org.pk, clock(), clock=clock)
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 8


def test_postgres_statement_obeys_remaining_batch_time():
    from django.db import OperationalError

    started = time.monotonic()
    with pytest.raises(OperationalError) as caught:
        with bounded_transaction(deadline=started + 0.25), connection.cursor() as cursor:
            cursor.execute("SELECT pg_sleep(2)")
    elapsed = time.monotonic() - started
    assert getattr(caught.value.__cause__, "sqlstate", None) == "57014"
    assert elapsed < 1.5
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)


def test_postgres_exact_fraction_ceiling_and_aggregate_overflow_leave_totals_intact(usage_runtime, clock):
    from decimal import Decimal

    org = church()
    mapping = active_mapping(org, identity(key="exact-sum"))
    usage_runtime()
    interval = UTCInterval(MONDAY, NOW)
    initial = begin_scan(DEEPGRAM, interval=interval)
    observed(initial, [
        request("part-a", key="exact-sum", duration=0.1),
        request("part-b", key="exact-sum", duration=0.2),
    ], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 1
    assert ProviderUsageRecord.objects.get(request_id="part-a").current_version.duration_seconds == Decimal("0.1")

    clock.value += timedelta(seconds=1)
    overflow = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, clock()), start=clock())
    observed(overflow, [
        request("part-a", key="exact-sum", duration=2**63 - 1),
        request("part-b", key="exact-sum", duration=1),
    ], clock())
    result = reconcile_org(org.pk, clock(), clock=clock)
    assert result.blocked_reason == "ARITHMETIC_OVERFLOW"
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 1


@pytest.mark.parametrize("failure", ("checkpoint", "lost-after-page"))
def test_prefork_usage_scan_checkpoints_and_recovers_terminal_page(usage_runtime, tmp_path, failure):
    from celery import Celery
    from django.utils import timezone
    from selahcue_api.apps.usage.models import UsagePageClaim, UsageScan
    from selahcue_api.apps.usage.usage_tasks import repair_delivery_batch

    broker = os.getenv("CELERY_BROKER_URL")
    if not broker or not broker.startswith(("redis://", "rediss://")):
        pytest.skip("Requires the existing disposable Redis broker")
    usage_runtime()
    original_at = timezone.now().replace(microsecond=0)
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(original_at - timedelta(days=1), original_at), start=original_at)
    work = scan.usagework_set.get()
    env = _worker_environment(f"task6-prefork-{uuid4().hex}:")
    env.update({
        "SELAHCUE_TEST_USAGE_FAILURE": failure,
        "SELAHCUE_TEST_USAGE_READS": str(tmp_path / "reads"),
        "SELAHCUE_TEST_USAGE_WALL": str(tmp_path / "wall"),
    })
    app = Celery("task6-prefork-test", broker=broker)
    app.conf.broker_transport_options = {
        **settings.CELERY_BROKER_TRANSPORT_OPTIONS, "global_keyprefix": env["SELAHCUE_TEST_USAGE_PREFIX"],
    }
    source = """
import os, django
from datetime import datetime
from pathlib import Path
import time
django.setup()
from selahcue_api.celery import app
from selahcue_api.apps.usage import scans, tasks
from selahcue_api.apps.providers.adapters import deepgram_usage
from django.utils import timezone
app.loader.import_default_modules()
app.conf.broker_transport_options = {
    **app.conf.broker_transport_options, 'global_keyprefix': os.environ['SELAHCUE_TEST_USAGE_PREFIX'],
}
behavior = os.environ['SELAHCUE_TEST_USAGE_FAILURE']
reads = Path(os.environ['SELAHCUE_TEST_USAGE_READS'])
clock_path = Path(os.environ['SELAHCUE_TEST_USAGE_WALL'])
real_claim = tasks.claim_work
def claim(*args, **kwargs):
    def clock():
        return datetime.fromisoformat(clock_path.read_text()) if clock_path.exists() else timezone.now()
    return real_claim(*args, clock=clock, **kwargs)
tasks.claim_work = claim
def read(scope, interval, cursor):
    with reads.open('a') as stream:
        stream.write('read\\n')
    if behavior == 'checkpoint':
        time.sleep(20)
    return deepgram_usage._parse_page({'page': 0, 'limit': 100, 'requests': []}, scope, interval, cursor)
deepgram_usage.read_usage_page = read
actual_ingest = scans.ingest_observations
def ingest(*args, **kwargs):
    result = actual_ingest(*args, **kwargs)
    if behavior == 'lost-after-page':
        os._exit(71)
    return result
scans.ingest_observations = ingest
if behavior == 'checkpoint':
    task = app.tasks['usage.scan']
    task.soft_time_limit = 2
    task.time_limit = 4
app.worker_main(['worker', '-P', 'prefork', '--concurrency=1', '-Q', 'provider_usage',
                 '--without-gossip', '--without-mingle', '--without-heartbeat', '--loglevel=INFO'])
"""
    with (tmp_path / "worker.log").open("w+") as output:
        process = subprocess.Popen([sys.executable, "-c", source], stdout=output, stderr=subprocess.STDOUT, env=env)

        def wait_for(query):
            limit = time.monotonic() + 15
            while time.monotonic() < limit and process.poll() is None:
                if query():
                    return
                time.sleep(0.04)
            output.seek(0)
            pytest.fail("Expected prefork checkpoint was not observed. " + output.read()[-2500:])

        try:
            _publish_with_delivery_receipt(work, app, clock=lambda: original_at)
            if failure == "checkpoint":
                wait_for(lambda: UsageWork.objects.filter(pk=work.pk, state="PENDING", execution_generation=2).exists())
                assert UsagePageClaim.objects.get(scan=scan).attempts == 1
                assert UsageScan.objects.get(pk=scan.pk).state == "PARTIAL"
            else:
                wait_for(lambda: UsagePageClaim.objects.filter(scan=scan, state="APPLIED", terminal=True).exists())
                work.refresh_from_db()
                assert work.state == "RUNNING"
                resumed_at = work.lease_until + timedelta(seconds=1)
                (tmp_path / "wall").write_text(resumed_at.isoformat())
                repair_delivery_batch(
                    app, maintenance=False, remaining=1, deadline=time.monotonic() + 8, clock=lambda: resumed_at,
                )
                wait_for(lambda: UsageWork.objects.filter(pk=work.pk, state="COMPLETE", execution_generation=2).exists())
                assert UsageScan.objects.get(pk=scan.pk).state == "COMPLETE"
                assert UsagePageClaim.objects.get(scan=scan).attempts == 1
                assert UsageOutbox.objects.filter(work=work, state="ACKED").count() == 2
            assert (tmp_path / "reads").read_text().splitlines() == ["read"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=4)


def test_migration_installs_oa_page_json_guard_with_safe_shape_refusal(usage_runtime, clock):
    from provider_helpers import OPENAI
    from selahcue_api.apps.usage.models import UsagePageClaim

    usage_runtime()
    scan = begin_scan(OPENAI)
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        UsagePageClaim.objects.create(
            scan=scan, ordinal=2, oa_bucket_starts={"wrong": 0},
            created_at=NOW, updated_at=NOW,
        )
    assert getattr(caught.value.__cause__, "sqlstate", None) == "23514"
    assert UsagePageClaim.objects.filter(scan=scan, ordinal=0).exists()


def test_postgres_scope_id_guard_accepts_full_256_byte_printable_contract():
    from django.db import DataError
    from selahcue_api.apps.usage.models import UsageScope

    for value in ("!", "x" * 255, "x" * 255 + "~"):
        scope = UsageScope.objects.create(provider="deepgram", parent_scope_id=value, created_at=NOW, updated_at=NOW)
        assert UsageScope.objects.get(pk=scope.pk).parent_scope_id == value
    with pytest.raises(DataError) as too_long, transaction.atomic():
        UsageScope.objects.create(provider="deepgram", parent_scope_id="x" * 257, created_at=NOW, updated_at=NOW)
    assert getattr(too_long.value.__cause__, "sqlstate", None) == "22001"
    for value in ("", "trailing ", "xπ", "tab\t"):
        with pytest.raises(IntegrityError) as caught, transaction.atomic():
            UsageScope.objects.create(provider="deepgram", parent_scope_id=value, created_at=NOW, updated_at=NOW)
        assert getattr(caught.value.__cause__, "sqlstate", None) == "23514"


def test_postgres_nested_savepoint_cleanup_preserves_original_error_and_works_after_deadline():
    from django.db import DataError
    from selahcue_api.apps.usage.observation_contracts import UsageRejected

    with bounded_transaction():
        with pytest.raises(DataError) as caught, transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT %s::integer", ["not-an-integer"])
        assert getattr(caught.value.__cause__, "sqlstate", None) == "22P02"
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)

    ns = [0]
    with pytest.raises(UsageRejected, match="TASK_BUDGET"):
        with bounded_transaction(deadline_ns=100_000_000, monotonic_ns=lambda: ns[0]):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SELECT 2")
                assert cursor.fetchone() == (2,)
                ns[0] = 100_000_000
            with connection.cursor() as cursor:
                cursor.execute("SELECT 3")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 4")
        assert cursor.fetchone() == (4,)


def test_concurrent_reconciles_publish_once_after_single_current_snapshot(usage_runtime, clock):
    from selahcue_api.apps.usage.models import SttOrgReadiness, SttOrgCoverage

    org = church()
    active_mapping(org, identity(key="simultaneous"))
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [request(key="simultaneous", duration=3)], NOW)
    barrier = Barrier(3, timeout=5)

    def write():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            barrier.wait()
            return pid, reconcile_org(org.pk, NOW, clock=clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write) for _ in range(2)]
        barrier.wait()
        rows = [future.result(timeout=10) for future in futures]
    assert rows[0][0] != rows[1][0]
    assert all(result.blocked_reason is None for _, result in rows)
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 3
    assert SttOrgReadiness.objects.get(org=org).publication_revision == 1
    assert SttOrgCoverage.objects.filter(publication_id=org.pk).count() == 1


def test_reader_sees_stale_old_vector_until_atomic_reconciliation_commits(usage_runtime, clock):
    from threading import Event
    from django.test.utils import CaptureQueriesContext

    org = church()
    mapping = active_mapping(org)
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    clock.value += timedelta(seconds=1)
    next_scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, clock()), start=clock())
    observed(next_scan, [], clock())
    updated, release = Event(), Event()

    def write():
        close_old_connections()
        try:
            with transaction.atomic():
                assert reconcile_org(org.pk, clock(), clock=clock).blocked_reason is None
                updated.set()
                assert release.wait(5)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write)
        assert updated.wait(5)
        try:
            with CaptureQueriesContext(connection) as statements:
                old = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock())
            assert old.status == "stale" and len(statements) == 1
        finally:
            release.set()
        future.result(timeout=10)
    full = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=clock())
    assert full.status == "current_observed" and full.publication_revision == old.publication_revision + 1


def test_concurrent_late_attribution_binds_once_at_scope_authority(usage_runtime, clock, provider_mounts):
    from selahcue_api.apps.usage.observations import attribute_scope_batch

    usage_runtime()
    from_provider = begin_scan(DEEPGRAM)
    observed(from_provider, [request("concurrent-binding", key="not-yet-known", duration=3)], NOW)
    assert ProviderUsageRecord.objects.get().mapping_id is None
    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    org = church()
    mapping = active_mapping(org, identity(key="not-yet-known"))
    usage_runtime()
    barrier = Barrier(3, timeout=5)

    def bind():
        close_old_connections()
        try:
            barrier.wait()
            return attribute_scope_batch(from_provider.scope_id, after=None, clock=clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(bind) for _ in range(2)]
        barrier.wait()
        results = [future.result(timeout=10) for future in futures]
    assert sum(item.changed for item in results) == 1
    assert ProviderUsageRecord.objects.get().mapping_id == mapping.mapping_id
    assert UsageWork.objects.filter(kind="RECONCILE", org=org, state__in=("PENDING", "RUNNING")).count() == 1


def test_original_discarded_mint_receipt_is_followed_by_late_exact_accounting(provider_mounts, usage_runtime, clock):
    from test_cloud_grant_postgres import granted, submit

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="discarded-key"))
    token, _ = token_for(install)
    provider_mounts("web", stt=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")

    def release_in_transit(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        UsageReservation.objects.filter(pk=dispatch.authorization.reservation_id).update(state="RELEASED")
        return receipt

    assert submit(token, command(), deps(release_in_transit, clock=clock)) == "RESERVATION_RELEASED"
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == "DISCARDED" and attempt.audit_event_id
    issued = attempt.reservation
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [request("known-discarded-actual", key="discarded-key", duration=4)], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 4
    issued.refresh_from_db()
    attempt.refresh_from_db()
    assert issued.state == "RELEASED" and attempt.state == "DISCARDED"


def test_actual_mint_recovery_precedes_original_owner_receipt_without_second_outcome(
    provider_mounts, usage_runtime, clock,
):
    from test_cloud_grant_postgres import granted, submit
    from selahcue_api.apps.audit.models import AuditEvent
    from selahcue_api.apps.providers.stt_recovery import recover_abandoned_stt_mint

    org = church()
    install = device(licence(org))
    active_mapping(org)
    token, _ = token_for(install)
    provider_mounts("web", stt=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    attempts = []

    def recover_then_return(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        identifier = dispatch.authorization.attempt_id
        attempts.append(identifier)
        usage_runtime()
        attempt = SttMintAttempt.objects.get(pk=identifier)
        at = attempt.dispatch_not_after + timedelta(seconds=4)
        assert recover_abandoned_stt_mint(identifier, clock=lambda: at).state == "recovered_unknown"
        assert not recover_abandoned_stt_mint(identifier, clock=lambda: at).changed
        provider_mounts("web", stt=True, capable=True)
        initialize_provider_runtime(entrypoint="wsgi")
        return receipt

    first = command()
    dependencies = deps(recover_then_return, clock=clock)
    assert submit(token, first, dependencies) == "PROVIDER_UNAVAILABLE"
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == "UNKNOWN" and attempt.audit_event_id is None
    assert attempt.known_mint_received_at == attempt.reservation.last_minted_at
    assert attempt.known_mint_received_at is not None
    assert submit(token, first, dependencies) == "SESSION_PENDING" and len(attempts) == 1
    assert AuditEvent.objects.filter(action="cloud.stt.mint_recovery", request_id=str(attempt.pk)).count() == 1


def _wait_for_pg_blocking(pid, seconds=1.5):
    timeout = time.monotonic()+seconds
    while time.monotonic() < timeout:
        with connection.cursor() as cursor:
            cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
            if cursor.fetchone()[0]:
                return
        time.sleep(0.01)
    pytest.fail("Expected PostgreSQL lock wait did not occur before its deadline")


def test_upgrade_guarded_by_org_lock_cannot_fall_back_to_an_older_counted_from(usage_runtime, clock):
    from queue import Queue
    from test_effective_org_plan import staff_grant

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="upgrade-race"))
    since = NOW - timedelta(hours=1)
    reserve_stt(install, mapping.mapping_id, since-timedelta(minutes=1))
    staff_grant(org, "CORE", since, NOW+timedelta(hours=1))
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [
        request("pre-race-upgrade", key="upgrade-race", duration=80, created=since-timedelta(seconds=1)),
        request("post-race-upgrade", key="upgrade-race", duration=7, created=since),
    ], NOW)
    pid = Queue(maxsize=1)

    def run():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid.put(cursor.fetchone()[0])
            return reconcile_org(org.pk, NOW, clock=clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            reserve_stt(install, mapping.mapping_id, since)
            future = pool.submit(run)
            _wait_for_pg_blocking(pid.get(timeout=4))
        assert future.result(timeout=8).blocked_reason is None
    week = UsageWeek.objects.get(org=org)
    assert (week.counted_from, week.stt_seconds_settled) == (since, 7)


def test_reconciliation_reads_fact_committed_while_waiting_for_final_provider_authority(usage_runtime, clock):
    from queue import Queue
    from selahcue_api.apps.usage import health

    org = church()
    mapping = active_mapping(org, identity(key="capture-race"))
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(initial, [], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    clock.value += timedelta(seconds=1)
    interval = UTCInterval(MONDAY, clock())
    arriving = begin_scan(DEEPGRAM, interval=interval, start=clock())
    work = task_for(arriving, clock())
    claim = page_claim(work, clock())
    page = parse_dg(dg_data([request("authority-arrival", duration=5, key="capture-race")]), interval=interval)
    pid = Queue(maxsize=1)

    def run():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid.put(cursor.fetchone()[0])
            return reconcile_org(org.pk, clock(), clock=clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            health.lock_provider("deepgram", clock())
            future = pool.submit(run)
            _wait_for_pg_blocking(pid.get(timeout=4))
            ingest_observations(page, arriving.pk, claim=claim)
        assert future.result(timeout=8).blocked_reason is None
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 5


def test_usage_transport_closes_open_auxiliary_alias_before_child(usage_runtime, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_usage, usage_transport
    from selahcue_api.apps.usage.observation_contracts import UsageProfile

    usage_runtime()
    alias = "task6_auxiliary"
    connections.databases[alias] = dict(connection.settings_dict)
    try:
        extra = connections[alias]
        extra.connect()
        with extra.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
        assert extra.connection is not None

        def checked(_payload, **_kwargs):
            assert all(connections[name].connection is None for name in connections)
            return b'{"page":0,"limit":100,"requests":[]}'

        monkeypatch.setattr(usage_transport, "_run", checked)
        result = deepgram_usage.read_usage_page(DEEPGRAM, COVERAGE, None)
        assert result.receipt.profile == UsageProfile.DG_LISTEN_V1
        assert result.receipt.terminal_page_seen
    finally:
        connections[alias].close()
        del connections[alias]
        del connections.databases[alias]


def test_actual_publisher_socket_timeout_records_failure_without_extra_attempts(usage_runtime, tmp_path):
    import socket
    from threading import Event, Thread

    if not os.getenv("CELERY_BROKER_URL"):
        pytest.skip("Requires the hosted publisher runner")
    usage_runtime()
    with bounded_transaction():
        attempt = uuid4()
        job = ensure_work("MINT_RECOVERY", str(attempt), NOW, attempt_id=attempt)
    done = Event()
    seen = Event()
    source = """
import django, os
from uuid import UUID
django.setup()
from selahcue_api.celery import app
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.usage.usage_tasks import publish_work
initialize_provider_runtime(entrypoint='celery_worker')
publish_work(UUID(os.environ['TASK6_PUBLISH_ID']), app=app)
"""
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(4)
        server.settimeout(3)

        def sink():
            accepted, _ = server.accept()
            with accepted:
                seen.set()
                done.wait(10)

        thread = Thread(target=sink, daemon=True)
        thread.start()
        port = server.getsockname()[1]
        env = _worker_environment(f"task6-publisher-{uuid4().hex}:")
        env.update({"CELERY_BROKER_URL": f"redis://127.0.0.1:{port}/2", "TASK6_PUBLISH_ID": str(job.pk)})
        start = time.monotonic()
        try:
            result = subprocess.run([sys.executable, "-c", source], env=env, capture_output=True, timeout=10)
        finally:
            done.set()
            thread.join(timeout=3)
        assert result.returncode == 0 and seen.is_set(), result.stderr[-1500:]
        assert time.monotonic()-start < 10
    delivery = UsageOutbox.objects.get(work=job)
    assert (delivery.state, delivery.publish_attempts, delivery.last_error) == ("PENDING", 1, "PUBLICATION_FAILED")
    assert delivery.first_failure_at is not None and delivery.available_at > delivery.first_failure_at


def test_other_parent_health_transaction_denies_org_only_after_it_commits(provider_mounts, settings, tmp_path, clock):
    from threading import Event
    from selahcue_api.apps.providers.adapters import deepgram_usage
    from selahcue_api.apps.providers.contracts import ProviderScope, ProvisioningAuditContext
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.usage.observation_contracts import ObservedCoverage
    from selahcue_api.apps.usage.scans import finish_scan
    from test_usage_retained_history_load import _complete_scope, _runtime

    other = ProviderScope("deepgram", "other-parent-race")
    scopes = (DEEPGRAM, other)
    _runtime("provisioner", provider_mounts, settings, tmp_path, scopes)
    publish_provider_policy(
        cleanup_authorizations=(), audit=ProvisioningAuditContext("custody-fixture", uuid4(), "other-parent"),
        clock=lambda: NOW-timedelta(hours=1),
    )
    org = church()
    mapping = active_mapping(org)
    _runtime("usage", provider_mounts, settings, tmp_path, scopes)
    for scope in scopes:
        _complete_scope(scope, MONDAY, NOW, NOW, health_input=True)
    assert reconcile_org(org.pk, NOW, clock=clock).blocked_reason is None
    clock.value += timedelta(seconds=1)
    at = clock()
    interval = UTCInterval(MONDAY, at)
    scan = begin_scan(other, interval=interval, start=at)
    work = task_for(scan, at)
    claim = page_claim(work, at)
    raw = request("other-parent-new-breach", duration=60)
    raw["project_uuid"] = other.parent_scope_id
    page = deepgram_usage._parse_page(dg_data([raw]), other, interval, None)
    committed, release = Event(), Event()

    def write():
        close_old_connections()
        try:
            with transaction.atomic():
                ingest_observations(page, scan.pk, claim=claim)
                finish_scan(scan.pk, ObservedCoverage(scan.pk, other, interval, at, at, True))
                committed.set()
                assert release.wait(5)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(write)
        assert committed.wait(5)
        try:
            assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=at).status == "current_observed"
        finally:
            release.set()
        future.result(timeout=10)
    assert read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=at).blocked_reason == "unattributed_limit"


def test_actual_early_future_renewal_has_no_mint_and_uses_authorized_until_floor(usage_runtime, provider_mounts, clock):
    from selahcue_api.apps.usage.reconciliation import settlement_floor

    org = church()
    install = device(licence(org))
    active_mapping(org)
    token, _ = token_for(install)
    provider_mounts("web", stt=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    first, _ = sessions._issue_stt_session(token, command(), deps(clock=clock))
    clock.value += timedelta(seconds=250)
    renewal, _ = sessions._issue_stt_session(
        token, command(first.decision.reservation_id), deps(clock=clock),
    )
    row = UsageReservation.objects.get(pk=renewal.decision.reservation_id)
    assert row.last_minted_at is None
    assert row.issued_at == clock() < row.authorized_from == first.decision.authorized_until
    assert settlement_floor(row) == row.authorized_until + timedelta(seconds=900)
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 1
