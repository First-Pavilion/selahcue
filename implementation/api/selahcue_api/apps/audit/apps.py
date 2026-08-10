from django.apps import AppConfig


class SelahCueAuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_audit"
    name = "selahcue_api.apps.audit"
    verbose_name = "SelahCue Audit And Outbox"
