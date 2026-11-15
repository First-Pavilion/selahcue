"""Provider attribution remains fixed through replay and renewal."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from queue import Queue
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from selahcue_api.apps.providers.contracts import RegistryReason
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.providers.registry import import_existing_mapping, retire_mapping
from selahcue_api.apps.usage.contracts import ReservationRejected, SessionRequest
from selahcue_api.apps.usage.models import UsageReservation, UsageWeek
from selahcue_api.apps.usage.services import reserve

from provider_helpers import (
    OPENAI, SECRET, audit, cold_provider_cache, identity, provider_mounts, provisioner_runtime,
)
from test_effective_org_plan import NOW, church, context, device, licence
from test_usage_weeks import DIGEST, start
from selahcue_api.apps.usage.services import reserve_notes_job

pytestmark = pytest.mark.django_db


def active_mapping(org, external=None):
    return import_existing_mapping(
        mapping_id=uuid4(), org_id=org.pk, identity=external or identity(),
        secret=SECRET, now=NOW, audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
    )


def retire(mapping):
    row = ProviderCredential.objects.get(pk=mapping.mapping_id)
    retire_mapping(mapping_id=row.pk, expected_revision=row.revision, now=NOW, audit=audit(RegistryReason.RETIRE))


def test_new_bound_reservation_keeps_retired_binding_through_exact_replay(provisioner_runtime):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    request = start()
    unbound = context(install, "stt")
    bound = replace(unbound, provider_mapping_id=mapping.mapping_id)
    admitted = reserve(bound, request, NOW)
    row = UsageReservation.objects.get(pk=admitted.reservation_id)
    assert row.provider_mapping_id == mapping.mapping_id
    retire(mapping)
    with pytest.raises(ReservationRejected, match="ALREADY_ISSUED"):
        reserve(bound, request, NOW)
    with pytest.raises(ReservationRejected, match="IDEMPOTENCY_CONFLICT"):
        reserve(unbound, request, NOW)
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve(bound, start(), NOW)
    row.refresh_from_db()
    assert row.provider_mapping_id == mapping.mapping_id


@pytest.mark.parametrize("invalid", ["other_org", "other_provider", "missing", "string", "provisioning"])
def test_binding_validates_org_provider_active_and_uuid_before_inserting(invalid, provisioner_runtime):
    org = church()
    install = device(licence(org))
    if invalid == "other_org":
        mapping_id = active_mapping(church()).mapping_id
    elif invalid == "other_provider":
        mapping_id = active_mapping(org, identity(OPENAI)).mapping_id
    elif invalid == "provisioning":
        mapping_id = ProviderCredential.objects.create(
            org=org, provider="deepgram", parent_scope_id="synthetic-project",
            external_project_id="synthetic-project", created_at=NOW, updated_at=NOW,
        ).pk
    else:
        mapping_id = uuid4()
        if invalid == "string":
            mapping_id = str(mapping_id)
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve(replace(context(install, "stt"), provider_mapping_id=mapping_id), start(), NOW)
    assert not UsageReservation.objects.filter(org=org).exists()
    assert not UsageWeek.objects.filter(org=org).exists()


def test_notes_binding_accepts_only_openai(provisioner_runtime):
    org = church()
    install = device(licence(org))
    deepgram = active_mapping(org)
    openai = active_mapping(org, identity(OPENAI))
    note = context(install, "notes")
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve_notes_job(replace(note, provider_mapping_id=deepgram.mapping_id), uuid4(), DIGEST, NOW)
    decision = reserve_notes_job(replace(note, provider_mapping_id=openai.mapping_id), uuid4(), DIGEST, NOW)
    assert UsageReservation.objects.get(pk=decision.reservation_id).provider_mapping_id == openai.mapping_id


def test_renewal_requires_same_mapping_even_after_retire_and_replacement(provisioner_runtime):
    org = church()
    install = device(licence(org))
    original = active_mapping(org)
    context_without_mapping = context(install, "stt")
    ctx = replace(context_without_mapping, provider_mapping_id=original.mapping_id)
    first = reserve(ctx, start(), NOW)
    # The foundation does not issue external grants. Set the already-issued starting slice.
    UsageReservation.objects.filter(pk=first.reservation_id).update(state="ISSUED", issued_at=NOW)

    def renewal(previous):
        return SessionRequest(uuid4(), "renew", previous, "existing", False, "v1", "v1")

    with pytest.raises(ReservationRejected, match="INVALID_RENEWAL"):
        reserve(context_without_mapping, renewal(first.reservation_id), NOW)
    second = reserve(ctx, renewal(first.reservation_id), NOW)
    assert UsageReservation.objects.get(pk=second.reservation_id).provider_mapping_id == original.mapping_id
    retire(original)
    replacement = active_mapping(org)
    new_ctx = replace(ctx, provider_mapping_id=replacement.mapping_id)
    with pytest.raises(ReservationRejected, match="INVALID_RENEWAL"):
        reserve(new_ctx, renewal(second.reservation_id), second.authorized_from)


@pytest.mark.django_db(transaction=True)
def test_postgres_reservation_rechecks_mapping_after_competing_retirement(provisioner_runtime):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row-lock contention.")
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    ctx = replace(context(install, "stt"), provider_mapping_id=mapping.mapping_id)
    worker_pids = Queue()

    def admit():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                worker_pids.put(cursor.fetchone()[0])
            reserve(ctx, start(), NOW)
            return "admitted"
        except ReservationRejected as error:
            return error.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            retire(mapping)
            attempt = pool.submit(admit)
            pid = worker_pids.get(timeout=10)
            deadline = monotonic() + 8
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                assert monotonic() < deadline, "Reservation must wait until retirement commits"
                sleep(0.01)
        assert attempt.result(timeout=10) == "INVALID_CONTEXT"
    assert not UsageWeek.objects.filter(org=org).exists()


@pytest.mark.django_db(transaction=True)
def test_postgres_task2_rows_survive_forward_reverse_and_restore_all_migration_leaves():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL migration and trigger round trip.")
    org = church()
    install = device(licence(org))
    original = reserve(context(install, "stt"), start(), NOW)
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    before = [("selahcue_usage", "0001_initial"), ("selahcue_providers", None)]
    try:
        executor.migrate(before)
        executor = MigrationExecutor(connection)
        assert ("selahcue_providers", "0001_initial") not in executor.loader.applied_migrations
        historical = executor.loader.project_state([before[0]]).apps.get_model(
            "selahcue_usage", "UsageReservation",
        )
        assert historical.objects.get(pk=original.reservation_id).state == "RESERVED"

        executor.migrate(leaves)
        row = UsageReservation.objects.get(pk=original.reservation_id)
        assert row.provider_mapping_id is None
        MigrationExecutor(connection).migrate(before)
        assert historical.objects.get(pk=original.reservation_id).state == "RESERVED"
    finally:
        MigrationExecutor(connection).migrate(leaves)
    assert UsageReservation.objects.get(pk=original.reservation_id).provider_mapping_id is None
