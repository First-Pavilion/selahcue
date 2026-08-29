"""Seed the DEC-008 tier table as data.

**This file is the only place in the API where a tier name appears, and that is the whole
design.** `tests/test_product_catalogue_slice.py` sweeps every other Python module in
`selahcue_api/` for these names and fails if one turns up — and asserts that it still finds
them *here*, so the sweep cannot quietly stop looking.

After this migration, changing "Platinum" to something else, or Pro's STT allowance from 5
hours to 8, is an UPDATE against a row. No code, no migration, no release (FR-544).

**Never edit this file to change a value.** Once it has been applied anywhere, editing it
changes what a FRESH database gets while every already-migrated environment keeps the old
row — the two silently diverge, and the difference shows up as a support ticket about a
customer whose limits are wrong on one deployment only. Change the value the way an
operator would: `manage.py set_plan_grant`. (There is no Django admin in this project —
`django.contrib.admin` is not installed and no `admin.py` exists — so the management
commands in `apps/catalogue/management/commands/` are the operator surface.) This file
describes the day the catalogue was created, not what it currently holds.

**Dimension defaults are a deliberate, asymmetric safety policy.** A dimension's default
applies when a plan declares no value for it — i.e. when a catalogue row is incomplete:

*   Core presentation (`screen_outputs`) defaults **permissive** (`unlimited`). An
    unconfigured plan must never be the reason a church loses its second screen mid-service
    (NFR-024 posture: never take away live output).
*   Paid add-ons (`ndi_outputs`, `stt_minutes_per_period`) default **restrictive** (`0`).
    These cost money to serve; an unconfigured plan must not give them away.
*   `watermark` defaults **on**, restrictive for the same reason — and a watermark degrades
    output, it never blanks it.
*   `device_instances` defaults to **nothing at all** (empty), and is additionally marked
    `publish_in_manifest=False` so it never reaches the signed payload. Absent and
    `unlimited` are different states, and more importantly nothing today reconciles a
    plan's seat number with `AppLicenseKey.device_limit` — FR-516's write-back is specified
    but not built. Publishing both would put two disagreeing seat numbers in one signed
    artefact, and the payload has no way to mark one advisory. The ROW still exists, so
    FR-516 and the portal can read it; only the wire is silent.
"""

from django.db import migrations

# (key, display_name, value_type, default_raw_value, publish_in_manifest, sort_order,
#  description)
DIMENSIONS = [
    (
        "device_instances",
        "Device instances (seats)",
        "INTEGER",
        "",
        False,
        10,
        "Activated device instances a tier allows (DEC-004 AS-P8: a seat is a device "
        "instance, not a separate licence key). NOT published to the manifest: "
        "`AppLicenseKey.device_limit` is what activation enforces, and nothing reconciles "
        "the two until FR-516's write-back is built. Kept as data for FR-516 and the "
        "portal to read.",
    ),
    (
        "screen_outputs",
        "Screen / outputs",
        "INTEGER",
        "unlimited",
        True,
        20,
        "Simultaneous screen outputs. What exactly counts as one output is AS-P9, still "
        "open in D1; the value is data, so closing AS-P9 changes rows, not code.",
    ),
    (
        "ndi_outputs",
        "NDI outputs",
        "INTEGER",
        "0",
        True,
        30,
        "Simultaneous NDI outputs. 0 means the feature is not granted.",
    ),
    (
        "stt_minutes_per_period",
        "Hosted STT minutes per period",
        "INTEGER",
        "0",
        True,
        40,
        "Hosted speech-to-text minutes, pooled across the org's seats and reset each "
        "calendar month on the billing anniversary (AS-P6/AS-P7). Metering and the period "
        "boundary belong to FR-546; this is the allowance only. The owner declares these "
        "values volatile — they depend on the AI subscription — which is why they are data.",
    ),
    (
        "watermark",
        "Watermark on output",
        "BOOLEAN",
        "true",
        True,
        50,
        "True means output carries the SelahCue watermark.",
    ),
]

# (code, display_name, is_fallback, sort_order, description)
PLANS = [
    (
        "LEGACY",
        "Legacy (pre-catalogue)",
        True,
        0,
        "Bridge plan for licences issued before the catalogue existed, and the fallback for "
        "anything that resolves to nothing else. Its grants freeze the behaviour those "
        "licences already had, so the catalogue changes nothing for them.",
    ),
    ("FREE", "Free", False, 10, "Entry tier (DEC-008)."),
    ("PRO", "Pro", False, 20, "Mid tier (DEC-008)."),
    ("PLATINUM", "Platinum", False, 30, "Top tier (DEC-008)."),
]

# {plan code: {dimension key: raw value}} — the DEC-008 table, verbatim.
#
# LEGACY declares no `device_instances`, and that dimension has no default, so the key is
# simply ABSENT for every legacy licence. Nothing is published about seats, and
# `instances_limit` (= `device_limit`) remains the single number for that quantity. The
# other four freeze pre-catalogue behaviour: nothing capped outputs or NDI, nothing drew a
# watermark, and hosted STT did not exist — and with FR-546's metering unbuilt, any
# non-zero STT allowance would be an UNMETERED one, which is unlimited by another name.
GRANTS = {
    "LEGACY": {
        "screen_outputs": "unlimited",
        "ndi_outputs": "unlimited",
        "stt_minutes_per_period": "0",
        "watermark": "false",
    },
    "FREE": {
        "device_instances": "1",
        "screen_outputs": "2",
        "ndi_outputs": "0",
        "stt_minutes_per_period": "30",
        "watermark": "true",
    },
    "PRO": {
        "device_instances": "3",
        "screen_outputs": "5",
        "ndi_outputs": "5",
        "stt_minutes_per_period": "300",
        "watermark": "false",
    },
    "PLATINUM": {
        "device_instances": "7",
        "screen_outputs": "10",
        "ndi_outputs": "10",
        "stt_minutes_per_period": "600",
        "watermark": "false",
    },
}


def seed(apps, _schema_editor):
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    GrantDimension = apps.get_model("selahcue_catalogue", "GrantDimension")
    PlanGrant = apps.get_model("selahcue_catalogue", "PlanGrant")
    CatalogueRevision = apps.get_model("selahcue_catalogue", "CatalogueRevision")

    dimensions = {}
    for (
        key,
        display_name,
        value_type,
        default_raw,
        publish_in_manifest,
        sort_order,
        description,
    ) in DIMENSIONS:
        dimension, _created = GrantDimension.objects.get_or_create(
            key=key,
            defaults={
                "display_name": display_name,
                "description": description,
                "value_type": value_type,
                "default_raw_value": default_raw,
                "is_active": True,
                "publish_in_manifest": publish_in_manifest,
                "sort_order": sort_order,
            },
        )
        dimensions[key] = dimension

    plans = {}
    for code, display_name, is_fallback, sort_order, description in PLANS:
        # `is_fallback` is under a partial unique constraint, so never claim it when another
        # row already holds it — an operator may have moved it deliberately.
        claim_fallback = is_fallback and not Plan.objects.filter(is_fallback=True).exclude(
            code=code
        ).exists()
        plan, _created = Plan.objects.get_or_create(
            code=code,
            defaults={
                "display_name": display_name,
                "description": description,
                "is_fallback": claim_fallback,
                "sort_order": sort_order,
            },
        )
        plans[code] = plan

    for plan_code, grants in GRANTS.items():
        plan = plans[plan_code]
        for dimension_key, raw_value in grants.items():
            PlanGrant.objects.get_or_create(
                plan=plan,
                dimension=dimensions[dimension_key],
                defaults={"raw_value": raw_value},
            )

    # Signals do not fire for historical models, so bump the counter explicitly: any process
    # that read the (empty) catalogue before this ran must not keep serving that read.
    revision, created = CatalogueRevision.objects.get_or_create(pk=1, defaults={"revision": 1})
    if not created:
        revision.revision += 1
        revision.save(update_fields=["revision", "updated_at"])


def unseed(apps, _schema_editor):
    """Reverse by removing only the rows this migration introduces, and only its own grants.

    Deliberately does NOT delete plans an operator added afterwards, nor grants they
    changed onto other dimensions — this is reference data, and after seeding it belongs to
    the operator, not to the migration.
    """
    Plan = apps.get_model("selahcue_catalogue", "Plan")
    GrantDimension = apps.get_model("selahcue_catalogue", "GrantDimension")
    PlanGrant = apps.get_model("selahcue_catalogue", "PlanGrant")

    PlanGrant.objects.filter(
        plan__code__in=[code for code, *_rest in PLANS],
        dimension__key__in=[key for key, *_rest in DIMENSIONS],
    ).delete()
    # PROTECTed relations (aliases, assignments) block a plan delete, which is correct:
    # reversing past a backfill should fail loudly rather than orphan live mappings.
    Plan.objects.filter(code__in=[code for code, *_rest in PLANS]).delete()
    GrantDimension.objects.filter(key__in=[key for key, *_rest in DIMENSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("selahcue_catalogue", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
