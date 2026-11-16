from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from functools import partial
from threading import Barrier, Event
from time import monotonic_ns
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

from provider_helpers import audit, cold_provider_cache, keyring, provider_mounts  # noqa: F401
from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.devices import services as devices
from selahcue_api.apps.devices.models import DeviceToken
from selahcue_api.apps.providers import sessions
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.contracts import (
    DefiniteFailure, EphemeralGrant, Granted, MintFailureCode, OutcomeUnknown,
    RegistryReason, SecretBytes, SessionRejected, SttMintState,
)
from selahcue_api.apps.providers.minting import MintReceipt
from selahcue_api.apps.providers.models import ProviderCredential, SttMintAttempt
from selahcue_api.apps.providers.registry import rotate_wrapping_key_batch
from selahcue_api.apps.throttling.cloud import CloudBudgetDecision
from selahcue_api.apps.throttling.services import BudgetOutcome
from selahcue_api.apps.usage.contracts import SessionRequest, SttReadiness
from selahcue_api.apps.usage.models import UsageReservation
from selahcue_api.apps.usage.services import remaining
from selahcue_api.platform.cloud_views import render_session_reply
from test_effective_org_plan import NOW, church, device, licence
from test_provider_provisioning import admitted_pool  # noqa: F401
from test_provider_reservation_binding import active_mapping, retire
from test_quota_read_only_sql import quota_read_only_query

pytestmark = pytest.mark.django_db(transaction=True)
ONGRANT = b"synthetic-not-a-provider-credential"


@pytest.fixture(autouse=True)
def real_postgresql():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL is required for Task 5 authority, locking and runtime integration")


def token_for(install):
    raw = f"synthetic-{uuid4().hex}"
    token = DeviceToken.objects.create(
        device=install, token_prefix="fixture", token_suffix="test", masked_token="fixture...test",
        token_hash="synthetic", token_fingerprint=devices._fingerprint(raw),
        issued_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=20),
    )
    return token, raw


@pytest.fixture
def live_org(provider_mounts):
    def setup(plan="FREE"):
        org = church()
        key = licence(org, plan)
        provider_mounts("provisioner")
        initialize_provider_runtime(entrypoint="operator")
        ready = active_mapping(org)
        provider_mounts("web", stt=True, provisioning=True, capable=True)
        initialize_provider_runtime(entrypoint="wsgi")
        token, raw = token_for(device(key))
        return org, key, token, raw, ready
    return setup


def command(previous=None):
    return SessionRequest(
        uuid4(), "start" if previous is None else "renew", previous,
        "new" if previous is None else "existing", False, "stt-direct-audio-v1", "stt-direct-v1",
    )


def current(*, org_id, mapping_id, at):
    return SttReadiness(org_id, mapping_id, "current_observed", at, at, at + timedelta(minutes=5), 1, None)


def granted(mapping_id, policy, *, dispatch):
    assert all(connections[alias].connection is None for alias in connections)
    assert mapping_id == dispatch.authorization.mapping_id
    assert policy.endpoint == "wss://api.deepgram.com/v1/listen"
    received = dispatch.request_started_at + timedelta(milliseconds=25)
    return MintReceipt(Granted(EphemeralGrant(
        SecretBytes(ONGRANT), policy.endpoint, received + timedelta(seconds=29), "deepgram",
    )), received)


def deps(mint=granted, clock=lambda: NOW, **kwargs):
    return replace(sessions.SessionDependencies(
        current, mint, lambda **_: CloudBudgetDecision(BudgetOutcome.ALLOWED, None),
        clock, monotonic_ns, render_session_reply,
    ), **kwargs)


def submit(token, request, dependencies):
    try:
        return sessions._issue_stt_session(token, request, dependencies)[0]
    except SessionRejected as error:
        return error.code.value


def audits(request):
    return AuditEvent.objects.filter(action="cloud.stt.session", request_id=str(request.idempotency_key))


def test_mint_attempt_reservation_is_protected_without_token_fk():
    assert SttMintAttempt._meta.get_field("reservation").one_to_one
    assert not SttMintAttempt._meta.get_field("trigger_token_pk").is_relation


def test_first_pending_uses_task4_and_records_one_denial(admitted_pool):
    org = church()
    created, _ = token_for(device(licence(org)))
    request = command()
    with pytest.raises(SessionRejected) as error:
        sessions._issue_stt_session(created, request, deps())
    assert error.value.code == "PROVIDER_PROVISIONING"
    assert error.value.retry_after_seconds == 5
    event = audits(request).get()
    assert event.after["reservation_id"] is None
    assert event.reason == "PROVIDER_PROVISIONING"
    assert not UsageReservation.objects.filter(org=org).exists()


def test_default_reader_blocks_ready_mapping_without_a_mint(live_org, monkeypatch):
    monkeypatch.setattr(sessions, "evaluate_cloud_budget", deps().rate_evaluator)
    org, _, token, _, _ = live_org()
    request = command()
    with pytest.raises(SessionRejected, match="RECONCILIATION_PENDING"):
        sessions.issue_stt_session(token, request, clock=lambda: NOW)
    assert not UsageReservation.objects.filter(org=org).exists()
    assert audits(request).get().reason == "RECONCILIATION_PENDING"


def test_four_free_slices_and_replay_of_same_socket_renewal(live_org):
    org, _, token, _, _ = live_org()
    first = command()
    result, reply = sessions._issue_stt_session(token, first, deps())
    assert result.decision.authorized_until == NOW + timedelta(seconds=300)
    assert reply["Cache-Control"] == "no-store"
    event = audits(first).get()
    assert event.after["delivery"] == "unconfirmed"
    assert event.after["remaining"] == 900
    assert event.actor_id == token.device.device_public_id
    assert set(event.after) == {
        "meter", "week_id", "limit", "remaining", "reservation_id", "request_receipt_id",
        "action", "replay", "decision_at", "delivery",
    }
    assert event.result == "SUCCESS"
    for offset in (250, 550, 850):
        request = command(result.decision.reservation_id)
        at = NOW + timedelta(seconds=offset)
        previous = result
        dependency = deps(clock=lambda: at)
        result, reply = sessions._issue_stt_session(token, request, dependency)
        assert b'"provider"' not in reply.content
        assert result.decision.authorized_from == previous.decision.authorized_until
        assert result.decision.authorized_until == NOW + timedelta(seconds=offset + 350)
        assert result.issued_at == at < result.decision.authorized_from
        assert submit(token, request, dependency) == "ALREADY_ISSUED"
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 1
    assert submit(
        token, command(result.decision.reservation_id), deps(clock=lambda: NOW + timedelta(seconds=1150)),
    ) == "QUOTA_EXHAUSTED"
    assert remaining(org, NOW + timedelta(seconds=1150))[0].remaining == 0


@pytest.mark.parametrize(("ending_state", "want"), [
    ("RELEASED", "RESERVATION_RELEASED"), ("SETTLED", "ALREADY_ISSUED"),
])
def test_terminal_reservation_still_receives_original_discard_and_audit(live_org, ending_state, want):
    org, _, token, _, _ = live_org()
    request = command()

    def mint(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        UsageReservation.objects.filter(pk=dispatch.authorization.reservation_id).update(state=ending_state)
        return receipt

    assert submit(token, request, deps(mint)) == want
    row = UsageReservation.objects.get(org=org)
    attempt = SttMintAttempt.objects.get(reservation=row)
    assert row.state == ending_state
    assert row.last_minted_at == attempt.known_mint_received_at == NOW + timedelta(milliseconds=25)
    assert attempt.state == SttMintState.DISCARDED
    assert attempt.audit_event_id == audits(request).get(result="DENIED", reason=want).pk
    assert submit(token, request, deps(mint)) == want
    assert audits(request).count() == 2
    assert audits(request).exclude(pk=attempt.audit_event_id).get().after["replay"] is True


@pytest.mark.parametrize("invalidated", ["token", "licence", "device", "org", "mapping"])
def test_final_phase_uses_original_authority(live_org, provider_mounts, invalidated):
    org, key, token, _, ready = live_org()
    request = command()

    def mint(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        if invalidated == "token":
            token_for(token.device)
            DeviceToken.objects.filter(pk=token.pk).update(status="REVOKED")
        elif invalidated == "licence":
            type(key).objects.filter(pk=key.pk).update(status="REVOKED")
        elif invalidated == "device":
            type(token.device).objects.filter(pk=token.device_id).update(status="REVOKED")
        elif invalidated == "org":
            type(org).objects.filter(pk=org.pk).update(status="SUSPENDED")
        else:
            ring = keyring(active="new", new=True)
            provider_mounts("provisioner", ring=ring)
            initialize_provider_runtime(entrypoint="operator")
            rotated = rotate_wrapping_key_batch(after=None, limit=100, now=NOW, audit=audit(RegistryReason.REWRAP))
            assert rotated.rewrapped == (ready.mapping_id,)
            provider_mounts("web", stt=True, provisioning=True, capable=True, ring=ring)
            initialize_provider_runtime(entrypoint="wsgi")
        return receipt

    expected = {
        "token": "UNAUTHENTICATED", "licence": "POLICY_DENIED", "device": "POLICY_DENIED",
        "org": "POLICY_DENIED", "mapping": "PROVIDER_UNAVAILABLE",
    }[invalidated]
    assert submit(token, request, deps(mint)) == expected
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == SttMintState.DISCARDED
    assert attempt.audit_event.reason == expected


def test_final_receipt_clock_keeps_provider_time_before_final_lock_delay(live_org):
    _, _, token, _, _ = live_org()
    now = NOW

    def delayed(*args, dispatch, **kwargs):
        nonlocal now
        evidence = granted(*args, dispatch=dispatch, **kwargs)
        now += timedelta(seconds=3)
        return evidence

    request = command()
    result, _ = sessions._issue_stt_session(token, request, deps(delayed, clock=lambda: now))
    attempt = SttMintAttempt.objects.get(reservation_id=result.decision.reservation_id)
    assert result.issued_at == NOW + timedelta(seconds=3)
    assert attempt.known_mint_received_at == attempt.reservation.last_minted_at == NOW + timedelta(milliseconds=25)


def test_render_failure_rolls_back_candidate_issuance_and_finalizes_once(live_org):
    _, _, token, _, _ = live_org()

    def fail(_):
        raise ValueError("synthetic exception that must not appear outside")

    request = command()
    assert submit(token, request, deps(render_reply=fail)) == "INTERNAL"
    attempt = SttMintAttempt.objects.get(audit_event=audits(request).get())
    assert attempt.state == SttMintState.DISCARDED
    assert attempt.reservation.state == "RESERVED"
    assert attempt.reservation.issued_at is None


@pytest.mark.parametrize(("outcome", "attempt_state", "reservation_state"), [
    (DefiniteFailure(MintFailureCode.REQUEST_REJECTED_LOCALLY), "DEFINITE_FAILURE", "RELEASED"),
    (OutcomeUnknown(MintFailureCode.TRANSPORT_TIMEOUT), "UNKNOWN", "RESERVED"),
])
def test_only_proven_no_send_releases_hold(live_org, outcome, attempt_state, reservation_state):
    _, _, token, _, _ = live_org()
    request = command()
    assert submit(token, request, deps(lambda *a, **kw: MintReceipt(outcome, None))) == "PROVIDER_UNAVAILABLE"
    attempt = SttMintAttempt.objects.get(audit_event=audits(request).get())
    assert (attempt.state, attempt.reservation.state) == (attempt_state, reservation_state)


def test_retired_historical_replay_never_provisions_replacement(live_org, provider_mounts, monkeypatch):
    org, _, token, _, ready = live_org()
    request = command()
    sessions._issue_stt_session(token, request, deps())
    provider_mounts("provisioner")
    initialize_provider_runtime(entrypoint="operator")
    retire(ready)
    provider_mounts("web", stt=True, provisioning=True, capable=True)
    initialize_provider_runtime(entrypoint="wsgi")

    def unexpected(*args, **kwargs):
        pytest.fail("A historical replay requested provisioning")

    monkeypatch.setattr(sessions, "ensure_provider_ready", unexpected)
    assert submit(token, request, deps()) == "ALREADY_ISSUED"
    assert ProviderCredential.objects.filter(org=org).count() == 1


def test_same_key_cross_device_replay_and_cross_org_previous(live_org):
    _, key, token, _, _ = live_org()
    other, _ = token_for(device(key))
    _, _, outsider, _, _ = live_org()
    first = command()
    result, _ = sessions._issue_stt_session(token, first, deps())
    assert submit(other, first, deps()) == "REQUEST_MISMATCH"
    assert submit(token, replace(first, consent_version="old"), deps()) == "POLICY_CHANGED"
    assert submit(other, command(result.decision.reservation_id), deps()) == "NOT_FOUND"
    assert submit(outsider, command(result.decision.reservation_id), deps()) == "NOT_FOUND"
    other_org = submit(outsider, first, deps())
    assert other_org.decision.reservation_id != result.decision.reservation_id


def test_duplicate_and_renewal_races(live_org):
    org, _, token, _, _ = live_org()
    first = command()
    passed_mint = Event()
    allow_mint = Event()
    dependencies = deps()

    def send(*args, **kwargs):
        passed_mint.set()
        assert allow_mint.wait(timeout=10)
        return granted(*args, **kwargs)

    def compete(request, dependencies):
        try:
            return submit(token, request, dependencies)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=8) as pool:
        original = pool.submit(compete, first, deps(send))
        try:
            assert passed_mint.wait(timeout=5)
            peers = [pool.submit(compete, first, dependencies) for _ in range(99)]
            assert all(future.result(timeout=16) == "SESSION_PENDING" for future in peers)
        finally:
            allow_mint.set()
        assert original.result(timeout=16).grant is not None
        result = original.result()
        barrier = Barrier(2, timeout=4)

        def renew():
            barrier.wait()
            return compete(command(result.decision.reservation_id), dependencies)

        renewals = [pool.submit(renew) for _ in range(2)]
        outcomes = [future.result(timeout=8) for future in renewals]

    assert outcomes.count("REQUEST_MISMATCH") == 1
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 1
    assert UsageReservation.objects.filter(org=org).count() == 2
    assert audits(first).count() == 100


def test_last_slice_race_different_devices(live_org):
    org, key, left, _, _ = live_org()
    right, _ = token_for(device(key))
    dependencies = deps()
    for _ in range(3):
        assert submit(left, command(), dependencies).grant is not None
    barrier = Barrier(2, timeout=5)

    def claim(token):
        try:
            barrier.wait()
            return submit(token, command(), dependencies)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim, token) for token in (left, right)]
        outcomes = [future.result(timeout=8) for future in futures]
    assert outcomes.count("QUOTA_EXHAUSTED") == 1
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 4


def test_week_geometry_resamples_after_wait(live_org):
    _, _, token, _, _ = live_org()
    # Monday midnight switches the candidate weekday geometry even with no
    # existing current week. Only the second full lock attempt may reserve.
    boundary = NOW.replace(hour=0) + timedelta(days=7)
    readings = iter([boundary - timedelta(microseconds=1), boundary])

    def clock():
        return next(readings, boundary)

    request = command()
    result, _ = sessions._issue_stt_session(token, request, deps(clock=clock))
    row = UsageReservation.objects.get(pk=result.decision.reservation_id)
    assert row.week.starts_at == boundary
    assert row.authorized_from == boundary


def test_migration_round_trip_and_protect_dispatch_identity(live_org):
    _, _, token, _, _ = live_org()
    request = command()
    result, _ = sessions._issue_stt_session(token, request, deps())
    attempt = SttMintAttempt.objects.get(reservation_id=result.decision.reservation_id)
    with pytest.raises(IntegrityError), transaction.atomic():
        SttMintAttempt.objects.filter(pk=attempt.pk).update(owner_nonce=uuid4())
    with pytest.raises(IntegrityError), transaction.atomic():
        SttMintAttempt.objects.filter(pk=attempt.pk).delete()
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    previous = ("selahcue_providers", "0002_provisioning_attempts")
    try:
        executor.migrate([previous])
        assert UsageReservation.objects.get(pk=result.decision.reservation_id).state == "ISSUED"
    finally:
        MigrationExecutor(connection).migrate(leaves)
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgname = 'stt_mint_attempt_guard'")
        assert cursor.fetchone()[0] == 1


@pytest.fixture
def real_budget(settings):
    import os

    url = os.getenv("TEST_STT_REDIS_URL")
    if url is None:
        pytest.skip("Set TEST_STT_REDIS_URL to a disposable Redis endpoint")
    from redis import Redis

    prefix = f"stt-grants-{uuid4().hex}"
    settings.CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": url, "KEY_PREFIX": prefix,
        "OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2},
    }}
    store = Redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    assert store.ping()
    yield store, prefix
    keys = list(store.scan_iter(match=f"{prefix}:*"))
    if keys:
        store.delete(*keys)
    store.close()


def wire(request):
    payload = {
        "idempotency_key": str(request.idempotency_key), "action": request.action,
        "socket": request.socket_mode, "consent_version": request.consent_version,
        "policy_version": request.policy_version,
    }
    if request.previous_reservation_id:
        payload["previous_reservation_id"] = str(request.previous_reservation_id)
    return payload


def test_http_direct_and_replay_spend_one_real_budget_each(client, live_org, real_budget, monkeypatch):
    from selahcue_api.apps.throttling.cloud import evaluate_cloud_budget

    store, prefix = real_budget
    org, _, token, raw, _ = live_org()
    got = []

    def count(**kwargs):
        assert all(not item.in_atomic_block for item in connections.all())
        got.append(kwargs)
        return evaluate_cloud_budget(**kwargs)

    monkeypatch.setattr(sessions, "evaluate_cloud_budget", count)
    monkeypatch.setattr(sessions, "read_stt_readiness", current)
    monkeypatch.setattr(sessions, "mint", granted)
    first = command()
    response = client.post("/v1/stt/session", wire(first), content_type="application/json",
                           headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200
    assert response.json()["provider"]["credential"] == ONGRANT.decode()
    with pytest.raises(SessionRejected, match="ALREADY_ISSUED"):
        sessions.issue_stt_session(devices.authenticate_device_token(raw), first)
    rotated, new_raw = token_for(token.device)
    DeviceToken.objects.filter(pk=token.pk).update(status="REVOKED")
    with pytest.raises(SessionRejected, match="POLICY_CHANGED"):
        sessions.issue_stt_session(
            devices.authenticate_device_token(new_raw), replace(command(), policy_version="old"),
        )
    assert got == [{"org_id": org.pk, "device_id": rotated.device_id, "kind": "admission"}] * 3
    counter = f"{prefix}:1:cloud:v1:{{org:{org.pk}}}:admission:device:{token.device_id}"
    assert store.get(counter) == b"3"
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 1
    assert audits(first).count() == 2


def test_retry_hint_is_preserved_with_no_device_audit(client, live_org, monkeypatch):
    org, _, _, raw, _ = live_org()
    command_to_deny = command()

    def deny(**_):
        return CloudBudgetDecision(BudgetOutcome.DENIED, 17)

    monkeypatch.setattr(sessions, "evaluate_cloud_budget", deny)
    response = client.post("/v1/stt/session", wire(command_to_deny), content_type="application/json",
                           headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 429 and response["Retry-After"] == "17"
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert not audits(command_to_deny).exists()
    assert not UsageReservation.objects.filter(org=org).exists()


def test_seventy_minute_pro_chain_uses_distinct_real_renewal_budget(live_org, real_budget):
    from selahcue_api.apps.throttling.cloud import evaluate_cloud_budget

    store, prefix = real_budget
    org, _, token, _, _ = live_org("PRO")
    at = NOW
    dependency = deps(clock=lambda: at, rate_evaluator=evaluate_cloud_budget)
    result, _ = sessions._issue_stt_session(token, command(), dependency)
    for index in range(14):
        at = result.decision.authorized_until - timedelta(seconds=20)
        request = command(result.decision.reservation_id)
        result, reply = sessions._issue_stt_session(token, request, dependency)
        assert b'"provider"' not in reply.content
        assert result.decision.authorized_from == NOW + timedelta(seconds=300 * (index + 1))
    assert result.decision.authorized_until == NOW + timedelta(seconds=4500)
    assert UsageReservation.objects.filter(org=org, state="ISSUED").count() == 15
    assert sum(UsageReservation.objects.filter(org=org).values_list("units", flat=True)) == 4500
    assert SttMintAttempt.objects.filter(reservation__org=org).count() == 1
    base = f"{prefix}:1:cloud:v1:{{org:{org.pk}}}:"
    assert store.get(base + f"admission:device:{token.device_id}") == b"1"
    assert store.get(base + f"renewal:device:{token.device_id}") == b"14"


def test_quota_is_read_only_for_authenticated_commercially_ineligible_token(client, live_org, real_budget):
    org, key, token, raw, _ = live_org()
    type(key).objects.filter(pk=key.pk).update(status="SUSPENDED", prior_status="ACTIVATED")
    # Inspect parameterized statements before debug capture interpolates values.
    rejection = []
    guard = partial(quota_read_only_query, rejection=rejection)
    with connection.execute_wrapper(guard), CaptureQueriesContext(connection) as queries:
        response = client.get("/v1/quota", headers={"Authorization": f"Bearer {raw}"})
    assert not rejection, rejection[0]
    assert response.status_code == 200 and response["Cache-Control"] == "no-store"
    assert not any("FOR UPDATE" in query["sql"].upper() for query in queries)
    assert response.json()["stt"]["remaining"] == 1200
    assert response.json()["stt"]["status"] == "not_initialized"
    assert response.json()["policies"] == {"notes": None, "stt": {
        "policy_version": "stt-direct-v1", "consent_version": "stt-direct-audio-v1",
    }}
    assert not UsageReservation.objects.filter(org=org).exists()
    assert not AuditEvent.objects.filter(actor_kind="DEVICE", actor_id=token.device.device_public_id).exists()


def test_original_owner_enriches_unknown_without_outcome_or_secret(live_org):
    org, _, token, _, _ = live_org()
    first = command()

    def abandoned(*args, dispatch, **kwargs):
        receipt = granted(*args, dispatch=dispatch, **kwargs)
        SttMintAttempt.objects.filter(pk=dispatch.authorization.attempt_id).update(
            state=SttMintState.UNKNOWN, finished_at=NOW, failure_code=MintFailureCode.TRANSPORT_TIMEOUT,
        )
        return receipt

    assert submit(token, first, deps(abandoned)) == "PROVIDER_UNAVAILABLE"
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == SttMintState.UNKNOWN and attempt.audit_event is None
    assert attempt.reservation.state == "RESERVED"
    assert attempt.known_mint_received_at == attempt.reservation.last_minted_at == NOW + timedelta(milliseconds=25)
    assert not audits(first).exists()
    assert submit(token, first, deps()) == "SESSION_PENDING"
    assert audits(first).get().reason == "SESSION_PENDING"


def test_unknown_commit_ack_refuses_secret_without_reversing_or_reauditing(live_org, monkeypatch):
    from django.db import OperationalError

    org, _, token, _, _ = live_org()
    first = command()
    real_commit = connection.commit
    next_commit_loses_ack = False

    def arm(*args, **kwargs):
        nonlocal next_commit_loses_ack
        evidence = granted(*args, **kwargs)
        next_commit_loses_ack = True
        return evidence

    def lost_ack():
        nonlocal next_commit_loses_ack
        real_commit()
        if next_commit_loses_ack:
            next_commit_loses_ack = False
            raise OperationalError("synthetic lost commit acknowledgement")

    monkeypatch.setattr(connection, "commit", lost_ack)
    assert submit(token, first, deps(arm)) == "INTERNAL"
    attempt = SttMintAttempt.objects.get(reservation__org=org)
    assert attempt.state == SttMintState.GRANTED and attempt.reservation.state == "ISSUED"
    assert audits(first).get().after["delivery"] == "unconfirmed"
    assert submit(token, first, deps()) == "ALREADY_ISSUED"
    assert audits(first).count() == 2


def test_expiry_candidates_across_weeks_and_meters_are_prelocked(live_org):
    from selahcue_api.apps.usage.services import reserve, reserve_notes_job
    from test_effective_org_plan import context
    from test_usage_weeks import DIGEST, start

    org, _, token, _, ready = live_org()
    install = token.device
    previous_week = NOW - timedelta(hours=11)
    historical = reserve_notes_job(context(install, "notes", previous_week), uuid4(), DIGEST, previous_week)
    current_reserved = reserve(context(install, "stt", NOW), start(), NOW)
    expiry = NOW + timedelta(seconds=1)
    UsageReservation.objects.filter(pk__in=(historical.reservation_id, current_reserved.reservation_id)).update(
        expires_at=expiry, state="RESERVED",
    )
    before = NOW
    after = NOW + timedelta(seconds=2)

    def clock():
        return readings.pop(0) if readings else after

    readings = [before, after]
    with CaptureQueriesContext(connection) as sql:
        from selahcue_api.apps.usage.live_stt import locked_stt_admission
        with locked_stt_admission(
            org_id=org.pk, license_id=install.license_key_id, device_id=install.pk, authenticated_token_id=token.pk,
            request=command(), clock=clock, mapping_id=ready.mapping_id,
        ) as ledger:
            assert ledger.now == after
    statements = [query["sql"] for query in sql]
    week = next(index for index, line in enumerate(statements) if 'usage_usageweek"' in line and "FOR UPDATE" in line)
    rows = next(index for index, line in enumerate(statements) if 'usage_usagereservation"' in line and "FOR UPDATE" in line)
    mapping = next(index for index, line in enumerate(statements) if 'providers_providercredential"' in line and "FOR UPDATE" in line)
    release = next(index for index, line in enumerate(statements) if line.startswith('UPDATE') and "RELEASED" in line)
    assert week < rows < mapping < release
    assert "starts_at" in statements[week].split("ORDER BY", 1)[1]
    assert "ORDER BY" in statements[rows]
    assert all(ident.hex in statements[rows] for ident in (historical.reservation_id, current_reserved.reservation_id))
    assert UsageReservation.objects.filter(org=org, state="RELEASED").count() == 2


@pytest.mark.parametrize("point", ["after_redis", "after_dispatch"])
def test_abrupt_process_death_keeps_only_durable_evidence(live_org, real_budget, settings, point):
    import json
    import os
    import selectors
    import signal
    import subprocess
    import sys

    store, prefix = real_budget
    org, _, token, raw, _ = live_org()
    request = command()
    path_vars = {
        key: getattr(settings, key)
        for key in ("SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE", "SELAHCUE_PROVIDER_KEYRING_FILE")
    }
    db = connection.settings_dict
    env = {
        "PATH": "/usr/bin:/bin", "DJANGO_SETTINGS_MODULE": "selahcue_api.settings",
        "SELAHCUE_PROVIDER_PROCESS_ROLE": "web", "SELAHCUE_CLOUD_STT_ENABLED": "1",
        "SELAHCUE_PROVIDER_PROVISIONING_ENABLED": "1",
        "SQL_ENGINE": "django.db.backends.postgresql", "SQL_DATABASE": db["NAME"],
        "SQL_HOST": db["HOST"], "SQL_PORT": db["PORT"], "SQL_USER": db["USER"], "SQL_PASSWORD": db["PASSWORD"],
        "CACHE_URL": settings.CACHES["default"]["LOCATION"],
        **path_vars,
    }
    code = """
import json, os, signal, sys
from dataclasses import replace
from datetime import timedelta
from uuid import UUID
import django
from django.conf import settings
from django.utils import timezone
args = json.loads(sys.stdin.readline())
settings.CACHES["default"]["KEY_PREFIX"] = args["cache_prefix"]
django.setup()
from selahcue_api.apps.devices.services import authenticate_device_token
from selahcue_api.apps.providers import sessions
from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.throttling.cloud import evaluate_cloud_budget
from selahcue_api.apps.usage.contracts import SessionRequest, SttReadiness
initialize_provider_runtime(entrypoint="wsgi")
def suspended():
    print("durable-checkpoint", flush=True)
    os.kill(os.getpid(), signal.SIGSTOP)
    raise RuntimeError("Test parent must kill this process")
def rate(**kwargs):
    decision = evaluate_cloud_budget(**kwargs)
    if decision.outcome.value != "ALLOWED":
        raise RuntimeError("Synthetic budget did not allow")
    if args["point"] == "after_redis":
        suspended()
    return decision
def ready(*, org_id, mapping_id, at):
    return SttReadiness(org_id, mapping_id, "current_observed", at, at, at + timedelta(minutes=5), 1, None)
def mint(*args, **kwargs):
    suspended()
request = SessionRequest(UUID(args["id"]), "start", None, "new", False, "stt-direct-audio-v1", "stt-direct-v1")
sessions._issue_stt_session(
    authenticate_device_token(args["synthetic_token"]), request,
    replace(sessions._defaults(timezone.now), rate_evaluator=rate, readiness_reader=ready, mint_callable=mint),
)
"""
    process = subprocess.Popen([sys.executable, "-c", code], env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        process.stdin.write((json.dumps({
            "id": str(request.idempotency_key), "synthetic_token": raw, "point": point, "cache_prefix": prefix,
        }) + "\n").encode())
        process.stdin.close()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(10), "Synthetic worker did not reach its crash checkpoint"
        assert process.stdout.readline() == b"durable-checkpoint\n"
        os.killpg(process.pid, signal.SIGKILL)
        assert process.wait(timeout=5) == -signal.SIGKILL
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    counter = f"{prefix}:1:cloud:v1:{{org:{org.pk}}}:admission:device:{token.device_id}"
    assert store.get(counter) == b"1"
    assert not audits(request).exists()
    rows = SttMintAttempt.objects.filter(reservation__org=org)
    if point == "after_dispatch":
        attempt = rows.get()
        assert attempt.state == SttMintState.DISPATCHED and attempt.audit_event_id is None
        assert attempt.reservation.state == "RESERVED"
    else:
        assert not rows.exists()
        assert not UsageReservation.objects.filter(org=org).exists()
    print(f"SIGKILL {point}: one Redis spend, attempts={rows.count()}, no synthesized DEVICE audit")


def test_launched_mint_releases_explicitly_open_alias_connection(live_org):
    _, _, token, _, _ = live_org()
    alias = "task5_auxiliary"
    connections.databases[alias] = dict(connection.settings_dict)
    try:
        alias_connection = connections[alias]
        # The alias is created after pytest's allowlist, and points only to
        # its already provisioned disposable test database.
        alias_connection.connect()
        with alias_connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
        assert alias_connection.connection is not None
        first = command()
        result, _ = sessions._issue_stt_session(token, first, deps())
        assert result.grant is not None
        assert alias_connection.connection is None
    finally:
        connections[alias].close()
        del connections[alias]
        del connections.databases[alias]


def test_original_token_revoked_while_admission_waits_for_its_lock(live_org):
    from queue import Queue
    from time import monotonic, sleep

    _, _, token, _, _ = live_org()
    first = command()
    worker_pid = Queue()

    def admission():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                worker_pid.put(cursor.fetchone()[0])
            return submit(token, first, deps())
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            DeviceToken.objects.select_for_update().get(pk=token.pk)
            worker = pool.submit(admission)
            pid = worker_pid.get(timeout=3)
            until = monotonic() + 1.5
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                assert monotonic() < until
                sleep(0.005)
            DeviceToken.objects.filter(pk=token.pk).update(status="REVOKED")
        assert worker.result(timeout=5) == "UNAUTHENTICATED"
    assert audits(first).get().reason == "UNAUTHENTICATED"
    assert not SttMintAttempt.objects.filter(reservation__idempotency_key=first.idempotency_key).exists()


def test_clock_failure_after_valid_mint_preserves_discard_and_no_delivery(live_org):
    from django.utils import timezone

    _, _, token, _, _ = live_org()
    first = command()
    invalid_clock = False

    def clock():
        at = timezone.now()
        return at.replace(tzinfo=None) if invalid_clock else at

    def receipt(*args, dispatch, **kwargs):
        nonlocal invalid_clock
        reply = granted(*args, dispatch=dispatch, **kwargs)
        invalid_clock = True
        return reply

    assert submit(token, first, deps(receipt, clock=clock)) == "PROVIDER_UNAVAILABLE"
    event = audits(first).get(result="DENIED")
    attempt = SttMintAttempt.objects.get(audit_event=event)
    assert attempt.state == SttMintState.DISCARDED
    assert attempt.reservation.state == "RESERVED"
    assert attempt.known_mint_received_at == attempt.reservation.last_minted_at
    assert event.after["delivery"] == "unconfirmed"


def test_reserved_note_crosses_expiry_during_real_reservation_lock_wait(live_org):
    from queue import Queue
    from time import monotonic, sleep

    from selahcue_api.apps.usage.live_stt import locked_stt_admission
    from selahcue_api.apps.usage.services import reserve_notes_job
    from test_effective_org_plan import context
    from test_usage_weeks import DIGEST

    org, _, token, _, ready = live_org()
    before = NOW
    expiry = NOW + timedelta(seconds=1)
    note = reserve_notes_job(context(token.device, "notes", NOW), uuid4(), DIGEST, NOW)
    UsageReservation.objects.filter(pk=note.reservation_id).update(expires_at=expiry)
    pid_queue = Queue()
    at = before

    def wait_for_prior_hold():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid_queue.put(cursor.fetchone()[0])
            with locked_stt_admission(
                org_id=org.pk, license_id=token.device.license_key_id, device_id=token.device_id,
                authenticated_token_id=token.pk, request=command(), clock=lambda: at,
                mapping_id=ready.mapping_id,
            ) as snapshot:
                return snapshot.now
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            UsageReservation.objects.select_for_update().get(pk=note.reservation_id)
            future = pool.submit(wait_for_prior_hold)
            pid = pid_queue.get(timeout=3)
            timeout = monotonic() + 1.5
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT cardinality(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                assert monotonic() < timeout
                sleep(0.005)
            at = expiry
        assert future.result(timeout=5) == expiry
    assert UsageReservation.objects.get(pk=note.reservation_id).state == "RELEASED"


@pytest.mark.parametrize("entry", ["http", "direct"])
@pytest.mark.parametrize("failure", ["naive", "exception"])
def test_provisioning_clock_failure_records_one_denial(
    client, admitted_pool, real_budget, monkeypatch, entry, failure,
):
    from django.utils import timezone

    from selahcue_api.apps.providers.models import ProviderProvisioningOutbox, ProvisioningDemand
    from selahcue_api.platform import cloud_views

    store, prefix = real_budget
    org = church()
    token, raw = token_for(device(licence(org)))
    first = command()
    at = timezone.now()
    samples = []
    outbox_count = ProviderProvisioningOutbox.objects.filter(pool=admitted_pool).count()

    def clock():
        assert connection.in_atomic_block
        samples.append(at)
        if len(samples) <= 2:
            return at
        assert len(samples) == 3, "Provisioning must not retry the authority clock"
        if failure == "naive":
            return at.replace(tzinfo=None)
        raise RuntimeError("synthetic clock detail")

    def unexpected_mint(*args, **kwargs):
        pytest.fail("A failing provisioning clock must not start a mint")

    monkeypatch.setattr(sessions, "mint", unexpected_mint)
    if entry == "http":
        monkeypatch.setattr(cloud_views, "_defaults", lambda _: sessions._defaults(clock))
        response = client.post("/v1/stt/session", wire(first), content_type="application/json",
                               headers={"Authorization": f"Bearer {raw}"})
        assert response.status_code == 503
        assert response.json() == {
            "error": {"code": "PROVIDER_UNAVAILABLE", "message": "The cloud provider is unavailable."},
            "surface": "desktop", "operation": "stt_session",
        }
        assert response["Cache-Control"] == "no-store" and "Retry-After" not in response
    else:
        with pytest.raises(SessionRejected, match="^PROVIDER_UNAVAILABLE$") as denied:
            sessions.issue_stt_session(devices.authenticate_device_token(raw), first, clock=clock)
        assert denied.value.retry_after_seconds is None

    assert len(samples) == 3
    base = f"{prefix}:1:cloud:v1:{{org:{org.pk}}}:admission:"
    assert store.mget(base + "org", base + f"device:{token.device_id}") == [b"1", b"1"]
    assert not UsageReservation.objects.filter(org=org).exists()
    assert not SttMintAttempt.objects.filter(reservation__org=org).exists()
    assert not ProviderCredential.objects.filter(org=org).exists()
    assert not ProvisioningDemand.objects.filter(org=org).exists()
    assert ProviderProvisioningOutbox.objects.filter(pool=admitted_pool).count() == outbox_count
    event = audits(first).get()
    assert (event.actor_kind, event.actor_id) == ("device", token.device.device_public_id)
    assert (event.result, event.reason) == ("DENIED", "PROVIDER_UNAVAILABLE")
    assert event.after["delivery"] == "unconfirmed"
    assert event.after["reservation_id"] is None and event.after["replay"] is False
