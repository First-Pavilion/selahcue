# Import the Celery app on package import so `-A selahcue_api` resolves and
# @shared_task decorators bind to it.
from selahcue_api.celery import app as celery_app

__all__ = ("celery_app", "__version__")

__version__ = "0.1.0"
