"""Seed the DEC-008 tier table as data.

**This file is the only place in the API where a tier name appears, and that is the whole
design.** `tests/test_product_catalogue_slice.py` sweeps every other Python module in
`selahcue_api/` for these names and fails if one turns up — and asserts that it still finds
them *here*, so the sweep cannot quietly stop looking.

After this migration, changing "Platinum" to something else, or Pro's STT allowance from 5
hours to 8, is an UPDATE against a row. No code, no migration, no release (FR-544).

**Dimension defaults are a deliberate, asymmetric safety policy.** A dimension's default
applies when a plan declares no value for it — i.e. when a catalogue row is incomplete:

*   Core presentation (`device_instances`, `screen_outputs`) defaults **permissive**
    (`unlimited`). An unconfigured plan must never be the reason a church loses its second
    screen mid-service (NFR-024 posture: never take away live output).
*   Paid add-ons (`ndi_outputs`, `stt_minutes_per_period`) default **restrictive** (`0`).
    These cost money to serve; an unconfigured plan must not give them away.
*   `watermark` defaults **on**, restrictive for the same reason — and a watermark degrades
    output, it never blanks it.
"""

from django.db import migrations

# (key, display_name, value_type, default_raw_value, governs_instance_limit, sort_order,
#  description)
DIMENSIONS = [
    (
        "device_instances",
        "Device instances (seats)",
        "INTEGER",
        "unlimited",
        True,
        10,
        "Activated device instances allowed under the org's licence key (DEC-004 AS-P8: a "
        "seat is a device instance, not a separate licence key).",
    ),
    (
        "screen_outputs",
        "Screen / outputs",
        "INTEGER",
        "unlimited",
        False,
        20,
        "Simultaneous screen outputs. What exactly counts as one output is AS-P9, still "
        "open in D1; the value is data, so closing AS-P9 changes rows, not code.",
    ),
    (
        "ndi_outputs",
        "NDI outputs",
        "INTEGER",
        "0",
        False,
        30,
        "Simultaneous NDI outputs. 0 means the feature is not granted.",
    ),
    (
        "stt_minutes_per_period",
        "Hosted STT minutes per period",
        "INTEGER",
        "0",
        False,
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
        False,
        50,
        "True means output carries the SelahCue watermark.",
    ),
]

# (code, display_name, is_public, is_fallback, sort_order, description)
PLANS = [
    (
        "LEGACY",
        "Legacy (pre-catalogue)",
        False,
        True,
        0,
        "Bridge plan for licences issued before the catalogue existed, and the fallback for "
        "anything that resolves to nothing else. Its grants freeze the behaviour those "
        "licences already had, so the catalogue changes nothing for them.",
    ),
    ("FREE", "Free", True, False, 10, "Entry tier (DEC-008)."),
    ("PRO", "Pro", True, False, 20, "Mid tier (DEC-008)."),
    ("PLATINUM", "Platinum", True, False, 30, "Top tier (DEC-008)."),
]

# {plan code: {dimension key: raw value}} — the DEC-008 table, verbatim.
#
# LEGACY declares no `device_instances`, so it falls through to that dimension's
# `unlimited` default, which the manifest reads as "the catalogue expresses no seat cap"
# and answers with the licence's own `device_limit`. Migration 0003 additionally pins every
# existing licence's seat cap as an explicit override, so equivalence is exact per row
# rather than merely by convention.
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
    for key, display_name, value_type, default_raw, governs, sort_order, description in DIMENSIONS:
        # A fallback/instance-limit flag is under a partial unique constraint, so never set
        # it when another row already holds it — an operator may have moved it deliberately.
        claim_governs = governs and not GrantDimension.objects.filter(
            governs_instance_limit=True
        ).exclude(key=key).exists()
        dimension, _created = GrantDimension.objects.get_or_create(
            key=key,
            defaults={
                "display_name": display_name,
                "description": description,
                "value_type": value_type,
                "default_raw_value": default_raw,
                "is_active": True,
                "governs_instance_limit": claim_governs,
                "sort_order": sort_order,
            },
        )
        dimensions[key] = dimension

    plans = {}
    for code, display_name, is_public, is_fallback, sort_order, description in PLANS:
        claim_fallback = is_fallback and not Plan.objects.filter(is_fallback=True).exclude(
            code=code
        ).exists()
        plan, _created = Plan.objects.get_or_create(
            code=code,
            defaults={
                "display_name": display_name,
                "description": description,
                "status": "ACTIVE",
                "is_public": is_public,
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
