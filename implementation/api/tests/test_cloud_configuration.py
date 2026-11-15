"""Provider startup refuses invalid roles before serving or contacting a broker."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from provider_helpers import cold_provider_cache, policy_rows, provider_mounts, write_mount
from test_deployment_guards import _environment

from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.configuration import get_provider_configuration, load_provider_configuration
from selahcue_api.apps.providers.contracts import ProviderConfigurationError

# The catalogue's autouse snapshot fixture requires database setup even for these boot checks.
pytestmark = pytest.mark.django_db



def run(*args, **values):
    return subprocess.run(
        [sys.executable, *args], env=_environment(values), check=False,
        capture_output=True, text=True, timeout=15,
    )


def test_web_refuses_unqualified_notes():
    result = run("-c", "import selahcue_api.wsgi", SELAHCUE_PROVIDER_PROCESS_ROLE="web",
                 SELAHCUE_CLOUD_NOTES_ENABLED="true")
    assert result.returncode != 0
    assert "PCFG_NOTES_RUNTIME_UNAVAILABLE" in result.stderr


def test_celery_refuses_wrong_queue_before_mounts_or_broker():
    result = run("-m", "celery", "-A", "selahcue_api", "worker", "--pool=solo", "-Q", "celery",
                 SELAHCUE_PROVIDER_PROCESS_ROLE="usage", CELERY_BROKER_URL="memory://")
    assert result.returncode == 78
    assert "PCFG_QUEUE_MISMATCH" in result.stderr


@pytest.mark.parametrize("entry", ["wsgi", "asgi"])
@pytest.mark.parametrize("role", ["maintenance", "web"])
def test_disabled_web_entrypoint_never_opens_provider_files(entry, role):
    result = run(
        "-c", f"from selahcue_api.{entry} import application; assert callable(application)",
        SELAHCUE_PROVIDER_PROCESS_ROLE=role,
        SELAHCUE_PROVIDER_KEYRING_FILE="/nonexistent/synthetic-keyring",
        SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE="/nonexistent/synthetic-usage",
        SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE="/nonexistent/synthetic-provisioner",
        SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE="/nonexistent/synthetic-policy",
    )
    assert result.returncode == 0, result.stderr


def test_ordinary_django_check_does_not_load_mounts():
    result = run("manage.py", "check", SELAHCUE_PROVIDER_PROCESS_ROLE="provisioner",
                 SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE="/nonexistent/synthetic-policy")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("role", ["", " usage ", "web,usage", "WEB"])
def test_role_syntax_rejected_by_check(role):
    result = run("manage.py", "check", SELAHCUE_PROVIDER_PROCESS_ROLE=role)
    assert result.returncode != 0
    assert "PCFG_ROLE_INVALID" in result.stderr


def test_invalid_new_flag_does_not_echo_input():
    result = run("-c", "import selahcue_api.wsgi", SELAHCUE_CLOUD_STT_ENABLED="synthetic-invalid")
    assert result.returncode != 0
    assert "PCFG_SCHEMA_INVALID (SELAHCUE_CLOUD_STT_ENABLED)" in result.stderr
    assert "synthetic-invalid" not in result.stderr


@pytest.mark.parametrize(("role", "queue", "code"), [
    ("usage", "provider_usage", "PCFG_FILE_REQUIRED"),
    ("provisioner", "provider_provisioning", "PCFG_FILE_REQUIRED"),
    ("notes", "notes", "PCFG_NOTES_RUNTIME_UNAVAILABLE"),
    ("web", "celery", "PCFG_ROLE_MISMATCH"),
    ("usage", "provider_usage,celery", "PCFG_QUEUE_MISMATCH"),
])
def test_worker_fatally_refuses_configuration(role, queue, code):
    result = run("-m", "celery", "-A", "selahcue_api", "worker", "--pool=solo", "-Q", queue,
                 SELAHCUE_PROVIDER_PROCESS_ROLE=role, CELERY_BROKER_URL="memory://")
    assert result.returncode == 78, result.stderr
    assert code in result.stderr


def test_embedded_beat_refused_before_mounts():
    result = run("-m", "celery", "-A", "selahcue_api", "worker", "--pool=solo", "-B", "-Q", "provider_usage",
                 SELAHCUE_PROVIDER_PROCESS_ROLE="usage", CELERY_BROKER_URL="memory://")
    assert result.returncode == 78, result.stderr
    assert "PCFG_QUEUE_MISMATCH" in result.stderr


def test_real_beat_refuses_nonmaintenance_role(tmp_path):
    result = run("-m", "celery", "-A", "selahcue_api", "beat", "--schedule", str(tmp_path / "beat"),
                 SELAHCUE_PROVIDER_PROCESS_ROLE="usage", CELERY_BROKER_URL="memory://")
    assert result.returncode == 78, result.stderr
    assert "PCFG_ROLE_MISMATCH" in result.stderr


@pytest.mark.parametrize(("role", "forbidden"), [
    ("web", ["USAGE_CREDENTIALS", "PROVISIONING_CREDENTIALS"]),
    ("usage", ["KEYRING", "PROVISIONING_CREDENTIALS"]),
    ("provisioner", ["USAGE_CREDENTIALS"]),
    ("notes", ["USAGE_CREDENTIALS", "PROVISIONING_CREDENTIALS"]),
    ("maintenance", ["KEYRING", "USAGE_CREDENTIALS", "PROVISIONING_CREDENTIALS", "DEPLOYMENT_POLICY"]),
])
def test_role_never_opens_forbidden_mounts(role, forbidden, settings, monkeypatch, provider_mounts):
    provider_mounts(role, stt=role == "web", capable=role == "web", notes=role != "web",
                    provisioning=role == "usage")
    forbidden_paths = {getattr(settings, f"SELAHCUE_PROVIDER_{name}_FILE") for name in forbidden}
    open_mount = os.open

    def check(path, *args, **kwargs):
        assert path not in forbidden_paths
        return open_mount(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", check)
    config = load_provider_configuration(role)
    assert config.role == role
    assert bool(config.usage_credentials) is (role == "usage")
    assert bool(config.provisioning_credentials) is (role == "provisioner")
    assert (config.keyring is not None) is (role in {"web", "provisioner", "notes"})


def test_parse_is_cached_but_does_not_initialize_runtime(provider_mounts, settings):
    provider_mounts("provisioner")
    config = load_provider_configuration("provisioner")
    Path(settings.SELAHCUE_PROVIDER_KEYRING_FILE).unlink()
    assert load_provider_configuration("provisioner") is config
    with pytest.raises(ProviderConfigurationError, match="PCFG_NOT_INITIALIZED"):
        get_provider_configuration(required_role="provisioner")
    assert initialize_provider_runtime(entrypoint="operator") is config
    assert get_provider_configuration(required_role="provisioner") is config
    with pytest.raises(ProviderConfigurationError, match="PCFG_ROLE_MISMATCH"):
        get_provider_configuration(required_role="usage")


def test_notes_provider_only_inspection_cannot_mark_runtime_ready(provider_mounts):
    provider_mounts("notes")
    assert load_provider_configuration("notes").keyring is not None
    with pytest.raises(ProviderConfigurationError, match="PCFG_NOTES_RUNTIME_UNAVAILABLE"):
        initialize_provider_runtime(entrypoint="celery_worker")
    with pytest.raises(ProviderConfigurationError, match="PCFG_NOT_INITIALIZED"):
        get_provider_configuration(required_role="notes")


def test_create_requested_recovery_only_is_refused_for_provisioner(provider_mounts):
    provider_mounts("provisioner", provisioning=True)
    with pytest.raises(ProviderConfigurationError, match="PCFG_CAPABILITY_UNCONFIGURED"):
        initialize_provider_runtime(entrypoint="operator")


def test_web_refuses_any_incomplete_admitted_parent(provider_mounts, settings, tmp_path):
    provider_mounts("web", stt=True, capable=True)
    policy = policy_rows(capable=True)
    policy["deepgram"].append({"project_id": "synthetic-historical-parent", "unattributed_usage_threshold": "0"})
    settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "extra-policy", policy)
    with pytest.raises(ProviderConfigurationError, match="PCFG_CAPABILITY_UNCONFIGURED"):
        initialize_provider_runtime(entrypoint="asgi")


@pytest.mark.parametrize(("role", "source"), [("usage", "USAGE_CREDENTIALS"),
                                              ("provisioner", "PROVISIONING_CREDENTIALS")])
def test_roles_fail_closed_with_public_flags_off_and_missing_local_mount(role, source, provider_mounts, settings):
    provider_mounts(role)
    setattr(settings, f"SELAHCUE_PROVIDER_{source}_FILE", "")
    with pytest.raises(ProviderConfigurationError, match="PCFG_FILE_REQUIRED"):
        load_provider_configuration(role)


@pytest.mark.parametrize("bad", [
    {"schema_version": True}, {"accepted_at": "2026-02-30T00:00:00Z"},
    {"accepted_at": "2026-11-14T00:00:00+00:00"}, {"accepted_by": "\ud800"},
])
def test_policy_schema_rejects_invalid_receipt(bad, provider_mounts, settings, tmp_path):
    provider_mounts("usage")
    data = policy_rows() | bad
    settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "invalid-policy", data)
    with pytest.raises(ProviderConfigurationError, match="PCFG_SCHEMA_INVALID"):
        load_provider_configuration("usage")


def test_valid_provisioner_scope_does_not_supply_missing_usage_scope(provider_mounts, settings, tmp_path):
    provider_mounts("usage")
    settings.SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE = write_mount(tmp_path, "empty-usage", {
        "schema_version": 1, "deepgram": [], "openai": [],
    })
    with pytest.raises(ProviderConfigurationError, match="PCFG_SCOPE_MISMATCH"):
        load_provider_configuration("usage")


def test_failed_parse_is_not_cached(provider_mounts, settings, tmp_path):
    provider_mounts("provisioner")
    installed = settings.SELAHCUE_PROVIDER_KEYRING_FILE
    settings.SELAHCUE_PROVIDER_KEYRING_FILE = ""
    with pytest.raises(ProviderConfigurationError, match="PCFG_FILE_REQUIRED"):
        load_provider_configuration("provisioner")
    settings.SELAHCUE_PROVIDER_KEYRING_FILE = installed
    assert load_provider_configuration("provisioner").keyring.active_key_id == "old"


def test_wsgi_returns_application_only_after_successful_role_startup(provider_mounts, settings):
    provider_mounts("web", stt=True, capable=True)
    result = run(
        "-c", "from selahcue_api.wsgi import application;"
        "from selahcue_api.apps.providers.configuration import get_provider_configuration;"
        "assert callable(application);"
        "assert get_provider_configuration(required_role='web').keyring.active_key_id == 'old'",
        SELAHCUE_PROVIDER_PROCESS_ROLE="web", SELAHCUE_CLOUD_STT_ENABLED=" YES ",
        SELAHCUE_PROVIDER_KEYRING_FILE=settings.SELAHCUE_PROVIDER_KEYRING_FILE,
        SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE=settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE,
    )
    assert result.returncode == 0, result.stderr


def test_pool_child_reuses_worker_snapshot_after_mount_disappears(provider_mounts, settings):
    provider_mounts("usage")
    result = run(
        "-c", """
import os
import django
from celery.signals import worker_process_init
from selahcue_api.celery import app
from selahcue_api.apps.providers.configuration import get_provider_configuration

django.setup()
app.Worker(pool="solo", queues=["provider_usage"], concurrency=1)
snapshot = get_provider_configuration(required_role="usage")
os.unlink(os.environ["SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE"])
pid = os.fork()
if pid == 0:
    try:
        worker_process_init.send(sender=None)
        assert get_provider_configuration(required_role="usage") is snapshot
    except BaseException:
        os._exit(1)
    os._exit(0)
assert os.waitpid(pid, 0)[1] == 0
""",
        SELAHCUE_PROVIDER_PROCESS_ROLE="usage", CELERY_BROKER_URL="memory://",
        SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE=settings.SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE,
        SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE=settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE,
    )
    assert result.returncode == 0, result.stderr


def test_maintenance_beat_starts_without_mounts_even_with_public_flags():
    result = run(
        "-c", """
import django
from celery.beat import Scheduler, Service
from selahcue_api.celery import app
from selahcue_api.apps.providers.configuration import get_provider_configuration

class OneTick(Scheduler):
    def tick(self):
        cfg = get_provider_configuration(required_role="maintenance")
        assert cfg.policy is None and cfg.keyring is None
        print("maintenance tick")
        raise SystemExit(0)

django.setup()
Service(app=app, scheduler_cls=OneTick).start()
""",
        SELAHCUE_CLOUD_STT_ENABLED="on", SELAHCUE_CLOUD_NOTES_ENABLED="on",
        SELAHCUE_PROVIDER_KEYRING_FILE="/nonexistent/synthetic-keyring",
        SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE="/nonexistent/synthetic-policy",
        CELERY_BROKER_URL="memory://",
    )
    assert result.returncode == 0, result.stderr
    assert "maintenance tick" in result.stdout
