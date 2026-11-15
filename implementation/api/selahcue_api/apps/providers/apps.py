from django.apps import AppConfig


class SelahCueProvidersConfig(AppConfig):
    name = "selahcue_api.apps.providers"
    label = "selahcue_providers"

    def ready(self):
        from django.core.checks import register

        from .checks import check_provider_settings

        register(check_provider_settings)
