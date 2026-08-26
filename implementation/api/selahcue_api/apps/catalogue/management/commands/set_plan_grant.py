"""Change what a plan grants on one dimension, from the command line.

The operator lever behind FR-544: renaming a tier or moving Pro's STT allowance from 5
hours to 8 is this command, not a release. It is a thin wrapper over
`catalogue.services.set_plan_grant`, so it inherits the permission check, the idempotency
handling and the audit record rather than writing rows behind them.

    manage.py set_plan_grant --plan PRO --dimension stt_minutes_per_period \
        --value 480 --actor staff_ops_1 --reason "AI subscription upgraded to 8h."
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from selahcue_api.apps.catalogue.management.commands._actor import (
    default_idempotency_key,
    staff_actor,
)
from selahcue_api.apps.catalogue.services import SetPlanGrantData, set_plan_grant
from selahcue_api.graphql.errors import SafeAPIError


class Command(BaseCommand):
    help = "Set a plan's grant value for one dimension (audited)."

    def add_arguments(self, parser):
        parser.add_argument("--plan", required=True, help="Plan code, e.g. the row's `code`.")
        parser.add_argument("--dimension", required=True, help="Grant dimension key.")
        parser.add_argument("--value", required=True, help="New raw value.")
        parser.add_argument("--actor", required=True, help="Staff actor id, for the audit trail.")
        parser.add_argument("--reason", required=True, help="Why, for the audit trail.")
        parser.add_argument(
            "--idempotency-key",
            default="",
            help="Optional; defaults to a deterministic key built from the arguments.",
        )

    def handle(self, *args, **options):
        idempotency_key = options["idempotency_key"] or default_idempotency_key(
            "cli-grant", options["plan"], options["dimension"], options["value"]
        )
        try:
            result = set_plan_grant(
                staff_actor(options["actor"]),
                SetPlanGrantData(
                    idempotency_key=idempotency_key,
                    plan_code=options["plan"],
                    dimension_key=options["dimension"],
                    raw_value=options["value"],
                    reason=options["reason"],
                ),
            )
        except SafeAPIError as error:
            raise CommandError(f"{error.code.value}: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"{options['plan']}.{options['dimension']}: "
                f"{result.previous_raw_value!r} -> {result.grant.raw_value!r}"
            )
        )
