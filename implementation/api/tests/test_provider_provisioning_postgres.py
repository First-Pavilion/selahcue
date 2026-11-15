"""PostgreSQL lock contention, migration and provider history enforcement."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from provider_helpers import provider_mounts  # noqa: F401
from test_provider_provisioning import NOW, admitted_pool, make_demand  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL is required for real row locks and history triggers")


def test_last_resource_slot_serializes_two_churches(admitted_pool):
    from selahcue_api.apps.providers.contracts import CapacityUnavailable, CapacityUnavailableCode, ProvisioningPending
    from selahcue_api.apps.providers.models import ProviderExternalResource, ProviderResourceClaim
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    ProviderExternalResource.objects.bulk_create([
        ProviderExternalResource(
            pool=admitted_pool, provider="deepgram", resource_scope_id=admitted_pool.parent_scope_id,
            external_id=f"external-{index}", count_state="COUNTED", first_seen_at=NOW,
            last_seen_at=NOW, created_at=NOW, updated_at=NOW,
        ) for index in range(15)
    ])
    contenders = [make_demand() for _ in range(2)]
    gate = Barrier(2, timeout=4)

    def admit(ctx, token):
        try:
            gate.wait()
            return ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(admit, *pair) for pair in contenders]
        results = [future.result(timeout=8) for future in futures]
    assert sum(isinstance(result, ProvisioningPending) for result in results) == 1
    assert CapacityUnavailable(CapacityUnavailableCode.RESOURCE_CAPACITY) in results
    assert ProviderResourceClaim.objects.count() == 1


def test_clock_runs_after_org_lock_wait(admitted_pool):
    from selahcue_api.apps.accounts.models import CustomerOrg
    from selahcue_api.apps.providers.contracts import ProvisioningRejected
    from selahcue_api.apps.providers.models import ProviderResourceClaim
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    ctx, token = make_demand()
    target = Event()
    observed_clock = Event()
    backend_pid = []

    def clock():
        observed_clock.set()
        return token.expires_at

    def admit():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            target.set()
            return ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=clock)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as workers:
        with transaction.atomic():
            CustomerOrg.objects.select_for_update().get(pk=ctx.org_id)
            future = workers.submit(admit)
            assert target.wait(timeout=3)
            until = monotonic() + 1
            with connection.cursor() as cursor:
                while True:
                    cursor.execute("SELECT pg_blocking_pids(%s)", [backend_pid[0]])
                    if cursor.fetchone()[0]:
                        break
                    assert monotonic() < until
                    sleep(0.01)
            assert not observed_clock.is_set()
        with pytest.raises(ProvisioningRejected, match="INELIGIBLE"):
            future.result(timeout=4)
    assert observed_clock.is_set()
    assert ProviderResourceClaim.objects.count() == 0


def test_original_token_is_deletable_but_provisioning_history_is_retained(admitted_pool):
    from selahcue_api.apps.providers.models import ProviderResourceClaim, ProvisioningDemand
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    ctx, token = make_demand()
    ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    pk = token.pk
    token.delete()
    assert ProvisioningDemand.objects.get().trigger_token_pk == pk
    with pytest.raises(IntegrityError), transaction.atomic():
        ProvisioningDemand.objects.update(trigger_token_pk=pk + 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProviderResourceClaim.objects.all().delete()
    assert ProviderResourceClaim.objects.count() == 1


def test_migration_forward_reverse_restores_leafs_and_preserves_task3_rows():
    apps_label = "selahcue_providers"
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    original = [(apps_label, "0001_initial")]
    try:
        executor.migrate(original)
        old = MigrationExecutor(connection).loader.project_state(original).apps
        org = old.get_model("selahcue_accounts", "CustomerOrg").objects.create(
            name="Historical provider fixture", slug=uuid4().hex, country="NG", primary_contact_email="test@example.test",
            created_by_actor_id="fixture", idempotency_key=uuid4().hex,
        )
        mapping = old.get_model(apps_label, "ProviderCredential").objects.create(
            org_id=org.pk, provider="deepgram", parent_scope_id="test-historical",
            external_project_id="test-historical", created_at=NOW, updated_at=NOW, state="PROVISIONING",
        )
        MigrationExecutor(connection).migrate(leaves)
        from selahcue_api.apps.providers.models import ProviderCredential, ProvisioningDemand
        assert ProviderCredential.objects.filter(pk=mapping.pk).exists()
        assert ProvisioningDemand.objects.count() == 0
        MigrationExecutor(connection).migrate(original)
        historical = MigrationExecutor(connection).loader.project_state(original).apps
        assert historical.get_model(apps_label, "ProviderCredential").objects.filter(pk=mapping.pk).exists()
    finally:
        MigrationExecutor(connection).migrate(leaves)
