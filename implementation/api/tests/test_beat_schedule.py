"""Beat schedules maintenance by default and only dispatches provider work by opt-in."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_deployment_guards import _environment


# The global catalogue snapshot fixture needs the test database even for these boot probes.
pytestmark = pytest.mark.django_db

API_ROOT = Path(__file__).resolve().parent.parent
PROVISIONING = "SELAHCUE_BEAT_PROVIDER_PROVISIONING_ENABLED"
USAGE = "SELAHCUE_BEAT_PROVIDER_USAGE_ENABLED"

_SCHEDULE_PROBE = """
import json
import sys

from celery.schedules import crontab
from selahcue_api import celery_app

expected = {
    "sweep-usage-retention": {
        "task": "usage.retention_sweep",
        "schedule": 60,
        "options": {"queue": "celery"},
    },
    "cascade-license-revocations": {
        "task": "devices.cascade_license_revocations",
        "schedule": crontab(minute=0),
    },
    "sweep-expired-credentials": {
        "task": "accounts.sweep_expired_credentials",
        "schedule": crontab(hour=3, minute=30),
    },
}
provider_entries = {
    "provisioning": ("sweep-provider-provisioning", "providers.sweep", 5, "provider_provisioning"),
    "usage": ("sweep-provider-usage", "usage.sweep", 60, "provider_usage"),
}
for role in json.loads(sys.argv[1]):
    name, task, seconds, queue = provider_entries[role]
    expected[name] = {"task": task, "schedule": seconds, "options": {"queue": queue}}

actual = celery_app.conf.beat_schedule
assert actual == expected, f"expected {expected!r}, got {actual!r}"
routes = celery_app.conf.task_routes
assert routes["providers.sweep"] == {"queue": "provider_provisioning"}
assert routes["usage.sweep"] == {"queue": "provider_usage"}
assert routes["usage.retention_sweep"] == {"queue": "celery"}
"""

_MAINTENANCE_BEAT_PROBE = """
import django
from celery.beat import Scheduler, Service
from selahcue_api import celery_app
from selahcue_api.apps.providers.configuration import get_provider_configuration

django.setup()
celery_app.loader.import_default_modules()

scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
assert {"providers.sweep", "usage.sweep"} <= scheduled
assert scheduled <= celery_app.tasks.keys(), scheduled - celery_app.tasks.keys()

class OneTick(Scheduler):
    def tick(self):
        config = get_provider_configuration(required_role="maintenance")
        assert config.policy is None and config.keyring is None
        print("maintenance tick")
        raise SystemExit(0)

Service(app=celery_app, scheduler_cls=OneTick).start()
"""


def _probe(code, *args, **overrides):
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=API_ROOT,
        env=_environment({
            "CELERY_BROKER_URL": "memory://",
            "CELERY_RESULT_BACKEND": "cache+memory://",
            **overrides,
        }),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


@pytest.mark.parametrize(("provisioning", "usage", "expected"), [
    pytest.param(None, None, [], id="omitted"),
    pytest.param("", "", [], id="empty"),
    pytest.param("0", "off", [], id="both-disabled"),
    pytest.param(" TrUe ", "no", ["provisioning"], id="provisioning-only"),
    pytest.param("false", "1", ["usage"], id="usage-only"),
    pytest.param("yEs", " ON ", ["provisioning", "usage"], id="both-enabled"),
])
def test_provider_schedules_require_their_own_opt_in(provisioning, usage, expected):
    result = _probe(_SCHEDULE_PROBE, json.dumps(expected), **{PROVISIONING: provisioning, USAGE: usage})
    assert result.returncode == 0, result.stderr


def test_public_provider_flags_leave_beat_maintenance_only():
    result = _probe(
        _SCHEDULE_PROBE, "[]",
        SELAHCUE_CLOUD_STT_ENABLED="on",
        SELAHCUE_CLOUD_NOTES_ENABLED="on",
        SELAHCUE_PROVIDER_PROVISIONING_ENABLED="on",
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("setting", [PROVISIONING, USAGE])
@pytest.mark.parametrize("value", ["invalid-synthetic-value", "  "])
def test_invalid_scheduler_flag_refuses_settings_without_echoing_value(setting, value):
    result = _probe(
        "from selahcue_api import celery_app; print(celery_app.conf.beat_schedule)",
        **{setting: value},
    )
    assert result.returncode != 0
    diagnostic = f"django.core.exceptions.ImproperlyConfigured: PCFG_SCHEMA_INVALID ({setting})"
    assert result.stderr.rstrip().endswith(diagnostic), result.stderr
    if value.strip():
        assert value not in result.stderr


def test_maintenance_beat_with_opt_ins_uses_no_provider_mounts():
    result = _probe(
        _MAINTENANCE_BEAT_PROBE,
        **{PROVISIONING: "true", USAGE: "true"},
        SELAHCUE_PROVIDER_PROCESS_ROLE="maintenance",
        SELAHCUE_PROVIDER_KEYRING_FILE="/nonexistent/synthetic-keyring",
        SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE="/nonexistent/synthetic-usage-credentials",
        SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE="/nonexistent/synthetic-provisioning-credentials",
        SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE="/nonexistent/synthetic-policy",
    )
    assert result.returncode == 0, result.stderr
    assert "maintenance tick" in result.stdout
