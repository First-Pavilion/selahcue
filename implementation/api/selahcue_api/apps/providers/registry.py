"""Audited mapping transitions. Registry writers acquire the org lock first."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest
from uuid import UUID

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Q

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.audit.models import AuditResult
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.graphql.context import ActorContext, ActorKind

from .configuration import (
    PROVIDERS, get_provider_configuration, selected_role, valid_evidence, valid_id,
)
from .contracts import (
    EncryptedSecret,
    ProviderConfigurationError,
    ProviderKind,
    ProviderCustodyError,
    ProviderExternalIdentity,
    ProviderMappingState as State,
    ProviderPartialIdentity,
    ProviderRegistryError,
    ProviderScope,
    ProviderScopePolicy,
    ReadyMapping,
    RegistryAuditContext,
    RegistryErrorCode as Code,
    RegistryReason as Reason,
    RegistrySnapshot,
    RotationBatchResult,
    RotationCursor,
    RotationFailure,
    SecretBytes,
)
from .custody import _rewrap, _validate_secret, open_secret, seal_secret
from .models import ENVELOPE_FIELDS, EXTERNAL_FIELDS, ProviderCredential

_INTENT_ACTOR = "provider-provisioning-intent"


def _refuse(code: Code):
    raise ProviderRegistryError(code)


def _positive_integer(value) -> bool:
    return type(value) is int and 0 < value <= 9223372036854775807


def _valid_scope(scope) -> bool:
    return (
        isinstance(scope, ProviderScope) and type(scope.provider) is str
        and scope.provider in PROVIDERS and valid_id(scope.parent_scope_id)
    )


def _context(*, permit_web: bool = False):
    try:
        role = selected_role()
        config = get_provider_configuration(required_role=role)
    except ProviderConfigurationError:
        raise ProviderRegistryError(Code.PREG_INVALID_CONTEXT) from None
    if role != "provisioner" and not (permit_web and role == "web"):
        _refuse(Code.PREG_INVALID_CONTEXT)
    return config


def _policy_scope(config, scope: ProviderScope) -> ProviderScopePolicy:
    if _valid_scope(scope) and config.policy is not None:
        for entry in config.policy.scopes:
            if entry.scope == scope:
                return entry
    _refuse(Code.PREG_INVALID_CONTEXT)


def _timestamp(at: datetime | None) -> str | None:
    if at is None:
        return None
    return at.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _projection(row: ProviderCredential) -> dict:
    return {
        "mapping_id": str(row.pk),
        "org_id": row.org_id,
        "provider": str(row.provider),
        "parent_scope_id": row.parent_scope_id,
        "external_project_id": row.external_project_id,
        "external_service_account_id": row.external_service_account_id,
        "external_api_key_id": row.external_api_key_id,
        "state": str(row.state),
        "revision": row.revision,
        "wrapping_key_id": row.wrapping_key_id,
        "created_at": _timestamp(row.created_at),
        "updated_at": _timestamp(row.updated_at),
        "activated_at": _timestamp(row.activated_at),
        "terminal_at": _timestamp(row.terminal_at),
    }


def _valid_audit(audit, reason: Reason) -> bool:
    return (
        isinstance(audit, RegistryAuditContext) and audit.reason is reason
        and valid_id(audit.operator_id) and len(audit.operator_id) <= 128
        and isinstance(audit.request_id, UUID) and valid_evidence(audit.evidence_ref)
        and (reason is not Reason.PROVISION_INTENT or audit.operator_id == _INTENT_ACTOR)
    )


@dataclass
class _Attempt:
    before: dict | None = None
    after: dict | None = None
    replayed: bool = False

    def completed(self, row: ProviderCredential, *, replayed: bool = False) -> None:
        self.after = _projection(row)
        self.replayed = replayed


def _record(mapping_id: UUID, audit: RegistryAuditContext, attempt: _Attempt,
            error: ProviderRegistryError | ProviderCustodyError | None = None) -> None:
    result = AuditResult.SUCCESS
    if error is not None:
        result = AuditResult.DENIED if error.code == Code.PREG_INVALID_CONTEXT else AuditResult.FAILED
    metadata = {
        "evidence_ref": audit.evidence_ref,
        "replayed": attempt.replayed if error is None else False,
        "error_code": error.code.value if error is not None else None,
    }
    before = attempt.before or {}
    after = (attempt.after if error is None else attempt.before) or {}
    record_audit_event(
        ActorContext(kind=ActorKind.SERVICE, actor_id=audit.operator_id),
        action=f"provider_registry.{audit.reason.value}",
        target_type="ProviderCredential",
        target_id=str(mapping_id),
        request_id=str(audit.request_id),
        reason=audit.reason.value,
        before={**before, **metadata},
        after={**after, **metadata},
        result=result,
        source_surface="provider_registry_internal",
    )


def _integrity_code(error: IntegrityError) -> Code:
    constraint = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None)
    if constraint == "provider_credential_owner_uniq":
        return Code.PREG_OWNERSHIP_CONFLICT
    if constraint in {"provider_credential_key_uniq", "provider_openai_project_uniq",
                      "selahcue_providers_providercredential_pkey"}:
        return Code.PREG_IDENTITY_CONFLICT
    if connection.vendor == "sqlite":
        table = ProviderCredential._meta.db_table
        message = str(error)
        if message.startswith("UNIQUE constraint failed: " + table + ".org_id"):
            return Code.PREG_OWNERSHIP_CONFLICT
        if message.startswith("UNIQUE constraint failed: " + table + "."):
            return Code.PREG_IDENTITY_CONFLICT
    return Code.PREG_INTERNAL_FAILURE


@contextmanager
def _operation(mapping_id: UUID, now: datetime, audit: RegistryAuditContext, reason: Reason):
    if not _valid_audit(audit, reason) or not isinstance(mapping_id, UUID):
        _refuse(Code.PREG_INVALID_CONTEXT)
    attempt = _Attempt()
    try:
        with transaction.atomic():
            if not isinstance(now, datetime) or now.utcoffset() is None:
                _refuse(Code.PREG_INVALID_CONTEXT)
            yield attempt
            _record(mapping_id, audit, attempt)
        return
    except (ProviderRegistryError, ProviderCustodyError) as error:
        failure = error
    except IntegrityError as error:
        failure = ProviderRegistryError(_integrity_code(error))
    except DatabaseError:
        failure = ProviderRegistryError(Code.PREG_INTERNAL_FAILURE)

    # The inner write rolled back. A denial audit participates in any caller-owned
    # transaction so an outbox rollback cannot leave an orphaned success record.
    try:
        with transaction.atomic():
            _record(mapping_id, audit, attempt, failure)
    except DatabaseError:
        _refuse(Code.PREG_INTERNAL_FAILURE)
    raise failure from None


def _scope_of(row: ProviderCredential) -> ProviderScope:
    return ProviderScope(row.provider, row.parent_scope_id)


def _partial(row: ProviderCredential) -> ProviderPartialIdentity:
    return ProviderPartialIdentity(_scope_of(row), *(getattr(row, field) for field in EXTERNAL_FIELDS))


def _snapshot(row: ProviderCredential) -> RegistrySnapshot:
    return RegistrySnapshot(row.pk, row.org_id, row.provider, State(row.state), row.revision, _partial(row))


def _ready(row: ProviderCredential) -> ReadyMapping:
    return ReadyMapping(row.pk, row.org_id, row.provider)


def _lock_org(org_id: int) -> None:
    if not _positive_integer(org_id):
        _refuse(Code.PREG_INVALID_CONTEXT)
    if not CustomerOrg.objects.select_for_update(no_key=True).filter(pk=org_id).only("id").first():
        _refuse(Code.PREG_NOT_FOUND)


def _lock_mapping(mapping_id: UUID, config, attempt: _Attempt) -> ProviderCredential:
    org_id = ProviderCredential.objects.filter(pk=mapping_id).values_list("org_id", flat=True).first()
    if org_id is None:
        _refuse(Code.PREG_NOT_FOUND)
    _lock_org(org_id)
    row = ProviderCredential.objects.select_for_update().filter(pk=mapping_id, org_id=org_id).first()
    if row is None:
        _refuse(Code.PREG_NOT_FOUND)
    _policy_scope(config, _scope_of(row))
    attempt.before = _projection(row)
    return row


def _new_mapping(mapping_id: UUID, org_id: int, scope: ProviderScope, now: datetime) -> ProviderCredential:
    return ProviderCredential.objects.create(
        pk=mapping_id, org_id=org_id, provider=scope.provider, parent_scope_id=scope.parent_scope_id,
        external_project_id=scope.parent_scope_id if scope.provider == "deepgram" else None,
        created_at=now, updated_at=now,
    )


def _save(row: ProviderCredential, now: datetime, fields: tuple[str, ...]) -> None:
    row.revision += 1
    row.updated_at = now
    row.save(update_fields=[*fields, "revision", "updated_at"])


def _revision(row: ProviderCredential, expected: int, *, replay: bool = False) -> None:
    if not _positive_integer(expected):
        _refuse(Code.PREG_INVALID_CONTEXT)
    if not replay and row.revision != expected:
        _refuse(Code.PREG_REVISION_CONFLICT)


def _check_identity(identity: ProviderPartialIdentity | ProviderExternalIdentity, *, complete: bool):
    required = ProviderExternalIdentity if complete else ProviderPartialIdentity
    if not isinstance(identity, required) or not _valid_scope(identity.scope):
        _refuse(Code.PREG_INVALID_CONTEXT)
    ids = (identity.project_id, identity.service_account_id, identity.api_key_id)
    if any(value is not None and not valid_id(value) for value in ids):
        _refuse(Code.PREG_INVALID_CONTEXT)
    if identity.scope.provider == "deepgram" and (
        identity.service_account_id is not None or identity.project_id not in (None, identity.scope.parent_scope_id)
    ):
        _refuse(Code.PREG_IDENTITY_CONFLICT)
    if complete and (
        identity.project_id is None or identity.api_key_id is None
        or (identity.scope.provider == "openai" and identity.service_account_id is None)
    ):
        _refuse(Code.PREG_IDENTITY_CONFLICT)
    return ids


def _identity_patch(row: ProviderCredential, scope: ProviderScope, ids: tuple) -> tuple[str, ...]:
    if _scope_of(row) != scope:
        _refuse(Code.PREG_IDENTITY_CONFLICT)
    changed = []
    for field, value in zip(EXTERNAL_FIELDS, ids, strict=True):
        if value is None:
            continue
        old = getattr(row, field)
        if old is not None and old != value:
            _refuse(Code.PREG_IDENTITY_CONFLICT)
        if old is None:
            setattr(row, field, value)
            changed.append(field)
    if row.provider == "openai" and (
        (row.external_service_account_id is not None and row.external_project_id is None)
        or (row.external_api_key_id is not None and row.external_service_account_id is None)
    ):
        _refuse(Code.PREG_IDENTITY_CONFLICT)
    return tuple(changed)


def _require_identity(row: ProviderCredential, identity: ProviderExternalIdentity, ids: tuple) -> None:
    if _scope_of(row) != identity.scope or tuple(getattr(row, field) for field in EXTERNAL_FIELDS) != ids:
        _refuse(Code.PREG_IDENTITY_CONFLICT)


def _set_envelope(row: ProviderCredential, envelope: EncryptedSecret) -> None:
    row.secret_version = envelope.version
    row.wrapping_key_id = envelope.key_id
    row.secret_nonce = envelope.nonce
    row.secret_ciphertext = envelope.ciphertext


def _activate(row: ProviderCredential, secret: SecretBytes, now: datetime,
              attempt: _Attempt, *, extra_fields: tuple[str, ...] = ()) -> ReadyMapping:
    if not isinstance(secret, SecretBytes):
        _refuse(Code.PREG_INVALID_CONTEXT)
    if row.state == State.ACTIVE:
        _validate_secret(secret.value)
        if not compare_digest(open_secret(row).value, secret.value):
            _refuse(Code.PREG_SECRET_MISMATCH)
        attempt.completed(row, replayed=True)
    elif row.state == State.PROVISIONING:
        _set_envelope(row, seal_secret(row, secret.value))
        row.state = State.ACTIVE
        row.activated_at = now
        _save(row, now, (*extra_fields, *ENVELOPE_FIELDS, "state", "activated_at"))
        attempt.completed(row)
    else:
        _refuse(Code.PREG_STATE_CONFLICT)
    return _ready(row)


def load_active_mapping(org_id: int, provider: ProviderKind) -> ProviderCredential | None:
    if not _positive_integer(org_id) or type(provider) is not str or provider not in PROVIDERS:
        _refuse(Code.PREG_INVALID_CONTEXT)
    try:
        return ProviderCredential.objects.filter(org_id=org_id, provider=provider, state=State.ACTIVE).first()
    except DatabaseError:
        raise ProviderRegistryError(Code.PREG_INTERNAL_FAILURE) from None


def begin_mapping(*, mapping_id: UUID, org_id: int, scope: ProviderScope,
                  now: datetime, audit: RegistryAuditContext) -> RegistrySnapshot:
    caller_atomic = connection.in_atomic_block
    with _operation(mapping_id, now, audit, Reason.PROVISION_INTENT) as attempt:
        config = _context(permit_web=True)
        policy = _policy_scope(config, scope)
        if config.role == "web" and (
            not caller_atomic or not config.provisioning_requested
            or scope.provider not in config.requested_public_providers
            or audit.evidence_ref != policy.controls_evidence_ref
        ):
            _refuse(Code.PREG_INVALID_CONTEXT)
        _lock_org(org_id)
        row = ProviderCredential.objects.select_for_update().filter(pk=mapping_id, org_id=org_id).first()
        if row is None:
            row = _new_mapping(mapping_id, org_id, scope, now)
            attempt.completed(row)
        else:
            if _scope_of(row) != scope:
                _refuse(Code.PREG_IDENTITY_CONFLICT)
            attempt.before = _projection(row)
            attempt.completed(row, replayed=True)
        return _snapshot(row)


def bind_provisioning_identity(*, mapping_id: UUID, expected_revision: int,
                               identity: ProviderPartialIdentity, now: datetime,
                               audit: RegistryAuditContext) -> RegistrySnapshot:
    with _operation(mapping_id, now, audit, Reason.PROVISION_STAGE) as attempt:
        row = _lock_mapping(mapping_id, _context(), attempt)
        if row.state != State.PROVISIONING:
            _refuse(Code.PREG_STATE_CONFLICT)
        ids = _check_identity(identity, complete=False)
        changed = _identity_patch(row, identity.scope, ids)
        _revision(row, expected_revision, replay=not changed)
        if changed:
            _save(row, now, changed)
        attempt.completed(row, replayed=not changed)
        return _snapshot(row)


def activate_mapping(*, mapping_id: UUID, expected_revision: int, secret: SecretBytes,
                     now: datetime, audit: RegistryAuditContext) -> ReadyMapping:
    with _operation(mapping_id, now, audit, Reason.ACTIVATE) as attempt:
        row = _lock_mapping(mapping_id, _context(), attempt)
        _revision(row, expected_revision, replay=row.state == State.ACTIVE)
        return _activate(row, secret, now, attempt)


def import_existing_mapping(*, mapping_id: UUID, org_id: int, identity: ProviderExternalIdentity,
                            secret: SecretBytes, now: datetime, audit: RegistryAuditContext) -> ReadyMapping:
    with _operation(mapping_id, now, audit, Reason.IMPORT_APPROVED_ALLOCATION) as attempt:
        config = _context()
        ids = _check_identity(identity, complete=True)
        _policy_scope(config, identity.scope)
        _lock_org(org_id)
        row = ProviderCredential.objects.select_for_update().filter(pk=mapping_id, org_id=org_id).first()
        if row is not None:
            _require_identity(row, identity, ids)
            attempt.before = _projection(row)
            if row.state != State.ACTIVE:
                _refuse(Code.PREG_STATE_CONFLICT)
            return _activate(row, secret, now, attempt)
        row = _new_mapping(mapping_id, org_id, identity.scope, now)
        changed = _identity_patch(row, identity.scope, ids)
        return _activate(row, secret, now, attempt, extra_fields=changed)


def recover_mapping_secret(*, mapping_id: UUID, expected_revision: int, identity: ProviderExternalIdentity,
                           secret: SecretBytes, now: datetime, audit: RegistryAuditContext) -> ReadyMapping:
    with _operation(mapping_id, now, audit, Reason.RECOVER_EXISTING_SECRET) as attempt:
        row = _lock_mapping(mapping_id, _context(), attempt)
        ids = _check_identity(identity, complete=True)
        _require_identity(row, identity, ids)
        _revision(row, expected_revision, replay=row.state == State.ACTIVE)
        return _activate(row, secret, now, attempt)


def _terminalize(*, mapping_id: UUID, expected_revision: int, state: State, now: datetime,
                 audit: RegistryAuditContext, reason: Reason) -> RegistrySnapshot:
    with _operation(mapping_id, now, audit, reason) as attempt:
        row = _lock_mapping(mapping_id, _context(), attempt)
        replay = row.state == state
        _revision(row, expected_revision, replay=replay)
        if not replay:
            if row.state != State.PROVISIONING and (row.state != State.ACTIVE or state != State.RETIRED):
                _refuse(Code.PREG_STATE_CONFLICT)
            row.state = state
            row.terminal_at = now
            _save(row, now, ("state", "terminal_at"))
        attempt.completed(row, replayed=replay)
        return _snapshot(row)


def fail_mapping(*, mapping_id: UUID, expected_revision: int, now: datetime,
                 audit: RegistryAuditContext) -> RegistrySnapshot:
    return _terminalize(mapping_id=mapping_id, expected_revision=expected_revision, state=State.FAILED,
                        now=now, audit=audit, reason=Reason.DEFINITE_FAILURE)


def retire_mapping(*, mapping_id: UUID, expected_revision: int, now: datetime,
                   audit: RegistryAuditContext) -> RegistrySnapshot:
    return _terminalize(mapping_id=mapping_id, expected_revision=expected_revision, state=State.RETIRED,
                        now=now, audit=audit, reason=Reason.RETIRE)


def rotate_wrapping_key_batch(*, after: RotationCursor | None, limit: int, now: datetime,
                              audit: RegistryAuditContext) -> RotationBatchResult:
    config = _context()
    if (
        not _valid_audit(audit, Reason.REWRAP) or type(limit) is not int or not 1 <= limit <= 100
        or not isinstance(now, datetime) or now.utcoffset() is None
        or (after is not None and (
            not isinstance(after, RotationCursor) or not _positive_integer(after.org_id)
            or not isinstance(after.mapping_id, UUID)
        ))
    ):
        _refuse(Code.PREG_INVALID_CONTEXT)
    rows = ProviderCredential.objects.filter(secret_version=1).order_by("org_id", "pk")
    if after is not None:
        rows = rows.filter(Q(org_id__gt=after.org_id) | Q(org_id=after.org_id, pk__gt=after.mapping_id))
    try:
        # Each row must release its org and mapping locks before the next one starts.
        if connection.in_atomic_block or not connection.get_autocommit():
            _refuse(Code.PREG_INVALID_CONTEXT)
        inspected = tuple(rows.values_list("org_id", "pk")[:limit])
        cursor = RotationCursor(*inspected[-1]) if inspected else None
        exhausted = cursor is None or not rows.filter(
            Q(org_id__gt=cursor.org_id) | Q(org_id=cursor.org_id, pk__gt=cursor.mapping_id)
        ).exists()
    except DatabaseError:
        raise ProviderRegistryError(Code.PREG_INTERNAL_FAILURE) from None

    rewrapped = []
    failures = []
    for _org_id, mapping_id in inspected:
        try:
            with _operation(mapping_id, now, audit, Reason.REWRAP) as attempt:
                row = _lock_mapping(mapping_id, config, attempt)
                replay = row.wrapping_key_id == config.keyring.active_key_id
                if not replay:
                    _set_envelope(row, _rewrap(row))
                    _save(row, now, ENVELOPE_FIELDS)
                attempt.completed(row, replayed=replay)
            if not replay:
                rewrapped.append(mapping_id)
        except (ProviderRegistryError, ProviderCustodyError) as error:
            failures.append(RotationFailure(mapping_id, error.code))
    return RotationBatchResult(cursor, len(inspected), tuple(rewrapped), tuple(failures), exhausted)
