"""Celery tasks for transactional email.

Tasks take an **opaque token string**, never a user object: task arguments are
serialized onto Redis, and a queued message is not a place to leave a user record.
Idempotent — CELERY_TASK_ACKS_LATE means a crashed worker redelivers, and sending the
same verification email twice is harmless.
"""

from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def _send(subject: str, to: str, html: str, text: str) -> None:
    message = EmailMultiAlternatives(
        subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=[to]
    )
    message.attach_alternative(html, "text/html")
    message.send()


@shared_task(name="accounts.send_verification_email")
def send_verification_email_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_verification

    url = f"{settings.FRONTEND_BASE_URL}/verify?token={raw_token}"
    html, text = render_verification(url)
    _send("Verify your SelahCue email address", email, html, text)


@shared_task(name="accounts.send_password_reset")
def send_password_reset_task(email: str, raw_token: str) -> None:
    from selahcue_api.apps.accounts.email import render_password_reset

    url = f"{settings.FRONTEND_BASE_URL}/reset?token={raw_token}"
    html, text = render_password_reset(url)
    _send("Reset your SelahCue password", email, html, text)


@shared_task(name="accounts.send_account_exists")
def send_account_exists_task(email: str) -> None:
    from selahcue_api.apps.accounts.email import render_account_exists

    html, text = render_account_exists()
    _send("Someone tried to sign up with your SelahCue address", email, html, text)
