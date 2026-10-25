"""Migration equivalence: dropping `CustomerOrg.device_limit` changes nothing any licence grants
(86ak5mn0m).

The ticket's verification expectation: "The migration needs an equivalence test over existing
rows, not just a successful `migrate`." A `migrate` that exits 0 proves the column went. It says
nothing about whether some licence quietly lost or gained seats because the org column was
standing in for the key's, which is exactly what this test is for.

HOW IT WORKS (the first `MigrationExecutor` test in this repo, so the method is spelled out)
------------------------------------------------------------------------------------------
1.  Migrate the database BACK to the state just before `selahcue_accounts` 0004. Rows are then
    seeded through the HISTORICAL models of that state, because the current `CustomerOrg` model
    has no `device_limit` and could not insert into a table that still has the NOT NULL column.
2.  Take a snapshot of every key THROUGH THE REAL SERVICES — the refresh response, the signed
    manifest's `instances_*`, the admin console's reading, and an activation PROBE. The services
    read only the licence-key table, which this migration does not touch, so they run unchanged
    on the old schema. The probe attempts a new activation inside a transaction that is rolled
    back, so "does this key admit one more device?" is observed without changing the data.
3.  Migrate FORWARD to the new migration and take the same snapshot.
4.  Assert the snapshots are identical, and that the key table is byte-for-byte unchanged.

The scenario table is the one the architect listed: an org value equal to, higher than and lower
than its key's (including the self-signup shape, org 1 with a staff key of 3); an org with no
keys; an org already holding two overlapping keys (grandfathered); every licence status incl.
SUSPENDED with a prior status and ACTIVATED past its expiry; keys at their limit and below it.

`transaction=True` because schema changes cannot run inside the per-test transaction on SQLite.
The `restore_schema` fixture puts the database back at the latest migration afterwards, so the
transactional tests that run after this one see the schema they expect.
"""

from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from selahcue_api.apps.accounts.models import CustomerOrg
from selahcue_api.apps.devices.services import (
    ActivateDeviceData,
    activate_device,
    refresh_license,
)
from selahcue_api.apps.entitlements.services import build_entitlement_manifest
from selahcue_api.apps.entitlements.signing import load_signing_key, verify_envelope
from selahcue_api.apps.license_keys import services as license_services
from selahcue_api.apps.license_keys.models import AppLicenseKey, LicenseKeyStatus
from selahcue_api.graphql.admin_schema import customer_to_type, license_key_to_type
from selahcue_api.graphql.errors import SafeAPIError

pytestmark = pytest.mark.django_db(transaction=True)

ACCOUNTS = "selahcue_accounts"
BEFORE = (ACCOUNTS, "0003_credentialtoken_customersession")
AFTER = (ACCOUNTS, "0004_remove_customerorg_device_limit")

TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode("ascii")


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return MigrationExecutor(connection)  # a fresh loader that sees the new applied state


def _targets_with(accounts_node):
    """Every app at its latest migration, except `selahcue_accounts` pinned to `accounts_node`."""
    graph = MigrationExecutor(connection).loader.graph
    return [node for node in graph.leaf_nodes() if node[0] != ACCOUNTS] + [accounts_node]


def _latest():
    return MigrationExecutor(connection).loader.graph.leaf_nodes()


@pytest.fixture(autouse=True)
def _environment(settings):
    cache.clear()
    settings.ENTITLEMENT_SIGNING_KEY = TEST_SEED_B64
    settings.SELAHCUE_THROTTLE_ACTIVATION = (1000, 60)
    # A FAST PASSWORD HASHER FOR THIS FILE ONLY. Seeding hashes every enrollment key and every
    # activation (seed or probe) verifies one, and PBKDF2 at ~250 ms apiece made these four
    # tests about 80% of the time the 86ak5mn0m change added to the suite. The hasher is not
    # what is under test: it only has to be a hasher that `make_password` and `check_password`
    # agree on, and the equivalence assertions below are unchanged. Django clears its hasher
    # cache when this setting changes, and `check_password` identifies a stored hash by its
    # prefix, so a key hashed here verifies here.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def restore_schema():
    yield
    _migrate(_latest())


# --- Scenario table ---------------------------------------------------------------------------
#
# name -> (org device_limit, key device_limit, devices to activate, final status, prior status,
#          window: "valid" | "past")
SCENARIOS = {
    "org-equal-key-at-limit": (3, 3, 3, LicenseKeyStatus.ACTIVATED, "", "valid"),
    "org-higher-key-below-limit": (9, 2, 1, LicenseKeyStatus.ACTIVATED, "", "valid"),
    "org-lower-key-below-limit": (1, 4, 2, LicenseKeyStatus.ACTIVATED, "", "valid"),
    "org-lower-key-at-limit": (1, 2, 2, LicenseKeyStatus.ACTIVATED, "", "valid"),
    "self-signup-shape-org-1-staff-key-3": (1, 3, 0, LicenseKeyStatus.ISSUED, "", "valid"),
    "expiring": (5, 3, 1, LicenseKeyStatus.EXPIRING, "", "valid"),
    "expired": (5, 3, 1, LicenseKeyStatus.EXPIRED, "", "valid"),
    "suspended-from-activated": (
        5, 3, 2, LicenseKeyStatus.SUSPENDED, LicenseKeyStatus.ACTIVATED, "valid",
    ),
    "suspended-from-expiring": (
        5, 3, 1, LicenseKeyStatus.SUSPENDED, LicenseKeyStatus.EXPIRING, "valid",
    ),
    "revoked": (5, 3, 1, LicenseKeyStatus.REVOKED, "", "valid"),
    "archived": (5, 3, 1, LicenseKeyStatus.ARCHIVED, "", "valid"),
    "converted": (5, 3, 1, LicenseKeyStatus.CONVERTED, "", "valid"),
    "activated-but-past-its-expiry": (5, 3, 3, LicenseKeyStatus.ACTIVATED, "", "past"),
}

assert {s for _, _, _, s, _, _ in SCENARIOS.values()} == set(LicenseKeyStatus), (
    "a licence status was added and no scenario covers it; the equivalence claim would be "
    "silent about that status"
)


class _Seeded:
    """What the seeding left behind, keyed by scenario name."""

    def __init__(self):
        self.keys = {}  # name -> (pk, full_key, first device token or None)
        self.no_key_org_pk = None
        self.grandfathered = {}  # "a"/"b" -> (pk, full_key)


def _historical_key(KeyModel, org, *, tag, full_key, status, limit, starts_at, expires_at, prior=""):
    return KeyModel.objects.create(
        customer=org,
        key_type="TRIAL",
        status=status,
        prior_status=prior,
        key_prefix=full_key[:12],
        key_suffix=full_key[-4:],
        masked_key=f"{full_key[:12]}...{full_key[-4:]}",
        secret_hash=make_password(full_key),
        secret_fingerprint=license_services._fingerprint(full_key),
        starts_at=starts_at,
        expires_at=expires_at,
        timezone="Africa/Lagos",
        feature_scope="CHURCH",
        seat_limit=5,
        device_limit=limit,
        territory="NG",
        generated_by_actor_id="staff_ops_1",
        generated_reason="Seeded for the migration equivalence test.",
        idempotency_key=f"migration-key-{tag}",
    )


def _full_key(tag):
    body = "".join(c for c in tag.upper() if c.isalnum())[:20].ljust(20, "X")
    return f"SC-TRIAL-{body[:4]}-{body[4:8]}-{body[8:12]}-{body[12:16]}-{body[16:20]}"


def _seed(old_apps):
    Org = old_apps.get_model(ACCOUNTS, "CustomerOrg")
    Key = old_apps.get_model("selahcue_license_keys", "AppLicenseKey")
    now = timezone.now().replace(microsecond=0)
    seeded = _Seeded()

    def make_org(tag, org_limit):
        return Org.objects.create(
            name=f"Migration Church {tag}",
            slug=f"migration-church-{tag}"[:200],
            primary_contact_email=f"ops+{tag}@migration.example"[:200],
            country="NG",
            timezone="Africa/Lagos",
            plan="TRIAL",
            seat_limit=5,
            device_limit=org_limit,
            created_by_actor_id="staff_ops_1",
            idempotency_key=f"migration-org-{tag}",
        )

    for name, (org_limit, key_limit, devices, final, prior, window) in SCENARIOS.items():
        org = make_org(name, org_limit)
        full_key = _full_key(name)
        key = _historical_key(
            Key, org, tag=name, full_key=full_key, status=LicenseKeyStatus.ACTIVATED,
            limit=key_limit, starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
        )
        first_token = None
        for index in range(devices):
            result = activate_device(
                ActivateDeviceData(
                    idempotency_key=f"seed-{name}-{index}"[:100],
                    presented_key=full_key,
                    device_fingerprint=f"seed-{name}-{index}"[:100],
                    platform="macos",
                )
            )
            first_token = first_token or result.full_token
        # Move the key to its scenario state AFTER activating, through the historical manager
        # (a queryset update), exactly as the existing tests drive these states.
        fields = {"status": final, "prior_status": prior}
        if window == "past":
            fields.update(starts_at=now - timedelta(days=60), expires_at=now - timedelta(days=1))
        Key.objects.filter(pk=key.pk).update(**fields)
        seeded.keys[name] = (key.pk, full_key, first_token)

    # An org with NO keys at all.
    seeded.no_key_org_pk = make_org("no-keys", 7).pk

    # An org that already holds two OVERLAPPING keys (it predates the one-key rule). Each key
    # keeps enforcing its own limit; the org column was never part of either.
    org = make_org("grandfathered", 2)
    for label, limit in (("a", 2), ("b", 3)):
        tag = f"grandfathered-{label}"
        full_key = _full_key(tag)
        key = _historical_key(
            Key, org, tag=tag, full_key=full_key, status=LicenseKeyStatus.ACTIVATED,
            limit=limit, starts_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
        )
        for index in range(limit if label == "a" else 1):
            activate_device(
                ActivateDeviceData(
                    idempotency_key=f"seed-{tag}-{index}",
                    presented_key=full_key,
                    device_fingerprint=f"seed-{tag}-{index}",
                    platform="macos",
                )
            )
        seeded.grandfathered[label] = (key.pk, full_key, None)
    return seeded


# --- Observations, taken through the real services ----------------------------------------------


def _observe(call):
    """A service outcome as a comparable value: the result, or the error code it refused with."""
    try:
        return ("ok", call())
    except SafeAPIError as error:
        return ("err", error.extensions["code"])


def _probe(full_key, tag):
    """Would this key admit ONE MORE device right now? Observed inside a transaction that is
    rolled back, so asking changes nothing and the before/after snapshots stay comparable."""
    outcome = None
    with transaction.atomic():
        outcome = _observe(
            lambda: activate_device(
                ActivateDeviceData(
                    idempotency_key=f"probe-{tag}",
                    presented_key=full_key,
                    device_fingerprint=f"probe-{tag}",
                    platform="macos",
                )
            ).created
        )
        transaction.set_rollback(True)
    # A probe whose own request is malformed answers VALIDATION_FAILED both before and after the
    # migration, so the equality it feeds would compare two identical errors and prove nothing.
    # That is exactly what happened when the grandfathered probes' idempotency keys were one
    # character short of the minimum (`validate_idempotency_key`). Refuse it here, once, for
    # every probe in this file.
    assert outcome != ("err", "VALIDATION_FAILED"), (
        f"the probe for {tag!r} was rejected as malformed, so it observes nothing about the key"
    )
    return outcome


def _manifest_instances(token):
    def read():
        envelope = build_entitlement_manifest(token).envelope
        payload = verify_envelope(envelope, public_key=load_signing_key(TEST_SEED_B64).public_key())
        return (
            payload["instances_used"],
            payload["instances_limit"],
            payload["license_status"],
            payload["license_valid_now"],
        )

    return _observe(read)


def _refresh_instances(token):
    def read():
        result = refresh_license(token)
        return (
            result.license_status,
            result.license_valid_now,
            result.instances_used,
            result.instances_limit,
        )

    return _observe(read)


def _snapshot_key(pk, full_key, token, tag):
    key = AppLicenseKey.objects.get(pk=pk)
    return {
        "device_limit": key.device_limit,
        "status": key.status,
        "prior_status": key.prior_status,
        "starts_at": key.starts_at,
        "expires_at": key.expires_at,
        "admin_reads": license_key_to_type(key).device_limit,
        "refresh": _refresh_instances(token) if token else None,
        "manifest": _manifest_instances(token) if token else None,
        "admits_one_more": _probe(full_key, tag),
    }


def _snapshot(seeded):
    snapshot = {name: _snapshot_key(pk, fk, tok, name) for name, (pk, fk, tok) in seeded.keys.items()}
    for label, (pk, fk, tok) in seeded.grandfathered.items():
        snapshot[f"grandfathered-{label}"] = _snapshot_key(pk, fk, tok, f"gf-{label}-probe")
    return snapshot


def _key_table():
    return list(AppLicenseKey.objects.order_by("pk").values())


def _org_table_columns():
    with connection.cursor() as cursor:
        return {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, "selahcue_accounts_customerorg"
            )
        }


# --- The tests -----------------------------------------------------------------------------------


def test_the_migration_is_a_single_forward_remove_field():
    executor = MigrationExecutor(connection)
    migration = executor.loader.get_migration(*AFTER)

    operations = [type(op).__name__ for op in migration.operations]
    assert operations == ["RemoveField"], operations
    assert migration.operations[0].model_name == "customerorg"
    assert migration.operations[0].name == "device_limit"
    assert migration.dependencies == [BEFORE], (
        "the migration should depend only on the accounts migration before it; any other "
        f"dependency means it does more than drop one column: {migration.dependencies}"
    )


def test_every_key_grants_exactly_what_it_did_before(restore_schema):
    old = _migrate(_targets_with(BEFORE))
    old_apps = old.loader.project_state(_targets_with(BEFORE)).apps
    # POSITIVE CONTROL: the "before" state really is the old schema, with the column present.
    assert "device_limit" in _org_table_columns(), (
        "the database was not migrated back, so this test would compare the new schema with itself"
    )

    seeded = _seed(old_apps)
    before_snapshot = _snapshot(seeded)
    before_keys = _key_table()
    assert len(before_keys) == len(SCENARIOS) + 2, "premise: every seeded key is in the table"
    # NON-VACUITY, spelled out for the pair that was once vacuous: the grandfathered org's two
    # keys give DIFFERENT, real answers (a is full, b has room), so equal snapshots across the
    # migration mean something.
    assert before_snapshot["grandfathered-a"]["admits_one_more"] == ("err", "POLICY_DENIED")
    assert before_snapshot["grandfathered-b"]["admits_one_more"] == ("ok", True)

    _migrate(_targets_with(AFTER))
    assert "device_limit" not in _org_table_columns(), "the column was not dropped"

    after_snapshot = _snapshot(seeded)
    after_keys = _key_table()

    assert after_keys == before_keys, "the migration changed a licence-key row"
    assert after_snapshot.keys() == before_snapshot.keys()
    for name in before_snapshot:
        assert after_snapshot[name] == before_snapshot[name], (
            f"{name}: what this key grants changed across the migration\n"
            f"before: {before_snapshot[name]}\nafter:  {after_snapshot[name]}"
        )


def test_the_scenarios_really_differ_so_equality_is_not_vacuous():
    """The comparison above would pass for a snapshot function that returns the same thing for
    every key. This shows the scenarios produce distinct observations — at least one key that
    admits another device, one that does not, and one that errors — on the old schema."""
    old = _migrate(_targets_with(BEFORE))
    try:
        seeded = _seed(old.loader.project_state(_targets_with(BEFORE)).apps)
        snapshot = _snapshot(seeded)
    finally:
        _migrate(_latest())

    probes = {tuple(s["admits_one_more"]) for s in snapshot.values()}
    assert ("ok", True) in probes, "no scenario admits another device"
    assert any(p[0] == "err" for p in probes), "no scenario refuses another device"
    limits = {s["device_limit"] for s in snapshot.values()}
    assert len(limits) >= 3, f"scenarios do not exercise different limits: {limits}"
    refreshes = [s["refresh"] for s in snapshot.values() if s["refresh"] is not None]
    assert refreshes and any(r[0] == "ok" for r in refreshes), "no refresh succeeded"
    # The key at its limit is refused and the one below is admitted — the two are not equal.
    assert snapshot["org-equal-key-at-limit"]["admits_one_more"] != (
        snapshot["org-higher-key-below-limit"]["admits_one_more"]
    )


def test_an_org_with_no_keys_survives_the_migration(restore_schema):
    old = _migrate(_targets_with(BEFORE))
    seeded = _seed(old.loader.project_state(_targets_with(BEFORE)).apps)
    _migrate(_targets_with(AFTER))

    org = CustomerOrg.objects.get(pk=seeded.no_key_org_pk)
    assert org.name == "Migration Church no-keys"
    assert not org.license_keys.exists()
    assert customer_to_type(org).name == org.name


def test_the_grandfathered_org_keeps_both_keys_each_with_its_own_limit(restore_schema):
    old = _migrate(_targets_with(BEFORE))
    seeded = _seed(old.loader.project_state(_targets_with(BEFORE)).apps)
    _migrate(_targets_with(AFTER))

    (pk_a, full_a, _), (pk_b, full_b, _) = seeded.grandfathered["a"], seeded.grandfathered["b"]
    key_a, key_b = AppLicenseKey.objects.get(pk=pk_a), AppLicenseKey.objects.get(pk=pk_b)
    assert key_a.customer_id == key_b.customer_id
    assert (key_a.device_limit, key_b.device_limit) == (2, 3)
    assert (key_a.status, key_b.status) == (LicenseKeyStatus.ACTIVATED,) * 2
    # a is full (2 of 2): refused. b has room (1 of 3): admitted. Each enforces its OWN limit.
    assert _probe(full_a, "post-a-probe") == ("err", "POLICY_DENIED")
    assert _probe(full_b, "post-b-probe") == ("ok", True)
