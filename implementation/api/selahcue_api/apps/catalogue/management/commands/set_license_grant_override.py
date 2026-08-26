"""Grant one licence a time-boxed deviation from its plan, audited.

    manage.py set_license_grant_override --license <id> --dimension ndi_outputs \
        --value 8 --actor staff_ops_1 --reason "Conference loan until October."

Time-boxed by default (see `DEFAULT_OVERRIDE_DAYS`); `--permanent` opts out deliberately.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from selahcue_api.apps.catalogue.management.commands._actor import (
    default_idempotency_key,
    staff_actor,
)
from selahcue_api.apps.catalogue.services import (
    SetLicenseGrantOverrideData,
    set_license_grant_override,
)
from selahcue_api.graphql.errors import SafeAPIError


class Command(BaseCommand):
    help = "Set a per-licence grant override (audited, time-boxed by default)."

    def add_arguments(self, parser):
        parser.add_argument("--license", required=True, help="AppLicenseKey id.")
        parser.add_argument("--dimension", required=True, help="Grant dimension key.")
        parser.add_argument("--value", required=True, help="Raw value.")
        parser.add_argument("--actor", required=True, help="Staff actor id, for the audit trail.")
        parser.add_argument("--reason", required=True, help="Why, for the audit trail.")
        parser.add_argument(
            "--permanent",
            action="store_true",
            help="Opt out of the default expiry. Use sparingly: an override nobody revisits "
            "is an entitlement nobody is charging for.",
        )
        parser.add_argument("--idempotency-key", default="")

    def handle(self, *args, **options):
        idempotency_key = options["idempotency_key"] or default_idempotency_key(
            "cli-override", options["license"], options["dimension"], options["value"]
        )
        try:
            result = set_license_grant_override(
                staff_actor(options["actor"]),
                SetLicenseGrantOverrideData(
                    idempotency_key=idempotency_key,
                    license_key_id=options["license"],
                    dimension_key=options["dimension"],
                    raw_value=options["value"],
                    reason=options["reason"],
                    permanent=options["permanent"],
                ),
            )
        except SafeAPIError as error:
            raise CommandError(f"{error.code.value}: {error}") from error
        expiry = result.override.expires_at.isoformat() if result.override.expires_at else "never"
        self.stdout.write(
            self.style.SUCCESS(
                f"{options['dimension']}: {result.previous_raw_value!r} -> "
                f"{result.override.raw_value!r} (expires {expiry})"
            )
        )
