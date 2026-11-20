"""Behavioral regressions for the current-main admin catalogue integration."""

import base64
import json
from datetime import timedelta
from queue import SimpleQueue
from threading import Event, Thread

import pytest
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.signals import post_save
from django.test import Client
from django.utils import timezone
from licensing_test_support import issue_key, seat_plan, seed_org

from selahcue_api.apps.audit.models import AuditEvent
from selahcue_api.apps.catalogue.admin import (
    read_admin_catalogue,
    rename_admin_plan,
    set_admin_grant,
    set_admin_price,
)
from selahcue_api.apps.catalogue.models import CatalogueAdminMutation, OrgPlanGrant, Plan, PlanGrant, PlanPrice
from selahcue_api.apps.catalogue.org_plans import effective_plan
from selahcue_api.apps.catalogue.services import SetPlanGrantData, current_revision, set_plan_grant
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.apps.usage.services import remaining
from selahcue_api.graphql.context import ActorContext, ActorKind, StaffPermission
from selahcue_api.graphql.errors import SafeAPIError

pytestmark = pytest.mark.django_db

NOTES = "sermon_notes_per_week"
MINUTES = "cloud_transcript_minutes_per_week"
DEVICES = "device_instances"
MAX_NOTES = 2**63 - 1
MAX_MINUTES = MAX_NOTES // 60
MAX_DEVICES = 2**31 - 1

CATALOGUE_QUERY = """
    { adminPlanCatalogue { revision plans { code prices { amountMinor currency interval effectiveFrom } } } }
"""
MUTATIONS = {
    "grant": """
        mutation($input: AdminSetPlanGrantInput!) {
            adminSetPlanGrant(input: $input) { revision rawValue replayed }
        }
    """,
    "price": """
        mutation($input: AdminSetPlanPriceInput!) {
            adminSetPlanPrice(input: $input) { revision amountMinor replayed }
        }
    """,
    "rename": """
        mutation($input: AdminRenamePlanInput!) {
            adminRenamePlan(input: $input) { revision name replayed }
        }
    """,
}
PAYLOADS = {"grant": "adminSetPlanGrant", "price": "adminSetPlanPrice", "rename": "adminRenamePlan"}


@pytest.fixture(autouse=True)
def enabled_admin_catalogue(settings):
    settings.ENVIRONMENT = "dev"
    settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE = True
    settings.SELAHCUE_TRUST_ACTOR_HEADERS = True


@pytest.fixture
def browser(settings):
    client = Client(enforce_csrf_checks=True)
    bootstrap = client.get("/graphql/csrf")
    assert bootstrap.status_code == 200
    assert settings.CSRF_COOKIE_NAME in bootstrap.cookies
    return client, bootstrap["X-CSRFToken"]


@pytest.fixture
def plan():
    return seat_plan("ADMIN-REVIEW", 2, other_grants={NOTES: "2", MINUTES: "7", "screen_outputs": "2"})


def staff(permission=StaffPermission.MANAGE_PLAN_PRICING):
    return ActorContext(kind=ActorKind.STAFF, actor_id="admin-review", staff_permissions=frozenset({permission}))


def post_admin(
    browser, query, variables=None, *, actor_id="admin-review", kind="staff",
    permission="manage_plan_pricing", send_token=True,
):
    client, token = browser
    headers = {
        "HTTP_X_SELAHCUE_ACTOR_KIND": kind,
        "HTTP_X_SELAHCUE_ACTOR_ID": actor_id,
        "HTTP_X_SELAHCUE_STAFF_PERMISSIONS": permission,
    }
    if send_token:
        headers["HTTP_X_CSRFTOKEN"] = token
    return client.post(
        "/graphql/admin",
        data=json.dumps({"query": query, "variables": variables or {}}),
        content_type="application/json",
        **headers,
    )


def mutation_input(plan, **fields):
    return {
        "planCode": plan.code,
        "expectedRevision": current_revision(),
        "reason": "Approved catalogue review fixture",
        "idempotencyKey": "admin-review-mutation",
        **fields,
    }


def mutate(browser, operation, data, **auth):
    return post_admin(browser, MUTATIONS[operation], {"input": data}, **auth)


def payload(response, field):
    assert response.status_code == 200, response.content
    body = response.json()
    assert "errors" not in body, body
    return body["data"][field]


def error_extensions(response):
    assert response.status_code == 200, response.content
    body = response.json()
    assert len(body.get("errors", [])) == 1, body
    return body["errors"][0]["extensions"]


def set_management_grant(plan, dimension, raw_value):
    return set_plan_grant(
        staff(StaffPermission.GRANT_ENTITLEMENT),
        SetPlanGrantData(
            plan_code=plan.code, dimension_key=dimension, raw_value=raw_value,
            reason="Approved catalogue review fixture", idempotency_key="review-management-grant",
        ),
    )


def catalogue_state(plan):
    return {
        "plan": Plan.objects.values().get(pk=plan.pk),
        "grants": list(PlanGrant.objects.filter(plan=plan).order_by("pk").values()),
        "prices": list(PlanPrice.objects.filter(plan=plan).order_by("pk").values()),
        "revision": current_revision(),
        "audit_count": AuditEvent.objects.count(),
        "receipt_count": CatalogueAdminMutation.objects.count(),
    }


@pytest.mark.django_db(transaction=True)
def test_postgres_price_snapshot_cannot_pair_new_revision_with_old_price(plan):
    if connection.vendor != "postgresql":
        pytest.skip("Requires two real PostgreSQL connections in hosted API CI")

    write = {
        "plan_code": plan.code,
        "currency": "USD",
        "interval": "MONTH",
        "effective_from": None,
        "reason": "Approved immediate price",
    }
    initial = set_admin_price(
        staff(), **write, amount_minor=10,
        idempotency_key="first-review-price", expected_revision=current_revision(),
    )
    revision_lookup = Event()
    release_reader = Event()
    outcome = SimpleQueue()
    reader_pid = None

    def pause_revision_lookup(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith("SELECT") and "selahcue_catalogue_cataloguerevision" in sql:
            revision_lookup.set()
            assert release_reader.wait(timeout=25), "The writer did not release the catalogue reader"
        return execute(sql, params, many, context)

    def read():
        nonlocal reader_pid
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                reader_pid = cursor.fetchone()[0]
                cursor.execute("SET statement_timeout = '8s'")
            with connection.execute_wrapper(pause_revision_lookup):
                outcome.put(read_admin_catalogue(staff()))
        except Exception as error:
            outcome.put(error)
        finally:
            connections.close_all()

    reader = Thread(target=read, name="price-snapshot-reader", daemon=True)
    reader.start()
    try:
        assert revision_lookup.wait(timeout=10), "Reader did not reach the revision SELECT"
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            assert reader_pid != cursor.fetchone()[0]
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            updated = set_admin_price(
                staff(), **write, amount_minor=20,
                idempotency_key="second-review-price", expected_revision=initial["revision"],
            )
        assert updated["revision"] > initial["revision"]
        assert PlanPrice.objects.get(pk=updated["price_id"]).effective_from > (
            PlanPrice.objects.get(pk=initial["price_id"]).effective_from
        )
    finally:
        release_reader.set()
        reader.join(timeout=10)

    assert not reader.is_alive(), "Catalogue reader did not finish"
    result = outcome.get_nowait()
    if isinstance(result, Exception):
        raise result
    prices = next(row["prices"] for row in result["plans"] if row["code"] == plan.code)
    assert result["revision"] in (initial["revision"], updated["revision"])
    if result["revision"] == updated["revision"]:
        assert [price["amount_minor"] for price in prices] == ["20"]


@pytest.mark.parametrize(
    ("dimension", "raw_value"),
    [
        pytest.param(NOTES, "unlimited", id="notes-unlimited"),
        pytest.param(NOTES, str(MAX_NOTES + 1), id="notes-overflow"),
        pytest.param(MINUTES, "unlimited", id="minutes-unlimited"),
        pytest.param(MINUTES, str(MAX_MINUTES + 1), id="minutes-seconds-overflow"),
        pytest.param(DEVICES, "unlimited", id="devices-unlimited"),
        pytest.param(DEVICES, "0", id="devices-zero"),
        pytest.param(DEVICES, str(MAX_DEVICES + 1), id="devices-overflow"),
    ],
)
@pytest.mark.parametrize("entry", ["management", "http"])
def test_shared_grant_writer_refuses_values_its_consumers_cannot_enforce(browser, plan, entry, dimension, raw_value):
    before = catalogue_state(plan)
    if entry == "http":
        response = mutate(browser, "grant", mutation_input(plan, dimensionKey=dimension, rawValue=raw_value))
        assert error_extensions(response) == {"code": "VALIDATION_FAILED", "field": "rawValue"}
        assert catalogue_state(plan) == before
    else:
        with pytest.raises(SafeAPIError) as error:
            set_management_grant(plan, dimension, raw_value)
        assert error.value.extensions["code"] == "VALIDATION_FAILED"
        assert catalogue_state(plan) == before


def test_http_grant_rejects_normalized_value_wider_than_storage(browser, plan):
    before = catalogue_state(plan)
    response = mutate(browser, "grant", mutation_input(plan, dimensionKey=NOTES, rawValue=" " + "0" * 64 + "1 "))
    assert error_extensions(response) == {"code": "VALIDATION_FAILED", "field": "rawValue"}
    assert catalogue_state(plan) == before


def test_management_grant_rejects_normalized_value_wider_than_storage(plan):
    before = catalogue_state(plan)
    with pytest.raises(SafeAPIError) as error:
        set_management_grant(plan, NOTES, " " + "0" * 64 + "1 ")
    assert error.value.extensions["code"] == "VALIDATION_FAILED"
    assert catalogue_state(plan) == before


def test_http_grant_accepts_normalized_value_at_storage_width(browser, plan):
    raw_value = "0" * 63 + "1"
    response = mutate(browser, "grant", mutation_input(plan, dimensionKey=NOTES, rawValue=f" {raw_value} "))
    assert payload(response, PAYLOADS["grant"])["rawValue"] == raw_value
    assert PlanGrant.objects.get(plan=plan, dimension__key=NOTES).raw_value == raw_value


@pytest.mark.parametrize(
    ("operation", "fields", "action"),
    [
        pytest.param("price", {"currency": "USD", "interval": "MONTH", "amountMinor": "0"},
                     "catalogue.plan_price_added", id="price"),
        pytest.param("grant", {"dimensionKey": NOTES, "rawValue": "6"}, "catalogue.plan_grant_set", id="grant"),
        pytest.param("rename", {"name": "Updated staff label"}, "catalogue.plan_renamed", id="rename"),
    ],
)
def test_http_canonical_retry_key_correlates_audit_and_receipt(browser, plan, operation, fields, action):
    key = "r" * 128
    data = mutation_input(plan, idempotencyKey=f" {key}\t", **fields)
    initial = payload(mutate(browser, operation, data), PAYLOADS[operation])
    assert initial["replayed"] is False
    after = catalogue_state(plan)
    replay = payload(mutate(browser, operation, {**data, "idempotencyKey": key}), PAYLOADS[operation])
    assert replay == {**initial, "replayed": True}
    receipt = CatalogueAdminMutation.objects.get(actor_id="admin-review")
    event = AuditEvent.objects.get(actor_id="admin-review", action=action)
    assert receipt.idempotency_key == event.request_id == key
    assert event.target_id
    assert catalogue_state(plan) == after


@pytest.mark.parametrize(
    ("operation", "fields"),
    [
        pytest.param("rename", {"planCode": "ADMIN\x00REVIEW", "name": "Refused label"}, id="rename-code"),
        pytest.param("price", {"planCode": "ADMIN\x00REVIEW", "currency": "USD", "interval": "MONTH",
                              "amountMinor": "0"}, id="price-code"),
        pytest.param("grant", {"planCode": "ADMIN\x00REVIEW", "dimensionKey": NOTES,
                              "rawValue": "6"}, id="grant-code"),
        pytest.param("grant", {"dimensionKey": NOTES + "\x00", "rawValue": "6"}, id="grant-dimension"),
    ],
)
def test_http_control_characters_cannot_name_catalogue_rows(browser, plan, operation, fields):
    before = catalogue_state(plan)
    response = mutate(browser, operation, mutation_input(plan, **fields))
    assert error_extensions(response) == {"code": "NOT_FOUND"}
    assert catalogue_state(plan) == before


@pytest.mark.parametrize("denial", ["missing-csrf", "gate-off", "permission", "customer", "device"])
def test_http_catalogue_mutation_requires_csrf_staff_permission_and_gate(browser, plan, settings, denial):
    options = {}
    if denial == "missing-csrf":
        options["send_token"] = False
    elif denial == "gate-off":
        settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE = False
    elif denial == "permission":
        options["permission"] = "view_customers"
    else:
        options["kind"] = denial

    before = catalogue_state(plan)
    response = mutate(browser, "grant", mutation_input(plan, dimensionKey=NOTES, rawValue="6"), **options)
    if denial == "missing-csrf":
        assert response.status_code == 403
    else:
        assert error_extensions(response) == {"code": "PERMISSION_DENIED"}
    assert catalogue_state(plan) == before


@pytest.mark.parametrize("lost", ["permission", "feature", "environment"])
def test_http_gate_and_permission_are_rechecked_before_replay(browser, plan, settings, lost):
    data = mutation_input(plan, dimensionKey=NOTES, rawValue="6")
    initial = payload(mutate(browser, "grant", data), PAYLOADS["grant"])
    assert initial["rawValue"] == "6"
    assert initial["replayed"] is False
    assert payload(mutate(browser, "grant", data), PAYLOADS["grant"]) == {**initial, "replayed": True}
    after = catalogue_state(plan)

    options = {}
    if lost == "permission":
        options["permission"] = "view_customers"
    elif lost == "feature":
        settings.SELAHCUE_ENABLE_ADMIN_CATALOGUE = False
    else:
        settings.ENVIRONMENT = "staging"
    assert error_extensions(mutate(browser, "grant", data, **options)) == {"code": "PERMISSION_DENIED"}
    assert catalogue_state(plan) == after


def test_http_receipt_replay_is_scoped_to_original_staff_actor(browser, plan):
    data = mutation_input(plan, dimensionKey=NOTES, rawValue="6")
    initial = payload(mutate(browser, "grant", data), PAYLOADS["grant"])
    assert initial["replayed"] is False
    after = catalogue_state(plan)

    other = mutate(browser, "grant", data, actor_id="other-admin-review")
    assert other.status_code == 200, other.content
    assert other.json()["errors"] == [{
        "message": "The catalogue changed since you loaded it. Reload before editing.",
        "extensions": {"code": "CONFLICT"},
    }]
    assert catalogue_state(plan) == after


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("write", "fields", "target", "expected", "action"),
    [
        pytest.param(
            set_admin_price,
            {"currency": "USD", "interval": "MONTH", "amount_minor": 15, "effective_from": None},
            "prices", 15, "catalogue.plan_price_added", id="price",
        ),
        pytest.param(
            set_admin_grant, {"dimension_key": NOTES, "raw_value": "6"},
            "grants", "6", "catalogue.plan_grant_set", id="grant",
        ),
        pytest.param(
            rename_admin_plan, {"name": "New staff label"},
            "plan", "New staff label", "catalogue.plan_renamed", id="rename",
        ),
    ],
)
def test_audit_failure_rolls_back_catalogue_write_and_allows_same_key_retry(plan, write, fields, target, expected, action):
    key = "rollback-admin-review"
    data = {
        "plan_code": plan.code,
        "idempotency_key": key,
        "reason": "Approved transaction test",
        "expected_revision": current_revision(),
        **fields,
    }
    before = catalogue_state(plan)

    def read_target():
        if target == "prices":
            return PlanPrice.objects.get(plan=plan).amount_minor
        if target == "grants":
            return PlanGrant.objects.get(plan=plan, dimension__key=NOTES).raw_value
        return Plan.objects.get(pk=plan.pk).display_name

    class AuditWriteFailed(Exception):
        pass

    def fail_after_audit_insert(sender, instance, created, **kwargs):
        if instance.action == action:
            assert created
            assert AuditEvent.objects.filter(pk=instance.pk, request_id=key).exists()
            assert read_target() == expected
            assert current_revision() > before["revision"]
            raise AuditWriteFailed

    post_save.connect(fail_after_audit_insert, sender=AuditEvent, weak=False)
    try:
        with pytest.raises(AuditWriteFailed):
            write(staff(), **data)
    finally:
        post_save.disconnect(fail_after_audit_insert, sender=AuditEvent)

    assert catalogue_state(plan) == before
    retry = write(staff(), **data)
    assert retry["replayed"] is False
    assert retry["revision"] == current_revision() > before["revision"]
    assert read_target() == expected
    assert CatalogueAdminMutation.objects.get(idempotency_key=key).actor_id == "admin-review"
    assert AuditEvent.objects.get(request_id=key).action == action
    assert catalogue_state(plan)["audit_count"] == before["audit_count"] + 1
    assert CatalogueAdminMutation.objects.count() == before["receipt_count"] + 1


def test_http_zero_null_and_scheduled_prices_preserve_history(browser, plan, monkeypatch):
    now = timezone.now().replace(microsecond=0)
    future = now + timedelta(days=2)
    monkeypatch.setattr(timezone, "now", lambda: now)

    def add_price(key, amount, effective_from=None):
        data = mutation_input(
            plan, currency="USD", interval="MONTH", amountMinor=amount, idempotencyKey=key,
        )
        if effective_from is not None:
            data["effectiveFrom"] = effective_from.isoformat()
        result = payload(mutate(browser, "price", data), PAYLOADS["price"])
        assert result["amountMinor"] == amount
        assert result["replayed"] is False
        return result["revision"]

    def assert_current(amount, effective_from, revision):
        catalogue = payload(post_admin(browser, CATALOGUE_QUERY), "adminPlanCatalogue")
        assert catalogue["revision"] == revision
        row = next(candidate for candidate in catalogue["plans"] if candidate["code"] == plan.code)
        assert row["prices"] == [{
            "amountMinor": amount, "currency": "USD", "interval": "MONTH",
            "effectiveFrom": effective_from.isoformat(),
        }]

    zero_at = now
    revision = add_price("zero-review-price", "0")
    assert_current("0", zero_at, revision)
    scheduled_revision = add_price("future-null-price", None, future)
    assert_current("0", zero_at, scheduled_revision)

    now += timedelta(seconds=1)
    immediate_at = now
    revision = add_price("next-review-price", "25")
    assert_current("25", immediate_at, revision)
    now = future
    assert_current(None, future, revision)
    assert list(PlanPrice.objects.filter(plan=plan).order_by("effective_from").values_list(
        "effective_from", "amount_minor",
    )) == [(zero_at, 0), (immediate_at, 25), (future, None)]


@pytest.mark.parametrize(
    ("dimension", "value", "meter", "units"),
    [
        pytest.param(NOTES, "0", "notes", 0, id="notes-zero"),
        pytest.param(NOTES, str(MAX_NOTES), "notes", MAX_NOTES, id="notes-max"),
        pytest.param(MINUTES, "0", "stt", 0, id="minutes-zero"),
        pytest.param(MINUTES, str(MAX_MINUTES), "stt", MAX_MINUTES * 60, id="minutes-max"),
    ],
)
def test_weekly_grant_boundaries_reach_ledger(browser, plan, dimension, value, meter, units):
    org = seed_org("quota-edge")
    now = timezone.now()
    OrgPlanGrant.objects.create(
        org=org, plan=plan, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1),
        granted_by_actor_id="fixture-staff", reason="Approved organisation test grant",
    )
    response = mutate(browser, "grant", mutation_input(plan, dimensionKey=dimension, rawValue=value))
    assert payload(response, PAYLOADS["grant"])["rawValue"] == value
    assert PlanGrant.objects.get(plan=plan, dimension__key=dimension).raw_value == value
    assert effective_plan(org, now).plan_id == plan.pk
    snapshot = next(quota for quota in remaining(org, now) if quota.meter == meter)
    assert snapshot.limit == snapshot.remaining == units


@pytest.mark.parametrize("value", [1, MAX_DEVICES], ids=["first-seat", "largest-supported-copy"])
def test_device_grant_boundaries_are_copied_only_on_new_issuance(browser, plan, value):
    existing = issue_key(seed_org("existing-copy"), tag="existing-copy", plan_code=plan.code).license_key
    assert existing.device_limit == 2
    response = mutate(browser, "grant", mutation_input(plan, dimensionKey=DEVICES, rawValue=str(value)))
    assert payload(response, PAYLOADS["grant"])["rawValue"] == str(value)
    new = issue_key(seed_org("new-copy"), tag="new-copy", plan_code=plan.code).license_key
    new.refresh_from_db()
    existing.refresh_from_db()
    assert new.device_limit == value
    assert existing.device_limit == 2


def test_active_org_grant_changes_next_signed_manifest_and_weekly_ledger(browser, settings, plan):
    signing_seed = base64.b64encode(bytes(range(32))).decode()
    settings.ENTITLEMENT_SIGNING_KEY = signing_seed
    public_key = load_signing_key(signing_seed).public_key()
    org = seed_org("active-catalogue-grant")
    base = Plan.objects.get(is_fallback=True)
    issued = issue_key(org, tag="active-catalogue-grant", plan_code=base.code)
    response = browser[0].post(
        "/v1/activations",
        data=json.dumps({
            "idempotency_key": "active-catalogue-activation",
            "license_key": issued.full_key,
            "device_fingerprint": "active-catalogue-device",
            "platform": "macos",
        }),
        content_type="application/json",
        REMOTE_ADDR="192.0.2.42",
    )
    assert response.status_code == 200, response.content
    token = response.json()["activation_token"]
    now = timezone.now()
    OrgPlanGrant.objects.create(
        org=org, plan=plan, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1),
        granted_by_actor_id="fixture-staff", reason="Approved organisation test grant",
    )

    def signed_grants():
        return verify_envelope(build_entitlement_manifest(token).envelope, public_key=public_key)["grants"]

    def limits():
        return {quota.meter: quota.limit for quota in remaining(org, timezone.now())}

    assert effective_plan(org, now).source == "staff_grant"
    initial = signed_grants()
    assert (initial[NOTES], initial[MINUTES], initial["screen_outputs"]) == (2, 7, 2)
    assert limits() == {"notes": 2, "stt": 420}

    for key, value, suffix in [(NOTES, "6", "notes"), (MINUTES, "11", "minutes"), ("screen_outputs", "unlimited", "generic")]:
        data = mutation_input(plan, dimensionKey=key, rawValue=value, idempotencyKey=f"org-grant-review-{suffix}")
        response = mutate(browser, "grant", data)
        assert payload(response, PAYLOADS["grant"])["rawValue"] == value
        assert PlanGrant.objects.get(plan=plan, dimension__key=key).raw_value == value

    updated = signed_grants()
    assert (updated[NOTES], updated[MINUTES], updated["screen_outputs"]) == (6, 11, None)
    assert limits() == {"notes": 6, "stt": 660}


@pytest.mark.django_db(transaction=True)
def test_receipt_migration_preserves_an_existing_org_grant(plan):
    catalogue = "selahcue_catalogue"
    before = (catalogue, "0009_org_plan_grant")
    executor = MigrationExecutor(connection)
    frontier = executor.loader.graph.leaf_nodes()
    previous = [node for node in frontier if node[0] != catalogue] + [before]
    receipt_table = CatalogueAdminMutation._meta.db_table
    receipt_key = "schema-upgrade-receipt"

    # pytest creates the fresh database from the full graph before this test starts.
    # The catalogue frontier is whatever the newest catalogue migration is (later seed
    # migrations such as 0011 only add data), so assert a single leaf rather than a name.
    assert len([node for node in frontier if node[0] == catalogue]) == 1
    assert receipt_table in connection.introspection.table_names()
    org = seed_org("receipt-migration")
    now = timezone.now()
    fields = {
        "org_id": org.pk,
        "plan_id": plan.pk,
        "starts_at": now - timedelta(hours=1),
        "ends_at": now + timedelta(days=1),
        "ended_at": None,
        "granted_by_actor_id": "migration-fixture",
        "reason": "Existing historical catalogue grant",
    }
    try:
        executor.migrate(previous)
        assert receipt_table not in connection.introspection.table_names()
        historical_grants = executor.loader.project_state(previous).apps.get_model(catalogue, "OrgPlanGrant")
        existing = historical_grants.objects.create(**fields)

        MigrationExecutor(connection).migrate(frontier)
        assert OrgPlanGrant.objects.filter(pk=existing.pk).values(*fields).get() == fields
        assert effective_plan(org, now).plan_id == plan.pk
        result = set_admin_grant(
            staff(), plan_code=plan.code, dimension_key=NOTES, raw_value="8",
            expected_revision=current_revision(), reason="Approved after schema upgrade",
            idempotency_key=receipt_key,
        )
        assert result["replayed"] is False
        assert CatalogueAdminMutation.objects.get(idempotency_key=receipt_key).result["raw_value"] == "8"
    finally:
        MigrationExecutor(connection).migrate(frontier)
