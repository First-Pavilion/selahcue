"""Expiry sweeps. Pure hygiene — expiry is already enforced at read time, so this only
stops unbounded table growth. Bounded batches; safe to re-run.

Deliberately holds no `@shared_task`: Celery's `autodiscover_tasks()` only imports
`tasks.py` from each installed app, so a task defined here would be scheduled by beat and
never registered by the worker. The task wrapper lives in `accounts/tasks.py`; this module
stays importable and testable without Celery in the picture.
"""

from __future__ import annotations

from django.utils import timezone

from selahcue_api.apps.accounts.models import CredentialToken, CustomerSession


def sweep_expired_credentials(batch_size: int = 1000) -> dict[str, int]:
    """Delete expired account sessions and credential tokens, at most `batch_size` of each.

    Idempotent: a redelivered run (CELERY_TASK_ACKS_LATE) simply finds nothing expired and
    returns zeros. The id-list-then-delete shape is what keeps the delete bounded — a bare
    `filter(expires_at__lt=now).delete()` cannot be sliced and would scan the whole table.
    """
    now = timezone.now()

    # `delete()` returns (TOTAL rows removed, {model label: count}). Reporting the total under
    # a per-model label is only correct while nothing cascades off these tables; the first
    # model to FK either with on_delete=CASCADE would silently inflate these numbers, and the
    # job's own output is the only signal anyone watches. Read the per-label counts instead.
    session_ids = list(
        CustomerSession.objects.filter(expires_at__lt=now)
        .order_by("id")
        .values_list("id", flat=True)[:batch_size]
    )
    _, session_counts = CustomerSession.objects.filter(id__in=session_ids).delete()

    token_ids = list(
        CredentialToken.objects.filter(expires_at__lt=now)
        .order_by("id")
        .values_list("id", flat=True)[:batch_size]
    )
    _, token_counts = CredentialToken.objects.filter(id__in=token_ids).delete()

    return {
        "sessions": session_counts.get(CustomerSession._meta.label, 0),
        "credential_tokens": token_counts.get(CredentialToken._meta.label, 0),
    }
