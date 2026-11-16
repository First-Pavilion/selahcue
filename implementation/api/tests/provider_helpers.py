"""Protected synthetic fixture mounts and stable registry context for provider tests."""
import base64
import json
from uuid import uuid4

import pytest

from selahcue_api.apps.providers.bootstrap import initialize_provider_runtime
from selahcue_api.apps.providers.configuration import _reset_provider_configuration_for_tests
from selahcue_api.apps.providers.contracts import (
    ProviderExternalIdentity, ProviderScope, RegistryAuditContext, RegistryReason, SecretBytes,
)

DEEPGRAM = ProviderScope("deepgram", "synthetic-project")
OPENAI = ProviderScope("openai", "synthetic-organization")
SECRET = SecretBytes(b"synthetic-reusable-secret")


def write_mount(tmp_path, name, contents):
    path = tmp_path / name
    path.unlink(missing_ok=True)
    path.write_bytes(contents if isinstance(contents, bytes) else json.dumps(contents).encode())
    path.chmod(0o400)
    return str(path)


def keyring(active="old", *, old=True, new=False):
    keys = {}
    for enabled, name, byte in ((old, "old", b"a"), (new, "new", b"b")):
        if enabled:
            keys[name] = base64.urlsafe_b64encode(byte * 32).decode().rstrip("=")
    return {"schema_version": 1, "active_key_id": active, "keys": keys}


def policy_rows(*, capable=False, budgets=True):
    deepgram = {"project_id": DEEPGRAM.parent_scope_id, "unattributed_usage_threshold": "0"}
    openai = {"organization_id": OPENAI.parent_scope_id, "unattributed_usage_threshold": "0.00001"}
    if capable:
        common = {
            "resource_capacity": 18, "resource_reserve": 2,
            "create_per_day": 5, "create_per_hour": 2,
            "capacity_evidence_ref": "synthetic-capacity-receipt",
            "controls_evidence_ref": "synthetic-controls-receipt",
        }
        deepgram.update(common, stream_concurrency_capacity=100)
        openai.update(common, notes_policy_id="synthetic-policy")
    policy = {
        "schema_version": 1, "accounting_mode": "observed_records_with_late_corrections",
        "accepted_by": "synthetic-operator", "accepted_at": "2026-11-14T00:00:00Z",
        "deepgram": [deepgram], "openai": [openai],
    }
    if capable and budgets:
        policy["creation_budgets"] = [
            {"provider": provider, "create_per_hour": 2, "create_per_day": 5}
            for provider in ("deepgram", "openai")
        ]
    return policy


def identity(scope=DEEPGRAM, *, key=None):
    return ProviderExternalIdentity(
        scope,
        scope.parent_scope_id if scope.provider == "deepgram" else "synthetic-openai-project",
        None if scope.provider == "deepgram" else "synthetic-service-account",
        key or f"synthetic-key-{uuid4()}",
    )


def audit(reason):
    intent = reason == RegistryReason.PROVISION_INTENT
    return RegistryAuditContext(
        "provider-provisioning-intent" if intent else "synthetic-operator", uuid4(), reason,
        "synthetic-controls-receipt" if intent else "synthetic-operator-evidence",
    )


@pytest.fixture(autouse=True)
def cold_provider_cache():
    _reset_provider_configuration_for_tests()
    yield
    _reset_provider_configuration_for_tests()


@pytest.fixture
def provider_mounts(settings, tmp_path):
    def prepare(role, *, stt=False, notes=False, provisioning=False, capable=False, ring=None, budgets=True):
        _reset_provider_configuration_for_tests()
        settings.SELAHCUE_PROVIDER_PROCESS_ROLE = role
        settings.SELAHCUE_CLOUD_STT_ENABLED = stt
        settings.SELAHCUE_CLOUD_NOTES_ENABLED = notes
        settings.SELAHCUE_PROVIDER_PROVISIONING_ENABLED = provisioning
        settings.SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE = write_mount(tmp_path, "policy", policy_rows(capable=capable, budgets=budgets))
        settings.SELAHCUE_PROVIDER_KEYRING_FILE = write_mount(tmp_path, "keys", keyring() if ring is None else ring)
        settings.SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE = write_mount(tmp_path, "usage", {
            "schema_version": 1,
            "deepgram": [{"project_id": DEEPGRAM.parent_scope_id, "api_key": "synthetic-usage"}],
            "openai": [{"organization_id": OPENAI.parent_scope_id, "admin_api_key": "synthetic-openai-usage"}],
        })
        settings.SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE = write_mount(tmp_path, "provisioning", {
            "schema_version": 1,
            "deepgram": [{"project_id": DEEPGRAM.parent_scope_id, "keys_write_api_key": "synthetic-creds"}],
            "openai": [{"organization_id": OPENAI.parent_scope_id, "admin_api_key": "synthetic-openai-creds"}],
        })
    return prepare


@pytest.fixture
def provisioner_runtime(provider_mounts):
    def initialize(**kwargs):
        provider_mounts("provisioner", **kwargs)
        return initialize_provider_runtime(entrypoint="operator")
    initialize()
    return initialize
