"""PostgreSQL coverage for complete provider lifecycle and exceptional replay."""
import json
from collections import deque
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection, transaction

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.providers import configuration, provisioning, provisioning_tasks, registry
from selahcue_api.apps.providers.adapters import deepgram_admin, transport
from selahcue_api.apps.providers.adapters.contracts import CleanupConfirmed, Created, MutationUnknown
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.capacity import mutate
from selahcue_api.apps.providers.contracts import (
    AdminOperation as Op,
    CleanupAuthorization,
    ProviderCleanupConfirmation,
    ProviderPartialIdentity,
    ProvisioningAuditContext,
    ProvisioningErrorCode,
    ProvisioningRejected,
    RecoveryEvidenceKind,
    RegistryAuditContext,
    RegistryReason,
)
from selahcue_api.apps.providers.custody import open_secret
from selahcue_api.apps.providers.models import (
    ProviderCapacityPool,
    ProviderCreateAllowance,
    ProviderCredential,
    ProviderExternalResource,
    ProviderProvisioningOutbox,
    ProviderRecoveryEvidence,
    ProviderResourceClaim,
    ProvisioningAttempt,
    ProvisioningDemand,
    ProvisioningStage,
)
from selahcue_api.apps.providers.policy_publication import publish_provider_policy
from selahcue_api.celery import app as celery_app

from provider_helpers import DEEPGRAM, OPENAI, provider_mounts  # noqa: F401
from test_provider_provisioning import NOW, admitted_pool, make_demand, mark_scan_complete  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)
PROJECTS = "/v1/organization/projects"
PROJECT = "synthetic-project-id"
ACCOUNT = "synthetic-account-id"
KEY = "synthetic-key-id"
SECRET = "synthetic-one-time-lifecycle-secret"
KEY_PATH = f"{PROJECTS}/{PROJECT}/api_keys/{KEY}"
ACCOUNTS_PATH = f"{PROJECTS}/{PROJECT}/service_accounts"
ACCOUNT_PATH = f"{ACCOUNTS_PATH}/{ACCOUNT}"
ARCHIVE_PATH = f"{PROJECTS}/{PROJECT}/archive"


@pytest.fixture(autouse=True)
def postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("Provider lifecycle tests exercise PostgreSQL history guards and connection closure.")


def clock(seconds=0):
    return lambda: NOW + timedelta(seconds=seconds)


def audit(reference):
    return ProvisioningAuditContext("synthetic-operator", uuid4(), reference)


def response(body):
    return transport._Response(200, "synthetic-http-request", json.dumps(body).encode())


def project_receipt(project=PROJECT):
    return response({"object": "organization.project", "id": project, "created_at": int(NOW.timestamp())})


def account_receipt(expiry, *, account=ACCOUNT, key_id=KEY):
    key = {"id": key_id, "value": SECRET}
    if expiry != "missing":
        key["expires_at"] = None if expiry == "none" else int((NOW + timedelta(days=1)).timestamp())
    return response({
        "object": "organization.project.service_account", "id": account,
        "created_at": int(NOW.timestamp()), "api_key": key,
    })


def openai_http(monkeypatch, *responses):
    remaining = deque(responses)
    calls = []

    def send(operation, credential):
        assert credential.scope == OPENAI
        calls.append((operation.method, operation.path, operation.body))
        assert remaining, f"Unexpected operation {operation.method} {operation.path}"
        method, path, result = remaining.popleft()
        assert (operation.method, operation.path) == (method, path)
        return result() if callable(result) else result

    monkeypatch.setattr(transport, "_send", send)
    return calls, remaining


@pytest.fixture
def openai_chain(provider_mounts):
    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(OPENAI, "synthetic-cleanup-authority"),),
        audit=audit("publish-policy"), clock=clock(),
    )
    pool = ProviderCapacityPool.objects.get(provider="openai")
    mark_scan_complete(pool, NOW)

    provider_mounts("web", notes=True, capable=True, provisioning=True)
    # Actual startup must still reject notes. The controlled config below only
    # exercises the not-yet-wired OpenAI provisioning algorithm.
    with pytest.raises(configuration.ProviderConfigurationError, match="PCFG_NOTES_RUNTIME_UNAVAILABLE"):
        initialize_provider_runtime(entrypoint="wsgi")
    configuration._load("web", entrypoint="wsgi")
    context, token = make_demand()
    pending = provisioning.ensure_provider_ready(
        replace(context, meter="notes"), authenticated_token_id=token.pk, clock=clock(),
    )
    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    return pool, pending.mapping_id, token


@pytest.mark.parametrize("eligible", [True, False], ids=["continue-account", "cancel-and-archive"])
def test_late_project_ownership_prepares_unsent_account_stage(openai_chain, monkeypatch, eligible):
    pool, mapping_id, token = openai_chain

    def late_project_receipt():
        attempt = ProvisioningAttempt.objects.get(stage__operation=Op.OA_CREATE_PROJECT)
        assert provisioning.recover_provisioning_attempt(attempt.pk, clock=clock(31)).state == "OUTCOME_UNKNOWN"
        assert provisioning.recover_provisioning_attempt(attempt.pk, clock=clock(36)).requires_operator_recovery
        return project_receipt()

    operations = [
        ("POST", PROJECTS, late_project_receipt),
        ("GET", PROJECTS, response({"has_more": False, "data": [{
            "id": PROJECT, "name": f"scp1-{mapping_id}-oaproj", "status": "active",
            "created_at": int(NOW.timestamp()),
        }]})),
    ]
    if eligible:
        operations.append(("POST", ACCOUNTS_PATH, account_receipt("none")))
    else:
        operations.append(("POST", ARCHIVE_PATH, archive_receipt()))
    calls, remaining = openai_http(monkeypatch, *operations)
    instants = iter((NOW, clock(37)()))
    assert provisioning.provision_mapping(mapping_id, clock=lambda: next(instants)).state == "FAILED"
    project = ProvisioningAttempt.objects.get(stage__operation=Op.OA_CREATE_PROJECT)
    account = ProvisioningStage.objects.get(operation=Op.OA_CREATE_SERVICE_ACCOUNT_KEY)
    allowance = ProviderCreateAllowance.objects.get(stage=account)
    assert (project.state, account.state, account.current_attempt_id, allowance.state) == (
        "SUCCEEDED", "BLOCKED", None, "HELD",
    )

    provisioning.record_recovery_evidence(
        pool_id=pool.pk, mapping_id=mapping_id, attempt_id=project.pk, kind=RecoveryEvidenceKind.OWNERSHIP,
        identity=ProviderPartialIdentity(OPENAI, PROJECT, None, None), audit=audit("fresh-project-ownership"),
        clock=clock(38),
    )
    account.refresh_from_db()
    assert account.state == "READY" and account.target_project_id == PROJECT
    assert account.current_attempt.state == "PREPARED" and account.current_attempt.sequence == 1
    assert ProviderCreateAllowance.objects.get(stage=account).pk == allowance.pk
    assert ProviderCreateAllowance.objects.count() == 2
    assert len(calls) == 2  # Evidence recording never issues HTTP.
    if not eligible:
        token.delete()

    original_outbox = ProviderProvisioningOutbox.objects.get(mapping_id=mapping_id, kind="PROVISION", state="PENDING")
    monkeypatch.setattr(celery_app, "send_task", lambda *args, **kwargs: None)
    provisioning_tasks.publish_outbox(original_outbox.pk, clock=clock(38))
    with transaction.atomic():
        delivered = ProviderProvisioningOutbox.objects.select_for_update().get(pk=original_outbox.pk)
        assert delivered.state == "SENT"
        # Simulate a lost worker after delivery with its prepared attempt still due.
        mutate(delivered, clock(38)(), state="ACKED", acked_at=clock(38)())
    provisioning_tasks.sweep_provisioning(clock=clock(39))
    recovered_outbox = ProviderProvisioningOutbox.objects.get(mapping_id=mapping_id, kind="PROVISION", state="PENDING")
    assert recovered_outbox.generation == original_outbox.generation + 1
    assert len(calls) == 2
    provisioning_tasks.publish_outbox(recovered_outbox.pk, clock=clock(39))
    result = provisioning._provision_mapping(
        mapping_id, clock=clock(39), outbox_id=recovered_outbox.pk, enough_time=lambda: True,
    )
    if eligible:
        assert result.state == "READY"
        assert ProviderCreateAllowance.objects.get(pk=allowance.pk).state == "DISPATCHED"
    else:
        assert result.state == "RECOVERY_REQUIRED"
        account.refresh_from_db()
        assert account.state == "CANCELLED" and account.current_attempt.dispatch_started_at is None
        assert ProviderCreateAllowance.objects.get(pk=allowance.pk).state == "RELEASED"
        assert provisioning.provision_mapping(mapping_id, clock=clock(40)).state == "RECOVERY_REQUIRED"
        assert provisioning.provision_mapping(mapping_id, clock=clock(41)).state == "WAITING_CAPACITY"
        assert ProviderCredential.objects.get(pk=mapping_id).state == "RETIRED"
    assert not remaining
    assert sum(method == "POST" and path == PROJECTS for method, path, _ in calls) == 1
    assert ProviderResourceClaim.objects.get().state == "COUNTED"
    assert ProviderExternalResource.objects.get().count_state == "COUNTED"


@pytest.mark.parametrize(("expiry", "state", "result_code"), [
    ("none", "READY", None),
    ("missing", "RECOVERY_REQUIRED", ProvisioningErrorCode.RESPONSE_INVALID),
    ("finite", "RECOVERY_REQUIRED", ProvisioningErrorCode.UNSUPPORTED_EXPIRY),
])
def test_openai_combined_receipt_binds_and_seals_only_explicit_null(openai_chain, monkeypatch, expiry, state, result_code):
    _, mapping_id, _ = openai_chain
    calls, remaining = openai_http(
        monkeypatch, ("POST", PROJECTS, project_receipt()), ("POST", ACCOUNTS_PATH, account_receipt(expiry)),
    )
    assert provisioning.provision_mapping(mapping_id, clock=clock()).state == "WORKING"
    assert provisioning.provision_mapping(mapping_id, clock=clock(1)).state == state
    assert not remaining
    assert [body for _, _, body in calls] == [
        {"name": f"scp1-{mapping_id}-oaproj"}, {"name": f"scp1-{mapping_id}-oasvc"},
    ]
    row = ProviderCredential.objects.get(pk=mapping_id)
    demand = ProvisioningDemand.objects.get()
    attempt = ProvisioningAttempt.objects.get(stage__operation=Op.OA_CREATE_SERVICE_ACCOUNT_KEY)
    assert (row.external_project_id, row.external_service_account_id, row.external_api_key_id) == (PROJECT, ACCOUNT, KEY)
    assert (attempt.observed_project_id, attempt.observed_service_account_id, attempt.observed_api_key_id) == (PROJECT, ACCOUNT, KEY)
    assert demand.last_error_code == result_code
    if expiry == "none":
        assert row.state == "ACTIVE" and row.secret_ciphertext and SECRET.encode() not in row.secret_ciphertext
        assert row.activated_at == clock(1)()
        assert open_secret(row).value == SECRET.encode()
    else:
        assert row.state == "PROVISIONING" and row.secret_ciphertext is None and row.activated_at is None
    assert ProviderCreateAllowance.objects.filter(state="DISPATCHED").count() == 2
    assert SECRET not in repr(list(AuditEvent.objects.values("after", "before")))
    assert SECRET not in repr(list(ProviderProvisioningOutbox.objects.values()))


def key_revocation_receipt():
    return response({"id": KEY, "deleted": True})


def archive_receipt(project=PROJECT):
    return response({"object": "organization.project", "id": project, "status": "archived",
                     "archived_at": int((NOW + timedelta(seconds=5)).timestamp())})


def begin_openai_cleanup(mapping_id):
    assert provisioning.provision_mapping(mapping_id, clock=clock()).state == "WORKING"
    assert provisioning.provision_mapping(mapping_id, clock=clock(1)).state == "RECOVERY_REQUIRED"
    assert provisioning.provision_mapping(mapping_id, clock=clock(2)).state == "RECOVERY_REQUIRED"
    assert provisioning.provision_mapping(mapping_id, clock=clock(3)).state == "RECOVERY_REQUIRED"


def confirm_target(pool, mapping_id, operation, identity):
    attempt = ProvisioningAttempt.objects.get(stage__claim__mapping_id=mapping_id, stage__operation=operation)
    return ProviderCleanupConfirmation(pool.pk, mapping_id, attempt.pk, operation, identity)


def snapshot_lifecycle():
    """Compare persisted chain, proof, tracking and accounting across a replay."""
    tables = (
        (ProvisioningDemand, ("pk", "current_mapping_id", "state", "replacement_count", "updated_at")),
        (ProviderCredential, ("pk", "state", "revision", "terminal_at")),
        (ProviderResourceClaim, ("pk", "mapping_id", "state", "resource_id", "previous_claim_id",
                                 "released_at", "cleanup_required_operations")),
        (ProviderExternalResource, ("pk", "count_state", "exclusion_evidence_id", "last_seen_at")),
        (ProviderCreateAllowance, ("pk", "state", "attempt_id", "dispatched_at", "released_at")),
        (ProvisioningStage, ("pk", "state", "current_attempt_id", "attempt_count")),
        (ProvisioningAttempt, ("pk", "state", "completed_at", "cleanup_completion_evidence_id")),
        (ProviderRecoveryEvidence, ("pk", "kind", "observed_at", "attempt_id")),
        (ProviderProvisioningOutbox, ("pk", "state", "generation", "available_at", "mapping_id")),
    )
    return tuple(list(model.objects.order_by("pk").values_list(*fields)) for model, fields in tables)


def test_openai_full_cleanup_waits_for_unknown_account_confirmation(openai_chain, monkeypatch):
    pool, mapping_id, token = openai_chain
    token.expires_at = NOW + timedelta(hours=2)
    token.save(update_fields=["expires_at"])
    successor_project, successor_account, successor_key = (
        f"{PROJECT}-replacement", f"{ACCOUNT}-replacement", f"{KEY}-replacement",
    )
    successor_path = f"{PROJECTS}/{successor_project}"
    calls, remaining = openai_http(
        monkeypatch, ("POST", PROJECTS, project_receipt()), ("POST", ACCOUNTS_PATH, account_receipt("finite")),
        ("DELETE", KEY_PATH, key_revocation_receipt()),
        ("DELETE", ACCOUNT_PATH, transport._Failure("possible_dispatch", "READ_TIMEOUT")),
        ("POST", ARCHIVE_PATH, archive_receipt()),
        ("GET", PROJECTS, response({"has_more": False, "data": [{"id": PROJECT, "status": "archived"}]})),
        ("POST", PROJECTS, project_receipt(successor_project)),
        ("POST", f"{successor_path}/service_accounts",
         account_receipt("finite", account=successor_account, key_id=successor_key)),
        ("DELETE", f"{successor_path}/api_keys/{successor_key}", response({"id": successor_key, "deleted": True})),
        ("DELETE", f"{successor_path}/service_accounts/{successor_account}",
         response({"object": "organization.project.service_account.deleted", "id": successor_account, "deleted": True})),
        ("POST", f"{successor_path}/archive", archive_receipt(successor_project)),
    )
    begin_openai_cleanup(mapping_id)
    claim = ProviderResourceClaim.objects.get(mapping_id=mapping_id)
    assert claim.cleanup_required_operations == [Op.OA_REVOKE_KEY, Op.OA_DELETE_SERVICE_ACCOUNT, Op.OA_ARCHIVE_PROJECT]
    stage_targets = {
        operation: (project, account, key)
        for operation, project, account, key in ProvisioningStage.objects.filter(
            claim=claim, operation__in=claim.cleanup_required_operations,
        ).values_list("operation", "target_project_id", "target_service_account_id", "target_api_key_id")
    }
    assert [stage_targets[operation] for operation in claim.cleanup_required_operations] == [
        (PROJECT, ACCOUNT, KEY), (PROJECT, ACCOUNT, None), (PROJECT, None, None),
    ]
    assert provisioning.provision_mapping(mapping_id, clock=clock(4)).state == "RECOVERY_REQUIRED"
    assert ProviderCredential.objects.get(pk=mapping_id).state == "PROVISIONING"
    assert ProvisioningDemand.objects.get().replacement_count == 0
    assert provisioning.provision_mapping(mapping_id, clock=clock(5)).state == "RECOVERY_REQUIRED"
    assert len(calls) == 4
    assert ProviderCredential.objects.get(pk=mapping_id).state == "PROVISIONING"
    proof = confirm_target(pool, mapping_id, Op.OA_DELETE_SERVICE_ACCOUNT, ProviderPartialIdentity(OPENAI, PROJECT, ACCOUNT, None))
    recorded = provisioning.confirm_provider_cleanup(proof, audit=audit("operator-confirmed-account-delete"), clock=clock(6))
    attempt = ProvisioningAttempt.objects.get(pk=proof.attempt_id)
    assert recorded.chain_state == "RECOVERY_REQUIRED" and len(calls) == 4
    assert attempt.state == "SUCCEEDED" and attempt.cleanup_completion_evidence_id == recorded.evidence_id
    assert ProviderCredential.objects.get(pk=mapping_id).state == "PROVISIONING"
    assert ProviderResourceClaim.objects.count() == 1
    assert provisioning.provision_mapping(mapping_id, clock=clock(7)).state == "WAITING_CAPACITY"
    assert ProviderCredential.objects.get(pk=mapping_id).state == "RETIRED"
    assert [path for _, path, _ in calls[2:]] == [KEY_PATH, ACCOUNT_PATH, ARCHIVE_PATH]
    claim.refresh_from_db()
    assert claim.state == "COUNTED" and claim.resource.count_state == "COUNTED"
    assert ProvisioningDemand.objects.get().replacement_count == 0
    # Both create tokens still count in the hourly window. A replacement is
    # neither allocated before the final proof nor while that budget is spent.
    assert provisioning.provision_mapping(mapping_id, clock=clock(8)).state == "WAITING_CAPACITY"
    assert ProviderResourceClaim.objects.count() == 1
    assert ProviderCreateAllowance.objects.count() == 2
    assert len(calls) == 5

    # After the rate window rolls and a fresh scan confirms the archived project
    # is still counted, one replacement can consume the now-available rate.
    scan_id = provisioning_tasks.refresh_inventory(pool.pk, clock=clock(3601))
    provisioning_tasks.inventory_page(scan_id, clock=clock(3601))
    replacement = provisioning.provision_mapping(mapping_id, clock=clock(3601))
    assert replacement.state == "QUEUED" and replacement.mapping_id != mapping_id
    for second, state in (
        (3602, "WORKING"), (3603, "RECOVERY_REQUIRED"), (3604, "RECOVERY_REQUIRED"),
        (3605, "RECOVERY_REQUIRED"), (3606, "RECOVERY_REQUIRED"), (3607, "FAILED"),
    ):
        assert provisioning.provision_mapping(replacement.mapping_id, clock=clock(second)).state == state
    assert provisioning.provision_mapping(replacement.mapping_id, clock=clock(3608)).state == "FAILED"
    assert not remaining
    demand = ProvisioningDemand.objects.get()
    assert demand.current_mapping_id == replacement.mapping_id and demand.replacement_count == 1
    assert ProviderResourceClaim.objects.get(generation=1).previous_claim_id == claim.pk
    assert ProviderExternalResource.objects.filter(count_state="COUNTED").count() == 2
    assert ProviderCreateAllowance.objects.filter(state="DISPATCHED").count() == 4


def test_retired_incomplete_openai_cleanup_refuses_corroboration_atomically(openai_chain, monkeypatch):
    pool, mapping_id, _ = openai_chain
    calls, remaining = openai_http(
        monkeypatch, ("POST", PROJECTS, project_receipt()), ("POST", ACCOUNTS_PATH, account_receipt("finite")),
        ("DELETE", KEY_PATH, key_revocation_receipt()),
    )
    begin_openai_cleanup(mapping_id)
    row = ProviderCredential.objects.get(pk=mapping_id)
    # Use the existing registry API to model a retained retired mapping whose
    # Task 4 plan did not finish, keeping PostgreSQL history guards active.
    registry.retire_mapping(mapping_id=mapping_id, expected_revision=row.revision, now=clock(4)(),
                            audit=RegistryAuditContext("synthetic-operator", uuid4(), RegistryReason.RETIRE,
                                                       "independent-registry-retirement"))
    proof = confirm_target(pool, mapping_id, Op.OA_REVOKE_KEY, ProviderPartialIdentity(OPENAI, PROJECT, ACCOUNT, KEY))
    assert ProvisioningStage.objects.get(operation=Op.OA_DELETE_SERVICE_ACCOUNT).state != "DONE"
    before = snapshot_lifecycle()
    audits_before = AuditEvent.objects.count()
    with pytest.raises(ProvisioningRejected, match="IDENTITY_CONFLICT"):
        provisioning.confirm_provider_cleanup(proof, audit=audit("corroborate-only-revocation"), clock=clock(5))
    assert snapshot_lifecycle() == before and AuditEvent.objects.count() == audits_before
    assert len(calls) == 3 and not remaining


def test_old_cleanup_proof_replays_without_changing_progressed_and_terminal_successor(
    admitted_pool, provider_mounts, monkeypatch,
):
    ctx, token = make_demand()
    original = provisioning.ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=clock()).mapping_id
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")

    calls = []

    def mutate_key(request, credential):
        calls.append((request.operation, request.mapping_id))
        identity = ProviderPartialIdentity(
            request.scope, request.project_id, None, request.api_key_id or f"key-{request.mapping_id}",
        )
        if request.operation == Op.DG_CREATE_KEY:
            return Created(identity, None, NOW + timedelta(days=1), "synthetic-confirmed-create", NOW)
        if request.mapping_id == original:
            return MutationUnknown(ProvisioningErrorCode.CLEANUP_UNKNOWN, identity)
        return CleanupConfirmed(identity, "synthetic-confirmed-revoke")

    monkeypatch.setattr(deepgram_admin, "mutate", mutate_key)
    for second in (0, 1, 2):
        assert provisioning.provision_mapping(original, clock=clock(second)).state == "RECOVERY_REQUIRED"
    attempt = ProvisioningAttempt.objects.get(stage__claim__mapping_id=original, stage__operation=Op.DG_REVOKE_KEY)
    proof = ProviderCleanupConfirmation(
        admitted_pool.pk, original, attempt.pk, Op.DG_REVOKE_KEY,
        ProviderPartialIdentity(DEEPGRAM, admitted_pool.parent_scope_id, None, f"key-{original}"),
    )
    approval = audit("confirm-generation-zero-revoke")
    first = provisioning.confirm_provider_cleanup(proof, audit=approval, clock=clock(3))
    assert first.chain_state == "WAITING_CAPACITY"
    successor = provisioning.provision_mapping(original, clock=clock(4)).mapping_id
    assert successor != original
    assert provisioning.provision_mapping(successor, clock=clock(5)).state == "RECOVERY_REQUIRED"
    for state, second in (("RECOVERY_REQUIRED", 6), ("FAILED", 9)):
        before = snapshot_lifecycle()
        before_calls = tuple(calls)
        replayed = provisioning.confirm_provider_cleanup(proof, audit=approval, clock=clock(second))
        assert replayed.replayed and replayed.evidence_id == first.evidence_id and replayed.chain_state == state
        assert tuple(calls) == before_calls and snapshot_lifecycle() == before
        demand = ProvisioningDemand.objects.get()
        assert demand.current_mapping_id == successor and demand.replacement_count == 1 and demand.state == state
        attempt.refresh_from_db()
        assert attempt.cleanup_completion_evidence_id == first.evidence_id and attempt.completed_at == clock(3)()
        if state == "RECOVERY_REQUIRED":
            assert provisioning.provision_mapping(successor, clock=clock(7)).state == "RECOVERY_REQUIRED"
            assert provisioning.provision_mapping(successor, clock=clock(8)).state == "FAILED"
    assert ProviderCreateAllowance.objects.filter(state="DISPATCHED").count() == 2
    assert ProviderResourceClaim.objects.filter(state="COUNTED").count() == 2
    assert ProviderExternalResource.objects.filter(count_state="COUNTED").count() == 2
    assert calls == [(Op.DG_CREATE_KEY, original), (Op.DG_REVOKE_KEY, original),
                     (Op.DG_CREATE_KEY, successor), (Op.DG_REVOKE_KEY, successor)]
