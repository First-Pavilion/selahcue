"""Give every pre-catalogue `feature_scope` value a plan mapping.

**Self-contained on purpose.** An earlier draft called a helper in
`apps/catalogue/backfill.py`; passing every model in as an argument handled the *drift*
half of the migration-imports-app-code problem, but not the *existence* half — deleting or
renaming that module would break `migrate` on every environment, including a fresh
database, long after anyone remembers why it mattered. The body lives here instead, and
`tests/test_catalogue_scope_mapping.py` imports THIS module to exercise it.

**What this does and, importantly, what it does not.** It creates one `PlanScopeAlias` per
distinct `feature_scope` found in the licence table, pointing at the fallback plan, so no
existing licence is left unmapped and an operator can later repoint "CHURCH" at a real
tier without touching a licence row.

It writes **no per-licence overrides**. An earlier draft pinned each licence's
`device_limit` as a `LicenseGrantOverride`, which meant shipping a day-one exception on
100% of rows — an override table whose contents are indistinguishable from routine data is
an override table nobody audits. It is also unnecessary: the manifest publishes
`AppLicenseKey.device_limit` directly as `instances_limit`, so a legacy licence keeps
exactly the seat cap it had without the catalogue asserting anything about seats at all.

Idempotent: `get_or_create` per scope, so a re-applied or resumed migration converges.
"""

from django.db import migrations

BATCH_SIZE = 500


def map_scopes(apps, _schema_editor):
    AppLicenseKey = apps.get_model("selahcue_license_keys", "AppLicenseKey")
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    PlanScopeAlias = apps.get_model("selahcue_catalogue", "PlanScopeAlias")
    CatalogueRevision = apps.get_model("selahcue_catalogue", "CatalogueRevision")

    bridge_plan = Plan.objects.filter(is_fallback=True).first()
    if bridge_plan is None:
        # Loud, not silent: mapping nothing would leave the estate unmapped and look like
        # success. Found by its DATA flag, so no tier name appears in this file.
        raise RuntimeError(
            "no fallback plan exists; catalogue reference data must be seeded first"
        )

    # Distinct scopes only — a handful of rows however large the estate. `.distinct()` on
    # the column keeps this bounded regardless of licence count (repo bounded-memory rule).
    scopes = {
        (scope or "").strip().upper()
        for scope in AppLicenseKey.objects.values_list("feature_scope", flat=True)
        .distinct()
        .iterator(chunk_size=BATCH_SIZE)
    }
    scopes.discard("")

    for scope in sorted(scopes):
        PlanScopeAlias.objects.get_or_create(
            feature_scope=scope, defaults={"plan": bridge_plan}
        )

    revision, created = CatalogueRevision.objects.get_or_create(pk=1, defaults={"revision": 1})
    if not created:
        revision.revision += 1
        revision.save(update_fields=["revision", "updated_at"])


def unmap_scopes(apps, _schema_editor):
    """Remove only the aliases still pointing at the fallback plan.

    An alias an operator has since repointed at a real tier is left alone: reversing this
    migration must not silently downgrade an org that has been moved onto a paid plan.
    """
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    PlanScopeAlias = apps.get_model("selahcue_catalogue", "PlanScopeAlias")

    fallback_ids = list(Plan.objects.filter(is_fallback=True).values_list("id", flat=True))
    PlanScopeAlias.objects.filter(plan_id__in=fallback_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("selahcue_catalogue", "0002_seed_catalogue_reference_data"),
        ("selahcue_license_keys", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(map_scopes, unmap_scopes),
    ]
