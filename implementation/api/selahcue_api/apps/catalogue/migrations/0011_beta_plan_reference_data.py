"""Seed the time-limited BETA catalogue plan (ClickUp 17tnw2bhkd2).

BETA unlocks everything a church can be granted: no watermark, unlimited outputs and a
generous weekly allowance. It ranks above PRO and is never the fallback; FREE stays the
only fallback. Seed constants belong only in seed migrations, never in API source.
"""
from django.db import migrations
from django.db.models import F

ACTOR = "migration:17tnw2bhkd2"
REASON = "Approved beta licensing plan: unlocks every grant for a limited time."
VALUES = {"device_instances": "10", "screen_outputs": "unlimited", "ndi_outputs": "unlimited",
          "watermark": "false", "cloud_transcript_minutes_per_week": "180", "sermon_notes_per_week": "5"}


def seed(apps, schema_editor):
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    Grant = apps.get_model("selahcue_catalogue", "PlanGrant")
    Dimension = apps.get_model("selahcue_catalogue", "GrantDimension")
    Revision = apps.get_model("selahcue_catalogue", "CatalogueRevision")
    dimensions = {d.key: d for d in Dimension.objects.filter(key__in=VALUES)}
    if set(dimensions) != set(VALUES):
        raise RuntimeError("Unexpected catalogue dimension shape; review before seeding the beta plan.")
    plan, _ = Plan.objects.update_or_create(code="BETA", defaults={
        "display_name": "Beta", "rank": 4, "sort_order": 40, "is_fallback": False,
        "description": "Time-limited beta plan; launch pricing remains unconfigured.",
        "changed_by_actor_id": ACTOR, "reason": REASON})
    for key, value in VALUES.items():
        Grant.objects.update_or_create(plan=plan, dimension=dimensions[key],
            defaults={"raw_value": value, "changed_by_actor_id": ACTOR, "reason": REASON})
    revision, created = Revision.objects.get_or_create(pk=1, defaults={"revision": 1})
    if not created:
        Revision.objects.filter(pk=1).update(revision=F("revision") + 1)


def unseed(apps, schema_editor):
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    Grant = apps.get_model("selahcue_catalogue", "PlanGrant")
    Revision = apps.get_model("selahcue_catalogue", "CatalogueRevision")
    Grant.objects.filter(plan__code="BETA").delete()
    Plan.objects.filter(code="BETA").delete()
    Revision.objects.filter(pk=1).update(revision=F("revision") + 1)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("selahcue_catalogue", "0010_admin_mutation_receipt")]
    operations = [migrations.RunPython(seed, unseed)]
