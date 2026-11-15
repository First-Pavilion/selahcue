"""Public STT admission, one-time mint ownership, and post-mint authority."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging
import time
from uuid import UUID, uuid4

from django.db import DatabaseError, connections, transaction
from django.utils import timezone

from selahcue_api.apps.devices.models import DeviceToken
from selahcue_api.apps.license_keys.selection import aware_utc
from selahcue_api.apps.throttling.cloud import CloudBudgetDecision, evaluate_cloud_budget
from selahcue_api.apps.throttling.services import BudgetOutcome
from selahcue_api.apps.usage.contracts import (
    CloudContext, ReservationDecision, ReservationRejected, ReservationState as State, SessionRequest, SttReadiness,
)
from selahcue_api.apps.usage.live_stt import locked_stt_admission, locked_stt_ledger
from selahcue_api.apps.usage.models import UsageReservation
from selahcue_api.apps.usage.readiness import read_stt_readiness
from selahcue_api.apps.usage.services import STT_SLICE_SECONDS, stt_request_digest
from selahcue_api.apps.usage.weeks import utc_instant
from selahcue_api.platform.responses import PreparedHttpReply

from .capacity import local_scope
from .contracts import (
    CapacityUnavailable, DefiniteFailure, Granted, MintFailureCode, OutcomeUnknown,
    ProviderConfigurationError, ProviderCustodyError, ProviderScope, ProvisioningErrorCode, ProvisioningPending,
    ProvisioningRejected, ReadyMapping, SessionFailureCode as Code, SessionRejected, SessionResult, SttMintState,
)
from .custody import open_secret
from .minting import MintDispatch, MintReceipt, SttDispatchAuthorization, mint
from .models import SttMintAttempt
from .provisioning import ensure_provider_ready
from .stt_audit import OutcomeRecorder
from .stt_circuit import STT_CIRCUIT
from .stt_policy import STT_MINT_POLICY, STT_VERSIONS, stt_configuration

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionDependencies:
    readiness_reader: Callable[..., SttReadiness]
    mint_callable: Callable[..., MintReceipt]
    rate_evaluator: Callable[..., CloudBudgetDecision]
    utc_clock: Callable[[], datetime]
    monotonic_ns: Callable[[], int]
    render_reply: Callable[[SessionResult], PreparedHttpReply]


def _defaults(clock):
    from selahcue_api.platform.cloud_views import render_session_reply

    return SessionDependencies(
        read_stt_readiness, mint, evaluate_cloud_budget, clock, time.monotonic_ns, render_session_reply,
    )


def issue_stt_session(token: DeviceToken, request: SessionRequest, *,
                      clock: Callable[[], datetime] = timezone.now) -> SessionResult:
    result, _ = _issue_stt_session(token, request, _defaults(clock))
    return result


def _scalar_version(value):
    return type(value) is str and len(value) <= 64 and not any("\ud800" <= c <= "\udfff" for c in value)


def validate_session_request(request):
    if (
        type(request) is not SessionRequest or type(request.idempotency_key) is not UUID
        or type(request.action) is not str or type(request.socket_mode) is not str
        or request.retry is not False or not _scalar_version(request.policy_version)
        or not _scalar_version(request.consent_version)
        or not (
            (request.action == "start" and request.socket_mode == "new" and request.previous_reservation_id is None)
            or (request.action == "renew" and request.socket_mode == "existing"
                and type(request.previous_reservation_id) is UUID)
        )
    ):
        raise SessionRejected(Code.VALIDATION_FAILED)


def _validate_original(ledger):
    if not ledger.exact_token_valid():
        raise SessionRejected(Code.UNAUTHENTICATED)
    if not ledger.eligible():
        raise SessionRejected(Code.POLICY_DENIED)


def _check_versions(request):
    if (request.policy_version, request.consent_version) != (STT_VERSIONS.policy_version, STT_VERSIONS.consent_version):
        raise SessionRejected(Code.POLICY_CHANGED)


def _check_mapping(ledger, deps, *, revision=None):
    config = stt_configuration()
    if config is None:
        raise SessionRejected(Code.CLOUD_NOT_ENABLED)
    mapping = ledger.mapping
    if (
        mapping is None or mapping.org_id != ledger.org.pk or mapping.provider != "deepgram"
        or mapping.state != "ACTIVE" or mapping.external_project_id != mapping.parent_scope_id
        or not mapping.external_api_key_id or mapping.secret_version != 1
        or not mapping.secret_nonce or not mapping.secret_ciphertext or not mapping.wrapping_key_id
        or (revision is not None and mapping.revision != revision)
        or local_scope(config, ProviderScope("deepgram", mapping.parent_scope_id)) is None
    ):
        raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
    try:
        config.keyring.lookup(mapping.wrapping_key_id)
    except ProviderConfigurationError:
        raise SessionRejected(Code.PROVIDER_UNAVAILABLE) from None
    observation = deps.readiness_reader(org_id=ledger.org.pk, mapping_id=mapping.pk, at=ledger.now)
    if (
        observation.status != "current_observed" or observation.org_id != ledger.org.pk
        or observation.mapping_id != mapping.pk or observation.checked_at != ledger.now
        or observation.valid_until <= ledger.now
    ):
        raise SessionRejected(Code.RECONCILIATION_PENDING)
    return mapping


def _replay(ledger, request):
    row = ledger.replay
    if not ledger.owns(row) or row.request_hash != stt_request_digest(request) or row.policy_version != request.policy_version:
        raise SessionRejected(Code.REQUEST_MISMATCH)
    raise SessionRejected({
        State.RESERVED: Code.SESSION_PENDING,
        State.RELEASED: Code.RESERVATION_RELEASED,
        State.ISSUED: Code.ALREADY_ISSUED,
        State.SETTLED: Code.ALREADY_ISSUED,
    }[row.state])


def _check_prior(ledger):
    prior = ledger.previous
    if not ledger.owns(prior):
        raise SessionRejected(Code.NOT_FOUND)
    if (
        prior.state != State.ISSUED or not prior.authorized_from <= ledger.now < prior.authorized_until
        or UsageReservation.objects.filter(renews_id=prior.pk).exists()
    ):
        raise SessionRejected(Code.REQUEST_MISMATCH)


def _claim(ledger, decision, secret, recorder):
    # The inserted reservation is already ours under the canonical org lock.
    row = UsageReservation.objects.get(pk=decision.reservation_id)
    mapping = ledger.mapping
    at = ledger.now
    send_at = min(at + timedelta(seconds=30), row.expires_at - timedelta(seconds=34))
    attempt = SttMintAttempt.objects.create(
        reservation=row, request_receipt_id=recorder.request_receipt_id,
        owner_nonce=uuid4(), trigger_token_pk=ledger.token.pk, mapping_revision=mapping.revision,
        state=SttMintState.PREPARED, prepared_at=at, dispatch_not_after=send_at,
    )
    attempt.state = SttMintState.DISPATCHED
    attempt.dispatched_at = at
    attempt.save(update_fields=["state", "dispatched_at"])
    duration_us = (send_at - at) // timedelta(microseconds=1)
    return SttDispatchAuthorization(
        attempt.pk, attempt.owner_nonce, row.pk, mapping.pk, mapping.revision, ledger.org.pk,
        mapping.parent_scope_id, mapping.external_project_id, mapping.external_api_key_id, secret,
        at, ledger.monotonic_ns, send_at, ledger.monotonic_ns + duration_us * 1000,
    )


class _SerializeFailure(Exception):
    pass


def _render(row, decision, grant, deps, *, previous=None):
    try:
        server_time = utc_instant(deps.utc_clock())
        if previous is not None and not previous.authorized_from <= server_time < previous.authorized_until:
            raise SessionRejected(Code.REQUEST_MISMATCH)
        if grant is not None and (
            not row.authorized_from <= server_time < row.authorized_until
            or grant.expires_at <= server_time
        ):
            raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
        if server_time < row.issued_at:
            raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
        result = SessionResult(decision, grant, server_time, row.issued_at, row.policy_version)
        return result, deps.render_reply(result)
    except SessionRejected:
        raise
    except Exception:
        raise _SerializeFailure from None


def _ledger_refusal(error):
    return SessionRejected({
        "INVALID_REQUEST": Code.VALIDATION_FAILED,
        "INVALID_CONTEXT": Code.PROVIDER_UNAVAILABLE,
        "NOT_FOUND": Code.NOT_FOUND,
        "INVALID_RENEWAL": Code.REQUEST_MISMATCH,
        "QUOTA_EXHAUSTED": Code.QUOTA_EXHAUSTED,
        "PROVIDER_UNAVAILABLE": Code.PROVIDER_UNAVAILABLE,
        "CLOCK_UNAVAILABLE": Code.PROVIDER_UNAVAILABLE,
    }.get(error.code, Code.INTERNAL))


def _admission(identity, request, deps, recorder, *, mapping_id=None):
    denial = None
    with locked_stt_admission(
        **identity, request=request, mapping_id=mapping_id, clock=deps.utc_clock,
        monotonic_ns=deps.monotonic_ns if mapping_id is not None else None,
    ) as ledger:
        try:
            _check_versions(request)
            if stt_configuration() is None:
                raise SessionRejected(Code.CLOUD_NOT_ENABLED)
            if not ledger.exact_token_valid():
                raise SessionRejected(Code.UNAUTHENTICATED)
            if not ledger.identity_matches():
                raise SessionRejected(Code.POLICY_DENIED)
            if ledger.replay is not None:
                _replay(ledger, request)
            _validate_original(ledger)
            if request.action == "renew":
                _check_prior(ledger)
            else:
                if not STT_CIRCUIT.available():
                    raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
                if mapping_id is None:
                    return CloudContext(
                        ledger.org.pk, ledger.license.pk, ledger.device.pk, "stt",
                        ledger.plan, None, request.policy_version,
                    )

            mapping = _check_mapping(ledger, deps)
            secret = None
            if request.action == "start":
                try:
                    secret = open_secret(mapping)
                except (ProviderCustodyError, ProviderConfigurationError):
                    raise SessionRejected(Code.PROVIDER_UNAVAILABLE) from None
            # Roll back an unsuccessful candidate week, upgrade, slice or renderer
            # while retaining the outer transaction's locked decision and audit.
            original_week = ledger.week
            try:
                with transaction.atomic():
                    decision = ledger.reserve(request, request.policy_version)
                    if secret is not None:
                        return _claim(ledger, decision, secret, recorder)
                    row = UsageReservation.objects.get(pk=decision.reservation_id)
                    result, reply = _render(row, decision, None, deps, previous=ledger.previous)
            except Exception:
                ledger.week = original_week
                raise
        except DatabaseError:
            raise
        except SessionRejected as error:
            denial = error
        except ReservationRejected as error:
            denial = _ledger_refusal(error)
        except Exception:
            denial = SessionRejected(Code.INTERNAL)
        else:
            recorder.record(org=ledger.org, at=ledger.now, week=ledger.week, row=row)
            return result, reply

        history = ledger.replay if ledger.owns(ledger.replay) else None
        recorder.record(org=ledger.org, at=ledger.now, week=ledger.week, row=history,
                        replay=ledger.replay is not None, reason=denial.code)
    raise denial


def _provision(context, token, clock):
    def provisioning_clock():
        try:
            return aware_utc(clock())
        except DatabaseError:
            raise
        except Exception:
            # This aborts Task 4's transaction before the outer denial writer.
            raise ReservationRejected("CLOCK_UNAVAILABLE") from None

    try:
        ready = ensure_provider_ready(context, authenticated_token_id=token.pk, clock=provisioning_clock)
    except ProvisioningRejected as error:
        raise SessionRejected({
            ProvisioningErrorCode.INVALID_CONTEXT: Code.VALIDATION_FAILED,
            ProvisioningErrorCode.INELIGIBLE: Code.POLICY_DENIED,
            ProvisioningErrorCode.ALLOWANCE_UNAVAILABLE: Code.QUOTA_EXHAUSTED,
        }.get(error.code, Code.PROVIDER_UNAVAILABLE)) from None
    except ProviderConfigurationError:
        raise SessionRejected(Code.CLOUD_NOT_ENABLED) from None
    if isinstance(ready, ProvisioningPending):
        raise SessionRejected(Code.PROVIDER_PROVISIONING, ready.retry_after_seconds)
    if isinstance(ready, CapacityUnavailable):
        raise SessionRejected(Code.PROVISIONING_CAPACITY_EXHAUSTED)
    if type(ready) is not ReadyMapping or ready.org_id != context.org_id or ready.provider != "deepgram":
        raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
    return ready.mapping_id


def _launch_once(authorization, deps):
    consumed = False

    def launch():
        nonlocal consumed
        if consumed:
            raise RuntimeError("STT launch already consumed")
        consumed = True
        for alias in connections:
            item = connections[alias]
            if item.in_atomic_block or (item.connection is not None and not item.get_autocommit()):
                return MintReceipt(DefiniteFailure(MintFailureCode.REQUEST_REJECTED_LOCALLY), None)
        connections.close_all()
        if any(connections[alias].connection is not None for alias in connections):
            return MintReceipt(DefiniteFailure(MintFailureCode.REQUEST_REJECTED_LOCALLY), None)

        try:
            invoked_at = deps.utc_clock()
            invoked_ns = deps.monotonic_ns()
            invoked_at = utc_instant(invoked_at)
        except Exception:
            return MintReceipt(DefiniteFailure(MintFailureCode.REQUEST_REJECTED_LOCALLY), None)
        end_ns = min(invoked_ns + 4_000_000_000, authorization.send_not_after_ns + 4_000_000_000)
        io_ns = end_ns - 500_000_000
        if (
            invoked_at >= authorization.send_not_after_utc or invoked_ns >= authorization.send_not_after_ns
            or io_ns - invoked_ns < 500_000_000
        ):
            return MintReceipt(DefiniteFailure(MintFailureCode.REQUEST_REJECTED_LOCALLY), None)
        dispatch = MintDispatch(authorization, invoked_at, invoked_ns, end_ns, io_ns)
        return deps.mint_callable(authorization.mapping_id, STT_MINT_POLICY, dispatch=dispatch)

    return launch()


def _validate_final_authority(ledger, deps, authorization, grant):
    row = ledger.reservation
    if row.state == State.RELEASED:
        raise SessionRejected(Code.RESERVATION_RELEASED)
    if row.state in (State.ISSUED, State.SETTLED):
        raise SessionRejected(Code.ALREADY_ISSUED)
    _validate_original(ledger)
    mapping = _check_mapping(ledger, deps, revision=authorization.mapping_revision)
    if (
        mapping.pk != authorization.mapping_id or not ledger.owns(row)
        or mapping.parent_scope_id != authorization.parent_scope_id
        or mapping.external_api_key_id != authorization.external_api_key_id
        or not row.authorized_from <= ledger.now < min(row.authorized_until, row.expires_at, grant.expires_at)
    ):
        raise SessionRejected(Code.PROVIDER_UNAVAILABLE)
    if ledger.remaining_without(row) < STT_SLICE_SECONDS:
        raise SessionRejected(Code.QUOTA_EXHAUSTED)


def _finalize(identity, authorization, deps, recorder, receipt, *, force_denial=None):
    denial = SessionRejected(Code.PROVIDER_UNAVAILABLE)
    with locked_stt_ledger(
        **identity, reservation_id=authorization.reservation_id, clock=deps.utc_clock,
    ) as ledger:
        row, attempt = ledger.reservation, ledger.attempt
        if (
            attempt is None or attempt.pk != authorization.attempt_id
            or attempt.owner_nonce != authorization.owner_nonce
            or attempt.request_receipt_id != recorder.request_receipt_id
            or attempt.trigger_token_pk != identity["authenticated_token_id"]
            or attempt.prepared_at != authorization.reserved_at
            or attempt.dispatch_not_after != authorization.send_not_after_utc
            or attempt.mapping_revision != authorization.mapping_revision
        ):
            raise denial
        outcome = receipt.outcome
        grant = outcome.grant if isinstance(outcome, Granted) else None
        if grant is not None and (
            receipt.response_received_at is None or grant.expires_at <= receipt.response_received_at
        ):
            outcome = OutcomeUnknown(MintFailureCode.INVALID_PROVIDER_RESPONSE)
            grant = None
        if attempt.state != SttMintState.DISPATCHED or attempt.audit_event_id is not None:
            if attempt.state == SttMintState.UNKNOWN and grant is not None:
                known = (attempt.known_mint_received_at, attempt.credential_expires_at)
                incoming = (receipt.response_received_at, grant.expires_at)
                if known == (None, None):
                    attempt.known_mint_received_at, attempt.credential_expires_at = incoming
                    attempt.save(update_fields=["known_mint_received_at", "credential_expires_at"])
                    row.last_minted_at = receipt.response_received_at
                    row.save(update_fields=["last_minted_at"])
                elif known != incoming:
                    logger.warning("STT receipt enrichment conflicts with finalized facts")
        else:
            result = _apply_receipt(ledger, authorization, deps, recorder, receipt, outcome, grant,
                                    force_denial=force_denial)
            if not isinstance(result, SessionRejected):
                return result
            denial = result
    raise denial


def _apply_receipt(ledger, authorization, deps, recorder, receipt, outcome, grant, *, force_denial):
    row, attempt = ledger.reservation, ledger.attempt
    denial = SessionRejected(Code.PROVIDER_UNAVAILABLE)
    prepared = None
    if grant is not None:
        try:
            if force_denial is not None:
                raise SessionRejected({
                    State.RELEASED: Code.RESERVATION_RELEASED,
                    State.ISSUED: Code.ALREADY_ISSUED,
                    State.SETTLED: Code.ALREADY_ISSUED,
                }.get(row.state, force_denial))
            _validate_final_authority(ledger, deps, authorization, grant)
            row.issued_at = ledger.now
            decision = ReservationDecision(
                row.pk, State.ISSUED, row.units, row.authorized_from, row.authorized_until, row.retry_count,
            )
            prepared = _render(row, decision, grant, deps)
        except (_SerializeFailure, DatabaseError):
            raise
        except SessionRejected as error:
            denial = error
        except Exception:
            denial = SessionRejected(Code.INTERNAL)
        attempt.credential_expires_at = grant.expires_at
        attempt.known_mint_received_at = receipt.response_received_at
        row.last_minted_at = receipt.response_received_at
        if prepared is not None:
            attempt.state = SttMintState.GRANTED
            row.state = State.ISSUED
            row.save(update_fields=["state", "issued_at", "last_minted_at"])
        else:
            attempt.state = SttMintState.DISCARDED
            row.save(update_fields=["last_minted_at"])
    elif isinstance(outcome, DefiniteFailure):
        attempt.state = SttMintState.DEFINITE_FAILURE
        attempt.failure_code = outcome.code
        if row.state == State.RESERVED:
            row.state = State.RELEASED
            row.save(update_fields=["state"])
    else:
        attempt.state = SttMintState.UNKNOWN
        attempt.failure_code = outcome.code

    attempt.finished_at = max(attempt.prepared_at, ledger.now)
    attempt.audit_event = recorder.record(
        org=ledger.org, at=ledger.now, week=ledger.week, row=row, reason=None if prepared is not None else denial.code,
    )
    attempt.save(update_fields=[
        "state", "finished_at", "credential_expires_at", "known_mint_received_at", "failure_code", "audit_event",
    ])
    return prepared if prepared is not None else denial



def _complete_mint(identity, authorization, deps, recorder, receipt):
    try:
        try:
            return _finalize(identity, authorization, deps, recorder, receipt)
        except _SerializeFailure:
            return _finalize(identity, authorization, deps, recorder, receipt, force_denial=Code.INTERNAL)
    except ReservationRejected as error:
        if error.code != "CLOCK_UNAVAILABLE":
            raise
        # This transaction can record the known mint but has no authority to
        # emit it. The original authority clock never gets refreshed for issue.
        denial_deps = replace(deps, utc_clock=timezone.now)
        return _finalize(identity, authorization, denial_deps, recorder, receipt, force_denial=Code.PROVIDER_UNAVAILABLE)


def _record_provisioning_denial(identity, deps, recorder, denial):
    with locked_stt_ledger(**identity, clock=deps.utc_clock) as ledger:
        if not ledger.exact_token_valid():
            denial = SessionRejected(Code.UNAUTHENTICATED)
        elif not ledger.eligible():
            denial = SessionRejected(Code.POLICY_DENIED)
        recorder.record(org=ledger.org, at=ledger.now, week=ledger.week, reason=denial.code)
    return denial


def _issue_stt_session(token: DeviceToken, request: SessionRequest,
                       deps: SessionDependencies) -> tuple[SessionResult, PreparedHttpReply]:
    validate_session_request(request)
    if type(token) is not DeviceToken or type(token.pk) is not int or token.pk <= 0:
        raise SessionRejected(Code.UNAUTHENTICATED)
    device = token.device
    identity = {
        "org_id": device.customer_id, "license_id": device.license_key_id,
        "device_id": device.pk, "authenticated_token_id": token.pk,
    }
    if any(type(value) is not int or value <= 0 for value in identity.values()):
        raise SessionRejected(Code.UNAUTHENTICATED)
    budget = deps.rate_evaluator(org_id=device.customer_id, device_id=device.pk,
                                 kind="admission" if request.action == "start" else "renewal")
    if budget.outcome is not BudgetOutcome.ALLOWED:
        raise SessionRejected(Code.RATE_LIMITED, budget.retry_after_seconds)

    recorder = OutcomeRecorder(device.device_public_id, device.customer_id, request)
    try:
        candidate = _admission(identity, request, deps, recorder)
        if isinstance(candidate, CloudContext):
            try:
                mapping_id = _provision(candidate, token, deps.utc_clock)
            except SessionRejected as error:
                raise _record_provisioning_denial(identity, deps, recorder, error) from None
            candidate = _admission(identity, request, deps, recorder, mapping_id=mapping_id)
        if not isinstance(candidate, SttDispatchAuthorization):
            return candidate
        try:
            receipt = _launch_once(candidate, deps)
        except Exception:
            receipt = MintReceipt(OutcomeUnknown(MintFailureCode.TRANSPORT_ERROR), None)
        return _complete_mint(identity, candidate, deps, recorder, receipt)
    except ReservationRejected as error:
        denial = _ledger_refusal(error)
        # The failed authority transaction has unwound. Record the completed
        # refusal without creating a new week.
        if error.code in ("PROVIDER_UNAVAILABLE", "CLOCK_UNAVAILABLE") and not recorder._used:
            denial_deps = replace(deps, utc_clock=timezone.now) if error.code == "CLOCK_UNAVAILABLE" else deps
            denial = _record_provisioning_denial(identity, denial_deps, recorder, denial)
        raise denial from None
    except DatabaseError:
        # A commit may have succeeded even if its acknowledgement was lost.
        # Never repeat authorization, release a hold or write a second outcome.
        raise SessionRejected(Code.INTERNAL) from None
