from django.db import models


class DeviceStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVOKED = "REVOKED", "Revoked"


class DeviceTokenStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REVOKED = "REVOKED", "Revoked"


class Device(models.Model):
    """An account-bound device instance (DEC-004): a single install activated against an
    enrollment key, counted against the plan's instance limit (`AppLicenseKey.device_limit`)."""

    license_key = models.ForeignKey(
        "selahcue_license_keys.AppLicenseKey",
        on_delete=models.PROTECT,
        related_name="devices",
    )
    customer = models.ForeignKey(
        "selahcue_accounts.CustomerOrg",
        on_delete=models.PROTECT,
        related_name="devices",
    )
    # Stable public id used as the device's ActorContext.actor_id in audit + future device-token auth.
    device_public_id = models.CharField(max_length=64, unique=True)
    # Client-supplied stable install/hardware identity (the natural device key under a license).
    device_fingerprint = models.CharField(max_length=128)
    platform = models.CharField(max_length=32)
    app_version = models.CharField(max_length=32, blank=True)
    display_name = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=DeviceStatus.choices, default=DeviceStatus.ACTIVE)
    activated_by_actor_id = models.CharField(max_length=128)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Retry-idempotency: the same presented key + client idempotency key is one device.
            models.UniqueConstraint(
                fields=["license_key", "idempotency_key"],
                name="uniq_device_key_idempotency",
            ),
            # Natural device identity: one device row per (license, install fingerprint).
            models.UniqueConstraint(
                fields=["license_key", "device_fingerprint"],
                name="uniq_device_license_fingerprint",
            ),
        ]
        indexes = [
            models.Index(fields=["license_key", "status"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["device_public_id"]),
        ]

    def __str__(self) -> str:
        return self.device_public_id


class DeviceToken(models.Model):
    """A show-once device token: the credential the desktop presents on every subsequent
    `device_token`-authed /v1 call. Only the masked triple + hash + fingerprint are stored;
    the full token leaves the system exactly once (the activation response)."""

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="tokens",
    )
    token_prefix = models.CharField(max_length=32)
    token_suffix = models.CharField(max_length=16)
    masked_token = models.CharField(max_length=64)
    token_hash = models.CharField(max_length=256)
    token_fingerprint = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=DeviceTokenStatus.choices, default=DeviceTokenStatus.ACTIVE)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="UTC")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("issued_at")),
                name="device_token_expires_after_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["device", "status"]),
        ]

    def __str__(self) -> str:
        return self.masked_token
