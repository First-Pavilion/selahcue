from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("selahcue_accounts", "0004_remove_customerorg_device_limit"),
        ("selahcue_license_keys", "0002_applicensekey_prior_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="FreeLicenseLifecycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_version", models.PositiveSmallIntegerField()),
                ("renewal_enabled", models.BooleanField(default=True)),
                ("customer", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT, related_name="free_license_lifecycle",
                    to="selahcue_accounts.customerorg",
                )),
                ("license_key", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT, related_name="free_lifecycle",
                    to="selahcue_license_keys.applicensekey",
                )),
            ],
        ),
    ]
