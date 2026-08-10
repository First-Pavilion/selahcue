from django.db import models


class LicenseKeyType(models.TextChoices):
    DEMO = "DEMO", "Demo"
    TRIAL = "TRIAL", "Trial"
    PILOT = "PILOT", "Pilot"
    PAID = "PAID", "Paid"
    INTERNAL_QA = "INTERNAL_QA", "Internal QA"
    CUSTOM = "CUSTOM", "Custom"


class LicenseKeyStatus(models.TextChoices):
    ISSUED = "ISSUED", "Issued"
    ACTIVATED = "ACTIVATED", "Activated"
    EXPIRING = "EXPIRING", "Expiring"
    EXPIRED = "EXPIRED", "Expired"
    SUSPENDED = "SUSPENDED", "Suspended"
    REVOKED = "REVOKED", "Revoked"
    CONVERTED = "CONVERTED", "Converted"
    ARCHIVED = "ARCHIVED", "Archived"


class AppLicenseKey(models.Model):
    customer = models.ForeignKey(
        "selahcue_accounts.CustomerOrg",
        on_delete=models.PROTECT,
        related_name="license_keys",
    )
    key_type = models.CharField(max_length=32, choices=LicenseKeyType.choices)
    status = models.CharField(max_length=32, choices=LicenseKeyStatus.choices, default=LicenseKeyStatus.ISSUED)
    key_prefix = models.CharField(max_length=32)
    key_suffix = models.CharField(max_length=16)
    masked_key = models.CharField(max_length=64)
    secret_hash = models.CharField(max_length=256)
    secret_fingerprint = models.CharField(max_length=64, unique=True)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="UTC")
    feature_scope = models.CharField(max_length=64)
    seat_limit = models.PositiveIntegerField(default=1)
    device_limit = models.PositiveIntegerField(default=1)
    territory = models.CharField(max_length=32, blank=True)
    generated_by_actor_id = models.CharField(max_length=128)
    generated_reason = models.TextField()
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["generated_by_actor_id", "idempotency_key"],
                name="uniq_license_key_actor_idempotency",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("starts_at")),
                name="license_key_expires_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "status", "expires_at"]),
            models.Index(fields=["key_prefix"]),
            models.Index(fields=["key_suffix"]),
            models.Index(fields=["key_type", "status"]),
        ]

    def __str__(self) -> str:
        return self.masked_key
