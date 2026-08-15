from django.apps import AppConfig


class SelahCueAccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    label = "selahcue_accounts"
    name = "selahcue_api.apps.accounts"
    verbose_name = "SelahCue Customer Accounts"

    def ready(self):
        # Swap the no-op seam for the Celery-backed sender once apps are loaded. Imported
        # here rather than at module scope because email.py reaches models and settings.
        from selahcue_api.apps.accounts.email import CeleryEmailSender
        from selahcue_api.apps.accounts.services import set_email_sender

        set_email_sender(CeleryEmailSender())

        # Importing the module is what registers the check with the framework.
        from selahcue_api.apps.accounts import checks  # noqa: F401
