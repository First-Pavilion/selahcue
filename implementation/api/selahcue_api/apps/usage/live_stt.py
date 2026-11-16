"""Lock and sample live STT authority without changing foundation callers."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from uuid import UUID

from django.db import connection, transaction
from django.db.models import Q

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.catalogue.contracts import EffectivePlan
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.devices.cloud_eligibility import CloudEligibilityFacts, cloud_eligibility
from selahcue_api.apps.devices.models import Device, DeviceToken
from selahcue_api.apps.license_keys.models import AppLicenseKey
from selahcue_api.apps.providers.models import ProviderCredential, SttMintAttempt

from .contracts import CloudContext, ReservationDecision, ReservationRejected, ReservationState, SessionRequest
from .models import UsageReservation, UsageWeek
from .services import (
    _apply_upgrade, _balance, _create_week, _current_week, _next_week_bounds,
    _reserve_from_snapshot, stt_request_digest,
)
from .weeks import utc_instant


@dataclass
class LockedSttLedger:
    org: CustomerOrg
    license: AppLicenseKey | None
    device: Device | None
    token: DeviceToken | None
    now: datetime
    monotonic_ns: int | None
    plan: EffectivePlan
    week: UsageWeek | None
    replay: UsageReservation | None
    previous: UsageReservation | None
    reservation: UsageReservation | None
    mapping: ProviderCredential | None
    attempt: SttMintAttempt | None

    def exact_token_valid(self):
        return (
            self.token is not None and self.device is not None
            and self.token.device_id == self.device.pk and self.token.status == "ACTIVE"
            and self.token.issued_at <= self.now < self.token.expires_at
        )

    def identity_matches(self):
        key, device = self.license, self.device
        return bool(
            key and device and key.customer_id == self.org.pk == device.customer_id
            and device.license_key_id == key.pk
        )

    def eligible(self):
        org, key, device, token = self.org, self.license, self.device, self.token
        return bool(key and device and token and cloud_eligibility(
            CloudEligibilityFacts(
                org.pk, org.status, key.pk, key.customer_id, key.status, key.starts_at, key.expires_at,
                device.pk, device.customer_id, device.license_key_id, device.status,
                token.pk, token.device_id, token.status, token.issued_at, token.expires_at,
            ), at=self.now,
        ))

    def owns(self, row):
        return row is not None and (
            row.device_id == getattr(self.device, "pk", None)
            and row.license_id == getattr(self.license, "pk", None)
        )

    def remaining_without(self, reservation: UsageReservation):
        return _balance(self.week, self.plan, "stt", excluding=reservation.pk,
                        virtual_upgrade=self.plan.rank > self.week.high_water_rank)

    def reserve(self, request: SessionRequest, policy_version: str) -> ReservationDecision:
        now = self.now
        if self.week is None:
            geometry = _next_week_bounds(self.org, now)
            if now < geometry[0].admissions_start_at:
                raise ReservationRejected("QUOTA_EXHAUSTED")
            self.week = _create_week(self.org, self.plan, geometry)
        if now < self.week.admissions_start_at:
            raise ReservationRejected("QUOTA_EXHAUSTED")
        _apply_upgrade(self.week, self.plan, now)
        context = CloudContext(
            self.org.pk, self.license.pk, self.device.pk, "stt", self.plan, self.mapping.pk, policy_version,
        )
        decision = _reserve_from_snapshot(
            context, request.idempotency_key, stt_request_digest(request), now,
            self.org, self.license, self.week, self.plan, self.previous,
        )
        if isinstance(decision, ReservationRejected):
            raise decision
        return decision


def _by_pk(model, pk):
    return model.objects.select_for_update().filter(pk=pk).first()


class _WeekMoved(Exception):
    pass


def _sample_clock(clock, monotonic_ns=None):
    try:
        at = clock()
        monotonic_sample = monotonic_ns() if monotonic_ns is not None else None
        if monotonic_ns is not None and (type(monotonic_sample) is not int or monotonic_sample < 0):
            raise ValueError("Invalid monotonic sample")
        return utc_instant(at), monotonic_sample
    except Exception:
        raise ReservationRejected("CLOCK_UNAVAILABLE") from None


def _lock_snapshot(org_id, license_id, device_id, token_id, reservation_id, previous_id, mapping_id,
                   clock, replay_key, monotonic_ns):
    org = CustomerOrg.objects.select_for_update(no_key=True).filter(pk=org_id).first()
    if org is None:
        raise ReservationRejected("INVALID_CONTEXT")
    license = _by_pk(AppLicenseKey, license_id)
    device = _by_pk(Device, device_id)
    token = _by_pk(DeviceToken, token_id)
    seed_time = None if reservation_id is not None else _sample_clock(clock)[0]
    current = None if seed_time is None else _current_week(org, seed_time)
    org_rows = UsageReservation.objects.filter(org=org)
    historical_id = None
    if replay_key is not None:
        historical_id = org_rows.filter(meter="stt", idempotency_key=replay_key).values_list("pk", flat=True).first()
    refs = list(org_rows.filter(
        Q(state=ReservationState.RESERVED)
        | Q(meter="stt", pk__in=[historical_id, reservation_id])
        | Q(meter="stt", pk=previous_id, device_id=device_id, license_id=license_id)
    ).values_list("pk", "week_id"))
    week_ids = {week for _, week in refs}
    if current is not None:
        week_ids.add(current.pk)
    weeks = {row.pk: row for row in UsageWeek.objects.select_for_update().filter(
        org=org, pk__in=week_ids,
    ).order_by("starts_at", "pk")}
    rows = {row.pk: row for row in org_rows.select_for_update().filter(
        pk__in=[pk for pk, _ in refs],
    ).order_by("pk")}
    previous, reservation, replay = (rows.get(pk) for pk in (previous_id, reservation_id, historical_id))
    if previous is not None and (
        previous.meter != "stt" or previous.device_id != device_id or previous.license_id != license_id
    ):
        previous = None
    if reservation_id is not None and reservation is None:
        raise ReservationRejected("NOT_FOUND")
    binding = reservation or previous
    mapping = None if replay is not None else ProviderCredential.objects.select_for_update().filter(
        pk=binding.provider_mapping_id if binding else mapping_id, org=org,
    ).first()
    attempt = None if reservation is None else SttMintAttempt.objects.select_for_update().filter(
        reservation=reservation,
    ).first()
    now, final_mono = _sample_clock(clock, monotonic_ns)
    if reservation is not None:
        week = weeks[reservation.week_id]
    else:
        final_week = _current_week(org, now)
        if getattr(final_week, "pk", None) != getattr(current, "pk", None):
            raise _WeekMoved
        if current is None and _next_week_bounds(org, seed_time) != _next_week_bounds(org, now):
            # Prior model instances compare by their primary keys.
            raise _WeekMoved
        week = weeks[current.pk] if current is not None else None
    org_rows.filter(
        pk__in=rows, state=ReservationState.RESERVED, expires_at__lte=now,
    ).update(state=ReservationState.RELEASED)
    for row in rows.values():
        if row.state == ReservationState.RESERVED and row.expires_at <= now:
            row.state = ReservationState.RELEASED
    return LockedSttLedger(
        org, license, device, token, now, final_mono, effective_plan(org, now), week, replay, previous, reservation,
        mapping, attempt,
    )


@contextmanager
def _locked_stt_ledger(*, org_id, license_id, device_id, authenticated_token_id,
                       reservation_id=None, previous_id=None, mapping_id=None, clock, replay_key=None,
                       monotonic_ns=None):
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ReservationRejected("INVALID_CONTEXT")
    if any(type(pk) is not int or pk <= 0 for pk in (org_id, license_id, device_id, authenticated_token_id)):
        raise ReservationRejected("INVALID_CONTEXT")
    for attempt in range(2):
        try:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '2000ms'")
                        cursor.execute("SET LOCAL statement_timeout = '5000ms'")
                ledger = _lock_snapshot(org_id, license_id, device_id, authenticated_token_id,
                                        reservation_id, previous_id, mapping_id, clock, replay_key, monotonic_ns)
                yield ledger
                return
        except _WeekMoved:
            if attempt == 1:
                raise ReservationRejected("PROVIDER_UNAVAILABLE") from None


def locked_stt_ledger(*, org_id, license_id, device_id, authenticated_token_id, reservation_id=None,
                      previous_id=None, mapping_id=None, clock: Callable[[], datetime]):
    return _locked_stt_ledger(
        org_id=org_id, license_id=license_id, device_id=device_id,
        authenticated_token_id=authenticated_token_id, reservation_id=reservation_id,
        previous_id=previous_id, mapping_id=mapping_id, clock=clock,
    )


def locked_stt_admission(*, request, **kwargs):
    return _locked_stt_ledger(
        replay_key=request.idempotency_key, previous_id=request.previous_reservation_id, **kwargs,
    )
