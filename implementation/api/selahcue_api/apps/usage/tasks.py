"""Fixed Celery names and argument/role boundaries for metadata work."""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import DatabaseError

from .observation_contracts import UsageFailureCode as Code, UsageRejected
from .usage_tasks import (
    _parse_uuid, claim_work, finish_work, publish_work, require_usage_role, run_claimed, sweep_retention, sweep_usage,
)

_TASK = dict(bind=True, ignore_result=True, acks_late=True, reject_on_worker_lost=True, max_retries=0)


def _run(task, work_id, kind):
    try:
        require_usage_role(maintenance=kind == "RETENTION")
        identifier = _parse_uuid(work_id)
        task_id = _parse_uuid(task.request.id)
    except (UsageRejected, ValueError):
        return
    try:
        work = claim_work(identifier, task_id, kind, (task.request.delivery_info or {}).get("routing_key"))
        if work is not None:
            try:
                run_claimed(work)
            except SoftTimeLimitExceeded:
                finish_work(work.pk, work.lease_id, pending=True, code=Code.TASK_BUDGET)
            except UsageRejected as error:
                finish_work(work.pk, work.lease_id, pending=True, code=error.code)
    except DatabaseError:
        # Uncertain finalization remains fenced by the durable claim and lease.
        # Never emit database exceptions containing page cursors or metadata.
        return


@shared_task(name="usage.scan", soft_time_limit=110, time_limit=120, **_TASK)
def scan(task, *, work_id):
    _run(task, work_id, "SCAN")


@shared_task(name="usage.reconcile", soft_time_limit=110, time_limit=120, **_TASK)
def reconcile(task, *, work_id):
    _run(task, work_id, "RECONCILE")


@shared_task(name="usage.attribute", soft_time_limit=110, time_limit=120, **_TASK)
def attribute(task, *, work_id):
    _run(task, work_id, "ATTRIBUTE")


@shared_task(name="usage.recover_mint", soft_time_limit=110, time_limit=120, **_TASK)
def recover_mint(task, *, work_id):
    _run(task, work_id, "MINT_RECOVERY")


@shared_task(name="usage.retain", soft_time_limit=10, time_limit=12, **_TASK)
def retain(task, *, work_id):
    _run(task, work_id, "RETENTION")


def _publish(task, work_id, *, maintenance=False):
    try:
        require_usage_role(maintenance=maintenance)
        identifier = _parse_uuid(work_id)
    except (UsageRejected, ValueError):
        return
    try:
        publish_work(identifier, app=task.app, maintenance=maintenance)
    except DatabaseError:
        return


@shared_task(name="usage.publish", soft_time_limit=8, time_limit=10, **_TASK)
def publish(task, *, work_id):
    _publish(task, work_id)


@shared_task(name="usage.publish_retention", soft_time_limit=8, time_limit=10, **_TASK)
def publish_retention(task, *, work_id):
    _publish(task, work_id, maintenance=True)


@shared_task(name="usage.sweep", soft_time_limit=10, time_limit=12, **_TASK)
def sweep(task):
    try:
        sweep_usage()
    except (UsageRejected, SoftTimeLimitExceeded, DatabaseError):
        return


@shared_task(name="usage.retention_sweep", soft_time_limit=10, time_limit=12, **_TASK)
def retention_sweep(task):
    try:
        sweep_retention()
    except (UsageRejected, SoftTimeLimitExceeded, DatabaseError):
        return
