"""Celery application for the SelahCue Platform API.

Entry point for `celery -A selahcue_api worker` and `celery -A selahcue_api beat`.
Configuration lives in Django settings under the `CELERY_` namespace, so there is one
place to change broker/backend/timezone.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "selahcue_api.settings")

app = Celery("selahcue_api")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
