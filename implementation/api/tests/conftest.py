"""Process-wide test fixtures.

**Deliberately narrow.** The shipped slices each build their own module-local seeding
helpers rather than sharing them, and that convention stands — nothing here seeds anything.
This file exists for one thing that module-local fixtures structurally cannot do.

(One deliberate exception to the convention, and it is not a fixture here either:
`licensing_test_support.py` holds the plan and licence seeding shared by the tests that need
"a licence with N seats" since a licence's device limit began to come from its plan
(86ak5mn0m). Its docstring says why; nothing else should join it without the same argument.)

`selahcue_api.apps.catalogue.cache.GRANT_CACHE` is a PROCESS global. It is not part of the
database, so `django_db`'s per-test rollback does not touch it, and its key (a plan primary
key) is stable across rollbacks — so an entry written by one test can be served to the next
one under a recycled id. Only the suites that happen to remember an autouse fixture were
protected; every other suite that calls `resolve_entitlement`, directly or through the
entitlement manifest, was not. None of them assert on grants today, which is exactly why a
stale map would have gone unnoticed rather than failed loudly.

A per-module fixture cannot fix that, because the suite that needs protecting is the one
whose author never thought about this cache.
"""

import pytest

from selahcue_api.apps.throttling import services as throttle_services
from selahcue_api.apps.throttling.circuit import CacheCircuit


_G1_REQUIRED_CONTROL_IDS = {
    "tests/test_native_account_controller_integration.py::test_required_g1_missing_binary_fails",
    "tests/test_native_account_controller_integration.py::"
    "test_required_g1_workflow_keeps_api_reachable_and_requires_same_source_artifact",
}
_G1_FAILURE_BODY_LIMIT = 65_536


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(items):
    result = yield
    # Promote only the G1 controls after pytest-django orders the suite. The
    # stable sort keeps every other selected item in its existing order.
    items.sort(key=lambda item: item.nodeid not in _G1_REQUIRED_CONTROL_IDS)
    return result


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    if (
        report.nodeid in _G1_REQUIRED_CONTROL_IDS
        and report.when == "call"
        and report.failed
        and call.excinfo is not None
    ):
        # The API job can time out before pytest's final summary. Emit the
        # observed failure now, with no locals, arguments or captured sections.
        body = str(call.excinfo.getrepr(style="short", showlocals=False, funcargs=False))
        print(f"\n--- G1 call failure for {report.nodeid} ---")
        print(body[:_G1_FAILURE_BODY_LIMIT], flush=True)
        if len(body) > _G1_FAILURE_BODY_LIMIT:
            print(f"[G1 failure trace truncated at {_G1_FAILURE_BODY_LIMIT} characters]", flush=True)
    return report


@pytest.fixture(autouse=True)
def _cold_catalogue_grant_cache():
    from selahcue_api.apps.catalogue.cache import GRANT_CACHE

    GRANT_CACHE.clear()
    yield
    GRANT_CACHE.clear()


# --- Migration-installed catalogue reference data, across a TransactionTestCase flush ----
#
# The second thing a module-local fixture structurally cannot do, and the same argument as
# above: the suite that needs protecting is the one whose author never thought about it.
#
# `pytest.mark.django_db(transaction=True)` gives up the per-test rollback and TRUNCATES
# every table on teardown. Rows installed by a DATA MIGRATION go with it, and nothing puts
# them back — `post_migrate` re-creates content types and permissions, never `RunPython`
# output. pytest-django runs all transactional tests LAST, so the damage is confined to
# that tail, but within it the first such test consumes the catalogue and every later one
# starts against an empty one.
#
# That only became load-bearing with DEC-014: issuing a licence now resolves a `Plan` row
# and REFUSES when it finds none, so a lifecycle test that merely wanted a licence to drive
# through its states fails on a missing plan — a failure about seeding, not about the
# lifecycle. Every catalogue test in this suite treats the migration seed as its fixture;
# this keeps that true for the transactional tail as well.
#
# Snapshot rather than re-seed: whatever the migrations produced is what comes back, with
# the original primary keys, so this cannot drift when the seed table changes and needs no
# second copy of it. `serialized_rollback=True` is Django's own answer to this and was
# measured first — it restores the whole database and collides with the content types
# `post_migrate` has already re-created (`UNIQUE constraint failed:
# django_content_type.app_label, django_content_type.model`).

# Insert order is FK order: grants reference both a plan and a dimension.
_CATALOGUE_REFERENCE_MODELS = (
    "CatalogueRevision",
    "GrantDimension",
    "Plan",
    "PlanGrant",
    "PlanScopeAlias",
)


def _catalogue_reference_models():
    from django.apps import apps as django_apps

    return [
        django_apps.get_model("selahcue_catalogue", name)
        for name in _CATALOGUE_REFERENCE_MODELS
    ]


def _catalogue_is_seeded():
    """Named lookup, not a position in the tuple above: reordering that tuple for FK reasons
    must not silently move this guard onto a different model, which would make the restore
    fire never or always."""
    from django.apps import apps as django_apps

    return django_apps.get_model("selahcue_catalogue", "Plan").objects.exists()


@pytest.fixture(scope="session", autouse=True)
def _catalogue_reference_snapshot(django_db_setup, django_db_blocker):
    """Serialise the migration-installed catalogue once, before any test can flush it.

    Session-scoped AND autouse so it is captured at session start. Requested lazily by the
    restore fixture instead, it would be captured after the first flush had already run and
    would faithfully snapshot an empty catalogue.
    """
    from django.core import serializers

    with django_db_blocker.unblock():
        rows = [row for model in _catalogue_reference_models() for row in model.objects.all()]
        return serializers.serialize("json", rows)


@pytest.fixture(autouse=True)
def _restore_catalogue_reference_data(request, _catalogue_reference_snapshot):
    """Put the catalogue back if a previous transactional test truncated it.

    Scoped to transactional tests: they are the only ones that can run after a flush, and
    the `exists()` guard makes it a no-op for the first of them, which still has the real
    thing.
    """
    marker = request.node.get_closest_marker("django_db")
    if marker is None or not marker.kwargs.get("transaction"):
        return

    if _catalogue_is_seeded():
        return

    from django.core import serializers
    from django.core.management.color import no_style
    from django.db import connection

    models = _catalogue_reference_models()
    for wrapped in serializers.deserialize("json", _catalogue_reference_snapshot):
        wrapped.save()

    # What `loaddata` does after restoring rows with explicit primary keys, and for the same
    # reason: on a sequence-backed engine an explicit-pk INSERT does not advance the
    # sequence, so a later `Plan.objects.create()` in the test could be handed a pk that is
    # already taken. It happens not to bite today only because Django flushes with
    # `reset_sequences=False`, which leaves the sequence ahead — an internal default, not a
    # contract. `sequence_reset_sql` returns nothing on SQLite, so this line does real work
    # only on Postgres, which is what CI runs.
    statements = connection.ops.sequence_reset_sql(no_style(), models)
    if statements:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)


@pytest.fixture(autouse=True)
def _cold_cache_circuit(monkeypatch):
    """Process circuit survives DB/cache rollback; isolate outage tests globally."""
    monkeypatch.setattr(throttle_services, "CACHE_CIRCUIT", CacheCircuit())
