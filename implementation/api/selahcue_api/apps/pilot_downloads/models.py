from django.db import models


class PilotSheetDestination(models.Model):
    # Keyed destination fingerprint, not a Google credential/document identifier.
    fingerprint = models.CharField(max_length=64, primary_key=True)
    next_row = models.PositiveBigIntegerField(default=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(next_row__gte=2), name="pilot_sheet_next_row_after_header"),
        ]


class PilotRegistrationRecord(models.Model):
    """Allocation ledger: no raw contact/church fields. Preserve row reservations.

    Fingerprints/UUIDs are still pseudonymous metadata subject to the approved
    policy. Retention must not delete/reuse allocations or shift Sheet rows.
    """

    registration_id = models.UUIDField(primary_key=True)
    destination = models.ForeignKey(PilotSheetDestination, on_delete=models.PROTECT)
    sheet_row = models.PositiveBigIntegerField()
    payload_fingerprint = models.CharField(max_length=64)
    platform = models.CharField(max_length=20)
    notice_version = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["destination", "sheet_row"], name="pilot_unique_destination_row"),
            models.CheckConstraint(condition=models.Q(sheet_row__gte=2), name="pilot_registration_row_after_header"),
            models.CheckConstraint(condition=models.Q(platform__in=["Windows", "Ubuntu", "macOS"]), name="pilot_supported_platform"),
        ]
