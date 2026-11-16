"""Abandoned mint metadata recovery for usage workers."""
from datetime import timedelta
from uuid import UUID

from django.apps import apps
from django.db import DatabaseError
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.audit.services import record_audit_event
from selahcue_api.apps.usage.models import UsageReservation, UsageWeek
from selahcue_api.apps.usage.observation_contracts import MintRecoveryResult, UsageFailureCode, UsageRejected
from selahcue_api.apps.usage.usage_tasks import bounded_transaction, require_usage_role
from selahcue_api.apps.usage.weeks import utc_instant
from selahcue_api.graphql.context import ActorContext, ActorKind

from .contracts import MintFailureCode, SttMintState
from .models import ProviderCredential


def mint_attempt_model():
    try:
        return apps.get_model("selahcue_providers", "SttMintAttempt")
    except LookupError:
        return None


def _recover(model, attempt_id, clock):
    with bounded_transaction():
        hint = model.objects.filter(pk=attempt_id).values(
            "reservation_id", "reservation__org_id", "reservation__week_id",
        ).first()
        if hint is None:
            return MintRecoveryResult(attempt_id, "unchanged", False)
        CustomerOrg.objects.select_for_update(no_key=True).get(pk=hint["reservation__org_id"])
        UsageWeek.objects.select_for_update().get(pk=hint["reservation__week_id"])
        reservation = UsageReservation.objects.select_for_update().get(pk=hint["reservation_id"])
        if reservation.provider_mapping_id is None or reservation.meter != "stt":
            return MintRecoveryResult(attempt_id, "unavailable", False)
        mapping = ProviderCredential.objects.select_for_update().get(pk=reservation.provider_mapping_id)
        row = model.objects.select_for_update().get(pk=attempt_id)
        now = utc_instant(clock())
        if row.reservation_id != reservation.pk or mapping.org_id != reservation.org_id or mapping.provider != "deepgram":
            return MintRecoveryResult(attempt_id, "unavailable", False)
        if row.state != SttMintState.DISPATCHED or now < row.dispatch_not_after + timedelta(seconds=4):
            return MintRecoveryResult(attempt_id, "unchanged", False)
        row.state = SttMintState.UNKNOWN
        row.finished_at = now
        row.failure_code = MintFailureCode.PROVIDER_OUTCOME_UNPROVEN
        row.save(update_fields=("state", "finished_at", "failure_code"))
        record_audit_event(
            ActorContext(kind=ActorKind.SERVICE, actor_id="usage-mint-recovery"),
            action="cloud.stt.mint_recovery", target_type="UsageReservation", target_id=str(reservation.pk),
            request_id=str(attempt_id), reason="MINT_OUTCOME_UNKNOWN", after={"state": SttMintState.UNKNOWN},
            source_surface="provider_usage",
        )
        return MintRecoveryResult(attempt_id, "recovered_unknown", True)


def recover_abandoned_stt_mint(attempt_id: UUID, *, clock=timezone.now) -> MintRecoveryResult:
    require_usage_role()
    if type(attempt_id) is not UUID:
        raise ValueError("Expected a mint attempt UUID")
    model = mint_attempt_model()
    if model is None:
        return MintRecoveryResult(attempt_id, "unavailable", False)
    for index in range(2):
        try:
            return _recover(model, attempt_id, clock)
        except DatabaseError as error:
            sqlstate = getattr(error.__cause__, "sqlstate", None)
            if sqlstate == "42P01":
                return MintRecoveryResult(attempt_id, "unavailable", False)
            if sqlstate in {"40001", "40P01"} and index == 0:
                continue
            if sqlstate in {"40001", "40P01", "55P03", "57014"}:
                raise UsageRejected(UsageFailureCode.DATABASE_BUSY) from None
            raise
