import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from django.test import Client
from django.core.cache import cache
from django.db import connections, connection
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from selahcue_api.apps.pilot_downloads import grants
from selahcue_api.apps.throttling import services

from test_pilot_registration_service import ack, payload, pilot_policy
from selahcue_api.apps.pilot_downloads.models import PilotRegistrationRecord, PilotSheetDestination
from selahcue_api.apps.pilot_downloads.grants import grant_download, SignedRead
from selahcue_api.apps.pilot_downloads.grant_views import grant
from selahcue_api.apps.pilot_downloads.policy import PilotRegistrationError
from selahcue_api.apps.pilot_downloads.services import confirm_registration, reserve_registration


pytestmark = pytest.mark.django_db
URL = "/v1/pilot/downloads:grant"


def manifest_value(now):
    artifacts = []
    for platform, name, architectures, signing in (
        ("Windows", "windows", ["x86_64"], "authenticode_verified"),
        ("Ubuntu", "ubuntu", ["x86_64"], "not_required"),
        ("macOS", "macos", ["x86_64", "aarch64"], "developer_id_notarized_stapled"),
    ):
        artifacts.append({
            "artifact_id": name, "platform": platform, "architectures": architectures,
            "object_key": f"pilot/release-1/{'a' * 64}/{name}.bin", "sha256": "a" * 64,
            "size_bytes": 123456, "available": True, "verified": True,
            "credentials_expires_at": int((now + timedelta(days=20)).timestamp()),
            "signing": signing,
        })
    return {
        "schema_version": 1, "manifest_id": "manifest-1", "release_id": "release-1",
        "cohort_id": "pilot-2026", "version": "0.1.0", "source_sha": "b" * 40,
        "promoted": True, "promoted_at": int((now - timedelta(seconds=60)).timestamp()),
        "expires_at": int((now + timedelta(days=30)).timestamp()), "artifacts": artifacts,
    }


@pytest.fixture
def grant_config(settings, tmp_path, pilot_policy, monkeypatch):
    # Synthetic positive cases must stay within the fixed cohort regardless of
    # the CI wall clock. Explicit boundary tests below still advance this clock.
    now = datetime(2026, 11, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: now)
    pilot_policy["pilot_expires_at"] = (now + timedelta(days=60)).isoformat()
    value = manifest_value(now)
    path = tmp_path / "manifest.json"
    data = json.dumps(value).encode()
    path.write_bytes(data)
    config = {
        "enabled": True, "cohort_id": "pilot-2026", "n8n_token": "g" * 48, "storage_target": "test-private-storage",
        "download_origin": "https://private.example.invalid", "manifest_path": str(path),
        "manifest_sha256": hashlib.sha256(data).hexdigest(), "max_ttl_seconds": 300,
        "signed_query_keys": ["signature", "expires"],
        "signing_requirements": {"Windows": "authenticode_verified", "Ubuntu": "not_required", "macOS": "developer_id_notarized_stapled"},
    }
    settings.SELAHCUE_PILOT_DOWNLOAD_GRANTS = config
    return config, value, path


def receipt_for(platform="Ubuntu"):
    reserved = reserve_registration(payload(platform=platform))
    return confirm_registration(ack(reserved))["receipt"]


def test_unconfigured_production_signer_cannot_return_fake_url(client, grant_config):
    config, _, _ = grant_config
    response = client.post(URL, {"schema_version": 1, "receipt": receipt_for(), "artifact_id": "ubuntu"},
                           content_type="application/json", HTTP_AUTHORIZATION="Bearer " + config["n8n_token"])
    assert response.status_code == 503
    assert response.json() == {"error": {"code": "download_configuration_required"}}


class SyntheticSigner:
    def __init__(self):
        self.requests = []

    def sign_read(self, request):
        self.requests.append(request)
        return SignedRead(f"https://private.example.invalid/{request.object_key}?signature=synthetic&expires={request.expires_at}", request.expires_at)


def grant_body(receipt="AUTO", **changes):
    value = {"schema_version": 1, "receipt": receipt_for() if receipt == "AUTO" else receipt, "artifact_id": "ubuntu"}
    value.update(changes)
    return value


def write_manifest(config, value, path):
    data = json.dumps(value).encode()
    path.write_bytes(data)
    config["manifest_sha256"] = hashlib.sha256(data).hexdigest()


def test_confirmed_registration_gets_exact_metadata_without_new_rows(grant_config):
    body = grant_body()
    before = PilotRegistrationRecord.objects.get().confirmed_at
    signer = SyntheticSigner()
    result = grant_download(body, signer=signer)
    assert result["platform"] == "Ubuntu"
    assert result["architectures"] == ["x86_64"]
    assert result["artifact_id"] == "ubuntu"
    assert result["release_id"] == "release-1"
    assert result["size_bytes"] == 123456
    assert result["sha256"] == "a" * 64
    assert urlsplit(result["download_url"]).path == f"/pilot/release-1/{'a' * 64}/ubuntu.bin"
    assert result["expires_at"] <= int(before.timestamp()) + 300
    assert PilotRegistrationRecord.objects.count() == 1
    assert PilotSheetDestination.objects.get().next_row == 3
    assert PilotRegistrationRecord.objects.get().confirmed_at == before
    assert "receipt" not in result
    assert body["receipt"] not in json.dumps(result)
    assert str(PilotRegistrationRecord.objects.get().registration_id) not in result["download_url"]
    assert grant_download(body, signer=signer)["expires_at"] == result["expires_at"]


@pytest.mark.parametrize("receipt_kind", ["tampered", "forged", "pending", "deleted"])
def test_unconfirmed_or_forged_receipt_never_signs(grant_config, receipt_kind):
    body = grant_body()
    if receipt_kind == "tampered": body["receipt"] += "x"
    if receipt_kind == "forged": body["receipt"] = "untrusted"
    if receipt_kind == "pending":
        PilotRegistrationRecord.objects.update(confirmed_at=None)
    if receipt_kind == "deleted": PilotRegistrationRecord.objects.all().delete()
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError): grant_download(body, signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("artifact_id", ["windows", "unknown", "../ubuntu", "https://bad.invalid/x", "", 1, True])
def test_wrong_platform_or_non_allowlisted_selection_never_signs(grant_config, artifact_id):
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError): grant_download(grant_body(artifact_id=artifact_id), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("changes", [
    {"schema_version": True}, {"schema_version": 2}, {"platform": "Windows"},
    {"ttl": 3600}, {"url": "https://bad.invalid"}, {"receipt": None},
])
def test_extra_fields_and_wrong_types_do_not_reach_signer(grant_config, changes):
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError): grant_download(grant_body(**changes), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("mutation", [
    "unknown_schema", "bool_schema", "incomplete", "duplicate_id", "unknown_platform", "ubuntu_arm", "mac_not_universal",
    "unpromoted", "future_promotion", "expired", "past_cutoff", "bad_sha", "bad_source", "zero_size", "bool_size",
    "unavailable", "unverified", "unknown_signing", "unsigned_mac", "expired_credentials", "credentials_past_cutoff",
    "traversal", "wrong_hash_path", "url_key", "extra", "artifact_extra",
])
def test_bad_manifest_is_never_grantable(grant_config, mutation):
    config, original, path = grant_config
    value = copy.deepcopy(original)
    artifact = value["artifacts"][1]
    if mutation == "unknown_schema": value["schema_version"] = 2
    elif mutation == "bool_schema": value["schema_version"] = True
    elif mutation == "incomplete": value["artifacts"].pop()
    elif mutation == "duplicate_id": artifact["artifact_id"] = "windows"
    elif mutation == "unknown_platform": artifact["platform"] = "Other"
    elif mutation == "ubuntu_arm": artifact["architectures"] = ["aarch64"]
    elif mutation == "mac_not_universal": value["artifacts"][2]["architectures"] = ["aarch64"]
    elif mutation == "unpromoted": value["promoted"] = False
    elif mutation == "future_promotion": value["promoted_at"] = int(timezone.now().timestamp()) + 3600
    elif mutation == "expired": value["expires_at"] = int(timezone.now().timestamp())
    elif mutation == "past_cutoff": value["expires_at"] = 1809129600
    elif mutation == "bad_sha": artifact["sha256"] = "x" * 64
    elif mutation == "bad_source": value["source_sha"] = "b" * 39
    elif mutation == "zero_size": artifact["size_bytes"] = 0
    elif mutation == "bool_size": artifact["size_bytes"] = True
    elif mutation == "unavailable": artifact["available"] = False
    elif mutation == "unverified": artifact["verified"] = False
    elif mutation == "unknown_signing": artifact["signing"] = "unknown"
    elif mutation == "unsigned_mac": value["artifacts"][2]["signing"] = "unsigned"
    elif mutation == "expired_credentials": artifact["credentials_expires_at"] = int(timezone.now().timestamp())
    elif mutation == "credentials_past_cutoff": artifact["credentials_expires_at"] = 1809129600
    elif mutation == "traversal": artifact["object_key"] = "../secret"
    elif mutation == "wrong_hash_path": artifact["object_key"] = "pilot/release-1/wrong/ubuntu.bin"
    elif mutation == "url_key": artifact["object_key"] = "https://bad.invalid/a"
    elif mutation == "extra": value["download_url"] = "https://bad.invalid"
    elif mutation == "artifact_extra": artifact["provider_key"] = "not-allowed"
    write_manifest(config, value, path)
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError): grant_download(grant_body(), signer=signer)
    assert not signer.requests


def test_manifest_digest_and_size_are_bounded(grant_config):
    config, _, path = grant_config
    body = grant_body()
    path.write_text('{}')
    with pytest.raises(PilotRegistrationError): grant_download(body, signer=SyntheticSigner())
    path.write_bytes(b' ' * 65537)
    config["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(PilotRegistrationError): grant_download(body, signer=SyntheticSigner())


def test_anchored_receipt_expiry_and_slow_signer_cannot_extend_window(grant_config, monkeypatch):
    now = timezone.now().replace(microsecond=0)
    monkeypatch.setattr(timezone, "now", lambda: now)
    body = grant_body()
    signer = SyntheticSigner()
    original = grant_download(body, signer=signer)
    now += timedelta(seconds=290)
    assert grant_download(body, signer=signer)["expires_at"] == original["expires_at"]
    now += timedelta(seconds=10)
    with pytest.raises(PilotRegistrationError): grant_download(body, signer=signer)
    now -= timedelta(seconds=10)
    class SlowSigner:
        def sign_read(self, request):
            nonlocal now
            now += timedelta(seconds=11)
            return SignedRead(f"https://private.example.invalid/{request.object_key}?signature=synthetic", request.expires_at)
    with pytest.raises(PilotRegistrationError): grant_download(body, signer=SlowSigner())


@pytest.mark.parametrize("mutation", ["exception", "wrong_origin", "wrong_object", "overlong_expiry", "expired", "receipt_query", "fragment", "userinfo", "duplicate_query", "unknown_query", "malformed"])
def test_signer_errors_or_unsafe_results_do_not_escape(grant_config, mutation, caplog):
    body = grant_body()
    class BadSigner:
        def sign_read(self, request):
            if mutation == "exception": raise TimeoutError("private-provider-secret-sentinel")
            url = f"https://private.example.invalid/{request.object_key}?signature=synthetic"
            expiry = request.expires_at
            if mutation == "wrong_origin": url = url.replace("private.example.invalid", "attacker.invalid")
            elif mutation == "wrong_object": url = url.replace("ubuntu.bin", "other.bin")
            elif mutation == "overlong_expiry": expiry += 1
            elif mutation == "expired": expiry = int(timezone.now().timestamp())
            elif mutation == "receipt_query": url += "&receipt=" + body["receipt"]
            elif mutation == "fragment": url += "#secret"
            elif mutation == "userinfo": url = url.replace("https://", "https://user:pass@")
            elif mutation == "duplicate_query": url += "&signature=second"
            elif mutation == "unknown_query": url += "&email=operator@example.invalid"
            elif mutation == "malformed": return {"download_url": url}
            return SignedRead(url, expiry)
    with pytest.raises(PilotRegistrationError) as error: grant_download(body, signer=BadSigner())
    assert "private-provider-secret-sentinel" not in str(error.value)
    assert body["receipt"] not in caplog.text
    assert "private-provider-secret-sentinel" not in caplog.text


def test_server_auth_precedes_body_read_and_cookie_never_authorizes(grant_config, rf):
    request = rf.post(URL, b'broken', content_type="application/json", HTTP_AUTHORIZATION="Bearer untrusted-device-token")
    request.COOKIES["selahcue_account_session"] = "untrusted-cookie"
    def forbidden(*args, **kwargs): raise AssertionError("unauthorized request body read")
    request.read = forbidden
    response = grant(request)
    assert response.status_code == 403
    assert response.content == b'{"error": {"code": "server_auth_required"}}'
    assert response["Cache-Control"] == "no-store"
    assert response["Referrer-Policy"] == "no-referrer"
    assert not response.cookies


@pytest.mark.parametrize("body,content_type,status", [
    ('{"schema_version":1,"schema_version":1}', "application/json", 400),
    ('[' * 1500 + ']' * 1500, "application/json", 400),
    ('x' * 8193, "application/json", 413),
    ('not-json', "text/plain", 415),
])
def test_body_bounds_and_media_are_enforced(client, grant_config, body, content_type, status):
    config, _, _ = grant_config
    response = client.post(URL, body, content_type=content_type, HTTP_AUTHORIZATION="Bearer " + config["n8n_token"])
    assert response.status_code == status
    assert "download_url" not in response.json()


@pytest.mark.parametrize("field,value", [
    ("n8n_token", "t" * 48), ("n8n_token", "s" * 48), ("n8n_token", "f" * 48),
    ("n8n_token", "\x00" * 48), ("n8n_token", "short"), ("n8n_token", "é" * 48),
    ("storage_target", "../private"), ("cohort_id", ""),
    ("download_origin", "http://private.example.invalid"),
    ("download_origin", "https://user:password@private.example.invalid"),
    ("download_origin", "https://private.example.invalid/path"),
    ("manifest_path", "relative.json"), ("manifest_sha256", "bad"),
    ("max_ttl_seconds", 301), ("max_ttl_seconds", 0), ("max_ttl_seconds", True),
    ("signed_query_keys", ["receipt"]), ("signed_query_keys", ["signature", "signature"]),
    ("signing_requirements", {"macOS": "unsigned"}),
])
def test_invalid_or_reused_grant_configuration_fails_closed(grant_config, field, value):
    config, _, _ = grant_config
    config[field] = value
    with pytest.raises(PilotRegistrationError) as error: grant_download(grant_body(), signer=SyntheticSigner())
    assert error.value.code == "download_configuration_required"


def test_disabled_and_method_errors_are_explicit(client, grant_config, settings):
    config, _, _ = grant_config
    settings.SELAHCUE_PILOT_DOWNLOAD_GRANTS = {"enabled": False}
    response = client.post(URL, {}, content_type="application/json")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "downloads_disabled"}}
    settings.SELAHCUE_PILOT_DOWNLOAD_GRANTS = config
    response = client.get(URL)
    assert response.status_code == 405
    assert response["Allow"] == "POST"


def test_signer_error_is_safe_over_http_and_csrf_does_not_replace_server_auth(grant_config, monkeypatch):
    client = Client(enforce_csrf_checks=True)
    config, _, _ = grant_config
    monkeypatch.setattr(grants, "configured_private_read_signer", lambda policy: SyntheticSigner())
    body = grant_body()
    response = client.post(URL, body, content_type="application/json", HTTP_AUTHORIZATION="Bearer " + config["n8n_token"])
    assert response.status_code == 200
    assert response.json()["artifact_id"] == "ubuntu"
    assert "Access-Control-Allow-Origin" not in response
    assert response["Cache-Control"] == "no-store"
    assert not response.cookies
    assert client.post(URL, body, content_type="application/json").status_code == 403


def test_rate_limit_and_store_outage_are_fail_closed(grant_config, client, settings, monkeypatch):
    cache.clear()
    config, _, _ = grant_config
    settings.SELAHCUE_THROTTLE_PILOT_DOWNLOAD_GRANT = (1, 60)
    headers = {"HTTP_AUTHORIZATION": "Bearer " + config["n8n_token"]}
    body = grant_body()
    assert client.post(URL, body, content_type="application/json", **headers).status_code == 503
    limited = client.post(URL, body, content_type="application/json", **headers)
    assert limited.status_code == 429
    assert limited.json() == {"error": {"code": "download_rate_limited"}}
    assert int(limited["Retry-After"]) >= 1
    cache.clear()
    def unavailable(*args, **kwargs): return services.BudgetOutcome.STORE_UNAVAILABLE
    monkeypatch.setattr("selahcue_api.apps.throttling.decorators.evaluate_budget", unavailable)
    denied = client.post(URL, body, content_type="application/json", **headers)
    assert denied.status_code == 429
    assert "download_url" not in denied.json()
    cache.clear()


@pytest.mark.django_db(transaction=True)
def test_postgres_concurrent_replay_preserves_ledger_without_locking_signer(grant_config):
    if connection.vendor != "postgresql":
        pytest.skip("requires actual PostgreSQL")
    body = grant_body()
    confirmed_at = PilotRegistrationRecord.objects.get().confirmed_at
    start = Barrier(4)
    class NoLockSigner(SyntheticSigner):
        def sign_read(self, request):
            if connection.in_atomic_block:
                raise AssertionError("remote signer inside database transaction")
            return super().sign_read(request)
    def worker():
        connections.close_all()
        try:
            start.wait(timeout=10)
            return grant_download(dict(body), signer=NoLockSigner())
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: worker(), range(4)))
    assert {value["artifact_id"] for value in results} == {"ubuntu"}
    assert len({value["expires_at"] for value in results}) == 1
    assert PilotRegistrationRecord.objects.count() == 1
    assert PilotSheetDestination.objects.get().next_row == 3
    assert PilotRegistrationRecord.objects.get().confirmed_at == confirmed_at


@pytest.fixture
def windows_grant_config(grant_config):
    config, value, path = grant_config
    config["required_platforms"] = ["Windows"]
    config["signing_requirements"] = {"Windows": "authenticode_verified"}
    value["artifacts"] = value["artifacts"][:1]
    write_manifest(config, value, path)
    return config, value, path


def windows_body(**changes):
    return grant_body(receipt_for("Windows"), artifact_id="windows", **changes)


def test_explicit_windows_only_grants_exact_verified_package(windows_grant_config):
    signer = SyntheticSigner()
    result = grant_download(windows_body(), signer=signer)
    assert result["platform"] == "Windows"
    assert result["architectures"] == ["x86_64"]
    assert result["artifact_id"] == "windows"
    assert result["sha256"] == "a" * 64
    assert result["size_bytes"] == 123456
    assert urlsplit(result["download_url"]).path == f"/pilot/release-1/{'a' * 64}/windows.bin"
    assert len(signer.requests) == 1
    assert signer.requests[0].storage_target == "test-private-storage"


@pytest.mark.parametrize("explicit_full", [False, True])
def test_windows_only_manifest_requires_explicit_windows_policy(grant_config, explicit_full):
    config, value, path = grant_config
    if explicit_full:
        config["required_platforms"] = ["Windows", "Ubuntu", "macOS"]
    value["artifacts"] = value["artifacts"][:1]
    write_manifest(config, value, path)
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError, match="download_manifest_unavailable"):
        grant_download(windows_body(), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("platforms", [
    None, "Windows", "", [], ["Windows", "Windows"], ["Windows", "Ubuntu"],
    ["Windows", "macOS"], ["Ubuntu", "macOS"], ["Ubuntu"], ["macOS"], ["Other"],
    ["Windows", "Ubuntu", "Other"], ["Windows", None], [True], {},
])
def test_invalid_server_platform_sets_never_sign(grant_config, platforms):
    config, _, _ = grant_config
    config["required_platforms"] = platforms
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError, match="download_configuration_required"):
        grant_download(grant_body(), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("signing", [
    {}, None, {"Ubuntu": "not_required"},
    {"Windows": "authenticode_verified", "Ubuntu": "not_required"},
    {"Windows": "not_required"}, {"Windows": "unsigned"}, {"Windows": None},
])
def test_windows_signing_policy_is_explicit_and_exact(windows_grant_config, signing):
    config, _, _ = windows_grant_config
    config["signing_requirements"] = signing
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError, match="download_configuration_required"):
        grant_download(windows_body(), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("unsigned_approved", [False, True])
def test_unsigned_windows_requires_explicit_signing_approval(windows_grant_config, unsigned_approved):
    config, value, path = windows_grant_config
    value["artifacts"][0]["signing"] = "unsigned_pilot_approved"
    write_manifest(config, value, path)
    if unsigned_approved:
        config["signing_requirements"]["Windows"] = "unsigned_pilot_approved"
    signer = SyntheticSigner()
    if unsigned_approved:
        assert grant_download(windows_body(), signer=signer)["artifact_id"] == "windows"
    else:
        with pytest.raises(PilotRegistrationError, match="download_manifest_unavailable"):
            grant_download(windows_body(), signer=signer)
        assert not signer.requests


@pytest.mark.parametrize("mutation", [
    "missing", "extra_ubuntu", "extra_macos", "unknown", "duplicate", "substitute_ubuntu",
    "architecture", "hash", "object_key", "signing", "expired", "credentials_expired",
    "unverified", "unavailable", "digest",
])
def test_windows_manifest_refuses_inexact_or_unverified_artifacts(windows_grant_config, mutation):
    config, value, path = windows_grant_config
    artifact = value["artifacts"][0]
    now = int(timezone.now().timestamp())
    if mutation == "missing": value["artifacts"] = []
    elif mutation == "extra_ubuntu": value["artifacts"].append(manifest_value(timezone.now())["artifacts"][1])
    elif mutation == "extra_macos": value["artifacts"].append(manifest_value(timezone.now())["artifacts"][2])
    elif mutation == "unknown": artifact["platform"] = "Other"
    elif mutation == "duplicate": value["artifacts"].append(copy.deepcopy(artifact))
    elif mutation == "substitute_ubuntu": value["artifacts"] = manifest_value(timezone.now())["artifacts"][1:2]
    elif mutation == "architecture": artifact["architectures"] = ["aarch64"]
    elif mutation == "hash": artifact["sha256"] = "bad"
    elif mutation == "object_key": artifact["object_key"] = "pilot/release-1/wrong/windows.bin"
    elif mutation == "signing": artifact["signing"] = "unsigned_pilot_approved"
    elif mutation == "expired": value["expires_at"] = now
    elif mutation == "credentials_expired": artifact["credentials_expires_at"] = now
    elif mutation == "unverified": artifact["verified"] = False
    elif mutation == "unavailable": artifact["available"] = False
    write_manifest(config, value, path)
    if mutation == "digest": config["manifest_sha256"] = "0" * 64
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError, match="download_manifest_unavailable"):
        grant_download(windows_body(), signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("mutation", ["forged", "ubuntu", "required_platforms", "signing_requirements"])
def test_windows_receipt_and_request_cannot_choose_policy(windows_grant_config, mutation):
    body = windows_body()
    if mutation == "forged": body["receipt"] = "untrusted"
    elif mutation == "ubuntu": body["receipt"] = receipt_for("Ubuntu")
    elif mutation == "required_platforms": body["required_platforms"] = ["Windows"]
    elif mutation == "signing_requirements": body["signing_requirements"] = {"Windows": "unsigned_pilot_approved"}
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError):
        grant_download(body, signer=signer)
    assert not signer.requests


def test_legacy_positional_policy_constructor_preserves_full_set(grant_config):
    config, _, _ = grant_config
    policy = grants.GrantPolicy(
        config["n8n_token"], config["storage_target"], config["download_origin"],
        config["manifest_path"], config["manifest_sha256"], 300,
        ("signature", "expires"), config["signing_requirements"], config["cohort_id"],
    )
    assert grant_download(grant_body(), policy=policy, signer=SyntheticSigner())["platform"] == "Ubuntu"


@pytest.mark.parametrize("changes", [
    {"required_platforms": None}, {"required_platforms": ()},
    {"required_platforms": ("Ubuntu",)}, {"required_platforms": ("Windows", "Ubuntu")},
    {"required_platforms": ("Windows", "Windows")}, {"required_platforms": ("Other",)},
    {"signing_requirements": {}}, {"signing_requirements": {"Windows": "not_required"}},
    {"signing_requirements": {"Windows": "authenticode_verified", "Ubuntu": "not_required"}},
])
def test_direct_policy_injection_cannot_weaken_platform_or_signing_checks(windows_grant_config, changes):
    policy = replace(grants.load_grant_policy(), **changes)
    signer = SyntheticSigner()
    with pytest.raises(PilotRegistrationError):
        grant_download(windows_body(), policy=policy, signer=signer)
    assert not signer.requests


@pytest.mark.parametrize("required_env,expected", [
    (None, ["Windows", "Ubuntu", "macOS"]), ("Windows", ["Windows"]),
    ("macOS, Windows Ubuntu", ["Windows", "Ubuntu", "macOS"]),
    ("", None), ("Windows Windows", None), ("Windows Ubuntu", None),
    ("Ubuntu", None), ("Other", None),
])
def test_actual_environment_settings_loader_and_manifest(grant_config, required_env, expected):
    config, value, path = grant_config
    if expected == ["Windows"]:
        value["artifacts"] = value["artifacts"][:1]
        config["signing_requirements"] = {"Windows": "authenticode_verified"}
        write_manifest(config, value, path)
    # A fresh, minimal environment prevents host deployment settings from
    # selecting a database, cache, provider or policy for this bounded process.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    env.update({"SQL_DATABASE": ":memory:", "DJANGO_SETTINGS_MODULE": "selahcue_api.settings"})
    for field, suffix in (
        ("enabled", "ENABLED"), ("n8n_token", "N8N_TOKEN"), ("storage_target", "STORAGE_TARGET"),
        ("download_origin", "DOWNLOAD_ORIGIN"), ("cohort_id", "COHORT_ID"),
        ("manifest_path", "MANIFEST_PATH"), ("manifest_sha256", "MANIFEST_SHA256"),
        ("max_ttl_seconds", "MAX_TTL_SECONDS"),
    ):
        env["SELAHCUE_PILOT_GRANT_" + suffix] = str(config[field])
    env["SELAHCUE_PILOT_GRANT_SIGNED_QUERY_KEYS"] = "signature,expires"
    env["SELAHCUE_PILOT_GRANT_SIGNING_REQUIREMENTS"] = json.dumps(config["signing_requirements"])
    if required_env is not None:
        env["SELAHCUE_PILOT_GRANT_REQUIRED_PLATFORMS"] = required_env
    program = """
import json
from types import SimpleNamespace
import django
django.setup()
from django.conf import settings
from selahcue_api.apps.pilot_downloads.grants import load_grant_policy
from selahcue_api.apps.pilot_downloads.grant_manifest import load_manifest
from selahcue_api.apps.pilot_downloads.policy import PilotRegistrationError
registration = SimpleNamespace(n8n_token='t'*48, signing_key='s'*48, fingerprint_key='f'*48)
try:
    policy = load_grant_policy(registration)
    manifest = load_manifest(policy, 1793534400)
    print(json.dumps({'required': list(policy.required_platforms), 'artifacts': [a.platform for a in manifest.artifacts]}))
except PilotRegistrationError as error:
    print(json.dumps({'error': error.code}))
"""
    result = subprocess.run([sys.executable, "-c", program], env=env, capture_output=True, text=True, timeout=10, check=True)
    actual = json.loads(result.stdout)
    if expected is None:
        assert actual == {"error": "download_configuration_required"}
    else:
        assert actual == {"required": expected, "artifacts": expected}
