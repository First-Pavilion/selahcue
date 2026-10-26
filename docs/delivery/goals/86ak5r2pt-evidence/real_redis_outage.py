"""Failed password-reset confirms against a REAL, UNREACHABLE Redis (86ak5r2pt).

The test suite simulates a limiter outage with a broken store object. This script uses the real
thing: the Django cache is pointed at a port nothing listens on, so every limiter call fails with
a genuine connection error, exactly as in a Redis outage. It posts failed confirms through the
real GraphQL endpoint and reports how many audit rows were written, what the responses were, and
which warnings the services logger emitted.

Two scenarios:

- `unknown` (default): unknown tokens. They name no account, so they spend the SHARED per-worker
  outage ceiling (200 an hour).
- `named`: weak passwords behind one account's live reset link. They name an account, so they
  spend that account's own per-worker outage allowance (30 an hour).

Run (from the repository root; needs `make api-install` once; no network, no Redis):

    cd implementation/api && env -i PATH="$PATH" HOME="$HOME" TMPDIR="$TMPDIR" \
      CACHE_URL=redis://127.0.0.1:1 SQL_DATABASE=:memory: \
      DJANGO_SETTINGS_MODULE=selahcue_api.settings \
      .venv-api-check/bin/python ../../docs/delivery/goals/86ak5r2pt-evidence/real_redis_outage.py \
      [COUNT] [unknown|named]

Port 1 refuses connections immediately; a stalled Redis (accepts, never answers) costs about one
socket timeout per limiter call instead and is covered by tests/test_cache_socket_timeouts.py.

Imports of project modules are inside functions and after `django.setup()` on purpose: models and
settings-dependent modules cannot be imported before Django is configured.
"""

import json
import logging
import sys

import django

django.setup()

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

assert settings.CACHES["default"]["BACKEND"].endswith("RedisCache"), "CACHE_URL was not honoured"

CONFIRM = """
    mutation Confirm($input: ConfirmPasswordResetInput!) {
      confirmPasswordReset(input: $input) { reset }
    }
"""


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append((record.name, record.getMessage()))


def post_confirm(client, token, password):
    response = client.post(
        "/graphql/account",
        data=json.dumps({"query": CONFIRM, "variables": {"input": {"token": token, "newPassword": password}}}),
        content_type="application/json",
        REMOTE_ADDR="203.0.113.5",
    )
    return (json.loads(response.content).get("errors") or [{}])[0].get("extensions", {}).get("code")


def live_reset_token(services):
    """A verified account with a live reset link, made through the services (nothing here needs the
    cache to be reachable: every budget fails open). Returns (user id, raw token)."""

    class Sender(services.EmailSender):
        def __init__(self):
            self.verify_tokens, self.reset_tokens = [], []

        def send_email_verification(self, user, raw_token):
            self.verify_tokens.append(raw_token)

        def send_password_reset(self, user, raw_token):
            self.reset_tokens.append(raw_token)

    sender = Sender()
    services.set_email_sender(sender)
    email = "demo@example.org"
    services.register_customer_user(
        services.RegisterCustomerUserData(
            idempotency_key="redis-demo-0001",
            email=email,
            password="correct-horse-battery-1",
            org_name="Demo Chapel",
            country="NG",
        )
    )
    services.verify_email(sender.verify_tokens[-1], client_ip="203.0.113.9")
    services.request_password_reset(email, client_ip="203.0.113.9")
    from selahcue_api.apps.accounts.models import CustomerUser

    return CustomerUser.objects.get(email=email).id, sender.reset_tokens[-1]


def main(count, scenario):
    setup_test_environment()
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()
    try:
        from selahcue_api.apps.accounts import services
        from selahcue_api.apps.audit.models import AuditEvent

        capture = Capture()
        logging.getLogger("selahcue_api").addHandler(capture)
        client = Client()
        codes = {}
        if scenario == "named":
            user_id, token = live_reset_token(services)
            attempts = [(token, "short")] * count  # too short: PASSWORD_INVALID, the link stays live
            ceiling = services.RESET_CONFIRM_TRACE_ACCOUNT_DEGRADED_CEILING
        else:
            user_id = None
            attempts = [(f"SC-PRS-guess-{n}", "a-perfectly-good-passphrase") for n in range(count)]
            ceiling = services.RESET_CONFIRM_TRACE_DEGRADED_CEILING
        for token, password in attempts:
            code = post_confirm(client, token, password)
            codes[code] = codes.get(code, 0) + 1
        rows = AuditEvent.objects.filter(action=services.RESET_CONFIRM_FAILED_ACTION)
        if user_id is not None:
            rows = rows.filter(target_type="customer_user", target_id=str(user_id))
        print(f"scenario: {scenario}")
        print(f"failed confirms posted: {count}")
        print(f"response codes: {codes}")
        print(f"audit rows written: {rows.count()}")
        print(f"process-local ceiling per worker ({'per account' if user_id is not None else 'shared'}): {ceiling}")
        for name, message in capture.messages:
            print(f"WARNING {name}: {message[:200]}")
    finally:
        runner.teardown_databases(old_config)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 25, sys.argv[2] if len(sys.argv) > 2 else "unknown")
