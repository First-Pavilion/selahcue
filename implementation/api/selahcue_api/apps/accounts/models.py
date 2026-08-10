from django.db import models


class CustomerStatus(models.TextChoices):
    PROSPECT = "PROSPECT", "Prospect"
    TRIAL = "TRIAL", "Trial"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    SUSPENDED = "SUSPENDED", "Suspended"
    CANCELLED = "CANCELLED", "Cancelled"
    CHURNED = "CHURNED", "Churned"
    ARCHIVED = "ARCHIVED", "Archived"


class CustomerOrg(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    status = models.CharField(max_length=32, choices=CustomerStatus.choices, default=CustomerStatus.PROSPECT)
    primary_contact_email = models.EmailField()
    billing_contact_email = models.EmailField(blank=True)
    country = models.CharField(max_length=2)
    timezone = models.CharField(max_length=64, default="UTC")
    plan = models.CharField(max_length=64, default="TRIAL")
    seat_limit = models.PositiveIntegerField(default=1)
    device_limit = models.PositiveIntegerField(default=1)
    internal_notes = models.TextField(blank=True)
    created_by_actor_id = models.CharField(max_length=128)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["created_by_actor_id", "idempotency_key"],
                name="uniq_customer_org_actor_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "country"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["primary_contact_email"]),
        ]

    def __str__(self) -> str:
        return self.name
