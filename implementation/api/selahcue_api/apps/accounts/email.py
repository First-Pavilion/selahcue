"""Rendering + dispatch for the three transactional emails.

Design: docs/design/TRANSACTIONAL-EMAIL-spec.md (Figma page 719:132). The copy there is
authoritative — change it there first, not here.
"""

from __future__ import annotations

import logging

from django.template.loader import render_to_string

from selahcue_api.apps.accounts.models import CustomerUser
from selahcue_api.apps.accounts.services import EmailSender
from selahcue_api.apps.accounts.tasks import (
    send_account_exists_task,
    send_password_reset_task,
    send_verification_email_task,
)

logger = logging.getLogger(__name__)


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
    succeeding with a delayed email is recoverable; signup 500ing because the broker
    blinked is not."""

    @staticmethod
    def _dispatch(task, *args) -> None:
        try:
            task.delay(*args)
        except Exception:
            logger.exception("could not enqueue %s; email not sent", task.name)

    def send_email_verification(self, user: CustomerUser, raw_token: str) -> None:
        self._dispatch(send_verification_email_task, user.email, raw_token)

    def send_password_reset(self, user: CustomerUser, raw_token: str) -> None:
        self._dispatch(send_password_reset_task, user.email, raw_token)

    def send_account_exists(self, email: str) -> None:
        self._dispatch(send_account_exists_task, email)
