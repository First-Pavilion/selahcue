"""List the failed password-reset confirms from one source address on one day.

    manage.py failed_reset_confirms --ip 203.0.113.5
    manage.py failed_reset_confirms --ip 2001:db8:1:2::9 --date 2026-10-26

The failed-confirm audit rows (86ak5r2pt) do not store the address; they store a keyed,
daily-rotating pseudonym of it (`audit_source_pseudonym`). This command is the way back for an
operator who already has an address: it computes that day's pseudonym for it, bucketing IPv6 to
its /64 exactly as the throttle does, and prints the matching rows, oldest first. It cannot
list the addresses behind a row, and it needs the deployment's SECRET_KEY to give the right
answer. A pseudonymised address is still personal data: use it for an incident, not for
browsing.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from selahcue_api.apps.accounts.services import (
    RESET_CONFIRM_FAILED_ACTION,
    audit_source_pseudonym_for_address,
)
from selahcue_api.apps.audit.models import AuditEvent

# Bounded output: an incident answer, not an export.
MAX_ROWS = 500


class Command(BaseCommand):
    help = "List failed password-reset confirms from one source address on one UTC day."

    def add_arguments(self, parser):
        parser.add_argument("--ip", required=True, help="The source address, IPv4 or IPv6.")
        parser.add_argument(
            "--date", default="", help="UTC day as YYYY-MM-DD (default: today). Pseudonyms rotate daily."
        )

    def handle(self, *args, **options):
        try:
            day = date.fromisoformat(options["date"]) if options["date"] else datetime.now(timezone.utc).date()
        except ValueError as error:
            raise CommandError("--date must be YYYY-MM-DD") from error
        try:
            actor_id = audit_source_pseudonym_for_address(options["ip"], day)
        except ValueError as error:
            raise CommandError("--ip is not an IPv4 or IPv6 address") from error

        rows = list(
            AuditEvent.objects.filter(action=RESET_CONFIRM_FAILED_ACTION, actor_id=actor_id).order_by(
                "created_at", "id"
            )[:MAX_ROWS]
        )
        self.stdout.write(f"pseudonym for {day.isoformat()}: {actor_id}")
        for row in rows:
            self.stdout.write(
                f"{row.created_at.isoformat()}  outcome={row.after.get('outcome', '')}  "
                f"account={row.target_id if row.target_type == 'customer_user' else '-'}"
            )
        self.stdout.write(f"{len(rows)} failed confirm(s)" + (f" (first {MAX_ROWS} shown)" if len(rows) == MAX_ROWS else ""))
