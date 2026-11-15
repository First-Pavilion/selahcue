from uuid import uuid4

from django.db import models
from django.db.models import F, Q

from selahcue_api.apps.usage.contracts import ReservationState

OPEN_STATES = (ReservationState.RESERVED.value, ReservationState.ISSUED.value)


class UsageWeek(models.Model):
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    week_start_local = models.DateField()
    tz_name = models.CharField(max_length=64)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    # A westward transition can start accounting before the first unused local Monday.
    admissions_start_at = models.DateTimeField()
    counted_from = models.DateTimeField()
    high_water_rank = models.PositiveIntegerField()
    stt_seconds_settled = models.PositiveBigIntegerField(default=0)
    notes_settled = models.PositiveBigIntegerField(default=0)
    stt_seconds_carried_debt = models.PositiveBigIntegerField(default=0)
    notes_carried_debt = models.PositiveBigIntegerField(default=0)
    # Opening limits cap carried debt for the life of this row. High-water limits
    # measure overrun and can change only on an upgrade to a higher rank.
    opening_stt_seconds_limit = models.PositiveBigIntegerField()
    opening_notes_limit = models.PositiveBigIntegerField()
    high_water_stt_seconds_limit = models.PositiveBigIntegerField()
    high_water_notes_limit = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "week_start_local"], name="usage_week_org_local_uniq"),
            models.CheckConstraint(
                condition=(
                    Q(starts_at__lte=F("counted_from"), counted_from__lt=F("ends_at"))
                    & Q(starts_at__lte=F("admissions_start_at"), admissions_start_at__lt=F("ends_at"))
                ),
                name="usage_week_valid_bounds",
            ),
        ]
        indexes = [models.Index(fields=["org", "-starts_at"], name="usage_week_org_starts_idx")]


class UsageReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    org = models.ForeignKey("selahcue_accounts.CustomerOrg", on_delete=models.PROTECT)
    license = models.ForeignKey("selahcue_license_keys.AppLicenseKey", on_delete=models.PROTECT)
    device = models.ForeignKey("selahcue_devices.Device", on_delete=models.PROTECT)
    week = models.ForeignKey(UsageWeek, on_delete=models.PROTECT, related_name="reservations")
    provider_mapping = models.ForeignKey(
        "selahcue_providers.ProviderCredential", on_delete=models.PROTECT, null=True,
    )
    meter = models.CharField(max_length=5, choices=[("stt", "Transcription"), ("notes", "Notes")])
    units = models.PositiveIntegerField()
    state = models.CharField(max_length=8, choices=[(state.value, state.value) for state in ReservationState])
    idempotency_key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=64)
    admitted_at = models.DateTimeField()
    authorized_from = models.DateTimeField()
    authorized_until = models.DateTimeField()
    issued_at = models.DateTimeField(null=True, blank=True)
    last_minted_at = models.DateTimeField(null=True, blank=True)
    renews = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "meter", "idempotency_key"], name="usage_res_org_meter_key_uniq"),
            models.CheckConstraint(
                condition=Q(meter="stt", units=300) | Q(meter="notes", units=1, renews__isnull=True),
                name="usage_res_fixed_meter_units",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state__in=[state.value for state in ReservationState])
                    & ~Q(meter="notes", state=ReservationState.ISSUED)
                    & Q(retry_count=0)
                ),
                name="usage_res_valid_state",
            ),
            models.CheckConstraint(
                condition=Q(
                    admitted_at__lte=F("authorized_from"),
                    authorized_from__lt=F("authorized_until"),
                    admitted_at__lt=F("expires_at"),
                ),
                name="usage_res_valid_timing",
            ),
        ]
        indexes = [
            models.Index(fields=["week"], condition=Q(state__in=OPEN_STATES), name="usage_res_open_week_idx"),
            models.Index(
                fields=["org", "expires_at"], condition=Q(state=ReservationState.RESERVED.value),
                name="usage_res_expiry_idx",
            ),
        ]


class NoteDeliveryCredit(models.Model):
    class Reason(models.TextChoices):
        CONTENT_LOST = "CONTENT_LOST", "Content lost"

    reservation = models.OneToOneField(
        UsageReservation, on_delete=models.PROTECT, related_name="delivery_credit",
    )
    note_job_id = models.UUIDField(unique=True)
    original_week = models.ForeignKey(UsageWeek, on_delete=models.PROTECT, related_name="delivery_credits")
    units = models.PositiveIntegerField(default=1)
    observed_at = models.DateTimeField()
    reason = models.CharField(max_length=12, choices=Reason.choices, default=Reason.CONTENT_LOST)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(units=1, reason="CONTENT_LOST"), name="usage_credit_one_content_lost",
            ),
        ]
