from django.db import migrations, models


BATCH_SIZE = 500
MAX_BIGINT = 2**63 - 1


def backfill_staff_extension_generation(apps, schema_editor):
    audit_event = apps.get_model("selahcue_audit", "AuditEvent")
    license_key = apps.get_model("selahcue_license_keys", "AppLicenseKey")
    alias = schema_editor.connection.alias
    events = audit_event.objects.using(alias).filter(
        action="license_key.extended", result="SUCCESS", target_type="app_license_key",
    ).order_by("pk")
    cursor = 0
    while True:
        batch = list(events.filter(pk__gt=cursor).values_list("pk", "target_id")[:BATCH_SIZE])
        if not batch:
            return
        cursor = batch[-1][0]
        targets = set()
        for _, target_id in batch:
            # Audit target IDs are text. Convert only canonical, in-range positive integers.
            if (
                1 <= len(target_id) <= 19 and target_id[0] != "0"
                and target_id.isascii() and target_id.isdecimal()
            ):
                target = int(target_id)
                if target <= MAX_BIGINT:
                    targets.add(target)
        if targets:
            license_key.objects.using(alias).filter(
                pk__in=targets, staff_extension_generation=0,
            ).update(staff_extension_generation=1)


class Migration(migrations.Migration):
    dependencies = [
        ("selahcue_devices", "0004_receipt_database_set_null"),
        ("selahcue_license_keys", "0004_staff_extension_generation"),
        ("selahcue_audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicetoken",
            name="staff_extension_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.RunPython(backfill_staff_extension_generation, migrations.RunPython.noop),
    ]
