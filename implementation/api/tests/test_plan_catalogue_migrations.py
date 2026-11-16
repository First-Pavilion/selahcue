"""Real forward migration and recovery in separate task-owned SQLite databases.

The data migration is intentionally irreversible: constants cannot recover old references.
These subprocesses never reverse or modify pytest's shared database or a deployment.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.django_db

API = Path(__file__).resolve().parents[1]
CHILD = r"""
import json, os, shutil
from datetime import timedelta
from pathlib import Path
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.exceptions import IrreversibleError
from django.utils import timezone

app = "selahcue_catalogue"
executor = MigrationExecutor(connection)
targets = [n for n in executor.loader.graph.leaf_nodes() if n[0] != app] + [(app, "0006_price_and_rank_schema")]
executor.migrate(targets)
registry = executor.loader.project_state(targets).apps
Plan = registry.get_model(app, "Plan")
Alias = registry.get_model(app, "PlanScopeAlias")
Assignment = registry.get_model(app, "LicensePlanAssignment")
Key = registry.get_model("selahcue_license_keys", "AppLicenseKey")
Org = registry.get_model("selahcue_accounts", "CustomerOrg")
Revision = registry.get_model(app, "CatalogueRevision")
Price = registry.get_model(app, "PlanPrice")
Audit = registry.get_model("selahcue_audit", "AuditEvent")
old_revision = Revision.objects.get(pk=1).revision
free_id = Plan.objects.get(code="FREE").pk
refs = []
for index, code in enumerate(("LEGACY", "PRO", "PLATINUM", "FREE")):
    plan = Plan.objects.get(code=code)
    org = Org.objects.create(name="Migration "+code, slug="migration-"+code.lower(),
        primary_contact_email="migration@example.test", country="NG", timezone="UTC", plan="TRIAL",
        created_by_actor_id="migration-fixture", idempotency_key="migration-org-"+code)
    now = timezone.now()
    key = Key.objects.create(customer=org, key_type="TRIAL", status="ACTIVATED", key_prefix="TEST",key_suffix=code[:4],
        masked_key="TEST-MIGRATION", secret_hash="hash", secret_fingerprint="migration-"+code,
        starts_at=now, expires_at=now+timedelta(days=30), timezone="UTC", feature_scope="MIGRATE-"+code,
        seat_limit=5, device_limit=10+index, territory="NG", generated_by_actor_id="migration-fixture",
        generated_reason="Keep old key fields unchanged.", idempotency_key="migration-key-"+code)
    alias = Alias.objects.create(feature_scope=key.feature_scope, plan=plan)
    assignment = Assignment.objects.create(license_key=key, plan=plan, assigned_by_actor_id="old-operator",
        reason="Original explicit assignment.", idempotency_key="old-assign-"+code)
    refs.append((code, key.pk, alias.pk, assignment.pk))
keys_before = list(Key.objects.order_by("pk").values())
mode = os.environ["MIGRATION_PROBE_MODE"]
if mode == "custom":
    Plan.objects.create(code="CUSTOM", display_name="Custom data must not be guessed", rank=100,
        changed_by_actor_id="custom-operator", reason="Unexpected catalogue configuration.")
if mode == "dimension":
    registry.get_model(app,"GrantDimension").objects.filter(key="screen_outputs").update(is_active=False)
if mode == "history":
    Price.objects.create(plan_id=free_id, currency="USD", interval="YEAR", amount_minor=7,
        effective_from=timezone.now()+timedelta(days=1), changed_by_actor_id="pricing-fixture", reason="Keep configured history intact.")
connection.close()
database = Path(connection.settings_dict["NAME"])
backup = database.with_suffix(".backup")
shutil.copy2(database, backup)
try:
    MigrationExecutor(connection).migrate([(app, "0008_enforce_plan_rank")])
except RuntimeError as error:
    if mode not in {"custom", "history", "dimension"}: raise
    assert "Unexpected" in str(error) or "price history" in str(error)
    assert Revision.objects.get(pk=1).revision == old_revision
    assert Plan.objects.get(is_fallback=True).code == "LEGACY"
    assert not registry.get_model(app,"GrantDimension").objects.filter(key="sermon_notes_per_week").exists()
    for code, key_id, alias_id, assignment_id in refs:
        assert Alias.objects.get(pk=alias_id).plan.code == code
        assert Assignment.objects.get(pk=assignment_id).plan.code == code
    assert list(Key.objects.order_by("pk").values()) == keys_before
    if mode == "history":
        assert Price.objects.get().amount_minor == 7
        try:
            MigrationExecutor(connection).migrate([(app, "0005_plan_accountability_constraints")])
        except IrreversibleError:
            assert Price.objects.get().amount_minor == 7
        else: raise AssertionError("schema rollback must not erase configured price history")
    print(json.dumps({"mode":mode,"unsafe_forward_refused_atomically":True}))
else:
    assert mode == "forward"
    assert set(Plan.objects.values_list("code",flat=True)) == {"FREE","CORE","PRO"}
    assert list(Plan.objects.order_by("rank").values_list("rank",flat=True)) == [1,2,3]
    assert Revision.objects.get(pk=1).revision == old_revision+1
    for code,key_id,alias_id,assignment_id in refs:
        assert Alias.objects.get(pk=alias_id).plan_id == free_id
        assignment = Assignment.objects.get(pk=assignment_id)
        assert assignment.plan_id == free_id
        if code == "FREE": assert assignment.assigned_by_actor_id == "old-operator"
        else: assert assignment.assigned_by_actor_id == "migration:17tnw2az0gd" and assignment.reason
    assert list(Key.objects.order_by("pk").values()) == keys_before
    events = Audit.objects.filter(action="catalogue.reference_repointed")
    assert events.count() == 6
    assert all(e.actor_kind=="service" and e.actor_id=="migration:17tnw2az0gd" and e.reason for e in events)
    assert not Price.objects.exists()
    Price.objects.create(plan_id=free_id, currency="USD", interval="YEAR", amount_minor=7,
        effective_from=timezone.now()+timedelta(days=1), changed_by_actor_id="pricing-fixture", reason="Protect historical versions on rollback.")
    try:
        MigrationExecutor(connection).migrate([(app, "0006_price_and_rank_schema")])
    except IrreversibleError:
        assert Price.objects.get().amount_minor == 7
    else: raise AssertionError("destructive reverse must require backup recovery")
    connection.close()
    shutil.copy2(backup,database)
    assert set(Plan.objects.values_list("code",flat=True)) == {"FREE","PRO","PLATINUM","LEGACY"}
    assert list(Key.objects.order_by("pk").values()) == keys_before
    for code,key_id,alias_id,assignment_id in refs:
        assert Alias.objects.get(pk=alias_id).plan.code == code
        assert Assignment.objects.get(pk=assignment_id).plan.code == code
    print(json.dumps({"mode":mode,"forward_refs_and_key_preservation":True,"reverse_refused_history_preserved":True,"backup_restore_verified":True}))
connection.close()
"""


@pytest.mark.parametrize("mode", ["forward", "custom", "history", "dimension"])
def test_actual_forward_and_backup_recovery_contract(tmp_path, mode):
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="selahcue_api.settings",
               SQL_ENGINE="django.db.backends.sqlite3", SQL_DATABASE=str(tmp_path/"migration.sqlite3"), MIGRATION_PROBE_MODE=mode)
    for key in ("CACHE_URL","CELERY_BROKER_URL","SQL_HOST","SQL_PORT","SQL_USER","SQL_PASSWORD"):
        env.pop(key,None)
    run = subprocess.run([sys.executable,"-c",CHILD],cwd=str(API),env=env,capture_output=True,text=True,timeout=120)
    assert run.returncode==0, run.stdout+run.stderr
    receipt=json.loads(run.stdout.strip().splitlines()[-1])
    assert receipt["mode"]==mode
    assert any(v is True for v in receipt.values())
