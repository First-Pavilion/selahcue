from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest

from selahcue_api.apps.usage.contracts import ReservationRejected, ReservationState, SessionRequest
from selahcue_api.apps.usage.models import UsageReservation, UsageWeek
from selahcue_api.apps.usage.services import (
    release_notes_failure, remaining, reserve, reserve_notes_job, settle_notes_success,
)
from selahcue_api.apps.usage.weeks import local_week
from django.db import transaction

from test_effective_org_plan import NOW, church, context, device, licence, staff_grant

pytestmark = pytest.mark.django_db
DIGEST = sha256(b"synthetic-request").hexdigest()


def start():
    return SessionRequest(uuid4(), "start", None, "new", False, "v1", "v1")


def quota(org, meter, at=NOW):
    return next(snapshot for snapshot in remaining(org, at) if snapshot.meter == meter)


def reserve_note(inst, at=NOW):
    return reserve_notes_job(context(inst, "notes", at), uuid4(), DIGEST, at)


def publish(reservation, at):
    with transaction.atomic():
        settle_notes_success(reservation.reservation_id, at)


def test_pool_free_budget_across_devices_and_deny_fifth_slice():
    org = church()
    key = licence(org)
    first, second = device(key), device(key)
    for install in (first, second, first, second):
        decision = reserve(context(install, "stt"), start(), NOW)
        assert decision.units == 300
        assert decision.state == ReservationState.RESERVED
        assert decision.authorized_until - decision.authorized_from == timedelta(seconds=300)
    with pytest.raises(ReservationRejected) as caught:
        reserve(context(second, "stt"), start(), NOW)
    assert caught.value.code == "QUOTA_EXHAUSTED"
    snapshot = quota(org, "stt")
    assert (snapshot.limit, snapshot.held, snapshot.remaining) == (1200, 1200, 0)

    reserve_note(first)
    with pytest.raises(ReservationRejected, match="QUOTA_EXHAUSTED"):
        reserve_note(second)
    assert quota(org, "notes").remaining == 0


def test_upgrade_resets_once_and_downgrade_preserves_recorded_units():
    org = church()
    install = device(licence(org))
    publish(reserve_note(install), NOW)
    upgrade = NOW + timedelta(hours=1)
    downgrade = upgrade + timedelta(hours=1)
    staff_grant(org, "CORE", upgrade, downgrade)
    assert quota(org, "notes", upgrade).remaining == 5
    assert UsageWeek.objects.get(org=org).notes_settled == 1
    publish(reserve_note(install, upgrade), upgrade)
    assert quota(org, "notes", downgrade).settled == 1
    assert quota(org, "notes", downgrade).remaining == 0
    later = downgrade + timedelta(hours=1)
    staff_grant(org, "CORE", later, later + timedelta(hours=1))
    publish(reserve_note(install, later), later)
    week = UsageWeek.objects.get(org=org)
    assert (week.counted_from, week.high_water_rank, week.notes_settled) == (upgrade, 2, 2)


def test_carried_debt_keeps_opening_week_cap_after_upgrade():
    org = church()
    install = device(licence(org))
    reserve(context(install, "stt"), start(), NOW)
    UsageWeek.objects.filter(org=org).update(stt_seconds_settled=2500)
    following = NOW + timedelta(days=7)
    reserve_note(install, following)
    assert quota(org, "stt", following).carried_debt == 1200
    upgrade = following + timedelta(hours=1)
    staff_grant(org, "PRO", upgrade, upgrade + timedelta(days=1))
    reserve(context(install, "stt", upgrade), start(), upgrade)
    snapshot = quota(org, "stt", upgrade)
    assert (snapshot.limit, snapshot.carried_debt, snapshot.remaining) == (4800, 1200, 3300)
    third = following + timedelta(days=7)
    assert quota(org, "stt", third).carried_debt == 0


def test_falls_back_to_utc_for_corrupt_historical_timezone(caplog):
    org = church()
    Customer = type(org)
    Customer.objects.filter(pk=org.pk).update(timezone="Africa/Imaginary")
    org.refresh_from_db()
    assert quota(org, "notes").resets_at == datetime(2026, 11, 16, tzinfo=UTC)
    assert "invalid time zone" in caplog.text
    assert not UsageWeek.objects.filter(org=org).exists()


def test_local_midnight_transition_uses_first_valid_instant():
    bounds = local_week("Asia/Tehran", datetime(1993, 3, 22, 12, tzinfo=UTC))
    assert bounds.start == datetime(1993, 3, 21, 20, 30, tzinfo=UTC)
    assert bounds.end == datetime(1993, 3, 28, 19, 30, tzinfo=UTC)


def test_timezone_change_cannot_issue_early_reset():
    org = church("Etc/GMT+12")
    inst = device(licence(org))
    inside_week = NOW + timedelta(hours=4)
    publish(reserve_note(inst, inside_week), inside_week)
    original = UsageWeek.objects.get(org=org)
    assert original.ends_at == datetime(2026, 11, 16, 12, tzinfo=UTC)
    org.timezone = "Pacific/Kiritimati"
    org.save(update_fields=["timezone"])
    apparent_reset = datetime(2026, 11, 15, 10, tzinfo=UTC)
    with pytest.raises(ReservationRejected, match="QUOTA_EXHAUSTED"):
        reserve_note(inst, apparent_reset)
    assert UsageWeek.objects.filter(org=org).count() == 1
    reserve_note(inst, original.ends_at)
    following = UsageWeek.objects.exclude(pk=original.pk).get(org=org)
    assert following.starts_at == original.ends_at
    assert following.ends_at == datetime(2026, 11, 22, 10, tzinfo=UTC)
    assert following.tz_name == "Pacific/Kiritimati"


def test_replay_and_expiry_leave_original_reservation_terminal():
    install = device(licence(church()))
    ctx = context(install, "notes")
    key = uuid4()
    first = reserve_notes_job(ctx, key, DIGEST, NOW)
    with pytest.raises(ReservationRejected, match="ALREADY_ISSUED"):
        reserve_notes_job(ctx, key, DIGEST, NOW)
    assert quota(install.customer, "notes", NOW + timedelta(seconds=299)).held == 1
    another = reserve_note(install, NOW + timedelta(seconds=300))
    assert another.reservation_id != first.reservation_id
    with pytest.raises(ReservationRejected, match="RESERVATION_RELEASED"):
        reserve_notes_job(ctx, key, DIGEST, NOW + timedelta(seconds=300))
    assert UsageReservation.objects.get(pk=first.reservation_id).state == ReservationState.RELEASED
    release_notes_failure(first.reservation_id, NOW + timedelta(seconds=301))
    assert quota(install.customer, "notes", NOW + timedelta(seconds=301)).held == 1


def test_renewal_adds_authorization_to_bound_live_slice():
    from dataclasses import replace

    org = church()
    key = licence(org)
    first, second = device(key), device(key)
    initial = reserve(context(first, "stt"), start(), NOW)
    # Task5 owns post-mint issuance. This fixture exercises an existing live slice.
    UsageReservation.objects.filter(pk=initial.reservation_id).update(
        state=ReservationState.ISSUED, issued_at=NOW, last_minted_at=NOW,
    )
    renew = SessionRequest(uuid4(), "renew", initial.reservation_id, "existing", False, "v1", "v1")
    at = NOW + timedelta(seconds=240)
    with pytest.raises(ReservationRejected, match="INVALID_REQUEST"):
        reserve(context(first, "stt", at), replace(renew, socket_mode="new"), at)
    with pytest.raises(ReservationRejected, match="INVALID_RENEWAL"):
        reserve(context(second, "stt", at), renew, at)
    result = reserve(context(first, "stt", at), renew, at)
    assert result.state == ReservationState.ISSUED
    assert result.authorized_from == NOW + timedelta(seconds=300)
    assert result.authorized_until == NOW + timedelta(seconds=600)
    row = UsageReservation.objects.get(pk=result.reservation_id)
    assert row.last_minted_at is None
    assert row.renews_id == initial.reservation_id
    with pytest.raises(ReservationRejected, match="INVALID_RENEWAL"):
        reserve(context(first, "stt", at), replace(renew, idempotency_key=uuid4()), at)


def test_expired_or_cross_tenant_context_cannot_reserve():
    from dataclasses import replace

    org = church()
    unrelated_org = church()
    first = device(licence(org, length=1))
    second = device(licence(unrelated_org))
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve(replace(context(first, "stt"), device_id=second.pk), start(), NOW)
    expired = NOW + timedelta(days=1)
    with pytest.raises(ReservationRejected, match="INVALID_CONTEXT"):
        reserve(context(first, "stt", expired), start(), expired)
    assert not UsageWeek.objects.exists()


@pytest.mark.parametrize("preinitialize", [True, False])
def test_westward_transition_delays_admissions_but_preserves_accounting_bounds(preinitialize):
    from datetime import date

    from selahcue_api.apps.catalogue.org_plans import effective_plan
    from selahcue_api.apps.usage.services import _open_week

    org = church("Pacific/Kiritimati")
    install = device(licence(org))
    interval_start = datetime(2026, 11, 15, 10, tzinfo=UTC)
    admissions_start = datetime(2026, 11, 16, 12, tzinfo=UTC)
    interval_end = datetime(2026, 11, 23, 12, tzinfo=UTC)
    gap = datetime(2026, 11, 16, 0, tzinfo=UTC)
    publish(reserve_note(install), NOW)
    original = UsageWeek.objects.get(org=org)
    assert original.ends_at == interval_start

    org.timezone = "Etc/GMT+12"
    org.save(update_fields=["timezone"])
    if preinitialize:
        # Model the future reconcile writer's accounting initialization without any
        # provider ingestion. Synthetic settled usage stands in for its projection.
        with transaction.atomic():
            locked_org = type(org).objects.select_for_update(no_key=True).get(pk=org.pk)
            type(install.license_key).objects.select_for_update().get(pk=install.license_key_id)
            projected = _open_week(locked_org, effective_plan(org, gap), gap)
            projected.stt_seconds_settled = 300
            projected.save(update_fields=["stt_seconds_settled"])
        original.refresh_from_db()
        assert original.ends_at == interval_start
        # Re-editing the account zone cannot change a materialized boundary.
        org.timezone = "UTC"
        org.save(update_fields=["timezone"])

    for blocked_at in (interval_start, gap, admissions_start - timedelta(microseconds=1)):
        snapshot = quota(org, "stt", blocked_at)
        assert (snapshot.remaining, snapshot.resets_at) == (0, admissions_start)
        with pytest.raises(ReservationRejected, match="QUOTA_EXHAUSTED"):
            reserve(context(install, "stt", blocked_at), start(), blocked_at)

    assert UsageWeek.objects.filter(org=org).count() == (2 if preinitialize else 1)
    at = admissions_start if preinitialize else admissions_start + timedelta(hours=5)
    decision = reserve(context(install, "stt", at), start(), at)
    following = UsageWeek.objects.exclude(pk=original.pk).get(org=org)
    assert (
        following.week_start_local, following.starts_at, following.admissions_start_at,
        following.counted_from, following.ends_at,
    ) == (date(2026, 11, 16), interval_start, admissions_start, interval_start, interval_end)
    assert UsageReservation.objects.get(pk=decision.reservation_id).week_id == following.pk
    assert UsageWeek.objects.get(org=org, starts_at__lte=gap, ends_at__gt=gap).pk == following.pk
    assert UsageWeek.objects.get(org=org, starts_at__lte=interval_start, ends_at__gt=interval_start).pk == following.pk
    assert not UsageWeek.objects.filter(org=org, starts_at__lte=interval_end, ends_at__gt=interval_end).exists()
    assert quota(org, "stt", at).remaining == (600 if preinitialize else 900)
    assert quota(org, "stt", at).resets_at == interval_end


def test_late_first_reserve_never_stretches_current_week_or_revives_expired_debt():
    org = church("Pacific/Kiritimati")
    install = device(licence(org))
    reserve(context(install, "stt"), start(), NOW)
    previous = UsageWeek.objects.get(org=org)
    UsageWeek.objects.filter(pk=previous.pk).update(stt_seconds_settled=2500)
    org.timezone = "Etc/GMT+12"
    org.save(update_fields=["timezone"])

    at = datetime(2026, 11, 24, 12, tzinfo=UTC)
    reserve(context(install, "stt", at), start(), at)
    current = UsageWeek.objects.exclude(pk=previous.pk).get(org=org)
    assert current.starts_at == current.admissions_start_at == datetime(2026, 11, 23, 12, tzinfo=UTC)
    assert quota(org, "stt", at).carried_debt == 0

    record_at = datetime(2026, 11, 16, 0, tzinfo=UTC)
    historical = local_week(
        org.timezone, record_at, previous=(previous.week_start_local, previous.ends_at),
    )
    assert historical.start == previous.ends_at
    assert historical.start <= record_at < historical.admissions_start_at
    assert historical.admissions_start_at == datetime(2026, 11, 16, 12, tzinfo=UTC)
    assert historical.end == current.starts_at


def test_unmaterialized_transition_reprojects_after_another_timezone_change():
    org = church("Pacific/Kiritimati")
    install = device(licence(org))
    reserve_note(install)
    gap = datetime(2026, 11, 15, 20, tzinfo=UTC)
    org.timezone = "Etc/GMT+12"
    org.save(update_fields=["timezone"])
    assert quota(org, "notes", gap).resets_at == datetime(2026, 11, 16, 12, tzinfo=UTC)

    org.timezone = "UTC"
    org.save(update_fields=["timezone"])
    snapshot = quota(org, "notes", gap)
    assert (snapshot.remaining, snapshot.resets_at) == (0, datetime(2026, 11, 16, 0, tzinfo=UTC))
    assert UsageWeek.objects.filter(org=org).count() == 1


@pytest.mark.parametrize("month, day, hours", [(3, 4, 167), (10, 28, 169)])
def test_dst_week_duration_follows_local_mondays(month, day, hours):
    bounds = local_week("America/New_York", datetime(2026, month, day, 12, tzinfo=UTC))
    assert bounds.end - bounds.start == timedelta(hours=hours)
    assert bounds.admissions_start_at == bounds.start
