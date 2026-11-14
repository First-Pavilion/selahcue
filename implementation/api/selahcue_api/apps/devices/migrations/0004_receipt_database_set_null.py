"""Database-owned token deletion without converting the protected identity graph.

Django E323/E050 prohibit mixing DB_SET_NULL and Python PROTECT in model state.
Keep DO_NOTHING in ORM state and install the explicit database referential action
using the supported schema-editor field alteration. Both directions preserve rows.
"""
from copy import copy

from django.db import migrations, models


def _with_action(field, action):
    changed = copy(field)
    changed.remote_field = copy(field.remote_field)
    changed.remote_field.on_delete = action
    return changed


def database_set_null(apps, schema_editor):
    receipt = apps.get_model("selahcue_devices", "DeviceActivationOperation")
    field = receipt._meta.get_field("result_token")
    schema_editor.alter_field(receipt, field, _with_action(field, models.DB_SET_NULL))


def restore_collector_set_null(apps, schema_editor):
    receipt = apps.get_model("selahcue_devices", "DeviceActivationOperation")
    field = receipt._meta.get_field("result_token")
    schema_editor.alter_field(
        receipt, _with_action(field, models.DB_SET_NULL), _with_action(field, models.SET_NULL),
    )


class Migration(migrations.Migration):
    dependencies = [("selahcue_devices", "0003_deviceactivationoperation")]
    operations = [migrations.SeparateDatabaseAndState(
        database_operations=[migrations.RunPython(database_set_null, restore_collector_set_null)],
        state_operations=[migrations.AlterField(
            model_name="deviceactivationoperation",
            name="result_token",
            field=models.ForeignKey(null=True, on_delete=models.DO_NOTHING, to="selahcue_devices.devicetoken"),
        )],
    )]
