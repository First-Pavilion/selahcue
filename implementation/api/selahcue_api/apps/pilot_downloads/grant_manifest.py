"""Bounded promoted-release consumer. P11 owns real publication and promotion.

Only a complete, verified three-platform set is grantable. An object key is
content addressed; P10 must enforce no overwrite of those immutable keys.
"""

from dataclasses import dataclass
import hashlib
import json
import os
import re
import stat

from selahcue_api.apps.pilot_downloads.policy import PilotRegistrationError


COHORT_CUTOFF = 1809129599
MAX_MANIFEST_BYTES = 65536
PLATFORMS = {"Windows": ("x86_64",), "Ubuntu": ("x86_64",), "macOS": ("x86_64", "aarch64")}
SIGNING_STATES = {
    "Windows": {"authenticode_verified", "unsigned_pilot_approved"},
    "Ubuntu": {"not_required"}, "macOS": {"developer_id_notarized_stapled"},
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def identifier(value, maximum=80):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0," + str(maximum - 1) + r"}", value) is not None


def integer(value):
    return type(value) is int


@dataclass(frozen=True, repr=False)
class Artifact:
    artifact_id: str
    platform: str
    architectures: tuple[str, ...]
    object_key: str
    sha256: str
    size_bytes: int
    credentials_expires_at: int


@dataclass(frozen=True, repr=False)
class Manifest:
    release_id: str
    expires_at: int
    artifacts: tuple[Artifact, ...]


def load_manifest(policy, now: int) -> Manifest:
    """Hash the exact bounded bytes consumed; no remote fetch, append or cache."""
    try:
        descriptor = os.open(policy.manifest_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError
            raw = source.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES or hashlib.sha256(raw).hexdigest() != policy.manifest_sha256:
            raise ValueError
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        root_keys = {"schema_version", "manifest_id", "release_id", "cohort_id", "version", "source_sha", "promoted", "promoted_at", "expires_at", "artifacts"}
        if (not isinstance(value, dict) or set(value) != root_keys or
                type(value["schema_version"]) is not int or value["schema_version"] != 1 or
                value["promoted"] is not True or value["cohort_id"] != policy.cohort_id or
                not all(identifier(value[k]) for k in ("manifest_id", "release_id", "cohort_id", "version")) or
                not isinstance(value["source_sha"], str) or not re.fullmatch(r"[a-f0-9]{40}", value["source_sha"]) or
                not integer(value["promoted_at"]) or not 0 < value["promoted_at"] <= now or
                not integer(value["expires_at"]) or not now < value["expires_at"] <= COHORT_CUTOFF):
            raise ValueError
        entries = value["artifacts"]
        if not isinstance(entries, list) or len(entries) != 3:
            raise ValueError
        artifacts = []
        ids = set()
        platforms = set()
        artifact_keys = {"artifact_id", "platform", "architectures", "object_key", "sha256", "size_bytes", "available", "verified", "credentials_expires_at", "signing"}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != artifact_keys:
                raise ValueError
            name, platform = entry["artifact_id"], entry["platform"]
            if (not identifier(name) or name in ids or not isinstance(platform, str) or platform not in PLATFORMS or platform in platforms or
                    entry["architectures"] != list(PLATFORMS[platform]) or
                    entry["available"] is not True or entry["verified"] is not True or
                    entry["signing"] != policy.signing_requirements[platform] or
                    not isinstance(entry["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]) or
                    not integer(entry["size_bytes"]) or not 0 < entry["size_bytes"] <= 20 * 1024 ** 3 or
                    not integer(entry["credentials_expires_at"]) or not now < entry["credentials_expires_at"] <= COHORT_CUTOFF):
                raise ValueError
            prefix = "pilot/" + value["release_id"] + "/" + entry["sha256"] + "/"
            key = entry["object_key"]
            if not isinstance(key, str) or not key.startswith(prefix) or not identifier(key[len(prefix):], 160):
                raise ValueError
            artifacts.append(Artifact(name, platform, tuple(entry["architectures"]), key, entry["sha256"], entry["size_bytes"], entry["credentials_expires_at"]))
            ids.add(name)
            platforms.add(platform)
        return Manifest(value["release_id"], value["expires_at"], tuple(artifacts))
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, RecursionError, OverflowError):
        raise PilotRegistrationError("download_manifest_unavailable", 503) from None
