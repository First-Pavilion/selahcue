from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from django.db import connection, connections

from test_pilot_registration_service import ack, payload, pilot_policy
from selahcue_api.apps.pilot_downloads.models import PilotRegistrationRecord, PilotSheetDestination
from selahcue_api.apps.pilot_downloads.services import PilotRegistrationError, confirm_registration, reserve_registration


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="Real row-lock proof requires PostgreSQL; SQLite is not evidence for this race"),
]


def race(operations):
    gate = threading.Barrier(len(operations))

    def run(operation):
        connections.close_all()
        try:
            gate.wait(timeout=10)
            try:
                return operation()
            except PilotRegistrationError as error:
                return error.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(run, operations))


def test_same_uuid_concurrent_retries_reserve_one_row(pilot_policy):
    data = payload()
    results = race([lambda: reserve_registration(data) for _ in range(6)])
    assert all(isinstance(result, dict) for result in results)
    assert len({result["sheet_write"]["range"] for result in results}) == 1
    assert PilotRegistrationRecord.objects.count() == 1
    assert PilotSheetDestination.objects.get().next_row == 3


def test_distinct_identities_cannot_collide_or_overrun_capacity(pilot_policy):
    results = race([lambda: reserve_registration(payload()) for _ in range(6)])
    success = [result for result in results if isinstance(result, dict)]
    assert len(success) == 3
    assert len({result["sheet_write"]["range"] for result in success}) == 3
    assert results.count("sheet_capacity_exhausted") == 3
    assert PilotRegistrationRecord.objects.count() == 3


def test_conflicting_identity_race_keeps_winners_original_binding(pilot_policy):
    data = payload()
    other = dict(data, email="different@example.invalid")
    results = race([lambda: reserve_registration(data), lambda: reserve_registration(other)])
    assert len([result for result in results if isinstance(result, dict)]) == 1
    assert results.count("identity_conflict") == 1
    assert PilotRegistrationRecord.objects.count() == 1


def test_parallel_matching_confirmations_share_first_expiry(pilot_policy):
    reserved = reserve_registration(payload())
    results = race([lambda: confirm_registration(ack(reserved)) for _ in range(6)])
    assert all(isinstance(result, dict) and result["state"] == "confirmed" for result in results)
    assert len({result["expires_at"] for result in results}) == 1
    assert PilotRegistrationRecord.objects.count() == 1
