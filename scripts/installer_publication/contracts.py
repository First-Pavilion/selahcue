"""Closed installer publication records. Digests bind evidence custody only."""

from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import json
import re
from typing import Literal
from urllib.parse import quote, unquote

type ArtifactId = Literal["windows", "universalMac", "ubuntu"]
type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

ARTIFACT_IDS = ("windows", "universalMac", "ubuntu")
TARGETS = ("windows-x64", "macos-arm64", "macos-x64", "ubuntu-24.04-x64")
BUCKET = "selahcue-installers"
ENDPOINT = "https://sfo3.digitaloceanspaces.com"
REGION = "sfo3"
PUBLIC_ORIGIN = "https://selahcue-installers.sfo3.digitaloceanspaces.com"
API_ORIGIN = "https://api.selahcueapp.com"
REPOSITORY = "First-Pavilion/selahcue"
CACHE_CONTROL = "public, max-age=31536000, immutable"
ALL_USERS = "http://acs.amazonaws.com/groups/global/AllUsers"
MAX_PACKAGE_BYTES = 4_000_000_000
MAX_JSON_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_STRING_BYTES = 4096
MAX_BUILD_INPUTS = 4096
# Every SourceFile can name one Ref, plus the fixed number of other records/leaves.
MAX_EVIDENCE_FILES = MAX_BUILD_INPUTS + 96
VERSION_CONFIG = "implementation/desktop/crates/selahcue-operator/tauri.conf.json"
PUBLIC_KEY_CONFIG = "implementation/desktop/crates/selahcue-licensing/src/trust.rs"
PUBLIC_KEY_SYMBOL = "PILOT_PUBLIC_KEY"
GATE_IDS = (
    "reviewed-source-profile", "build-artifact-custody", "windows-native",
    "macos-arm64-native", "macos-x64-native", "ubuntu-24.04-native",
    "package-secret-controls", "entitlement-key-enforcement", "cloud-transcription",
    "cloud-notes", "quota-provider-reconciliation", "presentation-offline-degradation",
)

_EXTENSIONS = dict(zip(ARTIFACT_IDS, (".exe", ".dmg", ".deb"), strict=True))
_CONTENT_TYPES = dict(zip(ARTIFACT_IDS, (
    "application/octet-stream", "application/x-apple-diskimage", "application/vnd.debian.binary-package",
), strict=True))
_SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class PublicationError(Exception):
    def __init__(self, exit_code: int, reason: str):
        if exit_code not in (2, 3, 4, 5):
            raise ValueError("Unsupported publication exit code")
        self.exit_code = exit_code
        self.reason = reason[:256]
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class Ref:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class Artifact:
    id: ArtifactId
    path: str
    filename: str
    size_bytes: int
    sha256: str
    build: Ref
    inspection: Ref


@dataclass(frozen=True, slots=True)
class ReleaseInput:
    schema_version: int
    release_id: str
    version: str
    source_commit: str
    profile: Ref
    acceptance: Ref
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True, slots=True)
class BuildCommand:
    cwd: str
    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BuildReceipt:
    schema_version: int
    artifact_id: ArtifactId
    source_commit: str
    version: str
    profile_sha256: str
    repository: str
    toolchain: Ref
    build_commands: tuple[BuildCommand, ...]
    build_log: Ref
    build_input_custody: Ref
    package_metadata: Ref
    filename: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CiBuildReceipt(BuildReceipt):
    kind: Literal["ci"]
    workflow_path: str
    workflow_sha256: str
    run_id: int
    run_attempt: int
    artifact_id_in_ci: str


@dataclass(frozen=True, slots=True)
class LocalBuildReceipt(BuildReceipt):
    kind: Literal["local"]
    build_id: str
    operator: str
    host_os: str
    host_arch: str


@dataclass(frozen=True, slots=True)
class BuildProfile:
    id: ArtifactId
    target_triples: tuple[str, ...]
    command_argv: tuple[str, ...]
    default_features: bool
    selected_features: tuple[str, ...]
    resolved_features: Ref
    release_boundary_check: Ref


@dataclass(frozen=True, slots=True)
class Profile:
    schema_version: int
    source_commit: str
    version: str
    api_origin: str
    entitlement_key_id: str
    entitlement_public_key_sha256: str
    source_evidence: Ref
    builds: tuple[BuildProfile, ...]


@dataclass(frozen=True, slots=True)
class SourceFile:
    source_path: str
    evidence: Ref


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    schema_version: int
    version_config: SourceFile
    public_key_config: SourceFile
    public_key_symbol: str
    public_key: Ref
    build_inputs: tuple[SourceFile, ...]


@dataclass(frozen=True, slots=True)
class Inspection:
    schema_version: int
    artifact_id: ArtifactId
    package_sha256: str
    architectures: tuple[str, ...]
    architecture_evidence: Ref
    version_evidence: Ref
    app_signature: str
    package_signature: str
    notarization: str
    publisher: str | None
    signature_evidence: Ref
    bundle_scan: Ref
    payload_scan: Ref
    development_key_scan: Ref
    scan_positive_controls: Ref
    build_input_custody: Ref


@dataclass(frozen=True, slots=True)
class InspectionVersionEvidence:
    schema_version: int
    artifact_id: ArtifactId
    package_sha256: str
    version: str
    entitlement_key_id: str
    entitlement_public_key_sha256: str
    evidence: Ref


@dataclass(frozen=True, slots=True)
class AcceptedArtifact:
    id: ArtifactId
    sha256: str


@dataclass(frozen=True, slots=True)
class Gate:
    id: str
    evidence: Ref


@dataclass(frozen=True, slots=True)
class Acceptance:
    schema_version: int
    source_commit: str
    version: str
    profile_sha256: str
    artifacts: tuple[AcceptedArtifact, ...]
    reviewer: str
    reviewed_at: str
    decision: str
    gates: tuple[Gate, ...]


@dataclass(frozen=True, slots=True)
class PackageMapping:
    id: ArtifactId
    original_path: str
    snapshot_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class EvidenceMapping:
    original_path: str
    snapshot_path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PrepareReceipt:
    schema_version: int
    input_sha256: str
    plan_sha256: str
    source_commit: str
    publisher_source_sha256: str
    created_at: str
    packages: tuple[PackageMapping, ...]
    evidence: tuple[EvidenceMapping, ...]


@dataclass(frozen=True, slots=True)
class ObjectPlan:
    id: ArtifactId
    key: str
    url: str
    filename: str
    size_bytes: int
    sha256: str
    content_type: str
    content_disposition: str
    cache_control: str


@dataclass(frozen=True, slots=True)
class PublicPlan:
    schema_version: int
    release_id: str
    version: str
    source_commit: str
    objects: tuple[ObjectPlan, ...]


@dataclass(frozen=True, slots=True)
class ResponseHeaders:
    content_type: str
    content_disposition: str
    cache_control: str
    content_length: int
    content_encoding: None


@dataclass(frozen=True, slots=True)
class HeadObservation(ResponseHeaders):
    request_id: str | None


@dataclass(frozen=True, slots=True)
class Grant:
    grantee_type: str
    grantee_id: str
    permission: str


@dataclass(frozen=True, slots=True)
class ObjectAcl:
    owner_id: str
    grants: tuple[Grant, ...]


@dataclass(frozen=True, slots=True)
class VerifiedObject:
    id: ArtifactId
    url: str
    http_status: int
    headers: ResponseHeaders
    observed_size_bytes: int
    observed_sha256: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class VerificationReceipt:
    schema_version: int
    plan_sha256: str
    verifier_version: str
    started_at: str
    finished_at: str
    objects: tuple[VerifiedObject, ...]


@dataclass(frozen=True, slots=True)
class UploadedObject:
    id: ArtifactId
    key: str
    sha256: str
    size_bytes: int
    put_outcome: str
    head: HeadObservation
    acl: ObjectAcl
    anonymous_readback: VerifiedObject


@dataclass(frozen=True, slots=True)
class UploadReceipt:
    schema_version: int
    plan_sha256: str
    input_sha256: str
    prepare_receipt_sha256: str
    tool_version: str
    started_at: str
    finished_at: str
    objects: tuple[UploadedObject, ...]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PublicationError(2, reason)


def _number(text: str) -> float:
    value = float(text)
    require(-float("inf") < value < float("inf"), "Non-finite JSON number")
    return value


def _non_finite(_: str) -> None:
    raise PublicationError(2, "Non-finite JSON number")


def _object(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result = dict(pairs)
    require(len(result) == len(pairs), "Duplicate JSON key")
    return result


def read_json(raw: bytes) -> JsonValue:
    require(len(raw) <= MAX_JSON_BYTES, "JSON document exceeds its byte limit")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_non_finite, parse_float=_number)
    except (ValueError, RecursionError) as exc:
        raise PublicationError(2, "Invalid bounded UTF-8 JSON") from exc


def canonical_bytes(value: JsonValue) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def record_bytes(value) -> bytes:
    raw = canonical_bytes(asdict(value))
    require(len(raw) <= MAX_JSON_BYTES, "JSON record exceeds its byte limit")
    return raw


def _text(value, *, argument=False) -> str:
    require(isinstance(value, str), "Expected a string field")
    try:
        length = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise PublicationError(2, "Invalid UTF-8 string field") from exc
    require(length <= MAX_STRING_BYTES and "\0" not in value, "Invalid bounded string field")
    if not argument:
        require(bool(value) and value.strip() == value and not _CONTROL.search(value), "Invalid text field")
    return value


def _nullable_text(value) -> str | None:
    return None if value is None else _text(value)


def _enum(value, choices):
    require(isinstance(value, str) and value in choices, "Unsupported enumerated field")
    return value


def _integer(value, low=1, high=None) -> int:
    require(type(value) is int and low <= value and (high is None or value <= high), "Invalid integer field")
    return value


def _size(value) -> int:
    return _integer(value, high=MAX_PACKAGE_BYTES)


def _boolean(value) -> bool:
    require(type(value) is bool, "Expected a Boolean field")
    return value


def _hex(value, length):
    value = _text(value)
    require(re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None, "Invalid lowercase digest or identifier")
    return value


def _sha(value) -> str:
    return _hex(value, 64)


def _release_id(value) -> str:
    value = _text(value)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", value) is not None, "Invalid release or build identifier")
    return value


def semver(value) -> str:
    value = _text(value)
    match = _SEMVER.fullmatch(value)
    require(match is not None, "Invalid packaged SemVer")
    prerelease = match.group("prerelease")
    if prerelease is not None:
        require(all(not (part.isdigit() and len(part) > 1 and part.startswith("0")) for part in prerelease.split(".")),
                "Invalid numeric SemVer prerelease")
    return value


def _timestamp(value) -> str:
    value = _text(value)
    require(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|\+00:00)", value)
            is not None, "Expected an RFC3339 UTC timestamp")
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise PublicationError(2, "Invalid UTC timestamp") from exc
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def contained_path(value) -> str:
    value = _text(value)
    require("\\" not in value and not re.match(r"[A-Za-z]:", value)
            and not any(part in ("", ".", "..") for part in value.split("/")),
            "Expected a contained relative file path")
    return value


def nonsecret_path(value) -> str:
    value = contained_path(value)
    for part in value.lower().split("/"):
        require(not (part.startswith(".env") or part in {".git", ".aws", ".ssh", ".gnupg", ".netrc", "credentials"}
                     or part.startswith(("secrets.", "private-key.", "signing-key."))
                     or part.endswith((".pem", ".key", ".p12", ".pfx", ".env"))),
                "Credential paths cannot be retained as evidence")
    return value


def _source_path(value) -> str:
    value = nonsecret_path(value)
    require(not any(char in value for char in ":~^?*[]@{"), "Git revision syntax is forbidden in source paths")
    return value


def _workflow_path(value) -> str:
    value = _source_path(value)
    require(re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", value) is not None,
            "CI workflow must be a GitHub Actions workflow path")
    return value


def _filename(value, artifact_id) -> str:
    value = _text(value)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ ()+-]{0,179}", value) is not None
            and not value.endswith((".", " ")) and value.endswith(_EXTENSIONS[artifact_id]),
            "Invalid installer basename or extension")
    return value


def _array(value, parse, low, high):
    require(isinstance(value, list) and low <= len(value) <= high, "Invalid array cardinality")
    return tuple(parse(item) for item in value)


def _distinct(records, attribute: str) -> None:
    require(len({getattr(row, attribute) for row in records}) == len(records), "Duplicate record identity")


def _artifacts(value, parse, *, ordered=False):
    records = _array(value, parse, 3, 3)
    ids = tuple(record.id for record in records)
    require(ids == ARTIFACT_IDS if ordered else set(ids) == set(ARTIFACT_IDS), "Invalid artifact identities or order")
    return records


def _argv(value) -> tuple[str, ...]:
    args = _array(value, lambda arg: _text(arg, argument=True), 1, 4096)
    require(bool(args[0].strip()), "Command executable field is empty")
    return args


def _record(value, cls):
    names = {field.name for field in fields(cls)}
    require(isinstance(value, dict) and set(value) == names, f"Invalid {cls.__name__} field set")
    if "schema_version" in names:
        _integer(value["schema_version"], 1, 1)
    return value.copy()


def _ref(value) -> Ref:
    row = _record(value, Ref)
    return Ref(nonsecret_path(row["path"]), _sha(row["sha256"]))


def _artifact(value) -> Artifact:
    row = _record(value, Artifact)
    artifact_id = _enum(row["id"], ARTIFACT_IDS)
    path = nonsecret_path(row["path"])
    filename = _filename(row["filename"], artifact_id)
    require(path.rsplit("/", 1)[-1] == filename, "Package path and basename differ")
    return Artifact(artifact_id, path, filename, _size(row["size_bytes"]), _sha(row["sha256"]),
                    _ref(row["build"]), _ref(row["inspection"]))


def parse_release_input(raw: bytes) -> ReleaseInput:
    row = _record(read_json(raw), ReleaseInput)
    artifacts = _artifacts(row["artifacts"], _artifact)
    _distinct(artifacts, "path")
    return ReleaseInput(1, _release_id(row["release_id"]), semver(row["version"]), _hex(row["source_commit"], 40),
                        _ref(row["profile"]), _ref(row["acceptance"]), artifacts)


def _command(value) -> BuildCommand:
    row = _record(value, BuildCommand)
    return BuildCommand(_text(row["cwd"]), _argv(row["argv"]))


def parse_build_receipt(raw: bytes) -> CiBuildReceipt | LocalBuildReceipt:
    value = read_json(raw)
    kind = value.get("kind") if isinstance(value, dict) else None
    _enum(kind, ("ci", "local"))
    cls = CiBuildReceipt if kind == "ci" else LocalBuildReceipt
    row = _record(value, cls)
    row.update(
        artifact_id=_enum(row["artifact_id"], ARTIFACT_IDS),
        source_commit=_hex(row["source_commit"], 40), version=semver(row["version"]),
        profile_sha256=_sha(row["profile_sha256"]), repository=_enum(row["repository"], (REPOSITORY,)),
        toolchain=_ref(row["toolchain"]), build_commands=_array(row["build_commands"], _command, 1, 4096),
        build_log=_ref(row["build_log"]), build_input_custody=_ref(row["build_input_custody"]),
        package_metadata=_ref(row["package_metadata"]), filename=_filename(row["filename"], row["artifact_id"]),
        size_bytes=_size(row["size_bytes"]), sha256=_sha(row["sha256"]),
    )
    if kind == "ci":
        row.update(
            workflow_path=_workflow_path(row["workflow_path"]), workflow_sha256=_sha(row["workflow_sha256"]),
            run_id=_integer(row["run_id"]), run_attempt=_integer(row["run_attempt"]),
            artifact_id_in_ci=_text(row["artifact_id_in_ci"]),
        )
        return CiBuildReceipt(**row)
    row.update(build_id=_release_id(row["build_id"]), operator=_text(row["operator"]),
               host_os=_text(row["host_os"]), host_arch=_enum(row["host_arch"], ("arm64", "x64")))
    return LocalBuildReceipt(**row)


def _profile_build(value) -> BuildProfile:
    row = _record(value, BuildProfile)
    triples = _array(row["target_triples"], _text, 1, 4096)
    features = _array(row["selected_features"], _text, 0, 4096)
    require(len(set(triples)) == len(triples) and len(set(features)) == len(features), "Duplicate build profile entry")
    return BuildProfile(
        _enum(row["id"], ARTIFACT_IDS), triples, _argv(row["command_argv"]), _boolean(row["default_features"]),
        features, _ref(row["resolved_features"]), _ref(row["release_boundary_check"]),
    )


def parse_profile(raw: bytes) -> Profile:
    row = _record(read_json(raw), Profile)
    return Profile(
        1, _hex(row["source_commit"], 40), semver(row["version"]), _enum(row["api_origin"], (API_ORIGIN,)),
        _hex(row["entitlement_key_id"], 8), _sha(row["entitlement_public_key_sha256"]),
        _ref(row["source_evidence"]), _artifacts(row["builds"], _profile_build),
    )


def _source_file(value) -> SourceFile:
    row = _record(value, SourceFile)
    return SourceFile(_source_path(row["source_path"]), _ref(row["evidence"]))


def parse_source_evidence(raw: bytes) -> SourceEvidence:
    row = _record(read_json(raw), SourceEvidence)
    version_config = _source_file(row["version_config"])
    public_key_config = _source_file(row["public_key_config"])
    require(version_config.source_path == VERSION_CONFIG and public_key_config.source_path == PUBLIC_KEY_CONFIG,
            "Unexpected source configuration path")
    build_inputs = _array(row["build_inputs"], _source_file, 1, MAX_BUILD_INPUTS)
    _distinct(build_inputs, "source_path")
    return SourceEvidence(1, version_config, public_key_config, _enum(row["public_key_symbol"], (PUBLIC_KEY_SYMBOL,)),
                          _ref(row["public_key"]), build_inputs)


def parse_inspection(raw: bytes) -> Inspection:
    row = _record(read_json(raw), Inspection)
    artifact_id = _enum(row["artifact_id"], ARTIFACT_IDS)
    architectures = _array(row["architectures"], _text, 1, 2)
    app_signature = _enum(row["app_signature"], ("unsigned", "ad_hoc", "verified", "not_applicable"))
    package_signature = _enum(row["package_signature"], ("unsigned", "verified"))
    notarization = _enum(row["notarization"], ("not_notarized", "not_applicable"))
    publisher = _nullable_text(row["publisher"])
    if artifact_id == "universalMac":
        require(architectures == ("arm64", "x64"), "The final macOS DMG must have both slices")
        require((app_signature, package_signature, notarization, publisher) == ("ad_hoc", "unsigned", "not_notarized", None),
                "Invalid macOS signature observations")
    else:
        require(architectures == ("x64",), "Invalid x64 package architecture")
        require(notarization == "not_applicable" and app_signature != "ad_hoc"
                and (artifact_id != "windows" or app_signature != "not_applicable"),
                "Invalid non-Mac signature observations")
        require((publisher is not None) == ("verified" in (app_signature, package_signature)),
                "Publisher and observed signer differ")
    for field in ("architecture_evidence", "version_evidence", "signature_evidence", "bundle_scan",
                  "payload_scan", "development_key_scan", "scan_positive_controls", "build_input_custody"):
        row[field] = _ref(row[field])
    row.update(package_sha256=_sha(row["package_sha256"]), architectures=architectures, publisher=publisher)
    return Inspection(**row)


def parse_inspection_version(raw: bytes) -> InspectionVersionEvidence:
    row = _record(read_json(raw), InspectionVersionEvidence)
    return InspectionVersionEvidence(
        1, _enum(row["artifact_id"], ARTIFACT_IDS), _sha(row["package_sha256"]), semver(row["version"]),
        _hex(row["entitlement_key_id"], 8), _sha(row["entitlement_public_key_sha256"]), _ref(row["evidence"]),
    )


def _accepted_artifact(value) -> AcceptedArtifact:
    row = _record(value, AcceptedArtifact)
    return AcceptedArtifact(_enum(row["id"], ARTIFACT_IDS), _sha(row["sha256"]))


def _gate(value) -> Gate:
    row = _record(value, Gate)
    return Gate(_enum(row["id"], GATE_IDS), _ref(row["evidence"]))


def parse_acceptance(raw: bytes) -> Acceptance:
    row = _record(read_json(raw), Acceptance)
    gates = _array(row["gates"], _gate, len(GATE_IDS), len(GATE_IDS))
    _distinct(gates, "id")
    return Acceptance(
        1, _hex(row["source_commit"], 40), semver(row["version"]), _sha(row["profile_sha256"]),
        _artifacts(row["artifacts"], _accepted_artifact), _text(row["reviewer"]), _timestamp(row["reviewed_at"]),
        _enum(row["decision"], ("accepted_for_publication",)), gates,
    )


def _snapshot_path(value, directory: str) -> str:
    value = contained_path(value)
    require(value.startswith(directory + "/"), "Snapshot path leaves its private directory")
    return value


def _package_mapping(value) -> PackageMapping:
    row = _record(value, PackageMapping)
    return PackageMapping(_enum(row["id"], ARTIFACT_IDS), nonsecret_path(row["original_path"]),
                          _snapshot_path(row["snapshot_path"], "packages"), _size(row["size_bytes"]), _sha(row["sha256"]))


def _evidence_mapping(value) -> EvidenceMapping:
    row = _record(value, EvidenceMapping)
    return EvidenceMapping(nonsecret_path(row["original_path"]), _snapshot_path(row["snapshot_path"], "evidence"),
                           _sha(row["sha256"]))


def parse_prepare_receipt(raw: bytes) -> PrepareReceipt:
    row = _record(read_json(raw), PrepareReceipt)
    packages = _artifacts(row["packages"], _package_mapping, ordered=True)
    evidence = _array(row["evidence"], _evidence_mapping, 1, MAX_EVIDENCE_FILES)
    _distinct(packages + evidence, "original_path")
    _distinct(packages + evidence, "snapshot_path")
    return PrepareReceipt(
        1, _sha(row["input_sha256"]), _sha(row["plan_sha256"]), _hex(row["source_commit"], 40),
        _sha(row["publisher_source_sha256"]), _timestamp(row["created_at"]), packages, evidence,
    )


def derive_object(artifact_id: ArtifactId, version: str, filename: str, size: int, sha256: str) -> ObjectPlan:
    segments = ("installers", version, sha256, filename)
    key = _text("/".join(segments))
    url = _text(PUBLIC_ORIGIN + "/" + "/".join(quote(segment, safe="") for segment in segments))
    return ObjectPlan(artifact_id, key, url, filename, size, sha256, _CONTENT_TYPES[artifact_id],
                      f'attachment; filename="{filename}"', CACHE_CONTROL)


def _object_plan(value, version: str) -> ObjectPlan:
    row = _record(value, ObjectPlan)
    artifact_id = _enum(row["id"], ARTIFACT_IDS)
    expected = derive_object(artifact_id, version, _filename(row["filename"], artifact_id),
                             _size(row["size_bytes"]), _sha(row["sha256"]))
    require(row == asdict(expected), "Public object fields differ from their derived identity")
    return expected


def parse_object_plan(raw: bytes) -> ObjectPlan:
    value = read_json(raw)
    row = _record(value, ObjectPlan)
    key = _text(row["key"])
    parts = key.split("/")
    require(len(parts) == 4, "Invalid public object key")
    return _object_plan(value, semver(parts[1]))


def parse_public_plan(raw: bytes) -> PublicPlan:
    row = _record(read_json(raw), PublicPlan)
    version = semver(row["version"])
    objects = _artifacts(row["objects"], lambda value: _object_plan(value, version), ordered=True)
    return PublicPlan(1, _release_id(row["release_id"]), version, _hex(row["source_commit"], 40), objects)


def expected_cache_control(value: str) -> bool:
    directives = tuple("=".join(piece.strip() for piece in part.lower().split("=")) for part in value.split(","))
    return len(directives) == 3 and set(directives) == {"public", "max-age=31536000", "immutable"}


def _headers(value, *, head=False) -> ResponseHeaders | HeadObservation:
    row = _record(value, HeadObservation if head else ResponseHeaders)
    require(row["content_encoding"] is None, "Content encoding must be absent")
    common = (
        _text(row["content_type"]), _text(row["content_disposition"]), _text(row["cache_control"]),
        _size(row["content_length"]), None,
    )
    if head:
        return HeadObservation(*common, _nullable_text(row["request_id"]))
    return ResponseHeaders(*common)


def headers_match(headers: ResponseHeaders, plan: ObjectPlan, *, authenticated=False) -> bool:
    cache_matches = headers.cache_control == plan.cache_control if authenticated else expected_cache_control(headers.cache_control)
    return (headers.content_type == plan.content_type and headers.content_disposition == plan.content_disposition
            and cache_matches and headers.content_length == plan.size_bytes and headers.content_encoding is None)


def _verification_plan(verified: VerifiedObject) -> ObjectPlan:
    require(verified.url.startswith(PUBLIC_ORIGIN + "/"), "Unexpected public installer origin")
    parts = verified.url[len(PUBLIC_ORIGIN) + 1:].split("/")
    require(len(parts) == 4, "Invalid public installer URL")
    try:
        version = semver(unquote(parts[1], errors="strict"))
        filename = _filename(unquote(parts[3], errors="strict"), verified.id)
    except UnicodeDecodeError as exc:
        raise PublicationError(2, "Invalid encoded public installer URL") from exc
    plan = derive_object(verified.id, version, filename, verified.observed_size_bytes, verified.observed_sha256)
    require(verified.url == plan.url, "Public installer URL differs from its derived identity")
    return plan


def _verified_object(value) -> VerifiedObject:
    row = _record(value, VerifiedObject)
    headers = _headers(row["headers"])
    verified = VerifiedObject(
        _enum(row["id"], ARTIFACT_IDS), _text(row["url"]), _integer(row["http_status"], 200, 200),
        headers, _size(row["observed_size_bytes"]), _sha(row["observed_sha256"]), _timestamp(row["completed_at"]),
    )
    require(headers_match(headers, _verification_plan(verified)), "Verified response headers differ from object identity")
    return verified


def parse_verified_object(raw: bytes) -> VerifiedObject:
    return _verified_object(read_json(raw))


def _timeline(start: str, finish: str, completions) -> None:
    started, finished = datetime.fromisoformat(start), datetime.fromisoformat(finish)
    require(started <= finished and all(started <= datetime.fromisoformat(at) <= finished for at in completions),
            "Receipt observation timestamps fall outside its invocation")


def parse_verification(raw: bytes) -> VerificationReceipt:
    row = _record(read_json(raw), VerificationReceipt)
    start, finish = _timestamp(row["started_at"]), _timestamp(row["finished_at"])
    objects = _artifacts(row["objects"], _verified_object, ordered=True)
    _timeline(start, finish, (entry.completed_at for entry in objects))
    return VerificationReceipt(1, _sha(row["plan_sha256"]), _text(row["verifier_version"]), start, finish, objects)


def _grant(value) -> Grant:
    row = _record(value, Grant)
    return Grant(_text(row["grantee_type"]), _text(row["grantee_id"]), _text(row["permission"]))


def _acl(value) -> ObjectAcl:
    row = _record(value, ObjectAcl)
    owner = _text(row["owner_id"])
    grants = _array(row["grants"], _grant, 2, 2)
    require(set(grants) == {Grant("CanonicalUser", owner, "FULL_CONTROL"), Grant("Group", ALL_USERS, "READ")},
            "Unexpected normalized object ACL")
    return ObjectAcl(owner, grants)


def _uploaded_object(value) -> UploadedObject:
    row = _record(value, UploadedObject)
    verified = _verified_object(row["anonymous_readback"])
    plan = _verification_plan(verified)
    artifact_id = _enum(row["id"], ARTIFACT_IDS)
    key, sha256, size = _text(row["key"]), _sha(row["sha256"]), _size(row["size_bytes"])
    require((artifact_id, key, sha256, size) == (plan.id, plan.key, plan.sha256, plan.size_bytes),
            "Uploaded object and anonymous readback differ")
    head = _headers(row["head"], head=True)
    require(headers_match(head, plan, authenticated=True), "Authenticated HEAD differs from object identity")
    outcome = _enum(row["put_outcome"], ("created", "reused_verified", "unknown_but_verified"))
    return UploadedObject(artifact_id, key, sha256, size, outcome, head, _acl(row["acl"]), verified)


def parse_upload_receipt(raw: bytes) -> UploadReceipt:
    row = _record(read_json(raw), UploadReceipt)
    start, finish = _timestamp(row["started_at"]), _timestamp(row["finished_at"])
    objects = _artifacts(row["objects"], _uploaded_object, ordered=True)
    _timeline(start, finish, (entry.anonymous_readback.completed_at for entry in objects))
    return UploadReceipt(1, _sha(row["plan_sha256"]), _sha(row["input_sha256"]), _sha(row["prepare_receipt_sha256"]),
                         _text(row["tool_version"]), start, finish, objects)
