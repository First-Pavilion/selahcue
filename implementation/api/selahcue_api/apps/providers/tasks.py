"""Celery autodiscovery for the provisioner queue."""
from .provisioning_tasks import (
    inventory_page_task,
    provision_task,
    publish_outbox_task,
    recovery_task,
    sweep_task,
)

__all__ = ["inventory_page_task", "provision_task", "publish_outbox_task", "recovery_task", "sweep_task"]
