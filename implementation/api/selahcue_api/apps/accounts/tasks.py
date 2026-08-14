"""Celery tasks for the accounts app: transactional email, plus the nightly expiry sweep.

Email tasks take an **opaque token string**, never a user object: task arguments are
serialized onto Redis, and a queued message is not a place to leave a user record.
Idempotent — CELERY_TASK_ACKS_LATE means a crashed worker redelivers, and sending the
same verification email twice is harmless.

This module is the app's ONLY autodiscovered one: `autodiscover_tasks()` imports
`<app>.tasks` and nothing else. Task bodies may live elsewhere (the sweep's logic is in
`maintenance.py`), but the `@shared_task` wrapper has to be here or the worker never
registers the name beat is dispatching.
"""

from __future__ import annotations

from celery import Task, shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


class RedactedArgsTask(Task):
    """A task whose arguments never appear in the broker message or the worker log.

    Celery derives `argsrepr`/`kwargsrepr` from `saferepr(args)` when the caller does not
    supply them, and stamps that into the message headers. The worker prints it on every
    `Received task: ...` line at `--loglevel=info` (what compose runs) and in
    `repr(request)` on failure — so a raw verification or reset token in `args` lands in
    worker logs, where it is as good as the credential itself. Overriding the repr keeps the
    task's real arguments (the worker still gets them) while logging nothing about them.

    Set on the task, not at the call site, so a `.delay()` from a shell or a future caller
    is redacted too.
    """

    redacted_argsrepr = "(<redacted>)"

    def apply_async(self, args=None, kwargs=None, **options):
        options.setdefault("argsrepr", self.redacted_argsrepr)
        options.setdefault("kwargsrepr", "{}")
        return super().apply_async(args, kwargs, **options)


def _send(subject: str, to: str, html: str, text: str) -> None:
    message = EmailMultiAlternatives(
        subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=[to]
    )
    message.attach_alternative(html, "text/html")
    message.send()


@shared_task(name="accounts.send_verification_email", base=RedactedArgsTask)
def send_verification_email_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_verification

    url = f"{settings.FRONTEND_BASE_URL}/verify?token={raw_token}"
    html, text = render_verification(url)
    _send("Verify your SelahCue email address", email, html, text)


@shared_task(name="accounts.send_password_reset", base=RedactedArgsTask)
def send_password_reset_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_password_reset

    url = f"{settings.FRONTEND_BASE_URL}/reset?token={raw_token}"
    html, text = render_password_reset(url)
    _send("Reset your SelahCue password", email, html, text)


@shared_task(name="accounts.send_account_exists", base=RedactedArgsTask)
def send_account_exists_task(email: str) -> None:
    from selahcue_api.apps.accounts.email import render_account_exists

    html, text = render_account_exists()
    _send("Someone tried to sign up with your SelahCue address", email, html, text)


@shared_task(name="accounts.sweep_expired_credentials")
def sweep_expired_credentials_task() -> dict[str, int]:
    """Nightly row hygiene. The logic lives in `maintenance.py`; this wrapper exists here
    because `tasks.py` is the only module Celery autodiscovers."""
    from selahcue_api.apps.accounts.maintenance import sweep_expired_credentials

    return sweep_expired_credentials()
