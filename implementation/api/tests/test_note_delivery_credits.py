from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import transaction

from selahcue_api.apps.usage.contracts import ReservationRejected, ReservationState
from selahcue_api.apps.usage.models import NoteDeliveryCredit, UsageReservation, UsageWeek
from selahcue_api.apps.usage.services import (
    apply_note_delivery_credit, release_notes_failure, settle_notes_success,
)

from test_effective_org_plan import NOW, church, device, licence, staff_grant
from test_usage_weeks import publish, quota, reserve_note

pytestmark = pytest.mark.django_db


def test_note_delivery_credit_is_unique_by_job_and_reservation():
    org = church()
    install = device(licence(org, "CORE"))
    first = reserve_note(install)
    publish(first, NOW)
    second = reserve_note(install)
    publish(second, NOW)

    job = uuid4()
    result = apply_note_delivery_credit(first.reservation_id, job, NOW)
    assert result.created and result.credited_units == 1
    replay = apply_note_delivery_credit(first.reservation_id, job, NOW)
    assert (replay.created, replay.credited_units, replay.week_id) == (False, 0, result.week_id)
    with pytest.raises(ReservationRejected, match="CREDIT_CONFLICT"):
        apply_note_delivery_credit(first.reservation_id, uuid4(), NOW)
    with pytest.raises(ReservationRejected, match="CREDIT_CONFLICT"):
        apply_note_delivery_credit(second.reservation_id, job, NOW)
    assert NoteDeliveryCredit.objects.count() == 1
    assert quota(org, "notes").settled == 1


def test_credit_preserves_terminal_state_and_original_week():
    org = church()
    install = device(licence(org))
    decision = reserve_note(install)
    publish(decision, NOW)
    following = NOW + timedelta(days=7)
    current = reserve_note(install, following)
    result = apply_note_delivery_credit(decision.reservation_id, uuid4(), following)
    original = UsageWeek.objects.get(pk=result.week_id)
    row = UsageReservation.objects.get(pk=decision.reservation_id)
    assert row.state == ReservationState.SETTLED
    assert row.week_id == original.pk
    assert original.notes_settled == 0
    assert UsageReservation.objects.get(pk=current.reservation_id).state == ReservationState.RESERVED
    assert quota(org, "notes", following).remaining == 0


def test_credit_does_not_reintroduce_pre_upgrade_units():
    org = church()
    install = device(licence(org))
    old = reserve_note(install)
    upgrade = NOW + timedelta(minutes=1)
    staff_grant(org, "CORE", upgrade, upgrade + timedelta(hours=1))
    new = reserve_note(install, upgrade)
    assert quota(org, "notes", upgrade).held == 2
    publish(old, upgrade)
    publish(new, upgrade)
    assert quota(org, "notes", upgrade).settled == 1
    apply_note_delivery_credit(old.reservation_id, uuid4(), upgrade)
    assert quota(org, "notes", upgrade).settled == 1


def test_note_terminal_changes_require_correct_state():
    org = church()
    install = device(licence(org))
    first = reserve_note(install)
    with pytest.raises(ReservationRejected, match="INVALID_STATE"):
        apply_note_delivery_credit(first.reservation_id, uuid4(), NOW)
    release_notes_failure(first.reservation_id, NOW)
    with transaction.atomic(), pytest.raises(ReservationRejected, match="INVALID_STATE"):
        settle_notes_success(first.reservation_id, NOW)
    second = reserve_note(install)
    publish(second, NOW)
    with pytest.raises(ReservationRejected, match="INVALID_STATE"):
        release_notes_failure(second.reservation_id, NOW)


@pytest.mark.parametrize("age, expected_debt", [(7, 0), (14, 1)])
def test_credit_adjusts_debt_only_while_following_week_is_open(age, expected_debt):
    from selahcue_api.apps.catalogue.models import PlanGrant
    from selahcue_api.apps.usage.services import reserve
    from test_effective_org_plan import NOTES_KEY, context
    from test_usage_weeks import start

    org = church()
    install = device(licence(org))
    publish(reserve_note(install), NOW)
    # A same-rank catalogue edit is honored for admission while preserving the
    # original one-unit snapshot used when measuring the week's overrun.
    grant = PlanGrant.objects.get(plan__is_fallback=True, dimension__key=NOTES_KEY)
    grant.raw_value = "2"
    grant.save(update_fields=["raw_value"])
    extra = reserve_note(install, NOW + timedelta(minutes=1))
    publish(extra, NOW + timedelta(minutes=1))
    original = UsageWeek.objects.get(org=org)
    assert (original.notes_settled, original.high_water_notes_limit) == (2, 1)

    grant.raw_value = "1"
    grant.save(update_fields=["raw_value"])
    following = NOW + timedelta(days=7)
    reserve(context(install, "stt", following), start(), following)
    following_week = UsageWeek.objects.exclude(pk=original.pk).get(org=org)
    assert following_week.notes_carried_debt == 1
    apply_note_delivery_credit(extra.reservation_id, uuid4(), NOW + timedelta(days=age))

    original.refresh_from_db()
    following_week.refresh_from_db()
    assert original.notes_settled == 1
    assert following_week.notes_carried_debt == expected_debt


@pytest.mark.django_db(transaction=True)
def test_notes_publication_requires_outer_transaction_and_rolls_back_with_it():
    from django.db.transaction import TransactionManagementError

    org = church()
    install = device(licence(org))
    decision = reserve_note(install)
    with pytest.raises(TransactionManagementError):
        settle_notes_success(decision.reservation_id, NOW)
    with transaction.atomic():
        settle_notes_success(decision.reservation_id, NOW)
        assert quota(org, "notes").settled == 1
        transaction.set_rollback(True)
    assert quota(org, "notes").settled == 0
    assert quota(org, "notes").held == 1


def test_notes_ledger_never_opens_outbound_transport(monkeypatch):
    import socket

    org = church()
    install = device(licence(org))

    def reject_socket(*args, **kwargs):
        pytest.fail("The notes ledger made an outbound transport call")

    monkeypatch.setattr(socket.socket, "connect", reject_socket)
    first = reserve_note(install)
    publish(first, NOW)
    apply_note_delivery_credit(first.reservation_id, uuid4(), NOW)
    second = reserve_note(install)
    release_notes_failure(second.reservation_id, NOW)


def test_late_credit_corrects_successor_debt_during_admission_hold():
    from datetime import UTC, datetime

    from selahcue_api.apps.catalogue.models import PlanGrant
    from selahcue_api.apps.catalogue.org_plans import effective_plan
    from selahcue_api.apps.usage.services import _open_week
    from test_effective_org_plan import NOTES_KEY

    org = church("Pacific/Kiritimati")
    install = device(licence(org))
    publish(reserve_note(install), NOW)
    grant = PlanGrant.objects.get(plan__is_fallback=True, dimension__key=NOTES_KEY)
    grant.raw_value = "2"
    grant.save(update_fields=["raw_value"])
    extra = reserve_note(install, NOW + timedelta(minutes=1))
    publish(extra, NOW + timedelta(minutes=1))
    grant.raw_value = "1"
    grant.save(update_fields=["raw_value"])

    org.timezone = "Etc/GMT+12"
    org.save(update_fields=["timezone"])
    gap = datetime(2026, 11, 16, 0, tzinfo=UTC)
    with transaction.atomic():
        locked_org = type(org).objects.select_for_update(no_key=True).get(pk=org.pk)
        type(install.license_key).objects.select_for_update().get(pk=install.license_key_id)
        successor = _open_week(locked_org, effective_plan(org, gap), gap)
    assert successor.notes_carried_debt == 1
    assert quota(org, "notes", gap).remaining == 0

    apply_note_delivery_credit(extra.reservation_id, uuid4(), gap)
    successor.refresh_from_db()
    assert successor.notes_carried_debt == 0
    assert quota(org, "notes", gap).remaining == 0
    assert quota(org, "notes", successor.admissions_start_at).remaining == 1
