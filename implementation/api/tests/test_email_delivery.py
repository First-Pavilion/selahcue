"""Transactional email rendering + dispatch.

Copy comes from docs/design/TRANSACTIONAL-EMAIL-spec.md. The account-exists assertions
enforce a security property, not a style preference.
"""

import pytest
from django.core import mail

from selahcue_api.apps.accounts.email import (
    render_account_exists,
    render_password_reset,
    render_verification,
)

pytestmark = pytest.mark.django_db


def test_verification_renders_both_parts_with_the_link():
    html, txt = render_verification("https://app.selahcue.com/verify?token=abc")
    assert "https://app.selahcue.com/verify?token=abc" in html
    assert "https://app.selahcue.com/verify?token=abc" in txt
    assert "24 hours" in html and "24 hours" in txt


def test_password_reset_states_the_one_hour_expiry():
    html, txt = render_password_reset("https://app.selahcue.com/reset?token=abc")
    assert "1 hour" in html and "1 hour" in txt
    assert "https://app.selahcue.com/reset?token=abc" in html


def test_account_exists_contains_no_url_at_all():
    """Security property. Signup returns an identical response whether or not the
    address is registered, so this email reaching the real owner is the ONLY signal an
    account exists. A link would hand that signal to an attacker probing addresses."""
    html, txt = render_account_exists()
    for part in (html, txt):
        assert "http://" not in part
        assert "https://" not in part
        assert "token" not in part.lower()


def test_sending_produces_html_and_text_alternatives():
    from selahcue_api.apps.accounts.tasks import send_verification_email_task

    send_verification_email_task("church@example.test", "tok-123")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["church@example.test"]
    assert message.body  # plain text
    assert any(ct == "text/html" for _, ct in message.alternatives)


def test_task_takes_an_opaque_token_not_a_user_object():
    """Tasks are serialized onto Redis. A queued message is not a place to leave a user
    record, and a token string is the minimum the task needs."""
    import inspect

    from selahcue_api.apps.accounts.tasks import send_verification_email_task

    params = list(inspect.signature(send_verification_email_task).parameters)
    assert params == ["email", "raw_token"]


def test_enqueue_failure_does_not_break_the_caller(monkeypatch):
    """Signup succeeding with a delayed email is recoverable; signup 500ing because
    Redis blinked is not."""
    from selahcue_api.apps.accounts import email as email_module

    def boom(*a, **k):
        raise RuntimeError("broker down")

    monkeypatch.setattr(email_module.send_verification_email_task, "delay", boom)
    sender = email_module.CeleryEmailSender()

    class FakeUser:
        email = "church@example.test"

    sender.send_email_verification(FakeUser(), "tok")  # must not raise


# --- dispatch wiring ------------------------------------------------------
class FakeUser:
    email = "church@example.test"


def test_verification_dispatch_runs_the_verification_task_with_email_then_token(settings):
    """The `CeleryEmailSender` happy path was untested: wiring `send_email_verification` to
    the RESET task, or swapping `(email, raw_token)` to `(raw_token, email)`, was invisible.
    Running the task eagerly proves the whole chain — right task, right argument order, right
    recipient, right URL."""
    from selahcue_api.apps.accounts import email as email_module
    from selahcue_api.celery import app as celery_app

    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        mail.outbox.clear()
        email_module.CeleryEmailSender().send_email_verification(FakeUser(), "raw-verify-token")
    finally:
        celery_app.conf.task_always_eager = False
        celery_app.conf.task_eager_propagates = False

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["church@example.test"], "the email argument must be the recipient"
    assert "/verify?token=raw-verify-token" in message.body, (
        "wrong task or swapped arguments: the token must land in the VERIFY url"
    )
    assert "/reset?token=" not in message.body


def test_reset_dispatch_runs_the_reset_task(settings):
    from selahcue_api.apps.accounts import email as email_module
    from selahcue_api.celery import app as celery_app

    settings.CELERY_TASK_ALWAYS_EAGER = True
    celery_app.conf.task_always_eager = True
    try:
        mail.outbox.clear()
        email_module.CeleryEmailSender().send_password_reset(FakeUser(), "raw-reset-token")
    finally:
        celery_app.conf.task_always_eager = False

    assert len(mail.outbox) == 1
    assert "/reset?token=raw-reset-token" in mail.outbox[0].body
    assert "/verify?token=" not in mail.outbox[0].body


def test_task_arguments_are_redacted_in_the_queued_message(monkeypatch):
    """Celery stamps `saferepr(args)` into the message headers, and the worker prints it on
    every `Received task: ...` line at `--loglevel=info` — which is what compose runs. Without
    an explicit repr the raw verification/reset token is written to worker logs in clear."""
    from selahcue_api.apps.accounts.tasks import send_verification_email_task

    captured = {}

    def fake_send_task(name, args=None, kwargs=None, **options):
        captured.update(name=name, args=args, kwargs=kwargs, options=options)
        return None

    monkeypatch.setattr(send_verification_email_task.app, "send_task", fake_send_task)
    send_verification_email_task.delay("church@example.test", "super-secret-raw-token")

    # The worker still receives the real arguments — redaction is about the log, not the payload.
    assert captured["args"] == ("church@example.test", "super-secret-raw-token")
    argsrepr = captured["options"]["argsrepr"]
    assert "super-secret-raw-token" not in argsrepr, argsrepr
    assert "church@example.test" not in argsrepr, argsrepr
    assert captured["options"]["kwargsrepr"] == "{}"
