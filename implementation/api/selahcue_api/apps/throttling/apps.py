from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class SelahCueThrottlingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_throttling"
    name = "selahcue_api.apps.throttling"
    verbose_name = "SelahCue Throttling"

    def ready(self):
        # Importing the module is what registers the check with the framework.
        from selahcue_api.apps.throttling import checks

        errors = checks.cloud_cache_key_prefix_is_safe()
        if errors:
            raise ImproperlyConfigured(errors[0].msg)
