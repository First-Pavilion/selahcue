"""Validate local provider mounts and cache one immutable process snapshot."""
import base64
import binascii
import errno
import json
import os
import re
import stat
from datetime import datetime
from decimal import Decimal
from threading import RLock

from django.conf import settings

from .contracts import (
    ConfigErrorCode as Code,
    ConfigSource as Source,
    ProviderConfiguration,
    ProviderConfigurationError,
    ProviderCreationBudget,
    ProviderDeploymentPolicy,
    ProviderKeyring,
    ProviderProcessRole,
    ProviderScope,
    ProviderScopePolicy,
    ProvisioningCredential,
    SecretBytes,
    UsageCredential,
    WrappingKey,
)

ROLES = ("web", "usage", "provisioner", "notes", "maintenance")
PROVIDERS = ("deepgram", "openai")
ACCOUNTING_MODE = "observed_records_with_late_corrections"
FILE_LIMIT = 65536
SCOPE_LIMIT = 32
PATH_SETTINGS = {
    Source.KEYRING: "SELAHCUE_PROVIDER_KEYRING_FILE",
    Source.USAGE: "SELAHCUE_PROVIDER_USAGE_CREDENTIALS_FILE",
    Source.PROVISIONING: "SELAHCUE_PROVIDER_PROVISIONING_CREDENTIALS_FILE",
    Source.POLICY: "SELAHCUE_PROVIDER_DEPLOYMENT_POLICY_FILE",
}
PARENT_FIELDS = {"deepgram": "project_id", "openai": "organization_id"}
COUNTERS = ("resource_capacity", "resource_reserve", "create_per_day", "create_per_hour")
EVIDENCE = ("capacity_evidence_ref", "controls_evidence_ref")
_ID = re.compile(r"[!-~]{1,256}")
_EVIDENCE = re.compile(r"[^\x00-\x1f\x7f-\x9f\ud800-\udfff]{1,2048}")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,12})?")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z")
_SECRET = re.compile(r"[!-~]{1,4096}")
_KEY = re.compile(r"[A-Za-z0-9_-]{43}")

_cache_lock = RLock()
_snapshot: ProviderConfiguration | None = None
_runtime_ready = False
_entrypoint = None


def valid_id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def valid_evidence(value: object) -> bool:
    return type(value) is str and bool(value.strip()) and _EVIDENCE.fullmatch(value) is not None


def selected_role() -> ProviderProcessRole:
    role = settings.SELAHCUE_PROVIDER_PROCESS_ROLE
    if role not in ROLES:
        raise ProviderConfigurationError(Code.PCFG_ROLE_INVALID, Source.SETTINGS)
    return role


def _requested_providers() -> frozenset:
    return frozenset(provider for provider, enabled in (
        ("deepgram", settings.SELAHCUE_CLOUD_STT_ENABLED),
        ("openai", settings.SELAHCUE_CLOUD_NOTES_ENABLED),
    ) if enabled)


def path_is_valid(path: object) -> bool:
    return type(path) is str and (path == "" or (os.path.isabs(path) and "\0" not in path))


def _file_metadata(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_file(source: Source) -> bytes:
    path = getattr(settings, PATH_SETTINGS[source])
    if path == "":
        raise ProviderConfigurationError(Code.PCFG_FILE_REQUIRED, source)
    if not path_is_valid(path):
        raise ProviderConfigurationError(Code.PCFG_FILE_UNSAFE, source)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid not in {0, os.geteuid()}
                    or not before.st_mode & stat.S_IRUSR or before.st_mode & 0o7077):
                raise ProviderConfigurationError(Code.PCFG_FILE_UNSAFE, source)
            if before.st_size > FILE_LIMIT:
                raise ProviderConfigurationError(Code.PCFG_FILE_TOO_LARGE, source)
            with os.fdopen(fd, "rb", closefd=False) as mount:
                data = mount.read(FILE_LIMIT + 1)
            if len(data) > FILE_LIMIT:
                raise ProviderConfigurationError(Code.PCFG_FILE_TOO_LARGE, source)
            if len(data) != before.st_size or _file_metadata(before) != _file_metadata(os.fstat(fd)):
                raise ProviderConfigurationError(Code.PCFG_FILE_UNSAFE, source)
            return data
        finally:
            os.close(fd)
    except OSError as exc:
        code = Code.PCFG_FILE_UNSAFE if exc.errno == errno.ELOOP else Code.PCFG_FILE_UNREADABLE
        raise ProviderConfigurationError(code, source) from None


def _pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _invalid_number(_raw: str):
    raise ValueError


def _read_json(source: Source):
    data = _read_file(source)
    try:
        decoded = data.decode("utf-8")
        if decoded.startswith("\ufeff"):
            raise UnicodeError
    except UnicodeError:
        raise ProviderConfigurationError(Code.PCFG_ENCODING_INVALID, source) from None
    try:
        return json.loads(decoded, object_pairs_hook=_pairs,
                          parse_float=_invalid_number, parse_constant=_invalid_number)
    except (ValueError, RecursionError):
        raise ProviderConfigurationError(Code.PCFG_JSON_INVALID, source) from None


def _fields(value: object, required: set[str], optional=()) -> bool:
    return type(value) is dict and required <= value.keys() <= required.union(optional)


def _version(value: dict) -> bool:
    return type(value["schema_version"]) is int and value["schema_version"] == 1


def _schema(source: Source) -> ProviderConfigurationError:
    return ProviderConfigurationError(Code.PCFG_SCHEMA_INVALID, source)


def _read_keyring() -> ProviderKeyring:
    source = Source.KEYRING
    data = _read_json(source)
    if not _fields(data, {"schema_version", "active_key_id", "keys"}) or not _version(data):
        raise _schema(source)
    keys = data["keys"]
    active = data["active_key_id"]
    if not valid_id(active) or type(keys) is not dict or not 1 <= len(keys) <= 8:
        raise _schema(source)
    parsed = []
    for key_id, encoded in sorted(keys.items()):
        if not valid_id(key_id):
            raise _schema(source)
        if type(encoded) is not str or not _KEY.fullmatch(encoded):
            raise ProviderConfigurationError(Code.PCFG_KEY_INVALID, source)
        try:
            material = base64.b64decode(encoded + "=", altchars=b"-_", validate=True)
        except binascii.Error:
            raise ProviderConfigurationError(Code.PCFG_KEY_INVALID, source) from None
        if len(material) != 32 or base64.urlsafe_b64encode(material).decode("ascii").rstrip("=") != encoded:
            raise ProviderConfigurationError(Code.PCFG_KEY_INVALID, source)
        parsed.append(WrappingKey(key_id, SecretBytes(material)))
    keyring = ProviderKeyring(active, tuple(parsed))
    keyring.active()
    return keyring


def _scoped_rows(data: dict, source: Source):
    if not all(type(data[provider]) is list for provider in PROVIDERS):
        raise _schema(source)
    if sum(len(data[provider]) for provider in PROVIDERS) > SCOPE_LIMIT:
        raise _schema(source)
    for provider in PROVIDERS:
        for row in data[provider]:
            yield provider, PARENT_FIELDS[provider], row


def _unique_scopes(rows: list, source: Source) -> tuple:
    if len({row.scope for row in rows}) != len(rows):
        raise ProviderConfigurationError(Code.PCFG_SCOPE_MISMATCH, source)
    return tuple(sorted(rows, key=lambda row: (row.scope.provider, row.scope.parent_scope_id)))


def _read_credentials(source: Source) -> tuple:
    data = _read_json(source)
    if not _fields(data, {"schema_version", *PROVIDERS}) or not _version(data):
        raise _schema(source)
    credential_type = UsageCredential if source == Source.USAGE else ProvisioningCredential
    rows = []
    for provider, parent, row in _scoped_rows(data, source):
        key_field = "admin_api_key" if provider == "openai" else (
            "api_key" if source == Source.USAGE else "keys_write_api_key"
        )
        if not _fields(row, {parent, key_field}) or not valid_id(row[parent]):
            raise _schema(source)
        value = row[key_field]
        if type(value) is not str or not _SECRET.fullmatch(value):
            raise _schema(source)
        rows.append(credential_type(ProviderScope(provider, row[parent]), SecretBytes(value.encode("ascii"))))
    return _unique_scopes(rows, source)


def _decimal(value: object) -> Decimal:
    if type(value) is not str or not _DECIMAL.fullmatch(value):
        raise _schema(Source.POLICY)
    return Decimal(value)


def _policy_scope(provider: str, parent: str, row: dict) -> ProviderScopePolicy:
    special = ("stream_concurrency_capacity",) if provider == "deepgram" else (
        "notes_policy_id", "notes_daily_budget_usd",
    )
    if not _fields(row, {parent, "unattributed_usage_threshold"}, (*COUNTERS, *EVIDENCE, *special)):
        raise _schema(Source.POLICY)
    if not valid_id(row[parent]) or ("notes_policy_id" in row and not valid_id(row["notes_policy_id"])):
        raise _schema(Source.POLICY)
    for name in (*COUNTERS, "stream_concurrency_capacity"):
        if name in row and (type(row[name]) is not int or not 0 <= row[name] <= 9223372036854775807):
            raise _schema(Source.POLICY)
    if any(name in row and not valid_evidence(row[name]) for name in EVIDENCE):
        raise _schema(Source.POLICY)
    capacity, reserve = row.get("resource_capacity"), row.get("resource_reserve")
    if capacity and reserve and capacity <= reserve:
        raise _schema(Source.POLICY)
    return ProviderScopePolicy(
        ProviderScope(provider, row[parent]), *(row.get(name) for name in (*COUNTERS, *EVIDENCE)),
        _decimal(row["unattributed_usage_threshold"]), row.get("stream_concurrency_capacity"),
        row.get("notes_policy_id"), _decimal(row["notes_daily_budget_usd"]) if "notes_daily_budget_usd" in row else None,
    )


def _read_policy() -> ProviderDeploymentPolicy:
    source = Source.POLICY
    data = _read_json(source)
    fields = {"schema_version", "accounting_mode", "accepted_by", "accepted_at", *PROVIDERS}
    if not _fields(data, fields, ("creation_budgets",)) or not _version(data) or data["accounting_mode"] != ACCOUNTING_MODE:
        raise _schema(source)
    at = data["accepted_at"]
    if not valid_id(data["accepted_by"]) or type(at) is not str or not _UTC.fullmatch(at):
        raise _schema(source)
    try:
        when = datetime.fromisoformat(at)
    except ValueError:
        raise _schema(source) from None
    rows = [_policy_scope(*scoped) for scoped in _scoped_rows(data, source)]
    budgets = data.get("creation_budgets", [])
    if type(budgets) is not list or len(budgets) > len(PROVIDERS):
        raise _schema(source)
    parsed_budgets = {}
    for row in budgets:
        if (
            not _fields(row, {"provider", "create_per_hour", "create_per_day"})
            or type(row["provider"]) is not str or row["provider"] not in PROVIDERS
            or row["provider"] in parsed_budgets
            or any(type(row[name]) is not int or not 0 <= row[name] <= 9223372036854775807
                   for name in ("create_per_hour", "create_per_day"))
        ):
            raise _schema(source)
        parsed_budgets[row["provider"]] = ProviderCreationBudget(**row)
    return ProviderDeploymentPolicy(
        1, ACCOUNTING_MODE, data["accepted_by"], when, _unique_scopes(rows, source),
        tuple(parsed_budgets[provider] for provider in sorted(parsed_budgets)),
    )


def is_create_capable(policy: ProviderScopePolicy) -> bool:
    return (
        all((getattr(policy, name) or 0) > 0 for name in COUNTERS)
        and policy.resource_capacity > policy.resource_reserve
        and bool(policy.capacity_evidence_ref and policy.controls_evidence_ref)
        and (
            (policy.stream_concurrency_capacity or 0) > 0 if policy.scope.provider == "deepgram"
            else bool(policy.notes_policy_id)
        )
    )


def has_creation_authority(policy: ProviderDeploymentPolicy, scope: ProviderScopePolicy) -> bool:
    return is_create_capable(scope) and any(
        budget.provider == scope.scope.provider and budget.create_per_hour > 0 and budget.create_per_day > 0
        for budget in policy.creation_budgets
    )


def _parse(role: ProviderProcessRole, public: frozenset) -> ProviderConfiguration:
    provisioning = settings.SELAHCUE_PROVIDER_PROVISIONING_ENABLED
    if role == "maintenance" or (role == "web" and not public):
        return ProviderConfiguration(role, public, provisioning, None, None, (), ())
    policy = _read_policy()
    scopes = {item.scope for item in policy.scopes}
    if role == "web" and "deepgram" in public:
        deepgram = tuple(item for item in policy.scopes if item.scope.provider == "deepgram")
        if not deepgram or not all(is_create_capable(item) for item in deepgram):
            raise ProviderConfigurationError(Code.PCFG_CAPABILITY_UNCONFIGURED, Source.POLICY)
    if role == "notes" and not any(scope.provider == "openai" for scope in scopes):
        raise ProviderConfigurationError(Code.PCFG_SCOPE_MISMATCH, Source.POLICY)
    creates = [scope for scope in policy.scopes if has_creation_authority(policy, scope)]
    if provisioning and (
        (role == "provisioner" and not creates)
        or (role == "web" and any(
            scope.scope.provider in public and is_create_capable(scope) and scope not in creates
            for scope in policy.scopes
        ))
    ):
        raise ProviderConfigurationError(Code.PCFG_CAPABILITY_UNCONFIGURED, Source.POLICY)

    usage = provisioners = ()
    if role in ("usage", "provisioner"):
        source = Source.USAGE if role == "usage" else Source.PROVISIONING
        credentials = _read_credentials(source)
        if not scopes or scopes != {entry.scope for entry in credentials}:
            raise ProviderConfigurationError(Code.PCFG_SCOPE_MISMATCH, source)
        if role == "usage":
            usage = credentials
        else:
            provisioners = credentials
    ring = None if role == "usage" else _read_keyring()
    return ProviderConfiguration(role, public, provisioning, policy, ring, usage, provisioners)


def _load(role: ProviderProcessRole, *, entrypoint: str | None = None) -> ProviderConfiguration:
    global _snapshot, _runtime_ready, _entrypoint
    if role not in ROLES:
        raise ProviderConfigurationError(Code.PCFG_ROLE_INVALID, Source.SETTINGS)
    selected = selected_role()
    public = _requested_providers()
    if role != selected:
        raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
    with _cache_lock:
        if _snapshot is not None and _snapshot.role != role:
            raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
        if _snapshot is None:
            _snapshot = _parse(role, public)
        if entrypoint is not None:
            if _entrypoint is not None and _entrypoint != entrypoint:
                raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
            _entrypoint = entrypoint
            _runtime_ready = True
        return _snapshot


def load_provider_configuration(role: ProviderProcessRole) -> ProviderConfiguration:
    return _load(role)


def get_provider_configuration(*, required_role: ProviderProcessRole) -> ProviderConfiguration:
    with _cache_lock:
        if not _runtime_ready or _snapshot is None:
            raise ProviderConfigurationError(Code.PCFG_NOT_INITIALIZED)
        if required_role != _snapshot.role:
            raise ProviderConfigurationError(Code.PCFG_ROLE_MISMATCH, Source.SETTINGS)
        return _snapshot


def _reset_provider_configuration_for_tests() -> None:
    global _snapshot, _runtime_ready, _entrypoint
    with _cache_lock:
        _snapshot = None
        _runtime_ready = False
        _entrypoint = None


def _reset_cache_lock_after_fork() -> None:
    global _cache_lock
    _cache_lock = RLock()


def _initialized_entrypoint():
    with _cache_lock:
        return _entrypoint
