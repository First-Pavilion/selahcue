"""Project matching acceptance and upload evidence into a website candidate."""

import errno
import hashlib
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from .contracts import (
    MAX_MANIFEST_BYTES, ArtifactId, JsonValue, ObjectPlan, PublicationError, VerifiedObject,
    canonical_bytes, headers_match, parse_prepare_receipt, parse_upload_receipt, parse_verification,
    require,
)
from .prepare import (
    PreparedRelease, _absolute, _directory, _read, _write_atomic, load_prepared_release,
    read_regular_file,
)

_VALIDATOR = Path(__file__).absolute().parents[2] / "implementation/marketing/scripts/validate_release_manifest.ts"
_TARGETS: tuple[tuple[ArtifactId, str], ...] = (
    ("windows", "windows-x64"),
    ("universalMac", "macos-arm64"),
    ("universalMac", "macos-x64"),
    ("ubuntu", "ubuntu-24.04-x64"),
)


def _matches(observed: VerifiedObject, plan: ObjectPlan) -> bool:
    return (
        (observed.id, observed.url, observed.observed_size_bytes, observed.observed_sha256)
        == (plan.id, plan.url, plan.size_bytes, plan.sha256)
        and headers_match(observed.headers, plan)
    )


def _project(prepared: PreparedRelease, observations: tuple[VerifiedObject, ...]) -> JsonValue:
    inspections = {inspection.artifact_id: inspection for inspection in prepared.inspections}
    objects = {obj.id: obj for obj in prepared.public_plan.objects}
    observed = {obj.id: obj for obj in observations}
    artifacts: list[JsonValue] = []
    for artifact_id, target in _TARGETS:
        inspection = inspections[artifact_id]
        obj = observed[artifact_id]
        artifacts.append({
            "target": target,
            "architectures": list(inspection.architectures),
            "url": obj.url,
            "filename": objects[artifact_id].filename,
            "size_bytes": obj.observed_size_bytes,
            "sha256": obj.observed_sha256,
            "app_signature": inspection.app_signature,
            "package_signature": inspection.package_signature,
            "notarization": inspection.notarization,
            "publisher": inspection.publisher,
        })
    return {
        "schema_version": 1,
        "status": "published",
        "release_id": prepared.input.release_id,
        "version": prepared.input.version,
        "source_commit": prepared.input.source_commit,
        "artifacts": artifacts,
    }


def _validate_with_website(raw: bytes) -> None:
    try:
        # The validator sees only a private temporary copy of the candidate and no installer credentials.
        with TemporaryDirectory(prefix="installer-manifest-") as directory:
            candidate = Path(directory).resolve() / "candidate.json"
            candidate.write_bytes(raw)
            result = subprocess.run(
                ["node", str(_VALIDATOR), str(candidate)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30, check=False, env={"PATH": os.environ.get("PATH", os.defpath)},
            )
    except (OSError, subprocess.TimeoutExpired):
        raise PublicationError(5, "Cannot run the website manifest validator") from None
    if result.returncode == 2:
        raise PublicationError(2, "Website manifest parser rejected the candidate")
    if result.returncode != 0:
        raise PublicationError(5, "Website manifest validator failed")


def emit_manifest(release_dir: Path, verification_path: Path, out_path: Path) -> Path:
    out = _absolute(out_path)
    require(bool(out.name) and tuple(part.casefold() for part in out.parts[-3:])
            != ("public", "releases", "current.json"), "Expected a separate candidate output file")
    prepared = load_prepared_release(release_dir)
    prepare_raw = read_regular_file(prepared.root / "prepare-receipt.json")
    require(parse_prepare_receipt(prepare_raw) == prepared.prepare_receipt,
            "Prepare receipt changed during manifest emission")
    upload = parse_upload_receipt(read_regular_file(prepared.root / "upload-receipt.json"))
    verification = parse_verification(read_regular_file(verification_path))
    require(upload.input_sha256 == prepared.prepare_receipt.input_sha256
            and upload.prepare_receipt_sha256 == hashlib.sha256(prepare_raw).hexdigest()
            and upload.plan_sha256 == verification.plan_sha256 == prepared.prepare_receipt.plan_sha256,
            "Upload and verification digests must match the prepared release")
    require(verification.verifier_version == (
        f"installer-publication/1 sha256:{prepared.prepare_receipt.publisher_source_sha256}"
    ), "Independent verifier source identity differs")
    upload_observations = tuple(obj.anonymous_readback for obj in upload.objects)
    require(verification.objects != upload_observations, "Independent verification repeats the upload observations")
    for plan, uploaded, independent in zip(
        prepared.public_plan.objects, upload_observations, verification.objects, strict=True
    ):
        require(_matches(uploaded, plan) and _matches(independent, plan),
                "Upload and independent observations must match the prepared objects")

    raw = canonical_bytes(_project(prepared, verification.objects))
    require(len(raw) <= MAX_MANIFEST_BYTES, "Website manifest exceeds its byte limit")
    _validate_with_website(raw)
    try:
        with _directory(out.parent) as parent:
            try:
                _write_atomic(parent, out.name, raw)
            except FileExistsError:
                try:
                    existing = _read(parent, out.name, MAX_MANIFEST_BYTES)
                except OSError:
                    raise PublicationError(2, "Candidate output must be a contained regular file") from None
                require(existing == raw, "Existing candidate output differs")
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            raise PublicationError(2, "Candidate output directory must be a contained directory") from None
        raise PublicationError(5, "Cannot write or sync the candidate output") from None
    return out
