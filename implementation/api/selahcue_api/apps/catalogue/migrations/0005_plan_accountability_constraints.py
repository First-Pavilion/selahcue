"""Constrain the accountability columns 0004 added and backfilled.

**Deliberately a separate migration from 0004, and it must stay that way.** `PlanGrant`
carries foreign keys, so 0004's backfill `UPDATE` queues deferred FK trigger events, and
Postgres refuses `ALTER TABLE ... ADD CONSTRAINT` on a table that has any pending:

    cannot ALTER TABLE "selahcue_catalogue_plangrant" because it has pending trigger events

A migration is one transaction, so inside 0004 that queue is still unflushed when the ALTER
runs. Here it is a new transaction, after 0004 has committed and the queue has drained.

SQLite has no deferred trigger queue and applies the merged version happily, so this is
invisible to anything verified on the bundled SQLite — which is exactly how the merged
version reached CI. CI and production run Postgres; local `pytest` does not. Treat "it
passed locally" as no evidence at all for a migration that mixes a data write with a schema
change on the same table.

The ordering argument from 0004 is unchanged: columns, then backfill, then constrain. At no
point does a row exist that the schema forbids.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("selahcue_catalogue", "0004_plan_accountability"),
    ]

    operations = [
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
