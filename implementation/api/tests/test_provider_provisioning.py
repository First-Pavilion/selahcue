"""Eligibility is tied to the original demand and the bounded validity windows."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from selahcue_api.apps.devices import services
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.providers import configuration
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import ConfigErrorCode, ProviderConfigurationError

from provider_helpers import provider_mounts  # noqa: F401


pytestmark = pytest.mark.django_db(transaction=True)

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def test_commercial_service_uses_explicit_utc_instant():
    key = AppLicenseKey(status="ISSUED", starts_at=NOW, expires_at=NOW + timedelta(hours=1))
    assert services.license_allows_commercial_service(key, at=NOW)
    assert not services.license_allows_commercial_service(key, at=key.expires_at)
    with pytest.raises(ValueError):
        services.license_allows_commercial_service(key, at=NOW.replace(tzinfo=None))


def test_exact_token_and_org_allowlist():
    from selahcue_api.apps.devices.cloud_eligibility import CloudEligibilityFacts, cloud_eligibility

    facts = CloudEligibilityFacts(
        1, "ACTIVE", 2, 1, "ISSUED", NOW, NOW + timedelta(hours=1),
        3, 1, 2, "ACTIVE", 4, 3, "ACTIVE", NOW, NOW + timedelta(minutes=1),
    )
    for status in ("PROSPECT", "TRIAL", "ACTIVE", "PAST_DUE"):
        assert cloud_eligibility(replace(facts, org_status=status), at=NOW)
    for invalid in (
        replace(facts, org_status="SUSPENDED"), replace(facts, token_status="REVOKED"),
        replace(facts, token_id=True), replace(facts, token_device_id=7),
        replace(facts, device_license_id=9), replace(facts, license_org_id=7),
        replace(facts, license_status="SUSPENDED"), replace(facts, token_issued_at=NOW + timedelta(seconds=1)),
    ):
        assert not cloud_eligibility(invalid, at=NOW)
    assert not cloud_eligibility(facts, at=facts.token_expires_at)


def test_create_cannot_boot_without_global_budgets(provider_mounts):
    provider_mounts("provisioner", provisioning=True, capable=True, budgets=False)
    with pytest.raises(ProviderConfigurationError) as error:
        initialize_provider_runtime(entrypoint="operator")
    assert error.value.code == ConfigErrorCode.PCFG_CAPABILITY_UNCONFIGURED


def test_initialized_role_cannot_change_entrypoint(provider_mounts):
    provider_mounts("provisioner")
    initialize_provider_runtime(entrypoint="celery_worker")
    with pytest.raises(ProviderConfigurationError) as error:
        initialize_provider_runtime(entrypoint="operator")
    assert error.value.code == ConfigErrorCode.PCFG_ROLE_MISMATCH


def test_policy_publication_is_role_bound_and_replays_same_epochs(provider_mounts):
    from uuid import uuid4

    from selahcue_api.apps.providers.contracts import ProvisioningAuditContext, CleanupAuthorization
    from selahcue_api.apps.providers.models import ProviderInventoryScan
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy

    provider_mounts("provisioner", capable=True)
    config = initialize_provider_runtime(entrypoint="celery_worker")
    audit = ProvisioningAuditContext("synthetic-operator", uuid4(), "test-receipt")
    with pytest.raises(ProviderConfigurationError) as error:
        publish_provider_policy(cleanup_authorizations=(), audit=audit, clock=lambda: NOW)
    assert error.value.code == ConfigErrorCode.PCFG_ROLE_MISMATCH

    provider_mounts("provisioner", capable=True)
    initialize_provider_runtime(entrypoint="operator")
    first = publish_provider_policy(cleanup_authorizations=(), audit=audit, clock=lambda: NOW)
    second = publish_provider_policy(cleanup_authorizations=(), audit=audit, clock=lambda: NOW)
    assert first == second
    assert len(first.scope_epochs) == 2
    assert ProviderInventoryScan.objects.count() == 2
    third = publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(config.policy.scopes[0].scope, "exact-lifecycle-receipt"),),
        audit=audit, clock=lambda: NOW,
    )
    assert third.scope_epochs[0] != first.scope_epochs[0]
    assert third.scope_epochs[1] == first.scope_epochs[1]
    assert ProviderInventoryScan.objects.count() == 3


def make_demand():
    from uuid import uuid4
    from selahcue_api.apps.devices.models import DeviceToken
    from test_effective_org_plan import church, licence, device, context

    inst = device(licence(church()))
    token = DeviceToken.objects.create(
        device=inst, token_prefix="test", token_suffix="test", masked_token="test",
        token_hash="synthetic", token_fingerprint=uuid4().hex, issued_at=NOW,
        expires_at=NOW + timedelta(minutes=20),
    )
    return context(inst, "stt", at=NOW), token


@pytest.fixture
def admitted_pool(provider_mounts):
    from uuid import uuid4

    from selahcue_api.apps.providers.contracts import ProvisioningAuditContext, CleanupAuthorization
    from provider_helpers import DEEPGRAM
    from selahcue_api.apps.providers.models import ProviderCapacityPool, ProviderInventoryScan
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy

    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(DEEPGRAM, "verified-lifecycle-fixture"),),
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "fixture"),
        clock=lambda: NOW,
    )
    pool = ProviderCapacityPool.objects.get(provider="deepgram")
    scan = ProviderInventoryScan.objects.get(pool=pool)
    scan.state = "COMPLETE"
    scan.finished_at = NOW
    scan.terminal_page_seen = True
    scan.save()
    pool.latest_complete_scan = scan
    pool.inventory_valid_until = NOW + timedelta(minutes=5)
    pool.save()
    provider_mounts("web", stt=True, provisioning=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")
    return pool


def test_duplicate_admission_reuses_original_intent(admitted_pool):
    from selahcue_api.apps.providers.contracts import ProvisioningPending
    from selahcue_api.apps.providers.models import ProviderProvisioningOutbox, ProviderResourceClaim, ProvisioningDemand
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready
    from selahcue_api.apps.usage.models import UsageReservation

    ctx, token = make_demand()
    assert ProvisioningDemand.objects.count() == 0
    replies = [ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW) for _ in range(100)]
    assert isinstance(replies[0], ProvisioningPending)
    assert all(reply == replies[0] for reply in replies)
    assert ProvisioningDemand.objects.get().trigger_token_pk == token.pk
    assert ProviderProvisioningOutbox.objects.filter(kind="PROVISION").count() == 1
    assert ProviderResourceClaim.objects.get().slot == 1
    assert UsageReservation.objects.count() == 0


def test_stale_scan_denies_new_resource_and_exact_expired_token_denies_eligibility(admitted_pool):
    from selahcue_api.apps.providers.contracts import CapacityUnavailable, CapacityUnavailableCode, ProvisioningRejected
    from selahcue_api.apps.providers.models import ProviderResourceClaim
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    ctx, token = make_demand()
    assert ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: admitted_pool.inventory_valid_until) == (
        CapacityUnavailable(CapacityUnavailableCode.POLICY_UNCONFIGURED)
    )
    with pytest.raises(ProvisioningRejected, match="INELIGIBLE"):
        ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: token.expires_at)
    assert ProviderResourceClaim.objects.count() == 0


def test_unknown_create_does_not_dispatch_again_on_poll_or_empty_metadata(admitted_pool, provider_mounts, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import InventoryPage, MutationUnknown
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, ProvisioningErrorCode
    from selahcue_api.apps.providers.models import ProviderCreateAllowance, ProviderResourceClaim, ProvisioningAttempt
    from selahcue_api.apps.providers.provisioning import (
        ensure_provider_ready, provision_mapping, recover_provisioning_attempt,
    )

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    mutations = []

    def lose_response(request, credential):
        mutations.append(request.marker)
        return MutationUnknown(ProvisioningErrorCode.OUTCOME_UNKNOWN,
                               ProviderPartialIdentity(request.scope, request.project_id, None, None))

    monkeypatch.setattr(deepgram_admin, "mutate", lose_response)
    monkeypatch.setattr(deepgram_admin, "list_page", lambda *_: InventoryPage((), None, True))
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW).state == "RECOVERY_REQUIRED"
    attempt = ProvisioningAttempt.objects.get()
    assert attempt.state == "OUTCOME_UNKNOWN"
    assert recover_provisioning_attempt(attempt.pk, clock=lambda: NOW + timedelta(seconds=5)).state == "OUTCOME_UNKNOWN"
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW + timedelta(seconds=6)).state == "RECOVERY_REQUIRED"
    assert len(mutations) == 1
    assert ProvisioningAttempt.objects.count() == 1
    assert ProviderResourceClaim.objects.get().state == "HELD"
    assert ProviderCreateAllowance.objects.get().state == "DISPATCHED"


def test_operator_confirmation_closes_exact_cleanup_without_second_mutation(admitted_pool, provider_mounts, monkeypatch):
    from uuid import uuid4

    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import Created, MutationUnknown
    from selahcue_api.apps.providers.contracts import (
        AdminOperation, ProviderCleanupConfirmation, ProviderPartialIdentity, ProvisioningAuditContext,
        ProvisioningErrorCode, ProvisioningRejected, RecoveryEvidenceKind,
    )
    from selahcue_api.apps.providers.models import (
        ProviderCredential, ProviderRecoveryEvidence, ProviderResourceClaim, ProvisioningAttempt, ProvisioningDemand,
    )
    from selahcue_api.apps.providers.provisioning import (
        confirm_provider_cleanup, ensure_provider_ready, provision_mapping, record_recovery_evidence,
    )

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    mutations = []

    def response(request, credential):
        mutations.append(request.operation)
        identity = ProviderPartialIdentity(request.scope, request.project_id, None, "owned-key")
        if request.operation == AdminOperation.DG_CREATE_KEY:
            return Created(identity, None, NOW + timedelta(days=1), "test-create-receipt", NOW)
        return MutationUnknown(ProvisioningErrorCode.CLEANUP_UNKNOWN, identity)

    monkeypatch.setattr(deepgram_admin, "mutate", response)
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW).state == "RECOVERY_REQUIRED"
    assert not ProviderCredential.objects.get(pk=pending.mapping_id).secret_ciphertext
    token.delete()  # Cleanup must finish even if the original customer is no longer eligible.
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW + timedelta(seconds=5)).state == "RECOVERY_REQUIRED"
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW + timedelta(seconds=6)).state == "RECOVERY_REQUIRED"
    attempt = ProvisioningAttempt.objects.get(stage__operation=AdminOperation.DG_REVOKE_KEY)
    assert attempt.state == "OUTCOME_UNKNOWN"
    identity = ProviderPartialIdentity(request_scope(admitted_pool),
                                       admitted_pool.parent_scope_id, None, "owned-key")
    confirmation = ProviderCleanupConfirmation(admitted_pool.pk, pending.mapping_id, attempt.pk,
                                               AdminOperation.DG_REVOKE_KEY, identity)
    audit = ProvisioningAuditContext("synthetic-operator", uuid4(), "separate-provider-verification")
    at = NOW + timedelta(seconds=7)
    with pytest.raises(ProvisioningRejected, match="INVALID_CONTEXT"):
        confirm_provider_cleanup(replace(confirmation, identity=replace(identity, api_key_id="wrong-key")),
                                 audit=audit, clock=lambda: at)
    with pytest.raises(ProvisioningRejected, match="INVALID_CONTEXT"):
        record_recovery_evidence(pool_id=admitted_pool.pk, mapping_id=pending.mapping_id, attempt_id=attempt.pk,
                                 kind=RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED, identity=identity,
                                 audit=audit, clock=lambda: at)
    first = confirm_provider_cleanup(confirmation, audit=audit, clock=lambda: at)
    replay = confirm_provider_cleanup(confirmation, audit=audit, clock=lambda: at + timedelta(seconds=1))
    assert first.replayed is False
    assert replay.evidence_id == first.evidence_id and replay.replayed is True
    assert first.chain_state == "WAITING_CAPACITY"
    attempt.refresh_from_db()
    assert attempt.completed_at == at and attempt.cleanup_completion_evidence_id == first.evidence_id
    with pytest.raises(ProvisioningRejected, match="IDENTITY_CONFLICT"):
        confirm_provider_cleanup(confirmation, audit=replace(audit, request_id=uuid4()), clock=lambda: at)
    assert ProviderResourceClaim.objects.get().state == "COUNTED"
    assert ProviderRecoveryEvidence.objects.filter(kind=RecoveryEvidenceKind.PROVIDER_CLEANUP_CONFIRMED).count() == 1
    assert provision_mapping(pending.mapping_id, clock=lambda: at).state == "FAILED"
    assert confirm_provider_cleanup(confirmation, audit=audit, clock=lambda: at).chain_state == "FAILED"
    assert ProvisioningDemand.objects.get().replacement_count == 0
    assert mutations == [AdminOperation.DG_CREATE_KEY, AdminOperation.DG_REVOKE_KEY]


def request_scope(pool):
    from selahcue_api.apps.providers.contracts import ProviderScope
    return ProviderScope(pool.provider, pool.parent_scope_id)


def test_valid_create_activates_only_after_binding_and_seals_secret(admitted_pool, provider_mounts, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import Created
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, ReadyMapping, SecretBytes
    from selahcue_api.apps.providers.models import ProviderCredential
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")

    def create(request, credential):
        from django.db import connections
        assert all(conn.connection is None for conn in connections.all(initialized_only=True))
        return Created(ProviderPartialIdentity(request.scope, request.project_id, None, "ready-key"),
                       SecretBytes(b"never-store-plaintext"), None, "test-receipt", NOW)

    monkeypatch.setattr(deepgram_admin, "mutate", create)
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW).state == "READY"
    mapping = ProviderCredential.objects.get(pk=pending.mapping_id)
    assert mapping.external_api_key_id == "ready-key"
    assert mapping.secret_ciphertext and b"never-store-plaintext" not in mapping.secret_ciphertext
    provider_mounts("web", stt=True, provisioning=False, capable=True, budgets=False)
    initialize_provider_runtime(entrypoint="asgi")
    assert ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW) == (
        ReadyMapping(pending.mapping_id, ctx.org_id, "deepgram")
    )


def test_signup_and_suspended_licence_create_no_provisioning_rows(admitted_pool, monkeypatch):
    from selahcue_api.apps.accounts import services as accounts
    from selahcue_api.apps.providers.contracts import ProvisioningRejected
    from selahcue_api.apps.providers.models import ProviderCreateAllowance, ProviderProvisioningOutbox, ProvisioningDemand
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    # Registration still performs its ordinary local account writes. Its
    # asynchronous verification email has no bearing on provisioning.
    class LocalSender:
        def send_email_verification(self, user, raw_token):
            assert user.email == "task4-signup@example.test"
            assert raw_token

    monkeypatch.setattr(accounts, "get_email_sender", LocalSender)
    assert accounts.register_customer_user(accounts.RegisterCustomerUserData(
        "task4-fixture-signup", "task4-signup@example.test", "synthetic-task4-password",
        "Provider capacity fixture", "NG",
    )).accepted
    ctx, token = make_demand()
    AppLicenseKey.objects.filter(pk=ctx.license_id).update(status="SUSPENDED", prior_status="ACTIVATED")
    with pytest.raises(ProvisioningRejected, match="INELIGIBLE"):
        ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    assert not ProvisioningDemand.objects.exists()
    assert not ProviderProvisioningOutbox.objects.filter(kind="PROVISION").exists()
    assert not ProviderCreateAllowance.objects.exists()


@pytest.mark.parametrize("value", [
    [], [{"provider": "deepgram", "create_per_hour": 0, "create_per_day": 3}],
])
def test_missing_or_zero_global_blocks_boot_only_for_create(value, provider_mounts, tmp_path, settings):
    from provider_helpers import policy_rows, write_mount

    for enabled in (True, False):
        provider_mounts("web", capable=True, stt=True, provisioning=enabled)
        settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(
            tmp_path, "global-policy", {**policy_rows(capable=True), "creation_budgets": value},
        )
        if enabled:
            with pytest.raises(ProviderConfigurationError, match="PCFG_CAPABILITY_UNCONFIGURED"):
                initialize_provider_runtime(entrypoint="wsgi")
        else:
            assert initialize_provider_runtime(entrypoint="wsgi").requested_public_providers == {"deepgram"}


@pytest.mark.parametrize("bad", [
    [{"provider": "deepgram", "create_per_hour": True, "create_per_day": 4}],
    [{"provider": "other", "create_per_hour": 3, "create_per_day": 4}],
    [{"provider": "deepgram", "create_per_hour": 3, "create_per_day": 4, "extra": 1}],
    [{"provider": "deepgram", "create_per_hour": 3, "create_per_day": 4}] * 2,
])
def test_global_budget_schema_is_strict(bad, provider_mounts, tmp_path, settings):
    from provider_helpers import policy_rows, write_mount

    provider_mounts("web", capable=True, stt=True)
    settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(
        tmp_path, "global-policy", {**policy_rows(capable=True), "creation_budgets": bad},
    )
    with pytest.raises(ProviderConfigurationError, match="PCFG_SCHEMA_INVALID"):
        initialize_provider_runtime(entrypoint="wsgi")


def test_outbox_publish_lost_delivery_and_early_ack_are_durable(admitted_pool, provider_mounts, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import MutationUnknown
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, ProvisioningErrorCode
    from selahcue_api.apps.providers.models import ProviderProvisioningOutbox
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready
    from selahcue_api.apps.providers import provisioning_tasks as tasks
    from selahcue_api.celery import app

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    outbox = ProviderProvisioningOutbox.objects.get(kind="PROVISION", mapping_id=pending.mapping_id)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    publishes = []

    def broker_send(name, **kwargs):
        publishes.append((name, kwargs))
        if len(publishes) == 1:
            raise OSError("fixture emulates a failed broker attempt")
        if len(publishes) == 3:
            tasks.provision_task.run(kwargs["kwargs"]["outbox_id"])

    mutations = []

    def lose_response(request, credential):
        mutations.append(request.attempt_id)
        return MutationUnknown(ProvisioningErrorCode.OUTCOME_UNKNOWN,
                               ProviderPartialIdentity(request.scope, request.project_id, None, None))

    monkeypatch.setattr(app, "send_task", broker_send)
    monkeypatch.setattr(deepgram_admin, "mutate", lose_response)
    monkeypatch.setattr(tasks.timezone, "now", lambda: NOW + timedelta(seconds=35))
    tasks.publish_outbox(outbox.pk, clock=lambda: NOW)
    outbox.refresh_from_db()
    assert outbox.state == "PENDING" and outbox.publish_count == 1
    tasks.publish_outbox(outbox.pk, clock=lambda: NOW + timedelta(seconds=5))
    outbox.refresh_from_db()
    assert outbox.state == "SENT" and outbox.publish_count == 2
    tasks._reclaim_publication(outbox.pk, lambda: NOW + timedelta(seconds=35))
    tasks.publish_outbox(outbox.pk, clock=lambda: NOW + timedelta(seconds=35))
    tasks.provision_task.run(str(outbox.pk))
    outbox.refresh_from_db()
    assert outbox.state == "ACKED" and outbox.publish_count == 3
    assert len(mutations) == 1
    assert all(item == (
        "providers.provision", {"kwargs": {"outbox_id": str(outbox.pk)}, "task_id": str(outbox.pk),
                                "retry": False, "queue": "provider_provisioning", "ignore_result": True},
    ) for item in publishes)


def test_task_autodiscovery_and_wrong_role_refusal():
    import subprocess
    import sys

    code = """
from selahcue_api.celery import app
from selahcue_api.apps.providers.contracts import ProviderConfigurationError
app.loader.import_default_modules()
names = ('provision', 'recover', 'inventory_page', 'publish_outbox', 'sweep')
for name in names:
    full = 'providers.' + name
    task = app.tasks[full]
    assert task.acks_late and task.reject_on_worker_lost and task.ignore_result
    assert (task.max_retries, task.soft_time_limit, task.time_limit) == (0, 15, 20)
    assert app.conf.task_routes[full]['queue'] == 'provider_provisioning'
    try:
        task.run(*(() if name == 'sweep' else ('bad-id',)))
    except ProviderConfigurationError as e:
        assert e.code == 'PCFG_NOT_INITIALIZED'
    else:
        raise AssertionError(full)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def mark_scan_complete(pool, at):
    from selahcue_api.apps.providers.models import ProviderInventoryScan

    scan = ProviderInventoryScan.objects.get(pool=pool, state="PARTIAL")
    scan.state, scan.finished_at, scan.terminal_page_seen = "COMPLETE", at, True
    scan.save()
    pool.latest_complete_scan, pool.inventory_valid_until = scan, scan.started_at + timedelta(seconds=300)
    pool.save()


def test_global_hourly_budget_counts_both_parent_pools(provider_mounts, settings, tmp_path):
    import json
    from pathlib import Path
    from uuid import uuid4

    from provider_helpers import policy_rows, write_mount
    from selahcue_api.apps.providers.contracts import CapacityUnavailable, CapacityUnavailableCode, ProvisioningAuditContext
    from selahcue_api.apps.providers.models import ProviderCapacityPool, ProviderCreateAllowance
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready

    policy = policy_rows(capable=True)
    first = policy["deepgram"][0]
    second = {**first, "project_id": "synthetic-second-parent"}
    policy["deepgram"] = [first, second]
    global_limit = policy["creation_budgets"][0]
    global_limit["create_per_hour"] = 1
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    creds = json.loads(Path(settings.SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE).read_bytes())
    creds["deepgram"].append({"project_id": second["project_id"], "keys_write_api_key": "synthetic-second-key"})
    settings.SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE = write_mount(tmp_path, "local-creds", creds)
    settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "all-policy", policy)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(cleanup_authorizations=(),
                            audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "scope-test"), clock=lambda: NOW)
    for pool in ProviderCapacityPool.objects.filter(provider="deepgram"):
        mark_scan_complete(pool, NOW)

    for index, scope in enumerate((first, second)):
        provider_mounts("web", capable=True, stt=True, provisioning=True)
        settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(
            tmp_path, "subset-policy", {**policy, "deepgram": [scope]},
        )
        initialize_provider_runtime(entrypoint="wsgi")
        ctx, token = make_demand()
        result = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
        if index == 0:
            assert result.retry_after_seconds == 5
        else:
            assert result == CapacityUnavailable(CapacityUnavailableCode.HOURLY_CREATE_LIMIT)
    assert ProviderCreateAllowance.objects.filter(state="HELD").count() == 1


def test_daily_window_keeps_dispatch_until_exact_boundary(admitted_pool, provider_mounts, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import MutationUnknown
    from selahcue_api.apps.providers.capacity import capacity_refusal, worker_configuration
    from selahcue_api.apps.providers.contracts import CapacityUnavailableCode, ProviderPartialIdentity, ProvisioningErrorCode
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    config = initialize_provider_runtime(entrypoint="celery_worker")
    monkeypatch.setattr(deepgram_admin, "mutate", lambda request, _: MutationUnknown(
        ProvisioningErrorCode.OUTCOME_UNKNOWN, ProviderPartialIdentity(request.scope, request.project_id, None, None),
    ))
    provision_mapping(pending.mapping_id, clock=lambda: NOW)
    # Supply the genuinely recorded dispatch and check rate arithmetic while
    # keeping the tested pool's authority freshly inventoried at both instants.
    admitted_pool.refresh_from_db()
    admitted_pool.inventory_valid_until = NOW + timedelta(days=2)
    budget = admitted_pool.budget
    assert capacity_refusal(config, budget, admitted_pool, NOW + timedelta(days=1, microseconds=-1),
                            additional_claims=0, additional_creates=5) == CapacityUnavailableCode.DAILY_CREATE_LIMIT
    assert capacity_refusal(config, budget, admitted_pool, NOW + timedelta(days=1),
                            additional_claims=0, additional_creates=5) == CapacityUnavailableCode.HOURLY_CREATE_LIMIT
    assert capacity_refusal(config, budget, admitted_pool, NOW + timedelta(days=1),
                            additional_claims=0, additional_creates=2) is None
    assert worker_configuration() is config


def test_openai_lost_combined_key_preserves_two_stage_rate_and_never_activates(provider_mounts, monkeypatch):
    from uuid import uuid4

    from selahcue_api.apps.providers import configuration
    from selahcue_api.apps.providers.adapters import openai_admin
    from selahcue_api.apps.providers.adapters.contracts import Created, MutationUnknown
    from selahcue_api.apps.providers.contracts import (
        AdminOperation, ProviderPartialIdentity, ProvisioningAuditContext, ProvisioningErrorCode,
    )
    from selahcue_api.apps.providers.models import (
        ProviderCapacityPool, ProviderCreateAllowance, ProviderCredential, ProviderResourceClaim,
    )
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping

    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(cleanup_authorizations=(),
                            audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "notes-synthetic"), clock=lambda: NOW)
    pool = ProviderCapacityPool.objects.get(provider="openai")
    mark_scan_complete(pool, NOW)
    provider_mounts("web", notes=True, capable=True, provisioning=True)
    with pytest.raises(ProviderConfigurationError, match="PCFG_NOTES_RUNTIME_UNAVAILABLE"):
        initialize_provider_runtime(entrypoint="wsgi")
    # Controlled algorithm-only runtime. Production web continues to refuse notes boot.
    configuration._load("web", entrypoint="wsgi")
    ctx, token = make_demand()
    pending = ensure_provider_ready(replace(ctx, meter="notes"), authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="celery_worker")

    def mutate(request, credential):
        if request.operation == AdminOperation.OA_CREATE_PROJECT:
            assert ProviderCreateAllowance.objects.filter(state="HELD").count() == 1
            return Created(ProviderPartialIdentity(request.scope, "synthetic-new-project", None, None),
                           None, None, "project-request", NOW)
        assert request.project_id == "synthetic-new-project"
        return MutationUnknown(ProvisioningErrorCode.RESPONSE_INVALID,
                               ProviderPartialIdentity(request.scope, request.project_id, "synthetic-account", "known-key"))

    monkeypatch.setattr(openai_admin, "mutate", mutate)
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW).state == "WORKING"
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW + timedelta(seconds=1)).state == "RECOVERY_REQUIRED"
    mapping = ProviderCredential.objects.get(pk=pending.mapping_id)
    assert mapping.external_project_id == "synthetic-new-project"
    assert mapping.external_service_account_id == "synthetic-account"
    assert mapping.external_api_key_id == "known-key"
    assert mapping.secret_ciphertext is None and mapping.state == "PROVISIONING"
    assert ProviderResourceClaim.objects.get().state == "COUNTED"
    assert ProviderCreateAllowance.objects.filter(state="DISPATCHED").count() == 2


def test_cleanup_allows_at_most_one_replacement_and_keeps_both_resources_counted(
    admitted_pool, provider_mounts, monkeypatch,
):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import CleanupConfirmed, Created
    from selahcue_api.apps.providers.contracts import AdminOperation, ProviderPartialIdentity
    from selahcue_api.apps.providers.models import ProviderExternalResource, ProviderResourceClaim, ProvisioningDemand
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping

    ctx, token = make_demand()
    original = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW).mapping_id
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    operations = []

    def response(request, credential):
        operations.append(request.operation)
        identity = ProviderPartialIdentity(request.scope, request.project_id, None,
                                           request.api_key_id or f"key-{request.mapping_id}")
        if request.operation == AdminOperation.DG_CREATE_KEY:
            return Created(identity, None, NOW + timedelta(days=1), "known-key-receipt", NOW)
        return CleanupConfirmed(identity, "confirmed-delete-receipt")

    monkeypatch.setattr(deepgram_admin, "mutate", response)
    result = None
    timings = (0, 5, 6, 7, 8, 13, 14, 15)
    states = ("RECOVERY_REQUIRED", "RECOVERY_REQUIRED", "WAITING_CAPACITY", "QUEUED",
              "RECOVERY_REQUIRED", "RECOVERY_REQUIRED", "FAILED", "FAILED")
    for delay, expected in zip(timings, states, strict=True):
        current_id = result.mapping_id if result else original
        result = provision_mapping(current_id, clock=lambda: NOW + timedelta(seconds=delay))
        assert result.state == expected
    assert result.mapping_id != original
    first, second = ProviderResourceClaim.objects.order_by("generation")
    assert second.previous_claim_id == first.pk
    assert first.state == second.state == "COUNTED"
    assert ProviderExternalResource.objects.filter(count_state="COUNTED").count() == 2
    assert ProvisioningDemand.objects.get().replacement_count == 1
    assert operations == [AdminOperation.DG_CREATE_KEY, AdminOperation.DG_REVOKE_KEY] * 2


def test_lost_create_recovers_exact_marker_but_requires_ownership_before_cleanup(
    admitted_pool, provider_mounts, monkeypatch,
):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import InventoryPage, InventoryRecord, MutationUnknown
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, ProvisioningErrorCode
    from selahcue_api.apps.providers.models import ProviderCredential, ProviderExternalResource, ProviderResourceClaim, ProvisioningAttempt
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping, recover_provisioning_attempt

    ctx, token = make_demand()
    mapping_id = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW).mapping_id
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    monkeypatch.setattr(deepgram_admin, "mutate", lambda request, _: MutationUnknown(
        ProvisioningErrorCode.OUTCOME_UNKNOWN, ProviderPartialIdentity(request.scope, request.project_id, None, None),
    ))
    monkeypatch.setattr(deepgram_admin, "list_page", lambda *_: InventoryPage((
        InventoryRecord("wrong-marker", "unknown-marker", NOW, "active", None),
        InventoryRecord("recovered-key-id", f"scp1-{mapping_id}-dgkey", NOW, "active", None),
    ), None, True))
    assert provision_mapping(mapping_id, clock=lambda: NOW).state == "RECOVERY_REQUIRED"
    attempt = ProvisioningAttempt.objects.get()
    assert recover_provisioning_attempt(attempt.pk, clock=lambda: NOW + timedelta(seconds=5)).requires_operator_recovery
    assert ProviderExternalResource.objects.get().external_id == "recovered-key-id"
    assert ProviderResourceClaim.objects.get().state == "COUNTED"
    assert ProviderCredential.objects.get(pk=mapping_id).secret_ciphertext is None
    assert ProvisioningAttempt.objects.count() == 1


def test_late_create_receipt_cannot_activate_the_returned_secret(admitted_pool, provider_mounts, monkeypatch):
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import Created
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, SecretBytes
    from selahcue_api.apps.providers.models import ProviderCredential, ProvisioningAttempt
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    monkeypatch.setattr(deepgram_admin, "mutate", lambda request, _: Created(
        ProviderPartialIdentity(request.scope, request.project_id, None, "late-known-key"),
        SecretBytes(b"this-late-secret-must-not-persist"), None, "late-receipt", NOW,
    ))
    times = iter((NOW, NOW + timedelta(seconds=31)))
    assert provision_mapping(pending.mapping_id, clock=lambda: next(times)).state == "RECOVERY_REQUIRED"
    attempt = ProvisioningAttempt.objects.get()
    assert attempt.state == "SUCCEEDED" and attempt.observed_api_key_id == "late-known-key"
    mapping = ProviderCredential.objects.get(pk=pending.mapping_id)
    assert mapping.state == "PROVISIONING" and mapping.secret_ciphertext is None


def test_sweep_recovers_acknowledged_prepared_work_without_transport(admitted_pool, provider_mounts, monkeypatch):
    from uuid import uuid4

    from selahcue_api.apps.providers import provisioning_tasks as tasks
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.models import ProviderProvisioningOutbox, ProvisioningAttempt
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready
    from selahcue_api.celery import app

    ctx, token = make_demand()
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    first = ProviderProvisioningOutbox.objects.get(kind="PROVISION", mapping_id=pending.mapping_id)
    first.state, first.lease_id, first.lease_until = "PUBLISHING", uuid4(), NOW + timedelta(seconds=30)
    first.save()
    first.state, first.acked_at, first.lease_id, first.lease_until = "ACKED", NOW, None, None
    first.save()
    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    monkeypatch.setattr(app, "send_task", lambda *a, **kw: None)
    monkeypatch.setattr(deepgram_admin, "mutate", lambda *_: pytest.fail("sweeper dispatched a provider mutation"))
    assert tasks.sweep_provisioning(clock=lambda: NOW + timedelta(seconds=1)) > 0
    second = ProviderProvisioningOutbox.objects.get(kind="PROVISION", mapping_id=pending.mapping_id, generation=2)
    assert second.state == "PENDING"
    assert ProvisioningAttempt.objects.get().state == "PREPARED"


def test_inventory_absence_never_frees_and_explicit_exclusion_can_restore(admitted_pool, provider_mounts, monkeypatch):
    from uuid import uuid4

    from selahcue_api.apps.providers import provisioning_tasks as tasks
    from selahcue_api.apps.providers.adapters import deepgram_admin
    from selahcue_api.apps.providers.adapters.contracts import InventoryPage, InventoryRecord
    from selahcue_api.apps.providers.contracts import ProviderPartialIdentity, ProvisioningAuditContext, RecoveryEvidenceKind
    from selahcue_api.apps.providers.models import ProviderExternalResource, ProviderInventoryScan
    from selahcue_api.apps.providers.provisioning import record_recovery_evidence

    provider_mounts("provisioner", capable=True, stt=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    resource_ids = iter((("existing-key",), (), ("existing-key",)))

    def fetch(*_):
        return InventoryPage(tuple(
            InventoryRecord(value, None, NOW, "active", None) for value in next(resource_ids)
        ), None, True)

    monkeypatch.setattr(deepgram_admin, "list_page", fetch)
    def scan_at(seconds):
        at = NOW + timedelta(seconds=seconds)
        scan = tasks.refresh_inventory(admitted_pool.pk, clock=lambda: at)
        tasks.inventory_page(scan, clock=lambda: at + timedelta(seconds=2))
        assert ProviderInventoryScan.objects.get(pk=scan).state == "COMPLETE"
        admitted_pool.refresh_from_db()
        assert admitted_pool.inventory_valid_until == at + timedelta(seconds=300)

    scan_at(60)
    scan_at(120)
    resource = ProviderExternalResource.objects.get()
    assert resource.count_state == "COUNTED"
    record_recovery_evidence(
        pool_id=admitted_pool.pk, mapping_id=None, attempt_id=None, kind=RecoveryEvidenceKind.RESOURCE_EXCLUSION,
        identity=ProviderPartialIdentity(request_scope(admitted_pool), admitted_pool.parent_scope_id, None, "existing-key"),
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "true-exclusion-fixture"),
        clock=lambda: NOW + timedelta(seconds=125),
    )
    resource.refresh_from_db()
    assert resource.count_state == "EXCLUDED"
    scan_at(180)
    resource.refresh_from_db()
    assert resource.count_state == "COUNTED" and resource.exclusion_evidence_id is None


def test_failed_openai_account_stage_requires_fresh_evidence_before_project_only_archive(
    provider_mounts, monkeypatch,
):
    from uuid import uuid4

    from selahcue_api.apps.providers import configuration
    from selahcue_api.apps.providers.adapters import openai_admin
    from selahcue_api.apps.providers.adapters.contracts import CleanupConfirmed, Created, InventoryPage, NotCreated
    from selahcue_api.apps.providers.contracts import (
        AdminOperation, CleanupAuthorization, ProviderPartialIdentity, ProvisioningAuditContext,
        ProvisioningErrorCode, RecoveryEvidenceKind,
    )
    from selahcue_api.apps.providers.models import ProviderCapacityPool, ProviderInventoryScan, ProvisioningAttempt
    from selahcue_api.apps.providers.policy_publication import publish_provider_policy
    from selahcue_api.apps.providers.provisioning import ensure_provider_ready, provision_mapping, record_recovery_evidence
    from provider_helpers import OPENAI

    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")
    publish_provider_policy(
        cleanup_authorizations=(CleanupAuthorization(OPENAI, "synthetic-archive-authority"),),
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "fixture"),
        clock=lambda: NOW,
    )
    pool = ProviderCapacityPool.objects.get(provider="openai")
    mark_scan_complete(pool, NOW)
    provider_mounts("web", notes=True, capable=True, provisioning=True)
    configuration._load("web", entrypoint="wsgi")
    ctx, token = make_demand()
    ctx = replace(ctx, meter="notes")
    pending = ensure_provider_ready(ctx, authenticated_token_id=token.pk, clock=lambda: NOW)
    provider_mounts("provisioner", notes=True, capable=True, provisioning=True)
    initialize_provider_runtime(entrypoint="operator")

    operations = []
    owned = ProviderPartialIdentity(OPENAI, "owned-project", None, None)

    def response(request, credential):
        operations.append(request.operation)
        if request.operation == AdminOperation.OA_CREATE_PROJECT:
            return Created(owned, None, None, "confirmed-project-create", NOW)
        if request.operation == AdminOperation.OA_CREATE_SERVICE_ACCOUNT_KEY:
            return NotCreated(ProvisioningErrorCode.TRANSPORT_NOT_SENT)
        assert (request.project_id, request.service_account_id, request.api_key_id) == ("owned-project", None, None)
        return CleanupConfirmed(owned, "confirmed-archive")

    monkeypatch.setattr(openai_admin, "mutate", response)
    monkeypatch.setattr(openai_admin, "list_page", lambda *_: InventoryPage((), None, True))
    # Dispatch tokens remain spent. Move the clock beyond the two hourly dispatch
    # boundaries and refresh inventory each time before a new create attempt.
    token.expires_at = NOW + timedelta(hours=5)
    token.save(update_fields=["expires_at"])
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW).state == "WORKING"
    assert provision_mapping(pending.mapping_id, clock=lambda: NOW + timedelta(seconds=1)).state == "WORKING"

    from selahcue_api.apps.providers import provisioning_tasks as tasks
    for offset, expected in ((3600, "WORKING"), (7200, "FAILED")):
        now = NOW + timedelta(seconds=offset)
        scan_id = tasks.refresh_inventory(pool.pk, clock=lambda: now)
        tasks.inventory_page(scan_id, clock=lambda: now)
        assert ProviderInventoryScan.objects.get(pk=scan_id).state == "COMPLETE"
        assert provision_mapping(pending.mapping_id, clock=lambda: now).state == expected
    later = NOW + timedelta(seconds=7201)
    assert provision_mapping(pending.mapping_id, clock=lambda: later).state == "FAILED"
    assert AdminOperation.OA_ARCHIVE_PROJECT not in operations
    project = ProvisioningAttempt.objects.get(stage__operation=AdminOperation.OA_CREATE_PROJECT)
    record_recovery_evidence(
        pool_id=pool.pk, mapping_id=pending.mapping_id, attempt_id=project.pk,
        kind=RecoveryEvidenceKind.OWNERSHIP, identity=owned,
        audit=ProvisioningAuditContext("synthetic-operator", uuid4(), "fresh-project-ownership-receipt"),
        clock=lambda: later,
    )
    assert provision_mapping(pending.mapping_id, clock=lambda: later).state == "RECOVERY_REQUIRED"
    assert provision_mapping(pending.mapping_id, clock=lambda: later + timedelta(seconds=1)).state == "WAITING_CAPACITY"
    assert operations == [AdminOperation.OA_CREATE_PROJECT, *([AdminOperation.OA_CREATE_SERVICE_ACCOUNT_KEY] * 3),
                          AdminOperation.OA_ARCHIVE_PROJECT]
