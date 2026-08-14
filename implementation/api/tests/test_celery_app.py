"""The Celery app must be importable and configured from Django settings, so that
`celery -A selahcue_api worker` resolves without a running broker."""

from django.conf import settings


def test_celery_app_is_exported_from_the_package():
    from selahcue_api import celery_app

    assert celery_app is not None
    assert celery_app.main == "selahcue_api"


def test_broker_and_backend_come_from_settings():
    from selahcue_api import celery_app

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_side_effecting_defaults_are_set():
    """acks_late + prefetch 1: these tasks send email and revoke tokens. Losing one to a
    worker crash is worse than running one twice, and every task is idempotent."""
    from selahcue_api import celery_app

    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
