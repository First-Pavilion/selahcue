"""Failed password-reset confirms against a REAL, UNREACHABLE Redis (86ak5r2pt).

The test suite simulates a limiter outage with a broken store object. This script uses the real
thing: the Django cache is pointed at a port nothing listens on, so every limiter call fails with
a genuine connection error, exactly as in a Redis outage. It posts failed confirms through the
real GraphQL endpoint and reports how many audit rows were written, what the responses were, and
which warnings the services logger emitted.

Run (from the repository root; needs `make api-install` once; no network, no Redis):

    cd implementation/api && env -i PATH="$PATH" HOME="$HOME" TMPDIR="$TMPDIR" \
      CACHE_URL=redis://127.0.0.1:1 SQL_DATABASE=:memory: \
      DJANGO_SETTINGS_MODULE=selahcue_api.settings \
      .venv-api-check/bin/python ../../docs/delivery/goals/86ak5r2pt-evidence/real_redis_outage.py

Port 1 refuses connections immediately; a stalled Redis (accepts, never answers) costs about one
socket timeout per limiter call instead and is covered by tests/test_cache_socket_timeouts.py.
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


def main(count):
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
        for n in range(count):
            response = client.post(
                "/graphql/account",
                data=json.dumps(
                    {"query": CONFIRM, "variables": {"input": {"token": f"SC-PRS-guess-{n}", "newPassword": "a-perfectly-good-passphrase"}}}
                ),
                content_type="application/json",
                REMOTE_ADDR="203.0.113.5",
            )
            code = (json.loads(response.content).get("errors") or [{}])[0].get("extensions", {}).get("code")
            codes[code] = codes.get(code, 0) + 1
        rows = AuditEvent.objects.filter(action=services.RESET_CONFIRM_FAILED_ACTION).count()
        print(f"failed confirms posted: {count}")
        print(f"response codes: {codes}")
        print(f"audit rows written: {rows}")
        print(f"process-local ceiling per worker: {services.RESET_CONFIRM_TRACE_DEGRADED_CEILING}")
        for name, message in capture.messages:
            print(f"WARNING {name}: {message[:160]}")
    finally:
        runner.teardown_databases(old_config)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 25)
