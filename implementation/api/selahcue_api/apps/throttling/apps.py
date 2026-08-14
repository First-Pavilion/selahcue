from django.apps import AppConfig


class SelahCueThrottlingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_throttling"
    name = "selahcue_api.apps.throttling"
    verbose_name = "SelahCue Throttling"

    def ready(self):
        # Importing the module is what registers the check with the framework.
        from selahcue_api.apps.throttling import checks  # noqa: F401
