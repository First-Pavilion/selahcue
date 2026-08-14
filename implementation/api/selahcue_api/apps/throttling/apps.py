from django.apps import AppConfig


class SelahCueThrottlingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_throttling"
    name = "selahcue_api.apps.throttling"
    verbose_name = "SelahCue Throttling"
