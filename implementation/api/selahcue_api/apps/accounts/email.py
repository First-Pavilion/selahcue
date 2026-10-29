"""Rendering + dispatch for the three transactional emails.

Design: docs/design/TRANSACTIONAL-EMAIL-spec.md (Figma page 719:132). The copy there is
authoritative — change it there first, not here.
"""

from __future__ import annotations

import logging
import threading
import time

from django.template.loader import render_to_string

from selahcue_api.apps.accounts.models import CustomerUser
from selahcue_api.apps.accounts.services import EmailSender
from selahcue_api.apps.accounts.tasks import (
    send_account_exists_task,
    send_password_reset_task,
    send_verification_email_task,
)

logger = logging.getLogger(__name__)
_publish_failure_lock = threading.Lock()
_last_publish_failure_log = float("-inf")


def _report_publish_failure(task_name: str, error: Exception) -> None:
    """One diagnostic per process per minute; neither exception text nor traceback is safe.

    A failed write may have reached Redis before its reply was lost. Report an unknown outcome,
    never assert that nothing was sent. Keep state constant-sized during an outage.
    """
    global _last_publish_failure_log
    now = time.monotonic()
    with _publish_failure_lock:
        if now - _last_publish_failure_log < 60:
            return
        _last_publish_failure_log = now
    logger.error(
        "could not confirm enqueue %s (%s); email delivery unconfirmed",
        task_name,
        type(error).__name__,
    )


def render_verification(verify_url: str) -> tuple[str, str]:
    ctx = {"verify_url": verify_url}
    return (
        render_to_string("email/verify_email.html", ctx),
        render_to_string("email/verify_email.txt", ctx),
    )


def render_password_reset(reset_url: str) -> tuple[str, str]:
    ctx = {"reset_url": reset_url}
    return (
        render_to_string("email/password_reset.html", ctx),
        render_to_string("email/password_reset.txt", ctx),
    )


def render_account_exists() -> tuple[str, str]:
    # No context: this email deliberately carries no token and no link.
    return (
        render_to_string("email/account_exists.html", {}),
        render_to_string("email/account_exists.txt", {}),
    )


class CeleryEmailSender(EmailSender):
    """Dispatches to the worker. Enqueue failure is logged, never raised: signup
    succeeding without confirmed delivery is recoverable through resend; signup 500ing
    because the broker blinked is not."""

    @staticmethod
    def _dispatch(task, *args) -> None:
        try:
            # Do not wait for a pooled producer, reconnect, or retry a possibly delivered write
            # on this request thread. Scope the connection retry choice to email publishing;
            # workers and unrelated task producers retain their own recovery policies.
            with task.app.connection_for_write(transport_options={"max_retries": 0}) as connection:
                # These fire-and-forget callers consume no task result. Without this per-send
                # flag, RedisBackend subscribes synchronously BEFORE the bounded broker send.
                # Keep global/task defaults and other producers' result policy unchanged.
                task.apply_async(args=args, connection=connection, retry=False, ignore_result=True)
        except Exception as error:
            _report_publish_failure(task.name, error)

    def send_email_verification(self, user: CustomerUser, raw_token: str) -> None:
        self._dispatch(send_verification_email_task, user.email, raw_token)

    def send_password_reset(self, user: CustomerUser, raw_token: str) -> None:
        self._dispatch(send_password_reset_task, user.email, raw_token)

    def send_account_exists(self, email: str) -> None:
        self._dispatch(send_account_exists_task, email)
