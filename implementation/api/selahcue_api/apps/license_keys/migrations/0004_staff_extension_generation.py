from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("selahcue_license_keys", "0003_free_license_lifecycle")]

    operations = [
        migrations.AddField(
            model_name="applicensekey",
            name="staff_extension_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
