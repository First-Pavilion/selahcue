"""Approved pre-launch catalogue; backup/restore is required for reference recovery.

Seed constants belong only here. Never edit0002 or infer commercial equivalence from
old tier names. No key seat count or signed historical dimension key is rewritten.
"""
from django.db.migrations.exceptions import IrreversibleError
from django.db import migrations
from django.db.models import F

ACTOR = "migration:17tnw2az0gd"
REASON = "Approved pre-launch weekly catalogue reseed; restore backup for previous references."
PENDING = "PENDING D7(a): restrictive placeholder until owner configures launch limits."
PLANS = [("FREE", "Free", 1, 10, 20, 1, "true"),
         ("CORE", "Core", 2, 20, 50, 5, "false"),
         ("PRO", "Pro", 3, 30, 80, 10, "false")]
WEEKLY = [("cloud_transcript_minutes_per_week", "Cloud transcript minutes per week", 40),
          ("sermon_notes_per_week", "Sermon note generations per week", 45)]


def seed(apps, schema_editor):
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    Grant = apps.get_model("selahcue_catalogue", "PlanGrant")
    Dimension = apps.get_model("selahcue_catalogue", "GrantDimension")
    Revision = apps.get_model("selahcue_catalogue", "CatalogueRevision")
    Price = apps.get_model("selahcue_catalogue", "PlanPrice")
    Audit = apps.get_model("selahcue_audit", "AuditEvent")
    Alias = apps.get_model("selahcue_catalogue", "PlanScopeAlias")
    Assignment = apps.get_model("selahcue_catalogue", "LicensePlanAssignment")
    if set(Plan.objects.values_list("code", flat=True)) != {"FREE", "PRO", "PLATINUM", "LEGACY"}:
        raise RuntimeError("Unexpected catalogue plan shape; review custom data and backup before reseeding.")
    if Price.objects.exists():
        raise RuntimeError("Existing price history must be preserved; review before catalogue reseed.")
    if Dimension.objects.filter(key__in=[key for key, _, _ in WEEKLY]).exists():
        raise RuntimeError("Weekly dimension already exists; inspect its wire meaning before reseeding.")
    expected = {"device_instances": "INTEGER", "screen_outputs": "INTEGER", "ndi_outputs": "INTEGER",
                "watermark": "BOOLEAN", "stt_minutes_per_period": "INTEGER"}
    if any(not Dimension.objects.filter(key=key, value_type=kind).exists() for key, kind in expected.items()):
        raise RuntimeError("Unexpected required dimension shape; review before catalogue reseed.")
    if any(not Dimension.objects.filter(key=key, is_active=True, publish_in_manifest=True).exists()
           for key in ("screen_outputs", "ndi_outputs", "watermark")):
        raise RuntimeError("Unexpected required dimension activation/publication; review before catalogue reseed.")
    old_ids = list(Plan.objects.filter(code__in=["PRO", "PLATINUM", "LEGACY"]).values_list("pk", flat=True))
    free = Plan.objects.get(code="FREE")
    # Preserve old row identity and assignment accountability in a migration-owned audit.
    # Old commercial names never silently acquire a newly configured paid plan's grants.
    for model, actor_field, target in ((Alias, None, "catalogue_scope_alias"),
                                        (Assignment, "assigned_by_actor_id", "catalogue_plan_assignment")):
        while True:
            batch = list(model.objects.filter(plan_id__in=old_ids).order_by("pk")[:500])
            if not batch:
                break
            for row in batch:
                before = {"plan_id": str(row.plan_id)}
                changes = {"plan_id": free.pk}
                if actor_field:
                    before.update({"actor_id": row.assigned_by_actor_id, "reason": row.reason,
                                   "idempotency_key": row.idempotency_key})
                    changes.update(assigned_by_actor_id=ACTOR, reason=REASON,
                                   idempotency_key="migration-17tnw2az0gd-%s" % row.pk)
                model.objects.filter(pk=row.pk).update(**changes)
                Audit.objects.create(actor_kind="service", actor_id=ACTOR, action="catalogue.reference_repointed",
                    target_type=target, target_id=str(row.pk), request_id="migration-17tnw2az0gd-%s-%s" % (target, row.pk),
                    reason=REASON, result="SUCCESS", source_surface="catalogue_migration",
                    before=before, after={"plan_id": str(free.pk)})
    Plan.objects.filter(is_fallback=True).update(is_fallback=False)
    Plan.objects.filter(code__in=["LEGACY", "PLATINUM"]).delete()
    Dimension.objects.filter(key="stt_minutes_per_period").update(is_active=False)
    Dimension.objects.filter(key="device_instances").update(is_active=True, publish_in_manifest=False)
    for key, label, order in WEEKLY:
        Dimension.objects.create(key=key, display_name=label, description="Weekly catalogue allowance; usage enforcement is separate.",
            value_type="INTEGER", default_raw_value="0", is_active=True, publish_in_manifest=True, sort_order=order)
    dimensions = {d.key: d for d in Dimension.objects.all()}
    for code, name, rank, order, minutes, notes, watermark in PLANS:
        plan, _ = Plan.objects.update_or_create(code=code, defaults={"display_name": name, "rank": rank,
            "sort_order": order, "description": "Weekly catalogue plan; launch pricing remains unconfigured.", "is_fallback": rank == 1, "changed_by_actor_id": ACTOR, "reason": REASON})
        values = {"device_instances": "1", "screen_outputs": "2", "ndi_outputs": "0",
                  "cloud_transcript_minutes_per_week": str(minutes), "sermon_notes_per_week": str(notes), "watermark": watermark}
        for key, value in values.items():
            pending = rank > 1 and key in {"device_instances", "screen_outputs", "ndi_outputs"}
            Grant.objects.update_or_create(plan=plan, dimension=dimensions[key],
                defaults={"raw_value": value, "changed_by_actor_id": ACTOR, "reason": PENDING if pending else REASON})
    revision, created = Revision.objects.get_or_create(pk=1, defaults={"revision": 1})
    if not created:
        Revision.objects.filter(pk=1).update(revision=F("revision") + 1)


def restore_backup(apps, schema_editor):
    raise IrreversibleError("Restore the pre-migration database backup with matching code; constants cannot recover prior assignments/audits.")


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("selahcue_catalogue", "0006_price_and_rank_schema"), ("selahcue_audit", "0001_initial")]
    operations = [migrations.RunPython(seed, restore_backup)]
