"""Bring every pre-catalogue licence into the catalogue with its entitlement unchanged.

The logic lives in `apps/catalogue/backfill.py` so the equivalence it promises can be
asserted directly against real models (`tests/test_catalogue_backfill_equivalence.py`)
rather than only through the migration executor. This file is the thin call.

Idempotent and re-runnable: aliases use get_or_create and overrides use
`bulk_create(ignore_conflicts=True)`, so a re-applied migration converges and never
overwrites an override an operator has since set by hand.

**Known trade-off:** a migration that imports application code is normally a trap, because
the code drifts while the migration is supposed to be frozen. It is accepted here because
`backfill_licenses_into_catalogue` takes every model it touches as an argument and reads no
module-level state — so a historical run behaves the same whatever the current models look
like — and because the alternative is a data migration whose equivalence guarantee can only
be exercised through the migration executor, which is exactly the guarantee most worth
testing directly.
"""

from django.db import migrations

from selahcue_api.apps.catalogue.backfill import (
    BACKFILL_REASON,
    backfill_licenses_into_catalogue,
)


def backfill(apps, _schema_editor):
    result = backfill_licenses_into_catalogue(
        license_key_model=apps.get_model("selahcue_license_keys", "AppLicenseKey"),
        plan_model=apps.get_model("selahcue_catalogue", "Plan"),
        alias_model=apps.get_model("selahcue_catalogue", "PlanScopeAlias"),
        dimension_model=apps.get_model("selahcue_catalogue", "GrantDimension"),
        override_model=apps.get_model("selahcue_catalogue", "LicenseGrantOverride"),
    )

    CatalogueRevision = apps.get_model("selahcue_catalogue", "CatalogueRevision")
    revision, created = CatalogueRevision.objects.get_or_create(pk=1, defaults={"revision": 1})
    if not created:
        revision.revision += 1
        revision.save(update_fields=["revision", "updated_at"])
    return result


def unbackfill(apps, _schema_editor):
    """Remove only what the backfill wrote: its seat overrides and its scope aliases.

    An override an operator edited afterwards is indistinguishable from one this wrote, so
    the reverse is scoped by the reason string the backfill stamps. Aliases repointed at a
    real tier are left alone — reversing the migration must not silently downgrade an org.
    """
    LicenseGrantOverride = apps.get_model("selahcue_catalogue", "LicenseGrantOverride")
    PlanScopeAlias = apps.get_model("selahcue_catalogue", "PlanScopeAlias")
    Plan = apps.get_model("selahcue_catalogue", "Plan")

    LicenseGrantOverride.objects.filter(reason=BACKFILL_REASON).delete()
    fallback_ids = list(Plan.objects.filter(is_fallback=True).values_list("id", flat=True))
    PlanScopeAlias.objects.filter(plan_id__in=fallback_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("selahcue_catalogue", "0002_seed_catalogue_reference_data"),
        ("selahcue_license_keys", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
