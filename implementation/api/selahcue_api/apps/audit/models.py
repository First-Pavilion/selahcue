from django.db import models


class AuditResult(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    DENIED = "DENIED", "Denied"
    FAILED = "FAILED", "Failed"


class AuditEvent(models.Model):
    actor_kind = models.CharField(max_length=32)
    actor_id = models.CharField(max_length=128)
    action = models.CharField(max_length=96)
    target_type = models.CharField(max_length=96)
    target_id = models.CharField(max_length=128)
    reason = models.TextField(blank=True)
    result = models.CharField(max_length=32, choices=AuditResult.choices, default=AuditResult.SUCCESS)
    request_id = models.CharField(max_length=128)
    source_surface = models.CharField(max_length=64, default="admin_graphql")
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["actor_id", "created_at"]),
            models.Index(fields=["target_type", "target_id", "created_at"]),
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["request_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action}:{self.target_type}:{self.target_id}"
