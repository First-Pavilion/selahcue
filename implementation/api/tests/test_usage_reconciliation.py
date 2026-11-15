from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from selahcue_api.apps.usage.readiness import read_stt_readiness

from provider_helpers import DEEPGRAM, cold_provider_cache, identity, provider_mounts
from test_effective_org_plan import church, context, device, licence
from test_provider_observations import (
    NOW, begin_scan, clock, complete, dg_data, page_claim, parse_dg, request, task_for, usage_runtime,
)
from test_provider_reservation_binding import active_mapping
from test_usage_weeks import DIGEST, start
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.usage.contracts import UTCInterval
from selahcue_api.apps.usage.models import (
    SttOrgCoverage, UsageReservation, UsageWeek, UsageWeekProjection,
)
from selahcue_api.apps.usage.observation_contracts import RetentionKind
from selahcue_api.apps.usage.observations import ingest_observations
from selahcue_api.apps.usage.reconciliation import reconcile_org, settlement_floor
from selahcue_api.apps.usage.retention import prune_usage_batch
from selahcue_api.apps.usage.services import reserve, reserve_notes_job, settle_notes_success

MONDAY = datetime(2026, 11, 9, tzinfo=UTC)

@pytest.mark.django_db
def test_empty_database_refuses_stt_with_one_read_of_persisted_evidence():
    now = datetime(2026, 11, 15, 12, tzinfo=UTC)
    with CaptureQueriesContext(connection) as statements:
        readiness = read_stt_readiness(org_id=1, mapping_id=UUID(int=1), at=now)

    assert len(statements) == 1
    assert readiness.status == "not_initialized"
    assert readiness.checked_at == now
    assert readiness.observed_through is None
    assert readiness.valid_until is None
    assert readiness.publication_revision is None



def observed(scan, rows, at):
    interval = UTCInterval(scan.requested_start, scan.requested_end)
    work = task_for(scan, at)
    ingest_observations(parse_dg(dg_data(rows), interval=interval), scan.pk, claim=page_claim(work, at))
    complete(scan, DEEPGRAM, at)


def set_issued(row, at, *, minted=None):
    row.state, row.issued_at, row.last_minted_at = "ISSUED", at, minted
    row.save(update_fields=("state", "issued_at", "last_minted_at"))


def reserve_stt(install, mapping_id, at):
    return UsageReservation.objects.get(pk=reserve(
        replace(context(install, "stt", at), provider_mapping_id=mapping_id), start(), at,
    ).reservation_id)


@pytest.mark.django_db
def test_initial_empty_observation_allows_current_readiness_until_original_expiry(usage_runtime, clock, provider_mounts):
    org = church()
    mapping = active_mapping(org)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), org=org, mapping=mapping.mapping_id)
    observed(scan, [], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    assert result.blocked_reason is None
    assert result.observed_through == NOW
    assert SttOrgCoverage.objects.filter(publication_id=org.pk).count() == 1
    provider_mounts("web", capable=True)
    initialized = initialize_provider_runtime(entrypoint="wsgi")
    assert not initialized.usage_credentials
    with CaptureQueriesContext(connection) as statements:
        readiness = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW)
    assert len(statements) == 1
    assert readiness.status == "current_observed"
    assert readiness.valid_until == NOW + timedelta(seconds=300)
    expired = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=readiness.valid_until)
    assert (expired.status, expired.blocked_reason) == ("stale", "coverage_stale")


@pytest.mark.django_db
def test_provisional_zero_at_floor_then_late_actuals_never_reopen_terminal_rows(usage_runtime, clock):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="mapped-late"))
    at = NOW - timedelta(minutes=30)
    issued = reserve_stt(install, mapping.mapping_id, at)
    set_issued(issued, at, minted=at + timedelta(seconds=30))
    released = reserve_stt(install, mapping.mapping_id, at)
    released.state = "RELEASED"
    released.save(update_fields=("state",))
    floor = settlement_floor(issued)
    assert floor == at + timedelta(seconds=1260)
    usage_runtime()
    clock.value = floor - timedelta(microseconds=1)
    before = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, floor - timedelta(seconds=1)), start=clock())
    observed(before, [], clock())
    assert reconcile_org(org.pk, clock(), clock=clock).settled_reservations == ()
    clock.value = floor
    exact = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, floor), start=clock())
    observed(exact, [], clock())
    assert reconcile_org(org.pk, clock(), clock=clock).settled_reservations == (issued.pk,)

    clock.value = NOW
    late = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), start=clock())
    observed(late, [
        request("late-one", key="mapped-late", duration=0.1, created=at + timedelta(seconds=1)),
        request("late-two", key="mapped-late", duration=0.2, created=at + timedelta(seconds=2)),
    ], NOW)
    assert reconcile_org(org.pk, NOW, clock=clock).settled_reservations == ()
    issued.refresh_from_db()
    released.refresh_from_db()
    assert (issued.state, released.state) == ("SETTLED", "RELEASED")
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 1


@pytest.mark.django_db
def test_open_mapped_record_holds_an_issued_slice_without_blocking_readiness(usage_runtime, clock):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="mapped-incomplete"))
    admitted = NOW - timedelta(minutes=30)
    issued = reserve_stt(install, mapping.mapping_id, admitted)
    set_issued(issued, admitted)
    assert settlement_floor(issued) == admitted + timedelta(seconds=1200)
    usage_runtime()
    initial = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW), org=org, mapping=mapping.mapping_id)
    observed(initial, [request("open", key="mapped-incomplete", completed=False, duration=None)], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    assert result.blocked_reason is None
    assert result.settled_reservations == ()
    issued.refresh_from_db()
    assert issued.state == "ISSUED"
    ready = read_stt_readiness(org_id=org.pk, mapping_id=mapping.mapping_id, at=NOW)
    assert ready.status == "current_observed"


@pytest.mark.django_db
def test_westward_accounting_placement_and_current_debt_leave_notes_unchanged(usage_runtime, clock):
    west = "Etc/GMT+12"
    prior_end = datetime(2026, 11, 15, 10, tzinfo=UTC)
    org = church("Pacific/Honolulu")
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="mapped-west"))
    prior = reserve_stt(install, mapping.mapping_id, prior_end - timedelta(hours=1)).week
    # Materialize the contract's frozen rollover example independently of today.
    prior.ends_at = prior_end
    prior.save(update_fields=("ends_at",))
    note = reserve_notes_job(context(install, "notes", prior_end - timedelta(hours=1)),
                            UUID(int=82), DIGEST, prior_end - timedelta(hours=1))
    settle_notes_success(note.reservation_id, prior_end - timedelta(minutes=59))
    org.timezone = west
    org.save(update_fields=("timezone",))
    usage_runtime()
    clock.value = datetime(2026, 11, 16, 13, tzinfo=UTC)
    source = begin_scan(
        DEEPGRAM, interval=UTCInterval(prior.starts_at, clock()), start=clock(),
        org=org, mapping=mapping.mapping_id,
    )
    observed(source, [
        request("prior-overrun", key="mapped-west", duration=3000, created=prior_end - timedelta(seconds=1)),
        request("at-accounting-start", key="mapped-west", duration=1, created=prior_end),
        request("before-admissions", key="mapped-west", duration=2, created=datetime(2026, 11, 16, tzinfo=UTC)),
    ], clock())
    result = reconcile_org(org.pk, clock(), clock=clock)
    assert result.blocked_reason is None
    prior.refresh_from_db()
    successor = UsageWeek.objects.get(org=org, starts_at=prior_end)
    assert successor.admissions_start_at == datetime(2026, 11, 16, 12, tzinfo=UTC)
    assert successor.ends_at == datetime(2026, 11, 23, 12, tzinfo=UTC)
    assert (prior.stt_seconds_settled, successor.stt_seconds_settled, successor.stt_seconds_carried_debt) == (3000, 3, 1200)
    assert (prior.notes_settled, successor.notes_settled, successor.notes_carried_debt) == (1, 0, 0)
    assert UsageWeekProjection.objects.get(week=successor).selected_timezone == west


@pytest.mark.django_db
def test_retention_strict_horizon_respects_terminal_reservation_and_chain(usage_runtime, clock, provider_mounts):
    org = church()
    install = device(licence(org))
    mapping = active_mapping(org)
    rows = [reserve_stt(install, mapping.mapping_id, NOW - timedelta(minutes=10)) for _ in range(3)]
    cutoff = NOW - timedelta(weeks=104)
    for item, created in zip(rows, (cutoff - timedelta(microseconds=1), cutoff, cutoff - timedelta(days=1)), strict=True):
        UsageReservation.objects.filter(pk=item.pk).update(state="RELEASED", created_at=created)
    UsageReservation.objects.filter(pk=rows[1].pk).update(renews=rows[2])
    provider_mounts("maintenance", capable=True)
    initialize_provider_runtime(entrypoint="celery_worker")
    removed = prune_usage_batch(RetentionKind.TERMINAL_RESERVATION, clock=clock)
    assert (removed.scanned, removed.deleted, removed.deferred) == (2, 1, 1)
    assert set(UsageReservation.objects.values_list("pk", flat=True)) == {rows[1].pk, rows[2].pk}


@pytest.mark.django_db
def test_g13_public_batch_cannot_create_provider_facts_or_dirty_work(client):
    from selahcue_api.apps.usage.models import ProviderUsageRecord, UsageOrgState, UsageWork

    response = client.post(
        "/v1/usage-events:batch",
        data={"events": [{"type": "stream_completed", "duration_seconds": 1200, "request_id": "client"}]},
        content_type="application/json",
    )
    assert response.status_code == 501
    assert not ProviderUsageRecord.objects.exists()
    assert not UsageOrgState.objects.exists()
    assert not UsageWork.objects.exists()


@pytest.mark.django_db
def test_late_retired_key_facts_correct_the_original_church_without_a_replacement(usage_runtime, clock):
    from test_provider_reservation_binding import retire
    from selahcue_api.apps.usage.models import ProviderUsageRecord

    org = church()
    install = device(licence(org))
    mapping = active_mapping(org, identity(key="retired-credential"))
    row = reserve_stt(install, mapping.mapping_id, NOW - timedelta(minutes=20))
    row.state = "RELEASED"
    row.save(update_fields=("state",))
    retire(mapping)
    usage_runtime()
    scan = begin_scan(DEEPGRAM, interval=UTCInterval(MONDAY, NOW))
    observed(scan, [request("retired-key", key="retired-credential", duration=3)], NOW)
    result = reconcile_org(org.pk, NOW, clock=clock)
    assert result.blocked_reason == "SCOPE_MISSING"
    assert UsageWeek.objects.get(org=org).stt_seconds_settled == 3
    assert ProviderUsageRecord.objects.get().mapping_id == mapping.mapping_id
    row.refresh_from_db()
    assert row.state == "RELEASED"
