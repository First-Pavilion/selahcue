"""Place one licence on a plan, audited.

    manage.py assign_license_plan --license <id> --plan PRO \
        --actor staff_ops_1 --reason "Upgraded after the pilot."

The governed path for what was previously a bare `objects.create()` recording neither who
moved a church between tiers nor why.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from selahcue_api.apps.catalogue.management.commands._actor import (
    default_idempotency_key,
    staff_actor,
)
from selahcue_api.apps.catalogue.services import (
    SetLicensePlanAssignmentData,
    set_license_plan_assignment,
)
from selahcue_api.graphql.errors import SafeAPIError


class Command(BaseCommand):
    help = "Assign a licence key to a catalogue plan (audited)."

    def add_arguments(self, parser):
        parser.add_argument("--license", required=True, help="AppLicenseKey id.")
        parser.add_argument("--plan", required=True, help="Plan code.")
        parser.add_argument("--actor", required=True, help="Staff actor id, for the audit trail.")
        parser.add_argument("--reason", required=True, help="Why, for the audit trail.")
        parser.add_argument("--idempotency-key", default="")

    def handle(self, *args, **options):
        idempotency_key = options["idempotency_key"] or default_idempotency_key(
            "cli-assign", options["license"], options["plan"]
        )
        try:
            result = set_license_plan_assignment(
                staff_actor(options["actor"]),
                SetLicensePlanAssignmentData(
                    idempotency_key=idempotency_key,
                    license_key_id=options["license"],
                    plan_code=options["plan"],
                    reason=options["reason"],
                ),
            )
        except SafeAPIError as error:
            raise CommandError(f"{error.code.value}: {error}") from error
        self.stdout.write(
            self.style.SUCCESS(
                f"licence {options['license']}: "
                f"{result.previous_plan_code!r} -> {result.assignment.plan.code!r}"
            )
        )
