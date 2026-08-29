from django.apps import AppConfig


class SelahCueCatalogueConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_catalogue"
    name = "selahcue_api.apps.catalogue"
    verbose_name = "SelahCue Product Catalogue"

    def ready(self):
        # Importing at module scope would touch models before the app registry is ready.
        from selahcue_api.apps.catalogue.signals import connect_catalogue_signals

        connect_catalogue_signals()
