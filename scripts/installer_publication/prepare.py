"""Offline preparation and loading of a private installer custody directory."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import time
from typing import BinaryIO
from uuid import uuid4

from .contracts import (
    ARTIFACT_IDS,
    MAX_JSON_BYTES,
    MAX_PACKAGE_BYTES,
    PUBLIC_KEY_SYMBOL,
    REPOSITORY,
    Acceptance,
    CiBuildReceipt,
    EvidenceMapping,
    Inspection,
    LocalBuildReceipt,
    PackageMapping,
    PrepareReceipt,
    Profile,
    PublicationError,
    PublicPlan,
    Ref,
    ReleaseInput,
    canonical_bytes,
    derive_object,
    nonsecret_path,
    parse_acceptance,
    parse_build_receipt,
    parse_inspection,
    parse_inspection_version,
    parse_prepare_receipt,
    parse_profile,
    parse_public_plan,
    parse_release_input,
    parse_source_evidence,
    read_json,
    record_bytes,
    require,
    semver,
    utc_now,
)

_INPUT = "input.json"
_PLAN = "public-plan.json"
_RECEIPT = "prepare-receipt.json"
_CHUNK = 1024 * 1024
MAX_OPAQUE_EVIDENCE_BYTES = 64 * _CHUNK
MAX_TOTAL_EVIDENCE_BYTES = 512 * _CHUNK
_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
_DIR_FLAGS = _READ_FLAGS | os.O_DIRECTORY
_WRITE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
_PACKAGE_SOURCE_FILES = (
    "scripts/installer_publication/__init__.py",
    "scripts/installer_publication/contracts.py",
    "scripts/installer_publication/prepare.py",
)
_LATER_SOURCE_FILES = (
    "scripts/installer_publication/public_verify.py",
    "scripts/installer_publication/upload.py",
    "scripts/installer_publication/manifest.py",
    "scripts/publish_installers.py",
    "implementation/marketing/scripts/validate_release_manifest.ts",
    "implementation/marketing/src/lib/releases/downloads.ts",
)
_ORIGINS = frozenset(
    prefix.encode() + REPOSITORY.lower().encode() + suffix.encode()
    for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/")
    for suffix in ("", ".git")
)
_KEY_DECLARATION = re.compile(
    rb"(?m)^[ \t]*const[ \t]+" + PUBLIC_KEY_SYMBOL.encode() +
    rb"[ \t]*:[ \t]*\[u8;[ \t]*(?:32|PUBLIC_KEY_BYTES)\][ \t]*=[ \t]*\[(?P<bytes>[^\[\]]*)\][ \t]*;"
)
_KEY_WIDTH = re.compile(rb"(?m)^[ \t]*pub const PUBLIC_KEY_BYTES: usize = 32;[ \t]*$")


@dataclass(frozen=True, slots=True)
class PreparedRelease:
    root: Path
    input: ReleaseInput
    profile: Profile
    inspections: tuple[Inspection, ...]
    acceptance: Acceptance
    prepare_receipt: PrepareReceipt
    public_plan: PublicPlan


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _absolute(path: Path) -> Path:
    path = Path(path).absolute()
    require(".." not in path.parts and path.anchor == "/", "Invalid local path")
    return path


@contextmanager
def _subdirectory(parent: int, parts: tuple[str, ...]) -> Iterator[int]:
    current = os.dup(parent)
    try:
        for part in parts:
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=current)
            os.close(current)
            current = next_fd
        yield current
    finally:
        os.close(current)


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    path = _absolute(path)
    root_fd = os.open("/", _DIR_FLAGS)
    try:
        with _subdirectory(root_fd, path.parts[1:]) as fd:
            yield fd
    finally:
        os.close(root_fd)


@contextmanager
def _regular(root: int, relative: str, maximum: int) -> Iterator[tuple[BinaryIO, int]]:
    parts = relative.split("/")
    with _subdirectory(root, tuple(parts[:-1])) as directory:
        fd = os.open(parts[-1], _READ_FLAGS, dir_fd=directory)
        with os.fdopen(fd, "rb") as file:
            before = os.fstat(file.fileno())
            require(stat.S_ISREG(before.st_mode), "Evidence and packages must be regular files")
            require(before.st_size <= maximum, "File exceeds its byte limit")
            yield file, before.st_size
            after = os.fstat(file.fileno())
            # Reopen path components relative to the same root to detect a swapped ancestor or entry.
            with _subdirectory(root, tuple(parts[:-1])) as current:
                linked = os.stat(parts[-1], dir_fd=current, follow_symlinks=False)
            require(_identity(before) == _identity(after) == _identity(linked), "File changed during custody read")


def _read(root: int, relative: str, maximum: int = MAX_JSON_BYTES) -> bytes:
    with _regular(root, relative, maximum) as (file, size):
        raw = file.read(maximum + 1)
        require(len(raw) == size, "File length changed during custody read")
    return raw


def read_regular_file(path: Path, maximum: int = MAX_JSON_BYTES) -> bytes:
    path = _absolute(path)
    try:
        with _directory(path.parent) as root:
            return _read(root, path.name, maximum)
    except OSError as exc:
        raise PublicationError(2, "Cannot read a contained regular file") from exc


def _stream_hash(source: BinaryIO, size: int, destination: BinaryIO | None = None) -> str:
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        chunk = source.read(min(_CHUNK, remaining))
        require(bool(chunk), "File was truncated during custody read")
        if destination is not None and destination.write(chunk) != len(chunk):
            raise PublicationError(5, "Short snapshot write")
        digest.update(chunk)
        remaining -= len(chunk)
    require(not source.read(1), "File grew during custody read")
    return digest.hexdigest()


def _hash(root: int, relative: str, maximum: int, expected_size: int) -> str:
    with _regular(root, relative, maximum) as (file, size):
        require(size == expected_size, "Package length differs from its custody mapping")
        return _stream_hash(file, size)


def hash_regular_file(path: Path, expected_size: int) -> str:
    path = _absolute(path)
    try:
        with _directory(path.parent) as root:
            return _hash(root, path.name, MAX_PACKAGE_BYTES, expected_size)
    except OSError as exc:
        raise PublicationError(2, "Cannot hash a contained regular package") from exc


def _write_new(root: int, filename: str, raw: bytes) -> None:
    fd = os.open(filename, _WRITE_FLAGS, 0o600, dir_fd=root)
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fchmod(file.fileno(), 0o400)
        os.fsync(file.fileno())


def _write_atomic(root: int, filename: str, raw: bytes) -> None:
    temporary = ".prepare-" + uuid4().hex
    try:
        _write_new(root, temporary, raw)
        # The receipt and plan paths are inside the freshly-created exclusive release directory.
        # A hard link installs the complete file without replacing an unexpected existing entry.
        os.link(temporary, filename, src_dir_fd=root, dst_dir_fd=root, follow_symlinks=False)
        try:
            os.unlink(temporary, dir_fd=root)
            os.fsync(root)
        except OSError:
            os.unlink(filename, dir_fd=root)
            raise
    finally:
        try:
            os.unlink(temporary, dir_fd=root)
        except FileNotFoundError:
            pass


def publisher_source_sha256() -> str:
    root_path = Path(__file__).absolute().parents[2]
    digests = {}
    try:
        with _directory(root_path) as root:
            for relative in _PACKAGE_SOURCE_FILES + _LATER_SOURCE_FILES:
                try:
                    digests[relative] = _sha(_read(root, relative))
                except FileNotFoundError:
                    if relative in _PACKAGE_SOURCE_FILES:
                        raise
    except OSError as exc:
        raise PublicationError(5, "Cannot read publisher source inventory") from exc
    return _sha(canonical_bytes(digests))


class _SourceCheckout:
    def __init__(self, root: Path, fd: int, commit: str):
        self.root = root
        self.fd = fd
        self.commit = commit

    def _git(self, *argv: str, code_one: bool = False, hash_size: int | None = None) -> bytes:
        # Receipt command_argv and build_commands are never used here.
        args = ["git", "--no-optional-locks", "--no-replace-objects", "-C", str(self.root),
                "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                "-c", "core.untrackedCache=false", "-c", "core.attributesFile=/dev/null", *argv]
        env = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1"}
        deadline = time.monotonic() + 30
        output = bytearray()
        digest = hashlib.sha256() if hash_size is not None else None
        limit = hash_size if hash_size is not None else MAX_JSON_BYTES
        count = 0
        try:
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  stdin=subprocess.DEVNULL, env=env) as process:
                try:
                    with selectors.DefaultSelector() as ready:
                        ready.register(process.stdout, selectors.EVENT_READ)
                        while True:
                            if not ready.select(max(0, deadline - time.monotonic())):
                                raise PublicationError(5, "Git source inspection timed out")
                            chunk = os.read(process.stdout.fileno(), min(_CHUNK, limit + 1 - count))
                            if not chunk:
                                break
                            count += len(chunk)
                            require(count <= limit, "Git source inspection exceeded its output limit")
                            if digest is None:
                                output.extend(chunk)
                            else:
                                digest.update(chunk)
                    returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
                finally:
                    if process.poll() is None:
                        process.kill()
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PublicationError(5, "Git source inspection failed") from exc
        require(returncode == 0 or (code_one and returncode == 1), "Git rejected the supplied source checkout")
        if digest is not None:
            require(count == hash_size, "Git source blob length changed")
            return digest.hexdigest().encode("ascii")
        return bytes(output)

    def check_clean(self) -> None:
        with _directory(self.root) as current:
            require(_identity(os.fstat(current))[:2] == _identity(os.fstat(self.fd))[:2],
                    "Source checkout directory changed")
        require(self._git("rev-parse", "--show-prefix") == b"\n", "Source tree must be a checkout root")
        # Configured filters can execute external programs during status. Refuse them before status.
        unsafe = self._git("config", "--local", "--no-includes", "--name-only", "--get-regexp",
                           r"^(filter\.|include\.|includeif\.|extensions\.worktreeconfig$)", code_one=True)
        require(not unsafe, "Source checkout has executable Git filters or indirect configuration")
        require(self._git("rev-parse", "--verify", "HEAD^{commit}").strip() == self.commit.encode(),
                "Source HEAD differs from the reviewed commit")
        origins = self._git("config", "--local", "--no-includes", "--get-all", "remote.origin.url").splitlines()
        require(len(origins) == 1 and origins[0].lower() in _ORIGINS, "Unexpected source origin")
        # Also reject locally marked assume-unchanged/skip-worktree paths that status could miss.
        flags = self._git("ls-files", "-v", "-z").split(b"\0")
        require(not any(line and not line.startswith(b"H ") for line in flags),
                "Source checkout hides tracked files from cleanliness checks")
        require(not self._git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"),
                "Reviewed source checkout contains uncommitted changes")

    def check_blob(self, source_path: str, size: int, sha256: str) -> None:
        row = self._git("--literal-pathspecs", "ls-tree", "-z", self.commit, "--", source_path)
        prefix, sep, suffix = row.partition(b"\t")
        mode, object_type, blob_id = (prefix.split() + [b"", b"", b""])[:3]
        require(sep and suffix == source_path.encode() + b"\0"
                and mode in (b"100644", b"100755") and object_type == b"blob"
                and re.fullmatch(rb"[a-f0-9]{40}", blob_id) is not None,
                "Source evidence does not name a tracked regular blob")
        oid = blob_id.decode("ascii")
        require(self._git("cat-file", "-s", oid).strip() == str(size).encode(),
                "Committed source blob length differs from evidence")
        require(self._git("cat-file", "blob", oid, hash_size=size) == sha256.encode("ascii")
                and _hash(self.fd, source_path, MAX_OPAQUE_EVIDENCE_BYTES, size) == sha256,
                "Committed or working source bytes differ from retained evidence")


class _RetainedEvidence:
    """Stream each unique original or retained file, then parse only known small records."""

    def __init__(self, release_fd: int, mapping: dict[str, EvidenceMapping], *,
                 original: int | None = None, evidence_fd: int | None = None):
        self.release_fd = release_fd
        self.mapping = mapping
        self.original = original
        self.evidence_fd = evidence_fd
        self.sizes: dict[str, int] = {}
        self.total = 0

    def validate(self, ref: Ref, maximum: int | None = None) -> int:
        maximum = MAX_OPAQUE_EVIDENCE_BYTES if maximum is None else maximum
        entry = self.mapping.get(ref.path)
        if entry is not None:
            require(entry.sha256 == ref.sha256, "Conflicting digests for an evidence path")
        if ref.path in self.sizes:
            require(self.sizes[ref.path] <= maximum, "Evidence exceeds its interpretation's byte limit")
            return self.sizes[ref.path]

        if self.original is not None:
            require(entry is None, "Unexpected preexisting evidence mapping")
            name = f"{len(self.mapping):04d}-{ref.sha256}.evidence"
            entry = EvidenceMapping(ref.path, f"evidence/{name}", ref.sha256)
            with _regular(self.original, ref.path, maximum) as (source, size):
                self._check_total(size)
                _copy_file(source, size, ref.sha256, self.evidence_fd, name)
            self.mapping[ref.path] = entry
        else:
            require(entry is not None, "Evidence mapping missing")
            with _regular(self.release_fd, entry.snapshot_path, maximum) as (file, size):
                self._check_total(size)
                require(_stream_hash(file, size) == ref.sha256, "Retained evidence bytes differ")

        self.total += size
        self.sizes[ref.path] = size
        return size

    def _check_total(self, size: int) -> None:
        require(self.total + size <= MAX_TOTAL_EVIDENCE_BYTES, "Retained evidence exceeds its aggregate byte limit")

    def read(self, ref: Ref, maximum: int = MAX_JSON_BYTES) -> bytes:
        self.validate(ref, maximum)
        raw = _read(self.release_fd, self.mapping[ref.path].snapshot_path, maximum)
        require(_sha(raw) == ref.sha256, "Parsed evidence bytes differ")
        return raw


def _validate_profile_source(profile: Profile, retained: _RetainedEvidence,
                             source: _SourceCheckout | None) -> dict[str, str]:
    evidence = parse_source_evidence(retained.read(profile.source_evidence))
    inputs = {row.source_path: row.evidence for row in evidence.build_inputs}
    for role in (evidence.version_config, evidence.public_key_config):
        require(inputs.get(role.source_path) == role.evidence, "Build inputs omit exact profile source configuration")
    config = read_json(retained.read(evidence.version_config.evidence))
    require(isinstance(config, dict) and semver(config.get("version")) == profile.version,
            "Packaged version differs from reviewed Tauri configuration")

    trust = retained.read(evidence.public_key_config.evidence)
    declarations = list(_KEY_DECLARATION.finditer(trust))
    require(len(declarations) == 1 and b"/*" not in trust, "Unsupported reviewed entitlement key source declaration")
    declaration = declarations[0]
    if b"PUBLIC_KEY_BYTES" in declaration.group(0):
        require(len(_KEY_WIDTH.findall(trust)) == 1, "Unsupported entitlement public key width declaration")
    literals = declaration.group("bytes").strip().removesuffix(b",").split(b",")
    require(len(literals) == 32 and all(re.fullmatch(rb"0x[0-9a-fA-F]{2}", item.strip()) for item in literals),
            "Expected exactly 32 hexadecimal public key byte literals")
    key_bytes = bytes(int(item.strip(), 16) for item in literals)
    key_digest = _sha(key_bytes)
    require(retained.read(evidence.public_key, maximum=32) == key_bytes
            and profile.entitlement_public_key_sha256 == key_digest
            and profile.entitlement_key_id == key_digest[:8],
            "Reviewed entitlement key bytes, digest and identifier differ")

    for row in evidence.build_inputs:
        size = retained.validate(row.evidence)
        if source is not None:
            source.check_blob(row.source_path, size, row.evidence.sha256)
    return {path: ref.sha256 for path, ref in inputs.items()}


def _validate_evidence(release: ReleaseInput, retained: _RetainedEvidence,
                       source: _SourceCheckout | None = None) -> tuple[Profile, tuple[Inspection, ...], Acceptance]:
    profile = parse_profile(retained.read(release.profile))
    identity = (release.source_commit, release.version)
    require((profile.source_commit, profile.version) == identity, "Profile release identity differs")
    workflows = _validate_profile_source(profile, retained, source)
    profiles = {row.id: row for row in profile.builds}
    acceptance = parse_acceptance(retained.read(release.acceptance))
    require((acceptance.source_commit, acceptance.version, acceptance.profile_sha256) == (*identity, release.profile.sha256),
            "Acceptance release/profile identity differs")
    require({entry.id: entry.sha256 for entry in acceptance.artifacts} == {row.id: row.sha256 for row in release.artifacts},
            "Acceptance package identities differ")
    for gate in acceptance.gates:
        retained.validate(gate.evidence)

    inspections = []
    local_ids = set()
    ci_ids = set()
    artifacts = {row.id: row for row in release.artifacts}
    for artifact_id in ARTIFACT_IDS:
        artifact = artifacts[artifact_id]
        build_profile = profiles[artifact_id]
        build = parse_build_receipt(retained.read(artifact.build))
        inspection = parse_inspection(retained.read(artifact.inspection))
        require((build.artifact_id, build.source_commit, build.version, build.profile_sha256,
                 build.filename, build.size_bytes, build.sha256) ==
                (artifact_id, *identity, release.profile.sha256, artifact.filename, artifact.size_bytes, artifact.sha256),
                "Build receipt package or release identity differs")
        require((inspection.artifact_id, inspection.package_sha256) == (artifact_id, artifact.sha256),
                "Inspection package identity differs")
        require(build_profile.command_argv in {command.argv for command in build.build_commands},
                "Reviewed build command is absent from its build receipt")
        if isinstance(build, CiBuildReceipt):
            ci_id = (build.run_id, build.run_attempt, build.artifact_id_in_ci)
            require(ci_id not in ci_ids and workflows.get(build.workflow_path) == build.workflow_sha256,
                    "Duplicate CI identity or missing exact workflow linkage")
            ci_ids.add(ci_id)
        if isinstance(build, LocalBuildReceipt):
            require(build.build_id not in local_ids, "Duplicate local build identifier")
            local_ids.add(build.build_id)

        version = parse_inspection_version(retained.read(inspection.version_evidence))
        require((version.artifact_id, version.package_sha256, version.version, version.entitlement_key_id,
                 version.entitlement_public_key_sha256) ==
                (artifact_id, artifact.sha256, release.version, profile.entitlement_key_id,
                 profile.entitlement_public_key_sha256), "Package inspection version or entitlement identity differs")
        for ref in (
            build_profile.resolved_features, build_profile.release_boundary_check,
            build.toolchain, build.build_log, build.build_input_custody, build.package_metadata,
            inspection.architecture_evidence, version.evidence, inspection.signature_evidence,
            inspection.bundle_scan, inspection.payload_scan, inspection.development_key_scan,
            inspection.scan_positive_controls, inspection.build_input_custody,
        ):
            retained.validate(ref)
        inspections.append(inspection)
    return profile, tuple(inspections), acceptance


def _plan_for(release: ReleaseInput) -> PublicPlan:
    artifacts = {row.id: row for row in release.artifacts}
    objects = tuple(
        derive_object(artifact.id, release.version, artifact.filename, artifact.size_bytes, artifact.sha256)
        for artifact in (artifacts[artifact_id] for artifact_id in ARTIFACT_IDS)
    )
    return PublicPlan(1, release.release_id, release.version, release.source_commit, objects)


def _copy_file(source: BinaryIO, size: int, sha256: str, destination_fd: int, filename: str) -> None:
    fd = os.open(filename, _WRITE_FLAGS, 0o600, dir_fd=destination_fd)
    with os.fdopen(fd, "wb") as destination:
        require(_stream_hash(source, size, destination) == sha256, "Copied file digest differs from declared identity")
        destination.flush()
        os.fchmod(destination.fileno(), 0o400)
        os.fsync(destination.fileno())


def _snapshot_packages(original: int, package_dir: int, release: ReleaseInput) -> tuple[PackageMapping, ...]:
    result = []
    for row in sorted(release.artifacts, key=lambda artifact: ARTIFACT_IDS.index(artifact.id)):
        filename = f"{row.id}-{row.filename}"
        with _regular(original, row.path, MAX_PACKAGE_BYTES) as (source, size):
            require(size == row.size_bytes, "Package length differs from its build receipt")
            _copy_file(source, size, row.sha256, package_dir, filename)
        result.append(PackageMapping(row.id, row.path, f"packages/{filename}", row.size_bytes, row.sha256))
    os.fsync(package_dir)
    return tuple(result)


def _create_snapshot(
    original: int, raw: bytes, release: ReleaseInput, source: _SourceCheckout, output: Path, release_fd: int,
) -> PreparedRelease:
    os.mkdir("evidence", mode=0o700, dir_fd=release_fd)
    os.mkdir("packages", mode=0o700, dir_fd=release_fd)
    evidence: dict[str, EvidenceMapping] = {}
    with _subdirectory(release_fd, ("evidence",)) as evidence_fd:
        retained = _RetainedEvidence(release_fd, evidence, original=original, evidence_fd=evidence_fd)
        profile, inspections, acceptance = _validate_evidence(release, retained, source)
        require(not ({row.path for row in release.artifacts} & evidence.keys()),
                "A package cannot also be an evidence file")
        os.fsync(evidence_fd)

    with _subdirectory(release_fd, ("packages",)) as package_fd:
        packages = _snapshot_packages(original, package_fd, release)

    source.check_clean()
    plan = _plan_for(release)
    plan_bytes = record_bytes(plan)
    receipt = PrepareReceipt(
        1, _sha(raw), _sha(plan_bytes), release.source_commit, publisher_source_sha256(), utc_now(), packages,
        tuple(evidence[path] for path in sorted(evidence)),
    )
    receipt_bytes = record_bytes(receipt)
    _write_atomic(release_fd, _INPUT, raw)
    _write_atomic(release_fd, _PLAN, plan_bytes)
    _write_atomic(release_fd, _RECEIPT, receipt_bytes)
    return PreparedRelease(output, release, profile, inspections, acceptance, receipt, plan)


def prepare_release(input_path: Path, source_tree: Path, out_dir: Path) -> PreparedRelease:
    input_path, source_tree, out_dir = map(_absolute, (input_path, source_tree, out_dir))
    require(bool(input_path.name and out_dir.name), "Expected named input and output paths")
    nonsecret_path(input_path.name)
    try:
        with _directory(input_path.parent) as original, _directory(source_tree) as source_fd:
            raw = _read(original, input_path.name)
            release = parse_release_input(raw)
            source = _SourceCheckout(source_tree, source_fd, release.source_commit)
            source.check_clean()
            with _directory(out_dir.parent) as parent:
                try:
                    os.mkdir(out_dir.name, mode=0o700, dir_fd=parent)
                except FileExistsError as exc:
                    raise PublicationError(2, "Release output directory must not already exist") from exc
                try:
                    os.fsync(parent)
                    with _subdirectory(parent, (out_dir.name,)) as output_fd:
                        os.fchmod(output_fd, 0o700)
                        return _create_snapshot(original, raw, release, source, out_dir, output_fd)
                except OSError as exc:
                    if exc.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                        raise PublicationError(5, "Cannot write or sync private publication snapshot") from exc
                    raise
    except OSError as exc:
        raise PublicationError(2, "Cannot open a contained regular publication input or directory") from exc


def load_prepared_release(release_dir: Path) -> PreparedRelease:
    root = _absolute(release_dir)
    try:
        with _directory(root) as directory:
            require(stat.S_IMODE(os.fstat(directory).st_mode) == 0o700, "Release directory is no longer private")
            raw = _read(directory, _INPUT)
            plan_raw = _read(directory, _PLAN)
            receipt = parse_prepare_receipt(_read(directory, _RECEIPT))
            release = parse_release_input(raw)
            plan = parse_public_plan(plan_raw)
            require(receipt.input_sha256 == _sha(raw) and receipt.plan_sha256 == _sha(plan_raw)
                    and receipt.source_commit == release.source_commit and plan == _plan_for(release)
                    and plan_raw == record_bytes(plan), "Retained input or canonical plan identity differs")
            require(receipt.publisher_source_sha256 == publisher_source_sha256(), "Publisher source inventory differs")
            mapping = {row.original_path: row for row in receipt.evidence}
            retained = _RetainedEvidence(directory, mapping)
            profile, inspections, acceptance = _validate_evidence(release, retained)
            require(retained.sizes.keys() == mapping.keys(), "Unexpected unreferenced evidence mapping")
            artifacts = {row.id: row for row in release.artifacts}
            for row in receipt.packages:
                original = artifacts[row.id]
                require((row.original_path, row.size_bytes, row.sha256) == (original.path, original.size_bytes, original.sha256),
                        "Retained package mapping differs from its original identity")
                require(_hash(directory, row.snapshot_path, MAX_PACKAGE_BYTES, row.size_bytes) == row.sha256,
                        "Retained package bytes differ")
    except OSError as exc:
        raise PublicationError(2, "Cannot read a contained regular snapshot file") from exc
    return PreparedRelease(root, release, profile, inspections, acceptance, receipt, plan)
