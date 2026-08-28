"""Put the accountability columns on `Plan` and `PlanGrant` too.

`LicensePlanAssignment` and `LicenseGrantOverride` have carried actor/reason CHECK
constraints since 0001, on the argument written beside `accountability_constraints`: a
service-layer permission check binds only the callers that remember to use the service, so
"a bare `objects.create()` from a shell must be refused too."

That argument applies harder to the two tables it was left off. An override changes ONE
customer's entitlement; a single `PlanGrant` row changes the allowance for **every tenant
on that plan**, and `Plan.is_fallback` decides what every unassigned licence in the system
grants. Shell access is already game-over under the documented trust model, so this is
consistency rather than new protection — but the inconsistency was in the direction of the
higher-blast-radius table, which is the wrong way round.

**Three operations, in this order, and the order is the point.** Adding a column and
constraining it in one step fails against a table that already has rows: the seeded plans
and grants from 0002 would be checked against a constraint they cannot yet satisfy. So the
columns land nullable-in-effect (a blank default), the existing rows are backfilled, and
only then is the constraint applied. That is also what makes this safe against live data:
at no point is there a window where a row exists that the schema forbids.
"""

from django.db import migrations, models

# The rows this backfills were written by migration 0002, not by a person. Naming the
# migration is more honest than attributing them to whoever happens to run `migrate`, and
# it is greppable in a way "system" is not.
SEED_ACTOR_ID = "migration_0002_seed_catalogue_reference_data"

# Must clear `MIN_REASON_LENGTH` (8) or the constraint this migration adds would reject the
# very rows it just backfilled.
SEED_REASON = (
    "Catalogue reference data seeded by migration 0002 from the DEC-008 tier table, "
    "before these accountability columns existed."
)

assert len(SEED_REASON) >= 8, "the backfilled reason must satisfy the constraint added below"


def backfill_accountability(apps, schema_editor):
    """Give every pre-existing row a truthful actor and reason.

    Scoped to rows that are actually blank, so re-running or resuming this migration cannot
    overwrite a real operator's name with the seed's.
    """
    for model_name in ("Plan", "PlanGrant"):
        model = apps.get_model("selahcue_catalogue", model_name)
        model.objects.filter(changed_by_actor_id="").update(changed_by_actor_id=SEED_ACTOR_ID)
        model.objects.filter(reason="").update(reason=SEED_REASON)


def unbackfill(apps, schema_editor):
    """Deliberately a no-op.

    Reversing this migration drops the columns immediately afterwards, so blanking them
    first would be work whose only observable effect is a window where the rows carry less
    information than they did. The constraint removal is what makes the reverse safe.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("selahcue_catalogue", "0003_map_existing_feature_scopes"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="changed_by_actor_id",
            field=models.CharField(default="", max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plan",
            name="reason",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plangrant",
            name="changed_by_actor_id",
            field=models.CharField(default="", max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plangrant",
            name="reason",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_accountability, unbackfill),
        migrations.AddConstraint(
            model_name="plan",
            constraint=models.CheckConstraint(
                condition=~models.Q(changed_by_actor_id=""),
                name="catalogue_plan_actor_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="plan",
            constraint=models.CheckConstraint(
                condition=models.Q(reason__regex=r".{8,}"),
                name="catalogue_plan_reason_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="plangrant",
            constraint=models.CheckConstraint(
                condition=~models.Q(changed_by_actor_id=""),
                name="catalogue_plan_grant_actor_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="plangrant",
            constraint=models.CheckConstraint(
                condition=models.Q(reason__regex=r".{8,}"),
                name="catalogue_plan_grant_reason_required",
            ),
        ),
    ]
