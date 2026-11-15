"""Audited provider identity lifecycle and PostgreSQL history enforcement."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import IntegrityError, close_old_connections, connection, connections, transaction

from provider_helpers import (
    DEEPGRAM, OPENAI, SECRET, audit, cold_provider_cache, identity, provider_mounts,
    provisioner_runtime,
)
from test_effective_org_plan import NOW, church

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import (
    ProviderCustodyError, ProviderPartialIdentity, ProviderRegistryError, ProviderScope,
    RegistryReason, SecretBytes,
)
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.providers.registry import (
    activate_mapping, begin_mapping, bind_provisioning_identity, fail_mapping, import_existing_mapping,
    load_active_mapping, recover_mapping_secret, retire_mapping, rotate_wrapping_key_batch,
)


@pytest.mark.django_db
def test_openai_project_cannot_be_claimed_by_another_org_across_parents():
    from selahcue_api.apps.accounts.models import CustomerOrg

    org_a = CustomerOrg.objects.create(name="A", slug="a", idempotency_key="a")
    org_b = CustomerOrg.objects.create(name="B", slug="b", idempotency_key="b")
    now = NOW
    ProviderCredential.objects.create(org=org_a, provider="openai", parent_scope_id="parent-a",
                                      external_project_id="project", created_at=now, updated_at=now)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProviderCredential.objects.create(org=org_b, provider="openai", parent_scope_id="parent-b",
                                          external_project_id="project", created_at=now, updated_at=now)



def begin(org, chosen_scope=DEEPGRAM):
    return begin_mapping(mapping_id=uuid4(), org_id=org.pk, scope=chosen_scope, now=NOW,
                         audit=audit(RegistryReason.PROVISION_INTENT))


def stage(mapping, *, project_id=None, service_id=None, key_id=None, revision=None):
    return bind_provisioning_identity(
        mapping_id=mapping.mapping_id,
        expected_revision=mapping.revision if revision is None else revision,
        identity=ProviderPartialIdentity(mapping.identity.scope, project_id, service_id, key_id),
        now=NOW, audit=audit(RegistryReason.PROVISION_STAGE),
    )


@pytest.mark.django_db
def test_partial_openai_stage_retained_without_claiming_key_or_readiness(provisioner_runtime):
    org = church()
    mapping = begin(org, OPENAI)
    assert mapping.identity.project_id is None and mapping.state == "PROVISIONING"
    with pytest.raises(ProviderRegistryError, match="PREG_IDENTITY_CONFLICT"):
        stage(mapping, key_id="synthetic-key-without-parent")
    pending = stage(mapping, project_id="synthetic-partial-project")
    assert pending.identity.project_id == "synthetic-partial-project"
    assert stage(mapping, project_id="synthetic-partial-project") == pending
    with pytest.raises(ProviderRegistryError, match="PREG_REVISION_CONFLICT"):
        stage(mapping, service_id="synthetic-service-account")
    with pytest.raises(ProviderCustodyError, match="PCUST_IDENTITY_INCOMPLETE"):
        activate_mapping(mapping_id=pending.mapping_id, expected_revision=pending.revision, secret=SECRET,
                         now=NOW, audit=audit(RegistryReason.ACTIVATE))
    failed = fail_mapping(mapping_id=pending.mapping_id, expected_revision=pending.revision,
                          now=NOW, audit=audit(RegistryReason.DEFINITE_FAILURE))
    assert failed.state == "FAILED" and failed.identity.api_key_id is None
    assert load_active_mapping(org.pk, "openai") is None
    row = ProviderCredential.objects.get(pk=pending.mapping_id)
    assert row.external_project_id == "synthetic-partial-project" and row.secret_ciphertext is None


@pytest.mark.django_db
def test_recovery_requires_exact_stage_facts_and_an_actual_secret(provisioner_runtime):
    org = church()
    mapping = begin(org, OPENAI)
    external = identity(OPENAI)

    def recover(mapping, provided):
        return recover_mapping_secret(mapping_id=mapping.mapping_id, expected_revision=mapping.revision,
                                      identity=external, secret=provided, now=NOW,
                                      audit=audit(RegistryReason.RECOVER_EXISTING_SECRET))

    with pytest.raises(ProviderRegistryError, match="PREG_IDENTITY_CONFLICT"):
        recover(mapping, SECRET)
    pending = stage(mapping, project_id=external.project_id, service_id=external.service_account_id,
                    key_id=external.api_key_id)
    with pytest.raises(ProviderCustodyError, match="PCUST_SECRET_INVALID"):
        recover(pending, SecretBytes(b""))
    assert load_active_mapping(org.pk, "openai") is None
    ready = recover(pending, SECRET)
    assert recover(pending, SECRET) == ready
    with pytest.raises(ProviderRegistryError, match="PREG_SECRET_MISMATCH"):
        recover(pending, SecretBytes(b"changed-synthetic-secret"))
    assert load_active_mapping(org.pk, "openai").revision == pending.revision + 1


@pytest.mark.django_db
def test_import_replay_and_refusal_use_exact_json_native_audits(provisioner_runtime, caplog):
    org = church()
    mapping_id = uuid4()
    external = identity(key="synthetic-provider-resource-id")
    context = audit(RegistryReason.IMPORT_APPROVED_ALLOCATION)

    def import_secret(value):
        return import_existing_mapping(mapping_id=mapping_id, org_id=org.pk, identity=external,
                                       secret=value, now=NOW, audit=context)

    ready = import_secret(SECRET)
    assert import_secret(SECRET) == ready
    with pytest.raises(ProviderRegistryError, match="PREG_SECRET_MISMATCH"):
        import_secret(SecretBytes(b"different-synthetic-secret"))
    success, replay, failure = AuditEvent.objects.filter(request_id=str(context.request_id)).order_by("id")
    assert success.actor_kind == "service"
    assert success.source_surface == "provider_registry_internal"
    assert success.action == "provider_registry.IMPORT_APPROVED_ALLOCATION"
    assert success.before == {"evidence_ref": context.evidence_ref, "replayed": False, "error_code": None}
    assert success.after == {
        **success.before, "mapping_id": str(mapping_id), "org_id": org.pk,
        "provider": "deepgram", "parent_scope_id": DEEPGRAM.parent_scope_id,
        "external_project_id": DEEPGRAM.parent_scope_id, "external_service_account_id": None,
        "external_api_key_id": external.api_key_id, "state": "ACTIVE", "revision": 2,
        "wrapping_key_id": "old", "created_at": "2026-11-09T10:00:00.000000Z",
        "updated_at": "2026-11-09T10:00:00.000000Z", "activated_at": "2026-11-09T10:00:00.000000Z",
        "terminal_at": None,
    }
    assert replay.before == replay.after == success.after | {"replayed": True}
    assert failure.result == "FAILED"
    assert failure.after == failure.before == success.after | {"error_code": "PREG_SECRET_MISMATCH"}
    assert "synthetic-reusable-secret" not in caplog.text + str(failure.after)
    assert "different-synthetic-secret" not in caplog.text + str(failure.after)


@pytest.mark.django_db(transaction=True)
def test_web_intent_requires_outer_transaction_and_rolls_back_with_it(provider_mounts):
    org = church()
    provider_mounts("web", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="wsgi")
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        begin(org)
    assert not ProviderCredential.objects.filter(org=org).exists()
    assert AuditEvent.objects.get(action="provider_registry.PROVISION_INTENT").result == "DENIED"
    with transaction.atomic():
        mapping = begin(org)
        row = ProviderCredential.objects.get(pk=mapping.mapping_id)
        assert row.secret_nonce is None and row.external_api_key_id is None
        transaction.set_rollback(True)
    assert not ProviderCredential.objects.filter(org=org).exists()
    assert not AuditEvent.objects.filter(result="SUCCESS", action="provider_registry.PROVISION_INTENT").exists()


@pytest.mark.django_db
def test_web_intent_refuses_missing_admission_and_wrong_policy_evidence(provider_mounts):
    org = church()
    provider_mounts("web", stt=True, provisioning=False, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        begin(org)
    provider_mounts("web", stt=True, provisioning=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        begin(org, ProviderScope("deepgram", "synthetic-unconfigured"))
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        begin_mapping(mapping_id=uuid4(), org_id=org.pk, scope=DEEPGRAM, now=NOW,
                      audit=replace(audit(RegistryReason.PROVISION_INTENT), evidence_ref="synthetic-wrong"))
    assert not ProviderCredential.objects.filter(org=org).exists()


@pytest.mark.django_db
def test_web_cannot_perform_any_other_registry_mutation(provider_mounts):
    org = church()
    provider_mounts("web", stt=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="asgi")
    mapping = begin(org)
    ext = identity()
    for service, reason, extra in (
        (bind_provisioning_identity, RegistryReason.PROVISION_STAGE,
         {"identity": ProviderPartialIdentity(DEEPGRAM, None, None, ext.api_key_id)}),
        (activate_mapping, RegistryReason.ACTIVATE, {"secret": SECRET}),
        (recover_mapping_secret, RegistryReason.RECOVER_EXISTING_SECRET, {"identity": ext, "secret": SECRET}),
        (fail_mapping, RegistryReason.DEFINITE_FAILURE, {}), (retire_mapping, RegistryReason.RETIRE, {}),
    ):
        with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
            service(mapping_id=mapping.mapping_id, expected_revision=mapping.revision,
                    now=NOW, audit=audit(reason), **extra)
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        import_existing_mapping(mapping_id=uuid4(), org_id=org.pk, identity=ext, secret=SECRET,
                                now=NOW, audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION))
    with pytest.raises(ProviderRegistryError, match="PREG_INVALID_CONTEXT"):
        rotate_wrapping_key_batch(after=None, limit=1, now=NOW, audit=audit(RegistryReason.REWRAP))
    assert not load_active_mapping(org.pk, "deepgram")


@pytest.mark.django_db
def test_postgres_history_guard_blocks_bulk_overwrite_delete_and_revival(provisioner_runtime):
    if connection.vendor != "postgresql":
        pytest.skip("Requires the PostgreSQL history trigger.")
    org = church()
    mapping = stage(begin(org), key_id="synthetic-known-key")
    row = ProviderCredential.objects.filter(pk=mapping.mapping_id)
    for values in (
        {"external_api_key_id": "synthetic-replacement-key"},
        {"external_api_key_id": None},
        {"parent_scope_id": "synthetic-other-parent", "external_project_id": "synthetic-other-parent"},
        {"created_at": NOW + timedelta(days=1)},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            row.update(revision=mapping.revision + 1, **values)
    with pytest.raises(IntegrityError), transaction.atomic():
        row.delete()
    failed = fail_mapping(mapping_id=mapping.mapping_id, expected_revision=mapping.revision, now=NOW,
                          audit=audit(RegistryReason.DEFINITE_FAILURE))
    with pytest.raises(IntegrityError), transaction.atomic():
        row.update(state="PROVISIONING", terminal_at=None, revision=failed.revision + 1)
    assert row.get().external_api_key_id == "synthetic-known-key"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("shared_org", [False, True])
def test_postgres_competing_imports_settle_identity_and_owner_uniqueness(shared_org, provisioner_runtime):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL concurrent transactions and constraints.")
    first = church()
    second = first if shared_org else church()
    shared = identity()
    gate = Barrier(2, timeout=10)

    def compete(org, external):
        close_old_connections()
        try:
            gate.wait()
            import_existing_mapping(mapping_id=uuid4(), org_id=org.pk, identity=external, secret=SECRET,
                                    now=NOW, audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION))
            return "success"
        except ProviderRegistryError as error:
            return error.code.value
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(compete, first, shared),
                    pool.submit(compete, second, identity() if shared_org else shared)]
        results = [attempt.result(timeout=15) for attempt in attempts]
    expected = "PREG_OWNERSHIP_CONFLICT" if shared_org else "PREG_IDENTITY_CONFLICT"
    assert sorted(results) == [expected, "success"]
    assert ProviderCredential.objects.filter(state="ACTIVE").count() == 1



@pytest.mark.django_db
def test_retirement_does_not_allow_same_provider_key_to_be_reassigned(provisioner_runtime):
    org = church()
    external = identity()
    ready = import_existing_mapping(
        mapping_id=uuid4(), org_id=org.pk, identity=external, secret=SECRET, now=NOW,
        audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION),
    )
    retire_mapping(mapping_id=ready.mapping_id, expected_revision=2, now=NOW,
                   audit=audit(RegistryReason.RETIRE))
    with pytest.raises(ProviderRegistryError, match="PREG_IDENTITY_CONFLICT"):
        import_existing_mapping(mapping_id=uuid4(), org_id=church().pk, identity=external,
                                secret=SECRET, now=NOW, audit=audit(RegistryReason.IMPORT_APPROVED_ALLOCATION))
    assert ProviderCredential.objects.get(pk=ready.mapping_id).state == "RETIRED"
