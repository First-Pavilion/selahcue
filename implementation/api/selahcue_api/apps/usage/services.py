"""Transactional weekly allowance accounting. No provider or content-store dependencies."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from uuid import UUID

from django.db import IntegrityError, connection, transaction
from django.db.models import Q, Sum

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.contracts import EffectivePlan
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.devices.models import Device, DeviceStatus
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.license_keys.selection import ACTIVATABLE_KEY_STATUSES
from selahcue_api.apps.providers.models import ProviderCredential
from selahcue_api.apps.usage.contracts import (
    CloudContext, DeliveryCreditResult, QuotaSnapshot, ReservationDecision,
    ReservationRejected, ReservationState, SessionRequest,
)
from selahcue_api.apps.usage.models import OPEN_STATES, NoteDeliveryCredit, UsageReservation, UsageWeek
from selahcue_api.apps.usage.weeks import WEEK, LocalWeek, local_week, utc_instant

STT_SLICE_SECONDS = 300
STT_RESERVED_TTL_SECONDS = 120
NOTES_RESERVED_TTL_SECONDS = 300
assert STT_RESERVED_TTL_SECONDS > 4 + 30  # Mint absolute deadline + credential maximum TTL.
assert NOTES_RESERVED_TTL_SECONDS > 60 + 180  # Queue wait + task hard time limit.


def _current_week(org: CustomerOrg, at: datetime, *, lock: bool = False) -> UsageWeek | None:
    rows = UsageWeek.objects.filter(org=org, starts_at__lte=at, ends_at__gt=at)
    if lock:
        rows = rows.select_for_update()
    return rows.order_by("-starts_at").first()


def _next_week_bounds(org: CustomerOrg, at: datetime) -> tuple[LocalWeek, UsageWeek | None]:
    prior = UsageWeek.objects.filter(org=org, ends_at__lte=at).order_by("-starts_at").first()
    previous = (prior.week_start_local, prior.ends_at) if prior is not None else None
    bounds = local_week(org.timezone, at, previous=previous)
    if prior is not None and prior.week_start_local + WEEK != bounds.monday:
        prior = None
    return bounds, prior


def _carried_debt(prior: UsageWeek | None, stt_limit: int, notes_limit: int) -> tuple[int, int]:
    if prior is None:
        return 0, 0
    return (
        min(stt_limit, max(0, prior.stt_seconds_settled - prior.high_water_stt_seconds_limit)),
        min(notes_limit, max(0, prior.notes_settled - prior.high_water_notes_limit)),
    )


def _open_week(org: CustomerOrg, plan: EffectivePlan, at: datetime) -> UsageWeek:
    week = _current_week(org, at, lock=True)
    if week is not None:
        return week
    return _create_week(org, plan, _next_week_bounds(org, at))


def _create_week(org, plan, geometry):
    bounds, prior = geometry
    stt_debt, notes_debt = _carried_debt(prior, plan.stt_seconds_limit, plan.notes_limit)
    # All ledger mutations take the org lock first. Only that holder can create a week.
    return UsageWeek.objects.create(
        org=org, week_start_local=bounds.monday, tz_name=bounds.tz_name,
        starts_at=bounds.start, ends_at=bounds.end, counted_from=bounds.start,
        admissions_start_at=bounds.admissions_start_at,
        high_water_rank=plan.rank,
        opening_stt_seconds_limit=plan.stt_seconds_limit, opening_notes_limit=plan.notes_limit,
        high_water_stt_seconds_limit=plan.stt_seconds_limit, high_water_notes_limit=plan.notes_limit,
        stt_seconds_carried_debt=stt_debt, notes_carried_debt=notes_debt,
    )


def _apply_upgrade(week: UsageWeek, plan: EffectivePlan, at: datetime) -> None:
    if plan.rank <= week.high_water_rank:
        return
    week.high_water_rank = plan.rank
    week.high_water_stt_seconds_limit = plan.stt_seconds_limit
    week.high_water_notes_limit = plan.notes_limit
    week.counted_from = at
    week.stt_seconds_settled = 0
    week.notes_settled = 0
    week.save(update_fields=[
        "high_water_rank", "high_water_stt_seconds_limit", "high_water_notes_limit",
        "counted_from", "stt_seconds_settled", "notes_settled",
    ])


def _open_rows(week: UsageWeek):
    return UsageReservation.objects.filter(week=week, state__in=OPEN_STATES)


def _remaining_units(limit, settled, held, debt):
    return max(0, limit - settled - held - debt)


def remaining(org: CustomerOrg, at: datetime) -> tuple[QuotaSnapshot, ...]:
    now = utc_instant(at)
    plan = effective_plan(org, now)
    week = _current_week(org, now)
    if week is None:
        bounds, prior = _next_week_bounds(org, now)
        stt_debt, notes_debt = _carried_debt(prior, plan.stt_seconds_limit, plan.notes_limit)
        stt_settled = notes_settled = stt_held = notes_held = 0
        unavailable = now < bounds.admissions_start_at
        resets_at = bounds.admissions_start_at if unavailable else bounds.end
        status = "not_initialized"
    else:
        stt_debt, notes_debt = week.stt_seconds_carried_debt, week.notes_carried_debt
        unavailable = now < week.admissions_start_at
        virtual_upgrade = not unavailable and plan.rank > week.high_water_rank
        stt_settled = 0 if virtual_upgrade else week.stt_seconds_settled
        notes_settled = 0 if virtual_upgrade else week.notes_settled
        holds = _open_rows(week).aggregate(
            stt=Sum("units", filter=Q(meter="stt"), default=0),
            notes=Sum("units", filter=Q(meter="notes"), default=0),
        )
        stt_held, notes_held = holds["stt"], holds["notes"]
        resets_at = week.admissions_start_at if unavailable else week.ends_at
        status = "stale"

    return tuple(
        QuotaSnapshot(
            meter, limit, settled, held, debt,
            0 if unavailable else _remaining_units(limit, settled, held, debt),
            now, resets_at, status,
        )
        for meter, limit, settled, held, debt in (
            ("stt", plan.stt_seconds_limit, stt_settled, stt_held, stt_debt),
            ("notes", plan.notes_limit, notes_settled, notes_held, notes_debt),
        )
    )


def reserve(context: CloudContext, request: SessionRequest, now: datetime) -> ReservationDecision:
    if context.meter != "stt" or request.retry or not request.consent_version:
        raise ReservationRejected("INVALID_REQUEST")
    if request.policy_version != context.policy_version:
        raise ReservationRejected("INVALID_REQUEST")
    starts_new = (
        request.action == "start" and request.socket_mode == "new"
        and request.previous_reservation_id is None
    )
    renews = (
        request.action == "renew" and request.socket_mode == "existing"
        and isinstance(request.previous_reservation_id, UUID)
    )
    if not (starts_new or renews):
        raise ReservationRejected("INVALID_REQUEST")
    return _reserve(
        context, request.idempotency_key, stt_request_digest(request),
        utc_instant(now), request.previous_reservation_id,
    )


def stt_request_digest(request: SessionRequest) -> str:
    payload = json.dumps([
        request.action, str(request.previous_reservation_id), request.socket_mode,
        request.consent_version, request.policy_version,
    ], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def reserve_notes_job(
    context: CloudContext, idempotency_key: UUID, request_digest: str, now: datetime,
) -> ReservationDecision:
    if context.meter != "notes" or not re.fullmatch(r"[0-9a-f]{64}", request_digest):
        raise ReservationRejected("INVALID_REQUEST")
    return _reserve(context, idempotency_key, request_digest, utc_instant(now))


def _reserve(
    context: CloudContext, key: UUID, request_hash: str, now: datetime,
    previous_id: UUID | None = None,
) -> ReservationDecision:
    if not isinstance(key, UUID):
        raise ReservationRejected("INVALID_REQUEST")
    if (
        (context.provider_mapping_id is not None and not isinstance(context.provider_mapping_id, UUID))
        or not 0 < len(context.policy_version) <= 64
    ):
        raise ReservationRejected("INVALID_CONTEXT")
    with transaction.atomic():
        decision = _reserve_locked(context, key, request_hash, now, previous_id)
    if isinstance(decision, ReservationRejected):
        raise decision
    return decision


def _reserve_locked(
    context: CloudContext, key: UUID, request_hash: str, now: datetime, previous_id: UUID | None,
) -> ReservationDecision | ReservationRejected:
    org = CustomerOrg.objects.select_for_update(no_key=True).filter(pk=context.org_id).first()
    if org is None:
        raise ReservationRejected("INVALID_CONTEXT")
    license_key = AppLicenseKey.objects.select_for_update().filter(
        pk=context.license_id, customer=org, status__in=ACTIVATABLE_KEY_STATUSES,
        starts_at__lte=now, expires_at__gt=now,
    ).first()
    if license_key is None or not Device.objects.filter(
        pk=context.device_id, license_key=license_key, customer=org, status=DeviceStatus.ACTIVE,
    ).exists():
        raise ReservationRejected("INVALID_CONTEXT")

    # Authorization uses current catalogue data under the ledger lock rather than the
    # plan snapshot captured by the authenticated caller before admission.
    plan = effective_plan(org, now)
    week = _open_week(org, plan, now)
    if now < week.admissions_start_at:
        # Roll back a week created solely by this refused attempt. A committed
        # reconciliation row and its pre-admission usage remain untouched.
        raise ReservationRejected("QUOTA_EXHAUSTED")
    _apply_upgrade(week, plan, now)
    UsageReservation.objects.filter(
        org=org, state=ReservationState.RESERVED, expires_at__lte=now,
    ).update(state=ReservationState.RELEASED)
    replay = UsageReservation.objects.filter(org=org, meter=context.meter, idempotency_key=key).first()
    if replay is not None:
        if (
            replay.device_id != context.device_id or replay.license_id != context.license_id
            or replay.provider_mapping_id != context.provider_mapping_id
            or replay.request_hash != request_hash or replay.policy_version != context.policy_version
        ):
            return ReservationRejected("IDEMPOTENCY_CONFLICT")
        if replay.state == ReservationState.RELEASED:
            return ReservationRejected("RESERVATION_RELEASED")
        return ReservationRejected("ALREADY_ISSUED")

    is_stt = context.meter == "stt"
    previous = None
    if previous_id is not None:
        previous = UsageReservation.objects.select_for_update().filter(
            pk=previous_id, org=org, meter="stt", device_id=context.device_id, license=license_key,
            state=ReservationState.ISSUED, authorized_from__lte=now, authorized_until__gt=now,
        ).first()
        if (
            previous is None or previous.provider_mapping_id != context.provider_mapping_id
            or UsageReservation.objects.filter(renews_id=previous_id).exists()
        ):
            return ReservationRejected("INVALID_RENEWAL")

    if context.provider_mapping_id is not None:
        mapping = ProviderCredential.objects.select_for_update().filter(
            pk=context.provider_mapping_id, org_id=org.pk,
            provider="deepgram" if is_stt else "openai", state="ACTIVE",
            secret_version=1, wrapping_key_id__isnull=False,
            secret_nonce__isnull=False, secret_ciphertext__isnull=False,
        ).only("id").first()
        if mapping is None:
            raise ReservationRejected("INVALID_CONTEXT")

    return _reserve_from_snapshot(context, key, request_hash, now, org, license_key, week, plan, previous)


def _balance(week, plan, meter, *, excluding=None, virtual_upgrade=False):
    rows = _open_rows(week).filter(meter=meter)
    if excluding is not None:
        rows = rows.exclude(pk=excluding)
    held = rows.aggregate(total=Sum("units", default=0))["total"]
    if meter == "stt":
        settled = week.stt_seconds_settled
        debt = week.stt_seconds_carried_debt
        limit = plan.stt_seconds_limit
    else:
        settled = week.notes_settled
        debt = week.notes_carried_debt
        limit = plan.notes_limit
    return _remaining_units(limit, 0 if virtual_upgrade else settled, held, debt)


def _reserve_from_snapshot(context, key, request_hash, now, org, license_key, week, plan, previous):
    is_stt = context.meter == "stt"
    units = STT_SLICE_SECONDS if is_stt else 1
    ttl = STT_RESERVED_TTL_SECONDS if is_stt else NOTES_RESERVED_TTL_SECONDS
    authorized_from = previous.authorized_until if previous is not None else now
    state = ReservationState.ISSUED if previous is not None else ReservationState.RESERVED
    if _balance(week, plan, context.meter) < units:
        return ReservationRejected("QUOTA_EXHAUSTED")

    authorized_until = authorized_from + timedelta(seconds=STT_SLICE_SECONDS if is_stt else ttl)
    row = UsageReservation.objects.create(
        org=org, week=week, license=license_key, device_id=context.device_id, meter=context.meter,
        provider_mapping_id=context.provider_mapping_id,
        units=units, state=state, idempotency_key=key, request_hash=request_hash,
        policy_version=context.policy_version, admitted_at=now,
        authorized_from=authorized_from, authorized_until=authorized_until,
        issued_at=now if state == ReservationState.ISSUED else None,
        renews=previous, expires_at=now + timedelta(seconds=ttl),
    )
    return ReservationDecision(row.pk, state, units, authorized_from, authorized_until, row.retry_count)


def _lock_note_reservation(
    reservation_id: UUID, now: datetime, *, recalculate: bool,
) -> tuple[UsageWeek, UsageWeek | None, UsageReservation]:
    ref = UsageReservation.objects.filter(pk=reservation_id, meter="notes").values(
        "org_id", "license_id", "week_id",
    ).first()
    if ref is None:
        raise ReservationRejected("NOT_FOUND")
    CustomerOrg.objects.select_for_update(no_key=True).get(pk=ref["org_id"])
    AppLicenseKey.objects.select_for_update().get(pk=ref["license_id"], customer_id=ref["org_id"])
    week = UsageWeek.objects.select_for_update().get(pk=ref["week_id"], org_id=ref["org_id"])
    following = None
    if recalculate and now >= week.ends_at:
        following = UsageWeek.objects.select_for_update().filter(
            org_id=week.org_id, week_start_local=week.week_start_local + WEEK,
            starts_at__lte=now, ends_at__gt=now,
        ).first()
    reservation = UsageReservation.objects.select_for_update().get(pk=reservation_id, week=week)
    return week, following, reservation


def _refresh_note_balance(week: UsageWeek, following: UsageWeek | None) -> None:
    notes = UsageReservation.objects.filter(
        week=week, meter="notes", state=ReservationState.SETTLED,
        admitted_at__gte=week.counted_from, admitted_at__lt=week.ends_at,
    ).aggregate(published=Sum("units", default=0), credits=Sum("delivery_credit__units", default=0))
    week.notes_settled = max(0, notes["published"] - notes["credits"])
    week.save(update_fields=["notes_settled"])
    if following is not None:
        _, debt = _carried_debt(week, following.opening_stt_seconds_limit, following.opening_notes_limit)
        if debt != following.notes_carried_debt:
            following.notes_carried_debt = debt
            following.save(update_fields=["notes_carried_debt"])


def settle_notes_success(reservation_id: UUID, now: datetime) -> None:
    if not connection.in_atomic_block:
        raise transaction.TransactionManagementError("Notes publication must own the transaction")
    now = utc_instant(now)
    week, following, row = _lock_note_reservation(reservation_id, now, recalculate=True)
    if row.state != ReservationState.RESERVED or not row.admitted_at <= now < row.expires_at:
        raise ReservationRejected("INVALID_STATE")
    row.state = ReservationState.SETTLED
    row.save(update_fields=["state"])
    _refresh_note_balance(week, following)


def release_notes_failure(reservation_id: UUID, now: datetime) -> None:
    now = utc_instant(now)
    with transaction.atomic():
        _, _, row = _lock_note_reservation(reservation_id, now, recalculate=False)
        if row.state == ReservationState.RELEASED:
            return
        if row.state != ReservationState.RESERVED or now < row.admitted_at:
            raise ReservationRejected("INVALID_STATE")
        row.state = ReservationState.RELEASED
        row.save(update_fields=["state"])


def apply_note_delivery_credit(
    reservation_id: UUID, job_id: UUID, observed_at: datetime,
) -> DeliveryCreditResult:
    """Record an authenticated publication loss supplied by the future notes service."""
    now = utc_instant(observed_at)
    with transaction.atomic():
        week, following, row = _lock_note_reservation(reservation_id, now, recalculate=True)
        if row.state != ReservationState.SETTLED or now < row.admitted_at:
            raise ReservationRejected("INVALID_STATE")
        existing = (
            NoteDeliveryCredit.objects.filter(Q(reservation=row) | Q(note_job_id=job_id))
            .values_list("reservation_id", "note_job_id")
            .first()
        )
        if existing is not None:
            if existing == (reservation_id, job_id):
                return DeliveryCreditResult(False, 0, week.pk)
            raise ReservationRejected("CREDIT_CONFLICT")
        try:
            with transaction.atomic():
                NoteDeliveryCredit.objects.create(
                    reservation=row, note_job_id=job_id, original_week=week, observed_at=now,
                )
        except IntegrityError as error:
            # Same org writes serialize. The globally unique job ID can also conflict
            # across different churches, so keep the constraint and isolate the insert.
            if NoteDeliveryCredit.objects.filter(note_job_id=job_id).exists():
                raise ReservationRejected("CREDIT_CONFLICT") from error
            raise
        _refresh_note_balance(week, following)
        return DeliveryCreditResult(True, 1, week.pk)
